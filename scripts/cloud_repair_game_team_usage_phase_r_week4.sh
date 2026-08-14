#!/bin/bash
# Reproduce the one Phase R slice whose first candidate-table append hit a
# BigQuery table-update quota.  The repair uses the original immutable image,
# model inputs, seeds and levers and writes to a provenance-only panel first.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/game-team-usage-runs/20260813-game-team-usage-phase-r-v1"
ORIGINAL=20260813-game-team-mult-r0-v1
REPAIR=20260813-game-team-mult-r0-2025-w4-repair1
TABLE="$PROJECT.nfl_predictions.replay_candidates_staging"
IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:4c59f038898d7a21aa2d6067c78238b0349f1e3b090999a6e9da8703ea316e43
CODE_SHA=45ece38
EXEC_FILE="$OUT/mult_r0_2025_week4_repair_execution.txt"

[ ! -e "$EXEC_FILE" ] || { echo "ABORT: repair already launched"; exit 2; }
original_rows=$(bq query --project_id="$PROJECT" --use_legacy_sql=false \
  --format=csv "SELECT COUNT(*) AS n FROM \`$TABLE\` WHERE panel_run_id='$ORIGINAL' AND season=2025 AND week=4" \
  | tail -1 | tr -d '[:space:]')
repair_rows=$(bq query --project_id="$PROJECT" --use_legacy_sql=false \
  --format=csv "SELECT COUNT(*) AS n FROM \`$TABLE\` WHERE panel_run_id='$REPAIR'" \
  | tail -1 | tr -d '[:space:]')
[ "${original_rows:-0}" = 0 ] || { echo "ABORT: original Week 4 is not empty"; exit 2; }
[ "${repair_rows:-0}" = 0 ] || { echo "ABORT: repair panel is not empty"; exit 2; }

ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
ENVS="GCP_PROJECT=$PROJECT|GAME_SIM_MODE=possession|MODEL_ENSEMBLE=1"
ENVS="$ENVS|TABPFN_MARGINALS=1|TABPFN_MARGINAL_TABLE=tabpfn_active_label_treatment_v2"
ENVS="$ENVS|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES"
ENVS="$ENVS|ROLE_BELIEF_SEED=7331|REPLAY_PROJECTION_SEED=0|REPLACEMENT_SLOTS=12"
ENVS="$ENVS|N_CE=0|N_EPISTEMIC=12|N_GUMBEL=0|N_BOOM=40"
ENVS="$ENVS|SERVED_POSITION_SCALES=QB:0.925,RB:0.96,TE:0.94,WR:1.04"
ENVS="$ENVS|PANEL_RUN_ID=$REPAIR|CODE_SHA=$CODE_SHA"
ENVS="$ENVS|CAND_LOG_TABLE=$TABLE"
ENVS="$ENVS|CAND_FEATURE_TABLE=$PROJECT.nfl_predictions.slate_player_features"
ENVS="$ENVS|CAND_ARTIFACT_BUCKET=${PROJECT}-raw"
ENVS="$ENVS|REPLAY_LINEUPS_TABLE=$PROJECT.nfl_features.replay_lineups_gtrmult0_2025"

JOB=replay-gtrmult0-2025-w4-repair1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --command nfl-dfs \
  --args "replay,--season,2025,--contest,gpp,--entries,80,--max-weeks,4" \
  --set-env-vars "^|^$ENVS" --memory 16Gi --cpu 4 --max-retries 0 \
  --task-timeout 14400 >/dev/null
deployed=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$deployed" = "$IMAGE" ] || { echo "ABORT: repair image differs"; exit 1; }
execution=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$execution" ] || { echo "ABORT: repair execution missing"; exit 1; }
printf '%s\n' "$execution" > "$EXEC_FILE"
echo "GAME_TEAM_USAGE_PHASE_R_WEEK4_REPAIR_LAUNCHED $execution"
