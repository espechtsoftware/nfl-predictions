#!/usr/bin/env bash
# Capture a Week-1 2026 team-grain SIS snapshot as a REVISION BASELINE.
#
# WHY (operator decision 2026-09-18).  The frozen pass-tail acquisition does not run until
# Week 5, when it fetches source weeks 1-4 in one go.  That is a RECONSTRUCTION: it asks the
# vendor in October what it said in September, and nothing checks whether those numbers were
# revised in between (OPEN-DEFECTS O-3b).  Stat corrections are ordinary in football.  This
# script takes an independent Week-1 snapshot NOW so the Week-5 fetch can be diffed against
# what the vendor actually published at the time.
#
# WHAT THIS IS NOT.  It is deliberately NOT the frozen acquisition and must never be passed
# off as one.  It writes outside the protocol's output tree, carries its own label, and does
# not touch `pass-tail-weekly.result.json` -- that artifact is one-shot and writing it early
# with incomplete weeks would burn the protocol's Week-5 slot.  It fetches only the three
# UNFILTERED team views; the wide/slot alignment views belong to the frozen run.
#
# COST: three requests against a documented 1,000-query weekly allowance.
#
# PREREQUISITE: the saved SIS session (expired 2026-09-18).  Run once, interactively:
#     sis-download login
# then verify with:  sis-download verify-login
set -euo pipefail
REPO=${REPO:-/home/erich/projects/nfl-predictions}
PY=${PY:-$REPO/.venv/bin/python}
OUT=${OUT:-$REPO/sis/revision-baseline-2026-w01-$(date -u +%Y%m%dT%H%M%SZ)}
SEASON=${SEASON:-2026}
WEEK=${WEEK:-1}

"$PY" -c "
from pathlib import Path
from nfl_dfs.ops import sis_downloads as sis
sis.verify_login(Path.home()/'.local'/'share'/'nfl-dfs'/'sis-playwright', 60.0)
print('SIS session verified')
"

mkdir -p "$OUT"
for REPORT in pass-defense-totals pass-defense-value pass-rush-totals; do
  echo "== $REPORT season $SEASON week $WEEK"
  "$PY" -m nfl_dfs.ops.sis_downloads export \
    --entity teams --report "$REPORT" \
    --season "$SEASON" --start-week "$WEEK" --end-week "$WEEK" \
    --output-dir "$OUT"
done

# Hash everything so a later comparison is exact rather than eyeballed.
( cd "$OUT" && sha256sum ./*.csv > SHA256SUMS.txt 2>/dev/null || true )
cat > "$OUT/README.md" <<NOTE
# SIS Week-1 2026 revision baseline (NOT the frozen acquisition)

Captured $(date -u +%Y-%m-%dT%H:%M:%SZ) at the operator's instruction, to make the Week-5
retrospective fetch checkable instead of assumed.

- Views: pass-defense-totals, pass-defense-value, pass-rush-totals (team entity, unfiltered).
- Season $SEASON, weeks $WEEK-$WEEK.
- This is NOT \`prospective-sis-pass-tail-weekly-acquisition-v1\` and carries no protocol standing.
  The frozen Week-5 run is unaffected and must still happen as specified.
- At Week 5, diff the protocol's fetch of week $WEEK against SHA256SUMS.txt here. A mismatch means
  the vendor revised published data, which is exactly what OPEN-DEFECTS O-3b warns is unguarded.
NOTE
echo "snapshot written to $OUT"
ls -l "$OUT"
