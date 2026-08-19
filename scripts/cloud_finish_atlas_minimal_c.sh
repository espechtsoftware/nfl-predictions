#!/usr/bin/env bash
set -euo pipefail

# Strict finisher for the minimal ATLAS world-selection C test. Runs only
# after every registered execution is terminal: verifies all 54
# executions succeeded, downloads every cell receipt, and aggregates the
# registered fields into one create-only report — with and without the
# four-seed recovery slate (2025 W1), per the reconciled briefing review.
# The predeclared prior is NEGATIVE: a null closes the world-ranking
# family permanently; no adoption can follow from this aggregate alone.

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260818-atlas-minimal-world-selection-c-v1
OUT="$ROOT/reports/atlas-minimal-c-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-minimal-world-selection-c-runs/$RUN_ID
EXECUTIONS="$OUT/executions.txt"
AGGREGATE="$OUT/aggregate-report.json"

[ -f "$EXECUTIONS" ] || {
  echo "ERROR: ATLAS C executions ledger is missing" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ERROR: ATLAS C executions ledger is not 54 cells" >&2; exit 2; }
[ -e "$AGGREGATE" ] && {
  echo "ERROR: ATLAS C aggregate already exists (create-only)" >&2; exit 2; }

while read -r SEASON WEEK JOB EXECUTION URI; do
  STATE=$(gcloud run jobs executions describe "$EXECUTION" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.conditions[0].status)' 2>/dev/null || echo "")
  [ "$STATE" = "True" ] || {
    echo "ERROR: ATLAS C cell $SEASON-$WEEK ($EXECUTION) is $STATE" >&2
    exit 2; }
  gsutil -q stat "$URI" || {
    echo "ERROR: ATLAS C cell object missing: $URI" >&2; exit 2; }
done < "$EXECUTIONS"

mkdir -p "$OUT/cells"
gsutil -m cp "$PREFIX/slate-*.json" "$OUT/cells/" >/dev/null 2>&1

"$ROOT/.venv/bin/python" - "$OUT" <<'PY'
import json
import sys
from hashlib import sha256
from pathlib import Path

out = Path(sys.argv[1])
cells = sorted(out.glob("cells/slate-*.json"))
if len(cells) != 54:
    raise SystemExit(f"ERROR: ATLAS C downloaded {len(cells)} cells, not 54")

rows = []
for path in cells:
    receipt = json.loads(path.read_text())
    if receipt.get("smoke"):
        raise SystemExit(f"ERROR: smoke receipt in the grid: {path.name}")
    modes = [seed["reproduction"]["mode"] for seed in receipt["seeds"]]
    if any(mode != "bq-identities-and-artifact-totals" for mode in modes):
        raise SystemExit(f"ERROR: unproven reproduction in {path.name}")
    rows.append({
        "season": int(receipt["season"]),
        "week": int(receipt["week"]),
        "sha256": sha256(path.read_bytes()).hexdigest(),
        "paired_delta_c": float(receipt["paired_delta_c"]),
        "control_c": float(receipt["control"]["c_score"]),
        "treatment_c": float(receipt["treatment"]["c_score"]),
        "control": receipt["control"],
        "treatment": receipt["treatment"],
        "seeds": len(receipt["seeds"]),
        "actual_parity_max_delta": receipt["actual_parity_max_delta"],
    })

def block(subset, label):
    deltas = [r["paired_delta_c"] for r in subset]
    return {
        "label": label,
        "n_slates": len(subset),
        "mean_paired_delta_c": sum(deltas) / len(deltas),
        "treatment_better": sum(d > 0 for d in deltas),
        "control_better": sum(d < 0 for d in deltas),
        "tied": sum(d == 0 for d in deltas),
        "mean_control_c": sum(r["control_c"] for r in subset) / len(subset),
        "mean_treatment_c": sum(r["treatment_c"] for r in subset) / len(subset),
    }

full = block(rows, "all-54")
no_recovery = block(
    [r for r in rows if not (r["season"] == 2025 and r["week"] == 1)],
    "without-four-seed-slate",
)
report = {
    "run_id": "20260818-atlas-minimal-world-selection-c-v1",
    "predeclared_prior": "negative",
    "uses_realized_outcomes": True,
    "production_change_licensed": False,
    "aggregate": full,
    "aggregate_without_recovery_slate": no_recovery,
    "per_slate": rows,
}
payload = json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
target = out / "aggregate-report.json"
if target.exists():
    raise SystemExit("ERROR: aggregate exists (create-only)")
target.write_text(payload)
print(
    "ATLAS_C_AGGREGATED",
    f"mean_delta_c={full['mean_paired_delta_c']:.4f}",
    f"treatment_better={full['treatment_better']}/54",
    f"sha256={sha256(payload.encode()).hexdigest()}",
)
PY
sha256sum "$AGGREGATE" "$EXECUTIONS" "$OUT/manifest.txt" > "$OUT/finish.sha256"
echo "ATLAS_C_FINISHED $RUN_ID"
