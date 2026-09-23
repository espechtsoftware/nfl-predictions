"""Within-book diagnostic, Weeks 1 and 2: does any sort key rank the ENTERED lineups by realized score
in the same direction both weeks? Direction-free: Spearman(key, realized) on distinct entered lineups,
two-sided permutation p (5,000). Keys from the LAST pre-lock generation of
nfl_predictions.player_projections (both weeks), plus realized-field oracles. Declared before running:
a key is a candidate only if its sign agrees in both weeks AND p < 0.10 in both."""
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from nfl_dfs.bq import query_df
from nfl_dfs.backtest.field import naive_ownership
T = "`nfl-predictions-503414.nfl_raw.contest_entries`"; SIG = "REGEXP_REPLACE(entry_name, r' \\(.*\\)$', '')"
LOCK = {1: "2026-09-13 17:00:00", 2: "2026-09-20 17:00:00"}
rng = np.random.default_rng(7)
out = []
for wk in (1, 2):
    ours = query_df(f"""WITH acct AS (SELECT {SIG} nm FROM {T} WHERE season=2026 AND week=2 GROUP BY 1
                          HAVING COUNT(DISTINCT contest_id)=12 AND COUNT(*)=97)
        SELECT players_key, ANY_VALUE(points) points, COUNT(*) copies FROM {T}
        WHERE season=2026 AND week={wk} AND {SIG} IN (SELECT nm FROM acct) GROUP BY 1""")
    milly_id = query_df(f"""SELECT contest_id FROM {T} WHERE season=2026 AND week={wk} AND contest_name LIKE '%Millionaire%'
                            GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1""").contest_id.iloc[0]
    pp = query_df(f"""SELECT display_name, position, salary, proj_points, proj_ownership FROM `nfl-predictions-503414.nfl_predictions.player_projections`
        WHERE season=2026 AND week={wk} AND generated_at = (SELECT MAX(generated_at) FROM `nfl-predictions-503414.nfl_predictions.player_projections`
        WHERE season=2026 AND week={wk} AND generated_at < TIMESTAMP('{LOCK[wk]}'))""")
    own = query_df(f"""SELECT display_name, SUM(pct_drafted) o FROM `nfl-predictions-503414.nfl_raw.contest_ownership`
                       WHERE season=2026 AND week={wk} AND contest_id='{milly_id}' GROUP BY 1""")
    field = query_df(f"SELECT players_key FROM {T} WHERE season=2026 AND week={wk} AND contest_id='{milly_id}'").players_key
    pp = pp.drop_duplicates("display_name")
    pp["own_naive"] = naive_ownership(pp.rename(columns={"position": "pos", "proj_points": "proj"})[["pos", "proj", "salary"]])
    P = pp.set_index("display_name"); O = dict(zip(own.display_name, own.o.astype(float)))
    vocab = {}; F = np.array([[vocab.setdefault(p, len(vocab)) for p in k.split("|")] for k in field if k and k.count("|") == 8])
    exact = pd.Series(["|".join(sorted(k.split("|"))) for k in field]).value_counts()
    L = [k.split("|") for k in ours.players_key]
    miss = sorted({p for l in L for p in l if p not in P.index})
    def s(col): return np.array([sum(P[col].get(p, np.nan) for p in l) for l in L], float)
    keys = {"proj_sum (desc)": s("proj_points"), "own_proj (asc)": -s("proj_ownership"), "own_naive (asc)": -s("own_naive"),
            "own_real (asc) ORACLE": -np.array([sum(O.get(p, 0.0) for p in l) for l in L]),
            "dup_exact (asc) ORACLE": -np.array([exact.get("|".join(sorted(l)), 0) for l in L], float),
            "dup_core>=7 (asc) ORACLE": -np.array([int((np.isin(F, [vocab.get(p, -1) for p in l]).sum(1) >= 7).sum()) for l in L], float)}
    y = ours.points.to_numpy(float)
    print(f"Week {wk}: {len(ours)} distinct entered lineups ({int(ours.copies.sum())} entries); Millionaire field {len(F)}; "
          f"players missing from projections: {miss}")
    for k, v in keys.items():
        ok = ~np.isnan(v); r = spearmanr(v[ok], y[ok]).correlation
        perm = np.array([spearmanr(v[ok], rng.permutation(y[ok])).correlation for _ in range(5000)])
        out.append({"week": wk, "key (sorted first = high)": k, "n": int(ok.sum()), "rho": round(r, 3),
                    "perm_p": round(float((np.abs(perm) >= abs(r)).mean()), 3)})
r = pd.DataFrame(out); print(r.pivot(index="key (sorted first = high)", columns="week", values=["rho", "perm_p", "n"]).to_string())
