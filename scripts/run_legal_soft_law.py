#!/usr/bin/env python3
"""Local mocked scaffold for the contingent legal-soft-law-v1 policy.

The runner accepts only canonical local JSON carrying ``mocked=true`` and
delegates to the pure accounting/ranking module.  It has no optimizer, model
fit, BigQuery, GCS, Cloud Run, lease, launch, or real-outcome path.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nfl_dfs.research.legal_soft_law import (  # noqa: E402
    canonical_json,
    evaluate_payload,
)


def _local_path(raw: str, *, label: str) -> Path:
    if "://" in raw:
        raise ValueError(f"{label} must be a local path")
    return Path(raw)


def load_canonical(path: Path) -> object:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("legal-soft-law input is invalid JSON") from exc
    if canonical_json(value) != raw:
        raise ValueError("legal-soft-law input is not canonical JSON")
    return value


def write_create_only(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)


def run(input_path: Path, output_path: Path | None = None) -> dict:
    report = evaluate_payload(load_canonical(input_path))
    raw = canonical_json(report)
    if output_path is not None:
        write_create_only(output_path, raw)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="canonical mocked local JSON")
    parser.add_argument("--output", help="optional create-only local JSON")
    args = parser.parse_args()
    input_path = _local_path(args.input, label="input")
    output_path = _local_path(args.output, label="output") if args.output else None
    report = run(input_path, output_path)
    print(canonical_json({
        "disposition": report["disposition"],
        "mode": report["mode"],
        "production_change_licensed": report["production_change_licensed"],
        "protocol_id": report["protocol_id"],
        "protocol_status": report["protocol_status"],
    }).decode("utf-8"))


if __name__ == "__main__":
    main()
