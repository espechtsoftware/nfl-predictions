#!/bin/bash
# Launch the one preregistered corrected K1 + 12 direct-role candidate union.
# Usage: prop_lock_direct_role_union.sh <IMAGE@sha256:...> 8677d21
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
SOURCE=20260810-lockfix-e80-k1-8677d21
PANEL=20260810-lockfix-e80-k1-role12union-8677d21
ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
ROOT=$(cd "$(dirname "$0")/.." && pwd)

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
[ "$CODE_SHA" = 8677d21 ] || {
  echo "ABORT: corrected source is frozen to code 8677d21"; exit 2; }
OUT="$ROOT/reports/panel-runs/$PANEL"
[ ! -e "$OUT/executions.txt" ] || {
  echo "ABORT: immutable direct-role panel already launched"; exit 2; }

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
  --max_rows=1000 \
  "SELECT season, week, COUNT(*) AS n
   FROM \`$PROJECT.nfl_predictions.replay_candidates\`
   WHERE panel_run_id='$SOURCE' AND research_eligible
     AND code_sha='$CODE_SHA'
   GROUP BY season, week ORDER BY season, week" > "$TMP_DIR/source_counts.csv"
"$ROOT/.venv/bin/python" - "$TMP_DIR/source_counts.csv" <<'PY'
import csv
import sys

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
if len(rows) != 107:
    raise SystemExit(f"ABORT: expected 107 accepted K1 slates, got {len(rows)}")
if min(int(row["n"]) for row in rows) < 80:
    raise SystemExit("ABORT: accepted K1 source contains an undersized pool")
print("accepted corrected K1 source contract verified: 107 slates")
PY

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_ARM_LABEL=lockfix_k1_role12_union \
PANEL_ARM_ENV="MODEL_ENSEMBLE=1|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES|ROLE_BELIEF_SEED=7331|REPLACEMENT_SLOTS=12" \
PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC=12 \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 PANEL_SMOKE_SEASON=2024 \
PANEL_TASK_TIMEOUT=14400 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" lockk1role "$PANEL"
echo "CORRECTED_K1_DIRECT_ROLE_LAUNCHED panel=$PANEL source=$SOURCE"

