#!/usr/bin/env python3
"""Is this run dir publishable by the after-build watcher? (2026-09-28, laptop finding: the watcher published any chosen-dose
run dir before, and regardless of, the build host's verify_k90 and audit.)

    python scripts/run_dir_publishable.py <run dir> [--union-mode] [--no-audit-gate]

Exit 0 = publish; exit 1 = skip (the reason on stdout; the watcher logs it and leaves the dir eligible). Rules:
  * receipt.json, candidates.parquet and the incumbent sidecar must exist (a build in progress);
  * `audit_passed` must exist in the run dir: the build host writes it only after that dir's own verify_k90 and audit
    pass (`audit_failed` = refused, never publishable); --no-audit-gate is an explicit rehearsal override, logged;
  * with --union-mode (UNION_SATURDAY_RUN set): the receipt must carry config.union, or the dir must carry
    `union_failed` (the build host marks a build whose union was refused, so it is published as the fallback).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def publishable(run: Path, union_mode: bool, audit_gate: bool = True) -> tuple[bool, str]:
    for f in ("receipt.json", "candidates.parquet", "incumbent_player_scores.npy"):
        if not (run / f).is_file():
            return False, f"{f} not written yet"
    if (run / "audit_failed").is_file():
        return False, "audit_failed: the build host refused this run dir"
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
    a = ap.parse_args(argv)
    ok, why = publishable(a.run, a.union_mode, audit_gate=not a.no_audit_gate)
    print(why)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
