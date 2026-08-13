#!/bin/bash
# Harvest exactly one terminal report from the frozen QB shell gate.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-fp-qb-shell-l4-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/fantasy-points-qb-shell-runs/$RUN_ID"
EXEC=$(cat "$OUT/execution.txt")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || { echo "ABORT: $EXEC is not a clean success ($STATE)"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable QB shell report already exists"; exit 2; }

gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"FP_QB_SHELL_JSON=\"" \
  --project "$PROJECT" --limit 10 --order asc --format='value(textPayload)' \
  > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "FP_QB_SHELL_JSON="
payloads = []
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix in line:
        payloads.append(json.loads(line.split(prefix, 1)[1]))
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one QB shell report, got {len(payloads)}")
report = payloads[0]
if not report.get("disposition") or not report.get("gate"):
    raise SystemExit("ABORT: QB shell report is incomplete")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "QB shell diagnostic harvested: $EXEC ($OUT/report.json)"
