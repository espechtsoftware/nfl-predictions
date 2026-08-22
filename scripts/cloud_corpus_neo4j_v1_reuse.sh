#!/usr/bin/env bash
# Reuse-only operator for the dedicated corpus Neo4j projection.
#
# Configure is a resourceVersion-bound update of one externally frozen job.
# Every graph operation consumes a stable create-once GCS launch intent before
# Cloud Run execute. An ambiguous response is recover-only: never relaunch.

set -euo pipefail

PROJECT="${CORPUS_NEO4J_PROJECT:-nfl-predictions-503414}"
REGION="${CORPUS_NEO4J_REGION:-us-central1}"
PYTHON_BIN="${CORPUS_NEO4J_PYTHON:-.venv/bin/python}"
TRANSPORT_SCRIPT="scripts/run_corpus_neo4j_transport.py"

die() {
  printf '%s\n' "corpus Neo4j operator refused: $*" >&2
  exit 2
}

require_variable() {
  local name="$1"
  [[ -n "${!name:-}" ]] || die "${name} is required"
}

require_execute() {
  [[ "${1:-}" == "--execute" ]] || die "literal --execute is required"
  [[ "${CORPUS_NEO4J_TRANSPORT_ENABLED:-}" == "1" ]] || \
    die "CORPUS_NEO4J_TRANSPORT_ENABLED=1 is required"
}

require_tools() {
  command -v gcloud >/dev/null || die "gcloud is required"
  command -v jq >/dev/null || die "jq is required"
  command -v curl >/dev/null || die "curl is required"
  [[ -x "$PYTHON_BIN" ]] || die "Python environment is absent: $PYTHON_BIN"
  [[ -f "$TRANSPORT_SCRIPT" ]] || die "graph transport script is absent"
}

prepare_run_dir() {
  require_variable CORPUS_NEO4J_RUN_DIR
  [[ "$CORPUS_NEO4J_RUN_DIR" == /* ]] || die "run directory must be absolute"
  [[ ! -L "$CORPUS_NEO4J_RUN_DIR" ]] || die "run directory cannot be a symlink"
  mkdir -p "$CORPUS_NEO4J_RUN_DIR"
  CORPUS_NEO4J_RUN_DIR="$(realpath "$CORPUS_NEO4J_RUN_DIR")"
}

timestamp_for() {
  local key="$1"
  [[ "$key" =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "timestamp key is unsafe"
  local directory="$CORPUS_NEO4J_RUN_DIR/timestamps"
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
  local action="$1"
  local ordinal candidate
  for ordinal in $(seq 1 999); do
    candidate="$(printf '%s/%s-attempt-%03d' \
      "$CORPUS_NEO4J_RUN_DIR" "$action" "$ordinal")"
    if mkdir "$candidate" 2>/dev/null; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  die "attempt namespace exhausted for ${action}"
}

require_frozen_job() {
  require_variable CORPUS_NEO4J_JOB
  require_variable CORPUS_NEO4J_JOB_UID
}

capture_job() {
  local output="$1"
  gcloud run jobs describe "$CORPUS_NEO4J_JOB" \
    --project "$PROJECT" --region "$REGION" --format=json >"$output"
}

capture_reconciled_job() {
  local output="$1"
  local poll="${output}.poll"
  local ordinal
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
  gcloud run jobs executions list --job "$CORPUS_NEO4J_JOB" \
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

manifest_identity_args() {
  for name in URI GENERATION SHA256 BYTES; do
    require_variable "CORPUS_NEO4J_MANIFEST_${name}"
  done
  printf '%s\n' \
    --manifest-uri "$CORPUS_NEO4J_MANIFEST_URI" \
    --manifest-generation "$CORPUS_NEO4J_MANIFEST_GENERATION" \
    --manifest-sha256 "$CORPUS_NEO4J_MANIFEST_SHA256" \
    --manifest-bytes "$CORPUS_NEO4J_MANIFEST_BYTES" \
    --project "$PROJECT"
}

parked_contract_args() {
  for name in IMAGE BUILD_ID CODE_SHA SERVICE_ACCOUNT URI DATABASE \
    PROVIDER_RESOURCE_ID USERNAME_SECRET_VERSION PASSWORD_SECRET_VERSION; do
    require_variable "CORPUS_NEO4J_${name}"
  done
  printf '%s\n' \
    --image "$CORPUS_NEO4J_IMAGE" \
    --build-id "$CORPUS_NEO4J_BUILD_ID" \
    --code-sha "$CORPUS_NEO4J_CODE_SHA" \
    --service-account "$CORPUS_NEO4J_SERVICE_ACCOUNT" \
    --uri "$CORPUS_NEO4J_URI" \
    --database "$CORPUS_NEO4J_DATABASE" \
    --provider-resource-id "$CORPUS_NEO4J_PROVIDER_RESOURCE_ID" \
    --username-secret-version "$CORPUS_NEO4J_USERNAME_SECRET_VERSION" \
    --password-secret-version "$CORPUS_NEO4J_PASSWORD_SECRET_VERSION"
}

operation_args() {
  local command="$1"
  printf '%s\n' --operation "$command"
  if [[ "$command" == "load-parametric-task" || \
        "$command" == "recover-parametric-receipt" ]]; then
    require_variable CORPUS_NEO4J_TASK_INDEX
    printf '%s\n' --task-index "$CORPUS_NEO4J_TASK_INDEX"
  fi
  if [[ "$command" == "query-smoke" && \
        "${CORPUS_NEO4J_REQUIRE_COMPLETE_SUITE:-}" == "1" ]]; then
    printf '%s\n' --require-complete-suite
  fi
}

required_role_for() {
  case "$1" in
    bootstrap-schema) printf '%s\n' bootstrap ;;
    load-task0|load-parametric-task|load-suite|load-strategy-registry)
      printf '%s\n' writer ;;
    recover-task0-receipt|recover-parametric-receipt|\
      recover-strategy-registry-receipt|finish-suite|query-smoke|\
      query-strategy-registry)
      printf '%s\n' reader ;;
    *) die "unsupported graph command: $1" ;;
  esac
}

validate_preflight_files() {
  local job="$1" executions="$2" schedulers="$3" output="$4"
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" validate-reuse-preflight \
    --job-file "$job" --job-name "$CORPUS_NEO4J_JOB" \
    --job-uid "$CORPUS_NEO4J_JOB_UID" \
    --executions-file "$executions" --schedulers-file "$schedulers" \
    --all-regions-complete >"$output"
}

build_rollback_export() {
  local captured="$1" output="$2"
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

put_existing_job() {
  local request="$1" response="$2"
  {
    printf '%s' 'Authorization: Bearer '
    gcloud auth print-access-token
  } | curl --fail-with-body --silent --show-error \
    --request PUT --header @- --header 'Content-Type: application/json' \
    --data-binary "@$request" \
    "https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${CORPUS_NEO4J_JOB}" \
    >"$response"
}

rollback_existing_job() {
  local prior_job="$1" prior_export="$2" directory="$3"
  local current="$directory/rollback-current.json"
  local request="$directory/rollback-request.json"
  local response="$directory/rollback-response.json"
  local restored="$directory/rollback-restored.json"
  capture_job "$current"
  jq -e -s '.[0].metadata.name == .[1].metadata.name and
    .[0].metadata.uid == .[1].metadata.uid' \
    "$prior_job" "$current" >/dev/null || return 1
  if jq -e -s '.[0].spec == .[1].spec' "$prior_job" "$current" >/dev/null; then
    cp --no-clobber "$current" "$restored"
    return 0
  fi
  local current_resource_version
  current_resource_version="$(jq -er '.metadata.resourceVersion' "$current")"
  jq -e --arg resource_version "$current_resource_version" \
    '.metadata.resourceVersion = $resource_version' \
    "$prior_export" >"$request"
  put_existing_job "$request" "$response"
  capture_job "$restored"
  jq -e -s '.[0].metadata.name == .[1].metadata.name and
    .[0].metadata.uid == .[1].metadata.uid and .[0].spec == .[1].spec' \
    "$prior_job" "$restored" >/dev/null
}

configure_mode() {
  local role="$1"
  require_execute "${2:-}"
  require_frozen_job
  [[ "$role" == "bootstrap" || "$role" == "writer" || "$role" == "reader" ]] || \
    die "role must be bootstrap, writer, or reader"
  mapfile -t contract_args < <(parked_contract_args)
  local attempt before_job before_executions before_schedulers preflight build_file
  local rollback_export request response after_job after_executions after_schedulers
  attempt="$(new_attempt_directory "configure-${role}")"
  before_job="$attempt/job-before.json"
  before_executions="$attempt/executions-before.json"
  before_schedulers="$attempt/schedulers-before.json"
  preflight="$attempt/preflight.json"
  build_file="$attempt/build-metadata.json"
  rollback_export="$attempt/rollback-export.json"
  request="$attempt/update-request.json"
  response="$attempt/update-response.json"
  after_job="$attempt/job-after.json"
  after_executions="$attempt/executions-after.json"
  after_schedulers="$attempt/schedulers-after.json"

  capture_job "$before_job"
  capture_executions "$before_executions"
  capture_all_region_schedulers "$before_schedulers"
  validate_preflight_files \
    "$before_job" "$before_executions" "$before_schedulers" "$preflight"
  gcloud builds describe "$CORPUS_NEO4J_BUILD_ID" \
    --project "$PROJECT" --format=json >"$build_file"
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" validate-build \
    --build-metadata-file "$build_file" --build-id "$CORPUS_NEO4J_BUILD_ID" \
    --code-sha "$CORPUS_NEO4J_CODE_SHA" --image "$CORPUS_NEO4J_IMAGE" \
    >"$attempt/build-validated.json"
  build_rollback_export "$before_job" "$rollback_export"

  local username_prefix username_version password_prefix password_version
  username_prefix="${CORPUS_NEO4J_USERNAME_SECRET_VERSION%/versions/*}"
  username_version="${CORPUS_NEO4J_USERNAME_SECRET_VERSION##*/versions/}"
  password_prefix="${CORPUS_NEO4J_PASSWORD_SECRET_VERSION%/versions/*}"
  password_version="${CORPUS_NEO4J_PASSWORD_SECRET_VERSION##*/versions/}"
  jq -e \
    --arg project "$PROJECT" --arg job "$CORPUS_NEO4J_JOB" \
    --arg image "$CORPUS_NEO4J_IMAGE" --arg role "$role" \
    --arg uri "$CORPUS_NEO4J_URI" --arg database "$CORPUS_NEO4J_DATABASE" \
    --arg provider "$CORPUS_NEO4J_PROVIDER_RESOURCE_ID" \
    --arg username_identity "$CORPUS_NEO4J_USERNAME_SECRET_VERSION" \
    --arg password_identity "$CORPUS_NEO4J_PASSWORD_SECRET_VERSION" \
    --arg username_secret "$username_prefix" --arg username_key "$username_version" \
    --arg password_secret "$password_prefix" --arg password_key "$password_version" \
    --arg build "$CORPUS_NEO4J_BUILD_ID" --arg code "$CORPUS_NEO4J_CODE_SHA" \
    --arg service_account "$CORPUS_NEO4J_SERVICE_ACCOUNT" '
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
            "run.googleapis.com/client-name": "corpus-neo4j-governed-rest",
            "run.googleapis.com/client-version": "1.0.0",
            "run.googleapis.com/execution-environment": "gen2"
          },
          labels: {"client.knative.dev/nonce": $build}
        },
        spec: {taskCount: 1, parallelism: 1, template: {spec: {
          containers: [{
            image: $image,
            command: ["python"],
            args: ["scripts/run_corpus_neo4j_transport.py", "parked"],
            env: [
              {name: "CORPUS_NEO4J_TRANSPORT_ENABLED", value: "1"},
              {name: "CORPUS_NEO4J_CONFIGURED_ROLE", value: $role},
              {name: "CORPUS_RETRIEVAL_NEO4J_URI", value: $uri},
              {name: "CORPUS_RETRIEVAL_NEO4J_DATABASE", value: $database},
              {name: "CORPUS_RETRIEVAL_NEO4J_PROVIDER_RESOURCE_ID", value: $provider},
              {name: "CORPUS_RETRIEVAL_NEO4J_USERNAME_SECRET_VERSION", value: $username_identity},
              {name: "CORPUS_RETRIEVAL_NEO4J_PASSWORD_SECRET_VERSION", value: $password_identity},
              {name: "CORPUS_NEO4J_IMAGE", value: $image},
              {name: "CORPUS_NEO4J_BUILD_ID", value: $build},
              {name: "CODE_SHA", value: $code},
              {name: "CORPUS_RETRIEVAL_NEO4J_USERNAME", valueSource: {secretKeyRef: {name: $username_secret, key: $username_key}}},
              {name: "CORPUS_RETRIEVAL_NEO4J_PASSWORD", valueSource: {secretKeyRef: {name: $password_secret, key: $password_key}}}
            ],
            resources: {limits: {cpu: "2000m", memory: "4Gi"}}
          }],
          maxRetries: 0, timeoutSeconds: "86400s",
          serviceAccountName: $service_account
        }}}
      }}}
    }
  ' "$before_job" >"$request"

  CORPUS_NEO4J_ROLLBACK_ARMED=1
  configure_exit() {
    local status=$?
    trap - EXIT
    if [[ "${CORPUS_NEO4J_ROLLBACK_ARMED:-0}" == "1" ]]; then
      if ! rollback_existing_job "$before_job" "$rollback_export" "$attempt"; then
        printf '%s\n' "exact rollback failed; manual recovery is required" >&2
        status=1
      fi
    fi
    exit "$status"
  }
  trap configure_exit EXIT
  put_existing_job "$request" "$response"
  capture_reconciled_job "$after_job"
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" validate-parked-job \
    --job-file "$after_job" --job-name "$CORPUS_NEO4J_JOB" \
    --job-uid "$CORPUS_NEO4J_JOB_UID" --role "$role" \
    "${contract_args[@]}" >"$attempt/parked-validated.json"
  capture_executions "$after_executions"
  capture_all_region_schedulers "$after_schedulers"
  validate_preflight_files \
    "$after_job" "$after_executions" "$after_schedulers" \
    "$attempt/post-configure-preflight.json"
  jq -e -s '
    ([.[0][].metadata.name] | sort) == ([.[1][].metadata.name] | sort)
  ' "$before_executions" "$after_executions" >/dev/null || \
    die "configure changed the execution census"
  CORPUS_NEO4J_ROLLBACK_ARMED=0
  trap - EXIT
  printf '%s\n' "existing frozen job configured once and remains parked"
}

launch_mode() {
  local command="$1"
  require_execute "${2:-}"
  require_frozen_job
  local role attempt job executions schedulers ready response after_job after_exec after_sched
  role="$(required_role_for "$command")"
  mapfile -t identity_args < <(manifest_identity_args)
  mapfile -t contract_args < <(parked_contract_args)
  mapfile -t op_args < <(operation_args "$command")
  attempt="$(new_attempt_directory "launch-${command}")"
  job="$attempt/job-before.json"
  executions="$attempt/executions-before.json"
  schedulers="$attempt/schedulers-before.json"
  ready="$attempt/launch-intent.json"
  response="$attempt/launch-response.json"
  after_job="$attempt/job-after.json"
  after_exec="$attempt/executions-after.json"
  after_sched="$attempt/schedulers-after.json"
  capture_job "$job"
  capture_executions "$executions"
  capture_all_region_schedulers "$schedulers"
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" consume-launch \
    "${identity_args[@]}" "${op_args[@]}" \
    --job-file "$job" --job-name "$CORPUS_NEO4J_JOB" \
    --job-uid "$CORPUS_NEO4J_JOB_UID" --executions-file "$executions" \
    --schedulers-file "$schedulers" --all-regions-complete \
    --role "$role" "${contract_args[@]}" \
    --created-at-utc "$(timestamp_for "launch-${command}")" --execute >"$ready"
  jq -e '.launch_permitted == true and .automatic_retry_licensed == false' \
    "$ready" >/dev/null || die "launch authority is already consumed; recover only"
  local joined_args
  joined_args="$(jq -r '.worker_args | join(",")' "$ready")"
  set +e
  gcloud run jobs execute "$CORPUS_NEO4J_JOB" \
    --project "$PROJECT" --region "$REGION" --args "$joined_args" \
    --async --format=json >"$response"
  local execute_status=$?
  set -e
  capture_job "$after_job"
  capture_executions "$after_exec"
  capture_all_region_schedulers "$after_sched"
  set +e
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" bind-execution \
    "${identity_args[@]}" "${op_args[@]}" \
    --job-file "$after_job" --job-name "$CORPUS_NEO4J_JOB" \
    --job-uid "$CORPUS_NEO4J_JOB_UID" --executions-file "$after_exec" \
    --schedulers-file "$after_sched" --all-regions-complete \
    --created-at-utc "$(timestamp_for "binding-${command}")" --execute \
    >"$attempt/execution-binding.json"
  local bind_status=$?
  set -e
  if [[ "$execute_status" -ne 0 || "$bind_status" -ne 0 ]]; then
    printf '%s\n' \
      "launch is consumed; response/name may be ambiguous. Recover only; never relaunch." >&2
    return 3
  fi
  printf '%s\n' "one execution launched and durably bound; watch it separately"
}

recover_launch_mode() {
  local command="$1"
  require_execute "${2:-}"
  require_frozen_job
  mapfile -t identity_args < <(manifest_identity_args)
  mapfile -t op_args < <(operation_args "$command")
  local attempt job executions schedulers
  attempt="$(new_attempt_directory "recover-${command}")"
  job="$attempt/job.json"
  executions="$attempt/executions.json"
  schedulers="$attempt/schedulers.json"
  capture_job "$job"
  capture_executions "$executions"
  capture_all_region_schedulers "$schedulers"
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" bind-execution \
    "${identity_args[@]}" "${op_args[@]}" \
    --job-file "$job" --job-name "$CORPUS_NEO4J_JOB" \
    --job-uid "$CORPUS_NEO4J_JOB_UID" --executions-file "$executions" \
    --schedulers-file "$schedulers" --all-regions-complete \
    --created-at-utc "$(timestamp_for "binding-${command}")" --execute \
    >"$attempt/execution-binding.json"
  printf '%s\n' "sole execution durably bound; watch it separately"
}

watch_mode() {
  local command="$1"
  require_execute "${2:-}"
  require_frozen_job
  mapfile -t identity_args < <(manifest_identity_args)
  mapfile -t op_args < <(operation_args "$command")
  local attempt job executions schedulers binding execution_name execution state
  attempt="$(new_attempt_directory "watch-${command}")"
  job="$attempt/job.json"
  executions="$attempt/executions.json"
  schedulers="$attempt/schedulers.json"
  binding="$attempt/execution-binding.json"
  execution="$attempt/execution.json"
  capture_job "$job"
  capture_executions "$executions"
  capture_all_region_schedulers "$schedulers"
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" bind-execution \
    "${identity_args[@]}" "${op_args[@]}" \
    --job-file "$job" --job-name "$CORPUS_NEO4J_JOB" \
    --job-uid "$CORPUS_NEO4J_JOB_UID" --executions-file "$executions" \
    --schedulers-file "$schedulers" --all-regions-complete \
    --created-at-utc "$(timestamp_for "binding-${command}")" --execute >"$binding"
  execution_name="$(jq -er '.execution_name' "$binding")"
  gcloud run jobs executions describe "$execution_name" \
    --project "$PROJECT" --region "$REGION" --format=json >"$execution"
  state="$(jq -r '[.status.conditions[]? | select(.type == "Completed")][0].status // "Unknown"' "$execution")"
  if [[ "$state" == "Unknown" ]]; then
    printf '%s\n' "execution remains nonterminal; invoke watch again later"
    return 3
  fi
  [[ "$state" == "True" ]] || die "execution failed; launch remains consumed"
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" finish-execution \
    "${identity_args[@]}" "${op_args[@]}" --execution-file "$execution" \
    --created-at-utc "$(timestamp_for "terminal-${command}")" --execute \
    >"$attempt/execution-terminal.json"
  printf '%s\n' "strict terminal success and exact GCS operation receipts accepted"
}

status_mode() {
  require_frozen_job
  local attempt
  attempt="$(new_attempt_directory status)"
  capture_job "$attempt/job.json"
  capture_executions "$attempt/executions.json"
  capture_all_region_schedulers "$attempt/schedulers.json"
  validate_preflight_files \
    "$attempt/job.json" "$attempt/executions.json" "$attempt/schedulers.json" \
    "$attempt/status.json"
  jq '{job: .job, idle: .idle, unscheduled: .unscheduled}' "$attempt/status.json"
}

main() {
  require_tools
  prepare_run_dir
  case "${1:-}" in
    parked) "$PYTHON_BIN" "$TRANSPORT_SCRIPT" parked ;;
    configure) configure_mode "${2:-}" "${3:-}" ;;
    launch) launch_mode "${2:-}" "${3:-}" ;;
    recover-launch) recover_launch_mode "${2:-}" "${3:-}" ;;
    watch) watch_mode "${2:-}" "${3:-}" ;;
    status) status_mode ;;
    *) die "usage: $0 parked | status | configure ROLE --execute | launch COMMAND --execute | recover-launch COMMAND --execute | watch COMMAND --execute" ;;
  esac
}

main "$@"
