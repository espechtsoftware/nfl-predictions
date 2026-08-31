#!/usr/bin/env bash
# One-use launcher for the d594 collector validation repair.  This script is
# intentionally separate from the generic construction launcher: only the
# exact known 29lvz failure can open the collect path, and only that successful
# collect coordinate can open the independent reopen path.
set -euo pipefail

die() { printf '%s\n' "ERROR: $*" >&2; exit 2; }

[[ $# -ge 5 ]] || die \
  "usage: $0 {collect|reopen} REPAIR_IMAGE@sha256:DIGEST REPAIR_CODE_SHA REPAIR_BUILD_ID BUILD_ATTESTATION_IDENTITY_JSON [PRIOR_COLLECT_NAME PRIOR_COLLECT_UID]"

ACTION=$1
IMAGE=$2
CODE_SHA=$3
BUILD_ID=$4
BUILD_ATTESTATION_PATH=$5
PRIOR_NAME=${6:-}
PRIOR_UID=${7:-}

PROJECT=nfl-predictions-503414
REGION=us-central1
JOB=atlas-cbc-32g-full-2023-w8-v1
JOB_UID=1f4bcf0a-2300-4afa-9fc1-9981844c8275
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
FAILED_NAME=atlas-cbc-32g-full-2023-w8-v1-29lvz
FAILED_UID=7cf1f35f-9c99-41ce-bd66-c78af15cc412
FAILED_COMPLETION=2026-08-31T02:25:33.731980Z
SOURCE_CODE_SHA=d5946133ebba0955586816c15905065c3ec71a0f
SOURCE_IMAGE_DIGEST=sha256:e8959e94cf41f0a0f63bf97d4631e0c7c799af7594675a0f037ed7625a2280a7
SOURCE_IMAGE="us-central1-docker.pkg.dev/${PROJECT}/nfl-dfs/nfl-dfs@${SOURCE_IMAGE_DIGEST}"
MANIFEST_IDENTITY='{"bytes":60541,"generation":"1788111932751802","sha256":"bbe47919f0dd753f8f7278f5f3d3e022bd70c2879c3f826dcd31e207ab1d4536","uri":"gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-construction-allocation-snapshot-shards/20260830-construction-allocation-d5946133-v1/input-manifest.json"}'
SELECTION_URI=gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-construction-allocation-snapshot-shards/20260830-construction-allocation-d5946133-v1/selection.json
TERMINAL_URI=gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-construction-allocation-snapshot-shards/20260830-construction-allocation-d5946133-v1/terminal.json
RECEIPT_URI=gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-construction-allocation-snapshot-shards/20260830-construction-allocation-d5946133-v1/collector-repair-receipt-v1.json
ENABLE_ENV=R6_CONSTRUCTION_ALLOCATION_COLLECTOR_REPAIR_ENABLE
ENABLE_VALUE=I_UNDERSTAND_D594_COLLECTOR_REPAIR_V1
SOURCE_ENABLE_ENV=R6_CONSTRUCTION_ALLOCATION_SNAPSHOT_SHARD_ENABLE
SOURCE_ENABLE_VALUE=I_UNDERSTAND_SCORE_BLIND_CONSTRUCTION_CROSS_V1
MANIFEST_ENV=R6_CONSTRUCTION_ALLOCATION_SNAPSHOT_SHARD_MANIFEST_IDENTITY
REQUEST_B64_ENV=R6_CONSTRUCTION_ALLOCATION_COLLECTOR_REPAIR_REQUEST_B64
REQUEST_SHA_ENV=R6_CONSTRUCTION_ALLOCATION_COLLECTOR_REPAIR_REQUEST_SHA256

[[ "$ACTION" =~ ^(collect|reopen)$ ]] || die "repair action differs"
[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/${PROJECT}/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || \
  die "repair image must be one immutable project image"
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ && "$CODE_SHA" != "$SOURCE_CODE_SHA" ]] || \
  die "repair code must be one new exact commit"
[[ "$BUILD_ID" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || \
  die "repair build ID differs"
[[ "$BUILD_ATTESTATION_PATH" == /* && -f "$BUILD_ATTESTATION_PATH" && ! -L "$BUILD_ATTESTATION_PATH" ]] || \
  die "repair build-attestation identity must be one absolute regular file"
if [[ "$ACTION" == collect ]]; then
  [[ $# -eq 5 ]] || die "initial repair collect accepts no predecessor"
else
  [[ $# -eq 7 && "$PRIOR_NAME" =~ ^${JOB}-[a-z0-9]{5}$ && -n "$PRIOR_UID" ]] || \
    die "repair reopen requires the exact successful collect name and UID"
fi

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || die "repository root unavailable"
[[ "$(git -C "$ROOT" rev-parse HEAD)" == "$CODE_SHA" ]] || die "repair code must equal HEAD"
[[ "$(git -C "$ROOT" rev-parse --verify 'refs/remotes/origin/main^{commit}')" == "$CODE_SHA" ]] || \
  die "repair code must equal durable origin/main"
[[ -z "$(git -C "$ROOT" status --porcelain --untracked-files=all)" ]] || \
  die "repair launch checkout must be clean"
for path in \
  scripts/run_corpus_r6_construction_allocation_collector_repair_v1.py \
  src/nfl_dfs/research/corpus_r6_construction_allocation_collector_repair_v1.py \
  src/nfl_dfs/research/corpus_r6_construction_allocation_cross_operator_v1.py; do
  git -C "$ROOT" cat-file -e "${CODE_SHA}:${path}" || die "repair release file absent: $path"
done

temp_dir=$(mktemp -d /tmp/construction-allocation-collector-repair.XXXXXX)
trap 'rm -rf "$temp_dir"' EXIT
build_json=$temp_dir/build.json
job_before=$temp_dir/job-before.json
job_after=$temp_dir/job-after.json
latest_json=$temp_dir/latest.json
execution_json=$temp_dir/execution.json
request_json=$temp_dir/request.json
launch_json=$temp_dir/launch.json
object_stderr=$temp_dir/object-stderr.log
image_digest=${IMAGE##*@}
image_tag="${IMAGE%@*}:construction-allocation-${CODE_SHA}"

gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format=json >"$build_json"
jq -e --arg build "$BUILD_ID" --arg sha "$CODE_SHA" --arg tag "$image_tag" \
  --arg digest "$image_digest" '
  .id == $build and .status == "SUCCESS" and
  .substitutions._CODE_SHA == $sha and .substitutions._BUILD_IMAGE == $tag and
  any(.results.images[]?; .name == $tag and .digest == $digest)
' "$build_json" >/dev/null || die "repair Cloud Build authority differs"

build_attestation=$(jq -cS . "$BUILD_ATTESTATION_PATH")
jq -e --arg sha "$CODE_SHA" --arg digest "$image_digest" '
  (keys | sort) == (["bytes","generation","sha256","uri"] | sort) and
  (.uri | startswith("gs://")) and (.generation | type == "string" and length > 0) and
  (.sha256 | test("^[0-9a-f]{64}$")) and (.bytes | type == "number" and . > 0)
' "$BUILD_ATTESTATION_PATH" >/dev/null || die "repair build-attestation identity differs"

known_name_absent() {
  local uri=$1
  if gcloud storage objects describe "$uri" --project "$PROJECT" --format=json \
      >"$temp_dir/object.json" 2>"$object_stderr"; then
    die "known create-once name is not absent: $uri"
  fi
  grep -Eqi 'not[ -]?found|404|No URLs matched' "$object_stderr" || \
    die "known-name absence check was inconclusive: $uri"
}

gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format=json >"$job_before"
jq -e --arg uid "$JOB_UID" '.metadata.uid == $uid' "$job_before" >/dev/null || \
  die "reused job identity differs"
latest=$(jq -er '.status.latestCreatedExecution.name' "$job_before") || \
  die "reused job latest execution is absent"
gcloud run jobs executions describe "$latest" --project "$PROJECT" --region "$REGION" \
  --format=json >"$latest_json"

if [[ "$ACTION" == collect ]]; then
  [[ "$latest" == "$FAILED_NAME" ]] || die "repair collect latest execution is not the admitted failure"
  jq -e --arg name "$FAILED_NAME" --arg uid "$FAILED_UID" --arg job "$JOB" \
    --arg job_uid "$JOB_UID" --arg completion "$FAILED_COMPLETION" \
    --arg source_code "$SOURCE_CODE_SHA" --arg source_image "$SOURCE_IMAGE" '
    .metadata.name == $name and .metadata.uid == $uid and
    .metadata.labels["run.googleapis.com/job"] == $job and
    .metadata.labels["run.googleapis.com/jobUid"] == $job_uid and
    .metadata.labels["run.googleapis.com/jobGeneration"] == "42" and
    .spec.taskCount == 1 and .status.failedCount == 1 and
    .status.completionTime == $completion and
    any(.status.conditions[]?; .type == "Completed" and .status == "False" and .reason == "NonZeroExitCode") and
    (.spec.template.spec.containers | length) == 1 and
    (.spec.template.spec.containers[0] as $c |
      $c.image == $source_image and
      ([ $c.env[] | select(.name == "CODE_SHA") | .value ] == [$source_code]))
  ' "$latest_json" >/dev/null || die "known failed collect provider facts differ"
  known_name_absent "$SELECTION_URI"
  known_name_absent "$TERMINAL_URI"
  known_name_absent "$RECEIPT_URI"
else
  [[ "$latest" == "$PRIOR_NAME" ]] || die "repair reopen latest execution is not its named collect"
  jq -e --arg name "$PRIOR_NAME" --arg uid "$PRIOR_UID" --arg image "$IMAGE" \
    --arg code "$CODE_SHA" '
    .metadata.name == $name and .metadata.uid == $uid and .spec.taskCount == 1 and
    (.status.succeededCount == 1) and ((.status.failedCount // 0) == 0) and
    any(.status.conditions[]?; .type == "Completed" and .status == "True") and
    (.spec.template.spec.containers | length) == 1 and
    (.spec.template.spec.containers[0] as $c |
      $c.image == $image and
      ([ $c.env[] | select(.name == "R6_COLLECTOR_REPAIR_CODE_SHA") | .value ] == [$code]))
  ' "$latest_json" >/dev/null || die "repair collect predecessor differs"
  gcloud storage objects describe "$SELECTION_URI" --project "$PROJECT" --format=json \
    >/dev/null || die "repair reopen selection predecessor is absent"
  gcloud storage objects describe "$TERMINAL_URI" --project "$PROJECT" --format=json \
    >/dev/null || die "repair reopen terminal predecessor is absent"
  known_name_absent "$RECEIPT_URI"
fi

if [[ "$ACTION" == collect ]]; then
  gcloud run jobs update "$JOB" --project "$PROJECT" --region "$REGION" \
    --image "$IMAGE" --command /usr/local/bin/python3.11 \
    --args /app/scripts/run_corpus_r6_construction_allocation_collector_repair_v1.py,--help \
    --tasks 54 --parallelism 4 --max-retries 0 --cpu 8 --memory 32Gi \
    --task-timeout 21600s --service-account "$SERVICE_ACCOUNT" \
    --set-env-vars "CODE_SHA=$CODE_SHA,IMAGE_DIGEST=$image_digest,BUILD_ID=$BUILD_ID,$ENABLE_ENV=DISABLED_INSTALL_ONLY" \
    --quiet >/dev/null
fi
gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format=json >"$job_after"
jq -e --arg uid "$JOB_UID" --arg image "$IMAGE" --arg code "$CODE_SHA" \
  --arg digest "$image_digest" --arg build "$BUILD_ID" --arg sa "$SERVICE_ACCOUNT" '
  .metadata.uid == $uid and .spec.template.spec.taskCount == 54 and
  .spec.template.spec.parallelism == 4 and
  .spec.template.spec.template.spec.maxRetries == 0 and
  .spec.template.spec.template.spec.serviceAccountName == $sa and
  (.spec.template.spec.template.spec.containers | length) == 1 and
  (.spec.template.spec.template.spec.containers[0] as $c |
    $c.image == $image and $c.command == ["/usr/local/bin/python3.11"] and
    $c.args == ["/app/scripts/run_corpus_r6_construction_allocation_collector_repair_v1.py","--help"] and
    ([ $c.env[] | select(.name == "CODE_SHA") | .value ] == [$code]) and
    ([ $c.env[] | select(.name == "IMAGE_DIGEST") | .value ] == [$digest]) and
    ([ $c.env[] | select(.name == "BUILD_ID") | .value ] == [$build]))
' "$job_after" >/dev/null || die "installed repair job differs"

prior_json=null
if [[ "$ACTION" == reopen ]]; then
  prior_json=$(jq -cnS --arg name "$PRIOR_NAME" --arg uid "$PRIOR_UID" \
    '{phase:"collect",execution_name:$name,execution_uid:$uid}')
fi
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/src:$ROOT/scripts" \
  "$ROOT/.venv/bin/python" -c '
import json,sys
from pathlib import Path
from nfl_dfs.research import corpus_r6_construction_allocation_collector_repair_v1 as r
phase, identity_path, prior_json = sys.argv[1:]
identity=json.loads(Path(identity_path).read_bytes())
prior=None if prior_json == "null" else json.loads(prior_json)
sys.stdout.buffer.write(r.canonical_bytes(r.request_v1(
    phase=phase,
    collector_runtime_build_attestation_identity=identity,
    prior_repair_execution=prior,
), newline=True))
' "$ACTION" "$BUILD_ATTESTATION_PATH" "$prior_json" >"$request_json"

request_sha=$(sha256sum "$request_json" | awk '{print $1}')
request_b64=$(base64 -w0 "$request_json")
env_override="^|^CODE_SHA=$CODE_SHA|IMAGE_DIGEST=$image_digest|BUILD_ID=$BUILD_ID|$ENABLE_ENV=$ENABLE_VALUE|$SOURCE_ENABLE_ENV=$SOURCE_ENABLE_VALUE|$MANIFEST_ENV=$MANIFEST_IDENTITY|$REQUEST_SHA_ENV=$request_sha|$REQUEST_B64_ENV=$request_b64|R6_COLLECTOR_REPAIR_CODE_SHA=$CODE_SHA|R6_COLLECTOR_REPAIR_IMAGE=$IMAGE|R6_COLLECTOR_REPAIR_BUILD_ID=$BUILD_ID|R6_COLLECTOR_REPAIR_BUILD_ATTESTATION_IDENTITY=$build_attestation|R6_CONSTRUCTION_ALLOCATION_COLLECTOR_REPAIR_PHASE=$ACTION|R6_CONSTRUCTION_ALLOCATION_FULL_IMAGE=$IMAGE|R6_CONSTRUCTION_ALLOCATION_TARGET_OUTCOMES_ALLOWED=false|R6_CONSTRUCTION_ALLOCATION_NO_OUTCOME_SMOKE=false"

gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --tasks 1 \
  --args /app/scripts/run_corpus_r6_construction_allocation_collector_repair_v1.py,container-collect,--execute \
  --update-env-vars "$env_override" --async --format=json >"$launch_json"
execution_name=$(jq -er '.metadata.name' "$launch_json") || die "repair launch name is absent"
gcloud run jobs executions describe "$execution_name" --project "$PROJECT" \
  --region "$REGION" --format=json >"$execution_json"
execution_uid=$(jq -er '.metadata.uid' "$execution_json") || die "repair execution UID is absent"
job_generation=$(jq -er '.metadata.generation' "$job_after") || die "repair job generation is absent"
jq -e --arg name "$execution_name" --arg uid "$execution_uid" --arg job "$JOB" \
  --arg job_uid "$JOB_UID" --arg generation "$job_generation" --arg image "$IMAGE" \
  --arg code "$CODE_SHA" --arg build "$BUILD_ID" --arg phase "$ACTION" \
  --arg request_sha "$request_sha" '
  .metadata.name == $name and .metadata.uid == $uid and
  .metadata.labels["run.googleapis.com/job"] == $job and
  .metadata.labels["run.googleapis.com/jobUid"] == $job_uid and
  .metadata.labels["run.googleapis.com/jobGeneration"] == $generation and
  .spec.taskCount == 1 and .spec.template.spec.maxRetries == 0 and
  (.spec.template.spec.containers | length) == 1 and
  (.spec.template.spec.containers[0] as $c |
    $c.image == $image and $c.command == ["/usr/local/bin/python3.11"] and
    $c.args == ["/app/scripts/run_corpus_r6_construction_allocation_collector_repair_v1.py","container-collect","--execute"] and
    ([ $c.env[] | select(.name == "R6_COLLECTOR_REPAIR_CODE_SHA") | .value ] == [$code]) and
    ([ $c.env[] | select(.name == "R6_COLLECTOR_REPAIR_BUILD_ID") | .value ] == [$build]) and
    ([ $c.env[] | select(.name == "R6_CONSTRUCTION_ALLOCATION_COLLECTOR_REPAIR_PHASE") | .value ] == [$phase]) and
    ([ $c.env[] | select(.name == "R6_CONSTRUCTION_ALLOCATION_COLLECTOR_REPAIR_REQUEST_SHA256") | .value ] == [$request_sha]) and
    ([ $c.env[] | select(.name == "R6_CONSTRUCTION_ALLOCATION_TARGET_OUTCOMES_ALLOWED") | .value ] == ["false"]))
' "$execution_json" >/dev/null || die "repair execution provider authority differs"

jq -n --arg schema corpus-r6-construction-allocation-collector-repair-launch/v1 \
  --arg phase "$ACTION" --arg code_sha "$CODE_SHA" --arg build_id "$BUILD_ID" \
  --arg image "$IMAGE" --arg job "$JOB" --arg job_uid "$JOB_UID" \
  --arg job_generation "$job_generation" --arg execution "$execution_name" \
  --arg execution_uid "$execution_uid" --arg request_sha "$request_sha" \
  --argjson request "$(jq -cS . "$request_json")" \
  --argjson build_attestation "$build_attestation" \
  --arg prior_name "$PRIOR_NAME" --arg prior_uid "$PRIOR_UID" '{
    schema_version:$schema,phase:$phase,collector_code_sha:$code_sha,
    collector_build_id:$build_id,collector_image:$image,
    collector_runtime_build_attestation_identity:$build_attestation,
    reused_job:{name:$job,uid:$job_uid,generation:$job_generation},
    execution:{name:$execution,uid:$execution_uid,task_count:1},
    request:$request,request_sha256:$request_sha,
    prior_repair_collect:(if $phase == "reopen" then {name:$prior_name,uid:$prior_uid} else null end),
    known_failed_execution_admission_used:($phase == "collect"),
    source_shards_recomputed:false,target_slate_outcomes_allowed:false,
    automatic_relaunch:false,complete:true
  }'
