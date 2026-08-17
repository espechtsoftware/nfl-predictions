#!/usr/bin/env bash
set -uo pipefail

# Carry the score-free lattice queue through support and resource preflight.
# The scientific treatment grid intentionally remains a separate later launch.

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
CODE_SHA=e6916decd1e455ab7c0be852f640ec4d63ddae6b
BUILD_ID=edc9f90d-b118-4b50-8d7d-dda42196cec1
TAG=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:constraint-support-e6916de
SUPPORT="$ROOT/reports/constraint-lattice-support-runs/20260816-constraint-lattice-control-support-census-v1"
RESOURCE="$ROOT/reports/constraint-lattice-resource-preflight-runs/20260816-constraint-lattice-resource-preflight-v1"

execution_status() {
  gcloud run jobs executions describe "$1" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)'
}

while true; do
  BUILD_STATUS=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
    --format='value(status)') || exit $?
  printf '%s CONSTRAINT_SUPPORT_BUILD_STATUS status=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$BUILD_STATUS"
  case "$BUILD_STATUS" in
    SUCCESS) break ;;
    QUEUED|PENDING|WORKING) sleep 60 ;;
    *) exit 2 ;;
  esac
done

DIGEST=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
  --format='value(results.images[0].digest)') || exit $?
[[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 2
IMAGE="${TAG%@*}@${DIGEST}"

while [ ! -e "$SUPPORT" ]; do
  "$ROOT/scripts/cloud_constraint_lattice_support_census.sh" \
    "$IMAGE" "$CODE_SHA" "$BUILD_ID"
  RC=$?
  if [ "$RC" -eq 0 ]; then
    break
  fi
  [ ! -e "$SUPPORT" ] || exit "$RC"
  printf '%s CONSTRAINT_SUPPORT_QUEUE_NOT_RELEASED rc=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$RC"
  sleep 300
done

while true; do
  unknown=0
  while read -r _season _week _job execution _uri; do
    state=$(execution_status "$execution") || exit $?
    [ "$state" = Unknown ] && unknown=$((unknown + 1))
  done < "$SUPPORT/executions.txt"
  printf '%s CONSTRAINT_SUPPORT_PRIMARY_STATUS running=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$unknown"
  [ "$unknown" -eq 0 ] && break
  sleep 300
done

"$ROOT/scripts/cloud_prepare_constraint_lattice_attempts.sh" support
ATTEMPT_RC=$?
[ "$ATTEMPT_RC" -eq 0 ] || exit "$ATTEMPT_RC"
while true; do
  unknown=0
  failed=0
  while read -r _season _week _job execution _uri; do
    state=$(execution_status "$execution") || exit $?
    case "$state" in
      Unknown) unknown=$((unknown + 1)) ;;
      True) ;;
      *) failed=$((failed + 1)) ;;
    esac
  done < "$SUPPORT/accepted-executions.txt"
  printf '%s CONSTRAINT_SUPPORT_ACCEPTED_STATUS running=%s failed=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$unknown" "$failed"
  [ "$unknown" -eq 0 ] && break
  sleep 300
done
[ "$failed" -eq 0 ] || exit 10
"$ROOT/scripts/cloud_finish_constraint_lattice_support_census.sh" || exit $?

DISPOSITION=$("$ROOT/.venv/bin/python" -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["disposition"])' \
  "$SUPPORT/report.json") || exit $?
if [ "$DISPOSITION" != p230-supported-original-gate-complete ]; then
  echo "CONSTRAINT_SUPPORT_STOPS_BEFORE_RESOURCE $DISPOSITION"
  exit 0
fi

"$ROOT/scripts/cloud_constraint_lattice_resource_preflight.sh" \
  "$IMAGE" "$CODE_SHA" "$BUILD_ID" || exit $?
read -r _job RESOURCE_EXECUTION _uri < "$RESOURCE/execution.txt"
while true; do
  state=$(execution_status "$RESOURCE_EXECUTION") || exit $?
  printf '%s CONSTRAINT_LATTICE_RESOURCE_STATUS state=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$state"
  [ "$state" != Unknown ] && break
  sleep 300
done
"$ROOT/scripts/cloud_finish_constraint_lattice_resource_preflight.sh"
