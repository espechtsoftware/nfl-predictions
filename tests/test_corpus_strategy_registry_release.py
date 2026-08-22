from __future__ import annotations

from hashlib import sha256
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
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
