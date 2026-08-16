#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-matched-diversity-mvp-v1-repair2
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
ORIGINAL_LEDGER="$OUT/executions.txt"
EFFECTIVE_LEDGER="$OUT/effective-executions.txt"
PROTOCOL="$ROOT/reports/2026-08-16-atlas-mvp-cbc-single-shard-retry.md"
PROTOCOL_SHA=bc55775c5a98a7027a0c117cf5371a67cc886c6da34dcdb7b1031bd6a471c455
MANIFEST_SHA=080c85700219ac246b093f2556c474f4bd79257809cf0e006766a1ed48e95d24
ORIGINAL_LEDGER_SHA=6794f8e608497613aec2f06f2bd13e57cf08b945d7ac20e2d4d00eb1ee3d5ea5
SEASON=2024
WEEK=7
JOB=atlas-md-s2024-w7-r2
ORIGINAL_EXEC=atlas-md-s2024-w7-r2-r9gnq
URI=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair2/slate-2024-7.json

[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || {
  echo "ERROR: ATLAS CBC retry protocol differs" >&2; exit 2; }
[ "$(sha256sum "$MANIFEST" | awk '{print $1}')" = "$MANIFEST_SHA" ] || {
  echo "ERROR: ATLAS repair2 manifest differs" >&2; exit 2; }
[ "$(sha256sum "$ORIGINAL_LEDGER" | awk '{print $1}')" = "$ORIGINAL_LEDGER_SHA" ] || {
  echo "ERROR: ATLAS original execution ledger differs" >&2; exit 2; }
[ "$(awk -v s="$SEASON" -v w="$WEEK" '$1==s && $2==w {print $4}' "$ORIGINAL_LEDGER")" = "$ORIGINAL_EXEC" ] || {
  echo "ERROR: ATLAS failed execution is not the registered cell" >&2; exit 2; }
[ ! -e "$OUT/failed-execution.json" ] && \
  [ ! -e "$OUT/failed-log.json" ] && \
  [ ! -e "$OUT/replacement-execution.txt" ] && \
  [ ! -e "$EFFECTIVE_LEDGER" ] || {
  echo "ERROR: immutable ATLAS CBC retry receipt already exists" >&2; exit 3; }
if gcloud storage objects describe "$URI" --project "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: ATLAS failed shard target already exists" >&2
  exit 3
fi

FAIL_TMP="$OUT/failed-execution.pending.json"
gcloud run jobs executions describe "$ORIGINAL_EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$FAIL_TMP"
"$ROOT/.venv/bin/python" - "$FAIL_TMP" "$MANIFEST" "$ORIGINAL_EXEC" "$URI" <<'PY'
import json, sys
x=json.load(open(sys.argv[1],encoding="utf-8")); m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
name,uri=sys.argv[3],sys.argv[4]
if x.get("metadata",{}).get("name")!=name:
 raise SystemExit("ERROR: ATLAS failed execution name differs")
s=x.get("status",{}); done=[r for r in s.get("conditions",[]) if r.get("type")=="Completed"]
if len(done)!=1 or done[0].get("status")!="False" or done[0].get("reason")!="NonZeroExitCode" or int(s.get("failedCount") or 0)!=1 or int(s.get("succeededCount") or 0)!=0 or not s.get("completionTime"):
 raise SystemExit("ERROR: ATLAS original failure receipt differs")
spec=x.get("spec",{}); t=spec.get("template",{}).get("spec",{}); cs=t.get("containers",[])
if spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(cs)!=1:
 raise SystemExit("ERROR: ATLAS failed task shape differs")
c=cs[0]
if c.get("image")!=m["image"] or c.get("command")!=["python"] or c.get("args")!=["scripts/run_atlas_matched_diversity_mvp.py","--season","2024","--week","7","--output-uri",uri]:
 raise SystemExit("ERROR: ATLAS failed command/image differs")
env={r.get("name"):str(r.get("value","")) for r in c.get("env",[])}
if env!={"CODE_SHA":m["code_sha"],"ANALYSIS_IMAGE":m["image"]}:
 raise SystemExit("ERROR: ATLAS failed environment differs")
if c.get("resources",{}).get("limits")!={"cpu":"1","memory":"4Gi"} or t.get("maxRetries")!=0 or str(t.get("timeoutSeconds"))!="43200" or t.get("serviceAccountName")!="817589974517-compute@developer.gserviceaccount.com":
 raise SystemExit("ERROR: ATLAS failed resources/account differ")
PY
mv "$FAIL_TMP" "$OUT/failed-execution.json"
sha256sum "$OUT/failed-execution.json" > "$OUT/failed-execution.sha256"

LOG_TMP="$OUT/failed-log.pending.json"
gcloud logging read \
  "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"$JOB\"" \
  --project "$PROJECT" --freshness=6h --limit=200 --order=asc --format=json \
  > "$LOG_TMP"
"$ROOT/.venv/bin/python" - "$LOG_TMP" <<'PY'
import json, sys
rows=json.load(open(sys.argv[1],encoding="utf-8"))
raw=json.dumps(rows,sort_keys=True)
if "PulpSolverError" not in raw or "ATLAS_MVP_SEED_COMPLETE" in raw or "ATLAS_MVP_SLATE_COMPLETE" in raw:
 raise SystemExit("ERROR: ATLAS failed mechanical log signature differs")
PY
mv "$LOG_TMP" "$OUT/failed-log.json"
sha256sum "$OUT/failed-log.json" > "$OUT/failed-log.sha256"

REPLACEMENT=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$REPLACEMENT" ] && [ "$REPLACEMENT" != "$ORIGINAL_EXEC" ] || {
  echo "ERROR: ATLAS replacement execution identity is missing" >&2; exit 1; }
printf '%s %s %s %s %s\n' "$SEASON" "$WEEK" "$JOB" "$REPLACEMENT" "$URI" \
  > "$OUT/replacement-execution.txt"
sha256sum "$OUT/replacement-execution.txt" > "$OUT/replacement-execution.sha256"

awk -v s="$SEASON" -v w="$WEEK" -v replacement="$REPLACEMENT" \
  'BEGIN{changed=0} $1==s && $2==w {$4=replacement; changed++} {print} END{if(changed!=1) exit 4}' \
  "$ORIGINAL_LEDGER" > "$EFFECTIVE_LEDGER"
"$ROOT/.venv/bin/python" - "$ORIGINAL_LEDGER" "$EFFECTIVE_LEDGER" "$ORIGINAL_EXEC" "$REPLACEMENT" <<'PY'
import sys
left=[line.split() for line in open(sys.argv[1],encoding="utf-8") if line.strip()]
right=[line.split() for line in open(sys.argv[2],encoding="utf-8") if line.strip()]
if len(left)!=54 or len(right)!=54:
 raise SystemExit("ERROR: ATLAS effective execution grid differs")
diffs=[]
for a,b in zip(left,right,strict=True):
 if a!=b: diffs.append((a,b))
if len(diffs)!=1 or diffs[0][0][:3]+diffs[0][0][4:]!=diffs[0][1][:3]+diffs[0][1][4:] or diffs[0][0][0:2]!=["2024","7"] or diffs[0][0][3]!=sys.argv[3] or diffs[0][1][3]!=sys.argv[4]:
 raise SystemExit("ERROR: ATLAS effective ledger changes more than execution identity")
PY
sha256sum "$EFFECTIVE_LEDGER" > "$OUT/effective-executions.sha256"
echo "ATLAS_MVP_CBC_SINGLE_SHARD_RETRY_LAUNCHED $REPLACEMENT"
