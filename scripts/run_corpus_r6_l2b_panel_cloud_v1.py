#!/usr/bin/env python3
"""Prepare, execute, or finalize the fixed 54-task R6 L2b panel."""

from __future__ import annotations

from collections.abc import Mapping
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import corpus_r6_l2b_panel_cloud_v1 as panel


class RunCorpusR6L2BPanelCloudV1Error(RuntimeError):
    """The fixed L2b cloud command failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6L2BPanelCloudV1Error(message)


def _canonical(value: object) -> bytes:
    return legal.canonical_json_bytes(value)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunCorpusR6L2BPanelCloudV1Error(
            f"{label} is not UTF-8 JSON"
        ) from exc
    item = _mapping(value, label=label)
    if _canonical(item) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return panel._identity(value, label=label)
    except panel.CorpusR6L2BPanelCloudV1Error as exc:
        raise RunCorpusR6L2BPanelCloudV1Error(str(exc)) from exc


class GCSExactTransportV1:
    """Fixed-project exact reads plus create-once equal-byte recovery."""

    def __init__(self) -> None:
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import storage
        except Exception as exc:  # pragma: no cover - cloud dependency
            raise RuntimeError("google-cloud-storage is required") from exc
        self._client = storage.Client(
            project=panel.FIXED_GCP_PROJECT,
            client_options=ClientOptions(
                api_endpoint=panel.FIXED_STORAGE_ENDPOINT
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
        raw = blob.download_as_bytes(
            if_generation_match=generation, retry=None
        )
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
            "application/octet-stream" if uri.endswith(".npz")
            else "application/json"
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
            _fail("create-once publication lacks a generation")
        identity = {
            "uri": uri,
            "generation": str(blob.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if self.read_exact(identity) != raw:
            _fail("create-once publication exact reopen differs")
        return identity


def _identity_environment(value: str, *, label: str) -> dict[str, object]:
    if not value or len(value.encode("utf-8")) > 2_048:
        _fail(f"{label} is absent or oversized")
    return _identity(
        _strict_json(value.encode("utf-8"), label=label), label=label
    )


def _prepare(request_file: Path, store: GCSExactTransportV1) -> dict[str, object]:
    request = _strict_json(request_file.read_bytes(), label="preparation request")
    expected = {
        "later_source_freeze_identity", "calibration_release_identity",
        "pit_target_panel_identity", "terminal_build_receipt_identity",
        "output_prefix", "source_commit_sha", "immutable_image_digest",
        "reused_job_name", "reused_job_uid",
    }
    if set(request) != expected:
        _fail("preparation request fields differ")
    return panel.prepare_54_task_manifest_v1(
        later_source_freeze_identity=request["later_source_freeze_identity"],
        calibration_release_identity=request["calibration_release_identity"],
        pit_target_panel_identity=request["pit_target_panel_identity"],
        terminal_build_receipt_identity=request[
            "terminal_build_receipt_identity"
        ],
        output_prefix=str(request["output_prefix"]),
        source_commit_sha=str(request["source_commit_sha"]),
        immutable_image_digest=str(request["immutable_image_digest"]),
        reused_job_name=str(request["reused_job_name"]),
        reused_job_uid=str(request["reused_job_uid"]),
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )


def _execute_task(store: GCSExactTransportV1) -> dict[str, object]:
    if os.environ.get(panel.ENABLE_ENV) != "1":
        _fail("L2b panel execution is not explicitly enabled")
    manifest_identity = _identity_environment(
        os.environ.get(panel.MANIFEST_IDENTITY_ENV, ""),
        label="L2b manifest identity environment",
    )
    try:
        task_index = int(os.environ.get("CLOUD_RUN_TASK_INDEX", ""))
        task_count = int(os.environ.get("CLOUD_RUN_TASK_COUNT", ""))
        task_attempt = int(os.environ.get("CLOUD_RUN_TASK_ATTEMPT", ""))
    except ValueError as exc:
        raise RunCorpusR6L2BPanelCloudV1Error(
            "Cloud Run task environment is not exact integer text"
        ) from exc
    if task_count != panel.TASK_COUNT or task_attempt != 0:
        _fail("Cloud Run task count/attempt differs from the no-retry law")
    manifest, _ = panel._open_manifest(
        manifest_identity=manifest_identity, read_exact=store.read_exact
    )
    if (
        os.environ.get("CODE_SHA") != manifest["source_commit_sha"]
        or os.environ.get("R6_RUNTIME_IMAGE_DIGEST")
        != manifest["immutable_image_digest"]
        or os.environ.get(panel.REUSED_JOB_UID_ENV)
        != manifest["reused_job_uid"]
    ):
        _fail("Cloud Run code/image/job environment differs from the manifest")
    result = panel.execute_manifest_task_v1(
        manifest_identity=manifest_identity,
        task_index=task_index,
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    return {
        "schema_version": "corpus-r6-l2b-cloud-task-completion/v1",
        "task_index": task_index,
        "slate_id": result.task_result["slate_id"],
        "task_result_identity": result.task_result_identity,
        "task_result_sha256": result.task_result["task_result_sha256"],
        "complete": True,
    }


def _finalize(request_file: Path, store: GCSExactTransportV1) -> dict[str, object]:
    request = _strict_json(request_file.read_bytes(), label="finalization request")
    if set(request) != {"manifest_identity", "task_result_identities"}:
        _fail("finalization request fields differ")
    identities = request["task_result_identities"]
    if isinstance(identities, (str, bytes)) or not isinstance(identities, list):
        _fail("finalization task identities must be one ordered array")
    return panel.finalize_panel_root_v1(
        manifest_identity=request["manifest_identity"],
        task_result_identities=identities,
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )


def _write_create_once(path: Path, value: Mapping[str, object]) -> None:
    raw = _canonical(value)
    if not path.is_absolute() or not path.parent.is_dir():
        _fail("local output must be a new file in an existing directory")
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except FileExistsError as exc:
        raise RunCorpusR6L2BPanelCloudV1Error(
            "local output already exists; create-once write refused"
        ) from exc
    except OSError as exc:
        raise RunCorpusR6L2BPanelCloudV1Error(
            "create-once local output write failed"
        ) from exc
    sys.stdout.buffer.write(raw + b"\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--request-file", type=Path, required=True)
    prepare.add_argument("--output-file", type=Path, required=True)
    sub.add_parser("execute-task")
    finalize = sub.add_parser("finalize")
    finalize.add_argument("--request-file", type=Path, required=True)
    finalize.add_argument("--output-file", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    store = GCSExactTransportV1()
    if args.command == "prepare":
        _write_create_once(args.output_file, _prepare(args.request_file, store))
        return 0
    if args.command == "execute-task":
        sys.stdout.buffer.write(_canonical(_execute_task(store)) + b"\n")
        return 0
    if args.command == "finalize":
        _write_create_once(args.output_file, _finalize(args.request_file, store))
        return 0
    _fail("unknown command")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        RunCorpusR6L2BPanelCloudV1Error,
        panel.CorpusR6L2BPanelCloudV1Error,
    ) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
