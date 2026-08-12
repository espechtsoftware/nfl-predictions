#!/bin/bash
# Launch the frozen SCHED final-served gate from terminal upstream decisions.
# Usage: cloud_tabpfn_sched_final_served.sh <AUDIT_IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260812-tabpfn-sched-final-served-v1-pit-clean
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sched-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-11-tabpfn-schedule-feature-sync-protocol.md"
TIER1="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-role-v2/selected_tier1.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
CACHE="$ROOT/reports/tabpfn-sched-runs/20260812-tabpfn-sched-v1-pit-clean/validation.json"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
for path in "$PROTOCOL" "$TIER1" "$USAGE" "$ACTIVE" "$CACHE"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable SCHED final-served execution exists"; exit 2; }

DECISION=$(
  "$ROOT/.venv/bin/python" - "$TIER1" "$USAGE" "$ACTIVE" "$CACHE" <<'PY'
import json
import math
import sys

def record(path):
    return dict(
        line.rstrip("\n").split("=", 1)
        for line in open(path, encoding="utf-8") if "=" in line
    )

tier = record(sys.argv[1])
usage = record(sys.argv[2])
active = record(sys.argv[3])
cache = json.load(open(sys.argv[4], encoding="utf-8"))
panel = tier.get("selected_panel")
if not panel or tier.get("selected_base") != "k1":
    raise SystemExit("ABORT: SCHED requires terminal K1 Tier-1 selection")
if usage.get("historical_source") != panel or active.get("historical_source") != panel:
    raise SystemExit("ABORT: terminal usage/label branches target another panel")
label = active.get("label_law")
if label == "current":
    label_law = "current"
elif label == "active-only":
    label_law = "active_only"
else:
    raise SystemExit("ABORT: terminal active-label law is invalid")
if cache.get("disposition") != "tabpfn-sched-caches-valid" or not cache.get("passes"):
    raise SystemExit("ABORT: SCHED cache validation did not pass")
if cache.get("label_law") != label_law:
    raise SystemExit("ABORT: SCHED caches use another terminal label law")
if cache.get("tables") != {
    "control": "tabpfn_sched_control_v1",
    "treatment": "tabpfn_sched_treatment_v1",
}:
    raise SystemExit("ABORT: SCHED cache tables differ")
allocation = usage.get("allocation")
selected_k = usage.get("selected_k", "")
if allocation == "multinomial" and selected_k == "infinity":
    print(panel, label_law, "multinomial", "-")
elif allocation == "dirichlet":
    try:
        value = float(selected_k)
    except ValueError as exc:
        raise SystemExit("ABORT: fitted-K selection is not numeric") from exc
    if not math.isfinite(value) or value <= 0:
        raise SystemExit("ABORT: fitted-K selection is invalid")
    print(panel, label_law, "dirichlet", selected_k)
else:
    raise SystemExit("ABORT: terminal usage law is invalid")
PY
)
read -r PANEL LABEL_LAW ACCEPTED_USAGE DIRICHLET_K <<< "$DECISION"

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "panel=$PANEL" "label_law=$LABEL_LAW" \
  "accepted_usage_law=$ACCEPTED_USAGE" "dirichlet_k=$DIRICHLET_K" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "tier1_selection_sha256=$(sha256sum "$TIER1" | awk '{print $1}')" \
  "usage_selection_sha256=$(sha256sum "$USAGE" | awk '{print $1}')" \
  "active_selection_sha256=$(sha256sum "$ACTIVE" | awk '{print $1}')" \
  "cache_validation_sha256=$(sha256sum "$CACHE" | awk '{print $1}')" \
  'control_table=nfl_features.tabpfn_sched_control_v1' \
  'treatment_table=nfl_features.tabpfn_sched_treatment_v1' \
  'calibration_fold=2022' 'evaluation_folds=2023 2024 2025' \
  'primary_positions=RB WR TE' \
  'primary_gate=aggregate-active-primary-30-point-brier-strictly-improves' \
  'position_factor_grid=0.750:0.005:1.500' \
  'n_sims=10000' 'seed=0' 'blend_model_weight=0.45' \
  > "$OUT/manifest.txt"

ENVS="GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1,TABPFN_SCHED_PANEL_ID=$PANEL"
ENVS="$ENVS,TABPFN_SCHED_LABEL_LAW=$LABEL_LAW"
ENVS="$ENVS,TABPFN_ACCEPTED_USAGE_LAW=$ACCEPTED_USAGE"
if [ "$ACCEPTED_USAGE" = dirichlet ]; then
  ENVS="$ENVS,TABPFN_ACCEPTED_DIRICHLET_K=$DIRICHLET_K"
  ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=$DIRICHLET_K"
fi
JOB=tabpfn-sched-final-served-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "tabpfn-sched-final-served,--panel,$PANEL" \
  --set-env-vars "$ENVS" --memory 16Gi --cpu 8 \
  --max-retries 0 --task-timeout 10800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: SCHED gate deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: SCHED execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "TABPFN_SCHED_FINAL_SERVED_LAUNCHED $EXEC"
