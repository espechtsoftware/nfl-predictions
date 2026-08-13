#!/usr/bin/env python
"""Mechanical audit and frozen five-seed repaired-usage Phase R decision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.research.served_tail_lineup import lever_values  # noqa: E402


SEEDS = {
    0: (0, 7331),
    1: (1137260708, 2690847602),
    2: (2875959182, 1630284992),
    3: (253722715, 3374646876),
    4: (1643280042, 3977633467),
}
PANELS = {
    (arm, replicate): f"20260813-game-team-{arm}-r{replicate}-v1"
    for arm in ("mult", "k") for replicate in SEEDS
}
POSITION_SPECS = {
    2023: "QB:0.965,RB:0.99,TE:0.945,WR:1.03",
    2024: "QB:0.905,RB:0.97,TE:0.95,WR:1.06",
    2025: "QB:0.925,RB:0.96,TE:0.94,WR:1.04",
}
TAILS = (240, 230, 220, 210, 200, 194, 187)
FITTED_K = "28.154043586960896"
ROLE_FEATURES = (
    "target_share_last,carry_share_last,snap_share_last,"
    "target_share_jump,carry_share_jump,snap_share_jump"
)
FEATURE_FIELDS = (
    "gsis_id", "name", "pos", "team", "opp", "game_id", "salary",
    "market_points", "model_points_pre",
    "target_share_last", "carry_share_last", "snap_share_last",
    "target_share_jump", "carry_share_jump", "snap_share_jump",
    "target_share_l4", "carry_share_l4", "snap_share_l4", "dk_points_l4",
    "implied_team_total", "spread", "game_total", "is_cold_start",
    "depth_rank", "depth_rank_delta", "team_vacated_target_share",
    "team_vacated_carry_share", "salary_delta_wow", "games_played_prior",
    "actual", "feature_missing", "component_mean_carries",
    "component_mean_catch_rate", "component_mean_interceptions",
    "component_mean_pass_attempts", "component_mean_pass_tds",
    "component_mean_rec_tds", "component_mean_rush_tds",
    "component_mean_targets", "component_mean_ypa", "component_mean_ypc",
    "component_mean_ypr", "model_ensemble_size", "model_member_spec",
    "ensemble_point_0", "ensemble_point_1", "ensemble_point_2",
)
OUTPUT_PREFIX = "GAME_TEAM_USAGE_PHASE_R_JSON="


def _parse_pairs(value: str) -> dict[str, str]:
    out = {}
    for item in str(value or "").split(";"):
        key, marker, val = item.partition("=")
        if marker:
            out[key] = val
    return out


def _equal_series(
    left: pd.Series, right: pd.Series, tolerance: float = 1e-10
) -> pd.Series:
    both_null = left.isna() & right.isna()
    if pd.api.types.is_bool_dtype(left.dtype) or pd.api.types.is_bool_dtype(
        right.dtype
    ):
        return both_null | (
            left.notna() & right.notna()
            & left.astype("boolean").eq(right.astype("boolean"))
        )
    ln = pd.to_numeric(left, errors="coerce").astype("Float64")
    rn = pd.to_numeric(right, errors="coerce").astype("Float64")
    numeric = left.notna() & right.notna() & ln.notna() & rn.notna()
    close = numeric & (ln - rn).abs().le(tolerance)
    text = (~numeric) & left.astype(str).eq(right.astype(str))
    return both_null | close | text


def _load_candidates() -> dict[tuple[str, int], pd.DataFrame]:
    fields = (
        "panel_run_id, code_sha, lever_env, seeds, labels_complete, season, "
        "week, cand_ix, selected, selected_rank, players, actual_score, "
        "sim_mean, n_entries, n_sims, n_worlds"
    )
    return {
        key: query_df(f"""
            SELECT {fields}
            FROM `{settings.predictions}.replay_candidates_staging`
            WHERE panel_run_id=@panel
              AND season IN UNNEST(@seasons)
            """, params={
                "panel": panel,
                "seasons": sorted(POSITION_SPECS),
            })
        for key, panel in PANELS.items()
    }


def _load_features() -> dict[tuple[str, int], pd.DataFrame]:
    fields = ", ".join(("season", "week", "id", *FEATURE_FIELDS))
    return {
        key: query_df(f"""
            SELECT {fields}
            FROM `{settings.predictions}.slate_player_features`
            WHERE panel_run_id=@panel
              AND season IN UNNEST(@seasons)
            """, params={
                "panel": panel,
                "seasons": sorted(POSITION_SPECS),
            })
        for key, panel in PANELS.items()
    }


def mechanical_failures(
    candidates: dict[tuple[str, int], pd.DataFrame],
    features: dict[tuple[str, int], pd.DataFrame],
    expected_code_sha: str,
) -> list[str]:
    failures: list[str] = []
    for (arm, replicate), frame in candidates.items():
        label = f"{arm}-R{replicate}"
        if frame.empty:
            failures.append(f"{label} candidate panel is empty")
            continue
        if not frame.code_sha.astype(str).eq(expected_code_sha).all():
            failures.append(f"{label} code SHA differs")
        if set(frame.season.astype(int)) != set(POSITION_SPECS):
            failures.append(f"{label} season set differs")
        groups = frame.groupby(["season", "week"])
        if len(groups) != 54:
            failures.append(f"{label} has {len(groups)} slates, want 54")
        if not frame.labels_complete.fillna(False).astype(bool).all() or \
                frame.actual_score.isna().any():
            failures.append(f"{label} labels are incomplete")
        if not frame.n_entries.eq(80).all() or not frame.n_sims.eq(10000).all() \
                or not frame.n_worlds.eq(10000).all():
            failures.append(f"{label} entries/world counts differ")
        if not groups.selected.sum().eq(80).all():
            failures.append(f"{label} does not select exactly 80 per slate")
        if frame[frame.selected].duplicated(["season", "week", "players"]).any():
            failures.append(f"{label} selected rosters are not distinct")
        if frame.duplicated(["season", "week", "cand_ix"]).any():
            failures.append(f"{label} candidate indices are duplicated")
        seed_values = frame.seeds.fillna("").astype(str).unique()
        if len(seed_values) != 1:
            failures.append(f"{label} has multiple seed identities")
        else:
            seeds = _parse_pairs(seed_values[0])
            got = (
                int(seeds.get("REPLAY_PROJECTION_SEED", "0")),
                int(seeds.get("ROLE_BELIEF_SEED", "7331")),
            )
            if got != SEEDS[replicate]:
                failures.append(f"{label} seed pair differs")
        for season, spec in POSITION_SPECS.items():
            values = frame.loc[frame.season.eq(season), "lever_env"].unique()
            if len(values) != 1:
                failures.append(f"{label} {season} lever identity is not unique")
                continue
            lever = lever_values(values[0])
            expected = {
                "GAME_SIM_MODE": "possession",
                "MODEL_ENSEMBLE": "1",
                "TABPFN_MARGINALS": "1",
                "TABPFN_MARGINAL_TABLE": "tabpfn_active_label_treatment_v2",
                "EPISTEMIC_FAMILY": "role_draws",
                "ROLE_BELIEF_FEATURES": ROLE_FEATURES,
                "ROLE_BELIEF_SEED": str(SEEDS[replicate][1]),
                "REPLAY_PROJECTION_SEED": str(SEEDS[replicate][0]),
                "REPLACEMENT_SLOTS": "12",
                "N_CE": "0", "N_EPISTEMIC": "12", "N_GUMBEL": "0",
                "N_BOOM": "40", "SERVED_POSITION_SCALES": spec,
            }
            for field, value in expected.items():
                if lever.get(field) != value:
                    failures.append(f"{label} {season} {field} differs")
            if "SIS_ASOE_TARGET_ALLOCATION" in lever or "SIS_ASOE_BETA" in lever:
                failures.append(f"{label} unexpectedly enables ASOE")
            if arm == "mult":
                if "GAME_SIM_USAGE" in lever or "DIRICHLET_K" in lever:
                    failures.append(f"{label} multinomial levers differ")
            elif lever.get("GAME_SIM_USAGE") != "dirichlet" or \
                    lever.get("DIRICHLET_K") != FITTED_K:
                failures.append(f"{label} finite-K levers differ")

    keys = ["season", "week", "id"]
    for replicate in SEEDS:
        left = features[("mult", replicate)]
        right = features[("k", replicate)]
        if left.empty or right.empty:
            failures.append(f"R{replicate} feature panel is empty")
            continue
        if left.duplicated(keys).any() or right.duplicated(keys).any():
            failures.append(f"R{replicate} feature keys repeat")
            continue
        left = left.set_index(keys).sort_index()
        right = right.set_index(keys).sort_index()
        if not left.index.equals(right.index):
            failures.append(f"R{replicate} feature keys differ by arm")
        else:
            for field in FEATURE_FIELDS:
                if not _equal_series(left[field], right[field]).all():
                    failures.append(f"R{replicate} invariant feature {field} differs")
        lc = candidates[("mult", replicate)]
        rc = candidates[("k", replicate)]
        roster_keys = ["season", "week", "players"]
        if lc.duplicated(roster_keys).any() or rc.duplicated(roster_keys).any():
            failures.append(f"R{replicate} candidate roster keys repeat")
            continue
        joined = lc.merge(
            rc, on=roster_keys,
            suffixes=("_mult", "_k"), validate="one_to_one",
        )
        if joined.empty:
            failures.append(f"R{replicate} arms have no shared candidates")
        else:
            if not _equal_series(
                joined.actual_score_mult, joined.actual_score_k
            ).all():
                failures.append(f"R{replicate} shared-candidate actuals differ")
            if not _equal_series(
                joined.sim_mean_mult, joined.sim_mean_k, tolerance=1e-4
            ).all():
                failures.append(f"R{replicate} shared-candidate means differ")
        left_membership = set(zip(lc.season, lc.week, lc.players))
        right_membership = set(zip(rc.season, rc.week, rc.players))
        if left_membership == right_membership:
            failures.append(f"R{replicate} candidate membership did not change")
    return failures


def arm_metrics(frame: pd.DataFrame) -> tuple[dict, pd.Series]:
    selected = frame[frame.selected].groupby(
        ["season", "week"]
    ).actual_score.max().sort_index()
    oracle = frame.groupby(["season", "week"]).actual_score.max().sort_index()
    return {
        "selected_tail": {str(t): int(selected.ge(t).sum()) for t in TAILS},
        "oracle_tail": {str(t): int(oracle.ge(t).sum()) for t in TAILS},
        "selected_mean": float(selected.mean()),
        "selected_median": float(selected.median()),
        "candidate_rows": int(len(frame)),
    }, selected


def frozen_decision(metrics: dict[str, dict]) -> dict:
    sums = {
        arm: {
            str(tail): sum(
                metrics[f"{arm}-R{rep}"]["selected_tail"][str(tail)]
                for rep in SEEDS
            )
            for tail in TAILS
        }
        for arm in ("mult", "k")
    }
    deciding_threshold = None
    comparison = 0
    for tail in TAILS:
        comparison = sums["k"][str(tail)] - sums["mult"][str(tail)]
        if comparison:
            deciding_threshold = tail
            break
    aggregate_mean = {
        arm: float(np.mean([
            metrics[f"{arm}-R{rep}"]["selected_mean"] for rep in SEEDS
        ]))
        for arm in ("mult", "k")
    }
    if comparison == 0:
        comparison = int(np.sign(aggregate_mean["k"] - aggregate_mean["mult"]))
    return {
        "selected_tail_sums": sums,
        "selected_tail_means": {
            arm: {key: value / len(SEEDS) for key, value in tails.items()}
            for arm, tails in sums.items()
        },
        "deciding_threshold": deciding_threshold,
        "aggregate_weekly_best_mean": aggregate_mean,
        "selected_arm": "k" if comparison >= 0 else "mult",
        "finite_k_retained_on_exact_tie": comparison == 0,
    }


def result_report(candidates: dict[tuple[str, int], pd.DataFrame]) -> dict:
    metrics: dict[str, dict] = {}
    weekly: dict[tuple[str, int], pd.Series] = {}
    for key, frame in candidates.items():
        label = f"{key[0]}-R{key[1]}"
        metrics[label], weekly[key] = arm_metrics(frame)
    paired = []
    for replicate in SEEDS:
        left = weekly[("mult", replicate)]
        right = weekly[("k", replicate)]
        delta = right - left
        paired.append({
            "replicate": f"R{replicate}",
            "finite_k_weeks_better": int(delta.gt(0).sum()),
            "multinomial_weeks_better": int(delta.lt(0).sum()),
            "ties": int(delta.eq(0).sum()),
            "mean_delta": float(delta.mean()),
            "weeks_abs_delta_at_least_10": int(delta.abs().ge(10).sum()),
        })
    return {
        "panels": {f"{arm}-R{rep}": panel for (arm, rep), panel in PANELS.items()},
        "metrics": metrics,
        "paired_seed_diagnostics": paired,
        "decision": frozen_decision(metrics),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-code-sha", required=True)
    args = parser.parse_args()
    candidates = _load_candidates()
    features = _load_features()
    failures = mechanical_failures(candidates, features, args.expected_code_sha)
    report = {
        "protocol": "2026-08-13-game-team-usage-repair-and-sis-asoe-exact80",
        "phase": "R",
        "mechanical_passes": not failures,
        "failures": failures,
    }
    if not failures:
        report["result"] = result_report(candidates)
    print(OUTPUT_PREFIX + json.dumps(report, separators=(",", ":"), sort_keys=True))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
