#!/usr/bin/env bash
set -euo pipefail

# Launch the frozen fresh repaired-path SIS receiver-copula reference.
# Usage: cloud_sis_receiver_copula_reference.sh <image@sha256:...> <full-code-sha> [run-id] [job]

IMAGE=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=${3:-20260815-sis-receiver-copula-v1}
JOB=${4:-sis-receiver-copula-reference-v1}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/sis-receiver-copula-runs/$RUN_ID/reference"
PROTOCOL="$ROOT/reports/2026-08-15-sis-receiver-copula-protocol.md"
G1="$ROOT/reports/g1-topology-runs/20260812-g1-archetype-topology-v3"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"
REPAIR_SHA=26e73c5
EXPECTED_PROTOCOL_SHA=045a5a8e90bdbc95b5fdfa4ff29574f71fe03fcc69701d3c39dfc159c1395274

case "$IMAGE" in *@sha256:*) ;; *) echo "ABORT: immutable SIS reference image required"; exit 2;; esac
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ABORT: full SIS reference code SHA required"; exit 2; }
git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}" 2>/dev/null || {
  echo "ABORT: SIS reference code commit is unavailable"; exit 2; }
git -C "$ROOT" merge-base --is-ancestor "$REPAIR_SHA" "$CODE_SHA" || {
  echo "ABORT: SIS reference code is not descended from $REPAIR_SHA"; exit 2; }
for path in "$PROTOCOL" "$G1/report.json" "$G1/manifest.txt" "$ACTIVE" "$USAGE"; do
  [ -s "$path" ] || { echo "ABORT: SIS reference prerequisite missing: $path"; exit 2; }
done
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$EXPECTED_PROTOCOL_SHA" ] || {
  echo "ABORT: frozen SIS receiver-copula protocol hash differs"; exit 2; }
[ ! -e "$OUT" ] || { echo "ABORT: immutable SIS reference exists: $OUT"; exit 2; }

declare -A resolved
while IFS='=' read -r key value; do resolved[$key]=$value; done < <(
  "$ROOT/.venv/bin/python" - "$ACTIVE" "$USAGE" "$G1/report.json" <<'PY'
import base64
import json
import math
import sys

def selection(path):
    return dict(line.rstrip("\n").split("=", 1)
                for line in open(path, encoding="utf-8") if "=" in line)

active = selection(sys.argv[1])
usage = selection(sys.argv[2])
g1 = json.load(open(sys.argv[3], encoding="utf-8"))
historical = "20260811-pitclean-e80-k1-role12union-a12ab31"
evaluation = "20260812-pitclean-e80-selected-tabpfn-active-v2"
cache = "tabpfn_active_label_treatment_v2"
k = "28.154043586960896"
expected_schedule = {
    "2023": {"factors": {"QB": 0.965, "RB": 0.99, "TE": 0.945, "WR": 1.03}},
    "2024": {"factors": {"QB": 0.905, "RB": 0.97, "TE": 0.95, "WR": 1.06}},
    "2025": {"factors": {"QB": 0.925, "RB": 0.96, "TE": 0.94, "WR": 1.04}},
}
if active.get("historical_source") != historical or \
        usage.get("historical_source") != historical:
    raise SystemExit("ABORT: SIS reference historical splice differs")
if active.get("selected_eval_panel") != evaluation:
    raise SystemExit("ABORT: SIS reference evaluation panel differs")
if active.get("cache_table") != cache:
    raise SystemExit("ABORT: SIS reference active cache differs")
if active.get("allocation") != "dirichlet" or \
        usage.get("allocation") != "dirichlet" or \
        active.get("selected_k") != k or usage.get("selected_k") != k or \
        not math.isclose(float(k), 28.154043586960896, rel_tol=0, abs_tol=0):
    raise SystemExit("ABORT: SIS reference finite usage law differs")
if g1.get("position_schedule") != expected_schedule:
    raise SystemExit("ABORT: SIS reference served-position schedule differs")
schedule = json.dumps(expected_schedule, sort_keys=True, separators=(",", ":"))
print(f"historical={historical}")
print(f"evaluation={evaluation}")
print(f"cache={cache}")
print(f"k={k}")
print(f"schedule_b64={base64.b64encode(schedule.encode()).decode()}")
PY
)

mkdir -p "$OUT"
SCHEDULE_SHA=$(printf '%s' "${resolved[schedule_b64]}" | base64 -d | sha256sum | awk '{print $1}')
printf '%s\n' \
  "run_id=$RUN_ID" "stage=fresh-reference" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "historical_panel=${resolved[historical]}" \
  "evaluation_panel=${resolved[evaluation]}" \
  "cache_table=${resolved[cache]}" "dirichlet_k=${resolved[k]}" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "g1_report_sha256=$(sha256sum "$G1/report.json" | awk '{print $1}')" \
  "g1_manifest_sha256=$(sha256sum "$G1/manifest.txt" | awk '{print $1}')" \
  "active_label_selection_sha256=$(sha256sum "$ACTIVE" | awk '{print $1}')" \
  "usage_selection_sha256=$(sha256sum "$USAGE" | awk '{print $1}')" \
  "schedule_sha256=$SCHEDULE_SHA" "repair_ancestor=$REPAIR_SHA" \
  'evaluation_seasons=2023 2024 2025' 'n_sims=10000' 'seed=0' \
  'model_market_blend=0.45/0.55' 'prior_numeric_reference=forbidden' > "$OUT/manifest.txt"

ENVS="GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1"
ENVS="$ENVS,SIS_RECEIVER_COPULA_REFERENCE_PANEL=${resolved[historical]}"
ENVS="$ENVS,SIS_RECEIVER_COPULA_REFERENCE_EVALUATION_PANEL=${resolved[evaluation]}"
ENVS="$ENVS,SIS_RECEIVER_COPULA_REFERENCE_RUN_ID=$RUN_ID"
ENVS="$ENVS,SIS_RECEIVER_COPULA_REFERENCE_CODE_SHA=$CODE_SHA"
ENVS="$ENVS,G1_PANEL_ID=${resolved[historical]},G1_CACHE_TABLE=${resolved[cache]}"
ENVS="$ENVS,G1_POSITION_SCHEDULE_B64=${resolved[schedule_b64]}"
ENVS="$ENVS,TABPFN_ACCEPTED_USAGE_LAW=dirichlet"
ENVS="$ENVS,TABPFN_ACCEPTED_DIRICHLET_K=${resolved[k]}"
ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=${resolved[k]}"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --command nfl-dfs \
  --args "sis-receiver-copula-reference,--panel,${resolved[historical]}" \
  --set-env-vars "$ENVS" --memory 32Gi --cpu 8 --tasks 1 --parallelism 1 \
  --max-retries 0 --task-timeout 21600 --quiet >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMAGE" ] || {
  echo "ABORT: SIS reference deployed $DEPLOYED, expected $IMAGE"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: SIS reference execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "SIS_RECEIVER_COPULA_REFERENCE_LAUNCHED $EXEC"
