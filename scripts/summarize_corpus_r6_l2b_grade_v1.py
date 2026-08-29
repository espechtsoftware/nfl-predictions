#!/usr/bin/env python3
"""Write local JSON and Markdown summaries for a completed L2b grade."""

from __future__ import annotations

import argparse
from pathlib import Path

from nfl_dfs.research.corpus_r6_l2b_grade_summary_v1 import (
    render_compact_markdown_v1,
    summarize_l2b_grade_v1,
)
from nfl_dfs.research.corpus_r6_score_sprint_scorecard_v1 import canonical_json_bytes_v1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--grade", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()
    summary = summarize_l2b_grade_v1(args.grade)
    args.json_output.write_bytes(canonical_json_bytes_v1(summary) + b"\n")
    args.markdown_output.write_text(render_compact_markdown_v1(summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
