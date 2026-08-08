#!/bin/bash
# Run the memory-heavy canonical panel acceptance gate on Cloud Run.
#
# Usage:
#   bash scripts/cloud_accept_panel.sh <IMAGE@sha256:...> <PANEL_RUN_ID> check
#   bash scripts/cloud_accept_panel.sh <IMAGE@sha256:...> <PANEL_RUN_ID> promote
set -euo pipefail

IMG=${1:-}
PANEL=${2:-}
MODE=${3:-check}
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/panel-runs/$PANEL"
EXECS="$OUT/executions.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$PANEL" in ""|*[!A-Za-z0-9_-]*) echo "ABORT: invalid panel id"; exit 2;; esac
case "$MODE" in check|promote) ;; *) echo "ABORT: mode is check or promote"; exit 2;; esac
[ -s "$EXECS" ] || { echo "ABORT: missing execution manifest $EXECS"; exit 2; }

# Never ask acceptance to interpret an incomplete or failed panel.
while read -r _season _job exec_id; do
  state=$(gcloud run jobs executions describe "$exec_id" --region "$REGION" \
    --format='value(status.conditions[0].status)')
  succeeded=$(gcloud run jobs executions describe "$exec_id" --region "$REGION" \
    --format='value(status.succeededCount)')
  failed=$(gcloud run jobs executions describe "$exec_id" --region "$REGION" \
    --format='value(status.failedCount)')
  # Cloud Run leaves zero-valued counters unset, so an omitted failedCount is
  # the normal representation of zero rather than an incomplete status.
  failed=${failed:-0}
  [ "$state" = "True" ] && [ "$succeeded" = "1" ] && [ "$failed" = "0" ] || {
    echo "ABORT: $exec_id is not a clean success (status=$state succeeded=$succeeded failed=$failed)"
    exit 1
  }
done < "$EXECS"

ARGS="scripts/harvest_accept.py,$PANEL"
[ "$MODE" = "promote" ] && ARGS="$ARGS,--promote"
JOB="accept-replay-panel"
gcloud run jobs deploy "$JOB" --image "$IMG" --region "$REGION" \
  --command python --args "$ARGS" \
  --set-env-vars GCP_PROJECT=nfl-predictions-503414 \
  --memory 8Gi --cpu 2 --max-retries 0 --task-timeout 3600 >/dev/null
EXEC=$(gcloud run jobs execute "$JOB" --region "$REGION" --async \
  --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: acceptance execution id missing"; exit 1; }
echo "$EXEC" > "$OUT/acceptance_${MODE}_execution.txt"

while true; do
  state=$(gcloud run jobs executions describe "$EXEC" --region "$REGION" \
    --format='value(status.conditions[0].status)')
  [ "$state" = "True" ] && break
  # Cloud Run can publish completionTime a few seconds before the Completed
  # condition transitions from Unknown to True.  completionTime therefore
  # cannot distinguish success from failure; only an explicit False can.
  if [ "$state" = "False" ]; then
    echo "ABORT: acceptance execution failed: $EXEC"
    exit 1
  fi
  sleep 30
done

gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\"" \
  --project=nfl-predictions-503414 --limit=5000 --order=asc \
  --format='value(textPayload)' > "$OUT/acceptance_${MODE}.txt"
grep -q 'ACCEPTANCE PASSED' "$OUT/acceptance_${MODE}.txt" || {
  echo "ABORT: success marker absent from acceptance logs"; exit 1; }
echo "Acceptance $MODE passed: $OUT/acceptance_${MODE}.txt"
