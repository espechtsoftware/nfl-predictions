#!/usr/bin/env bash
# One-time GCP project setup. Idempotent.
set -euo pipefail

PROJECT="${GCP_PROJECT:-nfl-dfs-prod}"
LOCATION="${BQ_LOCATION:-US}"
BUCKET="${GCS_BUCKET:-${PROJECT}-raw}"

gcloud config set project "$PROJECT"
gcloud services enable \
  bigquery.googleapis.com \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com

for ds in nfl_raw nfl_features nfl_predictions; do
  bq mk --dataset --location="$LOCATION" "${PROJECT}:${ds}" 2>/dev/null || true
done

gsutil mb -l "$LOCATION" "gs://${BUCKET}" 2>/dev/null || true

echo "Applying raw DDL..."
for f in "$(dirname "$0")/../sql/raw/"*.sql; do
  sed -e "s/\${raw}/${PROJECT}.nfl_raw/g" \
      -e "s/\${features}/${PROJECT}.nfl_features/g" \
      -e "s/\${predictions}/${PROJECT}.nfl_predictions/g" "$f" | bq query --use_legacy_sql=false
done

echo "Done. Next: build + deploy jobs with deploy/deploy_jobs.sh, then run"
echo "  gcloud run jobs execute ingest-nflverse --args=--full   # backfill"
