"""R2(a): replicate the outside-the-box review's section 2.4 (crowd information vs recency-chasing) on OUR point-in-time data.

Plan `reports/2026-09-25-plan-from-outside-the-box-review.md` §1: "the kill test for R2". The review used LineStar's
projections (whose pre-lock status cannot be proven); this re-run uses the lab/production point-in-time replay panel
(`nfl_predictions.slate_player_features`, panel 20260811-pitclean-e80-k1-a12ab31) and `nfl_raw.contest_ownership` (the
largest Sunday Millionaire per week, 2022-2025 = up to 72 weeks). It follows the review's c2 script test for test where our
data allow (T1, T4, T5, T6); T2/T3 (LineStar's projected ownership, drift) have no counterpart here.

Rows: skill players (QB/RB/WR/TE) on the slate with projection PP >= 4; outcome tests on players who played (a weekly_stats
row). PP = `mean_projection` (PRIMARY: the replay's served mean); sensitivity: PP = `model_points_pre` (model only; the
2023-24 snapshot blends some one-market prices into mean_projection). Residual = actual - PP. Excess actual ownership
e_act = within-slate OLS residual of log(own + 0.1) on log PP, log salary, value (PP / salary x 1000) and position dummies.
prev_surprise = last week's (actual - PP) for the same player (same season, week - 1, if he was on that week's panel).
Recency split: within slate, OLS of e_act on prev_surprise; own_recency = fitted, own_other = e_act - fitted.
Statistic: per-slate Spearman, mean over slates, t = mean / (sd / sqrt(n slates)), slates with >= 25 rows.

DECISION CRITERIA (written before this script was first run; the kill test for R2):
  R2 HOLDS iff all three:
    (i)   T4  last-week surprise -> excess actual ownership: mean rho > 0 with t >= 3   (the crowd chases)
    (ii)  T6a recency part of excess ownership -> residual: |t| < 2                    (chasing carries no information)
    (iii) T6b the rest of excess ownership -> residual: mean rho > 0 with t >= 3       (the crowd is informed otherwise)
  R2 is KILLED if (i) fails or (iii) fails, or if (ii) shows the recency part informative (t >= 2).
  The primary PP decides; the sensitivity PP is co-reported and a disagreement is disclosed.

    PYTHONPATH=src python reports/lab-handoffs/2026-09-25-r2a-recency-replication.py
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
from scipy import stats

from nfl_dfs.bq import query_df

P = "nfl-predictions-503414"
PANEL = "20260811-pitclean-e80-k1-a12ab31"


def norm(s: object) -> str:
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower())
    return re.sub(r"[^a-z]", "", s)


def load() -> pd.DataFrame:
    own = query_df(f"""
        WITH c AS (
          SELECT season, week, contest_id, ANY_VALUE(contest_name) nm,
                 SAFE_CAST(REGEXP_EXTRACT(ANY_VALUE(contest_name), r"\\[(\\d+) entries") AS INT64) ent
          FROM `{P}.nfl_raw.contest_ownership` WHERE season BETWEEN 2022 AND 2025 GROUP BY 1,2,3),
        pick AS (
          SELECT season, week, ARRAY_AGG(STRUCT(contest_id, ent) ORDER BY ent DESC LIMIT 1)[OFFSET(0)] AS p
          FROM c WHERE REGEXP_CONTAINS(nm, r"Fantasy Football Millionaire") AND NOT REGEXP_CONTAINS(nm, r"\\(Thu\\)|MEGA|\\$555")
          GROUP BY 1,2)
        SELECT o.season, o.week, o.display_name, MAX(o.pct_drafted) pct
        FROM `{P}.nfl_raw.contest_ownership` o JOIN pick ON o.season = pick.season AND o.week = pick.week
             AND o.contest_id = pick.p.contest_id GROUP BY 1,2,3""")
    own["key"] = own.display_name.map(norm)
    own = own.groupby(["season", "week", "key"], as_index=False).pct.max()
    spf = query_df(f"""
        SELECT season, week, gsis_id, name, pos, salary, mean_projection, model_points_pre, actual
        FROM `{P}.nfl_predictions.slate_player_features`
        WHERE panel_run_id = "{PANEL}" AND season BETWEEN 2022 AND 2025 AND gsis_id IS NOT NULL""")
    spf = spf.sort_values(["season", "week", "gsis_id", "salary"], kind="stable").drop_duplicates(["season", "week", "gsis_id"])
    played = query_df(f"""SELECT DISTINCT season, week, player_id gsis_id FROM `{P}.nfl_raw.weekly_stats`
                          WHERE season BETWEEN 2022 AND 2025 AND season_type = 'REG'""")
    played["played"] = True
    d = spf.merge(played, on=["season", "week", "gsis_id"], how="left")
    d["played"] = d.played.fillna(False).astype(bool)
    d["key"] = d.name.map(norm)
    have = set(map(tuple, own[["season", "week"]].drop_duplicates().to_numpy()))
    d = d[[(s, w) in have for s, w in zip(d.season, d.week)]]
    d = d.merge(own, on=["season", "week", "key"], how="left")
    d["own"] = d.pct.fillna(0.0)
    return d


def resid_within(g: pd.DataFrame, y: str, cols: list[str]) -> np.ndarray:
    X = np.column_stack([np.ones(len(g))] + [g[c].to_numpy(float) for c in cols]
                        + [(g.pos == p).astype(float).to_numpy() for p in ("RB", "WR", "TE")])
    beta, *_ = np.linalg.lstsq(X, g[y].to_numpy(float), rcond=None)
    return g[y].to_numpy(float) - X @ beta


def slate_corr(d: pd.DataFrame, x: str, y: str, min_n: int = 25) -> tuple[float, float, int, int, str]:
    out = np.array([stats.spearmanr(g[x], g[y])[0] for _, g in d.groupby(["season", "week"])
                    if len(g[[x, y]].dropna()) >= min_n])
    out = out[np.isfinite(out)]
    t = out.mean() / (out.std(ddof=1) / np.sqrt(len(out)))
    return float(out.mean()), float(t), int((out > 0).sum()), len(out), f"mean rho {out.mean():+.3f}  t {t:+.1f}  positive {int((out > 0).sum())}/{len(out)}"


def run(d: pd.DataFrame, pp_col: str) -> dict:
    x = d.copy()
    x["pp"] = pd.to_numeric(x[pp_col], errors="coerce")
    prev = x[["season", "week", "gsis_id", "pp", "actual"]].copy()
    prev["prev_surprise"] = pd.to_numeric(prev.actual, errors="coerce") - prev.pp
    prev["week"] = prev.week + 1
    x = x.merge(prev[["season", "week", "gsis_id", "prev_surprise"]], on=["season", "week", "gsis_id"], how="left")
    sk = x[x.pos.isin(["QB", "RB", "WR", "TE"]) & (x.pp >= 4) & x.salary.notna()].copy()
    sk["resid"] = pd.to_numeric(sk.actual, errors="coerce") - sk.pp
    sk["lo_act"] = np.log(sk.own + 0.1); sk["lpp"] = np.log(sk.pp); sk["lsal"] = np.log(sk.salary)
    sk["val"] = sk.pp / sk.salary * 1000
    parts = []
    for _, g in sk.groupby(["season", "week"]):
        g = g.copy(); g["e_act"] = resid_within(g, "lo_act", ["lpp", "lsal", "val"]); parts.append(g)
    sk = pd.concat(parts)
    pl = sk[sk.played & sk.resid.notna()]
    print(f"--- PP = {pp_col}: skill rows {len(sk)}, played {len(pl)}, slates {sk.groupby(['season', 'week']).ngroups}; "
          f"corr(PP, actual | played) {np.corrcoef(pl.pp, pl.actual.astype(float))[0, 1]:.3f}")
    res = {}
    res["T1"] = slate_corr(pl, "e_act", "resid"); print("[T1] excess actual ownership -> residual:", res["T1"][4])
    r = pl.dropna(subset=["prev_surprise"])
    res["T4"] = slate_corr(r, "prev_surprise", "e_act"); print("[T4] last-week surprise -> excess actual ownership:", res["T4"][4])
    res["T5"] = slate_corr(r, "prev_surprise", "resid"); print("[T5] last-week surprise -> this week's residual:", res["T5"][4])
    parts = []
    for _, g in r.groupby(["season", "week"]):
        if len(g) < 25:
            continue
        g = g.copy(); X = np.column_stack([np.ones(len(g)), g.prev_surprise.to_numpy(float)])
        b, *_ = np.linalg.lstsq(X, g.e_act.to_numpy(float), rcond=None)
        g["own_recency"] = X @ b; g["own_other"] = g.e_act - g.own_recency; parts.append(g)
    r2 = pd.concat(parts)
    res["T6a"] = slate_corr(r2, "own_recency", "resid"); print("[T6a] recency part of excess ownership -> residual:", res["T6a"][4])
    res["T6b"] = slate_corr(r2, "own_other", "resid"); print("[T6b] the rest of excess ownership -> residual:", res["T6b"][4])
    for s, g in r2.groupby("season"):
        print(f"      {s}: T6a {slate_corr(g, 'own_recency', 'resid')[4]} | T6b {slate_corr(g, 'own_other', 'resid')[4]}")
    pl = pl.copy()
    pl["q"] = pl.groupby(["season", "week"]).e_act.transform(lambda s: pd.qcut(s.rank(method="first"), 5, labels=False))
    print("     residual by within-slate quintile of excess actual ownership:",
          " ".join(f"{v:+.2f}" for v in pl.groupby("q").resid.mean()))
    return res


def verdict(res: dict) -> str:
    i = res["T4"][0] > 0 and res["T4"][1] >= 3
    ii = abs(res["T6a"][1]) < 2
    iii = res["T6b"][0] > 0 and res["T6b"][1] >= 3
    return (f"(i) crowd chases: {'PASS' if i else 'FAIL'}; (ii) recency part uninformative: {'PASS' if ii else 'FAIL'}; "
            f"(iii) rest informative: {'PASS' if iii else 'FAIL'} -> R2 {'HOLDS' if (i and ii and iii) else 'KILLED'}")


if __name__ == "__main__":
    data = load()
    primary = run(data, "mean_projection")
    print("VERDICT (primary, PP = mean_projection):", verdict(primary))
    sens = run(data, "model_points_pre")
    print("co-report (sensitivity, PP = model_points_pre):", verdict(sens))
