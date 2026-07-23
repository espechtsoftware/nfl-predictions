#!/usr/bin/env bash
# Build the container and (re)create Cloud Run Jobs + Cloud Scheduler triggers.
# Cadences follow the guide §11.
set -euo pipefail

PROJECT="${GCP_PROJECT:-nfl-dfs-prod}"
REGION="${REGION:-us-central1}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/nfl-dfs/nfl-dfs:latest"
SA="nfl-dfs-jobs@${PROJECT}.iam.gserviceaccount.com"

gcloud artifacts repositories create nfl-dfs --repository-format=docker \
  --location="$REGION" 2>/dev/null || true
gcloud builds submit --tag "$IMAGE" .

job() {  # name, module, schedule, [args]
  local name=$1 module=$2 schedule=$3 args=${4:-}
  gcloud run jobs deploy "$name" \
    --image "$IMAGE" \
    --region "$REGION" \
    --service-account "$SA" \
    --set-env-vars "GCP_PROJECT=${PROJECT}" \
    --command python3 --args="-m,${module}${args:+,$args}" \
    --max-retries 1 --task-timeout 3600
  gcloud scheduler jobs create http "trigger-${name}" \
    --location "$REGION" \
    --schedule "$schedule" \
    --time-zone "America/Chicago" \
    --uri "https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${name}:run" \
    --http-method POST \
    --oauth-service-account-email "$SA" 2>/dev/null || \
  gcloud scheduler jobs update http "trigger-${name}" \
    --location "$REGION" --schedule "$schedule" --time-zone "America/Chicago"
}

# §11 orchestration schedule (times in CT)
job ingest-nflverse  nfl_dfs.ingest.nflverse_job   "0 6 * * *"
job ingest-dk-slate  nfl_dfs.ingest.dk_job         "0 * * * 4,5,6,0"     # hourly Thu-Sun
job ingest-dk-mon    nfl_dfs.ingest.dk_job         "0 0-4 * * 1"         # Mon 00-04
job ingest-odds      nfl_dfs.ingest.odds_job       "30 * * * 4,5,6,0"
job ingest-weather   nfl_dfs.ingest.weather_job    "0 6,12,18 * * 5,6,0" # 3x daily Fri-Sun
job build-features   nfl_dfs.features.build        "0 7 * * *"
job run-projections  nfl_dfs.inference.run_projections "0 8 * * 2"       # Tue initial
job run-projections-wknd nfl_dfs.inference.run_projections "0 * * * 6,0" # hourly Sat-Sun (late swap)
job retrain-models   nfl_dfs.models.train_job      "0 9 * * 2"           # Tue after new week lands
