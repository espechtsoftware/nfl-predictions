#!/bin/bash
# Run the frozen SIS QB line score-free final-served gate.
# Usage: cloud_tabpfn_sis_qb_line_final_served.sh <AUDIT_IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-tabpfn-sis-qb-line-final-served-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sis-qb-line-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-13-sis-qb-line-context-protocol.md"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"
CACHE="$ROOT/reports/tabpfn-sis-qb-line-runs/20260813-tabpfn-sis-qb-line-v1/validation.json"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
for path in "$PROTOCOL" "$ACTIVE" "$USAGE" "$CACHE"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable SIS QB line gate already recorded"; exit 2; }

read -r PANEL DIRICHLET_K <<< "$(
  "$ROOT/.venv/bin/python" - "$ACTIVE" "$USAGE" "$CACHE" <<'PY'
import json
import math
import sys

def selection(path):
    return dict(line.rstrip("\n").split("=", 1)
                for line in open(path, encoding="utf-8") if "=" in line)

active, usage = map(selection, sys.argv[1:3])
cache = json.load(open(sys.argv[3], encoding="utf-8"))
panel = active.get("historical_source", "")
if not panel or active.get("label_law") != "active-only" or \
        active.get("cache_table") != "tabpfn_active_label_treatment_v2":
    raise SystemExit("ABORT: active-label selection differs")
if cache.get("disposition") != "tabpfn-sis-qb-line-caches-valid" or \
        not cache.get("passes") or \
        not cache.get("control_reproduction", {}).get("passes"):
    raise SystemExit("ABORT: SIS QB line cache validation did not pass")
if usage.get("allocation") != "dirichlet":
    raise SystemExit("ABORT: accepted usage law is not finite Dirichlet")
value = usage.get("selected_k", "")
try:
    numeric = float(value)
except ValueError as exc:
    raise SystemExit("ABORT: fitted K is not numeric") from exc
if not math.isfinite(numeric) or numeric <= 0:
    raise SystemExit("ABORT: fitted K is invalid")
print(panel, value)
PY
)"

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" "panel=$PANEL" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "active_selection_sha256=$(sha256sum "$ACTIVE" | awk '{print $1}')" \
  "usage_selection_sha256=$(sha256sum "$USAGE" | awk '{print $1}')" \
  "cache_validation_sha256=$(sha256sum "$CACHE" | awk '{print $1}')" \
  'label_law=active_only' 'feature_law=base' \
  'accepted_usage_law=dirichlet' "dirichlet_k=$DIRICHLET_K" \
  'control_table=nfl_features.tabpfn_sis_qb_line_control_v1' \
  'treatment_table=nfl_features.tabpfn_sis_qb_line_treatment_v1' \
  'calibration_fold=2022' 'evaluation_folds=2023 2024 2025' \
  'primary_position=QB' \
  'primary_gate=aggregate-active-qb-30-point-brier-strictly-improves' \
  'position_factor_grid=0.750:0.005:1.500' 'n_sims=10000' 'seed=0' \
  'blend_model_weight=0.45' > "$OUT/manifest.txt"

ENVS="GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1,TABPFN_SIS_QB_LINE_PANEL_ID=$PANEL"
ENVS="$ENVS,TABPFN_ACCEPTED_USAGE_LAW=dirichlet"
ENVS="$ENVS,TABPFN_ACCEPTED_DIRICHLET_K=$DIRICHLET_K"
ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=$DIRICHLET_K"
JOB=tabpfn-sis-qb-line-final-served-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "tabpfn-sis-qb-line-final-served,--panel,$PANEL" \
  --set-env-vars "$ENVS" --memory 16Gi --cpu 8 \
  --max-retries 0 --task-timeout 10800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: SIS QB line gate deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: SIS QB line gate execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "TABPFN_SIS_QB_LINE_FINAL_SERVED_LAUNCHED $EXEC"
