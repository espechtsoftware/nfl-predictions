#!/bin/bash
# Check a frozen active-label exact-80 partial panel. Research panels are never
# promoted directly; a passing treatment requires canonical cache regeneration.
# Usage: cloud_accept_tabpfn_active_label_exact80.sh <IMAGE@sha256:...> control|treatment
set -euo pipefail

IMG=${1:-}
ARM=${2:-}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
case "$ARM" in
  control) PANEL=20260811-lockfix-e80-k1-tabpfn-current-label-v1 ;;
  treatment) PANEL=20260811-lockfix-e80-k1-tabpfn-active-label-v1 ;;
  *) echo "ABORT: arm must be control or treatment"; exit 2 ;;
esac
bash "$ROOT/scripts/cloud_accept_panel.sh" \
  "$IMG" "$PANEL" check 80 2 "2023 2024 2025" season-varying-config
