#!/bin/bash
# Compare the frozen served-position Stage B panels and harvest one report.
# Usage: cloud_compare_served_position_stage_b.sh <IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
SOURCE=20260810-lockfix-e80-k1-role12union-8677d21
CONTROL=20260811-lockfix-e80-k1-role12-position-control-v1
TREATMENT=20260811-lockfix-e80-k1-role12-position-scales-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/panel-runs/$TREATMENT"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable comparator image required"; exit 2;; esac
case "$CODE_SHA" in
  ""|*[!0-9a-f]*) echo "ABORT: exact lowercase hexadecimal code SHA required"; exit 2 ;;
esac
for panel in "$CONTROL" "$TREATMENT"; do
  grep -q 'ACCEPTANCE PASSED' \
    "$ROOT/reports/panel-runs/$panel/acceptance_check.txt" || {
    echo "ABORT: check-only acceptance has not passed for $panel"; exit 2; }
done
EXEC_FILE="$OUT/comparison_execution.txt"
LOG_FILE="$OUT/comparison_log.json"
REPORT_FILE="$OUT/served_position_stage_b_comparison.json"
[ ! -s "$EXEC_FILE" ] || {
  echo "ABORT: immutable position comparison already recorded"; exit 2; }

JOB=compare-served-position-stage-b
ARGS="scripts/compare_served_position_lineup.py,--source,$SOURCE,--control,$CONTROL,--treatment,$TREATMENT,--experiment-code-sha,$CODE_SHA"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python --args "$ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 8Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: comparator deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: comparator execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$EXEC_FILE"

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || break
  sleep 20
done

gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND jsonPayload.disposition:*" \
  --project "$PROJECT" --limit 10 --order asc \
  --format='json(jsonPayload)' > "$LOG_FILE"
grep -q '"disposition"' "$LOG_FILE" || {
  echo "ABORT: structured position comparison report absent"; exit 1; }
"$ROOT/.venv/bin/python" - "$LOG_FILE" "$REPORT_FILE" <<'PY'
import json
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))
if len(rows) != 1 or "jsonPayload" not in rows[0]:
    raise SystemExit(f"ABORT: expected one structured report, got {len(rows)}")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(rows[0]["jsonPayload"], handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
[ "$STATE" = True ] || { echo "ABORT: comparator execution failed"; exit 1; }
echo "Served-position Stage B comparison complete: $REPORT_FILE"
