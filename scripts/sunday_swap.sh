#!/usr/bin/env bash
# Sunday scratch / late swap, one command (2026-09-24, after the laptop's HIGH finding that swaps could not re-publish
# under ENTER_ORDER=fewest-low). Swaps change CELLS only: the published bundle's row->contest map is frozen, so no lineup
# moves between contests (after a lock DraftKings cannot re-assign an entry), and a lineup entered in several contests is
# edited in every one of them.
#
#   source scripts/week_env.sh && ENTER_LAYOUT=head ENTER_ORDER=fewest-low week_env 3
#   scripts/sunday_swap.sh ROW:OUT_DD:IN_DD [ROW:OUT_DD:IN_DD ...]      # ROW = 1-based row of the bundle's own upload
#   (scripts/swap_suggest.py proposes replacements; apply_swaps.py checks legality, locks and the fresh DK feed)
#
# Steps: the published bundle (ENTER/ ->) and the upload it was built from (its ENTER-all-rows-*-KEEPERS.csv) ->
# apply_swaps.py (receipt <OUT_CSV>.swap.json, fresh DK feed saved) -> relayout_enter.sh with ENTER_FROZEN_BUNDLE (checks
# that only the receipt's cells changed) -> verified atomic publish -> a TODAY line. A failure leaves ENTER/ unchanged.
set -uo pipefail
: "${OUT:?source scripts/week_env.sh and call week_env WEEK first}" "${GROUP:?}" "${CONTESTS_JSON:?}" "${PROD:?}" "${PROD_PY:?}"
[ $# -ge 1 ] || { echo "usage: $0 ROW:OUT_DD:IN_DD [...]" >&2; exit 2; }
log(){ printf '%s %s\n' "$(date -u +%H:%M:%SZ)" "$*"; }
E="$OUT/ENTER"; [ -L "$E" ] || { echo "no published ENTER bundle at $E" >&2; exit 2; }
B=$(readlink -f "$E"); CUR=$(basename "$B")
BASEUP=$(ls "$B"/ENTER-all-rows-*-KEEPERS.csv 2>/dev/null | head -1); [ -f "$BASEUP" ] || { echo "no upload copy in $B" >&2; exit 2; }
ROOT=$(echo "$CUR" | sed -E 's/(-swap[0-9]+|-live|-promoted)+$//')
FRAMEDIR="$OUT/after-$ROOT/paid-vetted"; [ -f "$FRAMEDIR/frame.parquet" ] || { echo "no frame at $FRAMEDIR (bundle $CUR)" >&2; exit 2; }
STEM=$(echo "$CUR" | sed -E 's/-swap[0-9]+$//'); N=1; while [ -e "$OUT/enter-bundles/$STEM-swap$N" ]; do N=$((N + 1)); done
NEW="$STEM-swap$N"; OUTCSV="$OUT/upload-$NEW.csv"
ARGS=(); for s in "$@"; do ARGS+=(--swap "$s"); done
log "bundle $CUR; base upload $(basename "$BASEUP"); frame $FRAMEDIR; new tag $NEW"
PYTHONPATH="$PROD/src" "$PROD_PY" "$PROD/scripts/apply_swaps.py" "$BASEUP" "$FRAMEDIR" "$OUTCSV" "${ARGS[@]}" --group "$GROUP" \
    --save-fresh "$OUT/dk-fresh-$NEW.json" ${SWAP_EXTRA_ARGS:-} \
  || { echo "apply_swaps refused (see above); ENTER/ unchanged" >&2; exit 1; }
ENTER_FROZEN_BUNDLE="$B" CONTESTS_JSON="$CONTESTS_JSON" PROD="$PROD" PY="$PROD_PY" \
  "$PROD/scripts/relayout_enter.sh" "$OUTCSV" "$OUT" "$NEW" > "$OUT/swap-$NEW.log" 2>&1 \
  || { echo "SWAP RE-PUBLISH FAILED (see $OUT/swap-$NEW.log); ENTER/ unchanged" >&2; tail -3 "$OUT/swap-$NEW.log" >&2; exit 1; }
grep -q 'published bundle' "$OUT/swap-$NEW.log" || { echo "swap did not publish; ENTER/ unchanged" >&2; exit 1; }
printf 'SWAP: published %s at %s (%s); receipt %s; rollback = enter-bundles/%s\n' "$NEW" "$(date -u +%H:%M:%SZ)" "$*" \
  "$(basename "$OUTCSV").swap.json" "$CUR" >> "$OUT/TODAY-30-LATEST.md"
log "published: $E -> $(readlink -f "$E"); the DK-entries watcher refills the export from it."
