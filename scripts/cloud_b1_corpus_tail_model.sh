#!/usr/bin/env bash
set -euo pipefail

# Reuse-only transport for the frozen B1 generated-corpus tail one-shot.
#
# Usage:
#   cloud_b1_corpus_tail_model.sh build-command CODE_SHA
#   cloud_b1_corpus_tail_model.sh prepare IMAGE CODE_SHA BUILD_ID
#   cloud_b1_corpus_tail_model.sh launch

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260820-b1-corpus-tail-model-v1
JOB=atlas-minimal-c-s2023-w1-v1
OUT="$ROOT/reports/b1-corpus-tail-runs/$RUN_ID"
ATTEMPT_URI="gs://nfl-predictions-503414-raw/research/b1-corpus-tail-runs/$RUN_ID/historical-attempt.json"
REPORT_URI="gs://nfl-predictions-503414-raw/research/b1-corpus-tail-runs/$RUN_ID/historical-report.json"
MODEL_URI="gs://nfl-predictions-503414-raw/research/b1-corpus-tail-runs/$RUN_ID/model.json"
FINISHER="$ROOT/scripts/finish_b1_corpus_tail_model.py"
PYTHON="$ROOT/.venv/bin/python"
COMMAND=${1:-}

die() {
  echo "ERROR: $*" >&2
  exit 2
}

for repair_name in B1_CORPUS_TAIL_FINISHER_REPAIR_SHA256 \
  B1_CORPUS_TAIL_LAUNCHER_REPAIR_SHA256 \
  B1_CORPUS_TAIL_WATCHER_REPAIR_SHA256; do
  repair_value=${!repair_name:-}
  [ -z "$repair_value" ] || [[ "$repair_value" =~ ^[0-9a-f]{64}$ ]] || \
    die "$repair_name differs"
done

capture_json() {
  local target=$1
  shift
  local raw="$target.gcloud.raw.pending"
  [ ! -e "$target" ] && [ ! -e "$raw" ] || \
    die "immutable external JSON path already exists: $target"
  if ! "$@" > "$raw"; then
    die "external JSON command failed; raw response retained: $raw"
  fi
  if ! PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      canonicalize-external-json --raw "$raw" --output "$target"; then
    die "external JSON canonicalization failed; raw retained: $raw"
  fi
  rm -- "$raw"
}

capture_job_state() {
  local suffix=$1
  capture_json "$OUT/job-$suffix.json" gcloud run jobs describe "$JOB" \
    --project "$PROJECT" --region "$REGION" --format=json
  capture_json "$OUT/job-executions-$suffix.json" gcloud run jobs executions \
    list --job "$JOB" --project "$PROJECT" --region "$REGION" --format=json
  capture_json "$OUT/schedulers-$suffix.json" gcloud scheduler jobs list \
    --project "$PROJECT" --location "$REGION" --format=json
}

case "$COMMAND" in
  build-command)
    CODE_SHA=${2:-}
    [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "full source commit required"
    TAG="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:b1-tail-${CODE_SHA:0:7}"
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
      die "immutable B1 image required"
    [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "full source commit required"
    [[ "$BUILD_ID" =~ ^[0-9A-Za-z-]{8,80}$ ]] || die "build ID differs"
    git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}" || die "source commit absent"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-a2a-terminal --code-sha "$CODE_SHA"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-smoke-staging --output-dir "$OUT" --code-sha "$CODE_SHA"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" check-empty-prefix
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" check-lease-absent
    trap 'echo "ERROR: B1 prepare stopped; immutable directory retained" >&2' ERR
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      capture-empty-prefix --output "$OUT/prefix-before.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      capture-lease-absence --output "$OUT/lease-before.json"
    capture_json "$OUT/build-metadata.json" gcloud builds describe "$BUILD_ID" \
      --project "$PROJECT" --format=json
    capture_job_state before
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-prepare-inputs --code-sha "$CODE_SHA" --image "$IMAGE" \
      --build-id "$BUILD_ID" --build-metadata "$OUT/build-metadata.json" \
      --job-before "$OUT/job-before.json" \
      --executions-before "$OUT/job-executions-before.json" \
      --schedulers-before "$OUT/schedulers-before.json"

    # This is an update of the known existing job, never a create.  Its default
    # args are inert; only the one launch below overrides them to execute-frozen.
    gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 8 --memory 32Gi \
      --max-retries 0 --task-timeout 4h \
      --clear-volumes --clear-volume-mounts --workdir="" --startup-probe="" \
      --clear-secrets --service-account "$SERVICE_ACCOUNT" \
      --set-env-vars "B1_CORPUS_TAIL_HISTORICAL_ENABLED=1,ANALYSIS_IMAGE=$IMAGE,CODE_SHA=$CODE_SHA" \
      --command python --args "scripts/finish_b1_corpus_tail_model.py,--help" \
      --quiet >/dev/null
    capture_job_state after
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      capture-empty-prefix --output "$OUT/prefix-after.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      capture-lease-absence --output "$OUT/lease-after.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      prepare-manifest --code-sha "$CODE_SHA" --image "$IMAGE" \
      --build-id "$BUILD_ID" --build-metadata "$OUT/build-metadata.json" \
      --job-before "$OUT/job-before.json" --job-after "$OUT/job-after.json" \
      --executions-before "$OUT/job-executions-before.json" \
      --executions-after "$OUT/job-executions-after.json" \
      --schedulers-before "$OUT/schedulers-before.json" \
      --schedulers-after "$OUT/schedulers-after.json" \
      --prefix-before "$OUT/prefix-before.json" \
      --prefix-after "$OUT/prefix-after.json" \
      --lease-before "$OUT/lease-before.json" \
      --lease-after "$OUT/lease-after.json" --output "$OUT/manifest.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      publish-manifest --manifest "$OUT/manifest.json" \
      --receipt "$OUT/manifest-object.json"
    (
      cd "$OUT"
      sha256sum build-metadata.json job-before.json job-after.json \
        job-executions-before.json job-executions-after.json \
        schedulers-before.json schedulers-after.json prefix-before.json \
        prefix-after.json lease-before.json lease-after.json manifest.json \
        manifest-object.json > prepared.sha256
    )
    trap - ERR
    echo "B1_CORPUS_TAIL_PREPARED commit_and_push_manifest_before_launch=true"
    ;;

  launch)
    [ -s "$OUT/prepared.sha256" ] || die "B1 prepared receipt absent"
    [ -s "$OUT/lease-receipt.json" ] || die "B1 lease receipt absent"
    [ ! -e "$OUT/executions.txt" ] && [ ! -e "$OUT/launch-intent.json" ] || \
      die "B1 launch already registered or ambiguous"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      verify-pushed-manifest --output-dir "$OUT" --remote-ref origin/main
    capture_job_state launch
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      capture-empty-prefix --output "$OUT/prefix-launch.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-launch-ready --output-dir "$OUT" \
      --job-current "$OUT/job-launch.json" \
      --executions "$OUT/job-executions-launch.json" \
      --schedulers "$OUT/schedulers-launch.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      publish-launch-intent --output-dir "$OUT"
    INTENT_GENERATION=$(PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      intent-generation --output-dir "$OUT")
    [[ "$INTENT_GENERATION" =~ ^[1-9][0-9]*$ ]] || die "intent generation differs"
    capture_job_state launch-final
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      capture-empty-prefix --output "$OUT/prefix-launch-final.json"
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-launch-ready --output-dir "$OUT" \
      --job-current "$OUT/job-launch-final.json" \
      --executions "$OUT/job-executions-launch-final.json" \
      --schedulers "$OUT/schedulers-launch-final.json" --require-intent

    EXECUTION=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
      --region "$REGION" --async \
      --args "scripts/finish_b1_corpus_tail_model.py,execute-frozen,--launch-intent-generation,$INTENT_GENERATION" \
      --format='value(metadata.name)')
    [[ "$EXECUTION" == "$JOB-"* ]] || die "B1 execution identity missing"
    printf '%s %s %s %s %s %s\n' "$JOB" "$EXECUTION" "$ATTEMPT_URI" \
      "$REPORT_URI" "$MODEL_URI" "$INTENT_GENERATION" > "$OUT/executions.txt"
    (
      cd "$OUT"
      sha256sum prepared.sha256 manifest.json manifest-object.json \
        lease-receipt.json job-launch.json job-executions-launch.json \
        schedulers-launch.json prefix-launch.json launch-intent.json \
        launch-intent-object.json job-launch-final.json \
        job-executions-launch-final.json schedulers-launch-final.json \
        prefix-launch-final.json executions.txt > launch.sha256
    )
    echo "B1_CORPUS_TAIL_LAUNCHED $EXECUTION"
    ;;

  *)
    die "usage: $0 {build-command|prepare|launch} ..."
    ;;
esac
