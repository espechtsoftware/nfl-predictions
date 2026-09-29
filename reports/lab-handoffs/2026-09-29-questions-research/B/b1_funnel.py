"""B1 funnel + D1 Saturday-vs-T-70 (projection-error split). Realized = DK fpts (contest_ownership) with nflverse fallback."""
from common import *
import sys
out = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); out.append(s)

for wk in (1, 2, 3):
    R = RUNS[wk]; cash = R["cash"]
    src_run = R["final"] if wk == 1 else R["sat"]
    fs = attach_realized(load_frame(R["sat"]), wk)
    cs, rs = load_cands(R["sat"], fs)
    st = lineup_stats(rs, fs)
    st["fam"] = cs.fam.values
    P(f"\n=== WEEK {wk}: Saturday pool {os.path.basename(R['sat'])}, {len(cs)} candidates; cash line (Milly p80) {cash} ===")
    P("realized source for frame rows:", fs.real_src.value_counts().to_dict(), "| players with no record and proj>3:", int(((fs.real_src=='none')&(fs.proj>3)).sum()))
    K = {1: 80, 2: 97, 3: 144}[wk]
    # stage 1: best lineup our projections could build
    i_top = int(np.argmax(st.proj.values)); lev = np.where(st.fam.values == "lev")[0]
    i_opt = lev[int(np.argmax(st.proj_t.values[lev]))] if len(lev) else i_top
    rows = []
    rows.append(("pool top-1 by projected mean (proj sum)", st.proj[i_top], st.realized[i_top], 1))
    rows.append(("optimizer best (lev argmax of proj_tourney)", st.proj[i_opt], st.realized[i_opt], 1))
    sel = topk_by_mean(rs, st.proj.values, K)
    rows.append((f"top-{K} by projected mean, overlap<=7", st.proj.values[sel].mean(), st.realized.values[sel].mean(), len(sel)))
    for fam in ("lev", "boom"):
        m = st.fam.values == fam
        if m.any(): rows.append((f"pool batch {fam}", st.proj.values[m].mean(), st.realized.values[m].mean(), int(m.sum())))
    rows.append(("pool all", st.proj.mean(), st.realized.mean(), len(st)))
    bk = cs.book_rank.notna().values
    rows.append(("delivered expected-max book (book_rank, pre-vetting)", st.proj.values[bk].mean(), st.realized.values[bk].mean(), int(bk.sum())))
    # entered book, valued on its source frame
    fe = attach_realized(load_frame(src_run), wk)
    er = entered_rows(wk, fe)
    se = lineup_stats(er, fe)
    rows.append((f"ENTERED book ({os.path.basename(src_run)} frame)", se.proj.mean(), se.realized.mean(), len(se)))
    # field: projected via Saturday-frame proj by display_name
    fd = field_sample(wk)
    pmap = dict(zip(fs.display_name.astype(str), fs.proj.astype(float)))
    def psum(names):
        v = [pmap.get(n, np.nan) for n in names]; return np.nan if any(np.isnan(v)) else float(np.sum(v))
    fd["proj"] = fd.names.map(psum)
    unm = fd.proj.isna().mean()
    rnd = fd[~fd.top1]; top = fd[fd.top1]
    rows.append(("FIELD mean (Millionaire; projected from 2% sample)", rnd.proj.mean(), FIELD[wk]["mean"], len(rnd)))
    rows.append(("FIELD top 1% (exact realized; projected from all top-1% rows)", top.proj.mean(), FIELD[wk]["top1"], len(top)))
    P(f"field lineups with an unmatched name (dropped from projected mean): {100*unm:.1f}%")
    P(f"{'stage':<62}{'projected':>10}{'realized':>10}{'error':>9}{'n':>7}")
    for name, pj, rl, n in rows:
        P(f"{name:<62}{pj:>10.1f}{rl:>10.1f}{rl-pj:>+9.1f}{n:>7}")
    # share above cash
    P(f"share above cash: pool {100*(st.realized>=cash).mean():.1f}%  lev {100*(st.realized[st.fam=='lev']>=cash).mean():.1f}%  boom {100*(st.realized[st.fam=='boom']>=cash).mean():.1f}%  top-K-mean {100*(st.realized.values[sel]>=cash).mean():.1f}%  entered {100*(se.realized>=cash).mean():.1f}%  field ~20%")
    P(f"entered book: best {se.realized.max():.1f}; pool best {st.realized.max():.1f}; top-K-mean best {st.realized.values[sel].max():.1f}")
    # projected-mean quintiles of the pool -> realized (does our projection rank our own pool?)
    q = pd.qcut(st.proj, 5, labels=False, duplicates="drop")
    g = st.groupby(q).agg(proj=("proj","mean"), realized=("realized","mean"), n=("proj","size"))
    P("pool by projected-mean quintile (low->high): " + "; ".join(f"Q{int(k)+1} proj {r.proj:.1f} real {r.realized:.1f}" for k, r in g.iterrows()))
    P(f"corr(proj sum, realized) over pool: {np.corrcoef(st.proj, st.realized)[0,1]:+.3f}; corr(sel_mean, realized): {np.corrcoef(cs.sel_mean, st.realized)[0,1]:+.3f}")

    # ---- D1: Saturday vs T-70 projections ----
    P(f"\n--- D1 week {wk}: Saturday vs T-70 projections ---")
    runs = [("Saturday", R["sat"]), ("Sunday 09:10", R["sun910"]), ("T-70", R["t70"])] + ([("final 11:04", R["final"])] if wk == 1 else [])
    frames = {n: attach_realized(load_frame(r), wk) for n, r in runs}
    base = frames["Saturday"][["id", "display_name", "pos", "salary", "proj", "status", "realized"]].rename(columns={"proj": "proj_sat", "status": "status_sat"})
    t70 = frames["T-70"][["id", "proj", "status"]].rename(columns={"proj": "proj_t70", "status": "status_t70"})
    m = base.merge(t70, on="id", how="outer")
    m["proj_sat"] = m.proj_sat.fillna(0.0); m["proj_t70"] = m.proj_t70.fillna(0.0)
    used = np.zeros(len(fs), bool); used[np.unique(rs)] = True
    m["used"] = m.id.isin(fs.id[used])
    mm = m[m.used].copy()
    for lab, col in (("Saturday", "proj_sat"), ("T-70", "proj_t70")):
        e = mm.realized - mm[col]
        played = mm.realized > 0
        P(f"{lab:<9} over {len(mm)} pool players: MAE {e.abs().mean():.2f}  bias {e.mean():+.2f} | played only ({played.sum()}): MAE {e[played].abs().mean():.2f} bias {e[played].mean():+.2f} | zero-scorers with proj>3: {int(((mm.realized==0)&(mm[col]>3)).sum())} carrying {mm.loc[(mm.realized==0)&(mm[col]>3), col].sum():.0f} projected pts")
    mm["dproj"] = mm.proj_t70 - mm.proj_sat
    mv = mm.reindex(mm.dproj.abs().sort_values(ascending=False).index).head(12)
    P("largest movers Sat->T-70 (proj_sat -> proj_t70 | realized | status sat/t70):")
    for _, r in mv.iterrows():
        P(f"   {r.display_name:<24}{r.pos:<4}${int(r.salary):<6}{r.proj_sat:6.1f} -> {r.proj_t70:6.1f}  real {r.realized:5.1f}  {r.status_sat}/{r.status_t70}")
    P(f"players moved >=1.0: {int((mm.dproj.abs()>=1).sum())} of {len(mm)}; moved >=3.0: {int((mm.dproj.abs()>=3).sum())}; mean |move| among players who played: {mm.loc[mm.realized>0,'dproj'].abs().mean():.2f}")
    # best available book under each projection set (top-K by mean, overlap<=7)
    P("best available book (top-K by mean, overlap<=7): pool x projection -> projected mean / realized mean / above cash")
    pt = dict(zip(m.id, m.proj_t70)); ps = dict(zip(m.id, m.proj_sat))
    Psat = fs.id.map(ps).fillna(0).to_numpy(float); Pt70 = fs.id.map(pt).fillna(0).to_numpy(float)
    combos = [("Saturday pool x Saturday proj", rs, Psat, fs), ("Saturday pool x T-70 proj", rs, Pt70, fs)]
    for name, run in runs[1:]:
        fr = frames[name]; cr, rr = load_cands(run, fr)
        combos.append((f"{name} pool ({len(cr)}) x its own proj", rr, fr.proj.to_numpy(float), fr))
    for name, rx, pv, fr in combos:
        pj = pv[rx].sum(1); rl = fr.realized.to_numpy(float)[rx].sum(1)
        s = topk_by_mean(rx, pj, K)
        P(f"   {name:<40} proj {pj[s].mean():6.1f}  real {rl[s].mean():6.1f}  err {rl[s].mean()-pj[s].mean():+6.1f}  above cash {100*(rl[s]>=cash).mean():4.0f}%  row1 real {rl[s[0]]:.1f}")
open(os.path.join(HERE, "b1_funnel.out"), "w").write("\n".join(out))
