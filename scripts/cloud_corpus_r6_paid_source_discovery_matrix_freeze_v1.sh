#!/usr/bin/env bash
# Default-off exact Cloud Run seam for the Experiment-5 discovery-matrix
# freezer. It reuses one known job, never lists executions/objects, and keeps
# collect phases on the host so the exact execution name is explicit.
set -euo pipefail

die() { printf '%s\n' "ERROR: $*" >&2; exit 2; }

RUNNER=/app/scripts/run_corpus_r6_paid_source_discovery_matrix_freeze_v1.py
ENABLE_ENV=R6_PAID_SOURCE_DISCOVERY_MATRIX_ENABLE
ENABLE_VALUE=I_UNDERSTAND_SCORE_FREE_DISCOVERY_MATRIX_FREEZE_V1
MODE_ENV=R6_PAID_SOURCE_DISCOVERY_MATRIX_MODE
OUTCOMES_ENV=R6_PAID_SOURCE_DISCOVERY_MATRIX_OUTCOMES_ALLOWED
PAYLOAD_ENV=R6_PAID_SOURCE_DISCOVERY_MATRIX_PAYLOAD_B64
PAYLOAD_SHA_ENV=R6_PAID_SOURCE_DISCOVERY_MATRIX_PAYLOAD_SHA256
TASK0_EXECUTION_ENV=R6_PAID_SOURCE_DISCOVERY_MATRIX_TASK0_EXECUTION
TASK0_GATE_SHA_ENV=R6_PAID_SOURCE_DISCOVERY_MATRIX_TASK0_GATE_SHA256
TASK0_GATE_B64_ENV=R6_PAID_SOURCE_DISCOVERY_MATRIX_TASK0_GATE_B64
MAX_PAYLOAD_BYTES=16777216

container_run() {
  [[ $# -eq 1 ]] || die "container-run requires one mode"
  local mode=$1 work payload command option
  case "$mode" in
    task0) command=task0; option=--manifest-identity ;;
    task) command=task; option=--manifest-identity ;;
    reopen-task) command=reopen-task; option=--terminal-identity ;;
    *) die "unsupported container mode" ;;
  esac
  [[ "${!ENABLE_ENV:-}" == "$ENABLE_VALUE" ]] || die "matrix freezer disabled"
  [[ "${!MODE_ENV:-}" == "$mode" ]] || die "matrix freezer mode differs"
  [[ "${!OUTCOMES_ENV:-}" == "false" ]] || die "outcome boundary differs"
  [[ "${CODE_SHA:-}" =~ ^[0-9a-f]{40}$ ]] || die "CODE_SHA differs"
  [[ "$(cat /app/SOURCE_COMMIT 2>/dev/null)" == "$CODE_SHA" ]] || die "baked image/source differs"
  [[ "${IMAGE_SOURCE_COMMIT_SHA:-}" == "$CODE_SHA" ]] || die "baked image label differs"
  [[ "${IMAGE_URI:-}" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || die "immutable image differs"
  [[ "${IMAGE_URI##*@}" == "${IMAGE_DIGEST:-}" ]] || die "image digest differs"
  [[ "${BUILD_ID:-}" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || die "build ID differs"
  [[ "${CLOUD_RUN_TASK_ATTEMPT:-}" == "0" ]] || die "task retry forbidden"
  if [[ "$mode" == "task0" ]]; then
    [[ "${CLOUD_RUN_TASK_INDEX:-}" == "0" && "${CLOUD_RUN_TASK_COUNT:-}" == "1" ]] || die "task0 shape differs"
  else
    [[ "${CLOUD_RUN_TASK_COUNT:-}" == "54" ]] || die "full cohort shape differs"
  fi
  work=$(mktemp -d /tmp/r6-paid-source-discovery-matrix.XXXXXX)
  cleanup_container() { rm -rf "$work"; }
  trap cleanup_container EXIT
  payload=$work/payload.json
  umask 077
  printf '%s' "${!PAYLOAD_ENV:?missing payload}" | base64 --decode >"$payload" || die "payload decode failed"
  [[ "$(stat -c '%s' "$payload")" -le "$MAX_PAYLOAD_BYTES" ]] || die "payload too large"
  [[ "$(sha256sum "$payload" | awk '{print $1}')" == "${!PAYLOAD_SHA_ENV:?missing payload hash}" ]] || die "payload bytes differ"
  /usr/local/bin/python3.11 -I "$RUNNER" "$command" "$option" "$payload" --execute
}

case "${1:-}" in
  container-help)
    printf '%s\n' 'container modes: task0 task reopen-task'
    exit 0
    ;;
  container-run)
    shift; container_run "$@"; exit 0
    ;;
esac

PROJECT=nfl-predictions-503414
REGION=us-central1
JOB=atlas-cbc-32g-full-2023-w8-v1
EXPECTED_JOB_UID=1f4bcf0a-2300-4afa-9fc1-9981844c8275
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
SOURCE_REPOSITORY=https://github.com/espechtsoftware/nfl-predictions.git

if [[ "${1:-}" == "build" ]]; then
  [[ $# -eq 2 && "$2" =~ ^[0-9a-f]{40}$ ]] || die "usage: $0 build FULL_PUSHED_CODE_SHA"
  build_sha=$2
  build_root=$(git rev-parse --show-toplevel 2>/dev/null) || die "repository root absent"
  [[ "$(git -C "$build_root" rev-parse HEAD)" == "$build_sha" ]] || die "build SHA must equal HEAD"
  [[ "$(git -C "$build_root" rev-parse --verify 'refs/remotes/origin/main^{commit}')" == "$build_sha" ]] || die "build SHA must equal origin/main"
  release_paths=(
    Dockerfile.corpus-r6-paid-source-discovery-matrix
    Dockerfile.corpus-r6-paid-source-discovery-matrix.dockerignore
    cloudbuild.corpus-r6-paid-source-discovery-matrix.yaml
    pyproject.toml README.md
    scripts/cloud_corpus_r6_paid_source_discovery_matrix_freeze_v1.sh
    scripts/run_corpus_r6_paid_source_discovery_matrix_freeze_v1.py
    src/nfl_dfs/research/corpus_r6_paid_source_discovery_matrix_freeze_v1.py
    tests/test_corpus_r6_paid_source_discovery_matrix_freeze_v1.py
    tests/test_run_corpus_r6_paid_source_discovery_matrix_freeze_v1.py
    tests/test_cloud_corpus_r6_paid_source_discovery_matrix_freeze_v1.py
  )
  for path in "${release_paths[@]}"; do
    git -C "$build_root" cat-file -e "$build_sha:$path" || die "release path absent from commit: $path"
    [[ -z "$(git -C "$build_root" status --porcelain --untracked-files=all -- "$path")" ]] || die "release path differs from commit: $path"
  done
  image_tag="${REGION}-docker.pkg.dev/${PROJECT}/nfl-dfs/nfl-dfs:paid-source-discovery-matrix-${build_sha}"
  mkdir -p "$build_root/.build-contexts"
  build_work=$(mktemp -d "$build_root/.build-contexts/discovery-matrix-build.XXXXXX")
  cleanup_build() { rm -rf "$build_work"; }
  trap cleanup_build EXIT
  build_id=$(gcloud builds submit "$SOURCE_REPOSITORY" \
    --git-source-revision "$build_sha" \
    --config "$build_root/cloudbuild.corpus-r6-paid-source-discovery-matrix.yaml" \
    --substitutions "_CODE_SHA=$build_sha,_BUILD_IMAGE=$image_tag" \
    --project "$PROJECT" --format='value(id)' --quiet)
  [[ "$build_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || die "build did not return one ID"
  build_json=$build_work/build.json
  gcloud builds describe "$build_id" --project "$PROJECT" --format=json >"$build_json"
  digest=$(jq -er --arg id "$build_id" --arg sha "$build_sha" --arg tag "$image_tag" --arg repo "$SOURCE_REPOSITORY" '
    select(.id == $id and .status == "SUCCESS" and
      .source.gitSource == {url:$repo,revision:$sha} and
      .sourceProvenance.resolvedGitSource == {url:$repo,revision:$sha} and
      .substitutions._CODE_SHA == $sha and .substitutions._BUILD_IMAGE == $tag) |
    [.results.images[]? | select(.name == $tag) | .digest] |
    if length == 1 then .[0] else error("image digest differs") end
  ' "$build_json") || die "provider build authority differs"
  [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || die "image digest differs"
  immutable_image="${image_tag%:*}@${digest}"
  attestation_uri="gs://${PROJECT}-corpus-retrieval/research/corpus-r6-paid-source-discovery-matrix-builds/${build_sha}/${build_id}/runtime-build-attestation.json"
  attestation_identity=$build_work/attestation.identity.json
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$build_root/src:$build_root/scripts" \
    "$build_root/.venv/bin/python" - "$build_json" "$SOURCE_REPOSITORY" \
      "$build_sha" "$image_tag" "$digest" "$attestation_uri" >"$attestation_identity" <<'PY'
import json, pathlib, sys
from nfl_dfs.research import corpus_r6_construction_allocation_cross_operator_v1 as authority
import run_corpus_r6_paid_source_discovery_matrix_freeze_v1 as runner

metadata_path, repository, code_sha, tag, digest, uri = sys.argv[1:]
metadata = json.loads(pathlib.Path(metadata_path).read_bytes())
attestation = authority.runtime_build_attestation_v1(
    build_id=metadata["id"], source_repository=repository,
    requested_source_commit=code_sha, resolved_source_commit=code_sha,
    image_tag=tag, image_digest=digest,
    provider_observed_at=metadata["finishTime"],
)
raw = runner.freeze.canonical_json_bytes(attestation)
store = runner.GCSStoreV1()
identity = store.publish_bytes_create_once(uri, raw)
if store.read_exact(identity) != raw:
    raise SystemExit("attestation exact reopen differs")
print(json.dumps(identity, sort_keys=True, separators=(",", ":")))
PY
  jq -e '(.sha256 | test("^[0-9a-f]{64}$")) and (.generation | type == "string") and (.bytes > 0)' "$attestation_identity" >/dev/null || die "build attestation differs"
  jq -n --arg code_sha "$build_sha" --arg build_id "$build_id" \
    --arg image "$immutable_image" --arg digest "$digest" \
    --argjson attestation "$(jq -cS . "$attestation_identity")" \
    '{schema_version:"corpus-r6-paid-source-discovery-matrix-cloud-build/v1",code_sha:$code_sha,cloud_build_id:$build_id,provider_resolved_image:$image,image_digest:$digest,runtime_build_attestation_identity:$attestation,complete:true}'
  exit 0
fi

[[ $# -ge 1 ]] || die "missing host action"
ACTION=$1
case "$ACTION" in
  install)
    [[ $# -eq 4 ]] || die "usage: $0 install IMAGE CODE_SHA BUILD_ID"
    ;;
  prepare)
    [[ $# -eq 5 ]] || die "usage: $0 prepare IMAGE CODE_SHA BUILD_ID REQUEST_JSON"
    ;;
  task0)
    [[ $# -eq 5 ]] || die "usage: $0 task0 IMAGE CODE_SHA BUILD_ID MANIFEST_IDENTITY"
    ;;
  task)
    [[ $# -eq 6 ]] || die "usage: $0 task IMAGE CODE_SHA BUILD_ID MANIFEST_IDENTITY EXACT_TASK0_EXECUTION"
    ;;
  collect)
    [[ $# -eq 6 ]] || die "usage: $0 collect IMAGE CODE_SHA BUILD_ID MANIFEST_IDENTITY EXACT_TASK_EXECUTION"
    ;;
  reopen-task)
    [[ $# -eq 6 ]] || die "usage: $0 reopen-task IMAGE CODE_SHA BUILD_ID TERMINAL_IDENTITY EXACT_TASK_EXECUTION"
    ;;
  reopen-collect)
    [[ $# -eq 6 ]] || die "usage: $0 reopen-collect IMAGE CODE_SHA BUILD_ID TERMINAL_IDENTITY EXACT_REOPEN_EXECUTION"
    ;;
  result)
    [[ $# -eq 2 && "$2" =~ ^${JOB}-[a-z0-9]{5}$ ]] || die "result requires one exact execution"
    gcloud run jobs executions describe "$2" --project "$PROJECT" --region "$REGION" --format=json
    exit 0
    ;;
  *) die "unknown host action" ;;
esac

IMAGE=$2 CODE_SHA=$3 BUILD_ID=$4 PAYLOAD=${5:-} PREDECESSOR=${6:-}
[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/${PROJECT}/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || die "image must be immutable"
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "code SHA differs"
[[ "$BUILD_ID" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || die "build ID differs"
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || die "repository root absent"
[[ "$(git -C "$ROOT" rev-parse HEAD)" == "$CODE_SHA" ]] || die "code SHA must equal HEAD"
[[ "$(git -C "$ROOT" rev-parse --verify 'refs/remotes/origin/main^{commit}')" == "$CODE_SHA" ]] || die "code SHA must equal origin/main"

mkdir -p "$ROOT/.build-contexts"
tmp=$(mktemp -d "$ROOT/.build-contexts/discovery-matrix-release.XXXXXX")
cleanup_host() { rm -rf "$tmp"; }
trap cleanup_host EXIT
job_json=$tmp/job.json
gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" --format=json >"$job_json"
jq -e --arg uid "$EXPECTED_JOB_UID" '.metadata.uid == $uid and any(.status.conditions[]?; .type == "Ready" and .status == "True")' "$job_json" >/dev/null || die "exact reused job differs"

verify_execution() {
  [[ $# -eq 4 && "$1" =~ ^${JOB}-[a-z0-9]{5}$ ]] || die "exact execution differs"
  local execution=$1 tasks=$2 mode=$3 expected_payload_sha=$4 file=$tmp/execution.json
  gcloud run jobs executions describe "$execution" --project "$PROJECT" --region "$REGION" --format=json >"$file"
  jq -e --arg execution "$execution" --arg job "$JOB" --arg uid "$EXPECTED_JOB_UID" \
    --arg image "$IMAGE" --arg code "$CODE_SHA" --arg build "$BUILD_ID" \
    --arg mode "$mode" --arg payload_sha "$expected_payload_sha" \
    --arg service "$SERVICE_ACCOUNT" --arg enable "$ENABLE_VALUE" \
    --arg enable_env "$ENABLE_ENV" --arg mode_env "$MODE_ENV" \
    --arg outcomes_env "$OUTCOMES_ENV" --arg payload_env "$PAYLOAD_ENV" \
    --arg payload_sha_env "$PAYLOAD_SHA_ENV" \
    --arg task0_execution_env "$TASK0_EXECUTION_ENV" \
    --arg task0_gate_env "$TASK0_GATE_SHA_ENV" \
    --arg task0_gate_b64_env "$TASK0_GATE_B64_ENV" --argjson tasks "$tasks" \
    --argjson expected_parallelism "$tasks" '
    def envmap:
      reduce (.spec.template.spec.containers[0].env[]?) as $row
        ({}; .[$row.name] = $row.value);
    (envmap) as $env |
    .metadata.name == $execution and .metadata.labels["run.googleapis.com/job"] == $job and
    ((.metadata.labels["run.googleapis.com/jobUid"] // .metadata.annotations["run.googleapis.com/jobUid"]) == $uid) and
    (.metadata.uid | type == "string" and length > 0) and
    .spec.taskCount == $tasks and .spec.parallelism == $expected_parallelism and
    .spec.template.spec.maxRetries == 0 and
    .spec.template.spec.timeoutSeconds == "21600" and
    .spec.template.spec.serviceAccountName == $service and
    (.spec.template.spec.containers | length) == 1 and
    .spec.template.spec.containers[0].image == $image and
    .spec.template.spec.containers[0].command == ["/bin/bash"] and
    .spec.template.spec.containers[0].args == [
      "/app/scripts/cloud_corpus_r6_paid_source_discovery_matrix_freeze_v1.sh",
      "container-run", $mode
    ] and
    .spec.template.spec.containers[0].resources.limits == {cpu:"8",memory:"32Gi"} and
    $env.CODE_SHA == $code and $env.IMAGE_URI == $image and
    $env.IMAGE_DIGEST == ($image | split("@") | .[1]) and
    $env.BUILD_ID == $build and $env[$enable_env] == $enable and
    $env[$mode_env] == $mode and $env[$outcomes_env] == "false" and
    $env[$payload_sha_env] == $payload_sha and
    ($env[$payload_env] | type == "string" and length > 0) and
    (($env | keys | sort) == ([
      "CODE_SHA", "IMAGE_URI", "IMAGE_DIGEST", "BUILD_ID", $enable_env,
      $mode_env, $outcomes_env, $payload_env, $payload_sha_env,
      $task0_execution_env, $task0_gate_env, $task0_gate_b64_env
    ] | sort)) and
    (if $mode == "task" then
      ($env[$task0_execution_env] | test("^[a-z][a-z0-9-]{2,100}$")) and
      ($env[$task0_gate_env] | test("^[0-9a-f]{64}$")) and
      ($env[$task0_gate_b64_env] | type == "string" and length > 0 and . != "none")
    else
      $env[$task0_execution_env] == "none" and
      $env[$task0_gate_env] == "none" and $env[$task0_gate_b64_env] == "none"
    end) and
    ($env | has("IMAGE_SOURCE_COMMIT_SHA") | not) and
    ((.status.succeededCount // 0) == $tasks) and ((.status.failedCount // 0) == 0) and
    ((.status.cancelledCount // 0) == 0) and ((.status.runningCount // 0) == 0) and
    any(.status.conditions[]?; .type == "Completed" and .status == "True")
  ' "$file" >/dev/null || die "predecessor execution is not exact terminal success"
}

extract_task0_receipt() {
  [[ $# -eq 2 && "$1" =~ ^${JOB}-[a-z0-9]{5}$ ]] || die "task0 receipt extraction differs"
  local execution=$1 destination=$2 logs=$tmp/task0-logs.json
  local filter
  filter="resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${JOB}\" AND labels.\"run.googleapis.com/execution_name\"=\"${execution}\" AND labels.\"run.googleapis.com/task_index\"=\"0\""
  gcloud logging read "$filter" --project "$PROJECT" --freshness=7d \
    --order=asc --limit=200 --format=json >"$logs"
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/src:$ROOT/scripts" \
    "$ROOT/.venv/bin/python" - "$logs" "$execution" "$destination" <<'PY' \
    || die "exactly one canonical task0 stdout receipt was not observed"
import json
from pathlib import Path
import sys

from nfl_dfs.research import corpus_r6_paid_source_discovery_matrix_freeze_v1 as freeze

log_path, expected_execution, destination = sys.argv[1:]
rows = json.loads(Path(log_path).read_bytes())
matches = []
for row in rows:
    if not isinstance(row, dict):
        continue
    payload = row.get("textPayload")
    structured = row.get("jsonPayload")
    if payload is None and isinstance(structured, dict):
        if structured.get("schema_version") == freeze.TASK0_SCHEMA:
            value = structured
            if (value.get("runtime_authority") or {}).get("execution_id") \
                    == expected_execution:
                matches.append(value)
            continue
        payload = structured.get("message")
    if not isinstance(payload, str):
        continue
    if payload.endswith("\n"):
        payload = payload[:-1]
    try:
        value = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError):
        continue
    if (
        not isinstance(value, dict)
        or payload.encode("utf-8") != freeze.canonical_json_bytes(value)
        or value.get("schema_version") != freeze.TASK0_SCHEMA
        or (value.get("runtime_authority") or {}).get("execution_id")
        != expected_execution
    ):
        continue
    matches.append(value)
if len(matches) != 1:
    raise SystemExit("expected exactly one canonical task0 stdout receipt")
Path(destination).write_bytes(freeze.canonical_json_bytes(matches[0]))
PY
}

if [[ "$ACTION" == "install" ]]; then
  gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
    --image "$IMAGE" --service-account "$SERVICE_ACCOUNT" --cpu 8 --memory 32Gi \
    --task-timeout 21600s --max-retries 0 --tasks 54 --parallelism 54 \
    --command /bin/bash \
    --args /app/scripts/cloud_corpus_r6_paid_source_discovery_matrix_freeze_v1.sh,container-help \
    --set-env-vars "CODE_SHA=$CODE_SHA,IMAGE_URI=$IMAGE,IMAGE_DIGEST=${IMAGE##*@},BUILD_ID=$BUILD_ID,$ENABLE_ENV=DISABLED,$MODE_ENV=DISABLED,$OUTCOMES_ENV=false,$TASK0_EXECUTION_ENV=none,$TASK0_GATE_SHA_ENV=none,$TASK0_GATE_B64_ENV=none" \
    --quiet >/dev/null
  printf '%s\n' '{"installed":true,"default_off":true}'
  exit 0
fi

[[ -f "$PAYLOAD" && ! -L "$PAYLOAD" ]] || die "payload path differs"
payload_sha=$(sha256sum "$PAYLOAD" | awk '{print $1}')
payload_b64=$(base64 -w0 "$PAYLOAD")

if [[ "$ACTION" == "prepare" ]]; then
  export "$ENABLE_ENV=$ENABLE_VALUE" "$MODE_ENV=prepare" "$OUTCOMES_ENV=false"
  "$ROOT/.venv/bin/python" "$ROOT/scripts/run_corpus_r6_paid_source_discovery_matrix_freeze_v1.py" prepare --request "$PAYLOAD" --execute
  exit 0
fi
if [[ "$ACTION" == "collect" || "$ACTION" == "reopen-collect" ]]; then
  [[ "$PREDECESSOR" =~ ^${JOB}-[a-z0-9]{5}$ ]] || die "collector predecessor differs"
  provider_mode=task
  [[ "$ACTION" == "reopen-collect" ]] && provider_mode=reopen-task
  verify_execution "$PREDECESSOR" 54 "$provider_mode" "$payload_sha"
  request=$tmp/request.json
  key=manifest_identity
  [[ "$ACTION" == "reopen-collect" ]] && key=terminal_identity
  jq -cS --arg execution "$PREDECESSOR" --arg key "$key" --slurpfile identity "$PAYLOAD" '{($key):$identity[0],execution_id:$execution}' >"$request"
  export "$ENABLE_ENV=$ENABLE_VALUE" "$MODE_ENV=$ACTION" "$OUTCOMES_ENV=false"
  "$ROOT/.venv/bin/python" "$ROOT/scripts/run_corpus_r6_paid_source_discovery_matrix_freeze_v1.py" "$ACTION" --request "$request" --execute
  exit 0
fi

mode=$ACTION tasks=54 parallelism=54
task0_execution_binding=none
task0_gate_binding=none
task0_gate_b64_binding=none
if [[ "$ACTION" == "task0" ]]; then
  mode=task0 tasks=1 parallelism=1
elif [[ "$ACTION" == "task" ]]; then
  verify_execution "$PREDECESSOR" 1 task0 "$payload_sha"
  task0_receipt=$tmp/task0-receipt.json
  task0_gate=$tmp/task0-gate.json
  extract_task0_receipt "$PREDECESSOR" "$task0_receipt"
  export "$ENABLE_ENV=$ENABLE_VALUE" "$MODE_ENV=task0-gate" "$OUTCOMES_ENV=false"
  "$ROOT/.venv/bin/python" \
    "$ROOT/scripts/run_corpus_r6_paid_source_discovery_matrix_freeze_v1.py" \
    task0-gate --manifest-identity "$PAYLOAD" --task0-receipt "$task0_receipt" \
    --execution-id "$PREDECESSOR" --execute >"$task0_gate"
  task0_gate_binding=$(jq -er '.task0_gate_sha256 | select(test("^[0-9a-f]{64}$"))' "$task0_gate") \
    || die "task0 gate proof differs"
  task0_execution_binding=$PREDECESSOR
  task0_gate_b64_binding=$(base64 -w0 "$task0_gate")
elif [[ "$ACTION" == "reopen-task" ]]; then
  [[ "$PREDECESSOR" =~ ^${JOB}-[a-z0-9]{5}$ ]] || die "matrix predecessor differs"
fi
execution=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --tasks "$tasks" \
  --args /app/scripts/cloud_corpus_r6_paid_source_discovery_matrix_freeze_v1.sh,container-run,"$mode" \
  --update-env-vars "^|^CODE_SHA=$CODE_SHA|IMAGE_URI=$IMAGE|IMAGE_DIGEST=${IMAGE##*@}|BUILD_ID=$BUILD_ID|$ENABLE_ENV=$ENABLE_VALUE|$MODE_ENV=$mode|$OUTCOMES_ENV=false|$PAYLOAD_ENV=$payload_b64|$PAYLOAD_SHA_ENV=$payload_sha|$TASK0_EXECUTION_ENV=$task0_execution_binding|$TASK0_GATE_SHA_ENV=$task0_gate_binding|$TASK0_GATE_B64_ENV=$task0_gate_b64_binding" \
  --async --format='value(metadata.name)')
[[ "$execution" =~ ^${JOB}-[a-z0-9]{5}$ ]] || die "launch did not return one exact execution"
printf '%s\n' "$execution"
