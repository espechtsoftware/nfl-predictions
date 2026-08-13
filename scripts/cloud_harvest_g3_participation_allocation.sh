#!/bin/bash
# Harvest the immutable G3 Stage A score-free report after Cloud completion.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-g3-participation-allocation-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/g3-participation-allocation-runs/$RUN_ID"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: G3 execution missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable G3 report already exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: G3 execution $EXEC is not complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"G3_PARTICIPATION_ALLOCATION_JSON=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json, sys
prefix = "G3_PARTICIPATION_ALLOCATION_JSON="
payloads = [json.loads(line.split(prefix, 1)[1])
            for line in open(sys.argv[1]) if prefix in line]
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one G3 report, got {len(payloads)}")
report = payloads[0]
if report.get("disposition") not in {
    "g3-stage-a-passes-to-dependence-gate",
    "g3-stage-a-conditional-allocation-fails",
} or "gate" not in report:
    raise SystemExit("ABORT: G3 report is incomplete")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "G3_PARTICIPATION_ALLOCATION_COMPLETE $OUT/report.json"

