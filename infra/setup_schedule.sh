#!/usr/bin/env bash
# In-season GCP setup (idempotent): dashboard service, one Cloud Run job
# per pipeline command, Cloud Scheduler cadence. Rerun any time — creates
# or updates in place. Requires: image pushed, .env exported (ODDS_API_KEY,
# ANTHROPIC_API_KEY) in the calling shell.
set -euo pipefail
PROJECT=nfl-predictions-503414
REGION=us-central1
IMG=us-central1-docker.pkg.dev/$PROJECT/nfl-dfs/nfl-dfs:latest
SA=$(gcloud iam service-accounts list --project $PROJECT \
     --filter="displayName:Compute Engine default" --format="value(email)")
ENVV="GCP_PROJECT=$PROJECT,ODDS_API_KEY=${ODDS_API_KEY:?},ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}"

job() {  # name, command, cpu, memory
  local name=$1 cmd=$2 cpu=${3:-1} mem=${4:-2Gi}
  if gcloud run jobs describe "$name" --region $REGION --project $PROJECT >/dev/null 2>&1; then
    gcloud run jobs update "$name" --image "$IMG" --region $REGION \
      --project $PROJECT --args "$cmd" --cpu "$cpu" --memory "$mem" \
      --task-timeout 3600 --set-env-vars "$ENVV" --quiet
  else
    gcloud run jobs create "$name" --image "$IMG" --region $REGION \
      --project $PROJECT --command nfl-dfs --args "$cmd" --cpu "$cpu" \
      --memory "$mem" --task-timeout 3600 --set-env-vars "$ENVV" --quiet
  fi
}

sched() {  # name, cron, jobname
  local name=$1 cron=$2 target=$3
  local uri="https://run.googleapis.com/v2/projects/$PROJECT/locations/$REGION/jobs/$target:run"
  if gcloud scheduler jobs describe "$name" --location $REGION --project $PROJECT >/dev/null 2>&1; then
    gcloud scheduler jobs update http "$name" --location $REGION --project $PROJECT \
      --schedule "$cron" --uri "$uri" --oauth-service-account-email "$SA" --quiet
  else
    gcloud scheduler jobs create http "$name" --location $REGION --project $PROJECT \
      --schedule "$cron" --uri "$uri" --http-method POST \
      --oauth-service-account-email "$SA" --time-zone "America/Chicago" --quiet
  fi
}

gcloud services enable cloudscheduler.googleapis.com --project $PROJECT --quiet

# Pipeline jobs
job ingest-nflverse ingest-nflverse
job build-features  build-features 2 4Gi
job train-weekly    train 4 8Gi
job project-slate   project 2 4Gi
job ingest-dk       ingest-dk
job ingest-odds     ingest-odds
job ingest-props    ingest-props
job ingest-weather  ingest-weather
job trends-alerts   trends

# Cadence (America/Chicago). Tuesday chain is staggered, not chained —
# each step reads whatever the previous wrote; an hour apart is plenty.
sched s-nflverse   "0 5 * * 2"        ingest-nflverse   # Tue 05:00
sched s-features   "30 6 * * 2"       build-features    # Tue 06:30
sched s-train      "30 7 * * 2"       train-weekly      # Tue 07:30
sched s-project-tu "30 9 * * 2"       project-slate     # Tue 09:30
sched s-dk         "0 10 * * 3-7"     ingest-dk         # Wed-Sun 10:00
sched s-odds       "0 9,15 * * 3-7"   ingest-odds       # Wed-Sun 9a+3p
sched s-props      "30 9 * * 3-7"     ingest-props      # Wed-Sun 09:30
sched s-weather    "0 8 * * 5-7"      ingest-weather    # Fri-Sun 08:00
sched s-trends     "0 11 * * 3"       trends-alerts     # Wed 11:00
sched s-project-su "0 6-11 * * 7"     project-slate     # Sun hourly 6-11a

# Dashboard service (auth required — your Google login via proxy or IAP)
gcloud run deploy nfl-dfs-app --image "$IMG" --region $REGION \
  --project $PROJECT --command nfl-dfs --args serve --port 8080 \
  --cpu 1 --memory 1Gi --min-instances 0 --no-allow-unauthenticated \
  --set-env-vars "$ENVV" --quiet
echo "DONE. Dashboard: gcloud run services proxy nfl-dfs-app --region $REGION"
