#!/bin/bash
# Harvest frozen PFR secondary final-served gate.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-tabpfn-pfr-secondary-final-served-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-pfr-secondary-runs/$RUN_ID"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: PFR gate execution missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable PFR report already exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: PFR gate $EXEC is not complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"TABPFN_PFR_SECONDARY_FINAL_SERVED_JSON=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json, sys
prefix = "TABPFN_PFR_SECONDARY_FINAL_SERVED_JSON="
payloads = [json.loads(line.split(prefix, 1)[1])
            for line in open(sys.argv[1], encoding="utf-8") if prefix in line]
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one PFR report, got {len(payloads)}")
report = payloads[0]
if report.get("disposition") not in {
        "tabpfn-pfr-secondary-final-served-eligible",
        "tabpfn-pfr-secondary-final-served-no-eligible-drop"}:
    raise SystemExit("ABORT: PFR disposition missing")
gate = report.get("gate", {})
if not isinstance(gate.get("passes"), bool) or \
        set(gate.get("treatments", {})) != {
            "drop_rates", "drop_top_cb", "drop_all"}:
    raise SystemExit("ABORT: PFR gate incomplete")
selected = gate.get("selected_arm")
if gate["passes"] != (selected in {"drop_rates", "drop_top_cb", "drop_all"}):
    raise SystemExit("ABORT: PFR branch selection is inconsistent")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "TABPFN_PFR_SECONDARY_FINAL_SERVED_COMPLETE $OUT/report.json"
