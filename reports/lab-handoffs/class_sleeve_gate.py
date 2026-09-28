#!/usr/bin/env python3
"""Class-sleeve gate (operator item 2, 2026-09-28): boom solves on an archived week's frame, every other visit under the
class sleeve's shape, scored on realized DK points. Read-only; writes nothing.

Uses the run dir's frame and its incumbent sidecar bank as the worlds, drops skill players projected under 1 point
(as the live --min-proj does), builds the sleeve's constraints from the class model file's pre-lock map
(nfl2.class_selector.class_sleeve_kwargs), and generates --boom visits with the lab generator's boom_sleeve hook.
Prints each family's realized mean and its rates at 193+, 175+ and the week's Millionaire p90/p99.

    PYTHONPATH=<lab two-track checkout>/src:<this repo>/src python reports/lab-handoffs/class_sleeve_gate.py \
        --run-dir RUN_DIR --class-model MODEL.json --season 2026 --week 3 --milly-contest 195905122 [--boom 400]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", type=Path, required=True); ap.add_argument("--class-model", type=Path, required=True)
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--milly-contest", required=True); ap.add_argument("--boom", type=int, default=400)
    ap.add_argument("--every", type=int, default=2)
    a = ap.parse_args()
    from nfl2.class_selector import class_sleeve_kwargs, prelock_map, salary_legal_optimum
    from nfl2.pipeline import candidate_actual, generate_candidates
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings

    fr = pd.read_parquet(a.run_dir / "frame.parquet").reset_index(drop=True)
    bank = np.load(a.run_dir / "incumbent_player_scores.npy")
    low = (fr.pos.isin(["QB", "RB", "WR", "TE"]) & (pd.to_numeric(fr.mean_projection, errors="coerce").fillna(0) < 1.0)).to_numpy()
    fr = fr[~low].reset_index(drop=True); bank = bank[~low]
    qs, pm = prelock_map(a.class_model); opt = salary_legal_optimum(fr); kw = class_sleeve_kwargs(fr, qs, opt)
    print(f"week {a.week}: frame optimum {opt:.2f}; projection band {kw['objective_floor']:.1f}-{kw['objective_ceiling']:.1f}; "
          f"QBs banned {len(kw['bans'])}; map weeks {pm['map_weeks']}")
    cands = generate_candidates(fr, bank, n_lev=0, n_boom=a.boom, env={"MAX_PER_GAME": "4"}, ledger=[],
                                boom_sleeve={"every": a.every, "tag": "boom:class", "kwargs": kw})
    fp = query_df(f"SELECT display_name, MAX(fpts) f FROM `{settings.raw}.contest_ownership` WHERE season={a.season} "
                  f"AND week={a.week} GROUP BY 1")
    real = dict(zip(fp.display_name.astype(str), fp.f.astype(float)))
    act = np.asarray(candidate_actual(fr.assign(actual=fr.display_name.map(real).fillna(0.0)), cands))
    tags = np.array([lu.tag for lu in cands])
    field = query_df(f"SELECT points FROM `{settings.raw}.contest_entries` WHERE season={a.season} AND week={a.week} "
                     f"AND contest_id='{a.milly_contest}'").points.to_numpy(float)
    p90, p99 = np.percentile(field, 90), np.percentile(field, 99)
    for t in ("boom", "boom:class"):
        m = tags == t; x = act[m]
        print(f"{t:11s} rows {m.sum():4d}; realized mean {x.mean():6.1f}; >= Milly p90 ({p90:.0f}) {100 * (x >= p90).mean():5.1f}%; "
              f">= p99 ({p99:.0f}) {100 * (x >= p99).mean():5.2f}%; >= 193 {100 * (x >= 193).mean():5.2f}%; "
              f">= 175 {100 * (x >= 175).mean():5.1f}%; best {x.max():.1f}")


if __name__ == "__main__":
    main()
