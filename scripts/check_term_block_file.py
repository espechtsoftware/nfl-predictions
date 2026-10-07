#!/usr/bin/env python3
"""The arm's term-block file check (the laptop and the reviewer, 10-07). The union builds the block's rows on projection +
min(tilt x pred_own, cap), so a file written for a larger dose than the armed cap is silently clipped: a +4 cheap file
under cap 2.0 would enter as +2, a different rule from the one tested. For a bonus-form file (a bonus_points column: the
matchup and cheap writers, pred_own = bonus / tilt) this refuses (exit 3):
  - a cap outside the union's range (0, 5];
  - a missing or duplicated dk_player_id;
  - a negative or non-numeric bonus, or no player with a bonus;
  - a largest bonus above the cap;
  - a pred_own that is not bonus_points / tilt.
A file without bonus_points (the prior-top form, where the cap clips tilt x pred_own by design) passes with a note.
Prints one summary line for the arming log.
    python scripts/check_term_block_file.py <file> --cap 2.0 [--tilt 0.20]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

CAP_MAX = 5.0          # the union's --term-block-cap-points range is (0, 5]


def check(df: pd.DataFrame, cap: float, tilt: float, require_bonus: bool = False) -> str:
    if not 0 < cap <= CAP_MAX:
        raise ValueError(f"the cap {cap:g} is outside the union's range (0, {CAP_MAX:g}]")
    for c in ("dk_player_id", "pred_own"):
        if c not in df.columns:
            raise ValueError(f"no {c} column")
    ids = pd.to_numeric(df["dk_player_id"], errors="coerce")
    if ids.isna().any() or ids.duplicated().any():
        raise ValueError("a missing or duplicated dk_player_id")
    if "bonus_points" not in df.columns:
        if require_bonus:                    # the outside review 10-07, M2: the paper-only prior-top file must never be armed
            raise ValueError("no bonus_points column (the prior-top, paper-only form): an ARMED block needs the bonus form")
        return f"no bonus_points column (the prior-top form): {len(df)} players; the cap {cap:g} clips tilt x pred_own by design"
    b = pd.to_numeric(df["bonus_points"], errors="coerce"); p = pd.to_numeric(df["pred_own"], errors="coerce")
    if b.isna().any() or p.isna().any():
        raise ValueError("a non-numeric bonus_points or pred_own")
    if (b < 0).any():
        raise ValueError("a negative bonus")
    if not (b > 0).any():
        raise ValueError("no player carries a bonus")
    if b.max() > cap + 1e-9:
        raise ValueError(f"the largest bonus {b.max():g} exceeds the cap {cap:g}: the union would clip it (arm the cap that equals the dose)")
    if ((tilt * p - b).abs() > 1e-3).any():
        raise ValueError(f"pred_own is not bonus_points / {tilt:g} on {int(((tilt * p - b).abs() > 1e-3).sum())} players")
    return f"{int((b > 0).sum())} of {len(df)} players carry a bonus (largest {b.max():g}, cap {cap:g})"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", type=Path); ap.add_argument("--cap", type=float, required=True); ap.add_argument("--tilt", type=float, default=0.20)
    ap.add_argument("--require-bonus", action="store_true", help="refuse the prior-top form (no bonus_points): the arm's live block")
    a = ap.parse_args(argv)
    try:
        msg = check(pd.read_csv(a.file), a.cap, a.tilt, a.require_bonus)
    except (ValueError, OSError, pd.errors.ParserError) as e:
        print(f"TERM BLOCK FILE REFUSED ({a.file.name}): {e}", file=sys.stderr)
        return 3
    print(f"term block file {a.file.name}: {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
