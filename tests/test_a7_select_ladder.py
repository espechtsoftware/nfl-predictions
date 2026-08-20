from __future__ import annotations

from itertools import combinations

import numpy as np
import pytest

from nfl_dfs.optimizer.lineup import _parse_ladder
from nfl_dfs.research import a7_select_ladder as a7


def _identity(prefix: str) -> list[str]:
    return [f"{prefix}-p{index}" for index in range(9)]


def _fake_scorefree_rows(*, treatment_r3: int = 11) -> list[dict]:
    rows = []
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            control_ids = [_identity(f"c-{season}-{week}-{index}") for index in range(80)]
            treatment_ids = [_identity(f"t-{season}-{week}-{index}") for index in range(80)]
            control_hist = [90, 0, 0, 10, 0, 0, 0, 0, 0, 0]
            treatment_hist = [110 - treatment_r3, 0, 0, treatment_r3,
                              0, 0, 0, 0, 0, 0]
            treatment_r3_blocks = [
                treatment_r3 // 5 + int(index < treatment_r3 % 5)
                for index in range(5)
            ]
            control_blocks = [[18, 0, 0, 2, 0, 0, 0, 0, 0, 0] for _ in range(5)]
            treatment_blocks = [
                [22 - value, 0, 0, value, 0, 0, 0, 0, 0, 0]
                for value in treatment_r3_blocks
            ]
            rows.append({
                "season": season,
                "week": week,
                "control": {
                    "identities": control_ids,
                    "scorefree": {
                        "total_ladder_utility": 100,
                        "ladder_utility_by_block": [20] * 5,
                        "realism": {
                            quantile: {
                                "utility_by_extreme_player_count": control_hist,
                                "utility_by_extreme_player_count_by_block": control_blocks,
                                "positive_gain_events_by_extreme_player_count_by_block": control_blocks,
                            }
                            for quantile in ("0.99", "0.995")
                        },
                    },
                },
                "treatment": {
                    "identities": treatment_ids,
                    "scorefree": {
                        "total_ladder_utility": 110,
                        "ladder_utility_by_block": [22] * 5,
                        "realism": {
                            quantile: {
                                "utility_by_extreme_player_count": treatment_hist,
                                "utility_by_extreme_player_count_by_block": treatment_blocks,
                                "positive_gain_events_by_extreme_player_count_by_block": treatment_blocks,
                            }
                            for quantile in ("0.99", "0.995")
                        },
                    },
                },
            })
    return rows


def _baseline_values() -> np.ndarray:
    high = [235.0, 225.0, 225.0, 215.0, 215.0, 215.0,
            205.0, 195.0, *([190.0] * 9)]
    low = (176.06 * 54 - sum(high)) / 37
    return np.asarray([*high, *([low] * 37)], dtype=float)


def _realized_rows(control: np.ndarray, treatment: np.ndarray) -> list[dict]:
    rows = []
    cursor = 0
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            c = float(control[cursor])
            t = float(treatment[cursor])
            rows.append({
                "season": season,
                "week": week,
                "pool_c": max(c, t) + 10.0,
                "control": {"realized": {"prefix_maxima": {
                    "4": c, "14": c, "80": c,
                }}},
                "treatment": {"realized": {"prefix_maxima": {
                    "4": t, "14": t, "80": t,
                }}},
            })
            cursor += 1
    return rows


def _baseline_vector(control: np.ndarray) -> dict[tuple[int, int], float]:
    keys = [
        (season, week) for season in (2023, 2024, 2025)
        for week in range(1, 19)
    ]
    return dict(zip(keys, map(float, control), strict=True))


def test_frozen_utility_is_clipped_linear_through_210_only():
    assert a7.LADDER_SPEC == "170:10,180:10,187:7,194:7,200:6,210:10"
    assert a7.LADDER == {
        170.0: 10, 180.0: 10, 187.0: 7,
        194.0: 7, 200.0: 6, 210.0: 10,
    }
    assert sum(a7.LADDER.values()) == 50
    assert max(a7.LADDER) == 210
    assert "mean" not in a7.LADDER_SPEC
    assert a7.CONTROL_ENV == {"SELECT_LSE": "0", "SELECT_LADDER": ""}
    assert a7.TREATMENT_ENV["SELECT_LADDER"] == a7.LADDER_SPEC
    parsed_ladder, parsed_mean = _parse_ladder(a7.LADDER_SPEC)
    assert parsed_ladder == a7.LADDER
    assert parsed_mean == 0.0


def test_select_books_is_exact_prefix_invariant_and_nonvacuous():
    rng = np.random.default_rng(20_260_820)
    totals = rng.normal(175, 24, size=(120, 50_000)).astype(np.float32)
    books = a7.select_books(totals)
    assert set(books) == {"control", "treatment"}
    assert all(len(value) == len(set(value)) == 80 for value in books.values())
    assert books["control"] != books["treatment"]


def test_select_books_rejects_nonfinite_and_wrong_world_width():
    with pytest.raises(ValueError, match="matrix differs"):
        a7.select_books(np.ones((80, 1), dtype=np.float32))
    totals = np.ones((80, 50_000), dtype=np.float32)
    totals[0, 0] = np.nan
    with pytest.raises(ValueError, match="matrix differs"):
        a7.select_books(totals)


def test_scorefree_receipt_conserves_utility_and_reports_extremes():
    rng = np.random.default_rng(4)
    player_ids = [f"p{index}" for index in range(18)]
    rosters = [list(value) for value in list(combinations(player_ids, 9))[:80]]
    draws = rng.normal(20, 7, size=(18, 50_000)).astype(np.float32)
    by_id = {value: index for index, value in enumerate(player_ids)}
    totals = np.stack([
        draws[[by_id[value] for value in roster]].sum(axis=0)
        for roster in rosters
    ]).astype(np.float32)
    receipt = a7.scorefree_book_receipt(
        candidate_totals=totals,
        candidate_identities=rosters,
        selected=list(range(80)),
        player_ids=player_ids,
        player_draws=draws,
    )
    assert receipt["total_ladder_utility"] == sum(
        receipt["ladder_utility_by_block"]
    )
    assert len(receipt["trace"]) == 80
    for quantile in ("0.99", "0.995"):
        row = receipt["realism"][quantile]
        assert sum(row["utility_by_extreme_player_count"]) == receipt[
            "total_ladder_utility"
        ]
        assert 0 <= row["r4"] <= row["r3"] <= row["r2"] <= 1


def test_strict_quantile_excludes_constant_and_tied_player_draws():
    constants = [f"constant-{index}" for index in range(7)]
    variable = [f"variable-{index}" for index in range(18)]
    player_ids = [*constants, *variable]
    rosters = [
        [*constants, *pair] for pair in list(combinations(variable, 2))[:80]
    ]
    draws = np.full((len(player_ids), 50_000), 20.0, dtype=np.float32)
    # Tied 2% upper mass makes q99 exactly 25. Strict > must classify neither
    # the tied values nor any zero-variance constant row as extreme.
    for index in range(len(constants), len(player_ids)):
        draws[index, :1_000] = 25.0
        draws[index, 1_000:] = 19.0
    by_id = {value: index for index, value in enumerate(player_ids)}
    totals = np.stack([
        draws[sorted(by_id[value] for value in roster)].sum(
            axis=0, dtype=np.float32,
        )
        for roster in rosters
    ]).astype(np.float32)
    receipt = a7.scorefree_book_receipt(
        candidate_totals=totals,
        candidate_identities=rosters,
        selected=list(range(80)),
        player_ids=player_ids,
        player_draws=draws,
    )
    for quantile in ("0.99", "0.995"):
        histogram = receipt["realism"][quantile][
            "utility_by_extreme_player_count"
        ]
        assert histogram[0] == receipt["total_ladder_utility"]
        assert sum(histogram[1:]) == 0


def test_scorefree_aggregate_passes_and_r3_margin_fails_closed():
    passed = a7.aggregate_scorefree(_fake_scorefree_rows())
    assert passed["passes"] is True
    assert passed["changed_slates"] == 54
    assert passed["improved_world_blocks"] == 5
    assert passed["realism_r3_delta"] == pytest.approx(0.0)

    failed = a7.aggregate_scorefree(_fake_scorefree_rows(treatment_r3=22))
    assert failed["passes"] is False
    assert failed["conditions"]["realism_r3_noninferior"] is False


def test_scorefree_nonvacuity_uses_membership_not_order_and_support_is_exact():
    rows = _fake_scorefree_rows()
    for row in rows:
        row["treatment"]["identities"] = list(reversed(
            row["control"]["identities"],
        ))
    result = a7.aggregate_scorefree(rows)
    assert result["conditions"]["treatment_nonvacuous"] is False
    assert result["passes"] is False

    unsupported = _fake_scorefree_rows()
    for row in unsupported:
        for arm in ("control", "treatment"):
            for quantile in ("0.99", "0.995"):
                row[arm]["scorefree"]["realism"][quantile][
                    "positive_gain_events_by_extreme_player_count_by_block"
                ] = [[20, 0, 0, 0, 0, 0, 0, 0, 0, 0] for _ in range(5)]
    support = a7.support_census(unsupported)
    assert support["passes"] is False
    aggregated = a7.aggregate_scorefree(unsupported)
    assert aggregated["conditions"]["realism_r3_supported"] is False


def test_support_floor_is_inclusive_and_requires_every_block():
    rows = _fake_scorefree_rows()
    for row in rows:
        for arm in ("control", "treatment"):
            row[arm]["scorefree"]["realism"]["0.99"][
                "positive_gain_events_by_extreme_player_count_by_block"
            ] = [[0] * 10 for _ in range(5)]
    for arm in ("control", "treatment"):
        rows[0][arm]["scorefree"]["realism"]["0.99"][
            "positive_gain_events_by_extreme_player_count_by_block"
        ] = [[0, 0, 0, 20, 0, 0, 0, 0, 0, 0] for _ in range(5)]
    assert a7.support_census(rows)["passes"] is True
    rows[0]["treatment"]["scorefree"]["realism"]["0.99"][
        "positive_gain_events_by_extreme_player_count_by_block"
    ][0][3] = 19
    assert a7.support_census(rows)["passes"] is False
    rows[0]["treatment"]["scorefree"]["realism"]["0.99"][
        "positive_gain_events_by_extreme_player_count_by_block"
    ][0][3] = 20
    rows[0]["treatment"]["scorefree"]["realism"]["0.99"][
        "positive_gain_events_by_extreme_player_count_by_block"
    ][4][3] = 0
    rows[1]["treatment"]["scorefree"]["realism"]["0.99"][
        "positive_gain_events_by_extreme_player_count_by_block"
    ][0][3] = 20
    assert a7.support_census(rows)["passes"] is False


def test_r3_one_percentage_point_boundary_is_exact_and_inclusive():
    rows = _fake_scorefree_rows()
    for row in rows:
        for quantile in ("0.99", "0.995"):
            treatment = row["treatment"]["scorefree"]
            treatment["total_ladder_utility"] = 100
            treatment["ladder_utility_by_block"] = [20] * 5
            realism = treatment["realism"][quantile]
            realism["utility_by_extreme_player_count"] = [
                89, 0, 0, 11, 0, 0, 0, 0, 0, 0,
            ]
            block_r3 = [3, 2, 2, 2, 2]
            blocks = [
                [20 - value, 0, 0, value, 0, 0, 0, 0, 0, 0]
                for value in block_r3
            ]
            realism["utility_by_extreme_player_count_by_block"] = blocks
            realism[
                "positive_gain_events_by_extreme_player_count_by_block"
            ] = [list(value) for value in blocks]
    boundary = a7.aggregate_scorefree(rows)
    assert boundary["realism_r3_exact_comparison"]["noninferior"] is True
    assert boundary["conditions"]["realism_r3_noninferior"] is True
    assert boundary["realism_r3_delta"] == pytest.approx(0.01)

    first = rows[0]["treatment"]["scorefree"]["realism"]["0.99"]
    first["utility_by_extreme_player_count"][0] -= 1
    first["utility_by_extreme_player_count"][3] += 1
    first["utility_by_extreme_player_count_by_block"][0][0] -= 1
    first["utility_by_extreme_player_count_by_block"][0][3] += 1
    above = a7.aggregate_scorefree(rows)
    assert above["realism_r3_exact_comparison"]["noninferior"] is False
    assert above["conditions"]["realism_r3_noninferior"] is False


def test_score_ordered_book_uses_prefixes_not_hindsight_subsets():
    identities = [_identity(f"r{index}") for index in range(80)]
    actuals = {tuple(sorted(identity)): float(index) for index, identity in enumerate(
        identities
    )}
    result = a7.score_ordered_book(identities, actuals)
    assert result["prefix_maxima"] == {"4": 3.0, "14": 13.0, "80": 79.0}
    with pytest.raises(ValueError, match="lacks a realized score"):
        a7.score_ordered_book(identities, {})


def test_outcome_aggregate_reproduces_baseline_and_licenses_only_transfer():
    control = _baseline_values()
    treatment = control + 5.0
    scorefree = a7.aggregate_scorefree(_fake_scorefree_rows())
    result = a7.aggregate_outcomes(
        _realized_rows(control, treatment), scorefree=scorefree,
        baseline_vector=_baseline_vector(control),
    )
    assert result["baseline_reproduced"] is True
    assert result["disposition"] == "historical-positive-phase-s"
    assert result["production_law_scorefree_transfer_licensed"] is True
    assert result["prospective_shadow_licensed"] is False
    assert result["production_change_licensed"] is False
    assert result["cuts"]["80"]["gating"] is True
    assert result["cuts"]["4"]["gating"] is False
    conversion = result["pool_to_book_conversion"]
    assert conversion["treatment_minus_control_c_minus_s_mean"] == -5.0
    assert conversion["control_minus_treatment_c_minus_s_mean"] == 5.0
    assert all(
        row["treatment_minus_control_c_minus_s"] == -5.0
        for row in conversion["weekly"]
    )
    assert all(result["conditions"].values())
    robustness = result["cuts"]["80"]["robustness"]
    assert len(robustness["leave_one_slate_mean_delta"]) == 54
    assert robustness["leave_one_slate_mean_delta"][0] == {
        "season": 2023, "week": 1, "mean_delta": 5.0,
    }
    assert set(robustness["leave_one_season_mean_delta"]) == {
        "2023", "2024", "2025",
    }


def test_outcome_aggregate_rejects_baseline_drift_and_secondary_cannot_gate():
    control = _baseline_values()
    scorefree = a7.aggregate_scorefree(_fake_scorefree_rows())
    rows = _realized_rows(control, control + 5.0)
    # Poison only a non-gating N=4 treatment result. Exact-80 disposition stays.
    for row in rows:
        row["treatment"]["realized"]["prefix_maxima"]["4"] = (
            row["control"]["realized"]["prefix_maxima"]["4"] - 20
        )
    result = a7.aggregate_outcomes(
        rows, scorefree=scorefree, baseline_vector=_baseline_vector(control),
    )
    assert result["disposition"] == "historical-positive-phase-s"
    assert result["cuts"]["4"]["paired"]["mean_diff"] == -20

    poisoned = _realized_rows(control.copy(), control + 5.0)
    poisoned[0]["control"]["realized"]["prefix_maxima"]["80"] += 1
    with pytest.raises(ValueError, match="weekly baseline vector"):
        a7.aggregate_outcomes(
            poisoned, scorefree=scorefree,
            baseline_vector=_baseline_vector(control),
        )


def test_outcome_zero_mean_is_null_and_weekly_vector_is_mandatory():
    control = _baseline_values()
    scorefree = a7.aggregate_scorefree(_fake_scorefree_rows())
    rows = _realized_rows(control, control.copy())
    result = a7.aggregate_outcomes(
        rows, scorefree=scorefree, baseline_vector=_baseline_vector(control),
    )
    assert result["disposition"] == "historical-null-or-inconclusive-phase-s"
    assert result["baseline"]["weekly_vector_reproduced"] is True
    assert result["pool_to_book_conversion"]["pool_c_mean"] > result[
        "cuts"
    ]["80"]["control_mean"]
    conversion = result["pool_to_book_conversion"]
    assert len(conversion["weekly"]) == 54
    assert conversion["weekly"][0] == {
        "season": 2023,
        "week": 1,
        "pool_c": float(rows[0]["pool_c"]),
        "control_s80": float(control[0]),
        "treatment_s80": float(control[0]),
        "control_c_minus_s": 10.0,
        "treatment_c_minus_s": 10.0,
        "treatment_minus_control_c_minus_s": 0.0,
    }
    assert conversion["treatment_minus_control_c_minus_s_mean"] == 0.0
    assert conversion["control_minus_treatment_c_minus_s_mean"] == 0.0
    with pytest.raises(ValueError, match="weekly baseline vector"):
        a7.aggregate_outcomes(
            rows, scorefree=scorefree,
            baseline_vector={**_baseline_vector(control), (2023, 1): 999.0},
        )


def test_candidate_source_counts_requires_one_registered_seed_tag():
    tags = [["boom", f"candidate_seed:R{index % 5}"] for index in range(80)]
    counts = a7.candidate_source_counts(list(range(80)), tags)
    assert counts == {f"R{index}": 16 for index in range(5)}
    tags[0] = ["boom"]
    with pytest.raises(ValueError, match="source tag differs"):
        a7.candidate_source_counts(list(range(80)), tags)
