#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=${1:-20260815-sis-receiver-copula-v1}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/sis-receiver-copula-runs/$RUN_ID/heldout"
MANIFEST="$OUT/manifest.txt"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: SIS held-out execution missing"; exit 2; }
[ -s "$MANIFEST" ] || { echo "ABORT: SIS held-out manifest missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || { echo "ABORT: immutable held-out report exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || { echo "ABORT: SIS held-out $EXEC is not complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"SIS_RECEIVER_COPULA_HELDOUT_\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 500 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$MANIFEST" "$OUT/report.json" <<'PY'
import base64
import gzip
import hashlib
import json
import sys

lines = list(open(sys.argv[1], encoding="utf-8"))
meta_prefix = "SIS_RECEIVER_COPULA_HELDOUT_META="
chunk_prefix = "SIS_RECEIVER_COPULA_HELDOUT_CHUNK="
metas = [json.loads(line.split(meta_prefix, 1)[1])
         for line in lines if meta_prefix in line]
if len(metas) != 1:
    raise SystemExit(f"ABORT: expected one held-out transport, got {len(metas)}")
meta = metas[0]
parts, totals = {}, set()
for line in lines:
    if chunk_prefix not in line:
        continue
    header, value = line.split(chunk_prefix, 1)[1].rstrip("\n").split(":", 1)
    index, total = map(int, header.split("/", 1))
    if index in parts:
        raise SystemExit("ABORT: duplicate held-out transport chunk")
    parts[index] = value
    totals.add(total)
if totals != {meta.get("chunks")} or set(parts) != set(range(meta.get("chunks", -1))):
    raise SystemExit("ABORT: incomplete held-out transport")
compressed = base64.b64decode(
    "".join(parts[index] for index in range(meta["chunks"])), validate=True)
content = gzip.decompress(compressed)
if len(compressed) != meta.get("gzip_bytes") or \
        hashlib.sha256(compressed).hexdigest() != meta.get("gzip_sha256") or \
        len(content) != meta.get("json_bytes") or \
        hashlib.sha256(content).hexdigest() != meta.get("json_sha256"):
    raise SystemExit("ABORT: held-out transport identity differs")
report = json.loads(content)
manifest = dict(line.rstrip("\n").split("=", 1)
                for line in open(sys.argv[2], encoding="utf-8") if "=" in line)
if report.get("version") != "sis-receiver-copula-heldout-v1" or \
        report.get("historical_panel") != manifest.get("historical_panel") or \
        report.get("evaluation_panel") != manifest.get("evaluation_panel") or \
        report.get("run_identity") != {
            "run_id": manifest.get("run_id"), "code_sha": manifest.get("code_sha")}:
    raise SystemExit("ABORT: held-out identity differs")
for name in ("reference", "calibration"):
    attestation = report.get(f"{name}_attestation")
    encoded = json.dumps(
        attestation, sort_keys=True, separators=(",", ":"),
    ).encode()
    if hashlib.sha256(encoded).hexdigest() != manifest.get(
            f"{name}_attestation_sha256"):
        raise SystemExit(f"ABORT: held-out {name} attestation differs")
if set(report.get("by_season", {})) != {"2023", "2024", "2025"} or \
        "paired_whole_slate_bootstrap" not in report:
    raise SystemExit("ABORT: held-out mandatory diagnostics are incomplete")
valid = {"sis-receiver-copula-gate-passes", "sis-receiver-copula-gate-fails",
         "sis-receiver-copula-invalid-or-inconclusive"}
if report.get("disposition") not in valid or \
        report.get("retrospective_exact80_licensed") is not False or \
        bool(report.get("prospective_2026_shadow_licensed")) != (
            report.get("disposition") == "sis-receiver-copula-gate-passes"):
    raise SystemExit("ABORT: held-out disposition/license differs")
if report.get("disposition") != "sis-receiver-copula-invalid-or-inconclusive" and \
        not report.get("invariants", {}).get("passes"):
    raise SystemExit("ABORT: valid held-out disposition lacks passing invariants")
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
sha256sum "$OUT/report.json" "$MANIFEST" > "$OUT/attestation.sha256"
echo "SIS_RECEIVER_COPULA_HELDOUT_COMPLETE $OUT/report.json"
