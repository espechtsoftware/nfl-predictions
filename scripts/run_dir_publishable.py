#!/usr/bin/env python3
"""Is this run dir publishable by the after-build watcher? (2026-09-28, laptop finding: the watcher published any chosen-dose
run dir before, and regardless of, the build host's verify_k90 and audit.)

    python scripts/run_dir_publishable.py <run dir> [--union-mode] [--no-audit-gate]

Exit 0 = publish; exit 1 = skip (the reason on stdout; the watcher logs it and leaves the dir eligible). Rules:
  * receipt.json, candidates.parquet and the incumbent sidecar must exist (a build in progress);
  * `audit_passed` must exist in the run dir: the build host writes it only after that dir's own verify_k90 and audit
    pass (`audit_failed` = refused, never publishable); --no-audit-gate is an explicit rehearsal override, logged;
  * with --union-mode (UNION_SATURDAY_RUN set): the receipt must carry config.union, or the dir must carry
    `union_failed` (the build host marks a build whose union was refused, so it is published as the fallback);
  * --group G: the receipt's draft_group must be G (a smoke on another slate is never published);
  * --built-after ISO: the receipt's built_utc must not be earlier (Wednesday's smoke, a Thursday paper build never are);
  * a `superseded` marker (the build host writes it when a build finishes after the T-70 build's start) is never published;
  * a `term_block_missing` marker (the build host: the decided prior-top term block is not in this union's book) is not
    published unless --accept-term-block-missing (TERM_BLOCK_MISSING_OK=1, the operator's decision to enter without it).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_utc(text: str):
    """A UTC datetime from either the lab's str(datetime) form ("2026-10-03 15:00:00.123+00:00") or ISO with T and an
    optional Z / offset; naive values are taken as UTC. Compare times by content, never by string (the frozen-chain lesson)."""
    from datetime import datetime, timezone
    t = str(text).strip().replace(" ", "T", 1)
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    d = datetime.fromisoformat(t)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def publishable(run: Path, union_mode: bool, audit_gate: bool = True, group: str | None = None,
                built_after: str | None = None, accept_term_block_missing: bool = False) -> tuple[bool, str]:
    for f in ("receipt.json", "candidates.parquet", "incumbent_player_scores.npy"):
        if not (run / f).is_file():
            return False, f"{f} not written yet"
    if (run / "superseded").is_file():
        return False, "superseded: a later build for this week replaces it (the build host marked it)"
    if (run / "audit_failed").is_file():
        return False, "audit_failed: the build host refused this run dir"
    if (run / "term_block_missing").is_file() and not accept_term_block_missing:
        why = (run / "term_block_missing").read_text().strip()
        return False, f"term_block_missing: the decided term block is not in this book ({why}); STOP for the operator (TERM_BLOCK_MISSING_OK=1 enters without it)"
    if group is not None or built_after is not None:
        try:
            rec = json.loads((run / "receipt.json").read_text())
        except (OSError, ValueError) as exc:
            return False, f"unreadable receipt: {exc}"
        if group is not None and str(rec.get("draft_group")) != str(group):
            return False, f"draft group {rec.get('draft_group')} is not this week's {group}"
        if built_after is not None:
            try:
                early = parse_utc(rec.get("built_utc", "")) < parse_utc(built_after)
            except (TypeError, ValueError) as exc:
                return False, f"unparseable built_utc / window start: {exc}"
            if early:
                return False, f"built {rec.get('built_utc')} before this week's window start {built_after} (a smoke or an old build)"
    if audit_gate and not (run / "audit_passed").is_file():
        return False, "no audit_passed marker yet (the build host writes it after verify_k90 and the audit pass)"
    if union_mode:
        try:
            has_union = bool(json.loads((run / "receipt.json").read_text()).get("config", {}).get("union"))
        except (OSError, ValueError) as exc:
            return False, f"unreadable receipt: {exc}"
        if not has_union and not (run / "union_failed").is_file():
            return False, "UNION_SATURDAY_RUN set: waiting for this build's union dir, or a union_failed marker"
    return True, "publishable" + (" (audit gate OFF: rehearsal override)" if not audit_gate else "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run", type=Path); ap.add_argument("--union-mode", action="store_true"); ap.add_argument("--no-audit-gate", action="store_true")
    ap.add_argument("--group", help="this week's draft group; a run dir for another group is never published")
    ap.add_argument("--built-after", help="ISO UTC; a run dir built before this (a smoke, an old build) is never published")
    ap.add_argument("--accept-term-block-missing", action="store_true",
                    help="publish a union marked term_block_missing (the operator's decision; TERM_BLOCK_MISSING_OK=1)")
    a = ap.parse_args(argv)
    ok, why = publishable(a.run, a.union_mode, audit_gate=not a.no_audit_gate, group=a.group, built_after=a.built_after,
                          accept_term_block_missing=a.accept_term_block_missing)
    print(why)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
