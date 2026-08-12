#!/bin/bash
# Harvest and validate the sole repaired v2 active-label final-served gate.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260811-tabpfn-active-label-final-served-v2-pit-clean
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-active-label-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
[ -s "$OUT/execution.txt" ] || { echo "ABORT: execution id missing"; exit 2; }
[ -s "$MANIFEST" ] || { echo "ABORT: manifest missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || { echo "ABORT: immutable report exists"; exit 2; }
EXEC=$(head -1 "$OUT/execution.txt")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || { echo "ABORT: $EXEC is incomplete ($STATE)"; exit 1; }

FILTER="resource.type=\"cloud_run_job\" AND "
FILTER+="labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND "
FILTER+='textPayload:"TABPFN_ACTIVE_LABEL_FINAL_SERVED_JSON="'
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$MANIFEST" "$OUT/report.json" <<'PY'
import json
import math
import sys

prefix = "TABPFN_ACTIVE_LABEL_FINAL_SERVED_JSON="
payloads = [
    json.loads(line.split(prefix, 1)[1])
    for line in open(sys.argv[1], encoding="utf-8") if prefix in line
]
if len(payloads) != 1:
    raise SystemExit(
        f"ABORT: expected one v2 active-label report, got {len(payloads)}")
manifest = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line
)
report = payloads[0]
if report.get("version") != "v2":
    raise SystemExit("ABORT: active-label report is not v2")
if report.get("panel") != manifest.get("panel"):
    raise SystemExit("ABORT: active-label report panel differs from manifest")
if report.get("cache_tables") != {
    "control": "tabpfn_active_label_control_v2",
    "treatment": "tabpfn_active_label_treatment_v2",
}:
    raise SystemExit("ABORT: active-label cache identities differ")
if int(report.get("cache_rows", -1)) != 52307:
    raise SystemExit("ABORT: active-label cache row count differs")
if not report.get("disposition") or not report.get("gate"):
    raise SystemExit("ABORT: active-label report is incomplete")
usage = report.get("common_usage_law", {})
accepted = manifest.get("accepted_usage_law")
manifest_k = manifest.get("dirichlet_k", "")
if accepted == "multinomial":
    if usage != {
        "mode": "production-multinomial", "game_sim_usage": "", "k": ""
    }:
        raise SystemExit("ABORT: final-served usage differs from multinomial selection")
elif accepted == "dirichlet":
    try:
        same_k = math.isclose(
            float(usage.get("k", "nan")), float(manifest_k),
            rel_tol=0, abs_tol=0)
    except ValueError:
        same_k = False
    if usage.get("mode") != "data-fitted-dirichlet" or \
            usage.get("game_sim_usage") != "dirichlet" or not same_k:
        raise SystemExit("ABORT: final-served usage differs from fitted-K selection")
else:
    raise SystemExit("ABORT: manifest has an unknown accepted usage law")
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "PIT_ACTIVE_LABEL_FINAL_SERVED_COMPLETE $EXEC"
