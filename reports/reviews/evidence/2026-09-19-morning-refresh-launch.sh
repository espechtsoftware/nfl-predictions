#!/usr/bin/env bash
# Acquire all three canonical writer lanes before the fixed readiness window.
# No scheduler, timer, image, or template changes. No automatic retry.
set -euo pipefail
TASK_REPO=/home/erich/projects/.nfl-predictions-worktrees/paid-source-experiments
TASK_STATE=/home/erich/.local/state/nfl-dfs/lab-launcher-registry
TASK_SELF="$TASK_REPO/reports/reviews/evidence/2026-09-19-morning-refresh-launch.sh"
TASK_REGISTRY="$TASK_REPO/scripts/launcher_registry.sh"
TASK_PYTHON=/home/erich/projects/nfl-predictions/.venv/bin/python
case "${1:-start}" in
  start) TASK_LANE=build-features; TASK_NEXT=features-held ;;
  features-held) TASK_LANE=tabpfn-gen; TASK_NEXT=cache-held ;;
  cache-held) TASK_LANE=project-slate; TASK_NEXT=all-held ;;
  all-held)
    export GCP_PROJECT=nfl-predictions-503414
    export PYTHONPATH="$TASK_REPO/src"
    export PYTHONDONTWRITEBYTECODE=1
    export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
    exec "$TASK_PYTHON" -X cpu_count=1 "$TASK_REPO/reports/reviews/evidence/2026-09-19-morning-refresh.py" execute
    ;;
  *) exit 2 ;;
esac
exec "$TASK_REGISTRY" run --root "$TASK_REPO" --state-root "$TASK_STATE" \
  --lane "$TASK_LANE" --owner production --target-prefixes morning-refresh-20260919 \
  -- "$TASK_SELF" "$TASK_NEXT"
