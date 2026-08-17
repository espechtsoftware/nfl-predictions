#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260817-production-law-dependence-source-lock-v1
OUT="$ROOT/reports/production-law-dependence-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"
RUNNER="$ROOT/scripts/run_production_law_dependence_source_lock.py"
FINISHER="$ROOT/scripts/cloud_finish_production_law_dependence_source_lock.sh"

[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] || {
  echo "ABORT: production-law dependence source-lock launch is incomplete" >&2; exit 2; }
[ ! -e "$OUT/source-lock.json" ] && [ ! -e "$OUT/execution.json" ] || {
  echo "ABORT: immutable production-law dependence source-lock harvest exists" >&2; exit 3; }
read -r JOB EXEC URI < "$EXECUTION"
TMP=$(mktemp -d "$OUT/.harvest.XXXXXX")
trap 'rm -rf -- "$TMP"' EXIT
gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$TMP/execution.json"
gcloud storage objects describe "$URI" --project "$PROJECT" --format=json \
  > "$TMP/object-metadata.json"
gcloud storage cp "$URI" "$TMP/source-lock.json" --project "$PROJECT" >/dev/null

PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" - \
  "$TMP/execution.json" "$TMP/object-metadata.json" "$TMP/source-lock.json" \
  "$MANIFEST" "$JOB" "$EXEC" "$URI" "$RUNNER" "$FINISHER" <<'PY'
from hashlib import sha256
import json, re, sys
from pathlib import Path
from run_production_law_dependence_remeasurement import _validate_source_lock

execution_path, object_path, lock_path, manifest_path = map(Path, sys.argv[1:5])
job, execution, uri = sys.argv[5:8]
runner, finisher = map(Path, sys.argv[8:10])
m = dict(line.split("=", 1) for line in manifest_path.read_text().splitlines() if "=" in line)
fixed = {
    "run_id": "20260817-production-law-dependence-source-lock-v1",
    "uses_realized_outcomes": "false", "actual_outcomes_queried": "false",
    "candidate_or_lineup_scores_read": "false",
    "production_change_licensed": "false", "artifacts": "270",
    "slates": "54", "cpu": "2", "memory": "4Gi",
    "timeout_seconds": "3600", "max_retries": "0",
}
if any(m.get(k) != v for k, v in fixed.items()) or \
        m.get("runner_sha256") != sha256(runner.read_bytes()).hexdigest() or \
        m.get("finisher_sha256") != sha256(finisher.read_bytes()).hexdigest():
    raise SystemExit("ABORT: production-law dependence source-lock manifest differs")
x = json.loads(execution_path.read_text())
s = x.get("status", {})
completed = [row for row in s.get("conditions", []) if row.get("type") == "Completed"]
if x.get("metadata", {}).get("name") != execution or len(completed) != 1 or \
        completed[0].get("status") != "True" or int(s.get("succeededCount") or 0) != 1 or \
        int(s.get("failedCount") or 0) != 0 or not s.get("completionTime"):
    raise SystemExit("ABORT: production-law dependence source-lock execution failed")
spec = x.get("spec", {})
task = spec.get("template", {}).get("spec", {})
containers = task.get("containers", [])
if len(containers) != 1 or spec.get("parallelism") != 1 or spec.get("taskCount") != 1:
    raise SystemExit("ABORT: production-law dependence source-lock task differs")
c = containers[0]
env = {row.get("name"): str(row.get("value", "")) for row in c.get("env", [])}
if job != "production-law-dep-source-lock-v1" or c.get("image") != m["image"] or \
        c.get("command") != ["python"] or c.get("args") != [
            "scripts/run_production_law_dependence_source_lock.py", "--output-uri", uri,
        ] or env != {"CODE_SHA": m["code_sha"], "ANALYSIS_IMAGE": m["image"]} or \
        c.get("resources", {}).get("limits") != {"cpu": "2", "memory": "4Gi"} or \
        task.get("maxRetries") != 0 or str(task.get("timeoutSeconds")) != "3600":
    raise SystemExit("ABORT: production-law dependence source-lock contract differs")
raw = lock_path.read_bytes()
o = json.loads(object_path.read_text())
digest = sha256(raw).hexdigest()
if int(o.get("size", -1)) != len(raw) or not str(o.get("generation", "")).isdigit():
    raise SystemExit("ABORT: production-law dependence source-lock object differs")
lock = json.loads(raw)
artifacts, catalog = _validate_source_lock(
    lock, generation=str(o["generation"]), digest=digest,
)
if len(artifacts) != 270 or len(catalog) != lock["catalog_rows"]:
    raise SystemExit("ABORT: production-law dependence source-lock population differs")
print("PRODUCTION_LAW_DEPENDENCE_SOURCE_LOCK_VALIDATED", len(catalog), lock["eligible_rows"])
PY

mv "$TMP/execution.json" "$OUT/execution.json"
mv "$TMP/object-metadata.json" "$OUT/object-metadata.json"
mv "$TMP/source-lock.json" "$OUT/source-lock.json"
trap - EXIT
rmdir "$TMP"
sha256sum "$OUT/execution.json" > "$OUT/execution-metadata.sha256"
sha256sum "$OUT/object-metadata.json" > "$OUT/object-metadata.sha256"
sha256sum "$OUT/source-lock.json" > "$OUT/source-lock.sha256"
GENERATION=$($ROOT/.venv/bin/python -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["generation"])' \
  "$OUT/object-metadata.json")
SHA=$(sha256sum "$OUT/source-lock.json" | awk '{print $1}')
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'uses_realized_outcomes=false' 'actual_outcomes_queried=false' \
  'artifacts=270' 'slates=54' "generation=$GENERATION" "sha256=$SHA" \
  'disposition=valid-production-law-source-lock' > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "PRODUCTION_LAW_DEPENDENCE_SOURCE_LOCK_HARVESTED $RUN_ID"
