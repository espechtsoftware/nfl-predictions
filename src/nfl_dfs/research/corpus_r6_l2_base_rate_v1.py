"""Leakage-safe empirical fallback for the R6 L2 role-jump law.

The first L2 candidate fits a multinomial logistic transition model.  This
fallback intentionally does less: it reuses the Dirichlet-one empirical
transition baseline that was fixed before the first L2 holdout was read.
Probabilities are conditioned only on ``(position, previous_state)``.  The
comparison law drops ``previous_state`` and conditions only on position.

The module reads role labels and player residuals, never lineup outcomes.  It
may license construction of a historical challenger bank only after the
pre-existing empirical law improves both proper role-state scores and both
team-exclusive jump scores on HOLD22, while remaining noninferior on WF21.
Production authority is always false.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import math
import re
from typing import Final

import numpy as np
import pandas as pd

from .belief_world_v1 import (
    CALIBRATION_FOLDS,
    calibration_fold_registry,
    canonical_json_bytes,
    canonical_sha256,
)
from .corpus_r6_belief_calibration_v1 import (
    CALIBRATION_SEASONS,
    L2_EFFECTIVE_FIRST_SEASON,
    L2_RESIDUAL_COLUMNS,
    BeliefCalibrationError,
    L2RoleJumpApplication,
    _validate_residual_history,
    _validate_role_history,
)
from .latent_role_state import (
    FORBIDDEN_OUTCOME_COLUMNS,
    POSITIONS,
    STATES,
    TARGET,
    empirical_transition_probabilities,
    multiclass_scores,
    prepare_transition_frame,
    transition_frame_sha256,
)
from .object_identity import IDENTITY_FIELDS, content_identity


L2B_SCHEMA: Final = "corpus-r6-l2-base-rate-calibration-release/v1"
L2B_APPLICATION_SCHEMA: Final = "corpus-r6-l2-base-rate-application/v1"
L2B_HISTORICAL_APPLICATION_SCHEMA: Final = (
    "corpus-r6-l2-base-rate-historical-application/v1"
)
L2B_CANDIDATE: Final = (
    "dirichlet-one-position-previous-state-empirical-transition"
)
L2B_COMPARATOR: Final = "dirichlet-one-position-only-empirical-transition"
PREVIOUS_STATES: Final = (*STATES, "unknown")

_SHA40: Final = re.compile(r"[0-9a-f]{40}")
_SHA64: Final = re.compile(r"[0-9a-f]{64}")
_LINEUP_OUTCOME_FIELDS: Final = frozenset({
    "lineup_score",
    "selected_score",
    "winner_score",
    "payout",
    "roi",
    "winnings",
    "rank",
    "finish_position",
    "player_actual_points",
    TARGET,
})


@dataclass(frozen=True, slots=True)
class _FoldResult:
    summary: dict[str, object]
    residuals: tuple[tuple[str, float], ...]


def _array_sha256(value: np.ndarray, *, dtype: str = "<f8") -> str:
    stable = np.ascontiguousarray(value, dtype=np.dtype(dtype))
    header = canonical_json_bytes({"dtype": dtype, "shape": list(stable.shape)})
    return sha256(header + b"\0" + stable.tobytes(order="C")).hexdigest()


def _records_sha256(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    records: list[dict[str, object]] = []
    for values in frame.loc[:, list(columns)].itertuples(index=False, name=None):
        record: dict[str, object] = {}
        for name, value in zip(columns, values, strict=True):
            if isinstance(value, np.integer):
                value = int(value)
            elif isinstance(value, np.floating):
                value = float(value)
            elif isinstance(value, np.bool_):
                value = bool(value)
            record[str(name)] = value
        records.append(record)
    return canonical_sha256(records)


def _source_identities(
    values: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    if not isinstance(values, Mapping) or not values:
        raise BeliefCalibrationError("L2b source identities are empty")
    result: dict[str, dict[str, object]] = {}
    for label in sorted(values):
        if not isinstance(label, str) or not label:
            raise BeliefCalibrationError("L2b source label differs")
        try:
            identity = content_identity(values[label])
        except (TypeError, ValueError) as exc:
            raise BeliefCalibrationError(
                f"L2b source identity {label!r} differs"
            ) from exc
        result[label] = dict(zip(IDENTITY_FIELDS, identity, strict=True))
    return result


def _binary_scores(truth: np.ndarray, probability: np.ndarray) -> dict[str, float]:
    labels = np.asarray(truth, dtype=np.float64)
    values = np.asarray(probability, dtype=np.float64)
    if (
        labels.ndim != 1
        or values.shape != labels.shape
        or not np.isfinite(values).all()
        or not np.isin(labels, (0.0, 1.0)).all()
        or np.any(values < 0.0)
        or np.any(values > 1.0)
    ):
        raise BeliefCalibrationError("L2b binary score inputs differ")
    clipped = np.clip(values, 1e-15, 1.0 - 1e-15)
    return {
        "log_loss": float(-np.mean(
            labels * np.log(clipped) + (1.0 - labels) * np.log(1.0 - clipped)
        )),
        "brier": float(np.mean((values - labels) ** 2)),
    }


def _position_only_probabilities(
    training: pd.DataFrame,
    target: pd.DataFrame,
) -> pd.DataFrame:
    train = prepare_transition_frame(training)
    test = prepare_transition_frame(target)
    counts = train.groupby(["position", TARGET], observed=True).size()
    rows: list[list[float]] = []
    for item in test.itertuples(index=False):
        values = np.ones(len(STATES), dtype=np.float64)
        for index, state in enumerate(STATES):
            values[index] += float(counts.get((item.position, state), 0))
        rows.append((values / values.sum()).tolist())
    return pd.DataFrame(rows, columns=STATES, index=test.index)


def _modal_and_above(
    probabilities: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    values = probabilities.loc[:, list(STATES)].to_numpy(dtype=np.float64)
    modal = np.argmax(values, axis=1).astype(np.int16)
    above = np.asarray([
        float(values[row_index, state_index + 1 :].sum())
        for row_index, state_index in enumerate(modal)
    ])
    return modal, above


def _above_fixed_modal(
    probabilities: pd.DataFrame,
    modal: np.ndarray,
) -> np.ndarray:
    values = probabilities.loc[:, list(STATES)].to_numpy(dtype=np.float64)
    return np.asarray([
        float(values[row_index, state_index + 1 :].sum())
        for row_index, state_index in enumerate(modal)
    ])


def _team_exclusive_projection(
    rows: pd.DataFrame,
    raw_probability: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, tuple[np.ndarray, ...]]:
    raw = np.asarray(raw_probability, dtype=np.float64)
    if len(rows) != len(raw):
        raise BeliefCalibrationError("L2b player probabilities do not align")
    keys = rows[["season", "week", "team"]].astype(str).agg(":".join, axis=1)
    key_values = keys.to_numpy()
    result = np.zeros(len(rows), dtype=np.float64)
    team_any: list[float] = []
    groups: list[np.ndarray] = []
    for key in dict.fromkeys(key_values):
        indexes = np.flatnonzero(key_values == key)
        values = np.clip(raw[indexes], 0.0, 1.0)
        any_probability = float(1.0 - np.prod(1.0 - values))
        total = float(values.sum())
        if total > 0.0:
            result[indexes] = any_probability * values / total
        team_any.append(any_probability)
        groups.append(indexes)
    if np.any(result < -1e-12) or np.any(result > 1.0 + 1e-12):
        raise BeliefCalibrationError("L2b team-exclusive probabilities differ")
    return result, np.asarray(team_any), tuple(groups)


def _fold_result(
    roles: pd.DataFrame,
    residual_history: pd.DataFrame,
    *,
    fold,
) -> _FoldResult:
    first = max(L2_EFFECTIVE_FIRST_SEASON, fold.component_train_first_season)
    training = roles[roles["season"].between(
        first, fold.component_train_last_season
    )]
    target = roles[roles["season"].eq(fold.season)]
    if training.empty or target.empty:
        raise BeliefCalibrationError(f"L2b fold {fold.fold_id} lacks rows")

    candidate = empirical_transition_probabilities(training, target)
    comparator = _position_only_probabilities(training, target)
    truth = target.loc[candidate.index, TARGET]
    candidate_multiclass = multiclass_scores(truth, candidate)
    comparator_multiclass = multiclass_scores(truth, comparator)

    modal, raw_candidate = _modal_and_above(candidate)
    raw_comparator = _above_fixed_modal(comparator, modal)
    truth_index = np.asarray([STATES.index(str(value)) for value in truth])
    jump = truth_index > modal
    candidate_projected, candidate_team_any, groups = _team_exclusive_projection(
        target, raw_candidate
    )
    comparator_projected, comparator_team_any, comparator_groups = (
        _team_exclusive_projection(target, raw_comparator)
    )
    if any(
        not np.array_equal(left, right)
        for left, right in zip(groups, comparator_groups, strict=True)
    ):
        raise BeliefCalibrationError("L2b comparator team groups differ")
    team_jump_counts = np.asarray([
        int(jump[indexes].sum()) for indexes in groups
    ])
    team_any_truth = team_jump_counts > 0

    residual_target = residual_history[residual_history["season"].eq(
        fold.season
    )]
    merged = target[["gsis_id", "season", "week", "position"]].copy()
    merged["actual_jump"] = jump
    merged = merged.merge(
        residual_target,
        on=["gsis_id", "season", "week"],
        how="left",
        validate="one_to_one",
    )
    if merged[["ordinary_mean", "player_actual_points"]].isna().any().any():
        raise BeliefCalibrationError(f"L2b fold {fold.fold_id} lacks residuals")
    jump_rows = merged[merged["actual_jump"]].copy()
    jump_rows["residual"] = (
        jump_rows["player_actual_points"] - jump_rows["ordinary_mean"]
    )
    residuals = tuple(
        (str(row.position), float(row.residual))
        for row in jump_rows.itertuples(index=False)
    )

    summary: dict[str, object] = {
        "season": fold.season,
        "phase": fold.phase,
        "effective_role_train_first_season": first,
        "train_last_season": fold.component_train_last_season,
        "train_rows": len(training),
        "test_rows": len(target),
        "candidate_log_loss": candidate_multiclass["log_loss"],
        "candidate_multiclass_brier": candidate_multiclass[
            "multiclass_brier"
        ],
        "comparator_log_loss": comparator_multiclass["log_loss"],
        "comparator_multiclass_brier": comparator_multiclass[
            "multiclass_brier"
        ],
        "actual_player_jump_rate": float(jump.mean()),
        "mean_raw_candidate_jump_probability": float(raw_candidate.mean()),
        "mean_raw_comparator_jump_probability": float(raw_comparator.mean()),
        "candidate_raw_jump_scores": _binary_scores(jump, raw_candidate),
        "comparator_raw_jump_scores": _binary_scores(jump, raw_comparator),
        "mean_competing_candidate_probability": float(
            candidate_projected.mean()
        ),
        "mean_competing_comparator_probability": float(
            comparator_projected.mean()
        ),
        "candidate_competing_jump_scores": _binary_scores(
            jump, candidate_projected
        ),
        "comparator_competing_jump_scores": _binary_scores(
            jump, comparator_projected
        ),
        "candidate_team_any_jump_scores": _binary_scores(
            team_any_truth, candidate_team_any
        ),
        "comparator_team_any_jump_scores": _binary_scores(
            team_any_truth, comparator_team_any
        ),
        "team_count": len(groups),
        "team_multi_jump_count": int(np.sum(team_jump_counts > 1)),
        "team_multi_jump_rate": float(np.mean(team_jump_counts > 1)),
        "jump_residual_count": len(residuals),
    }
    return _FoldResult(summary=summary, residuals=residuals)


def _transition_tables(
    roles: pd.DataFrame,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    training = prepare_transition_frame(roles)
    group_counts = training.groupby(
        ["position", "previous_state", TARGET], observed=True
    ).size()
    position_counts = training.groupby(["position", TARGET], observed=True).size()
    candidate: list[dict[str, object]] = []
    comparator: list[dict[str, object]] = []
    for position in POSITIONS:
        position_values = np.ones(len(STATES), dtype=np.float64)
        position_state_counts: dict[str, int] = {}
        for index, state in enumerate(STATES):
            count = int(position_counts.get((position, state), 0))
            position_state_counts[state] = count
            position_values[index] += count
        comparator.append({
            "position": position,
            "state_counts": position_state_counts,
            "probabilities": {
                state: float(position_values[index] / position_values.sum())
                for index, state in enumerate(STATES)
            },
        })
        observed_previous = sorted(
            str(value)
            for value in training.loc[
                training["position"].eq(position), "previous_state"
            ].unique()
        )
        if set(observed_previous) - set(PREVIOUS_STATES):
            raise BeliefCalibrationError("L2b previous-state support differs")
        for previous_state in observed_previous:
            values = np.ones(len(STATES), dtype=np.float64)
            state_counts: dict[str, int] = {}
            for index, state in enumerate(STATES):
                count = int(group_counts.get((position, previous_state, state), 0))
                state_counts[state] = count
                values[index] += count
            candidate.append({
                "position": position,
                "previous_state": previous_state,
                "state_counts": state_counts,
                "probabilities": {
                    state: float(values[index] / values.sum())
                    for index, state in enumerate(STATES)
                },
            })
    return candidate, comparator


def _residual_payload(
    collected: Mapping[str, Sequence[float]],
    *,
    minimum_group_support: int,
) -> tuple[dict[str, list[float]], dict[str, dict[str, object]], bool]:
    samples: dict[str, list[float]] = {}
    summaries: dict[str, dict[str, object]] = {}
    passes = True
    for position in POSITIONS:
        values = np.asarray(collected[position], dtype=np.float64)
        supported = (
            len(values) >= minimum_group_support
            and np.isfinite(values).all()
            and float(values.mean()) > 0.0
            and float(np.quantile(values, 0.9)) > 0.0
        )
        passes = passes and bool(supported)
        samples[position] = [float(value) for value in values]
        summaries[position] = {
            "count": len(values),
            "samples_sha256": _array_sha256(values),
            "mean": float(values.mean()) if len(values) else None,
            "q50": float(np.quantile(values, 0.5)) if len(values) else None,
            "q90": float(np.quantile(values, 0.9)) if len(values) else None,
            "passes": bool(supported),
        }
    return samples, summaries, passes


def _historical_application_entry(
    *,
    fold,
    role_training: pd.DataFrame,
    prior_residuals: Mapping[str, Sequence[float]],
    residual_source_fold_ids: Sequence[str],
    minimum_group_support: int,
) -> dict[str, object]:
    transition_table, fallback_table = _transition_tables(role_training)
    samples, summaries, supported = _residual_payload(
        prior_residuals,
        minimum_group_support=minimum_group_support,
    )
    fold_season = {
        item.fold_id: item.season for item in CALIBRATION_FOLDS
    }
    body: dict[str, object] = {
        "fold_id": fold.fold_id,
        "target_season": fold.season,
        "role_train_first_season": L2_EFFECTIVE_FIRST_SEASON,
        "role_train_last_season": fold.component_train_last_season,
        "role_train_row_count": len(role_training),
        "role_training_frame_sha256": transition_frame_sha256(role_training),
        "transition_table": transition_table,
        "position_fallback_table": fallback_table,
        "transition_table_sha256": canonical_sha256(transition_table),
        "position_fallback_table_sha256": canonical_sha256(fallback_table),
        "residual_source_fold_ids": list(residual_source_fold_ids),
        "residual_source_seasons": [
            fold_season[str(fold_id)] for fold_id in residual_source_fold_ids
        ],
        "residual_samples_by_group": samples,
        "residual_group_summaries": summaries,
        "residual_samples_sha256": canonical_sha256(samples),
        "minimum_group_support": minimum_group_support,
        "uses_target_role_labels_for_fit": False,
        "uses_target_player_outcomes_for_fit": False,
        "application_ready": bool(supported),
        "historical_lineup_scoring_licensed": False,
        "production_change_licensed": False,
    }
    body["application_sha256"] = canonical_sha256(body)
    return body


def build_l2_base_rate_calibration_release_v1(
    *,
    role_history: pd.DataFrame,
    residual_history: pd.DataFrame,
    source_identities: Mapping[str, Mapping[str, object]],
    code_sha: str,
    minimum_group_support: int = 20,
) -> dict[str, object]:
    """Build the single prespecified L2b empirical calibration release."""
    if not _SHA40.fullmatch(str(code_sha)):
        raise BeliefCalibrationError("L2b calibration requires a full code SHA")
    if type(minimum_group_support) is not int or minimum_group_support < 20:
        raise BeliefCalibrationError("L2b minimum support must be at least 20")
    roles = _validate_role_history(role_history)
    label_ids = roles[roles["season"].isin(CALIBRATION_SEASONS)][
        ["gsis_id", "season", "week"]
    ]
    residuals = _validate_residual_history(residual_history, label_ids)

    folds: dict[str, dict[str, object]] = {}
    historical_applications: dict[str, dict[str, object]] = {}
    collected: dict[str, list[float]] = {position: [] for position in POSITIONS}
    for fold in CALIBRATION_FOLDS:
        first = max(
            L2_EFFECTIVE_FIRST_SEASON, fold.component_train_first_season
        )
        role_training = roles[roles["season"].between(
            first, fold.component_train_last_season
        )]
        historical_applications[fold.fold_id] = _historical_application_entry(
            fold=fold,
            role_training=role_training,
            prior_residuals=collected,
            residual_source_fold_ids=fold.prior_label_folds,
            minimum_group_support=minimum_group_support,
        )
        result = _fold_result(roles, residuals, fold=fold)
        folds[fold.fold_id] = result.summary
        for position, residual in result.residuals:
            if position not in collected:
                raise BeliefCalibrationError("L2b residual position differs")
            collected[position].append(residual)

    residual_samples, residual_summaries, residual_gate = _residual_payload(
        collected,
        minimum_group_support=minimum_group_support,
    )

    wf21 = folds["WF21"]
    hold22 = folds["HOLD22"]
    gate = {
        "wf21_multiclass_noninferior": (
            wf21["candidate_log_loss"] <= wf21["comparator_log_loss"] + 1e-12
            and wf21["candidate_multiclass_brier"]
            <= wf21["comparator_multiclass_brier"] + 1e-12
        ),
        "wf21_competing_jump_noninferior": (
            wf21["candidate_competing_jump_scores"]["log_loss"]
            <= wf21["comparator_competing_jump_scores"]["log_loss"] + 1e-12
            and wf21["candidate_competing_jump_scores"]["brier"]
            <= wf21["comparator_competing_jump_scores"]["brier"] + 1e-12
        ),
        "hold22_multiclass_improves": (
            hold22["candidate_log_loss"] < hold22["comparator_log_loss"]
            and hold22["candidate_multiclass_brier"]
            < hold22["comparator_multiclass_brier"]
        ),
        "hold22_competing_jump_improves": (
            hold22["candidate_competing_jump_scores"]["log_loss"]
            < hold22["comparator_competing_jump_scores"]["log_loss"]
            and hold22["candidate_competing_jump_scores"]["brier"]
            < hold22["comparator_competing_jump_scores"]["brier"]
        ),
        "residual_support_and_positive_component": residual_gate,
    }
    gate["passes"] = all(bool(value) for value in gate.values())
    final_roles = roles[roles["season"].between(
        L2_EFFECTIVE_FIRST_SEASON, 2022
    )]
    transition_table, comparator_table = _transition_tables(final_roles)
    body: dict[str, object] = {
        "schema": L2B_SCHEMA,
        "code_sha": str(code_sha),
        "fold_registry_sha256": calibration_fold_registry()["registry_sha256"],
        "effective_role_source_first_season": L2_EFFECTIVE_FIRST_SEASON,
        "candidate_definition": L2B_CANDIDATE,
        "comparator_definition": L2B_COMPARATOR,
        "smoothing_pseudocount_per_state": 1,
        "hyperparameter_search_performed": False,
        "candidate_preexisting_as_exact_l2_baseline": True,
        "post_failure_fallback_evaluation_disclosed": True,
        "folds": folds,
        "historical_application_registry": historical_applications,
        "historical_application_registry_sha256": canonical_sha256(
            historical_applications
        ),
        "final_fit_seasons": list(range(L2_EFFECTIVE_FIRST_SEASON, 2023)),
        "final_fit_scope": "prospective-2023-plus-only",
        "transition_table": transition_table,
        "position_fallback_table": comparator_table,
        "probability_law": {
            "raw_player_probability": (
                "empirical-mass-strictly-above-empirical-modal-state"
            ),
            "modal_tie_break": "lower-state",
            "unseen_position_previous_state_fallback": "position-only-table",
            "team_projection": (
                "independent-any-jump-proportional-competing-risk"
            ),
            "maximum_selected_jumps_per_team_world": 1,
        },
        "residual_samples_by_group": residual_samples,
        "residual_group_summaries": residual_summaries,
        "role_history_sha256": transition_frame_sha256(roles),
        "residual_evidence_sha256": _records_sha256(
            residuals, L2_RESIDUAL_COLUMNS
        ),
        "minimum_group_support": minimum_group_support,
        "source_identities": _source_identities(source_identities),
        "gate": gate,
        "uses_role_labels": True,
        "uses_player_outcomes_for_residual_amplitude": True,
        "uses_lineup_outcomes": False,
        "prospective_challenger_bank_generation_licensed": bool(
            gate["passes"]
        ),
        "historical_lineup_scoring_licensed": False,
        "production_change_licensed": False,
    }
    seed_hash = canonical_sha256(body)
    body["calibration_id"] = (
        f"r6-l2b-cal19-wf21-hold22-{seed_hash[:16]}"
    )
    body["release_sha256"] = canonical_sha256(body)
    validate_l2_base_rate_calibration_release_v1(body)
    return body


def _validate_probability_table(
    rows: object,
    *,
    candidate: bool,
) -> None:
    if not isinstance(rows, list) or not rows:
        raise BeliefCalibrationError("L2b transition table differs")
    expected_keys = {"position", "state_counts", "probabilities"}
    if candidate:
        expected_keys.add("previous_state")
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != expected_keys:
            raise BeliefCalibrationError("L2b transition table row differs")
        position = str(row["position"])
        if position not in POSITIONS:
            raise BeliefCalibrationError("L2b transition position differs")
        key = (position,)
        if candidate:
            previous = str(row["previous_state"])
            if previous not in PREVIOUS_STATES:
                raise BeliefCalibrationError("L2b previous state differs")
            key = (position, previous)
        if key in seen:
            raise BeliefCalibrationError("L2b transition keys repeat")
        seen.add(key)
        counts = row["state_counts"]
        probabilities = row["probabilities"]
        if (
            not isinstance(counts, Mapping)
            or set(counts) != set(STATES)
            or not isinstance(probabilities, Mapping)
            or set(probabilities) != set(STATES)
            or any(
                type(counts[state]) is not int or counts[state] < 0
                for state in STATES
            )
        ):
            raise BeliefCalibrationError("L2b transition content differs")
        values = np.asarray([probabilities[state] for state in STATES], dtype=float)
        if (
            not np.isfinite(values).all()
            or np.any(values <= 0.0)
            or not math.isclose(float(values.sum()), 1.0, abs_tol=1e-12)
        ):
            raise BeliefCalibrationError("L2b transition probabilities differ")


def _validate_residual_groups(
    samples: object,
    summaries: object,
    *,
    minimum: int,
    allow_unsupported: bool,
) -> bool:
    if (
        not isinstance(samples, Mapping)
        or set(samples) != set(POSITIONS)
        or not isinstance(summaries, Mapping)
        or set(summaries) != set(POSITIONS)
    ):
        raise BeliefCalibrationError("L2b residual groups differ")
    all_supported = True
    for position in POSITIONS:
        values = np.asarray(samples[position], dtype=np.float64)
        summary = summaries[position]
        supported = (
            len(values) >= minimum
            and np.isfinite(values).all()
            and float(values.mean()) > 0.0
            and float(np.quantile(values, 0.9)) > 0.0
        )
        all_supported = all_supported and bool(supported)
        if (
            values.ndim != 1
            or not np.isfinite(values).all()
            or not isinstance(summary, Mapping)
            or summary.get("count") != len(values)
            or summary.get("samples_sha256") != _array_sha256(values)
            or summary.get("passes") is not bool(supported)
        ):
            raise BeliefCalibrationError("L2b residual group content differs")
    if not allow_unsupported and not all_supported:
        raise BeliefCalibrationError("L2b residual group support differs")
    return all_supported


def _validate_historical_application_registry(
    value: object,
    *,
    minimum: int,
) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        fold.fold_id for fold in CALIBRATION_FOLDS
    }:
        raise BeliefCalibrationError("L2b historical application registry differs")
    fold_by_id = {fold.fold_id: fold for fold in CALIBRATION_FOLDS}
    for fold_id, entry in value.items():
        fold = fold_by_id[str(fold_id)]
        expected = {
            "fold_id", "target_season", "role_train_first_season",
            "role_train_last_season", "role_train_row_count",
            "role_training_frame_sha256", "transition_table",
            "position_fallback_table", "transition_table_sha256",
            "position_fallback_table_sha256", "residual_source_fold_ids",
            "residual_source_seasons", "residual_samples_by_group",
            "residual_group_summaries", "residual_samples_sha256",
            "minimum_group_support", "uses_target_role_labels_for_fit",
            "uses_target_player_outcomes_for_fit", "application_ready",
            "historical_lineup_scoring_licensed", "production_change_licensed",
            "application_sha256",
        }
        if (
            not isinstance(entry, Mapping)
            or set(entry) != expected
            or entry.get("fold_id") != fold.fold_id
            or entry.get("target_season") != fold.season
            or entry.get("role_train_first_season") != 2018
            or entry.get("role_train_last_season")
            != fold.component_train_last_season
            or type(entry.get("role_train_row_count")) is not int
            or entry["role_train_row_count"] <= 0
            or entry.get("minimum_group_support") != minimum
            or entry.get("residual_source_fold_ids")
            != list(fold.prior_label_folds)
            or entry.get("residual_source_seasons") != [
                fold_by_id[name].season for name in fold.prior_label_folds
            ]
            or entry.get("uses_target_role_labels_for_fit") is not False
            or entry.get("uses_target_player_outcomes_for_fit") is not False
            or entry.get("historical_lineup_scoring_licensed") is not False
            or entry.get("production_change_licensed") is not False
        ):
            raise BeliefCalibrationError(
                f"L2b historical application {fold_id} differs"
            )
        if not _SHA64.fullmatch(
            str(entry.get("role_training_frame_sha256", ""))
        ):
            raise BeliefCalibrationError("L2b historical train hash differs")
        _validate_probability_table(entry["transition_table"], candidate=True)
        _validate_probability_table(
            entry["position_fallback_table"], candidate=False
        )
        if (
            entry.get("transition_table_sha256")
            != canonical_sha256(entry["transition_table"])
            or entry.get("position_fallback_table_sha256")
            != canonical_sha256(entry["position_fallback_table"])
            or entry.get("residual_samples_sha256")
            != canonical_sha256(entry["residual_samples_by_group"])
        ):
            raise BeliefCalibrationError(
                "L2b historical application content hash differs"
            )
        supported = _validate_residual_groups(
            entry["residual_samples_by_group"],
            entry["residual_group_summaries"],
            minimum=minimum,
            allow_unsupported=True,
        )
        if entry.get("application_ready") is not bool(supported):
            raise BeliefCalibrationError(
                "L2b historical application readiness differs"
            )
        digest = entry.get("application_sha256")
        body = dict(entry)
        body.pop("application_sha256", None)
        if digest != canonical_sha256(body):
            raise BeliefCalibrationError(
                "L2b historical application hash differs"
            )


def validate_l2_base_rate_calibration_release_v1(
    value: Mapping[str, object],
) -> dict[str, object]:
    expected = {
        "schema", "code_sha", "fold_registry_sha256",
        "effective_role_source_first_season", "candidate_definition",
        "comparator_definition", "smoothing_pseudocount_per_state",
        "hyperparameter_search_performed",
        "candidate_preexisting_as_exact_l2_baseline",
        "post_failure_fallback_evaluation_disclosed", "folds",
        "historical_application_registry",
        "historical_application_registry_sha256", "final_fit_seasons",
        "final_fit_scope", "transition_table", "position_fallback_table",
        "probability_law", "residual_samples_by_group",
        "residual_group_summaries", "role_history_sha256",
        "residual_evidence_sha256", "minimum_group_support",
        "source_identities", "gate", "uses_role_labels",
        "uses_player_outcomes_for_residual_amplitude", "uses_lineup_outcomes",
        "prospective_challenger_bank_generation_licensed",
        "historical_lineup_scoring_licensed", "production_change_licensed",
        "calibration_id", "release_sha256",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != expected
        or value.get("schema") != L2B_SCHEMA
        or value.get("candidate_definition") != L2B_CANDIDATE
        or value.get("comparator_definition") != L2B_COMPARATOR
        or value.get("smoothing_pseudocount_per_state") != 1
        or value.get("hyperparameter_search_performed") is not False
        or value.get("candidate_preexisting_as_exact_l2_baseline") is not True
        or value.get("post_failure_fallback_evaluation_disclosed") is not True
    ):
        raise BeliefCalibrationError("L2b calibration release schema differs")
    if not _SHA40.fullmatch(str(value.get("code_sha", ""))):
        raise BeliefCalibrationError("L2b code SHA differs")
    if value.get("fold_registry_sha256") != calibration_fold_registry()[
        "registry_sha256"
    ]:
        raise BeliefCalibrationError("L2b fold registry differs")
    if value.get("effective_role_source_first_season") != 2018:
        raise BeliefCalibrationError("L2b source boundary differs")
    if not isinstance(value.get("folds"), Mapping) or set(value["folds"]) != {
        "CAL19", "WF21", "HOLD22"
    }:
        raise BeliefCalibrationError("L2b folds differ")
    minimum = value.get("minimum_group_support")
    if type(minimum) is not int or minimum < 20:
        raise BeliefCalibrationError("L2b minimum support differs")
    _validate_historical_application_registry(
        value.get("historical_application_registry"),
        minimum=minimum,
    )
    if value.get("historical_application_registry_sha256") != canonical_sha256(
        value["historical_application_registry"]
    ):
        raise BeliefCalibrationError("L2b historical registry hash differs")
    if (
        value.get("final_fit_seasons") != list(range(2018, 2023))
        or value.get("final_fit_scope") != "prospective-2023-plus-only"
    ):
        raise BeliefCalibrationError("L2b prospective fit scope differs")
    _validate_probability_table(value.get("transition_table"), candidate=True)
    _validate_probability_table(
        value.get("position_fallback_table"), candidate=False
    )
    if value.get("probability_law") != {
        "raw_player_probability": (
            "empirical-mass-strictly-above-empirical-modal-state"
        ),
        "modal_tie_break": "lower-state",
        "unseen_position_previous_state_fallback": "position-only-table",
        "team_projection": "independent-any-jump-proportional-competing-risk",
        "maximum_selected_jumps_per_team_world": 1,
    }:
        raise BeliefCalibrationError("L2b probability law differs")
    _validate_residual_groups(
        value.get("residual_samples_by_group"),
        value.get("residual_group_summaries"),
        minimum=minimum,
        allow_unsupported=False,
    )
    gate_names = (
        "wf21_multiclass_noninferior",
        "wf21_competing_jump_noninferior",
        "hold22_multiclass_improves",
        "hold22_competing_jump_improves",
        "residual_support_and_positive_component",
    )
    gate = value.get("gate")
    if (
        not isinstance(gate, Mapping)
        or set(gate) != {*gate_names, "passes"}
        or gate["passes"] is not all(bool(gate[name]) for name in gate_names)
        or value.get("prospective_challenger_bank_generation_licensed")
        is not gate["passes"]
    ):
        raise BeliefCalibrationError("L2b gate differs")
    for flag, expected_value in {
        "uses_role_labels": True,
        "uses_player_outcomes_for_residual_amplitude": True,
        "uses_lineup_outcomes": False,
        "historical_lineup_scoring_licensed": False,
        "production_change_licensed": False,
    }.items():
        if value.get(flag) is not expected_value:
            raise BeliefCalibrationError(f"L2b {flag} differs")
    _source_identities(value.get("source_identities"))
    for name in (
        "role_history_sha256", "residual_evidence_sha256", "release_sha256"
    ):
        if not _SHA64.fullmatch(str(value.get(name, ""))):
            raise BeliefCalibrationError(f"L2b {name} differs")
    digest = value.get("release_sha256")
    body = dict(value)
    body.pop("release_sha256", None)
    if digest != canonical_sha256(body):
        raise BeliefCalibrationError("L2b calibration content hash differs")
    return dict(value)


def _apply_l2_base_rate_tables_v1(
    *,
    target_players: pd.DataFrame,
    transition_table: Sequence[Mapping[str, object]],
    position_fallback_table: Sequence[Mapping[str, object]],
    receipt_context: Mapping[str, object],
) -> L2RoleJumpApplication:
    required = {"gsis_id", "team", "position", "previous_state", "injury_status"}
    if not isinstance(target_players, pd.DataFrame) or (
        missing := required - set(target_players.columns)
    ):
        raise BeliefCalibrationError(
            f"L2b target players missing columns {sorted(missing)}"
        )
    forbidden = _LINEUP_OUTCOME_FIELDS | FORBIDDEN_OUTCOME_COLUMNS
    if forbidden & {str(name).lower() for name in target_players.columns}:
        raise BeliefCalibrationError("L2b target players expose outcomes")
    target = target_players.copy().reset_index(drop=True)
    target["gsis_id"] = target["gsis_id"].astype("string")
    target["team"] = target["team"].astype("string")
    target["position"] = target["position"].astype("string").str.upper()
    target["previous_state"] = target["previous_state"].fillna(
        "unknown"
    ).astype("string")
    if (
        target.empty
        or target["gsis_id"].isna().any()
        or target["gsis_id"].duplicated().any()
        or target["team"].isna().any()
        or not target["position"].isin(POSITIONS).all()
        or not target["previous_state"].isin(PREVIOUS_STATES).all()
    ):
        raise BeliefCalibrationError("L2b target player identities differ")

    candidate = {
        (str(row["position"]), str(row["previous_state"])): row["probabilities"]
        for row in transition_table
    }
    fallback = {
        str(row["position"]): row["probabilities"]
        for row in position_fallback_table
    }
    probability_rows: list[list[float]] = []
    for row in target.itertuples(index=False):
        values = candidate.get((str(row.position), str(row.previous_state)))
        if values is None:
            values = fallback[str(row.position)]
        probability_rows.append([float(values[state]) for state in STATES])
    state_probability = pd.DataFrame(probability_rows, columns=STATES)
    modal, raw = _modal_and_above(state_probability)
    injury = target["injury_status"].fillna("").astype(str).str.upper()
    raw[injury.eq("OUT").to_numpy()] = 0.0
    competition = target.assign(season=0, week=1)
    competing, _, _ = _team_exclusive_projection(competition, raw)
    groups = tuple(str(value) for value in target["position"])
    body: dict[str, object] = {
        **dict(receipt_context),
        "player_count": len(target),
        "ordered_player_ids_sha256": canonical_sha256(
            target["gsis_id"].tolist()
        ),
        "ordered_team_ids_sha256": canonical_sha256(target["team"].tolist()),
        "empirical_group_by_player_sha256": canonical_sha256(list(groups)),
        "state_probabilities_sha256": _array_sha256(
            state_probability.to_numpy(dtype=np.float64)
        ),
        "modal_state_indexes_sha256": _array_sha256(modal, dtype="<i2"),
        "raw_above_modal_probabilities_sha256": _array_sha256(raw),
        "competing_role_jump_probabilities_sha256": _array_sha256(competing),
        "uses_lineup_outcomes": False,
        "historical_lineup_scoring_licensed": False,
        "production_change_licensed": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return L2RoleJumpApplication(
        role_jump_probabilities=np.ascontiguousarray(competing),
        empirical_group_by_player=groups,
        receipt=body,
    )


def apply_l2_base_rate_calibration_v1(
    release: Mapping[str, object],
    target_players: pd.DataFrame,
) -> L2RoleJumpApplication:
    """Produce ordered team-exclusive probabilities for the existing L2 bank."""
    validated = validate_l2_base_rate_calibration_release_v1(release)
    if validated["gate"]["passes"] is not True:
        raise BeliefCalibrationError("L2b calibration did not pass HOLD22")
    return _apply_l2_base_rate_tables_v1(
        target_players=target_players,
        transition_table=validated["transition_table"],
        position_fallback_table=validated["position_fallback_table"],
        receipt_context={
            "schema": L2B_APPLICATION_SCHEMA,
            "calibration_id": validated["calibration_id"],
            "calibration_release_sha256": validated["release_sha256"],
        },
    )


def apply_l2_base_rate_historical_fold_v1(
    release: Mapping[str, object],
    fold_id: str,
    target_players: pd.DataFrame,
) -> L2RoleJumpApplication:
    """Apply only the pre-target transition/residual registry for one fold."""
    validated = validate_l2_base_rate_calibration_release_v1(release)
    registry = validated["historical_application_registry"]
    if type(fold_id) is not str or fold_id not in registry:
        raise BeliefCalibrationError("L2b historical fold differs")
    entry = registry[fold_id]
    if entry["application_ready"] is not True:
        raise BeliefCalibrationError(
            f"L2b fold {fold_id} lacks pre-target residual support"
        )
    if (
        not isinstance(target_players, pd.DataFrame)
        or "season" not in target_players.columns
        or target_players.empty
        or not target_players["season"].eq(entry["target_season"]).all()
    ):
        raise BeliefCalibrationError(
            f"L2b fold {fold_id} target season differs"
        )
    return _apply_l2_base_rate_tables_v1(
        target_players=target_players,
        transition_table=entry["transition_table"],
        position_fallback_table=entry["position_fallback_table"],
        receipt_context={
            "schema": L2B_HISTORICAL_APPLICATION_SCHEMA,
            "calibration_id": (
                f"r6-l2b-{fold_id.lower()}-{entry['application_sha256'][:16]}"
            ),
            "fold_id": fold_id,
            "target_season": entry["target_season"],
            "historical_application_sha256": entry["application_sha256"],
            "role_train_first_season": entry["role_train_first_season"],
            "role_train_last_season": entry["role_train_last_season"],
            "residual_source_fold_ids": entry["residual_source_fold_ids"],
            "residual_source_seasons": entry["residual_source_seasons"],
            "uses_target_role_labels_for_fit": False,
            "uses_target_player_outcomes_for_fit": False,
        },
    )


def l2_base_rate_residual_samples_by_group_v1(
    release: Mapping[str, object],
) -> dict[str, np.ndarray]:
    """Return copied empirical residual samples for the L2 component adapter."""
    validated = validate_l2_base_rate_calibration_release_v1(release)
    return {
        position: np.asarray(
            validated["residual_samples_by_group"][position], dtype=np.float64
        ).copy()
        for position in POSITIONS
    }


def l2_base_rate_historical_residual_samples_by_group_v1(
    release: Mapping[str, object],
    fold_id: str,
) -> dict[str, np.ndarray]:
    """Return only residual samples observed before the requested fold."""
    validated = validate_l2_base_rate_calibration_release_v1(release)
    registry = validated["historical_application_registry"]
    if type(fold_id) is not str or fold_id not in registry:
        raise BeliefCalibrationError("L2b historical fold differs")
    entry = registry[fold_id]
    if entry["application_ready"] is not True:
        raise BeliefCalibrationError(
            f"L2b fold {fold_id} lacks pre-target residual support"
        )
    return {
        position: np.asarray(
            entry["residual_samples_by_group"][position], dtype=np.float64
        ).copy()
        for position in POSITIONS
    }


__all__ = [
    "L2B_APPLICATION_SCHEMA",
    "L2B_CANDIDATE",
    "L2B_COMPARATOR",
    "L2B_HISTORICAL_APPLICATION_SCHEMA",
    "L2B_SCHEMA",
    "apply_l2_base_rate_calibration_v1",
    "apply_l2_base_rate_historical_fold_v1",
    "build_l2_base_rate_calibration_release_v1",
    "l2_base_rate_historical_residual_samples_by_group_v1",
    "l2_base_rate_residual_samples_by_group_v1",
    "validate_l2_base_rate_calibration_release_v1",
]
