#!/bin/bash
# Launch a dependence-only conditional-template panel on an immutable image.
# Usage: bash scripts/cloud_dependence_panel.sh <IMAGE@sha256:...> <RUN_ID>
set -euo pipefail

IMG=${1:-}
RUN_ID=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/dependence-runs/$RUN_ID"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$RUN_ID" in ""|*[!A-Za-z0-9_-]*) echo "ABORT: invalid run id"; exit 2;; esac
[ ! -e "$OUT/executions.txt" ] || {
  echo "ABORT: dependence run already exists: $RUN_ID"; exit 2; }
mkdir -p "$OUT"
printf 'image=%s\nrun_id=%s\nseasons=2023 2024 2025\nmode=forest\n' \
  "$IMG" "$RUN_ID" > "$OUT/manifest.txt"
: > "$OUT/executions.txt"

SMOKE_JOB=conditional-schaake-smoke
gcloud run jobs deploy "$SMOKE_JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python \
  --args scripts/run_conditional_schaake_smoke.py \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 2Gi --cpu 1 \
  --max-retries 0 --task-timeout 600 >/dev/null
SMOKE_EXEC=$(gcloud run jobs execute "$SMOKE_JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
printf '%s\n' "$SMOKE_EXEC" > "$OUT/smoke_execution.txt"
smoke_image=$(gcloud run jobs executions describe "$SMOKE_EXEC" \
  --project "$PROJECT" --region "$REGION" \
  --format='value(spec.template.spec.containers[0].image)')
[ "$smoke_image" = "$IMG" ] || {
  echo "ABORT: $SMOKE_EXEC image mismatch"; exit 1; }
while true; do
  state=$(gcloud run jobs executions describe "$SMOKE_EXEC" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.conditions[0].status)')
  [ "$state" = "True" ] && break
  [ "$state" != "False" ] || { echo "ABORT: smoke failed"; exit 1; }
  sleep 20
done

for season in 2023 2024 2025; do
  job="dependence-forest-$season"
  gcloud run jobs deploy "$job" --project "$PROJECT" --region "$REGION" \
    --image "$IMG" --command nfl-dfs \
    --args "replay,--season,$season,--contest,gpp,--entries,80" \
    --set-env-vars "GCP_PROJECT=$PROJECT,GAME_SIM_MODE=possession,SCHAAKE_DIAG=1,SCHAAKE_DIAG_STRICT=1,SCHAAKE_DIAG_ONLY=1,SCHAAKE_TEMPLATE_MODE=forest" \
    --memory 16Gi --cpu 4 --max-retries 0 --task-timeout 3600 >/dev/null
  execution=$(gcloud run jobs execute "$job" --project "$PROJECT" \
    --region "$REGION" --async --format='value(metadata.name)')
  deployed=$(gcloud run jobs executions describe "$execution" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(spec.template.spec.containers[0].image)')
  [ "$deployed" = "$IMG" ] || {
    echo "ABORT: $execution image mismatch"; exit 1; }
  printf '%s %s %s\n' "$season" "$job" "$execution" \
    | tee -a "$OUT/executions.txt"
done
