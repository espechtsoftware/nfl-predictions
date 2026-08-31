#!/usr/bin/env bash
# Immutable Cloud Build/Run release for Experiment 4.  Installation updates
# one already-existing shared research job into a dormant state.  Every phase
# is an explicit execution; this script never creates, deletes, or lists jobs.
set -euo pipefail

die() { printf '%s\n' "ERROR: $*" >&2; exit 2; }

RUNNER=/app/scripts/run_corpus_r6_broad_admission_tournament_v1.py
ENABLE_ENV=R6_BROAD_ADMISSION_ENABLE
ENABLE_VALUE=I_UNDERSTAND_FIXED_CORPUS_ADMISSION_TOURNAMENT_V1
REQUEST_B64_ENV=R6_BROAD_ADMISSION_REQUEST_B64
REQUEST_SHA_ENV=R6_BROAD_ADMISSION_REQUEST_SHA256
BOUND_IDENTITY_ENV=R6_BROAD_ADMISSION_BOUND_IDENTITY
OUTCOMES_ENV=R6_BROAD_ADMISSION_OUTCOMES_ALLOWED
TASK0_ENV=R6_BROAD_ADMISSION_TASK0_SMOKE

container_run() {
  [[ $# -eq 1 ]] || die "container-run requires one phase"
  local phase=$1 command request expected_outcomes=false
  case "$phase" in
    prepare|collect|reopen|grade-reopen) command=$phase ;;
    task0|task) command=task ;;
    grade) command=grade; expected_outcomes=true ;;
    *) die "unsupported in-container phase" ;;
  esac
  [[ "${!ENABLE_ENV:-}" == "$ENABLE_VALUE" ]] || \
    die "broad-admission execution is not explicitly enabled"
  [[ "${CODE_SHA:-}" =~ ^[0-9a-f]{40}$ ]] || die "runtime CODE_SHA differs"
  [[ "${IMAGE_SOURCE_COMMIT_SHA:-}" == "$CODE_SHA" ]] || \
    die "runtime image/source commit differs"
  [[ "${IMAGE_DIGEST:-}" =~ ^sha256:[0-9a-f]{64}$ ]] || \
    die "runtime image digest differs"
  [[ "${BUILD_ID:-}" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || \
    die "runtime build ID differs"
  [[ "${!OUTCOMES_ENV:-}" == "$expected_outcomes" ]] || \
    die "outcome boundary differs for $phase"

  request=$(mktemp /tmp/broad-admission-request.XXXXXX.json)
  local cleanup_command
  printf -v cleanup_command 'rm -f -- %q' "$request"
  trap "$cleanup_command" EXIT
  umask 077
  printf '%s' "${!REQUEST_B64_ENV:?missing request bytes}" | \
    base64 --decode >"$request" || die "request base64 decode failed"
  [[ "$(sha256sum "$request" | awk '{print $1}')" == \
      "${!REQUEST_SHA_ENV:?missing request hash}" ]] || die "request bytes differ"

  if [[ "$phase" == "task0" ]]; then
    export CLOUD_RUN_TASK_INDEX=0 CLOUD_RUN_TASK_COUNT=54
    export "$TASK0_ENV=true"
  elif [[ "$phase" == "task" ]]; then
    [[ "${CLOUD_RUN_TASK_COUNT:-}" == "54" ]] || \
      die "full task execution must contain 54 tasks"
    export "$TASK0_ENV=false"
  else
    export "$TASK0_ENV=false"
  fi
  /usr/local/bin/python3.11 -I "$RUNNER" "$command" \
    --request "$request" --execute
  rm -f -- "$request"
  trap - EXIT
}

case "${1:-}" in
  container-help)
    printf '%s\n' \
      'container phases: prepare task0 task collect reopen grade grade-reopen'
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
TASK_COUNT=54
PARALLELISM=54
TASK_TIMEOUT=21600s
CPU=8
MEMORY=32Gi

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

  build_image="${REGION}-docker.pkg.dev/${PROJECT}/nfl-dfs/nfl-dfs:broad-admission-${build_code_sha}"
  build_paths=(
    Dockerfile.corpus-r6-broad-admission
    Dockerfile.corpus-r6-broad-admission.dockerignore
    cloudbuild.corpus-r6-broad-admission.yaml
    pyproject.toml
    README.md
    scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh
    scripts/run_corpus_r6_broad_admission_tournament_v1.py
    scripts/run_corpus_r6_combined_frontier_reportfolio_v1.py
    scripts/run_corpus_r6_combined_population_all_block_v1.py
    scripts/run_corpus_r6_hard230_selector_bridge_v1.py
    scripts/run_corpus_r6_construction_allocation_grade_v1.py
    src/nfl_dfs/research/corpus_r6_construction_allocation_cross_operator_v1.py
    src/nfl_dfs/research/corpus_r6_broad_admission_tournament_v1.py
    src/nfl_dfs/research/corpus_r6_broad_admission_program_v1.py
    tests/conftest.py
    tests/test_corpus_r6_broad_admission_tournament_v1.py
    tests/test_corpus_r6_broad_admission_program_v1.py
    tests/test_run_corpus_r6_broad_admission_tournament_v1.py
    tests/test_cloud_corpus_r6_broad_admission_tournament_v1.py
  )
  require_committed_release_paths_clean \
    "$build_root" "$build_code_sha" "${build_paths[@]}"
  mkdir -p "$build_root/.build-contexts"
  build_temp=$(mktemp -d "$build_root/.build-contexts/broad-admission-build.XXXXXX")
  cleanup_build() { rm -rf "$build_temp"; }
  trap cleanup_build EXIT

  submit_output=$(gcloud builds submit "$SOURCE_REPOSITORY" \
    --git-source-revision "$build_code_sha" \
    --config "$build_root/cloudbuild.corpus-r6-broad-admission.yaml" \
    --substitutions "_CODE_SHA=$build_code_sha,_BUILD_IMAGE=$build_image" \
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
    --arg sha "$build_code_sha" --arg repository "$SOURCE_REPOSITORY" '
      select(.id == $id and .status == "SUCCESS" and
        .source.gitSource == {url:$repository,revision:$sha} and
        .sourceProvenance.resolvedGitSource == {url:$repository,revision:$sha} and
        .substitutions._CODE_SHA == $sha and
        .substitutions._BUILD_IMAGE == $tag) |
      [ .results.images[]? | select(.name == $tag) | .digest ] |
      if length == 1 then .[0] else error("resolved image count differs") end
    ' "$build_json") || die "completed Cloud Build authority differs"
  [[ "$built_digest" =~ ^sha256:[0-9a-f]{64}$ ]] || \
    die "provider-resolved image digest differs"
  immutable_image="${build_image%:*}@${built_digest}"
  attestation_uri="gs://${PROJECT}-corpus-retrieval/research/corpus-r6-broad-admission-builds/${build_code_sha}/${built_id}/runtime-build-attestation.json"
  attestation_identity=$build_temp/runtime-build-attestation.identity.json
  host_python=$build_root/.venv/bin/python
  [[ -x "$host_python" ]] || die "exact release virtualenv Python is absent"
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$build_root/src:$build_root/scripts" \
    "$host_python" - "$build_json" "$SOURCE_REPOSITORY" \
      "$build_code_sha" "$build_image" "$built_digest" "$attestation_uri" \
      >"$attestation_identity" <<'PY'
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import hashlib
import json
import sys

from nfl_dfs.research import (
    corpus_r6_construction_allocation_cross_operator_v1 as authority,
)
import run_corpus_r6_construction_allocation_grade_v1 as grade_runner


(
    metadata_path,
    source_repository,
    code_sha,
    image_tag,
    image_digest,
    attestation_uri,
) = sys.argv[1:]
try:
    metadata = json.loads(Path(metadata_path).read_bytes())
except (OSError, UnicodeError, json.JSONDecodeError) as exc:
    raise SystemExit(f"Cloud Build metadata bytes differ: {exc}")
if not isinstance(metadata, Mapping):
    raise SystemExit("Cloud Build metadata is not an object")
build_id = metadata.get("id")
finish_time = metadata.get("finishTime")
expected_source = {"url": source_repository, "revision": code_sha}
source = metadata.get("source")
provenance = metadata.get("sourceProvenance")
substitutions = metadata.get("substitutions")
results = metadata.get("results")
images = results.get("images") if isinstance(results, Mapping) else None
matching_images = [
    row for row in images or []
    if isinstance(row, Mapping)
    and row.get("name") == image_tag
    and row.get("digest") == image_digest
]
if (
    metadata.get("status") != "SUCCESS"
    or not isinstance(build_id, str)
    or not isinstance(finish_time, str)
    or not isinstance(source, Mapping)
    or source.get("gitSource") != expected_source
    or not isinstance(provenance, Mapping)
    or provenance.get("resolvedGitSource") != expected_source
    or not isinstance(substitutions, Mapping)
    or substitutions.get("_CODE_SHA") != code_sha
    or substitutions.get("_BUILD_IMAGE") != image_tag
    or len(matching_images) != 1
):
    raise SystemExit("provider-resolved direct-Git build authority differs")
attestation = authority.runtime_build_attestation_v1(
    build_id=build_id,
    source_repository=source_repository,
    requested_source_commit=code_sha,
    resolved_source_commit=code_sha,
    image_tag=image_tag,
    image_digest=image_digest,
    provider_observed_at=finish_time,
)
authority.validate_runtime_build_attestation_v1(
    attestation,
    expected_code_sha=code_sha,
    expected_image_digest=image_digest,
)
raw = json.dumps(
    attestation,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
    allow_nan=False,
).encode("utf-8")
store = grade_runner.GCSExactCreateOnceStoreV1()
published = store.publish_create_once(attestation_uri, raw)
identity = {
    key: published[key] for key in ("uri", "generation", "sha256", "bytes")
}
if (
    store.read_exact(identity) != raw
    or identity["sha256"] != hashlib.sha256(raw).hexdigest()
):
    raise SystemExit("runtime build attestation exact reopen differs")
sys.stdout.write(json.dumps(identity, sort_keys=True, separators=(",", ":")) + "\n")
PY
  jq -e '
    (keys | sort) == (["bytes","generation","sha256","uri"] | sort) and
    (.uri | startswith("gs://")) and
    (.generation | type == "string" and length > 0) and
    (.sha256 | test("^[0-9a-f]{64}$")) and
    (.bytes | type == "number" and . > 0)
  ' "$attestation_identity" >/dev/null || \
    die "runtime build attestation publication differs"
  jq -n --arg schema "corpus-r6-broad-admission-cloud-build/v1" \
    --arg code_sha "$build_code_sha" --arg build_id "$built_id" \
    --arg build_image "$build_image" --arg image "$immutable_image" \
    --arg digest "$built_digest" --arg source_repository "$SOURCE_REPOSITORY" \
    --argjson attestation "$(jq -cS . "$attestation_identity")" '{
      schema_version:$schema, code_sha:$code_sha, cloud_build_id:$build_id,
      build_image_tag:$build_image, provider_resolved_image:$image,
      image_digest:$digest, source_repository:$source_repository,
      runtime_build_attestation_identity:$attestation,
      provider_requested_and_resolved_git_source_exact:true,
      outcome_artifacts_read_by_build_steps:false,
      outcome_artifacts_in_runtime_image_context:false,
      complete:true
    }'
  exit 0
fi

[[ $# -ge 4 && $# -le 6 ]] || \
  die "usage: $0 {install|prepare|task0|collect|reopen|grade|grade-reopen|result} IMAGE@sha256:DIGEST FULL_CODE_SHA BUILD_ID [ABSOLUTE_REQUEST_JSON|EXACT_EXECUTION_NAME]; or: $0 task IMAGE@sha256:DIGEST FULL_CODE_SHA BUILD_ID ABSOLUTE_REQUEST_JSON EXACT_TASK0_EXECUTION_NAME"
ACTION=$1
IMAGE=$2
CODE_SHA=$3
BUILD_ID=$4
REQUEST_PATH=${5:-}
TASK0_GATE_EXECUTION=${6:-}

[[ "$ACTION" =~ ^(install|prepare|task0|task|collect|reopen|grade|grade-reopen|result)$ ]] || \
  die "unknown action"
[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/${PROJECT}/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || \
  die "image must be one immutable project image"
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "CODE_SHA must be one full commit"
[[ "$BUILD_ID" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || \
  die "BUILD_ID must be one provider UUID"
if [[ "$ACTION" == "task" ]]; then
  [[ $# -eq 6 && "$TASK0_GATE_EXECUTION" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
    die "task requires one exact successful task0 execution name"
else
  [[ $# -le 5 ]] || die "$ACTION accepts no task0 gate argument"
fi

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || die "repository root unavailable"
[[ "$(git -C "$ROOT" rev-parse HEAD)" == "$CODE_SHA" ]] || \
  die "CODE_SHA must equal HEAD"
git -C "$ROOT" cat-file -e "${CODE_SHA}^{commit}" || die "CODE_SHA commit unavailable"
[[ "$(git -C "$ROOT" rev-parse --verify 'refs/remotes/origin/main^{commit}')" == "$CODE_SHA" ]] || \
  die "CODE_SHA must equal durable origin/main"

release_paths=(
  Dockerfile.corpus-r6-broad-admission
  Dockerfile.corpus-r6-broad-admission.dockerignore
  cloudbuild.corpus-r6-broad-admission.yaml
  pyproject.toml
  README.md
  scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh
  scripts/run_corpus_r6_broad_admission_tournament_v1.py
  scripts/run_corpus_r6_combined_frontier_reportfolio_v1.py
  scripts/run_corpus_r6_combined_population_all_block_v1.py
  scripts/run_corpus_r6_hard230_selector_bridge_v1.py
  scripts/run_corpus_r6_construction_allocation_grade_v1.py
  src/nfl_dfs/research/corpus_r6_construction_allocation_cross_operator_v1.py
  src/nfl_dfs/research/corpus_r6_broad_admission_tournament_v1.py
  src/nfl_dfs/research/corpus_r6_broad_admission_program_v1.py
)
require_committed_release_paths_clean "$ROOT" "$CODE_SHA" "${release_paths[@]}"

image_digest=${IMAGE##*@}
image_tag="${IMAGE%@*}:broad-admission-${CODE_SHA}"
mkdir -p "$ROOT/.build-contexts"
temp_dir=$(mktemp -d "$ROOT/.build-contexts/broad-admission-launch.XXXXXX")
cleanup_host() { rm -rf "$temp_dir"; }
trap cleanup_host EXIT
build_json=$temp_dir/build.json
job_before=$temp_dir/job-before.json
job_after=$temp_dir/job-after.json
execution_json=$temp_dir/execution.json
launch_json=$temp_dir/launch.json

gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format=json >"$build_json"
jq -e --arg build "$BUILD_ID" --arg sha "$CODE_SHA" --arg tag "$image_tag" \
  --arg digest "$image_digest" --arg repository "$SOURCE_REPOSITORY" '
  .id == $build and .status == "SUCCESS" and
  .source.gitSource == {url:$repository,revision:$sha} and
  .sourceProvenance.resolvedGitSource == {url:$repository,revision:$sha} and
  .substitutions._CODE_SHA == $sha and .substitutions._BUILD_IMAGE == $tag and
  ([.results.images[]? | select(.name == $tag and .digest == $digest)] | length) == 1
' "$build_json" >/dev/null || die "Cloud Build authority differs"

# Exact-name inspection proves the shared job exists.  Requiring its latest
# execution to be terminal prevents this release from disrupting another
# cohort that currently owns the slot.
gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format=json >"$job_before"
jq -e --arg uid "$EXPECTED_JOB_UID" '
  .metadata.uid == $uid and
  any(.status.conditions[]?; .type == "Ready" and .status == "True")
' "$job_before" >/dev/null || die "reused job identity/readiness differs"
prior_execution=null
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
  ' "$execution_json" >/dev/null || die "reused job latest execution is not terminal-success"
fi

verify_installed_job() {
  [[ $# -eq 1 ]] || die "job verification requires one observation"
  jq -e --arg uid "$EXPECTED_JOB_UID" --arg image "$IMAGE" \
    --arg sha "$CODE_SHA" --arg digest "$image_digest" \
    --arg build "$BUILD_ID" --arg sa "$SERVICE_ACCOUNT" \
    --argjson tasks "$TASK_COUNT" --argjson parallelism "$PARALLELISM" '
    .metadata.uid == $uid and
    .spec.template.spec.taskCount == $tasks and
    .spec.template.spec.parallelism == $parallelism and
    .spec.template.spec.template.spec.maxRetries == 0 and
    (.spec.template.spec.template.spec.timeoutSeconds == "21600" or
     .spec.template.spec.template.spec.timeout == "21600s") and
    .spec.template.spec.template.spec.serviceAccountName == $sa and
    (.spec.template.spec.template.spec.containers | length) == 1 and
    (.spec.template.spec.template.spec.containers[0] as $c |
      $c.image == $image and $c.command == ["/bin/bash"] and
      $c.args == ["/app/scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh", "container-help"] and
      $c.resources.limits.cpu == "8" and $c.resources.limits.memory == "32Gi" and
      ([ $c.env[] | select(.name == "CODE_SHA") | .value ] == [$sha]) and
      ([ $c.env[] | select(.name == "IMAGE_DIGEST") | .value ] == [$digest]) and
      ([ $c.env[] | select(.name == "BUILD_ID") | .value ] == [$build]) and
      ([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_ENABLE") | .value ] == ["DISABLED_INSTALL_ONLY"]) and
      ([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_OUTCOMES_ALLOWED") | .value ] == ["false"]) and
      ([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_TASK0_SMOKE") | .value ] == ["false"])
    )
  ' "$1" >/dev/null || die "installed reused-job template differs"
}

if [[ "$ACTION" == "install" ]]; then
  [[ -z "$REQUEST_PATH" ]] || die "install accepts no request"
  gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
    --image "$IMAGE" --command /bin/bash \
    --args /app/scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh,container-help \
    --tasks "$TASK_COUNT" --parallelism "$PARALLELISM" --max-retries 0 \
    --cpu "$CPU" --memory "$MEMORY" --task-timeout "$TASK_TIMEOUT" \
    --service-account "$SERVICE_ACCOUNT" \
    --set-env-vars "CODE_SHA=$CODE_SHA,IMAGE_DIGEST=$image_digest,BUILD_ID=$BUILD_ID,$ENABLE_ENV=DISABLED_INSTALL_ONLY,$OUTCOMES_ENV=false,$TASK0_ENV=false" \
    --quiet >/dev/null
  gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
    --format=json >"$job_after"
  verify_installed_job "$job_after"
  prior_generation=$(jq -er '.metadata.generation' "$job_before")
  installed_generation=$(jq -er '.metadata.generation' "$job_after")
  [[ "$prior_generation" =~ ^[0-9]+$ && "$installed_generation" =~ ^[0-9]+$ && \
      "$installed_generation" -gt "$prior_generation" ]] || \
    die "reused job generation did not advance through installation"
  jq -n --arg schema "corpus-r6-broad-admission-cloud-install/v1" \
    --arg code_sha "$CODE_SHA" --arg build_id "$BUILD_ID" --arg image "$IMAGE" \
    --arg digest "$image_digest" --arg job "$JOB" --arg uid "$EXPECTED_JOB_UID" \
    --argjson generation "$installed_generation" --arg prior "$prior_execution" '{
      schema_version:$schema, code_sha:$code_sha, cloud_build_id:$build_id,
      provider_resolved_image:$image, image_digest:$digest,
      reused_job:{name:$job,uid:$uid,generation:$generation},
      prior_terminal_execution:$prior, install_only:true,
      execution_launched:false, outcomes_allowed:false, complete:true
    }'
  exit 0
fi

if [[ "$ACTION" == "result" ]]; then
  result_execution=$REQUEST_PATH
  [[ "$result_execution" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
    die "result requires one exact broad-admission execution name"
  gcloud run jobs executions describe "$result_execution" \
    --project "$PROJECT" --region "$REGION" --format=json >"$execution_json"
  result_phase=$(jq -er '
    .spec.template.spec.containers[0].args as $args |
    if ($args | length) == 3 and
       $args[0] == "/app/scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh" and
       $args[1] == "container-run" and
       ($args[2] | IN("prepare","task0","collect","reopen","grade","grade-reopen"))
    then $args[2] else error("result execution phase differs") end
  ' "$execution_json") || die "result execution command differs"
  [[ "$result_phase" == "grade" ]] && result_outcomes=true || result_outcomes=false
  if [[ "$result_phase" == "grade" || "$result_phase" == "grade-reopen" ]]; then
    result_uses_realized=true
  else
    result_uses_realized=false
  fi
  [[ "$result_phase" == "task0" ]] && result_task0=true || result_task0=false
  jq -e --arg execution "$result_execution" --arg job "$JOB" \
    --arg uid "$EXPECTED_JOB_UID" --arg image "$IMAGE" --arg sha "$CODE_SHA" \
    --arg digest "$image_digest" --arg build "$BUILD_ID" \
    --arg enable "$ENABLE_VALUE" --arg outcomes "$result_outcomes" \
    --arg smoke "$result_task0" --arg sa "$SERVICE_ACCOUNT" '
    .metadata.name == $execution and
    .metadata.labels["run.googleapis.com/job"] == $job and
    .metadata.labels["run.googleapis.com/jobUid"] == $uid and
    (.metadata.labels["run.googleapis.com/jobGeneration"] | test("^[0-9]+$")) and
    any(.status.conditions[]?; .type == "Completed" and .status == "True") and
    (.status.completionTime | type == "string" and length > 0) and
    (.status.succeededCount // 0) == 1 and
    (.status.failedCount // 0) == 0 and (.status.cancelledCount // 0) == 0 and
    (.status.runningCount // 0) == 0 and
    .spec.taskCount == 1 and (.spec.parallelism == 1 or .spec.parallelism == 54) and
    .spec.template.spec.maxRetries == 0 and
    (.spec.template.spec.timeout == "21600s" or
     .spec.template.spec.timeout == "21600.000000000s") and
    .spec.template.spec.serviceAccountName == $sa and
    (.spec.template.spec.containers | length) == 1 and
    (.spec.template.spec.containers[0] as $c |
      $c.image == $image and $c.command == ["/bin/bash"] and
      $c.resources.limits.cpu == "8" and $c.resources.limits.memory == "32Gi" and
      ([ $c.env[] | select(.name == "CODE_SHA") | .value ] == [$sha]) and
      ([ $c.env[] | select(.name == "IMAGE_DIGEST") | .value ] == [$digest]) and
      ([ $c.env[] | select(.name == "BUILD_ID") | .value ] == [$build]) and
      ([ $c.env[] | select(.name == "IMAGE_URI") | .value ] == [$image]) and
      ([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_ENABLE") | .value ] == [$enable]) and
      ([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_OUTCOMES_ALLOWED") | .value ] == [$outcomes]) and
      ([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_TASK0_SMOKE") | .value ] == [$smoke]) and
      (([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_BOUND_IDENTITY") | .value ]) as $bound |
        ($bound | length) == 1 and ($bound[0] | fromjson? | type == "object")) and
      (([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_REQUEST_SHA256") | .value ]) as $hash |
        ($hash | length) == 1 and ($hash[0] | test("^[0-9a-f]{64}$"))) and
      (([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_REQUEST_B64") | .value ]) as $body |
        ($body | length) == 1 and ($body[0] | type == "string" and length > 0))
    )
  ' "$execution_json" >/dev/null || die "terminal result execution differs"

  result_request_b64=$(jq -er '
    [.spec.template.spec.containers[0].env[] |
     select(.name == "R6_BROAD_ADMISSION_REQUEST_B64") | .value] |
    if length == 1 then .[0] else error("result request b64 differs") end
  ' "$execution_json")
  result_request_sha=$(jq -er '
    [.spec.template.spec.containers[0].env[] |
     select(.name == "R6_BROAD_ADMISSION_REQUEST_SHA256") | .value] |
    if length == 1 then .[0] else error("result request hash differs") end
  ' "$execution_json")
  [[ "${#result_request_b64}" -le 1400000 ]] || die "result request exceeds byte ceiling"
  result_request=$temp_dir/result-request.json
  printf '%s' "$result_request_b64" | base64 --decode >"$result_request" || \
    die "result request base64 differs"
  [[ "$(sha256sum "$result_request" | awk '{print $1}')" == "$result_request_sha" ]] || \
    die "result request bytes differ"
  result_bound=$(jq -er '
    [.spec.template.spec.containers[0].env[] |
     select(.name == "R6_BROAD_ADMISSION_BOUND_IDENTITY") | .value] |
    if length == 1 then .[0] else error("result bound identity differs") end
  ' "$execution_json")
  result_bound_canonical=$(printf '%s' "$result_bound" | jq -cS .) || \
    die "result bound identity is not JSON"
  [[ "$result_bound" == "$result_bound_canonical" ]] || \
    die "result bound identity is not canonical"
  case "$result_phase" in
    prepare)
      jq -e --arg sha "$CODE_SHA" --arg image "$IMAGE" '
        (keys | sort) == (["code_sha","combined_terminal_identity","frontier_manifest_identity","immutable_image","output_prefix","runtime_build_attestation_identity"] | sort) and
        .code_sha == $sha and .immutable_image == $image
      ' "$result_request" >/dev/null || die "result prepare request differs"
      [[ "$result_bound" == "$(jq -cS '.combined_terminal_identity' "$result_request")" ]] || \
        die "result prepare bound identity differs"
      ;;
    task0)
      jq -e '(keys == ["manifest_identity"])' "$result_request" >/dev/null || \
        die "result task0 request differs"
      [[ "$result_bound" == "$(jq -cS '.manifest_identity' "$result_request")" ]] || \
        die "result task0 bound identity differs"
      ;;
    collect)
      jq -e '
        (keys | sort) == (["execution_id","manifest_identity"] | sort) and
        (.execution_id | type == "string")
      ' "$result_request" >/dev/null || die "result collect request differs"
      [[ "$result_bound" == "$(jq -cS '.manifest_identity' "$result_request")" ]] || \
        die "result collect bound identity differs"
      ;;
    reopen)
      jq -e '(keys == ["terminal_identity"])' "$result_request" >/dev/null || \
        die "result reopen request differs"
      [[ "$result_bound" == "$(jq -cS '.terminal_identity' "$result_request")" ]] || \
        die "result reopen bound identity differs"
      ;;
    grade)
      jq -e '
        (keys | sort) == (["outcome_authority_identity","terminal_identity"] | sort)
      ' "$result_request" >/dev/null || die "result grade request differs"
      [[ "$result_bound" == "$(jq -cS '.terminal_identity' "$result_request")" ]] || \
        die "result grade bound identity differs"
      ;;
    grade-reopen)
      jq -e '(keys == ["grade_terminal_identity"])' "$result_request" >/dev/null || \
        die "result grade-reopen request differs"
      [[ "$result_bound" == "$(jq -cS '.grade_terminal_identity' "$result_request")" ]] || \
        die "result grade-reopen bound identity differs"
      ;;
  esac

  result_logs=$temp_dir/result-stdout.json
  log_filter="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$result_execution\" AND logName=\"projects/$PROJECT/logs/run.googleapis.com%2Fstdout\" AND (textPayload:* OR jsonPayload:*)"
  gcloud logging read "$log_filter" --project "$PROJECT" --limit 100 \
    --order=asc --format=json >"$result_logs"
  result_receipt=$temp_dir/operator-receipt.json
  jq -e 'type == "array" and length == 1' "$result_logs" >/dev/null || \
    die "operator stdout receipt count differs"
  result_payload_kind=$(jq -er '
    .[0] as $row |
    ($row | has("textPayload")) as $has_text |
    ($row | has("jsonPayload")) as $has_json |
    if ($has_text and ($has_json | not) and ($row.textPayload | type == "string"))
    then "text"
    elif ($has_json and ($has_text | not) and ($row.jsonPayload | type == "object"))
    then "json"
    else error("operator stdout receipt payload kind differs")
    end
  ' "$result_logs") || die "operator stdout receipt payload kind differs"
  if [[ "$result_payload_kind" == "text" ]]; then
    result_raw=$(jq -er '.[0].textPayload' "$result_logs") || \
      die "operator stdout text receipt differs"
    result_canonical=$(printf '%s' "$result_raw" | jq -ecS '
      select(type == "object" and
        .schema_version == "corpus-r6-broad-admission-cli-receipt/v1")
    ') || die "operator stdout receipt is not JSON"
    [[ "$result_raw" == "$result_canonical" ]] || \
      die "operator stdout receipt is not canonical JSON"
    printf '%s' "$result_raw" >"$result_receipt"
  else
    result_structured=$temp_dir/operator-receipt-structured.json
    jq -e '.[0].jsonPayload' "$result_logs" >"$result_structured" || \
      die "operator structured stdout receipt differs"
    host_python=$ROOT/.venv/bin/python
    [[ -x "$host_python" ]] || die "exact release virtualenv Python is absent"
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT:$ROOT/src:$ROOT/scripts" \
      "$host_python" - "$result_structured" "$result_receipt" <<'PY_CANONICALIZE' || \
      die "operator structured stdout canonicalization differs"
from __future__ import annotations

import json
from pathlib import Path
import sys

from scripts import run_corpus_r6_broad_admission_tournament_v1 as experiment


source_path, output_path = sys.argv[1:]
value = json.loads(Path(source_path).read_bytes())
Path(output_path).write_bytes(experiment._canonical(value))
PY_CANONICALIZE
    jq -e '
      type == "object" and
      .schema_version == "corpus-r6-broad-admission-cli-receipt/v1"
    ' "$result_receipt" >/dev/null || die "operator structured stdout receipt differs"
  fi

  expected_command=$result_phase
  [[ "$result_phase" == "task0" ]] && expected_command=task
  jq -e --arg command "$expected_command" --argjson smoke "$result_task0" \
    --argjson outcomes "$result_uses_realized" '
    (keys | sort) == (["command","complete","result","schema_version","task0_nonpublishing_smoke","uses_realized_outcomes"] | sort) and
    .schema_version == "corpus-r6-broad-admission-cli-receipt/v1" and
    .command == $command and .task0_nonpublishing_smoke == $smoke and
    .uses_realized_outcomes == $outcomes and .complete == true and
    (.result | type == "object")
  ' "$result_receipt" >/dev/null || die "operator stdout envelope differs"
  case "$result_phase" in
    prepare)
      jq -e --arg build "$BUILD_ID" '
        (.result | keys | sort) == (["all_nonpublication_authorities_validated_before_first_write","build_id","complete","deployment_mutation_performed","execution_launched","manifest_identity","manifest_sha256","prepare_result_sha256","schema_version","task_count","uses_realized_outcomes"] | sort) and
        .result.schema_version == "corpus-r6-broad-admission-prepare-result/v1" and
        .result.task_count == 54 and .result.build_id == $build and
        .result.all_nonpublication_authorities_validated_before_first_write == true and
        .result.execution_launched == false and .result.deployment_mutation_performed == false and
        .result.uses_realized_outcomes == false and .result.complete == true and
        (.result.manifest_identity | type == "object") and
        (.result.manifest_sha256 | test("^[0-9a-f]{64}$")) and
        (.result.prepare_result_sha256 | test("^[0-9a-f]{64}$"))
      ' "$result_receipt" >/dev/null || die "prepare stdout result differs"
      ;;
    task0)
      jq -e '
        (.result | keys | sort) == (["complete","manifest_identity","package_sha256","publication_performed","schema_version","slate_id","smoke_result_sha256","source_ordinal","task_result_sha256","union_lineups_sha256","uses_realized_outcomes"] | sort) and
        .result.schema_version == "corpus-r6-broad-admission-task0-smoke/v1" and
        .result.source_ordinal == 0 and .result.publication_performed == false and
        .result.uses_realized_outcomes == false and .result.complete == true and
        ([.result.package_sha256,.result.union_lineups_sha256,.result.task_result_sha256,.result.smoke_result_sha256] |
          all(test("^[0-9a-f]{64}$")))
      ' "$result_receipt" >/dev/null || die "task0 stdout result differs"
      ;;
    collect)
      jq -e '
        (.result | keys | sort) == (["collect_result_sha256","complete","root_published_last","schema_version","task_count","terminal_identity","terminal_sha256","uses_realized_outcomes"] | sort) and
        .result.schema_version == "corpus-r6-broad-admission-collect-result/v1" and
        .result.task_count == 54 and .result.root_published_last == true and
        .result.uses_realized_outcomes == false and .result.complete == true and
        (.result.terminal_identity | type == "object") and
        ([.result.terminal_sha256,.result.collect_result_sha256] | all(test("^[0-9a-f]{64}$")))
      ' "$result_receipt" >/dev/null || die "collect stdout result differs"
      ;;
    reopen)
      jq -e '
        (.result | keys | sort) == (["all_packages_independently_recomputed","all_tasks_and_parents_generation_exact_reopened","catalog_reread","complete","outcome_reread","package_lattice_sha256","reopen_result_sha256","schema_version","task_count","terminal_identity","uses_realized_outcomes"] | sort) and
        .result.schema_version == "corpus-r6-broad-admission-reopen-result/v1" and
        .result.task_count == 54 and
        .result.all_tasks_and_parents_generation_exact_reopened == true and
        .result.all_packages_independently_recomputed == true and
        .result.catalog_reread == false and .result.outcome_reread == false and
        .result.uses_realized_outcomes == false and .result.complete == true and
        ([.result.package_lattice_sha256,.result.reopen_result_sha256] | all(test("^[0-9a-f]{64}$")))
      ' "$result_receipt" >/dev/null || die "reopen stdout result differs"
      ;;
    grade)
      jq -e '
        (.result | keys | sort) == (["complete","descriptive_only","grade_result_sha256","grade_root_published_last","grade_terminal_identity","grade_terminal_sha256","program_grade_sha256","schema_version"] | sort) and
        .result.schema_version == "corpus-r6-broad-admission-grade-result/v1" and
        .result.grade_root_published_last == true and .result.descriptive_only == true and
        .result.complete == true and (.result.grade_terminal_identity | type == "object") and
        ([.result.grade_terminal_sha256,.result.program_grade_sha256,.result.grade_result_sha256] |
          all(test("^[0-9a-f]{64}$")))
      ' "$result_receipt" >/dev/null || die "grade stdout result differs"
      ;;
    grade-reopen)
      jq -e '
        (.result | keys | sort) == (["catalog_reread","complete","grade_reopen_result_sha256","grade_terminal_identity","historical_outcome_lease_reread","outcome_snapshot_reread","persisted_derived_scores_replayed","program_grade_independently_recomputed","program_grade_sha256","schema_version","score_free_lattice_and_parents_replayed","uses_realized_outcomes"] | sort) and
        .result.schema_version == "corpus-r6-broad-admission-grade-reopen-result/v1" and
        .result.score_free_lattice_and_parents_replayed == true and
        .result.persisted_derived_scores_replayed == true and
        .result.program_grade_independently_recomputed == true and
        .result.catalog_reread == false and .result.outcome_snapshot_reread == false and
        .result.historical_outcome_lease_reread == false and
        .result.uses_realized_outcomes == true and .result.complete == true and
        ([.result.program_grade_sha256,.result.grade_reopen_result_sha256] |
          all(test("^[0-9a-f]{64}$")))
      ' "$result_receipt" >/dev/null || die "grade-reopen stdout result differs"
      ;;
  esac

  jq -n --arg schema "corpus-r6-broad-admission-cloud-result/v1" \
    --arg phase "$result_phase" --arg code_sha "$CODE_SHA" --arg build_id "$BUILD_ID" \
    --arg image "$IMAGE" --arg execution "$result_execution" \
    --arg execution_uid "$(jq -er '.metadata.uid' "$execution_json")" \
    --arg completion_time "$(jq -er '.status.completionTime' "$execution_json")" \
    --argjson operator_receipt "$(jq -cS . "$result_receipt")" '{
      schema_version:$schema, phase:$phase, code_sha:$code_sha,
      cloud_build_id:$build_id, provider_resolved_image:$image,
      execution:{name:$execution,uid:$execution_uid,task_count:1,
        succeeded_count:1,failed_count:0,cancelled_count:0,
        completion_time:$completion_time},
      operator_receipt:$operator_receipt,
      exact_execution_stdout_only:true, complete:true
    }'
  exit 0
fi

[[ -n "$REQUEST_PATH" && "$REQUEST_PATH" == /* && -f "$REQUEST_PATH" && \
   ! -L "$REQUEST_PATH" ]] || die "$ACTION requires one absolute unaliased request file"
gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format=json >"$job_after"
verify_installed_job "$job_after"

outcomes_allowed=false
task0_smoke=false
source_task_execution=null
task0_gate_result=null
effective_request=$REQUEST_PATH
case "$ACTION" in
  prepare)
    jq -e --arg sha "$CODE_SHA" --arg image "$IMAGE" '
      (keys | sort) == (["code_sha","combined_terminal_identity","frontier_manifest_identity","immutable_image","output_prefix","runtime_build_attestation_identity"] | sort) and
      .code_sha == $sha and .immutable_image == $image and
      (.combined_terminal_identity | type == "object") and
      (.frontier_manifest_identity | type == "object") and
      (.runtime_build_attestation_identity | type == "object") and
      (.output_prefix | type == "string" and startswith("gs://") and endswith("/"))
    ' "$REQUEST_PATH" >/dev/null || die "prepare request differs"
    bound_identity=$(jq -cS '.combined_terminal_identity' "$REQUEST_PATH")
    command_phase=prepare
    tasks=1
    ;;
  task0|task)
    jq -e '(keys == ["manifest_identity"]) and (.manifest_identity | type == "object")' \
      "$REQUEST_PATH" >/dev/null || die "$ACTION request differs"
    bound_identity=$(jq -cS '.manifest_identity' "$REQUEST_PATH")
    command_phase=$ACTION
    if [[ "$ACTION" == "task" ]]; then
      tasks=$TASK_COUNT
      task0_gate_output=$temp_dir/task0-gate-result.json
      "$ROOT/scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh" \
        result "$IMAGE" "$CODE_SHA" "$BUILD_ID" "$TASK0_GATE_EXECUTION" \
        >"$task0_gate_output"
      jq -e --arg image "$IMAGE" --arg sha "$CODE_SHA" --arg build "$BUILD_ID" \
        --arg execution "$TASK0_GATE_EXECUTION" --argjson manifest "$bound_identity" '
        .schema_version == "corpus-r6-broad-admission-cloud-result/v1" and
        .phase == "task0" and .code_sha == $sha and
        .cloud_build_id == $build and .provider_resolved_image == $image and
        .execution.name == $execution and .execution.task_count == 1 and
        .execution.succeeded_count == 1 and .execution.failed_count == 0 and
        .execution.cancelled_count == 0 and
        .operator_receipt.command == "task" and
        .operator_receipt.task0_nonpublishing_smoke == true and
        .operator_receipt.uses_realized_outcomes == false and
        .operator_receipt.complete == true and
        .operator_receipt.result.schema_version == "corpus-r6-broad-admission-task0-smoke/v1" and
        .operator_receipt.result.manifest_identity == $manifest and
        .operator_receipt.result.source_ordinal == 0 and
        .operator_receipt.result.publication_performed == false and
        .operator_receipt.result.uses_realized_outcomes == false and
        .operator_receipt.result.complete == true and .complete == true
      ' "$task0_gate_output" >/dev/null || \
        die "task0 launch gate differs from the requested task manifest"
      task0_gate_result=$(jq -cS . "$task0_gate_output")
    else
      tasks=1
      task0_smoke=true
    fi
    ;;
  collect)
    jq -e '(keys == ["manifest_identity"]) and (.manifest_identity | type == "object")' \
      "$REQUEST_PATH" >/dev/null || die "collect request differs"
    bound_identity=$(jq -cS '.manifest_identity' "$REQUEST_PATH")
    task_execution_name=${R6_BROAD_ADMISSION_TASK_EXECUTION_NAME:-}
    [[ "$task_execution_name" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
      die "collect requires exact R6_BROAD_ADMISSION_TASK_EXECUTION_NAME"
    task_execution_json=$temp_dir/task-execution.json
    gcloud run jobs executions describe "$task_execution_name" \
      --project "$PROJECT" --region "$REGION" --format=json >"$task_execution_json"
    job_generation=$(jq -er '.metadata.generation' "$job_after")
    jq -e --arg name "$task_execution_name" --arg job "$JOB" \
      --arg uid "$EXPECTED_JOB_UID" --arg generation "$job_generation" \
      --arg image "$IMAGE" --arg sha "$CODE_SHA" --arg digest "$image_digest" \
      --arg build "$BUILD_ID" --arg enable "$ENABLE_VALUE" \
      --arg bound "$bound_identity" --arg sa "$SERVICE_ACCOUNT" \
      --argjson tasks "$TASK_COUNT" --argjson parallelism "$PARALLELISM" '
      .metadata.name == $name and
      .metadata.labels["run.googleapis.com/job"] == $job and
      .metadata.labels["run.googleapis.com/jobUid"] == $uid and
      .metadata.labels["run.googleapis.com/jobGeneration"] == $generation and
      any(.status.conditions[]?; .type == "Completed" and .status == "True") and
      (.status.completionTime | type == "string" and length > 0) and
      (.status.succeededCount // 0) == $tasks and
      (.status.failedCount // 0) == 0 and (.status.cancelledCount // 0) == 0 and
      (.status.runningCount // 0) == 0 and
      .spec.taskCount == $tasks and .spec.parallelism == $parallelism and
      .spec.template.spec.maxRetries == 0 and
      .spec.template.spec.serviceAccountName == $sa and
      (.spec.template.spec.containers | length) == 1 and
      (.spec.template.spec.containers[0] as $c |
        $c.image == $image and $c.command == ["/bin/bash"] and
        $c.args == ["/app/scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh","container-run","task"] and
        $c.resources.limits.cpu == "8" and $c.resources.limits.memory == "32Gi" and
        ([ $c.env[] | select(.name == "CODE_SHA") | .value ] == [$sha]) and
        ([ $c.env[] | select(.name == "IMAGE_DIGEST") | .value ] == [$digest]) and
        ([ $c.env[] | select(.name == "BUILD_ID") | .value ] == [$build]) and
        ([ $c.env[] | select(.name == "IMAGE_URI") | .value ] == [$image]) and
        ([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_ENABLE") | .value ] == [$enable]) and
        ([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_BOUND_IDENTITY") | .value ] == [$bound]) and
        (([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_REQUEST_SHA256") | .value ]) as $hash |
          ($hash | length) == 1 and ($hash[0] | test("^[0-9a-f]{64}$"))) and
        (([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_REQUEST_B64") | .value ]) as $body |
          ($body | length) == 1 and ($body[0] | type == "string" and length > 0)) and
        ([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_OUTCOMES_ALLOWED") | .value ] == ["false"]) and
        ([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_TASK0_SMOKE") | .value ] == ["false"])
      )
    ' "$task_execution_json" >/dev/null || die "named task execution differs"
    task_request_b64=$(jq -er '
      [.spec.template.spec.containers[0].env[] |
       select(.name == "R6_BROAD_ADMISSION_REQUEST_B64") | .value] |
      if length == 1 then .[0] else error("task request b64 differs") end
    ' "$task_execution_json")
    task_request_sha=$(jq -er '
      [.spec.template.spec.containers[0].env[] |
       select(.name == "R6_BROAD_ADMISSION_REQUEST_SHA256") | .value] |
      if length == 1 then .[0] else error("task request hash differs") end
    ' "$task_execution_json")
    [[ "${#task_request_b64}" -le 1400000 ]] || die "task request exceeds byte ceiling"
    task_request_path=$temp_dir/source-task-request.json
    printf '%s' "$task_request_b64" | base64 --decode >"$task_request_path" || \
      die "source task request base64 differs"
    [[ "$(sha256sum "$task_request_path" | awk '{print $1}')" == "$task_request_sha" ]] || \
      die "source task request bytes differ"
    jq -e --argjson manifest "$bound_identity" '
      (keys == ["manifest_identity"]) and .manifest_identity == $manifest
    ' "$task_request_path" >/dev/null || die "source task request manifest differs"
    source_task_execution=$(jq -cnS --arg name "$task_execution_name" \
      --arg uid "$(jq -er '.metadata.uid' "$task_execution_json")" \
      --argjson count "$TASK_COUNT" '{name:$name,uid:$uid,task_count:$count}')
    effective_request=$temp_dir/collect-request.json
    jq -cnS --argjson manifest "$bound_identity" --arg execution "$task_execution_name" \
      '{manifest_identity:$manifest,execution_id:$execution}' >"$effective_request"
    command_phase=collect
    tasks=1
    ;;
  reopen)
    jq -e '(keys == ["terminal_identity"]) and (.terminal_identity | type == "object")' \
      "$REQUEST_PATH" >/dev/null || die "reopen request differs"
    bound_identity=$(jq -cS '.terminal_identity' "$REQUEST_PATH")
    command_phase=reopen
    tasks=1
    ;;
  grade)
    jq -e '
      (keys | sort) == (["outcome_authority_identity","terminal_identity"] | sort) and
      (.terminal_identity | type == "object") and
      (.outcome_authority_identity | type == "object")
    ' "$REQUEST_PATH" >/dev/null || die "grade request differs"
    bound_identity=$(jq -cS '.terminal_identity' "$REQUEST_PATH")
    command_phase=grade
    tasks=1
    outcomes_allowed=true
    ;;
  grade-reopen)
    jq -e '(keys == ["grade_terminal_identity"]) and (.grade_terminal_identity | type == "object")' \
      "$REQUEST_PATH" >/dev/null || die "grade-reopen request differs"
    bound_identity=$(jq -cS '.grade_terminal_identity' "$REQUEST_PATH")
    command_phase=grade-reopen
    tasks=1
    ;;
esac

request_sha=$(sha256sum "$effective_request" | awk '{print $1}')
request_b64=$(base64 -w0 "$effective_request")
execution_args="/app/scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh,container-run,$command_phase"
env_override="^|^CODE_SHA=$CODE_SHA|IMAGE_DIGEST=$image_digest|BUILD_ID=$BUILD_ID|IMAGE_URI=$IMAGE|$ENABLE_ENV=$ENABLE_VALUE|$REQUEST_SHA_ENV=$request_sha|$REQUEST_B64_ENV=$request_b64|$BOUND_IDENTITY_ENV=$bound_identity|$OUTCOMES_ENV=$outcomes_allowed|$TASK0_ENV=$task0_smoke"

gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --tasks "$tasks" --args "$execution_args" --update-env-vars "$env_override" \
  --async --format=json >"$launch_json"
execution_name=$(jq -er '.metadata.name' "$launch_json") || \
  die "launch lacks one execution name"
[[ "$execution_name" == "$JOB-"* ]] || die "execution is not bound to reused job"
gcloud run jobs executions describe "$execution_name" --project "$PROJECT" \
  --region "$REGION" --format=json >"$execution_json"

job_generation=$(jq -er '.metadata.generation' "$job_after")
jq -e --arg execution "$execution_name" --arg job "$JOB" \
  --arg uid "$EXPECTED_JOB_UID" --arg generation "$job_generation" \
  --arg image "$IMAGE" --arg sha "$CODE_SHA" --arg digest "$image_digest" \
  --arg build "$BUILD_ID" --arg enable "$ENABLE_VALUE" \
  --arg bound "$bound_identity" --arg request_sha "$request_sha" \
  --arg args_csv "$execution_args" --arg outcomes "$outcomes_allowed" \
  --arg smoke "$task0_smoke" --arg sa "$SERVICE_ACCOUNT" --argjson tasks "$tasks" '
  .metadata.name == $execution and
  .metadata.labels["run.googleapis.com/job"] == $job and
  .metadata.labels["run.googleapis.com/jobUid"] == $uid and
  .metadata.labels["run.googleapis.com/jobGeneration"] == $generation and
  .spec.taskCount == $tasks and .spec.template.spec.maxRetries == 0 and
  .spec.template.spec.serviceAccountName == $sa and
  (.spec.template.spec.containers | length) == 1 and
  (.spec.template.spec.containers[0] as $c |
    $c.image == $image and $c.command == ["/bin/bash"] and
    $c.args == ($args_csv | split(",")) and
    $c.resources.limits.cpu == "8" and $c.resources.limits.memory == "32Gi" and
    ([ $c.env[] | select(.name == "CODE_SHA") | .value ] == [$sha]) and
    ([ $c.env[] | select(.name == "IMAGE_DIGEST") | .value ] == [$digest]) and
    ([ $c.env[] | select(.name == "BUILD_ID") | .value ] == [$build]) and
    ([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_ENABLE") | .value ] == [$enable]) and
    ([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_BOUND_IDENTITY") | .value ] == [$bound]) and
    ([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_REQUEST_SHA256") | .value ] == [$request_sha]) and
    ([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_OUTCOMES_ALLOWED") | .value ] == [$outcomes]) and
    ([ $c.env[] | select(.name == "R6_BROAD_ADMISSION_TASK0_SMOKE") | .value ] == [$smoke])
  )
' "$execution_json" >/dev/null || die "launched execution provider authority differs"

execution_uid=$(jq -er '.metadata.uid' "$execution_json") || die "execution UID absent"
jq -n --arg schema "corpus-r6-broad-admission-cloud-launch/v1" \
  --arg phase "$ACTION" --arg code_sha "$CODE_SHA" --arg build_id "$BUILD_ID" \
  --arg image "$IMAGE" --arg digest "$image_digest" --arg job "$JOB" \
  --arg job_uid "$EXPECTED_JOB_UID" --argjson generation "$job_generation" \
  --arg execution "$execution_name" --arg execution_uid "$execution_uid" \
  --argjson task_count "$tasks" --argjson bound "$bound_identity" \
  --argjson source_task_execution "$source_task_execution" \
  --argjson task0_gate_result "$task0_gate_result" \
  --arg request_sha "$request_sha" --argjson outcomes "$outcomes_allowed" \
  --argjson task0 "$task0_smoke" '{
    schema_version:$schema, phase:$phase, code_sha:$code_sha,
    cloud_build_id:$build_id, provider_resolved_image:$image,
    image_digest:$digest,
    reused_job:{name:$job,uid:$job_uid,generation:$generation},
    execution:{name:$execution,uid:$execution_uid,task_count:$task_count},
    bound_input_authority_identity:$bound,
    source_task_execution:$source_task_execution,
    task0_gate_result:$task0_gate_result,
    request_sha256:$request_sha,
    outcomes_allowed:$outcomes, task0_nonpublishing_smoke:$task0,
    execution_provider_reopened:true, complete:true
  }'
