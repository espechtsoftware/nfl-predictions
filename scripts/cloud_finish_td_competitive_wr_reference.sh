#!/bin/bash
# Harvest and strictly validate the clean repaired-path competitive-WR reference.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=${1:-20260814-td-competitive-wr-v1}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/td-competitive-wr-runs/$RUN_ID/reference"
MANIFEST="$OUT/manifest.txt"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: competitive-WR reference execution missing"; exit 2; }
[ -s "$MANIFEST" ] || { echo "ABORT: competitive-WR reference manifest missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable competitive-WR reference report exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: competitive-WR reference $EXEC is not complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"TD_COMPETITIVE_WR_REFERENCE_\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 300 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$MANIFEST" "$OUT/report.json" <<'PY'
import base64
import gzip
import hashlib
import json
import math
import re
import sys

lines = list(open(sys.argv[1], encoding="utf-8"))
meta_prefix = "TD_COMPETITIVE_WR_REFERENCE_META="
chunk_prefix = "TD_COMPETITIVE_WR_REFERENCE_CHUNK="
metas = [json.loads(line.split(meta_prefix, 1)[1])
         for line in lines if meta_prefix in line]
if len(metas) != 1:
    raise SystemExit(f"ABORT: expected one reference transport, got {len(metas)}")
meta = metas[0]
parts, totals = {}, set()
for line in lines:
    if chunk_prefix not in line:
        continue
    header, value = line.split(chunk_prefix, 1)[1].rstrip("\n").split(":", 1)
    index, total = map(int, header.split("/", 1))
    if index in parts:
        raise SystemExit("ABORT: duplicate reference transport chunk")
    parts[index] = value
    totals.add(total)
if totals != {meta.get("chunks")} or set(parts) != set(range(meta.get("chunks", -1))):
    raise SystemExit("ABORT: incomplete reference transport")
try:
    compressed = base64.b64decode(
        "".join(parts[index] for index in range(meta["chunks"])), validate=True)
    content = gzip.decompress(compressed)
except Exception as exc:
    raise SystemExit("ABORT: invalid reference transport") from exc
if len(compressed) != meta.get("gzip_bytes") or \
        hashlib.sha256(compressed).hexdigest() != meta.get("gzip_sha256"):
    raise SystemExit("ABORT: reference gzip identity differs")
if len(content) != meta.get("json_bytes") or \
        hashlib.sha256(content).hexdigest() != meta.get("json_sha256"):
    raise SystemExit("ABORT: reference JSON identity differs")
report = json.loads(content)
manifest = dict(line.rstrip("\n").split("=", 1)
                for line in open(sys.argv[2], encoding="utf-8") if "=" in line)
if report.get("version") != "td-competitive-wr-reference-v1" or \
        report.get("panel") != manifest.get("panel"):
    raise SystemExit("ABORT: reference report identity differs")
if report.get("run_identity") != {
        "run_id": manifest.get("run_id"), "code_sha": manifest.get("code_sha")}:
    raise SystemExit("ABORT: reference run/code identity differs")
if report.get("adaptive_retrospective") is not True or \
        report.get("prior_treatment_and_disposition_ignored") is not True:
    raise SystemExit("ABORT: reference adaptive disclosure differs")
if not math.isclose(report.get("reference_tolerance", -1), 1e-12,
                    rel_tol=0, abs_tol=0):
    raise SystemExit("ABORT: reference tolerance differs")
valid = {"td-competitive-wr-reference-passes",
         "td-competitive-wr-reference-invalid-or-inconclusive"}
if report.get("disposition") not in valid:
    raise SystemExit("ABORT: reference disposition differs")
if bool(report.get("treatment_licensed")) != (
        report.get("disposition") == "td-competitive-wr-reference-passes"):
    raise SystemExit("ABORT: reference license differs")
score_content = json.dumps(
    report.get("score"), sort_keys=True, separators=(",", ":"),
    allow_nan=False,
).encode()
if not re.fullmatch(r"[0-9a-f]{64}", report.get("score_sha256", "")) or \
        hashlib.sha256(score_content).hexdigest() != report.get("score_sha256"):
    raise SystemExit("ABORT: reference score fingerprint differs")
if report.get("disposition") == "td-competitive-wr-reference-passes" and \
        not report.get("invariants", {}).get("passes"):
    raise SystemExit("ABORT: passing reference lacks passing invariants")
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "TD_COMPETITIVE_WR_REFERENCE_COMPLETE $OUT/report.json"
