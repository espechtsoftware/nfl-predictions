#!/bin/bash
# Launch the sole frozen score-free SIS ASOE target-allocation Stage A gate.
# Usage: cloud_sis_asoe_allocation.sh <AUDIT_IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-sis-asoe-allocation-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/sis-asoe-allocation-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-13-sis-asoe-allocation-stage-a-protocol.md"
ACQUISITION="$ROOT/reports/2026-08-13-sis-asoe-acquisition-protocol.md"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable ASOE image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable ASOE code SHA required"; exit 2;;
esac
for path in "$PROTOCOL" "$ACQUISITION" "$ACTIVE" "$USAGE"; do
  [ -s "$path" ] || { echo "ABORT: ASOE prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable ASOE execution already recorded"; exit 2; }

"$ROOT/.venv/bin/python" - "$ACTIVE" "$USAGE" <<'PY'
import sys
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
        raise SystemExit(f"ABORT: ASOE selected {key} prerequisite differs")
if a.get("cache_table") != "tabpfn_active_label_treatment_v2":
    raise SystemExit("ABORT: ASOE accepted active-label cache differs")
PY

for table in fantasy_points_alignment_player_l4 fantasy_points_alignment_team_l4 sis_alignment_attempt_game; do
  bq show --project_id="$PROJECT" "nfl_raw.$table" >/dev/null || {
    echo "ABORT: ASOE raw table missing: $table"; exit 2; }
done

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "acquisition_protocol_sha256=$(sha256sum "$ACQUISITION" | awk '{print $1}')" \
  "active_label_selection_sha256=$(sha256sum "$ACTIVE" | awk '{print $1}')" \
  "usage_selection_sha256=$(sha256sum "$USAGE" | awk '{print $1}')" \
  'calibration_season=2022' 'evaluation_seasons=2023 2024 2025' \
  'target_weeks=5 6 7 8 9 10 11 12 13 14 15 16 17 18' \
  'global_k=28.154043586960896' 'beta_bounds=0:8' 'beta_l2=0.01' \
  'minimum_group_probability_mass=0.50' \
  'minimum_evaluation_group_coverage=0.50' \
  'bootstrap_resamples=2000' 'bootstrap_seed=8113126' > "$OUT/manifest.txt"

JOB=sis-asoe-allocation-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs --args sis-asoe-allocation \
  --set-env-vars "GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1" \
  --memory 32Gi --cpu 8 --max-retries 0 --task-timeout 21600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: ASOE job deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: ASOE execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "SIS_ASOE_ALLOCATION_LAUNCHED $EXEC"
