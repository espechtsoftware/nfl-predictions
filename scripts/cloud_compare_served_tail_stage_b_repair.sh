#!/bin/bash
# Repair only the failed Stage B comparator harness; never regenerate treatment.
# Usage: cloud_compare_served_tail_stage_b_repair.sh <IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
SOURCE=20260810-lockfix-e80-k1-role12union-8677d21
TREATMENT=20260811-lockfix-e80-k1-role12-tail1025-v1
TREATMENT_CODE_SHA=3431add
FAILED_EXEC=compare-served-tail-stage-b-pgwcw
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/panel-runs/$TREATMENT"
DIAGNOSTIC="$OUT/comparison_failure_diagnostic.json"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable repair image required"; exit 2;; esac
[ "$(cat "$OUT/comparison_execution.txt")" = "$FAILED_EXEC" ] || {
  echo "ABORT: original failed comparator identity differs"; exit 2; }
[ "$(gcloud run jobs executions describe "$FAILED_EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')" = False ] || {
  echo "ABORT: original comparator is not the recorded failed execution"; exit 2; }
"$ROOT/.venv/bin/python" - "$DIAGNOSTIC" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
audit = report["candidate_mean_audit"]
assert report["scientific_treatment_regenerated"] is False
assert audit["old_mismatches"] == 4342
assert audit["maximum_absolute_delta"] < audit["repaired_absolute_tolerance"]
assert audit["repaired_mismatches"] == 0
PY

EXEC_FILE="$OUT/comparison_repair_execution.txt"
RAW_LOG="$OUT/comparison_repair_raw_log.json"
REPORT_FILE="$OUT/served_tail_stage_b_comparison.json"
[ ! -s "$EXEC_FILE" ] || {
  echo "ABORT: immutable Stage B comparator repair already recorded"; exit 2; }
[ ! -s "$REPORT_FILE" ] || {
  echo "ABORT: Stage B comparison report already exists"; exit 2; }

JOB=compare-served-tail-stage-b-repair
ARGS="scripts/compare_served_tail_lineup.py,$TREATMENT,--source,$SOURCE,--treatment-code-sha,$TREATMENT_CODE_SHA"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python --args "$ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 8Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: repair deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: repair execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$EXEC_FILE"

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || break
  sleep 20
done

gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\"" \
  --project "$PROJECT" --limit 100 --order asc --format=json > "$RAW_LOG"
"$ROOT/.venv/bin/python" - "$RAW_LOG" "$REPORT_FILE" <<'PY'
import json
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))
reports = []
for row in rows:
    payload = row.get("jsonPayload")
    if isinstance(payload, dict) and "disposition" in payload:
        reports.append(payload)
        continue
    text = row.get("textPayload")
    if not isinstance(text, str):
        continue
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        continue
    if isinstance(payload, dict) and "disposition" in payload:
        reports.append(payload)
if len(reports) != 1:
    raise SystemExit(f"ABORT: expected one compact report, got {len(reports)}")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(reports[0], handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
[ "$STATE" = True ] || { echo "ABORT: comparator repair execution failed"; exit 1; }
echo "Served-tail Stage B comparator repair complete: $REPORT_FILE"
