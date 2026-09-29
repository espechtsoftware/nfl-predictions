"""What the projection is worth INSIDE the historical panel: the sampled field's lineups by their projected-sum percentile."""
import os, sys, json, time
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("OMP_THREAD_LIMIT", "1"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
WT = os.environ["LAB_WT"]                  # a clean checkout of the lab at the L18 results commit (read-only)
sys.path.insert(0, WT + "/src"); sys.path.insert(0, WT + "/experiments")
import numpy as np, pandas as pd
BANDS = [0, .2, .4, .6, .8, .9, .95, .98, .99, .995, 1.0]
def one(args):
    season, week = args; out = f"band/{season}_w{week:02d}.json"
    if os.path.exists(out): return out
    import l09_satellite_objective as l09
    from nfl2.hsim.world import simulate_hsim
    from nfl2.pipeline import simulate_slate, slate_frame, slate_seed
    from l02_field_sampler import sample_field
    bank = 1240
    fr = slate_frame(season, week).reset_index(drop=True)
    sel = simulate_slate(fr, n_sims=10_000, seed=slate_seed(bank + 50, season, week), law_env=l09.ENV).astype(np.float32)
    vsel = simulate_hsim(fr, season, week, 10_000, seed=slate_seed(bank + 50, season, week)).astype(np.float32)
    pm = np.concatenate([sel, vsel], axis=1).mean(axis=1)
    served = pd.to_numeric(fr.get("mean_projection", pd.Series(pm)), errors="coerce").fillna(0).to_numpy(float) if "mean_projection" in fr else pm
    own = pd.read_parquet(l09.OWN_PATH); own = own[(own.season == season) & (own.week == week)]
    target = {str(i): float(p) / 100.0 for i, p in zip(own.id, own.pct)}
    field, _ = sample_field(fr, target, l09.FIELD_N, seed=slate_seed(bank + 700, season, week))
    actual = pd.to_numeric(fr.actual, errors="coerce").fillna(0.0).to_numpy(float)
    ownv = np.array([target.get(str(i), 0.0) for i in fr.id.astype(str)])
    fs = actual[field].sum(axis=1); fp = pm[field].sum(axis=1); fo = ownv[field].sum(axis=1)
    z = (fs - fs.mean()) / fs.std(); pr = pd.Series(fp).rank(pct=True).to_numpy(); orank = pd.Series(fo).rank(pct=True).to_numpy()
    cash = fs >= np.percentile(fs, 77); t10 = fs >= np.percentile(fs, 90); t1 = fs >= np.percentile(fs, 99)
    res = {"season": season, "week": week, "corr_player": float(np.corrcoef(pm[(pm >= 5)], actual[(pm >= 5)])[0, 1]), "mae_player": float(np.abs(pm - actual)[pm >= 5].mean()), "bands": {}, "own_in_80_95": {}}
    for lo, hi in zip(BANDS[:-1], BANDS[1:]):
        m = (pr > lo) & (pr <= hi); res["bands"][f"{lo}-{hi}"] = {"z": float(z[m].mean()), "cash": float(cash[m].mean()), "top10": float(t10[m].mean()), "top1": float(t1[m].mean()), "n": int(m.sum())}
    m = (pr >= .8) & (pr < .95); q = pd.qcut(pd.Series(orank[m]), 5, labels=False).to_numpy()
    for k in range(5): res["own_in_80_95"][str(k)] = {"z": float(z[m][q == k].mean()), "top1": float(t1[m][q == k].mean())}
    json.dump(res, open(out, "w")); return out
if __name__ == "__main__":
    from multiprocessing import Pool
    rows = [json.loads(l)["result"] for l in open(WT + "/results/l18/results_bank1240.jsonl")]
    slates = sorted({(r["season"], r["week"]) for r in rows})
    with Pool(9) as p:
        for o in p.imap_unordered(one, slates): print("done", o, flush=True)
    print("ALL DONE", flush=True)
