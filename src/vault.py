"""Vault: the Obsidian-on-disk store.

The vault *is* the database. Every norm is a `.md` file whose YAML frontmatter
holds its full state. The graph is the set of wikilinks between notes. There is
no separate index — queries are file-system walks over frontmatter.

Determinism: a norm's `id` is derived from (country, identifier, year). Same
norm rediscovered later -> same `id` -> same file path -> dedup for free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

import frontmatter  # python-frontmatter
from slugify import slugify

# ---------- Constants -----------------------------------------------------

VALID_STATUSES = {
    "discovered",
    "verified",
    "scraped",
    "analyzed",
    "quarantine",
}

VALID_TYPES = {"statute", "regulation", "guidance", "case_law"}
VALID_AUTHORITIES = {"primary", "secondary", "tertiary"}
VALID_DISCOVERED_VIA = {"seed", "citation", "semantic"}

SUPRANATIONAL_COUNTRY = "INTL"
QUARANTINE_DIR = "_quarantine"
MOC_DIR = "_MOC"
META_DIR = "_meta"

# ---------- Note model ----------------------------------------------------


@dataclass
class Note:
    """In-memory representation of one vault note."""

    id: str
    country: str
    jurisdiction: str
    type: str
    title: str
    status: str = "discovered"
    regulator: Optional[str] = None
    source_url: Optional[str] = None
    source_authority: Optional[str] = None  # primary | secondary | tertiary
    confidence: Optional[float] = None
    language: Optional[str] = None
    date: Optional[str] = None  # ISO YYYY-MM-DD as string for YAML stability
    discovered_via: str = "seed"
    cycle: int = 0
    references: list[str] = field(default_factory=list)  # ["[[ID]]", ...]
    ref_types: dict[str, str] = field(default_factory=dict)  # id -> "citation" | "semantic"
    body: str = ""
    extra: dict[str, Any] = field(default_factory=dict)  # arbitrary frontmatter passthrough

    # -- frontmatter (de)serialization ------------------------------------

    def to_frontmatter(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "country": self.country,
            "jurisdiction": self.jurisdiction,
            "type": self.type,
            "title": self.title,
            "status": self.status,
            "discovered_via": self.discovered_via,
            "cycle": self.cycle,
            "references": list(self.references),
            "ref_types": dict(self.ref_types),
        }
        if self.regulator is not None:
            data["regulator"] = self.regulator
        if self.source_url is not None:
            data["source_url"] = self.source_url
        if self.source_authority is not None:
            data["source_authority"] = self.source_authority
        if self.confidence is not None:
            data["confidence"] = round(float(self.confidence), 3)
        if self.language is not None:
            data["language"] = self.language
        if self.date is not None:
            data["date"] = self.date
        data.update(self.extra)
        return data

    @classmethod
    def from_post(cls, post: frontmatter.Post) -> "Note":
        d = dict(post.metadata)
        # Pop typed fields, leave the rest in `extra`.
        def pop(key: str, default: Any = None) -> Any:
            return d.pop(key, default)

        # `date` may come back as datetime.date from YAML — coerce to str.
        raw_date = pop("date")
        if isinstance(raw_date, date):
            date_str = raw_date.isoformat()
        elif raw_date is None:
            date_str = None
        else:
            date_str = str(raw_date)

        return cls(
            id=pop("id"),
            country=pop("country"),
            jurisdiction=pop("jurisdiction", ""),
            type=pop("type"),
            title=pop("title", ""),
            status=pop("status", "discovered"),
            regulator=pop("regulator"),
            source_url=pop("source_url"),
            source_authority=pop("source_authority"),
            confidence=pop("confidence"),
            language=pop("language"),
            date=date_str,
            discovered_via=pop("discovered_via", "seed"),
            cycle=int(pop("cycle", 0) or 0),
            references=list(pop("references", []) or []),
            ref_types=dict(pop("ref_types", {}) or {}),
            body=post.content or "",
            extra=d,
        )


# ---------- ID derivation -------------------------------------------------

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")
_YEAR_RE = re.compile(r"\b(1[7-9]\d{2}|20\d{2}|21\d{2})\b")


# Filler words stripped from the start of titles before slug fallback.
_LEADING_ARTICLES = {
    "the", "a", "an", "el", "la", "le", "les", "der", "die", "das",
    "il", "lo", "os", "as",
}

# Statute-marker words used to recognize "<X> Act/Law/Bill/Code" patterns.
_STATUTE_MARKERS = (
    "Act", "Law", "Bill", "Code", "Regulation", "Order", "Decree",
    "Statute", "Directive", "Rule",
)
_STATUTE_MARKERS_RE = "|".join(_STATUTE_MARKERS)


def _identifier_slug(title: str, regulator: Optional[str]) -> str:
    """Pull a compact identifier-ish slug from a title.

    Heuristic — we want stable, short, recognizable IDs:
    - "Lei nº 14.478, de 21 de dezembro de 2022" -> "LEI14478"
    - "Instrução Normativa BCB nº 701" -> "IN701" (or "BCB701" if regulator-led)
    - "Markets in Crypto-Assets Regulation (MiCA)" -> "MICA"
    - "The CLARITY Act of 2025" -> "CLARITYACT"
    - falls back to a slug of the title if nothing matches
    """
    if not title:
        return "UNKNOWN"

    # 1) Look for ALL-CAPS acronyms in parentheses, e.g. "(MiCA)" or "(MAS)".
    paren = re.findall(r"\(([A-Za-z][A-Za-z0-9\-]{1,15})\)", title)
    for cand in paren:
        s = _NON_ALNUM.sub("", cand).upper()
        if 2 <= len(s) <= 12 and any(c.isalpha() for c in s):
            return s

    # 2) Look for "<word> n[ºo°] <number>" or "<word> N.<number>" patterns.
    m = re.search(
        r"\b([A-Za-zÀ-ÿ]{2,20})\s*(?:n[ºo°.]|N\.|No\.?)\s*([0-9][0-9\.,/-]*)",
        title,
    )
    if m:
        word = _NON_ALNUM.sub("", m.group(1)).upper()
        num = _NON_ALNUM.sub("", m.group(2))
        if word and num:
            return f"{word}{num}"[:24]

    # 3) Look for "<WORD> <number>" (BCB 701, FATF R16, etc.).
    m = re.search(r"\b([A-Z]{2,8})\s*([0-9][0-9\.,/-]{0,10})", title)
    if m:
        word = m.group(1).upper()
        num = _NON_ALNUM.sub("", m.group(2))
        if word and num:
            return f"{word}{num}"

    # 4) "<CAPS_WORD> Act/Law/Bill/..." — common in English statutes.
    m = re.search(
        rf"\b([A-Z]{{2,15}})\s+(?:{_STATUTE_MARKERS_RE})\b",
        title,
    )
    if m:
        return f"{m.group(1).upper()}ACT"[:24]

    # 5) Fall back to slug + regulator prefix. Strip leading articles first.
    cleaned = " ".join(
        w for w in title.split()
        if w.strip(".,").lower() not in _LEADING_ARTICLES
    )
    slug = slugify(cleaned, lowercase=False, separator="")[:24].upper()
    if regulator:
        reg = _NON_ALNUM.sub("", regulator).upper()[:8]
        return f"{reg}{slug}"[:24] or "UNKNOWN"
    return slug or "UNKNOWN"


def _extract_year(*candidates: Optional[str]) -> Optional[str]:
    for c in candidates:
        if not c:
            continue
        m = _YEAR_RE.search(str(c))
        if m:
            return m.group(1)
    return None


def make_id(
    *,
    country: str,
    title: str,
    regulator: Optional[str] = None,
    date_str: Optional[str] = None,
) -> str:
    """Build a deterministic id: `{COUNTRY}-{SLUG}-{YEAR}`.

    Same logical norm -> same id, even rediscovered through a different route.
    """
    country = (country or "").strip().upper() or "ZZ"
    slug = _identifier_slug(title, regulator)
    year = _extract_year(date_str, title)
    if year:
        return f"{country}-{slug}-{year}"
    return f"{country}-{slug}"


# ---------- Vault store ---------------------------------------------------


class Vault:
    """File-system view of the vault."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / QUARANTINE_DIR).mkdir(exist_ok=True)
        (self.root / MOC_DIR).mkdir(exist_ok=True)
        (self.root / META_DIR).mkdir(exist_ok=True)

    # -- path helpers -----------------------------------------------------

    def _country_dir(self, country: str) -> Path:
        d = self.root / country.upper()
        d.mkdir(parents=True, exist_ok=True)
        return d

    def path_for(self, note: Note) -> Path:
        if note.status == "quarantine":
            return self.root / QUARANTINE_DIR / f"{note.id}.md"
        return self._country_dir(note.country) / f"{note.id}.md"

    def find_path(self, note_id: str) -> Optional[Path]:
        """Locate an existing note by id, regardless of which folder it lives in."""
        # Fast path: probe the obvious places.
        if "-" in note_id:
            country = note_id.split("-", 1)[0]
            candidates = [
                self.root / country / f"{note_id}.md",
                self.root / QUARANTINE_DIR / f"{note_id}.md",
            ]
            for p in candidates:
                if p.exists():
                    return p
        # Fallback: search the whole vault.
        for p in self.root.rglob(f"{note_id}.md"):
            return p
        return None

    # -- CRUD -------------------------------------------------------------

    def exists(self, note_id: str) -> bool:
        return self.find_path(note_id) is not None

    def read(self, note_id: str) -> Optional[Note]:
        p = self.find_path(note_id)
        if p is None:
            return None
        post = frontmatter.load(p)
        return Note.from_post(post)

    def write(self, note: Note) -> Path:
        """Write (create or overwrite) a note, moving it between folders on
        status changes (e.g. quarantine <-> country dir)."""
        target = self.path_for(note)
        # If the note already lives elsewhere (status changed), remove the old file.
        old = self.find_path(note.id)
        if old is not None and old != target:
            try:
                old.unlink()
            except FileNotFoundError:
                pass
        target.parent.mkdir(parents=True, exist_ok=True)
        post = frontmatter.Post(note.body or "", **note.to_frontmatter())
        target.write_text(frontmatter.dumps(post), encoding="utf-8")
        return target

    def upsert(self, note: Note) -> tuple[Note, bool]:
        """Create or merge into an existing note.

        Returns (final_note, created). When a note already exists, we keep the
        existing body and references and *only* fill in missing scalar fields
        so we never overwrite scraped/analyzed work with a rediscovery."""
        existing = self.read(note.id)
        if existing is None:
            self.write(note)
            return note, True

        # Merge: existing wins on body + references + status if it's further along.
        def prefer_existing(field_name: str) -> None:
            if getattr(existing, field_name) is None and getattr(note, field_name) is not None:
                setattr(existing, field_name, getattr(note, field_name))

        for f in (
            "regulator",
            "source_url",
            "source_authority",
            "confidence",
            "language",
            "date",
            "jurisdiction",
            "title",
        ):
            prefer_existing(f)

        # Status only advances forward; never regress.
        if _status_rank(note.status) > _status_rank(existing.status):
            existing.status = note.status

        # Merge references, dedup, preserve first-seen ref_type.
        for ref in note.references:
            if ref not in existing.references:
                existing.references.append(ref)
        for k, v in note.ref_types.items():
            existing.ref_types.setdefault(k, v)

        self.write(existing)
        return existing, False

    # -- queries (the "work queue") --------------------------------------

    def iter_notes(self) -> Iterator[Note]:
        for p in self.root.rglob("*.md"):
            # Skip MOC / meta / quarantine isn't skipped — it's still a note,
            # callers filter by status.
            if p.parent.name in {MOC_DIR, META_DIR}:
                continue
            try:
                post = frontmatter.load(p)
            except Exception:
                continue
            if "id" not in post.metadata:
                continue
            yield Note.from_post(post)

    def query(
        self,
        *,
        status: Optional[str | Iterable[str]] = None,
        country: Optional[str] = None,
        type: Optional[str] = None,  # noqa: A002 (matches frontmatter key)
        discovered_via: Optional[str] = None,
    ) -> list[Note]:
        if isinstance(status, str):
            status_set = {status}
        elif status is None:
            status_set = None
        else:
            status_set = set(status)

        out: list[Note] = []
        for n in self.iter_notes():
            if status_set is not None and n.status not in status_set:
                continue
            if country is not None and n.country != country.upper():
                continue
            if type is not None and n.type != type:
                continue
            if discovered_via is not None and n.discovered_via != discovered_via:
                continue
            out.append(n)
        return out

    def counts_by_status(self, country: Optional[str] = None) -> dict[str, int]:
        counts: dict[str, int] = {s: 0 for s in VALID_STATUSES}
        for n in self.iter_notes():
            if country is not None and n.country != country.upper():
                continue
            counts[n.status] = counts.get(n.status, 0) + 1
        return counts


# ---------- Helpers -------------------------------------------------------


_STATUS_ORDER = {
    "discovered": 0,
    "verified": 1,
    "scraped": 2,
    "analyzed": 3,
    "quarantine": -1,  # off the main path
}


def _status_rank(status: str) -> int:
    return _STATUS_ORDER.get(status, 0)


def wikilink(note_id: str) -> str:
    return f"[[{note_id}]]"


def parse_wikilink(s: str) -> Optional[str]:
    m = re.match(r"\[\[([^\]\|]+)(?:\|[^\]]*)?\]\]", s.strip())
    return m.group(1).strip() if m else None
