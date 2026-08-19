#!/usr/bin/env bash
set -euo pipefail

# All-boom reallocation arm: wait out the validation build, verify it,
# reuse the existing job (frozen-chain rule 5: deploy-update + per-
# execution --args, zero job creations), run the 2023 W1 real-path
# canary, release the 53 remaining cells, poll to terminal failing
# closed on any cell, then aggregate paired delta C create-only.
#
# Usage: cloud_all_boom_chain.sh <build-id> <code-sha>

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260819-all-boom-reallocation-c-v1
OUT="$ROOT/reports/all-boom-reallocation-c-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/all-boom-reallocation-c-runs/$RUN_ID
REUSED_JOB=atlas-minimal-c-s2023-w1-v1
EXECUTIONS="$OUT/executions.txt"
BUILD_ID=${1:?build id}
CODE_SHA=${2:?code sha}

[ -e "$EXECUTIONS" ] && { echo "ERROR: all-boom ledger exists" >&2; exit 2; }

while :; do
  STATUS=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
    --format='value(status)' 2>/dev/null || echo "")
  printf '%s ALLBOOM_BUILD status=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${STATUS:-Unknown}"
  case "$STATUS" in
    SUCCESS) break ;;
    FAILURE|CANCELLED|TIMEOUT|EXPIRED)
      echo "ERROR: all-boom build terminal $STATUS" >&2; exit 2 ;;
    *) sleep 120 ;;
  esac
done
DIGEST=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
  --format='value(results.images[0].digest)')
IMAGE="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@${DIGEST}"

for RELATIVE in Dockerfile cloudbuild.yaml \
  scripts/run_all_boom_reallocation_c.py \
  scripts/run_atlas_minimal_world_selection_c.py \
  reports/2026-08-19-all-boom-reallocation-protocol.md; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: all-boom built source differs: $RELATIVE" >&2; exit 2; }
done
if gsutil -q stat "$PREFIX/slate-*.json" 2>/dev/null; then
  echo "ERROR: all-boom prefix already holds objects" >&2; exit 2
fi
mkdir -p "$OUT"

gcloud run jobs deploy "$REUSED_JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
  --max-retries 0 --task-timeout 2h \
  --service-account 817589974517-compute@developer.gserviceaccount.com \
  --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
  --command python \
  --args "scripts/run_all_boom_reallocation_c.py,--season,2023,--week,1,--output-uri,$PREFIX/slate-2023-1.json" \
  --quiet >/dev/null
echo "ALLBOOM_JOB_UPDATED $IMAGE"

run_cell() {
  local season=$1 week=$2
  local uri="$PREFIX/slate-${season}-${week}.json"
  local execution
  execution=$(gcloud run jobs execute "$REUSED_JOB" --project "$PROJECT" \
    --region "$REGION" --async --format='value(metadata.name)' \
    --args "scripts/run_all_boom_reallocation_c.py,--season,$season,--week,$week,--output-uri,$uri")
  [[ "$execution" == "$REUSED_JOB-"* ]] || {
    echo "ERROR: all-boom execution identity missing" >&2; exit 2; }
  printf '%s %s %s %s %s\n' "$season" "$week" "$REUSED_JOB" "$execution" "$uri" \
    >> "$EXECUTIONS"
}

run_cell 2023 1
CANARY=$(awk '{print $4}' "$EXECUTIONS")
echo "ALLBOOM_CANARY_LAUNCHED $CANARY"
DEADLINE=$(( $(date +%s) + 7200 ))
while :; do
  STATE=$(gcloud run jobs executions describe "$CANARY" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.conditions[0].status)' 2>/dev/null || echo "")
  printf '%s ALLBOOM_CANARY state=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${STATE:-Unknown}"
  [ "$STATE" = "True" ] && break
  [ "$STATE" = "False" ] && {
    echo "ERROR: all-boom canary failed; halt and disposition" >&2; exit 2; }
  [ "$(date +%s)" -ge "$DEADLINE" ] && {
    echo "ERROR: all-boom canary exceeded two hours" >&2; exit 2; }
  sleep 60
done
gsutil -q stat "$PREFIX/slate-2023-1.json" || {
  echo "ERROR: all-boom canary produced no output" >&2; exit 2; }
echo "ALLBOOM_CANARY_PASSED"

for SEASON in 2023 2024 2025; do
  for WEEK in $(seq 1 18); do
    [ "$SEASON" = 2023 ] && [ "$WEEK" = 1 ] && continue
    run_cell "$SEASON" "$WEEK"
    sleep 2
  done
done
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ERROR: all-boom population is not 54" >&2; exit 2; }
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" "build_id=$BUILD_ID" \
  "output_prefix=$PREFIX" \
  "protocol_sha256=$(sha256sum "$ROOT/reports/2026-08-19-all-boom-reallocation-protocol.md" | awk '{print $1}')" \
  "runner_sha256=$(sha256sum "$ROOT/scripts/run_all_boom_reallocation_c.py" | awk '{print $1}')" \
  "chain_sha256=$(sha256sum "$ROOT/scripts/cloud_all_boom_chain.sh" | awk '{print $1}')" \
  "quota_note=reused job $REUSED_JOB (frozen-chain rule 5)" \
  'uses_realized_outcomes=true' 'production_change_licensed=false' \
  'predeclared_prior=uncertain' 'cells=54' 'canary=2023-1' \
  > "$OUT/manifest.txt"
sha256sum "$OUT/manifest.txt" "$EXECUTIONS" > "$OUT/launch.sha256"
echo "ALLBOOM_GRID_LAUNCHED"

while :; do
  OBJECTS=$(gsutil ls "$PREFIX/slate-*.json" 2>/dev/null | wc -l)
  printf '%s ALLBOOM_GRID objects=%s/54\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$OBJECTS"
  [ "$OBJECTS" -ge 54 ] && break
  while read -r SEASON WEEK JOB EXECUTION URI; do
    gsutil -q stat "$URI" 2>/dev/null && continue
    STATE=$(gcloud run jobs executions describe "$EXECUTION" \
      --project "$PROJECT" --region "$REGION" \
      --format='value(status.conditions[0].status)' 2>/dev/null || echo "")
    if [ "$STATE" = "False" ]; then
      printf '%s ALLBOOM_CELL_FAILED %s %s %s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$SEASON" "$WEEK" "$EXECUTION"
      exit 2
    fi
  done < "$EXECUTIONS"
  sleep 300
done

mkdir -p "$OUT/cells"
gsutil -m cp "$PREFIX/slate-*.json" "$OUT/cells/" >/dev/null 2>&1
"$ROOT/.venv/bin/python" - "$OUT" <<'PY'
import json, sys
from hashlib import sha256
from pathlib import Path
out = Path(sys.argv[1])
cells = sorted(out.glob("cells/slate-*.json"))
if len(cells) != 54:
    raise SystemExit(f"ERROR: all-boom downloaded {len(cells)} cells")
rows = []
for path in cells:
    r = json.loads(path.read_text())
    if r.get("smoke"):
        raise SystemExit(f"ERROR: smoke receipt in grid: {path.name}")
    rows.append({
        "season": int(r["season"]), "week": int(r["week"]),
        "paired_delta_c": float(r["paired_delta_c"]),
        "control_c": float(r["control"]["c_score"]),
        "treatment_c": float(r["treatment"]["c_score"]),
        "control": r["control"], "treatment": r["treatment"],
        "sha256": sha256(path.read_bytes()).hexdigest(),
    })
deltas = [r["paired_delta_c"] for r in rows]
report = {
    "run_id": "20260819-all-boom-reallocation-c-v1",
    "predeclared_prior": "uncertain",
    "uses_realized_outcomes": True,
    "production_change_licensed": False,
    "n_slates": len(rows),
    "mean_paired_delta_c": sum(deltas) / len(deltas),
    "treatment_better": sum(d > 0 for d in deltas),
    "control_better": sum(d < 0 for d in deltas),
    "tied": sum(d == 0 for d in deltas),
    "mean_control_c": sum(r["control_c"] for r in rows) / len(rows),
    "mean_treatment_c": sum(r["treatment_c"] for r in rows) / len(rows),
    "per_slate": rows,
}
target = out / "aggregate-report.json"
if target.exists():
    raise SystemExit("ERROR: aggregate exists (create-only)")
payload = json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
target.write_text(payload)
print("ALLBOOM_AGGREGATED",
      f"mean_delta_c={report['mean_paired_delta_c']:.4f}",
      f"treatment_better={report['treatment_better']}/54",
      f"sha256={sha256(payload.encode()).hexdigest()}")
PY
sha256sum "$OUT/aggregate-report.json" "$EXECUTIONS" "$OUT/manifest.txt" \
  > "$OUT/finish.sha256"
echo "ALLBOOM_FINISHED $RUN_ID"
