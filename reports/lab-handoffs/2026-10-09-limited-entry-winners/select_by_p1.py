"""The operator 10-09 ("Yes do that"): in each W1-4 limited-entry contest (4444 / 555 / 333 / FFWC / $20-Milly satellites),
rank OUR union candidate pool (the lineups our process generated pre-lock) by (a) projected points -- what we do -- and (b) the
model's chance of finishing 1st (and top 3) against that contest's REAL field, scored by the week's T-70 sims (incumbent +
corrected hsim, 20,000 sims; the calibration's machinery), take as many lineups as we entered there, and compare their REAL
finishes (real DK points; the money gate's place(): DK's tie rule; our real entries removed from the field).
Also: the pool's best possible lineup (did the pool hold a winner at all?).
Selection uses pre-lock sims only; the REAL field's rosters are used to compute the chance of 1st (disclosed: a best case for
any field model -- live, the field is projected). Outcomes are read only for the evaluation. Private outputs stay here."""
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import moneygate_score as MS  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze import group  # noqa: E402

BANKS = ("incumbent_player_scores.npy", "corrected_hsim_player_scores.npy")
CHUNK = 1500
rows_out = []
pool_out = []
for w in (1, 2, 3, 4):
    W = MS.load_week(cfg := MS.load_config(), w) if w == 1 else MS.load_week(cfg, w)
    e = cfg["weeks"][str(w)]
    run = Path(e["t70_run"])
    fr = pd.read_parquet(run / "frame.parquet").reset_index(drop=True)
    bank = np.concatenate([np.load(run / b, mmap_mode="r") for b in BANKS], axis=1).astype(np.float32)   # players x 20k
    if bank.shape[0] != len(fr):
        raise SystemExit(f"W{w}: bank rows != frame rows")
    S = bank.shape[1]
    row_of_id = {str(i): k for k, i in enumerate(fr["id"].astype(str))}
    cn = fr.display_name.map(MS.canon)
    dup = set(cn[cn.duplicated(keep=False)])
    row_of_name = {n: k for k, n in enumerate(cn) if n not in dup}
    proj = pd.to_numeric(fr.mean_projection, errors="coerce").fillna(0.0).to_numpy(float)
    name_of_row = dict(enumerate(cn))
    fpts = {k: v / 100.0 for k, v in W.fpts.items()}
    real = np.array([fpts.get(name_of_row[k], np.nan) for k in range(len(fr))])
    cand_dir = Path(e.get("entered_union") or e["t70_run"])
    cands = pd.read_parquet(cand_dir / "candidates.parquet")
    seen, C = set(), []
    for players in cands.players.astype(str):
        r = [row_of_id.get(p.strip()) for p in players.split(",")]
        if len(r) != 9 or any(x is None for x in r):
            continue
        key = frozenset(r)
        if key in seen:
            continue
        seen.add(key); C.append(sorted(r))
    C = np.array(C, dtype=np.int64)
    c_proj = proj[C].sum(axis=1)
    c_real_ok = ~np.isnan(real[C]).any(axis=1)
    c_real = np.where(c_real_ok, np.nan_to_num(real[C]).sum(axis=1), np.nan)
    # the contests
    names_by_cid = dict(zip(W.history.Contest_Key, W.history.Entry))
    contests = []
    for cid in sorted(set(W.history.Contest_Key)):
        nm = (W.details.get(cid, {}) or {}).get("name") or names_by_cid.get(cid, "?")
        g = group(nm)
        if g is None:
            continue
        fc = W.field[(W.field.contest_id == cid) & (W.field.names.map(len) == 9)]
        oth = fc[~fc.entry_id.isin(W.ours)]
        k_ours = int((W.history.Contest_Key == cid).sum())
        if len(oth) < 5 or k_ours < 1:
            continue
        fr_rows = np.array([[row_of_name.get(n, -1) for n in names] for names in oth.names], dtype=np.int64)
        known = (fr_rows >= 0).all(axis=1)
        top = np.full((3, S), -np.inf, np.float32)                 # the field's top 3 per sim, built in chunks
        kr = fr_rows[known]
        for f0 in range(0, len(kr), 300):
            sc = np.zeros((len(kr[f0:f0 + 300]), S), np.float32)
            for j in range(9):
                sc += bank[kr[f0:f0 + 300, j]]
            top = -np.sort(-np.vstack([top, sc]), axis=0)[:3]
        fmax, f3 = top[0], top[2] if np.isfinite(top[2]).all() else top[0]
        mine = fc[fc.entry_id.isin(W.ours)]
        lad = MS.Ladder.from_details(W.details[cid]) if cid in W.details else None
        contests.append({"cid": cid, "name": nm, "group": g, "k": k_ours, "n": len(fc), "fmax": fmax, "f3": f3,
                         "unknown": float((~known).mean()), "others_sorted": W.others_sorted(cid), "lad": lad,
                         "ours_pts": [MS.lineup_points(list(nn), W.fpts, True)[0] for nn in mine.names]})
    if not contests:
        continue
    p1 = {c["cid"]: np.zeros(len(C)) for c in contests}
    p3 = {c["cid"]: np.zeros(len(C)) for c in contests}
    for s0 in range(0, len(C), CHUNK):
        Cc = C[s0:s0 + CHUNK]
        sc = np.zeros((len(Cc), S), np.float32)
        for j in range(9):
            sc += bank[Cc[:, j]]
        for c in contests:
            p1[c["cid"]][s0:s0 + CHUNK] = (sc > c["fmax"][None, :]).mean(axis=1)
            p3[c["cid"]][s0:s0 + CHUNK] = (sc > c["f3"][None, :]).mean(axis=1)
    for c in contests:
        k = c["k"]
        def evaluate(idx, label):
            pts = np.round(np.nan_to_num(c_real[idx]) * 100).astype(np.int64)
            res = MS.place(pts, c["others_sorted"], c["lad"]) if c["lad"] is not None else None
            ranks = res["rank"] if res is not None else np.array([1 + int((c["others_sorted"] > p).sum()) for p in pts])
            pct = 100.0 * np.searchsorted(c["others_sorted"], pts, "left") / max(len(c["others_sorted"]), 1)
            rows_out.append({"week": w, "group": c["group"], "contest": c["name"], "cid": c["cid"], "n": c["n"], "k": k,
                             "rule": label, "real_pts_mean": float(np.mean(pts) / 100), "best_rank": int(ranks.min()),
                             "pct_mean": float(pct.mean()), "top3": int((ranks <= 3).sum()), "first": int((ranks == 1).sum()),
                             "cash": int(((res["cash"] + res["ticket"]) > 0).sum()) if res is not None else None,
                             "unknown_field": c["unknown"]})
        ok = np.where(c_real_ok)[0]
        by_proj = ok[np.argsort(-c_proj[ok], kind="stable")[:k]]
        by_p1 = ok[np.lexsort((-c_proj[ok], -p1[c["cid"]][ok]))[:k]]
        by_p3 = ok[np.lexsort((-c_proj[ok], -p3[c["cid"]][ok]))[:k]]
        evaluate(by_proj, "projection"); evaluate(by_p1, "P(1st)"); evaluate(by_p3, "P(top 3)")
        best = ok[np.argsort(-c_real[ok])[:1]]
        evaluate(best, "pool's best (hindsight)")
        # our actual entries
        pts = np.array(c["ours_pts"], dtype=np.int64)
        res = MS.place(pts, c["others_sorted"], c["lad"]) if c["lad"] is not None else None
        if res is not None:
            pct = 100.0 * np.searchsorted(c["others_sorted"], pts, "left") / max(len(c["others_sorted"]), 1)
            rows_out.append({"week": w, "group": c["group"], "contest": c["name"], "cid": c["cid"], "n": c["n"], "k": k, "rule": "ours (entered)",
                             "real_pts_mean": float(pts.mean() / 100), "best_rank": int(res["rank"].min()), "pct_mean": float(pct.mean()),
                             "top3": int((res["rank"] <= 3).sum()), "first": int((res["rank"] == 1).sum()),
                             "cash": int(((res["cash"] + res["ticket"]) > 0).sum()), "unknown_field": c["unknown"]})
        pool_out.append({"week": w, "cid": c["cid"], "pool": len(C), "p1_max": float(p1[c["cid"]].max()),
                         "p1_of_proj_top": float(p1[c["cid"]][by_proj].mean())})
    print(f"W{w}: pool {len(C)} lineups, contests {len(contests)}", flush=True)
R = pd.DataFrame(rows_out)
R.to_csv((Path.home() / "private" / "limited-entry-winners" / "select_by_p1.csv"), index=False)
pd.DataFrame(pool_out).to_csv((Path.home() / "private" / "limited-entry-winners" / "select_by_p1_pool.csv"), index=False)
pd.set_option("display.width", 220)
order = ["ours (entered)", "projection", "P(1st)", "P(top 3)", "pool's best (hindsight)"]
for g, gd in R.groupby("group"):
    t = gd.groupby("rule").agg(contests=("cid", "nunique"), lineups=("k", "sum"), real_pts=("real_pts_mean", "mean"),
                               finish_pct=("pct_mean", "mean"), top3=("top3", "sum"), first=("first", "sum"), cash=("cash", "sum")).reindex(order)
    print(f"\n== {g}"); print(t.round(2).to_string())
t = R.groupby(["week", "rule"]).agg(finish_pct=("pct_mean", "mean"), top3=("top3", "sum"), first=("first", "sum")).unstack("rule")
print("\n== by week (every group)"); print(t.round(1).to_string())
