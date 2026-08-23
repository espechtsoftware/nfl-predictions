from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_corpus_parametric_batch_v1.py"
NOW = "2026-08-21T18:00:00Z"
SOLVER = {
    "name": "cbc",
    "version": "2.10.3",
    "binary_sha256": "2" * 64,
    "options_sha256": "3" * 64,
    "exact_mode": True,
}


@pytest.fixture()
def module() -> ModuleType:
    name = "prepare_corpus_parametric_batch_v1_under_test"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    imported = importlib.util.module_from_spec(spec)
    sys.modules[name] = imported
    spec.loader.exec_module(imported)
    return imported


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _identity(uri: str, raw: bytes, generation: str) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class _FakeStorage:
    """Exact-name storage with no LIST/inventory capability."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.current: dict[str, str] = {}
        self.events: list[tuple[str, str]] = []
        self.next_generation = 900_000

    def seed(self, uri: str, raw: bytes, generation: str) -> dict[str, object]:
        if uri in self.current:
            raise FileExistsError(uri)
        self.objects[(uri, generation)] = raw
        self.current[uri] = generation
        return _identity(uri, raw, generation)

    def read(self, identity: Mapping[str, object]) -> bytes:
        uri = str(identity["uri"])
        generation = str(identity["generation"])
        self.events.append(("read", uri))
        raw = self.objects[(uri, generation)]
        if (
            len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            raise ValueError("generation-pinned body differs")
        return raw

    def resolve_optional(
        self, uri: str,
    ) -> tuple[dict[str, object], bytes] | None:
        self.events.append(("resolve", uri))
        generation = self.current.get(uri)
        if generation is None:
            return None
        raw = self.objects[(uri, generation)]
        return _identity(uri, raw, generation), raw

    def publish(
        self, uri: str, raw: bytes, media_type: str = "application/json",
    ) -> dict[str, object]:
        del media_type
        self.events.append(("publish", uri))
        generation = str(self.next_generation)
        self.next_generation += 1
        return self.seed(uri, raw, generation)

    def __getattr__(self, name: str) -> object:
        if "list" in name.lower() or "inventory" in name.lower():
            raise AssertionError("LIST is forbidden")
        raise AttributeError(name)


def _code_source(module: ModuleType) -> dict[str, object]:
    digest = "sha256:" + "1" * 64
    image = {
        "uri": f"us-docker.pkg.dev/example/research/image@{digest}",
        "digest": digest,
    }
    commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", "HEAD"], cwd=ROOT, text=True,
    ).strip()
    return {
        "schema": "corpus-legal-feasibility-code-source/v1",
        "source_commit_sha": commit,
        "cloud_build_id": "12345678-1234-1234-1234-123456789abc",
        "implementation_sha256": {
            path: sha256((ROOT / path).read_bytes()).hexdigest()
            for path in module.legal._CODE_SOURCE_IMPLEMENTATION_PATHS
        },
        "build_definition_sha256": {
            path: sha256((ROOT / path).read_bytes()).hexdigest()
            for path in module.legal._CODE_SOURCE_BUILD_PATHS
        },
        "immutable_image": image,
        "terminal_verification": dict(
            module.legal._CODE_SOURCE_TERMINAL_VERIFICATION
        ),
    }


def _input_identity(uri: str, marker: str) -> dict[str, object]:
    return {
        "uri": uri, "generation": marker, "sha256": marker[-1] * 64,
        "bytes": 1,
    }


def _preplan(module: ModuleType, *, mode: str) -> dict[str, object]:
    marker = "production" if mode == "production" else "smoke"
    foundation_id = f"corpus-parametric-{marker}-foundation-v1"
    batch_id = f"corpus-parametric-{marker}-batch-v1"
    return module.build_preplan(
        mode=mode,
        workstream=module.WORKSTREAM,
        foundation_id=foundation_id,
        batch_id=batch_id,
        created_at_utc=NOW,
        accepted_at_utc=NOW,
        foundation_prefix=(
            "gs://foundation/corpus-parametric-research/"
            f"foundations/{foundation_id}/"
        ),
        batch_output_prefix=(
            "gs://batch/corpus-parametric-research/"
            f"batches/{batch_id}/"
        ),
        retrieval_terminal_identity=_input_identity(
            "gs://retrieval/task0/terminal.json", "11",
        ),
        source_publication_completion_identity=_input_identity(
            "gs://source/governance/publication.json", "22",
        ),
        source_task_indexes=(list(range(54)) if mode == "production" else [0]),
        code_source=_code_source(module),
        solver=dict(SOLVER),
        world_seed=20_260_821,
        publish_task_requests=False,
        default_off=True,
        outcome_columns_read=[],
        uses_realized_outcomes=False,
        historical_scoring_licensed=False,
        corpus_fill_licensed=False,
        live_strategy_authority=False,
        production_change_licensed=False,
    )


def _validate_plan(module: ModuleType, plan: object) -> dict[str, object]:
    return module.validate_preplan(
        plan, repository_root=ROOT, solver_probe_fn=lambda: dict(SOLVER),
    )


def _rehash(module: ModuleType, value: Mapping[str, object]) -> dict[str, object]:
    body = {key: value[key] for key in value if key != "preplan_sha256"}
    return {**body, "preplan_sha256": module.canonical_sha256(body)}


def test_preplan_enforces_54_production_one_smoke_and_separate_namespaces(
    module: ModuleType,
) -> None:
    smoke = _validate_plan(module, _preplan(module, mode="smoke"))
    production = _validate_plan(module, _preplan(module, mode="production"))
    assert smoke["source_task_indexes"] == [0]
    assert production["source_task_indexes"] == list(range(54))
    assert smoke["foundation_prefix"] != production["foundation_prefix"]
    assert smoke["batch_output_prefix"] != production["batch_output_prefix"]
    assert "corpus-population-research" not in _canonical([smoke, production]).decode()

    # The v7 two-lane split admits exactly the two enumerated half-batch
    # lattices — and nothing else.
    lane_a = _validate_plan(module, _rehash(
        module, {**production, "source_task_indexes": list(range(0, 28))}
    ))
    lane_b = _validate_plan(module, _rehash(
        module, {**production, "source_task_indexes": list(range(28, 54))}
    ))
    assert lane_a["source_task_indexes"] == list(range(0, 28))
    assert lane_b["source_task_indexes"] == list(range(28, 54))
    for bad in (
        list(range(53)), list(range(1, 28)), list(range(27, 54)),
        list(range(0, 27)), list(range(28, 53)), [0, 2],
    ):
        wrong = _rehash(module, {**production, "source_task_indexes": bad})
        with pytest.raises(Exception, match="task lattice"):
            _validate_plan(module, wrong)
    wrong_smoke = _rehash(module, {**smoke, "source_task_indexes": [0, 1]})
    with pytest.raises(Exception, match="task lattice"):
        _validate_plan(module, wrong_smoke)


def test_preplan_fails_closed_on_solver_code_and_namespace_drift(
    module: ModuleType,
) -> None:
    plan = _preplan(module, mode="smoke")
    with pytest.raises(Exception, match="CBC authority"):
        module.validate_preplan(
            plan, repository_root=ROOT,
            solver_probe_fn=lambda: {**SOLVER, "binary_sha256": "4" * 64},
        )
    bad_code = deepcopy(plan)
    bad_code["code_source"]["implementation_sha256"][
        module.legal._CODE_SOURCE_IMPLEMENTATION_PATHS[0]
    ] = "5" * 64
    with pytest.raises(Exception, match="code/image/build bytes drifted"):
        _validate_plan(module, _rehash(module, bad_code))
    population = _rehash(module, {
        **plan,
        "foundation_prefix": str(plan["foundation_prefix"]).replace(
            "corpus-parametric-research", "corpus-population-research"
        ),
    })
    with pytest.raises(Exception, match="independent parametric research"):
        _validate_plan(module, population)


def _seed_json(
    store: _FakeStorage, uri: str, value: object, generation: int,
) -> dict[str, object]:
    return store.seed(uri, _canonical(value), str(generation))


def _retrieval_graph(
    module: ModuleType, store: _FakeStorage,
) -> tuple[dict[str, object], SimpleNamespace, list[dict[str, object]]]:
    transitive = [
        _seed_json(store, f"gs://retrieval/sidecars/{index}.json", {"x": index}, 50 + index)
        for index in range(3)
    ]
    snapshot = {"tasks": [{"task_index": 0}]}
    snapshot_raw = _canonical(snapshot)
    snapshot_id = store.seed("gs://retrieval/snapshot.json", snapshot_raw, "10")
    suite = {
        "snapshot_manifest_identity": snapshot_id,
        "tasks": [{"task_index": 0, "task_id": "task-0000"}],
    }
    suite_id = store.seed("gs://retrieval/suite.json", _canonical(suite), "11")
    result = {
        "task_index": 0,
        "task_result_sha256": "a" * 64,
        "coverage": {
            "world_count": 50_000,
            "unique_lineup_count": 12,
            "lineup_world_score_count": 600_000,
            "every_unique_lineup_scored_in_every_world": True,
            "strategy_count": 4,
            "all_strategies_exact_budget": True,
        },
        "licenses": {
            "analytics_authority": True,
            "corpus_fill_authority": False,
            "historical_outcome_read_authority": False,
            "live_money_policy_authority": False,
            "production_default_change_authority": False,
        },
        "execution": {
            "execution_id": "exec-1", "execution_name": "projects/p/e/exec-1",
            "attempt": 0, "retry_count": 0, "mode": "cloud-run-task",
        },
        "transitive": transitive,
    }
    result_id = store.seed("gs://retrieval/result.json", _canonical(result), "12")
    completion = {
        "batch_completion_sha256": "b" * 64,
        "coverage": {"task_count": 1, "all_tasks_complete": True},
        "task_results": [{"task_result_object": result_id}],
        "licenses": {
            "analytical_graph_projection_ready": True,
            "corpus_fill_authority": False,
            "historical_outcome_read_authority": False,
            "live_money_policy_authority": False,
            "production_default_change_authority": False,
        },
    }
    completion_id = store.seed(
        "gs://retrieval/completion.json", _canonical(completion), "13"
    )
    governance = {
        field: _seed_json(
            store, f"gs://retrieval/governance/{field}.json", {"field": field},
            100 + ordinal,
        )
        for ordinal, field in enumerate(module._TERMINAL_GOVERNANCE_FIELDS)
    }
    inventory = sorted([
        {"uri": identity["uri"], "generation": identity["generation"],
         "bytes": identity["bytes"]}
        for identity in (suite_id, result_id, completion_id)
    ], key=lambda row: (row["uri"], row["generation"]))
    terminal_body = {
        "schema_version": "corpus-retrieval-transport-terminal/v1",
        "finished_at_utc": NOW,
        **governance,
        "execution": {
            "execution_id": "exec-1", "execution_name": "projects/p/e/exec-1",
            "execution_uid": "uid", "job_uid": "job-uid", "job_generation": "7",
            "task_count": 1, "attempt": 0, "retry_count": 0, "state": "True",
            "counters": {"succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0},
        },
        "suite_manifest_identity": suite_id,
        "snapshot_manifest_identity": snapshot_id,
        "task_index": 0,
        "task_id": "task-0000",
        "result_object": result_id,
        "task_result_sha256": result["task_result_sha256"],
        "batch_completion": completion_id,
        "batch_completion_sha256": completion["batch_completion_sha256"],
        "post_terminal_job": {
            "uid": "job-uid", "generation": "7", "observed_generation": "7",
        },
        "output_inventory_before_terminal": inventory,
        "output_inventory_before_terminal_sha256": sha256(_canonical(inventory)).hexdigest(),
        "one_execution": True,
        "attempt_zero": True,
        "retry_count": 0,
        "generation_pinned_replay": True,
        "successful_deployment_remains_parked": True,
        "uses_realized_outcomes": False,
        "bigquery_access_licensed": False,
        "corpus_fill_licensed": False,
        "live_policy_access_licensed": False,
        "production_change_licensed": False,
    }
    terminal = {
        **terminal_body,
        "terminal_receipt_sha256": sha256(_canonical(terminal_body)).hexdigest(),
    }
    terminal_id = store.seed(
        "gs://retrieval/terminal.json", _canonical(terminal), "14"
    )
    replay_flags: list[bool] = []

    def validate_result(**kwargs: object) -> Mapping[str, object]:
        replay_flags.append(bool(kwargs["replay"]))
        authority = kwargs["published_result"]["authority"]
        for identity in authority["transitive"]:
            kwargs["read_object"](identity)
        return authority

    fake = SimpleNamespace(
        parse_canonical_json_bytes=lambda raw, **_kwargs: json.loads(raw),
        canonical_json_bytes=_canonical,
        canonical_sha256=lambda value: sha256(_canonical(value)).hexdigest(),
        validate_suite_manifest=lambda value: value,
        validate_snapshot_manifest=lambda value: value,
        validate_retrieval_task_result=validate_result,
        validate_retrieval_batch_completion=lambda value, **_kwargs: value,
    )
    fake.replay_flags = replay_flags
    return terminal_id, fake, transitive


def test_retrieval_bridge_replays_transitive_graph_and_matches_transport_schema(
    module: ModuleType,
) -> None:
    store = _FakeStorage()
    terminal, fake, transitive = _retrieval_graph(module, store)
    prerequisite, raw = module.bridge_retrieval_task0(
        storage=store, terminal_identity=terminal, accepted_at_utc=NOW,
        retrieval_module=fake,
    )
    assert fake.replay_flags == [True]
    read_uris = [uri for action, uri in store.events if action == "read"]
    assert all(identity["uri"] in read_uris for identity in transitive)
    assert raw.endswith(b"\n")
    assert prerequisite["completion_receipt"]["uri"].endswith("completion.json")
    assert prerequisite["partial_result"] is False
    assert prerequisite["partial_object_count"] == 0

    transport_spec = importlib.util.spec_from_file_location(
        "parametric_transport_schema_under_test",
        ROOT / "scripts" / "run_corpus_parametric_transport.py",
    )
    assert transport_spec is not None and transport_spec.loader is not None
    transport = importlib.util.module_from_spec(transport_spec)
    sys.modules[transport_spec.name] = transport
    transport_spec.loader.exec_module(transport)
    assert transport.validate_retrieval_task0_prerequisite(prerequisite) == prerequisite


def test_retrieval_bridge_rejects_transitive_generation_tamper(
    module: ModuleType,
) -> None:
    store = _FakeStorage()
    terminal, fake, transitive = _retrieval_graph(module, store)
    target = transitive[-1]
    key = (str(target["uri"]), str(target["generation"]))
    store.objects[key] += b"tamper"
    with pytest.raises(Exception, match="generation-pinned body differs"):
        module.bridge_retrieval_task0(
            storage=store, terminal_identity=terminal, accepted_at_utc=NOW,
            retrieval_module=fake,
        )


def _source_graph(
    module: ModuleType, store: _FakeStorage,
) -> tuple[dict[str, object], SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    tasks: list[dict[str, object]] = []
    slates: list[dict[str, object]] = []
    for task_index in range(54):
        season = 2023 + task_index // 18
        week = task_index % 18 + 1
        receipts: dict[str, dict[str, object]] = {}
        source_receipts: list[dict[str, object]] = []
        for role_index, (role, block) in enumerate(zip(
            module.batch.TASK_WORLD_SOURCE_ROLES, module.rw.WORLD_BLOCKS, strict=True,
        )):
            raw = f"npz-{task_index:02d}-{block}".encode()
            identity = store.seed(
                f"gs://source/worlds/{task_index:02d}/{block}.npz", raw,
                str(10_000 + task_index * 5 + role_index),
            )
            receipts[role] = identity
            source_receipts.append({**identity, "block": block})
        receipt_hash = module.batch.canonical_sha256(receipts)
        tasks.append({
            "task_index": task_index, "season": season, "week": week,
            "slate_id": f"{season}-w{week:02d}",
            "world_artifact_receipts": receipts,
            "world_artifact_receipt_set_sha256": receipt_hash,
            "task_source_authority_sha256": f"{task_index + 1:064x}",
        })
        slates.append({
            "season": season, "week": week,
            "slate_id": f"{season}-w{week:02d}",
            "artifact_receipts": source_receipts,
        })
    registration = {
        "registered_at": NOW,
        "source_queries": {
            "r0_candidates": {"query": "r0"},
            "artifact_catalog": {"query": "catalog"},
        },
        "salary_universe_query": {"query": "salary"},
    }
    freeze = {"freeze_sha256": "a" * 64, "slates": slates}
    completion = {
        "task_count": 54, "artifact_count": 270,
        "completion_sha256": "b" * 64,
        "later_source_freeze_manifest_sha256": freeze["freeze_sha256"],
        "tasks": tasks,
    }
    direct_values = {
        "prefix_claim": {"claim": True},
        "registration_object": registration,
        "later_source_freeze_object": freeze,
        "salary_diagnostic_object": {"salary": True},
        "source_authority_completion_object": completion,
    }
    direct = {
        field: _seed_json(
            store, f"gs://source/governance/{field}.json", value, 20_000 + index,
        )
        for index, (field, value) in enumerate(direct_values.items())
    }
    completion["later_source_freeze_object"] = direct["later_source_freeze_object"]
    completion_raw = _canonical(completion)
    completion_key = (
        direct["source_authority_completion_object"]["uri"],
        direct["source_authority_completion_object"]["generation"],
    )
    store.objects[completion_key] = completion_raw
    direct["source_authority_completion_object"] = _identity(
        str(completion_key[0]), completion_raw, str(completion_key[1])
    )
    captures: dict[str, dict[str, object]] = {}
    for index, role in enumerate(module.QUERY_ROLES):
        value = {
            "role": role, "row_count": 54, "rows_sha256": f"{index + 4:064x}",
            "capture_sha256": f"{index + 7:064x}",
        }
        identity = _seed_json(
            store, f"gs://source/captures/{role}.json", value, 21_000 + index,
        )
        captures[role] = {"object": identity, **value}
    publication = {
        "task_count": 54, "artifact_count": 270,
        "artifact_list_used": False, "uses_realized_outcomes": False,
        **direct,
        "query_captures": captures,
        "later_source_freeze_manifest_sha256": freeze["freeze_sha256"],
        "source_authority_completion_sha256": completion["completion_sha256"],
    }
    publication_identity = _seed_json(
        store, "gs://source/governance/publication.json", publication, 22_000,
    )

    transport = SimpleNamespace(
        validate_publication_completion_bytes=lambda raw: json.loads(raw),
        parse_canonical_json_bytes=lambda raw, **_kwargs: json.loads(raw),
        validate_query_capture=lambda value, **_kwargs: value,
    )

    @dataclass(frozen=True)
    class Record:
        task_index: int
        role: str
        identity: Mapping[str, object]
        raw: bytes

    def verify(**kwargs: object) -> bytes:
        records = list(kwargs["artifact_bodies"])
        assert len(records) == 270
        assert [row.task_index for row in records[::5]] == list(range(54))
        return completion_raw

    authority = SimpleNamespace(
        RetainedArtifactBody=Record,
        validate_registration=lambda value: value,
        canonical_json_bytes=_canonical,
        validate_completion_bytes=lambda raw: json.loads(raw),
        verify_artifact_supported_source_authority=verify,
    )
    later_fake = SimpleNamespace(
        validate_source_freeze=lambda value, **_kwargs: value,
        canonical_json=_canonical,
        prepare_later_slate=lambda _freeze, **kwargs: SimpleNamespace(
            task_index=next(
                index for index, row in enumerate(slates)
                if row["season"] == kwargs["season"] and row["week"] == kwargs["week"]
            )
        ),
    )
    return publication_identity, transport, authority, later_fake


def test_source_loader_reopens_all_54_tasks_and_exactly_270_npzs_without_list(
    module: ModuleType,
) -> None:
    store = _FakeStorage()
    publication, transport, authority, later_fake = _source_graph(module, store)

    def ranker(prepared: object, **_kwargs: object) -> Sequence[object]:
        del prepared
        return tuple(
            module.rw.WorldId(block, index)
            for block in module.rw.WORLD_BLOCKS for index in range(200)
        )

    loaded = module.load_source_authority(
        storage=store, publication_identity=publication,
        source_task_indexes=list(range(54)),
        source_transport_module=transport, authority_module=authority,
        later_module=later_fake, ranker=ranker,
    )
    artifact_reads = [
        uri for action, uri in store.events
        if action == "read" and uri.startswith("gs://source/worlds/")
    ]
    assert loaded.exact_artifact_get_count == 270
    assert len(loaded.task_rows) == len(loaded.schedule_rows) == 54
    assert len(artifact_reads) == len(set(artifact_reads)) == 270
    assert "list" not in type(store).__dict__


def test_source_loader_rejects_task_alias_before_science_replay(
    module: ModuleType,
) -> None:
    store = _FakeStorage()
    publication, transport, authority, later_fake = _source_graph(module, store)
    terminal = json.loads(store.read(publication))
    completion_id = terminal["source_authority_completion_object"]
    key = (completion_id["uri"], completion_id["generation"])
    completion = json.loads(store.objects[key])
    completion["tasks"][53]["slate_id"] = completion["tasks"][0]["slate_id"]
    raw = _canonical(completion)
    store.objects[key] = raw
    terminal["source_authority_completion_object"] = _identity(
        completion_id["uri"], raw, completion_id["generation"]
    )
    terminal_key = (publication["uri"], publication["generation"])
    terminal_raw = _canonical(terminal)
    store.objects[terminal_key] = terminal_raw
    publication = _identity(publication["uri"], terminal_raw, publication["generation"])
    with pytest.raises(Exception):
        module.load_source_authority(
            storage=store, publication_identity=publication,
            source_task_indexes=list(range(54)),
            source_transport_module=transport, authority_module=authority,
            later_module=later_fake,
            ranker=lambda *_args, **_kwargs: (),
        )


def _fake_source(
    module: ModuleType, store: _FakeStorage, plan: Mapping[str, object],
    count: int = 1,
) -> object:
    publication_raw = b"p"
    publication_identity = store.seed(
        plan["source_publication_completion_identity"]["uri"],
        publication_raw,
        plan["source_publication_completion_identity"]["generation"],
    )
    # The plan hashes are rebuilt around the real seeded identities by the caller.
    completion_identity = store.seed("gs://source/completion.json", b"c", "31")
    freeze_identity = store.seed("gs://source/freeze.json", b"f", "32")
    blocks = [
        {"block": block, "world_indices": list(range(200))}
        for block in module.rw.WORLD_BLOCKS
    ]
    flattened = [
        {"block": block, "index": index}
        for block in module.rw.WORLD_BLOCKS for index in range(200)
    ]
    tasks: list[dict[str, object]] = []
    schedules: list[dict[str, object]] = []
    for local in range(count):
        receipts = {
            role: _input_identity(
                f"gs://source/t{local:02d}-{role}.npz",
                str(40 + local * 10 + index),
            )
            for index, role in enumerate(module.batch.TASK_WORLD_SOURCE_ROLES)
        }
        receipt_hash = module.batch.canonical_sha256(receipts)
        season = 2023 + local // 18
        week = local % 18 + 1
        slate_id = f"{season}-w{week:02d}"
        tasks.append({
            "task_index": local, "season": season, "week": week,
            "slate_id": slate_id,
            "world_artifact_receipts": receipts,
            "world_artifact_receipt_set_sha256": receipt_hash,
            "task_source_authority_sha256": "d" * 64,
        })
        schedules.append({
            "task_index": local, "season": season, "week": week,
            "slate_id": slate_id,
            "later_source_freeze_manifest_sha256": "a" * 64,
            "world_artifact_receipt_set_sha256": receipt_hash,
            "blocks": blocks,
            "visit_schedule_sha256": module.legal.canonical_sha256(flattened),
        })
    return module.SourceFoundation(
        publication_identity=publication_identity,
        publication={},
        completion_identity=completion_identity,
        completion={"completion_sha256": "b" * 64},
        source_freeze_identity=freeze_identity,
        source_freeze={"freeze_sha256": "a" * 64},
        task_rows=tuple(tasks), schedule_rows=tuple(schedules),
        exact_artifact_get_count=270,
    )


def _fake_prerequisite(module: ModuleType) -> tuple[dict[str, object], bytes]:
    identities = [
        _input_identity(f"gs://retrieval/prerequisite-input-{index}.json", str(60 + index))
        for index in range(5)
    ]
    body = {
        "schema_version": module.RETRIEVAL_PREREQUISITE_SCHEMA,
        "accepted_at_utc": NOW, "task_index": 0,
        "suite_manifest_identity": identities[0],
        "snapshot_manifest_identity": identities[1],
        "task_result_object": identities[2],
        "terminal_receipt": identities[3],
        "completion_receipt": identities[4],
        "accepted": True, "complete_result": True, "partial_result": False,
        "partial_object_count": 0,
        "every_unique_lineup_scored_in_every_world": True,
        "generation_pinned_replay": True, "uses_realized_outcomes": False,
        "corpus_fill_licensed": False,
    }
    value = {
        **body, "acceptance_sha256": module._transport_sha256(body),
    }
    return value, module._transport_json_bytes(value)


def test_create_once_publication_is_idempotent_conflict_safe_and_batch_clean(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _FakeStorage()
    original_plan = _preplan(module, mode="smoke")
    source_raw = b"p"
    source_identity = store.seed(
        original_plan["source_publication_completion_identity"]["uri"],
        source_raw,
        original_plan["source_publication_completion_identity"]["generation"],
    )
    plan = _rehash(module, {
        **original_plan,
        "source_publication_completion_identity": source_identity,
    })
    source = _fake_source(module, _FakeStorage(), plan)
    # Replace source identities with objects in the execution store.
    completion_identity = store.seed("gs://source/completion.json", b"c", "31")
    freeze_identity = store.seed("gs://source/freeze.json", b"f", "32")
    source = module.SourceFoundation(
        publication_identity=source_identity, publication={},
        completion_identity=completion_identity,
        completion=source.completion,
        source_freeze_identity=freeze_identity,
        source_freeze=source.source_freeze,
        task_rows=source.task_rows, schedule_rows=source.schedule_rows,
        exact_artifact_get_count=270,
    )
    prerequisite = _fake_prerequisite(module)
    monkeypatch.setattr(module, "bridge_retrieval_task0", lambda **_kwargs: prerequisite)
    monkeypatch.setattr(module, "load_source_authority", lambda **_kwargs: source)
    kwargs = {
        "preplan": plan,
        "execute": True,
        "environ": {module.ENABLE_ENV: "1"},
        "storage_factory": lambda: store,
        "repository_root": ROOT,
        "solver_probe_fn": lambda: dict(SOLVER),
    }
    first = module.execute_preparer(**kwargs)
    second = module.execute_preparer(**kwargs)
    assert first["status"] == "created"
    assert second["status"] == "already-complete"
    assert first["publication_identity"] == second["publication_identity"]
    batch_objects = sorted(
        uri for uri in store.current if uri.startswith(plan["batch_output_prefix"])
    )
    assert batch_objects == [
        f"{plan['batch_output_prefix']}governance/batch-manifest.json",
        f"{plan['batch_output_prefix']}governance/pre-run-evidence-contract.json",
    ]
    serialized = _canonical(first["publication"]).decode().lower()
    assert not any(word in serialized for word in ("password", "credential", "secret"))
    assert all(
        value is False for key, value in first["publication"].items()
        if key.endswith("authority") and type(value) is bool
    )

    manifest_identity = first["publication"]["full_manifest"]
    manifest_key = (manifest_identity["uri"], manifest_identity["generation"])
    store.objects[manifest_key] += b"tamper"
    with pytest.raises(Exception):
        module.execute_preparer(**kwargs)


def test_partial_namespace_is_terminal_and_invalid_config_writes_nothing(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _preplan(module, mode="smoke")
    called: list[str] = []
    invalid = _rehash(module, {**plan, "source_task_indexes": [0, 1]})
    with pytest.raises(Exception):
        module.execute_preparer(
            preplan=invalid, execute=True,
            environ={module.ENABLE_ENV: "1"},
            storage_factory=lambda: called.append("client"),
            solver_probe_fn=lambda: dict(SOLVER),
        )
    assert called == []

    store = _FakeStorage()
    source_identity = store.seed(
        plan["source_publication_completion_identity"]["uri"], b"p",
        plan["source_publication_completion_identity"]["generation"],
    )
    plan = _rehash(module, {
        **plan, "source_publication_completion_identity": source_identity,
    })
    helper_store = _FakeStorage()
    source = _fake_source(module, helper_store, plan)
    source = module.SourceFoundation(
        publication_identity=source_identity, publication={},
        completion_identity=_input_identity("gs://source/completion.json", "31"),
        completion=source.completion,
        source_freeze_identity=_input_identity("gs://source/freeze.json", "32"),
        source_freeze=source.source_freeze,
        task_rows=source.task_rows, schedule_rows=source.schedule_rows,
        exact_artifact_get_count=270,
    )
    monkeypatch.setattr(module, "bridge_retrieval_task0", lambda **_kwargs: _fake_prerequisite(module))
    monkeypatch.setattr(module, "load_source_authority", lambda **_kwargs: source)
    manifest_uri = f"{plan['batch_output_prefix']}governance/batch-manifest.json"
    store.seed(manifest_uri, b"partial", "77")
    before_publish = sum(event[0] == "publish" for event in store.events)
    with pytest.raises(Exception, match="partial preparer namespace is terminal"):
        module.execute_preparer(
            preplan=plan, execute=True,
            environ={module.ENABLE_ENV: "1"}, storage_factory=lambda: store,
            repository_root=ROOT, solver_probe_fn=lambda: dict(SOLVER),
        )
    after_publish = sum(event[0] == "publish" for event in store.events)
    assert after_publish == before_publish


def test_execute_gate_precedes_clients_and_solver_probe_is_client_free(
    module: ModuleType,
) -> None:
    called: list[str] = []
    with pytest.raises(Exception, match="literal --execute"):
        module.execute_preparer(
            preplan={}, execute=False, environ={module.ENABLE_ENV: "1"},
            storage_factory=lambda: called.append("client"),
        )
    assert called == []
    with pytest.raises(Exception, match=f"{module.ENABLE_ENV}=1"):
        module.execute_preparer(
            preplan={}, execute=True, environ={},
            storage_factory=lambda: called.append("client"),
        )
    assert called == []
    authority = module.solver_probe()
    assert authority == {
        "name": "cbc", "version": "2.10.3",
        "binary_sha256": (
            "2e17077752aa52b06385ad248c9e90bb4f1ce34038c34c94e1012ca6adea5cc7"
        ),
        "options_sha256": (
            "01bae1c5fab58e2e2e2c7142b1ba23d83ce6d2b16909c69f3d9216d314371c58"
        ),
        "exact_mode": True,
    }


def test_lane_execute_publishes_exactly_the_selected_half_batch(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression for the v7 lane failure "preflight task count differs":
    # every execute-path count law must derive from the plan's lattice,
    # not from the production constant.
    store = _FakeStorage()
    original_plan = _preplan(module, mode="production")
    plan = _rehash(module, {
        **original_plan,
        "source_task_indexes": list(range(28, 54)),
    })
    source_raw = b"p"
    source_identity = store.seed(
        plan["source_publication_completion_identity"]["uri"],
        source_raw,
        plan["source_publication_completion_identity"]["generation"],
    )
    plan = _rehash(module, {
        **plan,
        "source_publication_completion_identity": source_identity,
    })
    source = _fake_source(module, _FakeStorage(), plan, count=26)
    completion_identity = store.seed("gs://source/completion.json", b"c", "31")
    freeze_identity = store.seed("gs://source/freeze.json", b"f", "32")
    source = module.SourceFoundation(
        publication_identity=source_identity, publication={},
        completion_identity=completion_identity,
        completion=source.completion,
        source_freeze_identity=freeze_identity,
        source_freeze=source.source_freeze,
        task_rows=source.task_rows, schedule_rows=source.schedule_rows,
        exact_artifact_get_count=270,
    )
    prerequisite = _fake_prerequisite(module)
    monkeypatch.setattr(
        module, "bridge_retrieval_task0", lambda **_kwargs: prerequisite
    )
    monkeypatch.setattr(
        module, "load_source_authority", lambda **_kwargs: source
    )
    result = module.execute_preparer(
        preplan=plan,
        execute=True,
        environ={module.ENABLE_ENV: "1"},
        storage_factory=lambda: store,
        repository_root=ROOT,
        solver_probe_fn=lambda: dict(SOLVER),
    )
    assert result["status"] == "created"
    assert result["publication"]["task_count"] == 26
    assert result["publication"]["source_task_count"] == 54
    manifest_identity = result["publication"]["full_manifest"]
    manifest = module.batch.parse_canonical_json_bytes(
        store.objects[(manifest_identity["uri"], manifest_identity["generation"])],
        label="lane manifest",
    )
    assert len(manifest["tasks"]) == 26
