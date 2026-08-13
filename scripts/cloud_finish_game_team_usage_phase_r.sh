#!/bin/bash
# Require all 30 Phase R jobs to finish cleanly, then launch its frozen audit.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260813-game-team-usage-phase-r-v1
OUT="$ROOT/reports/game-team-usage-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
LIST="$OUT/executions.txt"
[ -s "$MANIFEST" ] && [ -s "$LIST" ] || {
  echo "ABORT: Phase R manifest/executions missing"; exit 2; }
[ ! -e "$OUT/analyzer_execution.txt" ] || {
  echo "ABORT: immutable Phase R analyzer already launched"; exit 2; }
IMG=$(awk -F= '$1=="image" {print $2}' "$MANIFEST")
CODE_SHA=$(awk -F= '$1=="code_sha" {print $2}' "$MANIFEST")
[ -n "$IMG" ] && [ -n "$CODE_SHA" ] || {
  echo "ABORT: Phase R image/code SHA missing"; exit 2; }
[ "$(wc -l < "$LIST")" = 30 ] || {
  echo "ABORT: Phase R needs exactly 30 executions"; exit 2; }

while read -r arm rep season panel job execution; do
  state=$(gcloud run jobs executions describe "$execution" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.conditions[0].status)')
  succeeded=$(gcloud run jobs executions describe "$execution" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.succeededCount)')
  failed=$(gcloud run jobs executions describe "$execution" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.failedCount)')
  failed=${failed:-0}
  [ "$state" = True ] && [ "$succeeded" = 1 ] && [ "$failed" = 0 ] || {
    echo "ABORT: $arm R$rep $season $execution is not a clean success ($state/$succeeded/$failed)"
    exit 1
  }
done < "$LIST"

JOB=analyze-game-team-usage-phase-r-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python \
  --args "scripts/analyze_game_team_usage_phase_r.py,--expected-code-sha,$CODE_SHA" \
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
echo "GAME_TEAM_USAGE_PHASE_R_ANALYZER_LAUNCHED $EXEC"
