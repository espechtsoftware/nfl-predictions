#!/bin/bash
# Require all 30 Phase S jobs to succeed, then launch the frozen audit.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/sis-asoe-phase-s-runs/20260813-sis-asoe-phase-s-v1"
MANIFEST="$OUT/manifest.txt"
LIST="$OUT/executions.txt"
[ -s "$MANIFEST" ] && [ -s "$LIST" ] || {
  echo "ABORT: Phase S manifest/executions missing"; exit 2; }
[ ! -e "$OUT/analyzer_execution.txt" ] || {
  echo "ABORT: immutable Phase S analyzer already launched"; exit 2; }
[ "$(wc -l < "$LIST")" = 30 ] || {
  echo "ABORT: Phase S needs exactly 30 executions"; exit 2; }
IMG=$(awk -F= '$1=="image" {print $2}' "$MANIFEST")
CODE_SHA=$(awk -F= '$1=="code_sha" {print $2}' "$MANIFEST")
CONTROL=$(awk -F= '$1=="selected_control_arm" {print $2}' "$MANIFEST")
case "$CONTROL" in mult|k) ;; *) echo "ABORT: invalid control arm"; exit 2;; esac

while read -r arm rep season panel job execution; do
  gcloud run jobs executions describe "$execution" \
    --project "$PROJECT" --region "$REGION" --format=json \
    | "$ROOT/.venv/bin/python" \
      "$ROOT/scripts/verify_sis_asoe_phase_s_execution.py" \
      --arm "$arm" --replicate "$rep" --season "$season" \
      --panel "$panel" --job "$job" --execution "$execution" \
      --image "$IMG" --code-sha "$CODE_SHA" --control-arm "$CONTROL" || {
        echo "ABORT: $arm R$rep $season $execution provenance/status differs"
        exit 1
      }
done < "$LIST"

JOB=analyze-sis-asoe-phase-s-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python \
  --args "scripts/analyze_sis_asoe_phase_s.py,--expected-code-sha,$CODE_SHA,--control-arm,$CONTROL" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 16Gi --cpu 4 \
  --max-retries 0 --task-timeout 7200 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: analyzer deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: analyzer execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/analyzer_execution.txt"
echo "SIS_ASOE_PHASE_S_ANALYZER_LAUNCHED $EXEC"
