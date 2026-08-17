#!/usr/bin/env bash
set -uo pipefail

# Usage: watch_atlas_repair6_queue.sh <image@sha256:...> <code-sha> <build-id>

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
REPAIR5="$ROOT/reports/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair5"
REPAIR6="$ROOT/reports/atlas-matched-diversity-runs/20260817-atlas-matched-diversity-mvp-v1-repair6"
HISTORICAL="$ROOT/reports/atlas-historical-score-runs/20260817-atlas-historical-score-diagnostic-v4"
PARITY="$ROOT/reports/atlas-interaction-parity-runs/20260816-atlas-interaction-parity-v1"
AMENDMENT="$ROOT/reports/2026-08-17-atlas-repair6-queue-order-amendment.md"
AMENDMENT_SHA=73f6a049789a2a695653d8085fd8d21587cb2a1b9bd97207ab4a65f90918910c
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable ATLAS repair6 image is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: exact ATLAS repair6 code commit is required" >&2; exit 2; }
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "ERROR: exact ATLAS repair6 build ID is required" >&2; exit 2; }
[ "$(sha256sum "$AMENDMENT" | awk '{print $1}')" = "$AMENDMENT_SHA" ] || {
  echo "ERROR: ATLAS repair6 queue amendment differs" >&2; exit 2; }
git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}" || exit $?
for RELATIVE in \
  reports/2026-08-17-atlas-repair6-identity-tiebreak-extension-protocol.md \
  reports/2026-08-17-atlas-repair6-queue-order-amendment.md \
  scripts/prepare_atlas_repair6_classification.py \
  scripts/cloud_atlas_repair6_dual_canary.sh \
  scripts/finish_atlas_repair6_dual_canary.py \
  scripts/cloud_atlas_repair6_grid.sh \
  scripts/finish_atlas_repair6_hybrid_population.py \
  scripts/watch_atlas_repair6_queue.sh; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: ATLAS repair6 queue source differs: $RELATIVE" >&2; exit 2; }
done

execution_status() {
  gcloud run jobs executions describe "$1" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)'
}

while true; do
  unknown=0
  while read -r _season _week _job execution _uri; do
    state=$(execution_status "$execution") || exit $?
    [ "$state" = Unknown ] && unknown=$((unknown + 1))
  done < "$REPAIR5/executions.txt"
  printf '%s ATLAS_REPAIR6_WAITING_FOR_REPAIR5 running=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$unknown"
  [ "$unknown" -eq 0 ] && break
  sleep 300
done

if [ ! -s "$REPAIR5/attempt-resolution.json" ]; then
  "$ROOT/scripts/cloud_prepare_atlas_matched_diversity_repair5_attempts.sh"
  attempt_rc=$?
  if [ "$attempt_rc" -ne 0 ] && [ "$attempt_rc" -ne 10 ]; then
    exit "$attempt_rc"
  fi
fi
if [ ! -s "$REPAIR5/terminal-census-completion.txt" ]; then
  "$ROOT/scripts/cloud_harvest_atlas_repair5_terminal_census.sh" || exit $?
fi
if [ ! -s "$REPAIR6/classification-completion.txt" ]; then
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
    "$ROOT/scripts/prepare_atlas_repair6_classification.py"
  classification_rc=$?
else
  classification_rc=0
fi

if [ "$classification_rc" -ne 0 ] || \
    ! grep -qx 'disposition=repair6-dual-canary-licensed' \
      "$REPAIR6/classification-completion.txt"; then
  echo "ATLAS_REPAIR6_CLOSED_RELEASING_CONTINUOUS_PARITY"
  "$ROOT/scripts/cloud_atlas_interaction_parity_diagnostic.sh" || exit $?
else
  if [ ! -s "$REPAIR6/canary-executions.txt" ]; then
    "$ROOT/scripts/cloud_atlas_repair6_dual_canary.sh" \
      "$IMAGE" "$CODE_SHA" "$BUILD_ID" || exit $?
  fi
  while true; do
    unknown=0; succeeded=0; failed=0
    while read -r _role _season _week _job execution _uri; do
      state=$(execution_status "$execution") || exit $?
      case "$state" in
        Unknown) unknown=$((unknown + 1)) ;;
        True) succeeded=$((succeeded + 1)) ;;
        *) failed=$((failed + 1)) ;;
      esac
    done < "$REPAIR6/canary-executions.txt"
    printf '%s ATLAS_REPAIR6_CANARY_STATUS running=%s succeeded=%s failed=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$unknown" "$succeeded" "$failed"
    [ "$unknown" -eq 0 ] && break
    sleep 300
  done
  [ "$failed" -eq 0 ] || {
    echo "ATLAS_REPAIR6_DUAL_CANARY_FAILED"; exit 10; }
  if [ ! -s "$REPAIR6/canary-completion.txt" ]; then
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
      "$ROOT/scripts/finish_atlas_repair6_dual_canary.py" || exit $?
  fi
  if [ ! -s "$REPAIR6/repair6-executions.txt" ]; then
    "$ROOT/scripts/cloud_atlas_repair6_grid.sh" || exit $?
  fi
  while true; do
    unknown=0; succeeded=0; failed=0
    while read -r _season _week _primary _job execution _uri; do
      state=$(execution_status "$execution") || exit $?
      case "$state" in
        Unknown) unknown=$((unknown + 1)) ;;
        True) succeeded=$((succeeded + 1)) ;;
        *) failed=$((failed + 1)) ;;
      esac
    done < "$REPAIR6/repair6-executions.txt"
    printf '%s ATLAS_REPAIR6_GRID_STATUS running=%s succeeded=%s failed=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$unknown" "$succeeded" "$failed"
    [ "$unknown" -eq 0 ] && break
    sleep 300
  done
  [ "$failed" -eq 0 ] || {
    echo "ATLAS_REPAIR6_GRID_FAILED"; exit 10; }
  if [ ! -s "$REPAIR6/hybrid-completion.txt" ]; then
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
      "$ROOT/scripts/finish_atlas_repair6_hybrid_population.py" || exit $?
  fi
  while [ ! -s "$HISTORICAL/queue-completion.txt" ]; do
    printf '%s ATLAS_REPAIR6_WAITING_FOR_HISTORICAL_V4\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    sleep 300
  done
  "$ROOT/scripts/cloud_atlas_interaction_parity_diagnostic.sh" || exit $?
fi

read -r _season _week _seed _job parity_execution _uri \
  < "$PARITY/execution.txt"
while true; do
  state=$(execution_status "$parity_execution") || exit $?
  printf '%s ATLAS_CONTINUOUS_PARITY_AFTER_REPAIR6_STATUS state=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$state"
  [ "$state" != Unknown ] && break
  sleep 60
done
"$ROOT/scripts/cloud_finish_atlas_interaction_parity_diagnostic.sh"
