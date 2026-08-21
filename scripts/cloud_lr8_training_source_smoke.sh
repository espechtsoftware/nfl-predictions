#!/usr/bin/env bash
set -euo pipefail

# Update-only transport for the single LR8 2019-W1/R0 outcome-blind smoke.
# It never creates/deletes a Cloud Run job and never acquires the historical
# outcome lease.  A create-once intent is durable before the sole execution;
# any ambiguous or failed launch permanently forbids an automatic relaunch.
#
# Usage:
#   cloud_lr8_training_source_smoke.sh build-command CODE_SHA
#   cloud_lr8_training_source_smoke.sh prepare IMAGE CODE_SHA BUILD_ID
#   cloud_lr8_training_source_smoke.sh launch

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
ATTEMPT_ID=20260821-lr8-training-source-smoke-v2
PREDECESSOR_ATTEMPT_ID=20260820-lr8-training-source-smoke-v1
JOB=atlas-md-prefix-r4-smoke
JOB_UID=51545eb0-59e4-424e-91c9-98dd318285f4
BUCKET=nfl-predictions-503414-raw
OUT="$ROOT/reports/lr8-training-source-smoke-runs/$ATTEMPT_ID"
PENDING="$ROOT/reports/lr8-training-source-smoke-runs/.$ATTEMPT_ID.prepare.pending"
PREDECESSOR_OUT="$ROOT/reports/lr8-training-source-smoke-runs/$PREDECESSOR_ATTEMPT_ID"
RESULT_PREFIX="gs://$BUCKET/research/lr8-training-source/$ATTEMPT_ID/"
SMOKE_MANIFEST_URI="${RESULT_PREFIX}smoke-manifest.json"
GOVERNANCE_PREFIX="gs://$BUCKET/research-governance/lr8-training-source-smoke/$ATTEMPT_ID/"
FINISHER="$ROOT/scripts/finish_lr8_training_source_smoke.py"
PYTHON=${NFL_DFS_PYTHON:-"$ROOT/.venv/bin/python"}
COMMAND=${1:-}
EVIDENCE_ROOT=/tmp/lr8-training-source-smoke-evidence
RUN_SCRIPT=$(printf '%s\n' \
  "test ! -e $EVIDENCE_ROOT" \
  "mkdir -p $EVIDENCE_ROOT" \
  "exec python scripts/run_lr8_training_source.py smoke --execute --attempt-id $ATTEMPT_ID --project $PROJECT --bucket $BUCKET --catalog-table $PROJECT.nfl_predictions.slate_player_features --candidate-table $PROJECT.nfl_predictions.replay_candidates_staging --pit-table $PROJECT.nfl_features.player_week_training --tabpfn-table $PROJECT.nfl_features.tabpfn_projections_pit_v2 --location US --evidence-root $EVIDENCE_ROOT")

die() {
  echo "ERROR: $*" >&2
  exit 2
}

for repair_name in LR8_SMOKE_FINISHER_REPAIR_SHA256 \
  LR8_SMOKE_LAUNCHER_REPAIR_SHA256 LR8_SMOKE_WATCHER_REPAIR_SHA256; do
  repair_value=${!repair_name:-}
  [ -z "$repair_value" ] || [[ "$repair_value" =~ ^[0-9a-f]{64}$ ]] || \
    die "$repair_name differs"
done

capture_gcloud_json() {
  local target=$1
  shift
  local raw="$target.gcloud.raw.pending"
  [ ! -e "$target" ] && [ ! -e "$raw" ] || \
    die "immutable external JSON path exists: $target"
  if ! "$@" > "$raw"; then
    die "external JSON command failed; raw response retained: $raw"
  fi
  if ! PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      canonicalize-external-json --raw "$raw" --output "$target"; then
    die "external JSON canonicalization failed; raw retained: $raw"
  fi
  rm -- "$raw"
}

capture_inventory() {
  local prefix=$1
  local target=$2
  [ ! -e "$target" ] || die "immutable inventory path exists: $target"
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" inventory \
    --prefix "$prefix" --output "$target"
}

validate_identity_args() {
  local image=$1 code=$2 build=$3
  [[ "$image" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || \
    die "immutable image differs"
  [[ "$code" =~ ^[0-9a-f]{40}$ ]] || die "code SHA differs"
  [[ "$build" =~ ^[0-9A-Za-z-]{8,80}$ ]] || die "build ID differs"
}

case "$COMMAND" in
  build-command)
    CODE_SHA=${2:-}
    [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "code SHA differs"
    IMAGE_TAG="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:lr8-smoke-${CODE_SHA:0:7}"
    printf 'gcloud builds submit %q --git-source-revision=%q --config=%q --substitutions=%q --project=%q --format=%q\n' \
      'https://github.com/espechtsoftware/nfl-predictions.git' \
      "$CODE_SHA" cloudbuild.yaml "_IMAGE=$IMAGE_TAG" \
      "$PROJECT" json
    ;;

  prepare)
    IMAGE=${2:-}
    CODE_SHA=${3:-}
    BUILD_ID=${4:-}
    validate_identity_args "$IMAGE" "$CODE_SHA" "$BUILD_ID"
    [ -s "$PREDECESSOR_OUT/failure-closure.json" ] && \
      [ -s "$PREDECESSOR_OUT/failed-execution.json" ] || \
      die "LR8 smoke v1 terminal-failure closure is absent"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-predecessor-failure \
      --closure "$PREDECESSOR_OUT/failure-closure.json" \
      --metadata "$PREDECESSOR_OUT/failed-execution.json"
    [ ! -e "$OUT" ] && [ ! -e "$PENDING" ] || \
      die "immutable LR8 smoke preparation already exists"
    mkdir -p "$(dirname "$PENDING")"
    mkdir "$PENDING"

    capture_gcloud_json "$PENDING/build-metadata.json" \
      gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format=json
    capture_gcloud_json "$PENDING/job-before.json" \
      gcloud run jobs describe "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_gcloud_json "$PENDING/executions-before.json" \
      gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_gcloud_json "$PENDING/schedulers-before.json" \
      gcloud scheduler jobs list --project "$PROJECT" --location "$REGION" \
        --format=json
    capture_inventory "$RESULT_PREFIX" \
      "$PENDING/result-inventory-before.json"
    capture_inventory "$GOVERNANCE_PREFIX" \
      "$PENDING/governance-inventory-before.json"

    # This gate runs before the only mutation.  A missing job, wrong UID,
    # active execution, scheduler target, dirty prefix, or non-exact build
    # therefore cannot update anything.
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-preupdate --code-sha "$CODE_SHA" --image "$IMAGE" \
      --build-id "$BUILD_ID" --job "$JOB" --job-uid "$JOB_UID" \
      --build-metadata "$PENDING/build-metadata.json" \
      --job-before "$PENDING/job-before.json" \
      --executions-before "$PENDING/executions-before.json" \
      --schedulers-before "$PENDING/schedulers-before.json" \
      --result-inventory-before "$PENDING/result-inventory-before.json" \
      --governance-inventory-before \
        "$PENDING/governance-inventory-before.json"

    # `gcloud run jobs update` cannot create a missing job.  The complete job
    # contract is replaced and then independently re-read below.
    gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 8 --memory 32Gi \
      --max-retries 0 --task-timeout 6h --clear-volumes \
      --clear-volume-mounts --workdir="" --startup-probe="" --clear-secrets \
      --service-account "$SERVICE_ACCOUNT" \
      --set-env-vars "ANALYSIS_IMAGE=$IMAGE,CODE_SHA=$CODE_SHA,LR8_TRAINING_SOURCE_ENABLED=1" \
      --command bash --args=-ceu,"$RUN_SCRIPT" --quiet >/dev/null

    capture_gcloud_json "$PENDING/job-after.json" \
      gcloud run jobs describe "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_gcloud_json "$PENDING/executions-after.json" \
      gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_gcloud_json "$PENDING/schedulers-after.json" \
      gcloud scheduler jobs list --project "$PROJECT" --location "$REGION" \
        --format=json
    capture_inventory "$RESULT_PREFIX" \
      "$PENDING/result-inventory-after.json"
    capture_inventory "$GOVERNANCE_PREFIX" \
      "$PENDING/governance-inventory-after.json"

    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" prepare \
      --code-sha "$CODE_SHA" --image "$IMAGE" --build-id "$BUILD_ID" \
      --job "$JOB" --job-uid "$JOB_UID" \
      --build-metadata "$PENDING/build-metadata.json" \
      --job-before "$PENDING/job-before.json" \
      --job-after "$PENDING/job-after.json" \
      --executions-before "$PENDING/executions-before.json" \
      --executions-after "$PENDING/executions-after.json" \
      --schedulers-before "$PENDING/schedulers-before.json" \
      --schedulers-after "$PENDING/schedulers-after.json" \
      --result-inventory-before "$PENDING/result-inventory-before.json" \
      --result-inventory-after "$PENDING/result-inventory-after.json" \
      --governance-inventory-before \
        "$PENDING/governance-inventory-before.json" \
      --governance-inventory-after \
        "$PENDING/governance-inventory-after.json" \
      --prepared-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --output-dir "$PENDING"
    mv -- "$PENDING" "$OUT"
    echo "LR8_TRAINING_SOURCE_SMOKE_PREPARED job=$JOB uid=$JOB_UID"
    ;;

  launch)
    [ -s "$OUT/prepared.sha256" ] || die "LR8 smoke is not prepared"
    [ ! -e "$OUT/launch-intent.json" ] && \
      [ ! -e "$OUT/executions.txt" ] && [ ! -e "$OUT/launch.sha256" ] || \
      die "LR8 smoke launch already attempted; no relaunch is licensed"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-prepared --output-dir "$OUT"

    capture_gcloud_json "$OUT/job-launch.json" \
      gcloud run jobs describe "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_gcloud_json "$OUT/executions-launch.json" \
      gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_gcloud_json "$OUT/schedulers-launch.json" \
      gcloud scheduler jobs list --project "$PROJECT" --location "$REGION" \
        --format=json
    capture_inventory "$RESULT_PREFIX" "$OUT/result-inventory-launch.json"
    capture_inventory "$GOVERNANCE_PREFIX" \
      "$OUT/governance-inventory-launch.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      create-launch-intent --output-dir "$OUT" \
      --job-metadata "$OUT/job-launch.json" \
      --execution-census "$OUT/executions-launch.json" \
      --schedulers "$OUT/schedulers-launch.json" \
      --result-inventory "$OUT/result-inventory-launch.json" \
      --governance-inventory "$OUT/governance-inventory-launch.json" \
      --created-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    # From this point onward any error is ambiguous and permanently no-retry.
    # The create-once launch intent above is the durable guard.
    EXECUTION_RAW="$OUT/.execution-launch.raw.pending"
    [ ! -e "$EXECUTION_RAW" ] || die "ambiguous execution raw path exists"
    if ! gcloud run jobs execute "$JOB" --project "$PROJECT" \
        --region "$REGION" --async --format='value(metadata.name)' \
        > "$EXECUTION_RAW"; then
      die "LR8 smoke launch is ambiguous; intent retained and relaunch forbidden"
    fi
    EXECUTION=$(tr -d '\r\n' < "$EXECUTION_RAW")
    [[ "$EXECUTION" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
      die "LR8 smoke execution name is ambiguous; no relaunch"
    [ "$(wc -l < "$EXECUTION_RAW")" -le 1 ] || \
      die "LR8 smoke execute response is ambiguous; no relaunch"
    printf '%s %s %s\n' "$JOB" "$EXECUTION" "$SMOKE_MANIFEST_URI" \
      > "$OUT/executions.txt"
    rm -- "$EXECUTION_RAW"
    capture_gcloud_json "$OUT/execution-initial.json" \
      gcloud run jobs executions describe "$EXECUTION" --project "$PROJECT" \
        --region "$REGION" --format=json
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      bind-execution --output-dir "$OUT" --execution "$EXECUTION" \
      --execution-metadata "$OUT/execution-initial.json"
    echo "LR8_TRAINING_SOURCE_SMOKE_LAUNCHED execution=$EXECUTION no_retry=true"
    ;;

  *)
    die "usage: $0 build-command CODE_SHA | prepare IMAGE CODE_SHA BUILD_ID | launch"
    ;;
esac
