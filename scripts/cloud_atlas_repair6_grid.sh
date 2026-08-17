#!/usr/bin/env bash
set -euo pipefail

# Release every mechanically eligible repair6 cell after the dual canary.

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260817-atlas-matched-diversity-mvp-v1-repair6
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/$RUN_ID
MANIFEST="$OUT/manifest.txt"
ELIGIBLE="$OUT/eligible-cells.txt"
CANARY="$OUT/canary-completion.txt"
CANARY_LEDGER="$OUT/canary-executions.txt"
LEDGER="$OUT/repair6-executions.txt"
PENDING="$OUT/repair6-executions.pending.txt"
RELEASE="$OUT/repair6-grid-release.txt"

for REQUIRED in "$MANIFEST" "$OUT/manifest.sha256" "$ELIGIBLE" \
  "$OUT/eligible-cells.sha256" "$CANARY" "$OUT/canary-finish.sha256" \
  "$CANARY_LEDGER" "$OUT/canary-executions.sha256"; do
  [ -s "$REQUIRED" ] || {
    echo "ERROR: ATLAS repair6 grid dependency is incomplete: $REQUIRED" >&2
    exit 2
  }
done
[ ! -e "$LEDGER" ] && [ ! -e "$RELEASE" ] || {
  echo "ERROR: immutable ATLAS repair6 grid receipt exists" >&2; exit 3; }

IMAGE=$(awk -F= '$1=="image" {print $2}' "$MANIFEST")
CODE_SHA=$(awk -F= '$1=="code_sha" {print $2}' "$MANIFEST")
GRID_COMMAND=$($ROOT/.venv/bin/python \
  "$ROOT/scripts/render_atlas_matched_diversity_repair4_command.py" \
  --replacement-prefix "$PREFIX")

PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" - \
  "$MANIFEST" "$ELIGIBLE" "$CANARY" "$CANARY_LEDGER" \
  "$OUT/canary-finish.sha256" "$GRID_COMMAND" \
  "$ROOT/scripts/cloud_atlas_repair6_grid.sh" <<'PY'
from hashlib import sha256
from pathlib import Path
import sys
from nfl_dfs.research.atlas_historical_v3_sources import parse_kv

manifest_path, eligible_path, canary_path, ledger_path, finish_hashes = map(
    Path, sys.argv[1:6]
)
grid_command = sys.argv[6]
grid_launcher = Path(sys.argv[7])
m = parse_kv(manifest_path)
c = parse_kv(canary_path)
eligible = [line.split() for line in eligible_path.read_text().splitlines() if line]
canaries = [line.split() for line in ledger_path.read_text().splitlines() if line]
if c.get("disposition") != "repair6-dual-canary-passes" or \
        c.get("repair5_repair6_week1_byte_identical") != "true" or \
        c.get("uses_realized_outcomes") != "false" or \
        m.get("run_id") != "20260817-atlas-matched-diversity-mvp-v1-repair6" or \
        m.get("grid_command_sha256") != sha256(grid_command.encode()).hexdigest() or \
        any(len(row) != 6 for row in eligible) or not eligible or \
        len({(row[0], row[1]) for row in eligible}) != len(eligible) or \
        len(canaries) != 2 or any(len(row) != 6 for row in canaries):
    raise SystemExit("ERROR: ATLAS repair6 grid source differs")
if m.get("grid_launcher_sha256") != sha256(grid_launcher.read_bytes()).hexdigest():
    raise SystemExit("ERROR: ATLAS repair6 grid launcher differs")
def verify(path):
    receipt = path.with_suffix(".sha256")
    expected = f"{sha256(path.read_bytes()).hexdigest()}  {path}\n"
    if not receipt.is_file() or receipt.read_text() != expected:
        raise SystemExit("ERROR: ATLAS repair6 grid source hash differs")
for path in (manifest_path, eligible_path, ledger_path):
    verify(path)
hashed = {line.split(maxsplit=1)[1] for line in finish_hashes.read_text().splitlines()}
if str(canary_path) not in hashed:
    raise SystemExit("ERROR: ATLAS repair6 canary completion is unsealed")
PY

touch "$PENDING"
while read -r SEASON WEEK PRIMARY_EXEC WORLD JOB URI; do
  [ "$JOB" = "atlas-md-s${SEASON}-w${WEEK}-r6" ] && \
    [ "$URI" = "$PREFIX/slate-${SEASON}-${WEEK}.json" ] || {
    echo "ERROR: ATLAS repair6 eligible-cell identity differs" >&2; exit 2; }
  if awk -v s="$SEASON" -v w="$WEEK" \
      '$1==s && $2==w {found=1} END {exit !found}' "$PENDING"; then
    continue
  fi
  if [ "$SEASON" = 2023 ] && [ "$WEEK" = 7 ]; then
    read -r ROLE C_SEASON C_WEEK C_JOB EXEC C_URI \
      < <(awk '$1=="defect"' "$CANARY_LEDGER")
    [ "$ROLE" = defect ] && [ "$C_SEASON" = "$SEASON" ] && \
      [ "$C_WEEK" = "$WEEK" ] && [ "$C_JOB" = "$JOB" ] && \
      [ "$C_URI" = "$URI" ] || {
      echo "ERROR: ATLAS repair6 defect canary binding differs" >&2; exit 2; }
  else
    LISTED=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
      --region "$REGION" --format='value(metadata.name)' 2>/dev/null || true)
    if [ -n "$LISTED" ]; then
      [ "$(printf '%s\n' "$LISTED" | sed '/^$/d' | wc -l)" = 1 ] || {
        echo "ERROR: ATLAS repair6 eligible job has extra executions: $JOB" >&2
        exit 3
      }
      EXEC=$LISTED
    else
      if gcloud storage objects describe "$URI" --project "$PROJECT" \
          >/dev/null 2>&1; then
        echo "ERROR: ATLAS repair6 eligible object exists without execution: $URI" >&2
        exit 3
      fi
      gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
        --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 8 --memory 32Gi \
        --max-retries 0 --task-timeout 12h --service-account "$SERVICE_ACCOUNT" \
        --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
        --command python \
        --args=-c,"$GRID_COMMAND",--season,"$SEASON",--week,"$WEEK",--output-uri,"$URI" \
        --quiet >/dev/null
      EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
        --region "$REGION" --async --format='value(metadata.name)')
    fi
  fi
  [[ "$EXEC" == "$JOB-"* ]] || {
    echo "ERROR: ATLAS repair6 execution identity differs" >&2; exit 2; }
  printf '%s %s %s %s %s %s\n' \
    "$SEASON" "$WEEK" "$PRIMARY_EXEC" "$JOB" "$EXEC" "$URI" >> "$PENDING"
done < "$ELIGIBLE"

[ "$(wc -l < "$PENDING")" = "$(wc -l < "$ELIGIBLE")" ] || {
  echo "ERROR: ATLAS repair6 eligible grid is incomplete" >&2; exit 2; }
mv "$PENDING" "$LEDGER"
sha256sum "$LEDGER" > "$OUT/repair6-executions.sha256"
printf '%s\n' \
  "released_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  "eligible_cells=$(wc -l < "$ELIGIBLE")" \
  "repair6_executions=$(wc -l < "$LEDGER")" \
  "canary_completion_sha256=$(sha256sum "$CANARY" | awk '{print $1}')" \
  'uses_realized_outcomes=false' 'effect_fields_inspected=false' \
  'production_change_licensed=false' > "$RELEASE"
sha256sum "$RELEASE" > "$OUT/repair6-grid-release.sha256"
echo "ATLAS_REPAIR6_GRID_RELEASED $RUN_ID"
