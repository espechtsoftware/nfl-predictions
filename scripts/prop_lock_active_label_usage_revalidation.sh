#!/bin/bash
# Launch the sole active-only multinomial control for fitted-K revalidation.
# Usage: prop_lock_active_label_usage_revalidation.sh <GENERATION_IMAGE@sha256:...> a12ab31
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
ROOT=$(cd "$(dirname "$0")/.." && pwd)
FROZEN_IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ad50fe19bde366ca11180b561127b09e2c79c97ec7dbbd5507282e33d2d5eb62
CONTROL=20260812-pitclean-e80-active-label-usage-multinomial-v1
TREATMENT=20260812-pitclean-e80-selected-tabpfn-active-v2
HISTORICAL_SOURCE=20260811-pitclean-e80-k1-role12union-a12ab31
ACTIVE_TABLE=tabpfn_active_label_treatment_v2
PROTOCOL="$ROOT/reports/2026-08-12-active-label-usage-revalidation-protocol.md"
ACTIVE_SELECTION="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
USAGE_SELECTION="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"
FINAL_REPORT="$ROOT/reports/tabpfn-active-label-runs/20260811-tabpfn-active-label-final-served-v2-pit-clean/report.json"
OUT="$ROOT/reports/panel-runs/$CONTROL"

[ "$IMG" = "$FROZEN_IMAGE" ] || {
  echo "ABORT: wrong generation image package or digest"; exit 2; }
[ "$CODE_SHA" = a12ab31 ] || {
  echo "ABORT: generation code is a12ab31"; exit 2; }
for path in "$PROTOCOL" "$ACTIVE_SELECTION" "$USAGE_SELECTION" "$FINAL_REPORT"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/executions.txt" ] || {
  echo "ABORT: immutable multinomial control already launched"; exit 2; }

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
"$ROOT/.venv/bin/python" - "$ACTIVE_SELECTION" "$USAGE_SELECTION" \
  "$FINAL_REPORT" "$TREATMENT" "$HISTORICAL_SOURCE" \
  "$TMP_DIR/schedules.txt" <<'PY'
import json
import math
import sys

def selection(path):
    return dict(
        line.rstrip("\n").split("=", 1)
        for line in open(path, encoding="utf-8") if "=" in line)

active = selection(sys.argv[1])
usage = selection(sys.argv[2])
report = json.load(open(sys.argv[3], encoding="utf-8"))
if active.get("label_law") != "active-only" or \
        active.get("cache_table") != "tabpfn_active_label_treatment_v2" or \
        active.get("selected_eval_panel") != sys.argv[4] or \
        active.get("historical_source") != sys.argv[5]:
    raise SystemExit("ABORT: active-label selection differs from frozen arm")
if usage.get("allocation") != "dirichlet" or \
        usage.get("selected_k") != "28.154043586960896":
    raise SystemExit("ABORT: finite-K incumbent differs from frozen arm")
if report.get("disposition") != "tabpfn-active-label-final-served-passes" or \
        not report.get("gate", {}).get("passes"):
    raise SystemExit("ABORT: active-label final-served prerequisite did not pass")
if report.get("cache_tables", {}).get("treatment") != \
        "tabpfn_active_label_treatment_v2":
    raise SystemExit("ABORT: active-only cache differs")
if float(report.get("maximum_mean_delta", {}).get("treatment", math.inf)) > 1e-10:
    raise SystemExit("ABORT: active-only mean preservation failed")
expected = {
    "2023": {"QB": 0.965, "RB": 0.99, "TE": 0.945, "WR": 1.03},
    "2024": {"QB": 0.905, "RB": 0.97, "TE": 0.95, "WR": 1.06},
    "2025": {"QB": 0.925, "RB": 0.96, "TE": 0.94, "WR": 1.04},
}
schedule = report.get("treatment_schedule", {})
for season, factors in expected.items():
    if schedule.get(season, {}).get("factors") != factors:
        raise SystemExit(f"ABORT: active-only {season} schedule differs")
with open(sys.argv[6], "w", encoding="utf-8") as handle:
    for season, factors in expected.items():
        spec = ",".join(
            f"{pos}:{float(factors[pos])!r}" for pos in ("QB", "RB", "TE", "WR"))
        handle.write(f"{season} {spec}\n")
PY

declare -A SPEC
while read -r season spec; do SPEC[$season]=$spec; done < "$TMP_DIR/schedules.txt"
TREATMENT_ROWS=$(bq query --project_id="$PROJECT" --use_legacy_sql=false \
  --format=csv \
  "SELECT COUNT(*) AS n FROM \`$PROJECT.nfl_predictions.replay_candidates\`
   WHERE panel_run_id='$TREATMENT' AND research_eligible
     AND season IN (2023, 2024, 2025)" | tail -1 | tr -d '[:space:]')
[ "$TREATMENT_ROWS" -gt 0 ] || {
  echo "ABORT: immutable active-only finite-K treatment is absent"; exit 2; }

ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
COMMON="MODEL_ENSEMBLE=1|TABPFN_MARGINALS=1|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES|ROLE_BELIEF_SEED=7331|REPLACEMENT_SLOTS=12"

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_SEASONS="2023 2024 2025" \
PANEL_ARM_LABEL=pit_clean_active_label_usage_multinomial_v1 \
PANEL_ARM_ENV="$COMMON" \
PANEL_ARM_ENV_2023="TABPFN_MARGINAL_TABLE=$ACTIVE_TABLE|SERVED_POSITION_SCALES=${SPEC[2023]}" \
PANEL_ARM_ENV_2024="TABPFN_MARGINAL_TABLE=$ACTIVE_TABLE|SERVED_POSITION_SCALES=${SPEC[2024]}" \
PANEL_ARM_ENV_2025="TABPFN_MARGINAL_TABLE=$ACTIVE_TABLE|SERVED_POSITION_SCALES=${SPEC[2025]}" \
PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC=12 \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 PANEL_SMOKE_SEASON=2024 \
PANEL_TASK_TIMEOUT=14400 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" pitactusemult "$CONTROL"

mkdir -p "$OUT"
printf '%s\n' \
  "control=$CONTROL" "treatment=$TREATMENT" \
  "historical_source=$HISTORICAL_SOURCE" "image=$IMG" \
  "code_sha=$CODE_SHA" "active_cache=$ACTIVE_TABLE" \
  "fitted_k=28.154043586960896" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "active_selection_sha256=$(sha256sum "$ACTIVE_SELECTION" | awk '{print $1}')" \
  "usage_selection_sha256=$(sha256sum "$USAGE_SELECTION" | awk '{print $1}')" \
  "final_report_sha256=$(sha256sum "$FINAL_REPORT" | awk '{print $1}')" \
  > "$OUT/revalidation_manifest.txt"
echo "ACTIVE_LABEL_USAGE_REVALIDATION_LAUNCHED control=$CONTROL treatment=$TREATMENT"
