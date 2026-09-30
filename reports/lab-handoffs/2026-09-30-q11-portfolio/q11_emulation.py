"""Q11 part 1 (production, 2026-09-30; laptop design c3dc040f): same pool per week, three 150-row books, scored against
the real Millionaire field. Descriptive hindsight on W1 and W3 (W2 excluded: its pre-lock pool is not the entered build's).

  (a) top-mean, <= 7 shared (the Week-4 form's selector without the term)
  (b) exposure-target selection: greedy by mean under per-player / QB / DST caps, a max-shared limit and a band on the
      row's PRE-LOCK predicted ownership sum; the cap/limit/band setting is chosen from a small grid by distance to the
      top-100 heavy users' profile (F3 targets) computed from PRE-LOCK quantities only -- never from outcomes
  (c) (a) with the ownership term: mean + 0.20 x pre-lock predicted ownership sum (the armed Week-4 objective's form)

Pre-lock ownership (see prelock_own): W3 primary = the Saturday lag-model file; W1 primary = LineStar's recorded Main-slate
Thursday 09-10 own_shadow (latest generation, booster_own), the only stored W1 pre-lock prediction. Both are rescaled
so the slate total is 900% (nine roster slots), the realized scale on which the F3 target 130-140 was measured.
Realized scores/ownership come from B/common.py's tables (post-lock) and are used ONLY to score finished books.
Inputs live in ~/q11-study (private: the field holds DK user names); prints aggregates only.
"""
import itertools, json, os, sys, glob
import numpy as np, pandas as pd
os.environ.setdefault("OMP_NUM_THREADS", "1")
Q = os.path.expanduser("~/q11-study")
sys.path.insert(0, os.path.join(Q, "q", "B"))
import common as C  # noqa: E402

K = 150
RUNS_SPEC = [(1, "linestar"), (1, "shadow"), (3, "sets"), (3, "linestar")]   # primary: W1 linestar, W3 sets
TARGETS = dict(exp_top1=(0.50, 0.60), exp_top3=(0.45, 0.50), n_ge25=(7, 9), n_players=(90, 115), mean_overlap=(1.8, 2.4),
               overlap_ge6=(0.0, 0.03), qb_modal=(0.0, 0.25), own_pre=(130, 140))
SCALE = dict(exp_top1=0.1, exp_top3=0.05, n_ge25=2, n_players=15, mean_overlap=0.4, overlap_ge6=0.02, qb_modal=0.05, own_pre=10)


def prelock_own(week, f, source):
    """Predicted ownership % per frame row, rescaled to a 900% slate total. Sources:
    sets     W3 Saturday lag-model file (pre-lock)
    linestar LineStar's recorded Main-slate projection (archive; published before lock, NOT provably the pre-lock copy)
    shadow   W1 own_shadow 09-10 (pre-lock) -- stored as a WITHIN-POSITION share (each position sums to 1), so it is
             scaled by roster slots first (QB 1, RB 2, WR 3, TE 1, DST 1; FLEX spread by the same shares)"""
    if source == "sets":
        s = pd.read_csv(os.path.expanduser("~/week3-sunday/ownership_sets.csv"))
        m = dict(zip(s.dk_player_id.astype(str), s.pred_own.clip(lower=0)))
        o = np.array([m.get(str(x), 0.0) for x in f.dk_player_id], float)
    elif source == "linestar":
        sys.path.insert(0, "/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/scripts")
        import ownership_tabpfn_rows_2026 as R
        pid = {1: 407, 2: 408, 3: 409}[week]
        ls = R.linestar_slate(json.load(open(os.path.expanduser(f"~/.cache/linestar-2026/p{pid}.json"))))
        o = np.array([ls.get((R.ls_norm(n), p), 0.0) for n, p in zip(f.display_name, f.pos.astype(str).str.upper())], float)
    elif source == "shadow":
        sys.path.insert(0, "/home/erich/projects/nfl-predictions/src")
        from nfl_dfs.bq import query_df
        from nfl_dfs.config import settings as st
        x = query_df(f"""SELECT gsis_id, name, booster_own FROM `{st.predictions}.own_shadow` WHERE season=2026 AND week={int(week)}
                         AND generated_at = (SELECT MAX(generated_at) FROM `{st.predictions}.own_shadow` WHERE season=2026 AND week={int(week)})""")
        by_g = dict(zip(x.gsis_id.astype(str), x.booster_own)); by_n = dict(zip(x.name.astype(str), x.booster_own))
        o = np.array([by_g.get(str(g), by_n.get(str(n), 0.0)) for g, n in zip(f.gsis_id, f.display_name)], float)
        slots = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "DST": 1}
        o = np.nan_to_num(o) * np.array([slots.get(p, 0) for p in f.pos.astype(str)]) * 100.0
    else:
        raise ValueError(source)
    o = np.nan_to_num(np.clip(o, 0, None))
    return o * (900.0 / o.sum()), source, float((o > 0).mean())


def load(week):
    f = C.attach_realized(C.load_frame(C.RUNS[week]["t70"]), week)
    if week == 1:
        c = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(C.W1 + "/*-e7255e9/candidates.parquet"))]).drop_duplicates("players")
        src = "W1 union of the e7255e9 builds' candidates"
    else:
        c = pd.read_pickle(os.path.expanduser("~/week3-sunday/postmortem/cands_scored.pkl"))
        src = "W3 Saturday D12800 pool (cands_scored.pkl)"
    idx = {k: i for i, k in enumerate(f["id"])}
    keep = c.players.map(lambda s: all(p in idx for p in s.split(",")))
    c = c[keep].reset_index(drop=True)
    rix = np.array([[idx[p] for p in s.split(",")] for s in c.players])
    return f, rix, dict(pool=src, rows=int(len(c)), dropped_not_in_t70=int((~keep).sum()))


def select(order, rix, pos, K=K, max_shared=7, cap=None, qb_cap=None, dst_cap=None, own_row=None, band=None):
    chosen, sets = [], []
    cnt = {}
    for i in order:
        if band is not None and not (band[0] <= own_row[i] <= band[1]):
            continue
        row = rix[i]; s = set(row)
        if any(len(s & t) > max_shared for t in sets):
            continue
        if cap is not None or qb_cap is not None or dst_cap is not None:
            bad = False
            for p in row:
                lim = cap
                if pos[p] == "QB" and qb_cap is not None: lim = qb_cap
                if pos[p] == "DST" and dst_cap is not None: lim = dst_cap
                if lim is not None and cnt.get(p, 0) + 1 > lim * K:
                    bad = True; break
            if bad:
                continue
        chosen.append(i); sets.append(s)
        for p in row: cnt[p] = cnt.get(p, 0) + 1
        if len(chosen) >= K:
            break
    return np.array(chosen)


def profile(sel, rix, pos, own_pre, own_real=None):
    rows = rix[sel]; n = len(rows)
    cnt = pd.Series(rows.ravel()).value_counts() / n
    qb = pd.Series([p for r in rows for p in r if pos[p] == "QB"]).value_counts() / n
    sets = [set(r) for r in rows]
    pairs = np.array([len(a & b) for a, b in itertools.combinations(sets, 2)])
    d = dict(n=n, exp_top1=float(cnt.iloc[0]), exp_top3=float(cnt.iloc[:3].mean()), n_ge25=int((cnt >= .25).sum()),
             n_ge50=int((cnt >= .5).sum()), n_players=int(len(cnt)), mean_overlap=float(pairs.mean()), overlap_ge6=float((pairs >= 6).mean()),
             qb_modal=float(qb.iloc[0]), n_qb=int(len(qb)), own_pre=float(own_pre[rows].sum(1).mean()))
    if own_real is not None:
        d["own_real"] = float(own_real[rows].sum(1).mean())
    return d


def distance(p):
    return sum(max(0.0, lo - p[k], p[k] - hi) / SCALE[k] for k, (lo, hi) in TARGETS.items())


def score(sel, rix, R, fq):
    pts = R[rix[sel]].sum(1)
    qs = np.array(fq["qs"]); cash, top1 = qs[800], qs[990]
    best = pts.max()
    return dict(mean=float(pts.mean()), vs_field=float(pts.mean() - fq["mean"]), cash_share=float((pts >= cash).mean()),
                top1_share=float((pts >= top1).mean()), best=float(best), best_pct=float((qs >= best).mean() * 100),
                cash_line=float(cash), top1_line=float(top1))


def main():
    fqs = {int(r.week): dict(qs=list(r.qs), mean=float(r.mean)) for r in pd.read_pickle(os.path.join(Q, "q11", "field_quantiles.pkl")).itertuples()}
    out = {}
    for w, source in RUNS_SPEC:
        f, rix, meta = load(w)
        own_pre, own_src, own_cover = prelock_own(w, f, source)
        pos = f.pos.astype(str).to_numpy(); P = f.proj.to_numpy(float); R = f.realized.to_numpy(float); O = f.field_own.to_numpy(float)
        mean = P[rix].sum(1); orow = own_pre[rix].sum(1)
        books = {}
        books["a_top_mean"] = select(np.argsort(-mean, kind="stable"), rix, pos)
        books["c_mean_plus_0.20_own"] = select(np.argsort(-(mean + 0.20 * orow), kind="stable"), rix, pos)
        grid = []
        for cap in (0.35, 0.45, 0.55, 0.60):
            for m in (4, 5, 6):
                for band in (None, (115, 155), (125, 145)):
                    sel = select(np.argsort(-mean, kind="stable"), rix, pos, max_shared=m, cap=cap, qb_cap=0.25, dst_cap=0.30, own_row=orow, band=band)
                    if len(sel) < K:
                        grid.append(dict(cap=cap, max_shared=m, band=band, n=len(sel), dist=np.inf)); continue
                    p = profile(sel, rix, pos, own_pre)
                    grid.append(dict(cap=cap, max_shared=m, band=band, n=len(sel), dist=distance(p), sel=sel))
        best = min(grid, key=lambda g: (g["dist"], -g["cap"]))
        books["b_exposure_target"] = best["sel"]
        res = {"meta": meta, "own_pre_source": own_src, "own_pre_coverage_players": round(own_cover, 3),
               "b_setting": {k: best[k] for k in ("cap", "max_shared", "band", "dist")},
               "grid_feasible": sum(np.isfinite(g["dist"]) for g in grid), "grid": len(grid),
               "pool_mean_top": float(np.sort(mean)[-1]), "books": {}}
        for name, sel in books.items():
            p = profile(sel, rix, pos, own_pre, O); s = score(sel, rix, R, fqs[w])
            p["dist_to_targets"] = distance(p); p["proj_mean"] = float(mean[sel].mean())
            res["books"][name] = {"profile": {k: round(v, 3) if isinstance(v, float) else v for k, v in p.items()},
                                  "score": {k: round(v, 3) for k, v in s.items()}}
        out[f"W{w}-{source}"] = res
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__" and "--ablation" not in sys.argv:
    main()


def ablation():
    """Which of (b)'s constraints costs the points: each constraint alone on top of top-mean selection (<= 7 shared)."""
    fqs = {int(r.week): dict(qs=list(r.qs), mean=float(r.mean)) for r in pd.read_pickle(os.path.join(Q, "q11", "field_quantiles.pkl")).itertuples()}
    out = {}
    for w in (1, 3):
        f, rix, _ = load(w)
        pos = f.pos.astype(str).to_numpy(); P = f.proj.to_numpy(float); R = f.realized.to_numpy(float)
        mean = P[rix].sum(1); order = np.argsort(-mean, kind="stable")
        arms = {"top_mean": {}, "player_cap_0.55": dict(cap=0.55), "qb_cap_0.25": dict(qb_cap=0.25), "dst_cap_0.30": dict(dst_cap=0.30),
                "max_shared_6": dict(max_shared=6), "max_shared_5": dict(max_shared=5), "all_b": dict(cap=0.55, qb_cap=0.25, dst_cap=0.30, max_shared=6)}
        res = {}
        for name, kw in arms.items():
            kw = dict(kw); kw.setdefault("max_shared", 7)
            sel = select(order, rix, pos, **kw)
            s = score(sel, rix, R, fqs[w])
            res[name] = dict(n=len(sel), proj_mean=round(float(mean[sel].mean()), 2), mean=round(s["mean"], 2),
                             vs_field=round(s["vs_field"], 2), cash_share=round(s["cash_share"], 3), top1_share=round(s["top1_share"], 3))
        out[f"W{w}"] = res
    print(json.dumps(out, indent=1))


if __name__ == "__main__" and "--ablation" in sys.argv:
    ablation()
