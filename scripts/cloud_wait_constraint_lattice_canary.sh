#!/usr/bin/env bash
set -euo pipefail

# Validate the first real 2023-W1 grid execution before releasing 53 cells.
# Usage: cloud_wait_constraint_lattice_canary.sh support|scorefree

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
MODE=${1:-}
CANARY_AMENDMENT_SHA=2599f722b6ba7703ff78fec31cb3c0b78d0c771178e8ea40fb4fb6563d44aa00
case "$MODE" in
  support)
    RUN_ID=20260816-constraint-lattice-control-support-census-v1
    OUT="$ROOT/reports/constraint-lattice-support-runs/$RUN_ID"
    EXPECTED_JOB=constraint-support-s2023-w1-v1
    EXPECTED_RUNNER=scripts/run_constraint_lattice_support_census.py
    EXPECTED_TIMEOUT=7200
    ;;
  scorefree)
    RUN_ID=20260816-constraint-lattice-scorefree-v1
    OUT="$ROOT/reports/constraint-lattice-runs/$RUN_ID"
    EXPECTED_JOB=constraint-lattice-s2023-w1-v1
    EXPECTED_RUNNER=scripts/run_constraint_lattice_scorefree.py
    EXPECTED_TIMEOUT=43200
    ;;
  *)
    echo "Usage: $0 support|scorefree" >&2
    exit 2
    ;;
esac
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] || {
  echo "ABORT: lattice canary launch receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 1 ] || {
  echo "ABORT: lattice canary must precede the other 53 cells" >&2; exit 2; }
[ ! -e "$OUT/canary-completion.txt" ] && \
  [ ! -e "$OUT/canary-execution-metadata.json" ] && \
  [ ! -e "$OUT/canary-object-metadata.json" ] || {
  echo "ABORT: immutable lattice canary receipt already exists" >&2; exit 3; }

read -r SEASON WEEK JOB EXEC URI < "$EXECUTIONS"
[ "$SEASON" = 2023 ] && [ "$WEEK" = 1 ] && [ "$JOB" = "$EXPECTED_JOB" ] || {
  echo "ABORT: lattice canary cell identity differs" >&2; exit 2; }

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  printf '%s CONSTRAINT_LATTICE_CANARY_STATUS mode=%s execution=%s state=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$MODE" "$EXEC" "$STATE"
  [ "$STATE" != Unknown ] && break
  sleep 60
done

LISTED=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
  --region "$REGION" --format='value(metadata.name)')
[ "$LISTED" = "$EXEC" ] || {
  echo "ABORT: lattice canary job has an extra execution" >&2; exit 2; }
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
"$ROOT/.venv/bin/python" - "$MODE" "$MANIFEST" "$EXECUTIONS" \
  "$OUT/canary-execution-metadata.pending.json" \
  "$OUT/canary-object-metadata.pending.json" "$OBJECT_PRESENT" \
  "$EXPECTED_RUNNER" "$EXPECTED_TIMEOUT" "$CANARY_AMENDMENT_SHA" \
  "$ROOT/scripts/cloud_wait_constraint_lattice_canary.sh" \
  "$OUT/canary-completion.pending.txt" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

mode = sys.argv[1]
manifest_path, ledger_path, metadata_path, object_path = map(Path, sys.argv[2:6])
object_present = sys.argv[6] == "true"
runner, timeout, amendment_sha = sys.argv[7:10]
validator_path = Path(sys.argv[10])
completion_path = Path(sys.argv[11])
manifest = dict(
    line.split("=", 1)
    for line in manifest_path.read_text(encoding="utf-8").splitlines()
    if "=" in line
)
row = ledger_path.read_text(encoding="utf-8").split()
if len(row) != 5:
    raise SystemExit("ABORT: lattice canary ledger differs")
season, week, job, execution, uri = row
if season != "2023" or week != "1" or \
        manifest.get("canary_amendment_sha256") != amendment_sha or \
        manifest.get("canary_validator_sha256") != \
        sha256(validator_path.read_bytes()).hexdigest() or \
        not re.fullmatch(r"[0-9a-f]{40}", manifest.get("code_sha", "")) or \
        not re.fullmatch(r".+@sha256:[0-9a-f]{64}", manifest.get("image", "")):
    raise SystemExit("ABORT: lattice canary manifest differs")
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
if metadata.get("metadata", {}).get("name") != execution:
    raise SystemExit("ABORT: lattice canary execution identity differs")
spec = metadata.get("spec", {})
task = spec.get("template", {}).get("spec", {})
containers = task.get("containers", [])
if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
        len(containers) != 1:
    raise SystemExit("ABORT: lattice canary task shape differs")
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
    raise SystemExit("ABORT: lattice canary execution contract differs")
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
    f"mode={mode}",
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
    raise SystemExit("CONSTRAINT_LATTICE_REAL_PATH_CANARY_FAILED")
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
echo "CONSTRAINT_LATTICE_REAL_PATH_CANARY_PASSED $MODE $EXEC"
