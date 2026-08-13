#!/bin/bash
# Require all twelve frozen seed panels to succeed, then run the mechanical
# audit and five-replicate report atomically in Cloud.
# Usage: cloud_finish_incumbent_seed_variance_panel.sh
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-incumbent-seed-variance-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/incumbent-seed-variance-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
[ -s "$MANIFEST" ] || { echo "ABORT: seed panel manifest missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable seed report already exists"; exit 2; }
IMG=$(awk -F= '$1=="image" {print $2}' "$MANIFEST")
CODE_SHA=$(awk -F= '$1=="code_sha" {print $2}' "$MANIFEST")
[ -n "$IMG" ] && [ -n "$CODE_SHA" ] || {
  echo "ABORT: image or code SHA missing"; exit 2; }

for list in "$OUT"/r?_executions.txt; do
  [ -s "$list" ] || { echo "ABORT: execution list missing: $list"; exit 2; }
  while read -r season job exec; do
    STATE=$(gcloud run jobs executions describe "$exec" --project "$PROJECT" \
      --region "$REGION" --format='value(status.conditions[0].status)')
    [ "$STATE" = True ] || {
      echo "ABORT: $exec ($season/$job) is not complete ($STATE)"; exit 1; }
  done < "$list"
done

JOB=analyze-incumbent-seed-variance-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python \
  --args "scripts/analyze_incumbent_seed_variance.py,--expected-code-sha,$CODE_SHA" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 16Gi --cpu 4 \
  --max-retries 0 --task-timeout 7200 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: seed analyzer deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: seed analyzer execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/analyzer_execution.txt"
echo "INCUMBENT_SEED_VARIANCE_ANALYZER_LAUNCHED $EXEC"

