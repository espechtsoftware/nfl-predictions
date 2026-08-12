#!/bin/bash
# Run the repaired v2 final-served gate from machine-selected dependencies.
# Usage: bash scripts/cloud_tabpfn_active_label_final_served_v2.sh \
#   <IMAGE@sha256:...> <CODE_SHA> <REPAIRED_PANEL> \
#   <CACHE_VALIDATION.json> <FITTED_K_COMPARISON.json>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PANEL=${3:-}
CACHE_VALIDATION=${4:-}
K_COMPARISON=${5:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260811-tabpfn-active-label-final-served-v2-pit-clean
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-active-label-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-11-tabpfn-active-label-protocol.md"
REPAIR_PROTOCOL="$ROOT/reports/2026-08-11-tabpfn-active-label-pit-clean-cache-addendum.md"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
case "$PANEL" in
  ""|*[!A-Za-z0-9_-]*) echo "ABORT: invalid repaired panel id"; exit 2;;
esac
[ -s "$PROTOCOL" ] || { echo "ABORT: frozen protocol is missing"; exit 2; }
[ -s "$REPAIR_PROTOCOL" ] || { echo "ABORT: repair protocol is missing"; exit 2; }
[ -s "$CACHE_VALIDATION" ] || { echo "ABORT: cache validation is missing"; exit 2; }
[ -s "$K_COMPARISON" ] || { echo "ABORT: fitted-K decision is missing"; exit 2; }
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable v2 final-served execution already recorded"; exit 2; }

DECISION_TEXT=$("$ROOT/.venv/bin/python" - \
    "$CACHE_VALIDATION" "$K_COMPARISON" <<'PY'
import json
import math
import sys

cache = json.load(open(sys.argv[1], encoding="utf-8"))
decision = json.load(open(sys.argv[2], encoding="utf-8"))
if cache.get("version") != "v2" or \
        cache.get("disposition") != "tabpfn-active-label-caches-valid" or \
        not cache.get("passes"):
    raise SystemExit("ABORT: v2 active-label cache validation did not pass")
if decision.get("failures") or decision.get("disposition") == "invalid":
    raise SystemExit("ABORT: repaired fitted-K comparison is invalid")
tail = decision.get("tail_first_decision", {})
if decision.get("disposition") == "pass":
    if not tail.get("passes"):
        raise SystemExit("ABORT: fitted-K pass lacks a passing tail-first decision")
    value = str(decision.get("fitted_k", ""))
    try:
        number = float(value)
    except ValueError as exc:
        raise SystemExit("ABORT: fitted-K pass lacks numeric fitted_k") from exc
    if not math.isfinite(number) or number <= 0:
        raise SystemExit("ABORT: fitted_k must be finite and positive")
    print("dirichlet", value)
elif decision.get("disposition") in ("neutral", "reject"):
    print("multinomial", "-")
else:
    raise SystemExit("ABORT: unknown repaired fitted-K disposition")
PY
)
read -r ACCEPTED_USAGE DIRICHLET_K <<< "$DECISION_TEXT"

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" \
  "image=$IMG" \
  "code_sha=$CODE_SHA" \
  "panel=$PANEL" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "repair_protocol_sha256=$(sha256sum "$REPAIR_PROTOCOL" | awk '{print $1}')" \
  "cache_validation=$CACHE_VALIDATION" \
  "cache_validation_sha256=$(sha256sum "$CACHE_VALIDATION" | awk '{print $1}')" \
  "fitted_k_comparison=$K_COMPARISON" \
  "fitted_k_comparison_sha256=$(sha256sum "$K_COMPARISON" | awk '{print $1}')" \
  "accepted_usage_law=$ACCEPTED_USAGE" \
  "dirichlet_k=$DIRICHLET_K" \
  'control_table=nfl_features.tabpfn_active_label_control_v2' \
  'treatment_table=nfl_features.tabpfn_active_label_treatment_v2' \
  'calibration_fold=2022' \
  'evaluation_folds=2023 2024 2025' \
  'primary_positions=RB WR TE' \
  'primary_gate=aggregate-active-primary-30-point-brier-strictly-improves' \
  'position_factor_grid=0.750:0.005:1.500' \
  'n_sims=10000' \
  'seed=0' \
  'blend_model_weight=0.45' \
  > "$OUT/manifest.txt"

ENVS="GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1,TABPFN_ACTIVE_LABEL_VERSION=v2"
ENVS="$ENVS,TABPFN_ACTIVE_LABEL_PANEL_ID=$PANEL"
ENVS="$ENVS,TABPFN_ACCEPTED_USAGE_LAW=$ACCEPTED_USAGE"
if [ "$ACCEPTED_USAGE" = dirichlet ]; then
  ENVS="$ENVS,TABPFN_ACCEPTED_DIRICHLET_K=$DIRICHLET_K"
  ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=$DIRICHLET_K"
fi
JOB=tabpfn-active-label-final-served-v2
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "tabpfn-active-label-final-served,--panel,$PANEL" \
  --set-env-vars "$ENVS" \
  --memory 16Gi --cpu 8 --max-retries 0 --task-timeout 10800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: v2 gate deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "TABPFN_ACTIVE_LABEL_FINAL_SERVED_V2_LAUNCHED $EXEC"
