#!/bin/bash
# Frozen corrected K=1 + CE role-belief candidate panel.
#
# Usage:
#   bash scripts/k1_role_belief_panel.sh union <IMAGE@sha256:...> <CODE_SHA>
#   bash scripts/k1_role_belief_panel.sh fixed <IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

MODE=${1:-}
IMG=${2:-}
CODE_SHA=${3:-}
PROJECT=nfl-predictions-503414
SOURCE=20260809-e80-k1-ce12-c616390
UNION=20260810-e80-k1-ce12-roleunion-c616390
FIXED=20260810-e80-k1-ce12-role12-c616390
SEED=7331
CE_SEED=1701
ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
ROOT=$(cd "$(dirname "$0")/.." && pwd)

case "$MODE" in union|fixed) ;; *) echo "ABORT: mode must be union or fixed"; exit 2 ;; esac
case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2 ;; esac
case "$CODE_SHA" in ""|*[!0-9a-f]*) echo "ABORT: CODE_SHA must be hexadecimal"; exit 2 ;; esac
[ "$CODE_SHA" = c616390 ] || {
  echo "ABORT: preregistration requires generation code c616390"; exit 2; }

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
  --max_rows=1000 \
  "SELECT season, week, COUNT(*) AS n
   FROM \`$PROJECT.nfl_predictions.replay_candidates\`
   WHERE panel_run_id='$SOURCE' AND research_eligible
     AND code_sha='$CODE_SHA'
   GROUP BY season, week ORDER BY season, week" > "$TMP_DIR/source_counts.csv"
"$ROOT/.venv/bin/python" - "$TMP_DIR/source_counts.csv" <<'PY'
import csv
import sys

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
if len(rows) != 107:
    raise SystemExit(f"ABORT: expected 107 accepted source slates, got {len(rows)}")
if min(int(row["n"]) for row in rows) < 80:
    raise SystemExit("ABORT: accepted source contains an undersized pool")
print("accepted K1 CE source contract verified: 107 slates")
PY

COMMON="MODEL_ENSEMBLE=1|CE_SEED=$CE_SEED|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES|ROLE_BELIEF_SEED=$SEED|REPLACEMENT_SLOTS=12"

if [ "$MODE" = union ]; then
  OUT="$ROOT/reports/panel-runs/$UNION"
  [ ! -e "$OUT/executions.txt" ] || {
    echo "ABORT: immutable union panel already launched"; exit 2; }
  PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
  PANEL_ARM_LABEL=k1_ce_role_union PANEL_ARM_ENV="$COMMON" \
  PANEL_N_ENTRIES=80 PANEL_N_CE=12 PANEL_N_EPISTEMIC=12 \
  PANEL_N_GUMBEL=0 PANEL_N_BOOM=28 \
  bash "$ROOT/scripts/baseline_panel.sh" "$IMG" e80k1ru "$UNION"
  echo "K1_ROLE_UNION_LAUNCHED panel=$UNION"
  exit 0
fi

UNION_REPORT="$ROOT/reports/panel-runs/$UNION/role_comparison.json"
[ -s "$UNION_REPORT" ] || {
  echo "ABORT: union comparison is absent: $UNION_REPORT"; exit 2; }
"$ROOT/.venv/bin/python" - "$UNION_REPORT" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
gate = report.get("union_gate", {})
if report.get("failures") or not gate.get("passes"):
    raise SystemExit("ABORT: preregistered role union gate did not pass")
print("role union mechanism/frontier gate passed")
PY

OUT="$ROOT/reports/panel-runs/$FIXED"
[ ! -e "$OUT/executions.txt" ] || {
  echo "ABORT: immutable fixed panel already launched"; exit 2; }
mkdir -p "$OUT"
"$ROOT/.venv/bin/python" - "$TMP_DIR/source_counts.csv" "$OUT/cap_map.json" <<'PY'
import csv
import json
import sys

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
if len(rows) != 107:
    raise SystemExit(f"ABORT: expected 107 source slates, got {len(rows)}")
caps = {f"{int(r['season'])}-{int(r['week'])}": int(r["n"])
        for r in rows}
if min(caps.values()) < 80:
    raise SystemExit(
        f"ABORT: unsafe cap range {min(caps.values())}-{max(caps.values())}")
with open(sys.argv[2], "w", encoding="utf-8") as fh:
    json.dump(caps, fh, sort_keys=True, separators=(",", ":"))
print(f"frozen {len(caps)} caps, range {min(caps.values())}-{max(caps.values())}")
PY
CAP_MAP=$(tr -d '\n' < "$OUT/cap_map.json")

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_ARM_LABEL=k1_ce_role_fixed \
PANEL_ARM_ENV="$COMMON|GEN_POOL_CAP_MAP=$CAP_MAP" \
PANEL_N_ENTRIES=80 PANEL_N_CE=12 PANEL_N_EPISTEMIC=12 \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=16 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" e80k1rf "$FIXED"
echo "K1_ROLE_FIXED_LAUNCHED panel=$FIXED"
