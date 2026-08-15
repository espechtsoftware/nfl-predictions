#!/usr/bin/env bash
set -euo pipefail

# Launch held-out SIS receiver-copula evaluation after both prerequisite harvests.
# Usage: cloud_sis_receiver_copula_heldout.sh <image@sha256:...> <full-code-sha> [run-id] [job]

IMAGE=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=${3:-20260815-sis-receiver-copula-v1}
JOB=${4:-sis-receiver-copula-heldout-v1}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/sis-receiver-copula-runs/$RUN_ID/heldout"
REFERENCE="$ROOT/reports/sis-receiver-copula-runs/$RUN_ID/reference"
CALIBRATION="$ROOT/reports/sis-receiver-copula-runs/$RUN_ID/calibration"
HISTORICAL=20260811-pitclean-e80-k1-role12union-a12ab31
EVALUATION=20260812-pitclean-e80-selected-tabpfn-active-v2

case "$IMAGE" in *@sha256:*) ;; *) echo "ABORT: immutable SIS held-out image required"; exit 2;; esac
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ABORT: full SIS held-out code SHA required"; exit 2; }
git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}" 2>/dev/null || {
  echo "ABORT: SIS held-out code commit is unavailable"; exit 2; }
git -C "$ROOT" merge-base --is-ancestor 26e73c5 "$CODE_SHA" || {
  echo "ABORT: SIS held-out code is not descended from 26e73c5"; exit 2; }
for path in "$REFERENCE/report.json" "$REFERENCE/manifest.txt" \
            "$CALIBRATION/report.json" "$CALIBRATION/manifest.txt"; do
  [ -s "$path" ] || { echo "ABORT: SIS held-out prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT" ] || { echo "ABORT: immutable SIS held-out output exists: $OUT"; exit 2; }

declare -A resolved
while IFS='=' read -r key value; do resolved[$key]=$value; done < <(
  "$ROOT/.venv/bin/python" - "$REFERENCE/report.json" "$REFERENCE/manifest.txt" \
      "$CALIBRATION/report.json" "$CALIBRATION/manifest.txt" <<'PY'
import base64
import hashlib
import json
import re
import sys

def digest(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()

reference = json.load(open(sys.argv[1], encoding="utf-8"))
calibration = json.load(open(sys.argv[3], encoding="utf-8"))
historical = "20260811-pitclean-e80-k1-role12union-a12ab31"
evaluation = "20260812-pitclean-e80-selected-tabpfn-active-v2"
if reference.get("disposition") != "sis-receiver-copula-reference-passes" or \
        reference.get("heldout_treatment_licensed") is not True or \
        reference.get("historical_panel") != historical or \
        reference.get("evaluation_panel") != evaluation or \
        not reference.get("invariants", {}).get("passes"):
    raise SystemExit("ABORT: fresh SIS reference did not pass")
if calibration.get("disposition") != "sis-receiver-copula-calibration-passes" or \
        calibration.get("heldout_evaluation_licensed") is not True or \
        calibration.get("panel") != historical or \
        not calibration.get("passes"):
    raise SystemExit("ABORT: SIS calibration did not pass")
reference_attestation = {
    "version": "sis-receiver-copula-reference-attestation-v1",
    "historical_panel": historical,
    "evaluation_panel": evaluation,
    "disposition": reference["disposition"],
    "heldout_treatment_licensed": True,
    "run_identity": reference["run_identity"],
    "report_sha256": digest(sys.argv[1]),
    "manifest_sha256": digest(sys.argv[2]),
    "score_sha256": reference["score_sha256"],
    "frame_sha256": reference["invariants"]["frame_sha256"],
    "draws_sha256": reference["invariants"]["draws_sha256"],
    "terminal_sha256": hashlib.sha256(json.dumps(
        reference["invariants"]["control_terminal"], sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest(),
}
calibration_attestation = {
    "version": "sis-receiver-copula-calibration-attestation-v1",
    "panel": historical,
    "disposition": calibration["disposition"],
    "heldout_evaluation_licensed": True,
    "run_identity": calibration["run_identity"],
    "report_sha256": digest(sys.argv[3]),
    "manifest_sha256": digest(sys.argv[4]),
    "protocols": calibration["protocols"],
    "selected": calibration["selected"],
}
for name, value in (("reference", reference_attestation),
                    ("calibration", calibration_attestation)):
    content = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    print(f"{name}_b64={base64.b64encode(content).decode()}")
    print(f"{name}_sha={hashlib.sha256(content).hexdigest()}")
schedule = json.dumps(
    reference["settings"]["position_schedule"],
    sort_keys=True, separators=(",", ":"),
).encode()
print(f"schedule_b64={base64.b64encode(schedule).decode()}")
PY
)

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "stage=heldout" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "historical_panel=$HISTORICAL" "evaluation_panel=$EVALUATION" \
  "reference_attestation_sha256=${resolved[reference_sha]}" \
  "calibration_attestation_sha256=${resolved[calibration_sha]}" \
  'evaluation_seasons=2023 2024 2025' 'cache_table=tabpfn_active_label_treatment_v2' \
  'dirichlet_k=28.154043586960896' 'model_market_blend=0.45/0.55' \
  'n_sims=10000' 'seed=0' 'bootstrap_replicates=2000' 'bootstrap_seed=1703' \
  'retrospective_exact80_licensed=false' > "$OUT/manifest.txt"

ENVS="GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1"
ENVS="$ENVS,SIS_RECEIVER_COPULA_HELDOUT_PANEL=$HISTORICAL"
ENVS="$ENVS,SIS_RECEIVER_COPULA_HELDOUT_EVALUATION_PANEL=$EVALUATION"
ENVS="$ENVS,SIS_RECEIVER_COPULA_HELDOUT_RUN_ID=$RUN_ID"
ENVS="$ENVS,SIS_RECEIVER_COPULA_HELDOUT_CODE_SHA=$CODE_SHA"
ENVS="$ENVS,SIS_RECEIVER_COPULA_REFERENCE_ATTESTATION_B64=${resolved[reference_b64]}"
ENVS="$ENVS,SIS_RECEIVER_COPULA_REFERENCE_ATTESTATION_SHA256=${resolved[reference_sha]}"
ENVS="$ENVS,SIS_RECEIVER_COPULA_CALIBRATION_ATTESTATION_B64=${resolved[calibration_b64]}"
ENVS="$ENVS,SIS_RECEIVER_COPULA_CALIBRATION_ATTESTATION_SHA256=${resolved[calibration_sha]}"
ENVS="$ENVS,G1_PANEL_ID=$HISTORICAL,G1_CACHE_TABLE=tabpfn_active_label_treatment_v2"
ENVS="$ENVS,G1_POSITION_SCHEDULE_B64=${resolved[schedule_b64]}"
ENVS="$ENVS,TABPFN_ACCEPTED_USAGE_LAW=dirichlet"
ENVS="$ENVS,TABPFN_ACCEPTED_DIRICHLET_K=28.154043586960896"
ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=28.154043586960896"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --command nfl-dfs \
  --args "sis-receiver-copula-heldout,--panel,$HISTORICAL" \
  --set-env-vars "$ENVS" --memory 32Gi --cpu 8 --tasks 1 --parallelism 1 \
  --max-retries 0 --task-timeout 21600 --quiet >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMAGE" ] || {
  echo "ABORT: SIS held-out deployed $DEPLOYED, expected $IMAGE"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: SIS held-out execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "SIS_RECEIVER_COPULA_HELDOUT_LAUNCHED $EXEC"
