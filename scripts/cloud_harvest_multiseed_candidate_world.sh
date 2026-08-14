#!/bin/bash
# Harvest the successful frozen artifact-only multi-seed factorial.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/multiseed-candidate-world-runs/20260813-multiseed-candidate-world-v1"
EXEC_FILE="$OUT/analyzer_execution.txt"
if [ -s "$OUT/analyzer_retry_execution.txt" ]; then
  [ -s "$OUT/analyzer_retry_manifest.txt" ] || {
    echo "ABORT: analyzer retry provenance is incomplete"; exit 2; }
  EXEC_FILE="$OUT/analyzer_retry_execution.txt"
fi
[ -s "$EXEC_FILE" ] || { echo "ABORT: analyzer execution missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable multi-seed report already exists"; exit 2; }
EXEC=$(tr -d '[:space:]' < "$EXEC_FILE")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || { echo "ABORT: analyzer is not successful ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"MULTISEED_CANDIDATE_WORLD_CHUNK=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 100 --order=asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
TMP=$(mktemp "$OUT/.report.XXXXXX.json")
trap 'rm -f "$TMP"' EXIT
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$TMP" <<'PY'
import base64
import json
import sys
import zlib

prefix = "MULTISEED_CANDIDATE_WORLD_CHUNK="
chunks = {}
total = None
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix not in line:
        continue
    header, chunk = line.split(prefix, 1)[1].rstrip("\n").split(":", 1)
    index, current_total = map(int, header.split("/", 1))
    if total is None:
        total = current_total
    if current_total != total or index in chunks:
        raise SystemExit("ABORT: invalid multi-seed chunk framing")
    chunks[index] = chunk
if total is None or set(chunks) != set(range(1, total + 1)):
    raise SystemExit("ABORT: incomplete multi-seed report chunks")
encoded = "".join(chunks[index] for index in range(1, total + 1))
r = json.loads(zlib.decompress(base64.b64decode(encoded)))
if not r.get("mechanical_passes") or r.get("failures"):
    raise SystemExit("ABORT: multi-seed mechanical audit did not pass")
result = r["result"]
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(r, handle, indent=2, sort_keys=True)
    handle.write("\n")
print(
    "MULTISEED_CANDIDATE_WORLD_HARVESTED",
    f"research={result['selected_arm']}",
    f"production={result['final_production_arm']}",
)
PY
mv "$TMP" "$OUT/report.json"
trap - EXIT
