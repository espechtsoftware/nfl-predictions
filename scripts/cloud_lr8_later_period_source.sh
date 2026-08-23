#!/usr/bin/env bash
set -euo pipefail

# Update-only transport for the LR8 2023--2025 source and construction books.
# Preparation leaves one reused job default-off.  Every scientific action is
# a distinct one-task, zero-retry execution whose bash override is bound by a
# create-once intent and exact three-field ledger.  No command in this file
# acquires an outcome lease or reads a later-period score.

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
JOB=atlas-md-prefix-r4-smoke
JOB_UID=51545eb0-59e4-424e-91c9-98dd318285f4
ATTEMPT_ID=20260821-lr8-later-period-source-v1
OUT="$ROOT/reports/lr8-later-period-source-runs/$ATTEMPT_ID"
PENDING="$ROOT/reports/lr8-later-period-source-runs/.$ATTEMPT_ID.prepare.pending"
PREFIX="gs://nfl-predictions-503414-raw/research/lr8-later-period/$ATTEMPT_ID"
FINISHER="$ROOT/scripts/finish_lr8_later_period_source_transport.py"
PYTHON=${NFL_DFS_PYTHON:-"$ROOT/.venv/bin/python"}
DISABLED_SCRIPT='echo LR8_LATER_PERIOD_TRANSPORT_DISABLED >&2; exit 78'
MAX_IN_FLIGHT=${LR8_LATER_MAX_IN_FLIGHT:-6}
COMMAND=${1:-}
EXECUTE=${2:-}

die() {
  echo "ERROR: $*" >&2
  exit 2
}

require_execute() {
  [ "$EXECUTE" = "--execute" ] || die "literal --execute is required"
  [ "${LR8_LATER_PERIOD_TRANSPORT_ENABLED:-}" = "1" ] || \
    die "LR8_LATER_PERIOD_TRANSPORT_ENABLED=1 is required"
}

validate_identity() {
  local image=$1 code=$2 build=$3
  [[ "$image" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || \
    die "immutable image differs"
  [[ "$code" =~ ^[0-9a-f]{40}$ ]] || die "code SHA differs"
  [[ "$build" =~ ^[0-9A-Za-z-]{8,80}$ ]] || die "build ID differs"
}

validate_receipt_args() {
  local label=$1 uri=$2 generation=$3 digest=$4 bytes=$5
  [[ "$uri" =~ ^gs://[^/]+/.+ ]] || die "$label URI differs"
  [[ "$generation" =~ ^[1-9][0-9]*$ ]] || die "$label generation differs"
  [[ "$digest" =~ ^[0-9a-f]{64}$ ]] || die "$label SHA-256 differs"
  [[ "$bytes" =~ ^[1-9][0-9]*$ ]] || die "$label bytes differ"
}

capture_json() {
  local target=$1
  shift
  local raw="$target.raw.pending"
  [ ! -e "$target" ] && [ ! -e "$raw" ] || \
    die "immutable external JSON path exists: $target"
  if ! "$@" > "$raw"; then
    die "external JSON command failed; raw retained: $raw"
  fi
  if ! PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      canonicalize-external-json --raw "$raw" --output "$target"; then
    die "external JSON is malformed; raw retained: $raw"
  fi
  rm -- "$raw"
}

capture_inventory() {
  local target=$1
  [ ! -e "$target" ] || die "immutable inventory exists: $target"
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" inventory \
    --prefix "$PREFIX/" --output "$target"
}

cleanup_control_dir() {
  local directory=$1
  rm -- "$directory/job.json" "$directory/executions.json" \
    "$directory/schedulers.json"
  if [ -e "$directory/inventory.json" ]; then
    rm -- "$directory/inventory.json"
  fi
  rmdir -- "$directory"
}

validate_ready_stage() {
  local stage=$1
  local control
  control=$(mktemp -d "$OUT/.${stage}-control.XXXXXX")
  capture_json "$control/job.json" \
    gcloud run jobs describe "$JOB" --project "$PROJECT" \
      --region "$REGION" --format=json
  capture_json "$control/executions.json" \
    gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
      --region "$REGION" --format=json
  capture_json "$control/schedulers.json" \
    gcloud scheduler jobs list --project "$PROJECT" --location "$REGION" \
      --format=json
  capture_inventory "$control/inventory.json"
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    validate-ready --output-dir "$OUT" --stage "$stage" \
    --job-metadata "$control/job.json" \
    --executions "$control/executions.json" \
    --schedulers "$control/schedulers.json" \
    --inventory "$control/inventory.json"
  cleanup_control_dir "$control"
}

validate_cell_control_plane() {
  local control
  control=$(mktemp -d "$OUT/.cells-control.XXXXXX")
  capture_json "$control/job.json" \
    gcloud run jobs describe "$JOB" --project "$PROJECT" \
      --region "$REGION" --format=json
  capture_json "$control/executions.json" \
    gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
      --region "$REGION" --format=json
  capture_json "$control/schedulers.json" \
    gcloud scheduler jobs list --project "$PROJECT" --location "$REGION" \
      --format=json
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    validate-control-plane --output-dir "$OUT" \
    --job-metadata "$control/job.json" \
    --executions "$control/executions.json" \
    --schedulers "$control/schedulers.json" \
    --allowed-cell-ledgers "$OUT/cell-execution-ledgers"
  cleanup_control_dir "$control"
}

validate_job_current() {
  local index=$1
  local raw="$OUT/.cell-${index}-job.raw.pending"
  local body="$OUT/.cell-${index}-job.json"
  [ ! -e "$raw" ] && [ ! -e "$body" ] || \
    die "cell $index current-job poll is ambiguous"
  if ! gcloud run jobs describe "$JOB" --project "$PROJECT" \
      --region "$REGION" --format=json > "$raw"; then
    die "cell $index current-job describe failed; raw retained"
  fi
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    canonicalize-external-json --raw "$raw" --output "$body" || \
    die "cell $index current-job response is malformed"
  rm -- "$raw"
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    validate-configured-job --output-dir "$OUT" --job-metadata "$body"
  rm -- "$body"
}

stage_paths() {
  local stage=$1 index=${2:-}
  if [ "$stage" = "cell" ]; then
    INTENT_PATH=$(printf '%s/cell-launch-intents/cell-%02d.json' "$OUT" "$index")
    LEDGER_PATH=$(printf '%s/cell-execution-ledgers/cell-%02d.txt' "$OUT" "$index")
  else
    INTENT_PATH="$OUT/$stage-launch-intent.json"
    LEDGER_PATH="$OUT/$stage-execution.txt"
  fi
}

launch_one() {
  local stage=$1 index=${2:-}
  local -a index_args=()
  if [ "$stage" = "cell" ]; then
    index_args=(--cell-index "$index")
  fi
  stage_paths "$stage" "$index"
  if [ -s "$INTENT_PATH" ] && [ -s "$LEDGER_PATH" ]; then
    return 0
  fi
  [ ! -e "$INTENT_PATH" ] && [ ! -e "$LEDGER_PATH" ] || \
    die "$stage ${index:-} launch is ambiguous; no relaunch"
  local script uri raw execution
  script=$(PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    launch-script --output-dir "$OUT" --stage "$stage" "${index_args[@]}") || \
    die "$stage ${index:-} launch script validation failed"
  [ -n "$script" ] && [ "$(printf '%s\n' "$script" | wc -l)" -eq 1 ] || \
    die "$stage ${index:-} launch script differs"
  uri=$(PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    output-uri --stage "$stage" "${index_args[@]}") || \
    die "$stage ${index:-} output URI validation failed"
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    create-intent --output-dir "$OUT" --stage "$stage" \
    "${index_args[@]}" --output "$INTENT_PATH"

  raw="$LEDGER_PATH.execution.raw.pending"
  [ ! -e "$raw" ] || die "$stage ${index:-} raw launch response exists"
  if ! gcloud run jobs execute "$JOB" --project "$PROJECT" \
      --region "$REGION" --args=-ceu,"$script" --async \
      --format='value(metadata.name)' > "$raw"; then
    die "$stage ${index:-} launch is ambiguous; intent retained, no relaunch"
  fi
  [ "$(wc -l < "$raw")" -le 1 ] || \
    die "$stage ${index:-} execution response is ambiguous; no relaunch"
  execution=$(tr -d '\r\n' < "$raw")
  [[ "$execution" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
    die "$stage ${index:-} execution name is ambiguous; no relaunch"
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" ledger \
    --execution "$execution" --uri "$uri" --output "$LEDGER_PATH" || \
    die "$stage ${index:-} ledger binding failed; no relaunch"
  rm -- "$raw"
  LAST_EXECUTION=$execution
}

poll_cell() {
  local index=$1 execution=$2
  local raw="$OUT/.cell-${index}-capacity.raw.pending"
  local body="$OUT/.cell-${index}-capacity.json"
  [ ! -e "$raw" ] && [ ! -e "$body" ] || \
    die "cell $index capacity poll is ambiguous"
  if ! gcloud run jobs executions describe "$execution" --project "$PROJECT" \
      --region "$REGION" --format=json > "$raw"; then
    die "cell $index capacity poll failed; no launch/retry"
  fi
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    canonicalize-external-json --raw "$raw" --output "$body" || \
    die "cell $index capacity response is malformed"
  rm -- "$raw"
  CELL_STATE=$(PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    poll-state --metadata "$body") || die "cell $index capacity state differs"
  rm -- "$body"
}

load_existing_cells() {
  ACTIVE_EXECUTIONS=()
  ACTIVE_INDICES=()
  local index uri
  for index in $(seq 0 53); do
    stage_paths cell "$index"
    if [ ! -e "$INTENT_PATH" ] && [ ! -e "$LEDGER_PATH" ]; then
      continue
    fi
    [ -s "$INTENT_PATH" ] && [ -s "$LEDGER_PATH" ] || \
      die "cell $index launch is ambiguous; no relaunch"
    uri=$(PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      output-uri --stage cell --cell-index "$index")
    mapfile -t fields < <(
      PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
        ledger-fields --ledger "$LEDGER_PATH" --expected-uri "$uri"
    )
    [ "${#fields[@]}" -eq 3 ] && [ "${fields[0]}" = "$JOB" ] || \
      die "cell $index ledger differs"
    poll_cell "$index" "${fields[1]}"
    case "$CELL_STATE" in
      True) ;;
      Unknown)
        ACTIVE_EXECUTIONS+=("${fields[1]}")
        ACTIVE_INDICES+=("$index")
        ;;
      False) die "cell $index is terminal failure; no further launch/retry" ;;
      *) die "cell $index state differs" ;;
    esac
  done
}

wait_for_cell_slot() {
  while [ "${#ACTIVE_EXECUTIONS[@]}" -ge "$MAX_IN_FLIGHT" ]; do
    local -a still_executions=() still_indices=()
    local position index execution
    for position in "${!ACTIVE_EXECUTIONS[@]}"; do
      execution=${ACTIVE_EXECUTIONS[$position]}
      index=${ACTIVE_INDICES[$position]}
      poll_cell "$index" "$execution"
      case "$CELL_STATE" in
        True) ;;
        Unknown)
          still_executions+=("$execution")
          still_indices+=("$index")
          ;;
        False) die "cell $index is terminal failure; no further launch/retry" ;;
        *) die "cell $index state differs" ;;
      esac
    done
    ACTIVE_EXECUTIONS=("${still_executions[@]}")
    ACTIVE_INDICES=("${still_indices[@]}")
    if [ "${#ACTIVE_EXECUTIONS[@]}" -ge "$MAX_IN_FLIGHT" ]; then
      printf '%s LR8_LATER_CELLS active=%s cap=%s launched_waiting=true\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "${#ACTIVE_EXECUTIONS[@]}" "$MAX_IN_FLIGHT"
      sleep 30
    fi
  done
}

case "$COMMAND" in
  prepare)
    require_execute
    IMAGE=${3:-}
    CODE_SHA=${4:-}
    BUILD_ID=${5:-}
    BASE_URI=${6:-}
    BASE_GENERATION=${7:-}
    BASE_SHA256=${8:-}
    BASE_BYTES=${9:-}
    FIT_URI=${10:-}
    FIT_GENERATION=${11:-}
    FIT_SHA256=${12:-}
    FIT_BYTES=${13:-}
    FIT_FREEZE_SHA256=${14:-}
    ANATOMY_ARTIFACT_SHA256=${15:-}
    [ "$#" -eq 15 ] || die "prepare argument count differs"
    validate_identity "$IMAGE" "$CODE_SHA" "$BUILD_ID"
    validate_receipt_args base-source "$BASE_URI" "$BASE_GENERATION" \
      "$BASE_SHA256" "$BASE_BYTES"
    validate_receipt_args fit-freeze "$FIT_URI" "$FIT_GENERATION" \
      "$FIT_SHA256" "$FIT_BYTES"
    [[ "$FIT_FREEZE_SHA256" =~ ^[0-9a-f]{64}$ ]] || \
      die "fit freeze manifest SHA-256 differs"
    [[ "$ANATOMY_ARTIFACT_SHA256" =~ ^[0-9a-f]{64}$ ]] || \
      die "anatomy artifact SHA-256 differs"
    [ ! -e "$OUT" ] && [ ! -e "$PENDING" ] || \
      die "immutable later-period preparation already exists"
    mkdir -p "$(dirname "$PENDING")"
    mkdir "$PENDING"

    capture_json "$PENDING/build.json" \
      gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format=json
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-build --metadata "$PENDING/build.json" --build-id "$BUILD_ID" \
      --code-sha "$CODE_SHA" --image "$IMAGE"
    capture_json "$PENDING/job-before.json" \
      gcloud run jobs describe "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_json "$PENDING/executions-before.json" \
      gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_json "$PENDING/schedulers-before.json" \
      gcloud scheduler jobs list --project "$PROJECT" --location "$REGION" \
        --format=json
    capture_inventory "$PENDING/inventory-before.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-reuse --job-metadata "$PENDING/job-before.json" \
      --executions "$PENDING/executions-before.json" \
      --schedulers "$PENDING/schedulers-before.json" \
      --inventory "$PENDING/inventory-before.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-inputs \
      --base-source-uri "$BASE_URI" \
      --base-source-generation "$BASE_GENERATION" \
      --base-source-sha256 "$BASE_SHA256" --base-source-bytes "$BASE_BYTES" \
      --fit-freeze-uri "$FIT_URI" \
      --fit-freeze-generation "$FIT_GENERATION" \
      --fit-freeze-sha256 "$FIT_SHA256" --fit-freeze-bytes "$FIT_BYTES" \
      --fit-freeze-manifest-sha256 "$FIT_FREEZE_SHA256" \
      --anatomy-artifact-sha256 "$ANATOMY_ARTIFACT_SHA256" \
      --output "$PENDING/input-validation.json"

    gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 8 --memory 32Gi \
      --max-retries 0 --task-timeout 6h --clear-volumes \
      --clear-volume-mounts --workdir="" --startup-probe="" --clear-secrets \
      --service-account "$SERVICE_ACCOUNT" \
      --set-env-vars "ANALYSIS_IMAGE=$IMAGE,CODE_SHA=$CODE_SHA,LR8_BUILD_ID=$BUILD_ID,LR8_LATER_PERIOD_ENABLED=1,LR8_LATER_PERIOD_TRANSPORT_ATTEMPT=$ATTEMPT_ID" \
      --command bash --args=-ceu,"$DISABLED_SCRIPT" --quiet >/dev/null

    capture_json "$PENDING/job-after.json" \
      gcloud run jobs describe "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_json "$PENDING/executions-after.json" \
      gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_json "$PENDING/schedulers-after.json" \
      gcloud scheduler jobs list --project "$PROJECT" --location "$REGION" \
        --format=json
    capture_inventory "$PENDING/inventory-after.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      create-contract --job-metadata "$PENDING/job-after.json" \
      --input-validation "$PENDING/input-validation.json" \
      --code-sha "$CODE_SHA" --build-id "$BUILD_ID" --image "$IMAGE" \
      --output "$PENDING/contract.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-reuse --job-metadata "$PENDING/job-after.json" \
      --executions "$PENDING/executions-after.json" \
      --schedulers "$PENDING/schedulers-after.json" \
      --inventory "$PENDING/inventory-after.json"
    mv -- "$PENDING" "$OUT"
    echo "LR8_LATER_PERIOD_PREPARED job=$JOB uid=$JOB_UID default_off=true"
    ;;

  launch-source)
    require_execute
    [ -s "$OUT/contract.json" ] || die "transport contract is absent"
    stage_paths source
    if [ ! -e "$INTENT_PATH" ] && [ ! -e "$LEDGER_PATH" ]; then
      validate_ready_stage source
    fi
    launch_one source
    echo "LR8_LATER_SOURCE_LAUNCHED execution=${LAST_EXECUTION:-existing} no_retry=true"
    ;;

  launch-smoke)
    require_execute
    [ -s "$OUT/source-completion.json" ] || die "source terminal harvest is absent"
    stage_paths smoke
    if [ ! -e "$INTENT_PATH" ] && [ ! -e "$LEDGER_PATH" ]; then
      validate_ready_stage smoke
    fi
    launch_one smoke
    echo "LR8_LATER_SMOKE_LAUNCHED execution=${LAST_EXECUTION:-existing} no_retry=true"
    ;;

  launch-cells)
    require_execute
    [ -s "$OUT/smoke-completion.json" ] || \
      die "strict 2023-W1 smoke terminal authority is absent"
    case "$MAX_IN_FLIGHT" in
      ''|*[!0-9]*) die "LR8_LATER_MAX_IN_FLIGHT must be an integer" ;;
    esac
    [ "$MAX_IN_FLIGHT" -ge 1 ] && [ "$MAX_IN_FLIGHT" -le 8 ] || \
      die "LR8_LATER_MAX_IN_FLIGHT must be in [1,8]"
    exec 9>"$OUT/.cell-launch.lock"
    flock -n 9 || die "another bounded cell launcher owns this attempt"
    mkdir -p "$OUT/cell-launch-intents" "$OUT/cell-execution-ledgers"
    shopt -s nullglob
    existing_ledgers=("$OUT"/cell-execution-ledgers/cell-*.txt)
    shopt -u nullglob
    if [ "${#existing_ledgers[@]}" -eq 0 ]; then
      validate_ready_stage cells
    else
      validate_cell_control_plane
    fi
    load_existing_cells
    for index in $(seq 0 53); do
      stage_paths cell "$index"
      if [ -s "$INTENT_PATH" ] && [ -s "$LEDGER_PATH" ]; then
        continue
      fi
      [ ! -e "$INTENT_PATH" ] && [ ! -e "$LEDGER_PATH" ] || \
        die "cell $index launch is ambiguous; no relaunch"
      wait_for_cell_slot
      validate_job_current "$index"
      launch_one cell "$index"
      ACTIVE_EXECUTIONS+=("$LAST_EXECUTION")
      ACTIVE_INDICES+=("$index")
      printf '%s LR8_LATER_CELL_LAUNCHED index=%s execution=%s active=%s cap=%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$index" "$LAST_EXECUTION" \
        "${#ACTIVE_EXECUTIONS[@]}" "$MAX_IN_FLIGHT"
    done
    if [ ! -e "$OUT/executions.txt" ]; then
      PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
        assemble-cell-ledger --output-dir "$OUT" \
        --output "$OUT/executions.txt"
    fi
    echo "LR8_LATER_CELLS_LAUNCHED count=54 cap=$MAX_IN_FLIGHT no_retry=true"
    ;;

  launch-aggregate)
    require_execute
    [ -s "$OUT/cell-completion.json" ] && \
      [ -s "$OUT/terminal-cell-manifest.json" ] || \
      die "all-terminal generation-pinned cell harvest is absent"
    stage_paths aggregate
    if [ ! -e "$INTENT_PATH" ] && [ ! -e "$LEDGER_PATH" ]; then
      validate_ready_stage aggregate
    fi
    launch_one aggregate
    echo "LR8_LATER_AGGREGATE_LAUNCHED execution=${LAST_EXECUTION:-existing} no_retry=true"
    ;;

  *)
    die "usage: $0 prepare|launch-source|launch-smoke|launch-cells|launch-aggregate --execute ..."
    ;;
esac
