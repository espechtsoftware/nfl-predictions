#!/usr/bin/env bash
# Reuse exactly one parked Cloud Run job for the one-read realized corpus grade.
#
# The historical lease receipt is not a secret and is never smuggled through an
# environment variable, Secret Manager alias, local mount, or mutable path.  A
# create-once GCS receipt identity (URI/generation/SHA-256/bytes) is placed in
# the exact execution argv.  An ambiguous execute response is census-only and
# can never result in a second launch request.

set -euo pipefail

PROJECT="${CORPUS_REALIZED_PROJECT:-nfl-predictions-503414}"
REGION="${CORPUS_REALIZED_REGION:-us-central1}"
PYTHON_BIN="${CORPUS_REALIZED_PYTHON:-.venv/bin/python}"
TRANSPORT_SCRIPT="scripts/run_corpus_realized_cloud_transport.py"
OUTPUT_BUCKET="nfl-predictions-503414-corpus-retrieval"
OUTPUT_NAMESPACE="research/corpus-realized-outcomes"

die() {
  printf '%s\n' "corpus realized operator refused: $*" >&2
  exit 2
}

require_variable() {
  local name="$1"
  [[ -n "${!name:-}" ]] || die "${name} is required"
}

require_execute() {
  [[ "${1:-}" == "--execute" ]] || die "literal --execute is required"
  [[ "${CORPUS_REALIZED_TRANSPORT_ENABLED:-}" == "1" ]] || \
    die "CORPUS_REALIZED_TRANSPORT_ENABLED=1 is required"
}

require_tools() {
  command -v gcloud >/dev/null || die "gcloud is required"
  command -v jq >/dev/null || die "jq is required"
  command -v curl >/dev/null || die "curl is required"
  [[ -x "$PYTHON_BIN" ]] || die "Python environment is absent: $PYTHON_BIN"
  [[ -f "$TRANSPORT_SCRIPT" ]] || die "realized transport script is absent"
}

prepare_run_dir() {
  require_variable CORPUS_REALIZED_RUN_DIR
  [[ "$CORPUS_REALIZED_RUN_DIR" == /* ]] || die "run directory must be absolute"
  [[ ! -L "$CORPUS_REALIZED_RUN_DIR" ]] || die "run directory cannot be a symlink"
  mkdir -p "$CORPUS_REALIZED_RUN_DIR"
  CORPUS_REALIZED_RUN_DIR="$(realpath "$CORPUS_REALIZED_RUN_DIR")"
}

require_contract() {
  local name
  for name in RUN_ID BUILD_ID CODE_SHA IMAGE BUILD_METADATA_FILE JOB JOB_UID \
    SERVICE_ACCOUNT BATCH_ACCEPTANCE_URI BATCH_ACCEPTANCE_GENERATION \
    BATCH_ACCEPTANCE_SHA256 BATCH_ACCEPTANCE_BYTES; do
    require_variable "CORPUS_REALIZED_${name}"
  done
  [[ "$CORPUS_REALIZED_RUN_ID" =~ ^[a-z0-9][a-z0-9-]{7,80}$ ]] || \
    die "run id syntax differs"
  (( ${#CORPUS_REALIZED_RUN_ID} <= 81 )) || die "run id exceeds 81 characters"
  [[ "$CORPUS_REALIZED_BUILD_METADATA_FILE" == /* ]] || \
    die "build metadata path must be absolute"
  [[ -f "$CORPUS_REALIZED_BUILD_METADATA_FILE" && \
     ! -L "$CORPUS_REALIZED_BUILD_METADATA_FILE" ]] || \
    die "build metadata file is absent or unsafe"
}

config_args() {
  printf '%s\n' \
    --project "$PROJECT" \
    --run-id "$CORPUS_REALIZED_RUN_ID" \
    --build-id "$CORPUS_REALIZED_BUILD_ID" \
    --code-sha "$CORPUS_REALIZED_CODE_SHA" \
    --image "$CORPUS_REALIZED_IMAGE" \
    --job "$CORPUS_REALIZED_JOB" \
    --job-uid "$CORPUS_REALIZED_JOB_UID" \
    --service-account "$CORPUS_REALIZED_SERVICE_ACCOUNT" \
    --batch-acceptance-uri "$CORPUS_REALIZED_BATCH_ACCEPTANCE_URI" \
    --batch-acceptance-generation "$CORPUS_REALIZED_BATCH_ACCEPTANCE_GENERATION" \
    --batch-acceptance-sha256 "$CORPUS_REALIZED_BATCH_ACCEPTANCE_SHA256" \
    --batch-acceptance-bytes "$CORPUS_REALIZED_BATCH_ACCEPTANCE_BYTES"
}

timestamp_for() {
  local key="$1"
  [[ "$key" =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "timestamp key is unsafe"
  local directory="$CORPUS_REALIZED_RUN_DIR/timestamps"
  [[ ! -L "$directory" ]] || die "timestamp directory is unsafe"
  mkdir -p "$directory"
  local path="$directory/${key}.txt"
  if [[ ! -e "$path" ]]; then
    date -u +'%Y-%m-%dT%H:%M:%SZ' >"$path"
  fi
  [[ -f "$path" && ! -L "$path" ]] || die "timestamp authority is unsafe"
  tr -d '\n' <"$path"
}

new_attempt_directory() {
  local action="$1" ordinal candidate
  for ordinal in $(seq 1 999); do
    candidate="$(printf '%s/%s-attempt-%03d' \
      "$CORPUS_REALIZED_RUN_DIR" "$action" "$ordinal")"
    if mkdir "$candidate" 2>/dev/null; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  die "attempt namespace exhausted for ${action}"
}

capture_job() {
  local output="$1"
  gcloud run jobs describe "$CORPUS_REALIZED_JOB" \
    --project "$PROJECT" --region "$REGION" --format=json >"$output"
}

capture_reconciled_job() {
  local output="$1" poll="${output}.poll" ordinal
  for ordinal in $(seq 1 30); do
    capture_job "$poll"
    if jq -e '
      (.metadata.generation | tostring) == (.status.observedGeneration | tostring) and
      any(.status.conditions[]?; .type == "Ready" and .status == "True")
    ' "$poll" >/dev/null; then
      mv "$poll" "$output"
      return 0
    fi
    sleep 2
  done
  mv "$poll" "$output"
  return 1
}

capture_executions() {
  local output="$1"
  gcloud run jobs executions list --job "$CORPUS_REALIZED_JOB" \
    --project "$PROJECT" --region "$REGION" --format=json >"$output"
}

capture_execution() {
  local execution_id="$1" output="$2"
  gcloud run jobs executions describe "$execution_id" \
    --project "$PROJECT" --region "$REGION" --format=json >"$output"
}

capture_all_region_schedulers() {
  local output="$1"
  [[ ! -e "$output" ]] || die "scheduler census already exists: $output"
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

validate_reuse_files() {
  local job="$1" executions="$2" schedulers="$3" output="$4"
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" validate-reuse-preflight \
    --job "$CORPUS_REALIZED_JOB" --job-uid "$CORPUS_REALIZED_JOB_UID" \
    --job-file "$job" --executions-file "$executions" \
    --schedulers-file "$schedulers" --all-regions-complete >"$output"
}

validate_parked_file() {
  local job="$1" output="$2"
  mapfile -t contract < <(config_args)
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" validate-parked-job \
    "${contract[@]}" --job-file "$job" >"$output"
}

build_rollback_export() {
  local captured="$1" output="$2"
  jq -e --arg project "$PROJECT" '
    select(.metadata.name | type == "string" and length > 0) |
    select(.metadata.uid | type == "string" and length > 0) |
    select(.metadata.resourceVersion | type == "string" and length > 0) |
    select(.spec | type == "object") |
    {
      apiVersion: "run.googleapis.com/v1", kind: "Job",
      metadata: {
        name: .metadata.name, namespace: $project,
        resourceVersion: .metadata.resourceVersion,
        labels: (.metadata.labels // {}),
        annotations: (.metadata.annotations // {})
      },
      spec: .spec
    }
  ' "$captured" >"$output"
}

put_existing_job() {
  local request="$1" response="$2"
  {
    printf '%s' 'Authorization: Bearer '
    gcloud auth print-access-token
  } | curl --fail-with-body --silent --show-error \
    --request PUT --header @- --header 'Content-Type: application/json' \
    --data-binary "@$request" \
    "https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${CORPUS_REALIZED_JOB}" \
    >"$response"
}

rollback_job() {
  local expected="$1" rollback_export="$2" directory="$3"
  local current="$directory/rollback-current.json"
  local request="$directory/rollback-request.json"
  capture_job "$current" || return 1
  jq -e -s '
    .[0].metadata.name == .[1].metadata.name and
    .[0].metadata.uid == .[1].metadata.uid
  ' "$expected" "$current" >/dev/null || return 1
  if jq -e -s '.[0].spec == .[1].spec' "$expected" "$current" >/dev/null; then
    cp --no-clobber "$current" "$directory/rollback-restored.json"
    return 0
  fi
  jq -e --arg resource_version "$(jq -er '.metadata.resourceVersion' "$current")" \
    '.metadata.resourceVersion = $resource_version' "$rollback_export" >"$request"
  put_existing_job "$request" "$directory/rollback-response.json" || return 1
  capture_reconciled_job "$directory/rollback-restored.json" || return 1
  jq -e -s '
    .[0].metadata.name == .[1].metadata.name and
    .[0].metadata.uid == .[1].metadata.uid and
    .[0].spec == .[1].spec
  ' "$expected" "$directory/rollback-restored.json" >/dev/null
}

configure_mode() {
  require_execute "${1:-}"
  local attempt before_job rollback_export request response
  local before_executions before_schedulers preflight
  local after_job after_executions after_schedulers parked_check
  attempt="$(new_attempt_directory configure)"
  before_job="$attempt/job-before.json"
  rollback_export="$attempt/rollback-export.json"
  request="$attempt/update-request.json"
  response="$attempt/update-response.json"
  before_executions="$attempt/executions-before.json"
  before_schedulers="$attempt/schedulers-before.json"
  preflight="$attempt/preflight.json"
  after_job="$attempt/job-after.json"
  after_executions="$attempt/executions-after.json"
  after_schedulers="$attempt/schedulers-after.json"
  parked_check="$attempt/parked-check.json"

  capture_job "$before_job"
  capture_executions "$before_executions"
  capture_all_region_schedulers "$before_schedulers"
  validate_reuse_files "$before_job" "$before_executions" \
    "$before_schedulers" "$preflight"
  mapfile -t contract < <(config_args)
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" validate-build "${contract[@]}" \
    --build-metadata-file "$CORPUS_REALIZED_BUILD_METADATA_FILE" \
    >"$attempt/build-validated.json"
  build_rollback_export "$before_job" "$rollback_export"
  jq -e --arg project "$PROJECT" --arg job "$CORPUS_REALIZED_JOB" \
    --arg image "$CORPUS_REALIZED_IMAGE" \
    --arg build "$CORPUS_REALIZED_BUILD_ID" \
    --arg code "$CORPUS_REALIZED_CODE_SHA" \
    --arg service_account "$CORPUS_REALIZED_SERVICE_ACCOUNT" '
    {
      apiVersion: "run.googleapis.com/v1", kind: "Job",
      metadata: {
        name: $job, namespace: $project,
        resourceVersion: .metadata.resourceVersion,
        labels: {}, annotations: {}
      },
      spec: {template: {
        metadata: {
          annotations: {
            "run.googleapis.com/client-name": "corpus-realized-governed-rest",
            "run.googleapis.com/client-version": "1.0.0",
            "run.googleapis.com/execution-environment": "gen2"
          },
          labels: {"client.knative.dev/nonce": $build}
        },
        spec: {taskCount: 1, parallelism: 1, template: {spec: {
          containers: [{
            image: $image,
            command: ["python"],
            args: ["scripts/run_corpus_realized_cloud_transport.py", "parked"],
            env: [
              {name: "CORPUS_REALIZED_TRANSPORT_ENABLED", value: "1"},
              {name: "CORPUS_REALIZED_OUTCOMES_ENABLED", value: "1"},
              {name: "CORPUS_REALIZED_IMAGE", value: $image},
              {name: "CORPUS_REALIZED_BUILD_ID", value: $build},
              {name: "CODE_SHA", value: $code}
            ],
            resources: {limits: {cpu: "4", memory: "16Gi"}}
          }],
          maxRetries: 0, timeoutSeconds: "86400s",
          serviceAccountName: $service_account
        }}}
      }}}
    }
  ' "$before_job" >"$request"

  CORPUS_REALIZED_ROLLBACK_ARMED=1
  configure_exit() {
    local status=$?
    trap - EXIT
    if [[ "${CORPUS_REALIZED_ROLLBACK_ARMED:-0}" == "1" ]]; then
      if ! rollback_job "$before_job" "$rollback_export" "$attempt"; then
        printf '%s\n' "exact rollback failed; manual recovery is required" >&2
        status=1
      fi
    fi
    exit "$status"
  }
  trap configure_exit EXIT
  put_existing_job "$request" "$response"
  capture_reconciled_job "$after_job"
  capture_executions "$after_executions"
  capture_all_region_schedulers "$after_schedulers"
  validate_parked_file "$after_job" "$parked_check"
  validate_reuse_files "$after_job" "$after_executions" \
    "$after_schedulers" "$attempt/postconfigure-preflight.json"
  jq -e -s '
    (.[0] | map(.metadata.name) | sort) ==
    (.[1] | map(.metadata.name) | sort)
  ' "$before_executions" "$after_executions" >/dev/null || \
    die "configure changed the execution census"
  CORPUS_REALIZED_ROLLBACK_ARMED=0
  trap - EXIT
  printf '%s\n' "CORPUS_REALIZED_JOB_PARKED ${attempt}"
}

launch_mode() {
  require_execute "${1:-}"
  local attempt job executions schedulers acquired_at created_at query_at
  local confirm_at confirm_query_at args_json joined_args request_status
  attempt="$(new_attempt_directory launch)"
  job="$attempt/job.json"
  executions="$attempt/executions-before.json"
  schedulers="$attempt/schedulers-before.json"
  capture_reconciled_job "$job"
  capture_executions "$executions"
  capture_all_region_schedulers "$schedulers"
  validate_parked_file "$job" "$attempt/parked-check.json"
  mapfile -t contract < <(config_args)

  acquired_at="$(timestamp_for lease-acquired)"
  CORPUS_REALIZED_LAUNCH_LEASE_PENDING=1
  CORPUS_REALIZED_LAUNCH_ABANDON_REASON=launch-preflight-failed
  launch_exit() {
    local status=$?
    trap - EXIT
    if [[ "${CORPUS_REALIZED_LAUNCH_LEASE_PENDING:-0}" == "1" ]]; then
      # Recover a possibly ambiguous lease-receipt publication before the
      # generation-matched abandonment. This is control-plane recovery, never
      # a second execution or historical query.
      "$PYTHON_BIN" "$TRANSPORT_SCRIPT" acquire-lease "${contract[@]}" \
        --acquired-at-utc "$acquired_at" --execute \
        >"$attempt/lease-acquire-recovery.json" 2>&1 || true
      if ! abandon_mode --execute "$CORPUS_REALIZED_LAUNCH_ABANDON_REASON"; then
        printf '%s\n' "lease abandonment could not be proven; manual recovery is required" >&2
        status=1
      fi
    fi
    exit "$status"
  }
  trap launch_exit EXIT
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" acquire-lease "${contract[@]}" \
    --acquired-at-utc "$acquired_at" --execute >"$attempt/lease-acquired.json"
  created_at="$(timestamp_for launch-intent)"
  query_at="$(timestamp_for launch-query-unused)"
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" prepare-launch "${contract[@]}" \
    --job-file "$job" --executions-file "$executions" \
    --schedulers-file "$schedulers" --all-regions-complete \
    --build-metadata-file "$CORPUS_REALIZED_BUILD_METADATA_FILE" \
    --created-at-utc "$created_at" --query-observed-at-utc "$query_at" \
    --execute >"$attempt/launch-consumed.json"
  confirm_at="$(timestamp_for pre-execution-confirmation)"
  confirm_query_at="$(timestamp_for pre-execution-query-unused)"
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" confirm-query-unused "${contract[@]}" \
    --created-at-utc "$confirm_at" \
    --query-observed-at-utc "$confirm_query_at" --execute \
    >"$attempt/query-confirmed.json"

  args_json="$attempt/worker-args.json"
  gcloud storage cat \
"gs://${OUTPUT_BUCKET}/${OUTPUT_NAMESPACE}/${CORPUS_REALIZED_RUN_ID}/governance/launch-intent.json" \
    | jq -e '.worker_args' >"$args_json"
  joined_args="$(jq -er 'if all(.[]; contains(",") | not) then join(",") else error("comma") end' "$args_json")"

  set +e
  gcloud run jobs execute "$CORPUS_REALIZED_JOB" \
    --project "$PROJECT" --region "$REGION" --async \
    --tasks 1 --task-timeout 86400s --args "$joined_args" \
    --format=json >"$attempt/execute-response.json" 2>"$attempt/execute-error.txt"
  request_status=$?
  set -e
  printf '%s\n' "$request_status" >"$attempt/execute-status.txt"

  # A nonzero/empty execute response is not permission to relaunch.  Recover
  # only by the execution census, which the bind action also supports later.
  local ordinal
  for ordinal in $(seq 1 30); do
    capture_executions "$attempt/executions-after.poll.json"
    if [[ "$(jq -s '
      (.[1] | map(.metadata.name) | unique) -
      (.[0] | map(.metadata.name) | unique) | length
    ' "$executions" "$attempt/executions-after.poll.json")" == "1" ]]; then
      mv "$attempt/executions-after.poll.json" "$attempt/executions-after.json"
      if ! (bind_mode --execute "$attempt/executions-after.json" "$attempt"); then
        CORPUS_REALIZED_LAUNCH_ABANDON_REASON=execution-binding-rejected
        die "execution binding was rejected; never relaunch"
      fi
      CORPUS_REALIZED_LAUNCH_LEASE_PENDING=0
      trap - EXIT
      printf '%s\n' "CORPUS_REALIZED_LAUNCH_BOUND ${attempt}"
      return 0
    fi
    sleep 2
  done
  mv "$attempt/executions-after.poll.json" "$attempt/executions-after.json"
  CORPUS_REALIZED_LAUNCH_ABANDON_REASON=launch-binding-ambiguous
  die "launch outcome remained ambiguous; never relaunch"
}

recover_execution_id() {
  local executions="$1" intent_file="$2"
  gcloud storage cat \
"gs://${OUTPUT_BUCKET}/${OUTPUT_NAMESPACE}/${CORPUS_REALIZED_RUN_ID}/governance/launch-intent.json" \
    >"$intent_file"
  jq -er -s '
    (.[1] | map(.metadata.name | split("/")[-1]) | unique) -
    (.[0].execution_names_before | unique) as $new |
    if ($new | length) == 1 then $new[0] else error("ambiguous") end
  ' "$intent_file" "$executions"
}

bind_mode() {
  require_execute "${1:-}"
  local supplied_executions="${2:-}" parent_attempt="${3:-}"
  local attempt executions job schedulers execution_id execution_file
  if [[ -n "$parent_attempt" ]]; then
    attempt="$parent_attempt/bind"
    mkdir "$attempt"
  else
    attempt="$(new_attempt_directory bind)"
  fi
  executions="${supplied_executions:-$attempt/executions.json}"
  if [[ -z "$supplied_executions" ]]; then
    capture_executions "$executions"
  fi
  job="$attempt/job.json"
  schedulers="$attempt/schedulers.json"
  capture_reconciled_job "$job"
  capture_all_region_schedulers "$schedulers"
  execution_id="$(recover_execution_id "$executions" "$attempt/launch-intent.json")" || \
    die "execution-name recovery is ambiguous; never relaunch"
  execution_file="$attempt/execution.json"
  capture_execution "$execution_id" "$execution_file"
  mapfile -t contract < <(config_args)
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" bind-execution "${contract[@]}" \
    --job-file "$job" --executions-file "$executions" \
    --schedulers-file "$schedulers" --all-regions-complete \
    --execution-file "$execution_file" \
    --created-at-utc "$(timestamp_for execution-binding)" --execute \
    >"$attempt/execution-bound.json"
  printf '%s\n' "$execution_id" >"$CORPUS_REALIZED_RUN_DIR/execution-id.txt"
}

finish_mode() {
  require_execute "${1:-}"
  local attempt execution_id execution job executions schedulers state
  [[ -f "$CORPUS_REALIZED_RUN_DIR/execution-id.txt" && \
     ! -L "$CORPUS_REALIZED_RUN_DIR/execution-id.txt" ]] || \
    die "bound execution id is absent; run bind first"
  execution_id="$(tr -d '\n' <"$CORPUS_REALIZED_RUN_DIR/execution-id.txt")"
  [[ "$execution_id" =~ ^[a-z0-9][a-z0-9-]{2,62}-[a-z0-9]{5}$ ]] || \
    die "bound execution id differs"
  attempt="$(new_attempt_directory finish)"
  execution="$attempt/execution.json"
  job="$attempt/job.json"
  executions="$attempt/executions.json"
  schedulers="$attempt/schedulers.json"
  capture_execution "$execution_id" "$execution"
  state="$(jq -r '[.status.conditions[]? | select(.type == "Completed") | .status] | if length == 1 then .[0] else "Unknown" end' "$execution")"
  if [[ "$state" == "Unknown" ]]; then
    die "execution is still active; lease remains fail-closed"
  fi
  if [[ "$state" != "True" ]]; then
    abandon_mode --execute terminal-execution-failed
    die "execution failed; lease was archived and abandoned"
  fi
  capture_reconciled_job "$job"
  capture_executions "$executions"
  capture_all_region_schedulers "$schedulers"
  mapfile -t contract < <(config_args)
  local finish_status=0 terminal_uri
  set +e
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" finish-execution "${contract[@]}" \
    --job-file "$job" --executions-file "$executions" \
    --schedulers-file "$schedulers" --all-regions-complete \
    --execution-file "$execution" \
    --created-at-utc "$(timestamp_for terminal-acceptance)" --execute \
    >"$attempt/terminal-accepted.json" 2>"$attempt/terminal-error.txt"
  finish_status=$?
  set -e
  terminal_uri="gs://${OUTPUT_BUCKET}/${OUTPUT_NAMESPACE}/${CORPUS_REALIZED_RUN_ID}/governance/terminal-acceptance.json"
  if (( finish_status != 0 )); then
    if ! gcloud storage cat "$terminal_uri" >"$attempt/terminal-recovery.json" \
      2>"$attempt/terminal-recovery-error.txt"; then
      abandon_mode --execute terminal-validation-rejected
      die "terminal validation was rejected; lease was abandoned; never relaunch"
    fi
  fi
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" release-lease "${contract[@]}" \
    --created-at-utc "$(timestamp_for lease-release)" --execute \
    >"$attempt/lease-released.json"
  printf '%s\n' "CORPUS_REALIZED_TERMINAL_CLOSED ${execution_id} ${attempt}"
}

abandon_mode() {
  require_execute "${1:-}"
  local reason="${2:-}"
  [[ "$reason" =~ ^[a-z0-9][a-z0-9-]{2,60}$ ]] || \
    die "abandon reason must be a short slug"
  local attempt
  attempt="$(new_attempt_directory abandon)"
  mapfile -t contract < <(config_args)
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" abandon-lease "${contract[@]}" \
    --reason "$reason" --created-at-utc "$(timestamp_for lease-abandonment)" \
    --execute >"$attempt/lease-abandoned.json"
  printf '%s\n' "CORPUS_REALIZED_FAILED_CLOSED ${reason} ${attempt}"
}

main() {
  require_tools
  prepare_run_dir
  require_contract
  case "${1:-}" in
    configure) configure_mode "${2:-}" ;;
    launch) launch_mode "${2:-}" ;;
    bind) bind_mode "${2:-}" ;;
    finish) finish_mode "${2:-}" ;;
    abandon) abandon_mode "${2:-}" "${3:-}" ;;
    *) die "usage: $0 {configure|launch|bind|finish|abandon} --execute [reason]" ;;
  esac
}

main "$@"
