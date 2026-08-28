from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import ast
from pathlib import Path

import numpy as np
import pytest

from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_contract_v1 as contract


def _fake_identity(uri: str, label: str, *, generation: str = "1") -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(label.encode("utf-8")).hexdigest(),
        "bytes": len(label.encode("utf-8")) or 1,
    }


def _body_identity(uri: str, value: object) -> dict[str, object]:
    raw = contract.canonical_json_bytes_v1(value)
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _rehash(value: dict[str, object], field: str) -> None:
    value[field] = contract.canonical_sha256_v1({
        key: item for key, item in value.items() if key != field
    })


def _process_specs() -> list[dict[str, object]]:
    rows = []
    for role in contract.PROCESS_ROLES:
        components = (
            ("artifact-broker", "matrix-selector")
            if role.endswith("fold-selector")
            else ("main",)
        )
        rows.append({
            "process_role": role,
            "process_chain": [
                {
                    "component_role": component,
                    "command": ["python", f"scripts/{role}-{component}.py"],
                    "entrypoint_path": f"scripts/{role}-{component}.py",
                    "entrypoint_sha256": sha256(
                        f"{role}-{component}".encode("utf-8")
                    ).hexdigest(),
                }
                for component in components
            ],
        })
    return rows


def _candidates(count: int = 80) -> list[dict[str, object]]:
    profiles = sorted(profile_id for _, profile_id, _ in contract.PROFILE_IDENTITIES)
    rows: list[dict[str, object]] = []
    for index in range(count):
        roster_index = 0 if index == 1 else index
        roster = [f"p-{roster_index:03d}-{slot}" for slot in range(9)]
        training = [block for block in contract.WORLD_BLOCKS if block != "R0"]
        rows.append({
            "lineup_id": f"lineup-{index:03d}",
            "roster_player_ids": roster,
            "training_origin_blocks": training,
            "training_source_arms": profiles,
            "training_occurrence_counts_by_block": {block: 1 for block in training},
            "training_source_arms_by_block": {block: profiles for block in training},
            "training_occurrence_count": 4,
        })
    return rows


def _eligible_fixture_rows() -> list[dict[str, object]]:
    profiles = sorted(profile_id for _, profile_id, _ in contract.PROFILE_IDENTITIES)
    rows = [
        {
            "lineup_id": f"lineup-{index:03d}",
            "training_source_arms": profiles,
        }
        for index in range(80)
    ]
    rows.extend([
        {"lineup_id": "lineup-080", "training_source_arms": [profiles[0]]},
        {"lineup_id": "lineup-081", "training_source_arms": [profiles[1]]},
        {"lineup_id": "lineup-082", "training_source_arms": [profiles[2]]},
        {"lineup_id": "lineup-083", "training_source_arms": [profiles[3]]},
    ])
    return rows


def _projection(
    fold_ordinal: int,
    *,
    candidates: list[dict[str, object]],
    score_matrix_sha256: str,
    later_source_identity: dict[str, object],
) -> dict[str, object]:
    heldout = contract.WORLD_BLOCKS[fold_ordinal]
    training = [block for block in contract.WORLD_BLOCKS if block != heldout]
    profile_ids = sorted(profile_id for _, profile_id, _ in contract.PROFILE_IDENTITIES)
    normalized_candidates = []
    for source in candidates:
        row = deepcopy(source)
        row["training_origin_blocks"] = list(training)
        row["training_occurrence_counts_by_block"] = {block: 1 for block in training}
        row["training_source_arms_by_block"] = {block: profile_ids for block in training}
        normalized_candidates.append(row)
    lineup_ids = [str(row["lineup_id"]) for row in normalized_candidates]
    rosters = [row["roster_player_ids"] for row in normalized_candidates]
    body = {
        "schema_version": contract.PROJECTION_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "slate_id": "fixture-slate",
        "fit_scope_id": f"holdout-{heldout}",
        "source_task_result_identity": _fake_identity(
            "gs://fixture/task-results/fixture-slate.json", "task-result"
        ),
        "task_result_payload_sha256": "1" * 64,
        "later_source_identity": later_source_identity,
        "world_artifact_identities": {
            f"world_artifact_{block.lower()}": _fake_identity(
                f"gs://fixture/worlds/fixture-slate/{block}.npz", f"world-{block}"
            )
            for block in contract.WORLD_BLOCKS
        },
        "fit_candidate_view_sha256": f"{fold_ordinal + 2:x}" * 64,
        "selection_provenance_sha256": f"{fold_ordinal + 3:x}" * 64,
        "training_blocks": training,
        "heldout_block": heldout,
        "training_world_columns_sha256": (
            contract.canonical_world_columns_sha256_v1(training)
        ),
        "candidates": normalized_candidates,
        "candidate_lineup_order_sha256": contract.canonical_sha256_v1(lineup_ids),
        "candidate_rosters_sha256": contract.canonical_sha256_v1(rosters),
        "candidate_rows_sha256": contract.canonical_sha256_v1(normalized_candidates),
        "expected_training_score_matrix_sha256": score_matrix_sha256,
        "expected_training_score_shape": [len(normalized_candidates), 40_000],
        "policy": dict(contract.POLICY_CLAIMS),
    }
    body["projection_sha256"] = contract.canonical_sha256_v1(body)
    return body


def _selection_cell(
    *,
    projection: dict[str, object],
    sample: dict[str, object],
    strategy: dict[str, object],
    full_ledger: dict[str, object],
    replicate: int = 0,
) -> dict[str, object]:
    selected_ids = list(sample["sampled_lineup_ids"][:80])
    candidate_by_id = {
        str(row["lineup_id"]): row for row in projection["candidates"]
    }
    roster_by_id = {
        lineup_id: list(candidate_by_id[lineup_id]["roster_player_ids"])
        for lineup_id in selected_ids
    }
    sampled_ledger = contract._sampled_score_row_ledger_from_full_v1(
        full_ledger, sample["sampled_lineup_ids"]
    )
    selection_trace = contract._selection_trace_binding_v1(
        selected_lineup_ids=selected_ids,
        sampled_lineup_ids=sample["sampled_lineup_ids"],
        sampled_score_row_ledger=sampled_ledger,
    )
    body = {
        "replicate": replicate,
        "view_id": sample["view_id"],
        "sampled_lineup_ids": list(sample["sampled_lineup_ids"]),
        "sampled_lineup_ids_sha256": sample["sampled_lineup_ids_sha256"],
        "rank_seed_sha256": sample["seed_material_sha256"],
        "strategy_ordinal": strategy["ordinal"],
        "strategy_id": strategy["strategy_id"],
        "strategy_sha256": strategy["strategy_sha256"],
        "executable_fingerprint_sha256": (
            contract.strategy_executable_fingerprint_v1(strategy)
        ),
        "training_score_row_ledger": sampled_ledger,
        "selected_lineup_ids": selected_ids,
        "selected_lineup_ids_sha256": contract.canonical_sha256_v1(selected_ids),
        "selected_rosters_sha256": contract.canonical_sha256_v1([
            roster_by_id[lineup_id] for lineup_id in selected_ids
        ]),
        "prefixes": contract._selection_prefixes_v1(selected_ids, roster_by_id),
        "selection_trace": selection_trace,
        "selection_trace_sha256": contract.canonical_sha256_v1(selection_trace),
    }
    body["selection_cell_sha256"] = contract.canonical_sha256_v1(body)
    return body


def _metrics(
    expected: int, p200: int, p220: int, p230: int, participation: int,
    *, denominator: int = 1_000_000,
) -> dict[str, int]:
    values = {
        "mean_heldout_expected_book_max_micro": expected,
        "mean_heldout_p_max_gt_200": p200,
        "mean_heldout_p_max_gt_220": p220,
        "mean_heldout_p_max_gt_230": p230,
        "mean_heldout_participation_ratio_gt_220_micro": participation,
    }
    return {
        key: part
        for stem, value in values.items()
        for key, part in (
            (f"{stem}_numerator", value),
            (f"{stem}_denominator", denominator),
        )
    }


def _metric_grid(*, replicate_count: int = 1) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for strategy_ordinal, strategy_id, _ in contract.STRATEGY_IDENTITIES:
        rows.append({
            "view_id": "U", "profile_id": "all-profiles", "profile_ordinal": -1,
            "strategy_id": strategy_id, "strategy_ordinal": strategy_ordinal,
            "prefix_size": 80,
            **_metrics(160_000_000 + strategy_ordinal, 100_000, 20_000, 5_000, 20_000_000),
            "complete_cell_count": 270,
            "subsample_replicate_count": replicate_count,
        })
    for profile_ordinal, profile_id, _ in contract.PROFILE_IDENTITIES:
        for strategy_ordinal, strategy_id, _ in contract.STRATEGY_IDENTITIES:
            rows.append({
                "view_id": contract.isolated_view_id_v1(profile_ordinal),
                "profile_id": profile_id, "profile_ordinal": profile_ordinal,
                "strategy_id": strategy_id, "strategy_ordinal": strategy_ordinal,
                "prefix_size": 80,
                **_metrics(150_000_000, 100_000, 20_000, 5_000, 20_000_000),
                "complete_cell_count": 270,
                "subsample_replicate_count": replicate_count,
            })
    return rows


def _layer(topology: dict[str, object], role: str) -> dict[str, object]:
    uris = [row["uri"] for row in topology["objects"] if row["role"] == role]
    return contract.build_layer_binding_v1(
        role=role,
        entries=[
            {
                "source_ordinal": index,
                "slate_id": f"slate-{53 - index:02d}",
                "identity": _fake_identity(str(uri), f"{role}-{index}"),
            }
            for index, uri in enumerate(uris)
        ],
    )


def _later_source_fixture(
    candidates: list[dict[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    player_ids = sorted({
        player_id
        for candidate in candidates
        for player_id in candidate["roster_player_ids"]
    })
    catalog = [
        {"id": player_id, "game_id": f"game-{index % 8:02d}"}
        for index, player_id in enumerate(player_ids)
    ]
    body = {
        "schema": "fixture-later-source/v1",
        "slates": [{
            "slate_id": "fixture-slate",
            "catalog": catalog,
            "catalog_sha256": contract.canonical_sha256_v1(catalog),
        }],
    }
    identity = _body_identity(
        "gs://fixture/later-source/fixture-slate.json", body
    )
    return body, identity


def _clone_evaluation_publications(
    *, template: dict[str, object], topology: dict[str, object], phase: str,
    projection_bodies: list[dict[str, object]],
    selection_bodies: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    selection_role = (
        "broad-selection-receipt"
        if phase == contract.BROAD_SCREEN_PHASE
        else "confirmation-selection-receipt"
    )
    evaluation_role = (
        "broad-evaluation-result"
        if phase == contract.BROAD_SCREEN_PHASE
        else "confirmation-evaluation-result"
    )
    projection_uris = [
        row["uri"] for row in topology["objects"] if row["role"] == "projection"
    ]
    selection_uris = [
        row["uri"]
        for row in topology["objects"]
        if row["role"] == selection_role
    ]
    evaluation_uris = [
        row["uri"]
        for row in topology["objects"]
        if row["role"] == evaluation_role
    ]
    projection_identities = [
        _body_identity(str(uri), body)
        for uri, body in zip(projection_uris, projection_bodies, strict=True)
    ]
    selection_identities = [
        _body_identity(str(uri), body)
        for uri, body in zip(selection_uris, selection_bodies, strict=True)
    ]
    publications = []
    for source in range(contract.PANEL_SLATE_COUNT):
        body = dict(template)
        body["phase"] = phase
        body["source_ordinal"] = source
        body["slate_id"] = (
            "fixture-slate" if source == 0 else f"2024-w{source + 1:02d}"
        )
        body["projection_bundle_identity"] = projection_identities[source]
        body["projection_bundle_sha256"] = sha256(
            f"projection-{source}".encode("utf-8")
        ).hexdigest()
        body["selection_receipt_identity"] = selection_identities[source]
        body["selection_receipt_sha256"] = sha256(
            f"{selection_role}-{source}".encode("utf-8")
        ).hexdigest()
        body["child_execution_evidence_sha256s"] = [
            sha256(
                f"{phase}-{source}-child-{fold}".encode("utf-8")
            ).hexdigest()
            for fold in range(contract.FOLDS_PER_SLATE)
        ]
        body["child_execution_evidence_set_sha256"] = sha256(
            f"{phase}-{source}-child-set".encode("utf-8")
        ).hexdigest()
        body["publication_role"] = evaluation_role
        _rehash(body, "evaluation_result_sha256")
        identity = _body_identity(str(evaluation_uris[source]), body)
        publications.append({
            "source_ordinal": source,
            "body": body,
            "identity": identity,
        })
    return publications, projection_identities, selection_identities


def _confirmation_template(
    broad: dict[str, object], nomination: dict[str, object],
) -> dict[str, object]:
    nominee_keys = [
        (row["view_id"], row["strategy_id"])
        for row in nomination["nominees"]
    ]
    folds = []
    for fold in broad["folds"]:
        broad_rows = {
            (row["view_id"], row["strategy_id"], row["prefix_size"]): row
            for row in fold["book_metric_rows"]
        }
        rows = []
        cell_ordinal = 0
        for replicate in range(contract.SUBSAMPLE_REPLICATES):
            for view_id, strategy_id in nominee_keys:
                for prefix_ordinal, prefix_size in enumerate(contract.PREFIX_SIZES):
                    row = dict(
                        broad_rows[(view_id, strategy_id, prefix_size)]
                    )
                    row["cell_ordinal"] = cell_ordinal
                    row["prefix_ordinal"] = prefix_ordinal
                    row["replicate"] = replicate
                    row["selection_cell_sha256"] = sha256(
                        f"confirmation-{fold['fold_ordinal']}-{replicate}-"
                        f"{view_id}-{strategy_id}".encode("utf-8")
                    ).hexdigest()
                    _rehash(row, "book_metric_row_sha256")
                    rows.append(row)
                cell_ordinal += 1
        retained = dict(fold)
        retained["selection_cell_count"] = len(nominee_keys) * contract.SUBSAMPLE_REPLICATES
        retained["book_metric_row_count"] = len(rows)
        retained["book_metric_rows"] = rows
        retained["book_metric_rows_sha256"] = contract.canonical_sha256_v1(rows)
        _rehash(retained, "evaluation_fold_sha256")
        folds.append(retained)
    result = dict(broad)
    result["phase"] = contract.CONFIRMATION_PHASE
    result["folds"] = folds
    result["folds_sha256"] = contract.canonical_sha256_v1(folds)
    result["book_metric_row_count"] = sum(
        fold["book_metric_row_count"] for fold in folds
    )
    result["publication_role"] = "confirmation-evaluation-result"
    _rehash(result, "evaluation_result_sha256")
    return result


def _broad_publication_template(
    derived: dict[str, object],
) -> dict[str, object]:
    """Give the primary control a nonzero P200 so only fixed controls nominate."""
    folds = []
    for fold in derived["folds"]:
        rows = []
        for original in fold["book_metric_rows"]:
            if (
                original["view_id"] == contract.PRIMARY_BASELINE_VIEW_ID
                and original["strategy_id"]
                == contract.PRIMARY_BASELINE_STRATEGY_ID
                and original["prefix_size"] == 80
            ):
                row = dict(original)
                tails = [dict(value) for value in original["tail_metrics"]]
                p200 = next(value for value in tails if value["metric_id"] == "gt_200")
                p200["tail_lineup_count"] = 1
                p200["tail_event_count"] = 1_000
                p200["tail_lineups_per_1000_micro"] = 12_500_000
                p200["tail_event_probability_numerator"] = 1_000
                p200["tail_event_probability_micro"] = 1_250
                p200["book_max_event_count"] = 1_000
                p200["book_max_event_probability_micro"] = 100_000
                row["tail_metrics"] = tails
                scalars = dict(original["aggregate_scalars"])
                scalars["mean_heldout_p_max_gt_200"] = {
                    "numerator": 1_000,
                    "denominator": 10_000,
                }
                row["aggregate_scalars"] = scalars
                _rehash(row, "book_metric_row_sha256")
                rows.append(row)
            else:
                rows.append(original)
        retained = dict(fold)
        retained["book_metric_rows"] = rows
        retained["book_metric_rows_sha256"] = contract.canonical_sha256_v1(rows)
        _rehash(retained, "evaluation_fold_sha256")
        folds.append(retained)
    result = dict(derived)
    result["folds"] = folds
    result["folds_sha256"] = contract.canonical_sha256_v1(folds)
    _rehash(result, "evaluation_result_sha256")
    return result


@pytest.fixture(scope="module")
def authorities() -> dict[str, object]:
    topology = contract.build_result_topology_v1(
        contract.OUTPUT_NAMESPACE + "fixture-run/"
    )
    topology_identity = _body_identity(
        "gs://fixture/authorities/fixture-topology.json", topology
    )
    run_identity = _fake_identity(
        "gs://fixture/run-authorities/fixture-run.json", "run-authority"
    )
    # The bootstrap run identity is the pre-design launch authorization token.
    launch_intent_identity = run_identity
    bootstrap_manifest = contract.build_bootstrap_manifest_v1(
        topology=topology,
        topology_identity=topology_identity,
        run_identity=run_identity,
        code_commit="a" * 40,
        image_digest="sha256:" + "b" * 64,
        process_specs=_process_specs(),
    )
    bootstrap_manifest_identity = _body_identity(
        "gs://fixture/authorities/bootstrap-manifest.json", bootstrap_manifest
    )
    design = contract.build_design_v1(
        output_prefix=contract.OUTPUT_NAMESPACE + "fixture-run/",
        code_identity=_fake_identity("gs://fixture/code.py", "code"),
        report_identity=_fake_identity("gs://fixture/report.md", "report"),
        topology_identity=topology_identity,
        bootstrap_manifest=bootstrap_manifest,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
    )
    design_identity = _body_identity(
        contract.OUTPUT_NAMESPACE + "fixture-run/design.json", design
    )
    training_scores = np.zeros((80, 40_000), dtype=np.float64)
    ledger = contract._ordered_score_row_ledger_fixture_v1(
        [f"lineup-{index:03d}" for index in range(80)], training_scores
    )
    candidates = _candidates()
    later_source_body, later_source_identity = _later_source_fixture(candidates)
    projections = [
        _projection(
            fold,
            candidates=candidates,
            score_matrix_sha256=str(ledger["score_matrix_sha256"]),
            later_source_identity=later_source_identity,
        )
        for fold in range(5)
    ]
    bundle = contract.build_projection_bundle_v1(
        source_ordinal=0, fold_projections=projections
    )
    bundle_uri = next(
        str(row["uri"]) for row in topology["objects"] if row["role"] == "projection"
    )
    bundle_identity = _body_identity(bundle_uri, bundle)
    strategies = contract.frozen_contract_v1()["strategies"]
    fold_receipts = []
    for fold, projection in enumerate(projections):
        sample = contract.deterministic_equal_count_samples_from_projection_v1(
            projection, phase=contract.BROAD_SCREEN_PHASE
        )
        cells = [
            _selection_cell(
                projection=projection,
                sample=view,
                strategy=strategy,
                full_ledger=ledger,
            )
            for view in sample["replicates"][0]["views"]
            for strategy in strategies
        ]
        fold_receipts.append(contract._build_selection_fold_receipt_structural_v1(
            source_ordinal=0,
            fold_ordinal=fold,
            projection=projection,
            phase=contract.BROAD_SCREEN_PHASE,
            full_candidate_score_row_ledger=ledger,
            cells=cells,
        ))
    fold_process_budgets = [
        contract.compile_process_budget_v1(
            process_role="broad-fold-selector",
            projection_bundle=bundle,
            projection_bundle_identity=bundle_identity,
            topology=topology,
            topology_identity=topology_identity,
            source_ordinal=0,
            fold_ordinal=fold,
        )
        for fold in range(contract.FOLDS_PER_SLATE)
    ]
    fold_process_budget_identities = [
        _body_identity(
            f"gs://fixture/authorities/fold-budget-{fold}.json", budget
        )
        for fold, budget in enumerate(fold_process_budgets)
    ]
    fold_process_chain = contract.bootstrap_process_spec_v1(
        bootstrap_manifest, process_role="broad-fold-selector"
    )["process_chain"]
    child_execution_evidence = []
    for fold in range(contract.FOLDS_PER_SLATE):
        training_reads = [
            {
                "ordinal": ordinal,
                "channel": "process-budget",
                "role": f"training-world-{block}",
                "identity": projections[fold]["world_artifact_identities"][
                    f"world_artifact_{block.lower()}"
                ],
            }
            for ordinal, block in enumerate(projections[fold]["training_blocks"])
        ]
        runtime_rows = []
        for component in fold_process_chain:
            runtime = {
                "command": component["command"],
                "entrypoint_sha256": component["entrypoint_sha256"],
                "code_commit": "a" * 40,
                "image_digest": "sha256:" + "b" * 64,
            }
            _rehash(runtime, "runtime_evidence_sha256")
            runtime_rows.append(runtime)
        evidence = {
            "schema_version": "corpus-r6-current-bank-child-execution-evidence/v1",
            "phase": contract.BROAD_SCREEN_PHASE,
            "source_ordinal": 0,
            "fold_ordinal": fold,
            "heldout_block": contract.WORLD_BLOCKS[fold],
            "process_ordinal": fold,
            "logical_fold_process_count": 1,
            "os_process_count": 2,
            "ordered_process_chain": fold_process_chain,
            "ordered_process_chain_sha256": contract.canonical_sha256_v1(
                fold_process_chain
            ),
            "broker_command": fold_process_chain[0]["command"],
            "broker_entrypoint_sha256": fold_process_chain[0]["entrypoint_sha256"],
            "matrix_command": fold_process_chain[1]["command"],
            "matrix_entrypoint_sha256": fold_process_chain[1]["entrypoint_sha256"],
            "broker_runtime_evidence": runtime_rows[0],
            "broker_runtime_evidence_sha256": runtime_rows[0][
                "runtime_evidence_sha256"
            ],
            "matrix_runtime_evidence": runtime_rows[1],
            "matrix_runtime_evidence_sha256": runtime_rows[1][
                "runtime_evidence_sha256"
            ],
            "training_artifact_read_ledger": training_reads,
            "training_artifact_read_ledger_sha256": contract.canonical_sha256_v1(
                training_reads
            ),
            "training_artifact_read_count": 4,
            "bootstrap_manifest_identity": bootstrap_manifest_identity,
            "bootstrap_manifest_sha256": bootstrap_manifest[
                "bootstrap_manifest_sha256"
            ],
            "process_budget_identity": fold_process_budget_identities[fold],
            "launch_intent_identity": launch_intent_identity,
            "fit_count": fold_receipts[fold]["cell_count"],
            "matrix_capability_sha256": sha256(
                f"capability-{fold}".encode("utf-8")
            ).hexdigest(),
            "matrix_response_sha256": sha256(
                f"response-{fold}".encode("utf-8")
            ).hexdigest(),
            "matrix_response_bytes": 50,
            "child_output_bytes": 100,
            "child_output_byte_ceiling": fold_process_budgets[fold][
                "child_output_byte_ceiling"
            ],
            "selection_fold_receipt_sha256": fold_receipts[fold][
                "selection_fold_receipt_sha256"
            ],
            "runtime_evidence_strength": "process-environment-observation-only",
            "outer_launch_authority_binding_required": True,
            "outer_launch_authority_identity": launch_intent_identity,
            "transport_capability_reached_matrix_process": False,
            "heldout_identity_reached_matrix_process": False,
        }
        _rehash(evidence, "child_execution_evidence_sha256")
        child_execution_evidence.append(evidence)
    receipt = contract.build_selection_receipt_v1(
        projection_bundle=bundle,
        projection_bundle_identity=bundle_identity,
        topology=topology,
        topology_identity=topology_identity,
        phase=contract.BROAD_SCREEN_PHASE,
        fold_receipts=fold_receipts,
        bootstrap_manifest=bootstrap_manifest,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
        launch_intent_identity=launch_intent_identity,
        child_execution_evidence=child_execution_evidence,
    )
    receipt_uri = next(
        str(row["uri"])
        for row in topology["objects"]
        if row["role"] == "broad-selection-receipt"
    )
    receipt_identity = _body_identity(receipt_uri, receipt)
    heldout_artifact_identities = [
        projections[fold]["world_artifact_identities"][
            f"world_artifact_{contract.WORLD_BLOCKS[fold].lower()}"
        ]
        for fold in range(5)
    ]
    heldout_score_matrices = [
        np.zeros((80, 10_000), dtype=np.float64) for _ in range(5)
    ]
    evaluator_process_budget = contract.compile_evaluator_process_budget_v1(
        design=design,
        design_publication_identity=design_identity,
        bootstrap_manifest=bootstrap_manifest,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
        launch_intent_identity=launch_intent_identity,
        projection_bundle=bundle,
        projection_bundle_identity=bundle_identity,
        topology_identity=topology_identity,
        source_ordinal=0,
        selection_receipt=receipt,
        selection_receipt_identity=receipt_identity,
    )
    evaluator_process_budget_identity = _body_identity(
        "gs://fixture/authorities/evaluator-budget.json",
        evaluator_process_budget,
    )
    evaluator_spec = contract.bootstrap_process_spec_v1(
        bootstrap_manifest, process_role="broad-evaluator"
    )["process_chain"][0]
    runtime_observation = contract.build_runtime_observation_v1(
        bootstrap_manifest=bootstrap_manifest,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
        process_budget=evaluator_process_budget,
        process_budget_identity=evaluator_process_budget_identity,
        launch_intent_identity=launch_intent_identity,
        observed_code_commit="a" * 40,
        observed_image_digest="sha256:" + "b" * 64,
        observed_command=evaluator_spec["command"],
        observed_entrypoint_sha256=evaluator_spec["entrypoint_sha256"],
        cloud_job_name="fixture-evaluator",
        cloud_execution_name="fixture-execution",
        cloud_task_index=0,
    )
    derived_evaluation_result = contract.build_evaluation_result_v1(
        design=design,
        design_publication_identity=design_identity,
        topology_identity=topology_identity,
        selection_receipt=receipt,
        selection_receipt_identity=receipt_identity,
        projection_bundle=bundle,
        projection_bundle_identity=bundle_identity,
        heldout_fold_input_stream=(
            {
                "fold_ordinal": fold,
                "heldout_artifact_identity": heldout_artifact_identities[fold],
                "heldout_score_matrix": heldout_score_matrices[fold],
            }
            for fold in range(contract.FOLDS_PER_SLATE)
        ),
        later_source_body=later_source_body,
        evaluator_process_budget=evaluator_process_budget,
        evaluator_process_budget_identity=evaluator_process_budget_identity,
        bootstrap_manifest=bootstrap_manifest,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
        runtime_observation=runtime_observation,
        launch_intent_identity=launch_intent_identity,
    )
    evaluation_uri = next(
        str(row["uri"])
        for row in topology["objects"]
        if row["role"] == "broad-evaluation-result"
    )
    derived_evaluation_identity = _body_identity(
        evaluation_uri, derived_evaluation_result
    )
    projection_bodies = [bundle] + [
        {"role": "projection", "source_ordinal": source,
         "policy": dict(contract.POLICY_CLAIMS)}
        for source in range(1, contract.PANEL_SLATE_COUNT)
    ]
    broad_selection_bodies = [receipt] + [
        {"role": "broad-selection-receipt", "source_ordinal": source,
         "policy": dict(contract.POLICY_CLAIMS)}
        for source in range(1, contract.PANEL_SLATE_COUNT)
    ]
    for body in broad_selection_bodies[1:]:
        _rehash(body, "selection_receipt_sha256")
    broad_template = _broad_publication_template(derived_evaluation_result)
    broad_publications, projection_identities, broad_selection_identities = (
        _clone_evaluation_publications(
            template=broad_template,
            topology=topology,
            phase=contract.BROAD_SCREEN_PHASE,
            projection_bodies=projection_bodies,
            selection_bodies=broad_selection_bodies,
        )
    )
    evaluation_result = broad_publications[0]["body"]
    evaluation_identity = broad_publications[0]["identity"]
    broad_authority = contract.build_broad_phase_authority_v1(
        design=design,
        design_publication_identity=design_identity,
        run_identity=run_identity,
        evaluation_publications=broad_publications,
    )
    nomination = contract.deterministic_nominees_from_broad_authority_v1(
        broad_authority
    )
    nomination_publication = contract.build_nomination_publication_v1(
        design=design,
        design_publication_identity=design_identity,
        run_identity=run_identity,
        broad_evaluation_publications=broad_publications,
    )
    assert nomination_publication["broad_phase_authority"] == broad_authority
    assert nomination_publication["nomination"] == nomination
    nomination_publication_identity = _body_identity(
        contract.OUTPUT_NAMESPACE + "fixture-run/nomination.json",
        nomination_publication,
    )
    confirmation_selection_bodies = [
        {"role": "confirmation-selection-receipt", "source_ordinal": source,
         "policy": dict(contract.POLICY_CLAIMS)}
        for source in range(contract.PANEL_SLATE_COUNT)
    ]
    for body in confirmation_selection_bodies:
        _rehash(body, "selection_receipt_sha256")
    confirmation_template = _confirmation_template(
        evaluation_result, nomination
    )
    (
        confirmation_publications,
        confirmation_projection_identities,
        confirmation_selection_identities,
    ) = _clone_evaluation_publications(
        template=confirmation_template,
        topology=topology,
        phase=contract.CONFIRMATION_PHASE,
        projection_bodies=projection_bodies,
        selection_bodies=confirmation_selection_bodies,
    )
    assert confirmation_projection_identities == projection_identities
    aggregate = contract.build_aggregate_mechanics_v1(
        design=design,
        design_publication_identity=design_identity,
        run_identity=run_identity,
        nomination_publication=nomination_publication,
        nomination_publication_identity=nomination_publication_identity,
        broad_evaluation_publications=broad_publications,
        confirmation_evaluation_publications=confirmation_publications,
    )
    aggregate_identity = _body_identity(
        contract.OUTPUT_NAMESPACE + "fixture-run/aggregate.json", aggregate
    )
    return locals()


def test_contract_import_closure_is_selector_free() -> None:
    source = Path(contract.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    ]
    forbidden = ("fast_lane", "corpus_batch_retrieval_runner", "corpus_legal_feasibility")
    assert not any(any(token in name for token in forbidden) for name in imports)
    assert "select_exact80" not in source
    assert "_run_strategy_v2" not in source
    assert contract.canonical_sha256_v1(contract.frozen_profiles_v1()) == contract.PROFILE_REGISTRY_SHA256
    assert contract.canonical_sha256_v1(contract.frozen_strategies_v1()) == contract.STRATEGY_REGISTRY_SHA256


def test_common_seed_equal_count_sampling_is_exact_and_deterministic() -> None:
    registry = contract._derive_view_registry_fixture_v1(_eligible_fixture_rows())
    first = contract._deterministic_equal_count_samples_fixture_v1(
        view_registry=registry,
        slate_id="fixture-slate",
        fit_scope_id="holdout-R4",
        phase=contract.CONFIRMATION_PHASE,
    )
    second = contract._deterministic_equal_count_samples_fixture_v1(
        view_registry=registry,
        slate_id="fixture-slate",
        fit_scope_id="holdout-R4",
        phase=contract.CONFIRMATION_PHASE,
    )
    assert first == second
    assert first["target_count"] == 80
    assert first["replicate_count"] == 32
    union_hashes = []
    for replicate in first["replicates"]:
        assert "view_id" not in replicate["seed_material"]
        assert len({row["seed_material_sha256"] for row in replicate["views"]}) == 1
        assert all(len(row["sampled_lineup_ids"]) == 80 for row in replicate["views"])
        union_hashes.append(replicate["views"][0]["sampled_lineup_ids_sha256"])
    assert len(set(union_hashes)) > 1
    assert "_deterministic_equal_count_samples_fixture_v1" not in contract.__all__


def test_effective_tail_math_preserves_degenerate_independent_and_duplicate_cases() -> None:
    empty = contract._effective_independent_tail_shots_fixture_v1(
        np.zeros((4, 8), dtype=np.float64), threshold=200.0
    )
    assert empty["active_tail_lineup_count"] == 0
    assert empty["zero_event_lineup_count"] == 4
    assert empty["participation_ratio_micro"] == 0
    one = contract._effective_independent_tail_shots_fixture_v1(
        np.asarray([
            [201, 0, 201, 0, 201, 0, 201, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
        ], dtype=np.float64),
        threshold=200.0,
    )
    assert one["active_tail_lineup_count"] == 1
    assert one["participation_ratio_micro"] == 1_000_000
    independent_scores = np.asarray([
        [201, 201, 0, 0],
        [201, 0, 201, 0],
    ], dtype=np.float64)
    independent = contract._effective_independent_tail_shots_fixture_v1(
        independent_scores, threshold=200.0
    )
    duplicate = contract._effective_independent_tail_shots_fixture_v1(
        np.vstack([independent_scores[0], independent_scores[0]]),
        threshold=200.0,
    )
    assert independent["pairwise_active_correlation_mean_micro"] == 0
    assert independent["participation_ratio_micro"] == 2_000_000
    assert duplicate["pairwise_active_correlation_mean_micro"] == 1_000_000
    assert duplicate["participation_ratio_micro"] == 1_000_000
    assert "_effective_independent_tail_shots_fixture_v1" not in contract.__all__


def test_projection_bundle_is_exact_five_fold_self_hashed_authority(
    authorities: dict[str, object],
) -> None:
    bundle = authorities["bundle"]
    assert bundle["fold_count"] == 5
    assert bundle["fold_order"] == ["R0", "R1", "R2", "R3", "R4"]
    assert len(bundle["fold_projection_sha256s"]) == 5
    assert contract.validate_projection_bundle_authority_v1(
        bundle,
        publication_identity=authorities["bundle_identity"],
        topology=authorities["topology"],
        topology_identity=authorities["topology_identity"],
    ) == bundle
    wrong_identity = _body_identity(
        "gs://fixture/unplanned/projection.json", bundle
    )
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="projection bundle URI differs",
    ):
        contract.validate_projection_bundle_authority_v1(
            bundle,
            publication_identity=wrong_identity,
            topology=authorities["topology"],
            topology_identity=authorities["topology_identity"],
        )
    changed = deepcopy(bundle)
    changed["fold_projections"] = (
        changed["fold_projections"][1:] + changed["fold_projections"][:1]
    )
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="fold order",
    ):
        contract.build_projection_bundle_v1(
            source_ordinal=0, fold_projections=changed["fold_projections"]
        )


def test_projection_forbids_outcome_current_and_multi_generation_reads(
    authorities: dict[str, object],
) -> None:
    projection = deepcopy(authorities["projections"][0])
    projection["world_artifact_identities"]["world_artifact_r1"]["uri"] = (
        "gs://fixture/outcome/forbidden.npz"
    )
    _rehash(projection, "projection_sha256")
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="forbidden URI family",
    ):
        contract.validate_narrow_projection_v1(projection)
    projection = deepcopy(authorities["projections"][0])
    projection["later_source_identity"]["generation"] = "current"
    _rehash(projection, "projection_sha256")
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="transport identity",
    ):
        contract.validate_narrow_projection_v1(projection)
    projection = deepcopy(authorities["projections"][0])
    projection["later_source_identity"] = deepcopy(
        projection["world_artifact_identities"]["world_artifact_r1"]
    )
    projection["later_source_identity"]["generation"] = "2"
    _rehash(projection, "projection_sha256")
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="more than one generation",
    ):
        contract.validate_narrow_projection_v1(projection)


def test_projection_freezes_fixed_panel_candidate_and_identifier_bounds(
    authorities: dict[str, object],
) -> None:
    base = authorities["projections"][0]
    maximum = _projection(
        0,
        candidates=_candidates(contract.MAX_SELECTION_CANDIDATES_PER_FOLD),
        score_matrix_sha256=str(base["expected_training_score_matrix_sha256"]),
        later_source_identity=deepcopy(base["later_source_identity"]),
    )
    assert len(contract.validate_narrow_projection_v1(maximum)["candidates"]) == 250

    too_many = _projection(
        0,
        candidates=_candidates(contract.MAX_SELECTION_CANDIDATES_PER_FOLD + 1),
        score_matrix_sha256=str(base["expected_training_score_matrix_sha256"]),
        later_source_identity=deepcopy(base["later_source_identity"]),
    )
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="candidate count",
    ):
        contract.validate_narrow_projection_v1(too_many)

    long_lineup = deepcopy(base)
    long_lineup["candidates"][0]["lineup_id"] = "x" * 72
    _rehash(long_lineup, "projection_sha256")
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="bounded ASCII identifier",
    ):
        contract.validate_narrow_projection_v1(long_lineup)

    long_player = deepcopy(base)
    long_player["candidates"][0]["roster_player_ids"][0] = "p" * 33
    _rehash(long_player, "projection_sha256")
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="bounded ASCII identifier",
    ):
        contract.validate_narrow_projection_v1(long_player)

    assert contract.BROAD_SELECTION_RECEIPT_MAX_BYTES == 32_000_000
    assert contract.CONFIRMATION_SELECTION_RECEIPT_MAX_BYTES == 96_000_000


def test_fold_receipts_freeze_270_logical_540_os_processes_and_score_ledger(
    authorities: dict[str, object],
) -> None:
    receipt = authorities["receipt"]
    assert contract.FOLD_SELECTOR_SUBPROCESS_COUNT == 270
    assert contract.LOGICAL_FOLD_SELECTION_COUNT_PER_PHASE == 270
    assert contract.SELECTOR_OS_PROCESS_COUNT_PER_PHASE == 540
    assert receipt["logical_fold_selection_ordinals"] == [0, 1, 2, 3, 4]
    assert receipt["logical_fold_selection_count"] == 5
    assert receipt["selector_os_process_count"] == 10
    assert receipt["assembler_artifact_body_read_count"] == 0
    for fold in receipt["fold_receipts"]:
        assert fold["training_artifact_count"] == 4
        assert fold["heldout_artifact_addressable"] is False
        assert fold["heldout_artifact_read"] is False
        assert fold["cell_count"] == 64
    row = np.asarray([0.0, 1.0], dtype=np.float64)
    assert contract._score_row_sha256_fixture_v1(row) == (
        "32d417f1c863366a4678c384746556f4bb26cb0693860e424ab03670a8af3cec"
    )
    assert "_score_row_sha256_fixture_v1" not in contract.__all__
    assert "_ordered_score_row_ledger_fixture_v1" not in contract.__all__


def test_cell_row_ledger_must_be_exact_subset_of_full_ledger(
    authorities: dict[str, object],
) -> None:
    fold = deepcopy(authorities["fold_receipts"][0])
    cell = fold["cells"][0]
    changed_row = dict(cell["training_score_row_ledger"]["rows"][0])
    changed_row["score_row_sha256"] = "f" * 64
    cell["training_score_row_ledger"]["rows"][0] = changed_row
    cell["training_score_row_ledger"]["rows_sha256"] = contract.canonical_sha256_v1(
        cell["training_score_row_ledger"]["rows"]
    )
    _rehash(cell, "selection_cell_sha256")
    fold["cells_sha256"] = contract.canonical_sha256_v1(fold["cells"])
    _rehash(fold, "selection_fold_receipt_sha256")
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="exact full subset",
    ):
        contract.validate_selection_fold_receipt_v1(
            fold, projection=authorities["projections"][0]
        )
    fold = deepcopy(authorities["fold_receipts"][0])
    cell = fold["cells"][0]
    cell["selection_trace"][0]["sampled_lineup_ordinal"] = 79
    cell["selection_trace_sha256"] = contract.canonical_sha256_v1(
        cell["selection_trace"]
    )
    _rehash(cell, "selection_cell_sha256")
    fold["cells_sha256"] = contract.canonical_sha256_v1(fold["cells"])
    _rehash(fold, "selection_fold_receipt_sha256")
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="trace binding differs",
    ):
        contract.validate_selection_fold_receipt_v1(
            fold, projection=authorities["projections"][0]
        )


def test_occurrence_dedup_and_surviving_roster_alias_are_distinct(
    authorities: dict[str, object],
) -> None:
    result = contract.candidate_dedup_diagnostics_from_projection_v1(
        authorities["projections"][0]
    )
    assert result["candidate_row_count"] == 80
    assert result["training_occurrence_count"] == 320
    assert result["occurrence_dedup_loss_count"] == 240
    assert result["unique_canonical_roster_count"] == 79
    assert result["surviving_roster_alias_count"] == 1


def test_heldout_metric_requires_receipt_exact_artifact_and_10000_worlds(
    authorities: dict[str, object],
) -> None:
    scores = np.zeros((4, 10_000), dtype=np.float64)
    first_cell = authorities["receipt"]["fold_receipts"][0]["cells"][0]
    heldout = authorities["projections"][0]["world_artifact_identities"][
        "world_artifact_r0"
    ]
    wrong_receipt_identity = _body_identity(
        "gs://fixture/unplanned/selection.json", authorities["receipt"]
    )
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="selection receipt URI differs",
    ):
        contract.validate_selection_receipt_authority_v1(
            authorities["receipt"],
            publication_identity=wrong_receipt_identity,
            projection_bundle=authorities["bundle"],
            projection_bundle_identity=authorities["bundle_identity"],
            topology=authorities["topology"],
            topology_identity=authorities["topology_identity"],
            bootstrap_manifest=authorities["bootstrap_manifest"],
            bootstrap_manifest_identity=authorities[
                "bootstrap_manifest_identity"
            ],
            launch_intent_identity=authorities["launch_intent_identity"],
        )
    derived = authorities["derived_evaluation_result"]
    assert contract.validate_evaluation_result_authority_v1(
        derived,
        publication_identity=authorities["derived_evaluation_identity"],
        design=authorities["design"],
        design_publication_identity=authorities["design_identity"],
        topology_identity=authorities["topology_identity"],
        selection_receipt=authorities["receipt"],
        selection_receipt_identity=authorities["receipt_identity"],
        projection_bundle=authorities["bundle"],
        projection_bundle_identity=authorities["bundle_identity"],
        heldout_fold_input_stream=(
            {
                "fold_ordinal": fold,
                "heldout_artifact_identity": authorities[
                    "heldout_artifact_identities"
                ][fold],
                "heldout_score_matrix": authorities[
                    "heldout_score_matrices"
                ][fold],
            }
            for fold in range(contract.FOLDS_PER_SLATE)
        ),
        later_source_body=authorities["later_source_body"],
        evaluator_process_budget=authorities["evaluator_process_budget"],
        evaluator_process_budget_identity=authorities[
            "evaluator_process_budget_identity"
        ],
        bootstrap_manifest=authorities["bootstrap_manifest"],
        bootstrap_manifest_identity=authorities["bootstrap_manifest_identity"],
        runtime_observation=authorities["runtime_observation"],
        launch_intent_identity=authorities["launch_intent_identity"],
    ) == derived
    assert derived["population_metric_row_count"] == 140
    assert derived["book_metric_row_count"] == 960
    assert derived["caller_metric_rows_accepted"] is False
    assert all(
        fold["book_metric_rows_sha256"]
        == contract.canonical_sha256_v1(fold["book_metric_rows"])
        for fold in derived["folds"]
    )
    fold = contract.build_evaluation_fold_v1(
        fold_ordinal=0,
        projection=authorities["projections"][0],
        selection_fold_receipt=authorities["receipt"]["fold_receipts"][0],
        heldout_artifact_identity=heldout,
        heldout_score_matrix=np.zeros((80, 10_000), dtype=np.float64),
        later_source_body=authorities["later_source_body"],
    )
    assert fold["population_metric_row_count"] == 28
    assert fold["book_metric_row_count"] == 192
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="full candidate matrix differs",
    ):
        contract.build_evaluation_fold_v1(
            fold_ordinal=0,
            projection=authorities["projections"][0],
            selection_fold_receipt=authorities["receipt"]["fold_receipts"][0],
            heldout_artifact_identity=heldout,
            heldout_score_matrix=np.zeros((80, 9_999), dtype=np.float64),
            later_source_body=authorities["later_source_body"],
        )


def test_phase_grids_require_positive_common_denominators_in_both_phases() -> None:
    broad = _metric_grid()
    broad[1]["mean_heldout_expected_book_max_micro_denominator"] = 2
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="denominator differs",
    ):
        contract._build_phase_grid_fixture_v1(
            phase=contract.BROAD_SCREEN_PHASE, rows=broad
        )
    confirmation = _metric_grid(replicate_count=32)[:3]
    confirmation[0]["mean_heldout_p_max_gt_200_denominator"] = 0
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="exact integer",
    ):
        contract._build_phase_grid_fixture_v1(
            phase=contract.CONFIRMATION_PHASE, rows=confirmation
        )


def test_exact_rational_nomination_guard_and_no_backfill_are_preserved() -> None:
    broad = _metric_grid()
    for row in broad:
        row["mean_heldout_expected_book_max_micro_numerator"] = (
            320_000_000 if row["profile_ordinal"] == -1 else 300_000_000
        )
        row["mean_heldout_expected_book_max_micro_denominator"] = 2
    first = next(
        row for row in broad
        if row["profile_ordinal"] == 1 and row["strategy_ordinal"] == 0
    )
    second = next(
        row for row in broad
        if row["profile_ordinal"] == 1 and row["strategy_ordinal"] == 1
    )
    first["mean_heldout_expected_book_max_micro_numerator"] = 300_000_001
    second["mean_heldout_expected_book_max_micro_numerator"] = 300_000_000
    nomination = contract._deterministic_nominees_fixture_v1(broad)
    assert nomination["p200_noninferiority_floor"] == {
        "numerator": 49, "denominator": 500
    }
    performance = next(
        row for row in nomination["nominees"]
        if "performance-nominee" in row["roles"]
    )
    assert performance["profile_ordinal"] == 1
    assert performance["strategy_ordinal"] == 0
    nominee_keys = {
        (row["view_id"], row["strategy_id"]) for row in nomination["nominees"]
    }
    confirmation = [
        row for row in _metric_grid(replicate_count=32)
        if (row["view_id"], row["strategy_id"]) in nominee_keys
    ]
    for row in confirmation:
        if row["profile_ordinal"] > 0:
            row["mean_heldout_p_max_gt_200_numerator"] = 0
    finalists = contract._deterministic_finalists_fixture_v1(broad, confirmation)
    assert finalists["removed_challenger_count"] == 3
    assert finalists["finalist_count"] == 3
    assert all(
        row["roles"][0].startswith("mandatory-")
        for row in finalists["finalists"]
    )


def test_nomination_binds_broad_authority_and_finalists_bind_combined_aggregate(
    authorities: dict[str, object],
) -> None:
    assert authorities["nomination"]["broad_phase_authority_sha256"] == (
        authorities["broad_authority"]["broad_phase_authority_sha256"]
    )
    assert contract.validate_aggregate_mechanics_authority_v1(
        authorities["aggregate"],
        publication_identity=authorities["aggregate_identity"],
    ) == authorities["aggregate"]
    wrong_aggregate_identity = _body_identity(
        "gs://fixture/unplanned/aggregate.json", authorities["aggregate"]
    )
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="aggregate mechanics URI differs",
    ):
        contract.validate_aggregate_mechanics_authority_v1(
            authorities["aggregate"],
            publication_identity=wrong_aggregate_identity,
        )
    finalists = contract.deterministic_finalists_from_aggregate_v1(
        authorities["aggregate"],
        aggregate_publication_identity=authorities["aggregate_identity"],
    )
    assert finalists["aggregate_mechanics_sha256"] == authorities["aggregate"][
        "aggregate_mechanics_sha256"
    ]
    changed = deepcopy(authorities["aggregate"])
    changed["confirmation_selection_layer"]["entries"][0]["identity"][
        "sha256"
    ] = "f" * 64
    _rehash(changed["confirmation_selection_layer"], "layer_binding_sha256")
    _rehash(changed, "aggregate_mechanics_sha256")
    with pytest.raises(contract.CorpusR6CurrentBankCrossedScreenContractV1Error):
        contract.validate_aggregate_mechanics_authority_v1(
            changed, publication_identity=authorities["aggregate_identity"]
        )


def test_confirmation_rejects_self_attested_nomination_and_wrong_uri(
    authorities: dict[str, object],
) -> None:
    wrong_identity = _body_identity(
        "gs://fixture/unplanned/nomination.json",
        authorities["nomination_publication"],
    )
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="nomination publication URI differs",
    ):
        contract.compile_process_budget_v1(
            process_role="confirmation-fold-selector",
            projection_bundle=authorities["bundle"],
            projection_bundle_identity=authorities["bundle_identity"],
            topology=authorities["topology"],
            topology_identity=authorities["topology_identity"],
            source_ordinal=0,
            fold_ordinal=0,
            nomination_publication=authorities["nomination_publication"],
            nomination_publication_identity=wrong_identity,
        )
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="nomination publication URI differs",
    ):
        contract.build_selection_receipt_v1(
            projection_bundle=authorities["bundle"],
            projection_bundle_identity=authorities["bundle_identity"],
            phase=contract.CONFIRMATION_PHASE,
            fold_receipts=authorities["fold_receipts"],
            nomination_publication=authorities["nomination_publication"],
            nomination_publication_identity=wrong_identity,
            topology=authorities["topology"],
            topology_identity=authorities["topology_identity"],
            bootstrap_manifest=authorities["bootstrap_manifest"],
            bootstrap_manifest_identity=authorities[
                "bootstrap_manifest_identity"
            ],
            launch_intent_identity=authorities["launch_intent_identity"],
            child_execution_evidence=authorities["child_execution_evidence"],
        )
    spliced = deepcopy(authorities["nomination_publication"])
    spliced["nomination"]["nominees"][0]["strategy_id"] = (
        contract.STRATEGY_IDENTITIES[1][1]
    )
    _rehash(spliced["nomination"], "nomination_sha256")
    spliced["nomination_sha256"] = spliced["nomination"]["nomination_sha256"]
    _rehash(spliced, "nomination_publication_sha256")
    spliced_identity = _body_identity(
        contract.OUTPUT_NAMESPACE + "fixture-run/nomination.json", spliced
    )
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="nomination differs",
    ):
        contract.compile_process_budget_v1(
            process_role="confirmation-fold-selector",
            projection_bundle=authorities["bundle"],
            projection_bundle_identity=authorities["bundle_identity"],
            topology=authorities["topology"],
            topology_identity=authorities["topology_identity"],
            source_ordinal=0,
            fold_ordinal=0,
            nomination_publication=spliced,
            nomination_publication_identity=spliced_identity,
        )


def test_aggregate_has_exact_ordered_layers_no_fictional_roots(
    authorities: dict[str, object],
) -> None:
    aggregate = authorities["aggregate"]
    assert aggregate["output_object_count"] == 275
    assert aggregate["all_block_final_fit_count"] == 0
    for field in (
        "projection_layer", "broad_selection_layer", "broad_evaluation_layer",
        "confirmation_selection_layer", "confirmation_evaluation_layer",
    ):
        layer = aggregate[field]
        assert layer["entry_count"] == 54
        assert [row["source_ordinal"] for row in layer["entries"]] == list(range(54))
        assert "root_identity" not in layer
    assert aggregate["broad_phase_grid"]["phase"] == contract.BROAD_SCREEN_PHASE
    assert aggregate["confirmation_phase_grid"]["phase"] == contract.CONFIRMATION_PHASE
    assert aggregate["caller_phase_grid_or_bootstrap_rows_accepted"] is False
    assert aggregate["broad_phase_execution_authority"][
        "logical_fold_selection_count"
    ] == 270
    assert aggregate["broad_phase_execution_authority"][
        "selector_os_process_count"
    ] == 540
    assert aggregate["confirmation_phase_execution_authority"][
        "logical_fold_selection_count"
    ] == 270
    assert aggregate["confirmation_phase_execution_authority"][
        "selector_os_process_count"
    ] == 540
    assert aggregate["paired_comparison_count"] == (
        (authorities["nomination"]["nominee_count"] - 1) * 5
    )
    assert all(
        comparison["ledger"]["row_count"] == 270
        for comparison in aggregate["paired_comparisons"]
    )


def test_process_budget_is_role_derived_exact_and_rejects_role_splice(
    authorities: dict[str, object],
) -> None:
    budget = contract.compile_process_budget_v1(
        process_role="broad-fold-selector",
        projection_bundle=authorities["bundle"],
        projection_bundle_identity=authorities["bundle_identity"],
        topology=authorities["topology"],
        topology_identity=authorities["topology_identity"],
        source_ordinal=0,
        fold_ordinal=0,
    )
    assert [row["role"] for row in budget["read_allowlist"]] == [
        "projection-bundle", "later-source", "training-world-R1",
        "training-world-R2", "training-world-R3", "training-world-R4",
    ]
    assert budget["write_allowlist"] == []
    assert budget["compute_fit_precharge"] == 64
    assert contract.validate_process_budget_v1(budget) == budget
    changed = deepcopy(budget)
    changed["read_allowlist"][2]["role"] = "heldout-world-R0"
    _rehash(changed, "process_budget_sha256")
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="read precharge differs",
    ):
        contract.validate_process_budget_v1(changed)
    assembler = contract.compile_process_budget_v1(
        process_role="broad-slate-assembler",
        projection_bundle=authorities["bundle"],
        projection_bundle_identity=authorities["bundle_identity"],
        topology=authorities["topology"],
        topology_identity=authorities["topology_identity"],
        source_ordinal=0,
    )
    assert [row["role"] for row in assembler["read_allowlist"]] == [
        "projection-bundle"
    ]
    assert assembler["compute_fit_precharge"] == 0
    assert assembler["write_allowlist"][0]["create_once"] is True


def test_selection_rejects_forged_child_evidence_and_wrong_launch_authority(
    authorities: dict[str, object],
) -> None:
    base = {
        "projection_bundle": authorities["bundle"],
        "projection_bundle_identity": authorities["bundle_identity"],
        "topology": authorities["topology"],
        "topology_identity": authorities["topology_identity"],
        "phase": contract.BROAD_SCREEN_PHASE,
        "fold_receipts": authorities["fold_receipts"],
        "bootstrap_manifest": authorities["bootstrap_manifest"],
        "bootstrap_manifest_identity": authorities["bootstrap_manifest_identity"],
    }
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="launch authority differs",
    ):
        contract.build_selection_receipt_v1(
            **base,
            launch_intent_identity=_fake_identity(
                "gs://fixture/authorities/not-authorized.json", "wrong-launch"
            ),
            child_execution_evidence=authorities["child_execution_evidence"],
        )
    forged = deepcopy(authorities["child_execution_evidence"])
    forged[0]["training_artifact_read_ledger"][0]["identity"] = deepcopy(
        forged[0]["training_artifact_read_ledger"][1]["identity"]
    )
    forged[0]["training_artifact_read_ledger_sha256"] = (
        contract.canonical_sha256_v1(
            forged[0]["training_artifact_read_ledger"]
        )
    )
    _rehash(forged[0], "child_execution_evidence_sha256")
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="child execution evidence authority",
    ):
        contract.build_selection_receipt_v1(
            **base,
            launch_intent_identity=authorities["launch_intent_identity"],
            child_execution_evidence=forged,
        )


def test_nomination_publisher_budget_precharges_exact_54_body_order(
    authorities: dict[str, object],
) -> None:
    identities = [row["identity"] for row in authorities["broad_publications"]]
    budget = contract.compile_publisher_process_budget_v1(
        process_role="broad-nomination-publisher",
        design=authorities["design"],
        design_publication_identity=authorities["design_identity"],
        topology_identity=authorities["topology_identity"],
        bootstrap_manifest=authorities["bootstrap_manifest"],
        bootstrap_manifest_identity=authorities["bootstrap_manifest_identity"],
        launch_intent_identity=authorities["launch_intent_identity"],
        scientific_read_identities=identities,
    )
    assert budget["scientific_read_count"] == 54
    assert budget["read_object_count_excluding_budget_authority"] == 58
    assert budget["write_object_count"] == 1
    assert budget["write_allowlist"][0]["role"] == "nomination"
    assert contract.validate_publisher_process_budget_v1(
        budget,
        design=authorities["design"],
        design_publication_identity=authorities["design_identity"],
        topology_identity=authorities["topology_identity"],
        bootstrap_manifest=authorities["bootstrap_manifest"],
        bootstrap_manifest_identity=authorities["bootstrap_manifest_identity"],
        launch_intent_identity=authorities["launch_intent_identity"],
    ) == budget
    reordered = list(identities)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="URI/order differs",
    ):
        contract.compile_publisher_process_budget_v1(
            process_role="broad-nomination-publisher",
            design=authorities["design"],
            design_publication_identity=authorities["design_identity"],
            topology_identity=authorities["topology_identity"],
            bootstrap_manifest=authorities["bootstrap_manifest"],
            bootstrap_manifest_identity=authorities[
                "bootstrap_manifest_identity"
            ],
            launch_intent_identity=authorities["launch_intent_identity"],
            scientific_read_identities=reordered,
        )


def test_topology_requires_nonempty_child_prefix_and_root_last() -> None:
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="fixed research namespace",
    ):
        contract.build_result_topology_v1(contract.OUTPUT_NAMESPACE)
    topology = contract.build_result_topology_v1(
        contract.OUTPUT_NAMESPACE + "another-run/"
    )
    assert topology["object_count"] == 275
    assert topology["objects"][-1]["role"] == "root"
    changed = deepcopy(topology)
    changed["objects"][-1], changed["objects"][-2] = (
        changed["objects"][-2], changed["objects"][-1]
    )
    _rehash(changed, "topology_sha256")
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="canonical replay differs",
    ):
        contract.validate_result_topology_v1(changed)


def test_derived_bootstrap_is_keyed_to_exact_noncaller_comparison_ledger(
    authorities: dict[str, object],
) -> None:
    comparison = authorities["aggregate"]["paired_comparisons"][0]
    result = comparison["bootstrap"]
    assert result["lower_endpoint_micro"] == 0
    assert result["upper_endpoint_micro"] == 0
    assert result["seed_material"]["contract_sha256"] == authorities["design"][
        "report_identity"
    ]["sha256"]
    changed = deepcopy(authorities["aggregate"])
    changed_comparison = changed["paired_comparisons"][0]
    changed_comparison["ledger"]["rows"][0]["delta_numerator_micro"] = 1
    changed_comparison["ledger"]["rows_sha256"] = contract.canonical_sha256_v1(
        changed_comparison["ledger"]["rows"]
    )
    changed_comparison["ledger"]["summary"] = contract._comparison_summary_v1(
        changed_comparison["ledger"]["rows"]
    )
    _rehash(changed_comparison["ledger"], "comparison_ledger_sha256")
    changed_comparison["comparison_ledger_sha256"] = changed_comparison[
        "ledger"
    ]["comparison_ledger_sha256"]
    changed["paired_comparisons_sha256"] = contract.canonical_sha256_v1(
        changed["paired_comparisons"]
    )
    _rehash(changed, "aggregate_mechanics_sha256")
    changed_identity = _body_identity(
        contract.OUTPUT_NAMESPACE + "fixture-run/aggregate.json", changed
    )
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="delta",
    ):
        contract.validate_aggregate_mechanics_authority_v1(
            changed, publication_identity=changed_identity
        )


def test_phase_authorities_reject_missing_reordered_or_fabricated_publications(
    authorities: dict[str, object],
) -> None:
    kwargs = {
        "design": authorities["design"],
        "design_publication_identity": authorities["design_identity"],
        "run_identity": authorities["run_identity"],
    }
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="exactly 54",
    ):
        contract.build_broad_phase_authority_v1(
            **kwargs,
            evaluation_publications=authorities["broad_publications"][:-1],
        )
    reordered = list(authorities["broad_publications"])
    reordered[0], reordered[1] = reordered[1], reordered[0]
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="source/phase/design/topology",
    ):
        contract.build_broad_phase_authority_v1(
            **kwargs, evaluation_publications=reordered
        )
    fabricated = list(authorities["broad_publications"])
    fabricated_record = dict(fabricated[0])
    fabricated_body = dict(fabricated_record["body"])
    fabricated_folds = list(fabricated_body["folds"])
    fabricated_fold = dict(fabricated_folds[0])
    fabricated_rows = list(fabricated_fold["book_metric_rows"])
    fabricated_rows.pop()
    fabricated_fold["book_metric_rows"] = fabricated_rows
    fabricated_folds[0] = fabricated_fold
    fabricated_body["folds"] = fabricated_folds
    fabricated_record["body"] = fabricated_body
    fabricated[0] = fabricated_record
    with pytest.raises(contract.CorpusR6CurrentBankCrossedScreenContractV1Error):
        contract.build_broad_phase_authority_v1(
            **kwargs, evaluation_publications=fabricated
        )


def test_evaluation_publication_rejects_reordered_or_caller_metric_rows(
    authorities: dict[str, object],
) -> None:
    changed = deepcopy(authorities["derived_evaluation_result"])
    rows = changed["folds"][0]["book_metric_rows"]
    rows[0], rows[1] = rows[1], rows[0]
    changed["folds"][0]["book_metric_rows_sha256"] = contract.canonical_sha256_v1(
        rows
    )
    _rehash(changed["folds"][0], "evaluation_fold_sha256")
    changed["folds_sha256"] = contract.canonical_sha256_v1(changed["folds"])
    _rehash(changed, "evaluation_result_sha256")
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="identity/lattice",
    ):
        contract.validate_evaluation_result_v1(changed)
    signature = set(
        __import__("inspect").signature(
            contract.build_evaluation_result_v1
        ).parameters
    )
    assert "fold_summaries" not in signature
    assert "metric_rows" not in signature


def test_all_durable_constructor_outputs_share_exact_nine_claim_policy(
    authorities: dict[str, object],
) -> None:
    finalists = contract.deterministic_finalists_from_aggregate_v1(
        authorities["aggregate"],
        aggregate_publication_identity=authorities["aggregate_identity"],
    )
    budget = contract.compile_process_budget_v1(
        process_role="broad-slate-assembler",
        projection_bundle=authorities["bundle"],
        projection_bundle_identity=authorities["bundle_identity"],
        topology=authorities["topology"],
        topology_identity=authorities["topology_identity"],
        source_ordinal=0,
    )
    values = [
        contract.frozen_contract_v1(),
        *authorities["projections"],
        authorities["bundle"],
        *authorities["fold_receipts"],
        authorities["receipt"],
        authorities["derived_evaluation_result"],
        authorities["topology"],
        authorities["broad_authority"],
        authorities["nomination_publication"],
        authorities["aggregate"],
        finalists,
        budget,
    ]
    assert contract.POLICY_CLAIMS == {
        "uses_realized_outcomes": False,
        "historical_scoring_performed": False,
        "historical_scoring_licensed": False,
        "corpus_regeneration_performed": False,
        "matchup_source_read": False,
        "graph_mutation_performed": False,
        "production_change_performed": False,
        "promotion_authority": False,
        "decision_authority": False,
    }
    assert all(value["policy"] == contract.POLICY_CLAIMS for value in values)
    changed = deepcopy(authorities["bundle"])
    changed["policy"]["decision_authority"] = True
    _rehash(changed, "projection_bundle_sha256")
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="policy claims differ",
    ):
        contract.validate_projection_bundle_v1(changed)


def test_no_legacy_raw_or_phase_budget_authority_is_exported() -> None:
    forbidden = {
        "compile_phase_budget_v1",
        "derive_view_registry_v1",
        "deterministic_equal_count_samples_v1",
        "deterministic_nominees_v1",
        "deterministic_finalists_v1",
        "deterministic_slate_cluster_bootstrap_v1",
        "effective_independent_tail_shots_v1",
    }
    assert forbidden.isdisjoint(contract.__all__)
    frozen = contract.frozen_contract_v1()
    assert frozen["primary_baseline"] == {
        "view_id": "U", "strategy_id": "coverage-194-v1", "prefix_size": 80
    }
    assert frozen["maximum_selector_fits"] == 69_120
    assert frozen["all_block_final_fit_count"] == 0


def test_design_precharges_all_275_and_terminal_root_is_exact_root_last(
    authorities: dict[str, object],
) -> None:
    design = authorities["design"]
    topology = authorities["topology"]
    assert len(design["publication_budgets"]) == contract.OUTPUT_OBJECT_COUNT
    assert [row["ordinal"] for row in design["publication_budgets"]] == list(range(275))
    assert all(row["create_once"] is True and row["max_bytes"] > 0 for row in design["publication_budgets"])
    design_identity = authorities["design_identity"]
    finalists = contract.deterministic_finalists_from_aggregate_v1(
        authorities["aggregate"],
        aggregate_publication_identity=authorities["aggregate_identity"],
    )
    finalist_publication = contract.build_finalist_publication_v1(
        finalists=finalists,
        aggregate=authorities["aggregate"],
        aggregate_publication_identity=authorities["aggregate_identity"],
    )
    finalist_identity = _body_identity(
        contract.OUTPUT_NAMESPACE + "fixture-run/confirmed-finalists.json",
        finalist_publication,
    )
    bodies: list[dict[str, object]] = [
        design,
        *authorities["projection_bodies"],
        *authorities["broad_selection_bodies"],
        *(row["body"] for row in authorities["broad_publications"]),
        authorities["nomination_publication"],
        *authorities["confirmation_selection_bodies"],
        *(row["body"] for row in authorities["confirmation_publications"]),
        authorities["aggregate"],
        finalist_publication,
    ]
    identities: list[dict[str, object]] = [
        design_identity,
        *authorities["projection_identities"],
        *authorities["broad_selection_identities"],
        *(row["identity"] for row in authorities["broad_publications"]),
        authorities["nomination_publication_identity"],
        *authorities["confirmation_selection_identities"],
        *(row["identity"] for row in authorities["confirmation_publications"]),
        authorities["aggregate_identity"],
        finalist_identity,
    ]
    assert len(bodies) == 274 == len(identities)
    def opener(descriptor: dict[str, object]) -> tuple[object, object]:
        ordinal = int(descriptor["ordinal"])
        return bodies[ordinal], identities[ordinal]

    checkpoints: list[str] = []
    root = contract.build_terminal_root_from_stream_v1(
        design=design,
        design_publication_identity=design_identity,
        predecessor_opener=opener,
        maximum_compact_evaluation_state_bytes=64_000_000,
        resource_checkpoint=checkpoints.append,
    )
    root_identity = _body_identity(
        contract.OUTPUT_NAMESPACE + "fixture-run/root.json", root
    )
    assert contract.validate_terminal_root_from_stream_authority_v1(
        root,
        publication_identity=root_identity,
        design=design,
        design_publication_identity=design_identity,
        predecessor_opener=opener,
        maximum_compact_evaluation_state_bytes=64_000_000,
        resource_checkpoint=lambda _label: None,
    ) == root
    assert root["predecessor_opener_call_count"] == 274
    assert root["retained_full_evaluation_body_count"] == 0
    assert root["retained_compact_evaluation_record_count"] == 108
    assert 2 < root["retained_compact_evaluation_state_bytes"] <= 64_000_000
    assert len(checkpoints) == 274
    assert root["broad_logical_fold_selection_count"] == 270
    assert root["broad_selector_os_process_count"] == 540
    assert root["confirmation_logical_fold_selection_count"] == 270
    assert root["confirmation_selector_os_process_count"] == 540

    def missing_opener(descriptor: dict[str, object]) -> tuple[object, object]:
        ordinal = int(descriptor["ordinal"])
        if ordinal == 273:
            raise contract.CorpusR6CurrentBankCrossedScreenContractV1Error(
                "missing predecessor"
            )
        return bodies[ordinal], identities[ordinal]

    with pytest.raises(contract.CorpusR6CurrentBankCrossedScreenContractV1Error):
        contract.build_terminal_root_from_stream_v1(
            design=design,
            design_publication_identity=design_identity,
            predecessor_opener=missing_opener,
            maximum_compact_evaluation_state_bytes=64_000_000,
            resource_checkpoint=lambda _label: None,
        )
    reordered = list(identities)
    reordered[1], reordered[2] = reordered[2], reordered[1]
    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="streamed predecessor",
    ):
        contract.build_terminal_root_from_stream_v1(
            design=design,
            design_publication_identity=design_identity,
            predecessor_opener=lambda descriptor: (
                bodies[int(descriptor["ordinal"])],
                reordered[int(descriptor["ordinal"])],
            ),
            maximum_compact_evaluation_state_bytes=64_000_000,
            resource_checkpoint=lambda _label: None,
        )

    with pytest.raises(
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        match="compact evaluation state exceeds",
    ):
        contract.build_terminal_root_from_stream_v1(
            design=design,
            design_publication_identity=design_identity,
            predecessor_opener=opener,
            maximum_compact_evaluation_state_bytes=2,
            resource_checkpoint=lambda _label: None,
        )
