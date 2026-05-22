"""Wrapper around the Anthropic SDK.

Centralizes:
  - model selection (discovery / analysis / extraction)
  - the native `web_search` server-side tool
  - retry/backoff
  - token + cost bookkeeping
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from anthropic import Anthropic, APIStatusError, APITimeoutError, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger(__name__)


# ---------- Cost ledger ---------------------------------------------------

# Rough pricing in USD per million tokens (input / output). Update as needed —
# these numbers are only used for the run-log estimate and never gate work.
PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    # in, out
    "claude-opus-4-7":        (15.0, 75.0),
    "claude-sonnet-4-6":      (3.0,  15.0),
    "claude-haiku-4-5":       (1.0,   5.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}


def _estimate_cost(model: str, in_tok: int, out_tok: int) -> float:
    base = model
    if base not in PRICING_USD_PER_MTOK:
        # Trim a trailing date if present (claude-haiku-4-5-20251001 -> claude-haiku-4-5)
        base = re.sub(r"-\d{8}$", "", base)
    pi, po = PRICING_USD_PER_MTOK.get(base, (0.0, 0.0))
    return (in_tok * pi + out_tok * po) / 1_000_000.0


@dataclass
class UsageRecord:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass
class CostLedger:
    records: list[UsageRecord] = field(default_factory=list)

    def add(self, model: str, input_tokens: int, output_tokens: int) -> UsageRecord:
        rec = UsageRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=_estimate_cost(model, input_tokens, output_tokens),
        )
        self.records.append(rec)
        return rec

    def total_tokens(self) -> int:
        return sum(r.input_tokens + r.output_tokens for r in self.records)

    def total_cost(self) -> float:
        return sum(r.cost_usd for r in self.records)

    def summary(self) -> dict[str, Any]:
        by_model: dict[str, dict[str, float]] = {}
        for r in self.records:
            m = by_model.setdefault(r.model, {"input": 0, "output": 0, "cost_usd": 0.0})
            m["input"] += r.input_tokens
            m["output"] += r.output_tokens
            m["cost_usd"] += r.cost_usd
        return {
            "calls": len(self.records),
            "total_tokens": self.total_tokens(),
            "total_cost_usd": round(self.total_cost(), 4),
            "by_model": {
                k: {**v, "cost_usd": round(v["cost_usd"], 4)} for k, v in by_model.items()
            },
        }


# ---------- Client --------------------------------------------------------


_WEB_SEARCH_TOOL_TYPE = "web_search_20250305"


@dataclass
class AnthropicConfig:
    discovery_model: str = "claude-sonnet-4-6"
    analysis_model: str = "claude-sonnet-4-6"
    extraction_model: str = "claude-haiku-4-5-20251001"
    web_search_enabled: bool = True
    web_search_max_uses: int = 5
    max_attempts: int = 5
    base_delay_seconds: float = 2.0
    max_delay_seconds: float = 60.0


class AnthropicClient:
    """Thin wrapper around `anthropic.Anthropic`."""

    def __init__(self, cfg: AnthropicConfig, api_key: Optional[str] = None):
        self.cfg = cfg
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.ledger = CostLedger()

    # ------------------------------------------------------------------

    def _web_search_tool(self, max_uses: Optional[int] = None) -> dict[str, Any]:
        return {
            "type": _WEB_SEARCH_TOOL_TYPE,
            "name": "web_search",
            "max_uses": max_uses or self.cfg.web_search_max_uses,
        }

    # ------------------------------------------------------------------

    def message(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 4000,
        temperature: float = 0.0,
        use_web_search: bool = False,
        max_web_searches: Optional[int] = None,
    ) -> dict[str, Any]:
        """Send one message and return a dict:

            { "text": <concatenated assistant text>,
              "raw":  <full SDK response>,
              "usage": UsageRecord }
        """
        tools: list[dict[str, Any]] = []
        if use_web_search and self.cfg.web_search_enabled:
            tools.append(self._web_search_tool(max_web_searches))

        @retry(
            reraise=True,
            stop=stop_after_attempt(self.cfg.max_attempts),
            wait=wait_exponential(
                multiplier=self.cfg.base_delay_seconds,
                max=self.cfg.max_delay_seconds,
            ),
            retry=retry_if_exception_type(
                (RateLimitError, APITimeoutError, APIStatusError)
            ),
        )
        def _call() -> Any:
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
            if tools:
                kwargs["tools"] = tools
            return self.client.messages.create(**kwargs)

        t0 = time.time()
        resp = _call()
        elapsed = time.time() - t0

        text = _extract_text(resp)
        in_tok = getattr(resp.usage, "input_tokens", 0) or 0
        out_tok = getattr(resp.usage, "output_tokens", 0) or 0
        rec = self.ledger.add(model, in_tok, out_tok)
        log.info(
            "anthropic call model=%s in=%d out=%d cost=$%.4f time=%.1fs ws=%s",
            model, in_tok, out_tok, rec.cost_usd, elapsed, use_web_search,
        )
        return {"text": text, "raw": resp, "usage": rec}

    # ------------------------------------------------------------------

    def message_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 4000,
        use_web_search: bool = False,
        max_web_searches: Optional[int] = None,
    ) -> Any:
        """Like `message`, but parses the response as strict JSON.

        Prompts should already instruct the model to return JSON only. We
        defensively strip ``` fences and surrounding prose.
        """
        out = self.message(
            model=model,
            system=system,
            user=user,
            max_tokens=max_tokens,
            temperature=0.0,
            use_web_search=use_web_search,
            max_web_searches=max_web_searches,
        )
        return parse_json_lenient(out["text"])


# ---------- Response parsing ---------------------------------------------


def _extract_text(resp: Any) -> str:
    """Concatenate all text blocks from the response."""
    parts: list[str] = []
    for block in getattr(resp, "content", []) or []:
        # SDK content blocks: TextBlock, ToolUseBlock, ServerToolUseBlock,
        # WebSearchResultBlock, etc. We only want assistant prose.
        btype = getattr(block, "type", None)
        if btype == "text":
            parts.append(getattr(block, "text", "") or "")
    return "\n".join(parts).strip()


_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json_lenient(text: str) -> Any:
    """Parse JSON from a model response, tolerating fences and prefatory prose."""
    if not text:
        raise ValueError("empty response")

    s = text.strip()
    # Strip a single leading/trailing code fence if present.
    if s.startswith("```"):
        s = _CODE_FENCE.sub("", s).strip()

    # Try direct first.
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # Fall back: extract the first {...} or [...] block.
    for opener, closer in [("[", "]"), ("{", "}")]:
        start = s.find(opener)
        end = s.rfind(closer)
        if start != -1 and end != -1 and end > start:
            chunk = s[start : end + 1]
            try:
                return json.loads(chunk)
            except json.JSONDecodeError:
                continue

    raise ValueError(f"could not parse JSON from response: {text[:300]!r}")
