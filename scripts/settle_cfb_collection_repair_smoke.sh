#!/usr/bin/env bash
# Read-only settlement recovery for the already-complete CFB repair smoke.
#
# This script is exact-bound to ingest-cfb-rwcqr and the immutable WlLILm
# evidence directory.  It reopens provider, log, and BigQuery state; accepts
# K only on showdown slates; and creates the receipt that the original
# settlement rejected.  It has no provider, scheduler, or BigQuery mutation
# path and cannot launch another execution.
set -euo pipefail

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

[[ $# -eq 1 && "$1" == "--settle" ]] || \
  die "usage: $0 --settle"

SCRIPT_PATH=$(readlink -f -- "$0")
SOURCE_ROOT=$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd -P)
[[ "$SOURCE_ROOT" == "/home/erich/projects/nfl-predictions" ]] || \
  die "the governed production repository path differs"

PROJECT="nfl-predictions-503414"
REGION="us-central1"
LOCATION="US"
JOB="ingest-cfb"
JOB_UID="2a1902a6-3bff-4511-9647-3340b1815ec9"
JOB_GENERATION=11
EXECUTION="ingest-cfb-rwcqr"
EXECUTION_UID="e4c4e5cf-1862-46e2-be94-1751a66dc683"
SOURCE_SHA="31fa0d82c81b140f7853fa7de0bbd6f880890957"
BUILD_ID="e3ebcc13-ba90-409b-b7d1-ce835adf23bf"
IMAGE_TAG="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:cfb-collection-31fa0d82c81b140f7853fa7de0bbd6f880890957"
IMAGE="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:78c905ff383cd6ddaded89d515d14d85617d7138398ec161f91e079655f02f80"
SERVICE_ACCOUNT="817589974517-compute@developer.gserviceaccount.com"
SMOKE_STARTED_AT="2026-09-02T04:25:01Z"
COMPLETION_TIME="2026-09-02T04:28:59.074510Z"
ARTIFACT_DIR="$SOURCE_ROOT/.tmp/cfb-collection-release.WlLILm"
RECEIPT="$ARTIFACT_DIR/receipt.json"

for command_name in awk bq chmod cmp dirname gcloud jq ln mkdir mktemp \
    readlink rm sha256sum; do
  command -v "$command_name" >/dev/null 2>&1 || \
    die "required read-only settlement tool is absent: $command_name"
done

[[ -d "$ARTIFACT_DIR" && ! -L "$ARTIFACT_DIR" ]] || \
  die "the exact smoke evidence directory is absent or unsafe"
[[ ! -e "$RECEIPT" && ! -L "$RECEIPT" ]] || \
  die "the create-once smoke receipt already exists"

verify_local_evidence_hashes() {
  local expected name actual
  while read -r expected name; do
    [[ -f "$ARTIFACT_DIR/$name" && ! -L "$ARTIFACT_DIR/$name" ]] || \
      die "required local evidence is absent or unsafe: $name"
    actual=$(sha256sum "$ARTIFACT_DIR/$name" | awk '{print $1}')
    [[ "$actual" == "$expected" ]] || \
      die "local smoke evidence changed: $name"
  done <<'EOF'
0ef1a56ca84f53bcbb988a5795f116042d59fc08baee6f2bf3edf10a37eb7b8e build.json
7bd754a7346fd69d04d54e79f7a8e86d8802b74bc59359d1607358174261b177 artifact-image-tag.json
669e98b3486c757b1c05ab7f722fcd25c45163db207b13743d8ac2a69023c2d9 job-before.json
1c26af1171a4268edac6862a80bb2f3250242d8292a9456968780cde549dffb8 job-after-update.json
1c26af1171a4268edac6862a80bb2f3250242d8292a9456968780cde549dffb8 job-before-launch.json
ef3c131ebb6d4977fecdb1569562d4d3b6195790660c2d3f762f0cdf6168bdfa scheduler-daily-before.json
834429be6350f4a202d73f96759ce55b65dd74d7e4aca5e17cd9818d95e44863 scheduler-saturday-before.json
ef3c131ebb6d4977fecdb1569562d4d3b6195790660c2d3f762f0cdf6168bdfa scheduler-daily-after.json
db8e89dc01055d36c258d4b630d0549cc475fea49be93a683e050da1127f034a scheduler-saturday-after.json
ef3c131ebb6d4977fecdb1569562d4d3b6195790660c2d3f762f0cdf6168bdfa scheduler-daily-before-launch.json
db8e89dc01055d36c258d4b630d0549cc475fea49be93a683e050da1127f034a scheduler-saturday-before-launch.json
ed2dadeb6dc6c1ab19731858831732a2030e138b98309cb7f9f7591fe0dbb39d executions-before-launch.json
1dfcba13d624472824d3155d2f86a01a675eb9473f3323501bbcc7fc1b602088 executions-terminal.json
a096d3720905d668d910dd79cc5feb9feff58e9bc7350424c91cdb33aaff8d78 new-executions.json
9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa execute.return-code
8ba4bd5f6ded01c87d62491b2a3d84363c07c6335aeda992b41959e70800faa3 execute.stdout
9ec9c3304f8ebb3e7ef087e4cda48cd73cfc8c81e0efc1e49425bdf9de7709ab execute.stderr
9cfd26edc2f510c360eacb0d550474a8a8e753672755d0cb1863a116b79cd6b3 smoke-started-at
c867b08af73b56dbf3092473dc92cfca69aa2a4e06552820e46ba42609e46d7e execution-terminal.json
77150eff1c8a76683e39feeb27e9661e719c57245e24e7ede10c82027134e589 execution-logs.json
48645a5d5cfccb96d8f64f794bc1bcd6430e46dfbf291dd6fba8045d3f63419f bq-before.json
b8e14fa56869f1351ec3fa37a34e3493992f79c5043efc933efd31784b0e171c bq-after.json
2bc3b79dcc3e263534f52ad31e977d47b3e52b884c0a5d5d40670c3261ee1a33 bq-new-row-validation.json
EOF
}

verify_scheduler() {
  local path=$1 scheduler=$2 schedule=$3
  jq -e \
    --arg name "projects/${PROJECT}/locations/${REGION}/jobs/${scheduler}" \
    --arg schedule "$schedule" \
    --arg uri "https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/${JOB}:run" \
    --arg service_account "$SERVICE_ACCOUNT" '
      .name == $name and .state == "PAUSED" and
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
        maxBackoffDuration:"3600s",maxDoublings:5,
        maxRetryDuration:"0s",minBackoffDuration:"5s"
      }
    ' "$path" >/dev/null || \
    die "scheduler $scheduler differs from the exact paused state"
}

verify_release_job() {
  local path=$1
  jq -e \
    --arg uid "$JOB_UID" \
    --arg image "$IMAGE" \
    --arg service_account "$SERVICE_ACCOUNT" \
    --arg project "$PROJECT" \
    --arg execution "$EXECUTION" \
    --argjson generation "$JOB_GENERATION" '
      .metadata.name == "ingest-cfb" and .metadata.uid == $uid and
      .metadata.generation == $generation and
      .status.observedGeneration == $generation and
      .status.executionCount == 130 and
      .status.latestCreatedExecution.name == $execution and
      .status.latestCreatedExecution.completionStatus == "EXECUTION_SUCCEEDED" and
      any(.status.conditions[]?;.type == "Ready" and .status == "True") and
      .spec.template.spec.taskCount == 1 and
      ((.spec.template.spec.parallelism // 1) == 1) and
      .spec.template.spec.template.spec == {
        containers:[{
          args:["ingest-cfb"],command:["nfl-dfs"],
          env:[
            {name:"GCP_PROJECT",value:$project},
            {name:"INGEST_CFB_ENABLED",value:"1"}
          ],
          image:$image,
          resources:{limits:{cpu:"1",memory:"2Gi"}}
        }],
        maxRetries:0,
        serviceAccountName:$service_account,
        timeoutSeconds:"3600"
      }
    ' "$path" >/dev/null || \
    die "live ingest-cfb job differs from the exact generation-11 release"
}

verify_execution() {
  local path=$1
  jq -e \
    --arg execution "$EXECUTION" \
    --arg execution_uid "$EXECUTION_UID" \
    --arg job_uid "$JOB_UID" \
    --arg image "$IMAGE" \
    --arg service_account "$SERVICE_ACCOUNT" \
    --arg project "$PROJECT" \
    --arg started "$SMOKE_STARTED_AT" \
    --arg completed "$COMPLETION_TIME" '
      .metadata.name == $execution and .metadata.uid == $execution_uid and
      .metadata.labels."run.googleapis.com/job" == "ingest-cfb" and
      .metadata.labels."run.googleapis.com/jobUid" == $job_uid and
      .metadata.labels."run.googleapis.com/jobGeneration" == "11" and
      .metadata.creationTimestamp >= $started and
      .status.completionTime == $completed and
      .spec.parallelism == 1 and .spec.taskCount == 1 and
      .spec.template.spec == {
        containers:[{
          args:["ingest-cfb"],command:["nfl-dfs"],
          env:[
            {name:"GCP_PROJECT",value:$project},
            {name:"INGEST_CFB_ENABLED",value:"1"}
          ],
          image:$image,
          resources:{limits:{cpu:"1",memory:"2Gi"}}
        }],
        maxRetries:0,
        serviceAccountName:$service_account,
        timeoutSeconds:"3600"
      } and
      .status.succeededCount == 1 and
      (.status.failedCount // 0) == 0 and
      (.status.cancelledCount // 0) == 0 and
      (.status.retriedCount // 0) == 0 and
      any(.status.conditions[]?;.type == "Completed" and .status == "True")
    ' "$path" >/dev/null || \
    die "the exact smoke execution identity or successful terminal state differs"
}

verify_logs() {
  local path=$1
  jq -e --arg execution "$EXECUTION" '
    def message:
      if (.textPayload | type) == "string" then .textPayload
      elif ((.jsonPayload | type) == "object" and
            (.jsonPayload.message | type) == "string") then
        .jsonPayload.message
      else "" end;
    [ .[] | message ] as $messages |
    length == 16 and
    all(.[];.labels."run.googleapis.com/execution_name" == $execution) and
    all(.[];(.severity // "") != "ERROR") and
    any($messages[];contains("Loading 2134 rows into nfl-predictions-503414.nfl_raw.cfb_dk_salaries")) and
    any($messages[];contains("Loading 2076 rows into nfl-predictions-503414.nfl_raw.dk_contest_fills")) and
    any($messages[];contains("Polled 2076 CFB contests across 11 draft groups")) and
    any($messages[];contains("Container called exit(0).")) and
    ([ $messages[] |
       try capture("CFB slate [0-9]+ \\((classic|showdown)\\): (?<n>[0-9]+) players$").n
       catch empty | tonumber ] | length == 11 and add == 2134) and
    all($messages[];contains("Traceback") | not)
  ' "$path" >/dev/null || die "exact-execution logs fail settlement"
}

verify_local_evidence_hashes

jq -e \
  --arg id "$BUILD_ID" --arg source "$SOURCE_SHA" \
  --arg tag "$IMAGE_TAG" --arg digest "${IMAGE##*@}" '
    .id == $id and .status == "SUCCESS" and
    .substitutions._CODE_SHA == $source and
    .substitutions._CFB_IMAGE == $tag and
    (.results.images | length) == 1 and
    .results.images[0].name == $tag and
    .results.images[0].digest == $digest
  ' "$ARTIFACT_DIR/build.json" >/dev/null || die "local build evidence differs"
jq -e --arg image "$IMAGE" --arg digest "${IMAGE##*@}" '
  .image_summary.digest == $digest and
  .image_summary.fully_qualified_digest == $image
' "$ARTIFACT_DIR/artifact-image-tag.json" >/dev/null || \
  die "local Artifact Registry evidence differs"
verify_scheduler "$ARTIFACT_DIR/scheduler-daily-before-launch.json" \
  "s-cfb" "0 10,14,18 * * *"
verify_scheduler "$ARTIFACT_DIR/scheduler-saturday-before-launch.json" \
  "s-cfb-sat" "0 8,9,11,12,13 * * 6"
verify_execution "$ARTIFACT_DIR/execution-terminal.json"
verify_logs "$ARTIFACT_DIR/execution-logs.json"
jq -e --arg execution "$EXECUTION" '. == [$execution]' \
  "$ARTIFACT_DIR/new-executions.json" >/dev/null || \
  die "local provider delta differs"
[[ "$(<"$ARTIFACT_DIR/execute.return-code")" == "0" ]] || \
  die "the sole execute call did not return zero"
jq -e '
  . == [
    {max_pulled_at:null,row_count:"0",table_name:"cfb_dk_salaries"},
    {max_pulled_at:null,row_count:"0",table_name:"dk_contest_fills_cfb"}
  ]
' "$ARTIFACT_DIR/bq-before.json" >/dev/null || die "local BQ baseline differs"
jq -e '
  . == [
    {max_pulled_at:"2026-09-02T04:28:44.657362Z",row_count:"2134",
     table_name:"cfb_dk_salaries"},
    {max_pulled_at:"2026-09-02T04:28:49.298872Z",row_count:"2076",
     table_name:"dk_contest_fills_cfb"}
  ]
' "$ARTIFACT_DIR/bq-after.json" >/dev/null || die "local BQ result differs"
jq -e '
  . == [
    {draft_groups:"11",invalid_rows:"29",table_name:"cfb_dk_salaries",
     total_rows:"2134"},
    {draft_groups:"11",invalid_rows:"0",table_name:"dk_contest_fills_cfb",
     total_rows:"2076"}
  ]
' "$ARTIFACT_DIR/bq-new-row-validation.json" >/dev/null || \
  die "the disclosed 29-row K-only settlement failure differs"

umask 077
[[ ! -L "$SOURCE_ROOT/.tmp" ]] || die "repository .tmp cannot be a symlink"
SETTLEMENT_DIR=$(mktemp -d "$SOURCE_ROOT/.tmp/cfb-collection-settlement.XXXXXX")
chmod 0700 "$SETTLEMENT_DIR"
printf 'SETTLEMENT_ARTIFACT_DIR=%s\n' "$SETTLEMENT_DIR"

# Every external call below is read-only.
gcloud builds describe "$BUILD_ID" --project="$PROJECT" --format=json \
  >"$SETTLEMENT_DIR/build-live.json"
cmp -s "$ARTIFACT_DIR/build.json" "$SETTLEMENT_DIR/build-live.json" || \
  die "live build evidence differs from the pinned smoke evidence"
gcloud artifacts docker images describe "$IMAGE_TAG" \
  --project="$PROJECT" --format=json \
  >"$SETTLEMENT_DIR/artifact-image-tag-live.json"
cmp -s "$ARTIFACT_DIR/artifact-image-tag.json" \
  "$SETTLEMENT_DIR/artifact-image-tag-live.json" || \
  die "live image tag no longer resolves to the pinned digest"

gcloud run jobs describe "$JOB" --project="$PROJECT" --region="$REGION" \
  --format=json >"$SETTLEMENT_DIR/job-live.json"
verify_release_job "$SETTLEMENT_DIR/job-live.json"
gcloud scheduler jobs describe s-cfb --project="$PROJECT" \
  --location="$REGION" --format=json \
  >"$SETTLEMENT_DIR/scheduler-daily-live.json"
gcloud scheduler jobs describe s-cfb-sat --project="$PROJECT" \
  --location="$REGION" --format=json \
  >"$SETTLEMENT_DIR/scheduler-saturday-live.json"
verify_scheduler "$SETTLEMENT_DIR/scheduler-daily-live.json" \
  "s-cfb" "0 10,14,18 * * *"
verify_scheduler "$SETTLEMENT_DIR/scheduler-saturday-live.json" \
  "s-cfb-sat" "0 8,9,11,12,13 * * 6"

gcloud run jobs executions describe "$EXECUTION" --project="$PROJECT" \
  --region="$REGION" --format=json \
  >"$SETTLEMENT_DIR/execution-live.json"
cmp -s "$ARTIFACT_DIR/execution-terminal.json" \
  "$SETTLEMENT_DIR/execution-live.json" || \
  die "live execution bytes differ from the exact terminal evidence"
verify_execution "$SETTLEMENT_DIR/execution-live.json"
gcloud run jobs executions list --job="$JOB" --project="$PROJECT" \
  --region="$REGION" --limit=1000 --format=json \
  >"$SETTLEMENT_DIR/executions-live.json"
cmp -s "$ARTIFACT_DIR/executions-terminal.json" \
  "$SETTLEMENT_DIR/executions-live.json" || \
  die "another CFB execution appeared after the exact smoke"

gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="ingest-cfb" AND labels."run.googleapis.com/execution_name"="ingest-cfb-rwcqr"' \
  --project="$PROJECT" --freshness=7d --limit=1000 --order=asc --format=json \
  >"$SETTLEMENT_DIR/execution-logs-live.json"
cmp -s "$ARTIFACT_DIR/execution-logs.json" \
  "$SETTLEMENT_DIR/execution-logs-live.json" || \
  die "live exact-execution logs differ from the pinned evidence"
verify_logs "$SETTLEMENT_DIR/execution-logs-live.json"

SNAPSHOT_QUERY=$(printf '%s\n' \
  'SELECT "cfb_dk_salaries" AS table_name, COUNT(1) AS row_count,' \
  '  FORMAT_TIMESTAMP("%Y-%m-%dT%H:%M:%E6SZ", MAX(pulled_at), "UTC") AS max_pulled_at' \
  'FROM `nfl-predictions-503414.nfl_raw.cfb_dk_salaries`' \
  'UNION ALL' \
  'SELECT "dk_contest_fills_cfb" AS table_name, COUNT(1) AS row_count,' \
  '  FORMAT_TIMESTAMP("%Y-%m-%dT%H:%M:%E6SZ", MAX(pulled_at), "UTC") AS max_pulled_at' \
  'FROM `nfl-predictions-503414.nfl_raw.dk_contest_fills`' \
  'WHERE sport = "CFB" ORDER BY table_name')
bq query --quiet --format=json --use_legacy_sql=false \
  --project_id="$PROJECT" --location="$LOCATION" "$SNAPSHOT_QUERY" \
  >"$SETTLEMENT_DIR/bq-live.json"
cmp -s "$ARTIFACT_DIR/bq-after.json" "$SETTLEMENT_DIR/bq-live.json" || \
  die "live CFB counts/max differ from the exact smoke result"

VALIDATION_QUERY=$(printf '%s\n' \
  'SELECT "cfb_dk_salaries" AS table_name, COUNT(1) AS total_rows,' \
  '  COUNTIF(' \
  "    pulled_at < TIMESTAMP(\"${SMOKE_STARTED_AT}\") OR" \
  "    pulled_at > TIMESTAMP(\"${COMPLETION_TIME}\") OR" \
  '    pulled_at IS NULL OR draft_group_id IS NULL OR draft_group_id <= 0 OR' \
  '    dk_player_id IS NULL OR dk_player_id <= 0 OR' \
  '    dk_draftable_id IS NULL OR dk_draftable_id <= 0 OR' \
  '    season IS NULL OR season != 2026 OR' \
  '    slate_type IS NULL OR slate_type NOT IN ("classic", "showdown") OR' \
  '    position IS NULL OR NOT (' \
  '      position IN ("QB", "RB", "WR") OR' \
  '      (slate_type = "showdown" AND position = "K")' \
  '    ) OR salary IS NULL OR salary <= 0 OR game_start IS NULL' \
  '  ) AS invalid_rows, COUNT(DISTINCT draft_group_id) AS draft_groups,' \
  '  COUNTIF(slate_type = "showdown" AND position = "K") AS showdown_k_rows,' \
  '  COUNTIF(slate_type != "showdown" AND position = "K") AS non_showdown_k_rows' \
  'FROM `nfl-predictions-503414.nfl_raw.cfb_dk_salaries`' \
  'UNION ALL' \
  'SELECT "dk_contest_fills_cfb" AS table_name, COUNT(1) AS total_rows,' \
  '  COUNTIF(' \
  "    pulled_at < TIMESTAMP(\"${SMOKE_STARTED_AT}\") OR" \
  "    pulled_at > TIMESTAMP(\"${COMPLETION_TIME}\") OR" \
  '    pulled_at IS NULL OR contest_id IS NULL OR contest_id <= 0 OR' \
  '    draft_group_id IS NULL OR draft_group_id <= 0 OR' \
  '    sport IS NULL OR sport != "CFB" OR start_time IS NULL' \
  '  ) AS invalid_rows, COUNT(DISTINCT draft_group_id) AS draft_groups,' \
  '  0 AS showdown_k_rows, 0 AS non_showdown_k_rows' \
  'FROM `nfl-predictions-503414.nfl_raw.dk_contest_fills`' \
  'WHERE sport = "CFB" ORDER BY table_name')
bq query --quiet --format=json --use_legacy_sql=false \
  --project_id="$PROJECT" --location="$LOCATION" "$VALIDATION_QUERY" \
  >"$SETTLEMENT_DIR/bq-row-validation.json"
jq -e '
  . == [
    {draft_groups:"11",invalid_rows:"0",non_showdown_k_rows:"0",
     showdown_k_rows:"29",table_name:"cfb_dk_salaries",total_rows:"2134"},
    {draft_groups:"11",invalid_rows:"0",non_showdown_k_rows:"0",
     showdown_k_rows:"0",table_name:"dk_contest_fills_cfb",total_rows:"2076"}
  ]
' "$SETTLEMENT_DIR/bq-row-validation.json" >/dev/null || \
  die "K-on-showdown-only row validation did not settle exactly"

LOCAL_EVIDENCE_SHA=$(sha256sum "$ARTIFACT_DIR/execution-terminal.json" | \
  awk '{print $1}')
LOG_SHA=$(sha256sum "$ARTIFACT_DIR/execution-logs.json" | awk '{print $1}')
BQ_BEFORE_SHA=$(sha256sum "$ARTIFACT_DIR/bq-before.json" | awk '{print $1}')
BQ_AFTER_SHA=$(sha256sum "$ARTIFACT_DIR/bq-after.json" | awk '{print $1}')
ROW_VALIDATION_SHA=$(sha256sum "$SETTLEMENT_DIR/bq-row-validation.json" | \
  awk '{print $1}')
RECEIPT_TEMP=$(mktemp "$ARTIFACT_DIR/.receipt.XXXXXX")
cleanup() {
  rm -f -- "$RECEIPT_TEMP"
}
trap cleanup EXIT
jq -cnS \
  --arg schema "cfb-collection-repair-smoke/v1" \
  --arg source_sha "$SOURCE_SHA" --arg build_id "$BUILD_ID" \
  --arg image "$IMAGE" --arg job_uid "$JOB_UID" \
  --arg execution "$EXECUTION" --arg execution_uid "$EXECUTION_UID" \
  --arg started "$SMOKE_STARTED_AT" --arg completed "$COMPLETION_TIME" \
  --arg evidence_root "$ARTIFACT_DIR" \
  --arg execution_sha "$LOCAL_EVIDENCE_SHA" --arg logs_sha "$LOG_SHA" \
  --arg bq_before_sha "$BQ_BEFORE_SHA" --arg bq_after_sha "$BQ_AFTER_SHA" \
  --arg row_validation_sha "$ROW_VALIDATION_SHA" \
  --slurpfile before "$ARTIFACT_DIR/bq-before.json" \
  --slurpfile after "$ARTIFACT_DIR/bq-after.json" \
  --slurpfile validation "$SETTLEMENT_DIR/bq-row-validation.json" '{
    schema_version:$schema,
    settlement_only:true,
    provider_mutation_performed:false,
    bq_mutation_performed:false,
    execution_launched:false,
    build:{source_sha:$source_sha,id:$build_id,image:$image},
    job:{name:"ingest-cfb",uid:$job_uid,generation:11,max_retries:0},
    schedulers:{daily_state:"PAUSED",saturday_state:"PAUSED",
                saturday_schedule:"0 8,9,11,12,13 * * 6"},
    execution:{name:$execution,uid:$execution_uid,
               smoke_started_at:$started,completion_time:$completed,
               succeeded_count:1,retried_count:0},
    collection:{acceptance:"salary-rows-and-max-advanced",
                before:$before[0],after:$after[0],
                row_validation:$validation[0]},
    settlement_amendment:{
      reason:"original validator excluded 29 valid showdown kicker rows",
      position_contract:{base:["QB","RB","WR"],
                         showdown_additional:["K"]},
      original_invalid_rows:29,
      corrected_invalid_rows:0
    },
    evidence:{root:$evidence_root,execution_sha256:$execution_sha,
              logs_sha256:$logs_sha,bq_before_sha256:$bq_before_sha,
              bq_after_sha256:$bq_after_sha,
              row_validation_sha256:$row_validation_sha}
  }' >"$RECEIPT_TEMP"
chmod 0600 "$RECEIPT_TEMP"
ln "$RECEIPT_TEMP" "$RECEIPT" || die "receipt create-once race"
rm -f -- "$RECEIPT_TEMP"
RECEIPT_TEMP=""
trap - EXIT

printf '%s\n' \
  "SETTLEMENT=PASS" \
  "EXECUTION=$EXECUTION" \
  "EXECUTION_UID=$EXECUTION_UID" \
  "SALARY_ROWS=2134" \
  "CONTEST_ROWS=2076" \
  "SHOWDOWN_K_ROWS=29" \
  "RECEIPT=$RECEIPT" \
  "SCHEDULERS=PAUSED"
