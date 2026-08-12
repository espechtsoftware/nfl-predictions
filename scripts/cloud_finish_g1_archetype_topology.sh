#!/bin/bash
# Harvest and validate the sole frozen G1 topology diagnostic.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260812-g1-archetype-topology-v2
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/g1-topology-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: G1 execution missing"; exit 2; }
[ -s "$MANIFEST" ] || { echo "ABORT: G1 manifest missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable G1 report already exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: G1 execution $EXEC is not cleanly complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"G1_ARCHETYPE_TOPOLOGY_JSON=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$MANIFEST" "$OUT/report.json" "$OUT/archetype_labels.csv.gz" <<'PY'
import base64
import gzip
import hashlib
import json
import sys

prefix = "G1_ARCHETYPE_TOPOLOGY_JSON="
payloads = [
    json.loads(line.split(prefix, 1)[1])
    for line in open(sys.argv[1], encoding="utf-8") if prefix in line]
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one G1 report, got {len(payloads)}")
manifest = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line)
report = payloads[0]
if report.get("version") != "v1" or report.get("panel") != manifest.get("panel"):
    raise SystemExit("ABORT: G1 report identity differs")
if report.get("cache_table") != manifest.get("cache_table"):
    raise SystemExit("ABORT: G1 cache identity differs")
if report.get("disposition") not in {
        "stable-qb-hub-confirmed", "dependence-miss-not-stable-qb-hub",
        "g1-inconclusive"}:
    raise SystemExit("ABORT: G1 disposition is invalid")
if bool(report.get("g2_licensed")) != (
        report.get("disposition") == "stable-qb-hub-confirmed"):
    raise SystemExit("ABORT: G1 G2 license differs from disposition")
if not report.get("invariants", {}).get("passes"):
    raise SystemExit("ABORT: G1 terminal/G0 reproduction invariants failed")
if set(report.get("population", {}).get("relationship_counts", {})) != {
        "QB_WR", "QB_TE", "QB_RB", "WR_WR", "RB_RB", "TE_TE",
        "QB_OPP_QB", "QB_OPP_WR", "QB_OPP_TE", "WR_OPP_WR",
        "QB_XGAME_WR", "QB_XGAME_TE", "WR_XGAME_WR"}:
    raise SystemExit("ABORT: G1 relationship set differs")
if report.get("bootstrap") != {
        "cluster": "season-week-slate", "replicates": 2000, "seed": 1702}:
    raise SystemExit("ABORT: G1 bootstrap contract differs")
artifact = report.pop("archetype_label_artifact", {})
try:
    compressed = base64.b64decode(artifact["gzip_base64"], validate=True)
    content = gzip.decompress(compressed)
except Exception as exc:
    raise SystemExit("ABORT: G1 archetype artifact is invalid") from exc
if hashlib.sha256(compressed).hexdigest() != artifact.get("gzip_sha256") or \
        hashlib.sha256(content).hexdigest() != artifact.get("csv_sha256"):
    raise SystemExit("ABORT: G1 archetype artifact checksum differs")
open(sys.argv[4], "wb").write(compressed)
report["archetype_label_artifact"] = {
    key: value for key, value in artifact.items() if key != "gzip_base64"}
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "G1_ARCHETYPE_TOPOLOGY_COMPLETE $OUT/report.json"
