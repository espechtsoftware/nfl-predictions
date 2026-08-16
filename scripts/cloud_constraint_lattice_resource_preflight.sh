#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_constraint_lattice_resource_preflight.sh <image@sha256:...> <code-sha> <build-id>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-constraint-lattice-resource-preflight-v1
OUT="$ROOT/reports/constraint-lattice-resource-preflight-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/constraint-lattice-resource-preflight-runs/$RUN_ID
URI="$PREFIX/slate-2023-1.json"
PROTOCOL="$ROOT/reports/2026-08-16-constraint-lattice-resource-preflight-protocol.md"
PROTOCOL_SHA=9e04ebcbcb2def607e28c5f8fa046ba4456f40e2e8a654182f654318ca579d7b
SUPPORT="$ROOT/reports/constraint-lattice-support-runs/20260816-constraint-lattice-control-support-census-v1"
RUNNER="$ROOT/scripts/run_constraint_lattice_resource_preflight.py"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable lattice-resource image is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full lattice-resource source commit is required" >&2; exit 2; }
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "ERROR: successful lattice-resource Cloud Build ID is required" >&2; exit 2; }
git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}" || {
  echo "ERROR: lattice-resource source commit is unavailable" >&2; exit 2; }
for RELATIVE in \
  Dockerfile cloudbuild.yaml \
  reports/2026-08-16-constraint-lattice-scorefree-protocol.md \
  reports/2026-08-16-constraint-lattice-source-and-execution-amendment.md \
  reports/2026-08-16-constraint-lattice-control-support-census-protocol.md \
  reports/2026-08-16-constraint-lattice-resource-preflight-protocol.md \
  reports/cbwu-order-invariant-runs/20260815-cbwu-order-invariant-repair-v1/report.json \
  scripts/run_constraint_lattice_scorefree.py \
  scripts/run_constraint_lattice_resource_preflight.py \
  src/nfl_dfs/analysis/constraint_lattice.py \
  src/nfl_dfs/analysis/atlas_world_ranking.py \
  src/nfl_dfs/inference/multiseed_portfolio.py \
  src/nfl_dfs/optimizer/lineup.py; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: lattice-resource built source differs: $RELATIVE" >&2; exit 2; }
done
[ -s "$PROTOCOL" ] && \
  [ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || {
  echo "ERROR: frozen lattice-resource protocol differs" >&2; exit 2; }
[ -s "$SUPPORT/completion.txt" ] && [ -s "$SUPPORT/report.json" ] || {
  echo "ERROR: lattice-resource awaits strict control support census" >&2; exit 2; }
"$ROOT/.venv/bin/python" - "$SUPPORT/completion.txt" "$SUPPORT/report.json" <<'PY'
import json, sys
c=dict(line.split("=",1) for line in open(sys.argv[1],encoding="utf-8") if "=" in line)
r=json.load(open(sys.argv[2],encoding="utf-8"))
allowed={"p230-supported-original-gate-complete","reanchor-required-p220","reanchor-required-p210"}
if c.get("disposition") not in allowed or r.get("disposition")!=c.get("disposition") or str(r.get("selected_anchor"))!=c.get("selected_anchor") or r.get("uses_realized_outcomes") is not False or r.get("treatment_constructed") is not False or r.get("mechanical",{}).get("heldout_folds")!=270:
 raise SystemExit("ERROR: lattice-resource support release differs")
PY
[ ! -e "$OUT" ] || {
  echo "ERROR: immutable lattice-resource local run exists" >&2; exit 3; }
if gcloud storage ls "$PREFIX/**" --project "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: immutable lattice-resource cloud prefix exists" >&2; exit 3
fi

mkdir -p "$OUT"
gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format=json \
  > "$OUT/build-metadata.json"
"$ROOT/.venv/bin/python" - "$OUT/build-metadata.json" "$IMAGE" "$CODE_SHA" <<'PY'
import json, sys
b=json.load(open(sys.argv[1],encoding="utf-8")); image=sys.argv[2]; code=sys.argv[3]
digest=image.rsplit("@",1)[1]
tag=f"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:constraint-support-{code[:7]}"
images=b.get("results",{}).get("images",[]); steps={row.get("id"):row.get("status") for row in b.get("steps",[])}
if b.get("status")!="SUCCESS" or b.get("substitutions",{}).get("_IMAGE")!=tag:
 raise SystemExit("ERROR: lattice-resource build identity differs")
if not any(row.get("digest")==digest and row.get("name")==tag for row in images):
 raise SystemExit("ERROR: lattice-resource image digest differs")
if steps.get("full-test-suite")!="SUCCESS" or steps.get("smoke-atlas-mvp-runner")!="SUCCESS":
 raise SystemExit("ERROR: lattice-resource build steps differ")
PY

printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" "build_id=$BUILD_ID" \
  "output_prefix=$PREFIX" "output_uri=$URI" "protocol_sha256=$PROTOCOL_SHA" \
  "runner_sha256=$(sha256sum "$RUNNER" | awk '{print $1}')" \
  "support_completion_sha256=$(sha256sum "$SUPPORT/completion.txt" | awk '{print $1}')" \
  "support_report_sha256=$(sha256sum "$SUPPORT/report.json" | awk '{print $1}')" \
  "support_disposition=$(awk -F= '$1=="disposition" {print $2}' "$SUPPORT/completion.txt")" \
  'cell=2023-1' 'source_artifact_bytes=163064634' \
  'cpu=4' 'memory=16Gi' 'timeout_seconds=43200' 'max_retries=0' \
  'uses_realized_outcomes=false' 'effect_fields_inspected=false' \
  'production_change_licensed=false' > "$OUT/manifest.txt"

JOB=constraint-lattice-resource-2023-w1-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
  --max-retries 0 --task-timeout 12h --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
  --command python \
  --args "scripts/run_constraint_lattice_resource_preflight.py,--output-uri,$URI" \
  --quiet >/dev/null
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[[ "$EXEC" == "$JOB-"* ]] || {
  echo "ERROR: lattice-resource execution identity missing" >&2; exit 2; }
printf '%s %s %s\n' "$JOB" "$EXEC" "$URI" > "$OUT/execution.txt"
sha256sum "$OUT/manifest.txt" "$OUT/execution.txt" \
  "$OUT/build-metadata.json" > "$OUT/launch.sha256"
echo "CONSTRAINT_LATTICE_RESOURCE_PREFLIGHT_LAUNCHED $EXEC"
