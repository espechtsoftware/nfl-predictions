#!/usr/bin/env python3
"""Prepare or execute the one fixed 54-task R6 hard-230 batch."""

from __future__ import annotations

from collections.abc import Mapping
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import (
    corpus_extreme_tail_hard230_r6_cloud_entrypoint_v1 as entrypoint,
)


class RunHard230R6CloudV1Error(RuntimeError):
    """The fixed hard-230 cloud executable failed closed."""


def _fail(message: str) -> None:
    raise RunHard230R6CloudV1Error(message)


def _canonical(value: object) -> bytes:
    return legal.canonical_json_bytes(value)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunHard230R6CloudV1Error(f"{label} is not UTF-8 JSON") from exc
    item = _mapping(value, label=label)
    if _canonical(item) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return entrypoint._identity(value, label=label)
    except entrypoint.Hard230R6CloudEntrypointV1Error as exc:
        raise RunHard230R6CloudV1Error(str(exc)) from exc


class GCSExactTransportV1:
    """Fixed-project exact reads and create-once equal-byte recovery."""

    def __init__(self) -> None:
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import storage
        except Exception as exc:  # pragma: no cover - cloud dependency
            raise RuntimeError("google-cloud-storage is required") from exc
        self._client = storage.Client(
            project=entrypoint.FIXED_GCP_PROJECT,
            client_options=ClientOptions(
                api_endpoint=entrypoint.FIXED_STORAGE_ENDPOINT
            ),
        )
        self._cache: dict[tuple[str, str, str, int], bytes] = {}

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if not uri.startswith("gs://"):
            _fail("GCS URI must use gs://")
        bucket, separator, name = uri[5:].partition("/")
        if not separator or not bucket or not name:
            _fail("GCS URI is malformed")
        return bucket, name

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        identity = _identity(identity_value, label="GCS exact read")
        key = (
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )
        if key in self._cache:
            return self._cache[key]
        bucket_name, object_name = self._parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        blob = self._client.bucket(bucket_name).blob(
            object_name, generation=generation
        )
        raw = blob.download_as_bytes(if_generation_match=generation, retry=None)
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("generation-exact GCS bytes differ")
        self._cache[key] = raw
        return raw

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if type(raw) is not bytes or not raw:
            _fail("create-once publication bytes differ")
        bucket_name, object_name = self._parts(uri)
        blob = self._client.bucket(bucket_name).blob(object_name)
        content_type = (
            "application/zlib" if uri.endswith(".zlib") else "application/json"
        )
        try:
            blob.upload_from_string(
                raw,
                content_type=content_type,
                if_generation_match=0,
                retry=None,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ not in {"Conflict", "PreconditionFailed"}:
                raise
            current = self._client.bucket(bucket_name).blob(object_name)
            current.reload(retry=None)
            if current.generation is None:
                _fail("create-once collision lacks an existing generation")
            identity = {
                "uri": uri,
                "generation": str(current.generation),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
            if self.read_exact(identity) != raw:
                _fail("create-once collision bytes differ")
            return identity
        if blob.generation is None:
            _fail("create-once upload lacks a generation")
        identity = {
            "uri": uri,
            "generation": str(blob.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if self.read_exact(identity) != raw:
            _fail("create-once publication exact reopen differs")
        return identity


def _parse_identity_environment(value: str, *, label: str) -> dict[str, object]:
    if not value or len(value.encode("utf-8")) > 2_048:
        _fail(f"{label} is absent or oversized")
    return _identity(
        _strict_json(value.encode("utf-8"), label=label), label=label
    )


def _execute_cloud_task(store: GCSExactTransportV1) -> dict[str, object]:
    if os.environ.get(entrypoint.ENABLE_ENV) != "1":
        _fail("hard230 R6 execution is not explicitly enabled")
    manifest_identity = _parse_identity_environment(
        os.environ.get(entrypoint.MANIFEST_IDENTITY_ENV, ""),
        label="hard230 manifest identity environment",
    )
    try:
        task_index = int(os.environ.get("CLOUD_RUN_TASK_INDEX", ""))
        task_count = int(os.environ.get("CLOUD_RUN_TASK_COUNT", ""))
        task_attempt = int(os.environ.get("CLOUD_RUN_TASK_ATTEMPT", ""))
    except ValueError as exc:
        raise RunHard230R6CloudV1Error(
            "Cloud Run task environment is not exact integer text"
        ) from exc
    if task_count != entrypoint.TASK_COUNT or task_attempt != 0:
        _fail("Cloud Run task count/attempt differs from the no-retry 54-task law")
    manifest, _, _ = entrypoint._open_manifest(
        manifest_identity=manifest_identity, read_exact=store.read_exact
    )
    if (
        os.environ.get("CODE_SHA") != manifest["source_commit_sha"]
        or os.environ.get("R6_RUNTIME_IMAGE_DIGEST")
        != manifest["immutable_image_digest"]
        or os.environ.get("CLOUD_RUN_JOB") != manifest["reused_job_name"]
    ):
        _fail("Cloud Run code/image/job environment differs from the manifest")
    result = entrypoint.execute_manifest_task_v1(
        manifest_identity=manifest_identity,
        task_index=task_index,
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    return {
        "schema_version": "hard230-r6-cloud-task-completion/v1",
        "task_index": task_index,
        "slate_id": result.task_result["slate_id"],
        "task_result_identity": result.task_result_identity,
        "task_result_sha256": result.task_result["task_result_sha256"],
        "complete": True,
    }


def _prepare(request_file: Path, store: GCSExactTransportV1) -> dict[str, object]:
    request = _strict_json(request_file.read_bytes(), label="preparation request")
    expected = {
        "panel_index_identity", "later_source_freeze_identity",
        "optimizer_source_identity", "terminal_build_receipt_identity",
        "output_prefix", "source_commit_sha", "immutable_image_digest",
        "reused_job_name",
    }
    if set(request) != expected:
        _fail("preparation request fields differ")
    return entrypoint.prepare_54_task_manifest_v1(
        panel_index_identity=request["panel_index_identity"],
        later_source_freeze_identity=request["later_source_freeze_identity"],
        optimizer_source_identity=request["optimizer_source_identity"],
        terminal_build_receipt_identity=request[
            "terminal_build_receipt_identity"
        ],
        output_prefix=str(request["output_prefix"]),
        source_commit_sha=str(request["source_commit_sha"]),
        immutable_image_digest=str(request["immutable_image_digest"]),
        reused_job_name=str(request["reused_job_name"]),
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or execute the fixed 54-task R6 hard230 batch"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--request-file", type=Path, required=True)
    prepare.add_argument("--output-file", type=Path, required=True)
    sub.add_parser("execute-task")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    store = GCSExactTransportV1()
    if args.command == "prepare":
        result = _prepare(args.request_file, store)
        raw = _canonical(result)
        if args.output_file.exists():
            _fail("preparation output file already exists")
        args.output_file.write_bytes(raw)
        print(raw.decode("utf-8"))
        return 0
    if args.command == "execute-task":
        raw = _canonical(_execute_cloud_task(store))
        sys.stdout.buffer.write(raw + b"\n")
        return 0
    _fail("unknown command")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RunHard230R6CloudV1Error, entrypoint.Hard230R6CloudEntrypointV1Error) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
