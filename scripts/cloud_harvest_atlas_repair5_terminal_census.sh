#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-matched-diversity-mvp-v1-repair5
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
RETRIES="$OUT/retry-executions.txt"
ACCEPTED="$OUT/accepted-executions.txt"
RESOLUTION="$OUT/attempt-resolution.json"
CLASSIFICATION="$OUT/primary-attempt-classification.json"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/$RUN_ID
PROTOCOL="$ROOT/reports/2026-08-16-atlas-repair5-terminal-census-protocol.md"
ATTEMPT_AMENDMENT="$ROOT/reports/2026-08-16-atlas-repair5-terminal-census-attempt-amendment.md"
RETRY_AMENDMENT="$ROOT/reports/2026-08-16-atlas-repair5-bounded-platform-retry-amendment.md"
REPAIR5_PROTOCOL="$ROOT/reports/2026-08-16-atlas-mvp-resource-only-repair5.md"
CANARY_AMENDMENT="$ROOT/reports/2026-08-16-atlas-repair5-real-path-canary-amendment.md"
CANARY_VALIDATOR="$ROOT/scripts/cloud_wait_atlas_repair5_canary.sh"
CANARY="$OUT/canary-completion.txt"
GRID_RELEASE="$OUT/grid-release.txt"
LAUNCHER="$ROOT/scripts/cloud_atlas_matched_diversity_repair5.sh"
ATTEMPT_RESOLVER="$ROOT/scripts/cloud_prepare_atlas_matched_diversity_repair5_attempts.sh"
FINISHER="$ROOT/scripts/cloud_finish_atlas_matched_diversity_repair5.sh"
RENDERER="$ROOT/scripts/render_atlas_matched_diversity_repair4_command.py"
PROTOCOL_SHA=94a792d80c4a908aed56034add9635478c738a29522554670c09360458561d0f
ATTEMPT_AMENDMENT_SHA=82e850d0c2c2ad525559c378e0116bc270b2d4e8428eb341506481f350a9e99b
RETRY_AMENDMENT_SHA=d464660b72e669d261d7f6d4800b3e59d55726b56e7003c5e3e806f38fa987a0
REPAIR5_PROTOCOL_SHA=5acc93c2b3a59931aa17dbc67d98fca81d3a6ac047011cfe1a9a81aa1ee8550e
CANARY_AMENDMENT_SHA=b2d0e32dabeb87bb1a67bee58c01f00c4c0d97e3fac9d1f7181bfcee50abc242
CANARY_VALIDATOR_SHA=e1c82612f231976563f0df12ffbe9f5e2db1aebfae636f61b723ad8699ae1411
LAUNCHER_SHA=3c8092c2bc3e40840a16867621f2f3ffe231f571d3f621818feab61dbefbe330
ATTEMPT_RESOLVER_SHA=705b65e5164b775361a2efe1440059f76978c3701c192179a40d85f4b0c27093
FINISHER_SHA=fe7a069e42bfece580ff4f312bc2990bd31339932713d834c2c123bbc431cdd9

for SPEC in "$PROTOCOL:$PROTOCOL_SHA" \
  "$ATTEMPT_AMENDMENT:$ATTEMPT_AMENDMENT_SHA" \
  "$RETRY_AMENDMENT:$RETRY_AMENDMENT_SHA" \
  "$REPAIR5_PROTOCOL:$REPAIR5_PROTOCOL_SHA" \
  "$CANARY_AMENDMENT:$CANARY_AMENDMENT_SHA" \
  "$CANARY_VALIDATOR:$CANARY_VALIDATOR_SHA" "$LAUNCHER:$LAUNCHER_SHA" \
  "$ATTEMPT_RESOLVER:$ATTEMPT_RESOLVER_SHA" "$FINISHER:$FINISHER_SHA"; do
  FILE=${SPEC%:*}
  DIGEST=${SPEC##*:}
  [ -s "$FILE" ] && [ "$(sha256sum "$FILE" | awk '{print $1}')" = "$DIGEST" ] || {
    echo "ABORT: ATLAS repair5 census frozen source differs: $FILE" >&2
    exit 2
  }
done
[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] && [ -e "$RETRIES" ] && \
  [ -s "$CANARY" ] && [ -s "$GRID_RELEASE" ] && \
  [ -s "$RESOLUTION" ] && [ -s "$CLASSIFICATION" ] || {
  echo "ABORT: ATLAS repair5 census launch receipt is incomplete" >&2
  exit 2
}
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ABORT: ATLAS repair5 census ledger is not 54 rows" >&2
  exit 2
}
[ ! -e "$OUT/terminal-census.json" ] && \
  [ ! -e "$OUT/terminal-census-execution-metadata" ] || {
  echo "ABORT: immutable ATLAS repair5 terminal census exists" >&2
  exit 3
}

PENDING="$OUT/terminal-census-execution-metadata.pending"
if [ -d "$PENDING" ]; then
  [ "$(find "$PENDING" -maxdepth 1 -name 'season-*-week-*.json' | wc -l)" = 54 ] || {
    echo "ABORT: ATLAS repair5 pending census metadata is incomplete" >&2
    exit 2
  }
else
  mkdir "$PENDING"
  while read -r SEASON WEEK JOB EXEC URI; do
    gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
      --region "$REGION" --format=json \
      > "$PENDING/season-${SEASON}-week-${WEEK}.json"
  done < "$EXECUTIONS"
fi

RETRY_PENDING="$OUT/terminal-census-retry-execution-metadata.pending"
if [ -d "$RETRY_PENDING" ]; then
  [ "$(find "$RETRY_PENDING" -maxdepth 1 -name 'season-*-week-*.json' | wc -l)" = \
    "$(wc -l < "$RETRIES")" ] || {
    echo "ABORT: ATLAS repair5 pending retry census metadata is incomplete" >&2
    exit 2
  }
else
  mkdir "$RETRY_PENDING"
  while read -r SEASON WEEK JOB PRIMARY_EXEC RETRY_EXEC URI; do
    gcloud run jobs executions describe "$RETRY_EXEC" --project "$PROJECT" \
      --region "$REGION" --format=json \
      > "$RETRY_PENDING/season-${SEASON}-week-${WEEK}.json"
  done < "$RETRIES"
fi

OBJECTS_PENDING="$OUT/terminal-census-object-inventory.pending.txt"
if [ ! -e "$OBJECTS_PENDING" ]; then
  gcloud storage ls "$PREFIX/**" --recursive --project "$PROJECT" \
    > "$OBJECTS_PENDING" 2>/dev/null || true
fi

GRID_COMMAND=$("$ROOT/.venv/bin/python" "$RENDERER" \
  --replacement-prefix "$PREFIX")
"$ROOT/.venv/bin/python" - "$MANIFEST" "$EXECUTIONS" "$PENDING" \
  "$RETRIES" "$RETRY_PENDING" "$ACCEPTED" "$RESOLUTION" "$CLASSIFICATION" \
  "$OBJECTS_PENDING" "$OUT/terminal-census.pending.json" \
  "$GRID_COMMAND" "$PROTOCOL_SHA" "$ATTEMPT_AMENDMENT_SHA" \
  "$RETRY_AMENDMENT_SHA" "$LAUNCHER_SHA" "$ATTEMPT_RESOLVER_SHA" \
  "$FINISHER_SHA" "$CANARY" "$GRID_RELEASE" "$CANARY_AMENDMENT_SHA" \
  "$CANARY_VALIDATOR_SHA" <<'PY'
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

manifest_path, ledger_path, metadata_dir, retry_path, retry_metadata_dir, \
    accepted_path, resolution_path, classification_path, inventory_path, \
    output_path = map(
    Path, sys.argv[1:11]
)
grid_command, protocol_sha, attempt_amendment_sha, retry_amendment_sha, \
    launcher_sha, attempt_resolver_sha, finisher_sha = sys.argv[11:18]
canary_path, grid_release_path = map(Path, sys.argv[18:20])
canary_amendment_sha, canary_validator_sha = sys.argv[20:22]
manifest = dict(
    line.rstrip("\n").split("=", 1)
    for line in manifest_path.read_text(encoding="utf-8").splitlines()
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
    "resource_repair5_protocol_sha256": (
        "5acc93c2b3a59931aa17dbc67d98fca81d3a6ac047011cfe1a9a81aa1ee8550e"
    ),
    "canary_amendment_sha256": canary_amendment_sha,
    "canary_validator_sha256": canary_validator_sha,
    "cpu": "8", "memory": "32Gi", "max_retries": "0",
    "timeout_seconds": "43200", "interaction_auxiliaries": "binary",
    "uses_realized_outcomes": "false",
    "production_change_licensed": "false",
}
if any(manifest.get(key) != value for key, value in fixed.items()):
    raise SystemExit("ABORT: ATLAS repair5 census manifest differs")
if manifest.get("grid_command_sha256") != sha256(grid_command.encode()).hexdigest():
    raise SystemExit("ABORT: ATLAS repair5 census command hash differs")
canary = dict(
    line.split("=", 1)
    for line in canary_path.read_text(encoding="utf-8").splitlines()
    if "=" in line
)
grid_release = dict(
    line.split("=", 1)
    for line in grid_release_path.read_text(encoding="utf-8").splitlines()
    if "=" in line
)
canary_sha = sha256(canary_path.read_bytes()).hexdigest()
grid_release_sha = sha256(grid_release_path.read_bytes()).hexdigest()
if canary.get("status") != "True" or \
        canary.get("disposition") != "real-path-canary-passes" or \
        canary.get("cell") != "2023-1" or \
        grid_release.get("primary_executions") != "54" or \
        grid_release.get("released_after_canary") != "53" or \
        grid_release.get("canary_completion_sha256") != canary_sha:
    raise SystemExit("ABORT: ATLAS repair5 census canary/grid release differs")

rows = [line.split() for line in ledger_path.read_text(encoding="utf-8").splitlines()]
retry_rows = [line.split() for line in retry_path.read_text(encoding="utf-8").splitlines()]
resolution = json.loads(resolution_path.read_text(encoding="utf-8"))
classification = json.loads(classification_path.read_text(encoding="utf-8"))
expected_cells = {
    (str(season), str(week))
    for season in (2023, 2024, 2025) for week in range(1, 19)
}
if len(rows) != 54 or {(row[0], row[1]) for row in rows} != expected_cells or \
        len({row[3] for row in rows}) != 54 or any(len(row) != 5 for row in rows):
    raise SystemExit("ABORT: ATLAS repair5 terminal census grid differs")
if any(len(row) != 6 for row in retry_rows) or \
        len({(row[0], row[1]) for row in retry_rows}) != len(retry_rows) or \
        len({row[4] for row in retry_rows}) != len(retry_rows):
    raise SystemExit("ABORT: ATLAS repair5 terminal retry grid differs")
if resolution.get("version") != "atlas-repair5-attempt-resolution-v1" or \
        resolution.get("uses_realized_outcomes") is not False or \
        resolution.get("effect_fields_inspected") is not False or \
        resolution.get("task_max_retries") != 0 or \
        resolution.get("max_replacement_executions_per_cell") != 1:
    raise SystemExit("ABORT: ATLAS repair5 census attempt resolution differs")
if classification.get("version") != \
        "atlas-repair5-primary-attempt-classification-v1" or \
        classification.get("uses_realized_outcomes") is not False or \
        classification.get("effect_fields_inspected") is not False:
    raise SystemExit("ABORT: ATLAS repair5 census classification differs")
if resolution.get("classification_sha256") != \
        sha256(classification_path.read_bytes()).hexdigest() or \
        resolution.get("primary_execution_ledger_sha256") != \
        sha256(ledger_path.read_bytes()).hexdigest() or \
        resolution.get("retry_execution_ledger_sha256") != \
        sha256(retry_path.read_bytes()).hexdigest() or \
        resolution.get("canary_completion_sha256") != canary_sha or \
        resolution.get("grid_release_sha256") != grid_release_sha or \
        classification.get("canary_completion_sha256") != canary_sha or \
        classification.get("grid_release_sha256") != grid_release_sha:
    raise SystemExit("ABORT: ATLAS repair5 census attempt hashes differ")

terminal = []
status_counts = Counter()
reason_counts = Counter()
for season_text, week_text, job, execution, uri in rows:
    season, week = int(season_text), int(week_text)
    if job != f"atlas-md-s{season}-w{week}-r5" or \
            not execution.startswith(job + "-") or \
            uri != f"{manifest['output_prefix']}/slate-{season}-{week}.json":
        raise SystemExit("ABORT: ATLAS repair5 census ledger identity differs")
    value = json.loads(
        (metadata_dir / f"season-{season}-week-{week}.json").read_text(
            encoding="utf-8"
        )
    )
    if value.get("metadata", {}).get("name") != execution:
        raise SystemExit("ABORT: ATLAS repair5 census execution name differs")
    status = value.get("status", {})
    completed = [
        row for row in status.get("conditions", []) if row.get("type") == "Completed"
    ]
    if len(completed) != 1 or completed[0].get("status") not in {"True", "False"} \
            or not status.get("completionTime"):
        raise SystemExit("ABORT: ATLAS repair5 census includes nonterminal cell")
    final_status = completed[0]["status"]
    if final_status == "True":
        if int(status.get("succeededCount") or 0) != 1 or \
                int(status.get("failedCount") or 0) != 0:
            raise SystemExit("ABORT: ATLAS repair5 census success count differs")
    elif int(status.get("succeededCount") or 0) != 0 or \
            int(status.get("failedCount") or 0) != 1 or \
            int(status.get("cancelledCount") or 0) != 0:
        raise SystemExit("ABORT: ATLAS repair5 census failure count differs")
    spec = value.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise SystemExit("ABORT: ATLAS repair5 census task shape differs")
    container = containers[0]
    expected_args = [
        "-c", grid_command, "--season", str(season), "--week", str(week),
        "--output-uri", uri,
    ]
    if container.get("image") != manifest["image"] or \
            container.get("command") != ["python"] or \
            container.get("args") != expected_args:
        raise SystemExit("ABORT: ATLAS repair5 census command/image differs")
    env = {
        row.get("name"): str(row.get("value", ""))
        for row in container.get("env", [])
    }
    if env != {
        "CODE_SHA": manifest["code_sha"],
        "ANALYSIS_IMAGE": manifest["image"],
    } or container.get("resources", {}).get("limits") != {
        "cpu": "8", "memory": "32Gi",
    }:
        raise SystemExit("ABORT: ATLAS repair5 census environment/resources differ")
    if task.get("maxRetries") != 0 or str(task.get("timeoutSeconds")) != "43200" \
            or task.get("serviceAccountName") != \
            "817589974517-compute@developer.gserviceaccount.com":
        raise SystemExit("ABORT: ATLAS repair5 census retry/timeout/account differs")
    reason = str(completed[0].get("reason", ""))
    message = str(completed[0].get("message", ""))
    status_counts[final_status] += 1
    if final_status == "False":
        if "configured memory limit was reached" in message:
            reason_key = "ConfiguredMemoryLimit"
        elif "Internal error running task" in message:
            reason_key = "InternalError"
        else:
            reason_key = reason or "unspecified"
        reason_counts[reason_key] += 1
    terminal.append({
        "season": season, "week": week, "job": job, "execution": execution,
        "status": final_status, "reason": reason, "message": message,
        "completion_time": status["completionTime"],
    })

if status_counts["False"] < 1:
    raise SystemExit("ABORT: ATLAS repair5 failure census has no failed cell")
primary_by_cell = {(row[0], row[1]): row for row in rows}
retry_terminal = []
retry_status_counts = Counter()
retry_reason_counts = Counter()
for season_text, week_text, job, primary_execution, retry_execution, uri in retry_rows:
    season, week = int(season_text), int(week_text)
    primary = primary_by_cell.get((season_text, week_text))
    if primary is None or primary[:4] != [season_text, week_text, job, primary_execution] \
            or primary[4] != uri or not retry_execution.startswith(job + "-") \
            or retry_execution == primary_execution:
        raise SystemExit("ABORT: ATLAS repair5 census retry binding differs")
    value = json.loads(
        (retry_metadata_dir / f"season-{season}-week-{week}.json").read_text(
            encoding="utf-8"
        )
    )
    if value.get("metadata", {}).get("name") != retry_execution:
        raise SystemExit("ABORT: ATLAS repair5 census retry identity differs")
    status = value.get("status", {})
    completed = [
        row for row in status.get("conditions", []) if row.get("type") == "Completed"
    ]
    if len(completed) != 1 or completed[0].get("status") not in {"True", "False"} \
            or not status.get("completionTime"):
        raise SystemExit("ABORT: ATLAS repair5 census includes nonterminal retry")
    final_status = completed[0]["status"]
    if final_status == "True":
        if int(status.get("succeededCount") or 0) != 1 or \
                int(status.get("failedCount") or 0) != 0:
            raise SystemExit("ABORT: ATLAS repair5 census retry success differs")
    elif int(status.get("succeededCount") or 0) != 0 or \
            int(status.get("failedCount") or 0) != 1 or \
            int(status.get("cancelledCount") or 0) != 0:
        raise SystemExit("ABORT: ATLAS repair5 census retry failure differs")
    spec = value.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise SystemExit("ABORT: ATLAS repair5 census retry task shape differs")
    container = containers[0]
    expected_args = [
        "-c", grid_command, "--season", str(season), "--week", str(week),
        "--output-uri", uri,
    ]
    env = {
        row.get("name"): str(row.get("value", ""))
        for row in container.get("env", [])
    }
    if container.get("image") != manifest["image"] or \
            container.get("command") != ["python"] or \
            container.get("args") != expected_args or \
            env != {"CODE_SHA": manifest["code_sha"],
                    "ANALYSIS_IMAGE": manifest["image"]} or \
            container.get("resources", {}).get("limits") != \
            {"cpu": "8", "memory": "32Gi"} or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != "43200" or \
            task.get("serviceAccountName") != \
            "817589974517-compute@developer.gserviceaccount.com":
        raise SystemExit("ABORT: ATLAS repair5 census retry contract differs")
    reason = str(completed[0].get("reason", ""))
    message = str(completed[0].get("message", ""))
    retry_status_counts[final_status] += 1
    if final_status == "False":
        retry_reason_counts[reason or "unspecified"] += 1
    retry_terminal.append({
        "season": season, "week": week, "job": job,
        "primary_execution": primary_execution, "retry_execution": retry_execution,
        "status": final_status, "reason": reason, "message": message,
        "completion_time": status["completionTime"],
    })

disposition = resolution.get("disposition")
if disposition == "terminal-invalid-primary":
    if classification.get("ineligible_failures", 0) < 1 or retry_rows or \
            resolution.get("accepted_executions") != 0:
        raise SystemExit("ABORT: ATLAS repair5 ineligible-primary release differs")
elif disposition == "accepted-population-with-platform-replacements":
    if classification.get("ineligible_failures") != 0 or \
            classification.get("eligible_replacements") != len(retry_rows) or \
            resolution.get("retry_executions") != len(retry_rows) or \
            resolution.get("accepted_executions") != 54 or \
            retry_status_counts["False"] < 1 or not accepted_path.is_file() or \
            resolution.get("accepted_execution_ledger_sha256") != \
            sha256(accepted_path.read_bytes()).hexdigest():
        raise SystemExit("ABORT: ATLAS repair5 failed-replacement release differs")
else:
    raise SystemExit("ABORT: ATLAS repair5 census release disposition differs")
inventory = [
    line.strip() for line in inventory_path.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
allowed = {row[4] for row in rows}
if any(uri not in allowed for uri in inventory) or len(inventory) != len(set(inventory)):
    raise SystemExit("ABORT: ATLAS repair5 object inventory differs")
payload = {
    "version": "atlas-matched-diversity-repair5-terminal-census-v1",
    "protocol_sha256": protocol_sha,
    "attempt_amendment_sha256": attempt_amendment_sha,
    "bounded_retry_amendment_sha256": retry_amendment_sha,
    "repair5_launcher_sha256": launcher_sha,
    "attempt_resolver_sha256": attempt_resolver_sha,
    "repair5_finisher_sha256": finisher_sha,
    "run_id": manifest["run_id"],
    "uses_realized_outcomes": False,
    "production_change_licensed": False,
    "scientific_result_valid": False,
    "manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
    "execution_ledger_sha256": sha256(ledger_path.read_bytes()).hexdigest(),
    "retry_execution_ledger_sha256": sha256(retry_path.read_bytes()).hexdigest(),
    "attempt_resolution_sha256": sha256(resolution_path.read_bytes()).hexdigest(),
    "attempt_classification_sha256": sha256(classification_path.read_bytes()).hexdigest(),
    "executions": 54,
    "retry_executions": len(retry_rows),
    "terminal_succeeded": status_counts["True"],
    "terminal_failed": status_counts["False"],
    "failure_reasons": dict(sorted(reason_counts.items())),
    "retry_terminal_succeeded": retry_status_counts["True"],
    "retry_terminal_failed": retry_status_counts["False"],
    "retry_failure_reasons": dict(sorted(retry_reason_counts.items())),
    "output_objects_present": len(inventory),
    "output_object_inventory_sha256": sha256(inventory_path.read_bytes()).hexdigest(),
    "effect_fields_inspected": False,
    "historical_scoring_licensed": False,
    "continuous_parity_capacity_released": True,
    "terminal": terminal,
    "retry_terminal": retry_terminal,
}
output_path.write_text(
    json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
PY

mv "$PENDING" "$OUT/terminal-census-execution-metadata"
mv "$RETRY_PENDING" "$OUT/terminal-census-retry-execution-metadata"
mv "$OBJECTS_PENDING" "$OUT/terminal-census-object-inventory.txt"
mv "$OUT/terminal-census.pending.json" "$OUT/terminal-census.json"
sha256sum "$OUT"/terminal-census-execution-metadata/*.json | sort \
  > "$OUT/terminal-census-execution-metadata.sha256"
if find "$OUT/terminal-census-retry-execution-metadata" -maxdepth 1 \
    -name '*.json' | grep -q .; then
  sha256sum "$OUT"/terminal-census-retry-execution-metadata/*.json | sort \
    > "$OUT/terminal-census-retry-execution-metadata.sha256"
else
  : > "$OUT/terminal-census-retry-execution-metadata.sha256"
fi
sha256sum "$OUT/terminal-census-object-inventory.txt" \
  > "$OUT/terminal-census-object-inventory.sha256"
sha256sum "$OUT/terminal-census.json" > "$OUT/terminal-census.sha256"
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'primary_executions=54' "retry_executions=$(wc -l < "$RETRIES")" \
  'all_declared_attempts_terminal=true' 'scientific_result_valid=false' \
  'effect_fields_inspected=false' 'uses_realized_outcomes=false' \
  'historical_scoring_licensed=false' \
  'continuous_parity_capacity_released=true' \
  'production_change_licensed=false' \
  > "$OUT/terminal-census-completion.txt"
sha256sum "$OUT/terminal-census-completion.txt" \
  > "$OUT/terminal-census-completion.sha256"
echo "ATLAS_REPAIR5_TERMINAL_CENSUS_HARVESTED $RUN_ID"
