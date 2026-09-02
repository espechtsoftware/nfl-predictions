#!/usr/bin/env bash
# Scoped, one-shot release operator for the repaired CFB collector.
#
# The mutation path always reacquires the ingest-cfb launcher-registry lane,
# proves the exact build and live pre-state, changes only the image/retry
# fields and the Saturday cron, then launches and reconciles exactly one
# outcome-blind collection smoke.  It never resumes either scheduler.
set -euo pipefail

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

usage() {
  printf '%s\n' \
    "usage: $0 --preflight" \
    "       $0 --execute" >&2
  exit 2
}

SCRIPT_PATH=$(readlink -f -- "$0")
SOURCE_ROOT=$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd -P)

PROJECT="nfl-predictions-503414"
REGION="us-central1"
LOCATION="US"
JOB="ingest-cfb"
JOB_UID="2a1902a6-3bff-4511-9647-3340b1815ec9"
PRE_GENERATION=10
PRE_IMAGE="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:6c556b9e7ff4685e89ec2f4efcff542aa8c5f1f2b62f181999cb81cbb9beb893"
BUILD_ID="e3ebcc13-ba90-409b-b7d1-ce835adf23bf"
SOURCE_SHA="31fa0d82c81b140f7853fa7de0bbd6f880890957"
IMAGE_TAG="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:cfb-collection-31fa0d82c81b140f7853fa7de0bbd6f880890957"
IMAGE="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:78c905ff383cd6ddaded89d515d14d85617d7138398ec161f91e079655f02f80"
DAILY_SCHEDULER="s-cfb"
SATURDAY_SCHEDULER="s-cfb-sat"
DAILY_SCHEDULE="0 10,14,18 * * *"
OLD_SATURDAY_SCHEDULE="0 8-13 * * 6"
NEW_SATURDAY_SCHEDULE="0 8,9,11,12,13 * * 6"
SERVICE_ACCOUNT="817589974517-compute@developer.gserviceaccount.com"
RUN_PREFIX="ingest-cfb-"

for command_name in awk bq chmod date dirname gcloud git jq mkdir mktemp mv \
    readlink seq sha256sum sleep; do
  command -v "$command_name" >/dev/null 2>&1 || \
    die "required host tool is absent: $command_name"
done

[[ "$SOURCE_ROOT" == "/home/erich/projects/nfl-predictions" ]] || \
  die "the governed production repository path differs"
git -C "$SOURCE_ROOT" cat-file -e "${SOURCE_SHA}^{commit}" || \
  die "the exact built source commit is unavailable"

MODE=${1:-}
[[ $# -eq 1 ]] || usage
[[ "$MODE" == "--preflight" || "$MODE" == "--execute" ]] || usage

process_start_ticks() {
  local pid=$1 stat_line rest
  [[ "$pid" =~ ^[1-9][0-9]*$ && -r "/proc/$pid/stat" ]] || return 1
  IFS= read -r stat_line <"/proc/$pid/stat" || return 1
  rest=${stat_line##*) }
  set -- $rest
  [[ $# -ge 20 && "${20}" =~ ^[1-9][0-9]*$ ]] || return 1
  printf '%s\n' "${20}"
}

verify_registry_authority() {
  local receipt=${NFL_LAUNCHER_REGISTRY_RECEIPT:-}
  local expected_sha=${NFL_LAUNCHER_REGISTRY_RECEIPT_SHA256:-}
  local wrapper_pid=${NFL_LAUNCHER_REGISTRY_WRAPPER_PID:-}
  local wrapper_ticks=${NFL_LAUNCHER_REGISTRY_WRAPPER_START_TICKS:-}
  local actual_sha live_ticks

  [[ "${NFL_LAUNCHER_REGISTRY_LANE:-}" == "$JOB" ]] || \
    die "mutation requires the exact $JOB launcher-registry lane"
  [[ "$receipt" == "$SOURCE_ROOT/.tmp/launchers/"*.json ]] || \
    die "launcher-registry receipt path differs"
  [[ -f "$receipt" && ! -L "$receipt" ]] || \
    die "launcher-registry receipt is absent or unsafe"
  [[ "$expected_sha" =~ ^[0-9a-f]{64}$ ]] || \
    die "launcher-registry receipt SHA-256 differs"
  actual_sha=$(sha256sum "$receipt" | awk '{print $1}')
  [[ "$actual_sha" == "$expected_sha" ]] || \
    die "launcher-registry receipt content changed"
  [[ "$wrapper_pid" =~ ^[1-9][0-9]*$ && "$wrapper_ticks" =~ ^[1-9][0-9]*$ ]] || \
    die "launcher-registry wrapper identity differs"
  live_ticks=$(process_start_ticks "$wrapper_pid") || \
    die "launcher-registry wrapper is not live"
  [[ "$live_ticks" == "$wrapper_ticks" ]] || \
    die "launcher-registry wrapper PID was reused"
  jq -e \
    --arg script "$SCRIPT_PATH" \
    --argjson pid "$wrapper_pid" \
    --argjson ticks "$wrapper_ticks" \
    --arg lane "$JOB" \
    --arg prefix "$RUN_PREFIX" '
      .schema_version == "shared-launcher-registry/v1" and
      .script_path == $script and .pid == $pid and
      .process_start_ticks == $ticks and .owner == "production" and
      .lane == $lane and .target_run_id_prefixes == [$prefix]
    ' "$receipt" >/dev/null || die "launcher-registry authority differs"
}

# The public mutation mode cannot run outside the shared single-writer lane.
if [[ "$MODE" == "--execute" && -z "${NFL_LAUNCHER_REGISTRY_RECEIPT:-}" ]]; then
  exec "$SOURCE_ROOT/scripts/launcher_registry.sh" run \
    --root "$SOURCE_ROOT" \
    --lane "$JOB" \
    --owner production \
    --target-prefixes "$RUN_PREFIX" \
    -- "$SCRIPT_PATH" --execute
fi
if [[ "$MODE" == "--execute" ]]; then
  verify_registry_authority
fi

umask 077
[[ ! -L "$SOURCE_ROOT/.tmp" ]] || die "repository .tmp cannot be a symlink"
mkdir -p "$SOURCE_ROOT/.tmp"
STATE_DIR=$(mktemp -d "$SOURCE_ROOT/.tmp/cfb-collection-release.XXXXXX")
chmod 0700 "$STATE_DIR"
printf 'ARTIFACT_DIR=%s\n' "$STATE_DIR"

describe_job() {
  local destination=$1
  gcloud run jobs describe "$JOB" \
    --project="$PROJECT" --region="$REGION" --format=json >"$destination"
}

describe_scheduler() {
  local scheduler=$1 destination=$2
  gcloud scheduler jobs describe "$scheduler" \
    --project="$PROJECT" --location="$REGION" --format=json >"$destination"
}

list_executions() {
  local destination=$1
  gcloud run jobs executions list --job="$JOB" \
    --project="$PROJECT" --region="$REGION" --limit=1000 \
    --format=json >"$destination"
}

capture_bq_snapshot() {
  local destination=$1
  local query
  query=$(printf '%s\n' \
    'SELECT "cfb_dk_salaries" AS table_name, COUNT(1) AS row_count,' \
    '  FORMAT_TIMESTAMP("%Y-%m-%dT%H:%M:%E6SZ", MAX(pulled_at), "UTC") AS max_pulled_at' \
    'FROM `nfl-predictions-503414.nfl_raw.cfb_dk_salaries`' \
    'UNION ALL' \
    'SELECT "dk_contest_fills_cfb" AS table_name, COUNT(1) AS row_count,' \
    '  FORMAT_TIMESTAMP("%Y-%m-%dT%H:%M:%E6SZ", MAX(pulled_at), "UTC") AS max_pulled_at' \
    'FROM `nfl-predictions-503414.nfl_raw.dk_contest_fills`' \
    'WHERE sport = "CFB"' \
    'ORDER BY table_name')
  bq query --quiet --format=json --use_legacy_sql=false \
    --project_id="$PROJECT" --location="$LOCATION" "$query" >"$destination"
  jq -e '
    length == 2 and
    (map(.table_name) | sort) == ["cfb_dk_salaries", "dk_contest_fills_cfb"] and
    all(.[]; (.row_count | test("^[0-9]+$")) and
      ((.max_pulled_at == null) or
       (.max_pulled_at | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T"))))
  ' "$destination" >/dev/null || die "CFB BigQuery snapshot shape differs"
}

verify_build() {
  gcloud builds describe "$BUILD_ID" --project="$PROJECT" \
    --format=json >"$STATE_DIR/build.json"
  jq -e \
    --arg id "$BUILD_ID" \
    --arg source "$SOURCE_SHA" \
    --arg tag "$IMAGE_TAG" \
    --arg digest "${IMAGE##*@}" '
      .id == $id and .status == "SUCCESS" and
      .substitutions._CODE_SHA == $source and
      .substitutions._CFB_IMAGE == $tag and
      (.results.images | length) == 1 and
      .results.images[0].name == $tag and
      .results.images[0].digest == $digest
    ' "$STATE_DIR/build.json" >/dev/null || \
    die "the exact successful CFB build authority differs"
  gcloud artifacts docker images describe "$IMAGE_TAG" \
    --project="$PROJECT" --format=json >"$STATE_DIR/artifact-image-tag.json"
  jq -e \
    --arg digest "${IMAGE##*@}" \
    --arg image "$IMAGE" '
      .image_summary.digest == $digest and
      .image_summary.fully_qualified_digest == $image and
      .image_summary.registry == "us-central1-docker.pkg.dev" and
      .image_summary.repository == "nfl-dfs"
    ' "$STATE_DIR/artifact-image-tag.json" >/dev/null || \
    die "the Artifact Registry tag no longer resolves to the built digest"
}

verify_pre_job() {
  local path=$1
  jq -e \
    --arg uid "$JOB_UID" \
    --arg image "$PRE_IMAGE" \
    --arg project "$PROJECT" \
    --arg service_account "$SERVICE_ACCOUNT" \
    --argjson generation "$PRE_GENERATION" '
      .apiVersion == "run.googleapis.com/v1" and .kind == "Job" and
      .metadata.name == "ingest-cfb" and .metadata.uid == $uid and
      .metadata.generation == $generation and
      .status.observedGeneration == $generation and
      any(.status.conditions[]?; .type == "Ready" and .status == "True") and
      .spec.template.spec.taskCount == 1 and
      ((.spec.template.spec.parallelism // 1) == 1) and
      (.spec.template.spec.template.spec.containers | length) == 1 and
      .spec.template.spec.template.spec.containers[0] == {
        args:["ingest-cfb"], command:["nfl-dfs"],
        env:[
          {name:"GCP_PROJECT", value:$project},
          {name:"INGEST_CFB_ENABLED", value:"1"}
        ],
        image:$image,
        resources:{limits:{cpu:"1", memory:"2Gi"}}
      } and
      .spec.template.spec.template.spec.maxRetries == 1 and
      .spec.template.spec.template.spec.serviceAccountName == $service_account and
      .spec.template.spec.template.spec.timeoutSeconds == "3600"
    ' "$path" >/dev/null || die "the exact ingest-cfb pre-state differs"
}

verify_scheduler() {
  local path=$1 scheduler=$2 schedule=$3
  jq -e \
    --arg full_name "projects/${PROJECT}/locations/${REGION}/jobs/${scheduler}" \
    --arg schedule "$schedule" \
    --arg uri "https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/${JOB}:run" \
    --arg service_account "$SERVICE_ACCOUNT" '
      .name == $full_name and .state == "PAUSED" and
      .schedule == $schedule and .timeZone == "America/Chicago" and
      .attemptDeadline == "180s" and
      .httpTarget == {
        headers:{"User-Agent":"Google-Cloud-Scheduler"},
        httpMethod:"POST",
        oauthToken:{
          scope:"https://www.googleapis.com/auth/cloud-platform",
          serviceAccountEmail:$service_account
        },
        uri:$uri
      } and
      .retryConfig == {
        maxBackoffDuration:"3600s", maxDoublings:5,
        maxRetryDuration:"0s", minBackoffDuration:"5s"
      }
    ' "$path" >/dev/null || \
    die "scheduler $scheduler does not match its exact paused contract"
}

verify_execution_inventory_is_idle() {
  local executions=$1 job_state=$2
  local expected_count
  expected_count=$(jq -er '.status.executionCount' "$job_state")
  jq -e --arg uid "$JOB_UID" --argjson expected "$expected_count" '
    length == $expected and
    all(.[];
      .metadata.labels."run.googleapis.com/job" == "ingest-cfb" and
      .metadata.labels."run.googleapis.com/jobUid" == $uid and
      (.status.completionTime | type) == "string"
    )
  ' "$executions" >/dev/null || \
    die "ingest-cfb execution inventory is incomplete or has a live execution"
}

capture_and_verify_preflight() {
  verify_build
  describe_job "$STATE_DIR/job-before.json"
  verify_pre_job "$STATE_DIR/job-before.json"
  describe_scheduler "$DAILY_SCHEDULER" "$STATE_DIR/scheduler-daily-before.json"
  describe_scheduler "$SATURDAY_SCHEDULER" "$STATE_DIR/scheduler-saturday-before.json"
  verify_scheduler \
    "$STATE_DIR/scheduler-daily-before.json" "$DAILY_SCHEDULER" "$DAILY_SCHEDULE"
  verify_scheduler \
    "$STATE_DIR/scheduler-saturday-before.json" \
    "$SATURDAY_SCHEDULER" "$OLD_SATURDAY_SCHEDULE"
  list_executions "$STATE_DIR/executions-before.json"
  verify_execution_inventory_is_idle \
    "$STATE_DIR/executions-before.json" "$STATE_DIR/job-before.json"
  capture_bq_snapshot "$STATE_DIR/bq-before.json"
  jq -e '
    all(.[]; .row_count == "0" and .max_pulled_at == null)
  ' "$STATE_DIR/bq-before.json" >/dev/null || \
    die "the exact zero-row CFB collection baseline differs"
}

capture_and_verify_preflight
if [[ "$MODE" == "--preflight" ]]; then
  printf '%s\n' \
    "PREFLIGHT=PASS" \
    "BUILD_ID=$BUILD_ID" \
    "SOURCE_SHA=$SOURCE_SHA" \
    "IMAGE=$IMAGE" \
    "JOB_UID=$JOB_UID" \
    "JOB_GENERATION=$PRE_GENERATION" \
    "SCHEDULERS=PAUSED"
  exit 0
fi

# From this point onward every provider mutation is deliberately singular.
POST_GENERATION=$((PRE_GENERATION + 1))

verify_release_job() {
  local path=$1
  jq -e -n \
    --slurpfile before "$STATE_DIR/job-before.json" \
    --slurpfile after "$path" \
    --arg uid "$JOB_UID" \
    --arg image "$IMAGE" \
    --argjson generation "$POST_GENERATION" '
      def config:
        {
          taskCount:.spec.template.spec.taskCount,
          parallelism:(.spec.template.spec.parallelism // 1),
          task:{
            containers:.spec.template.spec.template.spec.containers,
            maxRetries:(.spec.template.spec.template.spec.maxRetries // 0),
            serviceAccountName:.spec.template.spec.template.spec.serviceAccountName,
            timeoutSeconds:.spec.template.spec.template.spec.timeoutSeconds,
            volumes:(.spec.template.spec.template.spec.volumes // [])
          }
        };
      ($before[0] | config) as $old |
      ($after[0] | config) as $new |
      ($old | .task.containers[0].image = $image | .task.maxRetries = 0) == $new and
      $after[0].metadata.uid == $uid and
      $after[0].metadata.generation == $generation and
      $after[0].status.observedGeneration == $generation and
      any($after[0].status.conditions[]?; .type == "Ready" and .status == "True")
    ' >/dev/null || \
    die "ingest-cfb differs from the image/maxRetries-only release state"
}

gcloud run jobs update "$JOB" \
  --project="$PROJECT" --region="$REGION" \
  --image="$IMAGE" --max-retries=0 --quiet \
  >"$STATE_DIR/job-update.stdout" 2>"$STATE_DIR/job-update.stderr"

describe_job "$STATE_DIR/job-after-update.json"
verify_release_job "$STATE_DIR/job-after-update.json"

gcloud scheduler jobs update http "$SATURDAY_SCHEDULER" \
  --project="$PROJECT" --location="$REGION" \
  --schedule="$NEW_SATURDAY_SCHEDULE" --quiet \
  >"$STATE_DIR/scheduler-update.stdout" \
  2>"$STATE_DIR/scheduler-update.stderr"

describe_scheduler "$DAILY_SCHEDULER" "$STATE_DIR/scheduler-daily-after.json"
describe_scheduler "$SATURDAY_SCHEDULER" "$STATE_DIR/scheduler-saturday-after.json"
verify_scheduler \
  "$STATE_DIR/scheduler-daily-after.json" "$DAILY_SCHEDULER" "$DAILY_SCHEDULE"
verify_scheduler \
  "$STATE_DIR/scheduler-saturday-after.json" \
  "$SATURDAY_SCHEDULER" "$NEW_SATURDAY_SCHEDULE"
jq -e -n \
  --slurpfile before "$STATE_DIR/scheduler-daily-before.json" \
  --slurpfile after "$STATE_DIR/scheduler-daily-after.json" '
    def contract:
      {name,state,schedule,timeZone,attemptDeadline,httpTarget,retryConfig};
    ($before[0] | contract) == ($after[0] | contract)
  ' >/dev/null || die "the daily CFB scheduler changed"
jq -e -n \
  --slurpfile before "$STATE_DIR/scheduler-saturday-before.json" \
  --slurpfile after "$STATE_DIR/scheduler-saturday-after.json" '
    def contract:
      {name,state,schedule,timeZone,attemptDeadline,httpTarget,retryConfig};
    (($before[0] | contract) | del(.schedule)) ==
      (($after[0] | contract) | del(.schedule))
  ' >/dev/null || die "the Saturday scheduler changed outside its schedule"

# Recheck immediately before the sole execute call.  Any intervening claim
# stops the operator rather than creating an overlapping execution.
describe_job "$STATE_DIR/job-before-launch.json"
verify_release_job "$STATE_DIR/job-before-launch.json"
describe_scheduler \
  "$DAILY_SCHEDULER" "$STATE_DIR/scheduler-daily-before-launch.json"
describe_scheduler \
  "$SATURDAY_SCHEDULER" "$STATE_DIR/scheduler-saturday-before-launch.json"
verify_scheduler \
  "$STATE_DIR/scheduler-daily-before-launch.json" \
  "$DAILY_SCHEDULER" "$DAILY_SCHEDULE"
verify_scheduler \
  "$STATE_DIR/scheduler-saturday-before-launch.json" \
  "$SATURDAY_SCHEDULER" "$NEW_SATURDAY_SCHEDULE"
list_executions "$STATE_DIR/executions-before-launch.json"
jq -e -n \
  --slurpfile first "$STATE_DIR/executions-before.json" \
  --slurpfile latest "$STATE_DIR/executions-before-launch.json" '
    ($first[0] | map(.metadata.name) | sort) ==
      ($latest[0] | map(.metadata.name) | sort)
  ' >/dev/null || die "execution inventory changed before the smoke claim"
verify_execution_inventory_is_idle \
  "$STATE_DIR/executions-before-launch.json" "$STATE_DIR/job-before-launch.json"

# Exactly one provider execute call exists in this operator.  A nonzero local
# return is treated as ambiguous: it is never retried and is reconciled from
# the exact provider execution-set delta below.
SMOKE_STARTED_AT=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
[[ "$SMOKE_STARTED_AT" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] || \
  die "smoke start time differs"
printf '%s\n' "$SMOKE_STARTED_AT" >"$STATE_DIR/smoke-started-at"
set +e
gcloud run jobs execute "$JOB" \
  --project="$PROJECT" --region="$REGION" --async --format=json \
  >"$STATE_DIR/execute.stdout" 2>"$STATE_DIR/execute.stderr"
EXECUTE_RC=$?
set -e
printf '%s\n' "$EXECUTE_RC" >"$STATE_DIR/execute.return-code"

EXECUTION=""
for _attempt in $(seq 1 60); do
  if list_executions "$STATE_DIR/executions-after-launch.json"; then
    jq -n \
      --slurpfile before "$STATE_DIR/executions-before-launch.json" \
      --slurpfile after "$STATE_DIR/executions-after-launch.json" '
        ($before[0] | map(.metadata.name)) as $old |
        [$after[0][].metadata.name as $name |
          select(($old | index($name)) == null) | $name]
      ' >"$STATE_DIR/new-executions.json"
    if [[ "$(jq -er 'length' "$STATE_DIR/new-executions.json")" == 1 ]]; then
      EXECUTION=$(jq -er '.[0]' "$STATE_DIR/new-executions.json")
      break
    fi
    [[ "$(jq -er 'length' "$STATE_DIR/new-executions.json")" == 0 ]] || \
      die "more than one provider execution appeared after the sole claim"
  fi
  sleep 5
done
[[ "$EXECUTION" =~ ^ingest-cfb-[a-z0-9]{5}$ ]] || \
  die "the sole execute call did not reconcile to exactly one execution"

for _attempt in $(seq 1 500); do
  if gcloud run jobs executions describe "$EXECUTION" \
      --project="$PROJECT" --region="$REGION" --format=json \
      >"$STATE_DIR/execution-terminal.json.tmp"; then
    mv "$STATE_DIR/execution-terminal.json.tmp" \
      "$STATE_DIR/execution-terminal.json"
    if jq -e '(.status.completionTime | type) == "string"' \
        "$STATE_DIR/execution-terminal.json" >/dev/null; then
      break
    fi
  fi
  sleep 15
done
[[ -s "$STATE_DIR/execution-terminal.json" ]] || \
  die "the exact CFB smoke did not reach a visible terminal state"

jq -e \
  --slurpfile job "$STATE_DIR/job-after-update.json" \
  --arg execution "$EXECUTION" \
  --arg uid "$JOB_UID" \
  --arg generation "$POST_GENERATION" '
    def job_config:
      {
        parallelism:(.spec.template.spec.parallelism // 1),
        taskCount:.spec.template.spec.taskCount,
        task:{
          containers:.spec.template.spec.template.spec.containers,
          maxRetries:(.spec.template.spec.template.spec.maxRetries // 0),
          serviceAccountName:.spec.template.spec.template.spec.serviceAccountName,
          timeoutSeconds:.spec.template.spec.template.spec.timeoutSeconds,
          volumes:(.spec.template.spec.template.spec.volumes // [])
        }
      };
    def execution_config:
      {
        parallelism:.spec.parallelism,
        taskCount:.spec.taskCount,
        task:{
          containers:.spec.template.spec.containers,
          maxRetries:(.spec.template.spec.maxRetries // 0),
          serviceAccountName:.spec.template.spec.serviceAccountName,
          timeoutSeconds:.spec.template.spec.timeoutSeconds,
          volumes:(.spec.template.spec.volumes // [])
        }
      };
    .metadata.name == $execution and
    .metadata.labels."run.googleapis.com/job" == "ingest-cfb" and
    .metadata.labels."run.googleapis.com/jobUid" == $uid and
    .metadata.labels."run.googleapis.com/jobGeneration" == $generation and
    execution_config == ($job[0] | job_config) and
    .status.succeededCount == 1 and
    (.status.failedCount // 0) == 0 and
    (.status.cancelledCount // 0) == 0 and
    (.status.retriedCount // 0) == 0 and
    any(.status.conditions[]?; .type == "Completed" and .status == "True")
  ' "$STATE_DIR/execution-terminal.json" >/dev/null || \
  die "the exact CFB smoke failed or ran under a different configuration"
EXECUTION_UID=$(jq -er '.metadata.uid' "$STATE_DIR/execution-terminal.json")
COMPLETION_TIME=$(jq -er '.status.completionTime' \
  "$STATE_DIR/execution-terminal.json")
[[ "$COMPLETION_TIME" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z$ ]] || \
  die "execution completion time differs"

# Reconcile the final provider set once more; a concurrent second execution
# invalidates this release even if the intended smoke itself succeeded.
list_executions "$STATE_DIR/executions-terminal.json"
jq -e -n \
  --slurpfile before "$STATE_DIR/executions-before-launch.json" \
  --slurpfile after "$STATE_DIR/executions-terminal.json" \
  --arg execution "$EXECUTION" '
    ($before[0] | map(.metadata.name) | sort) as $old |
    ($after[0] | map(.metadata.name) | sort) as $new |
    ($new | length) == (($old | length) + 1) and
    all($old[]; . as $name | ($new | index($name)) != null) and
    [$new[] as $name | select(($old | index($name)) == null) | $name] ==
      [$execution]
  ' >/dev/null || die "terminal provider execution inventory differs"

# Logs are read by exact execution identity.  Read-only retries cover Cloud
# Logging ingestion lag; they never relaunch or modify the provider job.
for _attempt in $(seq 1 30); do
  if gcloud logging read \
      "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${JOB}\" AND labels.\"run.googleapis.com/execution_name\"=\"${EXECUTION}\"" \
      --project="$PROJECT" --freshness=7d --limit=1000 --order=asc \
      --format=json >"$STATE_DIR/execution-logs.json" && \
      jq -e 'length > 0' "$STATE_DIR/execution-logs.json" >/dev/null; then
    break
  fi
  sleep 5
done
jq -e --arg execution "$EXECUTION" '
  length > 0 and all(.[];
    .labels."run.googleapis.com/execution_name" == $execution)
' "$STATE_DIR/execution-logs.json" >/dev/null || \
  die "exact-execution Cloud Logging evidence is absent or mixed"

capture_bq_snapshot "$STATE_DIR/bq-after.json"

ADVANCED=false
jq -e -n \
  --slurpfile before "$STATE_DIR/bq-before.json" \
  --slurpfile after "$STATE_DIR/bq-after.json" '
    def keyed:
      map({key:.table_name,
           value:{row_count:(.row_count | tonumber),
                  max_pulled_at:(.max_pulled_at // null)}}) | from_entries;
    ($before[0] | keyed) as $old |
    ($after[0] | keyed) as $new |
    all($old | keys[]; . as $table |
      $new[$table].row_count >= $old[$table].row_count and
      (($old[$table].max_pulled_at == null) or
       ($new[$table].max_pulled_at != null and
        $new[$table].max_pulled_at >= $old[$table].max_pulled_at))) and
    $new.cfb_dk_salaries.row_count > $old.cfb_dk_salaries.row_count and
    $new.cfb_dk_salaries.max_pulled_at != null and
    (($old.cfb_dk_salaries.max_pulled_at == null) or
     ($new.cfb_dk_salaries.max_pulled_at >
      $old.cfb_dk_salaries.max_pulled_at))
  ' >/dev/null && ADVANCED=true

if [[ "$ADVANCED" == true ]]; then
  VALIDATION_QUERY=$(printf '%s\n' \
    'SELECT "cfb_dk_salaries" AS table_name, COUNT(1) AS total_rows,' \
    '  COUNTIF(' \
    '    pulled_at IS NULL OR' \
    "    pulled_at < TIMESTAMP(\"${SMOKE_STARTED_AT}\") OR" \
    "    pulled_at > TIMESTAMP(\"${COMPLETION_TIME}\") OR" \
    '    draft_group_id IS NULL OR draft_group_id <= 0 OR' \
    '    dk_player_id IS NULL OR dk_player_id <= 0 OR' \
    '    dk_draftable_id IS NULL OR dk_draftable_id <= 0 OR' \
    '    season IS NULL OR season != 2026 OR' \
    '    slate_type IS NULL OR slate_type NOT IN ("classic", "showdown") OR' \
    '    position IS NULL OR position NOT IN ("QB", "RB", "WR") OR' \
    '    salary IS NULL OR salary <= 0 OR game_start IS NULL' \
    '  ) AS invalid_rows, COUNT(DISTINCT draft_group_id) AS draft_groups' \
    'FROM `nfl-predictions-503414.nfl_raw.cfb_dk_salaries`' \
    'UNION ALL' \
    'SELECT "dk_contest_fills_cfb" AS table_name, COUNT(1) AS total_rows,' \
    '  COUNTIF(' \
    '    pulled_at IS NULL OR' \
    "    pulled_at < TIMESTAMP(\"${SMOKE_STARTED_AT}\") OR" \
    "    pulled_at > TIMESTAMP(\"${COMPLETION_TIME}\") OR" \
    '    contest_id IS NULL OR contest_id <= 0 OR' \
    '    draft_group_id IS NULL OR draft_group_id <= 0 OR' \
    '    sport IS NULL OR sport != "CFB" OR start_time IS NULL' \
    '  ) AS invalid_rows, COUNT(DISTINCT draft_group_id) AS draft_groups' \
    'FROM `nfl-predictions-503414.nfl_raw.dk_contest_fills`' \
    'WHERE sport = "CFB"' \
    'ORDER BY table_name')
  bq query --quiet --format=json --use_legacy_sql=false \
    --project_id="$PROJECT" --location="$LOCATION" "$VALIDATION_QUERY" \
    >"$STATE_DIR/bq-new-row-validation.json"
  jq -e -n \
    --slurpfile validation "$STATE_DIR/bq-new-row-validation.json" \
    --slurpfile snapshot "$STATE_DIR/bq-after.json" '
      def keyed: map({key:.table_name,value:.}) | from_entries;
      ($validation[0] | keyed) as $checks |
      ($snapshot[0] | keyed) as $counts |
      ($checks | keys | sort) ==
        ["cfb_dk_salaries", "dk_contest_fills_cfb"] and
      ($checks.cfb_dk_salaries.total_rows | tonumber) > 0 and
      ($checks.cfb_dk_salaries.invalid_rows | tonumber) == 0 and
      ($checks.cfb_dk_salaries.draft_groups | tonumber) > 0 and
      $checks.cfb_dk_salaries.total_rows ==
        $counts.cfb_dk_salaries.row_count and
      ($checks.dk_contest_fills_cfb.invalid_rows | tonumber) == 0 and
      $checks.dk_contest_fills_cfb.total_rows ==
        $counts.dk_contest_fills_cfb.row_count
    ' >/dev/null || \
    die "new CFB salary/contest rows failed the settlement contract"
  ACCEPTANCE="salary-rows-and-max-advanced"
elif jq -e '
    def message:
      if (.textPayload | type) == "string" then .textPayload
      elif ((.jsonPayload | type) == "object" and
            (.jsonPayload.message | type) == "string") then
        .jsonPayload.message
      else "" end;
    any(.[]; message | contains("No upcoming CFB draft groups"))
  ' "$STATE_DIR/execution-logs.json" >/dev/null; then
  # Zero writes are accepted only with this exact outcome-blind no-op signal.
  jq -e -n \
    --slurpfile before "$STATE_DIR/bq-before.json" \
    --slurpfile after "$STATE_DIR/bq-after.json" '$before[0] == $after[0]' \
    >/dev/null || die "CFB rows changed non-monotonically"
  printf '[]\n' >"$STATE_DIR/bq-new-row-validation.json"
  ACCEPTANCE="no-upcoming-draft-groups"
else
  die "successful smoke neither advanced CFB data nor logged the exact no-op"
fi

# The release never resumes a scheduler.  Re-open both after settlement so
# the final receipt proves that they remained paused throughout the smoke.
describe_scheduler "$DAILY_SCHEDULER" "$STATE_DIR/scheduler-daily-terminal.json"
describe_scheduler \
  "$SATURDAY_SCHEDULER" "$STATE_DIR/scheduler-saturday-terminal.json"
verify_scheduler \
  "$STATE_DIR/scheduler-daily-terminal.json" "$DAILY_SCHEDULER" "$DAILY_SCHEDULE"
verify_scheduler \
  "$STATE_DIR/scheduler-saturday-terminal.json" \
  "$SATURDAY_SCHEDULER" "$NEW_SATURDAY_SCHEDULE"

jq -cnS \
  --arg schema "cfb-collection-repair-smoke/v1" \
  --arg build_id "$BUILD_ID" \
  --arg source_sha "$SOURCE_SHA" \
  --arg image "$IMAGE" \
  --arg job "$JOB" \
  --arg job_uid "$JOB_UID" \
  --argjson pre_generation "$PRE_GENERATION" \
  --argjson post_generation "$POST_GENERATION" \
  --arg execution "$EXECUTION" \
  --arg execution_uid "$EXECUTION_UID" \
  --arg smoke_started_at "$SMOKE_STARTED_AT" \
  --arg completion_time "$COMPLETION_TIME" \
  --argjson execute_return_code "$EXECUTE_RC" \
  --arg acceptance "$ACCEPTANCE" \
  --slurpfile bq_before "$STATE_DIR/bq-before.json" \
  --slurpfile bq_after "$STATE_DIR/bq-after.json" \
  --slurpfile row_validation "$STATE_DIR/bq-new-row-validation.json" '{
    schema_version:$schema,
    build:{id:$build_id,source_sha:$source_sha,image:$image},
    job:{name:$job,uid:$job_uid,pre_generation:$pre_generation,
         post_generation:$post_generation,max_retries:0},
    scheduler:{daily_state:"PAUSED",saturday_state:"PAUSED",
               saturday_schedule:"0 8,9,11,12,13 * * 6"},
    execution:{name:$execution,uid:$execution_uid,
               smoke_started_at:$smoke_started_at,
               completion_time:$completion_time,
               execute_return_code:$execute_return_code,
               succeeded_count:1,retried_count:0},
    collection:{acceptance:$acceptance,
                before:$bq_before[0],after:$bq_after[0],
                new_row_validation:$row_validation[0]}
  }' >"$STATE_DIR/receipt.json"

printf '%s\n' \
  "RELEASE_SMOKE=PASS" \
  "EXECUTION=$EXECUTION" \
  "EXECUTION_UID=$EXECUTION_UID" \
  "ACCEPTANCE=$ACCEPTANCE" \
  "RECEIPT=$STATE_DIR/receipt.json" \
  "SCHEDULERS=PAUSED"
