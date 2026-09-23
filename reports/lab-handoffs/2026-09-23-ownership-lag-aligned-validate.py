"""Re-validate ownership lag inputs: base vs 440ab0ab (old) vs aligned, walk-forward 2023-25 and the 2026 Week-2 live frame."""
import importlib.util, sys, numpy as np, pandas as pd
from scipy.stats import spearmanr
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
NEW = load("/home/erich/projects/.nfl-predictions-worktrees/ownership-lag-aligned-20260923/scripts/ownership_sets.py", "osets_new")
OLD = load("/home/erich/projects/.nfl-predictions-worktrees/laptop-agent-intro-20260922/scripts/ownership_sets.py", "osets_old")

for lab, M, lag in (("base", NEW, False), ("old lag (440ab0ab)", OLD, True), ("aligned lag", NEW, True)):
    d = M.training_frame(query_df, settings.project)
    v = M.validate(d, M.FEATURES + M.LAG_FEATURES if lag else M.FEATURES)
    print(f"walk-forward {lab:20s}", {k: round(x, 3) for k, x in v.items()}, flush=True)

# 2026 Week 2 live frame: the last served batch before the Week-2 lock on the main group, implied totals from team_week_context
x = query_df(f"""
    WITH latest AS (SELECT MAX(pulled_at) ts FROM `{settings.raw}.dk_salaries` WHERE draft_group_id = 153428),
    slate AS (SELECT DISTINCT dk_player_id FROM `{settings.raw}.dk_salaries`, latest WHERE draft_group_id = 153428 AND pulled_at = latest.ts),
    b AS (SELECT MAX(generated_at) g FROM `{settings.predictions}.player_projections`
          WHERE season = 2026 AND week = 2 AND generated_at < TIMESTAMP('2026-09-20 17:00:00+00'))
    SELECT p.gsis_id, p.dk_player_id, p.display_name, p.position AS pos, p.team, p.salary, p.proj_points AS proj, p.proj_p90,
           t.implied_team_total
    FROM `{settings.predictions}.player_projections` p JOIN b ON p.generated_at = b.g
    JOIN slate s ON CAST(p.dk_player_id AS STRING) = CAST(s.dk_player_id AS STRING)
    LEFT JOIN `{settings.features}.team_week_context` t ON t.team = p.team AND t.season = 2026 AND t.week = 2
    WHERE p.season = 2026 AND p.week = 2""")
x["slate"] = 153428
own = query_df(f"""
    WITH c AS (SELECT contest_id, ANY_VALUE(contest_name) nm, COUNT(*) n FROM `{settings.raw}.contest_ownership`
               WHERE season = 2026 AND week = 2 GROUP BY 1),
    pick AS (SELECT ARRAY_AGG(contest_id ORDER BY n DESC LIMIT 1)[OFFSET(0)] cid FROM c
             WHERE REGEXP_CONTAINS(nm, r"Millionaire") AND NOT REGEXP_CONTAINS(nm, r"\\(Thu\\)|MEGA|\\$555")),
    slots AS (SELECT o.display_name, o.roster_position, ANY_VALUE(o.pct_drafted) p FROM `{settings.raw}.contest_ownership` o
              JOIN pick ON o.contest_id = pick.cid WHERE o.season = 2026 AND o.week = 2 GROUP BY 1, 2)
    SELECT display_name, SUM(p) own FROM slots GROUP BY 1""")
own["key"] = own.display_name.map(NEW.norm)
print(f"\nW2 frame {len(x)} players; implied total present {x.implied_team_total.notna().mean():.2f}")
for lab, M, lag in (("base", NEW, False), ("old lag (440ab0ab)", OLD, True), ("aligned lag", NEW, True)):
    d = M.training_frame(query_df, settings.project)
    f = M.FEATURES + M.LAG_FEATURES if lag else M.FEATURES
    xx = M.add_features(x.copy(), ["slate"])
    if lag:
        xx = M.live_lag_features(query_df, settings, xx, 2026, 2)
    xx["pred"] = M.predict(M.fit(d, f), xx)
    xx["key"] = xx.display_name.map(NEW.norm); xx["own"] = xx.key.map(own.set_index("key").own).fillna(0.0)
    sub = xx[xx.proj >= 3]
    cov = {c: round(float(xx[c].notna().mean()), 2) for c in NEW.LAG_FEATURES if c in xx}
    print(f"W2 live {lab:20s} Spearman {spearmanr(sub.pred, sub.own).statistic:.3f} (n {len(sub)}) coverage {cov}", flush=True)
