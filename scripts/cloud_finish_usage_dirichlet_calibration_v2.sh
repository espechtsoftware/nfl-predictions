#!/bin/bash
# Harvest the sole repaired-table usage-concentration diagnostic.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260812-data-fitted-usage-k-v2-pit-clean
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/usage-dirichlet-calibration-runs/$RUN_ID"
[ -s "$OUT/execution.txt" ] || { echo "ABORT: execution id missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || { echo "ABORT: report exists"; exit 2; }
EXEC=$(head -1 "$OUT/execution.txt")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || { echo "ABORT: $EXEC is incomplete ($STATE)"; exit 1; }

FILTER="resource.type=\"cloud_run_job\" AND "
FILTER+="labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND "
FILTER+='textPayload:"USAGE_DIRICHLET_CALIBRATION_JSON="'
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "USAGE_DIRICHLET_CALIBRATION_JSON="
payloads = []
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix in line:
        payloads.append(json.loads(line.split(prefix, 1)[1]))
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one usage report, got {len(payloads)}")
report = payloads[0]
if not report.get("disposition") or not report.get("gate"):
    raise SystemExit("ABORT: usage report is incomplete")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "PIT_USAGE_CALIBRATION_COMPLETE $EXEC"
