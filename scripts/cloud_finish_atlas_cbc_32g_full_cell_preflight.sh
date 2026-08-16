#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-cbc-32g-full-cell-preflight-v1
OUT="$ROOT/reports/atlas-cbc-32g-full-cell-preflight-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"
RENDERER="$ROOT/scripts/render_atlas_matched_diversity_repair4_command.py"

[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] && \
  [ "$(wc -l < "$EXECUTION")" = 1 ] || {
  echo "ABORT: ATLAS 32-GiB preflight launch receipt differs" >&2; exit 2; }
[ ! -e "$OUT/completion.txt" ] && [ ! -e "$OUT/execution-metadata.json" ] && \
  [ ! -e "$OUT/shard.json" ] || {
  echo "ABORT: immutable ATLAS 32-GiB preflight harvest exists" >&2; exit 3; }

read -r SEASON WEEK JOB EXEC URI < "$EXECUTION"
META="$OUT/execution-metadata.pending.json"
gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$META"
STATUS=$("$ROOT/.venv/bin/python" - "$META" "$MANIFEST" "$RENDERER" \
  "$SEASON" "$WEEK" "$JOB" "$EXEC" "$URI" <<'PY'
from hashlib import sha256
import json, subprocess, sys
meta=json.load(open(sys.argv[1],encoding="utf-8"))
m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
renderer=sys.argv[3]; season,week,job,execution,uri=sys.argv[4:]
if season!="2023" or week!="8" or job!="atlas-cbc-32g-full-2023-w8-v1" or meta.get("metadata",{}).get("name")!=execution:
 raise SystemExit("ABORT: ATLAS 32-GiB preflight identity differs")
s=meta.get("status",{}); done=[r for r in s.get("conditions",[]) if r.get("type")=="Completed"]
if len(done)!=1 or done[0].get("status") not in {"True","False"} or not s.get("completionTime"):
 raise SystemExit("ABORT: ATLAS 32-GiB preflight is not terminal")
spec=meta.get("spec",{}); task=spec.get("template",{}).get("spec",{}); containers=task.get("containers",[])
if spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(containers)!=1:
 raise SystemExit("ABORT: ATLAS 32-GiB preflight task shape differs")
command=subprocess.check_output([
 sys.executable,renderer,"--replacement-prefix",m["output_prefix"],
],text=True).strip()
if sha256(command.encode()).hexdigest()!=m["command_sha256"]:
 raise SystemExit("ABORT: ATLAS 32-GiB preflight command hash differs")
container=containers[0]
expected=["-c",command,"--season","2023","--week","8","--output-uri",uri]
if container.get("image")!=m["image"] or container.get("command")!=["python"] or container.get("args")!=expected:
 raise SystemExit("ABORT: ATLAS 32-GiB preflight command/image differs")
env={r.get("name"):str(r.get("value","")) for r in container.get("env",[])}
if env!={"CODE_SHA":m["code_sha"],"ANALYSIS_IMAGE":m["image"]} or container.get("resources",{}).get("limits")!={"cpu":"8","memory":"32Gi"}:
 raise SystemExit("ABORT: ATLAS 32-GiB preflight environment/resources differ")
if task.get("maxRetries")!=0 or str(task.get("timeoutSeconds"))!="43200" or task.get("serviceAccountName")!="817589974517-compute@developer.gserviceaccount.com":
 raise SystemExit("ABORT: ATLAS 32-GiB preflight retry/timeout/account differs")
print(done[0]["status"])
PY
)

if [ "$STATUS" = True ]; then
  gcloud storage cp "$URI" "$OUT/shard.pending.json" \
    --project "$PROJECT" >/dev/null
  "$ROOT/.venv/bin/python" - "$OUT/shard.pending.json" "$MANIFEST" <<'PY'
import json, sys
r=json.load(open(sys.argv[1],encoding="utf-8"))
m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
if r.get("version")!="atlas-matched-diversity-mvp-v1" or r.get("uses_realized_outcomes") is not False or r.get("season")!=2023 or r.get("shard_week")!=8 or r.get("code_sha")!=m["code_sha"] or r.get("analysis_image")!=m["image"] or len(r.get("slates",[]))!=1:
 raise SystemExit("ABORT: ATLAS 32-GiB preflight shard identity differs")
row=r["slates"][0]
if row.get("season")!=2023 or row.get("week")!=8 or row.get("mechanical_valid") is not True or row.get("uses_realized_outcomes") is not False or row.get("global_atlas_additions")!=200 or set(row.get("native_boom_counts",{}).values())!={40}:
 raise SystemExit("ABORT: ATLAS 32-GiB preflight shard mechanics differ")
PY
  mv "$OUT/shard.pending.json" "$OUT/shard.json"
  sha256sum "$OUT/shard.json" > "$OUT/shard.sha256"
  DISPOSITION=full-cell-r0-complete-at-32g
else
  DISPOSITION=full-cell-failed-at-32g
fi

mv "$META" "$OUT/execution-metadata.json"
sha256sum "$OUT/execution-metadata.json" > "$OUT/execution-metadata.sha256"
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  "status=$STATUS" "disposition=$DISPOSITION" 'cell=2023-8' \
  'cpu=8' 'memory=32Gi' 'max_retries=0' \
  'uses_realized_outcomes=false' 'production_change_licensed=false' \
  > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "ATLAS_CBC_32G_FULL_CELL_PREFLIGHT_HARVESTED $DISPOSITION"
