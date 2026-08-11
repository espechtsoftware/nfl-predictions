#!/bin/bash
# Rebuild the frozen true-80 policy chain after the common-lock correction.
#
# Usage:
#   bash scripts/prop_lock_rebaseline.sh controls <IMAGE@sha256:...> 8677d21
#   bash scripts/prop_lock_rebaseline.sh ce       <IMAGE@sha256:...> 8677d21
#   bash scripts/prop_lock_rebaseline.sh role     <IMAGE@sha256:...> 8677d21
#   bash scripts/prop_lock_rebaseline.sh nofloor  <IMAGE@sha256:...> 8677d21
set -euo pipefail

MODE=${1:-}
IMG=${2:-}
CODE_SHA=${3:-}
PROJECT=nfl-predictions-503414
ROOT=$(cd "$(dirname "$0")/.." && pwd)

K3=20260810-lockfix-e80-k3-8677d21
K1=20260810-lockfix-e80-k1-8677d21
CE=20260810-lockfix-e80-k1-ce12-8677d21
ROLE=20260810-lockfix-e80-k1-ce12-roleunion-8677d21
DIRECT_ROLE=20260810-lockfix-e80-k1-role12union-8677d21
NOFLOOR=20260810-lockfix-e80-k1-nofloor-8677d21

case "$MODE" in controls|ce|role|nofloor) ;; *)
  echo "ABORT: mode must be controls, ce, role, or nofloor"; exit 2;;
esac
case "$IMG" in *@sha256:*) ;; *)
  echo "ABORT: immutable image required"; exit 2;;
esac
[ "$CODE_SHA" = 8677d21 ] || {
  echo "ABORT: correction is frozen to generation code 8677d21"; exit 2; }

launch() {
  local family=$1 panel=$2 label=$3 env=$4 n_ce=$5 n_epi=$6 n_boom=$7
  PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
  PANEL_ARM_LABEL="$label" PANEL_ARM_ENV="$env" \
  PANEL_N_ENTRIES=80 PANEL_N_CE="$n_ce" PANEL_N_EPISTEMIC="$n_epi" \
  PANEL_N_GUMBEL=0 PANEL_N_BOOM="$n_boom" \
  PANEL_SMOKE_SEASON=2024 PANEL_TASK_TIMEOUT=14400 \
  bash "$ROOT/scripts/baseline_panel.sh" "$IMG" "$family" "$panel"
}

accepted_counts() {
  local source=$1 output=$2
  bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
    --max_rows=1000 \
    "SELECT season, week, COUNT(*) AS n
     FROM \`$PROJECT.nfl_predictions.replay_candidates\`
     WHERE panel_run_id='$source' AND research_eligible
       AND code_sha='$CODE_SHA'
     GROUP BY season, week ORDER BY season, week" > "$output"
  "$ROOT/.venv/bin/python" - "$output" <<'PY'
import csv
import sys

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
if len(rows) != 107:
    raise SystemExit(f"ABORT: expected 107 accepted source slates, got {len(rows)}")
if min(int(row["n"]) for row in rows) < 80:
    raise SystemExit("ABORT: accepted source contains an undersized pool")
PY
}

if [ "$MODE" = controls ]; then
  launch lockk3 "$K3" lockfix_k3 "" 0 0 40
  launch lockk1 "$K1" lockfix_k1 "MODEL_ENSEMBLE=1" 0 0 40
  echo "PROP_LOCK_CONTROLS_LAUNCHED k3=$K3 k1=$K1"
  exit 0
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

if [ "$MODE" = ce ]; then
  accepted_counts "$K1" "$TMP_DIR/source_counts.csv"
  OUT="$ROOT/reports/panel-runs/$CE"
  mkdir -p "$OUT"
  "$ROOT/.venv/bin/python" - "$TMP_DIR/source_counts.csv" \
    "$OUT/cap_map.json" <<'PY'
import csv
import json
import sys

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
caps = {f"{int(row['season'])}-{int(row['week'])}": int(row["n"])
        for row in rows}
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(caps, handle, sort_keys=True, separators=(",", ":"))
PY
  CAP_MAP=$(tr -d '\n' < "$OUT/cap_map.json")
  launch lockce "$CE" lockfix_k1_ce12 \
    "MODEL_ENSEMBLE=1|CE_SEED=1701|GEN_POOL_CAP_MAP=$CAP_MAP|REPLACEMENT_SLOTS=12" \
    12 0 28
  echo "PROP_LOCK_CE_LAUNCHED panel=$CE source=$K1"
  exit 0
fi

if [ "$MODE" = role ]; then
  accepted_counts "$CE" "$TMP_DIR/source_counts.csv"
  ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
  launch lockrole "$ROLE" lockfix_k1_ce12_role_union \
    "MODEL_ENSEMBLE=1|CE_SEED=1701|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES|ROLE_BELIEF_SEED=7331|REPLACEMENT_SLOTS=12" \
    12 12 28
  echo "PROP_LOCK_ROLE_LAUNCHED panel=$ROLE source=$CE"
  exit 0
fi

# The no-floor source is deliberately sequenced after the corrected role
# source, even though its own generation is an isolated K1 binary ablation.
# This prevents an early score-bearing launch outside the preregistered union
# protocol. The corrected chain selected the direct-role union rather than
# the never-launched CE+role branch, so its accepted rows are the completeness
# prerequisite. They do not affect the independent no-floor generation.
accepted_counts "$DIRECT_ROLE" "$TMP_DIR/source_counts.csv"
launch locknofloor "$NOFLOOR" lockfix_k1_nofloor \
  "MODEL_ENSEMBLE=1|MIN_LINEUP_SALARY=0" 0 0 40
echo "PROP_LOCK_NOFLOOR_LAUNCHED panel=$NOFLOOR source=$DIRECT_ROLE"
