#!/bin/bash
# Record the preregistered identity-position fallback after a failed refit gate.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
TIER1="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-role-v2/selected_tier1.txt"
CALIBRATION="$ROOT/reports/served-position-calibration-runs/20260812-served-position-calibration-v2-pit-clean/report.json"
OUT="$ROOT/reports/served-position-calibration-runs/20260812-served-position-stage-b-v2-pit-clean"
for path in "$TIER1" "$CALIBRATION"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/selected_position.txt" ] || {
  echo "ABORT: immutable position selection exists"; exit 2; }

"$ROOT/.venv/bin/python" - "$CALIBRATION" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") == "served-position-calibration-passes" or \
        report.get("gate", {}).get("passes"):
    raise SystemExit("ABORT: passing position gate requires Stage B comparison")
if not report.get("disposition") or not report.get("gate"):
    raise SystemExit("ABORT: repaired position report is incomplete")
PY

BASE=$(awk -F= '$1=="selected_base" {print $2}' "$TIER1")
SOURCE=$(awk -F= '$1=="selected_panel" {print $2}' "$TIER1")
ROLE_SELECTED=$(awk -F= '$1=="role_selected" {print $2}' "$TIER1")
case "$BASE" in k1|k3) ;; *) echo "ABORT: invalid selected base"; exit 2;; esac
case "$ROLE_SELECTED" in true|false) ;; *) echo "ABORT: invalid role selection"; exit 2;; esac
[ -n "$SOURCE" ] || { echo "ABORT: selected Tier-1 panel is missing"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "selected_base=$BASE" "source_panel=$SOURCE" \
  "role_selected=$ROLE_SELECTED" 'position_selected=false' \
  "selected_eval_panel=$SOURCE" 'served_position_scales=identity' \
  'selection_reason=calibration-gate-failed' \
  "calibration_sha256=$(sha256sum "$CALIBRATION" | awk '{print $1}')" \
  > "$OUT/selected_position.txt"
echo "PIT_POSITION_FALLBACK_SELECTED $SOURCE"
