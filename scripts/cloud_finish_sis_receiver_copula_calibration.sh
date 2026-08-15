#!/usr/bin/env bash
set -euo pipefail

# Harvest and validate calibration before any held-out deployment is allowed.

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=${1:-20260815-sis-receiver-copula-v1}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/sis-receiver-copula-runs/$RUN_ID/calibration"
MANIFEST="$OUT/manifest.txt"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: SIS calibration execution missing"; exit 2; }
[ -s "$MANIFEST" ] || { echo "ABORT: SIS calibration manifest missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable SIS calibration report exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: SIS calibration $EXEC is not complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"SIS_RECEIVER_COPULA_CALIBRATION_\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 500 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$MANIFEST" "$OUT/report.json" <<'PY'
import base64
import gzip
import hashlib
import json
import math
import sys

lines = list(open(sys.argv[1], encoding="utf-8"))
meta_prefix = "SIS_RECEIVER_COPULA_CALIBRATION_META="
chunk_prefix = "SIS_RECEIVER_COPULA_CALIBRATION_CHUNK="
metas = [json.loads(line.split(meta_prefix, 1)[1])
         for line in lines if meta_prefix in line]
if len(metas) != 1:
    raise SystemExit(f"ABORT: expected one calibration transport, got {len(metas)}")
meta = metas[0]
parts, totals = {}, set()
for line in lines:
    if chunk_prefix not in line:
        continue
    header, value = line.split(chunk_prefix, 1)[1].rstrip("\n").split(":", 1)
    index, total = map(int, header.split("/", 1))
    if index in parts:
        raise SystemExit("ABORT: duplicate calibration transport chunk")
    parts[index] = value
    totals.add(total)
if totals != {meta.get("chunks")} or set(parts) != set(range(meta.get("chunks", -1))):
    raise SystemExit("ABORT: incomplete calibration transport")
compressed = base64.b64decode(
    "".join(parts[index] for index in range(meta["chunks"])), validate=True)
content = gzip.decompress(compressed)
if len(compressed) != meta.get("gzip_bytes") or \
        hashlib.sha256(compressed).hexdigest() != meta.get("gzip_sha256") or \
        len(content) != meta.get("json_bytes") or \
        hashlib.sha256(content).hexdigest() != meta.get("json_sha256"):
    raise SystemExit("ABORT: calibration transport identity differs")
report = json.loads(content)
manifest = dict(line.rstrip("\n").split("=", 1)
                for line in open(sys.argv[2], encoding="utf-8") if "=" in line)
if report.get("version") != "sis-receiver-copula-calibration-v1" or \
        report.get("panel") != manifest.get("panel") or \
        report.get("run_identity") != {
            "run_id": manifest.get("run_id"), "code_sha": manifest.get("code_sha")}:
    raise SystemExit("ABORT: calibration identity differs")
if report.get("protocols") != {
        "parent_protocol_sha256": manifest.get("parent_protocol_sha256"),
        "calibration_amendment_sha256": manifest.get("calibration_amendment_sha256")}:
    raise SystemExit("ABORT: calibration protocol identity differs")
expected_grid = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
if report.get("strength_grid") != expected_grid or \
        len(report.get("selector_grid", [])) != len(expected_grid) or \
        [row.get("strength") for row in report["selector_grid"]] != expected_grid:
    raise SystemExit("ABORT: calibration grid differs")
if set(report.get("scorebooks", {})) != {
        format(value, ".2f") for value in expected_grid} or \
        set(report.get("grid_invariants", {})) != set(report["scorebooks"]):
    raise SystemExit("ABORT: calibration scorebook grid is incomplete")
if report.get("heldout_outcomes_queried") is not False or \
        report.get("retrospective_exact80_licensed") is not False:
    raise SystemExit("ABORT: calibration outcome/license disclosure differs")
valid = {"sis-receiver-copula-calibration-passes",
         "sis-receiver-copula-calibration-invalid-or-inconclusive"}
if report.get("disposition") not in valid or \
        bool(report.get("heldout_evaluation_licensed")) != (
            report.get("disposition") == "sis-receiver-copula-calibration-passes"):
    raise SystemExit("ABORT: calibration disposition/license differs")
if report.get("disposition") == "sis-receiver-copula-calibration-passes":
    selected = report.get("selected")
    if not report.get("passes") or not report.get("selected_repeat_exact") or \
            not selected or selected.get("strength") not in expected_grid or \
            not selected.get("required_support"):
        raise SystemExit("ABORT: passing calibration lacks passing evidence")
    for field in ("registered_absolute_log_error_sum", "joint_q90_brier",
                  "variogram_p0_5"):
        if not math.isfinite(float(selected.get(field))):
            raise SystemExit(f"ABORT: selected calibration {field} is invalid")
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
sha256sum "$OUT/report.json" "$MANIFEST" > "$OUT/attestation.sha256"
echo "SIS_RECEIVER_COPULA_CALIBRATION_COMPLETE $OUT/report.json"
