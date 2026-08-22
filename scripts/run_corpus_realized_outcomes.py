#!/usr/bin/env python3
"""Default-off runner for the sole corpus historical-outcome read.

The runner generation-reopens a previously accepted complete corpus batch,
requires the externally owned shared historical-outcome lease, and delegates
one frozen BigQuery read to the pure callback boundary.  It neither acquires
nor releases the lease and prints only create-once completion receipts.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import re
import sys
from typing import Final, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT / "src", ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import run_lr8_label_score_map as cloud_boundary  # noqa: E402
from nfl_dfs.research import lr8_label_fit_adapter as lease_identity  # noqa: E402
from nfl_dfs.research import lr8_label_score_map as lease_boundary  # noqa: E402
from nfl_dfs.research import corpus_realized_outcome_transport as supplier  # noqa: E402


ENABLED_ENV: Final = "CORPUS_REALIZED_OUTCOMES_ENABLED"
PROJECT: Final = supplier.PROJECT
_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,80}")
_JOB: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_CODE: Final = re.compile(r"[0-9a-f]{40}")
_IMAGE: Final = re.compile(r".+@sha256:[0-9a-f]{64}")
_BYTES: Final = re.compile(r"[1-9][0-9]*")


class CorpusRealizedOutcomeRunnerError(RuntimeError):
    """The executable realized-outcome boundary failed closed."""


@dataclass(frozen=True, slots=True)
class BatchAcceptancePin:
    uri: str
    generation: str
    sha256: str
    bytes: int

    def identity(self) -> dict[str, object]:
        return {
            "uri": self.uri,
            "generation": self.generation,
            "sha256": self.sha256,
            "bytes": self.bytes,
        }


@dataclass(frozen=True, slots=True)
class LeaseReceiptPin:
    """Non-secret, generation-pinned GCS delivery of the lease receipt."""

    uri: str
    generation: str
    sha256: str
    bytes: int

    def identity(self) -> dict[str, object]:
        return {
            "uri": self.uri,
            "generation": self.generation,
            "sha256": self.sha256,
            "bytes": self.bytes,
        }


class _ExactGraphReader:
    """Generation-pinned byte reader for every identity in the accepted DAG."""

    def __init__(self, client: object):
        self._client = client

    def __call__(self, identity: Mapping[str, object]) -> bytes:
        try:
            uri = identity["uri"]
            generation = cloud_boundary._generation(  # noqa: SLF001
                identity["generation"], label="accepted graph object"
            )
            cloud_boundary._digest(  # noqa: SLF001
                identity["sha256"], label="accepted graph digest"
            )
            bucket_name, name = cloud_boundary._gcs_parts(  # noqa: SLF001
                uri, label="accepted graph object"
            )
            generation_int = int(generation)
            blob = self._client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
                name, generation=generation_int
            )
            blob.reload(if_generation_match=generation_int)
            raw = blob.download_as_bytes(if_generation_match=generation_int)
        except cloud_boundary.LR8ScoreMapRunnerError as exc:
            raise CorpusRealizedOutcomeRunnerError(str(exc)) from exc
        except Exception as exc:
            raise CorpusRealizedOutcomeRunnerError(
                "accepted graph generation-pinned read failed"
            ) from exc
        if str(blob.generation) != generation or type(raw) is not bytes:
            raise CorpusRealizedOutcomeRunnerError(
                "accepted graph generation-pinned read differs"
            )
        return raw


class _CreateOncePublisher:
    def __init__(self, client: object):
        self._delegate = cloud_boundary._CreateOncePublisher(client)  # noqa: SLF001

    def __call__(self, uri: str, raw: bytes) -> supplier.PublishedObject:
        published = self._delegate(uri, raw)
        return supplier.PublishedObject(
            receipt=published.receipt,
            reopened_raw=published.reopened_raw,
            created_at=published.created_at,
            created=published.created,
        )


def run_cloud(
    *,
    config: supplier.SupplierConfig,
    batch_pin: BatchAcceptancePin,
    lease_contract: Mapping[str, object],
    bq_client: object,
    storage_client: object,
    clock: supplier.Clock = lambda: datetime.now(timezone.utc),
) -> supplier.RealizedOutcomeSupply:
    """Run through generation-pinned GCS and one-query BQ adapters."""
    if config.enabled is not True:
        raise CorpusRealizedOutcomeRunnerError(
            "corpus realized outcome runner is default-off"
        )
    verifier = cloud_boundary._LiveLeaseVerifier(  # noqa: SLF001
        storage_client, lease_contract
    )
    publisher = _CreateOncePublisher(storage_client)
    return supplier.supply_realized_outcomes(
        config=config,
        batch_acceptance_identity=batch_pin.identity(),
        read_exact=_ExactGraphReader(storage_client),
        verify_lease=verifier,
        read_table_metadata=lambda table: cloud_boundary._table_metadata(  # noqa: SLF001
            bq_client, table
        ),
        execute_query=lambda spec: cloud_boundary._execute_query(  # noqa: SLF001
            bq_client, spec
        ),
        publish=publisher,
        clock=clock,
    )


def _lease_contract_from_raw(raw: bytes) -> dict[str, object]:
    value = cloud_boundary._strict_json(  # noqa: SLF001
        raw, label="historical lease receipt"
    )
    allowed = ({"lease", "object"}, {"schema_version", "lease", "object"})
    if set(value) not in allowed or (
        "schema_version" in value
        and value["schema_version"] != "corpus-realized-lease-receipt/v1"
    ):
        raise CorpusRealizedOutcomeRunnerError(
            "historical lease receipt fields differ"
        )
    try:
        body = dict(value["lease"])  # type: ignore[arg-type]
        receipt = dict(value["object"])  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise CorpusRealizedOutcomeRunnerError(
            "historical lease receipt contract differs"
        ) from exc
    return {"body": body, "object_receipt": receipt}


def _load_remote_lease_receipt(
    storage_client: object, pin: LeaseReceiptPin,
) -> dict[str, object]:
    try:
        bucket_name, name = cloud_boundary._gcs_parts(  # noqa: SLF001
            pin.uri, label="historical lease receipt delivery"
        )
        generation = cloud_boundary._generation(  # noqa: SLF001
            pin.generation, label="historical lease receipt delivery"
        )
        cloud_boundary._digest(  # noqa: SLF001
            pin.sha256, label="historical lease receipt delivery digest"
        )
        generation_int = int(generation)
        blob = storage_client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
            name, generation=generation_int
        )
        blob.reload(if_generation_match=generation_int)
        raw = blob.download_as_bytes(if_generation_match=generation_int)
    except cloud_boundary.LR8ScoreMapRunnerError as exc:
        raise CorpusRealizedOutcomeRunnerError(str(exc)) from exc
    except Exception as exc:
        raise CorpusRealizedOutcomeRunnerError(
            "historical lease receipt generation-pinned delivery failed"
        ) from exc
    if (
        str(blob.generation) != generation
        or type(raw) is not bytes
        or len(raw) != pin.bytes
        or sha256(raw).hexdigest() != pin.sha256
    ):
        raise CorpusRealizedOutcomeRunnerError(
            "historical lease receipt delivery identity differs"
        )
    return _lease_contract_from_raw(raw)


def _receipt_only(result: supplier.RealizedOutcomeSupply) -> dict[str, object]:
    return {
        "status": "CORPUS_REALIZED_OUTCOMES_CLOSED",
        "attempt_object": dict(result.attempt_receipt),
        "player_score_source_object": dict(result.source_receipt),
        "actual_player_outcomes_object": dict(result.outcome_bundle_receipt),
        "realized_completion_object": dict(result.completion_receipt),
        "rank_available": False,
        "roi_available": False,
        "rank_roi_unavailable_reason": (
            "full_field_standings_and_payout_ladder_not_supplied"
        ),
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": supplier.LEASE_RELEASE_OWNER,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--batch-acceptance-uri", required=True)
    parser.add_argument("--batch-acceptance-generation", required=True)
    parser.add_argument("--batch-acceptance-sha256", required=True)
    parser.add_argument("--batch-acceptance-bytes", required=True)
    parser.add_argument("--historical-lease-receipt", type=Path)
    parser.add_argument("--historical-lease-receipt-uri")
    parser.add_argument("--historical-lease-receipt-generation")
    parser.add_argument("--historical-lease-receipt-sha256")
    parser.add_argument("--historical-lease-receipt-bytes")
    return parser


def _validated_cli(
    args: argparse.Namespace,
) -> tuple[
    supplier.SupplierConfig,
    BatchAcceptancePin,
    dict[str, object] | LeaseReceiptPin,
]:
    # These two gates intentionally precede every file read and cloud object.
    if not args.execute or os.environ.get(ENABLED_ENV) != "1":
        raise CorpusRealizedOutcomeRunnerError(
            f"--execute and {ENABLED_ENV}=1 are required explicitly"
        )
    if args.project != PROJECT or (
        _RUN_ID.fullmatch(args.run_id) is None
        or _JOB.fullmatch(args.job) is None
        or _CODE.fullmatch(args.code_sha) is None
        or _IMAGE.fullmatch(args.image) is None
    ):
        raise CorpusRealizedOutcomeRunnerError(
            "corpus realized runtime identity differs"
        )
    try:
        cloud_boundary._gcs_parts(  # noqa: SLF001
            args.batch_acceptance_uri, label="batch acceptance"
        )
        generation = cloud_boundary._generation(  # noqa: SLF001
            args.batch_acceptance_generation, label="batch acceptance"
        )
        digest = cloud_boundary._digest(  # noqa: SLF001
            args.batch_acceptance_sha256, label="batch acceptance digest"
        )
        if _BYTES.fullmatch(args.batch_acceptance_bytes) is None:
            raise CorpusRealizedOutcomeRunnerError(
                "batch acceptance bytes must be canonical"
            )
        pin = BatchAcceptancePin(
            uri=args.batch_acceptance_uri,
            generation=generation,
            sha256=digest,
            bytes=int(args.batch_acceptance_bytes),
        )
    except cloud_boundary.LR8ScoreMapRunnerError as exc:
        raise CorpusRealizedOutcomeRunnerError(str(exc)) from exc
    config = supplier.SupplierConfig(
        run_id=args.run_id,
        job=args.job,
        code_sha=args.code_sha,
        image=args.image,
        expected_batch_acceptance_object_sha256=pin.sha256,
        enabled=True,
    )
    local_receipt = getattr(args, "historical_lease_receipt", None)
    remote_values = (
        getattr(args, "historical_lease_receipt_uri", None),
        getattr(args, "historical_lease_receipt_generation", None),
        getattr(args, "historical_lease_receipt_sha256", None),
        getattr(args, "historical_lease_receipt_bytes", None),
    )
    if (local_receipt is not None) == all(
        value is not None for value in remote_values
    ):
        raise CorpusRealizedOutcomeRunnerError(
            "use exactly one local or generation-pinned GCS lease receipt"
        )
    if any(value is not None for value in remote_values) and not all(
        value is not None for value in remote_values
    ):
        raise CorpusRealizedOutcomeRunnerError(
            "generation-pinned GCS lease receipt fields are incomplete"
        )
    if local_receipt is not None:
        try:
            lease: dict[str, object] | LeaseReceiptPin = (
                cloud_boundary._read_lease_contract(local_receipt)  # noqa: SLF001
            )
        except cloud_boundary.LR8ScoreMapRunnerError as exc:
            raise CorpusRealizedOutcomeRunnerError(str(exc)) from exc
    else:
        assert all(value is not None for value in remote_values)
        uri, generation_raw, digest_raw, bytes_raw = remote_values
        try:
            cloud_boundary._gcs_parts(  # noqa: SLF001
                uri, label="historical lease receipt delivery"
            )
            generation = cloud_boundary._generation(  # noqa: SLF001
                generation_raw, label="historical lease receipt delivery"
            )
            digest = cloud_boundary._digest(  # noqa: SLF001
                digest_raw, label="historical lease receipt delivery digest"
            )
        except cloud_boundary.LR8ScoreMapRunnerError as exc:
            raise CorpusRealizedOutcomeRunnerError(str(exc)) from exc
        if type(bytes_raw) is not str or _BYTES.fullmatch(bytes_raw) is None:
            raise CorpusRealizedOutcomeRunnerError(
                "historical lease receipt delivery bytes must be canonical"
            )
        lease = LeaseReceiptPin(
            uri=str(uri),
            generation=generation,
            sha256=digest,
            bytes=int(bytes_raw),
        )
    uris = {
        pin.uri,
        lease_identity.HISTORICAL_OUTCOME_LEASE_URI,
        f"{config.output_root}/read-attempt.json",
        f"{config.output_root}/player-score-source.json",
        f"{config.output_root}/actual-player-outcomes.json",
        f"{config.output_root}/realized-completion.json",
    }
    if len(uris) != 6:
        raise CorpusRealizedOutcomeRunnerError(
            "corpus realized object URIs alias"
        )
    if isinstance(lease, LeaseReceiptPin):
        if lease.uri in uris:
            raise CorpusRealizedOutcomeRunnerError(
                "historical lease receipt delivery URI aliases runtime objects"
            )
        return config, pin, lease
    return config, pin, _validate_lease_for_config(lease, config=config)


def _validate_lease_for_config(
    lease: Mapping[str, object], *, config: supplier.SupplierConfig,
) -> dict[str, object]:
    lease_config = lease_boundary.SupplierConfig(
        config.run_id,
        config.job,
        config.code_sha,
        config.image,
        config.expected_batch_acceptance_object_sha256,
        True,
    )
    try:
        return lease_boundary._validate_lease(  # noqa: SLF001
            lease, config=lease_config
        )
    except lease_boundary.LR8ScoreMapError as exc:
        raise CorpusRealizedOutcomeRunnerError(str(exc)) from exc


def main(argv: Sequence[str] | None = None) -> int:
    config, pin, lease_reference = _validated_cli(_parser().parse_args(argv))
    # No Google client import or construction is reachable before both gates.
    from google.cloud import bigquery, storage

    storage_client = storage.Client(project=PROJECT)
    if isinstance(lease_reference, LeaseReceiptPin):
        lease = _validate_lease_for_config(
            _load_remote_lease_receipt(storage_client, lease_reference),
            config=config,
        )
    else:
        lease = lease_reference
    result = run_cloud(
        config=config,
        batch_pin=pin,
        lease_contract=lease,
        bq_client=bigquery.Client(project=PROJECT),
        storage_client=storage_client,
    )
    print(supplier.canonical_json_bytes(_receipt_only(result)).decode(), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CorpusRealizedOutcomeRunnerError,
        supplier.CorpusRealizedOutcomeError,
        lease_boundary.LR8ScoreMapError,
        cloud_boundary.LR8ScoreMapRunnerError,
    ) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
