#!/bin/bash
# Launch the sole frozen same-image fitted-K control and treatment.
# Usage: prop_lock_usage_dirichlet_exact80.sh <IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
HISTORICAL_SOURCE=20260810-lockfix-e80-k1-role12union-8677d21
EVALUATION_SOURCE=20260811-lockfix-e80-k1-role12-position-scales-v1
CONTROL=20260811-lockfix-e80-k1-role12-poscal-usage-control-v1
TREATMENT=20260811-lockfix-e80-k1-role12-poscal-usage-k28246898-v1
ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
POSITION_SPEC=QB:0.970,RB:1.005,TE:0.940,WR:1.070
FITTED_K=28.246898139750336
REPORT_SHA=7fd2a735d22294a9f75469eda4ce5230c9e20b52620bbb0bb0d01e5a478a6996
ROOT=$(cd "$(dirname "$0")/.." && pwd)
FIT_REPORT="$ROOT/reports/usage-dirichlet-calibration-runs/20260811-data-fitted-usage-k-v1/report.json"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$CODE_SHA" in
  ""|*[!0-9a-f]*) echo "ABORT: exact lowercase hexadecimal code SHA required"; exit 2 ;;
esac
[ -s "$FIT_REPORT" ] || { echo "ABORT: fitted-K report absent"; exit 2; }
[ "$(sha256sum "$FIT_REPORT" | awk '{print $1}')" = "$REPORT_SHA" ] || {
  echo "ABORT: fitted-K report hash differs"; exit 2; }
"$ROOT/.venv/bin/python" - "$FIT_REPORT" "$FITTED_K" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
expected = float(sys.argv[2])
if report.get("disposition") != "data-fitted-usage-concentration-passes":
    raise SystemExit("ABORT: fitted-K diagnostic did not pass")
if not report.get("gate", {}).get("passes"):
    raise SystemExit("ABORT: fitted-K gate is false")
if report.get("fit", {}).get("selected_k") != expected:
    raise SystemExit("ABORT: selected K differs from frozen value")
for season in ("2021", "2022", "2023", "2024", "2025"):
    for kind in ("targets", "carries"):
        coverage = report["population"][season][kind]["opportunity_coverage"]
        if coverage != 1.0:
            raise SystemExit(f"ABORT: coverage differs for {season} {kind}")
print("fitted-K report hash, gate, value and coverage verified")
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
   WHERE panel_run_id IN ('$HISTORICAL_SOURCE', '$EVALUATION_SOURCE')
     AND research_eligible
   GROUP BY panel_run_id, code_sha, season, week
   ORDER BY panel_run_id, season, week" > "$TMP_DIR/source_counts.csv"
"$ROOT/.venv/bin/python" - "$TMP_DIR/source_counts.csv" \
  "$HISTORICAL_SOURCE" "$EVALUATION_SOURCE" <<'PY'
import csv
import sys

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
historical = [row for row in rows if row["panel_run_id"] == sys.argv[2]]
evaluation = [row for row in rows if row["panel_run_id"] == sys.argv[3]]
if len(historical) != 107 or {row["code_sha"] for row in historical} != {"8677d21"}:
    raise SystemExit("ABORT: historical splice source contract differs")
if len(evaluation) != 54 or {row["code_sha"] for row in evaluation} != {"d86e4f6"}:
    raise SystemExit("ABORT: position-scale evaluation source contract differs")
if min(int(row["n"]) for row in historical + evaluation) < 80:
    raise SystemExit("ABORT: accepted source contains an undersized pool")
print("accepted historical 107-slate and evaluation 54-slate sources verified")
PY

COMMON="MODEL_ENSEMBLE=1|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES|ROLE_BELIEF_SEED=7331|REPLACEMENT_SLOTS=12|SERVED_POSITION_SCALES=$POSITION_SPEC"

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_SEASONS="2023 2024 2025" \
PANEL_ARM_LABEL=lockfix_k1_role12_poscal_usage_control \
PANEL_ARM_ENV="$COMMON" \
PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC=12 \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 PANEL_SMOKE_SEASON=2024 \
PANEL_TASK_TIMEOUT=14400 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" lockk1ukctl "$CONTROL"

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_SEASONS="2023 2024 2025" \
PANEL_ARM_LABEL=lockfix_k1_role12_poscal_usage_k28246898 \
PANEL_ARM_ENV="$COMMON|GAME_SIM_USAGE=dirichlet|DIRICHLET_K=$FITTED_K" \
PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC=12 \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 PANEL_SMOKE_SEASON=2024 \
PANEL_TASK_TIMEOUT=14400 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" lockk1uktrt "$TREATMENT"

echo "USAGE_DIRICHLET_EXACT80_LAUNCHED control=$CONTROL treatment=$TREATMENT"
