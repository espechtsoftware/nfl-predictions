"""Reproduce production's returning-teammate diff, then (c) a lagged placebo and (d) 2022-24 only."""
import numpy as np, pandas as pd
d = pd.read_parquet("ceiling_panel.parquet"); q = pd.read_parquet("q_resid.parquet")[["pred", "resid"]]
a = d.join(q, how="inner"); a = a[a.was_active.astype(bool) & a.position.isin(["WR", "TE", "RB"])].copy()
act = d[d.was_active.astype(bool)][["gsis_id", "season", "week", "team", "position", "target_share_l4"]]
key = set(zip(act.gsis_id, act.season, act.week)); teamweeks = set(zip(act.season, act.team, act.week))
a["played_prev"] = [(g, s, w - 1) in key for g, s, w in zip(a.gsis_id, a.season, a.week)]
a = a[a.played_prev].copy(); a["spiked"] = a.target_share_jump.fillna(0) >= 0.05

def returners(lag):
    """lag 1 = production's definition (absent W-1, back at W). lag 2 = PLACEBO: absent W-2, back at W-1, active W."""
    top = act[act.position.isin(["WR", "TE", "RB"]) & (act.target_share_l4 >= 0.18)]
    out = {}
    for g, s, w, t in zip(top.gsis_id, top.season, top.week, top.team):
        if lag == 1:
            ok = ((g, s, w - 1) not in key and ((g, s, w - 2) in key or (g, s, w - 3) in key) and (s, t, w - 1) in teamweeks)
        else:
            ok = ((g, s, w - 1) in key and (g, s, w - 2) not in key and ((g, s, w - 3) in key or (g, s, w - 4) in key)
                  and (s, t, w - 2) in teamweeks and not ((g, s, w) in key and False))
        if ok:
            out.setdefault((s, t, w), set()).add(g)
    return out

def diff(sub, rset, label, seasons=None):
    sub = sub if seasons is None else sub[sub.season.isin(seasons)]
    rw = np.array([((s, t, w) in rset) and (g not in rset[(s, t, w)]) for s, t, w, g in zip(sub.season, sub.team, sub.week, sub.gsis_id)])
    r, o = sub.resid[rw], sub.resid[~rw]
    se = np.sqrt(r.var() / len(r) + o.var() / len(o))
    per = sub.assign(rw=rw).groupby(["season", "rw"]).resid.mean().unstack()
    dd = (per[True] - per[False]).dropna()
    print(f"  {label:48s} n_ret {len(r):5d}  diff {r.mean() - o.mean():+.2f} (se {se:.2f})  negative {int((dd < 0).sum())}/{len(dd)} seasons")

for lag, name in ((1, "RETURN at W (production)"), (2, "PLACEBO: returned at W-1 instead")):
    rs = returners(lag)
    print(f"\n{name}: {sum(len(v) for v in rs.values())} returner-weeks")
    for sub_label, sub in (("all teammates", a), ("spiked teammates", a[a.spiked]), ("spiked WRs", a[a.spiked & a.position.eq("WR")])):
        diff(sub, rs, f"{sub_label} 2018-24")
        diff(sub, rs, f"{sub_label} 2022-24 only", seasons=(2022, 2023, 2024))
        diff(sub, rs, f"{sub_label} 2018-21 only", seasons=(2018, 2019, 2020, 2021))

# live definition: no "active W-2 or W-3" requirement (cascade_adjust.returning_teammate_deltas)
top = act[act.position.isin(["WR", "TE", "RB"]) & (act.target_share_l4 >= 0.18)]
live, extra = {}, {}
for g, s, w, t in zip(top.gsis_id, top.season, top.week, top.team):
    if (g, s, w - 1) not in key and (s, t, w - 1) in teamweeks:
        live.setdefault((s, t, w), set()).add(g)
        if not ((g, s, w - 2) in key or (g, s, w - 3) in key):
            extra.setdefault((s, t, w), set()).add(g)
print(f"\nLIVE definition: {sum(len(v) for v in live.values())} returner-weeks; of which {sum(len(v) for v in extra.values())} "
      f"are long absences the study excluded")
for sub_label, sub in (("all teammates", a), ("spiked teammates", a[a.spiked])):
    diff(sub, live, f"LIVE def: {sub_label} 2018-24")
    diff(sub, extra, f"EXTRA (long absence only): {sub_label}")
