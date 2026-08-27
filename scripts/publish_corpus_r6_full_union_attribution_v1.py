#!/usr/bin/env python3
"""Publish or fully reopen the generation-pinned R6 attribution release."""

from __future__ import annotations

import argparse
from collections import OrderedDict
from hashlib import sha256
import os
from typing import Mapping, Sequence

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_attribution_release_v1 as release
from nfl_dfs.research import corpus_r6_full_union_grade_release_v1 as grade_release


PROJECT = "nfl-predictions-503414"
ENABLED_ENV = "R6_FULL_UNION_ATTRIBUTION_RELEASE_ENABLED"
DEFAULT_CACHE_BYTES = 2_500_000_000


class PublishCorpusR6FullUnionAttributionV1Error(ValueError):
    """The guarded attribution release CLI failed closed."""


def _fail(message: str) -> None:
    raise PublishCorpusR6FullUnionAttributionV1Error(message)


def _identity(
    *, uri: str, generation: str, sha256_value: str, bytes_value: int,
) -> dict[str, object]:
    try:
        return batch.normalize_object_identity({
            "uri": uri,
            "generation": generation,
            "sha256": sha256_value,
            "bytes": bytes_value,
        }, label="attribution CLI object identity")
    except batch.CorpusParametricBatchError as exc:
        raise PublishCorpusR6FullUnionAttributionV1Error(str(exc)) from exc


def _gcs_parts(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://") or "/" not in uri[5:]:
        _fail("attribution object URI must be canonical GCS")
    bucket, name = uri[5:].split("/", 1)
    if not bucket or not name or "//" in name:
        _fail("attribution object URI must be canonical GCS")
    return bucket, name


def _generation(value: object) -> str:
    retained = str(value)
    if not retained.isdigit() or int(retained) <= 0:
        _fail("GCS object generation differs")
    return retained


def _not_found(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    return (
        code == 404
        or callable(code) and code() == 404
        or type(exc).__name__ == "NotFound"
    )


class GenerationPinnedGCSV1:
    """Exact reads plus create-or-existing-byte-identical publication.

    The bounded LRU retains enough panel/task bytes to avoid a second remote
    transfer during publication, while evicting old task/output bodies rather
    than retaining the complete 54-slate release indefinitely.
    """

    def __init__(self, client: object, *, cache_bytes: int) -> None:
        if type(cache_bytes) is not int or cache_bytes < 100_000_000:
            _fail("attribution exact-read cache must be at least 100 MB")
        self.client = client
        self.cache_bytes = cache_bytes
        self.cached_bytes = 0
        self.cache: OrderedDict[tuple[str, str, str, int], bytes] = OrderedDict()

    @staticmethod
    def _key(identity: Mapping[str, object]) -> tuple[str, str, str, int]:
        return (
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )

    def _cache_get(self, identity: Mapping[str, object]) -> bytes | None:
        key = self._key(identity)
        raw = self.cache.get(key)
        if raw is not None:
            self.cache.move_to_end(key)
        return raw

    def _cache_put(self, identity: Mapping[str, object], raw: bytes) -> None:
        key = self._key(identity)
        previous = self.cache.pop(key, None)
        if previous is not None:
            self.cached_bytes -= len(previous)
        if len(raw) > self.cache_bytes:
            return
        self.cache[key] = raw
        self.cached_bytes += len(raw)
        while self.cached_bytes > self.cache_bytes and self.cache:
            _old_key, old_raw = self.cache.popitem(last=False)
            self.cached_bytes -= len(old_raw)

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        try:
            identity = batch.normalize_object_identity(
                identity_value, label="attribution exact-read identity"
            )
        except batch.CorpusParametricBatchError as exc:
            raise PublishCorpusR6FullUnionAttributionV1Error(str(exc)) from exc
        cached = self._cache_get(identity)
        if cached is not None:
            return cached
        bucket_name, object_name = _gcs_parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        try:
            blob = self.client.bucket(bucket_name).blob(
                object_name, generation=generation
            )
            blob.reload(if_generation_match=generation)
            raw = blob.download_as_bytes(if_generation_match=generation)
        except Exception as exc:
            raise PublishCorpusR6FullUnionAttributionV1Error(
                "attribution generation-pinned read failed"
            ) from exc
        if (
            type(raw) is not bytes
            or _generation(blob.generation) != identity["generation"]
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("attribution generation-pinned object differs")
        self._cache_put(identity, raw)
        return raw

    def resolve_current(
        self, uri: str, *, absent_ok: bool,
    ) -> tuple[dict[str, object], bytes] | None:
        bucket_name, object_name = _gcs_parts(uri)
        try:
            current = self.client.bucket(bucket_name).blob(object_name)
            current.reload()
        except Exception as exc:
            if absent_ok and _not_found(exc):
                return None
            raise PublishCorpusR6FullUnionAttributionV1Error(
                "attribution current object resolution failed"
            ) from exc
        generation = _generation(current.generation)
        try:
            pinned = self.client.bucket(bucket_name).blob(
                object_name, generation=int(generation)
            )
            pinned.reload(if_generation_match=int(generation))
            raw = pinned.download_as_bytes(if_generation_match=int(generation))
        except Exception as exc:
            raise PublishCorpusR6FullUnionAttributionV1Error(
                "attribution current generation reopen failed"
            ) from exc
        if type(raw) is not bytes or not raw:
            _fail("attribution current object is empty")
        identity = _identity(
            uri=uri,
            generation=generation,
            sha256_value=sha256(raw).hexdigest(),
            bytes_value=len(raw),
        )
        self._cache_put(identity, raw)
        return identity, raw

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        """Create once or recover only the exact existing byte sequence."""
        if type(raw) is not bytes or not raw:
            _fail("attribution publication payload differs")
        bucket_name, object_name = _gcs_parts(uri)
        try:
            blob = self.client.bucket(bucket_name).blob(object_name)
            blob.upload_from_string(
                raw, content_type="application/json", if_generation_match=0
            )
        except Exception:
            # A real collision and an ambiguous successful write are both
            # resolved by the exact current-generation comparison below.
            pass
        reopened = self.resolve_current(uri, absent_ok=False)
        if reopened is None:  # pragma: no cover - absent_ok=False
            raise AssertionError("required attribution object resolved absent")
        identity, existing = reopened
        if existing != raw:
            _fail("existing attribution object differs")
        return identity


def _add_grade_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--grade-completion-uri", required=True)
    parser.add_argument("--grade-completion-generation", required=True)
    parser.add_argument("--grade-completion-sha256", required=True)
    parser.add_argument("--grade-completion-bytes", type=int, required=True)
    parser.add_argument("--expected-grade-run-id", required=True)
    parser.add_argument("--expected-grade-job", required=True)
    parser.add_argument("--expected-grade-execution", required=True)
    parser.add_argument("--expected-grade-code-sha", required=True)
    parser.add_argument("--expected-grade-image", required=True)
    parser.add_argument("--expected-supply-run-id", required=True)
    parser.add_argument("--expected-supply-job", required=True)
    parser.add_argument("--expected-supply-code-sha", required=True)
    parser.add_argument("--expected-supply-image", required=True)
    parser.add_argument("--snapshot-module-sha256", required=True)
    parser.add_argument("--snapshot-cli-sha256", required=True)
    parser.add_argument("--snapshot-test-sha256", required=True)
    parser.add_argument("--snapshot-cli-test-sha256", required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--cache-bytes", type=int, default=DEFAULT_CACHE_BYTES)
    subparsers = parser.add_subparsers(dest="command", required=True)
    publish = subparsers.add_parser("publish")
    _add_grade_arguments(publish)
    publish.add_argument("--output-run-id", required=True)
    reopen = subparsers.add_parser("reopen")
    _add_grade_arguments(reopen)
    reopen.add_argument("--attribution-root-uri", required=True)
    reopen.add_argument("--attribution-root-generation", required=True)
    reopen.add_argument("--attribution-root-sha256", required=True)
    reopen.add_argument("--attribution-root-bytes", type=int, required=True)
    return parser


def _grade_inputs(
    args: argparse.Namespace,
) -> tuple[dict[str, object], grade_release.FullUnionGradeReleaseConfigV1]:
    completion_identity = _identity(
        uri=args.grade_completion_uri,
        generation=args.grade_completion_generation,
        sha256_value=args.grade_completion_sha256,
        bytes_value=args.grade_completion_bytes,
    )
    config = grade_release.FullUnionGradeReleaseConfigV1(
        run_id=args.expected_grade_run_id,
        job=args.expected_grade_job,
        execution=args.expected_grade_execution,
        code_sha=args.expected_grade_code_sha,
        image=args.expected_grade_image,
        expected_supply_run_id=args.expected_supply_run_id,
        expected_supply_job=args.expected_supply_job,
        expected_supply_code_sha=args.expected_supply_code_sha,
        expected_supply_image=args.expected_supply_image,
        snapshot_module_sha256=args.snapshot_module_sha256,
        snapshot_cli_sha256=args.snapshot_cli_sha256,
        snapshot_test_sha256=args.snapshot_test_sha256,
        snapshot_cli_test_sha256=args.snapshot_cli_test_sha256,
        enabled=True,
    )
    try:
        return completion_identity, grade_release.validate_grade_release_config_v1(
            config
        )
    except grade_release.CorpusR6FullUnionGradeReleaseV1Error as exc:
        raise PublishCorpusR6FullUnionAttributionV1Error(str(exc)) from exc


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    storage_client: object | None = None,
) -> int:
    args = _parser().parse_args(argv)
    env = os.environ if environ is None else environ
    if not args.execute or env.get(ENABLED_ENV) != "1":
        _fail(f"--execute and {ENABLED_ENV}=1 are required")
    if args.project != PROJECT:
        _fail("attribution release project differs")
    completion_identity, config = _grade_inputs(args)
    if storage_client is None:
        try:
            from google.cloud import storage  # type: ignore

            storage_client = storage.Client(project=args.project)
        except Exception as exc:
            raise PublishCorpusR6FullUnionAttributionV1Error(
                "attribution storage client construction failed"
            ) from exc
    store = GenerationPinnedGCSV1(
        storage_client, cache_bytes=args.cache_bytes
    )
    try:
        if args.command == "publish":
            output_prefix = (
                f"gs://{release.OUTPUT_BUCKET}/{release.OUTPUT_NAMESPACE}/"
                f"{args.output_run_id}"
            )
            root, root_identity = (
                release.publish_r6_full_union_attribution_release_v1(
                    grade_completion_identity=completion_identity,
                    grade_release_config=config,
                    output_prefix=output_prefix,
                    read_exact=store.read_exact,
                    publish_create_once=store.publish_create_once,
                )
            )
        elif args.command == "reopen":
            root_identity_input = _identity(
                uri=args.attribution_root_uri,
                generation=args.attribution_root_generation,
                sha256_value=args.attribution_root_sha256,
                bytes_value=args.attribution_root_bytes,
            )
            root, root_identity = (
                release.reopen_r6_full_union_attribution_release_v1(
                    root_identity_input,
                    grade_completion_identity=completion_identity,
                    grade_release_config=config,
                    read_exact=store.read_exact,
                )
            )
        else:  # pragma: no cover - argparse owns the command choices
            raise AssertionError("unknown attribution command")
    except release.CorpusR6FullUnionAttributionReleaseV1Error as exc:
        raise PublishCorpusR6FullUnionAttributionV1Error(str(exc)) from exc
    summary = {
        "schema_version": "corpus-r6-full-union-attribution-cli-summary/v1",
        "command": args.command,
        "root_identity": root_identity,
        "run_id": root["run_id"],
        "source_slate_count": root["source_slate_count"],
        "lineup_count": root["lineup_count"],
        "scope_membership_count": root["scope_membership_count"],
        "book_count": root["book_count"],
        "selection_count": root["selection_count"],
        "attribution_release_sha256": root["attribution_release_sha256"],
        "reads_freeze_and_grade_artifacts_only": root[
            "reads_freeze_and_grade_artifacts_only"
        ],
        "outcome_source_read": root["outcome_source_read"],
        "outcome_snapshot_read": root["outcome_snapshot_read"],
        "lineup_rescore_performed": root["lineup_rescore_performed"],
        "complete": root["complete"],
    }
    print(release.canonical_json_bytes(summary).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
