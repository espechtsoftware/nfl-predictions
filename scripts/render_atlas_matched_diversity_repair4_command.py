#!/usr/bin/env python3
"""Render the fail-closed ATLAS repair4 output-prefix bootstrap."""

from __future__ import annotations

import argparse
import base64


RUNNER_PATH = "/app/scripts/run_atlas_matched_diversity_mvp.py"
ORIGINAL_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/"
    "20260816-atlas-matched-diversity-mvp-v1-repair2"
)
RUNNER_SHA256 = "0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740"


def render(
    replacement_prefix: str,
    *,
    verify_only: bool = False,
    runner_path: str = RUNNER_PATH,
    runner_sha256: str = RUNNER_SHA256,
    original_prefix: str = ORIGINAL_PREFIX,
) -> str:
    """Load the pinned runner and replace only its shard-output identity."""
    wrapper = (
        "from hashlib import sha256\n"
        "from pathlib import Path\n"
        "import sys\n"
        f"path=Path({runner_path!r})\n"
        "raw=path.read_bytes()\n"
        f"expected_sha={runner_sha256!r}\n"
        "if sha256(raw).hexdigest()!=expected_sha:\n"
        " raise RuntimeError('ATLAS repair4 pinned runner source differs')\n"
        "sys.path.insert(0,str(path.parent))\n"
        "ns={'__name__':'atlas_matched_diversity_repair4_base',"
        "'__file__':str(path)}\n"
        "exec(compile(raw,str(path),'exec'),ns)\n"
        f"original_prefix={original_prefix!r}\n"
        "if ns.get('SHARDED_OUTPUT_PREFIX')!=original_prefix:\n"
        " raise RuntimeError('ATLAS repair4 original output prefix differs')\n"
        f"replacement_prefix={replacement_prefix!r}\n"
        "ns['SHARDED_OUTPUT_PREFIX']=replacement_prefix\n"
        "if ns.get('SHARDED_OUTPUT_PREFIX')!=replacement_prefix:\n"
        " raise RuntimeError('ATLAS repair4 replacement output prefix differs')\n"
    )
    if verify_only:
        wrapper += (
            "print('ATLAS_REPAIR4_PREFIX_PATCH_VERIFIED',expected_sha,"
            "original_prefix,replacement_prefix,flush=True)\n"
        )
    else:
        wrapper += "ns['main']()\n"
    encoded = base64.b64encode(wrapper.encode("utf-8")).decode("ascii")
    return f"exec(__import__('base64').b64decode({encoded!r}))"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replacement-prefix", required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    print(render(args.replacement_prefix, verify_only=args.verify_only))


if __name__ == "__main__":
    main()
