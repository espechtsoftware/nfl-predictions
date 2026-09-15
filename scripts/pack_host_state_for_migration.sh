#!/usr/bin/env bash
# Pack the host-only state a machine move needs and upload it to the project's private bucket.
#   scripts/pack_host_state_for_migration.sh              # pack + upload to gs://nfl-predictions-503414-raw/host-migration/<date>/
#   scripts/pack_host_state_for_migration.sh --no-upload  # pack only (tarballs under /home/erich/host-migration/)
# Skips caches (direct_runner/work), the 17 GB worktree archive and the 3 GB monitor logs; includes ENTERED/ (your
# DraftKings entries exports) — the bucket is private to the project, but delete the upload once the laptop has it.
set -euo pipefail
STAMP=$(date -u +%Y%m%d); OUT=/home/erich/host-migration/$STAMP; mkdir -p "$OUT"; UPLOAD=1; [[ "${1:-}" == "--no-upload" ]] && UPLOAD=0
tar --exclude='direct_runner/work' -czf "$OUT/week1-sunday.tgz" -C /home/erich week1-sunday week2-sunday week2-sunday-build.sh week2-sunday-watchers.sh week1-sunday-build.sh 2>/dev/null
tar -czf "$OUT/dk-exports-results-2026-09-13.tgz" -C /home/erich/projects/nfl-predictions results/2026-09-13
tar -czf "$OUT/launcher-registry.tgz" -C /home/erich/.local/state/nfl-dfs lab-launcher-registry
tar -czf "$OUT/assistant-memory.tgz" -C /home/erich/.claude/projects -- -home-erich-projects-nfl-predictions/memory
tar -czf "$OUT/systemd-user-units.tgz" -C /home/erich/.config systemd/user 2>/dev/null || true
( cd "$OUT" && sha256sum *.tgz > SHA256SUMS && ls -la )
if [[ "$UPLOAD" == 1 ]]; then
  gcloud storage cp -r "$OUT" "gs://nfl-predictions-503414-raw/host-migration/" --quiet
  echo "uploaded to gs://nfl-predictions-503414-raw/host-migration/$STAMP/"
fi
