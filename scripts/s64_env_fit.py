#!/usr/bin/env python3
"""Study 64 (S1, the pros briefing 10-08): fit the GAME-ENVIRONMENT calibration from 2023-25 and write the FROZEN
coefficients file (reports/2026-10-08-prereg-study64-env-calibration.md). Version 2, before the freeze, after the outside
reviewer's correction (pro-methods 0b2207b8): REAL UNITS and wind from open-air games only.

History (the outside reviewer's analysis C): on played QB / RB / WR / TE player-weeks with a props number
(nfl_dfs.models.prop_market.market_points, >= 2 scoring markets), the team implied total and wind predicted DraftKings
points BEYOND the market (the best historical stand-in for FP). Per position, in real units, two models:

    resid      = y_dk_points - market_points, demeaned within season x week x position
    itt_d      = implied_team_total minus its season x week x position mean (points of team total)
    wind_d     = wind minus its season x week x position mean over the OPEN-AIR rows (mph); 0 for every other row.
                 OPEN-AIR = the home team (game_id's last token) is not in ROOFED_HOME and the wind is not NULL. In
                 2023-25 the wind is the schedule's MEASURED game wind, NULL at every dome and retractable-roof stadium
                 (ARI ATL DAL HOU IND, DET LA LAC LV MIN NO) but for 2 international games, which the rule zeroes; a
                 NULL wind at an open-air stadium (39 games, mostly 2023 W1-2) is missing and contributes 0
    ITT        resid ~ b_itt * itt_d                      (THE PRIMARY adjustment)
    ENV        resid ~ b_itt * itt_d + b_wind * wind_d    (the secondary: ITT plus wind, an UPPER BOUND -- measured wind,
                                                           where live has a forecast)

Uncertainty: a whole-week bootstrap (season-weeks resampled), 300 reps, seed 3; per-season coefficients for stability.
Writes the coefficients JSON (create-once) with the fit's row count, the input content sha and this script's sha.

    PYTHONPATH=src python scripts/s64_env_fit.py --out reports/2026-10-09-s64-env/s64_env_coefficients_v2.json
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
# every 2023-25 home game at these stadiums has a NULL schedule wind (dome, or a retractable roof open or closed)
ROOFED_HOME = ("ARI", "ATL", "DAL", "DET", "HOU", "IND", "LA", "LAC", "LV", "MIN", "NO")


def build_panel(training: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    """The fit rows: played skill players with a market number and an implied total; the residual and the regressors in
    real units, demeaned within season x week x position (wind among the open-air rows only)."""
    t = training[training.position.isin(POSITIONS) & training.season.isin(SEASONS)].copy()
    t = t[t.was_active.astype(bool)]
    m = t.merge(market[["season", "week", "gsis_id", "market_points"]], on=["season", "week", "gsis_id"], how="inner")
    m = m[m.market_points.notna() & m.y_dk_points.notna() & m.implied_team_total.notna()].copy()
    m["resid"] = m.y_dk_points.astype(float) - m.market_points.astype(float)
    m["swp"] = m.season.astype(int).astype(str) + "-" + m.week.astype(int).astype(str) + "-" + m.position
    m["sw"] = m.season.astype(int).astype(str) + "-" + m.week.astype(int).astype(str)
    m["resid_d"] = m.resid - m.groupby("swp").resid.transform("mean")
    m["itt_d"] = m.implied_team_total.astype(float) - m.groupby("swp").implied_team_total.transform("mean")
    wind = pd.to_numeric(m.wind_mph, errors="coerce")
    m["open_air"] = ~m.game_id.astype(str).str.split("_").str[-1].isin(ROOFED_HOME) & wind.notna()
    w_mean = wind.where(m.open_air).groupby(m.swp).transform("mean")
    m["wind_d"] = np.where(m.open_air, wind - w_mean, 0.0)
    return m


def fit(df: pd.DataFrame, cols: tuple[str, ...]) -> tuple[float, ...]:
    X = df[list(cols)].to_numpy(float); y = df.resid_d.to_numpy(float)
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return tuple(float(v) for v in b)


MODELS = {"ITT": ("itt_d",), "ENV": ("itt_d", "wind_d")}
NAMES = {"itt_d": "b_itt", "wind_d": "b_wind"}


def fit_all(m: pd.DataFrame) -> dict:
    rng = np.random.default_rng(SEED)
    out = {}
    for model, cols in MODELS.items():
        out[model] = {}
        for pos in POSITIONS:
            d = m[m.position == pos]
            b = fit(d, cols)
            dw = {w: np.flatnonzero(d.sw.values == w) for w in d.sw.unique()}
            keys = list(dw)
            bs = np.asarray([fit(d.iloc[np.concatenate([dw[w] for w in rng.choice(keys, len(keys), replace=True)])], cols)
                             for _ in range(BOOT)])
            per = {int(s): fit(d[d.season == s], cols) for s in SEASONS}
            rec = {"n": int(len(d)), "n_open_air": int(d.open_air.sum())}
            for i, c in enumerate(cols):
                rec[NAMES[c]] = round(b[i], 5); rec[f"se_{NAMES[c][2:]}"] = round(float(bs[:, i].std()), 5)
            rec["by_season"] = {s: {NAMES[c]: round(v[i], 5) for i, c in enumerate(cols)} for s, v in per.items()}
            out[model][pos] = rec
    return out


def content_sha(m: pd.DataFrame) -> str:
    cols = ["season", "week", "gsis_id", "game_id", "position", "y_dk_points", "market_points", "implied_team_total", "wind_mph"]
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
    tr = c.query(f"""SELECT season, week, gsis_id, game_id, position, was_active, y_dk_points, implied_team_total, wind_mph, is_dome
                     FROM `{settings.features}.player_week_training` WHERE season IN UNNEST(@s)""",
                 job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ArrayQueryParameter("s", "INT64", list(SEASONS))])).to_dataframe()
    mk = market_points(SEASONS, minimum_markets=MIN_MARKETS)
    m = build_panel(tr, mk)
    coefs = fit_all(m)
    doc = {"study": 64, "version": 2, "what": "the game-environment calibration on Fantasy Points (S1, the pros briefing 10-08)",
           "fit": {"seasons": list(SEASONS), "rows": int(len(m)), "rows_open_air": int(m.open_air.sum()),
                   "residual": "y_dk_points - market_points (nfl_dfs.models.prop_market, minimum_markets 2), played QB/RB/WR/TE",
                   "models": {"ITT": "resid_d ~ b_itt * itt_d (THE PRIMARY)", "ENV": "resid_d ~ b_itt * itt_d + b_wind * wind_d (secondary; wind an upper bound)"},
                   "units": {"b_itt": "DK points per point of team implied total", "b_wind": "DK points per mph"},
                   "demeaning": "within season x week x position; wind among the open-air rows only (home team not in roofed_home, wind not NULL)",
                   "bootstrap": {"reps": BOOT, "seed": SEED, "unit": "season-week"},
                   "input_content_sha256": content_sha(m), "fitter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "written_utc": datetime.now(UTC).isoformat(timespec="seconds")},
           "apply": {"itt": "implied_team_total minus the slate frame's mean by position (players with an FP projection)",
                     "wind": "open-air only: the home team is not in roofed_home; wind minus the slate's open-air mean by position; else 0",
                     "roofed_home": list(ROOFED_HOME), "missing": "a missing value contributes 0",
                     "cap_points": CAP, "floor": "max(fp + adj, 0)"},
           "models": coefs}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1, sort_keys=False) + "\n")
    print(f"S64 FIT v2: {len(m)} rows ({int(m.open_air.sum())} open-air); "
          + "; ".join(f"{p} ITT {coefs['ITT'][p]['b_itt']:+.4f}/pt (se {coefs['ITT'][p]['se_itt']:.4f}) | ENV itt {coefs['ENV'][p]['b_itt']:+.4f} "
                      f"wind {coefs['ENV'][p]['b_wind']:+.4f}/mph (se {coefs['ENV'][p]['se_wind']:.4f})" for p in POSITIONS) + f" -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
