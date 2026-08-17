#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260817-coherent-market-state-historical-score-v1
OUT="$ROOT/reports/coherent-market-state-historical-score-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"
PROTOCOL_SHA=80d85a6af930ee7640ce0e2733a5aee4293cdf3c6102f7659b2d991671464274
RUNNER="$ROOT/scripts/run_coherent_market_state_historical_score.py"
FINISHER="$ROOT/scripts/cloud_finish_coherent_market_state_historical_score.sh"

[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] && \
  [ -s "$OUT/upstream-receipt.json" ] || {
  echo "ABORT: coherent-state historical launch receipt is incomplete" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/execution.json" ] && \
  [ ! -e "$OUT/object-metadata.json" ] || {
  echo "ABORT: immutable coherent-state historical harvest already exists" >&2; exit 3; }

read -r JOB EXEC URI < "$EXECUTION"
TMP=$(mktemp -d "$OUT/.harvest.XXXXXX")
trap 'rm -rf -- "$TMP"' EXIT
gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$TMP/execution.json"
gcloud storage objects describe "$URI" --project "$PROJECT" --format=json \
  > "$TMP/object-metadata.json"

"$ROOT/.venv/bin/python" - "$TMP/execution.json" "$TMP/object-metadata.json" \
  "$MANIFEST" "$EXEC" "$JOB" "$URI" "$RUNNER" "$FINISHER" \
  "$PROTOCOL_SHA" <<'PY'
from hashlib import sha256
import json, re, sys
from pathlib import Path

execution_path, object_path, manifest_path = map(Path, sys.argv[1:4])
name, job, uri = sys.argv[4:7]
runner, finisher = map(Path, sys.argv[7:9])
protocol_sha = sys.argv[9]
m = dict(
    line.split("=", 1)
    for line in manifest_path.read_text().splitlines() if "=" in line
)
fixed = {
    "run_id": "20260817-coherent-market-state-historical-score-v1",
    "protocol_sha256": protocol_sha,
    "uses_realized_outcomes": "true",
    "production_change_licensed": "false",
    "canonical_fold": "R0", "seasons": "2023,2024,2025", "slates": "54",
    "cpu": "4", "memory": "16Gi", "timeout_seconds": "7200",
    "max_retries": "0",
}
if any(m.get(key) != value for key, value in fixed.items()) or \
        not re.fullmatch(r"[0-9a-f]{40}", m.get("code_sha", "")) or \
        not re.fullmatch(r".+@sha256:[0-9a-f]{64}", m.get("image", "")) or \
        m.get("runner_sha256") != sha256(runner.read_bytes()).hexdigest() or \
        m.get("finisher_sha256") != sha256(finisher.read_bytes()).hexdigest():
    raise SystemExit("ABORT: coherent-state historical manifest/source differs")
x = json.loads(execution_path.read_text())
if x.get("metadata", {}).get("name") != name:
    raise SystemExit("ABORT: coherent-state historical execution name differs")
s = x.get("status", {})
completed = [row for row in s.get("conditions", []) if row.get("type") == "Completed"]
if len(completed) != 1 or completed[0].get("status") != "True" or \
        int(s.get("succeededCount") or 0) != 1 or \
        int(s.get("failedCount") or 0) != 0 or not s.get("completionTime"):
    raise SystemExit("ABORT: coherent-state historical execution is not successful")
spec = x.get("spec", {})
task = spec.get("template", {}).get("spec", {})
containers = task.get("containers", [])
if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or len(containers) != 1:
    raise SystemExit("ABORT: coherent-state historical task shape differs")
c = containers[0]
expected_args = [
    "scripts/run_coherent_market_state_historical_score.py",
    "--upstream-receipt-uri", m["output_prefix"] + "/upstream-receipt.json",
    "--output-uri", uri,
]
env = {row.get("name"): str(row.get("value", "")) for row in c.get("env", [])}
if job != "coherent-market-historical-v1" or \
        c.get("image") != m["image"] or c.get("command") != ["python"] or \
        c.get("args") != expected_args or env != {
            "CODE_SHA": m["code_sha"], "ANALYSIS_IMAGE": m["image"],
        } or c.get("resources", {}).get("limits") != {
            "cpu": "4", "memory": "16Gi",
        } or task.get("maxRetries") != 0 or \
        str(task.get("timeoutSeconds")) != "7200" or \
        task.get("serviceAccountName") != \
        "817589974517-compute@developer.gserviceaccount.com":
    raise SystemExit("ABORT: coherent-state historical execution contract differs")
o = json.loads(object_path.read_text())
if not str(o.get("generation", "")).isdigit() or int(o.get("size", 0)) <= 0:
    raise SystemExit("ABORT: coherent-state historical object metadata differs")
PY

gcloud storage cp "$URI" "$TMP/report.json" --project "$PROJECT" >/dev/null
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" - \
  "$TMP/report.json" "$TMP/object-metadata.json" "$MANIFEST" \
  "$OUT/upstream-receipt.json" <<'PY'
from hashlib import sha256
import json, sys
from nfl_dfs.analysis.coherent_market_state_historical import aggregate_historical

report_path, object_path, manifest_path, upstream_path = sys.argv[1:]
raw = open(report_path, "rb").read()
r = json.loads(raw)
o = json.load(open(object_path, encoding="utf-8"))
m = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(manifest_path, encoding="utf-8") if "=" in line
)
upstream = json.load(open(upstream_path, encoding="utf-8"))
if int(o.get("size", -1)) != len(raw):
    raise SystemExit("ABORT: coherent-state historical report size differs")
if r.get("version") != "coherent-market-state-historical-score-v1" or \
        r.get("run_id") != m["run_id"] or \
        r.get("uses_realized_outcomes") is not True or \
        r.get("production_change_licensed") is not False or \
        r.get("canonical_fold") != "R0" or \
        r.get("protocol_sha256") != m["protocol_sha256"] or \
        r.get("scorer_code_sha") != m["code_sha"] or \
        r.get("scorer_image") != m["image"]:
    raise SystemExit("ABORT: coherent-state historical report identity differs")
if r.get("population") != {"seasons": [2023, 2024, 2025], "slates": 54} or \
        len(r.get("rows", [])) != 54:
    raise SystemExit("ABORT: coherent-state historical population differs")
p = r.get("native_actual_score_parity", {})
if p.get("registered_candidate_rows") != 68199 or \
        p.get("slots_per_roster") != 9 or p.get("malformed_rosters") != 0 or \
        p.get("missing_player_outcomes") != 0 or \
        p.get("compared_rows") != 68199 or \
        float(p.get("maximum_absolute_error", 1)) > 1e-9 or \
        float(p.get("absolute_tolerance", -1)) != 1e-9 or \
        float(p.get("relative_tolerance", -1)) != 0.0 or \
        p.get("source_storage_type") != "FLOAT":
    raise SystemExit("ABORT: coherent-state historical actual parity differs")
u = r.get("upstream", {})
receipt_object = u.get("receipt_object", {})
if u.get("run_id") != m["upstream_run_id"] or \
        u.get("code_sha") != upstream.get("code_sha") or \
        u.get("image") != upstream.get("image") or \
        u.get("strict_harvest_sha256") != upstream.get("strict_harvest_sha256") or \
        u.get("report_object") != upstream.get("report_object") or \
        u.get("shard_objects") != upstream.get("shard_objects") or \
        receipt_object.get("uri") != m["output_prefix"] + "/upstream-receipt.json" or \
        receipt_object.get("sha256") != m["upstream_receipt_sha256"]:
    raise SystemExit("ABORT: coherent-state historical upstream binding differs")
expected = aggregate_historical(r["rows"])
for key, value in expected.items():
    if r.get(key) != value:
        raise SystemExit(f"ABORT: coherent-state historical aggregate differs at {key}")
gate = r.get("gate", {})
conditions = gate.get("conditions", {})
if set(conditions) != {
    "selected_p200_gains_two_weeks", "selected_p210_nondecline",
    "selected_p220_nondecline", "selected_p230_nondecline",
    "selected_p240_nondecline", "candidate_p200_nondecline",
} or gate.get("historical_tail_signal_positive") is not all(conditions.values()):
    raise SystemExit("ABORT: coherent-state historical gate differs")
print("COHERENT_MARKET_STATE_HISTORICAL_REPORT_VALIDATED", gate["disposition"])
PY

mv "$TMP/execution.json" "$OUT/execution.json"
mv "$TMP/object-metadata.json" "$OUT/object-metadata.json"
mv "$TMP/report.json" "$OUT/report.json"
trap - EXIT
rmdir "$TMP"
sha256sum "$OUT/execution.json" > "$OUT/execution.sha256"
sha256sum "$OUT/object-metadata.json" > "$OUT/object-metadata.sha256"
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
DISPOSITION=$(
  "$ROOT/.venv/bin/python" -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["gate"]["disposition"])' \
    "$OUT/report.json"
)
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'executions=1' 'seasons=2023,2024,2025' 'slates=54' \
  'canonical_fold=R0' 'uses_realized_outcomes=true' \
  'production_change_licensed=false' "disposition=$DISPOSITION" \
  > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "COHERENT_MARKET_STATE_HISTORICAL_HARVESTED $RUN_ID $DISPOSITION"
