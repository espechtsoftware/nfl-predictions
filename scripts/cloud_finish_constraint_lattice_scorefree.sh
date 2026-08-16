#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-constraint-lattice-scorefree-v1
OUT="$ROOT/reports/constraint-lattice-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
RUNNER="$ROOT/scripts/run_constraint_lattice_scorefree.py"
AGGREGATOR="$ROOT/scripts/aggregate_constraint_lattice_scorefree.py"
SUPPORT="$ROOT/reports/constraint-lattice-support-runs/20260816-constraint-lattice-control-support-census-v1"
RESOURCE="$ROOT/reports/constraint-lattice-resource-preflight-runs/20260816-constraint-lattice-resource-preflight-v1"

[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] && \
  [ -s "$OUT/build-metadata.json" ] && [ -s "$OUT/queue-release.json" ] && \
  [ -s "$SUPPORT/completion.txt" ] && [ -s "$SUPPORT/report.json" ] && \
  [ -s "$RESOURCE/completion.txt" ] && \
  [ -s "$RESOURCE/execution-metadata.json" ] && \
  [ -s "$RESOURCE/object-metadata.json" ] || {
  echo "ABORT: constraint-lattice launch receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ABORT: constraint-lattice execution grid is not 54" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/execution-metadata" ] && \
  [ ! -e "$OUT/shards" ] && [ ! -e "$OUT/object-metadata" ] || {
  echo "ABORT: immutable constraint-lattice harvest already exists" >&2; exit 3; }

"$ROOT/.venv/bin/python" - "$MANIFEST" "$EXECUTIONS" "$OUT/build-metadata.json" \
  "$RUNNER" "$AGGREGATOR" "$OUT/queue-release.json" "$SUPPORT" "$RESOURCE" <<'PY'
from hashlib import sha256
import json, pathlib, re, sys
m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[1],encoding="utf-8") if "=" in line)
rows=[line.split() for line in open(sys.argv[2],encoding="utf-8") if line.strip()]
b=json.load(open(sys.argv[3],encoding="utf-8")); runner=pathlib.Path(sys.argv[4]); aggregator=pathlib.Path(sys.argv[5]); release_path=pathlib.Path(sys.argv[6]); release=json.loads(release_path.read_text()); support=pathlib.Path(sys.argv[7]); resource=pathlib.Path(sys.argv[8])
fixed={
 "run_id":"20260816-constraint-lattice-scorefree-v1",
 "output_prefix":"gs://nfl-predictions-503414-raw/research/constraint-lattice-runs/20260816-constraint-lattice-scorefree-v1",
 "protocol_sha256":"f8591d24dd56749e5b56235f9636687fd41bd1a78991fdb60cfbb092ee65bf62",
 "source_amendment_sha256":"35ea1f0dba3be5311631d51057c7667cb624bcdc19be75e2b202c57e297e8321",
 "cbwu_report_sha256":"556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33",
 "source_panels":"20260813-sis-asoe-treatment-r0-v1,20260813-sis-asoe-treatment-r1-v1,20260813-sis-asoe-treatment-r2-v1,20260813-sis-asoe-treatment-r3-v1,20260813-sis-asoe-treatment-r4-v1",
 "forensic_manifest_sha256":"51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02",
 "seasons":"2023,2024,2025", "weeks":"1-18", "slates":"54", "folds":"270",
 "cpu":"4", "memory":"16Gi", "timeout_seconds":"43200", "max_retries":"0",
 "uses_realized_outcomes":"false", "production_change_licensed":"false",
 "historical_scoring_licensed":"false",
 "support_disposition":"p230-supported-original-gate-complete",
 "resource_disposition":"full-cell-complete-at-16g",
}
for key,value in fixed.items():
 if m.get(key)!=value: raise SystemExit(f"ABORT: constraint-lattice manifest differs: {key}")
if not re.fullmatch(r"[0-9a-f]{40}",m.get("code_sha","")) or not re.fullmatch(r".+@sha256:[0-9a-f]{64}",m.get("image","")):
 raise SystemExit("ABORT: constraint-lattice code/image manifest differs")
for key,path in (("runner_sha256",runner),("aggregator_sha256",aggregator)):
 if m.get(key)!=sha256(path.read_bytes()).hexdigest():
  raise SystemExit(f"ABORT: constraint-lattice implementation differs: {key}")
if m.get("build_metadata_sha256")!=sha256(pathlib.Path(sys.argv[3]).read_bytes()).hexdigest() or b.get("id")!=m.get("build_id") or b.get("status")!="SUCCESS":
 raise SystemExit("ABORT: constraint-lattice build receipt differs")
if m.get("queue_release_sha256")!=sha256(release_path.read_bytes()).hexdigest() or release.get("version")!="constraint-lattice-queue-release-v1" or release.get("branch")!=m.get("queue_release_branch") or release.get("branch") not in {"preflight-failed-parity-closed","repair5-valid-historical-closed","repair5-failed-parity-closed"}:
 raise SystemExit("ABORT: constraint-lattice queue release differs")
for raw_path,digest in release.get("bindings",{}).items():
 path=pathlib.Path(raw_path)
 if not path.is_file() or sha256(path.read_bytes()).hexdigest()!=digest:
  raise SystemExit("ABORT: constraint-lattice queue binding differs")
if m.get("support_completion_sha256")!=sha256((support/"completion.txt").read_bytes()).hexdigest() or m.get("support_report_sha256")!=sha256((support/"report.json").read_bytes()).hexdigest():
 raise SystemExit("ABORT: constraint-lattice support binding differs")
support_report=json.loads((support/"report.json").read_text())
if support_report.get("selected_anchor")!=230 or support_report.get("disposition")!="p230-supported-original-gate-complete" or support_report.get("treatment_constructed") is not False:
 raise SystemExit("ABORT: constraint-lattice p230 support differs")
for key,name in (("resource_completion_sha256","completion.txt"),("resource_execution_metadata_sha256","execution-metadata.json"),("resource_object_metadata_sha256","object-metadata.json")):
 if m.get(key)!=sha256((resource/name).read_bytes()).hexdigest():
  raise SystemExit(f"ABORT: constraint-lattice resource binding differs: {key}")
resource_completion=dict(line.split("=",1) for line in (resource/"completion.txt").read_text().splitlines() if "=" in line)
if resource_completion.get("status")!="True" or resource_completion.get("disposition")!="full-cell-complete-at-16g" or resource_completion.get("object_content_inspected")!="false" or resource_completion.get("effect_fields_inspected")!="false":
 raise SystemExit("ABORT: constraint-lattice resource preflight differs")
expected={(str(s),str(w)) for s in (2023,2024,2025) for w in range(1,19)}
if len(rows)!=54 or any(len(row)!=5 for row in rows) or {(row[0],row[1]) for row in rows}!=expected:
 raise SystemExit("ABORT: constraint-lattice execution ledger differs")
for season,week,job,execution,uri in rows:
 if job!=f"constraint-lattice-s{season}-w{week}-v1" or not execution.startswith(job+"-") or uri!=f"{m['output_prefix']}/slate-{season}-{week}.json":
  raise SystemExit("ABORT: constraint-lattice execution identity differs")
PY

mkdir -p "$OUT/execution-metadata.pending" "$OUT/object-metadata.pending" \
  "$OUT/shards.pending"
while read -r SEASON WEEK JOB EXEC URI; do
  LISTED=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
    --region "$REGION" --format='value(metadata.name)')
  [ "$LISTED" = "$EXEC" ] || {
    echo "ABORT: constraint-lattice job has replacement/extra execution: $JOB" >&2; exit 2; }
  META="$OUT/execution-metadata.pending/${EXEC}.json"
  gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format=json > "$META"
  "$ROOT/.venv/bin/python" - "$META" "$MANIFEST" "$EXEC" "$SEASON" "$WEEK" "$URI" <<'PY'
import json, sys
x=json.load(open(sys.argv[1],encoding="utf-8")); m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
name,season,week,uri=sys.argv[3:]
if x.get("metadata",{}).get("name")!=name: raise SystemExit("ABORT: constraint-lattice execution name differs")
s=x.get("status",{}); done=[row for row in s.get("conditions",[]) if row.get("type")=="Completed"]
if len(done)!=1 or done[0].get("status")!="True" or int(s.get("succeededCount") or 0)!=1 or int(s.get("failedCount") or 0)!=0 or not s.get("completionTime"):
 raise SystemExit("ABORT: constraint-lattice execution is not terminal successful")
spec=x.get("spec",{}); task=spec.get("template",{}).get("spec",{}); containers=task.get("containers",[])
if spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(containers)!=1: raise SystemExit("ABORT: constraint-lattice task shape differs")
c=containers[0]
expected=["scripts/run_constraint_lattice_scorefree.py","--season",season,"--week",week,"--output-uri",uri]
if c.get("image")!=m["image"] or c.get("command")!=["python"] or c.get("args")!=expected:
 raise SystemExit("ABORT: constraint-lattice image/command differs")
env={row.get("name"):str(row.get("value","")) for row in c.get("env",[])}
if env!={"CODE_SHA":m["code_sha"],"ANALYSIS_IMAGE":m["image"]}: raise SystemExit("ABORT: constraint-lattice environment differs")
if c.get("resources",{}).get("limits")!={"cpu":"4","memory":"16Gi"} or task.get("maxRetries")!=0 or str(task.get("timeoutSeconds"))!="43200" or task.get("serviceAccountName")!="817589974517-compute@developer.gserviceaccount.com":
 raise SystemExit("ABORT: constraint-lattice resources/account differ")
PY
  OBJECT="$OUT/object-metadata.pending/slate-${SEASON}-${WEEK}.json"
  gcloud storage objects describe "$URI" --project "$PROJECT" --format=json > "$OBJECT"
  SHARD="$OUT/shards.pending/slate-${SEASON}-${WEEK}.json"
  gcloud storage cp "$URI" "$SHARD" --project "$PROJECT" >/dev/null
  "$ROOT/.venv/bin/python" - "$OBJECT" "$SHARD" "$URI" <<'PY'
from hashlib import sha256
import json, sys
m=json.load(open(sys.argv[1],encoding="utf-8")); raw=open(sys.argv[2],"rb").read()
if not str(m.get("generation","")).isdigit() or int(m.get("size",-1))!=len(raw):
 raise SystemExit("ABORT: constraint-lattice output object metadata differs")
json.loads(raw)
print(sha256(raw).hexdigest())
PY
done < "$EXECUTIONS"

mv "$OUT/execution-metadata.pending" "$OUT/execution-metadata"
mv "$OUT/object-metadata.pending" "$OUT/object-metadata"
mv "$OUT/shards.pending" "$OUT/shards"
ARGS=()
for SHARD in "$OUT"/shards/slate-*.json; do ARGS+=(--shard-report "$SHARD"); done
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" "$AGGREGATOR" \
  "${ARGS[@]}" --output "$OUT/report.json"

"$ROOT/.venv/bin/python" - "$OUT/report.json" "$MANIFEST" <<'PY'
import json, sys
r=json.load(open(sys.argv[1],encoding="utf-8")); m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
if r.get("version")!="constraint-lattice-scorefree-report-v1" or r.get("run_id")!=m["run_id"] or r.get("uses_realized_outcomes") is not False or r.get("production_change_licensed") is not False or r.get("historical_scoring_licensed") is not False or r.get("code_sha")!=m["code_sha"] or r.get("analysis_image")!=m["image"]:
 raise SystemExit("ABORT: constraint-lattice aggregate identity/license differs")
if r.get("mechanical")!={"seasons":[2023,2024,2025],"slates":54,"heldout_folds":270,"source_artifacts":270,"all_valid":True}:
 raise SystemExit("ABORT: constraint-lattice aggregate mechanics differ")
g=r.get("gate",{}); c=g.get("conditions",{}); expected={"aggregate_p230_improves","at_least_three_heldout_blocks_improve_p230","aggregate_p210_nondecline","aggregate_p194_retains_95pct","every_fold_pair_and_core_retain_90pct"}
if set(c)!=expected or g.get("passes_scorefree_gate") is not all(c.values()) or g.get("slates")!=54 or g.get("folds")!=270:
 raise SystemExit("ABORT: constraint-lattice aggregate gate differs")
print("CONSTRAINT_LATTICE_STRICT_AGGREGATE_VALIDATED",g["passes_scorefree_gate"])
PY

PREFIX=$(awk -F= '$1=="output_prefix" {print $2}' "$MANIFEST")
PYTHONPATH="$ROOT/scripts" "$ROOT/.venv/bin/python" - "$OUT/report.json" \
  "$PREFIX/report.json" "$OUT/report-upload.json" <<'PY'
import json, sys
from google.cloud import storage
from run_cbwu_seed_order_audit import _upload_create_only
raw=open(sys.argv[1],"rb").read(); receipt=_upload_create_only(storage.Client(project="nfl-predictions-503414"),sys.argv[2],raw)
open(sys.argv[3],"w",encoding="utf-8").write(json.dumps(receipt,sort_keys=True,separators=(",",":"))+"\n")
PY

sha256sum "$OUT/report.json" > "$OUT/report.sha256"
sha256sum "$OUT/report-upload.json" > "$OUT/report-upload.sha256"
sha256sum "$OUT"/execution-metadata/*.json | sort > "$OUT/execution-metadata.sha256"
sha256sum "$OUT"/object-metadata/*.json | sort > "$OUT/object-metadata.sha256"
sha256sum "$OUT"/shards/*.json | sort > "$OUT/shards.sha256"
DISPOSITION=$("$ROOT/.venv/bin/python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["gate"]["disposition"])' "$OUT/report.json")
PASS=$("$ROOT/.venv/bin/python" -c 'import json,sys; print(str(json.load(open(sys.argv[1]))["gate"]["passes_scorefree_gate"]).lower())' "$OUT/report.json")
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'executions=54' 'slates=54' 'folds=270' 'source_artifacts=270' \
  'uses_realized_outcomes=false' 'production_change_licensed=false' \
  'historical_scoring_licensed=false' "passes_scorefree_gate=$PASS" \
  "disposition=$DISPOSITION" > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "CONSTRAINT_LATTICE_HARVESTED $RUN_ID $DISPOSITION"
