#!/usr/bin/env bash
# Refinement 1 on the money path (operator, 2026-09-24): after the Sunday 10:30 CT inactives and BEFORE the upload,
# re-lay the published ENTER bundle out with flags from DraftKings' LIVE status (players declared active have lost their
# Q tag) instead of the Friday injury report, then publish it through relayout_enter.sh's verified atomic swap. The
# lineups do not change; only which contest gets which book row. Late-game Questionable players stay flagged (DK keeps
# their tag until their own inactives), so only resolved early-game players leave the flagged set.
#
#   source scripts/week_env.sh && ENTER_LAYOUT=head ENTER_ORDER=fewest-low week_env 3
#   scripts/sunday_live_relayout.sh --dry-run     # snapshot + what would move; writes a scratch copy only
#   scripts/sunday_live_relayout.sh               # publish (then do any scratch swaps, then upload)
#
# Order on Sunday: 10:30 inactives -> this (dry run, then publish) -> scratch swaps -> upload by 11:15.
# Refuses to run on a bundle that is already a live re-layout (run once), and needs ENTER_ORDER=fewest-low.
set -uo pipefail
: "${OUT:?source scripts/week_env.sh and call week_env WEEK first}" "${GROUP:?}" "${CONTESTS_JSON:?}" "${PROD:?}" "${PROD_PY:?}"
MODE=${1:-publish}
[[ "$MODE" == publish || "$MODE" == --dry-run ]] || { echo "usage: $0 [--dry-run]" >&2; exit 2; }
[[ "${ENTER_ORDER:-greedy}" == fewest-low ]] || { echo "live re-layout needs ENTER_ORDER=fewest-low (got ${ENTER_ORDER:-greedy})" >&2; exit 2; }
[[ -f "${OWNERSHIP_SETS:-}" ]] || { echo "sets file missing: ${OWNERSHIP_SETS:-<unset>}" >&2; exit 2; }
log(){ printf '%s %s\n' "$(date -u +%H:%M:%SZ)" "$*"; }

E="$OUT/ENTER"; [ -L "$E" ] || { echo "no published ENTER bundle at $E" >&2; exit 2; }
CUR=$(basename "$(readlink -f "$E")")
case "$CUR" in *-live) echo "the published bundle $CUR is already a live re-layout; refusing to run twice" >&2; exit 2 ;;
  *-swap*) echo "the published bundle $CUR carries swaps; a live re-layout now would re-order rows across contests -- refusing (run it BEFORE any swap)" >&2; exit 2 ;; esac
if [[ "$CUR" == *-promoted ]]; then
  BASE=${CUR%-promoted}; FINAL="$OUT/after-$BASE/paid-vetted-promoted"; UP="$OUT/upload-$BASE-promoted-paid-vetted-all.csv"; PIN=1
else
  BASE=$CUR; FINAL="$OUT/after-$BASE/paid-vetted-replaced"; [ -d "$FINAL" ] || FINAL="$OUT/after-$BASE/paid-vetted"
  UP="$OUT/upload-$BASE-paid-vetted-all.csv"; PIN=0
fi
for f in "$FINAL/book.csv" "$FINAL/vetting_final.json" "$UP"; do [ -f "$f" ] || { echo "missing $f (the published bundle's source)" >&2; exit 2; }; done
log "published bundle $CUR; source book $FINAL; upload $UP; promoted row pinned: $PIN"

SNAP="$OUT/dk-status-$(date -u +%Y%m%dT%H%M%SZ).csv"
PYTHONPATH="$PROD/src" "$PROD_PY" - "$GROUP" "$SNAP" <<'PY' || { echo "DK status snapshot FAILED" >&2; exit 1; }
import csv, sys
from nfl_dfs.ingest.dk_client import fetch_draftables
seen = {}
for d in fetch_draftables(int(sys.argv[1]))["draftables"]:
    st = d.get("status"); seen[str(d.get("playerId"))] = "" if st in (None, "None", "") else str(st)
with open(sys.argv[2], "w", newline="") as f:
    w = csv.writer(f); w.writerow(["id", "status"]); w.writerows(sorted(seen.items()))
print(f"DK status snapshot: {len(seen)} players, {sum(1 for s in seen.values() if s)} with a status -> {sys.argv[2]}")
PY

# what moves: the Saturday rule vs the live rule, on the same book and sets
PIN_ARG=(); (( PIN == 1 )) && PIN_ARG=(--pin-first)
PYTHONPATH="$PROD/src" "$PROD_PY" - "$FINAL" "$UP" "$CONTESTS_JSON" "$OWNERSHIP_SETS" "$SNAP" "$PIN" "${ENTER_LAYOUT:-sequential}" <<'PY' || exit 1
import sys
from pathlib import Path
from nfl_dfs.inference import enter_layout as EL
final, up, contests, sets, snap, pin, layout = sys.argv[1:8]
cs = EL._contests(Path(contests)); body = EL._read_rows(Path(up))[1]; prot = EL.protected_ranks(cs, layout)
kw = dict(book=Path(final) / "book.csv", vetting=Path(final) / "vetting_final.json", sets=Path(sets), pin_first=pin == "1",
          upload_rows=body, protect=prot)
sat, _ = EL.load_order("fewest-low", len(body), **kw)
live, info = EL.load_order("fewest-low", len(body), live_status=Path(snap), **kw)
a, b = set(sat[:prot]), set(live[:prot])
print(f"protected ranks {prot}: flagged rows Saturday rule {len(EL.flagged_positions(Path(final) / 'vetting_final.json', len(body)))}"
      f" -> live rule {info['flagged_rows']}; book rows newly protected {sorted(x + 1 for x in b - a)}, "
      f"leaving {sorted(x + 1 for x in a - b)}")
PY

if [[ "$MODE" == --dry-run ]]; then
  S="$OUT/.live-relayout-dryrun-$(date -u +%H%M%SZ)"; mkdir -p "$S"
  PYTHONPATH="$PROD/src" "$PROD_PY" -m nfl_dfs.inference.enter_layout write "$CONTESTS_JSON" "$UP" "$S" \
    --book "$FINAL/book.csv" --vetting "$FINAL/vetting_final.json" --live-status "$SNAP" "${PIN_ARG[@]}" > "$S/ENTER-layout.txt" \
    || { echo "dry-run layout FAILED" >&2; exit 1; }
  log "DRY RUN: nothing published; scratch layout in $S (ENTER-layout.txt)"; exit 0
fi

ENTER_LIVE_STATUS="$SNAP" ENTER_BOOK_DIR="$FINAL" ENTER_PIN_FIRST="$PIN" CONTESTS_JSON="$CONTESTS_JSON" PROD="$PROD" PY="$PROD_PY" \
  "$PROD/scripts/relayout_enter.sh" "$UP" "$OUT" "$CUR-live" > "$OUT/live-relayout-$CUR.log" 2>&1 \
  || { echo "LIVE RE-LAYOUT FAILED (see $OUT/live-relayout-$CUR.log); ENTER/ unchanged -- upload the Saturday bundle" >&2; exit 1; }
grep -q 'published bundle' "$OUT/live-relayout-$CUR.log" || { echo "live re-layout did not publish; ENTER/ unchanged" >&2; exit 1; }
printf 'LIVE-STATUS RE-LAYOUT: published %s-live at %s from DK snapshot %s; rollback = enter-bundles/%s\n' \
  "$CUR" "$(date -u +%H:%M:%SZ)" "$(basename "$SNAP")" "$CUR" >> "$OUT/TODAY-30-LATEST.md"
log "published: $E -> $(readlink -f "$E"). Next: scratch swaps (if any), then upload."
