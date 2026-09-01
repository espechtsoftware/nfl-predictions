#!/usr/bin/env python3
"""Run the local-only Week-1 contest-capture rehearsal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nfl_dfs.ingest.contest_capture_rehearsal import (
    rehearse_capture,
    write_receipt_create_only,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a representative settled field, contest manifest, payout "
            "ladder and paid/shadow bindings without external reads or writes."
        )
    )
    parser.add_argument("--standings", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--captured-at",
        required=True,
        help=(
            "Representative post-settlement ISO-8601 capture timestamp; "
            "explicitly simulated when rehearsal_fixture=true"
        ),
    )
    parser.add_argument(
        "--rehearsed-at",
        required=True,
        help="ISO-8601 time at which this local rehearsal was performed",
    )
    parser.add_argument(
        "--receipt",
        required=True,
        type=Path,
        help="Create-only local receipt path",
    )
    parser.add_argument(
        "--confirm-settled",
        action="store_true",
        help="Explicitly confirm the representative contest is settled",
    )
    parser.add_argument(
        "--confirm-full-field",
        action="store_true",
        help="Explicitly confirm the representative CSV is the complete field",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    receipt = rehearse_capture(
        standings_path=args.standings,
        manifest_path=args.manifest,
        captured_at=args.captured_at,
        rehearsed_at=args.rehearsed_at,
        confirm_settled=args.confirm_settled,
        confirm_full_field=args.confirm_full_field,
    )
    disposition = write_receipt_create_only(args.receipt, receipt)
    print(
        json.dumps(
            {
                "status": "passed",
                "receipt_disposition": disposition,
                "receipt_path": str(args.receipt),
                "rehearsal_id": receipt["rehearsal_id"],
                "receipt_sha256": receipt["receipt_sha256"],
                "external_writes_performed": False,
            },
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
