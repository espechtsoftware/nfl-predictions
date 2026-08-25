#!/usr/bin/env bash
# Resumable post-T230 Core v1 catalog -> outcome -> grade operator.
#
# This script never builds, deploys, configures, or creates a Cloud Run job.
# It only exact-checks one already parked image-D job and supplies a different
# `bash -ceu <python CLI ...>` argv override for each execution.  Historical
# outcome lease acquisition and release remain separate, explicit operations.
set -euo pipefail

readonly PROJECT_LAW="nfl-predictions-503414"
readonly REGION_LAW="us-central1"
readonly ENABLED_ENV="CORE_V1_SCORE_CHAIN_ENABLED"
readonly OUTCOME_LEASE_URI="gs://nfl-predictions-503414-raw/research-governance/historical-outcome-active-v1.json"
readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly RUN_ROOT="$ROOT/reports/core-v1-score-chain-runs"
readonly PYTHON_BIN="${CORE_V1_SCORE_CHAIN_PYTHON_BIN:-$ROOT/.venv/bin/python}"

MODE=""
EXECUTE=0
CHAIN_RUN_ID=""
PROJECT="$PROJECT_LAW"
REGION="$REGION_LAW"
JOB=""
SERVICE_ACCOUNT=""
IMAGE=""
CODE_SHA=""
CATALOG_ID=""
CATALOG_OUTPUT_PREFIX=""
MAX_LOGICAL_CATALOG_BYTES=""
OUTCOME_RUN_ID=""
OUTCOME_OUTPUT_PREFIX=""
GRADE_RUN_ID=""
GRADE_OUTPUT_PREFIX=""
MAX_LOGICAL_GRADE_BYTES=""
SOURCE_PANEL_IDENTITY_FILE=""
T230_PANEL_RELEASE_IDENTITY_FILE=""
LEASE_RECEIPT_FILE=""
POLL_SECONDS=15
MAX_WAIT_SECONDS=23000

SOURCE_PANEL_CANON=""
T230_PANEL_RELEASE_CANON=""
LEASE_RECEIPT_CANON=""

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

usage() {
  cat <<'USAGE'
Usage:
  CORE_V1_SCORE_CHAIN_ENABLED=1 scripts/cloud_core_v1_score_chain.sh \
    --execute --mode catalog|outcome|grade|all \
    --chain-run-id ID --project nfl-predictions-503414 \
    --region us-central1 --job REUSED_JOB \
    --service-account EMAIL --image IMAGE@sha256:DIGEST --code-sha SHA \
    --catalog-id ID --catalog-output-prefix gs://.../ \
    --max-logical-catalog-bytes N \
    --outcome-run-id ID --outcome-output-prefix gs://.../ \
    --grade-run-id ID --grade-output-prefix gs://.../ \
    --max-logical-grade-bytes N \
    --source-panel-identity FILE --t230-panel-release-identity FILE \
    [--lease-receipt FILE] [--poll-seconds N] [--max-wait-seconds N]

`outcome` and `all` require --lease-receipt. Acquire that lease explicitly
with scripts/historical_outcome_lease.py before this operator. The operator
exact-reads the known Core completion and materializes the strict local release
evidence, but never acquires, abandons, or deletes the lease. Release remains
explicit after the grade is durably closed.
USAGE
}

require_value() {
  local option="$1" value="${2:-}"
  [[ -n "$value" ]] || die "$option requires a value"
}

parse_args() {
  while (($#)); do
    case "$1" in
      --execute) EXECUTE=1; shift ;;
      --mode) require_value "$1" "${2:-}"; MODE="$2"; shift 2 ;;
      --chain-run-id) require_value "$1" "${2:-}"; CHAIN_RUN_ID="$2"; shift 2 ;;
      --project) require_value "$1" "${2:-}"; PROJECT="$2"; shift 2 ;;
      --region) require_value "$1" "${2:-}"; REGION="$2"; shift 2 ;;
      --job) require_value "$1" "${2:-}"; JOB="$2"; shift 2 ;;
      --service-account) require_value "$1" "${2:-}"; SERVICE_ACCOUNT="$2"; shift 2 ;;
      --image) require_value "$1" "${2:-}"; IMAGE="$2"; shift 2 ;;
      --code-sha) require_value "$1" "${2:-}"; CODE_SHA="$2"; shift 2 ;;
      --catalog-id) require_value "$1" "${2:-}"; CATALOG_ID="$2"; shift 2 ;;
      --catalog-output-prefix) require_value "$1" "${2:-}"; CATALOG_OUTPUT_PREFIX="$2"; shift 2 ;;
      --max-logical-catalog-bytes) require_value "$1" "${2:-}"; MAX_LOGICAL_CATALOG_BYTES="$2"; shift 2 ;;
      --outcome-run-id) require_value "$1" "${2:-}"; OUTCOME_RUN_ID="$2"; shift 2 ;;
      --outcome-output-prefix) require_value "$1" "${2:-}"; OUTCOME_OUTPUT_PREFIX="$2"; shift 2 ;;
      --grade-run-id) require_value "$1" "${2:-}"; GRADE_RUN_ID="$2"; shift 2 ;;
      --grade-output-prefix) require_value "$1" "${2:-}"; GRADE_OUTPUT_PREFIX="$2"; shift 2 ;;
      --max-logical-grade-bytes) require_value "$1" "${2:-}"; MAX_LOGICAL_GRADE_BYTES="$2"; shift 2 ;;
      --source-panel-identity) require_value "$1" "${2:-}"; SOURCE_PANEL_IDENTITY_FILE="$2"; shift 2 ;;
      --t230-panel-release-identity) require_value "$1" "${2:-}"; T230_PANEL_RELEASE_IDENTITY_FILE="$2"; shift 2 ;;
      --lease-receipt) require_value "$1" "${2:-}"; LEASE_RECEIPT_FILE="$2"; shift 2 ;;
      --poll-seconds) require_value "$1" "${2:-}"; POLL_SECONDS="$2"; shift 2 ;;
      --max-wait-seconds) require_value "$1" "${2:-}"; MAX_WAIT_SECONDS="$2"; shift 2 ;;
      --help|-h) usage; exit 0 ;;
      *) die "unknown argument: $1" ;;
    esac
  done
}

require_tools() {
  local tool
  for tool in gcloud jq sha256sum cmp mktemp date sleep awk chmod cp dirname ln rm tr wc; do
    command -v "$tool" >/dev/null 2>&1 || die "required tool is absent: $tool"
  done
  [[ -x "$PYTHON_BIN" ]] || die "Core v1 local Python is absent or not executable"
}

validate_slug() {
  local value="$1" label="$2" minimum="$3" maximum="$4"
  [[ ${#value} -ge $minimum && ${#value} -le $maximum ]] || \
    die "$label length differs"
  [[ "$value" =~ ^[a-z0-9][a-z0-9._-]*$ ]] || die "$label differs"
  [[ "$value" != *","* ]] || die "$label contains a comma"
}

validate_run_id() {
  local value="$1" label="$2"
  [[ ${#value} -ge 8 && ${#value} -le 81 ]] || die "$label length differs"
  [[ "$value" =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "$label differs"
}

validate_positive_int() {
  local value="$1" label="$2"
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || die "$label must be a canonical positive integer"
}

validate_nonnegative_int() {
  local value="$1" label="$2"
  [[ "$value" == "0" || "$value" =~ ^[1-9][0-9]*$ ]] || \
    die "$label must be a canonical nonnegative integer"
}

validate_gcs_prefix() {
  local value="$1" label="$2" remainder=""
  [[ "$value" =~ ^gs://[^/]+/.+/$ ]] || die "$label must be a nonempty GCS prefix"
  remainder="${value#gs://}"
  [[ "/$remainder/" != *"/../"* && "/$remainder/" != *"/./"* ]] || \
    die "$label contains a noncanonical path segment"
  [[ "$value" != *","* && "$value" != *" "* ]] || die "$label differs"
}

validate_cli() {
  [[ "$EXECUTE" -eq 1 && "${!ENABLED_ENV:-}" == "1" ]] || \
    die "--execute and $ENABLED_ENV=1 are required explicitly"
  case "$MODE" in catalog|outcome|grade|all) ;; *) die "mode differs" ;; esac
  [[ "$PROJECT" == "$PROJECT_LAW" ]] || die "project differs"
  [[ "$REGION" == "$REGION_LAW" ]] || die "region differs"
  validate_run_id "$CHAIN_RUN_ID" "chain run ID"
  [[ "$JOB" =~ ^[a-z0-9][a-z0-9-]{2,62}$ ]] || die "Cloud Run job differs"
  [[ "$SERVICE_ACCOUNT" =~ ^[a-z0-9][a-z0-9.-]*@[a-z0-9.-]+\.gserviceaccount\.com$ ]] || \
    die "service account differs"
  [[ "$IMAGE" =~ ^[^[:space:],]+@sha256:[0-9a-f]{64}$ ]] || die "image is not digest pinned"
  [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "code SHA differs"
  validate_slug "$CATALOG_ID" "catalog ID" 3 128
  validate_run_id "$OUTCOME_RUN_ID" "outcome run ID"
  validate_run_id "$GRADE_RUN_ID" "grade run ID"
  validate_gcs_prefix "$CATALOG_OUTPUT_PREFIX" "catalog output prefix"
  validate_gcs_prefix "$OUTCOME_OUTPUT_PREFIX" "outcome output prefix"
  validate_gcs_prefix "$GRADE_OUTPUT_PREFIX" "grade output prefix"
  validate_positive_int "$MAX_LOGICAL_CATALOG_BYTES" "catalog byte ceiling"
  validate_positive_int "$MAX_LOGICAL_GRADE_BYTES" "grade byte ceiling"
  validate_positive_int "$POLL_SECONDS" "poll seconds"
  validate_positive_int "$MAX_WAIT_SECONDS" "maximum wait seconds"
  [[ "$OUTCOME_OUTPUT_PREFIX" == \
    "gs://nfl-predictions-503414-corpus-retrieval/research/corpus-core-v1-realized/$OUTCOME_RUN_ID/" ]] || \
    die "outcome output prefix differs from the runner's fixed law"
  [[ "$GRADE_OUTPUT_PREFIX" == \
    "gs://nfl-predictions-503414-corpus-retrieval/research/corpus-core-v1-grades/$GRADE_RUN_ID/" ]] || \
    die "grade output prefix differs from the runner's fixed law"
  [[ -f "$SOURCE_PANEL_IDENTITY_FILE" && ! -L "$SOURCE_PANEL_IDENTITY_FILE" ]] || \
    die "source-panel identity must be one regular local file"
  [[ -f "$T230_PANEL_RELEASE_IDENTITY_FILE" && ! -L "$T230_PANEL_RELEASE_IDENTITY_FILE" ]] || \
    die "T230 panel-release identity must be one regular local file"
  if [[ "$MODE" == "outcome" || "$MODE" == "all" ]]; then
    [[ -n "$LEASE_RECEIPT_FILE" && -f "$LEASE_RECEIPT_FILE" && ! -L "$LEASE_RECEIPT_FILE" ]] || \
      die "outcome execution requires one supplied regular lease receipt"
  fi
}

canonicalize_identity() {
  local source="$1" target="$2" label="$3"
  jq -ce '
    if (
      type == "object"
      and (keys | sort) == ["bytes","generation","sha256","uri"]
      and (.uri | type == "string" and startswith("gs://") and (endswith("/") | not))
      and (.uri | contains(",") | not)
      and (.uri | test("[[:space:]]") | not)
      and (.uri | split("/") | all(. != "." and . != ".."))
      and (.generation | type == "string" and test("^[1-9][0-9]*$"))
      and (.sha256 | type == "string" and test("^[0-9a-f]{64}$"))
      and (.bytes | type == "number" and floor == . and . >= 1)
    ) then . else error("object identity differs") end
  ' "$source" >"$target" || die "$label differs"
}

canonicalize_lease_receipt() {
  local source="$1" target="$2" lease_raw lease_sha lease_bytes
  jq -cSe --arg run_id "$OUTCOME_RUN_ID" --arg job "$JOB" \
    --arg code_sha "$CODE_SHA" --arg image "$IMAGE" \
    --arg uri "$OUTCOME_LEASE_URI" '
    if (
      type == "object"
      and (keys | sort) == ["lease","object"]
      and (.lease | type == "object")
      and (.lease | keys | sort) == ["acquired_at","code_sha","image","job","run_id","version"]
      and .lease.version == "historical-outcome-active-v1"
      and .lease.run_id == $run_id
      and .lease.job == $job
      and .lease.code_sha == $code_sha
      and .lease.image == $image
      and (.lease.acquired_at | type == "string" and length > 0)
      and (.object | type == "object")
      and (.object | keys | sort) == ["bytes","create_only","generation","sha256","uri"]
      and .object.uri == $uri
      and .object.create_only == true
      and (.object.generation | type == "string" and test("^[1-9][0-9]*$"))
      and (.object.sha256 | type == "string" and test("^[0-9a-f]{64}$"))
      and (.object.bytes | type == "number" and floor == . and . >= 1)
    ) then . else error("lease receipt differs") end
  ' "$source" >"$target" || die "historical-outcome lease receipt differs"
  cmp -s "$source" "$target" || \
    die "historical-outcome lease receipt is not exact canonical writer bytes"
  lease_raw="$(mktemp)"
  jq -cS '.lease' "$target" >"$lease_raw"
  lease_sha="$(sha256sum "$lease_raw" | awk '{print $1}')"
  lease_bytes="$(wc -c <"$lease_raw" | tr -d ' ')"
  if [[ "$lease_sha" != "$(jq -er '.object.sha256' "$target")" || \
        "$lease_bytes" != "$(jq -er '.object.bytes | tostring' "$target")" ]]; then
    rm -f -- "$lease_raw"
    die "lease receipt does not bind its canonical lease bytes"
  fi
  rm -f -- "$lease_raw"
}

install_local_equal() {
  local source="$1" target="$2" directory temp
  directory="$(dirname "$target")"
  mkdir -p "$directory"
  if [[ -e "$target" || -L "$target" ]]; then
    [[ -f "$target" && ! -L "$target" ]] || die "durable evidence target is not a regular file: $target"
    cmp -s "$source" "$target" || die "durable evidence differs: $target"
    return 0
  fi
  temp="$(mktemp "$directory/.core-v1-local.XXXXXX")"
  cp -- "$source" "$temp"
  chmod 0600 "$temp"
  if ! ln "$temp" "$target" 2>/dev/null; then
    [[ -f "$target" && ! -L "$target" ]] && cmp -s "$temp" "$target" || {
      rm -f -- "$temp"
      die "durable evidence create/equal race differs: $target"
    }
  fi
  rm -f -- "$temp"
}

write_local_equal() {
  local target="$1" value="$2" directory temp
  directory="$(dirname "$target")"
  mkdir -p "$directory"
  temp="$(mktemp "$directory/.core-v1-text.XXXXXX")"
  printf '%s\n' "$value" >"$temp"
  install_local_equal "$temp" "$target"
  rm -f -- "$temp"
}

prepare_chain_config() {
  local run_dir="$1" config_tmp
  SOURCE_PANEL_CANON="$(mktemp)"
  T230_PANEL_RELEASE_CANON="$(mktemp)"
  canonicalize_identity "$SOURCE_PANEL_IDENTITY_FILE" "$SOURCE_PANEL_CANON" "source-panel identity"
  canonicalize_identity "$T230_PANEL_RELEASE_IDENTITY_FILE" "$T230_PANEL_RELEASE_CANON" "T230 panel-release identity"
  install_local_equal "$SOURCE_PANEL_CANON" "$run_dir/source-panel-identity.json"
  install_local_equal "$T230_PANEL_RELEASE_CANON" "$run_dir/t230-panel-release-identity.json"
  config_tmp="$(mktemp)"
  jq -cnS \
    --arg schema_version "core-v1-score-chain-config/v1" \
    --arg chain_run_id "$CHAIN_RUN_ID" --arg project "$PROJECT" --arg region "$REGION" \
    --arg job "$JOB" --arg service_account "$SERVICE_ACCOUNT" --arg image "$IMAGE" \
    --arg code_sha "$CODE_SHA" --arg catalog_id "$CATALOG_ID" \
    --arg catalog_output_prefix "$CATALOG_OUTPUT_PREFIX" \
    --argjson max_catalog "$MAX_LOGICAL_CATALOG_BYTES" \
    --arg outcome_run_id "$OUTCOME_RUN_ID" --arg outcome_output_prefix "$OUTCOME_OUTPUT_PREFIX" \
    --arg grade_run_id "$GRADE_RUN_ID" --arg grade_output_prefix "$GRADE_OUTPUT_PREFIX" \
    --argjson max_grade "$MAX_LOGICAL_GRADE_BYTES" \
    --slurpfile source "$SOURCE_PANEL_CANON" --slurpfile t230 "$T230_PANEL_RELEASE_CANON" '
      {
        schema_version:$schema_version, chain_run_id:$chain_run_id,
        project:$project, region:$region, cloud_run_job:$job,
        service_account:$service_account, image:$image, code_sha:$code_sha,
        catalog:{run_id:$catalog_id,output_prefix:$catalog_output_prefix,
          max_logical_bytes:$max_catalog,root_uri:($catalog_output_prefix+"catalog-root.json")},
        outcome:{run_id:$outcome_run_id,output_prefix:$outcome_output_prefix,
          completion_uri:($outcome_output_prefix+"completion.json")},
        grade:{run_id:$grade_run_id,output_prefix:$grade_output_prefix,
          max_logical_bytes:$max_grade,completion_uri:($grade_output_prefix+"completion.json")},
        source_panel_identity:$source[0],t230_panel_release_identity:$t230[0],
        cloud_build_or_deploy_licensed:false,automatic_retry_licensed:false,
        historical_lease_managed_by_chain:false
      }
    ' >"$config_tmp"
  install_local_equal "$config_tmp" "$run_dir/config.json"
  rm -f -- "$config_tmp"
}

prepare_lease_evidence() {
  local run_dir="$1"
  LEASE_RECEIPT_CANON="$(mktemp)"
  canonicalize_lease_receipt "$LEASE_RECEIPT_FILE" "$LEASE_RECEIPT_CANON"
  install_local_equal "$LEASE_RECEIPT_CANON" "$run_dir/historical-outcome-lease-receipt.json"
}

job_contract() {
  local stage_dir="$1" raw projected
  raw="$(mktemp)"
  projected="$(mktemp)"
  gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
    --format=json >"$raw"
  jq -ce --arg job "$JOB" --arg image "$IMAGE" \
    --arg service_account "$SERVICE_ACCOUNT" '
    .spec.template.spec as $outer
    | $outer.template.spec as $task
    | $task.containers as $containers
    | if (
        (.metadata.name | endswith("/" + $job) or . == $job)
        and $outer.taskCount == 1
        and $outer.parallelism == 1
        and ($containers | type == "array" and length == 1)
        and $containers[0].image == $image
        and $containers[0].command == ["bash"]
        and $containers[0].args == [
          "-ceu",
          "python scripts/run_corpus_extreme_tail_panel_transport_v1.py parked"
        ]
        and $containers[0].resources.limits == {cpu:"8",memory:"32Gi"}
        and ($containers[0].env // []) == []
        and ($containers[0].volumeMounts // []) == [{
          name:"foundry-t230-runtime-evidence",mountPath:"/etc/nfl-dfs"
        }]
        and $task.maxRetries == 0
        and (($task.timeoutSeconds | tostring) == "21600")
        and $task.serviceAccountName == $service_account
        and ($task.volumes // []) == [{
          name:"foundry-t230-runtime-evidence",
          emptyDir:{medium:"Memory",sizeLimit:"1Mi"}
        }]
      ) then {
        schema_version:"core-v1-score-chain-job-projection/v1",
        job:$job,image:$image,service_account:$service_account,
        command:["bash"],parked_args:$containers[0].args,
        cpu:"8",memory:"32Gi",task_count:1,parallelism:1,
        max_retries:0,task_timeout_seconds:21600,
        runtime_evidence_volume:{type:"in-memory",name:"foundry-t230-runtime-evidence",
          size_limit:"1Mi",mount_path:"/etc/nfl-dfs"},
        cloud_describe_exactly_validated:true
      } else error("configured Cloud Run job differs from Core v1 chain contract") end
  ' "$raw" >"$projected" || {
    rm -f -- "$raw" "$projected"
    die "configured Cloud Run job differs from the image-D reuse contract"
  }
  install_local_equal "$projected" "$stage_dir/job-config.json"
  rm -f -- "$raw" "$projected"
}

shell_command() {
  local token joined=""
  for token in "$@"; do
    [[ "$token" != *","* ]] || die "remote CLI argument contains a comma"
    printf -v token '%q' "$token"
    if [[ -z "$joined" ]]; then joined="$token"; else joined+=" $token"; fi
  done
  printf 'exec %s\n' "$joined"
}

stage_launch_receipt() {
  local stage_dir="$1" stage="$2" gate="$3" command="$4" temp lease_sha lease_object
  temp="$(mktemp)"
  lease_sha=""
  lease_object="null"
  if [[ "$stage" == "outcome" ]]; then
    [[ -n "$LEASE_RECEIPT_CANON" && -f "$LEASE_RECEIPT_CANON" ]] || \
      die "outcome launch lacks its validated lease receipt"
    lease_sha="$(sha256sum "$LEASE_RECEIPT_CANON" | awk '{print $1}')"
    lease_object="$(jq -c '.object' "$LEASE_RECEIPT_CANON")"
  fi
  jq -cnS --arg schema_version "core-v1-score-chain-launch/v1" \
    --arg stage "$stage" --arg job "$JOB" --arg image "$IMAGE" \
    --arg service_account "$SERVICE_ACCOUNT" --arg gate "$gate" \
    --arg bash_command "$command" --arg lease_sha "$lease_sha" \
    --argjson lease_object "$lease_object" '
    {schema_version:$schema_version,stage:$stage,job:$job,image:$image,
      service_account:$service_account,container_command:["bash"],
      execution_args:["-ceu",$bash_command],execution_env:($gate+"=1"),
      historical_outcome_lease_receipt_sha256:
        (if $stage == "outcome" then $lease_sha else null end),
      historical_outcome_lease_object:
        (if $stage == "outcome" then $lease_object else null end),
      async:true,build_or_deploy_licensed:false,automatic_retry_licensed:false}
  ' >"$temp"
  install_local_equal "$temp" "$stage_dir/launch.json"
  rm -f -- "$temp"
}

terminal_state() {
  local source="$1" execution="$2"
  jq -er --arg execution "$execution" '
    if (.metadata.name == $execution or (.metadata.name | endswith("/" + $execution)))
    then ([.status.conditions[]? | select(.type == "Completed")] | if length == 1 then .[0].status else "Unknown" end)
    else error("execution name differs") end
  ' "$source"
}

has_completion_time() {
  jq -e '.status.completionTime | type == "string" and length > 0' "$1" \
    >/dev/null
}

validate_terminal_envelope() {
  local source="$1" execution="$2" gate="$3" command="$4"
  jq -e --arg execution "$execution" --arg job "$JOB" --arg image "$IMAGE" \
    --arg service_account "$SERVICE_ACCOUNT" --arg gate "$gate" \
    --arg bash_command "$command" '
    .spec as $outer
    | .spec.template.spec as $task
    | $task.containers as $containers
    | if (
        ((.metadata.name == $execution) or (.metadata.name | endswith("/" + $execution)))
        and .metadata.labels["run.googleapis.com/job"] == $job
        and $outer.taskCount == 1
        and $outer.parallelism == 1
        and ($containers | type == "array" and length == 1)
        and $containers[0].image == $image
        and $containers[0].command == ["bash"]
        and $containers[0].args == ["-ceu",$bash_command]
        and $containers[0].resources.limits == {cpu:"8",memory:"32Gi"}
        and ($containers[0].env // []) == [{name:$gate,value:"1"}]
        and ($containers[0].volumeMounts // []) == [{
          name:"foundry-t230-runtime-evidence",mountPath:"/etc/nfl-dfs"
        }]
        and $task.maxRetries == 0
        and (($task.timeoutSeconds | tostring) == "21600")
        and $task.serviceAccountName == $service_account
        and ($task.volumes // []) == [{
          name:"foundry-t230-runtime-evidence",
          emptyDir:{medium:"Memory",sizeLimit:"1Mi"}
        }]
      ) then true else error("terminal execution envelope differs") end
  ' "$source" >/dev/null || die "terminal execution differs from its exact image-D stage envelope"
}

validate_closed_stage() {
  local stage_dir="$1" gate="$2" command="$3" execution state
  [[ -f "$stage_dir/execution-name.txt" && ! -L "$stage_dir/execution-name.txt" ]] || return 1
  [[ -f "$stage_dir/terminal-execution.json" && ! -L "$stage_dir/terminal-execution.json" ]] || return 1
  [[ -f "$stage_dir/elapsed-seconds.txt" && ! -L "$stage_dir/elapsed-seconds.txt" ]] || return 1
  execution="$(tr -d '\n' <"$stage_dir/execution-name.txt")"
  [[ "$execution" =~ ^[a-z0-9][a-z0-9-]{2,127}$ ]] || die "retained execution name differs"
  state="$(terminal_state "$stage_dir/terminal-execution.json" "$execution")"
  [[ "$state" == "True" ]] || die "retained stage execution is not successful"
  validate_terminal_envelope "$stage_dir/terminal-execution.json" "$execution" "$gate" "$command"
  has_completion_time "$stage_dir/terminal-execution.json" || \
    die "retained terminal execution lacks completion time"
  validate_nonnegative_int \
    "$(tr -d '\n' <"$stage_dir/elapsed-seconds.txt")" "retained elapsed seconds"
  return 0
}

wait_for_terminal() {
  local stage_dir="$1" execution="$2" started_epoch="$3" gate="$4" command="$5"
  local observed state now elapsed
  while true; do
    observed="$(mktemp)"
    gcloud run jobs executions describe "$execution" \
      --project "$PROJECT" --region "$REGION" --format=json >"$observed"
    state="$(terminal_state "$observed" "$execution")"
    now="$(date +%s)"
    elapsed=$((now - started_epoch))
    ((elapsed >= 0)) || die "wall clock moved behind stage start"
    if [[ "$state" == "Unknown" ]]; then
      rm -f -- "$observed"
      if ((elapsed >= MAX_WAIT_SECONDS)); then
        printf 'CORE_V1_STAGE_STILL_RUNNING %s %s elapsed=%s\n' \
          "$(basename "$stage_dir")" "$execution" "$elapsed" >&2
        return 3
      fi
      sleep "$POLL_SECONDS"
      continue
    fi
    validate_terminal_envelope "$observed" "$execution" "$gate" "$command"
    install_local_equal "$observed" "$stage_dir/terminal-execution.json"
    write_local_equal "$stage_dir/elapsed-seconds.txt" "$elapsed"
    rm -f -- "$observed"
    [[ "$state" == "True" ]] || die "Cloud Run stage execution failed or was cancelled: $execution"
    has_completion_time "$stage_dir/terminal-execution.json" || \
      die "successful terminal execution lacks completion time"
    return 0
  done
}

run_stage() {
  local run_dir="$1" stage="$2" gate="$3" command="$4"
  local stage_dir="$run_dir/stages/$stage" execution started_epoch launch_output
  [[ ! -L "$run_dir/stages" && ! -L "$stage_dir" ]] || \
    die "stage evidence directory cannot be a symlink"
  mkdir -p "$stage_dir"
  [[ -d "$stage_dir" && ! -L "$stage_dir" ]] || die "stage evidence directory differs"
  if validate_closed_stage "$stage_dir" "$gate" "$command"; then
    printf 'CORE_V1_STAGE_RECOVERED %s %s\n' "$stage" "$(tr -d '\n' <"$stage_dir/execution-name.txt")"
    return 0
  fi
  stage_launch_receipt "$stage_dir" "$stage" "$gate" "$command"
  if [[ -f "$stage_dir/started-at-epoch.txt" && ! -L "$stage_dir/started-at-epoch.txt" ]]; then
    started_epoch="$(tr -d '\n' <"$stage_dir/started-at-epoch.txt")"
    validate_positive_int "$started_epoch" "stage start epoch"
  else
    started_epoch="$(date +%s)"
    write_local_equal "$stage_dir/started-at-epoch.txt" "$started_epoch"
  fi
  if [[ -f "$stage_dir/execution-name.txt" && ! -L "$stage_dir/execution-name.txt" ]]; then
    execution="$(tr -d '\n' <"$stage_dir/execution-name.txt")"
  else
    job_contract "$stage_dir"
    launch_output="$(mktemp)"
    if ! gcloud run jobs execute "$JOB" \
      --project "$PROJECT" --region "$REGION" \
      --args="-ceu,$command" --update-env-vars="$gate=1" \
      --async --quiet --format='value(metadata.name)' >"$launch_output"; then
      rm -f -- "$launch_output"
      die "Cloud Run launch response was ambiguous; the fixed stage is safe to recover/reinvoke"
    fi
    execution="$(tr -d '\r\n' <"$launch_output")"
    rm -f -- "$launch_output"
    [[ "$execution" =~ ^[a-z0-9][a-z0-9-]{2,127}$ ]] || die "Cloud Run execution name differs"
    write_local_equal "$stage_dir/execution-name.txt" "$execution"
  fi
  [[ "$execution" =~ ^[a-z0-9][a-z0-9-]{2,127}$ ]] || die "Cloud Run execution name differs"
  wait_for_terminal "$stage_dir" "$execution" "$started_epoch" "$gate" "$command"
  printf 'CORE_V1_STAGE_CLOSED %s %s elapsed=%s\n' \
    "$stage" "$execution" "$(tr -d '\n' <"$stage_dir/elapsed-seconds.txt")"
}

catalog_command() {
  shell_command python scripts/run_core_v1_catalog_cloud.py materialize \
    --execute --project "$PROJECT" --catalog-id "$CATALOG_ID" \
    --output-prefix "$CATALOG_OUTPUT_PREFIX" \
    --max-logical-catalog-bytes "$MAX_LOGICAL_CATALOG_BYTES" \
    --source-panel-uri "$(jq -er '.uri' "$SOURCE_PANEL_CANON")" \
    --source-panel-generation "$(jq -er '.generation' "$SOURCE_PANEL_CANON")" \
    --source-panel-sha256 "$(jq -er '.sha256' "$SOURCE_PANEL_CANON")" \
    --source-panel-bytes "$(jq -er '.bytes' "$SOURCE_PANEL_CANON")" \
    --t230-panel-release-uri "$(jq -er '.uri' "$T230_PANEL_RELEASE_CANON")" \
    --t230-panel-release-generation "$(jq -er '.generation' "$T230_PANEL_RELEASE_CANON")" \
    --t230-panel-release-sha256 "$(jq -er '.sha256' "$T230_PANEL_RELEASE_CANON")" \
    --t230-panel-release-bytes "$(jq -er '.bytes' "$T230_PANEL_RELEASE_CANON")"
}

outcome_command() {
  shell_command python scripts/run_core_v1_outcome_supply.py \
    --execute --project "$PROJECT" --run-id "$OUTCOME_RUN_ID" \
    --job "$JOB" --code-sha "$CODE_SHA" --image "$IMAGE" \
    --catalog-root-uri "${CATALOG_OUTPUT_PREFIX}catalog-root.json" \
    --expected-lease-uri "$(jq -er '.object.uri' "$LEASE_RECEIPT_CANON")" \
    --expected-lease-generation "$(jq -er '.object.generation' "$LEASE_RECEIPT_CANON")" \
    --expected-lease-sha256 "$(jq -er '.object.sha256' "$LEASE_RECEIPT_CANON")" \
    --expected-lease-bytes "$(jq -er '.object.bytes' "$LEASE_RECEIPT_CANON")"
}

grade_command() {
  shell_command python scripts/run_core_v1_grade_cloud.py grade \
    --execute --project "$PROJECT" --grade-run-id "$GRADE_RUN_ID" \
    --max-logical-grade-bytes "$MAX_LOGICAL_GRADE_BYTES" \
    --catalog-root-uri "${CATALOG_OUTPUT_PREFIX}catalog-root.json" \
    --outcome-completion-uri "${OUTCOME_OUTPUT_PREFIX}completion.json"
}

materialize_core_completion() {
  local run_dir="$1" output receipt_tmp
  output="$run_dir/historical-outcome-strict-completion.txt"
  receipt_tmp="$(mktemp)"
  if ! PYTHONPATH="$ROOT/src:$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}" \
    "$PYTHON_BIN" "$ROOT/scripts/historical_outcome_lease.py" \
      materialize-core-v1-completion \
      --receipt "$run_dir/historical-outcome-lease-receipt.json" \
      --completion-uri "${OUTCOME_OUTPUT_PREFIX}completion.json" \
      --output "$output" >"$receipt_tmp"; then
    rm -f -- "$receipt_tmp"
    die "Core v1 strict lease completion materialization failed"
  fi
  install_local_equal \
    "$receipt_tmp" "$run_dir/historical-outcome-completion-materialization.txt"
  rm -f -- "$receipt_tmp"
}

record_release_required() {
  local run_dir="$1" temp
  temp="$(mktemp)"
  jq -cnS --arg schema_version "core-v1-score-chain-lease-release-required/v1" \
    --arg lease_receipt "$run_dir/historical-outcome-lease-receipt.json" \
    --arg outcome_execution "$run_dir/stages/outcome/terminal-execution.json" \
    --arg strict_completion "$run_dir/historical-outcome-strict-completion.txt" \
    --arg outcome_completion_uri "${OUTCOME_OUTPUT_PREFIX}completion.json" '
    {schema_version:$schema_version,status:"EXPLICIT_EXTERNAL_RELEASE_REQUIRED",
      lease_receipt:$lease_receipt,outcome_execution:$outcome_execution,
      strict_completion:$strict_completion,
      outcome_completion_uri:$outcome_completion_uri,
      automatic_release_licensed:false}
  ' >"$temp"
  install_local_equal "$temp" "$run_dir/historical-outcome-lease-release-required.json"
  rm -f -- "$temp"
}

cleanup() {
  [[ -z "$SOURCE_PANEL_CANON" ]] || rm -f -- "$SOURCE_PANEL_CANON"
  [[ -z "$T230_PANEL_RELEASE_CANON" ]] || rm -f -- "$T230_PANEL_RELEASE_CANON"
  [[ -z "$LEASE_RECEIPT_CANON" ]] || rm -f -- "$LEASE_RECEIPT_CANON"
}

main() {
  umask 077
  parse_args "$@"
  validate_cli
  require_tools
  trap cleanup EXIT
  local run_dir="$RUN_ROOT/$CHAIN_RUN_ID"
  [[ ! -L "$ROOT/reports" && ! -L "$RUN_ROOT" && ! -L "$run_dir" ]] || \
    die "score-chain evidence path cannot be a symlink"
  mkdir -p "$run_dir"
  [[ -d "$run_dir" && ! -L "$run_dir" ]] || die "score-chain evidence directory differs"
  prepare_chain_config "$run_dir"
  if [[ "$MODE" == "outcome" || "$MODE" == "all" ]]; then
    prepare_lease_evidence "$run_dir"
  fi
  case "$MODE" in
    catalog)
      run_stage "$run_dir" catalog CORE_V1_CATALOG_CLOUD_ENABLED "$(catalog_command)"
      ;;
    outcome)
      run_stage "$run_dir" outcome CORE_V1_OUTCOME_SUPPLY_ENABLED "$(outcome_command)"
      materialize_core_completion "$run_dir"
      record_release_required "$run_dir"
      ;;
    grade)
      run_stage "$run_dir" grade CORE_V1_GRADE_CLOUD_ENABLED "$(grade_command)"
      ;;
    all)
      run_stage "$run_dir" catalog CORE_V1_CATALOG_CLOUD_ENABLED "$(catalog_command)"
      run_stage "$run_dir" outcome CORE_V1_OUTCOME_SUPPLY_ENABLED "$(outcome_command)"
      materialize_core_completion "$run_dir"
      record_release_required "$run_dir"
      run_stage "$run_dir" grade CORE_V1_GRADE_CLOUD_ENABLED "$(grade_command)"
      record_release_required "$run_dir"
      ;;
  esac
  printf 'CORE_V1_SCORE_CHAIN_CLOSED mode=%s run_dir=%s lease_release_external=%s\n' \
    "$MODE" "$run_dir" "$([[ "$MODE" == "outcome" || "$MODE" == "all" ]] && printf true || printf false)"
}

main "$@"
