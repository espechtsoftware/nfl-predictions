#!/usr/bin/env python3
"""Publish one selector-successor realized report from frozen score rows.

The command exact-opens a successor-native terminal aggregate and the pinned
full-union attribution release, lets the pure bridge validate and grade them,
then publishes the completed report create-once.  It never queries BigQuery,
runs a lineup scorer, lists a bucket, resolves an input generation, or mutates
the graph.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import os
import sys
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_realized_bridge_v1 as bridge,
)


PROJECT: Final = "nfl-predictions-503414"
DOWNLOAD_TIMEOUT_SECONDS: Final = 600
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


class RunCorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
    RuntimeError
):
    """The bounded exact-generation publisher failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(message)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise RunCorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
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


def _safe_output_uri(value: object) -> str:
    if type(value) is not str:
        _fail("output URI must be one string")
    suffix = f"/{bridge.OUTPUT_FILENAME}"
    relative = value.removeprefix(contract.OUTPUT_NAMESPACE)
    if (
        not value.startswith(contract.OUTPUT_NAMESPACE)
        or not value.endswith(suffix)
        or "//" in value.removeprefix("gs://")
        or any(part in {"", ".", ".."} for part in relative.split("/"))
        or any(character in value for character in ("\n", "\r", "?", "#"))
    ):
        _fail("output URI is outside the fixed successor realized namespace")
    _gcs_parts(value)
    return value


def _preclient_environment_gate_v1(environment: Mapping[str, str]) -> None:
    if any(environment.get(name) for name in _REDIRECT_ENVIRONMENT):
        _fail("redirect/credential environment is forbidden")


class GenerationExactGCSReaderV1:
    """One prefix-scoped generation reader with an expected-size sentinel."""

    def __init__(self, client: object, *, allowed_prefix: str, label: str) -> None:
        if not allowed_prefix.startswith("gs://") or not allowed_prefix.endswith("/"):
            _fail(f"{label} allowed prefix differs")
        self._client = client
        self._allowed_prefix = allowed_prefix
        self._label = label
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
                timeout=DOWNLOAD_TIMEOUT_SECONDS,
                retry=None,
            )
        except Exception as exc:
            raise RunCorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
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

    def __init__(self, client: object, *, output_uri: str) -> None:
        self._client = client
        self._output_uri = _safe_output_uri(output_uri)
        self.call_count = 0

    def _exact_reopen(self, identity: Mapping[str, object]) -> bytes:
        bucket_name, object_name = _gcs_parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        blob = self._client.bucket(bucket_name).blob(
            object_name, generation=generation,
        )
        return blob.download_as_bytes(
            if_generation_match=generation,
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
            retry=None,
        )

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if (
            uri != self._output_uri
            or type(raw) is not bytes
            or not raw
            or len(raw) > bridge.MAXIMUM_REPORT_BYTES
        ):
            _fail("successor realized create-once publication differs")
        bucket_name, object_name = _gcs_parts(uri)
        blob = self._client.bucket(bucket_name).blob(object_name)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
                retry=None,
            )
        except Exception as exc:  # pragma: no cover - provider exception type
            if exc.__class__.__name__ not in {"Conflict", "PreconditionFailed"}:
                raise
            existing = self._client.bucket(bucket_name).blob(object_name)
            existing.reload(retry=None)
            if existing.generation is None:
                _fail("successor realized create-once collision lacks generation")
            generation = str(existing.generation)
        else:
            if blob.generation is None:
                _fail("successor realized create-once upload lacks generation")
            generation = str(blob.generation)
        identity = _identity({
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }, label="successor realized published report")
        try:
            reopened = self._exact_reopen(identity)
        except Exception as exc:
            raise RunCorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
                "successor realized create-once exact reopen failed"
            ) from exc
        if reopened != raw:
            _fail("successor realized create-once collision bytes differ")
        self.call_count += 1
        return identity


def _namespace_for_terminal_graph(identity: Mapping[str, object]) -> str:
    uri = str(identity["uri"])
    if (
        not uri.startswith(contract.OUTPUT_NAMESPACE)
        or not uri.endswith("/terminal-aggregate.json")
    ):
        _fail("successor terminal identity must name terminal-aggregate.json")
    # Successor terminals intentionally refer back to projection bundles in
    # the source-control run prefix.  Exact identities remain mandatory, but
    # the read namespace must cover both source and successor run prefixes.
    return contract.OUTPUT_NAMESPACE


def _prefix_for_attribution(identity: Mapping[str, object]) -> str:
    uri = str(identity["uri"])
    if not uri.endswith("/attribution-release.json"):
        _fail("outcome identity must name attribution-release.json")
    return uri.removesuffix("attribution-release.json")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Publish successor-native historical grades from persisted "
            "no-rescore rows"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    publish = sub.add_parser("publish")
    publish.add_argument(
        "--mode",
        required=True,
        choices=(bridge.MODE_ONE_SLATE_SMOKE, bridge.MODE_FULL_PANEL),
    )
    for stem in ("terminal_aggregate", "outcome_authority"):
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
    terminal_reader: object,
    outcome_reader: object,
    publisher: object,
) -> dict[str, object]:
    if args.command != "publish":
        _fail("successor realized command differs")
    terminal_identity = _identity_from_args(args, stem="terminal_aggregate")
    outcome_identity = _identity_from_args(args, stem="outcome_authority")
    output_uri = _safe_output_uri(args.output_uri)
    terminal_open = getattr(terminal_reader, "read_exact", None)
    outcome_open = getattr(outcome_reader, "read_exact", None)
    publish = getattr(publisher, "publish_create_once", None)
    if not callable(terminal_open) or not callable(outcome_open) or not callable(publish):
        _fail("successor realized exact transport differs")
    report = bridge.build_successor_realized_bridge_v1(
        terminal_aggregate_identity=terminal_identity,
        outcome_authority_identity=outcome_identity,
        mode=args.mode,
        read_terminal_exact=terminal_open,
        read_outcome_exact=outcome_open,
    )
    raw = bridge.canonical_json_bytes_v1(report)
    if len(raw) > bridge.MAXIMUM_REPORT_BYTES:
        _fail("successor realized report exceeds its publication ceiling")
    report_identity = _identity(
        publish(output_uri, raw), label="published successor realized report"
    )
    if (
        report_identity["uri"] != output_uri
        or report_identity["sha256"] != sha256(raw).hexdigest()
        or report_identity["bytes"] != len(raw)
    ):
        _fail("published successor realized report identity differs")
    return bridge.build_publication_envelope_v1(
        report=report, report_identity=report_identity,
    )


def run_with_transports_v1(
    argv: Sequence[str],
    *,
    terminal_reader: object,
    outcome_reader: object,
    publisher: object,
) -> dict[str, object]:
    """Testable CLI boundary with injected exact readers and publisher."""
    return _run_parsed_v1(
        _parser().parse_args(list(argv)),
        terminal_reader=terminal_reader,
        outcome_reader=outcome_reader,
        publisher=publisher,
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
        if args.command != "publish":
            _fail("successor realized command differs")
        terminal_identity = _identity_from_args(
            args, stem="terminal_aggregate"
        )
        outcome_identity = _identity_from_args(args, stem="outcome_authority")
        output_uri = _safe_output_uri(args.output_uri)
        _preclient_environment_gate_v1(os.environ)
        try:
            from google.cloud import storage
        except ImportError as exc:
            raise RunCorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
                "google-cloud-storage is required for the exact publisher CLI"
            ) from exc
        client = storage.Client(project=PROJECT)
        envelope = _run_parsed_v1(
            args,
            terminal_reader=GenerationExactGCSReaderV1(
                client,
                allowed_prefix=_namespace_for_terminal_graph(
                    terminal_identity
                ),
                label="successor terminal authority",
            ),
            outcome_reader=GenerationExactGCSReaderV1(
                client,
                allowed_prefix=_prefix_for_attribution(outcome_identity),
                label="no-rescore attribution authority",
            ),
            publisher=CreateOnceGCSWriterV1(client, output_uri=output_uri),
        )
        sys.stdout.buffer.write(bridge.canonical_json_bytes_v1(envelope) + b"\n")
        sys.stdout.buffer.flush()
        return 0
    except (
        RunCorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error,
        bridge.CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error,
    ) as exc:
        message = str(exc).encode("utf-8")[:MAXIMUM_ERROR_UTF8_BYTES].decode(
            "utf-8", errors="replace",
        )
        print(f"successor realized publisher failed: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
