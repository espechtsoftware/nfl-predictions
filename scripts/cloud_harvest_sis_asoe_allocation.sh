#!/bin/bash
# Harvest the immutable SIS ASOE Stage A report after Cloud completion.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-sis-asoe-allocation-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/sis-asoe-allocation-runs/$RUN_ID"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: ASOE execution missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable ASOE report already exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: ASOE execution $EXEC is not complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"SIS_ASOE_ALLOCATION_JSON=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json, sys
prefix = "SIS_ASOE_ALLOCATION_JSON="
payloads = [json.loads(line.split(prefix, 1)[1])
            for line in open(sys.argv[1]) if prefix in line]
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one ASOE report, got {len(payloads)}")
report = payloads[0]
if report.get("disposition") not in {
    "sis-asoe-allocation-passes-to-final-served",
    "sis-asoe-allocation-fails",
} or "gate" not in report or report.get("forbidden_outcomes_read") != []:
    raise SystemExit("ABORT: ASOE report is incomplete")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "SIS_ASOE_ALLOCATION_COMPLETE $OUT/report.json"
