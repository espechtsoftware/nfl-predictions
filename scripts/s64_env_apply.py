#!/usr/bin/env python3
"""Study 64 (S1): apply the FROZEN game-environment calibration (version 2, real units) to one week's frame and FP
projections (reports/2026-10-08-prereg-study64-env-calibration.md §3).

Per skill player (QB / RB / WR / TE) of the frame with an FP projection (the union's proj_source.csv `fp`):
    itt_d      implied_team_total minus the mean over those players of the same position (points of team total)
    wind_d     OPEN-AIR players only (the game's home team -- game_id's last token -- is not in the file's roofed_home):
               wind_mph minus the open-air mean of the same position (mph); 0 for every other player
    a group with fewer than 3 non-missing values, or a missing value, contributes 0
    itt_adj    ITT model:  b_itt[pos] * itt_d                       capped at +/- the file's cap (2.0 points)
    env_adj    ENV model:  b_itt[pos] * itt_d + b_wind[pos] * wind_d  capped likewise (the ENV fit's own b_itt)
    fp_itt     max(fp + itt_adj, 0)   (THE PRIMARY)          fp_env  max(fp + env_adj, 0)   (the wind increment)
Writes a PRIVATE CSV (id, dk_draftable_id, pos, fp, itt_adj, env_adj, fp_itt, fp_env; FP's numbers are licensed) and
<out>.json (the coefficients' sha, the frame's and the projection file's shas, counts).

    PYTHONPATH=src python scripts/s64_env_apply.py --frame <T-70 frame.parquet> --proj-source <proj_source.csv> \
        --coeffs reports/2026-10-09-s64-env/s64_env_coefficients_v2.json --out ~/private/s64-env/w05-fp-env.csv
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SKILL = ("QB", "RB", "WR", "TE")


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def home_team(game_id: pd.Series) -> pd.Series:
    """nflverse game ids are SEASON_WW_AWAY_HOME."""
    return game_id.astype(str).str.split("_").str[-1]


def demean(x: pd.Series, groups: pd.Series) -> pd.Series:
    """Within each group: x minus the mean of its non-missing values, where there are >= 3; else 0; a missing x is 0."""
    out = pd.Series(0.0, index=x.index)
    for _, idx in x.groupby(groups).groups.items():
        v = x.loc[idx]
        ok = v.notna()
        if ok.sum() >= 3:
            out.loc[idx] = (v - v[ok].mean()).fillna(0.0)
    return out


def apply(frame: pd.DataFrame, proj: pd.DataFrame, coeffs: dict) -> pd.DataFrame:
    if coeffs.get("version") != 2:
        raise SystemExit(f"S64 APPLY REFUSED: coefficients version {coeffs.get('version')}, not 2 (real units)")
    fr = frame[frame.pos.astype(str).isin(SKILL)].copy()
    fr["id"] = fr["id"].astype(str)
    p = proj.assign(id=proj["id"].astype(str))[["id", "fp"]]
    d = fr.merge(p, on="id", how="inner")
    d["fp"] = pd.to_numeric(d.fp, errors="coerce")
    d = d[d.fp.notna()].copy()
    roofed = set(coeffs["apply"]["roofed_home"])
    wind = pd.to_numeric(d.wind_mph, errors="coerce")
    d["open_air"] = ~home_team(d.game_id).isin(roofed) & wind.notna()
    d["itt_d"] = demean(pd.to_numeric(d.implied_team_total, errors="coerce"), d.pos)
    d["wind_d"] = demean(wind.where(d.open_air), d.pos).where(d.open_air, 0.0)
    m, cap = coeffs["models"], float(coeffs["apply"]["cap_points"])
    by = lambda model, b: d.pos.map(lambda q: m[model][q][b])
    d["itt_adj"] = (by("ITT", "b_itt") * d.itt_d).clip(-cap, cap).round(4)
    d["env_adj"] = (by("ENV", "b_itt") * d.itt_d + by("ENV", "b_wind") * d.wind_d).clip(-cap, cap).round(4)
    d["fp_itt"] = (d.fp + d.itt_adj).clip(lower=0.0).round(4)
    d["fp_env"] = (d.fp + d.env_adj).clip(lower=0.0).round(4)
    cols = ["id", "dk_draftable_id", "pos", "open_air", "fp", "itt_adj", "env_adj", "fp_itt", "fp_env"]
    return d[[c for c in cols if c in d.columns]].sort_values("id").reset_index(drop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--frame", type=Path, required=True); ap.add_argument("--proj-source", type=Path, required=True)
    ap.add_argument("--coeffs", type=Path, required=True); ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    coeffs = json.loads(a.coeffs.read_text())
    out = apply(pd.read_parquet(a.frame), pd.read_csv(a.proj_source, dtype={"id": str}), coeffs)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)
    cap = coeffs["apply"]["cap_points"]
    meta = {"coeffs_sha256": sha256(a.coeffs), "frame_sha256": sha256(a.frame), "proj_source_sha256": sha256(a.proj_source),
            "players": int(len(out)), "open_air": int(out.open_air.sum()),
            "itt_mean_abs": round(float(out.itt_adj.abs().mean()), 4), "itt_capped": int((out.itt_adj.abs() >= cap).sum()),
            "env_mean_abs": round(float(out.env_adj.abs().mean()), 4), "env_capped": int((out.env_adj.abs() >= cap).sum()),
            "csv_sha256": sha256(a.out)}
    Path(str(a.out) + ".json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"S64 ENV: {meta['players']} players ({meta['open_air']} open-air); ITT mean |adj| {meta['itt_mean_abs']} (capped "
          f"{meta['itt_capped']}), ENV mean |adj| {meta['env_mean_abs']} (capped {meta['env_capped']}) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
