"""Cash/double-up shadow, Week 2 2026: what would a mean-maximizing cash build have scored, once the availability
defects are removed? Declared before scoring: pool = the Saturday 15:30Z frame minus every skill player with zero
offensive snaps (an ORACLE availability filter, ~ the Week-3 rules, which catch 56/57 of Week-2's entered non-players,
so it is mildly optimistic); cash builds = optimize_many on mean `proj` (max_overlap 7) under (i) no stack rule and
(ii) the production QB+2+bring-back stack, 20 lineups each; comparison = the 97 entered lineups; lines = each real
GPP field's top-45% score (the usual double-up depth) and field median. Metric = share of lineups at or above the line."""
import re, sys, numpy as np, pandas as pd
from nfl2.core.lineup import optimize_many, StackRules
from nfl2.pipeline import _pool, PRODUCTION_STACK, PRODUCTION_ENV
from nfl_dfs.bq import query_df
FRAME, WK = sys.argv[1], int(sys.argv[2])     # usage: <run_dir>/frame.parquet <week> ; W2 applies the stand-in fix below
fr = pd.read_parquet(FRAME).reset_index(drop=True)
T = "`nfl-predictions-503414.nfl_raw.contest_entries`"
MID = query_df(f"SELECT contest_id FROM {T} WHERE season=2026 AND week={WK} AND contest_name LIKE '%Millionaire%' GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1").contest_id.iloc[0]
own = query_df(f"""SELECT display_name, MAX(fpts) f FROM `nfl-predictions-503414.nfl_raw.contest_ownership`
                  WHERE season=2026 AND week={WK} AND contest_id='{MID}' GROUP BY 1""")
pts = dict(zip(own.display_name.astype(str), own.f.astype(float)))
sn = query_df(f"""SELECT player nn, SUM(COALESCE(offense_snaps,0)) off FROM `nfl-predictions-503414.nfl_raw.snap_counts`
                 WHERE season=2026 AND week={WK} GROUP BY 1""")
_SUF = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")
def _norm(s): return re.sub(r"[^a-z]", "", _SUF.sub(" ", re.sub(r"[^a-z ]", " ", str(s).lower())))
snl = {_norm(k): v for k, v in zip(sn.nn, sn.off)}
played = [(p == "DST") or snl.get(_norm(n), 0) > 0 for n, p in zip(fr.display_name, fr.pos)]
clean = fr[played].reset_index(drop=True)
# stand-in inflations fixed for Week 3 (production Addendum 2 of simulator-calibration-is-the-defect.md): served -> props-or-nothing value
FIX = {"Justin Jefferson": 17.3, "Ladd McConkey": 14.8, "Jack Bech": 7.1} if WK == 2 else {}
for nm, v in FIX.items():
    m = clean.display_name.astype(str).eq(nm)
    print(f"stand-in fix {nm}: {clean.loc[m, 'proj'].round(1).tolist()} -> {v}"); clean.loc[m, "proj"] = v
top = clean[clean.pos != "DST"].nlargest(8, "proj")[["display_name", "pos", "salary", "proj"]]
print("top projections after fixes:", top.assign(real=[pts.get(n, 0) for n in top.display_name]).round(1).to_string(index=False))
print(f"frame {len(fr)} -> clean {len(clean)} (removed {len(fr)-len(clean)} zero-snap skill players)")
pool = _pool(clean)
def score(lus): return np.array([sum(pts.get(str(p["name"]), 0.0) for p in lu.players) for lu in lus])
builds = {"cash_nostack": optimize_many(pool, 20, stack=StackRules(qb_stack_min=0, bring_back_min=0), objective_col="proj", env=dict(PRODUCTION_ENV)),
          "cash_prodstack": optimize_many(pool, 20, stack=PRODUCTION_STACK, objective_col="proj", env=dict(PRODUCTION_ENV))}
sc = {k: score(v) for k, v in builds.items()}
ours = query_df(f"""WITH acct AS (SELECT REGEXP_REPLACE(entry_name, r' \\(.*\\)$', '') nm FROM {T} WHERE season=2026 AND week=2
                      GROUP BY 1 HAVING COUNT(DISTINCT contest_id)=12 AND COUNT(*)=97)
   SELECT points FROM {T} WHERE season=2026 AND week={WK} AND REGEXP_REPLACE(entry_name, r' \\(.*\\)$', '') IN (SELECT nm FROM acct)""")
sc["entered_book"] = ours.points.to_numpy(float)
proj_of = {k: np.mean([sum(p["proj"] for p in lu.players) for lu in v]) for k, v in builds.items()}
rows = []
gpps = query_df(f"""SELECT contest_id, ANY_VALUE(contest_name) nm, COUNT(*) n FROM {T} WHERE season=2026 AND week={WK}
                   AND NOT REGEXP_CONTAINS(LOWER(contest_name), r'sat|qualifier') GROUP BY 1 HAVING n >= 5000 ORDER BY n DESC LIMIT 5""")
for cid, nm in zip(gpps.contest_id, gpps.nm.str.slice(0, 22)):
    f = query_df(f"SELECT points FROM {T} WHERE season=2026 AND week=2 AND contest_id='{cid}'").points.to_numpy(float)
    du, med = np.quantile(f, 0.55), np.median(f)
    rows.append({"field": nm, "double-up line (top 45%)": round(du, 1), "median": round(med, 1),
                 **{f"{k} cash%": round(100 * (v >= du).mean(), 1) for k, v in sc.items()}})
print(pd.DataFrame(rows).to_string(index=False))
for k, v in sc.items():
    print(f"{k:15s} n={len(v):3d} mean {v.mean():6.1f} min {v.min():6.1f} max {v.max():6.1f}" + (f"  (mean proj {proj_of[k]:.1f})" if k in proj_of else ""))
