"""Minimal walk-forward calibration releases for the R6 L1/L2 laws.

This module closes the probability boundary left deliberately open by the
L1/L2 sampling primitives.  It does not generate or score a lineup.

L1 fits one scalar game-regime probability from three fixed team-game
co-exceedance events.  CAL19 chooses the initial value, WF21 evaluates that
value and updates it, and HOLD22 evaluates the updated value before one final
pre-2023 refit.  Opposing-WR1 correlation is an exact holdout guardrail from
sufficient moments; it is not used to tune the scalar.

L2 reuses the already-audited latent-role transition implementation rather
than fitting a second role model.  The authoritative role source begins in
2018, so the effective role fit boundary is explicitly the intersection of
that source with the broader CAL19/WF21/HOLD22 component registry.  Rare-mode
probability is the fitted mass above each player's modal state.  A deterministic
competing-risk projection converts those marginals to the at-most-one-jump
team law.  Player DK-point residuals are consumed only for role-jump component
amplitudes; lineup outcomes are forbidden throughout.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
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
from .latent_role_state import (
    FORBIDDEN_OUTCOME_COLUMNS,
    INPUT_FEATURES,
    POSITIONS,
    STATES,
    TARGET,
    TRANSITION_SOURCE_SQL,
    decode_role_transition_artifact,
    empirical_transition_probabilities,
    encode_role_transition_artifact,
    fit_role_transition,
    multiclass_scores,
    prepare_transition_frame,
)
from .object_identity import IDENTITY_FIELDS, content_identity


L1_SCHEMA: Final = "corpus-r6-l1-shootout-calibration-release/v1"
L2_SCHEMA: Final = "corpus-r6-l2-role-jump-calibration-release/v1"
L2_APPLICATION_SCHEMA: Final = "corpus-r6-l2-role-jump-application/v1"

L1_METRICS: Final = (
    "qb_wr1_ge_50",
    "qb_wr1_ge_70",
    "qb_wr1_rb1_ge_75",
)
L1_EVENT_COLUMNS: Final = (
    "season",
    "sample_id",
    "metric",
    "observed_event",
    "ordinary_probability",
    "shootout_probability",
)
L1_MOMENT_COLUMNS: Final = (
    "season",
    "component",
    "count",
    "sum_x",
    "sum_y",
    "sum_x2",
    "sum_y2",
    "sum_xy",
)
L1_MOMENT_COMPONENTS: Final = ("ordinary", "shootout", "observed")
L2_RESIDUAL_COLUMNS: Final = (
    "gsis_id",
    "season",
    "week",
    "ordinary_mean",
    "player_actual_points",
)
L2_EFFECTIVE_FIRST_SEASON: Final = 2018
CALIBRATION_SEASONS: Final = tuple(fold.season for fold in CALIBRATION_FOLDS)

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
})


class BeliefCalibrationError(ValueError):
    """A calibration input, fold, release, or application was not exact."""


@dataclass(frozen=True, slots=True)
class L2RoleJumpApplication:
    """Direct inputs for the L2 component builder and mixture sampler."""

    role_jump_probabilities: np.ndarray
    empirical_group_by_player: tuple[str, ...]
    receipt: dict[str, object]


def _source_identities(
    values: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    if not isinstance(values, Mapping) or not values:
        raise BeliefCalibrationError("calibration source identities are empty")
    result: dict[str, dict[str, object]] = {}
    for label in sorted(values):
        if not isinstance(label, str) or not label:
            raise BeliefCalibrationError("calibration source label differs")
        try:
            identity = content_identity(values[label])
        except (TypeError, ValueError) as exc:
            raise BeliefCalibrationError(
                f"calibration source identity {label!r} differs"
            ) from exc
        result[label] = dict(zip(IDENTITY_FIELDS, identity, strict=True))
    return result


def _finite_number(value: object, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise BeliefCalibrationError(f"{label} is not numeric") from exc
    if not math.isfinite(result):
        raise BeliefCalibrationError(f"{label} is not finite")
    return result


def _array_sha256(value: np.ndarray, *, dtype: str = "<f8") -> str:
    stable = np.ascontiguousarray(value, dtype=np.dtype(dtype))
    header = canonical_json_bytes({"dtype": dtype, "shape": list(stable.shape)})
    return sha256(header + b"\0" + stable.tobytes(order="C")).hexdigest()


def _records_sha256(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    records: list[dict[str, object]] = []
    for values in frame.loc[:, list(columns)].itertuples(index=False, name=None):
        record: dict[str, object] = {}
        for name, value in zip(columns, values, strict=True):
            if isinstance(value, (np.integer,)):
                value = int(value)
            elif isinstance(value, (np.floating,)):
                value = float(value)
            elif isinstance(value, (np.bool_,)):
                value = bool(value)
            record[str(name)] = value
        records.append(record)
    return canonical_sha256(records)


def _validate_l1_events(rows: pd.DataFrame, *, minimum_samples: int) -> pd.DataFrame:
    if not isinstance(rows, pd.DataFrame) or set(rows.columns) != set(
        L1_EVENT_COLUMNS
    ):
        raise BeliefCalibrationError("L1 event evidence columns differ")
    if type(minimum_samples) is not int or minimum_samples < 20:
        raise BeliefCalibrationError("L1 minimum samples must be at least 20")
    out = rows.loc[:, list(L1_EVENT_COLUMNS)].copy()
    out["season"] = pd.to_numeric(out["season"], errors="raise").astype(int)
    if set(out["season"]) != set(CALIBRATION_SEASONS):
        raise BeliefCalibrationError("L1 event evidence seasons differ")
    out["sample_id"] = out["sample_id"].astype("string")
    out["metric"] = out["metric"].astype("string")
    if out["sample_id"].isna().any() or (out["sample_id"].str.len() == 0).any():
        raise BeliefCalibrationError("L1 sample identities are empty")
    if set(out["metric"]) != set(L1_METRICS):
        raise BeliefCalibrationError("L1 co-exceedance metrics differ")
    observed = pd.to_numeric(out["observed_event"], errors="raise")
    if not observed.isin((0, 1)).all():
        raise BeliefCalibrationError("L1 observed events must be binary")
    out["observed_event"] = observed.astype(int)
    for name in ("ordinary_probability", "shootout_probability"):
        values = pd.to_numeric(out[name], errors="raise").astype(float)
        if not np.isfinite(values).all() or not values.between(0.0, 1.0).all():
            raise BeliefCalibrationError(f"L1 {name} is outside [0,1]")
        out[name] = values
    if out.duplicated(["season", "sample_id", "metric"]).any():
        raise BeliefCalibrationError("L1 event evidence identities repeat")
    support = out.groupby(["season", "sample_id"])["metric"].agg(
        lambda values: tuple(sorted(str(value) for value in values))
    )
    expected_metrics = tuple(sorted(L1_METRICS))
    if not all(tuple(value) == expected_metrics for value in support):
        raise BeliefCalibrationError("L1 sample lacks a complete metric set")
    sample_counts = out.groupby("season")["sample_id"].nunique()
    if any(int(sample_counts.get(season, 0)) < minimum_samples for season in CALIBRATION_SEASONS):
        raise BeliefCalibrationError("L1 fold lacks minimum sample support")
    return out.sort_values(
        ["season", "sample_id", "metric"], kind="mergesort"
    ).reset_index(drop=True)


def _validate_l1_moments(rows: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(rows, pd.DataFrame) or set(rows.columns) != set(
        L1_MOMENT_COLUMNS
    ):
        raise BeliefCalibrationError("L1 opposing-WR1 moment columns differ")
    out = rows.loc[:, list(L1_MOMENT_COLUMNS)].copy()
    out["season"] = pd.to_numeric(out["season"], errors="raise").astype(int)
    out["component"] = out["component"].astype("string")
    if set(out["season"]) != set(CALIBRATION_SEASONS):
        raise BeliefCalibrationError("L1 moment seasons differ")
    if set(out["component"]) != set(L1_MOMENT_COMPONENTS):
        raise BeliefCalibrationError("L1 moment components differ")
    if out.duplicated(["season", "component"]).any() or len(out) != (
        len(CALIBRATION_SEASONS) * len(L1_MOMENT_COMPONENTS)
    ):
        raise BeliefCalibrationError("L1 moment cells are not one-to-one")
    counts = pd.to_numeric(out["count"], errors="raise")
    if not np.equal(counts, np.floor(counts)).all() or (counts < 2).any():
        raise BeliefCalibrationError("L1 moment counts must be integers >=2")
    out["count"] = counts.astype(int)
    for name in L1_MOMENT_COLUMNS[3:]:
        values = pd.to_numeric(out[name], errors="raise").astype(float)
        if not np.isfinite(values).all():
            raise BeliefCalibrationError(f"L1 moment {name} is nonfinite")
        out[name] = values
    # This also rejects zero/negative marginal variance.
    for row in out.itertuples(index=False):
        _correlation_from_moments(row._asdict())
    return out.sort_values(["season", "component"], kind="mergesort").reset_index(
        drop=True
    )


def _fit_l1_probability(rows: pd.DataFrame) -> float:
    ordinary = rows["ordinary_probability"].to_numpy(dtype=float)
    delta = rows["shootout_probability"].to_numpy(dtype=float) - ordinary
    observed = rows["observed_event"].to_numpy(dtype=float)
    denominator = float(np.dot(delta, delta))
    if denominator <= 1e-12:
        raise BeliefCalibrationError(
            "L1 components have no identifiable co-exceedance contrast"
        )
    value = float(np.dot(delta, observed - ordinary) / denominator)
    return float(np.clip(value, 0.0, 1.0))


def _l1_predictions(rows: pd.DataFrame, probability: float) -> np.ndarray:
    ordinary = rows["ordinary_probability"].to_numpy(dtype=float)
    shootout = rows["shootout_probability"].to_numpy(dtype=float)
    return ordinary + float(probability) * (shootout - ordinary)


def _binary_brier(observed: np.ndarray, probability: np.ndarray) -> float:
    return float(np.mean((probability - observed) ** 2))


def _correlation_from_moments(row: Mapping[str, object]) -> float:
    count = int(row["count"])
    ex = _finite_number(row["sum_x"], label="L1 sum_x") / count
    ey = _finite_number(row["sum_y"], label="L1 sum_y") / count
    ex2 = _finite_number(row["sum_x2"], label="L1 sum_x2") / count
    ey2 = _finite_number(row["sum_y2"], label="L1 sum_y2") / count
    exy = _finite_number(row["sum_xy"], label="L1 sum_xy") / count
    var_x = ex2 - ex * ex
    var_y = ey2 - ey * ey
    if var_x <= 1e-12 or var_y <= 1e-12:
        raise BeliefCalibrationError("L1 opposing-WR1 moment variance is zero")
    corr = (exy - ex * ey) / math.sqrt(var_x * var_y)
    if not math.isfinite(corr) or corr < -1.000000001 or corr > 1.000000001:
        raise BeliefCalibrationError("L1 opposing-WR1 correlation is invalid")
    return float(np.clip(corr, -1.0, 1.0))


def _mixed_correlation(
    ordinary: Mapping[str, object],
    shootout: Mapping[str, object],
    probability: float,
) -> float:
    p = float(probability)
    moments: dict[str, float | int] = {"count": 1}
    for name in ("sum_x", "sum_y", "sum_x2", "sum_y2", "sum_xy"):
        ordinary_mean = float(ordinary[name]) / int(ordinary["count"])
        shootout_mean = float(shootout[name]) / int(shootout["count"])
        moments[name] = (1.0 - p) * ordinary_mean + p * shootout_mean
    return _correlation_from_moments(moments)


def _l1_fold_summary(
    events: pd.DataFrame,
    moments: pd.DataFrame,
    *,
    season: int,
    probability: float,
    fit_seasons: Sequence[int],
    phase: str,
) -> dict[str, object]:
    target = events[events["season"].eq(season)]
    observed = target["observed_event"].to_numpy(dtype=float)
    ordinary = target["ordinary_probability"].to_numpy(dtype=float)
    predicted = _l1_predictions(target, probability)
    by_metric: dict[str, dict[str, object]] = {}
    for metric in L1_METRICS:
        cell = target[target["metric"].eq(metric)]
        cell_observed = cell["observed_event"].to_numpy(dtype=float)
        cell_ordinary = cell["ordinary_probability"].to_numpy(dtype=float)
        cell_predicted = _l1_predictions(cell, probability)
        by_metric[metric] = {
            "samples": len(cell),
            "observed_rate": float(cell_observed.mean()),
            "ordinary_mean_probability": float(cell_ordinary.mean()),
            "mixture_mean_probability": float(cell_predicted.mean()),
            "ordinary_brier": _binary_brier(cell_observed, cell_ordinary),
            "mixture_brier": _binary_brier(cell_observed, cell_predicted),
        }
    cells = {
        str(row.component): row._asdict()
        for row in moments[moments["season"].eq(season)].itertuples(index=False)
    }
    observed_corr = _correlation_from_moments(cells["observed"])
    ordinary_corr = _correlation_from_moments(cells["ordinary"])
    mixture_corr = _mixed_correlation(
        cells["ordinary"], cells["shootout"], probability
    )
    return {
        "season": season,
        "phase": phase,
        "fit_seasons": [int(value) for value in fit_seasons],
        "shootout_probability": probability,
        "samples": int(target["sample_id"].nunique()),
        "event_rows": len(target),
        "ordinary_brier": _binary_brier(observed, ordinary),
        "mixture_brier": _binary_brier(observed, predicted),
        "coexceedance": by_metric,
        "opposing_wr1_correlation": {
            "observed": observed_corr,
            "ordinary": ordinary_corr,
            "mixture": mixture_corr,
            "ordinary_absolute_error": abs(ordinary_corr - observed_corr),
            "mixture_absolute_error": abs(mixture_corr - observed_corr),
        },
    }


def build_l1_shootout_calibration_release_v1(
    *,
    event_rows: pd.DataFrame,
    opposing_wr1_moment_rows: pd.DataFrame,
    source_identities: Mapping[str, Mapping[str, object]],
    minimum_samples_per_fold: int = 20,
) -> dict[str, object]:
    """Fit and freeze the pre-2023 scalar L1 regime probability."""
    events = _validate_l1_events(
        event_rows, minimum_samples=minimum_samples_per_fold
    )
    moments = _validate_l1_moments(opposing_wr1_moment_rows)
    rows19 = events[events["season"].eq(2019)]
    rows19_21 = events[events["season"].isin((2019, 2021))]
    p19 = _fit_l1_probability(rows19)
    p19_21 = _fit_l1_probability(rows19_21)
    final_probability = _fit_l1_probability(events)
    folds = {
        "CAL19": _l1_fold_summary(
            events,
            moments,
            season=2019,
            probability=p19,
            fit_seasons=(2019,),
            phase="calibration-in-sample",
        ),
        "WF21": _l1_fold_summary(
            events,
            moments,
            season=2021,
            probability=p19,
            fit_seasons=(2019,),
            phase="walk-forward-evaluation",
        ),
        "HOLD22": _l1_fold_summary(
            events,
            moments,
            season=2022,
            probability=p19_21,
            fit_seasons=(2019, 2021),
            phase="holdout-evaluation",
        ),
    }
    holdout = folds["HOLD22"]
    holdout_corr = holdout["opposing_wr1_correlation"]
    gate = {
        "hold22_coexceedance_brier_improves": (
            holdout["mixture_brier"] < holdout["ordinary_brier"]
        ),
        "hold22_opposing_wr1_correlation_noninferior": (
            holdout_corr["mixture_absolute_error"]
            <= holdout_corr["ordinary_absolute_error"] + 1e-12
        ),
    }
    gate["passes"] = all(gate.values())
    registry = calibration_fold_registry()
    body: dict[str, object] = {
        "schema": L1_SCHEMA,
        "fold_registry_sha256": registry["registry_sha256"],
        "metrics": list(L1_METRICS),
        "minimum_samples_per_fold": minimum_samples_per_fold,
        "event_evidence_sha256": _records_sha256(events, L1_EVENT_COLUMNS),
        "opposing_wr1_moment_evidence_sha256": _records_sha256(
            moments, L1_MOMENT_COLUMNS
        ),
        "source_identities": _source_identities(source_identities),
        "folds": folds,
        "final_fit_seasons": list(CALIBRATION_SEASONS),
        "final_shootout_probability": final_probability,
        "gate": gate,
        "probability_scope": "global-game-regime-v1",
        "probability_fit_objective": "unweighted-fixed-event-brier",
        "correlation_used_for_fit": False,
        "uses_player_outcomes": True,
        "uses_lineup_outcomes": False,
        "historical_lineup_scoring_licensed": False,
        "production_change_licensed": False,
    }
    seed_hash = canonical_sha256(body)
    body["calibration_id"] = (
        f"r6-l1-cal19-wf21-hold22-{seed_hash[:16]}"
    )
    body["release_sha256"] = canonical_sha256(body)
    validate_l1_shootout_calibration_release_v1(body)
    return body


def validate_l1_shootout_calibration_release_v1(
    value: Mapping[str, object],
) -> dict[str, object]:
    expected = {
        "schema", "fold_registry_sha256", "metrics",
        "minimum_samples_per_fold", "event_evidence_sha256",
        "opposing_wr1_moment_evidence_sha256", "source_identities", "folds",
        "final_fit_seasons", "final_shootout_probability", "gate",
        "probability_scope", "probability_fit_objective",
        "correlation_used_for_fit", "uses_player_outcomes",
        "uses_lineup_outcomes", "historical_lineup_scoring_licensed",
        "production_change_licensed", "calibration_id", "release_sha256",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != expected
        or value.get("schema") != L1_SCHEMA
    ):
        raise BeliefCalibrationError("L1 calibration release schema differs")
    if value.get("fold_registry_sha256") != calibration_fold_registry()[
        "registry_sha256"
    ]:
        raise BeliefCalibrationError("L1 calibration fold registry differs")
    if value.get("metrics") != list(L1_METRICS):
        raise BeliefCalibrationError("L1 calibration metrics differ")
    probability = _finite_number(
        value.get("final_shootout_probability"), label="L1 probability"
    )
    if not 0.0 <= probability <= 1.0:
        raise BeliefCalibrationError("L1 probability is outside [0,1]")
    if not isinstance(value.get("folds"), Mapping) or set(value["folds"]) != {
        "CAL19", "WF21", "HOLD22"
    }:
        raise BeliefCalibrationError("L1 calibration folds differ")
    if not isinstance(value.get("gate"), Mapping) or set(value["gate"]) != {
        "hold22_coexceedance_brier_improves",
        "hold22_opposing_wr1_correlation_noninferior",
        "passes",
    }:
        raise BeliefCalibrationError("L1 calibration gate differs")
    if value["gate"]["passes"] is not all(
        bool(value["gate"][name])
        for name in (
            "hold22_coexceedance_brier_improves",
            "hold22_opposing_wr1_correlation_noninferior",
        )
    ):
        raise BeliefCalibrationError("L1 calibration gate is incoherent")
    for name in (
        "event_evidence_sha256", "opposing_wr1_moment_evidence_sha256",
        "release_sha256",
    ):
        if not _SHA64.fullmatch(str(value.get(name, ""))):
            raise BeliefCalibrationError(f"L1 calibration {name} differs")
    for flag, expected_value in {
        "correlation_used_for_fit": False,
        "uses_player_outcomes": True,
        "uses_lineup_outcomes": False,
        "historical_lineup_scoring_licensed": False,
        "production_change_licensed": False,
    }.items():
        if value.get(flag) is not expected_value:
            raise BeliefCalibrationError(f"L1 calibration {flag} differs")
    _source_identities(value.get("source_identities"))
    digest = value.get("release_sha256")
    body = dict(value)
    body.pop("release_sha256", None)
    if digest != canonical_sha256(body):
        raise BeliefCalibrationError("L1 calibration content hash differs")
    return dict(value)


def l1_probability_by_game_v1(
    release: Mapping[str, object], game_ids: Sequence[object]
) -> dict[str, float]:
    """Return direct sampler input for every unique game in input order."""
    validated = validate_l1_shootout_calibration_release_v1(release)
    if validated["gate"]["passes"] is not True:
        raise BeliefCalibrationError("L1 calibration did not pass HOLD22")
    if isinstance(game_ids, (str, bytes)) or not isinstance(game_ids, Sequence):
        raise BeliefCalibrationError("L1 game IDs must be an ordered sequence")
    games = tuple(str(value) for value in game_ids)
    if not games or any(not value for value in games):
        raise BeliefCalibrationError("L1 game IDs are empty")
    probability = float(validated["final_shootout_probability"])
    return {game: probability for game in dict.fromkeys(games)}


def _validate_role_history(rows: pd.DataFrame) -> pd.DataFrame:
    required = {
        "gsis_id", "season", "week", "team", "position",
        "target_share", "carry_share", "snap_share", *INPUT_FEATURES, TARGET,
    }
    if not isinstance(rows, pd.DataFrame) or (missing := required - set(rows.columns)):
        raise BeliefCalibrationError(
            f"L2 role history missing columns {sorted(missing)}"
        )
    forbidden = sorted(FORBIDDEN_OUTCOME_COLUMNS & set(rows.columns))
    if forbidden:
        raise BeliefCalibrationError(
            f"L2 role history contains forbidden outcomes {forbidden}"
        )
    out = rows.copy()
    out["season"] = pd.to_numeric(out["season"], errors="raise").astype(int)
    out["week"] = pd.to_numeric(out["week"], errors="raise").astype(int)
    if not out["week"].between(1, 18).all():
        raise BeliefCalibrationError("L2 role history week is outside 1--18")
    if out.duplicated(["gsis_id", "season", "week"]).any():
        raise BeliefCalibrationError("L2 role history identities repeat")
    required_seasons = set(range(L2_EFFECTIVE_FIRST_SEASON, 2023))
    if not required_seasons <= set(out["season"]):
        raise BeliefCalibrationError("L2 role history lacks an effective fit season")
    out = out[out["season"].between(L2_EFFECTIVE_FIRST_SEASON, 2022)].copy()
    prepare_transition_frame(out)
    return out.sort_values(
        ["season", "week", "team", "gsis_id"], kind="mergesort"
    ).reset_index(drop=True)


def _validate_residual_history(
    rows: pd.DataFrame, expected_identities: pd.DataFrame
) -> pd.DataFrame:
    if not isinstance(rows, pd.DataFrame) or set(rows.columns) != set(
        L2_RESIDUAL_COLUMNS
    ):
        raise BeliefCalibrationError("L2 residual evidence columns differ")
    if _LINEUP_OUTCOME_FIELDS & {str(name).lower() for name in rows.columns}:
        raise BeliefCalibrationError("L2 residual evidence exposes lineup outcomes")
    out = rows.loc[:, list(L2_RESIDUAL_COLUMNS)].copy()
    out["gsis_id"] = out["gsis_id"].astype("string")
    out["season"] = pd.to_numeric(out["season"], errors="raise").astype(int)
    out["week"] = pd.to_numeric(out["week"], errors="raise").astype(int)
    if out.duplicated(["gsis_id", "season", "week"]).any():
        raise BeliefCalibrationError("L2 residual identities repeat")
    for name in ("ordinary_mean", "player_actual_points"):
        values = pd.to_numeric(out[name], errors="raise").astype(float)
        if not np.isfinite(values).all():
            raise BeliefCalibrationError(f"L2 residual {name} is nonfinite")
        out[name] = values
    identities = out[["gsis_id", "season", "week"]].sort_values(
        ["season", "week", "gsis_id"], kind="mergesort"
    ).reset_index(drop=True)
    expected = expected_identities.astype({"gsis_id": "string"}).sort_values(
        ["season", "week", "gsis_id"], kind="mergesort"
    ).reset_index(drop=True)
    if not identities.equals(expected):
        raise BeliefCalibrationError(
            "L2 residual evidence does not exactly match calibration labels"
        )
    return out.sort_values(
        ["season", "week", "gsis_id"], kind="mergesort"
    ).reset_index(drop=True)


def _modal_and_above_probability(probabilities: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    values = probabilities.loc[:, list(STATES)].to_numpy(dtype=float)
    # np.argmax chooses the first state, which is the frozen lower-state tie break.
    modal_index = np.argmax(values, axis=1)
    above = np.asarray([
        float(values[row_index, state_index + 1 :].sum())
        for row_index, state_index in enumerate(modal_index)
    ])
    return modal_index.astype(np.int16), above


def _predict_transition_copy_safe(
    artifact: Mapping[str, object], rows: pd.DataFrame
) -> pd.DataFrame:
    """Portable latent-role predictor with an owned numeric work array.

    ``latent_role_state.predict_role_transition_artifact`` is the authority
    for the formula.  Pandas 3 can expose its ``to_numpy`` result read-only,
    while that function fills missing values in place.  This narrow adapter
    repeats the exact frozen arithmetic but requests an owned array; it does
    not fit or alter a model.
    """
    from .latent_role_state import CATEGORICAL_FEATURES, NUMERIC_FEATURES

    prepared = prepare_transition_frame(rows, require_target=False)
    numeric = prepared[list(NUMERIC_FEATURES)].apply(
        pd.to_numeric, errors="coerce"
    ).to_numpy(dtype=float, copy=True)
    imputer = np.asarray(artifact["numeric_imputer"], dtype=float)
    mean = np.asarray(artifact["numeric_mean"], dtype=float)
    scale = np.asarray(artifact["numeric_scale"], dtype=float)
    missing = ~np.isfinite(numeric)
    numeric[missing] = np.broadcast_to(imputer, numeric.shape)[missing]
    numeric = (numeric - mean) / scale
    encoded = [numeric]
    for index, feature in enumerate(CATEGORICAL_FEATURES):
        fill = str(artifact["categorical_imputer"][index])
        values = prepared[feature].fillna(fill).astype(str).to_numpy()
        levels = [str(value) for value in artifact["categorical_levels"][index]]
        encoded.append(np.column_stack([values == level for level in levels]))
    design = np.column_stack(encoded).astype(float)
    coefficients = np.asarray(artifact["classifier_coef"], dtype=float)
    intercept = np.asarray(artifact["classifier_intercept"], dtype=float)
    logits = design @ coefficients.T + intercept
    logits -= logits.max(axis=1, keepdims=True)
    probability = np.exp(logits)
    probability /= probability.sum(axis=1, keepdims=True)
    by_class = {
        state: probability[:, index]
        for index, state in enumerate(artifact["classifier_classes"])
    }
    return pd.DataFrame(
        {state: by_class[state] for state in STATES}, index=prepared.index
    )


def _competing_risk_probabilities(
    rows: pd.DataFrame, raw_probability: np.ndarray
) -> tuple[np.ndarray, dict[str, float]]:
    if len(rows) != len(raw_probability):
        raise BeliefCalibrationError("L2 raw probabilities do not align")
    result = np.zeros(len(rows), dtype=np.float64)
    team_any: dict[str, float] = {}
    group_keys = rows[["season", "week", "team"]].astype(str).agg(": ".join, axis=1)
    for key in dict.fromkeys(group_keys):
        indexes = np.flatnonzero(group_keys.to_numpy() == key)
        raw = np.clip(raw_probability[indexes], 0.0, 1.0)
        any_jump = float(1.0 - np.prod(1.0 - raw))
        total = float(raw.sum())
        if total > 0.0:
            result[indexes] = any_jump * raw / total
        team_any[str(key)] = any_jump
    if np.any(result < -1e-12) or np.any(result > 1.0 + 1e-12):
        raise BeliefCalibrationError("L2 competing-risk probabilities are invalid")
    for key in dict.fromkeys(group_keys):
        indexes = np.flatnonzero(group_keys.to_numpy() == key)
        if float(result[indexes].sum()) > 1.0 + 1e-12:
            raise BeliefCalibrationError("L2 team jump probability exceeds one")
    return result, team_any


def _l2_fold(
    role_history: pd.DataFrame,
    residual_history: pd.DataFrame,
    *,
    fold,
) -> tuple[dict[str, object], list[tuple[str, float]]]:
    first = max(L2_EFFECTIVE_FIRST_SEASON, fold.component_train_first_season)
    training = role_history[role_history["season"].between(
        first, fold.component_train_last_season
    )]
    target = role_history[role_history["season"].eq(fold.season)]
    if training.empty or target.empty:
        raise BeliefCalibrationError(f"L2 fold {fold.fold_id} lacks train/test rows")
    fitted = fit_role_transition(training)
    probabilities = fitted.predict_proba(target)
    baseline = empirical_transition_probabilities(training, target)
    truth = target.loc[probabilities.index, TARGET]
    model_score = multiclass_scores(truth, probabilities)
    baseline_score = multiclass_scores(truth, baseline)
    modal_index, raw_probability = _modal_and_above_probability(probabilities)
    competing, team_any = _competing_risk_probabilities(target, raw_probability)
    truth_index = np.asarray([STATES.index(str(value)) for value in truth])
    actual_jump = truth_index > modal_index
    player_brier = _binary_brier(actual_jump.astype(float), competing)
    group_keys = target[["season", "week", "team"]].astype(str).agg(": ".join, axis=1)
    team_counts: list[int] = []
    team_probabilities: list[float] = []
    for key in dict.fromkeys(group_keys):
        indexes = np.flatnonzero(group_keys.to_numpy() == key)
        team_counts.append(int(actual_jump[indexes].sum()))
        team_probabilities.append(team_any[str(key)])
    team_any_truth = np.asarray(team_counts) > 0
    team_any_brier = _binary_brier(
        team_any_truth.astype(float), np.asarray(team_probabilities)
    )
    residual_target = residual_history[residual_history["season"].eq(fold.season)]
    merged = target[["gsis_id", "season", "week", "position"]].copy()
    merged["modal_index"] = modal_index
    merged["actual_jump"] = actual_jump
    merged = merged.merge(
        residual_target,
        on=["gsis_id", "season", "week"],
        how="left",
        validate="one_to_one",
    )
    if merged[["ordinary_mean", "player_actual_points"]].isna().any().any():
        raise BeliefCalibrationError(f"L2 fold {fold.fold_id} lacks residual labels")
    jump_rows = merged[merged["actual_jump"]].copy()
    jump_rows["residual"] = (
        jump_rows["player_actual_points"] - jump_rows["ordinary_mean"]
    )
    residuals = [
        (str(row.position), float(row.residual))
        for row in jump_rows.itertuples(index=False)
    ]
    summary = {
        "season": fold.season,
        "phase": fold.phase,
        "registered_component_train_first_season": (
            fold.component_train_first_season
        ),
        "effective_role_train_first_season": first,
        "train_last_season": fold.component_train_last_season,
        "train_rows": len(training),
        "test_rows": len(target),
        "model_log_loss": model_score["log_loss"],
        "model_multiclass_brier": model_score["multiclass_brier"],
        "baseline_log_loss": baseline_score["log_loss"],
        "baseline_multiclass_brier": baseline_score["multiclass_brier"],
        "mean_raw_above_modal_probability": float(raw_probability.mean()),
        "mean_competing_player_probability": float(competing.mean()),
        "actual_player_jump_rate": float(actual_jump.mean()),
        "player_jump_brier": player_brier,
        "team_any_jump_brier": team_any_brier,
        "team_count": len(team_counts),
        "team_multi_jump_count": int(np.sum(np.asarray(team_counts) > 1)),
        "team_multi_jump_rate": float(np.mean(np.asarray(team_counts) > 1)),
        "jump_residual_count": len(residuals),
    }
    return summary, residuals


def build_l2_role_jump_calibration_release_v1(
    *,
    role_history: pd.DataFrame,
    residual_history: pd.DataFrame,
    source_identities: Mapping[str, Mapping[str, object]],
    code_sha: str,
    minimum_group_support: int = 20,
) -> dict[str, object]:
    """Build one exact pre-2023 L2 probability/residual calibration release."""
    if not _SHA40.fullmatch(str(code_sha)):
        raise BeliefCalibrationError("L2 calibration requires a full code SHA")
    if type(minimum_group_support) is not int or minimum_group_support < 20:
        raise BeliefCalibrationError("L2 minimum group support must be at least 20")
    roles = _validate_role_history(role_history)
    label_ids = roles[roles["season"].isin(CALIBRATION_SEASONS)][
        ["gsis_id", "season", "week"]
    ]
    residuals = _validate_residual_history(residual_history, label_ids)
    fold_summaries: dict[str, object] = {}
    collected: dict[str, list[float]] = {position: [] for position in POSITIONS}
    for fold in CALIBRATION_FOLDS:
        summary, values = _l2_fold(roles, residuals, fold=fold)
        fold_summaries[fold.fold_id] = summary
        for position, residual in values:
            if position not in collected:
                raise BeliefCalibrationError("L2 residual position differs")
            collected[position].append(residual)
    group_summaries: dict[str, dict[str, object]] = {}
    for position in POSITIONS:
        values = np.asarray(collected[position], dtype=np.float64)
        if len(values) < minimum_group_support or not np.isfinite(values).all():
            raise BeliefCalibrationError(
                f"L2 residual group {position} lacks minimum support"
            )
        if float(values.mean()) <= 0.0 or float(np.quantile(values, 0.9)) <= 0.0:
            raise BeliefCalibrationError(
                f"L2 residual group {position} is not a positive jump component"
            )
        group_summaries[position] = {
            "count": len(values),
            "samples_sha256": _array_sha256(values),
            "mean": float(values.mean()),
            "q50": float(np.quantile(values, 0.5)),
            "q90": float(np.quantile(values, 0.9)),
        }
    final_training = roles[roles["season"].between(
        L2_EFFECTIVE_FIRST_SEASON, 2022
    )]
    fitted = fit_role_transition(final_training)
    transition_payload, transition_receipt = encode_role_transition_artifact(
        fitted,
        final_training,
        code_sha=str(code_sha),
        source_sql=TRANSITION_SOURCE_SQL,
    )
    transition_artifact = json.loads(transition_payload)
    holdout = fold_summaries["HOLD22"]
    gate = {
        "hold22_log_loss_improves": (
            holdout["model_log_loss"] < holdout["baseline_log_loss"]
        ),
        "hold22_multiclass_brier_improves": (
            holdout["model_multiclass_brier"]
            < holdout["baseline_multiclass_brier"]
        ),
        "residual_support_and_positive_component": True,
    }
    gate["passes"] = all(gate.values())
    registry = calibration_fold_registry()
    body: dict[str, object] = {
        "schema": L2_SCHEMA,
        "fold_registry_sha256": registry["registry_sha256"],
        "effective_role_source_first_season": L2_EFFECTIVE_FIRST_SEASON,
        "registered_component_first_season": min(
            fold.component_train_first_season for fold in CALIBRATION_FOLDS
        ),
        "source_boundary_intersection_disclosed": True,
        "folds": fold_summaries,
        "transition_artifact": transition_artifact,
        "transition_artifact_sha256": transition_receipt["sha256"],
        "transition_training_frame_sha256": transition_receipt[
            "training_frame_sha256"
        ],
        "residual_samples_by_group": {
            position: [float(value) for value in collected[position]]
            for position in POSITIONS
        },
        "residual_group_summaries": group_summaries,
        "residual_evidence_sha256": _records_sha256(
            residuals, L2_RESIDUAL_COLUMNS
        ),
        "minimum_group_support": minimum_group_support,
        "source_identities": _source_identities(source_identities),
        "probability_law": {
            "raw_player_probability": "fitted-mass-strictly-above-modal-state",
            "modal_tie_break": "lower-state",
            "team_projection": "independent-any-jump-proportional-competing-risk",
            "maximum_selected_jumps_per_team_world": 1,
        },
        "gate": gate,
        "uses_role_labels": True,
        "uses_player_outcomes_for_residual_amplitude": True,
        "uses_lineup_outcomes": False,
        "historical_lineup_scoring_licensed": False,
        "production_change_licensed": False,
    }
    seed_hash = canonical_sha256(body)
    body["calibration_id"] = (
        f"r6-l2-cal19-wf21-hold22-{seed_hash[:16]}"
    )
    body["release_sha256"] = canonical_sha256(body)
    validate_l2_role_jump_calibration_release_v1(body)
    return body


def validate_l2_role_jump_calibration_release_v1(
    value: Mapping[str, object],
) -> dict[str, object]:
    expected = {
        "schema", "fold_registry_sha256", "effective_role_source_first_season",
        "registered_component_first_season",
        "source_boundary_intersection_disclosed", "folds",
        "transition_artifact", "transition_artifact_sha256",
        "transition_training_frame_sha256", "residual_samples_by_group",
        "residual_group_summaries", "residual_evidence_sha256",
        "minimum_group_support", "source_identities", "probability_law", "gate",
        "uses_role_labels", "uses_player_outcomes_for_residual_amplitude",
        "uses_lineup_outcomes", "historical_lineup_scoring_licensed",
        "production_change_licensed", "calibration_id", "release_sha256",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != expected
        or value.get("schema") != L2_SCHEMA
    ):
        raise BeliefCalibrationError("L2 calibration release schema differs")
    if value.get("fold_registry_sha256") != calibration_fold_registry()[
        "registry_sha256"
    ]:
        raise BeliefCalibrationError("L2 calibration fold registry differs")
    if value.get("effective_role_source_first_season") != 2018 or value.get(
        "registered_component_first_season"
    ) != 2015 or value.get("source_boundary_intersection_disclosed") is not True:
        raise BeliefCalibrationError("L2 calibration source boundary differs")
    if not isinstance(value.get("folds"), Mapping) or set(value["folds"]) != {
        "CAL19", "WF21", "HOLD22"
    }:
        raise BeliefCalibrationError("L2 calibration folds differ")
    if not _SHA64.fullmatch(str(value.get("transition_artifact_sha256", ""))):
        raise BeliefCalibrationError("L2 transition artifact hash differs")
    transition_payload = json.dumps(
        value.get("transition_artifact"),
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    decode_role_transition_artifact(
        transition_payload, str(value["transition_artifact_sha256"])
    )
    residual_groups = value.get("residual_samples_by_group")
    summaries = value.get("residual_group_summaries")
    if not isinstance(residual_groups, Mapping) or set(residual_groups) != set(
        POSITIONS
    ):
        raise BeliefCalibrationError("L2 residual groups differ")
    if not isinstance(summaries, Mapping) or set(summaries) != set(POSITIONS):
        raise BeliefCalibrationError("L2 residual summaries differ")
    minimum = value.get("minimum_group_support")
    if type(minimum) is not int or minimum < 20:
        raise BeliefCalibrationError("L2 minimum support differs")
    for position in POSITIONS:
        values = np.asarray(residual_groups[position], dtype=np.float64)
        summary = summaries[position]
        if (
            values.ndim != 1
            or len(values) < minimum
            or not np.isfinite(values).all()
            or not isinstance(summary, Mapping)
            or summary.get("count") != len(values)
            or summary.get("samples_sha256") != _array_sha256(values)
            or float(values.mean()) <= 0.0
            or float(np.quantile(values, 0.9)) <= 0.0
        ):
            raise BeliefCalibrationError(
                f"L2 residual group {position} content differs"
            )
    if value.get("probability_law") != {
        "raw_player_probability": "fitted-mass-strictly-above-modal-state",
        "modal_tie_break": "lower-state",
        "team_projection": "independent-any-jump-proportional-competing-risk",
        "maximum_selected_jumps_per_team_world": 1,
    }:
        raise BeliefCalibrationError("L2 probability law differs")
    gate = value.get("gate")
    gate_names = (
        "hold22_log_loss_improves",
        "hold22_multiclass_brier_improves",
        "residual_support_and_positive_component",
    )
    if not isinstance(gate, Mapping) or set(gate) != {*gate_names, "passes"}:
        raise BeliefCalibrationError("L2 calibration gate differs")
    if gate["passes"] is not all(bool(gate[name]) for name in gate_names):
        raise BeliefCalibrationError("L2 calibration gate is incoherent")
    for flag, expected_value in {
        "uses_role_labels": True,
        "uses_player_outcomes_for_residual_amplitude": True,
        "uses_lineup_outcomes": False,
        "historical_lineup_scoring_licensed": False,
        "production_change_licensed": False,
    }.items():
        if value.get(flag) is not expected_value:
            raise BeliefCalibrationError(f"L2 calibration {flag} differs")
    _source_identities(value.get("source_identities"))
    for name in (
        "transition_training_frame_sha256", "residual_evidence_sha256",
        "release_sha256",
    ):
        if not _SHA64.fullmatch(str(value.get(name, ""))):
            raise BeliefCalibrationError(f"L2 calibration {name} differs")
    digest = value.get("release_sha256")
    body = dict(value)
    body.pop("release_sha256", None)
    if digest != canonical_sha256(body):
        raise BeliefCalibrationError("L2 calibration content hash differs")
    return dict(value)


def apply_l2_role_jump_calibration_v1(
    release: Mapping[str, object], target_players: pd.DataFrame
) -> L2RoleJumpApplication:
    """Produce ordered player probabilities/groups for the existing L2 bank."""
    validated = validate_l2_role_jump_calibration_release_v1(release)
    if validated["gate"]["passes"] is not True:
        raise BeliefCalibrationError("L2 calibration did not pass HOLD22")
    required = {"gsis_id", "team", "position", *INPUT_FEATURES}
    if not isinstance(target_players, pd.DataFrame) or (
        missing := required - set(target_players.columns)
    ):
        raise BeliefCalibrationError(
            f"L2 target players missing columns {sorted(missing)}"
        )
    if _LINEUP_OUTCOME_FIELDS & {
        str(name).lower() for name in target_players.columns
    }:
        raise BeliefCalibrationError("L2 target players expose lineup outcomes")
    target = target_players.copy().reset_index(drop=True)
    target["gsis_id"] = target["gsis_id"].astype("string")
    target["team"] = target["team"].astype("string")
    target["position"] = target["position"].astype("string").str.upper()
    if (
        target.empty
        or target["gsis_id"].isna().any()
        or target["gsis_id"].duplicated().any()
        or target["team"].isna().any()
        or not target["position"].isin(POSITIONS).all()
    ):
        raise BeliefCalibrationError("L2 target player identities differ")
    transition_payload = json.dumps(
        validated["transition_artifact"],
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    artifact = decode_role_transition_artifact(
        transition_payload, str(validated["transition_artifact_sha256"])
    )
    probabilities = _predict_transition_copy_safe(artifact, target)
    modal_index, raw = _modal_and_above_probability(probabilities)
    injury = target["injury_status"].fillna("").astype(str).str.upper()
    raw[injury.eq("OUT").to_numpy()] = 0.0
    # Application is one slate; synthetic season/week keys make the shared
    # competing-risk primitive exact without widening its accepted schema.
    competition_frame = target.assign(season=0, week=1)
    competing, team_any = _competing_risk_probabilities(competition_frame, raw)
    groups = tuple(str(value) for value in target["position"])
    body: dict[str, object] = {
        "schema": L2_APPLICATION_SCHEMA,
        "calibration_id": validated["calibration_id"],
        "calibration_release_sha256": validated["release_sha256"],
        "player_count": len(target),
        "ordered_player_ids_sha256": canonical_sha256(target["gsis_id"].tolist()),
        "ordered_team_ids_sha256": canonical_sha256(target["team"].tolist()),
        "empirical_group_by_player_sha256": canonical_sha256(list(groups)),
        "state_probabilities_sha256": _array_sha256(
            probabilities.to_numpy(dtype=float)
        ),
        "modal_state_indexes_sha256": _array_sha256(modal_index, dtype="<i2"),
        "raw_above_modal_probabilities_sha256": _array_sha256(raw),
        "competing_role_jump_probabilities_sha256": _array_sha256(competing),
        "team_any_jump_probabilities": {
            key: float(value) for key, value in sorted(team_any.items())
        },
        "uses_lineup_outcomes": False,
        "historical_lineup_scoring_licensed": False,
        "production_change_licensed": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return L2RoleJumpApplication(
        np.ascontiguousarray(competing, dtype=np.float64), groups, body
    )


def l2_residual_samples_by_group_v1(
    release: Mapping[str, object],
) -> dict[str, np.ndarray]:
    """Return copied direct inputs for the existing L2 component builder."""
    validated = validate_l2_role_jump_calibration_release_v1(release)
    return {
        position: np.asarray(
            validated["residual_samples_by_group"][position], dtype=np.float64
        ).copy()
        for position in POSITIONS
    }


__all__ = [
    "BeliefCalibrationError",
    "CALIBRATION_SEASONS",
    "L1_EVENT_COLUMNS",
    "L1_METRICS",
    "L1_MOMENT_COLUMNS",
    "L2_RESIDUAL_COLUMNS",
    "L2RoleJumpApplication",
    "apply_l2_role_jump_calibration_v1",
    "build_l1_shootout_calibration_release_v1",
    "build_l2_role_jump_calibration_release_v1",
    "l1_probability_by_game_v1",
    "l2_residual_samples_by_group_v1",
    "validate_l1_shootout_calibration_release_v1",
    "validate_l2_role_jump_calibration_release_v1",
]
