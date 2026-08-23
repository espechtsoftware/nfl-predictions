#!/usr/bin/env bash
set -euo pipefail

# Reuse-only, no-retry transport for the conditional A7 score-free transfer.
#
# Usage:
#   cloud_a7_production_law_transfer.sh build-command CODE_SHA
#   cloud_a7_production_law_transfer.sh prepare IMAGE CODE_SHA BUILD_ID
#   cloud_a7_production_law_transfer.sh launch {smoke|support|full}
#   cloud_a7_production_law_transfer.sh freeze

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260821-a7-production-law-scorefree-selector-transfer-v1
JOB=atlas-minimal-c-s2023-w1-v1
OUT="$ROOT/reports/a7-production-law-selector-transfer-runs/$RUN_ID"
FINISHER="$ROOT/scripts/finish_a7_production_law_transfer.py"
RUNNER="$ROOT/scripts/run_a7_production_law_transfer.py"
PYTHON="$ROOT/.venv/bin/python"
COMMAND=${1:-}

die() {
  echo "ERROR: $*" >&2
  exit 2
}

# This must be the first operation before every gcloud command or any helper
# that constructs a storage client.
gate_predecessor() {
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$RUNNER" \
    validate-predecessor >/dev/null || \
    die "exact final A7 positive predecessor is absent"
}

canonicalize_pending() {
  local raw=$1
  local target=$2
  [ -e "$raw" ] || return 1
  [ ! -e "$target" ] || return 0
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    canonicalize-external-json --raw "$raw" --output "$target"
}

capture_json_once() {
  local target=$1
  shift
  local raw="$target.gcloud.raw.pending"
  if [ -e "$target" ]; then
    [ ! -e "$raw" ] || die "canonical and raw external JSON both exist: $target"
    return 0
  fi
  if [ -e "$raw" ]; then
    canonicalize_pending "$raw" "$target" || \
      die "retained external JSON is malformed: $raw"
    rm -- "$raw"
    return 0
  fi
  if ! "$@" > "$raw"; then
    die "external JSON command failed; raw response retained: $raw"
  fi
  canonicalize_pending "$raw" "$target" || \
    die "external JSON canonicalization failed: $raw"
  rm -- "$raw"
}

capture_job_state() {
  local stem=$1
  capture_json_once "$stem-job.json" gcloud run jobs describe "$JOB" \
    --project "$PROJECT" --region "$REGION" --format=json
  capture_json_once "$stem-executions.json" gcloud run jobs executions list \
    --job "$JOB" --project "$PROJECT" --region "$REGION" --format=json
  capture_json_once "$stem-schedulers.json" gcloud scheduler jobs list \
    --project "$PROJECT" --location "$REGION" --format=json
}

case "$COMMAND" in
  build-command)
    CODE_SHA=${2:-}
    [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "full source commit required"
    TAG="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:a7-transfer-${CODE_SHA:0:7}"
    printf 'gcloud builds submit %q --git-source-revision=%q --config=%q --substitutions=%q --project=%q --format=%q\n' \
      'https://github.com/espechtsoftware/nfl-predictions.git' \
      "$CODE_SHA" "$ROOT/cloudbuild.yaml" "_IMAGE=$TAG" "$PROJECT" \
      'value(id)'
    ;;

  prepare)
    IMAGE=${2:-}
    CODE_SHA=${3:-}
    BUILD_ID=${4:-}
    [[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || \
      die "immutable transfer image required"
    [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "full source commit required"
    [[ "$BUILD_ID" =~ ^[0-9A-Za-z-]{8,80}$ ]] || die "build ID differs"
    gate_predecessor
    mkdir -p "$OUT"
    capture_json_once "$OUT/build-metadata.json" gcloud builds describe \
      "$BUILD_ID" --project "$PROJECT" --format=json
    capture_job_state "$OUT/claim-before"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" claim-job \
      --code-sha "$CODE_SHA" --image "$IMAGE" --build-id "$BUILD_ID" \
      --build-metadata "$OUT/build-metadata.json" \
      --job-before "$OUT/claim-before-job.json" \
      --executions-before "$OUT/claim-before-executions.json" \
      --schedulers-before "$OUT/claim-before-schedulers.json" \
      --receipt "$OUT/job-claim-receipt.json" >/dev/null

    # Crash recovery first: a prior update may already have reached the exact
    # inert state even if its local after-capture was interrupted.
    capture_job_state "$OUT/deployment-recovery"
    if PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
        prepare-deployment --claim "$OUT/job-claim-receipt.json" \
        --job-after "$OUT/deployment-recovery-job.json" \
        --executions-after "$OUT/deployment-recovery-executions.json" \
        --schedulers-after "$OUT/deployment-recovery-schedulers.json" \
        --receipt "$OUT/deployment-receipt.json" >/dev/null 2>&1; then
      echo "A7_TRANSFER_DEPLOYMENT_RECOVERED"
      exit 0
    fi

    [ ! -e "$OUT/deployment-receipt.json" ] || \
      die "deployment receipt exists but did not validate"
    gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
      --max-retries 0 --task-timeout 2h --clear-volumes \
      --clear-volume-mounts --workdir="" --startup-probe="" --clear-secrets \
      --service-account "$SERVICE_ACCOUNT" \
      --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
      --command python \
      --args "scripts/run_a7_production_law_transfer.py,--help" \
      --quiet >/dev/null
    capture_job_state "$OUT/deployment-after"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      prepare-deployment --claim "$OUT/job-claim-receipt.json" \
      --job-after "$OUT/deployment-after-job.json" \
      --executions-after "$OUT/deployment-after-executions.json" \
      --schedulers-after "$OUT/deployment-after-schedulers.json" \
      --receipt "$OUT/deployment-receipt.json" >/dev/null
    echo "A7_TRANSFER_PREPARED inert=true retry=false"
    ;;

  launch)
    PHASE=${2:-}
    [[ "$PHASE" =~ ^(smoke|support|full)$ ]] || die "phase differs"
    gate_predecessor
    [ -s "$OUT/deployment-receipt.json" ] || die "deployment is absent"
    mkdir -p "$OUT/$PHASE"
    RESPONSE="$OUT/$PHASE/execute-response.json"
    RAW="$OUT/$PHASE/execute-response.gcloud.raw.pending"
    EXECUTION_RECEIPT="$OUT/$PHASE/execution-claim-receipt.json"
    LAUNCH_RECEIPT="$OUT/$PHASE/launch-claim-receipt.json"

    if [ -s "$EXECUTION_RECEIPT" ]; then
      echo "A7_TRANSFER_EXECUTION_ALREADY_REGISTERED phase=$PHASE no_relaunch=true"
      exit 0
    fi
    if [ -e "$RAW" ] && [ ! -e "$RESPONSE" ]; then
      canonicalize_pending "$RAW" "$RESPONSE" || \
        die "ambiguous execute response retained; no relaunch"
      rm -- "$RAW"
    fi

    if [ ! -s "$LAUNCH_RECEIPT" ]; then
      if [ -s "$OUT/$PHASE/intent-receipt.json" ] && \
          [ -s "$OUT/$PHASE/launch-current-job.json" ] && \
          [ -s "$OUT/$PHASE/launch-current-executions.json" ] && \
          [ -s "$OUT/$PHASE/launch-current-schedulers.json" ]; then
        # Recover a create-only launch claim whose local receipt write was
        # interrupted. These captures were made before any execute call.
        PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
          create-launch-claim --phase "$PHASE" --output-dir "$OUT" \
          --job-current "$OUT/$PHASE/launch-current-job.json" \
          --executions-current "$OUT/$PHASE/launch-current-executions.json" \
          --schedulers-current "$OUT/$PHASE/launch-current-schedulers.json" \
          >/dev/null
      else
        capture_job_state "$OUT/$PHASE/intent-current"
        PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
          create-phase-intent --phase "$PHASE" --output-dir "$OUT" \
          --deployment "$OUT/deployment-receipt.json" \
          --job-current "$OUT/$PHASE/intent-current-job.json" \
          --executions-current "$OUT/$PHASE/intent-current-executions.json" \
          --schedulers-current "$OUT/$PHASE/intent-current-schedulers.json" \
          >/dev/null
        capture_job_state "$OUT/$PHASE/launch-current"
        PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
          create-launch-claim --phase "$PHASE" --output-dir "$OUT" \
          --job-current "$OUT/$PHASE/launch-current-job.json" \
          --executions-current "$OUT/$PHASE/launch-current-executions.json" \
          --schedulers-current "$OUT/$PHASE/launch-current-schedulers.json" \
          >/dev/null
      fi
    fi

    if [ -s "$RESPONSE" ]; then
      PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
        register-execution --phase "$PHASE" --output-dir "$OUT" \
        --execute-response "$RESPONSE" >/dev/null
      echo "A7_TRANSFER_EXECUTION_RECOVERED phase=$PHASE no_relaunch=true"
      exit 0
    fi

    ARGS=$($PYTHON - "$OUT/$PHASE/intent-receipt.json" <<'PY'
import json
import sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
args = value["intent"]["contract"]["args"]
if not isinstance(args, list) or any("," in item for item in args):
    raise SystemExit("invalid phase args")
print(",".join(args))
PY
    ) || die "phase args differ"
    [ ! -e "$RAW" ] && [ ! -e "$RESPONSE" ] || \
      die "execute response path already exists; no relaunch"
    if ! gcloud run jobs execute "$JOB" --project "$PROJECT" \
        --region "$REGION" --async --args "$ARGS" --format=json > "$RAW"; then
      die "execute call ambiguous; raw retained and no relaunch"
    fi
    canonicalize_pending "$RAW" "$RESPONSE" || \
      die "execute response malformed; raw retained and no relaunch"
    rm -- "$RAW"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      register-execution --phase "$PHASE" --output-dir "$OUT" \
      --execute-response "$RESPONSE" >/dev/null
    echo "A7_TRANSFER_LAUNCHED phase=$PHASE no_retry=true"
    ;;

  freeze)
    gate_predecessor
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" freeze \
      --output-dir "$OUT" >/dev/null
    echo "A7_TRANSFER_FROZEN shadow=false production=false"
    ;;

  *)
    die "usage: $0 {build-command|prepare|launch|freeze} ..."
    ;;
esac
