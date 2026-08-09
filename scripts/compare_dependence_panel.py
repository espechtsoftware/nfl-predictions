#!/usr/bin/env python3
"""Apply the frozen 2023-2025 conditional-dependence gate to log reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nfl_dfs.research.conditional_schaake import (  # noqa: E402
    evaluate_dependence_panel,
)


def _load_report(path: Path) -> dict:
    text = path.read_text()
    for line in reversed(text.splitlines()):
        marker = "schaake-gate "
        if marker in line:
            return json.loads(line.split(marker, 1)[1])
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"no schaake-gate JSON in {path}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs=3, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate_dependence_panel([
        _load_report(path) for path in args.reports
    ])
    payload = json.dumps(result, indent=2, sort_keys=True)
    print(payload)
    if args.output:
        args.output.write_text(payload + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
