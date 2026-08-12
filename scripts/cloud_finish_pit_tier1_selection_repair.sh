#!/bin/bash
# Complete base selection after the registered comparator packaging repair.
# Usage: cloud_finish_pit_tier1_selection_repair.sh <REPAIRED_AUDIT_IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
K3=20260811-pitclean-e80-k3-a12ab31
K1=20260811-pitclean-e80-k1-a12ab31
REPORT="$ROOT/reports/panel-runs/$K1/pit_tier1_comparison.json"
OUT="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-controls-v2"
case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable repaired audit image required"; exit 2;; esac
[ -s "$REPORT" ] || { echo "ABORT: repaired comparison report missing"; exit 2; }
[ ! -e "$OUT/selected_base.txt" ] || { echo "ABORT: selection exists"; exit 2; }
SELECTED=$("$ROOT/.venv/bin/python" - "$REPORT" "$K3" "$K1" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") != "valid" or report.get("failures"):
    raise SystemExit("ABORT: repaired Tier-1 comparison invalid")
selected = report.get("selected_panel")
if selected not in {sys.argv[2], sys.argv[3]}:
    raise SystemExit("ABORT: selected panel is not a frozen control")
print("k1" if selected == sys.argv[3] else "k3")
PY
)
if [ "$SELECTED" = k1 ]; then
  bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$K1" promote 80 2
fi
mkdir -p "$OUT"
printf '%s\n' \
  "selected_base=$SELECTED" \
  "selected_panel=$([ "$SELECTED" = k1 ] && echo "$K1" || echo "$K3")" \
  "comparison_sha256=$(sha256sum "$REPORT" | awk '{print $1}')" \
  'supersedes_failed_comparator=compare-pit-tier1-ensemble-x8nkn' \
  > "$OUT/selected_base.txt"
echo "PIT_TIER1_BASE_SELECTED $SELECTED"
