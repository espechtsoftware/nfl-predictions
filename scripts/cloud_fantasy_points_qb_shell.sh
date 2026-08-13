#!/bin/bash
# Launch the frozen Fantasy Points QB offense-by-defense shell-fit gate.
# Usage: bash scripts/cloud_fantasy_points_qb_shell.sh <IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-fp-qb-shell-l4-v1
PANEL=20260810-lockfix-e80-k1-8677d21
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/fantasy-points-qb-shell-runs/$RUN_ID"
ACCEPT="$ROOT/reports/panel-runs/$PANEL/acceptance_check.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
[ -s "$ACCEPT" ] && grep -q 'ACCEPTANCE PASSED' "$ACCEPT" || {
  echo "ABORT: corrected K1 check-only acceptance is not recorded"; exit 2; }
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable QB shell execution already recorded"; exit 2; }

SOURCE_CHECK=$(bq query --project_id="$PROJECT" --use_legacy_sql=false \
  --format=csv --quiet "
SELECT
  COUNT(*) AS source_rows,
  COUNT(DISTINCT offense_source_run_id) AS offense_runs,
  ANY_VALUE(offense_source_run_id) AS offense_run,
  COUNT(DISTINCT defense_source_run_id) AS defense_runs,
  ANY_VALUE(defense_source_run_id) AS defense_run
FROM \`$PROJECT.nfl_raw.fantasy_points_qb_shell_l4\`
" | tail -n 1)
IFS=, read -r SOURCE_ROWS OFFENSE_RUNS OFFENSE_RUN DEFENSE_RUNS DEFENSE_RUN \
  <<< "$SOURCE_CHECK"
[ "$SOURCE_ROWS" = 1792 ] && [ "$OFFENSE_RUNS" = 1 ] \
  && [ "$DEFENSE_RUNS" = 1 ] || {
  echo "ABORT: imported QB shell source contract differs: $SOURCE_CHECK"; exit 2; }
case "$OFFENSE_RUN" in *__same-season-qb-shell-fit-last-four-v1) ;; *)
  echo "ABORT: offense run identity differs: $OFFENSE_RUN"; exit 2;; esac
[ "$DEFENSE_RUN" = 20260811T053208Z__same-season-coverage-last-four-v1 ] || {
  echo "ABORT: defense run identity differs: $DEFENSE_RUN"; exit 2; }

mkdir -p "$OUT"
printf 'run_id=%s\nimage=%s\npanel=%s\noffense_run=%s\ndefense_run=%s\nsource_rows=%s\nheld_out=2023 2024 2025\ntarget_weeks=5-18\n' \
  "$RUN_ID" "$IMG" "$PANEL" "$OFFENSE_RUN" "$DEFENSE_RUN" "$SOURCE_ROWS" \
  > "$OUT/manifest.txt"

JOB=fantasy-points-qb-shell
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "fantasy-points-qb-shell-diagnostic,--panel,$PANEL" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 4Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: QB shell deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: QB shell execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "QB shell diagnostic launched: $EXEC"
