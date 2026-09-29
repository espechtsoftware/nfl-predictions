"""Gate 4 of the ownership term (reviewer 16c293b7 §5): Saturday's lag-model ownership file must look like a live week's.

The 36 panel files sum to 297-621 predicted ownership points and top out at 11-26%; a file rebuilt for a week that is no
longer current finds no `player_week_inference` rows and collapses (106-223). Below --min-sum the term must not be armed.

  python scripts/check_ownership_lag.py ~/week4-sunday/ownership_lag.csv [--min-sum 280]

Exit 0 and a one-line summary when it passes; exit 2 with the reason when it does not.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def check(path: Path, min_sum: float = 280.0, min_rows: int = 100) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"{path} does not exist (build it Saturday: ownership_sets.py sets --lag-features)"
    try:
        d = pd.read_csv(path)
    except (OSError, ValueError) as exc:
        return False, f"{path} is unreadable ({exc})"
    if "pred_own" not in d.columns:
        return False, f"{path} has no pred_own column"
    v = pd.to_numeric(d.pred_own, errors="coerce")
    if len(d) < min_rows:
        return False, f"{path} holds {len(d)} rows (< {min_rows})"
    if not np.all(np.isfinite(v)):
        return False, f"{path} holds {int((~np.isfinite(v)).sum())} pred_own values that are not numbers"
    if float(v.max()) <= 1.0:
        return False, f"{path} tops out at {float(v.max()):.3f}: fractions, not percentages"
    total = float(v.clip(lower=0).sum())
    if total < min_sum:
        return False, (f"{path} pred_own sums to {total:.0f} (< {min_sum:.0f}): a collapsed file (a rebuilt past week?); "
                       "do not arm the ownership term (UNION_MAIN_OWN_TILT=0)")
    name = "display_name" if "display_name" in d.columns else ("name" if "name" in d.columns else None)
    top = d.assign(v=v).nlargest(3, "v")
    tops = ", ".join(f"{r[name] if name else '?'} {r.v:.1f}%" for _, r in top.iterrows())
    return True, f"{path}: {len(d)} rows, pred_own sum {total:.0f} (>= {min_sum:.0f}), max {float(v.max()):.1f}% ({tops})"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path)
    ap.add_argument("--min-sum", type=float, default=280.0)
    ap.add_argument("--min-rows", type=int, default=100)
    a = ap.parse_args(argv)
    ok, msg = check(a.path, a.min_sum, a.min_rows)
    print(("OWNERSHIP LAG OK: " if ok else "OWNERSHIP LAG REFUSED: ") + msg, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
