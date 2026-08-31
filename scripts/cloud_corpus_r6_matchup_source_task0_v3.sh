#!/usr/bin/env bash
# Exact-name controller for task0 worker -> distinct verifier -> full source-v3.
set -euo pipefail

die() { printf '%s\n' "ERROR: $*" >&2; exit 2; }

PROJECT=nfl-predictions-503414
REGION=us-central1
JOB=atlas-cbc-32g-full-2023-w8-v1
EXPECTED_JOB_UID=1f4bcf0a-2300-4afa-9fc1-9981844c8275
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
SCRIPT=scripts/cloud_corpus_r6_matchup_source_task0_v3.sh
TASK0_RUNNER=scripts/run_corpus_r6_matchup_source_task0_v3.py
SOURCE_RUNNER=scripts/run_corpus_r6_matchup_source_batch_v3.py
PAYLOAD_B64_ENV=R6_MATCHUP_SOURCE_TASK0_PAYLOAD_B64
PAYLOAD_SHA_ENV=R6_MATCHUP_SOURCE_TASK0_PAYLOAD_SHA256
MODE_ENV=R6_MATCHUP_SOURCE_TASK0_MODE
OUTCOMES_ENV=R6_MATCHUP_SOURCE_TASK0_OUTCOMES_ALLOWED
WORKER_EXECUTION_ENV=CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_WORKER_EXECUTION
VERIFIER_EXECUTION_ENV=CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_VERIFIER_EXECUTION
PUBLISHER_EXECUTION_ENV=CORPUS_R6_MATCHUP_SOURCE_V3_PUBLISHER_EXECUTION
HOST_ENABLE_ENV=CORPUS_R6_MATCHUP_SOURCE_TASK0_CLOUD_RELEASE
HOST_ENABLE_VALUE=I_UNDERSTAND_SOURCE_V3_TASK0_CHAIN
# The provider spec binds the uncompressed canonical JSON.  Only transport
# through the Cloud Run environment uses exact deterministic gzip-n9/base64.
MAX_PAYLOAD_BYTES=262144
MAX_PAYLOAD_BASE64_BYTES=30000
EMPTY_JSON_SHA256=44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a
CONTROLLER_EVIDENCE_PREFIX=gs://nfl-predictions-503414-corpus-source/research/corpus-r6-matchup-source-controller-v3

decode_exact_payload() {
  [[ $# -eq 3 ]] || die "decode-exact-payload requires encoded bytes, SHA and target"
  local encoded=$1 expected_sha=$2 target=$3 size compressed recompressed
  [[ "$encoded" =~ ^[A-Za-z0-9+/]+={0,2}$ && \
     "$expected_sha" =~ ^[0-9a-f]{64}$ ]] || die "payload identity differs"
  [[ "${#encoded}" -le "$MAX_PAYLOAD_BASE64_BYTES" ]] || \
    die "compressed payload environment bound differs"
  compressed=$target.gzip
  recompressed=$target.recompressed.gzip
  umask 077
  printf '%s' "$encoded" | base64 --decode >"$compressed" || \
    die "payload base64 differs"
  [[ -f "$compressed" && ! -L "$compressed" && \
     "$(base64 -w0 "$compressed")" == "$encoded" ]] || \
    die "payload base64 is not canonical"
  gzip -t "$compressed" || die "payload gzip differs"
  gzip -dc "$compressed" >"$target" || die "payload decompression differs"
  [[ -f "$target" && ! -L "$target" ]] || die "payload file differs"
  size=$(stat -c '%s' "$target")
  [[ "$size" -ge 1 && "$size" -le "$MAX_PAYLOAD_BYTES" ]] || \
    die "payload byte bound differs"
  [[ "$(sha256sum "$target" | awk '{print $1}')" == "$expected_sha" ]] || \
    die "payload SHA differs"
  gzip -n -9 -c "$target" >"$recompressed" || \
    die "payload deterministic compression differs"
  [[ "$(base64 -w0 "$recompressed")" == "$encoded" ]] || \
    die "payload gzip encoding is not exact deterministic gzip-n9"
}

decode_payload() {
  local target=$1
  [[ "${!PAYLOAD_B64_ENV:-}" && "${!PAYLOAD_SHA_ENV:-}" =~ ^[0-9a-f]{64}$ ]] || \
    die "payload identity is absent"
  decode_exact_payload "${!PAYLOAD_B64_ENV}" "${!PAYLOAD_SHA_ENV}" "$target"
}

container_gate() {
  local mode=$1
  [[ "${!MODE_ENV:-}" == "$mode" && "${!OUTCOMES_ENV:-}" == false ]] || \
    die "container mode/outcome gate differs"
  [[ "${CODE_SHA:-}" =~ ^[0-9a-f]{40}$ && \
     "${IMAGE_SOURCE_COMMIT_SHA:-}" == "$CODE_SHA" && \
     "$(cat /usr/local/share/nfl/SOURCE_COMMIT)" == "$CODE_SHA" ]] || \
    die "container source commit differs"
  [[ "$(git -C /app rev-parse HEAD)" == "$CODE_SHA" && \
     -z "$(git -C /app status --porcelain --untracked-files=all)" ]] || \
    die "container checkout is not exact-clean Commit B"
  [[ "${IMAGE_DIGEST:-}" =~ ^sha256:[0-9a-f]{64}$ && \
     "${IMAGE_URI:-}" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ && \
     "${IMAGE_URI##*@}" == "$IMAGE_DIGEST" ]] || die "container image differs"
  [[ "${BUILD_ID:-}" =~ ^[0-9a-f-]{36}$ ]] || die "container build ID differs"
  command -v gzip >/dev/null || die "container gzip dependency differs"
  [[ "${CLOUD_RUN_TASK_INDEX:-}" == 0 && "${CLOUD_RUN_TASK_COUNT:-}" == 1 && \
     "${CLOUD_RUN_TASK_ATTEMPT:-}" == 0 && \
     "${CLOUD_RUN_EXECUTION:-}" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
    die "container task/execution boundary differs"
}

container_run() {
  [[ $# -eq 1 ]] || die "container-run requires one mode"
  local mode=$1 work payload
  container_gate "$mode"
  work=$(mktemp -d /tmp/source-task0-v3.XXXXXX)
  trap "rm -rf '$work'" EXIT
  case "$mode" in
    worker)
      [[ "${TASK0_RUN_ID:-}" =~ ^[a-z0-9][a-z0-9-]{7,80}$ ]] || \
        die "task0 run ID differs"
      CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_WORKER=I_UNDERSTAND_SOURCE_V3_TASK0_WORKER \
        /usr/local/bin/python3.11 -I "/app/$TASK0_RUNNER" \
        --action worker --run-id "$TASK0_RUN_ID"
      ;;
    verify)
      payload=$work/worker-provider-receipt.json
      decode_payload "$payload"
      /usr/local/bin/python3.11 -I "/app/$TASK0_RUNNER" \
        --action validate-provider-receipt --provider-receipt "$payload" >/dev/null
      jq -e '
        .schema_version == "corpus-r6-matchup-source-task0-provider-receipt/v3" and
        .complete == true and .provider_execution_spec.phase == "worker" and
        .provider_execution_spec.execution_name ==
          .operator_output.worker_execution_name' "$payload" >/dev/null || \
        die "worker provider receipt differs"
      jq -c '.operator_output.worker_result_identity' "$payload" \
        >"$work/worker-result-identity.json" || die "worker result identity differs"
      CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_VERIFY=I_UNDERSTAND_SOURCE_V3_TASK0_VERIFY \
        /usr/local/bin/python3.11 -I "/app/$TASK0_RUNNER" \
        --action verify --worker-result-identity "$work/worker-result-identity.json"
      ;;
    publish)
      [[ "${TASK0_RUN_ID:-}" =~ ^[a-z0-9][a-z0-9-]{7,80}$ ]] || \
        die "source run ID differs"
      payload=$work/verifier-provider-receipt.json
      decode_payload "$payload"
      jq -e '
        keys == ["bytes","generation","sha256","uri"] and
        (.generation | test("^[1-9][0-9]*$")) and
        (.sha256 | test("^[0-9a-f]{64}$")) and
        (.bytes | type) == "number" and .bytes > 0 and
        (.uri | test("^gs://nfl-predictions-503414-corpus-source/research/corpus-r6-matchup-source-controller-v3/.+/verify/.+/provider-receipt\\.json$"))' \
        "$payload" >/dev/null || die "verifier provider receipt identity differs"
      CORPUS_R6_MATCHUP_SOURCE_BATCH_V3_PUBLISH=1 \
        /usr/local/bin/python3.11 -I -c '
import json, sys
from nfl_dfs.research import corpus_r6_matchup_source_task0_v3 as task0
from nfl_dfs.research import corpus_r6_matchup_source_batch_outer_candidate_authority_v3 as batch
with open(sys.argv[1], "r", encoding="utf-8") as handle:
    identity = json.load(handle)
authorization = task0.authorize_full_publication_v3(
    identity, expected_run_id=sys.argv[2]
)
result = batch.publish_matchup_source_batch_outer_candidate_authority_v3(
    run_id=sys.argv[2], task0_authorization=authorization
)
result = task0._provider_publication_stdout_v3(result)
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
' "$payload" "$TASK0_RUN_ID"
      ;;
    reopen)
      payload=$work/publication-provider-receipt-identity.json
      decode_payload "$payload"
      jq -e '
        keys == ["bytes","generation","sha256","uri"] and
        (.generation | test("^[1-9][0-9]*$")) and
        (.sha256 | test("^[0-9a-f]{64}$")) and
        (.bytes | type) == "number" and .bytes > 0 and
        (.uri | test("^gs://nfl-predictions-503414-corpus-source/research/corpus-r6-matchup-source-controller-v3/.+/publish/.+/provider-receipt\\.json$"))' \
        "$payload" >/dev/null || die "publication provider receipt identity differs"
      /usr/local/bin/python3.11 -I -c '
import json, sys
from nfl_dfs.research import corpus_r6_matchup_source_task0_v3 as task0
with open(sys.argv[1], "r", encoding="utf-8") as handle:
    identity = json.load(handle)
result = task0.independently_reopen_provider_publication_v3(
    publication_provider_receipt_identity=identity
)
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
' "$payload"
      ;;
    *) die "container mode differs" ;;
  esac
}

case "${1:-}" in
  container-help)
    printf '%s\n' 'container modes: worker verify publish reopen'
    exit 0
    ;;
  container-run)
    shift
    container_run "$@"
    exit 0
    ;;
esac

[[ "${!HOST_ENABLE_ENV:-}" == "$HOST_ENABLE_VALUE" ]] || \
  die "cloud chain is disabled; set $HOST_ENABLE_ENV=$HOST_ENABLE_VALUE"
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || die "repository root unavailable"
release_paths=(
  Dockerfile.corpus-r6-matchup-source-v3
  Dockerfile.corpus-r6-matchup-source-v3.dockerignore
  cloudbuild.corpus-r6-matchup-source-v3.yaml
  pyproject.toml README.md
  "$SCRIPT" "$TASK0_RUNNER" "$SOURCE_RUNNER"
  src/nfl_dfs/research/corpus_r6_matchup_source_task0_v3.py
  src/nfl_dfs/research/corpus_r6_matchup_source_batch_outer_candidate_authority_v3.py
  src/nfl_dfs/research/corpus_r6_matchup_component_producer_v1.py
  src/nfl_dfs/research/corpus_r6_matchup_source_operator_v2.py
  src/nfl_dfs/research/corpus_r6_matchup_source_release_v1.py
)
[[ $# -ge 5 && $# -le 6 ]] || \
  die "usage: $0 {worker|verify|publish|reopen|result} IMAGE@sha256:DIGEST CODE_SHA BUILD_ID TARGET [PREDECESSOR_EXECUTION]"
action=$1 image=$2 code=$3 build_id=$4 target=$5 extra=${6:-}
[[ "$action" =~ ^(worker|verify|publish|reopen|result)$ ]] || die "action differs"
[[ "$image" =~ ^us-central1-docker\.pkg\.dev/${PROJECT}/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || \
  die "image must be immutable"
[[ "$code" =~ ^[0-9a-f]{40}$ && "$build_id" =~ ^[0-9a-f-]{36}$ ]] || \
  die "code/build identity differs"
[[ "$(git -C "$ROOT" rev-parse HEAD)" == "$code" && \
   "$(git -C "$ROOT" rev-parse --verify 'refs/remotes/origin/main^{commit}')" == "$code" ]] || \
  die "Commit B must equal durable origin/main"
for path in "${release_paths[@]}"; do
  git -C "$ROOT" cat-file -e "${code}:${path}" || die "release path is untracked: $path"
  [[ -z "$(git -C "$ROOT" status --porcelain --untracked-files=all -- "$path")" ]] || \
    die "release path differs from Commit B: $path"
done

mkdir -p "$ROOT/.build-contexts"
work=$(mktemp -d "$ROOT/.build-contexts/source-task0-controller.XXXXXX")
trap 'rm -rf "$work"' EXIT
digest=${image##*@}
gcloud builds describe "$build_id" --project "$PROJECT" --format=json >"$work/build.json"
jq -e --arg id "$build_id" --arg code "$code" --arg digest "$digest" '
  .id == $id and .status == "SUCCESS" and
  .sourceProvenance.resolvedGitSource.revision == $code and
  any(.results.images[]?; .digest == $digest)' "$work/build.json" >/dev/null || \
  die "provider build/image/Commit-B binding differs"

persist_controller_artifact() {
  [[ $# -eq 6 ]] || die "persist-controller-artifact arguments differ"
  local source=$1 run=$2 phase=$3 execution=$4 filename=$5 output=$6 uri
  [[ "$run" =~ ^[a-z0-9][a-z0-9-]{7,80}$ && \
     "$phase" =~ ^(worker|verify|publish|reopen)$ && \
     "$execution" =~ ^${JOB}-[a-z0-9]{5}$ && \
     "$filename" =~ ^[a-z0-9-]+\.json$ && -s "$source" ]] || \
    die "controller evidence identity differs"
  uri=$CONTROLLER_EVIDENCE_PREFIX/$run/$phase/$execution/$filename
  "$ROOT/.venv/bin/python" -I -c '
import json, pathlib, sys
from nfl_dfs.research import corpus_r6_matchup_batch_candidate_authority_v1 as mechanics
source = pathlib.Path(sys.argv[1])
uri = sys.argv[2]
raw = source.read_bytes()
transport = mechanics._trusted_gcs_transport_v1(expected_write_uris=(uri,))
identity = transport.publish_create_once(uri, raw)
if transport.read_exact(identity) != raw:
    raise SystemExit("controller evidence exact reopen differs")
print(json.dumps(identity, sort_keys=True, separators=(",", ":")))
' "$source" "$uri" >"$output" || die "controller evidence persistence differs"
  [[ "$(wc -l <"$output")" == 1 ]] || die "controller evidence identity differs"
}

bind_controller_provider_receipt() {
  [[ $# -eq 4 ]] || die "bind-controller-provider-receipt arguments differ"
  local spec=$1 operator=$2 predecessor=$3 output=$4
  "$ROOT/.venv/bin/python" -I -c '
import json, pathlib, sys
from nfl_dfs.research import corpus_r6_matchup_source_task0_v3 as task0
def load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
predecessor = None if sys.argv[3] == "DISABLED" else load(sys.argv[3])
receipt = task0._build_task0_provider_receipt_v3(
    provider_execution_spec=load(sys.argv[1]),
    operator_output=load(sys.argv[2]),
    worker_provider_receipt=predecessor,
)
print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
' "$spec" "$operator" "$predecessor" >"$output" || \
    die "controller provider receipt binding differs"
}

exact_reopen_controller_provider_receipt() {
  [[ $# -eq 2 ]] || die "exact-reopen-controller-provider-receipt arguments differ"
  local identity=$1 output=$2
  "$ROOT/.venv/bin/python" -I -c '
import json, pathlib, sys
from nfl_dfs.research import corpus_r6_matchup_source_task0_v3 as task0
identity = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
receipt, reopened_identity = task0._exact_reopen_provider_receipt_v3(identity)
if reopened_identity != identity:
    raise SystemExit("controller provider receipt identity projection differs")
print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
' "$identity" >"$output" || die "controller provider receipt exact reopen differs"
}

collect_result() {
  local execution=$1 output=$2 phase execution_json logs_json provider_spec
  local operator_output operator_stdout request_payload payload_b64 payload_sha payload_bytes
  local request_run_id bound_worker_execution bound_verifier_execution
  local bound_publisher_execution
  [[ "$execution" =~ ^${JOB}-[a-z0-9]{5}$ ]] || die "execution name differs"
  execution_json="$work/execution-$execution.json"
  logs_json="$work/logs-$execution.json"
  provider_spec="$output.provider-spec.json"
  operator_output="$output.operator-output.json"
  operator_stdout="$output.operator-stdout.json"
  request_payload="$output.request-payload.json"
  gcloud run jobs executions describe "$execution" --project "$PROJECT" \
    --region "$REGION" --format=json >"$execution_json"
  phase=$(jq -er --arg script "/app/$SCRIPT" '
    .spec.template.spec.containers[0].args as $args |
    if $args == [$script,"container-run","worker"] then "worker"
    elif $args == [$script,"container-run","verify"] then "verify"
    elif $args == [$script,"container-run","publish"] then "publish"
    elif $args == [$script,"container-run","reopen"] then "reopen"
    else error("execution phase differs") end' "$execution_json") || \
    die "execution phase differs"
  jq -e --arg execution "$execution" --arg image "$image" --arg job "$JOB" \
    --arg phase "$phase" --arg code "$code" --arg build "$build_id" \
    --arg digest "$digest" --arg service "$SERVICE_ACCOUNT" \
    --arg expected_job_uid "$EXPECTED_JOB_UID" --arg mode_env "$MODE_ENV" \
    --arg outcomes_env "$OUTCOMES_ENV" --arg payload_b64_env "$PAYLOAD_B64_ENV" \
    --arg payload_sha_env "$PAYLOAD_SHA_ENV" '
    .spec.template.spec.containers as $containers |
    ($containers[0]) as $container |
    ($container.env // []) as $env_rows |
    ($env_rows | map(select((.name | type) == "string" and
      (.value | type) == "string") | {key:.name,value:.value}) |
      from_entries) as $env |
    .metadata.name == $execution and
    (.metadata.uid | type) == "string" and
    (.metadata.uid |
      test("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")) and
    .metadata.labels["run.googleapis.com/job"] == $job and
    .metadata.labels["run.googleapis.com/jobUid"] == $expected_job_uid and
    (.metadata.labels["run.googleapis.com/jobGeneration"] | type) == "string" and
    (.metadata.labels["run.googleapis.com/jobGeneration"] |
      test("^[1-9][0-9]*$")) and
    any(.status.conditions[]?; .type == "Completed" and .status == "True") and
    (.status.completionTime | type) == "string" and
    (.status.completionTime |
      test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z$")) and
    (.status.succeededCount // 0) == 1 and (.status.failedCount // 0) == 0 and
    (.status.cancelledCount // 0) == 0 and (.status.runningCount // 0) == 0 and
    .spec.taskCount == 1 and .spec.parallelism == 1 and
    .spec.template.spec.maxRetries == 0 and
    (.spec.template.spec.timeoutSeconds | tostring) == "86400s" and
    .spec.template.spec.serviceAccountName == $service and
    ($containers | length) == 1 and
    $container.image == $image and
    $container.command == ["/bin/bash"] and
    $container.args == ["/app/scripts/cloud_corpus_r6_matchup_source_task0_v3.sh",
      "container-run",$phase] and
    $container.resources.limits == {"cpu":"8","memory":"32Gi"} and
    ($env_rows | length) == ($env | length) and
    ($env | keys | sort) == ([
      "BUILD_ID","CODE_SHA","CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_DIGEST",
      "CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_REFERENCE",
      "CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_SOURCE_COMMIT",
      "CORPUS_R6_MATCHUP_SOURCE_V3_PUBLISHER_EXECUTION",
      "CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_VERIFIER_EXECUTION",
      "CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_WORKER_EXECUTION",
      "IMAGE_DIGEST","IMAGE_SOURCE_COMMIT_SHA","IMAGE_URI","TASK0_RUN_ID",
      $mode_env,$outcomes_env,$payload_b64_env,$payload_sha_env] | sort) and
    $env.CODE_SHA == $code and $env.IMAGE_SOURCE_COMMIT_SHA == $code and
    $env.IMAGE_DIGEST == $digest and $env.IMAGE_URI == $image and
    $env.BUILD_ID == $build and
    $env.CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_DIGEST == $digest and
    $env.CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_REFERENCE == $image and
    $env.CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_SOURCE_COMMIT == $code and
    $env[$mode_env] == $phase and $env[$outcomes_env] == "false" and
    ($env.TASK0_RUN_ID | test("^[a-z0-9][a-z0-9-]{7,80}$")) and
    ($env[$payload_b64_env] | type) == "string" and
    ($env[$payload_b64_env] | length) > 0 and
    ($env[$payload_sha_env] | test("^[0-9a-f]{64}$")) and
    ($env.CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_WORKER_EXECUTION |
      test("^(DISABLED|atlas-cbc-32g-full-2023-w8-v1-[a-z0-9]{5})$")) and
    ($env.CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_VERIFIER_EXECUTION |
      test("^(DISABLED|atlas-cbc-32g-full-2023-w8-v1-[a-z0-9]{5})$")) and
    ($env.CORPUS_R6_MATCHUP_SOURCE_V3_PUBLISHER_EXECUTION |
      test("^(DISABLED|atlas-cbc-32g-full-2023-w8-v1-[a-z0-9]{5})$"))' \
    "$execution_json" >/dev/null || \
    die "execution is not exact terminal success"

  payload_b64=$(jq -er --arg key "$PAYLOAD_B64_ENV" '
    (.spec.template.spec.containers[0].env |
      map({key:.name,value:.value}) | from_entries)[$key]' "$execution_json")
  payload_sha=$(jq -er --arg key "$PAYLOAD_SHA_ENV" '
    (.spec.template.spec.containers[0].env |
      map({key:.name,value:.value}) | from_entries)[$key]' "$execution_json")
  request_run_id=$(jq -er '
    (.spec.template.spec.containers[0].env |
      map({key:.name,value:.value}) | from_entries).TASK0_RUN_ID' "$execution_json")
  bound_worker_execution=$(jq -er '
    (.spec.template.spec.containers[0].env |
      map({key:.name,value:.value}) | from_entries)
      .CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_WORKER_EXECUTION' "$execution_json")
  bound_verifier_execution=$(jq -er '
    (.spec.template.spec.containers[0].env |
      map({key:.name,value:.value}) | from_entries)
      .CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_VERIFIER_EXECUTION' "$execution_json")
  bound_publisher_execution=$(jq -er '
    (.spec.template.spec.containers[0].env |
      map({key:.name,value:.value}) | from_entries)
      .CORPUS_R6_MATCHUP_SOURCE_V3_PUBLISHER_EXECUTION' "$execution_json")
  decode_exact_payload "$payload_b64" "$payload_sha" "$request_payload"
  payload_bytes=$(stat -c '%s' "$request_payload")

  case "$phase" in
    worker)
      [[ "$payload_sha" == "$EMPTY_JSON_SHA256" && "$payload_bytes" == 2 && \
         "$bound_worker_execution" == DISABLED && \
         "$bound_verifier_execution" == DISABLED && \
         "$bound_publisher_execution" == DISABLED ]] || \
        die "worker request provider boundary differs"
      ;;
    verify)
      "$ROOT/.venv/bin/python" "$ROOT/$TASK0_RUNNER" \
        --action validate-provider-receipt \
        --provider-receipt "$request_payload" >/dev/null || \
        die "worker provider receipt validation differs"
      jq -e --arg worker "$bound_worker_execution" --arg run "$request_run_id" '
        .schema_version == "corpus-r6-matchup-source-task0-provider-receipt/v3" and
        .complete == true and .provider_execution_spec.phase == "worker" and
        .provider_execution_spec.execution_name == $worker and
        .operator_output.worker_execution_name == $worker and
        .operator_output.run_id == $run and
        (.worker_provider_receipt | not)' "$request_payload" >/dev/null || \
        die "verifier predecessor/provider boundary differs"
      [[ "$bound_worker_execution" != DISABLED && \
         "$bound_verifier_execution" == DISABLED && \
         "$bound_publisher_execution" == DISABLED ]] || \
        die "verifier execution binding differs"
      ;;
    publish)
      exact_reopen_controller_provider_receipt \
        "$request_payload" "$work/verifier-predecessor.json"
      "$ROOT/.venv/bin/python" "$ROOT/$TASK0_RUNNER" \
        --action validate-provider-receipt \
        --provider-receipt "$work/verifier-predecessor.json" >/dev/null || \
        die "verifier provider receipt validation differs"
      jq -e --arg worker "$bound_worker_execution" \
        --arg verifier "$bound_verifier_execution" --arg run "$request_run_id" '
        .schema_version == "corpus-r6-matchup-source-task0-provider-receipt/v3" and
        .complete == true and .provider_execution_spec.phase == "verify" and
        .provider_execution_spec.execution_name == $verifier and
        .operator_output.verifier_execution_name == $verifier and
        .operator_output.worker_execution_name == $worker and
        .operator_output.run_id == $run and
        .worker_provider_receipt.provider_execution_spec.phase == "worker" and
        .worker_provider_receipt.provider_execution_spec.execution_name == $worker' \
        "$work/verifier-predecessor.json" >/dev/null || \
        die "publisher predecessor/provider boundary differs"
      [[ "$bound_worker_execution" != DISABLED && \
         "$bound_verifier_execution" != DISABLED && \
         "$bound_worker_execution" != "$bound_verifier_execution" && \
         "$bound_publisher_execution" == DISABLED ]] || \
        die "publisher execution binding differs"
      ;;
    reopen)
      jq -e --arg publisher "$bound_publisher_execution" '
        keys == ["bytes","generation","sha256","uri"] and
        (.generation | test("^[1-9][0-9]*$")) and
        (.sha256 | test("^[0-9a-f]{64}$")) and
        (.uri | contains("/publish/" + $publisher + "/provider-receipt.json"))' \
        "$request_payload" >/dev/null || \
        die "independent reopen predecessor identity differs"
      exact_reopen_controller_provider_receipt \
        "$request_payload" "$work/publish-predecessor.json"
      "$ROOT/.venv/bin/python" "$ROOT/$TASK0_RUNNER" \
        --action validate-provider-receipt \
        --provider-receipt "$work/publish-predecessor.json" >/dev/null || \
        die "publish provider receipt validation differs"
      jq -e --arg publisher "$bound_publisher_execution" \
        --arg run "$request_run_id" '
        .provider_execution_spec.phase == "publish" and
        .provider_execution_spec.execution_name == $publisher and
        .operator_output.run_id == $run and
        .operator_output.complete == true and
        .operator_output.terminal_batch_root_requested_last == true and
        .operator_output.same_process_deep_reopen_complete == true' \
        "$work/publish-predecessor.json" >/dev/null || \
        die "independent reopen publication predecessor differs"
      [[ "$bound_worker_execution" != DISABLED && \
         "$bound_verifier_execution" != DISABLED && \
         "$bound_publisher_execution" != DISABLED && \
         "$execution" != "$bound_worker_execution" && \
         "$execution" != "$bound_verifier_execution" && \
         "$execution" != "$bound_publisher_execution" ]] || \
        die "independent reopen execution binding differs"
      ;;
  esac

  jq -e --arg schema \
      corpus-r6-matchup-source-task0-provider-execution-spec/v3 \
    --arg phase "$phase" --arg project "$PROJECT" --arg region "$REGION" \
    --arg job "$JOB" --arg image "$image" --arg digest "$digest" \
    --arg code "$code" --arg build "$build_id" --arg service "$SERVICE_ACCOUNT" \
    --arg request_run "$request_run_id" --arg payload_sha "$payload_sha" \
    --arg payload_bytes "$payload_bytes" --arg mode_env "$MODE_ENV" \
    --arg outcomes_env "$OUTCOMES_ENV" '
    (.spec.template.spec.containers[0]) as $container |
    ($container.env | map({key:.name,value:.value}) | from_entries) as $env |
    {schema_version:$schema,phase:$phase,project:$project,region:$region,
      job:$job,job_uid:.metadata.labels["run.googleapis.com/jobUid"],
      job_generation:.metadata.labels["run.googleapis.com/jobGeneration"],
      execution_name:.metadata.name,execution_uid:.metadata.uid,
      completion_time:.status.completionTime,task_count:.spec.taskCount,
      parallelism:.spec.parallelism,max_retries:.spec.template.spec.maxRetries,
      timeout_seconds:(.spec.template.spec.timeoutSeconds | tostring),
      service_account:.spec.template.spec.serviceAccountName,
      cpu:$container.resources.limits.cpu,memory:$container.resources.limits.memory,
      command:$container.command,args:$container.args,image_uri:$container.image,
      image_digest:$digest,code_sha:$code,image_source_commit_sha:$code,
      build_id:$build,mode:$env[$mode_env],
      outcomes_allowed:($env[$outcomes_env] == "true"),
      request_run_id:$request_run,payload_sha256:$payload_sha,
      payload_bytes:($payload_bytes | tonumber),
      bound_worker_execution:
        $env.CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_WORKER_EXECUTION,
      bound_verifier_execution:
        $env.CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_VERIFIER_EXECUTION,
      bound_publisher_execution:
        $env.CORPUS_R6_MATCHUP_SOURCE_V3_PUBLISHER_EXECUTION,
      succeeded_count:(.status.succeededCount // 0),
      failed_count:(.status.failedCount // 0),
      cancelled_count:(.status.cancelledCount // 0),
      running_count:(.status.runningCount // 0)}' \
    "$execution_json" >"$provider_spec" || die "provider spec projection differs"

  filter="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$execution\" AND logName=\"projects/$PROJECT/logs/run.googleapis.com%2Fstdout\" AND textPayload:*"
  gcloud logging read "$filter" --project "$PROJECT" --limit 20 --order=asc \
    --format=json >"$logs_json"
  jq -er '[.[] | .textPayload? | select(type == "string") |
      select((fromjson? | .schema_version? |
        startswith("corpus-r6-matchup-source-")) == true)] |
      if length == 1 then .[0] else error("stdout result count differs") end' \
    "$logs_json" >"$operator_stdout" || die "exact stdout result differs"
  "$ROOT/.venv/bin/python" -I -c '
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
raw = path.read_bytes()
value = json.loads(raw.decode("utf-8"))
canonical = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
if raw != canonical:
    raise SystemExit("provider stdout is not exact canonical JSON")
' "$operator_stdout" || die "provider stdout canonical bytes differ"
  cp "$operator_stdout" "$operator_output"

  case "$phase" in
    worker)
      jq -e --arg execution "$execution" --arg run "$request_run_id" '
        .schema_version == "corpus-r6-matchup-source-task0-worker-publication/v3" and
        .complete == true and .worker_execution_name == $execution and
        .run_id == $run and
        .task0_result_root_was_final_create_once_request == true' \
        "$operator_output" >/dev/null || die "worker stdout gate differs"
      bind_controller_provider_receipt \
        "$provider_spec" "$operator_output" DISABLED "$output"
      ;;
    verify)
      jq -e --arg execution "$execution" --arg worker "$bound_worker_execution" \
        --arg run "$request_run_id" '
        .complete == true and .verifier_execution_name == $execution and
        .worker_execution_name == $worker and .run_id == $run and
        .worker_execution_name != .verifier_execution_name and
        .publication_callback_exposed == false and .write_inventory_count == 0' \
        "$operator_output" >/dev/null || die "verifier stdout gate differs"
      bind_controller_provider_receipt \
        "$provider_spec" "$operator_output" "$request_payload" "$output"
      ;;
    publish)
      jq -e --arg run "$request_run_id" --arg worker "$bound_worker_execution" \
        --arg verifier "$bound_verifier_execution" \
        --slurpfile predecessor "$request_payload" '
        .schema_version == "corpus-r6-matchup-source-provider-publication-stdout/v3" and
        .complete == true and .run_id == $run and
        .task0_worker_execution_name == $worker and
        .task0_verifier_execution_name == $verifier and
        .task0_verifier_provider_receipt_identity == $predecessor[0] and
        .terminal_batch_root_requested_last == true and
        .same_process_deep_reopen_complete == true' "$operator_output" >/dev/null || \
        die "publication stdout gate differs"
      bind_controller_provider_receipt \
        "$provider_spec" "$operator_output" DISABLED "$output"
      ;;
    reopen)
      jq -e --arg run "$request_run_id" --arg publisher "$bound_publisher_execution" \
        --arg reopener "$execution" --arg worker "$bound_worker_execution" \
        --arg verifier "$bound_verifier_execution" '
        .schema_version ==
          "corpus-r6-matchup-source-independent-reopen-receipt/v3" and
        .complete == true and .run_id == $run and
        .publisher_execution_name == $publisher and
        .reopen_execution_name == $reopener and
        .task0_worker_execution_name == $worker and
        .task0_verifier_execution_name == $verifier and
        .publisher_execution_name != .reopen_execution_name and
        .candidate_v2_capture_v3_component_v3_source_v3_deep_reopen_complete == true and
        .write_disabled_public_reopen_complete == true and
        .publication_callback_exposed == false and .write_inventory_count == 0 and
        .write_capability_enabled == false and .cloud_mutation_performed == false' \
        "$operator_output" >/dev/null || die "independent reopen stdout gate differs"
      bind_controller_provider_receipt \
        "$provider_spec" "$operator_output" DISABLED "$output"
      ;;
  esac
  "$ROOT/.venv/bin/python" "$ROOT/$TASK0_RUNNER" \
    --action validate-provider-receipt --provider-receipt "$output" >/dev/null || \
    die "provider-bound stdout receipt differs"

  persist_controller_artifact "$operator_stdout" "$request_run_id" "$phase" \
    "$execution" operator-stdout.json "$output.operator-stdout.identity.json"
  persist_controller_artifact "$output" "$request_run_id" "$phase" \
    "$execution" provider-receipt.json "$output.provider-receipt.identity.json"
}

if [[ "$action" == result ]]; then
  collect_result "$target" "$work/result.json"
  phase=$(jq -er '.provider_execution_spec.phase' "$work/result.json")
  jq -n --arg schema corpus-r6-matchup-source-controller-result/v3 \
    --arg phase "$phase" --arg execution "$target" \
    --slurpfile stdout_identity "$work/result.json.operator-stdout.identity.json" \
    --slurpfile receipt_identity "$work/result.json.provider-receipt.identity.json" \
    '{schema_version:$schema,phase:$phase,execution_name:$execution,
      operator_stdout_identity:$stdout_identity[0],
      provider_receipt_identity:$receipt_identity[0],
      exact_provider_state_derived:true,complete:true}'
  exit 0
fi

payload=$work/payload.json
run_id=DISABLED
bound_worker=DISABLED
bound_verifier=DISABLED
bound_publisher=DISABLED
case "$action" in
  worker)
    [[ "$target" =~ ^[a-z0-9][a-z0-9-]{7,80}$ ]] || die "worker run ID differs"
    run_id=$target
    printf '{}' >"$payload"
    ;;
  verify)
    collect_result "$target" "$work/worker.json"
    "$ROOT/.venv/bin/python" "$ROOT/$TASK0_RUNNER" \
      --action validate-provider-receipt \
      --provider-receipt "$work/worker.json" >/dev/null || \
      die "worker provider receipt validation differs"
    jq -e --arg execution "$target" '
      .schema_version == "corpus-r6-matchup-source-task0-provider-receipt/v3" and
      .complete == true and .provider_execution_spec.phase == "worker" and
      .provider_execution_spec.execution_name == $execution and
      .operator_output.worker_execution_name == $execution and
      .operator_output.task0_result_root_was_final_create_once_request == true' \
      "$work/worker.json" >/dev/null || die "worker provider gate differs"
    cp "$work/worker.json" "$payload"
    run_id=$(jq -er '.operator_output.run_id' "$work/worker.json")
    bound_worker=$target
    ;;
  publish)
    [[ "$target" =~ ^[a-z0-9][a-z0-9-]{7,80}$ && \
       "$extra" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
      die "publish requires run ID and verifier execution"
    run_id=$target
    collect_result "$extra" "$work/verifier.json"
    "$ROOT/.venv/bin/python" "$ROOT/$TASK0_RUNNER" \
      --action validate-provider-receipt \
      --provider-receipt "$work/verifier.json" >/dev/null || \
      die "verifier provider receipt validation differs"
    jq -e --arg execution "$extra" --arg run "$run_id" '
      .schema_version == "corpus-r6-matchup-source-task0-provider-receipt/v3" and
      .complete == true and .provider_execution_spec.phase == "verify" and
      .provider_execution_spec.execution_name == $execution and
      .operator_output.verifier_execution_name == $execution and
      .operator_output.run_id == $run and
      .operator_output.worker_execution_name !=
        .operator_output.verifier_execution_name and
      .operator_output.publication_callback_exposed == false and
      .operator_output.write_inventory_count == 0 and
      .worker_provider_receipt.provider_execution_spec.phase == "worker"' \
      "$work/verifier.json" >/dev/null || die "distinct verifier provider gate differs"
    cp "$work/verifier.json.provider-receipt.identity.json" "$payload"
    bound_worker=$(jq -er \
      '.worker_provider_receipt.provider_execution_spec.execution_name' \
      "$work/verifier.json")
    bound_verifier=$extra
    ;;
  reopen)
    [[ "$target" =~ ^[a-z0-9][a-z0-9-]{7,80}$ && \
       "$extra" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
      die "reopen requires run ID and publish execution"
    run_id=$target
    collect_result "$extra" "$work/publish.json"
    "$ROOT/.venv/bin/python" "$ROOT/$TASK0_RUNNER" \
      --action validate-provider-receipt \
      --provider-receipt "$work/publish.json" >/dev/null || \
      die "publish provider receipt validation differs"
    jq -e --arg execution "$extra" --arg run "$run_id" '
      .schema_version == "corpus-r6-matchup-source-task0-provider-receipt/v3" and
      .complete == true and .provider_execution_spec.phase == "publish" and
      .provider_execution_spec.execution_name == $execution and
      .operator_output.run_id == $run and
      .operator_output.complete == true and
      .operator_output.terminal_batch_root_requested_last == true and
      .operator_output.same_process_deep_reopen_complete == true and
      .operator_output.independent_process_deep_reopen_required == true and
      .operator_output.independent_process_deep_reopen_complete == false' \
      "$work/publish.json" >/dev/null || \
      die "publish provider gate differs before independent reopen"
    cp "$work/publish.json.provider-receipt.identity.json" "$payload"
    bound_worker=$(jq -er '.provider_execution_spec.bound_worker_execution' \
      "$work/publish.json")
    bound_verifier=$(jq -er '.provider_execution_spec.bound_verifier_execution' \
      "$work/publish.json")
    bound_publisher=$extra
    ;;
esac
payload_sha=$(sha256sum "$payload" | awk '{print $1}')
gzip -n -9 -c "$payload" >"$work/payload.gzip" || \
  die "payload deterministic compression differs"
payload_b64=$(base64 -w0 "$work/payload.gzip")
[[ "${#payload_b64}" -le "$MAX_PAYLOAD_BASE64_BYTES" ]] || \
  die "compressed payload environment bound differs"

gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format=json >"$work/job.json"
jq -e --arg uid "$EXPECTED_JOB_UID" '.metadata.uid == $uid' "$work/job.json" >/dev/null || \
  die "reused job UID differs"
latest=$(jq -er '.status.latestCreatedExecution.name' "$work/job.json")
gcloud run jobs executions describe "$latest" --project "$PROJECT" --region "$REGION" \
  --format=json >"$work/latest.json"
jq -e 'any(.status.conditions[]?; .type == "Completed" and .status == "True") and
  (.status.failedCount // 0) == 0 and (.status.cancelledCount // 0) == 0 and
  (.status.runningCount // 0) == 0' "$work/latest.json" >/dev/null || \
  die "reused job latest execution is not terminal success"

gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$image" --command /bin/bash --args "/app/$SCRIPT,container-help" \
  --tasks 1 --parallelism 1 --max-retries 0 --cpu 8 --memory 32Gi \
  --task-timeout 86400s --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars "CODE_SHA=$code,IMAGE_SOURCE_COMMIT_SHA=$code,IMAGE_DIGEST=$digest,IMAGE_URI=$image,BUILD_ID=$build_id,$MODE_ENV=DISABLED,$OUTCOMES_ENV=false,$WORKER_EXECUTION_ENV=DISABLED,$VERIFIER_EXECUTION_ENV=DISABLED,$PUBLISHER_EXECUTION_ENV=DISABLED" \
  --quiet >/dev/null
envs="^|^CODE_SHA=$code|IMAGE_SOURCE_COMMIT_SHA=$code|IMAGE_DIGEST=$digest|IMAGE_URI=$image|BUILD_ID=$build_id|$MODE_ENV=$action|$OUTCOMES_ENV=false|TASK0_RUN_ID=$run_id|$PAYLOAD_SHA_ENV=$payload_sha|$PAYLOAD_B64_ENV=$payload_b64|CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_DIGEST=$digest|CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_REFERENCE=$image|CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_SOURCE_COMMIT=$code|$WORKER_EXECUTION_ENV=$bound_worker|$VERIFIER_EXECUTION_ENV=$bound_verifier|$PUBLISHER_EXECUTION_ENV=$bound_publisher"
gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" --tasks 1 \
  --args "/app/$SCRIPT,container-run,$action" --update-env-vars "$envs" \
  --async --format=json >"$work/launch.json"
execution=$(jq -er '.metadata.name' "$work/launch.json") || die "launch name differs"
[[ "$execution" =~ ^${JOB}-[a-z0-9]{5}$ ]] || die "launch execution name differs"
jq -n --arg schema corpus-r6-matchup-source-task0-cloud-launch/v3 \
  --arg phase "$action" --arg execution "$execution" --arg image "$image" \
  --arg code "$code" --arg build "$build_id" --arg payload "$payload_sha" \
  '{schema_version:$schema,phase:$phase,execution:{name:$execution,task_count:1},
    provider_resolved_image:$image,code_sha:$code,cloud_build_id:$build,
    payload_sha256:$payload,outcomes_allowed:false,complete:true}'
