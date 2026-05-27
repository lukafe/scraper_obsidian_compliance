"""Deadline-data audit + cleanup.

The Phase 1 evidence trail requires every structured field to carry a
verbatim quote from the source body. Many deadlines in the vault predate
that requirement and were not re-validated by the Phase 1 + Phase 3
rerun (12 of 23 countries are still waiting on the Gemini daily quota).

This script enforces the same rule retroactively across the entire vault:

  1. Inventory every norm with `deadline_principal` set.
  2. Drop any deadline that lacks a `deadline_principal_evidence` quote
     (the LLM never grounded it in the body).
  3. Drop deadlines where the evidence quote does not contain the date or
     its year (Phase 3 semantic validator applied retroactively).
  4. Wipe `deadline_principal` AND `tipo_deadline` together (the two
     fields describe the same event; orphaning one is incoherent).
  5. Log every demotion for review.

The cleaner is conservative — null is better than an unsupported claim.
A future LLM rerun with the Phase 1 prompt can re-populate any missing
deadline IF the body actually carries one with a temporal anchor.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.vault import Vault  # noqa: E402
from src.validators import supports_deadline  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vault", default="vault")
    p.add_argument(
        "--dry-run", action="store_true",
        help="Report what would change without writing.",
    )
    args = p.parse_args()

    vault = Vault(args.vault)
    scanned = 0
    kept_grounded = 0
    demoted_no_evidence = 0
    demoted_evidence_fail = 0
    demotions: list[tuple[str, str, str, str]] = []

    for note in vault.iter_notes():
        if note.status == "quarantine":
            continue
        extra = note.extra
        dl = extra.get("deadline_principal")
        if not dl:
            continue
        scanned += 1
        ev = extra.get("deadline_principal_evidence")
        reason = None
        if not ev:
            reason = "no_evidence"
            demoted_no_evidence += 1
        elif not supports_deadline(str(dl)[:10], ev):
            reason = "evidence_fails_validator"
            demoted_evidence_fail += 1
        else:
            kept_grounded += 1
            continue
        # Demote: wipe both deadline + tipo_deadline + their evidence.
        demotions.append((note.id, note.country, str(dl)[:10], reason))
        if not args.dry_run:
            extra["deadline_principal"] = None
            extra["deadline_principal_evidence"] = None
            extra["tipo_deadline"] = None
            extra["tipo_deadline_evidence"] = None
            vault.write(note)

    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(f"{mode}: scanned={scanned}")
    print(f"  kept (grounded):           {kept_grounded}")
    print(f"  demoted (no evidence):     {demoted_no_evidence}")
    print(f"  demoted (validator fail):  {demoted_evidence_fail}")
    print()
    print("First 25 demotions:")
    for nid, country, dl, reason in demotions[:25]:
        print(f"  {country}  {dl}  {reason:25s}  {nid}")
    if len(demotions) > 25:
        print(f"  ... and {len(demotions) - 25} more.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
