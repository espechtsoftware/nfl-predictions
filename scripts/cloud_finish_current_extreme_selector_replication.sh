#!/bin/bash
# Harvest the frozen current-stack extreme-selector replication.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PANEL=20260812-pitclean-e80-selected-tabpfn-active-v2
OUT="$ROOT/reports/selector-runs/${PANEL}-extreme-replication"
EXEC=$(cat "$OUT/execution.txt")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || { echo "ABORT: $EXEC is $STATE"; exit 1; }
[ ! -e "$OUT/report.json" ] || { echo "ABORT: report already exists"; exit 2; }

gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"EXTREME_SELECTOR_CONFIRMATION_JSON=\"" \
  --project "$PROJECT" --limit 10 --order asc --format='value(textPayload)' \
  > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "EXTREME_SELECTOR_CONFIRMATION_JSON="
payloads = []
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix in line:
        payloads.append(json.loads(line.split(prefix, 1)[1]))
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one selector report, got {len(payloads)}")
report = payloads[0]
if report.get("mechanical_checks", {}).get("complete_slates") != 54:
    raise SystemExit("ABORT: current-stack replication is not exactly 54 slates")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "CURRENT_EXTREME_SELECTOR_REPLICATION_COMPLETE $EXEC"
