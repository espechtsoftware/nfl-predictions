#!/usr/bin/env bash
# Host-side fallback for the DraftKings pulls while the Cloud Run egress 403 is open.
# The loop is intentionally small: it runs the same repository CLI that the deployed jobs use, once per hour, and
# leaves the provider/BigQuery work to the application.  Use --check before starting it and --once only for a deliberate
# operator-run pull.  This script never changes Cloud Run jobs or schedulers.
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROD=${PROD:-$(cd -- "$SCRIPT_DIR/.." && pwd)}
PROD_PY=${PROD_PY:-${NFL_PREDICTIONS_PY:-/home/erich/projects/nfl-predictions/.venv/bin/python}}
CLI=${CLI:-$PROD/.venv/bin/nfl-dfs}
GCP_PROJECT=${GCP_PROJECT:-nfl-predictions-503414}
INTERVAL_SECONDS=${INTERVAL_SECONDS:-3600}
PID_FILE=${PID_FILE:-${OUT:-$HOME/week1-sunday}/host_ingest_dk_loop.pid}
LOCK_FILE=${LOCK_FILE:-${PID_FILE}.lock}
MODE=${1:-loop}

usage() {
  cat <<'EOF'
usage: host_ingest_dk_loop.sh [--check|--once]

  --check  validate the local checkout, venv, CLI and project without provider calls
  --once   run ingest-dk and the opt-in ingest-contests poll once, then exit
  (none)   run the pair hourly until stopped
EOF
}

if [[ "$MODE" == "--help" || "$MODE" == "-h" ]]; then usage; exit 0; fi
[[ "$MODE" == "loop" || "$MODE" == "--check" || "$MODE" == "--once" ]] || { usage >&2; exit 2; }

fail() { echo "host DK ingest: $*" >&2; exit 2; }
[[ -d "$PROD" ]] || fail "production checkout missing: $PROD"
[[ -x "$PROD_PY" ]] || fail "PROD_PY is not executable: $PROD_PY"
[[ "$GCP_PROJECT" == "nfl-predictions-503414" ]] || fail "unexpected GCP_PROJECT=$GCP_PROJECT (refusing a wrong project)"
[[ "$INTERVAL_SECONDS" =~ ^[1-9][0-9]*$ ]] || fail "INTERVAL_SECONDS must be a positive integer"
command -v flock >/dev/null 2>&1 || fail "flock is required for single-instance protection"

export PYTHONPATH="$PROD/src${PYTHONPATH:+:$PYTHONPATH}"
if [[ -x "$CLI" ]]; then
  CLI_CMD=("$CLI")
else
  CLI_CMD=("$PROD_PY" -m nfl_dfs.cli)
fi

if [[ "$MODE" == "--check" ]]; then
  "$PROD_PY" -c 'import nfl_dfs.cli' >/dev/null || fail "cannot import nfl_dfs.cli from $PROD"
  printf 'host DK ingest check ok: project=%s cli=%q pid_file=%s interval=%ss\n' \
    "$GCP_PROJECT" "${CLI_CMD[*]}" "$PID_FILE" "$INTERVAL_SECONDS"
  exit 0
fi

mkdir -p "$(dirname -- "$PID_FILE")" "$(dirname -- "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
flock -n 9 || fail "another host ingest loop holds $LOCK_FILE"
if [[ -f "$PID_FILE" ]]; then
  old_pid=$(cat "$PID_FILE" 2>/dev/null || true)
  if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
    fail "pid $old_pid from $PID_FILE is still running"
  fi
fi
printf '%s\n' "$$" >"$PID_FILE"
cleanup() { rm -f "$PID_FILE"; }
trap cleanup EXIT INT TERM

run_pull() {
  local label=$1; shift
  local extra=()
  [[ "$label" == "ingest-contests" ]] && extra=(INGEST_CONTESTS_ENABLED=1)
  local started status
  started=$(date -u +%FT%TZ)
  echo "$started starting $label (project=$GCP_PROJECT)"
  set +e
  (cd "$PROD" && env GCP_PROJECT="$GCP_PROJECT" PYTHONPATH="$PYTHONPATH" "${extra[@]}" "${CLI_CMD[@]}" "$@")
  status=$?
  set -e
  echo "$(date -u +%FT%TZ) $label exit=$status"
  return "$status"
}

run_pair() {
  local dk_status contests_status
  run_pull ingest-dk ingest-dk; dk_status=$?
  run_pull ingest-contests ingest-contests; contests_status=$?
  if ((dk_status != 0 || contests_status != 0)); then
    echo "$(date -u +%FT%TZ) host DK ingest pair failed: ingest-dk=$dk_status ingest-contests=$contests_status" >&2
    return 1
  fi
  echo "$(date -u +%FT%TZ) host DK ingest pair succeeded"
}

while :; do
  cycle_started=$(date +%s)
  set +e
  run_pair
  pair_status=$?
  set -e
  [[ "$MODE" == "--once" ]] && exit "$pair_status"
  next=$((cycle_started + INTERVAL_SECONDS)); now=$(date +%s); delay=$((next - now)); ((delay > 0)) || delay=1
  echo "$(date -u +%FT%TZ) next host DK ingest in ${delay}s (last_status=$pair_status)"
  sleep "$delay"
done
