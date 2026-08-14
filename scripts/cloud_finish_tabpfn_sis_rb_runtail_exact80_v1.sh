#!/bin/bash
# Require 30 clean generation cells, then launch the frozen run-tail analyzer.
# Usage: cloud_finish_tabpfn_sis_rb_runtail_exact80_v1.sh <IMAGE@sha256:...> <40-char SHA>
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
AUDIT_IMG=${1:-}
AUDIT_CODE=${2:-}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sis-rb-runtail-runs/20260814-sis-runtail-exact80-v1"
MANIFEST="$OUT/manifest.txt"
LIST="$OUT/executions.txt"
CACHE="$ROOT/reports/tabpfn-sis-rb-runtail-runs/20260814-tabpfn-sis-rb-runtail-v1/validation.json"
FINAL="$ROOT/reports/tabpfn-sis-rb-runtail-runs/20260814-tabpfn-sis-rb-runtail-final-served-v1/report.json"

case "$AUDIT_IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
[[ "$AUDIT_CODE" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ABORT: full immutable audit code SHA required"; exit 2; }
[ -s "$MANIFEST" ] && [ -s "$LIST" ] || {
  echo "ABORT: run-tail manifest/executions missing"; exit 2; }
[ "$(wc -l < "$LIST")" = 30 ] || {
  echo "ABORT: run-tail panel needs exactly 30 cells"; exit 2; }
[ ! -e "$OUT/analyzer_execution.txt" ] || {
  echo "ABORT: immutable analyzer already launched"; exit 2; }
GEN_IMG=$(awk -F= '$1=="generation_image" {print $2}' "$MANIFEST")
GEN_CODE=$(awk -F= '$1=="generation_code_sha" {print $2}' "$MANIFEST")
CONTROL_SCHEDULES_JSON=$(awk -F= '$1=="control_schedules_json" {print substr($0,index($0,"=")+1)}' "$MANIFEST")
TREATMENT_SCHEDULES_JSON=$(awk -F= '$1=="treatment_schedules_json" {print substr($0,index($0,"=")+1)}' "$MANIFEST")
for value in "$GEN_IMG" "$GEN_CODE" "$CONTROL_SCHEDULES_JSON" "$TREATMENT_SCHEDULES_JSON"; do
  [ -n "$value" ] || { echo "ABORT: run-tail manifest field missing"; exit 2; }
done
[ "$(sha256sum "$CACHE" | awk '{print $1}')" = \
  "$(awk -F= '$1=="cache_validation_sha256" {print $2}' "$MANIFEST")" ] || {
  echo "ABORT: cache validation changed after launch"; exit 2; }
[ "$(sha256sum "$FINAL" | awk '{print $1}')" = \
  "$(awk -F= '$1=="final_served_report_sha256" {print $2}' "$MANIFEST")" ] || {
  echo "ABORT: final-served report changed after launch"; exit 2; }

while read -r arm rep season panel job execution; do
  gcloud run jobs executions describe "$execution" --project "$PROJECT" \
    --region "$REGION" --format=json \
    | "$ROOT/.venv/bin/python" "$ROOT/scripts/verify_tabpfn_sis_rb_runtail_exact80_execution.py" \
      --arm "$arm" --replicate "$rep" --season "$season" \
      --panel "$panel" --job "$job" --execution "$execution" \
      --image "$GEN_IMG" --code-sha "$GEN_CODE" \
      --control-schedules-json "$CONTROL_SCHEDULES_JSON" \
      --treatment-schedules-json "$TREATMENT_SCHEDULES_JSON" || {
        echo "ABORT: $arm R$rep $season execution provenance/status differs"; exit 1; }
done < "$LIST"

CACHE_SHA=$(sha256sum "$CACHE" | awk '{print $1}')
FINAL_SHA=$(sha256sum "$FINAL" | awk '{print $1}')
CONTROL_B64=$(printf '%s' "$CONTROL_SCHEDULES_JSON" | base64 -w0)
TREATMENT_B64=$(printf '%s' "$TREATMENT_SCHEDULES_JSON" | base64 -w0)
JOB=analyze-sis-runtail-exact80-v1
ARGS="scripts/analyze_tabpfn_sis_rb_runtail_exact80_v1.py,--expected-code-sha,$GEN_CODE,--control-schedules-b64,$CONTROL_B64,--treatment-schedules-b64,$TREATMENT_B64,--cache-validation-sha,$CACHE_SHA,--final-served-sha,$FINAL_SHA"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$AUDIT_IMG" --command python --args "$ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 16Gi --cpu 4 \
  --max-retries 0 --task-timeout 7200 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$AUDIT_IMG" ] || { echo "ABORT: analyzer image differs"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: analyzer execution missing"; exit 1; }
printf '%s\n' \
  "audit_image=$AUDIT_IMG" "audit_code_sha=$AUDIT_CODE" \
  "generation_image=$GEN_IMG" "generation_code_sha=$GEN_CODE" \
  "control_schedules_json=$CONTROL_SCHEDULES_JSON" \
  "treatment_schedules_json=$TREATMENT_SCHEDULES_JSON" \
  "cache_validation_sha256=$CACHE_SHA" \
  "final_served_report_sha256=$FINAL_SHA" > "$OUT/analyzer_manifest.txt"
printf '%s\n' "$EXEC" > "$OUT/analyzer_execution.txt"
echo "TABPFN_SIS_RB_RUNTAIL_EXACT80_V1_ANALYZER_LAUNCHED $EXEC"
