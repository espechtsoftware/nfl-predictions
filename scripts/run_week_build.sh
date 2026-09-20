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
if [[ "${1:-}" == '--check' ]]; then exit 0; fi
exec "$PROD/scripts/sunday_build_host.sh" "$@"
