#!/bin/bash
# Accept K3, audit K1, compare, and promote only the selected PIT-clean base.
# Usage: cloud_finish_pit_tier1_controls.sh <AUDIT_IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
K3=20260811-pitclean-e80-k3-a12ab31
K1=20260811-pitclean-e80-k1-a12ab31
OUT="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-controls-v2"
case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
[ ! -e "$OUT/selected_base.txt" ] || { echo "ABORT: selection exists"; exit 2; }
mkdir -p "$OUT"

bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$K3" check 80 2
bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$K3" promote 80 2
bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$K1" check 80 2
bash "$ROOT/scripts/cloud_compare_pit_tier1.sh" \
  "$IMG" "$K3" "$K1" ensemble a12ab31
REPORT="$ROOT/reports/panel-runs/$K1/pit_tier1_comparison.json"
SELECTED=$("$ROOT/.venv/bin/python" - "$REPORT" "$K3" "$K1" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") != "valid" or report.get("failures"):
    raise SystemExit("ABORT: Tier-1 control comparison invalid")
selected = report.get("selected_panel")
if selected not in {sys.argv[2], sys.argv[3]}:
    raise SystemExit("ABORT: selected panel is not a registered control")
print("k1" if selected == sys.argv[3] else "k3")
PY
)
if [ "$SELECTED" = k1 ]; then
  bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$K1" promote 80 2
fi
printf '%s\n' \
  "selected_base=$SELECTED" \
  "selected_panel=$([ "$SELECTED" = k1 ] && echo "$K1" || echo "$K3")" \
  "comparison_sha256=$(sha256sum "$REPORT" | awk '{print $1}')" \
  > "$OUT/selected_base.txt"
echo "PIT_TIER1_BASE_SELECTED $SELECTED"
