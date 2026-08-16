#!/usr/bin/env python3
"""Run the frozen exact full-cell constraint-lattice resource preflight."""

from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path

from run_constraint_lattice_scorefree import run


RUN_ID = "20260816-constraint-lattice-resource-preflight-v1"
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/"
    "constraint-lattice-resource-preflight-runs/"
    f"{RUN_ID}"
)
PROTOCOL = Path(
    "reports/2026-08-16-constraint-lattice-resource-preflight-protocol.md"
)
PROTOCOL_SHA256 = (
    "9e04ebcbcb2def607e28c5f8fa046ba4456f40e2e8a654182f654318ca579d7b"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    if not PROTOCOL.is_file() or \
            sha256(PROTOCOL.read_bytes()).hexdigest() != PROTOCOL_SHA256:
        raise RuntimeError("constraint-lattice resource protocol differs")
    print(
        "CONSTRAINT_LATTICE_RESOURCE_PROTOCOL_SHA256",
        PROTOCOL_SHA256,
        flush=True,
    )
    run(
        2023,
        1,
        args.output_uri,
        run_id=RUN_ID,
        output_prefix=OUTPUT_PREFIX,
    )


if __name__ == "__main__":
    main()
