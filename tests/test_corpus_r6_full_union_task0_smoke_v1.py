from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_fast_lane_v1 as lane
from nfl_dfs.research import corpus_r6_full_union_task0_smoke_v1 as smoke
from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_adapter_v1 as adapter
from nfl_dfs.research import corpus_v12_panel_index as panel_index
from nfl_dfs.research import residual_world_columns as rw


def _identity(name: str, generation: int) -> dict[str, object]:
    raw = name.encode("utf-8")
    return {
        "uri": f"gs://fixture/{name}.json",
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _member(ordinal: int) -> dict[str, object]:
    slate_id = smoke.TASK0_SLATE_ID if ordinal == 0 else f"fixture-{ordinal:02d}"
    return {
        "source_task_ordinal": ordinal,
        "task_ordinal": ordinal,
        "lane_ordinal": 0 if ordinal < 28 else 1,
        "lane_id": "v12a" if ordinal < 28 else "v12b",
        "slate_id": slate_id,
        "source_task_authority_sha256": f"{ordinal + 1:064x}",
        "task_acceptance_identity": _identity(f"acceptance-{ordinal}", 100 + ordinal),
        "carrier_identity": _identity(f"carrier-{ordinal}", 200 + ordinal),
        "arms": [
            {
                "arm_ordinal": arm_ordinal,
                "parameter_set_id": arm_id,
                "result_identity": _identity(
                    f"result-{ordinal}-{arm_ordinal}",
                    1_000 + ordinal * 10 + arm_ordinal,
                ),
            }
            for arm_ordinal, arm_id in enumerate(batch.PARAMETER_SET_ORDER)
        ],
    }


def _fixed_panel(monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, object], bytes]:
    members = [_member(ordinal) for ordinal in range(panel_index.V12_SOURCE_TASK_COUNT)]
    body: dict[str, object] = {
        "schema_version": panel_index.PANEL_INDEX_SCHEMA,
        "publication_mode": panel_index.PUBLICATION_MODE,
        "panel_id": adapter.FIXED_PANEL_ID,
        "accepted_slate_count": panel_index.V12_SOURCE_TASK_COUNT,
        "accepted_slates": members,
        "coverage": {
            "expected_task_count": panel_index.V12_SOURCE_TASK_COUNT,
            "accepted_task_count": panel_index.V12_SOURCE_TASK_COUNT,
            "complete": True,
        },
        "exclusions": [],
        "failures": [],
        "missing_tasks": [],
    }
    body["panel_index_sha256"] = batch.canonical_sha256(body)
    raw = batch.canonical_json_bytes(body)
    panel_identity = {
        "uri": "gs://fixture/fixed-panel.json",
        "generation": "999",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    monkeypatch.setattr(adapter, "FIXED_PANEL_INDEX_SHA256", body["panel_index_sha256"])
    monkeypatch.setattr(adapter, "FIXED_PANEL_IDENTITY", panel_identity)
    monkeypatch.setattr(
        smoke,
        "FIXED_TASK0_MEMBERSHIP_SHA256",
        batch.canonical_sha256(members[0]),
    )
    return body, raw


def _rosters() -> tuple[list[str], list[list[str]]]:
    lineup_ids = [f"lineup-{index:03d}" for index in range(lane.ENTRY_BUDGET)]
    rosters = [
        [f"player-{index:03d}-{slot}" for slot in range(rw.ROSTER_SIZE)]
        for index in range(lane.ENTRY_BUDGET)
    ]
    return lineup_ids, rosters


def _execution(panel: dict[str, object]) -> dict[str, object]:
    strategies = lane.frozen_full_union_strategies_v1()
    lineup_ids, rosters = _rosters()
    candidate_sha = "b" * 64
    reconstruction_sha = "c" * 64
    scopes = []
    for scope_ordinal, heldout in enumerate([*rw.WORLD_BLOCKS, None]):
        training_blocks = [block for block in rw.WORLD_BLOCKS if block != heldout]
        fit_scope_id = (
            "all-block-final-fit" if heldout is None else f"holdout-{heldout}"
        )
        slate = {
            "season": 2023,
            "week": 1,
            "slate_id": smoke.TASK0_SLATE_ID,
        }
        eligible_candidates = [
            {
                "lineup_id": lineup_id,
                "roster_player_ids": list(roster),
                "training_origin_blocks": list(training_blocks),
                "training_source_arms": [batch.PARAMETER_SET_ORDER[0]],
                "training_occurrence_counts_by_block": {
                    block: 1 for block in training_blocks
                },
                "training_source_arms_by_block": {
                    block: [batch.PARAMETER_SET_ORDER[0]]
                    for block in training_blocks
                },
                "training_occurrence_count": len(training_blocks),
            }
            for lineup_id, roster in zip(lineup_ids, rosters, strict=True)
        ]
        selection_projection = {
            "schema_version": "corpus-fold-selection-provenance/v2",
            "slate": slate,
            "fit_scope_id": fit_scope_id,
            "training_blocks": training_blocks,
            "eligible_candidates": eligible_candidates,
            "dose_authority": runner.AUTHORITATIVE_DOSE,
            "uses_realized_outcomes": False,
        }
        selection_sha = batch.canonical_sha256(selection_projection)
        candidate_view: dict[str, object] = {
            "schema_version": "corpus-fold-candidate-view/v2",
            "slate": slate,
            "fit_scope_id": fit_scope_id,
            "training_blocks": training_blocks,
            "heldout_block": heldout,
            "eligible_candidates": eligible_candidates,
            "excluded_candidates_audit": [],
            "eligible_count": len(eligible_candidates),
            "excluded_count": 0,
            "dose_authority": runner.AUTHORITATIVE_DOSE,
            "selection_inputs_exclude_heldout_occurrences": True,
            "selection_provenance_sha256": selection_sha,
            "uses_realized_outcomes": False,
        }
        candidate_view["fit_candidate_view_sha256"] = batch.canonical_sha256(
            candidate_view
        )
        admission: dict[str, object] = {
            "schema_version": runner.ADMISSION_SCHEMA,
            "admission_id": runner.FULL_UNION_ADMISSION_ID,
            "fit_scope_id": fit_scope_id,
            "selection_provenance_sha256": selection_sha,
            "admitted_lineup_ids": list(lineup_ids),
            "admitted_count": len(lineup_ids),
            "excluded_eligible_candidates": [],
            "dose_authority": runner.AUTHORITATIVE_DOSE,
            "admission_inputs": "fold-local-provenance-and-stable-lineup-id-only",
            "uses_simulated_scores": False,
            "uses_matchup_values": False,
            "uses_realized_outcomes": False,
        }
        admission["admission_sha256"] = batch.canonical_sha256(admission)
        books = []
        for strategy in strategies:
            book: dict[str, object] = {
                "schema_version": runner.BOOK_SCHEMA,
                "book_id": f"{fit_scope_id}:{strategy['strategy_id']}",
                "fit_scope_id": fit_scope_id,
                "reconstruction_sha256": reconstruction_sha,
                "training_blocks": training_blocks,
                "strategy_id": strategy["strategy_id"],
                "strategy_sha256": strategy["strategy_sha256"],
                "heldout_block": heldout,
                "admission_id": admission["admission_id"],
                "admission_sha256": admission["admission_sha256"],
                "strategy_application_scope": (
                    "explicit-all-five-block-final-fit"
                    if heldout is None
                    else "explicit-rotated-training-blocks"
                ),
                "input_lineup_ids_sha256": batch.canonical_sha256(lineup_ids),
                "training_score_matrix_sha256": "2" * 64,
                "training_score_shape": [
                    len(lineup_ids),
                    len(training_blocks) * rw.WORLDS_PER_BLOCK,
                ],
                "worlds_per_block": rw.WORLDS_PER_BLOCK,
                "dose_authority": runner.AUTHORITATIVE_DOSE,
                "selected_local_indices": list(range(lane.ENTRY_BUDGET)),
                "selected_global_indices": list(range(lane.ENTRY_BUDGET)),
                "selected_lineup_ids": list(lineup_ids),
                "selected_rosters": deepcopy(rosters),
                "entry_count": lane.ENTRY_BUDGET,
                "marginal_trace": [],
                "training_metrics": {},
                "redundancy_diagnostics": {},
                "heldout_metrics_descriptive": None,
                "threshold_semantics": [],
                "uses_realized_outcomes": False,
                "promotion_authority": False,
            }
            book["book_sha256"] = batch.canonical_sha256(book)
            books.append(book)
        scope: dict[str, object] = {
            "schema_version": lane.SCOPE_SCHEMA,
            "fit_scope_id": fit_scope_id,
            "reconstruction_sha256": reconstruction_sha,
            "training_blocks": training_blocks,
            "heldout_block": heldout,
            "worlds_per_block": rw.WORLDS_PER_BLOCK,
            "dose_authority": runner.AUTHORITATIVE_DOSE,
            "require_authoritative": True,
            "candidate_view": candidate_view,
            "admission": admission,
            "admission_mode": "complete-fold-eligible-cross-arm-union",
            "strategy_registry": strategies,
            "strategy_count": lane.STRATEGY_COUNT,
            "book_count": lane.BOOKS_PER_SCOPE,
            "books": books,
            "matchup_source_read": False,
            "matchup_admission_read": False,
            "neutral_control_read": False,
            "uses_realized_outcomes": False,
            "promotion_authority": False,
        }
        scope["fit_scope_sha256"] = batch.canonical_sha256(scope)
        scopes.append(scope)
    surface: dict[str, object] = {
        "schema_version": lane.SURFACE_SCHEMA,
        "slate": slate,
        "candidate_provenance_sha256": candidate_sha,
        "reconstruction_sha256": reconstruction_sha,
        "scope_count": lane.SCOPE_COUNT,
        "books_per_scope": lane.BOOKS_PER_SCOPE,
        "book_count": lane.BOOKS_PER_SLATE,
        "prefix_sizes": list(lane.PREFIX_SIZES),
        "strategy_registry": strategies,
        "strategy_registry_sha256": batch.canonical_sha256(strategies),
        "scopes": scopes,
        "rotated_simulated_fold_count": len(rw.WORLD_BLOCKS),
        "final_fit_is_distinct_all_block_refit": True,
        "full_union_only": True,
        "matchup_source_read": False,
        "uses_realized_outcomes": False,
        "evidence_tier": "outcome-blind-simulated-analysis",
        "promotion_authority": False,
    }
    surface["full_union_surface_sha256"] = batch.canonical_sha256(surface)
    worlds = {
        role: _identity(role, 2_000 + ordinal)
        for ordinal, role in enumerate(smoke.EXPECTED_WORLD_ROLES)
    }
    member = panel["accepted_slates"][0]
    result: dict[str, object] = {
        "schema_version": lane.EXECUTION_SCHEMA,
        "slate_id": smoke.TASK0_SLATE_ID,
        "panel_index_identity": dict(adapter.FIXED_PANEL_IDENTITY),
        "panel_index_sha256": adapter.FIXED_PANEL_INDEX_SHA256,
        "accepted_slate_membership": deepcopy(member),
        "accepted_slate_membership_sha256": batch.canonical_sha256(member),
        "task_acceptance_identity": deepcopy(member["task_acceptance_identity"]),
        "carrier_identity": deepcopy(member["carrier_identity"]),
        "later_source_freeze_identity": _identity("later-source", 3_000),
        "world_artifact_identities": worlds,
        "world_artifact_identity_set_sha256": batch.canonical_sha256(worlds),
        "compatibility_import_sha256": "a" * 64,
        "candidate_provenance_sha256": candidate_sha,
        "reconstruction_sha256": reconstruction_sha,
        "full_union_surface": surface,
        "full_union_surface_sha256": surface["full_union_surface_sha256"],
        "verification": {
            "panel_exact_reopen_verified": True,
            "accepted_membership_binding_verified": True,
            "task_acceptance_exact_reopen_verified": True,
            "carrier_exact_reopen_verified": True,
            "world_artifact_exact_reopen_verified": True,
            "all_seven_arm_score_hashes_verified": True,
            "complete_cross_arm_union_reconstructed": True,
            "all_48_books_materialized": True,
            "matchup_source_not_read": True,
            "realized_outcomes_not_read": True,
        },
        **{field: False for field in smoke._FALSE_FIELDS},
    }
    result["task_result_sha256"] = batch.canonical_sha256(result)
    return result


def _receipt(monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, object], dict[str, object], bytes]:
    panel, raw = _fixed_panel(monkeypatch)
    receipt = smoke.build_receipt_v1(
        source_commit_sha="d" * 40,
        panel=panel,
        execution_result=_execution(panel),
    )
    return receipt, panel, raw


def _rehash_receipt(receipt: dict[str, object]) -> None:
    result = receipt["execution_result"]
    surface = result["full_union_surface"]
    for scope in surface["scopes"]:
        candidate_view = scope["candidate_view"]
        candidate_view["fit_candidate_view_sha256"] = batch.canonical_sha256({
            key: value
            for key, value in candidate_view.items()
            if key != "fit_candidate_view_sha256"
        })
        admission = scope["admission"]
        admission["admission_sha256"] = batch.canonical_sha256({
            key: value
            for key, value in admission.items()
            if key != "admission_sha256"
        })
        for book in scope["books"]:
            book["admission_sha256"] = admission["admission_sha256"]
            book["input_lineup_ids_sha256"] = batch.canonical_sha256(
                admission["admitted_lineup_ids"]
            )
            book["book_sha256"] = batch.canonical_sha256({
                key: value for key, value in book.items() if key != "book_sha256"
            })
        scope["fit_scope_sha256"] = batch.canonical_sha256({
            key: value for key, value in scope.items() if key != "fit_scope_sha256"
        })
    surface["full_union_surface_sha256"] = batch.canonical_sha256({
        key: value
        for key, value in surface.items()
        if key != "full_union_surface_sha256"
    })
    result["full_union_surface_sha256"] = surface["full_union_surface_sha256"]
    result["task_result_sha256"] = batch.canonical_sha256({
        key: value for key, value in result.items() if key != "task_result_sha256"
    })
    receipt["execution_result_sha256"] = result["task_result_sha256"]
    receipt["receipt_sha256"] = batch.canonical_sha256({
        key: value for key, value in receipt.items() if key != "receipt_sha256"
    })


def test_receipt_validates_fixed_48_book_authoritative_lattice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt, _, _ = _receipt(monkeypatch)
    assert smoke.validate_receipt_v1(receipt) == receipt
    assert receipt["production_dose"]["book_count"] == 48
    assert receipt["production_dose"]["world_count"] == 50_000
    assert receipt["verification"]["realized_outcomes_not_read"] is True


def test_coherently_rehashed_non_80_book_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt, _, _ = _receipt(monkeypatch)
    mutated = deepcopy(receipt)
    result = mutated["execution_result"]
    surface = result["full_union_surface"]
    scope = surface["scopes"][0]
    book = scope["books"][0]
    book["entry_count"] = 79
    book["book_sha256"] = batch.canonical_sha256({
        key: value for key, value in book.items() if key != "book_sha256"
    })
    scope["fit_scope_sha256"] = batch.canonical_sha256({
        key: value for key, value in scope.items() if key != "fit_scope_sha256"
    })
    surface["full_union_surface_sha256"] = batch.canonical_sha256({
        key: value
        for key, value in surface.items()
        if key != "full_union_surface_sha256"
    })
    result["full_union_surface_sha256"] = surface["full_union_surface_sha256"]
    result["task_result_sha256"] = batch.canonical_sha256({
        key: value for key, value in result.items() if key != "task_result_sha256"
    })
    mutated["execution_result_sha256"] = result["task_result_sha256"]
    mutated["receipt_sha256"] = batch.canonical_sha256({
        key: value for key, value in mutated.items() if key != "receipt_sha256"
    })
    with pytest.raises(smoke.CorpusR6FullUnionTask0SmokeV1Error):
        smoke.validate_receipt_v1(mutated)


@pytest.mark.parametrize(
    "mutation",
    [
        "non_full_union",
        "empty_verification",
        "nested_actual_score",
        "nested_realized_score",
        "candidate_schema",
        "admission_law",
        "admitted_subset",
        "book_roster_mismatch",
        "wrong_world_role",
    ],
)
def test_coherent_contract_mutations_are_rejected(
    monkeypatch: pytest.MonkeyPatch, mutation: str,
) -> None:
    receipt, _, _ = _receipt(monkeypatch)
    mutated = deepcopy(receipt)
    result = mutated["execution_result"]
    surface = result["full_union_surface"]
    if mutation == "non_full_union":
        surface["full_union_only"] = False
    elif mutation == "empty_verification":
        mutated["verification"] = {}
    elif mutation == "nested_actual_score":
        surface["scopes"][0]["books"][0]["training_metrics"][
            "actual_score"
        ] = 250.0
    elif mutation == "nested_realized_score":
        surface["scopes"][0]["books"][0]["training_metrics"][
            "realized_score_micro"
        ] = 250_000_000
    elif mutation == "candidate_schema":
        surface["scopes"][0]["candidate_view"]["schema_version"] = (
            "corpus-fold-candidate-view/future"
        )
    elif mutation == "admission_law":
        surface["scopes"][0]["admission"]["admission_inputs"] = (
            "changed-admission-law"
        )
    elif mutation == "admitted_subset":
        admission = surface["scopes"][0]["admission"]
        admission["admitted_lineup_ids"] = admission["admitted_lineup_ids"][:-1]
        admission["admitted_count"] -= 1
    elif mutation == "book_roster_mismatch":
        roster = surface["scopes"][0]["books"][0]["selected_rosters"][0]
        roster[0] = "different-player"
    else:
        worlds = result["world_artifact_identities"]
        worlds["world_artifact_rx"] = worlds.pop("world_artifact_r4")
        result["world_artifact_identity_set_sha256"] = batch.canonical_sha256(
            worlds
        )
    _rehash_receipt(mutated)
    with pytest.raises(smoke.CorpusR6FullUnionTask0SmokeV1Error):
        smoke.validate_receipt_v1(mutated)


def test_result_output_is_absolute_create_once(tmp_path: Path) -> None:
    value = {"fixed": True}
    relative = Path("relative-result.json")
    with pytest.raises(smoke.CorpusR6FullUnionTask0SmokeV1Error):
        smoke._write_create_once(relative, value)
    output = tmp_path / "result.json"
    smoke._write_create_once(output, value)
    assert output.read_bytes() == batch.canonical_json_bytes(value)
    with pytest.raises(smoke.CorpusR6FullUnionTask0SmokeV1Error):
        smoke._write_create_once(output, value)


def test_production_gate_fails_before_repository_or_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.delenv(smoke.PRODUCTION_ENABLE_ENV, raising=False)
    called = []

    def forbidden() -> object:
        called.append(True)
        raise AssertionError("production dependency constructed")

    with pytest.raises(smoke.CorpusR6FullUnionTask0SmokeV1Error):
        smoke.run_production_smoke_v1(
            result_output=tmp_path / "result.json",
            repository_factory=forbidden,
            backend_factory=forbidden,
        )
    assert called == []


def test_bad_output_preflight_fails_before_repository_or_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv(smoke.PRODUCTION_ENABLE_ENV, "1")
    dangling = tmp_path / "dangling-result.json"
    dangling.symlink_to(tmp_path / "missing-target.json")
    called = []

    def forbidden() -> object:
        called.append(True)
        raise AssertionError("production dependency constructed")

    with pytest.raises(smoke.CorpusR6FullUnionTask0SmokeV1Error):
        smoke.run_production_smoke_v1(
            result_output=dangling,
            repository_factory=forbidden,
            backend_factory=forbidden,
        )
    assert called == []


def test_clean_head_failure_precedes_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv(smoke.PRODUCTION_ENABLE_ENV, "1")
    backend_called = []

    class DirtyRepository:
        @staticmethod
        def require_current_clean_head() -> str:
            raise smoke.CorpusR6FullUnionTask0SmokeV1Error("dirty")

    def forbidden_backend() -> object:
        backend_called.append(True)
        raise AssertionError("backend constructed")

    with pytest.raises(smoke.CorpusR6FullUnionTask0SmokeV1Error, match="dirty"):
        smoke.run_production_smoke_v1(
            result_output=tmp_path / "result.json",
            repository_factory=DirtyRepository,
            backend_factory=forbidden_backend,
        )
    assert backend_called == []


def test_fixed_task0_membership_literal_is_not_derived_from_fixture() -> None:
    assert smoke.FIXED_TASK0_MEMBERSHIP_SHA256 == (
        "ddcb8909d8eb6600345facd5c54fad64f8db3ac15f6b86eb7c348d3802f49105"
    )


def test_production_exactly_forwards_fixed_task0_without_catalog_projection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    receipt, panel, panel_raw = _receipt(monkeypatch)
    del receipt
    monkeypatch.setenv(smoke.PRODUCTION_ENABLE_ENV, "1")
    calls: list[dict[str, object]] = []
    transport = object()

    class Repository:
        @staticmethod
        def require_current_clean_head() -> str:
            return "e" * 40

    class Backend:
        @staticmethod
        def transport() -> object:
            return transport

    def read_exact(identity: object, *, transport: object) -> bytes:
        assert identity == adapter.FIXED_PANEL_IDENTITY
        assert transport is not None
        return panel_raw

    expected = _execution(panel)

    def execute(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return expected

    output = tmp_path / "result.json"
    result = smoke.run_production_smoke_v1(
        result_output=output,
        repository_factory=Repository,
        backend_factory=Backend,
        read_generation_exact=read_exact,
        execute=execute,
    )
    assert output.exists()
    assert result["verification"]["catalog_projection_not_used"] is True
    assert len(calls) == 1
    call = calls[0]
    assert call["validated_panel_index"] == panel
    assert call["accepted_slate_membership"] == panel["accepted_slates"][0]
    assert call["task_acceptance_identity"] == (
        panel["accepted_slates"][0]["task_acceptance_identity"]
    )
    assert call["carrier_identity"] == panel["accepted_slates"][0][
        "carrier_identity"
    ]
    assert call["worlds_per_block"] == rw.WORLDS_PER_BLOCK
    assert call["require_authoritative"] is True
    assert callable(call["read_exact"])
