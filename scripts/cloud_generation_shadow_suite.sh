#!/usr/bin/env bash
# Deploy the dedicated prospective-generation suite. Execution is a separate,
# explicit opt-in so installing the immutable job ahead of Week 1 cannot
# consume a slate or create a pre-lock experiment.
set -euo pipefail

die() { printf '%s\n' "ERROR: $*" >&2; exit 2; }

[[ $# -eq 2 ]] || die "usage: $0 IMAGE@sha256:DIGEST FULL_CODE_SHA"
IMAGE=$1
CODE_SHA=$2
PROJECT=${GCP_PROJECT:-nfl-predictions-503414}
REGION=${GCP_REGION:-us-central1}
JOB=${GENERATION_SHADOW_JOB:-generation-shadow-suite}
SERVICE_ACCOUNT=${GENERATION_SHADOW_SERVICE_ACCOUNT:-nfl-dfs-runner@${PROJECT}.iam.gserviceaccount.com}
EXECUTE=${GENERATION_SHADOW_EXECUTE:-0}
ALLOW_CREATE=${GENERATION_SHADOW_ALLOW_CREATE:-0}
SEASON=${GENERATION_SHADOW_SEASON:-}
WEEK=${GENERATION_SHADOW_WEEK:-}
DRAFT_GROUP_ID=${GENERATION_SHADOW_DRAFT_GROUP_ID:-}
SLATE_LOCK_AT=${GENERATION_SHADOW_SLATE_LOCK_AT:-}

[[ "$IMAGE" =~ ^[^[:space:]@]+@sha256:[0-9a-f]{64}$ ]] || \
  die "image must be immutable and digest-pinned"
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "CODE_SHA must be a full Git commit"
[[ "$JOB" == "generation-shadow-suite" ]] || \
  die "the dedicated unscheduled job name is fixed"
[[ "$EXECUTE" == "0" || "$EXECUTE" == "1" ]] || \
  die "GENERATION_SHADOW_EXECUTE must be 0 or 1"
[[ "$ALLOW_CREATE" == "0" || "$ALLOW_CREATE" == "1" ]] || \
  die "GENERATION_SHADOW_ALLOW_CREATE must be 0 or 1"
ROOT=$(git rev-parse --show-toplevel)
[[ "$(git -C "$ROOT" rev-parse HEAD)" == "$CODE_SHA" ]] || \
  die "CODE_SHA must equal repository HEAD"
git -C "$ROOT" cat-file -e "${CODE_SHA}^{commit}" || die "CODE_SHA is absent"

JOB_ARGS_CSV=shadow-generation-suite
if [[ "$EXECUTE" == "1" ]]; then
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

common=(
  --project "$PROJECT" --region "$REGION"
  --image "$IMAGE"
  --command nfl-dfs --args "$JOB_ARGS_CSV"
  --tasks 1 --parallelism 1 --max-retries 0
  --cpu 8 --memory 32Gi --task-timeout 86400s
  --service-account "$SERVICE_ACCOUNT"
  --set-env-vars "CODE_SHA=$CODE_SHA,IMAGE_URI=$IMAGE"
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
  ([ $c.env[] | select(.name == "IMAGE_URI") | .value ] == [$image])
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
  --arg args_csv "$JOB_ARGS_CSV" '
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
' "$execution_json" >/dev/null || die "execution differs from the validated job template"

printf '%s\n' "$EXECUTION_ID"
