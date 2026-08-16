#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-matched-diversity-mvp-v1-repair5
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/$RUN_ID
PROTOCOL="$ROOT/reports/2026-08-16-atlas-repair5-terminal-census-protocol.md"
REPAIR5_PROTOCOL="$ROOT/reports/2026-08-16-atlas-mvp-resource-only-repair5.md"
LAUNCHER="$ROOT/scripts/cloud_atlas_matched_diversity_repair5.sh"
FINISHER="$ROOT/scripts/cloud_finish_atlas_matched_diversity_repair5.sh"
RENDERER="$ROOT/scripts/render_atlas_matched_diversity_repair4_command.py"
PROTOCOL_SHA=94a792d80c4a908aed56034add9635478c738a29522554670c09360458561d0f
REPAIR5_PROTOCOL_SHA=5acc93c2b3a59931aa17dbc67d98fca81d3a6ac047011cfe1a9a81aa1ee8550e
LAUNCHER_SHA=9ea70f34e2591672e4b84621c116db8e4b465177bbda689d9d555c3d18d85b42
FINISHER_SHA=39fe8218edbfabe8a0e021407f8cca5da0fa9113c93e858556761164ca434933

for SPEC in "$PROTOCOL:$PROTOCOL_SHA" \
  "$REPAIR5_PROTOCOL:$REPAIR5_PROTOCOL_SHA" "$LAUNCHER:$LAUNCHER_SHA" \
  "$FINISHER:$FINISHER_SHA"; do
  FILE=${SPEC%:*}
  DIGEST=${SPEC##*:}
  [ -s "$FILE" ] && [ "$(sha256sum "$FILE" | awk '{print $1}')" = "$DIGEST" ] || {
    echo "ABORT: ATLAS repair5 census frozen source differs: $FILE" >&2
    exit 2
  }
done
[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] || {
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

OBJECTS_PENDING="$OUT/terminal-census-object-inventory.pending.txt"
if [ ! -e "$OBJECTS_PENDING" ]; then
  gcloud storage ls "$PREFIX/**" --recursive --project "$PROJECT" \
    > "$OBJECTS_PENDING" 2>/dev/null || true
fi

GRID_COMMAND=$("$ROOT/.venv/bin/python" "$RENDERER" \
  --replacement-prefix "$PREFIX")
"$ROOT/.venv/bin/python" - "$MANIFEST" "$EXECUTIONS" "$PENDING" \
  "$OBJECTS_PENDING" "$OUT/terminal-census.pending.json" \
  "$GRID_COMMAND" "$PROTOCOL_SHA" "$LAUNCHER_SHA" "$FINISHER_SHA" <<'PY'
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

manifest_path, ledger_path, metadata_dir, inventory_path, output_path = map(
    Path, sys.argv[1:6]
)
grid_command, protocol_sha, launcher_sha, finisher_sha = sys.argv[6:]
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
    "cpu": "8", "memory": "32Gi", "max_retries": "0",
    "timeout_seconds": "43200", "interaction_auxiliaries": "binary",
    "uses_realized_outcomes": "false",
    "production_change_licensed": "false",
}
if any(manifest.get(key) != value for key, value in fixed.items()):
    raise SystemExit("ABORT: ATLAS repair5 census manifest differs")
if manifest.get("grid_command_sha256") != sha256(grid_command.encode()).hexdigest():
    raise SystemExit("ABORT: ATLAS repair5 census command hash differs")

rows = [line.split() for line in ledger_path.read_text(encoding="utf-8").splitlines()]
expected_cells = {
    (str(season), str(week))
    for season in (2023, 2024, 2025) for week in range(1, 19)
}
if len(rows) != 54 or {(row[0], row[1]) for row in rows} != expected_cells or \
        len({row[3] for row in rows}) != 54 or any(len(row) != 5 for row in rows):
    raise SystemExit("ABORT: ATLAS repair5 terminal census grid differs")

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
    "repair5_launcher_sha256": launcher_sha,
    "repair5_finisher_sha256": finisher_sha,
    "run_id": manifest["run_id"],
    "uses_realized_outcomes": False,
    "production_change_licensed": False,
    "scientific_result_valid": False,
    "manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
    "execution_ledger_sha256": sha256(ledger_path.read_bytes()).hexdigest(),
    "executions": 54,
    "terminal_succeeded": status_counts["True"],
    "terminal_failed": status_counts["False"],
    "failure_reasons": dict(sorted(reason_counts.items())),
    "output_objects_present": len(inventory),
    "output_object_inventory_sha256": sha256(inventory_path.read_bytes()).hexdigest(),
    "effect_fields_inspected": False,
    "historical_scoring_licensed": False,
    "continuous_parity_capacity_released": True,
    "terminal": terminal,
}
output_path.write_text(
    json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
PY

mv "$PENDING" "$OUT/terminal-census-execution-metadata"
mv "$OBJECTS_PENDING" "$OUT/terminal-census-object-inventory.txt"
mv "$OUT/terminal-census.pending.json" "$OUT/terminal-census.json"
sha256sum "$OUT"/terminal-census-execution-metadata/*.json | sort \
  > "$OUT/terminal-census-execution-metadata.sha256"
sha256sum "$OUT/terminal-census-object-inventory.txt" \
  > "$OUT/terminal-census-object-inventory.sha256"
sha256sum "$OUT/terminal-census.json" > "$OUT/terminal-census.sha256"
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'executions=54' 'all_terminal=true' 'scientific_result_valid=false' \
  'effect_fields_inspected=false' 'uses_realized_outcomes=false' \
  'historical_scoring_licensed=false' \
  'continuous_parity_capacity_released=true' \
  'production_change_licensed=false' \
  > "$OUT/terminal-census-completion.txt"
sha256sum "$OUT/terminal-census-completion.txt" \
  > "$OUT/terminal-census-completion.sha256"
echo "ATLAS_REPAIR5_TERMINAL_CENSUS_HARVESTED $RUN_ID"
