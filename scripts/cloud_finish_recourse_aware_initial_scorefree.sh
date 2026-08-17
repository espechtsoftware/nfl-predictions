#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260817-recourse-aware-initial-book-scorefree-v1
OUT="$ROOT/reports/recourse-aware-initial-book-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
RUNNER="$ROOT/scripts/run_recourse_aware_initial_scorefree.py"
AGGREGATOR="$ROOT/scripts/aggregate_recourse_aware_initial_scorefree.py"
CANARY_WAITER="$ROOT/scripts/cloud_wait_recourse_aware_initial_canary.sh"
CANARY_VALIDATOR="$ROOT/scripts/validate_recourse_aware_initial_canary.py"
LAUNCHER="$ROOT/scripts/cloud_recourse_aware_initial_scorefree.sh"
FINISHER="$ROOT/scripts/cloud_finish_recourse_aware_initial_scorefree.sh"
WATCHER="$ROOT/scripts/watch_recourse_aware_initial_queue.sh"

[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] && \
  [ -s "$OUT/build-metadata.json" ] && [ -s "$OUT/queue-release.json" ] && \
  [ -s "$OUT/canary-completion.json" ] && \
  [ -s "$OUT/canary-execution-metadata.json" ] && \
  [ -s "$OUT/canary-object-metadata.json" ] && \
  [ -s "$OUT/canary-shard.json" ] && [ -s "$OUT/grid-release.txt" ] || {
  echo "ABORT: recourse-aware launch receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ABORT: recourse-aware execution grid is not 54" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/completion.txt" ] && \
  [ ! -e "$OUT/execution-metadata" ] && [ ! -e "$OUT/object-metadata" ] && \
  [ ! -e "$OUT/shards" ] || {
  echo "ABORT: immutable recourse-aware harvest exists" >&2; exit 3; }

"$ROOT/.venv/bin/python" - "$MANIFEST" "$EXECUTIONS" \
  "$OUT/build-metadata.json" "$OUT/queue-release.json" \
  "$OUT/canary-completion.json" "$OUT/grid-release.txt" \
  "$RUNNER" "$AGGREGATOR" "$CANARY_WAITER" "$CANARY_VALIDATOR" \
  "$LAUNCHER" "$FINISHER" "$WATCHER" <<'PY'
from hashlib import sha256
import json, pathlib, re, sys
manifest_path, ledger_path, build_path, release_path, canary_path, grid_path, runner, aggregator, waiter, validator, launcher, finisher, watcher = map(pathlib.Path,sys.argv[1:])
m=dict(line.split("=",1) for line in manifest_path.read_text().splitlines() if "=" in line)
fixed={"run_id":"20260817-recourse-aware-initial-book-scorefree-v1","output_prefix":"gs://nfl-predictions-503414-raw/research/recourse-aware-initial-book-runs/20260817-recourse-aware-initial-book-scorefree-v1","science_protocol_sha256":"0085b5f77b4e859982fc4f664161cdafe2bb6ec07ea0351fb618ddf58319c077","execution_protocol_sha256":"3991fdbf36c2018b2ec11625a6be62990c100fdf1f47bde3985c2327e3248c9b","cbwu_report_sha256":"556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33","forensic_manifest_sha256":"51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02","source_panels":"20260813-sis-asoe-treatment-r0-v1,20260813-sis-asoe-treatment-r1-v1,20260813-sis-asoe-treatment-r2-v1,20260813-sis-asoe-treatment-r3-v1,20260813-sis-asoe-treatment-r4-v1","seasons":"2023,2024,2025","weeks":"1-18","slates":"54","folds":"270","cpu":"4","memory":"16Gi","timeout_seconds":"14400","max_retries":"0","uses_realized_outcomes":"false","production_change_licensed":"false","historical_scoring_licensed":"false"}
for key,value in fixed.items():
 if m.get(key)!=value: raise SystemExit(f"ABORT: recourse-aware manifest differs: {key}")
if not re.fullmatch(r"[0-9a-f]{40}",m.get("code_sha","")) or not re.fullmatch(r".+@sha256:[0-9a-f]{64}",m.get("image","")):
 raise SystemExit("ABORT: recourse-aware code/image differs")
for key,path in (("runner_sha256",runner),("aggregator_sha256",aggregator),("canary_waiter_sha256",waiter),("canary_validator_sha256",validator),("launcher_sha256",launcher),("finisher_sha256",finisher),("watcher_sha256",watcher)):
 if m.get(key)!=sha256(path.read_bytes()).hexdigest(): raise SystemExit(f"ABORT: recourse-aware source binding differs: {key}")
b=json.loads(build_path.read_text()); release=json.loads(release_path.read_text()); canary=json.loads(canary_path.read_text())
if m.get("build_metadata_sha256")!=sha256(build_path.read_bytes()).hexdigest() or b.get("id")!=m.get("build_id") or b.get("status")!="SUCCESS": raise SystemExit("ABORT: recourse-aware build binding differs")
if m.get("queue_release_sha256")!=sha256(release_path.read_bytes()).hexdigest() or release.get("version")!="recourse-aware-queue-release-v1" or release.get("branch")!=m.get("queue_release_branch") or release.get("branch") not in {"preflight-failed-parity-closed","repair5-valid-historical-closed","repair5-failed-parity-closed"}: raise SystemExit("ABORT: recourse-aware queue release differs")
for raw,digest in release.get("bindings",{}).items():
 path=pathlib.Path(raw)
 if not path.is_file() or sha256(path.read_bytes()).hexdigest()!=digest: raise SystemExit("ABORT: recourse-aware queue binding differs")
if canary.get("status") is not True or canary.get("disposition")!="actual-final-path-canary-passes" or canary.get("remaining_cells_released") is not False or canary.get("outcome_fields_inspected") is not False or canary.get("effect_fields_inspected") is not False: raise SystemExit("ABORT: recourse-aware canary disposition differs")
g=dict(line.split("=",1) for line in grid_path.read_text().splitlines() if "=" in line)
if g.get("primary_executions")!="54" or g.get("released_after_canary")!="53" or g.get("canary_completion_sha256")!=sha256(canary_path.read_bytes()).hexdigest() or g.get("outcome_fields_inspected")!="false" or g.get("effect_fields_inspected")!="false": raise SystemExit("ABORT: recourse-aware grid release differs")
rows=[line.split() for line in ledger_path.read_text().splitlines() if line]
expected={(str(s),str(w)) for s in (2023,2024,2025) for w in range(1,19)}
if len(rows)!=54 or any(len(row)!=5 for row in rows) or {(row[0],row[1]) for row in rows}!=expected or len({row[3] for row in rows})!=54: raise SystemExit("ABORT: recourse-aware execution ledger differs")
for season,week,job,execution,uri in rows:
 if job!=f"recourse-initial-s{season}-w{week}-v1" or not execution.startswith(job+"-") or uri!=f"{m['output_prefix']}/slate-{season}-{week}.json": raise SystemExit("ABORT: recourse-aware execution identity differs")
PY

mkdir -p "$OUT/execution-metadata.pending" "$OUT/object-metadata.pending" \
  "$OUT/shards.pending"
while read -r SEASON WEEK JOB EXEC URI; do
  LISTED=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
    --region "$REGION" --format='value(metadata.name)')
  [ "$LISTED" = "$EXEC" ] || {
    echo "ABORT: recourse-aware job execution population differs: $JOB" >&2; exit 2; }
  META="$OUT/execution-metadata.pending/${EXEC}.json"
  gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format=json > "$META"
  "$ROOT/.venv/bin/python" - "$META" "$MANIFEST" "$EXEC" "$SEASON" \
    "$WEEK" "$URI" <<'PY'
import json,sys
x=json.load(open(sys.argv[1])); m=dict(line.split("=",1) for line in open(sys.argv[2]) if "=" in line)
name,season,week,uri=sys.argv[3:]
s=x.get("status",{}); done=[row for row in s.get("conditions",[]) if row.get("type")=="Completed"]
spec=x.get("spec",{}); task=spec.get("template",{}).get("spec",{}); containers=task.get("containers",[])
if x.get("metadata",{}).get("name")!=name or len(done)!=1 or done[0].get("status")!="True" or int(s.get("succeededCount") or 0)!=1 or int(s.get("failedCount") or 0)!=0 or int(s.get("retriedCount") or 0)!=0 or not s.get("completionTime") or spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(containers)!=1: raise SystemExit("ABORT: recourse-aware execution mechanics differ")
c=containers[0]; expected=["scripts/run_recourse_aware_initial_scorefree.py","--season",season,"--week",week,"--output-uri",uri]
env={row.get("name"):str(row.get("value","")) for row in c.get("env",[])}
if c.get("image")!=m["image"] or c.get("command")!=["python"] or c.get("args")!=expected or env!={"CODE_SHA":m["code_sha"],"ANALYSIS_IMAGE":m["image"]} or c.get("resources",{}).get("limits")!={"cpu":"4","memory":"16Gi"} or task.get("maxRetries")!=0 or str(task.get("timeoutSeconds"))!="14400" or task.get("serviceAccountName")!="817589974517-compute@developer.gserviceaccount.com": raise SystemExit("ABORT: recourse-aware execution contract differs")
PY
  OBJECT="$OUT/object-metadata.pending/slate-${SEASON}-${WEEK}.json"
  gcloud storage objects describe "$URI" --project "$PROJECT" --format=json \
    > "$OBJECT"
  SHARD="$OUT/shards.pending/slate-${SEASON}-${WEEK}.json"
  gcloud storage cp "$URI" "$SHARD" --project "$PROJECT" >/dev/null
  "$ROOT/.venv/bin/python" - "$OBJECT" "$SHARD" <<'PY'
import json,sys
m=json.load(open(sys.argv[1])); raw=open(sys.argv[2],"rb").read()
if not str(m.get("generation","")).isdigit() or int(m.get("size",-1))!=len(raw): raise SystemExit("ABORT: recourse-aware object metadata differs")
json.loads(raw)
PY
done < "$EXECUTIONS"

[ "$(sha256sum "$OUT/shards.pending/slate-2023-1.json" | awk '{print $1}')" = \
  "$(sha256sum "$OUT/canary-shard.json" | awk '{print $1}')" ] || {
  echo "ABORT: recourse-aware canary shard changed after release" >&2; exit 2; }
mv "$OUT/execution-metadata.pending" "$OUT/execution-metadata"
mv "$OUT/object-metadata.pending" "$OUT/object-metadata"
mv "$OUT/shards.pending" "$OUT/shards"
ARGS=()
for SHARD in "$OUT"/shards/slate-*.json; do ARGS+=(--shard-report "$SHARD"); done
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" "$AGGREGATOR" \
  "${ARGS[@]}" --output "$OUT/report.json"

"$ROOT/.venv/bin/python" - "$OUT/report.json" "$MANIFEST" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); m=dict(line.split("=",1) for line in open(sys.argv[2]) if "=" in line)
if r.get("version")!="recourse-aware-initial-book-scorefree-report-v1" or r.get("run_id")!=m["run_id"] or r.get("uses_realized_outcomes") is not False or r.get("production_change_licensed") is not False or r.get("code_sha")!=m["code_sha"] or r.get("analysis_image")!=m["image"]: raise SystemExit("ABORT: recourse-aware aggregate identity/license differs")
if r.get("mechanical")!={"slates":54,"folds":270,"worlds_per_fold":10000,"all_valid":True} or len(r.get("source_artifacts",[]))!=270 or len(r.get("leave_one_slate_out_influence",[]))!=54 or len(r.get("selection_effective_rank",{}).get("by_slate",[]))!=54: raise SystemExit("ABORT: recourse-aware aggregate mechanics differ")
conditions=r.get("conditions",{}); expected={"reachable_p230_strict_and_three_blocks","reachable_p240_p220_p210_nondecline","initial_p240_p230_p220_nondecline","initial_p194_retention_at_least_95pct","mean_reachable_alternatives_nondecline","locked_slot_signature_nondecline"}
if set(conditions)!=expected or r.get("passed") is not all(conditions.values()) or r.get("disposition") not in {"recourse-aware-initial-book-premise-passes","recourse-aware-candidate-union-selector-premise-fails"}: raise SystemExit("ABORT: recourse-aware frozen gate differs")
print("RECOURSE_INITIAL_STRICT_AGGREGATE_VALIDATED",r["disposition"])
PY

PREFIX=$(awk -F= '$1=="output_prefix" {print $2}' "$MANIFEST")
PYTHONPATH="$ROOT/scripts" "$ROOT/.venv/bin/python" - "$OUT/report.json" \
  "$PREFIX/report.json" "$OUT/report-upload.json" <<'PY'
import json,sys
from google.cloud import storage
from run_cbwu_seed_order_audit import _upload_create_only
raw=open(sys.argv[1],"rb").read(); receipt=_upload_create_only(storage.Client(project="nfl-predictions-503414"),sys.argv[2],raw)
open(sys.argv[3],"w").write(json.dumps(receipt,sort_keys=True,separators=(",",":"))+"\n")
PY

sha256sum "$OUT/report.json" > "$OUT/report.sha256"
sha256sum "$OUT/report-upload.json" > "$OUT/report-upload.sha256"
sha256sum "$OUT"/execution-metadata/*.json | sort > "$OUT/execution-metadata.sha256"
sha256sum "$OUT"/object-metadata/*.json | sort > "$OUT/object-metadata.sha256"
sha256sum "$OUT"/shards/*.json | sort > "$OUT/shards.sha256"
DISPOSITION=$("$ROOT/.venv/bin/python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["disposition"])' "$OUT/report.json")
PASS=$("$ROOT/.venv/bin/python" -c 'import json,sys; print(str(json.load(open(sys.argv[1]))["passed"]).lower())' "$OUT/report.json")
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'executions=54' 'slates=54' 'folds=270' 'source_artifacts=270' \
  'uses_realized_outcomes=false' 'production_change_licensed=false' \
  "historical_policy_diagnostic_licensed=$PASS" \
  "passes_scorefree_gate=$PASS" "disposition=$DISPOSITION" \
  "executions_sha256=$(sha256sum "$EXECUTIONS" | awk '{print $1}')" \
  "canary_completion_sha256=$(sha256sum "$OUT/canary-completion.json" | awk '{print $1}')" \
  "grid_release_sha256=$(sha256sum "$OUT/grid-release.txt" | awk '{print $1}')" \
  > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "RECOURSE_INITIAL_HARVESTED $RUN_ID $DISPOSITION"
