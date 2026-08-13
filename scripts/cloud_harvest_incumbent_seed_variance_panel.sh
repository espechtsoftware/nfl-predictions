#!/bin/bash
# Harvest the atomic seed audit/report after its Cloud execution succeeds.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-incumbent-seed-variance-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/incumbent-seed-variance-runs/$RUN_ID"
EXEC=$(cat "$OUT/analyzer_execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: seed analyzer execution missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable seed report already exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: seed analyzer $EXEC is not complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"INCUMBENT_SEED_VARIANCE_JSON=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json, sys
prefix = "INCUMBENT_SEED_VARIANCE_JSON="
records = [line.split(prefix, 1)[1] for line in open(sys.argv[1]) if prefix in line]
if len(records) != 1:
    raise SystemExit(f"ABORT: expected one seed report, got {len(records)}")
report = json.loads(records[0])
if not report.get("mechanical_passes") or report.get("failures"):
    raise SystemExit("ABORT: seed report mechanical gate did not pass")
if report.get("result", {}).get("interpretation") not in {
        "stable", "borderline", "materially-monte-carlo-sensitive"}:
    raise SystemExit("ABORT: seed interpretation missing")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "INCUMBENT_SEED_VARIANCE_COMPLETE $OUT/report.json"
