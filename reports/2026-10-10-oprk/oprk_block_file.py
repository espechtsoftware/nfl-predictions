#!/usr/bin/env python3
"""The week's PAPER DK-opponent-rank block file (the operator 10-10: a DK-rank test; study 38 amendment 6z6,
MIXT_QA0_OPRKBLOCK8 -- the 8-row paper block in place of the cheap block, 6z4's pattern; the lab reviewer's design). The
union's --term-block-* vehicle builds N rows on projection + min(tilt x pred_own, cap); pred_own = bonus / 0.20 at tilt 0.20 /
cap 2.0 adds the bonus:

    oprk  = DraftKings' OPPONENT RANK vs the player's position (draftStatAttributes id -2, sort_value: 1 = the toughest
            defense, 32 = the easiest) in the LAST capture of nfl_raw.dk_draftable_attributes for --group strictly before
            --as-of (reports/2026-10-10-dk-oprk/capture_dk_attributes.py), joined to the frame by dk_player_id;
    bonus = clip(2 x (oprk - 16) / 16, 0, 2) for QB / RB / WR / TE: 32 -> +2.0, 24 -> +1.0, 16 or tougher -> 0; no rank -> 0.

Output (plain CSV, the format own_bonus reads; no metadata line): dk_player_id, id, display_name, pos, team, opp, pred_own
(= bonus / 0.20), bonus_points, oprk, snapshot_ts; every skill player of the frame once (a bonus of 0 included), the DST
omitted. Refuses (exit 3): an --as-of without a time zone; no capture for --group before --as-of; a capture more than
--max-age-hours (default 3) before --as-of (a missed Sunday capture must not hand Saturday's ranks to the file: Saturday's
14:31 CT capture is about 20 h before a Sunday 10:40 CT --as-of, so a 24 h limit would accept it); a dk_player_id
repeated in the capture or the frame; a frame without skill players; a week where no player carries a bonus.

Two inputs besides BigQuery, for a mechanics smoke (W1-4 ranks were never stored):
    --capture-csv FILE   a capture with columns dk_player_id, oprk, pulled_at (UTC); the same timing checks apply;
    --synthetic          a DETERMINISTIC capture made from the frame itself: each opponent team's rank spreads its sorted
                         position over 1-32 (the same for every player position); snapshot_ts 'SYNTHETIC-mechanics-only';
                         no timing check; a banner. Never for a real week's file.

    python reports/2026-10-10-oprk/oprk_block_file.py --week 5 --group 154468 --frame <the T-70 union frame.parquet> \
        --as-of <UTC, just after Sunday's ~10:35 CT capture> --out <path>/paper-oprk-w05.csv
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SKILL = ("QB", "RB", "WR", "TE")
TILT = 0.20
PIVOT, SPAN, CAP = 16.0, 16.0, 2.0                  # bonus = clip(CAP x (oprk - PIVOT) / SPAN, 0, CAP)
SYNTHETIC_TS = "SYNTHETIC-mechanics-only"
COLUMNS = ["dk_player_id", "id", "display_name", "pos", "team", "opp", "pred_own", "bonus_points", "oprk", "snapshot_ts"]

OPRK_SQL = """
WITH snap AS (SELECT MAX(pulled_at) AS ts FROM `{raw}.dk_draftable_attributes`
              WHERE draft_group_id = @group AND attr_id = -2 AND pulled_at < TIMESTAMP(@as_of))
SELECT CAST(a.dk_player_id AS STRING) AS dk_player_id, ANY_VALUE(a.sort_value) AS oprk, COUNT(*) AS n,
       FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', ANY_VALUE(snap.ts)) AS ts
FROM `{raw}.dk_draftable_attributes` a JOIN snap ON a.pulled_at = snap.ts
WHERE a.draft_group_id = @group AND a.attr_id = -2
GROUP BY 1"""


def bonus(oprk: pd.Series) -> pd.Series:
    """clip(2 x (oprk - 16) / 16, 0, 2); NaN (no rank) -> 0."""
    v = pd.to_numeric(oprk, errors="coerce")
    return (CAP * (v - PIVOT) / SPAN).clip(0.0, CAP).fillna(0.0)


def synthetic_capture(frame: pd.DataFrame) -> pd.DataFrame:
    """A deterministic stand-in capture for a mechanics smoke: the frame's opponent teams sorted, team k of n gets the rank
    1 + round(31 x k / (n - 1)); every skill player takes his opponent's rank."""
    fr = frame.drop_duplicates("dk_player_id")
    fr = fr[fr.pos.astype(str).isin(SKILL)]
    opps = sorted(set(fr.opp.astype(str)))
    n = len(opps)
    rank = {o: (1 + round(31 * k / (n - 1)) if n > 1 else 32) for k, o in enumerate(opps)}
    return pd.DataFrame({"dk_player_id": fr.dk_player_id.astype("Int64").astype(str).to_numpy(),
                         "oprk": [float(rank[o]) for o in fr.opp.astype(str)], "n": 1, "ts": SYNTHETIC_TS})


def build(frame: pd.DataFrame, cap: pd.DataFrame, snapshot_ts: str) -> tuple[pd.DataFrame, int]:
    """The block file's rows and the number of skill players without a rank; raises ValueError rather than write a file the
    union would misread."""
    n = pd.to_numeric(cap["n"], errors="coerce").fillna(1) if "n" in cap.columns else pd.Series(1, index=cap.index)
    if (n > 1).any() or cap.dk_player_id.astype(str).duplicated().any():
        raise ValueError("a dk_player_id repeats in the capture")
    fr = frame.copy()
    sk = fr.pos.astype(str).isin(SKILL)
    if not sk.any():
        raise ValueError("the frame has no skill players")
    if fr.loc[sk, "dk_player_id"].isna().any():
        raise ValueError("a skill player has no dk_player_id")
    out = fr[sk].copy()
    out["dk_player_id"] = out.dk_player_id.astype("Int64").astype(str)
    if out.dk_player_id.duplicated().any():
        raise ValueError(f"dk_player_id repeats in the frame: {out.dk_player_id[out.dk_player_id.duplicated()].tolist()[:10]}")
    rk = dict(zip(cap.dk_player_id.astype(str), pd.to_numeric(cap.oprk, errors="coerce")))
    out["oprk"] = out.dk_player_id.map(rk)
    out["bonus_points"] = bonus(out.oprk)
    out["pred_own"] = out.bonus_points / TILT
    out["snapshot_ts"] = snapshot_ts
    out["id"] = out["id"].astype(str)
    for c in ("display_name", "pos", "team", "opp"):
        out[c] = out[c].astype(str)
    out = out[COLUMNS].reset_index(drop=True)
    if not np.isfinite(out[["pred_own", "bonus_points"]].to_numpy(float)).all():
        raise ValueError("a non-finite bonus")
    if float(out.pred_own.max()) <= 1.0:
        raise ValueError("no player carries a bonus (own_bonus would refuse the file as fractions)")
    return out, int(out.oprk.isna().sum())


def check_timing(snapshot_ts: str, as_of: str, max_age_hours: float) -> None:
    """Refuses (ValueError) an --as-of without a time zone, a capture at / after --as-of, or one older than the limit."""
    a = pd.Timestamp(as_of)
    if a.tzinfo is None:
        raise ValueError(f"--as-of {as_of} has no time zone (give UTC, e.g. 2026-10-11T15:40:00Z)")
    t = pd.Timestamp(snapshot_ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    if t >= a:
        raise ValueError(f"capture {snapshot_ts} is not before --as-of {as_of}")
    if (a - t) > pd.Timedelta(hours=max_age_hours):
        raise ValueError(f"capture {snapshot_ts} is more than {max_age_hours:g} h before --as-of {as_of} (a missed capture?)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--group", type=int, required=True, help="the DK draft group (W5 main slate: 154468)")
    ap.add_argument("--frame", type=Path, required=True)
    ap.add_argument("--as-of", help="UTC ISO time; the last capture strictly before it (not with --synthetic)")
    ap.add_argument("--max-age-hours", type=float, default=3.0, help="refuse a capture older than this before --as-of")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--capture-csv", type=Path, help="a capture file (dk_player_id, oprk, pulled_at) instead of BigQuery")
    src.add_argument("--synthetic", action="store_true", help="a deterministic capture from the frame (mechanics smokes only)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    frame = pd.read_parquet(a.frame)
    if a.synthetic:
        print("OPRK BLOCK FILE: *** SYNTHETIC CAPTURE -- mechanics only, never a real week's file ***", file=sys.stderr)
        cap, ts = synthetic_capture(frame), SYNTHETIC_TS
    else:
        if not a.as_of or pd.Timestamp(a.as_of).tzinfo is None:
            print(f"OPRK BLOCK FILE REFUSED: --as-of {a.as_of} is missing or has no time zone (give UTC)", file=sys.stderr)
            return 3
        if a.capture_csv:
            cap = pd.read_csv(a.capture_csv, dtype={"dk_player_id": str})
            pulled = pd.to_datetime(cap.pulled_at, utc=True)
            cap = cap[pulled < pd.Timestamp(a.as_of)]
            if cap.empty:
                print(f"OPRK BLOCK FILE REFUSED: no capture in {a.capture_csv} before {a.as_of}", file=sys.stderr)
                return 3
            last = pd.to_datetime(cap.pulled_at, utc=True).max()
            cap = cap[pd.to_datetime(cap.pulled_at, utc=True) == last]
            ts = last.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            from nfl_dfs.bq import query_df
            from nfl_dfs.config import settings
            cap = query_df(OPRK_SQL.format(raw=settings.raw), {"group": a.group, "as_of": a.as_of})
            if cap.empty or cap.ts.isna().all():
                print(f"OPRK BLOCK FILE REFUSED: no capture of group {a.group} before {a.as_of}", file=sys.stderr)
                return 3
            ts = str(cap.ts.iloc[0])
        try:
            check_timing(ts, a.as_of, a.max_age_hours)
        except ValueError as e:
            print(f"OPRK BLOCK FILE REFUSED: {e}", file=sys.stderr)
            return 3
    try:
        out, unranked = build(frame, cap, ts)
    except ValueError as e:
        print(f"OPRK BLOCK FILE REFUSED: {e}", file=sys.stderr)
        return 3
    out.to_csv(a.out, index=False)
    print(f"OPRK BLOCK FILE: week {a.week}, group {a.group}, capture {ts}" + (f" (before {a.as_of})" if a.as_of else "")
          + f", {len(out)} skill players, {int((out.bonus_points > 0).sum())} with a bonus ({int((out.bonus_points >= CAP).sum())} at "
          f"+{CAP:g}), {unranked} without a rank (0); frame {hashlib.sha256(a.frame.read_bytes()).hexdigest()[:8]} -> {a.out} "
          f"(sha256 {hashlib.sha256(a.out.read_bytes()).hexdigest()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
