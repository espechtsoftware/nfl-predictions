#!/usr/bin/env bash
set -euo pipefail

# Update-only transport for the post-smoke LR8 70-cell score-free source.
# The same existing Cloud Run job is reused.  Preparation is one one-task,
# zero-retry execution; each cell is then a distinct one-task, zero-retry
# execution with an immutable local launch intent.  This script never creates
# or deletes a job and never touches the historical-outcome lease.

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
JOB=atlas-md-prefix-r4-smoke
JOB_UID=51545eb0-59e4-424e-91c9-98dd318285f4
ATTEMPT_ID=20260821-lr8-full-source-shards-v1
OUT="$ROOT/reports/lr8-full-source-shard-runs/$ATTEMPT_ID"
PENDING="$ROOT/reports/lr8-full-source-shard-runs/.$ATTEMPT_ID.prepare.pending"
RESULT_PREFIX="gs://nfl-predictions-503414-raw/research/lr8-training-source/$ATTEMPT_ID"
PREPARATION_URI="$RESULT_PREFIX/preparation-manifest.json"
SMOKE_OUT="$ROOT/reports/lr8-training-source-smoke-runs/20260820-lr8-training-source-smoke-v1"
RUNNER="$ROOT/scripts/run_lr8_full_source_shards.py"
FINISHER="$ROOT/scripts/finish_lr8_full_source_shards.py"
PYTHON=${NFL_DFS_PYTHON:-"$ROOT/.venv/bin/python"}
COMMAND=${1:-}

die() {
  echo "ERROR: $*" >&2
  exit 2
}

capture_json() {
  local target=$1
  shift
  local raw="$target.raw.pending"
  [ ! -e "$target" ] && [ ! -e "$raw" ] || die "immutable JSON exists: $target"
  "$@" > "$raw" || die "external JSON command failed: $target"
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    canonicalize-external-json --raw "$raw" --output "$target" || \
    die "external JSON is malformed: $target"
  rm -- "$raw"
}

capture_inventory() {
  local prefix=$1 target=$2
  [ ! -e "$target" ] || die "immutable inventory exists: $target"
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" inventory \
    --prefix "$prefix" --output "$target"
}

validate_identity() {
  local image=$1 code=$2 build=$3
  [[ "$image" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || \
    die "immutable image differs"
  [[ "$code" =~ ^[0-9a-f]{40}$ ]] || die "code SHA differs"
  [[ "$build" =~ ^[0-9A-Za-z-]{8,80}$ ]] || die "build ID differs"
}

case "$COMMAND" in
  prepare)
    IMAGE=${2:-}
    CODE_SHA=${3:-}
    BUILD_ID=${4:-}
    validate_identity "$IMAGE" "$CODE_SHA" "$BUILD_ID"
    [ -s "$SMOKE_OUT/finish.sha256" ] || die "real LR8 smoke is not finished"
    [ -s "$SMOKE_OUT/completion.json" ] || die "smoke completion is absent"
    [ -s "$SMOKE_OUT/smoke-solve-freeze.json" ] || die "smoke freeze is absent"
    [ ! -e "$OUT" ] && [ ! -e "$PENDING" ] || \
      die "immutable full-source preparation already exists"
    mkdir -p "$(dirname "$PENDING")"
    mkdir "$PENDING"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-smoke --completion "$SMOKE_OUT/completion.json" \
      --smoke-freeze "$SMOKE_OUT/smoke-solve-freeze.json"
    capture_json "$PENDING/build.json" \
      gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format=json
    # This intentionally keeps the scaffold unlaunchable until Docker and
    # Cloud Build integration add all four registered source/transport smokes.
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-build --build-metadata "$PENDING/build.json" \
      --build-id "$BUILD_ID" --code-sha "$CODE_SHA" --image "$IMAGE"
    capture_json "$PENDING/job-before.json" \
      gcloud run jobs describe "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_json "$PENDING/executions-before.json" \
      gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_json "$PENDING/schedulers-before.json" \
      gcloud scheduler jobs list --project "$PROJECT" \
        --location "$REGION" --format=json
    capture_inventory "$RESULT_PREFIX/" \
      "$PENDING/result-inventory-before.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-reuse --job "$JOB" --job-uid "$JOB_UID" \
      --job-metadata "$PENDING/job-before.json" \
      --executions "$PENDING/executions-before.json" \
      --schedulers "$PENDING/schedulers-before.json" \
      --result-inventory "$PENDING/result-inventory-before.json"

    PREP_ARGS="scripts/run_lr8_full_source_shards.py,prepare-cloud,--execute,--project,$PROJECT,--bucket,nfl-predictions-503414-raw,--catalog-table,$PROJECT.nfl_predictions.slate_player_features,--candidate-table,$PROJECT.nfl_predictions.replay_candidates_staging,--pit-table,$PROJECT.nfl_features.player_week_training,--tabpfn-table,$PROJECT.nfl_features.tabpfn_projections_pit_v2,--location,US"
    gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 8 --memory 32Gi \
      --max-retries 0 --task-timeout 6h --clear-volumes \
      --clear-volume-mounts --workdir="" --startup-probe="" --clear-secrets \
      --service-account "$SERVICE_ACCOUNT" \
      --set-env-vars "ANALYSIS_IMAGE=$IMAGE,CODE_SHA=$CODE_SHA,LR8_BUILD_ID=$BUILD_ID,LR8_FULL_SOURCE_SHARDS_ENABLED=1" \
      --command python --args="$PREP_ARGS" --quiet >/dev/null
    capture_json "$PENDING/job-after.json" \
      gcloud run jobs describe "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_inventory "$RESULT_PREFIX/" \
      "$PENDING/result-inventory-after.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      create-preparation-contract --output-dir "$PENDING" \
      --job-metadata "$PENDING/job-after.json" --code-sha "$CODE_SHA" \
      --build-id "$BUILD_ID" --image "$IMAGE"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-reuse --job "$JOB" --job-uid "$JOB_UID" \
      --job-metadata "$PENDING/job-after.json" \
      --executions "$PENDING/executions-before.json" \
      --schedulers "$PENDING/schedulers-before.json" \
      --result-inventory "$PENDING/result-inventory-after.json"
    mv -- "$PENDING" "$OUT"

    printf '%s\n' "prepare $CODE_SHA $BUILD_ID $IMAGE" > "$OUT/prepare-intent.txt"
    mapfile -t PREP_PROVENANCE_ARGS < <(
      PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
        contract-arguments --mode prepare --output-dir "$OUT"
    )
    [ "${#PREP_PROVENANCE_ARGS[@]}" -eq 16 ] || \
      die "preparation provenance arguments differ"
    PREP_PROVENANCE_CSV=$(IFS=,; echo "${PREP_PROVENANCE_ARGS[*]}")
    EXEC_RAW="$OUT/.prepare-execution.raw.pending"
    gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
      --args="$PREP_ARGS,$PREP_PROVENANCE_CSV" \
      --async --format='value(metadata.name)' > "$EXEC_RAW" || \
      die "preparation launch is ambiguous; no relaunch"
    EXECUTION=$(tr -d '\r\n' < "$EXEC_RAW")
    [[ "$EXECUTION" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
      die "preparation execution response is ambiguous; no relaunch"
    printf '%s %s %s\n' "$JOB" "$EXECUTION" "$PREPARATION_URI" \
      > "$OUT/preparation-execution.txt"
    rm -- "$EXEC_RAW"
    echo "LR8_FULL_SOURCE_PREPARATION_LAUNCHED execution=$EXECUTION no_retry=true"
    ;;

  launch-cells)
    [ -s "$OUT/preparation-completion.json" ] || \
      die "strict preparation harvest is absent"
    [ -s "$OUT/smoke-parity-object.json" ] || \
      die "exact smoke/prepared parity is absent"
    [ ! -e "$OUT/executions.txt" ] || \
      die "cell launch already attempted; no automatic relaunch"
    mapfile -t RECEIPTS < <(PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" \
      "$FINISHER" execution-arguments --output-dir "$OUT")
    [ "${#RECEIPTS[@]}" -eq 8 ] || die "pinned execution arguments differ"
    capture_json "$OUT/job-before-cells.json" \
      gcloud run jobs describe "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_json "$OUT/executions-before-cells.json" \
      gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_json "$OUT/schedulers-before-cells.json" \
      gcloud scheduler jobs list --project "$PROJECT" \
        --location "$REGION" --format=json
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-reuse --job "$JOB" --job-uid "$JOB_UID" \
      --job-metadata "$OUT/job-before-cells.json" \
      --executions "$OUT/executions-before-cells.json" \
      --schedulers "$OUT/schedulers-before-cells.json"
    mapfile -t PREPARED_IDENTITY < <(
      PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
        prepared-identity --output-dir "$OUT"
    )
    [ "${#PREPARED_IDENTITY[@]}" -eq 3 ] || \
      die "prepared immutable identity differs"
    CODE_SHA=${PREPARED_IDENTITY[0]}
    BUILD_ID=${PREPARED_IDENTITY[1]}
    IMAGE=${PREPARED_IDENTITY[2]}
    validate_identity "$IMAGE" "$CODE_SHA" "$BUILD_ID"
    COMMON_CELL_ARGS="--execute --project $PROJECT --evidence-root /tmp/lr8-full-source-cell-evidence --preparation-uri ${RECEIPTS[0]} --preparation-generation ${RECEIPTS[1]} --preparation-sha256 ${RECEIPTS[2]} --preparation-bytes ${RECEIPTS[3]} --parity-uri ${RECEIPTS[4]} --parity-generation ${RECEIPTS[5]} --parity-sha256 ${RECEIPTS[6]} --parity-bytes ${RECEIPTS[7]}"
    DEFAULT_RUN_SCRIPT="test ! -e /tmp/lr8-full-source-cell-evidence; mkdir /tmp/lr8-full-source-cell-evidence; exec python scripts/run_lr8_full_source_shards.py solve-cell-cloud --cell-index 0 $COMMON_CELL_ARGS"
    gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 8 --memory 32Gi \
      --max-retries 0 --task-timeout 6h --clear-volumes \
      --clear-volume-mounts --workdir="" --startup-probe="" --clear-secrets \
      --service-account "$SERVICE_ACCOUNT" \
      --set-env-vars "ANALYSIS_IMAGE=$IMAGE,CODE_SHA=$CODE_SHA,LR8_BUILD_ID=$BUILD_ID,LR8_FULL_SOURCE_SHARDS_ENABLED=1" \
      --command bash --args=-ceu,"$DEFAULT_RUN_SCRIPT" \
      --quiet >/dev/null
    capture_json "$OUT/job-after-cells.json" \
      gcloud run jobs describe "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      create-cell-contract --output-dir "$OUT" \
      --job-metadata "$OUT/job-after-cells.json"
    mapfile -t CELL_PROVENANCE_ARGS < <(
      PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
        contract-arguments --mode cell --output-dir "$OUT"
    )
    [ "${#CELL_PROVENANCE_ARGS[@]}" -eq 16 ] || \
      die "cell provenance arguments differ"
    CELL_PROVENANCE_STRING="${CELL_PROVENANCE_ARGS[*]}"
    : > "$OUT/executions.txt.pending"
    mkdir "$OUT/cell-launch-intents"
    for CELL_INDEX in $(seq 0 69); do
      STEM=$(printf 'cell-%02d' "$CELL_INDEX")
      printf '%s\n' "$CELL_INDEX" > "$OUT/cell-launch-intents/$STEM.txt"
      CELL_RUN_SCRIPT="test ! -e /tmp/lr8-full-source-cell-evidence; mkdir /tmp/lr8-full-source-cell-evidence; exec python scripts/run_lr8_full_source_shards.py solve-cell-cloud --cell-index $CELL_INDEX $COMMON_CELL_ARGS $CELL_PROVENANCE_STRING"
      RAW="$OUT/.${STEM}-execution.raw.pending"
      gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
        --args=-ceu,"$CELL_RUN_SCRIPT" \
        --async --format='value(metadata.name)' > "$RAW" || \
        die "cell $CELL_INDEX launch is ambiguous; no relaunch"
      EXECUTION=$(tr -d '\r\n' < "$RAW")
      [[ "$EXECUTION" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
        die "cell $CELL_INDEX execution response is ambiguous; no relaunch"
      URI=$(PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" -c \
        'import run_lr8_full_source_shards as r,sys; print(r.cell_shard_uri(int(sys.argv[1])))' \
        "$CELL_INDEX")
      printf '%s %s %s\n' "$JOB" "$EXECUTION" "$URI" \
        >> "$OUT/executions.txt.pending"
      rm -- "$RAW"
    done
    mv -- "$OUT/executions.txt.pending" "$OUT/executions.txt"
    echo "LR8_FULL_SOURCE_CELLS_LAUNCHED count=70 per_execution_tasks=1 no_retry=true"
    ;;

  *)
    die "usage: $0 prepare IMAGE CODE_SHA BUILD_ID | launch-cells"
    ;;
esac
