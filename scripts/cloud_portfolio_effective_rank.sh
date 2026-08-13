#!/bin/bash
# Launch the frozen outcome-blind incumbent portfolio effective-rank diagnostic.
# Usage: cloud_portfolio_effective_rank.sh <AUDIT_IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-incumbent-effective-rank-v1
PANEL=20260812-pitclean-e80-selected-tabpfn-active-v2
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/portfolio-effective-rank-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-13-portfolio-effective-rank-protocol.md"
G2="$ROOT/reports/g2-qb-gumbel-runs/20260812-g2-qb-gumbel-factor-v3/report.json"
PANEL_DIR="$ROOT/reports/panel-runs/$PANEL"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable effective-rank image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable effective-rank code SHA required"; exit 2;;
esac
for path in "$PROTOCOL" "$G2" "$PANEL_DIR/manifest.txt" \
  "$PANEL_DIR/acceptance_promote.txt"; do
  [ -s "$path" ] || { echo "ABORT: effective-rank prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable effective-rank execution already recorded"; exit 2; }

"$ROOT/.venv/bin/python" - "$G2" "$PANEL" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") != "g2-dependence-gate-fails" or \
        report.get("exact80_licensed") is not False or \
        not report.get("invariants", {}).get("passes"):
    raise SystemExit("ABORT: effective-rank run lacks terminal valid G2 failure")
if report.get("selected_eval_panel") != sys.argv[2]:
    raise SystemExit("ABORT: effective-rank panel differs from G2 incumbent")
PY

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "panel=$PANEL" "source=promoted" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "g2_report_sha256=$(sha256sum "$G2" | awk '{print $1}')" \
  "panel_manifest_sha256=$(sha256sum "$PANEL_DIR/manifest.txt" | awk '{print $1}')" \
  "panel_acceptance_sha256=$(sha256sum "$PANEL_DIR/acceptance_promote.txt" | awk '{print $1}')" \
  'expected_slates=107' 'entries=80' 'worlds=10000' \
  'seasons=2019 2021 2022 2023 2024 2025' \
  'lines=187 194 200 210 220 230 240' \
  'book_sizes=20 40 80' 'random_books=20' 'random_seed=20260812' \
  > "$OUT/manifest.txt"

JOB=portfolio-effective-rank-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python \
  --args "scripts/analyze_portfolio_effective_rank.py,--panel,$PANEL,--source,promoted" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 16Gi --cpu 8 \
  --max-retries 0 --task-timeout 10800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: effective-rank job deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: effective-rank execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "PORTFOLIO_EFFECTIVE_RANK_LAUNCHED $EXEC"
