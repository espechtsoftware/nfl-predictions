"""Focused offline tests for the one-read corpus realized transport."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from typing import Mapping

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_realized_grading as grading
from nfl_dfs.research import corpus_realized_outcome_transport as transport
from nfl_dfs.research import lr8_label_fit_adapter as lease_adapter
from nfl_dfs.research import lr8_label_score_map as shared


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
import run_corpus_realized_outcomes as runner  # noqa: E402


RUN_ID = "corpus-realized-test-v1"
JOB = "corpus-realized-test"
CODE_SHA = "a" * 40
IMAGE = "us-central1-docker.pkg.dev/p/r/i@sha256:" + "b" * 64


def _helper(path: str, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load helper {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(value: object, *, uri: str, generation: int) -> dict[str, object]:
    return batch.object_identity_for_json(
        value, uri=uri, generation=str(generation)
    )


def _transport_task(task: Mapping[str, object]) -> dict[str, object]:
    prefix = str(task["variant_output_prefix"])
    boundary = f"{prefix}transport/"
    result: dict[str, object] = {
        "task_index": task["task_index"],
        "task_sha256": task["task_sha256"],
        "variant_output_prefix": prefix,
        "result_receipt_uri": task["result_receipt_uri"],
        "science_terminal_uri": f"{prefix}task-terminal.json",
        "producer_close_uri": f"{boundary}producer-close.json",
        "independent_verification_uri": (
            f"{boundary}independent-verification.json"
        ),
        "accepted_terminal_uri": f"{boundary}accepted-terminal.json",
    }
    for phase in ("producer", "verifier"):
        result[f"{phase}_launch_intent_uri"] = (
            f"{boundary}{phase}-launch-intent.json"
        )
        result[f"{phase}_launch_ledger_uri"] = (
            f"{boundary}{phase}-launch-ledger.json"
        )
        result[f"{phase}_execution_name_uri"] = (
            f"{boundary}{phase}-execution-name.json"
        )
        result[f"{phase}_worker_completion_uri"] = (
            f"{boundary}{phase}-worker-completion.json"
        )
    return result


def _store_key(value: Mapping[str, object]) -> tuple[object, ...]:
    return tuple(value[key] for key in ("uri", "generation", "sha256", "bytes"))


def _lease() -> dict[str, object]:
    body = {
        "version": lease_adapter.HISTORICAL_OUTCOME_LEASE_VERSION,
        "run_id": RUN_ID,
        "job": JOB,
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "acquired_at": "2026-08-21T19:59:00+00:00",
    }
    raw = shared.canonical_json(body)
    return {
        "body": body,
        "object_receipt": {
            "uri": lease_adapter.HISTORICAL_OUTCOME_LEASE_URI,
            "generation": "900001",
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
            "create_only": True,
        },
    }


@pytest.fixture(scope="module")
def accepted_graph() -> dict[str, object]:
    grading_helper = _helper(
        "tests/test_corpus_realized_grading.py", "_realized_grading_fixture"
    )
    source_helper = _helper(
        "tests/test_lr8_later_period_source.py", "_later_source_fixture"
    )
    source = source_helper._build_source()
    source_identity = _identity(
        source,
        uri="gs://fixture-authority/later-source-freeze.json",
        generation=610_000,
    )
    base_common_law = grading_helper._common_law

    def common_law() -> dict[str, object]:
        law = base_common_law()
        sources = {"later_source_freeze": source_identity}
        law["source_receipts"] = sources
        law["source_receipt_set_sha256"] = batch.canonical_sha256(sources)
        law["later_source_freeze_manifest_sha256"] = source["freeze_sha256"]
        return law

    def manifest() -> dict[str, object]:
        output = (
            "gs://fixture-batch/corpus-parametric-research/batches/"
            "grade-fixture-v1/"
        )
        tasks: list[dict[str, object]] = []
        for task_index, source_slate in enumerate(source["slates"]):
            world_receipts = {
                role: grading_helper._receipt(
                    f"worlds/task-{task_index:04d}/{role}",
                    1_000 + task_index * 10 + ordinal,
                )
                for ordinal, role in enumerate(batch.TASK_WORLD_SOURCE_ROLES)
            }
            tasks.append({
                "task_index": task_index,
                "slate_id": source_slate["slate_id"],
                "season": source_slate["season"],
                "week": source_slate["week"],
                "result_receipt_uri": (
                    f"{output}tasks/{task_index:04d}/result.json"
                ),
                "variant_output_prefix": (
                    f"{output}variants/task-{task_index:04d}/"
                ),
                "world_artifact_receipts": world_receipts,
                "world_artifact_receipt_set_sha256": batch.canonical_sha256(
                    world_receipts
                ),
                "artifact_source_authority_task_sha256": (
                    grading_helper._digest(f"source-task-{task_index}")
                ),
            })
        return batch.build_batch_manifest(
            batch_id="grade-fixture-v1",
            created_at_utc="2026-08-21T18:00:00Z",
            output_prefix=output,
            common_law=common_law(),
            tasks=tasks,
        )

    originals = (
        grading_helper._common_law,
        grading_helper._manifest,
        grading_helper._rosters,
    )
    grading_helper._common_law = common_law
    grading_helper._manifest = manifest
    grading_helper._rosters = lambda: [
        list(roster) for roster in source_helper._legal_rosters(81)
    ]
    try:
        evidence = grading_helper._accepted_fixture()
    finally:
        (
            grading_helper._common_law,
            grading_helper._manifest,
            grading_helper._rosters,
        ) = originals

    manifest_value = evidence["batch_manifest"]
    manifest_identity = evidence["batch_manifest_identity"]
    placeholder = evidence["batch_acceptance"][
        "retrieval_task0_prerequisite_identity"
    ]
    contract_body: dict[str, object] = {
        "schema_version": transport.TRANSPORT_CONTRACT_SCHEMA,
        "created_at_utc": "2026-08-21T18:10:00+00:00",
        "project": transport.PROJECT,
        "region": "us-central1",
        "batch_id": manifest_value["batch_id"],
        "output_prefix": manifest_value["output_prefix"],
        "batch_manifest_identity": manifest_identity,
        "batch_manifest_sha256": manifest_value["batch_manifest_sha256"],
        "evidence_contract_identity": grading_helper._receipt("evidence", 601),
        "retrieval_task0_prerequisite_identity": placeholder,
        "foundation_publication_identity": grading_helper._receipt(
            "foundation", 602
        ),
        "runtime_iam_evidence_identity": grading_helper._receipt("iam", 603),
        "prefix_claim_identity": grading_helper._receipt("prefix", 604),
        "build": {
            "build_id": "11111111-1111-1111-1111-111111111111",
            "code_repository": "fixture/repository",
            "code_sha": CODE_SHA,
            "image": IMAGE,
        },
        "service_account": "fixture@example.iam.gserviceaccount.com",
        "job": {
            "name": "fixture-job", "uid": "fixture-job-uid",
            "generation": "1", "observed_generation": "1",
            "spec_sha256": "c" * 64,
        },
        "manifest_input_identity_set_sha256": "d" * 64,
        "task_count": 54,
        "batch_mode": "complete-54-task",
        "matrix_cell_count": 378,
        "complete_batch_acceptance_required": True,
        "tasks": [_transport_task(task) for task in manifest_value["tasks"]],
        "cloud_run_task_count": 1,
        "cloud_run_parallelism": 1,
        "max_retries": 0,
        "task_attempt": 0,
        "default_command": ["python"],
        "default_args": [
            "scripts/run_corpus_parametric_transport.py", "parked"
        ],
        "literal_execute_flag_required": True,
        "environment_execute_gate_required": True,
        "producer_and_verifier_separate_executions": True,
        "automatic_retry_licensed": False,
        "create_once": True,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "corpus_fill_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
    }
    contract = {
        **contract_body,
        "transport_contract_sha256": batch.canonical_sha256(contract_body),
    }
    contract_identity = _identity(
        contract,
        uri=(
            f"{manifest_value['output_prefix']}governance/"
            "parametric-transport-contract.json"
        ),
        generation=620_000,
    )

    task_acceptance_ids: list[dict[str, object]] = []
    for task_row in evidence["accepted_tasks"]:
        value = dict(task_row["task_acceptance"])
        value["transport_contract"] = contract_identity
        body = {key: item for key, item in value.items() if key != (
            "task_acceptance_sha256"
        )}
        value["task_acceptance_sha256"] = batch.canonical_sha256(body)
        old_identity = task_row["task_acceptance_identity"]
        identity = _identity(
            value,
            uri=old_identity["uri"],
            generation=int(old_identity["generation"]),
        )
        task_row["task_acceptance"] = value
        task_row["task_acceptance_identity"] = identity
        task_acceptance_ids.append(identity)

    acceptance = dict(evidence["batch_acceptance"])
    acceptance["transport_contract"] = contract_identity
    acceptance["task_acceptances"] = task_acceptance_ids
    inventory_ids = [
        manifest_identity,
        evidence["batch_completion_identity"],
        *task_acceptance_ids,
    ]
    inventory = sorted(({
        "uri": row["uri"],
        "generation": row["generation"],
        "bytes": row["bytes"],
    } for row in inventory_ids), key=lambda row: (
        row["uri"], row["generation"]
    ))
    acceptance["output_inventory_before_batch_acceptance"] = inventory
    acceptance["output_inventory_before_batch_acceptance_sha256"] = (
        batch.canonical_sha256(inventory)
    )
    acceptance["output_object_count_before_batch_acceptance"] = len(inventory)
    acceptance_body = {
        key: item for key, item in acceptance.items()
        if key != "batch_acceptance_sha256"
    }
    acceptance["batch_acceptance_sha256"] = batch.canonical_sha256(
        acceptance_body
    )
    acceptance_identity = _identity(
        acceptance,
        uri=(
            f"{manifest_value['output_prefix']}governance/"
            "batch-acceptance.json"
        ),
        generation=630_000,
    )
    evidence["batch_acceptance"] = acceptance
    evidence["batch_acceptance_identity"] = acceptance_identity

    store: dict[tuple[object, ...], bytes] = {}

    def retain(value: object, identity: Mapping[str, object]) -> None:
        store[_store_key(identity)] = batch.canonical_json_bytes(value)

    retain(acceptance, acceptance_identity)
    retain(contract, contract_identity)
    retain(manifest_value, manifest_identity)
    retain(evidence["batch_completion"], evidence["batch_completion_identity"])
    retain(source, source_identity)
    for task_row in evidence["accepted_tasks"]:
        retain(task_row["task_acceptance"], task_row["task_acceptance_identity"])
        retain(task_row["task_result"], task_row["task_result_identity"])
        for variant in task_row["variant_results"]:
            retain(variant["result"], variant["object_identity"])
    return {
        "evidence": evidence,
        "source": source,
        "store": store,
    }


class Harness:
    def __init__(self, fixture: Mapping[str, object]):
        self.fixture = fixture
        self.events: list[str] = []
        self.query_count = 0
        self.lease_count = 0
        self.publish_count = 0
        self.spec: transport.QuerySpec | None = None
        self.lease_value = _lease()
        self.query_mutator = lambda rows: rows
        self.lease_mutator = lambda value, _count: value
        self.times = iter((
            datetime(2026, 8, 21, 20, 0, 0, tzinfo=timezone.utc),
            datetime(
                2026, 8, 21, 20, 0, 0, 500_000, tzinfo=timezone.utc
            ),
        ))
        self.created = (
            "2026-08-21T20:00:01+00:00",
            "2026-08-21T20:00:04+00:00",
            "2026-08-21T20:00:05+00:00",
            "2026-08-21T20:00:06+00:00",
        )

    def read(self, identity: Mapping[str, object]) -> bytes:
        self.events.append("read")
        return self.fixture["store"][_store_key(identity)]

    def lease(self) -> Mapping[str, object]:
        self.lease_count += 1
        self.events.append(f"lease-{self.lease_count}")
        return self.lease_mutator(deepcopy(self.lease_value), self.lease_count)

    @staticmethod
    def metadata(table: str) -> dict[str, object]:
        return {
            "table_id": table,
            "etag": f"etag-{table}",
            "modified": "2026-08-20T00:00:00+00:00",
            "num_rows": 1_000_000,
            "schema_sha256": "e" * 64,
        }

    def query(self, spec: transport.QuerySpec) -> shared.QueryResult:
        self.events.append("query")
        self.query_count += 1
        self.spec = spec
        assert self.publish_count == 1
        params = {value.name: value.value for value in spec.parameters}
        rows: list[dict[str, object]] = []
        for source_kind, parameter_name, score in (
            ("dst", "dst_keys", Decimal("-1.25")),
            ("skill", "skill_keys", Decimal("10.000001")),
        ):
            for encoded in params[parameter_name]:
                season, week, source_key = encoded.split("|", 2)
                rows.append({
                    "season": int(season),
                    "week": int(week),
                    "source_kind": source_kind,
                    "source_key": source_key,
                    "realized_score": score,
                })
        rows.sort(key=lambda row: (
            row["season"], row["week"], row["source_kind"], row["source_key"]
        ))
        return shared.QueryResult(
            rows=self.query_mutator(rows),
            job_receipt={
                "job_id": spec.job_id,
                "location": spec.location,
                "sql_sha256": spec.sql_sha256,
                "parameters_sha256": spec.parameters_sha256,
                "created": "2026-08-21T20:00:02+00:00",
                "started": "2026-08-21T20:00:02+00:00",
                "ended": "2026-08-21T20:00:03+00:00",
                "total_bytes_processed": 100,
                "cache_hit": False,
                "error_result": None,
            },
        )

    def publish(self, uri: str, raw: bytes) -> transport.PublishedObject:
        self.events.append(f"publish-{self.publish_count + 1}")
        created = self.created[self.publish_count]
        self.publish_count += 1
        return transport.PublishedObject(
            receipt={
                "uri": uri,
                "generation": str(700_000 + self.publish_count),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
                "create_only": True,
            },
            reopened_raw=raw,
            created_at=created,
            created=True,
        )

    def clock(self) -> datetime:
        return next(self.times)


def _config(fixture: Mapping[str, object], *, enabled: bool = True) -> (
    transport.SupplierConfig
):
    identity = fixture["evidence"]["batch_acceptance_identity"]
    return transport.SupplierConfig(
        run_id=RUN_ID,
        job=JOB,
        code_sha=CODE_SHA,
        image=IMAGE,
        expected_batch_acceptance_object_sha256=identity["sha256"],
        enabled=enabled,
    )


def _supply(
    fixture: Mapping[str, object], harness: Harness,
) -> transport.RealizedOutcomeSupply:
    return transport.supply_realized_outcomes(
        config=_config(fixture),
        batch_acceptance_identity=fixture["evidence"][
            "batch_acceptance_identity"
        ],
        read_exact=harness.read,
        verify_lease=harness.lease,
        read_table_metadata=harness.metadata,
        execute_query=harness.query,
        publish=harness.publish,
        clock=harness.clock,
    )


def test_complete_batch_is_reopened_before_one_read_and_replayed(
    accepted_graph: Mapping[str, object],
) -> None:
    harness = Harness(accepted_graph)
    result = _supply(accepted_graph, harness)

    assert harness.query_count == 1
    assert harness.lease_count == 2
    assert harness.publish_count == 4
    assert harness.events.index("publish-1") < harness.events.index("query")
    assert result.attempt["task_count"] == 54
    assert result.attempt["task_arm_count"] == 378
    assert len(result.attempt["union_keys"]) == 54 * 19
    assert result.attempt["query_spec"]["schema_version"] == (
        transport.QUERY_CONTRACT_SCHEMA
    )
    assert result.attempt["query_spec"]["query_count"] == 1
    assert result.attempt["query_spec"]["use_query_cache"] is False
    assert result.source["row_count"] == result.attempt["union_player_dst_count"]
    assert result.source["row_count"] == 54 * 19
    assert result.outcome_bundle["row_count"] == 54 * 19
    assert len(result.completion["realized_grade"]["task_arm_metrics"]) == 378
    assert result.completion["rank_available"] is False
    assert result.completion["roi_available"] is False
    assert result.completion["independent_replay_complete"] is True
    assert all(receipt["create_only"] is True for receipt in (
        result.attempt_receipt,
        result.source_receipt,
        result.outcome_bundle_receipt,
        result.completion_receipt,
    ))
    stdout = runner._receipt_only(result)
    assert "realized_grade" not in stdout
    assert stdout["historical_outcome_lease_release_required"] is True


def test_default_off_refuses_every_callback(
    accepted_graph: Mapping[str, object],
) -> None:
    called = False

    def forbidden(*_args: object, **_kwargs: object) -> object:
        nonlocal called
        called = True
        raise AssertionError("callback reached")

    with pytest.raises(
        transport.CorpusRealizedOutcomeError, match="default-off"
    ):
        transport.supply_realized_outcomes(
            config=_config(accepted_graph, enabled=False),
            batch_acceptance_identity=accepted_graph["evidence"][
                "batch_acceptance_identity"
            ],
            read_exact=forbidden,
            verify_lease=forbidden,
            read_table_metadata=forbidden,
            execute_query=forbidden,
            publish=forbidden,
        )
    assert called is False


@pytest.mark.parametrize("mutation", ("missing", "extra", "float"))
def test_query_must_return_exact_micro_union_after_attempt(
    accepted_graph: Mapping[str, object], mutation: str,
) -> None:
    harness = Harness(accepted_graph)

    def mutate(rows: list[dict[str, object]]) -> list[dict[str, object]]:
        changed = deepcopy(rows)
        if mutation == "missing":
            changed.pop()
        elif mutation == "extra":
            changed.append({**changed[-1], "source_key": "not-in-union"})
        else:
            changed[0]["realized_score"] = 1.25
        return changed

    harness.query_mutator = mutate
    with pytest.raises(transport.CorpusRealizedOutcomeError):
        _supply(accepted_graph, harness)
    assert harness.query_count == 1
    assert harness.publish_count == 1
    assert harness.events.index("publish-1") < harness.events.index("query")


def test_lease_drift_fails_before_source_publication(
    accepted_graph: Mapping[str, object],
) -> None:
    harness = Harness(accepted_graph)

    def drift(value: dict[str, object], count: int) -> dict[str, object]:
        if count == 2:
            value["object_receipt"]["generation"] = "900002"
        return value

    harness.lease_mutator = drift
    with pytest.raises(transport.CorpusRealizedOutcomeError):
        _supply(accepted_graph, harness)
    assert harness.query_count == 1
    assert harness.publish_count == 1


def test_missing_accepted_variant_fails_before_lease_or_query(
    accepted_graph: Mapping[str, object],
) -> None:
    broken = dict(accepted_graph)
    broken["store"] = dict(accepted_graph["store"])
    identity = accepted_graph["evidence"]["accepted_tasks"][0][
        "variant_results"
    ][0]["object_identity"]
    del broken["store"][_store_key(identity)]
    harness = Harness(broken)
    with pytest.raises(transport.CorpusRealizedOutcomeError):
        _supply(broken, harness)
    assert harness.lease_count == 0
    assert harness.query_count == 0
    assert harness.publish_count == 0


def test_cli_literal_and_environment_gates_precede_file_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = tmp_path / "does-not-exist.json"
    args = argparse.Namespace(
        execute=False,
        project=transport.PROJECT,
        run_id=RUN_ID,
        job=JOB,
        code_sha=CODE_SHA,
        image=IMAGE,
        batch_acceptance_uri="gs://fixture/batch-acceptance.json",
        batch_acceptance_generation="1",
        batch_acceptance_sha256="a" * 64,
        batch_acceptance_bytes="100",
        historical_lease_receipt=missing,
    )
    monkeypatch.setenv(runner.ENABLED_ENV, "1")
    with pytest.raises(
        runner.CorpusRealizedOutcomeRunnerError, match="--execute"
    ):
        runner._validated_cli(args)
    args.execute = True
    monkeypatch.delenv(runner.ENABLED_ENV)
    with pytest.raises(
        runner.CorpusRealizedOutcomeRunnerError, match="--execute"
    ):
        runner._validated_cli(args)


def test_cli_validates_pin_and_shared_lease_without_clients(
    accepted_graph: Mapping[str, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lease = _lease()
    receipt_path = tmp_path / "lease.json"
    receipt_path.write_bytes(batch.canonical_json_bytes({
        "lease": lease["body"],
        "object": lease["object_receipt"],
    }))
    identity = accepted_graph["evidence"]["batch_acceptance_identity"]
    args = argparse.Namespace(
        execute=True,
        project=transport.PROJECT,
        run_id=RUN_ID,
        job=JOB,
        code_sha=CODE_SHA,
        image=IMAGE,
        batch_acceptance_uri=identity["uri"],
        batch_acceptance_generation=identity["generation"],
        batch_acceptance_sha256=identity["sha256"],
        batch_acceptance_bytes=str(identity["bytes"]),
        historical_lease_receipt=receipt_path,
    )
    monkeypatch.setenv(runner.ENABLED_ENV, "1")
    config, pin, validated_lease = runner._validated_cli(args)

    assert config.enabled is True
    assert pin.identity() == identity
    assert validated_lease == lease


def test_frozen_query_has_only_player_dst_actuals() -> None:
    sql = transport.AUTHORITATIVE_SCORE_SQL.lower()
    assert sql.count("select ") == 4
    assert "player_week_actuals" in sql
    assert "team_defense_week" in sql
    assert "for system_time as of @source_snapshot_at" in sql
    assert "contest" not in sql
    assert "standings" not in sql
    assert "payout" not in sql
    assert "winner" not in sql
