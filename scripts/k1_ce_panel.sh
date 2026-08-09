#!/bin/bash
# Frozen corrected K=1 cross-entropy panel.
#
# Usage:
#   bash scripts/k1_ce_panel.sh union <IMAGE@sha256:...> <CODE_SHA>
#   bash scripts/k1_ce_panel.sh fixed <IMAGE@sha256:...> <CODE_SHA>
#
# The union diagnostic adds 12 CE solves without removing boom solves.  It is
# intentionally not adoptable.  The fixed arm is launchable only after the
# tracked union comparison passes its preregistered candidate-frontier gate;
# it replaces 12 boom solves with 12 CE solves and caps every slate to the
# accepted source panel's realized pool size.
set -euo pipefail

MODE=${1:-}
IMG=${2:-}
CODE_SHA=${3:-}
PROJECT=nfl-predictions-503414
SOURCE=20260808-e80-k1-c616390
UNION=20260809-e80-k1-ceunion-c616390
FIXED=20260809-e80-k1-ce12-c616390
SEED=1701
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
print("accepted source contract verified: 107 slates")
PY

if [ "$MODE" = union ]; then
  OUT="$ROOT/reports/panel-runs/$UNION"
  [ ! -e "$OUT/executions.txt" ] || {
    echo "ABORT: immutable union panel already launched"; exit 2; }
  PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
  PANEL_ARM_LABEL=k1_ce_union PANEL_ARM_ENV="MODEL_ENSEMBLE=1|CE_SEED=$SEED" \
  PANEL_N_ENTRIES=80 PANEL_N_CE=12 PANEL_N_EPISTEMIC=0 \
  PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 \
  bash "$ROOT/scripts/baseline_panel.sh" "$IMG" e80k1ceu "$UNION"
  echo "K1_CE_UNION_LAUNCHED panel=$UNION"
  exit 0
fi

# Fixed replacement may use union outcomes only through this frozen binary
# gate.  It must never be launched because a human eyeballed partial logs.
UNION_REPORT="$ROOT/reports/panel-runs/$UNION/ce_comparison_v2.json"
[ -s "$UNION_REPORT" ] || {
  echo "ABORT: union comparison is absent: $UNION_REPORT"; exit 2; }
"$ROOT/.venv/bin/python" - "$UNION_REPORT" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
gate = report.get("union_gate", {})
if report.get("failures") or not gate.get("passes"):
    raise SystemExit("ABORT: preregistered union gate did not pass")
print("union mechanism/frontier gate passed")
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
PANEL_ARM_LABEL=k1_ce_fixed \
PANEL_ARM_ENV="MODEL_ENSEMBLE=1|CE_SEED=$SEED|GEN_POOL_CAP_MAP=$CAP_MAP|REPLACEMENT_SLOTS=12" \
PANEL_N_ENTRIES=80 PANEL_N_CE=12 PANEL_N_EPISTEMIC=0 \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=28 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" e80k1cef "$FIXED"
echo "K1_CE_FIXED_LAUNCHED panel=$FIXED"
