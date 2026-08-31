#!/usr/bin/env bash
# Immutable build/install/execute boundary for the normalized Fantasy
# Points/SIS snapshot. The host half reuses one exact existing research job
# only after its latest execution is terminal-success. It never creates,
# deletes or lists jobs. Installation is inert; every data-bearing phase is
# a one-task explicit execution override.
set -euo pipefail

die() { printf '%s\n' "ERROR: $*" >&2; exit 2; }

RUNNER=/app/scripts/run_corpus_r6_paid_source_normalized_snapshot_v1.py
REPOSITORY_ROOT=/app
PAYLOAD_B64_ENV=R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_PAYLOAD_B64
PAYLOAD_SHA_ENV=R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_PAYLOAD_SHA256
TASK0_B64_ENV=R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_TASK0_RECEIPT_B64
TASK0_SHA_ENV=R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_TASK0_RECEIPT_SHA256
BOUND_SHA_ENV=R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_BOUND_SHA256
MODULE_SHA_ENV=R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_MODULE_SHA256
OUTCOMES_ENV=R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_OUTCOMES_ALLOWED
TASK0_ENABLE_ENV=R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_TASK0
PUBLISH_ENABLE_ENV=R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_PUBLISH
REOPEN_ENABLE_ENV=R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_REOPEN
ENABLE_VALUE=I_UNDERSTAND_RETROSPECTIVE_FP_SIS_SNAPSHOT_V1
MAX_PAYLOAD_BYTES=16777216

decode_exact_file() {
  [[ $# -eq 4 ]] || die "decode-exact-file contract differs"
  local payload_env=$1 digest_env=$2 destination=$3 label=$4
  local expected_digest=${!digest_env:-}
  [[ "$expected_digest" =~ ^[0-9a-f]{64}$ ]] || die "$label SHA-256 differs"
  [[ -n "${!payload_env:-}" ]] || die "$label base64 is absent"
  umask 077
  printf '%s' "${!payload_env}" | base64 --decode >"$destination" || \
    die "$label base64 decode failed"
  [[ -f "$destination" && ! -L "$destination" ]] || die "$label file differs"
  local size
  size=$(stat -c '%s' "$destination") || die "$label stat failed"
  [[ "$size" =~ ^[0-9]+$ && "$size" -ge 1 && \
     "$size" -le "$MAX_PAYLOAD_BYTES" ]] || die "$label size differs"
  [[ "$(sha256sum "$destination" | awk '{print $1}')" == \
      "$expected_digest" ]] || die "$label bytes differ"
}

container_runtime_gate() {
  [[ $# -eq 1 ]] || die "container runtime gate requires one mode"
  local mode=$1 module_path
  [[ "${CODE_SHA:-}" =~ ^[0-9a-f]{40}$ ]] || die "runtime CODE_SHA differs"
  [[ "${IMAGE_SOURCE_COMMIT_SHA:-}" == "$CODE_SHA" ]] || \
    die "runtime image/source commit differs"
  [[ "${!MODULE_SHA_ENV:-}" =~ ^[0-9a-f]{64}$ ]] || \
    die "runtime projection-module SHA differs"
  module_path=/app/src/nfl_dfs/research/corpus_r6_paid_source_normalized_snapshot_v1.py
  [[ -f "$module_path" && ! -L "$module_path" ]] || \
    die "runtime projection module differs"
  [[ "$(sha256sum "$module_path" | awk '{print $1}')" == \
      "${!MODULE_SHA_ENV}" ]] || die "runtime projection module bytes differ"
  [[ "$(cat /app/SOURCE_COMMIT)" == "$CODE_SHA" ]] || \
    die "runtime source-commit file differs"
  [[ "${IMAGE_DIGEST:-}" =~ ^sha256:[0-9a-f]{64}$ ]] || \
    die "runtime image digest differs"
  [[ "${IMAGE_URI:-}" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || \
    die "runtime immutable image differs"
  [[ "${IMAGE_URI##*@}" == "$IMAGE_DIGEST" ]] || \
    die "runtime immutable image/digest differs"
  [[ "${BUILD_ID:-}" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || \
    die "runtime build ID differs"
  [[ "${CLOUD_RUN_TASK_INDEX:-}" == "0" && \
     "${CLOUD_RUN_TASK_COUNT:-}" == "1" && \
     "${CLOUD_RUN_TASK_ATTEMPT:-}" == "0" ]] || \
    die "normalized snapshot requires one first-attempt Cloud Run task"
  [[ "${!OUTCOMES_ENV:-}" == "false" ]] || \
    die "normalized snapshot outcome boundary differs"
  case "$mode" in
    task0)
      [[ "${!TASK0_ENABLE_ENV:-}" == "$ENABLE_VALUE" && \
         "${!PUBLISH_ENABLE_ENV:-}" == "DISABLED" && \
         "${!REOPEN_ENABLE_ENV:-}" == "DISABLED" ]] || \
        die "task0 mode gates differ"
      ;;
    publish)
      [[ "${!TASK0_ENABLE_ENV:-}" == "DISABLED" && \
         "${!PUBLISH_ENABLE_ENV:-}" == "$ENABLE_VALUE" && \
         "${!REOPEN_ENABLE_ENV:-}" == "DISABLED" ]] || \
        die "publish mode gates differ"
      ;;
    reopen)
      [[ "${!TASK0_ENABLE_ENV:-}" == "DISABLED" && \
         "${!PUBLISH_ENABLE_ENV:-}" == "DISABLED" && \
         "${!REOPEN_ENABLE_ENV:-}" == "$ENABLE_VALUE" ]] || \
        die "reopen mode gates differ"
      ;;
    *) die "unsupported normalized-snapshot runtime mode" ;;
  esac
}

container_run() {
  [[ $# -eq 1 ]] || die "container-run requires one mode"
  local mode=$1 work payload receipt
  case "$mode" in task0|publish|reopen) ;; *) die "unsupported normalized-snapshot container mode" ;; esac
  container_runtime_gate "$mode"
  work=$(mktemp -d /tmp/paid-source-normalized-snapshot.XXXXXX)
  cleanup_normalized_snapshot_payload() { rm -rf "$work"; }
  trap cleanup_normalized_snapshot_payload EXIT
  payload=$work/payload.json
  decode_exact_file "$PAYLOAD_B64_ENV" "$PAYLOAD_SHA_ENV" \
    "$payload" "normalized-snapshot payload"
  case "$mode" in
    task0)
      /usr/local/bin/python3.11 -I "$RUNNER" task0 --request "$payload" \
        --repository-root "$REPOSITORY_ROOT" --execute
      ;;
    publish)
      receipt=$work/task0-receipt.json
      decode_exact_file "$TASK0_B64_ENV" "$TASK0_SHA_ENV" \
        "$receipt" "normalized-snapshot task0 receipt"
      /usr/local/bin/python3.11 -I "$RUNNER" publish --request "$payload" \
        --task0-receipt "$receipt" --repository-root "$REPOSITORY_ROOT" \
        --execute
      ;;
    reopen)
      /usr/local/bin/python3.11 -I "$RUNNER" reopen \
        --terminal-identity "$payload" --execute
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
TASK_TIMEOUT=3600s
CPU=2
MEMORY=4Gi
MODULE_PATH=src/nfl_dfs/research/corpus_r6_paid_source_normalized_snapshot_v1.py

require_committed_release_paths_clean() {
  [[ $# -ge 3 ]] || die "release-path validation requires root, commit, and paths"
  local root=$1 commit=$2 relative status
  shift 2
  for relative in "$@"; do
    git -C "$root" cat-file -e "${commit}:${relative}" || \
      die "committed release input absent: $relative"
    [[ -f "$root/$relative" && ! -L "$root/$relative" ]] || \
      die "local release input is absent or aliased: $relative"
    status=$(git -C "$root" status --porcelain --untracked-files=all -- "$relative")
    [[ -z "$status" ]] || die "local release input differs from commit: $relative"
  done
}

release_paths=(
  Dockerfile.corpus-r6-paid-source-normalized-snapshot
  Dockerfile.corpus-r6-paid-source-normalized-snapshot.dockerignore
  cloudbuild.corpus-r6-paid-source-normalized-snapshot.yaml
  pyproject.toml
  README.md
  scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh
  scripts/run_corpus_r6_paid_source_normalized_snapshot_v1.py
  scripts/run_corpus_r6_matchup_seven_pack_capture_v1.py
  src/nfl_dfs/research/corpus_r6_paid_source_normalized_snapshot_v1.py
  src/nfl_dfs/research/corpus_r6_matchup_seven_pack_capture_v1.py
  src/nfl_dfs/research/corpus_r6_matchup_source_v2.py
  src/nfl_dfs/research/corpus_r6_player_catalog_v1.py
  src/nfl_dfs/research/corpus_parametric_batch.py
  tests/test_corpus_r6_matchup_seven_pack_capture_v1.py
  tests/test_corpus_r6_paid_source_normalized_snapshot_v1.py
  tests/test_run_corpus_r6_paid_source_normalized_snapshot_v1.py
  tests/test_cloud_corpus_r6_paid_source_normalized_snapshot_v1.py
)

if [[ "${1:-}" == "build" ]]; then
  [[ $# -eq 2 && "$2" =~ ^[0-9a-f]{40}$ ]] || \
    die "usage: $0 build FULL_PUSHED_CODE_SHA"
  build_code_sha=$2
  build_root=$(git rev-parse --show-toplevel 2>/dev/null) || \
    die "repository root unavailable"
  [[ "$(git -C "$build_root" rev-parse HEAD)" == "$build_code_sha" ]] || \
    die "build source commit must equal HEAD"
  [[ "$(git -C "$build_root" rev-parse --verify 'refs/remotes/origin/main^{commit}')" == \
      "$build_code_sha" ]] || die "build source commit must equal durable origin/main"
  require_committed_release_paths_clean \
    "$build_root" "$build_code_sha" "${release_paths[@]}"
  module_sha=$(git -C "$build_root" show \
    "${build_code_sha}:${MODULE_PATH}" | sha256sum | awk '{print $1}')
  [[ "$module_sha" =~ ^[0-9a-f]{64}$ && \
     "$(sha256sum "$build_root/$MODULE_PATH" | awk '{print $1}')" == "$module_sha" ]] || \
    die "committed projection module identity differs"
  build_image="${REGION}-docker.pkg.dev/${PROJECT}/nfl-dfs/nfl-dfs:paid-source-normalized-snapshot-${build_code_sha}"
  mkdir -p "$build_root/.build-contexts"
  build_temp=$(mktemp -d "$build_root/.build-contexts/paid-source-normalized-snapshot-build.XXXXXX")
  cleanup_build() { rm -rf "$build_temp"; }
  trap cleanup_build EXIT
  submit_output=$(gcloud builds submit "$SOURCE_REPOSITORY" \
    --git-source-revision "$build_code_sha" \
    --config "$build_root/cloudbuild.corpus-r6-paid-source-normalized-snapshot.yaml" \
    --substitutions "_CODE_SHA=$build_code_sha,_MODULE_SHA=$module_sha,_BUILD_IMAGE=$build_image" \
    --project "$PROJECT" --format='value(id)' --quiet)
  mapfile -t build_ids < <(
    printf '%s\n' "$submit_output" |
      grep -Eo '[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}' |
      sort -u
  )
  [[ "${#build_ids[@]}" -eq 1 ]] || \
    die "Cloud Build did not return exactly one durable build ID"
  built_id=${build_ids[0]}
  build_json=$build_temp/build.json
  gcloud builds describe "$built_id" --project "$PROJECT" --format=json >"$build_json"
  built_digest=$(jq -er --arg id "$built_id" --arg tag "$build_image" \
    --arg sha "$build_code_sha" --arg module "$module_sha" \
    --arg repository "$SOURCE_REPOSITORY" '
      select(.id == $id and .status == "SUCCESS" and
        .source.gitSource == {url:$repository,revision:$sha} and
        .sourceProvenance.resolvedGitSource == {url:$repository,revision:$sha} and
        .substitutions._CODE_SHA == $sha and
        .substitutions._MODULE_SHA == $module and
        .substitutions._BUILD_IMAGE == $tag) |
      [ .results.images[]? | select(.name == $tag) | .digest ] |
      if length == 1 then .[0] else error("resolved image count differs") end
    ' "$build_json") || die "completed Cloud Build authority differs"
  [[ "$built_digest" =~ ^sha256:[0-9a-f]{64}$ ]] || \
    die "provider-resolved image digest differs"
  immutable_image="${build_image%:*}@${built_digest}"
  jq -n --arg schema "corpus-r6-paid-source-normalized-snapshot-cloud-build/v1" \
    --arg code_sha "$build_code_sha" --arg module_sha "$module_sha" \
    --arg build_id "$built_id" --arg tag "$build_image" \
    --arg image "$immutable_image" --arg digest "$built_digest" \
    --arg source "$SOURCE_REPOSITORY" '{
      schema_version:$schema,code_sha:$code_sha,module_sha256:$module_sha,
      cloud_build_id:$build_id,build_image_tag:$tag,
      provider_resolved_image:$image,image_digest:$digest,
      source_repository:$source,provider_requested_and_resolved_git_source_exact:true,
      outcome_artifacts_read_by_build_steps:false,
      outcome_artifacts_in_runtime_image_context:false,complete:true
    }'
  exit 0
fi

[[ $# -ge 4 && $# -le 6 ]] || \
  die "usage: $0 {install|task0|reopen|result} IMAGE@sha256:DIGEST FULL_CODE_SHA BUILD_ID [ABSOLUTE_PAYLOAD_JSON]; or: $0 publish IMAGE@sha256:DIGEST FULL_CODE_SHA BUILD_ID ABSOLUTE_REQUEST_JSON EXACT_TASK0_EXECUTION"
ACTION=$1
IMAGE=$2
CODE_SHA=$3
BUILD_ID=$4
PAYLOAD_PATH=${5:-}
TASK0_EXECUTION=${6:-}
[[ "$ACTION" =~ ^(install|task0|publish|reopen|result)$ ]] || die "unknown action"
[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/${PROJECT}/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || \
  die "image must be one immutable project image"
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "CODE_SHA must be one full commit"
[[ "$BUILD_ID" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || \
  die "BUILD_ID must be one provider UUID"
if [[ "$ACTION" == "publish" ]]; then
  [[ $# -eq 6 && "$TASK0_EXECUTION" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
    die "publish requires one exact successful task0 execution"
else
  [[ $# -le 5 ]] || die "$ACTION accepts no task0 execution argument"
fi

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || die "repository root unavailable"
[[ "$(git -C "$ROOT" rev-parse HEAD)" == "$CODE_SHA" ]] || die "CODE_SHA must equal HEAD"
[[ "$(git -C "$ROOT" rev-parse --verify 'refs/remotes/origin/main^{commit}')" == "$CODE_SHA" ]] || \
  die "CODE_SHA must equal durable origin/main"
require_committed_release_paths_clean "$ROOT" "$CODE_SHA" "${release_paths[@]}"
module_sha=$(git -C "$ROOT" show "${CODE_SHA}:${MODULE_PATH}" | sha256sum | awk '{print $1}')
[[ "$module_sha" =~ ^[0-9a-f]{64}$ && \
   "$(sha256sum "$ROOT/$MODULE_PATH" | awk '{print $1}')" == "$module_sha" ]] || \
  die "projection module identity differs"
image_digest=${IMAGE##*@}
image_tag="${IMAGE%@*}:paid-source-normalized-snapshot-${CODE_SHA}"

mkdir -p "$ROOT/.build-contexts"
temp_dir=$(mktemp -d "$ROOT/.build-contexts/paid-source-normalized-snapshot-launch.XXXXXX")
cleanup_host() { rm -rf "$temp_dir"; }
trap cleanup_host EXIT
build_json=$temp_dir/build.json
job_before=$temp_dir/job-before.json
job_after=$temp_dir/job-after.json
execution_json=$temp_dir/execution.json
launch_json=$temp_dir/launch.json

gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format=json >"$build_json"
jq -e --arg build "$BUILD_ID" --arg sha "$CODE_SHA" --arg module "$module_sha" \
  --arg tag "$image_tag" --arg digest "$image_digest" \
  --arg repository "$SOURCE_REPOSITORY" '
  .id == $build and .status == "SUCCESS" and
  .source.gitSource == {url:$repository,revision:$sha} and
  .sourceProvenance.resolvedGitSource == {url:$repository,revision:$sha} and
  .substitutions._CODE_SHA == $sha and .substitutions._MODULE_SHA == $module and
  .substitutions._BUILD_IMAGE == $tag and
  ([.results.images[]? | select(.name == $tag and .digest == $digest)] | length) == 1
' "$build_json" >/dev/null || die "Cloud Build authority differs"

gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format=json >"$job_before"
jq -e --arg uid "$EXPECTED_JOB_UID" '
  .metadata.uid == $uid and
  any(.status.conditions[]?; .type == "Ready" and .status == "True")
' "$job_before" >/dev/null || die "reused job identity/readiness differs"
if [[ "$ACTION" != "result" ]]; then
  prior_execution=$(jq -er '.status.latestCreatedExecution.name' "$job_before") || \
    die "reused job lacks an exact latest execution"
  gcloud run jobs executions describe "$prior_execution" --project "$PROJECT" \
    --region "$REGION" --format=json >"$execution_json"
  jq -e --arg job "$JOB" '
    .metadata.labels["run.googleapis.com/job"] == $job and
    any(.status.conditions[]?; .type == "Completed" and .status == "True") and
    (.status.completionTime | type == "string" and length > 0) and
    (.status.failedCount // 0) == 0 and (.status.cancelledCount // 0) == 0 and
    (.status.runningCount // 0) == 0
  ' "$execution_json" >/dev/null || \
    die "reused job latest execution is not terminal-success"
fi

verify_installed_job() {
  [[ $# -eq 1 ]] || die "job verification requires one observation"
  jq -e --arg uid "$EXPECTED_JOB_UID" --arg image "$IMAGE" \
    --arg sha "$CODE_SHA" --arg digest "$image_digest" \
    --arg build "$BUILD_ID" --arg module "$module_sha" \
    --arg sa "$SERVICE_ACCOUNT" '
    .metadata.uid == $uid and .spec.template.spec.taskCount == 1 and
    .spec.template.spec.parallelism == 1 and
    .spec.template.spec.template.spec.maxRetries == 0 and
    (.spec.template.spec.template.spec.timeoutSeconds == "3600" or
     .spec.template.spec.template.spec.timeout == "3600s") and
    .spec.template.spec.template.spec.serviceAccountName == $sa and
    (.spec.template.spec.template.spec.containers | length) == 1 and
    (.spec.template.spec.template.spec.containers[0] as $c |
      $c.image == $image and $c.command == ["/bin/bash"] and
      $c.args == ["/app/scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh","container-help"] and
      $c.resources.limits.cpu == "2" and $c.resources.limits.memory == "4Gi" and
      ([ $c.env[] | select(.name == "CODE_SHA") | .value ] == [$sha]) and
      ([ $c.env[] | select(.name == "IMAGE_DIGEST") | .value ] == [$digest]) and
      ([ $c.env[] | select(.name == "BUILD_ID") | .value ] == [$build]) and
      ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_MODULE_SHA256") | .value ] == [$module]) and
      ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_TASK0") | .value ] == ["DISABLED_INSTALL_ONLY"]) and
      ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_PUBLISH") | .value ] == ["DISABLED_INSTALL_ONLY"]) and
      ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_REOPEN") | .value ] == ["DISABLED_INSTALL_ONLY"]) and
      ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_OUTCOMES_ALLOWED") | .value ] == ["false"])
    )
  ' "$1" >/dev/null || die "installed reused-job template differs"
}

if [[ "$ACTION" == "install" ]]; then
  [[ -z "$PAYLOAD_PATH" ]] || die "install accepts no payload"
  gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
    --image "$IMAGE" --command /bin/bash \
    --args /app/scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh,container-help \
    --tasks 1 --parallelism 1 --max-retries 0 --cpu "$CPU" --memory "$MEMORY" \
    --task-timeout "$TASK_TIMEOUT" --service-account "$SERVICE_ACCOUNT" \
    --set-env-vars "CODE_SHA=$CODE_SHA,IMAGE_DIGEST=$image_digest,BUILD_ID=$BUILD_ID,$MODULE_SHA_ENV=$module_sha,$TASK0_ENABLE_ENV=DISABLED_INSTALL_ONLY,$PUBLISH_ENABLE_ENV=DISABLED_INSTALL_ONLY,$REOPEN_ENABLE_ENV=DISABLED_INSTALL_ONLY,$OUTCOMES_ENV=false" \
    --quiet >/dev/null
  gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
    --format=json >"$job_after"
  verify_installed_job "$job_after"
  prior_generation=$(jq -er '.metadata.generation' "$job_before")
  installed_generation=$(jq -er '.metadata.generation' "$job_after")
  [[ "$prior_generation" =~ ^[0-9]+$ && "$installed_generation" =~ ^[0-9]+$ && \
     "$installed_generation" -gt "$prior_generation" ]] || \
    die "reused job generation did not advance through installation"
  jq -n --arg schema "corpus-r6-paid-source-normalized-snapshot-cloud-install/v1" \
    --arg code "$CODE_SHA" --arg module "$module_sha" --arg build "$BUILD_ID" \
    --arg image "$IMAGE" --arg job "$JOB" --arg uid "$EXPECTED_JOB_UID" \
    --argjson generation "$installed_generation" --arg prior "$prior_execution" '{
      schema_version:$schema,code_sha:$code,module_sha256:$module,
      cloud_build_id:$build,provider_resolved_image:$image,
      reused_job:{name:$job,uid:$uid,generation:$generation},
      prior_terminal_execution:$prior,install_only:true,execution_launched:false,
      outcomes_allowed:false,complete:true
    }'
  exit 0
fi

if [[ "$ACTION" == "result" ]]; then
  result_execution=$PAYLOAD_PATH
  [[ "$result_execution" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
    die "result requires one exact normalized-snapshot execution name"
  gcloud run jobs executions describe "$result_execution" --project "$PROJECT" \
    --region "$REGION" --format=json >"$execution_json"
  result_phase=$(jq -er '
    .spec.template.spec.containers[0].args as $args |
    if $args == ["/app/scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh","container-run","task0"] then "task0"
    elif $args == ["/app/scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh","container-run","publish"] then "publish"
    elif $args == ["/app/scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh","container-run","reopen"] then "reopen"
    else error("result execution phase differs") end
  ' "$execution_json") || die "result execution command differs"
  case "$result_phase" in
    task0) task0_gate=$ENABLE_VALUE; publish_gate=DISABLED; reopen_gate=DISABLED ;;
    publish) task0_gate=DISABLED; publish_gate=$ENABLE_VALUE; reopen_gate=DISABLED ;;
    reopen) task0_gate=DISABLED; publish_gate=DISABLED; reopen_gate=$ENABLE_VALUE ;;
  esac
  jq -e --arg execution "$result_execution" --arg job "$JOB" \
    --arg uid "$EXPECTED_JOB_UID" --arg image "$IMAGE" --arg sha "$CODE_SHA" \
    --arg digest "$image_digest" --arg build "$BUILD_ID" --arg module "$module_sha" \
    --arg task0 "$task0_gate" --arg publish "$publish_gate" --arg reopen "$reopen_gate" \
    --arg sa "$SERVICE_ACCOUNT" '
    .metadata.name == $execution and
    .metadata.labels["run.googleapis.com/job"] == $job and
    .metadata.labels["run.googleapis.com/jobUid"] == $uid and
    (.metadata.labels["run.googleapis.com/jobGeneration"] | test("^[0-9]+$")) and
    any(.status.conditions[]?; .type == "Completed" and .status == "True") and
    (.status.completionTime | type == "string" and length > 0) and
    (.status.succeededCount // 0) == 1 and (.status.failedCount // 0) == 0 and
    (.status.cancelledCount // 0) == 0 and (.status.runningCount // 0) == 0 and
    .spec.taskCount == 1 and .spec.template.spec.maxRetries == 0 and
    .spec.template.spec.serviceAccountName == $sa and
    (.spec.template.spec.containers | length) == 1 and
    (.spec.template.spec.containers[0] as $c |
      $c.image == $image and $c.command == ["/bin/bash"] and
      $c.resources.limits.cpu == "2" and $c.resources.limits.memory == "4Gi" and
      ([ $c.env[] | select(.name == "CODE_SHA") | .value ] == [$sha]) and
      ([ $c.env[] | select(.name == "IMAGE_DIGEST") | .value ] == [$digest]) and
      ([ $c.env[] | select(.name == "BUILD_ID") | .value ] == [$build]) and
      ([ $c.env[] | select(.name == "IMAGE_URI") | .value ] == [$image]) and
      ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_MODULE_SHA256") | .value ] == [$module]) and
      ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_TASK0") | .value ] == [$task0]) and
      ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_PUBLISH") | .value ] == [$publish]) and
      ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_REOPEN") | .value ] == [$reopen]) and
      ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_OUTCOMES_ALLOWED") | .value ] == ["false"]) and
      (([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_BOUND_SHA256") | .value ]) | length) == 1 and
      (([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_PAYLOAD_SHA256") | .value ]) | length) == 1 and
      (([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_PAYLOAD_B64") | .value ]) | length) == 1
    )
  ' "$execution_json" >/dev/null || die "terminal result execution differs"
  result_payload_b64=$(jq -er '[.spec.template.spec.containers[0].env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_PAYLOAD_B64") | .value] | if length == 1 then .[0] else error("payload b64 differs") end' "$execution_json")
  result_payload_sha=$(jq -er '[.spec.template.spec.containers[0].env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_PAYLOAD_SHA256") | .value] | if length == 1 then .[0] else error("payload hash differs") end' "$execution_json")
  [[ "${#result_payload_b64}" -le 1400000 && "$result_payload_sha" =~ ^[0-9a-f]{64}$ ]] || \
    die "result payload envelope differs"
  result_payload=$temp_dir/result-payload.json
  printf '%s' "$result_payload_b64" | base64 --decode >"$result_payload" || \
    die "result payload base64 differs"
  [[ "$(sha256sum "$result_payload" | awk '{print $1}')" == "$result_payload_sha" ]] || \
    die "result payload bytes differ"
  result_bound=$(jq -er '[.spec.template.spec.containers[0].env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_BOUND_SHA256") | .value] | if length == 1 then .[0] else error("bound hash differs") end' "$execution_json")
  if [[ "$result_phase" == "reopen" ]]; then
    [[ "$result_bound" == "$(jq -er '.sha256' "$result_payload")" ]] || \
      die "result terminal identity binding differs"
  else
    [[ "$result_bound" == "$(jq -er '.snapshot_request_sha256' "$result_payload")" ]] || \
      die "result snapshot request binding differs"
  fi
  if [[ "$result_phase" == "publish" ]]; then
    result_task0_b64=$(jq -er '[.spec.template.spec.containers[0].env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_TASK0_RECEIPT_B64") | .value] | if length == 1 then .[0] else error("task0 b64 differs") end' "$execution_json")
    result_task0_sha=$(jq -er '[.spec.template.spec.containers[0].env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_TASK0_RECEIPT_SHA256") | .value] | if length == 1 then .[0] else error("task0 hash differs") end' "$execution_json")
    result_task0=$temp_dir/result-task0.json
    printf '%s' "$result_task0_b64" | base64 --decode >"$result_task0" || \
      die "result task0 receipt base64 differs"
    [[ "$(sha256sum "$result_task0" | awk '{print $1}')" == "$result_task0_sha" && \
       "$(jq -er '.snapshot_request_sha256' "$result_task0")" == "$result_bound" && \
       "$(jq -er '.publication_count' "$result_task0")" == "0" ]] || \
      die "result task0 receipt binding differs"
  fi
  result_logs=$temp_dir/result-stdout.json
  log_filter="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$result_execution\" AND logName=\"projects/$PROJECT/logs/run.googleapis.com%2Fstdout\" AND textPayload:*"
  gcloud logging read "$log_filter" --project "$PROJECT" --limit 100 \
    --order=asc --format=json >"$result_logs"
  case "$result_phase" in
    task0) result_schema=corpus-r6-paid-source-normalized-snapshot-task0/v1 ;;
    publish) result_schema=corpus-r6-paid-source-normalized-snapshot-publication-result/v1 ;;
    reopen) result_schema=corpus-r6-paid-source-normalized-snapshot-reopen/v1 ;;
  esac
  result_raw=$(jq -er --arg schema "$result_schema" '
    [.[] | .textPayload? | select(type == "string") as $raw |
      ($raw | fromjson?) as $body | select($body.schema_version == $schema) | $raw] |
    if length == 1 then .[0] else error("operator stdout receipt count differs") end
  ' "$result_logs") || die "operator stdout receipt count differs"
  result_canonical=$(printf '%s' "$result_raw" | jq -cS .) || \
    die "operator stdout receipt is not JSON"
  [[ "$result_raw" == "$result_canonical" ]] || \
    die "operator stdout receipt is not canonical JSON"
  result_receipt=$temp_dir/operator-receipt.json
  printf '%s' "$result_raw" >"$result_receipt"
  case "$result_phase" in
    task0)
      jq -e --arg request "$result_bound" '
        .snapshot_request_sha256 == $request and .publication_count == 0 and
        .publication_callback_present == false and
        .write_api_reachable_from_task0 == false and
        .runtime_principal_write_authority_status == "not-evaluated" and
        .recognized_outcome_callback_present == false and
        .runtime_principal_outcome_authority_status == "not-evaluated" and
        .outcome_artifacts_read == [] and
        .full_snapshot_launched == false and .mechanical_launch_gate_passed == true and
        .uses_realized_outcomes == false and .authoritative_pit == false and .complete == true
      ' "$result_receipt" >/dev/null || die "task0 stdout result differs"
      ;;
    publish)
      jq -e --arg request "$result_bound" '
        .terminal.snapshot_request_sha256 == $request and
        (.terminal_identity | type == "object") and
        (.artifact_manifest_identities | keys | length) == 2 and
        .independent_reopen.both_manifests_and_all_exact_predecessors_reopened == true and
        .uses_realized_outcomes == false and .authoritative_pit == false and .complete == true
      ' "$result_receipt" >/dev/null || die "publish stdout result differs"
      ;;
    reopen)
      jq -e --argjson terminal "$(jq -cS . "$result_payload")" '
        .terminal_identity == $terminal and .artifact_manifest_count == 2 and
        .both_manifests_and_all_exact_predecessors_reopened == true and
        .publication_callback_present == false and
        .runtime_principal_write_authority_status == "not-evaluated" and
        .recognized_outcome_callback_present == false and
        .runtime_principal_outcome_authority_status == "not-evaluated" and
        .outcome_artifacts_read == [] and
        .uses_realized_outcomes == false and .authoritative_pit == false and .complete == true
      ' "$result_receipt" >/dev/null || die "reopen stdout result differs"
      ;;
  esac
  jq -n --arg schema "corpus-r6-paid-source-normalized-snapshot-cloud-result/v1" \
    --arg phase "$result_phase" --arg code "$CODE_SHA" --arg module "$module_sha" \
    --arg build "$BUILD_ID" --arg image "$IMAGE" --arg execution "$result_execution" \
    --arg uid "$(jq -er '.metadata.uid' "$execution_json")" \
    --arg completed "$(jq -er '.status.completionTime' "$execution_json")" \
    --argjson receipt "$(jq -cS . "$result_receipt")" '{
      schema_version:$schema,phase:$phase,code_sha:$code,module_sha256:$module,
      cloud_build_id:$build,provider_resolved_image:$image,
      execution:{name:$execution,uid:$uid,task_count:1,succeeded_count:1,
        failed_count:0,cancelled_count:0,completion_time:$completed},
      operator_receipt:$receipt,exact_execution_stdout_only:true,complete:true
    }'
  exit 0
fi

[[ -n "$PAYLOAD_PATH" && "$PAYLOAD_PATH" == /* && -f "$PAYLOAD_PATH" && \
   ! -L "$PAYLOAD_PATH" ]] || die "$ACTION requires one absolute unaliased payload file"
gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format=json >"$job_after"
verify_installed_job "$job_after"

payload_sha=$(sha256sum "$PAYLOAD_PATH" | awk '{print $1}')
payload_b64=$(base64 -w0 "$PAYLOAD_PATH")
[[ "${#payload_b64}" -le 1400000 ]] || die "payload exceeds Cloud Run override ceiling"
task0_gate=DISABLED
publish_gate=DISABLED
reopen_gate=DISABLED
task0_receipt_sha=
task0_receipt_b64=
case "$ACTION" in
  task0)
    "$ROOT/.venv/bin/python" "$ROOT/scripts/run_corpus_r6_paid_source_normalized_snapshot_v1.py" \
      validate --request "$PAYLOAD_PATH" >/dev/null || die "snapshot request validation failed"
    bound_sha=$(jq -er '.snapshot_request_sha256' "$PAYLOAD_PATH")
    task0_gate=$ENABLE_VALUE
    ;;
  publish)
    "$ROOT/.venv/bin/python" "$ROOT/scripts/run_corpus_r6_paid_source_normalized_snapshot_v1.py" \
      validate --request "$PAYLOAD_PATH" >/dev/null || die "snapshot request validation failed"
    bound_sha=$(jq -er '.snapshot_request_sha256' "$PAYLOAD_PATH")
    gate_result=$temp_dir/task0-gate-result.json
    "$ROOT/scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh" \
      result "$IMAGE" "$CODE_SHA" "$BUILD_ID" "$TASK0_EXECUTION" >"$gate_result"
    jq -e --arg image "$IMAGE" --arg code "$CODE_SHA" --arg build "$BUILD_ID" \
      --arg execution "$TASK0_EXECUTION" --arg request "$bound_sha" '
      .schema_version == "corpus-r6-paid-source-normalized-snapshot-cloud-result/v1" and
      .phase == "task0" and .provider_resolved_image == $image and
      .code_sha == $code and .cloud_build_id == $build and
      .execution.name == $execution and .execution.task_count == 1 and
      .execution.succeeded_count == 1 and .execution.failed_count == 0 and
      .operator_receipt.snapshot_request_sha256 == $request and
      .operator_receipt.publication_count == 0 and
      .operator_receipt.mechanical_launch_gate_passed == true and
      .operator_receipt.uses_realized_outcomes == false and
      .operator_receipt.complete == true and .complete == true
    ' "$gate_result" >/dev/null || die "task0 launch gate differs"
    task0_receipt=$temp_dir/task0-receipt.json
    jq -cS '.operator_receipt' "$gate_result" >"$task0_receipt"
    task0_receipt_sha=$(sha256sum "$task0_receipt" | awk '{print $1}')
    task0_receipt_b64=$(base64 -w0 "$task0_receipt")
    publish_gate=$ENABLE_VALUE
    ;;
  reopen)
    jq -e '
      (keys | sort) == (["bytes","generation","sha256","uri"] | sort) and
      (.uri | startswith("gs://")) and
      (.generation | type == "string" and test("^[1-9][0-9]*$")) and
      (.sha256 | test("^[0-9a-f]{64}$")) and (.bytes | type == "number" and . > 0)
    ' "$PAYLOAD_PATH" >/dev/null || die "terminal identity payload differs"
    bound_sha=$(jq -er '.sha256' "$PAYLOAD_PATH")
    reopen_gate=$ENABLE_VALUE
    ;;
esac
[[ "$bound_sha" =~ ^[0-9a-f]{64}$ ]] || die "bound payload identity differs"

execution_args="/app/scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh,container-run,$ACTION"
env_override="^|^CODE_SHA=$CODE_SHA|IMAGE_DIGEST=$image_digest|IMAGE_URI=$IMAGE|BUILD_ID=$BUILD_ID|$MODULE_SHA_ENV=$module_sha|$PAYLOAD_SHA_ENV=$payload_sha|$PAYLOAD_B64_ENV=$payload_b64|$BOUND_SHA_ENV=$bound_sha|$TASK0_ENABLE_ENV=$task0_gate|$PUBLISH_ENABLE_ENV=$publish_gate|$REOPEN_ENABLE_ENV=$reopen_gate|$OUTCOMES_ENV=false"
if [[ "$ACTION" == "publish" ]]; then
  env_override="$env_override|$TASK0_SHA_ENV=$task0_receipt_sha|$TASK0_B64_ENV=$task0_receipt_b64"
fi
gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --tasks 1 --args "$execution_args" --update-env-vars "$env_override" \
  --async --format=json >"$launch_json"
execution_name=$(jq -er '.metadata.name' "$launch_json") || die "launch lacks execution name"
[[ "$execution_name" =~ ^${JOB}-[a-z0-9]{5}$ ]] || die "execution is not bound to reused job"
gcloud run jobs executions describe "$execution_name" --project "$PROJECT" \
  --region "$REGION" --format=json >"$execution_json"
job_generation=$(jq -er '.metadata.generation' "$job_after")
jq -e --arg execution "$execution_name" --arg job "$JOB" \
  --arg uid "$EXPECTED_JOB_UID" --arg generation "$job_generation" \
  --arg image "$IMAGE" --arg sha "$CODE_SHA" --arg digest "$image_digest" \
  --arg build "$BUILD_ID" --arg module "$module_sha" --arg payload "$payload_sha" \
  --arg bound "$bound_sha" --arg task0 "$task0_gate" --arg publish "$publish_gate" \
  --arg reopen "$reopen_gate" --arg sa "$SERVICE_ACCOUNT" '
  .metadata.name == $execution and .metadata.labels["run.googleapis.com/job"] == $job and
  .metadata.labels["run.googleapis.com/jobUid"] == $uid and
  .metadata.labels["run.googleapis.com/jobGeneration"] == $generation and
  .spec.taskCount == 1 and .spec.template.spec.maxRetries == 0 and
  .spec.template.spec.serviceAccountName == $sa and
  (.spec.template.spec.containers | length) == 1 and
  (.spec.template.spec.containers[0] as $c |
    $c.image == $image and $c.command == ["/bin/bash"] and
    $c.resources.limits.cpu == "2" and $c.resources.limits.memory == "4Gi" and
    ([ $c.env[] | select(.name == "CODE_SHA") | .value ] == [$sha]) and
    ([ $c.env[] | select(.name == "IMAGE_DIGEST") | .value ] == [$digest]) and
    ([ $c.env[] | select(.name == "BUILD_ID") | .value ] == [$build]) and
    ([ $c.env[] | select(.name == "IMAGE_URI") | .value ] == [$image]) and
    ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_MODULE_SHA256") | .value ] == [$module]) and
    ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_PAYLOAD_SHA256") | .value ] == [$payload]) and
    ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_BOUND_SHA256") | .value ] == [$bound]) and
    ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_TASK0") | .value ] == [$task0]) and
    ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_PUBLISH") | .value ] == [$publish]) and
    ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_REOPEN") | .value ] == [$reopen]) and
    ([ $c.env[] | select(.name == "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_OUTCOMES_ALLOWED") | .value ] == ["false"])
  )
' "$execution_json" >/dev/null || die "launched execution provider authority differs"
execution_uid=$(jq -er '.metadata.uid' "$execution_json") || die "execution UID absent"
jq -n --arg schema "corpus-r6-paid-source-normalized-snapshot-cloud-launch/v1" \
  --arg phase "$ACTION" --arg code "$CODE_SHA" --arg module "$module_sha" \
  --arg build "$BUILD_ID" --arg image "$IMAGE" --arg job "$JOB" \
  --arg job_uid "$EXPECTED_JOB_UID" --argjson generation "$job_generation" \
  --arg execution "$execution_name" --arg execution_uid "$execution_uid" \
  --arg payload "$payload_sha" --arg bound "$bound_sha" '{
    schema_version:$schema,phase:$phase,code_sha:$code,module_sha256:$module,
    cloud_build_id:$build,provider_resolved_image:$image,
    reused_job:{name:$job,uid:$job_uid,generation:$generation},
    execution:{name:$execution,uid:$execution_uid,task_count:1},
    payload_sha256:$payload,bound_input_sha256:$bound,
    outcomes_allowed:false,execution_provider_reopened:true,complete:true
  }'
