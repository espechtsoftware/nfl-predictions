"""Standing diagnostic battery (2026-08-05, Addendum 61): the WHY layer
under the tails metric. Run against any entries export (replay_lineups
CSV with player rows incl. actuals) + the slate-actuals pull:

  python scripts/diagnose_portfolio.py reports/entries_study/e150_lineups_2025.csv

Reports, per the analyses that found tonight's mechanisms:
  1. capture%: best-of-N vs perfect-hindsight optimal (skill-8 MILP)
  2. pool-hit%: optimal players present anywhere in the portfolio
  3. assembly: best-entry overlap w/ optimal vs the exposure-preserving
     RANDOM null (below null = construction is scattering winners)
  4. pair co-occurrence: optimal pairs co-rostered in >=1 entry
  5. QB anchoring: optimal QB in pool / in best entry
  6. generator attribution: which candidate batch produced the weekly
     best and the line-clearers
A future arm that MOVES tails should move one of these; one that
doesn't move any is winning on noise.
"""
import sys

import numpy as np
import pandas as pd
import pulp

sys.path.insert(0, "src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings


def hindsight_optimal(wd):
    prob = pulp.LpProblem("h", pulp.LpMaximize)
    x = {i: pulp.LpVariable(f"x{i}", cat="Binary") for i in wd.index}
    prob += pulp.lpSum(x[i] * wd.actual[i] for i in wd.index)
    prob += pulp.lpSum(x[i] * wd.salary[i] for i in wd.index) <= 47000
    prob += pulp.lpSum(x.values()) == 8
    pos = wd.position
    def cnt(p): return pulp.lpSum(x[i] for i in wd.index if pos[i] == p)
    prob += cnt("QB") == 1
    prob += cnt("RB") >= 2; prob += cnt("RB") <= 3
    prob += cnt("WR") >= 3; prob += cnt("WR") <= 4
    prob += cnt("TE") >= 1; prob += cnt("TE") <= 2
    prob.solve(pulp.PULP_CBC_CMD(msg=0, threads=2))
    return wd.loc[[i for i in wd.index if x[i].value() == 1]]


def main(path):
    ours = pd.read_csv(path)
    seasons = sorted(ours.season.unique())
    slate = query_df(f"""
      SELECT a.season, a.week, a.gsis_id, a.dk_points AS actual,
             s.salary, u.position, i.name
      FROM `{settings.features}.player_week_actuals` a
      JOIN `{settings.features}.dk_salary_week` s USING (gsis_id, season, week)
      JOIN `{settings.features}.player_week_usage` u USING (gsis_id, season, week)
      LEFT JOIN `{settings.raw}.player_ids` i USING (gsis_id)
      WHERE a.season IN ({",".join(map(str, seasons))}) AND a.week <= 18
        AND u.position IN ('QB','RB','WR','TE')""")
    import itertools

    rng = np.random.default_rng(0)
    rows, pair_hits, pair_tot = [], 0, 0
    qb_pool = qb_best = 0
    tag_best: dict = {}
    for (season, week), wd in slate.groupby(["season", "week"]):
        ow = ours[(ours.season == season) & (ours.week == week)]
        if ow.empty:
            continue
        wd = wd.reset_index(drop=True)
        opt = hindsight_optimal(wd)
        opt_names = list(opt.name.dropna())
        entries = {ix: set(g.player) for ix, g in ow.groupby("entry_ix")}
        lu = ow.drop_duplicates("entry_ix")[["entry_ix", "lineup_score", "tag"]]
        bix = lu.loc[lu.lineup_score.idxmax(), "entry_ix"]
        tag = lu.loc[lu.entry_ix == bix, "tag"].iloc[0]
        tag_best[tag] = tag_best.get(tag, 0) + 1
        in_pool = [n for n in opt_names
                   if any(n in e for e in entries.values())]
        for a, b in itertools.combinations(in_pool, 2):
            pair_tot += 1
            pair_hits += any(a in e and b in e for e in entries.values())
        oqb = opt[opt.position == "QB"].name.iloc[0]
        qb_pool += any(oqb in e for e in entries.values())
        qb_best += oqb in entries[bix]
        exp = [sum(1 for e in entries.values() if n in e) / len(entries)
               for n in in_pool]
        null = np.mean([(rng.random((len(entries), len(exp)))
                         < np.array(exp)).sum(axis=1).max()
                        for _ in range(100)]) if exp else 0
        rows.append({
            "capture": lu.lineup_score.max() / (opt.actual.sum() + 10),
            "pool_hit": len(in_pool) / max(len(opt_names), 1),
            "best_overlap": len(set(opt_names) & entries[bix]),
            "null_overlap": null})
    r = pd.DataFrame(rows)
    n = len(r)
    print(f"weeks: {n}")
    print(f"1. capture (best vs optimal):   {100*r.capture.mean():.1f}%")
    print(f"2. pool-hit (optimal in pool):  {100*r.pool_hit.mean():.1f}%")
    print(f"3. assembly: best-entry overlap {r.best_overlap.mean():.2f} "
          f"vs random-null {r.null_overlap.mean():.2f} "
          f"({'BELOW' if r.best_overlap.mean() < r.null_overlap.mean() else 'above'} null)")
    print(f"4. optimal pairs co-rostered:   {100*pair_hits/max(pair_tot,1):.1f}%")
    print(f"5. optimal QB in pool {qb_pool}/{n}; in best entry {qb_best}/{n}")
    print(f"6. best-entry generator: {tag_best}")


if __name__ == "__main__":
    main(sys.argv[1])
