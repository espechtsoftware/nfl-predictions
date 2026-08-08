#!/bin/bash
# Frozen fixed-budget role-belief panel.
#
# Usage:
#   bash scripts/role_belief_panel.sh \
#     <IMAGE@sha256:...> <CODE_SHA> <FAMILY> <PANEL_PREFIX> [SEED]
#
# A newly accepted, same-image corrected baseline supplies per-slate realized
# pool sizes. Both arms use those FULL sizes: the control must reproduce the
# source baseline exactly, while treatment replaces 12 boom solves with 12
# role-belief solves. Reducing both arms below baseline created an easier but
# nonrepresentative control in the invalid v1 panel and is forbidden here.
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
FAMILY=${3:-}
PREFIX=${4:-}
SEED=${5:-7331}
PROJECT=nfl-predictions-503414
SOURCE_PANEL=${ROLE_CAP_SOURCE_PANEL:-}
ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/panel-runs/$PREFIX"
CONTROL_ID="${PREFIX}-control"
TREATMENT_ID="${PREFIX}-treatment"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2 ;; esac
case "$CODE_SHA" in ""|*[!0-9a-f]*) echo "ABORT: CODE_SHA must be hexadecimal"; exit 2 ;; esac
case "$FAMILY" in ""|*[!a-z0-9]*) echo "ABORT: FAMILY must be lower-case alphanumeric"; exit 2 ;; esac
case "$PREFIX" in ""|*[!A-Za-z0-9_-]*) echo "ABORT: invalid panel prefix"; exit 2 ;; esac
case "$SEED" in ""|*[!0-9]*) echo "ABORT: seed must be an integer"; exit 2 ;; esac
[ -n "$SOURCE_PANEL" ] || {
  echo "ABORT: ROLE_CAP_SOURCE_PANEL must name the accepted same-image baseline"; exit 2; }
case "$SOURCE_PANEL" in
  *[!A-Za-z0-9_-]*) echo "ABORT: invalid ROLE_CAP_SOURCE_PANEL"; exit 2 ;;
esac
[ ! -e "$OUT/cap_map.json" ] || {
  echo "ABORT: immutable role panel manifest already exists at $OUT"; exit 2; }
mkdir -p "$OUT"

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
  --max_rows=1000 \
  "SELECT season, week, COUNT(*) AS n
   FROM \`$PROJECT.nfl_predictions.replay_candidates\`
   WHERE panel_run_id='$SOURCE_PANEL' AND research_eligible
     AND code_sha='$CODE_SHA'
   GROUP BY season, week ORDER BY season, week" > "$TMP_DIR/source_counts.csv"

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
    raise SystemExit(f"ABORT: unsafe cap range {min(caps.values())}-{max(caps.values())}")
with open(sys.argv[2], "w", encoding="utf-8") as fh:
    json.dump(caps, fh, sort_keys=True, separators=(",", ":"))
print(f"frozen {len(caps)} caps, range {min(caps.values())}-{max(caps.values())}")
PY

CAP_MAP=$(tr -d '\n' < "$OUT/cap_map.json")
printf 'image=%s\ncode_sha=%s\nsource_panel=%s\ncontrol=%s\ntreatment=%s\nseed=%s\nrole_features=%s\nreplacement_slots=12\n' \
  "$IMG" "$CODE_SHA" "$SOURCE_PANEL" "$CONTROL_ID" "$TREATMENT_ID" \
  "$SEED" "$ROLE_FEATURES" > "$OUT/manifest.txt"

COMMON_ENV="EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES|ROLE_BELIEF_SEED=$SEED|GEN_POOL_CAP_MAP=$CAP_MAP|REPLACEMENT_SLOTS=12"

echo "Launching equal-compute control (40 boom; role model computed but unused)."
PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_ARM_LABEL=role_belief_control PANEL_ARM_ENV="$COMMON_ENV" \
PANEL_N_CE=0 PANEL_N_EPISTEMIC=0 PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" "${FAMILY}c" "$CONTROL_ID"

echo "Launching treatment (28 boom + 12 role-belief candidates)."
PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_ARM_LABEL=role_belief_treatment PANEL_ARM_ENV="$COMMON_ENV" \
PANEL_N_CE=0 PANEL_N_EPISTEMIC=12 PANEL_N_GUMBEL=0 PANEL_N_BOOM=28 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" "${FAMILY}t" "$TREATMENT_ID"

printf '%s\n%s\n' "$CONTROL_ID" "$TREATMENT_ID" > "$OUT/panels.txt"
echo "ROLE_BELIEF_PANEL_LAUNCHED control=$CONTROL_ID treatment=$TREATMENT_ID"
