#!/usr/bin/env python3
"""The week's TOP-RECEIVER term-block file (the outside reviewer, 10-08; the operator: "Is there a test we can do
immediately to try to fix this for this week?", after Week 4's winning lineups needed CeeDee Lamb and Nico Collins --
expensive receivers our FP-value optimizer never paid for). The union's --term-block-* vehicle builds N rows on
projection + min(tilt x pred_own, cap); with pred_own = bonus / 0.20, tilt 0.20 and cap = POINTS, the block adds exactly
POINTS projected points to each team's TOP RECEIVER -- the team's highest-salaried WR on the slate (ties: the higher frame
mean_projection, then the id) -- and nothing to anyone else.

    bonus = POINTS if the player is his team's highest-salaried WR in the frame                          else 0
    --with-cheap adds the cheap rule too: every non-DST player under $4,000 also gets POINTS (one combined file, one cap).

Output in the cheap / TE writers' format: dk_player_id, id, display_name, pos, team, opp, pred_own, bonus_points; every
skill player of the frame once, the DST omitted. Refuses (exit 3) a frame without the needed columns, a missing or
duplicated dk_player_id, non-positive POINTS, no player with a bonus, or an existing --out.

--base <cheap file> (production's review 10-08, REQUIRED for the Week-5 combined file): the combined file is the LIVE
trial's own cheap file (cheap2-w5.csv, written by cheap_block_file.py --group from the group's newest DK pull, so it keeps
the late-week cheap players a frame-based rebuild would drop) with ONLY the frame-derived top receivers flagged: every
base line is copied byte for byte except those WRs' rows, whose pred_own / bonus_points take the base's own bonus
strings. It refuses a base whose bonuses are not all 0 or POINTS, a top WR whose dk_player_id the base lacks, and
--base together with --with-cheap. The top-WR set stays frame-based: the frame excludes OUT players, so a ruled-out WR1
does not take his team's bonus.

    python scripts/top_wr_block_file.py --season 2026 --week 5 --frame <T-70 or A3 frame.parquet> --points 2.0 --out <path>
    python scripts/top_wr_block_file.py --season 2026 --week 5 --frame <A3 frame.parquet> --points 2.0 \\
        --base <cheap2-w5.csv> --out <cheaptopwr2-w5.csv>
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

TILT = 0.20
CHEAP_MAX_SALARY = 4000
SKILL = ("QB", "RB", "WR", "TE")
COLUMNS = ["dk_player_id", "id", "display_name", "pos", "team", "opp", "pred_own", "bonus_points"]


def top_receivers(fr: pd.DataFrame) -> set[str]:
    """Each team's highest-salaried WR (ties: higher mean_projection, then id): their frame ids."""
    w = fr[fr["pos"].astype(str) == "WR"].copy()
    w["sal"] = pd.to_numeric(w["salary"], errors="coerce")
    w["proj"] = pd.to_numeric(w.get("mean_projection", pd.Series(0.0, index=w.index)), errors="coerce").fillna(0.0)
    w = w[w.sal.notna()].sort_values(["team", "sal", "proj", "id"], ascending=[True, False, False, True])
    return set(w.groupby("team").head(1)["id"].astype(str))


def build(frame: pd.DataFrame, points: float, with_cheap: bool = False) -> pd.DataFrame:
    """The block file's rows; raises ValueError rather than write a file the union would misread."""
    if not points > 0:
        raise ValueError(f"points must be positive (got {points})")
    for c in ("dk_player_id", "id", "display_name", "pos", "team", "salary"):
        if c not in frame.columns:
            raise ValueError(f"the frame has no {c} column")
    fr = frame[frame["pos"].astype(str).isin(SKILL)].copy()
    if fr.empty:
        raise ValueError("the frame holds no skill players")
    ids = pd.to_numeric(fr["dk_player_id"], errors="coerce")
    if ids.isna().any():
        raise ValueError(f"{int(ids.isna().sum())} skill players have no dk_player_id")
    if ids.duplicated().any():
        raise ValueError(f"{int(ids.duplicated().sum())} duplicated dk_player_id values")
    flag = fr["id"].astype(str).isin(top_receivers(fr))
    if with_cheap:
        sal = pd.to_numeric(fr["salary"], errors="coerce")
        flag |= sal.notna() & (sal < CHEAP_MAX_SALARY)
    bonus = np.where(flag, float(points), 0.0)
    if not (bonus > 0).any():
        raise ValueError("no player carries a bonus (own_bonus would refuse the file as fractions)")
    out = pd.DataFrame({"dk_player_id": ids.astype("int64"), "id": fr["id"].astype(str),
                        "display_name": fr["display_name"].astype(str), "pos": fr["pos"].astype(str),
                        "team": fr["team"].astype(str), "opp": fr.get("opp", pd.Series("", index=fr.index)).astype(str),
                        "pred_own": np.round(bonus / TILT, 4), "bonus_points": bonus})
    return out[COLUMNS].reset_index(drop=True)


def on_base(base_text: str, frame: pd.DataFrame, points: float) -> tuple[str, list[str]]:
    """The base file's text with ONLY the frame's top receivers flagged (byte-identical otherwise). Returns the new text and
    the flagged dk_player_ids. Raises ValueError rather than write a file the union would misread."""
    lines = base_text.splitlines(keepends=True)
    if not lines:
        raise ValueError("the base file is empty")
    rows = list(csv.reader(lines))
    head = rows[0]
    if head != COLUMNS:
        raise ValueError(f"the base's columns are {head}, not {COLUMNS}")
    i_dk, i_po, i_bp = head.index("dk_player_id"), head.index("pred_own"), head.index("bonus_points")
    vals = sorted({float(r[i_bp]) for r in rows[1:]})
    if not set(vals) <= {0.0, float(points)}:
        raise ValueError(f"the base's bonuses {vals} are not all 0 or POINTS {points:g}")
    bonus_rows = [r for r in rows[1:] if float(r[i_bp]) == float(points)]
    po_s, bp_s = (bonus_rows[0][i_po], bonus_rows[0][i_bp]) if bonus_rows else (str(round(points / TILT, 4)), str(float(points)))
    fr = frame[frame["pos"].astype(str).isin(SKILL)]
    top = top_receivers(fr)
    dk_of = {str(i): str(k).removesuffix(".0") for i, k in zip(fr["id"].astype(str), fr["dk_player_id"].astype(str))}
    want = {dk_of[i] for i in top}
    have = {str(r[i_dk]).removesuffix(".0") for r in rows[1:]}
    missing = sorted(want - have)
    if missing:
        raise ValueError(f"{len(missing)} top receivers are not in the base file (dk_player_id {missing[:5]})")
    out = [lines[0]]
    for line, r in zip(lines[1:], rows[1:]):
        if str(r[i_dk]).removesuffix(".0") in want:
            r = list(r); r[i_po], r[i_bp] = po_s, bp_s
            term = line[len(line.rstrip("\r\n")):]                     # keep the line's own ending (none on a last line)
            buf = io.StringIO(); csv.writer(buf, lineterminator="\n").writerow(r)
            out.append(buf.getvalue().rstrip("\n") + term)
        else:
            out.append(line)
    return "".join(out), sorted(want)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--frame", type=Path, required=True); ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--points", type=float, default=2.0, help="projected points added per qualifying player (the cap)")
    ap.add_argument("--with-cheap", action="store_true", help="also give every non-DST player under $4,000 the bonus (one combined file)")
    ap.add_argument("--base", type=Path, default=None, help="the live cheap file to flag the top receivers on (byte-identical otherwise)")
    a = ap.parse_args(argv)
    if a.out.exists():
        print(f"TOP-WR BLOCK FILE REFUSED: {a.out} exists (create-once; remove it deliberately to rewrite)", file=sys.stderr)
        return 3
    if a.base is not None:
        if a.with_cheap:
            print("TOP-WR BLOCK FILE REFUSED: --base and --with-cheap together (the base IS the cheap part)", file=sys.stderr)
            return 3
        try:
            text, flagged = on_base(a.base.read_text(), pd.read_parquet(a.frame), a.points)
        except (OSError, ValueError) as e:
            print(f"TOP-WR BLOCK FILE REFUSED: {e}", file=sys.stderr)
            return 3
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text)
        print(f"top-WR block file {a.season} W{a.week} ON BASE {a.base} (sha256 {hashlib.sha256(a.base.read_bytes()).hexdigest()[:12]}): "
              f"{len(flagged)} top receivers flagged +{a.points:g}, every other line unchanged (frame sha256 "
              f"{hashlib.sha256(a.frame.read_bytes()).hexdigest()[:8]}) -> {a.out} (sha256 {hashlib.sha256(a.out.read_bytes()).hexdigest()})")
        return 0
    try:
        out = build(pd.read_parquet(a.frame), a.points, a.with_cheap)
    except ValueError as e:
        print(f"TOP-WR BLOCK FILE REFUSED: {e}", file=sys.stderr)
        return 3
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)
    wr = out[(out.pos == "WR") & (out.bonus_points > 0)]
    print(f"top-WR block file {a.season} W{a.week}: {int((out.bonus_points > 0).sum())} of {len(out)} skill players get +{a.points:g} "
          f"({len(wr)} WRs; with cheap: {a.with_cheap}) (frame sha256 {hashlib.sha256(a.frame.read_bytes()).hexdigest()[:8]}) -> {a.out} "
          f"(sha256 {hashlib.sha256(a.out.read_bytes()).hexdigest()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
