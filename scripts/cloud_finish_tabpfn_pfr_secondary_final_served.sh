#!/bin/bash
# Harvest frozen PFR secondary final-served gate.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-tabpfn-pfr-secondary-final-served-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-pfr-secondary-runs/$RUN_ID"
EXEC=$(cat "$OUT/repair_execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: PFR gate execution missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable PFR report already exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: PFR gate $EXEC is not complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"TABPFN_PFR_SECONDARY_FINAL_SERVED_\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 100 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import base64
import gzip
import hashlib
import json
import sys

meta_prefix = "TABPFN_PFR_SECONDARY_FINAL_SERVED_META="
chunk_prefix = "TABPFN_PFR_SECONDARY_FINAL_SERVED_CHUNK="
lines = list(open(sys.argv[1], encoding="utf-8"))
metas = [
    json.loads(line.split(meta_prefix, 1)[1])
    for line in lines if meta_prefix in line]
if len(metas) != 1:
    raise SystemExit(f"ABORT: expected one PFR transport manifest, got {len(metas)}")
meta = metas[0]
parts = {}
totals = set()
for line in lines:
    if chunk_prefix not in line:
        continue
    header, value = line.split(chunk_prefix, 1)[1].rstrip("\n").split(":", 1)
    index, total = map(int, header.split("/", 1))
    if index in parts:
        raise SystemExit("ABORT: duplicate PFR transport chunk")
    parts[index] = value
    totals.add(total)
if totals != {meta.get("chunks")} or \
        set(parts) != set(range(meta.get("chunks", -1))):
    raise SystemExit("ABORT: incomplete PFR transport chunks")
try:
    compressed = base64.b64decode(
        "".join(parts[index] for index in range(meta["chunks"])),
        validate=True)
    content = gzip.decompress(compressed)
except Exception as exc:
    raise SystemExit("ABORT: PFR report transport is invalid") from exc
if len(compressed) != meta.get("gzip_bytes") or \
        hashlib.sha256(compressed).hexdigest() != meta.get("gzip_sha256"):
    raise SystemExit("ABORT: PFR report transport gzip identity differs")
if len(content) != meta.get("json_bytes") or \
        hashlib.sha256(content).hexdigest() != meta.get("json_sha256"):
    raise SystemExit("ABORT: PFR report transport JSON identity differs")
report = json.loads(content)
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
