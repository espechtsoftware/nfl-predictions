#!/bin/bash
# Harvest and validate the sole frozen G2 QB-rooted Gumbel factor gate.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260812-g2-qb-gumbel-factor-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/g2-qb-gumbel-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: G2 execution missing"; exit 2; }
[ -s "$MANIFEST" ] || { echo "ABORT: G2 manifest missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable G2 report already exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: G2 execution $EXEC is not cleanly complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"G2_QB_GUMBEL_FACTOR_\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 200 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$MANIFEST" "$OUT/report.json" <<'PY'
import base64
import gzip
import hashlib
import json
import math
import sys

meta_prefix = "G2_QB_GUMBEL_FACTOR_META="
chunk_prefix = "G2_QB_GUMBEL_FACTOR_CHUNK="
lines = list(open(sys.argv[1], encoding="utf-8"))
metas = [json.loads(line.split(meta_prefix, 1)[1])
         for line in lines if meta_prefix in line]
if len(metas) != 1:
    raise SystemExit(f"ABORT: expected one G2 transport manifest, got {len(metas)}")
meta = metas[0]
parts = {}
totals = set()
for line in lines:
    if chunk_prefix not in line:
        continue
    header, value = line.split(chunk_prefix, 1)[1].rstrip("\n").split(":", 1)
    index, total = map(int, header.split("/", 1))
    if index in parts:
        raise SystemExit("ABORT: duplicate G2 transport chunk")
    parts[index] = value
    totals.add(total)
if totals != {meta.get("chunks")} or set(parts) != set(range(meta.get("chunks", -1))):
    raise SystemExit("ABORT: incomplete G2 transport chunks")
try:
    compressed = base64.b64decode(
        "".join(parts[index] for index in range(meta["chunks"])), validate=True)
    content = gzip.decompress(compressed)
except Exception as exc:
    raise SystemExit("ABORT: G2 report transport is invalid") from exc
if len(compressed) != meta.get("gzip_bytes") or \
        hashlib.sha256(compressed).hexdigest() != meta.get("gzip_sha256"):
    raise SystemExit("ABORT: G2 report gzip identity differs")
if len(content) != meta.get("json_bytes") or \
        hashlib.sha256(content).hexdigest() != meta.get("json_sha256"):
    raise SystemExit("ABORT: G2 report JSON identity differs")
report = json.loads(content)
manifest = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line)
if report.get("version") != "v1" or report.get("panel") != manifest.get("panel"):
    raise SystemExit("ABORT: G2 report identity differs")
if report.get("historical_panel") != manifest.get("historical_panel") or \
        report.get("selected_eval_panel") != manifest.get("selected_eval_panel"):
    raise SystemExit("ABORT: G2 selected panel identity differs")
if report.get("disposition") not in {
        "g2-dependence-gate-passes", "g2-dependence-gate-fails",
        "g2-invalid-or-inconclusive"}:
    raise SystemExit("ABORT: G2 disposition is invalid")
if bool(report.get("exact80_licensed")) != (
        report.get("disposition") == "g2-dependence-gate-passes"):
    raise SystemExit("ABORT: G2 exact-80 license differs")
fit = report.get("fit", {})
if fit.get("calibration_seasons") != [2019, 2021, 2022] or \
        len(fit.get("grid", [])) != 81:
    raise SystemExit("ABORT: G2 calibration grid differs")
selected = fit.get("selected", {})
if not any(
        math.isclose(row.get("theta_wr", -1), selected.get("theta_wr", -2),
                     rel_tol=0, abs_tol=0)
        and math.isclose(row.get("theta_te", -1), selected.get("theta_te", -2),
                         rel_tol=0, abs_tol=0)
        for row in fit.get("grid", [])):
    raise SystemExit("ABORT: G2 selected cell is absent from grid")
bootstrap = report.get("bootstrap", {})
if {key: bootstrap.get(key) for key in ("cluster", "replicates", "seed")} != {
        "cluster": "season-week-slate", "replicates": 2000, "seed": 1703}:
    raise SystemExit("ABORT: G2 bootstrap contract differs")
if set(bootstrap.get("metrics", {})) != {
        "joint_q90_brier", "variogram_p0_5"}:
    raise SystemExit("ABORT: G2 bootstrap metrics differ")
if report.get("disposition") != "g2-invalid-or-inconclusive" and \
        not report.get("invariants", {}).get("passes"):
    raise SystemExit("ABORT: valid G2 disposition lacks passing invariants")
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "G2_QB_GUMBEL_FACTOR_COMPLETE $OUT/report.json"
