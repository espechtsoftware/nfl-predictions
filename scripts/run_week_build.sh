#!/usr/bin/env bash
# Stable timer entrypoint for the Sunday build.  It sources the same environment as the interactive runbook and then
# execs the real driver, so systemd does not depend on an untracked /home/erich/week<W>-sunday-build.sh wrapper.
set -Eeuo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ -z "${WEEK:-}" ]]; then
  WEEK=${1:?usage: run_week_build.sh WEEK [driver args...]}
  shift
fi
# shellcheck disable=SC1091
source "$SCRIPT_DIR/week_env.sh"
week_env "$WEEK" "${GROUP:-}"
"$PROD_PY" "$SCRIPT_DIR/check_week_runtime.py" --role build
# Every money-path call into the pinned lab clone must match its signatures (reviewer 2026-10-05: a mocked unit test
# could not catch union_reselect passing a keyword the pinned optimize lacks). Hard: a mismatch or a missing clone stops.
"$PROD_PY" "$SCRIPT_DIR/check_lab_api.py" --clone "$CLONE"
if [[ "${1:-}" == '--check' ]]; then exit 0; fi
# A runtime-valid checkout can still have missing or stale warehouse inputs.
# Keep a distinct receipt per invocation, including failed preflights.
INPUT_RECEIPT=$(mktemp "$OUT/build-inputs-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX.json")
"$PROD_PY" "$SCRIPT_DIR/check_build_inputs.py" \
  --season "$SEASON" --week "$WEEK" \
  --chosen-dose "$CHOSEN_FILE" --contests "$CONTESTS_JSON" \
  --draft-group "$GROUP" \
  ${MIN_PROJ_GENERATED_AT:+--min-generated-at "$MIN_PROJ_GENERATED_AT"} \
  --receipt "$INPUT_RECEIPT"
exec "$PROD/scripts/sunday_build_host.sh" "$@"
