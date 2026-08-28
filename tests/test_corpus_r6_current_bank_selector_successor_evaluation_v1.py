from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import numpy as np
import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_authority_v1 as authority,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_cloud_v1 as selection_cloud,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_evaluation_v1 as evaluation,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_process_adapter_v1 as adapter,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)


def _rehash(value: dict[str, object], field: str) -> None:
    value[field] = contract.canonical_sha256_v1({
        key: item for key, item in value.items() if key != field
    })


def _identity(uri: str, value: object) -> dict[str, object]:
    raw = contract.canonical_json_bytes_v1(value)
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _tag_identity(uri: str, tag: str) -> dict[str, object]:
    raw = tag.encode("utf-8")
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _candidates(fold: int, *, count: int = 80) -> list[dict[str, object]]:
    profiles = sorted(row[1] for row in contract.PROFILE_IDENTITIES)
    training = [block for block in contract.WORLD_BLOCKS if block != contract.WORLD_BLOCKS[fold]]
    rows = []
    for index in range(count):
        roster = sorted(f"p-{index:03d}-{slot}" for slot in range(9))
        rows.append({
            "lineup_id": f"lineup-{index:03d}",
            "roster_player_ids": roster,
            "training_origin_blocks": list(training),
            "training_source_arms": profiles,
            "training_occurrence_counts_by_block": {block: 1 for block in training},
            "training_source_arms_by_block": {block: profiles for block in training},
            "training_occurrence_count": len(training),
        })
    return rows


def _projection(
    fold: int,
    *,
    later_identity: dict[str, object],
    world_identities: dict[str, dict[str, object]],
) -> dict[str, object]:
    candidates = _candidates(fold)
    lineup_ids = [str(row["lineup_id"]) for row in candidates]
    rosters = [row["roster_player_ids"] for row in candidates]
    heldout = contract.WORLD_BLOCKS[fold]
    training = [block for block in contract.WORLD_BLOCKS if block != heldout]
    body: dict[str, object] = {
        "schema_version": contract.PROJECTION_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "slate_id": "fixture-slate",
        "fit_scope_id": f"holdout-{heldout}",
        "source_task_result_identity": _tag_identity(
            "gs://fixture/source/task.json", "task"
        ),
        "task_result_payload_sha256": "1" * 64,
        "later_source_identity": later_identity,
        "world_artifact_identities": world_identities,
        "fit_candidate_view_sha256": f"{fold + 2:x}" * 64,
        "selection_provenance_sha256": f"{fold + 3:x}" * 64,
        "training_blocks": training,
        "heldout_block": heldout,
        "training_world_columns_sha256": contract.canonical_world_columns_sha256_v1(
            training
        ),
        "candidates": candidates,
        "candidate_lineup_order_sha256": contract.canonical_sha256_v1(lineup_ids),
        "candidate_rosters_sha256": contract.canonical_sha256_v1(rosters),
        "candidate_rows_sha256": contract.canonical_sha256_v1(candidates),
        "expected_training_score_matrix_sha256": "9" * 64,
        "expected_training_score_shape": [
            len(candidates), len(training) * contract.WORLDS_PER_BLOCK,
        ],
        "policy": dict(contract.POLICY_CLAIMS),
    }
    _rehash(body, "projection_sha256")
    return contract.validate_narrow_projection_v1(body)


def _prefixes(
    selected: list[str], candidate_by_id: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    rosters = [candidate_by_id[lineup_id]["roster_player_ids"] for lineup_id in selected]
    rows = []
    for size in successor.PREFIX_SIZES:
        ids = selected[:size]
        prefix_rosters = rosters[:size]
        rows.append({
            "prefix_size": size,
            "selected_lineup_ids_sha256": contract.canonical_sha256_v1(ids),
            "selected_rosters_sha256": contract.canonical_sha256_v1(prefix_rosters),
            "prefix_payload_sha256": contract.canonical_sha256_v1({
                "selected_lineup_ids": ids,
                "selected_rosters": prefix_rosters,
            }),
        })
    return rows


def _fold_receipt(fold: int, projection: dict[str, object]) -> dict[str, object]:
    candidate_by_id = {
        str(row["lineup_id"]): row for row in projection["candidates"]
    }
    sampled = sorted(candidate_by_id)
    views = [
        "U",
        *[
            contract.isolated_view_id_v1(profile_ordinal)
            for profile_ordinal, _, _ in contract.PROFILE_IDENTITIES
        ],
    ]
    presets = successor.frozen_native_preset_registry_v1()
    cells = []
    for view_ordinal, view_id in enumerate(views):
        for preset in presets:
            shift = int(preset["ordinal"])
            selected = sampled[shift:] + sampled[:shift]
            body: dict[str, object] = {
                "schema_version": authority.AUTHORITY_CELL_SCHEMA,
                "replicate": 0,
                "view_ordinal": view_ordinal,
                "view_id": view_id,
                "sampled_lineup_ids": sampled,
                "sampled_lineup_ids_sha256": contract.canonical_sha256_v1(sampled),
                "rank_seed_sha256": f"{view_ordinal + 1:x}" * 64,
                "preset_ordinal": preset["ordinal"],
                "preset_id": preset["preset_id"],
                "preset_sha256": preset["preset_sha256"],
                "adapter_id": preset["adapter_id"],
                "parameters_sha256": preset["parameters_sha256"],
                "executable_fingerprint_sha256": preset[
                    "executable_fingerprint_sha256"
                ],
                "successor_selector_result_sha256": "a" * 64,
                "grouped_result_sha256": "b" * 64,
                "training_score_row_ledger": {},
                "training_score_row_ledger_sha256": contract.canonical_sha256_v1({}),
                "selected_lineup_ids": selected,
                "selected_lineup_ids_sha256": contract.canonical_sha256_v1(selected),
                "selected_rosters_sha256": contract.canonical_sha256_v1([
                    candidate_by_id[lineup_id]["roster_player_ids"]
                    for lineup_id in selected
                ]),
                "prefixes": _prefixes(selected, candidate_by_id),
                "selection_trace": [],
                "selection_trace_sha256": contract.canonical_sha256_v1([]),
                "compact_diagnostics": {},
                "compact_diagnostics_sha256": contract.canonical_sha256_v1({}),
            }
            _rehash(body, "authority_cell_sha256")
            cells.append(body)
    binding: dict[str, object] = {
        "projection_sha256": projection["projection_sha256"],
        "candidate_lineup_order_sha256": projection[
            "candidate_lineup_order_sha256"
        ],
    }
    _rehash(binding, "authority_binding_sha256")
    response: dict[str, object] = {
        "schema_version": authority.AUTHORITY_RESPONSE_SCHEMA,
        "source_ordinal": 0,
        "fold_ordinal": fold,
        "process_ordinal": fold,
        "slate_id": projection["slate_id"],
        "fit_scope_id": projection["fit_scope_id"],
        "training_blocks": projection["training_blocks"],
        "authority_binding": binding,
        "authority_binding_sha256": binding["authority_binding_sha256"],
        "fit_count": len(cells),
        "cells": cells,
        "cell_sha256s": [row["authority_cell_sha256"] for row in cells],
    }
    _rehash(response, "authority_response_sha256")
    receipt: dict[str, object] = {
        "schema_version": adapter.FOLD_RECEIPT_SCHEMA,
        "source_ordinal": 0,
        "fold_ordinal": fold,
        "slate_id": projection["slate_id"],
        "fit_scope_id": projection["fit_scope_id"],
        "heldout_block": projection["heldout_block"],
        "fit_count": len(cells),
        "source_control_receipt_compatible": False,
        "source_control_fit_parity_claimed": False,
        "authority_response": response,
        "authority_response_sha256": response["authority_response_sha256"],
        "cell_sha256s": response["cell_sha256s"],
    }
    _rehash(receipt, "successor_fold_receipt_sha256")
    return receipt


def _fixture(monkeypatch: pytest.MonkeyPatch) -> tuple[
    dict[str, object], dict[str, object], list[dict[str, object]],
    dict[str, object], list[np.ndarray],
]:
    # The laws use the module constant dynamically; eight worlds is enough to
    # test authority/metric mechanics without allocating the 10,000-world panel.
    monkeypatch.setattr(contract, "WORLDS_PER_BLOCK", 8)
    players = sorted(
        f"p-{index:03d}-{slot}" for index in range(80) for slot in range(9)
    )
    later_body = {
        "schema": "fixture-later-source/v1",
        "slates": [{
            "slate_id": "fixture-slate",
            "catalog": [
                {"id": player, "game_id": f"game-{index % 12:02d}"}
                for index, player in enumerate(players)
            ],
        }],
    }
    later_body["slates"][0]["catalog_sha256"] = contract.canonical_sha256_v1(
        later_body["slates"][0]["catalog"]
    )
    later_identity = _identity("gs://fixture/later.json", later_body)
    worlds = {
        f"world_artifact_{block.lower()}": _tag_identity(
            f"gs://fixture/{block}.npz", f"world-{block}"
        )
        for block in contract.WORLD_BLOCKS
    }
    projections = [
        _projection(fold, later_identity=later_identity, world_identities=worlds)
        for fold in range(contract.FOLDS_PER_SLATE)
    ]
    bundle = contract.build_projection_bundle_v1(
        source_ordinal=0, fold_projections=projections
    )
    folds = [_fold_receipt(fold, projection) for fold, projection in enumerate(projections)]
    selection: dict[str, object] = {
        "schema_version": selection_cloud.SLATE_RESULT_SCHEMA,
        "source_ordinal": 0,
        "slate_id": "fixture-slate",
        "fold_count": contract.FOLDS_PER_SLATE,
        "fold_order": list(contract.WORLD_BLOCKS),
        "fold_receipts": folds,
        "fold_receipt_sha256s": [
            row["successor_fold_receipt_sha256"] for row in folds
        ],
        "fit_count": contract.FOLDS_PER_SLATE * adapter.EXACT_FIT_COUNT,
        "source_control_fit_parity_claimed": False,
        "source_control_receipt_compatible": False,
    }
    _rehash(selection, "slate_result_sha256")
    score_matrices = []
    for fold in range(contract.FOLDS_PER_SLATE):
        rows = np.empty((80, contract.WORLDS_PER_BLOCK), dtype=np.float64)
        for index in range(80):
            rows[index] = 180.0 + index / 2.0 + fold + np.arange(8) / 4.0
        rows.flags.writeable = False
        score_matrices.append(rows)
    return selection, bundle, projections, later_body, score_matrices


def _clone_for_source(
    template: dict[str, object], source: int,
) -> dict[str, object]:
    result = deepcopy(template)
    slate_id = f"fixture-slate-{source:02d}"
    result["source_ordinal"] = source
    result["slate_id"] = slate_id
    result["selection_slate_result_identity"] = _tag_identity(
        f"gs://fixture/selection/{source:02d}.json", f"selection-{source}"
    )
    execution_binding = result["execution_binding"]
    execution_binding["source_ordinal"] = source
    execution_binding["slate_id"] = slate_id
    _rehash(execution_binding, "evaluation_execution_binding_sha256")
    result["execution_binding_sha256"] = execution_binding[
        "evaluation_execution_binding_sha256"
    ]
    for fold in result["folds"]:
        fold["source_ordinal"] = source
        fold["slate_id"] = slate_id
        for row in fold["book_metric_rows"]:
            row["source_ordinal"] = source
            row["slate_id"] = slate_id
            pairing = row["pairing_coordinate"]
            pairing["source_ordinal"] = source
            pairing["slate_id"] = slate_id
            _rehash(pairing, "pairing_coordinate_sha256")
            row["pairing_coordinate_sha256"] = pairing[
                "pairing_coordinate_sha256"
            ]
            _rehash(row, "book_metric_row_sha256")
        fold["book_metric_rows_sha256"] = contract.canonical_sha256_v1(
            fold["book_metric_rows"]
        )
        _rehash(fold, "evaluation_fold_sha256")
    result["folds_sha256"] = contract.canonical_sha256_v1(result["folds"])
    _rehash(result, "evaluation_result_sha256")
    return result


def test_successor_evaluator_scores_all_current_books_without_control_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection, bundle, projections, later_body, matrices = _fixture(monkeypatch)
    result = evaluation.build_evaluation_result_v1(
        selection_slate_result=selection,
        selection_slate_result_identity=_identity(
            "gs://fixture/selection.json", selection
        ),
        projection_bundle=bundle,
        projection_bundle_identity=_identity("gs://fixture/projection.json", bundle),
        heldout_fold_input_stream=[
            {
                "fold_ordinal": fold,
                "heldout_artifact_identity": projections[fold][
                    "world_artifact_identities"
                ][f"world_artifact_{contract.WORLD_BLOCKS[fold].lower()}"],
                "heldout_score_matrix": matrices[fold],
            }
            for fold in range(contract.FOLDS_PER_SLATE)
        ],
        later_source_body=later_body,
    )
    assert evaluation.validate_evaluation_result_v1(result) == result
    assert result["entry_budgets"] == [4, 14, 80]
    assert result["paired_control_comparison_ready_entry_budgets"] == [80]
    assert result["book_metric_row_count"] == 5 * 24 * 3
    assert result["source_control_evaluator_invoked"] is False
    first = result["folds"][0]["book_metric_rows"][0]
    assert set(first["decision_metrics"]) == set(evaluation.DECISION_METRIC_STEMS)
    assert first["selector_coordinate"]["selector_family_id"] == (
        "grouped-native-current-bank-selectors-v1"
    )


def test_evaluator_rejects_tampered_book_before_heldout_metric_derivation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection, bundle, projections, later_body, matrices = _fixture(monkeypatch)
    selection["fold_receipts"][0]["authority_response"]["cells"][0][
        "selected_lineup_ids"
    ][0] = "lineup-079"
    _rehash(
        selection["fold_receipts"][0]["authority_response"]["cells"][0],
        "authority_cell_sha256",
    )
    _rehash(selection["fold_receipts"][0]["authority_response"], "authority_response_sha256")
    _rehash(selection["fold_receipts"][0], "successor_fold_receipt_sha256")
    _rehash(selection, "slate_result_sha256")
    with pytest.raises(
        evaluation.CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error,
        match="selection slate result authority|selected lineup authority|cell hash lattice",
    ):
        evaluation.build_evaluation_result_v1(
            selection_slate_result=selection,
            selection_slate_result_identity=_identity(
                "gs://fixture/selection.json", selection
            ),
            projection_bundle=bundle,
            projection_bundle_identity=_identity(
                "gs://fixture/projection.json", bundle
            ),
            heldout_fold_input_stream=[
                {
                    "fold_ordinal": fold,
                    "heldout_artifact_identity": projections[fold][
                        "world_artifact_identities"
                    ][f"world_artifact_{contract.WORLD_BLOCKS[fold].lower()}"],
                    "heldout_score_matrix": matrices[fold],
                }
                for fold in range(contract.FOLDS_PER_SLATE)
            ],
            later_source_body=later_body,
        )


def test_terminal_aggregate_freezes_complete_panel_before_realized_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection, bundle, projections, later_body, matrices = _fixture(monkeypatch)
    runtime = {"runtime_mode": "fixture-successor-evaluator"}
    _rehash(runtime, "runtime_evidence_sha256")
    execution_binding = evaluation.build_evaluation_execution_binding_v1(
        source_ordinal=0,
        slate_id="fixture-slate",
        task_manifest_identity=_tag_identity(
            "gs://fixture/evaluation-manifest.json", "manifest"
        ),
        process_budget_identity=_tag_identity(
            "gs://fixture/evaluation-budget.json", "budget"
        ),
        runtime_evidence=runtime,
    )
    template = evaluation.build_evaluation_result_v1(
        selection_slate_result=selection,
        selection_slate_result_identity=_identity(
            "gs://fixture/selection.json", selection
        ),
        projection_bundle=bundle,
        projection_bundle_identity=_identity("gs://fixture/projection.json", bundle),
        heldout_fold_input_stream=[
            {
                "fold_ordinal": fold,
                "heldout_artifact_identity": projections[fold][
                    "world_artifact_identities"
                ][f"world_artifact_{contract.WORLD_BLOCKS[fold].lower()}"],
                "heldout_score_matrix": matrices[fold],
            }
            for fold in range(contract.FOLDS_PER_SLATE)
        ],
        later_source_body=later_body,
        execution_binding=execution_binding,
    )
    publications = []
    for source in range(contract.PANEL_SLATE_COUNT):
        result = _clone_for_source(template, source)
        publications.append({
            "evaluation_result": result,
            "evaluation_identity": _identity(
                f"gs://fixture/evaluation/{source:02d}.json", result
            ),
        })
    terminal_runtime = {"runtime_mode": "fixture-terminal-aggregate"}
    _rehash(terminal_runtime, "runtime_evidence_sha256")
    terminal_execution = evaluation.build_terminal_execution_binding_v1(
        terminal_manifest_identity=_tag_identity(
            "gs://fixture/terminal-manifest.json", "terminal-manifest"
        ),
        process_budget_identity=_tag_identity(
            "gs://fixture/terminal-budget.json", "terminal-budget"
        ),
        runtime_evidence=terminal_runtime,
    )
    terminal = evaluation.build_terminal_aggregate_v1(
        evaluation_publications=publications,
        execution_binding=terminal_execution,
    )
    assert evaluation.validate_terminal_aggregate_v1(terminal) == terminal
    assert terminal["terminal_before_realized_outcome_read"] is True
    assert terminal["realized_outcome_identity_present"] is False
    assert {row["entry_budget"] for row in terminal["finalists"]} == {80}
    assert all(
        row["complete_cell_count"] == 54 * 5
        for row in terminal["aggregate_metric_rows"]
    )


def test_terminal_rejects_incomplete_panel() -> None:
    with pytest.raises(
        evaluation.CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error,
        match="exact 54-slate panel",
    ):
        evaluation.build_terminal_aggregate_v1(
            evaluation_publications=[], execution_binding={}
        )
