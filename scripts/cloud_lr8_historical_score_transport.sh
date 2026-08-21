#!/usr/bin/env bash
set -euo pipefail

# Shared update-only Cloud Run transport for the two LR8 historical reads.
# Prepare never acquires the historical-outcome lease.  Launch revalidates the
# exact configured job and empty result prefix, acquires the lease, writes the
# immutable launch intent, and then submits exactly one zero-retry execution.

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
JOB=atlas-md-prefix-r4-smoke
JOB_UID=51545eb0-59e4-424e-91c9-98dd318285f4
FINISHER="$ROOT/scripts/finish_lr8_historical_score_transport.py"
LEASE_TOOL="$ROOT/scripts/historical_outcome_lease.py"
PYTHON=${NFL_DFS_PYTHON:-"$ROOT/.venv/bin/python"}
COMMAND=${1:-}
MODE=${2:-}

die() {
  echo "ERROR: $*" >&2
  exit 2
}

mapfile -t MODE_VALUES < <(
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    mode-values --mode "$MODE"
) || die "historical-score mode differs"
[ "${#MODE_VALUES[@]}" -eq 4 ] || die "historical-score mode values differ"
RUN_ID=${MODE_VALUES[0]}
PREFIX=${MODE_VALUES[1]}
OUT=${MODE_VALUES[2]}
GOVERNANCE_PREFIX=${MODE_VALUES[3]}
PENDING="$(dirname "$OUT")/.$RUN_ID.prepare.pending"
LEASE="$OUT/historical-outcome-lease.json"

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
  local target=$1
  local prefix=${2:-"$PREFIX/"}
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
    IMAGE=${3:-}
    CODE_SHA=${4:-}
    BUILD_ID=${5:-}
    INPUT_URI=${6:-}
    INPUT_GENERATION=${7:-}
    INPUT_SHA256=${8:-}
    INPUT_MANIFEST_SHA256=${9:-}
    validate_identity "$IMAGE" "$CODE_SHA" "$BUILD_ID"
    [ ! -e "$OUT" ] && [ ! -e "$PENDING" ] || \
      die "immutable historical-score preparation exists"
    mkdir -p "$(dirname "$PENDING")"
    mkdir "$PENDING"

    capture_json "$PENDING/build.json" \
      gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
        --region "$REGION" --format=json
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
      gcloud scheduler jobs list --project "$PROJECT" \
        --location "$REGION" --format=json
    capture_inventory "$PENDING/result-inventory-before.json"
    capture_inventory "$PENDING/governance-inventory-before.json" \
      "$GOVERNANCE_PREFIX/"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-reuse --job-metadata "$PENDING/job-before.json" \
      --executions "$PENDING/executions-before.json" \
      --schedulers "$PENDING/schedulers-before.json" \
      --inventory "$PENDING/result-inventory-before.json" \
      --governance-inventory "$PENDING/governance-inventory-before.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-input --mode "$MODE" --input-uri "$INPUT_URI" \
      --input-generation "$INPUT_GENERATION" --input-sha256 "$INPUT_SHA256" \
      --input-manifest-sha256 "$INPUT_MANIFEST_SHA256" \
      --output "$PENDING/input-validation.json"

    DEFAULT_SCRIPT="echo LR8_HISTORICAL_SCORE_TRANSPORT_DISABLED_${MODE^^} >&2; exit 78"
    gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 8 --memory 32Gi \
      --max-retries 0 --task-timeout 6h --clear-volumes \
      --clear-volume-mounts --workdir="" --startup-probe="" --clear-secrets \
      --service-account "$SERVICE_ACCOUNT" \
      --set-env-vars "ANALYSIS_IMAGE=$IMAGE,CODE_SHA=$CODE_SHA,LR8_BUILD_ID=$BUILD_ID,LR8_HISTORICAL_SCORE_TRANSPORT_MODE=$MODE" \
      --command bash --args=-ceu,"$DEFAULT_SCRIPT" --quiet >/dev/null
    capture_json "$PENDING/job-after.json" \
      gcloud run jobs describe "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_inventory "$PENDING/result-inventory-after.json"
    capture_inventory "$PENDING/governance-inventory-after.json" \
      "$GOVERNANCE_PREFIX/"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      create-contract --mode "$MODE" --input-uri "$INPUT_URI" \
      --input-generation "$INPUT_GENERATION" --input-sha256 "$INPUT_SHA256" \
      --input-manifest-sha256 "$INPUT_MANIFEST_SHA256" \
      --input-validation "$PENDING/input-validation.json" \
      --job-metadata "$PENDING/job-after.json" --code-sha "$CODE_SHA" \
      --build-id "$BUILD_ID" --image "$IMAGE" \
      --output "$PENDING/contract.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-ready --contract "$PENDING/contract.json" \
      --job-metadata "$PENDING/job-after.json" \
      --executions "$PENDING/executions-before.json" \
      --schedulers "$PENDING/schedulers-before.json" \
      --inventory "$PENDING/result-inventory-after.json" \
      --governance-inventory "$PENDING/governance-inventory-after.json"
    mv -- "$PENDING" "$OUT"
    echo "LR8_HISTORICAL_SCORE_PREPARED mode=$MODE run_id=$RUN_ID lease_acquired=false"
    ;;

  launch)
    [ -s "$OUT/contract.json" ] || die "prepared transport contract is absent"
    for forbidden in "$OUT/launch-claim.json" "$OUT/launch-intent.json" \
      "$OUT/execution.txt" \
      "$OUT/execution-terminal.json" "$OUT/completion.txt"; do
      [ ! -e "$forbidden" ] || die "immutable launch/terminal receipt exists"
    done
    READY=$(mktemp -d)
    trap 'rm -rf -- "$READY"' EXIT
    capture_json "$READY/job.json" \
      gcloud run jobs describe "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_json "$READY/executions.json" \
      gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_json "$READY/schedulers.json" \
      gcloud scheduler jobs list --project "$PROJECT" \
        --location "$REGION" --format=json
    capture_inventory "$READY/inventory.json"
    capture_inventory "$READY/governance-inventory.json" \
      "$GOVERNANCE_PREFIX/"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-ready --contract "$OUT/contract.json" \
      --job-metadata "$READY/job.json" --executions "$READY/executions.json" \
      --schedulers "$READY/schedulers.json" --inventory "$READY/inventory.json" \
      --governance-inventory "$READY/governance-inventory.json"

    # Acquisition precedes the durable no-relaunch claim.  Only metadata/prefix
    # reads follow it, ending with the exact job-generation check immediately
    # before the sole execute call.  A failed acquisition leaves OUT retry-clean.
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$LEASE_TOOL" acquire \
      --run-id "$RUN_ID" --job "$JOB" --code-sha "$(PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["code_sha"])' "$OUT/contract.json")" \
      --image "$(PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["image"])' "$OUT/contract.json")" \
      --receipt "$LEASE" || die "historical-outcome lease is unavailable"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      create-launch-claim --contract "$OUT/contract.json" --lease "$LEASE" \
      --output "$OUT/launch-claim.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      create-launch-intent --contract "$OUT/contract.json" --lease "$LEASE" \
      --claim "$OUT/launch-claim.json" \
      --output "$OUT/launch-intent.json"
    RUN_SCRIPT=$(PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      launch-script --contract "$OUT/contract.json" \
      --intent "$OUT/launch-intent.json" --claim "$OUT/launch-claim.json")

    # The durable claim is now live.  Re-census prior executions and both
    # prefixes, then describe the mutable reused job LAST so the exact
    # generation/spec check is immediately adjacent to the sole execute call.
    capture_json "$OUT/executions-after-lease.json" \
      gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    capture_json "$OUT/schedulers-after-lease.json" \
      gcloud scheduler jobs list --project "$PROJECT" \
        --location "$REGION" --format=json
    capture_inventory "$OUT/result-inventory-after-lease.json"
    capture_inventory "$OUT/governance-inventory-after-lease.json" \
      "$GOVERNANCE_PREFIX/"
    capture_json "$OUT/job-after-lease.json" \
      gcloud run jobs describe "$JOB" --project "$PROJECT" \
        --region "$REGION" --format=json
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-preexecute --contract "$OUT/contract.json" \
      --intent "$OUT/launch-intent.json" --claim "$OUT/launch-claim.json" \
      --job-metadata "$OUT/job-after-lease.json" \
      --executions "$OUT/executions-after-lease.json" \
      --schedulers "$OUT/schedulers-after-lease.json" \
      --inventory "$OUT/result-inventory-after-lease.json" \
      --governance-inventory "$OUT/governance-inventory-after-lease.json"
    RAW="$OUT/.execution.raw.pending"
    if ! gcloud run jobs execute "$JOB" --project "$PROJECT" \
        --region "$REGION" --args=-ceu,"$RUN_SCRIPT" --async \
        --format='value(metadata.name)' > "$RAW"; then
      die "historical-score launch is ambiguous; live lease and raw response retained; no relaunch"
    fi
    EXECUTION=$(tr -d '\r\n' < "$RAW")
    if [[ ! "$EXECUTION" =~ ^${JOB}-[a-z0-9]{5}$ ]]; then
      die "execution response is ambiguous; live lease and raw response retained; no relaunch"
    fi
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" ledger \
      --mode "$MODE" --execution "$EXECUTION" --output "$OUT/execution.txt"
    rm -- "$RAW"
    cp "$READY/job.json" "$OUT/job-at-launch.json"
    cp "$READY/executions.json" "$OUT/executions-at-launch.json"
    cp "$READY/schedulers.json" "$OUT/schedulers-at-launch.json"
    cp "$READY/inventory.json" "$OUT/result-inventory-at-launch.json"
    trap - EXIT
    rm -rf -- "$READY"
    echo "LR8_HISTORICAL_SCORE_LAUNCHED mode=$MODE execution=$EXECUTION sole_execution=true"
    ;;

  *)
    die "usage: $0 prepare MODE IMAGE CODE_SHA BUILD_ID INPUT_URI INPUT_GENERATION INPUT_SHA256 INPUT_MANIFEST_SHA256 | launch MODE"
    ;;
esac
