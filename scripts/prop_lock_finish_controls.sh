#!/bin/bash
# Accept and compare the complete corrected K3/K1 true-80 controls.
# Usage: bash scripts/prop_lock_finish_controls.sh <IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
K3=20260810-lockfix-e80-k3-8677d21
K1=20260810-lockfix-e80-k1-8677d21

case "$IMG" in *@sha256:*) ;; *)
  echo "ABORT: immutable image required"; exit 2;;
esac

# K3 becomes the canonical source only after independent check mode passes.
bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$K3" check 80 2
bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$K3" promote 80 2

# K1 remains staging until the mechanism-aware comparison and the operator's
# corrected tail-first decision are recorded.
bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$K1" check 80 2
bash "$ROOT/scripts/cloud_compare_adoption_panel.sh" \
  "$IMG" "$K3" "$K1" ensemble 80

echo "PROP_LOCK_CONTROL_COMPARISON_COMPLETE source=$K3 treatment=$K1"
