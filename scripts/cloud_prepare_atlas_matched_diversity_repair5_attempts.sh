#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-matched-diversity-mvp-v1-repair5
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
PRIMARY="$OUT/executions.txt"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/$RUN_ID
AMENDMENT="$ROOT/reports/2026-08-16-atlas-repair5-bounded-platform-retry-amendment.md"
AMENDMENT_SHA=d464660b72e669d261d7f6d4800b3e59d55726b56e7003c5e3e806f38fa987a0
LAUNCHER="$ROOT/scripts/cloud_atlas_matched_diversity_repair5.sh"
LAUNCHER_SHA=9ea70f34e2591672e4b84621c116db8e4b465177bbda689d9d555c3d18d85b42
RENDERER="$ROOT/scripts/render_atlas_matched_diversity_repair4_command.py"

for SPEC in "$AMENDMENT:$AMENDMENT_SHA" "$LAUNCHER:$LAUNCHER_SHA"; do
  FILE=${SPEC%:*}
  DIGEST=${SPEC##*:}
  [ -s "$FILE" ] && [ "$(sha256sum "$FILE" | awk '{print $1}')" = "$DIGEST" ] || {
    echo "ABORT: ATLAS repair5 attempt dependency differs: $FILE" >&2; exit 2; }
done
[ -s "$MANIFEST" ] && [ -s "$PRIMARY" ] || {
  echo "ABORT: ATLAS repair5 primary launch receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$PRIMARY")" = 54 ] || {
  echo "ABORT: ATLAS repair5 primary grid is not 54" >&2; exit 2; }
if [ -s "$OUT/attempt-resolution.json" ]; then
  echo "ATLAS_REPAIR5_ATTEMPTS_ALREADY_RESOLVED $RUN_ID"
  exit 0
fi
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/completion.txt" ] || {
  echo "ABORT: ATLAS repair5 was harvested before attempt resolution" >&2; exit 3; }

GRID_COMMAND=$("$ROOT/.venv/bin/python" "$RENDERER" \
  --replacement-prefix "$PREFIX")

if [ ! -s "$OUT/primary-attempt-classification.json" ]; then
  TMP=$(mktemp -d "$OUT/.primary-attempts.XXXXXX")
  trap 'rm -rf -- "$TMP"' EXIT
  mkdir "$TMP/primary-execution-metadata"
  while read -r SEASON WEEK JOB EXEC URI; do
    gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
      --region "$REGION" --format=json \
      > "$TMP/primary-execution-metadata/season-${SEASON}-week-${WEEK}.json"
  done < "$PRIMARY"
  gcloud storage ls "$PREFIX/**" --recursive --project "$PROJECT" \
    > "$TMP/primary-object-inventory.txt" 2>/dev/null || true

  "$ROOT/.venv/bin/python" - "$MANIFEST" "$PRIMARY" \
    "$TMP/primary-execution-metadata" "$TMP/primary-object-inventory.txt" \
    "$TMP/primary-attempt-classification.json" "$TMP/retry-cells.txt" \
    "$GRID_COMMAND" "$AMENDMENT_SHA" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys

manifest_path, ledger_path, metadata_dir, inventory_path, output_path, retry_path = map(
    Path, sys.argv[1:7]
)
grid_command, amendment_sha = sys.argv[7:]
manifest = dict(
    line.split("=", 1) for line in manifest_path.read_text(encoding="utf-8").splitlines()
    if "=" in line
)
fixed = {
    "run_id": "20260816-atlas-matched-diversity-mvp-v1-repair5",
    "output_prefix": (
        "gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/"
        "20260816-atlas-matched-diversity-mvp-v1-repair5"
    ),
    "image": (
        "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@"
        "sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb"
    ),
    "code_sha": "60f296fdad769b30c0bb7334118698f156e462b9",
    "cpu": "8", "memory": "32Gi", "timeout_seconds": "43200",
    "max_retries": "0", "interaction_auxiliaries": "binary",
    "uses_realized_outcomes": "false", "production_change_licensed": "false",
}
if any(manifest.get(key) != value for key, value in fixed.items()):
    raise SystemExit("ABORT: ATLAS repair5 attempt manifest differs")
if manifest.get("grid_command_sha256") != sha256(grid_command.encode()).hexdigest():
    raise SystemExit("ABORT: ATLAS repair5 attempt command differs")

rows = [line.split() for line in ledger_path.read_text(encoding="utf-8").splitlines()]
expected = {(str(s), str(w)) for s in (2023, 2024, 2025) for w in range(1, 19)}
if len(rows) != 54 or {(r[0], r[1]) for r in rows} != expected or \
        len({r[3] for r in rows}) != 54 or any(len(r) != 5 for r in rows):
    raise SystemExit("ABORT: ATLAS repair5 primary attempt ledger differs")
inventory = {
    line.strip() for line in inventory_path.read_text(encoding="utf-8").splitlines()
    if line.strip()
}
allowed = {row[4] for row in rows}
if not inventory <= allowed:
    raise SystemExit("ABORT: ATLAS repair5 primary object inventory differs")

eligible = []
ineligible = []
cells = []
for season_text, week_text, job, execution, uri in rows:
    season, week = int(season_text), int(week_text)
    if job != f"atlas-md-s{season}-w{week}-r5" or \
            not execution.startswith(job + "-") or \
            uri != f"{manifest['output_prefix']}/slate-{season}-{week}.json":
        raise SystemExit("ABORT: ATLAS repair5 primary identity differs")
    value = json.loads(
        (metadata_dir / f"season-{season}-week-{week}.json").read_text(
            encoding="utf-8"
        )
    )
    if value.get("metadata", {}).get("name") != execution:
        raise SystemExit("ABORT: ATLAS repair5 primary metadata identity differs")
    status = value.get("status", {})
    completed = [r for r in status.get("conditions", []) if r.get("type") == "Completed"]
    if len(completed) != 1 or completed[0].get("status") not in {"True", "False"} \
            or not status.get("completionTime"):
        raise SystemExit("ATLAS_REPAIR5_PRIMARY_NOT_TERMINAL")
    spec = value.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise SystemExit("ABORT: ATLAS repair5 primary task shape differs")
    container = containers[0]
    expected_args = [
        "-c", grid_command, "--season", str(season), "--week", str(week),
        "--output-uri", uri,
    ]
    env = {r.get("name"): str(r.get("value", "")) for r in container.get("env", [])}
    if container.get("image") != manifest["image"] or \
            container.get("command") != ["python"] or \
            container.get("args") != expected_args or \
            env != {"CODE_SHA": manifest["code_sha"], "ANALYSIS_IMAGE": manifest["image"]}:
        raise SystemExit("ABORT: ATLAS repair5 primary command differs")
    if container.get("resources", {}).get("limits") != {"cpu": "8", "memory": "32Gi"} \
            or task.get("maxRetries") != 0 or str(task.get("timeoutSeconds")) != "43200" \
            or task.get("serviceAccountName") != \
            "817589974517-compute@developer.gserviceaccount.com":
        raise SystemExit("ABORT: ATLAS repair5 primary execution contract differs")

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
        blocked = (
            "internal error running task" not in message.lower()
            or any(token in message.lower() for token in (
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
        "season": season, "week": week, "job": job, "primary_execution": execution,
        "uri": uri, "status": final_status, "reason": reason, "message": message,
        "completion_time": status["completionTime"], "object_present": object_present,
        "eligibility": eligibility,
    })

if ineligible:
    disposition = "terminal-invalid-primary"
elif eligible:
    disposition = "replacement-required"
else:
    disposition = "all-primary-success"
payload = {
    "version": "atlas-repair5-primary-attempt-classification-v1",
    "run_id": manifest["run_id"],
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
    "cells": cells,
}
output_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
retry_path.write_text("".join(
    f"{s} {w} {job} {execution} {uri}\n"
    for s, w, job, execution, uri in eligible
))
PY

  mv "$TMP/primary-execution-metadata" "$OUT/primary-execution-metadata"
  mv "$TMP/primary-object-inventory.txt" "$OUT/primary-object-inventory.txt"
  mv "$TMP/primary-attempt-classification.json" "$OUT/primary-attempt-classification.json"
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

DISPOSITION=$("$ROOT/.venv/bin/python" - "$OUT/primary-attempt-classification.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["disposition"])
PY
)

if [ "$DISPOSITION" = terminal-invalid-primary ]; then
  : > "$OUT/retry-executions.txt"
  "$ROOT/.venv/bin/python" - "$OUT/primary-attempt-classification.json" \
    "$PRIMARY" "$OUT/retry-executions.txt" "$OUT/attempt-resolution.json" <<'PY'
from hashlib import sha256
import json, pathlib, sys
source, primary, retries, target = map(pathlib.Path, sys.argv[1:])
classification = json.loads(source.read_text(encoding="utf-8"))
payload = {
    "version": "atlas-repair5-attempt-resolution-v1",
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
target.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
PY
  sha256sum "$OUT/retry-executions.txt" "$OUT/attempt-resolution.json" \
    > "$OUT/attempt-resolution.sha256"
  echo "ATLAS_REPAIR5_PRIMARY_TERMINALLY_INVALID $RUN_ID"
  exit 10
fi

if [ "$DISPOSITION" = all-primary-success ]; then
  : > "$OUT/retry-executions.txt"
  cp "$PRIMARY" "$OUT/accepted-executions.txt"
else
  [ "$DISPOSITION" = replacement-required ] || {
    echo "ABORT: ATLAS repair5 primary disposition differs" >&2; exit 2; }
  PENDING="$OUT/retry-executions.pending.txt"
  touch "$PENDING"
  while read -r SEASON WEEK JOB PRIMARY_EXEC URI; do
    if awk -v s="$SEASON" -v w="$WEEK" '$1==s && $2==w {found=1} END {exit !found}' \
        "$PENDING"; then
      continue
    fi
    if gcloud storage ls "$URI" --project "$PROJECT" >/dev/null 2>&1; then
      echo "ABORT: ATLAS repair5 retry destination appeared: $URI" >&2; exit 2
    fi
    RETRY_EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
      --region "$REGION" --async --format='value(metadata.name)')
    [ -n "$RETRY_EXEC" ] && [ "$RETRY_EXEC" != "$PRIMARY_EXEC" ] && \
      [[ "$RETRY_EXEC" == "$JOB-"* ]] || {
      echo "ABORT: ATLAS repair5 retry identity missing" >&2; exit 2; }
    printf '%s %s %s %s %s %s\n' "$SEASON" "$WEEK" "$JOB" \
      "$PRIMARY_EXEC" "$RETRY_EXEC" "$URI" | tee -a "$PENDING"
  done < "$OUT/retry-cells.txt"
  [ "$(wc -l < "$PENDING")" = "$(wc -l < "$OUT/retry-cells.txt")" ] || {
    echo "ABORT: ATLAS repair5 retry population is incomplete" >&2; exit 2; }
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
    raise SystemExit("ABORT: ATLAS repair5 retry ledger differs")
accepted = []
for season, week, job, execution, uri in primary:
    retry = replacement.get((season, week))
    if retry:
        if retry[:4] != [season, week, job, execution] or retry[5] != uri:
            raise SystemExit("ABORT: ATLAS repair5 retry binding differs")
        execution = retry[4]
    accepted.append(" ".join((season, week, job, execution, uri)))
accepted_path.write_text("\n".join(accepted) + "\n")
PY
fi

"$ROOT/.venv/bin/python" - "$OUT/primary-attempt-classification.json" \
  "$PRIMARY" "$OUT/retry-executions.txt" "$OUT/accepted-executions.txt" \
  "$OUT/attempt-resolution.json" <<'PY'
from hashlib import sha256
import json, pathlib, sys
classification_path, primary_path, retry_path, accepted_path, target = map(
    pathlib.Path, sys.argv[1:]
)
classification = json.loads(classification_path.read_text(encoding="utf-8"))
retry_rows = [line for line in retry_path.read_text().splitlines() if line]
accepted_rows = [line for line in accepted_path.read_text().splitlines() if line]
if len(accepted_rows) != 54:
    raise SystemExit("ABORT: ATLAS repair5 accepted population is not 54")
payload = {
    "version": "atlas-repair5-attempt-resolution-v1",
    "run_id": classification["run_id"],
    "disposition": (
        "accepted-primary-population" if not retry_rows
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
target.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
PY
sha256sum "$OUT/executions.txt" "$OUT/retry-executions.txt" \
  "$OUT/accepted-executions.txt" "$OUT/attempt-resolution.json" \
  > "$OUT/attempt-resolution.sha256"
echo "ATLAS_REPAIR5_ATTEMPTS_RESOLVED $RUN_ID"
