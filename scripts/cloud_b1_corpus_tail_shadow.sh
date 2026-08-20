#!/usr/bin/env bash
set -euo pipefail

# Reuse-only orchestration for the historically licensed B1 2026 shadow.
# Nothing in this script changes production.  The deployed job is inert and
# CORPUS_TAIL_SHADOW_ENABLED=0 until an explicit one-week execution override.
#
# Usage:
#   cloud_b1_corpus_tail_shadow.sh build-command CODE_SHA
#   cloud_b1_corpus_tail_shadow.sh prepare IMAGE CODE_SHA BUILD_ID JOB JOB_UID EVIDENCE_COMMIT
#   cloud_b1_corpus_tail_shadow.sh prepare-week PANEL_SOURCE_RECEIPT_OBJECT
#   cloud_b1_corpus_tail_shadow.sh launch-week WEEK
#   cloud_b1_corpus_tail_shadow.sh harvest-week WEEK freeze|settlement
#   cloud_b1_corpus_tail_shadow.sh launch-settlement WEEK
#   cloud_b1_corpus_tail_shadow.sh launch-adoption
#   cloud_b1_corpus_tail_shadow.sh harvest-adoption

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PYTHON=${PYTHON:-$ROOT/.venv/bin/python}
TRANSPORT="$ROOT/scripts/run_b1_corpus_tail_shadow_transport.py"
OUT="$ROOT/reports/b1-corpus-tail-shadow-runs/2026-b1-corpus-tail-shadow-v1"
DEPLOYMENT="$OUT/deployment-manifest.json"
DEPLOYMENT_RECEIPT="$OUT/deployment-receipt.json"
COMMAND=${1:-}

die() {
  echo "ERROR: $*" >&2
  exit 2
}

run_transport() {
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$TRANSPORT" "$@"
}

capture_json() {
  local target=$1
  shift
  local raw="$target.gcloud.raw.pending"
  [ ! -e "$target" ] && [ ! -e "$target.sha256" ] && [ ! -e "$raw" ] || \
    die "immutable external JSON target exists: $target"
  if ! "$@" > "$raw"; then
    die "external JSON command failed; raw response retained: $raw"
  fi
  run_transport canonicalize-external-json --raw "$raw" --output "$target"
  rm -- "$raw"
}

verify_pushed() {
  local path=$1
  local relative=${path#"$ROOT/"}
  [ "$relative" != "$path" ] || die "path is outside repository: $path"
  git -C "$ROOT" show "origin/main:$relative" | cmp -s - "$path" || \
    die "file is not byte-identical in origin/main: $relative"
}

verify_harvest_pushed() {
  local directory=$1
  for name in execution.json result-metadata.json result.json harvest.sha256; do
    verify_pushed "$directory/$name"
  done
}

week_dir() {
  printf '%s/weeks/week-%02d' "$OUT" "$1"
}

capture_job_state() {
  local job=$1
  local suffix=$2
  capture_json "$OUT/job-$suffix.json" gcloud run jobs describe "$job" \
    --project "$PROJECT" --region "$REGION" --format=json
  capture_json "$OUT/executions-$suffix.json" gcloud run jobs executions list \
    --job "$job" --project "$PROJECT" --region "$REGION" --format=json
  capture_json "$OUT/schedulers-$suffix.json" gcloud scheduler jobs list \
    --project "$PROJECT" --location "$REGION" --format=json
}

deployment_job() {
  "$PYTHON" - "$DEPLOYMENT" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["job"]["name"])
PY
}

intent_generation() {
  "$PYTHON" - "$1" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
print(value["object"]["generation"])
PY
}

case "$COMMAND" in
  build-command)
    CODE_SHA=${2:-}
    [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "full source commit required"
    TAG="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:b1-shadow-${CODE_SHA:0:7}"
    printf 'gcloud builds submit %q --git-source-revision=%q --config=%q --substitutions=%q --project=%q --format=%q\n' \
      'https://github.com/espechtsoftware/nfl-predictions.git' "$CODE_SHA" \
      "$ROOT/cloudbuild.yaml" "_IMAGE=$TAG" "$PROJECT" 'value(id)'
    ;;

  prepare)
    IMAGE=${2:-}
    CODE_SHA=${3:-}
    BUILD_ID=${4:-}
    JOB=${5:-}
    JOB_UID=${6:-}
    EVIDENCE_COMMIT=${7:-}
    [[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || \
      die "immutable shadow image required"
    [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "full source commit required"
    [[ "$EVIDENCE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "full evidence commit required"
    [[ "$BUILD_ID" =~ ^[0-9A-Za-z-]{8,80}$ ]] || die "build ID differs"
    [ -n "$JOB" ] && [ -n "$JOB_UID" ] || die "existing job name and UID required"
    git -C "$ROOT" merge-base --is-ancestor "$CODE_SHA" origin/main || \
      die "shadow source is not pushed to origin/main"
    mkdir -p "$OUT"
    [ ! -e "$OUT/historical-license.json" ] || die "historical license already prepared"
    run_transport validate-historical-license \
      --historical-out "$ROOT/reports/b1-corpus-tail-runs/20260820-b1-corpus-tail-model-v1" \
      --evidence-commit "$EVIDENCE_COMMIT" --remote-ref origin/main \
      --output "$OUT/historical-license.json"
    capture_json "$OUT/build-metadata.json" gcloud builds describe "$BUILD_ID" \
      --project "$PROJECT" --format=json
    capture_job_state "$JOB" before
    run_transport validate-reuse-candidate --job-name "$JOB" --job-uid "$JOB_UID" \
      --job "$OUT/job-before.json" --executions "$OUT/executions-before.json" \
      --schedulers "$OUT/schedulers-before.json"

    # Update only the exact idle/unscheduled existing job.  Its saved command
    # is help and its saved enable flag is zero; each real week is explicit.
    gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
      --max-retries 0 --task-timeout 4h --clear-volumes --clear-volume-mounts \
      --workdir="" --startup-probe="" --clear-secrets \
      --service-account "$SERVICE_ACCOUNT" \
      --set-env-vars "ANALYSIS_IMAGE=$IMAGE,CODE_SHA=$CODE_SHA,CORPUS_TAIL_SHADOW_ENABLED=0" \
      --command python \
      --args "scripts/run_b1_corpus_tail_shadow_transport.py,--help" \
      --quiet >/dev/null
    capture_job_state "$JOB" after
    run_transport prepare-deployment \
      --historical-license "$OUT/historical-license.json" \
      --code-sha "$CODE_SHA" --image "$IMAGE" --build-id "$BUILD_ID" \
      --build-metadata "$OUT/build-metadata.json" \
      --job-name "$JOB" --job-uid "$JOB_UID" \
      --job-before "$OUT/job-before.json" --job-after "$OUT/job-after.json" \
      --executions-before "$OUT/executions-before.json" \
      --executions-after "$OUT/executions-after.json" \
      --schedulers-before "$OUT/schedulers-before.json" \
      --schedulers-after "$OUT/schedulers-after.json" \
      --output "$DEPLOYMENT"
    run_transport publish-deployment --deployment "$DEPLOYMENT" \
      --receipt "$DEPLOYMENT_RECEIPT"
    (
      cd "$OUT"
      sha256sum historical-license.json historical-license.json.sha256 \
        build-metadata.json build-metadata.json.sha256 \
        job-before.json job-before.json.sha256 job-after.json job-after.json.sha256 \
        executions-before.json executions-before.json.sha256 \
        executions-after.json executions-after.json.sha256 \
        schedulers-before.json schedulers-before.json.sha256 \
        schedulers-after.json schedulers-after.json.sha256 \
        deployment-manifest.json deployment-manifest.json.sha256 \
        deployment-receipt.json deployment-receipt.json.sha256 \
        > deployment.sha256
    )
    echo "B1_CORPUS_TAIL_SHADOW_DEPLOYED_DEFAULT_OFF commit_and_push_before_week=true"
    ;;

  prepare-week)
    PANEL_SOURCE_RECEIPT_OBJECT=${2:-}
    [ "$#" = 2 ] || die "prepare-week requires one panel-source receipt object"
    [ -n "$PANEL_SOURCE_RECEIPT_OBJECT" ] || \
      die "panel-source receipt object is required"
    verify_pushed "$DEPLOYMENT"
    verify_pushed "$DEPLOYMENT_RECEIPT"
    verify_pushed "$PANEL_SOURCE_RECEIPT_OBJECT"
    WEEK=$("$PYTHON" - "$PANEL_SOURCE_RECEIPT_OBJECT" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle)
if not isinstance(value, dict) or not isinstance(value.get("uri"), str):
    raise SystemExit("panel-source receipt object schema differs")
match = re.fullmatch(
    r"gs://nfl-predictions-503414-raw/research/"
    r"b1-corpus-tail-shadow-panel-sources/2026/week-(0[1-6])/[0-9a-f]{64}/"
    r"source-receipt\.json",
    value["uri"],
)
if match is None:
    raise SystemExit("panel-source receipt URI differs")
print(int(match.group(1)))
PY
    ) || die "panel-source receipt object cannot determine a canonical week"
    [[ "$WEEK" =~ ^[1-6]$ ]] || die "derived week must be 1 through 6"
    JOB=$(deployment_job)
    mkdir -p "$(week_dir "$WEEK")"
    capture_job_state "$JOB" "week-${WEEK}-prepare"
    run_transport validate-inert-job --deployment "$DEPLOYMENT" \
      --job "$OUT/job-week-${WEEK}-prepare.json" \
      --executions "$OUT/executions-week-${WEEK}-prepare.json" \
      --schedulers "$OUT/schedulers-week-${WEEK}-prepare.json"
    INTENT="$(week_dir "$WEEK")/freeze-intent.json"
    RECEIPT="$(week_dir "$WEEK")/freeze-intent-receipt.json"
    run_transport prepare-week --deployment "$DEPLOYMENT" \
      --deployment-receipt "$DEPLOYMENT_RECEIPT" \
      --panel-source-receipt-object "$PANEL_SOURCE_RECEIPT_OBJECT" \
      --output "$INTENT"
    run_transport publish-week --intent "$INTENT" --receipt "$RECEIPT"
    (
      cd "$(week_dir "$WEEK")"
      sha256sum freeze-intent.json freeze-intent.json.sha256 \
        freeze-intent-receipt.json freeze-intent-receipt.json.sha256 \
        > prepared.sha256
    )
    echo "B1_CORPUS_TAIL_SHADOW_WEEK_PREPARED week=$WEEK commit_and_push_before_launch=true"
    ;;

  launch-week)
    WEEK=${2:-}
    [[ "$WEEK" =~ ^[1-6]$ ]] || die "week must be 1 through 6"
    INTENT="$(week_dir "$WEEK")/freeze-intent.json"
    RECEIPT="$(week_dir "$WEEK")/freeze-intent-receipt.json"
    EXECUTIONS="$(week_dir "$WEEK")/freeze-execution.txt"
    [ ! -e "$EXECUTIONS" ] || die "week freeze already launched or ambiguous"
    verify_pushed "$DEPLOYMENT"
    verify_pushed "$INTENT"
    verify_pushed "$RECEIPT"
    JOB=$(deployment_job)
    capture_job_state "$JOB" "week-${WEEK}-launch"
    run_transport validate-inert-job --deployment "$DEPLOYMENT" \
      --job "$OUT/job-week-${WEEK}-launch.json" \
      --executions "$OUT/executions-week-${WEEK}-launch.json" \
      --schedulers "$OUT/schedulers-week-${WEEK}-launch.json"
    GENERATION=$(intent_generation "$RECEIPT")
    [[ "$GENERATION" =~ ^[1-9][0-9]*$ ]] || die "intent generation differs"
    EXECUTION=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
      --region "$REGION" --async --tasks 1 --task-timeout 4h \
      --update-env-vars CORPUS_TAIL_SHADOW_ENABLED=1 \
      --args "scripts/run_b1_corpus_tail_shadow_transport.py,execute-freeze,--week,$WEEK,--intent-generation,$GENERATION" \
      --format='value(metadata.name)')
    [[ "$EXECUTION" == "$JOB-"* ]] || die "freeze execution identity missing"
    printf '%s %s %s\n' "$JOB" "$EXECUTION" "$GENERATION" > "$EXECUTIONS"
    echo "B1_CORPUS_TAIL_SHADOW_FREEZE_LAUNCHED week=$WEEK execution=$EXECUTION"
    ;;

  harvest-week)
    WEEK=${2:-}
    PHASE=${3:-}
    [[ "$WEEK" =~ ^[1-6]$ ]] || die "week must be 1 through 6"
    case "$PHASE" in freeze|settlement) ;; *) die "phase must be freeze or settlement" ;; esac
    LEDGER="$(week_dir "$WEEK")/${PHASE}-execution.txt"
    [ -s "$LEDGER" ] || die "$PHASE execution ledger absent"
    read -r JOB EXECUTION EXTRA < "$LEDGER"
    [ -n "$JOB" ] && [ -n "$EXECUTION" ] || die "$PHASE execution ledger differs"
    META="$(week_dir "$WEEK")/${PHASE}-execution.json"
    capture_json "$META" gcloud run jobs executions describe "$EXECUTION" \
      --project "$PROJECT" --region "$REGION" --format=json
    ARGS=(--deployment "$DEPLOYMENT" --execution "$META" --phase "$PHASE" \
      --week "$WEEK" --output-dir "$(week_dir "$WEEK")/${PHASE}-harvest")
    if [ "$PHASE" = freeze ]; then
      ARGS+=(--intent-generation "$EXTRA")
    fi
    run_transport harvest "${ARGS[@]}"
    echo "B1_CORPUS_TAIL_SHADOW_HARVESTED week=$WEEK phase=$PHASE"
    ;;

  launch-settlement)
    WEEK=${2:-}
    [[ "$WEEK" =~ ^[1-6]$ ]] || die "week must be 1 through 6"
    [ -s "$(week_dir "$WEEK")/freeze-harvest/harvest.sha256" ] || \
      die "strict freeze harvest is absent"
    verify_harvest_pushed "$(week_dir "$WEEK")/freeze-harvest"
    EXECUTIONS="$(week_dir "$WEEK")/settlement-execution.txt"
    [ ! -e "$EXECUTIONS" ] || die "settlement already launched or ambiguous"
    JOB=$(deployment_job)
    capture_job_state "$JOB" "week-${WEEK}-settlement"
    run_transport validate-inert-job --deployment "$DEPLOYMENT" \
      --job "$OUT/job-week-${WEEK}-settlement.json" \
      --executions "$OUT/executions-week-${WEEK}-settlement.json" \
      --schedulers "$OUT/schedulers-week-${WEEK}-settlement.json"
    EXECUTION=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
      --region "$REGION" --async --tasks 1 --task-timeout 4h \
      --update-env-vars CORPUS_TAIL_SHADOW_ENABLED=0 \
      --args "scripts/run_b1_corpus_tail_shadow_transport.py,execute-settlement,--week,$WEEK" \
      --format='value(metadata.name)')
    [[ "$EXECUTION" == "$JOB-"* ]] || die "settlement execution identity missing"
    printf '%s %s -\n' "$JOB" "$EXECUTION" > "$EXECUTIONS"
    echo "B1_CORPUS_TAIL_SHADOW_SETTLEMENT_LAUNCHED week=$WEEK execution=$EXECUTION"
    ;;

  launch-adoption)
    for WEEK in 1 2 3 4 5 6; do
      [ -s "$(week_dir "$WEEK")/settlement-harvest/harvest.sha256" ] || \
        die "Week $WEEK strict settlement harvest is absent"
      verify_harvest_pushed "$(week_dir "$WEEK")/freeze-harvest"
      verify_harvest_pushed "$(week_dir "$WEEK")/settlement-harvest"
    done
    LEDGER="$OUT/adoption-execution.txt"
    [ ! -e "$LEDGER" ] || die "adoption already launched or ambiguous"
    JOB=$(deployment_job)
    capture_job_state "$JOB" adoption
    run_transport validate-inert-job --deployment "$DEPLOYMENT" \
      --job "$OUT/job-adoption.json" --executions "$OUT/executions-adoption.json" \
      --schedulers "$OUT/schedulers-adoption.json"
    EXECUTION=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
      --region "$REGION" --async --tasks 1 --task-timeout 4h \
      --update-env-vars CORPUS_TAIL_SHADOW_ENABLED=0 \
      --args "scripts/run_b1_corpus_tail_shadow_transport.py,execute-adoption" \
      --format='value(metadata.name)')
    [[ "$EXECUTION" == "$JOB-"* ]] || die "adoption execution identity missing"
    printf '%s %s\n' "$JOB" "$EXECUTION" > "$LEDGER"
    echo "B1_CORPUS_TAIL_SHADOW_ADOPTION_LAUNCHED execution=$EXECUTION"
    ;;

  harvest-adoption)
    [ -s "$OUT/adoption-execution.txt" ] || die "adoption execution ledger absent"
    read -r JOB EXECUTION < "$OUT/adoption-execution.txt"
    capture_json "$OUT/adoption-execution.json" gcloud run jobs executions describe \
      "$EXECUTION" --project "$PROJECT" --region "$REGION" --format=json
    run_transport harvest --deployment "$DEPLOYMENT" \
      --execution "$OUT/adoption-execution.json" --phase adoption \
      --output-dir "$OUT/adoption-harvest"
    echo "B1_CORPUS_TAIL_SHADOW_ADOPTION_HARVESTED"
    ;;

  *)
    die "usage: $0 {build-command|prepare|prepare-week|launch-week|harvest-week|launch-settlement|launch-adoption|harvest-adoption} ..."
    ;;
esac
