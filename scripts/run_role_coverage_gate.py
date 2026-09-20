"""Run the frozen role/coverage feature gate on historical held-out seasons."""
from __future__ import annotations
import json, os, sys
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings

OUT = Path(__file__).resolve().parents[1] / "reports" / "reviews" / "evidence" / "2026-09-20-role-coverage-gate.json"
BASE_NUM = [
    "salary","target_share_l4","target_share_last","snap_share_l4",
    "snap_share_last","air_yards_share_l4","wopr_l4","rz20_target_share_l4",
    "games_played_prior","implied_team_total","spread","game_total","expected_plays",
    "epa_per_dropback_allowed_l6","wr_fp_allowed_adj_l6","te_fp_allowed_adj_l6",
    "fp_route_share_last","fp_route_share_l4","fp_route_share_jump",
]
ROLE_NUM = [
    "fp_player_wide_share","fp_player_slot_share","fp_player_inline_share",
    "fp_player_backfield_share","fp_route_shape_horizontal","fp_route_shape_vertical",
    "fp_route_shape_static","fp_route_shape_shallow","fp_route_shape_backfield",
    "fp_route_te_interaction","fp_route_target_interaction",
]
FP_COV_NUM = ["fp_cov_tprr_edge","fp_cov_yprr_edge","fp_cov_fprr_edge","fp_cov_sep_edge","fp_cov_supported"]
SIS_NUM = ["sis_wide_target_rate","sis_slot_target_rate","sis_wide_ypt","sis_slot_ypt","sis_wide_vulnerability","sis_slot_vulnerability","sis_wide_share","sis_alignment_edge","sis_supported"]


def load():
    q = f"""
    WITH base AS (
      SELECT * FROM `{settings.features}.player_week_training`
      WHERE season BETWEEN 2022 AND 2025 AND week BETWEEN 5 AND 18
        AND was_active AND position IN ('WR','TE') AND y_dk_points IS NOT NULL
    ),
    align AS (
      SELECT season,target_week,gsis_id,player_wide_share,
             SAFE_DIVIDE(slot_routes,overall_routes) AS player_slot_share,
             SAFE_DIVIDE(inline_routes,overall_routes) AS player_inline_share,
             SAFE_DIVIDE(wide_slot_routes,overall_routes) AS player_wide_slot_share,
             SAFE_DIVIDE((overall_routes-wide_routes-slot_routes-inline_routes),overall_routes) AS player_backfield_share
      FROM `{settings.raw}.fantasy_points_alignment_player_l4`
    ),
    shape AS (
      SELECT season,target_week,gsis_id,fp_route_shape_l4_horizontal_share AS route_shape_horizontal,
             fp_route_shape_l4_vertical_share AS route_shape_vertical,
             fp_route_shape_l4_static_share AS route_shape_static,
             fp_route_shape_l4_shallow_share AS route_shape_shallow,
             fp_route_shape_l4_backfield_share AS route_shape_backfield
      FROM `{settings.raw}.fantasy_points_route_shape_l4`
    ),
    cov AS (
      SELECT c.season,c.target_week,c.gsis_id,d.team AS opponent,
        SAFE_DIVIDE(d.def_man_rate*c.man_tprr+d.def_zone_rate*c.zone_tprr,d.def_man_rate+d.def_zone_rate)-c.overall_tprr AS fp_cov_tprr_edge,
        SAFE_DIVIDE(d.def_man_rate*c.man_yprr+d.def_zone_rate*c.zone_yprr,d.def_man_rate+d.def_zone_rate)-c.overall_yprr AS fp_cov_yprr_edge,
        SAFE_DIVIDE(d.def_man_rate*c.man_fprr+d.def_zone_rate*c.zone_fprr,d.def_man_rate+d.def_zone_rate)-c.overall_fprr AS fp_cov_fprr_edge,
        SAFE_DIVIDE(d.def_man_rate*c.man_sep+d.def_zone_rate*c.zone_sep,d.def_man_rate+d.def_zone_rate)-c.zone_sep AS fp_cov_sep_edge,
        CAST(c.fp_cov_l4_supported AS INT64) AS fp_cov_supported
      FROM `{settings.raw}.fantasy_points_receiver_coverage_l4` c
      JOIN `{settings.raw}.fantasy_points_defense_coverage_l4` d
        ON d.season=c.season AND d.target_week=c.target_week

    ),
    sis_w AS (
      SELECT season,target_week,defense,
        SAFE_DIVIDE(targets,coverage_snaps) AS wide_target_rate,
        SAFE_DIVIDE(yards,coverage_snaps) AS wide_ypt,
        vulnerability AS wide_vulnerability
      FROM `{settings.raw}.sis_receiver_copula_defense_prior` WHERE alignment='wide'
    ),
    sis_s AS (
      SELECT season,target_week,defense,
        SAFE_DIVIDE(targets,coverage_snaps) AS slot_target_rate,
        SAFE_DIVIDE(yards,coverage_snaps) AS slot_ypt,
        vulnerability AS slot_vulnerability
      FROM `{settings.raw}.sis_receiver_copula_defense_prior` WHERE alignment='slot'
    )
    SELECT b.*, a.player_wide_share AS fp_player_wide_share, a.player_slot_share AS fp_player_slot_share,
      a.player_inline_share AS fp_player_inline_share, a.player_backfield_share AS fp_player_backfield_share,
      sh.route_shape_horizontal AS fp_route_shape_horizontal, sh.route_shape_vertical AS fp_route_shape_vertical,
      sh.route_shape_static AS fp_route_shape_static, sh.route_shape_shallow AS fp_route_shape_shallow,
      sh.route_shape_backfield AS fp_route_shape_backfield,
      SAFE_MULTIPLY(b.fp_route_share_last, CAST(b.position='TE' AS INT64)) AS fp_route_te_interaction,
      b.fp_route_share_last*b.target_share_l4 AS fp_route_target_interaction,
      c.fp_cov_tprr_edge,c.fp_cov_yprr_edge,c.fp_cov_fprr_edge,c.fp_cov_sep_edge,c.fp_cov_supported,
      w.wide_target_rate AS sis_wide_target_rate,s.slot_target_rate AS sis_slot_target_rate,
      w.wide_ypt AS sis_wide_ypt,s.slot_ypt AS sis_slot_ypt,
      w.wide_vulnerability AS sis_wide_vulnerability,s.slot_vulnerability AS sis_slot_vulnerability,
      a.player_wide_share AS sis_wide_share,
      a.player_wide_share*(COALESCE(w.wide_target_rate,0)-COALESCE(s.slot_target_rate,0)) AS sis_alignment_edge,
      CAST(w.wide_target_rate IS NOT NULL AND s.slot_target_rate IS NOT NULL AS INT64) AS sis_supported
    FROM base b
    LEFT JOIN align a ON a.season=b.season AND a.target_week=b.week AND a.gsis_id=b.gsis_id
    LEFT JOIN shape sh ON sh.season=b.season AND sh.target_week=b.week AND sh.gsis_id=b.gsis_id
    LEFT JOIN cov c ON c.season=b.season AND c.target_week=b.week AND c.gsis_id=b.gsis_id AND c.opponent=b.opponent
    LEFT JOIN sis_w w ON w.season=b.season AND w.target_week=b.week AND w.defense=b.opponent
    LEFT JOIN sis_s s ON s.season=b.season AND s.target_week=b.week AND s.defense=b.opponent
    """
    return query_df(q)


def score(df, arm, test_season):
    train=df[df.season<test_season].copy(); test=df[df.season==test_season].copy()
    num=BASE_NUM.copy()
    if arm in ('role','combined'): num += ROLE_NUM
    if arm in ('fp_coverage','combined'): num += FP_COV_NUM
    if arm in ('sis_coverage','combined'): num += SIS_NUM
    num=[x for x in num if x in df.columns]
    cat=['position']
    prep=ColumnTransformer([('num',Pipeline([('imp',SimpleImputer(strategy='median',add_indicator=True)),('scale',StandardScaler())]),num),('cat',OneHotEncoder(handle_unknown='ignore'),cat)])
    out={'arm':arm,'test_season':int(test_season),'train_rows':len(train),'test_rows':len(test),'features':num}
    y=train.y_dk_points.astype(float); yt=test.y_dk_points.astype(float)
    reg=Pipeline([('prep',prep),('model',Ridge(alpha=10.0))]); reg.fit(train,y); pred=reg.predict(test)
    out['mae']=float(mean_absolute_error(yt,pred))
    for threshold in (20,30):
      clf=Pipeline([('prep',prep),('model',LogisticRegression(C=.1,solver='lbfgs',max_iter=2000))])
      clf.fit(train,(y>=threshold).astype(int)); p=clf.predict_proba(test)[:,1]
      out[f'brier_{threshold}']=float(brier_score_loss((yt>=threshold).astype(int),p)); out[f'event_rate_{threshold}']=float((yt>=threshold).mean())
    out['support']={k:float(test[k].notna().mean()) for k in (ROLE_NUM+FP_COV_NUM+SIS_NUM) if k in test}
    return out

if __name__=='__main__':
  df=load(); print('rows',len(df),'cols',len(df.columns),flush=True)
  results=[]
  for season in (2024,2025):
    for arm in ('control','role','fp_coverage','sis_coverage','combined'):
      print('scoring',season,arm,flush=True); results.append(score(df,arm,season))
  report={'protocol':'2026-09-20-paid-source-role-coverage-protocol','rows':len(df),'results':results}
  OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,indent=2,sort_keys=True)); print(json.dumps(report,indent=2))
