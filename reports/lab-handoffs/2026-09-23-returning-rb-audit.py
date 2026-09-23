"""Audit of production's returning-lead-RB study (2301dd86): false returners, a 'lead stays out' placebo, eras, live def."""
import numpy as np, pandas as pd
d = pd.read_parquet("ceiling_panel.parquet"); q = pd.read_parquet("q_resid.parquet")[["pred", "resid"]]
a = d.join(q, how="inner"); a = a[a.was_active.astype(bool) & a.position.eq("RB")].copy()
act = d[d.was_active.astype(bool)][["gsis_id", "season", "week", "team", "position", "carry_share_l4"]]
key = set(zip(act.gsis_id, act.season, act.week)); tw = set(zip(act.season, act.team, act.week))
lead = act[act.position.eq("RB") & (act.carry_share_l4 >= 0.40)]
lead_rows = set(zip(lead.gsis_id, lead.season, lead.week))
a["played_prev"] = [(g, s, w - 1) in key for g, s, w in zip(a.gsis_id, a.season, a.week)]
a = a[a.played_prev].copy(); a["spiked"] = a.carry_share_jump.fillna(0) >= 0.10

def study_returns(require_before=True):
    m = {}
    for g, s, w, t in zip(lead.gsis_id, lead.season, lead.week, lead.team):
        if (g, s, w - 1) in key or (s, t, w - 1) not in tw:
            continue
        if require_before and not ((g, s, w - 2) in key or (g, s, w - 3) in key):
            continue
        m.setdefault((s, t, w), set()).add(g)
    return m

def stays_out():
    """Lead RB (cs_l4 >= .40 at his last active week W-2 or W-3) absent at W-1 AND at W; team played W-1 and W."""
    m = {}
    teams_by = {}
    for g, s, w, t in zip(act.gsis_id, act.season, act.week, act.team):
        teams_by[(g, s, w)] = t
    for g, s, w0 in lead_rows:
        t = teams_by[(g, s, w0)]
        for W in (w0 + 2, w0 + 3):
            gap = range(w0 + 1, W + 1)
            if all((g, s, x) not in key for x in gap) and all((s, t, x) in tw for x in gap):
                m.setdefault((s, t, W), set()).add(g)
    return m

def diff(sub, rset, label, seasons=None):
    sub = sub if seasons is None else sub[sub.season.isin(seasons)]
    rw = np.array([((s, t, w) in rset) and (g not in rset[(s, t, w)]) for s, t, w, g in zip(sub.season, sub.team, sub.week, sub.gsis_id)])
    r, o = sub.resid[rw], sub.resid[~rw]
    if len(r) < 5:
        print(f"  {label:44s} n_ret {len(r)} too few"); return
    se = np.sqrt(r.var() / len(r) + o.var() / len(o))
    per = sub.assign(rw=rw).groupby(["season", "rw"]).resid.mean().unstack()
    dd = (per[True] - per[False]).dropna() if True in per else pd.Series(dtype=float)
    print(f"  {label:44s} n_ret {len(r):4d}  diff {r.mean() - o.mean():+.2f} (se {se:.2f})  negative {int((dd < 0).sum())}/{len(dd)} seasons")

for name, rs in (("RETURN (study definition)", study_returns()), ("LIVE definition (no W-2/W-3 requirement)", study_returns(False)),
                 ("PLACEBO: lead STAYS OUT at W (no return)", stays_out())):
    print(f"\n{name}: {sum(len(v) for v in rs.values())} lead-weeks")
    for sl, sub in (("all RB teammates", a), ("spiked RB teammates", a[a.spiked])):
        diff(sub, rs, f"{sl} 2018-24")
        diff(sub, rs, f"{sl} 2022-24", (2022, 2023, 2024))
        diff(sub, rs, f"{sl} 2018-21", (2018, 2019, 2020, 2021))
R = study_returns()
pd.DataFrame([(s, t, w, g) for (s, t, w), gs in R.items() for g in gs], columns=["season", "team", "week", "gsis_id"]).to_parquet("rb_returners.parquet")
