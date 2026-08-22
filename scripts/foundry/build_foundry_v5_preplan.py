"""Build the Foundry v5 production preplan from the accepted v4 template.

Run from the clean 04d6579 worktree with Python 3.11 and PYTHONPATH=src.
Zero cloud writes: output is a local canonical JSON file for validate/dry-run.
Every hash is recomputed from the worktree or copied from durable receipts —
never retyped by hand.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

WORKTREE = Path("/tmp/nfl-predictions-corpus-04d6579")
ROOT_REPO = Path("/home/erich/projects/nfl-predictions")
TEMPLATE = (
    ROOT_REPO / "reports/corpus-parametric-runs/"
    "20260822-corpus-parametric-task0-smoke-v4/foundation-live/preplan.json"
)
OUTPUT = (
    ROOT_REPO / "reports/corpus-parametric-runs/"
    "20260822-foundry-production-v5/foundation-live/preplan.json"
)

EXPECTED_COMMIT = "04d6579394af70df7120e81c0196837d29b5ffcf"
BUILD_ID = "b2832a18-666d-4260-9d4b-619ad94aa5ae"
IMAGE_DIGEST = (
    "sha256:232c1087471f91a62e1f3a7d7036e7a344dab1c826eedc004cb027d86a2cdadd"
)
IMAGE_URI = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
    f"nfl-dfs@{IMAGE_DIGEST}"
)
BATCH_ID = "20260822-corpus-parametric-production-batch-v5"
FOUNDATION_ID = "20260822-corpus-parametric-production-foundation-v5"
BUCKET_PREFIX = (
    "gs://nfl-predictions-503414-corpus-parametric/research/"
    "corpus-parametric-research"
)


def main() -> int:
    sys.path.insert(0, str(WORKTREE / "scripts"))
    sys.path.insert(0, str(WORKTREE / "src"))
    import prepare_corpus_parametric_batch_v1 as prep

    head = subprocess.run(
        ["git", "-C", str(WORKTREE), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(WORKTREE), "status", "--porcelain"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if head != EXPECTED_COMMIT or dirty:
        raise SystemExit(f"worktree differs: head={head} dirty={bool(dirty)}")

    template = json.loads(TEMPLATE.read_bytes())
    values = {
        key: value for key, value in template.items()
        if key not in {"schema_version", "preplan_sha256"}
    }

    code_source = dict(values["code_source"])
    code_source["cloud_build_id"] = BUILD_ID
    code_source["source_commit_sha"] = EXPECTED_COMMIT
    code_source["immutable_image"] = {"digest": IMAGE_DIGEST, "uri": IMAGE_URI}
    code_source["implementation_sha256"] = {
        path: sha256((WORKTREE / path).read_bytes()).hexdigest()
        for path in sorted(code_source["implementation_sha256"])
    }
    code_source["build_definition_sha256"] = {
        path: sha256((WORKTREE / path).read_bytes()).hexdigest()
        for path in sorted(code_source["build_definition_sha256"])
    }
    values["code_source"] = code_source

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    values.update({
        "batch_id": BATCH_ID,
        "foundation_id": FOUNDATION_ID,
        "batch_output_prefix": f"{BUCKET_PREFIX}/batches/{BATCH_ID}/",
        "foundation_prefix": f"{BUCKET_PREFIX}/foundations/{FOUNDATION_ID}/",
        "mode": "production",
        "source_task_indexes": list(range(54)),
        "created_at_utc": now,
        "accepted_at_utc": now,
    })

    preplan = prep.build_preplan(**values)
    raw = prep.canonical_json_bytes(preplan)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite existing preplan: {OUTPUT}")
    OUTPUT.write_bytes(raw)
    print(json.dumps({
        "output": str(OUTPUT),
        "bytes": len(raw),
        "raw_sha256": sha256(raw).hexdigest(),
        "preplan_sha256": preplan["preplan_sha256"],
        "mode": preplan["mode"],
        "task_count": len(preplan["source_task_indexes"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
