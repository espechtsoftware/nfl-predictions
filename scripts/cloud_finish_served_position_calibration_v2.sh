#!/bin/bash
# Harvest and validate the sole PIT-clean served-position refit.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260812-served-position-calibration-v2-pit-clean
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/served-position-calibration-runs/$RUN_ID"
[ -s "$OUT/execution.txt" ] || { echo "ABORT: execution missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || { echo "ABORT: report exists"; exit 2; }
EXEC=$(head -1 "$OUT/execution.txt")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" --region "$REGION" \
  --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || { echo "ABORT: $EXEC is incomplete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"SERVED_POSITION_CALIBRATION_JSON=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/manifest.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "SERVED_POSITION_CALIBRATION_JSON="
payloads = [json.loads(line.split(prefix, 1)[1]) for line in open(sys.argv[1], encoding="utf-8") if prefix in line]
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one position report, got {len(payloads)}")
manifest = dict(line.rstrip("\n").split("=", 1) for line in open(sys.argv[2], encoding="utf-8") if "=" in line)
report = payloads[0]
contract = report.get("contract", {})
if contract != {
    "version": "v2",
    "panel": manifest["panel"],
    "model_ensemble": int(manifest["model_ensemble"]),
    "tabpfn_table": "tabpfn_projections_pit_v2",
}:
    raise SystemExit("ABORT: repaired position contract differs from manifest")
if not report.get("disposition") or not report.get("r2_final_served_fit") or not report.get("gate"):
    raise SystemExit("ABORT: position report is incomplete")
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "PIT_POSITION_CALIBRATION_COMPLETE $EXEC"
