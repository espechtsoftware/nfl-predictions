from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from nfl_dfs.research import corpus_neo4j_transport as transport
from nfl_dfs.research import corpus_retrieval_neo4j as projection
from nfl_dfs.research import corpus_strategy_registry as registry


ROOT = Path(__file__).resolve().parents[1]
EXACT_RELEASE = {
    "code_commit": "1" * 40,
    "image": "us-docker.pkg.dev/p/r/engine@sha256:" + "2" * 64,
    "build_id": "12345678-1234-1234-1234-123456789abc",
}


def _fixture_module() -> ModuleType:
    path = ROOT / "tests/test_corpus_retrieval_neo4j.py"
    spec = importlib.util.spec_from_file_location(
        "_strategy_registry_parent_fixture", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PARENT_FIXTURES = _fixture_module()


def _self_hash(value: dict[str, Any], field: str) -> dict[str, Any]:
    retained = deepcopy(value)
    retained[field] = projection.canonical_sha256(retained)
    return retained


def _placeholder_identity(name: str, generation: int) -> dict[str, object]:
    raw = f"placeholder:{name}".encode()
    return {
        "uri": f"gs://registry-fixture/pointers/{name}",
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _identity_key(value: dict[str, object]) -> tuple[object, ...]:
    return tuple(value[key] for key in ("uri", "generation", "sha256", "bytes"))


class FakeStorage:
    def __init__(self) -> None:
        self.exact: dict[tuple[str, str], bytes] = {}
        self.current: dict[str, transport.ObjectIdentity] = {}
        self.reads: list[tuple[str, str]] = []
        self.next_generation = 10_000

    def publish(self, name: str, body: dict[str, object]) -> dict[str, object]:
        raw = projection.canonical_json_bytes(body)
        self.next_generation += 1
        identity = {
            "uri": f"gs://registry-fixture/objects/{name}.json",
            "generation": str(self.next_generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.exact[(str(identity["uri"]), str(identity["generation"]))] = raw
        return identity

    def read_exact(self, identity: transport.ObjectIdentity) -> bytes:
        key = (identity.uri, identity.generation)
        self.reads.append(key)
        return self.exact[key]

    def resolve_optional(
        self, uri: str
    ) -> tuple[transport.ObjectIdentity, bytes] | None:
        identity = self.current.get(uri)
        if identity is None:
            return None
        return identity, self.exact[(identity.uri, identity.generation)]

    def publish_create_once(
        self, uri: str, raw: bytes
    ) -> transport.ObjectIdentity:
        existing = self.resolve_optional(uri)
        if existing is not None:
            if existing[1] != raw:
                raise transport.CorpusNeo4jTransportError(
                    "fake create-once conflict"
                )
            return existing[0]
        self.next_generation += 1
        identity = transport.ObjectIdentity(
            uri=uri,
            generation=str(self.next_generation),
            sha256=sha256(raw).hexdigest(),
            bytes=len(raw),
        )
        self.exact[(identity.uri, identity.generation)] = raw
        self.current[identity.uri] = identity
        return identity


def _sort_identities(values: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(values, key=_identity_key)


def _metric_rows(
    *,
    discovery: float,
    heldout: float,
    baseline: dict[str, object] | None,
) -> list[dict[str, object]]:
    return [
        {
            "metric_id": "discovery-score",
            "name": "score",
            "value": discovery,
            "unit": "fantasy-points",
            "direction": "maximize",
            "scope": "discovery",
            "sample_count": 40_000,
            "paired_key": "world-id",
            "baseline_experiment_run": baseline,
        },
        {
            "metric_id": "heldout-score",
            "name": "score",
            "value": heldout,
            "unit": "fantasy-points",
            "direction": "maximize",
            "scope": "heldout",
            "sample_count": 10_000,
            "paired_key": "world-id",
            "baseline_experiment_run": baseline,
        },
    ]


def _metrics(
    *,
    experiment_id: str,
    discovery: float,
    heldout: float,
    baseline: dict[str, object] | None,
    comparison_axis: str,
    authority: dict[str, dict[str, object]],
) -> dict[str, object]:
    rows = _metric_rows(
        discovery=discovery, heldout=heldout, baseline=baseline
    )
    return _self_hash(
        {
            "schema_version": registry.METRIC_SET_SCHEMA,
            "publication_mode": "create_once",
            "experiment_id": experiment_id,
            "metrics": rows,
            "paired_design": {
                "required": baseline is not None,
                "comparison_axis": comparison_axis,
                "same_snapshot": comparison_axis == "retrieval",
                "same_worlds": True,
                "paired_key": "world-id",
            },
            "heldout_design": {
                "heldout_split_registered": True,
                "selection_informed_by_heldout": False,
            },
            **authority,
            "uses_realized_outcomes": False,
            "historical_outcome_read_authority": False,
            "outcome_namespace_read": False,
            "outcome_columns_read": [],
        },
        "metric_set_sha256",
    )


def _experiment(
    *,
    experiment_id: str,
    fill: dict[str, object],
    retrieval: dict[str, object],
    snapshot: dict[str, object],
    matrix: dict[str, object],
    metric_set: dict[str, object],
    authority: dict[str, dict[str, object]],
) -> dict[str, object]:
    return _self_hash(
        {
            "schema_version": registry.EXPERIMENT_SCHEMA,
            "publication_mode": "create_once",
            "experiment_id": experiment_id,
            "task_index": 0,
            "slate_id": "2023-w1-main",
            "fill_preset": fill,
            "retrieval_preset": retrieval,
            "corpus_snapshot": snapshot,
            "exact_release": EXACT_RELEASE,
            "matrix_artifacts": [matrix],
            "metric_set": metric_set,
            **authority,
            "status": "complete-accepted",
            "uses_realized_outcomes": False,
            "historical_outcome_read_authority": False,
            "outcome_namespace_read": False,
            "outcome_columns_read": [],
            "automatic_promotion": False,
            "application_config_mutation": False,
            "production_policy_authority": False,
        },
        "experiment_run_sha256",
    )


def _authority(
    *,
    storage: FakeStorage,
    experiment_id: str,
    fill: dict[str, object],
    fill_parameters: list[dict[str, object]],
    retrieval: dict[str, object],
    retrieval_parameters: list[dict[str, object]],
    snapshot: dict[str, object],
    matrix: dict[str, object],
    metric_rows: list[dict[str, object]],
    exact_release: dict[str, str] = EXACT_RELEASE,
) -> dict[str, dict[str, object]]:
    firewall = {
        "uses_realized_outcomes": False,
        "historical_outcome_read_authority": False,
        "outcome_namespace_read": False,
        "outcome_columns_read": [],
    }
    effective = storage.publish(
        f"{experiment_id}-effective-parameters",
        _self_hash(
            {
                "schema_version": registry.EFFECTIVE_PARAMETERS_SCHEMA,
                "publication_mode": "create_once",
                "experiment_id": experiment_id,
                "fill_preset": fill,
                "retrieval_preset": retrieval,
                "fill_parameters": fill_parameters,
                "retrieval_parameters": retrieval_parameters,
                **firewall,
            },
            "effective_parameters_sha256",
        ),
    )
    gate = storage.publish(
        f"{experiment_id}-pre-execution-gate",
        _self_hash(
            {
                "schema_version": registry.PRE_EXECUTION_GATE_SCHEMA,
                "publication_mode": "create_once",
                "gate_id": f"{experiment_id}-gate",
                "experiment_id": experiment_id,
                "task_index": 0,
                "slate_id": "2023-w1-main",
                "fill_preset": fill,
                "retrieval_preset": retrieval,
                "corpus_snapshot": snapshot,
                "matrix_artifacts": [matrix],
                "effective_parameters": effective,
                "exact_release": exact_release,
                "registered_before_execution": True,
                "gate_passed": True,
                **firewall,
                "created_at_utc": "2026-08-21T11:00:00Z",
            },
            "pre_execution_gate_sha256",
        ),
    )
    retained: dict[str, dict[str, object]] = {
        "pre_execution_gate": gate,
        "effective_parameters": effective,
    }

    def evidence(
        field: str,
        role: str,
        dependencies: list[dict[str, object]],
        minute: int,
        *,
        metric_digest: str | None = None,
    ) -> dict[str, object]:
        identity = storage.publish(
            f"{experiment_id}-{field}",
            _self_hash(
                {
                    "schema_version": registry.EVIDENCE_BINDING_SCHEMA,
                    "publication_mode": "create_once",
                    "evidence_id": f"{experiment_id}-{field}",
                    "experiment_id": experiment_id,
                    "evidence_role": role,
                    "task_index": 0,
                    "slate_id": "2023-w1-main",
                    "exact_release": exact_release,
                    "dependencies": _sort_identities(dependencies),
                    "accepted": True,
                    "complete": True,
                    "computed_metrics_sha256": metric_digest,
                    **firewall,
                    "created_at_utc": f"2026-08-21T11:{minute:02d}:00Z",
                },
                "evidence_binding_sha256",
            ),
        )
        retained[field] = identity
        return identity

    execution = evidence(
        "accepted_execution", "accepted-execution", [gate, effective], 1
    )
    result = evidence(
        "accepted_result", "accepted-result", [execution, effective], 2
    )
    verification = evidence(
        "independent_verification",
        "independent-verification",
        [result, effective],
        3,
    )
    selection = evidence(
        "selection_evidence",
        "selection-evidence",
        [result, verification, effective],
        4,
    )
    evidence(
        "metric_computation",
        "metric-computation",
        [result, verification, effective, selection],
        5,
        metric_digest=projection.canonical_sha256(metric_rows),
    )
    return retained


def _build_fixture(
    *,
    include_winners: bool = False,
    request_winners_without_authority: bool = False,
    invalid_typed_parameter: bool = False,
    automatic_promotion: bool = False,
    embed_matrix_values: bool = False,
    invalid_pairing_axis: bool = False,
    snapshot_fill_mismatch: bool = False,
    omit_promotion: bool = False,
    effective_parameter_drift: bool = False,
    computed_metric_drift: bool = False,
    cross_experiment_evidence: bool = False,
    metric_authority_mismatch: bool = False,
    realized_outcome_read: bool = False,
    authority_release_drift: bool = False,
) -> tuple[FakeStorage, dict[str, object], dict[str, object]]:
    storage = FakeStorage()
    source_manifest = _placeholder_identity("source-snapshot-manifest", 1)
    matrix = _placeholder_identity("world-matrix.npz", 2)

    fill_bodies = [
        _self_hash(
            {
                "schema_version": registry.FILL_PRESET_SCHEMA,
                "publication_mode": "create_once",
                "preset_id": "baseline-fill",
                "version": 1,
                "parameters": [
                    {"name": "candidate-count", "type": "integer", "value": 80}
                ],
                "description": "Frozen baseline corpus population.",
                "deprecated": False,
                "research_only": True,
                "production_policy_authority": False,
            },
            "fill_preset_sha256",
        ),
        _self_hash(
            {
                "schema_version": registry.FILL_PRESET_SCHEMA,
                "publication_mode": "create_once",
                "preset_id": "tail-fill",
                "version": 1,
                "parameters": [
                    {
                        "name": "candidate-count",
                        "type": "integer",
                        "value": True if invalid_typed_parameter else 194,
                    },
                    {"name": "tail-weight", "type": "number", "value": 1.5},
                ],
                "description": "Tail-focused independent fill preset.",
                "deprecated": False,
                "research_only": True,
                "production_policy_authority": False,
            },
            "fill_preset_sha256",
        ),
    ]
    fill_ids = [
        storage.publish(f"fill-{ordinal}", body)
        for ordinal, body in enumerate(fill_bodies)
    ]

    retrieval_bodies = [
        _self_hash(
            {
                "schema_version": registry.RETRIEVAL_PRESET_SCHEMA,
                "publication_mode": "create_once",
                "preset_id": "baseline-retrieval",
                "version": 1,
                "parameters": [
                    {"name": "minimum-score", "type": "number", "value": 0.0}
                ],
                "description": "Frozen baseline retrieval preset.",
                "deprecated": False,
                "research_only": True,
                "production_policy_authority": False,
            },
            "retrieval_preset_sha256",
        ),
        _self_hash(
            {
                "schema_version": registry.RETRIEVAL_PRESET_SCHEMA,
                "publication_mode": "create_once",
                "preset_id": "strict200-retrieval",
                "version": 1,
                "parameters": [
                    {"name": "minimum-score", "type": "number", "value": 200.0},
                    {"name": "strict-threshold", "type": "boolean", "value": True},
                ],
                "description": "Score every lineup, then retrieve strict >200.",
                "deprecated": False,
                "research_only": True,
                "production_policy_authority": False,
            },
            "retrieval_preset_sha256",
        ),
    ]
    retrieval_ids = [
        storage.publish(f"retrieval-{ordinal}", body)
        for ordinal, body in enumerate(retrieval_bodies)
    ]

    pointer: dict[str, object] = {
        "role": "world-matrix",
        "format": "canonical-compressed-npz-v1",
        "object_identity": matrix,
        "contains_world_matrix": True,
        "contains_raw_outcomes": False,
    }
    if embed_matrix_values:
        pointer["matrix_values"] = [[1.0, 2.0]]
    players = [
        {
            "player_id": f"p{ordinal:02d}",
            "display_name": f"Player {ordinal:02d}",
            "team": "aaa" if ordinal < 5 else "bbb",
            "positions": ["QB" if ordinal == 0 else "FLEX"],
        }
        for ordinal in range(9)
    ]
    structure_body = _self_hash(
        {
            "schema_version": registry.STRUCTURE_SCHEMA,
            "publication_mode": "create_once",
            "task_index": 0,
            "slate_id": "2023-w1-main",
            "games": [{"game_id": "game-aaa-bbb", "home_team": "aaa", "away_team": "bbb"}],
            "teams": [
                {"team": "aaa", "game_id": "game-aaa-bbb", "opponent": "bbb"},
                {"team": "bbb", "game_id": "game-aaa-bbb", "opponent": "aaa"},
            ],
            "players": players,
            "lineups": [
                {
                    "lineup_id": "corpus-lineup-001",
                    "player_ids": [f"p{ordinal:02d}" for ordinal in range(9)],
                    "salary": 50_000,
                    "source": "corpus",
                }
            ],
        },
        "slate_structure_sha256",
    )
    structure_id = storage.publish("slate-structure", structure_body)

    def snapshot(
        *, snapshot_id: str, producing_fill: dict[str, object]
    ) -> dict[str, object]:
        return _self_hash(
            {
                "schema_version": registry.SNAPSHOT_SCHEMA,
                "publication_mode": "create_once",
                "snapshot_id": snapshot_id,
                "task_index": 0,
                "slate_id": "2023-w1-main",
                "season": 2023,
                "week": 1,
                "source_snapshot_manifest": source_manifest,
                "producing_fill_preset": producing_fill,
                "slate_structure": structure_id,
                "artifact_pointers": [pointer],
                "lineup_ids": ["corpus-lineup-001"],
                "created_at_utc": "2026-08-21T12:00:00Z",
            },
            "corpus_snapshot_sha256",
        )

    baseline_snapshot_id = storage.publish(
        "baseline-snapshot",
        snapshot(
            snapshot_id="corpus-snapshot-baseline-task0",
            producing_fill=fill_ids[0],
        ),
    )
    tail_snapshot_id = storage.publish(
        "tail-snapshot",
        snapshot(
            snapshot_id="corpus-snapshot-tail-task0",
            producing_fill=fill_ids[1],
        ),
    )

    baseline_rows = _metric_rows(
        discovery=194.0, heldout=192.5, baseline=None
    )
    baseline_authority = _authority(
        storage=storage,
        experiment_id="baseline-experiment",
        fill=fill_ids[0],
        fill_parameters=fill_bodies[0]["parameters"],
        retrieval=retrieval_ids[0],
        retrieval_parameters=retrieval_bodies[0]["parameters"],
        snapshot=baseline_snapshot_id,
        matrix=matrix,
        metric_rows=baseline_rows,
    )
    baseline_metric_body = _metrics(
        experiment_id="baseline-experiment",
        discovery=194.0,
        heldout=192.5,
        baseline=None,
        comparison_axis="none",
        authority=baseline_authority,
    )
    baseline_metric_id = storage.publish("baseline-metrics", baseline_metric_body)
    baseline_experiment_body = _experiment(
        experiment_id="baseline-experiment",
        fill=fill_ids[0],
        retrieval=retrieval_ids[0],
        snapshot=baseline_snapshot_id,
        matrix=matrix,
        metric_set=baseline_metric_id,
        authority=baseline_authority,
    )
    baseline_experiment_id = storage.publish(
        "baseline-experiment", baseline_experiment_body
    )

    fill_rows = _metric_rows(
        discovery=198.4, heldout=197.1, baseline=baseline_experiment_id
    )
    fill_authority = _authority(
        storage=storage,
        experiment_id="fill-experiment",
        fill=fill_ids[1],
        fill_parameters=fill_bodies[1]["parameters"],
        retrieval=retrieval_ids[0],
        retrieval_parameters=retrieval_bodies[0]["parameters"],
        snapshot=tail_snapshot_id,
        matrix=matrix,
        metric_rows=fill_rows,
    )
    fill_metric_body = _metrics(
        experiment_id="fill-experiment",
        discovery=198.4,
        heldout=197.1,
        baseline=baseline_experiment_id,
        comparison_axis="fill",
        authority=fill_authority,
    )
    fill_metric_id = storage.publish("fill-metrics", fill_metric_body)
    fill_experiment_body = _experiment(
        experiment_id="fill-experiment",
        fill=fill_ids[1],
        retrieval=retrieval_ids[0],
        snapshot=tail_snapshot_id,
        matrix=matrix,
        metric_set=fill_metric_id,
        authority=fill_authority,
    )
    fill_experiment_id = storage.publish("fill-experiment", fill_experiment_body)

    candidate_rows = _metric_rows(
        discovery=203.2, heldout=201.1, baseline=fill_experiment_id
    )
    candidate_fill_index = 0 if snapshot_fill_mismatch else 1
    candidate_authority = _authority(
        storage=storage,
        experiment_id="candidate-experiment",
        fill=fill_ids[candidate_fill_index],
        fill_parameters=(
            fill_bodies[0]["parameters"]
            if effective_parameter_drift
            else fill_bodies[candidate_fill_index]["parameters"]
        ),
        retrieval=retrieval_ids[1],
        retrieval_parameters=retrieval_bodies[1]["parameters"],
        snapshot=tail_snapshot_id,
        matrix=matrix,
        metric_rows=(
            [{**candidate_rows[0], "value": 999.0}, candidate_rows[1]]
            if computed_metric_drift else candidate_rows
        ),
        exact_release=(
            {**EXACT_RELEASE, "code_commit": "9" * 40}
            if authority_release_drift else EXACT_RELEASE
        ),
    )
    if cross_experiment_evidence:
        candidate_authority["accepted_result"] = fill_authority["accepted_result"]
    candidate_metric_body = _metrics(
        experiment_id="candidate-experiment",
        discovery=203.2,
        heldout=201.1,
        baseline=fill_experiment_id,
        comparison_axis="fill" if invalid_pairing_axis else "retrieval",
        authority=(fill_authority if metric_authority_mismatch else candidate_authority),
    )
    candidate_metric_id = storage.publish("candidate-metrics", candidate_metric_body)
    candidate_experiment_body = _experiment(
        experiment_id="candidate-experiment",
        fill=fill_ids[0] if snapshot_fill_mismatch else fill_ids[1],
        retrieval=retrieval_ids[1],
        snapshot=tail_snapshot_id,
        matrix=matrix,
        metric_set=candidate_metric_id,
        authority=candidate_authority,
    )
    candidate_experiment_id = storage.publish(
        "candidate-experiment", candidate_experiment_body
    )

    promotion_body = _self_hash(
        {
            "schema_version": registry.PROMOTION_SCHEMA,
            "publication_mode": "create_once",
            "decision_id": "candidate-review",
            "version": 1,
            "candidate_experiment": candidate_experiment_id,
            "incumbent_active_pointer": None,
            "metric_set": candidate_metric_id,
            "registered_gates": [
                {
                    "metric_id": "heldout-score",
                    "scope": "heldout",
                    "operator": ">=",
                    "threshold": 200.0,
                    "minimum_sample_count": 10_000,
                }
            ],
            "decision": "promote",
            "review": {
                "reviewer_id": "research-reviewer",
                "reviewed_at_utc": "2026-08-21T12:30:00Z",
                "independent_review": True,
            },
            "automatic_promotion": automatic_promotion,
            "human_review_required": True,
            "application_config_mutation": False,
            "production_policy_authority": False,
        },
        "promotion_decision_sha256",
    )
    promotion_id = storage.publish("promotion", promotion_body)
    active_body = _self_hash(
        {
            "schema_version": registry.ACTIVE_POINTER_SCHEMA,
            "publication_mode": "create_once",
            "pointer_id": "research-active-strategy",
            "version": 1,
            "previous_pointer": None,
            "promotion_decision": promotion_id,
            "fill_preset": fill_ids[1],
            "retrieval_preset": retrieval_ids[1],
            "source_experiment": candidate_experiment_id,
            "effective_scope": "research-retrieval",
            "status": "active",
            "automatic_activation": False,
            "application_config_mutation": False,
            "external_activation_required": True,
            "production_policy_authority": False,
        },
        "active_strategy_pointer_sha256",
    )
    active_id = storage.publish("active-pointer", active_body)

    authority_id: dict[str, object] | None = None
    winner_evidence_id: dict[str, object] | None = None
    if include_winners:
        authority_body = _self_hash(
            {
                "schema_version": registry.WINNER_AUTHORITY_SCHEMA,
                "publication_mode": "create_once",
                "authority_id": "licensed-51-winner-import",
                "expected_winner_count": 51,
                "source_manifest": source_manifest,
                "licenses": {
                    "historical_outcome_read_authority": True,
                    "winner_evidence_graph_import": True,
                    "graph_research_only": True,
                    "automatic_promotion": False,
                    "production_policy_authority": False,
                },
                "created_at_utc": "2026-08-21T12:40:00Z",
            },
            "winner_import_authority_sha256",
        )
        authority_id = storage.publish("winner-authority", authority_body)
        winner_body = _self_hash(
            {
                "schema_version": registry.WINNER_EVIDENCE_SCHEMA,
                "publication_mode": "create_once",
                "authority": authority_id,
                "source_manifest": source_manifest,
                "winners": [
                    {
                        "winner_id": f"winner-{ordinal:02d}",
                        "slate_id": "2023-w1-main",
                        "lineup_id": f"winner-lineup-{ordinal:02d}",
                        "player_ids": [f"p{player:02d}" for player in range(9)],
                        "winning_score": 201.0 + ordinal,
                        "contest_id": f"contest-{ordinal:02d}",
                    }
                    for ordinal in range(51)
                ],
            },
            "winner_evidence_sha256",
        )
        winner_evidence_id = storage.publish("winner-evidence", winner_body)

    requested = include_winners or request_winners_without_authority
    release_body = _self_hash(
        {
            "schema_version": registry.RELEASE_SCHEMA,
            "publication_mode": "create_once",
            "registry_id": "20260821-strategy-registry-v1",
            "output_prefix": "gs://registry-fixture/output/",
            "fill_presets": _sort_identities(fill_ids),
            "retrieval_presets": _sort_identities(retrieval_ids),
            "corpus_snapshots": _sort_identities(
                [baseline_snapshot_id, tail_snapshot_id]
            ),
            "slate_structures": [structure_id],
            "experiment_runs": _sort_identities(
                [
                    baseline_experiment_id,
                    fill_experiment_id,
                    candidate_experiment_id,
                ]
            ),
            "metric_sets": _sort_identities(
                [baseline_metric_id, fill_metric_id, candidate_metric_id]
            ),
            "promotion_decisions": [] if omit_promotion else [promotion_id],
            "active_strategy_pointers": [] if omit_promotion else [active_id],
            "winner_import_requested": requested,
            "winner_import_authority": authority_id,
            "winner_evidence": winner_evidence_id,
            "automatic_promotion": False,
            "application_config_mutation": False,
            "production_policy_authority": False,
            "gcs_remains_authoritative": True,
            "world_matrices_stored_in_graph": False,
            "raw_outcomes_stored_in_graph": False,
            "uses_realized_outcomes": realized_outcome_read,
            "historical_outcome_read_authority": False,
            "outcome_namespace_read": False,
            "outcome_columns_read": [],
            "created_at_utc": "2026-08-21T13:00:00Z",
        },
        "registry_release_sha256",
    )
    release_id = storage.publish("registry-release", release_body)
    return storage, release_id, matrix


def _prepare(
    storage: FakeStorage, release_id: dict[str, object]
) -> registry.StrategyRegistryBundle:
    return registry.prepare_strategy_registry_plan(
        parent_plan=PARENT_FIXTURES._plan(PARENT_FIXTURES._bundle()),
        storage=storage,
        release_identity=release_id,
    )


def test_registry_projects_versioned_outcome_blind_strategy_evidence() -> None:
    storage, release_id, matrix = _build_fixture()
    bundle = _prepare(storage, release_id)
    registry_nodes = [
        row for row in bundle.plan.nodes
        if row["workstream_namespace"] == registry.REGISTRY_NAMESPACE
    ]
    registry_edges = [
        row for row in bundle.plan.relationships
        if str(row["from_id"]).startswith("corpus-strategy-registry:")
        or str(row["to_id"]).startswith("corpus-strategy-registry:")
    ]
    kinds = {str(row["kind"]) for row in registry_nodes}
    assert {
        "StrategyRegistryRelease", "FillPreset", "RetrievalPreset",
        "CorpusSnapshot", "CorpusArtifactPointer", "Slate", "Game",
        "TeamSlate", "PlayerSlate", "Player", "Lineup", "ExperimentRun",
        "ExperimentMetricSet", "Metric", "PromotionDecision",
        "ActiveStrategyPointer", "ExperimentPreExecutionGate",
        "ExperimentEffectiveParameters", "ExperimentAcceptedExecution",
        "ExperimentAcceptedResult", "ExperimentIndependentVerification",
        "ExperimentSelectionEvidence", "ExperimentMetricComputation",
    }.issubset(kinds)
    assert sum(row["kind"] == "WinningLineup" for row in registry_nodes) == 0
    assert sum(row["kind"] == "CorpusSnapshot" for row in registry_nodes) == 2
    assert sum(
        row["relationship_type"] == "PRODUCED_BY_FILL_PRESET"
        for row in registry_edges
    ) == 2
    assert sum(
        row["relationship_type"] == "CONTAINS_LINEUP"
        for row in registry_edges
    ) == 2
    assert not any(
        row["relationship_type"] == "ROSTERS_PLAYER_SLATE"
        and '"historical_winner":true' in str(row["properties_json"])
        for row in registry_edges
    )
    pairing_edges = [
        row for row in registry_edges
        if row["relationship_type"] == "PAIRED_AGAINST_EXPERIMENT"
    ]
    assert len(pairing_edges) == 4
    assert {
        json.loads(str(row["properties_json"]))["comparison_axis"]
        for row in pairing_edges
    } == {"fill", "retrieval"}
    assert any(row["relationship_type"] == "EVALUATES_METRIC" for row in registry_edges)
    assert not {
        "AUTHORIZES_PRODUCTION", "DEPLOYS", "MUTATES_POLICY", "AUTO_PROMOTES"
    }.intersection(str(row["relationship_type"]) for row in registry_edges)
    for row in registry_nodes:
        if row["kind"] in {
            "FillPreset", "RetrievalPreset", "ExperimentRun",
            "PromotionDecision", "ActiveStrategyPointer",
        }:
            payload = json.loads(str(row["properties_json"]))
            assert payload["production_policy_authority"] is False
        if str(row["kind"]).startswith("Experiment"):
            payload = json.loads(str(row["properties_json"]))
            assert payload["uses_realized_outcomes"] is False
            assert payload["outcome_namespace_read"] is False
            assert payload["outcome_columns_read"] == []

    pointer_node = next(row for row in registry_nodes if row["kind"] == "CorpusArtifactPointer")
    assert pointer_node["source_uri"] == matrix["uri"]
    assert "matrix_values" not in str(pointer_node["properties_json"])
    assert (str(matrix["uri"]), str(matrix["generation"])) not in storage.reads
    assert len(storage.reads) == len(set(storage.reads))

    receipt = registry.build_projection_receipt(
        bundle,
        governed_load_manifest=_placeholder_identity("governed-manifest", 90),
        governed_registry_load_receipt=_placeholder_identity(
            "governed-registry-load", 91
        ),
    )
    assert receipt["winner_imported"] is False
    assert receipt["winner_count"] == 0
    assert receipt["manifest_namespace_v2_authorized"] is True
    assert receipt["gcs_remains_authoritative"] is True
    assert receipt["world_matrices_stored_in_graph"] is False
    assert receipt["automatic_promotion"] is False
    published = registry.publish_registry_receipt(
        bundle=bundle,
        storage=storage,
        uri="gs://registry-fixture/output/projection-receipt.json",
        receipt=receipt,
    )
    assert published.sha256 == sha256(
        projection.canonical_json_bytes(receipt)
    ).hexdigest()


def test_registry_read_only_query_receipt_is_bounded_and_non_mutating() -> None:
    storage, release_id, _ = _build_fixture(include_winners=False)
    bundle = _prepare(storage, release_id)
    calls: list[tuple[str, str, dict[str, object]]] = []

    def run_query(
        database: str, cypher: str, parameters: dict[str, object]
    ) -> list[dict[str, object]]:
        calls.append((database, cypher, dict(parameters)))
        return [{"ordinal": len(calls), "row": "fixture"}]

    receipt = registry.run_read_only_traversal_receipt(
        bundle=bundle,
        database="corpusresearch",
        query_runner=run_query,
        governed_load_manifest=_placeholder_identity("governed-manifest", 92),
        governed_registry_load_receipt=_placeholder_identity(
            "governed-registry-load", 93
        ),
        registry_projection_receipt=_placeholder_identity(
            "governed-registry-projection", 94
        ),
    )
    assert len(calls) == len(registry.READ_ONLY_QUERIES)
    assert all(call[2] == {
        "namespace": registry.REGISTRY_NAMESPACE,
        "registry_id": "20260821-strategy-registry-v1",
    } for call in calls)
    assert receipt["read_only"] is True
    assert receipt["graph_mutation"] is False
    assert receipt["automatic_promotion"] is False
    assert receipt["winner_imported"] is False
    assert receipt["winner_count"] == 0
    assert [result["name"] for result in receipt["results"]] == [
        "preset-registry",
        "strategy-lineage",
        "paired-heldout-fill-retrieval-comparison",
        "active-pointer-promotion-traversal",
        "lineup-player-team-game-traversal",
        "registry-firewall-census",
        "named-scenario-comparison",
    ]
    assert all(result["row_count"] == 1 for result in receipt["results"])
    assert all("rows" not in result for result in receipt["results"])
    uri = "gs://registry-fixture/output/query-receipt.json"
    first = registry.publish_registry_receipt(
        bundle=bundle, storage=storage, uri=uri, receipt=receipt
    )
    second = registry.publish_registry_receipt(
        bundle=bundle, storage=storage, uri=uri, receipt=receipt
    )
    assert first == second
    assert first.uri == uri
    with pytest.raises(
        registry.CorpusStrategyRegistryError,
        match="outside the exact output prefix",
    ):
        registry.publish_registry_receipt(
            bundle=bundle,
            storage=storage,
            uri="gs://other-bucket/query-receipt.json",
            receipt=receipt,
        )


def test_registry_allows_review_to_remain_pending_without_active_pointer() -> None:
    storage, release_id, _ = _build_fixture(
        include_winners=False, omit_promotion=True
    )
    bundle = _prepare(storage, release_id)
    kinds = {
        str(row["kind"]) for row in bundle.plan.nodes
        if row["workstream_namespace"] == registry.REGISTRY_NAMESPACE
    }
    assert "ExperimentRun" in kinds
    assert "PromotionDecision" not in kinds
    assert "ActiveStrategyPointer" not in kinds


@pytest.mark.parametrize(
    "options,match",
    [
        ({"invalid_typed_parameter": True}, "typed value differs"),
        ({"automatic_promotion": True}, "no-auto-promotion law differs"),
        ({"embed_matrix_values": True}, "artifact pointer.*fields differ"),
        (
            {"invalid_pairing_axis": True},
            "fill comparison is not isolated",
        ),
        (
            {"snapshot_fill_mismatch": True},
            "experiment snapshot/matrix binding differs",
        ),
        (
            {"include_winners": False, "request_winners_without_authority": True},
            "outcome-blind registry v2 firewall",
        ),
        (
            {"effective_parameter_drift": True},
            "executed parameters differ from the registered presets",
        ),
        (
            {"computed_metric_drift": True},
            "metric values differ from the bound computation evidence",
        ),
        (
            {"cross_experiment_evidence": True},
            "authority identities alias across roles or experiments",
        ),
        (
            {"metric_authority_mismatch": True},
            "metric set experiment authority binding differs",
        ),
        (
            {"realized_outcome_read": True},
            "outcome firewall differs",
        ),
        (
            {"authority_release_drift": True},
            "pre-execution gate experiment binding differs",
        ),
    ],
)
def test_registry_fails_closed_on_authority_and_schema_violations(
    options: dict[str, bool], match: str
) -> None:
    storage, release_id, _ = _build_fixture(**options)
    with pytest.raises(registry.CorpusStrategyRegistryError, match=match):
        _prepare(storage, release_id)


def _paired_axis_evidence(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "experiment_id": "exp-baseline",
        "definition": {"uri": "gs://x/def.json", "generation": "1",
                       "sha256": "a" * 64, "bytes": 10},
        "paired_design": {"required": False},
        "task_index": 0,
        "slate_id": "2023-w01",
        "shared_world_artifacts": [{"uri": "gs://x/w0.npz", "generation": "1",
                                    "sha256": "b" * 64, "bytes": 5}],
        "metrics": [{
            "metric_id": "m0", "name": "worlds-gt-200", "unit": "worlds",
            "direction": "descriptive", "scope": "all-worlds-descriptive",
            "sample_count": 50_000, "paired_key": "r0-r4-world-id",
            "source_scope": "all_r0_r4_descriptive",
            "source_metric": "strict-200-worlds",
        }],
        "fill_preset": {"uri": "gs://x/fill-a.json", "generation": "1",
                        "sha256": "c" * 64, "bytes": 7},
        "retrieval_preset": {"uri": "gs://x/ret-a.json", "generation": "1",
                             "sha256": "d" * 64, "bytes": 7},
        "source_terminal": {"uri": "gs://x/term-a.json", "generation": "1",
                            "sha256": "e" * 64, "bytes": 7},
        "source_task_result": {"uri": "gs://x/res-a.json", "generation": "1",
                               "sha256": "f" * 64, "bytes": 7},
        "source_suite_manifest": {"uri": "gs://x/suite-a.json",
                                  "generation": "1", "sha256": "1" * 64,
                                  "bytes": 7},
        "source_snapshot_manifest": {"uri": "gs://x/snap-a.json",
                                     "generation": "1", "sha256": "2" * 64,
                                     "bytes": 7},
        "source_execution": {"execution_id": "exec-a"},
    }
    body.update(overrides)
    return body


def test_fill_axis_pairing_is_now_satisfiable() -> None:
    baseline = _paired_axis_evidence()
    challenger = _paired_axis_evidence(
        experiment_id="exp-fill-challenger",
        paired_design={"required": True},
        fill_preset={"uri": "gs://x/fill-b.json", "generation": "1",
                     "sha256": "3" * 64, "bytes": 7},
        source_snapshot_manifest={"uri": "gs://x/snap-b.json",
                                  "generation": "1", "sha256": "4" * 64,
                                  "bytes": 7},
        source_terminal={"uri": "gs://x/term-b.json", "generation": "1",
                         "sha256": "5" * 64, "bytes": 7},
        source_task_result={"uri": "gs://x/res-b.json", "generation": "1",
                            "sha256": "6" * 64, "bytes": 7},
        source_suite_manifest={"uri": "gs://x/suite-b.json", "generation": "1",
                               "sha256": "7" * 64, "bytes": 7},
        source_execution={"execution_id": "exec-b"},
    )
    # Different fill-produced snapshot, same worlds, same retrieval preset:
    # this is the roadmap's fill-only cell and must validate.
    registry._validate_paired_scenario_axis(
        baseline=baseline,
        evidence=challenger,
        comparison_axis="fill",
        expected_baseline_id="exp-baseline",
    )
    same_snapshot = dict(challenger)
    same_snapshot["source_snapshot_manifest"] = dict(
        baseline["source_snapshot_manifest"]
    )
    with pytest.raises(
        registry.CorpusStrategyRegistryError, match="fill comparison"
    ):
        registry._validate_paired_scenario_axis(
            baseline=baseline,
            evidence=same_snapshot,
            comparison_axis="fill",
            expected_baseline_id="exp-baseline",
        )


def test_retrieval_axis_pairing_still_requires_one_source_run() -> None:
    baseline = _paired_axis_evidence()
    challenger = _paired_axis_evidence(
        experiment_id="exp-retrieval-challenger",
        paired_design={"required": True},
        retrieval_preset={"uri": "gs://x/ret-b.json", "generation": "1",
                          "sha256": "8" * 64, "bytes": 7},
    )
    registry._validate_paired_scenario_axis(
        baseline=baseline,
        evidence=challenger,
        comparison_axis="retrieval",
        expected_baseline_id="exp-baseline",
    )
    foreign_result = dict(challenger)
    foreign_result["source_task_result"] = {
        "uri": "gs://x/res-other.json", "generation": "1",
        "sha256": "9" * 64, "bytes": 7,
    }
    with pytest.raises(
        registry.CorpusStrategyRegistryError, match="retrieval comparison"
    ):
        registry._validate_paired_scenario_axis(
            baseline=baseline,
            evidence=foreign_result,
            comparison_axis="retrieval",
            expected_baseline_id="exp-baseline",
        )
    with pytest.raises(
        registry.CorpusStrategyRegistryError, match="source/world law"
    ):
        registry._validate_paired_scenario_axis(
            baseline=baseline,
            evidence=_paired_axis_evidence(
                paired_design={"required": True},
                shared_world_artifacts=[{
                    "uri": "gs://x/other-worlds.npz", "generation": "1",
                    "sha256": "0" * 64, "bytes": 5,
                }],
            ),
            comparison_axis="retrieval",
            expected_baseline_id="exp-baseline",
        )
