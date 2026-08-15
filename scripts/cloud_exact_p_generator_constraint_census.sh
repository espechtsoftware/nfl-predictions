#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_exact_p_generator_constraint_census.sh <image@sha256:...> <full-code-sha>

PROJECT=nfl-predictions-503414
REGION=us-central1
JOB=exact-p-generator-constraint-census-v1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
OUTPUT_URI=gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-exact-p-generator-constraint-census-v1/result.json

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
if gcloud storage objects describe "$OUTPUT_URI" \
    --project "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: frozen create-only output already exists: $OUTPUT_URI" >&2
  exit 3
fi

gcloud run jobs deploy "$JOB" \
  --project "$PROJECT" \
  --region "$REGION" \
  --image "$IMAGE" \
  --command python \
  --args scripts/run_exact_p_generator_constraint_census.py,--output-uri,"$OUTPUT_URI" \
  --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
  --service-account "$SERVICE_ACCOUNT" \
  --cpu 8 \
  --memory 32Gi \
  --tasks 1 \
  --parallelism 1 \
  --max-retries 0 \
  --task-timeout 2h \
  --quiet

gcloud run jobs execute "$JOB" \
  --project "$PROJECT" \
  --region "$REGION" \
  --async \
  --format='value(metadata.name)'
