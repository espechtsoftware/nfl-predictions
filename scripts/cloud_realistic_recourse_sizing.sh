#!/usr/bin/env bash
set -euo pipefail

# Deploy and execute the frozen 54-slate realistic-recourse sizing run.
# Usage: cloud_realistic_recourse_sizing.sh <image@sha256:...> <full-code-sha>

PROJECT=nfl-predictions-503414
REGION=us-central1
JOB=realistic-recourse-sizing-v1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-realistic-recourse-sizing-v1
OUTPUT_URI=$ROOT/result.json
PROPOSAL_URI=$ROOT/proposal-set.json

IMAGE=${1:-}
CODE_SHA=${2:-}
if [[ ! "$IMAGE" =~ @sha256:[0-9a-f]{64}$ ]]; then
  echo "ERROR: immutable image digest is required" >&2
  exit 2
fi
if [[ ! "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: full code SHA is required" >&2
  exit 2
fi
for target in "$OUTPUT_URI" "$PROPOSAL_URI"; do
  if gcloud storage objects describe "$target" --project "$PROJECT" >/dev/null 2>&1; then
    echo "ERROR: frozen create-only output already exists: $target" >&2
    exit 3
  fi
done

gcloud run jobs deploy "$JOB" \
  --project "$PROJECT" \
  --region "$REGION" \
  --image "$IMAGE" \
  --command python \
  --args scripts/run_realistic_recourse_sizing.py,--output-uri,"$OUTPUT_URI",--proposal-uri,"$PROPOSAL_URI" \
  --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
  --service-account "$SERVICE_ACCOUNT" \
  --cpu 8 \
  --memory 32Gi \
  --tasks 1 \
  --parallelism 1 \
  --max-retries 0 \
  --task-timeout 4h \
  --quiet

gcloud run jobs execute "$JOB" \
  --project "$PROJECT" \
  --region "$REGION" \
  --async \
  --format='value(metadata.name)'
