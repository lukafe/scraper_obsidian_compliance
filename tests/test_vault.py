"""Vault foundation: deterministic IDs, dedup, status-rank merge, folder routing."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.vault import (
    QUARANTINE_DIR,
    Note,
    Vault,
    make_id,
    parse_wikilink,
    wikilink,
)


# ---------- ID derivation ------------------------------------------------


@pytest.mark.parametrize("kwargs,expected", [
    (dict(country="BR", title="Lei nº 14.478, de 21 de dezembro de 2022"),
     "BR-LEI14478-2022"),
    (dict(country="EU", title="Markets in Crypto-Assets Regulation (MiCA)",
          date_str="2023-05-31"), "EU-MICA-2023"),
    (dict(country="US", title="The CLARITY Act of 2025"),
     "US-CLARITYACT-2025"),
])
def test_make_id_known_cases(kwargs, expected):
    assert make_id(**kwargs) == expected


def test_make_id_is_deterministic_across_whitespace():
    a = make_id(country="BR", title="Lei nº 14.478")
    b = make_id(country="BR", title="  Lei nº 14.478  ")
    assert a == b


def test_make_id_uppercases_country():
    assert make_id(country="br", title="X").startswith("BR-")


# ---------- Vault round-trip + dedup ------------------------------------


def _note(**over):
    base = dict(
        id="BR-LEI14478-2022",
        country="BR",
        jurisdiction="Brasil",
        type="statute",
        title="Lei nº 14.478",
        status="verified",
    )
    base.update(over)
    return Note(**base)


def test_vault_roundtrip(tmp_path: Path):
    v = Vault(tmp_path)
    n = _note(source_url="https://www.in.gov.br/x", confidence=0.95, date="2022-12-21")
    v.write(n)
    back = v.read(n.id)
    assert back is not None
    assert back.id == n.id
    assert back.status == "verified"
    assert back.source_url == n.source_url
    assert back.confidence == 0.95


def test_vault_upsert_does_not_regress_status(tmp_path: Path):
    v = Vault(tmp_path)
    v.write(_note(status="verified"))
    merged, created = v.upsert(_note(status="discovered"))
    assert not created
    assert merged.status == "verified"


def test_vault_upsert_advances_status_and_merges_refs(tmp_path: Path):
    v = Vault(tmp_path)
    v.write(_note(status="verified", references=["[[INTL-FATF16-X]]"],
                  ref_types={"INTL-FATF16-X": "citation"}))
    merged, _ = v.upsert(_note(
        status="analyzed",
        references=["[[INTL-FATF16-X]]", "[[INTL-IOSCO-2023]]"],
        ref_types={"INTL-FATF16-X": "semantic",   # must NOT overwrite "citation"
                   "INTL-IOSCO-2023": "semantic"},
    ))
    assert merged.status == "analyzed"
    assert "[[INTL-IOSCO-2023]]" in merged.references
    assert merged.ref_types["INTL-FATF16-X"] == "citation"
    assert merged.ref_types["INTL-IOSCO-2023"] == "semantic"


def test_vault_quarantine_routing(tmp_path: Path):
    v = Vault(tmp_path)
    v.write(_note(id="BR-FAKE-2099", status="quarantine", confidence=0.1))
    p = v.find_path("BR-FAKE-2099")
    assert p is not None
    assert QUARANTINE_DIR in str(p)


def test_vault_query_by_status_and_country(tmp_path: Path):
    v = Vault(tmp_path)
    v.write(_note(id="BR-A-2020", status="verified"))
    v.write(_note(id="BR-B-2021", status="analyzed"))
    v.write(_note(id="US-C-2022", country="US", jurisdiction="US", status="verified"))
    assert {n.id for n in v.query(status="verified")} == {"BR-A-2020", "US-C-2022"}
    assert {n.id for n in v.query(status="verified", country="BR")} == {"BR-A-2020"}
    assert {n.id for n in v.query(country="BR")} == {"BR-A-2020", "BR-B-2021"}


def test_status_change_moves_file(tmp_path: Path):
    v = Vault(tmp_path)
    v.write(_note(id="BR-X-2024", status="verified"))
    p1 = v.find_path("BR-X-2024")
    assert QUARANTINE_DIR not in str(p1)
    v.write(_note(id="BR-X-2024", status="quarantine", confidence=0.1))
    p2 = v.find_path("BR-X-2024")
    assert QUARANTINE_DIR in str(p2)
    # Old file is gone — no duplicate.
    assert not p1.exists()


# ---------- Wikilinks ----------------------------------------------------


def test_wikilink_and_parse_roundtrip():
    s = wikilink("BR-LEI14478-2022")
    assert s == "[[BR-LEI14478-2022]]"
    assert parse_wikilink(s) == "BR-LEI14478-2022"
    assert parse_wikilink("[[BR-X|alias]]") == "BR-X"
    assert parse_wikilink("not a link") is None
