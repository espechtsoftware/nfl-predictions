"""External review, 2026-09-22: does the field know something our projection does not, and what does
it cost our lineups?  Reads the CSVs written by pull_inputs.py.

    python crowd_and_gap.py <inputs_dir>

Sections (all numbers in reports/2026-09-22-external-review-suggestions.md come from this output):
  1  crowd information: within-slate partial Spearman between "excess ownership" (log Millionaire
     ownership not explained by our projection, salary, position) and our residual
     (actual - projection), players who PLAYED with projection >= 5; 2022-2025, one value per slate
  2  LineStar pre-game projection / projected ownership as a pre-lock proxy for that information
  3  the replay panel's own_est ownership column, for comparison
  4  replay books (80 entries/slate, replay_lineups_pitk1) vs the field's ownership-weighted
     average lineup: projected, realized, did-not-play slots, surprise among players who played
  5  the same crowd test against the SERVED 2026 projections (weeks 1-2)
Ownership is post-lock: sections 1, 4 and 5 measure information, they are not live inputs.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

IN = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
SK = ["QB", "RB", "WR", "TE"]


def norm(s: str) -> str:
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower())
    return re.sub(r"[^a-z]", "", s)


def csv(name: str) -> pd.DataFrame:
    return pd.read_csv(IN / f"{name}.csv")


# ---------------------------------------------------------------- inputs
own = csv("milly_own").assign(key=lambda x: x.display_name.map(norm))
own = own.groupby(["season", "week", "key"], as_index=False).pct_drafted.max()
spf = csv("spf").assign(key=lambda x: x.name.map(norm))
played = csv("played")
PLAYED = set(zip(played.season, played.week, played.player_id.astype(str)))
spf["played"] = [(s, w, str(g)) in PLAYED for s, w, g in zip(spf.season, spf.week, spf.gsis_id)]
inj = csv("injuries")
sch = csv("schedules")
slot_rows = [{"season": r.season, "week": r.week, "team": t, "hour": int(str(r.gametime)[:2]), "weekday": r.weekday}
             for r in sch.itertuples() for t in (r.home_team, r.away_team)]
slots = pd.DataFrame(slot_rows)
ls_path = IN / "linestar.csv"
ls = pd.read_csv(ls_path) if ls_path.exists() else None

d = spf[spf.pos.isin(SK) & spf.salary.notna() & spf.mean_projection.notna()].drop_duplicates(["season", "week", "key"])
d = d.merge(own, on=["season", "week", "key"], how="left")
d["own"] = d.pct_drafted.fillna(0.0)
d = d.merge(inj, on=["season", "week", "gsis_id"], how="left")
d["listed"] = d.report_status.notna() | (d.practice_status.notna() & ~d.practice_status.fillna("").str.startswith("Full"))
d = d.merge(slots, on=["season", "week", "team"], how="left")
d["slot"] = np.where(d.hour == 13, "early", np.where(d.hour.between(14, 16), "late", "other"))
d["sal"] = d.salary / 1000.0
if ls is not None:
    ls = ls[ls.ls_pp > 0].assign(key=lambda x: x.name.map(norm))
    ls = ls.sort_values("ls_proj_own", na_position="first").drop_duplicates(["season", "week", "key"], keep="last")
    d = d.merge(ls[["season", "week", "key", "ls_pp", "ls_proj_own"]], on=["season", "week", "key"], how="left")
a = d[d.played & (d.mean_projection >= 5)].copy()          # analysis rows


def partial(g: pd.DataFrame, signal, controls=(), quad=False):
    X = pd.get_dummies(g.pos, drop_first=True, dtype=float)
    X["proj"] = g.mean_projection
    X["sal"] = g.sal
    if quad:
        X["proj2"] = g.mean_projection ** 2
        X["ps"] = X.proj * X.sal
    for c in controls:
        X[c] = g[c].fillna(g[c].mean())
    X["c"] = 1.0
    A = X.to_numpy(float)
    v = signal(g)
    ex = v - A @ np.linalg.lstsq(A, v, rcond=None)[0]
    r = (g.actual - g.mean_projection).to_numpy(float)
    r2 = r - A @ np.linalg.lstsq(A, r, rcond=None)[0]
    top, bot = ex >= np.quantile(ex, .8), ex <= np.quantile(ex, .2)
    return stats.spearmanr(ex, r2).correlation, r2[top].mean() - r2[bot].mean()


def report(sub: pd.DataFrame, label: str, signal, controls=(), quad=False) -> None:
    res = [partial(g, signal, controls, quad) for _, g in sub.groupby(["season", "week"]) if len(g) > 30]
    rho = np.array([x[0] for x in res])
    gap = np.array([x[1] for x in res])
    t = rho.mean() / (rho.std(ddof=1) / np.sqrt(len(rho)))
    print(f"  {label:<64} rho {rho.mean():+.3f}  t {t:+5.1f}  positive {int((rho > 0).sum()):>2}/{len(rho):<2}"
          f"  top-minus-bottom quintile {gap.mean():+.2f} pts")


ACT = lambda g: np.log(g.own + 0.1).to_numpy(float)                        # noqa: E731
print(f"rows: skill {len(d)}, analysis (played, projection >= 5) {len(a)}, slates {a.groupby(['season', 'week']).ngroups}")

print("\n1. Crowd information in ACTUAL Millionaire ownership, beyond our replay projection")
report(a, "baseline (position, projection, salary)", ACT)
report(a, "+ quadratic terms and implied team total", ACT, controls=("implied_team_total",), quad=True)
report(a[~a.listed], "healthy only (not on the injury report)", ACT, quad=True)
m = a[(a.season >= 2023) & a.market_points.notna() & a.model_points_pre.notna()]
report(m, "2023-25 prop-covered, controlling market and model components", ACT,
       controls=("market_points", "model_points_pre", "implied_team_total", "proj_p90"), quad=True)
print(f"  (same rows: Spearman(market minus model component, actual minus blend) "
      f"{stats.spearmanr(m.market_points - m.model_points_pre, m.actual - m.mean_projection).correlation:+.3f})")
for sl in ("early", "late"):
    report(a[a.slot == sl], f"{sl} games, quadratic", ACT, quad=True)
for y in sorted(a.season.unique()):
    report(a[a.season == y], f"season {y}", ACT)

if ls is not None:
    print("\n2. LineStar (public, pre-game) projection and projected ownership")
    b = a[a.ls_pp.notna()].copy()
    b["ls_proj_own"] = b.ls_proj_own.fillna(0.0)
    for lab, c in (("ours (replay mean_projection)", "mean_projection"), ("LineStar PP", "ls_pp")):
        print(f"  {lab:<30} corr with actual {np.corrcoef(b[c], b.actual)[0, 1]:.3f}  MAE {np.abs(b[c] - b.actual).mean():.3f}")
    for y in (2023, 2024, 2025):
        tr, te = b[b.season < y], b[b.season == y]
        dm = (tr.ls_pp - tr.mean_projection).to_numpy(); dt = (tr.actual - tr.mean_projection).to_numpy()
        w = float(np.clip(dm @ dt / (dm @ dm), 0, 1))
        pred = te.mean_projection + w * (te.ls_pp - te.mean_projection)
        print(f"  walk-forward {y}: LineStar weight {w:.2f}; MAE ours {np.abs(te.mean_projection - te.actual).mean():.3f}"
              f" -> blend {np.abs(pred - te.actual).mean():.3f}")
    r = [stats.spearmanr(g.ls_proj_own, g.own).correlation for _, g in b.groupby(["season", "week"]) if (g.ls_proj_own > 0).sum() > 20]
    print(f"  within-slate Spearman(LineStar projected ownership, actual Millionaire ownership): {np.nanmean(r):.3f}")
    PO = lambda g: np.log(g.ls_proj_own + 0.1).to_numpy(float)              # noqa: E731
    PP = lambda g: g.ls_pp.to_numpy(float)                                  # noqa: E731
    report(b, "ACTUAL ownership excess (same rows)", ACT, quad=True)
    report(b, "LineStar PROJECTED ownership excess (pre-game)", PO, quad=True)
    report(b, "LineStar projected-points excess (pre-game)", PP, quad=True)
    report(b, "ACTUAL ownership excess after controlling both LineStar signals", ACT, controls=("ls_pp", "ls_proj_own"), quad=True)
    for sl in ("early", "late"):
        report(b[b.slot == sl], f"[{sl}] LineStar projected-points excess", PP, quad=True)
        report(b[b.slot == sl], f"[{sl}] ACTUAL excess after LineStar controls", ACT, controls=("ls_pp", "ls_proj_own"), quad=True)

print("\n3. The replay panel's own_est column vs actual ownership")
r = [stats.spearmanr(g.own_est, g.own).correlation for _, g in a.groupby(["season", "week"]) if len(g) > 30]
r2 = [stats.spearmanr(g.mean_projection / g.salary, g.own).correlation for _, g in a.groupby(["season", "week"]) if len(g) > 30]
print(f"  within-slate Spearman(own_est, actual): {np.nanmean(r):.3f}   (our points per dollar vs actual: {np.nanmean(r2):.3f})")

print("\n4. Replay books vs the field's average lineup (8 skill slots per lineup)")
rl = csv("replay_books").assign(key=lambda x: x.player.map(norm))
f_all = spf[spf.pos.isin(SK)].drop_duplicates(["season", "week", "key"]).copy()
f_all["surprise"] = f_all.actual - f_all.mean_projection
if ls is not None:
    f_all = f_all.merge(ls[["season", "week", "key", "ls_pp"]], on=["season", "week", "key"], how="left")
    f_all["ls_minus_ours"] = f_all.ls_pp - f_all.mean_projection
else:
    f_all["ls_minus_ours"] = np.nan
rows, pos_rows = [], []
for (s, w), bk in rl[rl.pos.isin(SK)].groupby(["season", "week"]):
    f = f_all[(f_all.season == s) & (f_all.week == w)].set_index("key")
    o = own[(own.season == s) & (own.week == w)].set_index("key")
    if o.empty:
        continue
    n = bk.entry_ix.nunique()
    bj = bk.join(f[["mean_projection", "actual", "played", "surprise", "ls_minus_ours", "salary"]], on="key", rsuffix="_f")
    fo = o.join(f[["mean_projection", "actual", "played", "surprise", "ls_minus_ours", "salary", "pos"]], how="inner")
    wt = fo.pct_drafted / 100.0
    sc = 8.0 / wt.sum()                                  # rescale matched skill ownership mass to 8 slots
    pb, pf = bj.played.astype(bool), fo.played.astype(bool)
    rows.append({
        "season": s,
        "book_proj": bj.mean_projection.sum() / n, "field_proj": (wt * fo.mean_projection).sum() * sc,
        "book_real": bj.actual_f.sum() / n, "field_real": (wt * fo.actual).sum() * sc,
        "book_dead": (~pb).sum() / n, "field_dead": (wt * ~pf).sum() * sc,
        "book_sur": bj.surprise[pb].sum() / n, "field_sur": (wt * fo.surprise)[pf].sum() * sc,
        "book_dis": bj.ls_minus_ours[pb].fillna(0).sum() / n, "field_dis": (wt * fo.ls_minus_ours.fillna(0))[pf].sum() * sc,
    })
    for p in SK:
        mb, mf = (bj.pos == p) & pb, (fo.pos == p) & pf
        pos_rows.append({"group": p, "book_slots": mb.sum() / n, "book_sur": bj.surprise[mb].sum() / n,
                         "field_slots": wt[mf].sum() * sc, "field_sur": (wt * fo.surprise)[mf].sum() * sc})
    for lo, hi, lab in ((0, 4500, "salary < 4.5k"), (4500, 6500, "salary 4.5-6.5k"), (6500, 99999, "salary >= 6.5k")):
        mb = (bj.salary_f >= lo) & (bj.salary_f < hi) & pb
        mf = (fo.salary >= lo) & (fo.salary < hi) & pf
        pos_rows.append({"group": lab, "book_slots": mb.sum() / n, "book_sur": bj.surprise[mb].sum() / n,
                         "field_slots": wt[mf].sum() * sc, "field_sur": (wt * fo.surprise)[mf].sum() * sc})
R = pd.DataFrame(rows)


def line(c1: str, c2: str, lab: str) -> None:
    g = R[c1] - R[c2]
    t = g.mean() / (g.std(ddof=1) / np.sqrt(len(g)))
    print(f"  {lab:<46} book {R[c1].mean():7.2f}  field {R[c2].mean():7.2f}  book-minus-field {g.mean():+6.2f}"
          f"  (t {t:+5.1f}; book lower in {int((g < 0).sum())}/{len(g)})")


print(f"  slates {len(R)}")
line("book_proj", "field_proj", "projected by our replay model")
line("book_real", "field_real", "realized")
line("book_sur", "field_sur", "realized minus projection, players who played")
line("book_dis", "field_dis", "LineStar minus our projection, players who played")
print(f"  did-not-play skill slots per lineup: book {R.book_dead.mean():.3f}  field {R.field_dead.mean():.3f}")
print(f"  share of the played-player gap matched by LineStar disagreement at weight 0.48: "
      f"{0.48 * (R.book_dis - R.field_dis).mean() / (R.book_sur - R.field_sur).mean():.0%}")
P = pd.DataFrame(pos_rows).groupby("group").mean()
P["book_per_slot"] = P.book_sur / P.book_slots
P["field_per_slot"] = P.field_sur / P.field_slots
print("  per slot, players who played (realized minus our projection):")
print(P[["book_slots", "field_slots", "book_per_slot", "field_per_slot"]].round(2).to_string())

print("\n5. The same crowd test against the SERVED 2026 projections (last run before lock)")
lp = csv("live_proj_2026").assign(key=lambda x: x.display_name.map(norm))
lo_ = csv("milly_own_2026").assign(key=lambda x: x.display_name.map(norm))
dk = csv("dk_points_2026")
dkp = dk.set_index(["week", "player_id"]).dk
L = lp.merge(lo_[["week", "key", "own", "fpts"]], on=["week", "key"], how="left")
L = L[L.position.isin(SK) & L.salary.notna()].copy()
L["played"] = [(2026, w, str(g)) in PLAYED for w, g in zip(L.week, L.gsis_id)]
L["actual"] = [o if pd.notna(o) else dkp.get((w, str(g)), 0.0) for o, w, g in zip(L.fpts, L.week, L.gsis_id)]
L["own"] = L.own.fillna(0.0)
L = L[L.played & (L.proj_points >= 5)].rename(columns={"position": "pos", "proj_points": "mean_projection"})
L["sal"] = L.salary / 1000.0
L = L.merge(slots[slots.season == 2026].drop(columns="season"), on=["week", "team"], how="left")
for w, g in L.groupby("week"):
    rho, gap = partial(g, ACT, quad=True)
    print(f"  2026 week {w}: n {len(g)}  partial rho {rho:+.3f}  top-minus-bottom quintile {gap:+.2f} pts")
    for sl in ("early", "late"):
        gg = g[g.hour.eq(13)] if sl == "early" else g[g.hour.between(14, 16)]
        if len(gg) > 30:
            rho, gap = partial(gg, ACT)
            print(f"      {sl:<5} n {len(gg):>3}  partial rho {rho:+.3f}")
