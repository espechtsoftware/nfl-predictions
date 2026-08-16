#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-matched-diversity-mvp-v1-repair3
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/$RUN_ID
MANIFEST_SHA=08a6ad9e4f8581c101965e1928a3d69aee96fd244d265e80b6eaa4cc00c93b84
EXECUTIONS_SHA=4bc8f940253b98e3a6f03f28b127b16cf3677ab8254b775f9fca6c1253b36467
EXPECTED_ERROR='RuntimeError: ATLAS MVP shard season/week/output identity differs'

[ -s "$MANIFEST" ] && [ "$(sha256sum "$MANIFEST" | awk '{print $1}')" = "$MANIFEST_SHA" ] || {
  echo "ABORT: ATLAS repair3 failure manifest differs" >&2; exit 2; }
[ -s "$EXECUTIONS" ] && [ "$(sha256sum "$EXECUTIONS" | awk '{print $1}')" = "$EXECUTIONS_SHA" ] || {
  echo "ABORT: ATLAS repair3 failure execution ledger differs" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ABORT: ATLAS repair3 failure ledger is not 54 rows" >&2; exit 2; }
[ ! -e "$OUT/failure-summary.json" ] && [ ! -e "$OUT/failure-execution-metadata" ] || {
  echo "ABORT: immutable ATLAS repair3 failure harvest already exists" >&2; exit 3; }

PENDING="$OUT/failure-execution-metadata.pending"
mkdir "$PENDING"
while read -r SEASON WEEK JOB EXEC URI; do
  gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format=json > "$PENDING/season-${SEASON}-week-${WEEK}.json"
done < "$EXECUTIONS"

LOG_PENDING="$OUT/failure-stderr.pending.json"
gcloud logging read \
  'resource.type="cloud_run_job" AND logName="projects/nfl-predictions-503414/logs/run.googleapis.com%2Fstderr" AND labels."run.googleapis.com/execution_name"=~"atlas-md-s20(23|24|25)-w([1-9]|1[0-8])-r3-.*"' \
  --project "$PROJECT" --limit=200 --order=asc --format=json > "$LOG_PENDING"

if gcloud storage ls "$PREFIX/**" --recursive --project "$PROJECT" \
    2>/dev/null | head -1 | grep -q .; then
  echo "ABORT: ATLAS repair3 prefix unexpectedly contains an object" >&2
  exit 2
fi

"$ROOT/.venv/bin/python" - "$MANIFEST" "$EXECUTIONS" "$PENDING" \
  "$LOG_PENDING" "$OUT/failure-summary.pending.json" "$EXPECTED_ERROR" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys

manifest_path, ledger_path, metadata_dir, log_path, output_path = map(
    Path, sys.argv[1:6]
)
expected_error = sys.argv[6]
manifest = dict(
    line.rstrip("\n").split("=", 1)
    for line in manifest_path.read_text(encoding="utf-8").splitlines()
    if "=" in line
)
rows = [line.split() for line in ledger_path.read_text(encoding="utf-8").splitlines()]
expected_keys = {(int(row[0]), int(row[1])) for row in rows}
expected_executions = {row[3] for row in rows}
if len(rows) != 54 or len(expected_keys) != 54 or len(expected_executions) != 54:
    raise SystemExit("ABORT: ATLAS repair3 failure grid differs")

terminal = []
for season_text, week_text, job, execution, uri in rows:
    season, week = int(season_text), int(week_text)
    value = json.loads(
        (metadata_dir / f"season-{season}-week-{week}.json").read_text(
            encoding="utf-8"
        )
    )
    if value.get("metadata", {}).get("name") != execution:
        raise SystemExit("ABORT: ATLAS repair3 failure execution identity differs")
    status = value.get("status", {})
    completed = [
        row for row in status.get("conditions", []) if row.get("type") == "Completed"
    ]
    if (
        len(completed) != 1
        or completed[0].get("status") != "False"
        or completed[0].get("reason") != "NonZeroExitCode"
        or int(status.get("failedCount") or 0) != 1
        or int(status.get("succeededCount") or 0) != 0
        or not status.get("completionTime")
    ):
        raise SystemExit("ABORT: ATLAS repair3 failure status differs")
    spec = value.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or len(containers) != 1:
        raise SystemExit("ABORT: ATLAS repair3 failure task shape differs")
    container = containers[0]
    if (
        container.get("image") != manifest["image"]
        or container.get("command") != ["python"]
        or container.get("args") != [
            "scripts/run_atlas_matched_diversity_mvp.py",
            "--season", str(season), "--week", str(week),
            "--output-uri", uri,
        ]
    ):
        raise SystemExit("ABORT: ATLAS repair3 failure command differs")
    env = {
        row.get("name"): str(row.get("value", ""))
        for row in container.get("env", [])
    }
    if env != {
        "CODE_SHA": manifest["code_sha"],
        "ANALYSIS_IMAGE": manifest["image"],
    }:
        raise SystemExit("ABORT: ATLAS repair3 failure environment differs")
    if (
        container.get("resources", {}).get("limits") != {
            "cpu": "4", "memory": "16Gi"
        }
        or task.get("maxRetries") != 0
        or str(task.get("timeoutSeconds")) != "43200"
        or task.get("serviceAccountName")
        != "817589974517-compute@developer.gserviceaccount.com"
    ):
        raise SystemExit("ABORT: ATLAS repair3 failure resources differ")
    terminal.append({
        "season": season,
        "week": week,
        "job": job,
        "execution": execution,
        "completion_time": status["completionTime"],
        "reason": completed[0]["reason"],
    })

logs = json.loads(log_path.read_text(encoding="utf-8"))
stderr_by_execution = {}
for row in logs:
    execution = row.get("labels", {}).get("run.googleapis.com/execution_name")
    if execution in expected_executions and expected_error in row.get("textPayload", ""):
        stderr_by_execution.setdefault(execution, []).append(row["textPayload"])
if set(stderr_by_execution) != expected_executions or any(
    len(values) != 1 for values in stderr_by_execution.values()
):
    raise SystemExit("ABORT: ATLAS repair3 failure stderr census differs")

payload = {
    "version": "atlas-matched-diversity-repair3-prefix-failure-v1",
    "run_id": manifest["run_id"],
    "uses_realized_outcomes": False,
    "production_change_licensed": False,
    "manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
    "execution_ledger_sha256": sha256(ledger_path.read_bytes()).hexdigest(),
    "executions": 54,
    "terminal_failed": 54,
    "terminal_succeeded": 0,
    "output_objects": 0,
    "common_reason": "NonZeroExitCode",
    "common_error": expected_error,
    "failure_stage": "pre-query-output-identity-check",
    "scientific_calculation_started": False,
    "terminal": terminal,
}
output_path.write_text(
    json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
PY

mv "$PENDING" "$OUT/failure-execution-metadata"
mv "$LOG_PENDING" "$OUT/failure-stderr.json"
mv "$OUT/failure-summary.pending.json" "$OUT/failure-summary.json"
sha256sum "$OUT"/failure-execution-metadata/*.json | sort \
  > "$OUT/failure-execution-metadata.sha256"
sha256sum "$OUT/failure-stderr.json" > "$OUT/failure-stderr.sha256"
sha256sum "$OUT/failure-summary.json" > "$OUT/failure-summary.sha256"
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'executions=54' 'terminal_failed=54' 'terminal_succeeded=0' \
  'output_objects=0' 'failure_stage=pre-query-output-identity-check' \
  'scientific_calculation_started=false' 'uses_realized_outcomes=false' \
  'production_change_licensed=false' > "$OUT/failure-completion.txt"
sha256sum "$OUT/failure-completion.txt" > "$OUT/failure-completion.sha256"
echo "ATLAS_REPAIR3_PREFIX_FAILURE_HARVESTED $RUN_ID"
