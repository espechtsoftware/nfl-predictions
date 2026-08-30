#!/usr/bin/env python3
"""Immutable Cloud Run CLI for the construction/allocation realized grade.

Modes:

* ``prepare`` freezes an outcome-blind grade manifest after deep-reopening the
  score-blind selection terminal.  It does not open the outcome authority.
* ``grade`` exact-opens the separately frozen catalog-wide completion, proves
  its already-active shared historical-outcome lease before opening realized
  data and again before publication, publishes all children create-once and
  the terminal root last, then deep-reopens/recomputes the grade.
* ``reopen`` independently repeats the same terminal/predecessor replay while
  proving that same completion-owned live lease.

The scientific store exposes exact reads and create-once writes only: there is
no listing, overwrite, or delete method.  The lease transport can only observe
the one fixed active-lease name; disposition remains the external launcher/
watcher's responsibility.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from typing import Final


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from nfl_dfs.research import (  # noqa: E402
    corpus_r6_construction_allocation_grade_operator_v1 as operator,
)


PROJECT: Final = "nfl-predictions-503414"
ENABLE_ENV: Final = "R6_CONSTRUCTION_ALLOCATION_GRADE_ENABLED"
ENABLE_VALUE: Final = "1"
CODE_SHA_ENV: Final = "R6_CONSTRUCTION_ALLOCATION_GRADE_CODE_SHA"
IMAGE_ENV: Final = "R6_CONSTRUCTION_ALLOCATION_GRADE_RUNTIME_IMAGE"
MAXIMUM_REQUEST_BYTES: Final = 8_000_000
GCS_TIMEOUT_SECONDS: Final = 900

PREPARE_REQUEST_SCHEMA: Final = (
    "corpus-r6-construction-allocation-grade-prepare-request/v1"
)
GRADE_REQUEST_SCHEMA: Final = (
    "corpus-r6-construction-allocation-grade-execute-request/v1"
)
REOPEN_REQUEST_SCHEMA: Final = (
    "corpus-r6-construction-allocation-grade-reopen-request/v1"
)
_RUN_ID = re.compile(r"[a-z0-9][a-z0-9-]{2,100}\Z")
_JOB = re.compile(r"[a-z0-9][a-z0-9-]{2,62}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_IMAGE = re.compile(r".+@sha256:[0-9a-f]{64}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class ConstructionAllocationGradeRunnerV1Error(RuntimeError):
    """The immutable runner contract or GCS operation differed."""


def _fail(message: str) -> None:
    raise ConstructionAllocationGradeRunnerV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} is not one string-keyed object")
    return dict(value)


def _canonical(value: object, *, newline: bool = False) -> bytes:
    try:
        raw = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ConstructionAllocationGradeRunnerV1Error(
            "canonical JSON differs"
        ) from exc
    return raw + (b"\n" if newline else b"")


def _identity(
    value: object, *, label: str, require_create_once: bool = False,
) -> dict[str, object]:
    item = _mapping(value, label=label)
    uri, generation, digest, size = (
        item.get("uri"), item.get("generation"), item.get("sha256"),
        item.get("bytes"),
    )
    if (
        type(uri) is not str or not uri.startswith("gs://")
        or type(generation) not in {str, int} or not str(generation)
        or type(digest) is not str or _SHA.fullmatch(digest) is None
        or type(size) is not int or size <= 0
        or (require_create_once and item.get("create_once") is not True)
    ):
        _fail(f"{label} identity differs")
    retained: dict[str, object] = {
        "uri": uri, "generation": str(generation), "sha256": digest,
        "bytes": size,
    }
    if require_create_once or item.get("create_once") is True:
        retained["create_once"] = True
    return retained


def _strict_request(path: Path) -> dict[str, object]:
    if not path.is_absolute() or not path.is_file():
        _fail("request must be one existing absolute regular file")
    if path.stat().st_size <= 0 or path.stat().st_size > MAXIMUM_REQUEST_BYTES:
        _fail("request exceeds its byte ceiling")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ConstructionAllocationGradeRunnerV1Error(
            "request is not JSON"
        ) from exc
    request = _mapping(value, label="request")
    if raw not in {_canonical(request), _canonical(request, newline=True)}:
        _fail("request is not canonical JSON")
    return request


class GCSExactCreateOnceStoreV1:
    """No list, overwrite, delete, or mutable resolution surface."""

    def __init__(self, client: object | None = None, *, project: str = PROJECT) -> None:
        if client is None:
            from google.cloud import storage

            client = storage.Client(project=project)
        self._client = client

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if type(uri) is not str or not uri.startswith("gs://"):
            _fail("GCS URI differs")
        bucket, separator, name = uri[5:].partition("/")
        if (
            not separator or not bucket or not name or "//" in name
            or any(part in {"", ".", ".."} for part in name.split("/"))
        ):
            _fail("GCS URI differs")
        return bucket, name

    def _blob(self, uri: str) -> object:
        bucket, name = self._parts(uri)
        return self._client.bucket(bucket).blob(name)

    def read_exact(self, identity: Mapping[str, object]) -> bytes:
        retained = _identity(identity, label="GCS exact read")
        raw = self._blob(str(retained["uri"])).download_as_bytes(
            if_generation_match=int(str(retained["generation"])),
            timeout=GCS_TIMEOUT_SECONDS,
        )
        if (
            type(raw) is not bytes or len(raw) != retained["bytes"]
            or sha256(raw).hexdigest() != retained["sha256"]
        ):
            _fail("GCS generation-exact bytes differ")
        return raw

    def open_known(
        self, uri: str, maximum_bytes: int,
    ) -> tuple[bytes, dict[str, object]]:
        """Observe the current generation of one caller-specified known name."""

        if type(maximum_bytes) is not int or maximum_bytes <= 0:
            _fail("known-name byte ceiling differs")
        blob = self._blob(uri)
        blob.reload(timeout=GCS_TIMEOUT_SECONDS)
        if (
            blob.generation is None or blob.size is None
            or int(blob.size) <= 0 or int(blob.size) > maximum_bytes
        ):
            _fail("known-name object metadata differs")
        generation = str(blob.generation)
        raw = blob.download_as_bytes(
            if_generation_match=int(generation), timeout=GCS_TIMEOUT_SECONDS,
        )
        if type(raw) is not bytes or len(raw) != int(blob.size):
            _fail("known-name exact bytes differ")
        return raw, {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }

    def publish_create_once(self, uri: str, raw: bytes) -> Mapping[str, object]:
        if type(raw) is not bytes or not raw:
            _fail("GCS create-once bytes differ")
        blob = self._blob(uri)
        try:
            blob.upload_from_string(
                raw, content_type="application/json", if_generation_match=0,
                timeout=GCS_TIMEOUT_SECONDS,
            )
        except Exception:
            # Resolve only this deterministic name.  This handles both a real
            # collision and an ambiguous successful create without listing.
            try:
                blob.reload(timeout=GCS_TIMEOUT_SECONDS)
            except Exception as exc:
                raise ConstructionAllocationGradeRunnerV1Error(
                    "GCS create-once publication failed"
                ) from exc
        if blob.generation is None or blob.size is None:
            blob.reload(timeout=GCS_TIMEOUT_SECONDS)
        identity = {
            "uri": uri,
            "generation": str(blob.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
            "create_once": True,
        }
        reopened = self.read_exact(identity)
        if reopened != raw or int(blob.size) != len(raw):
            _fail("GCS create-once collision/reopen differs")
        return identity


class GCSLiveHistoricalOutcomeLeaseVerifierV1:
    """Verify the completion-owned current lease; never mutate it."""

    MAXIMUM_LEASE_BYTES: Final = 64_000

    def __init__(self, *, store: GCSExactCreateOnceStoreV1) -> None:
        self._store = store

    def __call__(
        self, *, expected_identity: Mapping[str, object], catalog_run_id: str,
    ) -> Mapping[str, object]:
        expected = _identity(
            expected_identity, label="completion historical-outcome lease"
        )
        if (
            expected["uri"] != operator.HISTORICAL_OUTCOME_LEASE_URI
            or _RUN_ID.fullmatch(catalog_run_id) is None
        ):
            _fail("completion historical-outcome lease authority differs")
        raw, observed = self._store.open_known(
            operator.HISTORICAL_OUTCOME_LEASE_URI, self.MAXIMUM_LEASE_BYTES
        )
        if observed != expected or not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
            _fail("completion lease is not the current live generation")
        try:
            value = json.loads(raw[:-1].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConstructionAllocationGradeRunnerV1Error(
                "live historical-outcome lease is not JSON"
            ) from exc
        body = _mapping(value, label="live historical-outcome lease")
        if (
            _canonical(body) != raw[:-1]
            or set(body) != {
                "version", "run_id", "job", "code_sha", "image", "acquired_at",
            }
            or body.get("version") != "historical-outcome-active-v1"
            or body.get("run_id") != catalog_run_id
            or type(body.get("job")) is not str or not body["job"]
            or _COMMIT.fullmatch(str(body.get("code_sha", ""))) is None
            or type(body.get("image")) is not str or not body["image"]
        ):
            _fail("live historical-outcome lease body differs")
        try:
            acquired_at = datetime.fromisoformat(str(body.get("acquired_at")))
        except ValueError as exc:
            raise ConstructionAllocationGradeRunnerV1Error(
                "live historical-outcome lease timestamp differs"
            ) from exc
        if acquired_at.tzinfo is None or acquired_at.utcoffset() is None:
            _fail("live historical-outcome lease timestamp is not timezone-aware")
        return {"body": body, "object_receipt": observed}


def _runtime_gate(
    *, execute: bool, environ: Mapping[str, str], code_sha: str,
    immutable_image: str, require_task_envelope: bool,
) -> str:
    if execute is not True or environ.get(ENABLE_ENV) != ENABLE_VALUE:
        _fail(f"literal --execute and {ENABLE_ENV}={ENABLE_VALUE} are required")
    if (
        environ.get(CODE_SHA_ENV) != code_sha
        or environ.get(IMAGE_ENV) != immutable_image
        or _COMMIT.fullmatch(code_sha) is None
        or _IMAGE.fullmatch(immutable_image) is None
    ):
        _fail("runner code/image environment differs")
    job = environ.get("CLOUD_RUN_JOB", "")
    if require_task_envelope and (
        _JOB.fullmatch(job) is None
        or environ.get("CLOUD_RUN_TASK_INDEX") != "0"
        or environ.get("CLOUD_RUN_TASK_COUNT") != "1"
        or environ.get("CLOUD_RUN_TASK_ATTEMPT") != "0"
    ):
        _fail("runner requires one first-attempt Cloud Run task")
    return job


def _validate_prepare_request(value: object) -> dict[str, object]:
    item = _mapping(value, label="prepare request")
    expected = {
        "schema_version", "run_id", "grade_id", "frozen_at", "code_sha",
        "immutable_image", "output_prefix", "selection_terminal_envelope",
        "outcome_authority_identity",
    }
    if set(item) != expected or item.get("schema_version") != PREPARE_REQUEST_SCHEMA:
        _fail("prepare request fields differ")
    return item


def _validate_grade_request(value: object) -> dict[str, object]:
    item = _mapping(value, label="grade request")
    if (
        set(item) != {"schema_version", "manifest_identity"}
        or item.get("schema_version") != GRADE_REQUEST_SCHEMA
    ):
        _fail("grade request fields differ")
    _identity(item["manifest_identity"], label="grade request manifest")
    return item


def _validate_reopen_request(value: object) -> dict[str, object]:
    item = _mapping(value, label="reopen request")
    if (
        set(item) != {
            "schema_version", "terminal_envelope", "code_sha", "immutable_image",
        }
        or item.get("schema_version") != REOPEN_REQUEST_SCHEMA
        or _COMMIT.fullmatch(str(item.get("code_sha", ""))) is None
        or _IMAGE.fullmatch(str(item.get("immutable_image", ""))) is None
    ):
        _fail("reopen request fields differ")
    return item


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "grade", "reopen"):
        child = commands.add_parser(name)
        child.add_argument("--request", type=Path, required=True)
        child.add_argument("--execute", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None, *,
    environ: Mapping[str, str] | None = None,
    store: GCSExactCreateOnceStoreV1 | None = None,
    lease_verifier_factory: object | None = None,
) -> dict[str, object]:
    args = _parser().parse_args(argv)
    environment = dict(os.environ if environ is None else environ)
    request = _strict_request(args.request)
    retained_store = store or GCSExactCreateOnceStoreV1()

    if args.command == "prepare":
        item = _validate_prepare_request(request)
        _runtime_gate(
            execute=args.execute, environ=environment,
            code_sha=str(item["code_sha"]),
            immutable_image=str(item["immutable_image"]),
            require_task_envelope=False,
        )
        result = operator.prepare_grade_manifest_v1(
            run_id=str(item["run_id"]), grade_id=str(item["grade_id"]),
            frozen_at=str(item["frozen_at"]), code_sha=str(item["code_sha"]),
            immutable_image=str(item["immutable_image"]),
            output_prefix=str(item["output_prefix"]),
            selection_terminal_envelope=_mapping(
                item["selection_terminal_envelope"],
                label="prepare selection terminal envelope",
            ),
            outcome_authority_identity=_mapping(
                item["outcome_authority_identity"],
                label="prepare outcome authority identity",
            ),
            read_exact=retained_store.read_exact,
            publish_create_once=retained_store.publish_create_once,
        )
    elif args.command == "grade":
        item = _validate_grade_request(request)
        manifest, _ = operator.open_grade_manifest_v1(
            item["manifest_identity"], read_exact=retained_store.read_exact
        )
        _runtime_gate(
            execute=args.execute, environ=environment,
            code_sha=str(manifest["code_sha"]),
            immutable_image=str(manifest["immutable_image"]),
            require_task_envelope=True,
        )
        factory = lease_verifier_factory or GCSLiveHistoricalOutcomeLeaseVerifierV1
        lease_verifier = factory(store=retained_store)
        result = operator.publish_grade_v1(
            manifest_identity=item["manifest_identity"],
            code_sha=str(manifest["code_sha"]),
            immutable_image=str(manifest["immutable_image"]),
            read_exact=retained_store.read_exact,
            publish_create_once=retained_store.publish_create_once,
            verify_live_lease=lease_verifier,
        )
    else:
        item = _validate_reopen_request(request)
        envelope = _mapping(
            item["terminal_envelope"], label="reopen terminal envelope"
        )
        # Open only the score-free manifest first so code/image can be checked
        # before live-lease observation or any realized child is opened.
        manifest, _ = operator.open_grade_manifest_v1(
            envelope["manifest_identity"], read_exact=retained_store.read_exact
        )
        _runtime_gate(
            execute=args.execute, environ=environment,
            code_sha=str(item["code_sha"]),
            immutable_image=str(item["immutable_image"]),
            require_task_envelope=True,
        )
        if (
            item["code_sha"] != manifest["code_sha"]
            or item["immutable_image"] != manifest["immutable_image"]
        ):
            _fail("reopen request differs from grade manifest runtime")
        factory = lease_verifier_factory or GCSLiveHistoricalOutcomeLeaseVerifierV1
        lease_verifier = factory(store=retained_store)
        receipt = operator.reopen_grade_terminal_v1(
            envelope, read_exact=retained_store.read_exact,
            verify_live_lease=lease_verifier,
        )
        result = {
            "schema_version": (
                "corpus-r6-construction-allocation-grade-independent-reopen/v1"
            ),
            "reopen_receipt": receipt,
            "historical_outcome_lease_identity": receipt[
                "historical_outcome_lease_identity"
            ],
            "historical_outcome_lease_release_required": True,
            "lease_release_owner": "external-launcher-watcher",
            "historical_outcome_lease_released": False,
            "uses_realized_outcomes": True,
            "complete": True,
        }

    print(_canonical(result).decode("utf-8"))
    return result


if __name__ == "__main__":
    try:
        main()
    except (
        ConstructionAllocationGradeRunnerV1Error,
        operator.ConstructionAllocationGradeOperatorV1Error,
    ) as exc:
        raise SystemExit(str(exc)) from exc
