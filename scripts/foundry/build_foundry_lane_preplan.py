"""Build one Foundry v7 lane preplan (a: source tasks 0-27, b: 28-53).

The v6 single-batch design died with its task-0 producer (one non-optimal
cell terminally fails a batch, and finish-batch demands all of a batch's
tasks accepted, so a 54-task batch cannot survive one consumed failed
launch). v7 splits the same 54 source slates into two half-batches on two
REUSED jobs so the lanes run concurrently and a single-task failure burns
only that lane. The panel for the frozen R6 preregistration is the union
of both lanes' accepted tasks — the same 54 source slates, split fixed
before any lane score exists.

Usage (py311, from anywhere):
  python scripts/foundry/build_foundry_lane_preplan.py --lane a|b

Reads the lane's build-metadata receipt (captured from the accepted
image build) and the frozen worktree; templates from the retained v6
preplan. Zero cloud writes.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

ROOT_REPO = Path("/home/erich/projects/nfl-predictions")
TEMPLATE = (
    ROOT_REPO / "reports/corpus-parametric-runs/"
    "20260822-foundry-production-v6/foundation-live/preplan.json"
)
BUCKET_PREFIX = (
    "gs://nfl-predictions-503414-corpus-parametric/research/"
    "corpus-parametric-research"
)
IMAGE_REPO = "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs"

LANES = {
    "a": {"task_indexes": list(range(0, 28))},
    "b": {"task_indexes": list(range(28, 54))},
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", required=True, choices=sorted(LANES))
    parser.add_argument(
        "--expected-commit", required=True,
        help="frozen worktree commit the image was built from",
    )
    parser.add_argument(
        "--worktree", required=True, type=Path,
        help="clean worktree checked out at --expected-commit",
    )
    args = parser.parse_args()
    lane = LANES[args.lane]
    lane_id = f"v7{args.lane}"
    run_root = ROOT_REPO / (
        f"reports/corpus-parametric-runs/20260823-foundry-production-{lane_id}"
    )
    build_metadata = run_root / f"governance-live-{lane_id}/build-metadata.json"
    output = run_root / "foundation-live/preplan.json"

    worktree = args.worktree
    sys.path.insert(0, str(worktree / "scripts"))
    sys.path.insert(0, str(worktree / "src"))
    import prepare_corpus_parametric_batch_v1 as prep

    head = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if head != args.expected_commit or dirty:
        raise SystemExit(f"worktree differs: head={head} dirty={bool(dirty)}")

    build = json.loads(build_metadata.read_bytes())
    if build["status"] != "SUCCESS":
        raise SystemExit(f"build not successful: {build['status']}")
    if build["source"]["gitSource"]["revision"] != args.expected_commit:
        raise SystemExit("build revision differs from expected commit")
    images = build["results"]["images"]
    if len(images) != 1:
        raise SystemExit(f"build emitted {len(images)} images, expected 1")
    image_digest = images[0]["digest"]

    template = json.loads(TEMPLATE.read_bytes())
    values = {
        key: value for key, value in template.items()
        if key not in {"schema_version", "preplan_sha256"}
    }
    code_source = dict(values["code_source"])
    code_source["cloud_build_id"] = build["id"]
    code_source["source_commit_sha"] = args.expected_commit
    code_source["immutable_image"] = {
        "digest": image_digest,
        "uri": f"{IMAGE_REPO}@{image_digest}",
    }
    code_source["implementation_sha256"] = {
        path: sha256((worktree / path).read_bytes()).hexdigest()
        for path in sorted(code_source["implementation_sha256"])
    }
    code_source["build_definition_sha256"] = {
        path: sha256((worktree / path).read_bytes()).hexdigest()
        for path in sorted(code_source["build_definition_sha256"])
    }
    values["code_source"] = code_source

    batch_id = f"20260823-corpus-parametric-production-batch-{lane_id}"
    foundation_id = (
        f"20260823-corpus-parametric-production-foundation-{lane_id}"
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    values.update({
        "batch_id": batch_id,
        "foundation_id": foundation_id,
        "batch_output_prefix": f"{BUCKET_PREFIX}/batches/{batch_id}/",
        "foundation_prefix": f"{BUCKET_PREFIX}/foundations/{foundation_id}/",
        "mode": "production",
        "source_task_indexes": list(lane["task_indexes"]),
        "created_at_utc": now,
        "accepted_at_utc": now,
    })

    preplan = prep.build_preplan(**values)
    raw = prep.canonical_json_bytes(preplan)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing preplan: {output}")
    output.write_bytes(raw)
    print(json.dumps({
        "lane": args.lane,
        "output": str(output),
        "bytes": len(raw),
        "preplan_sha256": preplan["preplan_sha256"],
        "task_count": len(preplan["source_task_indexes"]),
        "source_task_indexes": (
            f"{lane['task_indexes'][0]}..{lane['task_indexes'][-1]}"
        ),
        "image_digest": image_digest,
        "cloud_build_id": build["id"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
