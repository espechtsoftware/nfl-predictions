#!/bin/bash
# Launch the sole PIT-clean same-image position-scale control and treatment.
# Usage: prop_lock_served_position_stage_b_v2.sh <GENERATION_IMAGE@sha256:...> a12ab31
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
ROOT=$(cd "$(dirname "$0")/.." && pwd)
FROZEN_DIGEST=sha256:ad50fe19bde366ca11180b561127b09e2c79c97ec7dbbd5507282e33d2d5eb62
CONTROL=20260812-pitclean-e80-selected-position-control-v2
TREATMENT=20260812-pitclean-e80-selected-position-scales-v2
SELECTION="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-role-v2/selected_tier1.txt"
CALIBRATION="$ROOT/reports/served-position-calibration-runs/20260812-served-position-calibration-v2-pit-clean/report.json"

case "$IMG" in *@"$FROZEN_DIGEST") ;; *) echo "ABORT: wrong generation digest"; exit 2;; esac
[ "$CODE_SHA" = a12ab31 ] || { echo "ABORT: generation code is a12ab31"; exit 2; }
for path in "$SELECTION" "$CALIBRATION"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
for panel in "$CONTROL" "$TREATMENT"; do
  [ ! -e "$ROOT/reports/panel-runs/$panel/executions.txt" ] || {
    echo "ABORT: immutable panel already launched: $panel"; exit 2; }
done

BASE=$(awk -F= '$1=="selected_base" {print $2}' "$SELECTION")
SOURCE=$(awk -F= '$1=="selected_panel" {print $2}' "$SELECTION")
ROLE_SELECTED=$(awk -F= '$1=="role_selected" {print $2}' "$SELECTION")
case "$BASE" in k1|k3) ;; *) echo "ABORT: invalid selected base"; exit 2;; esac
case "$ROLE_SELECTED" in true|false) ;; *) echo "ABORT: invalid role selection"; exit 2;; esac
case "$SOURCE" in ""|*[!A-Za-z0-9_-]*) echo "ABORT: invalid selected panel"; exit 2;; esac

POSITION_SPEC=$("$ROOT/.venv/bin/python" - "$CALIBRATION" "$SOURCE" "$BASE" <<'PY'
import json
import math
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") != "served-position-calibration-passes":
    raise SystemExit("ABORT: repaired position calibration did not pass")
if not report.get("gate", {}).get("passes"):
    raise SystemExit("ABORT: repaired position-calibration gate is false")
contract = report.get("contract", {})
if contract.get("version") != "v2" or contract.get("panel") != sys.argv[2]:
    raise SystemExit("ABORT: repaired position report targets another panel")
expected_ensemble = 1 if sys.argv[3] == "k1" else 3
if contract.get("model_ensemble") != expected_ensemble:
    raise SystemExit("ABORT: repaired position report targets another ensemble")
if contract.get("tabpfn_table") != "tabpfn_projections_pit_v2":
    raise SystemExit("ABORT: repaired position report used another cache")
factors = report.get("r2_final_served_fit", {}).get("factors", {})
if set(factors) != {"QB", "RB", "TE", "WR"}:
    raise SystemExit("ABORT: repaired position factors are incomplete")
if not all(math.isfinite(float(value)) for value in factors.values()):
    raise SystemExit("ABORT: repaired position factors are non-finite")
print(",".join(f"{pos}:{float(factors[pos])!r}" for pos in ("QB", "RB", "TE", "WR")))
PY
)

COUNT=$(bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
  "SELECT COUNT(DISTINCT CONCAT(CAST(season AS STRING), '-', CAST(week AS STRING))) AS n
   FROM \`$PROJECT.nfl_predictions.replay_candidates\`
   WHERE panel_run_id='$SOURCE' AND research_eligible AND code_sha='$CODE_SHA'" \
  | tail -1 | tr -d '[:space:]')
[ "$COUNT" = 107 ] || { echo "ABORT: selected panel has $COUNT accepted slates"; exit 2; }

COMMON="TABPFN_MARGINALS=1|TABPFN_MARGINAL_TABLE=tabpfn_projections_pit_v2"
[ "$BASE" != k1 ] || COMMON="$COMMON|MODEL_ENSEMBLE=1"
N_EPI=0
if [ "$ROLE_SELECTED" = true ]; then
  ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
  COMMON="$COMMON|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES|ROLE_BELIEF_SEED=7331|REPLACEMENT_SLOTS=12"
  N_EPI=12
fi

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_SEASONS="2023 2024 2025" \
PANEL_ARM_LABEL=pit_clean_selected_position_control_v2 \
PANEL_ARM_ENV="$COMMON|SERVED_POSITION_SCALES=identity" \
PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC="$N_EPI" \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 PANEL_SMOKE_SEASON=2024 \
PANEL_TASK_TIMEOUT=14400 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" pitposv2ctl "$CONTROL"

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_SEASONS="2023 2024 2025" \
PANEL_ARM_LABEL=pit_clean_selected_position_scales_v2 \
PANEL_ARM_ENV="$COMMON|SERVED_POSITION_SCALES=$POSITION_SPEC" \
PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC="$N_EPI" \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 PANEL_SMOKE_SEASON=2024 \
PANEL_TASK_TIMEOUT=14400 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" pitposv2trt "$TREATMENT"

echo "PIT_POSITION_STAGE_B_LAUNCHED source=$SOURCE control=$CONTROL treatment=$TREATMENT factors=$POSITION_SPEC"
