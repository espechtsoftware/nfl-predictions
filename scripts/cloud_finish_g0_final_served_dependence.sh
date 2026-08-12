#!/bin/bash
# Harvest and validate the sole frozen G0 dependence diagnostic.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260812-g0-final-served-dependence-v2
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/g0-dependence-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: G0 execution missing"; exit 2; }
[ -s "$MANIFEST" ] || { echo "ABORT: G0 manifest missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable G0 report already exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: G0 execution $EXEC is not cleanly complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"G0_FINAL_SERVED_DEPENDENCE_JSON=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$MANIFEST" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "G0_FINAL_SERVED_DEPENDENCE_JSON="
payloads = [
    json.loads(line.split(prefix, 1)[1])
    for line in open(sys.argv[1], encoding="utf-8") if prefix in line]
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one G0 report, got {len(payloads)}")
manifest = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line)
report = payloads[0]
if report.get("version") != "v1" or report.get("panel") != manifest.get("panel"):
    raise SystemExit("ABORT: G0 report identity differs")
if report.get("cache_table") != manifest.get("cache_table"):
    raise SystemExit("ABORT: G0 selected cache differs")
if report.get("disposition") not in {
        "dependence-premise-reproduced",
        "dependence-premise-miss",
        "dependence-premise-inconclusive"}:
    raise SystemExit("ABORT: G0 disposition is invalid")
if set(report.get("cells", {})) != {
        "multiplicity_ge2", "multiplicity_ge3", "multiplicity_ge4",
        "qb_wr", "qb_te", "qb_rb", "wr_wr", "rb_rb", "te_te"}:
    raise SystemExit("ABORT: G0 registered cell set differs")
if report.get("bootstrap") != {"clusters": 54, "replicates": 2000, "seed": 1701}:
    raise SystemExit("ABORT: G0 bootstrap contract differs")
if not report.get("invariants", {}).get("passes"):
    raise SystemExit("ABORT: G0 terminal invariants failed")
licensed = report.get("disposition") == "dependence-premise-miss"
if bool(report.get("g1_licensed")) != licensed:
    raise SystemExit("ABORT: G0 G1 license differs from disposition")
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "G0_FINAL_SERVED_DEPENDENCE_COMPLETE $OUT/report.json"
