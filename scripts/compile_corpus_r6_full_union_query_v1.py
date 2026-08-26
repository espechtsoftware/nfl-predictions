#!/usr/bin/env python3
"""Compile the registered R6 outcome SQL without executing or reading rows."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Callable, Mapping, Sequence

from nfl_dfs.research import corpus_realized_outcome_transport as registered


ENABLED_ENV = "R6_FULL_UNION_QUERY_COMPILE_ENABLED"
SCHEMA_VERSION = "r6-full-union-query-compile-receipt/v1"
PROJECT = "nfl-predictions-503414"
LOCATION = "US"
_CODE_SHA = re.compile(r"[0-9a-f]{40}")
_IMAGE = re.compile(
    r"us-central1-docker\.pkg\.dev/nfl-predictions-503414/"
    r"nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}"
)
_SHA256 = re.compile(r"[0-9a-f]{64}")
_RUN_ID = re.compile(r"[a-z0-9][a-z0-9-]{7,80}")
_RECEIPT_ROOT = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-full-union-realized"
)


class R6QueryCompileError(RuntimeError):
    """Raised when the outcome-free compile gate differs."""


@dataclass(frozen=True)
class CompileConfigV1:
    project: str
    location: str
    code_sha: str
    image: str


@dataclass(frozen=True)
class RuntimeBuildIdentityV1:
    git_head: str
    git_worktree_clean: bool
    sql_sha256: str
    query_module_sha256: str
    compile_script_sha256: str


@dataclass(frozen=True)
class CompilePublicationV1:
    receipt: Mapping[str, object]
    receipt_raw: bytes
    object_identity: Mapping[str, object] | None


GitRunner = Callable[[Sequence[str], Path], str]


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _fail(message: str) -> None:
    raise R6QueryCompileError(message)


def _validate_config(config: CompileConfigV1) -> CompileConfigV1:
    if (
        not isinstance(config, CompileConfigV1)
        or config.project != PROJECT
        or config.location != LOCATION
        or _CODE_SHA.fullmatch(config.code_sha) is None
        or _IMAGE.fullmatch(config.image) is None
    ):
        _fail("R6 query compile identity differs")
    return config


def _file_sha256(path: Path, *, label: str) -> str:
    try:
        raw = path.read_bytes()
    except Exception as exc:
        raise R6QueryCompileError(f"R6 query compile {label} read failed") from exc
    if not raw:
        _fail(f"R6 query compile {label} is empty")
    return sha256(raw).hexdigest()


def _default_git_runner(argv: Sequence[str], cwd: Path) -> str:
    try:
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        raise R6QueryCompileError("R6 query compile git proof failed") from exc
    if completed.returncode != 0:
        _fail("R6 query compile git proof failed")
    return completed.stdout


def prove_runtime_build_identity_v1(
    *,
    config: CompileConfigV1,
    repo_root: Path | None = None,
    query_module_path: Path | None = None,
    compile_script_path: Path | None = None,
    git_runner: GitRunner = _default_git_runner,
) -> RuntimeBuildIdentityV1:
    """Prove that this process is running the clean, requested Git build."""
    retained = _validate_config(config)
    root = (
        repo_root.resolve()
        if repo_root is not None
        else Path(__file__).resolve().parents[1]
    )
    if not root.is_dir() or not callable(git_runner):
        _fail("R6 query compile repository proof differs")
    try:
        head_raw = git_runner(
            ("git", "rev-parse", "--verify", "HEAD"), root
        )
        status_raw = git_runner(
            (
                "git", "status", "--porcelain=v1",
                "--untracked-files=all",
            ),
            root,
        )
    except R6QueryCompileError:
        raise
    except Exception as exc:
        raise R6QueryCompileError("R6 query compile git proof failed") from exc
    if head_raw not in {retained.code_sha, retained.code_sha + "\n"}:
        _fail("R6 query compile runtime Git HEAD differs")
    if status_raw != "":
        _fail("R6 query compile runtime Git worktree is not clean")

    module_path = (
        query_module_path.resolve()
        if query_module_path is not None
        else Path(str(registered.__file__)).resolve()
    )
    script_path = (
        compile_script_path.resolve()
        if compile_script_path is not None
        else Path(__file__).resolve()
    )
    try:
        module_path.relative_to(root)
        script_path.relative_to(root)
    except ValueError as exc:
        raise R6QueryCompileError(
            "R6 query compile runtime source escaped the repository"
        ) from exc
    sql_sha = sha256(
        registered.AUTHORITATIVE_SCORE_SQL.encode("utf-8")
    ).hexdigest()
    if sql_sha != registered.AUTHORITATIVE_SCORE_SQL_SHA256:
        _fail("R6 query compile registered SQL hash differs")
    return RuntimeBuildIdentityV1(
        git_head=retained.code_sha,
        git_worktree_clean=True,
        sql_sha256=sql_sha,
        query_module_sha256=_file_sha256(
            module_path, label="query module"
        ),
        compile_script_sha256=_file_sha256(
            script_path, label="compile script"
        ),
    )


def _validate_runtime_identity(
    value: RuntimeBuildIdentityV1, *, config: CompileConfigV1,
) -> RuntimeBuildIdentityV1:
    if (
        not isinstance(value, RuntimeBuildIdentityV1)
        or value.git_head != config.code_sha
        or value.git_worktree_clean is not True
        or value.sql_sha256 != registered.AUTHORITATIVE_SCORE_SQL_SHA256
        or _SHA256.fullmatch(value.query_module_sha256) is None
        or _SHA256.fullmatch(value.compile_script_sha256) is None
    ):
        _fail("R6 query compile runtime build identity differs")
    return value


def _field_payload(field: object) -> dict[str, str]:
    name = getattr(field, "name", None)
    field_type = getattr(field, "field_type", None)
    mode = getattr(field, "mode", None)
    if not all(isinstance(value, str) and value for value in (
        name, field_type, mode
    )):
        _fail("R6 query compile output schema differs")
    return {"name": name, "field_type": field_type, "mode": mode}


def _api(values: Sequence[object]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for value in values:
        method = getattr(value, "to_api_repr", None)
        if not callable(method):
            _fail("R6 query compile parameter representation differs")
        raw = method()
        if not isinstance(raw, Mapping):
            _fail("R6 query compile parameter representation differs")
        result.append(dict(raw))
    return result


def compile_query_v1(
    *,
    config: CompileConfigV1,
    runtime_identity: RuntimeBuildIdentityV1,
    client_factory: Callable[[], object] | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, object]:
    """Submit one dry-run compile request and return its canonical receipt."""
    retained = _validate_config(config)
    runtime = _validate_runtime_identity(
        runtime_identity, config=retained
    )
    from google.cloud import bigquery

    now = clock()
    if not isinstance(now, datetime) or now.tzinfo is None:
        _fail("R6 query compile clock differs")
    compiled_at = now.astimezone(timezone.utc)
    snapshot = compiled_at - timedelta(minutes=1)
    parameters = [
        bigquery.ScalarQueryParameter(
            "source_snapshot_at", "TIMESTAMP", snapshot
        ),
        bigquery.ArrayQueryParameter("target_seasons", "INT64", [2023]),
        bigquery.ArrayQueryParameter(
            "skill_keys", "STRING", ["2023|01|__compile_probe__"]
        ),
        bigquery.ArrayQueryParameter(
            "dst_keys", "STRING", ["2023|01|ZZZ"]
        ),
    ]
    job_config = bigquery.QueryJobConfig(
        dry_run=True,
        query_parameters=parameters,
        use_legacy_sql=False,
        use_query_cache=False,
    )
    try:
        client = (
            client_factory() if client_factory is not None
            else bigquery.Client(project=retained.project)
        )
        job = client.query(  # type: ignore[attr-defined]
            registered.AUTHORITATIVE_SCORE_SQL,
            job_config=job_config,
            location=retained.location,
            retry=None,
            job_retry=None,
        )
    except Exception as exc:
        raise R6QueryCompileError("R6 query server compile failed") from exc

    expected_schema = [
        {"name": "season", "field_type": "INTEGER", "mode": "NULLABLE"},
        {"name": "week", "field_type": "INTEGER", "mode": "NULLABLE"},
        {"name": "source_kind", "field_type": "STRING", "mode": "NULLABLE"},
        {"name": "source_key", "field_type": "STRING", "mode": "NULLABLE"},
        {"name": "realized_score", "field_type": "NUMERIC", "mode": "NULLABLE"},
    ]
    observed_parameters = getattr(job, "query_parameters", None)
    observed_schema = getattr(job, "schema", None)
    total_bytes = getattr(job, "total_bytes_processed", None)
    errors = getattr(job, "errors", None)
    parameter_sequence = (
        isinstance(observed_parameters, Sequence)
        and not isinstance(observed_parameters, (str, bytes))
    )
    schema_sequence = (
        isinstance(observed_schema, Sequence)
        and not isinstance(observed_schema, (str, bytes))
    )
    observed_schema_payload = (
        [_field_payload(field) for field in observed_schema]
        if schema_sequence else None
    )
    checks = {
        "query": getattr(job, "query", None)
        == registered.AUTHORITATIVE_SCORE_SQL,
        "location": getattr(job, "location", None) == retained.location,
        "dry_run": getattr(job, "dry_run", None) is True,
        "legacy_sql": getattr(job, "use_legacy_sql", None) is False,
        "query_cache": getattr(job, "use_query_cache", None) is False,
        "error_result": getattr(job, "error_result", None) is None,
        "errors": errors in (None, []),
        "statement_type": getattr(job, "statement_type", None) == "SELECT",
        "parameters": parameter_sequence
        and _api(observed_parameters) == _api(parameters),
        "schema": observed_schema_payload == expected_schema,
        "total_bytes": type(total_bytes) is int and total_bytes >= 0,
    }
    failed = sorted(name for name, passed in checks.items() if passed is not True)
    if failed:
        _fail("R6 query server compile result differs: " + ",".join(failed))

    parameter_contract = [
        {"name": "source_snapshot_at", "type": "TIMESTAMP", "array": False},
        {"name": "target_seasons", "type": "INT64", "array": True},
        {"name": "skill_keys", "type": "STRING", "array": True},
        {"name": "dst_keys", "type": "STRING", "array": True},
    ]
    body: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "project": retained.project,
        "location": retained.location,
        "code_sha": retained.code_sha,
        "image": retained.image,
        "runtime_git_head": runtime.git_head,
        "runtime_git_worktree_clean": runtime.git_worktree_clean,
        "compiled_at": compiled_at.isoformat(),
        "source_snapshot_at": snapshot.isoformat(),
        "sql_sha256": runtime.sql_sha256,
        "query_module_sha256": runtime.query_module_sha256,
        "compile_script_sha256": runtime.compile_script_sha256,
        "parameter_contract": parameter_contract,
        "parameter_contract_sha256": sha256(
            json.dumps(
                parameter_contract, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest(),
        "output_schema": expected_schema,
        "total_bytes_processed_estimate": total_bytes,
        "compiled": True,
        "dry_run": True,
        "fixed_job_id_claimed": False,
        "query_executed": False,
        "rows_read": 0,
        "historical_outcome_lease_acquired": False,
        "uses_realized_outcome_rows": False,
        "lineup_scoring_performed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    body["compile_receipt_sha256"] = sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return body


def _write_create_only(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise R6QueryCompileError("R6 query compile receipt already exists") from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _validate_receipt_uri(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail("R6 query compile receipt URI differs")
    prefix = _RECEIPT_ROOT + "/"
    suffix = "/query-compile-receipt.json"
    if not value.startswith(prefix) or not value.endswith(suffix):
        _fail("R6 query compile receipt URI differs")
    run_id = value[len(prefix):-len(suffix)]
    if _RUN_ID.fullmatch(run_id) is None:
        _fail("R6 query compile receipt URI differs")
    return value


def _gcs_parts(uri: str) -> tuple[str, str]:
    retained = _validate_receipt_uri(uri)
    if retained is None:  # pragma: no cover - uri is statically nonoptional
        raise AssertionError("validated receipt URI became absent")
    bucket, name = retained[5:].split("/", 1)
    if not bucket or not name:
        _fail("R6 query compile receipt URI differs")
    return bucket, name


def _generation(value: object) -> int:
    if isinstance(value, bool):
        _fail("R6 query compile publication generation differs")
    try:
        generation = int(str(value))
    except (TypeError, ValueError) as exc:
        raise R6QueryCompileError(
            "R6 query compile publication generation differs"
        ) from exc
    if generation <= 0:
        _fail("R6 query compile publication generation differs")
    return generation


def _publish_create_once(
    storage_client: object, *, uri: str, raw: bytes,
) -> dict[str, object]:
    """Create and exact-generation reopen one canonical receipt object."""
    if type(raw) is not bytes or not raw:
        _fail("R6 query compile publication bytes differ")
    bucket_name, object_name = _gcs_parts(uri)
    try:
        blob = storage_client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
            object_name
        )
        blob.upload_from_string(
            raw,
            content_type="application/json",
            if_generation_match=0,
        )
    except Exception as exc:
        raise R6QueryCompileError(
            "R6 query compile create-once publication failed"
        ) from exc
    generation = _generation(getattr(blob, "generation", None))
    try:
        pinned = storage_client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
            object_name, generation=generation
        )
        pinned.reload(if_generation_match=generation)
        reopened = pinned.download_as_bytes(
            if_generation_match=generation
        )
    except Exception as exc:
        raise R6QueryCompileError(
            "R6 query compile exact publication reopen failed"
        ) from exc
    if (
        type(reopened) is not bytes
        or reopened != raw
        or _generation(getattr(pinned, "generation", None)) != generation
    ):
        _fail("R6 query compile published bytes differ")
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(reopened).hexdigest(),
        "bytes": len(reopened),
    }


def compile_and_publish_query_v1(
    *,
    config: CompileConfigV1,
    runtime_identity: RuntimeBuildIdentityV1,
    receipt_path: Path,
    receipt_uri: str | None = None,
    client_factory: Callable[[], object] | None = None,
    storage_client: object | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> CompilePublicationV1:
    """Compile, retain locally, and optionally create the exact GCS bytes."""
    retained = _validate_config(config)
    uri = _validate_receipt_uri(receipt_uri)
    if not isinstance(receipt_path, Path):
        _fail("R6 query compile local receipt path differs")
    receipt = compile_query_v1(
        config=retained,
        runtime_identity=runtime_identity,
        client_factory=client_factory,
        clock=clock,
    )
    raw = canonical_bytes(receipt)
    _write_create_only(receipt_path, raw)
    identity: Mapping[str, object] | None = None
    if uri is not None:
        client = storage_client
        if client is None:
            try:
                from google.cloud import storage

                client = storage.Client(project=retained.project)
            except Exception as exc:
                raise R6QueryCompileError(
                    "R6 query compile storage client construction failed"
                ) from exc
        identity = _publish_create_once(client, uri=uri, raw=raw)
    return CompilePublicationV1(
        receipt=receipt,
        receipt_raw=raw,
        object_identity=identity,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--location", default=LOCATION)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--receipt-uri")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.execute is not True or os.environ.get(ENABLED_ENV) != "1":
        raise R6QueryCompileError(
            "R6 query compile requires --execute and exact enablement"
        )
    config = CompileConfigV1(
        project=args.project,
        location=args.location,
        code_sha=args.code_sha,
        image=args.image,
    )
    receipt_uri = _validate_receipt_uri(args.receipt_uri)
    runtime_identity = prove_runtime_build_identity_v1(config=config)
    publication = compile_and_publish_query_v1(
        config=config,
        runtime_identity=runtime_identity,
        receipt_path=args.receipt,
        receipt_uri=receipt_uri,
    )
    output = (
        publication.object_identity
        if publication.object_identity is not None
        else publication.receipt
    )
    print(canonical_bytes(output).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
