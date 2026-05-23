"""MOC generator that groups norms by REGULATORY AXIS instead of by country.

A norm can belong to multiple axes (e.g. a BCB resolution may be both AML and
Framework). We tag with a primary axis using keyword + regulator heuristics
applied to the title/title_original.

Run via:
    python -m src.moc_axis
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from .vault import MOC_DIR, Vault, wikilink

# Axes (display order matters — first matching wins)
AXES = [
    ("AML",        "AML / CFT / Travel Rule",
                   "Anti-money laundering, counter-terrorism financing, KYC, Travel Rule, sanctions."),
    ("TAX",        "Taxation",
                   "Income tax, capital gains, withholding, reporting (DeCripto, CARF, BMF, BOFiP, RFB INs)."),
    ("SECURITIES", "When the token is a security",
                   "Securities law, public offerings, MiFID II, prospectus, market abuse."),
    ("CYBER",      "Digital resilience / Cybersecurity",
                   "DORA, cybersecurity policy, ICT risk, third-party governance."),
    ("CONSUMER",   "Consumer protection / Data",
                   "Consumer codes, GDPR / LGPD / BDSG / CNIL, contractual protections."),
    ("FX",         "FX and payments",
                   "Foreign exchange rules, payment-system arrangements (EMTs, ZAG, CMN, BCB Res 521)."),
    ("CASE_LAW",   "Case law / jurisprudence",
                   "Binding precedents that interpret crypto law."),
    ("INTL_STD",   "International standards",
                   "FATF, BIS / Basel, FSB, IOSCO, OECD CARF, IMF — non-binding global benchmarks."),
    ("FRAMEWORK",  "Crypto-asset framework / VASP licensing",
                   "Core crypto-asset laws, regulator competence, VASP/CASP/PSCA licensing regimes."),
]


# ---------- Classification --------------------------------------------------

_AML_RX = re.compile(
    r"\b(AML|CFT|anti-money laundering|money laundering|financial crime|"
    r"Geldwäsche|blanchiment|lavagem|terror|terrorism|Travel Rule|"
    r"MASAK|GwG|GAFI|FATF|KYC|FIU|Tracfin|COAF|FinCEN|suspicious activity)\b",
    re.I,
)
_TAX_RX = re.compile(
    r"\b(tax|taxation|Steuer|impôt|impots|tributação|tributário|"
    r"capital gains|plus-value|Veräußerungsgeschäft|income tax|"
    r"BMF|DGFiP|BOFiP|RFB|BFH|DeCripto|CARF|reporting framework|"
    r"flat tax|withholding|EStG|KStG|CGI)\b",
    re.I,
)
_SEC_RX = re.compile(
    r"\b(security token|securit|Wertpapier|valor mobiliário|valeur mobilière|"
    r"WpHG|WpIG|WpPG|MiFID|prospectus|prospecto|market abuse|abuso de mercado|"
    r"CVM|SEC\b|AMF |ESMA|SPK|public offering|oferta pública|crowdfunding)\b",
    re.I,
)
_CYBER_RX = re.compile(
    r"\b(DORA|cyber|cibern|cybersécurité|resilience|resiliência|"
    r"operational resilience|ICT risk|risco operacional|"
    r"information security|TIC|security policy)\b",
    re.I,
)
_CONSUMER_RX = re.compile(
    r"\b(consumer|consumidor|consommation|Verbraucher|"
    r"data protection|proteção de dados|protection des données|Datenschutz|"
    r"GDPR|LGPD|BDSG|CNIL|KVKK|civil code|código civil|"
    r"BGB|Bürgerliches Gesetzbuch|Code de la consommation|"
    r"Code monétaire et financier consum)\b",
    re.I,
)
_FX_RX = re.compile(
    r"\b(foreign exchange|câmbio|cambial|Devisen|FX market|"
    r"payment system|sistema de pagamentos|arranjo de pagamento|"
    r"e-money|EMT\b|electronic money|stablecoin and FX|ZAG|"
    r"Zahlungsdienste|capitais internacionais)\b",
    re.I,
)
_INTL_RX = re.compile(r"\b(FATF|GAFI|BIS|Basel|FSB|IOSCO|OECD|IMF|UN |United Nations|FATF/GAFI)\b", re.I)
_FRAMEWORK_RX = re.compile(
    r"\b(virtual asset|crypto-asset|criptoativos?|Kryptowerte?|crypto-actif|"
    r"VASP|CASP|PSAV|PSCA|PSAN|SPSAV|Marco Legal|framework|"
    r"MiCA|FinmadiG|KMAG|Loi PACTE|Lei 14.478|kripto varlık)\b",
    re.I,
)


def classify(note) -> str:
    """Pick a primary axis. Heuristic; first match wins per AXES order."""
    blob = " ".join(filter(None, [note.title or "", note.title_original or "", note.regulator or ""]))
    if note.type == "case_law":
        return "CASE_LAW"
    if note.country == "INTL" and _INTL_RX.search(blob):
        return "INTL_STD"
    if _AML_RX.search(blob):
        return "AML"
    if _TAX_RX.search(blob):
        return "TAX"
    if _SEC_RX.search(blob):
        return "SECURITIES"
    if _CYBER_RX.search(blob):
        return "CYBER"
    if _CONSUMER_RX.search(blob):
        return "CONSUMER"
    if _FX_RX.search(blob):
        return "FX"
    if note.country == "INTL":
        return "INTL_STD"
    return "FRAMEWORK"


# ---------- MOC files ------------------------------------------------------


def write_axis_mocs(vault: Vault) -> list[Path]:
    """Write one MOC file per axis. Returns list of written paths."""
    by_axis: dict[str, list] = defaultdict(list)
    for n in vault.iter_notes():
        if n.status == "quarantine":
            continue
        by_axis[classify(n)].append(n)

    written = []
    for axis_id, axis_label, axis_desc in AXES:
        notes = by_axis.get(axis_id, [])
        if not notes:
            continue
        notes.sort(key=lambda n: (n.country, (n.date or "0000"), n.id))

        lines: list[str] = []
        lines.append(f"# Axis — {axis_label}")
        lines.append("")
        lines.append(f"*{axis_desc}*")
        lines.append("")
        lines.append(f"**Total nodes:** {len(notes)}")
        lines.append("")

        # Group by country within axis
        by_country: dict[str, list] = defaultdict(list)
        for n in notes:
            by_country[n.country].append(n)

        for country in sorted(by_country.keys()):
            country_notes = by_country[country]
            lines.append(f"## {country}  ({len(country_notes)})")
            lines.append("")
            for n in country_notes:
                date = f" — {n.date}" if n.date else ""
                reg = f" · *{n.regulator}*" if n.regulator else ""
                t = (n.title or "")[:80]
                lines.append(f"- {wikilink(n.id)} — {t}{date}{reg}")
            lines.append("")

        target = vault.root / MOC_DIR / f"AXIS-{axis_id}.md"
        target.write_text("\n".join(lines), encoding="utf-8")
        written.append(target)

    # Also write an axis index
    index_lines = [
        "# Axes — Regulatory dimensions",
        "",
        "Cross-cuts the vault by REGULATORY AXIS instead of by country.",
        "Useful when asking: \"what does jurisdiction X say about AML?\"",
        "",
    ]
    for axis_id, axis_label, axis_desc in AXES:
        notes = by_axis.get(axis_id, [])
        if not notes:
            continue
        index_lines.append(
            f"- [[{MOC_DIR}/AXIS-{axis_id}|{axis_label}]] — {len(notes)} nodes · *{axis_desc}*"
        )
    target = vault.root / MOC_DIR / "AXES.md"
    target.write_text("\n".join(index_lines), encoding="utf-8")
    written.append(target)
    return written


def main() -> int:
    vault = Vault("./vault")
    paths = write_axis_mocs(vault)
    print(f"Wrote {len(paths)} axis MOC files:")
    for p in paths:
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
