#!/usr/bin/env python3
"""Stage 1 of the marginal-tail realism design: outcome-blind effect census.

Transforms every archived world block with the rank-preserving tail
shrink under strictly walk-forward ceilings and publishes ONLY the
effect census (how much draws move, shrink distribution, coverage).
No slate outcome is read: ceilings consume realized history strictly
BEFORE each slate (nfl_features.player_week_actuals, 2014 onward), and
no transformed draw is compared against anything realized. See
reports/2026-08-19-marginal-tail-realism-design.md — this census is the
design's Stage 1 and feeds the anchor/quantile confirmation before any
Stage 2 freeze.

Coverage notes disclosed in the output: DST draws are constant under
the production law, so the fit degenerates to a no-op for them by
construction; players with no prior realized history receive the
position-level ceiling component; players whose position is unknown to
the snapshot map are left untouched and counted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.research.marginal_tail_realism import (  # noqa: E402
    ANCHOR_QUANTILE,
    CEILING_HEADROOM,
    TARGET_QUANTILE,
    TailRealismError,
    apply_tail_shrink,
    assert_ranks_preserved,
    effect_census,
    fit_tail_shrink,
    point_in_time_ceiling,
)

HISTORY_SQL = """
SELECT gsis_id AS id, season, week, dk_points AS actual
FROM `nfl-predictions-503414.nfl_features.player_week_actuals`
WHERE season >= 2014 AND dk_points IS NOT NULL
"""
POSITION_QUANTILE = 0.999


def _load_block(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with np.load(path) as artifact:
        if not {"player_ids", "player_draws"} <= set(artifact.files):
            raise TailRealismError(f"{path} lacks player worlds")
        return (
            np.asarray(artifact["player_ids"], dtype=str),
            np.asarray(artifact["player_draws"], dtype=np.float64),
        )


def _slate_ceilings(
    history: pd.DataFrame,
    pos_of: dict[str, str],
    season: int,
    week: int,
) -> tuple[dict[str, float], dict[str, float]]:
    """Walk-forward per-player ceilings plus the position fallback map."""
    ceilings = point_in_time_ceiling(history, season=season, week=week)
    prior = history[
        (history.season < season)
        | ((history.season == season) & (history.week < week))
    ]
    actual = pd.to_numeric(prior.actual, errors="raise")
    scale = 1.0 + CEILING_HEADROOM
    fallback = {
        str(pos): scale * float(value)
        for pos, value in actual.groupby(
            prior.pos.astype(str)).quantile(POSITION_QUANTILE).items()
    }
    return ceilings, fallback


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--smoke", metavar="SEASON:WEEK")
    args = parser.parse_args(argv)
    if not args.smoke and args.output is None:
        parser.error("--output is required outside --smoke mode")

    manifest = json.loads(args.manifest.read_text())
    features = (
        pd.read_parquet(args.features)
        if args.features.suffix == ".parquet"
        else pd.read_csv(args.features)
    )
    pos_of = dict(zip(
        features.id.astype(str),
        features.pos.astype(str).str.upper(),
    ))
    history = query_df(HISTORY_SQL)
    history["pos"] = history.id.astype(str).map(pos_of)
    history = history[history.pos.notna()]

    slates = sorted(
        ((int(m["season"]), int(m["week"]), [Path(p) for p in m["artifacts"]])
         for m in manifest),
        key=lambda row: (row[0], row[1]))
    if args.smoke:
        season, week = (int(x) for x in args.smoke.split(":"))
        slates = [s for s in slates if (s[0], s[1]) == (season, week)]
        if not slates:
            raise TailRealismError(f"{season} week {week} not in manifest")

    per_slate = []
    for season, week, paths in slates:
        ceilings, fallback = _slate_ceilings(history, pos_of, season, week)
        block_census = []
        for path in paths:
            ids, draws = _load_block(path)
            anchors = np.quantile(draws, ANCHOR_QUANTILE, axis=1)
            shrinks = np.ones(len(ids), dtype=np.float64)
            n_fallback = 0
            n_unknown = 0
            for row, pid in enumerate(ids):
                pid = str(pid)
                ceiling = ceilings.get(pid)
                if ceiling is None:
                    pos = pos_of.get(pid)
                    if pos is None or pos == "DST" or pos not in fallback:
                        n_unknown += 1
                        continue
                    ceiling = fallback[pos]
                    n_fallback += 1
                fit = fit_tail_shrink(draws[row], ceiling)
                anchors[row] = fit["anchor"]
                shrinks[row] = fit["shrink"]
            transformed = apply_tail_shrink(draws, anchors, shrinks)
            assert_ranks_preserved(draws, transformed)
            census = effect_census(draws, transformed, shrinks)
            census["block_file"] = path.name
            census["n_position_fallback"] = int(n_fallback)
            census["n_untouched_unknown"] = int(n_unknown)
            block_census.append(census)
        per_slate.append({
            "season": season,
            "week": week,
            "blocks": block_census,
        })
        print(f"CENSUSED {season}:{week} blocks={len(block_census)}")

    all_blocks = [b for s in per_slate for b in s["blocks"]]
    frame = pd.DataFrame(all_blocks)
    report = {
        "design_doc": "reports/2026-08-19-marginal-tail-realism-design.md",
        "stage": 1,
        "anchor_quantile": ANCHOR_QUANTILE,
        "target_quantile": TARGET_QUANTILE,
        "ceiling_headroom": CEILING_HEADROOM,
        "position_quantile": POSITION_QUANTILE,
        "n_slates": len(per_slate),
        "n_blocks": len(all_blocks),
        "fraction_draws_changed_mean": float(
            frame.fraction_draws_changed.mean()),
        "fraction_players_shrunk_mean": float(
            frame.fraction_players_shrunk.mean()),
        "fraction_players_collapsed_mean": float(
            frame.fraction_players_collapsed.mean()),
        "shrink_median_of_medians": float(frame.shrink_median.median()),
        "mean_abs_change_mean": float(frame.mean_abs_change.mean()),
        "max_abs_change_max": float(frame.max_abs_change.max()),
        "position_fallback_total": int(frame.n_position_fallback.sum()),
        "untouched_unknown_total": int(frame.n_untouched_unknown.sum()),
        "per_slate": per_slate,
        "uses_realized_outcomes": False,
        "fit_performed": False,
        "tuning_performed": False,
        "gate_decision": None,
        "production_change_licensed": False,
    }
    if args.smoke:
        block = all_blocks[0]
        print(f"SMOKE_OK ranks_preserved=True "
              f"players={block['n_players']} worlds={block['n_worlds']} "
              f"fallback={block['n_position_fallback']} "
              f"unknown={block['n_untouched_unknown']}")
        return 0
    payload = json.dumps(
        report, sort_keys=True, separators=(",", ":")).encode()
    with args.output.open("xb") as handle:
        handle.write(payload)
    digest = hashlib.sha256(payload).hexdigest()
    print(
        "MARGINAL_TAIL_STAGE1_COMPLETE",
        f"slates={report['n_slates']}",
        f"output={args.output}",
        f"sha256={digest}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
