#!/usr/bin/env bash
set -euo pipefail

# Thin operator for the reviewed R6 full-union freeze. Invoke it only from an
# exact clean checkout of R6_FREEZE_CODE_SHA. It reuses the two registered
# Cloud Run jobs and never creates a job, lists science objects, or reads an
# outcome.

stage="${1:-}"
case "$stage" in
  build|prepare|canary|launch|status|repair|finish) ;;
  *)
    echo "usage: $0 {build|prepare|canary|launch|status|repair|finish} [ordinal]" >&2
    exit 2
    ;;
esac

: "${R6_FREEZE_CODE_SHA:?set R6_FREEZE_CODE_SHA}"
: "${R6_FREEZE_RUN_DIR:?set R6_FREEZE_RUN_DIR}"

repository_root="$(git rev-parse --show-toplevel)"
resolved_run_dir="$(realpath -m "$R6_FREEZE_RUN_DIR")"
case "${resolved_run_dir}/" in
  "${repository_root}/"*)
    echo "R6_FREEZE_RUN_DIR must be outside the exact clean checkout" >&2
    exit 2
    ;;
esac
R6_FREEZE_RUN_DIR="$resolved_run_dir"

project="nfl-predictions-503414"
project_number="817589974517"
region="us-central1"
service_account="817589974517-compute@developer.gserviceaccount.com"
job_a="atlas-minimal-c-s2023-w1-v1"
job_b="atlas-cbc-32g-full-2023-w8-v1"
image_repository="us-central1-docker.pkg.dev/${project}/nfl-dfs/nfl-dfs"
output_prefix="gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-full-union-freezes/20260826-foundry-v12-r6-full-union-freeze-v1/"
panel_uri="gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/panels/20260823-foundry-production-v12/foundry-v12-combined-panel-index-v1.json"
panel_generation="1787663639938214"
panel_sha256="4d41acd9277e525cd8521071b62390281c442d6324db1e3f5812bf59920c16f9"
panel_bytes="209279"
freeze_cli="scripts/run_corpus_r6_full_union_panel_freeze_v1.py"

mkdir -p "$R6_FREEZE_RUN_DIR"

observed_head="$(git rev-parse --verify HEAD)"
test "$observed_head" = "$R6_FREEZE_CODE_SHA"
test -z "$(git status --porcelain=v1 --untracked-files=all)"

if [[ "$stage" == "build" ]]; then
  gcloud builds submit --no-source \
    --project "$project" \
    --region "$region" \
    --config cloudbuild.r6-full-union-freeze.yaml \
    --substitutions "_SOURCE_COMMIT=${R6_FREEZE_CODE_SHA},_IMAGE_REPOSITORY=${image_repository}" \
    --format=json >"${R6_FREEZE_RUN_DIR}/build.json"
  jq -e '.status == "SUCCESS"' "${R6_FREEZE_RUN_DIR}/build.json" >/dev/null
  jq -er '.results.images[0] | .name + "@" + .digest' \
    "${R6_FREEZE_RUN_DIR}/build.json" \
    >"${R6_FREEZE_RUN_DIR}/immutable-image.txt"
  exit 0
fi

: "${R6_FREEZE_IMAGE:?set R6_FREEZE_IMAGE to the resolved digest}"
case "$R6_FREEZE_IMAGE" in
  "${image_repository}@sha256:"????????????????????????????????????????????????????????????????) ;;
  *) echo "R6_FREEZE_IMAGE must be the resolved repository digest" >&2; exit 2 ;;
esac

: "${R6_FREEZE_PYTHON:?set R6_FREEZE_PYTHON to the trusted venv python}"
test -x "$R6_FREEZE_PYTHON"

run_cli() {
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${PWD}/src" \
    "$R6_FREEZE_PYTHON" "$freeze_cli" --project "$project" "$@"
}

if [[ "$stage" == "prepare" ]]; then
  R6_FULL_UNION_PANEL_FREEZE_PRODUCTION_ENABLED=1 run_cli \
    prepare --execute \
    --panel-uri "$panel_uri" \
    --panel-generation "$panel_generation" \
    --panel-sha256 "$panel_sha256" \
    --panel-bytes "$panel_bytes" \
    --source-commit-sha "$R6_FREEZE_CODE_SHA" \
    --immutable-image "$R6_FREEZE_IMAGE" \
    --output-prefix "$output_prefix" \
    >"${R6_FREEZE_RUN_DIR}/prepare.json"
  jq -e '.source_slate_count == 54 and .rank_80_book_count == 2592 and .prefix_count == 7776' \
    "${R6_FREEZE_RUN_DIR}/prepare.json" >/dev/null
  exit 0
fi

prepare_receipt="${R6_FREEZE_RUN_DIR}/prepare.json"
test -f "$prepare_receipt"
manifest_uri="$(jq -er '.manifest_identity.uri' "$prepare_receipt")"
manifest_generation="$(jq -er '.manifest_identity.generation' "$prepare_receipt")"
manifest_sha256="$(jq -er '.manifest_identity.sha256' "$prepare_receipt")"
manifest_bytes="$(jq -er '.manifest_identity.bytes' "$prepare_receipt")"

manifest_args=(
  --manifest-uri "$manifest_uri"
  --manifest-generation "$manifest_generation"
  --manifest-sha256 "$manifest_sha256"
  --manifest-bytes "$manifest_bytes"
)

clear_job() {
  gcloud run jobs update "$1" \
    --project "$project" --region "$region" \
    --clear-env-vars --clear-secrets --clear-volumes --clear-volume-mounts \
    --clear-cloudsql-instances --clear-vpc-connector --clear-network \
    --quiet >/dev/null
}

configure_job() {
  local job="$1"
  local task_count="$2"
  local parallelism="$3"
  local cloud_args="$4"
  gcloud run jobs update "$job" \
    --project "$project" --region "$region" \
    --image "$R6_FREEZE_IMAGE" --service-account "$service_account" \
    --cpu 4 --memory 16Gi --tasks "$task_count" \
    --parallelism "$parallelism" --max-retries 0 --task-timeout 7200s \
    --command python --args="$cloud_args" \
    --set-env-vars "R6_FULL_UNION_PANEL_FREEZE_PRODUCTION_ENABLED=1,R6_FULL_UNION_PANEL_FREEZE_RUNTIME_IMAGE=${R6_FREEZE_IMAGE}" \
    --quiet >/dev/null
}

require_terminal_execution() {
  local execution_file="$1"
  local label="$2"
  test -s "$execution_file"
  local execution
  execution="$(tr -d '\n' <"$execution_file")"
  gcloud run jobs executions describe "$execution" \
    --project "$project" --region "$region" --format=json \
    >"${R6_FREEZE_RUN_DIR}/${label}-terminal.json"
  jq -e '
    (.status.completionTime | type == "string" and endswith("Z"))
    and ([.status.conditions[]? | select(.type == "Completed") | .status]
      | length == 1 and (.[0] == "True" or .[0] == "False"))
  ' "${R6_FREEZE_RUN_DIR}/${label}-terminal.json" >/dev/null
}

common_csv="${freeze_cli},--project,${project},run-slate,--execute,--manifest-uri,${manifest_uri},--manifest-generation,${manifest_generation},--manifest-sha256,${manifest_sha256},--manifest-bytes,${manifest_bytes}"
binding_csv="--expected-source-commit-sha,${R6_FREEZE_CODE_SHA},--expected-immutable-image,${R6_FREEZE_IMAGE},--expected-project-number,${project_number},--expected-region,${region}"

if [[ "$stage" == "canary" ]]; then
  clear_job "$job_a"
  configure_job "$job_a" 1 1 \
    "${common_csv},--source-ordinal,0,${binding_csv}"
  gcloud run jobs execute "$job_a" \
    --project "$project" --region "$region" --wait \
    --tasks 1 --task-timeout 7200s --format='value(metadata.name)' \
    >"${R6_FREEZE_RUN_DIR}/canary-execution.txt"
  run_cli status "${manifest_args[@]}" \
    >"${R6_FREEZE_RUN_DIR}/status-after-canary.json"
  jq -e '
    .completed_source_ordinals == [0]
    and .result_only_source_ordinals == []
    and .missing_source_ordinals == [range(1;54)]
    and .rank_80_book_count == 48
    and .prefix_count == 144
    and .root_ready == false
  ' "${R6_FREEZE_RUN_DIR}/status-after-canary.json" >/dev/null
  exit 0
fi

if [[ "$stage" == "launch" ]]; then
  test -s "${R6_FREEZE_RUN_DIR}/canary-execution.txt"
  run_cli status "${manifest_args[@]}" \
    >"${R6_FREEZE_RUN_DIR}/status-before-launch.json"
  if [[ ! -s "${R6_FREEZE_RUN_DIR}/lane-a-execution.txt" \
        && ! -e "${R6_FREEZE_RUN_DIR}/lane-a-submission-pending.json" \
        && ! -s "${R6_FREEZE_RUN_DIR}/lane-b-execution.txt" \
        && ! -e "${R6_FREEZE_RUN_DIR}/lane-b-submission-pending.json" ]]; then
    jq -e '
      .completed_source_ordinals == [0]
      and .result_only_source_ordinals == []
      and .missing_source_ordinals == [range(1;54)]
      and .rank_80_book_count == 48
      and .prefix_count == 144
      and .root_ready == false
    ' "${R6_FREEZE_RUN_DIR}/status-before-launch.json" >/dev/null
  else
    jq -e '
      (.completed_source_ordinals | index(0)) != null
      and .rank_80_book_count == (.completed_slate_count * 48)
      and .prefix_count == (.completed_slate_count * 144)
    ' "${R6_FREEZE_RUN_DIR}/status-before-launch.json" >/dev/null
  fi
  configure_job "$job_a" 28 4 \
    "${common_csv},--source-offset,0,${binding_csv}"
  clear_job "$job_b"
  configure_job "$job_b" 26 4 \
    "${common_csv},--source-offset,28,${binding_csv}"
  if [[ ! -s "${R6_FREEZE_RUN_DIR}/lane-a-execution.txt" ]]; then
    test ! -e "${R6_FREEZE_RUN_DIR}/lane-a-submission-pending.json"
    jq -cn --arg job "$job_a" --arg code_sha "$R6_FREEZE_CODE_SHA" \
      --arg image "$R6_FREEZE_IMAGE" \
      '{lane:"A",job:$job,code_sha:$code_sha,image:$image,submission_pending:true}' \
      >"${R6_FREEZE_RUN_DIR}/lane-a-submission-pending.json"
    gcloud run jobs execute "$job_a" \
      --project "$project" --region "$region" --async \
      --tasks 28 --task-timeout 7200s --format='value(metadata.name)' \
      >"${R6_FREEZE_RUN_DIR}/lane-a-execution.txt"
    grep -Eq '^atlas-minimal-c-s2023-w1-v1-[a-z0-9]+$' \
      "${R6_FREEZE_RUN_DIR}/lane-a-execution.txt"
  fi
  if [[ ! -s "${R6_FREEZE_RUN_DIR}/lane-b-execution.txt" ]]; then
    test ! -e "${R6_FREEZE_RUN_DIR}/lane-b-submission-pending.json"
    jq -cn --arg job "$job_b" --arg code_sha "$R6_FREEZE_CODE_SHA" \
      --arg image "$R6_FREEZE_IMAGE" \
      '{lane:"B",job:$job,code_sha:$code_sha,image:$image,submission_pending:true}' \
      >"${R6_FREEZE_RUN_DIR}/lane-b-submission-pending.json"
    gcloud run jobs execute "$job_b" \
      --project "$project" --region "$region" --async \
      --tasks 26 --task-timeout 7200s --format='value(metadata.name)' \
      >"${R6_FREEZE_RUN_DIR}/lane-b-execution.txt"
    grep -Eq '^atlas-cbc-32g-full-2023-w8-v1-[a-z0-9]+$' \
      "${R6_FREEZE_RUN_DIR}/lane-b-execution.txt"
  fi
  exit 0
fi

if [[ "$stage" == "status" ]]; then
  run_cli status "${manifest_args[@]}" \
    >"${R6_FREEZE_RUN_DIR}/status.json"
  jq '{completed_slate_count,result_only_source_ordinals,missing_source_ordinals,rank_80_book_count,prefix_count,root_ready}' \
    "${R6_FREEZE_RUN_DIR}/status.json"
  exit 0
fi

if [[ "$stage" == "repair" ]]; then
  repair_ordinal="${2:-}"
  [[ "$repair_ordinal" =~ ^([0-9]|[1-4][0-9]|5[0-3])$ ]]
  require_terminal_execution \
    "${R6_FREEZE_RUN_DIR}/lane-a-execution.txt" "lane-a"
  require_terminal_execution \
    "${R6_FREEZE_RUN_DIR}/lane-b-execution.txt" "lane-b"
  run_cli status "${manifest_args[@]}" \
    >"${R6_FREEZE_RUN_DIR}/status-before-repair-${repair_ordinal}.json"
  jq -e --argjson ordinal "$repair_ordinal" '
    ([.missing_source_ordinals[], .result_only_source_ordinals[]]
      | index($ordinal)) != null
  ' "${R6_FREEZE_RUN_DIR}/status-before-repair-${repair_ordinal}.json" \
    >/dev/null
  repair_job="$job_a"
  if (( repair_ordinal >= 28 )); then
    repair_job="$job_b"
  fi
  clear_job "$repair_job"
  configure_job "$repair_job" 1 1 \
    "${common_csv},--source-ordinal,${repair_ordinal},${binding_csv}"
  gcloud run jobs execute "$repair_job" \
    --project "$project" --region "$region" --wait \
    --tasks 1 --task-timeout 7200s --format='value(metadata.name)' \
    >"${R6_FREEZE_RUN_DIR}/repair-${repair_ordinal}-execution.txt"
  exit 0
fi

run_cli status "${manifest_args[@]}" >"${R6_FREEZE_RUN_DIR}/status-before-finish.json"
jq -e '
  .completed_slate_count == 54
  and .result_only_source_ordinals == []
  and .missing_source_ordinals == []
  and .rank_80_book_count == 2592
  and .prefix_count == 7776
  and .root_ready == true
' "${R6_FREEZE_RUN_DIR}/status-before-finish.json" >/dev/null
R6_FULL_UNION_PANEL_FREEZE_PRODUCTION_ENABLED=1 \
R6_FULL_UNION_PANEL_FREEZE_RUNTIME_IMAGE="$R6_FREEZE_IMAGE" \
  run_cli finish-panel --execute "${manifest_args[@]}" \
  --expected-source-commit-sha "$R6_FREEZE_CODE_SHA" \
  --expected-immutable-image "$R6_FREEZE_IMAGE" \
  >"${R6_FREEZE_RUN_DIR}/finish.json"
jq -e '
  .source_slate_count == 54
  and .rank_80_book_count == 2592
  and .prefix_count == 7776
  and .outcome_key_projection_inputs_frozen == true
  and .uses_realized_outcomes == false
' "${R6_FREEZE_RUN_DIR}/finish.json" >/dev/null
