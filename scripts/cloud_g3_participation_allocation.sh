#!/bin/bash
# Launch the sole frozen score-free G3 conditional allocation Stage A gate.
# Usage: cloud_g3_participation_allocation.sh <AUDIT_IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-g3-participation-allocation-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/g3-participation-allocation-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-13-g3-participation-conditioned-allocation-protocol.md"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable G3 image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable G3 code SHA required"; exit 2;;
esac
for path in "$PROTOCOL" "$ACTIVE" "$USAGE"; do
  [ -s "$path" ] || { echo "ABORT: G3 prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable G3 execution already recorded"; exit 2; }

"$ROOT/.venv/bin/python" - "$ACTIVE" "$USAGE" <<'PY'
import math, sys
def read(path):
    return dict(line.rstrip().split("=", 1) for line in open(path) if "=" in line)
a, u = read(sys.argv[1]), read(sys.argv[2])
expected = {
    "allocation": "dirichlet",
    "selected_k": "28.154043586960896",
    "historical_source": "20260811-pitclean-e80-k1-role12union-a12ab31",
}
for key, value in expected.items():
    if a.get(key) != value or u.get(key) != value:
        raise SystemExit(f"ABORT: G3 selected {key} prerequisite differs")
if a.get("cache_table") != "tabpfn_active_label_treatment_v2":
    raise SystemExit("ABORT: G3 accepted cache differs")
PY

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "active_label_selection_sha256=$(sha256sum "$ACTIVE" | awk '{print $1}')" \
  "usage_selection_sha256=$(sha256sum "$USAGE" | awk '{print $1}')" \
  'source_seasons=2016 2017 2018 2019 2020 2021 2022 2023 2024' \
  'calibration_seasons=2021 2022' \
  'evaluation_seasons=2023 2024 2025' \
  'global_k=28.154043586960896' 'embedding_dimension=16' \
  'negative_samples=5' 'actor_context_bonus=3' \
  'svd_iterations=7' 'svd_seed=8112026' \
  'minimum_geometry_mass=0.80' 'beta_bounds=-1.5:1.5' \
  'beta_l2=0.05' 'bootstrap_resamples=2000' \
  'bootstrap_seed=8113026' > "$OUT/manifest.txt"

JOB=g3-participation-allocation-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs --args g3-participation-allocation \
  --set-env-vars "GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1" \
  --memory 32Gi --cpu 8 --max-retries 0 --task-timeout 21600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: G3 job deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: G3 execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "G3_PARTICIPATION_ALLOCATION_LAUNCHED $EXEC"

