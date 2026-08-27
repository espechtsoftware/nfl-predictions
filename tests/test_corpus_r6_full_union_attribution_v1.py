"""Hermetic adversarial tests for the R6 per-slate attribution join.

The fixture retains production geometry (six scopes, eight strategies, eighty
ranked selections, and one complete final union) while using only synthetic
lineups and scores.  No outcome source, cloud object, or tracked score artifact
is opened by this module.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import pytest

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_attribution_v1 as attribution
from nfl_dfs.research import residual_world_columns as rw
from tests import test_corpus_r6_full_union_realized_grading_v1 as grade_fixture


@dataclass(frozen=True)
class _Case:
    source_ordinal: int
    slate_id: str
    task_result: dict[str, object]
    slate_grade: dict[str, object]
    panel_freeze_identity: dict[str, object]
    slate_freeze_identity: dict[str, object]
    task_result_identity: dict[str, object]
    slate_grade_identity: dict[str, object]

    def build(self, **overrides: object) -> dict[str, object]:
        arguments: dict[str, object] = {
            "source_ordinal": self.source_ordinal,
            "slate_id": self.slate_id,
            "task_result": self.task_result,
            "realized_slate_grade": self.slate_grade,
            "panel_freeze_identity": self.panel_freeze_identity,
            "slate_freeze_identity": self.slate_freeze_identity,
            "task_result_identity": self.task_result_identity,
            "slate_grade_identity": self.slate_grade_identity,
            "candidate_provenance": None,
        }
        arguments.update(overrides)
        return attribution.build_slate_attribution_v1(**arguments)  # type: ignore[arg-type]

    def validate(
        self, value: object, **overrides: object,
    ) -> dict[str, object]:
        arguments: dict[str, object] = {
            "source_ordinal": self.source_ordinal,
            "slate_id": self.slate_id,
            "task_result": self.task_result,
            "realized_slate_grade": self.slate_grade,
            "panel_freeze_identity": self.panel_freeze_identity,
            "slate_freeze_identity": self.slate_freeze_identity,
            "task_result_identity": self.task_result_identity,
            "slate_grade_identity": self.slate_grade_identity,
            "candidate_provenance": None,
        }
        arguments.update(overrides)
        return attribution.validate_slate_attribution_v1(  # type: ignore[arg-type]
            value, **arguments
        )


def _rehash(value: dict[str, object], field: str) -> None:
    value.pop(field, None)
    value[field] = batch.canonical_sha256(value)


def _enrich_task_result(task_result: dict[str, object]) -> None:
    """Add the validated candidate/admission/trace surfaces omitted by the grade fixture."""
    surface = task_result["full_union_surface"]
    assert isinstance(surface, dict)
    slate = surface["slate"]
    assert isinstance(slate, dict)
    task_result["slate_id"] = slate["slate_id"]
    task_result["candidate_provenance_sha256"] = batch.canonical_sha256({
        "synthetic_slate_id": slate["slate_id"],
    })
    scopes = surface["scopes"]
    assert isinstance(scopes, list)
    final_scope = scopes[-1]
    assert isinstance(final_scope, dict)
    final_view = final_scope["candidate_view"]
    assert isinstance(final_view, dict)
    base_candidates = final_view["eligible_candidates"]
    assert isinstance(base_candidates, list)
    global_index_by_id = {
        str(row["lineup_id"]): index
        for index, row in enumerate(base_candidates)
        if isinstance(row, dict)
    }

    for scope_ordinal, scope_value in enumerate(scopes):
        assert isinstance(scope_value, dict)
        heldout = scope_value["heldout_block"]
        training_blocks = [block for block in rw.WORLD_BLOCKS if block != heldout]
        scope_value["training_blocks"] = list(training_blocks)
        eligible: list[dict[str, object]] = []
        for global_index, raw in enumerate(base_candidates):
            assert isinstance(raw, dict)
            arm_id = batch.PARAMETER_SET_ORDER[
                global_index % len(batch.PARAMETER_SET_ORDER)
            ]
            eligible.append({
                "lineup_id": raw["lineup_id"],
                "roster_player_ids": deepcopy(raw["roster_player_ids"]),
                "training_origin_blocks": list(training_blocks),
                "training_source_arms": [arm_id],
                "training_occurrence_counts_by_block": {
                    block: 1 for block in training_blocks
                },
                "training_source_arms_by_block": {
                    block: [arm_id] for block in training_blocks
                },
                "training_occurrence_count": len(training_blocks),
            })
        selection_projection = {
            "schema_version": "corpus-fold-selection-provenance/v2",
            "slate": deepcopy(surface["slate"]),
            "fit_scope_id": scope_value["fit_scope_id"],
            "training_blocks": list(training_blocks),
            "eligible_candidates": eligible,
            "dose_authority": runner.AUTHORITATIVE_DOSE,
            "uses_realized_outcomes": False,
        }
        candidate_view: dict[str, object] = {
            "schema_version": "corpus-fold-candidate-view/v2",
            "slate": deepcopy(surface["slate"]),
            "fit_scope_id": scope_value["fit_scope_id"],
            "training_blocks": list(training_blocks),
            "heldout_block": heldout,
            "eligible_candidates": eligible,
            "excluded_candidates_audit": [],
            "eligible_count": len(eligible),
            "excluded_count": 0,
            "dose_authority": runner.AUTHORITATIVE_DOSE,
            "selection_inputs_exclude_heldout_occurrences": True,
            "selection_provenance_sha256": batch.canonical_sha256(
                selection_projection
            ),
            "uses_realized_outcomes": False,
        }
        candidate_view["fit_candidate_view_sha256"] = batch.canonical_sha256(
            candidate_view
        )
        admitted_ids = [str(row["lineup_id"]) for row in eligible]
        admission: dict[str, object] = {
            "schema_version": runner.ADMISSION_SCHEMA,
            "admission_id": runner.FULL_UNION_ADMISSION_ID,
            "fit_scope_id": scope_value["fit_scope_id"],
            "selection_provenance_sha256": candidate_view[
                "selection_provenance_sha256"
            ],
            "admitted_lineup_ids": admitted_ids,
            "admitted_count": len(admitted_ids),
            "excluded_eligible_candidates": [],
            "dose_authority": runner.AUTHORITATIVE_DOSE,
            "admission_inputs": "fold-local-provenance-and-stable-lineup-id-only",
            "uses_simulated_scores": False,
            "uses_matchup_values": False,
            "uses_realized_outcomes": False,
        }
        admission["admission_sha256"] = batch.canonical_sha256(admission)
        scope_value["candidate_view"] = candidate_view
        scope_value["admission"] = admission

        books = scope_value["books"]
        assert isinstance(books, list)
        for book in books:
            assert isinstance(book, dict)
            selected_ids = book["selected_lineup_ids"]
            assert isinstance(selected_ids, list)
            selected_indices = [
                global_index_by_id[str(lineup_id)] for lineup_id in selected_ids
            ]
            book["selected_local_indices"] = selected_indices
            book["selected_global_indices"] = list(selected_indices)
            book["marginal_trace"] = [
                {
                    "selection_rank": rank,
                    "lineup_id": lineup_id,
                    "global_lineup_index": global_index_by_id[str(lineup_id)],
                    "admitted_lineup_index": global_index_by_id[str(lineup_id)],
                    "synthetic_objective_gain": rank + 1,
                }
                for rank, lineup_id in enumerate(selected_ids)
            ]


@pytest.fixture(scope="module")
def case() -> Any:
    patcher = pytest.MonkeyPatch()
    panel = grade_fixture._synthetic_panel()
    for leaf, task_result, _ in panel.leaves_by_uri.values():
        del leaf
        _enrich_task_result(task_result)
    grade_fixture._install_validators(patcher, panel)
    _, shards = grade_fixture._grade(panel)
    root_row = panel.root["slate_freezes"][0]
    leaf_identity = root_row["slate_freeze_identity"]
    assert isinstance(leaf_identity, dict)
    leaf, task_result, retained_leaf_identity = panel.leaves_by_uri[
        str(leaf_identity["uri"])
    ]
    assert retained_leaf_identity == leaf_identity
    built = _Case(
        source_ordinal=0,
        slate_id=str(leaf["slate_id"]),
        task_result=task_result,
        slate_grade=shards[0],
        panel_freeze_identity=panel.root_identity,
        slate_freeze_identity=leaf_identity,
        task_result_identity=leaf["task_result_identity"],
        slate_grade_identity=grade_fixture._identity("attribution-slate-grade-0"),
    )
    yield built
    patcher.undo()


def _final_candidates(task_result: dict[str, object]) -> list[dict[str, object]]:
    surface = task_result["full_union_surface"]
    assert isinstance(surface, dict)
    scopes = surface["scopes"]
    assert isinstance(scopes, list)
    final_scope = scopes[-1]
    assert isinstance(final_scope, dict)
    view = final_scope["candidate_view"]
    assert isinstance(view, dict)
    candidates = view["eligible_candidates"]
    assert isinstance(candidates, list)
    return candidates  # type: ignore[return-value]


def _first_book(task_result: dict[str, object]) -> dict[str, object]:
    surface = task_result["full_union_surface"]
    assert isinstance(surface, dict)
    scopes = surface["scopes"]
    assert isinstance(scopes, list) and isinstance(scopes[0], dict)
    books = scopes[0]["books"]
    assert isinstance(books, list) and isinstance(books[0], dict)
    return books[0]


def _first_grade_book(slate_grade: dict[str, object]) -> dict[str, object]:
    books = slate_grade["book_grades"]
    assert isinstance(books, list) and isinstance(books[0], dict)
    return books[0]


def test_exact_lineup_roster_book_and_rank_join_is_deterministic(
    case: _Case,
) -> None:
    first = case.build()
    second = case.build()
    replayed = case.validate(first)

    assert attribution.canonical_json_bytes(first) == (
        attribution.canonical_json_bytes(second)
    )
    assert attribution.canonical_json_bytes(replayed) == (
        attribution.canonical_json_bytes(first)
    )
    retained_sha = first["slate_attribution_sha256"]
    assert retained_sha == attribution.canonical_sha256({
        key: value
        for key, value in first.items()
        if key != "slate_attribution_sha256"
    })

    lineup_rows = first["lineup_rows"]
    scope_rows = first["scope_membership_rows"]
    book_rows = first["book_rows"]
    selection_rows = first["selection_rows"]
    assert isinstance(lineup_rows, list)
    assert isinstance(scope_rows, list)
    assert isinstance(book_rows, list)
    assert isinstance(selection_rows, list)
    assert len(lineup_rows) == len(_final_candidates(case.task_result))
    assert len(scope_rows) == 6 * len(lineup_rows)
    assert len(book_rows) == 6 * 8
    assert len(selection_rows) == 6 * 8 * 80

    first_lineup = lineup_rows[0]
    assert isinstance(first_lineup, dict)
    frozen_candidate = _final_candidates(case.task_result)[0]
    grade_score = case.slate_grade["union_score_rows"][0]
    assert first_lineup["lineup_id"] == frozen_candidate["lineup_id"]
    assert first_lineup["roster_player_ids"] == frozen_candidate[
        "roster_player_ids"
    ]
    assert first_lineup["roster_identity_sha256"] == grade_score[
        "roster_identity_sha256"
    ]
    assert first_lineup["realized_score_micro"] == grade_score[
        "realized_score_micro"
    ]

    first_selection = selection_rows[0]
    assert isinstance(first_selection, dict)
    frozen_book = _first_book(case.task_result)
    grade_book = _first_grade_book(case.slate_grade)
    assert first_selection["lineup_id"] == frozen_book[
        "selected_lineup_ids"
    ][0]
    assert first_selection["lineup_id"] == grade_book[
        "rank_80_score_rows"
    ][0]["lineup_id"]
    assert first_selection["selection_rank"] == 0
    assert first_selection["marginal_trace"] == frozen_book[
        "marginal_trace"
    ][0]

    assert first["uses_realized_outcomes"] is True
    assert first["no_rescore"] is True
    assert first["projected_from_persisted_union_score_lookup"] is True
    for field in (
        "outcome_source_read",
        "additional_historical_outcome_read",
        "bigquery_client_constructed",
        "outcome_query_executed",
        "historical_scoring_licensed",
        "historical_retry_licensed",
        "historical_retune_licensed",
        "corpus_fill_licensed",
        "graph_mutation_licensed",
        "production_change_licensed",
        "promotion_authority",
        "decision_authority",
    ):
        assert first[field] is False


def test_missing_final_union_lineup_is_rejected(case: _Case) -> None:
    changed = deepcopy(case.task_result)
    surface = changed["full_union_surface"]
    assert isinstance(surface, dict)
    scopes = surface["scopes"]
    assert isinstance(scopes, list) and isinstance(scopes[-1], dict)
    final_view = scopes[-1]["candidate_view"]
    assert isinstance(final_view, dict)
    candidates = final_view["eligible_candidates"]
    assert isinstance(candidates, list)
    candidates.pop()
    final_view["eligible_count"] = len(candidates)
    _rehash(final_view, "fit_candidate_view_sha256")

    with pytest.raises(
        attribution.CorpusR6FullUnionAttributionV1Error,
        match="lineup|union|population|candidate",
    ):
        case.build(task_result=changed)


def test_duplicate_final_union_lineup_is_rejected(case: _Case) -> None:
    changed = deepcopy(case.task_result)
    candidates = _final_candidates(changed)
    candidates[-1] = deepcopy(candidates[0])
    surface = changed["full_union_surface"]
    assert isinstance(surface, dict)
    scopes = surface["scopes"]
    assert isinstance(scopes, list) and isinstance(scopes[-1], dict)
    final_view = scopes[-1]["candidate_view"]
    assert isinstance(final_view, dict)
    _rehash(final_view, "fit_candidate_view_sha256")

    with pytest.raises(
        attribution.CorpusR6FullUnionAttributionV1Error,
        match="repeat|duplicate|lineup|union|candidate",
    ):
        case.build(task_result=changed)


def test_grade_roster_identity_drift_is_rejected(case: _Case) -> None:
    changed = deepcopy(case.slate_grade)
    score_rows = changed["union_score_rows"]
    assert isinstance(score_rows, list) and isinstance(score_rows[0], dict)
    score_rows[0]["roster_identity_sha256"] = "f" * 64

    with pytest.raises(
        attribution.CorpusR6FullUnionAttributionV1Error,
        match="roster",
    ):
        case.build(realized_slate_grade=changed)


def test_grade_rank_drift_from_frozen_book_is_rejected(case: _Case) -> None:
    changed = deepcopy(case.slate_grade)
    grade_book = _first_grade_book(changed)
    rank_rows = grade_book["rank_80_score_rows"]
    assert isinstance(rank_rows, list)
    first = deepcopy(rank_rows[0])
    second = deepcopy(rank_rows[1])
    assert isinstance(first, dict) and isinstance(second, dict)
    first["lineup_id"] = second["lineup_id"]
    first["realized_score_micro"] = second["realized_score_micro"]
    second["lineup_id"] = rank_rows[0]["lineup_id"]
    second["realized_score_micro"] = rank_rows[0]["realized_score_micro"]
    rank_rows[0] = first
    rank_rows[1] = second

    with pytest.raises(
        attribution.CorpusR6FullUnionAttributionV1Error,
        match="rank|selection|lineup|book",
    ):
        case.build(realized_slate_grade=changed)


def test_frozen_marginal_trace_rank_drift_is_rejected(case: _Case) -> None:
    changed = deepcopy(case.task_result)
    book = _first_book(changed)
    traces = book["marginal_trace"]
    assert isinstance(traces, list) and isinstance(traces[0], dict)
    traces[0]["lineup_id"] = traces[1]["lineup_id"]

    with pytest.raises(
        attribution.CorpusR6FullUnionAttributionV1Error,
        match="trace|rank|selection|lineup",
    ):
        case.build(task_result=changed)


def test_cross_run_panel_identity_is_rejected(case: _Case) -> None:
    changed = deepcopy(case.slate_grade)
    changed["panel_freeze_identity"] = grade_fixture._identity(
        "other-panel-freeze"
    )

    with pytest.raises(
        attribution.CorpusR6FullUnionAttributionV1Error,
        match="panel|identity|binding",
    ):
        case.build(realized_slate_grade=changed)


def test_builder_does_not_reopen_or_rescore_realized_outcomes(
    case: _Case, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("attribution attempted to reopen or rescore outcomes")

    monkeypatch.setattr(
        attribution.grading.outcomes,
        "validate_outcome_snapshot_v1",
        forbidden,
    )
    monkeypatch.setattr(
        attribution.grading,
        "grade_r6_full_union_realized_v1",
        forbidden,
    )

    value = case.build()

    assert value["outcome_source_read"] is False
    assert value["additional_historical_outcome_read"] is False
    assert value["no_rescore"] is True


@pytest.mark.parametrize(
    "field",
    [
        "outcome_source_read",
        "additional_historical_outcome_read",
        "historical_scoring_licensed",
        "historical_retry_licensed",
        "historical_retune_licensed",
        "corpus_fill_licensed",
        "graph_mutation_licensed",
        "production_change_licensed",
        "promotion_authority",
        "decision_authority",
    ],
)
def test_structure_rejects_coherently_rehashed_forbidden_authority(
    case: _Case, field: str,
) -> None:
    changed = deepcopy(case.build())
    changed[field] = True
    _rehash(changed, "slate_attribution_sha256")

    with pytest.raises(
        attribution.CorpusR6FullUnionAttributionV1Error,
        match="authority|licensed|outcome|read|forbidden",
    ):
        attribution.validate_slate_attribution_structure_v1(changed)
