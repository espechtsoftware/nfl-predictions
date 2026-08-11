#!/bin/bash
# Run and harvest the frozen same-season last-four Advanced Passing tail gate.
# Usage: bash scripts/cloud_fantasy_points_same_season_passing.sh <IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260811-fp-same-season-passing-l4-v1
SOURCE_RUN=20260811T063609Z__same-season-advanced-passing-last-four-v1
PANEL=20260810-lockfix-e80-k1-8677d21
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/fantasy-points-same-season-passing-runs/$RUN_ID"
ACCEPT="$ROOT/reports/panel-runs/$PANEL/acceptance_check.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
[ -s "$ACCEPT" ] && grep -q 'ACCEPTANCE PASSED' "$ACCEPT" || {
  echo "ABORT: corrected K1 check-only acceptance is not recorded"; exit 2; }
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable same-season passing execution already recorded"; exit 2; }

SOURCE_CHECK=$(bq query --project_id="$PROJECT" --use_legacy_sql=false \
  --format=csv --quiet "
SELECT
  COUNT(*) AS passing_rows,
  COUNT(DISTINCT source_run_id) AS passing_runs,
  ANY_VALUE(source_run_id) AS passing_run
FROM \`$PROJECT.nfl_raw.fantasy_points_advanced_passing_l4\`
" | tail -n 1)
[ "$SOURCE_CHECK" = "2879,1,$SOURCE_RUN" ] || {
  echo "ABORT: imported same-season source contract differs: $SOURCE_CHECK"; exit 2; }

mkdir -p "$OUT"
printf 'run_id=%s\nimage=%s\npanel=%s\nsource_run=%s\npassing_rows=2879\nsupported_rows=1636\nheld_out=2023 2024 2025\ntarget_weeks=5-18\n' \
  "$RUN_ID" "$IMG" "$PANEL" "$SOURCE_RUN" > "$OUT/manifest.txt"

JOB=fantasy-points-same-season-passing
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "fantasy-points-same-season-passing-diagnostic,--panel,$PANEL" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 4Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: same-season passing deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: same-season passing execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || break
  sleep 20
done

gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"FP_SAME_SEASON_PASSING_JSON=\"" \
  --project "$PROJECT" --limit 10 --order asc --format='value(textPayload)' \
  > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "FP_SAME_SEASON_PASSING_JSON="
payloads = []
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix in line:
        payloads.append(json.loads(line.split(prefix, 1)[1]))
if len(payloads) != 1:
    raise SystemExit(
        f"ABORT: expected one same-season passing report, got {len(payloads)}")
if not payloads[0].get("disposition") or not payloads[0].get("gate"):
    raise SystemExit("ABORT: same-season passing report is incomplete")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(payloads[0], handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

[ "$STATE" = True ] || { echo "ABORT: $EXEC failed"; exit 1; }
echo "Same-season passing diagnostic complete: $EXEC ($OUT/report.json)"
