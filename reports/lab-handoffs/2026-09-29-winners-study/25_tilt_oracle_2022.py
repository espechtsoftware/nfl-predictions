"""Descriptive: the armed main-book form with an ownership term in the objective. ORACLE = realized Millionaire ownership
(not available before lock; it measures the ceiling). LAG = the lag model's pre-lock predicted ownership (L05's replay sets)."""
import os, sys, json, math, time
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("OMP_THREAD_LIMIT", "1"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
WT = os.environ["LAB_WT"]                  # a clean checkout of the lab at the L18 results commit (read-only)
sys.path.insert(0, WT + "/src"); sys.path.insert(0, WT + "/experiments")
import numpy as np, pandas as pd
def one(args):
    season, week = args; out = f"tilt2022/{season}_w{week:02d}.json"
    if os.path.exists(out): return out
    import l18_cap_tight as L, l09_satellite_objective as l09
    from nfl2.hsim.world import simulate_hsim
    from nfl2.pipeline import candidate_actual, simulate_slate, slate_frame, slate_seed
    from l02_field_sampler import sample_field
    bank = 1240
    fr = slate_frame(season, week).reset_index(drop=True)
    sel = simulate_slate(fr, n_sims=10_000, seed=slate_seed(bank + 50, season, week), law_env=l09.ENV).astype(np.float32)
    vsel = simulate_hsim(fr, season, week, 10_000, seed=slate_seed(bank + 50, season, week)).astype(np.float32)
    pm = np.concatenate([sel, vsel], axis=1).mean(axis=1)
    own = pd.read_parquet(l09.OWN_PATH); own = own[(own.season == season) & (own.week == week)]
    target = {str(i): float(p) / 100.0 for i, p in zip(own.id, own.pct)}
    ids = fr.id.astype(str).to_numpy(); skill = fr.pos.astype(str).isin(["QB", "RB", "WR", "TE"]).to_numpy()
    oracle = np.array([100 * target.get(i, 0.0) for i in ids]) * skill
    lagv = oracle
    low = skill & (pm < 1.0); keep = ~low
    frp = fr[keep].reset_index(drop=True)
    field, _ = sample_field(fr, target, l09.FIELD_N, seed=slate_seed(bank + 700, season, week))
    actual = pd.to_numeric(fr.actual, errors="coerce").fillna(0.0).to_numpy(float); fs = np.sort(actual[field].sum(axis=1))
    res = {"season": season, "week": week, "field_mean": float(fs.mean()), "field_sd": float(fs.std()), "lag_coverage": float((lagv[skill & (pm >= 5)] > 0).mean()),
           "corr_lag_oracle": float(pd.Series(lagv[skill & (pm >= 3)]).corr(pd.Series(oracle[skill & (pm >= 3)]), method="spearman")), "arms": {}}
    arms = {"base": pm, "oracle05": pm + 0.05 * oracle, "oracle10": pm + 0.10 * oracle, "oracle20": pm + 0.20 * oracle}
    base_ids = None
    for name, obj in arms.items():
        b = L.plain_mean_book(frp, obj[keep], 36, 18, max(1, math.floor(0.25 * 36)))
        a = np.asarray(candidate_actual(fr, b), dtype=float)
        idset = [frozenset(lu.ids) for lu in b]
        if name == "base": base_ids = set(idset)
        res["arms"][name] = {"score": a.round(2).tolist(), "pct": (np.searchsorted(fs, a, side="left") / len(fs)).round(5).tolist(), "shared_with_base": len(set(idset) & base_ids),
                             "own_sum": float(np.mean([sum(oracle[list(ids).index(str(p["id"]))] for p in lu.players) for lu in b]))}
    json.dump(res, open(out, "w")); return out
if __name__ == "__main__":
    from multiprocessing import Pool
    slates = [tuple(x) for x in json.load(open("slates_2022.json"))]
    with Pool(9) as p:
        for o in p.imap_unordered(one, slates): print("done", o, flush=True)
    print("ALL DONE", flush=True)
