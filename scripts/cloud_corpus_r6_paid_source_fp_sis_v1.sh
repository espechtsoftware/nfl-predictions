#!/usr/bin/env bash
# Immutable build/install/execute boundary for the fixed-corpus Fantasy
# Points x SIS ablation. It reuses one exact job and never creates/lists jobs.
set -euo pipefail

die() { printf '%s\n' "ERROR: $*" >&2; exit 2; }

RUNNER=/app/scripts/run_corpus_r6_paid_source_fp_sis_v1.py
REQUEST_B64_ENV=R6_PAID_SOURCE_FP_SIS_REQUEST_B64
REQUEST_SHA_ENV=R6_PAID_SOURCE_FP_SIS_REQUEST_SHA256
TASK0_B64_ENV=R6_PAID_SOURCE_FP_SIS_TASK0_RECEIPT_B64
TASK0_SHA_ENV=R6_PAID_SOURCE_FP_SIS_TASK0_RECEIPT_SHA256
TASK0_GATE_B64_ENV=R6_PAID_SOURCE_FP_SIS_TASK0_PROVIDER_GATE_B64
TASK0_GATE_SHA_ENV=R6_PAID_SOURCE_FP_SIS_TASK0_PROVIDER_GATE_SHA256
PUBLICATIONS_B64_ENV=R6_PAID_SOURCE_FP_SIS_SLATE_PUBLICATIONS_GZIP_B64
PUBLICATIONS_SHA_ENV=R6_PAID_SOURCE_FP_SIS_SLATE_PUBLICATIONS_SHA256
ENABLE_ENV=R6_PAID_SOURCE_FP_SIS_ENABLE
ENABLE_VALUE=I_UNDERSTAND_FIXED_CORPUS_FP_SIS_ABLATION_V1
OUTCOMES_ENV=R6_PAID_SOURCE_FP_SIS_OUTCOMES_ALLOWED
MAX_REQUEST_BYTES=16777216
MAX_ENV_B64_BYTES=30000

decode_exact_file() {
  [[ $# -eq 4 ]] || die "decode-exact-file contract differs"
  local payload_env=$1 digest_env=$2 destination=$3 label=$4
  local expected_digest=${!digest_env:-}
  local payload=${!payload_env:-}
  [[ "$expected_digest" =~ ^[0-9a-f]{64}$ ]] || \
    die "$label SHA-256 differs"
  [[ -n "$payload" && "${#payload}" -le "$MAX_ENV_B64_BYTES" ]] || \
    die "$label base64 envelope differs"
  umask 077
  printf '%s' "$payload" | base64 --decode >"$destination" || \
    die "$label base64 decode failed"
  [[ -f "$destination" && ! -L "$destination" ]] || \
    die "$label file differs"
  local size
  size=$(stat -c '%s' "$destination") || die "$label stat failed"
  [[ "$size" =~ ^[0-9]+$ && "$size" -ge 1 && \
     "$size" -le "$MAX_REQUEST_BYTES" ]] || die "$label size differs"
  [[ "$(sha256sum "$destination" | awk '{print $1}')" == \
      "$expected_digest" ]] || die "$label bytes differ"
}

decode_exact_gzip_file() {
  [[ $# -eq 4 ]] || die "decode-exact-gzip-file contract differs"
  local payload_env=$1 digest_env=$2 destination=$3 label=$4
  local expected_digest=${!digest_env:-}
  local payload=${!payload_env:-}
  local archive=${destination}.gz size
  [[ "$expected_digest" =~ ^[0-9a-f]{64}$ ]] || die "$label SHA-256 differs"
  [[ -n "$payload" && "${#payload}" -le "$MAX_ENV_B64_BYTES" ]] || \
    die "$label compressed envelope differs"
  umask 077
  printf '%s' "$payload" | base64 --decode >"$archive" || \
    die "$label compressed base64 decode failed"
  gzip -dc "$archive" >"$destination" || die "$label gzip decode failed"
  rm -f "$archive"
  [[ -f "$destination" && ! -L "$destination" ]] || die "$label file differs"
  size=$(stat -c '%s' "$destination") || die "$label stat failed"
  [[ "$size" =~ ^[0-9]+$ && "$size" -ge 1 && \
     "$size" -le "$MAX_REQUEST_BYTES" ]] || die "$label size differs"
  [[ "$(sha256sum "$destination" | awk '{print $1}')" == \
      "$expected_digest" ]] || die "$label bytes differ"
}

container_run() {
  [[ $# -eq 1 ]] || die "container-run requires one mode"
  local mode=$1 work request receipt task0_gate publications
  case "$mode" in
    validate|task0|task|collect|reopen|grade|grade-reopen) ;;
    *) die "unsupported paid-source container mode" ;;
  esac
  work=$(mktemp -d /tmp/paid-source-fp-sis.XXXXXX)
  cleanup_paid_source_request() { rm -rf "$work"; }
  trap cleanup_paid_source_request EXIT
  request=$work/request.json
  decode_exact_file "$REQUEST_B64_ENV" "$REQUEST_SHA_ENV" \
    "$request" "paid-source request"
  if [[ "$mode" == "validate" ]]; then
    /usr/local/bin/python3.11 -I "$RUNNER" validate --request "$request"
    return
  fi
  if [[ "$mode" == "task" || "$mode" == "collect" ]]; then
    receipt=$work/task0-receipt.json
    task0_gate=$work/task0-provider-gate.json
    decode_exact_file "$TASK0_B64_ENV" "$TASK0_SHA_ENV" \
      "$receipt" "paid-source task0 receipt"
    decode_exact_file "$TASK0_GATE_B64_ENV" "$TASK0_GATE_SHA_ENV" \
      "$task0_gate" "paid-source task0 provider gate"
    if [[ "$mode" == "collect" ]]; then
      publications=$work/slate-publications.json
      decode_exact_gzip_file "$PUBLICATIONS_B64_ENV" "$PUBLICATIONS_SHA_ENV" \
        "$publications" "paid-source slate publications"
      /usr/local/bin/python3.11 -I "$RUNNER" collect \
        --request "$request" --task0-receipt "$receipt" \
        --task0-provider-gate "$task0_gate" \
        --slate-publications "$publications" --execute
      return
    fi
    /usr/local/bin/python3.11 -I "$RUNNER" task \
      --request "$request" --task0-receipt "$receipt" \
      --task0-provider-gate "$task0_gate" --execute
    return
  fi
  /usr/local/bin/python3.11 -I "$RUNNER" "$mode" \
    --request "$request" --execute
}

case "${1:-}" in
  container-help)
    printf '%s\n' \
      'container modes: validate task0 task collect reopen grade grade-reopen'
    exit 0
    ;;
  container-run)
    shift
    container_run "$@"
    exit 0
    ;;
  host-help)
    printf '%s\n' \
      'host chain:' \
      '  build FULL_PUSHED_CODE_SHA' \
      '  prepare IMAGE@sha256:DIGEST FULL_CODE_SHA BUILD_ID PREPARE_INPUT > request.json' \
      '  install IMAGE@sha256:DIGEST FULL_CODE_SHA BUILD_ID' \
      '  launch IMAGE FULL_CODE_SHA BUILD_ID task0 REQUEST' \
      '  result IMAGE FULL_CODE_SHA BUILD_ID TASK0_EXECUTION > task0-cloud-result.json' \
      '  launch IMAGE FULL_CODE_SHA BUILD_ID task REQUEST TASK0_EXECUTION' \
      '  task-manifest IMAGE FULL_CODE_SHA BUILD_ID FULL54_EXECUTION > publications.json' \
      '  launch IMAGE FULL_CODE_SHA BUILD_ID collect REQUEST TASK0_EXECUTION publications.json FULL54_EXECUTION' \
      '  result IMAGE FULL_CODE_SHA BUILD_ID COLLECT_EXECUTION' \
      '  launch IMAGE FULL_CODE_SHA BUILD_ID reopen REOPEN_REQUEST' \
      '  launch IMAGE FULL_CODE_SHA BUILD_ID grade GRADE_REQUEST' \
      '  launch IMAGE FULL_CODE_SHA BUILD_ID grade-reopen GRADE_REOPEN_REQUEST'
    exit 0
    ;;
  *) ;;
esac

PROJECT=nfl-predictions-503414
REGION=us-central1
SOURCE_REPOSITORY=https://github.com/espechtsoftware/nfl-predictions.git
JOB=atlas-cbc-32g-full-2023-w8-v1
EXPECTED_JOB_UID=1f4bcf0a-2300-4afa-9fc1-9981844c8275
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
TASK_TIMEOUT=21600s
CPU=8
MEMORY=32Gi

release_paths=(
  Dockerfile.corpus-r6-paid-source-fp-sis
  Dockerfile.corpus-r6-paid-source-fp-sis.dockerignore
  cloudbuild.corpus-r6-paid-source-fp-sis.yaml
  pyproject.toml
  README.md
  scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh
  scripts/run_corpus_r6_paid_source_fp_sis_v1.py
  scripts/run_corpus_r6_construction_allocation_grade_v1.py
  src/nfl_dfs/research/corpus_r6_paid_source_ablation_v1.py
  src/nfl_dfs/research/corpus_r6_paid_source_discovery_matrix_freeze_v1.py
  src/nfl_dfs/research/corpus_r6_construction_allocation_cross_operator_v1.py
  src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py
  src/nfl_dfs/research/corpus_r6_matchup_source_v2.py
  src/nfl_dfs/research/corpus_r6_matchup_source_release_outer_candidate_authority_v3.py
  src/nfl_dfs/research/paid_source_ablation_execution_v1.py
  src/nfl_dfs/research/paid_source_ablation_grade_v1.py
  src/nfl_dfs/research/paid_source_ablation_operator_v1.py
  src/nfl_dfs/research/paid_source_ablation_registry_v1.py
  tests/test_paid_source_ablation_execution_v1.py
  tests/test_run_corpus_r6_paid_source_fp_sis_v1.py
  tests/test_cloud_corpus_r6_paid_source_fp_sis_v1.py
)

require_exact_release_commit() {
  [[ $# -eq 2 ]] || die "release commit check requires root and SHA"
  local root=$1 code=$2 path status
  [[ "$(git -C "$root" rev-parse HEAD)" == "$code" ]] || \
    die "release SHA must equal HEAD"
  [[ "$(git -C "$root" rev-parse --verify 'refs/remotes/origin/main^{commit}')" == \
     "$code" ]] || die "release SHA must equal durable origin/main"
  for path in "${release_paths[@]}"; do
    git -C "$root" cat-file -e "${code}:${path}" || \
      die "committed release path absent: $path"
    [[ -f "$root/$path" && ! -L "$root/$path" ]] || \
      die "release path is absent or aliased: $path"
    status=$(git -C "$root" status --porcelain --untracked-files=all -- "$path")
    [[ -z "$status" ]] || die "release path differs from commit: $path"
  done
}

if [[ "${1:-}" == "build" ]]; then
  [[ $# -eq 2 && "$2" =~ ^[0-9a-f]{40}$ ]] || \
    die "usage: $0 build FULL_PUSHED_CODE_SHA"
  root=$(git rev-parse --show-toplevel 2>/dev/null) || die "repository root absent"
  code_sha=$2
  require_exact_release_commit "$root" "$code_sha"
  image_tag="${REGION}-docker.pkg.dev/${PROJECT}/nfl-dfs/nfl-dfs:paid-source-fp-sis-${code_sha}"
  mkdir -p "$root/.build-contexts"
  work=$(mktemp -d "$root/.build-contexts/paid-source-fp-sis-build.XXXXXX")
  cleanup_host_build() { rm -rf "$work"; }
  trap cleanup_host_build EXIT
  build_output=$(gcloud builds submit "$SOURCE_REPOSITORY" \
    --git-source-revision "$code_sha" \
    --config "$root/cloudbuild.corpus-r6-paid-source-fp-sis.yaml" \
    --substitutions "_CODE_SHA=$code_sha,_BUILD_IMAGE=$image_tag,_SOURCE_REPOSITORY=$SOURCE_REPOSITORY" \
    --project "$PROJECT" --format='value(id)' --quiet)
  mapfile -t build_ids < <(printf '%s\n' "$build_output" | \
    grep -Eo '[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}' | sort -u)
  [[ "${#build_ids[@]}" -eq 1 ]] || die "Cloud Build ID count differs"
  build_id=${build_ids[0]}
  gcloud builds describe "$build_id" --project "$PROJECT" \
    --format=json >"$work/build.json"
  digest=$(jq -er --arg id "$build_id" --arg sha "$code_sha" \
    --arg image "$image_tag" --arg source "$SOURCE_REPOSITORY" '
      select(.id == $id and .status == "SUCCESS" and
        .source.gitSource == {url:$source,revision:$sha} and
        .sourceProvenance.resolvedGitSource == {url:$source,revision:$sha} and
        .substitutions._CODE_SHA == $sha and
        .substitutions._BUILD_IMAGE == $image and
        .substitutions._SOURCE_REPOSITORY == $source) |
      [.results.images[]? | select(.name == $image) | .digest] |
      if length == 1 then .[0] else error("image digest count differs") end
    ' "$work/build.json") || die "Cloud Build authority differs"
  [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || die "image digest differs"
  immutable_image="${image_tag%:*}@${digest}"
  attestation_uri="gs://${PROJECT}-corpus-retrieval/research/corpus-r6-paid-source-fp-sis-builds/${code_sha}/${build_id}/runtime-build-attestation.json"
  attestation_identity=$work/runtime-build-attestation.identity.json
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$root/src:$root/scripts" \
    "$root/.venv/bin/python" - "$work/build.json" "$SOURCE_REPOSITORY" \
      "$code_sha" "$image_tag" "$digest" "$attestation_uri" \
      >"$attestation_identity" <<'PY'
import json
from pathlib import Path
import sys

from nfl_dfs.research import corpus_r6_construction_allocation_cross_operator_v1 as authority
from nfl_dfs.research import paid_source_ablation_registry_v1 as registry
import run_corpus_r6_paid_source_fp_sis_v1 as runner

metadata_path, repository, code_sha, tag, digest, uri = sys.argv[1:]
metadata = json.loads(Path(metadata_path).read_bytes())
attestation = authority.runtime_build_attestation_v1(
    build_id=metadata["id"],
    source_repository=repository,
    requested_source_commit=code_sha,
    resolved_source_commit=code_sha,
    image_tag=tag,
    image_digest=digest,
    provider_observed_at=metadata["finishTime"],
)
raw = registry.canonical_json_bytes(attestation)
store = runner.GCSExactCreateOnceAndFileStoreV1()
identity = store.publish_create_once(uri, raw)
if store.read_exact(identity) != raw:
    raise SystemExit("runtime build attestation exact reopen differs")
print(json.dumps(identity, sort_keys=True, separators=(",", ":")))
PY
  jq -e '
    .create_once == true and (.generation | test("^[0-9]+$")) and
    (.sha256 | test("^[0-9a-f]{64}$")) and (.bytes > 0)
  ' "$attestation_identity" >/dev/null || die "runtime build attestation differs"
  jq -n -cS --arg schema "corpus-r6-paid-source-fp-sis-build/v1" \
    --arg code "$code_sha" --arg build "$build_id" \
    --arg image "$immutable_image" --arg digest "$digest" \
    --argjson attestation "$(jq -cS . "$attestation_identity")" '{
      schema_version:$schema,code_sha:$code,cloud_build_id:$build,
      provider_resolved_image:$image,image_digest:$digest,
      runtime_build_attestation_identity:$attestation,
      direct_git_source_verified:true,attestation_create_once_exact_reopened:true,
      outcome_artifacts_read:false,complete:true}'
  exit 0
fi

[[ $# -ge 4 ]] || die "usage: $0 {prepare|install|launch|result|task-manifest} ..."
action=$1
image=$2
code_sha=$3
build_id=$4
[[ "$action" =~ ^(prepare|install|launch|result|task-manifest)$ ]] || die "host action differs"
[[ "$image" =~ ^us-central1-docker\.pkg\.dev/${PROJECT}/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || \
  die "immutable image differs"
[[ "$code_sha" =~ ^[0-9a-f]{40}$ ]] || die "code SHA differs"
[[ "$build_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || \
  die "build ID differs"
root=$(git rev-parse --show-toplevel 2>/dev/null) || die "repository root absent"
require_exact_release_commit "$root" "$code_sha"
mkdir -p "$root/.build-contexts"
work=$(mktemp -d "$root/.build-contexts/paid-source-fp-sis-host.XXXXXX")
cleanup_host_release() { rm -rf "$work"; }
trap cleanup_host_release EXIT
digest=${image##*@}
image_tag="${image%@*}:paid-source-fp-sis-${code_sha}"
gcloud builds describe "$build_id" --project "$PROJECT" --format=json >"$work/build.json"
jq -e --arg id "$build_id" --arg sha "$code_sha" --arg tag "$image_tag" \
  --arg digest "$digest" --arg source "$SOURCE_REPOSITORY" '
  .id == $id and .status == "SUCCESS" and
  .source.gitSource == {url:$source,revision:$sha} and
  .sourceProvenance.resolvedGitSource == {url:$source,revision:$sha} and
  .substitutions._CODE_SHA == $sha and .substitutions._BUILD_IMAGE == $tag and
  .substitutions._SOURCE_REPOSITORY == $source and
  ([.results.images[]? | select(.name == $tag and .digest == $digest)] | length) == 1
' "$work/build.json" >/dev/null || die "build/image authority differs"
if [[ "$action" == "prepare" ]]; then
  [[ $# -eq 5 && "$5" == /* && -f "$5" && ! -L "$5" ]] || \
    die "prepare requires one absolute unaliased prepare input"
  "$root/.venv/bin/python" \
    "$root/scripts/run_corpus_r6_paid_source_fp_sis_v1.py" build-request \
    --input "$5" --code-sha "$code_sha" --immutable-image "$image" \
    --build-id "$build_id"
  exit 0
fi
gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format=json >"$work/job.json"
jq -e --arg uid "$EXPECTED_JOB_UID" '
  .metadata.uid == $uid and any(.status.conditions[]?;
    .type == "Ready" and .status == "True")
' "$work/job.json" >/dev/null || die "reused job identity/readiness differs"
latest=$(jq -er '.status.latestCreatedExecution.name' "$work/job.json") || \
  die "reused job latest execution absent"
gcloud run jobs executions describe "$latest" --project "$PROJECT" \
  --region "$REGION" --format=json >"$work/latest.json"
jq -e '
  any(.status.conditions[]?; .type == "Completed" and .status == "True") and
  (.status.failedCount // 0) == 0 and (.status.cancelledCount // 0) == 0 and
  (.status.runningCount // 0) == 0 and (.status.completionTime | type == "string")
' "$work/latest.json" >/dev/null || die "reused job is not terminal-success"

verify_installed_job() {
  [[ $# -eq 1 ]] || die "job verification requires one observation"
  jq -e --arg uid "$EXPECTED_JOB_UID" --arg image "$image" \
    --arg sha "$code_sha" --arg digest "$digest" --arg build "$build_id" \
    --arg sa "$SERVICE_ACCOUNT" --arg enable "$ENABLE_ENV" \
    --arg outcomes "$OUTCOMES_ENV" '
    .metadata.uid == $uid and .spec.template.spec.taskCount == 54 and
    .spec.template.spec.parallelism == 54 and
    .spec.template.spec.template.spec.maxRetries == 0 and
    .spec.template.spec.template.spec.serviceAccountName == $sa and
    (.spec.template.spec.template.spec.containers | length) == 1 and
    (.spec.template.spec.template.spec.containers[0] as $c |
      $c.image == $image and $c.command == ["/bin/bash"] and
      $c.args == ["/app/scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh","container-help"] and
      $c.resources.limits.cpu == "8" and $c.resources.limits.memory == "32Gi" and
      ([$c.env[] | select(.name == "CODE_SHA") | .value] == [$sha]) and
      ([$c.env[] | select(.name == "IMAGE_SOURCE_COMMIT_SHA") | .value] == [$sha]) and
      ([$c.env[] | select(.name == "IMAGE_DIGEST") | .value] == [$digest]) and
      ([$c.env[] | select(.name == "BUILD_ID") | .value] == [$build]) and
      ([$c.env[] | select(.name == "IMAGE_URI") | .value] == [$image]) and
      ([$c.env[] | select(.name == $enable) | .value] == ["DISABLED_INSTALL_ONLY"]) and
      ([$c.env[] | select(.name == $outcomes) | .value] == ["false"])
    )
  ' "$1" >/dev/null || die "installed reused-job template differs"
}

if [[ "$action" == "install" ]]; then
  [[ $# -eq 4 ]] || die "install accepts no payload"
  prior_generation=$(jq -er '.metadata.generation' "$work/job.json") || \
    die "prior job generation differs"
  gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
    --image "$image" --command /bin/bash \
    --args /app/scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh,container-help \
    --tasks 54 --parallelism 54 --max-retries 0 --cpu "$CPU" --memory "$MEMORY" \
    --task-timeout "$TASK_TIMEOUT" --service-account "$SERVICE_ACCOUNT" \
    --set-env-vars "CODE_SHA=$code_sha,IMAGE_SOURCE_COMMIT_SHA=$code_sha,IMAGE_DIGEST=$digest,BUILD_ID=$build_id,IMAGE_URI=$image,$ENABLE_ENV=DISABLED_INSTALL_ONLY,$OUTCOMES_ENV=false" \
    --quiet >/dev/null
  gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
    --format=json >"$work/job-after.json"
  verify_installed_job "$work/job-after.json"
  installed_generation=$(jq -er '.metadata.generation' "$work/job-after.json") || \
    die "installed job generation differs"
  [[ "$prior_generation" =~ ^[0-9]+$ && "$installed_generation" =~ ^[0-9]+$ && \
     "$installed_generation" -gt "$prior_generation" ]] || \
    die "reused job generation did not advance through installation"
  jq -n -cS --arg schema "corpus-r6-paid-source-fp-sis-install/v1" \
    --arg image "$image" --arg code "$code_sha" --arg build "$build_id" \
    --arg job "$JOB" --arg uid "$EXPECTED_JOB_UID" \
    --argjson generation "$installed_generation" '{
      schema_version:$schema,provider_resolved_image:$image,code_sha:$code,
      cloud_build_id:$build,reused_job:{name:$job,uid:$uid,generation:$generation},install_only:true,
      execution_launched:false,outcomes_allowed:false,complete:true}'
  exit 0
fi

execution_name=${5:-}
if [[ "$action" == "task-manifest" || "$action" == "result" ]]; then
  [[ $# -eq 5 && "$execution_name" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
    die "$action requires one exact execution"
  gcloud run jobs executions describe "$execution_name" --project "$PROJECT" \
    --region "$REGION" --format=json >"$work/execution.json"
  result_mode=$(jq -er '
    .spec.template.spec.containers[0].args as $args |
    if $args == ["/app/scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh","container-run","task0"] then "task0"
    elif $args == ["/app/scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh","container-run","task"] then "task"
    elif $args == ["/app/scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh","container-run","collect"] then "collect"
    elif $args == ["/app/scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh","container-run","reopen"] then "reopen"
    elif $args == ["/app/scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh","container-run","grade"] then "grade"
    elif $args == ["/app/scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh","container-run","grade-reopen"] then "grade-reopen"
    else error("execution mode differs") end
  ' "$work/execution.json") || die "result execution command differs"
  expected_tasks=1
  expected_outcomes=false
  if [[ "$action" == "task-manifest" ]]; then
    [[ "$result_mode" == "task" ]] || die "task manifest execution mode differs"
    expected_tasks=54
  else
    [[ "$result_mode" != "task" ]] || die "task execution requires task-manifest"
    [[ "$result_mode" == "grade" || "$result_mode" == "grade-reopen" ]] && \
      expected_outcomes=true
  fi
  jq -e --arg execution "$execution_name" --arg job "$JOB" \
    --arg uid "$EXPECTED_JOB_UID" --arg image "$image" \
    --arg sha "$code_sha" --arg digest "$digest" --arg build "$build_id" \
    --arg sa "$SERVICE_ACCOUNT" --arg mode "$result_mode" \
    --arg enable "$ENABLE_VALUE" --arg outcomes "$expected_outcomes" \
    --argjson tasks "$expected_tasks" '
    .metadata.name == $execution and .metadata.labels["run.googleapis.com/job"] == $job and
    .metadata.labels["run.googleapis.com/jobUid"] == $uid and .spec.taskCount == $tasks and
    (.metadata.labels["run.googleapis.com/jobGeneration"] | test("^[0-9]+$")) and
    .spec.template.spec.maxRetries == 0 and
    (.spec.template.spec.timeoutSeconds | tostring) == "21600" and
    .spec.template.spec.serviceAccountName == $sa and
    (.spec.template.spec.containers | length) == 1 and
    (.spec.template.spec.containers[0] as $c |
      $c.image == $image and $c.command == ["/bin/bash"] and
      $c.resources.limits.cpu == "8" and $c.resources.limits.memory == "32Gi" and
      ([$c.env[] | select(.name == "CODE_SHA") | .value] == [$sha]) and
      ([$c.env[] | select(.name == "IMAGE_SOURCE_COMMIT_SHA") | .value] == [$sha]) and
      ([$c.env[] | select(.name == "IMAGE_DIGEST") | .value] == [$digest]) and
      ([$c.env[] | select(.name == "BUILD_ID") | .value] == [$build]) and
      ([$c.env[] | select(.name == "IMAGE_URI") | .value] == [$image]) and
      ([$c.env[] | select(.name == "R6_PAID_SOURCE_FP_SIS_ENABLE") | .value] == [$enable]) and
      ([$c.env[] | select(.name == "R6_PAID_SOURCE_FP_SIS_OUTCOMES_ALLOWED") | .value] == [$outcomes]) and
      (([$c.env[] | select(.name == "R6_PAID_SOURCE_FP_SIS_REQUEST_SHA256") | .value]) | length) == 1 and
      (([$c.env[] | select(.name == "R6_PAID_SOURCE_FP_SIS_REQUEST_B64") | .value]) | length) == 1
      and ($mode != "task0" or
        ([$c.env[].name] | sort) == ([
          "BUILD_ID","CODE_SHA","IMAGE_DIGEST","IMAGE_SOURCE_COMMIT_SHA",
          "IMAGE_URI","R6_PAID_SOURCE_FP_SIS_ENABLE",
          "R6_PAID_SOURCE_FP_SIS_OUTCOMES_ALLOWED",
          "R6_PAID_SOURCE_FP_SIS_REQUEST_B64",
          "R6_PAID_SOURCE_FP_SIS_REQUEST_SHA256"
        ] | sort))
    ) and
    any(.status.conditions[]?; .type == "Completed" and .status == "True") and
    (.status.succeededCount // 0) == $tasks and (.status.failedCount // 0) == 0 and
    (.status.cancelledCount // 0) == 0 and (.status.runningCount // 0) == 0
  ' "$work/execution.json" >/dev/null || die "terminal execution differs"
  execution_request_b64=$(jq -er '[.spec.template.spec.containers[0].env[] |
    select(.name == "R6_PAID_SOURCE_FP_SIS_REQUEST_B64") | .value] |
    if length == 1 then .[0] else error("request b64 differs") end' \
    "$work/execution.json")
  execution_request_sha=$(jq -er '[.spec.template.spec.containers[0].env[] |
    select(.name == "R6_PAID_SOURCE_FP_SIS_REQUEST_SHA256") | .value] |
    if length == 1 then .[0] else error("request SHA differs") end' \
    "$work/execution.json")
  [[ "${#execution_request_b64}" -le "$MAX_ENV_B64_BYTES" && \
     "$execution_request_sha" =~ ^[0-9a-f]{64}$ ]] || \
    die "execution request envelope differs"
  printf '%s' "$execution_request_b64" | base64 --decode \
    >"$work/execution-request.json" || die "execution request base64 differs"
  [[ "$(sha256sum "$work/execution-request.json" | awk '{print $1}')" == \
     "$execution_request_sha" ]] || die "execution request bytes differ"
  filter="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$execution_name\" AND logName=\"projects/$PROJECT/logs/run.googleapis.com%2Fstdout\" AND textPayload:*"
  gcloud logging read "$filter" --project "$PROJECT" --limit 500 \
    --order=asc --format=json >"$work/logs.json"
  if [[ "$action" == "task-manifest" ]]; then
    rows=$(jq -cer '
      [.[] | .textPayload? | select(type == "string") | fromjson? |
       select(.schema_version == "corpus-r6-paid-source-fp-sis-slate-publication/v2")] |
      sort_by(.source_task_ordinal) as $rows |
      if ($rows|length) == 54 and
         ([$rows[].source_task_ordinal] == [range(0;54)]) and
         ([$rows[].complete] | all) then
        $rows
      else error("slate publication stdout lattice differs") end
    ' "$work/logs.json") || die "slate publication stdout lattice differs"
    rows_sha=$(printf '%s' "$rows" | sha256sum | awk '{print $1}')
    request_sha=$execution_request_sha
    [[ "$request_sha" =~ ^[0-9a-f]{64}$ ]] || die "task request SHA differs"
    jq -n -cS --argjson rows "$rows" --arg sha "$rows_sha" '{
      schema_version:"corpus-r6-paid-source-fp-sis-slate-publication-manifest/v1",
      slate_publications:$rows,slate_publication_manifest_sha256:$sha}'
  else
    case "$result_mode" in
      task0) result_schema=corpus-r6-paid-source-fp-sis-task0/v1 ;;
      collect) result_schema=corpus-r6-paid-source-fp-sis-score-free-terminal-result/v2 ;;
      reopen) result_schema=corpus-r6-paid-source-fp-sis-terminal-reopen/v2 ;;
      grade) result_schema=corpus-r6-paid-source-fp-sis-grade-result/v1 ;;
      grade-reopen) result_schema=corpus-r6-paid-source-fp-sis-grade-independent-reopen/v1 ;;
    esac
    result_raw=$(jq -er --arg schema "$result_schema" '
      [.[] | .textPayload? | select(type == "string") as $raw |
       ($raw | fromjson?) as $body |
       select($body.schema_version == $schema and $body.complete == true) | $raw] |
      if length == 1 then .[0] else error("operator result count differs") end
    ' "$work/logs.json") || die "operator result count differs"
    result_canonical=$(printf '%s' "$result_raw" | jq -cS .) || \
      die "operator result is not JSON"
    [[ "$result_raw" == "$result_canonical" ]] || \
      die "operator result is not canonical JSON"
    printf '%s' "$result_canonical" >"$work/operator-result.json"
    request_internal=$(jq -er '.execution_request_sha256 // empty' \
      "$work/execution-request.json" 2>/dev/null || true)
    case "$result_mode" in
      task0)
        jq -e --arg request "$request_internal" '
          .execution_request_sha256 == $request and
          .publication_performed == false and
          .publication_callback_present == false and
          .write_api_reachable_from_task0 == false and
          .runtime_principal_write_authority_status == "not-evaluated" and
          .full_cohort_execution_launched == false and
          .all_54_input_identities_frozen == true and
          .world_matrix_body_read_count == 1 and
          .recognized_outcome_callback_present == false and
          .runtime_principal_outcome_authority_status == "not-evaluated" and
          .outcome_artifacts_read == [] and
          .uses_realized_outcomes == false and
          .mechanical_launch_gate_passed == true
        ' "$work/operator-result.json" >/dev/null || die "task0 operator result differs"
        ;;
      collect)
        jq -e --arg request "$request_internal" '
          .execution_request_sha256 == $request and .slate_count == 54 and
          .all_54_score_free_slates_complete == true and
          .one_slate_per_task == true and
          .collector_matrix_body_read_count == 0 and
          .terminal_root_last == true and
          .outcomes_read_during_selection == false and
          .uses_realized_outcomes == false and
          .automatic_policy_promotion == false
        ' "$work/operator-result.json" >/dev/null || die "collect operator result differs"
        ;;
      reopen)
        jq -e '
          .slate_count == 54 and .all_children_generation_exact_reopened == true and
          .score_free_terminal_recomputed == true and .matrix_body_read_count == 0 and
          .publication_callback_present == false and
          .runtime_principal_write_authority_status == "not-evaluated" and
          .recognized_outcome_callback_present == false and
          .runtime_principal_outcome_authority_status == "not-evaluated" and
          .outcome_artifacts_read == [] and .uses_realized_outcomes == false
        ' "$work/operator-result.json" >/dev/null || die "reopen operator result differs"
        ;;
      grade)
        jq -e '
          .score_free_terminal_reopened_before_outcomes == true and
          .grade_create_once == true and .grade_exact_reopened == true and
          .automatic_policy_promotion == false and .uses_realized_outcomes == true
        ' "$work/operator-result.json" >/dev/null || die "grade operator result differs"
        ;;
      grade-reopen)
        jq -e '
          .persisted_derived_scores_replayed == true and
          .score_free_terminal_and_children_reopened == true and
          .recognized_outcome_completion_reread == false and
          .outcome_snapshot_reread == false and
          .historical_outcome_lease_reread == false and
          .grade_internal_aggregates_independently_recomputed == true and
          .automatic_policy_promotion == false and .uses_realized_outcomes == true
        ' "$work/operator-result.json" >/dev/null || die "grade reopen operator result differs"
        ;;
    esac
    request_sha=$execution_request_sha
    [[ "$request_sha" =~ ^[0-9a-f]{64}$ ]] || die "result request SHA differs"
    provider_spec_body=$(jq -cS --arg schema \
      "corpus-r6-paid-source-fp-sis-provider-execution-spec/v1" \
      --arg project "$PROJECT" --arg region "$REGION" --arg job "$JOB" \
      --arg request "$request_sha" --arg internal "$request_internal" \
      --arg mode "$result_mode" '
      . as $e | .spec.template.spec as $task |
      $task.containers[0] as $c |
      ($c.env | map({key:.name,value:.value}) | from_entries) as $env |
      {schema_version:$schema,provider:"google-cloud-run-v2-api",
       project_id:$project,region:$region,job_name:$job,
       job_uid:$e.metadata.labels["run.googleapis.com/jobUid"],
       job_generation:$e.metadata.labels["run.googleapis.com/jobGeneration"],
       execution_name:$e.metadata.name,execution_uid:$e.metadata.uid,
       service_account_name:$task.serviceAccountName,
       task_count:$e.spec.taskCount,max_retries:$task.maxRetries,
       timeout_seconds:($task.timeoutSeconds|tonumber),image:$c.image,
       command:$c.command,args:$c.args,cpu:$c.resources.limits.cpu,
       memory:$c.resources.limits.memory,
       environment_names:($c.env|map(.name)|sort),
       environment_bindings:{code_sha:$env.CODE_SHA,
         image_source_commit_sha:$env.IMAGE_SOURCE_COMMIT_SHA,
         image_digest:$env.IMAGE_DIGEST,build_id:$env.BUILD_ID,
         image_uri:$env.IMAGE_URI,
         enable_name:"R6_PAID_SOURCE_FP_SIS_ENABLE",
         enable_value:$env.R6_PAID_SOURCE_FP_SIS_ENABLE,
         outcomes_name:"R6_PAID_SOURCE_FP_SIS_OUTCOMES_ALLOWED",
         outcomes_allowed:($env.R6_PAID_SOURCE_FP_SIS_OUTCOMES_ALLOWED == "true"),
         request_b64_name:"R6_PAID_SOURCE_FP_SIS_REQUEST_B64",
         request_sha256_name:"R6_PAID_SOURCE_FP_SIS_REQUEST_SHA256",
         request_sha256:$env.R6_PAID_SOURCE_FP_SIS_REQUEST_SHA256,
         execution_request_sha256:$internal},
       request_payload_sha256:$request,
       creation_time:$e.metadata.creationTimestamp,
       start_time:$e.status.startTime,completion_time:$e.status.completionTime,
       provider_observed_from_execution_describe:true,
       uses_realized_outcomes:($mode == "grade" or $mode == "grade-reopen")}
    ' "$work/execution.json") || die "provider execution spec projection differs"
    provider_spec_sha=$(printf '%s' "$provider_spec_body" | sha256sum | awk '{print $1}')
    provider_spec=$(jq -n -cS --argjson body "$provider_spec_body" \
      --arg sha "$provider_spec_sha" '$body + {provider_execution_spec_sha256:$sha}')
    jq -n -cS --arg schema "corpus-r6-paid-source-fp-sis-cloud-result/v1" \
      --arg mode "$result_mode" --arg code "$code_sha" --arg build "$build_id" \
      --arg image "$image" --arg execution "$execution_name" \
      --arg execution_uid "$(jq -er '.metadata.uid' "$work/execution.json")" \
      --arg creation_time "$(jq -er '.metadata.creationTimestamp' "$work/execution.json")" \
      --arg start_time "$(jq -er '.status.startTime' "$work/execution.json")" \
      --arg completion_time "$(jq -er '.status.completionTime' "$work/execution.json")" \
      --arg request "$request_sha" --argjson receipt "$result_canonical" \
      --argjson provider_spec "$provider_spec" '{
        schema_version:$schema,mode:$mode,code_sha:$code,cloud_build_id:$build,
        provider_resolved_image:$image,execution:{name:$execution,uid:$execution_uid,
          task_count:1,succeeded_count:1,failed_count:0,cancelled_count:0,
          running_count:0,creation_time:$creation_time,start_time:$start_time,
          completion_time:$completion_time},provider_execution_spec:$provider_spec,
        request_sha256:$request,operator_receipt:$receipt,
        exact_execution_stdout_only:true,
        task0_provider_gate_eligible:($mode == "task0"),
        outcome_artifacts_read:(if $mode == "task0" then [] else null end),
        complete:true}'
  fi
  exit 0
fi

[[ "$action" == "launch" && $# -ge 6 ]] || die "launch arguments differ"
mode=$5
request_path=$6
task0_execution=${7:-}
publications_path=${8:-}
task_execution=${9:-}
case "$mode" in
  task0|reopen|grade|grade-reopen) [[ $# -eq 6 ]] || die "$mode launch arguments differ" ;;
  task) [[ $# -eq 7 ]] || die "task launch requires request and exact task0 execution" ;;
  collect) [[ $# -eq 9 ]] || die "collect launch requires request, exact task0 execution, publications, and exact task execution" ;;
  *) die "launch mode differs" ;;
esac
verify_installed_job "$work/job.json"
[[ "$request_path" == /* && -f "$request_path" && ! -L "$request_path" ]] || \
  die "request path differs"
if [[ "$mode" =~ ^(task0|task|collect)$ ]]; then
  "$root/.venv/bin/python" "$root/scripts/run_corpus_r6_paid_source_fp_sis_v1.py" \
    validate --request "$request_path" >/dev/null || die "execution request differs"
  jq -e --arg code "$code_sha" --arg image "$image" --arg build "$build_id" '
    .code_sha == $code and .immutable_image == $image and .build_id == $build
  ' "$request_path" >/dev/null || die "request release binding differs"
else
  case "$mode" in
    reopen) expected_request_schema=corpus-r6-paid-source-fp-sis-terminal-reopen-request/v1 ;;
    grade) expected_request_schema=corpus-r6-paid-source-fp-sis-grade-request/v1 ;;
    grade-reopen) expected_request_schema=corpus-r6-paid-source-fp-sis-grade-reopen-request/v1 ;;
  esac
  jq -e --arg schema "$expected_request_schema" --arg code "$code_sha" \
    --arg image "$image" --arg digest "$digest" '
    .schema_version == $schema and .code_sha == $code and
    .immutable_image == $image and .image_digest == $digest
  ' "$request_path" >/dev/null || die "$mode request release binding differs"
fi
request_sha=$(sha256sum "$request_path" | awk '{print $1}')
request_b64=$(base64 -w0 "$request_path")
[[ "${#request_b64}" -le "$MAX_ENV_B64_BYTES" ]] || \
  die "request exceeds override ceiling"
tasks=1
outcomes=false
task0_sha=
task0_b64=
task0_gate_sha=
task0_gate_b64=
task0_execution_uid=
task0_completion_time=
task0_provider_spec_sha=
publications_sha=
publications_b64=
if [[ "$mode" == "task" || "$mode" == "collect" ]]; then
  [[ "$task0_execution" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
    die "task0 authority differs"
  task0_result="$work/task0-result.json"
  "$0" result "$image" "$code_sha" "$build_id" "$task0_execution" >"$task0_result"
  "$root/.venv/bin/python" "$root/scripts/run_corpus_r6_paid_source_fp_sis_v1.py" \
    validate-task0-cloud-gate --request "$request_path" \
    --cloud-result "$task0_result" \
    --request-file-sha256 "$request_sha" --code-sha "$code_sha" \
    --immutable-image "$image" --build-id "$build_id" \
    --task0-execution "$task0_execution" >/dev/null || \
    die "task0 provider gate differs from exact execution"
  task0_path="$work/task0-receipt.json"
  jq -cS '.operator_receipt' "$task0_result" >"$task0_path" || \
    die "exact task0 receipt extraction failed"
  task0_sha=$(sha256sum "$task0_path" | awk '{print $1}')
  task0_b64=$(base64 -w0 "$task0_path")
  task0_gate_sha=$(sha256sum "$task0_result" | awk '{print $1}')
  task0_gate_b64=$(base64 -w0 "$task0_result")
  task0_execution_uid=$(jq -er '.execution.uid' "$task0_result")
  task0_completion_time=$(jq -er '.execution.completion_time' "$task0_result")
  task0_provider_spec_sha=$(jq -er \
    '.provider_execution_spec.provider_execution_spec_sha256' "$task0_result")
  [[ "${#task0_b64}" -le "$MAX_ENV_B64_BYTES" && \
     "${#task0_gate_b64}" -le "$MAX_ENV_B64_BYTES" && \
     "$task0_gate_sha" =~ ^[0-9a-f]{64}$ && \
     "$task0_provider_spec_sha" =~ ^[0-9a-f]{64}$ ]] || \
    die "task0 exact receipt/provider gate exceeds override ceiling"
  [[ "$mode" == "task" ]] && tasks=54
fi
if [[ "$mode" == "collect" ]]; then
  [[ "$publications_path" == /* && -f "$publications_path" && \
     ! -L "$publications_path" ]] || die "publication manifest path differs"
  publications_sha=$(sha256sum "$publications_path" | awk '{print $1}')
  publications_b64=$(gzip -n -9 -c "$publications_path" | base64 -w0)
  [[ "${#publications_b64}" -le "$MAX_ENV_B64_BYTES" && \
     "$task_execution" =~ ^${JOB}-[a-z0-9]{5}$ ]] || \
    die "publication manifest/task execution envelope differs"
  derived_publications="$work/exact-task-publications.json"
  "$0" task-manifest "$image" "$code_sha" "$build_id" "$task_execution" \
    >"$derived_publications"
  jq -e --argjson expected "$(jq -cS . "$publications_path")" \
    '. == $expected' "$derived_publications" >/dev/null || \
    die "publication manifest differs from exact 54-task execution"
  gcloud run jobs executions describe "$task_execution" --project "$PROJECT" \
    --region "$REGION" --format=json >"$work/task-execution.json"
  jq -e --arg request "$request_sha" --arg receipt "$task0_sha" \
    --arg gate "$task0_gate_sha" '
    .spec.template.spec.containers[0].args ==
      ["/app/scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh","container-run","task"] and
    ([.spec.template.spec.containers[0].env[] |
      select(.name == "R6_PAID_SOURCE_FP_SIS_REQUEST_SHA256") | .value] == [$request]) and
    ([.spec.template.spec.containers[0].env[] |
      select(.name == "R6_PAID_SOURCE_FP_SIS_TASK0_RECEIPT_SHA256") | .value] == [$receipt])
    and ([.spec.template.spec.containers[0].env[] |
      select(.name == "R6_PAID_SOURCE_FP_SIS_TASK0_PROVIDER_GATE_SHA256") | .value] == [$gate])
  ' "$work/task-execution.json" >/dev/null || \
    die "54-task execution request/task0 provider binding differs"
fi
[[ "$mode" == "grade" || "$mode" == "grade-reopen" ]] && outcomes=true
envs="^|^$ENABLE_ENV=$ENABLE_VALUE|$OUTCOMES_ENV=$outcomes|CODE_SHA=$code_sha|IMAGE_SOURCE_COMMIT_SHA=$code_sha|IMAGE_DIGEST=$digest|BUILD_ID=$build_id|IMAGE_URI=$image|$REQUEST_SHA_ENV=$request_sha|$REQUEST_B64_ENV=$request_b64"
if [[ "$mode" == "task" || "$mode" == "collect" ]]; then
  envs="$envs|$TASK0_SHA_ENV=$task0_sha|$TASK0_B64_ENV=$task0_b64|$TASK0_GATE_SHA_ENV=$task0_gate_sha|$TASK0_GATE_B64_ENV=$task0_gate_b64"
fi
if [[ "$mode" == "collect" ]]; then
  envs="$envs|$PUBLICATIONS_SHA_ENV=$publications_sha|$PUBLICATIONS_B64_ENV=$publications_b64"
fi
gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --tasks "$tasks" \
  --args "/app/scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh,container-run,$mode" \
  --update-env-vars "$envs" --async --format=json >"$work/launch.json"
launched=$(jq -er '.metadata.name' "$work/launch.json") || die "execution name absent"
[[ "$launched" =~ ^${JOB}-[a-z0-9]{5}$ ]] || die "execution name differs"
gcloud run jobs executions describe "$launched" --project "$PROJECT" \
  --region "$REGION" --format=json >"$work/launched-execution.json"
job_generation=$(jq -er '.metadata.generation' "$work/job.json") || \
  die "installed job generation differs"
jq -e --arg execution "$launched" --arg job "$JOB" \
  --arg uid "$EXPECTED_JOB_UID" --arg generation "$job_generation" \
  --arg image "$image" --arg mode "$mode" --arg sa "$SERVICE_ACCOUNT" \
  --arg sha "$code_sha" --arg digest "$digest" --arg build "$build_id" \
  --arg request "$request_sha" --arg outcomes "$outcomes" \
  --arg enable "$ENABLE_VALUE" --arg task0 "$task0_sha" \
  --arg task0_gate "$task0_gate_sha" \
  --arg publications "$publications_sha" --argjson tasks "$tasks" '
  .metadata.name == $execution and
  .metadata.labels["run.googleapis.com/job"] == $job and
  .metadata.labels["run.googleapis.com/jobUid"] == $uid and
  .metadata.labels["run.googleapis.com/jobGeneration"] == $generation and
  .spec.taskCount == $tasks and .spec.template.spec.maxRetries == 0 and
  (.spec.template.spec.timeoutSeconds | tostring) == "21600" and
  .spec.template.spec.serviceAccountName == $sa and
  (.spec.template.spec.containers | length) == 1 and
  (.spec.template.spec.containers[0] as $c |
    $c.image == $image and $c.command == ["/bin/bash"] and
    $c.args == ["/app/scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh","container-run",$mode] and
    $c.resources.limits.cpu == "8" and $c.resources.limits.memory == "32Gi" and
    ([$c.env[] | select(.name == "CODE_SHA") | .value] == [$sha]) and
    ([$c.env[] | select(.name == "IMAGE_SOURCE_COMMIT_SHA") | .value] == [$sha]) and
    ([$c.env[] | select(.name == "IMAGE_DIGEST") | .value] == [$digest]) and
    ([$c.env[] | select(.name == "BUILD_ID") | .value] == [$build]) and
    ([$c.env[] | select(.name == "IMAGE_URI") | .value] == [$image]) and
    ([$c.env[] | select(.name == "R6_PAID_SOURCE_FP_SIS_ENABLE") | .value] == [$enable]) and
    ([$c.env[] | select(.name == "R6_PAID_SOURCE_FP_SIS_OUTCOMES_ALLOWED") | .value] == [$outcomes]) and
    ([$c.env[] | select(.name == "R6_PAID_SOURCE_FP_SIS_REQUEST_SHA256") | .value] == [$request]) and
    (([$c.env[] | select(.name == "R6_PAID_SOURCE_FP_SIS_REQUEST_B64") | .value] | length) == 1) and
    (($mode != "task" and $mode != "collect") or
      ([$c.env[] | select(.name == "R6_PAID_SOURCE_FP_SIS_TASK0_RECEIPT_SHA256") | .value] == [$task0])) and
    (($mode != "task" and $mode != "collect") or
      (([$c.env[] | select(.name == "R6_PAID_SOURCE_FP_SIS_TASK0_RECEIPT_B64") | .value] | length) == 1)) and
    (($mode != "task" and $mode != "collect") or
      ([$c.env[] | select(.name == "R6_PAID_SOURCE_FP_SIS_TASK0_PROVIDER_GATE_SHA256") | .value] == [$task0_gate])) and
    (($mode != "task" and $mode != "collect") or
      (([$c.env[] | select(.name == "R6_PAID_SOURCE_FP_SIS_TASK0_PROVIDER_GATE_B64") | .value] | length) == 1)) and
    ($mode != "collect" or
      ([$c.env[] | select(.name == "R6_PAID_SOURCE_FP_SIS_SLATE_PUBLICATIONS_SHA256") | .value] == [$publications])) and
    ($mode != "collect" or
      (([$c.env[] | select(.name == "R6_PAID_SOURCE_FP_SIS_SLATE_PUBLICATIONS_GZIP_B64") | .value] | length) == 1)) and
    ([$c.env[].name] | sort) == (([
      "BUILD_ID","CODE_SHA","IMAGE_DIGEST","IMAGE_SOURCE_COMMIT_SHA",
      "IMAGE_URI","R6_PAID_SOURCE_FP_SIS_ENABLE",
      "R6_PAID_SOURCE_FP_SIS_OUTCOMES_ALLOWED",
      "R6_PAID_SOURCE_FP_SIS_REQUEST_B64",
      "R6_PAID_SOURCE_FP_SIS_REQUEST_SHA256"
    ] + (if $mode == "task" or $mode == "collect" then [
      "R6_PAID_SOURCE_FP_SIS_TASK0_PROVIDER_GATE_B64",
      "R6_PAID_SOURCE_FP_SIS_TASK0_PROVIDER_GATE_SHA256",
      "R6_PAID_SOURCE_FP_SIS_TASK0_RECEIPT_B64",
      "R6_PAID_SOURCE_FP_SIS_TASK0_RECEIPT_SHA256"
    ] else [] end) + (if $mode == "collect" then [
      "R6_PAID_SOURCE_FP_SIS_SLATE_PUBLICATIONS_GZIP_B64",
      "R6_PAID_SOURCE_FP_SIS_SLATE_PUBLICATIONS_SHA256"
    ] else [] end)) | sort)
  )
' "$work/launched-execution.json" >/dev/null || die "launched execution binding differs"
execution_uid=$(jq -er '.metadata.uid' "$work/launched-execution.json") || \
  die "execution UID differs"
jq -n -cS --arg schema "corpus-r6-paid-source-fp-sis-launch/v1" \
  --arg mode "$mode" --arg image "$image" --arg code "$code_sha" \
  --arg build "$build_id" --arg execution "$launched" \
  --arg execution_uid "$execution_uid" --argjson tasks "$tasks" \
  --arg request "$request_sha" --arg task0 "$task0_sha" \
  --arg task0_gate "$task0_gate_sha" \
  --arg task0_execution "$task0_execution" --arg publications "$publications_sha" \
  --arg task0_execution_uid "$task0_execution_uid" \
  --arg task0_completion_time "$task0_completion_time" \
  --arg task0_provider_spec_sha "$task0_provider_spec_sha" \
  --arg task_execution "$task_execution" '{schema_version:$schema,mode:$mode,
    provider_resolved_image:$image,code_sha:$code,cloud_build_id:$build,
    execution:{name:$execution,uid:$execution_uid,task_count:$tasks},request_sha256:$request,
    task0_receipt_sha256:(if $task0 == "" then null else $task0 end),
    task0_provider_gate_sha256:(if $task0_gate == "" then null else $task0_gate end),
    task0_provider_authority:(if $task0_execution == "" then null else {
      name:$task0_execution,uid:$task0_execution_uid,
      completion_time:$task0_completion_time,
      provider_execution_spec_sha256:$task0_provider_spec_sha} end),
    slate_publication_manifest_sha256:(if $publications == "" then null else $publications end),
    source_task_execution:(if $task_execution == "" then null else $task_execution end),
    exact_task0_execution_required:($mode=="task" or $mode=="collect"),
    outcomes_allowed:($mode=="grade" or $mode=="grade-reopen"),complete:true}'
