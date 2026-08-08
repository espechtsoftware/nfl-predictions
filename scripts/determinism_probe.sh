#!/bin/bash
# Persist one replay slate for a cheap staging-to-staging exact-world proof.
#
# Usage:
#   bash scripts/determinism_probe.sh \
#     <IMAGE@sha256:...> <CODE_SHA> <FAMILY> <PANEL_RUN_ID> <SEASON>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
FAMILY=${3:-}
PANEL_RUN_ID=${4:-}
SEASON=${5:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/panel-runs/$PANEL_RUN_ID"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$CODE_SHA" in ""|*[!A-Fa-f0-9]*) echo "ABORT: CODE_SHA must be hexadecimal"; exit 2;; esac
case "$FAMILY" in ""|*[!a-z0-9]*) echo "ABORT: FAMILY must be lower-case alphanumeric"; exit 2;; esac
case "$PANEL_RUN_ID" in ""|*[!A-Za-z0-9_-]*) echo "ABORT: invalid panel id"; exit 2;; esac
case "$SEASON" in 20[0-9][0-9]) ;; *) echo "ABORT: invalid season"; exit 2;; esac

mkdir -p "$OUT"
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable probe already has an execution"; exit 2; }

EXISTING=$(bq query --project_id="$PROJECT" --use_legacy_sql=false \
  --format=csv \
  "SELECT COUNT(*) AS n FROM \`$PROJECT.nfl_predictions.replay_candidates_staging\` WHERE panel_run_id='$PANEL_RUN_ID'" \
  | tail -1 | tr -d '[:space:]')
[ "${EXISTING:-0}" = "0" ] || {
  echo "ABORT: panel id already has $EXISTING staging rows"; exit 2; }

JOB="replay-$FAMILY-$SEASON"
LINEUPS="$PROJECT.nfl_features.replay_lineups_${FAMILY}_${SEASON}"
ENVS="GCP_PROJECT=$PROJECT|GAME_SIM_MODE=possession|MODEL_ENSEMBLE=3|N_CE=0|N_EPISTEMIC=0|N_GUMBEL=0|N_BOOM=40|PANEL_RUN_ID=$PANEL_RUN_ID|CODE_SHA=$CODE_SHA|CAND_LOG_TABLE=$PROJECT.nfl_predictions.replay_candidates_staging|CAND_FEATURE_TABLE=$PROJECT.nfl_predictions.slate_player_features|CAND_ARTIFACT_BUCKET=${PROJECT}-raw|REPLAY_LINEUPS_TABLE=$LINEUPS"
ARGS="replay,--season,$SEASON,--contest,gpp,--entries,40,--field-size,500,--max-weeks,1"

printf 'image=%s\ncode_sha=%s\nfamily=%s\npanel_run_id=%s\nseason=%s\n' \
  "$IMG" "$CODE_SHA" "$FAMILY" "$PANEL_RUN_ID" "$SEASON" \
  > "$OUT/manifest.txt"

gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs --args "$ARGS" \
  --set-env-vars "^|^$ENVS" --memory 16Gi --cpu 4 --max-retries 0 \
  --task-timeout 10800 --quiet >/dev/null
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"

GOT=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(spec.template.spec.containers[0].image)')
[ "$GOT" = "$IMG" ] || {
  echo "ABORT: $EXEC runs $GOT, expected $IMG"; exit 1; }

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = "True" ] && break
  [ "$STATE" != "False" ] || {
    echo "ABORT: probe execution failed: $EXEC"; exit 1; }
  sleep 30
done

COUNTS=$(bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
  "SELECT COUNT(*) AS candidates, COUNT(DISTINCT CONCAT(CAST(season AS STRING),'-',CAST(week AS STRING))) AS slates, COUNTIF(selected) AS selected FROM \`$PROJECT.nfl_predictions.replay_candidates_staging\` WHERE panel_run_id='$PANEL_RUN_ID'" \
  | tail -1 | tr -d '[:space:]')
IFS=, read -r CANDIDATES SLATES SELECTED <<< "$COUNTS"
[ "${CANDIDATES:-0}" -gt 0 ] && [ "$SLATES" = "1" ] && [ "$SELECTED" = "40" ] || {
  echo "ABORT: incomplete probe candidates=$CANDIDATES slates=$SLATES selected=$SELECTED"; exit 1; }
printf 'candidates=%s\nslates=%s\nselected=%s\n' \
  "$CANDIDATES" "$SLATES" "$SELECTED" > "$OUT/counts.txt"
echo "Determinism probe passed: $PANEL_RUN_ID ($EXEC)"
