#!/usr/bin/env python
"""Mechanical audit and frozen five-seed SIS ASOE Phase S decision."""

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
    0: (0, 7331), 1: (1137260708, 2690847602),
    2: (2875959182, 1630284992), 3: (253722715, 3374646876),
    4: (1643280042, 3977633467),
}
POSITION_SPECS = {
    2023: "QB:0.965,RB:0.99,TE:0.945,WR:1.03",
    2024: "QB:0.905,RB:0.97,TE:0.95,WR:1.06",
    2025: "QB:0.925,RB:0.96,TE:0.94,WR:1.04",
}
TAILS = (240, 230, 220, 210, 200, 194, 187)
FITTED_K = "28.154043586960896"
FROZEN_BETA = "0.07771181538347656"
ROLE_FEATURES = (
    "target_share_last,carry_share_last,snap_share_last,"
    "target_share_jump,carry_share_jump,snap_share_jump"
)
FEATURE_FIELDS = (
    "gsis_id", "name", "pos", "team", "opp", "game_id", "salary",
    "proj", "proj_tourney", "market_points", "model_points_pre",
    "mean_projection", "proj_p10", "proj_p50", "proj_p90", "proj_std",
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
OUTPUT_PREFIX = "SIS_ASOE_PHASE_S_JSON="
BOOTSTRAP_SEED = 8_132_026
BOOTSTRAP_RESAMPLES = 2_000


def _panel(arm: str, replicate: int, control_arm: str) -> str:
    return f"20260813-sis-asoe-{arm}-r{replicate}-v1"


def _parse_pairs(value: str) -> dict[str, str]:
    out = {}
    for item in str(value or "").split(";"):
        key, marker, val = item.partition("=")
        if marker:
            out[key] = val
    return out


def _equal_series(left: pd.Series, right: pd.Series, atol=1e-10) -> pd.Series:
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
    return both_null | (numeric & (ln - rn).abs().le(atol)) | (
        (~numeric) & left.astype(str).eq(right.astype(str))
    )


def _load_candidates(control_arm: str) -> dict[tuple[str, int], pd.DataFrame]:
    fields = (
        "panel_run_id,code_sha,lever_env,seeds,labels_complete,season,week,"
        "cand_ix,selected,selected_rank,players,actual_score,sim_mean,"
        "n_entries,n_sims,n_worlds,score_artifact_uri,"
        "score_artifact_sha256"
    )
    return {
        (arm, replicate): query_df(f"""
            SELECT {fields}
            FROM `{settings.predictions}.replay_candidates_staging`
            WHERE panel_run_id=@panel AND season IN UNNEST(@seasons)
            """, params={
                "panel": _panel(arm, replicate, control_arm),
                "seasons": sorted(POSITION_SPECS),
            })
        for arm in ("control", "treatment") for replicate in SEEDS
    }


def _load_features(control_arm: str) -> dict[tuple[str, int], pd.DataFrame]:
    fields = ",".join(("season", "week", "id", *FEATURE_FIELDS))
    return {
        (arm, replicate): query_df(f"""
            SELECT {fields}
            FROM `{settings.predictions}.slate_player_features`
            WHERE panel_run_id=@panel AND season IN UNNEST(@seasons)
            """, params={
                "panel": _panel(arm, replicate, control_arm),
                "seasons": sorted(POSITION_SPECS),
            })
        for arm in ("control", "treatment") for replicate in SEEDS
    }


def mechanical_failures(candidates, features, code_sha, control_arm):
    failures = []
    for (arm, replicate), frame in candidates.items():
        label = f"{arm}-R{replicate}"
        if frame.empty:
            failures.append(f"{label} is empty")
            continue
        if not frame.code_sha.astype(str).eq(code_sha).all():
            failures.append(f"{label} code SHA differs")
        groups = frame.groupby(["season", "week"])
        if len(groups) != 54 or set(frame.season.astype(int)) != set(POSITION_SPECS):
            failures.append(f"{label} slate/season set differs")
        if not frame.labels_complete.fillna(False).astype(bool).all() or \
                frame.actual_score.isna().any():
            failures.append(f"{label} labels incomplete")
        if not frame.n_entries.eq(80).all() or not frame.n_sims.eq(10000).all() \
                or not frame.n_worlds.eq(10000).all():
            failures.append(f"{label} entries/worlds differ")
        if not groups.selected.sum().eq(80).all() or \
                frame[frame.selected].duplicated(["season", "week", "players"]).any():
            failures.append(f"{label} exact-80 contract differs")
        if frame.duplicated(["season", "week", "cand_ix"]).any():
            failures.append(f"{label} candidate indices repeat")
        artifacts = frame[[
            "season", "week", "score_artifact_uri", "score_artifact_sha256",
        ]].drop_duplicates()
        if len(artifacts) != 54 or artifacts.duplicated(
            ["season", "week"]
        ).any():
            failures.append(f"{label} artifact identity differs by slate")
        elif (
            ~artifacts.score_artifact_uri.astype(str).str.startswith("gs://")
        ).any() or (
            ~artifacts.score_artifact_sha256.astype(str).str.fullmatch(
                r"[0-9a-f]{64}"
            )
        ).any():
            failures.append(f"{label} player-world artifact provenance invalid")
        seeds = frame.seeds.fillna("").astype(str).unique()
        if len(seeds) != 1:
            failures.append(f"{label} seed identity mixed")
        else:
            got = _parse_pairs(seeds[0])
            pair = (int(got.get("REPLAY_PROJECTION_SEED", "0")),
                    int(got.get("ROLE_BELIEF_SEED", "7331")))
            if pair != SEEDS[replicate]:
                failures.append(f"{label} seed pair differs")
        for season, spec in POSITION_SPECS.items():
            values = frame.loc[frame.season.eq(season), "lever_env"].unique()
            if len(values) != 1:
                failures.append(f"{label} {season} lever identity mixed")
                continue
            lever = lever_values(values[0])
            expected = {
                "GAME_SIM_MODE": "possession", "MODEL_ENSEMBLE": "1",
                "TABPFN_MARGINALS": "1",
                "TABPFN_MARGINAL_TABLE": "tabpfn_active_label_treatment_v2",
                "EPISTEMIC_FAMILY": "role_draws",
                "ROLE_BELIEF_FEATURES": ROLE_FEATURES,
                "ROLE_BELIEF_SEED": str(SEEDS[replicate][1]),
                "REPLAY_PROJECTION_SEED": str(SEEDS[replicate][0]),
                "REPLACEMENT_SLOTS": "12", "N_CE": "0",
                "N_EPISTEMIC": "12", "N_GUMBEL": "0", "N_BOOM": "40",
                "SERVED_POSITION_SCALES": spec,
                "CAND_ARTIFACT_PLAYER_WORLDS": "1",
            }
            for key, value in expected.items():
                if lever.get(key) != value:
                    failures.append(f"{label} {season} {key} differs")
            if control_arm == "k":
                if lever.get("GAME_SIM_USAGE") != "dirichlet" or \
                        lever.get("DIRICHLET_K") != FITTED_K:
                    failures.append(f"{label} corrected finite-K law differs")
            elif "GAME_SIM_USAGE" in lever or "DIRICHLET_K" in lever:
                failures.append(f"{label} corrected multinomial law differs")
            if arm == "treatment":
                if lever.get("SIS_ASOE_TARGET_ALLOCATION") != "1" or \
                        lever.get("SIS_ASOE_BETA") != FROZEN_BETA:
                    failures.append(f"{label} ASOE law differs")
            elif "SIS_ASOE_TARGET_ALLOCATION" in lever or "SIS_ASOE_BETA" in lever:
                failures.append(f"{label} unexpectedly enables ASOE")

    keys = ["season", "week", "id"]
    changed_slates = set()
    for replicate in SEEDS:
        left = features[("control", replicate)]
        right = features[("treatment", replicate)]
        if left.empty or right.empty or left.duplicated(keys).any() or \
                right.duplicated(keys).any():
            failures.append(f"R{replicate} feature frames invalid")
        else:
            left = left.set_index(keys).sort_index()
            right = right.set_index(keys).sort_index()
            if not left.index.equals(right.index):
                failures.append(f"R{replicate} feature keys differ")
            else:
                for field in FEATURE_FIELDS:
                    if not _equal_series(left[field], right[field], atol=1e-12).all():
                        failures.append(f"R{replicate} exact marginal feature {field} differs")
        lc = candidates[("control", replicate)]
        rc = candidates[("treatment", replicate)]
        roster_keys = ["season", "week", "players"]
        if lc.duplicated(roster_keys).any() or rc.duplicated(roster_keys).any():
            failures.append(f"R{replicate} candidate roster keys repeat")
            continue
        joined = lc.merge(rc, on=roster_keys, suffixes=("_c", "_t"))
        if joined.empty:
            failures.append(f"R{replicate} has no shared candidates")
        else:
            if not _equal_series(joined.actual_score_c, joined.actual_score_t).all():
                failures.append(f"R{replicate} common actuals differ")
            if not _equal_series(joined.sim_mean_c, joined.sim_mean_t, atol=1e-4).all():
                failures.append(f"R{replicate} common simulated means differ")
        left_sets = {
            key: set(group.players.astype(str))
            for key, group in lc.groupby(["season", "week"])
        }
        right_sets = {
            key: set(group.players.astype(str))
            for key, group in rc.groupby(["season", "week"])
        }
        changed_slates.update(key for key in left_sets if left_sets[key] != right_sets.get(key))
    if len(changed_slates) < 2:
        failures.append("ASOE changes candidate membership on fewer than two slates")
    return failures


def phase_r_reproduction_failures(candidates, control_arm):
    """Same-image Phase S control must reproduce every Phase R candidate.

    A weekly maximum alone is too weak: a changed pool or selected portfolio
    can happen to retain the same best realized score. Candidate index is
    deterministic within a replay, so the complete roster identity, selected
    status/rank, label, and simulated mean form a compact replay fingerprint.
    """
    failures = []
    key = ["season", "week", "cand_ix"]
    for replicate in SEEDS:
        phase_r_panel = f"20260813-game-team-{control_arm}-r{replicate}-v1"
        prior = query_df(f"""
            SELECT season, week, cand_ix, players, selected, selected_rank,
                   actual_score, sim_mean
            FROM `{settings.predictions}.replay_candidates_staging`
            WHERE panel_run_id=@panel AND season IN UNNEST(@seasons)
            """, params={
                "panel": phase_r_panel, "seasons": sorted(POSITION_SPECS),
            })
        current = candidates[("control", replicate)]
        if prior.empty or current.empty or prior.duplicated(key).any() or \
                current.duplicated(key).any():
            failures.append(f"R{replicate} Phase R reproduction frames invalid")
            continue
        columns = key + [
            "players", "selected", "selected_rank", "actual_score", "sim_mean",
        ]
        joined = prior.merge(
            current[columns], on=key, suffixes=("_prior", "_current"),
            validate="one_to_one",
        )
        if len(joined) != len(prior) or len(joined) != len(current):
            failures.append(
                f"R{replicate} same-image control candidate membership differs"
            )
            continue
        for field, tolerance in (
            ("players", 0.0), ("selected", 0.0), ("selected_rank", 0.0),
            ("actual_score", 1e-10), ("sim_mean", 1e-10),
        ):
            if not _equal_series(
                joined[f"{field}_prior"], joined[f"{field}_current"],
                atol=tolerance,
            ).all():
                failures.append(
                    f"R{replicate} same-image control {field} differs from Phase R"
                )
    return failures


def arm_metrics(frame):
    selected = frame[frame.selected].groupby(["season", "week"]).actual_score.max().sort_index()
    oracle = frame.groupby(["season", "week"]).actual_score.max().sort_index()
    return {
        "selected_tail": {str(t): int(selected.ge(t).sum()) for t in TAILS},
        "oracle_tail": {str(t): int(oracle.ge(t).sum()) for t in TAILS},
        "selected_mean": float(selected.mean()),
        "selected_median": float(selected.median()),
        "candidate_rows": int(len(frame)),
    }, selected


def frozen_decision(metrics):
    sums = {
        arm: {str(t): sum(metrics[f"{arm}-R{r}"]["selected_tail"][str(t)] for r in SEEDS)
              for t in TAILS}
        for arm in ("control", "treatment")
    }
    first = None
    comparison = 0
    for tail in TAILS:
        comparison = sums["treatment"][str(tail)] - sums["control"][str(tail)]
        if comparison:
            first = tail
            break
    means = {
        arm: float(np.mean([metrics[f"{arm}-R{r}"]["selected_mean"] for r in SEEDS]))
        for arm in ("control", "treatment")
    }
    if comparison == 0:
        comparison = int(np.sign(means["treatment"] - means["control"]))
    return {
        "selected_tail_sums": sums,
        "selected_tail_means": {
            arm: {key: value / len(SEEDS) for key, value in values.items()}
            for arm, values in sums.items()
        },
        "deciding_threshold": first,
        "aggregate_weekly_best_mean": means,
        "selected_arm": "treatment" if comparison > 0 else "control",
        "control_retained_on_exact_tie": comparison == 0,
    }


def result_report(candidates, control_arm):
    metrics, weekly = {}, {}
    for key, frame in candidates.items():
        label = f"{key[0]}-R{key[1]}"
        metrics[label], weekly[key] = arm_metrics(frame)
    paired = []
    for replicate in SEEDS:
        delta = weekly[("treatment", replicate)] - weekly[("control", replicate)]
        left_selected = candidates[("control", replicate)]
        left_selected = left_selected[left_selected.selected]
        right_selected = candidates[("treatment", replicate)]
        right_selected = right_selected[right_selected.selected]
        overlap = left_selected.merge(
            right_selected, on=["season", "week", "players"]
        ).groupby(["season", "week"]).size()
        paired.append({
            "replicate": f"R{replicate}",
            "treatment_weeks_better": int(delta.gt(0).sum()),
            "control_weeks_better": int(delta.lt(0).sum()),
            "ties": int(delta.eq(0).sum()),
            "mean_delta": float(delta.mean()),
            "weeks_abs_delta_at_least_10": int(delta.abs().ge(10).sum()),
            "mean_selected_overlap_of_80": float(overlap.mean()),
        })
    aligned = pd.DataFrame({
        f"R{replicate}": (
            weekly[("treatment", replicate)]
            - weekly[("control", replicate)]
        )
        for replicate in SEEDS
    })
    cluster_delta = aligned.mean(axis=1).to_numpy(dtype=float)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = np.empty(BOOTSTRAP_RESAMPLES, dtype=float)
    for index in range(BOOTSTRAP_RESAMPLES):
        sample = rng.integers(0, len(cluster_delta), size=len(cluster_delta))
        draws[index] = float(cluster_delta[sample].mean())
    return {
        "control_allocation": control_arm,
        "metrics": metrics,
        "paired_seed_diagnostics": paired,
        "slate_clustered_bootstrap_diagnostic": {
            "clusters": int(len(cluster_delta)),
            "seed_replicates_averaged_within_cluster": len(SEEDS),
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
            "mean_delta": float(cluster_delta.mean()),
            "ci95": [
                float(np.quantile(draws, 0.025)),
                float(np.quantile(draws, 0.975)),
            ],
        },
        "decision": frozen_decision(metrics),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--control-arm", choices=("mult", "k"), required=True)
    args = parser.parse_args()
    candidates = _load_candidates(args.control_arm)
    features = _load_features(args.control_arm)
    failures = mechanical_failures(
        candidates, features, args.expected_code_sha, args.control_arm
    )
    failures.extend(phase_r_reproduction_failures(candidates, args.control_arm))
    report = {
        "protocol": "2026-08-13-game-team-usage-repair-and-sis-asoe-exact80",
        "phase": "S", "mechanical_passes": not failures, "failures": failures,
    }
    if not failures:
        report["result"] = result_report(candidates, args.control_arm)
    print(OUTPUT_PREFIX + json.dumps(report, separators=(",", ":"), sort_keys=True))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
