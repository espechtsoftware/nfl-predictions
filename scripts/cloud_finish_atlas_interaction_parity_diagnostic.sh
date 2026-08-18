#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-interaction-parity-v1
OUT="$ROOT/reports/atlas-interaction-parity-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"
SOURCE="$ROOT/scripts/run_atlas_interaction_parity_diagnostic.py"
PREFLIGHT="$ROOT/reports/atlas-cbc-32g-full-cell-preflight-runs/20260816-atlas-cbc-32g-full-cell-preflight-v1"
REPAIR5="$ROOT/reports/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair5"

[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] && \
  [ -s "$OUT/smoke-execution.json" ] && [ -s "$OUT/smoke.log" ] && \
[ "$(wc -l < "$EXECUTION")" = 1 ] || {
  echo "ABORT: ATLAS interaction-parity launch receipt is incomplete" >&2
  exit 2
}
[ -s "$OUT/launch.sha256" ] || {
  echo "ABORT: ATLAS interaction-parity launch hashes are missing" >&2
  exit 2
}
sha256sum -c "$OUT/launch.sha256" >/dev/null
[ -s "$PREFLIGHT/completion.txt" ] && \
  [ -s "$PREFLIGHT/execution-metadata.json" ] || {
  echo "ABORT: ATLAS interaction-parity binary-preflight evidence is missing" >&2
  exit 2
}
[ ! -e "$OUT/completion.txt" ] && [ ! -e "$OUT/execution-metadata.json" ] && \
  [ ! -e "$OUT/parity.json" ] || {
  echo "ABORT: immutable ATLAS interaction-parity harvest exists" >&2
  exit 3
}

read -r SEASON WEEK SEED JOB EXEC URI < "$EXECUTION"
META="$OUT/execution-metadata.pending.json"
gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$META"
STATUS=$("$ROOT/.venv/bin/python" - "$META" "$MANIFEST" "$SOURCE" \
  "$PREFLIGHT/completion.txt" "$PREFLIGHT/execution-metadata.json" \
  "$REPAIR5/terminal-census.json" "$REPAIR5/terminal-census-completion.txt" \
  "$SEASON" "$WEEK" "$SEED" "$JOB" "$EXEC" "$URI" <<'PY'
import base64
from hashlib import sha256
import json
from pathlib import Path
import sys

meta=json.load(open(sys.argv[1],encoding="utf-8"))
m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
source=Path(sys.argv[3]).read_bytes()
preflight_completion=Path(sys.argv[4])
preflight_metadata=Path(sys.argv[5])
repair5_census=Path(sys.argv[6])
repair5_census_completion=Path(sys.argv[7])
season,week,seed,job,execution,uri=sys.argv[8:]
fixed={
 "run_id":"20260816-atlas-interaction-parity-v1",
 "protocol_sha256":"0d925bc4c5fd03ca01b53ec2e2d0bdf10e48ca66f959a723aedf28ad636678a1",
 "build_repair_sha256":"2a3a02f00e2a78b862647aa30da251fab27366181522b5849859b6f770acf5dc",
 "queue_release_repair_sha256":"c49809b833e5aeec8a386670fb1edf89b6c21ba0312da3fb1775fba77adcc0d5",
 "build_receipt_sha256":"a3c7032e25bc6bcdcddcd8096d5b08436aa36bf52002298a369d025ba6b78ccf",
 "build_id":"9e8347a9-7fe1-460f-a0d6-9ba379616b52",
 "diagnostic_source_sha256":"f8b5b54ce3aab95be36d32bdb3825f2c0b34ed9552c7ebaf0085f0e5f0fb1d2d",
 "runner_sha256":"0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740",
 "optimizer_sha256":"ba5ac3a7c9eb5d436fa6b319e13104b10281fee640c64377904d56c93db65de6",
 "code_sha":"06797314a0ed423b9f5783fc926b269c1fb24371",
 "image":"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:437641a46e1c952ec2f1628428904c89fb4f8eef3d2a2c42a52262c45817231f",
 "output_prefix":"gs://nfl-predictions-503414-raw/research/atlas-interaction-parity-runs/20260816-atlas-interaction-parity-v1",
 "cell":"2024-15-R0",
 "cpu":"8", "memory":"32Gi", "max_retries":"0",
 "timeout_seconds":"43200", "uses_realized_outcomes":"false",
 "persists_lineups":"false", "production_change_licensed":"false",
}
if any(m.get(k)!=v for k,v in fixed.items()):
 raise SystemExit("ABORT: ATLAS interaction-parity manifest differs")
if m.get("preflight_completion_sha256")!=sha256(preflight_completion.read_bytes()).hexdigest() or m.get("preflight_execution_metadata_sha256")!=sha256(preflight_metadata.read_bytes()).hexdigest():
 raise SystemExit("ABORT: ATLAS interaction-parity preflight binding differs")
preflight=dict(line.rstrip("\n").split("=",1) for line in preflight_completion.read_text(encoding="utf-8").splitlines() if "=" in line)
trigger=m.get("queue_trigger")
if trigger=="binary-32g-preflight-failed":
 if preflight.get("status")!="False" or m.get("repair5_terminal_census_sha256")!="none" or m.get("repair5_terminal_census_completion_sha256")!="none":
  raise SystemExit("ABORT: ATLAS interaction-parity direct queue trigger differs")
elif trigger=="repair5-terminal-failure-census":
 if preflight.get("status")!="True" or not repair5_census.is_file() or not repair5_census_completion.is_file():
  raise SystemExit("ABORT: ATLAS interaction-parity repair5 trigger is missing")
 if m.get("repair5_terminal_census_sha256")!=sha256(repair5_census.read_bytes()).hexdigest() or m.get("repair5_terminal_census_completion_sha256")!=sha256(repair5_census_completion.read_bytes()).hexdigest():
  raise SystemExit("ABORT: ATLAS interaction-parity repair5 trigger binding differs")
 census=json.loads(repair5_census.read_text(encoding="utf-8"))
 completion=dict(line.rstrip("\n").split("=",1) for line in repair5_census_completion.read_text(encoding="utf-8").splitlines() if "=" in line)
 if census.get("version")!="atlas-matched-diversity-repair5-terminal-census-v1" or census.get("executions")!=54 or census.get("terminal_failed",0)<1 or census.get("scientific_result_valid") is not False or census.get("effect_fields_inspected") is not False or census.get("historical_scoring_licensed") is not False or census.get("continuous_parity_capacity_released") is not True or completion.get("all_declared_attempts_terminal")!="true" or completion.get("continuous_parity_capacity_released")!="true":
  raise SystemExit("ABORT: ATLAS interaction-parity repair5 trigger differs")
else:
 raise SystemExit("ABORT: ATLAS interaction-parity queue trigger differs")
if (season,week,seed,job)!=("2024","15","R0","atlas-interaction-parity-v1") or meta.get("metadata",{}).get("name")!=execution or uri!=m["output_prefix"]+"/parity.json":
 raise SystemExit("ABORT: ATLAS interaction-parity cell/execution differs")
status=meta.get("status",{}); done=[r for r in status.get("conditions",[]) if r.get("type")=="Completed"]
if len(done)!=1 or done[0].get("status") not in {"True","False"} or not status.get("completionTime"):
 raise SystemExit("ABORT: ATLAS interaction-parity is not terminal")
spec=meta.get("spec",{}); task=spec.get("template",{}).get("spec",{}); containers=task.get("containers",[])
if spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(containers)!=1:
 raise SystemExit("ABORT: ATLAS interaction-parity task shape differs")
command="exec(__import__('base64').b64decode('"+base64.b64encode(source).decode()+"'))"
if sha256(command.encode()).hexdigest()!=m["command_sha256"]:
 raise SystemExit("ABORT: ATLAS interaction-parity command hash differs")
container=containers[0]
expected=["-c",command,"--season","2024","--week","15","--output-uri",uri]
if container.get("image")!=m["image"] or container.get("command")!=["python"] or container.get("args")!=expected:
 raise SystemExit("ABORT: ATLAS interaction-parity command/image differs")
env={r.get("name"):str(r.get("value","")) for r in container.get("env",[])}
expected_env={
 "CODE_SHA":m["code_sha"], "ANALYSIS_IMAGE":m["image"],
 "ATLAS_INTERACTION_PARITY_PROTOCOL_SHA256":m["protocol_sha256"],
 "ATLAS_INTERACTION_PARITY_SOURCE_SHA256":m["diagnostic_source_sha256"],
}
if env!=expected_env or container.get("resources",{}).get("limits")!={"cpu":"8","memory":"32Gi"}:
 raise SystemExit("ABORT: ATLAS interaction-parity environment/resources differ")
if task.get("maxRetries")!=0 or str(task.get("timeoutSeconds"))!="43200" or task.get("serviceAccountName")!="817589974517-compute@developer.gserviceaccount.com":
 raise SystemExit("ABORT: ATLAS interaction-parity retry/timeout/account differs")
print(done[0]["status"])
PY
)

if [ "$STATUS" = True ]; then
  gcloud storage cp "$URI" "$OUT/parity.pending.json" \
    --project "$PROJECT" >/dev/null
  DISPOSITION=$("$ROOT/.venv/bin/python" - "$OUT/parity.pending.json" \
    "$MANIFEST" <<'PY'
import json,re,sys
r=json.load(open(sys.argv[1],encoding="utf-8"))
m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
expected={
 "version":"atlas-interaction-parity-v1",
 "uses_realized_outcomes":False,
 "persists_lineups":False,
 "production_change_licensed":False,
 "protocol_id":m["run_id"],
 "protocol_sha256":m["protocol_sha256"],
 "diagnostic_source_sha256":m["diagnostic_source_sha256"],
 "code_sha":m["code_sha"],
 "analysis_image":m["image"],
 "runner_sha256":m["runner_sha256"],
 "optimizer_sha256":m["optimizer_sha256"],
 "season":2024,"week":15,"source_seed":"R0","worlds_ranked":40,
}
if any(r.get(k)!=v for k,v in expected.items()):
 raise SystemExit("ABORT: ATLAS interaction-parity receipt identity differs")
allowed=set(expected)|{
 "binary_candidate_count","continuous_candidate_count",
 "binary_interaction_variables_constructed",
 "continuous_interaction_variables_constructed",
 "binary_roster_sha256","continuous_roster_sha256",
 "binary_proposal_signature_sha256",
 "continuous_proposal_signature_sha256","ordered_roster_parity",
 "proposal_path_parity","interaction_category_instrumentation_valid",
 "passes_parity_gate",
}
if set(r)!=allowed:
 raise SystemExit("ABORT: ATLAS interaction-parity receipt field set differs")
if r.get("binary_candidate_count")!=40 or r.get("continuous_candidate_count")!=40:
 raise SystemExit("ABORT: ATLAS interaction-parity candidate count differs")
if int(r.get("binary_interaction_variables_constructed",0))<1 or int(r.get("continuous_interaction_variables_constructed",0))<1:
 raise SystemExit("ABORT: ATLAS interaction-parity instrumentation is empty")
for key in ("binary_roster_sha256","continuous_roster_sha256","binary_proposal_signature_sha256","continuous_proposal_signature_sha256"):
 if not re.fullmatch(r"[0-9a-f]{64}",str(r.get(key,""))):
  raise SystemExit("ABORT: ATLAS interaction-parity hash differs")
for forbidden in ("actual_score","actual_rank","payout","ownership","selected_lineups","roster_ids","player_ids"):
 if forbidden in json.dumps(r,sort_keys=True).lower():
  raise SystemExit("ABORT: ATLAS interaction-parity crossed score/identity firewall")
passed=(r.get("ordered_roster_parity") is True and r.get("proposal_path_parity") is True and r.get("interaction_category_instrumentation_valid") is True and r.get("passes_parity_gate") is True)
print("real-slate-parity-passes" if passed else "real-slate-parity-fails")
PY
)
  mv "$OUT/parity.pending.json" "$OUT/parity.json"
  sha256sum "$OUT/parity.json" > "$OUT/parity.sha256"
else
  if gcloud storage ls "$URI" --project "$PROJECT" 2>/dev/null | grep -q .; then
    echo "ABORT: failed parity execution unexpectedly created its receipt" >&2
    exit 2
  fi
  DISPOSITION=parity-execution-failed
fi

mv "$META" "$OUT/execution-metadata.json"
sha256sum "$OUT/execution-metadata.json" > "$OUT/execution-metadata.sha256"
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  "status=$STATUS" "disposition=$DISPOSITION" 'cell=2024-15-R0' \
  'uses_realized_outcomes=false' 'persists_lineups=false' \
  'production_change_licensed=false' > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "ATLAS_INTERACTION_PARITY_HARVESTED $DISPOSITION"
