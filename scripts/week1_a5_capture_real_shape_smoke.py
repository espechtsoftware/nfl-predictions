#!/usr/bin/env python3
"""Default-off, write-free shape smoke for Week-1 A5 provider bytes.

This tool never publishes an object, calls DraftKings, opens a browser, or
touches cloud/warehouse state.  It reads only operator-supplied local files
after an explicit execution flag and prints a redacted structural projection.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from nfl_dfs.ingest import week1_a5_capture_contracts as capture


def _read(path: str | None, *, label: str) -> bytes:
    if path is None:
        raise ValueError(f"{label} path is required")
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"{label} is not a file: {source}")
    raw = source.read_bytes()
    if not raw:
        raise ValueError(f"{label} is empty: {source}")
    return raw


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect local A5 provider capture shapes without writes"
    )
    parser.add_argument(
        "--execute-real-shape-smoke",
        action="store_true",
        help="required opt-in; without it no file is opened",
    )
    parser.add_argument(
        "--phase",
        choices=("prelock-acceptance", "postlock-final-field"),
        required=True,
    )
    parser.add_argument(
        "--contest-role",
        choices=tuple(capture.A5_ROLE_TABLE),
        required=True,
    )
    parser.add_argument("--acceptance-source")
    parser.add_argument("--provider-source")
    parser.add_argument("--standings-source")
    parser.add_argument(
        "--allow-postlock-outcome-bytes",
        action="store_true",
        help="separate acknowledgement required before reading standings bytes",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not args.execute_real_shape_smoke:
        parser.error("real-shape smoke is default-off; pass --execute-real-shape-smoke")
    if args.phase == "prelock-acceptance":
        if args.provider_source or args.standings_source:
            parser.error("prelock acceptance accepts only --acceptance-source")
        result = capture.inspect_acceptance_provider_bytes_v1(
            _read(args.acceptance_source, label="acceptance source"),
            contest_role=args.contest_role,
        )
    else:
        if args.acceptance_source:
            parser.error("postlock final-field does not accept --acceptance-source")
        if not args.allow_postlock_outcome_bytes:
            parser.error(
                "postlock final-field requires --allow-postlock-outcome-bytes"
            )
        result = capture.inspect_final_field_provider_bytes_v1(
            _read(args.provider_source, label="provider source"),
            _read(args.standings_source, label="standings source"),
            contest_role=args.contest_role,
        )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
