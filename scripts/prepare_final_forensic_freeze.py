#!/usr/bin/env python3
"""Build or verify the outcome-free final-forensic freeze manifest.

The input file contains only immutable code/production identities and prelock
panel metadata.  This command never queries BigQuery and never reads a player
actual or lineup score.  Panel metadata must be captured separately before the
freeze, then reviewed and tracked with the resulting manifest.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nfl_dfs.research.final_forensic import (
    build_freeze_manifest,
    validate_freeze_manifest,
)


DEFAULT_REGISTRY = (
    "reports/final-forensic-runs/20260814-final-preseason-forensic-v1/"
    "arm_registry.json"
)
DEFAULT_OUTPUT = (
    "reports/final-forensic-runs/20260814-final-preseason-forensic-v1/"
    "freeze_manifest.json"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="validate the existing output without rebuilding it",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    root = Path(args.repo_root).resolve()
    output = root / args.output
    if args.verify_only:
        manifest = json.loads(output.read_text(encoding="utf-8"))
        summary = validate_freeze_manifest(manifest, repo_root=root)
    else:
        inputs_path = Path(args.inputs)
        if not inputs_path.is_absolute():
            inputs_path = root / inputs_path
        inputs = json.loads(inputs_path.read_text(encoding="utf-8"))
        expected = {
            "analysis_image", "analysis_code_sha", "production", "panels",
            "between_arm_variance", "warehouse_retention",
        }
        if set(inputs) != expected:
            raise SystemExit(
                "freeze inputs must contain exactly " + ", ".join(sorted(expected))
            )
        manifest = build_freeze_manifest(
            repo_root=root,
            analysis_image=inputs["analysis_image"],
            analysis_code_sha=inputs["analysis_code_sha"],
            production=inputs["production"],
            panels=inputs["panels"],
            between_arm_variance=inputs["between_arm_variance"],
            warehouse_retention=inputs["warehouse_retention"],
            registry_path=args.registry,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        summary = validate_freeze_manifest(manifest, repo_root=root)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
