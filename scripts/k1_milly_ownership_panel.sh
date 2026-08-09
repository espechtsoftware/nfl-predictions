#!/bin/bash
# Frozen true-80 K=1 contest-aware Milly ownership fade arm.
# Usage: k1_milly_ownership_panel.sh <IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DIAG="$ROOT/reports/ownership-runs/20260809-milly-k1-c616390-v4/report.json"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2 ;; esac
case "$CODE_SHA" in ""|*[!0-9a-f]*) echo "ABORT: CODE_SHA must be hexadecimal"; exit 2 ;; esac
LOCAL_SHA=$(git -C "$ROOT" rev-parse HEAD)
[ "$CODE_SHA" = "$LOCAL_SHA" ] || {
  echo "ABORT: CODE_SHA $CODE_SHA is not local HEAD $LOCAL_SHA"; exit 2; }
[ -s "$DIAG" ] || { echo "ABORT: corrected ownership diagnostic absent"; exit 2; }
"$ROOT/.venv/bin/python" - "$DIAG" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") != "pass" or not report.get("gate", {}).get("passes"):
    raise SystemExit("ABORT: corrected ownership diagnostic did not pass")
if report.get("data_contract", {}).get("scope_eligible_contests") != 71:
    raise SystemExit("ABORT: corrected ownership scope contract is not 71")
print("corrected contest-aware ownership gate passed")
PY

SHORT=${CODE_SHA:0:7}
PANEL_ID="20260809-e80-k1-millyown-$SHORT"
OUT="$ROOT/reports/panel-runs/$PANEL_ID"
[ ! -e "$OUT/executions.txt" ] || {
  echo "ABORT: immutable ownership panel already launched"; exit 2; }

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_ARM_LABEL=k1_milly_ownership \
PANEL_ARM_ENV="MODEL_ENSEMBLE=1|OWN_MODEL=milly_fade" \
PANEL_SMOKE_SEASON=2023 \
PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC=0 \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" e80k1milly "$PANEL_ID"
echo "K1_MILLY_OWNERSHIP_PANEL_LAUNCHED panel=$PANEL_ID"
