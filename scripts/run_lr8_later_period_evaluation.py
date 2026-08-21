#!/usr/bin/env python3
"""Default-off executable for the sole LR8 later-period score read.

This process does not acquire, release, abandon, or delete the shared
historical-outcome lease.  Its external launcher/watcher owns that lifecycle;
this runner generation-reopens the supplied lease before and after the query
and returns receipt-only stdout so the owner can perform terminal release.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
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
from nfl_dfs.research import lr8_later_period_evaluation as supplier  # noqa: E402


ENABLED_ENV: Final = "LR8_LATER_PERIOD_EVALUATION_ENABLED"
PROJECT: Final = supplier.PROJECT
_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,127}")
_JOB: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_CODE: Final = re.compile(r"[0-9a-f]{40}")
_IMAGE: Final = re.compile(r".+@sha256:[0-9a-f]{64}")


class LR8LaterPeriodRunnerError(RuntimeError):
    """The executable later-period boundary failed closed."""


@dataclass(frozen=True, slots=True)
class BookFreezePin:
    uri: str
    generation: str
    sha256: str
    freeze_sha256: str


def _load_book_freeze(
    client: object, pin: BookFreezePin,
) -> tuple[dict[str, object], dict[str, object]]:
    source_pin = cloud_boundary.SourcePin(
        uri=pin.uri,
        generation=pin.generation,
        sha256=pin.sha256,
        manifest_sha256=pin.freeze_sha256,
    )
    try:
        return cloud_boundary._load_source(client, source_pin)  # noqa: SLF001
    except cloud_boundary.LR8ScoreMapRunnerError as exc:
        raise LR8LaterPeriodRunnerError(
            "book freeze generation-pinned read failed"
        ) from exc


def run_cloud(
    *, config: supplier.SupplierConfig, book_pin: BookFreezePin,
    lease_contract: Mapping[str, object], bq_client: object,
    storage_client: object,
    clock: supplier.Clock = lambda: datetime.now(timezone.utc),
) -> supplier.EvaluationSupply:
    """Run through reused, already-tested GCS/BQ callback adapters."""
    if config.enabled is not True:
        raise LR8LaterPeriodRunnerError("later-period runner is default-off")
    book_freeze, book_receipt = _load_book_freeze(storage_client, book_pin)
    verifier = cloud_boundary._LiveLeaseVerifier(  # noqa: SLF001
        storage_client, lease_contract
    )
    publisher = cloud_boundary._CreateOncePublisher(storage_client)  # noqa: SLF001
    return supplier.supply_later_period_evaluation(
        config=config,
        book_freeze=book_freeze,
        book_freeze_receipt=book_receipt,
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


def _receipt_only(result: supplier.EvaluationSupply) -> dict[str, object]:
    return {
        "status": "LR8_LATER_PERIOD_EVALUATION_CLOSED",
        "attempt_object": dict(result.attempt_receipt),
        "source_object": dict(result.source_receipt),
        "evaluation_object": dict(result.evaluation_receipt),
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": supplier.LEASE_OWNER,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--book-freeze-uri", required=True)
    parser.add_argument("--book-freeze-generation", required=True)
    parser.add_argument("--book-freeze-sha256", required=True)
    parser.add_argument("--book-freeze-manifest-sha256", required=True)
    parser.add_argument("--historical-lease-receipt", type=Path, required=True)
    return parser


def _validated_cli(
    args: argparse.Namespace,
) -> tuple[supplier.SupplierConfig, BookFreezePin, dict[str, object]]:
    # This check intentionally precedes every file read and cloud object.
    if not args.execute or os.environ.get(ENABLED_ENV) != "1":
        raise LR8LaterPeriodRunnerError(
            f"--execute and {ENABLED_ENV}=1 are required explicitly"
        )
    if args.project != PROJECT or (
        _RUN_ID.fullmatch(args.run_id) is None
        or _JOB.fullmatch(args.job) is None
        or _CODE.fullmatch(args.code_sha) is None
        or _IMAGE.fullmatch(args.image) is None
    ):
        raise LR8LaterPeriodRunnerError("later-period runtime identity differs")
    try:
        cloud_boundary._gcs_parts(  # noqa: SLF001
            args.book_freeze_uri, label="book freeze"
        )
        pin = BookFreezePin(
            uri=args.book_freeze_uri,
            generation=cloud_boundary._generation(  # noqa: SLF001
                args.book_freeze_generation, label="book freeze"
            ),
            sha256=cloud_boundary._digest(  # noqa: SLF001
                args.book_freeze_sha256, label="book freeze digest"
            ),
            freeze_sha256=cloud_boundary._digest(  # noqa: SLF001
                args.book_freeze_manifest_sha256,
                label="book freeze manifest digest",
            ),
        )
        lease = cloud_boundary._read_lease_contract(  # noqa: SLF001
            args.historical_lease_receipt
        )
    except cloud_boundary.LR8ScoreMapRunnerError as exc:
        raise LR8LaterPeriodRunnerError(str(exc)) from exc
    config = supplier.SupplierConfig(
        run_id=args.run_id,
        job=args.job,
        code_sha=args.code_sha,
        image=args.image,
        expected_book_freeze_sha256=pin.freeze_sha256,
        enabled=True,
    )
    uris = {
        pin.uri,
        lease_identity.HISTORICAL_OUTCOME_LEASE_URI,
        f"{config.output_root}/later-period-read-attempt.json",
        f"{config.output_root}/later-period-player-score-source.json",
        f"{config.output_root}/later-period-evaluation.json",
    }
    if len(uris) != 5:
        raise LR8LaterPeriodRunnerError("later-period object URIs alias")
    lease_config = lease_boundary.SupplierConfig(
        config.run_id, config.job, config.code_sha, config.image,
        config.expected_book_freeze_sha256, True,
    )
    try:
        validated_lease = lease_boundary._validate_lease(  # noqa: SLF001
            lease, config=lease_config
        )
    except lease_boundary.LR8ScoreMapError as exc:
        raise LR8LaterPeriodRunnerError(str(exc)) from exc
    return config, pin, validated_lease


def main(argv: Sequence[str] | None = None) -> int:
    config, pin, lease = _validated_cli(_parser().parse_args(argv))
    from google.cloud import bigquery, storage

    result = run_cloud(
        config=config,
        book_pin=pin,
        lease_contract=lease,
        bq_client=bigquery.Client(project=PROJECT),
        storage_client=storage.Client(project=PROJECT),
    )
    print(supplier.canonical_json(_receipt_only(result)).decode(), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        LR8LaterPeriodRunnerError,
        supplier.LR8LaterPeriodError,
        lease_boundary.LR8ScoreMapError,
        cloud_boundary.LR8ScoreMapRunnerError,
    ) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
