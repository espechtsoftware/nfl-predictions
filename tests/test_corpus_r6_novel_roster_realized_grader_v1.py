from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.research import (
    corpus_r6_novel_roster_realized_grader_v1 as grader,
)
from nfl_dfs.research import (
    corpus_extreme_tail_hard230_population_successor_v1 as hard_successor,
)
from nfl_dfs.research import corpus_r6_full_union_outcome_snapshot_v1 as outcomes
from nfl_dfs.research.corpus_batch_evidence_contract import MICRO_DK_PER_POINT


def _identity(uri: str, value: object, generation: int = 1) -> dict[str, object]:
    raw = grader.canonical_json_bytes_v1(value)
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _placeholder_identity(label: str, ordinal: int = 0) -> dict[str, object]:
    value = {"label": label, "ordinal": ordinal}
    return _identity(f"gs://fixture/{label}-{ordinal}.json", value, ordinal + 1)


def _result_descriptors() -> list[dict[str, object]]:
    return [{
        "source_ordinal": ordinal,
        "slate_id": f"2024-w{ordinal + 1:02d}",
        "task_result_identity": _placeholder_identity("task-result", ordinal),
        "task_result_sha256": sha256(f"result-{ordinal}".encode()).hexdigest(),
    } for ordinal in range(grader.SOURCE_SLATE_COUNT)]


def _roster(start: int) -> list[str]:
    return [f"p{value}" for value in range(start, start + 9)]


def _normalized_slates(*, selected: bool = True) -> list[dict[str, object]]:
    slates = []
    for ordinal in range(grader.SOURCE_SLATE_COUNT):
        first = {
            "lineup_id": "lineup-a",
            "roster_player_ids": _roster(0),
            "roster_sha256": grader.canonical_sha256_v1(_roster(0)),
        }
        second_roster = [*_roster(0)[:8], "p9"]
        second = {
            "lineup_id": "lineup-b",
            "roster_player_ids": second_roster,
            "roster_sha256": grader.canonical_sha256_v1(second_roster),
        }
        coordinate = {
            "adapter_id": grader.POPULATION_CROSSED_ADAPTER,
            "metric_kind": "selected-book",
            "heldout_block": "R0",
            "profile_id": "fixture-profile",
            "selector_family": "fixture-selector",
            "selector_ordinal": 0,
            "selector_id": "fixture-selector-v1",
            "entry_budget": 1,
        }
        slates.append({
            "source_ordinal": ordinal,
            "slate_id": f"2024-w{ordinal + 1:02d}",
            "populations": [{
                "population_id": "fixture-population",
                "dimensions": {"entry_budget": 2},
                "lineups": [first, second],
            }],
            "books": ([] if not selected else [{
                "coordinate": coordinate,
                "coordinate_sha256": grader.canonical_sha256_v1(coordinate),
                "population_id": "fixture-population",
                "selected_lineup_ids": ["lineup-b"],
            }]),
        })
    return slates


def _snapshot(later_source_identity: dict[str, object]) -> dict[str, object]:
    rows = []
    for source_ordinal in range(grader.SOURCE_SLATE_COUNT):
        for player_ordinal in range(10):
            # lineup-a = 240 DK; lineup-b = 220 DK.
            if player_ordinal < 8:
                points = 25
            elif player_ordinal == 8:
                points = 40
            else:
                points = 20
            rows.append({
                "source_ordinal": source_ordinal,
                "season": 2024,
                "week": source_ordinal + 1,
                "slate_id": f"2024-w{source_ordinal + 1:02d}",
                "player_id": f"p{player_ordinal}",
                "realized_score_micro": points * MICRO_DK_PER_POINT,
            })
    row_keys = [{key: row[key] for key in (
        "source_ordinal", "season", "week", "slate_id", "player_id"
    )} for row in rows]
    body = {
        "schema_version": outcomes.OUTCOME_SNAPSHOT_SCHEMA,
        "outcome_key_projection_identity": _placeholder_identity("projection"),
        "outcome_key_projection_sha256": "1" * 64,
        "panel_freeze_identity": _placeholder_identity("panel"),
        "panel_freeze_sha256": "2" * 64,
        "later_source_freeze_identity": later_source_identity,
        "later_source_freeze_sha256": "3" * 64,
        "realized_source_identity": _placeholder_identity("realized-source"),
        "realized_source_sha256": "4" * 64,
        "score_unit": "micro_dk",
        "micro_dk_per_point": MICRO_DK_PER_POINT,
        "row_count": len(rows),
        "row_keys_sha256": grader.canonical_sha256_v1(row_keys),
        "rows_sha256": grader.canonical_sha256_v1(rows),
        "rows": rows,
        "exact_union_coverage": True,
        "lineup_scoring_performed": False,
        "full_field_standings_included": False,
        "payout_ladder_included": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    body["outcome_snapshot_sha256"] = grader.canonical_sha256_v1(body)
    return body


def _fake_opened(
    *, descriptors: list[dict[str, object]], later_source_identity: dict[str, object],
) -> grader._OpenedTerminal:
    manifest = {"task_manifest_sha256": "a" * 64}
    return grader._OpenedTerminal(
        adapter_id=grader.POPULATION_CROSSED_ADAPTER,
        task_manifest=manifest,
        task_manifest_identity=_placeholder_identity("manifest"),
        task_manifest_sha256="a" * 64,
        task_results=tuple({"ordinal": value} for value in range(54)),
        task_result_descriptors=tuple(descriptors),
        slates=tuple(_normalized_slates()),
        later_source_identity=later_source_identity,
    )


def test_terminal_root_requires_exactly_54_ordered_result_identities() -> None:
    descriptors = _result_descriptors()
    root = grader.build_terminal_experiment_root_v1(
        adapter_id=grader.POPULATION_CROSSED_ADAPTER,
        task_manifest_identity=_placeholder_identity("manifest"),
        task_manifest_sha256="a" * 64,
        task_result_descriptors=descriptors,
    )
    assert grader.validate_terminal_experiment_root_v1(deepcopy(root)) == root
    assert root["source_slate_count"] == 54
    assert root["root_built_after_all_task_results"] is True

    with pytest.raises(
        grader.CorpusR6NovelRosterRealizedGraderV1Error,
        match="exactly 54",
    ):
        grader.build_terminal_experiment_root_v1(
            adapter_id=grader.POPULATION_CROSSED_ADAPTER,
            task_manifest_identity=_placeholder_identity("manifest"),
            task_manifest_sha256="a" * 64,
            task_result_descriptors=descriptors[:-1],
        )


def test_terminal_root_tamper_fails_closed() -> None:
    root = grader.build_terminal_experiment_root_v1(
        adapter_id=grader.HARD230_ADAPTER,
        task_manifest_identity=_placeholder_identity("manifest"),
        task_manifest_sha256="a" * 64,
        task_result_descriptors=_result_descriptors(),
    )
    root["complete"] = False
    with pytest.raises(
        grader.CorpusR6NovelRosterRealizedGraderV1Error, match="self-hash"
    ):
        grader.validate_terminal_experiment_root_v1(root)


def test_terminal_root_is_published_create_once_only_after_adapter_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptors = _result_descriptors()
    later = _placeholder_identity("later-source")
    opened = _fake_opened(descriptors=descriptors, later_source_identity=later)
    events: list[str] = []
    objects: dict[tuple[str, str], bytes] = {}

    def fake_adapter(**_kwargs):
        events.append("all-54-results-validated")
        return opened

    def publisher(uri: str, payload: bytes):
        events.append("root-create-once")
        identity = {
            "uri": uri,
            "generation": "9001",
            "sha256": sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
        objects[(uri, "9001")] = payload
        return identity

    def reader(identity):
        return objects[(str(identity["uri"]), str(identity["generation"]))]

    monkeypatch.setitem(
        grader._ADAPTER_REGISTRY, grader.POPULATION_CROSSED_ADAPTER, fake_adapter
    )
    root, identity = grader.publish_terminal_experiment_root_v1(
        adapter_id=grader.POPULATION_CROSSED_ADAPTER,
        task_manifest_identity=opened.task_manifest_identity,
        task_result_identities=[
            row["task_result_identity"] for row in descriptors
        ],
        target_uri="gs://fixture/terminal/experiment-root.json",
        read_exact=reader,
        publish_create_once=publisher,
    )
    assert events == ["all-54-results-validated", "root-create-once"]
    assert identity["sha256"] == sha256(
        grader.canonical_json_bytes_v1(root)
    ).hexdigest()


def test_population_crossed_adapter_normalizes_population_and_selected_book() -> None:
    later = _placeholder_identity("later-source")
    roster_a = _roster(0)
    roster_b = [*_roster(0)[:8], "p9"]
    result = {
        "source_ordinal": 0,
        "slate_id": "2024-w01",
        "fold_results": [{
            "fold_ordinal": 0,
            "heldout_block": "R0",
            "profile_results": [{
                "profile_id": "f7",
                "sampled_lineup_ids": ["a", "b"],
                "sampled_candidate_rows": [
                    {"lineup_id": "a", "roster_player_ids": roster_a},
                    {"lineup_id": "b", "roster_player_ids": roster_b},
                ],
                "evaluation_book_descriptors": [{
                    "selector_family": "rank",
                    "selector_ordinal": 0,
                    "selector_id": "rank-v1",
                    "prefixes": [{
                        "entry_budget": 1,
                        "selected_lineup_ids": ["b"],
                    }],
                }],
                "evaluator_recipe": {"later_source_identity": later},
            }],
        }],
    }
    normalized = grader._normalize_population_crossed_slate(result)
    assert len(normalized["populations"]) == 1
    assert normalized["books"][0]["selected_lineup_ids"] == ["b"]
    assert normalized["later_source_identity"] == later


def test_hard230_adapter_normalizes_both_population_mechanisms() -> None:
    def population(population_id: str, roster: list[str], first: int):
        roster_sha = grader.canonical_sha256_v1(roster)
        rows = [{
            "lineup_id": f"lineup-v1-{roster_sha}",
            "roster_player_ids": roster,
            "roster_sha256": roster_sha,
            "first_occurrence_ordinal": first,
            "fit_world_score_vector_sha256": "8" * 64,
        }]
        return {
            "population_id": population_id,
            "population_lineup_count": 1,
            "population_rosters": rows,
            "population_rosters_sha256": grader.canonical_sha256_v1(rows),
            "uses_heldout_scores": False,
            "uses_realized_outcomes": False,
        }

    control = population(hard_successor.CONTROL_POPULATION_ID, _roster(0), 0)
    challenger = population(
        hard_successor.CHALLENGER_POPULATION_ID, [*_roster(0)[:8], "p9"], 1
    )
    task = {
        "task_index": 0,
        "slate_id": "2024-w01",
        "p0_target_count": 80,
        "score_blind_control_population_count": 1,
        "score_blind_control_population_sha256": control[
            "population_rosters_sha256"
        ],
        "hard230_challenger_population_count": 1,
        "hard230_challenger_population_sha256": challenger[
            "population_rosters_sha256"
        ],
    }
    receipt = {"scientific_receipt": {
        "target_retained_count": 80,
        "score_blind_control_population": control,
        "hard230_challenger_population": challenger,
    }}
    normalized = grader._normalize_hard230_slate(
        task_result=task, process_receipt=receipt
    )
    assert [row["population_id"] for row in normalized["populations"]] == [
        hard_successor.CONTROL_POPULATION_ID,
        hard_successor.CHALLENGER_POPULATION_ID,
    ]
    assert all(row["dimensions"]["entry_budget"] == 80 for row in normalized[
        "populations"
    ])


def test_grade_is_terminal_first_scores_each_roster_once_and_emits_tail_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptors = _result_descriptors()
    later = _placeholder_identity("later-source")
    opened = _fake_opened(descriptors=descriptors, later_source_identity=later)
    events: list[str] = []

    def fake_adapter(**kwargs):
        events.append("terminal-adapter-complete")
        return opened

    monkeypatch.setitem(
        grader._ADAPTER_REGISTRY, grader.POPULATION_CROSSED_ADAPTER, fake_adapter
    )
    root = grader.build_terminal_experiment_root_v1(
        adapter_id=grader.POPULATION_CROSSED_ADAPTER,
        task_manifest_identity=opened.task_manifest_identity,
        task_manifest_sha256=opened.task_manifest_sha256,
        task_result_descriptors=descriptors,
    )
    root_identity = _identity("gs://fixture/terminal-root.json", root)
    snapshot = _snapshot(later)
    snapshot_identity = _identity("gs://fixture/outcome-snapshot.json", snapshot)

    def terminal_reader(identity):
        assert identity == root_identity
        return grader.canonical_json_bytes_v1(root)

    def outcome_reader(identity):
        events.append("first-outcome-read")
        assert identity == snapshot_identity
        return grader.canonical_json_bytes_v1(snapshot)

    grade = grader.grade_novel_roster_experiment_realized_v1(
        terminal_root_identity=root_identity,
        outcome_snapshot_identity=snapshot_identity,
        read_terminal_exact=terminal_reader,
        read_outcome_exact=outcome_reader,
    )
    assert events == ["terminal-adapter-complete", "first-outcome-read"]
    assert grade["terminal_before_first_outcome_read"] is True
    assert grade["roster_sum_operation_count"] == 2 * 54
    assert all(
        slate["roster_sum_operation_count"] == slate["unique_roster_count"] == 2
        for slate in grade["slate_grades"]
    )
    cell = grade["aggregate_cells"][0]
    assert cell["mean_weekly_maximum_micro"] == {
        "numerator": 220 * MICRO_DK_PER_POINT * 54,
        "denominator": 54,
        "unit": "micro_dk",
    }
    assert cell["mean_population_ceiling_regret_micro"] == {
        "numerator": 20 * MICRO_DK_PER_POINT * 54,
        "denominator": 54,
        "unit": "micro_dk",
    }
    assert [row["selected_slates_with_at_least_one_hit"] for row in cell[
        "thresholds"
    ]] == [54, 54, 54, 0]
    assert cell["population_ceiling_conversion_count"] == 0


def test_invalid_terminal_root_never_invokes_outcome_reader() -> None:
    descriptors = _result_descriptors()
    root = grader.build_terminal_experiment_root_v1(
        adapter_id=grader.POPULATION_CROSSED_ADAPTER,
        task_manifest_identity=_placeholder_identity("manifest"),
        task_manifest_sha256="a" * 64,
        task_result_descriptors=descriptors,
    )
    root["complete"] = False
    root_identity = _identity("gs://fixture/bad-terminal-root.json", root)
    outcome_calls = 0

    def outcome_reader(_identity):
        nonlocal outcome_calls
        outcome_calls += 1
        raise AssertionError("outcome reader must remain inaccessible")

    with pytest.raises(
        grader.CorpusR6NovelRosterRealizedGraderV1Error, match="self-hash"
    ):
        grader.grade_novel_roster_experiment_realized_v1(
            terminal_root_identity=root_identity,
            outcome_snapshot_identity=_placeholder_identity("snapshot"),
            read_terminal_exact=lambda _identity: grader.canonical_json_bytes_v1(root),
            read_outcome_exact=outcome_reader,
        )
    assert outcome_calls == 0


def test_missing_novel_player_outcome_fails_closed_after_terminal_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptors = _result_descriptors()
    later = _placeholder_identity("later-source")
    opened = _fake_opened(descriptors=descriptors, later_source_identity=later)
    monkeypatch.setitem(
        grader._ADAPTER_REGISTRY,
        grader.POPULATION_CROSSED_ADAPTER,
        lambda **_kwargs: opened,
    )
    root = grader.build_terminal_experiment_root_v1(
        adapter_id=grader.POPULATION_CROSSED_ADAPTER,
        task_manifest_identity=opened.task_manifest_identity,
        task_manifest_sha256=opened.task_manifest_sha256,
        task_result_descriptors=descriptors,
    )
    root_identity = _identity("gs://fixture/terminal-root.json", root)
    snapshot = _snapshot(later)
    snapshot["rows"] = [
        row for row in snapshot["rows"]
        if not (row["source_ordinal"] == 0 and row["player_id"] == "p9")
    ]
    snapshot["row_count"] = len(snapshot["rows"])
    snapshot["rows_sha256"] = grader.canonical_sha256_v1(snapshot["rows"])
    row_keys = [{key: row[key] for key in (
        "source_ordinal", "season", "week", "slate_id", "player_id"
    )} for row in snapshot["rows"]]
    snapshot["row_keys_sha256"] = grader.canonical_sha256_v1(row_keys)
    snapshot["outcome_snapshot_sha256"] = grader.canonical_sha256_v1({
        key: value for key, value in snapshot.items()
        if key != "outcome_snapshot_sha256"
    })
    snapshot_identity = _identity("gs://fixture/outcome-snapshot.json", snapshot)
    with pytest.raises(
        grader.CorpusR6NovelRosterRealizedGraderV1Error,
        match="lacks novel-roster player key",
    ):
        grader.grade_novel_roster_experiment_realized_v1(
            terminal_root_identity=root_identity,
            outcome_snapshot_identity=snapshot_identity,
            read_terminal_exact=lambda _identity: grader.canonical_json_bytes_v1(root),
            read_outcome_exact=lambda _identity: grader.canonical_json_bytes_v1(snapshot),
        )
