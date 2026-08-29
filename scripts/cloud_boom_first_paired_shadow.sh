#!/usr/bin/env bash
# Launch one outcome-blind boom-first pair through an unscheduled reusable job,
# then restore that job's exact prior spec immediately. The execution keeps a
# snapshot of the temporary template; no scheduler or money path is changed.
set -euo pipefail

PROJECT="${GCP_PROJECT:?set GCP_PROJECT}"
REGION="${REGION:-us-central1}"
IMAGE_URI="${IMAGE_URI:?set IMAGE_URI to an @sha256 registry URI}"
CODE_SHA="${CODE_SHA:-$(git rev-parse HEAD)}"
REUSED_JOB="atlas-minimal-c-smoke"
REUSED_JOB_UID="5135c9eb-96c2-41c0-a68a-5c587a601903"
STATE_DIR="$(mktemp -d /tmp/boom-first-launch.XXXXXX)"
PRIOR_YAML="$STATE_DIR/job-before.yaml"
PRIOR_JSON="$STATE_DIR/job-before.json"
AFTER_JSON="$STATE_DIR/job-after-restore.json"
CURRENT_JSON="$STATE_DIR/job-current.json"
TEMP_JSON="$STATE_DIR/job-temporary.json"
EXECUTION_JSON="$STATE_DIR/execution.json"
LEASE_FILE="$STATE_DIR/operator-lease.json"
RECOVERY_BUCKET="${GCS_BUCKET:-${PROJECT}-raw}"
LEASE_ID="$(date -u +%Y%m%dT%H%M%SZ)-${STATE_DIR##*/}"
LEASE_URI="gs://${RECOVERY_BUCKET}/boom_first_shadow/operator-locks/${REUSED_JOB}.json"
RECOVERY_PREFIX="gs://${RECOVERY_BUCKET}/boom_first_shadow/operator-recovery/${LEASE_ID}"
RESTORE_NEEDED=0
LEASE_HELD=0
TEMP_SPEC_SHA=""
EXECUTION=""

job_spec_sha() {
  jq -S -c '.spec' "$1" | sha256sum | awk '{print $1}'
}

describe_job() {
  output="$1"
  gcloud run jobs describe "$REUSED_JOB" \
    --project "$PROJECT" \
    --region "$REGION" \
    --format=json > "$output"
}

verify_prior_job() {
  describe_job "$AFTER_JSON" || return 1
  after_uid="$(jq -r '.metadata.uid // empty' "$AFTER_JSON")"
  after_spec_sha="$(job_spec_sha "$AFTER_JSON")"
  if [[ "$after_uid" != "$prior_uid" || "$after_spec_sha" != "$prior_spec_sha" ]]; then
    printf 'reusable job restoration verification failed\n' >&2
    return 1
  fi
  RESTORE_NEEDED=0
  return 0
}

restore_job() {
  if [[ "$RESTORE_NEEDED" == "1" ]]; then
    # Never overwrite a third-party update made after our temporary template.
    # If the current spec is neither the captured prior spec nor our exact
    # temporary spec, retain the lease and recovery artifacts for reconciliation.
    if [[ -n "$TEMP_SPEC_SHA" ]]; then
      describe_job "$CURRENT_JSON" || return 1
      current_uid="$(jq -r '.metadata.uid // empty' "$CURRENT_JSON")"
      current_spec_sha="$(job_spec_sha "$CURRENT_JSON")"
      if [[ "$current_uid" != "$prior_uid" ]]; then
        printf 'reusable job UID changed during launch; refusing overwrite\n' >&2
        return 1
      fi
      if [[ "$current_spec_sha" == "$prior_spec_sha" ]]; then
        RESTORE_NEEDED=0
        return 0
      fi
      if [[ "$current_spec_sha" != "$TEMP_SPEC_SHA" ]]; then
        printf 'reusable job changed outside this launcher; refusing overwrite\n' >&2
        return 1
      fi
    fi
    gcloud run jobs replace "$PRIOR_YAML" \
      --project "$PROJECT" \
      --region "$REGION" \
      --quiet || return 1
    # Keep RESTORE_NEEDED armed until exact UID/spec verification succeeds.
    verify_prior_job || return 1
  fi
}

release_lease() {
  if [[ "$LEASE_HELD" == "1" ]]; then
    gcloud storage rm "$LEASE_URI" --quiet || return 1
    LEASE_HELD=0
  fi
}

cleanup() {
  status=$?
  trap - EXIT INT TERM
  set +e
  if [[ "$RESTORE_NEEDED" == "1" ]]; then
    restore_job || status=1
  fi
  if [[ "$RESTORE_NEEDED" == "0" && "$LEASE_HELD" == "1" ]]; then
    release_lease || status=1
  fi
  if [[ "$status" == "0" && "$RESTORE_NEEDED" == "0" && "$LEASE_HELD" == "0" ]]; then
    rm -rf -- "$STATE_DIR"
  else
    printf 'boom-first launcher failed; recovery_state=%s\n' "$STATE_DIR" >&2
    printf 'recovery_prefix=%s\nlease_uri=%s\n' \
      "$RECOVERY_PREFIX" "$LEASE_URI" >&2
    if [[ -n "$EXECUTION" ]]; then
      printf 'launched_execution=%s\n' "$EXECUTION" >&2
    fi
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

if [[ ! "$IMAGE_URI" =~ ^${REGION}-docker\.pkg\.dev/${PROJECT}/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]]; then
  printf 'IMAGE_URI is not the immutable nfl-dfs image for %s/%s\n' \
    "$PROJECT" "$REGION" >&2
  exit 2
fi
if [[ ! "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  printf 'CODE_SHA must be the full 40-character lowercase commit SHA\n' >&2
  exit 2
fi

gcloud run jobs describe "$REUSED_JOB" \
  --project "$PROJECT" \
  --region "$REGION" \
  --format=export > "$PRIOR_YAML"
gcloud run jobs describe "$REUSED_JOB" \
  --project "$PROJECT" \
  --region "$REGION" \
  --format=json > "$PRIOR_JSON"

prior_uid="$(jq -r '.metadata.uid // empty' "$PRIOR_JSON")"
if [[ "$prior_uid" != "$REUSED_JOB_UID" ]]; then
  printf 'reusable job UID differs: %s\n' "$prior_uid" >&2
  exit 2
fi
prior_spec_sha="$(job_spec_sha "$PRIOR_JSON")"
prior_service_account="$(jq -r \
  '.spec.template.spec.template.spec.serviceAccountName // empty' \
  "$PRIOR_JSON")"
if [[ -z "$prior_service_account" ]]; then
  printf 'reusable job service account is absent\n' >&2
  exit 2
fi

running_count="$(gcloud run jobs executions list \
  --job "$REUSED_JOB" \
  --project "$PROJECT" \
  --region "$REGION" \
  --limit 100 \
  --format=json | jq '[.[] | select(.status.completionTime == null)] | length')"
if [[ "$running_count" != "0" ]]; then
  printf 'reusable job has %s unfinished execution(s)\n' "$running_count" >&2
  exit 2
fi

scheduler_refs="$(gcloud scheduler jobs list \
  --project "$PROJECT" \
  --location "$REGION" \
  --format=json | jq --arg job "$REUSED_JOB" \
  '[.[] | select((.httpTarget.uri // "") | contains($job))] | length')"
if [[ "$scheduler_refs" != "0" ]]; then
  printf 'reusable job is referenced by %s scheduler(s)\n' "$scheduler_refs" >&2
  exit 2
fi

# Serialize launchers with a create-only cloud lease. A stale lease is a
# deliberate fail-closed recovery signal; it must be reconciled, not expired
# automatically. Persist the pre-mutation spec remotely before changing state.
jq -n \
  --arg lease_id "$LEASE_ID" \
  --arg project "$PROJECT" \
  --arg region "$REGION" \
  --arg job "$REUSED_JOB" \
  --arg job_uid "$prior_uid" \
  --arg prior_spec_sha256 "$prior_spec_sha" \
  --arg image_uri "$IMAGE_URI" \
  --arg code_sha "$CODE_SHA" \
  '{schema_version:"boom-first-operator-lease/v1",lease_id:$lease_id,
    project:$project,region:$region,job:$job,job_uid:$job_uid,
    prior_spec_sha256:$prior_spec_sha256,image_uri:$image_uri,
    code_sha:$code_sha}' > "$LEASE_FILE"
gcloud storage cp "$LEASE_FILE" "$LEASE_URI" \
  --if-generation-match=0 --quiet
LEASE_HELD=1
gcloud storage cp "$PRIOR_YAML" "$RECOVERY_PREFIX/job-before.yaml" \
  --if-generation-match=0 --quiet
gcloud storage cp "$PRIOR_JSON" "$RECOVERY_PREFIX/job-before.json" \
  --if-generation-match=0 --quiet

# Close the preflight race for cooperating launchers and detect any manual
# update that landed between the first read and lease acquisition.
describe_job "$CURRENT_JSON"
current_uid="$(jq -r '.metadata.uid // empty' "$CURRENT_JSON")"
current_spec_sha="$(job_spec_sha "$CURRENT_JSON")"
if [[ "$current_uid" != "$prior_uid" || "$current_spec_sha" != "$prior_spec_sha" ]]; then
  printf 'reusable job changed during preflight\n' >&2
  exit 2
fi
running_count="$(gcloud run jobs executions list \
  --job "$REUSED_JOB" \
  --project "$PROJECT" \
  --region "$REGION" \
  --limit 100 \
  --format=json | jq '[.[] | select(.status.completionTime == null)] | length')"
if [[ "$running_count" != "0" ]]; then
  printf 'reusable job acquired an unfinished execution during preflight\n' >&2
  exit 2
fi

# Set the trap before the first mutation so every failure path restores the
# captured service account, command, image, environment and resources.
RESTORE_NEEDED=1
gcloud run jobs update "$REUSED_JOB" \
  --project "$PROJECT" \
  --region "$REGION" \
  --image "$IMAGE_URI" \
  --command nfl-dfs \
  --args shadow-boom-first-paired \
  --set-env-vars "GCP_PROJECT=${PROJECT},CODE_SHA=${CODE_SHA},IMAGE_URI=${IMAGE_URI}" \
  --cpu 4 \
  --memory 16Gi \
  --tasks 1 \
  --parallelism 1 \
  --max-retries 0 \
  --task-timeout 21600s \
  --quiet

describe_job "$TEMP_JSON"
temp_uid="$(jq -r '.metadata.uid // empty' "$TEMP_JSON")"
TEMP_SPEC_SHA="$(job_spec_sha "$TEMP_JSON")"
if [[ "$temp_uid" != "$prior_uid" ]]; then
  printf 'temporary reusable job UID differs\n' >&2
  exit 1
fi
jq -e \
  --arg image "$IMAGE_URI" \
  --arg code "$CODE_SHA" \
  --arg project "$PROJECT" \
  --arg service_account "$prior_service_account" '
    .spec.template.spec as $task |
    $task.template.spec as $spec |
    $spec.containers[0] as $container |
    (($container.env | map({key:.name,value:.value}) | from_entries) ==
      {GCP_PROJECT:$project,CODE_SHA:$code,IMAGE_URI:$image}) and
    ($container.image == $image) and
    ($container.command == ["nfl-dfs"]) and
    ($container.args == ["shadow-boom-first-paired"]) and
    ($container.resources.limits.cpu == "4") and
    ($container.resources.limits.memory == "16Gi") and
    ($task.taskCount == 1) and
    (($task.parallelism // 1) == 1) and
    ($spec.maxRetries == 0) and
    ($spec.timeoutSeconds == "21600") and
    ($spec.serviceAccountName == $service_account)
  ' "$TEMP_JSON" >/dev/null || {
    printf 'temporary reusable job contract differs\n' >&2
    exit 1
  }

EXECUTION="$(gcloud run jobs execute "$REUSED_JOB" \
  --project "$PROJECT" \
  --region "$REGION" \
  --async \
  --format='value(metadata.name)')"
if [[ -z "$EXECUTION" ]]; then
  printf 'Cloud Run did not return an execution identity\n' >&2
  exit 1
fi
printf 'launched_execution=%s\nrecovery_state=%s\nrecovery_prefix=%s\n' \
  "$EXECUTION" "$STATE_DIR" "$RECOVERY_PREFIX" >&2

gcloud run jobs executions describe "$EXECUTION" \
  --project "$PROJECT" \
  --region "$REGION" \
  --format=json > "$EXECUTION_JSON"
execution_uid="$(jq -r '.metadata.uid // empty' "$EXECUTION_JSON")"
execution_spec_sha="$(jq -S -c '.spec' "$EXECUTION_JSON" | \
  sha256sum | awk '{print $1}')"
if [[ -z "$execution_uid" ]]; then
  printf 'Cloud Run execution UID is absent\n' >&2
  exit 1
fi
jq -e \
  --arg job "$REUSED_JOB" \
  --arg job_uid "$prior_uid" \
  --arg image "$IMAGE_URI" \
  --arg code "$CODE_SHA" \
  --arg project "$PROJECT" \
  --arg service_account "$prior_service_account" '
    .spec as $execution |
    $execution.template.spec as $spec |
    $spec.containers[0] as $container |
    ((.metadata.labels["run.googleapis.com/job"] // "") == $job) and
    ((.metadata.labels["run.googleapis.com/jobUid"] // "") == $job_uid) and
    (($container.env | map({key:.name,value:.value}) | from_entries) ==
      {GCP_PROJECT:$project,CODE_SHA:$code,IMAGE_URI:$image}) and
    ($container.image == $image) and
    ($container.command == ["nfl-dfs"]) and
    ($container.args == ["shadow-boom-first-paired"]) and
    ($container.resources.limits.cpu == "4") and
    ($container.resources.limits.memory == "16Gi") and
    ($execution.taskCount == 1) and
    ($execution.parallelism == 1) and
    ($spec.maxRetries == 0) and
    ($spec.timeoutSeconds == "21600") and
    ($spec.serviceAccountName == $service_account)
  ' "$EXECUTION_JSON" >/dev/null || {
    printf 'created Cloud Run execution contract differs\n' >&2
    exit 1
  }
gcloud storage cp "$EXECUTION_JSON" \
  "$RECOVERY_PREFIX/execution-${EXECUTION}.json" \
  --if-generation-match=0 --quiet

# The execution now owns the temporary template snapshot. Restore the reusable
# job before returning control to the operator.
restore_job
release_lease

printf 'reused_job=%s\nreused_job_uid=%s\nexecution=%s\nexecution_uid=%s\nexecution_spec_sha256=%s\nimage=%s\ncode_sha=%s\nprior_spec_sha256=%s\nrestored_spec_sha256=%s\nrecovery_prefix=%s\nrestored=true\nlease_released=true\n' \
  "$REUSED_JOB" "$prior_uid" "$EXECUTION" "$execution_uid" \
  "$execution_spec_sha" "$IMAGE_URI" "$CODE_SHA" "$prior_spec_sha" \
  "$after_spec_sha" "$RECOVERY_PREFIX"
