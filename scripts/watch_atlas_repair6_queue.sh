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
WAIT_REPAIR="$ROOT/reports/2026-08-17-atlas-repair6-accepted-retry-wait-repair.md"
WAIT_REPAIR_SHA=3f4c420e64ffbebc29de247a3a2cdc43f9cf8af15b3d7b965b8dabb52a9d44b7
CLOSURE_REPAIR="$ROOT/reports/2026-08-17-atlas-repair6-closure-release-repair.md"
CLOSURE_REPAIR_SHA=1bd230b83f326489a2944f2e3e8db87d5d21907695df0beae0f0642712f2393b
CLOSURE="$REPAIR6/queue-closure.txt"
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
[ "$(sha256sum "$WAIT_REPAIR" | awk '{print $1}')" = "$WAIT_REPAIR_SHA" ] || {
  echo "ERROR: ATLAS repair6 accepted-retry wait repair differs" >&2; exit 2; }
[ "$(sha256sum "$CLOSURE_REPAIR" | awk '{print $1}')" = "$CLOSURE_REPAIR_SHA" ] || {
  echo "ERROR: ATLAS repair6 closure-release repair differs" >&2; exit 2; }
git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}" || exit $?
for RELATIVE in \
  reports/2026-08-17-atlas-repair6-identity-tiebreak-extension-protocol.md \
  reports/2026-08-17-atlas-repair6-queue-order-amendment.md \
  reports/2026-08-17-atlas-repair6-accepted-retry-wait-repair.md \
  reports/2026-08-17-atlas-repair6-closure-release-repair.md \
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

run_continuous_parity() {
  "$ROOT/scripts/cloud_atlas_interaction_parity_diagnostic.sh" || return $?
  read -r _season _week _seed _job parity_execution _uri \
    < "$PARITY/execution.txt" || return $?
  while true; do
    state=$(execution_status "$parity_execution") || return $?
    printf '%s ATLAS_CONTINUOUS_PARITY_AFTER_REPAIR6_STATUS state=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$state"
    [ "$state" != Unknown ] && break
    sleep 60
  done
  "$ROOT/scripts/cloud_finish_atlas_interaction_parity_diagnostic.sh"
}

repair6_closure_is_valid() {
  [ -s "$CLOSURE" ] && [ -s "$REPAIR6/queue-closure.sha256" ] && \
    sha256sum -c "$REPAIR6/queue-closure.sha256" >/dev/null 2>&1 && \
    [ "$(wc -l < "$CLOSURE")" = 6 ] && \
    [ "$(grep -c '^reason=' "$CLOSURE")" = 1 ] && \
    grep -qx 'disposition=repair6-closed-no-scoreable-population' "$CLOSURE" && \
    grep -qx 'uses_realized_outcomes=false' "$CLOSURE" && \
    grep -qx 'candidate_or_lineup_scores_read=false' "$CLOSURE" && \
    grep -qx 'production_change_licensed=false' "$CLOSURE" && \
    grep -Eq '^recorded_at=[0-9]{4}-[0-9]{2}-[0-9]{2}T' "$CLOSURE" || return 1
  recorded_reason=$(awk -F= '$1=="reason" {print substr($0,8)}' "$CLOSURE")
  case "$recorded_reason" in
    failure-classification-closed|dual-canary-execution-failed|\
repair6-grid-execution-failed|hybrid-population-invalid) return 0 ;;
    *) return 1 ;;
  esac
}

record_repair6_closure() {
  reason=$1
  case "$reason" in
    failure-classification-closed|dual-canary-execution-failed|\
repair6-grid-execution-failed|hybrid-population-invalid) ;;
    *) echo "ERROR: unknown ATLAS repair6 closure reason" >&2; return 2 ;;
  esac
  if [ -s "$CLOSURE" ]; then
    repair6_closure_is_valid && grep -qx "reason=$reason" "$CLOSURE" || {
      echo "ERROR: ATLAS repair6 closure receipt differs" >&2; return 2; }
    return 0
  fi
  [ ! -e "$CLOSURE" ] || {
    echo "ERROR: empty ATLAS repair6 closure receipt exists" >&2; return 2; }
  pending=$(mktemp "$REPAIR6/.queue-closure.XXXXXX") || return $?
  printf '%s\n' \
    'disposition=repair6-closed-no-scoreable-population' \
    "reason=$reason" \
    'uses_realized_outcomes=false' \
    'candidate_or_lineup_scores_read=false' \
    'production_change_licensed=false' \
    "recorded_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$pending"
  mv "$pending" "$CLOSURE"
  sha256sum "$CLOSURE" > "$REPAIR6/queue-closure.sha256"
  repair6_closure_is_valid || {
    echo "ERROR: ATLAS repair6 closure receipt failed validation" >&2
    return 2
  }
}

close_repair6_and_release_parity() {
  reason=$1
  record_repair6_closure "$reason" || return $?
  printf 'ATLAS_REPAIR6_CLOSED reason=%s RELEASING_CONTINUOUS_PARITY\n' "$reason"
  run_continuous_parity
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
if [ -s "$REPAIR5/accepted-executions.txt" ]; then
  while true; do
    unknown=0; succeeded=0; failed=0
    while read -r _season _week _job execution _uri; do
      state=$(execution_status "$execution") || exit $?
      case "$state" in
        Unknown) unknown=$((unknown + 1)) ;;
        True) succeeded=$((succeeded + 1)) ;;
        *) failed=$((failed + 1)) ;;
      esac
    done < "$REPAIR5/accepted-executions.txt"
    printf '%s ATLAS_REPAIR6_WAITING_FOR_REPAIR5_ACCEPTED running=%s succeeded=%s failed=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$unknown" "$succeeded" "$failed"
    [ "$unknown" -eq 0 ] && break
    sleep 300
  done
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
  close_repair6_and_release_parity failure-classification-closed
  exit $?
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
  if [ "$failed" -ne 0 ]; then
    close_repair6_and_release_parity dual-canary-execution-failed
    exit $?
  fi
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
  if [ "$failed" -ne 0 ]; then
    close_repair6_and_release_parity repair6-grid-execution-failed
    exit $?
  fi
  if [ ! -s "$REPAIR6/hybrid-completion.txt" ]; then
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
      "$ROOT/scripts/finish_atlas_repair6_hybrid_population.py" || exit $?
  fi
  if ! grep -qx 'disposition=valid-complete-repair6-hybrid-population' \
      "$REPAIR6/hybrid-completion.txt"; then
    close_repair6_and_release_parity hybrid-population-invalid
    exit $?
  fi
  while [ ! -s "$HISTORICAL/queue-completion.txt" ]; do
    printf '%s ATLAS_REPAIR6_WAITING_FOR_HISTORICAL_V4\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    sleep 300
  done
  run_continuous_parity
  exit $?
fi
