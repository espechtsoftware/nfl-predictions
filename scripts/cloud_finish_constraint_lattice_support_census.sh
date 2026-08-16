#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-constraint-lattice-control-support-census-v1
OUT="$ROOT/reports/constraint-lattice-support-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
PRIMARY="$OUT/executions.txt"
RETRIES="$OUT/retry-executions.txt"
EXECUTIONS="$OUT/accepted-executions.txt"
RUNNER="$ROOT/scripts/run_constraint_lattice_support_census.py"
AGGREGATOR="$ROOT/scripts/aggregate_constraint_lattice_support_census.py"
ATTEMPT_VALIDATOR="$ROOT/scripts/validate_constraint_lattice_attempts.py"
CANARY_VALIDATOR="$ROOT/scripts/cloud_wait_constraint_lattice_canary.sh"

[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] && \
  [ -s "$PRIMARY" ] && [ -e "$RETRIES" ] && \
  [ -s "$OUT/attempt-resolution.json" ] && \
  [ -s "$OUT/canary-completion.txt" ] && \
  [ -s "$OUT/canary-execution-metadata.json" ] && \
  [ -s "$OUT/canary-object-metadata.json" ] && \
  [ -s "$OUT/grid-release.txt" ] && \
  [ -s "$OUT/build-metadata.json" ] && [ -s "$OUT/queue-release.json" ] || {
  echo "ABORT: lattice-support launch receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ABORT: lattice-support execution grid is not 54" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/execution-metadata" ] && \
  [ ! -e "$OUT/shards" ] && [ ! -e "$OUT/object-metadata" ] || {
  echo "ABORT: immutable lattice-support harvest already exists" >&2; exit 3; }

PYTHONPATH="$ROOT/scripts" "$ROOT/.venv/bin/python" "$ATTEMPT_VALIDATOR" \
  support --output-dir "$OUT" --manifest "$MANIFEST"
"$ROOT/.venv/bin/python" - "$MANIFEST" "$OUT/canary-completion.txt" \
  "$OUT/canary-execution-metadata.json" "$OUT/canary-object-metadata.json" \
  "$OUT/grid-release.txt" "$CANARY_VALIDATOR" <<'PY'
from hashlib import sha256
import pathlib, sys
m=dict(line.split("=",1) for line in open(sys.argv[1],encoding="utf-8") if "=" in line)
c=dict(line.split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
execution=pathlib.Path(sys.argv[3]); obj=pathlib.Path(sys.argv[4]); release=pathlib.Path(sys.argv[5]); validator=pathlib.Path(sys.argv[6])
r=dict(line.split("=",1) for line in release.read_text().splitlines() if "=" in line)
if m.get("canary_amendment_sha256")!="2599f722b6ba7703ff78fec31cb3c0b78d0c771178e8ea40fb4fb6563d44aa00" or m.get("canary_validator_sha256")!=sha256(validator.read_bytes()).hexdigest():
 raise SystemExit("ABORT: lattice-support canary source binding differs")
if c.get("status")!="True" or c.get("disposition")!="real-path-canary-passes" or c.get("mode")!="support" or c.get("cell")!="2023-1" or c.get("remaining_cells_released")!="false" or c.get("object_content_inspected")!="false" or c.get("effect_fields_inspected")!="false":
 raise SystemExit("ABORT: lattice-support canary disposition differs")
if c.get("execution_metadata_sha256")!=sha256(execution.read_bytes()).hexdigest() or c.get("object_metadata_sha256")!=sha256(obj.read_bytes()).hexdigest():
 raise SystemExit("ABORT: lattice-support canary metadata binding differs")
if r.get("primary_executions")!="54" or r.get("released_after_canary")!="53" or r.get("canary_completion_sha256")!=sha256(pathlib.Path(sys.argv[2]).read_bytes()).hexdigest() or r.get("object_content_inspected")!="false" or r.get("effect_fields_inspected")!="false":
 raise SystemExit("ABORT: lattice-support grid release differs")
PY

"$ROOT/.venv/bin/python" - "$MANIFEST" "$EXECUTIONS" "$OUT/build-metadata.json" \
  "$RUNNER" "$AGGREGATOR" "$OUT/queue-release.json" <<'PY'
from hashlib import sha256
import json, pathlib, re, sys
m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[1],encoding="utf-8") if "=" in line)
rows=[line.split() for line in open(sys.argv[2],encoding="utf-8") if line.strip()]
b=json.load(open(sys.argv[3],encoding="utf-8")); runner=pathlib.Path(sys.argv[4]); aggregator=pathlib.Path(sys.argv[5]); release_path=pathlib.Path(sys.argv[6]); release=json.loads(release_path.read_text())
fixed={
 "run_id":"20260816-constraint-lattice-control-support-census-v1",
 "output_prefix":"gs://nfl-predictions-503414-raw/research/constraint-lattice-support-runs/20260816-constraint-lattice-control-support-census-v1",
 "protocol_sha256":"11e97d5e94a11808b4838396c6fe59ff327a65a9ae260223138657db8d2a1a17",
 "lattice_protocol_sha256":"f8591d24dd56749e5b56235f9636687fd41bd1a78991fdb60cfbb092ee65bf62",
 "source_amendment_sha256":"35ea1f0dba3be5311631d51057c7667cb624bcdc19be75e2b202c57e297e8321",
 "attempt_amendment_sha256":"f846d4540d27c1480037b440aabf94c91a1a5121e6d9968ad5ef39f679ce63aa",
 "distribution_amendment_sha256":"9bdfd3b24aa42616425138e1fed437fecbeae1d9b9c02606bbe9cde8202bb6e8",
 "cbwu_report_sha256":"556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33",
 "source_panels":"20260813-sis-asoe-treatment-r0-v1,20260813-sis-asoe-treatment-r1-v1,20260813-sis-asoe-treatment-r2-v1,20260813-sis-asoe-treatment-r3-v1,20260813-sis-asoe-treatment-r4-v1",
 "forensic_manifest_sha256":"51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02",
 "seasons":"2023,2024,2025", "weeks":"1-18", "slates":"54", "folds":"270",
 "cpu":"4", "memory":"16Gi", "timeout_seconds":"7200", "max_retries":"0",
 "aggregate_events_minimum_per_block":"540",
 "positive_slates_minimum_per_block":"41", "anchor_order":"230,220,210",
 "uses_realized_outcomes":"false", "effect_fields_inspected":"false",
 "treatment_constructed":"false", "production_change_licensed":"false",
 "historical_scoring_licensed":"false",
}
for key,value in fixed.items():
 if m.get(key)!=value: raise SystemExit(f"ABORT: lattice-support manifest differs: {key}")
if not re.fullmatch(r"[0-9a-f]{40}",m.get("code_sha","")) or not re.fullmatch(r".+@sha256:[0-9a-f]{64}",m.get("image","")):
 raise SystemExit("ABORT: lattice-support code/image differs")
for key,path in (("runner_sha256",runner),("aggregator_sha256",aggregator)):
 if m.get(key)!=sha256(path.read_bytes()).hexdigest():
  raise SystemExit(f"ABORT: lattice-support implementation differs: {key}")
if m.get("build_metadata_sha256")!=sha256(pathlib.Path(sys.argv[3]).read_bytes()).hexdigest() or b.get("id")!=m.get("build_id") or b.get("status")!="SUCCESS":
 raise SystemExit("ABORT: lattice-support build receipt differs")
if m.get("queue_release_sha256")!=sha256(release_path.read_bytes()).hexdigest() or release.get("version")!="constraint-lattice-support-queue-release-v1" or release.get("branch")!=m.get("queue_release_branch") or release.get("branch") not in {"preflight-failed-parity-closed","repair5-valid-historical-closed","repair5-failed-parity-closed"}:
 raise SystemExit("ABORT: lattice-support queue release differs")
for raw_path,digest in release.get("bindings",{}).items():
 path=pathlib.Path(raw_path)
 if not path.is_file() or sha256(path.read_bytes()).hexdigest()!=digest:
  raise SystemExit("ABORT: lattice-support queue binding differs")
expected={(str(s),str(w)) for s in (2023,2024,2025) for w in range(1,19)}
if len(rows)!=54 or any(len(row)!=5 for row in rows) or {(row[0],row[1]) for row in rows}!=expected or len({row[3] for row in rows})!=54:
 raise SystemExit("ABORT: lattice-support execution ledger differs")
for season,week,job,execution,uri in rows:
 if job!=f"constraint-support-s{season}-w{week}-v1" or not execution.startswith(job+"-") or uri!=f"{m['output_prefix']}/slate-{season}-{week}.json":
  raise SystemExit("ABORT: lattice-support execution identity differs")
PY

mkdir -p "$OUT/execution-metadata.pending" "$OUT/object-metadata.pending" \
  "$OUT/shards.pending"
while read -r SEASON WEEK JOB EXEC URI; do
  LISTED=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
    --region "$REGION" --format='value(metadata.name)' | sort)
  EXPECTED=$({
    awk -v job="$JOB" '$3==job {print $4}' "$PRIMARY"
    awk -v job="$JOB" '$3==job {print $5}' "$RETRIES"
  } | sort)
  [ "$LISTED" = "$EXPECTED" ] || {
    echo "ABORT: lattice-support job attempt population differs: $JOB" >&2; exit 2; }
  META="$OUT/execution-metadata.pending/${EXEC}.json"
  gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format=json > "$META"
  "$ROOT/.venv/bin/python" - "$META" "$MANIFEST" "$EXEC" "$SEASON" "$WEEK" "$URI" <<'PY'
import json, sys
x=json.load(open(sys.argv[1],encoding="utf-8")); m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
name,season,week,uri=sys.argv[3:]
if x.get("metadata",{}).get("name")!=name: raise SystemExit("ABORT: lattice-support execution name differs")
s=x.get("status",{}); done=[row for row in s.get("conditions",[]) if row.get("type")=="Completed"]
if len(done)!=1 or done[0].get("status")!="True" or int(s.get("succeededCount") or 0)!=1 or int(s.get("failedCount") or 0)!=0 or not s.get("completionTime"):
 raise SystemExit("ABORT: lattice-support execution is not terminal successful")
spec=x.get("spec",{}); task=spec.get("template",{}).get("spec",{}); containers=task.get("containers",[])
if spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(containers)!=1: raise SystemExit("ABORT: lattice-support task shape differs")
c=containers[0]; expected=["scripts/run_constraint_lattice_support_census.py","--season",season,"--week",week,"--output-uri",uri]
if c.get("image")!=m["image"] or c.get("command")!=["python"] or c.get("args")!=expected:
 raise SystemExit("ABORT: lattice-support image/command differs")
env={row.get("name"):str(row.get("value","")) for row in c.get("env",[])}
if env!={"CODE_SHA":m["code_sha"],"ANALYSIS_IMAGE":m["image"]}: raise SystemExit("ABORT: lattice-support environment differs")
if c.get("resources",{}).get("limits")!={"cpu":"4","memory":"16Gi"} or task.get("maxRetries")!=0 or str(task.get("timeoutSeconds"))!="7200" or task.get("serviceAccountName")!="817589974517-compute@developer.gserviceaccount.com":
 raise SystemExit("ABORT: lattice-support resources/account differ")
PY
  OBJECT="$OUT/object-metadata.pending/slate-${SEASON}-${WEEK}.json"
  gcloud storage objects describe "$URI" --project "$PROJECT" --format=json > "$OBJECT"
  SHARD="$OUT/shards.pending/slate-${SEASON}-${WEEK}.json"
  gcloud storage cp "$URI" "$SHARD" --project "$PROJECT" >/dev/null
  "$ROOT/.venv/bin/python" - "$OBJECT" "$SHARD" <<'PY'
from hashlib import sha256
import json, sys
m=json.load(open(sys.argv[1],encoding="utf-8")); raw=open(sys.argv[2],"rb").read()
if not str(m.get("generation","")).isdigit() or int(m.get("size",-1))!=len(raw):
 raise SystemExit("ABORT: lattice-support output metadata differs")
json.loads(raw); print(sha256(raw).hexdigest())
PY
done < "$EXECUTIONS"

mv "$OUT/execution-metadata.pending" "$OUT/execution-metadata"
mv "$OUT/object-metadata.pending" "$OUT/object-metadata"
mv "$OUT/shards.pending" "$OUT/shards"
ARGS=()
for SHARD in "$OUT"/shards/slate-*.json; do ARGS+=(--shard-report "$SHARD"); done
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" "$AGGREGATOR" \
  "${ARGS[@]}" --output-dir "$OUT"

"$ROOT/.venv/bin/python" - "$OUT/report.json" "$MANIFEST" <<'PY'
import json, sys
r=json.load(open(sys.argv[1],encoding="utf-8")); m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
if r.get("version")!="constraint-lattice-control-support-report-v1" or r.get("run_id")!=m["run_id"] or r.get("uses_realized_outcomes") is not False or r.get("effect_fields_inspected") is not False or r.get("treatment_constructed") is not False or r.get("production_change_licensed") is not False or r.get("historical_scoring_licensed") is not False or r.get("code_sha")!=m["code_sha"] or r.get("analysis_image")!=m["image"]:
 raise SystemExit("ABORT: lattice-support aggregate identity differs")
if r.get("mechanical")!={"seasons":[2023,2024,2025],"slates":54,"heldout_folds":270,"worlds_per_fold":10000,"source_artifacts":270,"all_valid":True}:
 raise SystemExit("ABORT: lattice-support mechanics differ")
law=r.get("support_law",{})
if law!={"aggregate_events_minimum_per_block":540,"positive_slates_minimum_per_block":41,"anchor_order":[230,220,210]} or set(r.get("counts_by_block",{}))!={"R0","R1","R2","R3","R4"} or len(r.get("cells",[]))!=270:
 raise SystemExit("ABORT: lattice-support law/population differs")
if r.get("distribution_amendment_sha256")!="9bdfd3b24aa42616425138e1fed437fecbeae1d9b9c02606bbe9cde8202bb6e8" or set(r.get("fold_correlation_by_threshold",{}))!={"194","210","220","230"}:
 raise SystemExit("ABORT: lattice-support distribution amendment differs")
required={"events","worlds","positive_slates","slates","top_1_event_share","top_3_event_share","top_5_event_share","top_10_event_share","herfindahl","effective_slates","median_positive_events","max_slate_events","slate_counts"}
for block in ("R0","R1","R2","R3","R4"):
 for threshold in ("194","210","220","230"):
  value=r["counts_by_block"][block].get(threshold,{})
  if set(value)!=required or len(value.get("slate_counts",[]))!=54:
   raise SystemExit("ABORT: lattice-support distribution fields differ")
for value in r["fold_correlation_by_threshold"].values():
 if len(value.get("pairs",[]))!=10 or value.get("diagnostic_only") is not True or value.get("folds_are_independent") is not False:
  raise SystemExit("ABORT: lattice-support fold correlation differs")
adequate=r.get("adequate_by_threshold",{}); anchor=r.get("selected_anchor"); disposition=r.get("disposition")
expected={230:"p230-supported-original-gate-complete",220:"reanchor-required-p220",210:"reanchor-required-p210",None:"terminal-insufficient-support"}
if set(adequate)!={"230","220","210"} or any(not isinstance(value,bool) for value in adequate.values()) or anchor not in expected or disposition!=expected[anchor]:
 raise SystemExit("ABORT: lattice-support disposition differs")
print("CONSTRAINT_LATTICE_SUPPORT_STRICTLY_VALIDATED",disposition)
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
DISPOSITION=$("$ROOT/.venv/bin/python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["disposition"])' "$OUT/report.json")
ANCHOR=$("$ROOT/.venv/bin/python" -c 'import json,sys; v=json.load(open(sys.argv[1]))["selected_anchor"]; print("none" if v is None else v)' "$OUT/report.json")
ATTEMPT_DISPOSITION=$("$ROOT/.venv/bin/python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["disposition"])' "$OUT/attempt-resolution.json")
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'executions=54' 'slates=54' 'folds=270' 'source_artifacts=270' \
  "attempt_disposition=$ATTEMPT_DISPOSITION" \
  "primary_executions_sha256=$(sha256sum "$PRIMARY" | awk '{print $1}')" \
  "retry_executions_sha256=$(sha256sum "$RETRIES" | awk '{print $1}')" \
  "accepted_executions_sha256=$(sha256sum "$EXECUTIONS" | awk '{print $1}')" \
  "attempt_resolution_sha256=$(sha256sum "$OUT/attempt-resolution.json" | awk '{print $1}')" \
  "canary_completion_sha256=$(sha256sum "$OUT/canary-completion.txt" | awk '{print $1}')" \
  "grid_release_sha256=$(sha256sum "$OUT/grid-release.txt" | awk '{print $1}')" \
  'uses_realized_outcomes=false' 'effect_fields_inspected=false' \
  'treatment_constructed=false' 'production_change_licensed=false' \
  'historical_scoring_licensed=false' "selected_anchor=$ANCHOR" \
  "disposition=$DISPOSITION" > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "CONSTRAINT_LATTICE_SUPPORT_HARVESTED $RUN_ID $DISPOSITION"
