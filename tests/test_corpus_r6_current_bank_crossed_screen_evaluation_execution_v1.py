from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import dataclass
import gc
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Mapping
import weakref

import numpy as np
import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_evaluation_v1 as evaluator,
)
from scripts import (
    run_corpus_r6_current_bank_crossed_screen_evaluation_v1 as runner,
)


def _identity(uri: str, raw: bytes, *, generation: str = "1") -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _tag_identity(tag: str, *, generation: str = "1") -> dict[str, object]:
    return _identity(f"gs://fixture/{tag}.json", tag.encode(), generation=generation)


@dataclass
class _Store:
    objects: dict[tuple[str, str], bytes]

    def __init__(self) -> None:
        self.objects = {}
        self.reads: list[dict[str, object]] = []
        self.publications: list[
            tuple[str, bytes, dict[str, object] | None]
        ] = []

    def add_raw(
        self, uri: str, raw: bytes, *, generation: str = "1",
    ) -> dict[str, object]:
        identity = _identity(uri, raw, generation=generation)
        self.objects[(uri, generation)] = raw
        return identity

    def add_json(
        self, uri: str, value: object, *, generation: str = "1",
    ) -> dict[str, object]:
        return self.add_raw(
            uri, contract.canonical_json_bytes_v1(value), generation=generation
        )

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        identity = contract._safe_object_identity(
            identity_value, label="fixture exact read"
        )
        self.reads.append(identity)
        return self.objects[(str(identity["uri"]), str(identity["generation"]))]

    def publish_create_once(
        self, uri: str, raw: bytes,
        prior: Mapping[str, object] | None,
    ) -> dict[str, object]:
        retained_prior = None if prior is None else dict(prior)
        self.publications.append((uri, raw, retained_prior))
        identity = _identity(uri, raw, generation="9001")
        self.objects[(uri, "9001")] = raw
        return identity


def _environment(source: int, *, execution: str = "fixture-execution") -> dict[str, str]:
    return {
        "GOOGLE_CLOUD_PROJECT": evaluator.FIXED_GCP_PROJECT,
        "CODE_SHA": "a" * 40,
        "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "b" * 64,
        "CLOUD_RUN_JOB": "fixture-evaluator",
        "CLOUD_RUN_EXECUTION": execution,
        "CLOUD_RUN_TASK_INDEX": str(source),
        "R6_EVALUATOR_PROCESS_ORDINAL": str(source),
    }


def _runtime(source: int, phase: str) -> dict[str, object]:
    return evaluator.derive_observed_runtime_evidence_v1(
        source_ordinal=source,
        phase=phase,
        environ=_environment(source),
        argv=evaluator.canonical_evaluator_command_v1(),
        pid=101,
        parent_pid=1,
    )


def _self_hashed(body: dict[str, object], field: str) -> dict[str, object]:
    retained = dict(body)
    retained[field] = contract.canonical_sha256_v1(retained)
    return retained


def _binding_evidence(
    request: Mapping[str, object],
) -> dict[str, object]:
    phase = str(request["phase"])
    source = int(request["source_ordinal"])
    request_raw = contract.canonical_json_bytes_v1(request)
    body = {
        "schema_version": runner.task_manifest.CHILD_TASK_BINDING_EVIDENCE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "manifest_identity": _tag_identity("task-manifest"),
        "task_manifest_sha256": "4" * 64,
        "layer_id": (
            "broad-evaluation-result"
            if phase == contract.BROAD_SCREEN_PHASE
            else "confirmation-evaluation-result"
        ),
        "phase": phase,
        "process_role": (
            "broad-evaluator"
            if phase == contract.BROAD_SCREEN_PHASE
            else "confirmation-evaluator"
        ),
        "task_index": source,
        "source_ordinal": source,
        "process_ordinal": source,
        "task_binding_sha256": "5" * 64,
        "request_sha256": sha256(request_raw).hexdigest(),
        "request_bytes": len(request_raw),
        "expected_outputs_sha256": "6" * 64,
        "child_command_sha256": "7" * 64,
        "manifest_generation_exact_reopen_required": True,
        "caller_request_or_command_accepted": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    return _self_hashed(body, "child_task_binding_evidence_sha256")


def test_request_surface_rejects_scientific_and_caller_created_fields() -> None:
    common = {
        "source_ordinal": 0,
        "design_identity": _tag_identity("design"),
        "topology_identity": _tag_identity("topology"),
        "projection_bundle_identity": _tag_identity("projection"),
        "selection_receipt_identity": _tag_identity("receipt"),
        "process_budget_identity": _tag_identity("budget"),
        "bootstrap_manifest_identity": _tag_identity("bootstrap"),
        "launch_intent_identity": _tag_identity("launch"),
    }
    broad = evaluator.build_evaluator_request_v1(
        phase=contract.BROAD_SCREEN_PHASE, **common
    )
    assert evaluator.validate_evaluator_request_v1(broad) == broad
    for forbidden in (
        "heldout_artifact_identities", "heldout_score_matrix", "player_game_map",
        "metric_rows", "selected_lineup_ids", "selector_command", "output_uri",
        "comparison_rows", "bootstrap_draws",
    ):
        mutated = deepcopy(broad)
        mutated[forbidden] = []
        with pytest.raises(
            evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
            match="request fields differ",
        ):
            evaluator.validate_evaluator_request_v1(mutated)
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="cannot accept nomination",
    ):
        evaluator.build_evaluator_request_v1(
            phase=contract.BROAD_SCREEN_PHASE,
            nomination_identity=_tag_identity("nomination"),
            **common,
        )
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="requires nomination",
    ):
        evaluator.build_evaluator_request_v1(
            phase=contract.CONFIRMATION_PHASE, **common
        )


def test_strict_json_rejects_duplicate_keys_and_nonfinite_constants() -> None:
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="repeats JSON key",
    ):
        evaluator.strict_json_v1(b'{"phase":"a","phase":"b"}', label="fixture")
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="non-finite JSON constant",
    ):
        evaluator.strict_json_v1(b'{"value":NaN}', label="fixture")
    # A non-object is rejected independently as well.
    with pytest.raises(evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error):
        evaluator.strict_json_v1(b"[1,2,3]", label="fixture")


def test_scientific_capability_is_exact_ordered_and_exhaustive() -> None:
    store = _Store()
    roles = [
        "later-source",
        *[f"heldout-world-{block}" for block in contract.WORLD_BLOCKS],
    ]
    rows = []
    for index, role in enumerate(roles):
        identity = store.add_raw(
            f"gs://fixture/scientific/{role}.bin",
            f"body-{index}".encode(),
            generation=str(index + 1),
        )
        rows.append({"role": role, "identity": identity})
    gate = evaluator.ExactAllowlistedScientificReadClientV1(
        allowed_rows=rows, read_exact=store.read_exact
    )
    wrong_fifth = dict(rows[-1]["identity"])
    wrong_fifth["generation"] = "999"
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="not addressable",
    ):
        gate.read(roles[-1], wrong_fifth)
    assert not store.reads
    for role, row in zip(roles, rows, strict=True):
        assert gate.read(role, row["identity"]).startswith(b"body-")
    assert [row["role"] for row in gate.require_complete()] == roles
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="exhausted",
    ):
        gate.read(roles[-1], rows[-1]["identity"])

    reordered = deepcopy(rows)
    reordered[-1], reordered[-2] = reordered[-2], reordered[-1]
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="role/order",
    ):
        evaluator.ExactAllowlistedScientificReadClientV1(
            allowed_rows=reordered, read_exact=store.read_exact
        )
    repeated = deepcopy(rows)
    repeated[-1]["identity"] = repeated[-2]["identity"]
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="URI repeats",
    ):
        evaluator.ExactAllowlistedScientificReadClientV1(
            allowed_rows=repeated, read_exact=store.read_exact
        )


def _later_source_with_catalog_size(player_count: int) -> dict[str, object]:
    catalog = [
        {
            "id": f"p-{index:04d}",
            "pos": "WR",
            "team": "AAA",
            "opp": "BBB",
            "game_id": "AAA-BBB",
            "salary": 3_000,
        }
        for index in range(player_count)
    ]
    receipts = [
        {"block": block, "fixture": True}
        for block in contract.WORLD_BLOCKS
    ]
    slates = [
        {
            "slate_id": f"fixture-{source:02d}",
            "catalog": catalog,
            "catalog_sha256": contract.canonical_sha256_v1(catalog),
            "artifact_receipts": receipts,
            "artifact_receipts_sha256": contract.canonical_sha256_v1(receipts),
        }
        for source in range(contract.PANEL_SLATE_COUNT)
    ]
    body = {
        "world_blocks": list(contract.WORLD_BLOCKS),
        "worlds_per_block": contract.WORLDS_PER_BLOCK,
        "slate_count": contract.PANEL_SLATE_COUNT,
        "slates": slates,
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "production_inputs_used": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    return _self_hashed(body, "freeze_sha256")


def test_real_773_player_later_source_surface_is_inside_resource_ceiling() -> None:
    assert evaluator.MAXIMUM_PLAYER_COUNT == 1_024
    source = _later_source_with_catalog_size(773)
    slate, players = evaluator._later_slate_v1(
        source, slate_id="fixture-00"
    )
    assert slate["slate_id"] == "fixture-00"
    assert len(players) == 773

    oversized = _later_source_with_catalog_size(
        evaluator.MAXIMUM_PLAYER_COUNT + 1
    )
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="scoring surface differs",
    ):
        evaluator._later_slate_v1(oversized, slate_id="fixture-00")


def _players() -> tuple[evaluator.ScoringPlayerV1, ...]:
    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "WR", "TE", "DST"]
    rows = []
    for index, position in enumerate(positions):
        team = "AAA" if index < 7 else "BBB"
        rows.append(evaluator.ScoringPlayerV1(
            player_id=f"p-{index:02d}",
            position=position,
            team=team,
            opponent="BBB" if team == "AAA" else "AAA",
            game_id="AAA-BBB" if index < 8 else "CCC-DDD",
            salary=5_000,
        ))
    return tuple(rows)


def test_local_cross_score_is_float64_candidate_order_and_legality_bound() -> None:
    players = _players()
    draws = np.repeat(
        np.arange(1, 10, dtype=np.float32)[:, None],
        contract.WORLDS_PER_BLOCK,
        axis=1,
    )
    roster = sorted(player.player_id for player in players)
    result = evaluator._cross_score_full_union_v1(
        players, draws, [roster], expected_worlds=contract.WORLDS_PER_BLOCK
    )
    assert result.dtype == np.dtype(np.float64)
    assert result.shape == (1, contract.WORLDS_PER_BLOCK)
    assert np.array_equal(result, np.full_like(result, 45.0))
    assert result.flags.writeable is False
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="canonical nine-player",
    ):
        evaluator._cross_score_full_union_v1(
            players, draws, [list(reversed(roster))],
            expected_worlds=contract.WORLDS_PER_BLOCK,
        )


@pytest.mark.parametrize("failure", ["dtype", "worlds", "nonfinite", "score-shape"])
def test_fold_scoring_rejects_matrix_shape_dtype_and_nonfinite(failure: str) -> None:
    players = _players()
    draws = np.ones(
        (len(players), contract.WORLDS_PER_BLOCK), dtype=np.float32
    )
    if failure == "dtype":
        draws = draws.astype(np.float64)
    elif failure == "worlds":
        draws = draws[:, :-1]
    elif failure == "nonfinite":
        draws[0, 0] = np.nan
    loaded = SimpleNamespace(
        block="R0",
        player_ids=tuple(player.player_id for player in reversed(players)),
        player_draws=draws[::-1],
    )

    def cross_score(
        _players_value: object, _draws_value: object, rosters: object,
        *, expected_worlds: int,
    ) -> np.ndarray:
        rows = list(rosters)
        shape = (
            (len(rows), expected_worlds - 1)
            if failure == "score-shape"
            else (len(rows), expected_worlds)
        )
        return np.zeros(shape, dtype=np.float64)

    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="player-world matrix|candidate score matrix",
    ):
        evaluator._score_heldout_fold_v1(
            projection={
                "heldout_block": "R0",
                "candidates": [{
                    "roster_player_ids": sorted(
                        player.player_id for player in players
                    )
                }],
            },
            players=players,
            receipt={},
            raw_artifact=b"fixture",
            load_artifact_worlds=lambda _receipt, _raw: loaded,
            cross_score=cross_score,
        )


def _world_npz(
    *, player_count: int = 9, candidate_rows: int = 2,
) -> tuple[bytes, tuple[str, ...]]:
    player_ids = tuple(f"p-{index:03d}" for index in range(player_count))
    output = BytesIO()
    np.savez_compressed(
        output,
        cand_ix=np.arange(candidate_rows, dtype=np.int32),
        totals=np.zeros(
            (candidate_rows, contract.WORLDS_PER_BLOCK), dtype=np.float32
        ),
        tail_line=np.asarray(194.0, dtype=np.float32),
        player_ids=np.asarray(player_ids),
        player_draws=np.ones(
            (player_count, contract.WORLDS_PER_BLOCK), dtype=np.float32
        ),
    )
    return output.getvalue(), player_ids


def test_solver_free_world_decoder_is_real_and_resource_bounded() -> None:
    raw, player_ids = _world_npz()
    receipt = {
        "block": "R0",
        "candidate_rows": 2,
        "bytes": len(raw),
        "sha256": sha256(raw).hexdigest(),
    }
    loaded = evaluator._load_artifact_worlds_v1(receipt, raw)
    assert loaded.block == "R0"
    assert loaded.player_ids == player_ids
    assert loaded.player_draws.shape == (9, contract.WORLDS_PER_BLOCK)
    assert loaded.player_draws.dtype == np.dtype(np.float32)
    assert loaded.player_draws.flags.writeable is False

    oversized = dict(receipt)
    oversized["candidate_rows"] = evaluator.MAXIMUM_SOURCE_CANDIDATE_ROWS + 1
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="resource authority",
    ):
        evaluator._load_artifact_worlds_v1(oversized, raw)


def test_world_decoder_accepts_frozen_panel_candidate_capacity_without_huge_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the real receipt path at 3,993 without allocating its totals."""
    raw, player_ids = _world_npz()
    original_header = evaluator._npy_member_header_v1

    def frozen_panel_header(
        archive: object, *, name: str,
    ) -> tuple[tuple[int, ...], bool, np.dtype, int]:
        shape, fortran_order, dtype, member_bytes = original_header(
            archive, name=name
        )
        if name == "cand_ix.npy":
            shape = (contract.MAX_SELECTION_CANDIDATES_PER_FOLD,)
        elif name == "totals.npy":
            shape = (
                contract.MAX_SELECTION_CANDIDATES_PER_FOLD,
                contract.WORLDS_PER_BLOCK,
            )
        return shape, fortran_order, dtype, member_bytes

    monkeypatch.setattr(
        evaluator, "_npy_member_header_v1", frozen_panel_header
    )
    receipt = {
        "block": "R0",
        "candidate_rows": contract.MAX_SELECTION_CANDIDATES_PER_FOLD,
        "bytes": len(raw),
        "sha256": sha256(raw).hexdigest(),
    }

    loaded = evaluator._load_artifact_worlds_v1(receipt, raw)
    assert loaded.player_ids == player_ids
    assert evaluator.MAXIMUM_SOURCE_CANDIDATE_ROWS == 3_993

    oversized = dict(receipt)
    oversized["candidate_rows"] = 3_994
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="resource authority",
    ):
        evaluator._load_artifact_worlds_v1(oversized, raw)


def _install_orchestration_contract(
    monkeypatch: pytest.MonkeyPatch,
    *, phase: str, invalid_nomination: bool = False,
) -> tuple[_Store, dict[str, object], dict[str, object], list[weakref.ReferenceType]]:
    store = _Store()
    source = 3
    topology: dict[str, object] = {"fixture": "topology"}
    topology_identity = store.add_json("gs://fixture/topology.json", topology)
    bootstrap: dict[str, object] = {"fixture": "bootstrap"}
    bootstrap_identity = store.add_json("gs://fixture/bootstrap.json", bootstrap)
    design: dict[str, object] = {
        "topology": topology,
        "topology_identity": topology_identity,
        "bootstrap_manifest": bootstrap,
        "bootstrap_manifest_identity": bootstrap_identity,
    }
    design_identity = store.add_json("gs://fixture/design.json", design)
    launch_identity = store.add_raw("gs://fixture/launch.json", b"launch-intent")
    later_identity = store.add_json(
        "gs://fixture/later.json", {"fixture": "later"}
    )
    artifact_identities = {
        block: store.add_raw(
            f"gs://fixture/world-{block}.npz", f"world-{block}".encode()
        )
        for block in contract.WORLD_BLOCKS
    }
    projections = [{
        "heldout_block": block,
        "candidates": [{"roster_player_ids": ["fixture"]}],
    } for block in contract.WORLD_BLOCKS]
    bundle: dict[str, object] = {
        "source_ordinal": source,
        "slate_id": "fixture-slate",
        "fold_projections": projections,
    }
    bundle_identity = store.add_json("gs://fixture/projection.json", bundle)
    receipt: dict[str, object] = {
        "phase": phase,
        "source_ordinal": source,
    }
    receipt_identity = store.add_json("gs://fixture/receipt.json", receipt)
    nomination: dict[str, object] | None = None
    nomination_identity: dict[str, object] | None = None
    if phase == contract.CONFIRMATION_PHASE:
        nomination = {"valid": not invalid_nomination}
        nomination_identity = store.add_json(
            "gs://fixture/nomination.json", nomination
        )
    output_uri = (
        "gs://nfl-predictions-503414/research/"
        "corpus-r6-current-bank-crossed-screens/fixture/evaluation.json"
    )
    base_reads = [
        {"role": "design", "identity": design_identity},
        {"role": "topology", "identity": topology_identity},
        {"role": "bootstrap-manifest", "identity": bootstrap_identity},
        {"role": "launch-intent", "identity": launch_identity},
        {"role": "projection-bundle", "identity": bundle_identity},
        {"role": "selection-receipt", "identity": receipt_identity},
        {"role": "later-source", "identity": later_identity},
        *[
            {"role": f"heldout-world-{block}", "identity": artifact_identities[block]}
            for block in contract.WORLD_BLOCKS
        ],
    ]
    if nomination_identity is not None:
        base_reads.append({"role": "nomination", "identity": nomination_identity})
    budget = _self_hashed({
        "read_allowlist": base_reads,
        "write_allowlist": [{
            "role": (
                "broad-evaluation-result"
                if phase == contract.BROAD_SCREEN_PHASE
                else "confirmation-evaluation-result"
            ),
            "source_ordinal": source,
            "uri": output_uri,
            "max_bytes": 1_000_000,
            "create_once": True,
        }],
    }, "evaluator_process_budget_sha256")
    budget_identity = store.add_json("gs://fixture/process-budget.json", budget)
    request = evaluator.build_evaluator_request_v1(
        phase=phase,
        source_ordinal=source,
        design_identity=design_identity,
        topology_identity=topology_identity,
        projection_bundle_identity=bundle_identity,
        selection_receipt_identity=receipt_identity,
        process_budget_identity=budget_identity,
        bootstrap_manifest_identity=bootstrap_identity,
        launch_intent_identity=launch_identity,
        nomination_identity=nomination_identity,
    )

    monkeypatch.setattr(
        contract, "validate_design_authority_v1",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(contract, "validate_result_topology_v1", lambda value: value)
    monkeypatch.setattr(
        contract, "validate_projection_bundle_authority_v1",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(
        contract, "validate_evaluator_process_budget_v1",
        lambda value, **_kwargs: value,
    )

    def compile_budget(**_kwargs: object) -> dict[str, object]:
        if invalid_nomination:
            raise evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error(
                "confirmation nomination publication differs"
            )
        return budget

    monkeypatch.setattr(evaluator, "_compile_evaluator_budget_v1", compile_budget)
    monkeypatch.setattr(
        evaluator, "_later_slate_v1", lambda *_args, **_kwargs: ({}, ())
    )
    monkeypatch.setattr(
        evaluator, "_artifact_receipt_v1", lambda *_args, **_kwargs: {}
    )
    matrix_refs: list[weakref.ReferenceType] = []

    def score(*, projection: Mapping[str, object], **_kwargs: object) -> np.ndarray:
        gc.collect()
        assert all(reference() is None for reference in matrix_refs)
        fold = contract.WORLD_BLOCKS.index(str(projection["heldout_block"]))
        matrix = np.full((1, contract.WORLDS_PER_BLOCK), fold, dtype=np.float64)
        matrix_refs.append(weakref.ref(matrix))
        return matrix

    monkeypatch.setattr(evaluator, "_score_heldout_fold_v1", score)
    runtime_observation = _self_hashed(
        {"fixture": "runtime"}, "runtime_observation_sha256"
    )
    monkeypatch.setattr(
        evaluator, "_build_runtime_observation_v1",
        lambda **_kwargs: runtime_observation,
    )

    def build_result(*, fold_stream: object, **_kwargs: object) -> dict[str, object]:
        stream = iter(fold_stream)
        observed = []
        for fold in range(contract.FOLDS_PER_SLATE):
            row = next(stream)
            assert set(row) == {
                "fold_ordinal", "heldout_artifact_identity", "heldout_score_matrix",
            }
            assert row["fold_ordinal"] == fold
            assert row["heldout_artifact_identity"] == artifact_identities[
                contract.WORLD_BLOCKS[fold]
            ]
            assert np.asarray(row["heldout_score_matrix"]).shape == (
                1, contract.WORLDS_PER_BLOCK
            )
            observed.append(fold)
            del row
        with pytest.raises(StopIteration):
            next(stream)
        assert observed == list(range(contract.FOLDS_PER_SLATE))
        return _self_hashed(
            {"phase": phase, "source_ordinal": source},
            "evaluation_result_sha256",
        )

    monkeypatch.setattr(evaluator, "_build_result_v1", build_result)
    monkeypatch.setattr(
        contract, "validate_evaluation_result_v1", lambda value: value
    )
    return store, request, _runtime(source, phase), matrix_refs


@pytest.mark.parametrize(
    "phase", [contract.BROAD_SCREEN_PHASE, contract.CONFIRMATION_PHASE]
)
def test_runner_reads_receipt_and_nomination_before_sequential_heldout(
    monkeypatch: pytest.MonkeyPatch, phase: str,
) -> None:
    store, request, runtime, matrix_refs = _install_orchestration_contract(
        monkeypatch, phase=phase
    )
    envelope = evaluator.run_evaluator_v1(
        request,
        observed_runtime=runtime,
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    roles = [row["role"] for row in envelope["read_ledger"]]
    assert roles == [
        "design", "topology", "bootstrap-manifest", "launch-intent",
        "projection-bundle", "selection-receipt",
        *(["nomination"] if phase == contract.CONFIRMATION_PHASE else []),
        "process-budget", "later-source",
        *[f"heldout-world-{block}" for block in contract.WORLD_BLOCKS],
    ]
    assert envelope["receipt_read_ordinal"] < envelope["first_heldout_read_ordinal"]
    if phase == contract.CONFIRMATION_PHASE:
        assert envelope["nomination_read_ordinal"] < envelope[
            "first_heldout_read_ordinal"
        ]
    else:
        assert envelope["nomination_read_ordinal"] is None
    assert envelope["fold_stream_consumption_order"] == list(
        range(contract.FOLDS_PER_SLATE)
    )
    assert len(matrix_refs) == contract.FOLDS_PER_SLATE
    assert len(store.publications) == 1
    assert store.publications[0][2] is None


def test_invalid_confirmation_nomination_fails_before_scientific_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, request, runtime, _ = _install_orchestration_contract(
        monkeypatch,
        phase=contract.CONFIRMATION_PHASE,
        invalid_nomination=True,
    )
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="nomination publication differs",
    ):
        evaluator.run_evaluator_v1(
            request,
            observed_runtime=runtime,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
    assert not any("/later.json" in str(row["uri"]) for row in store.reads)
    assert not any("/world-R" in str(row["uri"]) for row in store.reads)
    assert not store.publications


def test_runtime_bootstrap_mismatch_fails_before_any_scientific_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, request, runtime, _ = _install_orchestration_contract(
        monkeypatch, phase=contract.BROAD_SCREEN_PHASE
    )

    def reject_runtime(**_kwargs: object) -> dict[str, object]:
        raise evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            "runtime bootstrap differs"
        )

    monkeypatch.setattr(evaluator, "_build_runtime_observation_v1", reject_runtime)
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="runtime bootstrap differs",
    ):
        evaluator.run_evaluator_v1(
            request,
            observed_runtime=runtime,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
    assert not any("/later.json" in str(row["uri"]) for row in store.reads)
    assert not any("/world-R" in str(row["uri"]) for row in store.reads)
    assert not store.publications


def test_wrong_resume_identity_uri_fails_before_scientific_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, request, runtime, _ = _install_orchestration_contract(
        monkeypatch, phase=contract.BROAD_SCREEN_PHASE
    )
    request = evaluator.build_evaluator_request_v1(
        phase=str(request["phase"]),
        source_ordinal=int(request["source_ordinal"]),
        design_identity=request["design_identity"],
        topology_identity=request["topology_identity"],
        projection_bundle_identity=request["projection_bundle_identity"],
        selection_receipt_identity=request["selection_receipt_identity"],
        process_budget_identity=request["process_budget_identity"],
        bootstrap_manifest_identity=request["bootstrap_manifest_identity"],
        launch_intent_identity=request["launch_intent_identity"],
        prior_evaluation_identity=_tag_identity("wrong-output"),
    )
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="prior evaluation identity",
    ):
        evaluator.run_evaluator_v1(
            request,
            observed_runtime=runtime,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
    assert not any("/later.json" in str(row["uri"]) for row in store.reads)
    assert not any("/world-R" in str(row["uri"]) for row in store.reads)
    assert not store.publications


def test_oversized_prior_identity_fails_before_scientific_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, request, runtime, _ = _install_orchestration_contract(
        monkeypatch, phase=contract.BROAD_SCREEN_PHASE
    )
    oversized_prior = {
        "uri": (
            "gs://nfl-predictions-503414/research/"
            "corpus-r6-current-bank-crossed-screens/fixture/evaluation.json"
        ),
        "generation": "77",
        "sha256": "0" * 64,
        "bytes": 1_000_001,
    }
    request = evaluator.build_evaluator_request_v1(
        phase=str(request["phase"]),
        source_ordinal=int(request["source_ordinal"]),
        design_identity=request["design_identity"],
        topology_identity=request["topology_identity"],
        projection_bundle_identity=request["projection_bundle_identity"],
        selection_receipt_identity=request["selection_receipt_identity"],
        process_budget_identity=request["process_budget_identity"],
        bootstrap_manifest_identity=request["bootstrap_manifest_identity"],
        launch_intent_identity=request["launch_intent_identity"],
        prior_evaluation_identity=oversized_prior,
    )
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="prior evaluation identity URI/bytes",
    ):
        evaluator.run_evaluator_v1(
            request,
            observed_runtime=runtime,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
    assert not any("/later.json" in str(row["uri"]) for row in store.reads)
    assert not any("/world-R" in str(row["uri"]) for row in store.reads)
    assert not store.publications


def test_preclient_runtime_and_redirect_gates_fail_before_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    common = {
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": 0,
        "design_identity": _tag_identity("design"),
        "topology_identity": _tag_identity("topology"),
        "projection_bundle_identity": _tag_identity("projection"),
        "selection_receipt_identity": _tag_identity("receipt"),
        "process_budget_identity": _tag_identity("budget"),
        "bootstrap_manifest_identity": _tag_identity("bootstrap"),
        "launch_intent_identity": _tag_identity("launch"),
    }
    request = evaluator.build_evaluator_request_v1(**common)
    raw = contract.canonical_json_bytes_v1(request)
    environment = _environment(0)
    environment[runner.ENABLE_ENV] = "1"
    environment["STORAGE_EMULATOR_HOST"] = "http://hostile.invalid"
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="redirect environment",
    ):
        runner.validate_preclient_invocation_v1(
            argv=evaluator.canonical_evaluator_command_v1(),
            environ=environment,
            raw_request=raw,
            pid=1,
            parent_pid=0,
        )

    monkeypatch.setattr(runner, "_read_stdin_bounded_v1", lambda: raw)
    monkeypatch.setattr(
        runner,
        "observed_process_command_v1",
        evaluator.canonical_evaluator_command_v1,
    )
    monkeypatch.setattr(
        runner, "GCSExactCreateOnceTransportV1",
        lambda: pytest.fail("cloud transport must be lazy"),
    )
    monkeypatch.setattr(runner.sys, "argv", ["fixture", "evaluate-slate"])
    monkeypatch.delenv(runner.ENABLE_ENV, raising=False)
    with pytest.raises(
        runner.RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="held-out evaluation failed",
    ):
        runner.main()


@pytest.mark.parametrize(
    "key,value",
    [
        ("HTTPS_PROXY", "http://hostile.invalid:8080"),
        ("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/hostile-credentials.json"),
        ("REQUESTS_CA_BUNDLE", "/tmp/hostile-ca.pem"),
    ],
)
def test_preclient_rejects_proxy_credential_and_trust_redirects(
    key: str, value: str,
) -> None:
    request = evaluator.build_evaluator_request_v1(
        phase=contract.BROAD_SCREEN_PHASE,
        source_ordinal=0,
        design_identity=_tag_identity("redirect-design"),
        topology_identity=_tag_identity("redirect-topology"),
        projection_bundle_identity=_tag_identity("redirect-projection"),
        selection_receipt_identity=_tag_identity("redirect-receipt"),
        process_budget_identity=_tag_identity("redirect-budget"),
        bootstrap_manifest_identity=_tag_identity("redirect-bootstrap"),
        launch_intent_identity=_tag_identity("redirect-launch"),
    )
    environment = _environment(0)
    environment[runner.ENABLE_ENV] = "1"
    environment[key] = value
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match=f"redirect environment {key}",
    ):
        runner.validate_preclient_invocation_v1(
            argv=evaluator.canonical_evaluator_command_v1(),
            environ=environment,
            raw_request=contract.canonical_json_bytes_v1(request),
            pid=1,
            parent_pid=0,
        )


def test_transport_create_once_and_collision_resume_are_generation_exact() -> None:
    class Conflict(Exception):
        pass

    uri = (
        "gs://nfl-predictions-503414/research/"
        "corpus-r6-current-bank-crossed-screens/fixture/evaluation.json"
    )
    raw = b'{"evaluation":"fixture"}'
    prior = _identity(uri, raw, generation="77")
    blob_calls: list[tuple[str, int | None]] = []
    downloads: list[tuple[int | None, int]] = []
    uploads: list[int | None] = []
    collision = {"enabled": True}

    class Blob:
        def __init__(self, name: str, generation: int | None) -> None:
            self.name = name
            self.generation = generation

        def upload_from_string(self, value: bytes, **kwargs: object) -> None:
            assert value == raw
            assert kwargs["if_generation_match"] == 0
            uploads.append(self.generation)
            if collision["enabled"]:
                raise Conflict("occupied")
            self.generation = 88

        def download_as_bytes(self, *, if_generation_match: int) -> bytes:
            downloads.append((self.generation, if_generation_match))
            if self.generation == 79:
                raise FileNotFoundError("recorded generation is absent")
            return raw

    class Bucket:
        def blob(self, name: str, generation: int | None = None) -> Blob:
            blob_calls.append((name, generation))
            return Blob(name, generation)

    class Client:
        def bucket(self, _name: str) -> Bucket:
            return Bucket()

    transport = object.__new__(runner.GCSExactCreateOnceTransportV1)
    transport._client = Client()
    assert transport.publish_create_once(uri, raw, prior) == prior
    assert downloads == [(77, 77)]
    with pytest.raises(
        runner.RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="lacks a recorded exact identity",
    ):
        transport.publish_create_once(uri, raw, None)
    assert downloads == [(77, 77)]
    wrong_body = _identity(uri, b"different", generation="78")
    with pytest.raises(
        runner.RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="exact-read body differs",
    ):
        transport.publish_create_once(uri, raw, wrong_body)
    assert downloads[-1] == (78, 78)

    missing_prior = _identity(uri, raw, generation="79")
    prior_upload_count = len(uploads)
    with pytest.raises(
        runner.RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="generation-pinned GET failed",
    ):
        transport.publish_create_once(uri, raw, missing_prior)
    assert len(uploads) == prior_upload_count

    collision["enabled"] = False
    created = transport.publish_create_once(uri, raw, None)
    assert created["generation"] == "88"
    assert downloads[-1] == (88, 88)
    assert not hasattr(transport, "list_blobs")
    assert not hasattr(transport, "reload")
    assert not hasattr(transport, "resolve_current")
    assert not hasattr(transport, "resolve_optional")


def test_kernel_observed_command_rejects_wrapper_and_module_invocation() -> None:
    canonical = evaluator.canonical_evaluator_command_v1()
    raw = b"\0".join(field.encode("utf-8") for field in canonical) + b"\0"
    assert runner.observed_process_command_v1(raw) == canonical
    prefix = (
        canonical[0].encode("utf-8") + b"\0"
        + canonical[1].encode("utf-8") + b"\0"
    )
    exact = prefix + b"x" * (
        runner.MAXIMUM_PROCESS_COMMAND_BYTES - len(prefix) - 1
    ) + b"\0"
    assert len(exact) == runner.MAXIMUM_PROCESS_COMMAND_BYTES
    with pytest.raises(
        runner.RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="canonical evaluator entrypoint",
    ):
        runner.observed_process_command_v1(exact)
    with pytest.raises(
        runner.RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="command differs",
    ):
        runner.observed_process_command_v1(exact + b"\0")
    module_invocation = b"\0".join([
        canonical[0].encode("utf-8"), b"-m", b"hostile.wrapper",
    ]) + b"\0"
    with pytest.raises(
        runner.RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="canonical evaluator entrypoint",
    ):
        runner.observed_process_command_v1(module_invocation)


def test_resource_precharge_rejects_candidate_matrix_overflow() -> None:
    candidate = {"roster_player_ids": ["fixture"]}
    bundle = {
        "fold_projections": [
            {"candidates": [candidate] * (evaluator.MAXIMUM_EVALUATION_CANDIDATES + 1)},
            *[{"candidates": [candidate]} for _ in range(4)],
        ]
    }
    scientific_rows = [
        {"identity": _tag_identity("later")},
        *[
            {"identity": _tag_identity(f"world-{block}")}
            for block in contract.WORLD_BLOCKS
        ],
    ]
    with pytest.raises(
        evaluator.CorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="resource precharge",
    ):
        evaluator._compile_resource_precharge_v1(
            bundle=bundle, scientific_rows=scientific_rows
        )


def test_resource_precharge_accepts_recorded_real_later_source_size() -> None:
    bundle = {
        "fold_projections": [
            {"candidates": [{"roster_player_ids": ["fixture"]}]}
            for _ in contract.WORLD_BLOCKS
        ]
    }
    later_identity = {
        "uri": (
            "gs://nfl-predictions-503414-corpus-source/research/source/"
            "20260821-corpus-artifact-source-authority-v3/source/"
            "later-source-freeze.json"
        ),
        "generation": "1787367678830738",
        "sha256": (
            "c63251a3dee0b455502a8e37d03c731c671457b9b17ff41dd9249edb0bae654a"
        ),
        "bytes": 4_566_802,
    }
    scientific_rows = [
        {"identity": later_identity},
        *[
            {"identity": _tag_identity(f"real-size-world-{block}")}
            for block in contract.WORLD_BLOCKS
        ],
    ]
    precharge = evaluator._compile_resource_precharge_v1(
        bundle=bundle, scientific_rows=scientific_rows
    )
    assert precharge["maximum_source_candidate_rows"] == (
        contract.MAX_SELECTION_CANDIDATES_PER_FOLD
    )
    assert (
        runner.task_manifest._EVALUATOR_MAXIMUM_SOURCE_CANDIDATE_ROWS
        == contract.MAX_SELECTION_CANDIDATES_PER_FOLD
    )
    assert precharge["maximum_later_source_bytes"] == 8_000_000
    assert later_identity["bytes"] <= precharge["maximum_later_source_bytes"]


def test_cli_rejects_stdout_envelope_overflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = evaluator.build_evaluator_request_v1(
        phase=contract.BROAD_SCREEN_PHASE,
        source_ordinal=0,
        design_identity=_tag_identity("overflow-design"),
        topology_identity=_tag_identity("overflow-topology"),
        projection_bundle_identity=_tag_identity("overflow-projection"),
        selection_receipt_identity=_tag_identity("overflow-selection"),
        process_budget_identity=_tag_identity("overflow-budget"),
        bootstrap_manifest_identity=_tag_identity("overflow-bootstrap"),
        launch_intent_identity=_tag_identity("overflow-launch"),
    )
    request_sha = str(request["evaluator_request_sha256"])
    binding = _binding_evidence(request)
    unbound = {
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": 0,
        "process_ordinal": 0,
        "evaluator_request_sha256": request_sha,
        "payload": "x" * (evaluator.MAXIMUM_ENVELOPE_BYTES + 1),
    }
    unbound["evaluator_envelope_sha256"] = contract.canonical_sha256_v1(
        unbound
    )
    monkeypatch.setattr(runner, "_read_stdin_bounded_v1", lambda: b"{}")
    monkeypatch.setattr(
        runner.task_manifest,
        "parse_child_task_binding_environment_v1",
        lambda _environ: {
            "manifest_identity": _tag_identity("overflow-task-manifest"),
            "layer_id": "broad-evaluation-result",
            "task_index": 0,
            "request_sha256": sha256(b"{}").hexdigest(),
            "child_command_sha256": contract.canonical_sha256_v1({
                "command": evaluator.canonical_evaluator_command_v1(),
                "entrypoint_sha256": sha256(
                    Path(runner.__file__).read_bytes()
                ).hexdigest(),
            }),
        },
    )
    monkeypatch.setattr(
        runner,
        "observed_process_command_v1",
        evaluator.canonical_evaluator_command_v1,
    )
    monkeypatch.setattr(
        runner,
        "validate_preclient_invocation_v1",
        lambda **_kwargs: (request, {"fixture": "runtime"}),
    )
    monkeypatch.setattr(runner, "GCSExactCreateOnceTransportV1", lambda: SimpleNamespace(
        read_exact=lambda _identity: b"",
        publish_create_once=lambda _uri, _raw, _prior: {},
    ))
    monkeypatch.setattr(
        runner.task_manifest,
        "reopen_child_task_binding_v1",
        lambda **_kwargs: binding,
    )
    monkeypatch.setattr(
        evaluator,
        "run_evaluator_v1",
        lambda *_args, **_kwargs: unbound,
    )
    with pytest.raises(
        runner.RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="stdout byte ceiling",
    ):
        runner.main()


def test_bound_evaluator_envelope_self_hashes_child_task_evidence() -> None:
    request = evaluator.build_evaluator_request_v1(
        phase=contract.CONFIRMATION_PHASE,
        source_ordinal=7,
        design_identity=_tag_identity("bound-design"),
        topology_identity=_tag_identity("bound-topology"),
        projection_bundle_identity=_tag_identity("bound-projection"),
        selection_receipt_identity=_tag_identity("bound-selection"),
        process_budget_identity=_tag_identity("bound-budget"),
        bootstrap_manifest_identity=_tag_identity("bound-bootstrap"),
        launch_intent_identity=_tag_identity("bound-launch"),
        nomination_identity=_tag_identity("bound-nomination"),
    )
    request_sha = str(request["evaluator_request_sha256"])
    body = {
        "schema_version": evaluator.EVALUATOR_ENVELOPE_SCHEMA,
        "phase": contract.CONFIRMATION_PHASE,
        "source_ordinal": 7,
        "process_ordinal": 7,
        "evaluator_request_sha256": request_sha,
    }
    envelope = _self_hashed(body, "evaluator_envelope_sha256")
    binding = _binding_evidence(request)
    retained = runner.bind_task_evidence_to_envelope_v1(
        envelope, binding, request
    )
    assert retained["task_binding_evidence"] == binding
    digest = retained.pop("evaluator_envelope_sha256")
    assert digest == contract.canonical_sha256_v1(retained)

    spliced = dict(binding)
    spliced["source_ordinal"] = 8
    with pytest.raises(
        runner.RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="task binding evidence differs",
    ):
        runner.bind_task_evidence_to_envelope_v1(envelope, spliced, request)


def test_successful_evaluator_envelope_terminalizes_exact_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, initial_request, observed_runtime, _ = _install_orchestration_contract(
        monkeypatch, phase=contract.BROAD_SCREEN_PHASE
    )
    initial_budget_identity = initial_request["process_budget_identity"]
    initial_budget = evaluator.strict_json_v1(
        store.objects[(
            str(initial_budget_identity["uri"]),
            str(initial_budget_identity["generation"]),
        )],
        label="initial evaluator budget",
    )
    budget_body = {
        "schema_version": contract.EVALUATOR_PROCESS_BUDGET_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "process_role": "broad-evaluator",
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": initial_request["source_ordinal"],
        "process_ordinal": initial_request["process_ordinal"],
        "read_allowlist": initial_budget["read_allowlist"],
        "read_object_count_excluding_budget_authority": len(
            initial_budget["read_allowlist"]
        ),
        "read_byte_ceiling_excluding_budget_authority": sum(
            int(row["identity"]["bytes"])
            for row in initial_budget["read_allowlist"]
        ),
        "write_allowlist": initial_budget["write_allowlist"],
        "write_object_count": 1,
        "write_byte_ceiling": initial_budget["write_allowlist"][0][
            "max_bytes"
        ],
        "compute_fit_precharge": 0,
        "process_budget_authority_added_at_runtime": True,
        "current_generation_lookup_allowed": False,
        "environment_redirect_allowed": False,
        "git_ref_redirect_allowed": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    budget = _self_hashed(
        budget_body, "evaluator_process_budget_sha256"
    )
    budget_identity = store.add_json(
        "gs://fixture/terminal-evaluator-process-budget.json", budget
    )
    request = evaluator.build_evaluator_request_v1(
        phase=contract.BROAD_SCREEN_PHASE,
        source_ordinal=int(initial_request["source_ordinal"]),
        design_identity=initial_request["design_identity"],
        topology_identity=initial_request["topology_identity"],
        projection_bundle_identity=initial_request["projection_bundle_identity"],
        selection_receipt_identity=initial_request["selection_receipt_identity"],
        process_budget_identity=budget_identity,
        bootstrap_manifest_identity=initial_request[
            "bootstrap_manifest_identity"
        ],
        launch_intent_identity=initial_request["launch_intent_identity"],
    )
    component = {
        "component_role": "main",
        "command": evaluator.canonical_evaluator_command_v1(),
        "entrypoint_path": evaluator.canonical_evaluator_command_v1()[1],
        "entrypoint_sha256": sha256(
            Path(evaluator.canonical_evaluator_command_v1()[1]).read_bytes()
        ).hexdigest(),
    }
    bootstrap_sha256 = "8" * 64
    runtime_body = {
        "schema_version": contract.RUNTIME_OBSERVATION_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "process_role": "broad-evaluator",
        "bootstrap_manifest_identity": request["bootstrap_manifest_identity"],
        "bootstrap_manifest_sha256": bootstrap_sha256,
        "process_budget_identity": budget_identity,
        "process_budget_sha256": budget["evaluator_process_budget_sha256"],
        "launch_intent_identity": request["launch_intent_identity"],
        "observed_code_commit": "a" * 40,
        "observed_image_digest": "sha256:" + "b" * 64,
        "observed_command": component["command"],
        "observed_entrypoint_sha256": component["entrypoint_sha256"],
        "cloud_job_name_observed": "fixture-evaluator",
        "cloud_execution_name_observed": "fixture-execution",
        "cloud_task_index_observed": request["source_ordinal"],
        "read_object_count_including_process_budget_authority": (
            budget["read_object_count_excluding_budget_authority"] + 1
        ),
        "read_byte_ceiling_including_process_budget_authority": (
            budget["read_byte_ceiling_excluding_budget_authority"]
            + budget_identity["bytes"]
        ),
        "cloud_values_are_unattested_observations": True,
        "terminal_execution_attestation_required": True,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    runtime_observation = _self_hashed(
        runtime_body, "runtime_observation_sha256"
    )
    monkeypatch.setattr(
        evaluator, "_compile_evaluator_budget_v1", lambda **_kwargs: budget
    )
    monkeypatch.setattr(
        evaluator,
        "_build_runtime_observation_v1",
        lambda **_kwargs: runtime_observation,
    )
    envelope = evaluator.run_evaluator_v1(
        request,
        observed_runtime=observed_runtime,
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    assert envelope["resource_precharge"][
        "maximum_source_candidate_rows"
    ] == contract.MAX_SELECTION_CANDIDATES_PER_FOLD

    binding = _binding_evidence(request)
    bound_envelope = runner.bind_task_evidence_to_envelope_v1(
        envelope, binding, request
    )
    child_stdout = runner.framed_envelope_bytes_v1(bound_envelope)
    write = budget["write_allowlist"][0]
    output = {
        "topology_ordinal": 0,
        "role": write["role"],
        "source_ordinal": write["source_ordinal"],
        "uri": write["uri"],
        "maximum_bytes": write["max_bytes"],
        "create_once": True,
        "prior_identity": None,
    }
    request_raw = contract.canonical_json_bytes_v1(request)
    task = {
        "task_index": request["source_ordinal"],
        "source_ordinal": request["source_ordinal"],
        "process_ordinal": request["process_ordinal"],
        "phase": contract.BROAD_SCREEN_PHASE,
        "process_role": "broad-evaluator",
        "task_binding_sha256": "5" * 64,
        "task_science_binding_sha256": "9" * 64,
        "request": request,
        "request_sha256": sha256(request_raw).hexdigest(),
        "request_bytes": len(request_raw),
        "expected_outputs": [output],
        "expected_outputs_sha256": "6" * 64,
        "child_command_sha256": "7" * 64,
        "child_stdout_byte_ceiling": evaluator.MAXIMUM_ENVELOPE_BYTES,
        "child_stderr_byte_ceiling": 256_000,
        "maximum_wall_seconds": evaluator.MAXIMUM_EVALUATOR_WALL_SECONDS,
        "maximum_peak_rss_bytes": evaluator.MAXIMUM_EVALUATOR_PEAK_RSS_BYTES,
    }
    task_index = int(request["source_ordinal"])
    manifest = {
        "task_count": task_index + 1,
        "layer_id": "broad-evaluation-result",
        "task_manifest_sha256": "4" * 64,
        "task_bindings": [*({} for _ in range(task_index)), task],
        "required_process_specs": [{
            "process_role": "broad-evaluator",
            "process_chain": [component],
        }],
        "bootstrap_manifest_identity": request["bootstrap_manifest_identity"],
        "bootstrap_manifest_sha256": bootstrap_sha256,
        "pre_design_run_authorization_identity": request[
            "launch_intent_identity"
        ],
        "code_commit": "a" * 40,
        "image_digest": "sha256:" + "b" * 64,
        "reused_job_name": "fixture-evaluator",
    }
    original_bind_body = runner.task_manifest._bind_body

    def bind_manifest_or_exact_body(
        value: object, identity: object, *, label: str,
    ) -> dict[str, object]:
        if label in {"terminal task manifest", "child evidence task manifest"}:
            return dict(identity)
        return original_bind_body(value, identity, label=label)

    def prove_exact(identity_value: Mapping[str, object]) -> dict[str, object]:
        identity = contract._safe_object_identity(
            identity_value, label="terminal evaluator publication"
        )
        raw = store.read_exact(identity)
        assert len(raw) == identity["bytes"]
        assert sha256(raw).hexdigest() == identity["sha256"]
        return identity

    monkeypatch.setattr(
        runner.task_manifest,
        "validate_task_manifest_v1",
        lambda value: dict(value),
    )
    monkeypatch.setattr(
        runner.task_manifest, "_bind_body", bind_manifest_or_exact_body
    )
    monkeypatch.setattr(
        runner.task_manifest,
        "build_dispatcher_runtime_evidence_v1",
        lambda **_kwargs: {
            "task_index": task_index,
            "cloud_execution_name": "fixture-execution",
            "dispatcher_runtime_evidence_sha256": "a" * 64,
        },
    )
    terminal = runner.task_manifest.build_task_terminal_evidence_v1(
        manifest=manifest,
        manifest_identity=binding["manifest_identity"],
        task_index=task_index,
        cloud_execution_name="fixture-execution",
        child_exit_code=0,
        child_stdout=child_stdout,
        child_stderr=b"",
        elapsed_milliseconds=max(
            1_000, int(envelope["observed_elapsed_milliseconds"]) + 1
        ),
        read_exact=store.read_exact,
        prove_exact_identity=prove_exact,
        dispatcher_kernel_observed_command=["fixture-dispatcher"],
        dispatcher_selected_environment={"FIXTURE": "1"},
    )

    assert terminal["task_completed"] is True
    assert terminal["child_exit_code"] == 0
    assert terminal["child_task_binding_evidence"] == binding
    assert terminal["publication_identities"] == [
        bound_envelope["evaluation_publication_identity"]
    ]
    assert terminal["publication_evidence"][0][
        "publication_generation_exact_reopen_proved"
    ] is True


def test_cli_rejects_missing_child_binding_before_cloud_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(runner, "_read_stdin_bounded_v1", lambda: b"{}")

    def reject(_environ: object) -> object:
        calls.append("parse-binding")
        raise ValueError("missing binding")

    monkeypatch.setattr(
        runner.task_manifest,
        "parse_child_task_binding_environment_v1",
        reject,
    )
    monkeypatch.setattr(
        runner,
        "GCSExactCreateOnceTransportV1",
        lambda: pytest.fail("cloud transport must follow child binding parse"),
    )
    with pytest.raises(
        runner.RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="held-out evaluation failed",
    ):
        runner.main()
    assert calls == ["parse-binding"]


def test_stdout_envelope_ceiling_includes_newline_framing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        contract,
        "canonical_json_bytes_v1",
        lambda _value: b"x" * (evaluator.MAXIMUM_ENVELOPE_BYTES - 1),
    )
    framed = runner.framed_envelope_bytes_v1({"fixture": True})
    assert len(framed) == evaluator.MAXIMUM_ENVELOPE_BYTES
    assert framed.endswith(b"\n")
    monkeypatch.setattr(
        contract,
        "canonical_json_bytes_v1",
        lambda _value: b"x" * evaluator.MAXIMUM_ENVELOPE_BYTES,
    )
    with pytest.raises(
        runner.RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error,
        match="stdout byte ceiling",
    ):
        runner.framed_envelope_bytes_v1({"fixture": True})


def test_evaluator_dependency_and_transport_firewalls_are_static() -> None:
    module_path = Path(evaluator.__file__)
    module_source = module_path.read_text(encoding="utf-8")
    module_tree = ast.parse(module_source)
    imported = set()
    for node in ast.walk(module_tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    forbidden = (
        "selector", "selection_fold_worker", "selection_assembler",
        "strategy", "book", "neo4j", "outcome", "lr8_later_period_source",
        "residual_world_columns",
    )
    assert not any(token in name for name in imported for token in forbidden)

    cli_tree = ast.parse(Path(runner.__file__).read_text(encoding="utf-8"))
    called_attributes = {
        node.func.attr
        for node in ast.walk(cli_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert called_attributes.isdisjoint({
        "list_blobs", "reload", "resolve_current", "resolve_optional",
    })
    assert evaluator.FIXED_GCP_PROJECT == "nfl-predictions-503414"
    assert evaluator.FIXED_STORAGE_ENDPOINT == "https://storage.googleapis.com"

    probe = (
        "import json,sys; "
        "from nfl_dfs.research import "
        "corpus_r6_current_bank_crossed_screen_evaluation_v1; "
        "bad=[name for name in sys.modules if (name=='pulp' or "
        "name.startswith('nfl_dfs.optimizer') or 'selector' in name or "
        "'residual_world_columns' in name or 'lr8_exact_solvers' in name or "
        "'lr8_later_period_source' in name)]; print(json.dumps(sorted(bad)))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert json.loads(completed.stdout) == []
