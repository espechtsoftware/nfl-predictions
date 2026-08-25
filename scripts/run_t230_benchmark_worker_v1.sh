#!/usr/bin/env bash
# Exact GNU-time command for the sole source-ordinal-zero mechanics benchmark.

set -euo pipefail
export LC_ALL=C

required=(
  PYTHONPATH CLOUD_RUN_EXECUTION CLOUD_RUN_JOB CLOUD_RUN_TASK_INDEX
  CLOUD_RUN_TASK_ATTEMPT CLOUD_RUN_TASK_COUNT T230_IMAGE
  T230_CONTRACT_URI T230_CONTRACT_GENERATION T230_CONTRACT_SHA256
  T230_CONTRACT_BYTES T230_AUTHORITY_URI T230_AUTHORITY_GENERATION
  T230_AUTHORITY_SHA256 T230_AUTHORITY_BYTES T230_LAUNCH_REQUEST_URI
  T230_LAUNCH_REQUEST_GENERATION T230_LAUNCH_REQUEST_SHA256
  T230_LAUNCH_REQUEST_BYTES T230_LAUNCH_INTENT_URI
  T230_LAUNCH_INTENT_GENERATION T230_LAUNCH_INTENT_SHA256
  T230_LAUNCH_INTENT_BYTES T230_LAUNCH_COMPLETION_URI
  T230_LAUNCH_COMPLETION_GENERATION T230_LAUNCH_COMPLETION_SHA256
  T230_LAUNCH_COMPLETION_BYTES
)
for name in "${required[@]}"; do
  [[ -n "${!name:-}" ]] || {
    printf '%s\n' "benchmark worker missing $name" >&2
    exit 2
  }
done
[[ "${T230_PRED_COUNT:-}" == "1" && -f /tmp/predecessor-0.json ]] || {
  printf '%s\n' "benchmark worker requires the prepare predecessor" >&2
  exit 2
}

exec env PYTHONPATH="$PYTHONPATH" LC_ALL=C \
  python scripts/run_corpus_extreme_tail_panel_transport_v1.py run-stage \
  --operation run-slate --source-ordinal 0 --runtime-attempt-ordinal 0 \
  --cloud-execution-name "$CLOUD_RUN_EXECUTION" \
  --cloud-job "$CLOUD_RUN_JOB" \
  --cloud-task-index "$CLOUD_RUN_TASK_INDEX" \
  --cloud-task-attempt "$CLOUD_RUN_TASK_ATTEMPT" \
  --cloud-task-count "$CLOUD_RUN_TASK_COUNT" \
  --runtime-image "$T230_IMAGE" \
  --transport-contract-uri "$T230_CONTRACT_URI" \
  --transport-contract-generation "$T230_CONTRACT_GENERATION" \
  --transport-contract-sha256 "$T230_CONTRACT_SHA256" \
  --transport-contract-bytes "$T230_CONTRACT_BYTES" \
  --launch-request-uri "$T230_LAUNCH_REQUEST_URI" \
  --launch-request-generation "$T230_LAUNCH_REQUEST_GENERATION" \
  --launch-request-sha256 "$T230_LAUNCH_REQUEST_SHA256" \
  --launch-request-bytes "$T230_LAUNCH_REQUEST_BYTES" \
  --launch-request-intent-uri "$T230_LAUNCH_INTENT_URI" \
  --launch-request-intent-generation "$T230_LAUNCH_INTENT_GENERATION" \
  --launch-request-intent-sha256 "$T230_LAUNCH_INTENT_SHA256" \
  --launch-request-intent-bytes "$T230_LAUNCH_INTENT_BYTES" \
  --launch-request-completion-uri "$T230_LAUNCH_COMPLETION_URI" \
  --launch-request-completion-generation "$T230_LAUNCH_COMPLETION_GENERATION" \
  --launch-request-completion-sha256 "$T230_LAUNCH_COMPLETION_SHA256" \
  --launch-request-completion-bytes "$T230_LAUNCH_COMPLETION_BYTES" \
  --execution-authority-uri "$T230_AUTHORITY_URI" \
  --execution-authority-generation "$T230_AUTHORITY_GENERATION" \
  --execution-authority-sha256 "$T230_AUTHORITY_SHA256" \
  --execution-authority-bytes "$T230_AUTHORITY_BYTES" \
  --predecessor-identity /tmp/predecessor-0.json \
  --execute
