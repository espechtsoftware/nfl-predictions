#!/bin/bash
# Harvest and strictly validate the score-free competitive-WR allocation gate.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=${1:-20260814-td-competitive-wr-v1}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/td-competitive-wr-runs/$RUN_ID/treatment"
MANIFEST="$OUT/manifest.txt"
EXEC=$(cat "$OUT/execution.txt")
[ -n "$EXEC" ] || { echo "ABORT: competitive-WR treatment execution missing"; exit 2; }
[ -s "$MANIFEST" ] || { echo "ABORT: competitive-WR treatment manifest missing"; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable competitive-WR treatment report exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: competitive-WR treatment $EXEC is not complete ($STATE)"; exit 1; }
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"TD_COMPETITIVE_WR_ALLOCATION_\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 300 --order asc \
  --format='value(textPayload)' > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$MANIFEST" "$OUT/report.json" <<'PY'
import base64
import gzip
import hashlib
import json
import sys

lines = list(open(sys.argv[1], encoding="utf-8"))
meta_prefix = "TD_COMPETITIVE_WR_ALLOCATION_META="
chunk_prefix = "TD_COMPETITIVE_WR_ALLOCATION_CHUNK="
metas = [json.loads(line.split(meta_prefix, 1)[1])
         for line in lines if meta_prefix in line]
if len(metas) != 1:
    raise SystemExit(f"ABORT: expected one allocation transport, got {len(metas)}")
meta = metas[0]
parts, totals = {}, set()
for line in lines:
    if chunk_prefix not in line:
        continue
    header, value = line.split(chunk_prefix, 1)[1].rstrip("\n").split(":", 1)
    index, total = map(int, header.split("/", 1))
    if index in parts:
        raise SystemExit("ABORT: duplicate allocation transport chunk")
    parts[index] = value
    totals.add(total)
if totals != {meta.get("chunks")} or set(parts) != set(range(meta.get("chunks", -1))):
    raise SystemExit("ABORT: incomplete allocation transport")
try:
    compressed = base64.b64decode(
        "".join(parts[index] for index in range(meta["chunks"])), validate=True)
    content = gzip.decompress(compressed)
except Exception as exc:
    raise SystemExit("ABORT: invalid allocation transport") from exc
if len(compressed) != meta.get("gzip_bytes") or \
        hashlib.sha256(compressed).hexdigest() != meta.get("gzip_sha256"):
    raise SystemExit("ABORT: allocation gzip identity differs")
if len(content) != meta.get("json_bytes") or \
        hashlib.sha256(content).hexdigest() != meta.get("json_sha256"):
    raise SystemExit("ABORT: allocation JSON identity differs")
report = json.loads(content)
manifest = dict(line.rstrip("\n").split("=", 1)
                for line in open(sys.argv[2], encoding="utf-8") if "=" in line)
if report.get("version") != "td-competitive-wr-allocation-v1" or \
        report.get("panel") != manifest.get("panel"):
    raise SystemExit("ABORT: allocation report identity differs")
if report.get("reference_identity") != {
        "run_id": manifest.get("reference_run_id"),
        "code_sha": manifest.get("reference_code_sha"),
}:
    raise SystemExit("ABORT: allocation reference identity differs")
expected = {
    "changed_positions": ["WR"],
    "rank_source": {"TD_LEDGER": "1", "td_alloc_k": None},
    "priority": "qb_control_percentile+(wr_td_percentile-team_wr_mean_percentile)",
    "rank_tie_rule": "stable_ascending_world_index",
    "coefficients": {"qb_control_percentile": 1.0, "centered_wr_td": 1.0},
    "minimum_supported_mean": 4.0,
    "required_qbs_per_group": 1,
    "minimum_wrs_per_group": 2,
}
if report.get("intervention") != expected:
    raise SystemExit("ABORT: allocation intervention differs")
if report.get("adaptive_retrospective") is not True:
    raise SystemExit("ABORT: allocation adaptive disclosure missing")
valid = {"td-competitive-wr-allocation-gate-passes",
         "td-competitive-wr-allocation-gate-fails",
         "td-competitive-wr-allocation-invalid-or-inconclusive"}
if report.get("disposition") not in valid:
    raise SystemExit("ABORT: allocation disposition differs")
if bool(report.get("exact80_licensed")) != (
        report.get("disposition") == "td-competitive-wr-allocation-gate-passes"):
    raise SystemExit("ABORT: allocation exact80 license differs")
if "invalid" not in report.get("disposition", "") and \
        not report.get("invariants", {}).get("passes"):
    raise SystemExit("ABORT: valid allocation result lacks passing invariants")
if bool(report.get("gate", {}).get("passes")) != (
        report.get("disposition") == "td-competitive-wr-allocation-gate-passes"):
    raise SystemExit("ABORT: allocation gate/disposition differs")
bootstrap = report.get("bootstrap", {})
if {key: bootstrap.get(key) for key in ("cluster", "replicates", "seed")} != {
        "cluster": "season-week-slate", "replicates": 2000, "seed": 1703}:
    raise SystemExit("ABORT: allocation bootstrap differs")
if set(report.get("season_disclosures", {})) != {"control", "treatment"}:
    raise SystemExit("ABORT: allocation season disclosures missing")
for arm in ("control", "treatment"):
    if set(report["season_disclosures"][arm]) != {"2023", "2024", "2025"}:
        raise SystemExit("ABORT: allocation season folds differ")
diagnostic = report.get("multiplicity_ge4_diagnostic", {})
required_diagnostic = {
    "mandatory_report", "gated", "supported", "realized_events",
    "independence_expected_events", "realized_estimate",
    "control_simulated_estimate", "treatment_simulated_estimate",
    "control_absolute_log_error", "treatment_absolute_log_error",
    "treatment_minus_control_simulated", "movement",
}
if set(diagnostic) != required_diagnostic or \
        diagnostic.get("mandatory_report") is not True or \
        diagnostic.get("gated") is not False or \
        diagnostic.get("movement") not in {
            "toward-realized", "away-from-realized", "unchanged"}:
    raise SystemExit("ABORT: allocation >=4 diagnostic differs")
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "TD_COMPETITIVE_WR_ALLOCATION_COMPLETE $OUT/report.json"
