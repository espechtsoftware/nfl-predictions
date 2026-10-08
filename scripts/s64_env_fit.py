#!/usr/bin/env python3
"""Study 64 (S1, the pros briefing 10-08): fit the GAME-ENVIRONMENT calibration from 2023-25 and write the FROZEN
coefficients file (reports/2026-10-08-prereg-study64-env-calibration.md).

History (the outside reviewer's analysis C, reports/2026-10-08-pro-methods/c_history_beyond_market.py): on played
QB / RB / WR / TE player-weeks with a props number (nfl_dfs.models.prop_market.market_points, >= 2 scoring markets), the
team implied total (+0.33 per sd, z 3.4, 3 / 3 seasons) and wind (-0.35 per sd; QB about -1) predicted DraftKings points
BEYOND the market, the best historical stand-in for Fantasy Points' projection. This fits both JOINTLY per position
(game total, spread and expected plays overlap the implied total; stacking their solo coefficients would double-count):

    resid = y_dk_points - market_points, demeaned within season x week x position
    z_itt  = implied_team_total, z-scored within season x week x position
    z_wind = wind (0 for a dome: training's wind is NULL under a roof), z-scored within season x week x position
    resid_demeaned ~ b_itt * z_itt + b_wind * z_wind          (per position, least squares, no intercept)

Uncertainty: a whole-week bootstrap (season-weeks resampled), 300 reps, seed 3; per-season coefficients for stability.
Writes the coefficients JSON (create-once) with the fit's row count, the input content sha and this script's sha.

    PYTHONPATH=src python scripts/s64_env_fit.py --out reports/2026-10-09-s64-env/s64_env_coefficients.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

SEASONS = (2023, 2024, 2025)
POSITIONS = ("QB", "RB", "WR", "TE")
MIN_MARKETS, BOOT, SEED, CAP = 2, 300, 3, 2.0


def build_panel(training: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    """The fit rows: played skill players with a market number, the residual, the wind with domes at 0."""
    t = training[training.position.isin(POSITIONS) & training.season.isin(SEASONS)].copy()
    t = t[t.was_active.astype(bool)]
    m = t.merge(market[["season", "week", "gsis_id", "market_points"]], on=["season", "week", "gsis_id"], how="inner")
    m = m[m.market_points.notna() & m.y_dk_points.notna() & m.implied_team_total.notna()].copy()
    dome = m.is_dome.fillna(False).astype(bool)
    m["wind_eff"] = np.where(dome, 0.0, pd.to_numeric(m.wind_mph, errors="coerce"))
    m = m[m.wind_eff.notna()].copy()                       # an outdoor game with no wind reading is left out
    m["resid"] = m.y_dk_points.astype(float) - m.market_points.astype(float)
    m["swp"] = m.season.astype(int).astype(str) + "-" + m.week.astype(int).astype(str) + "-" + m.position
    m["sw"] = m.season.astype(int).astype(str) + "-" + m.week.astype(int).astype(str)
    for col, z in (("implied_team_total", "z_itt"), ("wind_eff", "z_wind")):
        g = m.groupby("swp")[col]
        sd = g.transform("std")
        m[z] = np.where(sd > 0, (m[col] - g.transform("mean")) / sd, 0.0)
    m["resid_d"] = m.resid - m.groupby("swp").resid.transform("mean")
    return m


def fit(df: pd.DataFrame) -> tuple[float, float]:
    X = df[["z_itt", "z_wind"]].to_numpy(float); y = df.resid_d.to_numpy(float)
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(b[0]), float(b[1])


def fit_all(m: pd.DataFrame) -> dict:
    rng = np.random.default_rng(SEED)
    weeks = m.sw.unique()
    idx = {w: np.flatnonzero(m.sw.values == w) for w in weeks}
    out = {}
    for pos in POSITIONS:
        d = m[m.position == pos]
        b_itt, b_wind = fit(d)
        bs = []
        dw = {w: np.flatnonzero(d.sw.values == w) for w in d.sw.unique()}
        keys = list(dw)
        for _ in range(BOOT):
            pick = rng.choice(keys, len(keys), replace=True)
            bs.append(fit(d.iloc[np.concatenate([dw[w] for w in pick])]))
        bs = np.asarray(bs)
        per = {int(s): fit(d[d.season == s]) for s in SEASONS}
        out[pos] = {"b_itt": round(b_itt, 4), "b_wind": round(b_wind, 4), "n": int(len(d)),
                    "se_itt": round(float(bs[:, 0].std()), 4), "se_wind": round(float(bs[:, 1].std()), 4),
                    "by_season": {s: {"b_itt": round(v[0], 4), "b_wind": round(v[1], 4)} for s, v in per.items()}}
    _ = idx
    return out


def content_sha(m: pd.DataFrame) -> str:
    cols = ["season", "week", "gsis_id", "position", "y_dk_points", "market_points", "implied_team_total", "wind_eff"]
    body = m[cols].sort_values(["season", "week", "gsis_id"]).to_csv(index=False, float_format="%.6f")
    return hashlib.sha256(body.encode()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.out.exists():
        print(f"S64 FIT REFUSED: {a.out} exists (create-once)", file=sys.stderr)
        return 3
    from google.cloud import bigquery
    from nfl_dfs.config import settings
    from nfl_dfs.models.prop_market import market_points
    c = bigquery.Client(project=settings.project)
    tr = c.query(f"""SELECT season, week, gsis_id, position, was_active, y_dk_points, implied_team_total, wind_mph, is_dome
                     FROM `{settings.features}.player_week_training` WHERE season IN UNNEST(@s)""",
                 job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ArrayQueryParameter("s", "INT64", list(SEASONS))])).to_dataframe()
    mk = market_points(SEASONS, minimum_markets=MIN_MARKETS)
    m = build_panel(tr, mk)
    coefs = fit_all(m)
    doc = {"study": 64, "what": "the game-environment calibration on Fantasy Points (S1, the pros briefing 10-08)",
           "fit": {"seasons": list(SEASONS), "rows": int(len(m)), "rows_by_position": {p: coefs[p]["n"] for p in POSITIONS},
                   "residual": "y_dk_points - market_points (nfl_dfs.models.prop_market, minimum_markets 2), played QB/RB/WR/TE",
                   "model": "per position, resid demeaned within season x week x position ~ b_itt * z_itt + b_wind * z_wind",
                   "z": "within season x week x position", "dome_wind": 0.0, "bootstrap": {"reps": BOOT, "seed": SEED, "unit": "season-week"},
                   "input_content_sha256": content_sha(m), "fitter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "written_utc": datetime.now(UTC).isoformat(timespec="seconds")},
           "apply": {"z": "within the slate's frame by position, over the skill players with an FP projection (sd > 0, >= 3 players; else 0)",
                     "dome_wind": 0.0, "missing": "a missing implied total or (outdoor) wind contributes 0",
                     "cap_points": CAP, "floor": "fp_env = max(fp + env_adj, 0)"},
           "positions": {p: {k: v for k, v in coefs[p].items()} for p in POSITIONS}}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1, sort_keys=False) + "\n")
    print(f"S64 FIT: {len(m)} rows; " + "; ".join(f"{p} itt {coefs[p]['b_itt']:+.3f} (se {coefs[p]['se_itt']:.3f}) wind "
                                                 f"{coefs[p]['b_wind']:+.3f} (se {coefs[p]['se_wind']:.3f}) n {coefs[p]['n']}"
                                                 for p in POSITIONS) + f" -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
