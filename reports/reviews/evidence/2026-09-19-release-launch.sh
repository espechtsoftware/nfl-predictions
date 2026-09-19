#!/usr/bin/env bash
# Immutable, supervised three-lane release window; never edits the host runtime.
set -euo pipefail
ROOT=/home/erich/projects/.nfl-predictions-worktrees/paid-source-experiments
STATE=/home/erich/.local/state/nfl-dfs/lab-launcher-registry
SELF="$ROOT/reports/reviews/evidence/2026-09-19-release-launch.sh"
case "${1:-0}" in
  0) lane=build-features; next=1 ;;
  1) lane=tabpfn-gen; next=2 ;;
  2) lane=project-slate; next=3 ;;
  3) exec /home/erich/projects/nfl-predictions/.venv/bin/python -u "$ROOT/reports/reviews/evidence/2026-09-19-release-supervisor.py" ;;
  *) exit 2 ;;
esac
exec "$ROOT/scripts/launcher_registry.sh" run --root "$ROOT" --state-root "$STATE" \
  --lane "$lane" --owner production --target-prefixes input-repair-20260919 -- "$SELF" "$next"
