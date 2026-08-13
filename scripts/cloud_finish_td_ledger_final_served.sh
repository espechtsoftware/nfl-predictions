#!/bin/bash
# Harvest and strictly validate the frozen TD-ledger dependence gate.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-td-ledger-final-served-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/td-ledger-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: TD-ledger execution missing"; exit 2; }
[ -s "$MANIFEST" ] || { echo "ABORT: TD-ledger manifest missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable TD-ledger report already exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: TD-ledger execution $EXEC is not cleanly complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"TD_LEDGER_FINAL_SERVED_\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 300 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$MANIFEST" "$OUT/report.json" <<'PY'
import base64
import gzip
import hashlib
import json
import math
import sys

lines = list(open(sys.argv[1], encoding="utf-8"))
meta_prefix = "TD_LEDGER_FINAL_SERVED_META="
chunk_prefix = "TD_LEDGER_FINAL_SERVED_CHUNK="
metas = [json.loads(line.split(meta_prefix, 1)[1])
         for line in lines if meta_prefix in line]
if len(metas) != 1:
    raise SystemExit(f"ABORT: expected one TD-ledger transport manifest, got {len(metas)}")
meta = metas[0]
parts = {}
totals = set()
for line in lines:
    if chunk_prefix not in line:
        continue
    header, value = line.split(chunk_prefix, 1)[1].rstrip("\n").split(":", 1)
    index, total = map(int, header.split("/", 1))
    if index in parts:
        raise SystemExit("ABORT: duplicate TD-ledger transport chunk")
    parts[index] = value
    totals.add(total)
if totals != {meta.get("chunks")} or set(parts) != set(range(meta.get("chunks", -1))):
    raise SystemExit("ABORT: incomplete TD-ledger transport chunks")
try:
    compressed = base64.b64decode(
        "".join(parts[index] for index in range(meta["chunks"])), validate=True)
    content = gzip.decompress(compressed)
except Exception as exc:
    raise SystemExit("ABORT: TD-ledger transport is invalid") from exc
if len(compressed) != meta.get("gzip_bytes") or \
        hashlib.sha256(compressed).hexdigest() != meta.get("gzip_sha256"):
    raise SystemExit("ABORT: TD-ledger gzip identity differs")
if len(content) != meta.get("json_bytes") or \
        hashlib.sha256(content).hexdigest() != meta.get("json_sha256"):
    raise SystemExit("ABORT: TD-ledger JSON identity differs")
report = json.loads(content)
manifest = dict(line.rstrip("\n").split("=", 1)
                for line in open(sys.argv[2], encoding="utf-8") if "=" in line)
if report.get("version") != "v1" or report.get("panel") != manifest.get("panel"):
    raise SystemExit("ABORT: TD-ledger report identity differs")
if report.get("intervention") != {"TD_LEDGER": "1", "td_alloc_k": None}:
    raise SystemExit("ABORT: TD-ledger intervention differs")
if report.get("adaptive_retrospective") is not True:
    raise SystemExit("ABORT: TD-ledger adaptive disclosure missing")
if report.get("disposition") not in {
        "td-ledger-dependence-gate-passes",
        "td-ledger-dependence-gate-fails",
        "td-ledger-invalid-or-inconclusive"}:
    raise SystemExit("ABORT: TD-ledger disposition is invalid")
if bool(report.get("exact80_licensed")) != (
        report.get("disposition") == "td-ledger-dependence-gate-passes"):
    raise SystemExit("ABORT: TD-ledger exact-80 license differs")
if report.get("disposition") != "td-ledger-invalid-or-inconclusive" and \
        not report.get("invariants", {}).get("passes"):
    raise SystemExit("ABORT: valid TD-ledger result lacks passing invariants")
if not math.isclose(
        report.get("material_regression_tolerance_abs_log", -1),
        math.log(1.05), rel_tol=0, abs_tol=1e-15):
    raise SystemExit("ABORT: TD-ledger guard tolerance differs")
bootstrap = report.get("bootstrap", {})
if {key: bootstrap.get(key) for key in ("cluster", "replicates", "seed")} != {
        "cluster": "season-week-slate", "replicates": 2000, "seed": 1703}:
    raise SystemExit("ABORT: TD-ledger bootstrap contract differs")
if set(report.get("season_disclosures", {})) != {"control", "treatment"}:
    raise SystemExit("ABORT: TD-ledger season disclosures are missing")
for arm in ("control", "treatment"):
    if set(report["season_disclosures"][arm]) != {"2023", "2024", "2025"}:
        raise SystemExit("ABORT: TD-ledger season disclosure folds differ")
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "TD_LEDGER_FINAL_SERVED_COMPLETE $OUT/report.json"
