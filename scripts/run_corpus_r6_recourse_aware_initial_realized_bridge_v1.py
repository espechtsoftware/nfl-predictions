#!/usr/bin/env python3
"""Publish a recourse-aware initial-book rotated-fit realized diagnostic.

The command exact-opens the passed score-free terminal root, its bound report,
and the pinned persisted full-union attribution release.  It delegates all
validation/scoring to the pure bridge and publishes one mode-specific report
create-once.  It never lists a bucket, resolves an input generation, queries a
raw outcome source, or runs a lineup scorer.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import os
from pathlib import Path
import sys
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_recourse_aware_initial_realized_bridge_v1 as bridge,
)


PROJECT: Final = "nfl-predictions-503414"
GCS_TIMEOUT_SECONDS: Final = 1_200
MAXIMUM_ERROR_UTF8_BYTES: Final = 4_000
_REDIRECT_ENVIRONMENT: Final = (
    "ALL_PROXY", "CLOUDSDK_API_ENDPOINT_OVERRIDES_STORAGE",
    "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE", "CURL_CA_BUNDLE",
    "GCS_EMULATOR_HOST", "GOOGLE_APPLICATION_CREDENTIALS",
    "GRPC_DEFAULT_SSL_ROOTS_FILE_PATH", "HTTPS_PROXY", "HTTP_PROXY",
    "LD_AUDIT", "LD_LIBRARY_PATH", "LD_PRELOAD", "NO_PROXY",
    "PYTHONHOME", "PYTHONPATH", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE",
    "STORAGE_EMULATOR_HOST", "all_proxy", "https_proxy", "http_proxy",
    "no_proxy",
)


class RunCorpusR6RecourseAwareInitialRealizedBridgeV1Error(RuntimeError):
    """The bounded exact-generation publisher failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6RecourseAwareInitialRealizedBridgeV1Error(message)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise RunCorpusR6RecourseAwareInitialRealizedBridgeV1Error(
            str(exc)
        ) from exc


def _identity_from_args(
    args: argparse.Namespace, *, stem: str,
) -> dict[str, object]:
    return _identity({
        "uri": getattr(args, f"{stem}_uri"),
        "generation": getattr(args, f"{stem}_generation"),
        "sha256": getattr(args, f"{stem}_sha256"),
        "bytes": getattr(args, f"{stem}_bytes"),
    }, label=stem.replace("_", " "))


def _gcs_parts(uri: str) -> tuple[str, str]:
    bucket, separator, name = uri.removeprefix("gs://").partition("/")
    if not uri.startswith("gs://") or not separator or not bucket or not name:
        _fail("object URI must be canonical GCS")
    return bucket, name


def _safe_output_uri(value: object, *, mode: str) -> str:
    if type(value) is not str:
        _fail("output URI must be one string")
    if mode not in bridge.OUTPUT_FILENAME_BY_MODE:
        _fail("output mode differs")
    suffix = f"/{bridge.OUTPUT_FILENAME_BY_MODE[mode]}"
    relative = value.removeprefix(bridge.OUTPUT_NAMESPACE)
    if (
        not value.startswith(bridge.OUTPUT_NAMESPACE)
        or not value.endswith(suffix)
        or "//" in value.removeprefix("gs://")
        or any(part in {"", ".", ".."} for part in relative.split("/"))
        or any(character in value for character in ("\n", "\r", "?", "#"))
    ):
        _fail("output URI is outside the fixed recourse realized namespace")
    _gcs_parts(value)
    return value


def _preclient_environment_gate_v1(environment: Mapping[str, str]) -> None:
    if any(environment.get(name) for name in _REDIRECT_ENVIRONMENT):
        _fail("redirect/credential environment is forbidden")


def _validate_local_protocol_v1() -> None:
    path = Path(bridge.REALIZED_PROTOCOL_RELATIVE_PATH)
    if (
        not path.is_file()
        or path.is_symlink()
        or sha256(path.read_bytes()).hexdigest() != bridge.REALIZED_PROTOCOL_SHA256
    ):
        _fail("recourse realized bridge protocol differs")


class GenerationExactGCSReaderV1:
    """One prefix-scoped generation reader with an exact-size sentinel."""

    def __init__(
        self,
        client: object,
        *,
        allowed_prefix: str,
        label: str,
        conditional_retry: object,
    ) -> None:
        if not allowed_prefix.startswith("gs://") or not allowed_prefix.endswith("/"):
            _fail(f"{label} allowed prefix differs")
        self._client = client
        self._allowed_prefix = allowed_prefix
        self._label = label
        self._conditional_retry = conditional_retry
        self.call_count = 0

    def read_exact(self, value: Mapping[str, object]) -> bytes:
        identity = _identity(value, label=f"{self._label} exact identity")
        uri = str(identity["uri"])
        if not uri.startswith(self._allowed_prefix):
            _fail(f"{self._label} URI escapes its exact prefix")
        bucket_name, object_name = _gcs_parts(uri)
        generation = int(str(identity["generation"]))
        expected_bytes = int(identity["bytes"])
        try:
            blob = self._client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
                object_name, generation=generation,
            )
            raw = blob.download_as_bytes(
                start=0,
                end=expected_bytes,
                if_generation_match=generation,
                timeout=GCS_TIMEOUT_SECONDS,
                retry=self._conditional_retry,
            )
        except Exception as exc:
            raise RunCorpusR6RecourseAwareInitialRealizedBridgeV1Error(
                f"{self._label} generation-exact read failed"
            ) from exc
        self.call_count += 1
        if (
            type(raw) is not bytes
            or len(raw) != expected_bytes
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail(f"{self._label} exact body differs")
        return raw


class CreateOnceGCSWriterV1:
    """One exact-URI create-once writer with equal-byte retry recovery."""

    def __init__(
        self,
        client: object,
        *,
        output_uri: str,
        mode: str,
        conditional_retry: object,
    ) -> None:
        self._client = client
        self._output_uri = _safe_output_uri(output_uri, mode=mode)
        self._conditional_retry = conditional_retry
        self.call_count = 0

    def _exact_reopen(self, identity: Mapping[str, object]) -> bytes:
        bucket_name, object_name = _gcs_parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        blob = self._client.bucket(bucket_name).blob(
            object_name, generation=generation,
        )
        return blob.download_as_bytes(
            if_generation_match=generation,
            timeout=GCS_TIMEOUT_SECONDS,
            retry=self._conditional_retry,
        )

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if (
            uri != self._output_uri
            or type(raw) is not bytes
            or not raw
            or len(raw) > bridge.MAXIMUM_REPORT_BYTES
        ):
            _fail("recourse realized create-once publication differs")
        bucket_name, object_name = _gcs_parts(uri)
        blob = self._client.bucket(bucket_name).blob(object_name)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
                timeout=GCS_TIMEOUT_SECONDS,
                retry=self._conditional_retry,
            )
        except Exception as exc:  # pragma: no cover - provider exception type
            if exc.__class__.__name__ not in {"Conflict", "PreconditionFailed"}:
                raise
            existing = self._client.bucket(bucket_name).blob(object_name)
            existing.reload(
                timeout=GCS_TIMEOUT_SECONDS,
                retry=self._conditional_retry,
            )
            if existing.generation is None:
                _fail("recourse realized create-once collision lacks generation")
            generation = str(existing.generation)
        else:
            if blob.generation is None:
                _fail("recourse realized create-once upload lacks generation")
            generation = str(blob.generation)
        identity = _identity({
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }, label="recourse realized published report")
        try:
            reopened = self._exact_reopen(identity)
        except Exception as exc:
            raise RunCorpusR6RecourseAwareInitialRealizedBridgeV1Error(
                "recourse realized create-once exact reopen failed"
            ) from exc
        if reopened != raw:
            _fail("recourse realized create-once collision bytes differ")
        self.call_count += 1
        return identity


def _scorefree_prefix(identity: Mapping[str, object]) -> str:
    uri = str(identity["uri"])
    if uri != bridge.SCOREFREE_TERMINAL_URI:
        _fail("score-free identity must name the frozen terminal-root URI")
    return uri.removesuffix("terminal-root.json")


def _outcome_prefix(identity: Mapping[str, object]) -> str:
    if identity != bridge.OUTCOME_AUTHORITY_IDENTITY:
        _fail("outcome identity is not the frozen attribution release")
    return str(identity["uri"]).removesuffix("attribution-release.json")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Publish recourse-aware initial-book historical grades from "
            "persisted no-rescore rows"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    publish = sub.add_parser("publish")
    publish.add_argument(
        "--mode",
        required=True,
        choices=(bridge.MODE_ONE_SLATE_SMOKE, bridge.MODE_FULL_PANEL),
    )
    for stem in ("scorefree_terminal", "outcome_authority"):
        option = stem.replace("_", "-")
        publish.add_argument(f"--{option}-uri", required=True)
        publish.add_argument(f"--{option}-generation", required=True)
        publish.add_argument(f"--{option}-sha256", required=True)
        publish.add_argument(f"--{option}-bytes", required=True, type=int)
    publish.add_argument("--output-uri", required=True)
    return parser


def _run_parsed_v1(
    args: argparse.Namespace,
    *,
    scorefree_reader: object,
    outcome_reader: object,
    publisher: object,
) -> dict[str, object]:
    if args.command != "publish":
        _fail("recourse realized command differs")
    scorefree_identity = _identity_from_args(args, stem="scorefree_terminal")
    outcome_identity = _identity_from_args(args, stem="outcome_authority")
    output_uri = _safe_output_uri(args.output_uri, mode=args.mode)
    scorefree_open = getattr(scorefree_reader, "read_exact", None)
    outcome_open = getattr(outcome_reader, "read_exact", None)
    publish = getattr(publisher, "publish_create_once", None)
    if not callable(scorefree_open) or not callable(outcome_open) or not callable(publish):
        _fail("recourse realized exact transport differs")
    report = bridge.build_recourse_aware_initial_realized_bridge_v1(
        scorefree_terminal_identity=scorefree_identity,
        outcome_authority_identity=outcome_identity,
        mode=args.mode,
        read_scorefree_exact=scorefree_open,
        read_outcome_exact=outcome_open,
    )
    raw = bridge.canonical_json_bytes_v1(report)
    if len(raw) > bridge.MAXIMUM_REPORT_BYTES:
        _fail("recourse realized report exceeds its publication ceiling")
    report_identity = _identity(
        publish(output_uri, raw), label="published recourse realized report"
    )
    if (
        report_identity["uri"] != output_uri
        or report_identity["sha256"] != sha256(raw).hexdigest()
        or report_identity["bytes"] != len(raw)
    ):
        _fail("published recourse realized report identity differs")
    return bridge.build_publication_envelope_v1(
        report=report, report_identity=report_identity,
    )


def run_with_transports_v1(
    argv: Sequence[str],
    *,
    scorefree_reader: object,
    outcome_reader: object,
    publisher: object,
) -> dict[str, object]:
    """Testable CLI boundary with injected exact transports."""
    return _run_parsed_v1(
        _parser().parse_args(list(argv)),
        scorefree_reader=scorefree_reader,
        outcome_reader=outcome_reader,
        publisher=publisher,
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
        if args.command != "publish":
            _fail("recourse realized command differs")
        scorefree_identity = _identity_from_args(args, stem="scorefree_terminal")
        outcome_identity = _identity_from_args(args, stem="outcome_authority")
        output_uri = _safe_output_uri(args.output_uri, mode=args.mode)
        _preclient_environment_gate_v1(os.environ)
        _validate_local_protocol_v1()
        try:
            from google.cloud import storage
            from google.cloud.storage.retry import (
                DEFAULT_RETRY_IF_GENERATION_SPECIFIED,
            )
        except ImportError as exc:
            raise RunCorpusR6RecourseAwareInitialRealizedBridgeV1Error(
                "google-cloud-storage is required for the exact publisher CLI"
            ) from exc
        client = storage.Client(project=PROJECT)
        envelope = _run_parsed_v1(
            args,
            scorefree_reader=GenerationExactGCSReaderV1(
                client,
                allowed_prefix=_scorefree_prefix(scorefree_identity),
                label="recourse score-free terminal authority",
                conditional_retry=DEFAULT_RETRY_IF_GENERATION_SPECIFIED,
            ),
            outcome_reader=GenerationExactGCSReaderV1(
                client,
                allowed_prefix=_outcome_prefix(outcome_identity),
                label="recourse no-rescore attribution authority",
                conditional_retry=DEFAULT_RETRY_IF_GENERATION_SPECIFIED,
            ),
            publisher=CreateOnceGCSWriterV1(
                client,
                output_uri=output_uri,
                mode=args.mode,
                conditional_retry=DEFAULT_RETRY_IF_GENERATION_SPECIFIED,
            ),
        )
        sys.stdout.buffer.write(bridge.canonical_json_bytes_v1(envelope) + b"\n")
        sys.stdout.buffer.flush()
        return 0
    except (
        RunCorpusR6RecourseAwareInitialRealizedBridgeV1Error,
        bridge.CorpusR6RecourseAwareInitialRealizedBridgeV1Error,
    ) as exc:
        message = str(exc).encode("utf-8")[:MAXIMUM_ERROR_UTF8_BYTES].decode(
            "utf-8", errors="replace",
        )
        print(f"recourse realized publisher failed: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
