#!/bin/bash
# Validate the mechanically selected base's role union, compare it under the
# frozen tail-first law, and promote it only when the comparison selects it.
# Usage: cloud_finish_pit_tier1_role.sh <AUDIT_IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
K3=20260811-pitclean-e80-k3-a12ab31
K1=20260811-pitclean-e80-k1-a12ab31
K3_ROLE=20260811-pitclean-e80-k3-role12union-a12ab31
K1_ROLE=20260811-pitclean-e80-k1-role12union-a12ab31
CONTROL_OUT="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-controls-v2"
OUT="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-role-v2"
SELECTION="$CONTROL_OUT/selected_base.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
[ -s "$SELECTION" ] || { echo "ABORT: selected base record missing"; exit 2; }
[ ! -e "$OUT/selected_tier1.txt" ] || { echo "ABORT: Tier-1 selection exists"; exit 2; }

BASE=$(awk -F= '$1=="selected_base" {print $2}' "$SELECTION")
case "$BASE" in
  k3) SOURCE=$K3; TREATMENT=$K3_ROLE ;;
  k1) SOURCE=$K1; TREATMENT=$K1_ROLE ;;
  *) echo "ABORT: invalid selected base '$BASE'"; exit 2 ;;
esac

mkdir -p "$OUT"
bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$TREATMENT" check 80 2
bash "$ROOT/scripts/cloud_compare_pit_tier1.sh" \
  "$IMG" "$SOURCE" "$TREATMENT" direct-role a12ab31
REPORT="$ROOT/reports/panel-runs/$TREATMENT/pit_tier1_comparison.json"
SELECTED=$("$ROOT/.venv/bin/python" - "$REPORT" "$SOURCE" "$TREATMENT" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") != "valid" or report.get("failures"):
    raise SystemExit("ABORT: Tier-1 role comparison invalid")
selected = report.get("selected_panel")
if selected not in {sys.argv[2], sys.argv[3]}:
    raise SystemExit("ABORT: selected panel is not a registered role branch")
print(selected)
PY
)
if [ "$SELECTED" = "$TREATMENT" ]; then
  bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$TREATMENT" promote 80 2
fi
printf '%s\n' \
  "selected_base=$BASE" \
  "source_panel=$SOURCE" \
  "role_panel=$TREATMENT" \
  "selected_panel=$SELECTED" \
  "role_selected=$([ "$SELECTED" = "$TREATMENT" ] && echo true || echo false)" \
  "comparison_sha256=$(sha256sum "$REPORT" | awk '{print $1}')" \
  > "$OUT/selected_tier1.txt"
echo "PIT_TIER1_FINAL_SELECTED $SELECTED"
