#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260815-cbwu-order-invariant-repair-v1
OUT="$ROOT/reports/cbwu-order-invariant-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"

[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] || {
  echo "ABORT: CBWU-OI manifest/execution is incomplete" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable CBWU-OI report already exists" >&2; exit 2; }
EXEC=$(tr -d '[:space:]' < "$EXECUTION")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: CBWU-OI execution is not successful ($STATE)" >&2; exit 1; }
OUTPUT_URI=$(awk -F= '$1=="output_uri" {print $2}' "$MANIFEST")
TMP=$(mktemp "$OUT/.report.XXXXXX.json")
trap 'rm -f "$TMP"' EXIT
gcloud storage cp "$OUTPUT_URI" "$TMP" --project "$PROJECT" >/dev/null
"$ROOT/.venv/bin/python" - "$TMP" "$MANIFEST" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
manifest = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line
)
for key in ("version", "code_sha", "image", "forensic_manifest_sha256",
            "repair_protocol_sha256"):
    if str(report.get(key)) != manifest.get(key):
        raise SystemExit(f"ABORT: CBWU-OI {key} differs")
if report.get("uses_realized_outcomes") is not False or \
        manifest.get("uses_realized_outcomes") != "false":
    raise SystemExit("ABORT: CBWU-OI report is not outcome-free")
if report.get("source_panels") != manifest.get("source_panels", "").split(",") or \
        len(report.get("source_artifacts", [])) != 270 or \
        len(report.get("slates", [])) != 54:
    raise SystemExit("ABORT: CBWU-OI source/slate coverage differs")
for slate in report["slates"]:
    if slate.get("uses_realized_outcomes") is not False or \
            len(slate.get("rotations", [])) != 5 or \
            not slate.get("order_invariant") or \
            len(slate.get("treatment", {}).get("identities", [])) != 80:
        raise SystemExit("ABORT: CBWU-OI slate invariant differs")
    if any(not row.get("candidate_identities_exact_vs_canonical") or
           not row.get("selected_identities_exact_vs_canonical")
           for row in slate["rotations"]):
        raise SystemExit("ABORT: CBWU-OI cyclic identity differs")
aggregate = report.get("aggregate", {})
allowed = {"cbwu-oi-scorefree-gate-passes", "cbwu-oi-scorefree-gate-fails"}
if aggregate.get("slates") != 54 or \
        aggregate.get("cyclic_comparisons") != 216 or \
        aggregate.get("disposition") not in allowed or \
        set(aggregate.get("conditions", {})) != {
            "all_rotations_identity_exact",
            "aggregate_world_coverage_improves",
            "at_least_three_blocks_improve",
            "pair_coverage_at_least_90pct",
            "triple_coverage_at_least_90pct",
            "exact_candidate_and_entry_counts",
        }:
    raise SystemExit("ABORT: CBWU-OI aggregate contract differs")
if bool(aggregate.get("passes_scorefree_gate")) != \
        all(aggregate["conditions"].values()) or \
        bool(aggregate.get("passes_scorefree_gate")) != \
        (aggregate.get("disposition") == "cbwu-oi-scorefree-gate-passes"):
    raise SystemExit("ABORT: CBWU-OI disposition is inconsistent")
if "cannot change production" not in str(report.get("consequence", "")):
    raise SystemExit("ABORT: CBWU-OI no-promotion consequence is missing")
print(
    "CBWU_OI_VALIDATED",
    aggregate["disposition"],
    f"coverage_delta={aggregate['mean_world_coverage_delta']:.8f}",
)
PY
mv "$TMP" "$OUT/report.json"
trap - EXIT
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
echo "CBWU_OI_HARVESTED $EXEC"
