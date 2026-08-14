#!/bin/bash
# Harvest the successful frozen artifact-only multi-seed factorial.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/multiseed-candidate-world-runs/20260813-multiseed-candidate-world-v1"
EXEC_FILE="$OUT/analyzer_execution.txt"
[ -s "$EXEC_FILE" ] || { echo "ABORT: analyzer execution missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable multi-seed report already exists"; exit 2; }
EXEC=$(tr -d '[:space:]' < "$EXEC_FILE")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || { echo "ABORT: analyzer is not successful ($STATE)"; exit 1; }
gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\"" \
  --project "$PROJECT" --limit 5000 --order=asc --format='value(textPayload)' \
  > "$OUT/raw_log.txt"
LINE=$(grep '^MULTISEED_CANDIDATE_WORLD_JSON=' "$OUT/raw_log.txt" | tail -1)
[ -n "$LINE" ] || { echo "ABORT: multi-seed JSON marker absent"; exit 1; }
printf '%s' "${LINE#MULTISEED_CANDIDATE_WORLD_JSON=}" \
  | "$ROOT/.venv/bin/python" -m json.tool > "$OUT/report.json"
"$ROOT/.venv/bin/python" - "$OUT/report.json" <<'PY'
import json
import sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
if not r.get("mechanical_passes") or r.get("failures"):
    raise SystemExit("ABORT: multi-seed mechanical audit did not pass")
result = r["result"]
print(
    "MULTISEED_CANDIDATE_WORLD_HARVESTED",
    f"research={result['selected_arm']}",
    f"production={result['final_production_arm']}",
)
PY
