#!/bin/bash
# Persist one 2024 incumbent slate with explicit baseline seed zero. The exact
# rebuild comparator must reproduce the accepted incumbent before nonzero seed
# replicas are licensed.
# Usage: cloud_incumbent_seed_zero_parity.sh <IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
PANEL=20260813-incumbent-seed-zero-parity-v1
REFERENCE=20260812-pitclean-e80-selected-tabpfn-active-v2
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/panel-runs/$PANEL"
PROTOCOL="$ROOT/reports/2026-08-13-incumbent-seed-variance-protocol.md"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
[ -s "$PROTOCOL" ] || { echo "ABORT: seed protocol missing"; exit 2; }
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable seed-zero smoke already recorded"; exit 2; }
EXISTING=$(bq query --project_id="$PROJECT" --use_legacy_sql=false \
  --format=csv \
  "SELECT COUNT(*) AS n FROM \`$PROJECT.nfl_predictions.replay_candidates_staging\` WHERE panel_run_id='$PANEL'" \
  | tail -1 | tr -d '[:space:]')
[ "${EXISTING:-0}" = 0 ] || {
  echo "ABORT: seed-zero smoke already has $EXISTING staging rows"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "panel=$PANEL" "reference=$REFERENCE" "image=$IMG" "code_sha=$CODE_SHA" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  'season=2024' 'slates=first-main-slate-only' 'n_sims=10000' \
  'n_entries=80' 'tail_line=194' 'replay_projection_seed=0' \
  'role_belief_seed=7331' 'allocation=dirichlet' \
  'dirichlet_k=28.154043586960896' 'n_ce=0' 'n_epistemic=12' \
  'n_gumbel=0' 'n_boom=40' 'label_law=active-only' \
  'tabpfn_table=tabpfn_active_label_treatment_v2' \
  'served_position_scales=QB:0.905,RB:0.97,TE:0.95,WR:1.06' \
  > "$OUT/manifest.txt"

ENVS="GCP_PROJECT=$PROJECT|GAME_SIM_MODE=possession|MODEL_ENSEMBLE=1"
ENVS="$ENVS|TABPFN_MARGINALS=1|TABPFN_MARGINAL_TABLE=tabpfn_active_label_treatment_v2"
ENVS="$ENVS|EPISTEMIC_FAMILY=role_draws"
ENVS="$ENVS|ROLE_BELIEF_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump"
ENVS="$ENVS|ROLE_BELIEF_SEED=7331|REPLAY_PROJECTION_SEED=0|REPLACEMENT_SLOTS=12"
ENVS="$ENVS|GAME_SIM_USAGE=dirichlet|DIRICHLET_K=28.154043586960896"
ENVS="$ENVS|SERVED_POSITION_SCALES=QB:0.905,RB:0.97,TE:0.95,WR:1.06"
ENVS="$ENVS|N_CE=0|N_EPISTEMIC=12|N_GUMBEL=0|N_BOOM=40"
ENVS="$ENVS|PANEL_RUN_ID=$PANEL|CODE_SHA=$CODE_SHA"
ENVS="$ENVS|CAND_LOG_TABLE=$PROJECT.nfl_predictions.replay_candidates_staging"
ENVS="$ENVS|CAND_FEATURE_TABLE=$PROJECT.nfl_predictions.slate_player_features"
ENVS="$ENVS|CAND_ARTIFACT_BUCKET=${PROJECT}-raw"
ENVS="$ENVS|REPLAY_LINEUPS_TABLE=$PROJECT.nfl_features.replay_lineups_mcseed0_parity"
JOB=replay-mcseed-zero-parity
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "replay,--season,2024,--contest,gpp,--entries,80,--field-size,5000,--max-weeks,1" \
  --set-env-vars "^|^$ENVS" --memory 16Gi --cpu 4 --max-retries 0 \
  --task-timeout 14400 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: seed-zero smoke deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: seed-zero execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "INCUMBENT_SEED_ZERO_PARITY_LAUNCHED $EXEC"
