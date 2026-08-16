#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260815-atlas-current-money-worlds-v1
OUT="$ROOT/reports/atlas-money-world-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
LIST="$OUT/executions.txt"

[ -s "$MANIFEST" ] && [ -s "$LIST" ] || {
  echo "ABORT: ATLAS money-world manifest/executions are incomplete" >&2
  exit 2
}
[ "$(wc -l < "$LIST")" = 15 ] || {
  echo "ABORT: ATLAS money-world acquisition needs 15 executions" >&2
  exit 2
}
[ ! -e "$OUT/acquisition-complete.txt" ] || {
  echo "ABORT: immutable ATLAS money-world acquisition is already finished" >&2
  exit 3
}
[ ! -e "$OUT/source-grid.json" ] || {
  echo "ABORT: immutable ATLAS money-world source grid already exists" >&2
  exit 3
}

IMAGE=$(awk -F= '$1=="image" {print $2}' "$MANIFEST")
CODE_SHA=$(awk -F= '$1=="code_sha" {print $2}' "$MANIFEST")
mkdir -p "$OUT/execution-metadata"

while read -r BLOCK SEASON PANEL JOB EXEC; do
  RECEIPT="$OUT/environment-receipts/r${BLOCK}-${SEASON}.json"
  TARGET="$OUT/execution-metadata/${EXEC}.json"
  [ -s "$RECEIPT" ] && [ ! -e "$TARGET" ] || {
    echo "ABORT: $EXEC receipt target is invalid" >&2; exit 2; }
  TMP="${TARGET}.pending"
  [ ! -e "$TMP" ] || {
    echo "ABORT: $EXEC has a stale pending receipt" >&2; exit 2; }
  gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format=json > "$TMP"
  "$ROOT/.venv/bin/python" - \
    "$TMP" "$RECEIPT" "$IMAGE" "$EXEC" "$SEASON" <<'PY'
import json
import sys

execution = json.load(open(sys.argv[1], encoding="utf-8"))
receipt = json.load(open(sys.argv[2], encoding="utf-8"))
image, name, season = sys.argv[3], sys.argv[4], int(sys.argv[5])
if execution.get("metadata", {}).get("name") != name:
    raise SystemExit("ABORT: acquisition execution name differs")
status = execution.get("status", {})
completed = [row for row in status.get("conditions", [])
             if row.get("type") == "Completed"]
if len(completed) != 1 or completed[0].get("status") != "True" or \
        int(status.get("succeededCount") or 0) != 1 or \
        int(status.get("failedCount") or 0) != 0 or \
        not status.get("completionTime"):
    raise SystemExit("ABORT: acquisition execution is not terminal successful")
spec = execution.get("spec", {})
template = spec.get("template", {}).get("spec", {})
containers = template.get("containers", [])
if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
        len(containers) != 1:
    raise SystemExit("ABORT: acquisition execution task shape differs")
container = containers[0]
expected_args = [
    "replay", "--season", str(season), "--contest", "gpp", "--entries", "80",
]
if container.get("image") != image or \
        container.get("command") != ["nfl-dfs"] or \
        container.get("args") != expected_args:
    raise SystemExit("ABORT: acquisition image/command differs")
actual_env = {
    row.get("name"): str(row.get("value", ""))
    for row in container.get("env", [])
}
if actual_env != receipt.get("values"):
    raise SystemExit("ABORT: acquisition execution environment differs")
if container.get("resources", {}).get("limits") != {
    "cpu": "4", "memory": "16Gi",
} or template.get("maxRetries") != 0 or \
        str(template.get("timeoutSeconds")) != "14400" or \
        template.get("serviceAccountName") != (
            "817589974517-compute@developer.gserviceaccount.com"
        ):
    raise SystemExit("ABORT: acquisition resources/account differ")
print("ATLAS_MONEY_WORLD_EXECUTION_VALIDATED", name)
PY
  mv "$TMP" "$TARGET"
  sha256sum "$TARGET" > "${TARGET}.sha256"
done < "$LIST"
sha256sum "$OUT"/execution-metadata/*.json | sort \
  > "$OUT/execution-metadata.sha256"
sha256sum "$OUT/execution-metadata.sha256" \
  > "$OUT/execution-metadata.sha256.sha256"

SOURCE_TMP="$OUT/source-grid.pending.json"
[ ! -e "$SOURCE_TMP" ] || {
  echo "ABORT: stale ATLAS money-world source-grid pending file" >&2; exit 2; }
bq query --project_id="$PROJECT" --use_legacy_sql=false --format=json \
  --max_rows=300 '
SELECT panel_run_id, season, week,
       ANY_VALUE(score_artifact_uri) AS score_artifact_uri,
       ANY_VALUE(score_artifact_sha256) AS score_artifact_sha256,
       ANY_VALUE(code_sha) AS code_sha,
       ANY_VALUE(lever_env) AS lever_env,
       COUNT(*) AS source_rows,
       COUNT(DISTINCT score_artifact_uri) AS uri_count,
       COUNT(DISTINCT score_artifact_sha256) AS sha_count,
       COUNT(DISTINCT code_sha) AS code_count,
       COUNT(DISTINCT lever_env) AS lever_count
FROM `nfl-predictions-503414.nfl_predictions.replay_candidates_staging`
WHERE panel_run_id IN (
  "20260815-atlas-money-worlds-r0-v1",
  "20260815-atlas-money-worlds-r1-v1",
  "20260815-atlas-money-worlds-r2-v1",
  "20260815-atlas-money-worlds-r3-v1",
  "20260815-atlas-money-worlds-r4-v1")
GROUP BY panel_run_id, season, week
ORDER BY panel_run_id, season, week' > "$SOURCE_TMP"

"$ROOT/.venv/bin/python" - "$SOURCE_TMP" "$CODE_SHA" <<'PY'
import json
import re
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))
code_sha = sys.argv[2]
panels = [f"20260815-atlas-money-worlds-r{block}-v1" for block in range(5)]
if len(rows) != 270:
    raise SystemExit(f"ABORT: acquisition source grid has {len(rows)} cells")
keys = set()
slates_by_panel = {panel: set() for panel in panels}
for row in rows:
    panel = str(row.get("panel_run_id"))
    season, week = int(row.get("season")), int(row.get("week"))
    key = (panel, season, week)
    if panel not in slates_by_panel or key in keys:
        raise SystemExit("ABORT: acquisition source key differs/repeats")
    keys.add(key)
    slates_by_panel[panel].add((season, week))
    if any(int(row.get(name) or 0) != 1 for name in (
        "uri_count", "sha_count", "code_count", "lever_count",
    )):
        raise SystemExit("ABORT: acquisition source identity is ambiguous")
    if str(row.get("code_sha")) != code_sha:
        raise SystemExit("ABORT: acquisition source code SHA differs")
    uri = str(row.get("score_artifact_uri", ""))
    digest = str(row.get("score_artifact_sha256", ""))
    if not uri.startswith("gs://") or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise SystemExit("ABORT: acquisition artifact identity is invalid")
    if int(row.get("source_rows") or 0) <= 0:
        raise SystemExit("ABORT: acquisition source has no candidates")
reference = slates_by_panel[panels[0]]
if len(reference) != 54 or any(
    slates_by_panel[panel] != reference for panel in panels[1:]
):
    raise SystemExit("ABORT: acquisition panel/slate grids differ")
if {season for season, _ in reference} != {2023, 2024, 2025}:
    raise SystemExit("ABORT: acquisition seasons differ")
print("ATLAS_MONEY_WORLD_SOURCE_GRID_VALIDATED", len(rows))
PY

mv "$SOURCE_TMP" "$OUT/source-grid.json"
sha256sum "$OUT/source-grid.json" > "$OUT/source-grid.sha256"
printf '%s\n' \
  "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'executions=15' 'source_cells=270' 'slates_per_panel=54' \
  > "$OUT/acquisition-complete.txt"
sha256sum "$OUT/acquisition-complete.txt" \
  > "$OUT/acquisition-complete.sha256"
echo "ATLAS_MONEY_WORLDS_HARVESTED $RUN_ID"
