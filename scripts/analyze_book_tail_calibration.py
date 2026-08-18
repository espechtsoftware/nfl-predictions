#!/usr/bin/env python3
"""Run the frozen retrospective selected-book tail-calibration audit."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nfl_dfs.research.book_tail_calibration import (  # noqa: E402
    analyze_source_path,
    canonical_json_bytes,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit selected-book tail calibration from the frozen tracked "
            "multi-seed factorial report. The output is retrospective and "
            "licenses no gate, promotion, or production change."
        )
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    if args.input.resolve() == args.output.resolve():
        parser.error("--input and --output must differ")
    result = analyze_source_path(args.input)
    payload = canonical_json_bytes(result)
    with args.output.open("xb") as handle:
        handle.write(payload)
    print(
        "SELECTED_BOOK_TAIL_CALIBRATION_COMPLETE",
        f"output={args.output}",
        f"bytes={len(payload)}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
