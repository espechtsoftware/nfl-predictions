from __future__ import annotations

import argparse
import ast
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import os
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest

from scripts import run_corpus_r6_current_bank_crossed_screen_projection_v1 as cli
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_contract_v1 as contract
from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_projection_v1 as projection
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as task_manifest,
)
from nfl_dfs.research import corpus_r6_full_union_panel_freeze_v1 as freeze
def _identity(uri: str, raw: bytes, generation: int = 1) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _tag_identity(tag: str, generation: int = 1) -> dict[str, object]:
    return _identity(f"gs://fixture/{tag}.json", tag.encode("utf-8"), generation)


def _projection_binding_evidence(
    request: Mapping[str, object],
) -> dict[str, object]:
    raw = contract.canonical_json_bytes_v1(request)
    body = {
        "schema_version": task_manifest.CHILD_TASK_BINDING_EVIDENCE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "manifest_identity": _tag_identity("projection-task-manifest"),
        "task_manifest_sha256": "1" * 64,
        "layer_id": "projection",
        "phase": "projection",
        "process_role": "projection-publisher",
        "task_index": 0,
        "source_ordinal": None,
        "process_ordinal": 0,
        "task_binding_sha256": "2" * 64,
        "request_sha256": sha256(raw).hexdigest(),
        "request_bytes": len(raw),
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


class _MemoryStore:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str, str, int], bytes] = {}
        self.current: dict[str, tuple[dict[str, object], bytes]] = {}
        self.read_counts: Counter[tuple[str, str, str, int]] = Counter()
        self.publish_uris: list[str] = []
        self.events: list[tuple[str, str]] = []
        self.generation = 10_000

    @staticmethod
    def _key(value: object) -> tuple[str, str, str, int]:
        assert isinstance(value, dict)
        return (
            str(value["uri"]),
            str(value["generation"]),
            str(value["sha256"]),
            int(value["bytes"]),
        )

    def add_raw(
        self, uri: str, raw: bytes, *, generation: int | None = None,
    ) -> dict[str, object]:
        if generation is None:
            self.generation += 1
            generation = self.generation
        identity = _identity(uri, raw, generation)
        self.values[self._key(identity)] = bytes(raw)
        self.current[uri] = (identity, bytes(raw))
        return identity

    def add_json(
        self, uri: str, value: object, *, generation: int | None = None,
    ) -> dict[str, object]:
        return self.add_raw(
            uri,
            contract.canonical_json_bytes_v1(value),
            generation=generation,
        )

    def read_exact(self, identity: Any) -> bytes:
        key = self._key(identity)
        self.read_counts[key] += 1
        self.events.append(("read", key[0]))
        return self.values[key]

    def publish_create_once(
        self, uri: str, raw: bytes, *, prior_identity: object | None = None,
    ) -> dict[str, object]:
        self.publish_uris.append(uri)
        self.events.append(("publish", uri))
        if prior_identity is not None:
            retained = dict(prior_identity)
            if (
                retained.get("uri") != uri
                or retained.get("bytes") != len(raw)
                or retained.get("sha256") != sha256(raw).hexdigest()
            ):
                raise RuntimeError("prior create-once identity differs")
            return retained
        existing = self.current.get(uri)
        if existing is not None:
            if existing[1] != raw:
                raise RuntimeError("create-once collision differs")
            return dict(existing[0])
        return self.add_raw(uri, raw)

def _candidates(count: int = 80) -> list[dict[str, object]]:
    rows = []
    for index in range(count):
        roster = sorted(f"p-{index:03d}-{player}" for player in range(9))
        rows.append({
            "lineup_id": f"lineup:{index:064x}",
            "roster_player_ids": roster,
            "training_origin_blocks": [],
            "training_source_arms": [],
            "training_occurrence_counts_by_block": {},
            "training_source_arms_by_block": {},
            "training_occurrence_count": 0,
        })
    return rows


def _task_result(slate_id: str, *, candidate_count: int = 80) -> dict[str, object]:
    scopes = []
    strategies = contract.frozen_strategies_v1()
    for fold, heldout in enumerate(contract.WORLD_BLOCKS):
        training_blocks = [block for block in contract.WORLD_BLOCKS if block != heldout]
        candidates = deepcopy(_candidates(candidate_count))
        for candidate in candidates:
            candidate["training_origin_blocks"] = list(training_blocks)
            candidate["training_source_arms"] = ["incumbent"]
            candidate["training_occurrence_counts_by_block"] = {
                block: 1 for block in training_blocks
            }
            candidate["training_source_arms_by_block"] = {
                block: ["incumbent"] for block in training_blocks
            }
            candidate["training_occurrence_count"] = len(training_blocks)
        lineup_ids = [str(candidate["lineup_id"]) for candidate in candidates]
        ids_sha = contract.canonical_sha256_v1(lineup_ids)
        matrix_sha = sha256(f"matrix-{slate_id}-{fold}".encode()).hexdigest()
        books = [
            {
                "strategy_id": strategy["strategy_id"],
                "strategy_sha256": strategy["strategy_sha256"],
                "fit_scope_id": f"holdout-{heldout}",
                "heldout_block": heldout,
                "training_blocks": list(training_blocks),
                "input_lineup_ids_sha256": ids_sha,
                "training_score_shape": [candidate_count, 40_000],
                "training_score_matrix_sha256": matrix_sha,
                # These upstream book fields must never be copied.
                "selected_lineup_ids": lineup_ids[:80],
                "selected_rosters": [
                    candidate["roster_player_ids"] for candidate in candidates[:80]
                ],
                "marginal_trace": [{"rank": 0}],
                "heldout_metrics_descriptive": {"mean": 999.0},
                "training_metrics": {"mean": 888.0},
            }
            for strategy in strategies
        ]
        scopes.append({
            "fit_scope_id": f"holdout-{heldout}",
            "candidate_view": {
                "eligible_candidates": candidates,
                "fit_candidate_view_sha256": sha256(
                    f"view-{slate_id}-{fold}".encode()
                ).hexdigest(),
                "selection_provenance_sha256": sha256(
                    f"provenance-{slate_id}-{fold}".encode()
                ).hexdigest(),
            },
            "books": books,
        })
    scopes.append({
        "fit_scope_id": "all-block-final-fit",
        "candidate_view": {"eligible_candidates": []},
        "books": [],
        "selected_lineup_ids": ["must-not-copy"],
    })
    return {
        "slate_id": slate_id,
        "later_source_freeze_identity": _tag_identity(f"later-{slate_id}", 500),
        "world_artifact_identities": {
            f"world_artifact_{block.lower()}": _tag_identity(
                f"world-{slate_id}-{block.lower()}", 600 + index
            )
            for index, block in enumerate(contract.WORLD_BLOCKS)
        },
        "full_union_surface": {
            "rotated_simulated_fold_count": 5,
            "final_fit_is_distinct_all_block_refit": True,
            "scopes": scopes,
        },
    }


def _build_direct_bundle(
    result: dict[str, object], *, source_ordinal: int = 0,
) -> dict[str, object]:
    raw = contract.canonical_json_bytes_v1(result)
    identity = _identity(
        f"gs://fixture/source-task-{source_ordinal}.json",
        raw,
        700 + source_ordinal,
    )
    return projection._build_projection_bundle_from_task_surface_v1(
        source_ordinal=source_ordinal,
        slate_id=str(result["slate_id"]),
        source_task_result_identity=identity,
        task_result_payload_sha256=batch.canonical_sha256(result),
        task_result=result,
    )


def test_direct_projection_emits_five_narrow_fold_views_only() -> None:
    bundle = _build_direct_bundle(_task_result("2023-w01"))
    assert bundle["fold_order"] == list(contract.WORLD_BLOCKS)
    assert len(bundle["fold_projections"]) == 5
    assert bundle["selector_executed"] is False
    assert bundle["old_book_fields_copied"] is False
    assert "all-block-final-fit" not in contract.canonical_json_bytes_v1(bundle).decode()
    for fold, item in enumerate(bundle["fold_projections"]):
        assert item["fit_scope_id"] == f"holdout-R{fold}"
        assert item["expected_training_score_shape"] == [80, 40_000]
        assert len(item["candidates"]) == 80
        keys = set(item)
        assert not any(key.startswith("selected_") for key in keys)
        assert not any(key.startswith("marginal_") for key in keys)
        assert "heldout_metrics_descriptive" not in keys
        assert "training_metrics" not in keys
    assert contract.validate_projection_bundle_v1(bundle) == bundle


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("input_lineup_ids_sha256", "0" * 64, "candidate order/input/shape"),
        ("training_score_shape", [80, 39_999], "candidate order/input/shape"),
        ("training_score_matrix_sha256", "0" * 64, "share one training matrix"),
    ],
)
def test_direct_projection_rejects_any_one_of_eight_book_authorities_drifting(
    field: str,
    replacement: object,
    message: str,
) -> None:
    result = _task_result("2023-w01")
    result["full_union_surface"]["scopes"][0]["books"][7][field] = replacement
    with pytest.raises(
        projection.CorpusR6CurrentBankCrossedScreenProjectionV1Error,
        match=message,
    ):
        _build_direct_bundle(result)


def test_projection_schema_rejects_reintroduced_selected_or_marginal_fields() -> None:
    bundle = _build_direct_bundle(_task_result("2023-w01"))
    for field in ("selected_lineup_ids", "marginal_trace"):
        mutated = deepcopy(bundle)
        mutated["fold_projections"][0][field] = []
        with pytest.raises(
            projection.CorpusR6CurrentBankCrossedScreenProjectionV1Error,
            match="copies an old book/heldout/marginal field",
        ):
            projection._forbid_old_book_output_fields(mutated)


def _full_synthetic_authorities(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    _MemoryStore,
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    store = _MemoryStore()
    manifest_identity = store.add_raw(
        "gs://fixture/structural/manifest.json", b"manifest", generation=2
    )
    fixed_panel_identity = store.add_raw(
        "gs://fixture/structural/fixed-panel.json", b"fixed-panel", generation=3
    )
    descriptors = []
    leaves = []
    results = []
    for ordinal in range(54):
        slate_id = f"{2023 + ordinal // 18}-w{ordinal % 18 + 1:02d}"
        result = _task_result(slate_id)
        payload_sha = batch.canonical_sha256(result)
        task_identity = store.add_json(
            f"gs://fixture/structural/task-{ordinal:02d}.json",
            {"task_result_payload_sha256": payload_sha},
            generation=100 + ordinal,
        )
        leaf = {
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "task_result_identity": task_identity,
        }
        leaf_identity = store.add_json(
            f"gs://fixture/structural/leaf-{ordinal:02d}.json",
            leaf,
            generation=200 + ordinal,
        )
        descriptors.append({
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "slate_freeze_identity": leaf_identity,
            "task_result_identity": task_identity,
        })
        leaves.append(leaf)
        results.append(result)
    root_body: dict[str, object] = {
        "manifest_identity": manifest_identity,
        "panel_index_identity": fixed_panel_identity,
        "source_slate_count": 54,
        "rank_80_book_count": 2_592,
        "prefix_count": 7_776,
        "slate_freezes": descriptors,
    }
    root_body["panel_freeze_sha256"] = contract.canonical_sha256_v1(root_body)
    root_identity = store.add_json(
        "gs://fixture/structural/panel-freeze.json",
        root_body,
        generation=1,
    )
    monkeypatch.setattr(contract, "PANEL_IDENTITY", root_identity)
    monkeypatch.setattr(
        contract,
        "PANEL_SELF_SHA256",
        root_body["panel_freeze_sha256"],
    )

    identity_by_leaf_uri = {
        descriptor["slate_freeze_identity"]["uri"]: descriptor[
            "slate_freeze_identity"
        ]
        for descriptor in descriptors
    }
    ordinal_by_leaf_uri = {
        descriptor["slate_freeze_identity"]["uri"]: ordinal
        for ordinal, descriptor in enumerate(descriptors)
    }

    def reopen_panel(identity: object, *, read_exact: Any):
        read_exact(identity)
        read_exact(manifest_identity)
        read_exact(fixed_panel_identity)
        for descriptor in descriptors:
            read_exact(descriptor["slate_freeze_identity"])
            read_exact(descriptor["task_result_identity"])
        return root_body, root_identity

    def reopen_slate(identity: object, *, read_exact: Any):
        uri = str(identity["uri"])
        ordinal = ordinal_by_leaf_uri[uri]
        descriptor = descriptors[ordinal]
        read_exact(identity_by_leaf_uri[uri])
        read_exact(manifest_identity)
        read_exact(fixed_panel_identity)
        read_exact(descriptor["task_result_identity"])
        return (
            leaves[ordinal],
            {"manifest": True},
            {"fixed_panel": True},
            [],
            results[ordinal],
            identity_by_leaf_uri[uri],
        )

    monkeypatch.setattr(freeze, "reopen_panel_freeze_v1", reopen_panel)
    monkeypatch.setattr(freeze, "reopen_slate_freeze_v1", reopen_slate)

    output_prefix = contract.OUTPUT_NAMESPACE + "synthetic-projection-run/"
    topology = contract.build_result_topology_v1(output_prefix)
    topology_identity = store.add_json(
        "gs://fixture/authority/topology.json", topology, generation=5_000
    )
    code_commit = "a" * 40
    image_digest = "sha256:" + "b" * 64
    run_authorization = task_manifest.build_pre_design_run_authorization_v1(
        output_prefix=output_prefix,
        code_commit=code_commit,
        image_digest=image_digest,
        reused_job_name="synthetic-projection-job",
    )
    run_authorization_identity = store.add_json(
        task_manifest.pre_design_run_authorization_uri_v1(output_prefix),
        run_authorization,
        generation=5_001,
    )
    bootstrap_manifest = contract.build_bootstrap_manifest_v1(
        topology=topology,
        topology_identity=topology_identity,
        run_identity=run_authorization_identity,
        code_commit=code_commit,
        image_digest=image_digest,
        process_specs=task_manifest.canonical_bootstrap_process_specs_v1(),
    )
    bootstrap_manifest_identity = store.add_json(
        "gs://fixture/authority/bootstrap-manifest.json",
        bootstrap_manifest,
        generation=5_002,
    )
    design = contract.build_design_v1(
        output_prefix=output_prefix,
        code_identity=_tag_identity("authority/code", 5_003),
        report_identity=_tag_identity("authority/report", 5_004),
        topology_identity=topology_identity,
        bootstrap_manifest=bootstrap_manifest,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
    )
    design_uri = str(design["topology"]["objects"][0]["uri"])
    design_identity = store.add_json(design_uri, design, generation=5_005)
    structural = [
        root_identity,
        manifest_identity,
        fixed_panel_identity,
        *[
            identity
            for descriptor in descriptors
            for identity in (
                descriptor["slate_freeze_identity"],
                descriptor["task_result_identity"],
            )
        ],
    ]
    return store, design_identity, topology_identity, structural, descriptors


def test_full_projection_execution_reads_exact_111_and_publishes_54_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, design_identity, topology_identity, structural, _descriptors = (
        _full_synthetic_authorities(monkeypatch)
    )
    summary = projection.publish_projection_layer_v1(
        design_identity=design_identity,
        topology_identity=topology_identity,
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    expected_uris = [
        str(row["uri"])
        for row in contract.build_result_topology_v1(
            contract.OUTPUT_NAMESPACE + "synthetic-projection-run/"
        )["objects"]
        if row["role"] == "projection"
    ]
    assert store.publish_uris == expected_uris
    assert summary["projection_count"] == 54


def test_projection_core_completes_through_exact_process_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, design_identity, topology_identity, structural, _descriptors = (
        _full_synthetic_authorities(monkeypatch)
    )
    design = task_manifest.strict_json_v1(
        store.read_exact(design_identity), label="budget test design"
    )
    topology = task_manifest.strict_json_v1(
        store.read_exact(topology_identity), label="budget test topology"
    )
    bootstrap = dict(design["bootstrap_manifest"])
    bootstrap_identity = dict(design["bootstrap_manifest_identity"])
    authorization_identity = dict(bootstrap["run_identity"])
    budget = contract.compile_publisher_process_budget_v1(
        process_role="projection-publisher",
        design=design,
        design_publication_identity=design_identity,
        topology_identity=topology_identity,
        bootstrap_manifest=bootstrap,
        bootstrap_manifest_identity=bootstrap_identity,
        launch_intent_identity=authorization_identity,
        scientific_read_identities=structural,
    )
    budget_identity = store.add_json(
        "gs://fixture/authority/projection-process-budget.json", budget
    )
    request = task_manifest.build_projection_task_request_v1(
        design_identity=design_identity,
        topology_identity=topology_identity,
        bootstrap_manifest_identity=bootstrap_identity,
        pre_design_run_authorization_identity=authorization_identity,
        process_budget_identity=budget_identity,
        prior_projection_identities=[None] * contract.PANEL_SLATE_COUNT,
    )
    args = argparse.Namespace(
        execute=True,
        project=cli.PROJECT,
        design_uri=design_identity["uri"],
        design_generation=design_identity["generation"],
        design_sha256=design_identity["sha256"],
        design_bytes=design_identity["bytes"],
        topology_uri=topology_identity["uri"],
        topology_generation=topology_identity["generation"],
        topology_sha256=topology_identity["sha256"],
        topology_bytes=topology_identity["bytes"],
        resume_identity_json=[],
    )
    monkeypatch.setenv(cli.ENABLE_ENV, "1")
    for name in cli.FORBIDDEN_REDIRECT_ENV:
        monkeypatch.delenv(name, raising=False)
    store.read_counts.clear()
    gate = cli._ProjectionBudgetedObjectStoreV1(
        store=store,
        process_budget=budget,
        process_budget_identity=request["process_budget_identity"],
        request=request,
    )
    summary = cli._run(args, store=gate)
    execution = gate.require_complete()
    assert execution["read_object_count"] == 113
    assert execution["write_object_count"] == 54
    assert [
        row["publication_identity"] for row in execution["write_ledger"]
    ] == summary["projection_identities"]
    assert sum(store.read_counts.values()) == 113 + 54
    assert all(
        store.read_counts[store._key(identity)] == 1
        for identity in summary["projection_identities"]
    )
    assert summary["projection_layer"]["entry_count"] == 54
    assert summary["source_ordinal_order"] == list(range(54))
    assert summary["structural_replay"] == {
        "structural_object_count": 111,
        "underlying_exact_read_count": 111,
        "structural_identities_sha256": contract.canonical_sha256_v1(structural),
        "no_listing_api": True,
        "no_current_generation_input_read": True,
    }
    for identity in structural:
        assert store.read_counts[store._key(identity)] == 1
    assert summary["selector_executed"] is False
    assert summary["world_artifact_read"] is False
    assert summary["old_seven_arm_reconstruction_executed"] is False
    assert summary["old_book_fields_copied"] is False


def test_projection_publication_is_byte_identical_create_once_resumable() -> None:
    store = _MemoryStore()
    uri = contract.OUTPUT_NAMESPACE + "resume/projections/slate-00.json"
    raw = b'{"projection":"fixture"}'
    first = store.publish_create_once(uri, raw)
    second = store.publish_create_once(uri, raw)
    assert first == second
    assert projection._publication_identity_v1(
        uri=uri,
        raw=raw,
        returned_identity=second,
        read_exact=store.read_exact,
    ) == first


def test_structural_cache_rejects_unlisted_or_second_generation_before_read() -> None:
    store = _MemoryStore()
    identities = [
        store.add_raw(
            f"gs://fixture/cache/{index:03d}.json",
            f"body-{index}".encode(),
            generation=index + 1,
        )
        for index in range(111)
    ]
    cache = projection.StructuralObjectCacheV1(
        read_exact=store.read_exact,
        allowed_identities=identities,
    )
    drift = dict(identities[0])
    drift["generation"] = "999999"
    with pytest.raises(
        projection.CorpusR6CurrentBankCrossedScreenProjectionV1Error,
        match="outside the exact 111-object allowlist",
    ):
        cache.read_exact(drift)
    assert sum(store.read_counts.values()) == 0


def test_projection_module_has_no_selector_dispatcher_or_listing_dependency() -> None:
    source = Path(projection.__file__).read_text(encoding="utf-8")
    assert "current_bank_crossed_screen_selector" not in source
    assert "run_strategy" not in source
    assert "list_blobs" not in source
    assert "resolve_current" not in source


def test_cli_requires_explicit_project_execute_and_environment_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = argparse.Namespace(execute=False, project=cli.PROJECT)
    with pytest.raises(cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error):
        cli._require_gate(args)
    args.execute = True
    monkeypatch.delenv(cli.ENABLE_ENV, raising=False)
    with pytest.raises(cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error):
        cli._require_gate(args)
    monkeypatch.setenv(cli.ENABLE_ENV, "1")
    cli._require_gate(args)
    args.project = "wrong-project"
    with pytest.raises(cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error):
        cli._require_gate(args)


def test_strict_projection_collision_requires_recorded_identity_without_extra_get() -> None:
    class Conflict(Exception):
        pass

    raw = b'{"projection":"recorded"}'
    uri = contract.OUTPUT_NAMESPACE + "strict-resume/projections/slate-00.json"
    prior = _identity(uri, raw, generation=77)
    blob_calls: list[tuple[str, int | None]] = []
    download_calls: list[tuple[int | None, int | None]] = []
    collision = {"enabled": True}

    class Blob:
        def __init__(self, name: str, generation: int | None) -> None:
            self.name = name
            self.generation = generation

        def upload_from_string(self, *_args: object, **_kwargs: object) -> None:
            if collision["enabled"]:
                raise Conflict("occupied")
            self.generation = 88

        def download_as_bytes(self, *, if_generation_match: int) -> bytes:
            download_calls.append((self.generation, if_generation_match))
            return raw

    class Bucket:
        def blob(self, name: str, generation: int | None = None) -> Blob:
            blob_calls.append((name, generation))
            return Blob(name, generation)

    class Client:
        def bucket(self, _name: str) -> Bucket:
            return Bucket()

    store = object.__new__(cli._StrictProjectionObjectStore)
    store._client = Client()
    assert store.publish_create_once(
        uri, raw, prior_identity=prior
    ) == prior
    assert blob_calls == []
    assert download_calls == []

    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error,
        match="lacks a recorded exact identity",
    ):
        store.publish_create_once(uri, raw, prior_identity=None)
    # The collision-without-authority path never performs any exact or current
    # read.  There is no LIST/resolve/current-generation method on this adapter.
    assert download_calls == []
    assert blob_calls[-1] == (
        "research/corpus-r6-current-bank-crossed-screens/strict-resume/"
        "projections/slate-00.json",
        None,
    )
    collision["enabled"] = False
    fresh_uri = (
        contract.OUTPUT_NAMESPACE
        + "strict-resume/projections/slate-01.json"
    )
    created = store.publish_create_once(
        fresh_uri, raw, prior_identity=None
    )
    assert created == {
        "uri": fresh_uri,
        "generation": "88",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    assert download_calls == []
    assert not hasattr(store, "resolve_optional")


def test_projection_cli_semantics_and_redirects_fail_before_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valid = _tag_identity("projection-cli-input")
    args = argparse.Namespace(
        execute=True,
        project=cli.PROJECT,
        design_uri=valid["uri"],
        design_generation=valid["generation"],
        design_sha256=valid["sha256"],
        design_bytes=valid["bytes"],
        topology_uri=valid["uri"],
        topology_generation=valid["generation"],
        topology_sha256=valid["sha256"],
        topology_bytes=valid["bytes"],
        resume_identity_json=["not-json"],
    )
    monkeypatch.setenv(cli.ENABLE_ENV, "1")
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error,
        match="not canonical JSON",
    ):
        cli._validated_request_v1(args)

    args.resume_identity_json = []
    monkeypatch.setenv("STORAGE_EMULATOR_HOST", "http://hostile.invalid")
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error,
        match="redirect is forbidden",
    ):
        cli._validated_request_v1(args)
    monkeypatch.delenv("STORAGE_EMULATOR_HOST")

    args.execute = False
    class Parser:
        @staticmethod
        def parse_args(_argv: object = None) -> argparse.Namespace:
            return args

    request = cli.task_manifest.build_projection_task_request_v1(
        design_identity=valid,
        topology_identity=valid,
        bootstrap_manifest_identity=valid,
        pre_design_run_authorization_identity=valid,
        process_budget_identity=_tag_identity("projection-process-budget"),
        prior_projection_identities=[None] * contract.PANEL_SLATE_COUNT,
    )
    raw_request = contract.canonical_json_bytes_v1(request)
    observed = [
        str(Path(sys.executable).resolve()),
        str(Path(cli.__file__).resolve()),
    ]
    monkeypatch.setattr(
        cli,
        "_read_stdin_bounded_v1",
        lambda: raw_request,
    )
    monkeypatch.setattr(
        cli.task_manifest,
        "parse_child_task_binding_environment_v1",
        lambda _environ: {
            "manifest_identity": _tag_identity("projection-task-manifest"),
            "layer_id": "projection",
            "task_index": 0,
            "request_sha256": sha256(raw_request).hexdigest(),
            "child_command_sha256": contract.canonical_sha256_v1({
                "command": observed,
                "entrypoint_sha256": sha256(
                    Path(cli.__file__).read_bytes()
                ).hexdigest(),
            }),
        },
    )
    monkeypatch.setattr(
        cli,
        "observed_process_command_v1",
        lambda: observed,
    )
    monkeypatch.setattr(cli, "_parser", lambda: Parser())
    monkeypatch.setattr(
        cli,
        "_StrictProjectionObjectStore",
        lambda **_kwargs: pytest.fail("cloud client must not be constructed"),
    )
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error,
        match="publication failed",
    ):
        cli.main()


def test_projection_summary_self_hashes_exact_child_task_binding() -> None:
    design = _tag_identity("bound-projection-design")
    topology = _tag_identity("bound-projection-topology")
    bootstrap = _tag_identity("bound-projection-bootstrap")
    authorization = _tag_identity("bound-projection-authorization")
    structural = [
        _tag_identity(f"bound-structural-{index:03d}")
        for index in range(contract.EXACT_STRUCTURAL_OBJECT_COUNT)
    ]
    projection_identities = [
        _tag_identity(f"bound-projection-{index:02d}")
        for index in range(contract.PANEL_SLATE_COUNT)
    ]
    process_budget = {
        "schema_version": contract.PUBLISHER_PROCESS_BUDGET_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "process_role": "projection-publisher",
        "read_allowlist": [
            {"role": "design", "identity": design},
            {"role": "topology", "identity": topology},
            {"role": "bootstrap-manifest", "identity": bootstrap},
            {"role": "launch-intent", "identity": authorization},
            *[
                {"role": f"scientific-{index:03d}", "identity": identity}
                for index, identity in enumerate(structural)
            ],
        ],
        "write_allowlist": [
            {
                "ordinal": index + 1,
                "role": "projection",
                "uri": identity["uri"],
                "max_bytes": 1_000_000,
                "create_once": True,
            }
            for index, identity in enumerate(projection_identities)
        ],
    }
    process_budget["publisher_process_budget_sha256"] = (
        contract.canonical_sha256_v1(process_budget)
    )
    process_budget_identity = _identity(
        "gs://fixture/bound-projection-process-budget.json",
        contract.canonical_json_bytes_v1(process_budget),
    )
    request = task_manifest.build_projection_task_request_v1(
        design_identity=design,
        topology_identity=topology,
        bootstrap_manifest_identity=bootstrap,
        pre_design_run_authorization_identity=authorization,
        process_budget_identity=process_budget_identity,
        prior_projection_identities=[None] * contract.PANEL_SLATE_COUNT,
    )
    raw = contract.canonical_json_bytes_v1(request)
    summary = {
        "schema_version": projection.PROJECTION_EXECUTION_SUMMARY_SCHEMA,
        "design_identity": design,
        "topology_identity": topology,
        "projection_identities": projection_identities,
    }
    summary["projection_execution_summary_sha256"] = (
        contract.canonical_sha256_v1(summary)
    )
    evidence = _projection_binding_evidence(request)
    runtime_observation = {
        "process_role": "projection-publisher",
        "process_budget_identity": process_budget_identity,
        "process_budget_sha256": process_budget[
            "publisher_process_budget_sha256"
        ],
    }
    runtime_observation["runtime_observation_sha256"] = (
        contract.canonical_sha256_v1(runtime_observation)
    )
    read_ledger = [
        {
            "ordinal": index,
            "role": (
                ["design", "topology"][index]
                if index < 2 else f"structural-{index - 2:03d}"
            ),
            "identity": [design, topology, *structural][index],
        }
        for index in range(2 + contract.EXACT_STRUCTURAL_OBJECT_COUNT)
    ]
    write_ledger = [
        {
            "ordinal": index + 1,
            "role": "projection",
            "uri": identity["uri"],
            "maximum_bytes": 1_000_000,
            "publication_identity": identity,
            "exact_generation_reopen_proved": True,
        }
        for index, identity in enumerate(summary["projection_identities"])
    ]
    budget_execution = {
        "read_ledger": read_ledger,
        "read_ledger_sha256": contract.canonical_sha256_v1(read_ledger),
        "read_object_count": len(read_ledger),
        "write_ledger": write_ledger,
        "write_ledger_sha256": contract.canonical_sha256_v1(write_ledger),
        "write_object_count": len(write_ledger),
        "read_budget_exhausted": True,
        "write_budget_exhausted": True,
    }
    retained = cli.bind_task_evidence_to_summary_v1(
        summary, evidence, request_value=request, raw_request=raw,
        process_budget_value=process_budget,
        runtime_observation_value=runtime_observation,
        budget_execution_value=budget_execution,
    )
    assert retained["task_binding_evidence"] == evidence
    assert retained["projection_task_request_sha256"] == request[
        "projection_task_request_sha256"
    ]
    digest = retained.pop("projection_execution_summary_sha256")
    assert digest == contract.canonical_sha256_v1(retained)

    spliced = dict(evidence)
    spliced["process_role"] = "broad-evaluator"
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error,
        match="binding evidence differs",
    ):
        cli.bind_task_evidence_to_summary_v1(
            summary, spliced, request_value=request, raw_request=raw,
            process_budget_value=process_budget,
            runtime_observation_value=runtime_observation,
            budget_execution_value=budget_execution,
        )

    ledger_mutations: list[dict[str, object]] = []
    changed_read = deepcopy(budget_execution)
    changed_read["read_ledger"][2]["role"] = "structural-999"
    changed_read["read_ledger_sha256"] = contract.canonical_sha256_v1(
        changed_read["read_ledger"]
    )
    ledger_mutations.append(changed_read)
    changed_write = deepcopy(budget_execution)
    changed_write["write_ledger"][0]["ordinal"] = 999
    changed_write["write_ledger_sha256"] = contract.canonical_sha256_v1(
        changed_write["write_ledger"]
    )
    ledger_mutations.append(changed_write)
    changed_identity = deepcopy(budget_execution)
    changed_identity["write_ledger"][0]["publication_identity"] = (
        _tag_identity("spliced-publication")
    )
    changed_identity["write_ledger_sha256"] = contract.canonical_sha256_v1(
        changed_identity["write_ledger"]
    )
    ledger_mutations.append(changed_identity)
    changed_reopen = deepcopy(budget_execution)
    changed_reopen["write_ledger"][0][
        "exact_generation_reopen_proved"
    ] = False
    changed_reopen["write_ledger_sha256"] = contract.canonical_sha256_v1(
        changed_reopen["write_ledger"]
    )
    ledger_mutations.append(changed_reopen)
    changed_count = deepcopy(budget_execution)
    changed_count["read_object_count"] = 112
    ledger_mutations.append(changed_count)
    changed_exhaustion = deepcopy(budget_execution)
    changed_exhaustion["write_budget_exhausted"] = False
    ledger_mutations.append(changed_exhaustion)
    for mutation in ledger_mutations:
        with pytest.raises(
            cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error,
            match="budget execution",
        ):
            cli.bind_task_evidence_to_summary_v1(
                summary, evidence, request_value=request, raw_request=raw,
                process_budget_value=process_budget,
                runtime_observation_value=runtime_observation,
                budget_execution_value=mutation,
            )


def test_projection_process_budget_enforces_every_core_read_and_write() -> None:
    store = _MemoryStore()
    design = store.add_raw("gs://fixture/budget/design.json", b"design")
    topology = store.add_raw("gs://fixture/budget/topology.json", b"topology")
    bootstrap = store.add_raw("gs://fixture/budget/bootstrap.json", b"bootstrap")
    authorization = store.add_raw(
        "gs://fixture/budget/authorization.json", b"authorization"
    )
    structural = [
        store.add_raw(
            f"gs://fixture/budget/structural-{index:03d}.json",
            f"structural-{index:03d}".encode("utf-8"),
        )
        for index in range(contract.EXACT_STRUCTURAL_OBJECT_COUNT)
    ]
    writes = [
        {
            "ordinal": index + 1,
            "role": "projection",
            "uri": f"{contract.OUTPUT_NAMESPACE}budget/projections/{index:02d}.json",
            "max_bytes": 128,
            "create_once": True,
        }
        for index in range(contract.PANEL_SLATE_COUNT)
    ]
    budget = {
        "process_role": "projection-publisher",
        "read_allowlist": [
            {"role": "design", "identity": design},
            {"role": "topology", "identity": topology},
            {"role": "bootstrap-manifest", "identity": bootstrap},
            {"role": "launch-intent", "identity": authorization},
            *[
                {"role": f"scientific-{index:03d}", "identity": identity}
                for index, identity in enumerate(structural)
            ],
        ],
        "write_allowlist": writes,
    }
    request = {
        "design_identity": design,
        "topology_identity": topology,
        "bootstrap_manifest_identity": bootstrap,
        "pre_design_run_authorization_identity": authorization,
    }
    gate = cli._ProjectionBudgetedObjectStoreV1(
        store=store,
        process_budget=budget,
        process_budget_identity=_tag_identity("budget-authority"),
        request=request,
    )
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error,
        match="before read-budget exhaustion",
    ):
        gate.publish_create_once(writes[0]["uri"], b"first", prior_identity=None)
    for identity in [design, topology, *structural]:
        gate.read_exact(identity)
    published = []
    for index, descriptor in enumerate(writes):
        identity = gate.publish_create_once(
            descriptor["uri"],
            f"projection-{index:02d}".encode("utf-8"),
            prior_identity=None,
        )
        assert gate.read_exact(identity) == f"projection-{index:02d}".encode(
            "utf-8"
        )
        published.append(identity)
    execution = gate.require_complete()
    assert execution["read_object_count"] == 113
    assert execution["write_object_count"] == 54
    assert execution["read_ledger"][2]["role"] == "structural-000"
    assert execution["write_ledger"][0] == {
        "ordinal": 1,
        "role": "projection",
        "uri": writes[0]["uri"],
        "maximum_bytes": 128,
        "publication_identity": published[0],
        "exact_generation_reopen_proved": True,
    }
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error,
        match="output reopen differs",
    ):
        gate.read_exact(published[-1])
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error,
        match="exceeds its process budget",
    ):
        gate.publish_create_once(writes[-1]["uri"], b"again", prior_identity=None)

    reordered = cli._ProjectionBudgetedObjectStoreV1(
        store=store,
        process_budget=budget,
        process_budget_identity=_tag_identity("budget-authority"),
        request=request,
    )
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error,
        match="read differs",
    ):
        reordered.read_exact(topology)

    resumed = cli._ProjectionBudgetedObjectStoreV1(
        store=store,
        process_budget=budget,
        process_budget_identity=_tag_identity("budget-authority"),
        request=request,
    )
    for identity in [design, topology, *structural]:
        resumed.read_exact(identity)
    first = resumed.publish_create_once(
        writes[0]["uri"], b"projection-00", prior_identity=published[0]
    )
    assert first == published[0]
    reads_before_reopen = store.read_counts[store._key(first)]
    assert resumed.read_exact(first) == b"projection-00"
    assert store.read_counts[store._key(first)] == reads_before_reopen + 1
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error,
        match="output reopen differs",
    ):
        resumed.read_exact(first)

    corrupted = cli._ProjectionBudgetedObjectStoreV1(
        store=store,
        process_budget=budget,
        process_budget_identity=_tag_identity("budget-authority"),
        request=request,
    )
    for identity in [design, topology, *structural]:
        corrupted.read_exact(identity)
    pending = corrupted.publish_create_once(
        writes[0]["uri"], b"projection-00", prior_identity=published[0]
    )
    key = store._key(pending)
    original_body = store.values[key]
    store.values[key] = b"X" * len(original_body)
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error,
        match="exact-reopen body differs",
    ):
        corrupted.read_exact(pending)
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error,
        match="prior exact reopen",
    ):
        corrupted.publish_create_once(
            writes[1]["uri"], b"projection-01", prior_identity=None
        )
    store.values[key] = original_body


def test_projection_main_reopens_controller_runtime_and_budget_before_science(
    monkeypatch: pytest.MonkeyPatch, capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    store, design_identity, topology_identity, structural, _descriptors = (
        _full_synthetic_authorities(monkeypatch)
    )
    design = task_manifest.strict_json_v1(
        store.read_exact(design_identity), label="main test design"
    )
    topology = task_manifest.strict_json_v1(
        store.read_exact(topology_identity), label="main test topology"
    )
    bootstrap = dict(design["bootstrap_manifest"])
    bootstrap_identity = dict(design["bootstrap_manifest_identity"])
    authorization_identity = dict(bootstrap["run_identity"])
    authorization = task_manifest.strict_json_v1(
        store.read_exact(authorization_identity), label="main test authorization"
    )
    budget = contract.compile_publisher_process_budget_v1(
        process_role="projection-publisher",
        design=design,
        design_publication_identity=design_identity,
        topology_identity=topology_identity,
        bootstrap_manifest=bootstrap,
        bootstrap_manifest_identity=bootstrap_identity,
        launch_intent_identity=authorization_identity,
        scientific_read_identities=structural,
    )
    budget_identity = store.add_json(
        "gs://fixture/authority/main-projection-process-budget.json", budget
    )
    request = task_manifest.build_projection_task_request_v1(
        design_identity=design_identity,
        topology_identity=topology_identity,
        bootstrap_manifest_identity=bootstrap_identity,
        pre_design_run_authorization_identity=authorization_identity,
        process_budget_identity=budget_identity,
        prior_projection_identities=[None] * contract.PANEL_SLATE_COUNT,
    )
    manifest = task_manifest.build_task_manifest_v1(
        layer_id="projection",
        design=design,
        design_identity=design_identity,
        topology=topology,
        topology_identity=topology_identity,
        bootstrap_manifest=bootstrap,
        bootstrap_manifest_identity=bootstrap_identity,
        pre_design_run_authorization=authorization,
        pre_design_run_authorization_identity=authorization_identity,
        task_requests=[request],
        predecessor_layer_receipts=[],
        projection_process_budget=budget,
    )
    manifest_identity = store.add_json(
        str(manifest["manifest_uri"]), manifest
    )
    binding_environment = task_manifest.child_task_binding_environment_v1(
        manifest, manifest_identity=manifest_identity, task_index=0
    )
    for name in list(os.environ):
        if name.startswith("R6_TASK_"):
            monkeypatch.delenv(name, raising=False)
    for name in cli.FORBIDDEN_REDIRECT_ENV:
        monkeypatch.delenv(name, raising=False)
    for name, value in binding_environment.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv(cli.ENABLE_ENV, "1")
    monkeypatch.setenv("CODE_SHA", str(bootstrap["code_commit"]))
    monkeypatch.setenv(
        "R6_RUNTIME_IMAGE_DIGEST", str(bootstrap["image_digest"])
    )
    monkeypatch.setenv("CLOUD_RUN_JOB", str(authorization["reused_job_name"]))
    monkeypatch.setenv("CLOUD_RUN_EXECUTION", "projection-main-fixture-1")
    monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "0")
    raw_request = contract.canonical_json_bytes_v1(request)
    observed_command = list(manifest["task_bindings"][0]["child_command"])
    monkeypatch.setattr(cli, "_read_stdin_bounded_v1", lambda: raw_request)
    monkeypatch.setattr(
        cli, "observed_process_command_v1", lambda: observed_command
    )
    constructed: list[str] = []

    def construct_store(*, project: str) -> _MemoryStore:
        constructed.append(project)
        store.events.append(("client", project))
        return store

    monkeypatch.setattr(cli, "_StrictProjectionObjectStore", construct_store)
    original_runtime = cli.build_projection_runtime_observation_v1

    def mark_runtime(**kwargs: object) -> dict[str, object]:
        store.events.append(("runtime", "projection-publisher"))
        return original_runtime(**kwargs)

    monkeypatch.setattr(
        cli, "build_projection_runtime_observation_v1", mark_runtime
    )
    task = manifest["task_bindings"][0]
    process_budget_bindings = (
        task_manifest._exact_task_process_budget_bindings_v1(
            manifest=manifest,
            task=task,
            read_exact=store.read_exact,
        )
    )
    store.events.clear()
    store.read_counts.clear()
    store.publish_uris.clear()
    cli.main()
    stdout = capsysbinary.readouterr().out
    assert stdout.endswith(b"\n") and not stdout.endswith(b"\n\n")
    envelope = task_manifest.strict_json_v1(
        stdout[:-1], label="projection main stdout"
    )
    task_manifest._validate_child_envelope_transport_v1(
        manifest=manifest,
        task=task,
        value=envelope,
        process_budget_bindings=process_budget_bindings,
        child_elapsed_milliseconds=7_200_000,
        cloud_execution_name="projection-main-fixture-1",
    )
    assert constructed == [cli.PROJECT]
    assert store.events[0] == ("client", cli.PROJECT)
    assert store.events[1] == ("read", manifest_identity["uri"])
    runtime_index = store.events.index(("runtime", "projection-publisher"))
    first_publish = next(
        index for index, event in enumerate(store.events)
        if event[0] == "publish"
    )
    core_events = store.events[runtime_index + 1:first_publish]
    assert len(core_events) == 113
    assert all(event[0] == "read" for event in core_events)
    output_events = store.events[first_publish:]
    assert len(output_events) == 108
    assert all(
        output_events[index][0] == ("publish" if index % 2 == 0 else "read")
        and output_events[index][1] == output_events[index - index % 2][1]
        for index in range(len(output_events))
    )
    assert envelope["read_object_count"] == 113
    assert envelope["write_object_count"] == 54

    parsed_binding = task_manifest.parse_child_task_binding_environment_v1(
        os.environ
    )
    base_environment = dict(os.environ)
    controller_errors = (
        task_manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error,
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        KeyError,
    )
    command_mutations = [
        [*observed_command, "--hostile-extra"],
        [*observed_command[:-2], observed_command[-1], observed_command[-2]],
        observed_command[:-1],
    ]
    for changed_command in command_mutations:
        changed_environment = dict(base_environment)
        changed_environment[task_manifest.CHILD_COMMAND_HASH_ENV] = (
            contract.canonical_sha256_v1({
                "command": changed_command,
                "entrypoint_sha256": sha256(
                    Path(cli.__file__).read_bytes()
                ).hexdigest(),
            })
        )
        store.events.clear()
        with pytest.raises(controller_errors):
            cli.reopen_controller_projection_task_after_client_v1(
                parsed_binding={
                    **parsed_binding,
                    "child_command_sha256": changed_environment[
                        task_manifest.CHILD_COMMAND_HASH_ENV
                    ],
                },
                environ=changed_environment,
                raw_request=raw_request,
                observed_command=changed_command,
                read_exact=store.read_exact,
            )
        assert store.events == [("read", manifest_identity["uri"])]

    changed_environment = dict(base_environment)
    changed_environment[task_manifest.CHILD_REQUEST_HASH_ENV] = "f" * 64
    store.events.clear()
    with pytest.raises(controller_errors):
        cli.reopen_controller_projection_task_after_client_v1(
            parsed_binding={
                **parsed_binding,
                "request_sha256": "f" * 64,
            },
            environ=changed_environment,
            raw_request=raw_request,
            observed_command=observed_command,
            read_exact=store.read_exact,
        )
    assert store.events == [("read", manifest_identity["uri"])]

    for field, replacement in (
        ("generation", "999999"),
        ("sha256", "f" * 64),
    ):
        changed_identity = dict(manifest_identity)
        changed_identity[field] = replacement
        store.events.clear()
        with pytest.raises(controller_errors):
            cli.reopen_controller_projection_task_after_client_v1(
                parsed_binding={
                    **parsed_binding,
                    "manifest_identity": changed_identity,
                },
                environ=base_environment,
                raw_request=raw_request,
                observed_command=observed_command,
                read_exact=store.read_exact,
            )
        assert not any(event[0] in {"runtime", "publish"} for event in store.events)

    store.events.clear()

    def altered_manifest_body(identity: Mapping[str, object]) -> bytes:
        retained = dict(identity)
        store.events.append(("read", str(retained["uri"])))
        if retained == manifest_identity:
            return b"{}"
        return store.read_exact(retained)

    with pytest.raises(controller_errors):
        cli.reopen_controller_projection_task_after_client_v1(
            parsed_binding=parsed_binding,
            environ=base_environment,
            raw_request=raw_request,
            observed_command=observed_command,
            read_exact=altered_manifest_body,
        )
    assert store.events == [("read", manifest_identity["uri"])]

    runtime_authority = {
        "bootstrap_manifest": bootstrap,
        "projection_process_budget": budget,
        "pre_design_run_authorization": authorization,
    }
    runtime_mutations = [
        ({**base_environment, "CODE_SHA": "f" * 40}, observed_command),
        ({**base_environment, "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "f" * 64}, observed_command),
        ({**base_environment, "CLOUD_RUN_JOB": "wrong-job"}, observed_command),
        ({**base_environment, "CLOUD_RUN_TASK_INDEX": "1"}, observed_command),
        (base_environment, ["/hostile/python", *observed_command[1:]]),
    ]
    for changed_environment, changed_command in runtime_mutations:
        with pytest.raises(
            cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error,
        ):
            original_runtime(
                authority=runtime_authority,
                request=request,
                observed_command=changed_command,
                environ=changed_environment,
            )


def test_projection_cli_observes_kernel_command_and_has_no_graph_import() -> None:
    expected = [
        str(Path(sys.executable).resolve()),
        str(Path(cli.__file__).resolve()),
        "--execute",
    ]
    raw = b"\0".join(token.encode("utf-8") for token in expected) + b"\0"
    assert cli.observed_process_command_v1(raw) == expected
    prefix = (
        expected[0].encode("utf-8") + b"\0"
        + expected[1].encode("utf-8") + b"\0"
    )
    exact = prefix + b"x" * (
        cli.MAXIMUM_PROCESS_COMMAND_BYTES - len(prefix) - 1
    ) + b"\0"
    assert len(exact) == cli.MAXIMUM_PROCESS_COMMAND_BYTES
    assert cli.observed_process_command_v1(exact)[:2] == expected[:2]
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error,
        match="command differs",
    ):
        cli.observed_process_command_v1(exact + b"\0")
    with pytest.raises(
        cli.RunCorpusR6CurrentBankCrossedScreenProjectionV1Error,
        match="entrypoint differs",
    ):
        cli.observed_process_command_v1(
            b"/hostile/python\0/hostile/projection.py\0--execute\0"
        )

    tree = ast.parse(Path(cli.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    assert not any("neo4j" in name for name in imported)
