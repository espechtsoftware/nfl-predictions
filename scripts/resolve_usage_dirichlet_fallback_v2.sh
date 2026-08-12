#!/bin/bash
# Record the preregistered multinomial fallback after a failed likelihood gate.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
TIER1="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-role-v2/selected_tier1.txt"
POSITION="$ROOT/reports/served-position-calibration-runs/20260812-served-position-stage-b-v2-pit-clean/selected_position.txt"
FIT_REPORT="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-data-fitted-usage-k-v2-pit-clean/report.json"
OUT="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean"
for path in "$TIER1" "$POSITION" "$FIT_REPORT"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/selected_usage.txt" ] || { echo "ABORT: immutable usage selection exists"; exit 2; }
"$ROOT/.venv/bin/python" - "$FIT_REPORT" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") == "data-fitted-usage-concentration-passes" or report.get("gate", {}).get("passes"):
    raise SystemExit("ABORT: passing likelihood gate requires exact-80 comparison")
if not report.get("disposition") or not report.get("gate"):
    raise SystemExit("ABORT: repaired fitted-K report is incomplete")
PY
BASE=$(awk -F= '$1=="selected_base" {print $2}' "$TIER1")
HISTORICAL_SOURCE=$(awk -F= '$1=="selected_panel" {print $2}' "$TIER1")
ROLE_SELECTED=$(awk -F= '$1=="role_selected" {print $2}' "$TIER1")
POSITION_SELECTED=$(awk -F= '$1=="position_selected" {print $2}' "$POSITION")
POSITION_SPEC=$(awk -F= '$1=="served_position_scales" {print $2}' "$POSITION")
if [ "$POSITION_SELECTED" = true ]; then
  EVALUATION_SOURCE=$(awk -F= '$1=="selected_eval_panel" {print $2}' "$POSITION")
else
  EVALUATION_SOURCE=$HISTORICAL_SOURCE
fi
mkdir -p "$OUT"
printf '%s\n' \
  "selected_base=$BASE" "historical_source=$HISTORICAL_SOURCE" \
  "evaluation_source=$EVALUATION_SOURCE" "role_selected=$ROLE_SELECTED" \
  "position_selected=$POSITION_SELECTED" "served_position_scales=$POSITION_SPEC" \
  'allocation=multinomial' 'selected_k=infinity' \
  "selected_eval_panel=$EVALUATION_SOURCE" \
  'selection_reason=likelihood-gate-failed' \
  "fit_report_sha256=$(sha256sum "$FIT_REPORT" | awk '{print $1}')" \
  > "$OUT/selected_usage.txt"
echo "PIT_USAGE_FALLBACK_SELECTED multinomial"
