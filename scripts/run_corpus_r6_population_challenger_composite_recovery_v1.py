#!/usr/bin/env python3
"""Operate the pre-result F7/F8/F9 task-0 composite recovery."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import Mapping

from nfl_dfs.research import (
    corpus_r6_population_challenger_authority_v1 as authority,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_composite_recovery_v1 as recovery,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_cloud_v1 as population_cloud,
)


class RunCorpusR6PopulationChallengerCompositeRecoveryV1Error(RuntimeError):
    """Raised when the isolated recovery operator differs."""


_SHA_RE = re.compile(r"[0-9a-f]{64}")
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_CORE_PATH = Path(
    "src/nfl_dfs/research/"
    "corpus_r6_population_challenger_composite_recovery_v1.py"
)
_OPERATOR_PATH = Path(
    "scripts/run_corpus_r6_population_challenger_composite_recovery_v1.py"
)
_REPORT_PATH = Path(recovery.AMENDMENT_REPORT_PATH)


def _fail(message: str) -> None:
    raise RunCorpusR6PopulationChallengerCompositeRecoveryV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _strict_json_any(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                _fail(f"{label} repeats JSON key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda token: _fail(
                f"{label} contains non-finite constant {token}"
            ),
        )
    except RunCorpusR6PopulationChallengerCompositeRecoveryV1Error:
        raise
    except Exception as exc:
        raise RunCorpusR6PopulationChallengerCompositeRecoveryV1Error(
            f"{label} is not strict UTF-8 JSON"
        ) from exc
    return _mapping(value, label=label)


def _read_json(path: Path, *, label: str, canonical: bool = True) -> dict[str, object]:
    raw = path.read_bytes()
    if canonical:
        return recovery.strict_json_bytes_v1(raw, label=label)
    return _strict_json_any(raw, label=label)


def _write_local_create_once(path: Path, value: object) -> None:
    raw = recovery.canonical_bytes_v1(value)
    if path.exists():
        if path.read_bytes() != raw:
            _fail("local create-once output collision differs")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} is already present")
    return {**body, field: recovery.canonical_sha256_v1(body)}


def _require_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    body = dict(value)
    observed = body.pop(field, None)
    if (
        type(observed) is not str
        or _SHA_RE.fullmatch(observed) is None
        or observed != recovery.canonical_sha256_v1(body)
    ):
        _fail(f"{label} self-hash differs")


def _parts(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        _fail("GCS URI must start with gs://")
    bucket, separator, name = uri[5:].partition("/")
    if not separator or not bucket or not name:
        _fail("GCS URI is incomplete")
    return bucket, name


class GCSExactTransportV1:
    """Generation-exact reads, deterministic-name opens and create-once writes."""

    def __init__(self) -> None:
        from google.cloud import storage  # imported only by live operator

        self._client = storage.Client(project=population_cloud.PROJECT)
        self._cache: dict[tuple[str, str], bytes] = {}

    def read_exact(self, identity_value: object) -> bytes:
        identity = authority.object_identity_v1(
            identity_value, label="generation-exact GCS object"
        )
        key = (str(identity["uri"]), str(identity["generation"]))
        if key in self._cache:
            return self._cache[key]
        bucket_name, object_name = _parts(str(identity["uri"]))
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

    def open_known(
        self, uri: str, maximum_bytes: int
    ) -> tuple[bytes, dict[str, object]]:
        bucket_name, object_name = _parts(uri)
        blob = self._client.bucket(bucket_name).blob(object_name)
        blob.reload(retry=None)
        if blob.generation is None or blob.size is None:
            _fail("known deterministic object lacks generation/size")
        if int(blob.size) <= 0 or int(blob.size) > maximum_bytes:
            _fail("known deterministic object exceeds its byte ceiling")
        generation = int(blob.generation)
        raw = blob.download_as_bytes(if_generation_match=generation, retry=None)
        identity = {
            "uri": uri,
            "generation": str(generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if len(raw) != int(blob.size):
            _fail("known deterministic object size differs")
        self._cache[(uri, str(generation))] = raw
        return raw, identity

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if type(raw) is not bytes or not raw:
            _fail("create-once publication bytes differ")
        bucket_name, object_name = _parts(uri)
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


def _publish_mapping(
    store: GCSExactTransportV1,
    *,
    uri: str,
    value: Mapping[str, object],
    maximum_bytes: int,
) -> dict[str, object]:
    try:
        return authority.publish_canonical_create_once_v1(
            uri=uri,
            value=value,
            maximum_bytes=maximum_bytes,
            publish_create_once=store.publish_create_once,
            read_exact=store.read_exact,
        )
    except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise RunCorpusR6PopulationChallengerCompositeRecoveryV1Error(
            str(exc)
        ) from exc


def _source_sha256s() -> dict[str, str]:
    if not _CORE_PATH.is_file() or not _OPERATOR_PATH.is_file():
        _fail("recovery source files are absent")
    return {
        "core": sha256(_CORE_PATH.read_bytes()).hexdigest(),
        "operator": sha256(_OPERATOR_PATH.read_bytes()).hexdigest(),
    }


def _prepare(args: argparse.Namespace) -> dict[str, object]:
    if _COMMIT_RE.fullmatch(args.recovery_code_commit) is None:
        _fail("--recovery-code-commit must be lowercase 40-hex")
    if not _REPORT_PATH.is_file():
        _fail("pre-result recovery amendment is absent")
    preparation = _read_json(
        args.preparation_file, label="population preparation"
    )
    manifest_identity = preparation.get("population_task_manifest_identity")
    store = GCSExactTransportV1()
    manifest_raw = store.read_exact(manifest_identity)
    manifest = recovery.strict_json_bytes_v1(
        manifest_raw, label="population task manifest"
    )
    intent = recovery.build_recovery_intent_v1(
        preparation=preparation,
        population_manifest=manifest,
        smoke_launch_result=_read_json(
            args.smoke_launch_file, label="task0 smoke launch"
        ),
        smoke_status=_read_json(
            args.smoke_status_file, label="task0 smoke status"
        ),
        smoke_collection=_read_json(
            args.smoke_collection_file, label="task0 smoke collection"
        ),
        full54_launch_result=_read_json(
            args.full54_launch_file, label="full54 launch"
        ),
        full54_status=_read_json(
            args.full54_status_file, label="full54 terminal status"
        ),
        smoke_task_description=_read_json(
            args.smoke_task_description_file,
            label="smoke task description",
            canonical=False,
        ),
        failed_task_description=_read_json(
            args.failed_task_description_file,
            label="failed task description",
            canonical=False,
        ),
        crossed_output_prefix=args.crossed_output_prefix,
        recovery_code_commit=args.recovery_code_commit,
        recovery_source_sha256s=_source_sha256s(),
        amendment_report_sha256=sha256(_REPORT_PATH.read_bytes()).hexdigest(),
    )
    intent_identity = _publish_mapping(
        store,
        uri=str(intent["outputs"]["intent_uri"]),
        value=intent,
        maximum_bytes=recovery.MAXIMUM_INTENT_BYTES,
    )
    result = _with_hash({
        "schema_version": recovery.PREPARE_RESULT_SCHEMA,
        "recovery_id": recovery.RECOVERY_ID,
        "recovery_intent_identity": intent_identity,
        "recovery_intent_sha256": intent["recovery_intent_sha256"],
        "intent_published_before_result_opens": True,
        "scientific_result_bodies_opened": False,
        "bucket_listing_performed": False,
        "logs_read": False,
        "outcomes_read": False,
    }, field="prepare_result_sha256")
    return result


def _validate_prepare_result(value: object) -> dict[str, object]:
    item = _mapping(value, label="recovery prepare result")
    expected = {
        "schema_version",
        "recovery_id",
        "recovery_intent_identity",
        "recovery_intent_sha256",
        "intent_published_before_result_opens",
        "scientific_result_bodies_opened",
        "bucket_listing_performed",
        "logs_read",
        "outcomes_read",
        "prepare_result_sha256",
    }
    if set(item) != expected or item.get("schema_version") != recovery.PREPARE_RESULT_SCHEMA:
        _fail("recovery prepare-result fields/schema differ")
    _require_hash(item, field="prepare_result_sha256", label="prepare result")
    authority.object_identity_v1(
        item["recovery_intent_identity"], label="recovery intent"
    )
    if (
        item.get("recovery_id") != recovery.RECOVERY_ID
        or item.get("intent_published_before_result_opens") is not True
        or item.get("scientific_result_bodies_opened") is not False
        or item.get("bucket_listing_performed") is not False
        or item.get("logs_read") is not False
        or item.get("outcomes_read") is not False
    ):
        _fail("recovery prepare-result safety differs")
    return item


def _collect(args: argparse.Namespace) -> dict[str, object]:
    prepare_result = _validate_prepare_result(
        _read_json(args.prepare_result_file, label="recovery prepare result")
    )
    store = GCSExactTransportV1()
    intent_identity = prepare_result["recovery_intent_identity"]
    intent_raw = store.read_exact(intent_identity)
    intent = recovery.validate_recovery_intent_v1(
        recovery.strict_json_bytes_v1(intent_raw, label="recovery intent")
    )
    if intent["recovery_intent_sha256"] != prepare_result["recovery_intent_sha256"]:
        _fail("prepare result/reopened intent differs")
    collection, crossed_request = recovery.collect_composite_results_v1(
        recovery_intent=intent,
        recovery_intent_identity=intent_identity,
        read_exact=store.read_exact,
        open_known=store.open_known,
    )
    collection_identity = _publish_mapping(
        store,
        uri=str(intent["outputs"]["collection_uri"]),
        value=collection,
        maximum_bytes=recovery.MAXIMUM_COLLECTION_BYTES,
    )
    crossed_identity = _publish_mapping(
        store,
        uri=str(intent["outputs"]["crossed_prepare_request_uri"]),
        value=crossed_request,
        maximum_bytes=recovery.MAXIMUM_CROSSED_REQUEST_BYTES,
    )
    receipt = recovery.build_recovery_receipt_v1(
        recovery_intent=intent,
        recovery_intent_identity=intent_identity,
        composite_collection=collection,
        composite_collection_identity=collection_identity,
        crossed_prepare_request=crossed_request,
        crossed_prepare_request_identity=crossed_identity,
    )
    receipt_identity = _publish_mapping(
        store,
        uri=str(intent["outputs"]["recovery_receipt_uri"]),
        value=receipt,
        maximum_bytes=recovery.MAXIMUM_RECOVERY_RECEIPT_BYTES,
    )
    _write_local_create_once(args.crossed_request_output_file, crossed_request)
    return _with_hash({
        "schema_version": recovery.COLLECT_RESULT_SCHEMA,
        "recovery_id": recovery.RECOVERY_ID,
        "recovery_intent_identity": intent_identity,
        "composite_collection_identity": collection_identity,
        "crossed_prepare_request_identity": crossed_identity,
        "recovery_receipt_identity": receipt_identity,
        "task_result_count": authority.TASK_COUNT,
        "crossed_request_output_file": str(args.crossed_request_output_file),
        "new_execution_launched": False,
        "task_recomputed": False,
        "bucket_listing_performed": False,
        "logs_read": False,
        "outcomes_read": False,
    }, field="collect_result_sha256")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compose task0 smoke plus full54 tasks 1-53 outcome-blind"
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--preparation-file", type=Path, required=True)
    prepare.add_argument("--smoke-launch-file", type=Path, required=True)
    prepare.add_argument("--smoke-status-file", type=Path, required=True)
    prepare.add_argument("--smoke-collection-file", type=Path, required=True)
    prepare.add_argument("--full54-launch-file", type=Path, required=True)
    prepare.add_argument("--full54-status-file", type=Path, required=True)
    prepare.add_argument(
        "--smoke-task-description-file", type=Path, required=True
    )
    prepare.add_argument(
        "--failed-task-description-file", type=Path, required=True
    )
    prepare.add_argument("--crossed-output-prefix", required=True)
    prepare.add_argument("--recovery-code-commit", required=True)
    prepare.add_argument("--output-file", type=Path, required=True)

    collect = subparsers.add_parser("collect")
    collect.add_argument("--prepare-result-file", type=Path, required=True)
    collect.add_argument(
        "--crossed-request-output-file", type=Path, required=True
    )
    collect.add_argument("--output-file", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.output_file.exists():
        _fail("operator output file already exists")
    if args.mode == "collect" and args.crossed_request_output_file.exists():
        _fail("crossed request output file already exists")
    result = _prepare(args) if args.mode == "prepare" else _collect(args)
    _write_local_create_once(args.output_file, result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except (
        RunCorpusR6PopulationChallengerCompositeRecoveryV1Error,
        recovery.CorpusR6PopulationChallengerCompositeRecoveryV1Error,
        population_cloud.CorpusR6PopulationChallengerCloudV1Error,
        authority.CorpusR6PopulationChallengerAuthorityV1Error,
    ) as exc:
        print(f"population composite recovery failed closed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
