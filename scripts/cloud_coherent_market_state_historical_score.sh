#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_coherent_market_state_historical_score.sh <image@sha256:...> <code-sha> <build-id>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260817-coherent-market-state-historical-score-v1
OUT="$ROOT/reports/coherent-market-state-historical-score-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/coherent-market-state-historical-score-runs/$RUN_ID
UPSTREAM_ID=20260816-coherent-market-state-scorefree-v1
UPSTREAM="$ROOT/reports/coherent-market-state-runs/$UPSTREAM_ID"
UPSTREAM_PREFIX=gs://nfl-predictions-503414-raw/research/coherent-market-state-runs/$UPSTREAM_ID
PROTOCOL="$ROOT/reports/2026-08-17-coherent-market-state-historical-score-protocol.md"
PROTOCOL_SHA=80d85a6af930ee7640ce0e2733a5aee4293cdf3c6102f7659b2d991671464274
RUNNER="$ROOT/scripts/run_coherent_market_state_historical_score.py"
FINISHER="$ROOT/scripts/cloud_finish_coherent_market_state_historical_score.sh"
LAUNCHER="$ROOT/scripts/cloud_coherent_market_state_historical_score.sh"
WATCHER="$ROOT/scripts/watch_coherent_market_state_historical_score_queue.sh"
ATTEMPT_VALIDATOR="$ROOT/scripts/validate_coherent_market_state_attempts.py"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable coherent-state historical image is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full coherent-state historical source commit is required" >&2; exit 2; }
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "ERROR: successful coherent-state historical build ID is required" >&2; exit 2; }
git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}" || {
  echo "ERROR: coherent-state historical source commit is unavailable" >&2; exit 2; }
for RELATIVE in \
  Dockerfile cloudbuild.yaml \
  reports/2026-08-17-coherent-market-state-historical-score-protocol.md \
  scripts/run_coherent_market_state_historical_score.py \
  scripts/cloud_coherent_market_state_historical_score.sh \
  scripts/cloud_finish_coherent_market_state_historical_score.sh \
  scripts/watch_coherent_market_state_historical_score_queue.sh \
  src/nfl_dfs/analysis/coherent_market_state_historical.py \
  scripts/aggregate_coherent_market_state_scorefree.py \
  scripts/validate_coherent_market_state_attempts.py; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: coherent-state historical built source differs: $RELATIVE" >&2; exit 2; }
done
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || {
  echo "ERROR: coherent-state historical protocol differs" >&2; exit 2; }

for NAME in manifest.txt executions.txt retry-executions.txt \
  accepted-executions.txt attempt-resolution.json completion.txt \
  execution-metadata.sha256 object-metadata.sha256 shards.sha256 report.json \
  report.sha256 report-upload.json report-upload.sha256; do
  [ -e "$UPSTREAM/$NAME" ] || {
    echo "ERROR: coherent-state historical upstream lacks $NAME" >&2; exit 2; }
done
for DIRECTORY in execution-metadata object-metadata shards; do
  [ -d "$UPSTREAM/$DIRECTORY" ] || {
    echo "ERROR: coherent-state historical upstream lacks $DIRECTORY" >&2; exit 2; }
done
[ "$(wc -l < "$UPSTREAM/accepted-executions.txt")" = 54 ] && \
  [ "$(find "$UPSTREAM/shards" -maxdepth 1 -name 'slate-*.json' | wc -l)" = 54 ] && \
  [ "$(find "$UPSTREAM/object-metadata" -maxdepth 1 -name 'slate-*.json' | wc -l)" = 54 ] || {
  echo "ERROR: coherent-state historical upstream population differs" >&2; exit 2; }
# The producing finisher recorded absolute paths from ITS checkout, so
# these checks must verify the files at checkout-independent run-relative
# paths (digests unchanged). Without this, the check silently verifies
# the PRODUCER checkout while it survives and hard-fails after any
# reboot. Same defect class and repair record as the attempt validator:
# reports/2026-08-18-coherent-historical-path-identity-repair.md.
for LEDGER in report.sha256 report-upload.sha256 execution-metadata.sha256 \
  object-metadata.sha256 shards.sha256; do
  (cd "$UPSTREAM" && sed -E \
    's#^([0-9a-f]{64})  .*/coherent-market-state-runs/[^/]+/#\1  #' \
    "$UPSTREAM/$LEDGER" | sha256sum --check - >/dev/null) || {
    echo "ERROR: coherent-state historical upstream hash ledger differs: $LEDGER" >&2
    exit 2
  }
done
"$ROOT/.venv/bin/python" "$ATTEMPT_VALIDATOR" \
  --output-dir "$UPSTREAM" --manifest "$UPSTREAM/manifest.txt"
"$ROOT/.venv/bin/python" - "$UPSTREAM/report.json" \
  "$UPSTREAM/completion.txt" <<'PY'
import json, sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
completion = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line
)
if report.get("version") != "coherent-market-state-scorefree-report-v1" or \
        report.get("historical_scoring_licensed") is not True or \
        report.get("mechanical") != {
            "seasons": [2023, 2024, 2025], "slates": 54,
            "heldout_folds": 270, "source_artifacts": 270,
            "added_candidates": 3240, "removed_candidates": 3240,
            "all_valid": True,
        } or completion.get("historical_scoring_licensed") != "true" or \
        completion.get("executions") != "54" or \
        completion.get("slates") != "54" or completion.get("folds") != "270":
    raise SystemExit("ERROR: coherent-state historical upstream license differs")
PY

[ ! -e "$OUT" ] || {
  echo "ERROR: immutable coherent-state historical local run exists" >&2; exit 3; }
for NAME in upstream-receipt.json report.json; do
  if gcloud storage objects describe "$PREFIX/$NAME" --project "$PROJECT" \
      >/dev/null 2>&1; then
    echo "ERROR: immutable coherent-state historical output exists: $NAME" >&2
    exit 3
  fi
done

mkdir -p "$OUT"
gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format=json \
  > "$OUT/build-metadata.json"
"$ROOT/.venv/bin/python" - "$OUT/build-metadata.json" "$IMAGE" "$CODE_SHA" <<'PY'
import json, sys
b = json.load(open(sys.argv[1], encoding="utf-8"))
image, code = sys.argv[2:]
digest = image.rsplit("@", 1)[1]
tag = f"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:coherent-market-historical-{code[:7]}"
images = b.get("results", {}).get("images", [])
steps = {row.get("id"): row.get("status") for row in b.get("steps", [])}
if b.get("status") != "SUCCESS" or b.get("substitutions", {}).get("_IMAGE") != tag or \
        not any(row.get("digest") == digest and row.get("name") == tag for row in images) or \
        steps.get("full-test-suite") != "SUCCESS" or \
        steps.get("smoke-atlas-mvp-runner") != "SUCCESS":
    raise SystemExit("ERROR: coherent-state historical validation build differs")
PY

RECEIPT="$OUT/upstream-receipt.json"
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" - \
  "$UPSTREAM" "$UPSTREAM_PREFIX" "$RECEIPT" \
  "$PREFIX/upstream-receipt.json" <<'PY'
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sys

from google.cloud import storage
from run_cbwu_seed_order_audit import _upload_create_only

upstream, prefix, target = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
target_uri = sys.argv[4]
manifest = dict(
    line.split("=", 1)
    for line in (upstream / "manifest.txt").read_text().splitlines() if "=" in line
)
report = json.loads((upstream / "report.json").read_text())
completion = dict(
    line.split("=", 1)
    for line in (upstream / "completion.txt").read_text().splitlines() if "=" in line
)
gcs = storage.Client(project="nfl-predictions-503414")

def object_receipt(uri, metadata_path, local_path):
    # The scorer recomputes each live object's receipt with
    # blob.updated.isoformat(); harvest-time update_time strings carry a
    # different representation (+0000, no microseconds) and can never
    # compare equal — the fourth checkout/representation identity defect
    # of 2026-08-18 (record: the path-identity repair report, addendum).
    # Live-derive generation/updated exactly as the scorer will, and
    # require the live generation to EQUAL the harvest-time generation —
    # a strictly stronger pin: any re-upload since harvest fails closed.
    metadata = json.loads(metadata_path.read_text())
    raw = local_path.read_bytes()
    blob = gcs.bucket(uri[5:].split("/", 1)[0]).blob(uri[5:].split("/", 1)[1])
    blob.reload()
    value = {
        "uri": uri,
        "generation": str(blob.generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
        "updated": blob.updated.isoformat() if blob.updated else "",
    }
    if not value["generation"].isdigit() or int(metadata.get("size", -1)) != len(raw):
        raise SystemExit("ERROR: coherent-state historical upstream object differs")
    if str(metadata.get("generation", "")) != value["generation"]:
        raise SystemExit(
            "ERROR: coherent-state historical upstream object regenerated since harvest")
    if int(blob.size or -1) != len(raw):
        raise SystemExit("ERROR: coherent-state historical upstream object size differs")
    return value

shards = []
for season in (2023, 2024, 2025):
    for week in range(1, 19):
        uri = f"{prefix}/slate-{season}-{week}.json"
        value = object_receipt(
            uri,
            upstream / "object-metadata" / f"slate-{season}-{week}.json",
            upstream / "shards" / f"slate-{season}-{week}.json",
        )
        shards.append({"season": season, "week": week, **value})
report_uri = f"{prefix}/report.json"
blob = gcs.bucket(report_uri[5:].split("/", 1)[0]).blob(
    report_uri[5:].split("/", 1)[1]
)
blob.reload()
report_raw = (upstream / "report.json").read_bytes()
report_object = {
    "uri": report_uri, "generation": str(blob.generation),
    "sha256": sha256(report_raw).hexdigest(), "bytes": len(report_raw),
    "updated": blob.updated.isoformat() if blob.updated else "",
}
if int(blob.size or -1) != len(report_raw):
    raise SystemExit("ERROR: coherent-state historical upstream report differs")
strict = {
    name: sha256((upstream / filename).read_bytes()).hexdigest()
    for name, filename in {
        "manifest": "manifest.txt",
        "primary_executions": "executions.txt",
        "retry_executions": "retry-executions.txt",
        "accepted_executions": "accepted-executions.txt",
        "attempt_resolution": "attempt-resolution.json",
        "completion": "completion.txt",
        "execution_metadata": "execution-metadata.sha256",
        "object_metadata": "object-metadata.sha256",
        "shards": "shards.sha256",
        "report": "report.json",
        "report_upload": "report-upload.json",
    }.items()
}
accepted = []
execution_metadata = {}
for line in (upstream / "accepted-executions.txt").read_text().splitlines():
    season_text, week_text, job, execution, uri = line.split()
    accepted.append({
        "season": int(season_text), "week": int(week_text), "job": job,
        "execution": execution, "uri": uri,
    })
    path = upstream / "execution-metadata" / f"{execution}.json"
    execution_metadata[execution] = json.loads(path.read_text())
if len(accepted) != 54 or len(execution_metadata) != 54:
    raise SystemExit("ERROR: coherent-state historical accepted receipt differs")
payload = {
    "version": "coherent-market-state-historical-upstream-receipt-v1",
    "run_id": "20260816-coherent-market-state-scorefree-v1",
    "uses_realized_outcomes": False,
    "historical_scoring_licensed": True,
    "code_sha": manifest["code_sha"], "image": manifest["image"],
    "primary_executions": 54, "accepted_execution_count": 54,
    "slates": 54, "folds": 270,
    "scorefree_gate_passed": report["gate"]["passes_scorefree_gate"],
    "scorefree_disposition": report["gate"]["disposition"],
    "strict_harvest_sha256": strict,
    "report_object": report_object,
    "shard_objects": shards,
    "accepted_executions": accepted,
    "execution_metadata": execution_metadata,
}
raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
target.write_bytes(raw)
upload = _upload_create_only(gcs, target_uri, raw)
print("COHERENT_MARKET_STATE_HISTORICAL_UPSTREAM_RECEIPT " + json.dumps(upload, sort_keys=True))
PY
sha256sum "$RECEIPT" > "$OUT/upstream-receipt.sha256"

printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "build_id=$BUILD_ID" "output_prefix=$PREFIX" \
  "protocol_sha256=$PROTOCOL_SHA" \
  "runner_sha256=$(sha256sum "$RUNNER" | awk '{print $1}')" \
  "finisher_sha256=$(sha256sum "$FINISHER" | awk '{print $1}')" \
  "launcher_sha256=$(sha256sum "$LAUNCHER" | awk '{print $1}')" \
  "watcher_sha256=$(sha256sum "$WATCHER" | awk '{print $1}')" \
  "upstream_run_id=$UPSTREAM_ID" \
  "upstream_manifest_sha256=$(sha256sum "$UPSTREAM/manifest.txt" | awk '{print $1}')" \
  "upstream_completion_sha256=$(sha256sum "$UPSTREAM/completion.txt" | awk '{print $1}')" \
  "upstream_receipt_sha256=$(sha256sum "$RECEIPT" | awk '{print $1}')" \
  'uses_realized_outcomes=true' 'production_change_licensed=false' \
  'canonical_fold=R0' 'seasons=2023,2024,2025' 'slates=54' \
  'cpu=4' 'memory=16Gi' 'timeout_seconds=7200' 'max_retries=0' \
  > "$OUT/manifest.txt"

JOB=coherent-market-historical-v1
URI="$PREFIX/report.json"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --command python \
  --args scripts/run_coherent_market_state_historical_score.py,--upstream-receipt-uri,"$PREFIX/upstream-receipt.json",--output-uri,"$URI" \
  --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
  --service-account "$SERVICE_ACCOUNT" --cpu 4 --memory 16Gi \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 2h --quiet >/dev/null
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[[ "$EXEC" == "$JOB-"* ]] || {
  echo "ERROR: coherent-state historical execution identity is missing" >&2; exit 2; }
printf '%s %s %s\n' "$JOB" "$EXEC" "$URI" > "$OUT/execution.txt"
sha256sum "$OUT/manifest.txt" "$OUT/execution.txt" \
  "$OUT/upstream-receipt.json" > "$OUT/launch.sha256"
echo "COHERENT_MARKET_STATE_HISTORICAL_LAUNCHED $RUN_ID"
