#!/usr/bin/env bash
# Cloud Run Jobs + Cloud Scheduler for nfl-dfs — reconciled with LIVE
# infrastructure 2026-08-01 (the previous version described an aspirational
# deployment that never matched production; see git history).
#
# Conventions (match every live job):
#   - container command is the `nfl-dfs` CLI (not python -m)
#   - schedulers are named s-<short>, POST to the v2 run API, oauth as the
#     default compute SA, timezone America/Chicago
#   - jobs pin the image DIGEST at deploy time: after building a new
#     :latest, re-run the deploy for any job that should pick it up
#
# Secrets come from the caller's environment (ODDS_API_KEY, ANTHROPIC_API_KEY).
# Idempotent: `gcloud run jobs deploy` upserts; scheduler create || update.
set -euo pipefail

PROJECT="${GCP_PROJECT:?set GCP_PROJECT}"
REGION="${REGION:-us-central1}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/nfl-dfs/nfl-dfs:latest"
CODE_SHA="${CODE_SHA:-$(git rev-parse --short=12 HEAD 2>/dev/null || true)}"
SA="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"

build() { gcloud builds submit --tag "$IMAGE" .; }

job() {  # name, cli-args (comma-separated), memory, cpu, extra-env (| separated)
  local name=$1 args=$2 mem=${3:-2Gi} cpu=${4:-1} extra=${5:-}
  gcloud run jobs deploy "$name" --image "$IMAGE" --region "$REGION" \
    --command nfl-dfs --args "$args" \
    --set-env-vars "^|^GCP_PROJECT=${PROJECT}${extra:+|$extra}" \
    --memory "$mem" --cpu "$cpu" --max-retries 1 --task-timeout 3600
}

sched() {  # scheduler-name, job-name, cron
  local sname=$1 jname=$2 cron=$3
  gcloud scheduler jobs create http "$sname" --location "$REGION" \
    --schedule "$cron" --time-zone "America/Chicago" \
    --uri "https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/${jname}:run" \
    --http-method POST --oauth-service-account-email "$SA" 2>/dev/null || \
  gcloud scheduler jobs update http "$sname" --location "$REGION" --schedule "$cron"
}

build

# --- Ingestion ---------------------------------------------------------------
job ingest-nflverse  ingest-nflverse 4Gi 1 "ODDS_API_KEY=${ODDS_API_KEY:-}"
job ingest-dk        ingest-dk       2Gi 1 "ODDS_API_KEY=${ODDS_API_KEY:-}"
job ingest-odds      ingest-odds     2Gi 1 "ODDS_API_KEY=${ODDS_API_KEY:-}"
job ingest-props     ingest-props    2Gi 1 "ODDS_API_KEY=${ODDS_API_KEY:-}"
job ingest-weather   ingest-weather
job ingest-cfb       ingest-cfb      2Gi 1 "INGEST_CFB_ENABLED=1"
# --- Pipeline ----------------------------------------------------------------
job build-features   build-features
job train-weekly     train           8Gi 4
# Tail-first research baseline: isolated registry labels mean this K=1
# retrain cannot overwrite the canonical K=3 models loaded by the app.
job train-weekly-k1  train           8Gi 4 "MODEL_ENSEMBLE=1|MODEL_REGISTRY_VARIANT=tail_k1"
job project-slate    project         4Gi 2 "GAME_SIM_MODE=possession"
# Prospective evidence only: fixed true-80/194 Sunday-main book, synchronous
# persistence, no user notes, and no projection/live-app mutation.
job shadow-k1        shadow-k1       8Gi 4 "MODEL_ENSEMBLE=1|MODEL_REGISTRY_VARIANT=tail_k1|GAME_SIM_MODE=possession|N_CE=0|N_EPISTEMIC=0|N_GUMBEL=0|N_BOOM=40|MIN_LINEUP_SALARY=49000|BLEND_MODEL_WEIGHT=0.45|LIVE_SIMS=30000|CAND_ARTIFACT_BUCKET=${PROJECT}-raw|CODE_SHA=${CODE_SHA}"
job shadow-k3        shadow-k3       8Gi 4 "MODEL_ENSEMBLE=3|MODEL_REGISTRY_VARIANT=canonical|GAME_SIM_MODE=possession|N_CE=0|N_EPISTEMIC=0|N_GUMBEL=0|N_BOOM=40|MIN_LINEUP_SALARY=49000|BLEND_MODEL_WEIGHT=0.45|LIVE_SIMS=30000|CAND_ARTIFACT_BUCKET=${PROJECT}-raw|CODE_SHA=${CODE_SHA}"
job score-entries    score-entries
job trends-alerts    trends
job check-freshness  check-freshness 1Gi 1

# --- Schedules (live cadences; seasonal pauses managed by the README §11
# runbook: s-nflverse/s-features/s-train*/s-project-*/s-shadow-k[13]-* are PAUSED in the
# off-season and resumed ~Aug 24) --------------------------------------------
sched s-nflverse    ingest-nflverse "0 5 * * 2"
sched s-features    build-features  "30 6 * * 2"
sched s-train       train-weekly    "30 7 * * 2"
sched s-train-k1    train-weekly-k1 "30 8 * * 2"
sched s-project-tu  project-slate   "30 9 * * 2"
sched s-project-su  project-slate   "0 6-11 * * 7"
# Two pre-lock snapshots: the early run is resilient to a late-run failure;
# the later one incorporates most Sunday inactive/market information.
sched s-shadow-k1-early shadow-k1   "30 10 * * 7"
sched s-shadow-k1-late  shadow-k1   "20 11 * * 7"
sched s-shadow-k3-early shadow-k3   "30 10 * * 7"
sched s-shadow-k3-late  shadow-k3   "20 11 * * 7"
sched s-dk          ingest-dk       "0 10 * * 3-7"
sched s-odds        ingest-odds     "0 9,15 * * 3-7"
sched s-props       ingest-props    "0 11 * * 4"
sched s-weather     ingest-weather  "0 6,12,18 * * 5,6,0"
sched s-score       score-entries   "0 8 * * 2"
sched s-trends      trends-alerts   "15 8 * * 2"
sched s-freshness   check-freshness "0 8 * * *"
sched s-cfb         ingest-cfb      "0 10,14,18 * * *"
sched s-cfb-sat     ingest-cfb      "0 8-13 * * 6"

echo "Deployed. NOTE: replay-* jobs are A/B harness jobs managed ad hoc, not here."
