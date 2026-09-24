#!/usr/bin/env bash
# Autonomous pre-lock Sunday build for any regular-season week (generalised from the Week-1 host driver, which is
# kept as scripts/week1_sunday_build_host.sh).  Armed by one-shot user timers at 05:30 CT, 09:10 CT, and 10:50 CT
# (T-70, after the 10:30 CT inactives; see scripts/arm_week_timers.sh).  Builds the configured dose through
# scripts/sunday_runbook.sh, then the K90 nested book, ordering shadows, vetting, composite, hybrid15, and emits
# draftable-ID upload CSVs per contest from $CONTESTS_JSON.  It never publishes and never uploads.
#
#   source scripts/week_env.sh && week_env 2 [GROUP]; scripts/sunday_build_host.sh          # RUN_TAG defaults to now
#   RUN_TAG=20260920t1550z-$RUN_SUFFIX scripts/sunday_build_host.sh                         # T-70 rebuild
#
# Dose (2026-09-16, operator decision for Week 2): the K90 book's dose is PAID_LEV/PAID_BOOM, taken from the
# environment or from $DOSE_FILE (default $OUT/dose.env, sourced FIRST).  SKIP_PAIR=1 skips the
# governed D-pair of scripts/sunday_runbook.sh (a publisher artifact; the K90's ranks 1-80 are the paid K80) so a
# big-dose build costs one stream, not two.  EXTRA_LEV/EXTRA_BOOM add an optional extra shadow book.  Several
# builds may run concurrently on Saturday/Sunday morning (Saturday 10:30 CT 12,800 / 10:35 CT 6,400 / Sunday 05:30 CT
# 6,400 / 09:10 CT 3,200 / 10:50 CT 800):
# each build's run dir is identified by its own receipt (lev/boom and build window), never by LATEST.
set -uo pipefail
: "${WEEK:?source scripts/week_env.sh and call week_env WEEK first}"
# Week-3 per-game cap (week_env.sh MAX_PER_GAME, default 4; 0 = flag omitted). Applied to EVERY
# live_week.py build here and in sunday_runbook.sh, so the K90 book still nests the paid K80 book.
MPG_ARGS=(); if [[ "${MAX_PER_GAME:-0}" != "0" ]]; then MPG_ARGS=(--max-per-game "$MAX_PER_GAME"); fi
echo "per-game cap: ${MPG_ARGS[*]:-off}"
check_cap() {  # $1 run dir -- fail closed if the receipt does not record the cap this run asked for
  python3 - "$1" "${MAX_PER_GAME:-0}" <<'CAPEOF' || { echo "per-game cap NOT in effect in $1"; exit 1; }
import json, sys
r = json.load(open(sys.argv[1] + "/receipt.json")); want = int(sys.argv[2])
got = (r.get("config", {}).get("arm", {}) or {}).get("max_per_game")
ok = (got is None) if want == 0 else (got == want)
print(f"receipt max_per_game={got} expected={want or None}")
sys.exit(0 if ok else 1)
CAPEOF
}
: "${GROUP:?}" "${OUT:?}" "${CLONE:?}" "${PROD:?}" "${PROD_PY:?}" "${LAB_PY:?}" "${TOOLS:?}" "${CONTESTS_JSON:?}" "${WEEKDIR:?}" "${RUN_SUFFIX:?}"
mkdir -p "$OUT"
LOG="$OUT/build-$(date -u +%Y%m%dT%H%M%SZ).log"; exec > >(tee -a "$LOG") 2>&1
RUN_TAG=${RUN_TAG:-$(date -u +%Y%m%dt%H%Mz)-$RUN_SUFFIX}
DOSE_FILE=${DOSE_FILE:-$OUT/dose.env}   # optional: PAID_LEV=640 PAID_BOOM=2560 [EXTRA_LEV= EXTRA_BOOM=]
# shellcheck disable=SC1090
[[ -f "$DOSE_FILE" ]] && source "$DOSE_FILE"
export PAID_LEV=${PAID_LEV:-160} PAID_BOOM=${PAID_BOOM:-640}
# 2026-09-18: the book must hold one lineup per reserved entry when ENTER_LAYOUT=sequential (unique across contests).
# BOOK_ENTRIES defaults to 90 and is raised from contests.json when the week reserves more.
export BOOK_ENTRIES=${BOOK_ENTRIES:-$(PYTHONPATH="$PROD/src" "$PROD_PY" -c "import json,sys; from nfl_dfs.inference.enter_layout import rows_needed; print(max(90, rows_needed(json.load(open(sys.argv[1])), sys.argv[2])))" "$CONTESTS_JSON" "${ENTER_LAYOUT:-sequential}")}
LIVE="$CLONE/results/live/$WEEKDIR"; mkdir -p "$LIVE"
echo "== $(date -u) week $WEEK group $GROUP run tag $RUN_TAG dose lev $PAID_LEV / boom $PAID_BOOM (D$((PAID_LEV + PAID_BOOM))) skip_pair ${SKIP_PAIR:-0}"
# the run dir this build creates: newest receipt with our lev/boom whose built_utc falls inside our window (concurrent
# builds at other doses may write LATEST meanwhile)
find_run_dir() {  # $1 lev, $2 boom, $3 start epoch -> the run dir THIS invocation produced, or empty
  # 2026-09-17 review finding 3: bind the result to this invocation, not merely to a dose plus an mtime window.
  # Every clause below must hold: the receipt's dose, its build time inside [start-60, now], the week's draft group,
  # the expected clone SHA, and a complete K90 (90 written, nested prefix true).
  "$PROD_PY" - "$LIVE" "$1" "$2" "$3" "$GROUP" "$WEEK" "$SEASON" "$BOOK_ENTRIES" <<'PYEOF'
import json, sys, pathlib
from datetime import datetime, timezone
live, lev, boom, start, group, week, season = (pathlib.Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]),
                                               float(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), int(sys.argv[7]))
best, why = None, []
for d in sorted(live.iterdir()):
    r = d / "receipt.json"
    if not r.is_file():
        continue
    try:
        j = json.load(open(r))
    except Exception:
        continue
    c = j.get("config", {})
    if (c.get("lev"), c.get("boom")) != (lev, boom):
        continue
    try:
        built = datetime.fromisoformat(str(j.get("built_utc"))).timestamp()
    except Exception:
        why.append(f"{d.name}: unreadable built_utc"); continue
    if built < start - 60:
        continue
    if int(j.get("draft_group", -1)) != group or int(j.get("week", -1)) != week or int(j.get("season", -1)) != season:
        why.append(f"{d.name}: group/week/season {j.get('draft_group')}/{j.get('week')}/{j.get('season')} != {group}/{week}/{season}"); continue
    if int(j.get("written", 0)) < int(sys.argv[8]):
        why.append(f"{d.name}: written {j.get('written')} < {sys.argv[8]}"); continue
    if j.get("book_k80_is_nested_prefix") is not True:
        why.append(f"{d.name}: K80 is not a nested prefix of the K90 book"); continue
    best = d
if best is None and why:
    print("REJECTED: " + "; ".join(why[-3:]), file=sys.stderr)
print(best or "")
PYEOF
}
[[ -f "$CONTESTS_JSON" ]] || { echo "contests file missing: $CONTESTS_JSON (copy scripts/contests.template.json and fill the week's contest ids)"; exit 2; }
"$PROD_PY" - "$CONTESTS_JSON" <<'PYEOF' || exit 2
import json, os, sys
c = json.load(open(sys.argv[1]))
assert isinstance(c, list) and c, "contests.json must be a non-empty list"
for x in c:
    assert set(x) >= {"name", "contest_id", "entries", "keep"} and str(x["contest_id"]).isdigit() and x["entries"] >= x["keep"] >= 0, x
    assert "REPLACE" not in json.dumps(x), f"contests.json still holds a template entry: {x}"
tot = sum(x["entries"] for x in c); keep = sum(x["keep"] for x in c); widest = max(x["entries"] for x in c)
layout = os.environ.get("ENTER_LAYOUT") or "sequential"
print(f"contests: {[(x['name'], x['contest_id'], x['entries'], x['keep']) for x in c]} total entries {tot} keepers {keep} widest contest {widest} layout {layout}")
# 2026-09-18: under the default `top` layout every contest independently receives the vetted book's first N, so the
# book only has to be as large as the WIDEST contest; the sum may exceed the book size (Week 2: 97 entries across 12
# contests, widest 23).  Under `sequential` (the Week-1 unique-across-contests layout) the SUM is the binding limit.
book = int(os.environ.get("BOOK_ENTRIES", "90"))
sys.path.insert(0, os.path.join(os.environ["PROD"], "src"))
from nfl_dfs.inference.enter_layout import rows_needed   # the one layout rule (2026-09-24)
need = rows_needed(c, layout)
assert need <= book, f"the {layout} layout reads {need} distinct lineups but the book holds {book}"
PYEOF

# 1. the governed pair (paid K80 / shadow) with receipt checks -- skipped with SKIP_PAIR=1 (the K90 below carries the
#    paid K80 as ranks 1-80).  REUSE_PAID_DIR/REUSE_SHADOW_DIR (and REUSE_K90_DIR below) let a rehearsal exercise
#    everything downstream of the builds on existing run dirs.
if [[ "${SKIP_PAIR:-0}" == "1" ]]; then
  echo "pair skipped (SKIP_PAIR=1); k80 emits come from the K90 run dir"; PAID_DIR=""; SHADOW_DIR=""
else
  "$PROD/scripts/sunday_runbook.sh" --run-id "$RUN_TAG" ${REUSE_PAID_DIR:+--paid-dir "$REUSE_PAID_DIR"} ${REUSE_SHADOW_DIR:+--shadow-dir "$REUSE_SHADOW_DIR"} | tee "$OUT/runbook-$RUN_TAG.txt"
  PAID_DIR=$(grep -o '^paid=.*' "$OUT/runbook-$RUN_TAG.txt" | cut -d= -f2-)
  SHADOW_DIR=$(grep -o '^shadow=.*' "$OUT/runbook-$RUN_TAG.txt" | cut -d= -f2-)
  [[ -d "$PAID_DIR" && -d "$SHADOW_DIR" ]] || { echo "runbook did not produce the pair"; exit 1; }
  echo "paid=$PAID_DIR shadow=$SHADOW_DIR"
fi

# 2. K90 nested build (ranks 1-80 equal the paid K80 book)
if [[ -n "${REUSE_K90_DIR:-}" ]]; then
  K90_DIR=$REUSE_K90_DIR; echo "reusing K90 run dir (rehearsal)"
else
  T0=$(date +%s)
  # 2026-09-17 review finding 3: the builder's exit status is required, not just the presence of a matching directory.
  if ( cd "$CLONE" && NFL2_LIVE_CENTER=production PYTHONPATH="$CLONE/src" OMP_NUM_THREADS=1 "$LAB_PY" scripts/live_week.py \
      --season "$SEASON" --week "$WEEK" --group "$GROUP" --selector dual_emax --lev "$PAID_LEV" --boom "$PAID_BOOM" --sims 10000 --k 1 \
      --seed 2026 --entries "$BOOK_ENTRIES" --emit-a5-sidecars "${MPG_ARGS[@]}" > /dev/null 2> "$OUT/k90-$RUN_TAG.err" ); then
    K90_DIR=$(find_run_dir "$PAID_LEV" "$PAID_BOOM" "$T0")
    [[ -n "$K90_DIR" ]] && check_cap "$K90_DIR"
  else
    echo "K90 builder exited non-zero (see $OUT/k90-$RUN_TAG.err); refusing to adopt any run dir"; exit 1
  fi
  echo "k90 build took $(( $(date +%s) - T0 )) s"
fi
[[ -n "$K90_DIR" && -f "$K90_DIR/receipt.json" ]] || { echo "K90 build failed (see $OUT/k90-$RUN_TAG.err)"; exit 1; }
# 2026-09-18 (review follow-up): use the SAME governed verifier as scripts/sunday_runbook.sh rather than a weaker
# local copy — it requires identity present, sha equal and NOT dirty, exact written/operational_k, the week's lock,
# the draft group, a legal unique 90-row book.csv and every sidecar file. Applied to reused directories too.
verify_k90() {  # $1 run dir
  "$LAB_PY" - "$1" "$PAID_LEV" "$PAID_BOOM" "$BOOK_ENTRIES" 1 "$EXPECT_SHA" "$LOCK_UTC" "$GROUP" <<'PYEOF'
import csv, json, sys
from pathlib import Path
d, lev, boom, entries, sidecars, sha, lock, group = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5] == "1", sys.argv[6], sys.argv[7], sys.argv[8]
r = json.loads((d / "receipt.json").read_text())
problems = []
ident = r.get("identity") or {}
if not ident.get("sha"): problems.append("receipt carries no identity sha")
elif ident["sha"] != sha or ident.get("dirty"): problems.append(f"identity {ident}")
if (r["config"]["lev"], r["config"]["boom"]) != (lev, boom): problems.append(f"config {r['config']['lev']}/{r['config']['boom']} != {lev}/{boom}")
if r["written"] != entries or r["config"].get("operational_k") != entries: problems.append(f"written {r['written']} / operational_k {r['config'].get('operational_k')} != {entries}")
if str(r["lock_utc"]) != lock: problems.append(f"lock_utc {r['lock_utc']} != {lock}")
if str(r["draft_group"]) != str(group): problems.append(f"draft_group {r['draft_group']} != {group}")
if r.get("book_k80_is_nested_prefix") is not True: problems.append("K80 is not a nested prefix of the K90 book")
rows = list(csv.reader((d / "book.csv").open()))
if rows[0] != ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]: problems.append("book.csv header")
if len(rows) - 1 != entries or len({tuple(sorted(x)) for x in rows[1:]}) != entries: problems.append("book.csv rows/uniqueness")
need = ["book.csv", "book.json", "candidates.parquet", "frame.parquet", "exposure_ledger.json", "receipt.json"]
if sidecars: need += ["book_wemax.csv", "book_wemax.json", "incumbent_player_scores.npy", "corrected_hsim_player_scores.npy"]
missing = [n for n in need if not (d / n).is_file()]
if missing: problems.append(f"missing {missing}")
if problems:
    print("K90 RECEIPT CHECK FAILED: " + "; ".join(problems)); sys.exit(1)
print(f"k90 receipt verified (governed): {d.name} lev/boom {lev}/{boom} entries {entries} group {group} lock {lock}")
PYEOF
}
verify_k90 "$K90_DIR" || { echo "K90 receipt verification FAILED for $K90_DIR"; exit 1; }
[[ -n "$PAID_DIR" ]] || PAID_DIR=$K90_DIR
echo "k90=$K90_DIR"
# The approved Saturday D12800 build may opt into the selection-only Week-3 shadow.  Keep this explicit so fallback and
# T-70 builds cannot silently replace the live shadow; the wrapper pins CLONE/EXPECT_SHA and refuses an existing output.
if [[ "${RUN_WEEK3_SHADOW:-0}" == "1" ]]; then
  SHADOW_OUT=${SHADOW_OUT:-$OUT/shadow-$RUN_TAG}
  "$PROD/scripts/run_week3_shadow.sh" "$K90_DIR" "$SHADOW_OUT" "${SHADOW_LABEL:-live}" \
    || { echo "WEEK3 SHADOW FAILED (see $SHADOW_OUT)"; exit 1; }
fi
# 2b. within-book ordering shadows (outcome-blind; graded after settlement)
( cd "$CLONE" && NFL2_ROOT="$CLONE" PYTHONPATH="$CLONE/src" "$LAB_PY" \
    "$TOOLS/ordering_shadows.py" "$K90_DIR" --k 30 --output "$OUT/ordering_shadows-$RUN_TAG-k30.json" \
    > "$OUT/ordering_shadows-$RUN_TAG-k30.txt" 2>&1 ) && echo "ordering shadows -> $OUT/ordering_shadows-$RUN_TAG-k30.json" || echo "ORDERING SHADOWS FAILED (see $OUT/ordering_shadows-$RUN_TAG-k30.txt)"

# 3. optional extra shadow book at another dose (EXTRA_LEV/EXTRA_BOOM from the environment or $DOSE_FILE)
if [[ -n "${EXTRA_LEV:-}" && -n "${EXTRA_BOOM:-}" ]]; then
  T1=$(date +%s)
  ( cd "$CLONE" && NFL2_LIVE_CENTER=production PYTHONPATH="$CLONE/src" OMP_NUM_THREADS=1 "$LAB_PY" scripts/live_week.py \
      --season "$SEASON" --week "$WEEK" --group "$GROUP" --selector dual_emax --lev "$EXTRA_LEV" --boom "$EXTRA_BOOM" \
      --sims 10000 --k 1 --seed 2026 --entries 90 --emit-a5-sidecars "${MPG_ARGS[@]}" > /dev/null 2> "$OUT/dose-$RUN_TAG.err" )
  DOSE_DIR=$(find_run_dir "$EXTRA_LEV" "$EXTRA_BOOM" "$T1"); [[ -n "$DOSE_DIR" ]] && check_cap "$DOSE_DIR"; echo "extra shadow (D$((EXTRA_LEV + EXTRA_BOOM)))=$DOSE_DIR"
fi

# 4. per-contest upload CSVs (draftable ids) from run dirs
emit() {  # $1 run dir, $2 label, $3 ranks
  ( cd "$PROD" && PYTHONPATH="$PROD/src" "$PROD_PY" scripts/emit_dk_upload_csv_v1.py --source run-dir \
      --run-dir "$1" --ranks "$3" --output "$OUT/upload-$RUN_TAG-$2-ranks-$3.csv" > "$OUT/upload-$RUN_TAG-$2-ranks-$3.receipt.json" 2>&1 ) \
    && echo "emitted $2 $3" || echo "EMIT FAILED $2 $3"
}
# layouts: k80 = the paid book's first N per contest (same lineups in every contest); k90 = one unique lineup per
# reserved entry (sequential ranks); k30 = the keepers only (sequential ranks over the keep counts)
# k80 = the per-contest layout the money path uses (every contest gets ranks 1..N; ENTER_LAYOUT=top).
# k90/k30 = the Week-1 sequential layout, kept only as reference emits; 2026-09-18: they are SKIPPED for contests whose
# cumulative range would run past the 90-lineup book (Week 2 reserves 97 entries across 12 contests), so that an
# "EMIT FAILED" line on Sunday always means a real failure.
layouts=$("$PROD_PY" - "$CONTESTS_JSON" <<'PYEOF'
import json, sys
import os
c = json.load(open(sys.argv[1])); p = 1; q = 1; BOOK = int(os.environ.get("BOOK_ENTRIES", "90"))
for x in c:
    n, k = int(x["entries"]), int(x["keep"]); lab = f"{x['name']}-{x['contest_id']}"
    print(f"k80 {lab} 1-{n}")
    if p + n - 1 <= BOOK:
        print(f"k90 {lab} {p}-{p+n-1}")
    else:
        print(f"skip k90 {lab} (sequential ranks {p}-{p+n-1} exceed the {BOOK}-lineup book)", file=sys.stderr)
    p += n
    if k and q + k - 1 <= BOOK:
        print(f"k30 {lab} {q}-{q+k-1}")
    elif k:
        print(f"skip k30 {lab} (sequential ranks {q}-{q+k-1} exceed the {BOOK}-lineup book)", file=sys.stderr)
    q += k
PYEOF
)
while read -r layout lab ranks; do
  case "$layout" in
    k80) emit "$PAID_DIR" "k80-$lab" "$ranks" ;;
    k90) emit "$K90_DIR" "k90-$lab" "$ranks" ;;
    k30) emit "$K90_DIR" "k30-$lab" "$ranks" ;;
  esac
done <<< "$layouts"

# 5. vetting (HARD to the back, material demoted), composite resort, hybrid15 — all reported, none entered automatically
VET_DIR="$OUT/vetted-$RUN_TAG"
( cd "$PROD" && PYTHONPATH="$PROD/src" "$PROD_PY" "$TOOLS/vet_book.py" "$K90_DIR" --k 30 --season "$SEASON" --week "$WEEK" --output-dir "$VET_DIR" > "$OUT/vetting-$RUN_TAG.txt" 2>&1 ) \
  && { echo "vetted book -> $VET_DIR (report $VET_DIR/vetting_report.md)"; grep -m1 "demoted_out_of_top_k" "$OUT/vetting-$RUN_TAG.txt"
       while read -r layout lab ranks; do [[ "$layout" == k30 ]] && emit "$VET_DIR" "vetted-$lab" "$ranks"; done <<< "$layouts"
       emit "$VET_DIR" vetted-all30 1-30; emit "$VET_DIR" vetted-all90 1-90; } \
  || echo "VETTING FAILED (see $OUT/vetting-$RUN_TAG.txt)"
COMP_DIR="$OUT/composite-$RUN_TAG"
( cd "$PROD" && PYTHONPATH="$PROD/src" "$PROD_PY" "$TOOLS/player_score.py" "$K90_DIR" --k 30 --season "$SEASON" --week "$WEEK" --vetting "$VET_DIR/vetting.json" --output-dir "$COMP_DIR" > "$OUT/composite-$RUN_TAG.txt" 2>&1 ) \
  && { echo "composite book -> $COMP_DIR"; emit "$COMP_DIR" composite-all30 1-30; } || echo "COMPOSITE FAILED (see $OUT/composite-$RUN_TAG.txt)"
HYB_DIR="$OUT/hybrid15-$RUN_TAG"
( cd "$CLONE" && "$LAB_PY" "$TOOLS/hybrid30.py" "$K90_DIR" --core 15 --k 30 --output-dir "$HYB_DIR" > "$OUT/hybrid15-$RUN_TAG.txt" 2>&1 ) \
  && { echo "hybrid15 -> $HYB_DIR"; emit "$HYB_DIR" hybrid15-all30 1-30; } || echo "HYBRID15 FAILED (see $OUT/hybrid15-$RUN_TAG.txt)"
# 6. exposure caps (reported, never entered automatically).  2026-09-22: Week 2 entered a
# player listed Doubtful at build time in 48 of 97 rows including the Millionaire seat; he
# scored 0.0.  A tool that could have bounded that existed but was not in the chain, so it
# runs here.  It re-selects from the SAME pool with the SAME objective at the SAME K, so its
# book is comparable to the delivered one row for row, and it fails closed rather than emit a
# book that breaches a cap.  The operator reads $CAP_DIR/exposure_sheet.md before upload.
CAP_DIR="$OUT/exposure-caps-$RUN_TAG"
( cd "$PROD" && PYTHONPATH="$PROD/src" "$PROD_PY" "$TOOLS/exposure_cap_book.py" "$K90_DIR" \
    --contests "$CONTESTS_JSON" --entries "$BOOK_ENTRIES" --layout "${ENTER_LAYOUT:-sequential}" \
    --output-dir "$CAP_DIR" > "$OUT/exposure-caps-$RUN_TAG.txt" 2>&1 ) \
  && { echo "exposure caps -> $CAP_DIR (sheet $CAP_DIR/exposure_sheet.md)"
       grep -m1 "E\[max\]" "$OUT/exposure-caps-$RUN_TAG.txt" || true; } \
  || echo "EXPOSURE CAPS FAILED (see $OUT/exposure-caps-$RUN_TAG.txt) -- check the injury sheet by hand before upload"
# 6b. Refinement 2 PAPER arm (operator 2026-09-24): the same capped re-selection with tighter caps for Questionable
#     QBs and Questionable players whose latest practice was DNP (both play ~50% vs 72% for Questionable overall).
#     Written beside the report above, never entered; scored Monday against the entered book.
CAP2_DIR="$OUT/exposure-caps-r2-$RUN_TAG"
( cd "$PROD" && PYTHONPATH="$PROD/src" "$PROD_PY" "$TOOLS/exposure_cap_book.py" "$K90_DIR" \
    --contests "$CONTESTS_JSON" --entries "$BOOK_ENTRIES" --layout "${ENTER_LAYOUT:-sequential}" \
    --questionable-qb-max-share "${R2_QB_SHARE:-0.05}" --questionable-dnp-max-share "${R2_DNP_SHARE:-0.05}" \
    --output-dir "$CAP2_DIR" > "$OUT/exposure-caps-r2-$RUN_TAG.txt" 2>&1 ) \
  && echo "refinement-2 paper book -> $CAP2_DIR/capped_book.csv" \
  || echo "REFINEMENT-2 PAPER BOOK FAILED (see $OUT/exposure-caps-r2-$RUN_TAG.txt) -- paper only, the entry is unaffected"
# ... laid out exactly like the entered book (laptop ask 2026-09-24) for Monday's per-contest-type scoring. Paper only.
if [[ -f "$CAP2_DIR/capped_book.csv" && -f "${OWNERSHIP_SETS:-}" ]]; then
  ( cd "$PROD" && PYTHONPATH="$PROD/src" "$PROD_PY" "$TOOLS/paper_layout_capped_book.py" --capped-book "$CAP2_DIR/capped_book.csv" \
      --run-dir "$K90_DIR" --contests "$CONTESTS_JSON" --sets "$OWNERSHIP_SETS" --layout "${ENTER_LAYOUT:-sequential}" \
      --order "${ENTER_ORDER:-greedy}" --out "$OUT/paper-r2-$RUN_TAG" > "$OUT/paper-r2-$RUN_TAG.txt" 2>&1 ) \
    && echo "refinement-2 paper bundle -> $OUT/paper-r2-$RUN_TAG/bundle" \
    || echo "REFINEMENT-2 PAPER BUNDLE FAILED (see $OUT/paper-r2-$RUN_TAG.txt) -- paper only"
fi
echo "== done $(date -u). The after-build chain (scripts/sunday_after_build.sh) writes ENTER/ and TODAY-30-LATEST.md from the vetted book; the operator uploads in the DK UI by 11:15 CT."
