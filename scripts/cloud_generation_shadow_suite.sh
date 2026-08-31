#!/usr/bin/env bash
# Deploy the dedicated prospective-generation suite. Execution is a separate,
# explicit opt-in so installing the immutable job ahead of Week 1 cannot
# consume a slate or create a pre-lock experiment.
set -euo pipefail

die() { printf '%s\n' "ERROR: $*" >&2; exit 2; }

[[ $# -eq 2 ]] || die "usage: $0 IMAGE@sha256:DIGEST FULL_CODE_SHA"
IMAGE=$1
CODE_SHA=$2
PROJECT=nfl-predictions-503414
REGION=${GCP_REGION:-us-central1}
BUCKET=nfl-predictions-503414-raw
JOB=${GENERATION_SHADOW_JOB:-generation-shadow-suite}
SERVICE_ACCOUNT=${GENERATION_SHADOW_SERVICE_ACCOUNT:-nfl-dfs-runner@${PROJECT}.iam.gserviceaccount.com}
EXECUTE=${GENERATION_SHADOW_EXECUTE:-0}
ALLOW_CREATE=${GENERATION_SHADOW_ALLOW_CREATE:-0}
COLLECT_EXECUTION=${GENERATION_SHADOW_COLLECT_EXECUTION:-}
SEASON=${GENERATION_SHADOW_SEASON:-}
WEEK=${GENERATION_SHADOW_WEEK:-}
DRAFT_GROUP_ID=${GENERATION_SHADOW_DRAFT_GROUP_ID:-}
SLATE_LOCK_AT=${GENERATION_SHADOW_SLATE_LOCK_AT:-}

[[ "$IMAGE" =~ ^[^[:space:]@]+@sha256:[0-9a-f]{64}$ ]] || \
  die "image must be immutable and digest-pinned"
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "CODE_SHA must be a full Git commit"
[[ "${GCP_PROJECT:-$PROJECT}" == "$PROJECT" ]] || \
  die "GCP_PROJECT must be the frozen production project"
[[ "${GCS_BUCKET:-$BUCKET}" == "$BUCKET" ]] || \
  die "GCS_BUCKET must be the frozen production raw bucket"
[[ "$JOB" == "generation-shadow-suite" ]] || \
  die "the dedicated unscheduled job name is fixed"
[[ "$EXECUTE" == "0" || "$EXECUTE" == "1" ]] || \
  die "GENERATION_SHADOW_EXECUTE must be 0 or 1"
[[ "$ALLOW_CREATE" == "0" || "$ALLOW_CREATE" == "1" ]] || \
  die "GENERATION_SHADOW_ALLOW_CREATE must be 0 or 1"
if [[ -n "$COLLECT_EXECUTION" ]]; then
  [[ "$COLLECT_EXECUTION" =~ ^generation-shadow-suite-[a-z0-9]{5}$ ]] || \
    die "GENERATION_SHADOW_COLLECT_EXECUTION must name one exact suite execution"
  [[ "$EXECUTE" == "0" && "$ALLOW_CREATE" == "0" ]] || \
    die "collection cannot deploy, create, or execute the job"
fi
ROOT=$(git rev-parse --show-toplevel)
[[ "$(git -C "$ROOT" rev-parse HEAD)" == "$CODE_SHA" ]] || \
  die "CODE_SHA must equal repository HEAD"
git -C "$ROOT" cat-file -e "${CODE_SHA}^{commit}" || die "CODE_SHA is absent"

JOB_ARGS_CSV=shadow-generation-suite
if [[ "$EXECUTE" == "1" || -n "$COLLECT_EXECUTION" ]]; then
  [[ "$SEASON" == "2026" ]] || \
    die "GENERATION_SHADOW_SEASON must be the frozen 2026 season"
  [[ "$WEEK" =~ ^([1-9]|1[0-8])$ ]] || \
    die "GENERATION_SHADOW_WEEK must be an explicit week from 1 through 18"
  [[ "$DRAFT_GROUP_ID" =~ ^[1-9][0-9]*$ ]] || \
    die "GENERATION_SHADOW_DRAFT_GROUP_ID must be an explicit positive integer"
  [[ "$SLATE_LOCK_AT" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})$ ]] || \
    die "GENERATION_SHADOW_SLATE_LOCK_AT must be an explicit ISO-8601 timestamp"
  JOB_ARGS_CSV="shadow-generation-suite,--season,$SEASON,--week,$WEEK,--draft-group-id,$DRAFT_GROUP_ID,--slate-lock-at,$SLATE_LOCK_AT"
fi

# Collection is a read-only, exact-execution phase.  It does not describe,
# update, deploy, or execute the mutable job resource.  Provider terminality
# and the one receipt-only stdout document are both checked before the exact
# manifest/terminal identities are returned.
if [[ -n "$COLLECT_EXECUTION" ]]; then
  collect_temp=$(mktemp -d /tmp/generation-shadow-collect.XXXXXX)
  trap 'rm -rf "$collect_temp"' EXIT
  execution_json=$collect_temp/execution.json
  logs_json=$collect_temp/stdout-logs.json
  suite_json=$collect_temp/suite.json
  gcloud run jobs executions describe "$COLLECT_EXECUTION" \
    --project "$PROJECT" --region "$REGION" --format=json >"$execution_json"
  jq -e --arg execution "$COLLECT_EXECUTION" --arg job "$JOB" \
    --arg image "$IMAGE" --arg sha "$CODE_SHA" --arg args_csv "$JOB_ARGS_CSV" \
    --arg project "$PROJECT" --arg bucket "$BUCKET" \
    --arg service_account "$SERVICE_ACCOUNT" '
    .metadata.name == $execution and
    .metadata.labels["run.googleapis.com/job"] == $job and
    any(.status.conditions[]?; .type == "Completed" and .status == "True") and
    (.status.completionTime | type == "string" and length > 0) and
    (.status.succeededCount // 0) == 1 and
    (.status.failedCount // 0) == 0 and
    (.status.cancelledCount // 0) == 0 and
    (.status.runningCount // 0) == 0 and
    .spec.taskCount == 1 and .spec.parallelism == 1 and
    .spec.template.spec.maxRetries == 0 and
    (.spec.template.spec.timeout == "86400s" or
     .spec.template.spec.timeout == "86400.000000000s") and
    .spec.template.spec.serviceAccountName == $service_account and
    (.spec.template.spec.containers | length) == 1 and
    (.spec.template.spec.containers[0] as $c |
      $c.image == $image and $c.command == ["nfl-dfs"] and
      $c.args == ($args_csv | split(",")) and
      $c.resources.limits.cpu == "8" and
      $c.resources.limits.memory == "32Gi" and
      ([ $c.env[] | select(.name == "CODE_SHA") | .value ] == [$sha]) and
      ([ $c.env[] | select(.name == "IMAGE_URI") | .value ] == [$image]) and
      ([ $c.env[] | select(.name == "GCP_PROJECT") | .value ] == [$project]) and
      ([ $c.env[] | select(.name == "GCS_BUCKET") | .value ] == [$bucket])
    )
  ' "$execution_json" >/dev/null || die "terminal execution differs from the frozen suite contract"

  log_filter="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$COLLECT_EXECUTION\" AND logName=\"projects/$PROJECT/logs/run.googleapis.com%2Fstdout\" AND textPayload:*"
  gcloud logging read "$log_filter" --project "$PROJECT" --limit 100 \
    --order=asc --format=json >"$logs_json"
  jq -e --arg execution "$COLLECT_EXECUTION" '
    [ .[] | .textPayload? | select(type == "string") | fromjson?
      | select(
          .complete == true and
          .cloud_run_execution == $execution and
          .production_enabled == false
        )
    ] | if length == 1 then .[0]
        else error("suite stdout result count differs") end
  ' "$logs_json" >"$suite_json" || die "suite stdout result differs"

  printf -v week_padded '%02d' "$((10#$WEEK))"
  expected_run_id="prospective-generation-${SEASON}w${week_padded}-${COLLECT_EXECUTION}"
  expected_root="gs://${BUCKET}/generation_shadow/${SEASON}/week-${week_padded}/${expected_run_id}"
  jq -e --arg execution "$COLLECT_EXECUTION" --arg run_id "$expected_run_id" \
    --arg manifest_uri "$expected_root/manifest.json" \
    --arg terminal_uri "$expected_root/terminal.json" '
    (keys | sort) == (["cloud_run_execution","complete","manifest","production_enabled","registry_sha256","run_id","terminal"] | sort) and
    .complete == true and .production_enabled == false and
    .cloud_run_execution == $execution and .run_id == $run_id and
    (.registry_sha256 | test("^[0-9a-f]{64}$")) and
    ([.manifest, .terminal] | all(
      (keys | sort) == (["bytes","create_only","gcs_time_created","generation","precedes_slate_lock","sha256","uri"] | sort) and
      (.generation | type == "number" and . > 0) and
      (.bytes | type == "number" and . > 0) and
      (.sha256 | test("^[0-9a-f]{64}$")) and
      .create_only == true and .precedes_slate_lock == true
    )) and
    .manifest.uri == $manifest_uri and .terminal.uri == $terminal_uri
  ' "$suite_json" >/dev/null || die "suite receipt identities differ"

  jq -cS --arg schema "prospective-generation-shadow-cloud-collection/v1" \
    --arg execution_uid "$(jq -er '.metadata.uid' "$execution_json")" \
    --arg completion_time "$(jq -er '.status.completionTime' "$execution_json")" '
    def identity: {uri, generation:(.generation | tostring), sha256, bytes};
    {
      schema_version:$schema,
      execution:{
        name:.cloud_run_execution,
        uid:$execution_uid,
        task_count:1,
        succeeded_count:1,
        failed_count:0,
        cancelled_count:0,
        completion_time:$completion_time
      },
      run_id:.run_id,
      registry_sha256:.registry_sha256,
      manifest_identity:(.manifest | identity),
      terminal_identity:(.terminal | identity),
      suite_stdout_receipt:.,
      uses_realized_outcomes:false,
      production_enabled:false,
      complete:true
    }
  ' "$suite_json"
  exit 0
fi

common=(
  --project "$PROJECT" --region "$REGION"
  --image "$IMAGE"
  --command nfl-dfs --args "$JOB_ARGS_CSV"
  --tasks 1 --parallelism 1 --max-retries 0
  --cpu 8 --memory 32Gi --task-timeout 86400s
  --service-account "$SERVICE_ACCOUNT"
  --set-env-vars "CODE_SHA=$CODE_SHA,IMAGE_URI=$IMAGE,GCP_PROJECT=$PROJECT,GCS_BUCKET=$BUCKET"
  --quiet
)

# This job is intentionally unscheduled and is never shared with a money path.
if gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
    --format='value(metadata.name)' >/dev/null 2>&1; then
  gcloud run jobs update "$JOB" "${common[@]}" >/dev/null
else
  [[ "$ALLOW_CREATE" == "1" ]] || \
    die "dedicated job is absent; set GENERATION_SHADOW_ALLOW_CREATE=1 to predeclare it"
  gcloud run jobs deploy "$JOB" "${common[@]}" >/dev/null
fi

job_json=$(mktemp)
execution_json=$(mktemp)
launch_json=$(mktemp)
trap 'rm -f "$job_json" "$execution_json" "$launch_json"' EXIT
gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format=json >"$job_json"

jq -e --arg image "$IMAGE" --arg sha "$CODE_SHA" --arg sa "$SERVICE_ACCOUNT" \
  --arg project "$PROJECT" --arg bucket "$BUCKET" \
  --arg args_csv "$JOB_ARGS_CSV" '
  .spec.template.spec as $outer |
  $outer.template.spec as $task |
  $task.containers[0] as $c |
  $outer.taskCount == 1 and $outer.parallelism == 1 and
  $task.maxRetries == 0 and ($task.timeout == "86400s" or $task.timeout == "86400.000000000s") and
  $task.serviceAccountName == $sa and
  ($task.containers | length) == 1 and
  $c.image == $image and $c.command == ["nfl-dfs"] and
  $c.args == ($args_csv | split(",")) and
  $c.resources.limits.cpu == "8" and $c.resources.limits.memory == "32Gi" and
  ([ $c.env[] | select(.name == "CODE_SHA") | .value ] == [$sha]) and
  ([ $c.env[] | select(.name == "IMAGE_URI") | .value ] == [$image]) and
  ([ $c.env[] | select(.name == "GCP_PROJECT") | .value ] == [$project]) and
  ([ $c.env[] | select(.name == "GCS_BUCKET") | .value ] == [$bucket])
' "$job_json" >/dev/null || die "deployed job template differs from the frozen suite contract"

if [[ "$EXECUTE" != "1" ]]; then
  printf '%s\n' "DEPLOYED:$JOB"
  exit 0
fi

gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format=json >"$launch_json"
EXECUTION_ID=$(jq -er '.metadata.name' "$launch_json") || die "launch lacks durable execution ID"
[[ "$EXECUTION_ID" == ${JOB}-* ]] || die "execution ID is not bound to the dedicated job"
gcloud run jobs executions describe "$EXECUTION_ID" --project "$PROJECT" \
  --region "$REGION" --format=json >"$execution_json"

jq -e --arg job "$JOB" --arg image "$IMAGE" --arg sha "$CODE_SHA" \
  --arg args_csv "$JOB_ARGS_CSV" --arg project "$PROJECT" \
  --arg bucket "$BUCKET" '
  (.metadata.name | startswith($job + "-"))
  and (.metadata.labels["run.googleapis.com/job"] == $job)
  and (.spec.taskCount == 1) and (.spec.parallelism == 1)
  and (.spec.template.spec.maxRetries == 0)
  and (.spec.template.spec.timeout == "86400s" or .spec.template.spec.timeout == "86400.000000000s")
  and (.spec.template.spec.containers | length == 1)
  and (.spec.template.spec.containers[0].image == $image)
  and (.spec.template.spec.containers[0].command == ["nfl-dfs"])
  and (.spec.template.spec.containers[0].args == ($args_csv | split(",")))
  and (.spec.template.spec.containers[0].resources.limits.cpu == "8")
  and (.spec.template.spec.containers[0].resources.limits.memory == "32Gi")
  and ([.spec.template.spec.containers[0].env[] | select(.name == "CODE_SHA") | .value] == [$sha])
  and ([.spec.template.spec.containers[0].env[] | select(.name == "IMAGE_URI") | .value] == [$image])
  and ([.spec.template.spec.containers[0].env[] | select(.name == "GCP_PROJECT") | .value] == [$project])
  and ([.spec.template.spec.containers[0].env[] | select(.name == "GCS_BUCKET") | .value] == [$bucket])
' "$execution_json" >/dev/null || die "execution differs from the validated job template"

printf '%s\n' "$EXECUTION_ID"
