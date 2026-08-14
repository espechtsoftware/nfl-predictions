#!/bin/bash
# Release at most one classified zero-output Phase S retry under a hard cap.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/sis-asoe-phase-s-runs/20260813-sis-asoe-phase-s-v1"
LIST="$OUT/executions.txt"
PENDING="$OUT/pending_infrastructure_retries.txt"
MANIFEST="$OUT/manifest.txt"
MAX_IN_FLIGHT=${PHASE_S_MAX_IN_FLIGHT:-10}

[ -s "$LIST" ] && [ -e "$PENDING" ] && [ -s "$MANIFEST" ] || {
  echo "ABORT: Phase S recovery state is incomplete"; exit 2; }
[ "$(wc -l < "$LIST")" = 30 ] || {
  echo "ABORT: Phase S needs exactly 30 ledger cells"; exit 2; }
case "$MAX_IN_FLIGHT" in
  ''|*[!0-9]*) echo "ABORT: PHASE_S_MAX_IN_FLIGHT must be an integer"; exit 2 ;;
esac
[ "$MAX_IN_FLIGHT" -ge 1 ] && [ "$MAX_IN_FLIGHT" -le 10 ] || {
  echo "ABORT: Phase S in-flight cap must be between 1 and 10"; exit 2; }
[ -s "$PENDING" ] || { echo "PHASE_S_RETRY_QUEUE_EMPTY"; exit 0; }

IMG=$(awk -F= '$1=="image" {print $2}' "$MANIFEST")
CODE_SHA=$(awk -F= '$1=="code_sha" {print $2}' "$MANIFEST")
CONTROL=$(awk -F= '$1=="selected_control_arm" {print $2}' "$MANIFEST")
case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image missing"; exit 2;; esac
case "$CONTROL" in mult|k) ;; *) echo "ABORT: invalid control law"; exit 2;; esac

ACTIVE=0
while read -r arm rep season panel job execution; do
  state=$(gcloud run jobs executions describe "$execution" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.conditions[0].status)')
  case "$state" in
    True) ;;
    False)
      if ! awk -v execution="$execution" '$4==execution {found=1} END {exit !found}' \
          "$PENDING"; then
        echo "ABORT: unclassified current execution failed: $execution" >&2
        exit 1
      fi
      ;;
    *) ACTIVE=$((ACTIVE + 1)) ;;
  esac
done < "$LIST"
[ "$ACTIVE" -lt "$MAX_IN_FLIGHT" ] || {
  echo "PHASE_S_RETRY_HELD active=$ACTIVE cap=$MAX_IN_FLIGHT"; exit 3; }

read -r ARM REP SEASON FAILED REASON < "$PENDING"
read -r LEDGER_ARM LEDGER_REP LEDGER_SEASON PANEL JOB CURRENT < <(
  awk -v arm="$ARM" -v rep="$REP" -v season="$SEASON" \
    '$1==arm && $2==rep && $3==season {print}' "$LIST"
)
[ "$LEDGER_ARM $LEDGER_REP $LEDGER_SEASON $CURRENT" = \
    "$ARM $REP $SEASON $FAILED" ] || {
  echo "ABORT: pending retry does not match its ledger cell"; exit 2; }

# Pending entries were classified only after these three stores were checked.
# Recheck immediately before launch so a late/partial write cannot be hidden.
CANDIDATES=$(bq query --project_id="$PROJECT" --use_legacy_sql=false \
  --format=csv \
  "SELECT COUNT(*) n FROM \`$PROJECT.nfl_predictions.replay_candidates_staging\` WHERE panel_run_id='$PANEL' AND season=$SEASON" \
  | tail -1 | tr -d '[:space:]')
FEATURES=$(bq query --project_id="$PROJECT" --use_legacy_sql=false \
  --format=csv \
  "SELECT COUNT(*) n FROM \`$PROJECT.nfl_predictions.slate_player_features\` WHERE panel_run_id='$PANEL' AND season=$SEASON" \
  | tail -1 | tr -d '[:space:]')
ARTIFACTS=$({ gcloud storage ls \
  "gs://${PROJECT}-raw/cand_scores/${PANEL}/${SEASON}_w*.npz" \
  2>/dev/null || true; } | wc -l)
[ "${CANDIDATES:-0}" = 0 ] && [ "${FEATURES:-0}" = 0 ] \
    && [ "${ARTIFACTS:-0}" = 0 ] || {
  echo "ABORT: retry target has output candidates=$CANDIDATES features=$FEATURES artifacts=$ARTIFACTS"
  exit 1
}

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: replacement execution missing"; exit 1; }
gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json \
  | "$ROOT/.venv/bin/python" \
    "$ROOT/scripts/verify_sis_asoe_phase_s_execution.py" \
    --arm "$ARM" --replicate "$REP" --season "$SEASON" \
    --panel "$PANEL" --job "$JOB" --execution "$EXEC" \
    --image "$IMG" --code-sha "$CODE_SHA" --control-arm "$CONTROL" \
    --allow-nonterminal || {
      echo "ABORT: launched $EXEC but its immutable spec differs" >&2
      exit 1
    }
"$ROOT/.venv/bin/python" \
  "$ROOT/scripts/update_sis_asoe_phase_s_retry_ledger.py" \
  --run-dir "$OUT" --arm "$ARM" --replicate "$REP" --season "$SEASON" \
  --panel "$PANEL" --job "$JOB" --failed-execution "$FAILED" \
  --retry-execution "$EXEC" --reason "${REASON}_bounded_cap_${MAX_IN_FLIGHT}"
echo "PHASE_S_RETRY_RELEASED active_before=$ACTIVE cap=$MAX_IN_FLIGHT execution=$EXEC"
