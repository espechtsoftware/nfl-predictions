"""Pure scientific boundary for the A7 incumbent-pool selector arm.

This module has no warehouse, cloud, filesystem, or production-policy side
effects.  It applies the already registered default-off ``SELECT_LADDER``
selector to one immutable candidate/world matrix, constructs the outcome-free
simultaneous-extremes falsifier, and aggregates separately supplied realized
lineup scores under the frozen A7 disposition law.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from typing import Any

import numpy as np

from nfl_dfs.optimizer.lineup import select_tail_entries
from nfl_dfs.research.paired_max_stats import paired_weekly_max_report


PROTOCOL_ID = "20260820-a7-select-ladder-phase-s-incumbent-v1"
LADDER_SPEC = "170:10,180:10,187:7,194:7,200:6,210:10"
LADDER = {170.0: 10, 180.0: 10, 187.0: 7,
          194.0: 7, 200.0: 6, 210.0: 10}
CONTROL_ENV = {"SELECT_LSE": "0", "SELECT_LADDER": ""}
TREATMENT_ENV = {"SELECT_LSE": "0", "SELECT_LADDER": LADDER_SPEC}
ENTRY_COUNT = 80
PREFIX_COUNTS = (4, 14, 80)
REPORT_THRESHOLDS = (187, 194, 200, 210, 220, 230, 240)
WORLDS_PER_BLOCK = 10_000
BLOCK_COUNT = 5
REALISM_QUANTILES = (0.99, 0.995)
REALISM_R3_MARGIN = 0.01
REALISM_R3_MARGIN_NUMERATOR = 1
REALISM_R3_MARGIN_DENOMINATOR = 100
R3_SUPPORT_MIN_EVENTS = 100
SHOULDER_NONINFERIORITY_SLATES = -1
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20_260_820


def _identity(values: Sequence[object]) -> tuple[str, ...]:
    result = tuple(sorted(str(value) for value in values))
    if len(result) != 9 or len(set(result)) != 9 or any(not value for value in result):
        raise ValueError("A7 candidate identity must contain nine unique IDs")
    return result


def _identities(values: Sequence[Sequence[object]]) -> tuple[tuple[str, ...], ...]:
    result = tuple(_identity(value) for value in values)
    if len(result) != len(set(result)):
        raise ValueError("A7 candidate identities repeat")
    return result


def _matrix(value: np.ndarray, *, rows: int | None = None) -> np.ndarray:
    result = np.asarray(value, dtype=np.float32)
    if result.ndim != 2 or result.shape[0] < ENTRY_COUNT or result.shape[1] != (
        BLOCK_COUNT * WORLDS_PER_BLOCK
    ) or not np.isfinite(result).all():
        raise ValueError("A7 candidate/world matrix differs")
    if rows is not None and result.shape[0] != rows:
        raise ValueError("A7 candidate/world identity count differs")
    return result


def select_books(candidate_totals: np.ndarray) -> dict[str, list[int]]:
    """Select the frozen control/treatment exact-80 orders.

    Direct N=4/N=14 calls must be prefixes of the exact-80 call.  This is
    expected from both sequential greedy laws and is asserted so a future
    selector refactor cannot silently change the registered secondary estimand.
    """
    totals = _matrix(candidate_totals)
    result: dict[str, list[int]] = {}
    for arm, env in (("control", CONTROL_ENV), ("treatment", TREATMENT_ENV)):
        selected = select_tail_entries(totals, ENTRY_COUNT, 194.0, env=env)
        if len(selected) != ENTRY_COUNT or len(set(selected)) != ENTRY_COUNT or any(
            index < 0 or index >= len(totals) for index in selected
        ):
            raise ValueError(f"A7 {arm} selector did not return exact-80")
        for prefix in PREFIX_COUNTS[:-1]:
            direct = select_tail_entries(totals, prefix, 194.0, env=env)
            if direct != selected[:prefix]:
                raise ValueError(f"A7 {arm} selector is not prefix-invariant")
        result[arm] = [int(index) for index in selected]
    return result


def selected_identities(
    candidate_identities: Sequence[Sequence[object]], selected: Sequence[int],
) -> list[list[str]]:
    identities = _identities(candidate_identities)
    indices = [int(index) for index in selected]
    if len(indices) != ENTRY_COUNT or len(set(indices)) != ENTRY_COUNT or any(
        index < 0 or index >= len(identities) for index in indices
    ):
        raise ValueError("A7 selected indices differ")
    return [list(identities[index]) for index in indices]


def _world_ladder_gain(previous: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    gain = np.zeros(previous.shape, dtype=np.int64)
    for threshold, weight in LADDER.items():
        gain += int(weight) * ((candidate >= threshold) & (previous < threshold))
    return gain


def scorefree_book_receipt(
    *,
    candidate_totals: np.ndarray,
    candidate_identities: Sequence[Sequence[object]],
    selected: Sequence[int],
    player_ids: Sequence[object],
    player_draws: np.ndarray,
) -> dict[str, Any]:
    """Build the ordered marginal-utility and simultaneous-extremes receipt."""
    identities = _identities(candidate_identities)
    totals = _matrix(candidate_totals, rows=len(identities))
    ids = tuple(str(value) for value in player_ids)
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        raise ValueError("A7 player IDs differ")
    draws = np.asarray(player_draws, dtype=np.float32)
    if draws.shape != (len(ids), BLOCK_COUNT * WORLDS_PER_BLOCK) or not np.isfinite(
        draws
    ).all():
        raise ValueError("A7 player/world matrix differs")
    by_id = {player_id: index for index, player_id in enumerate(ids)}
    indices = [int(index) for index in selected]
    if (
        len(indices) != ENTRY_COUNT
        or len(set(indices)) != ENTRY_COUNT
        or any(index < 0 or index >= len(identities) for index in indices)
    ):
        raise ValueError("A7 score-free book is not exact-80")
    try:
        roster_rows = {
            index: np.asarray(sorted(
                by_id[player_id] for player_id in identities[index]
            ), dtype=np.int64)
            for index in indices
        }
    except (KeyError, IndexError) as exc:
        raise ValueError("A7 selected roster is outside the player universe") from exc
    for index, rows in roster_rows.items():
        reconstructed = draws[rows].sum(axis=0, dtype=np.float32)
        if not np.array_equal(reconstructed, totals[index]):
            raise ValueError("A7 candidate total differs from player draws")

    quantile_cutoffs: dict[float, list[np.ndarray]] = {
        quantile: [] for quantile in REALISM_QUANTILES
    }
    for block in range(BLOCK_COUNT):
        start = block * WORLDS_PER_BLOCK
        stop = start + WORLDS_PER_BLOCK
        block_draws = draws[:, start:stop]
        for quantile in REALISM_QUANTILES:
            quantile_cutoffs[quantile].append(np.quantile(
                block_draws, quantile, axis=1, method="higher",
            ).astype(np.float32))

    previous = np.zeros(totals.shape[1], dtype=np.float32)
    by_block = [0] * BLOCK_COUNT
    histograms = {
        str(quantile): [0] * 10 for quantile in REALISM_QUANTILES
    }
    histograms_by_block = {
        str(quantile): [[0] * 10 for _ in range(BLOCK_COUNT)]
        for quantile in REALISM_QUANTILES
    }
    positive_events_by_block = {
        str(quantile): [[0] * 10 for _ in range(BLOCK_COUNT)]
        for quantile in REALISM_QUANTILES
    }
    trace: list[dict[str, Any]] = []
    for position, index in enumerate(indices):
        candidate = totals[index]
        world_gain = _world_ladder_gain(previous, candidate)
        block_gains: list[int] = []
        for block in range(BLOCK_COUNT):
            start = block * WORLDS_PER_BLOCK
            stop = start + WORLDS_PER_BLOCK
            gain = world_gain[start:stop]
            gain_sum = int(gain.sum(dtype=np.int64))
            block_gains.append(gain_sum)
            by_block[block] += gain_sum
            block_draws = draws[roster_rows[index], start:stop]
            for quantile in REALISM_QUANTILES:
                cutoff = quantile_cutoffs[quantile][block][roster_rows[index]]
                extreme_count = np.count_nonzero(
                    block_draws > cutoff[:, None], axis=0,
                )
                weighted = np.bincount(
                    extreme_count, weights=gain, minlength=10,
                )
                if not np.all(weighted == np.rint(weighted)):
                    raise ValueError("A7 realism weights are not integral")
                key = str(quantile)
                histograms[key] = [
                    current + int(round(addition))
                    for current, addition in zip(
                        histograms[key], weighted.tolist(), strict=True,
                    )
                ]
                histograms_by_block[key][block] = [
                    current + int(round(addition))
                    for current, addition in zip(
                        histograms_by_block[key][block], weighted.tolist(),
                        strict=True,
                    )
                ]
                event_counts = np.bincount(
                    extreme_count[gain > 0], minlength=10,
                )
                positive_events_by_block[key][block] = [
                    current + int(addition)
                    for current, addition in zip(
                        positive_events_by_block[key][block],
                        event_counts.tolist(), strict=True,
                    )
                ]
        trace.append({
            "position": int(position),
            "candidate_index": int(index),
            "identity": list(identities[index]),
            "marginal_gain": int(world_gain.sum(dtype=np.int64)),
            "marginal_gain_by_block": block_gains,
        })
        np.maximum(previous, candidate, out=previous)

    total = int(sum(by_block))
    if total <= 0:
        raise ValueError("A7 book has zero ladder utility")
    realism: dict[str, Any] = {}
    for quantile in REALISM_QUANTILES:
        histogram = histograms[str(quantile)]
        if sum(histogram) != total:
            raise ValueError("A7 realism histogram does not conserve utility")
        realism[str(quantile)] = {
            "utility_by_extreme_player_count": histogram,
            "utility_by_extreme_player_count_by_block": (
                histograms_by_block[str(quantile)]
            ),
            "positive_gain_events_by_extreme_player_count_by_block": (
                positive_events_by_block[str(quantile)]
            ),
            "r2": float(sum(histogram[2:]) / total),
            "r3": float(sum(histogram[3:]) / total),
            "r4": float(sum(histogram[4:]) / total),
        }
    return {
        "ladder_spec": LADDER_SPEC,
        "selection_order": indices,
        "selection_order_sha256": sha256(json.dumps(
            indices, separators=(",", ":"),
        ).encode()).hexdigest(),
        "total_ladder_utility": total,
        "ladder_utility_by_block": by_block,
        "realism": realism,
        "trace": trace,
    }


def _sum_histograms(rows: Sequence[Mapping[str, Any]], arm: str, q: str) -> list[int]:
    result = [0] * 10
    for row in rows:
        values = row[arm]["scorefree"]["realism"][q][
            "utility_by_extreme_player_count"
        ]
        if (
            not isinstance(values, list)
            or len(values) != 10
            or any(type(value) is not int or value < 0 for value in values)
        ):
            raise ValueError("A7 realism histogram differs")
        result = [
            current + value
            for current, value in zip(result, values, strict=True)
        ]
    return result


def _sum_block_histograms(
    rows: Sequence[Mapping[str, Any]],
    arm: str,
    q: str,
    field: str,
) -> list[list[int]]:
    result = [[0] * 10 for _ in range(BLOCK_COUNT)]
    for row in rows:
        values = row[arm]["scorefree"]["realism"][q].get(field)
        if not isinstance(values, list) or len(values) != BLOCK_COUNT:
            raise ValueError("A7 block realism receipt differs")
        for block, histogram in enumerate(values):
            if (
                not isinstance(histogram, list)
                or len(histogram) != 10
                or any(type(value) is not int or value < 0 for value in histogram)
            ):
                raise ValueError("A7 block realism histogram differs")
            result[block] = [
                current + value
                for current, value in zip(result[block], histogram, strict=True)
            ]
    return result


def aggregate_scorefree(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate the 54-slate pre-outcome mechanism and realism gates."""
    if len(rows) != 54:
        raise ValueError("A7 score-free population must contain 54 slates")
    keys = [(int(row["season"]), int(row["week"])) for row in rows]
    expected = {(season, week) for season in (2023, 2024, 2025)
                for week in range(1, 19)}
    if set(keys) != expected or len(set(keys)) != 54:
        raise ValueError("A7 score-free slate population differs")
    changed = 0
    utility = {arm: 0 for arm in ("control", "treatment")}
    blocks = {arm: [0] * BLOCK_COUNT for arm in ("control", "treatment")}
    for row in rows:
        for arm in ("control", "treatment"):
            selected = row[arm].get("identities")
            if not isinstance(selected, list) or len(selected) != ENTRY_COUNT:
                raise ValueError("A7 score-free exact-80 identity receipt differs")
            if len({_identity(value) for value in selected}) != ENTRY_COUNT:
                raise ValueError("A7 score-free book identities repeat")
            receipt = row[arm]["scorefree"]
            total = int(receipt["total_ladder_utility"])
            by_block = [int(value) for value in receipt["ladder_utility_by_block"]]
            if total <= 0 or len(by_block) != BLOCK_COUNT or sum(by_block) != total:
                raise ValueError("A7 score-free utility receipt differs")
            utility[arm] += total
            blocks[arm] = [
                current + value
                for current, value in zip(blocks[arm], by_block, strict=True)
            ]
        changed += int(
            {_identity(value) for value in row["control"]["identities"]}
            != {_identity(value) for value in row["treatment"]["identities"]}
        )

    realism = {}
    for q in map(str, REALISM_QUANTILES):
        realism[q] = {}
        for arm in ("control", "treatment"):
            histogram = _sum_histograms(rows, arm, q)
            by_block = _sum_block_histograms(
                rows, arm, q, "utility_by_extreme_player_count_by_block",
            )
            positive_events_by_block = _sum_block_histograms(
                rows, arm, q,
                "positive_gain_events_by_extreme_player_count_by_block",
            )
            denominator = sum(histogram)
            if (
                denominator != utility[arm]
                or denominator <= 0
                or [sum(value) for value in by_block] != blocks[arm]
                or [
                    sum(value[index] for value in by_block)
                    for index in range(10)
                ] != histogram
            ):
                raise ValueError("A7 aggregate realism denominator differs")
            realism[q][arm] = {
                "utility_by_extreme_player_count": histogram,
                "utility_by_extreme_player_count_by_block": by_block,
                "positive_gain_events_by_extreme_player_count_by_block": (
                    positive_events_by_block
                ),
                "r2": float(sum(histogram[2:]) / denominator),
                "r3": float(sum(histogram[3:]) / denominator),
                "r4": float(sum(histogram[4:]) / denominator),
            }
    control_histogram = realism["0.99"]["control"][
        "utility_by_extreme_player_count"
    ]
    treatment_histogram = realism["0.99"]["treatment"][
        "utility_by_extreme_player_count"
    ]
    control_r3_numerator = sum(control_histogram[3:])
    treatment_r3_numerator = sum(treatment_histogram[3:])
    control_r3_denominator = sum(control_histogram)
    treatment_r3_denominator = sum(treatment_histogram)
    control_r3 = control_r3_numerator / control_r3_denominator
    treatment_r3 = treatment_r3_numerator / treatment_r3_denominator
    # Compare t_num/t_den - c_num/c_den <= 1/100 exactly. Integer
    # histograms are the gate; binary floats below are report-only.
    r3_difference_cross_product = (
        treatment_r3_numerator * control_r3_denominator
        - control_r3_numerator * treatment_r3_denominator
    )
    r3_margin_noninferior = (
        r3_difference_cross_product * REALISM_R3_MARGIN_DENOMINATOR
        <= REALISM_R3_MARGIN_NUMERATOR
        * treatment_r3_denominator * control_r3_denominator
    )
    support = support_census(rows)
    supported = support["passes"] is True
    improved_blocks = sum(
        treatment > control
        for control, treatment in zip(
            blocks["control"], blocks["treatment"], strict=True,
        )
    )
    conditions = {
        "treatment_nonvacuous": changed > 0,
        "aggregate_ladder_utility_strictly_improves": (
            utility["treatment"] > utility["control"]
        ),
        "at_least_four_world_blocks_improve": improved_blocks >= 4,
        "realism_r3_supported": supported,
        "realism_r3_noninferior": (
            supported and r3_margin_noninferior
        ),
    }
    mechanics_conditions = {
        key: value for key, value in conditions.items()
        if key not in {"realism_r3_supported", "realism_r3_noninferior"}
    }
    return {
        "protocol_id": PROTOCOL_ID,
        "uses_realized_outcomes": False,
        "slates": 54,
        "changed_slates": int(changed),
        "ladder_utility": utility,
        "ladder_utility_by_block": blocks,
        "improved_world_blocks": int(improved_blocks),
        "realism": realism,
        "support": support,
        "realism_r3_delta": float(treatment_r3 - control_r3),
        "realism_r3_exact_comparison": {
            "control_numerator": int(control_r3_numerator),
            "control_denominator": int(control_r3_denominator),
            "treatment_numerator": int(treatment_r3_numerator),
            "treatment_denominator": int(treatment_r3_denominator),
            "difference_cross_product": int(r3_difference_cross_product),
            "margin_numerator": REALISM_R3_MARGIN_NUMERATOR,
            "margin_denominator": REALISM_R3_MARGIN_DENOMINATOR,
            "noninferior": bool(r3_margin_noninferior),
        },
        "conditions": conditions,
        "mechanics_passes": all(mechanics_conditions.values()),
        "passes": all(conditions.values()),
    }


def support_census(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return only preregistration support counts, never arm effects."""
    if len(rows) != 54:
        raise ValueError("A7 support census must contain 54 slates")
    keys = {(int(row["season"]), int(row["week"])) for row in rows}
    expected = {(season, week) for season in (2023, 2024, 2025)
                for week in range(1, 19)}
    if keys != expected:
        raise ValueError("A7 support census slate population differs")
    cells: dict[str, list[int]] = {}
    for arm in ("control", "treatment"):
        by_block = [0] * BLOCK_COUNT
        for row in rows:
            values = row[arm]["scorefree"]["realism"]["0.99"].get(
                "positive_gain_events_by_extreme_player_count_by_block"
            )
            if not isinstance(values, list) or len(values) != BLOCK_COUNT:
                raise ValueError("A7 support receipt lacks five blocks")
            for block, histogram in enumerate(values):
                if not isinstance(histogram, list) or len(histogram) != 10 or any(
                    type(value) is not int or value < 0 for value in histogram
                ):
                    raise ValueError("A7 support histogram differs")
                by_block[block] += sum(histogram[3:])
        cells[arm] = by_block
    conditions = {
        "control_r3_events_at_least_100": sum(cells["control"]) >= (
            R3_SUPPORT_MIN_EVENTS
        ),
        "treatment_r3_events_at_least_100": sum(cells["treatment"]) >= (
            R3_SUPPORT_MIN_EVENTS
        ),
        "control_r3_supported_in_every_block": all(
            value > 0 for value in cells["control"]
        ),
        "treatment_r3_supported_in_every_block": all(
            value > 0 for value in cells["treatment"]
        ),
    }
    return {
        "version": "a7-r3-support-census-v1",
        "uses_realized_outcomes": False,
        "slates": 54,
        "definition": "positive-ladder-gain-events-with-at-least-3-strict-q99-exceedances",
        "minimum_aggregate_events_per_arm": R3_SUPPORT_MIN_EVENTS,
        "r3_positive_gain_events_by_block": cells,
        "conditions": conditions,
        "passes": all(conditions.values()),
    }


def score_ordered_book(
    ordered_identities: Sequence[Sequence[object]],
    actual_by_identity: Mapping[tuple[str, ...], float],
) -> dict[str, Any]:
    identities = tuple(_identity(value) for value in ordered_identities)
    if len(identities) != ENTRY_COUNT or len(set(identities)) != ENTRY_COUNT:
        raise ValueError("A7 realized book is not exact-80")
    scores = []
    for identity in identities:
        if identity not in actual_by_identity:
            raise ValueError("A7 selected roster lacks a realized score")
        value = float(actual_by_identity[identity])
        if not np.isfinite(value):
            raise ValueError("A7 selected roster score is non-finite")
        scores.append(value)
    return {
        "identities": [list(value) for value in identities],
        "scores": scores,
        "prefix_maxima": {
            str(count): float(max(scores[:count])) for count in PREFIX_COUNTS
        },
    }


def _signed_rank_positive(differences: np.ndarray) -> bool:
    nonzero = differences[differences != 0.0]
    if len(nonzero) == 0:
        return False
    magnitudes = np.abs(nonzero)
    order = np.argsort(magnitudes, kind="mergesort")
    ranks = np.empty(len(nonzero), dtype=float)
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
    return float(ranks[nonzero > 0].sum()) > float(ranks.sum()) / 2.0


def _robustness(keys: Sequence[tuple[int, int]], differences: np.ndarray) -> dict[str, Any]:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    seasons = np.asarray([season for season, _ in keys], dtype=int)
    samples = np.empty(BOOTSTRAP_RESAMPLES, dtype=float)
    season_values = sorted(set(seasons.tolist()))
    for replicate in range(BOOTSTRAP_RESAMPLES):
        indices = np.concatenate([
            rng.choice(np.flatnonzero(seasons == season), size=int(
                np.count_nonzero(seasons == season)
            ), replace=True)
            for season in season_values
        ])
        samples[replicate] = float(differences[indices].mean())
    leave_one_slate = np.asarray([
        np.delete(differences, index).mean() for index in range(len(differences))
    ])
    by_season = {
        str(season): float(differences[seasons == season].mean())
        for season in season_values
    }
    leave_one_season = {
        str(season): float(differences[seasons != season].mean())
        for season in season_values
    }
    return {
        "bootstrap": {
            "design": "season-stratified-within-season-resampling",
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
            "mean_interval_95": [
                float(np.quantile(samples, 0.025, method="linear")),
                float(np.quantile(samples, 0.975, method="linear")),
            ],
        },
        "mean_delta_by_season": by_season,
        "leave_one_slate_mean_delta": [
            {
                "season": int(season),
                "week": int(week),
                "mean_delta": float(leave_one_slate[index]),
            }
            for index, (season, week) in enumerate(keys)
        ],
        "leave_one_slate_mean_delta_min": float(leave_one_slate.min()),
        "leave_one_slate_mean_delta_max": float(leave_one_slate.max()),
        "leave_one_season_mean_delta": leave_one_season,
    }


def _threshold_counts(values: np.ndarray) -> dict[str, int]:
    return {
        str(threshold): int(np.count_nonzero(values >= threshold))
        for threshold in REPORT_THRESHOLDS
    }


def validate_control_baseline(
    rows: Sequence[Mapping[str, Any]],
    *,
    baseline_mean: float = 176.06,
    baseline_counts: Mapping[str, int] | None = None,
    baseline_vector: Mapping[tuple[int, int], float] | None = None,
) -> dict[str, Any]:
    """Validate the registered control before any treatment is summarized."""
    if len(rows) != 54:
        raise ValueError("A7 control baseline population must contain 54 slates")
    ordered = sorted(rows, key=lambda row: (int(row["season"]), int(row["week"])))
    keys = [(int(row["season"]), int(row["week"])) for row in ordered]
    expected = [(season, week) for season in (2023, 2024, 2025)
                for week in range(1, 19)]
    if keys != expected:
        raise ValueError("A7 control baseline slate population differs")
    control = np.asarray([
        float(row["control"]["realized"]["prefix_maxima"][str(ENTRY_COUNT)])
        for row in ordered
    ])
    if not np.isfinite(control).all():
        raise ValueError("A7 control baseline contains a non-finite maximum")
    counts = _threshold_counts(control)
    expected_counts = dict(baseline_counts or {
        "187": 17, "194": 8, "200": 7, "210": 6,
        "220": 3, "230": 1, "240": 0,
    })
    mean_value = float(control.mean())
    if baseline_vector is not None:
        if set(baseline_vector) != set(keys) or any(
            control[index] != float(baseline_vector[key])
            for index, key in enumerate(keys)
        ):
            raise ValueError("A7 control weekly baseline vector differs")
    if round(mean_value, 2) != round(float(baseline_mean), 2) or counts != (
        expected_counts
    ):
        raise ValueError("A7 control does not reproduce the registered money book")
    return {
        "slates": 54,
        "mean": mean_value,
        "threshold_counts": counts,
        "weekly_vector_reproduced": baseline_vector is not None,
        "reproduced": True,
    }


def aggregate_outcomes(
    rows: Sequence[Mapping[str, Any]],
    *,
    scorefree: Mapping[str, Any],
    baseline_mean: float = 176.06,
    baseline_counts: Mapping[str, int] | None = None,
    baseline_vector: Mapping[tuple[int, int], float] | None = None,
) -> dict[str, Any]:
    """Aggregate realized results and apply the frozen disposition law."""
    if baseline_vector is None:
        raise ValueError("A7 weekly baseline vector is required")
    if scorefree.get("passes") is not True or scorefree.get(
        "uses_realized_outcomes"
    ) is not False:
        raise ValueError("A7 outcome aggregation lacks a passed score-free gate")
    if len(rows) != 54:
        raise ValueError("A7 outcome population must contain 54 slates")
    ordered = sorted(rows, key=lambda row: (int(row["season"]), int(row["week"])))
    keys = [(int(row["season"]), int(row["week"])) for row in ordered]
    expected = [(season, week) for season in (2023, 2024, 2025)
                for week in range(1, 19)]
    if keys != expected:
        raise ValueError("A7 outcome slate population differs")
    # This must precede the first treatment read below. The historical arm is
    # invalid if the registered control cannot be reproduced.
    baseline = validate_control_baseline(
        ordered, baseline_mean=baseline_mean, baseline_counts=baseline_counts,
        baseline_vector=baseline_vector,
    )
    cuts: dict[str, Any] = {}
    for count in PREFIX_COUNTS:
        control = np.asarray([
            float(row["control"]["realized"]["prefix_maxima"][str(count)])
            for row in ordered
        ])
        treatment = np.asarray([
            float(row["treatment"]["realized"]["prefix_maxima"][str(count)])
            for row in ordered
        ])
        if not (np.isfinite(control).all() and np.isfinite(treatment).all()):
            raise ValueError("A7 prefix maxima are non-finite")
        paired = paired_weekly_max_report(
            control, treatment, thresholds=REPORT_THRESHOLDS,
            slate_keys=[f"{season}-{week}" for season, week in keys],
        )
        differences = treatment - control
        cuts[str(count)] = {
            "gating": count == ENTRY_COUNT,
            "control_mean": float(control.mean()),
            "treatment_mean": float(treatment.mean()),
            "control_threshold_counts": _threshold_counts(control),
            "treatment_threshold_counts": _threshold_counts(treatment),
            "paired": paired,
            "signed_rank_direction_positive": _signed_rank_positive(differences),
            "robustness": _robustness(keys, differences),
        }

    primary = cuts[str(ENTRY_COUNT)]
    pool = np.asarray([float(row["pool_c"]) for row in ordered])
    if not np.isfinite(pool).all():
        raise ValueError("A7 pool ceiling is non-finite")
    control_primary = np.asarray([
        float(row["control"]["realized"]["prefix_maxima"][str(ENTRY_COUNT)])
        for row in ordered
    ])
    treatment_primary = np.asarray([
        float(row["treatment"]["realized"]["prefix_maxima"][str(ENTRY_COUNT)])
        for row in ordered
    ])
    if np.any(pool < control_primary) or np.any(pool < treatment_primary):
        raise ValueError("A7 selected book exceeds the shared candidate pool ceiling")
    control_gap = pool - control_primary
    treatment_gap = pool - treatment_primary
    weekly_conversion = [
        {
            "season": int(season),
            "week": int(week),
            "pool_c": float(pool[index]),
            "control_s80": float(control_primary[index]),
            "treatment_s80": float(treatment_primary[index]),
            "control_c_minus_s": float(control_gap[index]),
            "treatment_c_minus_s": float(treatment_gap[index]),
            "treatment_minus_control_c_minus_s": float(
                treatment_gap[index] - control_gap[index]
            ),
        }
        for index, (season, week) in enumerate(keys)
    ]
    conversion = {
        "weekly": weekly_conversion,
        "pool_c_mean": float(pool.mean()),
        "pool_c_threshold_counts": _threshold_counts(pool),
        "control_s80_mean": float(control_primary.mean()),
        "treatment_s80_mean": float(treatment_primary.mean()),
        "treatment_minus_control_s80_mean": float(
            (treatment_primary - control_primary).mean()
        ),
        "control_c_minus_s_mean": float(control_gap.mean()),
        "treatment_c_minus_s_mean": float(treatment_gap.mean()),
        "treatment_minus_control_c_minus_s_mean": float(
            (treatment_gap - control_gap).mean()
        ),
        "control_minus_treatment_c_minus_s_mean": float(
            (control_gap - treatment_gap).mean()
        ),
    }
    inference = primary["paired"]["inference"]
    control_counts = primary["control_threshold_counts"]
    treatment_counts = primary["treatment_threshold_counts"]
    conditions = {
        "mean_delta_positive": primary["paired"]["mean_diff"] > 0,
        "paired_mean_p_le_0_05": inference["p_mean_two_sided"] <= 0.05,
        "signed_rank_direction_positive": primary[
            "signed_rank_direction_positive"
        ],
        "paired_signed_rank_p_le_0_05": (
            inference["p_signed_rank_two_sided"] <= 0.05
        ),
        "194_noninferior_by_one_slate": (
            treatment_counts["194"] - control_counts["194"]
            >= SHOULDER_NONINFERIORITY_SLATES
        ),
        "200_noninferior_by_one_slate": (
            treatment_counts["200"] - control_counts["200"]
            >= SHOULDER_NONINFERIORITY_SLATES
        ),
    }
    if all(conditions.values()):
        disposition = "historical-positive-phase-s"
    elif primary["paired"]["mean_diff"] < 0 or not (
        conditions["194_noninferior_by_one_slate"]
        and conditions["200_noninferior_by_one_slate"]
    ):
        disposition = "rejected-phase-s-dose"
    else:
        disposition = "historical-null-or-inconclusive-phase-s"
    return {
        "protocol_id": PROTOCOL_ID,
        "uses_realized_outcomes": True,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": (
            disposition == "historical-positive-phase-s"
        ),
        "prospective_shadow_licensed": False,
        "baseline": baseline,
        "baseline_reproduced": True,
        "pool_to_book_conversion": conversion,
        "conditions": conditions,
        "disposition": disposition,
        "cuts": cuts,
    }


def candidate_source_counts(
    selected: Sequence[int], tags: Sequence[Sequence[str]],
) -> dict[str, int]:
    indices = [int(value) for value in selected]
    if any(index < 0 for index in indices) or len(tags) <= max(
        indices, default=-1,
    ):
        raise ValueError("A7 candidate tags are misaligned")
    counts: Counter[str] = Counter()
    for index in indices:
        sources = [tag for tag in tags[index]
                   if str(tag).startswith("candidate_seed:")]
        if len(sources) != 1:
            raise ValueError("A7 selected candidate source tag differs")
        counts[str(sources[0]).split(":", 1)[1]] += 1
    return dict(sorted(counts.items()))


__all__ = [
    "BLOCK_COUNT", "CONTROL_ENV", "ENTRY_COUNT", "LADDER", "LADDER_SPEC",
    "PREFIX_COUNTS", "PROTOCOL_ID", "REALISM_R3_MARGIN",
    "REALISM_R3_MARGIN_DENOMINATOR", "REALISM_R3_MARGIN_NUMERATOR",
    "REPORT_THRESHOLDS", "TREATMENT_ENV", "WORLDS_PER_BLOCK",
    "aggregate_outcomes", "aggregate_scorefree", "candidate_source_counts",
    "score_ordered_book", "scorefree_book_receipt", "select_books",
    "selected_identities", "support_census", "validate_control_baseline",
]
