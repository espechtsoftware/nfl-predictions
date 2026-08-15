#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260815-cbwu-oi-construction-diagnostic-v1
OUT="$ROOT/reports/cbwu-oi-construction-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"

[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] || {
  echo "ABORT: CBWU-OI construction receipt is incomplete" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] || {
  echo "ABORT: immutable CBWU-OI construction report exists" >&2; exit 2; }
EXEC=$(tr -d '[:space:]' < "$EXECUTION")
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: CBWU-OI construction execution is not successful ($STATE)" >&2
  exit 1
}
OUTPUT_URI=$(awk -F= '$1=="output_uri" {print $2}' "$MANIFEST")
TMP=$(mktemp "$OUT/.report.XXXXXX.json")
trap 'rm -f "$TMP"' EXIT
gcloud storage cp "$OUTPUT_URI" "$TMP" --project "$PROJECT" >/dev/null
"$ROOT/.venv/bin/python" - "$TMP" "$MANIFEST" <<'PY'
import json
import math
import sys

r = json.load(open(sys.argv[1], encoding="utf-8"))
m = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[2], encoding="utf-8") if "=" in line
)
for key in (
    "version", "protocol_sha256", "forensic_manifest_sha256",
    "cbwu_oi_scorefree_report_sha256",
):
    if str(r.get(key)) != m.get(key):
        raise SystemExit(f"ABORT: CBWU-OI construction {key} differs")
for key, manifest_key in (
    ("analysis_code_sha", "code_sha"), ("analysis_image", "image"),
):
    if str(r.get(key)) != m.get(manifest_key):
        raise SystemExit(f"ABORT: CBWU-OI construction {key} differs")
identity = r.get("corrected_identity_source", {})
if (
    str(identity.get("generation")) != m.get("identity_generation")
    or identity.get("sha256") != m.get("identity_sha256")
):
    raise SystemExit("ABORT: CBWU-OI construction exact-P receipt differs")
if r.get("source_panels") != m.get("source_panels", "").split(",") or \
        len(r.get("source_artifacts", [])) != 270 or \
        len(r.get("records", [])) != 54:
    raise SystemExit("ABORT: CBWU-OI construction source coverage differs")
flags = {
    "uses_realized_candidate_scores": True,
    "scores_cbwu_oi_selected_80": False,
    "historical_arm_licensed": False,
    "production_change_licensed": False,
}
if any(r.get(key) is not value for key, value in flags.items()):
    raise SystemExit("ABORT: CBWU-OI construction evidence license differs")

structure_fields = {
    "salary", "distinct_games", "largest_team_block", "qb_stack_count",
    "bring_back_count", "qb_salary", "rb_salary", "wr_salary",
    "te_salary", "dst_salary",
}
slate_keys = set()
for row in r["records"]:
    slate_keys.add((int(row["season"]), int(row["week"])))
    budgets = (
        int(row["canonical_candidate_budget"]),
        int(row["cbwu_oi_candidate_budget"]),
        int(row["frozen_r0_candidate_budget"]),
    )
    if len(set(budgets)) != 1 or budgets[0] <= 80:
        raise SystemExit("ABORT: CBWU-OI construction budget differs")
    if not budgets[0] <= int(row["complete_union_candidates"]):
        raise SystemExit("ABORT: CBWU-OI construction union is too small")
    if not 0 <= int(row["pool_identity_overlap"]) <= budgets[0]:
        raise SystemExit("ABORT: CBWU-OI construction overlap differs")
    if len(row.get("exact_p_identity", [])) != 9 or \
            len(set(row["exact_p_identity"])) != 9 or \
            not math.isfinite(float(row["exact_p_score"])):
        raise SystemExit("ABORT: CBWU-OI construction exact-P differs")
    for arm in ("canonical", "cbwu_oi"):
        value = row.get(arm, {})
        if not math.isfinite(float(value.get("c_score", math.nan))) or \
                len(value.get("c_identity", [])) != 9 or \
                len(value.get("c_tied_identities", [])) != \
                int(value.get("c_tie_count", -1)) or \
                not 0 <= int(value.get("minimum_swaps_to_exact_p", -1)) <= 9 or \
                int(value.get("equally_closest_candidates", 0)) != \
                len(value.get("closest_identities", [])) or \
                not 0 <= int(value.get("exact_p_player_slots_represented", -1)) <= 9:
            raise SystemExit("ABORT: CBWU-OI construction pool result differs")
        structure = value.get("structure", {})
        if set(structure) != structure_fields or any(
            set(summary) != {"mean", "median", "q10", "q90"}
            or not all(math.isfinite(float(number)) for number in summary.values())
            for summary in structure.values()
        ):
            raise SystemExit("ABORT: CBWU-OI construction structure differs")

aggregate = r.get("aggregate", {})
tails = aggregate.get("c_tail_counts", {})
if aggregate.get("slates") != 54 or len(slate_keys) != 54 or \
        aggregate.get("candidate_budget_equal_all_slates") is not True or \
        set(tails) != {"187", "194", "200", "210", "220", "230", "240"}:
    raise SystemExit("ABORT: CBWU-OI construction aggregate differs")
for values in tails.values():
    if set(values) != {"canonical", "cbwu_oi"} or any(
        not 0 <= int(value) <= 54 for value in values.values()
    ):
        raise SystemExit("ABORT: CBWU-OI construction tails differ")
if {line: tails[line]["canonical"] for line in ("200", "210", "220", "230", "240")} != {
    "200": 8, "210": 6, "220": 3, "230": 1, "240": 0,
}:
    raise SystemExit("ABORT: canonical corrected C tails do not reproduce")
signs = aggregate.get("c_score_paired_signs", {})
if set(signs) != {"positive", "zero", "negative"} or \
        sum(int(value) for value in signs.values()) != 54:
    raise SystemExit("ABORT: CBWU-OI construction paired signs differ")

def walk(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if "selected" in key.lower() and key != "scores_cbwu_oi_selected_80":
                raise SystemExit("ABORT: selected-book field leaked into diagnostic")
            if key.lower() in {"s_score", "adoption_verdict"}:
                raise SystemExit("ABORT: prohibited diagnostic field is present")
            walk(child)
    elif isinstance(value, list):
        for child in value:
            walk(child)

walk(r)
if "cannot score or promote" not in str(r.get("consequence", "")):
    raise SystemExit("ABORT: CBWU-OI construction no-promotion consequence is absent")
print(
    "CBWU_OI_CONSTRUCTION_VALIDATED",
    f"delta={aggregate['mean_c_score']['cbwu_oi'] - aggregate['mean_c_score']['canonical']:.6f}",
    f"signs={signs}",
)
PY
mv "$TMP" "$OUT/report.json"
trap - EXIT
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
echo "CBWU_OI_CONSTRUCTION_HARVESTED $EXEC"
