#!/bin/bash
# Harvest the frozen team-QB final-served gate.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260812-tabpfn-team-qb-final-served-v1-pit-clean
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-team-qb-runs/$RUN_ID"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: team-QB gate execution missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable team-QB gate report already exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: team-QB gate $EXEC is not cleanly complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"TABPFN_TEAM_QB_FINAL_SERVED_JSON=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "TABPFN_TEAM_QB_FINAL_SERVED_JSON="
payloads = [
    json.loads(line.split(prefix, 1)[1])
    for line in open(sys.argv[1], encoding="utf-8") if prefix in line]
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one team-QB report, got {len(payloads)}")
report = payloads[0]
if report.get("disposition") not in {
        "tabpfn-team-qb-final-served-passes",
        "tabpfn-team-qb-final-served-fails"}:
    raise SystemExit("ABORT: team-QB gate disposition missing")
if not isinstance(report.get("gate", {}).get("passes"), bool):
    raise SystemExit("ABORT: team-QB gate is incomplete")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "TABPFN_TEAM_QB_FINAL_SERVED_COMPLETE $OUT/report.json"
