#!/usr/bin/env python3
"""Print one frozen ATLAS money-world acquisition environment/receipt."""

from __future__ import annotations

import argparse
import json

from nfl_dfs.research.atlas_money_transfer import (
    acquisition_environment,
    canonical_policy_receipt,
    environment_receipt,
    gcloud_environment,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--block", type=int, required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument(
        "--format", choices=("gcloud", "json", "policy-json"),
        default="json",
    )
    args = parser.parse_args()
    if args.format == "policy-json":
        print(json.dumps(canonical_policy_receipt(), sort_keys=True))
        return
    env = acquisition_environment(
        block=args.block,
        season=args.season,
        code_sha=args.code_sha,
        project=args.project,
    )
    if args.format == "gcloud":
        print(gcloud_environment(env))
    else:
        print(json.dumps(environment_receipt(env), sort_keys=True))


if __name__ == "__main__":
    main()
