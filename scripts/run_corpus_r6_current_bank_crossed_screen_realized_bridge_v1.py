#!/usr/bin/env python3
"""Run the terminal-first R6 current-bank no-rescore bridge.

This command accepts two explicit generation/SHA/byte identities.  It never
lists or resolves a current generation, queries BigQuery, opens a raw outcome
snapshot, runs a scorer, publishes an object, or mutates a graph.  The
outcome-reader closure is scoped to the named attribution release and is not
called until the pure bridge has validated all terminal confirmation pairs.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import os
from pathlib import Path
import sys
from typing import Final


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nfl_dfs.research import corpus_parametric_batch as batch  # noqa: E402
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_current_bank_crossed_screen_realized_bridge_v1 as bridge,
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


class RunCorpusR6CurrentBankRealizedBridgeV1Error(RuntimeError):
    """The bounded exact-generation bridge transport failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6CurrentBankRealizedBridgeV1Error(message)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise RunCorpusR6CurrentBankRealizedBridgeV1Error(str(exc)) from exc


def _identity_from_args(args: argparse.Namespace, *, stem: str) -> dict[str, object]:
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


def _preclient_environment_gate_v1(environment: Mapping[str, str]) -> None:
    present = [name for name in _REDIRECT_ENVIRONMENT if environment.get(name)]
    if present:
        _fail("redirect/credential environment is forbidden")


class GenerationExactGCSReaderV1:
    """One prefix-scoped generation read with an expected-size sentinel."""

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
            raise RunCorpusR6CurrentBankRealizedBridgeV1Error(
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


def _prefix_for_terminal(identity: Mapping[str, object]) -> str:
    uri = str(identity["uri"])
    if not uri.endswith("/root.json"):
        _fail("terminal root identity must name root.json")
    return uri[:-len("root.json")]


def _prefix_for_attribution(identity: Mapping[str, object]) -> str:
    uri = str(identity["uri"])
    if not uri.endswith("/attribution-release.json"):
        _fail("outcome identity must name attribution-release.json")
    return uri[:-len("attribution-release.json")]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score every frozen confirmation path from persisted no-rescore rows",
    )
    parser.add_argument(
        "--mode", required=True,
        choices=(bridge.MODE_ONE_SLATE_SMOKE, bridge.MODE_FULL_PANEL),
    )
    for stem in ("terminal_root", "outcome_authority"):
        option = stem.replace("_", "-")
        parser.add_argument(f"--{option}-uri", required=True)
        parser.add_argument(f"--{option}-generation", required=True)
        parser.add_argument(f"--{option}-sha256", required=True)
        parser.add_argument(f"--{option}-bytes", required=True, type=int)
    return parser


def run_with_readers_v1(
    argv: Sequence[str], *, terminal_reader: object, outcome_reader: object,
) -> dict[str, object]:
    """Testable command boundary; reader objects expose ``read_exact``."""
    args = _parser().parse_args(list(argv))
    terminal_identity = _identity_from_args(args, stem="terminal_root")
    outcome_identity = _identity_from_args(args, stem="outcome_authority")
    terminal_open = getattr(terminal_reader, "read_exact", None)
    outcome_open = getattr(outcome_reader, "read_exact", None)
    if not callable(terminal_open) or not callable(outcome_open):
        _fail("generation-exact readers differ")
    return bridge.build_realized_score_bridge_v1(
        terminal_root_identity=terminal_identity,
        outcome_authority_identity=outcome_identity,
        mode=args.mode,
        read_terminal_exact=terminal_open,
        read_outcome_exact=outcome_open,
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
        terminal_identity = _identity_from_args(args, stem="terminal_root")
        outcome_identity = _identity_from_args(args, stem="outcome_authority")
        _preclient_environment_gate_v1(os.environ)
        try:
            from google.cloud import storage
        except ImportError as exc:
            raise RunCorpusR6CurrentBankRealizedBridgeV1Error(
                "google-cloud-storage is required for the exact bridge CLI"
            ) from exc
        client = storage.Client(project=PROJECT)
        terminal_reader = GenerationExactGCSReaderV1(
            client, allowed_prefix=_prefix_for_terminal(terminal_identity),
            label="terminal authority",
        )
        outcome_reader = GenerationExactGCSReaderV1(
            client, allowed_prefix=_prefix_for_attribution(outcome_identity),
            label="no-rescore attribution authority",
        )
        report = bridge.build_realized_score_bridge_v1(
            terminal_root_identity=terminal_identity,
            outcome_authority_identity=outcome_identity,
            mode=args.mode,
            read_terminal_exact=terminal_reader.read_exact,
            read_outcome_exact=outcome_reader.read_exact,
        )
        raw = bridge.canonical_json_bytes_v1(report)
        if len(raw) > bridge.MAXIMUM_REPORT_BYTES:
            _fail("bridge stdout exceeds its byte ceiling")
        sys.stdout.buffer.write(raw + b"\n")
        sys.stdout.buffer.flush()
        return 0
    except (RunCorpusR6CurrentBankRealizedBridgeV1Error,
            bridge.CorpusR6CurrentBankRealizedBridgeV1Error,
            SystemExit) as exc:
        if isinstance(exc, SystemExit):
            raise
        message = str(exc).encode("utf-8")[:MAXIMUM_ERROR_UTF8_BYTES].decode(
            "utf-8", errors="replace",
        )
        print(f"realized bridge failed: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
