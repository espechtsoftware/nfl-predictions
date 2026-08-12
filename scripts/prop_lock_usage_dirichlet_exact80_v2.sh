#!/bin/bash
# Launch the sole PIT-clean fitted-K exact-80 control and treatment.
# Usage: prop_lock_usage_dirichlet_exact80_v2.sh <GENERATION_IMAGE@sha256:...> a12ab31
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
ROOT=$(cd "$(dirname "$0")/.." && pwd)
FROZEN_DIGEST=sha256:ad50fe19bde366ca11180b561127b09e2c79c97ec7dbbd5507282e33d2d5eb62
CONTROL=20260812-pitclean-e80-selected-usage-control-v2
TREATMENT=20260812-pitclean-e80-selected-usage-fitted-v2
TIER1="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-role-v2/selected_tier1.txt"
POSITION="$ROOT/reports/served-position-calibration-runs/20260812-served-position-stage-b-v2-pit-clean/selected_position.txt"
FIT_REPORT="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-data-fitted-usage-k-v2-pit-clean/report.json"
PROTOCOL="$ROOT/reports/2026-08-12-pit-clean-usage-exact80.md"

case "$IMG" in *@"$FROZEN_DIGEST") ;; *) echo "ABORT: wrong generation digest"; exit 2;; esac
[ "$CODE_SHA" = a12ab31 ] || { echo "ABORT: generation code is a12ab31"; exit 2; }
for path in "$TIER1" "$POSITION" "$FIT_REPORT" "$PROTOCOL"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
for panel in "$CONTROL" "$TREATMENT"; do
  [ ! -e "$ROOT/reports/panel-runs/$panel/executions.txt" ] || {
    echo "ABORT: immutable panel already launched: $panel"; exit 2; }
done

BASE=$(awk -F= '$1=="selected_base" {print $2}' "$TIER1")
HISTORICAL_SOURCE=$(awk -F= '$1=="selected_panel" {print $2}' "$TIER1")
ROLE_SELECTED=$(awk -F= '$1=="role_selected" {print $2}' "$TIER1")
POSITION_SELECTED=$(awk -F= '$1=="position_selected" {print $2}' "$POSITION")
POSITION_SPEC=$(awk -F= '$1=="served_position_scales" {print $2}' "$POSITION")
case "$BASE" in k1|k3) ;; *) echo "ABORT: invalid selected base"; exit 2;; esac
case "$ROLE_SELECTED" in true|false) ;; *) echo "ABORT: invalid role selection"; exit 2;; esac
case "$POSITION_SELECTED" in true|false) ;; *) echo "ABORT: invalid position selection"; exit 2;; esac
if [ "$POSITION_SELECTED" = true ]; then
  EVALUATION_SOURCE=$(awk -F= '$1=="selected_eval_panel" {print $2}' "$POSITION")
else
  EVALUATION_SOURCE=$HISTORICAL_SOURCE
  [ "$POSITION_SPEC" = identity ] || { echo "ABORT: identity position selection mismatch"; exit 2; }
fi

FITTED_K=$("$ROOT/.venv/bin/python" - "$FIT_REPORT" <<'PY'
import json
import math
import sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") != "data-fitted-usage-concentration-passes":
    raise SystemExit("ABORT: repaired fitted-K diagnostic did not pass")
if not report.get("gate", {}).get("passes"):
    raise SystemExit("ABORT: repaired fitted-K gate is false")
value = float(report.get("fit", {}).get("selected_k"))
if not math.isfinite(value) or not 5.0 < value < 500.0:
    raise SystemExit("ABORT: repaired fitted K is not finite and interior")
for season in ("2021", "2022", "2023", "2024", "2025"):
    for kind in ("targets", "carries"):
        if report["population"][season][kind]["opportunity_coverage"] < 0.95:
            raise SystemExit(f"ABORT: coverage gate differs for {season} {kind}")
print(repr(value))
PY
)

for spec in "$HISTORICAL_SOURCE:107" "$EVALUATION_SOURCE:54"; do
  PANEL=${spec%:*}
  EXPECTED=${spec#*:}
  COUNT=$(bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
    "SELECT COUNT(DISTINCT CONCAT(CAST(season AS STRING), '-', CAST(week AS STRING))) AS n
     FROM \`$PROJECT.nfl_predictions.replay_candidates\`
     WHERE panel_run_id='$PANEL' AND research_eligible AND code_sha='$CODE_SHA'
       AND ($EXPECTED = 107 OR season IN (2023, 2024, 2025))" \
    | tail -1 | tr -d '[:space:]')
  [ "$COUNT" = "$EXPECTED" ] || {
    echo "ABORT: source $PANEL has $COUNT slates, expected $EXPECTED"; exit 2; }
done

COMMON="TABPFN_MARGINALS=1|TABPFN_MARGINAL_TABLE=tabpfn_projections_pit_v2"
[ "$BASE" != k1 ] || COMMON="$COMMON|MODEL_ENSEMBLE=1"
N_EPI=0
if [ "$ROLE_SELECTED" = true ]; then
  ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
  COMMON="$COMMON|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES|ROLE_BELIEF_SEED=7331|REPLACEMENT_SLOTS=12"
  N_EPI=12
fi
[ "$POSITION_SPEC" = identity ] || COMMON="$COMMON|SERVED_POSITION_SCALES=$POSITION_SPEC"

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_SEASONS="2023 2024 2025" \
PANEL_ARM_LABEL=pit_clean_selected_usage_control_v2 \
PANEL_ARM_ENV="$COMMON" \
PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC="$N_EPI" \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 PANEL_SMOKE_SEASON=2024 \
PANEL_TASK_TIMEOUT=14400 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" pitusev2ctl "$CONTROL"

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_SEASONS="2023 2024 2025" \
PANEL_ARM_LABEL=pit_clean_selected_usage_fitted_v2 \
PANEL_ARM_ENV="$COMMON|GAME_SIM_USAGE=dirichlet|DIRICHLET_K=$FITTED_K" \
PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC="$N_EPI" \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 PANEL_SMOKE_SEASON=2024 \
PANEL_TASK_TIMEOUT=14400 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" pitusev2trt "$TREATMENT"

echo "PIT_USAGE_EXACT80_LAUNCHED source=$HISTORICAL_SOURCE evaluation=$EVALUATION_SOURCE fitted_k=$FITTED_K"
