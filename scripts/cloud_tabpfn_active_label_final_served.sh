#!/bin/bash
# Run the frozen final-served gate for the validated active-label caches.
# Usage: bash scripts/cloud_tabpfn_active_label_final_served.sh <IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260811-tabpfn-active-label-final-served-v1
PANEL=20260810-lockfix-e80-k1-8677d21
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-active-label-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-11-tabpfn-active-label-protocol.md"
CACHE_VALIDATION="$ROOT/reports/tabpfn-active-label-runs/20260811-tabpfn-active-label-v1/validation.json"
K_COMPARISON="$ROOT/reports/panel-runs/20260811-lockfix-e80-k1-role12-poscal-usage-k28246898-v1/usage_dirichlet_exact80_comparison.json"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
[ -s "$PROTOCOL" ] || { echo "ABORT: frozen protocol is missing"; exit 2; }
[ -s "$CACHE_VALIDATION" ] || { echo "ABORT: cache validation is missing"; exit 2; }
[ -s "$K_COMPARISON" ] || { echo "ABORT: fitted-K decision is missing"; exit 2; }
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable active-label final-served execution already recorded"; exit 2; }

DECISION_TEXT=$("$ROOT/.venv/bin/python" - "$CACHE_VALIDATION" "$K_COMPARISON" <<'PY'
import json
import sys

cache = json.load(open(sys.argv[1], encoding="utf-8"))
decision = json.load(open(sys.argv[2], encoding="utf-8"))
if cache.get("disposition") != "tabpfn-active-label-caches-valid" or not cache.get("passes"):
    raise SystemExit("ABORT: active-label cache validation did not pass")
if decision.get("failures") or decision.get("disposition") == "invalid":
    raise SystemExit("ABORT: fitted-K comparison is invalid")
if decision.get("disposition") == "pass":
    if not decision.get("tail_first_decision", {}).get("passes"):
        raise SystemExit("ABORT: fitted-K pass lacks a passing tail-first decision")
    print("dirichlet 28.246898139750336")
elif decision.get("disposition") in ("neutral", "reject"):
    print("multinomial -")
else:
    raise SystemExit("ABORT: unknown fitted-K disposition")
PY
)
read -r USAGE_MODE DIRICHLET_K <<< "$DECISION_TEXT"
if [ "$USAGE_MODE" = multinomial ] && [ "$DIRICHLET_K" = - ]; then
  USAGE_MODE=
  DIRICHLET_K=
fi

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" \
  "image=$IMG" \
  "panel=$PANEL" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "cache_validation_sha256=$(sha256sum "$CACHE_VALIDATION" | awk '{print $1}')" \
  "fitted_k_comparison_sha256=$(sha256sum "$K_COMPARISON" | awk '{print $1}')" \
  "game_sim_usage=$USAGE_MODE" \
  "dirichlet_k=$DIRICHLET_K" \
  'control_table=nfl_features.tabpfn_active_label_control_v1' \
  'treatment_table=nfl_features.tabpfn_active_label_treatment_v1' \
  'calibration_fold=2022' \
  'evaluation_folds=2023 2024 2025' \
  'primary_positions=RB WR TE' \
  'primary_gate=aggregate-active-primary-30-point-brier-strictly-improves' \
  'position_factor_grid=0.750:0.005:1.500' \
  'n_sims=10000' \
  'seed=0' \
  'blend_model_weight=0.45' \
  > "$OUT/manifest.txt"

ENVS="GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1"
if [ "$USAGE_MODE" = dirichlet ]; then
  ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=$DIRICHLET_K"
fi
JOB=tabpfn-active-label-final-served
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "tabpfn-active-label-final-served,--panel,$PANEL" \
  --set-env-vars "$ENVS" \
  --memory 16Gi --cpu 8 --max-retries 0 --task-timeout 10800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: active-label gate deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || break
  sleep 20
done

LOG_FILTER="resource.type=\"cloud_run_job\" AND "
LOG_FILTER+="labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND "
LOG_FILTER+='textPayload:"TABPFN_ACTIVE_LABEL_FINAL_SERVED_JSON="'
gcloud logging read "$LOG_FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "TABPFN_ACTIVE_LABEL_FINAL_SERVED_JSON="
payloads = []
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix in line:
        payloads.append(json.loads(line.split(prefix, 1)[1]))
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one active-label report, got {len(payloads)}")
report = payloads[0]
if not report.get("disposition") or not report.get("gate"):
    raise SystemExit("ABORT: active-label report is incomplete")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

[ "$STATE" = True ] || { echo "ABORT: $EXEC failed"; exit 1; }
echo "TabPFN active-label final-served gate complete: $EXEC ($OUT/report.json)"
