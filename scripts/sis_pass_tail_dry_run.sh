#!/usr/bin/env bash
# O-3 (2026-10-05): ONE outcome-blind dry run of one SIS pass-tail job.
#
#   scripts/sis_pass_tail_dry_run.sh <job>
#
# It re-executes itself under the ONE production launcher registry
# (scripts/launcher_registry.sh, CLAUDE.md rule 6): --root is the canonical
# production checkout, so the lane state lives in its .tmp (never the lab
# registry root); the lane is the Cloud Run job's own name.
#
# SHADOW_DRY_RUN=1 is an EXECUTION-scoped override: the job's own env is not
# changed. The cache jobs then write only tabpfn_sis_pass_tail_live_<arm>_v1_dryrun
# (replaced each dry run); the paired job reads those copies, writes
# gs://<raw>/<identity>_dryrun/..., candidate rows with a *_dryrun run type and
# panel ids prefixed dryrun-, and no own_shadow rows. Nothing a graded reader
# selects is touched.
set -euo pipefail

project="${GCP_PROJECT:-nfl-predictions-503414}"
region="${REGION:-us-central1}"
registry_root="${NFL_PRODUCTION_ROOT:-/home/erich/projects/nfl-predictions}"
script_path="$(readlink -f "${BASH_SOURCE[0]}")"
script_root="$(cd "$(dirname "$script_path")/.." && pwd -P)"
job="${1:-}"

case "$job" in
  tabpfn-sis-pass-tail-live-control|tabpfn-sis-pass-tail-live-treatment)
    contract="pass-tail-v1-a1" ;;
  shadow-sis-pass-tail-paired)
    contract="pass-tail-v1-a1-companion" ;;
  *) echo "usage: $0 tabpfn-sis-pass-tail-live-{control,treatment}|shadow-sis-pass-tail-paired" >&2
     exit 2 ;;
esac

if [[ -z "${NFL_LAUNCHER_REGISTRY_RECEIPT:-}" ]]; then
  exec "$script_root/scripts/launcher_registry.sh" run \
    --root "$registry_root" \
    --lane "$job" \
    --owner production \
    --target-prefixes "$job" \
    -- "$script_path" "$job"
fi
expected_state="$(cd "$registry_root/.tmp" && pwd -P)"
if [[ "${NFL_LAUNCHER_REGISTRY_LANE:-}" != "$job" \
      || "${NFL_LAUNCHER_REGISTRY_STATE_ROOT:-}" != "$expected_state" ]]; then
  echo "refusing: lane '${NFL_LAUNCHER_REGISTRY_LANE:-}' / state '${NFL_LAUNCHER_REGISTRY_STATE_ROOT:-}'" \
       "is not the production registry lane ${job} under ${expected_state}" >&2
  exit 2
fi

declared="$(gcloud run jobs describe "$job" --project "$project" --region "$region" \
  --format=json | jq -r '.spec.template.spec.template.spec.containers[0].env[]
    | select(.name == "SIS_PASS_TAIL_CONTRACT") | .value')"
if [[ "$declared" != "$contract" ]]; then
  echo "refusing: $job declares SIS_PASS_TAIL_CONTRACT='${declared}', not ${contract};" \
       "update the job (image + env together) first" >&2
  exit 2
fi

started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "dry run: job=$job contract=$contract started=$started"
execution="$(gcloud run jobs execute "$job" --project "$project" --region "$region" \
  --update-env-vars SHADOW_DRY_RUN=1 --wait --format='value(metadata.name)')"
echo "execution=$execution"
gcloud run jobs executions describe "$execution" --project "$project" --region "$region" \
  --format='value(status.completionTime,status.succeededCount,status.failedCount)'
echo "receipt (log lines carrying the contract):"
gcloud logging read \
  "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"$job\" AND labels.\"run.googleapis.com/execution_name\"=\"$execution\"" \
  --project "$project" --limit 400 --order asc --format='value(textPayload)' \
  | grep -E 'TABPFN_SIS_PASS_TAIL_LIVE_JSON=|"contract"|"dry_run"|"disposition"|"feature_snapshot"|"draft_group|"manifest_uri"|"pool"|"marginal_reads"|"empty_fallbacks"' \
  || true
