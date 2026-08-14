#!/bin/bash
# Harvest the frozen adaptive SIS RB opponent run-tail final-served gate.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260814-tabpfn-sis-rb-runtail-final-served-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sis-rb-runtail-runs/$RUN_ID"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: run-tail gate execution missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable run-tail report already exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: run-tail gate $EXEC is not complete ($STATE)"; exit 1; }
META_FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"TABPFN_SIS_RB_RUNTAIL_FINAL_SERVED_META=\""
CHUNK_FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"TABPFN_SIS_RB_RUNTAIL_FINAL_SERVED_CHUNK=\""
gcloud logging read "$META_FILTER" --project "$PROJECT" --limit 5 --order asc \
  --format='value(textPayload)' > "$OUT/raw_meta_log.txt"
gcloud logging read "$CHUNK_FILTER" --project "$PROJECT" --limit 100 --order asc \
  --format='value(textPayload)' > "$OUT/raw_chunk_log.txt"
"$ROOT/.venv/bin/python" - \
  "$OUT/raw_meta_log.txt" "$OUT/raw_chunk_log.txt" "$OUT/report.json" <<'PY'
import base64
import hashlib
import json
import sys
import zlib

meta_prefix = "TABPFN_SIS_RB_RUNTAIL_FINAL_SERVED_META="
chunk_prefix = "TABPFN_SIS_RB_RUNTAIL_FINAL_SERVED_CHUNK="
meta_rows = [
    json.loads(line.split(meta_prefix, 1)[1])
    for line in open(sys.argv[1], encoding="utf-8") if meta_prefix in line
]
if len(meta_rows) != 1:
    raise SystemExit(f"ABORT: expected one run-tail transport meta row, got {len(meta_rows)}")
meta = meta_rows[0]
chunks = {}
expected_total = None
for line in open(sys.argv[2], encoding="utf-8"):
    if chunk_prefix not in line:
        continue
    header, chunk = line.split(chunk_prefix, 1)[1].rstrip("\n").split(":", 1)
    index, total = map(int, header.split("/", 1))
    if expected_total is None:
        expected_total = total
    if total != expected_total or index in chunks:
        raise SystemExit("ABORT: invalid run-tail chunk framing")
    chunks[index] = chunk
if expected_total is None or expected_total != meta.get("chunks") or \
        set(chunks) != set(range(expected_total)):
    raise SystemExit("ABORT: incomplete run-tail transport chunks")
encoded = "".join(chunks[index] for index in range(expected_total))
compressed = base64.b64decode(encoded, validate=True)
if len(compressed) != meta.get("zlib_bytes") or \
        hashlib.sha256(compressed).hexdigest() != meta.get("zlib_sha256"):
    raise SystemExit("ABORT: run-tail compressed payload identity differs")
content = zlib.decompress(compressed)
if len(content) != meta.get("json_bytes") or \
        hashlib.sha256(content).hexdigest() != meta.get("json_sha256"):
    raise SystemExit("ABORT: run-tail JSON payload identity differs")
report = json.loads(content)
if report.get("disposition") not in {
        "tabpfn-sis-rb-runtail-final-served-passes",
        "tabpfn-sis-rb-runtail-final-served-fails"}:
    raise SystemExit("ABORT: run-tail disposition missing")
if report.get("adaptive_retrospective") is not True:
    raise SystemExit("ABORT: run-tail adaptive label missing")
gate = report.get("gate", {})
if not isinstance(gate.get("passes"), bool) or \
        not isinstance(gate.get("equal_q95_q99_mean_ratio_below_1"), bool) or \
        not isinstance(gate.get("maximum_mean_delta_at_most_1e_10"), bool):
    raise SystemExit("ABORT: run-tail gate incomplete")
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "TABPFN_SIS_RB_RUNTAIL_FINAL_SERVED_COMPLETE $OUT/report.json"
