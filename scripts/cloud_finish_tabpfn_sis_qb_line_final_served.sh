#!/bin/bash
# Harvest the frozen SIS QB line final-served gate.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-tabpfn-sis-qb-line-final-served-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sis-qb-line-runs/$RUN_ID"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: SIS QB line gate execution missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable SIS QB line report already exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: SIS QB line gate $EXEC is not complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"TABPFN_SIS_QB_LINE_FINAL_SERVED_JSON=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "TABPFN_SIS_QB_LINE_FINAL_SERVED_JSON="
payloads = [json.loads(line.split(prefix, 1)[1])
            for line in open(sys.argv[1], encoding="utf-8") if prefix in line]
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one SIS QB line report, got {len(payloads)}")
report = payloads[0]
if report.get("disposition") not in {
        "tabpfn-sis-qb-line-final-served-passes",
        "tabpfn-sis-qb-line-final-served-fails"}:
    raise SystemExit("ABORT: SIS QB line disposition missing")
if not isinstance(report.get("gate", {}).get("passes"), bool):
    raise SystemExit("ABORT: SIS QB line gate is incomplete")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "TABPFN_SIS_QB_LINE_FINAL_SERVED_COMPLETE $OUT/report.json"
