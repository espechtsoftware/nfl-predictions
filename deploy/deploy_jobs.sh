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
# API credentials come from Secret Manager. Never replace a deployed secret
# reference with an empty or workstation-local value during a machine move.
# Idempotent: `gcloud run jobs deploy` upserts; scheduler create || update.
set -euo pipefail

PROJECT="${GCP_PROJECT:?set GCP_PROJECT}"
REGION="${REGION:-us-central1}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/nfl-dfs/nfl-dfs:latest"
CODE_SHA="${CODE_SHA:-$(git rev-parse --short=12 HEAD 2>/dev/null || true)}"
SA="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"

build() { gcloud builds submit --tag "$IMAGE" .; }

job() {  # name, cli-args, memory, cpu, extra-env (|), secrets, timeout
  local name=$1 args=$2 mem=${3:-2Gi} cpu=${4:-1} extra=${5:-} secrets=${6:-}
  local timeout=${7:-3600}
  local secret_args=()
  if [[ -n "$secrets" ]]; then
    secret_args=(--set-secrets "$secrets")
  fi
  gcloud run jobs deploy "$name" --image "$IMAGE" --region "$REGION" \
    --command nfl-dfs --args "$args" \
    --set-env-vars "^|^GCP_PROJECT=${PROJECT}${extra:+|$extra}" \
    "${secret_args[@]}" \
    --memory "$mem" --cpu "$cpu" --max-retries 1 --task-timeout "$timeout"
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
job ingest-nflverse  ingest-nflverse 4Gi 1
job ingest-dk        ingest-dk       2Gi 1
job ingest-odds      ingest-odds     2Gi 1 "" "ODDS_API_KEY=odds-api-key:latest"
# Live-only collection shadow. It writes a dedicated non-production table
# and stops before each paid request unless the provider-reported remaining
# balance will preserve the 5,000-credit reserve.
job ingest-props     ingest-props    2Gi 1 "ODDS_SHADOW_MARKETS_ENABLED=1|ODDS_SHADOW_MIN_REMAINING=5000" "ODDS_API_KEY=odds-api-key:latest"
job ingest-weather   ingest-weather
job ingest-cfb       ingest-cfb      2Gi 1 "INGEST_CFB_ENABLED=1"
# --- Pipeline ----------------------------------------------------------------
job build-features   build-features
job train-weekly     train           8Gi 4
# Tail-first research baseline: isolated registry labels mean this K=1
# retrain cannot overwrite the canonical K=3 models loaded by the app.
job train-weekly-k1  train           8Gi 4 "MODEL_ENSEMBLE=1|MODEL_REGISTRY_VARIANT=tail_k1"
# Alternate K=1 role registry used by the promoted expanded candidate union.
job train-weekly-k1-role train        8Gi 4 "MODEL_ENSEMBLE=1|MODEL_REGISTRY_VARIANT=tail_k1_role|EXTRA_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump"
# Paired Route Share treatment registries. These never replace the incumbent
# K=1 registries and fail closed after Week 1 unless the exact W-1 licensed
# export has been imported before this Tuesday chain reaches them.
job train-weekly-k1-route train       8Gi 4 "MODEL_ENSEMBLE=1|MODEL_REGISTRY_VARIANT=tail_k1_route|EXTRA_FEATURES=fp_route_share_last,fp_route_share_l4,fp_route_share_jump,fp_route_cross_season"
job train-weekly-k1-route-role train  8Gi 4 "MODEL_ENSEMBLE=1|MODEL_REGISTRY_VARIANT=tail_k1_route_role|EXTRA_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump,fp_route_share_last,fp_route_share_l4,fp_route_share_jump,fp_route_cross_season"
# The command also pins/verifies these values from production_policy.py;
# keeping them on the job makes the Cloud Run configuration self-describing.
job project-slate    project         4Gi 2 "GAME_SIM_MODE=possession|MODEL_ENSEMBLE=1|MODEL_REGISTRY_VARIANT=tail_k1|BLEND_MODEL_WEIGHT=0.45"
# Prospective evidence only: fixed true-80/194 Sunday-main book, synchronous
# persistence, no user notes, and no projection/live-app mutation.
job shadow-k1        shadow-k1       8Gi 4 "MODEL_ENSEMBLE=1|MODEL_REGISTRY_VARIANT=tail_k1|GAME_SIM_MODE=possession|N_CE=0|N_EPISTEMIC=0|N_GUMBEL=0|N_BOOM=40|MIN_LINEUP_SALARY=49000|BLEND_MODEL_WEIGHT=0.45|LIVE_SIMS=30000|CAND_ARTIFACT_BUCKET=${PROJECT}-raw|CODE_SHA=${CODE_SHA}"
job shadow-k1-nofloor shadow-k1-nofloor 8Gi 4 "MODEL_ENSEMBLE=1|MODEL_REGISTRY_VARIANT=tail_k1|GAME_SIM_MODE=possession|N_CE=0|N_EPISTEMIC=0|N_GUMBEL=0|N_BOOM=40|MIN_LINEUP_SALARY=0|BLEND_MODEL_WEIGHT=0.45|LIVE_SIMS=30000|CAND_ARTIFACT_BUCKET=${PROJECT}-raw|CODE_SHA=${CODE_SHA}"
job shadow-k1-roleunion shadow-k1-roleunion 8Gi 4 "MODEL_ENSEMBLE=1|MODEL_REGISTRY_VARIANT=tail_k1|GAME_SIM_MODE=possession|GEN_TOTAL_BUDGET=52|N_CE=12|CE_SEED=1701|N_EPISTEMIC=12|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump|ROLE_BELIEF_SEED=7331|N_GUMBEL=0|N_BOOM=28|REPLACEMENT_SLOTS=12|MIN_LINEUP_SALARY=49000|BLEND_MODEL_WEIGHT=0.45|LIVE_SIMS=30000|CAND_ARTIFACT_BUCKET=${PROJECT}-raw|CODE_SHA=${CODE_SHA}"
job shadow-k1-route-roleunion shadow-k1-route-roleunion 8Gi 4 "MODEL_ENSEMBLE=1|MODEL_REGISTRY_VARIANT=tail_k1_route|GAME_SIM_MODE=possession|GEN_TOTAL_BUDGET=52|N_CE=12|CE_SEED=1701|N_EPISTEMIC=12|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump|ROLE_BELIEF_SEED=7331|N_GUMBEL=0|N_BOOM=28|REPLACEMENT_SLOTS=12|MIN_LINEUP_SALARY=49000|BLEND_MODEL_WEIGHT=0.45|LIVE_SIMS=30000|CAND_ARTIFACT_BUCKET=${PROJECT}-raw|CODE_SHA=${CODE_SHA}"
job shadow-k3        shadow-k3       8Gi 4 "MODEL_ENSEMBLE=3|MODEL_REGISTRY_VARIANT=canonical|GAME_SIM_MODE=possession|N_CE=0|N_EPISTEMIC=0|N_GUMBEL=0|N_BOOM=40|MIN_LINEUP_SALARY=49000|BLEND_MODEL_WEIGHT=0.45|LIVE_SIMS=30000|CAND_ARTIFACT_BUCKET=${PROJECT}-raw|CODE_SHA=${CODE_SHA}"
# Same-snapshot/same-world paired Program A shadow plus immutable recourse
# worlds. It is deliberately separate from every money-lineup route and gets
# two hours because it builds all five native CBWU books before persisting.
job shadow-archetype-paired shadow-archetype-paired 16Gi 4 "CODE_SHA=${CODE_SHA}" "" 7200
# Paired CBWU-OI union shadow (2026-08-18): control CBWU vs frozen
# order-invariant union on identical worlds; grading bar frozen at
# reports/2026-08-18-cbwu-oi-prospective-shadow-spec.md.
job shadow-cbwu-oi-paired shadow-cbwu-oi-paired 16Gi 4 "CODE_SHA=${CODE_SHA}" "" 7200
# B1 volume shadow: builds TWENTY seed books instead of five, so it gets a
# 4h task timeout and starts earliest of the Sunday shadows.
job shadow-cbwu-volume shadow-cbwu-volume 16Gi 4 "CODE_SHA=${CODE_SHA}" "" 14400
# Independent finite-usage SIS pass-tail evidence. The job is a ten-book
# five-seed pair and deliberately never changes the K=1/CBWU money path.
job shadow-sis-pass-tail-paired shadow-sis-pass-tail-paired 16Gi 4 "CODE_SHA=${CODE_SHA}" "" 14400
# Cheap post-processing only: read the four complete pre-lock pools, freeze
# control/top-p/no-floor/mixed memberships, and never regenerate candidates.
job freeze-tail-early "freeze-tail-portfolios,--slot,early" 1Gi 1
job freeze-tail-late  "freeze-tail-portfolios,--slot,late"  1Gi 1
job score-entries    score-entries
job trends-alerts    trends
job check-freshness  check-freshness 1Gi 1

# --- Schedules (live cadences; seasonal pauses managed by the design guide §11
# runbook: s-nflverse/s-features/s-train*/s-project-*/s-shadow-* and
# s-freeze-tail-* are PAUSED in the
# off-season and resumed ~Aug 24) --------------------------------------------
# nflverse's final injury files may omit source modification timestamps. A
# daily in-season pull gives the append-only injury collector actual pre-lock
# observation times; the scheduler remains paused in the off-season.
sched s-nflverse    ingest-nflverse "0 5 * * *"
sched s-features    build-features  "30 6 * * 2"
sched s-train       train-weekly    "30 7 * * 2"
sched s-train-k1    train-weekly-k1 "30 8 * * 2"
sched s-train-k1-role train-weekly-k1-role "45 8 * * 2"
# Licensed Route Share is posted after the completed week. Give the operator
# Tuesday/Wednesday to collect+import it, then rebuild the feature tables and
# train only the isolated treatment registries on Thursday.
sched s-features-route build-features "30 6 * * 4"
sched s-train-k1-route train-weekly-k1-route "30 7 * * 4"
sched s-train-k1-route-role train-weekly-k1-route-role "0 8 * * 4"
sched s-project-tu  project-slate   "30 9 * * 2"
sched s-project-su  project-slate   "0 6-11 * * 7"
# Two pre-lock snapshots: the early run is resilient to a late-run failure;
# the later one incorporates most Sunday inactive/market information.
sched s-shadow-k1-early shadow-k1   "30 10 * * 7"
sched s-shadow-k1-late  shadow-k1   "20 11 * * 7"
sched s-shadow-k1-nofloor-early shadow-k1-nofloor "30 10 * * 7"
sched s-shadow-k1-nofloor-late  shadow-k1-nofloor "20 11 * * 7"
sched s-shadow-k1-roleunion-early shadow-k1-roleunion "20 10 * * 7"
sched s-shadow-k1-roleunion-late  shadow-k1-roleunion "10 11 * * 7"
sched s-shadow-k1-route-roleunion-early shadow-k1-route-roleunion "20 10 * * 7"
sched s-shadow-k1-route-roleunion-late  shadow-k1-route-roleunion "10 11 * * 7"
sched s-shadow-k3-early shadow-k3   "30 10 * * 7"
sched s-shadow-k3-late  shadow-k3   "20 11 * * 7"
# Paired snapshots begin earlier than the one-seed shadows so their five-book
# build and create-only manifest can finish before the next decision boundary.
sched s-shadow-archetype-paired-early shadow-archetype-paired "15 9 * * 7"
sched s-shadow-cbwu-volume shadow-cbwu-volume "30 8 * * 7"
sched s-shadow-cbwu-oi-paired-early shadow-cbwu-oi-paired "45 9 * * 7"
sched s-shadow-cbwu-oi-paired-late  shadow-cbwu-oi-paired "45 10 * * 7"
sched s-shadow-archetype-paired-late  shadow-archetype-paired "30 10 * * 7"
# Start early enough for the ten isolated books to finish before main lock.
sched s-shadow-sis-pass-tail-paired shadow-sis-pass-tail-paired "0 6 * * 7"
# Both source jobs start together. These delayed jobs fail closed unless the
# corresponding complete K=1 and K=3 hour-slot panels are present.
sched s-freeze-tail-early freeze-tail-early "5 11 * * 7"
sched s-freeze-tail-late  freeze-tail-late  "50 11 * * 7"
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
