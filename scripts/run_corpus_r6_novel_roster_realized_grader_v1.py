#!/usr/bin/env python3
"""Seal or grade one terminal 54-slate novel-roster experiment."""

from __future__ import annotations

from collections.abc import Mapping
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from nfl_dfs.research import corpus_r6_novel_roster_realized_grader_v1 as grader


class RunCorpusR6NovelRosterRealizedGraderV1Error(RuntimeError):
    """The terminal-root or realized-scorecard command failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6NovelRosterRealizedGraderV1Error(message)


def _canonical(value: object) -> bytes:
    return grader.canonical_json_bytes_v1(value)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunCorpusR6NovelRosterRealizedGraderV1Error(
            f"{label} is not UTF-8 JSON"
        ) from exc
    item = _mapping(value, label=label)
    if _canonical(item) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return grader._identity(value, label=label)
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise RunCorpusR6NovelRosterRealizedGraderV1Error(str(exc)) from exc


class GCSExactTransportV1:
    """Generation-exact reads and create-once equal-byte recovery."""

    def __init__(self) -> None:
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import storage
        except Exception as exc:  # pragma: no cover - cloud dependency
            raise RunCorpusR6NovelRosterRealizedGraderV1Error(
                "google-cloud-storage is required"
            ) from exc
        self._client = storage.Client(
            project=grader.FIXED_GCP_PROJECT,
            client_options=ClientOptions(
                api_endpoint=grader.FIXED_STORAGE_ENDPOINT
            ),
        )
        self._cache: dict[tuple[str, str, str, int], bytes] = {}

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if type(uri) is not str or not uri.startswith("gs://"):
            _fail("GCS URI must use gs://")
        bucket, separator, name = uri[5:].partition("/")
        if not separator or not bucket or not name or "//" in name:
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
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
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


def create_terminal_root_from_request_v1(
    request: object, *, store: object,
) -> dict[str, object]:
    item = _mapping(request, label="create-terminal-root request")
    expected = {
        "adapter_id", "task_manifest_identity", "task_result_identities",
        "output_uri",
    }
    if set(item) != expected:
        _fail("create-terminal-root request fields differ")
    identities = item["task_result_identities"]
    if isinstance(identities, (str, bytes)) or not isinstance(identities, list):
        _fail("task-result identities must be one ordered array")
    if len(identities) != grader.SOURCE_SLATE_COUNT:
        _fail("create-terminal-root requires exactly 54 task-result identities")
    root, identity = grader.publish_terminal_experiment_root_v1(
        adapter_id=str(item["adapter_id"]),
        task_manifest_identity=item["task_manifest_identity"],
        task_result_identities=identities,
        target_uri=str(item["output_uri"]),
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    return {
        "schema_version": "corpus-r6-novel-roster-terminal-root-cli-result/v1",
        "adapter_id": root["adapter_id"],
        "terminal_root_identity": identity,
        "terminal_root_sha256": root["terminal_experiment_root_sha256"],
        "source_slate_count": root["source_slate_count"],
        "complete": True,
    }


def grade_from_request_v1(request: object, *, store: object) -> dict[str, object]:
    item = _mapping(request, label="grade request")
    expected = {
        "terminal_root_identity", "outcome_snapshot_identity", "output_uri",
    }
    if set(item) != expected:
        _fail("grade request fields differ")
    grade, identity = (
        grader.grade_and_publish_novel_roster_experiment_realized_v1(
            terminal_root_identity=item["terminal_root_identity"],
            outcome_snapshot_identity=item["outcome_snapshot_identity"],
            target_uri=str(item["output_uri"]),
            read_terminal_exact=store.read_exact,
            read_outcome_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
    )
    return {
        "schema_version": "corpus-r6-novel-roster-realized-grade-cli-result/v1",
        "adapter_id": grade["adapter_id"],
        "terminal_root_identity": grade["terminal_root_identity"],
        "outcome_snapshot_identity": grade["outcome_snapshot_identity"],
        "realized_scorecard_identity": identity,
        "realized_grade_sha256": grade["realized_grade_sha256"],
        "source_slate_count": grade["source_slate_count"],
        "aggregate_cell_count": grade["aggregate_cell_count"],
        "terminal_before_first_outcome_read": grade[
            "terminal_before_first_outcome_read"
        ],
        "complete": True,
    }


def _request_file(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_absolute() or not path.is_file():
        _fail(f"{label} must be an existing absolute file")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise RunCorpusR6NovelRosterRealizedGraderV1Error(
            f"{label} read failed"
        ) from exc
    return _strict_json(raw, label=label)


def _write_create_once(path: Path, value: Mapping[str, object]) -> None:
    raw = _canonical(value)
    if not path.is_absolute() or not path.parent.is_dir():
        _fail("local result must be a new file in an existing directory")
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except FileExistsError as exc:
        raise RunCorpusR6NovelRosterRealizedGraderV1Error(
            "local result already exists; create-once write refused"
        ) from exc
    except OSError as exc:
        raise RunCorpusR6NovelRosterRealizedGraderV1Error(
            "local result create-once write failed"
        ) from exc
    sys.stdout.buffer.write(raw + b"\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("create-terminal-root", "grade"):
        child = commands.add_parser(command)
        child.add_argument("--request-file", type=Path, required=True)
        child.add_argument("--output-file", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    store = GCSExactTransportV1()
    request = _request_file(args.request_file, label=f"{args.command} request")
    if args.command == "create-terminal-root":
        result = create_terminal_root_from_request_v1(request, store=store)
    elif args.command == "grade":
        result = grade_from_request_v1(request, store=store)
    else:  # pragma: no cover - argparse owns the command registry
        _fail("unknown command")
    _write_create_once(args.output_file, result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        RunCorpusR6NovelRosterRealizedGraderV1Error,
        grader.CorpusR6NovelRosterRealizedGraderV1Error,
    ) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
