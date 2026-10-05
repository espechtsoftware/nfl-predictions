"""O-32 correction: the three columns (original Cloud report | local uncorrected | local corrected) for one study,
and the reproduction gate of protocol amendment 1 (the uncorrected leg must reproduce the original).

    python scripts/o32_compare.py defense-proe [--runs-root DIR]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ORIGINAL = {
    "defense-proe": "reports/fantasy-points-defense-proe-runs/20260811-fp-defense-proe-l4-v1/report.json",
    "qb-shell": "reports/fantasy-points-qb-shell-runs/20260813-fp-qb-shell-l4-v1/report.json",
    "market-tail": "reports/market-tail-runs/20260810-market-tail-v1/report.json",
    "ngs-receiver": "reports/ngs-receiver-runs/20260810-ngs-receiver-v1/report.json",
    "pass-participation": "reports/pass-participation-runs/20260810-pass-participation-v1/report.json",
}
REL_TOL = 1e-4


def leg_json(path: Path) -> dict:
    for line in path.read_text().splitlines():
        if "_JSON=" in line:
            return json.loads(line.split("_JSON=", 1)[1])
    raise SystemExit(f"no *_JSON= line in {path}")


def flat(d, prefix=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(flat(v, f"{prefix}{k}."))
    elif isinstance(d, (int, float, bool, str)) and not isinstance(d, type(None)):
        out[prefix[:-1]] = d
    return out


def close(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool) or isinstance(a, str) or isinstance(b, str):
        return a == b
    return math.isclose(float(a), float(b), rel_tol=REL_TOL, abs_tol=1e-9)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("study", choices=sorted(ORIGINAL))
    ap.add_argument("--runs-root", default=str(Path.home() / "projects/.nfl-predictions-worktrees/o32-runs"))
    a = ap.parse_args(argv)
    root = Path(a.runs_root); out = root / "reports" / "o32-correction-runs" / a.study
    orig = json.loads((root / ORIGINAL[a.study]).read_text())
    unc, cor = leg_json(out / "uncorrected.txt"), leg_json(out / "corrected.txt")
    keep = ("disposition", "gate", "aggregate", "game_day_active", "source_audit")
    fo, fu, fc = ({k: v for k, v in flat({s: r.get(s) for s in keep}).items()} for r in (orig, unc, cor))
    keys = sorted(set(fo) | set(fu) | set(fc), key=lambda k: (not k.startswith(("disposition", "gate")), k))
    print(f"O-32 {a.study}: original (Cloud) | local uncorrected | local corrected")
    for k in keys:
        print(f"  {k:55s} {str(fo.get(k, '-'))[:22]:>22} {str(fu.get(k, '-'))[:22]:>22} {str(fc.get(k, '-'))[:22]:>22}")
    bad = [k for k in fo if k in fu and not close(fo[k], fu[k])] + [k for k in fo if k not in fu]
    print(f"\nREPRODUCTION (uncorrected vs original, rel tol {REL_TOL}): "
          + ("REPRODUCED" if not bad else f"NOT REPRODUCED on {len(bad)} field(s): {bad[:8]}"))
    if bad:
        print("Per amendment 1, this study's correction STOPS: report 'environment changed since the verdict'.")
        return 3
    print(f"CORRECTION: disposition {fu.get('disposition')} -> {fc.get('disposition')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
