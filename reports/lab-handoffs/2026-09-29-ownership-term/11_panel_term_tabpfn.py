"""Descriptive: the armed main-book form (K rows, exposure cap K/2, DST cap K/4) with the ownership term from several
predictors on the same bank: none (X50), the L15 blend files, and the L23b TabPFN stage-1 predictions (sha-pinned).
    KROWS=100 WORKERS=14 python tilt6_run.py <bank> <outdir> <name=lambda:source,...>
    source = a directory of <season>-w<WW>.csv sets files (pred_own, id/gsis_id), or TABPFN_LS / TABPFN_LAG"""
import os, sys, json, math, hashlib
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("OMP_THREAD_LIMIT", "1"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
WT = os.environ["LAB_WT"]            # a lab checkout at L18's freeze (fb397d9), imported read-only
sys.path.insert(0, WT + "/src"); sys.path.insert(0, WT + "/experiments")
import numpy as np, pandas as pd
BANK = int(sys.argv[1]); OUT = sys.argv[2]; KROWS = int(os.environ.get("KROWS", "36"))
ARMS = []
for a in sys.argv[3].split(","):
    name, rest = a.split("="); lam, src = rest.split(":") if ":" in rest else (rest, "")
    ARMS.append((name, float(lam), src))
PREDS = os.environ["TABPFN_PREDS"]   # gs://…-raw/private/l23b/preds_l23b.parquet (sha pinned below); PREDS_SHA = "5c8384d644298991c7c4bf111d60ebb5b08e062487df54068fc618d5d4f4d28c"
def one(args):
    season, week = args; out = f"{OUT}/{season}_w{week:02d}.json"
    if os.path.exists(out): return out
    import l18_cap_tight as L, l09_satellite_objective as l09
    from nfl2.hsim.world import simulate_hsim
    from nfl2.pipeline import candidate_actual, simulate_slate, slate_frame, slate_seed
    from l02_field_sampler import sample_field
    fr = slate_frame(season, week).reset_index(drop=True)
    sel = simulate_slate(fr, n_sims=10_000, seed=slate_seed(BANK + 50, season, week), law_env=l09.ENV).astype(np.float32)
    vsel = simulate_hsim(fr, season, week, 10_000, seed=slate_seed(BANK + 50, season, week)).astype(np.float32)
    pm = np.concatenate([sel, vsel], axis=1).mean(axis=1)
    own = pd.read_parquet(l09.OWN_PATH); own = own[(own.season == season) & (own.week == week)]
    target = {str(i): float(p) / 100.0 for i, p in zip(own.id, own.pct)}
    ids = fr.id.astype(str).to_numpy(); skill = fr.pos.astype(str).isin(["QB", "RB", "WR", "TE"]).to_numpy()
    pos_of = {i: k for k, i in enumerate(ids)}
    oracle = np.array([100 * target.get(i, 0.0) for i in ids]) * skill
    gid = fr.gsis_id.astype(str).to_numpy() if "gsis_id" in fr.columns else ids
    def pred_from(src):
        if not src:
            return np.zeros(len(ids))
        if src.startswith("TABPFN"):
            p = pd.read_parquet(PREDS); p = p[(p.season == season) & (p.week == week) & (p.arm == src)]
            d = dict(zip(p.id.astype(str), p.pred_own.astype(float)))
            return np.array([max(d.get(i, 0.0), 0.0) for i in ids]) * skill
        s = pd.read_csv(f"{src}/{season}-w{week:02d}.csv", dtype=str)
        key = "id" if "id" in s.columns else "gsis_id"; lp = dict(zip(s[key].astype(str), pd.to_numeric(s.pred_own, errors="coerce").fillna(0)))
        return np.array([max(lp.get(a, lp.get(b, 0.0)), 0.0) for a, b in zip(ids, gid)]) * skill
    keep = ~(skill & (pm < 1.0))
    frp = fr[keep].reset_index(drop=True)
    field, _ = sample_field(fr, target, l09.FIELD_N, seed=slate_seed(BANK + 700, season, week))
    actual = pd.to_numeric(fr.actual, errors="coerce").fillna(0.0).to_numpy(float); fs = np.sort(actual[field].sum(axis=1))
    res = {"season": season, "week": week, "bank": BANK, "K": KROWS, "field_mean": float(fs.mean()), "field_sd": float(fs.std()), "arms": {}}
    base_ids = None
    for name, lam, src in ARMS:
        pred = pred_from(src)
        b = L.plain_mean_book(frp, (pm + lam * pred)[keep], KROWS, max(1, int(0.5 * KROWS)), max(1, int(0.25 * KROWS)))
        a = np.asarray(candidate_actual(fr, b), dtype=float)
        rows = [[str(p["id"]) for p in lu.players] for lu in b]
        idset = [frozenset(r) for r in rows]
        if base_ids is None: base_ids = set(idset)
        ix = [[pos_of[i] for i in r] for r in rows]
        res["arms"][name] = {"lambda": lam, "source": src, "score": a.round(2).tolist(), "pct": (np.searchsorted(fs, a, side="left") / len(fs)).round(5).tolist(),
                             "shared_with_base": len(set(idset) & base_ids), "rows": rows,
                             "proj_sum": [round(float(pm[j].sum()), 3) for j in ix], "pred_own_sum": [round(float(pred[j].sum()), 3) for j in ix],
                             "real_own_sum": [round(float(oracle[j].sum()), 3) for j in ix]}
    json.dump(res, open(out, "w")); return out
if __name__ == "__main__":
    from multiprocessing import Pool
    got = hashlib.sha256(open(PREDS, "rb").read()).hexdigest()
    assert got == PREDS_SHA, got
    os.makedirs(OUT, exist_ok=True)
    rows = [json.loads(l)["result"] for l in open(WT + "/results/l18/results_bank1240.jsonl")]
    slates = sorted({(r["season"], r["week"]) for r in rows})
    with Pool(int(os.environ.get("WORKERS", "12"))) as p:
        for o in p.imap_unordered(one, slates): print("done", o, flush=True)
    print("ALL DONE", flush=True)
