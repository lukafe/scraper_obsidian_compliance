"""Confidence: authority classification, title-match scoring, blended score, quarantine policy."""

from __future__ import annotations

import pytest

from src.confidence import (
    Liveness,
    classify_authority,
    compute_confidence,
    should_quarantine,
    title_match_score,
)


@pytest.mark.parametrize("url,expected", [
    ("https://www.bcb.gov.br/foo", "primary"),
    ("https://eur-lex.europa.eu/legal-content/EN", "primary"),
    ("https://www.fca.org.uk/firms/cryptoassets", "primary"),
    ("https://sso.agc.gov.sg/Act/PSA2019", "primary"),
    ("https://www.fatf-gafi.org/x", "primary"),
    ("https://www.lexology.com/x", "secondary"),
    ("https://random-blog.example.com/post", "tertiary"),
    (None, "tertiary"),
    ("", "tertiary"),
])
def test_classify_authority(url, expected):
    assert classify_authority(url) == expected


def test_title_match_high_score_on_exact_substring():
    score = title_match_score(
        "Instrução Normativa BCB nº 701",
        "Banco Central > Instrução Normativa BCB nº 701, de 15 de novembro de 2024.",
    )
    assert score > 0.9


def test_title_match_low_score_on_unrelated_text():
    score = title_match_score(
        "Markets in Crypto-Assets Regulation",
        "Welcome to our cooking blog! Today: best banana bread recipe.",
    )
    assert score < 0.6


def test_title_match_handles_empty_inputs():
    assert title_match_score("", "anything") == 0.0
    assert title_match_score("title", "") == 0.0


def test_compute_confidence_primary_high():
    live = Liveness(ok=True, status_code=200, content_length=10_000)
    c = compute_confidence(authority="primary", liveness=live, title_score=0.95)
    assert c > 0.8


def test_compute_confidence_dead_url_kills_score():
    live = Liveness(ok=False, status_code=404)
    c = compute_confidence(authority="primary", liveness=live, title_score=1.0)
    assert c == 0.0


def test_compute_confidence_tiny_page_penalized():
    live = Liveness(ok=True, status_code=200, content_length=50)
    c_tiny = compute_confidence(authority="primary", liveness=live, title_score=1.0)
    live_big = Liveness(ok=True, status_code=200, content_length=10_000)
    c_big = compute_confidence(authority="primary", liveness=live_big, title_score=1.0)
    assert c_tiny < c_big


def test_tertiary_always_quarantined_regardless_of_score():
    live = Liveness(ok=True, status_code=200, content_length=20_000)
    c = compute_confidence(authority="tertiary", liveness=live, title_score=1.0)
    # Even at the highest possible tertiary score, the policy quarantines.
    assert should_quarantine(c, "tertiary", threshold=0.0) is True


def test_primary_passes_threshold_at_default():
    live = Liveness(ok=True, status_code=200, content_length=10_000)
    c = compute_confidence(authority="primary", liveness=live, title_score=0.9)
    assert should_quarantine(c, "primary", threshold=0.70) is False
