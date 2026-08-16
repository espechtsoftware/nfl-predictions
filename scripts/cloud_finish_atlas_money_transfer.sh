#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/atlas-money-transfer-runs/20260815-atlas-current-money-transfer-v1"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"

[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] || {
  echo "ABORT: ATLAS money-transfer receipt is incomplete" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/execution.json" ] || {
  echo "ABORT: immutable ATLAS money-transfer result exists" >&2; exit 3; }
EXEC=$(tr -d '[:space:]' < "$EXECUTION")
EXEC_TMP="$OUT/execution.pending.json"
REPORT_TMP="$OUT/report.pending.json"
[ ! -e "$EXEC_TMP" ] && [ ! -e "$REPORT_TMP" ] || {
  echo "ABORT: stale ATLAS money-transfer pending receipt" >&2; exit 2; }
gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$EXEC_TMP"

"$ROOT/.venv/bin/python" - "$EXEC_TMP" "$MANIFEST" "$EXEC" <<'PY'
import json
import sys

execution = json.load(open(sys.argv[1], encoding="utf-8"))
manifest = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line
)
name = sys.argv[3]
if execution.get("metadata", {}).get("name") != name:
    raise SystemExit("ABORT: transfer execution name differs")
status = execution.get("status", {})
completed = [row for row in status.get("conditions", [])
             if row.get("type") == "Completed"]
if len(completed) != 1 or completed[0].get("status") != "True" or \
        int(status.get("succeededCount") or 0) != 1 or \
        int(status.get("failedCount") or 0) != 0 or \
        not status.get("completionTime"):
    raise SystemExit("ABORT: transfer execution is not terminal successful")
spec = execution.get("spec", {})
template = spec.get("template", {}).get("spec", {})
containers = template.get("containers", [])
if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
        len(containers) != 1:
    raise SystemExit("ABORT: transfer execution task shape differs")
container = containers[0]
if container.get("image") != manifest.get("image") or \
        container.get("command") != ["python"] or \
        container.get("args") != [
            "scripts/run_atlas_money_transfer.py", "--output-uri",
            manifest.get("output_uri"),
        ]:
    raise SystemExit("ABORT: transfer execution image/command differs")
expected_env = {
    "CODE_SHA": manifest.get("code_sha"),
    "ANALYSIS_IMAGE": manifest.get("image"),
    "PROTOCOL_SHA256": manifest.get("protocol_sha256"),
    "LAW_SEPARATION_AMENDMENT_SHA256": manifest.get(
        "law_separation_amendment_sha256"),
    "ACQUISITION_MANIFEST_SHA256": manifest.get(
        "acquisition_manifest_sha256"),
    "SOURCE_GRID_SHA256": manifest.get("source_grid_sha256"),
    "ACQUISITION_COMPLETE_SHA256": manifest.get(
        "acquisition_complete_sha256"),
    "EXECUTION_RECEIPTS_SHA256": manifest.get("execution_receipts_sha256"),
}
actual_env = {row.get("name"): str(row.get("value", ""))
              for row in container.get("env", [])}
if actual_env != expected_env:
    raise SystemExit("ABORT: transfer execution environment differs")
if container.get("resources", {}).get("limits") != {
    "cpu": "8", "memory": "32Gi",
} or template.get("maxRetries") != 0 or \
        str(template.get("timeoutSeconds")) != "21600" or \
        template.get("serviceAccountName") != (
            "817589974517-compute@developer.gserviceaccount.com"
        ):
    raise SystemExit("ABORT: transfer resources/account differ")
print("ATLAS_MONEY_TRANSFER_EXECUTION_VALIDATED", name)
PY

OUTPUT_URI=$(awk -F= '$1=="output_uri" {print $2}' "$MANIFEST")
gcloud storage cp "$OUTPUT_URI" "$REPORT_TMP" --project "$PROJECT" >/dev/null
"$ROOT/.venv/bin/python" - "$REPORT_TMP" "$MANIFEST" <<'PY'
import json
import math
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
manifest = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line
)
if report.get("version") != "atlas-current-money-transfer-v1" or \
        report.get("code_sha") != manifest.get("code_sha") or \
        report.get("image") != manifest.get("image") or \
        report.get("protocol_sha256") != manifest.get("protocol_sha256") or \
        report.get("law_separation_amendment_sha256") != \
        manifest.get("law_separation_amendment_sha256"):
    raise SystemExit("ABORT: transfer report identity differs")
if report.get("uses_realized_outcomes") is not False or \
        report.get("candidate_or_lineup_scores_read") is not False or \
        report.get("historical_arm_licensed") is not False or \
        report.get("production_change_licensed") is not False:
    raise SystemExit("ABORT: transfer evidence license differs")
expected_panels = manifest.get("source_panels", "").split(",")
preflight = report.get("source_preflight", {})
if report.get("source_panels") != expected_panels or \
        preflight.get("panel_ids") != expected_panels or \
        preflight.get("slate_count") != 54 or \
        preflight.get("artifact_count") != 270 or \
        len(report.get("source_artifacts", [])) != 270 or \
        len(report.get("diagnostics", [])) != 270:
    raise SystemExit("ABORT: transfer source coverage differs")
local = report.get("local_source_receipts", {})
expected_local = {
    "protocol": manifest.get("protocol_sha256"),
    "law_separation_amendment": manifest.get(
        "law_separation_amendment_sha256"),
    "acquisition_manifest": manifest.get("acquisition_manifest_sha256"),
    "source_grid": manifest.get("source_grid_sha256"),
    "acquisition_complete": manifest.get("acquisition_complete_sha256"),
    "execution_receipts": manifest.get("execution_receipts_sha256"),
}
if local != expected_local:
    raise SystemExit("ABORT: transfer source receipts differ")
law = report.get("law_separation", {})
reference = law.get("reference_measurement_law", {})
target = law.get("target_measurement_law", {})
if reference != {
    "usage_allocation": "finite-dirichlet",
    "dirichlet_k": 28.154043586960896,
    "sis_asoe_rank_transport": True,
} or target != {
    "game_mode": "possession", "team_factors": True,
    "usage_allocation": "production-multinomial",
    "game_sim_usage_env": "", "dirichlet_k": None,
    "td_ledger": False,
} or law.get("effect_may_be_law_dependent") is not True:
    raise SystemExit("ABORT: transfer measurement-law receipt differs")
gate = report.get("gate", {})
conditions = gate.get("conditions", {})
quality = gate.get("quality_conditions", {})
diversity = gate.get("raw_diversity_diagnostics", {})
quality_names = {
    "aggregate_mean_improves", "at_least_three_seed_means_improve",
    "aggregate_q25_nonworse",
}
diversity_names = {
    "roster_diversity_at_least_80pct",
    "stack_core_diversity_at_least_80pct",
    "dominant_game_diversity_at_least_80pct",
}
if gate.get("version") != "atlas-current-money-transfer-gate-v1" or \
        gate.get("rows") != 270 or gate.get("slates") != 54 or \
        set(quality) != quality_names or set(diversity) != diversity_names or \
        set(conditions) != quality_names | diversity_names or \
        gate.get("passes_part_a_transfer") is not all(quality.values()) or \
        gate.get("passes_original_all_six") is not all(conditions.values()):
    raise SystemExit("ABORT: transfer gate contract differs")
disposition = report.get("transfer_disposition", {})
mechanical = disposition.get("mechanical", {})
effect = disposition.get("effect", {})
if mechanical.get("passes") is not True or \
        len(mechanical.get("conditions", {})) != 6 or \
        not all(mechanical["conditions"].values()) or \
        effect.get("evaluated") is not True or \
        effect.get("passes") is not gate.get("passes_part_a_transfer") or \
        effect.get("conditions") != quality:
    raise SystemExit("ABORT: transfer mechanical/effect disposition differs")
summary = report.get("proxy_summary", {})
numeric = [
    gate.get("aggregate_mean_delta"), gate.get("aggregate_q25_delta"),
    summary.get("identity_tolerance"),
    summary.get("mean_proxy_minus_exact_slack"),
    summary.get("mean_proxy_exact_rank_correlation_union"),
]
numeric.extend(gate.get("per_seed_mean_delta", {}).values())
numeric.extend(gate.get("mean_diversity_ratios", {}).values())
numeric.extend(summary.get("mean_top_world_overlap", {}).values())
numeric.extend(summary.get("mean_cutoff_ties", {}).values())
reach = report.get("combination_reach", {})
if set(reach) != {"unique_player_pairs", "unique_qb_stack_cores"}:
    raise SystemExit("ABORT: transfer combination-reach output differs")
for metric in reach.values():
    if metric.get("gating") is not False or set(metric) != {
        "incumbent", "attainable", "attainable_to_incumbent_ratio", "gating",
    }:
        raise SystemExit("ABORT: transfer combination-reach contract differs")
    for distribution in (
        metric["incumbent"], metric["attainable"],
        metric["attainable_to_incumbent_ratio"],
    ):
        if set(distribution) != {"mean", "q10", "median", "minimum", "maximum"}:
            raise SystemExit("ABORT: transfer reach distribution differs")
        numeric.extend(distribution.values())
if len(gate.get("per_seed_mean_delta", {})) != 5 or \
        not all(math.isfinite(float(value)) for value in numeric):
    raise SystemExit("ABORT: transfer metrics are invalid")
paired = summary.get("paired_exact_quality", {})
if set(paired) != {"wins", "ties", "losses"} or sum(paired.values()) != 10800:
    raise SystemExit("ABORT: transfer paired-quality count differs")
if "pre-lock atlas mvp shadow" not in str(report.get("consequence", "")).lower():
    raise SystemExit("ABORT: transfer consequence restriction differs")
print(
    "ATLAS_MONEY_TRANSFER_VALIDATED",
    f"part_a={gate['passes_part_a_transfer']}",
    f"all_six={gate['passes_original_all_six']}",
    f"mean_delta={gate['aggregate_mean_delta']:.6f}",
)
PY

mv "$EXEC_TMP" "$OUT/execution.json"
mv "$REPORT_TMP" "$OUT/report.json"
sha256sum "$OUT/execution.json" > "$OUT/execution.sha256"
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
echo "ATLAS_MONEY_TRANSFER_HARVESTED $EXEC"
