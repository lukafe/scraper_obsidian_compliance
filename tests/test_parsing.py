"""Lenient JSON parsing + analyzer citation/related parsers."""

from __future__ import annotations

import pytest

from src.analyzer import _parse_citations, _parse_related
from src.anthropic_client import parse_json_lenient


# ---------- parse_json_lenient ------------------------------------------


@pytest.mark.parametrize("text,expected", [
    ('[{"a": 1}]', [{"a": 1}]),
    ('```json\n[{"a": 1}]\n```', [{"a": 1}]),
    ('```\n[{"a": 1}]\n```', [{"a": 1}]),
    ('preamble\n[{"a": 1}]\nepilogue', [{"a": 1}]),
    ('{"k": [1, 2, 3]}', {"k": [1, 2, 3]}),
])
def test_parse_json_lenient_variants(text, expected):
    assert parse_json_lenient(text) == expected


def test_parse_json_lenient_raises_on_unparseable():
    with pytest.raises(ValueError):
        parse_json_lenient("nothing JSON here at all")


def test_parse_json_lenient_raises_on_empty():
    with pytest.raises(ValueError):
        parse_json_lenient("")


# ---------- analyzer parsers --------------------------------------------


def test_parse_citations_drops_invalid_type_and_empty_title():
    out = _parse_citations([
        {"title": "Good Law", "country": "BR", "type": "statute"},
        {"title": "Bad Type", "country": "BR", "type": "executive_memo"},
        {"title": "", "country": "BR", "type": "statute"},  # empty title
        "not a dict",
    ])
    assert len(out) == 1
    assert out[0].title == "Good Law"


def test_parse_citations_treaty_maps_to_guidance():
    out = _parse_citations([
        {"title": "FATF Recommendation 16", "country": "INTL", "type": "treaty"},
    ])
    assert len(out) == 1
    assert out[0].type == "guidance"


def test_parse_citations_normalizes_country():
    out = _parse_citations([
        {"title": "X", "country": "br", "type": "statute"},
        {"title": "Y", "country": None, "type": "statute"},
    ])
    assert out[0].country == "BR"
    assert out[1].country == "INTL"   # default for missing


def test_parse_related_rejects_treaty_type():
    # "treaty" is only allowed in citations, not in `related`.
    out = _parse_related([
        {"title": "X", "country": "BR", "type": "treaty"},
        {"title": "Y", "country": "BR", "type": "regulation"},
    ])
    assert len(out) == 1
    assert out[0].title == "Y"
