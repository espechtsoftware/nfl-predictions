#!/bin/bash
# Launch the one preregistered coverage-fit union after Route chooses source.
# Usage: prop_lock_coverage_tail_union.sh <IMAGE@sha256:...> d977d0c \
#   <direct|route>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
SOURCE_MODE=${3:-}
PROJECT=nfl-predictions-503414
DIRECT=20260810-lockfix-e80-k1-role12union-8677d21
ROUTE=20260810-lockfix-e80-k1-role12-route12-aa087b8
ROUTE_REPORT=reports/route-tail-union-runs/20260810-fp-route-tail-union-v1/report.json
ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
ROOT=$(cd "$(dirname "$0")/.." && pwd)

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
[ "$CODE_SHA" = d977d0c ] || {
  echo "ABORT: coverage generator is frozen to code d977d0c"; exit 2; }
[ -s "$ROOT/$ROUTE_REPORT" ] || {
  echo "ABORT: Route disposition is not recorded"; exit 2; }
ROUTE_DISPOSITION=$(jq -r '.disposition' "$ROOT/$ROUTE_REPORT")

case "$SOURCE_MODE" in
  direct)
    [ "$ROUTE_DISPOSITION" = keep-corrected-incumbent ] || {
      echo "ABORT: direct source conflicts with Route disposition"; exit 2; }
    SOURCE=$DIRECT
    PANEL=20260810-lockfix-e80-k1-role12-cov12-d977d0c
    FAMILY=lockk1cov
    LABEL=lockfix_k1_role12_cov12
    PAID_ENV=N_COVERAGE_TAIL=12
    ;;
  route)
    [ "$ROUTE_DISPOSITION" = promote-route-tail-union ] || {
      echo "ABORT: Route source conflicts with Route disposition"; exit 2; }
    SOURCE=$ROUTE
    PANEL=20260810-lockfix-e80-k1-role12-route12-cov12-d977d0c
    FAMILY=lockk1routecov
    LABEL=lockfix_k1_role12_route12_cov12
    PAID_ENV='N_ROUTE_TAIL=12|N_COVERAGE_TAIL=12'
    ;;
  *) echo "ABORT: source mode must be direct or route"; exit 2;;
esac

SOURCE_DIR="$ROOT/reports/panel-runs/$SOURCE"
grep -q 'ACCEPTANCE PASSED' "$SOURCE_DIR/acceptance_promote.txt" || {
  echo "ABORT: selected source is not promoted"; exit 2; }
OUT="$ROOT/reports/panel-runs/$PANEL"
[ ! -e "$OUT/executions.txt" ] || {
  echo "ABORT: immutable coverage treatment already launched"; exit 2; }

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
  --max_rows=1000 \
  "SELECT season, week, COUNT(*) AS n
   FROM \`$PROJECT.nfl_predictions.replay_candidates\`
   WHERE panel_run_id='$SOURCE' AND research_eligible
   GROUP BY season, week ORDER BY season, week" > "$TMP_DIR/source_counts.csv"
"$ROOT/.venv/bin/python" - "$TMP_DIR/source_counts.csv" <<'PY'
import csv
import sys

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
if len(rows) != 107:
    raise SystemExit(f"ABORT: expected 107 accepted source slates, got {len(rows)}")
if min(int(row["n"]) for row in rows) < 80:
    raise SystemExit("ABORT: accepted source contains an undersized pool")
print("accepted coverage source verified: 107 slates")
PY

PANEL_CODE_SHA="$CODE_SHA" PANEL_ALLOW_TREATMENT=1 \
PANEL_ARM_LABEL="$LABEL" \
PANEL_ARM_ENV="MODEL_ENSEMBLE=1|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES|ROLE_BELIEF_SEED=7331|REPLACEMENT_SLOTS=12|$PAID_ENV" \
PANEL_N_ENTRIES=80 PANEL_N_CE=0 PANEL_N_EPISTEMIC=12 \
PANEL_N_GUMBEL=0 PANEL_N_BOOM=40 PANEL_SMOKE_SEASON=2024 \
PANEL_TASK_TIMEOUT=14400 \
bash "$ROOT/scripts/baseline_panel.sh" "$IMG" "$FAMILY" "$PANEL"
echo "COVERAGE_TAIL_LAUNCHED panel=$PANEL source=$SOURCE"
