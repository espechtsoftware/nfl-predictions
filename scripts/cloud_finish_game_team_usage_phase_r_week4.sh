#!/bin/bash
# Validate and append the exact Week 4 repair slice, then relaunch the frozen
# Phase R analyzer.  Repair-panel rows remain in BigQuery as provenance.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/game-team-usage-runs/20260813-game-team-usage-phase-r-v1"
ORIGINAL=20260813-game-team-mult-r0-v1
REPAIR=20260813-game-team-mult-r0-2025-w4-repair1
TABLE="$PROJECT.nfl_predictions.replay_candidates_staging"
EXEC_FILE="$OUT/mult_r0_2025_week4_repair_execution.txt"
REPAIR_FILE="$OUT/mult_r0_2025_week4_repair.txt"
ANALYZER_RETRY="$OUT/analyzer_retry_execution.txt"

[ -s "$EXEC_FILE" ] || { echo "ABORT: repair execution missing"; exit 2; }
[ ! -e "$REPAIR_FILE" ] && [ ! -e "$ANALYZER_RETRY" ] || {
  echo "ABORT: repair already finished"; exit 2; }
execution=$(tr -d '[:space:]' < "$EXEC_FILE")
state=$(gcloud run jobs executions describe "$execution" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
succeeded=$(gcloud run jobs executions describe "$execution" --project "$PROJECT" \
  --region "$REGION" --format='value(status.succeededCount)')
[ "$state" = True ] && [ "$succeeded" = 1 ] || {
  echo "ABORT: repair is not a clean success ($state/$succeeded)"; exit 1; }

audit=$(bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
  "SELECT COUNT(DISTINCT week), COUNTIF(week=4), COUNT(DISTINCT IF(week=4,cand_ix,NULL)), COUNTIF(week=4 AND selected), COUNTIF(week=4 AND (labels_complete IS NOT TRUE OR actual_score IS NULL)), COUNT(DISTINCT IF(week=4,code_sha,NULL)), COUNT(DISTINCT IF(week=4,lever_env,NULL)), COUNT(DISTINCT IF(week=4,seeds,NULL)) FROM \`$TABLE\` WHERE panel_run_id='$REPAIR' AND season=2025" \
  | tail -1 | tr -d '[:space:]')
IFS=, read -r weeks rows unique_rows selected bad_labels shas levers seeds <<< "$audit"
[ "$weeks" = 4 ] && [ "$rows" -gt 0 ] && [ "$rows" = "$unique_rows" ] \
  && [ "$selected" = 80 ] && [ "$bad_labels" = 0 ] \
  && [ "$shas" = 1 ] && [ "$levers" = 1 ] && [ "$seeds" = 1 ] || {
    echo "ABORT: repair audit differs ($audit)"; exit 1; }
original_rows=$(bq query --project_id="$PROJECT" --use_legacy_sql=false \
  --format=csv "SELECT COUNT(*) FROM \`$TABLE\` WHERE panel_run_id='$ORIGINAL' AND season=2025 AND week=4" \
  | tail -1 | tr -d '[:space:]')
[ "${original_rows:-0}" = 0 ] || { echo "ABORT: original Week 4 is not empty"; exit 2; }

bq query --project_id="$PROJECT" --use_legacy_sql=false \
  "INSERT INTO \`$TABLE\` SELECT * REPLACE('$ORIGINAL' AS panel_run_id) FROM \`$TABLE\` WHERE panel_run_id='$REPAIR' AND season=2025 AND week=4" >/dev/null
copied=$(bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
  "SELECT COUNT(*) FROM \`$TABLE\` WHERE panel_run_id='$ORIGINAL' AND season=2025 AND week=4" \
  | tail -1 | tr -d '[:space:]')
[ "$copied" = "$rows" ] || { echo "ABORT: copied Week 4 row count differs"; exit 1; }

printf '%s\n' \
  "source_execution=$execution" "source_panel=$REPAIR" \
  "target_panel=$ORIGINAL" "season=2025" "week=4" \
  "candidate_rows=$rows" "selected_rows=$selected" \
  "repair_kind=append-only-exact-image-seed-and-lever-reproduction" \
  > "$REPAIR_FILE"
printf '%s %s %s %s %s %s %s\n' \
  mult 0 2025 replay-gtrmult0-2025-k2vtd "$execution" \
  BigQuery_429_candidate_append_repaired_from_exact_frozen_reproduction \
  "$rows" >> "$OUT/infrastructure_retries.txt"

JOB=analyze-game-team-usage-phase-r-v1
retry=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$retry" ] || { echo "ABORT: analyzer retry execution missing"; exit 1; }
printf '%s\n' "$retry" > "$ANALYZER_RETRY"
echo "GAME_TEAM_USAGE_PHASE_R_WEEK4_REPAIRED rows=$rows analyzer=$retry"
