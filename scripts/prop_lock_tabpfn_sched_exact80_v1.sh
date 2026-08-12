#!/bin/bash
# Launch the sole PIT-clean TabPFN SCHED exact-80 pair.
# The validated generation identity is read from its tracked pre-result record.
set -euo pipefail

PROJECT=nfl-predictions-503414
ROOT=$(cd "$(dirname "$0")/.." && pwd)
FREEZE="$ROOT/reports/tabpfn-sched-runs/20260812-sched-generation-v1/image.txt"
CONTROL=20260812-pitclean-e80-selected-tabpfn-sched-control-v1
TREATMENT=20260812-pitclean-e80-selected-tabpfn-sched-treatment-v1
CONTROL_TABLE=tabpfn_sched_control_v1
TREATMENT_TABLE=tabpfn_sched_treatment_v1
TIER1="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-role-v2/selected_tier1.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
FINAL_REPORT="$ROOT/reports/tabpfn-sched-runs/20260812-tabpfn-sched-final-served-v1-pit-clean/report.json"
CACHE_VALIDATION="$ROOT/reports/tabpfn-sched-runs/20260812-tabpfn-sched-v1-pit-clean/validation.json"
PROTOCOL="$ROOT/reports/2026-08-12-pit-clean-tabpfn-sched-exact80.md"

for path in "$FREEZE" "$TIER1" "$USAGE" "$ACTIVE" "$FINAL_REPORT" \
    "$CACHE_VALIDATION" "$PROTOCOL"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
IMG=$(awk -F= '$1=="image" {print $2}' "$FREEZE")
CODE_SHA=$(awk -F= '$1=="code_sha" {print $2}' "$FREEZE")
case "$IMG" in *@sha256:*) ;; *) echo "ABORT: frozen image is not immutable"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: frozen generation code SHA is invalid"; exit 2;;
esac
for panel in "$CONTROL" "$TREATMENT"; do
  [ ! -e "$ROOT/reports/panel-runs/$panel/executions.txt" ] || {
    echo "ABORT: immutable panel already launched: $panel"; exit 2; }
done

SOURCE=$(awk -F= '$1=="selected_panel" {print $2}' "$TIER1")
BASE=$(awk -F= '$1=="selected_base" {print $2}' "$TIER1")
ROLE_SELECTED=$(awk -F= '$1=="role_selected" {print $2}' "$TIER1")
USAGE_SOURCE=$(awk -F= '$1=="historical_source" {print $2}' "$USAGE")
ALLOCATION=$(awk -F= '$1=="allocation" {print $2}' "$USAGE")
SELECTED_K=$(awk -F= '$1=="selected_k" {print $2}' "$USAGE")
LABEL_LAW=$(awk -F= '$1=="label_law" {print $2}' "$ACTIVE")
[ "$BASE" = k1 ] || { echo "ABORT: SCHED requires selected K1"; exit 2; }
[ "$SOURCE" = "$USAGE_SOURCE" ] || {
  echo "ABORT: Tier-1 and usage historical sources differ"; exit 2; }
case "$ROLE_SELECTED" in true|false) ;; *) echo "ABORT: invalid role selection"; exit 2;; esac
case "$ALLOCATION:$SELECTED_K" in
  multinomial:infinity|dirichlet:*) ;;
  *) echo "ABORT: invalid terminal usage law"; exit 2;;
esac
case "$LABEL_LAW" in current|active-only) ;; *) echo "ABORT: invalid label law"; exit 2;; esac

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
"$ROOT/.venv/bin/python" - "$FINAL_REPORT" "$CACHE_VALIDATION" \
  "$SOURCE" "$ALLOCATION" "$SELECTED_K" "$LABEL_LAW" \
  "$TMP_DIR/schedules.txt" <<'PY'
import json
import math
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
cache = json.load(open(sys.argv[2], encoding="utf-8"))
if report.get("disposition") != "tabpfn-sched-final-served-passes" or \
        not report.get("gate", {}).get("passes"):
    raise SystemExit("ABORT: SCHED final-served gate did not pass")
if report.get("version") != "v1" or report.get("panel") != sys.argv[3]:
    raise SystemExit("ABORT: SCHED final-served report targets another lineage")
expected_label = "active_only" if sys.argv[6] == "active-only" else "current"
if report.get("label_law") != expected_label:
    raise SystemExit("ABORT: SCHED report label law differs")
if report.get("cache_tables") != {
        "control": "tabpfn_sched_control_v1",
        "treatment": "tabpfn_sched_treatment_v1",
} or report.get("cache_rows") != 52307:
    raise SystemExit("ABORT: SCHED report cache contract differs")
if cache.get("disposition") != "tabpfn-sched-caches-valid" or \
        not cache.get("passes") or cache.get("label_law") != expected_label:
    raise SystemExit("ABORT: SCHED caches are invalid")
if not cache.get("control_reproduction", {}).get("passes"):
    raise SystemExit("ABORT: SCHED control does not reproduce inherited cache")
usage = report.get("common_usage_law", {})
if sys.argv[4] == "multinomial":
    expected = {"mode": "production-multinomial", "game_sim_usage": "", "k": ""}
    if usage != expected or sys.argv[5] != "infinity":
        raise SystemExit("ABORT: SCHED report usage differs from multinomial")
else:
    if usage.get("mode") != "data-fitted-dirichlet" or \
            usage.get("game_sim_usage") != "dirichlet" or \
            usage.get("k") != sys.argv[5]:
        raise SystemExit("ABORT: SCHED report usage differs from fitted K")
if any(float(report.get("maximum_mean_delta", {}).get(arm, math.inf)) > 1e-10
       for arm in ("control", "treatment")):
    raise SystemExit("ABORT: SCHED final-served mean preservation failed")
lines = []
for arm in ("control", "treatment"):
    schedule = report.get(f"{arm}_schedule", {})
    if set(schedule) != {"2023", "2024", "2025"}:
        raise SystemExit(f"ABORT: {arm} SCHED schedule seasons differ")
    for season in ("2023", "2024", "2025"):
        factors = schedule[season].get("factors", {})
        if set(factors) != {"QB", "RB", "TE", "WR"}:
            raise SystemExit(f"ABORT: {arm} {season} factors differ")
        spec = ",".join(
            f"{pos}:{float(factors[pos])!r}" for pos in ("QB", "RB", "TE", "WR"))
        lines.append(f"{arm} {season} {spec}")
open(sys.argv[7], "w", encoding="utf-8").write("\n".join(lines) + "\n")
PY

declare -A CONTROL_SPEC TREATMENT_SPEC
while read -r arm season spec; do
  if [ "$arm" = control ]; then
    CONTROL_SPEC[$season]=$spec
  else
    TREATMENT_SPEC[$season]=$spec
  fi
done < "$TMP_DIR/schedules.txt"
COUNT=$(bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
  "SELECT COUNT(DISTINCT CONCAT(CAST(season AS STRING), '-', CAST(week AS STRING))) AS n
   FROM \`$PROJECT.nfl_predictions.replay_candidates\`
   WHERE panel_run_id='$SOURCE' AND research_eligible AND code_sha='a12ab31'" \
  | tail -1 | tr -d '[:space:]')
[ "$COUNT" = 107 ] || { echo "ABORT: historical source has $COUNT slates"; exit 2; }

COMMON="MODEL_ENSEMBLE=1|TABPFN_MARGINALS=1"
N_EPI=0
if [ "$ROLE_SELECTED" = true ]; then
  ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
  COMMON="$COMMON|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES|ROLE_BELIEF_SEED=7331|REPLACEMENT_SLOTS=12"
  N_EPI=12
fi
if [ "$ALLOCATION" = dirichlet ]; then
  COMMON="$COMMON|GAME_SIM_USAGE=dirichlet|DIRICHLET_K=$SELECTED_K"
fi

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_SEASONS="2023 2024 2025" \
PANEL_ARM_LABEL=pit_clean_selected_tabpfn_sched_control_v1 \
PANEL_ARM_ENV="$COMMON" \
PANEL_ARM_ENV_2023="TABPFN_MARGINAL_TABLE=$CONTROL_TABLE|SERVED_POSITION_SCALES=${CONTROL_SPEC[2023]}" \
PANEL_ARM_ENV_2024="TABPFN_MARGINAL_TABLE=$CONTROL_TABLE|SERVED_POSITION_SCALES=${CONTROL_SPEC[2024]}" \
PANEL_ARM_ENV_2025="TABPFN_MARGINAL_TABLE=$CONTROL_TABLE|SERVED_POSITION_SCALES=${CONTROL_SPEC[2025]}" \
PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC="$N_EPI" \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 PANEL_SMOKE_SEASON=2024 \
PANEL_TASK_TIMEOUT=14400 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" pitschedctl "$CONTROL"

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_SEASONS="2023 2024 2025" \
PANEL_ARM_LABEL=pit_clean_selected_tabpfn_sched_treatment_v1 \
PANEL_ARM_ENV="$COMMON" \
PANEL_ARM_ENV_2023="TABPFN_MARGINAL_TABLE=$TREATMENT_TABLE|SERVED_POSITION_SCALES=${TREATMENT_SPEC[2023]}" \
PANEL_ARM_ENV_2024="TABPFN_MARGINAL_TABLE=$TREATMENT_TABLE|SERVED_POSITION_SCALES=${TREATMENT_SPEC[2024]}" \
PANEL_ARM_ENV_2025="TABPFN_MARGINAL_TABLE=$TREATMENT_TABLE|SERVED_POSITION_SCALES=${TREATMENT_SPEC[2025]}" \
PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC="$N_EPI" \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 PANEL_SMOKE_SEASON=2024 \
PANEL_TASK_TIMEOUT=14400 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" pitschedtrt "$TREATMENT"

echo "PIT_SCHED_EXACT80_LAUNCHED source=$SOURCE control=$CONTROL treatment=$TREATMENT"
