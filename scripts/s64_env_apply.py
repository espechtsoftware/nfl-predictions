#!/usr/bin/env python3
"""Study 64 (S1): apply the FROZEN game-environment calibration to one week's frame and FP projections
(reports/2026-10-08-prereg-study64-env-calibration.md §3).

Per skill player (QB / RB / WR / TE) of the frame with an FP projection (the union's proj_source.csv `fp`):
    z_itt, z_wind  within the frame by position over those players (sd > 0 and >= 3 players, else 0); wind 0 under a roof
                   (training's wind is NULL for domes); a missing value contributes 0
    env_adj        b_itt[pos] * z_itt + b_wind[pos] * z_wind, capped at +/- the file's cap (2.0 points)
    fp_env         max(fp + env_adj, 0)
Writes a PRIVATE CSV (id, dk_draftable_id, pos, fp, env_adj, fp_env; FP's numbers are licensed) and <out>.json (the
coefficients' sha, the frame's and the projection file's shas, counts).

    PYTHONPATH=src python scripts/s64_env_apply.py --frame <T-70 frame.parquet> --proj-source <proj_source.csv> \
        --coeffs reports/2026-10-09-s64-env/s64_env_coefficients.json --out ~/private/s64-env/w05-fp-env.csv
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


def zscore(x: pd.Series, groups: pd.Series) -> pd.Series:
    """Within each group: (x - mean) / sd where sd > 0 and >= 3 non-missing values; else 0; a missing x is 0."""
    out = pd.Series(0.0, index=x.index)
    for _, idx in x.groupby(groups).groups.items():
        v = x.loc[idx]
        ok = v.notna()
        if ok.sum() >= 3 and v[ok].std() > 0:
            out.loc[idx] = ((v - v[ok].mean()) / v[ok].std()).fillna(0.0)
    return out


def apply(frame: pd.DataFrame, proj: pd.DataFrame, coeffs: dict) -> pd.DataFrame:
    fr = frame[frame.pos.astype(str).isin(SKILL)].copy()
    fr["id"] = fr["id"].astype(str)
    p = proj.assign(id=proj["id"].astype(str))[["id", "fp"]]
    d = fr.merge(p, on="id", how="inner")
    d["fp"] = pd.to_numeric(d.fp, errors="coerce")
    d = d[d.fp.notna()].copy()
    dome = d.is_dome.fillna(False).astype(bool) if "is_dome" in d.columns else pd.Series(False, index=d.index)
    wind = pd.to_numeric(d.get("wind_mph"), errors="coerce")
    d["wind_eff"] = np.where(dome, 0.0, wind)
    d["z_itt"] = zscore(pd.to_numeric(d.implied_team_total, errors="coerce"), d.pos)
    d["z_wind"] = zscore(d.wind_eff.astype(float), d.pos)
    b = coeffs["positions"]; cap = float(coeffs["apply"]["cap_points"])
    raw = d.pos.map(lambda q: b[q]["b_itt"]) * d.z_itt + d.pos.map(lambda q: b[q]["b_wind"]) * d.z_wind
    d["env_adj"] = raw.clip(-cap, cap).round(4)
    d["fp_env"] = (d.fp + d.env_adj).clip(lower=0.0).round(4)
    cols = ["id", "dk_draftable_id", "pos", "fp", "env_adj", "fp_env"]
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
    meta = {"coeffs_sha256": sha256(a.coeffs), "frame_sha256": sha256(a.frame), "proj_source_sha256": sha256(a.proj_source),
            "players": int(len(out)), "adjusted": int((out.env_adj != 0).sum()), "capped": int((out.env_adj.abs() >= coeffs["apply"]["cap_points"]).sum()),
            "env_adj_mean_abs": round(float(out.env_adj.abs().mean()), 4), "csv_sha256": sha256(a.out)}
    Path(str(a.out) + ".json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"S64 ENV: {meta['players']} players, {meta['adjusted']} adjusted (mean |adj| {meta['env_adj_mean_abs']}, capped "
          f"{meta['capped']}) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
