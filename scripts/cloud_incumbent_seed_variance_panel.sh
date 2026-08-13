#!/bin/bash
# Launch exactly four frozen nonzero incumbent seed replicas after seed-zero
# exact parity passes.
# Usage: cloud_incumbent_seed_variance_panel.sh <IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260813-incumbent-seed-variance-v1
OUT="$ROOT/reports/incumbent-seed-variance-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-13-incumbent-seed-variance-protocol.md"
PARITY="$ROOT/reports/panel-runs/20260813-incumbent-seed-zero-parity-v1/exact_rebuild_comparison.json"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
[ -s "$PROTOCOL" ] || { echo "ABORT: frozen seed protocol missing"; exit 2; }
[ -s "$PARITY" ] && grep -Eq '"passes"[[:space:]]*:[[:space:]]*true' "$PARITY" || {
  echo "ABORT: exact explicit-seed-zero parity has not passed"; exit 2; }
[ ! -e "$OUT/manifest.txt" ] || {
  echo "ABORT: immutable seed panel already launched"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "parity_sha256=$(sha256sum "$PARITY" | awk '{print $1}')" \
  'reference=R0:20260812-pitclean-e80-selected-tabpfn-active-v2:0:7331' \
  'replicate=R1:20260813-incumbent-mcseed-r1-v1:1137260708:2690847602' \
  'replicate=R2:20260813-incumbent-mcseed-r2-v1:2875959182:1630284992' \
  'replicate=R3:20260813-incumbent-mcseed-r3-v1:253722715:3374646876' \
  'replicate=R4:20260813-incumbent-mcseed-r4-v1:1643280042:3977633467' \
  'seasons=2023 2024 2025' 'n_entries=80' 'n_sims=10000' \
  'tail_line=194' 'allocation=dirichlet' \
  'dirichlet_k=28.154043586960896' 'n_ce=0' 'n_epistemic=12' \
  'n_gumbel=0' 'n_boom=40' > "$OUT/manifest.txt"

ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
COMMON="MODEL_ENSEMBLE=1|TABPFN_MARGINALS=1|TABPFN_MARGINAL_TABLE=tabpfn_active_label_treatment_v2|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES|REPLACEMENT_SLOTS=12|GAME_SIM_USAGE=dirichlet|DIRICHLET_K=28.154043586960896"

launch_replicate() {
  local LABEL=$1 FAMILY=$2 PANEL=$3 BASE_SEED=$4 ROLE_SEED=$5
  local LIST="$OUT/${LABEL}_executions.txt" EXISTING SEASON SPEC JOB LINEUPS ENVS EXEC GOT
  [ ! -e "$LIST" ] || { echo "ABORT: $LIST already exists"; exit 2; }
  EXISTING=$(bq query --project_id="$PROJECT" --use_legacy_sql=false \
    --format=csv \
    "SELECT COUNT(*) AS n FROM \`$PROJECT.nfl_predictions.replay_candidates_staging\` WHERE panel_run_id='$PANEL'" \
    | tail -1 | tr -d '[:space:]')
  [ "${EXISTING:-0}" = 0 ] || {
    echo "ABORT: $PANEL already has $EXISTING staging rows"; exit 2; }
  : > "$LIST"
  for SEASON in 2023 2024 2025; do
    case "$SEASON" in
      2023) SPEC="QB:0.965,RB:0.99,TE:0.945,WR:1.03" ;;
      2024) SPEC="QB:0.905,RB:0.97,TE:0.95,WR:1.06" ;;
      2025) SPEC="QB:0.925,RB:0.96,TE:0.94,WR:1.04" ;;
    esac
    JOB="replay-${FAMILY}-${SEASON}"
    LINEUPS="$PROJECT.nfl_features.replay_lineups_${FAMILY}_${SEASON}"
    ENVS="GCP_PROJECT=$PROJECT|GAME_SIM_MODE=possession|N_CE=0|N_EPISTEMIC=12|N_GUMBEL=0|N_BOOM=40"
    ENVS="$ENVS|PANEL_RUN_ID=$PANEL|CODE_SHA=$CODE_SHA"
    ENVS="$ENVS|CAND_LOG_TABLE=$PROJECT.nfl_predictions.replay_candidates_staging"
    ENVS="$ENVS|CAND_FEATURE_TABLE=$PROJECT.nfl_predictions.slate_player_features"
    ENVS="$ENVS|CAND_ARTIFACT_BUCKET=${PROJECT}-raw|REPLAY_LINEUPS_TABLE=$LINEUPS"
    ENVS="$ENVS|$COMMON|REPLAY_PROJECTION_SEED=$BASE_SEED|ROLE_BELIEF_SEED=$ROLE_SEED"
    ENVS="$ENVS|SERVED_POSITION_SCALES=$SPEC"
    gcloud run jobs deploy "$JOB" --project "$PROJECT" --region us-central1 \
      --image "$IMG" --command nfl-dfs \
      --args "replay,--season,$SEASON,--contest,gpp,--entries,80" \
      --set-env-vars "^|^$ENVS" --memory 16Gi --cpu 4 --max-retries 0 \
      --task-timeout 14400 >/dev/null
    EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
      --region us-central1 --async --format='value(metadata.name)')
    [ -n "$EXEC" ] || { echo "ABORT: no execution for $JOB"; exit 1; }
    GOT=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
      --region us-central1 \
      --format='value(spec.template.spec.containers[0].image)')
    [ "$GOT" = "$IMG" ] || {
      echo "ABORT: $EXEC runs $GOT, expected $IMG"; exit 1; }
    printf '%s %s %s\n' "$SEASON" "$JOB" "$EXEC" | tee -a "$LIST"
  done
}

launch_replicate r1 mcseedr1 20260813-incumbent-mcseed-r1-v1 1137260708 2690847602
launch_replicate r2 mcseedr2 20260813-incumbent-mcseed-r2-v1 2875959182 1630284992
launch_replicate r3 mcseedr3 20260813-incumbent-mcseed-r3-v1 253722715 3374646876
launch_replicate r4 mcseedr4 20260813-incumbent-mcseed-r4-v1 1643280042 3977633467
echo "INCUMBENT_SEED_VARIANCE_PANEL_LAUNCHED $RUN_ID"
