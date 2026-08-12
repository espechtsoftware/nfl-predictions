#!/bin/bash
# Retain the incumbent TabPFN law after a failed SCHED final-served gate.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
TIER1="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-role-v2/selected_tier1.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
FINAL="$ROOT/reports/tabpfn-sched-runs/20260812-tabpfn-sched-final-served-v1-pit-clean/report.json"
OUT="$ROOT/reports/tabpfn-sched-runs/20260812-tabpfn-sched-exact80-v1-pit-clean"
for path in "$TIER1" "$USAGE" "$ACTIVE" "$FINAL"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/selected_sched.txt" ] || {
  echo "ABORT: immutable SCHED selection exists"; exit 2; }
"$ROOT/.venv/bin/python" - "$FINAL" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") == "tabpfn-sched-final-served-passes" or \
        report.get("gate", {}).get("passes"):
    raise SystemExit("ABORT: passing SCHED gate requires exact-80 comparison")
if not report.get("disposition") or not report.get("gate"):
    raise SystemExit("ABORT: SCHED final-served report is incomplete")
PY
SOURCE=$(awk -F= '$1=="selected_panel" {print $2}' "$TIER1")
ROLE_SELECTED=$(awk -F= '$1=="role_selected" {print $2}' "$TIER1")
ALLOCATION=$(awk -F= '$1=="allocation" {print $2}' "$USAGE")
SELECTED_K=$(awk -F= '$1=="selected_k" {print $2}' "$USAGE")
LABEL_LAW=$(awk -F= '$1=="label_law" {print $2}' "$ACTIVE")
CACHE_TABLE=$(awk -F= '$1=="cache_table" {print $2}' "$ACTIVE")
mkdir -p "$OUT"
printf '%s\n' \
  "historical_source=$SOURCE" "role_selected=$ROLE_SELECTED" \
  "allocation=$ALLOCATION" "selected_k=$SELECTED_K" \
  "label_law=$LABEL_LAW" 'sched_selected=false' \
  'feature_contract=shared33' "cache_table=$CACHE_TABLE" \
  "selected_eval_panel=$SOURCE" \
  'selection_reason=final-served-gate-failed' \
  "final_served_report_sha256=$(sha256sum "$FINAL" | awk '{print $1}')" \
  > "$OUT/selected_sched.txt"
echo "PIT_SCHED_FALLBACK_SELECTED shared33"
