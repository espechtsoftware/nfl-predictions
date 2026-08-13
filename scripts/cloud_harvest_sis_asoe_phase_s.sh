#!/bin/bash
# Harvest successful immutable Phase S JSON after all mechanical gates pass.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/sis-asoe-phase-s-runs/20260813-sis-asoe-phase-s-v1"
EXEC_FILE="$OUT/analyzer_execution.txt"
[ -s "$EXEC_FILE" ] || { echo "ABORT: analyzer execution missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable Phase S report already exists"; exit 2; }
EXEC=$(tr -d '[:space:]' < "$EXEC_FILE")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || { echo "ABORT: analyzer is not successful ($STATE)"; exit 1; }
gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\"" \
  --project "$PROJECT" --limit 5000 --order=asc --format='value(textPayload)' \
  > "$OUT/raw_log.txt"
LINE=$(grep '^SIS_ASOE_PHASE_S_JSON=' "$OUT/raw_log.txt" | tail -1)
[ -n "$LINE" ] || { echo "ABORT: Phase S JSON marker absent"; exit 1; }
printf '%s' "${LINE#SIS_ASOE_PHASE_S_JSON=}" \
  | "$ROOT/.venv/bin/python" -m json.tool > "$OUT/report.json"
"$ROOT/.venv/bin/python" - "$OUT/report.json" <<'PY'
import json
import sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
if not r.get("mechanical_passes") or r.get("failures"):
    raise SystemExit("ABORT: Phase S mechanical audit did not pass")
print("SIS_ASOE_PHASE_S_HARVESTED", r["result"]["decision"])
PY
