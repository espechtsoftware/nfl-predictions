#!/usr/bin/env bash
set -euo pipefail

# Harvest and strictly validate the fresh SIS receiver-copula reference.

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=${1:-20260815-sis-receiver-copula-v1}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/sis-receiver-copula-runs/$RUN_ID/reference"
ORDER_REPAIR="$ROOT/reports/2026-08-15-sis-reference-cross-run-order-repair.md"
PRIOR_REPORT="$ROOT/reports/sis-receiver-copula-runs/20260815-sis-receiver-copula-v1-repair1/reference/report.json"
EXPECTED_ORDER_REPAIR_SHA=e502b611887d78968970968bdd2cc44a752f80519d9e583a90dfb1dbb501a325
MANIFEST="$OUT/manifest.txt"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: SIS reference execution missing"; exit 2; }
[ -s "$MANIFEST" ] || { echo "ABORT: SIS reference manifest missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable SIS reference report exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: SIS reference $EXEC is not complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"SIS_RECEIVER_COPULA_REFERENCE_\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 300 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$MANIFEST" "$OUT/report.json" \
  "$ORDER_REPAIR" "$PRIOR_REPORT" "$EXPECTED_ORDER_REPAIR_SHA" <<'PY'
import base64
import gzip
import hashlib
import json
import re
import sys

from nfl_dfs.analysis.sis_receiver_copula import compare_control_scorebooks

lines = list(open(sys.argv[1], encoding="utf-8"))
meta_prefix = "SIS_RECEIVER_COPULA_REFERENCE_META="
chunk_prefix = "SIS_RECEIVER_COPULA_REFERENCE_CHUNK="
metas = [json.loads(line.split(meta_prefix, 1)[1])
         for line in lines if meta_prefix in line]
if len(metas) != 1:
    raise SystemExit(f"ABORT: expected one SIS reference transport, got {len(metas)}")
meta = metas[0]
parts, totals = {}, set()
for line in lines:
    if chunk_prefix not in line:
        continue
    header, value = line.split(chunk_prefix, 1)[1].rstrip("\n").split(":", 1)
    index, total = map(int, header.split("/", 1))
    if index in parts:
        raise SystemExit("ABORT: duplicate SIS reference transport chunk")
    parts[index] = value
    totals.add(total)
if totals != {meta.get("chunks")} or set(parts) != set(range(meta.get("chunks", -1))):
    raise SystemExit("ABORT: incomplete SIS reference transport")
try:
    compressed = base64.b64decode(
        "".join(parts[index] for index in range(meta["chunks"])), validate=True)
    content = gzip.decompress(compressed)
except Exception as exc:
    raise SystemExit("ABORT: invalid SIS reference transport") from exc
if len(compressed) != meta.get("gzip_bytes") or \
        hashlib.sha256(compressed).hexdigest() != meta.get("gzip_sha256"):
    raise SystemExit("ABORT: SIS reference gzip identity differs")
if len(content) != meta.get("json_bytes") or \
        hashlib.sha256(content).hexdigest() != meta.get("json_sha256"):
    raise SystemExit("ABORT: SIS reference JSON identity differs")
report = json.loads(content)
manifest = dict(line.rstrip("\n").split("=", 1)
                for line in open(sys.argv[2], encoding="utf-8") if "=" in line)
if report.get("version") != "sis-receiver-copula-reference-v1" or \
        report.get("historical_panel") != manifest.get("historical_panel") or \
        report.get("evaluation_panel") != manifest.get("evaluation_panel"):
    raise SystemExit("ABORT: SIS reference report identity differs")
if report.get("run_identity") != {
        "run_id": manifest.get("run_id"), "code_sha": manifest.get("code_sha")}:
    raise SystemExit("ABORT: SIS reference run/code identity differs")
if report.get("fresh_post_repair_reference") is not True or \
        report.get("prior_numeric_reference_consulted") is not False:
    raise SystemExit("ABORT: SIS reference freshness disclosure differs")
valid = {"sis-receiver-copula-reference-passes",
         "sis-receiver-copula-reference-invalid-or-inconclusive"}
if report.get("disposition") not in valid:
    raise SystemExit("ABORT: SIS reference disposition differs")
if bool(report.get("heldout_treatment_licensed")) != (
        report.get("disposition") == "sis-receiver-copula-reference-passes"):
    raise SystemExit("ABORT: SIS reference treatment license differs")
if report.get("retrospective_exact80_licensed") is not False:
    raise SystemExit("ABORT: SIS reference exact-80 license differs")
score_content = json.dumps(
    report.get("score"), sort_keys=True, separators=(",", ":"), allow_nan=False,
).encode()
if not re.fullmatch(r"[0-9a-f]{64}", report.get("score_sha256", "")) or \
        hashlib.sha256(score_content).hexdigest() != report.get("score_sha256") or \
        report.get("repeat_score_sha256") != report.get("score_sha256"):
    raise SystemExit("ABORT: SIS reference score fingerprint differs")
invariants = report.get("invariants", {})
if report.get("disposition") == "sis-receiver-copula-reference-passes" and \
        not invariants.get("passes"):
    raise SystemExit("ABORT: passing SIS reference lacks passing invariants")
for key in ("frame_sha256", "repeat_frame_sha256", "draws_sha256",
            "repeat_draws_sha256"):
    if not re.fullmatch(r"[0-9a-f]{64}", invariants.get(key, "")):
        raise SystemExit(f"ABORT: SIS reference {key} is invalid")
if invariants.get("frame_sha256") != invariants.get("repeat_frame_sha256") or \
        invariants.get("draws_sha256") != invariants.get("repeat_draws_sha256"):
    raise SystemExit("ABORT: SIS reference repeat fingerprints differ")
if manifest.get("run_id") == \
        "20260815-sis-receiver-copula-v1-repair2-canonical":
    repair_content = open(sys.argv[4], "rb").read()
    if hashlib.sha256(repair_content).hexdigest() != sys.argv[6] or \
            manifest.get("order_repair_sha256") != sys.argv[6]:
        raise SystemExit("ABORT: SIS canonical order-repair identity differs")
    if invariants.get("canonical_player_order") is not True:
        raise SystemExit("ABORT: SIS canonical reference order differs")
    prior_content = open(sys.argv[5], "rb").read()
    prior = json.loads(prior_content)
    comparison = compare_control_scorebooks(
        prior.get("score"), report.get("score"), absolute_tolerance=1e-12,
    )
    if not comparison.get("passes"):
        raise SystemExit("ABORT: SIS canonical scorebook differs from repair1")
    report["cross_run_order_repair"] = {
        **comparison,
        "prior_run_id": "20260815-sis-receiver-copula-v1-repair1",
        "prior_report_sha256": hashlib.sha256(prior_content).hexdigest(),
        "order_repair_sha256": sys.argv[6],
    }
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "SIS_RECEIVER_COPULA_REFERENCE_COMPLETE $OUT/report.json"
