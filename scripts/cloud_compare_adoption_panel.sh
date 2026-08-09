#!/bin/bash
# Compare an accepted/promoted source with a staging treatment in Cloud Run.
# Usage: cloud_compare_adoption_panel.sh <IMAGE@sha256:...> <SOURCE> <TREATMENT> [blend|ensemble|salary|member_world|candidate_budget] [N_ENTRIES]
set -euo pipefail

IMG=${1:-}
SOURCE=${2:-}
TREATMENT=${3:-}
MECHANISM=${4:-}
N_ENTRIES=${5:-40}
REGION=us-central1
PROJECT=nfl-predictions-503414
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/panel-runs/$TREATMENT"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$SOURCE" in ""|*[!A-Za-z0-9_-]*) echo "ABORT: invalid source panel"; exit 2;; esac
case "$TREATMENT" in ""|*[!A-Za-z0-9_-]*) echo "ABORT: invalid treatment panel"; exit 2;; esac
case "$MECHANISM" in
  ""|blend|ensemble|salary|member_world|candidate_budget) ;;
  *) echo "ABORT: unsupported mechanism"; exit 2;;
esac
case "$N_ENTRIES" in ""|*[!0-9]*) echo "ABORT: invalid entry count"; exit 2;; esac
[ "$N_ENTRIES" -ge 1 ] && [ "$N_ENTRIES" -le 150 ] || {
  echo "ABORT: entry count must be from 1 through 150"; exit 2; }
[ -d "$OUT" ] || { echo "ABORT: treatment report directory absent: $OUT"; exit 2; }

ARGS="scripts/compare_adoption_panel.py,$SOURCE,$TREATMENT,--entries-expected,$N_ENTRIES"
[ -z "$MECHANISM" ] || ARGS="$ARGS,--mechanism,$MECHANISM"
JOB=compare-adoption-panel
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python --args "$ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 8Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null

DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: comparator deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: comparator execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/comparison_execution.txt"

harvest_logs() {
  gcloud logging read \
    "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND jsonPayload.disposition:*" \
    --project "$PROJECT" --limit 10 --order asc \
    --format='json(jsonPayload)' > "$OUT/comparison.json"
}

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = "True" ] && break
  if [ "$STATE" = "False" ]; then
    # Mechanism-invalid comparisons deliberately exit non-zero; preserve the
    # diagnostic report before failing the wrapper.
    harvest_logs
    echo "ABORT: adoption comparator failed: $EXEC"
    exit 1
  fi
  sleep 30
done

harvest_logs
grep -q '"disposition"' "$OUT/comparison.json" || {
  echo "ABORT: comparison report absent from structured logs"; exit 1; }
echo "Adoption comparison complete: $OUT/comparison.json"
