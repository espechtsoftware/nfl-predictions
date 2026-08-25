#!/usr/bin/env bash
# Default-off two-lane operator for the frozen T230 production transport.
# It reuses exactly two existing jobs, launches one task per execution with
# maxRetries=0, and never performs a bucket list or resolves a latest alias.

set -euo pipefail
export LC_ALL=C
set -o noclobber

PROJECT="nfl-predictions-503414"
REGION="us-central1"
JOB_A="atlas-minimal-c-s2023-w1-v1"
JOB_B="atlas-cbc-32g-full-2023-w8-v1"
PYTHON_BIN="${T230_PYTHON_BIN:-.venv/bin/python}"
TRANSPORT="scripts/run_corpus_extreme_tail_panel_transport_v1.py"
ENABLE_ENV="FOUNDRY_T230_PRODUCTION_TRANSPORT_ENABLED"

die() { printf '%s\n' "T230 operator refused: $*" >&2; exit 2; }
require_var() { [[ -n "${!1:-}" ]] || die "$1 is required"; }

require_base_gate() {
  [[ "${1:-}" == "--execute" ]] || die "literal --execute is required"
  [[ "${FOUNDRY_T230_PRODUCTION_TRANSPORT_ENABLED:-}" == "1" ]] || \
    die "${ENABLE_ENV}=1 is required"
  command -v gcloud >/dev/null || die "gcloud is required"
  command -v jq >/dev/null || die "jq is required"
  [[ -x "$PYTHON_BIN" && -f "$TRANSPORT" ]] || die "transport runtime is absent"
  require_var T230_RUN_DIR
  [[ "$T230_RUN_DIR" == /* && ! -L "$T230_RUN_DIR" ]] || \
    die "T230_RUN_DIR must be one absolute non-symlink path"
  mkdir -p "$T230_RUN_DIR"
  [[ "$(realpath "$T230_RUN_DIR")" == "$T230_RUN_DIR" ]] || \
    die "T230_RUN_DIR must be canonical"
}

require_gate() {
  require_base_gate "$@"
  require_var T230_TRANSPORT_CONTRACT_IDENTITY_FILE
  require_var T230_IMAGE_EVIDENCE_IDENTITY_FILE
  require_var T230_IMAGE
  require_var T230_SERVICE_ACCOUNT
  local contract="$T230_RUN_DIR/transport-contract-identity.json"
  local evidence="$T230_RUN_DIR/image-evidence-identity.json"
  local image="$T230_RUN_DIR/immutable-image.json"
  [[ "$T230_TRANSPORT_CONTRACT_IDENTITY_FILE" == "$contract" ]] || \
    die "transport contract identity must be the fixed bootstrap carrier"
  [[ "$T230_IMAGE_EVIDENCE_IDENTITY_FILE" == "$evidence" ]] || \
    die "image evidence identity must be the fixed bootstrap carrier"
  "$PYTHON_BIN" "$TRANSPORT" resolve-transport-contract \
    --contract-output "$contract" --evidence-output "$evidence" \
    --image-output "$image" --execute >/dev/null
  [[ "$T230_IMAGE" == "$(identity_value "$image" uri)" ]] || \
    die "T230_IMAGE differs from the exact transport contract"
}

bootstrap() {
  require_base_gate "${1:-}"
  local contract="$T230_RUN_DIR/transport-contract-identity.json"
  local evidence="$T230_RUN_DIR/image-evidence-identity.json"
  local image="$T230_RUN_DIR/immutable-image.json"
  "$PYTHON_BIN" "$TRANSPORT" resolve-transport-contract \
    --contract-output "$contract" --evidence-output "$evidence" \
    --image-output "$image" --execute >/dev/null
  printf 'export T230_TRANSPORT_CONTRACT_IDENTITY_FILE=%q\n' "$contract"
  printf 'export T230_IMAGE_EVIDENCE_IDENTITY_FILE=%q\n' "$evidence"
  printf 'export T230_IMAGE=%q\n' "$(identity_value "$image" uri)"
}

identity_value() {
  local path="$1" field="$2"
  [[ -f "$path" && ! -L "$path" ]] || die "identity file is unsafe: $path"
  jq -er --arg field "$field" '.[$field]' "$path"
}

install_local_equal() {
  local candidate="$1" target="$2"
  if [[ -e "$target" ]]; then
    [[ -f "$target" && ! -L "$target" ]] || die "unsafe local carrier: $target"
    cmp -s "$candidate" "$target" || die "local carrier bytes differ: $target"
    command rm -f -- "$candidate"
  else
    install -m 0600 "$candidate" "$target"
    command rm -f -- "$candidate"
  fi
}

write_jq_identity() {
  local filter="$1" source="$2" target="$3" candidate
  candidate="$(mktemp "$T230_RUN_DIR/.identity-candidate.XXXXXX")"
  jq -c "$filter" "$source" >|"$candidate"
  install_local_equal "$candidate" "$target"
}

contract_cli_args() {
  printf '%s\n' \
    --transport-contract-uri "$(identity_value "$T230_TRANSPORT_CONTRACT_IDENTITY_FILE" uri)" \
    --transport-contract-generation "$(identity_value "$T230_TRANSPORT_CONTRACT_IDENTITY_FILE" generation)" \
    --transport-contract-sha256 "$(identity_value "$T230_TRANSPORT_CONTRACT_IDENTITY_FILE" sha256)" \
    --transport-contract-bytes "$(identity_value "$T230_TRANSPORT_CONTRACT_IDENTITY_FILE" bytes)"
}

runtime_script() {
  cat <<'RUNTIME'
set -euo pipefail
python scripts/run_corpus_extreme_tail_panel_transport_v1.py materialize-image-evidence \
  --image-evidence-uri "$T230_EVIDENCE_URI" \
  --image-evidence-generation "$T230_EVIDENCE_GENERATION" \
  --image-evidence-sha256 "$T230_EVIDENCE_SHA256" \
  --image-evidence-bytes "$T230_EVIDENCE_BYTES" --execute >/tmp/materialized.json

stage=(python scripts/run_corpus_extreme_tail_panel_transport_v1.py run-stage
  --operation "$T230_OPERATION"
  --runtime-attempt-ordinal "$T230_ATTEMPT"
  --cloud-execution-name "$CLOUD_RUN_EXECUTION"
  --cloud-job "$CLOUD_RUN_JOB"
  --cloud-task-index "$CLOUD_RUN_TASK_INDEX"
  --cloud-task-attempt "$CLOUD_RUN_TASK_ATTEMPT"
  --cloud-task-count "$CLOUD_RUN_TASK_COUNT"
  --runtime-image "$T230_IMAGE"
  --transport-contract-uri "$T230_CONTRACT_URI"
  --transport-contract-generation "$T230_CONTRACT_GENERATION"
  --transport-contract-sha256 "$T230_CONTRACT_SHA256"
  --transport-contract-bytes "$T230_CONTRACT_BYTES"
  --launch-request-uri "$T230_LAUNCH_REQUEST_URI"
  --launch-request-generation "$T230_LAUNCH_REQUEST_GENERATION"
  --launch-request-sha256 "$T230_LAUNCH_REQUEST_SHA256"
  --launch-request-bytes "$T230_LAUNCH_REQUEST_BYTES"
  --launch-request-intent-uri "$T230_LAUNCH_INTENT_URI"
  --launch-request-intent-generation "$T230_LAUNCH_INTENT_GENERATION"
  --launch-request-intent-sha256 "$T230_LAUNCH_INTENT_SHA256"
  --launch-request-intent-bytes "$T230_LAUNCH_INTENT_BYTES"
  --launch-request-completion-uri "$T230_LAUNCH_COMPLETION_URI"
  --launch-request-completion-generation "$T230_LAUNCH_COMPLETION_GENERATION"
  --launch-request-completion-sha256 "$T230_LAUNCH_COMPLETION_SHA256"
  --launch-request-completion-bytes "$T230_LAUNCH_COMPLETION_BYTES"
  --execute)
[[ "$T230_PRED_COUNT" =~ ^[0-2]$ ]] || exit 2
if (( T230_PRED_COUNT > 0 )); then
for pred_index in $(seq 0 $((T230_PRED_COUNT - 1))); do
  uri_name="T230_PRED${pred_index}_URI"
  generation_name="T230_PRED${pred_index}_GENERATION"
  sha_name="T230_PRED${pred_index}_SHA256"
  bytes_name="T230_PRED${pred_index}_BYTES"
  pred_path="/tmp/predecessor-${pred_index}.json"
  jq -cn --arg uri "${!uri_name}" --arg generation "${!generation_name}" \
    --arg sha256 "${!sha_name}" --argjson bytes "${!bytes_name}" \
    '{uri:$uri,generation:$generation,sha256:$sha256,bytes:$bytes}' >"$pred_path"
  stage+=(--predecessor-identity "$pred_path")
done
fi
if [[ "$T230_SOURCE_ORDINAL" != "none" ]]; then
  stage+=(--source-ordinal "$T230_SOURCE_ORDINAL")
fi
if [[ "$T230_OPERATION" != "prepare" ]]; then
  stage+=(--execution-authority-uri "$T230_AUTHORITY_URI"
    --execution-authority-generation "$T230_AUTHORITY_GENERATION"
    --execution-authority-sha256 "$T230_AUTHORITY_SHA256"
    --execution-authority-bytes "$T230_AUTHORITY_BYTES")
fi
if [[ "$T230_OPERATION" == "verify-slate" ]]; then
  stage+=(--result-uri "$T230_RESULT_URI"
    --result-generation "$T230_RESULT_GENERATION"
    --result-sha256 "$T230_RESULT_SHA256"
    --result-bytes "$T230_RESULT_BYTES")
fi
if [[ "$T230_OPERATION" == "finish-panel" ]]; then
  jq -cn --arg uri "$T230_LANE0_URI" --arg generation "$T230_LANE0_GENERATION" \
    --arg sha256 "$T230_LANE0_SHA256" --argjson bytes "$T230_LANE0_BYTES" \
    '{uri:$uri,generation:$generation,sha256:$sha256,bytes:$bytes}' >/tmp/lane0.json
  jq -cn --arg uri "$T230_LANE1_URI" --arg generation "$T230_LANE1_GENERATION" \
    --arg sha256 "$T230_LANE1_SHA256" --argjson bytes "$T230_LANE1_BYTES" \
    '{uri:$uri,generation:$generation,sha256:$sha256,bytes:$bytes}' >/tmp/lane1.json
  stage+=(--lane-ledger /tmp/lane0.json --lane-ledger /tmp/lane1.json)
fi
if [[ "$T230_COMPUTE_URI" != "" ]]; then
  stage+=(--compute-release-uri "$T230_COMPUTE_URI"
    --compute-release-generation "$T230_COMPUTE_GENERATION"
    --compute-release-sha256 "$T230_COMPUTE_SHA256"
    --compute-release-bytes "$T230_COMPUTE_BYTES")
fi

if [[ "$T230_BENCHMARK" == "1" ]]; then
  export LC_ALL=C
  /usr/bin/time -v -o /tmp/gnu-time-v.raw \
    bash scripts/run_t230_benchmark_worker_v1.sh \
    >/tmp/stage.json
  jq -c '.stage_receipt_identity' /tmp/stage.json >/tmp/worker-stage-identity.json
  raw_publication="$(python scripts/run_corpus_extreme_tail_panel_transport_v1.py publish-raw-time-v \
    --transport-contract-uri "$T230_CONTRACT_URI" \
    --transport-contract-generation "$T230_CONTRACT_GENERATION" \
    --transport-contract-sha256 "$T230_CONTRACT_SHA256" \
    --transport-contract-bytes "$T230_CONTRACT_BYTES" \
    --worker-stage-receipt-uri "$(jq -er '.uri' /tmp/worker-stage-identity.json)" \
    --worker-stage-receipt-generation "$(jq -er '.generation' /tmp/worker-stage-identity.json)" \
    --worker-stage-receipt-sha256 "$(jq -er '.sha256' /tmp/worker-stage-identity.json)" \
    --worker-stage-receipt-bytes "$(jq -er '.bytes' /tmp/worker-stage-identity.json)" \
    --raw-time-v /tmp/gnu-time-v.raw --execute)"
  raw_uri="$(jq -er '.raw_time_v_identity.uri' <<<"$raw_publication")"
  raw_generation="$(jq -er '.raw_time_v_identity.generation' <<<"$raw_publication")"
  raw_sha256="$(jq -er '.raw_time_v_identity.sha256' <<<"$raw_publication")"
  raw_bytes="$(jq -er '.raw_time_v_identity.bytes' <<<"$raw_publication")"
  python scripts/run_corpus_extreme_tail_panel_transport_v1.py build-benchmark \
    --transport-contract-uri "$T230_CONTRACT_URI" \
    --transport-contract-generation "$T230_CONTRACT_GENERATION" \
    --transport-contract-sha256 "$T230_CONTRACT_SHA256" \
    --transport-contract-bytes "$T230_CONTRACT_BYTES" \
    --worker-stage-receipt-uri "$(jq -er '.uri' /tmp/worker-stage-identity.json)" \
    --worker-stage-receipt-generation "$(jq -er '.generation' /tmp/worker-stage-identity.json)" \
    --worker-stage-receipt-sha256 "$(jq -er '.sha256' /tmp/worker-stage-identity.json)" \
    --worker-stage-receipt-bytes "$(jq -er '.bytes' /tmp/worker-stage-identity.json)" \
    --benchmark-disposition-uri "$(jq -er '.benchmark_disposition_identity.uri' <<<"$raw_publication")" \
    --benchmark-disposition-generation "$(jq -er '.benchmark_disposition_identity.generation' <<<"$raw_publication")" \
    --benchmark-disposition-sha256 "$(jq -er '.benchmark_disposition_identity.sha256' <<<"$raw_publication")" \
    --benchmark-disposition-bytes "$(jq -er '.benchmark_disposition_identity.bytes' <<<"$raw_publication")" \
    --raw-time-v-uri "$raw_uri" --raw-time-v-generation "$raw_generation" \
    --raw-time-v-sha256 "$raw_sha256" --raw-time-v-bytes "$raw_bytes" \
    --output /tmp/benchmark.json --execute >/tmp/benchmark-build.json
  benchmark_publication="$(python scripts/run_corpus_extreme_tail_panel_transport_v1.py publish-benchmark \
    --transport-contract-uri "$T230_CONTRACT_URI" \
    --transport-contract-generation "$T230_CONTRACT_GENERATION" \
    --transport-contract-sha256 "$T230_CONTRACT_SHA256" \
    --transport-contract-bytes "$T230_CONTRACT_BYTES" \
    --benchmark /tmp/benchmark.json --execute)"
  python scripts/run_corpus_extreme_tail_panel_transport_v1.py publish-compute-release \
    --transport-contract-uri "$T230_CONTRACT_URI" \
    --transport-contract-generation "$T230_CONTRACT_GENERATION" \
    --transport-contract-sha256 "$T230_CONTRACT_SHA256" \
    --transport-contract-bytes "$T230_CONTRACT_BYTES" \
    --benchmark-uri "$(jq -er '.target_identity.uri' <<<"$benchmark_publication")" \
    --benchmark-generation "$(jq -er '.target_identity.generation' <<<"$benchmark_publication")" \
    --benchmark-sha256 "$(jq -er '.target_identity.sha256' <<<"$benchmark_publication")" \
    --benchmark-bytes "$(jq -er '.target_identity.bytes' <<<"$benchmark_publication")" \
    --execute >/tmp/compute-release.json
else
  exec env PYTHONPATH="$PYTHONPATH" "${stage[@]}"
fi
RUNTIME
}

configure_job() {
  local job="$1"
  gcloud run jobs update "$job" --project "$PROJECT" --region "$REGION" \
    --clear-volumes --clear-volume-mounts --clear-secrets \
    --clear-cloudsql-instances --clear-vpc-connector --clear-network \
    --clear-env-vars --quiet >/dev/null
  gcloud run jobs update "$job" --project "$PROJECT" --region "$REGION" \
    --image "$T230_IMAGE" --service-account "$T230_SERVICE_ACCOUNT" \
    --cpu 8 --memory 32Gi --tasks 1 --parallelism 1 --max-retries 0 \
    --task-timeout 21600s --command bash \
    --args=-ceu,'python scripts/run_corpus_extreme_tail_panel_transport_v1.py parked' \
    --add-volume type=in-memory,name=foundry-t230-runtime-evidence,size-limit=1Mi \
    --add-volume-mount volume=foundry-t230-runtime-evidence,mount-path=/etc/nfl-dfs \
    --quiet >/dev/null
}

capture_job_contract() {
  local job="$1" output="$2" raw
  raw="$(mktemp "$T230_RUN_DIR/.job-describe.XXXXXX")"
  gcloud run jobs describe "$job" --project "$PROJECT" --region "$REGION" \
    --format=json >|"$raw"
  jq -ce --arg job "$job" --arg image "$T230_IMAGE" \
    --arg service_account "$T230_SERVICE_ACCOUNT" '
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
        job:$job,image:$image,service_account:$service_account,
        cpu:"8",memory:"32Gi",task_count:1,parallelism:1,max_retries:0,
        task_timeout_seconds:21600,
        runtime_evidence_volume:{
          type:"in-memory",name:"foundry-t230-runtime-evidence",
          size_limit:"1Mi",mount_path:"/etc/nfl-dfs"
        },
        cloud_describe_exactly_validated:true
      } else error("configured Cloud Run job differs from T230 contract") end
  ' "$raw" >|"$output"
  command rm -f -- "$raw"
}

job_config_identity_path() {
  case "$1" in
    "$JOB_A") printf '%s\n' "$T230_RUN_DIR/job-a-config-identity.json" ;;
    "$JOB_B") printf '%s\n' "$T230_RUN_DIR/job-b-config-identity.json" ;;
    *) die "unknown T230 reused job" ;;
  esac
}

publish_or_replay_live_job_config() {
  local job="$1" observed publication candidate target
  observed="$(mktemp "$T230_RUN_DIR/.observed-job-config.XXXXXX")"
  capture_job_contract "$job" "$observed"
  mapfile -t config_contract_args < <(contract_cli_args)
  publication="$("$PYTHON_BIN" "$TRANSPORT" publish-job-config \
    "${config_contract_args[@]}" --job "$job" --observed-config "$observed" \
    --execute)"
  command rm -f -- "$observed"
  candidate="$(mktemp "$T230_RUN_DIR/.job-config-identity.XXXXXX")"
  jq -c '.target_identity' <<<"$publication" >|"$candidate"
  target="$(job_config_identity_path "$job")"
  install_local_equal "$candidate" "$target"
  printf '%s\n' "$target"
}

configure() {
  require_var T230_IMAGE
  require_var T230_SERVICE_ACCOUNT
  [[ "$T230_IMAGE" =~ @sha256:[0-9a-f]{64}$ ]] || die "T230_IMAGE is not digest pinned"
  configure_job "$JOB_A"
  configure_job "$JOB_B"
  publish_or_replay_live_job_config "$JOB_A" >/dev/null
  publish_or_replay_live_job_config "$JOB_B" >/dev/null
}

authority_env() {
  local file="${T230_EXECUTION_AUTHORITY_IDENTITY_FILE:-}"
  if [[ -n "$file" ]]; then
    printf '%s' "~T230_AUTHORITY_URI=$(identity_value "$file" uri)"
    printf '%s' "~T230_AUTHORITY_GENERATION=$(identity_value "$file" generation)"
    printf '%s' "~T230_AUTHORITY_SHA256=$(identity_value "$file" sha256)"
    printf '%s' "~T230_AUTHORITY_BYTES=$(identity_value "$file" bytes)"
  else
    printf '%s' '~T230_AUTHORITY_URI=~T230_AUTHORITY_GENERATION=~T230_AUTHORITY_SHA256=~T230_AUTHORITY_BYTES='
  fi
}

launch_stage() {
  require_var T230_IMAGE
  local job="$1" operation="$2" ordinal="$3" result_file="${4:-}" benchmark="${5:-0}"
  local lane0_file="${6:-}" lane1_file="${7:-}"
  local predecessor0="${8:-}" predecessor1="${9:-}"
  [[ -z "${T230_RUNTIME_ATTEMPT_ORDINAL:-}" ]] || \
    die "caller-selected runtime attempts are forbidden"
  local attempt=0
  local member="$ordinal"
  [[ "$ordinal" == "none" ]] && member="panel"
  local stem="$T230_RUN_DIR/stages/${operation}-${member}-attempt-${attempt}"
  mkdir -p "$T230_RUN_DIR/stages"
  local intent="${stem}.launch-intent"
  local response="${stem}.gcloud-response.txt"
  local stage_identity="${stem}.stage-identity.json"
  local stage_body="${stem}.stage-body.json"
  local pre_resolve=("$PYTHON_BIN" "$TRANSPORT" resolve-stage-receipt)
  mapfile -t pre_contract_args < <(contract_cli_args)
  pre_resolve+=("${pre_contract_args[@]}" --operation "$operation" \
    --output "$stage_identity" --body-output "$stage_body" --execute)
  [[ "$ordinal" != "none" ]] && pre_resolve+=(--source-ordinal "$ordinal")
  if "${pre_resolve[@]}" >/dev/null 2>&1; then
    printf '%s\n' "$stage_body"
    return 0
  fi
  mapfile -t launch_contract_args < <(contract_cli_args)
  local recover=("$PYTHON_BIN" "$TRANSPORT" recover-stage-after-core-terminal)
  recover+=("${launch_contract_args[@]}" --operation "$operation" \
    --output "$stage_identity" --body-output "$stage_body" --execute)
  [[ "$ordinal" != "none" ]] && recover+=(--source-ordinal "$ordinal")
  [[ -n "$predecessor0" ]] && recover+=(--predecessor-identity "$predecessor0")
  [[ -n "$predecessor1" ]] && recover+=(--predecessor-identity "$predecessor1")
  if [[ "$operation" != "prepare" ]]; then
    recover+=(
      --execution-authority-uri "$(identity_value "$T230_EXECUTION_AUTHORITY_IDENTITY_FILE" uri)"
      --execution-authority-generation "$(identity_value "$T230_EXECUTION_AUTHORITY_IDENTITY_FILE" generation)"
      --execution-authority-sha256 "$(identity_value "$T230_EXECUTION_AUTHORITY_IDENTITY_FILE" sha256)"
      --execution-authority-bytes "$(identity_value "$T230_EXECUTION_AUTHORITY_IDENTITY_FILE" bytes)"
    )
  fi
  if [[ "$operation" == "finish-panel" ]]; then
    recover+=(--lane-ledger "$lane0_file" --lane-ledger "$lane1_file")
  fi
  local launch_identity_file="${stem}.launch-request-identity.json"
  local resolve_launch=("$PYTHON_BIN" "$TRANSPORT" resolve-launch-request)
  resolve_launch+=("${launch_contract_args[@]}" --operation "$operation" \
    --output "$launch_identity_file" --execute)
  [[ "$ordinal" != "none" ]] && resolve_launch+=(--source-ordinal "$ordinal")
  [[ -n "$predecessor0" ]] && resolve_launch+=(--predecessor-identity "$predecessor0")
  [[ -n "$predecessor1" ]] && resolve_launch+=(--predecessor-identity "$predecessor1")
  if "${resolve_launch[@]}" >/dev/null 2>&1; then
    if "${recover[@]}" >/dev/null 2>&1; then
      printf '%s\n' "$stage_body"
      return 0
    fi
    die "durable launch request is consumed; no stage or recoverable core terminal exists, and relaunch is forbidden"
  fi
  local job_config_file
  job_config_file="$(publish_or_replay_live_job_config "$job")"
  local envs="^~^${ENABLE_ENV}=1~T230_OPERATION=${operation}~T230_SOURCE_ORDINAL=${ordinal}~T230_ATTEMPT=${attempt}~T230_BENCHMARK=${benchmark}~T230_IMAGE=${T230_IMAGE}"
  local predecessor_count=0 predecessor_file
  for predecessor_file in "$predecessor0" "$predecessor1"; do
    [[ -n "$predecessor_file" ]] || continue
    envs+="~T230_PRED${predecessor_count}_URI=$(identity_value "$predecessor_file" uri)"
    envs+="~T230_PRED${predecessor_count}_GENERATION=$(identity_value "$predecessor_file" generation)"
    envs+="~T230_PRED${predecessor_count}_SHA256=$(identity_value "$predecessor_file" sha256)"
    envs+="~T230_PRED${predecessor_count}_BYTES=$(identity_value "$predecessor_file" bytes)"
    predecessor_count=$((predecessor_count + 1))
  done
  envs+="~T230_PRED_COUNT=${predecessor_count}"
  while (( predecessor_count < 2 )); do
    envs+="~T230_PRED${predecessor_count}_URI=~T230_PRED${predecessor_count}_GENERATION=~T230_PRED${predecessor_count}_SHA256=~T230_PRED${predecessor_count}_BYTES="
    predecessor_count=$((predecessor_count + 1))
  done
  envs+="~T230_CONTRACT_URI=$(identity_value "$T230_TRANSPORT_CONTRACT_IDENTITY_FILE" uri)"
  envs+="~T230_CONTRACT_GENERATION=$(identity_value "$T230_TRANSPORT_CONTRACT_IDENTITY_FILE" generation)"
  envs+="~T230_CONTRACT_SHA256=$(identity_value "$T230_TRANSPORT_CONTRACT_IDENTITY_FILE" sha256)"
  envs+="~T230_CONTRACT_BYTES=$(identity_value "$T230_TRANSPORT_CONTRACT_IDENTITY_FILE" bytes)"
  envs+="~T230_EVIDENCE_URI=$(identity_value "$T230_IMAGE_EVIDENCE_IDENTITY_FILE" uri)"
  envs+="~T230_EVIDENCE_GENERATION=$(identity_value "$T230_IMAGE_EVIDENCE_IDENTITY_FILE" generation)"
  envs+="~T230_EVIDENCE_SHA256=$(identity_value "$T230_IMAGE_EVIDENCE_IDENTITY_FILE" sha256)"
  envs+="~T230_EVIDENCE_BYTES=$(identity_value "$T230_IMAGE_EVIDENCE_IDENTITY_FILE" bytes)"
  envs+="$(authority_env)"
  if [[ -n "$result_file" ]]; then
    envs+="~T230_RESULT_URI=$(identity_value "$result_file" uri)"
    envs+="~T230_RESULT_GENERATION=$(identity_value "$result_file" generation)"
    envs+="~T230_RESULT_SHA256=$(identity_value "$result_file" sha256)"
    envs+="~T230_RESULT_BYTES=$(identity_value "$result_file" bytes)"
  else
    envs+='~T230_RESULT_URI=~T230_RESULT_GENERATION=~T230_RESULT_SHA256=~T230_RESULT_BYTES='
  fi
  if [[ "$operation" == "finish-panel" ]]; then
    [[ -f "$lane0_file" && -f "$lane1_file" ]] || die "finalizer lane identities are absent"
    envs+="~T230_LANE0_URI=$(identity_value "$lane0_file" uri)"
    envs+="~T230_LANE0_GENERATION=$(identity_value "$lane0_file" generation)"
    envs+="~T230_LANE0_SHA256=$(identity_value "$lane0_file" sha256)"
    envs+="~T230_LANE0_BYTES=$(identity_value "$lane0_file" bytes)"
    envs+="~T230_LANE1_URI=$(identity_value "$lane1_file" uri)"
    envs+="~T230_LANE1_GENERATION=$(identity_value "$lane1_file" generation)"
    envs+="~T230_LANE1_SHA256=$(identity_value "$lane1_file" sha256)"
    envs+="~T230_LANE1_BYTES=$(identity_value "$lane1_file" bytes)"
  else
    envs+='~T230_LANE0_URI=~T230_LANE0_GENERATION=~T230_LANE0_SHA256=~T230_LANE0_BYTES='
    envs+='~T230_LANE1_URI=~T230_LANE1_GENERATION=~T230_LANE1_SHA256=~T230_LANE1_BYTES='
  fi
  if [[ -n "${T230_COMPUTE_RELEASE_IDENTITY_FILE:-}" ]] \
      && [[ "$operation" != "prepare" ]] \
      && [[ "$operation" != "run-slate" || "$ordinal" != "0" ]]; then
    envs+="~T230_COMPUTE_URI=$(identity_value "$T230_COMPUTE_RELEASE_IDENTITY_FILE" uri)"
    envs+="~T230_COMPUTE_GENERATION=$(identity_value "$T230_COMPUTE_RELEASE_IDENTITY_FILE" generation)"
    envs+="~T230_COMPUTE_SHA256=$(identity_value "$T230_COMPUTE_RELEASE_IDENTITY_FILE" sha256)"
    envs+="~T230_COMPUTE_BYTES=$(identity_value "$T230_COMPUTE_RELEASE_IDENTITY_FILE" bytes)"
  else
    envs+='~T230_COMPUTE_URI=~T230_COMPUTE_GENERATION=~T230_COMPUTE_SHA256=~T230_COMPUTE_BYTES='
  fi
  local launch_request=("$PYTHON_BIN" "$TRANSPORT" publish-launch-request)
  launch_request+=("${launch_contract_args[@]}" --operation "$operation" --execute)
  launch_request+=(--job-config-identity "$job_config_file")
  [[ "$ordinal" != "none" ]] && launch_request+=(--source-ordinal "$ordinal")
  [[ -n "$predecessor0" ]] && launch_request+=(--predecessor-identity "$predecessor0")
  [[ -n "$predecessor1" ]] && launch_request+=(--predecessor-identity "$predecessor1")
  local launch_publication
  launch_publication="$("${launch_request[@]}")"
  if [[ "$(jq -er '.target_created' <<<"$launch_publication")" != "true" ]]; then
    if "${recover[@]}" >/dev/null 2>&1; then
      printf '%s\n' "$stage_body"
      return 0
    fi
    die "durable launch request is consumed; no stage or recoverable core terminal exists, and relaunch is forbidden"
  fi
  envs+="~T230_LAUNCH_REQUEST_URI=$(jq -er '.target_identity.uri' <<<"$launch_publication")"
  envs+="~T230_LAUNCH_REQUEST_GENERATION=$(jq -er '.target_identity.generation' <<<"$launch_publication")"
  envs+="~T230_LAUNCH_REQUEST_SHA256=$(jq -er '.target_identity.sha256' <<<"$launch_publication")"
  envs+="~T230_LAUNCH_REQUEST_BYTES=$(jq -er '.target_identity.bytes' <<<"$launch_publication")"
  envs+="~T230_LAUNCH_INTENT_URI=$(jq -er '.intent_identity.uri' <<<"$launch_publication")"
  envs+="~T230_LAUNCH_INTENT_GENERATION=$(jq -er '.intent_identity.generation' <<<"$launch_publication")"
  envs+="~T230_LAUNCH_INTENT_SHA256=$(jq -er '.intent_identity.sha256' <<<"$launch_publication")"
  envs+="~T230_LAUNCH_INTENT_BYTES=$(jq -er '.intent_identity.bytes' <<<"$launch_publication")"
  envs+="~T230_LAUNCH_COMPLETION_URI=$(jq -er '.completion_identity.uri' <<<"$launch_publication")"
  envs+="~T230_LAUNCH_COMPLETION_GENERATION=$(jq -er '.completion_identity.generation' <<<"$launch_publication")"
  envs+="~T230_LAUNCH_COMPLETION_SHA256=$(jq -er '.completion_identity.sha256' <<<"$launch_publication")"
  envs+="~T230_LAUNCH_COMPLETION_BYTES=$(jq -er '.completion_identity.bytes' <<<"$launch_publication")"
  local intent_candidate
  intent_candidate="$(mktemp "$T230_RUN_DIR/.launch-intent.XXXXXX")"
  printf '%s\n' "job=$job operation=$operation ordinal=$ordinal attempt=$attempt maxRetries=0" >|"$intent_candidate"
  install_local_equal "$intent_candidate" "$intent"
  if ! gcloud run jobs execute "$job" --project "$PROJECT" --region "$REGION" \
    --wait --tasks 1 --task-timeout 21600s \
    --args="^~^-ceu~$(runtime_script)" --update-env-vars "$envs" \
    --format='value(metadata.name)' >"$response"; then
    printf '%s\n' "execution response was ambiguous or failed; durable request is consumed and will never be relaunched" >&2
  fi
  local resolve=("$PYTHON_BIN" "$TRANSPORT" resolve-stage-receipt)
  mapfile -t contract_args < <(contract_cli_args)
  resolve+=("${contract_args[@]}" --operation "$operation" --output "$stage_identity" --body-output "$stage_body" --execute)
  [[ "$ordinal" != "none" ]] && resolve+=(--source-ordinal "$ordinal")
  "${resolve[@]}" >/dev/null || die "stage is not durable yet; rerun to resolve, never relaunch this intent"
  printf '%s\n' "$stage_body"
}

prepare_panel() {
  launch_stage "$JOB_A" prepare none >/dev/null
  local body="$T230_RUN_DIR/stages/prepare-panel-attempt-0.stage-body.json"
  write_jq_identity '.exposed_identities.execution_authority_identity' "$body" \
    "$T230_RUN_DIR/execution-authority-identity.json"
}

resolve_compute_release() {
  local output="$T230_RUN_DIR/compute-release-identity.json"
  mapfile -t contract_args < <(contract_cli_args)
  "$PYTHON_BIN" "$TRANSPORT" resolve-compute-release \
    "${contract_args[@]}" --output "$output" --execute >/dev/null
  printf '%s\n' "$output"
}

require_benchmark_execution_terminal() {
  local worker_body="$1" worker_identity="$2"
  local execution_name raw projection publication identity_candidate identity_file
  execution_name="$(jq -er '.cloud_execution_name' "$worker_body")"
  raw="$(mktemp "$T230_RUN_DIR/.benchmark-execution-describe.XXXXXX")"
  projection="$(mktemp "$T230_RUN_DIR/.benchmark-execution-projection.XXXXXX")"
  gcloud run jobs executions describe "$execution_name" \
    --project "$PROJECT" --region "$REGION" --format=json \
    >|"$raw"
  jq -ce --arg execution "$execution_name" --arg job "$JOB_A" \
    --arg image "$T230_IMAGE" --arg service_account "$T230_SERVICE_ACCOUNT" '
    .spec as $outer
    | .spec.template.spec as $task
    | $task.containers as $containers
    | [.status.conditions[]? | select(.type == "Completed") | .status] as $completed
    | if (
        ((.metadata.name == $execution) or (.metadata.name | endswith("/" + $execution)))
        and .metadata.labels["run.googleapis.com/job"] == $job
        and ($completed | length == 1)
        and ($completed[0] == "True" or $completed[0] == "False")
        and (.status.completionTime | type == "string" and endswith("Z"))
        and $outer.taskCount == 1
        and $outer.parallelism == 1
        and ($containers | type == "array" and length == 1)
        and $containers[0].image == $image
        and $containers[0].command == ["bash"]
        and ($containers[0].args | type == "array" and length == 2
          and .[0] == "-ceu"
          and (.[1] | contains("run_corpus_extreme_tail_panel_transport_v1.py")))
        and $containers[0].resources.limits == {cpu:"8",memory:"32Gi"}
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
        job:$job,image:$image,service_account:$service_account,
        cpu:"8",memory:"32Gi",task_count:1,parallelism:1,max_retries:0,
        task_timeout_seconds:21600,
        runtime_evidence_volume:{
          type:"in-memory",name:"foundry-t230-runtime-evidence",
          size_limit:"1Mi",mount_path:"/etc/nfl-dfs"
        },
        cloud_describe_exactly_validated:true,
        execution_name:$execution,completed_status:$completed[0],
        completion_time:.status.completionTime,
        cloud_execution_describe_exactly_validated:true
      } else error("benchmark execution is nonterminal or its envelope differs") end
  ' "$raw" >|"$projection"
  command rm -f -- "$raw"
  mapfile -t terminal_contract_args < <(contract_cli_args)
  publication="$("$PYTHON_BIN" "$TRANSPORT" \
    publish-benchmark-execution-terminal "${terminal_contract_args[@]}" \
    --worker-stage-receipt-uri "$(identity_value "$worker_identity" uri)" \
    --worker-stage-receipt-generation "$(identity_value "$worker_identity" generation)" \
    --worker-stage-receipt-sha256 "$(identity_value "$worker_identity" sha256)" \
    --worker-stage-receipt-bytes "$(identity_value "$worker_identity" bytes)" \
    --observed-terminal "$projection" --execute)"
  command rm -f -- "$projection"
  identity_candidate="$(mktemp "$T230_RUN_DIR/.benchmark-terminal-identity.XXXXXX")"
  jq -c '.target_identity' <<<"$publication" >|"$identity_candidate"
  identity_file="$T230_RUN_DIR/benchmark-execution-terminal-identity.json"
  install_local_equal "$identity_candidate" "$identity_file"
  printf '%s\n' "$identity_file"
}

run_benchmark() {
  require_var T230_IMAGE
  require_var T230_EXECUTION_AUTHORITY_IDENTITY_FILE
  if resolve_compute_release >/dev/null 2>&1; then
    return 0
  fi
  local worker_identity="$T230_RUN_DIR/stages/run-slate-0-attempt-0.stage-identity.json"
  local worker_body="$T230_RUN_DIR/stages/run-slate-0-attempt-0.stage-body.json"
  mapfile -t benchmark_contract_args < <(contract_cli_args)
  if "$PYTHON_BIN" "$TRANSPORT" resolve-stage-receipt \
      "${benchmark_contract_args[@]}" --operation run-slate --source-ordinal 0 \
      --output "$worker_identity" --body-output "$worker_body" --execute \
      >/dev/null 2>&1; then
    if "$PYTHON_BIN" "$TRANSPORT" resume-benchmark-transaction \
        "${benchmark_contract_args[@]}" --execute >/dev/null 2>&1; then
      resolve_compute_release >/dev/null
      return 0
    fi
    local terminal_identity_file
    terminal_identity_file="$(require_benchmark_execution_terminal \
      "$worker_body" "$worker_identity")"
    "$PYTHON_BIN" "$TRANSPORT" publish-benchmark-terminal-abort \
      "${benchmark_contract_args[@]}" \
      --worker-stage-receipt-uri "$(identity_value "$worker_identity" uri)" \
      --worker-stage-receipt-generation "$(identity_value "$worker_identity" generation)" \
      --worker-stage-receipt-sha256 "$(identity_value "$worker_identity" sha256)" \
      --worker-stage-receipt-bytes "$(identity_value "$worker_identity" bytes)" \
      --benchmark-execution-terminal-uri "$(identity_value "$terminal_identity_file" uri)" \
      --benchmark-execution-terminal-generation "$(identity_value "$terminal_identity_file" generation)" \
      --benchmark-execution-terminal-sha256 "$(identity_value "$terminal_identity_file" sha256)" \
      --benchmark-execution-terminal-bytes "$(identity_value "$terminal_identity_file" bytes)" \
      --execute >/dev/null
    die "worker zero is durable without its benchmark release; this run is terminal and requires a new frozen run id/prefix"
  fi
  local prepare_identity="$T230_RUN_DIR/stages/prepare-panel-attempt-0.stage-identity.json"
  [[ -f "$prepare_identity" ]] || die "prepare stage identity is absent"
  launch_stage "$JOB_A" run-slate 0 '' 1 '' '' "$prepare_identity" >/dev/null
  resolve_compute_release >/dev/null || \
    die "benchmark did not produce the exact compute release; scale-out forbidden"
}

run_lane() {
  local lane="$1" job start end ordinal
  if [[ "$lane" == "0" ]]; then job="$JOB_A"; start=0; end=27; else job="$JOB_B"; start=28; end=53; fi
  local lane_dir="$T230_RUN_DIR/lane-${lane}"
  mkdir -p "$lane_dir"
  for ordinal in $(seq "$start" "$end"); do
    local worker_body result_file verifier_body predecessor
    if [[ "$ordinal" == "$start" ]]; then
      predecessor="$T230_RUN_DIR/stages/prepare-panel-attempt-0.stage-identity.json"
    else
      predecessor="$T230_RUN_DIR/stages/verify-slate-$((ordinal - 1))-attempt-0.stage-identity.json"
    fi
    [[ -f "$predecessor" ]] || die "worker predecessor identity is absent"
    worker_body="$(launch_stage "$job" run-slate "$ordinal" '' 0 '' '' "$predecessor")"
    result_file="$lane_dir/result-${ordinal}.json"
    write_jq_identity '.exposed_identities.result_identity' "$worker_body" "$result_file"
    predecessor="$T230_RUN_DIR/stages/run-slate-${ordinal}-attempt-0.stage-identity.json"
    verifier_body="$(launch_stage "$job" verify-slate "$ordinal" "$result_file" 0 '' '' "$predecessor")"
    write_jq_identity '.exposed_identities.acceptance_identity' "$verifier_body" \
      "$lane_dir/acceptance-${ordinal}.json"
  done
  local args=()
  for ordinal in $(seq "$start" "$end"); do
    args+=(--stage-receipt-identity "$T230_RUN_DIR/stages/run-slate-${ordinal}-attempt-0.stage-identity.json")
    args+=(--stage-receipt-identity "$T230_RUN_DIR/stages/verify-slate-${ordinal}-attempt-0.stage-identity.json")
  done
  mapfile -t contract_args < <(contract_cli_args)
  "$PYTHON_BIN" "$TRANSPORT" build-lane-ledger "${contract_args[@]}" \
    --lane-ordinal "$lane" "${args[@]}" --output "$lane_dir/ledger.json" --execute >/dev/null
  local publication_candidate
  publication_candidate="$(mktemp "$T230_RUN_DIR/.ledger-publication.XXXXXX")"
  "$PYTHON_BIN" "$TRANSPORT" publish-lane-ledger "${contract_args[@]}" \
    --lane-ordinal "$lane" --lane-ledger "$lane_dir/ledger.json" --execute \
    | jq -c '.target_identity' >|"$publication_candidate"
  install_local_equal "$publication_candidate" "$lane_dir/ledger-identity.json"
}

run_panel() {
  require_var T230_EXECUTION_AUTHORITY_IDENTITY_FILE
  T230_COMPUTE_RELEASE_IDENTITY_FILE="$(resolve_compute_release)" || \
    die "compute release is absent; scale-out forbidden"
  export T230_COMPUTE_RELEASE_IDENTITY_FILE
  local lane_a_pid lane_b_pid lane_a_status=0 lane_b_status=0
  run_lane 0 &
  lane_a_pid=$!
  run_lane 1 &
  lane_b_pid=$!
  if wait "$lane_a_pid"; then
    lane_a_status=0
  else
    lane_a_status=$?
  fi
  if wait "$lane_b_pid"; then
    lane_b_status=0
  else
    lane_b_status=$?
  fi
  local status_candidate status_file
  status_candidate="$(mktemp "$T230_RUN_DIR/.lane-controller-status.XXXXXX")"
  jq -cn --argjson lane_a "$lane_a_status" --argjson lane_b "$lane_b_status" \
    '{lane_a_exit_status:$lane_a,lane_b_exit_status:$lane_b,
      both_background_controllers_joined:true,
      automatic_relaunch_licensed:false}' >|"$status_candidate"
  status_file="$T230_RUN_DIR/lane-controller-status-${lane_a_status}-${lane_b_status}.json"
  install_local_equal "$status_candidate" "$status_file"
  if (( lane_a_status != 0 || lane_b_status != 0 )); then
    die "lane controllers were both joined; lane A=$lane_a_status lane B=$lane_b_status"
  fi
}

finish_panel() {
  require_var T230_EXECUTION_AUTHORITY_IDENTITY_FILE
  local lane0="$T230_RUN_DIR/lane-0/ledger-identity.json"
  local lane1="$T230_RUN_DIR/lane-1/ledger-identity.json"
  [[ -f "$lane0" && -f "$lane1" ]] || die "both lane ledgers are required"
  T230_COMPUTE_RELEASE_IDENTITY_FILE="$(resolve_compute_release)" || \
    die "compute release is absent; finalization forbidden"
  export T230_COMPUTE_RELEASE_IDENTITY_FILE
  launch_stage "$JOB_A" finish-panel none '' 0 "$lane0" "$lane1" "$lane0" "$lane1" >/dev/null
  local body="$T230_RUN_DIR/stages/finish-panel-panel-attempt-0.stage-body.json"
  write_jq_identity '.exposed_identities.panel_release_identity' "$body" \
    "$T230_RUN_DIR/panel-release-identity.json"
}

mode="${1:-parked}"
case "$mode" in
  parked) printf '%s\n' '{"state":"parked","default_off":true,"maxRetries":0}' ;;
  bootstrap) bootstrap "${2:-}" ;;
  configure) require_gate "${2:-}"; require_var T230_SERVICE_ACCOUNT; configure ;;
  prepare) require_gate "${2:-}"; prepare_panel ;;
  benchmark) require_gate "${2:-}"; run_benchmark ;;
  run-panel) require_gate "${2:-}"; run_panel ;;
  finish-panel) require_gate "${2:-}"; finish_panel ;;
  *) die "mode must be parked, bootstrap, configure, prepare, benchmark, run-panel, or finish-panel" ;;
esac
