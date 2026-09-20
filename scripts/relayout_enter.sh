#!/usr/bin/env bash
# relayout_enter.sh v2 (layout-aware row check) -- rebuild the per-contest ENTER/ bundle from a given all-lineups upload CSV (e.g. the PROMOTED one),
# with the after-build chain's OWN layout code (vendored verbatim below from scripts/sunday_after_build.sh; the chain's
# sha256 at vendoring time is recorded in CHAIN_SHA), the same staged verification (verify_enter_bundle.py) and the same
# atomic versioned-bundle publication (symlink swap).  The DK-entries watcher then refills DKEntries-FILLED-keepers-first.csv.
#   relayout_enter.sh UPLOAD_CSV OUT_DIR TAG [SHEET_MD]
# env: CONTESTS_JSON (default OUT_DIR/contests.json), ENTER_LAYOUT (default sequential, as week_env.sh sets it), PROD, PY
set -uo pipefail
CHAIN_SHA_AT_VENDORING=4d3babfdac600b8af980a2f7a454698864700de331ca2b2ed32841016e42d243
all=${1:?UPLOAD_CSV}; OUT=${2:?OUT_DIR}; tag=${3:?TAG}; SHEET_MD=${4:-}
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROD=${PROD:-$(cd -- "$HERE"/.. && pwd)}
PY=${PY:-${PROD_PY:-$PROD/.venv/bin/python}}
CONTESTS_JSON=${CONTESTS_JSON:-$OUT/contests.json}; export ENTER_LAYOUT=${ENTER_LAYOUT:-sequential}
log(){ printf '%s %s\n' "$(date -u +%H:%M:%SZ)" "$*"; }
[ -s "$all" ] || { log "no upload csv $all"; exit 2; }; [ -s "$CONTESTS_JSON" ] || { log "no contests $CONTESTS_JSON"; exit 2; }
entries=$($PY -c "import json,sys; print(sum(int(c['entries']) for c in json.load(open(sys.argv[1]))))" "$CONTESTS_JSON")
E="$OUT/ENTER"; STAGE="$OUT/.ENTER-staging-$tag"
rm -rf "$STAGE"; mkdir -p "$STAGE"
# ---- chain layout code, verbatim ----
  $PY - "$CONTESTS_JSON" "$all" "$STAGE" "$entries" <<'PYEOF' > "$STAGE/ENTER-layout.txt"
import csv, json, sys, pathlib
import os
contests, src, E, entries = json.load(open(sys.argv[1])), sys.argv[2], pathlib.Path(sys.argv[3]), int(sys.argv[4])
rows = list(csv.reader(open(src))); hdr, body = rows[0], rows[1:]
layout = os.environ.get("ENTER_LAYOUT", "top")   # top: every contest gets vetted ranks 1..n (contests pay independently,
                                                 # so each deserves the best lineups; Week-2 default).  sequential: the
                                                 # Week-1 layout (unique lineups across contests, keepers first).
if layout == "top":
    # A contest may set "block": true to take its own consecutive block of the book instead of ranks 1..n
    # (2026-09-18 operator decision, measured on the corrected Week-2 book's own worlds: for five satellite contests,
    # repeating the top block gives more EXPECTED seats but all-or-nothing; distinct blocks raise P(at least one seat)
    # from 35% to 58% at a 190-point cutoff, costing ~15% of expected seats. Fixed-value seats favour reliability.)
    cursor = 0
    for c in contests:
        n, k = int(c["entries"]), int(c["keep"]); lab = f"{c['name']}-{c['contest_id']}"
        if c.get("block"):
            lines = body[cursor:cursor + n]; lo, hi = cursor + 1, cursor + n; cursor += n; kind = "own block"
        else:
            lines = body[:n]; lo, hi = 1, n; kind = "top"
        if len(lines) != n:
            print(f"WARNING {lab}: only {len(lines)} of {n} lineups available from a K{entries} book (ranks {lo}-{hi})")
        out = E / f"ENTER-{lab}-{n}-entries-KEEP-first-{k}.csv"
        with open(out, "w", newline="") as f:
            w = csv.writer(f); w.writerow(hdr); w.writerows(lines)
        print(f"{lab}: {n} entries = vetted ranks {lo}-{hi} ({kind}; keep {k}) -> {out.name}")
    if cursor > entries:
        print(f"WARNING: blocked contests need ranks up to {cursor} but the book holds {entries}")
    print(f"top layout: {sum(int(c['entries']) for c in contests)} entries; blocked contests consumed ranks 1-{cursor}" if cursor else
          f"top layout: every contest receives the vetted book's first N; {sum(int(c['entries']) for c in contests)} entries in total")
else:
    keep_total = sum(int(c["keep"]) for c in contests); fill_next = keep_total + 1; keep_next = 1
    for c in contests:
        n, k = int(c["entries"]), int(c["keep"]); lab = f"{c['name']}-{c['contest_id']}"
        keepers = body[keep_next - 1: keep_next - 1 + k]; keep_next += k
        fills = body[fill_next - 1: fill_next - 1 + (n - k)]; fill_next += n - k
        if len(keepers) + len(fills) != n:
            print(f"WARNING {lab}: only {len(keepers) + len(fills)} of {n} lineups available from a K{entries} book")
        out = E / f"ENTER-{lab}-{n}-entries-KEEP-first-{k}.csv"
        with open(out, "w", newline="") as f:
            w = csv.writer(f); w.writerow(hdr); w.writerows(keepers + fills)
        print(f"{lab}: {n} entries, keep rows 1-{k} (vetted ranks {keep_next - k}-{keep_next - 1}), fill rows {k + 1}-{n} -> {out.name}")
    print(f"keepers total {keep_total}; fills drawn from vetted ranks {keep_total + 1}-{fill_next - 1}")
PYEOF
# ---- end of vendored block ----
cp "$all" "$STAGE/ENTER-all-rows-1-to-$(( $($PY -c "import json; print(sum(c['keep'] for c in json.load(open('$CONTESTS_JSON'))))") ))-are-the-KEEPERS.csv"
[ -n "$SHEET_MD" ] && [ -s "$SHEET_MD" ] && cp "$SHEET_MD" "$STAGE/ENTER-sheet-keepers.md"
want=$($PY -c "import json; print(len(json.load(open('$CONTESTS_JSON'))))")
got=$(ls "$STAGE"/ENTER-*-entries-KEEP-first-*.csv 2>/dev/null | wc -l)
if [ "$want" != "$got" ]; then log "staged bundle has $got per-contest files, expected $want -- NOT published, previous ENTER/ kept"; rm -rf "$STAGE"; exit 1; fi
if ! $PY "$PROD/scripts/verify_enter_bundle.py" "$CONTESTS_JSON" "$STAGE"; then log "staged bundle failed verification -- NOT published, previous ENTER/ kept"; rm -rf "$STAGE"; exit 1; fi
# rows of the staged per-contest files must equal the upload's rows mapped through the SAME layout rule the chain uses
# (sequential: each contest's keeper slice then its fill slice from the tail; top: ranks 1..n, or a cursor block for
# contests marked "block": true) -- a layout-aware check, not a contiguous slice (laptop review 2026-09-20).
if ! ENTER_LAYOUT="$ENTER_LAYOUT" $PY - "$all" "$STAGE" "$CONTESTS_JSON" <<'PYCHK'
import csv, json, os, sys, pathlib
rows = list(csv.reader(open(sys.argv[1])))[1:]; E = pathlib.Path(sys.argv[2]); contests = json.load(open(sys.argv[3]))
layout = os.environ.get("ENTER_LAYOUT", "top"); expected = {}
if layout == "top":
    cursor = 0
    for c in contests:
        n = int(c["entries"])
        if c.get("block"): expected[c["name"]] = rows[cursor:cursor + n]; cursor += n
        else: expected[c["name"]] = rows[:n]
else:
    keep_total = sum(int(c["keep"]) for c in contests); fill_next = keep_total + 1; keep_next = 1
    for c in contests:
        n, k = int(c["entries"]), int(c["keep"])
        keepers = rows[keep_next - 1: keep_next - 1 + k]; keep_next += k
        fills = rows[fill_next - 1: fill_next - 1 + (n - k)]; fill_next += n - k
        expected[c["name"]] = keepers + fills
ok = True
for c in contests:
    f = next(E.glob(f"ENTER-{c['name']}-{c['contest_id']}-*-entries-KEEP-first-*.csv")); body = list(csv.reader(open(f)))[1:]
    if body != expected[c["name"]]: ok = False; print(f"MISMATCH {c['name']}: staged rows != layout-mapped upload rows ({layout})")
print(f"staged bundle == upload rows under the {layout} layout mapping:", ok); sys.exit(0 if ok else 1)
PYCHK
then log "staged bundle does not reproduce the upload order under the $ENTER_LAYOUT layout -- NOT published"; rm -rf "$STAGE"; exit 1; fi
BUNDLES="$OUT/enter-bundles"; VER="$BUNDLES/$tag"
mkdir -p "$BUNDLES"; rm -rf "$VER"; mv "$STAGE" "$VER"
if [ -e "$E" ] && [ ! -L "$E" ]; then rm -rf "$BUNDLES/legacy-$tag"; mv "$E" "$BUNDLES/legacy-$tag"; fi
ln -sfn "$VER" "$E.new" && mv -T "$E.new" "$E"
log "published bundle $tag atomically: $E -> $(readlink -f "$E")"
