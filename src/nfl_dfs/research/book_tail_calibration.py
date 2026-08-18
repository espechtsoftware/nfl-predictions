"""Frozen retrospective selected-book tail-calibration audit.

This module consumes only the compact, immutable multi-seed factorial report.
It does not fit or tune a model, select an arm, define a gate, or license a
production change.  The audited estimand is absolute calibration of the
already-selected CBWU book, not an arm-transport contrast.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import rankdata
from sklearn.metrics import average_precision_score, roc_auc_score


AUDIT_PROTOCOL_ID = "20260817-selected-book-tail-calibration-v1"
SOURCE_PROTOCOL_ID = "2026-08-13-multiseed-candidate-world-factorial"
EXPECTED_SOURCE_SHA256 = (
    "a41d3427aa267ed9ab52753a898f14135caa9bd42c11c645d92eccffbb170239"
)
EXPECTED_CODE_SHA = "4d6f5cf"
SOURCE_ARM = "treatment"
FINAL_PRODUCTION_ARM = "CBWU"
SEASONS = (2023, 2024, 2025)
SLATES_PER_SEASON = 18
SLATE_COUNT = 54
ENTRY_COUNT = 80
WORLD_COUNT = 50_000
CALIBRATION_THRESHOLDS = (187, 194, 200, 210)
DESCRIPTIVE_THRESHOLDS = (220, 230, 240)
THRESHOLDS = CALIBRATION_THRESHOLDS + DESCRIPTIVE_THRESHOLDS
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20_260_817
QUANTILE_KEYS = ("0.95", "0.99")
SEED_KEYS = ("R0", "R1", "R2", "R3", "R4")
ARM_KEYS = ("C0W0", "C0WU", "CUW0", "CUWU")
CONFIRMATION_KEYS = ("CBW0", "CBWU")
ROOT_KEYS = {
    "protocol", "source_arm", "expected_code_sha", "mechanical_passes",
    "failures", "result",
}
RESULT_KEYS = {
    "metrics", "selected_arm", "ranked_arms", "production_selected_arm",
    "production_ranked_arms", "candidate_union_confirmation_required",
    "fixed_budget_confirmation", "final_production_arm",
    "factorial_contrasts", "weekly_deltas_at_least_10",
    "standalone_seed_noise_floor", "by_season",
    "slate_clustered_bootstrap_diagnostic", "slates",
}
SLATE_KEYS = {
    "season", "week", "novel_candidates_by_seed", "standalone_seed_books",
    "fixed_budget_confirmation", "arms",
}
BOOK_BASE_KEYS = {
    "candidate_count", "world_count", "selected_best", "oracle_best",
    "selected_from_seed", "simulated_coverage",
    "simulated_weekly_best_quantile",
}


def _reject_constant(value: str) -> None:
    raise ValueError(f"source JSON contains non-finite constant {value!r}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"source JSON contains duplicate key {key!r}")
        output[key] = value
    return output


def load_source_json(raw: bytes) -> Mapping[str, Any]:
    """Decode strict UTF-8 JSON while rejecting duplicates and NaN/Infinity."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("source report is not UTF-8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ValueError("source report is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise ValueError("source report root must be an object")
    return value


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _probability(value: Any, label: str) -> float:
    result = _finite(value, label)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{label} must be a probability in [0, 1]")
    return result


def _field(source: Mapping[str, Any], key: str, label: str) -> Any:
    if key not in source:
        raise ValueError(f"{label} is missing required field {key!r}")
    return source[key]


def _exact_keys(source: Mapping[str, Any], expected: set[str], label: str) -> None:
    observed = set(source)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise ValueError(
            f"{label} schema differs: missing={missing!r}, extra={extra!r}"
        )


def _reject_selected_rosters(value: Any, label: str = "source report") -> None:
    if isinstance(value, Mapping):
        if "selected_rosters" in value:
            raise ValueError(
                f"{label} unexpectedly contains selected_rosters; the pinned "
                "compact source strips roster identities"
            )
        for key, child in value.items():
            _reject_selected_rosters(child, f"{label}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_selected_rosters(child, f"{label}[{index}]")


def _validate_identity(report: Mapping[str, Any]) -> Mapping[str, Any]:
    _exact_keys(report, ROOT_KEYS, "source report root")
    _reject_selected_rosters(report)
    if _field(report, "protocol", "source report") != SOURCE_PROTOCOL_ID:
        raise ValueError("source protocol identity differs")
    if _field(report, "source_arm", "source report") != SOURCE_ARM:
        raise ValueError("source arm identity differs")
    if _field(report, "expected_code_sha", "source report") != EXPECTED_CODE_SHA:
        raise ValueError("source expected code SHA differs")
    if _field(report, "mechanical_passes", "source report") is not True:
        raise ValueError("source report did not mechanically pass")
    failures = _list(_field(report, "failures", "source report"), "source failures")
    if failures:
        raise ValueError("source report contains failures")
    result = _mapping(_field(report, "result", "source report"), "source result")
    _exact_keys(result, RESULT_KEYS, "source result")
    if _field(result, "final_production_arm", "source result") != FINAL_PRODUCTION_ARM:
        raise ValueError("source final production arm differs")
    return result


def _validate_seed_counts(book: Mapping[str, Any], label: str) -> None:
    source_counts = _mapping(
        _field(book, "selected_from_seed", label), f"{label} selected source counts",
    )
    if set(source_counts) != set(SEED_KEYS):
        raise ValueError(f"{label} selected source seed identity differs")
    counts = [
        _integer(source_counts[key], f"{label} selected count {key}")
        for key in SEED_KEYS
    ]
    if any(count < 0 for count in counts) or sum(counts) != ENTRY_COUNT:
        raise ValueError(f"{label} does not bind exact seed counts summing to 80")


def _validate_book(
    raw_book: Any,
    label: str,
    *,
    extra_keys: set[str],
    expected_world_count: int,
) -> dict[str, Any]:
    book = _mapping(raw_book, label)
    _exact_keys(book, BOOK_BASE_KEYS | extra_keys, label)
    candidate_count = _integer(
        _field(book, "candidate_count", label), f"{label} candidate count",
    )
    if candidate_count < ENTRY_COUNT:
        raise ValueError(f"{label} candidate count is below exact-80")
    if _integer(_field(book, "world_count", label), f"{label} world count") \
            != expected_world_count:
        raise ValueError(
            f"{label} does not bind exactly {expected_world_count} worlds"
        )
    selected_best = _finite(
        _field(book, "selected_best", label), f"{label} selected best",
    )
    oracle_best = _finite(
        _field(book, "oracle_best", label), f"{label} oracle best",
    )
    if selected_best > oracle_best:
        raise ValueError(f"{label} selected best exceeds its candidate oracle")
    _validate_seed_counts(book, label)

    coverage = _mapping(
        _field(book, "simulated_coverage", label),
        f"{label} simulated coverage",
    )
    expected_tail_keys = {str(threshold) for threshold in THRESHOLDS}
    if set(coverage) != expected_tail_keys:
        raise ValueError(f"{label} simulated coverage threshold schema differs")
    probabilities = {
        str(threshold): _probability(
            coverage[str(threshold)], f"{label} simulated coverage {threshold}",
        )
        for threshold in THRESHOLDS
    }
    ordered_probabilities = [
        probabilities[str(threshold)] for threshold in sorted(THRESHOLDS)
    ]
    if any(
        left < right
        for left, right in zip(ordered_probabilities, ordered_probabilities[1:])
    ):
        raise ValueError(f"{label} simulated coverage is not tail-monotone")
    quantiles = _mapping(
        _field(book, "simulated_weekly_best_quantile", label),
        f"{label} simulated weekly-best quantiles",
    )
    if set(quantiles) != set(QUANTILE_KEYS):
        raise ValueError(f"{label} simulated weekly-best quantile schema differs")
    q95 = _finite(quantiles["0.95"], f"{label} weekly-best q95")
    q99 = _finite(quantiles["0.99"], f"{label} weekly-best q99")
    if q95 > q99:
        raise ValueError(f"{label} weekly-best quantiles are not monotone")
    for key in extra_keys:
        value = _finite(_field(book, key, label), f"{label} {key}")
        if key.startswith("selected_overlap_") and not 0 <= value <= ENTRY_COUNT:
            raise ValueError(f"{label} {key} is outside [0, 80]")
    return {
        "candidate_count": candidate_count,
        "selected_best": selected_best,
        "simulated_coverage": probabilities,
        "simulated_weekly_best_q95": q95,
        "simulated_weekly_best_q99": q99,
    }


def _extract_slates(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_slates = _list(_field(result, "slates", "source result"), "source slates")
    if len(raw_slates) != SLATE_COUNT:
        raise ValueError(f"source must contain exactly {SLATE_COUNT} slates")
    rows: list[dict[str, Any]] = []
    identities: set[tuple[int, int]] = set()
    for index, raw_slate in enumerate(raw_slates):
        label = f"source slate {index}"
        slate = _mapping(raw_slate, label)
        _exact_keys(slate, SLATE_KEYS, label)
        season = _integer(_field(slate, "season", label), f"{label} season")
        week = _integer(_field(slate, "week", label), f"{label} week")
        if season not in SEASONS or week not in range(1, SLATES_PER_SEASON + 1):
            raise ValueError(f"{label} season/week identity is invalid")
        identity = (season, week)
        if identity in identities:
            raise ValueError("source slate identities repeat")
        identities.add(identity)

        novelty = _mapping(
            _field(slate, "novel_candidates_by_seed", label),
            f"{label} novel candidates by seed",
        )
        if set(novelty) != set(SEED_KEYS):
            raise ValueError(f"{label} novel-candidate seed identity differs")
        for seed in SEED_KEYS:
            if _integer(novelty[seed], f"{label} novel candidates {seed}") < 0:
                raise ValueError(f"{label} novel candidate count is negative")

        standalone = _mapping(
            _field(slate, "standalone_seed_books", label),
            f"{label} standalone seed books",
        )
        if set(standalone) != set(SEED_KEYS):
            raise ValueError(f"{label} standalone seed-book identity differs")
        for seed in SEED_KEYS:
            _validate_book(
                standalone[seed], f"{label} standalone {seed}",
                extra_keys=set(), expected_world_count=10_000,
            )

        arms = _mapping(_field(slate, "arms", label), f"{label} arms")
        if set(arms) != set(ARM_KEYS):
            raise ValueError(f"{label} arm identity differs")
        validated_arms = {}
        for arm in ARM_KEYS:
            validated_arms[arm] = _validate_book(
                arms[arm], f"{label} arm {arm}",
                extra_keys={"selected_overlap_c0w0", "selected_delta_c0w0"},
                expected_world_count=50_000 if "WU" in arm else 10_000,
            )
        c0w0_best = validated_arms["C0W0"]["selected_best"]
        for arm in ARM_KEYS:
            delta = _finite(
                _mapping(arms[arm], f"{label} arm {arm}")["selected_delta_c0w0"],
                f"{label} arm {arm} selected delta",
            )
            if not math.isclose(
                delta, validated_arms[arm]["selected_best"] - c0w0_best,
                rel_tol=0.0, abs_tol=1e-12,
            ):
                raise ValueError(f"{label} arm {arm} selected delta differs")

        confirmation = _mapping(
            _field(slate, "fixed_budget_confirmation", label),
            f"{label} fixed-budget confirmation",
        )
        if set(confirmation) != set(CONFIRMATION_KEYS):
            raise ValueError(f"{label} fixed-budget confirmation identity differs")
        validated_confirmation = {}
        for arm, comparator in (("CBW0", "c0w0"), ("CBWU", "c0wu")):
            validated_confirmation[arm] = _validate_book(
                confirmation[arm], f"{label} confirmation {arm}",
                extra_keys={f"selected_overlap_{comparator}"},
                expected_world_count=50_000 if arm == "CBWU" else 10_000,
            )
        candidate_count = validated_confirmation[FINAL_PRODUCTION_ARM][
            "candidate_count"
        ]
        if candidate_count != validated_arms["C0W0"]["candidate_count"]:
            raise ValueError(
                f"{label} CBWU candidate count differs from arms.C0W0"
            )
        book = validated_confirmation[FINAL_PRODUCTION_ARM]
        rows.append({
            "season": season,
            "week": week,
            "selected_best": book["selected_best"],
            "simulated_coverage": book["simulated_coverage"],
            "simulated_weekly_best_q95": book["simulated_weekly_best_q95"],
            "simulated_weekly_best_q99": book["simulated_weekly_best_q99"],
        })

    season_counts = {season: 0 for season in SEASONS}
    for row in rows:
        season_counts[row["season"]] += 1
    if season_counts != {season: SLATES_PER_SEASON for season in SEASONS}:
        raise ValueError("source must contain exactly 18 slates in each 2023-2025 season")
    if identities != {
        (season, week)
        for season in SEASONS for week in range(1, SLATES_PER_SEASON + 1)
    }:
        raise ValueError("source slate identities must be exactly 2023-2025 weeks 1-18")
    return sorted(rows, key=lambda row: (row["season"], row["week"]))


def _loso_prevalence(labels: np.ndarray, seasons: np.ndarray) -> np.ndarray:
    probabilities = np.empty(len(labels), dtype=float)
    for season in SEASONS:
        held_out = seasons == season
        training = ~held_out
        if int(held_out.sum()) == 0 or int(training.sum()) == 0:
            raise ValueError("leave-one-season-out prevalence split is empty")
        probabilities[held_out] = float(labels[training].mean())
    return probabilities


def _skill(model_brier: float, baseline_brier: float) -> float | None:
    if baseline_brier == 0.0:
        return None
    return float(1.0 - model_brier / baseline_brier)


def _threshold_metrics(
    labels: np.ndarray,
    probabilities: np.ndarray,
    baseline: np.ndarray,
) -> dict[str, Any]:
    model_brier = float(np.mean(np.square(probabilities - labels)))
    baseline_brier = float(np.mean(np.square(baseline - labels)))
    both_classes = bool(np.unique(labels).size == 2)
    output = {
        "slates": int(len(labels)),
        "realized_events": int(labels.sum()),
        "realized_prevalence": float(labels.mean()),
        "mean_simulated_coverage": float(probabilities.mean()),
        "brier_score": model_brier,
        "loso_prevalence_baseline_brier_score": baseline_brier,
        "brier_skill": _skill(model_brier, baseline_brier),
        "both_classes_present": both_classes,
        "roc_auc": None,
        "average_precision": None,
    }
    if both_classes:
        output["roc_auc"] = float(roc_auc_score(labels, probabilities))
        output["average_precision"] = float(
            average_precision_score(labels, probabilities)
        )
    return output


def _descriptive_metrics(
    labels: np.ndarray,
    probabilities: np.ndarray,
) -> dict[str, Any]:
    return {
        "slates": int(len(labels)),
        "realized_events": int(labels.sum()),
        "realized_prevalence": float(labels.mean()),
        "mean_simulated_coverage": float(probabilities.mean()),
        "minimum_simulated_coverage": float(probabilities.min()),
        "maximum_simulated_coverage": float(probabilities.max()),
    }


def _correlation(left: np.ndarray, right: np.ndarray) -> dict[str, float | None]:
    if len(left) < 2 or np.ptp(left) == 0.0 or np.ptp(right) == 0.0:
        return {"pearson": None, "spearman": None}
    pearson = float(np.corrcoef(left, right)[0, 1])
    spearman = float(np.corrcoef(rankdata(left), rankdata(right))[0, 1])
    return {"pearson": pearson, "spearman": spearman}


def _ci(values: Sequence[float]) -> list[float] | None:
    if not values:
        return None
    array = np.asarray(values, dtype=float)
    return [
        float(np.quantile(array, 0.025, method="linear")),
        float(np.quantile(array, 0.975, method="linear")),
    ]


def _bootstrap_indices(seasons: np.ndarray) -> np.ndarray:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    blocks = []
    for season in SEASONS:
        indices = np.flatnonzero(seasons == season)
        if len(indices) != SLATES_PER_SEASON:
            raise ValueError("bootstrap season strata differ from the frozen population")
        blocks.append(rng.choice(
            indices,
            size=(BOOTSTRAP_RESAMPLES, SLATES_PER_SEASON),
            replace=True,
        ))
    return np.concatenate(blocks, axis=1)


def _bootstrap_skill(
    labels: np.ndarray,
    probabilities: np.ndarray,
    seasons: np.ndarray,
    samples: np.ndarray,
    *,
    evaluation_season: int | None = None,
) -> dict[str, Any]:
    values: list[float] = []
    undefined = 0
    for chosen in samples:
        y = labels[chosen]
        q = probabilities[chosen]
        strata = seasons[chosen]
        baseline = _loso_prevalence(y, strata)
        evaluation = (
            np.ones(len(y), dtype=bool)
            if evaluation_season is None else strata == evaluation_season
        )
        if not evaluation.any():
            raise ValueError("bootstrap evaluation season is absent")
        skill = _skill(
            float(np.mean(np.square(q[evaluation] - y[evaluation]))),
            float(np.mean(np.square(
                baseline[evaluation] - y[evaluation],
            ))),
        )
        if skill is None:
            undefined += 1
        else:
            values.append(skill)
    return {
        "ci95": _ci(values),
        "finite_resamples": len(values),
        "undefined_resamples": undefined,
    }


def _bootstrap_correlation(
    left: np.ndarray,
    right: np.ndarray,
    samples: np.ndarray,
) -> dict[str, Any]:
    values: dict[str, list[float]] = {"pearson": [], "spearman": []}
    for chosen in samples:
        correlations = _correlation(left[chosen], right[chosen])
        for method in values:
            value = correlations[method]
            if value is not None:
                values[method].append(value)
    return {
        method: {
            "ci95": _ci(method_values),
            "finite_resamples": len(method_values),
            "undefined_resamples": BOOTSTRAP_RESAMPLES - len(method_values),
        }
        for method, method_values in values.items()
    }


def _bootstrap_classification(
    labels: np.ndarray,
    probabilities: np.ndarray,
    seasons: np.ndarray,
    samples: np.ndarray,
    *,
    evaluation_season: int | None = None,
) -> dict[str, Any]:
    values: dict[str, list[float]] = {"roc_auc": [], "average_precision": []}
    undefined = 0
    for chosen in samples:
        y = labels[chosen]
        q = probabilities[chosen]
        strata = seasons[chosen]
        evaluation = (
            np.ones(len(y), dtype=bool)
            if evaluation_season is None else strata == evaluation_season
        )
        if not evaluation.any():
            raise ValueError("bootstrap classification evaluation season is absent")
        y_evaluation = y[evaluation]
        if np.unique(y_evaluation).size != 2:
            undefined += 1
            continue
        q_evaluation = q[evaluation]
        roc_auc = float(roc_auc_score(y_evaluation, q_evaluation))
        average_precision = float(
            average_precision_score(y_evaluation, q_evaluation)
        )
        if not math.isfinite(roc_auc) or not math.isfinite(average_precision):
            undefined += 1
            continue
        values["roc_auc"].append(roc_auc)
        values["average_precision"].append(average_precision)
    return {
        f"bootstrap_{name}": {
            "ci95": _ci(metric_values),
            "finite_resamples": len(metric_values),
            "undefined_resamples": undefined,
        }
        for name, metric_values in values.items()
    }


def _assert_json_finite(value: Any, label: str = "result") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _assert_json_finite(child, f"{label}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_json_finite(child, f"{label}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{label} is non-finite")


def _analyze_report(
    report: Mapping[str, Any],
    *,
    source_sha256: str,
) -> dict[str, Any]:
    """Validate the frozen source report and return the canonical audit object."""
    if len(source_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in source_sha256
    ):
        raise ValueError("source SHA-256 identity is invalid")
    result = _validate_identity(report)
    rows = _extract_slates(result)
    seasons = np.asarray([row["season"] for row in rows], dtype=int)
    selected_best = np.asarray([row["selected_best"] for row in rows], dtype=float)
    q95 = np.asarray(
        [row["simulated_weekly_best_q95"] for row in rows], dtype=float,
    )
    q99 = np.asarray(
        [row["simulated_weekly_best_q99"] for row in rows], dtype=float,
    )
    samples = _bootstrap_indices(seasons)

    threshold_results: dict[str, Any] = {}
    for threshold in THRESHOLDS:
        labels = (selected_best >= threshold).astype(float)
        probabilities = np.asarray([
            row["simulated_coverage"][str(threshold)] for row in rows
        ], dtype=float)
        by_season: dict[str, Any] = {}
        if threshold in CALIBRATION_THRESHOLDS:
            baseline = _loso_prevalence(labels, seasons)
            for season in SEASONS:
                mask = seasons == season
                by_season[str(season)] = _threshold_metrics(
                    labels[mask], probabilities[mask], baseline[mask],
                )
                by_season[str(season)].update(_bootstrap_classification(
                    labels, probabilities, seasons, samples,
                    evaluation_season=season,
                ))
                by_season[str(season)]["bootstrap_brier_skill"] = \
                    _bootstrap_skill(
                        labels,
                        probabilities,
                        seasons,
                        samples,
                        evaluation_season=season,
                    )
            all_metrics = _threshold_metrics(labels, probabilities, baseline)
            all_metrics.update(_bootstrap_classification(
                labels, probabilities, seasons, samples,
            ))
            threshold_results[str(threshold)] = {
                "status": "calibration",
                "all": all_metrics,
                "by_season": by_season,
                "bootstrap_brier_skill": _bootstrap_skill(
                    labels, probabilities, seasons, samples,
                ),
            }
        else:
            for season in SEASONS:
                mask = seasons == season
                by_season[str(season)] = _descriptive_metrics(
                    labels[mask], probabilities[mask],
                )
            threshold_results[str(threshold)] = {
                "status": "descriptive_only_sparse_tail",
                "all": _descriptive_metrics(labels, probabilities),
                "by_season": by_season,
            }

    association: dict[str, Any] = {"all": {}, "by_season": {}}
    for name, predicted in (("q95", q95), ("q99", q99)):
        association["all"][name] = _correlation(predicted, selected_best)
        association["all"][name]["bootstrap"] = _bootstrap_correlation(
            predicted, selected_best, samples,
        )
    for season in SEASONS:
        mask = seasons == season
        season_sample_columns = np.all(seasons[samples] == season, axis=0)
        season_samples = samples[:, season_sample_columns]
        if season_samples.shape != (BOOTSTRAP_RESAMPLES, SLATES_PER_SEASON):
            raise ValueError("bootstrap season sample block identity differs")
        association["by_season"][str(season)] = {
            "slates": int(mask.sum()),
            "q95": _correlation(q95[mask], selected_best[mask]),
            "q99": _correlation(q99[mask], selected_best[mask]),
        }
        association["by_season"][str(season)]["q95"]["bootstrap"] = \
            _bootstrap_correlation(q95, selected_best, season_samples)
        association["by_season"][str(season)]["q99"]["bootstrap"] = \
            _bootstrap_correlation(q99, selected_best, season_samples)

    output: dict[str, Any] = {
        "audit_protocol_id": AUDIT_PROTOCOL_ID,
        "source_identity": {
            "sha256": source_sha256,
            "protocol": SOURCE_PROTOCOL_ID,
            "expected_code_sha": EXPECTED_CODE_SHA,
            "source_arm": SOURCE_ARM,
            "final_production_arm": FINAL_PRODUCTION_ARM,
        },
        "population": {
            "slates": SLATE_COUNT,
            "seasons": list(SEASONS),
            "slates_by_season": {
                str(season): SLATES_PER_SEASON for season in SEASONS
            },
            "entries_per_selected_book": ENTRY_COUNT,
            "simulated_worlds_per_selected_book": WORLD_COUNT,
            "exact80_count_attestation": "transitive_pinned_source",
            "selected_roster_identity_revalidated": False,
        },
        "bootstrap_design": {
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
            "within_season_stratified_slate_resampling": True,
            "season_sample_sizes_preserved": True,
            "interval": "percentile_95",
        },
        "thresholds": threshold_results,
        "selected_book_maximum_association": association,
        "interpretation_flags": {
            "retrospective_diagnostic_only": True,
            "absolute_calibration_estimand": True,
            "arm_transport_estimand": False,
            "fit_performed": False,
            "tuning_performed": False,
            "gate_licensed": False,
            "promotion_licensed": False,
            "production_change_licensed": False,
            "permanent_closure_licensed": False,
            "uses_realized_outcomes": True,
        },
    }
    _assert_json_finite(output)
    return output


def analyze_source_bytes(
    raw: bytes,
) -> dict[str, Any]:
    """Hash-lock source bytes, decode strict JSON, and run the audit."""
    return _analyze_source_bytes_for_test(
        raw, expected_source_sha256=EXPECTED_SOURCE_SHA256,
    )


def _analyze_source_bytes_for_test(
    raw: bytes,
    *,
    expected_source_sha256: str,
) -> dict[str, Any]:
    """Test-only source-byte analyzer with an explicit synthetic hash lock."""
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_source_sha256:
        raise ValueError(
            f"source report SHA-256 differs: expected {expected_source_sha256}, "
            f"observed {digest}"
        )
    return _analyze_report(load_source_json(raw), source_sha256=digest)


def analyze_source_path(path: str | Path) -> dict[str, Any]:
    """Read and audit the single frozen tracked source path."""
    return analyze_source_bytes(Path(path).read_bytes())


def canonical_json_bytes(result: Mapping[str, Any]) -> bytes:
    """Serialize a result deterministically, rejecting non-standard floats."""
    _assert_json_finite(result)
    return (
        json.dumps(
            result,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


__all__ = [
    "AUDIT_PROTOCOL_ID",
    "BOOTSTRAP_RESAMPLES",
    "BOOTSTRAP_SEED",
    "CALIBRATION_THRESHOLDS",
    "DESCRIPTIVE_THRESHOLDS",
    "EXPECTED_SOURCE_SHA256",
    "analyze_source_bytes",
    "analyze_source_path",
    "canonical_json_bytes",
    "load_source_json",
]
