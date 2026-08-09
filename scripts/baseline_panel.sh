#!/bin/bash
# Audited corrected-universe baseline panel.
#
# Usage:
#   bash scripts/baseline_panel.sh <IMAGE@sha256:...> <FAMILY> <PANEL_RUN_ID>
#
# This is deliberately baseline-only.  It establishes the shipping score
# after a data-universe repair without mixing in a feature or generator arm.
# Results and immutable execution IDs stay under reports/panel-runs/ in this
# repository; no state is inferred from "latest execution".
set -euo pipefail

IMG=${1:-}
FAM=${2:-}
PANEL_RUN_ID=${3:-}
REGION=us-central1
PROJECT=nfl-predictions-503414
SEASONS=${PANEL_SEASONS:-"2019 2021 2022 2023 2024 2025"}
CODE_SHA=${PANEL_CODE_SHA:-}
ARM_LABEL=${PANEL_ARM_LABEL:-baseline}
ARM_ENV=${PANEL_ARM_ENV:-}
PANEL_MEMORY=${PANEL_MEMORY:-16Gi}
PANEL_SMOKE_SEASON=${PANEL_SMOKE_SEASON:-2022}
PANEL_N_CE=${PANEL_N_CE:-0}
PANEL_N_EPISTEMIC=${PANEL_N_EPISTEMIC:-0}
PANEL_N_GUMBEL=${PANEL_N_GUMBEL:-0}
PANEL_N_BOOM=${PANEL_N_BOOM:-40}
PANEL_N_ENTRIES=${PANEL_N_ENTRIES:-40}

case "$IMG" in
  *@sha256:*) ;;
  *) echo "ABORT: immutable @sha256 image required, got '$IMG'"; exit 2 ;;
esac
case "$FAM" in
  ""|*[!a-z0-9]*)
    echo "ABORT: FAMILY must contain only lower-case letters and digits"; exit 2 ;;
  rev|g2|panel|ceconf1)
    echo "ABORT: dedicated FAMILY required, not '$FAM'"; exit 2 ;;
esac
case "$PANEL_RUN_ID" in
  ""|*[!A-Za-z0-9_-]*)
    echo "ABORT: PANEL_RUN_ID must use letters, digits, '_' or '-'"; exit 2 ;;
esac
[ -n "$CODE_SHA" ] || {
  echo "ABORT: PANEL_CODE_SHA must be the commit embedded in the image"; exit 2; }
case "$PANEL_N_ENTRIES" in
  ""|*[!0-9]*)
    echo "ABORT: PANEL_N_ENTRIES must be an integer from 1 through 150"; exit 2 ;;
esac
[ "$PANEL_N_ENTRIES" -ge 1 ] && [ "$PANEL_N_ENTRIES" -le 150 ] || {
  echo "ABORT: PANEL_N_ENTRIES must be an integer from 1 through 150"; exit 2; }
[ -z "$ARM_ENV" ] || [ "${PANEL_ALLOW_TREATMENT:-0}" = "1" ] || {
  echo "ABORT: baseline runner refuses treatment env without reviewed wrapper"; exit 2; }
if [ "$PANEL_N_CE" != 0 ] || [ "$PANEL_N_EPISTEMIC" != 0 ] \
   || [ "$PANEL_N_GUMBEL" != 0 ] || [ "$PANEL_N_BOOM" != 40 ]; then
  [ "${PANEL_ALLOW_TREATMENT:-0}" = "1" ] || {
    echo "ABORT: nonbaseline generation budget requires reviewed wrapper"; exit 2; }
fi

ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/panel-runs/$PANEL_RUN_ID"
mkdir -p "$OUT"
EXECS="$OUT/executions.txt"
PREFLIGHT="$OUT/preflight.txt"
[ ! -s "$EXECS" ] || {
  echo "ABORT: $EXECS already exists; PANEL_RUN_ID must be immutable"; exit 2; }

# A panel id is globally unique, not merely unique in this checkout.  Reusing
# one would make the warehouse look like a duplicate/mixed-config panel.
EXISTING=$(bq query --project_id="$PROJECT" --use_legacy_sql=false \
  --format=csv \
  "SELECT COUNT(*) AS n FROM \`$PROJECT.nfl_predictions.replay_candidates_staging\` WHERE panel_run_id='$PANEL_RUN_ID'" \
  | tail -1 | tr -d '[:space:]')
[ "${EXISTING:-0}" = "0" ] || {
  echo "ABORT: panel id already has $EXISTING staging rows"; exit 2; }

printf 'image=%s\nfamily=%s\npanel_run_id=%s\ncode_sha=%s\nseasons=%s\narm_label=%s\narm_env=%s\nmemory=%s\nsmoke_season=%s\nn_entries=%s\nn_ce=%s\nn_epistemic=%s\nn_gumbel=%s\nn_boom=%s\n' \
  "$IMG" "$FAM" "$PANEL_RUN_ID" "$CODE_SHA" "$SEASONS" \
  "$ARM_LABEL" "$ARM_ENV" "$PANEL_MEMORY" "$PANEL_SMOKE_SEASON" \
  "$PANEL_N_ENTRIES" "$PANEL_N_CE" "$PANEL_N_EPISTEMIC" \
  "$PANEL_N_GUMBEL" "$PANEL_N_BOOM" \
  > "$OUT/manifest.txt"
: > "$EXECS"
: > "$PREFLIGHT"

launch_one() {
  local S=$1 MODE=${2:-panel} JOB LINEUPS ENVS ARGS RECORD EXEC GOT
  if [ "$MODE" = "smoke" ]; then
    JOB="replay-$FAM-smoke"
    LINEUPS="$PROJECT.nfl_features.replay_lineups_${FAM}_smoke"
    # Exercise model fitting, nullable/cold-start handling, simulation,
    # generation, and selection without polluting the canonical panel tables.
    ENVS="GCP_PROJECT=$PROJECT|GAME_SIM_MODE=possession|N_CE=$PANEL_N_CE|N_EPISTEMIC=$PANEL_N_EPISTEMIC|N_GUMBEL=$PANEL_N_GUMBEL|N_BOOM=$PANEL_N_BOOM|CODE_SHA=$CODE_SHA|REPLAY_LINEUPS_TABLE=$LINEUPS"
    ARGS="replay,--season,$S,--contest,gpp,--entries,$PANEL_N_ENTRIES,--field-size,500,--max-weeks,1"
    RECORD="$PREFLIGHT"
  else
    JOB="replay-$FAM-$S"
    LINEUPS="$PROJECT.nfl_features.replay_lineups_${FAM}_${S}"
    ENVS="GCP_PROJECT=$PROJECT|GAME_SIM_MODE=possession|N_CE=$PANEL_N_CE|N_EPISTEMIC=$PANEL_N_EPISTEMIC|N_GUMBEL=$PANEL_N_GUMBEL|N_BOOM=$PANEL_N_BOOM|PANEL_RUN_ID=$PANEL_RUN_ID|CODE_SHA=$CODE_SHA|CAND_LOG_TABLE=$PROJECT.nfl_predictions.replay_candidates_staging|CAND_FEATURE_TABLE=$PROJECT.nfl_predictions.slate_player_features|CAND_ARTIFACT_BUCKET=${PROJECT}-raw|REPLAY_LINEUPS_TABLE=$LINEUPS"
    ARGS="replay,--season,$S,--contest,gpp,--entries,$PANEL_N_ENTRIES"
    RECORD="$EXECS"
  fi
  [ -z "$ARM_ENV" ] || ENVS="$ENVS|$ARM_ENV"
  gcloud run jobs deploy "$JOB" --image "$IMG" --region "$REGION" \
    --command nfl-dfs --args "$ARGS" \
    --set-env-vars "^|^$ENVS" --memory "$PANEL_MEMORY" --cpu 4 --max-retries 0 \
    --task-timeout 10800 >/dev/null
  EXEC=$(gcloud run jobs execute "$JOB" --region "$REGION" --async \
    --format='value(metadata.name)')
  [ -n "$EXEC" ] || { echo "ABORT: no execution id for $JOB"; exit 1; }
  GOT=$(gcloud run jobs executions describe "$EXEC" --region "$REGION" \
    --format='value(spec.template.spec.containers[0].image)')
  [ "$GOT" = "$IMG" ] || {
    echo "ABORT: $EXEC runs $GOT, expected $IMG"; exit 1; }
  printf '%s %s %s\n' "$S" "$JOB" "$EXEC" | tee -a "$RECORD"
}

wait_success() {
  local EXEC=$1 STATE SUCC FAIL
  while true; do
    STATE=$(gcloud run jobs executions describe "$EXEC" --region "$REGION" \
      --format='value(status.conditions[0].status)')
    [ "$STATE" = "True" ] && break
    # completionTime can be visible before Completed changes from Unknown to
    # True, so it is not itself a failure signal.
    if [ "$STATE" = "False" ]; then
      echo "ABORT: cloud preflight $EXEC did not succeed (state=$STATE)"
      exit 1
    fi
    sleep 30
  done
  SUCC=$(gcloud run jobs executions describe "$EXEC" --region "$REGION" \
    --format='value(status.succeededCount)')
  FAIL=$(gcloud run jobs executions describe "$EXEC" --region "$REGION" \
    --format='value(status.failedCount)')
  [ "${SUCC:-0}" = "1" ] && [ "${FAIL:-0}" = "0" ] || {
    echo "ABORT: cloud preflight $EXEC succeeded=$SUCC failed=$FAIL"; exit 1; }
}

# Run one cloud week to completion before spending six full executions. This
# catches data-shape and mechanism failures without turning the preflight into
# a duplicate hour-long season replay.
read -r -a SEASON_LIST <<< "$SEASONS"
[ "${#SEASON_LIST[@]}" -gt 0 ] || { echo "ABORT: no seasons"; exit 2; }
case " $SEASONS " in
  *" $PANEL_SMOKE_SEASON "*) ;;
  *) PANEL_SMOKE_SEASON=${SEASON_LIST[0]} ;;
esac
launch_one "$PANEL_SMOKE_SEASON" smoke
PREFLIGHT_EXEC=$(awk 'NR==1 {print $3}' "$PREFLIGHT")
echo "Waiting for cloud preflight $PREFLIGHT_EXEC ..."
wait_success "$PREFLIGHT_EXEC"
echo "Cloud preflight passed; launching all panel seasons."
for S in "${SEASON_LIST[@]}"; do
  launch_one "$S"
done

echo "Launched $(wc -l < "$EXECS") immutable baseline executions."
echo "Execution manifest: $EXECS"
