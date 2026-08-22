"""Build the Foundry v6 production preplan from the v5 template.

v6 exists because the v4/v5 image (232c1087, commit 04d6579) carries the
CBC integer-infeasibility classification defect fixed in bcf31a7: the v4
producer failed terminally and the never-launched v5 batch is bound to the
broken image, so its namespace is burned. Run from the clean bcf31a7
worktree with Python 3.11 and PYTHONPATH=src. Zero cloud writes: output is
a local canonical JSON file for validate/dry-run.

Build identity (cloud build id + immutable image digest) is read from the
captured build-metadata receipt — never retyped by hand. Capture it after
the build succeeds with:

  gcloud builds describe <BUILD_ID> --project nfl-predictions-503414 \
    --format=json > reports/corpus-parametric-runs/\
20260822-foundry-production-v6/governance-live-v6/build-metadata.json
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

WORKTREE = Path("/tmp/nfl-predictions-corpus-bcf31a7")
ROOT_REPO = Path("/home/erich/projects/nfl-predictions")
TEMPLATE = (
    ROOT_REPO / "reports/corpus-parametric-runs/"
    "20260822-foundry-production-v5/foundation-live/preplan.json"
)
RUN_ROOT = ROOT_REPO / "reports/corpus-parametric-runs/20260822-foundry-production-v6"
BUILD_METADATA = RUN_ROOT / "governance-live-v6/build-metadata.json"
OUTPUT = RUN_ROOT / "foundation-live/preplan.json"

EXPECTED_COMMIT = "bcf31a75087a48d7207389fe6a69bf9244f73aeb"
BATCH_ID = "20260822-corpus-parametric-production-batch-v6"
FOUNDATION_ID = "20260822-corpus-parametric-production-foundation-v6"
BUCKET_PREFIX = (
    "gs://nfl-predictions-503414-corpus-parametric/research/"
    "corpus-parametric-research"
)
IMAGE_REPO = "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs"


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

    build = json.loads(BUILD_METADATA.read_bytes())
    if build["status"] != "SUCCESS":
        raise SystemExit(f"build not successful: {build['status']}")
    revision = build["source"]["gitSource"]["revision"]
    if revision != EXPECTED_COMMIT:
        raise SystemExit(f"build revision differs: {revision}")
    images = build["results"]["images"]
    if len(images) != 1:
        raise SystemExit(f"build emitted {len(images)} images, expected 1")
    image_digest = images[0]["digest"]
    build_id = build["id"]
    image_uri = f"{IMAGE_REPO}@{image_digest}"

    template = json.loads(TEMPLATE.read_bytes())
    values = {
        key: value for key, value in template.items()
        if key not in {"schema_version", "preplan_sha256"}
    }

    code_source = dict(values["code_source"])
    code_source["cloud_build_id"] = build_id
    code_source["source_commit_sha"] = EXPECTED_COMMIT
    code_source["immutable_image"] = {"digest": image_digest, "uri": image_uri}
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
        "image_digest": image_digest,
        "cloud_build_id": build_id,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
