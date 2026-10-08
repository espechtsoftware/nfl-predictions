# PRO METHODS, analysis B (2026 W1-4): beyond the market projection, which pre-lock data points do the regulars lean
# on (and the crowd), and which of them predicted points beyond the market? PRIVATE inputs; output is aggregates only.
#   tilt_reg  = regulars' pooled share - rest-of-field share (pp)      field = log field ownership (what the crowd did)
#   resid     = actual DK points - props (prop-covered players who played): the "beyond the market" outcome
# Each feature is z-scored within week x position (pool: >= 0.2% field-owned skill players) and fitted one at a time
# with week x position fixed effects and the props edge (props minus salary-implied, z) as the market control.
# SEs: game-cluster bootstrap (games resampled within week), 400 reps.
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path.home() / "private" / "pro-methods"
pan = pd.read_parquet(OUT / "panel.parquet")
for c in pan.columns:
    if pd.api.types.is_numeric_dtype(pan[c]) and not pd.api.types.is_bool_dtype(pan[c]):
        pan[c] = pan[c].astype(float)
d = pan[pan.pos.isin(["QB", "RB", "WR", "TE"]) & (pan.field_own >= 0.002)].copy()
d["wp"] = d.week.astype(str) + d.pos


def edge(df, col):
    out = pd.Series(np.nan, index=df.index)
    for _, g in df.groupby("wp"):
        ok = g[col].notna() & g.salary.notna()
        if ok.sum() < 6:
            continue
        b = np.polyfit(g.salary[ok] / 1000.0, g[col][ok], 1)
        r = g[col] - np.polyval(b, g.salary / 1000.0)
        out[g.index] = (r - r[ok].mean()) / r[ok].std()
    return out


d["e_props"] = edge(d, "props")
# position-matched matchup measures
d["opp_epa_pos"] = np.where(d.pos == "RB", d.opp_rush_epa, d.opp_pass_epa)
d["fp_ol_pos"] = np.where(d.pos == "RB", d.fp_ol_rush, d.fp_ol_pass)
d["allowed_l6_pos"] = np.select([d.pos == "QB", d.pos == "RB", d.pos == "WR", d.pos == "TE"],
                                [d.qb_fp_allowed_adj_l6, d.rb_fp_allowed_adj_l6, d.wr_fp_allowed_adj_l6, d.te_fp_allowed_adj_l6])
d["usage_l4"] = np.where(d.pos == "RB", d.carry_share_l4.fillna(0) + d.target_share_l4.fillna(0), d.target_share_l4)
d["usage_jump"] = np.where(d.pos == "RB", d.carry_share_jump.fillna(0) + d.target_share_jump.fillna(0), d.target_share_jump)
d["td_equity"] = np.where(d.pos == "RB", d.gl3_carry_share_l4, d.rz20_target_share_l4)
d["log_own"] = np.log(d.field_own.clip(lower=1e-3))
d["pts_per_k"] = d.props / (d.salary / 1000.0)
FEATS = {
    "recency: last week's DK points": "dk_w1", "recency: last week beat our projection": "beat_proj_w1",
    "recency: last week's ownership": "own_w1", "price: salary change since last week": "sal_change",
    "usage: target/carry share (4 wk)": "usage_l4", "usage: share jump (last vs 4 wk)": "usage_jump",
    "usage: snap share (4 wk)": "snap_share_l4", "usage: snap share jump": "snap_share_jump",
    "usage: FP route share (4 wk)": "fp_route_share_l4", "usage: FP route share jump": "fp_route_share_jump",
    "usage: air-yards share (4 wk)": "air_yards_share_l4", "usage: WOPR (4 wk)": "wopr_l4",
    "TD equity: red-zone / goal-line share": "td_equity", "TD equity: end-zone targets (4 wk)": "ez_targets_l4",
    "ceiling: DK points sd": "dk_points_std", "ceiling: aDOT (8 wk)": "adot_l8", "ceiling: deep targets (4 wk)": "deep_targets_l4",
    "game: team implied total": "implied_team_total", "game: game total": "game_total", "game: spread (+ = favoured)": "spread",
    "matchup: opp DK pts allowed to pos, 2025": "dvp25", "matchup: opp DK pts allowed to pos, 2026": "dvp26",
    "matchup: opp EPA allowed, 2026": "opp_epa_pos", "matchup: opp FP allowed adj (6 g)": "allowed_l6_pos",
    "matchup: FP coverage grade (WR/TE)": "fp_cov_grade", "matchup: FP O-line grade": "fp_ol_pos",
    "news: vacated team target share": "team_vacated_target_share", "news: Questionable tag": "questionable",
    "weather: wind mph": "wind_mph", "crowd: field ownership (log)": "log_own", "market value: props pts per $1k": "pts_per_k",
}
for lab, col in FEATS.items():
    z = d.groupby("wp")[col].transform(lambda x: (x - x.mean()) / x.std() if x.std() > 0 else x * 0)
    d[f"z::{lab}"] = z
d["tilt_reg"] = (d.exp_reg - d.exp_rest) * 100
d["tilt_top1"] = (d.exp_top1 - d.exp_rest) * 100
d["resid"] = d.actual - d.props
rng = np.random.default_rng(11)
games = d[["week", "game"]].drop_duplicates()


def coef(df, y, x, ctrl=True):
    ok = df[y].notna() & df[x].notna() & (df.e_props.notna() if ctrl else True)
    g = df[ok]
    if len(g) < 40:
        return np.nan, len(g)
    D = pd.get_dummies(g.wp, drop_first=False).astype(float).values
    X = np.column_stack([g[x].values] + ([g.e_props.values] if ctrl else []) + [D])
    b, *_ = np.linalg.lstsq(X, g[y].values, rcond=None)
    return b[0], len(g)


def boot(df, y, x, ctrl=True, reps=400):
    out = []
    gk = df.week.astype(str) + "|" + df.game
    for _ in range(reps):
        pick = []
        for w, gw in games.groupby("week"):
            pick += list((str(w) + "|" + gw.game.sample(len(gw), replace=True, random_state=rng.integers(1e9))).values)
        idx = np.concatenate([np.flatnonzero(gk.values == k) for k in pick])
        b, _ = coef(df.iloc[idx], y, x, ctrl)
        out.append(b)
    return np.nanstd(out)


rows = []
for lab in FEATS:
    x = f"z::{lab}"
    r = {"data point": lab}
    for y, nm in (("tilt_reg", "regulars tilt (pp)"), ("log_own", "crowd log-own"), ("resid", "pts beyond props")):
        if y == "log_own" and lab.startswith("crowd"):
            r[nm] = np.nan; continue
        b, n = coef(d, y, x)
        se = boot(d, y, x, reps=200 if y != "resid" else 400)
        r[nm] = b; r[nm + " z"] = b / se if se > 0 else np.nan; r[nm + " n"] = n
    rows.append(r)
R = pd.DataFrame(rows)
pd.set_option("display.width", 250)
cols = ["data point", "regulars tilt (pp)", "regulars tilt (pp) z", "crowd log-own", "crowd log-own z", "pts beyond props",
        "pts beyond props z", "pts beyond props n"]
print("2026 W1-4, each data point alone + props edge + week x position: per 1 sd (z = game-cluster bootstrap)")
print(R[cols].round(2).to_string(index=False))
R.to_csv(OUT / "b_drivers_2026.csv", index=False)

# W4 only: the same, but with FP as the market (resid_fp = actual - FP, control = FP edge)
w4 = d[d.week == 4].copy()
w4["e_fp"] = edge(w4, "fp"); w4["resid_fp"] = w4.actual - w4.fp
w4["e_props"] = w4.e_fp      # reuse coef() with the FP edge as the control
rows = []
for lab in FEATS:
    x = f"z::{lab}"
    b1, n1 = coef(w4, "tilt_reg", x); b2, n2 = coef(w4, "resid_fp", x)
    rows.append({"data point": lab, "W4 regulars tilt beyond FP (pp)": b1, "W4 pts beyond FP": b2, "n": n2})
print("\nW4 only, FP as the market (no SEs: one week, ~140 players; descriptive)")
print(pd.DataFrame(rows).round(2).to_string(index=False))
