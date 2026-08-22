#!/usr/bin/env bash
# Reuse-only operator for the governed 54-slate artifact-source authority.
#
# Every mutating invocation requires both the literal --execute token and the
# source-authority enable environment. Configure, consume/launch, recover,
# bind, and watch/accept are separate actions. A consumed launch authority is
# never retried, including after an ambiguous gcloud response.

set -euo pipefail

PROJECT="nfl-predictions-503414"
REGION="us-central1"
PYTHON_BIN="${CORPUS_ARTIFACT_SOURCE_PYTHON:-.venv/bin/python}"
PREPARER="scripts/prepare_corpus_artifact_source_authority.py"
TRANSPORT="scripts/run_corpus_artifact_source_transport.py"

die() {
  printf '%s\n' "corpus artifact-source operator refused: $*" >&2
  exit 2
}

require_variable() {
  local name="$1"
  [[ -n "${!name:-}" ]] || die "${name} is required"
}

require_execute_gate() {
  [[ "${1:-}" == "--execute" ]] || die "literal --execute is required"
  [[ "${CORPUS_ARTIFACT_SOURCE_AUTHORITY_ENABLED:-}" == "1" ]] || \
    die "CORPUS_ARTIFACT_SOURCE_AUTHORITY_ENABLED=1 is required"
}

require_tools() {
  command -v gcloud >/dev/null || die "gcloud is required"
  command -v jq >/dev/null || die "jq is required"
  command -v curl >/dev/null || die "curl is required"
  [[ -x "$PYTHON_BIN" ]] || die "Python environment is absent: $PYTHON_BIN"
  [[ -f "$PREPARER" && -f "$TRANSPORT" ]] || die "source scripts are absent"
}

prepare_run_directory() {
  require_variable CORPUS_ARTIFACT_SOURCE_RUN_DIR
  [[ "$CORPUS_ARTIFACT_SOURCE_RUN_DIR" == /* ]] || \
    die "run directory must be absolute"
  [[ ! -L "$CORPUS_ARTIFACT_SOURCE_RUN_DIR" ]] || \
    die "run directory cannot be a symlink"
  mkdir -p "$CORPUS_ARTIFACT_SOURCE_RUN_DIR"
  CORPUS_ARTIFACT_SOURCE_RUN_DIR="$(realpath "$CORPUS_ARTIFACT_SOURCE_RUN_DIR")"
}

timestamp_for() {
  local key="$1"
  [[ "$key" =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "timestamp key is unsafe"
  local directory="$CORPUS_ARTIFACT_SOURCE_RUN_DIR/timestamps"
  [[ ! -L "$directory" ]] || die "timestamp directory is unsafe"
  mkdir -p "$directory"
  [[ -d "$directory" && ! -L "$directory" ]] || \
    die "timestamp directory is unsafe"
  local path="$directory/${key}.txt"
  if [[ ! -e "$path" ]]; then
    date -u +'%Y-%m-%dT%H:%M:%SZ' >"$path"
  fi
  [[ -f "$path" && ! -L "$path" ]] || die "timestamp authority is unsafe"
  tr -d '\n' <"$path"
}

new_attempt_directory() {
  local action="$1"
  local base="$CORPUS_ARTIFACT_SOURCE_RUN_DIR/${action}"
  local ordinal
  for ordinal in $(seq 1 999); do
    local candidate
    candidate="$(printf '%s-attempt-%03d' "$base" "$ordinal")"
    if mkdir "$candidate" 2>/dev/null; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  die "attempt namespace is exhausted"
}

contract_identity_args() {
  require_variable CORPUS_ARTIFACT_SOURCE_CONTRACT_URI
  require_variable CORPUS_ARTIFACT_SOURCE_CONTRACT_GENERATION
  require_variable CORPUS_ARTIFACT_SOURCE_CONTRACT_SHA256
  require_variable CORPUS_ARTIFACT_SOURCE_CONTRACT_BYTES
  printf '%s\n' \
    --contract-uri "$CORPUS_ARTIFACT_SOURCE_CONTRACT_URI" \
    --contract-generation "$CORPUS_ARTIFACT_SOURCE_CONTRACT_GENERATION" \
    --contract-sha256 "$CORPUS_ARTIFACT_SOURCE_CONTRACT_SHA256" \
    --contract-bytes "$CORPUS_ARTIFACT_SOURCE_CONTRACT_BYTES"
}

capture_job() {
  local output="$1"
  gcloud run jobs describe "$CORPUS_ARTIFACT_SOURCE_JOB" \
    --project "$PROJECT" --region "$REGION" --format=json >"$output"
}

build_rollback_export() {
  local captured="$1"
  local output="$2"
  jq -e --arg project "$PROJECT" '
    select(.metadata.name | type == "string" and length > 0) |
    select(.metadata.uid | type == "string" and length > 0) |
    select(.metadata.resourceVersion | type == "string" and length > 0) |
    select(.spec | type == "object") |
    {
      apiVersion: "run.googleapis.com/v1",
      kind: "Job",
      metadata: {
        name: .metadata.name,
        namespace: $project,
        resourceVersion: .metadata.resourceVersion,
        labels: (.metadata.labels // {}),
        annotations: (.metadata.annotations // {})
      },
      spec: .spec
    }
  ' "$captured" >"$output"
}

rollback_existing_job() {
  local prior_job="$1"
  local prior_export="$2"
  local directory="$3"
  local current="$directory/rollback-current.json"
  local request="$directory/rollback-request.json"
  local response="$directory/rollback-response.json"
  local restored="$directory/rollback-restored.json"
  capture_job "$current"
  jq -e -s '
    .[0].metadata.name == .[1].metadata.name and
    .[0].metadata.uid == .[1].metadata.uid
  ' "$prior_job" "$current" >/dev/null || {
    printf '%s\n' "rollback refused: reused job identity changed" >&2
    return 1
  }
  if jq -e -s '.[0].spec == .[1].spec' "$prior_job" "$current" >/dev/null; then
    cp --no-clobber "$current" "$restored"
    printf '%s\n' "rollback not needed: prior job spec is still present" >&2
    return 0
  fi
  local current_resource_version
  current_resource_version="$(jq -er '.metadata.resourceVersion' "$current")"
  jq -e --arg resource_version "$current_resource_version" \
    '.metadata.resourceVersion = $resource_version' \
    "$prior_export" >"$request"
  {
    printf '%s' 'Authorization: Bearer '
    gcloud auth print-access-token
  } | curl --fail-with-body --silent --show-error \
    --request PUT --header @- --header 'Content-Type: application/json' \
    --data-binary "@$request" \
    "https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${CORPUS_ARTIFACT_SOURCE_JOB}" \
    >"$response"
  capture_job "$restored"
  jq -e -s '
    .[0].metadata.name == .[1].metadata.name and
    .[0].metadata.uid == .[1].metadata.uid and
    .[0].spec == .[1].spec
  ' "$prior_job" "$restored" >/dev/null || {
    printf '%s\n' "rollback response did not restore the exact prior job" >&2
    return 1
  }
  printf '%s\n' "exact prior reused-job spec restored after configure failure" >&2
}

capture_executions() {
  local output="$1"
  gcloud run jobs executions list --job "$CORPUS_ARTIFACT_SOURCE_JOB" \
    --project "$PROJECT" --region "$REGION" --format=json >"$output"
}

capture_all_region_schedulers() {
  local output="$1"
  [[ ! -e "$output" ]] || die "scheduler capture already exists: $output"
  local stem parent locations fragments location
  stem="$(basename "$output" .json)"
  parent="$(dirname "$output")"
  locations="$parent/${stem}-locations.json"
  fragments="$parent/${stem}-fragments"
  [[ ! -e "$locations" && ! -e "$fragments" ]] || \
    die "scheduler census namespace already exists"
  mkdir -p "$fragments"
  gcloud scheduler locations list --project "$PROJECT" --format=json >"$locations"
  while IFS= read -r location; do
    [[ -n "$location" ]] || continue
    gcloud scheduler jobs list --project "$PROJECT" --location "$location" \
      --format=json >"$fragments/${location}.json"
  done < <(jq -r '.[].locationId' "$locations" | LC_ALL=C sort)
  jq -s 'add // []' "$fragments"/*.json >"$output"
}

configure_mode() {
  require_variable CORPUS_ARTIFACT_SOURCE_JOB
  require_variable CORPUS_ARTIFACT_SOURCE_IMAGE
  require_variable CORPUS_ARTIFACT_SOURCE_BUILD_ID
  require_variable CORPUS_ARTIFACT_SOURCE_CODE_SHA
  require_variable CORPUS_ARTIFACT_SOURCE_SERVICE_ACCOUNT
  require_variable CORPUS_ARTIFACT_SOURCE_PLAN_FILE
  require_variable CORPUS_ARTIFACT_SOURCE_RUNTIME_IAM_FILE
  require_variable CORPUS_ARTIFACT_SOURCE_DELIVERY_PREFIX
  [[ ! -e "$CORPUS_ARTIFACT_SOURCE_RUN_DIR/configured.json" ]] || \
    die "configure receipt already exists"
  "$PYTHON_BIN" "$TRANSPORT" validate-only \
    --plan-file "$CORPUS_ARTIFACT_SOURCE_PLAN_FILE" >/dev/null

  local before_job before_export before_executions before_schedulers build_file
  before_job="$CORPUS_ARTIFACT_SOURCE_RUN_DIR/job-before.json"
  before_export="$CORPUS_ARTIFACT_SOURCE_RUN_DIR/job-before-export.json"
  before_executions="$CORPUS_ARTIFACT_SOURCE_RUN_DIR/executions-before.json"
  before_schedulers="$CORPUS_ARTIFACT_SOURCE_RUN_DIR/schedulers-before.json"
  build_file="$CORPUS_ARTIFACT_SOURCE_RUN_DIR/build-metadata.json"
  capture_job "$before_job"
  build_rollback_export "$before_job" "$before_export"
  capture_executions "$before_executions"
  capture_all_region_schedulers "$before_schedulers"
  gcloud builds describe "$CORPUS_ARTIFACT_SOURCE_BUILD_ID" \
    --project "$PROJECT" --format=json >"$build_file"
  "$PYTHON_BIN" "$TRANSPORT" validate-build \
    --build-metadata-file "$build_file" \
    --build-id "$CORPUS_ARTIFACT_SOURCE_BUILD_ID" \
    --code-sha "$CORPUS_ARTIFACT_SOURCE_CODE_SHA" \
    --image "$CORPUS_ARTIFACT_SOURCE_IMAGE" >/dev/null
  jq -e 'all(.[]; ([.status.conditions[]? | select(.type == "Completed")][0].status // "Unknown") != "Unknown")' \
    "$before_executions" >/dev/null || die "reused job has an active execution"
  jq -e --arg needle "/jobs/${CORPUS_ARTIFACT_SOURCE_JOB}:run" \
    'all(.[]; ((.httpTarget.uri // "") | contains($needle) | not))' \
    "$before_schedulers" >/dev/null || die "a scheduler targets the reused job"

  CORPUS_SOURCE_ROLLBACK_ARMED=1
  CORPUS_SOURCE_ROLLBACK_PRIOR_JOB="$before_job"
  CORPUS_SOURCE_ROLLBACK_PRIOR_EXPORT="$before_export"
  CORPUS_SOURCE_ROLLBACK_DIRECTORY="$CORPUS_ARTIFACT_SOURCE_RUN_DIR"
  configure_exit() {
    local status=$?
    trap - EXIT
    if [[ "${CORPUS_SOURCE_ROLLBACK_ARMED:-0}" == "1" ]]; then
      if ! rollback_existing_job \
        "$CORPUS_SOURCE_ROLLBACK_PRIOR_JOB" \
        "$CORPUS_SOURCE_ROLLBACK_PRIOR_EXPORT" \
        "$CORPUS_SOURCE_ROLLBACK_DIRECTORY"; then
        printf '%s\n' "automatic exact-job rollback failed; manual recovery required" >&2
        status=1
      fi
    fi
    exit "$status"
  }
  trap configure_exit EXIT

  gcloud run jobs update "$CORPUS_ARTIFACT_SOURCE_JOB" \
    --project "$PROJECT" --region "$REGION" \
    --image "$CORPUS_ARTIFACT_SOURCE_IMAGE" \
    --command python \
    --args "$PREPARER,parked" \
    --clear-secrets --clear-volumes --clear-volume-mounts \
    --clear-vpc-connector --clear-cloudsql-instances \
    --clear-network --clear-network-tags --clear-labels \
    --startup-probe="" --workdir="" \
    --set-env-vars "CORPUS_ARTIFACT_SOURCE_AUTHORITY_ENABLED=1,CORPUS_ARTIFACT_SOURCE_IMAGE=${CORPUS_ARTIFACT_SOURCE_IMAGE},CORPUS_ARTIFACT_SOURCE_BUILD_ID=${CORPUS_ARTIFACT_SOURCE_BUILD_ID},CODE_SHA=${CORPUS_ARTIFACT_SOURCE_CODE_SHA}" \
    --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 86400s \
    --cpu 8 --memory 32Gi \
    --service-account "$CORPUS_ARTIFACT_SOURCE_SERVICE_ACCOUNT" \
    --quiet >/dev/null

  local after_job after_executions after_schedulers
  after_job="$CORPUS_ARTIFACT_SOURCE_RUN_DIR/job-after.json"
  after_executions="$CORPUS_ARTIFACT_SOURCE_RUN_DIR/executions-after.json"
  after_schedulers="$CORPUS_ARTIFACT_SOURCE_RUN_DIR/schedulers-after.json"
  capture_job "$after_job"
  "$PYTHON_BIN" "$TRANSPORT" validate-parked-job \
    --job-file "$after_job" --build-metadata-file "$build_file" \
    --build-id "$CORPUS_ARTIFACT_SOURCE_BUILD_ID" \
    --code-sha "$CORPUS_ARTIFACT_SOURCE_CODE_SHA" \
    --image "$CORPUS_ARTIFACT_SOURCE_IMAGE" \
    --service-account "$CORPUS_ARTIFACT_SOURCE_SERVICE_ACCOUNT" >/dev/null
  capture_executions "$after_executions"
  capture_all_region_schedulers "$after_schedulers"
  "$PYTHON_BIN" "$TRANSPORT" configure \
    --plan-file "$CORPUS_ARTIFACT_SOURCE_PLAN_FILE" \
    --runtime-iam-file "$CORPUS_ARTIFACT_SOURCE_RUNTIME_IAM_FILE" \
    --delivery-prefix "$CORPUS_ARTIFACT_SOURCE_DELIVERY_PREFIX" \
    --build-metadata-file "$build_file" \
    --build-id "$CORPUS_ARTIFACT_SOURCE_BUILD_ID" \
    --code-sha "$CORPUS_ARTIFACT_SOURCE_CODE_SHA" \
    --image "$CORPUS_ARTIFACT_SOURCE_IMAGE" \
    --service-account "$CORPUS_ARTIFACT_SOURCE_SERVICE_ACCOUNT" \
    --job-before-file "$before_job" --job-after-file "$after_job" \
    --executions-before-file "$before_executions" \
    --executions-after-file "$after_executions" \
    --schedulers-before-file "$before_schedulers" \
    --schedulers-after-file "$after_schedulers" \
    --all-regions-complete --created-at-utc "$(timestamp_for configured)" \
    --execute >"$CORPUS_ARTIFACT_SOURCE_RUN_DIR/configured.json"
  CORPUS_SOURCE_ROLLBACK_ARMED=0
  trap - EXIT
}

consume_launch_mode() {
  require_variable CORPUS_ARTIFACT_SOURCE_JOB
  local attempt job_file executions_file schedulers_file ready_file response_file
  attempt="$(new_attempt_directory consume-launch)"
  job_file="$attempt/job.json"
  executions_file="$attempt/executions.json"
  schedulers_file="$attempt/schedulers.json"
  ready_file="$attempt/launch-ready.json"
  response_file="$attempt/launch-response.json"
  capture_job "$job_file"
  capture_executions "$executions_file"
  capture_all_region_schedulers "$schedulers_file"
  mapfile -t identity_args < <(contract_identity_args)
  "$PYTHON_BIN" "$TRANSPORT" consume-launch \
    "${identity_args[@]}" --job-file "$job_file" \
    --executions-file "$executions_file" --schedulers-file "$schedulers_file" \
    --all-regions-complete --created-at-utc "$(timestamp_for launch-consumed)" \
    --execute >"$ready_file"
  jq -e '.launch_permitted == true and .automatic_retry_licensed == false' \
    "$ready_file" >/dev/null || die "launch is consumed; recover only"
  local joined_args
  joined_args="$(jq -r '.worker_args | join(",")' "$ready_file")"
  set +e
  gcloud run jobs execute "$CORPUS_ARTIFACT_SOURCE_JOB" \
    --project "$PROJECT" --region "$REGION" --args "$joined_args" \
    --async --format=json >"$response_file"
  local status=$?
  set -e
  if [[ "$status" -ne 0 ]]; then
    printf '%s\n' "launch response ambiguous; run recover only, never relaunch" >&2
    return "$status"
  fi
  printf '%s\n' "launch consumed; run recover as a separate action"
}

recover_mode() {
  require_variable CORPUS_ARTIFACT_SOURCE_JOB
  local attempt job_file executions_file schedulers_file candidate_file execution_id execution_file
  attempt="$(new_attempt_directory recover)"
  job_file="$attempt/job.json"
  executions_file="$attempt/executions.json"
  schedulers_file="$attempt/schedulers.json"
  candidate_file="$attempt/recovery-candidate.json"
  execution_file="$attempt/execution.json"
  capture_job "$job_file"
  capture_executions "$executions_file"
  capture_all_region_schedulers "$schedulers_file"
  mapfile -t identity_args < <(contract_identity_args)
  "$PYTHON_BIN" "$TRANSPORT" recover-name \
    "${identity_args[@]}" --job-file "$job_file" \
    --executions-file "$executions_file" --schedulers-file "$schedulers_file" \
    --all-regions-complete --execute \
    >"$candidate_file"
  execution_id="$(jq -er '.execution_id' "$candidate_file")"
  gcloud run jobs executions describe "$execution_id" \
    --project "$PROJECT" --region "$REGION" --format=json >"$execution_file"
  printf '%s\n' "recovered metadata: $execution_file; bind is a separate action"
}

bind_mode() {
  require_variable CORPUS_ARTIFACT_SOURCE_JOB
  require_variable CORPUS_ARTIFACT_SOURCE_EXECUTION_FILE
  [[ -f "$CORPUS_ARTIFACT_SOURCE_EXECUTION_FILE" && \
     ! -L "$CORPUS_ARTIFACT_SOURCE_EXECUTION_FILE" ]] || \
    die "execution metadata file is unsafe"
  [[ ! -e "$CORPUS_ARTIFACT_SOURCE_RUN_DIR/execution-bound.json" ]] || \
    die "execution is already locally bound"
  local attempt job_file executions_file schedulers_file result_file
  attempt="$(new_attempt_directory bind)"
  job_file="$attempt/job.json"
  executions_file="$attempt/executions.json"
  schedulers_file="$attempt/schedulers.json"
  result_file="$attempt/execution-bound.json"
  capture_job "$job_file"
  capture_executions "$executions_file"
  capture_all_region_schedulers "$schedulers_file"
  mapfile -t identity_args < <(contract_identity_args)
  "$PYTHON_BIN" "$TRANSPORT" bind-execution \
    "${identity_args[@]}" \
    --execution-metadata-file "$CORPUS_ARTIFACT_SOURCE_EXECUTION_FILE" \
    --job-file "$job_file" --executions-file "$executions_file" \
    --schedulers-file "$schedulers_file" --all-regions-complete \
    --created-at-utc "$(timestamp_for execution-bound)" --execute \
    >"$result_file"
  cp --no-clobber "$result_file" \
    "$CORPUS_ARTIFACT_SOURCE_RUN_DIR/execution-bound.json"
  printf '%s\n' "execution bound; watch is a separate action"
}

watch_mode() {
  require_variable CORPUS_ARTIFACT_SOURCE_JOB
  local bound execution_id attempt terminal_file completed job_file executions_file schedulers_file result_file
  bound="$CORPUS_ARTIFACT_SOURCE_RUN_DIR/execution-bound.json"
  [[ -f "$bound" && ! -L "$bound" ]] || die "bound execution receipt is absent"
  execution_id="$(jq -er '.execution_id' "$bound")"
  attempt="$(new_attempt_directory watch)"
  terminal_file="$attempt/execution.json"
  gcloud run jobs executions describe "$execution_id" \
    --project "$PROJECT" --region "$REGION" --format=json >"$terminal_file"
  completed="$(jq -r '[.status.conditions[]? | select(.type == "Completed")][0].status // "Unknown"' "$terminal_file")"
  if [[ "$completed" == "Unknown" ]]; then
    printf '%s\n' "execution is nonterminal; invoke watch again later"
    return 3
  fi
  [[ "$completed" == "True" ]] || die "execution failed/cancelled; no retry licensed"
  job_file="$attempt/job.json"
  executions_file="$attempt/executions.json"
  schedulers_file="$attempt/schedulers.json"
  result_file="$attempt/terminal-accepted.json"
  capture_job "$job_file"
  capture_executions "$executions_file"
  capture_all_region_schedulers "$schedulers_file"
  mapfile -t identity_args < <(contract_identity_args)
  "$PYTHON_BIN" "$TRANSPORT" accept-terminal \
    "${identity_args[@]}" --execution-metadata-file "$terminal_file" \
    --job-file "$job_file" --executions-file "$executions_file" \
    --schedulers-file "$schedulers_file" --all-regions-complete \
    --accepted-at-utc "$(timestamp_for terminal-accepted)" --execute \
    >"$result_file"
  if [[ ! -e "$CORPUS_ARTIFACT_SOURCE_RUN_DIR/terminal-accepted.json" ]]; then
    cp --no-clobber "$result_file" \
      "$CORPUS_ARTIFACT_SOURCE_RUN_DIR/terminal-accepted.json"
  fi
  printf '%s\n' "exact source authority independently replayed and accepted"
}

main() {
  require_execute_gate "${1:-}"
  local mode="${2:-}"
  [[ -n "$mode" ]] || die "mode is required"
  require_tools
  prepare_run_directory
  case "$mode" in
    configure) configure_mode ;;
    consume-launch) consume_launch_mode ;;
    recover) recover_mode ;;
    bind) bind_mode ;;
    watch) watch_mode ;;
    *) die "unknown mode: $mode" ;;
  esac
}

main "$@"
