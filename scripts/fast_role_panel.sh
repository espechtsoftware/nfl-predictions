#!/bin/bash
# Frozen fast-role-state treatment. Uses the audited baseline harness so image,
# execution-id, preflight, persistence, and boom-only controls are identical.
set -euo pipefail

[ "$#" -eq 3 ] || {
  echo "usage: $0 <IMAGE@sha256:...> <FAMILY> <PANEL_RUN_ID>"; exit 2; }

export PANEL_ALLOW_TREATMENT=1
export PANEL_ARM_LABEL=fast_role_v1
export PANEL_ARM_ENV='EXTRA_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump'

exec bash "$(dirname "$0")/baseline_panel.sh" "$1" "$2" "$3"
