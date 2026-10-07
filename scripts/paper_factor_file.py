#!/usr/bin/env python3
"""The week's PAPER factor-bonus file for study 38 amendment 6d (the operator 10-07: "Please review this and schedule any
necessary experiments this week"; the outside reviewer's Experiment A, review/outside-fill-order-20261006 @ 0ad813b2,
reports/2026-10-07-winners-strategy-study/run/experiments/make_factor_files.py; the reviewer's arms MIXT_QA0_MATCHUPX
and MIXT_QA0_COMBINED). Paper only: nothing on the money path reads it.

The bonuses (make_factor_files.py's formulas and weights, fixed before any replay; ported for one week):
    MATCHUP  = clip(1.0 x z, 0, 2): z within position, across ALL the frame's skill players (pandas' std, ddof 1, + 1e-9;
               a missing z counts 0), of the opponent's DK points allowed to the position per game: (6 x the prior
               season's per-game mean + this season's sum over weeks < w) / (6 + this season's games), regular season
               only, positions from player_week_role; a defense missing from the prior season gets the position mean.
    VACATED  = clip(10 x the own-type share vacated by teammates ruled Out (RB: team_vacated_carry_share; WR / TE:
               team_vacated_target_share; QB: 0), 0, 3); a missing share counts 0.
    MARKET   = clip(0.5 x (the frame's props-implied market_points - FP's T-70 mean), 0, 2); a missing market counts 0.
    COMBINED = clip(MATCHUP + VACATED + MARKET, 0, 3).
A player FP projects at 0 (not expected to play) has every bonus 0.

The file (the reviewer's format, 10-07; the arm refuses anything else): one '#' JSON metadata line (study, season, week,
weights, clips, prior_season, prior_games, frame_sha256, fp_sha256, script_sha256, rows, unmatched_opp = the rows whose
opponent and position found no points-allowed value), then dk_player_id, gsis_id, pos, team, opp, b_matchup, b_vacated,
b_market, b_combined, fp: one row per frame skill player with an FP value, each once. The script refuses (exit 3: the arm
is missing that week) a duplicated or missing dk_player_id, a non-finite bonus, or no rows.

    python scripts/paper_factor_file.py --season 2026 --week 5 --frame <w5 T-70 frame.parquet> \
        --fp <w5 T-70 proj_fp csv> --out <abs dir>/2026-w05.csv   (the snapshot copies it as paper-factor-2026-w05.csv)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SKILL = ("QB", "RB", "WR", "TE")
WEIGHTS = {"matchup": 1.0, "vacated": 10.0, "market": 0.5}
CLIPS = {"matchup": (0.0, 2.0), "vacated": (0.0, 3.0), "market": (0.0, 2.0), "combined": (0.0, 3.0)}
PRIOR_GAMES = 6
COLUMNS = ["dk_player_id", "gsis_id", "pos", "team", "opp", "b_matchup", "b_vacated", "b_market", "b_combined", "fp"]

ALLOWED_SQL = """
WITH a AS (SELECT x.season, x.week, x.team, r.position, x.dk_points FROM `{features}.player_week_actuals` x
           JOIN `{features}.player_week_role` r ON r.gsis_id = x.gsis_id AND r.season = x.season AND r.week = x.week
           WHERE x.season IN (@prior, @season) AND r.position IN ('QB', 'RB', 'WR', 'TE'))
SELECT a.season, a.week, s.opponent AS def, a.position, SUM(a.dk_points) AS pts
FROM a JOIN `{features}.schedule_long` s ON s.season = a.season AND s.week = a.week AND s.team = a.team
WHERE s.game_type = 'REG' AND (a.season = @prior OR a.week < @week)
GROUP BY 1, 2, 3, 4"""


def allowed_per_game(allowed: pd.DataFrame, season: int, week: int) -> dict:
    """{(defense, position): (6 x prior-season per-game mean + this season's sum before week) / (6 + games)}."""
    prior = allowed[allowed.season == season - 1].groupby(["def", "position"]).pts.mean()
    cur = allowed[(allowed.season == season) & (allowed.week < week)].groupby(["def", "position"]).pts.agg(["sum", "count"])
    mm = pd.DataFrame({"prior": prior}).join(cur, how="outer").fillna({"sum": 0, "count": 0})
    pr = mm.prior.fillna(mm.prior.groupby(level=1).transform("mean"))      # a defense missing from the prior season
    return ((PRIOR_GAMES * pr + mm["sum"]) / (PRIOR_GAMES + mm["count"])).to_dict()


def fp_by_draftable(frame: pd.DataFrame, fp: pd.DataFrame) -> np.ndarray:
    """FP's T-70 mean per frame row (the proj_fp capture is keyed by dk_draftable_id, as apply_proj_source reads it)."""
    m = dict(zip(fp.dk_draftable_id.astype("Int64").astype(str), pd.to_numeric(fp.fp, errors="coerce")))
    return pd.to_numeric(frame.dk_draftable_id.astype("Int64").astype(str).map(m), errors="coerce").to_numpy(float)


def build(frame: pd.DataFrame, fp: pd.DataFrame, allowed: pd.DataFrame, season: int, week: int) -> tuple[pd.DataFrame, int]:
    """The week's rows in the arm's format and the unmatched-opponent count; raises ValueError rather than write
    outside the format."""
    fr = frame.drop_duplicates("dk_player_id").reset_index(drop=True).copy()
    apg = allowed_per_game(allowed, season, week)
    fr["matchup_raw"] = [apg.get((o, p), np.nan) for o, p in zip(fr.opp.astype(str), fr.pos.astype(str))]
    sk = fr.pos.astype(str).isin(SKILL)
    z = fr[sk].groupby("pos").matchup_raw.transform(lambda s: (s - s.mean()) / (s.std() + 1e-9))
    fr["b_matchup"] = 0.0
    fr.loc[sk, "b_matchup"] = np.clip(WEIGHTS["matchup"] * z.fillna(0), *CLIPS["matchup"])
    vac = np.where(fr.pos == "RB", fr.team_vacated_carry_share,
                   np.where(fr.pos.isin(["WR", "TE"]), fr.team_vacated_target_share, 0.0))
    fr["b_vacated"] = np.where(sk, np.clip(WEIGHTS["vacated"] * pd.to_numeric(pd.Series(vac), errors="coerce").fillna(0).to_numpy(),
                                           *CLIPS["vacated"]), 0.0)
    fr["fp"] = fp_by_draftable(fr, fp)
    mk = pd.to_numeric(fr.market_points, errors="coerce") - fr.fp
    fr["b_market"] = np.where(sk, np.clip(WEIGHTS["market"] * mk.fillna(0), *CLIPS["market"]), 0.0)
    fr["b_combined"] = np.clip(fr.b_matchup + fr.b_vacated + fr.b_market, *CLIPS["combined"])
    out = fr[sk & fr.fp.notna()].copy()
    out.loc[out.fp <= 0, ["b_matchup", "b_vacated", "b_market", "b_combined"]] = 0.0   # FP's 0: no bonus
    unmatched = int(out.matchup_raw.isna().sum())
    if out.dk_player_id.isna().any():                  # checked before the string cast (pandas 3 keeps NA as NaN)
        raise ValueError(f"dk_player_id not unique / missing: {int(out.dk_player_id.isna().sum())} missing")
    out["dk_player_id"] = out.dk_player_id.astype("Int64").astype(str)
    out["gsis_id"] = out["id"].astype(str)
    for c in ("pos", "team", "opp"):
        out[c] = out[c].astype(str)
    out = out[COLUMNS].reset_index(drop=True)
    if out.empty:
        raise ValueError("no skill player on the frame has an FP value")
    dup = out.dk_player_id[out.dk_player_id.duplicated()]
    if len(dup) or out.dk_player_id.isna().any() or (out.dk_player_id == "<NA>").any():
        raise ValueError(f"dk_player_id not unique / missing: {dup.tolist()[:10]}")
    b = out[["b_matchup", "b_vacated", "b_market", "b_combined"]].to_numpy(float)
    if not np.isfinite(b).all() or not np.isfinite(out.fp.to_numpy(float)).all():
        raise ValueError("a non-finite bonus or fp")
    return out, unmatched


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--frame", type=Path, required=True, help="week w's T-70 frame (the union's frame.parquet)")
    ap.add_argument("--fp", type=Path, required=True, help="week w's T-70 FP capture (OUT's proj_fp-<RUN_TAG>.csv)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    allowed = query_df(ALLOWED_SQL.format(features=settings.features), {"prior": a.season - 1, "season": a.season, "week": a.week})
    try:
        out, unmatched = build(pd.read_parquet(a.frame), pd.read_csv(a.fp), allowed, a.season, a.week)
    except ValueError as e:
        print(f"PAPER FACTOR REFUSED: {e}; the arm is missing this week", file=sys.stderr)
        return 3
    meta = {"study": "38 amendment 6d", "season": a.season, "week": a.week, "weights": WEIGHTS,
            "clips": {k: list(v) for k, v in CLIPS.items()}, "prior_season": a.season - 1, "prior_games": PRIOR_GAMES,
            "frame_sha256": hashlib.sha256(a.frame.read_bytes()).hexdigest(),
            "fp_sha256": hashlib.sha256(a.fp.read_bytes()).hexdigest(),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "rows": len(out),
            "unmatched_opp": unmatched}
    with a.out.open("w") as h:
        h.write("# " + json.dumps(meta, sort_keys=True) + "\n")
        out.to_csv(h, index=False)
    n = {k: int((out[f"b_{k}"] > 0).sum()) for k in ("matchup", "vacated", "market", "combined")}
    print(f"PAPER FACTOR: week {a.week}, {len(out)} players; with a bonus: {n}; mean combined "
          f"{out.b_combined.mean():.3f}; unmatched opponents {unmatched} -> {a.out} "
          f"(sha256 {hashlib.sha256(a.out.read_bytes()).hexdigest()[:8]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
