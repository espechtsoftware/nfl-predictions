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
  preflight|compile|smoke|supply|grade|finish|run|status) ;;
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
  local names candidate temp argv_json env_json matches=()
  argv_json="$(printf '%s\n' "$@" | jq -Rsc 'split("\n")[:-1]')"
  env_json="$(stage_env_json "$gate" "$token")"
  names="$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" --region "$REGION" --format='value(metadata.name)')"
  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    candidate="${candidate##*/}"
    temp="$(mktemp)"
    gcloud run jobs executions describe "$candidate" --project "$PROJECT" --region "$REGION" --format=json >"$temp"
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
    ' "$temp" >/dev/null; then
      matches+=("$candidate")
    fi
    rm -f -- "$temp"
  done <<<"$names"
  [[ "${#matches[@]}" -le 1 ]] || die "execution-name recovery is ambiguous for $stage"
  [[ "${#matches[@]}" -eq 1 ]] && printf '%s\n' "${matches[0]}"
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
  preflight
  [[ -f "$RUN_DIR/stages/supply/terminal-execution.json" ]] || die "supply must close first"
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
  for stage in compile smoke supply grade; do
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
  grade) grade_stage ;;
  finish) finish ;;
  status) status ;;
  run) compile_stage; smoke; supply_stage; grade_stage; finish ;;
esac
