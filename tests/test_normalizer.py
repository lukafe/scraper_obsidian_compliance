"""Normalizer: cleaning, truncation, language detection."""

from __future__ import annotations

from src.normalizer import (
    MAX_BODY_CHARS,
    clean_text,
    detect_language,
    truncate,
    normalize,
)


def test_clean_collapses_whitespace_and_blank_lines():
    raw = "Article  1\t\n\n\n\nText\f\fnext page"
    out = clean_text(raw)
    assert "  " not in out
    assert "\n\n\n" not in out
    assert "\f" not in out


def test_clean_strips_page_numbers():
    raw = "real content\npage 4 of 12\nmore content\nPágina 5 de 30\nfinal"
    out = clean_text(raw)
    assert "page 4" not in out.lower()
    assert "página 5" not in out.lower()


def test_truncate_within_limit_is_passthrough():
    s = "short"
    out, tr = truncate(s)
    assert out == s
    assert not tr


def test_truncate_marks_when_cut():
    s = "x" * (MAX_BODY_CHARS + 1000)
    out, tr = truncate(s)
    assert tr
    assert out.endswith("*[truncated]*")
    assert len(out) <= MAX_BODY_CHARS + 30


def test_detect_language_english():
    text = "This Act establishes the framework for crypto-asset regulation. " * 5
    assert detect_language(text) == "en"


def test_detect_language_portuguese():
    text = (
        "Esta Lei dispõe sobre as diretrizes a serem observadas na prestação de "
        "serviços de ativos virtuais e na regulamentação das prestadoras de "
        "serviços de ativos virtuais. "
    ) * 3
    assert detect_language(text) == "pt"


def test_normalize_no_translate_returns_clean_body():
    raw = "Article  1\n\n\n\nThe present Act regulates crypto. " * 5
    nb = normalize(raw, translate_to=None)
    assert "  " not in nb.body
    assert nb.language == "en"
    assert not nb.truncated
