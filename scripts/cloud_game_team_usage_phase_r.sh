#!/bin/bash
# Launch the frozen five-seed repaired multinomial/finite-K Phase R panel.
# Usage: cloud_game_team_usage_phase_r.sh <IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260813-game-team-usage-phase-r-v1
OUT="$ROOT/reports/game-team-usage-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-13-game-team-usage-repair-and-sis-asoe-exact80-protocol.md"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
[ -s "$PROTOCOL" ] || { echo "ABORT: frozen protocol missing"; exit 2; }
[ ! -e "$OUT/manifest.txt" ] || {
  echo "ABORT: immutable Phase R panel already launched"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  'arms=multinomial finite-k' 'replicates=R0 R1 R2 R3 R4' \
  'seasons=2023 2024 2025' 'n_entries=80' 'n_sims=10000' \
  'tail_line=194' 'dirichlet_k=28.154043586960896' \
  'r0=0:7331' 'r1=1137260708:2690847602' \
  'r2=2875959182:1630284992' 'r3=253722715:3374646876' \
  'r4=1643280042:3977633467' > "$OUT/manifest.txt"
: > "$OUT/executions.txt"
: > "$OUT/preflight.txt"

ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump

seed_pair() {
  case "$1" in
    0) printf '%s %s' 0 7331 ;;
    1) printf '%s %s' 1137260708 2690847602 ;;
    2) printf '%s %s' 2875959182 1630284992 ;;
    3) printf '%s %s' 253722715 3374646876 ;;
    4) printf '%s %s' 1643280042 3977633467 ;;
    *) return 2 ;;
  esac
}

position_spec() {
  case "$1" in
    2023) printf '%s' 'QB:0.965,RB:0.99,TE:0.945,WR:1.03' ;;
    2024) printf '%s' 'QB:0.905,RB:0.97,TE:0.95,WR:1.06' ;;
    2025) printf '%s' 'QB:0.925,RB:0.96,TE:0.94,WR:1.04' ;;
    *) return 2 ;;
  esac
}

# One outcome-blind corrected finite-K week must finish before the 30 full
# season jobs are allowed to spend. It persists no candidate panel.
SMOKE_JOB=replay-gtrphase-r-smoke
SMOKE_ENVS="GCP_PROJECT=$PROJECT|GAME_SIM_MODE=possession|MODEL_ENSEMBLE=1"
SMOKE_ENVS="$SMOKE_ENVS|TABPFN_MARGINALS=1|TABPFN_MARGINAL_TABLE=tabpfn_active_label_treatment_v2"
SMOKE_ENVS="$SMOKE_ENVS|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES"
SMOKE_ENVS="$SMOKE_ENVS|ROLE_BELIEF_SEED=7331|REPLAY_PROJECTION_SEED=0|REPLACEMENT_SLOTS=12"
SMOKE_ENVS="$SMOKE_ENVS|N_CE=0|N_EPISTEMIC=12|N_GUMBEL=0|N_BOOM=40"
SMOKE_ENVS="$SMOKE_ENVS|SERVED_POSITION_SCALES=$(position_spec 2024)"
SMOKE_ENVS="$SMOKE_ENVS|GAME_SIM_USAGE=dirichlet|DIRICHLET_K=28.154043586960896"
SMOKE_ENVS="$SMOKE_ENVS|CODE_SHA=$CODE_SHA|REPLAY_LINEUPS_TABLE=$PROJECT.nfl_features.replay_lineups_gtrphase_r_smoke"
gcloud run jobs deploy "$SMOKE_JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "replay,--season,2024,--contest,gpp,--entries,80,--field-size,500,--max-weeks,1" \
  --set-env-vars "^|^$SMOKE_ENVS" --memory 16Gi --cpu 4 --max-retries 0 \
  --task-timeout 14400 >/dev/null
SMOKE_EXEC=$(gcloud run jobs execute "$SMOKE_JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$SMOKE_EXEC" ] || { echo "ABORT: no smoke execution"; exit 1; }
printf '%s %s\n' "$SMOKE_JOB" "$SMOKE_EXEC" > "$OUT/preflight.txt"
while true; do
  SMOKE_STATE=$(gcloud run jobs executions describe "$SMOKE_EXEC" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.conditions[0].status)')
  [ "$SMOKE_STATE" = True ] && break
  [ "$SMOKE_STATE" != False ] || {
    echo "ABORT: Phase R smoke failed: $SMOKE_EXEC"; exit 1; }
  sleep 30
done
echo "Phase R smoke passed: $SMOKE_EXEC"

for ARM in mult k; do
  for REP in 0 1 2 3 4; do
    read -r BASE_SEED ROLE_SEED <<< "$(seed_pair "$REP")"
    PANEL="20260813-game-team-${ARM}-r${REP}-v1"
    EXISTING=$(bq query --project_id="$PROJECT" --use_legacy_sql=false \
      --format=csv \
      "SELECT COUNT(*) AS n FROM \`$PROJECT.nfl_predictions.replay_candidates_staging\` WHERE panel_run_id='$PANEL'" \
      | tail -1 | tr -d '[:space:]')
    [ "${EXISTING:-0}" = 0 ] || {
      echo "ABORT: $PANEL already has $EXISTING staging rows"; exit 2; }
    for SEASON in 2023 2024 2025; do
      SPEC=$(position_spec "$SEASON")
      FAMILY="gtr${ARM}${REP}"
      JOB="replay-${FAMILY}-${SEASON}"
      LINEUPS="$PROJECT.nfl_features.replay_lineups_${FAMILY}_${SEASON}"
      ENVS="GCP_PROJECT=$PROJECT|GAME_SIM_MODE=possession|MODEL_ENSEMBLE=1"
      ENVS="$ENVS|TABPFN_MARGINALS=1|TABPFN_MARGINAL_TABLE=tabpfn_active_label_treatment_v2"
      ENVS="$ENVS|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES"
      ENVS="$ENVS|ROLE_BELIEF_SEED=$ROLE_SEED|REPLAY_PROJECTION_SEED=$BASE_SEED|REPLACEMENT_SLOTS=12"
      ENVS="$ENVS|N_CE=0|N_EPISTEMIC=12|N_GUMBEL=0|N_BOOM=40"
      ENVS="$ENVS|SERVED_POSITION_SCALES=$SPEC|PANEL_RUN_ID=$PANEL|CODE_SHA=$CODE_SHA"
      ENVS="$ENVS|CAND_LOG_TABLE=$PROJECT.nfl_predictions.replay_candidates_staging"
      ENVS="$ENVS|CAND_FEATURE_TABLE=$PROJECT.nfl_predictions.slate_player_features"
      ENVS="$ENVS|CAND_ARTIFACT_BUCKET=${PROJECT}-raw|REPLAY_LINEUPS_TABLE=$LINEUPS"
      if [ "$ARM" = k ]; then
        ENVS="$ENVS|GAME_SIM_USAGE=dirichlet|DIRICHLET_K=28.154043586960896"
      fi
      gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
        --image "$IMG" --command nfl-dfs \
        --args "replay,--season,$SEASON,--contest,gpp,--entries,80" \
        --set-env-vars "^|^$ENVS" --memory 16Gi --cpu 4 --max-retries 0 \
        --task-timeout 14400 >/dev/null
      EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
        --region "$REGION" --async --format='value(metadata.name)')
      [ -n "$EXEC" ] || { echo "ABORT: no execution for $JOB"; exit 1; }
      GOT=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
        --region "$REGION" --format='value(spec.template.spec.containers[0].image)')
      [ "$GOT" = "$IMG" ] || {
        echo "ABORT: $EXEC runs $GOT, expected $IMG"; exit 1; }
      printf '%s %s %s %s %s %s\n' \
        "$ARM" "$REP" "$SEASON" "$PANEL" "$JOB" "$EXEC" \
        | tee -a "$OUT/executions.txt"
    done
  done
done
echo "GAME_TEAM_USAGE_PHASE_R_LAUNCHED $RUN_ID"
