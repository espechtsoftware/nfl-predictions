"""What the Week-4 ENTERED main book (capped plain-mean optimizer + ownership term) would have scored in Weeks 1-3,
next to the corpus audit's pool rates: the book's rate at the real Millionaire field's top 50/20/10/5/1/0.1% lines."""
import json, os, re, sys, time
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, os.environ["PROD_SCRIPTS"])   # <production checkout>/scripts (union_reselect.py)
import union_reselect as ur
S = Path(os.environ["DATA_DIR"])   # private: winners/ (own_pts, entries_all) and own/ (archived run dirs, own2026 files)
MILLY = {1: 193028206, 2: 195648007, 3: 195905122}; RUN = {1: "w1run", 2: "w2run", 3: "w3z"}
K = int(sys.argv[1]) if len(sys.argv) > 1 else 105; XCAP, DCAP = max(1, int(0.5 * K)), max(1, int(0.25 * K))
LINES = (0.5, 0.2, 0.1, 0.05, 0.01, 0.001)
def norm(s):
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower()); return re.sub(r"[^a-z]", "", s)
pts = pd.read_parquet(S / "winners/own_pts.parquet"); ent = pd.read_parquet(S / "winners/entries_all.parquet", columns=["week", "contest_id", "points"])
out = []
for wk in (1, 2, 3):
    fr = pd.read_parquet(S / "own" / RUN[wk] / "frame.parquet").reset_index(drop=True)
    own = pd.read_parquet(S / "own" / f"own2026_w{wk}.parquet")
    gone = ur.unavailable_ids(fr, None)
    proj = dict(zip(fr.id.astype(str), pd.to_numeric(fr.mean_projection, errors="coerce"))); pos = dict(zip(fr.id.astype(str), fr.pos.astype(str)))
    excl = gone | {i for i in proj if pos[i] in ur.SKILL and not (proj[i] >= 1.0)}
    p = pts[pts.week == wk].assign(key=lambda d: d.display_name.map(norm)); fp = p.groupby("key").fpts.max()
    key_of = dict(zip(fr.id.astype(str), fr.name.map(norm))); actual = {i: float(fp.get(key_of[i], 0.0)) for i in key_of}
    field = np.sort(ent[(ent.week == wk) & (ent.contest_id.astype(str) == str(MILLY[wk]))].points.to_numpy(float))
    cuts = {l: float(np.quantile(field, 1 - l)) for l in LINES}
    for name, col, lam in (("plain capped book", None, 0.0), ("+ lag file at 0.10 (Sunday's likely form)", "pred_lag", 0.10),
                           ("+ blend at 0.20", "blend_lag", 0.20)):
        bonus = {}
        if col:
            f = S / "own" / f"tmp_w{wk}_{col}.csv"
            own[["gsis_id", "dk_player_id", "display_name", "pos"]].assign(pred_own=own[col]).dropna(subset=["pred_own"]).to_csv(f, index=False)
            bonus, _ = ur.own_bonus(f, fr, excl, lam, 0.9)
        t0 = time.time()
        rows = ur.pmo_rows(fr, excl, K, 7, 4, 49_000, set(), exposure_cap=XCAP, dst_cap=DCAP, bonus=bonus or None)
        sc = np.array([sum(actual[i] for i in r) for r in rows])
        rec = {"week": wk, "book": name, "rows": len(rows), "secs": round(time.time() - t0), "book avg": round(sc.mean(), 1), "field avg": round(field.mean(), 1)}
        for l in LINES:
            rec[f"top {l:.1%}".replace(".0%", "%")] = round(float((sc >= cuts[l]).mean() / l), 2)
        rec["best"] = round(float(sc.max()), 1); rec["winner"] = round(float(field.max()), 1)
        out.append(rec); print(rec, flush=True)
pd.DataFrame(out).to_csv(S / "own" / f"entered_design_2026_K{K}.csv", index=False)
