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
RECOVER_FAILED_STAGE=""
POLL_SECONDS=15
MAX_WAIT_SECONDS=23000

SOURCE_PANEL_CANON=""
T230_PANEL_RELEASE_CANON=""
LEASE_RECEIPT_CANON=""
RECOVERY_CONSUMED=0
STAGE_OPERATION_LOCK_FD=""

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
    [--lease-receipt FILE] [--recover-failed-stage catalog|outcome|grade] \
    [--poll-seconds N] [--max-wait-seconds N]

`outcome` and `all` require --lease-receipt. Acquire that lease explicitly
with scripts/historical_outcome_lease.py before this operator. The operator
exact-reads the known Core completion and materializes the strict local release
evidence, but never acquires, abandons, or deletes the lease. Release remains
explicit after the grade is durably closed.

Terminally failed executions are retained and refused by default. A reviewed
manual recovery must name exactly one failed stage with
--recover-failed-stage. That flag never authorizes an automatic retry or a
different command, image, input, output, lease, or outcome-query identity.
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
      --recover-failed-stage)
        require_value "$1" "${2:-}"
        [[ -z "$RECOVER_FAILED_STAGE" ]] || die "--recover-failed-stage may be supplied only once"
        RECOVER_FAILED_STAGE="$2"
        shift 2
        ;;
      --poll-seconds) require_value "$1" "${2:-}"; POLL_SECONDS="$2"; shift 2 ;;
      --max-wait-seconds) require_value "$1" "${2:-}"; MAX_WAIT_SECONDS="$2"; shift 2 ;;
      --help|-h) usage; exit 0 ;;
      *) die "unknown argument: $1" ;;
    esac
  done
}

require_tools() {
  local tool
  for tool in gcloud jq sha256sum cmp mktemp date sleep awk chmod cp dirname flock ln mv rm tr wc; do
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
  case "$RECOVER_FAILED_STAGE:$MODE" in
    :*) ;;
    catalog:catalog) ;;
    outcome:outcome) ;;
    grade:grade) ;;
    catalog:all|outcome:all|grade:all)
      die "failed-stage recovery must close in its exact stage mode before all mode"
      ;;
    catalog:*|outcome:*|grade:*)
      die "--recover-failed-stage is outside the selected mode"
      ;;
    *) die "--recover-failed-stage differs" ;;
  esac
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

acquire_stage_operation_lock() {
  local run_dir="$1" stage="$2"
  local lock_root="$run_dir/stages/recovery-transition-locks"
  local lock_file="$lock_root/$stage.lock" temp
  [[ -z "$STAGE_OPERATION_LOCK_FD" ]] || die "stage operation lock is already held"
  [[ ! -L "$run_dir/stages" && ! -L "$lock_root" && ! -L "$lock_file" ]] || \
    die "stage operation lock path cannot be a symlink"
  mkdir -p "$lock_root"
  [[ -d "$lock_root" && ! -L "$lock_root" ]] || \
    die "stage operation lock root differs"
  temp="$(mktemp)"
  : >"$temp"
  install_local_equal "$temp" "$lock_file"
  rm -f -- "$temp"
  [[ -f "$lock_file" && ! -L "$lock_file" ]] || \
    die "stage operation lock file differs"
  exec {STAGE_OPERATION_LOCK_FD}<>"$lock_file"
  if ! flock -n "$STAGE_OPERATION_LOCK_FD"; then
    exec {STAGE_OPERATION_LOCK_FD}>&-
    STAGE_OPERATION_LOCK_FD=""
    die "another invocation owns the stage recovery-transition lock: $stage"
  fi
}

release_stage_operation_lock() {
  [[ -n "$STAGE_OPERATION_LOCK_FD" ]] || die "stage operation lock is not held"
  flock -u "$STAGE_OPERATION_LOCK_FD" || die "stage operation lock release failed"
  exec {STAGE_OPERATION_LOCK_FD}>&-
  STAGE_OPERATION_LOCK_FD=""
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

stage_launch_intent() {
  local run_dir="$1" stage_dir="$2" stage="$3" gate="$4" command="$5"
  local temp config_sha launch_sha job_config_sha file
  for file in "$run_dir/config.json" "$stage_dir/launch.json" "$stage_dir/job-config.json"; do
    [[ -f "$file" && ! -L "$file" ]] || die "launch-intent predecessor is unsafe: $file"
  done
  config_sha="$(sha256sum "$run_dir/config.json" | awk '{print $1}')"
  launch_sha="$(sha256sum "$stage_dir/launch.json" | awk '{print $1}')"
  job_config_sha="$(sha256sum "$stage_dir/job-config.json" | awk '{print $1}')"
  temp="$(mktemp)"
  jq -cnS --arg schema_version "core-v1-score-chain-launch-intent/v1" \
    --arg stage "$stage" --arg job "$JOB" --arg image "$IMAGE" \
    --arg service_account "$SERVICE_ACCOUNT" --arg gate "$gate" \
    --arg bash_command "$command" --arg config_sha "$config_sha" \
    --arg launch_sha "$launch_sha" --arg job_config_sha "$job_config_sha" '
    {schema_version:$schema_version,stage:$stage,job:$job,image:$image,
      service_account:$service_account,gate:$gate,bash_command:$bash_command,
      chain_config_sha256:$config_sha,launch_receipt_sha256:$launch_sha,
      job_config_sha256:$job_config_sha,manual_recovery_required_after_ambiguity:true,
      blind_reinvocation_licensed:false,automatic_retry_licensed:false}
  ' >"$temp"
  install_local_equal "$temp" "$stage_dir/launch-intent.json"
  rm -f -- "$temp"
}

build_stage_launch_claim() {
  local run_dir="$1" stage_dir="$2" stage="$3" output="$4"
  local recovery_attempt="${5:-}"
  local config_sha intent_sha started_sha file archive recovery_claim_sha recovery_receipt_sha
  local recovery_binding="null"
  for file in \
    "$run_dir/config.json" \
    "$stage_dir/launch-intent.json" \
    "$stage_dir/started-at-epoch.txt"; do
    [[ -f "$file" && ! -L "$file" ]] || \
      die "launch-claim predecessor is unsafe: $file"
  done
  config_sha="$(sha256sum "$run_dir/config.json" | awk '{print $1}')"
  intent_sha="$(sha256sum "$stage_dir/launch-intent.json" | awk '{print $1}')"
  started_sha="$(sha256sum "$stage_dir/started-at-epoch.txt" | awk '{print $1}')"
  if [[ -n "$recovery_attempt" ]]; then
    validate_nonnegative_int "$recovery_attempt" "launch-claim recovery attempt ordinal"
    printf -v archive '%s/stages/failed-attempts/%s/attempt-%04d' \
      "$run_dir" "$stage" "$recovery_attempt"
    for file in \
      "$archive/manual-recovery-owner-claim.json" \
      "$archive/manual-recovery.json"; do
      [[ -f "$file" && ! -L "$file" ]] || \
        die "replacement launch recovery binding is unsafe: $file"
    done
    recovery_claim_sha="$(sha256sum "$archive/manual-recovery-owner-claim.json" | awk '{print $1}')"
    recovery_receipt_sha="$(sha256sum "$archive/manual-recovery.json" | awk '{print $1}')"
    recovery_binding="$(jq -cnS --argjson attempt "$recovery_attempt" \
      --arg claim_sha "$recovery_claim_sha" --arg receipt_sha "$recovery_receipt_sha" '
      {failed_attempt_ordinal:$attempt,
        manual_recovery_owner_claim_sha256:$claim_sha,
        manual_recovery_receipt_sha256:$receipt_sha}
    ')"
  fi
  jq -cnS --arg schema_version "core-v1-score-chain-launch-owner-claim/v1" \
    --arg stage "$stage" --arg job "$JOB" --arg image "$IMAGE" \
    --arg config_sha "$config_sha" --arg intent_sha "$intent_sha" \
    --arg started_sha "$started_sha" --argjson recovery_binding "$recovery_binding" '
    {schema_version:$schema_version,stage:$stage,job:$job,image:$image,
      chain_config_sha256:$config_sha,launch_intent_sha256:$intent_sha,
      started_at_epoch_sha256:$started_sha,
      failed_stage_recovery_binding:$recovery_binding,
      creator_alone_may_launch:true,equal_preexisting_claim_licenses_launch:false,
      automatic_retry_licensed:false}
  ' >"$output"
}

claim_stage_launch_owner() {
  local run_dir="$1" stage_dir="$2" stage="$3" recovery_attempt="${4:-}" target temp
  target="$stage_dir/launch-owner-claim.json"
  [[ ! -e "$target" && ! -L "$target" ]] || \
    die "stage launch already has an owner; this invocation cannot launch: $stage"
  temp="$(mktemp "$stage_dir/.launch-owner-claim.XXXXXX")"
  build_stage_launch_claim "$run_dir" "$stage_dir" "$stage" "$temp" "$recovery_attempt"
  chmod 0600 "$temp"
  if ! ln "$temp" "$target" 2>/dev/null; then
    rm -f -- "$temp"
    die "another invocation atomically owns the stage launch: $stage"
  fi
  rm -f -- "$temp"
}

validate_stage_launch_claim() {
  local run_dir="$1" stage_dir="$2" stage="$3" recovery_attempt="${4:-}" target temp
  target="$stage_dir/launch-owner-claim.json"
  [[ -f "$target" && ! -L "$target" ]] || \
    die "stage launch owner claim is unsafe: $target"
  temp="$(mktemp "$stage_dir/.launch-owner-validation.XXXXXX")"
  build_stage_launch_claim "$run_dir" "$stage_dir" "$stage" "$temp" "$recovery_attempt"
  if ! cmp -s "$temp" "$target"; then
    rm -f -- "$temp"
    die "stage launch owner claim differs: $target"
  fi
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
  local run_dir="$1" stage_dir="$2" stage="$3" gate="$4" command="$5"
  local archive_count="$6" recovery_attempt=""
  local execution state response_execution launch_status started_epoch file
  validate_nonnegative_int "$archive_count" "closed-stage failed archive count"
  [[ -f "$stage_dir/execution-name.txt" && ! -L "$stage_dir/execution-name.txt" ]] || return 1
  for file in \
    "$run_dir/config.json" \
    "$stage_dir/launch.json" \
    "$stage_dir/job-config.json" \
    "$stage_dir/started-at-epoch.txt" \
    "$stage_dir/launch-intent.json" \
    "$stage_dir/launch-owner-claim.json" \
    "$stage_dir/launch-output.txt" \
    "$stage_dir/launch-exit-status.txt"; do
    [[ -f "$file" && ! -L "$file" ]] || \
      die "retained stage launch evidence is unsafe: $file"
  done
  stage_launch_receipt "$stage_dir" "$stage" "$gate" "$command"
  stage_launch_intent "$run_dir" "$stage_dir" "$stage" "$gate" "$command"
  if [[ "$archive_count" -gt 0 ]]; then
    recovery_attempt=$((archive_count - 1))
  fi
  validate_stage_launch_claim "$run_dir" "$stage_dir" "$stage" "$recovery_attempt"
  execution="$(tr -d '\n' <"$stage_dir/execution-name.txt")"
  [[ "$execution" =~ ^[a-z0-9][a-z0-9-]{2,127}$ ]] || die "retained execution name differs"
  response_execution="$(tr -d '\r\n' <"$stage_dir/launch-output.txt")"
  [[ "$response_execution" == "$execution" ]] || \
    die "retained launch output differs from its execution name"
  launch_status="$(tr -d '\n' <"$stage_dir/launch-exit-status.txt")"
  validate_nonnegative_int "$launch_status" "retained launch exit status"
  [[ "$launch_status" == "0" ]] || die "retained launch exit status differs"
  started_epoch="$(tr -d '\n' <"$stage_dir/started-at-epoch.txt")"
  validate_positive_int "$started_epoch" "retained stage start epoch"
  [[ -f "$stage_dir/terminal-execution.json" && ! -L "$stage_dir/terminal-execution.json" ]] || return 1
  [[ -f "$stage_dir/elapsed-seconds.txt" && ! -L "$stage_dir/elapsed-seconds.txt" ]] || return 1
  state="$(terminal_state "$stage_dir/terminal-execution.json" "$execution")"
  [[ "$state" == "True" || "$state" == "False" ]] || \
    die "retained stage execution terminal state differs"
  validate_terminal_envelope "$stage_dir/terminal-execution.json" "$execution" "$gate" "$command"
  has_completion_time "$stage_dir/terminal-execution.json" || \
    die "retained terminal execution lacks completion time"
  validate_nonnegative_int \
    "$(tr -d '\n' <"$stage_dir/elapsed-seconds.txt")" "retained elapsed seconds"
  [[ "$state" == "True" ]] || return 4
  return 0
}

build_failed_recovery_claim() {
  local run_dir="$1" stage_dir="$2" stage="$3" attempt="$4" output="$5"
  local config_sha terminal_sha launch_claim_sha execution file
  for file in \
    "$run_dir/config.json" \
    "$stage_dir/terminal-execution.json" \
    "$stage_dir/launch-owner-claim.json" \
    "$stage_dir/execution-name.txt"; do
    [[ -f "$file" && ! -L "$file" ]] || \
      die "recovery-claim predecessor is unsafe: $file"
  done
  validate_nonnegative_int "$attempt" "recovery-claim attempt ordinal"
  execution="$(tr -d '\n' <"$stage_dir/execution-name.txt")"
  [[ "$execution" =~ ^[a-z0-9][a-z0-9-]{2,127}$ ]] || \
    die "recovery-claim execution name differs"
  config_sha="$(sha256sum "$run_dir/config.json" | awk '{print $1}')"
  terminal_sha="$(sha256sum "$stage_dir/terminal-execution.json" | awk '{print $1}')"
  launch_claim_sha="$(sha256sum "$stage_dir/launch-owner-claim.json" | awk '{print $1}')"
  jq -cnS --arg schema_version "core-v1-score-chain-recovery-owner-claim/v1" \
    --arg stage "$stage" --argjson attempt "$attempt" \
    --arg execution "$execution" --arg config_sha "$config_sha" \
    --arg terminal_sha "$terminal_sha" --arg launch_claim_sha "$launch_claim_sha" '
    {schema_version:$schema_version,stage:$stage,failed_attempt_ordinal:$attempt,
      failed_execution:$execution,chain_config_sha256:$config_sha,
      terminal_execution_sha256:$terminal_sha,
      launch_owner_claim_sha256:$launch_claim_sha,
      creator_alone_may_archive_and_recover:true,
      equal_preexisting_claim_licenses_recovery:false,
      equal_preexisting_claim_allows_locked_transaction_replay:true,
      automatic_retry_licensed:false}
  ' >"$output"
}

claim_failed_recovery_owner() {
  local run_dir="$1" stage_dir="$2" stage="$3" attempt="$4" target temp
  [[ "$RECOVER_FAILED_STAGE" == "$stage" && -n "$STAGE_OPERATION_LOCK_FD" ]] || \
    die "failed-stage recovery claim requires its explicit locked transaction"
  target="$stage_dir/manual-recovery-owner-claim.json"
  temp="$(mktemp "$stage_dir/.recovery-owner-claim.XXXXXX")"
  build_failed_recovery_claim "$run_dir" "$stage_dir" "$stage" "$attempt" "$temp"
  chmod 0600 "$temp"
  if [[ -e "$target" || -L "$target" ]]; then
    [[ -f "$target" && ! -L "$target" ]] || {
      rm -f -- "$temp"
      die "failed-stage recovery owner claim is unsafe: $target"
    }
    if ! cmp -s "$temp" "$target"; then
      rm -f -- "$temp"
      die "failed-stage recovery owner claim differs: $target"
    fi
    rm -f -- "$temp"
    return 0
  fi
  if ! ln "$temp" "$target" 2>/dev/null; then
    [[ -f "$target" && ! -L "$target" ]] && cmp -s "$temp" "$target" || {
      rm -f -- "$temp"
      die "failed-stage recovery owner claim create/equal race differs: $target"
    }
  fi
  rm -f -- "$temp"
}

validate_failed_recovery_claim() {
  local run_dir="$1" stage_dir="$2" stage="$3" attempt="$4" target temp
  target="$stage_dir/manual-recovery-owner-claim.json"
  [[ -f "$target" && ! -L "$target" ]] || \
    die "failed-stage recovery owner claim is unsafe: $target"
  temp="$(mktemp "$stage_dir/.recovery-owner-validation.XXXXXX")"
  build_failed_recovery_claim "$run_dir" "$stage_dir" "$stage" "$attempt" "$temp"
  if ! cmp -s "$temp" "$target"; then
    rm -f -- "$temp"
    die "failed-stage recovery owner claim differs: $target"
  fi
  rm -f -- "$temp"
}

manual_recovery_receipt() {
  local run_dir="$1" stage_dir="$2" stage="$3" attempt="$4" gate="$5" command="$6"
  local temp lease_sha lease_object fixed_outcome file
  local config_sha launch_sha job_config_sha started_sha intent_sha claim_sha
  local recovery_claim_sha response_sha
  local response_status_sha execution_sha terminal_sha elapsed_sha
  local execution elapsed launch_status started_epoch response_execution
  local prior_recovery_attempt=""
  for file in \
    "$run_dir/config.json" \
    "$stage_dir/launch.json" \
    "$stage_dir/job-config.json" \
    "$stage_dir/started-at-epoch.txt" \
    "$stage_dir/launch-intent.json" \
    "$stage_dir/launch-owner-claim.json" \
    "$stage_dir/manual-recovery-owner-claim.json" \
    "$stage_dir/launch-output.txt" \
    "$stage_dir/launch-exit-status.txt" \
    "$stage_dir/execution-name.txt" \
    "$stage_dir/terminal-execution.json" \
    "$stage_dir/elapsed-seconds.txt"; do
    [[ -f "$file" && ! -L "$file" ]] || die "failed-stage recovery predecessor is unsafe: $file"
  done
  validate_nonnegative_int "$attempt" "failed-stage attempt ordinal"
  execution="$(tr -d '\n' <"$stage_dir/execution-name.txt")"
  [[ "$execution" =~ ^[a-z0-9][a-z0-9-]{2,127}$ ]] || die "failed execution name differs"
  response_execution="$(tr -d '\r\n' <"$stage_dir/launch-output.txt")"
  [[ "$response_execution" == "$execution" ]] || \
    die "failed launch response does not bind its execution name"
  launch_status="$(tr -d '\n' <"$stage_dir/launch-exit-status.txt")"
  validate_nonnegative_int "$launch_status" "failed launch exit status"
  [[ "$launch_status" == "0" ]] || die "failed launch exit status differs"
  started_epoch="$(tr -d '\n' <"$stage_dir/started-at-epoch.txt")"
  validate_positive_int "$started_epoch" "failed stage start epoch"
  [[ "$(terminal_state "$stage_dir/terminal-execution.json" "$execution")" == "False" ]] || \
    die "manual recovery requires one terminally failed execution"
  validate_terminal_envelope "$stage_dir/terminal-execution.json" "$execution" "$gate" "$command"
  has_completion_time "$stage_dir/terminal-execution.json" || \
    die "failed execution lacks completion time"
  elapsed="$(tr -d '\n' <"$stage_dir/elapsed-seconds.txt")"
  validate_nonnegative_int "$elapsed" "failed execution elapsed seconds"
  stage_launch_receipt "$stage_dir" "$stage" "$gate" "$command"
  stage_launch_intent "$run_dir" "$stage_dir" "$stage" "$gate" "$command"
  if [[ "$attempt" -gt 0 ]]; then
    prior_recovery_attempt=$((attempt - 1))
  fi
  validate_stage_launch_claim \
    "$run_dir" "$stage_dir" "$stage" "$prior_recovery_attempt"
  validate_failed_recovery_claim "$run_dir" "$stage_dir" "$stage" "$attempt"

  config_sha="$(sha256sum "$run_dir/config.json" | awk '{print $1}')"
  launch_sha="$(sha256sum "$stage_dir/launch.json" | awk '{print $1}')"
  job_config_sha="$(sha256sum "$stage_dir/job-config.json" | awk '{print $1}')"
  started_sha="$(sha256sum "$stage_dir/started-at-epoch.txt" | awk '{print $1}')"
  intent_sha="$(sha256sum "$stage_dir/launch-intent.json" | awk '{print $1}')"
  claim_sha="$(sha256sum "$stage_dir/launch-owner-claim.json" | awk '{print $1}')"
  recovery_claim_sha="$(sha256sum "$stage_dir/manual-recovery-owner-claim.json" | awk '{print $1}')"
  response_sha="$(sha256sum "$stage_dir/launch-output.txt" | awk '{print $1}')"
  response_status_sha="$(sha256sum "$stage_dir/launch-exit-status.txt" | awk '{print $1}')"
  execution_sha="$(sha256sum "$stage_dir/execution-name.txt" | awk '{print $1}')"
  terminal_sha="$(sha256sum "$stage_dir/terminal-execution.json" | awk '{print $1}')"
  elapsed_sha="$(sha256sum "$stage_dir/elapsed-seconds.txt" | awk '{print $1}')"
  lease_sha=""
  lease_object="null"
  fixed_outcome="null"
  if [[ "$stage" == "outcome" ]]; then
    [[ -n "$LEASE_RECEIPT_CANON" && -f "$LEASE_RECEIPT_CANON" ]] || \
      die "outcome recovery lacks its exact lease receipt"
    lease_sha="$(sha256sum "$LEASE_RECEIPT_CANON" | awk '{print $1}')"
    lease_object="$(jq -c '.object' "$LEASE_RECEIPT_CANON")"
    fixed_outcome="$(jq -cnS --arg run_id "$OUTCOME_RUN_ID" \
      --arg lease_sha "$lease_sha" --argjson lease_object "$lease_object" '
      {outcome_run_id:$run_id,lease_receipt_sha256:$lease_sha,
        historical_outcome_lease_object:$lease_object,
        same_deterministic_query_job_get_or_create_only:true,
        duplicate_query_licensed:false}
    ')"
  fi
  temp="$(mktemp)"
  jq -cnS --arg schema_version "core-v1-score-chain-manual-recovery/v1" \
    --arg stage "$stage" --argjson failed_attempt_ordinal "$attempt" \
    --arg failed_execution "$execution" --arg job "$JOB" --arg image "$IMAGE" \
    --arg service_account "$SERVICE_ACCOUNT" --arg gate "$gate" \
    --arg bash_command "$command" --arg config_sha "$config_sha" \
    --arg launch_sha "$launch_sha" --arg job_config_sha "$job_config_sha" \
    --arg started_sha "$started_sha" --arg intent_sha "$intent_sha" \
    --arg claim_sha "$claim_sha" \
    --arg recovery_claim_sha "$recovery_claim_sha" \
    --arg response_sha "$response_sha" --arg response_status_sha "$response_status_sha" \
    --arg execution_sha "$execution_sha" --arg terminal_sha "$terminal_sha" \
    --arg elapsed_sha "$elapsed_sha" --arg catalog_id "$CATALOG_ID" \
    --arg catalog_prefix "$CATALOG_OUTPUT_PREFIX" --arg outcome_run_id "$OUTCOME_RUN_ID" \
    --arg outcome_prefix "$OUTCOME_OUTPUT_PREFIX" --arg grade_run_id "$GRADE_RUN_ID" \
    --arg grade_prefix "$GRADE_OUTPUT_PREFIX" --argjson fixed_outcome "$fixed_outcome" '
    {schema_version:$schema_version,stage:$stage,
      failed_attempt_ordinal:$failed_attempt_ordinal,
      failed_execution:$failed_execution,job:$job,image:$image,
      service_account:$service_account,gate:$gate,bash_command:$bash_command,
      chain_config_sha256:$config_sha,launch_receipt_sha256:$launch_sha,
      job_config_sha256:$job_config_sha,started_at_epoch_sha256:$started_sha,
      launch_intent_sha256:$intent_sha,launch_output_sha256:$response_sha,
      launch_owner_claim_sha256:$claim_sha,
      manual_recovery_owner_claim_sha256:$recovery_claim_sha,
      launch_exit_status_sha256:$response_status_sha,
      execution_name_sha256:$execution_sha,terminal_execution_sha256:$terminal_sha,
      elapsed_seconds_sha256:$elapsed_sha,
      output_binding:{catalog_id:$catalog_id,catalog_output_prefix:$catalog_prefix,
        outcome_run_id:$outcome_run_id,outcome_output_prefix:$outcome_prefix,
        grade_run_id:$grade_run_id,grade_output_prefix:$grade_prefix},
      fixed_outcome_recovery:$fixed_outcome,explicit_manual_recovery:true,
      command_image_input_output_drift_licensed:false,
      blind_outcome_reinvocation_licensed:false,automatic_retry_licensed:false}
  ' >"$temp"
  install_local_equal "$temp" "$stage_dir/manual-recovery.json"
  rm -f -- "$temp"
}

validate_failed_attempt_archive() {
  local run_dir="$1" archive="$2" stage="$3" attempt="$4" gate="$5" command="$6"
  local file
  local -a expected=(
    elapsed-seconds.txt
    execution-name.txt
    job-config.json
    launch-exit-status.txt
    launch-intent.json
    launch-output.txt
    launch-owner-claim.json
    launch.json
    manual-recovery-owner-claim.json
    manual-recovery.json
    started-at-epoch.txt
    terminal-execution.json
  )
  local -a observed=()
  [[ -d "$archive" && ! -L "$archive" ]] || die "failed-stage archive is unsafe: $archive"
  [[ -f "$archive/manual-recovery.json" && ! -L "$archive/manual-recovery.json" ]] || \
    die "failed-stage archive lacks its manual recovery receipt"
  shopt -s dotglob nullglob
  observed=("$archive"/*)
  shopt -u dotglob nullglob
  [[ "${#observed[@]}" -eq "${#expected[@]}" ]] || \
    die "failed-stage archive inventory differs: $archive"
  for file in "${expected[@]}"; do
    [[ -f "$archive/$file" && ! -L "$archive/$file" ]] || \
      die "failed-stage archive inventory differs: $archive"
  done
  manual_recovery_receipt "$run_dir" "$archive" "$stage" "$attempt" "$gate" "$command"
}

failed_attempt_count() {
  local run_dir="$1" stage="$2" gate="$3" command="$4"
  local root="$run_dir/stages/failed-attempts/$stage" expected ordinal
  local -a entries=()
  [[ ! -L "$run_dir/stages/failed-attempts" && ! -L "$root" ]] || \
    die "failed-stage evidence path cannot be a symlink"
  if [[ ! -e "$root" ]]; then
    printf '0\n'
    return 0
  fi
  [[ -d "$root" && ! -L "$root" ]] || die "failed-stage evidence root is unsafe"
  shopt -s dotglob nullglob
  entries=("$root"/*)
  shopt -u dotglob nullglob
  for ((ordinal = 0; ordinal < ${#entries[@]}; ordinal += 1)); do
    printf -v expected '%s/attempt-%04d' "$root" "$ordinal"
    [[ "${entries[$ordinal]}" == "$expected" ]] || \
      die "failed-stage attempt archive sequence differs"
    validate_failed_attempt_archive \
      "$run_dir" "$expected" "$stage" "$ordinal" "$gate" "$command"
  done
  printf '%s\n' "${#entries[@]}"
}

archive_failed_stage() {
  local run_dir="$1" stage_dir="$2" stage="$3" attempt="$4" gate="$5" command="$6"
  local root="$run_dir/stages/failed-attempts/$stage" archive
  [[ ! -L "$run_dir/stages/failed-attempts" && ! -L "$root" ]] || \
    die "failed-stage evidence path cannot be a symlink"
  mkdir -p "$root"
  [[ -d "$root" && ! -L "$root" ]] || die "failed-stage evidence root is unsafe"
  printf -v archive '%s/attempt-%04d' "$root" "$attempt"
  [[ ! -e "$archive" && ! -L "$archive" ]] || die "failed-stage attempt archive already exists"
  [[ "$RECOVER_FAILED_STAGE" == "$stage" && -n "$STAGE_OPERATION_LOCK_FD" ]] || \
    die "failed-stage archive requires its explicit locked transaction"
  if [[ -e "$stage_dir/manual-recovery.json" || -L "$stage_dir/manual-recovery.json" ]]; then
    [[ -f "$stage_dir/manual-recovery-owner-claim.json" && \
       ! -L "$stage_dir/manual-recovery-owner-claim.json" ]] || \
      die "failed-stage recovery receipt lacks its exact owner claim"
  fi
  claim_failed_recovery_owner "$run_dir" "$stage_dir" "$stage" "$attempt"
  manual_recovery_receipt "$run_dir" "$stage_dir" "$stage" "$attempt" "$gate" "$command"
  validate_failed_attempt_archive \
    "$run_dir" "$stage_dir" "$stage" "$attempt" "$gate" "$command"
  mv -T -- "$stage_dir" "$archive"
  mkdir -p "$stage_dir"
  [[ -d "$stage_dir" && ! -L "$stage_dir" ]] || die "recovery stage directory differs"
  validate_failed_attempt_archive \
    "$run_dir" "$archive" "$stage" "$attempt" "$gate" "$command"
  printf 'CORE_V1_STAGE_FAILED_ATTEMPT_RETAINED %s attempt=%s execution=%s\n' \
    "$stage" "$attempt" "$(tr -d '\n' <"$archive/execution-name.txt")"
}

preflight_recovery_target() {
  local run_dir="$1" stage="$2" gate="$3" command="$4" stage_dir
  local archive_count closed_status file
  [[ "$RECOVER_FAILED_STAGE" == "$stage" ]] || return 0
  stage_dir="$run_dir/stages/$stage"
  [[ ! -L "$run_dir/stages" && ! -L "$stage_dir" ]] || \
    die "failed-stage recovery target path cannot be a symlink"
  mkdir -p "$stage_dir"
  archive_count="$(failed_attempt_count "$run_dir" "$stage" "$gate" "$command")"
  validate_nonnegative_int "$archive_count" "failed-stage recovery archive count"
  if validate_closed_stage \
    "$run_dir" "$stage_dir" "$stage" "$gate" "$command" "$archive_count"; then
    die "failed-stage recovery was requested for an already successful stage: $stage"
  else
    closed_status=$?
  fi
  if [[ "$closed_status" -eq 4 ]]; then
    return 0
  fi
  [[ "$closed_status" -eq 1 ]] || die "failed-stage recovery target differs"
  [[ "$archive_count" -gt 0 ]] || \
    die "failed-stage recovery requires one retained terminally failed attempt"
  for file in \
    execution-name.txt terminal-execution.json launch-intent.json \
    launch-owner-claim.json launch-output.txt launch-exit-status.txt; do
    [[ ! -e "$stage_dir/$file" && ! -L "$stage_dir/$file" ]] || \
      die "failed-stage recovery cannot replace an ambiguous or active launch"
  done
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

run_stage_locked() {
  local run_dir="$1" stage="$2" gate="$3" command="$4"
  local stage_dir="$run_dir/stages/$stage" execution started_epoch launch_output
  local closed_status archive_count launch_status recovery_authorized=0
  local recovery_binding_attempt=""
  [[ ! -L "$run_dir/stages" && ! -L "$stage_dir" ]] || \
    die "stage evidence directory cannot be a symlink"
  mkdir -p "$stage_dir"
  [[ -d "$stage_dir" && ! -L "$stage_dir" ]] || die "stage evidence directory differs"
  archive_count="$(failed_attempt_count "$run_dir" "$stage" "$gate" "$command")"
  validate_nonnegative_int "$archive_count" "failed-stage archive count"
  if validate_closed_stage \
    "$run_dir" "$stage_dir" "$stage" "$gate" "$command" "$archive_count"; then
    [[ "$RECOVER_FAILED_STAGE" != "$stage" ]] || \
      die "failed-stage recovery was requested for an already successful stage: $stage"
    printf 'CORE_V1_STAGE_RECOVERED %s %s\n' "$stage" "$(tr -d '\n' <"$stage_dir/execution-name.txt")"
    return 0
  else
    closed_status=$?
  fi
  if [[ "$closed_status" -eq 4 ]]; then
    [[ "$RECOVER_FAILED_STAGE" == "$stage" ]] || \
      die "terminally failed stage is retained; review it and rerun with --recover-failed-stage $stage"
    archive_failed_stage \
      "$run_dir" "$stage_dir" "$stage" "$archive_count" "$gate" "$command"
    archive_count=$((archive_count + 1))
    recovery_authorized=1
    RECOVERY_CONSUMED=1
  elif [[ "$closed_status" -ne 1 ]]; then
    die "retained stage state differs"
  elif [[ "$RECOVER_FAILED_STAGE" == "$stage" ]]; then
    [[ "$archive_count" -gt 0 ]] || \
      die "failed-stage recovery requires one retained terminally failed attempt"
    [[ ! -e "$stage_dir/execution-name.txt" && ! -L "$stage_dir/execution-name.txt" ]] || \
      die "failed-stage recovery cannot replace an execution that is not terminally failed"
    [[ ! -e "$stage_dir/launch-intent.json" && ! -L "$stage_dir/launch-intent.json" ]] || \
      die "failed-stage recovery cannot resolve an ambiguous prior launch"
    recovery_authorized=1
    RECOVERY_CONSUMED=1
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
    if [[ -e "$stage_dir/launch-intent.json" || -L "$stage_dir/launch-intent.json" || \
          -e "$stage_dir/launch-owner-claim.json" || -L "$stage_dir/launch-owner-claim.json" || \
          -e "$stage_dir/launch-output.txt" || -L "$stage_dir/launch-output.txt" || \
          -e "$stage_dir/launch-exit-status.txt" || -L "$stage_dir/launch-exit-status.txt" ]]; then
      die "prior Cloud Run launch is ambiguous; blind reinvocation is forbidden"
    fi
    if [[ "$archive_count" -gt 0 && "$recovery_authorized" -ne 1 ]]; then
      die "failed-stage retry remains unlicensed; rerun with --recover-failed-stage $stage"
    fi
    job_contract "$stage_dir"
    stage_launch_intent "$run_dir" "$stage_dir" "$stage" "$gate" "$command"
    if [[ "$archive_count" -gt 0 ]]; then
      [[ "$recovery_authorized" -eq 1 ]] || \
        die "replacement launch lacks explicit failed-stage recovery authorization"
      recovery_binding_attempt=$((archive_count - 1))
    fi
    claim_stage_launch_owner \
      "$run_dir" "$stage_dir" "$stage" "$recovery_binding_attempt"
    launch_output="$(mktemp)"
    if gcloud run jobs execute "$JOB" \
      --project "$PROJECT" --region "$REGION" \
      --args="-ceu,$command" --update-env-vars="$gate=1" \
      --async --quiet --format='value(metadata.name)' >"$launch_output"; then
      launch_status=0
    else
      launch_status=$?
    fi
    execution="$(tr -d '\r\n' <"$launch_output")"
    install_local_equal "$launch_output" "$stage_dir/launch-output.txt"
    write_local_equal "$stage_dir/launch-exit-status.txt" "$launch_status"
    rm -f -- "$launch_output"
    [[ "$launch_status" -eq 0 ]] || \
      die "Cloud Run launch response is ambiguous; blind reinvocation is forbidden"
    [[ "$execution" =~ ^[a-z0-9][a-z0-9-]{2,127}$ ]] || \
      die "Cloud Run launch response is ambiguous; blind reinvocation is forbidden"
    write_local_equal "$stage_dir/execution-name.txt" "$execution"
  fi
  [[ "$execution" =~ ^[a-z0-9][a-z0-9-]{2,127}$ ]] || die "Cloud Run execution name differs"
  wait_for_terminal "$stage_dir" "$execution" "$started_epoch" "$gate" "$command"
  validate_closed_stage \
    "$run_dir" "$stage_dir" "$stage" "$gate" "$command" "$archive_count" || \
    die "stage did not exact-replay its complete closed evidence envelope"
  printf 'CORE_V1_STAGE_CLOSED %s %s elapsed=%s\n' \
    "$stage" "$execution" "$(tr -d '\n' <"$stage_dir/elapsed-seconds.txt")"
}

run_stage() {
  local run_dir="$1" stage="$2" gate="$3" command="$4"
  acquire_stage_operation_lock "$run_dir" "$stage"
  preflight_recovery_target "$run_dir" "$stage" "$gate" "$command"
  run_stage_locked "$run_dir" "$stage" "$gate" "$command"
  release_stage_operation_lock
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
  if [[ -n "$RECOVER_FAILED_STAGE" && "$RECOVERY_CONSUMED" -ne 1 ]]; then
    die "requested failed-stage recovery was not consumed"
  fi
  printf 'CORE_V1_SCORE_CHAIN_CLOSED mode=%s run_dir=%s lease_release_external=%s\n' \
    "$MODE" "$run_dir" "$([[ "$MODE" == "outcome" || "$MODE" == "all" ]] && printf true || printf false)"
}

main "$@"
