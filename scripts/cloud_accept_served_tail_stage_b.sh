#!/bin/bash
# Run the exact 2023--2025 Stage B acceptance contract.
# Usage: cloud_accept_served_tail_stage_b.sh <IMAGE@sha256:...> check|promote
set -euo pipefail

IMG=${1:-}
MODE=${2:-check}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PANEL=20260811-lockfix-e80-k1-role12-tail1025-v1

case "$MODE" in check|promote) ;; *) echo "ABORT: mode is check or promote"; exit 2;; esac
bash "$ROOT/scripts/cloud_accept_panel.sh" \
  "$IMG" "$PANEL" "$MODE" 80 2 "2023 2024 2025"
