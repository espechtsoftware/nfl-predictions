#!/bin/bash
# Harvest and validate the frozen incumbent portfolio effective-rank diagnostic.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-incumbent-effective-rank-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/portfolio-effective-rank-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: effective-rank execution missing"; exit 2; }
[ -s "$MANIFEST" ] || { echo "ABORT: effective-rank manifest missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable effective-rank report already exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: effective-rank execution $EXEC is not cleanly complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"PORTFOLIO_EFFECTIVE_RANK_\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 1000 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$MANIFEST" "$OUT/report.json" <<'PY'
import base64
import gzip
import hashlib
import json
import math
import sys

meta_prefix = "PORTFOLIO_EFFECTIVE_RANK_META="
chunk_prefix = "PORTFOLIO_EFFECTIVE_RANK_CHUNK="
lines = list(open(sys.argv[1], encoding="utf-8"))
metas = [json.loads(line.split(meta_prefix, 1)[1])
         for line in lines if meta_prefix in line]
if len(metas) != 1:
    raise SystemExit(
        f"ABORT: expected one effective-rank transport manifest, got {len(metas)}")
meta = metas[0]
parts = {}
totals = set()
for line in lines:
    if chunk_prefix not in line:
        continue
    header, value = line.split(chunk_prefix, 1)[1].rstrip("\n").split(":", 1)
    index, total = map(int, header.split("/", 1))
    if index in parts:
        raise SystemExit("ABORT: duplicate effective-rank transport chunk")
    parts[index] = value
    totals.add(total)
if totals != {meta.get("chunks")} or \
        set(parts) != set(range(meta.get("chunks", -1))):
    raise SystemExit("ABORT: incomplete effective-rank transport chunks")
try:
    compressed = base64.b64decode(
        "".join(parts[index] for index in range(meta["chunks"])), validate=True)
    content = gzip.decompress(compressed)
except Exception as exc:
    raise SystemExit("ABORT: effective-rank transport is invalid") from exc
if len(compressed) != meta.get("gzip_bytes") or \
        hashlib.sha256(compressed).hexdigest() != meta.get("gzip_sha256"):
    raise SystemExit("ABORT: effective-rank gzip identity differs")
if len(content) != meta.get("json_bytes") or \
        hashlib.sha256(content).hexdigest() != meta.get("json_sha256"):
    raise SystemExit("ABORT: effective-rank JSON identity differs")
report = json.loads(content)
manifest = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line)
if report.get("version") != "v1" or report.get("panel") != manifest.get("panel"):
    raise SystemExit("ABORT: effective-rank report identity differs")
if report.get("source") != "promoted" or report.get("slate_count") != 107:
    raise SystemExit("ABORT: effective-rank source/slate count differs")
if report.get("simulator_implied_only") is not True or \
        report.get("reads_realized_outcomes") is not False:
    raise SystemExit("ABORT: effective-rank outcome-scope flags differ")
slates = report.get("slates", [])
if len(slates) != 107 or \
        {row.get("season") for row in slates} != {2019, 2021, 2022, 2023, 2024, 2025} or \
        len({(row.get("season"), row.get("week")) for row in slates}) != 107:
    raise SystemExit("ABORT: effective-rank slate universe differs")
expected_lines = [187.0, 194.0, 200.0, 210.0, 220.0, 230.0, 240.0]
for row in slates:
    if row.get("selected_entries") != 80 or row.get("worlds") != 10000:
        raise SystemExit("ABORT: effective-rank entry/world count differs")
    if not row.get("simulator_implied_only") or \
            "not a formal bound" not in row.get("expected_bias", ""):
        raise SystemExit("ABORT: effective-rank caveat differs")
    if [tail.get("line") for tail in row.get("tails", [])] != expected_lines:
        raise SystemExit("ABORT: effective-rank tail grid differs")
    if set(row.get("nested_books", {})) != {"20", "40", "80"}:
        raise SystemExit("ABORT: effective-rank nested books differ")
    controls = row.get("same_world_controls", {})
    if controls.get("random_books", {}).get("books") != 20 or \
            not controls.get("top_sim_mean"):
        raise SystemExit("ABORT: effective-rank controls differ")
    headline = row.get("after_first_pc_deflation", {}).get("correlation")
    if headline is not None and not math.isfinite(
            float(headline.get("participation_ratio", math.nan))):
        raise SystemExit("ABORT: effective-rank headline is invalid")
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "PORTFOLIO_EFFECTIVE_RANK_COMPLETE $OUT/report.json"
