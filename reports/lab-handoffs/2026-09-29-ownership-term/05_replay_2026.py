"""Fixed-book replay of the ownership term on the 2026 frames (Weeks 1-3), with the PATCHED production tool's own
functions (own_bonus, pmo_rows) and the Week-4 pinned lab clone. Scored with DraftKings' points and the real Millionaire
field. The model's ownership is rebuilt from pre-lock inputs; LineStar's is its recorded projection, fetched after the
fact (NOT provably pre-lock) -- so the blend rows are an upper bound and the model-only rows are the clean ones.
    PYTHONPATH=<pinned clone>/src python rehearse2026.py <patched scripts dir> <out dir>
"""
import json, os, re, sys, time
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, sys.argv[1]); OUT = Path(sys.argv[2]); OUT.mkdir(exist_ok=True)
import union_reselect as ur
S = Path(os.environ["DATA_DIR"])     # private data directory, outside the repo
MILLY = {1: 193028206, 2: 195648007, 3: 195905122}
RUN = {1: "w1run", 2: "w2run", 3: "w3z"}
K, XCAP, DCAP = 36, 18, 9
def norm(s):
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower()); return re.sub(r"[^a-z]", "", s)
pts_all = pd.read_parquet(S / "winners/own_pts.parquet")
ent = pd.read_parquet(S / "winners/entries_all.parquet", columns=["week", "contest_id", "points"])
res = []
for wk in (1, 2, 3):
    fr = pd.read_parquet(S / "own" / RUN[wk] / "frame.parquet").reset_index(drop=True)
    own = pd.read_parquet(S / "own" / f"own2026_w{wk}.parquet")
    gone = ur.unavailable_ids(fr, None)
    proj = dict(zip(fr.id.astype(str), pd.to_numeric(fr.mean_projection, errors="coerce")))
    pos = dict(zip(fr.id.astype(str), fr.pos.astype(str)))
    excl = gone | {i for i in proj if pos[i] in ur.SKILL and not (proj[i] >= 1.0)}
    p = pts_all[pts_all.week == wk].assign(key=lambda d: d.display_name.map(norm))
    fp = p.groupby("key").fpts.max(); ro = p.groupby("key").own.max()
    key_of = dict(zip(fr.id.astype(str), fr.name.map(norm)))
    actual = {i: float(fp.get(key_of[i], np.nan)) for i in key_of}
    realown = {i: float(ro.get(key_of[i], 0.0)) for i in key_of}
    field = np.sort(ent[(ent.week == wk) & (ent.contest_id.astype(str) == str(MILLY[wk]))].points.to_numpy(float))
    files = {}
    for col in ("pred_base", "pred_lag", "blend_base", "blend_lag", "own_proj"):
        d = own[["gsis_id", "dk_player_id", "display_name", "pos"]].assign(pred_own=own[col]).dropna(subset=["pred_own"])
        f = OUT / f"w{wk}_{col}.csv"; d.to_csv(f, index=False); files[col] = f
    # the realized ownership as a file too (diagnostic ceiling; never available before lock)
    d = fr[fr.pos.isin(ur.SKILL)][["id", "dk_player_id", "name", "pos"]].rename(columns={"id": "gsis_id", "name": "display_name"})
    d = d.assign(pred_own=[realown[i] for i in d.gsis_id.astype(str)]); f = OUT / f"w{wk}_realized.csv"; d.to_csv(f, index=False); files["realized"] = f
    arms = [("plain", None, 0.0), ("model_base 0.20", "pred_base", 0.2), ("model_lag 0.20", "pred_lag", 0.2),
            ("blend_base 0.10", "blend_base", 0.1), ("blend_base 0.20", "blend_base", 0.2), ("blend_base 0.30", "blend_base", 0.3),
            ("blend_lag 0.20", "blend_lag", 0.2), ("realized 0.20 (ceiling)", "realized", 0.2)]
    plain_rows = None
    for name, col, lam in arms:
        t0 = time.time()
        meta = {}
        if col is None:
            rows = ur.pmo_rows(fr, excl, K, 7, 4, 49_000, set(), exposure_cap=XCAP, dst_cap=DCAP); plain_rows = rows
        else:
            try:
                bonus, meta = ur.own_bonus(files[col], fr, excl, lam, 0.9 if col != "own_proj" else 0.0)
            except SystemExit as e:
                print(f"W{wk} {name}: {e}"); continue
            rows = ur.pmo_rows(fr, excl, K, 7, 4, 49_000, set(), exposure_cap=XCAP, dst_cap=DCAP, bonus=bonus)
        secs = time.time() - t0
        miss = sorted({key_of[i] for r in rows for i in r if not np.isfinite(actual[i])})
        sc = np.array([sum(0.0 if not np.isfinite(actual[i]) else actual[i] for i in r) for r in rows])
        pct = np.searchsorted(field, sc, side="left") / len(field)
        res.append({"week": wk, "arm": name, "rows": len(rows), "secs": round(secs, 1), "proj/row": round(float(np.mean([sum(proj[i] for i in r) for r in rows])), 2),
                    "real own/row": round(float(np.mean([sum(realown[i] for i in r if pos[i] in ur.SKILL) for r in rows])), 1),
                    "avg pts": round(float(sc.mean()), 2), "field avg": round(float(field.mean()), 2), "z": round(float((sc.mean() - field.mean()) / field.std()), 3),
                    "best": round(float(sc.max()), 1), ">=p80": int((pct >= 0.80).sum()), ">=p89": int((pct >= 0.89).sum()), ">=p95": int((pct >= 0.95).sum()), ">=p99": int((pct >= 0.99).sum()),
                    "top4 avg pct": round(float(pct[:4].mean()), 3), "shared w/ plain": len({frozenset(r) for r in rows} & {frozenset(r) for r in plain_rows}),
                    "coverage": meta.get("coverage_projected_5"), "unscored players": len(miss)})
        json.dump({"rows": rows, "score": sc.tolist(), "pct": pct.tolist()}, open(OUT / f"w{wk}_{name.replace(' ', '_').replace('(', '').replace(')', '')}.json", "w"))
        print(res[-1], flush=True)
pd.DataFrame(res).to_csv(OUT / "rehearsal_2026.csv", index=False)
