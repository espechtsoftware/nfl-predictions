#!/usr/bin/env bash
set -euo pipefail

# Validate the actual 2023-W1 coherent-state job before releasing 53 cells.

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-coherent-market-state-scorefree-v1
OUT="$ROOT/reports/coherent-market-state-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
EXPECTED_JOB=coherent-state-s2023-w1-v1
EXPECTED_RUNNER=scripts/run_coherent_market_state_scorefree.py
EXPECTED_TIMEOUT=14400
EXECUTION_PROTOCOL_SHA=0dd8175e88c9e01c29971663e0455f83b3d693c97b34f8bf8de2b2d054fafcbd

[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] || {
  echo "ABORT: coherent-state canary launch receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 1 ] || {
  echo "ABORT: coherent-state canary must precede the other 53 cells" >&2; exit 2; }
[ ! -e "$OUT/canary-completion.txt" ] && \
  [ ! -e "$OUT/canary-execution-metadata.json" ] && \
  [ ! -e "$OUT/canary-object-metadata.json" ] || {
  echo "ABORT: immutable coherent-state canary receipt already exists" >&2; exit 3; }

read -r SEASON WEEK JOB EXEC URI < "$EXECUTIONS"
[ "$SEASON" = 2023 ] && [ "$WEEK" = 1 ] && [ "$JOB" = "$EXPECTED_JOB" ] || {
  echo "ABORT: coherent-state canary cell identity differs" >&2; exit 2; }

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format=json | "$ROOT/.venv/bin/python" -c '
import json, sys
value = json.load(sys.stdin)
completed = [
    row for row in value.get("status", {}).get("conditions", [])
    if row.get("type") == "Completed"
]
print(completed[0].get("status", "Unknown") if len(completed) == 1 else "Unknown")
')
  printf '%s COHERENT_MARKET_STATE_CANARY_STATUS execution=%s state=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$EXEC" "$STATE"
  [ "$STATE" != Unknown ] && break
  sleep 60
done

LISTED=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
  --region "$REGION" --format='value(metadata.name)')
[ "$LISTED" = "$EXEC" ] || {
  echo "ABORT: coherent-state canary job has an extra execution" >&2; exit 2; }
gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$OUT/canary-execution-metadata.pending.json"
OBJECT_PRESENT=false
if gcloud storage objects describe "$URI" --project "$PROJECT" --format=json \
    > "$OUT/canary-object-metadata.pending.json" 2>/dev/null; then
  OBJECT_PRESENT=true
else
  rm -f "$OUT/canary-object-metadata.pending.json"
fi

set +e
"$ROOT/.venv/bin/python" - "$MANIFEST" "$EXECUTIONS" \
  "$OUT/canary-execution-metadata.pending.json" \
  "$OUT/canary-object-metadata.pending.json" "$OBJECT_PRESENT" \
  "$EXPECTED_RUNNER" "$EXPECTED_TIMEOUT" "$EXECUTION_PROTOCOL_SHA" \
  "$ROOT/scripts/cloud_wait_coherent_market_state_canary.sh" \
  "$OUT/canary-completion.pending.txt" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

manifest_path, ledger_path, metadata_path, object_path = map(Path, sys.argv[1:5])
object_present = sys.argv[5] == "true"
runner, timeout, protocol_sha = sys.argv[6:9]
validator_path = Path(sys.argv[9])
completion_path = Path(sys.argv[10])
manifest = dict(
    line.split("=", 1)
    for line in manifest_path.read_text(encoding="utf-8").splitlines()
    if "=" in line
)
row = ledger_path.read_text(encoding="utf-8").split()
if len(row) != 5:
    raise SystemExit("ABORT: coherent-state canary ledger differs")
season, week, job, execution, uri = row
if season != "2023" or week != "1" or \
        manifest.get("execution_protocol_sha256") != protocol_sha or \
        manifest.get("canary_validator_sha256") != \
        sha256(validator_path.read_bytes()).hexdigest() or \
        not re.fullmatch(r"[0-9a-f]{40}", manifest.get("code_sha", "")) or \
        not re.fullmatch(r".+@sha256:[0-9a-f]{64}", manifest.get("image", "")):
    raise SystemExit("ABORT: coherent-state canary manifest differs")
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
if metadata.get("metadata", {}).get("name") != execution:
    raise SystemExit("ABORT: coherent-state canary execution identity differs")
spec = metadata.get("spec", {})
task = spec.get("template", {}).get("spec", {})
containers = task.get("containers", [])
if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or len(containers) != 1:
    raise SystemExit("ABORT: coherent-state canary task shape differs")
container = containers[0]
expected_args = [runner, "--season", season, "--week", week, "--output-uri", uri]
env = {
    value.get("name"): str(value.get("value", ""))
    for value in container.get("env", [])
}
if container.get("image") != manifest["image"] or \
        container.get("command") != ["python"] or \
        container.get("args") != expected_args or env != {
            "CODE_SHA": manifest["code_sha"],
            "ANALYSIS_IMAGE": manifest["image"],
        } or container.get("resources", {}).get("limits") != {
            "cpu": "4", "memory": "16Gi",
        } or task.get("maxRetries") != 0 or \
        str(task.get("timeoutSeconds")) != timeout or \
        task.get("serviceAccountName") != \
        "817589974517-compute@developer.gserviceaccount.com":
    raise SystemExit("ABORT: coherent-state canary execution contract differs")
status = metadata.get("status", {})
completed = [
    value for value in status.get("conditions", [])
    if value.get("type") == "Completed"
]
success = (
    len(completed) == 1
    and completed[0].get("status") == "True"
    and int(status.get("succeededCount") or 0) == 1
    and int(status.get("failedCount") or 0) == 0
    and bool(status.get("completionTime"))
    and object_present
)
object_sha = "absent"
if object_present:
    value = json.loads(object_path.read_text(encoding="utf-8"))
    if not str(value.get("generation", "")).isdigit() or int(value.get("size", 0)) <= 0:
        success = False
    object_sha = sha256(object_path.read_bytes()).hexdigest()
lines = [
    f"validated_at={status.get('completionTime', '')}",
    f"status={'True' if success else 'False'}",
    f"disposition={'real-path-canary-passes' if success else 'real-path-canary-fails'}",
    f"execution={execution}",
    "cell=2023-1",
    "remaining_cells_released=false",
    "object_content_inspected=false",
    "effect_fields_inspected=false",
    "uses_realized_outcomes=false",
    f"execution_metadata_sha256={sha256(metadata_path.read_bytes()).hexdigest()}",
    f"object_metadata_sha256={object_sha}",
]
completion_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
if not success:
    raise SystemExit("COHERENT_MARKET_STATE_REAL_PATH_CANARY_FAILED")
PY
RC=$?
set -e

mv "$OUT/canary-execution-metadata.pending.json" \
  "$OUT/canary-execution-metadata.json"
if [ -e "$OUT/canary-object-metadata.pending.json" ]; then
  mv "$OUT/canary-object-metadata.pending.json" \
    "$OUT/canary-object-metadata.json"
fi
mv "$OUT/canary-completion.pending.txt" "$OUT/canary-completion.txt"
sha256sum "$OUT/canary-execution-metadata.json" \
  "$OUT/canary-completion.txt" > "$OUT/canary.sha256"
if [ "$OBJECT_PRESENT" = true ]; then
  sha256sum "$OUT/canary-object-metadata.json" >> "$OUT/canary.sha256"
fi
[ "$RC" -eq 0 ] || exit "$RC"
echo "COHERENT_MARKET_STATE_REAL_PATH_CANARY_PASSED $EXEC"
