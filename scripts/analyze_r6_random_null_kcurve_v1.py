#!/usr/bin/env python3
"""Print the local-only R6 random-null and nested-K diagnostic as JSON."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from nfl_dfs.research.corpus_r6_random_null_kcurve_v1 import (
    analyze_random_null_kcurve_v1,
)


def _pairs_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON repeats object key {key!r}")
        result[key] = value
    return result


def _load(path: Path) -> tuple[dict[str, object], dict[str, object]]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_without_duplicates)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value, {
        "path": str(path.resolve()),
        "bytes": len(raw),
        "file_sha256": sha256(raw).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-score-report", type=Path, required=True)
    parser.add_argument("--hard230-terminal", type=Path, required=True)
    parser.add_argument("--hard230-grade", type=Path, required=True)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    current, current_identity = _load(args.current_score_report)
    terminal, terminal_identity = _load(args.hard230_terminal)
    grade, grade_identity = _load(args.hard230_grade)
    result = analyze_random_null_kcurve_v1(
        current_report=current,
        hard_terminal=terminal,
        hard_grade=grade,
    )
    result["local_input_files"] = {
        "current_score_report": current_identity,
        "hard230_terminal": terminal_identity,
        "hard230_grade": grade_identity,
    }
    separators = (",", ":") if args.compact else None
    json.dump(result, sys.stdout, sort_keys=True, separators=separators, allow_nan=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
