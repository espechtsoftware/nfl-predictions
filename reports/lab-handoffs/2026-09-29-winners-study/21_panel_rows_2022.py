"""Descriptive (not a frozen read): the armed main-book form (PMO_X50, 25% DST cap) on L13's 36 slates, bank 1240, with every
row's realized score and its percentile in a 200,000-lineup field sampled from the slate's real ownership. Lab code is
imported READ-ONLY from the L18 reader worktree; nothing is written there."""
import os, sys, json, math, time
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("OMP_THREAD_LIMIT", "1"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
WT = os.environ["LAB_WT"]                  # a clean checkout of the lab at the L18 results commit (read-only)
sys.path.insert(0, WT + "/src"); sys.path.insert(0, WT + "/experiments")
import numpy as np, pandas as pd
from collections import Counter

def one(args):
    season, week = args
    out = f"pct2022/{season}_w{week:02d}.json"
    if os.path.exists(out): return out
    import l18_cap_tight as L, l09_satellite_objective as l09
    from nfl2.hsim.world import simulate_hsim
    from nfl2.pipeline import candidate_actual, simulate_slate, slate_frame, slate_seed
    from l02_field_sampler import sample_field
    bank = 1240; t0 = time.time()
    fr = slate_frame(season, week).reset_index(drop=True)
    sel = simulate_slate(fr, n_sims=10_000, seed=slate_seed(bank + 50, season, week), law_env=l09.ENV).astype(np.float32)
    vsel = simulate_hsim(fr, season, week, 10_000, seed=slate_seed(bank + 50, season, week)).astype(np.float32)
    pm = np.concatenate([sel, vsel], axis=1).mean(axis=1)
    low = fr.pos.astype(str).isin(["QB", "RB", "WR", "TE"]).to_numpy() & (pm < 1.0)
    frp = fr[~low].reset_index(drop=True); pmp = pm[~low]
    books = {"K36": L.plain_mean_book(frp, pmp, 36, 18, max(1, math.floor(0.25 * 36))),
             "K144": L.plain_mean_book(frp, pmp, 144, 72, max(1, math.floor(0.25 * 144)))}
    own = pd.read_parquet(l09.OWN_PATH); own = own[(own.season == season) & (own.week == week)]
    target = {str(i): float(p) / 100.0 for i, p in zip(own.id, own.pct)}
    field, _ = sample_field(fr, target, l09.FIELD_N, seed=slate_seed(bank + 700, season, week))
    actual = pd.to_numeric(fr.actual, errors="coerce").fillna(0.0).to_numpy(float)
    fs = np.sort(actual[field].sum(axis=1))
    idx = {str(i): n for n, i in enumerate(fr.id.astype(str))}
    res = {"season": season, "week": week, "field_mean": float(fs.mean()), "field_sd": float(fs.std()),
           "field_q": {str(q): float(np.percentile(fs, q)) for q in (10, 25, 50, 55, 60, 70, 75, 77, 80, 85, 89, 90, 91, 95, 96, 98, 99, 99.5, 99.8, 99.9, 99.99)}}
    for k, b in books.items():
        a = np.asarray(candidate_actual(fr, b), dtype=float)
        res[k] = {"score": a.round(2).tolist(), "pct": (np.searchsorted(fs, a, side="left") / len(fs)).round(5).tolist(),
                  "proj": [round(float(sum(pm[idx[str(p['id'])]] for p in lu.players)), 2) for lu in b],
                  "max_exposure": max(Counter(p for lu in b for p in lu.ids).values()), "distinct": len(set().union(*[lu.ids for lu in b]))}
    res["secs"] = round(time.time() - t0, 1)
    json.dump(res, open(out, "w"))
    return out

if __name__ == "__main__":
    from multiprocessing import Pool
    slates = [tuple(x) for x in json.load(open("slates_2022.json"))]
    print("slates", len(slates), flush=True)
    with Pool(9) as p:
        for o in p.imap_unordered(one, slates): print("done", o, flush=True)
    print("ALL DONE", flush=True)
