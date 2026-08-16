#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_atlas_matched_diversity_mvp.sh <image@sha256:...> <full-code-sha>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-matched-diversity-mvp-v1-repair1
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/$RUN_ID
PROTOCOL="$ROOT/reports/2026-08-16-atlas-matched-diversity-mvp-protocol.md"
PROTOCOL_SHA=badc0d64be69694caadd8fb2fe16a293c0cfbfe1f7813b4e80dc45e10b727abf
PAIR_REACH_AMENDMENT="$ROOT/reports/2026-08-16-atlas-mvp-pair-reach-amendment.md"
PAIR_REACH_AMENDMENT_SHA=2e3734c595159d64748ab2eeec2de61194b665d43ef6854140e5378bac464a33
PACKAGING_REPAIR="$ROOT/reports/2026-08-16-atlas-mvp-image-packaging-repair.md"
PACKAGING_REPAIR_SHA=e4293fae2dcd88b7a50179f0b4a688a23a8b1961bd7da8e437544e15a64e0e62
REPAIR="$ROOT/reports/atlas-mvp-source-repair-runs/20260816-atlas-mvp-source-repair-r3-2025-v1"
REPAIR_VALIDATION_SHA=4938df8c8f7f84dea40baf2f76cd84f78cdc9e1a097c271b419e3dc8c6b5cd37
REPAIR_EXECUTION_SHA=f2bb244daf1b2d9515bee59799095fcbdd44414acb16b06e65e8298bd87c62b7
REPAIR_COMPLETION_SHA=7bbff5dd3721ba436f79cb984091e7aa5815642629ab2c5615a6f2d9aacaa592
IMAGE=${1:-}
CODE_SHA=${2:-}

[[ "$IMAGE" =~ @sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable image digest is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full code SHA is required" >&2; exit 2; }
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || {
  echo "ERROR: ATLAS MVP protocol differs" >&2; exit 2; }
[ "$(sha256sum "$PAIR_REACH_AMENDMENT" | awk '{print $1}')" = "$PAIR_REACH_AMENDMENT_SHA" ] || {
  echo "ERROR: ATLAS MVP pair-reach amendment differs" >&2; exit 2; }
[ "$(sha256sum "$PACKAGING_REPAIR" | awk '{print $1}')" = "$PACKAGING_REPAIR_SHA" ] || {
  echo "ERROR: ATLAS MVP packaging repair differs" >&2; exit 2; }
[ -s "$REPAIR/completion.txt" ] && [ -s "$REPAIR/validation.json" ] && \
    [ -s "$REPAIR/execution.json" ] || {
  echo "ERROR: strict ATLAS MVP source repair is incomplete" >&2; exit 2; }
[ "$(sha256sum "$REPAIR/validation.json" | awk '{print $1}')" = "$REPAIR_VALIDATION_SHA" ] || {
  echo "ERROR: ATLAS MVP source-repair validation differs" >&2; exit 2; }
[ "$(sha256sum "$REPAIR/execution.json" | awk '{print $1}')" = "$REPAIR_EXECUTION_SHA" ] || {
  echo "ERROR: ATLAS MVP source-repair execution differs" >&2; exit 2; }
[ "$(sha256sum "$REPAIR/completion.txt" | awk '{print $1}')" = "$REPAIR_COMPLETION_SHA" ] || {
  echo "ERROR: ATLAS MVP source-repair completion differs" >&2; exit 2; }
[ ! -e "$OUT" ] || {
  echo "ERROR: immutable ATLAS MVP run directory exists" >&2; exit 3; }
for NAME in season-2023.json season-2024.json season-2025.json report.json; do
  if gcloud storage objects describe "$PREFIX/$NAME" \
      --project "$PROJECT" >/dev/null 2>&1; then
    echo "ERROR: frozen ATLAS MVP output $NAME already exists" >&2
    exit 3
  fi
done

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "output_prefix=$PREFIX" "protocol_sha256=$PROTOCOL_SHA" \
  "pair_reach_amendment_sha256=$PAIR_REACH_AMENDMENT_SHA" \
  "packaging_repair_sha256=$PACKAGING_REPAIR_SHA" \
  "repair_validation_sha256=$REPAIR_VALIDATION_SHA" \
  "repair_execution_sha256=$REPAIR_EXECUTION_SHA" \
  "repair_completion_sha256=$REPAIR_COMPLETION_SHA" \
  'uses_realized_outcomes=false' 'production_change_licensed=false' \
  'seasons=2023,2024,2025' 'slates=54' 'native_seed_blocks=5' \
  'worlds_per_block=10000' 'atlas_additions_per_seed=40' \
  'atlas_additions_per_slate=200' 'causal_contrast=P2_vs_P1' \
  > "$OUT/manifest.txt"
: > "$OUT/executions.txt"

for SEASON in 2023 2024 2025; do
  JOB="atlas-matched-diversity-${SEASON}-v1-repair1"
  URI="$PREFIX/season-${SEASON}.json"
  gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
    --image "$IMAGE" --command python \
    --args scripts/run_atlas_matched_diversity_mvp.py,--season,"$SEASON",--output-uri,"$URI" \
    --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
    --service-account "$SERVICE_ACCOUNT" --cpu 8 --memory 32Gi \
    --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 8h --quiet
  EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
    --region "$REGION" --async --format='value(metadata.name)')
  [ -n "$EXEC" ] || {
    echo "ERROR: ATLAS MVP execution identity is missing" >&2; exit 1; }
  printf '%s %s %s %s\n' "$SEASON" "$JOB" "$EXEC" "$URI" \
    | tee -a "$OUT/executions.txt"
done
echo "ATLAS_MATCHED_DIVERSITY_MVP_LAUNCHED $RUN_ID"
