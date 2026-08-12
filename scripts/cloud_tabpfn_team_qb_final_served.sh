#!/bin/bash
# Run the frozen team-QB final-served gate from terminal inherited decisions.
# Usage: cloud_tabpfn_team_qb_final_served.sh <AUDIT_IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260812-tabpfn-team-qb-final-served-v1-pit-clean
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-team-qb-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-11-tabpfn-team-qb-quality-protocol.md"
TIER1="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-role-v2/selected_tier1.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"
SCHED="$ROOT/reports/tabpfn-sched-runs/20260812-tabpfn-sched-exact80-v1-pit-clean/selected_sched.txt"
CACHE="$ROOT/reports/tabpfn-team-qb-runs/20260812-tabpfn-team-qb-v1-pit-clean/validation.json"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
for path in "$PROTOCOL" "$TIER1" "$USAGE" "$SCHED" "$CACHE"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable team-QB gate execution already recorded"; exit 2; }

read -r PANEL LABEL_LAW FEATURE_LAW ACCEPTED_USAGE DIRICHLET_K <<< "$(
  "$ROOT/.venv/bin/python" - "$TIER1" "$USAGE" "$SCHED" "$CACHE" <<'PY'
import json
import math
import sys

def selection(path):
    return dict(
        line.rstrip("\n").split("=", 1)
        for line in open(path, encoding="utf-8") if "=" in line)

tier1, usage, sched = map(selection, sys.argv[1:4])
cache = json.load(open(sys.argv[4], encoding="utf-8"))
panel = tier1.get("selected_panel", "")
if not panel or sched.get("historical_source") != panel:
    raise SystemExit("ABORT: team-QB inherited panel differs")
label = {"current": "current", "active-only": "active_only"}.get(
    sched.get("label_law"))
feature = {"shared33": "base", "sched35": "sched"}.get(
    sched.get("feature_contract"))
if label is None or feature is None:
    raise SystemExit("ABORT: team-QB inherited feature/label law differs")
if cache.get("disposition") != "tabpfn-team-qb-caches-valid" or \
        not cache.get("passes") or \
        not cache.get("control_reproduction", {}).get("passes"):
    raise SystemExit("ABORT: team-QB cache validation did not pass")
if cache.get("label_law") != label or cache.get("feature_law") != feature:
    raise SystemExit("ABORT: team-QB cache validation targets another law")
allocation = usage.get("allocation")
value = usage.get("selected_k", "")
if allocation == "multinomial" and value == "infinity":
    print(panel, label, feature, "multinomial", "-")
elif allocation == "dirichlet":
    try:
        numeric = float(value)
    except ValueError as exc:
        raise SystemExit("ABORT: team-QB fitted K is not numeric") from exc
    if not math.isfinite(numeric) or numeric <= 0:
        raise SystemExit("ABORT: team-QB fitted K is invalid")
    print(panel, label, feature, "dirichlet", value)
else:
    raise SystemExit("ABORT: team-QB usage selection is invalid")
PY
)"

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" "panel=$PANEL" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "tier1_selection_sha256=$(sha256sum "$TIER1" | awk '{print $1}')" \
  "usage_selection_sha256=$(sha256sum "$USAGE" | awk '{print $1}')" \
  "sched_selection_sha256=$(sha256sum "$SCHED" | awk '{print $1}')" \
  "cache_validation_sha256=$(sha256sum "$CACHE" | awk '{print $1}')" \
  "label_law=$LABEL_LAW" "feature_law=$FEATURE_LAW" \
  "accepted_usage_law=$ACCEPTED_USAGE" "dirichlet_k=$DIRICHLET_K" \
  'control_table=nfl_features.tabpfn_team_qb_control_v1' \
  'treatment_table=nfl_features.tabpfn_team_qb_treatment_v1' \
  'calibration_fold=2022' 'evaluation_folds=2023 2024 2025' \
  'primary_positions=RB WR TE' \
  'primary_gate=aggregate-active-primary-30-point-brier-strictly-improves' \
  'position_factor_grid=0.750:0.005:1.500' 'n_sims=10000' 'seed=0' \
  'blend_model_weight=0.45' \
  > "$OUT/manifest.txt"

ENVS="GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1,TABPFN_TEAM_QB_PANEL_ID=$PANEL"
ENVS="$ENVS,TABPFN_TEAM_QB_LABEL_LAW=$LABEL_LAW"
ENVS="$ENVS,TABPFN_TEAM_QB_FEATURE_LAW=$FEATURE_LAW"
ENVS="$ENVS,TABPFN_ACCEPTED_USAGE_LAW=$ACCEPTED_USAGE"
if [ "$ACCEPTED_USAGE" = dirichlet ]; then
  ENVS="$ENVS,TABPFN_ACCEPTED_DIRICHLET_K=$DIRICHLET_K"
  ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=$DIRICHLET_K"
fi
JOB=tabpfn-team-qb-final-served-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "tabpfn-team-qb-final-served,--panel,$PANEL" \
  --set-env-vars "$ENVS" --memory 16Gi --cpu 8 \
  --max-retries 0 --task-timeout 10800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: team-QB gate deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: team-QB gate execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "TABPFN_TEAM_QB_FINAL_SERVED_LAUNCHED $EXEC"
