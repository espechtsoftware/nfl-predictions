#!/usr/bin/env bash
# Deploy the two isolated prospective SIS pass-tail GPU cache jobs/schedulers.
set -euo pipefail

PROJECT="${GCP_PROJECT:?set GCP_PROJECT}"
REGION="${REGION:-us-central1}"
CODE_SHA="${CODE_SHA:-$(git rev-parse --short=12 HEAD)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/nfl-dfs/tabpfn-sis-pass-tail-live:${CODE_SHA}"
SA="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"

case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable CODE_SHA required"; exit 2 ;;
esac

gcloud builds submit --project "$PROJECT" \
  --config scripts/tabpfn_sis_pass_tail_live/cloudbuild.yaml \
  --substitutions "_IMAGE=${IMAGE}" .

deploy_arm() {
  local arm=$1
  local job="tabpfn-sis-pass-tail-live-${arm}"
  local table="tabpfn_sis_pass_tail_live_${arm}_v1"
  gcloud run jobs deploy "$job" --project "$PROJECT" --region "$REGION" \
    --image "$IMAGE" \
    --set-env-vars "GCP_PROJECT=${PROJECT},TABPFN_SIS_PASS_TAIL_LIVE_ARM=${arm},TABPFN_OUTPUT_TABLE=${table},TABPFN_UPCOMING=auto,CODE_SHA=${CODE_SHA}" \
    --memory 16Gi --cpu 4 --gpu 1 --gpu-type nvidia-l4 \
    --no-gpu-zonal-redundancy --max-retries 0 --task-timeout 3600 \
    --service-account "$SA"
  local scheduler="s-tabpfn-sis-pass-tail-${arm}"
  local minute=15
  [ "$arm" = treatment ] && minute=20
  gcloud scheduler jobs create http "$scheduler" --location "$REGION" \
    --schedule "${minute} 9 * * 4" --time-zone America/Chicago \
    --uri "https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/${job}:run" \
    --http-method POST --oauth-service-account-email "$SA" 2>/dev/null || \
  gcloud scheduler jobs update http "$scheduler" --location "$REGION" \
    --schedule "${minute} 9 * * 4" --time-zone America/Chicago
}

deploy_arm control
deploy_arm treatment

echo "Deployed prospective SIS pass-tail cache pair at ${IMAGE}."
echo "Keep both schedulers paused until the forensic cleanup/resume gate."

