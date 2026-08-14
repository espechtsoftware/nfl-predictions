#!/bin/bash
# Harvest the frozen, mechanically valid pass-tail exact-80 report.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sis-pass-tail-runs/20260814-sis-pass-tail-exact80-v1"
EXEC_FILE="$OUT/analyzer_execution.txt"
MANIFEST="$OUT/manifest.txt"
ANALYZER_MANIFEST="$OUT/analyzer_manifest.txt"
[ -s "$EXEC_FILE" ] && [ -s "$MANIFEST" ] && [ -s "$ANALYZER_MANIFEST" ] || {
  echo "ABORT: analyzer provenance is incomplete"; exit 2; }
[ ! -e "$OUT/report.json" ] || { echo "ABORT: immutable report already exists"; exit 2; }
EXEC=$(tr -d '[:space:]' < "$EXEC_FILE")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || { echo "ABORT: analyzer is not successful ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"TABPFN_SIS_PASS_TAIL_EXACT80_V1_CHUNK=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 100 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" \
  "$MANIFEST" "$ANALYZER_MANIFEST" <<'PY'
import base64
import json
import sys
import zlib

prefix = "TABPFN_SIS_PASS_TAIL_EXACT80_V1_CHUNK="
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
        raise SystemExit("ABORT: invalid pass-tail chunk framing")
    chunks[index] = chunk
if total is None or set(chunks) != set(range(1, total + 1)):
    raise SystemExit("ABORT: incomplete pass-tail report chunks")
encoded = "".join(chunks[index] for index in range(1, total + 1))
report = json.loads(zlib.decompress(base64.b64decode(encoded)))
manifest = dict(line.rstrip("\n").split("=", 1)
                for line in open(sys.argv[3], encoding="utf-8") if "=" in line)
audit = dict(line.rstrip("\n").split("=", 1)
             for line in open(sys.argv[4], encoding="utf-8") if "=" in line)
if report.get("disposition") != "valid" or \
        not report.get("mechanical_passes") or report.get("failures"):
    raise SystemExit("ABORT: pass-tail exact-80 mechanical audit failed")
checks = {
    "expected_code_sha": manifest.get("generation_code_sha"),
    "phase_s_arm": manifest.get("phase_s_arm"),
    "phase_s_report_sha256": audit.get("phase_s_report_sha256"),
    "cache_validation_sha256": audit.get("cache_validation_sha256"),
    "final_served_report_sha256": audit.get("final_served_report_sha256"),
}
for field, expected in checks.items():
    if report.get(field) != expected:
        raise SystemExit(f"ABORT: report {field} differs from manifest")
decision = report.get("result", {}).get("decision", {})
if decision.get("selected_arm") not in {"control", "treatment"}:
    raise SystemExit("ABORT: pass-tail decision is not registered")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
"$ROOT/.venv/bin/python" - "$OUT/report.json" "$OUT/selected_pass_tail.txt" "$EXEC" <<'PY'
import json
import sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
d = r["result"]["decision"]
arm = d["selected_arm"]
table = r[f"{arm}_cache"]
schedules = r[f"{arm}_schedules"]
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    handle.write(f"selected_arm={arm}\n")
    handle.write(f"selected_cache_table={table}\n")
    handle.write("selected_schedules_json=" + json.dumps(schedules, sort_keys=True) + "\n")
    handle.write(f"deciding_threshold={d.get('deciding_threshold')}\n")
    handle.write(f"analyzer_execution={sys.argv[3]}\n")
print("TABPFN_SIS_PASS_TAIL_EXACT80_V1_SELECTED", arm, d)
PY
