"""Outcome-free tests for the R6 BigQuery server compile gate."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from google.cloud import bigquery

from nfl_dfs.research import corpus_realized_outcome_transport as registered


ROOT = Path(__file__).resolve().parents[1]
CODE_SHA = "a" * 40
IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/"
    "nfl-dfs/nfl-dfs@sha256:" + "b" * 64
)


def _load_cli():
    path = ROOT / "scripts/compile_corpus_r6_full_union_query_v1.py"
    spec = importlib.util.spec_from_file_location(
        "compile_corpus_r6_full_union_query_v1_test", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


class _FakeJob:
    def __init__(self, *, query: str, job_config, location: str) -> None:
        self.query = query
        self.location = location
        self.dry_run = job_config.dry_run
        self.use_legacy_sql = job_config.use_legacy_sql
        self.use_query_cache = job_config.use_query_cache
        self.query_parameters = job_config.query_parameters
        self.error_result = None
        self.errors = None
        self.statement_type = "SELECT"
        self.destination = None
        self.total_bytes_processed = 12345
        self.schema = [
            bigquery.SchemaField("season", "INTEGER"),
            bigquery.SchemaField("week", "INTEGER"),
            bigquery.SchemaField("source_kind", "STRING"),
            bigquery.SchemaField("source_key", "STRING"),
            bigquery.SchemaField("realized_score", "NUMERIC"),
        ]

    def result(self):  # pragma: no cover - must never be called
        raise AssertionError("compile gate attempted to read rows")

    def __iter__(self):  # pragma: no cover - must never be called
        raise AssertionError("compile gate attempted to iterate rows")


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.mutate = None

    def query(self, query: str, **kwargs):
        self.calls.append({"query": query, **kwargs})
        job = _FakeJob(
            query=query,
            job_config=kwargs["job_config"],
            location=kwargs["location"],
        )
        if self.mutate is not None:
            self.mutate(job)
        return job


def _run(client: _FakeClient | None = None):
    retained = client or _FakeClient()
    receipt = cli.compile_query_v1(
        config=cli.CompileConfigV1(
            project=cli.PROJECT,
            location=cli.LOCATION,
            code_sha=CODE_SHA,
            image=IMAGE,
        ),
        runtime_identity=_runtime_identity(),
        client_factory=lambda: retained,
        clock=lambda: datetime(2026, 8, 26, 19, 50, tzinfo=timezone.utc),
    )
    return receipt, retained


def _runtime_identity():
    return cli.RuntimeBuildIdentityV1(
        git_head=CODE_SHA,
        git_worktree_clean=True,
        sql_sha256=registered.AUTHORITATIVE_SCORE_SQL_SHA256,
        query_module_sha256="c" * 64,
        compile_script_sha256="d" * 64,
    )


def test_compile_gate_uses_exact_sql_and_never_claims_a_job_id_or_rows() -> None:
    receipt, client = _run()

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["query"] == registered.AUTHORITATIVE_SCORE_SQL
    assert call["location"] == cli.LOCATION
    assert call["retry"] is None
    assert call["job_retry"] is None
    assert "job_id" not in call
    config = call["job_config"]
    assert config.dry_run is True
    assert config.use_legacy_sql is False
    assert config.use_query_cache is False
    assert [value.name for value in config.query_parameters] == [
        "source_snapshot_at", "target_seasons", "skill_keys", "dst_keys"
    ]
    assert receipt["sql_sha256"] == registered.AUTHORITATIVE_SCORE_SQL_SHA256
    assert receipt["runtime_git_head"] == CODE_SHA
    assert receipt["runtime_git_worktree_clean"] is True
    assert receipt["query_module_sha256"] == "c" * 64
    assert receipt["compile_script_sha256"] == "d" * 64
    assert receipt["compiled"] is True
    assert receipt["dry_run"] is True
    assert "destination_materialized" not in receipt
    assert receipt["fixed_job_id_claimed"] is False
    assert receipt["query_executed"] is False
    assert receipt["rows_read"] == 0
    assert receipt["historical_outcome_lease_acquired"] is False
    assert receipt["lineup_scoring_performed"] is False
    body = dict(receipt)
    digest = body.pop("compile_receipt_sha256")
    assert digest == sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda job: setattr(job, "dry_run", False),
        lambda job: setattr(job, "error_result", {"reason": "invalidQuery"}),
        lambda job: setattr(job, "statement_type", "INSERT"),
        lambda job: setattr(job, "total_bytes_processed", None),
        lambda job: setattr(job.schema[4], "_properties", {
            "name": "realized_score", "type": "FLOAT", "mode": "NULLABLE"
        }),
    ],
)
def test_compile_gate_fails_closed_on_server_contract_drift(mutation) -> None:
    client = _FakeClient()
    client.mutate = mutation
    with pytest.raises(cli.R6QueryCompileError):
        _run(client)


def test_compile_gate_does_not_infer_materialization_from_destination() -> None:
    client = _FakeClient()
    client.mutate = lambda job: setattr(job, "destination", object())

    receipt, _ = _run(client)

    assert receipt["compiled"] is True
    assert "destination_materialized" not in receipt


def test_compile_receipt_write_is_create_only(tmp_path: Path) -> None:
    path = tmp_path / "compile.json"
    raw = b"{}\n"
    cli._write_create_only(path, raw)
    assert path.read_bytes() == raw
    with pytest.raises(cli.R6QueryCompileError):
        cli._write_create_only(path, raw)


def test_runtime_build_identity_proves_exact_clean_git_and_source_hashes() -> None:
    calls: list[tuple[tuple[str, ...], Path]] = []

    def run(argv, cwd):
        calls.append((tuple(argv), cwd))
        if argv[1] == "rev-parse":
            return CODE_SHA + "\n"
        return ""

    module_path = Path(registered.__file__).resolve()
    script_path = (
        ROOT / "scripts/compile_corpus_r6_full_union_query_v1.py"
    ).resolve()
    identity = cli.prove_runtime_build_identity_v1(
        config=cli.CompileConfigV1(
            project=cli.PROJECT,
            location=cli.LOCATION,
            code_sha=CODE_SHA,
            image=IMAGE,
        ),
        repo_root=ROOT,
        query_module_path=module_path,
        compile_script_path=script_path,
        git_runner=run,
    )

    assert calls == [
        (("git", "rev-parse", "--verify", "HEAD"), ROOT),
        (
            (
                "git", "status", "--porcelain=v1",
                "--untracked-files=all",
            ),
            ROOT,
        ),
    ]
    assert identity.git_head == CODE_SHA
    assert identity.git_worktree_clean is True
    assert identity.sql_sha256 == registered.AUTHORITATIVE_SCORE_SQL_SHA256
    assert identity.query_module_sha256 == sha256(
        module_path.read_bytes()
    ).hexdigest()
    assert identity.compile_script_sha256 == sha256(
        script_path.read_bytes()
    ).hexdigest()


@pytest.mark.parametrize(
    ("head", "status", "message"),
    [
        ("f" * 40 + "\n", "", "Git HEAD differs"),
        (CODE_SHA + "\n", "?? unexpected\n", "worktree is not clean"),
    ],
)
def test_runtime_build_identity_rejects_wrong_head_or_dirty_tree(
    head: str, status: str, message: str,
) -> None:
    def run(argv, _cwd):
        return head if argv[1] == "rev-parse" else status

    with pytest.raises(cli.R6QueryCompileError, match=message):
        cli.prove_runtime_build_identity_v1(
            config=cli.CompileConfigV1(
                project=cli.PROJECT,
                location=cli.LOCATION,
                code_sha=CODE_SHA,
                image=IMAGE,
            ),
            repo_root=ROOT,
            query_module_path=Path(registered.__file__).resolve(),
            compile_script_path=(
                ROOT / "scripts/compile_corpus_r6_full_union_query_v1.py"
            ),
            git_runner=run,
        )


class _ObjectExists(RuntimeError):
    pass


class _FakeBlob:
    def __init__(
        self,
        client,
        bucket: str,
        name: str,
        generation: int | None,
    ) -> None:
        self.client = client
        self.bucket = bucket
        self.name = name
        self.requested_generation = generation
        self.generation = generation

    @property
    def key(self):
        return self.bucket, self.name

    def upload_from_string(
        self, raw: bytes, *, content_type: str, if_generation_match: int,
    ) -> None:
        self.client.calls.append((
            "upload", self.key, raw, content_type, if_generation_match,
        ))
        assert content_type == "application/json"
        assert if_generation_match == 0
        if self.key in self.client.backend:
            raise _ObjectExists("already exists")
        generation = self.client.next_generation
        self.client.next_generation += 1
        self.client.backend[self.key] = (generation, raw)
        self.generation = generation

    def reload(self, *, if_generation_match: int) -> None:
        self.client.calls.append((
            "reload", self.key, self.requested_generation,
            if_generation_match,
        ))
        generation, _ = self.client.backend[self.key]
        assert self.requested_generation == generation
        assert if_generation_match == generation
        self.generation = generation

    def download_as_bytes(self, *, if_generation_match: int) -> bytes:
        self.client.calls.append((
            "download", self.key, self.requested_generation,
            if_generation_match,
        ))
        generation, raw = self.client.backend[self.key]
        assert self.requested_generation == generation
        assert if_generation_match == generation
        return (
            self.client.reopened_raw
            if self.client.reopened_raw is not None
            else raw
        )


class _FakeBucket:
    def __init__(self, client, name: str) -> None:
        self.client = client
        self.name = name

    def blob(self, name: str, generation: int | None = None):
        return _FakeBlob(self.client, self.name, name, generation)


class _FakeStorageClient:
    def __init__(self) -> None:
        self.backend: dict[tuple[str, str], tuple[int, bytes]] = {}
        self.calls: list[tuple[object, ...]] = []
        self.next_generation = 73
        self.reopened_raw: bytes | None = None

    def bucket(self, name: str):
        return _FakeBucket(self, name)


RUN_ID = "20260826-foundry-v12-r6-full-union-realized-v2"
RECEIPT_URI = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    f"corpus-r6-full-union-realized/{RUN_ID}/"
    "query-compile-receipt.json"
)


def _publish(
    tmp_path: Path,
    *,
    storage_client: _FakeStorageClient | None = None,
    receipt_uri: str | None = RECEIPT_URI,
):
    bq_client = _FakeClient()
    retained_storage = storage_client or _FakeStorageClient()
    publication = cli.compile_and_publish_query_v1(
        config=cli.CompileConfigV1(
            project=cli.PROJECT,
            location=cli.LOCATION,
            code_sha=CODE_SHA,
            image=IMAGE,
        ),
        runtime_identity=_runtime_identity(),
        receipt_path=tmp_path / "compile.json",
        receipt_uri=receipt_uri,
        client_factory=lambda: bq_client,
        storage_client=retained_storage,
        clock=lambda: datetime(
            2026, 8, 26, 19, 50, tzinfo=timezone.utc
        ),
    )
    return publication, bq_client, retained_storage


@pytest.mark.parametrize(
    "uri",
    [
        "gs://wrong-bucket/research/corpus-r6-full-union-realized/"
        f"{RUN_ID}/query-compile-receipt.json",
        "gs://nfl-predictions-503414-corpus-retrieval/research/other/"
        f"{RUN_ID}/query-compile-receipt.json",
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-full-union-realized/short/query-compile-receipt.json",
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        f"corpus-r6-full-union-realized/{RUN_ID}/other.json",
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        f"corpus-r6-full-union-realized/{RUN_ID}/../"
        "query-compile-receipt.json",
    ],
)
def test_compile_publication_rejects_wrong_uri_before_bigquery(
    tmp_path: Path, uri: str,
) -> None:
    bq_client = _FakeClient()
    with pytest.raises(cli.R6QueryCompileError, match="receipt URI differs"):
        cli.compile_and_publish_query_v1(
            config=cli.CompileConfigV1(
                project=cli.PROJECT,
                location=cli.LOCATION,
                code_sha=CODE_SHA,
                image=IMAGE,
            ),
            runtime_identity=_runtime_identity(),
            receipt_path=tmp_path / "must-not-exist.json",
            receipt_uri=uri,
            client_factory=lambda: bq_client,
            storage_client=_FakeStorageClient(),
        )
    assert bq_client.calls == []
    assert not (tmp_path / "must-not-exist.json").exists()


def test_compile_publication_is_create_once_and_byte_identical(
    tmp_path: Path,
) -> None:
    publication, bq_client, storage_client = _publish(tmp_path)
    key = (
        "nfl-predictions-503414-corpus-retrieval",
        f"research/corpus-r6-full-union-realized/{RUN_ID}/"
        "query-compile-receipt.json",
    )
    generation, remote_raw = storage_client.backend[key]

    assert len(bq_client.calls) == 1
    assert publication.receipt_raw == (tmp_path / "compile.json").read_bytes()
    assert publication.receipt_raw == remote_raw
    assert publication.object_identity == {
        "uri": RECEIPT_URI,
        "generation": str(generation),
        "sha256": sha256(remote_raw).hexdigest(),
        "bytes": len(remote_raw),
    }
    uploads = [call for call in storage_client.calls if call[0] == "upload"]
    downloads = [
        call for call in storage_client.calls if call[0] == "download"
    ]
    assert len(uploads) == len(downloads) == 1
    assert uploads[0][4] == 0
    assert downloads[0][2] == downloads[0][3] == generation


def test_compile_publication_rejects_preexisting_remote_object(
    tmp_path: Path,
) -> None:
    storage_client = _FakeStorageClient()
    key = (
        "nfl-predictions-503414-corpus-retrieval",
        f"research/corpus-r6-full-union-realized/{RUN_ID}/"
        "query-compile-receipt.json",
    )
    storage_client.backend[key] = (19, b"preexisting\n")

    with pytest.raises(
        cli.R6QueryCompileError, match="create-once publication failed"
    ):
        _publish(tmp_path, storage_client=storage_client)

    assert storage_client.backend[key] == (19, b"preexisting\n")
    assert (tmp_path / "compile.json").is_file()


def test_compile_publication_rejects_nonidentical_exact_reopen(
    tmp_path: Path,
) -> None:
    storage_client = _FakeStorageClient()
    storage_client.reopened_raw = b"forged\n"

    with pytest.raises(cli.R6QueryCompileError, match="published bytes differ"):
        _publish(tmp_path, storage_client=storage_client)


def test_cli_prints_exact_gcs_identity_when_uri_is_requested(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    identity = {
        "uri": RECEIPT_URI,
        "generation": "73",
        "sha256": "e" * 64,
        "bytes": 123,
    }
    monkeypatch.setenv(cli.ENABLED_ENV, "1")
    monkeypatch.setattr(sys, "argv", [
        "compile", "--execute", "--code-sha", CODE_SHA,
        "--image", IMAGE, "--receipt", str(tmp_path / "compile.json"),
        "--receipt-uri", RECEIPT_URI,
    ])
    monkeypatch.setattr(
        cli,
        "prove_runtime_build_identity_v1",
        lambda **_kwargs: _runtime_identity(),
    )
    monkeypatch.setattr(
        cli,
        "compile_and_publish_query_v1",
        lambda **_kwargs: cli.CompilePublicationV1(
            receipt={"compiled": True},
            receipt_raw=b'{"compiled":true}\n',
            object_identity=identity,
        ),
    )

    assert cli.main() == 0
    assert capsys.readouterr().out.encode() == cli.canonical_bytes(identity)


def test_cli_is_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(cli.ENABLED_ENV, raising=False)
    monkeypatch.setattr(sys, "argv", [
        "compile", "--code-sha", CODE_SHA, "--image", IMAGE,
        "--receipt", "ignored.json",
    ])
    with pytest.raises(cli.R6QueryCompileError, match="requires --execute"):
        cli.main()
