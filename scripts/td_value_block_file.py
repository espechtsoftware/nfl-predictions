#!/usr/bin/env python3
"""The week's LIVE TD-value term-block file (the operator 10-07: "I would like to test the under $7000 player idea before
this week - not as paper"; the outside reviewer's field check 70437915 and replay make_tdup_files.py; the reviewer's format,
timing and harm screen 10-07, reports/2026-10-07-td-block-harm-screen.md). The union's --term-block-* vehicle builds N rows
on projection + min(tilt x pred_own, cap); pred_own = bonus / 0.20 at tilt 0.20 / cap 2.0 adds the bonus (capped at 2):

    td_prob = the mean implied probability over books of the player's 'player_anytime_td' price in the LAST props snapshot
              strictly before --as-of (Saturday's arming time; the W2-4 replay uses each week's Saturday 10:00 CT), joined
              to the frame by display_name (as the field check did; unmatched cheap players are printed);
    td_res  = td_prob minus a linear fit of td_prob on salary within position (RB / WR / TE, over the frame's players with a
              price; a position with 5 or fewer priced players gets none);
    z       = td_res standardized within position (pandas' std, ddof 1);
    b_td    = clip(1.0 x z, 0, 2) for RB / WR / TE with salary < 7,000, else 0 (no price: 0). $7,000+ players are not ruled out.
    --matchup-file (the combined option): b_matchup from scripts/matchup_block_file.py's file for the same frame; the bonus is
              b_matchup + b_td, and the block's 2.0 cap binds above 2 (the two are NOT additive above it).

Output (plain CSV, the format own_bonus reads; no metadata line): dk_player_id, id, display_name, pos, team, opp, pred_own
(= bonus / 0.20), bonus_points, b_td, b_matchup, td_prob, salary, td_res, z, snapshot_ts; every skill player of the frame
once (a bonus of 0 included), the DST omitted. Refuses (exit 3): a frame without skill players, a missing or duplicated
dk_player_id, no props snapshot before --as-of (or one at / after it), a snapshot more than --max-age-hours (default 3) before
--as-of (a missed pull must not hand an older day's prices to the live file; the reviewer 10-07), an --as-of without a time
zone, or a week where no player carries a bonus.

    python scripts/td_value_block_file.py --season 2026 --week 5 --frame <a Week-5 frame.parquet> \
        --as-of 2026-10-10T15:00:00Z [--matchup-file <matchup-w5.csv>] --out <path>/tdvalue-w5.csv   (W5: Saturday 10:00 CT,
        written after that morning's ~09:33 CT props pull lands; reports/2026-10-07-td-block-harm-screen.md)
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SKILL = ("QB", "RB", "WR", "TE")
TD_POS = ("RB", "WR", "TE")
CHEAP = 7000
TILT = 0.20
CLIP = (0.0, 2.0)
COLUMNS = ["dk_player_id", "id", "display_name", "pos", "team", "opp", "pred_own", "bonus_points", "b_td", "b_matchup",
           "td_prob", "salary", "td_res", "z", "snapshot_ts"]

TD_SQL = """
WITH snap AS (SELECT MAX(TIMESTAMP(snapshot_ts)) AS ts FROM `{raw}.prop_lines`
              WHERE season = @season AND week = @week AND market = 'player_anytime_td'
                AND TIMESTAMP(snapshot_ts) < TIMESTAMP(@as_of))
SELECT p.player, AVG(IF(p.price > 0, 100 / (p.price + 100), -p.price / (-p.price + 100))) AS td,
       FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', ANY_VALUE(snap.ts)) AS ts
FROM `{raw}.prop_lines` p JOIN snap ON TIMESTAMP(p.snapshot_ts) = snap.ts
WHERE p.season = @season AND p.week = @week AND p.market = 'player_anytime_td'
GROUP BY p.player"""


def build(frame: pd.DataFrame, td: pd.DataFrame, snapshot_ts: str, matchup: pd.DataFrame | None = None) -> tuple[pd.DataFrame, list]:
    """The block file's rows and the unmatched cheap players; raises ValueError rather than write a file the union
    would misread."""
    fr = frame.drop_duplicates("dk_player_id").reset_index(drop=True).copy()
    sk = fr.pos.astype(str).isin(SKILL)
    if not sk.any():
        raise ValueError("the frame has no skill players")
    if fr.loc[sk, "dk_player_id"].isna().any():
        raise ValueError("a skill player has no dk_player_id")
    tdm = dict(zip(td.player.astype(str), pd.to_numeric(td.td, errors="coerce")))
    fr["td_prob"] = fr.display_name.astype(str).map(tdm)
    fr["salary"] = pd.to_numeric(fr.salary, errors="coerce")
    fr["td_res"] = np.nan
    for pos in TD_POS:
        g = fr[(fr.pos == pos) & fr.td_prob.notna() & fr.salary.notna()]
        if len(g) > 5:
            b = np.polyfit(g.salary, g.td_prob, 1)
            fr.loc[g.index, "td_res"] = g.td_prob - np.polyval(b, g.salary)
    fr["z"] = fr.groupby("pos").td_res.transform(lambda v: (v - v.mean()) / v.std())
    fr["b_td"] = np.where(fr.pos.isin(TD_POS) & (fr.salary < CHEAP), np.clip(fr.z.fillna(0), *CLIP), 0.0)
    cheap = fr.pos.isin(TD_POS) & (fr.salary < CHEAP)
    unmatched = fr.loc[cheap & fr.td_prob.isna(), "display_name"].astype(str).tolist()
    out = fr[sk].copy()
    out["dk_player_id"] = out.dk_player_id.astype("Int64").astype(str)
    if matchup is not None:
        mb = dict(zip(matchup.dk_player_id.astype(str), pd.to_numeric(matchup.bonus_points, errors="coerce")))
        out["b_matchup"] = out.dk_player_id.map(mb).fillna(0.0)
    else:
        out["b_matchup"] = 0.0
    out["bonus_points"] = out.b_td + out.b_matchup
    out["pred_own"] = out.bonus_points / TILT
    out["snapshot_ts"] = snapshot_ts
    out["id"] = out["id"].astype(str)
    for c in ("display_name", "pos", "team", "opp"):
        out[c] = out[c].astype(str)
    out = out[COLUMNS].reset_index(drop=True)
    if out.dk_player_id.duplicated().any():
        raise ValueError(f"dk_player_id repeats: {out.dk_player_id[out.dk_player_id.duplicated()].tolist()[:10]}")
    if not np.isfinite(out[["pred_own", "bonus_points", "b_td", "b_matchup"]].to_numpy(float)).all():
        raise ValueError("a non-finite bonus")
    if float(out.pred_own.max()) <= 1.0:
        raise ValueError("no player carries a bonus (own_bonus would refuse the file as fractions)")
    return out, unmatched


def check_timing(snapshot_ts: str, as_of: str, max_age_hours: float) -> None:
    """Refuses (ValueError) an --as-of without a time zone, a snapshot at / after --as-of, or one older than the limit."""
    a = pd.Timestamp(as_of)
    if a.tzinfo is None:
        raise ValueError(f"--as-of {as_of} has no time zone (give UTC, e.g. 2026-10-10T15:00:00Z)")
    t = pd.Timestamp(snapshot_ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    if t >= a:
        raise ValueError(f"snapshot {snapshot_ts} is not before --as-of {as_of}")
    if (a - t) > pd.Timedelta(hours=max_age_hours):
        raise ValueError(f"snapshot {snapshot_ts} is more than {max_age_hours:g} h before --as-of {as_of} (a missed props pull?)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--frame", type=Path, required=True)
    ap.add_argument("--as-of", required=True, help="UTC ISO time (Saturday's arming); the last snapshot strictly before it")
    ap.add_argument("--matchup-file", type=Path, help="scripts/matchup_block_file.py's file for the same frame (combined option)")
    ap.add_argument("--max-age-hours", type=float, default=3.0, help="refuse a snapshot older than this before --as-of")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    if pd.Timestamp(a.as_of).tzinfo is None:
        print(f"TD BLOCK FILE REFUSED: --as-of {a.as_of} has no time zone (give UTC, e.g. 2026-10-10T15:00:00Z)", file=sys.stderr)
        return 3
    td = query_df(TD_SQL.format(raw=settings.raw), {"season": a.season, "week": a.week, "as_of": a.as_of})
    if td.empty or td.ts.isna().all():
        print(f"TD BLOCK FILE REFUSED: no player_anytime_td snapshot for {a.season} W{a.week} before {a.as_of}", file=sys.stderr)
        return 3
    ts = str(td.ts.iloc[0])
    try:
        check_timing(ts, a.as_of, a.max_age_hours)
    except ValueError as e:
        print(f"TD BLOCK FILE REFUSED: {e}", file=sys.stderr)
        return 3
    matchup = pd.read_csv(a.matchup_file, dtype={"dk_player_id": str}) if a.matchup_file else None
    try:
        out, unmatched = build(pd.read_parquet(a.frame), td, ts, matchup)
    except ValueError as e:
        print(f"TD BLOCK FILE REFUSED: {e}", file=sys.stderr)
        return 3
    out.to_csv(a.out, index=False)
    n_td = int((out.b_td > 0).sum()); capped = int((out.bonus_points > CLIP[1]).sum())
    print(f"TD BLOCK FILE: week {a.week}, snapshot {ts} (before {a.as_of}), {len(out)} skill players, {n_td} with a TD bonus"
          + (f", {int((out.bonus_points > 0).sum())} with a combined bonus, {capped} above the block's 2.0 cap" if matchup is not None else "")
          + f"; unmatched cheap players {len(unmatched)}" + (f" ({', '.join(unmatched[:12])})" if unmatched else "")
          + f"; frame {hashlib.sha256(a.frame.read_bytes()).hexdigest()[:8]} -> {a.out} (sha256 {hashlib.sha256(a.out.read_bytes()).hexdigest()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
