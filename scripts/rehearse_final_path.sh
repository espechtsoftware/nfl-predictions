#!/usr/bin/env bash
# rehearse_final_path.sh -- bounded, outcome-blind rehearsal of the exact reviewed Sunday final path on an ARCHIVED run:
#   qb classifier -> vet_book v2.1 -> vet_replace_v4 (fresh DK status) -> emit -> atomic ENTER layout -> promotion v1.2
#   -> relayout -> fill of a SYNTHETIC entries template. Everything is written under a scratch OUT dir; the live
#   /home/erich/week<W>-sunday, ENTER and Downloads are never touched. No DK entry key is read or written.
#   rehearse_final_path.sh RUN_DIR CLONE OUT_DIR [WEEK] [CONTESTS_JSON]
#   env: PROD (checkout with scripts/sunday_after_build.sh; default: this repo), PROD_PY, TOOLS (default: this dir)
set -euo pipefail
RUN=${1:?RUN_DIR}; CLONE=${2:?LAB_CLONE}; OUTDIR=${3:?scratch OUT_DIR}; WEEK=${4:-2}
HERE=$(cd "$(dirname "$0")" && pwd); export PROD=${PROD:-$(cd "$HERE/.." && pwd)}
export TOOLS=${TOOLS:-$PROD/scripts}; export PROD_PY=${PROD_PY:-$PROD/.venv/bin/python}
export CLONE EXPECT_SHA=${EXPECT_SHA:-$(git -C "$CLONE" rev-parse HEAD 2>/dev/null || echo unknown)}
mkdir -p "$OUTDIR"; export OUT=$OUTDIR
export CONTESTS_JSON=${5:-${CONTESTS_JSON:-$OUTDIR/contests.json}}
cp -n "$CONTESTS_JSON" "$OUT/contests.json" 2>/dev/null || true; export CONTESTS_JSON=$OUT/contests.json
source "$PROD/scripts/week_env.sh"; week_env "$WEEK" >/dev/null
export OUT=$OUTDIR TOOLS=${TOOLS} CONTESTS_JSON=$OUT/contests.json     # week_env keeps exported OUT/TOOLS; restate for clarity
TAG="REHEARSAL-$(basename "$RUN")-$(date -u +%H%M%SZ)"
echo "== rehearsal $TAG | PROD=$PROD | TOOLS=$TOOLS | CLONE=$CLONE | OUT=$OUT | K=$BOOK_ENTRIES layout=$ENTER_LAYOUT =="
PROMOTE_FIRST_ENTRY=1 "$PROD/scripts/sunday_after_build.sh" once "$RUN" "$TAG" | tee "$OUT/rehearsal-chain.log" | tail -n 8
AFTER="$OUT/after-$TAG"; test -f "$AFTER/paid-vetted-replaced/replace.json"
grep -q '^PROMOTION STEP:' "$OUT/TODAY-30-LATEST.md" || { echo "promotion hook did not run" >&2; exit 3; }
tail -n 4 "$AFTER/promotion.log"
B=$(readlink -f "$OUT/ENTER"); echo "ENTER -> $B"
"$PROD_PY" "$HERE/make_synthetic_entries_template.py" "$CONTESTS_JSON" "$OUT/SYNTHETIC-entries-template.csv"
frame=$(ls -td "$LIVE_DIR"/*/ | while read -r d; do [ -f "$d/frame.parquet" ] && { echo "$d/frame.parquet"; break; }; done)
"$PROD_PY" "$PROD/scripts/fill_dk_entries.py" "$OUT/SYNTHETIC-entries-template.csv" --contests "$CONTESTS_JSON" --enter-dir "$B" --out-dir "$B" --frame "$frame" | tail -n 3
test -s "$B/DKEntries-FILLED-keepers-first.csv" && echo "filled synthetic template: $(( $(wc -l < "$B/DKEntries-FILLED-keepers-first.csv") - 1 )) rows"
echo "REHEARSAL OK: $OUT (label: rehearsal; not a live bundle)"
