#!/bin/bash
# Require 30 clean generation cells, then launch the frozen audit image.
# Usage: cloud_finish_tabpfn_sis_pass_tail_exact80_v1.sh <AUDIT_IMAGE@sha256:...> <AUDIT_CODE_SHA>
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
AUDIT_IMG=${1:-}
AUDIT_CODE=${2:-}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sis-pass-tail-runs/20260814-sis-pass-tail-exact80-v1"
MANIFEST="$OUT/manifest.txt"
LIST="$OUT/executions.txt"
PHASE_S_REPORT="$ROOT/reports/sis-asoe-phase-s-runs/20260813-sis-asoe-phase-s-v1/report.json"
CACHE="$ROOT/reports/tabpfn-sis-pass-tail-runs/20260813-tabpfn-sis-pass-tail-v1/validation.json"
FINAL="$ROOT/reports/tabpfn-sis-pass-tail-runs/20260813-tabpfn-sis-pass-tail-final-served-v1/report.json"

case "$AUDIT_IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
case "$AUDIT_CODE" in ''|*[!0-9a-f]*) echo "ABORT: lowercase hexadecimal audit code required"; exit 2;; esac
[ -s "$MANIFEST" ] && [ -s "$LIST" ] || { echo "ABORT: pass-tail manifest/executions missing"; exit 2; }
[ "$(wc -l < "$LIST")" = 30 ] || { echo "ABORT: pass-tail panel needs exactly 30 cells"; exit 2; }
[ ! -e "$OUT/analyzer_execution.txt" ] || { echo "ABORT: immutable analyzer already launched"; exit 2; }
GEN_IMG=$(awk -F= '$1=="generation_image" {print $2}' "$MANIFEST")
GEN_CODE=$(awk -F= '$1=="generation_code_sha" {print $2}' "$MANIFEST")
PHASE_S_ARM=$(awk -F= '$1=="phase_s_arm" {print $2}' "$MANIFEST")
case "$PHASE_S_ARM" in control|treatment) ;; *) echo "ABORT: invalid Phase S branch"; exit 2;; esac
[ "$(sha256sum "$PHASE_S_REPORT" | awk '{print $1}')" = \
  "$(awk -F= '$1=="phase_s_report_sha256" {print $2}' "$MANIFEST")" ] || {
  echo "ABORT: Phase S report changed after launch"; exit 2; }
[ "$(sha256sum "$CACHE" | awk '{print $1}')" = \
  "$(awk -F= '$1=="cache_validation_sha256" {print $2}' "$MANIFEST")" ] || {
  echo "ABORT: cache validation changed after launch"; exit 2; }
[ "$(sha256sum "$FINAL" | awk '{print $1}')" = \
  "$(awk -F= '$1=="final_served_report_sha256" {print $2}' "$MANIFEST")" ] || {
  echo "ABORT: final-served report changed after launch"; exit 2; }

while read -r arm rep season panel job execution; do
  gcloud run jobs executions describe "$execution" --project "$PROJECT" \
    --region "$REGION" --format=json \
    | "$ROOT/.venv/bin/python" "$ROOT/scripts/verify_tabpfn_sis_pass_tail_exact80_execution.py" \
      --arm "$arm" --replicate "$rep" --season "$season" \
      --panel "$panel" --job "$job" --execution "$execution" \
      --image "$GEN_IMG" --code-sha "$GEN_CODE" --phase-s-arm "$PHASE_S_ARM" || {
        echo "ABORT: $arm R$rep $season execution provenance/status differs"; exit 1; }
done < "$LIST"

PHASE_S_SHA=$(sha256sum "$PHASE_S_REPORT" | awk '{print $1}')
CACHE_SHA=$(sha256sum "$CACHE" | awk '{print $1}')
FINAL_SHA=$(sha256sum "$FINAL" | awk '{print $1}')
JOB=analyze-sis-pass-tail-exact80-v1
ARGS="scripts/analyze_tabpfn_sis_pass_tail_exact80_v1.py,--expected-code-sha,$GEN_CODE,--phase-s-arm,$PHASE_S_ARM,--phase-s-report-sha,$PHASE_S_SHA,--cache-validation-sha,$CACHE_SHA,--final-served-sha,$FINAL_SHA"
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
  "phase_s_arm=$PHASE_S_ARM" "phase_s_report_sha256=$PHASE_S_SHA" \
  "cache_validation_sha256=$CACHE_SHA" "final_served_report_sha256=$FINAL_SHA" \
  > "$OUT/analyzer_manifest.txt"
printf '%s\n' "$EXEC" > "$OUT/analyzer_execution.txt"
echo "TABPFN_SIS_PASS_TAIL_EXACT80_V1_ANALYZER_LAUNCHED $EXEC"
