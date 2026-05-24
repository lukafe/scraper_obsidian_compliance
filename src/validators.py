"""Phase 3 — deterministic post-LLM validators.

Each validator inspects an evidence quote (produced in Phase 1) and decides
whether it actually supports the claim. They are intentionally simple and
multilingual: legal text in different jurisdictions uses different but
overlapping vocabularies of obligation.

A validator returns True if the quote SUPPORTS the call; False otherwise.
The caller (gap_analyzer._enforce_evidence) demotes the field to None when
support is missing — keeping the audit trail honest.

The validators run AFTER Phase 1's verbatim check, so the quote we look at
here is guaranteed to be in the body. Their job is the semantic layer.
"""

from __future__ import annotations

import re
from typing import Optional


# --- Imperative-verb vocabulary across the languages we scrape ----------
#
# Sources: MiCA (English/French/German), Brazilian Resolução BCB,
# Singapore Payment Services Act, Spanish CNMV circulars, German BaFin
# guidance, UAE SCA regulations, Turkish CMB notices.

_IMPERATIVE_PATTERNS = [
    r"\bshall\b",
    r"\bmust\b",
    r"\bis\s+required\s+to\b",
    r"\bare\s+required\s+to\b",
    r"\bhas\s+to\b",
    r"\bhave\s+to\b",
    r"\brequired\b",
    r"\boblig",            # obliged / obligation / obligatoire / obligatorio
    r"\bmandator",
    # Portuguese / Spanish
    r"\bdever?á\b",
    r"\bdever?ão\b",
    r"\bdeve\b",
    r"\bdebe\b",
    r"\bdeben\b",
    r"\bobrigad",
    r"\bobligator",
    r"\bexige",            # exige / exigirá
    # French
    r"\bdoit\b",
    r"\bdoivent\b",
    r"\bsont\s+tenus\b",
    # German
    r"\bmuss\b",
    r"\bmüssen\b",
    r"\bist\s+verpflichtet\b",
    r"\bsind\s+verpflichtet\b",
    # Italian
    r"\bdeve\b",  # already covered, kept here for clarity
    r"\bè\s+tenut",
]

_IMPERATIVE_RE = re.compile("|".join(_IMPERATIVE_PATTERNS), re.IGNORECASE)


def supports_obligation(evidence: Optional[str]) -> bool:
    """A boolean `exige_*` claim is credible only if the quote contains at
    least one imperative-verb form. Otherwise we are likely looking at a
    recital, an explanatory clause, or descriptive prose.
    """
    if not evidence:
        return False
    return bool(_IMPERATIVE_RE.search(evidence))


# --- Temporal anchor near a deadline date -------------------------------

# Anchors that introduce a deadline ("by 2025-12-31", "before X"). They are
# valid evidence only when they appear BEFORE the date — in
# "Resolution 2025-12-31 was reviewed by the board" the trailing "by"
# does not describe a deadline.
_TEMPORAL_LEAD_PATTERNS = [
    r"\bby\b",
    r"\bbefore\b",
    r"\buntil\b",
    r"\bno\s+later\s+than\b",
    r"\bnot\s+later\s+than\b",
    # Portuguese / Spanish
    r"\baté\b",
    r"\bantes\s+de\b",
    # French
    r"\bau\s+plus\s+tard\b",
    r"\bavant\s+le\b",
    # German
    r"\bspätestens\b",
]

# Anchors that mark a deadline regardless of position ("deadline", "sunset",
# "comes into force", "Frist", "vigência").
_TEMPORAL_FREE_PATTERNS = [
    r"\bdeadline\b",
    r"\bexpire",
    r"\beffective\b",
    r"\benters?\s+into\s+force\b",
    r"\bcomes?\s+into\s+force\b",
    r"\bin\s+force\b",
    r"\btransition",
    r"\bsunset\b",
    # Portuguese / Spanish
    r"\bprazo\b",
    r"\bvigê?ncia\b",
    r"\ben\s+vigor\b",
    r"\bentra\s+em\s+vigor\b",
    r"\bentra\s+en\s+vigor\b",
    # French
    r"\bdélai\b",
    r"\ben\s+vigueur\b",
    # German
    r"\bfrist\b",
    r"\binkrafttreten\b",
    r"\btritt\s+in\s+kraft\b",
]

_TEMPORAL_LEAD_RE = re.compile("|".join(_TEMPORAL_LEAD_PATTERNS), re.IGNORECASE)
_TEMPORAL_FREE_RE = re.compile("|".join(_TEMPORAL_FREE_PATTERNS), re.IGNORECASE)


_DEADLINE_PROXIMITY_CHARS = 80


def supports_deadline(date_iso: Optional[str], evidence: Optional[str]) -> bool:
    """A `deadline_principal` ISO date is credible only if (a) the date or
    its year appears in the quote and (b) a temporal-anchor keyword sits
    within ~80 characters of the date. Co-presence alone is not enough:
    "Resolution 2025-12-31 was reviewed by the board" mentions both a date
    and the word "by" but does NOT describe a deadline.
    """
    if not date_iso or not evidence:
        return False

    pos = evidence.find(date_iso)
    if pos < 0:
        year = date_iso[:4]
        pos = evidence.find(year)
        if pos < 0:
            return False
        anchor_len = len(year)
    else:
        anchor_len = len(date_iso)

    # "lead" anchors must appear in the LEFT window (before the date).
    left_start = max(0, pos - _DEADLINE_PROXIMITY_CHARS)
    left_window = evidence[left_start:pos]
    if _TEMPORAL_LEAD_RE.search(left_window):
        return True

    # "free" anchors can appear on either side, within the proximity window.
    window_start = max(0, pos - _DEADLINE_PROXIMITY_CHARS)
    window_end = pos + anchor_len + _DEADLINE_PROXIMITY_CHARS
    window = evidence[window_start:window_end]
    return bool(_TEMPORAL_FREE_RE.search(window))


# --- Regime-keyword validator -------------------------------------------

_REGIME_KEYWORDS = {
    "licenciamento": [
        r"\blicen[cs]",      # license / licence / licença / licencia
        r"\bauthoris",       # authorise / authorisation
        r"\bauthori[zs]ation\b",
        r"\bauthorized\b",
        r"\bautoriza",       # autorização / autorización / autorisation
        r"\bgenehmig",       # Genehmigung (DE)
        r"\bermächtigung\b",
        r"\bapproval\b",
        r"\bzulass",          # Zulassung (DE)
    ],
    "registro": [
        # `\bregist` covers register, registered, registration, registry,
        # registrar, registro (PT/ES). Plain `register` would miss
        # "registration" because the shared prefix stops at `regist`.
        r"\bregist",
        r"\brécord\b",
        r"\binscri",          # inscription / inscripción
        r"\beintragung\b",
        r"\benrol",
    ],
    "proibicao": [
        r"\bprohibit",
        r"\bban\b",
        r"\bbanned\b",
        r"\bverbot",
        r"\binterdi",         # interdire / interdit
        r"\bproibi",
        r"\bprohíbe\b",
    ],
    "em_consulta": [
        r"\bconsultation\b",
        r"\bconsulta\s+pública\b",
        r"\bdraft\b",
        r"\bentwurf\b",
        r"\bproject\b",
    ],
    "sem_regra": [
        r"\bsilent\b",
        r"\bnot\s+regulated\b",
        r"\bnão\s+regula",
        r"\bno\s+regulation\b",
        r"\bunregulated\b",
    ],
}

_REGIME_RES = {
    regime: re.compile("|".join(patterns), re.IGNORECASE)
    for regime, patterns in _REGIME_KEYWORDS.items()
}


def supports_regime(regime: Optional[str], evidence: Optional[str]) -> bool:
    """A `regime` enum is credible only if its evidence quote actually
    contains a keyword consistent with that regime. e.g. saying the regime
    is `licenciamento` requires the quote to mention licence / authorisation
    / Genehmigung / autorización or similar.
    """
    if not regime or not evidence:
        return False
    pattern = _REGIME_RES.get(regime)
    if pattern is None:
        return True  # unknown / desconhecido — nothing to check
    return bool(pattern.search(evidence))


# --- Keyword scan with word boundaries (replaces naïve substring) -------

_SHORT_TOKEN_WHITELIST = {
    "aml", "cft", "kyc", "kyt", "ico", "dao",  # well-known crypto/regulatory acronyms
}


def keyword_hits(text: str, keywords: list[str]) -> list[str]:
    """Return the keywords that match within `text` using word boundaries.

    - Multi-word keywords ("travel rule") are matched verbatim, case-insensitive.
    - Short tokens (< 4 chars) are accepted only if whitelisted (the legal
      vocabulary uses a handful of short acronyms like AML, KYT, KYC).
    - All other matches require a regex word boundary so "aml" does not
      match inside "amal" or "examined".
    """
    if not text:
        return []
    haystack = text.lower()
    hits = []
    for kw in keywords:
        kw_l = kw.lower().strip()
        if not kw_l:
            continue
        if " " in kw_l or "-" in kw_l:
            # Phrase — case-insensitive substring is fine.
            if kw_l in haystack:
                hits.append(kw)
            continue
        if len(kw_l) < 4 and kw_l not in _SHORT_TOKEN_WHITELIST:
            # Skip risky short tokens unless explicitly whitelisted.
            continue
        if re.search(rf"\b{re.escape(kw_l)}\b", haystack):
            hits.append(kw)
    return hits
