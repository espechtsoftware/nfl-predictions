#!/bin/bash
# Relaunch only the mechanically repaired analyzer against the twelve already
# completed frozen replay tables. The original failed execution remains
# immutable and the replay panels are never rerun.
# Usage: cloud_repair_incumbent_seed_variance_analyzer.sh <IMAGE@sha256:...> <REPAIR_CODE_SHA>
set -euo pipefail

IMG=${1:-}
REPAIR_CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-incumbent-seed-variance-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/incumbent-seed-variance-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
ORIGINAL_EXECUTION="$OUT/analyzer_execution.txt"
REPAIR_EXECUTION="$OUT/analyzer_repair_execution.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable repair image required"; exit 2;; esac
case "$REPAIR_CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable repair code SHA required"; exit 2;;
esac
[ -s "$MANIFEST" ] || { echo "ABORT: seed panel manifest missing"; exit 2; }
[ -s "$ORIGINAL_EXECUTION" ] || { echo "ABORT: original analyzer execution missing"; exit 2; }
[ ! -e "$REPAIR_EXECUTION" ] || {
  echo "ABORT: immutable repaired analyzer execution already recorded"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable seed report already exists"; exit 2; }
EXPECTED_CODE_SHA=$(awk -F= '$1=="code_sha" {print $2}' "$MANIFEST")
[ -n "$EXPECTED_CODE_SHA" ] || { echo "ABORT: expected panel code SHA missing"; exit 2; }
ORIGINAL_EXEC=$(cat "$ORIGINAL_EXECUTION")
ORIGINAL_STATE=$(gcloud run jobs executions describe "$ORIGINAL_EXEC" \
  --project "$PROJECT" --region "$REGION" \
  --format='value(status.conditions[0].status)')
[ "$ORIGINAL_STATE" = False ] || {
  echo "ABORT: original analyzer is not the recorded failed execution"; exit 2; }

JOB=analyze-incumbent-seed-variance-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python \
  --args "scripts/analyze_incumbent_seed_variance.py,--expected-code-sha,$EXPECTED_CODE_SHA" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 16Gi --cpu 4 \
  --max-retries 0 --task-timeout 7200 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: seed analyzer deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: repaired seed analyzer execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$REPAIR_EXECUTION"
printf '%s\n' \
  "repair_image=$IMG" \
  "repair_code_sha=$REPAIR_CODE_SHA" \
  "expected_panel_code_sha=$EXPECTED_CODE_SHA" \
  "original_failed_execution=$ORIGINAL_EXEC" \
  "repair_execution=$EXEC" > "$OUT/analyzer_repair_manifest.txt"
echo "INCUMBENT_SEED_VARIANCE_ANALYZER_REPAIR_LAUNCHED $EXEC"
