"""Normalize fetched text into clean markdown.

- detects language (best-effort, with langdetect)
- cleans whitespace / boilerplate
- truncates extremely long bodies (legislative consolidations can be >1MB)
- optionally adds a translated section *below* the original (never replaces)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from .anthropic_client import AnthropicClient

log = logging.getLogger(__name__)


# Hard ceiling on body size we'll write to a vault note. Most norms are well
# under this; gigantic codes (e.g. a full civil code) get trimmed.
MAX_BODY_CHARS = 120_000

# Hard ceiling on text we'll send to the LLM for translation.
MAX_TRANSLATE_CHARS = 40_000


# ---------- Cleaning -----------------------------------------------------


_WS = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_PAGE_NUMS = re.compile(r"^\s*(page|página|seite)?\s*\d+\s*(of|de|von)\s*\d+\s*$",
                        re.IGNORECASE | re.MULTILINE)
_FORM_FEEDS = re.compile(r"[\f\x0b]+")


def clean_text(s: str) -> str:
    if not s:
        return ""
    s = _FORM_FEEDS.sub("\n\n", s)
    s = _PAGE_NUMS.sub("", s)
    # Collapse runs of spaces/tabs (but keep newlines).
    s = "\n".join(_WS.sub(" ", line.rstrip()) for line in s.splitlines())
    s = _BLANK_LINES.sub("\n\n", s)
    return s.strip()


def truncate(s: str, limit: int = MAX_BODY_CHARS) -> tuple[str, bool]:
    if len(s) <= limit:
        return s, False
    cut = s[:limit]
    # Try to break on a paragraph boundary.
    last = cut.rfind("\n\n")
    if last > limit * 0.8:
        cut = cut[:last]
    return cut + "\n\n*[truncated]*", True


# ---------- Language detection -------------------------------------------


def detect_language(s: str) -> Optional[str]:
    if not s or len(s) < 80:
        return None
    try:
        from langdetect import detect, DetectorFactory  # type: ignore
        DetectorFactory.seed = 0  # deterministic
        return detect(s[:4000])
    except Exception as e:
        log.debug("language detection failed: %s", e)
        return None


# ---------- Translation --------------------------------------------------


_TRANSLATE_SYSTEM = """You translate legal texts faithfully. Preserve numbering,
article references, definitions, and legal terms of art. Do NOT summarize, do
NOT add commentary. Output the translation only, in markdown, no preamble."""


def translate(
    client: AnthropicClient,
    *,
    text: str,
    source_lang: Optional[str],
    target_lang: str,
    model: str,
) -> Optional[str]:
    if not text.strip():
        return None
    src = source_lang or "the source language"
    chunk = text[:MAX_TRANSLATE_CHARS]
    user = (
        f"Translate the following legal text from {src} to {target_lang}.\n\n"
        f"---\n{chunk}\n---"
    )
    try:
        out = client.message(
            model=model,
            system=_TRANSLATE_SYSTEM,
            user=user,
            max_tokens=8000,
        )
        return out["text"].strip() or None
    except Exception as e:
        log.warning("translation failed: %s", e)
        return None


# ---------- Top-level ----------------------------------------------------


@dataclass
class NormalizedBody:
    body: str
    language: Optional[str]
    truncated: bool


def normalize(
    raw_text: str,
    *,
    translate_to: Optional[str] = None,
    client: Optional[AnthropicClient] = None,
    translation_model: str = "claude-haiku-4-5-20251001",
) -> NormalizedBody:
    """Clean + (optionally) translate.

    When `translate_to` is provided and the detected source language differs,
    the body becomes ENGLISH-FIRST: the translated text is the main content,
    and the original is collapsed into a `<details>` block at the bottom for
    legal verification. Engineers reading the vault see English by default;
    a lawyer auditing the source can click to expand the original.
    """
    cleaned = clean_text(raw_text)
    lang = detect_language(cleaned)
    body_original, truncated = truncate(cleaned)

    should_translate = (
        translate_to
        and client is not None
        and lang is not None
        and lang != translate_to
        and len(cleaned) > 200
    )

    if not should_translate:
        return NormalizedBody(body=body_original, language=lang, truncated=truncated)

    translated = translate(
        client,
        text=cleaned,
        source_lang=lang,
        target_lang=translate_to,
        model=translation_model,
    )
    if not translated:
        # Translation failed — keep the original rather than blocking the pipeline.
        return NormalizedBody(body=body_original, language=lang, truncated=truncated)

    # English-first: translation is the main body; original goes in a foldable section.
    body = (
        f"> *Auto-translated from `{lang}` to `{translate_to}`. "
        f"For legal verification, expand the original below or follow `source_url`.*\n\n"
        + translated
        + "\n\n---\n\n"
        + f"<details>\n<summary>Original text ({lang})</summary>\n\n"
        + body_original
        + "\n\n</details>\n"
    )
    return NormalizedBody(body=body, language=lang, truncated=truncated)
