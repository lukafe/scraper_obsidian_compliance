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
    ) -> dict[str, Any]:
        """Send one message; return { 'text', 'raw', 'usage' }."""
        tools: list[genai_types.Tool] = []
        if use_web_search and self.cfg.web_search_enabled:
            tools.append(genai_types.Tool(google_search=genai_types.GoogleSearch()))

        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
            tools=tools or None,
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
        out_tok = getattr(usage, "candidates_token_count", 0) or 0
        rec = self.ledger.add(model, in_tok, out_tok)
        # Override cost with Gemini-specific pricing (the shared ledger only
        # knows Anthropic prices by default).
        rec.cost_usd = _estimate_gemini_cost(model, in_tok, out_tok)
        log.info(
            "gemini call model=%s in=%d out=%d cost=$%.4f time=%.1fs ws=%s",
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
