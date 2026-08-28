from __future__ import annotations

import ast
import builtins
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import errno
import fcntl
from hashlib import sha256
import inspect
import importlib.util
import io
import os
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys

import numpy as np
import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_selection_assembler_v1 as assembler,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_selection_fold_worker_v1 as worker,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as task_manifest,
)
from scripts import (
    run_corpus_r6_current_bank_crossed_screen_selection_v1 as runner,
)


def _body_identity(
    uri: str, value: object, *, generation: str = "1",
) -> dict[str, object]:
    raw = contract.canonical_json_bytes_v1(value)
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


@dataclass
class _Store:
    objects: dict[tuple[str, str], bytes]

    def __init__(self) -> None:
        self.objects = {}
        self.reads: list[dict[str, object]] = []
        self.publications: list[tuple[str, bytes]] = []

    def add_body(
        self, uri: str, value: object, *, generation: str = "1",
    ) -> dict[str, object]:
        identity = _body_identity(uri, value, generation=generation)
        self.objects[(uri, generation)] = contract.canonical_json_bytes_v1(value)
        return identity

    def add_bytes(
        self, uri: str, raw: bytes, *, generation: str = "1",
    ) -> dict[str, object]:
        identity = {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[(uri, generation)] = raw
        return identity

    def read_exact(self, identity: MappingForTest) -> bytes:
        retained = contract._safe_object_identity(identity, label="fixture read")
        self.reads.append(retained)
        try:
            return self.objects[
                (str(retained["uri"]), str(retained["generation"]))
            ]
        except KeyError as exc:
            raise assembler.CorpusR6CurrentBankSelectionAssemblerV1Error(
                "fixture exact generation is absent"
            ) from exc

    def publish(
        self, uri: str, raw: bytes,
        prior_identity: MappingForTest | None,
    ) -> dict[str, object]:
        self.publications.append((uri, raw))
        if any(key[0] == uri for key in self.objects):
            if prior_identity is None:
                raise assembler.CorpusR6CurrentBankSelectionAssemblerV1Error(
                    "fixture collision lacks prior authority"
                )
            prior = contract._safe_object_identity(
                prior_identity, label="fixture prior authority"
            )
            if prior["uri"] != uri or self.read_exact(prior) != raw:
                raise assembler.CorpusR6CurrentBankSelectionAssemblerV1Error(
                    "fixture collision differs from prior authority"
                )
            return prior
        identity = {
            "uri": uri,
            "generation": "9",
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[(uri, "9")] = raw
        return identity


MappingForTest = dict[str, object]


def _environment(process_ordinal: int, *, execution: str) -> dict[str, str]:
    return {
        "GOOGLE_CLOUD_PROJECT": assembler.FIXED_GCP_PROJECT,
        "CODE_SHA": "a" * 40,
        "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "b" * 64,
        "CLOUD_RUN_JOB": "fixture-selection",
        "CLOUD_RUN_EXECUTION": execution,
        "CLOUD_RUN_TASK_INDEX": str(process_ordinal),
        "R6_SELECTOR_PROCESS_ORDINAL": str(process_ordinal),
    }


def _task_binding_evidence(
    request: dict[str, object], raw_request: bytes,
) -> dict[str, object]:
    phase = str(request["phase"])
    source = int(request["source_ordinal"])
    manifest_raw = b'{"fixture":"selection-task-manifest"}'
    body = {
        "schema_version": task_manifest.CHILD_TASK_BINDING_EVIDENCE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "manifest_identity": {
            "uri": contract.OUTPUT_NAMESPACE
            + "fixture-binding/selection-task-manifest.json",
            "generation": "717171",
            "sha256": sha256(manifest_raw).hexdigest(),
            "bytes": len(manifest_raw),
        },
        "task_manifest_sha256": "1" * 64,
        "layer_id": (
            "broad-selection-receipt"
            if phase == contract.BROAD_SCREEN_PHASE
            else "confirmation-selection-receipt"
        ),
        "phase": phase,
        "process_role": (
            "broad-slate-assembler"
            if phase == contract.BROAD_SCREEN_PHASE
            else "confirmation-slate-assembler"
        ),
        "task_index": source,
        "source_ordinal": source,
        "process_ordinal": source,
        "task_binding_sha256": "2" * 64,
        "request_sha256": sha256(raw_request).hexdigest(),
        "request_bytes": len(raw_request),
        "expected_outputs_sha256": "3" * 64,
        "child_command_sha256": "4" * 64,
        "manifest_generation_exact_reopen_required": True,
        "caller_request_or_command_accepted": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    body["child_task_binding_evidence_sha256"] = (
        contract.canonical_sha256_v1(body)
    )
    return body


def _runtime(
    mode: str, process_ordinal: int, *, pid: int, execution: str,
) -> dict[str, object]:
    command = {
        "fold-broker": assembler.canonical_fold_broker_command_v1,
        "matrix-selector": assembler.canonical_matrix_selector_command_v1,
        "slate-assembler": assembler.canonical_slate_assembler_command_v1,
    }[mode]()
    return assembler.derive_observed_runtime_evidence_v1(
        mode=mode,
        process_ordinal=process_ordinal,
        environ=_environment(process_ordinal, execution=execution),
        argv=command,
        pid=pid,
        parent_pid=1,
    )


def _catalog() -> list[dict[str, object]]:
    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "WR", "TE", "DST"]
    return [
        {
            "id": f"p-{index:02d}",
            "pos": position,
            "team": "AAA" if index < 8 else "BBB",
            "opp": "BBB" if index < 8 else "AAA",
            "game_id": "AAA-BBB",
            "salary": 3000 + index * 100,
        }
        for index, position in enumerate(positions)
    ]


def _candidates(training: list[str]) -> list[dict[str, object]]:
    profiles = sorted(value[1] for value in contract.PROFILE_IDENTITIES)
    roster = [f"p-{index:02d}" for index in range(9)]
    return [
        {
            "lineup_id": f"lineup-{index:03d}",
            "roster_player_ids": roster,
            "training_origin_blocks": list(training),
            "training_source_arms": profiles,
            "training_occurrence_counts_by_block": {
                block: 1 for block in training
            },
            "training_source_arms_by_block": {
                block: profiles for block in training
            },
            "training_occurrence_count": len(training),
        }
        for index in range(contract.ENTRY_BUDGET)
    ]


def _projection(
    fold: int,
    *,
    source_identity: dict[str, object],
    artifact_identities: dict[str, dict[str, object]],
    score_sha256: str,
) -> dict[str, object]:
    heldout = contract.WORLD_BLOCKS[fold]
    training = [block for block in contract.WORLD_BLOCKS if block != heldout]
    candidates = _candidates(training)
    lineup_ids = [row["lineup_id"] for row in candidates]
    rosters = [row["roster_player_ids"] for row in candidates]
    body = {
        "schema_version": contract.PROJECTION_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "slate_id": "fixture-slate",
        "fit_scope_id": f"holdout-{heldout}",
        "source_task_result_identity": {
            "uri": "gs://fixture/task-results/fixture-slate.json",
            "generation": "1",
            "sha256": "1" * 64,
            "bytes": 1,
        },
        "task_result_payload_sha256": "2" * 64,
        "later_source_identity": source_identity,
        "world_artifact_identities": {
            f"world_artifact_{block.lower()}": artifact_identities[block]
            for block in contract.WORLD_BLOCKS
        },
        "fit_candidate_view_sha256": f"{fold + 3:x}" * 64,
        "selection_provenance_sha256": f"{fold + 4:x}" * 64,
        "training_blocks": training,
        "heldout_block": heldout,
        "training_world_columns_sha256": (
            contract.canonical_world_columns_sha256_v1(training)
        ),
        "candidates": candidates,
        "candidate_lineup_order_sha256": contract.canonical_sha256_v1(
            lineup_ids
        ),
        "candidate_rosters_sha256": contract.canonical_sha256_v1(rosters),
        "candidate_rows_sha256": contract.canonical_sha256_v1(candidates),
        "expected_training_score_matrix_sha256": score_sha256,
        "expected_training_score_shape": [contract.ENTRY_BUDGET, 40_000],
        "policy": dict(contract.POLICY_CLAIMS),
    }
    body["projection_sha256"] = contract.canonical_sha256_v1(body)
    return contract.validate_narrow_projection_v1(body)


def _selection_cell(
    *,
    projection: dict[str, object],
    sample: dict[str, object],
    strategy: dict[str, object],
    ledger: dict[str, object],
    replicate: int,
) -> dict[str, object]:
    selected = list(sample["sampled_lineup_ids"][: contract.ENTRY_BUDGET])
    candidate_by_id = {
        row["lineup_id"]: row for row in projection["candidates"]
    }
    roster_by_id = {
        lineup_id: list(candidate_by_id[lineup_id]["roster_player_ids"])
        for lineup_id in selected
    }
    sampled_ledger = contract._sampled_score_row_ledger_from_full_v1(
        ledger, sample["sampled_lineup_ids"]
    )
    trace = contract._selection_trace_binding_v1(
        selected_lineup_ids=selected,
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
        "selected_lineup_ids": selected,
        "selected_lineup_ids_sha256": contract.canonical_sha256_v1(selected),
        "selected_rosters_sha256": contract.canonical_sha256_v1(
            [roster_by_id[lineup_id] for lineup_id in selected]
        ),
        "prefixes": contract._selection_prefixes_v1(selected, roster_by_id),
        "selection_trace": trace,
        "selection_trace_sha256": contract.canonical_sha256_v1(trace),
    }
    body["selection_cell_sha256"] = contract.canonical_sha256_v1(body)
    return body


def _maximum_selection_wire_shape(
) -> tuple[dict[str, object], dict[str, object], list[str]]:
    """Build the largest frozen candidate/sample surface without a matrix."""

    def maximum_identity(tag: str) -> dict[str, object]:
        prefix = "gs://fixture/"
        segment = (tag + "-" + "x" * contract.MAX_GCS_URI_UTF8_BYTES)[
            : contract.MAX_GCS_URI_UTF8_BYTES - len(prefix)
        ]
        uri = prefix + segment
        assert len(uri.encode("utf-8")) == contract.MAX_GCS_URI_UTF8_BYTES
        return {
            "uri": uri,
            "generation": "9" * contract.MAX_GENERATION_DIGITS,
            "sha256": sha256(tag.encode("utf-8")).hexdigest(),
            "bytes": contract.MAX_IDENTITY_BYTES,
        }

    fold = 0
    heldout = contract.WORLD_BLOCKS[fold]
    training = [
        block for block in contract.WORLD_BLOCKS if block != heldout
    ]
    profiles = sorted(value[1] for value in contract.PROFILE_IDENTITIES)
    lineup_ids = [
        f"lineup-{index:064x}"
        for index in range(contract.MAX_SELECTION_CANDIDATES_PER_FOLD)
    ]
    assert all(
        len(value.encode("utf-8")) == contract.MAX_LINEUP_ID_UTF8_BYTES
        for value in lineup_ids
    )
    roster = [
        prefix + "x" * (contract.MAX_PLAYER_ID_UTF8_BYTES - len(prefix))
        for prefix in (f"player-{index:02d}-" for index in range(contract.ROSTER_SIZE))
    ]
    assert roster == sorted(roster)
    assert all(
        len(value.encode("utf-8")) == contract.MAX_PLAYER_ID_UTF8_BYTES
        for value in roster
    )
    candidates = [
        {
            "lineup_id": lineup_id,
            "roster_player_ids": roster,
            "training_origin_blocks": training,
            "training_source_arms": profiles,
            "training_occurrence_counts_by_block": {
                block: 1 for block in training
            },
            "training_source_arms_by_block": {
                block: profiles for block in training
            },
            "training_occurrence_count": len(training),
        }
        for lineup_id in lineup_ids
    ]
    rows = [
        {
            "lineup_id": lineup_id,
            "score_row_sha256": sha256(lineup_id.encode("utf-8")).hexdigest(),
        }
        for lineup_id in lineup_ids
    ]
    ledger = {
        "dtype": "float64-le",
        "world_count": 4 * contract.WORLDS_PER_BLOCK,
        "row_count": len(lineup_ids),
        "lineup_ids_sha256": contract.canonical_sha256_v1(lineup_ids),
        "rows": rows,
        "rows_sha256": contract.canonical_sha256_v1(rows),
        "score_matrix_shape": [
            len(lineup_ids), 4 * contract.WORLDS_PER_BLOCK,
        ],
        "score_matrix_sha256": "a" * 64,
    }
    body = {
        "schema_version": contract.PROJECTION_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "slate_id": "2025-w18",
        "fit_scope_id": f"holdout-{heldout}",
        "source_task_result_identity": maximum_identity("task-result"),
        "task_result_payload_sha256": "b" * 64,
        "later_source_identity": maximum_identity("later-source"),
        "world_artifact_identities": {
            f"world_artifact_{block.lower()}": maximum_identity(
                f"world-{block}"
            )
            for block in contract.WORLD_BLOCKS
        },
        "fit_candidate_view_sha256": "c" * 64,
        "selection_provenance_sha256": "d" * 64,
        "training_blocks": training,
        "heldout_block": heldout,
        "training_world_columns_sha256": (
            contract.canonical_world_columns_sha256_v1(training)
        ),
        "candidates": candidates,
        "candidate_lineup_order_sha256": contract.canonical_sha256_v1(
            lineup_ids
        ),
        "candidate_rosters_sha256": contract.canonical_sha256_v1(
            [roster] * len(lineup_ids)
        ),
        "candidate_rows_sha256": contract.canonical_sha256_v1(candidates),
        "expected_training_score_matrix_sha256": "a" * 64,
        "expected_training_score_shape": [
            len(lineup_ids), 4 * contract.WORLDS_PER_BLOCK,
        ],
        "policy": dict(contract.POLICY_CLAIMS),
    }
    body["projection_sha256"] = contract.canonical_sha256_v1(body)
    return contract.validate_narrow_projection_v1(body), ledger, roster


def _matrix_response(
    capability_value: object, process_ordinal: int,
    training_score_matrix: object,
) -> tuple[dict[str, object], int]:
    capability = worker.validate_matrix_capability_v1(capability_value)
    assert capability["process_ordinal"] == process_ordinal
    projection = capability["projection_scientific_binding"]
    scores = np.asarray(training_score_matrix)
    assert worker._matrix_descriptor_v1(
        scores,
        expected_matrix_sha256=projection["training_score_matrix_sha256"],
    ) == capability["matrix_descriptor"]
    lineup_ids = [row["lineup_id"] for row in projection["candidates"]]
    full_ledger = contract._ordered_score_row_ledger_fixture_v1(
        lineup_ids, scores
    )
    cells = [
        _selection_cell(
            projection=projection,
            sample=view,
            strategy=strategy,
            ledger=full_ledger,
            replicate=int(replicate["replicate"]),
        )
        for replicate in capability["samples"]["replicates"]
        for view in replicate["views"]
        for strategy in capability["strategies"]
    ]
    body = {
        "schema_version": worker.MATRIX_RESPONSE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "phase": capability["phase"],
        "source_ordinal": capability["source_ordinal"],
        "fold_ordinal": capability["fold_ordinal"],
        "process_ordinal": capability["process_ordinal"],
        "matrix_capability_sha256": capability["matrix_capability_sha256"],
        "runtime_evidence": _runtime(
            "matrix-selector",
            process_ordinal,
            pid=20_000 + process_ordinal,
            execution=f"matrix-{process_ordinal}",
        ),
        "full_candidate_score_row_ledger": full_ledger,
        "full_candidate_score_row_ledger_sha256": contract.canonical_sha256_v1(
            full_ledger
        ),
        "cells": cells,
        "cells_sha256": contract.canonical_sha256_v1(cells),
        "fit_count": len(cells),
        "transport_imported": False,
        "raw_read_callable_received": False,
        "heldout_artifact_identity_received": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    body["runtime_evidence_sha256"] = body["runtime_evidence"][
        "runtime_evidence_sha256"
    ]
    body["matrix_response_sha256"] = contract.canonical_sha256_v1(body)
    retained = worker.validate_matrix_response_v1(body, capability=capability)
    return retained, len(contract.canonical_json_bytes_v1(retained))


def _load_artifact(
    receipt: dict[str, object], _raw: bytes,
) -> SimpleNamespace:
    player_ids = tuple(row["id"] for row in _catalog())
    return SimpleNamespace(
        block=receipt["block"],
        player_ids=player_ids,
        player_draws=np.zeros(
            (len(player_ids), contract.WORLDS_PER_BLOCK), dtype=np.float32
        ),
    )


def _contains_callable(value: object) -> bool:
    if callable(value):
        return True
    if isinstance(value, dict):
        return any(_contains_callable(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_callable(child) for child in value)
    return False


def _bootstrap_process_specs() -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for role in contract.PROCESS_ROLES:
        if str(role).endswith("fold-selector"):
            chain = assembler.canonical_fold_process_chain_v1()
        elif str(role).endswith("slate-assembler"):
            command = assembler.canonical_slate_assembler_command_v1()
            chain = [{
                "component_role": "main",
                "command": command,
                "entrypoint_path": command[1],
                "entrypoint_sha256": sha256(
                    Path(command[1]).read_bytes()
                ).hexdigest(),
            }]
        else:
            chain = [{
                "component_role": "main",
                "command": ["/usr/bin/true"],
                "entrypoint_path": "/usr/bin/true",
                "entrypoint_sha256": "0" * 64,
            }]
        specs.append({"process_role": role, "process_chain": chain})
    return specs


def _build_execution_fixture() -> dict[str, object]:
    store = _Store()
    prefix = contract.OUTPUT_NAMESPACE + "fixture-selection-execution/"
    topology = contract.build_result_topology_v1(prefix)
    topology_identity = store.add_body(
        prefix + "authorities/topology.json", topology
    )
    launch_intent_identity = store.add_body(
        prefix + "authorities/run-and-launch.json",
        {
            "schema_version": "fixture-pre-design-run-authorization/v1",
            "contract_id": contract.CONTRACT_ID,
            "cloud_execution_attestation": False,
        },
    )
    bootstrap_manifest = contract.build_bootstrap_manifest_v1(
        topology=topology,
        topology_identity=topology_identity,
        run_identity=launch_intent_identity,
        code_commit="a" * 40,
        image_digest="sha256:" + "b" * 64,
        process_specs=_bootstrap_process_specs(),
    )
    bootstrap_manifest_identity = store.add_body(
        prefix + "authorities/bootstrap-manifest.json", bootstrap_manifest
    )
    design = contract.build_design_v1(
        output_prefix=prefix,
        code_identity={
            "uri": "gs://fixture/code/contract.py",
            "generation": "1",
            "sha256": "d" * 64,
            "bytes": 1,
        },
        report_identity={
            "uri": "gs://fixture/docs/contract.md",
            "generation": "1",
            "sha256": "e" * 64,
            "bytes": 1,
        },
        topology_identity=topology_identity,
        bootstrap_manifest=bootstrap_manifest,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
    )
    design_uri = next(
        row["uri"] for row in topology["objects"] if row["role"] == "design"
    )
    design_identity = store.add_body(str(design_uri), design)
    artifact_identities = {
        block: store.add_bytes(
            f"gs://fixture/worlds/fixture-slate/{block}.npz",
            f"fixture-world-{block}".encode(),
        )
        for block in contract.WORLD_BLOCKS
    }
    source = {
        "freeze_sha256": "f" * 64,
        "slates": [{
            "slate_id": "fixture-slate",
            "catalog": _catalog(),
            "artifact_receipts": [
                {
                    "season": 2023,
                    "week": 1,
                    "block": block,
                    "candidate_rows": 1,
                    **artifact_identities[block],
                }
                for block in contract.WORLD_BLOCKS
            ],
        }],
    }
    source_identity = store.add_body(
        "gs://fixture/later-source/fixture-source.json", source
    )
    scores = np.zeros(
        (contract.ENTRY_BUDGET, 4 * contract.WORLDS_PER_BLOCK),
        dtype=np.float64,
    )
    score_sha = contract._float64_matrix_sha256_v1(
        scores, label="fixture scores"
    )
    projections = [
        _projection(
            fold,
            source_identity=source_identity,
            artifact_identities=artifact_identities,
            score_sha256=score_sha,
        )
        for fold in range(contract.FOLDS_PER_SLATE)
    ]
    bundle = contract.build_projection_bundle_v1(
        source_ordinal=0, fold_projections=projections
    )
    bundle_uri = next(
        row["uri"] for row in topology["objects"]
        if row["role"] == "projection"
    )
    bundle_identity = store.add_body(str(bundle_uri), bundle)
    fold_budgets = [
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
    fold_budget_identities = [
        store.add_body(
            prefix + f"process-budgets/broad-fold-{fold}.json", budget
        )
        for fold, budget in enumerate(fold_budgets)
    ]
    assembler_budget = contract.compile_process_budget_v1(
        process_role="broad-slate-assembler",
        projection_bundle=bundle,
        projection_bundle_identity=bundle_identity,
        topology=topology,
        topology_identity=topology_identity,
        source_ordinal=0,
    )
    assembler_budget_identity = store.add_body(
        prefix + "process-budgets/broad-assembler.json", assembler_budget
    )
    fold_requests = [
        assembler.build_fold_worker_request_v1(
            phase=contract.BROAD_SCREEN_PHASE,
            source_ordinal=0,
            fold_ordinal=fold,
            design_identity=design_identity,
            topology_identity=topology_identity,
            projection_bundle_identity=bundle_identity,
            process_budget_identity=fold_budget_identities[fold],
        )
        for fold in range(contract.FOLDS_PER_SLATE)
    ]
    assembler_request = assembler.build_slate_assembler_request_v1(
        phase=contract.BROAD_SCREEN_PHASE,
        source_ordinal=0,
        design_identity=design_identity,
        topology_identity=topology_identity,
        projection_bundle_identity=bundle_identity,
        assembler_process_budget_identity=assembler_budget_identity,
        worker_process_budget_identities=fold_budget_identities,
    )
    captured_capabilities: list[dict[str, object]] = []

    def spawn_matrix(
        capability: dict[str, object], ordinal: int, scores: object,
    ) -> tuple[dict[str, object], int]:
        reads_before = len(store.reads)
        captured_capabilities.append(deepcopy(capability))
        result = _matrix_response(capability, ordinal, scores)
        assert len(store.reads) == reads_before
        return result

    children = [
        runner._run_fold_broker_fixture_v1(
            fold_requests[fold],
            broker_runtime_evidence=_runtime(
                "fold-broker", fold, pid=10_000 + fold,
                execution=f"broker-{fold}",
            ),
            read_exact=store.read_exact,
            validate_later_source=lambda value: value,
            players_from_catalog=runner._players,
            load_artifact_worlds=_load_artifact,
            cross_score=lambda *_args, **_kwargs: scores,
            score_matrix_sha256=lambda value: contract._float64_matrix_sha256_v1(
                value, label="fixture cross score"
            ),
            spawn_matrix=spawn_matrix,
        )
        for fold in range(contract.FOLDS_PER_SLATE)
    ]
    return {
        "store": store,
        "topology": topology,
        "launch_intent_identity": launch_intent_identity,
        "design_identity": design_identity,
        "topology_identity": topology_identity,
        "bundle_identity": bundle_identity,
        "bundle": bundle,
        "scores": scores,
        "artifact_identities": artifact_identities,
        "fold_budgets": fold_budgets,
        "fold_requests": fold_requests,
        "assembler_request": assembler_request,
        "children": children,
        "captured_capabilities": captured_capabilities,
    }


@pytest.fixture(scope="module")
def execution_fixture() -> dict[str, object]:
    return _build_execution_fixture()


@pytest.fixture(scope="module")
def assembled_envelope(
    execution_fixture: dict[str, object],
) -> dict[str, object]:
    store = execution_fixture["store"]
    return assembler.run_slate_assembler_v1(
        execution_fixture["assembler_request"],
        read_exact=store.read_exact,
        publish_create_once=store.publish,
        assembler_runtime_evidence=_runtime(
            "slate-assembler", 0, pid=30_000, execution="assembler-0"
        ),
        child_envelopes=execution_fixture["children"],
    )


def test_terminal_reopens_selection_specific_process_budget_lattice(
    execution_fixture: dict[str, object],
) -> None:
    request = execution_fixture["assembler_request"]
    assert "process_budget_identity" not in request
    task = {
        "phase": contract.BROAD_SCREEN_PHASE,
        "process_role": "broad-slate-assembler",
        "source_ordinal": 0,
        "process_ordinal": 0,
        "request": request,
    }

    bindings = task_manifest._exact_task_process_budget_bindings_v1(
        manifest={"layer_id": "broad-selection-receipt"},
        task=task,
        read_exact=execution_fixture["store"].read_exact,
    )

    expected_identities = [
        request["assembler_process_budget_identity"],
        *request["worker_process_budget_identities"],
    ]
    assert [row["process_budget_identity"] for row in bindings] == (
        expected_identities
    )
    assert [row["process_budget_sha256"] for row in bindings] == [
        budget["process_budget_sha256"]
        for budget in [
            contract.compile_process_budget_v1(
                process_role="broad-slate-assembler",
                projection_bundle=execution_fixture["bundle"],
                projection_bundle_identity=execution_fixture["bundle_identity"],
                topology=execution_fixture["topology"],
                topology_identity=execution_fixture["topology_identity"],
                source_ordinal=0,
            ),
            *execution_fixture["fold_budgets"],
        ]
    ]

    poisoned_budget = assembler._strict_json(
        execution_fixture["store"].read_exact(
            request["worker_process_budget_identities"][0]
        ),
        label="poisoned worker process budget",
    )
    poisoned_budget["fold_ordinal"] = 0
    poisoned_budget["process_budget_sha256"] = contract.canonical_sha256_v1({
        key: value for key, value in poisoned_budget.items()
        if key != "process_budget_sha256"
    })
    poisoned_identity = execution_fixture["store"].add_body(
        contract.OUTPUT_NAMESPACE
        + "fixture-selection-execution/process-budgets/poisoned-fold.json",
        poisoned_budget,
    )
    poisoned_request = deepcopy(request)
    poisoned_request["worker_process_budget_identities"][0] = poisoned_identity
    with pytest.raises(
        task_manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error,
        match="fold/process differs",
    ):
        task_manifest._exact_task_process_budget_bindings_v1(
            manifest={"layer_id": "broad-selection-receipt"},
            task={**task, "request": poisoned_request},
            read_exact=execution_fixture["store"].read_exact,
        )


def test_successful_selection_envelope_terminalizes_exact_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_environment = _environment

    def shared_execution_environment(
        process_ordinal: int, *, execution: str,
    ) -> dict[str, str]:
        del execution
        environment = original_environment(
            process_ordinal, execution="selection-terminal-execution"
        )
        environment["CLOUD_RUN_TASK_INDEX"] = "0"
        return environment

    monkeypatch.setattr(
        sys.modules[__name__], "_environment", shared_execution_environment
    )
    fixture = _build_execution_fixture()
    store = fixture["store"]
    request = fixture["assembler_request"]
    assembler_envelope = assembler.run_slate_assembler_v1(
        request,
        read_exact=store.read_exact,
        publish_create_once=store.publish,
        assembler_runtime_evidence=_runtime(
            "slate-assembler",
            0,
            pid=30_000,
            execution="selection-terminal-execution",
        ),
        child_envelopes=fixture["children"],
    )
    raw_request = contract.canonical_json_bytes_v1(request)
    binding_evidence = _task_binding_evidence(request, raw_request)
    bound_envelope = runner.bind_task_evidence_to_assembler_envelope_v1(
        assembler_envelope,
        binding_evidence,
        request=request,
        raw_request=raw_request,
    )
    child_stdout = contract.canonical_json_bytes_v1(bound_envelope)

    output = next(
        row for row in fixture["topology"]["objects"]
        if row["role"] == "broad-selection-receipt"
    )
    output_descriptor = {
        "topology_ordinal": output["ordinal"],
        "role": output["role"],
        "source_ordinal": 0,
        "uri": output["uri"],
        "maximum_bytes": contract.BROAD_SELECTION_RECEIPT_MAX_BYTES,
        "create_once": True,
        "prior_identity": None,
    }
    task = {
        "task_index": 0,
        "source_ordinal": 0,
        "process_ordinal": 0,
        "phase": contract.BROAD_SCREEN_PHASE,
        "process_role": "broad-slate-assembler",
        "task_binding_sha256": "2" * 64,
        "task_science_binding_sha256": "5" * 64,
        "request": request,
        "request_sha256": sha256(raw_request).hexdigest(),
        "request_bytes": len(raw_request),
        "expected_outputs": [output_descriptor],
        "expected_outputs_sha256": "3" * 64,
        "child_command_sha256": "4" * 64,
        "child_stdout_byte_ceiling": 4_000_000,
        "child_stderr_byte_ceiling": 1_000_000,
        "maximum_wall_seconds": 7_200,
    }
    design = assembler._strict_json(
        store.read_exact(fixture["design_identity"]), label="fixture design"
    )
    terminal_manifest = {
        "task_count": 1,
        "layer_id": "broad-selection-receipt",
        "task_manifest_sha256": "1" * 64,
        "task_bindings": [task],
        "required_process_specs": _bootstrap_process_specs(),
        "bootstrap_manifest_identity": design["bootstrap_manifest_identity"],
        "bootstrap_manifest_sha256": design["bootstrap_manifest"][
            "bootstrap_manifest_sha256"
        ],
        "pre_design_run_authorization_identity": fixture[
            "launch_intent_identity"
        ],
        "code_commit": "a" * 40,
        "image_digest": "sha256:" + "b" * 64,
        "reused_job_name": "fixture-selection",
    }
    original_bind_body = task_manifest._bind_body

    def bind_manifest_or_exact_body(
        value: object, identity: object, *, label: str,
    ) -> dict[str, object]:
        if label in {"terminal task manifest", "child evidence task manifest"}:
            return dict(identity)
        return original_bind_body(value, identity, label=label)

    def prove_exact_identity(identity: MappingForTest) -> dict[str, object]:
        retained = contract._safe_object_identity(
            identity, label="fixture terminal publication"
        )
        raw = store.read_exact(retained)
        assert len(raw) == retained["bytes"]
        assert sha256(raw).hexdigest() == retained["sha256"]
        return retained

    monkeypatch.setattr(
        task_manifest, "validate_task_manifest_v1", lambda value: dict(value)
    )
    monkeypatch.setattr(task_manifest, "_bind_body", bind_manifest_or_exact_body)
    monkeypatch.setattr(
        task_manifest,
        "build_dispatcher_runtime_evidence_v1",
        lambda **_kwargs: {
            "task_index": 0,
            "cloud_execution_name": "selection-terminal-execution",
            "dispatcher_runtime_evidence_sha256": "6" * 64,
        },
    )
    terminal = task_manifest.build_task_terminal_evidence_v1(
        manifest=terminal_manifest,
        manifest_identity=binding_evidence["manifest_identity"],
        task_index=0,
        cloud_execution_name="selection-terminal-execution",
        child_exit_code=0,
        child_stdout=child_stdout,
        child_stderr=b"",
        elapsed_milliseconds=1_000,
        read_exact=store.read_exact,
        prove_exact_identity=prove_exact_identity,
        dispatcher_kernel_observed_command=["fixture-dispatcher"],
        dispatcher_selected_environment={"FIXTURE": "1"},
    )

    assert terminal["task_completed"] is True
    assert terminal["child_exit_code"] == 0
    assert terminal["child_task_binding_evidence"] == binding_evidence
    assert terminal["publication_identities"] == [
        bound_envelope["selection_receipt_identity"]
    ]
    assert terminal["publication_evidence"][0][
        "publication_generation_exact_reopen_proved"
    ] is True


def test_broker_reads_four_blocks_and_matrix_child_has_no_raw_capability(
    execution_fixture: dict[str, object],
) -> None:
    children = execution_fixture["children"]
    capabilities = execution_fixture["captured_capabilities"]
    artifact_identities = execution_fixture["artifact_identities"]
    assert len(children) == len(capabilities) == contract.FOLDS_PER_SLATE
    for fold, (child, capability) in enumerate(zip(children, capabilities)):
        assert assembler.validate_fold_child_envelope_v1(
            child,
            request=execution_fixture["fold_requests"][fold],
            process_budget=execution_fixture["fold_budgets"][fold],
        ) == child
        assert child["training_artifact_body_read_count"] == 4
        assert child["observed_fit_count"] == 64
        assert child["child_execution_evidence"][
            "outer_launch_authority_binding_required"
        ] is True
        assert not _contains_callable(capability)
        raw = contract.canonical_json_bytes_v1(capability)
        assert "matrix" not in capability
        assert capability["matrix_bytes_embedded"] is False
        assert capability["inherited_local_matrix_fd_exposed"] is True
        assert capability[
            "object_store_transport_capability_exposed"
        ] is False
        assert capability["matrix_descriptor"]["raw_bytes"] == (
            execution_fixture["scores"].nbytes
        )
        assert "base64" not in _walk_keys(capability)
        heldout_identity = artifact_identities[contract.WORLD_BLOCKS[fold]]
        assert str(heldout_identity["uri"]).encode() not in raw
        projection = capability["projection_scientific_binding"]
        assert not any(
            key in {"uri", "generation", "artifact_identity", "read_exact"}
            for key in _walk_keys(projection)
        )


def _walk_keys(value: object) -> list[str]:
    if isinstance(value, dict):
        return [
            *(str(key).lower() for key in value),
            *(key for child in value.values() for key in _walk_keys(child)),
        ]
    if isinstance(value, list):
        return [key for child in value for key in _walk_keys(child)]
    return []


@contextmanager
def _sealed_memfd_bytes(
    raw: bytes, *, seals: int = worker.MATRIX_REQUIRED_SEALS,
    readonly: bool = True,
):
    writable_fd = os.memfd_create(
        worker.MATRIX_MEMFD_NAME,
        os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING,
    )
    exposed_fd: int | None = None
    try:
        offset = 0
        while offset < len(raw):
            count = os.write(writable_fd, raw[offset:])
            assert count > 0
            offset += count
        if seals:
            fcntl.fcntl(writable_fd, fcntl.F_ADD_SEALS, seals)
        if readonly:
            exposed_fd = os.open(
                f"/proc/self/fd/{writable_fd}", os.O_RDONLY | os.O_CLOEXEC
            )
            os.close(writable_fd)
            writable_fd = -1
        else:
            exposed_fd = writable_fd
            writable_fd = -1
        yield exposed_fd
    finally:
        if writable_fd >= 0:
            os.close(writable_fd)
        if exposed_fd is not None:
            try:
                os.close(exposed_fd)
            except OSError as exc:
                if exc.errno != errno.EBADF:
                    raise


def _small_ipc_matrix() -> tuple[np.ndarray, dict[str, object], bytes]:
    matrix = np.arange(
        4 * contract.WORLDS_PER_BLOCK, dtype=np.float64
    ).reshape((1, 4 * contract.WORLDS_PER_BLOCK))
    matrix_sha256 = contract._float64_matrix_sha256_v1(
        matrix, label="IPC adversarial matrix"
    )
    descriptor = worker._matrix_descriptor_v1(
        matrix, expected_matrix_sha256=matrix_sha256
    )
    return matrix, descriptor, memoryview(matrix).cast("B").tobytes()


def test_inherited_matrix_fd_is_exact_anonymous_and_read_only() -> None:
    matrix, descriptor, raw = _small_ipc_matrix()
    assert descriptor["raw_bytes"] == len(raw) == matrix.nbytes
    with _sealed_memfd_bytes(raw) as fd_number:
        scores, matrix_mapping = worker._map_inherited_matrix_readonly_v1(
            descriptor, fd_number=fd_number
        )
        assert np.array_equal(scores, matrix)
        assert scores.flags.writeable is False
        with pytest.raises(ValueError, match="read-only"):
            scores[0, 0] = -1.0
        with pytest.raises(OSError) as closed:
            os.fstat(fd_number)
        assert closed.value.errno == errno.EBADF
        del scores
        matrix_mapping.close()


def test_inherited_matrix_fd_rejects_absent_and_wrong_fd() -> None:
    _matrix, descriptor, _raw = _small_ipc_matrix()
    absent_fd = os.dup(1)
    os.close(absent_fd)
    with pytest.raises(
        worker.CorpusR6CurrentBankSelectionFoldWorkerV1Error,
        match="FD is absent",
    ):
        worker._map_inherited_matrix_readonly_v1(
            descriptor, fd_number=absent_fd
        )
    read_fd, write_fd = os.pipe()
    try:
        with pytest.raises(
            worker.CorpusR6CurrentBankSelectionFoldWorkerV1Error,
            match="not one regular anonymous memfd",
        ):
            worker._map_inherited_matrix_readonly_v1(
                descriptor, fd_number=read_fd
            )
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_inherited_matrix_fd_rejects_writable_anonymous_file() -> None:
    _matrix, descriptor, raw = _small_ipc_matrix()
    with _sealed_memfd_bytes(raw, readonly=False) as writable_fd:
        with pytest.raises(
            worker.CorpusR6CurrentBankSelectionFoldWorkerV1Error,
            match="not read-only",
        ):
            worker._map_inherited_matrix_readonly_v1(
                descriptor, fd_number=writable_fd
            )


@pytest.mark.parametrize(
    "seals",
    [
        0,
        worker.MATRIX_REQUIRED_SEALS & ~fcntl.F_SEAL_WRITE,
        worker.MATRIX_REQUIRED_SEALS & ~fcntl.F_SEAL_GROW,
        worker.MATRIX_REQUIRED_SEALS & ~fcntl.F_SEAL_SHRINK,
        worker.MATRIX_REQUIRED_SEALS & ~fcntl.F_SEAL_SEAL,
    ],
)
def test_inherited_matrix_fd_rejects_missing_or_incomplete_seals(
    seals: int,
) -> None:
    _matrix, descriptor, raw = _small_ipc_matrix()
    with _sealed_memfd_bytes(raw, seals=seals) as fd_number:
        with pytest.raises(
            worker.CorpusR6CurrentBankSelectionFoldWorkerV1Error,
            match="exact seal set differs",
        ):
            worker._map_inherited_matrix_readonly_v1(
                descriptor, fd_number=fd_number
            )


@pytest.mark.parametrize("delta", [-8, 8])
def test_inherited_matrix_fd_rejects_truncated_or_extra_bytes(delta: int) -> None:
    _matrix, descriptor, raw = _small_ipc_matrix()
    changed = raw[:delta] if delta < 0 else raw + (b"\0" * delta)
    with _sealed_memfd_bytes(changed) as fd_number:
        with pytest.raises(
            worker.CorpusR6CurrentBankSelectionFoldWorkerV1Error,
            match="byte count differs",
        ):
            worker._map_inherited_matrix_readonly_v1(
                descriptor, fd_number=fd_number
            )


def test_inherited_matrix_fd_rejects_mutated_exact_length_bytes() -> None:
    _matrix, descriptor, raw = _small_ipc_matrix()
    changed = bytearray(raw)
    changed[-1] ^= 1
    with _sealed_memfd_bytes(bytes(changed)) as fd_number:
        with pytest.raises(
            worker.CorpusR6CurrentBankSelectionFoldWorkerV1Error,
            match="raw hash differs",
        ):
            worker._map_inherited_matrix_readonly_v1(
                descriptor, fd_number=fd_number
            )


def test_selector_failure_is_not_masked_by_retained_mmap_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    matrix, descriptor, _raw = _small_ipc_matrix()
    retained_views: list[np.ndarray] = []

    class _SelectorSentinel(RuntimeError):
        pass

    def fail_selector(
        _capability: object, *, runtime_evidence: object,
        training_score_matrix: np.ndarray,
    ) -> dict[str, object]:
        del runtime_evidence
        with pytest.raises(OSError) as closed:
            os.fstat(worker.MATRIX_ANONYMOUS_FD)
        assert closed.value.errno == errno.EBADF
        descendant = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import errno,os,sys; "
                    f"fd={worker.MATRIX_ANONYMOUS_FD}; "
                    "\ntry: os.fstat(fd)"
                    "\nexcept OSError as exc: "
                    "sys.exit(0 if exc.errno == errno.EBADF else 2)"
                    "\nelse: sys.exit(3)"
                ),
            ],
            close_fds=False,
            check=False,
        )
        assert descendant.returncode == 0
        retained_views.append(training_score_matrix)
        raise _SelectorSentinel("original selector failure")

    monkeypatch.setattr(
        worker, "_execute_registered_selection_v1", fail_selector
    )
    with runner._readonly_anonymous_matrix_fd_v1(matrix, descriptor):
        with pytest.raises(_SelectorSentinel, match="original selector failure"):
            worker._execute_with_inherited_matrix_v1(
                {"matrix_descriptor": descriptor}, runtime_evidence={}
            )
    retained_views.clear()


def test_sealed_matrix_memfd_cannot_be_mutated_after_reopen() -> None:
    matrix, descriptor, raw = _small_ipc_matrix()
    with runner._readonly_anonymous_matrix_fd_v1(
        matrix, descriptor
    ) as fd_number:
        assert os.readlink(f"/proc/self/fd/{fd_number}") == (
            worker.MATRIX_MEMFD_LINK_TARGET
        )
        assert fcntl.fcntl(fd_number, fcntl.F_GET_SEALS) == (
            worker.MATRIX_REQUIRED_SEALS
        )
        assert fcntl.fcntl(fd_number, fcntl.F_GETFL) & os.O_ACCMODE == (
            os.O_RDONLY
        )
        reopened = os.open(
            f"/proc/self/fd/{fd_number}", os.O_RDWR | os.O_CLOEXEC
        )
        try:
            with pytest.raises(OSError) as overwrite:
                os.pwrite(reopened, b"x", 0)
            assert overwrite.value.errno == errno.EPERM
            with pytest.raises(OSError) as truncate:
                os.ftruncate(reopened, len(raw) - 8)
            assert truncate.value.errno == errno.EPERM
            with pytest.raises(OSError) as truncate_on_reopen:
                os.open(
                    f"/proc/self/fd/{fd_number}",
                    os.O_RDWR | os.O_TRUNC | os.O_CLOEXEC,
                )
            assert truncate_on_reopen.value.errno == errno.EPERM
            assert os.pread(reopened, len(raw), 0) == raw
        finally:
            os.close(reopened)


def test_bounded_subprocess_inherits_matrix_fd_only_when_explicit() -> None:
    matrix, descriptor, _raw = _small_ipc_matrix()
    expected = str(descriptor["raw_sha256"]).encode("ascii")
    program = (
        "import hashlib,os;"
        f"fd={worker.MATRIX_ANONYMOUS_FD};"
        "size=os.fstat(fd).st_size;"
        "raw=os.pread(fd,size,0);"
        "print(hashlib.sha256(raw).hexdigest(),end='')"
    )
    with runner._readonly_anonymous_matrix_fd_v1(matrix, descriptor) as fd_number:
        output = runner._bounded_subprocess(
            command=[os.path.abspath(sys.executable), "-c", program],
            input_bytes=b"",
            output_ceiling=64,
            environment=os.environ,
            pass_fds=(fd_number,),
        )
    assert output == expected

    tree = ast.parse(Path(runner.__file__).read_text(encoding="utf-8"))
    pass_fd_call_owners: list[str] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "_bounded_subprocess"
                and any(keyword.arg == "pass_fds" for keyword in child.keywords)
            ):
                pass_fd_call_owners.append(node.name)
    assert pass_fd_call_owners == ["_spawn_matrix_official"]


def test_spawn_matrix_official_roundtrips_canonical_child(
    execution_fixture: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capability = execution_fixture["captured_capabilities"][0]
    for key in assembler._REDIRECT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in _environment(0, execution="canonical-matrix-child").items():
        monkeypatch.setenv(key, value)

    response, output_bytes = runner._spawn_matrix_official(
        capability,
        execution_fixture["scores"],
        process_ordinal=0,
    )

    assert output_bytes == len(contract.canonical_json_bytes_v1(response))
    assert worker.validate_matrix_response_v1(
        response, capability=capability
    ) == response
    runtime = response["runtime_evidence"]
    assert runtime["command"] == assembler.canonical_matrix_selector_command_v1()
    assert runtime["process_ordinal"] == 0


def test_fifth_identity_is_unaddressable_at_raw_broker_boundary(
    execution_fixture: dict[str, object],
) -> None:
    store = execution_fixture["store"]
    identities = execution_fixture["artifact_identities"]
    gate = runner._ExactFourBlockBodyBrokerV1(
        allowed_by_role={
            "later-source": {
                "uri": "gs://fixture/source",
                "generation": "1",
                "sha256": "0" * 64,
                "bytes": 1,
            },
            **{
                f"training-world-{block}": identities[block]
                for block in contract.WORLD_BLOCKS[1:]
            },
        },
        read_exact=store.read_exact,
        starting_ordinal=0,
    )
    with pytest.raises(runner.SelectionExecutionV1Error, match="not addressable"):
        gate.read("training-world-R0", identities["R0"])


def test_fixed_command_runtime_and_request_reject_spoofing(
    execution_fixture: dict[str, object],
) -> None:
    request = deepcopy(execution_fixture["fold_requests"][0])
    request["command"] = ["/tmp/attacker", "--select"]
    request["worker_request_sha256"] = contract.canonical_sha256_v1({
        key: value for key, value in request.items()
        if key != "worker_request_sha256"
    })
    with pytest.raises(
        assembler.CorpusR6CurrentBankSelectionAssemblerV1Error,
        match="request fields differ",
    ):
        assembler.validate_fold_worker_request_v1(request)
    with pytest.raises(
        assembler.CorpusR6CurrentBankSelectionAssemblerV1Error,
        match="command differs",
    ):
        assembler.derive_observed_runtime_evidence_v1(
            mode="fold-broker",
            process_ordinal=0,
            environ=_environment(0, execution="spoof"),
            argv=[sys.executable, "/tmp/unregistered.py", "fold-broker"],
            pid=1,
            parent_pid=0,
        )
    runtime = _runtime("fold-broker", 0, pid=1, execution="derived")
    runtime["code_commit"] = "c" * 40
    with pytest.raises(
        assembler.CorpusR6CurrentBankSelectionAssemblerV1Error,
        match="self hash differs",
    ):
        assembler.validate_observed_runtime_evidence_v1(runtime)
    assert "select_from_matrix" not in inspect.signature(
        runner.run_fold_broker_v1
    ).parameters
    assert "command" not in inspect.signature(
        assembler.build_fold_worker_request_v1
    ).parameters
    assert "_execute_registered_selection_v1" not in worker.__all__


def test_subprocess_capture_kills_before_stdout_ceiling() -> None:
    with pytest.raises(
        runner.SelectionExecutionV1Error,
        match="exceeded precharged byte ceiling",
    ):
        runner._bounded_subprocess(
            command=[
                str(Path(sys.executable).resolve()),
                "-c",
                "import sys; sys.stdout.write('x' * 4096)",
            ],
            input_bytes=b"",
            output_ceiling=64,
            environment=os.environ,
        )


def test_assembler_stdout_streaming_cap_accepts_exact_and_rejects_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty_raw = contract.canonical_json_bytes_v1({"payload": ""})
    exact = {
        "payload": "x" * (
            runner.ASSEMBLER_STDOUT_BYTE_CEILING - len(empty_raw)
        )
    }
    exact_raw = contract.canonical_json_bytes_v1(exact)
    assert len(exact_raw) == runner.ASSEMBLER_STDOUT_BYTE_CEILING
    output = io.BytesIO()
    monkeypatch.setattr(
        runner.sys, "stdout", SimpleNamespace(buffer=output)
    )
    runner._emit_bounded(
        exact, ceiling=runner.ASSEMBLER_STDOUT_BYTE_CEILING
    )
    assert output.getvalue() == exact_raw

    plus_one = {"payload": exact["payload"] + "x"}
    assert len(contract.canonical_json_bytes_v1(plus_one)) == (
        runner.ASSEMBLER_STDOUT_BYTE_CEILING + 1
    )
    overflow_output = io.BytesIO()
    monkeypatch.setattr(
        runner.sys, "stdout", SimpleNamespace(buffer=overflow_output)
    )
    with pytest.raises(
        runner.SelectionExecutionV1Error,
        match="stdout envelope exceeds byte ceiling",
    ):
        runner._emit_bounded(
            plus_one, ceiling=runner.ASSEMBLER_STDOUT_BYTE_CEILING
        )
    assert overflow_output.getvalue() == b""


def test_assembler_stdout_memory_accounting_fits_dispatcher_rss_budget() -> None:
    assert runner.ASSEMBLER_STDOUT_BYTE_CEILING == 4_000_000
    assert runner.ASSEMBLER_STDOUT_DUPLICATE_CAPTURE_BYTES == 8_000_001
    assert runner.ASSEMBLER_STDOUT_JSON_VALIDATION_RESERVE_BYTES == 128_000_000
    assert runner.ASSEMBLER_STDOUT_DERIVED_WORST_CASE_RSS_BYTES == 136_064_001
    assert runner.ASSEMBLER_STDOUT_DERIVED_WORST_CASE_RSS_BYTES < (
        runner.DISPATCHER_RSS_BUDGET_BYTES // 3
    )
    # The superseded cap could not fit even the bytearray -> bytes conversion,
    # before JSON decoding or any baseline interpreter/authority memory.
    assert 2 * 512_000_000 + 1 > runner.DISPATCHER_RSS_BUDGET_BYTES

    assert contract.BROAD_SELECTION_RECEIPT_MAX_BYTES == 40_000_000
    assert contract.CONFIRMATION_SELECTION_RECEIPT_MAX_BYTES == 96_000_000
    assert runner.DISPATCHER_SELECTION_RECEIPT_SINGLE_COPY_BYTES == 96_000_000
    assert (
        runner.DISPATCHER_SELECTION_TERMINAL_WORST_CASE_RSS_BYTES
        == 441_145_859
    )
    assert runner.DISPATCHER_SELECTION_TERMINAL_WORST_CASE_RSS_BYTES < (
        runner.DISPATCHER_RSS_BUDGET_BYTES
    )
    assert (
        runner.DISPATCHER_RSS_BUDGET_BYTES
        - runner.DISPATCHER_SELECTION_TERMINAL_WORST_CASE_RSS_BYTES
        == 95_725_053
    )


def test_maximum_selection_wire_shape_fits_phase_publication_ceiling() -> None:
    projection, ledger, _roster = _maximum_selection_wire_shape()
    strategies = contract.frozen_strategies_v1()

    broad_samples = contract.deterministic_equal_count_samples_from_projection_v1(
        projection, phase=contract.BROAD_SCREEN_PHASE
    )
    assert broad_samples["target_count"] == contract.MAX_EQUAL_COUNT_SAMPLE
    broad_cells = [
        _selection_cell(
            projection=projection,
            sample=view,
            strategy=strategy,
            ledger=ledger,
            replicate=0,
        )
        for view in broad_samples["replicates"][0]["views"]
        for strategy in strategies
    ]
    broad_fold = contract._build_selection_fold_receipt_structural_v1(
        source_ordinal=0,
        fold_ordinal=0,
        projection=projection,
        phase=contract.BROAD_SCREEN_PHASE,
        full_candidate_score_row_ledger=ledger,
        cells=broad_cells,
    )
    broad_cells_bytes = len(contract.canonical_json_bytes_v1(broad_cells))
    broad_fold_bytes = len(contract.canonical_json_bytes_v1(broad_fold))

    confirmation_samples = (
        contract.deterministic_equal_count_samples_from_projection_v1(
            projection, phase=contract.CONFIRMATION_PHASE
        )
    )
    longest_pairs = sorted(
        (
            (view["view_id"], strategy["strategy_id"], strategy)
            for view in confirmation_samples["replicates"][0]["views"]
            for strategy in strategies
        ),
        key=lambda row: (
            len(str(row[0]).encode("utf-8"))
            + len(str(row[1]).encode("utf-8")),
            str(row[0]),
            str(row[1]),
        ),
        reverse=True,
    )[: contract.MAXIMUM_CONFIRMATION_NOMINEES]
    confirmation_cells = []
    for replicate in confirmation_samples["replicates"]:
        view_by_id = {
            view["view_id"]: view for view in replicate["views"]
        }
        for view_id, _strategy_id, strategy in longest_pairs:
            confirmation_cells.append(_selection_cell(
                projection=projection,
                sample=view_by_id[view_id],
                strategy=strategy,
                ledger=ledger,
                replicate=int(replicate["replicate"]),
            ))
    confirmation_cells_bytes = len(
        contract.canonical_json_bytes_v1(confirmation_cells)
    )

    assert len(broad_cells) == contract.BROAD_FITS_PER_FOLD == 64
    assert len(confirmation_cells) == (
        contract.SUBSAMPLE_REPLICATES
        * contract.MAXIMUM_CONFIRMATION_NOMINEES
    ) == 192
    assert len(contract.canonical_json_bytes_v1(ledger)) <= 700_000
    assert broad_cells_bytes <= 5_650_000
    assert broad_fold_bytes <= 6_350_000
    assert confirmation_cells_bytes <= 17_000_000

    # The actual N=80 positive receipt has <42 KiB above its five fold
    # bodies.  One full MiB is frozen here as an adversarial allowance for
    # maximum-width top-level identities, child evidence, and nomination
    # fields; 512 bytes covers the two confirmation hashes and longer phase.
    top_level_overhead_ceiling = 1_000_000
    confirmation_fold_delta_ceiling = 512
    broad_receipt_bound = (
        contract.FOLDS_PER_SLATE * broad_fold_bytes
        + top_level_overhead_ceiling
    )
    confirmation_fold_bound = (
        broad_fold_bytes - broad_cells_bytes
        + confirmation_cells_bytes
        + confirmation_fold_delta_ceiling
    )
    confirmation_receipt_bound = (
        contract.FOLDS_PER_SLATE * confirmation_fold_bound
        + top_level_overhead_ceiling
    )
    assert broad_receipt_bound <= contract.BROAD_SELECTION_RECEIPT_MAX_BYTES
    assert (
        confirmation_receipt_bound
        <= contract.CONFIRMATION_SELECTION_RECEIPT_MAX_BYTES
    )


def test_matrix_capability_is_bounded_descriptor_only_at_maximum_metadata(
    execution_fixture: dict[str, object],
) -> None:
    projection, _ledger, _roster = _maximum_selection_wire_shape()
    binding = {
        "projection_sha256": projection["projection_sha256"],
        "slate_id": projection["slate_id"],
        "fit_scope_id": projection["fit_scope_id"],
        "training_blocks": list(projection["training_blocks"]),
        "heldout_block_label": projection["heldout_block"],
        "training_world_columns_sha256": projection[
            "training_world_columns_sha256"
        ],
        "candidates": [dict(row) for row in projection["candidates"]],
        "candidate_lineup_order_sha256": projection[
            "candidate_lineup_order_sha256"
        ],
        "candidate_rosters_sha256": projection["candidate_rosters_sha256"],
        "candidate_rows_sha256": projection["candidate_rows_sha256"],
        "training_score_matrix_sha256": projection[
            "expected_training_score_matrix_sha256"
        ],
        "training_score_shape": projection["expected_training_score_shape"],
    }
    samples = contract.deterministic_equal_count_samples_from_projection_v1(
        projection, phase=contract.BROAD_SCREEN_PHASE
    )
    descriptor_body = {
        "codec": worker.MATRIX_DESCRIPTOR_CODEC,
        "dtype": "float64-le",
        "shape": list(projection["expected_training_score_shape"]),
        "raw_sha256": "b" * 64,
        "raw_bytes": worker.MATRIX_RAW_BYTE_CEILING,
        "matrix_sha256": projection["expected_training_score_matrix_sha256"],
        "fd_number": worker.MATRIX_ANONYMOUS_FD,
    }
    descriptor = worker._with_hash(
        descriptor_body, field="matrix_descriptor_sha256"
    )
    capability = deepcopy(execution_fixture["captured_capabilities"][0])
    capability["projection_scientific_binding"] = binding
    capability["projection_scientific_binding_sha256"] = (
        contract.canonical_sha256_v1(binding)
    )
    capability["samples"] = samples
    capability["samples_sha256"] = contract.canonical_sha256_v1(samples)
    capability["matrix_descriptor"] = descriptor
    capability["matrix_capability_sha256"] = contract.canonical_sha256_v1({
        key: value for key, value in capability.items()
        if key != "matrix_capability_sha256"
    })
    retained = worker.validate_matrix_capability_v1(capability)
    raw = contract.canonical_json_bytes_v1(retained)
    assert descriptor["raw_bytes"] == 1_277_760_000
    assert len(raw) <= worker.MATRIX_CAPABILITY_BYTE_CEILING
    assert len(raw) * 100 < descriptor["raw_bytes"]
    assert "matrix" not in retained
    assert "base64" not in _walk_keys(retained)


def test_invalid_redirect_is_rejected_before_cloud_client(
    execution_fixture: dict[str, object], monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = contract.canonical_json_bytes_v1(execution_fixture["fold_requests"][0])
    monkeypatch.setattr(runner, "_read_stdin_bounded", lambda _limit: raw)
    for key in runner.assembler._REDIRECT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in _environment(0, execution="invalid-preclient").items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("STORAGE_EMULATOR_HOST", "http://attacker.invalid")
    constructed: list[object] = []

    class _ForbiddenClient:
        def __init__(self, **kwargs: object) -> None:
            constructed.append(kwargs)

    monkeypatch.setattr(runner, "GCSExactCreateOnceTransportV1", _ForbiddenClient)
    monkeypatch.setattr(
        runner,
        "observed_process_command_v1",
        lambda **_kwargs: assembler.canonical_fold_broker_command_v1(),
    )
    with pytest.raises(
        assembler.CorpusR6CurrentBankSelectionAssemblerV1Error,
        match="redirect environment",
    ):
        runner.main(["fold-broker"])
    assert constructed == []


def test_no_artifact_assembler_publishes_once_and_binds_five_children(
    execution_fixture: dict[str, object], assembled_envelope: dict[str, object],
) -> None:
    store = execution_fixture["store"]
    result = assembled_envelope
    assert result["child_process_count"] == 5
    assert result["child_fit_count"] == 320
    assert result["publication_count"] == 1
    assert result["assembler_world_artifact_body_read_count"] == 0
    assert result["assembler_selection_algorithm_execution_count"] == 0
    assert result["outer_launch_authority_binding_required"] is True
    assert result["launch_intent_identity"] == execution_fixture[
        "launch_intent_identity"
    ]
    assert result["outer_launch_authority_identity"] == execution_fixture[
        "launch_intent_identity"
    ]
    assert result["selection_receipt_publication_resumed"] is False
    assert result["create_once_resume_exact_generation_proved"] is True
    assert result["child_envelopes_sha256"] == contract.canonical_sha256_v1(
        result["child_envelope_sha256s"]
    )
    assert len(store.publications) == 1
    artifact_uris = {
        identity["uri"]
        for identity in execution_fixture["artifact_identities"].values()
    }
    assert not artifact_uris.intersection(
        row["identity"]["uri"] for row in result["assembler_read_ledger"]
    )


def _request_with_prior_selection(
    request_value: object, prior_identity: object,
) -> dict[str, object]:
    request = deepcopy(request_value)
    request["prior_selection_receipt_identity"] = prior_identity
    request["assembler_request_sha256"] = contract.canonical_sha256_v1({
        key: value for key, value in request.items()
        if key != "assembler_request_sha256"
    })
    return assembler.validate_slate_assembler_request_v1(request)


def _selection_store_without_output(
    execution_fixture: dict[str, object],
) -> tuple[_Store, str]:
    output_uri = next(
        str(row["uri"])
        for row in execution_fixture["topology"]["objects"]
        if row["role"] == "broad-selection-receipt"
    )
    retained = _Store()
    retained.objects = {
        key: raw
        for key, raw in execution_fixture["store"].objects.items()
        if key[0] != output_uri
    }
    return retained, output_uri


def _run_fixture_assembler(
    execution_fixture: dict[str, object], store: _Store,
    request: object,
) -> dict[str, object]:
    return assembler.run_slate_assembler_v1(
        request,
        read_exact=store.read_exact,
        publish_create_once=store.publish,
        assembler_runtime_evidence=_runtime(
            "slate-assembler", 0, pid=31_000, execution="assembler-resume"
        ),
        child_envelopes=execution_fixture["children"],
    )


def test_selection_create_once_exact_resume_and_collision_adversaries(
    execution_fixture: dict[str, object],
) -> None:
    store, output_uri = _selection_store_without_output(execution_fixture)
    first = _run_fixture_assembler(
        execution_fixture, store, execution_fixture["assembler_request"]
    )
    prior = first["selection_receipt_identity"]
    resumed = _run_fixture_assembler(
        execution_fixture,
        store,
        _request_with_prior_selection(
            execution_fixture["assembler_request"], prior
        ),
    )
    assert resumed["selection_receipt_identity"] == prior
    assert resumed["prior_selection_receipt_identity"] == prior
    assert resumed["selection_receipt_publication_resumed"] is True
    assert resumed["create_once_resume_exact_generation_proved"] is True

    with pytest.raises(
        assembler.CorpusR6CurrentBankSelectionAssemblerV1Error,
        match="collision lacks prior",
    ):
        _run_fixture_assembler(
            execution_fixture, store, execution_fixture["assembler_request"]
        )

    wrong_generation = dict(prior)
    wrong_generation["generation"] = "999999"
    with pytest.raises(
        assembler.CorpusR6CurrentBankSelectionAssemblerV1Error,
        match="exact generation is absent",
    ):
        _run_fixture_assembler(
            execution_fixture,
            store,
            _request_with_prior_selection(
                execution_fixture["assembler_request"], wrong_generation
            ),
        )

    changed_store, _ = _selection_store_without_output(execution_fixture)
    changed_prior = changed_store.add_body(
        output_uri,
        {
            "schema_version": contract.SELECTION_RECEIPT_SCHEMA,
            "selection_receipt_sha256": "0" * 64,
            "changed_body": True,
        },
        generation="77",
    )
    with pytest.raises(
        assembler.CorpusR6CurrentBankSelectionAssemblerV1Error,
        match="URI/body hash/size differs",
    ):
        _run_fixture_assembler(
            execution_fixture,
            changed_store,
            _request_with_prior_selection(
                execution_fixture["assembler_request"], changed_prior
            ),
        )

    oversized_prior = dict(prior)
    oversized_prior["bytes"] = contract.BROAD_SELECTION_RECEIPT_MAX_BYTES + 1
    with pytest.raises(
        assembler.CorpusR6CurrentBankSelectionAssemblerV1Error,
        match="prior selection receipt exceeds phase byte ceiling",
    ):
        _request_with_prior_selection(
            execution_fixture["assembler_request"], oversized_prior
        )


def test_confirmation_accepts_only_exact_nomination_publication(
    execution_fixture: dict[str, object],
) -> None:
    store = execution_fixture["store"]
    topology = execution_fixture["topology"]
    nomination_uri = next(
        row["uri"] for row in topology["objects"]
        if row["role"] == "nomination"
    )
    nomination_identity = store.add_body(
        str(nomination_uri), {"schema_version": "fixture-unembedded-nomination"}
    )
    request = assembler.build_fold_worker_request_v1(
        phase=contract.CONFIRMATION_PHASE,
        source_ordinal=0,
        fold_ordinal=0,
        design_identity=execution_fixture["design_identity"],
        topology_identity=execution_fixture["topology_identity"],
        projection_bundle_identity=execution_fixture["bundle_identity"],
        process_budget_identity=execution_fixture["fold_requests"][0][
            "process_budget_identity"
        ],
        nomination_identity=nomination_identity,
    )
    reads_before = len(store.reads)
    with pytest.raises(
        assembler.CorpusR6CurrentBankSelectionAssemblerV1Error,
        match="nomination publication fields differ",
    ):
        assembler._reopen_common_authorities(
            request, read_exact=store.read_exact
        )
    assert str(nomination_uri) in {
        row["uri"] for row in store.reads[reads_before:]
    }
    caller_injected = deepcopy(request)
    caller_injected["broad_phase_authority"] = {"attacker": True}
    caller_injected["worker_request_sha256"] = contract.canonical_sha256_v1({
        key: value for key, value in caller_injected.items()
        if key != "worker_request_sha256"
    })
    with pytest.raises(
        assembler.CorpusR6CurrentBankSelectionAssemblerV1Error,
        match="request fields differ",
    ):
        assembler.validate_fold_worker_request_v1(caller_injected)


def _synthetic_phase_envelopes(
    base_value: object, *, phase: str,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for source in range(contract.PANEL_SLATE_COUNT):
        envelope = deepcopy(base_value)
        envelope["phase"] = phase
        envelope["source_ordinal"] = source
        rows = envelope["child_execution_evidence"]
        for fold, row in enumerate(rows):
            row["phase"] = phase
            row["source_ordinal"] = source
            row["fold_ordinal"] = fold
            row["process_ordinal"] = source * contract.FOLDS_PER_SLATE + fold
            for prefix in ("broker", "matrix"):
                runtime = row[f"{prefix}_runtime_evidence"]
                runtime["process_ordinal"] = row["process_ordinal"]
                runtime["runtime_evidence_sha256"] = contract.canonical_sha256_v1({
                    key: value for key, value in runtime.items()
                    if key != "runtime_evidence_sha256"
                })
                row[f"{prefix}_runtime_evidence_sha256"] = runtime[
                    "runtime_evidence_sha256"
                ]
            row["child_execution_evidence_sha256"] = contract.canonical_sha256_v1({
                key: value for key, value in row.items()
                if key != "child_execution_evidence_sha256"
            })
        envelope["child_execution_evidence_sha256s"] = [
            row["child_execution_evidence_sha256"] for row in rows
        ]
        envelope["child_execution_evidence_set_sha256"] = (
            contract.canonical_sha256_v1(rows)
        )
        envelope["assembler_envelope_sha256"] = contract.canonical_sha256_v1({
            key: value for key, value in envelope.items()
            if key != "assembler_envelope_sha256"
        })
        result.append(envelope)
    return result


@pytest.mark.parametrize(
    "phase", [contract.BROAD_SCREEN_PHASE, contract.CONFIRMATION_PHASE],
)
def test_phase_local_54_by_5_child_lattice_is_exact(
    assembled_envelope: dict[str, object], phase: str,
) -> None:
    envelopes = _synthetic_phase_envelopes(assembled_envelope, phase=phase)
    lattice = assembler.build_phase_child_lattice_v1(
        phase=phase, assembler_envelopes=envelopes
    )
    assert lattice["slate_count"] == 54
    assert lattice["logical_fold_process_count"] == 270
    assert lattice["os_process_count"] == 540
    assert lattice["process_ordinals"] == list(range(270))
    assert lattice["outer_launch_authority_binding_required"] is True
    with pytest.raises(
        assembler.CorpusR6CurrentBankSelectionAssemblerV1Error,
        match="exactly 54",
    ):
        assembler.build_phase_child_lattice_v1(
            phase=phase, assembler_envelopes=envelopes[:-1]
        )
    spliced = deepcopy(envelopes)
    spliced[0]["child_envelopes_sha256"] = "0" * 64
    spliced[0]["assembler_envelope_sha256"] = contract.canonical_sha256_v1({
        key: value for key, value in spliced[0].items()
        if key != "assembler_envelope_sha256"
    })
    with pytest.raises(
        assembler.CorpusR6CurrentBankSelectionAssemblerV1Error,
        match="slate/fold/process binding differs",
    ):
        assembler.build_phase_child_lattice_v1(
            phase=phase, assembler_envelopes=spliced
        )


def test_assembler_dependency_closure_has_no_executable_selection_import() -> None:
    source = Path(assembler.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    ] + [
        str(node.module)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    ]
    assert not any("crossed_screen_selector" in name for name in imports)
    assert "_run_strategy_v2" not in source
    worker_source = Path(worker.__file__).read_text(encoding="utf-8")
    assert "from nfl_dfs.research import " \
        "corpus_r6_current_bank_crossed_screen_selector_v1" in worker_source
    assert "select_from_matrix" not in worker_source


def test_slate_assembler_cli_import_and_runtime_closure(
    execution_fixture: dict[str, object], monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner_path = Path(runner.__file__)
    source = runner_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level_imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            top_level_imports.append(str(node.module))
            top_level_imports.extend(alias.name for alias in node.names)
    forbidden = (
        "corpus_legal_feasibility",
        "lr8_later_period_source",
        "residual_world_columns",
        "corpus_r6_current_bank_crossed_screen_selection_fold_worker_v1",
        "corpus_r6_current_bank_crossed_screen_selector_v1",
    )
    assert not any(
        token in imported
        for imported in top_level_imports
        for token in forbidden
    )

    imported_forbidden: list[str] = []
    original_import = builtins.__import__

    def guarded_import(
        name: str, globals=None, locals=None, fromlist=(), level: int = 0,
    ):
        candidates = [name, *(str(value) for value in (fromlist or ()))]
        matches = [
            value for value in candidates
            if any(token in value for token in forbidden)
        ]
        if matches:
            imported_forbidden.extend(matches)
            raise AssertionError(
                f"assembler mode imported scientific dependency {matches[0]}"
            )
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    spec = importlib.util.spec_from_file_location(
        "selection_runner_assembler_closure_test", runner_path
    )
    assert spec is not None and spec.loader is not None
    isolated = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(
        sys.modules, "selection_runner_assembler_closure_test", isolated
    )
    spec.loader.exec_module(isolated)
    raw = contract.canonical_json_bytes_v1(
        execution_fixture["assembler_request"]
    )
    request = execution_fixture["assembler_request"]
    monkeypatch.setattr(isolated, "_read_stdin_bounded", lambda _limit: raw)
    for key in isolated.assembler._REDIRECT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in _environment(0, execution="assembler-import-closure").items():
        monkeypatch.setenv(key, value)

    class _Transport:
        def __init__(self, **_kwargs: object) -> None:
            pass

        read_exact = execution_fixture["store"].read_exact
        publish_create_once = execution_fixture["store"].publish

    observed: list[object] = []
    monkeypatch.setattr(isolated, "GCSExactCreateOnceTransportV1", _Transport)
    monkeypatch.setattr(
        isolated,
        "observed_process_command_v1",
        lambda **_kwargs: assembler.canonical_slate_assembler_command_v1(),
    )
    monkeypatch.setattr(
        isolated.task_manifest,
        "parse_child_task_binding_environment_v1",
        lambda _environ: {
            "layer_id": "broad-selection-receipt", "task_index": 0,
            "request_sha256": sha256(raw).hexdigest(),
            "child_command_sha256": contract.canonical_sha256_v1({
                "command": assembler.canonical_slate_assembler_command_v1(),
                "entrypoint_sha256": sha256(
                    Path(
                        assembler.canonical_slate_assembler_command_v1()[1]
                    ).read_bytes()
                ).hexdigest(),
            }),
        },
    )
    binding_evidence = _task_binding_evidence(request, raw)
    monkeypatch.setattr(
        isolated,
        "reopen_controller_task_after_client_v1",
        lambda **_kwargs: binding_evidence,
    )
    unbound = {
        "assembler_mode_dependency_closed": True,
        "assembler_request_sha256": request["assembler_request_sha256"],
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": 0,
    }
    unbound["assembler_envelope_sha256"] = contract.canonical_sha256_v1(
        unbound
    )
    monkeypatch.setattr(
        isolated.assembler,
        "run_slate_assembler_v1",
        lambda *_args, **_kwargs: unbound,
    )
    monkeypatch.setattr(
        isolated, "_emit_bounded",
        lambda value, *, ceiling: observed.append((value, ceiling)),
    )
    assert isolated.main(["slate-assembler"]) == 0
    expected_bound = isolated.bind_task_evidence_to_assembler_envelope_v1(
        unbound,
        binding_evidence,
        request=request,
        raw_request=raw,
    )
    assert observed == [
        (expected_bound, isolated.ASSEMBLER_STDOUT_BYTE_CEILING)
    ]
    assert imported_forbidden == []


def _syntactic_child_binding_environment(
    *, layer_id: str, task_index: int,
) -> dict[str, str]:
    raw_manifest = b'{"fixture":"task-manifest"}'
    identity = {
        "uri": contract.OUTPUT_NAMESPACE + "fixture-binding/task-manifest.json",
        "generation": "818181",
        "sha256": sha256(raw_manifest).hexdigest(),
        "bytes": len(raw_manifest),
    }
    return {
        task_manifest.CHILD_MANIFEST_IDENTITY_ENV:
            contract.canonical_json_bytes_v1(identity).decode("utf-8"),
        task_manifest.CHILD_MANIFEST_SELF_HASH_ENV: "1" * 64,
        task_manifest.CHILD_TASK_BINDING_HASH_ENV: "2" * 64,
        task_manifest.CHILD_LAYER_ID_ENV: layer_id,
        task_manifest.CHILD_TASK_INDEX_ENV: str(task_index),
        task_manifest.CHILD_REQUEST_HASH_ENV: "3" * 64,
        task_manifest.CHILD_OUTPUTS_HASH_ENV: "4" * 64,
        task_manifest.CHILD_COMMAND_HASH_ENV: "5" * 64,
    }


@pytest.mark.parametrize(
    "binding_environment",
    [
        {},
        _syntactic_child_binding_environment(
            layer_id="terminal-root", task_index=0
        ),
        _syntactic_child_binding_environment(
            layer_id="broad-selection-receipt", task_index=1
        ),
        {
            **_syntactic_child_binding_environment(
                layer_id="broad-selection-receipt", task_index=0
            ),
            "R6_TASK_HOSTILE_SPLICE": "present",
        },
    ],
)
def test_selection_missing_layer_index_and_spliced_env_fail_before_client(
    execution_fixture: dict[str, object], monkeypatch: pytest.MonkeyPatch,
    binding_environment: dict[str, str],
) -> None:
    raw = contract.canonical_json_bytes_v1(
        execution_fixture["assembler_request"]
    )
    constructed = 0

    class ForbiddenClient:
        def __init__(self, **_kwargs: object) -> None:
            nonlocal constructed
            constructed += 1

    monkeypatch.setattr(runner, "_read_stdin_bounded", lambda _limit: raw)
    monkeypatch.setattr(runner, "GCSExactCreateOnceTransportV1", ForbiddenClient)
    monkeypatch.setattr(
        runner,
        "observed_process_command_v1",
        lambda **_kwargs: assembler.canonical_slate_assembler_command_v1(),
    )
    monkeypatch.setattr(runner.os, "environ", binding_environment)
    with pytest.raises((
        runner.SelectionExecutionV1Error,
        task_manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error,
    )):
        runner.main(["slate-assembler"])
    assert constructed == 0


def test_selection_spliced_request_and_command_hashes_fail_before_client(
    execution_fixture: dict[str, object], monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = contract.canonical_json_bytes_v1(
        execution_fixture["assembler_request"]
    )
    command = assembler.canonical_slate_assembler_command_v1()
    command_sha256 = contract.canonical_sha256_v1({
        "command": command,
        "entrypoint_sha256": sha256(Path(command[1]).read_bytes()).hexdigest(),
    })
    base = _syntactic_child_binding_environment(
        layer_id="broad-selection-receipt", task_index=0
    )
    environments = []
    request_bound = dict(base)
    request_bound[task_manifest.CHILD_REQUEST_HASH_ENV] = sha256(raw).hexdigest()
    environments.append(request_bound)
    command_bound = dict(base)
    command_bound[task_manifest.CHILD_COMMAND_HASH_ENV] = command_sha256
    environments.append(command_bound)
    constructed = 0

    class ForbiddenClient:
        def __init__(self, **_kwargs: object) -> None:
            nonlocal constructed
            constructed += 1

    monkeypatch.setattr(runner, "_read_stdin_bounded", lambda _limit: raw)
    monkeypatch.setattr(runner, "GCSExactCreateOnceTransportV1", ForbiddenClient)
    monkeypatch.setattr(
        runner, "observed_process_command_v1", lambda **_kwargs: command
    )
    for environment in environments:
        monkeypatch.setattr(runner.os, "environ", environment)
        with pytest.raises(
            runner.SelectionExecutionV1Error,
            match="request/command scalar binding differs",
        ):
            runner.main(["slate-assembler"])
    assert constructed == 0


def test_selection_kernel_command_and_full_request_binding_are_exact(
    execution_fixture: dict[str, object],
) -> None:
    command = assembler.canonical_slate_assembler_command_v1()
    raw_command = b"\0".join(
        token.encode("utf-8") for token in command
    ) + b"\0"
    assert runner.observed_process_command_v1(
        mode="slate-assembler", raw_cmdline=raw_command
    ) == command
    with pytest.raises(
        runner.SelectionExecutionV1Error,
        match="canonical selection entrypoint",
    ):
        runner.observed_process_command_v1(
            mode="slate-assembler",
            raw_cmdline=b"\0".join([
                command[0].encode("utf-8"), b"-m", b"hostile.wrapper",
            ]) + b"\0",
        )

    first = b"/usr/bin/python3"
    second = str(Path(runner.__file__).resolve()).encode("utf-8")
    third_length = (
        runner.MAXIMUM_PROCESS_COMMAND_BYTES - len(first) - len(second) - 3
    )
    exact_ceiling = b"\0".join([
        first, second, b"x" * third_length,
    ]) + b"\0"
    assert len(exact_ceiling) == runner.MAXIMUM_PROCESS_COMMAND_BYTES
    with pytest.raises(
        runner.SelectionExecutionV1Error,
        match="canonical selection entrypoint",
    ):
        runner.observed_process_command_v1(
            mode="slate-assembler", raw_cmdline=exact_ceiling
        )
    plus_one = b"\0".join([
        first, second, b"x" * (third_length + 1),
    ]) + b"\0"
    assert len(plus_one) == runner.MAXIMUM_PROCESS_COMMAND_BYTES + 1
    with pytest.raises(
        runner.SelectionExecutionV1Error,
        match="kernel process command differs",
    ):
        runner.observed_process_command_v1(
            mode="slate-assembler", raw_cmdline=plus_one
        )

    request = execution_fixture["assembler_request"]
    raw_request = contract.canonical_json_bytes_v1(request)
    unbound = {
        "schema_version": assembler.ASSEMBLER_ENVELOPE_SCHEMA,
        "assembler_request_sha256": request["assembler_request_sha256"],
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": 0,
    }
    unbound["assembler_envelope_sha256"] = contract.canonical_sha256_v1(
        unbound
    )
    evidence = _task_binding_evidence(request, raw_request)
    bound = runner.bind_task_evidence_to_assembler_envelope_v1(
        unbound,
        evidence,
        request=request,
        raw_request=raw_request,
    )
    assert bound["task_binding_evidence"] == evidence
    assert bound["assembler_envelope_sha256"] == contract.canonical_sha256_v1({
        key: value for key, value in bound.items()
        if key != "assembler_envelope_sha256"
    })
    for changed in (
        {**evidence, "unexpected": True},
        {
            **evidence,
            "child_task_binding_evidence_sha256": "f" * 64,
        },
        {
            **evidence,
            "schema_version": "hostile-task-binding/v1",
        },
        {
            **evidence,
            "policy": {**contract.POLICY_CLAIMS, "uses_realized_outcomes": True},
        },
    ):
        if (
            set(changed) == set(evidence)
            and changed["child_task_binding_evidence_sha256"]
            == evidence["child_task_binding_evidence_sha256"]
        ):
            changed["child_task_binding_evidence_sha256"] = (
                contract.canonical_sha256_v1({
                    key: value for key, value in changed.items()
                    if key != "child_task_binding_evidence_sha256"
                })
            )
        with pytest.raises(
            runner.SelectionExecutionV1Error,
            match="task binding evidence differs",
        ):
            runner.bind_task_evidence_to_assembler_envelope_v1(
                unbound,
                changed,
                request=request,
                raw_request=raw_request,
            )
    wrong_outer_hash = dict(evidence)
    wrong_outer_hash["request_sha256"] = request[
        "assembler_request_sha256"
    ]
    with pytest.raises(
        runner.SelectionExecutionV1Error,
        match="task binding evidence differs",
    ):
        runner.bind_task_evidence_to_assembler_envelope_v1(
            unbound,
            wrong_outer_hash,
            request=request,
            raw_request=raw_request,
        )
    with pytest.raises(
        runner.SelectionExecutionV1Error,
        match="task binding evidence differs",
    ):
        runner.bind_task_evidence_to_assembler_envelope_v1(
            unbound,
            evidence,
            request=request,
            raw_request=raw_request + b"\n",
        )

    oversized_identity = dict(evidence["manifest_identity"])
    oversized_identity["bytes"] = task_manifest.MAXIMUM_MANIFEST_BYTES + 1
    reads = 0

    def forbidden_read(_identity):
        nonlocal reads
        reads += 1
        raise AssertionError("oversized manifest must fail before exact read")

    with pytest.raises(
        runner.SelectionExecutionV1Error,
        match="manifest exceeds byte ceiling",
    ):
        runner.reopen_controller_task_after_client_v1(
            parsed_binding={"manifest_identity": oversized_identity},
            environ={},
            raw_request=raw_request,
            observed_command=command,
            read_exact=forbidden_read,
            expected_process_role="broad-slate-assembler",
            expected_phase=contract.BROAD_SCREEN_PHASE,
            expected_source_ordinal=0,
            expected_process_ordinal=0,
        )
    assert reads == 0
