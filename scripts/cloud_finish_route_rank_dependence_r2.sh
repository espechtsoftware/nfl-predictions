#!/bin/bash
# Harvest the frozen fixed-midpoint Route rank dependence screen.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260814-route-rank-dependence-r2-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/route-rank-dependence-runs/$RUN_ID"
EXEC=$(tr -d '[:space:]' < "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: Route rank R2 execution missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable Route rank R2 report already exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: Route rank R2 gate $EXEC is not complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"ROUTE_RANK_DEPENDENCE_R2_CHUNK=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 30 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import base64
import json
import sys
import zlib

prefix = "ROUTE_RANK_DEPENDENCE_R2_CHUNK="
chunks = {}
expected_total = None
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix not in line:
        continue
    header, chunk = line.split(prefix, 1)[1].rstrip("\n").split(":", 1)
    index, total = map(int, header.split("/", 1))
    if expected_total is None:
        expected_total = total
    if total != expected_total or index in chunks:
        raise SystemExit("ABORT: invalid Route rank R2 chunk framing")
    chunks[index] = chunk
if expected_total is None or set(chunks) != set(range(1, expected_total + 1)):
    raise SystemExit("ABORT: incomplete Route rank R2 report chunks")
encoded = "".join(chunks[index] for index in range(1, expected_total + 1))
report = json.loads(zlib.decompress(base64.b64decode(encoded)))
if report.get("disposition") not in {
        "route-rank-dependence-r2-passes",
        "route-rank-dependence-r2-fails"}:
    raise SystemExit("ABORT: Route rank R2 disposition missing")
checks = report.get("gate", {}).get("checks", {})
if not isinstance(checks.get("passes"), bool):
    raise SystemExit("ABORT: Route rank R2 gate is incomplete")
if report.get("midpoint_weight") != 0.5:
    raise SystemExit("ABORT: Route rank R2 midpoint weight differs")
if report.get("sorted_marginal_max_abs_delta", 1) > 1e-10 or \
        report.get("mean_max_abs_delta", 1) > 1e-10:
    raise SystemExit("ABORT: Route rank R2 did not preserve control marginals")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "ROUTE_RANK_DEPENDENCE_R2_COMPLETE $OUT/report.json"
