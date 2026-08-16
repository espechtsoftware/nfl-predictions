#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-matched-diversity-mvp-v1-repair4
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/$RUN_ID
MANIFEST_SHA=083a5e158053cd03f509bfebe518516af695773c029a78a8e80aa6aa336e5df6
EXECUTIONS_SHA=0ca2e0635a8cb572912aeb19156a388c9a87ba8bc0f340998a6b39eb2b28c3fd
RENDERER="$ROOT/scripts/render_atlas_matched_diversity_repair4_command.py"

[ -s "$MANIFEST" ] && [ "$(sha256sum "$MANIFEST" | awk '{print $1}')" = "$MANIFEST_SHA" ] || {
  echo "ABORT: ATLAS repair4 census manifest differs" >&2; exit 2; }
[ -s "$EXECUTIONS" ] && [ "$(sha256sum "$EXECUTIONS" | awk '{print $1}')" = "$EXECUTIONS_SHA" ] || {
  echo "ABORT: ATLAS repair4 census execution ledger differs" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ABORT: ATLAS repair4 census ledger is not 54 rows" >&2; exit 2; }
[ ! -e "$OUT/terminal-census.json" ] && \
  [ ! -e "$OUT/terminal-census-execution-metadata" ] || {
  echo "ABORT: immutable ATLAS repair4 terminal census exists" >&2; exit 3; }

PENDING="$OUT/terminal-census-execution-metadata.pending"
if [ -d "$PENDING" ]; then
  [ "$(find "$PENDING" -maxdepth 1 -name 'season-*-week-*.json' | wc -l)" = 54 ] || {
    echo "ABORT: ATLAS repair4 pending census metadata is incomplete" >&2
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
  "$GRID_COMMAND" <<'PY'
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

manifest_path, ledger_path, metadata_dir, inventory_path, output_path = map(
    Path, sys.argv[1:6]
)
grid_command = sys.argv[6]
manifest = dict(
    line.rstrip("\n").split("=", 1)
    for line in manifest_path.read_text(encoding="utf-8").splitlines()
    if "=" in line
)
rows = [line.split() for line in ledger_path.read_text(encoding="utf-8").splitlines()]
if len(rows) != 54 or len({(r[0], r[1]) for r in rows}) != 54 or \
        len({r[3] for r in rows}) != 54:
    raise SystemExit("ABORT: ATLAS repair4 terminal census grid differs")

terminal = []
status_counts = Counter()
reason_counts = Counter()
for season_text, week_text, job, execution, uri in rows:
    season, week = int(season_text), int(week_text)
    value = json.loads(
        (metadata_dir / f"season-{season}-week-{week}.json").read_text(
            encoding="utf-8"
        )
    )
    if value.get("metadata", {}).get("name") != execution:
        raise SystemExit("ABORT: ATLAS repair4 census execution name differs")
    status = value.get("status", {})
    completed = [
        row for row in status.get("conditions", []) if row.get("type") == "Completed"
    ]
    if len(completed) != 1 or completed[0].get("status") not in {"True", "False"} \
            or not status.get("completionTime"):
        raise SystemExit("ABORT: ATLAS repair4 census includes nonterminal cell")
    final_status = completed[0]["status"]
    if final_status == "True":
        if int(status.get("succeededCount") or 0) != 1 or \
                int(status.get("failedCount") or 0) != 0:
            raise SystemExit("ABORT: ATLAS repair4 census success count differs")
    else:
        failed_count = int(status.get("failedCount") or 0)
        succeeded_count = int(status.get("succeededCount") or 0)
        cancelled_count = int(status.get("cancelledCount") or 0)
        reason_text = str(completed[0].get("reason", ""))
        message_text = str(completed[0].get("message", ""))
        cancelled = cancelled_count == 1 or \
            "cancel" in f"{reason_text} {message_text}".lower()
        if succeeded_count != 0 or not (
            (failed_count == 1 and cancelled_count == 0)
            or (failed_count == 0 and cancelled_count == 1 and cancelled)
            or (failed_count == 0 and cancelled_count == 0 and cancelled)
        ):
            raise SystemExit("ABORT: ATLAS repair4 census failure count differs")
    spec = value.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise SystemExit("ABORT: ATLAS repair4 census task shape differs")
    container = containers[0]
    expected_args = [
        "-c", grid_command, "--season", str(season), "--week", str(week),
        "--output-uri", uri,
    ]
    if container.get("image") != manifest["image"] or \
            container.get("command") != ["python"] or \
            container.get("args") != expected_args:
        raise SystemExit("ABORT: ATLAS repair4 census command/image differs")
    env = {
        row.get("name"): str(row.get("value", ""))
        for row in container.get("env", [])
    }
    if env != {
        "CODE_SHA": manifest["code_sha"],
        "ANALYSIS_IMAGE": manifest["image"],
    } or container.get("resources", {}).get("limits") != {
        "cpu": "4", "memory": "16Gi",
    }:
        raise SystemExit("ABORT: ATLAS repair4 census environment/resources differ")
    if task.get("maxRetries") != 0 or str(task.get("timeoutSeconds")) != "43200" \
            or task.get("serviceAccountName") != \
            "817589974517-compute@developer.gserviceaccount.com":
        raise SystemExit("ABORT: ATLAS repair4 census retry/timeout/account differs")
    reason = str(completed[0].get("reason", ""))
    message = str(completed[0].get("message", ""))
    status_counts[final_status] += 1
    if final_status == "False":
        cancelled_count = int(status.get("cancelledCount") or 0)
        if cancelled_count == 1 or "cancel" in f"{reason} {message}".lower():
            reason_key = "Cancelled"
        elif "configured memory limit was reached" in message:
            reason_key = "ConfiguredMemoryLimit"
        elif "Internal error running task" in message:
            reason_key = "InternalError"
        else:
            reason_key = reason or "unspecified"
        reason_counts[reason_key] += 1
    terminal.append({
        "season": season, "week": week, "job": job, "execution": execution,
        "status": final_status, "reason": reason, "message": message,
        "cancelled_count": int(status.get("cancelledCount") or 0),
        "completion_time": status["completionTime"],
    })

if status_counts["False"] < 1:
    raise SystemExit("ABORT: ATLAS repair4 failure census has no failed cell")
week8 = [row for row in terminal if row["season"] == 2023 and row["week"] == 8]
if len(week8) != 1 or week8[0]["status"] != "False" or \
        "configured memory limit was reached" not in week8[0]["message"]:
    raise SystemExit("ABORT: ATLAS repair4 natural memory failure differs")
inventory = [
    line.strip() for line in inventory_path.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
allowed = {row[4] for row in rows}
if any(uri not in allowed for uri in inventory) or len(inventory) != len(set(inventory)):
    raise SystemExit("ABORT: ATLAS repair4 object inventory differs")
payload = {
    "version": "atlas-matched-diversity-repair4-terminal-census-v1",
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
    "output_object_inventory_sha256": sha256(
        inventory_path.read_bytes()
    ).hexdigest(),
    "effect_fields_inspected": False,
    "historical_scoring_licensed": False,
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
  'historical_scoring_licensed=false' 'production_change_licensed=false' \
  > "$OUT/terminal-census-completion.txt"
sha256sum "$OUT/terminal-census-completion.txt" \
  > "$OUT/terminal-census-completion.sha256"
echo "ATLAS_REPAIR4_TERMINAL_CENSUS_HARVESTED $RUN_ID"
