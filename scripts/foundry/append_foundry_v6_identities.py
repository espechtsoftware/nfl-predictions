"""Print (or append) the v6 env exports from durable receipts.

Reads the v6 foundation execute-result.json and the captured
build-metadata.json and emits the export lines for
scripts/foundry/foundry_v6_env.sh — publication identities and the
immutable image — so no hash is ever retyped by hand. With --append it
appends the block to the env file exactly once (refuses if any of the
variables are already present).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path("/home/erich/projects/nfl-predictions")
RUN_ROOT = ROOT / "reports/corpus-parametric-runs/20260822-foundry-production-v6"
EXECUTE_RESULT = RUN_ROOT / "foundation-live/execute-result.json"
BUILD_METADATA = RUN_ROOT / "governance-live-v6/build-metadata.json"
ENV_FILE = ROOT / "scripts/foundry/foundry_v6_env.sh"
IMAGE_REPO = "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs"

# Verified against the v5 execute-result: the foundation publication's own
# identity is the top-level publication_identity; the other three live
# under publication/ as full_manifest, full_evidence_contract, and
# accepted_retrieval_prerequisite.
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
    parser.add_argument("--append", action="store_true")
    args = parser.parse_args()

    result = json.loads(EXECUTE_RESULT.read_bytes())
    build = json.loads(BUILD_METADATA.read_bytes())
    if build["status"] != "SUCCESS":
        raise SystemExit(f"build not successful: {build['status']}")
    images = build["results"]["images"]
    if len(images) != 1:
        raise SystemExit("build image count differs")

    lines = [
        "",
        "# Appended from execute-result.json + build-metadata.json by",
        "# append_foundry_v6_identities.py — never edit by hand.",
        "export CORPUS_PARAMETRIC_IMAGE="
        f"{IMAGE_REPO}@{images[0]['digest']}",
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
        existing = ENV_FILE.read_text()
        if "CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_URI=" in existing.replace(
            "#   CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_*", ""
        ) and "export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_URI" in existing:
            print("refused: identities already appended", file=sys.stderr)
            return 2
        ENV_FILE.write_text(existing + block)
        print(f"appended to {ENV_FILE}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
