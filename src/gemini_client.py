"""Google Gemini client with the same surface as AnthropicClient.

Methods `message`, `message_json`, and attribute `ledger` are duck-typed
identical so the rest of the pipeline (discovery, analyzer, normalizer)
doesn't care which provider is behind it.

Web search is implemented via Google Search grounding — Gemini's equivalent
to Anthropic's `web_search` server-side tool. When `use_web_search=True`,
the model is given the `google_search` tool and decides on its own whether
to query it.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

from google import genai
from google.genai import types as genai_types
from google.genai import errors as genai_errors
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .anthropic_client import CostLedger, parse_json_lenient

log = logging.getLogger(__name__)


# Rough pricing in USD per million tokens (input / output). Estimates.
GEMINI_PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "gemini-2.5-pro":        (1.25, 10.0),
    "gemini-2.5-flash":      (0.30,  2.50),
    "gemini-2.5-flash-lite": (0.10,  0.40),
    "gemini-2.0-flash":      (0.10,  0.40),
    "gemini-2.0-flash-001":  (0.10,  0.40),
}


@dataclass
class GeminiConfig:
    discovery_model: str = "gemini-2.5-flash"
    analysis_model: str = "gemini-2.5-flash"
    extraction_model: str = "gemini-2.5-flash-lite"
    web_search_enabled: bool = True
    max_attempts: int = 5
    base_delay_seconds: float = 2.0
    max_delay_seconds: float = 60.0


class GeminiClient:
    """Drop-in alternative to AnthropicClient."""

    def __init__(self, cfg: GeminiConfig, api_key: Optional[str] = None):
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set")
        self.cfg = cfg
        self.client = genai.Client(api_key=key)
        self.ledger = CostLedger()

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
        max_web_searches: Optional[int] = None,  # accepted for parity; Gemini has no cap knob
        thinking_budget: Optional[int] = 0,       # 0 = thinking disabled (default for our prompts)
    ) -> dict[str, Any]:
        """Send one message; return { 'text', 'raw', 'usage' }.

        Note on `thinking_budget`: Gemini 2.5 models reason internally before
        producing visible output. For discovery/analysis prompts (enumeration,
        extraction) we disable it (`thinking_budget=0`) so the entire token
        budget goes to the visible JSON. Otherwise the response can hit
        MAX_TOKENS mid-output. Set higher (e.g. 4000) for tasks that genuinely
        need multi-step reasoning.
        """
        tools: list[genai_types.Tool] = []
        if use_web_search and self.cfg.web_search_enabled:
            tools.append(genai_types.Tool(google_search=genai_types.GoogleSearch()))

        thinking_cfg = None
        if thinking_budget is not None:
            thinking_cfg = genai_types.ThinkingConfig(thinking_budget=int(thinking_budget))

        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
            tools=tools or None,
            thinking_config=thinking_cfg,
        )

        @retry(
            reraise=True,
            stop=stop_after_attempt(self.cfg.max_attempts),
            wait=wait_exponential(
                multiplier=self.cfg.base_delay_seconds,
                max=self.cfg.max_delay_seconds,
            ),
            retry=retry_if_exception_type(
                (genai_errors.APIError, genai_errors.ServerError, TimeoutError)
            ),
        )
        def _call() -> Any:
            return self.client.models.generate_content(
                model=model,
                contents=user,
                config=config,
            )

        t0 = time.time()
        resp = _call()
        elapsed = time.time() - t0

        text = _extract_text(resp)
        usage = getattr(resp, "usage_metadata", None)
        in_tok = getattr(usage, "prompt_token_count", 0) or 0
        cand_tok = getattr(usage, "candidates_token_count", 0) or 0
        thoughts_tok = getattr(usage, "thoughts_token_count", 0) or 0
        out_tok_billed = cand_tok + thoughts_tok
        rec = self.ledger.add(model, in_tok, out_tok_billed)
        rec.cost_usd = _estimate_gemini_cost(model, in_tok, out_tok_billed)

        finish_reason_name = ""
        if resp.candidates:
            fr = getattr(resp.candidates[0], "finish_reason", None)
            if fr is not None:
                finish_reason_name = fr.name if hasattr(fr, "name") else str(fr)

        log.info(
            "gemini call model=%s in=%d out=%d (visible=%d thoughts=%d) cost=$%.4f time=%.1fs ws=%s finish=%s",
            model, in_tok, out_tok_billed, cand_tok, thoughts_tok,
            rec.cost_usd, elapsed, use_web_search, finish_reason_name,
        )

        # RECITATION fallback: Gemini's safety layer blocks output when it
        # thinks the model is about to reproduce copyrighted text. Citing
        # official law titles + URLs sometimes trips this. Retry once without
        # the web_search tool — the model still has built-in knowledge of
        # major legal frameworks. This is a no-op if web_search wasn't used.
        if (
            not text
            and use_web_search
            and finish_reason_name in {"RECITATION", "SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"}
        ):
            log.info("retrying without web_search after %s", finish_reason_name)
            fallback_config = genai_types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_tokens,
                tools=None,
                thinking_config=thinking_cfg,
            )
            try:
                resp2 = self.client.models.generate_content(
                    model=model, contents=user, config=fallback_config,
                )
                text2 = _extract_text(resp2)
                if text2:
                    usage2 = getattr(resp2, "usage_metadata", None)
                    in2 = getattr(usage2, "prompt_token_count", 0) or 0
                    cand2 = getattr(usage2, "candidates_token_count", 0) or 0
                    th2 = getattr(usage2, "thoughts_token_count", 0) or 0
                    rec2 = self.ledger.add(model, in2, cand2 + th2)
                    rec2.cost_usd = _estimate_gemini_cost(model, in2, cand2 + th2)
                    log.info("retry recovered %d chars (extra cost $%.4f)", len(text2), rec2.cost_usd)
                    return {"text": text2, "raw": resp2, "usage": rec2}
            except Exception as e:
                log.warning("retry without web_search failed: %s", e)

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
        thinking_budget: Optional[int] = 0,
    ) -> Any:
        out = self.message(
            model=model,
            system=system,
            user=user,
            max_tokens=max_tokens,
            temperature=0.0,
            use_web_search=use_web_search,
            max_web_searches=max_web_searches,
            thinking_budget=thinking_budget,
        )
        return parse_json_lenient(out["text"])


# ---------- helpers -------------------------------------------------------


def _extract_text(resp: Any) -> str:
    """Concatenate text parts from a Gemini response."""
    # Easy path: SDK exposes .text directly when there's a single text part.
    direct = getattr(resp, "text", None)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    # Walk candidates → content.parts → .text
    out: list[str] = []
    for cand in getattr(resp, "candidates", None) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", None) or []:
            t = getattr(part, "text", None)
            if t:
                out.append(t)
    return "\n".join(out).strip()


def _estimate_gemini_cost(model: str, in_tok: int, out_tok: int) -> float:
    base = model
    if base not in GEMINI_PRICING_USD_PER_MTOK:
        base = re.sub(r"-\d{3,}$", "", base)
    pi, po = GEMINI_PRICING_USD_PER_MTOK.get(base, (0.0, 0.0))
    return (in_tok * pi + out_tok * po) / 1_000_000.0
