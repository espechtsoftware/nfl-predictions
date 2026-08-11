#!/bin/bash
# Check or promote a frozen fitted-K exact-80 partial panel.
# Usage: cloud_accept_usage_dirichlet_exact80.sh <IMAGE@sha256:...> control|treatment check|promote
set -euo pipefail

IMG=${1:-}
ARM=${2:-}
MODE=${3:-check}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CONTROL=20260811-lockfix-e80-k1-role12-poscal-usage-control-v1
TREATMENT=20260811-lockfix-e80-k1-role12-poscal-usage-k28246898-v1

case "$ARM" in
  control) PANEL=$CONTROL ;;
  treatment) PANEL=$TREATMENT ;;
  *) echo "ABORT: arm must be control or treatment"; exit 2 ;;
esac
case "$MODE" in check|promote) ;; *) echo "ABORT: mode is check or promote"; exit 2;; esac
if [ "$MODE" = promote ]; then
  [ "$ARM" = treatment ] || { echo "ABORT: never promote fitted-K control"; exit 2; }
  REPORT="$ROOT/reports/panel-runs/$TREATMENT/usage_dirichlet_exact80_comparison.json"
  [ -s "$REPORT" ] || { echo "ABORT: fitted-K comparison report absent"; exit 2; }
  "$ROOT/.venv/bin/python" - "$REPORT" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") != "pass":
    raise SystemExit("ABORT: fitted-K treatment did not pass")
if not report.get("tail_first_decision", {}).get("passes"):
    raise SystemExit("ABORT: fitted-K tail-first decision is not pass")
PY
fi
bash "$ROOT/scripts/cloud_accept_panel.sh" \
  "$IMG" "$PANEL" "$MODE" 80 2 "2023 2024 2025"
