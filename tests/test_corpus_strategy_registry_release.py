from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import corpus_strategy_registry as registry
from nfl_dfs.research import corpus_strategy_registry_release as release
from nfl_dfs.research import corpus_retrieval_neo4j as projection
from nfl_dfs.research.corpus_neo4j_transport import ObjectIdentity


ROOT = Path(__file__).resolve().parents[1]


def _fixture_module() -> ModuleType:
    path = ROOT / "tests/test_corpus_retrieval_neo4j.py"
    spec = importlib.util.spec_from_file_location("_release_parent_fixture", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PARENT = _fixture_module()


class FakeStorage:
    def __init__(self) -> None:
        self.current: dict[str, ObjectIdentity] = {}
        self.exact: dict[tuple[str, str], bytes] = {}
        self.generation = 1_000_000

    def read_exact(self, identity: ObjectIdentity) -> bytes:
        return self.exact[(identity.uri, identity.generation)]

    def resolve_optional(
        self, uri: str,
    ) -> tuple[ObjectIdentity, bytes] | None:
        identity = self.current.get(uri)
        if identity is None:
            return None
        return identity, self.read_exact(identity)

    def publish_create_once(self, uri: str, raw: bytes) -> ObjectIdentity:
        existing = self.resolve_optional(uri)
        if existing is not None:
            assert existing[1] == raw
            return existing[0]
        self.generation += 1
        identity = ObjectIdentity(
            uri=uri,
            generation=str(self.generation),
            sha256=sha256(raw).hexdigest(),
            bytes=len(raw),
        )
        self.current[uri] = identity
        self.exact[(uri, identity.generation)] = raw
        return identity


def _pointer(name: str, ordinal: int) -> dict[str, object]:
    return {
        "uri": f"gs://accepted-evidence/{name}.json",
        "generation": str(ordinal + 1),
        "sha256": sha256(name.encode()).hexdigest(),
        "bytes": 1,
    }


def _verification(task_index: int) -> dict[str, object]:
    endpoints = []
    coverage = []
    outside = []
    for ordinal, parameter_id in enumerate(batch.PARAMETER_SET_ORDER):
        endpoints.append({
            "parameter_set_id": parameter_id,
            "simulated_candidate_ceiling_c": 200.0 + ordinal,
            "simulated_exact80_maximum_s": 190.0 + ordinal,
            "simulated_conversion_gap_c_minus_s": 10.0,
        })
        coverage.append({
            "parameter_set_id": parameter_id,
            "generated_unique_roster_count": 100 + ordinal,
        })
        outside.append({
            "parameter_set_id": parameter_id,
            "outside_incumbent_law_unique_count": ordinal,
        })
    return {
        "task_index": task_index,
        "score_free_endpoint_summaries": endpoints,
        "score_matrix_coverage_summaries": coverage,
        "outside_incumbent_law_summaries": outside,
    }


def _accepted_evidence() -> release.AcceptedBatchEvidence:
    parameter_sets = list(batch.frozen_parameter_sets())
    common_law = {
        "cbwu": _pointer("cbwu", 10),
        "exact_80": _pointer("exact-80", 11),
        "line_194": _pointer("line-194", 12),
        "selector": _pointer("selector", 13),
        "solve_budget": {"selected_entry_budget": 80},
    }
    source_slates = []
    manifest_tasks = []
    accepted_tasks = []
    for task_index in range(release.TASK_COUNT):
        season = 2023 + task_index // 18
        week = task_index % 18 + 1
        slate_id = f"{season}-w{week:02d}"
        team_a = f"a{task_index:02d}"
        team_b = f"b{task_index:02d}"
        game_id = f"A{task_index:02d}|B{task_index:02d}"
        catalog = []
        player_ids = []
        for player_index in range(12):
            player_id = (
                f"DST_A{task_index:02d}"
                if player_index == 0
                else f"p{task_index:02d}{player_index:02d}"
            )
            player_ids.append(player_id)
            first = player_index < 6
            catalog.append({
                "id": player_id,
                "pos": "flex",
                "team": team_a if first else team_b,
                "opp": team_b if first else team_a,
                "game_id": game_id,
                "salary": 5_000,
            })
        rosters = [
            player_ids[:9],
            [*player_ids[:8], player_ids[9]],
            [*player_ids[:8], player_ids[10]],
        ]
        source_slates.append({
            "season": season,
            "week": week,
            "slate_id": slate_id,
            "catalog": catalog,
        })
        worlds = {
            f"world_artifact_r{block}": _pointer(
                f"task-{task_index:04d}-world-r{block}",
                1_000 + task_index * 10 + block,
            )
            for block in range(5)
        }
        manifest_tasks.append({
            "task_index": task_index,
            "season": season,
            "week": week,
            "slate_id": slate_id,
            "world_artifact_receipts": worlds,
        })
        variants = []
        for ordinal, parameter_set in enumerate(parameter_sets):
            parameter_id = str(parameter_set["parameter_set_id"])
            variants.append(release.AcceptedVariantEvidence(
                parameter_set_id=parameter_id,
                parameter_set_sha256=str(parameter_set["parameter_set_sha256"]),
                effective_policy_identity=_pointer(
                    f"task-{task_index:04d}-{parameter_id}-policy",
                    10_000 + task_index * 100 + ordinal,
                ),
                effective_policy={},
                result_identity=_pointer(
                    f"task-{task_index:04d}-{parameter_id}-result",
                    20_000 + task_index * 100 + ordinal,
                ),
                result={"selected_rosters": rosters},
            ))
        accepted_tasks.append(release.AcceptedTaskEvidence(
            task_index=task_index,
            task_acceptance_identity=_pointer(
                f"task-{task_index:04d}-acceptance", 30_000 + task_index
            ),
            task_acceptance={"accepted_at_utc": "2026-08-21T22:00:00Z"},
            task_result_identity=_pointer(
                f"task-{task_index:04d}-task-result", 31_000 + task_index
            ),
            task_result={
                "slate_id": slate_id,
                "task_sha256": sha256(
                    f"task-{task_index:04d}".encode()
                ).hexdigest(),
            },
            science_terminal_identity=_pointer(
                f"task-{task_index:04d}-terminal", 32_000 + task_index
            ),
            science_terminal={},
            independent_verification_identity=_pointer(
                f"task-{task_index:04d}-verification", 33_000 + task_index
            ),
            independent_verification=_verification(task_index),
            variants=tuple(variants),
        ))
    return release.AcceptedBatchEvidence(
        retrieval_plan=PARENT._plan(PARENT._bundle()),
        retrieval_terminal_identity=_pointer("retrieval-terminal", 40_000),
        batch_acceptance_identity=_pointer("batch-acceptance", 40_001),
        batch_acceptance={},
        batch_completion_identity=_pointer("batch-completion", 40_002),
        batch_manifest_identity=_pointer("batch-manifest", 40_003),
        batch_manifest={
            "created_at_utc": "2026-08-21T21:00:00Z",
            "parameter_sets": parameter_sets,
            "common_law": common_law,
            "tasks": manifest_tasks,
        },
        source_freeze_identity=_pointer("source-freeze", 40_004),
        source_freeze={"slates": source_slates},
        exact_release={
            "code_commit": "a" * 40,
            "image": "example.invalid/repo/image@sha256:" + "b" * 64,
            "build_id": "12345678-1234-1234-1234-123456789abc",
        },
        tasks=tuple(accepted_tasks),
    )


def _parent_node(
    *, node_id: str, kind: str, identity: dict[str, object],
    payload: dict[str, object], strategy_id: str = "",
) -> dict[str, object]:
    return {
        "id": node_id,
        "kind": kind,
        "logical_id": node_id,
        "run_id": "accepted-task0",
        "task_id": "2023-w01",
        "payload_sha256": projection.canonical_sha256(payload),
        "properties_json": projection.canonical_json_bytes(payload).decode(),
        "source_uri": identity["uri"],
        "source_generation": identity["generation"],
        "source_sha256": identity["sha256"],
        "source_bytes": identity["bytes"],
        "workstream_namespace": "corpus-retrieval-research",
        "task_index": 0,
        "task_index_present": True,
        "slate_id": "2023-w01",
        "parameter_set_id": "",
        "strategy_id": strategy_id,
        "analysis_scope": "accepted-task0-fixture",
        "metric_name": "",
        "metric_value": 0.0,
        "metric_value_present": False,
    }


def _named_context() -> tuple[projection.Neo4jLoadPlan, dict[str, object]]:
    terminal = _pointer("named-retrieval-terminal", 50_000)
    result = _pointer("named-retrieval-result", 50_001)
    suite = _pointer("named-retrieval-suite", 50_002)
    snapshot = _pointer("named-retrieval-snapshot", 50_003)
    graph = _pointer("named-retrieval-graph", 50_004)
    completion = _pointer("named-retrieval-completion", 50_005)
    shared = _pointer("named-unique-lineup-scores", 50_006)
    execution = {
        "execution_id": "accepted-task0-execution",
        "execution_name": "projects/p/locations/l/jobs/j/executions/e",
        "task_index": 0,
        "attempt": 0,
        "retry_count": 0,
        "mode": "cloud-run-task",
        "code_commit": "e" * 40,
        "image_uri": "example.invalid/retrieval@sha256:" + "f" * 64,
        "image_digest": "sha256:" + "f" * 64,
    }
    nodes = [
        _parent_node(
            node_id="parent-terminal",
            kind="CorpusTerminalReceipt",
            identity=terminal,
            payload={
                "result_object": result,
                "retry_count": 0,
                "uses_realized_outcomes": False,
            },
        )
    ]
    strategy_context: dict[str, object] = {}
    strategy_results = []
    sidecars = [{
        "role": "unique-lineup-scores",
        "strategy_id": "",
        "object_identity": shared,
    }]
    for ordinal, strategy in enumerate(retrieval.frozen_retrieval_strategies()):
        strategy_id = str(strategy["strategy_id"])
        selection = _pointer(f"named-selection-{strategy_id}", 51_000 + ordinal)
        selected_scores = _pointer(
            f"named-selected-scores-{strategy_id}", 52_000 + ordinal
        )
        metrics = {
            "discovery_r0_r3": {
                "world_count": 40_000,
                "portfolio_worlds_gt_200": 1_000 + ordinal,
            },
            "heldout_r4": {
                "world_count": 10_000,
                "portfolio_worlds_gt_200": 200 + ordinal,
            },
            "all_r0_r4_descriptive": {
                "world_count": 50_000,
                "portfolio_worlds_gt_200": 1_200 + ordinal,
            },
        }
        strategy_context[strategy_id] = {
            "strategy": strategy,
            "selection": selection,
            "selected_scores": selected_scores,
            "metrics": metrics,
        }
        strategy_results.append({
            "strategy_id": strategy_id,
            "strategy_sha256": strategy["strategy_sha256"],
            "selection_object": selection,
            "selected_scores_object": selected_scores,
            "metrics": metrics,
        })
        nodes.extend((
            _parent_node(
                node_id=f"parent-strategy-{ordinal}",
                kind="RetrievalStrategyResult",
                identity=graph,
                payload={"strategy_id": strategy_id, "entry_budget": 80},
                strategy_id=strategy_id,
            ),
            _parent_node(
                node_id=f"parent-selection-{ordinal}",
                kind="CorpusArtifactPointer",
                identity=selection,
                payload={"role": "strategy-selection", "strategy_id": strategy_id},
                strategy_id=strategy_id,
            ),
            _parent_node(
                node_id=f"parent-selected-scores-{ordinal}",
                kind="CorpusArtifactPointer",
                identity=selected_scores,
                payload={
                    "role": "strategy-selected-scores",
                    "strategy_id": strategy_id,
                },
                strategy_id=strategy_id,
            ),
        ))
    task_result = {
        "task_index": 0,
        "task_id": "2023-w01",
        "suite_manifest_identity": suite,
        "snapshot_manifest_identity": snapshot,
        "execution": execution,
        "strategy_results": strategy_results,
        "sidecars": sidecars,
    }
    nodes.extend((
        _parent_node(
            node_id="parent-result",
            kind="CorpusTaskResult",
            identity=result,
            payload=task_result,
        ),
        _parent_node(
            node_id="parent-shared-scores",
            kind="CorpusArtifactPointer",
            identity=shared,
            payload={"role": "unique-lineup-scores", "strategy_id": ""},
        ),
    ))
    plan = projection.Neo4jLoadPlan(
        schema_version=projection.LOAD_SCHEMA,
        run_id="accepted-task0",
        task_id="2023-w01",
        terminal_receipt_identity=terminal,
        batch_completion_identity=completion,
        task_result_identity=result,
        graph_projection_identity=graph,
        nodes=tuple(nodes),
        relationships=(),
        plan_sha256="0" * 64,
    )
    context = {
        "terminal": terminal,
        "task_result": result,
        "suite_manifest": suite,
        "snapshot_manifest": snapshot,
        "shared_world_artifacts": [shared],
        "source_execution": execution,
        "slate_id": "2023-w01",
        "strategies": strategy_context,
    }
    return plan, context


@pytest.fixture
def accepted_task0_named_definition() -> dict[str, object]:
    strategies = retrieval.frozen_retrieval_strategies()
    retrieval_presets = sorted(({
        "preset_id": strategy["strategy_id"],
        "version": 1,
        "parameters": release.accepted_task0_retrieval_preset_parameters(
            strategy
        ),
        "description": strategy["description"],
        "deprecated": False,
    } for strategy in strategies), key=lambda row: str(row["preset_id"]))
    baseline = "task0-coverage-194-v1"
    experiments = []
    for strategy in strategies:
        strategy_id = str(strategy["strategy_id"])
        experiment_id = f"task0-{strategy_id}"
        experiments.append({
            "experiment_id": experiment_id,
            "task_index": 0,
            "fill_preset": {
                "preset_id": "accepted-task0-existing-corpus-v1",
                "version": 1,
            },
            "retrieval_preset": {
                "preset_id": strategy_id,
                "version": 1,
            },
            "source_kind": "accepted-task0-retrieval-v1",
            "source_strategy_id": strategy_id,
            "metrics": [
                {
                    "metric_id": "discovery-worlds-gt-200",
                    "source_scope": "discovery_r0_r3",
                    "source_metric": "portfolio_worlds_gt_200",
                    "name": "worlds-gt-200",
                    "unit": "worlds",
                    "direction": "maximize",
                },
                {
                    "metric_id": "heldout-worlds-gt-200",
                    "source_scope": "heldout_r4",
                    "source_metric": "portfolio_worlds_gt_200",
                    "name": "worlds-gt-200",
                    "unit": "worlds",
                    "direction": "descriptive",
                },
            ],
            "paired_design": {
                "required": experiment_id != baseline,
                "comparison_axis": (
                    "none" if experiment_id == baseline else "retrieval"
                ),
                "baseline_experiment_id": (
                    None if experiment_id == baseline else baseline
                ),
            },
        })
    body = {
        "schema_version": registry.NAMED_SCENARIO_DEFINITION_SCHEMA,
        "publication_mode": "create_once",
        "definition_id": "accepted-task0-retrieval-laws-v1",
        "description": "Synthetic fixture for the four accepted task-0 laws.",
        "fill_presets": [{
            "preset_id": "accepted-task0-existing-corpus-v1",
            "version": 1,
            "parameters": release.accepted_task0_existing_corpus_fill_parameters(),
            "description": "Neutral retrospective existing-corpus binding.",
            "deprecated": False,
        }],
        "retrieval_presets": retrieval_presets,
        "accepted_experiments": sorted(
            experiments, key=lambda row: str(row["experiment_id"])
        ),
        "heldout_policy": {
            "heldout_split_registered": True,
            "selection_informed_by_heldout": False,
            "heldout_metrics_descriptive_only": True,
            "ranker_input_authority": False,
            "promotion_authority": False,
        },
        "uses_realized_outcomes": False,
        "automatic_promotion": False,
        "production_policy_authority": False,
    }
    body["named_scenario_definition_sha256"] = projection.canonical_sha256(body)
    return body


def test_release_projects_complete_batch_as_descriptive_no_promotion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = FakeStorage()
    evidence = _accepted_evidence()
    reopen_calls = []

    def reopen(**kwargs: object) -> release.AcceptedBatchEvidence:
        reopen_calls.append(kwargs)
        return evidence

    monkeypatch.setattr(release, "reopen_accepted_batch_evidence", reopen)
    published = release.publish_strategy_registry_release(
        storage=storage,
        retrieval_terminal_identity=evidence.retrieval_terminal_identity,
        batch_acceptance_identity=evidence.batch_acceptance_identity,
        registry_id="accepted-54x7-registry-v1",
        output_prefix="gs://registry-output/accepted-54x7-registry-v1/",
        created_at_utc="2026-08-21T23:00:00Z",
        producer_release={
            "code_commit": "c" * 40,
            "image": "example.invalid/repo/producer@sha256:" + "d" * 64,
            "build_id": "87654321-4321-4321-4321-cba987654321",
        },
    )
    replayed = release.publish_strategy_registry_release(
        storage=storage,
        retrieval_terminal_identity=evidence.retrieval_terminal_identity,
        batch_acceptance_identity=evidence.batch_acceptance_identity,
        registry_id="accepted-54x7-registry-v1",
        output_prefix="gs://registry-output/accepted-54x7-registry-v1/",
        created_at_utc="2026-08-21T23:00:00Z",
        producer_release={
            "code_commit": "c" * 40,
            "image": "example.invalid/repo/producer@sha256:" + "d" * 64,
            "build_id": "87654321-4321-4321-4321-cba987654321",
        },
    )
    assert replayed.release_identity == published.release_identity
    assert replayed.publication_identity == published.publication_identity
    # The additive named-scenario path must not perturb the original v2 bytes.
    assert published.release_identity.sha256 == (
        "936cd0e1199759ee457c8c4f3521ff2fdc4948fb500ff3bc0807035703172cda"
    )
    assert published.publication_identity.sha256 == (
        "6dc65acb05c8e642066cd7f6d18b22fe9878816f414a4448c4e0f53c4ec5893c"
    )
    bundle = registry.prepare_strategy_registry_plan(
        parent_plan=evidence.retrieval_plan,
        storage=storage,
        release_identity=published.release_identity.as_dict(),
    )

    assert len(bundle.release["fill_presets"]) == 7
    assert len(bundle.release["retrieval_presets"]) == 1
    assert len(bundle.release["corpus_snapshots"]) == 378
    assert len(bundle.release["experiment_runs"]) == 378
    assert bundle.release["promotion_decisions"] == []
    assert bundle.release["active_strategy_pointers"] == []
    assert published.publication["metric_scope"] == "all-worlds-descriptive"
    assert published.publication["heldout_split_registered"] is False
    assert published.publication["selection_informed_by_heldout"] is False
    assert published.publication[
        "selection_informed_by_evaluation_worlds"
    ] is True
    assert published.publication["realized_namespace_reserved"] is True
    assert published.publication["registration_mode"] == (
        "retrospective-pointer-binding"
    )
    assert published.publication["new_gate_claimed_pre_execution"] is False
    assert published.publication["publication_intent"] == storage.current[
        "gs://registry-output/accepted-54x7-registry-v1/publication-intent.json"
    ].as_dict()
    assert len(reopen_calls) == 2
    assert reopen_calls[0]["retrieval_terminal_identity"] == (
        evidence.retrieval_terminal_identity
    )
    assert published.publication["sampled_unique_lineup_count"] <= 54 * 21
    first_structure_identity = ObjectIdentity(
        **published.release["slate_structures"][0]
    )
    first_structure = projection.parse_canonical_json_bytes(
        storage.read_exact(first_structure_identity), label="first structure"
    )
    assert isinstance(first_structure, dict)
    assert first_structure["games"][0]["game_id"].startswith("a")
    assert "|" not in first_structure["games"][0]["game_id"]
    assert any(
        player["player_id"].startswith("dst_a")
        for player in first_structure["players"]
    )
    first_experiment = projection.parse_canonical_json_bytes(
        storage.read_exact(ObjectIdentity(
            **published.release["experiment_runs"][0]
        )),
        label="first experiment",
    )
    assert isinstance(first_experiment, dict)
    retrospective_gate = projection.parse_canonical_json_bytes(
        storage.read_exact(ObjectIdentity(
            **first_experiment["pre_execution_gate"]
        )),
        label="retrospective registration",
    )
    assert isinstance(retrospective_gate, dict)
    assert retrospective_gate["registered_before_execution"] is False
    assert retrospective_gate["retrospective_binding"] is True
    assert retrospective_gate["task_acceptance"] in [
        task.task_acceptance_identity for task in evidence.tasks
    ]
    registry_nodes = [
        row for row in bundle.plan.nodes
        if row["workstream_namespace"] == registry.REGISTRY_NAMESPACE
    ]
    assert not any(
        row["kind"] in {"PromotionDecision", "ActiveStrategyPointer"}
        for row in registry_nodes
    )
    assert sum(
        row["kind"] == "ExperimentRetrospectiveRegistration"
        for row in registry_nodes
    ) == 378
    assert not any(
        row["kind"] == "ExperimentPreExecutionGate"
        for row in registry_nodes
    )
    metric_scopes = {
        row["analysis_scope"] for row in registry_nodes
        if row["kind"] == "Metric"
    }
    assert metric_scopes == {"all-worlds-descriptive"}


def test_release_requires_an_output_bucket_dedicated_from_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = FakeStorage()
    evidence = _accepted_evidence()
    monkeypatch.setattr(
        release,
        "reopen_accepted_batch_evidence",
        lambda **_kwargs: evidence,
    )
    with pytest.raises(
        release.CorpusStrategyRegistryReleaseError,
        match="bucket dedicated away",
    ):
        release.publish_strategy_registry_release(
            storage=storage,
            retrieval_terminal_identity=evidence.retrieval_terminal_identity,
            batch_acceptance_identity=evidence.batch_acceptance_identity,
            registry_id="accepted-54x7-registry-v1",
            output_prefix="gs://accepted-evidence/registry-v1/",
            created_at_utc="2026-08-21T23:00:00Z",
            producer_release={
                "code_commit": "c" * 40,
                "image": (
                    "example.invalid/repo/producer@sha256:" + "d" * 64
                ),
                "build_id": "87654321-4321-4321-4321-cba987654321",
            },
        )
    assert storage.current == {}


def test_named_definition_registers_accepted_task0_retrieval_laws(
    monkeypatch: pytest.MonkeyPatch,
    accepted_task0_named_definition: dict[str, object],
) -> None:
    storage = FakeStorage()
    parent_plan, named_context = _named_context()
    evidence = replace(
        _accepted_evidence(),
        retrieval_plan=parent_plan,
        retrieval_terminal_identity=named_context["terminal"],
    )
    monkeypatch.setattr(
        release,
        "reopen_accepted_batch_evidence",
        lambda **_kwargs: evidence,
    )
    monkeypatch.setattr(
        release,
        "_accepted_task0_retrieval_context",
        lambda **_kwargs: named_context,
    )

    published = release.publish_strategy_registry_release(
        storage=storage,
        retrieval_terminal_identity=evidence.retrieval_terminal_identity,
        batch_acceptance_identity=evidence.batch_acceptance_identity,
        registry_id="accepted-task0-named-registry-v1",
        output_prefix="gs://registry-output/accepted-task0-named-v1/",
        created_at_utc="2026-08-22T03:00:00Z",
        producer_release={
            "code_commit": "c" * 40,
            "image": "example.invalid/repo/producer@sha256:" + "d" * 64,
            "build_id": "87654321-4321-4321-4321-cba987654321",
        },
        named_scenario_definitions=[accepted_task0_named_definition],
    )
    bundle = registry.prepare_strategy_registry_plan(
        parent_plan=parent_plan,
        storage=storage,
        release_identity=published.release_identity.as_dict(),
    )

    assert published.release["schema_version"] == registry.NAMED_RELEASE_SCHEMA
    assert len(published.release["fill_presets"]) == 8
    assert len(published.release["retrieval_presets"]) == 5
    assert len(published.release["experiment_runs"]) == 378
    assert len(published.release["named_scenario_definitions"]) == 1
    assert len(published.release["accepted_scenario_evidence"]) == 4
    assert published.publication["named_scenario_definition_count"] == 1
    assert published.publication["accepted_scenario_evidence_count"] == 4
    assert published.publication[
        "named_heldout_metrics_descriptive_only"
    ] is True
    assert published.publication["named_ranker_input_authority"] is False
    assert published.publication["automatic_promotion"] is False
    assert published.publication["production_policy_authority"] is False

    registry_nodes = [
        row for row in bundle.plan.nodes
        if row["workstream_namespace"] == registry.REGISTRY_NAMESPACE
    ]
    assert sum(
        row["kind"] == "NamedScenarioDefinition" for row in registry_nodes
    ) == 1
    assert sum(
        row["kind"] == "AcceptedScenarioExperimentEvidence"
        for row in registry_nodes
    ) == 4
    assert sum(
        row["kind"] == "ExperimentRun" for row in registry_nodes
    ) == 378

    evidence_payloads = [
        projection.parse_canonical_json_bytes(
            row["properties_json"].encode(), label="accepted scenario evidence"
        )
        for row in registry_nodes
        if row["kind"] == "AcceptedScenarioExperimentEvidence"
    ]
    assert {
        row["source_strategy"]["strategy_id"] for row in evidence_payloads
    } == {
        strategy["strategy_id"]
        for strategy in retrieval.frozen_retrieval_strategies()
    }
    assert all(row["uses_realized_outcomes"] is False for row in evidence_payloads)
    assert all(
        row["historical_outcome_read_authority"] is False
        for row in evidence_payloads
    )
    assert all(
        row["production_policy_authority"] is False
        for row in evidence_payloads
    )
    assert all(row["automatic_promotion"] is False for row in evidence_payloads)
    assert all(
        metric["direction"] == "descriptive"
        for row in evidence_payloads
        for metric in row["metrics"]
        if metric["source_scope"] == "heldout_r4"
    )
    assert "boom" not in projection.canonical_json_bytes(
        accepted_task0_named_definition
    ).decode()

    assert all(
        row["heldout_design"]["ranker_input_authority"] is False
        and row["heldout_design"]["promotion_authority"] is False
        and row["heldout_design"]["heldout_metrics_descriptive_only"] is True
        for row in evidence_payloads
    )
    paired_rows = [
        row["paired_design"] for row in evidence_payloads
        if row["paired_design"]["required"] is True
    ]
    baseline_rows = [
        row["paired_design"] for row in evidence_payloads
        if row["paired_design"]["required"] is False
    ]
    assert len(paired_rows) == 3
    assert len(baseline_rows) == 1
    assert all(row["comparison_axis"] == "retrieval" for row in paired_rows)
    assert all(row["same_snapshot"] is True for row in paired_rows)
    assert all(row["same_worlds"] is True for row in paired_rows)
    assert all(row["baseline_evidence"] is not None for row in paired_rows)
    assert baseline_rows[0]["comparison_axis"] == "none"
    assert baseline_rows[0]["baseline_evidence"] is None


def test_named_definition_rejects_heldout_metric_as_ranker_signal(
    accepted_task0_named_definition: dict[str, object],
) -> None:
    invalid = deepcopy(accepted_task0_named_definition)
    invalid["accepted_experiments"][0]["metrics"][1]["direction"] = "maximize"
    invalid.pop("named_scenario_definition_sha256")
    invalid["named_scenario_definition_sha256"] = projection.canonical_sha256(
        invalid
    )

    with pytest.raises(
        registry.CorpusStrategyRegistryError,
        match="heldout_r4 metric direction must be descriptive",
    ):
        registry.validate_named_scenario_definition(invalid)
