#!/bin/bash
# Launch the sole frozen same-image active-label exact-80 control/treatment.
# Usage: prop_lock_tabpfn_active_label_exact80.sh <IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
HISTORICAL_SOURCE=20260810-lockfix-e80-k1-role12union-8677d21
CONTROL=20260811-lockfix-e80-k1-tabpfn-current-label-v1
TREATMENT=20260811-lockfix-e80-k1-tabpfn-active-label-v1
ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
CONTROL_TABLE=tabpfn_active_label_control_v1
TREATMENT_TABLE=tabpfn_active_label_treatment_v1
FINAL_SHA=36982de7412ddd1d77ae92cf7951d42b6a5ea550fe568d2bb279672012c4d2c6
CACHE_SHA=fe72d38634b0036e185ade288429356b74fc5c65ebae1c8f424e926f12aecc01
ROOT=$(cd "$(dirname "$0")/.." && pwd)
FINAL_REPORT="$ROOT/reports/tabpfn-active-label-runs/20260811-tabpfn-active-label-final-served-v1/report.json"
CACHE_VALIDATION="$ROOT/reports/tabpfn-active-label-runs/20260811-tabpfn-active-label-v1/validation.json"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$CODE_SHA" in
  ""|*[!0-9a-f]*) echo "ABORT: exact lowercase hexadecimal code SHA required"; exit 2 ;;
esac
for file in "$FINAL_REPORT" "$CACHE_VALIDATION"; do
  [ -s "$file" ] || { echo "ABORT: prerequisite artifact absent: $file"; exit 2; }
done
[ "$(sha256sum "$FINAL_REPORT" | awk '{print $1}')" = "$FINAL_SHA" ] || {
  echo "ABORT: final-served report hash differs"; exit 2; }
[ "$(sha256sum "$CACHE_VALIDATION" | awk '{print $1}')" = "$CACHE_SHA" ] || {
  echo "ABORT: cache validation hash differs"; exit 2; }
"$ROOT/.venv/bin/python" - "$FINAL_REPORT" "$CACHE_VALIDATION" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
cache = json.load(open(sys.argv[2], encoding="utf-8"))
if report.get("disposition") != "tabpfn-active-label-final-served-passes":
    raise SystemExit("ABORT: final-served disposition is not pass")
if report.get("gate") != {
    "aggregate_calibrated_30_brier_improves": True,
    "maximum_mean_delta_at_most_1e_10": True,
    "passes": True,
}:
    raise SystemExit("ABORT: final-served gate differs")
if report.get("common_usage_law") != {
    "mode": "production-multinomial", "game_sim_usage": "", "k": ""}:
    raise SystemExit("ABORT: common usage law is not production multinomial")
if report.get("cache_rows") != 52307:
    raise SystemExit("ABORT: final-served cache row count differs")
if any(float(report["maximum_mean_delta"][arm]) > 1e-10
       for arm in ("control", "treatment")):
    raise SystemExit("ABORT: final-served mean preservation failed")
if cache.get("disposition") != "tabpfn-active-label-caches-valid" or \
        not cache.get("passes"):
    raise SystemExit("ABORT: prerequisite cache validation did not pass")
expected = {
    "control_schedule": {
        "2023": {"QB": .990, "RB": .995, "TE": .940, "WR": 1.020},
        "2024": {"QB": .910, "RB": .990, "TE": .950, "WR": 1.085},
        "2025": {"QB": .935, "RB": .975, "TE": .945, "WR": 1.090},
    },
    "treatment_schedule": {
        "2023": {"QB": .955, "RB": .985, "TE": .975, "WR": 1.005},
        "2024": {"QB": .895, "RB": .980, "TE": .975, "WR": 1.040},
        "2025": {"QB": .920, "RB": .955, "TE": .955, "WR": 1.030},
    },
}
for schedule, seasons in expected.items():
    got = {season: item["factors"]
           for season, item in report.get(schedule, {}).items()}
    if got != seasons:
        raise SystemExit(f"ABORT: {schedule} differs from frozen factors")
if report.get("cache_tables") != {
    "control": "tabpfn_active_label_control_v1",
    "treatment": "tabpfn_active_label_treatment_v1",
}:
    raise SystemExit("ABORT: final-served cache table identities differ")
print("active-label report hashes, gate, cache tables and schedules verified")
PY

for panel in "$CONTROL" "$TREATMENT"; do
  [ ! -e "$ROOT/reports/panel-runs/$panel/executions.txt" ] || {
    echo "ABORT: immutable panel already launched: $panel"; exit 2; }
done

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
  --max_rows=1000 \
  "SELECT panel_run_id, code_sha, season, week, COUNT(*) AS n
   FROM \`$PROJECT.nfl_predictions.replay_candidates\`
   WHERE panel_run_id = '$HISTORICAL_SOURCE' AND research_eligible
   GROUP BY panel_run_id, code_sha, season, week
   ORDER BY season, week" > "$TMP_DIR/source_counts.csv"
"$ROOT/.venv/bin/python" - "$TMP_DIR/source_counts.csv" <<'PY'
import csv
import sys

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
if len(rows) != 107 or {row["code_sha"] for row in rows} != {"8677d21"}:
    raise SystemExit("ABORT: historical splice source contract differs")
if min(int(row["n"]) for row in rows) < 80:
    raise SystemExit("ABORT: historical source contains an undersized pool")
print("accepted historical 107-slate splice source verified")
PY

COMMON="MODEL_ENSEMBLE=1|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES|ROLE_BELIEF_SEED=7331|REPLACEMENT_SLOTS=12"

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_SEASONS="2023 2024 2025" \
PANEL_ARM_LABEL=lockfix_k1_tabpfn_current_label \
PANEL_ARM_ENV="$COMMON" \
PANEL_ARM_ENV_2023="TABPFN_MARGINAL_TABLE=$CONTROL_TABLE|SERVED_POSITION_SCALES=QB:0.990,RB:0.995,TE:0.940,WR:1.020" \
PANEL_ARM_ENV_2024="TABPFN_MARGINAL_TABLE=$CONTROL_TABLE|SERVED_POSITION_SCALES=QB:0.910,RB:0.990,TE:0.950,WR:1.085" \
PANEL_ARM_ENV_2025="TABPFN_MARGINAL_TABLE=$CONTROL_TABLE|SERVED_POSITION_SCALES=QB:0.935,RB:0.975,TE:0.945,WR:1.090" \
PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC=12 \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 PANEL_SMOKE_SEASON=2024 \
PANEL_TASK_TIMEOUT=14400 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" tapctl "$CONTROL"

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_SEASONS="2023 2024 2025" \
PANEL_ARM_LABEL=lockfix_k1_tabpfn_active_label \
PANEL_ARM_ENV="$COMMON" \
PANEL_ARM_ENV_2023="TABPFN_MARGINAL_TABLE=$TREATMENT_TABLE|SERVED_POSITION_SCALES=QB:0.955,RB:0.985,TE:0.975,WR:1.005" \
PANEL_ARM_ENV_2024="TABPFN_MARGINAL_TABLE=$TREATMENT_TABLE|SERVED_POSITION_SCALES=QB:0.895,RB:0.980,TE:0.975,WR:1.040" \
PANEL_ARM_ENV_2025="TABPFN_MARGINAL_TABLE=$TREATMENT_TABLE|SERVED_POSITION_SCALES=QB:0.920,RB:0.955,TE:0.955,WR:1.030" \
PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC=12 \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 PANEL_SMOKE_SEASON=2024 \
PANEL_TASK_TIMEOUT=14400 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" taptrt "$TREATMENT"

echo "TABPFN_ACTIVE_LABEL_EXACT80_LAUNCHED control=$CONTROL treatment=$TREATMENT"
