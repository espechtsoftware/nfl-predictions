#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-cbc-16g-preflight-v1
OUT="$ROOT/reports/atlas-cbc-16g-preflight-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-cbc-16g-preflight-runs/$RUN_ID
PROTOCOL="$ROOT/reports/2026-08-16-atlas-cbc-16g-preflight-protocol.md"
SOURCE="$ROOT/scripts/run_atlas_cbc_resource_diagnostic.py"
RENDERER="$ROOT/scripts/render_atlas_cbc_16g_preflight_command.py"
PROTOCOL_SHA=4c09ba4065e5ac32af3873f149ca42c0dd922cadc21524fd277f404d7fdc45a7
SOURCE_SHA=ad0c9307b28aab0a18d511fe680f92d59075211fad2e5abfc1eddcafa0509abc
RENDERER_SHA=9d780be4e6d3d00f2553c238ece78af8046a7e0a26de096dfff1d1f984043a53
IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb
CODE_SHA=60f296fdad769b30c0bb7334118698f156e462b9

for SPEC in "$PROTOCOL:$PROTOCOL_SHA" "$SOURCE:$SOURCE_SHA" \
  "$RENDERER:$RENDERER_SHA"; do
  FILE=${SPEC%:*}
  DIGEST=${SPEC##*:}
  [ -s "$FILE" ] && [ "$(sha256sum "$FILE" | awk '{print $1}')" = "$DIGEST" ] || {
    echo "ERROR: ATLAS CBC 16 GiB preflight source differs: $FILE" >&2
    exit 2
  }
done
[ ! -e "$OUT" ] || {
  echo "ERROR: ATLAS CBC 16 GiB preflight local run exists" >&2; exit 2; }
if gcloud storage ls "$PREFIX/**" --recursive --project "$PROJECT" \
    2>/dev/null | head -1 | grep -q .; then
  echo "ERROR: ATLAS CBC 16 GiB preflight cloud run exists" >&2
  exit 2
fi

ARTIFACT_PREFIX=$PREFIX/season-2024-week-15
PY_COMMAND=$("$ROOT/.venv/bin/python" "$RENDERER" \
  --source "$SOURCE" --protocol-id "$RUN_ID" --prefix "$PREFIX")
mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "protocol_sha256=$PROTOCOL_SHA" \
  "diagnostic_source_sha256=$SOURCE_SHA" "renderer_sha256=$RENDERER_SHA" \
  "repair2_code_sha=$CODE_SHA" "repair2_image=$IMAGE" \
  "artifact_prefix=$ARTIFACT_PREFIX" 'cell=2024-15' \
  'cpu=4' 'memory=16Gi' 'max_retries=0' 'timeout_seconds=43200' \
  'uses_realized_outcomes=false' 'persists_lineups=false' \
  > "$OUT/manifest.txt"

JOB=atlas-cbc-16g-preflight-2024-w15-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --command python \
  --args=-c,"$PY_COMMAND",--season,2024,--week,15,--artifact-prefix,"$ARTIFACT_PREFIX" \
  --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE",ATLAS_CBC_RESOURCE_PROTOCOL_SHA256="$PROTOCOL_SHA",ATLAS_CBC_RESOURCE_SOURCE_SHA256="$SOURCE_SHA" \
  --service-account "$SERVICE_ACCOUNT" --cpu 4 --memory 16Gi \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 12h --quiet
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$EXEC" ] || {
  echo "ERROR: ATLAS CBC 16 GiB preflight execution missing" >&2; exit 2; }
printf '2024 15 %s %s %s\n' "$JOB" "$EXEC" "$ARTIFACT_PREFIX" \
  | tee "$OUT/execution.txt"
sha256sum "$OUT/manifest.txt" "$OUT/execution.txt" > "$OUT/launch.sha256"
echo "ATLAS_CBC_16G_PREFLIGHT_LAUNCHED $RUN_ID"

