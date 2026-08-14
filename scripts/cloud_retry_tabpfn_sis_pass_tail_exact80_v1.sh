#!/bin/bash
# Retry only the exact-80 analyzer after its verified pandas BOOL audit defect.
# Usage: cloud_retry_tabpfn_sis_pass_tail_exact80_v1.sh <IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
IMG=${1:-}
CODE_SHA=${2:-}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sis-pass-tail-runs/20260814-sis-pass-tail-exact80-v1"
ORIGINAL_EXEC=$(tr -d '[:space:]' < "$OUT/analyzer_execution.txt")
ORIGINAL_MANIFEST="$OUT/analyzer_manifest.txt"
RETRY_EXEC_FILE="$OUT/analyzer_retry_execution.txt"
RETRY_MANIFEST="$OUT/analyzer_retry_manifest.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable retry image required"; exit 2;; esac
case "$CODE_SHA" in ''|*[!0-9a-f]*) echo "ABORT: lowercase hexadecimal retry code required"; exit 2;; esac
[ -s "$ORIGINAL_MANIFEST" ] || { echo "ABORT: original analyzer manifest missing"; exit 2; }
[ ! -e "$RETRY_EXEC_FILE" ] && [ ! -e "$RETRY_MANIFEST" ] && \
  [ ! -e "$OUT/report.json" ] || {
    echo "ABORT: exact-80 analyzer retry/output already exists"; exit 2; }

STATE=$(gcloud run jobs executions describe "$ORIGINAL_EXEC" \
  --project "$PROJECT" --region "$REGION" \
  --format='value(status.conditions[0].status)')
[ "$STATE" = False ] || { echo "ABORT: original analyzer did not fail"; exit 2; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$ORIGINAL_EXEC\""
LOG=$(gcloud logging read "$FILTER" --project "$PROJECT" --limit 500 \
  --order=asc --format='value(textPayload)')
grep -Fq 'TypeError: numpy boolean subtract' <<< "$LOG" || {
  echo "ABORT: registered pandas BOOL failure evidence absent"; exit 2; }
grep -Fq 'feature_invariance_audit' <<< "$LOG" || {
  echo "ABORT: failure did not occur in the frozen feature audit"; exit 2; }

GEN_CODE=$(awk -F= '$1=="generation_code_sha" {print $2}' "$ORIGINAL_MANIFEST")
PHASE_S_ARM=$(awk -F= '$1=="phase_s_arm" {print $2}' "$ORIGINAL_MANIFEST")
PHASE_S_SHA=$(awk -F= '$1=="phase_s_report_sha256" {print $2}' "$ORIGINAL_MANIFEST")
CACHE_SHA=$(awk -F= '$1=="cache_validation_sha256" {print $2}' "$ORIGINAL_MANIFEST")
FINAL_SHA=$(awk -F= '$1=="final_served_report_sha256" {print $2}' "$ORIGINAL_MANIFEST")
case "$PHASE_S_ARM" in control|treatment) ;; *) echo "ABORT: invalid Phase S arm"; exit 2;; esac

JOB=analyze-sis-pass-tail-exact80-v1
ARGS="scripts/analyze_tabpfn_sis_pass_tail_exact80_v1.py,--expected-code-sha,$GEN_CODE,--phase-s-arm,$PHASE_S_ARM,--phase-s-report-sha,$PHASE_S_SHA,--cache-validation-sha,$CACHE_SHA,--final-served-sha,$FINAL_SHA"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python --args "$ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 16Gi --cpu 4 \
  --max-retries 0 --task-timeout 7200 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || { echo "ABORT: retry analyzer image differs"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: retry analyzer execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$RETRY_EXEC_FILE"
printf '%s\n' \
  "retry_image=$IMG" "retry_code_sha=$CODE_SHA" \
  "prior_execution=$ORIGINAL_EXEC" \
  'retry_reason=pandas_nullable_boolean_subtraction_in_mechanical_audit' \
  "generation_code_sha=$GEN_CODE" "phase_s_arm=$PHASE_S_ARM" \
  "phase_s_report_sha256=$PHASE_S_SHA" \
  "cache_validation_sha256=$CACHE_SHA" \
  "final_served_report_sha256=$FINAL_SHA" > "$RETRY_MANIFEST"
echo "TABPFN_SIS_PASS_TAIL_EXACT80_V1_ANALYZER_RETRIED $EXEC"
