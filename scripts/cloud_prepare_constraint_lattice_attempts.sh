#!/usr/bin/env bash
set -euo pipefail

# Resolve the bounded external-attempt law for a complete terminal lattice grid.
# Usage: cloud_prepare_constraint_lattice_attempts.sh support|scorefree

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
MODE=${1:-}
AMENDMENT="$ROOT/reports/2026-08-16-constraint-lattice-bounded-platform-retry-amendment.md"
AMENDMENT_SHA=f846d4540d27c1480037b440aabf94c91a1a5121e6d9968ad5ef39f679ce63aa

case "$MODE" in
  support)
    RUN_ID=20260816-constraint-lattice-control-support-census-v1
    OUT="$ROOT/reports/constraint-lattice-support-runs/$RUN_ID"
    PREFIX="gs://nfl-predictions-503414-raw/research/constraint-lattice-support-runs/$RUN_ID"
    ;;
  scorefree)
    RUN_ID=20260816-constraint-lattice-scorefree-v1
    OUT="$ROOT/reports/constraint-lattice-runs/$RUN_ID"
    PREFIX="gs://nfl-predictions-503414-raw/research/constraint-lattice-runs/$RUN_ID"
    ;;
  *)
    echo "Usage: $0 support|scorefree" >&2
    exit 2
    ;;
esac

MANIFEST="$OUT/manifest.txt"
PRIMARY="$OUT/executions.txt"
CANARY="$OUT/canary-completion.txt"
GRID_RELEASE="$OUT/grid-release.txt"
[ -s "$AMENDMENT" ] && \
  [ "$(sha256sum "$AMENDMENT" | awk '{print $1}')" = "$AMENDMENT_SHA" ] || {
  echo "ABORT: constraint-lattice attempt amendment differs" >&2; exit 2; }
[ -s "$MANIFEST" ] && [ -s "$PRIMARY" ] || {
  echo "ABORT: constraint-lattice primary launch receipt is incomplete" >&2; exit 2; }
[ -s "$CANARY" ] && [ -s "$GRID_RELEASE" ] || {
  echo "ABORT: constraint-lattice canary/grid release is incomplete" >&2; exit 2; }
[ "$(wc -l < "$PRIMARY")" = 54 ] || {
  echo "ABORT: constraint-lattice primary grid is not 54" >&2; exit 2; }
if [ -s "$OUT/attempt-resolution.json" ]; then
  echo "CONSTRAINT_LATTICE_ATTEMPTS_ALREADY_RESOLVED $MODE $RUN_ID"
  exit 0
fi
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/completion.txt" ] || {
  echo "ABORT: constraint-lattice was harvested before attempt resolution" >&2; exit 3; }

if [ ! -s "$OUT/primary-attempt-classification.json" ]; then
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

  "$ROOT/.venv/bin/python" - "$MODE" "$MANIFEST" "$PRIMARY" \
    "$TMP/primary-execution-metadata" "$TMP/primary-object-inventory.txt" \
    "$TMP/primary-attempt-classification.json" "$TMP/retry-cells.txt" \
    "$CANARY" "$GRID_RELEASE" "$AMENDMENT_SHA" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

mode = sys.argv[1]
manifest_path, ledger_path, metadata_dir, inventory_path, output_path, retry_path, \
    canary_path, grid_release_path = map(
    Path, sys.argv[2:10]
)
amendment_sha = sys.argv[10]
manifest = dict(
    line.split("=", 1)
    for line in manifest_path.read_text(encoding="utf-8").splitlines()
    if "=" in line
)
contracts = {
    "support": {
        "run_id": "20260816-constraint-lattice-control-support-census-v1",
        "prefix": (
            "gs://nfl-predictions-503414-raw/research/"
            "constraint-lattice-support-runs/"
            "20260816-constraint-lattice-control-support-census-v1"
        ),
        "job": "constraint-support-s{season}-w{week}-v1",
        "runner": "scripts/run_constraint_lattice_support_census.py",
        "timeout": "7200",
    },
    "scorefree": {
        "run_id": "20260816-constraint-lattice-scorefree-v1",
        "prefix": (
            "gs://nfl-predictions-503414-raw/research/constraint-lattice-runs/"
            "20260816-constraint-lattice-scorefree-v1"
        ),
        "job": "constraint-lattice-s{season}-w{week}-v1",
        "runner": "scripts/run_constraint_lattice_scorefree.py",
        "timeout": "43200",
    },
}
contract = contracts[mode]
fixed = {
    "run_id": contract["run_id"],
    "output_prefix": contract["prefix"],
    "cpu": "4",
    "memory": "16Gi",
    "timeout_seconds": contract["timeout"],
    "max_retries": "0",
    "uses_realized_outcomes": "false",
    "production_change_licensed": "false",
    "historical_scoring_licensed": "false",
    "attempt_amendment_sha256": amendment_sha,
}
if any(manifest.get(key) != value for key, value in fixed.items()):
    raise SystemExit("ABORT: constraint-lattice attempt manifest differs")
if not re.fullmatch(r"[0-9a-f]{40}", manifest.get("code_sha", "")) or not re.fullmatch(
    r".+@sha256:[0-9a-f]{64}", manifest.get("image", "")
):
    raise SystemExit("ABORT: constraint-lattice attempt code/image differs")

rows = [line.split() for line in ledger_path.read_text(encoding="utf-8").splitlines()]
expected = {(str(s), str(w)) for s in (2023, 2024, 2025) for w in range(1, 19)}
if len(rows) != 54 or any(len(row) != 5 for row in rows) or \
        {(row[0], row[1]) for row in rows} != expected or \
        len({row[3] for row in rows}) != 54:
    raise SystemExit("ABORT: constraint-lattice primary ledger differs")
inventory = {
    line.strip()
    for line in inventory_path.read_text(encoding="utf-8").splitlines()
    if line.strip()
}
allowed = {row[4] for row in rows}
if not inventory <= allowed:
    raise SystemExit("ABORT: constraint-lattice object inventory differs")

eligible = []
ineligible = []
cells = []
for season_text, week_text, job, execution, uri in rows:
    season, week = int(season_text), int(week_text)
    expected_job = contract["job"].format(season=season, week=week)
    expected_uri = f"{contract['prefix']}/slate-{season}-{week}.json"
    if job != expected_job or not execution.startswith(job + "-") or uri != expected_uri:
        raise SystemExit("ABORT: constraint-lattice primary identity differs")
    metadata = json.loads(
        (metadata_dir / f"season-{season}-week-{week}.json").read_text(
            encoding="utf-8"
        )
    )
    if metadata.get("metadata", {}).get("name") != execution:
        raise SystemExit("ABORT: constraint-lattice primary metadata differs")
    status = metadata.get("status", {})
    completed = [
        row for row in status.get("conditions", []) if row.get("type") == "Completed"
    ]
    if len(completed) != 1 or completed[0].get("status") not in {"True", "False"} \
            or not status.get("completionTime"):
        raise SystemExit("CONSTRAINT_LATTICE_PRIMARY_NOT_TERMINAL")
    spec = metadata.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise SystemExit("ABORT: constraint-lattice primary task shape differs")
    container = containers[0]
    expected_args = [
        contract["runner"], "--season", str(season), "--week", str(week),
        "--output-uri", uri,
    ]
    env = {
        row.get("name"): str(row.get("value", ""))
        for row in container.get("env", [])
    }
    if container.get("image") != manifest["image"] or \
            container.get("command") != ["python"] or \
            container.get("args") != expected_args or \
            env != {
                "CODE_SHA": manifest["code_sha"],
                "ANALYSIS_IMAGE": manifest["image"],
            }:
        raise SystemExit("ABORT: constraint-lattice primary command differs")
    if container.get("resources", {}).get("limits") != {
            "cpu": "4", "memory": "16Gi"} or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != contract["timeout"] or \
            task.get("serviceAccountName") != \
            "817589974517-compute@developer.gserviceaccount.com":
        raise SystemExit("ABORT: constraint-lattice execution contract differs")

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
        blocked = (
            "internal error running task" not in lower
            or any(token in lower for token in (
                "configured memory limit", "timeout", "signal", "sigkill",
                "solver", "cbc", "nonzero exit",
            ))
            or int(status.get("succeededCount") or 0) != 0
            or int(status.get("failedCount") or 0) != 1
            or int(status.get("cancelledCount") or 0) != 0
            or object_present
        )
        if blocked:
            eligibility = "ineligible-primary-failure"
            ineligible.append((season, week))
        else:
            eligibility = "eligible-platform-replacement"
            eligible.append((season, week, job, execution, uri))
    cells.append({
        "season": season,
        "week": week,
        "job": job,
        "primary_execution": execution,
        "uri": uri,
        "status": final_status,
        "reason": reason,
        "message": message,
        "completion_time": status["completionTime"],
        "object_present": object_present,
        "eligibility": eligibility,
    })

if ineligible:
    disposition = "terminal-invalid-primary"
elif eligible:
    disposition = "replacement-required"
else:
    disposition = "all-primary-success"
payload = {
    "version": "constraint-lattice-primary-attempt-classification-v1",
    "mode": mode,
    "run_id": contract["run_id"],
    "bounded_retry_amendment_sha256": amendment_sha,
    "uses_realized_outcomes": False,
    "effect_fields_inspected": False,
    "task_max_retries": 0,
    "max_replacement_executions_per_cell": 1,
    "primary_executions": 54,
    "eligible_replacements": len(eligible),
    "ineligible_failures": len(ineligible),
    "disposition": disposition,
    "primary_execution_ledger_sha256": sha256(ledger_path.read_bytes()).hexdigest(),
    "primary_object_inventory_sha256": sha256(inventory_path.read_bytes()).hexdigest(),
    "canary_completion_sha256": sha256(canary_path.read_bytes()).hexdigest(),
    "grid_release_sha256": sha256(grid_release_path.read_bytes()).hexdigest(),
    "cells": cells,
}
output_path.write_text(
    json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
retry_path.write_text(
    "".join(
        f"{season} {week} {job} {execution} {uri}\n"
        for season, week, job, execution, uri in eligible
    ),
    encoding="utf-8",
)
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
  sha256sum "$OUT/primary-attempt-classification.json" \
    > "$OUT/primary-attempt-classification.sha256"
  trap - EXIT
  rm -rf -- "$TMP"
fi

DISPOSITION=$("$ROOT/.venv/bin/python" - \
  "$OUT/primary-attempt-classification.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["disposition"])
PY
)

if [ "$DISPOSITION" = terminal-invalid-primary ]; then
  : > "$OUT/retry-executions.txt"
  "$ROOT/.venv/bin/python" - "$MODE" \
    "$OUT/primary-attempt-classification.json" "$PRIMARY" \
    "$OUT/retry-executions.txt" "$OUT/attempt-resolution.json" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys

mode = sys.argv[1]
source, primary, retries, target = map(Path, sys.argv[2:])
classification = json.loads(source.read_text(encoding="utf-8"))
payload = {
    "version": "constraint-lattice-attempt-resolution-v1",
    "mode": mode,
    "run_id": classification["run_id"],
    "disposition": "terminal-invalid-primary",
    "uses_realized_outcomes": False,
    "effect_fields_inspected": False,
    "task_max_retries": 0,
    "max_replacement_executions_per_cell": 1,
    "primary_executions": 54,
    "retry_executions": 0,
    "accepted_executions": 0,
    "classification_sha256": sha256(source.read_bytes()).hexdigest(),
    "primary_execution_ledger_sha256": sha256(primary.read_bytes()).hexdigest(),
    "retry_execution_ledger_sha256": sha256(retries.read_bytes()).hexdigest(),
}
target.write_text(
    json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
PY
  sha256sum "$OUT/retry-executions.txt" "$OUT/attempt-resolution.json" \
    > "$OUT/attempt-resolution.sha256"
  echo "CONSTRAINT_LATTICE_PRIMARY_TERMINALLY_INVALID $MODE $RUN_ID"
  exit 10
fi

if [ "$DISPOSITION" = all-primary-success ]; then
  : > "$OUT/retry-executions.txt"
  cp "$PRIMARY" "$OUT/accepted-executions.txt"
else
  [ "$DISPOSITION" = replacement-required ] || {
    echo "ABORT: constraint-lattice primary disposition differs" >&2; exit 2; }
  PENDING="$OUT/retry-executions.pending.txt"
  touch "$PENDING"
  while read -r SEASON WEEK JOB PRIMARY_EXEC URI; do
    if awk -v s="$SEASON" -v w="$WEEK" \
        '$1==s && $2==w {found=1} END {exit !found}' "$PENDING"; then
      continue
    fi
    LISTED=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
      --region "$REGION" --format='value(metadata.name)')
    [ "$LISTED" = "$PRIMARY_EXEC" ] || {
      echo "ABORT: unreceipted lattice attempt exists: $JOB" >&2; exit 2; }
    if gcloud storage ls "$URI" --project "$PROJECT" >/dev/null 2>&1; then
      echo "ABORT: lattice retry destination appeared: $URI" >&2; exit 2
    fi
    RETRY_EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
      --region "$REGION" --async --format='value(metadata.name)')
    [ -n "$RETRY_EXEC" ] && [ "$RETRY_EXEC" != "$PRIMARY_EXEC" ] && \
      [[ "$RETRY_EXEC" == "$JOB-"* ]] || {
      echo "ABORT: constraint-lattice retry identity missing" >&2; exit 2; }
    printf '%s %s %s %s %s %s\n' "$SEASON" "$WEEK" "$JOB" \
      "$PRIMARY_EXEC" "$RETRY_EXEC" "$URI" | tee -a "$PENDING"
  done < "$OUT/retry-cells.txt"
  [ "$(wc -l < "$PENDING")" = "$(wc -l < "$OUT/retry-cells.txt")" ] || {
    echo "ABORT: constraint-lattice retry population is incomplete" >&2; exit 2; }
  mv "$PENDING" "$OUT/retry-executions.txt"
  "$ROOT/.venv/bin/python" - "$PRIMARY" "$OUT/retry-executions.txt" \
    "$OUT/accepted-executions.txt" <<'PY'
from pathlib import Path
import sys

primary_path, retry_path, accepted_path = map(Path, sys.argv[1:])
primary = [line.split() for line in primary_path.read_text().splitlines()]
retries = [line.split() for line in retry_path.read_text().splitlines()]
replacement = {(row[0], row[1]): row for row in retries}
if len(replacement) != len(retries) or any(len(row) != 6 for row in retries):
    raise SystemExit("ABORT: constraint-lattice retry ledger differs")
accepted = []
for season, week, job, execution, uri in primary:
    retry = replacement.get((season, week))
    if retry:
        if retry[:4] != [season, week, job, execution] or retry[5] != uri:
            raise SystemExit("ABORT: constraint-lattice retry binding differs")
        execution = retry[4]
    accepted.append(" ".join((season, week, job, execution, uri)))
accepted_path.write_text("\n".join(accepted) + "\n", encoding="utf-8")
PY
fi

"$ROOT/.venv/bin/python" - "$MODE" \
  "$OUT/primary-attempt-classification.json" "$PRIMARY" \
  "$OUT/retry-executions.txt" "$OUT/accepted-executions.txt" \
  "$OUT/attempt-resolution.json" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys

mode = sys.argv[1]
classification_path, primary_path, retry_path, accepted_path, target = map(
    Path, sys.argv[2:]
)
classification = json.loads(classification_path.read_text(encoding="utf-8"))
retry_rows = [line for line in retry_path.read_text().splitlines() if line]
accepted_rows = [line for line in accepted_path.read_text().splitlines() if line]
if len(accepted_rows) != 54:
    raise SystemExit("ABORT: constraint-lattice accepted population is not 54")
payload = {
    "version": "constraint-lattice-attempt-resolution-v1",
    "mode": mode,
    "run_id": classification["run_id"],
    "disposition": (
        "accepted-primary-population"
        if not retry_rows
        else "accepted-population-with-platform-replacements"
    ),
    "uses_realized_outcomes": False,
    "effect_fields_inspected": False,
    "task_max_retries": 0,
    "max_replacement_executions_per_cell": 1,
    "primary_executions": 54,
    "retry_executions": len(retry_rows),
    "accepted_executions": 54,
    "classification_sha256": sha256(classification_path.read_bytes()).hexdigest(),
    "primary_execution_ledger_sha256": sha256(primary_path.read_bytes()).hexdigest(),
    "retry_execution_ledger_sha256": sha256(retry_path.read_bytes()).hexdigest(),
    "accepted_execution_ledger_sha256": sha256(accepted_path.read_bytes()).hexdigest(),
}
target.write_text(
    json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
PY
sha256sum "$PRIMARY" "$OUT/retry-executions.txt" \
  "$OUT/accepted-executions.txt" "$OUT/attempt-resolution.json" \
  > "$OUT/attempt-resolution.sha256"
echo "CONSTRAINT_LATTICE_ATTEMPTS_RESOLVED $MODE $RUN_ID"
