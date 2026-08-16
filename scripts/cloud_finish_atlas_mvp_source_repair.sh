#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-mvp-source-repair-r3-2025-v1
PANEL=20260816-atlas-mvp-repair-r3-2025-v1
OUT="$ROOT/reports/atlas-mvp-source-repair-runs/$RUN_ID"
EXEC_FILE="$OUT/execution.txt"
RECEIPT="$OUT/environment-receipt.json"
ORIGINAL_URI=gs://nfl-predictions-503414-raw/cand_scores/20260815-atlas-money-worlds-r3-v1/2025_w1_0590227023eb.npz

[ -s "$EXEC_FILE" ] && [ -s "$RECEIPT" ] || {
  echo "ABORT: ATLAS MVP repair launch receipt is incomplete" >&2; exit 2; }
[ ! -e "$OUT/completion.txt" ] && [ ! -e "$OUT/validation.json" ] || {
  echo "ABORT: immutable ATLAS MVP repair is already harvested" >&2; exit 3; }
EXEC=$(cat "$EXEC_FILE")
EXEC_TMP="$OUT/execution.pending.json"
gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$EXEC_TMP"
"$ROOT/.venv/bin/python" - "$EXEC_TMP" "$RECEIPT" "$EXEC" <<'PY'
import json
import sys
from nfl_dfs.research.atlas_mvp_source_repair import validate_repair_execution

execution = json.load(open(sys.argv[1], encoding="utf-8"))
receipt = json.load(open(sys.argv[2], encoding="utf-8"))
result = validate_repair_execution(
    execution, execution_name=sys.argv[3],
    expected_environment=receipt["values"], terminal=True,
)
print("ATLAS_MVP_SOURCE_REPAIR_EXECUTION_VALIDATED", result["execution"])
PY
mv "$EXEC_TMP" "$OUT/execution.json"
sha256sum "$OUT/execution.json" > "$OUT/execution.sha256"

bq query --project_id="$PROJECT" --use_legacy_sql=false --format=json \
  --max_rows=30 \
  "SELECT season,week,COUNT(*) AS candidates,COUNTIF(tag='boom') AS boom,COUNT(DISTINCT cand_ix) AS indices,COUNT(DISTINCT score_artifact_uri) AS uris,COUNT(DISTINCT score_artifact_sha256) AS shas FROM \`$PROJECT.nfl_predictions.replay_candidates_staging\` WHERE panel_run_id='$PANEL' GROUP BY season,week ORDER BY season,week" \
  > "$OUT/cell-grid.pending.json"
"$ROOT/.venv/bin/python" - "$OUT/cell-grid.pending.json" <<'PY'
import json, sys
rows=json.load(open(sys.argv[1], encoding="utf-8"))
if len(rows) != 18 or [(int(r["season"]), int(r["week"])) for r in rows] != [(2025, w) for w in range(1, 19)]:
    raise SystemExit("ABORT: repair cell grid differs")
for row in rows:
    if int(row["candidates"]) <= 0 or int(row["candidates"]) != int(row["indices"]) or int(row["boom"]) != 40 or int(row["uris"]) != 1 or int(row["shas"]) != 1:
        raise SystemExit("ABORT: repair cell candidate/artifact contract differs")
if int(rows[0]["candidates"]) != 248:
    raise SystemExit("ABORT: repaired Week 1 candidate count differs")
print("ATLAS_MVP_SOURCE_REPAIR_GRID_VALIDATED", len(rows))
PY
mv "$OUT/cell-grid.pending.json" "$OUT/cell-grid.json"
sha256sum "$OUT/cell-grid.json" > "$OUT/cell-grid.sha256"

bq query --project_id="$PROJECT" --use_legacy_sql=false --format=json \
  --max_rows=300 \
  "SELECT cand_ix,tag,players,salary,score_artifact_uri,score_artifact_sha256 FROM \`$PROJECT.nfl_predictions.replay_candidates_staging\` WHERE panel_run_id='$PANEL' AND season=2025 AND week=1 ORDER BY cand_ix" \
  > "$OUT/week1-candidates.json"
bq query --project_id="$PROJECT" --use_legacy_sql=false --format=json \
  --max_rows=1000 \
  "SELECT id,pos,team,opp,game_id,salary FROM \`$PROJECT.nfl_predictions.slate_player_features\` WHERE panel_run_id='$PANEL' AND season=2025 AND week=1 ORDER BY id" \
  > "$OUT/week1-features.json"
REPAIRED_URI=$("$ROOT/.venv/bin/python" - "$OUT/week1-candidates.json" <<'PY'
import json, re, sys
rows=json.load(open(sys.argv[1], encoding="utf-8"))
uris={str(row["score_artifact_uri"]) for row in rows}
shas={str(row["score_artifact_sha256"]) for row in rows}
if len(rows) != 248 or len(uris) != 1 or len(shas) != 1 or not next(iter(uris)).startswith("gs://") or not re.fullmatch(r"[0-9a-f]{64}", next(iter(shas))):
    raise SystemExit("ABORT: repaired Week 1 artifact binding differs")
print(next(iter(uris)))
PY
)
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
gcloud storage cp "$ORIGINAL_URI" "$TMP/original.npz" >/dev/null
gcloud storage cp "$REPAIRED_URI" "$TMP/repaired.npz" >/dev/null
"$ROOT/.venv/bin/python" "$ROOT/scripts/validate_atlas_mvp_source_repair.py" \
  --original "$TMP/original.npz" --repaired "$TMP/repaired.npz" \
  --candidates "$OUT/week1-candidates.json" \
  --features "$OUT/week1-features.json" \
  --output "$OUT/validation.json"
sha256sum "$OUT/week1-candidates.json" "$OUT/week1-features.json" \
  "$OUT/validation.json" > "$OUT/validation.sha256"
printf '%s\n' \
  "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  "execution=$EXEC" "panel=$PANEL" "repaired_artifact_uri=$REPAIRED_URI" \
  'uses_realized_outcomes=false' 'disposition=valid-mvp-source' \
  > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "ATLAS_MVP_SOURCE_REPAIR_HARVESTED $EXEC"
