"""Focused offline tests for the R6 realized-grade cloud wrapper."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.util
from pathlib import Path
import sys

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_grade_release_v1 as release
from nfl_dfs.research import corpus_r6_full_union_realized_grading_v1 as grading
from nfl_dfs.research import lr8_label_score_map as shared


ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    path = ROOT / "scripts/run_corpus_r6_full_union_realized_grade_v1.py"
    spec = importlib.util.spec_from_file_location(
        "run_corpus_r6_full_union_realized_grade_v1_test", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


class NotFound(Exception):
    pass


class _Blob:
    def __init__(
        self, client: "_Client", bucket: str, name: str,
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

    @property
    def uri(self) -> str:
        return f"gs://{self.bucket}/{self.name}"

    def reload(self, *, if_generation_match: int | None = None) -> None:
        versions = self.client.objects.get(self.key, {})
        if not versions:
            raise NotFound("absent")
        generation = max(versions) if self.generation is None else int(self.generation)
        if generation not in versions:
            raise NotFound("generation absent")
        if if_generation_match is not None and generation != if_generation_match:
            raise RuntimeError("generation differs")
        self.generation = generation
        self.time_created = datetime(2026, 8, 26, tzinfo=timezone.utc) + timedelta(
            microseconds=generation
        )

    def download_as_bytes(self, *, if_generation_match: int) -> bytes:
        assert self.generation == if_generation_match
        self.client.read_uris.append(self.uri)
        return self.client.objects[self.key][if_generation_match]

    def upload_from_string(
        self, raw: bytes, *, content_type: str, if_generation_match: int,
    ) -> None:
        assert content_type == "application/json"
        assert if_generation_match == 0
        self.client.upload_uris.append(self.uri)
        if self.client.objects.get(self.key):
            raise RuntimeError("precondition failed")
        generation = self.client.next_generation
        self.client.next_generation += 1
        self.client.objects[self.key] = {generation: raw}
        self.generation = generation
        if self.client.ambiguous_upload:
            self.client.ambiguous_upload = False
            raise RuntimeError("lost response")


class _Bucket:
    def __init__(self, client: "_Client", name: str) -> None:
        self.client = client
        self.name = name

    def blob(self, name: str, generation: int | None = None) -> _Blob:
        return _Blob(self.client, self.name, name, generation)


class _Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[int, bytes]] = {}
        self.next_generation = 100
        self.read_uris: list[str] = []
        self.upload_uris: list[str] = []
        self.ambiguous_upload = False

    def bucket(self, name: str) -> _Bucket:
        return _Bucket(self, name)

    def seed(self, uri: str, raw: bytes, generation: int) -> dict[str, object]:
        bucket, name = uri.removeprefix("gs://").split("/", 1)
        self.objects.setdefault((bucket, name), {})[generation] = raw
        return _identity(uri, raw=raw, generation=generation)


def _identity(
    uri: str, *, raw: bytes | None = None, generation: int = 1,
) -> dict[str, object]:
    body = uri.encode() if raw is None else raw
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(body).hexdigest(),
        "bytes": len(body),
    }


def _config() -> release.FullUnionGradeReleaseConfigV1:
    return release.FullUnionGradeReleaseConfigV1(
        run_id="r6-grade-release-fixture",
        job="r6-grade-job",
        execution="r6-grade-job-abc12",
        code_sha="a" * 40,
        image=f"grade@sha256:{'b' * 64}",
        expected_supply_run_id="r6-supply-fixture",
        expected_supply_job="r6-supply-job",
        expected_supply_code_sha="c" * 40,
        expected_supply_image=f"supply@sha256:{'d' * 64}",
        snapshot_module_sha256="1" * 64,
        snapshot_cli_sha256="2" * 64,
        snapshot_test_sha256="3" * 64,
        snapshot_cli_test_sha256="4" * 64,
        enabled=True,
    )


def _runtime_env(*, enabled: bool = True) -> dict[str, str]:
    config = _config()
    return {
        cli.ENABLED_ENV: "1" if enabled else "0",
        "CLOUD_RUN_JOB": config.job,
        "CLOUD_RUN_EXECUTION": config.execution,
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_COUNT": "1",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
        cli.CODE_SHA_ENV: config.code_sha,
        cli.IMAGE_ENV: config.image,
    }


def _argv() -> list[str]:
    config = _config()
    supply_root = (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-full-union-realized/r6-supply-fixture"
    )
    result = [
        "--run-id", config.run_id,
        "--code-sha", config.code_sha,
        "--image", config.image,
        "--expected-supply-run-id", config.expected_supply_run_id,
        "--expected-supply-job", config.expected_supply_job,
        "--expected-supply-code-sha", config.expected_supply_code_sha,
        "--expected-supply-image", config.expected_supply_image,
        "--snapshot-module-sha256", config.snapshot_module_sha256,
        "--snapshot-cli-sha256", config.snapshot_cli_sha256,
        "--snapshot-test-sha256", config.snapshot_test_sha256,
        "--snapshot-cli-test-sha256", config.snapshot_cli_test_sha256,
    ]
    uris = {
        "panel-freeze": (
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "freeze/panel-freeze.json"
        ),
        "outcome-supply-completion": f"{supply_root}/completion.json",
        "outcome-key-projection": f"{supply_root}/outcome-key-projection.json",
        "realized-source": f"{supply_root}/realized-source.json",
        "outcome-snapshot": f"{supply_root}/outcome-snapshot.json",
        "expected-lease": shared.adapter.HISTORICAL_OUTCOME_LEASE_URI,
    }
    for prefix, uri in uris.items():
        identity = _identity(uri)
        result.extend([
            f"--{prefix}-uri", str(identity["uri"]),
            f"--{prefix}-generation", str(identity["generation"]),
            f"--{prefix}-sha256", str(identity["sha256"]),
            f"--{prefix}-bytes", str(identity["bytes"]),
        ])
    return result


def _lease(config: release.FullUnionGradeReleaseConfigV1) -> tuple[
    dict[str, object], dict[str, object], bytes,
]:
    body = {
        "version": shared.adapter.HISTORICAL_OUTCOME_LEASE_VERSION,
        "run_id": config.expected_supply_run_id,
        "job": config.expected_supply_job,
        "code_sha": config.expected_supply_code_sha,
        "image": config.expected_supply_image,
        "acquired_at": "2026-08-26T00:00:00+00:00",
    }
    raw = shared.canonical_json(body)
    identity = _identity(
        shared.adapter.HISTORICAL_OUTCOME_LEASE_URI,
        raw=raw,
        generation=10,
    )
    return body, {"body": body, "object_receipt": {
        **identity, "create_only": True,
    }}, raw


def _blind_fixture(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Real pinned reads with pure validators and no score objects seeded."""
    config = _config()
    client = _Client()
    panel = {"panel": "structural"}
    panel_identity = client.seed(
        "gs://fixture/freeze/panel-freeze.json",
        batch.canonical_json_bytes(panel),
        1,
    )
    projection = {
        "panel_freeze_identity": panel_identity,
        "panel_freeze_sha256": "5" * 64,
        "outcome_key_projection_sha256": "6" * 64,
        "later_source_freeze_identity": _identity("gs://fixture/later.json"),
        "later_source_freeze_sha256": "7" * 64,
    }
    projection_identity = client.seed(
        "gs://fixture/supply/outcome-key-projection.json",
        batch.canonical_json_bytes(projection),
        2,
    )
    evidence_identity = _identity("gs://fixture/supply/query-evidence.json")
    source_identity = _identity("gs://fixture/supply/realized-source.json")
    snapshot_identity = _identity("gs://fixture/supply/outcome-snapshot.json")
    smoke = {
        "panel_freeze_identity": panel_identity,
        "outcome_key_projection_identity": projection_identity,
        "reviewed_source_commit_sha": config.expected_supply_code_sha,
        "runtime_immutable_image": config.expected_supply_image,
        "snapshot_module_sha256": config.snapshot_module_sha256,
        "snapshot_cli_sha256": config.snapshot_cli_sha256,
        "snapshot_test_sha256": config.snapshot_test_sha256,
        "snapshot_cli_test_sha256": config.snapshot_cli_test_sha256,
        "actual_root_smoke_receipt_sha256": "8" * 64,
    }
    smoke_identity = client.seed(
        "gs://fixture/supply/actual-root-smoke-receipt.json",
        batch.canonical_json_bytes(smoke),
        3,
    )
    _lease_body, lease_binding, lease_raw = _lease(config)
    query_contract = {"source_snapshot_at": "2026-08-25T00:00:00+00:00"}
    attempt = {
        "historical_outcome_lease": lease_binding,
        "query_contract": query_contract,
        "table_receipts_before_query": [],
    }
    attempt_identity = client.seed(
        "gs://fixture/supply/attempt.json",
        batch.canonical_json_bytes(attempt),
        4,
    )
    spec = cli.registered.QuerySpec(
        sql="SELECT 1",
        parameters=(),
        job_id="r6_full_union_realized_fixture",
        location="US",
        sql_sha256="9" * 64,
        parameters_sha256="a" * 64,
        union_keys_sha256="b" * 64,
    )
    completion = {
        "run_id": config.expected_supply_run_id,
        "panel_freeze_identity": panel_identity,
        "outcome_key_projection_identity": projection_identity,
        "actual_root_smoke_receipt_identity": smoke_identity,
        "attempt_identity": attempt_identity,
        "query_evidence_identity": evidence_identity,
        "realized_source_identity": source_identity,
        "outcome_snapshot_identity": snapshot_identity,
        "query_job_id": spec.job_id,
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": cli.supply.LEASE_RELEASE_OWNER,
    }
    completion_identity = client.seed(
        "gs://fixture/supply/completion.json",
        batch.canonical_json_bytes(completion),
        5,
    )
    keys = (cli.outcomes.OutcomeKeyV1(
        source_ordinal=0,
        season=2023,
        week=1,
        slate_id="2023-w01",
        player_id="player",
        position="WR",
        team="AAA",
        source_kind="skill",
        source_key="player",
    ),)

    def reopen_panel(identity, *, read_exact):
        assert read_exact(identity) == batch.canonical_json_bytes(panel)
        return dict(panel), dict(identity)

    def validate_projection(value, *, identity, read_exact):
        assert read_exact(identity) == batch.canonical_json_bytes(projection)
        return dict(value), dict(identity), keys

    def validate_smoke(value, **kwargs):
        pairs = {
            "reviewed_source_commit_sha": "expected_reviewed_source_commit_sha",
            "runtime_immutable_image": "expected_runtime_immutable_image",
            "snapshot_module_sha256": "expected_snapshot_module_sha256",
            "snapshot_cli_sha256": "expected_snapshot_cli_sha256",
            "snapshot_test_sha256": "expected_snapshot_test_sha256",
            "snapshot_cli_test_sha256": "expected_snapshot_cli_test_sha256",
        }
        if any(value[field] != kwargs[expected] for field, expected in pairs.items()):
            raise cli.outcomes.CorpusR6FullUnionOutcomeSnapshotV1Error(
                "actual-root smoke receipt canonical replay differs"
            )
        assert kwargs["read_exact"](kwargs["identity"]) == (
            batch.canonical_json_bytes(smoke)
        )
        return dict(value), dict(kwargs["identity"])

    monkeypatch.setattr(cli.freeze, "reopen_panel_freeze_v1", reopen_panel)
    monkeypatch.setattr(
        cli.outcomes, "validate_outcome_key_projection_v1", validate_projection
    )
    monkeypatch.setattr(
        cli.outcomes, "validate_actual_root_smoke_receipt_v1", validate_smoke
    )
    monkeypatch.setattr(
        cli.supply,
        "_query_spec_from_contract",
        lambda value, **kwargs: (spec, query_contract),
    )

    def validate_attempt(value, *, config, lease, **kwargs):
        assert config.run_id == _config().expected_supply_run_id
        assert config.job == _config().expected_supply_job
        assert config.code_sha == _config().expected_supply_code_sha
        assert config.image == _config().expected_supply_image
        assert lease == lease_binding
        return dict(value)

    monkeypatch.setattr(
        cli.supply, "validate_outcome_attempt_v1", validate_attempt
    )
    return {
        "config": config,
        "client": client,
        "panel_identity": panel_identity,
        "completion_identity": completion_identity,
        "projection_identity": projection_identity,
        "evidence_identity": evidence_identity,
        "source_identity": source_identity,
        "snapshot_identity": snapshot_identity,
        "lease_identity": {
            key: lease_binding["object_receipt"][key]
            for key in ("uri", "generation", "sha256", "bytes")
        },
        "lease_binding": lease_binding,
        "lease_raw": lease_raw,
    }


def _run_blind(case: dict[str, object], *, config=None):
    return cli.preflight_grade_authority_v1(
        config=case["config"] if config is None else config,
        panel_freeze_identity=case["panel_identity"],
        outcome_supply_completion_identity=case["completion_identity"],
        outcome_key_projection_identity=case["projection_identity"],
        realized_source_identity=case["source_identity"],
        outcome_snapshot_identity=case["snapshot_identity"],
        store=cli.GenerationPinnedGCSV1(case["client"]),
    )


def _final_case() -> dict[str, object]:
    config = _config()
    panel = _identity("gs://fixture/panel.json")
    projection_identity = _identity("gs://fixture/projection.json")
    source_identity = _identity("gs://fixture/source.json")
    snapshot_identity = _identity("gs://fixture/snapshot.json")
    supply_identity = _identity("gs://fixture/completion.json")
    smoke_identity = _identity("gs://fixture/smoke.json")
    projection = {
        "panel_freeze_identity": panel,
        "panel_freeze_sha256": "1" * 64,
        "outcome_key_projection_sha256": "2" * 64,
        "later_source_freeze_identity": _identity("gs://fixture/later.json"),
        "later_source_freeze_sha256": "3" * 64,
    }
    source = {
        "panel_freeze_identity": panel,
        "outcome_key_projection_identity": projection_identity,
        "realized_source_sha256": "4" * 64,
    }
    snapshot = {
        "panel_freeze_identity": panel,
        "outcome_key_projection_identity": projection_identity,
        "realized_source_identity": source_identity,
        "outcome_snapshot_sha256": "5" * 64,
    }
    smoke = {
        "panel_freeze_identity": panel,
        "outcome_key_projection_identity": projection_identity,
        "reviewed_source_commit_sha": config.expected_supply_code_sha,
        "runtime_immutable_image": config.expected_supply_image,
        "snapshot_module_sha256": config.snapshot_module_sha256,
        "snapshot_cli_sha256": config.snapshot_cli_sha256,
        "snapshot_test_sha256": config.snapshot_test_sha256,
        "snapshot_cli_test_sha256": config.snapshot_cli_test_sha256,
        "actual_root_smoke_receipt_sha256": "6" * 64,
    }
    supply_completion = {
        "run_id": config.expected_supply_run_id,
        "object_uri": supply_identity["uri"],
        "completion_sha256": "7" * 64,
        "query_job_id": "r6_full_union_realized_fixture",
        "panel_freeze_identity": panel,
        "outcome_key_projection_identity": projection_identity,
        "realized_source_identity": source_identity,
        "outcome_snapshot_identity": snapshot_identity,
        "actual_root_smoke_receipt_identity": smoke_identity,
    }
    coverage = {
        "source_slate_count": 54,
        "rank_80_book_count": 2592,
        "prefix_grade_count": 7776,
        "aggregate_cell_count": 144,
        "aggregate_slate_row_count": 7776,
        "unique_final_union_roster_count": 9000,
        "roster_sum_operation_ceiling": 9000,
        "roster_sum_operation_count": 9000,
        "actual_player_outcome_row_count": 5000,
        "every_unique_final_union_roster_scored_once": True,
        "roster_sum_operation_ceiling_equals_final_union_count": True,
        "every_book_projected_from_union_score_lookup": True,
        "all_4_14_80_prefixes_projected_from_rank_80": True,
        "actual_player_outcome_keys_exact": True,
        "complete": True,
    }
    logical = {
        "panel_freeze_identity": panel,
        "outcome_key_projection_identity": projection_identity,
        "realized_source_identity": source_identity,
        "outcome_snapshot_identity": snapshot_identity,
        "realized_grade_sha256": "8" * 64,
        "slate_grade_descriptors_sha256": "9" * 64,
        "aggregate_cells_sha256": "a" * 64,
        "strategy_registry_sha256": "b" * 64,
        "coverage": coverage,
        "contest_metrics": {
            "availability": "unavailable",
            "reason": (
                "full_field_standings_duplicate_tie_settlement_and_"
                "payout_ladder_not_supplied"
            ),
            "rank": None,
            "roi_micro_usd": None,
        },
    }
    root = {
        "target_uri": f"{config.output_root}/realized-grade-root.json",
        "source_slate_count": 54,
        "slate_grade_objects": [{} for _ in range(54)],
        "slate_grade_objects_sha256": "c" * 64,
        "persisted_grade_root_sha256": "d" * 64,
        "logical_grade_root": logical,
    }
    root_identity = _identity(str(root["target_uri"]))
    _lease_body, lease_binding, _lease_raw = _lease(config)
    authority = cli.GradePreflightAuthorityV1(
        panel_freeze={},
        panel_freeze_identity=panel,
        outcome_supply_completion=supply_completion,
        outcome_supply_completion_identity=supply_identity,
        actual_root_smoke_receipt=smoke,
        actual_root_smoke_receipt_identity=smoke_identity,
        outcome_key_projection=projection,
        outcome_key_projection_identity=projection_identity,
        realized_source=source,
        realized_source_identity=source_identity,
        outcome_snapshot=snapshot,
        outcome_snapshot_identity=snapshot_identity,
        supply_attempt={},
        supply_attempt_identity=_identity("gs://fixture/attempt.json"),
        supply_query_evidence={},
        supply_query_evidence_identity=_identity("gs://fixture/evidence.json"),
        historical_lease_binding=lease_binding,
    )
    return {
        "config": config,
        "authority": authority,
        "root": root,
        "root_identity": root_identity,
        "lease_binding": lease_binding,
        "lease_identity": {
            key: lease_binding["object_receipt"][key]
            for key in ("uri", "generation", "sha256", "bytes")
        },
    }


def test_help_is_inert() -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["--help"], environ={})
    assert raised.value.code == 0


def test_default_off_and_bad_runtime_use_zero_storage_callbacks() -> None:
    class Bomb:
        calls = 0

        def bucket(self, name):
            self.calls += 1
            raise AssertionError(name)

    bomb = Bomb()
    with pytest.raises(cli.R6FullUnionRealizedGradeRunnerV1Error):
        cli.main(_argv(), environ=_runtime_env(enabled=False), storage_client=bomb)
    assert bomb.calls == 0

    env = _runtime_env()
    env["CLOUD_RUN_TASK_ATTEMPT"] = "1"
    with pytest.raises(cli.R6FullUnionRealizedGradeRunnerV1Error):
        cli.main(["--execute", *_argv()], environ=env, storage_client=bomb)
    assert bomb.calls == 0


def test_wrong_upstream_uri_fails_before_storage() -> None:
    argv = ["--execute", *_argv()]
    argv[argv.index("--realized-source-uri") + 1] = "gs://wrong/source.json"
    with pytest.raises(
        cli.R6FullUnionRealizedGradeRunnerV1Error,
        match="upstream URI law differs",
    ):
        cli.main(argv, environ=_runtime_env(), storage_client=object())


def test_create_once_equal_recovery_ambiguous_success_and_collision() -> None:
    client = _Client()
    store = cli.GenerationPinnedGCSV1(client)
    raw = batch.canonical_json_bytes({"fixture": True})
    equal_uri = "gs://fixture/grade/equal.json"
    expected = client.seed(equal_uri, raw, 7)
    assert store.publish_create_once(equal_uri, raw) == expected

    ambiguous_uri = "gs://fixture/grade/ambiguous.json"
    client.ambiguous_upload = True
    assert store.publish_create_once(ambiguous_uri, raw)["sha256"] == (
        sha256(raw).hexdigest()
    )

    collision_uri = "gs://fixture/grade/collision.json"
    client.seed(collision_uri, batch.canonical_json_bytes({"wrong": True}), 8)
    with pytest.raises(
        cli.R6FullUnionRealizedGradeRunnerV1Error,
        match="existing .* differs",
    ):
        store.publish_create_once(collision_uri, raw)


def test_outcome_blind_preflight_succeeds_without_score_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _blind_fixture(monkeypatch)
    blind = _run_blind(case)

    assert blind.config == case["config"]
    assert blind.historical_lease_binding == case["lease_binding"]
    forbidden = {
        case["evidence_identity"]["uri"],
        case["source_identity"]["uri"],
        case["snapshot_identity"]["uri"],
    }
    assert forbidden.isdisjoint(case["client"].read_uris)
    assert case["client"].upload_uris == []


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("expected_supply_run_id", "wrong-supply-run"),
        ("expected_supply_job", "wrong-supply-job"),
        ("expected_supply_code_sha", "e" * 40),
        ("expected_supply_image", f"wrong@sha256:{'e' * 64}"),
        ("snapshot_module_sha256", "e" * 64),
        ("snapshot_cli_sha256", "e" * 64),
        ("snapshot_test_sha256", "e" * 64),
        ("snapshot_cli_test_sha256", "e" * 64),
    ],
)
def test_outcome_blind_preflight_rejects_each_independent_pin(
    monkeypatch: pytest.MonkeyPatch, field: str, wrong: str,
) -> None:
    case = _blind_fixture(monkeypatch)
    mutated = replace(case["config"], **{field: wrong})
    with pytest.raises(cli.R6FullUnionRealizedGradeRunnerV1Error):
        _run_blind(case, config=mutated)


def test_stale_live_lease_causes_zero_score_reads_and_zero_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _blind_fixture(monkeypatch)
    stale = shared.canonical_json({
        **case["lease_binding"]["body"],
        "acquired_at": "2026-08-26T00:01:00+00:00",
    })
    case["client"].seed(
        shared.adapter.HISTORICAL_OUTCOME_LEASE_URI, stale, 11
    )

    with pytest.raises(
        cli.R6FullUnionRealizedGradeRunnerV1Error,
        match="lease identity changed",
    ):
        cli.run_grade_cloud_v1(
            config=case["config"],
            panel_freeze_identity=case["panel_identity"],
            outcome_supply_completion_identity=case["completion_identity"],
            outcome_key_projection_identity=case["projection_identity"],
            realized_source_identity=case["source_identity"],
            outcome_snapshot_identity=case["snapshot_identity"],
            expected_lease_identity=case["lease_identity"],
            storage_client=case["client"],
        )
    forbidden = {
        case["evidence_identity"]["uri"],
        case["source_identity"]["uri"],
        case["snapshot_identity"]["uri"],
    }
    assert forbidden.isdisjoint(case["client"].read_uris)
    assert case["client"].upload_uris == []


class _StoreStub:
    def read_exact(self, identity):
        raise AssertionError("stubbed grader must not read")

    def publish_create_once(self, uri, raw):
        raise AssertionError("completion must remain absent")


def _stub_preflight(monkeypatch, case):
    monkeypatch.setattr(cli, "GenerationPinnedGCSV1", lambda client: _StoreStub())
    monkeypatch.setattr(
        cli, "preflight_grade_authority_v1", lambda **kwargs: case["authority"]
    )
    monkeypatch.setattr(
        cli, "open_outcome_grade_authority_v1",
        lambda **kwargs: case["authority"],
    )


def test_grade_root_tampering_blocks_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _final_case()
    _stub_preflight(monkeypatch, case)

    class Lease:
        def __init__(self, *args, **kwargs):
            pass

        def verify(self):
            return case["lease_binding"]

    monkeypatch.setattr(cli, "StableHistoricalLeaseV1", Lease)
    monkeypatch.setattr(
        cli.grading, "grade_and_publish_r6_full_union_realized_v1",
        lambda **kwargs: (case["root"], case["root_identity"]),
    )
    monkeypatch.setattr(
        cli.grading,
        "validate_persisted_realized_grade_v1",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            grading.CorpusR6FullUnionRealizedGradingV1Error(
                "persisted realized-grade root canonical replay differs"
            )
        ),
    )
    with pytest.raises(
        cli.R6FullUnionRealizedGradeRunnerV1Error,
        match="canonical replay differs",
    ):
        cli.run_grade_cloud_v1(
            config=case["config"],
            panel_freeze_identity={},
            outcome_supply_completion_identity={},
            outcome_key_projection_identity={},
            realized_source_identity={},
            outcome_snapshot_identity={},
            expected_lease_identity=case["lease_identity"],
            storage_client=object(),
        )


def test_changed_lease_after_grade_blocks_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _final_case()
    _stub_preflight(monkeypatch, case)

    class Lease:
        def __init__(self, *args, **kwargs):
            self.calls = 0

        def verify(self):
            self.calls += 1
            if self.calls == 2:
                raise cli.R6FullUnionRealizedGradeRunnerV1Error(
                    "live historical-outcome lease identity changed"
                )
            return case["lease_binding"]

    monkeypatch.setattr(cli, "StableHistoricalLeaseV1", Lease)
    monkeypatch.setattr(
        cli.grading, "grade_and_publish_r6_full_union_realized_v1",
        lambda **kwargs: (case["root"], case["root_identity"]),
    )
    monkeypatch.setattr(
        cli.grading, "validate_persisted_realized_grade_v1",
        lambda *args, **kwargs: (
            case["root"], case["root_identity"],
            case["root"]["logical_grade_root"], [{} for _ in range(54)],
        ),
    )
    with pytest.raises(
        cli.R6FullUnionRealizedGradeRunnerV1Error,
        match="lease identity changed",
    ):
        cli.run_grade_cloud_v1(
            config=case["config"],
            panel_freeze_identity={},
            outcome_supply_completion_identity={},
            outcome_key_projection_identity={},
            realized_source_identity={},
            outcome_snapshot_identity={},
            expected_lease_identity=case["lease_identity"],
            storage_client=object(),
        )


def test_stdout_receipt_has_no_score_or_row_payload() -> None:
    case = _final_case()
    authority = case["authority"]
    completion = release.build_grade_completion_v1(
        config=case["config"],
        panel_freeze_identity=authority.panel_freeze_identity,
        outcome_supply_completion=authority.outcome_supply_completion,
        outcome_supply_completion_identity=(
            authority.outcome_supply_completion_identity
        ),
        actual_root_smoke_receipt=authority.actual_root_smoke_receipt,
        actual_root_smoke_receipt_identity=(
            authority.actual_root_smoke_receipt_identity
        ),
        historical_outcome_lease=authority.historical_lease_binding,
        outcome_key_projection=authority.outcome_key_projection,
        outcome_key_projection_identity=authority.outcome_key_projection_identity,
        realized_source=authority.realized_source,
        realized_source_identity=authority.realized_source_identity,
        outcome_snapshot=authority.outcome_snapshot,
        outcome_snapshot_identity=authority.outcome_snapshot_identity,
        persisted_grade_root=case["root"],
        persisted_grade_root_identity=case["root_identity"],
    )
    completion_identity = batch.object_identity_for_json(
        completion, uri=case["config"].completion_uri, generation="2"
    )
    cloud = cli.FullUnionRealizedGradeCloudResultV1(
        authority=authority,
        persisted_grade_root=case["root"],
        persisted_grade_root_identity=case["root_identity"],
        grade_completion=completion,
        grade_completion_identity=completion_identity,
        historical_lease_identity=case["lease_identity"],
    )
    serialized = release.canonical_json_bytes(
        cli._receipt_only(cloud)  # noqa: SLF001
    ).decode()
    for forbidden in (
        "realized_score", "maximum_score", "score_mean", "score_median",
        "lineup_ids", "union_score_rows", '"rows"',
    ):
        assert forbidden not in serialized
