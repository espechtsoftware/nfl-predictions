#!/bin/bash
# Launch the sole frozen same-image position-scale control and treatment.
# Usage: prop_lock_served_position_stage_b.sh <IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
SOURCE=20260810-lockfix-e80-k1-role12union-8677d21
CONTROL=20260811-lockfix-e80-k1-role12-position-control-v1
TREATMENT=20260811-lockfix-e80-k1-role12-position-scales-v1
ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
POSITION_SPEC=QB:0.970,RB:1.005,TE:0.940,WR:1.070
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CALIBRATION="$ROOT/reports/served-position-calibration-runs/20260811-served-position-calibration-v1/report.json"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$CODE_SHA" in
  ""|*[!0-9a-f]*) echo "ABORT: exact lowercase hexadecimal code SHA required"; exit 2 ;;
esac
[ -s "$CALIBRATION" ] || { echo "ABORT: calibration report absent"; exit 2; }
"$ROOT/.venv/bin/python" - "$CALIBRATION" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
expected = {"QB": 0.970, "RB": 1.005, "TE": 0.940, "WR": 1.070}
if report.get("disposition") != "served-position-calibration-passes":
    raise SystemExit("ABORT: frozen position calibration did not pass")
if not report.get("gate", {}).get("passes"):
    raise SystemExit("ABORT: frozen position-calibration gate is false")
if report.get("r2_final_served_fit", {}).get("factors") != expected:
    raise SystemExit("ABORT: fitted position factors differ from frozen factors")
print("frozen position-calibration pass and four factors verified")
PY

for panel in "$CONTROL" "$TREATMENT"; do
  [ ! -e "$ROOT/reports/panel-runs/$panel/executions.txt" ] || {
    echo "ABORT: immutable panel already launched: $panel"; exit 2; }
done

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
  --max_rows=1000 \
  "SELECT season, week, COUNT(*) AS n
   FROM \`$PROJECT.nfl_predictions.replay_candidates\`
   WHERE panel_run_id='$SOURCE' AND research_eligible
     AND code_sha='8677d21'
   GROUP BY season, week ORDER BY season, week" > "$TMP_DIR/source_counts.csv"
"$ROOT/.venv/bin/python" - "$TMP_DIR/source_counts.csv" <<'PY'
import csv
import sys

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
if len(rows) != 107:
    raise SystemExit(f"ABORT: expected 107 accepted source slates, got {len(rows)}")
if min(int(row["n"]) for row in rows) < 80:
    raise SystemExit("ABORT: accepted source contains an undersized pool")
print("accepted corrected direct-role source verified: 107 slates")
PY

COMMON="MODEL_ENSEMBLE=1|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES|ROLE_BELIEF_SEED=7331|REPLACEMENT_SLOTS=12"

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_SEASONS="2023 2024 2025" \
PANEL_ARM_LABEL=lockfix_k1_role12_position_control \
PANEL_ARM_ENV="$COMMON|SERVED_POSITION_SCALES=identity" \
PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC=12 \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 PANEL_SMOKE_SEASON=2024 \
PANEL_TASK_TIMEOUT=14400 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" lockk1posctl "$CONTROL"

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_SEASONS="2023 2024 2025" \
PANEL_ARM_LABEL=lockfix_k1_role12_position_scales \
PANEL_ARM_ENV="$COMMON|SERVED_POSITION_SCALES=$POSITION_SPEC" \
PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC=12 \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 PANEL_SMOKE_SEASON=2024 \
PANEL_TASK_TIMEOUT=14400 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" lockk1postrt "$TREATMENT"

echo "SERVED_POSITION_STAGE_B_LAUNCHED control=$CONTROL treatment=$TREATMENT source=$SOURCE"
