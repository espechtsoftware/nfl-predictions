#!/usr/bin/env python3
"""Render a local-only comparison of already-downloaded R6 grade JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from nfl_dfs.research.corpus_r6_score_sprint_scorecard_v1 import (
    CorpusR6ScoreSprintScorecardV1Error,
    ScorecardInputV1,
    build_scorecard_v1,
    render_markdown_v1,
)


def _input_spec(value: str) -> ScorecardInputV1:
    label, separator, raw_path = value.partition("=")
    if separator:
        if not label or not raw_path:
            raise argparse.ArgumentTypeError("input must be LABEL=PATH")
        return ScorecardInputV1(label=label, path=Path(raw_path))
    path = Path(value)
    return ScorecardInputV1(label=path.stem, path=path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs",
        nargs="+",
        type=_input_spec,
        metavar="[LABEL=]PATH",
        help=(
            "local immutable grade/report JSON; labels are required when "
            "two basenames would collide"
        ),
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="stdout format (default: markdown)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    scorecard = build_scorecard_v1(args.inputs)
    if args.format == "json":
        json.dump(
            scorecard,
            sys.stdout,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown_v1(scorecard))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CorpusR6ScoreSprintScorecardV1Error as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
