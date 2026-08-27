#!/usr/bin/env bash
# Crash-safe launcher for the smoke-gated, one-query R6 full-union score chain.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: cloud_r6_full_union_score_chain_v1.sh <command>

Commands:
  preflight  Validate inputs and update one already-existing Cloud Run job.
  compile    Server-compile the exact outcome SQL without reading result rows.
  smoke      Run the outcome-blind actual-root smoke and retain its identities.
  supply     Acquire/resolve the lease and run exactly one fixed-ID query.
  recover-supply
             Recover one already-successful fixed-ID query after an exact
             terminal supply failure; query submission is impossible.
  grade      Canonically grade and publish 54 shards plus the root last.
  finish     Materialize strict evidence and generation-match release the lease.
  run        Execute compile, smoke, supply, grade, and finish in order.
  status     Report retained local stage evidence without launching work.
  help       Show this text without reading environment or accessing cloud.

Required environment for commands other than help:
  R6_SCORE_RUN_ID, R6_SCORE_JOB, R6_SCORE_CODE_SHA, R6_SCORE_IMAGE,
  R6_SCORE_SERVICE_ACCOUNT, R6_SCORE_RUN_DIR,
  R6_PANEL_FREEZE_URI, R6_PANEL_FREEZE_GENERATION,
  R6_PANEL_FREEZE_SHA256, R6_PANEL_FREEZE_BYTES, and the four
  R6_SNAPSHOT_{MODULE,CLI,TEST,CLI_TEST}_SHA256 values.

recover-supply additionally requires the fresh immutable repair runtime in
R6_SCORE_RECOVERY_CODE_SHA and R6_SCORE_RECOVERY_IMAGE. The ordinary
R6_SCORE_CODE_SHA and R6_SCORE_IMAGE remain the original smoke/lease identity.

The job must already exist. This launcher never creates a job, retries an
ambiguous execution, opens a second outcome query, mutates Neo4j/production,
or performs an IAM census.
EOF
}

COMMAND="${1:-help}"
if [[ "$COMMAND" == "help" || "$COMMAND" == "--help" || "$COMMAND" == "-h" ]]; then
  usage
  exit 0
fi
case "$COMMAND" in
  preflight|compile|smoke|supply|recover-supply|grade|finish|run|status) ;;
  *) usage >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

PROJECT="${R6_SCORE_PROJECT:-nfl-predictions-503414}"
REGION="${R6_SCORE_REGION:-us-central1}"
RUN_ID="${R6_SCORE_RUN_ID:?R6_SCORE_RUN_ID is required}"
JOB="${R6_SCORE_JOB:?R6_SCORE_JOB is required}"
SERVICE_ACCOUNT="${R6_SCORE_SERVICE_ACCOUNT:?R6_SCORE_SERVICE_ACCOUNT is required}"
CODE_SHA="${R6_SCORE_CODE_SHA:?R6_SCORE_CODE_SHA is required}"
IMAGE="${R6_SCORE_IMAGE:?R6_SCORE_IMAGE is required}"
RUN_DIR="${R6_SCORE_RUN_DIR:?R6_SCORE_RUN_DIR is required}"
PYTHON="${R6_SCORE_PYTHON:-python}"
PANEL_URI="${R6_PANEL_FREEZE_URI:?R6_PANEL_FREEZE_URI is required}"
PANEL_GENERATION="${R6_PANEL_FREEZE_GENERATION:?R6_PANEL_FREEZE_GENERATION is required}"
PANEL_SHA256="${R6_PANEL_FREEZE_SHA256:?R6_PANEL_FREEZE_SHA256 is required}"
PANEL_BYTES="${R6_PANEL_FREEZE_BYTES:?R6_PANEL_FREEZE_BYTES is required}"
SNAPSHOT_MODULE_SHA="${R6_SNAPSHOT_MODULE_SHA256:?R6_SNAPSHOT_MODULE_SHA256 is required}"
SNAPSHOT_CLI_SHA="${R6_SNAPSHOT_CLI_SHA256:?R6_SNAPSHOT_CLI_SHA256 is required}"
SNAPSHOT_TEST_SHA="${R6_SNAPSHOT_TEST_SHA256:?R6_SNAPSHOT_TEST_SHA256 is required}"
SNAPSHOT_CLI_TEST_SHA="${R6_SNAPSHOT_CLI_TEST_SHA256:?R6_SNAPSHOT_CLI_TEST_SHA256 is required}"

SUPPLY_PREFIX="gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-full-union-realized/$RUN_ID"
GRADE_PREFIX="gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-full-union-realized-grades/$RUN_ID"
LEASE_URI="gs://nfl-predictions-503414-raw/research-governance/historical-outcome-active-v1.json"
DEFAULT_COMPUTE_SERVICE_ACCOUNT="817589974517-compute@developer.gserviceaccount.com"
COMPILE_SQL_SHA256="03b5028dadbe4d92621103e2ccd6dcfe91e8e36fc351cf671f37e309951752cb"
RECOVERY_STAGE="supply-recovery-01"
RECOVERY_GATE="R6_FULL_UNION_OUTCOME_RECOVERY_ENABLED"
RECOVERY_PREFIX="$SUPPLY_PREFIX/recoveries/supply-attempt-01"
RECOVERY_INTENT_URI="$RECOVERY_PREFIX/recovery-intent.json"
RECOVERY_WORKER_COMPLETION_URI="$RECOVERY_PREFIX/worker-completion.json"
RECOVERY_RECEIPT_URI="$RECOVERY_PREFIX/recovery-receipt.json"
RECOVERY_CONTROLLER="scripts/recover_corpus_r6_full_union_outcome_supply_v1.py"
RECOVERY_RUNTIME_CONTROLLER="/opt/nfl-predictions/scripts/recover_corpus_r6_full_union_outcome_supply_v1.py"

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[[ "$PROJECT" == "nfl-predictions-503414" ]] || die "project differs"
[[ "$REGION" == "us-central1" ]] || die "region differs"
[[ "$RUN_ID" =~ ^[a-z0-9][a-z0-9-]{7,80}$ ]] || die "run ID differs"
[[ "$JOB" =~ ^[a-z0-9][a-z0-9-]{2,62}$ ]] || die "job differs"
if [[ "$SERVICE_ACCOUNT" != "$DEFAULT_COMPUTE_SERVICE_ACCOUNT" \
      && ! "$SERVICE_ACCOUNT" =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]@nfl-predictions-503414\.iam\.gserviceaccount\.com$ ]]; then
  die "service account differs"
fi
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "code SHA differs"
[[ "$IMAGE" =~ @sha256:[0-9a-f]{64}$ ]] || die "image must be immutable"
[[ "$PANEL_URI" =~ ^gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-full-union-freezes/[a-z0-9][a-z0-9-]{7,80}/panel-freeze\.json$ ]] || die "panel URI differs"
[[ "$PANEL_GENERATION" =~ ^[1-9][0-9]*$ ]] || die "panel generation differs"
[[ "$PANEL_SHA256" =~ ^[0-9a-f]{64}$ ]] || die "panel SHA differs"
[[ "$PANEL_BYTES" =~ ^[1-9][0-9]*$ ]] || die "panel bytes differ"
for digest in "$SNAPSHOT_MODULE_SHA" "$SNAPSHOT_CLI_SHA" "$SNAPSHOT_TEST_SHA" "$SNAPSHOT_CLI_TEST_SHA"; do
  [[ "$digest" =~ ^[0-9a-f]{64}$ ]] || die "snapshot code identity differs"
done
mkdir -p "$RUN_DIR/stages" "$RUN_DIR/objects"

WRITE_EQUAL_CREATED=false
write_equal() {
  local target="$1" value="$2" temp
  WRITE_EQUAL_CREATED=false
  if [[ -e "$target" || -L "$target" ]]; then
    [[ -f "$target" && ! -L "$target" ]] || die "unsafe retained file: $target"
    [[ "$(cat "$target")" == "$value" ]] || die "retained file differs: $target"
    return
  fi
  temp="$(mktemp "$(dirname "$target")/.r6-write.XXXXXX")"
  printf '%s\n' "$value" >"$temp"
  chmod 0600 "$temp"
  if ln "$temp" "$target" 2>/dev/null; then
    WRITE_EQUAL_CREATED=true
  else
    [[ -f "$target" && ! -L "$target" ]] && cmp -s "$temp" "$target" || {
      rm -f -- "$temp"
      die "create/equal race differs: $target"
    }
  fi
  rm -f -- "$temp"
}

identity_arg() {
  local file="$1" prefix="$2"
  [[ -f "$file" && ! -L "$file" ]] || die "identity receipt is absent: $file"
  jq -e 'setpath([];.) | keys == ["bytes","generation","sha256","uri"]' "$file" >/dev/null || die "identity receipt fields differ"
  printf -- '--%s-uri=%s\n' "$prefix" "$(jq -r .uri "$file")"
  printf -- '--%s-generation=%s\n' "$prefix" "$(jq -r .generation "$file")"
  printf -- '--%s-sha256=%s\n' "$prefix" "$(jq -r .sha256 "$file")"
  printf -- '--%s-bytes=%s\n' "$prefix" "$(jq -r .bytes "$file")"
}

validate_identity_receipt() {
  local file="$1" expected_uri="$2" label="$3"
  [[ -f "$file" && ! -L "$file" ]] || die "$label identity is absent"
  jq -e --arg uri "$expected_uri" '
    keys == ["bytes","generation","sha256","uri"]
      and .uri == $uri
      and (.generation | type == "string" and test("^[1-9][0-9]*$"))
      and (.sha256 | type == "string" and test("^[0-9a-f]{64}$"))
      and (.bytes | type == "number" and . > 0 and floor == .)
  ' "$file" >/dev/null || die "$label identity fields differ"
}

identity_from_recovery_cli_summary() {
  local raw="$1" expected_status="$2" expected_uri="$3" label="$4"
  jq -ceS --arg status "$expected_status" --arg uri "$expected_uri" \
    --arg run "$RUN_ID" --arg job "$JOB" '
    select(keys == ([
      "automatic_retry_licensed","cloud_run_job","decision_authority",
      "job_submission_count","new_job_count","object_identity",
      "outcome_rows_in_stdout","run_id","schema_version","status"
    ] | sort))
    | select(.schema_version == "r6-full-union-outcome-supply-recovery-cli/v1")
    | select(.run_id == $run and .cloud_run_job == $job)
    | select(.status == $status and .outcome_rows_in_stdout == false)
    | select(.job_submission_count == 0 and .new_job_count == 0)
    | select(.automatic_retry_licensed == false and .decision_authority == false)
    | select(.object_identity.uri == $uri)
    | .object_identity
  ' <<<"$raw" || die "$label CLI receipt differs"
}

load_recovery_runtime() {
  RECOVERY_CODE_SHA="${R6_SCORE_RECOVERY_CODE_SHA:?R6_SCORE_RECOVERY_CODE_SHA is required}"
  RECOVERY_IMAGE="${R6_SCORE_RECOVERY_IMAGE:?R6_SCORE_RECOVERY_IMAGE is required}"
  [[ "$RECOVERY_CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "recovery code SHA differs"
  [[ "$RECOVERY_IMAGE" =~ @sha256:[0-9a-f]{64}$ ]] || die "recovery image must be immutable"
  [[ "$RECOVERY_CODE_SHA" != "$CODE_SHA" ]] || die "recovery code must differ from original code"
  [[ "$RECOVERY_IMAGE" != "$IMAGE" ]] || die "recovery image must differ from original image"
  [[ -f "$RECOVERY_CONTROLLER" && ! -L "$RECOVERY_CONTROLLER" ]] || die "recovery controller is absent"
}

resolve_object() {
  local uri="$1" target="$2" payload_target="${3:-}" describe generation size exact_uri raw temp current
  describe="$(mktemp)"; raw="$(mktemp)"; temp="$(mktemp)"
  gcloud storage objects describe "$uri" --project "$PROJECT" --format=json >"$describe"
  generation="$(jq -r '.generation // empty' "$describe")"
  size="$(jq -r '.size // empty' "$describe")"
  [[ "$generation" =~ ^[1-9][0-9]*$ && "$size" =~ ^[1-9][0-9]*$ ]] || {
    rm -f -- "$describe" "$raw" "$temp"; die "known object metadata differs: $uri";
  }
  exact_uri="${uri}#${generation}"
  gcloud storage cat "$exact_uri" --project "$PROJECT" >"$raw"
  [[ "$(wc -c <"$raw" | tr -d ' ')" == "$size" ]] || {
    rm -f -- "$describe" "$raw" "$temp"; die "known object bytes differ: $uri";
  }
  current="$(gcloud storage objects describe "$uri" --project "$PROJECT" --format='value(generation)')"
  [[ "$current" == "$generation" ]] || {
    rm -f -- "$describe" "$raw" "$temp"; die "known object changed during resolution: $uri";
  }
  jq -cnS --arg uri "$uri" --arg generation "$generation" \
    --arg sha256 "$(sha256sum "$raw" | awk '{print $1}')" --argjson bytes "$size" \
    '{uri:$uri,generation:$generation,sha256:$sha256,bytes:$bytes}' >"$temp"
  write_equal "$target" "$(cat "$temp")"
  if [[ -n "$payload_target" ]]; then
    write_equal "$payload_target" "$(cat "$raw")"
  fi
  rm -f -- "$describe" "$raw" "$temp"
}

panel_args=()
panel_args+=("--panel-freeze-uri=$PANEL_URI" "--panel-freeze-generation=$PANEL_GENERATION")
panel_args+=("--panel-freeze-sha256=$PANEL_SHA256" "--panel-freeze-bytes=$PANEL_BYTES")
smoke_args=(/opt/nfl-predictions/scripts/run_corpus_r6_full_union_outcome_supply_v1.py smoke --execute "--project=$PROJECT" "--run-id=$RUN_ID" "--job=$JOB" "--code-sha=$CODE_SHA" "--image=$IMAGE")
smoke_args+=("${panel_args[@]}")
smoke_args+=("--snapshot-module-sha256=$SNAPSHOT_MODULE_SHA" "--snapshot-cli-sha256=$SNAPSHOT_CLI_SHA" "--snapshot-test-sha256=$SNAPSHOT_TEST_SHA" "--snapshot-cli-test-sha256=$SNAPSHOT_CLI_TEST_SHA")
compile_args=(/opt/nfl-predictions/scripts/compile_corpus_r6_full_union_query_v1.py --execute "--project=$PROJECT" --location=US "--code-sha=$CODE_SHA" "--image=$IMAGE" --receipt=/tmp/r6-query-compile-receipt.json "--receipt-uri=$SUPPLY_PREFIX/query-compile-receipt.json")

preflight() {
  local after="$RUN_DIR/job-config.json" temp
  temp="$(mktemp)"
  gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" --format=json >"$temp" || {
    rm -f -- "$temp"; die "registered Cloud Run job does not already exist";
  }
  rm -f -- "$temp"
  # Update one registered job only. There is intentionally no deploy/create path.
  gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
    --image "$IMAGE" --command python --args="" \
    --clear-env-vars --clear-secrets \
    --clear-volume-mounts --clear-volumes \
    --clear-cloudsql-instances --clear-vpc-connector \
    --clear-network \
    --service-account "$SERVICE_ACCOUNT" \
    --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 8h \
    --cpu 8 --memory 32Gi --quiet >/dev/null
  temp="$(mktemp)"
  gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" --format=json >"$temp"
  jq -e --arg job "$JOB" --arg image "$IMAGE" \
    --arg service_account "$SERVICE_ACCOUNT" '
    .spec.template.spec as $outer
    | $outer.template.spec as $task
    | $task.containers as $containers
    | ((.metadata.name | split("/")[-1]) == $job)
      and $outer.taskCount == 1
      and $outer.parallelism == 1
      and $task.maxRetries == 0
      and (($task.timeoutSeconds | tostring) == "28800")
      and ($containers | length) == 1
      and $containers[0].image == $image
      and $containers[0].command == ["python"]
      and (($containers[0].args // []) == [])
      and (($containers[0].env // []) == [])
      and (($containers[0].volumeMounts // []) == [])
      and (($task.volumes // []) == [])
      and (($task.vpcAccess // {}) == {})
      and $task.serviceAccountName == $service_account
      and $containers[0].resources.limits == {cpu:"8",memory:"32Gi"}
  ' "$temp" >/dev/null || { rm -f -- "$temp"; die "registered job contract differs"; }
  write_equal "$after" "$(jq -cS --arg job "$JOB" --arg image "$IMAGE" \
    --arg service_account "$SERVICE_ACCOUNT" '
    .spec.template.spec as $outer
    | $outer.template.spec as $task
    | $task.containers[0] as $container
    | {schema_version:"r6-full-union-isolated-job-contract/v1",
       job:$job,image:$container.image,command:$container.command,
       args:($container.args // []),env:($container.env // []),
       volume_mounts:($container.volumeMounts // []),
       resources:$container.resources.limits,
       task_count:$outer.taskCount,parallelism:$outer.parallelism,
       max_retries:$task.maxRetries,timeout_seconds:($task.timeoutSeconds|tostring),
       service_account:$task.serviceAccountName,volumes:($task.volumes // []),
       vpc_access:($task.vpcAccess // {}),
       expected_image:$image,expected_service_account:$service_account,
       inherited_runtime_state_cleared:true}
  ' "$temp")"
  rm -f -- "$temp"
}

preflight_recovery() {
  local after="$RUN_DIR/job-config-recovery.json" temp
  temp="$(mktemp)"
  gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" --format=json >"$temp" || {
    rm -f -- "$temp"; die "registered Cloud Run job does not already exist";
  }
  rm -f -- "$temp"
  # This isolated mutation installs only the reviewed repair image. The
  # original create/equal job-config.json remains untouched and is restored
  # before recover-supply returns, including through the EXIT trap.
  gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
    --image "$RECOVERY_IMAGE" --command python --args="" \
    --clear-env-vars --clear-secrets \
    --clear-volume-mounts --clear-volumes \
    --clear-cloudsql-instances --clear-vpc-connector \
    --clear-network \
    --service-account "$SERVICE_ACCOUNT" \
    --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 8h \
    --cpu 8 --memory 32Gi --quiet >/dev/null
  temp="$(mktemp)"
  gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" --format=json >"$temp"
  jq -e --arg job "$JOB" --arg image "$RECOVERY_IMAGE" \
    --arg service_account "$SERVICE_ACCOUNT" '
    .spec.template.spec as $outer
    | $outer.template.spec as $task
    | $task.containers as $containers
    | ((.metadata.name | split("/")[-1]) == $job)
      and $outer.taskCount == 1
      and $outer.parallelism == 1
      and $task.maxRetries == 0
      and (($task.timeoutSeconds | tostring) == "28800")
      and ($containers | length) == 1
      and $containers[0].image == $image
      and $containers[0].command == ["python"]
      and (($containers[0].args // []) == [])
      and (($containers[0].env // []) == [])
      and (($containers[0].volumeMounts // []) == [])
      and (($task.volumes // []) == [])
      and (($task.vpcAccess // {}) == {})
      and $task.serviceAccountName == $service_account
      and $containers[0].resources.limits == {cpu:"8",memory:"32Gi"}
  ' "$temp" >/dev/null || { rm -f -- "$temp"; die "registered recovery job contract differs"; }
  write_equal "$after" "$(jq -cS --arg job "$JOB" --arg image "$RECOVERY_IMAGE" \
    --arg original_code "$CODE_SHA" --arg original_image "$IMAGE" \
    --arg recovery_code "$RECOVERY_CODE_SHA" \
    --arg service_account "$SERVICE_ACCOUNT" '
    .spec.template.spec as $outer
    | $outer.template.spec as $task
    | $task.containers[0] as $container
    | {schema_version:"r6-full-union-isolated-recovery-job-contract/v1",
       job:$job,image:$container.image,command:$container.command,
       args:($container.args // []),env:($container.env // []),
       volume_mounts:($container.volumeMounts // []),
       resources:$container.resources.limits,
       task_count:$outer.taskCount,parallelism:$outer.parallelism,
       max_retries:$task.maxRetries,timeout_seconds:($task.timeoutSeconds|tostring),
       service_account:$task.serviceAccountName,volumes:($task.volumes // []),
       vpc_access:($task.vpcAccess // {}),
       original_code_sha:$original_code,original_image:$original_image,
       recovery_code_sha:$recovery_code,recovery_image:$image,
       expected_service_account:$service_account,
       inherited_runtime_state_cleared:true,
       query_submission_licensed:false,
       ordinary_supply_relaunch_licensed:false}
  ' "$temp")"
  rm -f -- "$temp"
}

stage_token() {
  local stage="$1" gate="$2" compile_binding; shift 2
  compile_binding="$(compile_binding_json "$stage")"
  {
    printf '%s\0' "$PROJECT" "$REGION" "$RUN_ID" "$JOB" "$stage" "$gate" \
      "$CODE_SHA" "$IMAGE" "$SERVICE_ACCOUNT" "$compile_binding"
    printf '%s\0' "$@"
  } | sha256sum | awk '{print $1}'
}

stage_env_json() {
  local gate="$1" token="$2"
  jq -cnS --arg gate "$gate" --arg token "$token" --arg code "$CODE_SHA" \
    --arg image "$IMAGE" '
    [{name:$gate,value:"1"},
     {name:"R6_CHAIN_STAGE_TOKEN",value:$token},
     {name:"R6_FULL_UNION_REVIEWED_CODE_SHA",value:$code},
     {name:"R6_FULL_UNION_RUNTIME_IMAGE",value:$image}] | sort_by(.name)
  '
}

recover_execution() {
  local stage="$1" token="$2" gate="$3"; shift 3
  local inventory candidate candidate_name argv_json env_json matches=()
  argv_json="$(printf '%s\n' "$@" | jq -Rsc 'split("\n")[:-1]')"
  env_json="$(stage_env_json "$gate" "$token")"
  inventory="$(mktemp)"
  if ! gcloud run jobs executions list --job "$JOB" \
    --project "$PROJECT" --region "$REGION" \
    --format=json >"$inventory"; then
    rm -f -- "$inventory"
    die "recovery execution inventory failed"
  fi
  jq -e 'type == "array"' "$inventory" >/dev/null || {
    rm -f -- "$inventory"
    die "recovery execution inventory shape differs"
  }
  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    candidate_name="$(jq -r '.metadata.name | split("/")[-1]' <<<"$candidate")"
    [[ "$candidate_name" =~ ^[a-z0-9][a-z0-9-]{2,127}$ ]] || {
      rm -f -- "$inventory"
      die "recovery execution inventory name differs"
    }
    if jq -e --arg token "$token" --arg image "$IMAGE" --arg job "$JOB" \
      --arg service_account "$SERVICE_ACCOUNT" \
      --argjson argv "$argv_json" --argjson expected_env "$env_json" '
      .spec.template.spec.containers as $containers
      | .metadata.labels["run.googleapis.com/job"] == $job
        and .spec.taskCount == 1 and .spec.parallelism == 1
        and .spec.template.spec.maxRetries == 0
        and ((.spec.template.spec.timeoutSeconds | tostring) == "28800")
        and ($containers | length) == 1
        and $containers[0].image == $image
        and $containers[0].command == ["python"]
        and $containers[0].args == $argv
        and ([($containers[0].env // [])[] | {name,value}] | sort_by(.name))
          == $expected_env
        and (($containers[0].volumeMounts // []) == [])
        and ((.spec.template.spec.volumes // []) == [])
        and ((.spec.template.spec.vpcAccess // {}) == {})
        and .spec.template.spec.serviceAccountName == $service_account
        and $containers[0].resources.limits == {cpu:"8",memory:"32Gi"}
    ' <<<"$candidate" >/dev/null; then
      matches+=("$candidate_name")
    fi
  done < <(jq -c '.[]' "$inventory")
  rm -f -- "$inventory"
  [[ "${#matches[@]}" -le 1 ]] || die "execution-name recovery is ambiguous for $stage"
  if [[ "${#matches[@]}" -eq 1 ]]; then
    printf '%s\n' "${matches[0]}"
  fi
  return 0
}

wait_terminal() {
  local execution="$1" target="$2" token="$3" gate="$4"; shift 4
  local temp state started now argv_json env_json
  argv_json="$(printf '%s\n' "$@" | jq -Rsc 'split("\n")[:-1]')"
  env_json="$(stage_env_json "$gate" "$token")"
  started="$(date +%s)"
  while true; do
    temp="$(mktemp)"
    gcloud run jobs executions describe "$execution" --project "$PROJECT" --region "$REGION" --format=json >"$temp"
    state="$(jq -r '[.status.conditions[]? | select(.type=="Completed") | .status] | if length==1 then .[0] else "" end' "$temp")"
    if [[ "$state" == "True" || "$state" == "False" ]]; then
      write_equal "$target" "$(jq -cS . "$temp")"
      rm -f -- "$temp"
      [[ "$state" == "True" ]] || die "Cloud Run execution failed: $execution"
      jq -e --arg execution "$execution" --arg project "$PROJECT" \
        --arg region "$REGION" --arg job "$JOB" '
        (.metadata.name == $execution)
          or (.metadata.name == (
            "projects/" + $project + "/locations/" + $region
            + "/jobs/" + $job + "/executions/" + $execution
          ))
      ' "$target" >/dev/null || die "terminal execution name differs"
      jq -e --arg image "$IMAGE" --arg token "$token" --arg job "$JOB" \
        --arg service_account "$SERVICE_ACCOUNT" \
        --argjson argv "$argv_json" --argjson expected_env "$env_json" '
        .spec.template.spec.containers as $containers
        | .metadata.labels["run.googleapis.com/job"] == $job
        and .spec.taskCount == 1 and .spec.parallelism == 1
        and .spec.template.spec.maxRetries == 0
        and ((.spec.template.spec.timeoutSeconds | tostring) == "28800")
        and ($containers | length) == 1
        and $containers[0].image == $image
        and $containers[0].command == ["python"]
        and $containers[0].args == $argv
        and ([$containers[0].env[]? | {name,value}]
          | sort_by(.name)) == $expected_env
        and (($containers[0].volumeMounts // []) == [])
        and ((.spec.template.spec.volumes // []) == [])
        and ((.spec.template.spec.vpcAccess // {}) == {})
        and .spec.template.spec.serviceAccountName == $service_account
        and $containers[0].resources.limits == {cpu:"8",memory:"32Gi"}
        and .status.succeededCount == 1
        and ((.status.failedCount // 0) == 0)
        and ((.status.runningCount // 0) == 0)
        and (.status.completionTime | type == "string")
      ' "$target" >/dev/null || die "terminal execution envelope differs"
      return
    fi
    rm -f -- "$temp"
    now="$(date +%s)"; (( now - started < 32400 )) || die "execution timeout: $execution"
    sleep 20
  done
}

launch_stage() {
  local stage="$1" gate="$2"; shift 2
  local stage_dir="$RUN_DIR/stages/$stage" token intent execution output status joined recovered argv_json argv_sha env_json compile_binding intent_preexisted=false arg
  local args=("$@")
  mkdir -p "$stage_dir"
  for arg in "${args[@]}"; do
    [[ "$arg" != *,* ]] || die "remote CLI argument contains a comma"
  done
  argv_json="$(printf '%s\n' "${args[@]}" | jq -Rsc 'split("\n")[:-1]')"
  argv_sha="$({ printf '%s\0' "${args[@]}"; } | sha256sum | awk '{print $1}')"
  token="$(stage_token "$stage" "$gate" "${args[@]}")"
  env_json="$(stage_env_json "$gate" "$token")"
  compile_binding="$(compile_binding_json "$stage")"
  intent="$(jq -cnS --arg stage "$stage" --arg token "$token" --arg run "$RUN_ID" \
    --arg project "$PROJECT" --arg region "$REGION" --arg job "$JOB" \
    --arg code "$CODE_SHA" --arg image "$IMAGE" \
    --arg service_account "$SERVICE_ACCOUNT" --arg gate "$gate" \
    --arg argv_sha "$argv_sha" --argjson argv "$argv_json" \
    --argjson env "$env_json" --argjson compile_binding "$compile_binding" \
    '{schema_version:"r6-full-union-stage-launch-intent/v1",stage:$stage,
      token:$token,project:$project,region:$region,run_id:$run,job:$job,
      code_sha:$code,image:$image,
      service_account:$service_account,gate:$gate,argv:$argv,
      argv_sha256:$argv_sha,execution_env:$env,
      query_compile_receipt:$compile_binding,
      all_panel_snapshot_upstream_identities_bound_in_argv:true,
      automatic_retry_licensed:false}')"
  write_equal "$stage_dir/launch-intent.json" "$intent"
  [[ "$WRITE_EQUAL_CREATED" == true ]] || intent_preexisted=true
  if [[ -e "$stage_dir/execution-name.txt" || -L "$stage_dir/execution-name.txt" ]]; then
    [[ -f "$stage_dir/execution-name.txt" && ! -L "$stage_dir/execution-name.txt" ]] || die "unsafe execution-name claim"
    execution="$(tr -d '\n' <"$stage_dir/execution-name.txt")"
  elif [[ "$intent_preexisted" == true ]]; then
    recovered="$(recover_execution "$stage" "$token" "$gate" "${args[@]}")"
    [[ -n "$recovered" ]] || die "prior launch remains ambiguous; blind relaunch is forbidden"
    execution="$recovered"
    write_equal "$stage_dir/execution-name.txt" "$execution"
  else
    joined="$(IFS=,; printf '%s' "${args[*]}")"
    output="$(mktemp)"
    set +e
    gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
      --args="$joined" \
      --update-env-vars="R6_CHAIN_STAGE_TOKEN=$token,$gate=1,R6_FULL_UNION_REVIEWED_CODE_SHA=$CODE_SHA,R6_FULL_UNION_RUNTIME_IMAGE=$IMAGE" \
      --async --quiet --format='value(metadata.name)' >"$output"
    status=$?
    set -e
    write_equal "$stage_dir/launch-output.txt" "$(tr -d '\r\n' <"$output")"
    write_equal "$stage_dir/launch-exit-status.txt" "$status"
    execution="$(tr -d '\r\n' <"$output")"
    rm -f -- "$output"
    [[ "$status" -eq 0 && "$execution" =~ ^[a-z0-9][a-z0-9-]{2,127}$ ]] || die "launch response is ambiguous; rerun only for exact recovery"
    write_equal "$stage_dir/execution-name.txt" "$execution"
  fi
  [[ "$execution" =~ ^[a-z0-9][a-z0-9-]{2,127}$ ]] || die "execution-name claim differs"
  wait_terminal "$execution" "$stage_dir/terminal-execution.json" "$token" "$gate" "${args[@]}"
  write_equal "$stage_dir/terminal-receipt.json" "$(jq -cnS --arg stage "$stage" --arg execution "$execution" --arg sha "$(sha256sum "$stage_dir/terminal-execution.json" | awk '{print $1}')" '{stage:$stage,execution:$execution,terminal_execution_sha256:$sha,complete:true}')"
}

recovery_env_json() {
  local token="$1"
  jq -cnS --arg gate "$RECOVERY_GATE" --arg token "$token" \
    --arg code "$RECOVERY_CODE_SHA" --arg image "$RECOVERY_IMAGE" '
    [{name:$gate,value:"1"},
     {name:"R6_RECOVERY_STAGE_TOKEN",value:$token},
     {name:"R6_FULL_UNION_RECOVERY_CODE_SHA",value:$code},
     {name:"R6_FULL_UNION_RECOVERY_RUNTIME_IMAGE",value:$image}]
    | sort_by(.name)
  '
}

recovery_stage_token() {
  local intent_file="$1" compile_binding intent_binding; shift
  compile_binding="$(compile_binding_json "$RECOVERY_STAGE")"
  intent_binding="$(jq -cS . "$intent_file")"
  {
    printf '%s\0' "$PROJECT" "$REGION" "$RUN_ID" "$JOB" \
      "$RECOVERY_STAGE" "$RECOVERY_GATE" "$CODE_SHA" "$IMAGE" \
      "$RECOVERY_CODE_SHA" "$RECOVERY_IMAGE" "$SERVICE_ACCOUNT" \
      "$compile_binding" "$intent_binding"
    printf '%s\0' "$@"
  } | sha256sum | awk '{print $1}'
}

recover_recovery_execution() {
  local token="$1"; shift
  local inventory candidate candidate_name argv_json env_json matches=()
  argv_json="$(printf '%s\n' "$@" | jq -Rsc 'split("\n")[:-1]')"
  env_json="$(recovery_env_json "$token")"
  inventory="$(mktemp)"
  if ! gcloud run jobs executions list --job "$JOB" \
    --project "$PROJECT" --region "$REGION" \
    --format=json >"$inventory"; then
    rm -f -- "$inventory"
    die "recovery execution inventory failed"
  fi
  jq -e 'type == "array"' "$inventory" >/dev/null || {
    rm -f -- "$inventory"
    die "recovery execution inventory shape differs"
  }
  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    candidate_name="$(jq -r '.metadata.name | split("/")[-1]' <<<"$candidate")"
    [[ "$candidate_name" =~ ^[a-z0-9][a-z0-9-]{2,127}$ ]] || {
      rm -f -- "$inventory"
      die "recovery execution inventory name differs"
    }
    if jq -e --arg image "$RECOVERY_IMAGE" --arg job "$JOB" \
      --arg service_account "$SERVICE_ACCOUNT" \
      --argjson argv "$argv_json" --argjson expected_env "$env_json" '
      .spec.template.spec.containers as $containers
      | .metadata.labels["run.googleapis.com/job"] == $job
        and .spec.taskCount == 1 and .spec.parallelism == 1
        and .spec.template.spec.maxRetries == 0
        and ((.spec.template.spec.timeoutSeconds | tostring) == "28800")
        and ($containers | length) == 1
        and $containers[0].image == $image
        and $containers[0].command == ["python"]
        and $containers[0].args == $argv
        and ([($containers[0].env // [])[] | {name,value}] | sort_by(.name))
          == $expected_env
        and (($containers[0].volumeMounts // []) == [])
        and ((.spec.template.spec.volumes // []) == [])
        and ((.spec.template.spec.vpcAccess // {}) == {})
        and .spec.template.spec.serviceAccountName == $service_account
        and $containers[0].resources.limits == {cpu:"8",memory:"32Gi"}
    ' <<<"$candidate" >/dev/null; then
      matches+=("$candidate_name")
    fi
  done < <(jq -c '.[]' "$inventory")
  rm -f -- "$inventory"
  [[ "${#matches[@]}" -le 1 ]] || die "execution-name recovery is ambiguous for $RECOVERY_STAGE"
  if [[ "${#matches[@]}" -eq 1 ]]; then
    printf '%s\n' "${matches[0]}"
  fi
  return 0
}

wait_recovery_terminal() {
  local execution="$1" target="$2" token="$3"; shift 3
  local temp state started now argv_json env_json
  argv_json="$(printf '%s\n' "$@" | jq -Rsc 'split("\n")[:-1]')"
  env_json="$(recovery_env_json "$token")"
  started="$(date +%s)"
  while true; do
    temp="$(mktemp)"
    gcloud run jobs executions describe "$execution" --project "$PROJECT" --region "$REGION" --format=json >"$temp"
    state="$(jq -r '[.status.conditions[]? | select(.type=="Completed") | .status] | if length==1 then .[0] else "" end' "$temp")"
    if [[ "$state" == "True" || "$state" == "False" ]]; then
      write_equal "$target" "$(jq -cS . "$temp")"
      rm -f -- "$temp"
      [[ "$state" == "True" ]] || die "Cloud Run recovery execution failed: $execution"
      jq -e --arg execution "$execution" --arg project "$PROJECT" \
        --arg region "$REGION" --arg job "$JOB" '
        (.metadata.name == $execution)
          or (.metadata.name == (
            "projects/" + $project + "/locations/" + $region
            + "/jobs/" + $job + "/executions/" + $execution
          ))
      ' "$target" >/dev/null || die "recovery terminal execution name differs"
      jq -e --arg image "$RECOVERY_IMAGE" --arg job "$JOB" \
        --arg service_account "$SERVICE_ACCOUNT" \
        --argjson argv "$argv_json" --argjson expected_env "$env_json" '
        .spec.template.spec.containers as $containers
        | .metadata.labels["run.googleapis.com/job"] == $job
          and .spec.taskCount == 1 and .spec.parallelism == 1
          and .spec.template.spec.maxRetries == 0
          and ((.spec.template.spec.timeoutSeconds | tostring) == "28800")
          and ($containers | length) == 1
          and $containers[0].image == $image
          and $containers[0].command == ["python"]
          and $containers[0].args == $argv
          and ([($containers[0].env // [])[] | {name,value}]
            | sort_by(.name)) == $expected_env
          and (($containers[0].volumeMounts // []) == [])
          and ((.spec.template.spec.volumes // []) == [])
          and ((.spec.template.spec.vpcAccess // {}) == {})
          and .spec.template.spec.serviceAccountName == $service_account
          and $containers[0].resources.limits == {cpu:"8",memory:"32Gi"}
          and .status.succeededCount == 1
          and ((.status.failedCount // 0) == 0)
          and ((.status.runningCount // 0) == 0)
          and (.status.completionTime | type == "string")
      ' "$target" >/dev/null || die "recovery terminal execution envelope differs"
      return
    fi
    rm -f -- "$temp"
    now="$(date +%s)"; (( now - started < 32400 )) || die "recovery execution timeout: $execution"
    sleep 20
  done
}

launch_recovery_stage() {
  local intent_file="$1"; shift
  local stage_dir="$RUN_DIR/stages/$RECOVERY_STAGE" token launch_intent execution output status joined recovered argv_json argv_sha env_json compile_binding semantic_intent intent_preexisted=false arg
  local args=("$@")
  mkdir -p "$stage_dir"
  for arg in "${args[@]}"; do
    [[ "$arg" != *,* ]] || die "recovery CLI argument contains a comma"
  done
  argv_json="$(printf '%s\n' "${args[@]}" | jq -Rsc 'split("\n")[:-1]')"
  argv_sha="$({ printf '%s\0' "${args[@]}"; } | sha256sum | awk '{print $1}')"
  token="$(recovery_stage_token "$intent_file" "${args[@]}")"
  env_json="$(recovery_env_json "$token")"
  compile_binding="$(compile_binding_json "$RECOVERY_STAGE")"
  semantic_intent="$(jq -cS . "$intent_file")"
  launch_intent="$(jq -cnS --arg stage "$RECOVERY_STAGE" --arg token "$token" \
    --arg run "$RUN_ID" --arg project "$PROJECT" --arg region "$REGION" \
    --arg job "$JOB" --arg original_code "$CODE_SHA" \
    --arg original_image "$IMAGE" --arg recovery_code "$RECOVERY_CODE_SHA" \
    --arg recovery_image "$RECOVERY_IMAGE" \
    --arg service_account "$SERVICE_ACCOUNT" --arg gate "$RECOVERY_GATE" \
    --arg argv_sha "$argv_sha" --argjson argv "$argv_json" \
    --argjson env "$env_json" --argjson compile_binding "$compile_binding" \
    --argjson semantic_intent "$semantic_intent" '
    {schema_version:"r6-full-union-recovery-stage-launch-intent/v1",
     stage:$stage,token:$token,project:$project,region:$region,run_id:$run,
     job:$job,original_code_sha:$original_code,original_image:$original_image,
     recovery_code_sha:$recovery_code,recovery_image:$recovery_image,
     service_account:$service_account,gate:$gate,argv:$argv,
     argv_sha256:$argv_sha,execution_env:$env,
     query_compile_receipt:$compile_binding,recovery_intent:$semantic_intent,
     fixed_job_lookup_only:true,query_submission_licensed:false,
     ordinary_supply_relaunch_licensed:false,automatic_retry_licensed:false}')"
  write_equal "$stage_dir/launch-intent.json" "$launch_intent"
  [[ "$WRITE_EQUAL_CREATED" == true ]] || intent_preexisted=true
  if [[ -e "$stage_dir/execution-name.txt" || -L "$stage_dir/execution-name.txt" ]]; then
    [[ -f "$stage_dir/execution-name.txt" && ! -L "$stage_dir/execution-name.txt" ]] || die "unsafe recovery execution-name claim"
    execution="$(tr -d '\n' <"$stage_dir/execution-name.txt")"
  else
    # The semantic recovery intent is durable in GCS. Always scan for its
    # exact argv/env/token execution before launching, even when this local
    # stage directory was recreated on another machine.
    recovered="$(recover_recovery_execution "$token" "${args[@]}")"
    if [[ -n "$recovered" ]]; then
      execution="$recovered"
      write_equal "$stage_dir/execution-name.txt" "$execution"
    elif [[ "$intent_preexisted" == true ]]; then
      die "prior recovery launch remains ambiguous; blind relaunch is forbidden"
    else
      joined="$(IFS=,; printf '%s' "${args[*]}")"
      output="$(mktemp)"
      set +e
      gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
        --args="$joined" \
        --update-env-vars="R6_RECOVERY_STAGE_TOKEN=$token,$RECOVERY_GATE=1,R6_FULL_UNION_RECOVERY_CODE_SHA=$RECOVERY_CODE_SHA,R6_FULL_UNION_RECOVERY_RUNTIME_IMAGE=$RECOVERY_IMAGE" \
        --async --quiet --format='value(metadata.name)' >"$output"
      status=$?
      set -e
      write_equal "$stage_dir/launch-output.txt" "$(tr -d '\r\n' <"$output")"
      write_equal "$stage_dir/launch-exit-status.txt" "$status"
      execution="$(tr -d '\r\n' <"$output")"
      rm -f -- "$output"
      [[ "$status" -eq 0 && "$execution" =~ ^[a-z0-9][a-z0-9-]{2,127}$ ]] || die "recovery launch response is ambiguous; rerun only for exact recovery"
      write_equal "$stage_dir/execution-name.txt" "$execution"
    fi
  fi
  [[ "$execution" =~ ^[a-z0-9][a-z0-9-]{2,127}$ ]] || die "recovery execution-name claim differs"
  wait_recovery_terminal "$execution" "$stage_dir/terminal-execution.json" "$token" "${args[@]}"
  write_equal "$stage_dir/terminal-receipt.json" "$(jq -cnS --arg stage "$RECOVERY_STAGE" --arg execution "$execution" --arg sha "$(sha256sum "$stage_dir/terminal-execution.json" | awk '{print $1}')" '{stage:$stage,execution:$execution,terminal_execution_sha256:$sha,complete:true}')"
}

validate_compile_receipt() {
  local payload="$1" claimed_self observed_self parameter_sha compiled_epoch snapshot_epoch
  [[ -f "$payload" && ! -L "$payload" ]] || die "query compile receipt payload is absent"
  jq -cS . "$payload" | cmp -s - "$payload" || die "query compile receipt is not canonical"
  jq -e --arg project "$PROJECT" --arg code "$CODE_SHA" --arg image "$IMAGE" \
    --arg sql "$COMPILE_SQL_SHA256" '
    keys == ([
      "code_sha","compile_receipt_sha256","compile_script_sha256",
      "compiled","compiled_at","decision_authority","dry_run",
      "fixed_job_id_claimed","graph_mutation_licensed",
      "historical_outcome_lease_acquired","image",
      "lineup_scoring_performed","location","output_schema",
      "parameter_contract","parameter_contract_sha256","production_change_licensed",
      "project","query_executed","query_module_sha256","rows_read",
      "runtime_git_head","runtime_git_worktree_clean","schema_version",
      "source_snapshot_at","sql_sha256","total_bytes_processed_estimate",
      "uses_realized_outcome_rows"
    ] | sort)
      and .schema_version == "r6-full-union-query-compile-receipt/v1"
      and .project == $project
      and .location == "US"
      and .code_sha == $code
      and .image == $image
      and .runtime_git_head == $code
      and .runtime_git_worktree_clean == true
      and .sql_sha256 == $sql
      and (.query_module_sha256 | type == "string" and test("^[0-9a-f]{64}$"))
      and (.compile_script_sha256 | type == "string" and test("^[0-9a-f]{64}$"))
      and (.compiled_at | type == "string")
      and (.source_snapshot_at | type == "string")
      and .parameter_contract == [
        {array:false,name:"source_snapshot_at",type:"TIMESTAMP"},
        {array:true,name:"target_seasons",type:"INT64"},
        {array:true,name:"skill_keys",type:"STRING"},
        {array:true,name:"dst_keys",type:"STRING"}
      ]
      and .output_schema == [
        {field_type:"INTEGER",mode:"NULLABLE",name:"season"},
        {field_type:"INTEGER",mode:"NULLABLE",name:"week"},
        {field_type:"STRING",mode:"NULLABLE",name:"source_kind"},
        {field_type:"STRING",mode:"NULLABLE",name:"source_key"},
        {field_type:"NUMERIC",mode:"NULLABLE",name:"realized_score"}
      ]
      and (.total_bytes_processed_estimate | type == "number" and . >= 0 and floor == .)
      and .compiled == true
      and .dry_run == true
      and .fixed_job_id_claimed == false
      and .query_executed == false
      and .rows_read == 0
      and .historical_outcome_lease_acquired == false
      and .uses_realized_outcome_rows == false
      and .lineup_scoring_performed == false
      and .graph_mutation_licensed == false
      and .production_change_licensed == false
      and .decision_authority == false
  ' "$payload" >/dev/null || die "query compile receipt content differs"
  compiled_epoch="$(date -d "$(jq -r .compiled_at "$payload")" +%s)" || die "query compile timestamp differs"
  snapshot_epoch="$(date -d "$(jq -r .source_snapshot_at "$payload")" +%s)" || die "query compile snapshot timestamp differs"
  (( compiled_epoch - snapshot_epoch == 60 )) || die "query compile timestamp relation differs"
  parameter_sha="$(jq -cS .parameter_contract "$payload" | tr -d '\n' | sha256sum | awk '{print $1}')"
  [[ "$(jq -r .parameter_contract_sha256 "$payload")" == "$parameter_sha" ]] || die "query compile parameter hash differs"
  claimed_self="$(jq -r .compile_receipt_sha256 "$payload")"
  observed_self="$(jq -cS 'del(.compile_receipt_sha256)' "$payload" | tr -d '\n' | sha256sum | awk '{print $1}')"
  [[ "$claimed_self" =~ ^[0-9a-f]{64}$ && "$claimed_self" == "$observed_self" ]] || die "query compile receipt self-hash differs"
}

compile_binding_json() {
  local stage="$1" identity="$RUN_DIR/objects/query-compile-receipt.json" \
    payload="$RUN_DIR/objects/query-compile-receipt.payload.json" payload_sha payload_bytes
  if [[ "$stage" == "compile" ]]; then
    jq -cnS '{stage_creates_receipt:true}'
    return
  fi
  [[ -f "$identity" && ! -L "$identity" ]] || die "query compile receipt identity is absent"
  jq -e --arg uri "$SUPPLY_PREFIX/query-compile-receipt.json" '
    keys == ["bytes","generation","sha256","uri"]
      and .uri == $uri
      and (.generation | type == "string" and test("^[1-9][0-9]*$"))
      and (.sha256 | type == "string" and test("^[0-9a-f]{64}$"))
      and (.bytes | type == "number" and . > 0 and floor == .)
  ' "$identity" >/dev/null || die "query compile receipt identity fields differ"
  validate_compile_receipt "$payload"
  payload_sha="$(sha256sum "$payload" | awk '{print $1}')"
  payload_bytes="$(wc -c <"$payload" | tr -d ' ')"
  [[ "$(jq -r .sha256 "$identity")" == "$payload_sha" ]] || die "query compile receipt object SHA differs"
  [[ "$(jq -r .bytes "$identity")" == "$payload_bytes" ]] || die "query compile receipt object bytes differ"
  jq -cnS --arg uri "$(jq -r .uri "$identity")" \
    --arg generation "$(jq -r .generation "$identity")" \
    --arg sha256 "$(jq -r .sha256 "$identity")" \
    --argjson bytes "$(jq -r .bytes "$identity")" \
    --arg self_hash "$(jq -r .compile_receipt_sha256 "$payload")" \
    --arg sql_sha256 "$COMPILE_SQL_SHA256" \
    '{uri:$uri,generation:$generation,sha256:$sha256,bytes:$bytes,
      compile_receipt_sha256:$self_hash,sql_sha256:$sql_sha256}'
}

validate_original_supply_failure() {
  local stage_dir="$RUN_DIR/stages/supply"
  local intent="$stage_dir/launch-intent.json" \
    terminal="$stage_dir/terminal-execution.json" \
    name_file="$stage_dir/execution-name.txt" execution token argv_json env_json \
    compile_binding
  for file in "$intent" "$terminal" "$name_file"; do
    [[ -f "$file" && ! -L "$file" ]] || die "original failed supply evidence is absent or unsafe: $file"
  done
  [[ ! -e "$stage_dir/terminal-receipt.json" && ! -L "$stage_dir/terminal-receipt.json" ]] || die "original supply has a success receipt and is not recoverable as failed"
  execution="$(tr -d '\n' <"$name_file")"
  [[ "$execution" =~ ^[a-z0-9][a-z0-9-]{2,127}$ ]] || die "original failed supply execution name differs"
  token="$(jq -r '.token // empty' "$intent")"
  [[ "$token" =~ ^[0-9a-f]{64}$ ]] || die "original failed supply stage token differs"
  argv_json="$(jq -cS '.argv' "$intent")"
  env_json="$(stage_env_json R6_FULL_UNION_OUTCOME_SUPPLY_ENABLED "$token")"
  compile_binding="$(compile_binding_json supply)"
  jq -e --arg project "$PROJECT" --arg region "$REGION" --arg run "$RUN_ID" \
    --arg job "$JOB" --arg code "$CODE_SHA" --arg image "$IMAGE" \
    --arg service_account "$SERVICE_ACCOUNT" --arg token "$token" \
    --argjson expected_env "$env_json" \
    --argjson compile_binding "$compile_binding" '
    .schema_version == "r6-full-union-stage-launch-intent/v1"
      and .stage == "supply" and .token == $token
      and .project == $project and .region == $region and .run_id == $run
      and .job == $job and .code_sha == $code and .image == $image
      and .service_account == $service_account
      and .gate == "R6_FULL_UNION_OUTCOME_SUPPLY_ENABLED"
      and (.argv | type == "array" and length > 2)
      and .argv[0] == "/opt/nfl-predictions/scripts/run_corpus_r6_full_union_outcome_supply_v1.py"
      and .argv[1] == "supply"
      and (.argv_sha256 | type == "string" and test("^[0-9a-f]{64}$"))
      and .execution_env == $expected_env
      and .query_compile_receipt == $compile_binding
      and .automatic_retry_licensed == false
  ' "$intent" >/dev/null || die "original failed supply launch intent differs"
  jq -e --arg execution "$execution" --arg project "$PROJECT" \
    --arg region "$REGION" --arg job "$JOB" --arg image "$IMAGE" \
    --arg service_account "$SERVICE_ACCOUNT" \
    --argjson argv "$argv_json" --argjson expected_env "$env_json" '
    .spec.template.spec.containers as $containers
    | ((.metadata.name == $execution)
        or (.metadata.name == (
          "projects/" + $project + "/locations/" + $region
          + "/jobs/" + $job + "/executions/" + $execution
        )))
      and .metadata.labels["run.googleapis.com/job"] == $job
      and .spec.taskCount == 1 and .spec.parallelism == 1
      and .spec.template.spec.maxRetries == 0
      and ((.spec.template.spec.timeoutSeconds | tostring) == "28800")
      and ($containers | length) == 1
      and $containers[0].image == $image
      and $containers[0].command == ["python"]
      and $containers[0].args == $argv
      and ([($containers[0].env // [])[] | {name,value}] | sort_by(.name))
        == $expected_env
      and (($containers[0].volumeMounts // []) == [])
      and ((.spec.template.spec.volumes // []) == [])
      and ((.spec.template.spec.vpcAccess // {}) == {})
      and .spec.template.spec.serviceAccountName == $service_account
      and $containers[0].resources.limits == {cpu:"8",memory:"32Gi"}
      and ([.status.conditions[]? | select(.type == "Completed")] | length) == 1
      and ([.status.conditions[]? | select(.type == "Completed")][0].status == "False")
      and ([.status.conditions[]? | select(.type == "Completed")][0].reason == "NonZeroExitCode")
      and ((.status.succeededCount // 0) == 0)
      and .status.failedCount == 1
      and ((.status.runningCount // 0) == 0)
      and (.status.completionTime | type == "string")
  ' "$terminal" >/dev/null || die "original failed supply terminal envelope differs"
}

validate_original_supply_success() {
  local stage_dir="$RUN_DIR/stages/supply"
  local intent="$stage_dir/launch-intent.json" \
    name_file="$stage_dir/execution-name.txt" \
    terminal="$stage_dir/terminal-execution.json" execution token expected_token
  local args=()
  for file in "$intent" "$name_file" "$terminal" "$stage_dir/terminal-receipt.json"; do
    [[ -f "$file" && ! -L "$file" ]] || die "successful supply evidence is absent or unsafe: $file"
  done
  mapfile -t args < <(jq -er '.argv[]' "$intent")
  [[ "${#args[@]}" -gt 2 ]] || die "successful supply argv differs"
  token="$(jq -r '.token // empty' "$intent")"
  expected_token="$(stage_token supply R6_FULL_UNION_OUTCOME_SUPPLY_ENABLED "${args[@]}")"
  [[ "$token" == "$expected_token" ]] || die "successful supply launch token differs"
  execution="$(tr -d '\n' <"$name_file")"
  [[ "$execution" =~ ^[a-z0-9][a-z0-9-]{2,127}$ ]] || die "successful supply execution name differs"
  # Reopen only the already-claimed execution. wait_terminal cannot launch.
  wait_terminal "$execution" "$terminal" "$token" \
    R6_FULL_UNION_OUTCOME_SUPPLY_ENABLED "${args[@]}"
  jq -e --arg execution "$execution" \
    --arg sha "$(sha256sum "$terminal" | awk '{print $1}')" '
    .stage == "supply" and .execution == $execution and .complete == true
      and .terminal_execution_sha256 == $sha
  ' "$stage_dir/terminal-receipt.json" >/dev/null || die "successful supply terminal receipt differs"
}

resolve_existing_recovery_lease() {
  local receipt="$RUN_DIR/historical-outcome-lease.json" identity="$RUN_DIR/objects/historical-outcome-lease.json"
  [[ -f "$receipt" && ! -L "$receipt" ]] || die "existing historical-outcome lease receipt is absent"
  "$PYTHON" scripts/historical_outcome_lease.py resolve --run-id "$RUN_ID" \
    --job "$JOB" --code-sha "$CODE_SHA" --image "$IMAGE" \
    --receipt "$receipt" >/dev/null
  jq -e --arg uri "$LEASE_URI" --arg run "$RUN_ID" --arg job "$JOB" \
    --arg code "$CODE_SHA" --arg image "$IMAGE" '
    .object.uri == $uri and .object.create_only == true
      and (.object.generation | type == "string" and test("^[1-9][0-9]*$"))
      and (.object.sha256 | type == "string" and test("^[0-9a-f]{64}$"))
      and (.object.bytes | type == "number" and . > 0 and floor == .)
      and .lease.run_id == $run and .lease.job == $job
      and .lease.code_sha == $code and .lease.image == $image
  ' "$receipt" >/dev/null || die "existing recovery lease receipt differs"
  write_equal "$identity" "$(jq -cS '.object | {uri,generation,sha256,bytes}' "$receipt")"
  validate_identity_receipt "$identity" "$LEASE_URI" "historical-outcome lease"
}

require_local_recovery_downstream_absence() {
  local file
  for file in \
    "$RUN_DIR/objects/query-evidence.json" \
    "$RUN_DIR/objects/realized-source.json" \
    "$RUN_DIR/objects/outcome-snapshot.json" \
    "$RUN_DIR/objects/supply-completion.json" \
    "$RUN_DIR/objects/supply-recovery-worker-completion.json" \
    "$RUN_DIR/objects/supply-recovery-receipt.json"; do
    [[ ! -e "$file" && ! -L "$file" ]] || die "recovery downstream evidence already exists before intent: $file"
  done
}

prepare_recovery_intent() {
  local target="$RUN_DIR/objects/supply-recovery-intent.json" raw identity item
  local args=("$RECOVERY_CONTROLLER" prepare --execute "--project=$PROJECT" \
    "--region=$REGION" "--run-id=$RUN_ID" "--job=$JOB" \
    "--original-code-sha=$CODE_SHA" "--original-image=$IMAGE" \
    "--recovery-code-sha=$RECOVERY_CODE_SHA" "--recovery-image=$RECOVERY_IMAGE" \
    "--service-account=$SERVICE_ACCOUNT" \
    "--original-launch-intent=$RUN_DIR/stages/supply/launch-intent.json" \
    "--original-terminal-execution=$RUN_DIR/stages/supply/terminal-execution.json")
  args+=("${panel_args[@]}")
  while IFS= read -r item; do args+=("$item"); done < <(identity_arg "$RUN_DIR/objects/outcome-key-projection.json" outcome-key-projection)
  while IFS= read -r item; do args+=("$item"); done < <(identity_arg "$RUN_DIR/objects/actual-root-smoke-receipt.json" actual-root-smoke)
  while IFS= read -r item; do args+=("$item"); done < <(identity_arg "$RUN_DIR/objects/query-compile-receipt.json" query-compile)
  while IFS= read -r item; do args+=("$item"); done < <(identity_arg "$RUN_DIR/objects/historical-outcome-lease.json" expected-lease)
  while IFS= read -r item; do args+=("$item"); done < <(identity_arg "$RUN_DIR/objects/read-attempt.json" read-attempt)
  args+=("--snapshot-module-sha256=$SNAPSHOT_MODULE_SHA" \
    "--snapshot-cli-sha256=$SNAPSHOT_CLI_SHA" \
    "--snapshot-test-sha256=$SNAPSHOT_TEST_SHA" \
    "--snapshot-cli-test-sha256=$SNAPSHOT_CLI_TEST_SHA")
  raw="$("$PYTHON" "${args[@]}")" || die "recovery intent preparation failed"
  identity="$(identity_from_recovery_cli_summary "$raw" \
    R6_FULL_UNION_RECOVERY_INTENT_CLOSED "$RECOVERY_INTENT_URI" \
    "recovery intent")"
  write_equal "$target" "$identity"
  validate_identity_receipt "$target" "$RECOVERY_INTENT_URI" "supply recovery intent"
  resolve_object "$RECOVERY_INTENT_URI" "$target"
}

recovery_worker_args() {
  local intent="$RUN_DIR/objects/supply-recovery-intent.json" item
  RECOVERY_ARGS=("$RECOVERY_RUNTIME_CONTROLLER" recover --execute \
    "--project=$PROJECT" "--run-id=$RUN_ID" "--job=$JOB" \
    "--original-code-sha=$CODE_SHA" "--original-image=$IMAGE" \
    "--recovery-code-sha=$RECOVERY_CODE_SHA" "--recovery-image=$RECOVERY_IMAGE")
  while IFS= read -r item; do RECOVERY_ARGS+=("$item"); done < <(identity_arg "$intent" recovery-intent)
}

finalize_recovery_receipt() {
  local intent="$RUN_DIR/objects/supply-recovery-intent.json" \
    terminal="$RUN_DIR/stages/$RECOVERY_STAGE/terminal-execution.json" \
    target="$RUN_DIR/objects/supply-recovery-receipt.json" raw identity token item
  local args=("$RECOVERY_CONTROLLER" finalize --execute "--project=$PROJECT" \
    "--region=$REGION" "--run-id=$RUN_ID" "--job=$JOB" \
    "--original-code-sha=$CODE_SHA" "--original-image=$IMAGE" \
    "--recovery-code-sha=$RECOVERY_CODE_SHA" "--recovery-image=$RECOVERY_IMAGE" \
    "--service-account=$SERVICE_ACCOUNT" \
    "--recovery-terminal-execution=$terminal")
  [[ -f "$RUN_DIR/stages/$RECOVERY_STAGE/launch-intent.json" ]] || die "recovery launch intent is absent"
  token="$(jq -r '.token // empty' "$RUN_DIR/stages/$RECOVERY_STAGE/launch-intent.json")"
  [[ "$token" =~ ^[0-9a-f]{64}$ ]] || die "recovery stage token differs"
  args+=("--recovery-stage-token=$token")
  while IFS= read -r item; do args+=("$item"); done < <(identity_arg "$intent" recovery-intent)
  raw="$("$PYTHON" "${args[@]}")" || die "recovery receipt finalization failed"
  identity="$(identity_from_recovery_cli_summary "$raw" \
    R6_FULL_UNION_RECOVERY_CLOSED "$RECOVERY_RECEIPT_URI" \
    "recovery finalize")"
  write_equal "$target" "$identity"
  validate_identity_receipt "$target" "$RECOVERY_RECEIPT_URI" "supply recovery receipt"
  resolve_object "$RECOVERY_WORKER_COMPLETION_URI" "$RUN_DIR/objects/supply-recovery-worker-completion.json"
  resolve_object "$RECOVERY_RECEIPT_URI" "$target"
}

resolve_supply_outputs() {
  resolve_object "$SUPPLY_PREFIX/read-attempt.json" "$RUN_DIR/objects/read-attempt.json"
  resolve_object "$SUPPLY_PREFIX/query-evidence.json" "$RUN_DIR/objects/query-evidence.json"
  resolve_object "$SUPPLY_PREFIX/completion.json" "$RUN_DIR/objects/supply-completion.json"
  resolve_object "$SUPPLY_PREFIX/realized-source.json" "$RUN_DIR/objects/realized-source.json"
  resolve_object "$SUPPLY_PREFIX/outcome-snapshot.json" "$RUN_DIR/objects/outcome-snapshot.json"
}

RECOVERY_RESTORE_ARMED=false
restore_original_job_on_exit() {
  local status=$?
  trap - EXIT
  if [[ "$RECOVERY_RESTORE_ARMED" == true ]]; then
    if ! (preflight); then
      printf 'ERROR: failed to restore the original immutable Cloud Run job contract\n' >&2
      status=1
    fi
  fi
  exit "$status"
}

recover_failed_supply() {
  load_recovery_runtime
  validate_original_supply_failure
  ensure_compile_closed
  ensure_smoke_closed
  resolve_existing_recovery_lease
  resolve_object "$SUPPLY_PREFIX/read-attempt.json" "$RUN_DIR/objects/read-attempt.json"
  if [[ ! -e "$RUN_DIR/objects/supply-recovery-intent.json" && ! -L "$RUN_DIR/objects/supply-recovery-intent.json" ]]; then
    require_local_recovery_downstream_absence
    prepare_recovery_intent
  else
    validate_identity_receipt "$RUN_DIR/objects/supply-recovery-intent.json" \
      "$RECOVERY_INTENT_URI" "supply recovery intent"
    resolve_object "$RECOVERY_INTENT_URI" "$RUN_DIR/objects/supply-recovery-intent.json"
  fi
  recovery_worker_args
  RECOVERY_RESTORE_ARMED=true
  trap restore_original_job_on_exit EXIT
  preflight_recovery
  launch_recovery_stage "$RUN_DIR/objects/supply-recovery-intent.json" "${RECOVERY_ARGS[@]}"
  finalize_recovery_receipt
  resolve_supply_outputs
  (preflight) || die "failed to restore the original immutable Cloud Run job contract"
  RECOVERY_RESTORE_ARMED=false
  trap - EXIT
}

ensure_supply_closed() {
  local original_terminal="$RUN_DIR/stages/supply/terminal-execution.json" state \
    recovery_launch="$RUN_DIR/stages/$RECOVERY_STAGE/launch-intent.json"
  [[ -f "$original_terminal" && ! -L "$original_terminal" ]] || die "supply terminal execution is absent"
  state="$(jq -r '[.status.conditions[]? | select(.type=="Completed") | .status] | if length==1 then .[0] else "" end' "$original_terminal")"
  if [[ "$state" == "True" ]]; then
    validate_original_supply_success
    return
  fi
  [[ "$state" == "False" ]] || die "supply is not terminal"
  validate_original_supply_failure
  [[ -f "$recovery_launch" && ! -L "$recovery_launch" ]] || die "failed supply lacks a recovery launch intent"
  RECOVERY_CODE_SHA="$(jq -r '.recovery_code_sha // empty' "$recovery_launch")"
  RECOVERY_IMAGE="$(jq -r '.recovery_image // empty' "$recovery_launch")"
  [[ "$RECOVERY_CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "retained recovery code SHA differs"
  [[ "$RECOVERY_IMAGE" =~ @sha256:[0-9a-f]{64}$ ]] || die "retained recovery image differs"
  validate_identity_receipt "$RUN_DIR/objects/supply-recovery-intent.json" \
    "$RECOVERY_INTENT_URI" "supply recovery intent"
  recovery_worker_args
  jq -e --arg original_code "$CODE_SHA" --arg original_image "$IMAGE" \
    --arg recovery_code "$RECOVERY_CODE_SHA" --arg recovery_image "$RECOVERY_IMAGE" \
    --argjson intent "$(jq -cS . "$RUN_DIR/objects/supply-recovery-intent.json")" \
    --argjson argv "$(printf '%s\n' "${RECOVERY_ARGS[@]}" | jq -Rsc 'split("\n")[:-1]')" '
    .schema_version == "r6-full-union-recovery-stage-launch-intent/v1"
      and .original_code_sha == $original_code
      and .original_image == $original_image
      and .recovery_code_sha == $recovery_code
      and .recovery_image == $recovery_image
      and .recovery_intent == $intent and .argv == $argv
      and .fixed_job_lookup_only == true
      and .query_submission_licensed == false
      and .ordinary_supply_relaunch_licensed == false
      and .automatic_retry_licensed == false
  ' "$recovery_launch" >/dev/null || die "retained recovery launch intent differs"
  finalize_recovery_receipt
  resolve_supply_outputs
}

compile_stage() {
  preflight
  launch_stage compile R6_FULL_UNION_QUERY_COMPILE_ENABLED "${compile_args[@]}"
  resolve_object "$SUPPLY_PREFIX/query-compile-receipt.json" \
    "$RUN_DIR/objects/query-compile-receipt.json" \
    "$RUN_DIR/objects/query-compile-receipt.payload.json"
  validate_compile_receipt "$RUN_DIR/objects/query-compile-receipt.payload.json"
}

ensure_compile_closed() {
  local stage_dir="$RUN_DIR/stages/compile" execution token
  [[ -f "$stage_dir/launch-intent.json" && ! -L "$stage_dir/launch-intent.json" ]] || die "query compile launch intent is absent"
  [[ -f "$stage_dir/execution-name.txt" && ! -L "$stage_dir/execution-name.txt" ]] || die "query compile execution name is absent"
  execution="$(tr -d '\n' <"$stage_dir/execution-name.txt")"
  token="$(stage_token compile R6_FULL_UNION_QUERY_COMPILE_ENABLED "${compile_args[@]}")"
  [[ "$(jq -r .token "$stage_dir/launch-intent.json")" == "$token" ]] || die "query compile launch intent token differs"
  wait_terminal "$execution" "$stage_dir/terminal-execution.json" "$token" \
    R6_FULL_UNION_QUERY_COMPILE_ENABLED "${compile_args[@]}"
  resolve_object "$SUPPLY_PREFIX/query-compile-receipt.json" \
    "$RUN_DIR/objects/query-compile-receipt.json" \
    "$RUN_DIR/objects/query-compile-receipt.payload.json"
  validate_compile_receipt "$RUN_DIR/objects/query-compile-receipt.payload.json"
}

smoke() {
  ensure_compile_closed
  preflight
  launch_stage smoke R6_FULL_UNION_ACTUAL_ROOT_SMOKE_ENABLED "${smoke_args[@]}"
  resolve_object "$SUPPLY_PREFIX/outcome-key-projection.json" "$RUN_DIR/objects/outcome-key-projection.json"
  resolve_object "$SUPPLY_PREFIX/actual-root-smoke-receipt.json" "$RUN_DIR/objects/actual-root-smoke-receipt.json"
}

ensure_smoke_closed() {
  local stage_dir="$RUN_DIR/stages/smoke" execution token
  [[ -f "$stage_dir/launch-intent.json" && ! -L "$stage_dir/launch-intent.json" ]] || die "smoke launch intent is absent"
  [[ -f "$stage_dir/execution-name.txt" && ! -L "$stage_dir/execution-name.txt" ]] || die "smoke execution name is absent"
  execution="$(tr -d '\n' <"$stage_dir/execution-name.txt")"
  token="$(stage_token smoke R6_FULL_UNION_ACTUAL_ROOT_SMOKE_ENABLED "${smoke_args[@]}")"
  [[ "$(jq -r .token "$stage_dir/launch-intent.json")" == "$token" ]] || die "smoke launch intent token differs"
  wait_terminal "$execution" "$stage_dir/terminal-execution.json" "$token" \
    R6_FULL_UNION_ACTUAL_ROOT_SMOKE_ENABLED "${smoke_args[@]}"
  resolve_object "$SUPPLY_PREFIX/outcome-key-projection.json" "$RUN_DIR/objects/outcome-key-projection.json"
  resolve_object "$SUPPLY_PREFIX/actual-root-smoke-receipt.json" "$RUN_DIR/objects/actual-root-smoke-receipt.json"
}

acquire_or_resolve_lease() {
  local receipt="$RUN_DIR/historical-outcome-lease.json"
  if [[ -f "$receipt" && ! -L "$receipt" ]]; then
    "$PYTHON" scripts/historical_outcome_lease.py resolve --run-id "$RUN_ID" --job "$JOB" --code-sha "$CODE_SHA" --image "$IMAGE" --receipt "$receipt" >/dev/null
    return
  fi
  if ! "$PYTHON" scripts/historical_outcome_lease.py acquire --run-id "$RUN_ID" --job "$JOB" --code-sha "$CODE_SHA" --image "$IMAGE" --receipt "$receipt" >/dev/null; then
    "$PYTHON" scripts/historical_outcome_lease.py resolve --run-id "$RUN_ID" --job "$JOB" --code-sha "$CODE_SHA" --image "$IMAGE" --receipt "$receipt" >/dev/null
  fi
  [[ "$(jq -r '.object.uri' "$receipt")" == "$LEASE_URI" ]] || die "lease URI differs"
}

supply_stage() {
  ensure_compile_closed
  preflight
  ensure_smoke_closed
  acquire_or_resolve_lease
  local args=(/opt/nfl-predictions/scripts/run_corpus_r6_full_union_outcome_supply_v1.py supply --execute "--project=$PROJECT" "--run-id=$RUN_ID" "--job=$JOB" "--code-sha=$CODE_SHA" "--image=$IMAGE") item
  args+=("${panel_args[@]}")
  args+=("--snapshot-module-sha256=$SNAPSHOT_MODULE_SHA" "--snapshot-cli-sha256=$SNAPSHOT_CLI_SHA" "--snapshot-test-sha256=$SNAPSHOT_TEST_SHA" "--snapshot-cli-test-sha256=$SNAPSHOT_CLI_TEST_SHA")
  while IFS= read -r item; do args+=("$item"); done < <(identity_arg "$RUN_DIR/objects/actual-root-smoke-receipt.json" actual-root-smoke)
  args+=("--expected-lease-uri=$(jq -r .object.uri "$RUN_DIR/historical-outcome-lease.json")" "--expected-lease-generation=$(jq -r .object.generation "$RUN_DIR/historical-outcome-lease.json")" "--expected-lease-sha256=$(jq -r .object.sha256 "$RUN_DIR/historical-outcome-lease.json")" "--expected-lease-bytes=$(jq -r .object.bytes "$RUN_DIR/historical-outcome-lease.json")")
  launch_stage supply R6_FULL_UNION_OUTCOME_SUPPLY_ENABLED "${args[@]}"
  resolve_object "$SUPPLY_PREFIX/read-attempt.json" "$RUN_DIR/objects/read-attempt.json"
  resolve_object "$SUPPLY_PREFIX/query-evidence.json" "$RUN_DIR/objects/query-evidence.json"
  resolve_object "$SUPPLY_PREFIX/completion.json" "$RUN_DIR/objects/supply-completion.json"
  resolve_object "$SUPPLY_PREFIX/realized-source.json" "$RUN_DIR/objects/realized-source.json"
  resolve_object "$SUPPLY_PREFIX/outcome-snapshot.json" "$RUN_DIR/objects/outcome-snapshot.json"
}

grade_stage() {
  ensure_compile_closed
  ensure_supply_closed
  preflight
  local args=(/opt/nfl-predictions/scripts/run_corpus_r6_full_union_realized_grade_v1.py --execute "--project=$PROJECT" "--run-id=$RUN_ID" "--code-sha=$CODE_SHA" "--image=$IMAGE") item
  args+=("${panel_args[@]}")
  while IFS= read -r item; do args+=("$item"); done < <(identity_arg "$RUN_DIR/objects/supply-completion.json" outcome-supply-completion)
  while IFS= read -r item; do args+=("$item"); done < <(identity_arg "$RUN_DIR/objects/outcome-key-projection.json" outcome-key-projection)
  while IFS= read -r item; do args+=("$item"); done < <(identity_arg "$RUN_DIR/objects/realized-source.json" realized-source)
  while IFS= read -r item; do args+=("$item"); done < <(identity_arg "$RUN_DIR/objects/outcome-snapshot.json" outcome-snapshot)
  args+=("--expected-lease-uri=$(jq -r .object.uri "$RUN_DIR/historical-outcome-lease.json")" "--expected-lease-generation=$(jq -r .object.generation "$RUN_DIR/historical-outcome-lease.json")" "--expected-lease-sha256=$(jq -r .object.sha256 "$RUN_DIR/historical-outcome-lease.json")" "--expected-lease-bytes=$(jq -r .object.bytes "$RUN_DIR/historical-outcome-lease.json")")
  args+=("--expected-supply-run-id=$RUN_ID" "--expected-supply-job=$JOB" "--expected-supply-code-sha=$CODE_SHA" "--expected-supply-image=$IMAGE")
  args+=("--snapshot-module-sha256=$SNAPSHOT_MODULE_SHA" "--snapshot-cli-sha256=$SNAPSHOT_CLI_SHA" "--snapshot-test-sha256=$SNAPSHOT_TEST_SHA" "--snapshot-cli-test-sha256=$SNAPSHOT_CLI_TEST_SHA")
  launch_stage grade R6_FULL_UNION_REALIZED_GRADE_ENABLED "${args[@]}"
  resolve_object "$GRADE_PREFIX/realized-grade-root.json" "$RUN_DIR/objects/persisted-grade-root.json"
  resolve_object "$GRADE_PREFIX/grade-completion.json" "$RUN_DIR/objects/grade-completion.json"
}

finish() {
  ensure_compile_closed
  [[ -f "$RUN_DIR/stages/grade/terminal-execution.json" ]] || die "grade must close first"
  resolve_object "$GRADE_PREFIX/realized-grade-root.json" "$RUN_DIR/objects/persisted-grade-root.json"
  resolve_object "$GRADE_PREFIX/grade-completion.json" "$RUN_DIR/objects/grade-completion.json"
  "$PYTHON" scripts/historical_outcome_lease.py materialize-r6-full-union-completion \
    --receipt "$RUN_DIR/historical-outcome-lease.json" \
    --supply-completion-uri "$SUPPLY_PREFIX/completion.json" \
    --grade-completion-uri "$GRADE_PREFIX/grade-completion.json" \
    --expected-service-account "$SERVICE_ACCOUNT" \
    --expected-grade-stage-token "$(jq -r .token "$RUN_DIR/stages/grade/launch-intent.json")" \
    --expected-snapshot-module-sha256 "$SNAPSHOT_MODULE_SHA" \
    --expected-snapshot-cli-sha256 "$SNAPSHOT_CLI_SHA" \
    --expected-snapshot-test-sha256 "$SNAPSHOT_TEST_SHA" \
    --expected-snapshot-cli-test-sha256 "$SNAPSHOT_CLI_TEST_SHA" \
    --output "$RUN_DIR/r6-strict-completion.txt" >"$RUN_DIR/materialize-receipt.txt"
  "$PYTHON" scripts/historical_outcome_lease.py release \
    --receipt "$RUN_DIR/historical-outcome-lease.json" \
    --execution "$RUN_DIR/stages/grade/terminal-execution.json" \
    --completion "$RUN_DIR/r6-strict-completion.txt" \
    --release-intent "$RUN_DIR/lease-release-intent.json" \
    --release-receipt "$RUN_DIR/lease-release-receipt.json" \
    --required-contract r6-full-union >"$RUN_DIR/lease-release-command.txt"
}

status() {
  local stage
  for stage in compile smoke supply "$RECOVERY_STAGE" grade; do
    if [[ -f "$RUN_DIR/stages/$stage/terminal-receipt.json" ]]; then
      jq -cS . "$RUN_DIR/stages/$stage/terminal-receipt.json"
    else
      printf '{"stage":"%s","complete":false}\n' "$stage"
    fi
  done
  if [[ -f "$RUN_DIR/lease-release-receipt.json" ]]; then
    "$PYTHON" scripts/historical_outcome_lease.py validate-release-receipt \
      --lease-receipt "$RUN_DIR/historical-outcome-lease.json" \
      --execution "$RUN_DIR/stages/grade/terminal-execution.json" \
      --completion "$RUN_DIR/r6-strict-completion.txt" \
      --release-intent "$RUN_DIR/lease-release-intent.json" \
      --release-receipt "$RUN_DIR/lease-release-receipt.json"
  else
    printf '{"lease_released":false}\n'
  fi
}

case "$COMMAND" in
  preflight) preflight ;;
  compile) compile_stage ;;
  smoke) smoke ;;
  supply) supply_stage ;;
  recover-supply) recover_failed_supply ;;
  grade) grade_stage ;;
  finish) finish ;;
  status) status ;;
  run) compile_stage; smoke; supply_stage; grade_stage; finish ;;
esac
