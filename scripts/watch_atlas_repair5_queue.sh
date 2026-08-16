#!/usr/bin/env bash
set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
PREFLIGHT_DIR="$ROOT/reports/atlas-cbc-32g-full-cell-preflight-runs/20260816-atlas-cbc-32g-full-cell-preflight-v1"
REPAIR5_DIR="$ROOT/reports/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair5"
PARITY_DIR="$ROOT/reports/atlas-interaction-parity-runs/20260816-atlas-interaction-parity-v1"

execution_status() {
  gcloud run jobs executions describe "$1" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)'
}

while [ ! -s "$PREFLIGHT_DIR/completion.txt" ]; do sleep 30; done
if ! grep -qx 'status=True' "$PREFLIGHT_DIR/completion.txt" || \
    ! grep -qx 'disposition=full-cell-r0-complete-at-32g' \
      "$PREFLIGHT_DIR/completion.txt"; then
  echo ATLAS_REPAIR5_NOT_LICENSED_CONTINUOUS_DIRECT_BRANCH_OWNS_QUEUE
  exit 0
fi

if [ ! -s "$REPAIR5_DIR/executions.txt" ]; then
  "$ROOT/scripts/cloud_atlas_matched_diversity_repair5.sh" || exit $?
fi
while true; do
  unknown=0
  while read -r _season _week _job execution _uri; do
    state=$(execution_status "$execution") || exit $?
    [ "$state" = Unknown ] && unknown=$((unknown + 1))
  done < "$REPAIR5_DIR/executions.txt"
  printf '%s ATLAS_REPAIR5_PRIMARY_STATUS running=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$unknown"
  [ "$unknown" -eq 0 ] && break
  sleep 300
done

"$ROOT/scripts/cloud_prepare_atlas_matched_diversity_repair5_attempts.sh"
attempt_rc=$?
if [ "$attempt_rc" -ne 0 ] && [ "$attempt_rc" -ne 10 ]; then
  exit "$attempt_rc"
fi
if [ "$attempt_rc" -eq 0 ]; then
  while true; do
    unknown=0
    succeeded=0
    failed=0
    while read -r _season _week _job execution _uri; do
      state=$(execution_status "$execution") || exit $?
      case "$state" in
        Unknown) unknown=$((unknown + 1)) ;;
        True) succeeded=$((succeeded + 1)) ;;
        *) failed=$((failed + 1)) ;;
      esac
    done < "$REPAIR5_DIR/accepted-executions.txt"
    printf '%s ATLAS_REPAIR5_ACCEPTED_STATUS running=%s succeeded=%s failed=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$unknown" "$succeeded" "$failed"
    [ "$unknown" -eq 0 ] && break
    sleep 300
  done
  if [ "$failed" -eq 0 ]; then
    "$ROOT/scripts/cloud_finish_atlas_matched_diversity_repair5.sh"
    exit $?
  fi
fi

"$ROOT/scripts/cloud_harvest_atlas_repair5_terminal_census.sh" || exit $?
"$ROOT/scripts/cloud_atlas_interaction_parity_diagnostic.sh" || exit $?
read -r _season _week _seed _job parity_execution _uri \
  < "$PARITY_DIR/execution.txt"
while true; do
  state=$(execution_status "$parity_execution") || exit $?
  printf '%s ATLAS_CONTINUOUS_PARITY_AFTER_REPAIR5_STATUS state=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$state"
  if [ "$state" != Unknown ]; then
    "$ROOT/scripts/cloud_finish_atlas_interaction_parity_diagnostic.sh"
    exit $?
  fi
  sleep 60
done
