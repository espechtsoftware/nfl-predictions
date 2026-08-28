from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import numpy as np
import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_selection_fold_worker_v1 as worker,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as source_manifest,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_diversity_selector_v1 as diversity,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_rank150_dpp_mode_v1 as mode,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_cloud_v1 as cloud,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_rank150_v1 as rank150,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_authority_v1 as source_authority,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_evaluation_v1 as evaluation,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_process_adapter_v1 as grouped_adapter,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)
from tests import (
    test_corpus_r6_current_bank_selector_successor_process_adapter_v1
    as process_fixtures,
)
from tests import (
    test_corpus_r6_current_bank_selector_successor_evaluation_v1
    as evaluation_fixtures,
)


def _identity(tag: str, value: object | None = None) -> dict[str, object]:
    raw = (
        tag.encode("utf-8")
        if value is None
        else contract.canonical_json_bytes_v1(value)
    )
    return {
        "uri": (
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            f"rank150-dpp-mode-fixture/{tag}.json"
        ),
        "generation": str(800_000 + len(tag)),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _candidates(training_blocks: list[str]) -> list[dict[str, object]]:
    profiles = sorted(row[1] for row in contract.PROFILE_IDENTITIES)
    rows: list[dict[str, object]] = []
    for index in range(160):
        counts = {block: 1 for block in training_blocks}
        rows.append({
            "lineup_id": f"lineup-{index:03d}",
            "roster_player_ids": sorted(
                f"p-{index:03d}-{slot}" for slot in range(9)
            ),
            "training_origin_blocks": list(training_blocks),
            "training_source_arms": profiles,
            "training_occurrence_counts_by_block": counts,
            "training_source_arms_by_block": {
                block: profiles for block in training_blocks
            },
            "training_occurrence_count": len(training_blocks),
        })
    return rows


def _scores() -> np.ndarray:
    world = np.arange(
        4 * source_authority.EXACT_WORLDS_PER_BLOCK, dtype=np.float64
    )
    scores = np.empty((160, world.size), dtype=np.float64, order="C")
    for index in range(160):
        # Keep the fixture below 230 so scenario/DPP fixture construction is
        # fast; production semantics of those selectors have dedicated tests.
        scores[index] = (
            169.0
            + np.remainder(world * (index + 3) + index * 17, 59.0)
            + (index % 5) * 0.125
        )
    return scores


def _capability(scores: np.ndarray) -> dict[str, object]:
    heldout = contract.WORLD_BLOCKS[0]
    training = [block for block in contract.WORLD_BLOCKS if block != heldout]
    candidates = _candidates(training)
    lineup_ids = [str(row["lineup_id"]) for row in candidates]
    matrix_sha = contract._float64_matrix_sha256_v1(
        scores, label="rank150/DPP fixture matrix"
    )
    projection = {
        "projection_sha256": "1" * 64,
        "slate_id": "2025-w18",
        "fit_scope_id": f"holdout-{heldout}",
        "training_blocks": training,
        "heldout_block_label": heldout,
        "training_world_columns_sha256": (
            contract.canonical_world_columns_sha256_v1(training)
        ),
        "candidates": candidates,
        "candidate_lineup_order_sha256": contract.canonical_sha256_v1(
            lineup_ids
        ),
        "candidate_rosters_sha256": contract.canonical_sha256_v1([
            row["roster_player_ids"] for row in candidates
        ]),
        "candidate_rows_sha256": contract.canonical_sha256_v1(candidates),
        "training_score_matrix_sha256": matrix_sha,
        "training_score_shape": list(scores.shape),
    }
    registry = contract._derive_view_registry_fixture_v1(candidates)
    samples = contract._deterministic_equal_count_samples_fixture_v1(
        view_registry=registry,
        slate_id=str(projection["slate_id"]),
        fit_scope_id=str(projection["fit_scope_id"]),
        phase=contract.BROAD_SCREEN_PHASE,
    )
    strategies = contract.frozen_strategies_v1()
    body = {
        "schema_version": worker.MATRIX_CAPABILITY_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": 0,
        "fold_ordinal": 0,
        "process_ordinal": 0,
        "projection_scientific_binding": projection,
        "projection_scientific_binding_sha256": (
            contract.canonical_sha256_v1(projection)
        ),
        "samples": samples,
        "samples_sha256": contract.canonical_sha256_v1(samples),
        "strategies": strategies,
        "strategy_registry_sha256": contract.canonical_sha256_v1(strategies),
        "fit_count_precharge": len(strategies) * mode.EXACT_VIEW_COUNT,
        "nominee_keys": None,
        "matrix_descriptor": worker._matrix_descriptor_v1(
            scores, expected_matrix_sha256=matrix_sha
        ),
        "matrix_bytes_embedded": False,
        "object_store_transport_capability_exposed": False,
        "inherited_local_matrix_fd_exposed": True,
        "object_identity_exposed": False,
        "heldout_artifact_identity_exposed": False,
        "heldout_artifact_body_exposed": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    body["matrix_capability_sha256"] = contract.canonical_sha256_v1(body)
    return worker.validate_matrix_capability_v1(body)


def _runtime() -> dict[str, object]:
    environment = {
        "GOOGLE_CLOUD_PROJECT": "nfl-predictions-503414",
        "CODE_SHA": "a" * 40,
        "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "b" * 64,
        "CLOUD_RUN_JOB": "rank150-dpp-fixture",
        "CLOUD_RUN_EXECUTION": "rank150-dpp-fixture-00001",
        "CLOUD_RUN_TASK_INDEX": "0",
        mode.PROCESS_ORDINAL_ENV: "0",
    }
    return mode.build_runtime_evidence_v1(
        environ=environment,
        observed_command=mode.canonical_matrix_selector_command_v1(),
        process_ordinal=0,
        pid=311,
        parent_pid=101,
    )


def _mock_rank_result(
    *, sampled_ids: list[str], sampled_candidates: list[dict[str, object]],
    sampled_scores: np.ndarray, training_blocks: list[str],
) -> dict[str, object]:
    presets = successor.frozen_native_preset_registry_v1()
    selectors = []
    for preset in presets:
        shift = int(preset["ordinal"])
        selected = sampled_ids[shift:] + sampled_ids[:shift]
        selected = selected[:150]
        selector = {
            "ordinal": preset["ordinal"],
            "preset_id": preset["preset_id"],
            "adapter_id": preset["adapter_id"],
            "ranked_lineup_ids": selected,
        }
        selector["selector_result_sha256"] = contract.canonical_sha256_v1(
            selector
        )
        selectors.append(selector)
    input_binding = {
        "ordered_sampled_lineup_ids_sha256": contract.canonical_sha256_v1(
            sampled_ids
        ),
        "sampled_candidate_rows_sha256": contract.canonical_sha256_v1(
            sampled_candidates
        ),
        "training_score_matrix_sha256": successor._matrix_sha(sampled_scores),
        "training_blocks": training_blocks,
    }
    body = {
        "schema_version": rank150.RESULT_SCHEMA,
        "implementation_sha256": rank150.frozen_rank150_implementation_v1()[
            "implementation_sha256"
        ],
        "input_binding": input_binding,
        "selector_count": 3,
        "selectors": selectors,
        "entry_budgets": [80, 100, 150],
        "ranking_depth": 150,
    }
    body["result_sha256"] = contract.canonical_sha256_v1(body)
    return body


def _mock_dpp_result(
    *, sampled_ids: list[str], sampled_candidates: list[dict[str, object]],
    sampled_scores: np.ndarray, training_blocks: list[str],
) -> dict[str, object]:
    contract_body = diversity.frozen_diversity_selector_contract_v1()
    input_binding = {
        "ordered_sampled_lineup_ids_sha256": contract.canonical_sha256_v1(
            sampled_ids
        ),
        "sampled_candidate_rows_sha256": contract.canonical_sha256_v1(
            sampled_candidates
        ),
        "training_score_matrix_sha256": successor._matrix_sha(sampled_scores),
        "training_blocks": training_blocks,
    }
    body = {
        "schema_version": diversity.RESULT_SCHEMA,
        "strategy_contract": contract_body,
        "input_binding": input_binding,
        "selected_lineup_ids": sampled_ids[9:159],
        "entry_budget": 150,
        "prefix_sizes": [80, 100, 150],
    }
    body["result_sha256"] = contract.canonical_sha256_v1(body)
    return body


@pytest.fixture(scope="module")
def mode_fixture() -> dict[str, object]:
    scores = _scores()
    capability = _capability(scores)
    scores.flags.writeable = False
    return {
        "scores": scores,
        "capability": capability,
        "runtime": _runtime(),
    }


def _install_pure_results(
    monkeypatch: pytest.MonkeyPatch, fixture: dict[str, object],
) -> tuple[list[object], list[object]]:
    rank_calls: list[object] = []
    dpp_calls: list[object] = []

    def run_rank(**kwargs: object) -> dict[str, object]:
        rank_calls.append(kwargs)
        return _mock_rank_result(
            sampled_ids=list(kwargs["sampled_lineup_ids"]),
            sampled_candidates=list(kwargs["candidate_rows"]),
            sampled_scores=kwargs["training_score_matrix"],
            training_blocks=list(kwargs["training_blocks"]),
        )

    def run_dpp(**kwargs: object) -> dict[str, object]:
        dpp_calls.append(kwargs)
        return _mock_dpp_result(
            sampled_ids=list(kwargs["sampled_lineup_ids"]),
            sampled_candidates=list(kwargs["candidate_rows"]),
            sampled_scores=kwargs["training_score_matrix"],
            training_blocks=list(kwargs["training_blocks"]),
        )

    monkeypatch.setattr(rank150, "run_exact_rank150_continuation_v1", run_rank)
    monkeypatch.setattr(
        diversity, "run_effective_independent_shots_selector_v1", run_dpp
    )
    return rank_calls, dpp_calls


def _evaluation_receipt(
    *, fold: int, projection: dict[str, object],
) -> dict[str, object]:
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
    cells = []
    for view_ordinal, view_id in enumerate(views):
        for selector_ordinal in range(4):
            rotated = sampled[selector_ordinal:] + sampled[:selector_ordinal]
            selected = rotated[:150]
            coordinate = mode._selector_coordinate_v1(
                ordinal=selector_ordinal,
                selector_family_id="rank150-dpp-evaluation-fixture",
                selector_id=f"selector-{selector_ordinal}",
                selector_semantics_sha256=f"{selector_ordinal + 1:x}" * 64,
                adapter_id=f"adapter-{selector_ordinal}",
                executable_fingerprint_sha256=f"{selector_ordinal + 5:x}" * 64,
            )
            cell = {
                "schema_version": mode.AUTHORITY_CELL_SCHEMA,
                "replicate": 0,
                "view_ordinal": view_ordinal,
                "view_id": view_id,
                "sampled_lineup_ids": sampled,
                "sampled_lineup_ids_sha256": contract.canonical_sha256_v1(
                    sampled
                ),
                "selector_coordinate": coordinate,
                "selector_coordinate_sha256": coordinate[
                    "selector_coordinate_sha256"
                ],
                "selected_lineup_ids": selected,
                "selected_lineup_ids_sha256": contract.canonical_sha256_v1(
                    selected
                ),
                "selected_rosters_sha256": contract.canonical_sha256_v1([
                    candidate_by_id[lineup_id]["roster_player_ids"]
                    for lineup_id in selected
                ]),
                "prefixes": mode._prefixes_v1(
                    selected_ids=selected, candidate_by_id=candidate_by_id
                ),
            }
            cell["authority_cell_sha256"] = contract.canonical_sha256_v1(cell)
            cells.append(cell)
    binding = {
        "projection_sha256": projection["projection_sha256"],
        "candidate_lineup_order_sha256": projection[
            "candidate_lineup_order_sha256"
        ],
    }
    binding["authority_binding_sha256"] = contract.canonical_sha256_v1(
        binding
    )
    response = {
        "schema_version": mode.AUTHORITY_RESPONSE_SCHEMA,
        "source_ordinal": 0,
        "fold_ordinal": fold,
        "slate_id": projection["slate_id"],
        "fit_scope_id": projection["fit_scope_id"],
        "authority_binding": binding,
        "fit_count": 32,
        "cells": cells,
        "cell_sha256s": [row["authority_cell_sha256"] for row in cells],
    }
    response["authority_response_sha256"] = contract.canonical_sha256_v1(
        response
    )
    receipt = {
        "schema_version": mode.FOLD_RECEIPT_SCHEMA,
        "source_ordinal": 0,
        "fold_ordinal": fold,
        "slate_id": projection["slate_id"],
        "heldout_block": projection["heldout_block"],
        "fit_count": 32,
        "source_control_fit_parity_claimed": False,
        "source_control_receipt_compatible": False,
        "grouped_24_fit_receipt_compatible": False,
        "authority_response": response,
        "cell_sha256s": response["cell_sha256s"],
    }
    receipt["rank150_dpp_fold_receipt_sha256"] = (
        contract.canonical_sha256_v1(receipt)
    )
    return receipt


def test_mode_is_distinct_exact_32_fit_cloud_process_contract() -> None:
    descriptor = mode.build_process_mode_v1()
    assert descriptor["mode_id"] == mode.MODE_ID
    assert descriptor["view_count_per_fold"] == 8
    assert descriptor["selector_count_per_view"] == 4
    assert descriptor["fit_count_per_fold"] == 32
    assert descriptor["fold_count_per_slate"] == 5
    assert descriptor["fit_count_per_slate"] == 160
    assert descriptor["entry_budgets"] == [80, 100, 150]
    assert descriptor["grouped_24_fit_mode_compatible"] is False
    assert mode.RUNTIME_MODE != "grouped-successor-matrix-selector"
    assert mode.FOLD_RECEIPT_SCHEMA != grouped_adapter.FOLD_RECEIPT_SCHEMA


def test_cloud_manifest_schema_smoke_is_distinct_and_exact_32_fit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_tasks = [{
        "task_index": index,
        "source_ordinal": index,
        "task_binding_sha256": f"{index + 1:064x}",
        "task_science_binding_sha256": f"{index + 101:064x}",
        "request_sha256": f"{index + 201:064x}",
    } for index in range(cloud.TASK_COUNT)]
    source = {
        "layer_id": "broad-selection-receipt",
        "phase": contract.BROAD_SCREEN_PHASE,
        "task_count": cloud.TASK_COUNT,
        "task_bindings": source_tasks,
    }
    source["task_manifest_sha256"] = contract.canonical_sha256_v1(source)
    monkeypatch.setattr(
        source_manifest, "validate_task_manifest_v1", lambda value: dict(value)
    )
    run_identity = _identity("rank150-dpp-run-authorization")
    bootstrap = cloud.build_bootstrap_v1(
        code_commit="a" * 40,
        image_digest="sha256:" + "b" * 64,
        run_authorization_identity=run_identity,
        selector_process_mode=cloud.RANK150_DPP_SELECTOR_MODE,
    )
    fold_budget_ids = [
        _identity(f"smoke-rank150-dpp-fold-{fold}")
        for fold in range(contract.FOLDS_PER_SLATE)
    ]
    slate_budget = cloud.build_slate_process_budget_v1(
        source_ordinal=0,
        slate_id="2025-w01",
        source_task_manifest_identity=_identity("smoke-source-manifest"),
        bootstrap_identity=_identity("smoke-bootstrap"),
        run_authorization_identity=run_identity,
        design_identity=_identity("smoke-design"),
        topology_identity=_identity("smoke-topology"),
        projection_bundle_identity=_identity("smoke-projection-bundle"),
        source_process_budget_identities=[
            _identity(f"smoke-source-fold-{fold}")
            for fold in range(contract.FOLDS_PER_SLATE)
        ],
        successor_process_budget_identities=fold_budget_ids,
        scientific_read_identities=[
            _identity("smoke-later"),
            *[
                _identity(f"smoke-world-{block}")
                for block in contract.WORLD_BLOCKS
            ],
        ],
        result_uri=(
            contract.OUTPUT_NAMESPACE
            + "rank150-dpp-cloud-fixture/results/source-000.json"
        ),
        selector_process_mode=cloud.RANK150_DPP_SELECTOR_MODE,
    )
    assert slate_budget["schema_version"] == (
        cloud.RANK150_DPP_SLATE_PROCESS_BUDGET_SCHEMA
    )
    assert slate_budget["fit_precharge_per_fold"] == 32
    assert slate_budget["compute_fit_precharge"] == 160
    assert cloud.validate_slate_process_budget_v1(slate_budget) == slate_budget
    bindings = []
    for index, source_task in enumerate(source_tasks):
        bindings.append(cloud.build_task_binding_v1(
            source_ordinal=index,
            slate_id=f"2025-w{index + 1:02d}",
            source_task_binding=source_task,
            projection_bundle_identity=_identity(f"bundle-{index:03d}"),
            source_process_budget_identities=[
                _identity(f"source-{index:03d}-fold-{fold}")
                for fold in range(contract.FOLDS_PER_SLATE)
            ],
            successor_process_budget_identities=[
                _identity(f"rank150-dpp-{index:03d}-fold-{fold}")
                for fold in range(contract.FOLDS_PER_SLATE)
            ],
            slate_process_budget_identity=_identity(
                f"rank150-dpp-slate-{index:03d}"
            ),
            result_uri=(
                contract.OUTPUT_NAMESPACE
                + "rank150-dpp-cloud-fixture/"
                + f"results/source-{index:03d}.json"
            ),
            selector_process_mode=cloud.RANK150_DPP_SELECTOR_MODE,
        ))
    source_identity = _identity("source-manifest", source)
    manifest = cloud.build_task_manifest_v1(
        output_prefix=(
            contract.OUTPUT_NAMESPACE + "rank150-dpp-cloud-fixture/"
        ),
        source_task_manifest=source,
        source_task_manifest_identity=source_identity,
        bootstrap=bootstrap,
        bootstrap_identity=_identity("rank150-dpp-bootstrap", bootstrap),
        run_authorization_identity=run_identity,
        task_bindings=bindings,
        selector_process_mode=cloud.RANK150_DPP_SELECTOR_MODE,
    )
    assert manifest["schema_version"] == cloud.RANK150_DPP_TASK_MANIFEST_SCHEMA
    assert manifest["selector_process_mode"] == mode.MODE_ID
    assert manifest["fit_count_precharge_per_task"] == 160
    assert manifest["fit_count_precharge_total"] == 8_640
    assert manifest["matrix_process_spec"]["process_role"] == mode.PROCESS_ROLE
    assert manifest["matrix_process_spec"]["command"] == (
        mode.canonical_matrix_selector_command_v1()
    )
    assert cloud.validate_task_manifest_v1(
        manifest, source_task_manifest=source, bootstrap=bootstrap
    ) == manifest
    configuration = cloud.build_cloud_run_job_configuration_v1(
        task_manifest=manifest,
        task_manifest_identity=_identity("rank150-dpp-manifest", manifest),
        reused_job_name="rank150-dpp-fixture",
    )
    assert configuration["selector_process_mode"] == mode.MODE_ID
    assert configuration["container_environment"][cloud.SELECTOR_MODE_ENV] == (
        mode.MODE_ID
    )
    runtime = cloud.build_dispatcher_runtime_evidence_v1(
        environ={
            cloud.ENABLE_ENV: "1",
            cloud.SELECTOR_MODE_ENV: mode.MODE_ID,
            "GOOGLE_CLOUD_PROJECT": cloud.FIXED_GCP_PROJECT,
            "CODE_SHA": "a" * 40,
            "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "b" * 64,
            "CLOUD_RUN_JOB": "rank150-dpp-fixture",
            "CLOUD_RUN_EXECUTION": "rank150-dpp-fixture-00001",
            "CLOUD_RUN_TASK_INDEX": "0",
            "CLOUD_RUN_TASK_COUNT": str(cloud.TASK_COUNT),
            "CLOUD_RUN_TASK_ATTEMPT": "0",
        },
        observed_command=list(cloud.DISPATCHER_COMMAND),
        pid=411,
        parent_pid=101,
    )
    assert runtime["schema_version"] == (
        cloud.RANK150_DPP_DISPATCHER_RUNTIME_SCHEMA
    )
    assert runtime["selector_process_mode"] == mode.MODE_ID
    assert cloud.validate_dispatcher_runtime_evidence_v1(runtime) == runtime


def test_authority_executes_eight_rank_and_eight_dpp_calls_for_32_cells(
    mode_fixture: dict[str, object], monkeypatch: pytest.MonkeyPatch,
) -> None:
    rank_calls, dpp_calls = _install_pure_results(monkeypatch, mode_fixture)
    response = mode.run_authority_bound_rank150_dpp_v1(
        matrix_capability=mode_fixture["capability"],
        training_score_matrix=mode_fixture["scores"],
        runtime_evidence=mode_fixture["runtime"],
    )
    assert len(rank_calls) == len(dpp_calls) == 8
    assert response["view_count"] == 8
    assert response["selector_count_per_view"] == 4
    assert response["fit_count"] == 32
    assert len(response["cells"]) == 32
    assert [
        (
            row["view_ordinal"],
            row["selector_coordinate"]["selector_ordinal"],
        )
        for row in response["cells"]
    ] == [(view, selector) for view in range(8) for selector in range(4)]
    assert all(len(row["selected_lineup_ids"]) == 150 for row in response["cells"])
    assert all(
        [prefix["prefix_size"] for prefix in row["prefixes"]]
        == [80, 100, 150]
        for row in response["cells"]
    )
    assert all(row["schema_version"] == mode.AUTHORITY_CELL_SCHEMA for row in response["cells"])


def test_exact_32_budget_request_receipt_and_successor_evaluator_seam(
    mode_fixture: dict[str, object], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_pure_results(monkeypatch, mode_fixture)
    capability = mode_fixture["capability"]
    source_budget = process_fixtures._source_process_budget(capability)
    source_identity = _identity("source-budget", source_budget)
    budget = mode.compile_process_budget_v1(
        source_process_budget=source_budget,
        source_process_budget_identity=source_identity,
        matrix_capability=capability,
    )
    budget_identity = _identity("mode-budget", budget)
    assert budget["compute_fit_precharge"] == 32
    assert budget["source_control_fit_precharge"] == 64
    assert budget["source_control_fit_parity_claimed"] is False
    response = mode.run_authority_bound_rank150_dpp_v1(
        matrix_capability=capability,
        training_score_matrix=mode_fixture["scores"],
        runtime_evidence=mode_fixture["runtime"],
    )
    request = mode.build_matrix_child_request_v1(
        source_process_budget=source_budget,
        source_process_budget_identity=source_identity,
        process_budget=budget,
        process_budget_identity=budget_identity,
        matrix_capability=capability,
        launch_intent_identity=_identity("launch"),
    )
    assert mode.validate_matrix_child_request_v1(request) == request
    routed_request = cloud.build_matrix_child_request_v1(
        source_process_budget=source_budget,
        source_process_budget_identity=source_identity,
        successor_process_budget=budget,
        successor_process_budget_identity=budget_identity,
        matrix_capability=capability,
        launch_intent_identity=_identity("launch"),
        selector_process_mode=cloud.RANK150_DPP_SELECTOR_MODE,
    )
    assert routed_request == request
    assert cloud.validate_matrix_child_request_v1(routed_request) == request
    receipt = mode.build_fold_receipt_v1(
        process_budget=budget,
        process_budget_identity=budget_identity,
        source_process_budget=source_budget,
        source_process_budget_identity=source_identity,
        matrix_capability=capability,
        runtime_evidence=mode_fixture["runtime"],
        authority_response=response,
        launch_intent_identity=_identity("launch"),
    )
    assert receipt["fit_count"] == 32
    assert receipt["entry_budgets"] == [80, 100, 150]
    assert receipt["grouped_24_fit_receipt_compatible"] is False
    retained, cells = evaluation._validate_fold_receipt_v1(
        receipt,
        source_ordinal=0,
        fold_ordinal=0,
        projection=capability["projection_scientific_binding"],
    )
    assert retained == receipt
    assert len(cells) == 32
    assert evaluation._selector_coordinate_v1(cells[-1])[
        "selector_id"
    ] == diversity.STRATEGY_ID

    tampered = deepcopy(receipt)
    tampered["fit_count"] = 24
    tampered["rank150_dpp_fold_receipt_sha256"] = (
        contract.canonical_sha256_v1({
            key: row for key, row in tampered.items()
            if key != "rank150_dpp_fold_receipt_sha256"
        })
    )
    with pytest.raises(
        evaluation.CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error,
        match="evaluation fold authority differs",
    ):
        evaluation._validate_fold_receipt_v1(
            tampered,
            source_ordinal=0,
            fold_ordinal=0,
            projection=capability["projection_scientific_binding"],
        )


def test_runtime_rejects_grouped_24_fit_command() -> None:
    environment = {
        "GOOGLE_CLOUD_PROJECT": "nfl-predictions-503414",
        "CODE_SHA": "a" * 40,
        "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "b" * 64,
        "CLOUD_RUN_JOB": "rank150-dpp-fixture",
        "CLOUD_RUN_EXECUTION": "rank150-dpp-fixture-00001",
        "CLOUD_RUN_TASK_INDEX": "0",
        mode.PROCESS_ORDINAL_ENV: "0",
    }
    with pytest.raises(
        mode.CorpusR6CurrentBankSelectorRank150DppModeV1Error,
        match="runtime environment/process binding differs",
    ):
        mode.build_runtime_evidence_v1(
            environ=environment,
            observed_command=[
                mode.PYTHON_EXECUTABLE,
                "/app/scripts/run_corpus_r6_current_bank_selector_successor_v1.py",
                "matrix-selector",
            ],
            process_ordinal=0,
            pid=311,
            parent_pid=101,
        )


def test_existing_successor_evaluator_scores_all_32_exact_books(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(contract, "WORLDS_PER_BLOCK", 8)
    original_candidates = evaluation_fixtures._candidates
    monkeypatch.setattr(
        evaluation_fixtures,
        "_candidates",
        lambda fold: original_candidates(fold, count=160),
    )
    players = sorted(
        f"p-{index:03d}-{slot}" for index in range(160) for slot in range(9)
    )
    later_body = {
        "schema": "rank150-dpp-evaluation-fixture/v1",
        "slates": [{
            "slate_id": "fixture-slate",
            "catalog": [
                {"id": player, "game_id": f"game-{index % 12:02d}"}
                for index, player in enumerate(players)
            ],
        }],
    }
    later_body["slates"][0]["catalog_sha256"] = (
        contract.canonical_sha256_v1(later_body["slates"][0]["catalog"])
    )
    later_identity = _identity("later-source", later_body)
    world_identities = {
        f"world_artifact_{block.lower()}": _identity(f"world-{block}")
        for block in contract.WORLD_BLOCKS
    }
    projection = evaluation_fixtures._projection(
        0,
        later_identity=later_identity,
        world_identities=world_identities,
    )
    receipt = _evaluation_receipt(fold=0, projection=projection)
    heldout = np.empty((160, 8), dtype=np.float64)
    for index in range(160):
        heldout[index] = 180.0 + index / 3.0 + np.arange(8) / 5.0
    heldout.flags.writeable = False
    result = evaluation.build_evaluation_fold_v1(
        source_ordinal=0,
        fold_ordinal=0,
        projection=projection,
        selection_fold_receipt=receipt,
        heldout_artifact_identity=world_identities["world_artifact_r0"],
        heldout_score_matrix=heldout,
        later_source_body=later_body,
    )
    assert result["selection_cell_count"] == 32
    assert result["entry_budgets"] == [80, 100, 150]
    assert result["book_metric_row_count"] == 32 * 3
    assert {
        row["entry_budget"] for row in result["book_metric_rows"]
    } == {80, 100, 150}
    assert all(
        row["selector_coordinate"]["selector_family_id"]
        == "rank150-dpp-evaluation-fixture"
        for row in result["book_metric_rows"]
    )
