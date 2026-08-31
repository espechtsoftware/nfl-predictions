#!/usr/bin/env bash
# Default-off immutable Cloud Run boundary for the seven-pack capture.
set -euo pipefail

die() { printf '%s\n' "ERROR: $*" >&2; exit 2; }

RUNNER=/app/scripts/run_corpus_r6_matchup_seven_pack_capture_v1.py
AUTHORITY=/app/SEVEN_PACK_IMPLEMENTATION_AUTHORITY.json
PAYLOAD_B64_ENV=R6_MATCHUP_SEVEN_PACK_PAYLOAD_B64
PAYLOAD_SHA_ENV=R6_MATCHUP_SEVEN_PACK_PAYLOAD_SHA256
AUTHORITY_SHA_ENV=R6_MATCHUP_SEVEN_PACK_IMPLEMENTATION_AUTHORITY_SHA256
OUTCOMES_ENV=R6_MATCHUP_SEVEN_PACK_OUTCOMES_ALLOWED
TASK0_ENV=CORPUS_R6_MATCHUP_SEVEN_PACK_TASK0
PUBLISH_ENV=CORPUS_R6_MATCHUP_SEVEN_PACK_PUBLISH
REOPEN_ENV=CORPUS_R6_MATCHUP_SEVEN_PACK_REOPEN
HOST_ENABLE_ENV=CORPUS_R6_MATCHUP_SEVEN_PACK_CLOUD_RELEASE
HOST_ENABLE_VALUE=I_UNDERSTAND_SEVEN_PACK_CAPTURE_V1
MAX_PAYLOAD_BYTES=16777216

# Cloud Logging may encode a one-line JSON stdout object as jsonPayload or
# retain it verbatim in textPayload.  The exact raw gcloud response must be a
# singleton array with exactly one of those fields.  Canonicalization uses the
# same measured Python producer as the receipt, including its numeric law.
STDOUT_RECEIPT_PY='
import json
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source

logs = json.loads(Path(sys.argv[2]).read_bytes())
schema_mode = sys.argv[3]
expected_schema = sys.argv[4]
if type(logs) is not list or len(logs) != 1:
    raise SystemExit("raw Cloud Logging response is not one row")
entry = logs[0]
if type(entry) is not dict:
    raise SystemExit("Cloud Logging row is not one object")
has_text = "textPayload" in entry
has_json = "jsonPayload" in entry
if has_text == has_json:
    raise SystemExit("stdout payload source is not exclusive")
if has_text:
    text = entry["textPayload"]
    if type(text) is not str:
        raise SystemExit("textPayload type differs")
    body = json.loads(text)
else:
    body = entry["jsonPayload"]
if type(body) is not dict:
    raise SystemExit("stdout receipt is not one object")
if schema_mode == "top-level":
    actual_schema = body.get("schema_version")
elif schema_mode == "operator-receipt":
    operator_receipt = body.get("operator_receipt")
    if type(operator_receipt) is not dict:
        raise SystemExit("operator receipt is absent")
    actual_schema = operator_receipt.get("schema_version")
else:
    raise SystemExit("stdout schema mode differs")
if actual_schema != expected_schema:
    raise SystemExit("stdout receipt schema differs")
canonical = source.canonical_json_bytes(body)
if has_text and text.encode("utf-8") != canonical:
    raise SystemExit("textPayload is not producer-canonical JSON")
sys.stdout.buffer.write(canonical)
'

canonicalize_stdout_receipt() {
  [[ $# -eq 4 ]] || die "stdout canonicalizer contract differs"
  local logs=$1 schema_mode=$2 expected_schema=$3 output=$4
  "$ROOT/.venv/bin/python" -I -c "$STDOUT_RECEIPT_PY" \
    "$ROOT/src" "$logs" "$schema_mode" "$expected_schema" >"$output" || \
    die "exact singleton stdout receipt differs"
}

decode_payload() {
  [[ "${!PAYLOAD_B64_ENV:-}" ]] || die "payload base64 is absent"
  [[ "${!PAYLOAD_SHA_ENV:-}" =~ ^[0-9a-f]{64}$ ]] || die "payload SHA differs"
  local target=$1
  umask 077
  printf '%s' "${!PAYLOAD_B64_ENV}" | base64 --decode >"$target" || \
    die "payload base64 decode failed"
  [[ -f "$target" && ! -L "$target" ]] || die "payload file differs"
  local size
  size=$(stat -c '%s' "$target") || die "payload stat failed"
  [[ "$size" =~ ^[0-9]+$ && "$size" -ge 1 && \
     "$size" -le "$MAX_PAYLOAD_BYTES" ]] || die "payload size differs"
  [[ "$(sha256sum "$target" | awk '{print $1}')" == \
      "${!PAYLOAD_SHA_ENV}" ]] || die "payload bytes differ"
}

container_gate() {
  local mode=$1 expected_task0=DISABLED expected_publish=DISABLED expected_reopen=DISABLED
  [[ "${CODE_SHA:-}" =~ ^[0-9a-f]{40}$ && \
     "${IMAGE_SOURCE_COMMIT_SHA:-}" == "$CODE_SHA" && \
     "$(cat /app/SOURCE_COMMIT)" == "$CODE_SHA" ]] || die "runtime source commit differs"
  [[ "${!AUTHORITY_SHA_ENV:-}" =~ ^[0-9a-f]{64}$ && \
     "$(sha256sum "$AUTHORITY" | awk '{print $1}')" == \
       "${!AUTHORITY_SHA_ENV}" ]] || die "runtime implementation authority differs"
  [[ "${IMAGE_DIGEST:-}" =~ ^sha256:[0-9a-f]{64}$ && \
     "${IMAGE_URI:-}" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ && \
     "${IMAGE_URI##*@}" == "$IMAGE_DIGEST" ]] || die "runtime image identity differs"
  [[ "${BUILD_ID:-}" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || \
    die "runtime build ID differs"
  [[ "${CLOUD_RUN_TASK_INDEX:-}" == 0 && "${CLOUD_RUN_TASK_COUNT:-}" == 1 && \
     "${CLOUD_RUN_TASK_ATTEMPT:-}" == 0 ]] || die "runtime task boundary differs"
  [[ "${!OUTCOMES_ENV:-}" == false ]] || die "outcome boundary differs"
  case "$mode" in
    task0) expected_task0=1 ;;
    publish) expected_publish=1 ;;
    reopen) expected_reopen=1 ;;
    *) die "unsupported container mode" ;;
  esac
  [[ "${!TASK0_ENV:-}" == "$expected_task0" && \
     "${!PUBLISH_ENV:-}" == "$expected_publish" && \
     "${!REOPEN_ENV:-}" == "$expected_reopen" ]] || die "mode gates differ"
}

container_run() {
  [[ $# -eq 1 ]] || die "container-run requires one mode"
  local mode=$1 work payload
  container_gate "$mode"
  work=$(mktemp -d /tmp/matchup-seven-pack.XXXXXX)
  cleanup_container() { rm -rf "$work"; }
  trap cleanup_container EXIT
  payload=$work/payload.json
  decode_payload "$payload"
  case "$mode" in
    task0)
      /usr/local/bin/python3.11 -I "$RUNNER" task0 --request "$payload"
      ;;
    publish)
      /usr/local/bin/python3.11 -I "$RUNNER" publish --request "$payload" \
        --repository-root /app --implementation-authority "$AUTHORITY"
      ;;
    reopen)
      /usr/local/bin/python3.11 -I "$RUNNER" reopen --release-identity "$payload"
      ;;
  esac
}

case "${1:-}" in
  container-help)
    printf '%s\n' 'container modes: task0 publish reopen'
    exit 0
    ;;
  container-run)
    shift
    container_run "$@"
    exit 0
    ;;
esac

PROJECT=nfl-predictions-503414
REGION=us-central1
SOURCE_REPOSITORY=https://github.com/espechtsoftware/nfl-predictions.git
JOB=atlas-cbc-32g-full-2023-w8-v1
EXPECTED_JOB_UID=1f4bcf0a-2300-4afa-9fc1-9981844c8275
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
SCRIPT=scripts/cloud_corpus_r6_matchup_seven_pack_capture_v1.sh

[[ "${!HOST_ENABLE_ENV:-}" == "$HOST_ENABLE_VALUE" ]] || \
  die "cloud release is disabled; set $HOST_ENABLE_ENV=$HOST_ENABLE_VALUE explicitly"

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || die "repository root unavailable"
release_paths=(
  Dockerfile.corpus-r6-matchup-seven-pack-capture
  Dockerfile.corpus-r6-matchup-seven-pack-capture.dockerignore
  cloudbuild.corpus-r6-matchup-seven-pack-capture.yaml
  pyproject.toml README.md
  "$SCRIPT"
  scripts/run_corpus_r6_matchup_seven_pack_capture_v1.py
  src/nfl_dfs/research/corpus_r6_matchup_seven_pack_capture_v1.py
  src/nfl_dfs/research/corpus_r6_matchup_seven_pack_capture_operator_v1.py
  src/nfl_dfs/research/corpus_r6_matchup_capture_plan_from_seven_pack_v1.py
  src/nfl_dfs/research/corpus_r6_paid_source_normalized_snapshot_v1.py
  src/nfl_dfs/research/corpus_r6_matchup_source_v2.py
  src/nfl_dfs/research/corpus_r6_player_catalog_v1.py
  tests/test_corpus_r6_matchup_seven_pack_capture_v1.py
  tests/test_corpus_r6_matchup_seven_pack_capture_operator_v1.py
  tests/test_corpus_r6_matchup_capture_plan_from_seven_pack_v1.py
  tests/test_cloud_corpus_r6_matchup_seven_pack_capture_v1.py
)

require_clean_commit() {
  local commit=$1 path status
  [[ "$(git -C "$ROOT" rev-parse HEAD)" == "$commit" && \
     "$(git -C "$ROOT" rev-parse --verify 'refs/remotes/origin/main^{commit}')" == \
       "$commit" ]] || die "commit must equal clean durable origin/main"
  for path in "${release_paths[@]}"; do
    git -C "$ROOT" cat-file -e "${commit}:${path}" || die "release path is untracked: $path"
    status=$(git -C "$ROOT" status --porcelain --untracked-files=all -- "$path")
    [[ -z "$status" ]] || die "release path differs from commit: $path"
  done
}

make_authority() {
  local commit=$1 output=$2
  "$ROOT/.venv/bin/python" "$ROOT/scripts/run_corpus_r6_matchup_seven_pack_capture_v1.py" \
    build-implementation-authority --repository-root "$ROOT" \
    --source-commit-sha "$commit" >"$output"
}

mkdir -p "$ROOT/.build-contexts"
work=$(mktemp -d "$ROOT/.build-contexts/matchup-seven-pack-release.XXXXXX")
cleanup_host() { rm -rf "$work"; }
trap cleanup_host EXIT

if [[ "${1:-}" == build ]]; then
  [[ $# -eq 2 && "$2" =~ ^[0-9a-f]{40}$ ]] || die "usage: $0 build FULL_CODE_SHA"
  code=$2
  require_clean_commit "$code"
  authority=$work/authority.json
  make_authority "$code" "$authority"
  authority_sha=$(sha256sum "$authority" | awk '{print $1}')
  tag="${REGION}-docker.pkg.dev/${PROJECT}/nfl-dfs/nfl-dfs:matchup-seven-pack-${code}"
  build_id=$(gcloud builds submit "$SOURCE_REPOSITORY" \
    --git-source-revision "$code" \
    --config "$ROOT/cloudbuild.corpus-r6-matchup-seven-pack-capture.yaml" \
    --substitutions "_CODE_SHA=$code,_IMPLEMENTATION_AUTHORITY_SHA=$authority_sha,_BUILD_IMAGE=$tag" \
    --project "$PROJECT" --format='value(id)' --quiet)
  [[ "$build_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || \
    die "Cloud Build ID differs"
  gcloud builds describe "$build_id" --project "$PROJECT" --format=json >"$work/build.json"
  digest=$(jq -er --arg id "$build_id" --arg tag "$tag" --arg code "$code" \
    --arg authority "$authority_sha" --arg repo "$SOURCE_REPOSITORY" '
      select(.id == $id and .status == "SUCCESS" and
        .source.gitSource == {url:$repo,revision:$code} and
        .sourceProvenance.resolvedGitSource == {url:$repo,revision:$code} and
        .substitutions._CODE_SHA == $code and
        .substitutions._IMPLEMENTATION_AUTHORITY_SHA == $authority) |
      [.results.images[]? | select(.name == $tag) | .digest] |
      if length == 1 then .[0] else error("image count differs") end
    ' "$work/build.json") || die "Cloud Build authority differs"
  jq -n --arg schema corpus-r6-matchup-seven-pack-cloud-build/v1 \
    --arg code "$code" --arg authority "$authority_sha" --arg build "$build_id" \
    --arg image "${tag%:*}@${digest}" '{schema_version:$schema,code_sha:$code,
      implementation_authority_sha256:$authority,cloud_build_id:$build,
      provider_resolved_image:$image,complete:true}'
  exit 0
fi

[[ $# -ge 5 && $# -le 6 ]] || \
  die "usage: $0 {task0|publish|reopen|result} IMAGE@sha256:DIGEST CODE_SHA BUILD_ID PAYLOAD_OR_EXECUTION [TASK0_EXECUTION]"
action=$1 image=$2 code=$3 build_id=$4 target=$5 task0_execution=${6:-}
[[ "$action" =~ ^(task0|publish|reopen|result)$ ]] || die "action differs"
[[ "$image" =~ ^us-central1-docker\.pkg\.dev/${PROJECT}/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || \
  die "image must be immutable"
[[ "$code" =~ ^[0-9a-f]{40}$ && "$build_id" =~ ^[0-9a-f-]{36}$ ]] || \
  die "code/build identity differs"
require_clean_commit "$code"
authority=$work/authority.json
make_authority "$code" "$authority"
authority_sha=$(sha256sum "$authority" | awk '{print $1}')
digest=${image##*@}

gcloud builds describe "$build_id" --project "$PROJECT" --format=json >"$work/build.json"
jq -e --arg id "$build_id" --arg code "$code" --arg authority "$authority_sha" \
  --arg digest "$digest" '.id == $id and .status == "SUCCESS" and
  .substitutions._CODE_SHA == $code and
  .substitutions._IMPLEMENTATION_AUTHORITY_SHA == $authority and
  any(.results.images[]?; .digest == $digest)' "$work/build.json" >/dev/null || \
  die "build/image binding differs"

collect_result() {
  local execution=$1 output=$2
  [[ "$execution" =~ ^${JOB}-[a-z0-9]{5}$ ]] || die "execution name differs"
  gcloud run jobs executions describe "$execution" --project "$PROJECT" \
    --region "$REGION" --format=json >"$work/execution.json"
  phase=$(jq -er --arg script "/app/$SCRIPT" '
    .spec.template.spec.containers[0].args as $a |
    if $a == [$script,"container-run","task0"] then "task0"
    elif $a == [$script,"container-run","publish"] then "publish"
    elif $a == [$script,"container-run","reopen"] then "reopen"
    else error("phase differs") end' "$work/execution.json") || die "execution phase differs"
  case "$phase" in
    task0) receipt_schema=corpus-r6-matchup-seven-pack-task0-readiness/v1 ;;
    publish) receipt_schema=corpus-r6-matchup-seven-pack-operator-publication/v1 ;;
    reopen) receipt_schema=corpus-r6-matchup-seven-pack-operator-reopen/v1 ;;
    *) die "execution receipt schema phase differs" ;;
  esac
  jq -e --arg execution "$execution" --arg job "$JOB" --arg image "$image" '
    .metadata.name == $execution and .metadata.labels["run.googleapis.com/job"] == $job and
    any(.status.conditions[]?; .type == "Completed" and .status == "True") and
    (.status.succeededCount // 0) == 1 and (.status.failedCount // 0) == 0 and
    (.status.cancelledCount // 0) == 0 and (.status.runningCount // 0) == 0 and
    .spec.taskCount == 1 and .spec.template.spec.maxRetries == 0 and
    .spec.template.spec.containers[0].image == $image' "$work/execution.json" >/dev/null || \
    die "execution is not terminal exact success"
  filter="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$execution\" AND logName=\"projects/$PROJECT/logs/run.googleapis.com%2Fstdout\" AND (textPayload:* OR jsonPayload:*)"
  gcloud logging read "$filter" --project "$PROJECT" --limit 50 --order=asc \
    --format=json >"$work/logs.json"
  canonicalize_stdout_receipt \
    "$work/logs.json" operator-receipt "$receipt_schema" "$output"
  jq -n --arg schema corpus-r6-matchup-seven-pack-cloud-result/v1 \
    --arg phase "$phase" --arg execution "$execution" --arg image "$image" \
    --arg code "$code" --arg build "$build_id" --slurpfile receipt "$output" \
    '{schema_version:$schema,phase:$phase,execution:{name:$execution,task_count:1,
      succeeded_count:1,failed_count:0,cancelled_count:0},provider_resolved_image:$image,
      code_sha:$code,cloud_build_id:$build,operator_output:$receipt[0],complete:true}'
}

if [[ "$action" == result ]]; then
  collect_result "$target" "$work/operator.json"
  exit 0
fi

[[ "$target" == /* && -f "$target" && ! -L "$target" ]] || die "payload file differs"
payload_sha=$(sha256sum "$target" | awk '{print $1}')
payload_b64=$(base64 -w0 "$target")
[[ "${#payload_b64}" -le 1400000 ]] || die "payload exceeds Cloud Run override ceiling"
task0_gate=DISABLED publish_gate=DISABLED reopen_gate=DISABLED
case "$action" in
  task0)
    "$ROOT/.venv/bin/python" "$ROOT/scripts/run_corpus_r6_matchup_seven_pack_capture_v1.py" \
      validate --request "$target" >/dev/null
    bound=$(jq -er '.capture_request_sha256' "$target")
    task0_gate=1
    ;;
  publish)
    [[ "$task0_execution" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
      die "publish requires one exact successful task0 execution"
    "$ROOT/.venv/bin/python" "$ROOT/scripts/run_corpus_r6_matchup_seven_pack_capture_v1.py" \
      validate --request "$target" >/dev/null
    bound=$(jq -er '.capture_request_sha256' "$target")
    collect_result "$task0_execution" "$work/task0.json" >"$work/task0-result.json"
    jq -e --arg bound "$bound" '.phase == "task0" and .complete == true and
      .operator_output.operator_receipt.capture_request_sha256 == $bound and
      .operator_output.operator_receipt.publication_count == 0' \
      "$work/task0-result.json" >/dev/null || die "task0 launch gate differs"
    publish_gate=1
    ;;
  reopen)
    bound=$(jq -er '.sha256' "$target")
    reopen_gate=1
    ;;
esac

gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format=json >"$work/job-before.json"
latest=$(jq -er '.status.latestCreatedExecution.name' "$work/job-before.json")
gcloud run jobs executions describe "$latest" --project "$PROJECT" --region "$REGION" \
  --format=json >"$work/latest.json"
jq -e 'any(.status.conditions[]?; .type == "Completed" and .status == "True") and
  (.status.failedCount // 0) == 0 and (.status.cancelledCount // 0) == 0 and
  (.status.runningCount // 0) == 0' "$work/latest.json" >/dev/null || \
  die "reused job latest execution is not terminal success"
jq -e --arg uid "$EXPECTED_JOB_UID" '.metadata.uid == $uid' \
  "$work/job-before.json" >/dev/null || die "reused job UID differs"

gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$image" --command /bin/bash --args "/app/$SCRIPT,container-help" \
  --tasks 1 --parallelism 1 --max-retries 0 --cpu 2 --memory 4Gi \
  --task-timeout 3600s --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars "CODE_SHA=$code,IMAGE_DIGEST=$digest,IMAGE_URI=$image,BUILD_ID=$build_id,$AUTHORITY_SHA_ENV=$authority_sha,$TASK0_ENV=DISABLED,$PUBLISH_ENV=DISABLED,$REOPEN_ENV=DISABLED,$OUTCOMES_ENV=false" \
  --quiet >/dev/null
envs="^|^CODE_SHA=$code|IMAGE_DIGEST=$digest|IMAGE_URI=$image|BUILD_ID=$build_id|$AUTHORITY_SHA_ENV=$authority_sha|$PAYLOAD_SHA_ENV=$payload_sha|$PAYLOAD_B64_ENV=$payload_b64|$TASK0_ENV=$task0_gate|$PUBLISH_ENV=$publish_gate|$REOPEN_ENV=$reopen_gate|$OUTCOMES_ENV=false"
gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" --tasks 1 \
  --args "/app/$SCRIPT,container-run,$action" --update-env-vars "$envs" \
  --async --format=json >"$work/launch.json"
execution=$(jq -er '.metadata.name' "$work/launch.json") || die "launch execution differs"
[[ "$execution" =~ ^${JOB}-[a-z0-9]{5}$ ]] || die "launch execution name differs"
jq -n --arg schema corpus-r6-matchup-seven-pack-cloud-launch/v1 \
  --arg phase "$action" --arg execution "$execution" --arg image "$image" \
  --arg code "$code" --arg build "$build_id" --arg payload "$payload_sha" \
  --arg bound "$bound" '{schema_version:$schema,phase:$phase,
    execution:{name:$execution,task_count:1},provider_resolved_image:$image,
    code_sha:$code,cloud_build_id:$build,payload_sha256:$payload,
    bound_input_sha256:$bound,outcomes_allowed:false,complete:true}'
