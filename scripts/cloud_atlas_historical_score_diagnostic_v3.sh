#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_atlas_historical_score_diagnostic_v3.sh <image@sha256:...> <code-sha> <build-id>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-historical-score-diagnostic-v3
OUT="$ROOT/reports/atlas-historical-score-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-historical-score-runs/$RUN_ID
RECEIPT_URI="$PREFIX/upstream-receipt.json"
REPORT_URI="$PREFIX/report.json"
PROTOCOL="$ROOT/reports/2026-08-17-atlas-historical-score-v3-execution-protocol.md"
PROTOCOL_SHA=2a4b0ed6c6a2c4b15c052968248aefd0d8a1ff519c5ec2bce5c72bfb50020e7b
SOURCE_RECEIPT="$OUT/upstream-receipt.json"
SOURCE_OBJECT="$OUT/upstream-receipt-object.json"
LEASE="$OUT/historical-outcome-lease.json"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable ATLAS historical v3 image is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: exact ATLAS historical v3 code commit is required" >&2; exit 2; }
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "ERROR: successful ATLAS historical v3 build ID is required" >&2; exit 2; }
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || {
  echo "ERROR: frozen ATLAS historical v3 execution protocol differs" >&2; exit 2; }
for REQUIRED in "$SOURCE_RECEIPT" "$SOURCE_OBJECT" \
  "$OUT/upstream-receipt.sha256" "$OUT/upstream-receipt-object.sha256"; do
  [ -s "$REQUIRED" ] || {
    echo "ERROR: ATLAS historical v3 source/lease receipt is missing: $REQUIRED" >&2
    exit 2
  }
done
for FORBIDDEN in "$OUT/manifest.txt" "$OUT/execution.txt" "$OUT/report.json" \
  "$OUT/completion.txt"; do
  [ ! -e "$FORBIDDEN" ] || {
    echo "ERROR: immutable ATLAS historical v3 launch/harvest exists" >&2; exit 3; }
done
if gcloud storage objects describe "$REPORT_URI" --project "$PROJECT" \
    >/dev/null 2>&1; then
  echo "ERROR: immutable ATLAS historical v3 report object exists" >&2; exit 3
fi

git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}"
for RELATIVE in Dockerfile cloudbuild.yaml \
  reports/2026-08-17-atlas-historical-score-v3-execution-protocol.md \
  src/nfl_dfs/research/atlas_historical_v3_sources.py \
  src/nfl_dfs/analysis/atlas_historical_score.py \
  scripts/prepare_atlas_historical_v3_source_receipt.py \
  scripts/run_atlas_historical_score_diagnostic.py \
  scripts/run_atlas_historical_score_diagnostic_v3.py \
  scripts/finish_atlas_historical_score_diagnostic_v3.py \
  scripts/cloud_atlas_historical_score_diagnostic_v3.sh \
  scripts/watch_atlas_historical_v3_queue.sh \
  scripts/historical_outcome_lease.py \
  scripts/run_cbwu_seed_order_audit.py \
  scripts/render_atlas_matched_diversity_repair4_command.py; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: ATLAS historical v3 built source differs: $RELATIVE" >&2; exit 2; }
done

SOURCE_VALUES=$(PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" - \
  "$SOURCE_RECEIPT" "$SOURCE_OBJECT" "$RECEIPT_URI" <<'PY'
import json, pathlib, sys
from nfl_dfs.research.atlas_historical_v3_sources import UPSTREAM_PREFIX, file_sha, load_json, validate_receipt
from render_atlas_matched_diversity_repair4_command import render
receipt_path, object_path = map(pathlib.Path, sys.argv[1:3]); uri=sys.argv[3]
receipt=load_json(receipt_path); obj=load_json(object_path)
validate_receipt(receipt, render(UPSTREAM_PREFIX))
digest=file_sha(receipt_path)
if obj.get("uri")!=uri or obj.get("sha256")!=digest or not str(obj.get("generation","")).isdigit() or obj.get("create_only") is not True:
 raise SystemExit("ERROR: ATLAS historical v3 immutable source object differs")
print(obj["generation"], digest)
PY
)
read -r RECEIPT_GENERATION RECEIPT_SHA <<< "$SOURCE_VALUES"

BUILD_TMP=$(mktemp)
trap 'rm -f "$BUILD_TMP"' EXIT
gcloud builds describe "$BUILD_ID" --project "$PROJECT" --region="$REGION" \
  --format=json > "$BUILD_TMP"
"$ROOT/.venv/bin/python" - "$BUILD_TMP" "$IMAGE" "$CODE_SHA" <<'PY'
import json, sys
b=json.load(open(sys.argv[1],encoding="utf-8")); image,code=sys.argv[2:]
tag=("us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:"
     f"atlas-historical-v3-{code[:7]}")
digest=image.rsplit("@",1)[1]
steps={row.get("id"):row.get("status") for row in b.get("steps",[])}
required={"full-test-suite","build-image","smoke-atlas-mvp-runner"}
if b.get("status")!="SUCCESS" or b.get("substitutions",{}).get("_IMAGE")!=tag or any(steps.get(name)!="SUCCESS" for name in required) or not any(row.get("name")==tag and row.get("digest")==digest for row in b.get("results",{}).get("images",[])):
 raise SystemExit("ERROR: ATLAS historical v3 build identity differs")
PY

JOB=atlas-historical-score-v3
EXISTING=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
  --region "$REGION" --format='value(metadata.name)' 2>/dev/null || true)
[ -z "$EXISTING" ] || {
  echo "ERROR: ATLAS historical v3 job already has an execution" >&2; exit 3; }

gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 8 --memory 32Gi \
  --max-retries 0 --task-timeout 8h --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" --command python \
  --args "scripts/run_atlas_historical_score_diagnostic_v3.py,--upstream-receipt-uri,$RECEIPT_URI,--upstream-receipt-generation,$RECEIPT_GENERATION,--upstream-receipt-sha256,$RECEIPT_SHA,--output-uri,$REPORT_URI" \
  --quiet >/dev/null
if [ ! -s "$LEASE" ]; then
  while ! PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
      "$ROOT/scripts/historical_outcome_lease.py" acquire \
      --run-id "$RUN_ID" --job "$JOB" --code-sha "$CODE_SHA" --image "$IMAGE" \
      --receipt "$LEASE"; do
    printf '%s ATLAS_HISTORICAL_V3_WAITING_FOR_OUTCOME_LEASE\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    sleep 300
  done
fi
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" - \
  "$LEASE" "$RUN_ID" "$JOB" "$IMAGE" "$CODE_SHA" <<'PY'
import pathlib, sys
from nfl_dfs.research.atlas_historical_v3_sources import load_json
lease=load_json(pathlib.Path(sys.argv[1])); run_id,job,image,code_sha=sys.argv[2:]
value=lease.get("lease",{}); obj=lease.get("object",{})
if value.get("version")!="historical-outcome-active-v1" or value.get("run_id")!=run_id or value.get("job")!=job or value.get("image")!=image or value.get("code_sha")!=code_sha or obj.get("create_only") is not True:
 raise SystemExit("ERROR: ATLAS historical v3 outcome lease differs")
PY
EXECUTION=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[[ "$EXECUTION" == "$JOB-"* ]] || {
  echo "ERROR: ATLAS historical v3 execution identity is missing" >&2; exit 2; }

MANIFEST="$OUT/manifest.txt"
printf '%s\n' \
  "run_id=$RUN_ID" "job=$JOB" "execution=$EXECUTION" \
  "image=$IMAGE" "code_sha=$CODE_SHA" "build_id=$BUILD_ID" \
  "output_prefix=$PREFIX" "output_uri=$REPORT_URI" \
  "protocol_sha256=$PROTOCOL_SHA" \
  "upstream_receipt_uri=$RECEIPT_URI" \
  "upstream_receipt_generation=$RECEIPT_GENERATION" \
  "upstream_receipt_sha256=$RECEIPT_SHA" \
  "source_module_sha256=$(sha256sum "$ROOT/src/nfl_dfs/research/atlas_historical_v3_sources.py" | awk '{print $1}')" \
  "runner_sha256=$(sha256sum "$ROOT/scripts/run_atlas_historical_score_diagnostic_v3.py" | awk '{print $1}')" \
  "finisher_sha256=$(sha256sum "$ROOT/scripts/finish_atlas_historical_score_diagnostic_v3.py" | awk '{print $1}')" \
  'tasks=1' 'parallelism=1' 'cpu=8' 'memory=32Gi' \
  'timeout_seconds=28800' 'max_retries=0' \
  'uses_realized_outcomes=true' 'production_change_licensed=false' \
  > "$MANIFEST"
printf '%s %s %s\n' "$JOB" "$EXECUTION" "$REPORT_URI" > "$OUT/execution.txt"
mv "$BUILD_TMP" "$OUT/build-metadata.json"
trap - EXIT
sha256sum "$MANIFEST" > "$OUT/manifest.sha256"
sha256sum "$OUT/execution.txt" > "$OUT/execution.txt.sha256"
echo "ATLAS_HISTORICAL_V3_LAUNCHED $EXECUTION"
