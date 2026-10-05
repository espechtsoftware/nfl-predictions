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
# market_movement_eval (Addendum 96) is NOT here: its panel 20260805-hf5 predates the 08-08 salary spine and holds 0
# non-ACT rows of 13,968 (protocol amendment 2), so it is out of class and has no correction leg.
REL_TOL = 1e-4
_STATS = ("aggregate.control_", "aggregate.treatment_", "aggregate.rows")
# The reproduction decision reads ONLY these fields (reviewer 10-05): the disposition, the gate booleans and the gate's
# numeric statistics. Everything else is printed as context (volatile identity, timing, audit counts).
WHITELIST = {
    "defense-proe": ("disposition", "gate.", *_STATS),
    "qb-shell": ("disposition", "gate.", *_STATS),
    "market-tail": ("disposition", "gate.", "heldout_overall.control_", "heldout_overall.treatment_",
                    "heldout_overall.rows", "heldout_rows", "training_rows"),
    "ngs-receiver": ("disposition", "gate.", *_STATS),
    "pass-participation": ("disposition", "gate.", *_STATS),
}
RULE = "O-32 game-day rosters_weekly status ACT"


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
    # LEG IDENTITY (reviewer 10-05): a mis-passed flag must never read as "no effect"
    ga = cor.get("game_day_active") or {}
    if "game_day_active" in unc or ga.get("rule") != RULE or not int(ga.get("rows_kept", 0)) > 0:
        print("LEG IDENTITY FAILED: the corrected leg must carry game_day_active (rule, rows_kept > 0) and the "
              "uncorrected leg must not. Nothing is concluded; re-run the legs.")
        return 4
    keep = ("disposition", "gate", "aggregate", "heldout_overall", "heldout_rows", "training_rows",
            "game_day_active", "source_audit")
    fo, fu, fc = ({k: v for k, v in flat({s: r.get(s) for s in keep}).items()} for r in (orig, unc, cor))
    decide = lambda k: k.startswith(WHITELIST[a.study])                                    # noqa: E731
    keys = sorted(set(fo) | set(fu) | set(fc), key=lambda k: (not decide(k), not k.startswith(("disposition", "gate")), k))
    print(f"O-32 {a.study}: original (Cloud) | local uncorrected | local corrected   (* = in the reproduction decision)")
    for k in keys:
        print(f"{'*' if decide(k) else ' '} {k:55s} {str(fo.get(k, '-'))[:22]:>22} {str(fu.get(k, '-'))[:22]:>22} "
              f"{str(fc.get(k, '-'))[:22]:>22}")
    wl = [k for k in fo if decide(k)]
    if "disposition" not in wl:
        raise SystemExit("the original report has no disposition: the whitelist is wrong for this study")
    bad = [k for k in wl if k in fu and not close(fo[k], fu[k])] + [k for k in wl if k not in fu]
    print(f"\nREPRODUCTION (uncorrected vs original, rel tol {REL_TOL}): "
          + ("REPRODUCED" if not bad else f"NOT REPRODUCED on {len(bad)} field(s): {bad[:8]}"))
    if bad:
        print("Per amendment 1, this study's correction STOPS: report 'environment changed since the verdict'.")
        return 3
    print(f"CORRECTION: disposition {fu.get('disposition')} -> {fc.get('disposition')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
