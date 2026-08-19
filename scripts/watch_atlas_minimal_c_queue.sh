#!/usr/bin/env bash
set -euo pipefail

# Queue watcher for the minimal ATLAS C test: loops until the coherent
# historical stage's report object exists, then runs the launcher exactly
# once. Rerunnable after a crash; refuses to relaunch a populated run.
#
# Usage: watch_atlas_minimal_c_queue.sh <image@sha256:...> <code-sha> <build-id>

ROOT=$(cd "$(dirname "$0")/.." && pwd)
LAUNCHER="$ROOT/scripts/cloud_atlas_minimal_c_launcher.sh"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/.+@sha256:[0-9a-f]{64}$ ]] && \
  [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] && \
  [[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "ERROR: ATLAS C watcher needs <image@digest> <code-sha> <build-id>" >&2
  exit 2; }

while :; do
  set +e
  bash "$LAUNCHER" "$IMAGE" "$CODE_SHA" "$BUILD_ID"
  STATUS=$?
  set -e
  case "$STATUS" in
    0) echo "ATLAS_C_QUEUE_COMPLETE"; exit 0 ;;
    3) printf '%s ATLAS_C_QUEUE_WAITING\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
       sleep 600 ;;
    *) echo "ATLAS_C_QUEUE_FAILED status=$STATUS" >&2; exit "$STATUS" ;;
  esac
done
