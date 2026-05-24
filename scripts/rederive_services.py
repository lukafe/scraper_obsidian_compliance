"""Re-derive `servicos_certik_aplicaveis` across every analyzed norm in the
vault, using the Phase 3 word-boundary keyword scanner.

This is deterministic — no LLM calls, no network. Safe to run repeatedly.

USAGE
-----
    # Dry-run: report what would change, no writes.
    python3 scripts/rederive_services.py --vault vault --dry-run

    # Apply: rewrite each affected note's frontmatter.
    python3 scripts/rederive_services.py --vault vault
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src import business_schema as bs  # noqa: E402
from src.vault import Vault  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vault", default="vault", help="Path to the vault root")
    p.add_argument("--dry-run", action="store_true", help="Don't write changes")
    args = p.parse_args()

    vault = Vault(args.vault)
    scanned = 0
    changed = 0
    examples: list[tuple[str, list[str], list[str]]] = []

    for note in vault.iter_notes():
        if note.status == "quarantine":
            continue
        scanned += 1
        extra = note.extra
        before = list(extra.get("servicos_certik_aplicaveis") or [])
        after = bs.derive_services_from_triggers(extra)
        if before == after:
            continue

        changed += 1
        if len(examples) < 10:
            examples.append((note.id, before, after))
        if not args.dry_run:
            extra["servicos_certik_aplicaveis"] = after
            vault.write(note)

    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(f"{mode}: scanned={scanned} changed={changed}")
    if examples:
        print("\nFirst {} examples:".format(len(examples)))
        for note_id, before, after in examples:
            removed = sorted(set(before) - set(after))
            added = sorted(set(after) - set(before))
            print(f"  {note_id}")
            if removed:
                print(f"    - removed: {', '.join(removed)}")
            if added:
                print(f"    + added:   {', '.join(added)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
