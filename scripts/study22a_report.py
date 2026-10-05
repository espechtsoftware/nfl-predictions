"""Study 22a frozen reader: does the served projection miss in five pre-declared directions?

Preregistration: reports/2026-10-05-prereg-study22a-residual-calibration.md (design frozen at 551f29af). Class C.

    python scripts/study22a_report.py --panel-run-id ID --census     # OUTCOME-BLIND support census (run before reading)
    python scripts/study22a_report.py --panel-run-id ID              # the read (B 20,000, seed 20261005)

Input: nfl_predictions.slate_player_features rows WHERE panel_run_id = ID AND research_eligible, seasons 2022-2025,
QB/RB/WR/TE. The census reads identities, salaries, projections and the PRESENCE of `actual` (never its value); the
read prints an input fingerprint (sha256 over the sorted analysis rows) so the cross-party re-run proves it read the
same rows. The reader validates no hash of itself, so no repair override is needed (frozen-chain rule 3).
"""
from __future__ import annotations

import argparse
import hashlib
import sys

import numpy as np
import pandas as pd

SEASONS = (2022, 2023, 2024, 2025)
TOP_N = {"QB": 24, "RB": 48, "WR": 72, "TE": 24}
H2_WEEKS = (2, 3, 4, 5)
SUPPORT_FLOOR = 500                     # eligible non-null rows per season, per hypothesis
B_FROZEN, SEED = 20_000, 20261005
ALPHA = 0.05 / 5                        # Bonferroni over five hypotheses
LEVEL_TEXT = "99% interval"             # must match the prereg's wording (tests assert it)
FIX = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LA"}
HYP = {  # key: (label, predicted sign)
    "h1": ("H1 last season's defence vs position", +1),
    "h2": ("H2 early-season defence vs position (weeks 2-5)", -1),
    "h3": ("H3 most recent played game's DK points", -1),
    "h4": ("H4 salary change (salary_delta_wow)", -1),
    "h5": ("H5 top value decile: mean miss minus the rest (DK points)", -1),
}
DK_SQL = """passing_yards*0.04 + passing_tds*4 - passing_interceptions + IF(passing_yards>=300,3,0)
  + rushing_yards*0.1 + rushing_tds*6 + IF(rushing_yards>=100,3,0)
  + receptions + receiving_yards*0.1 + receiving_tds*6 + IF(receiving_yards>=100,3,0)
  - IFNULL(fumbles_lost_total,0) + 2*(IFNULL(passing_2pt_conversions,0)+IFNULL(rushing_2pt_conversions,0)
  + IFNULL(receiving_2pt_conversions,0)) + 6*IFNULL(special_teams_tds,0)"""


# ---------------------------------------------------------------- loading (BigQuery)
def load(panel_run_id: str, *, outcomes: bool):
    from google.cloud import bigquery
    from nfl_dfs.config import settings
    if settings.project == "nfl-dfs-prod":       # O-31: the config default is not this warehouse
        raise SystemExit("set GCP_PROJECT (the warehouse project) before reading")
    c = bigquery.Client(project=settings.project)
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("p", "STRING", panel_run_id)])
    actual = "actual" if outcomes else "actual IS NOT NULL AS has_actual"
    panel = c.query(f"""SELECT season, week, gsis_id, pos, team, opp, salary, mean_projection, model_points_pre, {actual}
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @p AND research_eligible AND season BETWEEN 2022 AND 2025
          AND pos IN ('QB','RB','WR','TE')""", job_config=cfg).to_dataframe()
    ws = c.query(f"""SELECT season, week, player_id, position pos, team, opponent_team opp, {DK_SQL} dk
        FROM `{settings.raw}.weekly_stats` WHERE season BETWEEN 2021 AND 2025 AND season_type='REG'""").to_dataframe()
    sal = c.query(f"""SELECT season, week, gsis_id, ANY_VALUE(salary_delta_wow) salary_delta_wow
        FROM `{settings.features}.dk_salary_week` WHERE season BETWEEN 2022 AND 2025 GROUP BY 1,2,3""").to_dataframe()
    return panel, ws, sal


# ---------------------------------------------------------------- pure logic (tested offline)
def eligible(panel: pd.DataFrame) -> pd.DataFrame:
    d = panel[panel.season.isin(SEASONS) & panel.pos.isin(list(TOP_N))].copy()
    dup = d.duplicated(["season", "week", "gsis_id"], keep=False)
    if dup.any():
        raise SystemExit(f"FAIL-CLOSED: {int(dup.sum())} rows share a (season, week, gsis_id) identity in the panel")
    has_actual = d["actual"].notna() if "actual" in d else d["has_actual"].astype(bool)
    d = d[(pd.to_numeric(d.salary, errors="coerce") > 0) & d.mean_projection.notna() & has_actual].copy()
    d["rank"] = d.groupby(["season", "week", "pos"]).mean_projection.rank(ascending=False, method="first")
    d = d[d["rank"] <= d.pos.map(TOP_N)].drop(columns="rank")
    for col in ("team", "opp"):
        d[col] = d[col].replace(FIX)
    return d.reset_index(drop=True)


def add_predictors(d: pd.DataFrame, ws: pd.DataFrame, sal: pd.DataFrame) -> pd.DataFrame:
    d = d.copy(); ws = ws.copy()
    for col in ("team", "opp"):
        ws[col] = ws[col].replace(FIX)
    per_game = ws.groupby(["season", "opp", "pos", "week"]).dk.sum().reset_index()        # DK points allowed per game
    prior = per_game.groupby(["season", "opp", "pos"]).dk.mean()
    d["h1"] = [prior.get((s - 1, o, p), np.nan) for s, o, p in zip(d.season, d.opp, d.pos)]
    h2 = []
    for s, w, o, p in zip(d.season, d.week, d.opp, d.pos):
        if w not in H2_WEEKS:
            h2.append(np.nan); continue
        g = per_game[(per_game.season == s) & (per_game.week < w) & (per_game.opp == o) & (per_game.pos == p)]
        h2.append(g.dk.mean() if len(g) else np.nan)
    d["h2"] = h2
    wsp = ws.sort_values("week")
    last = {}
    for (s, pid), g in wsp.groupby(["season", "player_id"]):
        last[(s, pid)] = (g.week.to_numpy(), g.dk.to_numpy())
    h3 = []
    for s, w, pid in zip(d.season, d.week, d.gsis_id):
        wk = last.get((s, pid))
        if wk is None:
            h3.append(np.nan); continue
        i = np.searchsorted(wk[0], w) - 1                  # the most recent played game before week W
        h3.append(float(wk[1][i]) if i >= 0 else np.nan)
    d["h3"] = h3
    sd = sal.set_index(["season", "week", "gsis_id"]).salary_delta_wow
    d["h4"] = [sd.get((s, w, g), np.nan) for s, w, g in zip(d.season, d.week, d.gsis_id)]
    for base, col in (("mean_projection", "h5"), ("model_points_pre", "h5_model")):
        v = pd.to_numeric(d[base], errors="coerce") / (pd.to_numeric(d.salary) / 1000)
        q = v.groupby([d.season, d.week, d.pos]).transform(lambda x: x.quantile(0.9))
        d[col] = np.where(v.notna(), (v >= q).astype(float), np.nan)
    return d


def census(d: pd.DataFrame) -> tuple[str, dict]:
    lines = ["STUDY 22a SUPPORT CENSUS (outcome-blind: identities, predictors, eligibility; never the value of actual)"]
    t = d.groupby(["season", "pos"]).size().unstack(fill_value=0)
    lines.append("eligible rows by season x position:\n" + t.to_string())
    support = {}
    for h in ("h1", "h2", "h3", "h4", "h5"):
        n = d[d[h].notna()].groupby("season").size().reindex(SEASONS, fill_value=0)
        support[h] = bool((n >= SUPPORT_FLOOR).all())
        lines.append(f"{HYP[h][0]}: non-null per season {n.to_dict()} -> "
                     f"{'SUPPORTED' if support[h] else 'UNSUPPORTED (below ' + str(SUPPORT_FLOOR) + ' in a season)'}")
    return "\n".join(lines), support


def _std(x: pd.Series, d: pd.DataFrame) -> pd.Series:
    g = x.groupby([d.season, d.pos])
    return (x - g.transform("mean")) / g.transform("std")


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = pd.Series(a).rank().to_numpy(); rb = pd.Series(b).rank().to_numpy()
    return float(np.corrcoef(ra, rb)[0, 1])


def _stat(h: str, frame: pd.DataFrame, miss_col: str = "miss_z") -> float:
    x = frame.dropna(subset=[h, miss_col])
    if len(x) < 3:
        return np.nan
    if h.startswith("h5"):
        raw = "miss_model" if h == "h5_model" else "miss"
        top = x[x[h] == 1][raw]; rest = x[x[h] == 0][raw]
        return float(top.mean() - rest.mean()) if len(top) and len(rest) else np.nan
    return _spearman(x[h + "_z"].to_numpy(), x[miss_col].to_numpy())


def analyse(d: pd.DataFrame, support: dict, *, B: int = B_FROZEN, seed: int = SEED) -> str:
    d = d.copy()
    d["miss"] = pd.to_numeric(d.actual) - pd.to_numeric(d.mean_projection)
    d["miss_model"] = pd.to_numeric(d.actual) - pd.to_numeric(d.model_points_pre)
    d["miss_z"] = _std(d.miss, d)
    for h in ("h1", "h2", "h3", "h4"):
        d[h + "_z"] = _std(pd.to_numeric(d[h]), d)
    keycols = ["season", "week", "gsis_id", "pos", "actual", "mean_projection", "model_points_pre", "salary",
               "h1", "h2", "h3", "h4"]
    fp = hashlib.sha256(d.sort_values(["season", "week", "gsis_id"])[keycols].to_csv(index=False).encode()).hexdigest()
    clusters = d.groupby(["season", "week"]).indices
    keys = list(clusters); rng = np.random.default_rng(seed)
    lo_q, hi_q = 100 * ALPHA / 2, 100 * (1 - ALPHA / 2)
    out = [f"STUDY 22a READ -- rows {len(d)}, (season, week) clusters {len(keys)}, B {B}, seed {seed}, "
           f"two-sided {LEVEL_TEXT} (alpha {ALPHA:.3f} = 0.05/5)", f"input fingerprint sha256 {fp}"]
    hs = ["h1", "h2", "h3", "h4", "h5"]
    obs = {h: _stat(h, d) for h in hs + ["h5_model"]}
    boot = {h: np.empty(B) for h in hs}
    for b in range(B):
        idx = np.concatenate([clusters[keys[i]] for i in rng.integers(0, len(keys), len(keys))])
        s = d.iloc[idx]
        for h in hs:
            boot[h][b] = _stat(h, s)
    for h in hs:
        label, sign = HYP[h]
        if not support.get(h, False):
            out.append(f"{label}: UNSUPPORTED (census) -- not tested"); continue
        lo, hi = np.nanpercentile(boot[h], [lo_q, hi_q])
        per_season = {s: _stat(h, d[d.season == s]) for s in SEASONS}
        agree = sum(1 for v in per_season.values() if v == v and np.sign(v) == sign)
        if (sign > 0 and lo > 0) or (sign < 0 and hi < 0):
            verdict = "CONFIRMED" if agree >= 3 else f"NOT CONFIRMED (interval clear, but sign in only {agree} of 4 seasons)"
        elif (sign > 0 and hi < 0) or (sign < 0 and lo > 0):
            verdict = "OPPOSITE"
        else:
            verdict = "NOT CONFIRMED"
        out.append(f"{label}: estimate {obs[h]:+.4f}, {LEVEL_TEXT} [{lo:+.4f}, {hi:+.4f}], predicted sign "
                   f"{'+' if sign > 0 else '-'}, seasons with predicted sign {agree}/4 -> {verdict}")
        out.append("    by season: " + ", ".join(f"{s} {v:+.4f}" for s, v in per_season.items()))
        out.append("    by position: " + ", ".join(f"{p} {_stat(h, d[d.pos == p]):+.4f}" for p in TOP_N))
    out.append(f"H5 secondary (no verdict): model_points_pre as value base and miss: {obs['h5_model']:+.4f}")
    for h in ("h1", "h2", "h3", "h4"):            # the decile curve, no verdict
        x = d.dropna(subset=[h + "_z"])
        dec = pd.qcut(x[h + "_z"].rank(method="first"), 10, labels=False) + 1
        out.append(f"{h} decile curve (mean miss, DK points): " + " ".join(f"{v:+.2f}" for v in x.groupby(dec).miss.mean()))
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--panel-run-id", required=True)
    ap.add_argument("--census", action="store_true", help="outcome-blind support census only")
    a = ap.parse_args(argv)
    panel, ws, sal = load(a.panel_run_id, outcomes=not a.census)
    d = add_predictors(eligible(panel), ws, sal)
    text, support = census(d)
    print(text)
    if not a.census:
        print(analyse(d, support))
    return 0


if __name__ == "__main__":
    sys.exit(main())
