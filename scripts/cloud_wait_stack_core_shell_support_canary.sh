#!/usr/bin/env bash
set -euo pipefail

# Validate the first actual support-grid cell before releasing the other 53.

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-stack-core-shell-control-support-census-v1
OUT="$ROOT/reports/stack-core-shell-support-runs/$RUN_ID"
EXPECTED_JOB=stack-shell-support-s2023-w1-v1
EXPECTED_RUNNER=scripts/run_stack_core_shell_support_census.py
EXPECTED_TIMEOUT=7200
EXECUTION_PROTOCOL_SHA=d2e902611e070ef67c191dffd35d86fd0c81365126eb86dcae7b9640aede1cc3
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"

[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] || {
  echo "ABORT: stack-core/shell canary launch receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 1 ] || {
  echo "ABORT: stack-core/shell canary must precede the other 53 cells" >&2; exit 2; }
[ ! -e "$OUT/canary-completion.txt" ] && \
  [ ! -e "$OUT/canary-execution-metadata.json" ] && \
  [ ! -e "$OUT/canary-object-metadata.json" ] || {
  echo "ABORT: immutable stack-core/shell canary receipt already exists" >&2; exit 3; }

read -r SEASON WEEK JOB EXEC URI < "$EXECUTIONS"
[ "$SEASON" = 2023 ] && [ "$WEEK" = 1 ] && \
  [ "$JOB" = "$EXPECTED_JOB" ] || {
  echo "ABORT: stack-core/shell canary identity differs" >&2; exit 2; }

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  printf '%s STACK_CORE_SHELL_CANARY_STATUS execution=%s state=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$EXEC" "$STATE"
  [ "$STATE" != Unknown ] && break
  sleep 60
done

LISTED=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
  --region "$REGION" --format='value(metadata.name)')
[ "$LISTED" = "$EXEC" ] || {
  echo "ABORT: stack-core/shell canary job has an extra execution" >&2; exit 2; }
gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json \
  > "$OUT/canary-execution-metadata.pending.json"
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
  "$ROOT/scripts/cloud_wait_stack_core_shell_support_canary.sh" \
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
    raise SystemExit("ABORT: stack-core/shell canary ledger differs")
season, week, job, execution, uri = row
if season != "2023" or week != "1" or \
        manifest.get("execution_protocol_sha256") != protocol_sha or \
        manifest.get("canary_validator_sha256") != \
        sha256(validator_path.read_bytes()).hexdigest() or \
        not re.fullmatch(r"[0-9a-f]{40}", manifest.get("code_sha", "")) or \
        not re.fullmatch(r".+@sha256:[0-9a-f]{64}", manifest.get("image", "")):
    raise SystemExit("ABORT: stack-core/shell canary manifest differs")
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
if metadata.get("metadata", {}).get("name") != execution:
    raise SystemExit("ABORT: stack-core/shell canary execution identity differs")
spec = metadata.get("spec", {})
task = spec.get("template", {}).get("spec", {})
containers = task.get("containers", [])
if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
        len(containers) != 1:
    raise SystemExit("ABORT: stack-core/shell canary task shape differs")
container = containers[0]
expected_args = [runner, "--season", season, "--week", week, "--output-uri", uri]
env = {
    value.get("name"): str(value.get("value", ""))
    for value in container.get("env", [])
}
if container.get("image") != manifest["image"] or \
        container.get("command") != ["python"] or \
        container.get("args") != expected_args or \
        env != {
            "CODE_SHA": manifest["code_sha"],
            "ANALYSIS_IMAGE": manifest["image"],
        } or container.get("resources", {}).get("limits") != {
            "cpu": "4", "memory": "16Gi"} or task.get("maxRetries") != 0 or \
        str(task.get("timeoutSeconds")) != timeout or \
        task.get("serviceAccountName") != \
        "817589974517-compute@developer.gserviceaccount.com":
    raise SystemExit("ABORT: stack-core/shell canary execution contract differs")
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
    "treatment_constructed=false",
    "uses_realized_outcomes=false",
    f"execution_metadata_sha256={sha256(metadata_path.read_bytes()).hexdigest()}",
    f"object_metadata_sha256={object_sha}",
]
completion_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
if not success:
    raise SystemExit("STACK_CORE_SHELL_REAL_PATH_CANARY_FAILED")
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
echo "STACK_CORE_SHELL_REAL_PATH_CANARY_PASSED $EXEC"
