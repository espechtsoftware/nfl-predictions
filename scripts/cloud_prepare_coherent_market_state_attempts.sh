#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-coherent-market-state-scorefree-v1
OUT="$ROOT/reports/coherent-market-state-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/coherent-market-state-runs/$RUN_ID
MANIFEST="$OUT/manifest.txt"
PRIMARY="$OUT/executions.txt"
CANARY="$OUT/canary-completion.txt"
GRID_RELEASE="$OUT/grid-release.txt"
PROTOCOL_SHA=0dd8175e88c9e01c29971663e0455f83b3d693c97b34f8bf8de2b2d054fafcbd

[ -s "$MANIFEST" ] && [ -s "$PRIMARY" ] && [ -s "$CANARY" ] && \
  [ -s "$GRID_RELEASE" ] || {
  echo "ABORT: coherent-state primary/canary launch receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$PRIMARY")" = 54 ] || {
  echo "ABORT: coherent-state primary grid is not 54" >&2; exit 2; }
if [ -s "$OUT/attempt-resolution.json" ]; then
  echo "COHERENT_MARKET_STATE_ATTEMPTS_ALREADY_RESOLVED $RUN_ID"
  exit 0
fi
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/completion.txt" ] || {
  echo "ABORT: coherent-state was harvested before attempt resolution" >&2; exit 3; }

TMP=$(mktemp -d "$OUT/.primary-attempts.XXXXXX")
trap 'rm -rf -- "$TMP"' EXIT
mkdir "$TMP/primary-execution-metadata"
while read -r SEASON WEEK _JOB EXEC _URI; do
  gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format=json \
    > "$TMP/primary-execution-metadata/season-${SEASON}-week-${WEEK}.json"
done < "$PRIMARY"
gcloud storage ls "$PREFIX/**" --recursive --project "$PROJECT" \
  > "$TMP/primary-object-inventory.txt" 2>/dev/null || true

"$ROOT/.venv/bin/python" - "$MANIFEST" "$PRIMARY" \
  "$TMP/primary-execution-metadata" "$TMP/primary-object-inventory.txt" \
  "$TMP/primary-attempt-classification.json" "$TMP/retry-cells.txt" \
  "$CANARY" "$GRID_RELEASE" "$PROTOCOL_SHA" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

manifest_path, ledger_path, metadata_dir, inventory_path, output_path, \
    retry_path, canary_path, grid_release_path = map(Path, sys.argv[1:9])
protocol_sha = sys.argv[9]
run_id = "20260816-coherent-market-state-scorefree-v1"
prefix = (
    "gs://nfl-predictions-503414-raw/research/coherent-market-state-runs/"
    + run_id
)
manifest = dict(
    line.split("=", 1)
    for line in manifest_path.read_text(encoding="utf-8").splitlines()
    if "=" in line
)
fixed = {
    "run_id": run_id,
    "output_prefix": prefix,
    "cpu": "4", "memory": "16Gi", "timeout_seconds": "14400",
    "max_retries": "0", "uses_realized_outcomes": "false",
    "production_change_licensed": "false",
    "historical_scoring_licensed": "false",
    "execution_protocol_sha256": protocol_sha,
}
if any(manifest.get(key) != value for key, value in fixed.items()) or \
        not re.fullmatch(r"[0-9a-f]{40}", manifest.get("code_sha", "")) or \
        not re.fullmatch(r".+@sha256:[0-9a-f]{64}", manifest.get("image", "")):
    raise SystemExit("ABORT: coherent-state attempt manifest differs")
rows = [line.split() for line in ledger_path.read_text().splitlines()]
expected = {(str(s), str(w)) for s in (2023, 2024, 2025) for w in range(1, 19)}
if len(rows) != 54 or any(len(row) != 5 for row in rows) or \
        {(row[0], row[1]) for row in rows} != expected or \
        len({row[3] for row in rows}) != 54:
    raise SystemExit("ABORT: coherent-state primary ledger differs")
inventory = {
    line.strip() for line in inventory_path.read_text().splitlines() if line.strip()
}
allowed = {row[4] for row in rows}
if not inventory <= allowed:
    raise SystemExit("ABORT: coherent-state object inventory differs")

eligible, ineligible, cells = [], [], []
for season_text, week_text, job, execution, uri in rows:
    season, week = int(season_text), int(week_text)
    expected_job = f"coherent-state-s{season}-w{week}-v1"
    expected_uri = f"{prefix}/slate-{season}-{week}.json"
    if job != expected_job or not execution.startswith(job + "-") or uri != expected_uri:
        raise SystemExit("ABORT: coherent-state primary identity differs")
    metadata = json.loads(
        (metadata_dir / f"season-{season}-week-{week}.json").read_text()
    )
    if metadata.get("metadata", {}).get("name") != execution:
        raise SystemExit("ABORT: coherent-state primary metadata differs")
    spec = metadata.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise SystemExit("ABORT: coherent-state primary task shape differs")
    container = containers[0]
    env = {row.get("name"): str(row.get("value", "")) for row in container.get("env", [])}
    if container.get("image") != manifest["image"] or \
            container.get("command") != ["python"] or container.get("args") != [
                "scripts/run_coherent_market_state_scorefree.py",
                "--season", str(season), "--week", str(week),
                "--output-uri", uri,
            ] or env != {
                "CODE_SHA": manifest["code_sha"],
                "ANALYSIS_IMAGE": manifest["image"],
            } or container.get("resources", {}).get("limits") != {
                "cpu": "4", "memory": "16Gi",
            } or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != "14400" or \
            task.get("serviceAccountName") != \
            "817589974517-compute@developer.gserviceaccount.com":
        raise SystemExit("ABORT: coherent-state primary contract differs")
    status = metadata.get("status", {})
    completed = [row for row in status.get("conditions", []) if row.get("type") == "Completed"]
    if len(completed) != 1 or completed[0].get("status") not in {"True", "False"} or \
            not status.get("completionTime"):
        raise SystemExit("COHERENT_MARKET_STATE_PRIMARY_NOT_TERMINAL")
    condition = completed[0]
    final_status = condition["status"]
    message = str(condition.get("message", ""))
    reason = str(condition.get("reason", ""))
    object_present = uri in inventory
    eligibility = "primary-success"
    if final_status == "True":
        if int(status.get("succeededCount") or 0) != 1 or \
                int(status.get("failedCount") or 0) != 0 or not object_present:
            eligibility = "ineligible-success-contract-or-object"
            ineligible.append((season, week))
    else:
        lower = message.lower()
        retryable = (
            (season, week) != (2023, 1)
            and "internal error running task" in lower
            and not any(token in lower for token in (
                "configured memory limit", "timeout", "signal", "sigkill",
                "solver", "cbc", "nonzero exit",
            ))
            and int(status.get("succeededCount") or 0) == 0
            and int(status.get("failedCount") or 0) == 1
            and int(status.get("cancelledCount") or 0) == 0
            and not object_present
        )
        if retryable:
            eligibility = "eligible-platform-replacement"
            eligible.append((season, week, job, execution, uri))
        else:
            eligibility = "ineligible-primary-failure"
            ineligible.append((season, week))
    cells.append({
        "season": season, "week": week, "job": job,
        "primary_execution": execution, "uri": uri, "status": final_status,
        "reason": reason, "message": message,
        "completion_time": status["completionTime"],
        "object_present": object_present, "eligibility": eligibility,
    })
disposition = (
    "terminal-invalid-primary" if ineligible else
    "replacement-required" if eligible else "all-primary-success"
)
payload = {
    "version": "coherent-market-state-primary-attempt-classification-v1",
    "run_id": run_id, "execution_protocol_sha256": protocol_sha,
    "uses_realized_outcomes": False, "effect_fields_inspected": False,
    "task_max_retries": 0, "max_replacement_executions_per_cell": 1,
    "primary_executions": 54, "eligible_replacements": len(eligible),
    "ineligible_failures": len(ineligible), "disposition": disposition,
    "primary_execution_ledger_sha256": sha256(ledger_path.read_bytes()).hexdigest(),
    "primary_object_inventory_sha256": sha256(inventory_path.read_bytes()).hexdigest(),
    "canary_completion_sha256": sha256(canary_path.read_bytes()).hexdigest(),
    "grid_release_sha256": sha256(grid_release_path.read_bytes()).hexdigest(),
    "cells": cells,
}
output_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
retry_path.write_text("".join(
    f"{season} {week} {job} {execution} {uri}\n"
    for season, week, job, execution, uri in eligible
))
PY

mv "$TMP/primary-execution-metadata" "$OUT/primary-execution-metadata"
mv "$TMP/primary-object-inventory.txt" "$OUT/primary-object-inventory.txt"
mv "$TMP/primary-attempt-classification.json" \
  "$OUT/primary-attempt-classification.json"
mv "$TMP/retry-cells.txt" "$OUT/retry-cells.txt"
sha256sum "$OUT"/primary-execution-metadata/*.json | sort \
  > "$OUT/primary-execution-metadata.sha256"
sha256sum "$OUT/primary-object-inventory.txt" \
  > "$OUT/primary-object-inventory.sha256"
trap - EXIT
rm -rf -- "$TMP"

DISPOSITION=$("$ROOT/.venv/bin/python" -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["disposition"])' \
  "$OUT/primary-attempt-classification.json")
: > "$OUT/retry-executions.txt"
if [ "$DISPOSITION" = terminal-invalid-primary ]; then
  : > "$OUT/accepted-executions.txt"
elif [ "$DISPOSITION" = all-primary-success ]; then
  cp "$PRIMARY" "$OUT/accepted-executions.txt"
elif [ "$DISPOSITION" = replacement-required ]; then
  while read -r SEASON WEEK JOB PRIMARY_EXEC URI; do
    LISTED=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
      --region "$REGION" --format='value(metadata.name)')
    [ "$LISTED" = "$PRIMARY_EXEC" ] || {
      echo "ABORT: unreceipted coherent-state attempt exists: $JOB" >&2; exit 2; }
    if gcloud storage ls "$URI" --project "$PROJECT" >/dev/null 2>&1; then
      echo "ABORT: coherent-state replacement destination appeared" >&2; exit 2
    fi
    RETRY_EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
      --region "$REGION" --async --format='value(metadata.name)')
    [[ "$RETRY_EXEC" == "$JOB-"* ]] && [ "$RETRY_EXEC" != "$PRIMARY_EXEC" ] || {
      echo "ABORT: coherent-state replacement identity missing" >&2; exit 2; }
    printf '%s %s %s %s %s %s\n' "$SEASON" "$WEEK" "$JOB" \
      "$PRIMARY_EXEC" "$RETRY_EXEC" "$URI" >> "$OUT/retry-executions.txt"
  done < "$OUT/retry-cells.txt"
  "$ROOT/.venv/bin/python" - "$PRIMARY" "$OUT/retry-executions.txt" \
    "$OUT/accepted-executions.txt" <<'PY'
from pathlib import Path
import sys
primary, retries, target = map(Path, sys.argv[1:])
replacement = {(row[0], row[1]): row for row in (
    line.split() for line in retries.read_text().splitlines()
)}
accepted = []
for season, week, job, execution, uri in (
    line.split() for line in primary.read_text().splitlines()
):
    retry = replacement.get((season, week))
    if retry:
        execution = retry[4]
    accepted.append(" ".join((season, week, job, execution, uri)))
target.write_text("\n".join(accepted) + "\n")
PY
else
  echo "ABORT: coherent-state primary disposition differs" >&2; exit 2
fi

"$ROOT/.venv/bin/python" - "$OUT/primary-attempt-classification.json" \
  "$PRIMARY" "$OUT/retry-executions.txt" "$OUT/accepted-executions.txt" \
  "$OUT/attempt-resolution.json" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys
classification_path, primary, retries, accepted, target = map(Path, sys.argv[1:])
classification = json.loads(classification_path.read_text())
retry_rows = [row for row in retries.read_text().splitlines() if row]
accepted_rows = [row for row in accepted.read_text().splitlines() if row]
terminal = classification["disposition"] == "terminal-invalid-primary"
payload = {
    "version": "coherent-market-state-attempt-resolution-v1",
    "run_id": classification["run_id"],
    "disposition": (
        "terminal-invalid-primary" if terminal else
        "accepted-primary-population" if not retry_rows else
        "accepted-population-with-platform-replacements"
    ),
    "uses_realized_outcomes": False, "effect_fields_inspected": False,
    "task_max_retries": 0, "max_replacement_executions_per_cell": 1,
    "primary_executions": 54, "retry_executions": len(retry_rows),
    "accepted_executions": len(accepted_rows),
    "classification_sha256": sha256(classification_path.read_bytes()).hexdigest(),
    "primary_execution_ledger_sha256": sha256(primary.read_bytes()).hexdigest(),
    "retry_execution_ledger_sha256": sha256(retries.read_bytes()).hexdigest(),
    "accepted_execution_ledger_sha256": sha256(accepted.read_bytes()).hexdigest(),
}
target.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
PY
sha256sum "$OUT/primary-attempt-classification.json" \
  "$OUT/retry-executions.txt" "$OUT/accepted-executions.txt" \
  "$OUT/attempt-resolution.json" > "$OUT/attempt-resolution.sha256"
[ "$DISPOSITION" != terminal-invalid-primary ] || exit 10
"$ROOT/.venv/bin/python" "$ROOT/scripts/validate_coherent_market_state_attempts.py" \
  --output-dir "$OUT" --manifest "$MANIFEST"
