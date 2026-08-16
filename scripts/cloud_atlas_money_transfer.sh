#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_atlas_money_transfer.sh <image@sha256:...> <full-code-sha>

PROJECT=nfl-predictions-503414
REGION=us-central1
JOB=atlas-current-money-transfer-v1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
RUN_ID=20260815-atlas-current-money-transfer-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/atlas-money-transfer-runs/$RUN_ID"
ACQ="$ROOT/reports/atlas-money-world-runs/20260815-atlas-current-money-worlds-v1"
PROTOCOL="$ROOT/reports/2026-08-15-atlas-current-money-transfer-protocol.md"
PROTOCOL_SHA=c6cb9605678bdfb68f54cbc9fd7adcea754500afb838d2a17a9c0861e4527423
LAW_AMENDMENT="$ROOT/reports/2026-08-16-atlas-transfer-law-separation-amendment.md"
LAW_AMENDMENT_SHA=59326d6c8db4209a4eac44bbc80935adb8d93fb71a0b92a5d5325a30562fae54
ARTIFACT_REPAIR="$ROOT/reports/2026-08-15-atlas-money-artifact-native-repair.md"
ARTIFACT_REPAIR_SHA=d51a32aeeb8d7f4546169709c4b0a5b8e6d8ef5aebf8b8a8adbd227f54d60812
OUTPUT_URI=gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-atlas-current-money-transfer-v1/result.json
IMAGE=${1:-}
CODE_SHA=${2:-}

[[ "$IMAGE" =~ @sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable image digest is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full code SHA is required" >&2; exit 2; }
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || {
  echo "ERROR: ATLAS money-transfer protocol differs" >&2; exit 2; }
[ "$(sha256sum "$LAW_AMENDMENT" | awk '{print $1}')" = "$LAW_AMENDMENT_SHA" ] || {
  echo "ERROR: ATLAS money-transfer law amendment differs" >&2; exit 2; }
[ "$(sha256sum "$ARTIFACT_REPAIR" | awk '{print $1}')" = "$ARTIFACT_REPAIR_SHA" ] || {
  echo "ERROR: ATLAS money-transfer artifact repair differs" >&2; exit 2; }
for FILE in manifest.txt source-grid.json acquisition-complete.txt \
    execution-metadata.sha256 environment-receipts.sha256; do
  [ -s "$ACQ/$FILE" ] || {
    echo "ERROR: strict ATLAS money-world acquisition is incomplete" >&2
    exit 2
  }
done
if gcloud storage objects describe "$OUTPUT_URI" \
    --project "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: frozen ATLAS money-transfer output already exists" >&2
  exit 3
fi
[ ! -e "$OUT" ] || {
  echo "ERROR: immutable ATLAS money-transfer run directory exists" >&2
  exit 3
}

ACQ_MANIFEST_SHA=$(sha256sum "$ACQ/manifest.txt" | awk '{print $1}')
SOURCE_GRID_SHA=$(sha256sum "$ACQ/source-grid.json" | awk '{print $1}')
ACQ_COMPLETE_SHA=$(sha256sum "$ACQ/acquisition-complete.txt" | awk '{print $1}')
EXECUTION_RECEIPTS_SHA=$(sha256sum "$ACQ/execution-metadata.sha256" | awk '{print $1}')
ENVIRONMENT_RECEIPTS_SHA=$(sha256sum "$ACQ/environment-receipts.sha256" | awk '{print $1}')
mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "output_uri=$OUTPUT_URI" "protocol_sha256=$PROTOCOL_SHA" \
  "law_separation_amendment_sha256=$LAW_AMENDMENT_SHA" \
  "artifact_native_repair_sha256=$ARTIFACT_REPAIR_SHA" \
  "acquisition_manifest_sha256=$ACQ_MANIFEST_SHA" \
  "source_grid_sha256=$SOURCE_GRID_SHA" \
  "acquisition_complete_sha256=$ACQ_COMPLETE_SHA" \
  "execution_receipts_sha256=$EXECUTION_RECEIPTS_SHA" \
  "environment_receipts_sha256=$ENVIRONMENT_RECEIPTS_SHA" \
  'source_panels=20260815-atlas-money-worlds-r0-v1,20260815-atlas-money-worlds-r1-v1,20260815-atlas-money-worlds-r2-v1,20260815-atlas-money-worlds-r3-v1,20260815-atlas-money-worlds-r4-v1' \
  'uses_realized_outcomes=false' 'candidate_or_lineup_scores_read=false' \
  'slates=54' 'seed_slate_artifacts=270' 'worlds_per_artifact=10000' \
  'primary_gate=part-a-quality-three-conditions' \
  > "$OUT/manifest.txt"

gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --command python \
  --args scripts/run_atlas_money_transfer.py,--output-uri,"$OUTPUT_URI" \
  --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE",PROTOCOL_SHA256="$PROTOCOL_SHA",LAW_SEPARATION_AMENDMENT_SHA256="$LAW_AMENDMENT_SHA",ARTIFACT_NATIVE_REPAIR_SHA256="$ARTIFACT_REPAIR_SHA",ACQUISITION_MANIFEST_SHA256="$ACQ_MANIFEST_SHA",SOURCE_GRID_SHA256="$SOURCE_GRID_SHA",ACQUISITION_COMPLETE_SHA256="$ACQ_COMPLETE_SHA",EXECUTION_RECEIPTS_SHA256="$EXECUTION_RECEIPTS_SHA",ENVIRONMENT_RECEIPTS_SHA256="$ENVIRONMENT_RECEIPTS_SHA" \
  --service-account "$SERVICE_ACCOUNT" --cpu 8 --memory 32Gi \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 6h --quiet
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$EXEC" ] || {
  echo "ERROR: ATLAS money-transfer execution identity is missing" >&2
  exit 1
}
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "$EXEC"
