"""Print (or append) one v7 lane's env exports from durable receipts.

Reads the lane's foundation execute-result.json and its captured
build-metadata.json and emits the export lines for
scripts/foundry/foundry_v7<lane>_env.sh — publication identities and the
immutable image — so no hash is ever retyped by hand. With --append it
appends the block exactly once (refuses if already present). Role paths
were verified against the real v5/v6 execute-result structure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path("/home/erich/projects/nfl-predictions")
IMAGE_REPO = "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs"

ROLES = (
    ("FOUNDATION_PUBLICATION", ("publication_identity",)),
    ("MANIFEST", ("publication", "full_manifest")),
    ("EVIDENCE_CONTRACT", ("publication", "full_evidence_contract")),
    ("RETRIEVAL_PREREQUISITE", ("publication", "accepted_retrieval_prerequisite")),
)


def _walk(doc: object, path: tuple[str, ...]) -> object:
    value = doc
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise SystemExit(f"receipt path absent: {'/'.join(path)}")
        value = value[key]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", required=True, choices=("a", "b"))
    parser.add_argument("--append", action="store_true")
    args = parser.parse_args()
    lane_id = f"v7{args.lane}"
    run_root = ROOT / (
        f"reports/corpus-parametric-runs/20260823-foundry-production-{lane_id}"
    )
    result = json.loads(
        (run_root / "foundation-live/execute-result.json").read_bytes()
    )
    build = json.loads(
        (run_root / f"governance-live-{lane_id}/build-metadata.json").read_bytes()
    )
    if build["status"] != "SUCCESS":
        raise SystemExit(f"build not successful: {build['status']}")
    images = build["results"]["images"]
    if len(images) != 1:
        raise SystemExit("build image count differs")

    lines = [
        "",
        "# Appended from execute-result.json + build-metadata.json by",
        f"# append_foundry_lane_identities.py --lane {args.lane} — never "
        "edit by hand.",
        f"export CORPUS_PARAMETRIC_IMAGE={IMAGE_REPO}@{images[0]['digest']}",
    ]
    for name, path in ROLES:
        identity = _walk(result, path)
        for suffix in ("uri", "generation", "sha256", "bytes"):
            if suffix not in identity:
                raise SystemExit(f"identity {name} lacks {suffix}")
            value = identity[suffix]
            quoted = f"'{value}'" if suffix == "uri" else value
            lines.append(
                f"export CORPUS_PARAMETRIC_{name}_{suffix.upper()}={quoted}"
            )
    block = "\n".join(lines) + "\n"
    print(block, end="")
    if args.append:
        env_file = ROOT / f"scripts/foundry/foundry_{lane_id}_env.sh"
        existing = env_file.read_text()
        if "export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_URI" in existing:
            print("refused: identities already appended", file=sys.stderr)
            return 2
        env_file.write_text(existing + block)
        print(f"appended to {env_file}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
