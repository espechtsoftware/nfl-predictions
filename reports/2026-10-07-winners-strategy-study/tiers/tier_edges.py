"""Where does the regulars' +6 points-per-lineup edge come from, and where is ours lost? The production team's own
picks-vs-field panel (weekly_picks_vs_field.load_week), decomposed by tier: QB, DST, skill under $4k, $4-5.9k, $6-7.9k,
$8k+. For each tier: the edge (sum over the tier's players of (group share - rest share) x points) and its part explained
by price and position tilts (the mean over 400 shuffles of points within position x $1k band); the remainder is
picking better players at the same price. Aggregates only."""
import importlib.util, json, sys, types
from pathlib import Path
import numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location("wpvf", sys.argv[1]); M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
from google.cloud import bigquery
BQ = bigquery.Client()
def tier(r):
    if r.pos == "QB": return "QB"
    if r.pos == "DST": return "DST"
    if pd.isna(r.salary): return "unpriced"
    return "skill <4k" if r.salary < 4000 else "skill 4-5.9k" if r.salary < 6000 else "skill 6-7.9k" if r.salary < 8000 else "skill 8k+"
rows = []
for w in (1, 2, 3, 4):
    cid = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    a = types.SimpleNamespace(season=2026, week=w, contest=cid, frame=str(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet"),
                              cohort=str(Path.home() / "private/regulars/cohort-2026w1-4.txt"), entry_history=str(Path.home() / "private/moneygate/inputs/draftkings-contest-entry-history.csv"))
    d, meta = M.load_week(a); d = d[d.dk.notna()].copy(); d["tier"] = d.apply(tier, axis=1)
    rng = np.random.default_rng(w); pr = d[d.salary.notna()].copy(); pr["band"] = (pr.salary // 1000).astype(int)
    idx = list(pr.groupby(["pos", "band"]).indices.values()); dk = pr.dk.to_numpy(float)
    nulls = {g: {t: [] for t in pr.tier.unique()} for g in ("reg_share", "our_share")}
    for _ in range(400):
        p = dk.copy()
        for ix in idx: p[ix] = rng.permutation(dk[ix])
        for g in nulls:
            contrib = (pr[g].to_numpy() - pr.rest_share.to_numpy()) * p
            for t in nulls[g]: nulls[g][t].append(contrib[(pr.tier == t).to_numpy()].sum())
    for g, lab in (("reg_share", "regulars"), ("our_share", "ours")):
        for t, sub in d.groupby("tier"):
            e = float(((sub[g] - sub.rest_share) * sub.dk).sum()); nm = float(np.mean(nulls[g][t])) if t in nulls[g] else 0.0
            share_diff = float((sub[g] - sub.rest_share).sum())
            rows.append({"week": w, "group": lab, "tier": t, "edge": e, "price_tilt": nm, "picking": e - nm, "slots_minus_field": share_diff})
    print(f"W{w}: lineups {meta['lineups']}", flush=True)
R = pd.DataFrame(rows); R.to_csv(sys.argv[2], index=False)
order = ["QB", "skill 8k+", "skill 6-7.9k", "skill 4-5.9k", "skill <4k", "DST", "unpriced"]
for lab in ("regulars", "ours"):
    g = R[R.group == lab].groupby("tier")[["edge", "price_tilt", "picking", "slots_minus_field"]].mean().reindex(order).dropna(how="all")
    wk = R[R.group == lab].pivot_table(index="tier", columns="week", values="picking").reindex(order).dropna(how="all").round(1)
    print(f"\n{lab.upper()}: points per lineup vs the rest of the field, mean over W1-4 (picking = edge - price/position tilt)"); print(g.round(2).to_string())
    print(f"  total edge {g.edge.sum():+.2f}, of which picking {g.picking.sum():+.2f}"); print("  picking by week:"); print(wk.to_string())
