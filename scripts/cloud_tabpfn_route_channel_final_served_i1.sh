#!/bin/bash
# Launch the frozen score-free I1 Route marginal-channel gate.
# Usage: cloud_tabpfn_route_channel_final_served_i1.sh <AUDIT_IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260814-tabpfn-route-channel-final-served-i1-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-route-channel-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-14-route-channel-i1-protocol.md"
CACHE="$ROOT/reports/tabpfn-route-channel-runs/20260814-tabpfn-route-channel-i1-v1/validation.json"
PHASE_S="$ROOT/reports/sis-asoe-phase-s-runs/20260813-sis-asoe-phase-s-v1/report.json"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
for path in "$PROTOCOL" "$CACHE" "$PHASE_S" "$ACTIVE" "$USAGE"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable Route score-free execution already recorded"; exit 2; }

read -r PANEL DIRICHLET_K PHASE_S_ARM <<< "$(
  "$ROOT/.venv/bin/python" - "$CACHE" "$PHASE_S" "$ACTIVE" "$USAGE" <<'PY'
import json
import math
import sys

def selection(path):
    return dict(line.rstrip("\n").split("=", 1)
                for line in open(path, encoding="utf-8") if "=" in line)

cache = json.load(open(sys.argv[1], encoding="utf-8"))
phase = json.load(open(sys.argv[2], encoding="utf-8"))
active = selection(sys.argv[3])
usage = selection(sys.argv[4])
if cache.get("disposition") != "tabpfn-route-channel-caches-valid" or \
        not cache.get("passes"):
    raise SystemExit("ABORT: Route-channel cache validation did not pass")
if not phase.get("mechanical_passes") or phase.get("failures"):
    raise SystemExit("ABORT: Phase S mechanical audit did not pass")
phase_arm = phase.get("result", {}).get("decision", {}).get("selected_arm")
if phase_arm not in {"control", "treatment"}:
    raise SystemExit("ABORT: Phase S decision is incomplete")
panel = active.get("historical_source", "")
if panel != "20260811-pitclean-e80-k1-role12union-a12ab31" or \
        active.get("label_law") != "active-only" or \
        active.get("cache_table") != "tabpfn_active_label_treatment_v2":
    raise SystemExit("ABORT: active-label selection differs")
if usage.get("allocation") != "dirichlet":
    raise SystemExit("ABORT: accepted usage law is not finite Dirichlet")
value = usage.get("selected_k", "")
try:
    numeric = float(value)
except ValueError as exc:
    raise SystemExit("ABORT: fitted K is not numeric") from exc
if not math.isfinite(numeric) or numeric <= 0:
    raise SystemExit("ABORT: fitted K is invalid")
print(panel, value, phase_arm)
PY
)"

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" "panel=$PANEL" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "cache_validation_sha256=$(sha256sum "$CACHE" | awk '{print $1}')" \
  "phase_s_report_sha256=$(sha256sum "$PHASE_S" | awk '{print $1}')" \
  "active_selection_sha256=$(sha256sum "$ACTIVE" | awk '{print $1}')" \
  "usage_selection_sha256=$(sha256sum "$USAGE" | awk '{print $1}')" \
  'label_law=active_only' 'accepted_usage_law=dirichlet' \
  "dirichlet_k=$DIRICHLET_K" "phase_s_arm=$PHASE_S_ARM" \
  'control_table=nfl_features.tabpfn_route_channel_control_v1' \
  'marginal_table=nfl_features.tabpfn_route_channel_marginal_v1' \
  'calibration_fold=2022' 'evaluation_folds=2023 2024 2025' \
  'primary_positions=RB WR TE' \
  'primary_gate=equal-position-equal-q95-q99-pinball-ratio-below-one-and-two-positions-improve' \
  'position_factor_grid=0.750:0.005:1.500' 'n_sims=10000' 'seed=0' \
  'blend_model_weight=0.45' > "$OUT/manifest.txt"

ENVS="GCP_PROJECT=$PROJECT,TABPFN_ROUTE_CHANNEL_PANEL_ID=$PANEL"
ENVS="$ENVS,TABPFN_ROUTE_PHASE_S_ARM=$PHASE_S_ARM"
ENVS="$ENVS,TABPFN_ACCEPTED_USAGE_LAW=dirichlet"
ENVS="$ENVS,TABPFN_ACCEPTED_DIRICHLET_K=$DIRICHLET_K"
ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=$DIRICHLET_K"
if [ "$PHASE_S_ARM" = treatment ]; then
  ENVS="$ENVS,SIS_ASOE_TARGET_ALLOCATION=1,SIS_ASOE_BETA=0.07771181538347656"
fi
JOB=tabpfn-route-channel-final-served-i1-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "tabpfn-route-channel-final-served,--panel,$PANEL" \
  --set-env-vars "$ENVS" --memory 16Gi --cpu 8 \
  --max-retries 0 --task-timeout 10800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: Route gate deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: Route gate execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "TABPFN_ROUTE_CHANNEL_FINAL_SERVED_LAUNCHED $EXEC"
