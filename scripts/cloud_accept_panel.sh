#!/bin/bash
# Run the memory-heavy canonical panel acceptance gate on Cloud Run.
#
# Usage:
#   bash scripts/cloud_accept_panel.sh <IMAGE@sha256:...> <PANEL_RUN_ID> check [N_ENTRIES] [CAND_MULT]
#   bash scripts/cloud_accept_panel.sh <IMAGE@sha256:...> <PANEL_RUN_ID> promote [N_ENTRIES] [CAND_MULT]
# Optional sixth argument is a quoted space-separated season list for a
# preregistered partial panel, for example "2023 2024 2025".
# Optional seventh argument is `season-varying-config` for a frozen experiment
# that deliberately uses one registered config/lever specification per season.
set -euo pipefail

IMG=${1:-}
PANEL=${2:-}
MODE=${3:-check}
N_ENTRIES=${4:-40}
N_CAND_MULT=${5:-2}
SEASONS=${6:-}
CONFIG_MODE=${7:-uniform-config}
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/panel-runs/$PANEL"
EXECS="$OUT/executions.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$PANEL" in ""|*[!A-Za-z0-9_-]*) echo "ABORT: invalid panel id"; exit 2;; esac
case "$MODE" in check|promote) ;; *) echo "ABORT: mode is check or promote"; exit 2;; esac
case "$CONFIG_MODE" in
  uniform-config|season-varying-config) ;;
  *) echo "ABORT: config mode is uniform-config or season-varying-config"; exit 2;;
esac
case "$N_ENTRIES" in ""|*[!0-9]*) echo "ABORT: invalid entry count"; exit 2;; esac
[ "$N_ENTRIES" -ge 1 ] && [ "$N_ENTRIES" -le 150 ] || {
  echo "ABORT: entry count must be from 1 through 150"; exit 2; }
case "$N_CAND_MULT" in ""|*[!0-9]*) echo "ABORT: invalid candidate multiple"; exit 2;; esac
[ "$N_CAND_MULT" -ge 1 ] && [ "$N_CAND_MULT" -le 10 ] || {
  echo "ABORT: candidate multiple must be from 1 through 10"; exit 2; }
if [ -n "$SEASONS" ]; then
  read -r -a SEASON_LIST <<< "$SEASONS"
  [ "${#SEASON_LIST[@]}" -gt 0 ] || { echo "ABORT: empty seasons"; exit 2; }
  for season in "${SEASON_LIST[@]}"; do
    case "$season" in
      [2-9][0-9][0-9][0-9]) ;;
      *) echo "ABORT: invalid season '$season'"; exit 2 ;;
    esac
  done
fi
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

ARGS="scripts/harvest_accept.py,$PANEL,--entries-expected,$N_ENTRIES,--candidate-multiple-expected,$N_CAND_MULT"
[ "$CONFIG_MODE" != season-varying-config ] || \
  ARGS="$ARGS,--allow-season-varying-config"
[ -z "$SEASONS" ] || {
  ARGS="$ARGS,--seasons"
  for season in "${SEASON_LIST[@]}"; do ARGS="$ARGS,$season"; done
}
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

harvest_logs() {
  # A treatment may deliberately violate a baseline-only parity assertion.
  # Preserve the complete audit in that case instead of stranding the useful
  # completeness, score, and mechanism evidence in Cloud Logging.
  gcloud logging read \
    "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\"" \
    --project=nfl-predictions-503414 --limit=5000 --order=asc \
    --format='value(textPayload)' > "$OUT/acceptance_${MODE}.txt"
}

while true; do
  state=$(gcloud run jobs executions describe "$EXEC" --region "$REGION" \
    --format='value(status.conditions[0].status)')
  [ "$state" = "True" ] && break
  # Cloud Run can publish completionTime a few seconds before the Completed
  # condition transitions from Unknown to True.  completionTime therefore
  # cannot distinguish success from failure; only an explicit False can.
  if [ "$state" = "False" ]; then
    harvest_logs
    echo "ABORT: acceptance execution failed: $EXEC"
    exit 1
  fi
  sleep 30
done

harvest_logs
grep -q 'ACCEPTANCE PASSED' "$OUT/acceptance_${MODE}.txt" || {
  echo "ABORT: success marker absent from acceptance logs"; exit 1; }
echo "Acceptance $MODE passed: $OUT/acceptance_${MODE}.txt"
