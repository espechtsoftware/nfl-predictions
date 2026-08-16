#!/usr/bin/env python3
"""Emit the frozen ATLAS MVP source-repair environment."""

from __future__ import annotations

import argparse
import json

from nfl_dfs.research.atlas_money_transfer import gcloud_environment
from nfl_dfs.research.atlas_mvp_source_repair import (
    environment_differences,
    environment_sha256,
    repair_environment,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-receipt", required=True)
    parser.add_argument("--format", choices=("gcloud", "json"), default="json")
    args = parser.parse_args()
    receipt = json.load(open(args.source_receipt, encoding="utf-8"))
    original = receipt.get("values", {})
    repaired = repair_environment(original)
    if args.format == "gcloud":
        print(gcloud_environment(repaired))
    else:
        print(json.dumps({
            "sha256": environment_sha256(repaired),
            "values": repaired,
            "differences": environment_differences(original, repaired),
        }, sort_keys=True))


if __name__ == "__main__":
    main()
