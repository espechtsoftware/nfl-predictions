"""Focused offline tests for the R6 fixed-job recover-only executable."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from nfl_dfs.research import corpus_r6_full_union_outcome_supply_v1 as supply
from nfl_dfs.research import corpus_realized_outcome_transport as registered
from nfl_dfs.research import lr8_label_score_map as shared


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/recover_corpus_r6_full_union_outcome_supply_v1.py"


def _load_cli():
    spec = importlib.util.spec_from_file_location("recover_r6_supply_v1_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cli = _load_cli()

NOW = datetime(2026, 8, 27, 1, 0, tzinfo=timezone.utc)
RUN_ID = "20260826-foundry-v12-r6-full-union-realized-v2"
JOB = "atlas-minimal-c-s2023-w1-v1"
ORIGINAL_CODE = "1" * 40
PREVIOUS_RECOVERY_CODE = "2" * 40
RECOVERY_CODE = "a" * 40
ORIGINAL_IMAGE = f"fixture/original@sha256:{'3' * 64}"
PREVIOUS_RECOVERY_IMAGE = f"fixture/previous-recovery@sha256:{'4' * 64}"
RECOVERY_IMAGE = f"fixture/recovery@sha256:{'b' * 64}"
SERVICE_ACCOUNT = "fixture@nfl-predictions-503414.iam.gserviceaccount.com"
TOKEN = "5" * 64
SNAPSHOT_CODE = {
    "snapshot_module_sha256": "6" * 64,
    "snapshot_cli_sha256": "7" * 64,
    "snapshot_test_sha256": "8" * 64,
    "snapshot_cli_test_sha256": "9" * 64,
}


class NotFound(Exception):
    pass


class _FakeBlob:
    def __init__(
        self, client: "_FakeGCS", bucket: str, name: str,
        generation: int | None,
    ) -> None:
        self.client = client
        self.bucket = bucket
        self.name = name
        self.generation = generation
        self.time_created: datetime | None = None

    @property
    def key(self) -> tuple[str, str]:
        return self.bucket, self.name

    def reload(self, *, if_generation_match: int | None = None) -> None:
        versions = self.client.objects.get(self.key, {})
        if not versions:
            raise NotFound("absent")
        generation = max(versions) if self.generation is None else int(self.generation)
        if generation not in versions:
            raise NotFound("generation absent")
        if if_generation_match is not None and generation != if_generation_match:
            raise RuntimeError("generation precondition")
        self.generation = generation
        self.time_created = NOW + timedelta(microseconds=generation)

    def download_as_bytes(self, *, if_generation_match: int) -> bytes:
        assert self.generation == if_generation_match
        return self.client.objects[self.key][if_generation_match]

    def upload_from_string(
        self, raw: bytes, *, content_type: str, if_generation_match: int,
    ) -> None:
        assert content_type == "application/json"
        assert if_generation_match == 0
        self.client.upload_preconditions.append(if_generation_match)
        if self.client.objects.get(self.key):
            raise RuntimeError("create-only collision")
        generation = self.client.next_generation
        self.client.next_generation += 1
        self.client.objects[self.key] = {generation: raw}
        self.generation = generation
        if self.client.ambiguous_upload:
            self.client.ambiguous_upload = False
            raise RuntimeError("lost create response")


class _FakeBucket:
    def __init__(self, client: "_FakeGCS", name: str) -> None:
        self.client = client
        self.name = name

    def blob(self, name: str, generation: int | None = None) -> _FakeBlob:
        return _FakeBlob(self.client, self.name, name, generation)


class _FakeGCS:
    """Exact-name fake with no list or delete capability."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[int, bytes]] = {}
        self.next_generation = 100
        self.upload_preconditions: list[int] = []
        self.ambiguous_upload = False

    def bucket(self, name: str) -> _FakeBucket:
        return _FakeBucket(self, name)

    def seed(self, uri: str, raw: bytes, generation: int) -> dict[str, object]:
        bucket, name = uri.removeprefix("gs://").split("/", 1)
        self.objects.setdefault((bucket, name), {})[generation] = raw
        return _identity(uri, generation, raw)


def _identity(uri: str, generation: int, raw: bytes) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _canonical(value: object) -> bytes:
    return supply.canonical_json_bytes(value)


def _spec() -> registered.QuerySpec:
    sql = "SELECT @source_snapshot_at AS observed_at, season FROM fixture"
    parameters = (
        shared.QueryParameter(
            "source_snapshot_at", "TIMESTAMP", "2026-08-27T00:00:00+00:00"
        ),
        shared.QueryParameter("target_seasons", "INT64", [2023], True),
    )
    return registered.QuerySpec(
        sql=sql,
        parameters=parameters,
        job_id=(
            "r6_full_union_realized_20260826_foundry_v12_r6_full_union_"
            "realized_v2_deadbeef"
        ),
        location="US",
        sql_sha256=sha256(sql.encode()).hexdigest(),
        parameters_sha256=registered.canonical_sha256(
            registered._parameter_payload(parameters)
        ),
        union_keys_sha256="a" * 64,
    )


class _FakeJob:
    def __init__(self, spec: registered.QuerySpec) -> None:
        self.job_id = spec.job_id
        self.location = spec.location
        self.query = spec.sql
        self.query_parameters = cli._parameter_objects(spec)
        self.use_legacy_sql = False
        self.use_query_cache = False
        self.state = "DONE"
        self.error_result = None
        self.cache_hit = False
        self.total_bytes_processed = 8_689_314
        self.created = NOW
        self.started = NOW + timedelta(seconds=1)
        self.ended = NOW + timedelta(seconds=2)
        self.result_calls: list[object] = []
        self.rows = ({
            "season": 2023, "week": 1, "source_kind": "player",
            "source_key": "fixture", "realized_score": "20.0",
        },)

    def result(self, *, retry: object, job_retry: object):
        self.result_calls.append((retry, job_retry))
        return self.rows


class _GetOnlyBQ:
    """Deliberately exposes no submission method."""

    def __init__(self, job: _FakeJob) -> None:
        self.job = job
        self.get_calls: list[tuple[str, str]] = []

    def get_job(self, job_id: str, *, location: str) -> _FakeJob:
        self.get_calls.append((job_id, location))
        assert (job_id, location) == (self.job.job_id, self.job.location)
        return self.job

    def get_table(self, _table_id: str):  # pragma: no cover - real pure path owns use
        raise AssertionError("fixture pure supplier must replace table reads")


def _job_metadata(job: _FakeJob, spec: registered.QuerySpec) -> dict[str, object]:
    return {
        "job_id": job.job_id,
        "location": job.location,
        "state": "DONE",
        "error_result": None,
        "cache_hit": False,
        "total_bytes_processed": job.total_bytes_processed,
        "created": job.created.isoformat(),
        "started": job.started.isoformat(),
        "ended": job.ended.isoformat(),
        "sql_sha256": spec.sql_sha256,
        "parameters_sha256": spec.parameters_sha256,
        "use_legacy_sql": False,
        "use_query_cache": False,
    }


def _runtime_env(execution: str = f"{JOB}-recover") -> dict[str, str]:
    return {
        cli.RECOVERY_ENABLED_ENV: "1",
        cli.RECOVERY_STAGE_TOKEN_ENV: TOKEN,
        cli.RECOVERY_CODE_ENV: RECOVERY_CODE,
        cli.RECOVERY_IMAGE_ENV: RECOVERY_IMAGE,
        "CLOUD_RUN_JOB": JOB,
        "CLOUD_RUN_EXECUTION": execution,
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_COUNT": "1",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
    }


def _failure() -> dict[str, object]:
    return {
        "launch_intent_measurement": {"sha256": "b" * 64, "bytes": 100},
        "launch_stage_token": "c" * 64,
        "launch_argv_sha256": "d" * 64,
        "execution_name": f"{JOB}-cc8xf",
        "execution_uid": "fixture-original-uid",
        "terminal_execution_measurement": {"sha256": "e" * 64, "bytes": 5103},
        "terminal_projection": {
            "completed_status": "False", "failed_count": 1,
            "succeeded_count": 0, "running_count": 0,
            "max_retries": 0, "exit_code": 1,
        },
    }


def _build_intent(
    *, identities: dict[str, dict[str, object]], job: _FakeJob,
    spec: registered.QuerySpec,
) -> dict[str, object]:
    return cli._self_hashed({
        "schema_version": cli.INTENT_SCHEMA,
        "created_at": NOW.isoformat(),
        "project": cli.PROJECT,
        "region": cli.REGION,
        "run_id": RUN_ID,
        "cloud_run_job": JOB,
        "recovery_ordinal": cli.RECOVERY_ORDINAL,
        "operation": cli.OPERATION,
        "original_runtime": {
            "code_sha": ORIGINAL_CODE, "image": ORIGINAL_IMAGE,
            "service_account": SERVICE_ACCOUNT,
        },
        "previous_recovery_runtime": {
            "code_sha": PREVIOUS_RECOVERY_CODE,
            "image": PREVIOUS_RECOVERY_IMAGE,
            "service_account": SERVICE_ACCOUNT,
        },
        "recovery_runtime": {
            "code_sha": RECOVERY_CODE, "image": RECOVERY_IMAGE,
            "service_account": SERVICE_ACCOUNT,
        },
        "original_supply_failure": _failure(),
        "previous_recovery_failure_closure_identity": identities[
            "failure_closure"
        ],
        "recovery_amendment_identity": identities["amendment"],
        "panel_freeze_identity": identities["panel"],
        "outcome_key_projection_identity": identities["projection"],
        "actual_root_smoke_receipt_identity": identities["smoke"],
        "query_compile_receipt_identity": identities["compile"],
        "snapshot_code_identities": SNAPSHOT_CODE,
        "historical_outcome_lease_identity": identities["lease"],
        "read_attempt_identity": identities["attempt"],
        "read_attempt_claims": {
            "attempt_sha256": "f" * 64,
            "query_contract_sha256": "0" * 64,
            "query_job_id": spec.job_id,
            "query_location": spec.location,
            "sql_sha256": spec.sql_sha256,
            "parameters_sha256": spec.parameters_sha256,
            "table_receipt_set_sha256": "1" * 64,
            "source_snapshot_at": "2026-08-27T00:00:00+00:00",
        },
        "fixed_query_job": _job_metadata(job, spec),
        "recovery_runner_sha256": sha256(SCRIPT.read_bytes()).hexdigest(),
        "supply_module_sha256": cli._source_measurement(supply, label="supply"),
        "output_uris": cli._output_uris(RUN_ID),
        "safety": {
            "existing_job_lookup_only": True,
            "expected_get_job_calls": 1,
            "expected_result_calls": 1,
            "result_job_retry_disabled": True,
            "distinct_query_job_count": 1,
            "total_query_submission_count": 1,
            "cumulative_fixed_job_result_retrieval_count": 2,
            "failed_result_validation_count": 1,
            "expected_successful_validation_count": 1,
            "expected_distinct_outcome_snapshot_count": 1,
            "query_submission_licensed": False,
            "new_job_creation_licensed": False,
            "read_attempt_creation_licensed": False,
            "automatic_retry_licensed": False,
            "additional_recovery_licensed": False,
            "historical_retune_licensed": False,
            "graph_mutation_licensed": False,
            "production_change_licensed": False,
            "decision_authority": False,
        },
    }, field="recovery_intent_sha256")


def _failure_closure_body(
    *, previous_intent: dict[str, object], previous_ownership: dict[str, object],
) -> dict[str, object]:
    return cli._self_hashed({
        "schema_version": cli.FAILURE_CLOSURE_SCHEMA,
        "closed_at": NOW.isoformat(),
        "project": cli.PROJECT,
        "region": cli.REGION,
        "run_id": RUN_ID,
        "cloud_run_job": JOB,
        "recovery_ordinal": 1,
        "recovery_runtime": {
            "code_sha": PREVIOUS_RECOVERY_CODE,
            "image": PREVIOUS_RECOVERY_IMAGE,
            "service_account": SERVICE_ACCOUNT,
        },
        "recovery_intent_identity": previous_intent,
        "prelaunch_ownership_identity": previous_ownership,
        **_failure(),
        "terminal_error_class": (
            "authoritative-query-not-exact-ordered-player-dst-union"
        ),
        "worker_completion_absent": True,
        "recovery_receipt_absent": True,
        "standard_supply_outputs_absent": True,
        "fixed_job_result_retrieval_count": 1,
        "failed_result_validation_count": 1,
        "automatic_retry_licensed": False,
        "additional_recovery_licensed": False,
        "query_submission_licensed": False,
        "decision_authority": False,
    }, field="terminal_failure_sha256")


def _amendment_body() -> dict[str, object]:
    return cli._self_hashed({
        "schema_version": cli.AMENDMENT_SCHEMA,
        "created_at": NOW.isoformat(),
        "run_id": RUN_ID,
        "recovery_ordinal": cli.RECOVERY_ORDINAL,
        "skill_zero_completion_law": supply.SKILL_ZERO_COMPLETION_LAW,
        "skill_zero_law_source_sha256": supply.SKILL_ZERO_LAW_SOURCE_SHA256,
        "salary_catalog_settlement_bridge": (
            supply.SALARY_CATALOG_SETTLEMENT_BRIDGE
        ),
        "salary_catalog_bridge_source_sha256": (
            supply.SALARY_CATALOG_BRIDGE_SOURCE_SHA256
        ),
        "missing_skill_score_micro": 0,
        "missing_dst_is_fatal": True,
        "requires_observed_skill_per_slate": True,
        "keeps_snapshot_normalizer_strict": True,
        "fixed_query_job_only": True,
        "query_submission_licensed": False,
        "new_job_creation_licensed": False,
        "automatic_retry_licensed": False,
        "additional_recovery_licensed": False,
        "decision_authority": False,
    }, field="recovery_amendment_sha256")


def _seed_recovery_fixture() -> tuple[
    _FakeGCS, dict[str, object], dict[str, dict[str, object]], _FakeJob, _GetOnlyBQ,
]:
    gcs = _FakeGCS()
    supply_root, _, _ = cli._output_roots(RUN_ID)
    raw_values = {
        "panel": _canonical({"fixture": "panel"}),
        "projection": _canonical({"fixture": "projection"}),
        "smoke": _canonical({"fixture": "smoke"}),
        "compile": _canonical({"fixture": "compile"}),
        "lease": _canonical({"fixture": "lease"}) + b"\n",
        "attempt": _canonical({"fixture": "attempt"}),
    }
    uris = {
        "panel": "gs://nfl-predictions-503414-corpus-retrieval/research/fixture/panel-freeze.json",
        "projection": f"{supply_root}/outcome-key-projection.json",
        "smoke": f"{supply_root}/actual-root-smoke-receipt.json",
        "compile": f"{supply_root}/query-compile-receipt.json",
        "lease": shared.adapter.HISTORICAL_OUTCOME_LEASE_URI,
        "attempt": f"{supply_root}/read-attempt.json",
    }
    identities = {
        label: gcs.seed(uri, raw_values[label], generation=10 + ordinal)
        for ordinal, (label, uri) in enumerate(uris.items())
    }
    previous_root = cli._previous_recovery_root(RUN_ID)
    previous_intent_raw = _canonical({"fixture": "previous-intent"})
    previous_ownership_raw = _canonical({"fixture": "previous-ownership"})
    identities["previous_intent"] = gcs.seed(
        f"{previous_root}/recovery-intent.json", previous_intent_raw, 21
    )
    identities["previous_ownership"] = gcs.seed(
        f"{previous_root}/recovery-prelaunch-resumption-ownership-v1.json",
        previous_ownership_raw,
        22,
    )
    closure_raw = _canonical(_failure_closure_body(
        previous_intent=identities["previous_intent"],
        previous_ownership=identities["previous_ownership"],
    ))
    identities["failure_closure"] = gcs.seed(
        cli._failure_closure_uri(RUN_ID), closure_raw, 23
    )
    amendment_raw = _canonical(_amendment_body())
    identities["amendment"] = gcs.seed(
        cli._amendment_uri(RUN_ID), amendment_raw, 24
    )
    spec = _spec()
    job = _FakeJob(spec)
    bq = _GetOnlyBQ(job)
    intent = cli.validate_recovery_intent_v1(
        _build_intent(identities=identities, job=job, spec=spec)
    )
    intent_raw = _canonical(intent)
    intent_identity = gcs.seed(cli._intent_uri(RUN_ID), intent_raw, generation=30)
    return gcs, intent_identity, identities, job, bq


def _published_identity(value: registered.PublishedObject) -> dict[str, object]:
    return {key: value.receipt[key] for key in ("uri", "generation", "sha256", "bytes")}


def _fake_pure_supplier(
    *, expected_spec: registered.QuerySpec,
):
    def run(**kwargs):
        config = kwargs["config"]
        assert config.code_sha == ORIGINAL_CODE
        assert config.image == ORIGINAL_IMAGE
        attempt_uri = f"{config.output_root}/read-attempt.json"
        attempt_object = kwargs["read_known"](attempt_uri)
        assert attempt_object is not None
        outputs = cli._output_uris(config.run_id)
        for key in ("query_evidence", "realized_source", "outcome_snapshot", "completion"):
            assert kwargs["read_known"](outputs[key]) is None
        recovered = kwargs["get_or_create_query"](expected_spec)
        assert recovered.disposition == "recovered"
        published = {}
        structure_facts = {
            "observed_integer_micro_row_count": 2,
            "observed_integer_micro_rows_sha256": "1" * 64,
            "observed_query_keys_sha256": "2" * 64,
            "observed_rows_reordered": False,
            "synthesized_skill_keys": [{
                "season": 2023, "week": 1, "source_kind": "skill",
                "source_key": "missing-fixture",
            }],
            "synthesized_skill_key_count": 1,
            "synthesized_skill_keys_sha256": "3" * 64,
            "missing_dst_key_count": 0,
            "final_query_key_union_sha256": "4" * 64,
            "skill_zero_completion_law": supply.SKILL_ZERO_COMPLETION_LAW,
            "skill_zero_law_source_sha256": (
                supply.SKILL_ZERO_LAW_SOURCE_SHA256
            ),
            "salary_catalog_settlement_bridge": (
                supply.SALARY_CATALOG_SETTLEMENT_BRIDGE
            ),
            "salary_catalog_bridge_source_sha256": (
                supply.SALARY_CATALOG_BRIDGE_SOURCE_SHA256
            ),
            "query_returned_exact_union": False,
        }
        for key in ("query_evidence", "realized_source", "outcome_snapshot", "completion"):
            body = {"fixture": key}
            if key == "query_evidence":
                body["query_job_disposition"] = "recovered"
                body["row_count"] = 3
            if key == "completion":
                body["query_job_id"] = expected_spec.job_id
            value = kwargs["publish"](outputs[key], _canonical(body))
            published[key] = (body, _published_identity(value))
        return supply.FullUnionOutcomeSupplyV1(
            outcome_key_projection=kwargs["outcome_key_projection"],
            outcome_key_projection_identity=kwargs["outcome_key_projection_identity"],
            attempt={"fixture": "attempt"},
            attempt_identity=_published_identity(attempt_object),
            query_evidence=published["query_evidence"][0],
            query_evidence_identity=published["query_evidence"][1],
            realized_source=published["realized_source"][0],
            realized_source_identity=published["realized_source"][1],
            outcome_snapshot=published["outcome_snapshot"][0],
            outcome_snapshot_identity=published["outcome_snapshot"][1],
            completion=published["completion"][0],
            completion_identity=published["completion"][1],
            recovery_result_structure=structure_facts,
        )

    return run


def test_source_has_no_bigquery_submission_capability() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    prohibited_attributes = {
        "query", "query_and_wait", "insert_job", "create_job",
    }
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in prohibited_attributes
    ]
    names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    assert calls == []
    assert "QueryJobConfig" not in names
    assert "run_corpus_r6_full_union_outcome_supply_v1" not in source


def test_legacy_prelaunch_ownership_is_content_bound_not_rendering_bound() -> None:
    previous_intent = {
        "bytes": 7342,
        "generation": "1787795058875426",
        "sha256": "1" * 64,
        "uri": "gs://fixture/recovery-intent.json",
    }
    body = {
        "automatic_retry_licensed": False,
        "first_recovery_execution_submission_licensed": True,
        "job": JOB,
        "max_recovery_execution_submission_calls": 1,
        "query_submission_licensed": False,
        "recovery_intent": previous_intent,
        "recovery_ordinal": 1,
        "run_id": RUN_ID,
        "schema_version": (
            "r6-full-union-recovery-prelaunch-resumption-ownership/v1"
        ),
    }
    pretty = (json.dumps(body, indent=2, sort_keys=True) + "\n").encode()
    assert pretty != _canonical(body)
    assert cli._previous_prelaunch_ownership_v1(
        pretty,
        previous_intent_identity=previous_intent,
        run_id=RUN_ID,
        job=JOB,
    ) == body
    with pytest.raises(cli.R6FullUnionRecoveryV1Error, match="not canonical"):
        cli._json(pretty, label="controller-created object")


@pytest.mark.parametrize(
    "raw",
    [
        b'{"duplicate":1,"duplicate":2}',
        b'{"nested":{"duplicate":1,"duplicate":2}}',
        b'{"not_finite":NaN}',
        b'{"not_finite":1e999}',
        b'{"not_finite":-1e999}',
        b'{"valid":true} trailing-junk',
        b'\xef\xbb\xbf{"bom":true}',
        b'{"invalid_utf8":"\xff"}',
        b"[]",
    ],
)
def test_legacy_content_identity_parser_rejects_ambiguous_json(raw: bytes) -> None:
    with pytest.raises(cli.R6FullUnionRecoveryV1Error):
        cli._content_identity_json(raw, label="previous prelaunch ownership")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("run_id", "different-run-id"),
        ("recovery_ordinal", 2),
        ("max_recovery_execution_submission_calls", 2),
        ("first_recovery_execution_submission_licensed", False),
        ("query_submission_licensed", True),
    ],
)
def test_legacy_prelaunch_ownership_semantic_drift_is_rejected(
    field: str, value: object,
) -> None:
    previous_intent = {
        "bytes": 7342,
        "generation": "1787795058875426",
        "sha256": "1" * 64,
        "uri": "gs://fixture/recovery-intent.json",
    }
    body = {
        "automatic_retry_licensed": False,
        "first_recovery_execution_submission_licensed": True,
        "job": JOB,
        "max_recovery_execution_submission_calls": 1,
        "query_submission_licensed": False,
        "recovery_intent": previous_intent,
        "recovery_ordinal": 1,
        "run_id": RUN_ID,
        "schema_version": (
            "r6-full-union-recovery-prelaunch-resumption-ownership/v1"
        ),
    }
    body[field] = value
    raw = (json.dumps(body, indent=2, sort_keys=True) + "\n").encode()
    with pytest.raises(
        cli.R6FullUnionRecoveryV1Error,
        match="previous prelaunch ownership differs",
    ):
        cli._previous_prelaunch_ownership_v1(
            raw,
            previous_intent_identity=previous_intent,
            run_id=RUN_ID,
            job=JOB,
        )


def test_fixed_job_helper_is_get_only_and_disables_job_retry() -> None:
    spec = _spec()
    job = _FakeJob(spec)
    client = _GetOnlyBQ(job)
    counters = {"get_job": 0, "result": 0}
    value = cli._recover_existing_fixed_job(
        client.get_job, spec=spec, expected_metadata=_job_metadata(job, spec),
        counters=counters,
    )
    assert value.disposition == "recovered"
    assert tuple(value.result.rows) == job.rows
    assert client.get_calls == [(spec.job_id, "US")]
    assert job.result_calls == [(None, None)]
    assert counters == {"get_job": 1, "result": 1}
    assert not hasattr(client, "query")


def test_absent_fixed_job_fails_without_fallback() -> None:
    spec = _spec()

    def absent(_job_id: str, *, location: str):
        assert location == "US"
        raise NotFound("absent")

    counters = {"get_job": 0, "result": 0}
    with pytest.raises(cli.R6FullUnionRecoveryV1Error, match="exact fixed job recovery"):
        cli._recover_existing_fixed_job(
            absent, spec=spec,
            expected_metadata=_job_metadata(_FakeJob(spec), spec), counters=counters,
        )
    assert counters == {"get_job": 1, "result": 0}


def test_fixed_job_configuration_drift_fails_before_result() -> None:
    spec = _spec()
    job = _FakeJob(spec)
    job.use_query_cache = True
    client = _GetOnlyBQ(job)
    counters = {"get_job": 0, "result": 0}
    with pytest.raises(
        cli.R6FullUnionRecoveryV1Error,
        match="terminal-success metadata differs",
    ):
        cli._recover_existing_fixed_job(
            client.get_job, spec=spec,
            expected_metadata=_job_metadata(job, spec), counters=counters,
        )
    assert client.get_calls == [(spec.job_id, "US")]
    assert job.result_calls == []
    assert counters == {"get_job": 1, "result": 0}


def test_recover_binds_original_and_recovery_runtimes_and_closes_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gcs, intent_identity, identities, job, bq = _seed_recovery_fixture()
    monkeypatch.setattr(
        cli.supply, "supply_full_union_outcome_snapshot_v1",
        _fake_pure_supplier(expected_spec=_spec()),
    )
    worker = cli.recover_supply_v1(
        project=cli.PROJECT, run_id=RUN_ID, job=JOB,
        original_code_sha=ORIGINAL_CODE, original_image=ORIGINAL_IMAGE,
        recovery_code_sha=RECOVERY_CODE, recovery_image=RECOVERY_IMAGE,
        recovery_stage_token=TOKEN, recovery_intent_identity=intent_identity,
        environ=_runtime_env(), storage_client=gcs,
        bq_client_factory=lambda: bq, clock=lambda: NOW + timedelta(minutes=1),
    )
    assert worker.body["query_job_disposition"] == "recovered"
    assert worker.body["read_attempt_identity"] == identities["attempt"]
    assert worker.body["original_runtime"]["image"] == ORIGINAL_IMAGE
    assert worker.body["recovery_runtime"]["image"] == RECOVERY_IMAGE
    assert worker.body["job_submission_count"] == 0
    assert worker.body["new_job_count"] == 0
    assert bq.get_calls == [(_spec().job_id, "US")]
    assert job.result_calls == [(None, None)]
    assert gcs.upload_preconditions and set(gcs.upload_preconditions) == {0}


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda env: env.__setitem__(cli.RECOVERY_IMAGE_ENV, ORIGINAL_IMAGE), "environment"),
        (lambda env: env.__setitem__("CLOUD_RUN_TASK_ATTEMPT", "1"), "environment"),
    ],
)
def test_recover_runtime_drift_fails_before_bigquery(
    monkeypatch: pytest.MonkeyPatch, mutation, message: str,
) -> None:
    gcs, intent_identity, _, _, _ = _seed_recovery_fixture()
    env = _runtime_env()
    mutation(env)
    constructed = 0

    def factory():
        nonlocal constructed
        constructed += 1
        raise AssertionError("must fail before BigQuery construction")

    with pytest.raises(cli.R6FullUnionRecoveryV1Error, match=message):
        cli.recover_supply_v1(
            project=cli.PROJECT, run_id=RUN_ID, job=JOB,
            original_code_sha=ORIGINAL_CODE, original_image=ORIGINAL_IMAGE,
            recovery_code_sha=RECOVERY_CODE, recovery_image=RECOVERY_IMAGE,
            recovery_stage_token=TOKEN, recovery_intent_identity=intent_identity,
            environ=env, storage_client=gcs, bq_client_factory=factory,
        )
    assert constructed == 0


def test_existing_downstream_or_changed_attempt_fails_before_bigquery() -> None:
    for drift in ("downstream", "attempt"):
        gcs, intent_identity, identities, _, _ = _seed_recovery_fixture()
        if drift == "downstream":
            gcs.seed(
                cli._output_uris(RUN_ID)["query_evidence"],
                _canonical({"unexpected": True}), 80,
            )
        else:
            gcs.seed(
                str(identities["attempt"]["uri"]),
                _canonical({"changed": True}), 81,
            )
        constructed = 0

        def factory():
            nonlocal constructed
            constructed += 1
            raise AssertionError("must fail before BigQuery construction")

        with pytest.raises(cli.R6FullUnionRecoveryV1Error):
            cli.recover_supply_v1(
                project=cli.PROJECT, run_id=RUN_ID, job=JOB,
                original_code_sha=ORIGINAL_CODE, original_image=ORIGINAL_IMAGE,
                recovery_code_sha=RECOVERY_CODE, recovery_image=RECOVERY_IMAGE,
                recovery_stage_token=TOKEN, recovery_intent_identity=intent_identity,
                environ=_runtime_env(), storage_client=gcs,
                bq_client_factory=factory,
            )
        assert constructed == 0


def _terminal_envelope(
    *, intent: Mapping[str, object], intent_identity: Mapping[str, object],
    execution: str,
) -> dict[str, object]:
    recovery = intent["recovery_runtime"]
    env = sorted([
        {"name": cli.RECOVERY_ENABLED_ENV, "value": "1"},
        {"name": cli.RECOVERY_STAGE_TOKEN_ENV, "value": TOKEN},
        {"name": cli.RECOVERY_CODE_ENV, "value": RECOVERY_CODE},
        {"name": cli.RECOVERY_IMAGE_ENV, "value": RECOVERY_IMAGE},
    ], key=lambda item: item["name"])
    return {
        "metadata": {
            "name": execution, "uid": "fixture-recovery-uid",
            "labels": {"run.googleapis.com/job": JOB},
        },
        "spec": {
            "taskCount": 1, "parallelism": 1,
            "template": {"spec": {
                "maxRetries": 0, "timeoutSeconds": "28800",
                "serviceAccountName": SERVICE_ACCOUNT,
                "volumes": [], "vpcAccess": {},
                "containers": [{
                    "image": recovery["image"], "command": ["python"],
                    "args": cli._recover_argv(intent, intent_identity),
                    "env": env, "volumeMounts": [],
                    "resources": {"limits": {"cpu": "8", "memory": "32Gi"}},
                }],
            }},
        },
        "status": {
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1, "failedCount": 0, "runningCount": 0,
            "completionTime": (NOW + timedelta(minutes=2)).isoformat(),
        },
    }


def _launch_intent(
    *, intent: dict[str, object], intent_identity: dict[str, object],
) -> dict[str, object]:
    argv = cli._recover_argv(intent, intent_identity)
    argv_sha = sha256(
        b"".join(item.encode() + b"\0" for item in argv)
    ).hexdigest()
    return {
        "schema_version": "r6-full-union-recovery-stage-launch-intent/v2",
        "stage": "supply-recovery-02",
        "token": TOKEN,
        "project": cli.PROJECT,
        "region": cli.REGION,
        "run_id": RUN_ID,
        "job": JOB,
        "original_code_sha": ORIGINAL_CODE,
        "original_image": ORIGINAL_IMAGE,
        "recovery_code_sha": RECOVERY_CODE,
        "recovery_image": RECOVERY_IMAGE,
        "service_account": SERVICE_ACCOUNT,
        "gate": cli.RECOVERY_ENABLED_ENV,
        "argv": argv,
        "argv_sha256": argv_sha,
        "execution_env": sorted([
            {"name": cli.RECOVERY_ENABLED_ENV, "value": "1"},
            {"name": cli.RECOVERY_STAGE_TOKEN_ENV, "value": TOKEN},
            {"name": cli.RECOVERY_CODE_ENV, "value": RECOVERY_CODE},
            {"name": cli.RECOVERY_IMAGE_ENV, "value": RECOVERY_IMAGE},
        ], key=lambda item: item["name"]),
        "query_compile_receipt": {"fixture": True},
        "recovery_intent": intent_identity,
        "fixed_job_lookup_only": True,
        "query_submission_licensed": False,
        "ordinary_supply_relaunch_licensed": False,
        "automatic_retry_licensed": False,
    }


def test_launch_ownership_is_create_only_and_reopen_never_relicenses(
    tmp_path: Path,
) -> None:
    gcs, intent_identity, _, _, _ = _seed_recovery_fixture()
    intent = cli.validate_recovery_intent_v1(
        json.loads(cli.GenerationPinnedGCSV1(gcs).read_exact(intent_identity))
    )
    launch_path = tmp_path / "launch-intent.json"
    launch_path.write_bytes(_canonical(_launch_intent(
        intent=intent, intent_identity=intent_identity,
    )))
    first = cli.claim_recovery_launch_v1(
        project=cli.PROJECT, region=cli.REGION, run_id=RUN_ID, job=JOB,
        original_code_sha=ORIGINAL_CODE, original_image=ORIGINAL_IMAGE,
        recovery_code_sha=RECOVERY_CODE, recovery_image=RECOVERY_IMAGE,
        service_account=SERVICE_ACCOUNT, recovery_stage_token=TOKEN,
        recovery_intent_identity=intent_identity,
        recovery_launch_intent_path=launch_path, storage_client=gcs,
        clock=lambda: NOW,
    )
    assert first.created is True
    assert first.body["max_recovery_execution_submission_calls"] == 1
    second = cli.claim_recovery_launch_v1(
        project=cli.PROJECT, region=cli.REGION, run_id=RUN_ID, job=JOB,
        original_code_sha=ORIGINAL_CODE, original_image=ORIGINAL_IMAGE,
        recovery_code_sha=RECOVERY_CODE, recovery_image=RECOVERY_IMAGE,
        service_account=SERVICE_ACCOUNT, recovery_stage_token=TOKEN,
        recovery_intent_identity=intent_identity,
        recovery_launch_intent_path=launch_path, storage_client=gcs,
        clock=lambda: NOW + timedelta(days=1),
    )
    assert second.created is False
    assert second.identity == first.identity
    assert second.body == first.body


def test_ambiguous_launch_ownership_create_consumes_authority(
    tmp_path: Path,
) -> None:
    gcs, intent_identity, _, _, _ = _seed_recovery_fixture()
    intent = cli.validate_recovery_intent_v1(
        json.loads(cli.GenerationPinnedGCSV1(gcs).read_exact(intent_identity))
    )
    launch_path = tmp_path / "launch-intent.json"
    launch_path.write_bytes(_canonical(_launch_intent(
        intent=intent, intent_identity=intent_identity,
    )))
    gcs.ambiguous_upload = True
    ownership = cli.claim_recovery_launch_v1(
        project=cli.PROJECT, region=cli.REGION, run_id=RUN_ID, job=JOB,
        original_code_sha=ORIGINAL_CODE, original_image=ORIGINAL_IMAGE,
        recovery_code_sha=RECOVERY_CODE, recovery_image=RECOVERY_IMAGE,
        service_account=SERVICE_ACCOUNT, recovery_stage_token=TOKEN,
        recovery_intent_identity=intent_identity,
        recovery_launch_intent_path=launch_path, storage_client=gcs,
        clock=lambda: NOW,
    )
    assert ownership.created is False
    assert cli.GenerationPinnedGCSV1(gcs).resolve_required(
        cli._launch_ownership_uri(RUN_ID)
    ) is not None


def test_finalize_reopens_all_standard_objects_and_replays_receipt_exactly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    gcs, intent_identity, _, _, bq = _seed_recovery_fixture()
    monkeypatch.setattr(
        cli.supply, "supply_full_union_outcome_snapshot_v1",
        _fake_pure_supplier(expected_spec=_spec()),
    )
    worker = cli.recover_supply_v1(
        project=cli.PROJECT, run_id=RUN_ID, job=JOB,
        original_code_sha=ORIGINAL_CODE, original_image=ORIGINAL_IMAGE,
        recovery_code_sha=RECOVERY_CODE, recovery_image=RECOVERY_IMAGE,
        recovery_stage_token=TOKEN, recovery_intent_identity=intent_identity,
        environ=_runtime_env(), storage_client=gcs,
        bq_client_factory=lambda: bq, clock=lambda: NOW + timedelta(minutes=1),
    )
    intent = cli.validate_recovery_intent_v1(
        json.loads(cli.GenerationPinnedGCSV1(gcs).read_exact(intent_identity))
    )
    launch_path = tmp_path / "launch-intent.json"
    launch_path.write_bytes(_canonical(_launch_intent(
        intent=intent, intent_identity=intent_identity,
    )))
    ownership = cli.claim_recovery_launch_v1(
        project=cli.PROJECT, region=cli.REGION, run_id=RUN_ID, job=JOB,
        original_code_sha=ORIGINAL_CODE, original_image=ORIGINAL_IMAGE,
        recovery_code_sha=RECOVERY_CODE, recovery_image=RECOVERY_IMAGE,
        service_account=SERVICE_ACCOUNT, recovery_stage_token=TOKEN,
        recovery_intent_identity=intent_identity,
        recovery_launch_intent_path=launch_path, storage_client=gcs,
        clock=lambda: NOW,
    )
    terminal_path = tmp_path / "terminal-execution.json"
    terminal_path.write_bytes(_canonical(_terminal_envelope(
        intent=intent, intent_identity=intent_identity,
        execution=worker.body["runtime_envelope"]["cloud_run_execution"],
    )))
    receipt = cli.finalize_recovery_v1(
        project=cli.PROJECT, region=cli.REGION, run_id=RUN_ID, job=JOB,
        original_code_sha=ORIGINAL_CODE, original_image=ORIGINAL_IMAGE,
        recovery_code_sha=RECOVERY_CODE, recovery_image=RECOVERY_IMAGE,
        service_account=SERVICE_ACCOUNT, recovery_stage_token=TOKEN,
        recovery_intent_identity=intent_identity,
        recovery_launch_intent_path=launch_path,
        launch_ownership_identity=ownership.identity,
        recovery_terminal_execution_path=terminal_path, storage_client=gcs,
        clock=lambda: NOW + timedelta(minutes=3),
    )
    assert receipt.body["recovery_closed"] is True
    assert receipt.body["same_fixed_job_recovered"] is True
    assert receipt.body["job_submission_count"] == 0
    replay = cli.finalize_recovery_v1(
        project=cli.PROJECT, region=cli.REGION, run_id=RUN_ID, job=JOB,
        original_code_sha=ORIGINAL_CODE, original_image=ORIGINAL_IMAGE,
        recovery_code_sha=RECOVERY_CODE, recovery_image=RECOVERY_IMAGE,
        service_account=SERVICE_ACCOUNT, recovery_stage_token=TOKEN,
        recovery_intent_identity=intent_identity,
        recovery_launch_intent_path=launch_path,
        launch_ownership_identity=ownership.identity,
        recovery_terminal_execution_path=terminal_path, storage_client=gcs,
        clock=lambda: NOW + timedelta(days=1),
    )
    assert replay == receipt


def test_cli_stdout_is_compact_and_contains_no_rows(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    gcs, intent_identity, _, _, _ = _seed_recovery_fixture()
    body = {
        "run_id": RUN_ID, "cloud_run_job": JOB,
        "rows": [{"realized_score": "SHOULD_NOT_APPEAR"}],
    }
    returned = cli.RecoveryObjectV1(body=body, identity=intent_identity)
    monkeypatch.setattr(cli, "recover_supply_v1", lambda **_kwargs: returned)
    argv = [
        "recover", "--execute", f"--project={cli.PROJECT}",
        f"--run-id={RUN_ID}", f"--job={JOB}",
        f"--original-code-sha={ORIGINAL_CODE}", f"--original-image={ORIGINAL_IMAGE}",
        f"--recovery-code-sha={RECOVERY_CODE}", f"--recovery-image={RECOVERY_IMAGE}",
    ]
    for suffix in ("uri", "generation", "sha256", "bytes"):
        argv.append(f"--recovery-intent-{suffix}={intent_identity[suffix]}")
    assert cli.main(
        argv, environ=_runtime_env(), storage_client=gcs,
        bq_client_factory=lambda: object(),
    ) == 0
    output = capsys.readouterr().out
    parsed = json.loads(output)
    assert parsed["outcome_rows_in_stdout"] is False
    assert parsed["job_submission_count"] == 0
    assert "SHOULD_NOT_APPEAR" not in output
    assert "realized_score" not in output


def test_cli_is_default_off_without_literal_execute() -> None:
    gcs, intent_identity, _, _, _ = _seed_recovery_fixture()
    argv = [
        "recover", f"--project={cli.PROJECT}", f"--run-id={RUN_ID}",
        f"--job={JOB}", f"--original-code-sha={ORIGINAL_CODE}",
        f"--original-image={ORIGINAL_IMAGE}",
        f"--recovery-code-sha={RECOVERY_CODE}",
        f"--recovery-image={RECOVERY_IMAGE}",
    ]
    for suffix in ("uri", "generation", "sha256", "bytes"):
        argv.append(f"--recovery-intent-{suffix}={intent_identity[suffix]}")
    with pytest.raises(cli.R6FullUnionRecoveryV1Error, match="--execute"):
        cli.main(
            argv, environ=_runtime_env(), storage_client=gcs,
            bq_client_factory=lambda: (_ for _ in ()).throw(
                AssertionError("default-off path must not construct BigQuery")
            ),
        )
