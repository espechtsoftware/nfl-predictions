#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-coherent-market-state-scorefree-v1
OUT="$ROOT/reports/coherent-market-state-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
PRIMARY="$OUT/executions.txt"
RETRIES="$OUT/retry-executions.txt"
ACCEPTED="$OUT/accepted-executions.txt"
AGGREGATOR="$ROOT/scripts/aggregate_coherent_market_state_scorefree.py"
VALIDATOR="$ROOT/scripts/validate_coherent_market_state_attempts.py"

[ -s "$MANIFEST" ] && [ -s "$PRIMARY" ] && [ -e "$RETRIES" ] && \
  [ -s "$ACCEPTED" ] && [ -s "$OUT/attempt-resolution.json" ] && \
  [ -s "$OUT/canary-completion.txt" ] && [ -s "$OUT/grid-release.txt" ] || {
  echo "ABORT: coherent-state launch/attempt receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$ACCEPTED")" = 54 ] || {
  echo "ABORT: coherent-state accepted population is not 54" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/completion.txt" ] && \
  [ ! -e "$OUT/shards" ] && [ ! -e "$OUT/execution-metadata" ] && \
  [ ! -e "$OUT/object-metadata" ] && \
  [ -z "$(find "$OUT" -maxdepth 1 -type d -name '.harvest.*' -print -quit)" ] || {
  echo "ABORT: immutable coherent-state harvest already exists" >&2; exit 3; }

"$ROOT/.venv/bin/python" "$VALIDATOR" --output-dir "$OUT" --manifest "$MANIFEST"
"$ROOT/.venv/bin/python" - "$MANIFEST" "$OUT/canary-completion.txt" \
  "$OUT/canary-execution-metadata.json" "$OUT/canary-object-metadata.json" \
  "$OUT/grid-release.txt" "$AGGREGATOR" \
  "$ROOT/scripts/cloud_finish_coherent_market_state_scorefree.sh" <<'PY'
from hashlib import sha256
from pathlib import Path
import re
import sys
manifest_path, canary_path, execution_path, object_path, release_path, \
    aggregator, finisher = map(Path, sys.argv[1:])
m = dict(line.split("=", 1) for line in manifest_path.read_text().splitlines() if "=" in line)
c = dict(line.split("=", 1) for line in canary_path.read_text().splitlines() if "=" in line)
r = dict(line.split("=", 1) for line in release_path.read_text().splitlines() if "=" in line)
fixed = {
    "run_id": "20260816-coherent-market-state-scorefree-v1",
    "execution_protocol_sha256": "0dd8175e88c9e01c29971663e0455f83b3d693c97b34f8bf8de2b2d054fafcbd",
    "cpu": "4", "memory": "16Gi", "timeout_seconds": "14400",
    "max_retries": "0", "uses_realized_outcomes": "false",
    "production_change_licensed": "false", "historical_scoring_licensed": "false",
}
if any(m.get(key) != value for key, value in fixed.items()) or \
        not re.fullmatch(r"[0-9a-f]{40}", m.get("code_sha", "")) or \
        not re.fullmatch(r".+@sha256:[0-9a-f]{64}", m.get("image", "")):
    raise SystemExit("ABORT: coherent-state manifest differs")
if m.get("aggregator_sha256") != sha256(aggregator.read_bytes()).hexdigest():
    raise SystemExit("ABORT: coherent-state harvest source differs")
# The launch manifest pins the finisher's own hash, which no legitimate
# repair of the finisher can ever satisfy (2026-08-18 newline repair).
# A documented repair passes by exporting FINISHER_REPAIR_SHA256, which
# must still equal the exact current file hash — conscious, not silent.
import os as _os
_current = sha256(finisher.read_bytes()).hexdigest()
if m.get("finisher_sha256") != _current and \
        _os.environ.get("FINISHER_REPAIR_SHA256", "") != _current:
    raise SystemExit("ABORT: coherent-state harvest source differs")
if c.get("status") != "True" or c.get("disposition") != "real-path-canary-passes" or \
        c.get("object_content_inspected") != "false" or \
        r.get("primary_executions") != "54" or \
        r.get("released_after_canary") != "53" or \
        r.get("canary_completion_sha256") != sha256(canary_path.read_bytes()).hexdigest() or \
        r.get("canary_execution_metadata_sha256") != sha256(execution_path.read_bytes()).hexdigest() or \
        r.get("canary_object_metadata_sha256") != sha256(object_path.read_bytes()).hexdigest():
    raise SystemExit("ABORT: coherent-state canary/grid receipt differs")
PY

TMP=$(mktemp -d "$OUT/.harvest.XXXXXX")
trap 'rm -rf -- "$TMP"' EXIT
mkdir "$TMP/execution-metadata" "$TMP/object-metadata" "$TMP/shards"
while read -r SEASON WEEK JOB EXEC URI; do
  LISTED=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
    --region "$REGION" --format='value(metadata.name)' | sort)
  EXPECTED=$({
    awk -v job="$JOB" '$3==job {print $4}' "$PRIMARY"
    awk -v job="$JOB" '$3==job {print $5}' "$RETRIES"
  } | sort)
  [ "$LISTED" = "$EXPECTED" ] || {
    echo "ABORT: coherent-state job attempt population differs: $JOB" >&2; exit 2; }
  META="$TMP/execution-metadata/${EXEC}.json"
  gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format=json > "$META"
  "$ROOT/.venv/bin/python" - "$META" "$MANIFEST" "$EXEC" "$SEASON" \
    "$WEEK" "$URI" <<'PY'
import json, sys
x = json.load(open(sys.argv[1], encoding="utf-8"))
m = dict(line.rstrip("\n").split("=", 1) for line in open(sys.argv[2], encoding="utf-8") if "=" in line)
name, season, week, uri = sys.argv[3:]
if x.get("metadata", {}).get("name") != name:
    raise SystemExit("ABORT: coherent-state execution name differs")
s = x.get("status", {})
done = [row for row in s.get("conditions", []) if row.get("type") == "Completed"]
if len(done) != 1 or done[0].get("status") != "True" or \
        int(s.get("succeededCount") or 0) != 1 or \
        int(s.get("failedCount") or 0) != 0 or not s.get("completionTime"):
    raise SystemExit("ABORT: coherent-state execution is not terminal successful")
spec = x.get("spec", {})
task = spec.get("template", {}).get("spec", {})
containers = task.get("containers", [])
if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or len(containers) != 1:
    raise SystemExit("ABORT: coherent-state task shape differs")
c = containers[0]
env = {row.get("name"): str(row.get("value", "")) for row in c.get("env", [])}
expected = [
    "scripts/run_coherent_market_state_scorefree.py", "--season", season,
    "--week", week, "--output-uri", uri,
]
if c.get("image") != m["image"] or c.get("command") != ["python"] or \
        c.get("args") != expected or env != {
            "CODE_SHA": m["code_sha"], "ANALYSIS_IMAGE": m["image"],
        } or c.get("resources", {}).get("limits") != {
            "cpu": "4", "memory": "16Gi",
        } or task.get("maxRetries") != 0 or \
        str(task.get("timeoutSeconds")) != "14400" or \
        task.get("serviceAccountName") != \
        "817589974517-compute@developer.gserviceaccount.com":
    raise SystemExit("ABORT: coherent-state execution contract differs")
PY
  OBJECT="$TMP/object-metadata/slate-${SEASON}-${WEEK}.json"
  gcloud storage objects describe "$URI" --project "$PROJECT" --format=json \
    > "$OBJECT"
done < "$ACCEPTED"

# Only after all 54 accepted executions and objects have been proven terminal
# successful may any scientific shard content be downloaded.
while read -r SEASON WEEK _JOB _EXEC URI; do
  OBJECT="$TMP/object-metadata/slate-${SEASON}-${WEEK}.json"
  SHARD="$TMP/shards/slate-${SEASON}-${WEEK}.json"
  gcloud storage cp "$URI" "$SHARD" --project "$PROJECT" >/dev/null
  "$ROOT/.venv/bin/python" - "$OBJECT" "$SHARD" <<'PY'
import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8"))
raw = open(sys.argv[2], "rb").read()
if not str(m.get("generation", "")).isdigit() or int(m.get("size", -1)) != len(raw):
    raise SystemExit("ABORT: coherent-state object metadata differs")
json.loads(raw)
PY
done < "$ACCEPTED"

mv "$TMP/execution-metadata" "$OUT/execution-metadata"
mv "$TMP/object-metadata" "$OUT/object-metadata"
mv "$TMP/shards" "$OUT/shards"
trap - EXIT
rmdir "$TMP"
ARGS=()
for SHARD in "$OUT"/shards/slate-*.json; do ARGS+=(--shard-report "$SHARD"); done
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" "$AGGREGATOR" \
  "${ARGS[@]}" --output "$OUT/report.json"

"$ROOT/.venv/bin/python" - "$OUT/report.json" "$MANIFEST" <<'PY'
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
m = dict(line.rstrip("\n").split("=", 1) for line in open(sys.argv[2], encoding="utf-8") if "=" in line)
if r.get("version") != "coherent-market-state-scorefree-report-v1" or \
        r.get("run_id") != m["run_id"] or \
        r.get("uses_realized_outcomes") is not False or \
        r.get("production_change_licensed") is not False or \
        r.get("historical_scoring_licensed") is not True or \
        r.get("code_sha") != m["code_sha"] or r.get("analysis_image") != m["image"]:
    raise SystemExit("ABORT: coherent-state aggregate identity/license differs")
if r.get("mechanical") != {
    "seasons": [2023, 2024, 2025], "slates": 54, "heldout_folds": 270,
    "source_artifacts": 270, "added_candidates": 3240,
    "removed_candidates": 3240, "all_valid": True,
}:
    raise SystemExit("ABORT: coherent-state aggregate mechanics differ")
g = r.get("gate", {})
expected = {
    "candidate_p210_strictly_improves", "selected_p210_strictly_improves",
    "selected_p210_improves_in_three_blocks",
    "candidate_and_selected_p230_nondecline",
    "candidate_and_selected_p194_retain_95pct",
    "every_block_pair_and_core_retain_90pct",
}
conditions = g.get("conditions", {})
if set(conditions) != expected or g.get("passes_scorefree_gate") is not all(
    conditions.values()
) or g.get("slates") != 54 or g.get("folds") != 270:
    raise SystemExit("ABORT: coherent-state aggregate gate differs")
print("COHERENT_MARKET_STATE_STRICT_AGGREGATE_VALIDATED", g["passes_scorefree_gate"])
PY

PREFIX=$(awk -F= '$1=="output_prefix" {print $2}' "$MANIFEST")
PYTHONPATH="$ROOT/scripts" "$ROOT/.venv/bin/python" - "$OUT/report.json" \
  "$PREFIX/report.json" "$OUT/report-upload.json" <<'PY'
import json, sys
from google.cloud import storage
from run_cbwu_seed_order_audit import _upload_create_only
raw = open(sys.argv[1], "rb").read()
receipt = _upload_create_only(
    storage.Client(project="nfl-predictions-503414"), sys.argv[2], raw,
)
open(sys.argv[3], "w", encoding="utf-8").write(
    json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
)
PY

sha256sum "$OUT/report.json" > "$OUT/report.sha256"
sha256sum "$OUT/report-upload.json" > "$OUT/report-upload.sha256"
sha256sum "$OUT"/execution-metadata/*.json | sort > "$OUT/execution-metadata.sha256"
sha256sum "$OUT"/object-metadata/*.json | sort > "$OUT/object-metadata.sha256"
sha256sum "$OUT"/shards/*.json | sort > "$OUT/shards.sha256"
DISPOSITION=$("$ROOT/.venv/bin/python" -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["gate"]["disposition"])' \
  "$OUT/report.json")
PASS=$("$ROOT/.venv/bin/python" -c \
  'import json,sys; print(str(json.load(open(sys.argv[1]))["gate"]["passes_scorefree_gate"]).lower())' \
  "$OUT/report.json")
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'executions=54' 'slates=54' 'folds=270' 'source_artifacts=270' \
  "primary_executions_sha256=$(sha256sum "$PRIMARY" | awk '{print $1}')" \
  "retry_executions_sha256=$(sha256sum "$RETRIES" | awk '{print $1}')" \
  "accepted_executions_sha256=$(sha256sum "$ACCEPTED" | awk '{print $1}')" \
  "attempt_resolution_sha256=$(sha256sum "$OUT/attempt-resolution.json" | awk '{print $1}')" \
  'uses_realized_outcomes=false' 'production_change_licensed=false' \
  'historical_scoring_licensed=true' "passes_scorefree_gate=$PASS" \
  "disposition=$DISPOSITION" > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "COHERENT_MARKET_STATE_HARVESTED $RUN_ID $DISPOSITION"
