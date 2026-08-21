#!/usr/bin/env bash
# Default-off operator wrapper for the frozen corpus-parametric transport.
#
# Every mutating mode requires both the literal --execute token and
# CORPUS_PARAMETRIC_RESEARCH_ENABLED=1.  Launch, census recovery, one-shot
# watching, and terminal publication are separate invocations.  A consumed
# launch ledger is never retried automatically, including after an ambiguous
# gcloud response.

set -euo pipefail
set -o noclobber

PROJECT="nfl-predictions-503414"
REGION="us-central1"
PYTHON_BIN="${CORPUS_PARAMETRIC_PYTHON:-.venv/bin/python}"
TRANSPORT_SCRIPT="scripts/run_corpus_parametric_transport.py"

die() {
  printf '%s\n' "corpus parametric operator refused: $*" >&2
  exit 2
}

require_variable() {
  local name="$1"
  [[ -n "${!name:-}" ]] || die "${name} is required"
}

require_execute_gate() {
  [[ "${1:-}" == "--execute" ]] || die "literal --execute is required"
  [[ "${CORPUS_PARAMETRIC_RESEARCH_ENABLED:-}" == "1" ]] || \
    die "CORPUS_PARAMETRIC_RESEARCH_ENABLED=1 is required"
}

require_tools() {
  command -v gcloud >/dev/null || die "gcloud is required"
  command -v jq >/dev/null || die "jq is required"
  [[ -x "$PYTHON_BIN" ]] || die "Python environment is absent: $PYTHON_BIN"
  [[ -f "$TRANSPORT_SCRIPT" ]] || die "transport script is absent"
}

prepare_run_directory() {
  require_variable CORPUS_PARAMETRIC_RUN_DIR
  [[ "$CORPUS_PARAMETRIC_RUN_DIR" == /* ]] || die "run directory must be absolute"
  [[ ! -L "$CORPUS_PARAMETRIC_RUN_DIR" ]] || die "run directory cannot be a symlink"
  mkdir -p "$CORPUS_PARAMETRIC_RUN_DIR"
  CORPUS_PARAMETRIC_RUN_DIR="$(realpath "$CORPUS_PARAMETRIC_RUN_DIR")"
}

timestamp_for() {
  local key="$1"
  [[ "$key" =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "timestamp key is unsafe"
  local directory="$CORPUS_PARAMETRIC_RUN_DIR/timestamps"
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

contract_identity_args() {
  require_variable CORPUS_PARAMETRIC_CONTRACT_URI
  require_variable CORPUS_PARAMETRIC_CONTRACT_GENERATION
  require_variable CORPUS_PARAMETRIC_CONTRACT_SHA256
  require_variable CORPUS_PARAMETRIC_CONTRACT_BYTES
  printf '%s\n' \
    --contract-uri "$CORPUS_PARAMETRIC_CONTRACT_URI" \
    --contract-generation "$CORPUS_PARAMETRIC_CONTRACT_GENERATION" \
    --contract-sha256 "$CORPUS_PARAMETRIC_CONTRACT_SHA256" \
    --contract-bytes "$CORPUS_PARAMETRIC_CONTRACT_BYTES"
}

capture_job() {
  local output="$1"
  gcloud run jobs describe "$CORPUS_PARAMETRIC_JOB" \
    --project "$PROJECT" --region "$REGION" --format=json >"$output"
}

capture_executions() {
  local output="$1"
  gcloud run jobs executions list --job "$CORPUS_PARAMETRIC_JOB" \
    --project "$PROJECT" --region "$REGION" --format=json >"$output"
}

capture_all_region_schedulers() {
  local output="$1"
  [[ ! -e "$output" ]] || die "scheduler capture already exists: $output"
  local stem
  stem="$(basename "$output" .json)"
  local parent
  parent="$(dirname "$output")"
  local locations_file="$parent/${stem}-locations.json"
  local fragments="$parent/${stem}-fragments"
  [[ ! -e "$locations_file" && ! -e "$fragments" ]] || \
    die "scheduler census namespace already exists"
  mkdir -p "$fragments"
  gcloud scheduler locations list --project "$PROJECT" --format=json >"$locations_file"
  local location
  while IFS= read -r location; do
    [[ -n "$location" ]] || continue
    gcloud scheduler jobs list --project "$PROJECT" --location "$location" \
      --format=json >"$fragments/${location}.json"
  done < <(jq -r '.[].locationId' "$locations_file" | LC_ALL=C sort)
  jq -s 'add // []' "$fragments"/*.json >"$output"
}

phase_file() {
  local phase="$1"
  local suffix="$2"
  printf '%s/tasks/%03d-%s-%s.json' \
    "$CORPUS_PARAMETRIC_RUN_DIR" "$CORPUS_PARAMETRIC_TASK_INDEX" "$phase" "$suffix"
}

new_phase_attempt_directory() {
  local phase="$1"
  local action="$2"
  local base
  base="$(printf '%s/tasks/%03d-%s-%s' \
    "$CORPUS_PARAMETRIC_RUN_DIR" "$CORPUS_PARAMETRIC_TASK_INDEX" "$phase" "$action")"
  local ordinal
  for ordinal in $(seq 1 999); do
    local candidate
    candidate="$(printf '%s-attempt-%03d' "$base" "$ordinal")"
    if mkdir "$candidate" 2>/dev/null; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  die "phase attempt namespace is exhausted"
}

configure_mode() {
  require_variable CORPUS_PARAMETRIC_JOB
  require_variable CORPUS_PARAMETRIC_IMAGE
  require_variable CORPUS_PARAMETRIC_BUILD_ID
  require_variable CORPUS_PARAMETRIC_CODE_SHA
  require_variable CORPUS_PARAMETRIC_SERVICE_ACCOUNT
  require_variable CORPUS_PARAMETRIC_EXPECTED_JOB_UID
  require_variable CORPUS_PARAMETRIC_RUNTIME_IAM_FILE
  require_variable CORPUS_PARAMETRIC_BUILD_METADATA_FILE
  for stem in FOUNDATION_PUBLICATION MANIFEST EVIDENCE_CONTRACT RETRIEVAL_PREREQUISITE; do
    require_variable "CORPUS_PARAMETRIC_${stem}_URI"
    require_variable "CORPUS_PARAMETRIC_${stem}_GENERATION"
    require_variable "CORPUS_PARAMETRIC_${stem}_SHA256"
    require_variable "CORPUS_PARAMETRIC_${stem}_BYTES"
  done
  local before_json="$CORPUS_PARAMETRIC_RUN_DIR/job-before.json"
  local before_yaml="$CORPUS_PARAMETRIC_RUN_DIR/job-before.yaml"
  local before_executions="$CORPUS_PARAMETRIC_RUN_DIR/executions-before.json"
  local before_schedulers="$CORPUS_PARAMETRIC_RUN_DIR/schedulers-before.json"
  local preflight_file="$CORPUS_PARAMETRIC_RUN_DIR/preflight-configure.json"
  local build_validated_file="$CORPUS_PARAMETRIC_RUN_DIR/build-validated.json"
  local job_after="$CORPUS_PARAMETRIC_RUN_DIR/job-after.json"
  local executions_after="$CORPUS_PARAMETRIC_RUN_DIR/executions-after.json"
  local schedulers_after="$CORPUS_PARAMETRIC_RUN_DIR/schedulers-after.json"
  local configured_file="$CORPUS_PARAMETRIC_RUN_DIR/configured.json"
  local rollback_restored="$CORPUS_PARAMETRIC_RUN_DIR/job-rollback-restored.json"
  local retained_path
  for retained_path in \
    "$before_json" "$before_yaml" "$before_executions" "$before_schedulers" \
    "$CORPUS_PARAMETRIC_BUILD_METADATA_FILE" "$build_validated_file" \
    "$preflight_file" "$job_after" "$executions_after" \
    "$schedulers_after" "$configured_file" "$rollback_restored"; do
    [[ ! -e "$retained_path" && ! -L "$retained_path" ]] || \
      die "configure evidence path already exists: $retained_path"
  done
  capture_job "$before_json"
  gcloud run jobs describe "$CORPUS_PARAMETRIC_JOB" \
    --project "$PROJECT" --region "$REGION" --format=export >"$before_yaml"
  capture_executions "$before_executions"
  capture_all_region_schedulers "$before_schedulers"
  jq -e 'all(.[]; ([.status.conditions[]? | select(.type == "Completed")][0].status // "Unknown") != "Unknown")' \
    "$before_executions" >/dev/null || die "reused job has an active execution"
  jq -e --arg needle "/jobs/${CORPUS_PARAMETRIC_JOB}:run" \
    'all(.[]; ((.httpTarget.uri // "") | contains($needle) | not))' \
    "$before_schedulers" >/dev/null || die "a scheduler targets the reused job"
  gcloud builds describe "$CORPUS_PARAMETRIC_BUILD_ID" \
    --project "$PROJECT" --format=json >"$CORPUS_PARAMETRIC_BUILD_METADATA_FILE"
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" validate-build \
    --build-metadata-file "$CORPUS_PARAMETRIC_BUILD_METADATA_FILE" \
    --build-id "$CORPUS_PARAMETRIC_BUILD_ID" \
    --code-sha "$CORPUS_PARAMETRIC_CODE_SHA" \
    --image "$CORPUS_PARAMETRIC_IMAGE" \
    >"$build_validated_file"

  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" preflight-configure \
    --foundation-publication-uri "$CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_URI" \
    --foundation-publication-generation "$CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_GENERATION" \
    --foundation-publication-sha256 "$CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_SHA256" \
    --foundation-publication-bytes "$CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_BYTES" \
    --manifest-uri "$CORPUS_PARAMETRIC_MANIFEST_URI" \
    --manifest-generation "$CORPUS_PARAMETRIC_MANIFEST_GENERATION" \
    --manifest-sha256 "$CORPUS_PARAMETRIC_MANIFEST_SHA256" \
    --manifest-bytes "$CORPUS_PARAMETRIC_MANIFEST_BYTES" \
    --evidence-contract-uri "$CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_URI" \
    --evidence-contract-generation "$CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_GENERATION" \
    --evidence-contract-sha256 "$CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_SHA256" \
    --evidence-contract-bytes "$CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_BYTES" \
    --retrieval-prerequisite-uri "$CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_URI" \
    --retrieval-prerequisite-generation "$CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_GENERATION" \
    --retrieval-prerequisite-sha256 "$CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_SHA256" \
    --retrieval-prerequisite-bytes "$CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_BYTES" \
    --runtime-iam-file "$CORPUS_PARAMETRIC_RUNTIME_IAM_FILE" \
    --build-metadata-file "$CORPUS_PARAMETRIC_BUILD_METADATA_FILE" \
    --job-file "$before_json" --executions-file "$before_executions" \
    --schedulers-file "$before_schedulers" --all-regions-complete \
    --build-id "$CORPUS_PARAMETRIC_BUILD_ID" \
    --code-sha "$CORPUS_PARAMETRIC_CODE_SHA" \
    --image "$CORPUS_PARAMETRIC_IMAGE" \
    --service-account "$CORPUS_PARAMETRIC_SERVICE_ACCOUNT" \
    --expected-job-name "$CORPUS_PARAMETRIC_JOB" \
    --expected-job-uid "$CORPUS_PARAMETRIC_EXPECTED_JOB_UID" \
    --execute >"$preflight_file"

  local configured=0
  rollback_before_acceptance() {
    local status=$?
    trap - EXIT
    if [[ "$configured" -eq 0 ]]; then
      if ! gcloud run jobs replace "$before_yaml" --project "$PROJECT" \
        --region "$REGION" --quiet >/dev/null \
        || ! capture_job "$rollback_restored" \
        || ! jq -e -s '
          def stable_metadata:
            {
              annotations: (
                (.metadata.annotations // {}) |
                del(
                  .["run.googleapis.com/client-name"],
                  .["run.googleapis.com/client-version"],
                  .["run.googleapis.com/lastModifier"],
                  .["run.googleapis.com/operation-id"]
                )
              ),
              labels: (
                (.metadata.labels // {}) |
                del(.["run.googleapis.com/lastUpdatedTime"])
              )
            };
          .[0].metadata.name == .[1].metadata.name and
          .[0].metadata.uid == .[1].metadata.uid and
          (.[0] | stable_metadata) == (.[1] | stable_metadata) and
          .[0].spec == .[1].spec
        ' "$before_json" "$rollback_restored" >/dev/null; then
        printf '%s\n' \
          "automatic exact-job rollback failed; manual recovery required" >&2
        status=97
      fi
    fi
    exit "$status"
  }
  trap rollback_before_acceptance EXIT
  gcloud run jobs update "$CORPUS_PARAMETRIC_JOB" \
    --project "$PROJECT" --region "$REGION" \
    --image "$CORPUS_PARAMETRIC_IMAGE" \
    --command python \
    --args "$TRANSPORT_SCRIPT,parked" \
    --set-env-vars "CORPUS_PARAMETRIC_RESEARCH_ENABLED=1,CORPUS_PARAMETRIC_IMAGE=${CORPUS_PARAMETRIC_IMAGE},CORPUS_PARAMETRIC_BUILD_ID=${CORPUS_PARAMETRIC_BUILD_ID},CODE_SHA=${CORPUS_PARAMETRIC_CODE_SHA}" \
    --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 86400s \
    --cpu 8 --memory 32Gi --service-account "$CORPUS_PARAMETRIC_SERVICE_ACCOUNT" \
    --clear-secrets --clear-volumes --clear-volume-mounts \
    --clear-vpc-connector --clear-cloudsql-instances --clear-network \
    --clear-network-tags --clear-labels \
    --startup-probe="" --workdir="" \
    --quiet >/dev/null
  capture_job "$job_after"
  capture_executions "$executions_after"
  capture_all_region_schedulers "$schedulers_after"
  local created_at
  created_at="$(timestamp_for configured)"
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" configure \
    --foundation-publication-uri "$CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_URI" \
    --foundation-publication-generation "$CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_GENERATION" \
    --foundation-publication-sha256 "$CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_SHA256" \
    --foundation-publication-bytes "$CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_BYTES" \
    --manifest-uri "$CORPUS_PARAMETRIC_MANIFEST_URI" \
    --manifest-generation "$CORPUS_PARAMETRIC_MANIFEST_GENERATION" \
    --manifest-sha256 "$CORPUS_PARAMETRIC_MANIFEST_SHA256" \
    --manifest-bytes "$CORPUS_PARAMETRIC_MANIFEST_BYTES" \
    --evidence-contract-uri "$CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_URI" \
    --evidence-contract-generation "$CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_GENERATION" \
    --evidence-contract-sha256 "$CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_SHA256" \
    --evidence-contract-bytes "$CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_BYTES" \
    --retrieval-prerequisite-uri "$CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_URI" \
    --retrieval-prerequisite-generation "$CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_GENERATION" \
    --retrieval-prerequisite-sha256 "$CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_SHA256" \
    --retrieval-prerequisite-bytes "$CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_BYTES" \
    --runtime-iam-file "$CORPUS_PARAMETRIC_RUNTIME_IAM_FILE" \
    --build-metadata-file "$CORPUS_PARAMETRIC_BUILD_METADATA_FILE" \
    --job-file "$job_after" --executions-file "$executions_after" \
    --schedulers-file "$schedulers_after" --all-regions-complete \
    --build-id "$CORPUS_PARAMETRIC_BUILD_ID" \
    --code-sha "$CORPUS_PARAMETRIC_CODE_SHA" \
    --image "$CORPUS_PARAMETRIC_IMAGE" \
    --service-account "$CORPUS_PARAMETRIC_SERVICE_ACCOUNT" \
    --expected-job-name "$CORPUS_PARAMETRIC_JOB" \
    --expected-job-uid "$CORPUS_PARAMETRIC_EXPECTED_JOB_UID" \
    --created-at-utc "$created_at" --execute \
    >"$configured_file"
  configured=1
  trap - EXIT
}

launch_mode() {
  local phase="$1"
  require_variable CORPUS_PARAMETRIC_JOB
  require_variable CORPUS_PARAMETRIC_TASK_INDEX
  mkdir -p "$CORPUS_PARAMETRIC_RUN_DIR/tasks"
  local attempt_dir
  attempt_dir="$(new_phase_attempt_directory "$phase" launch)"
  local job_file executions_file schedulers_file ready_file
  job_file="$attempt_dir/job.json"
  executions_file="$attempt_dir/executions.json"
  schedulers_file="$attempt_dir/schedulers.json"
  ready_file="$attempt_dir/launch-ready.json"
  capture_job "$job_file"
  capture_executions "$executions_file"
  capture_all_region_schedulers "$schedulers_file"
  mapfile -t identity_args < <(contract_identity_args)
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" consume-launch \
    "${identity_args[@]}" --task-index "$CORPUS_PARAMETRIC_TASK_INDEX" \
    --phase "$phase" --job-file "$job_file" \
    --executions-file "$executions_file" --schedulers-file "$schedulers_file" \
    --all-regions-complete \
    --created-at-utc "$(timestamp_for "task-${CORPUS_PARAMETRIC_TASK_INDEX}-${phase}-launch")" \
    --execute \
    >"$ready_file"
  jq -e '.launch_permitted == true and .automatic_retry_licensed == false' \
    "$ready_file" >/dev/null || die "launch authority was already consumed; recover only"
  local joined_args
  joined_args="$(jq -r '.worker_args | join(",")' "$ready_file")"
  local response_file
  response_file="$attempt_dir/launch-response.json"
  set +e
  gcloud run jobs execute "$CORPUS_PARAMETRIC_JOB" \
    --project "$PROJECT" --region "$REGION" --args "$joined_args" \
    --async --format=json >"$response_file"
  local status=$?
  set -e
  if [[ "$status" -ne 0 ]]; then
    printf '%s\n' "launch response was ambiguous; run recover-${phase}; never relaunch" >&2
    return "$status"
  fi
  printf '%s\n' "launch consumed; run recover-${phase} as a separate action"
}

recover_mode() {
  local phase="$1"
  require_variable CORPUS_PARAMETRIC_JOB
  require_variable CORPUS_PARAMETRIC_TASK_INDEX
  mkdir -p "$CORPUS_PARAMETRIC_RUN_DIR/tasks"
  local attempt_dir
  attempt_dir="$(new_phase_attempt_directory "$phase" recover)"
  mapfile -t identity_args < <(contract_identity_args)
  local executions_file candidate_file execution_id execution_file job_file schedulers_file bound_file
  executions_file="$attempt_dir/executions.json"
  candidate_file="$attempt_dir/recovery-candidate.json"
  execution_file="$attempt_dir/execution.json"
  job_file="$attempt_dir/job.json"
  schedulers_file="$attempt_dir/schedulers.json"
  bound_file="$(phase_file "$phase" bound)"
  capture_executions "$executions_file"
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" recover-name \
    "${identity_args[@]}" --task-index "$CORPUS_PARAMETRIC_TASK_INDEX" \
    --phase "$phase" --executions-file "$executions_file" --execute \
    >"$candidate_file"
  execution_id="$(jq -er '.execution_id' "$candidate_file")"
  gcloud run jobs executions describe "$execution_id" \
    --project "$PROJECT" --region "$REGION" --format=json >"$execution_file"
  capture_job "$job_file"
  capture_all_region_schedulers "$schedulers_file"
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" bind-execution \
    "${identity_args[@]}" --task-index "$CORPUS_PARAMETRIC_TASK_INDEX" \
    --phase "$phase" --execution-metadata-file "$execution_file" \
    --job-file "$job_file" --executions-file "$executions_file" \
    --schedulers-file "$schedulers_file" --all-regions-complete \
    --created-at-utc "$(timestamp_for "task-${CORPUS_PARAMETRIC_TASK_INDEX}-${phase}-bound")" \
    --execute >"$bound_file"
  printf '%s\n' "execution bound; run watch-${phase} as a separate action"
}

watch_mode() {
  local phase="$1"
  require_variable CORPUS_PARAMETRIC_JOB
  require_variable CORPUS_PARAMETRIC_TASK_INDEX
  mapfile -t identity_args < <(contract_identity_args)
  local attempt_dir
  attempt_dir="$(new_phase_attempt_directory "$phase" watch)"
  local bound_file execution_id terminal_file completed job_file executions_file schedulers_file
  bound_file="$(phase_file "$phase" bound)"
  [[ -f "$bound_file" ]] || die "bound execution receipt is absent; recover first"
  execution_id="$(jq -er '.execution_id' "$bound_file")"
  terminal_file="$attempt_dir/execution.json"
  gcloud run jobs executions describe "$execution_id" \
    --project "$PROJECT" --region "$REGION" --format=json >"$terminal_file"
  completed="$(jq -r '[.status.conditions[]? | select(.type == "Completed")][0].status // "Unknown"' "$terminal_file")"
  if [[ "$completed" == "Unknown" ]]; then
    printf '%s\n' "execution is still nonterminal; invoke this watch mode again later"
    return 3
  fi
  [[ "$completed" == "True" ]] || die "execution failed/cancelled; no retry is licensed"
  job_file="$attempt_dir/job.json"
  executions_file="$attempt_dir/executions.json"
  schedulers_file="$attempt_dir/schedulers.json"
  capture_job "$job_file"
  capture_executions "$executions_file"
  capture_all_region_schedulers "$schedulers_file"
  if [[ "$phase" == "producer" ]]; then
    "$PYTHON_BIN" "$TRANSPORT_SCRIPT" close-producer \
      "${identity_args[@]}" --task-index "$CORPUS_PARAMETRIC_TASK_INDEX" \
      --execution-metadata-file "$terminal_file" \
      --job-file "$job_file" --executions-file "$executions_file" \
      --schedulers-file "$schedulers_file" --all-regions-complete \
      --created-at-utc "$(timestamp_for "task-${CORPUS_PARAMETRIC_TASK_INDEX}-producer-closed")" \
      --execute \
      >"$(phase_file "$phase" closed)"
    printf '%s\n' "producer closed; verifier launch remains a separate action"
  else
    "$PYTHON_BIN" "$TRANSPORT_SCRIPT" accept-task \
      "${identity_args[@]}" --task-index "$CORPUS_PARAMETRIC_TASK_INDEX" \
      --execution-metadata-file "$terminal_file" \
      --job-file "$job_file" --executions-file "$executions_file" \
      --schedulers-file "$schedulers_file" --all-regions-complete \
      --created-at-utc "$(timestamp_for "task-${CORPUS_PARAMETRIC_TASK_INDEX}-verifier-accepted")" \
      --execute \
      >"$(phase_file "$phase" accepted)"
    printf '%s\n' "task independently verified and accepted"
  fi
}

finish_batch_mode() {
  mapfile -t identity_args < <(contract_identity_args)
  "$PYTHON_BIN" "$TRANSPORT_SCRIPT" finish-batch \
    "${identity_args[@]}" --created-at-utc "$(timestamp_for batch-accepted)" \
    --execute \
    >"$CORPUS_PARAMETRIC_RUN_DIR/batch-accepted.json"
}

main() {
  require_execute_gate "${1:-}"
  local mode="${2:-}"
  [[ -n "$mode" ]] || die "mode is required"
  require_tools
  prepare_run_directory
  case "$mode" in
    configure) configure_mode ;;
    launch-producer) launch_mode producer ;;
    recover-producer) recover_mode producer ;;
    watch-producer) watch_mode producer ;;
    launch-verifier) launch_mode verifier ;;
    recover-verifier) recover_mode verifier ;;
    watch-verifier) watch_mode verifier ;;
    finish-batch) finish_batch_mode ;;
    *) die "unknown mode: $mode" ;;
  esac
}

main "$@"
