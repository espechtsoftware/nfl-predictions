#!/usr/bin/env bash
set -euo pipefail

# Validate the first real repair5 grid execution before releasing 53 cells.

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-matched-diversity-mvp-v1-repair5
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
RENDERER="$ROOT/scripts/render_atlas_matched_diversity_repair4_command.py"
AMENDMENT_SHA=b2d0e32dabeb87bb1a67bee58c01f00c4c0d97e3fac9d1f7181bfcee50abc242

[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] || {
  echo "ABORT: ATLAS repair5 canary launch receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 1 ] || {
  echo "ABORT: ATLAS repair5 canary must precede the other 53 cells" >&2; exit 2; }
[ ! -e "$OUT/canary-completion.txt" ] && \
  [ ! -e "$OUT/canary-execution-metadata.json" ] && \
  [ ! -e "$OUT/canary-object-metadata.json" ] || {
  echo "ABORT: immutable ATLAS repair5 canary receipt already exists" >&2; exit 3; }

read -r SEASON WEEK JOB EXEC URI < "$EXECUTIONS"
[ "$SEASON" = 2023 ] && [ "$WEEK" = 1 ] && \
  [ "$JOB" = atlas-md-s2023-w1-r5 ] || {
  echo "ABORT: ATLAS repair5 canary cell identity differs" >&2; exit 2; }

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  printf '%s ATLAS_REPAIR5_CANARY_STATUS execution=%s state=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$EXEC" "$STATE"
  [ "$STATE" != Unknown ] && break
  sleep 60
done

LISTED=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
  --region "$REGION" --format='value(metadata.name)')
[ "$LISTED" = "$EXEC" ] || {
  echo "ABORT: ATLAS repair5 canary job has an extra execution" >&2; exit 2; }
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
GRID_COMMAND=$("$ROOT/.venv/bin/python" "$RENDERER" \
  --replacement-prefix "$(awk -F= '$1==\"output_prefix\" {print $2}' "$MANIFEST")")

set +e
"$ROOT/.venv/bin/python" - "$MANIFEST" "$EXECUTIONS" \
  "$OUT/canary-execution-metadata.pending.json" \
  "$OUT/canary-object-metadata.pending.json" "$OBJECT_PRESENT" \
  "$GRID_COMMAND" "$AMENDMENT_SHA" \
  "$ROOT/scripts/cloud_wait_atlas_repair5_canary.sh" \
  "$OUT/canary-completion.pending.txt" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys

manifest_path, ledger_path, metadata_path, object_path = map(Path, sys.argv[1:5])
object_present = sys.argv[5] == "true"
grid_command, amendment_sha = sys.argv[6:8]
validator_path, completion_path = map(Path, sys.argv[8:10])
manifest = dict(
    line.split("=", 1)
    for line in manifest_path.read_text(encoding="utf-8").splitlines()
    if "=" in line
)
row = ledger_path.read_text(encoding="utf-8").split()
if len(row) != 5:
    raise SystemExit("ABORT: ATLAS repair5 canary ledger differs")
season, week, job, execution, uri = row
expected = {
    "run_id": "20260816-atlas-matched-diversity-mvp-v1-repair5",
    "image": (
        "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@"
        "sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb"
    ),
    "code_sha": "60f296fdad769b30c0bb7334118698f156e462b9",
    "cpu": "8",
    "memory": "32Gi",
    "timeout_seconds": "43200",
    "max_retries": "0",
    "canary_amendment_sha256": amendment_sha,
    "canary_validator_sha256": sha256(validator_path.read_bytes()).hexdigest(),
}
if season != "2023" or week != "1" or job != "atlas-md-s2023-w1-r5" or \
        any(manifest.get(key) != value for key, value in expected.items()) or \
        manifest.get("grid_command_sha256") != sha256(grid_command.encode()).hexdigest():
    raise SystemExit("ABORT: ATLAS repair5 canary manifest differs")
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
if metadata.get("metadata", {}).get("name") != execution:
    raise SystemExit("ABORT: ATLAS repair5 canary execution identity differs")
spec = metadata.get("spec", {})
task = spec.get("template", {}).get("spec", {})
containers = task.get("containers", [])
if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
        len(containers) != 1:
    raise SystemExit("ABORT: ATLAS repair5 canary task shape differs")
container = containers[0]
expected_args = [
    "-c", grid_command, "--season", season, "--week", week,
    "--output-uri", uri,
]
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
            "cpu": "8", "memory": "32Gi",
        } or task.get("maxRetries") != 0 or \
        str(task.get("timeoutSeconds")) != "43200" or \
        task.get("serviceAccountName") != \
        "817589974517-compute@developer.gserviceaccount.com":
    raise SystemExit("ABORT: ATLAS repair5 canary execution contract differs")
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
    if not str(value.get("generation", "")).isdigit() or \
            int(value.get("size", 0)) <= 0:
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
    raise SystemExit("ATLAS_REPAIR5_REAL_PATH_CANARY_FAILED")
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
echo "ATLAS_REPAIR5_REAL_PATH_CANARY_PASSED $EXEC"
