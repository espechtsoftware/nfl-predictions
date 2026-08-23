#!/usr/bin/env python3
"""Two-phase retrospective A7 exact-80 rank-fusion diagnostic.

``freeze-selections`` derives the seven registered books without dereferencing
candidate scores.  ``score`` is allowed only after that manifest is present in
a pushed commit and then evaluates every frozen book from the already sealed
A7 report.  This script has no network, cloud, query, deployment, or mutation
path outside its create-once local output directory.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Final, Mapping, Sequence

import numpy as np


ROOT: Final = Path(__file__).resolve().parents[1]
RUN_ID: Final = "20260821-a7-corpus-rank-fusion-variations-v1"
VERSION: Final = "a7-corpus-rank-fusion-variations-v1"
LABEL: Final = "retrospective-post-outcome-exploratory"
PROTOCOL_PATH: Final = Path(
    "reports/2026-08-21-a7-corpus-rank-fusion-variations-v1.md"
)
PROTOCOL_SHA256: Final = (
    "b608f894f4373fd0350c77e4f10290828ba21e963e56b3f4187ae686c77eb433"
)
SOURCE_RUN_ID: Final = "20260820-a7-select-ladder-phase-s-incumbent-v2"
REPORT_SHA256: Final = (
    "e29c31df96f8d207361504d5db5615e3120ede77d783a0725a4721621bf74b15"
)
COMPLETION_SHA256: Final = (
    "af23011cc3f2d7837e62dedd1c492c999c47498643cc8c362c35dc0089674787"
)
FINISH_SHA256: Final = (
    "e9328355dbf43a1451ef8a705d898688ad5ec4eae1ad4639804b8cf30d70c692"
)
LEASE_RELEASE_SHA256: Final = (
    "0cb058154da510505100df3be56a9fc4851d073a46a2f962d3e411665632641f"
)
CHECKER_PATH: Final = Path("scripts/review_verify_a7_coprimaries.py")
CHECKER_SHA256: Final = (
    "8e967584eb6d210b1c5e54bdba4d4041f82ce775cd9348a5f66a24531280d0a7"
)
ENTRY_COUNT: Final = 80
MISSING_RANK: Final = 81
VARIANT_ORDER: Final = (
    "DS25", "DS50", "DS75", "RB25", "RB50", "RB75", "A7-100",
)
EXPECTED_SLATES: Final = tuple(
    (season, week) for season in (2023, 2024, 2025) for week in range(1, 19)
)
THRESHOLDS: Final = (187, 194, 200, 210, 220, 230, 240)
MICRO_DK_SCALE: Final = 1_000_000
CENT_TO_MICRO: Final = 10_000
CENT_RESIDUAL_MAX: Final = 1e-9
EPSILON: Final = 1e-12
EXACT_NONZERO_LIMIT: Final = 20
MONTE_CARLO_RESAMPLES: Final = 200_000
MONTE_CARLO_SEED: Final = 20_260_818
MONTE_CARLO_CHUNK: Final = 1 << 16
SELECTION_NAME: Final = "selection-manifest.json"
SELECTION_LEDGER_NAME: Final = "selection.sha256"
RESULT_NAME: Final = "result.json"
RESULT_LEDGER_NAME: Final = "result.sha256"
HEX64 = re.compile(r"[0-9a-f]{64}")
HEX40 = re.compile(r"[0-9a-f]{40}")


class VariationError(RuntimeError):
    """The frozen diagnostic contract or its retained evidence differs."""


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha_bytes(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _strict_json(path: Path, *, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise VariationError(f"{label} is absent or linked")
    raw = path.read_bytes()

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs_hook,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite constant: {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise VariationError(f"{label} is not strict JSON") from exc
    if not isinstance(value, dict) or raw != _canonical(value):
        raise VariationError(f"{label} is not canonical JSON")
    return value


def _implementation_sha256() -> str:
    return _sha(Path(__file__).resolve())


def _fixed_path_sha(path: Path, expected: str, *, label: str) -> None:
    if path.is_symlink() or not path.is_file() or _sha(path) != expected:
        raise VariationError(f"{label} differs")


def _validate_finish_ledger(directory: Path) -> None:
    ledger = directory / "finish.sha256"
    _fixed_path_sha(ledger, FINISH_SHA256, label="A7 finish ledger")
    rows: dict[str, str] = {}
    text = ledger.read_text(encoding="utf-8")
    if not text.endswith("\n") or "\r" in text:
        raise VariationError("A7 finish ledger encoding differs")
    for line in text.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9._-]+)", line)
        if match is None or match.group(2) in rows:
            raise VariationError("A7 finish ledger row differs")
        rows[match.group(2)] = match.group(1)
    required = {
        "report.json": REPORT_SHA256,
        "completion.txt": COMPLETION_SHA256,
    }
    if any(rows.get(name) != digest for name, digest in required.items()):
        raise VariationError("A7 finish ledger binding differs")
    for name, digest in rows.items():
        candidate = directory / name
        if candidate.is_symlink() or not candidate.is_file() or _sha(
            candidate
        ) != digest:
            raise VariationError(f"A7 finish member differs: {name}")


def _load_fixed_report(path: Path) -> dict[str, Any]:
    report_path = path.resolve(strict=True)
    if report_path.name != "report.json" or report_path.is_symlink():
        raise VariationError("input must be the sealed local report.json")
    _fixed_path_sha(ROOT / PROTOCOL_PATH, PROTOCOL_SHA256, label="protocol")
    _fixed_path_sha(ROOT / CHECKER_PATH, CHECKER_SHA256, label="checker")
    _fixed_path_sha(report_path, REPORT_SHA256, label="A7 report")
    _fixed_path_sha(
        report_path.parent / "completion.txt",
        COMPLETION_SHA256,
        label="A7 completion",
    )
    _fixed_path_sha(
        report_path.parent / "lease-release.txt",
        LEASE_RELEASE_SHA256,
        label="A7 lease closure",
    )
    _validate_finish_ledger(report_path.parent)
    report = _strict_json(report_path, label="A7 report")
    if report.get("run_id") != SOURCE_RUN_ID or report.get(
        "uses_realized_outcomes"
    ) is not True or report.get("actual_score_query_executed") is not True:
        raise VariationError("A7 report identity differs")
    return report


def _exact_index(value: object, *, label: str, maximum: int) -> int:
    if type(value) is not int or not 0 <= value < maximum:
        raise VariationError(f"{label} is not an exact in-range integer")
    return value


def _identity(value: object, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) != 9 or not all(
        isinstance(player, str) and player for player in value
    ):
        raise VariationError(f"{label} is malformed")
    result = tuple(value)
    if result != tuple(sorted(result)):
        raise VariationError(f"{label} is not canonical")
    return result


def _arm_order(
    row: Mapping[str, Any], arm: str, identities: Sequence[tuple[str, ...]],
) -> tuple[int, ...]:
    value = row.get(arm)
    if not isinstance(value, Mapping):
        raise VariationError(f"{arm} row is malformed")
    raw = value.get("indices")
    scorefree = value.get("scorefree")
    if not isinstance(raw, list) or not isinstance(scorefree, Mapping) or raw != (
        scorefree.get("selection_order")
    ):
        raise VariationError(f"{arm} score-free order differs")
    order = tuple(
        _exact_index(item, label=f"{arm} candidate index", maximum=len(identities))
        for item in raw
    )
    if len(order) != ENTRY_COUNT or len(set(order)) != ENTRY_COUNT:
        raise VariationError(f"{arm} order is not exact 80")
    retained = value.get("identities")
    if not isinstance(retained, list) or tuple(
        _identity(item, label=f"{arm} identity") for item in retained
    ) != tuple(identities[index] for index in order):
        raise VariationError(f"{arm} retained identities differ")
    return order


def _directional_swap(
    control: tuple[int, ...], treatment: tuple[int, ...], p: int,
) -> tuple[int, ...]:
    c_set, t_set = set(control), set(treatment)
    c_rank = {value: rank for rank, value in enumerate(control, start=1)}
    t_rank = {value: rank for rank, value in enumerate(treatment, start=1)}
    c_only = sorted(c_set - t_set, key=lambda value: (c_rank[value], value), reverse=True)
    t_only = sorted(t_set - c_set, key=lambda value: (t_rank[value], value))
    if len(c_only) != len(t_only) or not c_only:
        raise VariationError("directional difference is empty or asymmetric")
    count = (p * len(c_only) + 3) // 4
    result = (c_set - set(c_only[:count])) | set(t_only[:count])
    return tuple(sorted(result))


def _rank_blend(
    control: tuple[int, ...], treatment: tuple[int, ...], p: int,
) -> tuple[int, ...]:
    c_rank = {value: rank for rank, value in enumerate(control, start=1)}
    t_rank = {value: rank for rank, value in enumerate(treatment, start=1)}

    def key(value: int) -> tuple[int, int, int, int]:
        left = c_rank.get(value, MISSING_RANK)
        right = t_rank.get(value, MISSING_RANK)
        return (
            (4 - p) * left + p * right,
            max(left, right),
            min(left, right),
            value,
        )

    return tuple(sorted(sorted(set(control) | set(treatment), key=key)[:ENTRY_COUNT]))


def _variant_sets(
    control: tuple[int, ...], treatment: tuple[int, ...],
) -> dict[str, tuple[int, ...]]:
    result = {
        "DS25": _directional_swap(control, treatment, 1),
        "DS50": _directional_swap(control, treatment, 2),
        "DS75": _directional_swap(control, treatment, 3),
        "RB25": _rank_blend(control, treatment, 1),
        "RB50": _rank_blend(control, treatment, 2),
        "RB75": _rank_blend(control, treatment, 3),
        "A7-100": tuple(sorted(treatment)),
    }
    if tuple(result) != VARIANT_ORDER:
        raise AssertionError("variant order changed")
    c_set = set(control)
    for name, book in result.items():
        if len(book) != ENTRY_COUNT or len(set(book)) != ENTRY_COUNT or set(book) == c_set:
            raise VariationError(f"{name} is not a nonvacuous exact-80 book")
    if set(result["A7-100"]) != set(treatment):
        raise VariationError("A7 endpoint differs")
    return result


def _selection_manifest(
    report: Mapping[str, Any], *, implementation_sha256: str,
) -> dict[str, Any]:
    rows = report.get("slates")
    if not isinstance(rows, list) or len(rows) != len(EXPECTED_SLATES):
        raise VariationError("A7 slate population differs")
    manifest_rows: list[dict[str, Any]] = []
    for expected, row in zip(EXPECTED_SLATES, rows, strict=True):
        if not isinstance(row, Mapping) or (
            row.get("season"), row.get("week")
        ) != expected:
            raise VariationError("A7 slate order differs")
        raw_identities = row.get("candidate_identities")
        if not isinstance(raw_identities, list) or len(raw_identities) < ENTRY_COUNT:
            raise VariationError("candidate identities are incomplete")
        identities = tuple(
            _identity(value, label="candidate identity") for value in raw_identities
        )
        if len(set(identities)) != len(identities):
            raise VariationError("candidate identities repeat")
        control = _arm_order(row, "control", identities)
        treatment = _arm_order(row, "treatment", identities)
        if len(set(control) - set(treatment)) != len(set(treatment) - set(control)):
            raise VariationError("control/A7 directional difference is asymmetric")
        variants = _variant_sets(control, treatment)
        prior: dict[tuple[int, ...], list[str]] = {}
        variant_payload: dict[str, dict[str, Any]] = {}
        for name in VARIANT_ORDER:
            book = variants[name]
            coincides = list(prior.get(book, ()))
            variant_payload[name] = {
                "indices": list(book),
                "indices_sha256": _sha_bytes(_canonical(list(book))),
                "control_swaps": ENTRY_COUNT - len(set(book) & set(control)),
                "coincides_with_earlier_variants": coincides,
            }
            prior.setdefault(book, []).append(name)
        manifest_rows.append({
            "season": expected[0],
            "week": expected[1],
            "candidate_count": len(identities),
            "candidate_identities_sha256": _sha_bytes(
                _canonical([list(identity) for identity in identities])
            ),
            "directional_difference_count": len(set(control) - set(treatment)),
            "control_indices": sorted(control),
            "control_indices_sha256": _sha_bytes(_canonical(sorted(control))),
            "a7_indices": sorted(treatment),
            "a7_indices_sha256": _sha_bytes(_canonical(sorted(treatment))),
            "variants": variant_payload,
        })
    payload: dict[str, Any] = {
        "version": f"{VERSION}-selection-manifest",
        "run_id": RUN_ID,
        "analysis_label": LABEL,
        "protocol": {"path": str(PROTOCOL_PATH), "sha256": PROTOCOL_SHA256},
        "implementation": {
            "path": "scripts/analyze_a7_corpus_rank_fusions.py",
            "sha256": implementation_sha256,
        },
        "input": {
            "run_id": SOURCE_RUN_ID,
            "report_sha256": REPORT_SHA256,
            "completion_sha256": COMPLETION_SHA256,
            "finish_sha256": FINISH_SHA256,
            "lease_release_sha256": LEASE_RELEASE_SHA256,
            "checker_sha256": CHECKER_SHA256,
        },
        "entry_count": ENTRY_COUNT,
        "missing_rank": MISSING_RANK,
        "variant_order": list(VARIANT_ORDER),
        "slates": manifest_rows,
        "score_field_semantically_accessed": False,
        "new_outcome_query_executed": False,
        "historical_adoption_licensed": False,
        "production_change_licensed": False,
        "deployment_licensed": False,
        "prospective_shadow_licensed": False,
    }
    payload["selection_surface_sha256"] = _sha_bytes(_canonical(manifest_rows))
    return payload


def _score_to_micro(value: object) -> int:
    if type(value) not in (int, float) or not math.isfinite(float(value)):
        raise VariationError("candidate score is not a finite numeric scalar")
    scaled = float(value) * 100.0
    cents = round(scaled)
    if abs(scaled - cents) > CENT_RESIDUAL_MAX:
        raise VariationError("candidate score is not exact to a cent")
    return int(cents) * CENT_TO_MICRO


def _average_ranks(magnitudes: np.ndarray) -> np.ndarray:
    order = np.argsort(magnitudes, kind="mergesort")
    ranks = np.empty(len(magnitudes), dtype=float)
    sorted_values = magnitudes[order]
    start = 0
    while start < len(sorted_values):
        stop = start
        while stop + 1 < len(sorted_values) and sorted_values[stop + 1] == (
            sorted_values[start]
        ):
            stop += 1
        ranks[order[start:stop + 1]] = (start + stop) / 2.0 + 1.0
        start = stop + 1
    return ranks


def _paired_inference(control: np.ndarray, treatment: np.ndarray) -> dict[str, Any]:
    if control.dtype != np.int64 or treatment.dtype != np.int64 or control.shape != (
        len(EXPECTED_SLATES),
    ) or treatment.shape != control.shape:
        raise VariationError("paired exact-micro vectors differ")
    differences = treatment - control
    nonzero = differences[differences != 0]
    if not len(nonzero):
        return {
            "method": "degenerate", "n_nonzero": 0,
            "p_mean_two_sided": 1.0, "p_signed_rank_two_sided": 1.0,
            "signed_rank_statistic": 0.0,
        }
    ranks = _average_ranks(np.abs(nonzero))
    observed_sum = float(nonzero.sum())
    observed_rank = float(ranks[nonzero > 0].sum())
    rank_center = float(ranks.sum()) / 2.0
    hits_mean = hits_rank = 0
    if len(nonzero) <= EXACT_NONZERO_LIMIT:
        total = 1 << len(nonzero)
        bits = np.arange(len(nonzero))
        for first in range(0, total, MONTE_CARLO_CHUNK):
            stop = min(first + MONTE_CARLO_CHUNK, total)
            codes = np.arange(first, stop, dtype=np.int64)
            flips = ((codes[:, None] >> bits[None, :]) & 1).astype(float)
            signs = 1.0 - 2.0 * flips
            signed_sums = signs @ nonzero
            positive_ranks = ((signs > 0) * ranks[None, :]).sum(axis=1)
            hits_mean += int((np.abs(signed_sums) >= abs(observed_sum) - EPSILON).sum())
            hits_rank += int((
                np.abs(positive_ranks - rank_center)
                >= abs(observed_rank - rank_center) - EPSILON
            ).sum())
        method = "exact_enumeration"
        p_mean = hits_mean / total
        p_rank = hits_rank / total
    else:
        rng = np.random.default_rng(MONTE_CARLO_SEED)
        completed = 0
        while completed < MONTE_CARLO_RESAMPLES:
            take = min(MONTE_CARLO_CHUNK, MONTE_CARLO_RESAMPLES - completed)
            signs = rng.choice((-1.0, 1.0), size=(take, len(nonzero)))
            signed_sums = signs @ nonzero
            positive_ranks = ((signs > 0) * ranks[None, :]).sum(axis=1)
            hits_mean += int((np.abs(signed_sums) >= abs(observed_sum) - EPSILON).sum())
            hits_rank += int((
                np.abs(positive_ranks - rank_center)
                >= abs(observed_rank - rank_center) - EPSILON
            ).sum())
            completed += take
        method = "monte_carlo"
        p_mean = (hits_mean + 1) / (MONTE_CARLO_RESAMPLES + 1)
        p_rank = (hits_rank + 1) / (MONTE_CARLO_RESAMPLES + 1)
    return {
        "method": method,
        "n_nonzero": int(len(nonzero)),
        "p_mean_two_sided": float(min(1.0, p_mean)),
        "p_signed_rank_two_sided": float(min(1.0, p_rank)),
        "signed_rank_statistic": observed_rank,
    }


def _median_fraction(values: np.ndarray) -> tuple[int, int]:
    ordered = sorted(int(value) for value in values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle], 1
    return ordered[middle - 1] + ordered[middle], 2


def _render_variant(
    name: str,
    control: np.ndarray,
    treatment: np.ndarray,
    swaps: Sequence[int],
) -> dict[str, Any]:
    differences = treatment - control
    inference = _paired_inference(control, treatment)
    threshold_counts = {
        str(threshold): int(np.count_nonzero(treatment >= threshold * MICRO_DK_SCALE))
        for threshold in THRESHOLDS
    }
    control_counts = {
        str(threshold): int(np.count_nonzero(control >= threshold * MICRO_DK_SCALE))
        for threshold in THRESHOLDS
    }
    median_num, median_den = _median_fraction(treatment)
    seasons: dict[str, dict[str, Any]] = {}
    for season in (2023, 2024, 2025):
        positions = [
            index for index, key in enumerate(EXPECTED_SLATES) if key[0] == season
        ]
        delta_sum = int(differences[positions].sum())
        seasons[str(season)] = {
            "delta_sum_micro": delta_sum,
            "delta_mean_dk": delta_sum / (len(positions) * MICRO_DK_SCALE),
        }
    result = {
        "variant": name,
        "maxima_micro": [int(value) for value in treatment],
        "sum_max_micro": int(treatment.sum()),
        "mean_max_dk": float(treatment.sum() / (len(treatment) * MICRO_DK_SCALE)),
        "median_max_micro_numerator": median_num,
        "median_max_micro_denominator": median_den,
        "mean_delta_dk": float(differences.sum() / (
            len(differences) * MICRO_DK_SCALE
        )),
        "delta_sum_micro": int(differences.sum()),
        "treatment_better": int(np.count_nonzero(differences > 0)),
        "tied": int(np.count_nonzero(differences == 0)),
        "control_better": int(np.count_nonzero(differences < 0)),
        "inference": inference,
        "p_joint": max(
            inference["p_mean_two_sided"],
            inference["p_signed_rank_two_sided"],
        ),
        "threshold_counts": threshold_counts,
        "threshold_deltas": {
            key: value - control_counts[key] for key, value in threshold_counts.items()
        },
        "season_deltas": seasons,
        "control_swaps": {
            "minimum": min(swaps),
            "sum": sum(swaps),
            "mean": sum(swaps) / len(swaps),
            "maximum": max(swaps),
        },
    }
    return result


def _holm(variants: Sequence[dict[str, Any]]) -> None:
    ordered = sorted(
        range(len(variants)), key=lambda index: (variants[index]["p_joint"], index)
    )
    running = 0.0
    adjusted = [0.0] * len(variants)
    total = len(variants)
    for position, index in enumerate(ordered):
        candidate = min(1.0, (total - position) * variants[index]["p_joint"])
        running = max(running, candidate)
        adjusted[index] = running
    for index, value in enumerate(adjusted):
        variants[index]["holm_adjusted_p_joint"] = value


def _validate_base_reconstruction(
    report: Mapping[str, Any], control: np.ndarray, treatment: np.ndarray,
) -> None:
    cuts = report.get("outcome", {}).get("cuts", {}).get("80")
    if not isinstance(cuts, Mapping):
        raise VariationError("sealed A7 exact-80 outcome is absent")
    for label, values in (("control", control), ("treatment", treatment)):
        expected_mean = cuts.get(f"{label}_mean")
        expected_counts = cuts.get(f"{label}_threshold_counts")
        actual_mean = values.sum() / (len(values) * MICRO_DK_SCALE)
        counts = {
            str(threshold): int(np.count_nonzero(values >= threshold * MICRO_DK_SCALE))
            for threshold in THRESHOLDS
        }
        if type(expected_mean) not in (int, float) or abs(
            float(expected_mean) - actual_mean
        ) > EPSILON or expected_counts != counts:
            raise VariationError(f"sealed A7 {label} reconstruction differs")


def _score_result(
    report: Mapping[str, Any], manifest: Mapping[str, Any],
) -> dict[str, Any]:
    rows = report.get("slates")
    manifest_rows = manifest.get("slates")
    if not isinstance(rows, list) or not isinstance(manifest_rows, list) or len(
        rows
    ) != len(EXPECTED_SLATES) or len(manifest_rows) != len(rows):
        raise VariationError("score/selection slate population differs")
    control_values: list[int] = []
    a7_values: list[int] = []
    variant_values = {name: [] for name in VARIANT_ORDER}
    variant_swaps = {name: [] for name in VARIANT_ORDER}
    for expected, row, frozen in zip(EXPECTED_SLATES, rows, manifest_rows, strict=True):
        if not isinstance(row, Mapping) or not isinstance(frozen, Mapping) or (
            row.get("season"), row.get("week")
        ) != expected or (frozen.get("season"), frozen.get("week")) != expected:
            raise VariationError("score/selection slate order differs")
        raw_scores = row.get("candidate_actual_scores")
        raw_identities = row.get("candidate_identities")
        if not isinstance(raw_scores, list) or not isinstance(raw_identities, list) or len(
            raw_scores
        ) != len(raw_identities):
            raise VariationError("candidate score alignment differs")
        scores = tuple(_score_to_micro(value) for value in raw_scores)
        identities = tuple(
            _identity(value, label="candidate identity") for value in raw_identities
        )
        for arm, frozen_key, target in (
            ("control", "control_indices", control_values),
            ("treatment", "a7_indices", a7_values),
        ):
            arm_value = row.get(arm)
            realized = arm_value.get("realized") if isinstance(arm_value, Mapping) else None
            order = arm_value.get("indices") if isinstance(arm_value, Mapping) else None
            if not isinstance(realized, Mapping) or not isinstance(order, list):
                raise VariationError(f"sealed {arm} realized receipt differs")
            frozen_set = frozen.get(frozen_key)
            if not isinstance(frozen_set, list) or sorted(order) != frozen_set:
                raise VariationError(f"frozen {arm} book differs")
            retained_scores = realized.get("scores")
            retained_identities = realized.get("identities")
            if not isinstance(retained_scores, list) or tuple(
                _score_to_micro(value) for value in retained_scores
            ) != tuple(scores[index] for index in order) or not isinstance(
                retained_identities, list
            ) or tuple(
                _identity(value, label=f"{arm} realized identity")
                for value in retained_identities
            ) != tuple(identities[index] for index in order):
                raise VariationError(f"sealed {arm} ordered realization differs")
            maximum = max(scores[index] for index in order)
            prefix = realized.get("prefix_maxima")
            if not isinstance(prefix, Mapping) or _score_to_micro(prefix.get("80")) != maximum:
                raise VariationError(f"sealed {arm} N80 maximum differs")
            target.append(maximum)
        variants = frozen.get("variants")
        if not isinstance(variants, Mapping) or tuple(variants) != VARIANT_ORDER:
            raise VariationError("frozen variant order differs")
        for name in VARIANT_ORDER:
            item = variants[name]
            indices = item.get("indices") if isinstance(item, Mapping) else None
            swaps = item.get("control_swaps") if isinstance(item, Mapping) else None
            if not isinstance(indices, list) or len(indices) != ENTRY_COUNT or type(
                swaps
            ) is not int:
                raise VariationError(f"frozen {name} book differs")
            variant_values[name].append(max(scores[index] for index in indices))
            variant_swaps[name].append(swaps)
    control_array = np.asarray(control_values, dtype=np.int64)
    treatment_array = np.asarray(a7_values, dtype=np.int64)
    _validate_base_reconstruction(report, control_array, treatment_array)
    rendered = [
        _render_variant(
            name,
            control_array,
            np.asarray(variant_values[name], dtype=np.int64),
            variant_swaps[name],
        )
        for name in VARIANT_ORDER
    ]
    _holm(rendered)
    eligible: list[dict[str, Any]] = []
    for result in rendered:
        season_nonnegative = sum(
            value["delta_sum_micro"] >= 0
            for value in result["season_deltas"].values()
        )
        result["nominee_eligible"] = bool(
            result["delta_sum_micro"] > 0
            and result["threshold_deltas"]["194"] >= -1
            and result["threshold_deltas"]["200"] >= -1
            and result["treatment_better"] >= result["control_better"]
            and season_nonnegative >= 2
        )
        if result["nominee_eligible"]:
            eligible.append(result)
    nominee = None
    if eligible:
        nominee = min(eligible, key=lambda result: (
            result["holm_adjusted_p_joint"],
            -result["delta_sum_micro"],
            result["control_swaps"]["sum"],
            VARIANT_ORDER.index(result["variant"]),
        ))["variant"]
    result_payload = {
        "version": f"{VERSION}-result",
        "run_id": RUN_ID,
        "analysis_label": LABEL,
        "protocol_sha256": PROTOCOL_SHA256,
        "implementation_sha256": _implementation_sha256(),
        "input_report_sha256": REPORT_SHA256,
        "selection_manifest_sha256": _sha_bytes(_canonical(dict(manifest))),
        "variant_order": list(VARIANT_ORDER),
        "control": {
            "maxima_micro": [int(value) for value in control_array],
            "sum_max_micro": int(control_array.sum()),
            "mean_max_dk": float(control_array.sum() / (
                len(control_array) * MICRO_DK_SCALE
            )),
            "threshold_counts": {
                str(threshold): int(np.count_nonzero(
                    control_array >= threshold * MICRO_DK_SCALE
                )) for threshold in THRESHOLDS
            },
        },
        "variants": rendered,
        "eligible_variants": [
            result["variant"] for result in rendered if result["nominee_eligible"]
        ],
        "future_prospective_nominee": nominee,
        "nomination_scope": (
            "draft-and-freeze-one-fresh-unseen-2026-prospective-test-only"
            if nominee is not None else "none"
        ),
        "retrospective_post_outcome_exploratory": True,
        "new_outcome_query_executed": False,
        "historical_adoption_licensed": False,
        "production_change_licensed": False,
        "deployment_licensed": False,
        "prospective_shadow_licensed": False,
        "followup_corpus_variation_licensed": False,
    }
    return result_payload


def _output_directory(path: Path) -> Path:
    target = path.resolve(strict=False)
    if not target.is_absolute() or target.is_symlink():
        raise VariationError("output directory must be an absolute real path")
    if target.exists():
        if not target.is_dir():
            raise VariationError("output path is not a directory")
    else:
        if not target.parent.is_dir() or target.parent.is_symlink():
            raise VariationError("output parent differs")
        target.mkdir()
    return target


def _write_or_validate(path: Path, raw: bytes) -> None:
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise VariationError(f"create-once collision: {path.name}")
        return
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()


def _write_pair(directory: Path, name: str, ledger_name: str, value: object) -> None:
    raw = _canonical(value)
    _write_or_validate(directory / name, raw)
    ledger = f"{_sha_bytes(raw)}  {name}\n".encode("utf-8")
    _write_or_validate(directory / ledger_name, ledger)


def _load_selection(directory: Path) -> dict[str, Any]:
    manifest_path = directory / SELECTION_NAME
    manifest = _strict_json(manifest_path, label="selection manifest")
    expected_ledger = f"{_sha(manifest_path)}  {SELECTION_NAME}\n".encode("utf-8")
    ledger = directory / SELECTION_LEDGER_NAME
    if ledger.is_symlink() or not ledger.is_file() or ledger.read_bytes() != expected_ledger:
        raise VariationError("selection ledger differs")
    return manifest


def _git(args: Sequence[str]) -> bytes:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError as exc:
        raise VariationError("selection commit is not pushed authority") from exc


def _validate_selection_commit(path: Path, commit: str, expected_sha: str) -> None:
    if HEX40.fullmatch(commit) is None or HEX64.fullmatch(expected_sha) is None:
        raise VariationError("selection commit/hash is malformed")
    if _sha(path) != expected_sha:
        raise VariationError("selection manifest external hash differs")
    try:
        relative = path.resolve(strict=True).relative_to(ROOT)
    except ValueError as exc:
        raise VariationError("selection manifest is outside repository") from exc
    retained = _git(["show", f"{commit}:{relative.as_posix()}"])
    if retained != path.read_bytes():
        raise VariationError("selection manifest differs from committed bytes")
    _git(["merge-base", "--is-ancestor", commit, "origin/main"])


def _freeze(args: argparse.Namespace) -> int:
    report = _load_fixed_report(Path(args.report))
    output = _output_directory(Path(args.output_dir))
    allowed = {SELECTION_NAME, SELECTION_LEDGER_NAME}
    if any(child.name not in allowed for child in output.iterdir()):
        raise VariationError("selection output population differs")
    manifest = _selection_manifest(
        report, implementation_sha256=_implementation_sha256()
    )
    _write_pair(output, SELECTION_NAME, SELECTION_LEDGER_NAME, manifest)
    print(f"A7_CORPUS_SELECTIONS_FROZEN sha256={_sha(output / SELECTION_NAME)}")
    return 0


def _score(args: argparse.Namespace) -> int:
    report = _load_fixed_report(Path(args.report))
    output = _output_directory(Path(args.output_dir))
    allowed = {SELECTION_NAME, SELECTION_LEDGER_NAME, RESULT_NAME, RESULT_LEDGER_NAME}
    if any(child.name not in allowed for child in output.iterdir()):
        raise VariationError("score output population differs")
    manifest = _load_selection(output)
    expected_manifest = _selection_manifest(
        report, implementation_sha256=_implementation_sha256()
    )
    if manifest != expected_manifest:
        raise VariationError("selection manifest failed independent replay")
    _validate_selection_commit(
        output / SELECTION_NAME,
        args.selection_commit,
        args.selection_manifest_sha256,
    )
    sys.path.insert(0, str(ROOT / "scripts"))
    import review_verify_a7_coprimaries as checker  # noqa: PLC0415

    checked, _completion = checker._fully_harvested_result(  # noqa: SLF001
        Path(args.report).resolve(strict=True)
    )
    if checked != report:
        raise VariationError("independent A7 report replay differs")
    result = _score_result(report, manifest)
    _write_pair(output, RESULT_NAME, RESULT_LEDGER_NAME, result)
    print(
        "A7_CORPUS_VARIATIONS_SCORED "
        f"nominee={result['future_prospective_nominee']} "
        f"sha256={_sha(output / RESULT_NAME)}"
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze-selections")
    freeze.add_argument("--report", required=True)
    freeze.add_argument("--output-dir", required=True)
    freeze.set_defaults(function=_freeze)
    score = sub.add_parser("score")
    score.add_argument("--report", required=True)
    score.add_argument("--output-dir", required=True)
    score.add_argument("--selection-commit", required=True)
    score.add_argument("--selection-manifest-sha256", required=True)
    score.set_defaults(function=_score)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return int(args.function(args))
    except (VariationError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
