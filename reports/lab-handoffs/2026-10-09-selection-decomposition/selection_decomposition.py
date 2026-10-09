"""(Committed 10-09 by the outside reviewer; run with the production venv, the money gate's private data in place.)
Where did our W1-4 lineups lose points against the field? Exact decomposition, per week:
  gap per lineup = real edge - model edge = sum_p (x_ours_p - x_field_p) * (real_p - proj_p)
x = average count per lineup (our entries vs the other entries of the SAME contests, weighted by our entries per contest).
proj = the T-70 frame's mean_projection (the model the book was built on); market = the frame's market_points; FP (W4 only).
Aggregates and public NFL names only; no ids, no dollars."""
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import moneygate_score as MS  # noqa: E402

cfg = MS.load_config()
ROWS = []
for w in (1, 2, 3, 4):
    W = MS.load_week(cfg, w)
    e = cfg["weeks"][str(w)]
    fr = pd.read_parquet(Path(e["t70_run"]) / "frame.parquet")
    fr["cn"] = fr.display_name.map(MS.canon)
    fr = fr[~fr.cn.duplicated(keep=False)].set_index("cn")
    excl = {str(k) for k in (e.get("reconcile_exclude") or [])}
    h = W.history
    xo, xf = defaultdict(float), defaultdict(float)
    n_ours = 0
    for cid in sorted(set(h.Contest_Key)):
        if cid in excl:
            continue
        fc = W.field[W.field.contest_id == cid]
        mine = fc[fc.entry_id.isin(W.ours)]
        oth = fc[~fc.entry_id.isin(W.ours) & (fc.names.map(len) == 9)]
        if not len(mine) or not len(oth):
            continue
        n = len(mine); n_ours += n
        for names in mine.names:
            for p in names:
                xo[p] += 1.0
        cnt = defaultdict(int)
        for names in oth.names:
            for p in names:
                cnt[p] += 1
        for p, c in cnt.items():
            xf[p] += n * c / len(oth)
    fpts = {k: v / 100.0 for k, v in W.fpts.items()}
    fp = {}
    if e.get("fp_proj_source"):
        f = pd.read_csv(e["fp_proj_source"]); fp = dict(zip(f.name.map(MS.canon), f.fp))
    for p in set(xo) | set(xf):
        if p not in fr.index or p not in fpts:
            continue
        r = fr.loc[p]
        ROWS.append({"week": w, "player": p, "pos": r.pos, "salary": float(r.salary), "proj": float(r.mean_projection),
                     "market": float(r.market_points) if pd.notna(r.market_points) else np.nan, "fp": fp.get(p, np.nan),
                     "real": fpts[p], "x_ours": xo.get(p, 0.0) / n_ours, "x_field": xf.get(p, 0.0) / n_ours})
    print(f"W{w}: our entries {n_ours}", flush=True)

D = pd.DataFrame(ROWS)
D["d"] = D.x_ours - D.x_field
D["err"] = D.real - D.proj
D.to_csv(Path.home() / "private" / "selection_decomp_w1_4.csv", index=False)


def tier_sal(s):
    return "<4k" if s < 4000 else "4-5.4k" if s < 5500 else "5.5-6.9k" if s < 7000 else "7k+"


def tier_own(o):
    return "<5%" if o < 0.05 else "5-15%" if o < 0.15 else "15-30%" if o < 0.30 else "30%+"


D["sal_t"] = D.salary.map(tier_sal); D["own_t"] = D.x_field.map(tier_own)
D["mm"] = D.proj - D.market
D["mm_t"] = np.where(D.market.isna(), "no market", np.where(D.mm > 1.5, "model > market +1.5", np.where(D.mm < -1.5, "model < market -1.5", "close")))
for w, g in D.groupby("week"):
    me = (g.d * g.proj).sum(); re_ = (g.d * g.real).sum(); mk = (g.d * g.market.fillna(g.proj)).sum()
    line = f"W{w}: model edge {me:+.1f}  real edge {re_:+.1f}  gap {re_ - me:+.1f}  market's edge {mk:+.1f}"
    if g.fp.notna().any():
        line += f"  FP's edge {(g.d * g.fp.fillna(g.proj)).sum():+.1f}"
    print(line)
print()
for key in ("pos", "sal_t", "own_t", "mm_t"):
    t = D.assign(c=D.d * D.err, mo=D.d * D.proj, rl=D.d * D.real).groupby(["week", key]).agg(gap=("c", "sum"), over=("d", lambda s: s[s > 0].sum()),
                                                                                       under=("d", lambda s: s[s < 0].sum())).round(2)
    print(f"== gap by {key} (points per lineup; over/under = players per lineup we held above/below the field)")
    print(t.unstack("week")["gap"].to_string())
    print()
g = D[D.week >= 2].assign(c=D.d * D.err)
top = g.groupby(["week", "player", "pos"]).agg(c=("c", "sum"), d=("d", "sum"), err=("err", "first"), proj=("proj", "first"), real=("real", "first"),
                                             own=("x_field", "first"), sal=("salary", "first"), mm=("mm", "first")).reset_index()
print("== the 15 biggest losses W2-4 (d = our extra exposure per lineup vs the field; err = real - model; mm = model - market)")
print(top.sort_values("c").head(15).round(2).to_string(index=False))
print("\n== the 8 biggest gains W2-4")
print(top.sort_values("c").tail(8).round(2).to_string(index=False))

# ---- concentration, the market check and the hindsight caps (the numbers in the study-89 prereg §1) ----
print()
for w, g in D.groupby("week"):
    print(f"W{w}: players in >= 40% of our entries {int((g.x_ours >= 0.40).sum())} (field {int((g.x_field >= 0.40).sum())}); "
          f">= 30% {int((g.x_ours >= 0.30).sum())} (field {int((g.x_field >= 0.30).sum())})")
M = D[D.market.notna()].assign(rm=lambda t: t.real - t.market)
for w, g in M.groupby("week"):
    over, under = g[g.d > 0.10], g[g.d < -0.05]
    print(f"W{w}: real - market per player: overweighted (d > +10 pts, n={len(over)}) {over.rm.mean():+.2f}; "
          f"underweighted (d < -5 pts, n={len(under)}) {under.rm.mean():+.2f}")
for pos, g in M.groupby("pos"):
    if len(g) > 20:
        print(f"{pos}: slope of (real - market) on our over-exposure {np.polyfit(g.d, g.rm, 1)[0]:+.1f} points per +100% (n={len(g)})")
for lab, ex_of in (("field ownership + 15 points", lambda g: np.clip(g.d - 0.15, 0, None)),
                   ("a flat 35% cap", lambda g: np.clip(g.x_ours - 0.35, 0, None))):
    out = []
    for w, g in D.groupby("week"):
        ex = ex_of(g); repl = np.average(g.real - g.proj, weights=g.x_field + 1e-12)
        out.append(f"W{w} {-(ex * ((g.real - g.proj) - repl)).sum():+.1f}")
    print(f"HINDSIGHT (the same weeks; not evidence) {lab}: " + ", ".join(out))
