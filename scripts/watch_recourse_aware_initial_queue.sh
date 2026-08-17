#!/usr/bin/env bash
set -uo pipefail

# Wait for strict ATLAS closure, build the immutable commit, and carry the
# recourse-aware score-free family through its canary, grid and strict harvest.
# Usage: watch_recourse_aware_initial_queue.sh <code-sha>

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
CODE_SHA=${1:-}
PREFLIGHT="$ROOT/reports/atlas-cbc-32g-full-cell-preflight-runs/20260816-atlas-cbc-32g-full-cell-preflight-v1"
REPAIR5="$ROOT/reports/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair5"
PARITY="$ROOT/reports/atlas-interaction-parity-runs/20260816-atlas-interaction-parity-v1"
HISTORICAL="$ROOT/reports/atlas-historical-score-runs/20260816-atlas-historical-score-diagnostic-v3"
RUN_ID=20260817-recourse-aware-initial-book-scorefree-v1
OUT="$ROOT/reports/recourse-aware-initial-book-runs/$RUN_ID"
TAG="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:recourse-initial-${CODE_SHA:0:7}"

[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "Usage: $0 <code-sha>" >&2; exit 2; }
git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}" || exit 2

queue_ready() {
  "$ROOT/.venv/bin/python" - "$PREFLIGHT" "$REPAIR5" "$PARITY" \
    "$HISTORICAL" <<'PY'
import pathlib,sys
preflight,repair5,parity,historical=(pathlib.Path(value) for value in sys.argv[1:])
def completion(path):
 p=path/"completion.txt"
 if not p.is_file(): return None
 return dict(line.split("=",1) for line in p.read_text().splitlines() if "=" in line)
p=completion(preflight)
if p is None: raise SystemExit(1)
if p.get("status")=="False":
 q=completion(parity)
 raise SystemExit(0 if q and q.get("status")=="True" else 1)
if p.get("status")!="True": raise SystemExit(2)
if completion(repair5) is not None:
 raise SystemExit(0 if all((historical/name).is_file() for name in ("completion.txt","report.json")) else 1)
q=completion(parity)
raise SystemExit(0 if (repair5/"terminal-census-completion.txt").is_file() and q and q.get("status")=="True" else 1)
PY
}

while true; do
  queue_ready
  RC=$?
  [ "$RC" -eq 0 ] && break
  [ "$RC" -eq 1 ] || exit "$RC"
  printf '%s RECOURSE_INITIAL_QUEUE awaiting_strict_atlas_closure\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 300
done

[ ! -e "$OUT" ] || {
  echo "ABORT: recourse-aware run already exists" >&2; exit 3; }
ARCHIVE=$(mktemp -d)
trap 'rm -rf -- "$ARCHIVE"' EXIT
git -C "$ROOT" archive "$CODE_SHA" | tar -x -C "$ARCHIVE"
BUILD_ID=$(gcloud builds submit "$ARCHIVE" --project "$PROJECT" \
  --config "$ARCHIVE/cloudbuild.yaml" --substitutions "_IMAGE=$TAG" \
  --async --format='value(id)') || exit $?
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || exit 2
printf '%s RECOURSE_INITIAL_BUILD launched=%s code=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$BUILD_ID" "$CODE_SHA"
while true; do
  STATUS=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
    --format='value(status)') || exit $?
  printf '%s RECOURSE_INITIAL_BUILD status=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$STATUS"
  case "$STATUS" in
    SUCCESS) break ;;
    QUEUED|PENDING|WORKING) sleep 60 ;;
    *) exit 2 ;;
  esac
done
DIGEST=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
  --format='value(results.images[0].digest)') || exit $?
[[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 2
IMAGE="${TAG%:*}@${DIGEST}"
rm -rf -- "$ARCHIVE"
trap - EXIT

"$ROOT/scripts/cloud_recourse_aware_initial_scorefree.sh" \
  "$IMAGE" "$CODE_SHA" "$BUILD_ID" || exit $?

execution_status() {
  gcloud run jobs executions describe "$1" --project "$PROJECT" \
    --region "$REGION" --format=json | "$ROOT/.venv/bin/python" -c '
import json,sys
x=json.load(sys.stdin); rows=[row for row in x.get("status",{}).get("conditions",[]) if row.get("type")=="Completed"]
print(rows[0].get("status","Unknown") if len(rows)==1 else "Unknown")
'
}
while true; do
  running=0; succeeded=0; failed=0
  while read -r _season _week _job execution _uri; do
    state=$(execution_status "$execution") || exit $?
    case "$state" in
      Unknown) running=$((running + 1)) ;;
      True) succeeded=$((succeeded + 1)) ;;
      *) failed=$((failed + 1)) ;;
    esac
  done < "$OUT/executions.txt"
  printf '%s RECOURSE_INITIAL_GRID running=%s succeeded=%s failed=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$running" "$succeeded" "$failed"
  [ "$running" -eq 0 ] && break
  sleep 300
done
[ "$failed" -eq 0 ] || {
  echo "RECOURSE_INITIAL_GRID_TERMINAL_FAILURE failed=$failed" >&2; exit 10; }
"$ROOT/scripts/cloud_finish_recourse_aware_initial_scorefree.sh"
