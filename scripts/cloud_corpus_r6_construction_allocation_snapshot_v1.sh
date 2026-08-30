#!/usr/bin/env bash
# Install, then explicitly launch, the immutable construction x allocation
# snapshot-shard cohort on one pre-existing Cloud Run job.  The installed
# template is deliberately disabled; each phase is an execution-level
# args/env override.  This file never creates, deletes, or enumerates jobs.
set -euo pipefail

die() { printf '%s\n' "ERROR: $*" >&2; exit 2; }

RUNNER=/app/scripts/run_corpus_r6_construction_allocation_snapshot_shard_v1.py
GRADE_RUNNER=/app/scripts/run_corpus_r6_construction_allocation_grade_v1.py
ENABLE_ENV=R6_CONSTRUCTION_ALLOCATION_SNAPSHOT_SHARD_ENABLE
ENABLE_VALUE=I_UNDERSTAND_SCORE_BLIND_CONSTRUCTION_CROSS_V1
MANIFEST_ENV=R6_CONSTRUCTION_ALLOCATION_SNAPSHOT_SHARD_MANIFEST_IDENTITY
REQUEST_B64_ENV=R6_CONSTRUCTION_ALLOCATION_CLOUD_REQUEST_B64
REQUEST_SHA_ENV=R6_CONSTRUCTION_ALLOCATION_CLOUD_REQUEST_SHA256
TASK_EXECUTION_ENV=R6_CONSTRUCTION_ALLOCATION_TASK_EXECUTION_NAME
GRADE_ENABLE_ENV=R6_CONSTRUCTION_ALLOCATION_GRADE_ENABLED
GRADE_CODE_SHA_ENV=R6_CONSTRUCTION_ALLOCATION_GRADE_CODE_SHA
GRADE_IMAGE_ENV=R6_CONSTRUCTION_ALLOCATION_GRADE_RUNTIME_IMAGE

container_request() {
  [[ $# -eq 1 ]] || die "container-request requires one phase"
  local phase=$1 command request
  case "$phase" in
    prepare) command=prepare ;;
    task0) command=smoke ;;
    collect) command=collect ;;
    # A second collect invocation is the independent-process reopen.  Every
    # object is create-once, so it can only reproduce identical bytes and then
    # perform the complete terminal/predecessor replay.
    reopen) command=collect ;;
    *) die "unsupported in-container request phase" ;;
  esac
  request=$(mktemp /tmp/construction-allocation-request.XXXXXX.json)
  trap 'rm -f "$request"' EXIT
  umask 077
  printf '%s' "${!REQUEST_B64_ENV:?missing request body}" | base64 --decode >"$request" \
    || die "request base64 decode failed"
  [[ "$(sha256sum "$request" | awk '{print $1}')" == \
      "${!REQUEST_SHA_ENV:?missing request hash}" ]] || die "request bytes differ"
  if [[ "$phase" == "task0" ]]; then
    # The scientific smoke represents logical ordinal 0 of the frozen 54-task
    # panel but consumes only one Cloud Run task and publishes nothing.
    export CLOUD_RUN_TASK_INDEX=0 CLOUD_RUN_TASK_COUNT=54
  fi
  exec /usr/local/bin/python3.11 -I "$RUNNER" "$command" \
    --request "$request" --execute
}

container_task() {
  exec /usr/local/bin/python3.11 -I "$RUNNER" task --execute
}

container_grade() {
  [[ $# -eq 1 ]] || die "container-grade requires one phase"
  local phase=$1 command request
  case "$phase" in
    grade-prepare) command=prepare ;;
    grade) command=grade ;;
    grade-reopen) command=reopen ;;
    *) die "unsupported dedicated grade phase" ;;
  esac
  request=$(mktemp /tmp/construction-allocation-grade.XXXXXX.json)
  trap 'rm -f "$request"' EXIT
  umask 077
  printf '%s' "${!REQUEST_B64_ENV:?missing grade request}" | base64 --decode >"$request" \
    || die "grade request base64 decode failed"
  [[ "$(sha256sum "$request" | awk '{print $1}')" == \
      "${!REQUEST_SHA_ENV:?missing request hash}" ]] || die "grade request bytes differ"
  exec /usr/local/bin/python3.11 -I "$GRADE_RUNNER" "$command" \
    --request "$request" --execute
}

case "${1:-}" in
  container-help)
    printf '%s\n' \
      'container phases: prepare task0 task collect reopen grade-prepare grade grade-reopen'
    exit 0
    ;;
  container-request)
    shift
    container_request "$@"
    ;;
  container-task)
    shift
    container_task "$@"
    ;;
  container-grade)
    shift
    container_grade "$@"
    ;;
esac

if [[ "${1:-}" == "build" ]]; then
  [[ $# -eq 2 && "$2" =~ ^[0-9a-f]{40}$ ]] || \
    die "usage: $0 build FULL_PUSHED_CODE_SHA"
  build_code_sha=$2
  build_root=$(git rev-parse --show-toplevel 2>/dev/null) || \
    die "repository root unavailable"
  [[ "$(git -C "$build_root" rev-parse HEAD)" == "$build_code_sha" ]] || \
    die "build source commit must equal HEAD"
  [[ -z "$(git -C "$build_root" status --porcelain --untracked-files=all)" ]] || \
    die "build source checkout must be clean, including untracked files"
  [[ "$(git -C "$build_root" rev-parse --verify 'refs/remotes/origin/main^{commit}')" == \
      "$build_code_sha" ]] || die "build source commit must equal durable origin/main"

  project=nfl-predictions-503414
  region=us-central1
  source_repository=https://github.com/espechtsoftware/nfl-predictions.git
  build_image="${region}-docker.pkg.dev/${project}/nfl-dfs/nfl-dfs:construction-allocation-${build_code_sha}"
  archive_paths=(
    Dockerfile.corpus-r6-construction-allocation-snapshot
    cloudbuild.corpus-r6-construction-allocation-snapshot.yaml
    pyproject.toml
    README.md
    src
    scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh
    scripts/run_corpus_r6_construction_allocation_grade_v1.py
    scripts/run_corpus_r6_construction_allocation_snapshot_shard_v1.py
    tests/conftest.py
    tests/test_boom_first_historical_construction_snapshot_adapter_v1.py
    tests/test_corpus_r6_construction_allocation_cloud_release_v1.py
    tests/test_corpus_r6_construction_allocation_cross_v1.py
    tests/test_corpus_r6_construction_allocation_grade_operator_v1.py
    tests/test_corpus_r6_construction_allocation_operator_hardening_v1.py
    tests/test_corpus_r6_construction_allocation_shard_v1.py
    tests/test_generation_exposure.py
    tests/test_preseeded_role_identities.py
    tests/test_run_corpus_r6_construction_allocation_grade_v1.py
    tests/test_run_corpus_r6_construction_allocation_snapshot_shard_v1.py
  )
  for relative in "${archive_paths[@]}"; do
    git -C "$build_root" cat-file -e "${build_code_sha}:${relative}" || \
      die "committed build input absent: $relative"
  done
  build_temp=$(mktemp -d /tmp/construction-allocation-build.XXXXXX)
  cleanup_build() { rm -rf "$build_temp"; }
  trap cleanup_build EXIT
  [[ "$(git -C "$build_root" rev-parse --verify 'refs/remotes/origin/main^{commit}')" == \
      "$build_code_sha" ]] || die "origin/main changed during build preparation"

  submit_output=$(gcloud builds submit "$source_repository" \
    --git-source-revision "$build_code_sha" \
    --config "$build_root/cloudbuild.corpus-r6-construction-allocation-snapshot.yaml" \
    --substitutions "_CODE_SHA=$build_code_sha,_BUILD_IMAGE=$build_image" \
    --project "$project" --format='value(id)' --quiet)
  mapfile -t build_ids < <(
    printf '%s\n' "$submit_output" |
      grep -Eo '[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}' |
      sort -u
  )
  [[ "${#build_ids[@]}" -eq 1 ]] || \
    die "Cloud Build did not return exactly one durable build ID"
  built_id=${build_ids[0]}
  build_metadata=$build_temp/build.json
  gcloud builds describe "$built_id" --project "$project" --format=json \
    >"$build_metadata"
  built_digest=$(jq -er --arg id "$built_id" --arg tag "$build_image" \
    --arg sha "$build_code_sha" --arg repository "$source_repository" '
      select(.id == $id and .status == "SUCCESS" and
        .source.gitSource == {url:$repository,revision:$sha} and
        .sourceProvenance.resolvedGitSource == {url:$repository,revision:$sha} and
        .substitutions._CODE_SHA == $sha and
        .substitutions._BUILD_IMAGE == $tag) |
      [ .results.images[]? | select(.name == $tag) | .digest ] |
      if length == 1 then .[0] else error("resolved image count differs") end
    ' "$build_metadata") || die "completed Cloud Build authority differs"
  [[ "$built_digest" =~ ^sha256:[0-9a-f]{64}$ ]] || \
    die "provider-resolved image digest differs"
  immutable_image="${build_image%:*}@${built_digest}"
  attestation_uri="gs://${project}-corpus-retrieval/research/corpus-r6-construction-allocation-builds/${build_code_sha}/${built_id}/runtime-build-attestation.json"
  attestation_identity=$build_temp/runtime-build-attestation.identity.json
  host_python=$build_root/.venv/bin/python
  [[ -x "$host_python" ]] || die "exact release virtualenv Python is absent"
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$build_root/src:$build_root/scripts" \
    "$host_python" - "$build_metadata" "$source_repository" \
      "$build_code_sha" "$build_image" "$built_digest" "$attestation_uri" \
      >"$attestation_identity" <<'PY'
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import json
import sys

from nfl_dfs.research import (
    corpus_r6_construction_allocation_cross_operator_v1 as operator,
)
import run_corpus_r6_construction_allocation_snapshot_shard_v1 as runner


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
attestation = operator.runtime_build_attestation_v1(
    build_id=build_id,
    source_repository=source_repository,
    requested_source_commit=code_sha,
    resolved_source_commit=code_sha,
    image_tag=image_tag,
    image_digest=image_digest,
    provider_observed_at=finish_time,
)
operator.validate_runtime_build_attestation_v1(
    attestation, expected_code_sha=code_sha,
    expected_image_digest=image_digest,
)
provider = runner.GCloudBuildProviderV1()
if provider.observe_runtime_build(attestation) != attestation:
    raise SystemExit("independent Cloud Build observation differs")
store = runner.GCSExactKnownNameStoreV1()
raw = runner._document(attestation)
published = store.publish_create_once(attestation_uri, raw)
identity = {
    key: published[key] for key in ("uri", "generation", "sha256", "bytes")
}
if store.read_exact(identity) != raw:
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
  jq -n --arg schema "corpus-r6-construction-allocation-cloud-build/v1" \
    --arg code_sha "$build_code_sha" --arg build_id "$built_id" \
    --arg build_image "$build_image" --arg image "$immutable_image" \
    --arg digest "$built_digest" --arg source_repository "$source_repository" \
    --argjson runtime_build_attestation_identity "$(jq -cS . "$attestation_identity")" '{
      schema_version:$schema, code_sha:$code_sha, cloud_build_id:$build_id,
      build_image_tag:$build_image, provider_resolved_image:$image,
      image_digest:$digest, source_repository:$source_repository,
      provider_requested_and_resolved_git_source_exact:true,
      narrow_outcome_blind_context_built_inside_provider_git_source:true,
      runtime_build_attestation_identity:$runtime_build_attestation_identity,
      provider_git_source_is_full_repository:true,
      outcome_artifacts_read_by_build_steps:false,
      outcome_artifacts_in_runtime_image_context:false, complete:true
    }'
  exit 0
fi

[[ $# -ge 4 && $# -le 5 ]] || \
  die "usage: $0 {install|prepare|task0|task|collect|reopen|grade-prepare|grade|grade-reopen} IMAGE@sha256:DIGEST FULL_CODE_SHA BUILD_ID [ABSOLUTE_REQUEST_JSON]"
ACTION=$1
IMAGE=$2
CODE_SHA=$3
BUILD_ID=$4
REQUEST_PATH=${5:-}

PROJECT=nfl-predictions-503414
REGION=us-central1
JOB=atlas-cbc-32g-full-2023-w8-v1
EXPECTED_JOB_UID=1f4bcf0a-2300-4afa-9fc1-9981844c8275
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
PARALLELISM=4
TASK_TIMEOUT=21600s

[[ "$ACTION" =~ ^(install|prepare|task0|task|collect|reopen|grade-prepare|grade|grade-reopen)$ ]] || die "unknown action"
[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/${PROJECT}/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || \
  die "image must be the immutable project construction image"
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "CODE_SHA must be one full commit"
[[ "$BUILD_ID" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || \
  die "BUILD_ID must be one provider UUID"

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || die "repository root unavailable"
[[ "$(git -C "$ROOT" rev-parse HEAD)" == "$CODE_SHA" ]] || die "CODE_SHA must equal HEAD"
git -C "$ROOT" cat-file -e "${CODE_SHA}^{commit}" || die "CODE_SHA commit unavailable"
[[ -z "$(git -C "$ROOT" status --porcelain --untracked-files=all)" ]] || \
  die "exact release checkout must be clean, including untracked files"
[[ "$(git -C "$ROOT" rev-parse --verify 'refs/remotes/origin/main^{commit}')" == "$CODE_SHA" ]] || \
  die "CODE_SHA must equal durable origin/main"

required_paths=(
  Dockerfile.corpus-r6-construction-allocation-snapshot
  cloudbuild.corpus-r6-construction-allocation-snapshot.yaml
  scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh
  scripts/run_corpus_r6_construction_allocation_grade_v1.py
  scripts/run_corpus_r6_construction_allocation_snapshot_shard_v1.py
  src/nfl_dfs/research/corpus_r6_construction_allocation_grade_operator_v1.py
  src/nfl_dfs/research/corpus_r6_construction_allocation_grade_v1.py
)
for relative in "${required_paths[@]}"; do
  git -C "$ROOT" cat-file -e "${CODE_SHA}:${relative}" || \
    die "required committed release file absent: $relative"
done

image_digest=${IMAGE##*@}
image_tag="${IMAGE%@*}:construction-allocation-${CODE_SHA}"
temp_dir=$(mktemp -d /tmp/construction-allocation-launch.XXXXXX)
trap 'rm -rf "$temp_dir"' EXIT
build_json=$temp_dir/build.json
job_before=$temp_dir/job-before.json
job_after=$temp_dir/job-after.json
execution_json=$temp_dir/execution.json
launch_json=$temp_dir/launch.json

gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format=json >"$build_json"
jq -e --arg build "$BUILD_ID" --arg sha "$CODE_SHA" --arg tag "$image_tag" \
  --arg digest "$image_digest" '
  .id == $build and .status == "SUCCESS" and
  .substitutions._CODE_SHA == $sha and
  .substitutions._BUILD_IMAGE == $tag and
  any(.results.images[]?; .name == $tag and .digest == $digest)
' "$build_json" >/dev/null || die "Cloud Build authority differs"

# Exact describe proves the named job already exists; update can never create
# it.  The latest exact execution must be terminal before this shared slot is
# touched.  No job or execution enumeration is used.
gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format=json >"$job_before"
jq -e --arg uid "$EXPECTED_JOB_UID" '
  .metadata.uid == $uid and
  any(.status.conditions[]?; .type == "Ready" and .status == "True")
' "$job_before" >/dev/null || die "reused job identity/readiness differs"
prior_execution=$(jq -er '.status.latestCreatedExecution.name' "$job_before") \
  || die "reused job lacks an exact latest execution"
gcloud run jobs executions describe "$prior_execution" --project "$PROJECT" \
  --region "$REGION" --format=json >"$execution_json"
jq -e --arg job "$JOB" '
  .metadata.labels["run.googleapis.com/job"] == $job and
  any(.status.conditions[]?; .type == "Completed" and .status == "True") and
  (.status.completionTime | type == "string" and length > 0)
' "$execution_json" >/dev/null || die "reused job latest execution is not terminal-success"

verify_installed_job() {
  local path=$1
  jq -e --arg uid "$EXPECTED_JOB_UID" --arg image "$IMAGE" --arg sha "$CODE_SHA" \
    --arg digest "$image_digest" --arg build "$BUILD_ID" --arg sa "$SERVICE_ACCOUNT" '
    .metadata.uid == $uid and
    .spec.template.spec.taskCount == 54 and
    .spec.template.spec.parallelism == 4 and
    .spec.template.spec.template.spec.maxRetries == 0 and
    (.spec.template.spec.template.spec.timeoutSeconds == "21600" or
     .spec.template.spec.template.spec.timeout == "21600s") and
    .spec.template.spec.template.spec.serviceAccountName == $sa and
    (.spec.template.spec.template.spec.containers | length) == 1 and
    (.spec.template.spec.template.spec.containers[0] as $c |
      $c.image == $image and
      $c.command == ["/bin/bash"] and
      $c.args == ["/app/scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh", "container-help"] and
      $c.resources.limits.cpu == "8" and $c.resources.limits.memory == "32Gi" and
      ([ $c.env[] | select(.name == "CODE_SHA") | .value ] == [$sha]) and
      ([ $c.env[] | select(.name == "IMAGE_DIGEST") | .value ] == [$digest]) and
      ([ $c.env[] | select(.name == "BUILD_ID") | .value ] == [$build]) and
      ([ $c.env[] | select(.name == "R6_CONSTRUCTION_ALLOCATION_SNAPSHOT_SHARD_ENABLE") | .value ] == ["DISABLED_INSTALL_ONLY"])
    )
  ' "$path" >/dev/null || die "installed reused-job template differs"
}

# Materialize the one provider-observed execution authority consumed by the
# collector.  This is intentionally an exact-name operation: the caller must
# name the prior 54-task execution, and neither Cloud Run nor GCS is listed.
# The provider completion timestamp makes repeated independent reopen calls
# byte-identical instead of injecting launcher wall-clock time.
publish_runtime_execution_attestation() {
  [[ $# -eq 4 ]] || die "execution attestation requires four exact files"
  local manifest_identity_path=$1 observed_job_path=$2
  local observed_execution_path=$3 output_identity_path=$4
  local host_python=$ROOT/.venv/bin/python
  [[ -x "$host_python" ]] || die "exact release virtualenv Python is absent"
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/src:$ROOT/scripts" \
    "$host_python" - \
      "$manifest_identity_path" "$observed_job_path" \
      "$observed_execution_path" "$PROJECT" "$REGION" "$JOB" \
      "$EXPECTED_JOB_UID" "$CODE_SHA" "$IMAGE" "$image_digest" \
      "$BUILD_ID" "$ENABLE_VALUE" "$SERVICE_ACCOUNT" \
      >"$output_identity_path" <<'PY'
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import json
import re
import sys

from nfl_dfs.research import (
    corpus_r6_construction_allocation_cross_operator_v1 as operator,
)
import run_corpus_r6_construction_allocation_snapshot_shard_v1 as runner


(
    manifest_identity_path,
    observed_job_path,
    observed_execution_path,
    project,
    region,
    expected_job,
    expected_job_uid,
    code_sha,
    immutable_image,
    image_digest,
    build_id,
    enable_value,
    service_account,
) = sys.argv[1:]


def fail(message: str) -> None:
    raise SystemExit(message)


def mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        fail(f"{label} is not an object")
    return dict(value)


def load(path: str, label: str) -> dict[str, object]:
    try:
        return mapping(json.loads(Path(path).read_bytes()), label)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"{label} bytes differ: {exc}")


def count(status: Mapping[str, object], name: str) -> int:
    value = status.get(name, 0)
    if value in {None, ""}:
        return 0
    if type(value) is not int or value < 0:
        fail(f"Cloud Run {name} differs")
    return value


def env_value(container: Mapping[str, object], name: str) -> str:
    values = [
        item.get("value")
        for item in container.get("env", [])
        if isinstance(item, Mapping) and item.get("name") == name
    ]
    if len(values) != 1 or type(values[0]) is not str:
        fail(f"Cloud Run task environment {name} differs")
    return values[0]


provided_manifest_identity = load(
    manifest_identity_path, "provided manifest identity"
)
store = runner.GCSExactKnownNameStoreV1()
manifest, retained_manifest_identity, _ = runner.open_input_manifest_v1(
    provided_manifest_identity, store=store
)
expected_identity = {
    key: provided_manifest_identity.get(key)
    for key in ("uri", "generation", "sha256", "bytes")
}
expected_identity["generation"] = str(expected_identity["generation"])
if retained_manifest_identity != expected_identity:
    fail("generation-exact manifest identity differs")
if (
    manifest.get("code_sha") != code_sha
    or manifest.get("image_digest") != image_digest
    or manifest.get("task_count") != 54
):
    fail("manifest runtime/task authority differs")

job = load(observed_job_path, "Cloud Run job observation")
execution = load(observed_execution_path, "Cloud Run execution observation")
job_metadata = mapping(job.get("metadata"), "Cloud Run job metadata")
execution_metadata = mapping(
    execution.get("metadata"), "Cloud Run execution metadata"
)
labels = mapping(execution_metadata.get("labels"), "Cloud Run execution labels")
status = mapping(execution.get("status"), "Cloud Run execution status")
spec = mapping(execution.get("spec"), "Cloud Run execution spec")
template = mapping(spec.get("template"), "Cloud Run task template")
task_spec = mapping(template.get("spec"), "Cloud Run task spec")
containers = task_spec.get("containers")
if not isinstance(containers, list) or len(containers) != 1:
    fail("Cloud Run task container count differs")
container = mapping(containers[0], "Cloud Run task container")

job_generation = str(labels.get("run.googleapis.com/jobGeneration", ""))
execution_name = str(execution_metadata.get("name", ""))
execution_uid = str(execution_metadata.get("uid", ""))
completion_time = status.get("completionTime")
completed = status.get("conditions")
completed_true = isinstance(completed, list) and any(
    isinstance(condition, Mapping)
    and condition.get("type") == "Completed"
    and str(condition.get("status")).lower() == "true"
    for condition in completed
)
if (
    job_metadata.get("name") != expected_job
    or str(job_metadata.get("uid")) != expected_job_uid
    or str(job_metadata.get("generation")) != job_generation
    or labels.get("run.googleapis.com/job") != expected_job
    or str(labels.get("run.googleapis.com/jobUid")) != expected_job_uid
    or re.fullmatch(re.escape(expected_job) + r"-[a-z0-9]{5}", execution_name)
    is None
    or not execution_uid
    or spec.get("taskCount") != 54
    or spec.get("parallelism") != 4
    or task_spec.get("maxRetries") != 0
    or task_spec.get("serviceAccountName") != service_account
    or container.get("image") != immutable_image
    or container.get("command") != ["/bin/bash"]
    or container.get("args")
    != [
        "/app/scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh",
        "container-task",
    ]
    or env_value(container, "CODE_SHA") != code_sha
    or env_value(container, "IMAGE_DIGEST") != image_digest
    or env_value(container, "BUILD_ID") != build_id
    or env_value(
        container, "R6_CONSTRUCTION_ALLOCATION_SNAPSHOT_SHARD_ENABLE"
    ) != enable_value
    or env_value(
        container,
        "R6_CONSTRUCTION_ALLOCATION_SNAPSHOT_SHARD_MANIFEST_IDENTITY",
    )
    != json.dumps(
        retained_manifest_identity, sort_keys=True, separators=(",", ":")
    )
    or env_value(
        container, "R6_CONSTRUCTION_ALLOCATION_NO_OUTCOME_SMOKE"
    ) != "false"
    or env_value(
        container, "R6_CONSTRUCTION_ALLOCATION_TARGET_OUTCOMES_ALLOWED"
    ) != "false"
    or not completed_true
    or type(completion_time) is not str
    or not completion_time.endswith("Z")
):
    fail("Cloud Run 54-task execution authority differs")

succeeded_count = count(status, "succeededCount")
failed_count = count(status, "failedCount")
cancelled_count = count(status, "cancelledCount")
running_count = count(status, "runningCount")
if (
    succeeded_count != 54
    or failed_count != 0
    or cancelled_count != 0
    or running_count != 0
):
    fail("Cloud Run 54-task terminal counts differ")

attestation = operator.runtime_execution_attestation_v1(
    project_id=project,
    region=region,
    job_name=expected_job,
    job_generation=job_generation,
    execution_name=execution_name,
    execution_uid=execution_uid,
    task_count=54,
    succeeded_count=succeeded_count,
    failed_count=failed_count,
    cancelled_count=cancelled_count,
    running_count=running_count,
    code_sha=code_sha,
    image_digest=image_digest,
    provider_observed_at=completion_time,
)
validated = operator.validate_runtime_execution_attestation_v1(
    attestation,
    expected_code_sha=code_sha,
    expected_image_digest=image_digest,
    expected_task_count=54,
)
if validated != attestation or attestation["uses_target_slate_outcomes"] is not False:
    fail("runtime execution attestation validation differs")

manifest_uri = str(manifest["manifest_uri"])
suffix = "input-manifest.json"
if not manifest_uri.endswith(suffix):
    fail("manifest URI suffix differs")
attestation_uri = (
    manifest_uri[: -len(suffix)]
    + "authorities/runtime-execution-attestation-"
    + execution_name
    + ".json"
)
raw = runner._document(attestation)
published = store.publish_create_once(attestation_uri, raw)
identity = {
    "uri": published["uri"],
    "generation": str(published["generation"]),
    "sha256": published["sha256"],
    "bytes": published["bytes"],
}
if store.read_exact(identity) != raw:
    fail("runtime execution attestation exact reopen differs")
sys.stdout.write(json.dumps(identity, sort_keys=True, separators=(",", ":")) + "\n")
PY
  jq -e '
    (keys | sort) == (["bytes","generation","sha256","uri"] | sort) and
    (.uri | startswith("gs://")) and
    (.generation | type == "string" and length > 0) and
    (.sha256 | test("^[0-9a-f]{64}$")) and
    (.bytes | type == "number" and . > 0)
  ' "$output_identity_path" >/dev/null || \
    die "runtime execution attestation identity differs"
}

if [[ "$ACTION" == "install" ]]; then
  [[ -z "$REQUEST_PATH" ]] || die "install accepts no request"
  gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
    --image "$IMAGE" --command /bin/bash \
    --args /app/scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh,container-help \
    --tasks 54 --parallelism "$PARALLELISM" --max-retries 0 \
    --cpu 8 --memory 32Gi --task-timeout "$TASK_TIMEOUT" \
    --service-account "$SERVICE_ACCOUNT" \
    --set-env-vars "CODE_SHA=$CODE_SHA,IMAGE_DIGEST=$image_digest,BUILD_ID=$BUILD_ID,$ENABLE_ENV=DISABLED_INSTALL_ONLY" \
    --quiet >/dev/null
  gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
    --format=json >"$job_after"
  verify_installed_job "$job_after"
  prior_generation=$(jq -er '.metadata.generation' "$job_before")
  installed_generation=$(jq -er '.metadata.generation' "$job_after")
  [[ "$installed_generation" =~ ^[0-9]+$ && "$prior_generation" =~ ^[0-9]+$ && \
      "$installed_generation" -gt "$prior_generation" ]] || \
    die "reused job generation did not advance exactly through installation"
  jq -n --arg schema "corpus-r6-construction-allocation-cloud-install/v1" \
    --arg code_sha "$CODE_SHA" --arg build_id "$BUILD_ID" --arg image "$IMAGE" \
    --arg image_digest "$image_digest" --arg job "$JOB" --arg uid "$EXPECTED_JOB_UID" \
    --argjson generation "$installed_generation" --arg prior_execution "$prior_execution" '{
      schema_version:$schema, code_sha:$code_sha, cloud_build_id:$build_id,
      provider_resolved_image:$image, image_digest:$image_digest,
      reused_job:{name:$job,uid:$uid,generation:$generation},
      prior_terminal_execution:$prior_execution, install_only:true,
      execution_launched:false, no_outcome_mode:true, complete:true
    }'
  exit 0
fi

[[ -n "$REQUEST_PATH" && "$REQUEST_PATH" == /* && -f "$REQUEST_PATH" && ! -L "$REQUEST_PATH" ]] || \
  die "$ACTION requires one absolute unaliased request file"
gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format=json >"$job_after"
verify_installed_job "$job_after"

runtime_execution_attestation_identity=null
source_task_execution=null
grade_phase=false
case "$ACTION" in
  prepare)
    jq -e --arg sha "$CODE_SHA" --arg digest "$image_digest" '
      (keys | sort) == (["code_sha","frozen_at","frozen_boom_first_manifest_identity","image_digest","output_prefix","panel_identity","run_id","runtime_build_attestation_identity"] | sort) and
      .code_sha == $sha and .image_digest == $digest
    ' "$REQUEST_PATH" >/dev/null || die "prepare request authority differs"
    manifest_identity=$(jq -cS '.frozen_boom_first_manifest_identity' "$REQUEST_PATH")
    execution_args="/app/scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh,container-request,prepare"
    tasks=1
    no_outcome_smoke=false
    outcomes_allowed=false
    ;;
  task0|task)
    jq -e '(keys == ["manifest_identity"])' "$REQUEST_PATH" >/dev/null || \
      die "$ACTION request must contain only manifest_identity"
    manifest_identity=$(jq -cS '.manifest_identity' "$REQUEST_PATH")
    if [[ "$ACTION" == "task" ]]; then
      execution_args="/app/scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh,container-task"
      tasks=54
    else
      execution_args="/app/scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh,container-request,task0"
      tasks=1
    fi
    [[ "$ACTION" == "task0" ]] && no_outcome_smoke=true || no_outcome_smoke=false
    outcomes_allowed=false
    ;;
  collect|reopen)
    jq -e '(keys == ["manifest_identity"])' "$REQUEST_PATH" >/dev/null || \
      die "$ACTION input request must contain only manifest_identity"
    manifest_identity=$(jq -cS '.manifest_identity' "$REQUEST_PATH")
    task_execution_name=${R6_CONSTRUCTION_ALLOCATION_TASK_EXECUTION_NAME:-}
    [[ "$task_execution_name" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
      die "$ACTION requires exact $TASK_EXECUTION_ENV"
    task_execution_json=$temp_dir/task-execution.json
    gcloud run jobs executions describe "$task_execution_name" \
      --project "$PROJECT" --region "$REGION" --format=json \
      >"$task_execution_json"
    manifest_identity_path=$temp_dir/manifest-identity.json
    attestation_identity_path=$temp_dir/runtime-execution-attestation.identity.json
    printf '%s\n' "$manifest_identity" >"$manifest_identity_path"
    publish_runtime_execution_attestation \
      "$manifest_identity_path" "$job_after" "$task_execution_json" \
      "$attestation_identity_path"
    runtime_execution_attestation_identity=$(jq -cS . "$attestation_identity_path")
    source_task_execution=$(jq -cnS \
      --arg name "$task_execution_name" \
      --arg uid "$(jq -er '.metadata.uid' "$task_execution_json")" \
      --argjson task_count 54 \
      '{name:$name,uid:$uid,task_count:$task_count}')
    effective_request=$temp_dir/collect-request.json
    jq -cnS --argjson manifest "$manifest_identity" \
      --argjson execution "$runtime_execution_attestation_identity" '{
        manifest_identity:$manifest,
        runtime_execution_attestation_identity:$execution
      }' >"$effective_request"
    REQUEST_PATH=$effective_request
    if [[ "$ACTION" == "collect" ]]; then
      execution_args="/app/scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh,container-request,collect"
    else
      execution_args="/app/scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh,container-request,reopen"
    fi
    tasks=1
    no_outcome_smoke=false
    outcomes_allowed=false
    ;;
  grade-prepare)
    jq -e --arg sha "$CODE_SHA" --arg image "$IMAGE" '
      .schema_version == "corpus-r6-construction-allocation-grade-prepare-request/v1" and
      (keys | sort) == (["code_sha","frozen_at","grade_id","immutable_image","outcome_authority_identity","output_prefix","run_id","schema_version","selection_terminal_envelope"] | sort) and
      .code_sha == $sha and .immutable_image == $image and
      (.selection_terminal_envelope.terminal_identity | type == "object")
    ' "$REQUEST_PATH" >/dev/null || die "grade prepare request authority differs"
    manifest_identity=$(jq -cS \
      '.selection_terminal_envelope.terminal_identity' "$REQUEST_PATH")
    execution_args="/app/scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh,container-grade,grade-prepare"
    tasks=1
    no_outcome_smoke=false
    outcomes_allowed=false
    grade_phase=true
    ;;
  grade)
    jq -e '
      .schema_version == "corpus-r6-construction-allocation-grade-execute-request/v1" and
      (keys | sort) == (["manifest_identity","schema_version"] | sort)
    ' "$REQUEST_PATH" >/dev/null || die "grade request authority differs"
    manifest_identity=$(jq -cS '.manifest_identity' "$REQUEST_PATH")
    execution_args="/app/scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh,container-grade,grade"
    tasks=1
    no_outcome_smoke=false
    outcomes_allowed=true
    grade_phase=true
    ;;
  grade-reopen)
    jq -e --arg sha "$CODE_SHA" --arg image "$IMAGE" '
      .schema_version == "corpus-r6-construction-allocation-grade-reopen-request/v1" and
      (keys | sort) == (["code_sha","immutable_image","schema_version","terminal_envelope"] | sort) and
      .code_sha == $sha and .immutable_image == $image and
      (.terminal_envelope.manifest_identity | type == "object")
    ' "$REQUEST_PATH" >/dev/null || die "grade reopen request authority differs"
    manifest_identity=$(jq -cS '.terminal_envelope.manifest_identity' "$REQUEST_PATH")
    execution_args="/app/scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh,container-grade,grade-reopen"
    tasks=1
    no_outcome_smoke=false
    outcomes_allowed=true
    grade_phase=true
    ;;
esac

[[ "$manifest_identity" != "null" ]] || die "request input authority is null"
request_sha=$(sha256sum "$REQUEST_PATH" | awk '{print $1}')
request_b64=$(base64 -w0 "$REQUEST_PATH")
grade_env_override=""
if [[ "$grade_phase" == "true" ]]; then
  grade_env_override="|$GRADE_ENABLE_ENV=1|$GRADE_CODE_SHA_ENV=$CODE_SHA|$GRADE_IMAGE_ENV=$IMAGE"
fi
env_override="^|^CODE_SHA=$CODE_SHA|IMAGE_DIGEST=$image_digest|BUILD_ID=$BUILD_ID|$ENABLE_ENV=$ENABLE_VALUE|$MANIFEST_ENV=$manifest_identity|$REQUEST_SHA_ENV=$request_sha|$REQUEST_B64_ENV=$request_b64|R6_CONSTRUCTION_ALLOCATION_JOB_NAME=$JOB|R6_CONSTRUCTION_ALLOCATION_FULL_IMAGE=$IMAGE|R6_CONSTRUCTION_ALLOCATION_NO_OUTCOME_SMOKE=$no_outcome_smoke|R6_CONSTRUCTION_ALLOCATION_TARGET_OUTCOMES_ALLOWED=$outcomes_allowed$grade_env_override"

gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --tasks "$tasks" --args "$execution_args" --update-env-vars "$env_override" \
  --async --format=json >"$launch_json"
execution_name=$(jq -er '.metadata.name' "$launch_json") || die "launch lacks execution name"
[[ "$execution_name" == "$JOB-"* ]] || die "execution name is not bound to reused job"
gcloud run jobs executions describe "$execution_name" --project "$PROJECT" \
  --region "$REGION" --format=json >"$execution_json"

job_generation=$(jq -er '.metadata.generation' "$job_after")
jq -e --arg job "$JOB" --arg image "$IMAGE" --arg sha "$CODE_SHA" \
  --arg digest "$image_digest" --arg build "$BUILD_ID" --arg args_csv "$execution_args" \
  --arg manifest "$manifest_identity" --arg enable "$ENABLE_VALUE" \
  --arg request_sha "$request_sha" --arg job_uid "$EXPECTED_JOB_UID" \
  --arg job_generation "$job_generation" --arg grade_image "$IMAGE" \
  --argjson grade_phase "$grade_phase" --argjson tasks "$tasks" '
  .metadata.labels["run.googleapis.com/job"] == $job and
  .metadata.labels["run.googleapis.com/jobUid"] == $job_uid and
  .metadata.labels["run.googleapis.com/jobGeneration"] == $job_generation and
  .spec.taskCount == $tasks and
  .spec.template.spec.maxRetries == 0 and
  (.spec.template.spec.containers[0] as $c |
    $c.image == $image and $c.command == ["/bin/bash"] and
    $c.args == ($args_csv | split(",")) and
    ([ $c.env[] | select(.name == "CODE_SHA") | .value ] == [$sha]) and
    ([ $c.env[] | select(.name == "IMAGE_DIGEST") | .value ] == [$digest]) and
    ([ $c.env[] | select(.name == "BUILD_ID") | .value ] == [$build]) and
    ([ $c.env[] | select(.name == "R6_CONSTRUCTION_ALLOCATION_SNAPSHOT_SHARD_ENABLE") | .value ] == [$enable]) and
    ([ $c.env[] | select(.name == "R6_CONSTRUCTION_ALLOCATION_SNAPSHOT_SHARD_MANIFEST_IDENTITY") | .value ] == [$manifest]) and
    ([ $c.env[] | select(.name == "R6_CONSTRUCTION_ALLOCATION_CLOUD_REQUEST_SHA256") | .value ] == [$request_sha]) and
    (($grade_phase == false) or (
      ([ $c.env[] | select(.name == "R6_CONSTRUCTION_ALLOCATION_GRADE_ENABLED") | .value ] == ["1"]) and
      ([ $c.env[] | select(.name == "R6_CONSTRUCTION_ALLOCATION_GRADE_CODE_SHA") | .value ] == [$sha]) and
      ([ $c.env[] | select(.name == "R6_CONSTRUCTION_ALLOCATION_GRADE_RUNTIME_IMAGE") | .value ] == [$grade_image])
    ))
  )
' "$execution_json" >/dev/null || die "execution provider authority differs"

execution_uid=$(jq -er '.metadata.uid' "$execution_json") || die "execution UID absent"
jq -n --arg schema "corpus-r6-construction-allocation-cloud-launch/v1" \
  --arg phase "$ACTION" --arg code_sha "$CODE_SHA" --arg build_id "$BUILD_ID" \
  --arg image "$IMAGE" --arg image_digest "$image_digest" \
  --arg job "$JOB" --arg job_uid "$EXPECTED_JOB_UID" --argjson job_generation "$job_generation" \
  --arg execution "$execution_name" --arg execution_uid "$execution_uid" \
  --argjson task_count "$tasks" --argjson manifest_identity "$manifest_identity" \
  --argjson runtime_execution_attestation_identity "$runtime_execution_attestation_identity" \
  --argjson source_task_execution "$source_task_execution" \
  --arg request_sha "$request_sha" --argjson no_outcome_smoke "$no_outcome_smoke" \
  --argjson outcomes_allowed "$outcomes_allowed" '{
    schema_version:$schema, phase:$phase, code_sha:$code_sha,
    cloud_build_id:$build_id, provider_resolved_image:$image,
    image_digest:$image_digest,
    reused_job:{name:$job,uid:$job_uid,generation:$job_generation},
    execution:{name:$execution,uid:$execution_uid,task_count:$task_count},
    bound_input_authority_identity:$manifest_identity,
    manifest_identity:$manifest_identity,
    runtime_execution_attestation_identity:$runtime_execution_attestation_identity,
    source_task_execution:$source_task_execution,
    request_sha256:$request_sha,
    no_outcome_smoke_mode:$no_outcome_smoke,
    target_slate_outcomes_allowed:$outcomes_allowed,
    execution_provider_reopened:true, complete:true
  }'
