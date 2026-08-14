#!/bin/bash
# Harvest the frozen SIS opponent pass-tail final-served gate.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-tabpfn-sis-pass-tail-final-served-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sis-pass-tail-runs/$RUN_ID"
EXEC_FILE="$OUT/execution.txt"
[ ! -s "$OUT/execution_retry.txt" ] || EXEC_FILE="$OUT/execution_retry.txt"
[ ! -s "$OUT/execution_harvest_retry.txt" ] || \
  EXEC_FILE="$OUT/execution_harvest_retry.txt"
EXEC=$(cat "$EXEC_FILE")
[ -n "$EXEC" ] || { echo "ABORT: SIS pass-tail gate execution missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable SIS pass-tail report already exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: SIS pass-tail gate $EXEC is not complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"TABPFN_SIS_PASS_TAIL_FINAL_SERVED_CHUNK=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import base64
import json
import sys
import zlib

prefix = "TABPFN_SIS_PASS_TAIL_FINAL_SERVED_CHUNK="
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
        raise SystemExit("ABORT: invalid SIS pass-tail chunk framing")
    chunks[index] = chunk
if expected_total is None or set(chunks) != set(range(1, expected_total + 1)):
    raise SystemExit("ABORT: incomplete SIS pass-tail report chunks")
encoded = "".join(chunks[index] for index in range(1, expected_total + 1))
report = json.loads(zlib.decompress(base64.b64decode(encoded)))
if report.get("disposition") not in {
        "tabpfn-sis-pass-tail-final-served-passes",
        "tabpfn-sis-pass-tail-final-served-fails"}:
    raise SystemExit("ABORT: SIS pass-tail disposition missing")
if not isinstance(report.get("gate", {}).get("passes"), bool):
    raise SystemExit("ABORT: SIS pass-tail gate is incomplete")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "TABPFN_SIS_PASS_TAIL_FINAL_SERVED_COMPLETE $OUT/report.json"
