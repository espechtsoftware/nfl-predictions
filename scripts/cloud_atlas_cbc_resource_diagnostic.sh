#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-cbc-resource-diagnostic-v1
OUT="$ROOT/reports/atlas-cbc-resource-diagnostic-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-cbc-resource-diagnostic-runs/$RUN_ID
PROTOCOL="$ROOT/reports/2026-08-16-atlas-cbc-resource-diagnostic-protocol.md"
SOURCE="$ROOT/scripts/run_atlas_cbc_resource_diagnostic.py"
IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb
CODE_SHA=60f296fdad769b30c0bb7334118698f156e462b9

[ ! -e "$OUT" ] || { echo "ERROR: ATLAS CBC resource diagnostic local run exists" >&2; exit 2; }
if gcloud storage ls "$PREFIX/**" --recursive --project "$PROJECT" 2>/dev/null | head -1 | grep -q .; then
  echo "ERROR: ATLAS CBC resource diagnostic cloud run exists" >&2; exit 2
fi
mkdir -p "$OUT"
PROTOCOL_SHA=$(sha256sum "$PROTOCOL" | awk '{print $1}')
SOURCE_SHA=$(sha256sum "$SOURCE" | awk '{print $1}')
SOURCE_B64=$(base64 -w0 "$SOURCE")
PY_COMMAND="exec(__import__('base64').b64decode('$SOURCE_B64'))"

printf '%s\n' \
  "run_id=$RUN_ID" "protocol_sha256=$PROTOCOL_SHA" \
  "diagnostic_source_sha256=$SOURCE_SHA" "repair2_code_sha=$CODE_SHA" \
  "repair2_image=$IMAGE" "cells=2024-7,2024-15,2024-16" \
  'uses_realized_outcomes=false' 'persists_lineups=false' \
  > "$OUT/manifest.txt"

: > "$OUT/executions.txt"
for WEEK in 7 15 16; do
  JOB=atlas-cbc-resource-diag-2024-w${WEEK}-v1
  ARTIFACT_PREFIX=$PREFIX/season-2024-week-$WEEK
  gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
    --image "$IMAGE" --command python \
    --args=-c,"$PY_COMMAND",--season,2024,--week,"$WEEK",--artifact-prefix,"$ARTIFACT_PREFIX" \
    --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE",ATLAS_CBC_RESOURCE_PROTOCOL_SHA256="$PROTOCOL_SHA",ATLAS_CBC_RESOURCE_SOURCE_SHA256="$SOURCE_SHA" \
    --service-account "$SERVICE_ACCOUNT" --cpu 1 --memory 4Gi \
    --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 12h --quiet
  EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
    --region "$REGION" --async --format='value(metadata.name)')
  [ -n "$EXEC" ] || { echo "ERROR: ATLAS CBC resource execution missing" >&2; exit 2; }
  printf '2024 %s %s %s %s\n' "$WEEK" "$JOB" "$EXEC" "$ARTIFACT_PREFIX" \
    | tee -a "$OUT/executions.txt"
done
sha256sum "$OUT/manifest.txt" "$OUT/executions.txt" > "$OUT/launch.sha256"
echo "ATLAS_CBC_RESOURCE_DIAGNOSTIC_LAUNCHED $RUN_ID"
