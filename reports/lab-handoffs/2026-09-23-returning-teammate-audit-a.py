"""(a) Were the study's 'returners' really absent at W-1?  Cross-check against box scores and snap counts."""
import pandas as pd
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
d = pd.read_parquet("ceiling_panel.parquet")
act = d[d.was_active.astype(bool)][["gsis_id", "season", "week", "team", "position", "target_share_l4"]]
key = set(zip(act.gsis_id, act.season, act.week)); teamweeks = set(zip(act.season, act.team, act.week))
ret = act[act.position.isin(["WR", "TE", "RB"]) & (act.target_share_l4 >= 0.18)].copy()
ret["was_out_prev"] = [(g, s, w - 1) not in key for g, s, w in zip(ret.gsis_id, ret.season, ret.week)]
ret["was_in_before"] = [((g, s, w - 2) in key) or ((g, s, w - 3) in key) for g, s, w in zip(ret.gsis_id, ret.season, ret.week)]
ret["team_played_prev"] = [(s, t, w - 1) in teamweeks for s, t, w in zip(ret.season, ret.team, ret.week)]
R = ret[ret.was_out_prev & ret.was_in_before & ret.team_played_prev].copy()
# does the panel have a row (inactive or not) at W-1?  pre-2022 missing rows vs recorded inactive rows
allkey = set(zip(d.gsis_id, d.season, d.week))
R["row_prev"] = [(g, s, w - 1) in allkey for g, s, w in zip(R.gsis_id, R.season, R.week)]
ws = query_df(f"""SELECT player_id gsis_id, season, week, COALESCE(targets,0)+COALESCE(carries,0) opps
                  FROM `{settings.raw}.weekly_stats` WHERE season BETWEEN 2014 AND 2025 AND season_type='REG'""")
wsk = {(g, s, w): o for g, s, w, o in zip(ws.gsis_id, ws.season, ws.week, ws.opps)}
sn = query_df(f"""SELECT i.gsis_id, CAST(n.season AS INT64) season, CAST(n.week AS INT64) week, MAX(n.offense_snaps) snaps
                  FROM `{settings.raw}.snap_counts` n JOIN `{settings.raw}.player_ids` i ON i.pfr_id = n.pfr_player_id
                  WHERE i.gsis_id IS NOT NULL AND CAST(n.season AS INT64) BETWEEN 2014 AND 2025 GROUP BY 1,2,3""")
snk = {(g, s, w): x for g, s, w, x in zip(sn.gsis_id, sn.season, sn.week, sn.snaps)}
R["box_prev_opps"] = [wsk.get((g, s, w - 1)) for g, s, w in zip(R.gsis_id, R.season, R.week)]
R["snaps_prev"] = [snk.get((g, s, w - 1)) for g, s, w in zip(R.gsis_id, R.season, R.week)]
R["played_prev_truth"] = R.box_prev_opps.notna() | (R.snaps_prev.fillna(0) > 0)
R["era"] = pd.cut(R.season, [2013, 2021, 2025], labels=["2014-21", "2022-25"])
print(f"returners: {len(R)}")
print(R.groupby(["era", "row_prev"], observed=True).agg(n=("gsis_id", "size"), false_returner=("played_prev_truth", "sum")).to_string())
print("\nfalse returners by season (played W-1 per box score/snaps but counted absent):")
print(R.groupby("season").agg(n=("gsis_id", "size"), false=("played_prev_truth", "sum")).assign(share=lambda x: (x.false / x.n).round(3)).to_string())
fr = R[R.played_prev_truth]
print("\nexamples:"); print(fr[["season", "week", "team", "position", "gsis_id", "box_prev_opps", "snaps_prev", "row_prev"]].head(15).to_string(index=False))
R.to_parquet("returners_audited.parquet")
# positive control: at the return week W every returner was active, so the lookups must hit
R["box_W"] = [wsk.get((g, s, w)) for g, s, w in zip(R.gsis_id, R.season, R.week)]
R["snaps_W"] = [snk.get((g, s, w)) for g, s, w in zip(R.gsis_id, R.season, R.week)]
print(f"\npositive control at W: box-score hit {R.box_W.notna().mean():.3f}, snaps hit {R.snaps_W.notna().mean():.3f}")
print(f"at W-2 (was_in_before): box hit {pd.Series([wsk.get((g, s, w - 2)) for g, s, w in zip(R.gsis_id, R.season, R.week)]).notna().mean():.3f}")
