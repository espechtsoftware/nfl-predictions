#!/bin/bash
# Harvest the successful immutable Phase R JSON after its audit completes.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/game-team-usage-runs/20260813-game-team-usage-phase-r-v1"
EXEC_FILE="$OUT/analyzer_execution.txt"
[ -s "$EXEC_FILE" ] || { echo "ABORT: analyzer execution missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable Phase R report already exists"; exit 2; }
EXEC=$(tr -d '[:space:]' < "$EXEC_FILE")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || { echo "ABORT: analyzer is not successful ($STATE)"; exit 1; }
gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\"" \
  --project "$PROJECT" --limit 5000 --order=asc --format='value(textPayload)' \
  > "$OUT/raw_log.txt"
LINE=$(grep '^GAME_TEAM_USAGE_PHASE_R_JSON=' "$OUT/raw_log.txt" | tail -1)
[ -n "$LINE" ] || { echo "ABORT: Phase R JSON marker absent"; exit 1; }
printf '%s' "${LINE#GAME_TEAM_USAGE_PHASE_R_JSON=}" \
  | "$ROOT/.venv/bin/python" -m json.tool > "$OUT/report.json"
"$ROOT/.venv/bin/python" - "$OUT/report.json" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
if not report.get("mechanical_passes") or report.get("failures"):
    raise SystemExit("ABORT: Phase R mechanical audit did not pass")
print("GAME_TEAM_USAGE_PHASE_R_HARVESTED", report["result"]["decision"])
PY
