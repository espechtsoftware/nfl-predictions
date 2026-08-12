#!/bin/bash
# Launch frozen PIT-clean exact-80 controls or the selected direct-role branch.
# Usage:
#   pit_tier1_panel.sh controls <GENERATION_IMAGE@sha256:...> a12ab31
#   pit_tier1_panel.sh role <GENERATION_IMAGE@sha256:...> a12ab31 k3|k1
set -euo pipefail

MODE=${1:-}
IMG=${2:-}
CODE_SHA=${3:-}
BASE=${4:-}
PROJECT=nfl-predictions-503414
ROOT=$(cd "$(dirname "$0")/.." && pwd)
FROZEN_DIGEST=sha256:ad50fe19bde366ca11180b561127b09e2c79c97ec7dbbd5507282e33d2d5eb62
K3=20260811-pitclean-e80-k3-a12ab31
K1=20260811-pitclean-e80-k1-a12ab31
K3_ROLE=20260811-pitclean-e80-k3-role12union-a12ab31
K1_ROLE=20260811-pitclean-e80-k1-role12union-a12ab31
CACHE=tabpfn_projections_pit_v2
CACHE_VALIDATION="$ROOT/reports/tabpfn-canonical-runs/20260811-tabpfn-canonical-pit-v2/validation.json"
REGISTRY_VALIDATION="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-registry-v2/validation.json"
SELECTION="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-controls-v2/selected_base.txt"

case "$MODE" in controls|role) ;; *) echo "ABORT: mode is controls or role"; exit 2;; esac
case "$IMG" in *@"$FROZEN_DIGEST") ;; *) echo "ABORT: wrong generation digest"; exit 2;; esac
[ "$CODE_SHA" = a12ab31 ] || { echo "ABORT: generation code is a12ab31"; exit 2; }
for path in "$CACHE_VALIDATION" "$REGISTRY_VALIDATION"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
"$ROOT/.venv/bin/python" - "$CACHE_VALIDATION" "$REGISTRY_VALIDATION" <<'PY'
import json
import sys

cache = json.load(open(sys.argv[1], encoding="utf-8"))
registry = json.load(open(sys.argv[2], encoding="utf-8"))
if cache.get("disposition") != "tabpfn-canonical-pit-cache-valid" or not cache.get("passes"):
    raise SystemExit("ABORT: canonical cache is not valid")
if registry.get("disposition") != "pit-clean-registry-qualified" or not registry.get("passes"):
    raise SystemExit("ABORT: isolated registries are not qualified")
PY

launch() {
  local family=$1 panel=$2 label=$3 env=$4 n_epi=$5
  PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
  PANEL_ARM_LABEL="$label" PANEL_ARM_ENV="$env" \
  PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC="$n_epi" \
  PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 PANEL_SMOKE_SEASON=2024 \
  PANEL_TASK_TIMEOUT=14400 \
  bash "$ROOT/scripts/baseline_panel.sh" "$IMG" "$family" "$panel"
}

COMMON="TABPFN_MARGINALS=1|TABPFN_MARGINAL_TABLE=$CACHE"
if [ "$MODE" = controls ]; then
  [ -z "$BASE" ] || { echo "ABORT: controls takes no base branch"; exit 2; }
  launch pitk3 "$K3" pit_clean_k3 "$COMMON" 0
  launch pitk1 "$K1" pit_clean_k1 "$COMMON|MODEL_ENSEMBLE=1" 0
  echo "PIT_TIER1_CONTROLS_LAUNCHED k3=$K3 k1=$K1"
  exit 0
fi

case "$BASE" in k3|k1) ;; *) echo "ABORT: role base is k3 or k1"; exit 2;; esac
[ -s "$SELECTION" ] || { echo "ABORT: selected base record missing"; exit 2; }
SELECTED=$(awk -F= '$1=="selected_base" {print $2}' "$SELECTION")
[ "$SELECTED" = "$BASE" ] || {
  echo "ABORT: requested $BASE but mechanical selection is $SELECTED"; exit 2; }
if [ "$BASE" = k3 ]; then
  SOURCE=$K3
  PANEL=$K3_ROLE
  FAMILY=pitk3role
  ENV=$COMMON
else
  SOURCE=$K1
  PANEL=$K1_ROLE
  FAMILY=pitk1role
  ENV="$COMMON|MODEL_ENSEMBLE=1"
fi
COUNT=$(bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
  "SELECT COUNT(DISTINCT CONCAT(CAST(season AS STRING), '-', CAST(week AS STRING))) AS n
   FROM \`$PROJECT.nfl_predictions.replay_candidates\`
   WHERE panel_run_id='$SOURCE' AND research_eligible AND code_sha='$CODE_SHA'" \
  | tail -1 | tr -d '[:space:]')
[ "$COUNT" = 107 ] || { echo "ABORT: selected source has $COUNT slates"; exit 2; }
ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
ENV="$ENV|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES|ROLE_BELIEF_SEED=7331|REPLACEMENT_SLOTS=12"
launch "$FAMILY" "$PANEL" "pit_clean_${BASE}_role12_union" "$ENV" 12
echo "PIT_TIER1_ROLE_LAUNCHED base=$BASE source=$SOURCE panel=$PANEL"
