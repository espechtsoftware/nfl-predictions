#!/bin/bash
# Harvest and validate the sole frozen SCHED final-served execution.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260812-tabpfn-sched-final-served-v1-pit-clean
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sched-runs/$RUN_ID"
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
FILTER+='textPayload:"TABPFN_SCHED_FINAL_SERVED_JSON="'
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$MANIFEST" "$OUT/report.json" <<'PY'
import json
import math
import sys

prefix = "TABPFN_SCHED_FINAL_SERVED_JSON="
payloads = [
    json.loads(line.split(prefix, 1)[1])
    for line in open(sys.argv[1], encoding="utf-8") if prefix in line
]
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one SCHED report, got {len(payloads)}")
manifest = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line
)
report = payloads[0]
if report.get("version") != "v1" or report.get("panel") != manifest.get("panel"):
    raise SystemExit("ABORT: SCHED report identity differs from manifest")
if report.get("label_law") != manifest.get("label_law"):
    raise SystemExit("ABORT: SCHED report label law differs")
if report.get("cache_tables") != {
    "control": "tabpfn_sched_control_v1",
    "treatment": "tabpfn_sched_treatment_v1",
} or int(report.get("cache_rows", -1)) != 52307:
    raise SystemExit("ABORT: SCHED report cache contract differs")
if not report.get("disposition") or not report.get("gate"):
    raise SystemExit("ABORT: SCHED report is incomplete")
usage = report.get("common_usage_law", {})
accepted = manifest.get("accepted_usage_law")
if accepted == "multinomial":
    expected = {"mode": "production-multinomial", "game_sim_usage": "", "k": ""}
    if usage != expected:
        raise SystemExit("ABORT: SCHED report usage differs from multinomial")
elif accepted == "dirichlet":
    try:
        same_k = math.isclose(
            float(usage.get("k", "nan")), float(manifest.get("dirichlet_k")),
            rel_tol=0, abs_tol=0)
    except ValueError:
        same_k = False
    if usage.get("mode") != "data-fitted-dirichlet" or \
            usage.get("game_sim_usage") != "dirichlet" or not same_k:
        raise SystemExit("ABORT: SCHED report usage differs from fitted K")
else:
    raise SystemExit("ABORT: SCHED manifest usage law is invalid")
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "TABPFN_SCHED_FINAL_SERVED_COMPLETE $EXEC"
