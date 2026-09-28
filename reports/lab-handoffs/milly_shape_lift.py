#!/usr/bin/env python3
"""Millionaire shape lift (laptop, 2026-09-27; operator: "be critical ... if you see a better way to win").

For every entry in the 2026 Week 1-3 Millionaires (contest_entries, ~1.17M lineups): lineup shape (QB salary, QB stack,
bring-back, most players from one game, salary left, TE salary, FLEX position, field ownership sum) and our pre-lock
projected sum (latest player_projections row generated before the Sunday 12:00 CT lock). Prints, per week, the rate at
which each shape finished in the top 1% / top 10% as a multiple of the base rate ("lift"): the conditional rate over the
whole field, not the anatomy of the winners (which is survivorship-biased). Read-only; writes nothing.

    python reports/lab-handoffs/milly_shape_lift.py
"""
import pandas as pd

from nfl_dfs.bq import query_df
from nfl_dfs.config import settings

pd.set_option("display.width", 250)
R, P = settings.raw, settings.predictions
SQL = f"""
WITH grp AS (SELECT * FROM UNNEST([STRUCT(1 AS week, 151307 AS dg, '193028206' AS cid), (2,153427,'195648007'), (3,153769,'195905122')])),
sal AS (SELECT g.week, s.display_name, ANY_VALUE(s.team_abbr) team, ANY_VALUE(s.position) pos, ANY_VALUE(s.salary) salary
        FROM `{R}.dk_salaries` s JOIN grp g ON s.draft_group_id=g.dg AND s.season=2026 GROUP BY 1,2),
sch AS (SELECT week, home_team t, away_team o, total_line tl FROM `{R}.schedules` WHERE season=2026 AND week<=3
        UNION ALL SELECT week, away_team, home_team, total_line FROM `{R}.schedules` WHERE season=2026 AND week<=3),
own AS (SELECT week, display_name, SUM(pct_drafted) own FROM (SELECT o.week, o.display_name, o.roster_position, o.pct_drafted FROM `{R}.contest_ownership` o JOIN grp g ON o.contest_id=g.cid AND o.week=g.week
        WHERE o.season=2026 QUALIFY ROW_NUMBER() OVER (PARTITION BY o.week, o.display_name, o.roster_position ORDER BY o.imported_at DESC)=1) GROUP BY 1,2),
e AS (SELECT e.week, e.entry_id, e.rank, e.points, e.lineup_slots_json, COUNT(*) OVER (PARTITION BY e.week) n
      FROM `{R}.contest_entries` e JOIN grp g ON e.contest_id=g.cid AND e.week=g.week WHERE e.season=2026 AND e.n_players=9
      QUALIFY ROW_NUMBER() OVER (PARTITION BY e.week, e.entry_id ORDER BY e.imported_at DESC)=1),
x AS (SELECT e.week, e.entry_id, e.rank, e.n, JSON_VALUE(it,'$.slot') slot, JSON_VALUE(it,'$.player') p, sal.team,
        IF(sal.pos IN ('D','DST'),'DST',sal.pos) pos, sal.salary, sch.o opp, LEAST(sal.team, sch.o) game, sch.tl, own.own
      FROM e, UNNEST(JSON_QUERY_ARRAY(e.lineup_slots_json)) it
      LEFT JOIN sal ON sal.week=e.week AND sal.display_name=JSON_VALUE(it,'$.player')
      LEFT JOIN sch ON sch.week=e.week AND sch.t=REPLACE(sal.team,'LAR','LA')
      LEFT JOIN own ON own.week=e.week AND own.display_name=JSON_VALUE(it,'$.player')),
q AS (SELECT week, entry_id, ANY_VALUE(IF(slot='QB', team, NULL)) qt, ANY_VALUE(IF(slot='QB', opp, NULL)) qo, ANY_VALUE(IF(slot='QB', tl, NULL)) qtl FROM x GROUP BY 1,2),
gm AS (SELECT week, entry_id, MAX(c) max_game FROM (SELECT week, entry_id, game, COUNT(*) c FROM x GROUP BY 1,2,3) GROUP BY 1,2),
f AS (SELECT x.week, x.entry_id, ANY_VALUE(x.rank) rank, ANY_VALUE(x.n) n,
        MAX(IF(slot='QB', salary, NULL)) qb_sal, SUM(salary) sal_used, SUM(own) own_sum,
        COUNTIF(slot!='QB' AND x.team=q.qt AND pos IN ('WR','TE')) stack,
        COUNTIF(x.team=q.qo AND pos!='DST') bring_back,
        MAX(IF(slot='FLEX', pos, NULL)) flex_pos, MAX(IF(pos='DST', own, NULL)) dst_own,
        MAX(IF(slot='TE', salary, NULL)) te_sal, SUM(IF(pos='RB', salary, 0)) rb_sal, ANY_VALUE(q.qtl) qb_game_total,
        COUNTIF(salary IS NULL) unmatched, ANY_VALUE(gm.max_game) max_game
      FROM x JOIN q USING(week, entry_id) JOIN gm USING(week, entry_id) GROUP BY 1,2)
SELECT *, NTILE(5) OVER (PARTITION BY week ORDER BY own_sum) own_q, NTILE(5) OVER (PARTITION BY week ORDER BY qb_game_total) qgt_q FROM f"""

PROJ = f"""
WITH grp AS (SELECT * FROM UNNEST([STRUCT(1 AS week, '193028206' AS cid, TIMESTAMP('2026-09-13 17:00:00') AS lk), (2,'195648007',TIMESTAMP('2026-09-20 17:00:00')), (3,'195905122',TIMESTAMP('2026-09-27 17:00:00'))])),
g AS (SELECT p.week, MAX(p.generated_at) ga FROM `{P}.player_projections` p JOIN grp USING(week) WHERE p.season=2026 AND p.generated_at < grp.lk GROUP BY 1),
pr AS (SELECT p.week, p.display_name, ANY_VALUE(p.proj_points) proj FROM `{P}.player_projections` p JOIN g ON p.week=g.week AND p.generated_at=g.ga WHERE p.season=2026 GROUP BY 1,2),
e AS (SELECT e.week, e.entry_id, e.lineup_slots_json FROM `{R}.contest_entries` e JOIN grp g ON e.contest_id=g.cid AND e.week=g.week WHERE e.season=2026 AND e.n_players=9
      QUALIFY ROW_NUMBER() OVER (PARTITION BY e.week, e.entry_id ORDER BY e.imported_at DESC)=1)
SELECT e.week, e.entry_id, SUM(pr.proj) proj_sum, COUNTIF(pr.proj IS NULL) proj_unmatched
FROM e, UNNEST(JSON_QUERY_ARRAY(e.lineup_slots_json)) it LEFT JOIN pr ON pr.week=e.week AND pr.display_name=JSON_VALUE(it,'$.player') GROUP BY 1,2"""


def lift(d: pd.DataFrame, col: str, flag: str, base: float) -> pd.DataFrame:
    g = d.groupby([col, "week"], observed=True)[flag].mean().unstack() / base
    return g.round(2)


def main() -> None:
    df = query_df(SQL).merge(query_df(PROJ), on=["week", "entry_id"])
    df = df[(df.unmatched == 0) & (df.proj_unmatched == 0)].copy()
    df["proj_sum"] = df.proj_sum.astype(float); df["own_sum"] = df.own_sum.astype(float)
    df["top1"] = df["rank"] <= 0.01 * df.n; df["top10"] = df["rank"] <= 0.10 * df.n
    df["qb_b"] = pd.cut(df.qb_sal, [0, 5499, 6499, 99999], labels=["<5.5k", "5.5-6.5k", "6.5k+"])
    df["stack_b"] = df["stack"].clip(upper=3); df["mg_b"] = df["max_game"].clip(2, 5)
    df["left_b"] = pd.cut(50000 - df.sal_used, [-1, 100, 400, 1000, 99999], labels=["0-100", "100-400", "400-1000", "1000+"])
    df["te_b"] = pd.cut(df.te_sal, [0, 3499, 4499, 99999], labels=["<3.5k", "3.5-4.5k", "4.5k+"])
    df["pct"] = df.groupby("week").proj_sum.rank(pct=True)
    df["pb"] = pd.cut(df.pct, [0, .5, .8, .9, .95, .98, .99, .995, 1.0001])
    df["pq"] = df.groupby("week").proj_sum.transform(lambda s: pd.qcut(s, 5, labels=False) + 1)
    df["oq"] = df.groupby(["week", "pq"]).own_sum.transform(lambda s: pd.qcut(s, 5, labels=False, duplicates="drop") + 1)
    print(df.groupby("week").size().rename("entries").to_string())
    for col in ("qb_b", "stack_b", "mg_b", "left_b", "te_b", "own_q"):
        print(f"\n== top-1% lift by {col}"); print(lift(df, col, "top1", 0.01).to_string())
        print(f"== top-10% lift by {col}"); print(lift(df, col, "top10", 0.10).to_string())
    print("\n== top-1% / top-10% lift by OUR projected-sum percentile band")
    print(lift(df, "pb", "top1", 0.01).to_string()); print(lift(df, "pb", "top10", 0.10).to_string())
    print("\n== top-1% lift by ownership quintile WITHIN each projected-sum quintile (per week)")
    print(lift(df, "oq", "top1", 0.01).to_string())
    print("\n== pooled weeks: rows = projected-sum quintile, columns = ownership quintile within it (top-1% lift)")
    print((df.groupby(["pq", "oq"]).top1.mean().unstack() / 0.01).round(2).to_string())


if __name__ == "__main__":
    main()
