# PRO METHODS, stage A (data). PRIVATE: per-user exposures carry DraftKings usernames; FP values are licensed.
# The operator, 10-08: "when the professionals/leaders in major tournaments appear to be relying upon Fantasy Points
# projections and when it seems they are using different methodology ... look into the available data points".
# One player-week panel for the 2026 Millionaires W1-4 (pre-lock data points from each week's T-70 frame, the 10-05
# regulars panel's matchup/prior-week features, FP W4 projection + projected ownership, realized fpts + field ownership),
# plus exposures: the 117 regulars per user (>= 100 entries every week), W4 users with >= 20 entries per user, the
# rest of the field pooled, and the week's top 0.1% / 1% lineups pooled (OUTCOME-SELECTED: the "leaders").
#   cd ~/projects/nfl-predictions && PYTHONPATH=src:scripts .venv/bin/python ~/private/pro-methods/build.py
import json
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery

from ownership_blend import norm

P = "nfl-predictions-503414"
OUT = Path.home() / "private" / "pro-methods"
c = bigquery.Client(project=P)
q = lambda s: c.query(s).to_dataframe()
M = {1: "193028206", 2: "195648007", 3: "195905122", 4: "196151357"}
FR = {1: "20260913T160405364118Z-e7255e9", 2: "20260920T155005557498Z-2dc116c", 3: "20260927T155027472554Z-65305f5",
      4: "20261004T155026918221Z-32cdb61"}
LOCK4 = "2026-10-04 17:00:00"
FIX = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS"}
ids = ",".join(f"'{v}'" for v in M.values())
WK = "CASE contest_id " + " ".join(f"WHEN '{v}' THEN {k}" for k, v in M.items()) + " END"

# ---- exposures (BigQuery): per user for regulars and W4 users with >= 20 entries; pooled field and leaders
base = f"""WITH e AS (SELECT {WK} week, entry_id, TRIM(SPLIT(entry_name,' (')[OFFSET(0)]) u, lineup_slots_json j,
    CAST(points AS FLOAT64) pts FROM `{P}.nfl_raw.contest_entries` WHERE season=2026 AND contest_id IN ({ids}) AND points IS NOT NULL),
  cnt AS (SELECT u, week, COUNT(*) n FROM e GROUP BY 1,2),
  reg AS (SELECT u FROM cnt WHERE n >= 100 GROUP BY u HAVING COUNT(DISTINCT week) = 4),
  vol4 AS (SELECT u FROM cnt WHERE week = 4 AND n >= 20),
  r AS (SELECT e.*, reg.u IS NOT NULL is_reg, vol4.u IS NOT NULL is_vol4,
          PERCENT_RANK() OVER (PARTITION BY week ORDER BY pts DESC) pr FROM e LEFT JOIN reg USING (u) LEFT JOIN vol4 USING (u))"""
UC = q(base + """ SELECT week, u, JSON_VALUE(s,'$.player') player, COUNT(*) k FROM r, UNNEST(JSON_QUERY_ARRAY(j)) s
  WHERE is_reg OR (is_vol4 AND week = 4) GROUP BY 1,2,3""")
UR = q(base + """ SELECT week, u, ANY_VALUE(is_reg) is_reg, COUNT(*) n, COUNTIF(pr < 0.01) top1, COUNTIF(pr < 0.001) top01,
  AVG(pr) mean_pr, MAX(pts) best FROM r WHERE is_reg OR (is_vol4 AND week = 4) GROUP BY 1,2""")
PO = q(base + """ SELECT week, JSON_VALUE(s,'$.player') player, COUNT(*) n_all, COUNTIF(NOT is_reg) n_rest, COUNTIF(is_reg) n_reg,
  COUNTIF(pr < 0.01) n_top1, COUNTIF(pr < 0.001) n_top01 FROM r, UNNEST(JSON_QUERY_ARRAY(j)) s GROUP BY 1,2""")
DEN = q(base + """ SELECT week, COUNT(*) all_l, COUNTIF(NOT is_reg) rest_l, COUNTIF(is_reg) reg_l, COUNTIF(pr < 0.01) top1_l,
  COUNTIF(pr < 0.001) top01_l FROM r GROUP BY 1""").set_index("week")
OWN = q(f"""SELECT {WK} week, display_name, MAX(CAST(fpts AS FLOAT64)) fpts, MAX(CAST(pct_drafted AS FLOAT64)) own_pct
  FROM `{P}.nfl_raw.contest_ownership` WHERE season=2026 AND contest_id IN ({ids}) GROUP BY 1,2""")

# ---- FP W4: the newest DraftKings Main capture before lock (projection + FP's projected ownership)
FP = q(f"""SELECT slate_player_id, name, position, fantasy_points fp, projected_ownership_pct fp_own, last_updated, retrieved_at
  FROM `{P}.nfl_raw.fantasy_points_dfs_projections` WHERE season=2026 AND week=4 AND operator='DraftKings' AND slate_name='Main'
  AND retrieved_at < TIMESTAMP('{LOCK4}') QUALIFY retrieved_at = MAX(retrieved_at) OVER ()""")
fp_key = FP.assign(dk=FP.slate_player_id.astype(str)).set_index("dk")

# ---- the 10-05 regulars panel: matchup and prior-week features (pre-lock), keyed (week, player)
old = pd.read_parquet(Path.home() / "private/week4-monday/players/panel.parquet")
keep_old = ["sal_change", "dvp26", "dvp25", "opp_pass_epa", "opp_rush_epa", "sis_opp_pass_epa", "sis_opp_rush_epa", "opp_def_proe",
            "fp_ol_rush", "fp_ol_pass", "fp_opp_dl_ybc", "fp_opp_dl_press", "fp_cov_grade", "fp_exp_fp_rte", "dk_w1", "own_w1",
            "beat_proj_w1", "tgt_share_w1", "car_share_w1", "questionable"]
old["key"] = old.player.map(norm)
old = old.drop_duplicates(["week", "key"]).set_index(["week", "key"])[keep_old]

FRAME_COLS = ["salary", "salary_delta_wow", "mean_projection", "model_points_pre", "market_points", "dk_ppg", "proj_tourney",
              "implied_team_total", "game_total", "spread", "expected_game_script", "expected_plays", "is_home", "is_dome",
              "wind_mph", "temp_f", "target_share_l4", "target_share_last", "target_share_jump", "target_share_trend",
              "carry_share_l4", "carry_share_last", "carry_share_jump", "snap_share_l4", "snap_share_last", "snap_share_jump",
              "wopr_l4", "air_yards_share_l4", "adot_l8", "deep_targets_l4", "ez_targets_l4", "rz20_target_share_l4",
              "rz10_target_share_l4", "gl3_carry_share_l4", "xfp_l4", "xtd_receiving_proxy", "separation_l4",
              "fp_route_share_l4", "fp_route_share_last", "fp_route_share_jump", "dk_points_l4", "dk_points_std",
              "dk_points_vol", "team_vacated_target_share", "team_vacated_carry_share", "vacated_capture_tgt",
              "vacated_capture_car", "depth_rank", "games_played_prior", "is_rookie", "practice_status", "injury_status",
              "pace_l4", "proe_l4", "neutral_pass_rate_l6", "pa_rate_l6", "team_top2_target_share_l6", "qb_cpoe_l6",
              "epa_per_dropback_allowed_l6", "epa_per_rush_allowed_l6", "qb_fp_allowed_adj_l6", "rb_fp_allowed_adj_l6",
              "wr_fp_allowed_adj_l6", "te_fp_allowed_adj_l6", "opp_blitz_rate_l6", "opp_pressure_rate_l6", "cb_ypt_allowed_l6",
              "top_cb_out", "rz_td_rate_allowed_l6", "stacked_box_l4", "yards_per_carry_l8", "yards_per_target_l8"]

rows, audit = [], {}
for w in (1, 2, 3, 4):
    fr = pd.read_parquet(Path.home() / f"moneygate/inputs/runs/{FR[w]}/frame.parquet").drop_duplicates("id")
    fr["key"] = fr.display_name.astype(str).map(norm)
    dup = set(fr.key[fr.key.duplicated(keep=False)])
    fr = fr[~fr.key.isin(dup)].copy()
    d = pd.DataFrame({"week": w, "key": fr.key, "name": fr.display_name.astype(str), "pos": fr.pos.astype(str),
                      "team": fr.team.astype(str).replace(FIX), "game": fr.game_id.astype(str),
                      "gsis": fr.gsis_id.astype(str),
                      "dk": fr.dk_draftable_id.map(lambda v: str(v)[:-2] if str(v).endswith(".0") else str(v))})
    for col in FRAME_COLS:
        d[col] = pd.to_numeric(fr[col], errors="coerce") if col in fr and col not in ("practice_status", "injury_status") \
            else (fr[col].astype(str) if col in fr else np.nan)
    d["props_real"] = d.market_points.notna() & ((d.market_points - d.dk_ppg).abs() >= 0.01)
    d["props"] = d.market_points.where(d.props_real)
    o = OWN[OWN.week == w].assign(key=lambda x: x.display_name.map(norm))
    o = o[~o.key.duplicated(keep=False)].set_index("key")
    d["actual"] = d.key.map(o.fpts); d["field_own"] = d.key.map(o.own_pct) / 100.0
    po = PO[PO.week == w].assign(key=lambda x: x.player.map(norm)); po = po[~po.key.duplicated(keep=False)].set_index("key")
    den = DEN.loc[w]
    for col, n in (("all", "all_l"), ("rest", "rest_l"), ("reg", "reg_l"), ("top1", "top1_l"), ("top01", "top01_l")):
        d[f"exp_{col}"] = d.key.map(po[f"n_{col}"]).fillna(0) / float(den[n])
    if w == 4:
        d["fp"] = d.dk.map(fp_key.fp.astype(float)); d["fp_own"] = d.dk.map(fp_key.fp_own.astype(float)) / 100.0
    else:
        d["fp"] = np.nan; d["fp_own"] = np.nan
    oo = old.loc[w] if w in old.index.get_level_values(0) else None
    for col in keep_old:
        d[col] = d.key.map(oo[col]) if oo is not None else np.nan
    audit[f"w{w}"] = {"frame_rows": int(len(fr)), "name_dups_dropped": len(dup), "with_actual": int(d.actual.notna().sum()),
                      "with_props_real": int(d.props_real.sum()), "with_fp": int(d.fp.notna().sum()),
                      "lineups": {k: int(v) for k, v in den.items()}}
    rows.append(d)
panel = pd.concat(rows, ignore_index=True)

# per-user exposures (share of the user's lineups holding the player), joined on the normalized key
UC["key"] = UC.player.map(norm)
UC = UC.merge(UR[["week", "u", "n"]], on=["week", "u"])
UC["share"] = UC.k / UC.n
ux = UC.groupby(["week", "u", "key"], as_index=False).share.sum()

panel.to_parquet(OUT / "panel.parquet")
ux.to_parquet(OUT / "user_exposure.parquet")
UR.to_parquet(OUT / "user_results.parquet")
audit["fp_capture"] = {"retrieved_at": str(FP.retrieved_at.max()), "last_updated": str(FP.last_updated.max()), "rows": int(len(FP))}
audit["users"] = {"regulars": int(UR[UR.is_reg].u.nunique()), "w4_vol20": int(UR[(UR.week == 4)].u.nunique())}
(OUT / "audit.json").write_text(json.dumps(audit, indent=1, default=str) + "\n")
print(json.dumps(audit, indent=1, default=str)[:2500])
