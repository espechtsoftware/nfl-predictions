#!/bin/bash
# Record canonical current-label fallback after a failed v2 final-served gate.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
TIER1="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-role-v2/selected_tier1.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"
FINAL_REPORT="$ROOT/reports/tabpfn-active-label-runs/20260811-tabpfn-active-label-final-served-v2-pit-clean/report.json"
OUT="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean"
for path in "$TIER1" "$USAGE" "$FINAL_REPORT"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/selected_active_label.txt" ] || { echo "ABORT: immutable active-label selection exists"; exit 2; }
"$ROOT/.venv/bin/python" - "$FINAL_REPORT" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") == "tabpfn-active-label-final-served-passes" or report.get("gate", {}).get("passes"):
    raise SystemExit("ABORT: passing final-served gate requires exact-80 comparison")
if not report.get("disposition") or not report.get("gate"):
    raise SystemExit("ABORT: repaired active-label report is incomplete")
PY
SOURCE=$(awk -F= '$1=="selected_panel" {print $2}' "$TIER1")
ROLE_SELECTED=$(awk -F= '$1=="role_selected" {print $2}' "$TIER1")
ALLOCATION=$(awk -F= '$1=="allocation" {print $2}' "$USAGE")
SELECTED_K=$(awk -F= '$1=="selected_k" {print $2}' "$USAGE")
mkdir -p "$OUT"
printf '%s\n' \
  "historical_source=$SOURCE" "role_selected=$ROLE_SELECTED" \
  "allocation=$ALLOCATION" "selected_k=$SELECTED_K" \
  'label_law=current' 'cache_table=tabpfn_projections_pit_v2' \
  "selected_eval_panel=$SOURCE" \
  'selection_reason=final-served-gate-failed' \
  "final_served_report_sha256=$(sha256sum "$FINAL_REPORT" | awk '{print $1}')" \
  > "$OUT/selected_active_label.txt"
echo "PIT_ACTIVE_LABEL_FALLBACK_SELECTED current"
