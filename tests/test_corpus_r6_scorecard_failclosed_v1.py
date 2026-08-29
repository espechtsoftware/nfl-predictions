from copy import deepcopy
from pathlib import Path

import pytest

from nfl_dfs.research import corpus_r6_score_sprint_scorecard_v1 as s


def _write(tmp_path: Path, name: str, value: object) -> Path:
    path = tmp_path / name
    path.write_bytes(s.canonical_json_bytes_v1(value))
    return path


def _identity(label: str) -> dict[str, object]:
    return {
        "uri": f"gs://synthetic/{label}.json",
        "generation": "1",
        "sha256": s.canonical_sha256_v1({"label": label}),
        "bytes": 1,
    }


def _coordinates(adapter_id: str) -> list[dict[str, object]]:
    coordinates: list[dict[str, object]] = []
    if adapter_id == "hard230-selected-book-bridge-v1":
        for population_role, population_id in s.HARD_POPULATIONS:
            for selector_family, selector_id in s.HARD_SELECTORS:
                for entry_budget in (80, 100, 150):
                    coordinates.append({
                        "adapter_id": adapter_id,
                        "metric_kind": "selected-book",
                        "population_role": population_role,
                        "population_id": population_id,
                        "selector_family": selector_family,
                        "selector_id": selector_id,
                        "entry_budget": entry_budget,
                    })
        return coordinates

    if adapter_id == "population-crossed-v1":
        outer_name = "profile_id"
        outer_values = s.POPULATION_PROFILES
        families = (
            ("grouped-native-rank80", (4, 14, 80)),
            ("exact-rank150-continuation", (80, 100, 150)),
            ("effective-independent-tail-shots", (80, 100, 150)),
        )
    elif adapter_id == "l2b-current-union-selectors-v1":
        outer_name = "fraction_id"
        outer_values = s.L2B_FRACTIONS
        families = (
            ("grouped-native-rank80", (4, 14, 80)),
            ("exact-rank150-continuation", (80, 100, 150)),
            ("effective-independent-tail-shots", (80, 100, 150)),
            ("tail-ladder-diversity-challengers", (80, 100, 150)),
        )
    else:  # pragma: no cover - fixture misuse
        raise AssertionError(adapter_id)

    for outer_value in outer_values:
        for heldout_block in s.WORLD_BLOCKS:
            for selector_family, budgets in families:
                for selector_ordinal, selector_id in enumerate(
                    s.GENERIC_SELECTOR_IDS[selector_family]
                ):
                    for entry_budget in budgets:
                        coordinates.append({
                            "adapter_id": adapter_id,
                            "metric_kind": "selected-book",
                            outer_name: outer_value,
                            "heldout_block": heldout_block,
                            "selector_family": selector_family,
                            "selector_ordinal": selector_ordinal,
                            "selector_id": selector_id,
                            "entry_budget": entry_budget,
                        })
    return coordinates


def _score_vectors() -> tuple[list[int], list[int]]:
    # The novel-roster artifacts do not store 194 in their threshold registry.
    # This vector makes the derived 194 count distinguishable from every
    # stored 200/210/220/230 count.
    selected = [
        231_000_000,
        221_000_000,
        201_000_000,
        195_000_000,
        *([193_000_000] * 50),
    ]
    return selected, [value + 10_000_000 for value in selected]


def _cell(coordinate: dict[str, object]) -> dict[str, object]:
    selected, ceilings = _score_vectors()
    entry_budget = int(coordinate["entry_budget"])
    slate_rows = []
    for ordinal, slate_id in enumerate(s.EXPECTED_SLATE_IDS):
        weekly = selected[ordinal]
        ceiling = ceilings[ordinal]
        slate_rows.append({
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "entry_budget": entry_budget,
            "population_lineup_count": max(200, entry_budget),
            "selected_lineup_count": entry_budget,
            "population_ceiling_micro": ceiling,
            "selected_weekly_maximum_micro": weekly,
            "weekly_maximum_micro": weekly,
            "population_ceiling_converted": False,
            "population_ceiling_regret_micro": ceiling - weekly,
        })
    thresholds = []
    for threshold in s.STORED_NOVEL_THRESHOLDS_DK:
        threshold_micro = threshold * s.MICRO_DK_PER_POINT
        selected_count = sum(value >= threshold_micro for value in selected)
        population_count = sum(value >= threshold_micro for value in ceilings)
        thresholds.append({
            "threshold_dk": threshold,
            "threshold_micro": threshold_micro,
            "operator": ">=",
            "population_lineup_hit_count": population_count,
            "population_slates_with_at_least_one_hit": population_count,
            "selected_lineup_hit_count": selected_count,
            "selected_slates_with_at_least_one_hit": selected_count,
        })
    body = {
        "schema_version": s.AGGREGATE_CELL_SCHEMA,
        "coordinate": coordinate,
        "coordinate_sha256": s.canonical_sha256_v1(coordinate),
        "source_slate_count": s.SOURCE_SLATE_COUNT,
        "slate_rows": slate_rows,
        "slate_rows_sha256": s.canonical_sha256_v1(slate_rows),
        "mean_weekly_maximum_micro": {
            "numerator": sum(selected),
            "denominator": s.SOURCE_SLATE_COUNT,
            "unit": "micro_dk",
        },
        "mean_population_ceiling_micro": {
            "numerator": sum(ceilings),
            "denominator": s.SOURCE_SLATE_COUNT,
            "unit": "micro_dk",
        },
        "thresholds": thresholds,
        "selection_conversion_available": True,
        "population_ceiling_conversion_count": 0,
        "population_ceiling_conversion_fraction": {
            "numerator": 0,
            "denominator": s.SOURCE_SLATE_COUNT,
            "unit": "slates",
        },
        "mean_population_ceiling_regret_micro": {
            "numerator": sum(
                ceiling - weekly
                for ceiling, weekly in zip(ceilings, selected, strict=True)
            ),
            "denominator": s.SOURCE_SLATE_COUNT,
            "unit": "micro_dk",
        },
        "complete": True,
    }
    return {**body, "aggregate_cell_sha256": s.canonical_sha256_v1(body)}


def _hard_grade(*, outcome_internal_sha256: str = "a" * 64) -> dict[str, object]:
    cells = [
        _cell(coordinate)
        for coordinate in _coordinates("hard230-selected-book-bridge-v1")
    ]
    slate_grades = [
        {"source_ordinal": ordinal, "slate_id": slate_id}
        for ordinal, slate_id in enumerate(s.EXPECTED_SLATE_IDS)
    ]
    body = {
        "schema_version": s.HARD230_GRADE_SCHEMA,
        "adapter_id": "hard230-selected-book-bridge-v1",
        "terminal_identity": _identity("terminal"),
        "terminal_sha256": "b" * 64,
        "outcome_snapshot_identity": _identity("outcome"),
        "outcome_snapshot_sha256": outcome_internal_sha256,
        "later_source_identity": _identity("later-source"),
        "source_slate_count": s.SOURCE_SLATE_COUNT,
        "slate_grades": slate_grades,
        "slate_grades_sha256": s.canonical_sha256_v1(slate_grades),
        "aggregate_cells": cells,
        "aggregate_cells_sha256": s.canonical_sha256_v1(cells),
        "all_score_free_predecessors_replayed_before_outcome_open": True,
        "outcome_source_and_slate_identity_bound": True,
        "complete": True,
    }
    return {**body, "grade_sha256": s.canonical_sha256_v1(body)}


def _l2b_grade() -> dict[str, object]:
    cells = [
        _cell(coordinate)
        for coordinate in _coordinates("l2b-current-union-selectors-v1")
    ]
    slate_grades = [
        {"source_ordinal": ordinal, "slate_id": slate_id}
        for ordinal, slate_id in enumerate(s.EXPECTED_SLATE_IDS)
    ]
    body = {
        "schema_version": s.NOVEL_GRADE_SCHEMA,
        "adapter_id": "l2b-current-union-selectors-v1",
        "terminal_root_identity": _identity("l2b-terminal"),
        "terminal_root_sha256": "d" * 64,
        "task_manifest_identity": _identity("l2b-manifest"),
        "task_manifest_sha256": "e" * 64,
        "outcome_snapshot_identity": _identity("outcome"),
        "outcome_snapshot_sha256": "a" * 64,
        "later_source_freeze_identity": _identity("later-source"),
        "score_unit": "micro_dk",
        "micro_dk_per_point": s.MICRO_DK_PER_POINT,
        "threshold_registry": [
            {
                "threshold_dk": threshold,
                "threshold_micro": threshold * s.MICRO_DK_PER_POINT,
                "operator": ">=",
            }
            for threshold in s.STORED_NOVEL_THRESHOLDS_DK
        ],
        "source_slate_count": s.SOURCE_SLATE_COUNT,
        "slate_grade_count": s.SOURCE_SLATE_COUNT,
        "slate_grades": slate_grades,
        "slate_grades_sha256": s.canonical_sha256_v1(slate_grades),
        "aggregate_cell_count": len(cells),
        "aggregate_cells": cells,
        "aggregate_cells_sha256": s.canonical_sha256_v1(cells),
        "roster_sum_operation_count": 1,
        "every_distinct_roster_scored_once_per_slate": True,
        "terminal_before_first_outcome_read": True,
        "uses_realized_outcomes": True,
        "historical_retune_licensed": False,
        "historical_retry_licensed": False,
        "decision_authority": False,
        "complete": True,
    }
    return {**body, "realized_grade_sha256": s.canonical_sha256_v1(body)}


def _performance_row(
    *, source: str, selector: str, mean_milli: int,
    counts: tuple[int, int, int, int]
) -> dict[str, object]:
    return {
        "source_label": source,
        "population_coordinate": {"population_id": f"{source}-population"},
        "selector_coordinate": {"selector_id": selector},
        "entry_budget": 80,
        "mean_weekly_maximum_micro": {
            "numerator": mean_milli * 1_000 * s.SOURCE_SLATE_COUNT,
            "denominator": s.SOURCE_SLATE_COUNT,
            "unit": "micro_dk",
        },
        "thresholds": [
            {
                "threshold_dk": threshold,
                "slates_with_at_least_one_hit": count,
                "slate_hit_rate": {
                    "numerator": count,
                    "denominator": s.SOURCE_SLATE_COUNT,
                    "unit": "slates",
                },
            }
            for threshold, count in zip(
                s.REQUESTED_THRESHOLDS_DK, counts, strict=True
            )
        ],
    }


@pytest.mark.parametrize(
    ("adapter_id", "expected_count"),
    (
        ("population-crossed-v1", 315),
        ("l2b-current-union-selectors-v1", 300),
        ("hard230-selected-book-bridge-v1", 24),
    ),
)
def test_complete_frozen_adapter_lattice_is_accepted(
    adapter_id: str, expected_count: int
) -> None:
    cells = [{"coordinate": row} for row in _coordinates(adapter_id)]
    assert len(cells) == expected_count
    s._validate_complete_lattice(
        adapter_id=adapter_id, cells=cells, label="fixture"
    )


@pytest.mark.parametrize(
    "adapter_id",
    (
        "population-crossed-v1",
        "l2b-current-union-selectors-v1",
        "hard230-selected-book-bridge-v1",
    ),
)
def test_each_adapter_rejects_missing_and_foreign_cells(adapter_id: str) -> None:
    coordinates = _coordinates(adapter_id)
    with pytest.raises(
        s.CorpusR6ScoreSprintScorecardV1Error,
        match="census differs|incomplete or foreign",
    ):
        s._validate_complete_lattice(
            adapter_id=adapter_id,
            cells=[{"coordinate": row} for row in coordinates[:-1]],
            label="missing",
        )

    foreign = deepcopy(coordinates)
    foreign[-1] = {**foreign[-1], "entry_budget": 999}
    with pytest.raises(
        s.CorpusR6ScoreSprintScorecardV1Error,
        match="incomplete or foreign",
    ):
        s._validate_complete_lattice(
            adapter_id=adapter_id,
            cells=[{"coordinate": row} for row in foreign],
            label="foreign",
        )


def test_exact_54_slate_194_derivation_and_stored_threshold_parity() -> None:
    cell = _cell(_coordinates("hard230-selected-book-bridge-v1")[0])
    performance, _ceiling = s._validate_cell(
        cell, adapter_id="hard230-selected-book-bridge-v1"
    )
    assert performance is not None
    assert {
        row["threshold_dk"]: row["slates_with_at_least_one_hit"]
        for row in performance["thresholds"]
    } == {194: 4, 200: 3, 220: 2, 230: 1}

    invalid = deepcopy(cell)
    invalid["thresholds"][0]["selected_slates_with_at_least_one_hit"] += 1
    invalid["aggregate_cell_sha256"] = s.canonical_sha256_v1({
        key: value
        for key, value in invalid.items()
        if key != "aggregate_cell_sha256"
    })
    with pytest.raises(
        s.CorpusR6ScoreSprintScorecardV1Error,
        match="selected threshold summary differs",
    ):
        s._validate_cell(invalid, adapter_id="hard230-selected-book-bridge-v1")


def test_l2b_population_ceiling_collapses_across_selector_fractions(
    tmp_path: Path,
) -> None:
    retained: dict[bytes, dict[str, object]] = {}
    for fraction_id in s.L2B_FRACTIONS:
        for heldout_block in s.WORLD_BLOCKS:
            source_coordinate = {
                "adapter_id": "l2b-current-union-selectors-v1",
                "metric_kind": "selected-book",
                "fraction_id": fraction_id,
                "heldout_block": heldout_block,
                "selector_family": "grouped-native-rank80",
                "selector_ordinal": 0,
                "selector_id": s.GENERIC_SELECTOR_IDS[
                    "grouped-native-rank80"
                ][0],
                "entry_budget": 80,
            }
            population = s._population_coordinate(
                adapter_id="l2b-current-union-selectors-v1",
                coordinate=source_coordinate,
            )
            selector = s._selector_coordinate(source_coordinate)
            assert "fraction_id" not in population
            assert selector["fraction_id"] == fraction_id
            s._merge_global_ceiling(retained, {
                "source_label": fraction_id,
                "population_coordinate": population,
                "availability": "available",
                "mean_population_ceiling_micro": {
                    "numerator": 200_000_000 * s.SOURCE_SLATE_COUNT,
                    "denominator": s.SOURCE_SLATE_COUNT,
                    "unit": "micro_dk",
                },
                "thresholds": [],
            })
    assert len(retained) == len(s.WORLD_BLOCKS) == 5

    # Exercise the complete 300-cell extraction path, not only the coordinate
    # projection helper: ten fraction/block combinations must still emit five
    # physical population ceilings.
    grade_path = _write(tmp_path, "l2b.json", _l2b_grade())
    result = s.build_scorecard_v1([s.ScorecardInputV1("l2b", grade_path)])
    assert len(result["corpus_ceiling_rows"]) == 5
    assert {
        tuple(sorted(row["population_coordinate"].items()))
        for row in result["corpus_ceiling_rows"]
    } == {
        tuple(sorted({
            "adapter_id": "l2b-current-union-selectors-v1",
            "heldout_block": block,
        }.items()))
        for block in s.WORLD_BLOCKS
    }


def test_new_grade_outcome_authority_requires_internal_hash_match(
    tmp_path: Path,
) -> None:
    first = _write(
        tmp_path,
        "first.json",
        _hard_grade(outcome_internal_sha256="a" * 64),
    )
    second = _write(
        tmp_path,
        "second.json",
        _hard_grade(outcome_internal_sha256="c" * 64),
    )
    with pytest.raises(
        s.CorpusR6ScoreSprintScorecardV1Error,
        match="incompatible realized-outcome authority tuples",
    ):
        s.build_scorecard_v1([
            s.ScorecardInputV1("first", first),
            s.ScorecardInputV1("second", second),
        ])

    positive = s.build_scorecard_v1([s.ScorecardInputV1("first", first)])
    assert positive["new_grade_outcome_authority"] == {
        "kind": "common-exact-realized-outcome-snapshot",
        "identity": _identity("outcome"),
        "internal_sha256": "a" * 64,
    }


def test_default_markdown_renders_full_reference_and_diagnostic_metrics() -> None:
    current = _performance_row(
        source="current",
        selector="current-r6",
        mean_milli=178_435,
        counts=(10, 9, 3, 1),
    )
    legacy = _performance_row(
        source="legacy",
        selector="legacy-a7",
        mean_milli=176_113,
        counts=(8, 7, 2, 1),
    )
    diagnostic = _performance_row(
        source="new-arm",
        selector="hard230",
        mean_milli=181_250,
        counts=(12, 11, 4, 2),
    )
    markdown = s.render_markdown_v1({
        "schema_version": s.SCORECARD_SCHEMA,
        "decision_bearing_all_block_final_fit_rows": [current],
        "frozen_benchmark_reference_rows": [legacy],
        "diagnostic_groups": [{
            "estimand_class": "fixed-r1-r4-fit-exact-k80",
            "entry_budget": 80,
            "rows": [diagnostic],
        }],
        "corpus_ceiling_rows": [],
    })
    assert "178.435" in markdown
    assert "176.113" in markdown
    legacy_line = next(
        line for line in markdown.splitlines() if "legacy-a7" in line
    )
    assert all(value in legacy_line for value in (
        "8/54 (14.8%)",
        "7/54 (13.0%)",
        "2/54 (3.7%)",
        "1/54 (1.9%)",
    ))
    diagnostic_line = next(
        line for line in markdown.splitlines() if "hard230" in line
    )
    assert "181.250" in diagnostic_line
    assert all(value in diagnostic_line for value in (
        "12/54 (22.2%)",
        "11/54 (20.4%)",
        "4/54 (7.4%)",
        "2/54 (3.7%)",
    ))


def test_incomplete_root_and_cross_pair_fail(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "incomplete.json",
        {
            "schema_version": s.NOVEL_GRADE_SCHEMA,
            "adapter_id": "l2b-current-union-selectors-v1",
        },
    )
    with pytest.raises(s.CorpusR6ScoreSprintScorecardV1Error, match="root fields"):
        s.build_scorecard_v1([s.ScorecardInputV1("x", path)])
    value = {field: None for field in s._HARD_ROOT_FIELDS}
    value.update(
        schema_version=s.HARD230_GRADE_SCHEMA,
        adapter_id="l2b-current-union-selectors-v1",
        all_score_free_predecessors_replayed_before_outcome_open=True,
        outcome_source_and_slate_identity_bound=True,
    )
    path = _write(tmp_path, "crossed.json", value)
    with pytest.raises(s.CorpusR6ScoreSprintScorecardV1Error, match="hard230.*law"):
        s.build_scorecard_v1([s.ScorecardInputV1("x", path)])


def test_population_only_is_iff() -> None:
    coordinate = {
        "adapter_id": "l2b-current-union-selectors-v1",
        "metric_kind": "selected-book",
        "fraction_id": "l2b-native",
        "heldout_block": "R0",
        "selector_family": "x",
        "selector_ordinal": 0,
        "selector_id": "x",
        "entry_budget": 80,
    }
    cell = {field: None for field in s._CELL_FIELDS}
    cell.update(
        schema_version=s.AGGREGATE_CELL_SCHEMA,
        coordinate=coordinate,
        coordinate_sha256=s.canonical_sha256_v1(coordinate),
        source_slate_count=54,
        slate_rows=[],
        thresholds=[],
        selection_conversion_available=False,
        complete=True,
    )
    cell["aggregate_cell_sha256"] = s.canonical_sha256_v1({
        key: value
        for key, value in cell.items()
        if key != "aggregate_cell_sha256"
    })
    with pytest.raises(s.CorpusR6ScoreSprintScorecardV1Error, match="not iff"):
        s._validate_cell(cell, adapter_id="l2b-current-union-selectors-v1")


def test_global_ceiling_duplicate_logic_is_content_sensitive() -> None:
    coordinate = {"adapter_id": "x", "population_id": "same"}
    one = {"population_coordinate": coordinate, "mean": 1}
    two = {"population_coordinate": coordinate, "mean": 2}
    retained: dict[bytes, dict[str, object]] = {}
    s._merge_global_ceiling(retained, one)
    s._merge_global_ceiling(retained, {"source_label": "duplicate", **one})
    assert len(retained) == 1
    with pytest.raises(
        s.CorpusR6ScoreSprintScorecardV1Error,
        match="duplicate population ceilings diverge",
    ):
        s._merge_global_ceiling(retained, two)
