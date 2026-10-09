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
# O-19 (2026-10-02): this driver takes NO arguments. It used to accept and ignore them, so `sunday_build_host.sh --check`
# started a real build in the live OUT and clone. Refuse any argument before the first side effect (mkdir, log, build);
# the check entrypoint is run_week_build.sh --check (the timers call run_week_build.sh, which passes none here).
(( $# == 0 )) || { echo "sunday_build_host.sh takes no arguments (use run_week_build.sh --check)"; exit 2; }
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
export BOOK_ENTRIES=${BOOK_ENTRIES:-$(PYTHONPATH="$PROD/src" "$PROD_PY" -c "import json,sys; from nfl_dfs.inference.enter_layout import rows_needed, sleeve_size; c=json.load(open(sys.argv[1])); print(max(1, rows_needed(c, sys.argv[2]) - sleeve_size(c, sys.argv[2])))" "$CONTESTS_JSON" "${ENTER_LAYOUT:-sequential}")}
export TAIL_SLEEVE=${TAIL_SLEEVE:-$(PYTHONPATH="$PROD/src" "$PROD_PY" -c "import json,sys; from nfl_dfs.inference.enter_layout import sleeve_size; print(sleeve_size(json.load(open(sys.argv[1])), sys.argv[2]))" "$CONTESTS_JSON" "${ENTER_LAYOUT:-sequential}")}
export LIVE_SELECTOR=${LIVE_SELECTOR:-dual_emax} TAIL_LINE=${TAIL_LINE:-210}
# Two tracks (operator 2026-09-27): --entries = mean rows, --tail-sleeve = Millionaire rows after them (0 = flag omitted).
SLEEVE_ARGS=()
if [[ "${TAIL_SLEEVE}" != "0" ]]; then
  SLEEVE_ARGS=(--tail-sleeve "$TAIL_SLEEVE" --tail-line "$TAIL_LINE" --tail-sleeve-selector "${TAIL_SLEEVE_SELECTOR:-emax}")
  if [[ "${TAIL_SLEEVE_SELECTOR:-emax}" == "class" ]]; then
    [[ -f "${CLASS_MODEL:-}" && -f "${CLASS_MODEL}.sha256" ]] || { echo "TAIL_SLEEVE_SELECTOR=class needs CLASS_MODEL (json + .sha256); got '${CLASS_MODEL:-}'"; exit 1; }
    SLEEVE_ARGS+=(--class-model "$CLASS_MODEL")
  fi
fi
# Class sleeve (reviewer item 2): every Nth boom visit under the 193+ shape; 0 = flag omitted; needs the class model.
CLASS_SLEEVE_ARGS=()
if [[ "${CLASS_SLEEVE_EVERY:-0}" != "0" ]]; then
  [[ -f "${CLASS_MODEL:-}" && -f "${CLASS_MODEL}.sha256" ]] || { echo "CLASS_SLEEVE_EVERY=$CLASS_SLEEVE_EVERY needs CLASS_MODEL (json + .sha256); got '${CLASS_MODEL:-}'"; exit 1; }
  CLASS_SLEEVE_ARGS=(--class-sleeve-every "$CLASS_SLEEVE_EVERY")
  [[ "$LIVE_SELECTOR" == "class" || "${TAIL_SLEEVE_SELECTOR:-emax}" == "class" ]] || CLASS_SLEEVE_ARGS+=(--class-model "$CLASS_MODEL")
fi
# Q4b: drop players projected below LIVE_MIN_PROJ before generation (empty = flag omitted; the audit then fails on non-players).
MINPROJ_ARGS=(); if [[ -n "${LIVE_MIN_PROJ:-}" ]]; then MINPROJ_ARGS=(--min-proj "$LIVE_MIN_PROJ"); fi
# Mean-track levers (operator 2026-09-28): ownership tilt with its source file, and the per-DST cap. Only with the mean selector.
MEAN_ARGS=()
if [[ "$LIVE_SELECTOR" == "class" ]]; then
  [[ -f "${CLASS_MODEL:-}" && -f "${CLASS_MODEL}.sha256" ]] || { echo "LIVE_SELECTOR=class needs CLASS_MODEL (json + .sha256); got '${CLASS_MODEL:-}'"; exit 1; }
  MEAN_ARGS+=(--class-model "$CLASS_MODEL")
fi
if [[ "$LIVE_SELECTOR" == "mean" || "$LIVE_SELECTOR" == "class" ]]; then
  if [[ -n "${MEAN_OWN_TILT:-}" && "${MEAN_OWN_TILT}" != "0" ]]; then
    [[ -f "${MEAN_OWN_SOURCE:-}" ]] || { echo "MEAN_OWN_TILT=$MEAN_OWN_TILT needs MEAN_OWN_SOURCE (the Saturday ownership sets file); got '${MEAN_OWN_SOURCE:-}'"; exit 1; }
    MEAN_ARGS+=(--mean-own-tilt "$MEAN_OWN_TILT" --mean-own-source "$MEAN_OWN_SOURCE")
  fi
  [[ -n "${MEAN_DST_CAP:-}" ]] && MEAN_ARGS+=(--mean-dst-cap "$MEAN_DST_CAP")
fi
echo "selector: $LIVE_SELECTOR; mean rows: $BOOK_ENTRIES; tail sleeve: $TAIL_SLEEVE; min proj: ${LIVE_MIN_PROJ:-off}; own tilt: ${MEAN_OWN_TILT:-off}; dst cap: ${MEAN_DST_CAP:-off}"
# Every flag this chain sends must be one the pinned lab clone accepts; a build that dies at argument parsing on
# Saturday morning is the failure the operator refuses to hear about afterwards (2026-09-27).
need_flags=(); [[ -n "${LIVE_MIN_PROJ:-}" ]] && need_flags+=(--min-proj); [[ "$TAIL_SLEEVE" != "0" ]] && need_flags+=(--tail-sleeve --tail-line); [[ "$LIVE_SELECTOR" == "mean" ]] && need_flags+=('"mean"'); [[ "$LIVE_SELECTOR" == "class" ]] && need_flags+=('"class"' --class-model)
[[ "$LIVE_SELECTOR" == "mean" && -n "${MEAN_OWN_TILT:-}" ]] && need_flags+=(--mean-own-tilt --mean-own-source)
[[ "$LIVE_SELECTOR" == "mean" && -n "${MEAN_DST_CAP:-}" ]] && need_flags+=(--mean-dst-cap)
[[ "$TAIL_SLEEVE" != "0" ]] && need_flags+=(--tail-sleeve-selector)
[[ "${CLASS_SLEEVE_EVERY:-0}" != "0" ]] && need_flags+=(--class-sleeve-every --class-model)
if [[ -n "${UNION_SATURDAY_RUN:-}" ]]; then
  grep -q 'dst_of' "$CLONE/src/nfl2/two_track.py" || { echo "the pinned lab clone $CLONE has no DST-capped select_top_mean (needed by union_reselect.py)"; exit 1; }
  [[ -f "$PROD/scripts/union_reselect.py" ]] || { echo "union_reselect.py missing in $PROD/scripts"; exit 1; }
fi
[[ "$TAIL_SLEEVE" != "0" && "${TAIL_SLEEVE_SELECTOR:-emax}" == "class" ]] && need_flags+=(--class-model)
if [[ "$TAIL_SLEEVE" != "0" && "${TAIL_SLEEVE_SELECTOR:-emax}" == "mean" ]]; then
  grep -A1 -- '"--tail-sleeve-selector"' "$CLONE/scripts/live_week.py" | grep -q '"mean"' || { echo "the pinned lab clone $CLONE has no --tail-sleeve-selector mean (lab 54dd512+); move the pin or declare no tail contests"; exit 1; }
fi
for f in "${need_flags[@]}"; do
  grep -q -- "$f" "$CLONE/scripts/live_week.py" || { echo "the pinned lab clone $CLONE does not accept $f (LIVE_SELECTOR=$LIVE_SELECTOR TAIL_SLEEVE=$TAIL_SLEEVE LIVE_MIN_PROJ=${LIVE_MIN_PROJ:-}); move the pin or unset the lever"; exit 1; }
done
LIVE="$CLONE/results/live/$WEEKDIR"; mkdir -p "$LIVE"
echo "== $(date -u) week $WEEK group $GROUP run tag $RUN_TAG dose lev $PAID_LEV / boom $PAID_BOOM (D$((PAID_LEV + PAID_BOOM))) skip_pair ${SKIP_PAIR:-0}"
# The local Milly graph never runs through a build window (reviewer 10-04, binding; the arm refuses while it runs, but it
# could be started after arming). Its heap + page cache (up to 18 GB) could starve the builds, so the build STOPS it
# (it is on-demand only) rather than refusing: a refusal here would cost the money path. Two signals, as at arming:
# the pid file (ps -p) and any listener on 7474/7687 (ss). A failed stop is a loud WARN, never a refusal.
NEO_PID=$HOME/.local/share/neo4j-milly/run/neo4j.pid
if { [[ -s $NEO_PID ]] && ps -p "$(cat "$NEO_PID")" >/dev/null 2>&1; } || [[ -n "$(ss -ltnH '( sport = :7474 or sport = :7687 )' 2>/dev/null)" ]]; then
  echo "NEO4J RUNNING during a build window: stopping it (neo4j-milly stop)"
  [[ -x $HOME/.local/bin/neo4j-milly ]] && timeout 120 "$HOME/.local/bin/neo4j-milly" stop || true
  if { [[ -s $NEO_PID ]] && ps -p "$(cat "$NEO_PID")" >/dev/null 2>&1; } || [[ -n "$(ss -ltnH '( sport = :7474 or sport = :7687 )' 2>/dev/null)" ]]; then
    echo "WARN: NEO4J STILL RUNNING (or another listener on 7474/7687); the build continues -- stop it by hand"
  else
    echo "neo4j stopped"
  fi
fi
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
# two tracks (2026-09-27): the book holds BOOK_ENTRIES mean rows PLUS TAIL_SLEEVE sleeve rows, and rows_needed counts both
# (the Week-4 smoke, 2026-10-01: comparing against the mean rows alone refused every two-track build before it started)
book = int(os.environ.get("BOOK_ENTRIES", "90")) + int(os.environ.get("TAIL_SLEEVE", "0") or 0)
sys.path.insert(0, os.path.join(os.environ["PROD"], "src"))
from nfl_dfs.inference.enter_layout import rows_needed   # the one layout rule (2026-09-24)
need = rows_needed(c, layout)
assert need <= book, f"the {layout} layout reads {need} distinct lineups but the book holds {book} (mean {os.environ.get('BOOK_ENTRIES')} + sleeve {os.environ.get('TAIL_SLEEVE', '0')})"
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
      --season "$SEASON" --week "$WEEK" --group "$GROUP" --selector "$LIVE_SELECTOR" --lev "$PAID_LEV" --boom "$PAID_BOOM" --sims 10000 --k 1 \
      --seed 2026 --entries "$BOOK_ENTRIES" --emit-a5-sidecars "${MPG_ARGS[@]}" "${SLEEVE_ARGS[@]}" "${CLASS_SLEEVE_ARGS[@]}" "${MINPROJ_ARGS[@]}" "${MEAN_ARGS[@]}" > /dev/null 2> "$OUT/k90-$RUN_TAG.err" ); then
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
  "$LAB_PY" - "$1" "$PAID_LEV" "$PAID_BOOM" "$BOOK_ENTRIES" 1 "$EXPECT_SHA" "$LOCK_UTC" "$GROUP" "$TAIL_SLEEVE" "$LIVE_SELECTOR" <<'PYEOF'
import csv, json, sys
from pathlib import Path
d, lev, boom, entries, sidecars, sha, lock, group = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5] == "1", sys.argv[6], sys.argv[7], sys.argv[8]
sleeve, selector = int(sys.argv[9]), sys.argv[10]
r = json.loads((d / "receipt.json").read_text())
problems = []
# Two tracks: the receipt's operational_k is the mean rows and written = mean + sleeve rows; both must match the layout.
if r["config"].get("selector") != selector: problems.append(f"selector {r['config'].get('selector')!r} != configured {selector!r}")
_ts = (r["config"].get("tail_sleeve") or {}); got_sleeve = int(_ts.get("rows", 0)) if isinstance(_ts, dict) else int(_ts or 0)
if got_sleeve != sleeve: problems.append(f"tail sleeve {got_sleeve} != configured {sleeve}")
sleeve_used = (_ts.get("selector_used") if isinstance(_ts, dict) else None) or "none"
_field = (_ts.get("field") or {}) if isinstance(_ts, dict) else {}
_field_ok = sleeve_used.split("+")[0] in ("field_top", "field_band", "field_free") and sleeve_used.split("+")[1:] in ([], ["mean"]) \
    and _field.get("used") is True   # the field sleeve (operator 10-02); "+mean" = the split (field rows first, then the projection sleeve)
if sleeve and sleeve_used not in ("class", "emax", "mean") and not _field_ok:
    problems.append(f"tail sleeve selector_used {sleeve_used!r} is none of class/emax/mean/field_* (field used: {_field.get('used')})")
if sleeve and _field.get("requested") and not _field.get("used"):
    print(f"NOTE: the FIELD SLEEVE was requested and FELL BACK to the projection sleeve: {_field.get('failed')}")
if sleeve and sleeve_used == "emax" and isinstance(_ts, dict) and isinstance(_ts.get("class"), dict) and _ts["class"].get("failure"):
    print(f"NOTE: the class selector FAILED and the sleeve fell back to EMAX: {_ts['class'].get('failure')}")
total_rows = entries + sleeve
ident = r.get("identity") or {}
if not ident.get("sha"): problems.append("receipt carries no identity sha")
elif ident["sha"] != sha or ident.get("dirty"): problems.append(f"identity {ident}")
if (r["config"]["lev"], r["config"]["boom"]) != (lev, boom): problems.append(f"config {r['config']['lev']}/{r['config']['boom']} != {lev}/{boom}")
if r["written"] != total_rows or r["config"].get("operational_k") != entries: problems.append(f"written {r['written']} / operational_k {r['config'].get('operational_k')} != {total_rows} / {entries}")
if str(r["lock_utc"]) != lock: problems.append(f"lock_utc {r['lock_utc']} != {lock}")
if str(r["draft_group"]) != str(group): problems.append(f"draft_group {r['draft_group']} != {group}")
if r.get("book_k80_is_nested_prefix") is not True: problems.append("K80 is not a nested prefix of the K90 book")
rows = list(csv.reader((d / "book.csv").open()))
if rows[0] != ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]: problems.append("book.csv header")
if len(rows) - 1 != total_rows or len({tuple(sorted(x)) for x in rows[1:entries + 1]}) != entries: problems.append("book.csv rows/uniqueness (mean rows must be unique; the sleeve may repeat)")
need = ["book.csv", "book.json", "candidates.parquet", "frame.parquet", "exposure_ledger.json", "receipt.json"]
if sidecars: need += ["book_wemax.csv", "book_wemax.json", "incumbent_player_scores.npy", "corrected_hsim_player_scores.npy"]
missing = [n for n in need if not (d / n).is_file()]
if missing: problems.append(f"missing {missing}")
if problems:
    print("K90 RECEIPT CHECK FAILED: " + "; ".join(problems)); sys.exit(1)
print(f"k90 receipt verified (governed): {d.name} lev/boom {lev}/{boom} entries {entries} (+{sleeve} sleeve, selector_used {sleeve_used}) selector {selector} group {group} lock {lock}")
PYEOF
}
verify_k90 "$K90_DIR" || { echo "K90 receipt verification FAILED for $K90_DIR"; exit 1; }
# M4 (the outside review 10-07): the T-70 build (the unit carrying MIN_PROJ_GENERATED_AT) must have used the DK salary pull
# made after the 10:30 CT inactives -- the money-path rule. The 10:33 t70-pull unit is independent of this build, so a failed
# pull left it on the morning's pull silently. A stale pull marks the dir salary_pull_stale (copied to its union below): a
# STOP the operator clears (SALARY_PULL_STALE_OK=1), with an ALERT and a banner; the earlier published book stands.
if [[ -n "${MIN_PROJ_GENERATED_AT:-}" ]]; then
  if ! SP_WHY=$("$PROD_PY" "$PROD/scripts/check_salary_pull.py" "$K90_DIR" --after "$MIN_PROJ_GENERATED_AT"); then
    printf '%s run %s: SALARY PULL STALE: %s\n' "$(date -u +%FT%TZ)" "$RUN_TAG" "$SP_WHY" \
      | tee "$K90_DIR/salary_pull_stale" > "$OUT/ALERT-salary-pull-stale-$RUN_TAG.txt"
    printf '\n%s\n%s\n%s\n\n' "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" \
      "!!! SALARY PULL STALE for $RUN_TAG: $SP_WHY -- NOT PUBLISHABLE until the operator decides (SALARY_PULL_STALE_OK=1)" \
      "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  else
    echo "SALARY PULL: $SP_WHY"
  fi
  # O-59 (the operator 10-08: "Add a 10:47 pull" + a loud warning): the pull's CONTENT -- did it carry DraftKings' inactive
  # update? A warning only (the ~11:00 pre-upload status check stays the safety net); its line goes to an ALERT file.
  ST_OUT=$(PYTHONPATH="$PROD/src" timeout 90 "$PROD_PY" "$PROD/scripts/check_t70_statuses.py" "$K90_DIR" --group "$GROUP" \
            --inactives-utc "$MIN_PROJ_GENERATED_AT" 2>/dev/null || echo "DK STATUS CHECK UNAVAILABLE: the checker failed")
  echo "$ST_OUT"
  if grep -q "DK STATUSES LOOK PRE-INACTIVES" <<< "$ST_OUT"; then
    printf '%s run %s: %s\n' "$(date -u +%FT%TZ)" "$RUN_TAG" "$(grep -m1 -o 'DK STATUSES LOOK PRE-INACTIVES.*' <<< "$ST_OUT")" \
      > "$OUT/ALERT-dk-statuses-pre-inactives-$RUN_TAG.txt"
  fi
fi
# The T-70 rules are declared ON for the audit only on the T-70 build: the unit that carries MIN_PROJ_GENERATED_AT (the
# projections made after the 10:30 inactives). Every other build (Saturday, 09:10) runs on projections the rules never
# touched, so it declares OFF (sweep 2026-09-29 item 1; with ON on every build the audit refused every run dir).
T70_DECLARED=off; [[ -n "${MIN_PROJ_GENERATED_AT:-}" && ( "${T70_ACTIVE_Q:-0}" == "1" || "${T70_VACATED_BUMP:-0}" == "1" ) ]] && T70_DECLARED=on
echo "T-70 rules declared $T70_DECLARED for the audit (MIN_PROJ_GENERATED_AT=${MIN_PROJ_GENERATED_AT:-unset})"
# Fail-loud build audit (operator 2026-09-27): every declared lever must leave its trace, no undeclared lever may, every
# candidate must be legal and playable, the declared sources must be present, and the selector/tracks must match. A
# failure stops the chain here; the run dir is never adopted. AUDIT_SOURCES lists frame_column:min_share pairs.
( cd "$PROD" && PYTHONPATH="$PROD/src" "$PROD_PY" scripts/audit_build_levers.py "$K90_DIR" --contests "$CONTESTS_JSON" \
    --layout "${ENTER_LAYOUT:-sequential}" --expect-selector "$LIVE_SELECTOR" ${MAX_PER_GAME:+--expect-max-per-game "$MAX_PER_GAME"} \
    --min-salary "${MIN_LINEUP_SALARY:-49000}" --fade "${AUDIT_FADE:-off}" --sources "${AUDIT_SOURCES:-market_points:0.30,dk_ppg:0.80}" \
    --t70 "$T70_DECLARED" \
    --out "$OUT/lever-audit-$RUN_TAG.json" | tee "$OUT/lever-audit-$RUN_TAG.txt" ) || { echo "BUILD AUDIT FAILED for $K90_DIR (see $OUT/lever-audit-$RUN_TAG.txt); refusing the run dir"; touch "$K90_DIR/audit_failed"; exit 1; }
cp "$OUT/lever-audit-$RUN_TAG.json" "$K90_DIR/lever_audit.json" && touch "$K90_DIR/audit_passed"   # the watcher publishes only marked dirs
# 2a. The T-70 UNION (operator 2026-09-28): with UNION_SATURDAY_RUN set, the Saturday paid pool's survivors join the T-70
# pool and the book is re-selected with the same mean selector; the union run dir is verified and audited like any build
# and becomes the run dir the chain emits and the watcher promotes (newest, same lev/boom as the T-70 run).
# union_fail WHY (the outside review 10-07, H1): every union-failure exit marks the T-70 dir union_failed. When the week's
# construction lives only in the union (UNION_MAIN=mix, or a live term block) the plain T-70 book carries none of it (no
# MIX, FP, QB cap, overlap 4 or block), so the dir is ALSO marked union_required: run_dir_publishable refuses it until the
# operator decides (UNION_FAILED_OK=1 enters the plain book); the published earlier book stands. Loud, like term_block_missing.
union_fail() {
  touch "$K90_DIR/union_failed"
  if [[ "${UNION_MAIN:-mean}" == "mix" || "${UNION_TERM_BLOCK_ROWS:-0}" != "0" ]]; then
    printf '%s run %s: UNION FAILED (%s) under UNION_MAIN=%s, term block %s rows: the plain T-70 book has none of the week settings\n' \
      "$(date -u +%FT%TZ)" "$RUN_TAG" "$1" "${UNION_MAIN:-mean}" "${UNION_TERM_BLOCK_ROWS:-0}" \
      | tee "$K90_DIR/union_required" > "$OUT/ALERT-union-failed-$RUN_TAG.txt"
    printf '\n%s\n%s\n%s\n\n' "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" \
      "!!! UNION FAILED for $RUN_TAG ($1): the plain T-70 book is NOT published -- the earlier book stands until the operator decides (UNION_FAILED_OK=1 enters the plain book)" \
      "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  fi
}
if [[ -n "${UNION_SATURDAY_RUN:-}" && ",${UNION_SAT_DOSE:-2560/10240}," == *",$PAID_LEV/$PAID_BOOM,"* ]]; then   # any listed supply dose
  echo "this build ($PAID_LEV/$PAID_BOOM) IS the Saturday supply (UNION_SAT_DOSE): no union for it (sweep item 7)"
  UNION_SATURDAY_RUN=""
fi
if [[ -n "${UNION_SATURDAY_RUN:-}" ]]; then
  [[ "$LIVE_SELECTOR" == "mean" ]] || { echo "the union is defined for LIVE_SELECTOR=mean (got $LIVE_SELECTOR)"; exit 1; }
  UNION_ARGS=(--saturday-run "$UNION_SATURDAY_RUN" --saturday-dose "${UNION_SAT_DOSE:-2560/10240}" --t70-run "$K90_DIR" --live-dir "$LIVE_DIR"
              --group "$GROUP" ${WEEK_WINDOW_START_UTC:+--saturday-after "$WEEK_WINDOW_START_UTC"}
              --entries "$BOOK_ENTRIES" --tail-sleeve "$TAIL_SLEEVE" --mean-max-shared "${UNION_MEAN_MAX_SHARED:-7}" --min-proj "${LIVE_MIN_PROJ:-1.0}"
              --max-per-game "${MAX_PER_GAME:-4}" --min-salary "${MIN_LINEUP_SALARY:-49000}" --pmo "${UNION_PMO:-0}" --pmo-cap-share "${UNION_PMO_CAP:-0.5}" --main "${UNION_MAIN:-mean}")
  [[ -n "${UNION_MAIN_CAP:-}" ]] && UNION_ARGS+=(--main-cap-share "$UNION_MAIN_CAP")
  # study 18's shape portfolio (--main mix): the interleave's entry weights come from THIS week's plan and layout
  # the MIX fill order (study 42; operator 10-06): unset = group, as before
  [[ "${UNION_MAIN:-mean}" == "mix" && -n "${UNION_MIX_FILL:-}" ]] && UNION_ARGS+=(--mix-fill "$UNION_MIX_FILL")
  # the MIX coverage rows (study 43; operator 10-06): unset or 0 = off, as before
  [[ "${UNION_MAIN:-mean}" == "mix" && "${UNION_MIX_COVER_GAMES:-0}" != 0 ]] && UNION_ARGS+=(--mix-cover-games "$UNION_MIX_COVER_GAMES")
  # study 71 (the operator 10-08): the bring-back = the opponent's top receiver on the named MIX cells (A1,B); empty = off
  [[ "${UNION_MAIN:-mean}" == "mix" && -n "${UNION_MIX_BRING_BACK_TOP_WR:-}" ]] && UNION_ARGS+=(--mix-bring-back-top-wr "$UNION_MIX_BRING_BACK_TOP_WR")
  # study 71b (the operator 10-08: "just do a very small percentage of these as a test"): the rule on only N book rows; empty = every A1/B row
  [[ "${UNION_MAIN:-mean}" == "mix" && -n "${UNION_MIX_BRING_BACK_TOP_WR:-}" && -n "${UNION_MIX_BRING_BACK_TOP_WR_ROWS:-}" ]] && UNION_ARGS+=(--mix-bring-back-top-wr-rows "$UNION_MIX_BRING_BACK_TOP_WR_ROWS")
  # the half-and-half book (study 46; operator 10-06): unset or 0 = off, as before
  [[ "${UNION_MAIN:-mean}" == "mix" && "${UNION_MIX_RS_ROWS:-0}" != 0 ]] && UNION_ARGS+=(--mix-rs-rows "$UNION_MIX_RS_ROWS")
  # the MIX cells' entry quotas (study 56, fewer QB + 1 rows; the operator 10-07): unset = MIX_CELLS, as before
  [[ "${UNION_MAIN:-mean}" == "mix" && -n "${UNION_MIX_CELL_QUOTAS:-}" ]] && UNION_ARGS+=(--mix-cell-quotas "$UNION_MIX_CELL_QUOTAS")
  # priority-first dealing (the operator 10-07; default off): the main rows re-ordered by the frozen score, a live term block
  # kept at its positions (nfl_dfs.inference.priority_deal); the order is a refinement and never stops a union
  [[ "${UNION_MAIN:-mean}" == "mix" && "${UNION_PRIORITY_ORDER:-0}" == "1" ]] && UNION_ARGS+=(--priority-order)
  # The prior-top term block (the operator 10-07: "Live, capped, part of book"; default 0 = off): N rows on projection +
  # min(tilt x pred_own, cap) from the pinned file. A union that builds WITHOUT it is stopped after the union (below).
  [[ "${UNION_MAIN:-mean}" == "mix" && "${UNION_TERM_BLOCK_ROWS:-0}" != 0 ]] && UNION_ARGS+=(--term-block-rows "$UNION_TERM_BLOCK_ROWS" \
      --term-block-source "${UNION_TERM_BLOCK_SOURCE:-}" --term-block-tilt "${UNION_TERM_BLOCK_TILT:-0.20}" \
      --term-block-cap-points "${UNION_TERM_BLOCK_CAP:-2.0}")
  [[ "${UNION_MAIN:-mean}" == "mix" ]] && UNION_ARGS+=(--mix-plan "$CONTESTS_JSON" --mix-layout "${ENTER_LAYOUT:-head}" --mix-portfolio "${UNION_MIX_PORTFOLIO:?UNION_MAIN=mix needs UNION_MIX_PORTFOLIO=mix|ws}" --mix-spares "${UNION_MIX_SPARES:-15}")
  # Fantasy Points' projections replace ours in the union's selection (operator 2026-10-05): the newest FP capture taken
  # before THIS T-70 run's build, joined exactly on DK draftable ids, gated (coverage, salary, r >= 0.7); a capture from
  # before the 10:30 CT inactives prints a banner on the earlier builds and REFUSES on the T-70 build (operator 10-06: a
  # stale FP capture loses to our post-inactives numbers); any refusal falls back LOUDLY to our projections. "The T-70
  # build" = the unit carrying the T70 gate's MIN_PROJ_GENERATED_AT (only the 10:50 unit does), NOT T70_DECLARED, which
  # also needs the T-70 rules on (the reviewer 10-06, R1: turning those rules off must not silently drop the refusal).
  if [[ "${UNION_PROJ_SOURCE:-}" == "fp" ]]; then
    T70_BUILT=$("$PROD_PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['built_utc'])" "$K90_DIR/receipt.json")
    INACT_UTC=$(date -u -d "@$(TZ=America/Chicago date -d "$SUNDAY 10:30" +%s)" +%Y-%m-%dT%H:%M:%SZ)
    if ( cd "$PROD" && PYTHONPATH="$PROD/src" timeout 180 "$PROD_PY" scripts/fp_projection_override.py --frame "$K90_DIR/frame.parquet" \
           --season "$SEASON" --week "$WEEK" --before "$T70_BUILT" --inactives-utc "$INACT_UTC" --out "$OUT/proj_fp-$RUN_TAG.csv" \
           $( [[ -n "${MIN_PROJ_GENERATED_AT:-}" ]] && echo --require-after-inactives ) ) \
         2>&1 | tee "$OUT/proj_fp-$RUN_TAG.txt"; then
      UNION_ARGS+=(--proj-source "$OUT/proj_fp-$RUN_TAG.csv")
      echo "PROJECTION SOURCE for $RUN_TAG: FANTASY POINTS ($(basename "$OUT/proj_fp-$RUN_TAG.csv"))"
    else
      printf '\n%s\n%s\n%s\n\n' "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" \
        "!!! FP PROJECTIONS FAILED for $RUN_TAG: $(grep -h 'REFUSED\|Error' "$OUT/proj_fp-$RUN_TAG.txt" | tail -1) -- FALLING BACK TO OUR PROJECTIONS" \
        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
      printf '%s run %s: FP projections FAILED -> ours\n' "$(date -u +%FT%TZ)" "$RUN_TAG" >> "$OUT/proj_source_fallback-$RUN_TAG.txt"
    fi
  fi
  [[ -n "${UNION_SLEEVE_CAP:-}" ]] && UNION_ARGS+=(--sleeve-cap-share "$UNION_SLEEVE_CAP")
  [[ -n "${UNION_MAIN_DST_CAP:-}" ]] && UNION_ARGS+=(--main-dst-cap "$UNION_MAIN_DST_CAP")
  # study 35's per-QB cap in ROWS (operator 10-06: QB diversity); default unset = off, as before
  [[ -n "${UNION_MAIN_QB_CAP_ROWS:-}" ]] && UNION_ARGS+=(--main-qb-cap-rows "$UNION_MAIN_QB_CAP_ROWS" --main-qb-cap-k "${UNION_MAIN_QB_CAP_K:-}")
  [[ "${UNION_SLEEVE_INCLUDES_MAIN:-0}" == "1" ]] && UNION_ARGS+=(--sleeve-includes-main)
  [[ -n "${MEAN_DST_CAP:-}" ]] && UNION_ARGS+=(--mean-dst-cap "$MEAN_DST_CAP")
  [[ -n "${UNION_DK_STATUS:-}" ]] && UNION_ARGS+=(--dk-status "$UNION_DK_STATUS")
  # The ownership term (operator 2026-09-29, reviewer 16c293b7 §1), with its fallback ORDER (operator 2026-10-01, the
  # reviewer's cracks audit c4188027 A): TabPFN (UNION_MAIN_OWN_PREDICTOR=tabpfn) -> the blend -> Saturday's LAG file at
  # UNION_MAIN_OWN_LAG_TILT (0.10; L20's LAG_010 SUPPORTED on its own, provably pre-lock) -> no term. Every step down is
  # LOUD: a capitals banner, a line in $OUT/own_term_fallback-$RUN_TAG.txt (copied into the union dir), and the receipt's
  # own_term.source names the file actually used.
  OWN_SRC=""; OWN_TILT="${UNION_MAIN_OWN_TILT:-0}"
  own_banner() {   # $1 = what failed, $2 = why; names what is used next
    local next; if [[ -n "$OWN_SRC" ]]; then next="$(basename "$OWN_SRC") at tilt $OWN_TILT"; else next="none: NO TERM"; fi
    printf '\n%s\n%s\n%s\n\n' "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" \
      "!!! OWNERSHIP $1 FAILED for $RUN_TAG: $2 -- FALLING BACK TO $next" \
      "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    printf '%s run %s: %s FAILED: %s -> fallback %s\n' "$(date -u +%FT%TZ)" "$RUN_TAG" "$1" "$2" "$next" >> "$OUT/own_term_fallback-$RUN_TAG.txt"
  }
  own_use_lag() {  # the lag file at the lag tilt, if it passes gate 4; else no term
    if [[ -s "${OWNERSHIP_LAG:-}" ]] && ( cd "$PROD" && "$PROD_PY" scripts/check_ownership_lag.py "$OWNERSHIP_LAG" >/dev/null ); then
      OWN_SRC="$OWNERSHIP_LAG"; OWN_TILT="${UNION_MAIN_OWN_LAG_TILT:-0.10}"
    else
      OWN_SRC=""; OWN_TILT="0"
    fi
  }
  if [[ ( "${UNION_MAIN:-mean}" == "pmo_x50" || "${UNION_MAIN:-mean}" == "mix" ) && "${UNION_MAIN_OWN_TILT:-0}" != "0" ]]; then
    # LineStar RETIRED 2026-10-06 (operator 10-04; the one-time revision check, README log): no per-union capture any more
    # (it cost up to 120 s inside the T-70 window). Without a capture for the week the blend below refuses at once and
    # TabPFN cannot run, so the chain is Fantasy Points -> Saturday's LAG at UNION_MAIN_OWN_LAG_TILT -> no term.
    BLEND_SRC=""
    if ( cd "$PROD" && PYTHONPATH="$PROD/src" timeout 120 "$PROD_PY" scripts/ownership_blend.py --sets "$OWNERSHIP_LAG" --linestar-dir "$LINESTAR_DIR" \
           --season "$SEASON" --week "$WEEK" --out "$OUT/ownership_blend-$RUN_TAG.csv" ); then
      BLEND_SRC="$OUT/ownership_blend-$RUN_TAG.csv"
    fi
    # Fantasy Points' ownership first (UNION_MAIN_OWN_PREDICTOR=fp; operator 10-02, a reversible Week-4 trial): capture
    # it NOW (the T-70 numbers), export it matched to this frame and rescaled to the blend's (else the lag's) skill
    # total; any failure falls back LOUDLY to the TabPFN -> blend -> lag chain below.
    FP_WHY=""
    if [[ "${UNION_MAIN_OWN_PREDICTOR:-blend}" == "fp" ]]; then
      # the shared FP browser-profile lock (Chromium: one process per profile; scripts/fp_projections_capture.sh holds it
      # too, and so does a concurrent build's capture): wait up to FP_OWN_LOCK_WAIT_S, else the loud fallback below
      FP_PROFILE_LOCK=${FP_PROFILE_LOCK:-$HOME/.cache/nfl-dfs/fantasy-points-profile.lock}; mkdir -p "$(dirname "$FP_PROFILE_LOCK")"
      ( cd "$PROD" && PYTHONPATH="$PROD/src" flock -w "${FP_OWN_LOCK_WAIT_S:-300}" "$FP_PROFILE_LOCK" timeout 240 "$PROD_PY" -m nfl_dfs.ops.fantasy_points_ownership collect --week "$WEEK" ) \
          > "$OUT/ownership_fp-$RUN_TAG.txt" 2>&1 || echo "FP OWNERSHIP CAPTURE FAILED for $RUN_TAG (see $OUT/ownership_fp-$RUN_TAG.txt); the newest earlier capture is used if fresh"
      if ( cd "$PROD" && PYTHONPATH="$PROD/src" timeout 120 "$PROD_PY" scripts/ownership_fp.py --season "$SEASON" --week "$WEEK" \
             --frame "$K90_DIR/frame.parquet" --lag "$OWNERSHIP_LAG" ${BLEND_SRC:+--blend "$BLEND_SRC"} --max-age-hours "${FP_MAX_AGE_HOURS:-30}" \
             --out "$OUT/ownership_fp-$RUN_TAG.csv" ) 2>&1 | tee -a "$OUT/ownership_fp-$RUN_TAG.txt"; then
        OWN_SRC="$OUT/ownership_fp-$RUN_TAG.csv"
        echo "OWNERSHIP TERM SOURCE for $RUN_TAG: FANTASY POINTS ($(basename "$OWN_SRC")) at tilt $OWN_TILT; $(grep -h '^FP OWNERSHIP AGE' "$OUT/ownership_fp-$RUN_TAG.txt" | tail -1 | sed 's/^FP OWNERSHIP //')"
      else
        FP_WHY="$(grep -h 'REFUSED' "$OUT/ownership_fp-$RUN_TAG.txt" | tail -1)"; FP_WHY=${FP_WHY:-the export failed}
      fi
    fi
    if [[ -n "$OWN_SRC" ]]; then
      :
    elif [[ "${UNION_MAIN_OWN_PREDICTOR:-blend}" == "tabpfn" || "${UNION_MAIN_OWN_PREDICTOR:-blend}" == "fp" ]]; then
      TAB_WHY=""
      if [[ -z "$BLEND_SRC" ]]; then
        TAB_WHY="no valid LineStar capture (TabPFN and the blend both need it)"
      elif ! ( cd "$PROD" && PYTHONPATH="$PROD/src" timeout 120 "$PROD_PY" scripts/ownership_tabpfn.py features --season "$SEASON" --week "$WEEK" \
                 --frame "$K90_DIR/frame.parquet" --lags "$OWNERSHIP_LAGS" --linestar-dir "$LINESTAR_DIR" --history "$OWN_TABPFN_ROWS" \
                 --out "$OUT/ownership_tabpfn_features-$RUN_TAG.parquet" ) 2>&1 | tee "$OUT/ownership_tabpfn-$RUN_TAG.txt"; then
        TAB_WHY="features step: $(grep -h 'REFUSED' "$OUT/ownership_tabpfn-$RUN_TAG.txt" | tail -1)"
      elif ! ( cd "$PROD" && timeout 300 "$TABPFN_PY" scripts/ownership_tabpfn.py fit --rows "$OWN_TABPFN_ROWS" \
                 ${OWN_TABPFN_ROWS_2026:+--rows-2026 "$OWN_TABPFN_ROWS_2026"} --features "$OUT/ownership_tabpfn_features-$RUN_TAG.parquet" \
                 --out "$OUT/ownership_tabpfn-$RUN_TAG.csv" ) 2>&1 | tee -a "$OUT/ownership_tabpfn-$RUN_TAG.txt"; then
        TAB_WHY="fit step: $(grep -h 'REFUSED\|Error' "$OUT/ownership_tabpfn-$RUN_TAG.txt" | tail -1)"
      fi
      if [[ -z "$TAB_WHY" ]]; then
        OWN_SRC="$OUT/ownership_tabpfn-$RUN_TAG.csv"
        echo "OWNERSHIP TERM SOURCE for $RUN_TAG: TABPFN ($(basename "$OWN_SRC")) at tilt $OWN_TILT; the blend stays beside it as the fallback"
      else
        if [[ -n "$BLEND_SRC" ]]; then OWN_SRC="$BLEND_SRC"; else own_use_lag; fi
        own_banner TABPFN "$TAB_WHY"
      fi
    elif [[ -n "$BLEND_SRC" ]]; then
      OWN_SRC="$BLEND_SRC"
    else
      own_use_lag
      own_banner BLEND "no valid LineStar capture"
    fi
    [[ -n "$FP_WHY" ]] && own_banner "FANTASY POINTS" "$FP_WHY"
    [[ -n "$OWN_SRC" ]] && UNION_ARGS+=(--main-own-tilt "$OWN_TILT" --main-own-source "$OWN_SRC")
  fi
  # His 10-09 package (study 89, Addendum 186; HANDOFF 5380e0e7): the 35% player cap WITH the ownership cap -- each skill
  # player in at most floor(K x (his FP projected ownership, rescaled, + UNION_MAIN_OWN_CAP_DELTA points)) main-book rows.
  # The flat 35% never runs alone (his rule): no FP ownership export = TODAY's book (the player cap 0.5, no ownership cap),
  # LOUDLY (a banner and an ALERT file); union_reselect also builds at --main-own-cap-fallback-share by itself if it refuses
  # the file, and the host turns its "OWN CAP NOT APPLIED" line into the same ALERT after the run. FP's export: the term's
  # when there is one, else this run's own capture + export (the winner order's pattern below).
  set_cap_share() {                                         # --main-cap-share VALUE in UNION_ARGS, in place (one value for parity)
    local i
    for i in "${!UNION_ARGS[@]}"; do [[ "${UNION_ARGS[$i]}" == "--main-cap-share" ]] && { UNION_ARGS[$((i+1))]="$1"; return; }; done
    UNION_ARGS+=(--main-cap-share "$1")
  }
  own_cap_alert() {                                         # his package not applied: today's book, loudly
    printf '%s run %s: OWN CAP NOT APPLIED (the book as before the package: player cap %s, no ownership cap): %s\n' "$(date -u +%FT%TZ)" "$RUN_TAG" \
      "${UNION_MAIN_OWN_CAP_FALLBACK_SHARE:-0.5}" "$1" | tee -a "$OUT/ALERT-own-cap-not-applied-$RUN_TAG.txt"
    printf '\n%s\n%s\n%s\n\n' "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" \
      "!!! OWN CAP NOT APPLIED for $RUN_TAG: $1 -- TODAY'S BOOK (player cap ${UNION_MAIN_OWN_CAP_FALLBACK_SHARE:-0.5}, no ownership cap)" \
      "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  }
  OWN_CAP_SRC=""; OWN_CAP_ON=0
  if [[ "${UNION_MAIN:-mean}" == "mix" && "${UNION_MAIN_OWN_CAP_DELTA:-0}" != "0" ]]; then
    OWN_CAP_ON=1; OWN_CAP_WHY=""
    if [[ -n "$OWN_SRC" && "$(basename "$OWN_SRC")" == ownership_fp-* ]]; then
      OWN_CAP_SRC="$OWN_SRC"
    else
      FP_PROFILE_LOCK=${FP_PROFILE_LOCK:-$HOME/.cache/nfl-dfs/fantasy-points-profile.lock}; mkdir -p "$(dirname "$FP_PROFILE_LOCK")"
      ( cd "$PROD" && PYTHONPATH="$PROD/src" flock -w "${FP_OWN_LOCK_WAIT_S:-300}" "$FP_PROFILE_LOCK" timeout 240 "$PROD_PY" -m nfl_dfs.ops.fantasy_points_ownership collect --week "$WEEK" ) \
          > "$OUT/own_cap-$RUN_TAG.txt" 2>&1 || echo "FP OWNERSHIP CAPTURE FAILED for $RUN_TAG (own cap; see $OUT/own_cap-$RUN_TAG.txt); the newest earlier capture is used if fresh"
      if ( cd "$PROD" && PYTHONPATH="$PROD/src" timeout 120 "$PROD_PY" scripts/ownership_fp.py --season "$SEASON" --week "$WEEK" \
             --frame "$K90_DIR/frame.parquet" --lag "$OWNERSHIP_LAG" --max-age-hours "${FP_MAX_AGE_HOURS:-30}" \
             --out "$OUT/ownership_fp-$RUN_TAG.csv" ) 2>&1 | tee -a "$OUT/own_cap-$RUN_TAG.txt"; then
        OWN_CAP_SRC="$OUT/ownership_fp-$RUN_TAG.csv"
      else
        OWN_CAP_WHY="FP ownership export: $(grep -h 'REFUSED' "$OUT/own_cap-$RUN_TAG.txt" | tail -1)"
      fi
    fi
    if [[ -n "$OWN_CAP_SRC" ]]; then
      UNION_ARGS+=(--main-own-cap-delta "$UNION_MAIN_OWN_CAP_DELTA" --main-own-cap-source "$OWN_CAP_SRC"
                   --main-own-cap-fallback-share "${UNION_MAIN_OWN_CAP_FALLBACK_SHARE:-0.5}")
      echo "OWN CAP for $RUN_TAG: ON (+$UNION_MAIN_OWN_CAP_DELTA points over FP ownership $(basename "$OWN_CAP_SRC"); player cap ${UNION_MAIN_CAP:-0.5})"
    else
      set_cap_share "${UNION_MAIN_OWN_CAP_FALLBACK_SHARE:-0.5}"    # TODAY's book: the player cap back to 0.5, in place
      own_cap_alert "${OWN_CAP_WHY:-no FP ownership file}"
    fi
  fi
  row_rules_alert() {                                       # his test-2 rules not applied: the book stands without them, loudly
    printf '%s run %s: ROW RULES NOT APPLIED: %s\n' "$(date -u +%FT%TZ)" "$RUN_TAG" "$1" | tee -a "$OUT/ALERT-row-rules-not-applied-$RUN_TAG.txt"
    printf '\n%s\n%s\n%s\n\n' "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" \
      "!!! ROW RULES NOT APPLIED for $RUN_TAG: $1 -- the book stands without them" \
      "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  }
  # His 10-09 test 2 (study 91; HANDOFF 2ab54e30): at most one TE and at most one skill player under 3% FP projected
  # ownership per main-book row, ONLY on top of his package and only when its ownership cap is applied (the rule reads the
  # same file). Live only if study 91 passes his rule; off = unset. No ownership file = no row rules, LOUDLY.
  if [[ "${UNION_MAIN:-mean}" == "mix" && "${UNION_MIX_ROW_RULES:-}" == "te1_low1" ]]; then
    if (( OWN_CAP_ON )) && [[ -n "$OWN_CAP_SRC" ]]; then
      UNION_ARGS+=(--mix-max-te 1 --mix-max-low-own 1 --mix-low-own-pct 3)
      echo "ROW RULES for $RUN_TAG: ON (at most one TE and one skill player under 3% FP ownership per book row; $(basename "$OWN_CAP_SRC"))"
    else
      row_rules_alert "the ownership cap is not on for this run (no FP ownership file)"
    fi
  fi
  # His 10-09 S1 / S2 ("Test both tonight for live"; HANDOFF 2be97397), each live only if its gate passes; off = unset:
  # S1 shrinks the main book's objective toward the salary-typical projection (union_reselect keeps the frame's proj /
  # proj_tourney as they are, so the lever audit is unaffected); S2 asks for at least one $8,000+ non-QB skill player per row.
  # S1 was tested only on the ARMED version (the package + the row rules): passed exactly when the row rules are, so a
  # fallback week (no ownership file) is exactly the book as before, never "that book + shrink" (the outside reviewer 10-09)
  if [[ "${UNION_MAIN:-mean}" == "mix" && -n "${UNION_PROJ_SHRINK_K:-}" && "${UNION_PROJ_SHRINK_K}" != "1" && "${UNION_PROJ_SHRINK_K}" != "1.0" ]]; then
    if printf '%s\n' "${UNION_ARGS[@]}" | grep -qx -- '--mix-max-te'; then
      UNION_ARGS+=(--proj-shrink-k "$UNION_PROJ_SHRINK_K" --proj-shrink-window "${UNION_PROJ_SHRINK_WINDOW:-500}")
      echo "PROJECTION SHRINK for $RUN_TAG: ON (k $UNION_PROJ_SHRINK_K toward the salary-typical projection, +/- \$${UNION_PROJ_SHRINK_WINDOW:-500})"
    else
      row_rules_alert "SHRINK NOT APPLIED: the projection shrink rides with the package + row rules, which are not on for this run"
    fi
  fi
  # S2 rides ONLY with the row rules (union_reselect refuses --mix-min-star without them): passed exactly when they are
  if [[ "${UNION_MAIN:-mean}" == "mix" && "${UNION_MIX_MIN_STAR:-0}" == "1" ]]; then
    if printf '%s\n' "${UNION_ARGS[@]}" | grep -qx -- '--mix-max-te'; then
      UNION_ARGS+=(--mix-min-star 1 --mix-star-salary "${UNION_MIX_STAR_SALARY:-8000}")
      echo "STAR RULE for $RUN_TAG: ON (at least one non-QB skill player at \$${UNION_MIX_STAR_SALARY:-8000}+ per book row)"
    else
      row_rules_alert "the star rule rides with the row rules, which are not on for this run"
    fi
  fi
  # Study 48b's winner-likeness order (operator 10-07: "Test tonight, aim for Week 5"; default off): FP's projected
  # ownership (the term's FP export when there is one, else this run's own capture + export) and the players' prior-game
  # touchdowns / attempts (scripts/winner_like_inputs.py), then the union re-orders the main book by study 48's frozen
  # score. Any failure keeps the book's own order, LOUDLY (a banner, a fallback file copied with the union, the receipt).
  # Study 48d's selection (UNION_WINNER_SELECT=1; default off) uses the same inputs; the two are never on together.
  WIN_FLAG=""
  [[ "${UNION_WINNER_ORDER:-0}" == "1" ]] && WIN_FLAG="--winner-order"
  [[ "${UNION_WINNER_SELECT:-0}" == "1" ]] && WIN_FLAG="--winner-select"
  if [[ "${UNION_WINNER_ORDER:-0}" == "1" && "${UNION_WINNER_SELECT:-0}" == "1" ]]; then
    echo "WINNER ORDER and WINNER SELECT are both on: refusing both (they are alternatives; check_week_runtime refuses this too)"; WIN_FLAG=""
  fi
  if [[ -n "$WIN_FLAG" && "${UNION_MAIN:-mean}" == "mix" ]]; then
    WIN_OWN=""; WIN_WHY=""
    if [[ -n "$OWN_SRC" && "$(basename "$OWN_SRC")" == ownership_fp-* ]]; then
      WIN_OWN="$OWN_SRC"
    else
      FP_PROFILE_LOCK=${FP_PROFILE_LOCK:-$HOME/.cache/nfl-dfs/fantasy-points-profile.lock}; mkdir -p "$(dirname "$FP_PROFILE_LOCK")"
      ( cd "$PROD" && PYTHONPATH="$PROD/src" flock -w "${FP_OWN_LOCK_WAIT_S:-300}" "$FP_PROFILE_LOCK" timeout 240 "$PROD_PY" -m nfl_dfs.ops.fantasy_points_ownership collect --week "$WEEK" ) \
          > "$OUT/winner_own-$RUN_TAG.txt" 2>&1 || echo "FP OWNERSHIP CAPTURE FAILED for $RUN_TAG (winner order; see $OUT/winner_own-$RUN_TAG.txt); the newest earlier capture is used if fresh"
      if ( cd "$PROD" && PYTHONPATH="$PROD/src" timeout 120 "$PROD_PY" scripts/ownership_fp.py --season "$SEASON" --week "$WEEK" \
             --frame "$K90_DIR/frame.parquet" --lag "$OWNERSHIP_LAG" --max-age-hours "${FP_MAX_AGE_HOURS:-30}" \
             --out "$OUT/ownership_fp-$RUN_TAG.csv" ) 2>&1 | tee -a "$OUT/winner_own-$RUN_TAG.txt"; then
        WIN_OWN="$OUT/ownership_fp-$RUN_TAG.csv"
      else
        WIN_WHY="FP ownership export: $(grep -h 'REFUSED' "$OUT/winner_own-$RUN_TAG.txt" | tail -1)"
      fi
    fi
    if [[ -n "$WIN_OWN" ]]; then
      if ( cd "$PROD" && PYTHONPATH="$PROD/src" timeout 180 "$PROD_PY" scripts/winner_like_inputs.py --season "$SEASON" --week "$WEEK" \
             --frame "$K90_DIR/frame.parquet" --own "$WIN_OWN" --out "$OUT/winner_inputs-$RUN_TAG.csv" ) 2>&1 | tee "$OUT/winner_inputs-$RUN_TAG.txt"; then
        UNION_ARGS+=("$WIN_FLAG" "$OUT/winner_inputs-$RUN_TAG.csv")
        echo "WINNER ${WIN_FLAG#--winner-} for $RUN_TAG: ON (studies 48b / 48d; FP ownership $(basename "$WIN_OWN"))"
      else
        WIN_WHY="inputs: $(grep -h 'REFUSED\|Error' "$OUT/winner_inputs-$RUN_TAG.txt" | tail -1)"
      fi
    fi
    if [[ -n "$WIN_WHY" ]]; then
      printf '\n%s\n%s\n%s\n\n' "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" \
        "!!! WINNER ${WIN_FLAG#--winner-} NOT APPLIED for $RUN_TAG: ${WIN_WHY} -- the book stands as built" \
        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
      printf '%s run %s: winner order NOT applied: %s\n' "$(date -u +%FT%TZ)" "$RUN_TAG" "$WIN_WHY" >> "$OUT/winner_order_fallback-$RUN_TAG.txt"
    fi
  fi
  # The winner-shaped tail sleeve (operator 2026-10-02, after the corpus audit): the Millionaire/FFWC/$555 rows come from a
  # field-like sample built from the pre-lock ownership predictor -- the term's source when there is one, else Saturday's
  # lag file. union_reselect.py falls back LOUDLY to the projection sleeve on any failure.
  if [[ "${UNION_SLEEVE_SOURCE:-mean}" == "field" ]]; then
    SLV_SRC="${OWN_SRC:-${OWNERSHIP_LAG:-}}"
    UNION_ARGS+=(--sleeve-source field --sleeve-field-mode "${UNION_SLEEVE_FIELD_MODE:-top}" --sleeve-max-per-game "${UNION_SLEEVE_MAX_PER_GAME:-5}")
    [[ -n "${UNION_SLEEVE_FIELD_ROWS:-}" ]] && UNION_ARGS+=(--sleeve-field-rows "$UNION_SLEEVE_FIELD_ROWS")
    [[ -n "$SLV_SRC" ]] && UNION_ARGS+=(--sleeve-own-source "$SLV_SRC")
    echo "TAIL SLEEVE SOURCE for $RUN_TAG: field sample (${UNION_SLEEVE_FIELD_MODE:-top}, <= ${UNION_SLEEVE_MAX_PER_GAME:-5} per game) from ${SLV_SRC:-NO OWNERSHIP FILE (will fall back)}"
  fi
  # drop the term's flags from an argument list (the refusal fallbacks below)
  strip_own() { OUT_ARGS=(); local skip=0; for x in "$@"; do
      if (( skip )); then skip=0; continue; fi
      case "$x" in --main-own-tilt|--main-own-source) skip=1 ;; *) OUT_ARGS+=("$x") ;; esac; done; }
  T2=$(date +%s)
  # the exact arguments of the last union call, kept with the union dir so Monday can rebuild the incumbent's book on
  # paper from the same inputs (scripts/union_paper_rebuild.sh; adoption track v2's unchanged comparison)
  run_union() { printf '%q ' "$@" > "$OUT/union-args-$RUN_TAG.txt"; ( cd "$PROD" && LIVE_FLEX_LATEST="${LIVE_FLEX_LATEST:-1}" PYTHONPATH="$CLONE/src:$PROD/src" "$LAB_PY" scripts/union_reselect.py "$@" 2>&1 | tee "$OUT/union-$RUN_TAG.txt"; return "${PIPESTATUS[0]}" ); }
  # shellcheck source=union_fallbacks.sh
  source "$PROD/scripts/union_fallbacks.sh"                 # mix_fallback: MIX REFUSED -> HOUSE MAIN (C), loudly
  UNION_MAIN_EFFECTIVE="${UNION_MAIN:-mean}"
  UNION_RC=0; run_union "${UNION_ARGS[@]}" || UNION_RC=$?
  if (( UNION_RC != 0 )) && grep -q '^OWN TERM REFUSED' "$OUT/union-$RUN_TAG.txt"; then   # anchored: a term-block refusal prints it mid-line (the outside review 10-07)
    # the union refused the term's file or its solves (named, before any output): step down to the lag file at the lag
    # tilt (unless that is what was refused), then to no term -- loudly each time
    cp "$OUT/union-$RUN_TAG.txt" "$OUT/union-$RUN_TAG-own-refused.txt"; OWN_REFUSED=1
    WHY=$(grep '^OWN TERM REFUSED' "$OUT/union-$RUN_TAG.txt" | tail -1)
    strip_own "${UNION_ARGS[@]}"; UNION_ARGS=("${OUT_ARGS[@]}")
    WAS_LAG=0; [[ "$OWN_SRC" == "${OWNERSHIP_LAG:-}" ]] && WAS_LAG=1
    if (( ! WAS_LAG )); then own_use_lag; else OWN_SRC=""; OWN_TILT="0"; fi
    own_banner "TERM ($(basename "${OWN_SRC:-none}"))" "the union refused it: $WHY"
    [[ -n "$OWN_SRC" ]] && UNION_ARGS+=(--main-own-tilt "$OWN_TILT" --main-own-source "$OWN_SRC")
    UNION_RC=0; run_union "${UNION_ARGS[@]}" || UNION_RC=$?
    if (( UNION_RC != 0 )) && grep -q '^OWN TERM REFUSED' "$OUT/union-$RUN_TAG.txt"; then
      strip_own "${UNION_ARGS[@]}"; UNION_ARGS=("${OUT_ARGS[@]}"); OWN_SRC=""; OWN_TILT="0"
      own_banner "LAG TERM" "the union refused it too: $(grep '^OWN TERM REFUSED' "$OUT/union-$RUN_TAG.txt" | tail -1)"
      UNION_RC=0; run_union "${UNION_ARGS[@]}" || UNION_RC=$?
    fi
  fi
  mix_fallback                                               # a refused MIX main re-runs as the house main (term kept)
  if (( UNION_RC != 0 )); then
    if [[ "$UNION_MAIN_EFFECTIVE" == "pmo_x50" ]] && grep -q 'PMO_X50 MAIN REFUSED' "$OUT/union-$RUN_TAG.txt"; then
      # fail closed, named (operator spec 14:05): the capped optimizer could not reach K rows; the union's MEAN main is built
      # instead, in capitals, and the run dir carries the refusal
      echo "PMO_X50 MAIN REFUSED -- $(grep 'PMO_X50 MAIN REFUSED' "$OUT/union-$RUN_TAG.txt" | tail -1); BUILDING THE UNION'S MEAN MAIN INSTEAD"
      cp "$OUT/union-$RUN_TAG.txt" "$OUT/union-$RUN_TAG-pmo-refused.txt"
      strip_own "${UNION_ARGS[@]}"; MEAN_ARGS_U=("${OUT_ARGS[@]}")     # the term is defined for pmo_x50 only
      for i in "${!MEAN_ARGS_U[@]}"; do [[ "${MEAN_ARGS_U[$i]}" == "--main" ]] && MEAN_ARGS_U[$((i+1))]=mean; done
      run_union "${MEAN_ARGS_U[@]}" || { echo "UNION FAILED (see $OUT/union-$RUN_TAG.txt); the T-70 run dir $K90_DIR stands"; union_fail "the mean-main fallback union failed"; exit 1; }
      UNION_DIR=$(sed -n 's/^UNION -> //p' "$OUT/union-$RUN_TAG.txt" | tail -1); [[ -n "$UNION_DIR" ]] && cp "$OUT/union-$RUN_TAG-pmo-refused.txt" "$UNION_DIR/pmo_x50_refused.txt"
      [[ -n "$UNION_DIR" && -n "${OWN_REFUSED:-}" ]] && cp "$OUT/union-$RUN_TAG-own-refused.txt" "$UNION_DIR/own_term_refused.txt"
    else
      echo "UNION FAILED (see $OUT/union-$RUN_TAG.txt); the T-70 run dir $K90_DIR stands"; union_fail "the union failed, rc $UNION_RC"; exit 1
    fi
  fi
  if [[ "${UNION_MIX_ROW_RULES:-}" == "te1_low1" ]] && grep -q 'ROW RULES NOT APPLIED' "$OUT/union-$RUN_TAG.txt" 2>/dev/null; then
    row_rules_alert "the union refused them: $(grep -h 'ROW RULES NOT APPLIED' "$OUT/union-$RUN_TAG.txt" | tail -1)"
  fi
  if (( OWN_CAP_ON )) && grep -q 'OWN CAP NOT APPLIED' "$OUT/union-$RUN_TAG.txt" 2>/dev/null; then
    own_cap_alert "the union refused it: $(grep -h 'OWN CAP NOT APPLIED' "$OUT/union-$RUN_TAG.txt" | tail -1)"
  fi
  UNION_DIR=$(sed -n 's/^UNION -> //p' "$OUT/union-$RUN_TAG.txt" | tail -1)
  [[ -n "$UNION_DIR" && -n "${OWN_REFUSED:-}" && ! -f "$UNION_DIR/own_term_refused.txt" ]] && cp "$OUT/union-$RUN_TAG-own-refused.txt" "$UNION_DIR/own_term_refused.txt"
  [[ -n "$UNION_DIR" && -f "$OUT/union-args-$RUN_TAG.txt" ]] && cp "$OUT/union-args-$RUN_TAG.txt" "$UNION_DIR/union_args.txt"
  [[ -n "$UNION_DIR" && -f "$OUT/ALERT-own-cap-not-applied-$RUN_TAG.txt" ]] && cp "$OUT/ALERT-own-cap-not-applied-$RUN_TAG.txt" "$UNION_DIR/own_cap_not_applied.txt"
  [[ -n "$UNION_DIR" && -f "$OUT/ALERT-row-rules-not-applied-$RUN_TAG.txt" ]] && cp "$OUT/ALERT-row-rules-not-applied-$RUN_TAG.txt" "$UNION_DIR/row_rules_not_applied.txt"
  # the projection source travels with the union dir, so the upload sheet can name it (the outside review 10-06, (1b))
  [[ -n "$UNION_DIR" && -f "$OUT/proj_fp-$RUN_TAG.txt" ]] && cp "$OUT/proj_fp-$RUN_TAG.txt" "$UNION_DIR/proj_source_log.txt"
  [[ -n "$UNION_DIR" && -f "$OUT/proj_source_fallback-$RUN_TAG.txt" ]] && cp "$OUT/proj_source_fallback-$RUN_TAG.txt" "$UNION_DIR/proj_source_fallback.txt"
  [[ -n "$UNION_DIR" && -f "$OUT/union-$RUN_TAG-mix-refused.txt" ]] && cp "$OUT/union-$RUN_TAG-mix-refused.txt" "$UNION_DIR/mix_refused.txt" \
    && echo "!!! MIX REFUSED for this union; it carries the HOUSE main (C): $UNION_DIR/mix_refused.txt"
  [[ -n "$UNION_DIR" && -f "$OUT/winner_order_fallback-$RUN_TAG.txt" ]] && cp "$OUT/winner_order_fallback-$RUN_TAG.txt" "$UNION_DIR/winner_order_fallback.txt" \
    && echo "!!! WINNER ORDER NOT APPLIED for this union: $UNION_DIR/winner_order_fallback.txt"
  [[ -n "$UNION_DIR" && -f "$OUT/own_term_fallback-$RUN_TAG.txt" ]] && cp "$OUT/own_term_fallback-$RUN_TAG.txt" "$UNION_DIR/own_term_fallback.txt" \
    && echo "!!! OWNERSHIP TERM FELL BACK for this union: $UNION_DIR/own_term_fallback.txt"
  [[ -n "$UNION_DIR" && -f "$UNION_DIR/receipt.json" ]] || { echo "union run dir not found in $OUT/union-$RUN_TAG.txt"; union_fail "the union run dir was not found"; exit 1; }
  [[ -f "$K90_DIR/salary_pull_stale" ]] && cp "$K90_DIR/salary_pull_stale" "$UNION_DIR/salary_pull_stale"   # M4: the union inherits the STOP
  verify_k90 "$UNION_DIR" || { echo "K90 receipt verification FAILED for the union $UNION_DIR"; union_fail "the union receipt verification failed"; rm -rf "$UNION_DIR"; exit 1; }
  # A DECIDED live rule must not go missing silently (the reviewer, 10-07): with UNION_TERM_BLOCK_ROWS set, a union whose
  # receipt does not carry the applied block (the right size, the pinned file) is marked term_block_missing, which
  # run_dir_publishable refuses -- nothing is published until the operator decides (TERM_BLOCK_MISSING_OK=1 enters without it).
  if [[ "${UNION_TERM_BLOCK_ROWS:-0}" != 0 ]]; then
    TB_WHY=$("$PROD_PY" - "$UNION_DIR/receipt.json" "$UNION_TERM_BLOCK_ROWS" "${UNION_TERM_BLOCK_SHA256:-}" <<'PYEOF'
import json, sys
rec, rows, sha = sys.argv[1], int(sys.argv[2]), sys.argv[3]
try:
    mix = json.load(open(rec))["config"]["union"]["mix"]["mix"]
except Exception as exc:
    print(f"the union receipt has no mix meta ({type(exc).__name__}: {exc})"); sys.exit()
src, term = mix.get("term_source") or {}, mix.get("term")
if "not_applied" in src:
    print(f"not applied: {src['not_applied']}")
elif not term or term.get("term_rows") != rows or sum(b == "T" for b in term.get("blocks", [])) != rows:
    print(f"the receipt carries no {rows}-row term block (term = {None if not term else term.get('term_rows')})")
elif sha and str(src.get("source_sha256", "")) != sha:
    print(f"the block's file sha {str(src.get('source_sha256'))[:12]} is not the pinned {sha[:12]}")
PYEOF
)
    if [[ -n "$TB_WHY" ]]; then
      printf '%s run %s: TERM BLOCK MISSING: %s\n' "$(date -u +%FT%TZ)" "$RUN_TAG" "$TB_WHY" | tee "$UNION_DIR/term_block_missing" > "$OUT/ALERT-term-block-missing-$RUN_TAG.txt"
      printf '\n%s\n%s\n%s\n\n' "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" \
        "!!! TERM BLOCK MISSING for $RUN_TAG: $TB_WHY -- NOT PUBLISHABLE until the operator decides (TERM_BLOCK_MISSING_OK=1)" \
        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    else
      echo "TERM BLOCK for $RUN_TAG: $UNION_TERM_BLOCK_ROWS rows applied (receipt checked)"
    fi
  fi
  ( cd "$PROD" && PYTHONPATH="$PROD/src" "$PROD_PY" scripts/audit_build_levers.py "$UNION_DIR" --contests "$CONTESTS_JSON" \
      --layout "${ENTER_LAYOUT:-sequential}" --expect-selector "$LIVE_SELECTOR" ${MAX_PER_GAME:+--expect-max-per-game "$MAX_PER_GAME"} \
      --min-salary "${MIN_LINEUP_SALARY:-49000}" --fade "${AUDIT_FADE:-off}" --sources "${AUDIT_SOURCES:-market_points:0.30,dk_ppg:0.80}" \
      --t70 "$T70_DECLARED" \
      --out "$OUT/lever-audit-$RUN_TAG-union.json" | tee "$OUT/lever-audit-$RUN_TAG-union.txt" ) || { echo "BUILD AUDIT FAILED for the union $UNION_DIR; refusing it (the T-70 run dir $K90_DIR stands)"; union_fail "the union build audit failed"; rm -rf "$UNION_DIR"; exit 1; }
  cp "$OUT/lever-audit-$RUN_TAG-union.json" "$UNION_DIR/lever_audit.json" && touch "$UNION_DIR/audit_passed"
  echo "union=$UNION_DIR (T-70 run $K90_DIR; $(( $(date +%s) - T2 )) s)"
  K90_DIR=$UNION_DIR
fi
if [[ -n "${SUPERSEDE_AFTER_UTC:-}" && "$(date -u +%Y-%m-%dT%H:%M:%S)" > "$SUPERSEDE_AFTER_UTC" ]]; then
  # sweep item 12: this build (the 09:10 slot) finished after the T-70 build started; publication is by newest dir, so
  # its union would displace the T-70 union. Mark every dir this build produced; the watcher never publishes a marked dir.
  for d in "$K90_DIR" ${UNION_DIR:+"$UNION_DIR"}; do touch "$d/superseded"; done
  echo "SUPERSEDED: this build finished at $(date -u +%H:%M:%S)Z, after $SUPERSEDE_AFTER_UTC (the T-70 build's start); it will not be published"
fi
[[ -n "$PAID_DIR" ]] || PAID_DIR=$K90_DIR
echo "k90=$K90_DIR"
# 2b. Cash/double-up PAPER shadows, arms A (mean-max on the served projection) and B (the same on the market-converted
# projection), built from the FINAL run dir before lock, entered nowhere, scored Monday (cash_shadow_paper.py score).
# Week 3 had none because this was a human evening step; now it is the chain's. A failure is printed in capitals and
# recorded, and does not stop the money path (paper).
if [[ "${CASH_SHADOW:-1}" == "1" ]]; then
  for arm in A B; do
    CS_OUT="$OUT/cash-shadow-w$(printf '%02d' "$WEEK")-$arm-$RUN_TAG"
    if ( cd "$PROD" && PYTHONPATH="$CLONE/src:$PROD/src" "$LAB_PY" reports/lab-handoffs/cash_shadow_paper.py \
           "$( [[ "$arm" == "B" ]] && echo build-b || echo build )" "$K90_DIR" "$CS_OUT" --n "${CASH_SHADOW_N:-20}" > "$CS_OUT.log" 2>&1 ); then
      echo "cash shadow $arm -> $CS_OUT (from $K90_DIR)"
      # the upload file for a cash pilot (operator 2026-09-28): draftable ids, create-only; paper unless the operator uploads it
      if ( cd "$PROD" && LIVE_FLEX_LATEST="${LIVE_FLEX_LATEST:-1}" PYTHONPATH="$CLONE/src:$PROD/src" "$LAB_PY" scripts/cash_shadow_upload.py "$CS_OUT" \
             --run-dir "$K90_DIR" --output "$OUT/upload-$RUN_TAG-cash-$arm.csv" > "$OUT/upload-$RUN_TAG-cash-$arm.receipt.json" 2>&1 ); then
        echo "cash upload $arm -> $OUT/upload-$RUN_TAG-cash-$arm.csv"
      else
        echo "CASH UPLOAD $arm FAILED (see $OUT/upload-$RUN_TAG-cash-$arm.receipt.json)"; echo "cash-upload-$arm FAILED $RUN_TAG" >> "$OUT/cash-shadow-failures.txt"
      fi
    else
      echo "CASH SHADOW $arm FAILED (see $CS_OUT.log); the money path continues -- record it in the handoff"; echo "cash-shadow-$arm FAILED $RUN_TAG" >> "$OUT/cash-shadow-failures.txt"
    fi
  done
fi
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
emit_ref() {  # $1 run dir, $2 label, $3 N: a REFERENCE emit of ranks 1..N, skipped (said, not failed) when N exceeds the
  # book (2026-10-08: at K 26 the all30 / all90 emits always failed "rank range 1-30 exceeds the 26 available lineups",
  # breaking the rule that an EMIT FAILED line on Sunday means a real failure)
  local book=$(( BOOK_ENTRIES + ${TAIL_SLEEVE:-0} ))
  if (( $3 > book )); then echo "skip reference emit $2 (ranks 1-$3 exceed the $book-lineup book)"; else emit "$1" "$2" "1-$3"; fi
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
       emit_ref "$VET_DIR" vetted-all30 30; emit_ref "$VET_DIR" vetted-all90 90; } \
  || echo "VETTING FAILED (see $OUT/vetting-$RUN_TAG.txt)"
COMP_DIR="$OUT/composite-$RUN_TAG"
( cd "$PROD" && PYTHONPATH="$PROD/src" "$PROD_PY" "$TOOLS/player_score.py" "$K90_DIR" --k 30 --season "$SEASON" --week "$WEEK" --vetting "$VET_DIR/vetting.json" --output-dir "$COMP_DIR" > "$OUT/composite-$RUN_TAG.txt" 2>&1 ) \
  && { echo "composite book -> $COMP_DIR"; emit_ref "$COMP_DIR" composite-all30 30; } || echo "COMPOSITE FAILED (see $OUT/composite-$RUN_TAG.txt)"
HYB_DIR="$OUT/hybrid15-$RUN_TAG"
( cd "$CLONE" && "$LAB_PY" "$TOOLS/hybrid30.py" "$K90_DIR" --core 15 --k 30 --output-dir "$HYB_DIR" > "$OUT/hybrid15-$RUN_TAG.txt" 2>&1 ) \
  && { echo "hybrid15 -> $HYB_DIR"; emit_ref "$HYB_DIR" hybrid15-all30 30; } || echo "HYBRID15 FAILED (see $OUT/hybrid15-$RUN_TAG.txt)"
# 6. exposure caps (reported, never entered automatically). K = mean rows + sleeve rows: the head layout deals the tail
#    contests ranks BOOK_ENTRIES+1.. (Week-4 smoke 2026-10-01: K = mean rows alone failed "reads rank 106 but the book is 105").  2026-09-22: Week 2 entered a
# player listed Doubtful at build time in 48 of 97 rows including the Millionaire seat; he
# scored 0.0.  A tool that could have bounded that existed but was not in the chain, so it
# runs here.  It re-selects from the SAME pool with the SAME objective at the SAME K, so its
# book is comparable to the delivered one row for row, and it fails closed rather than emit a
# book that breaches a cap.  The operator reads $CAP_DIR/exposure_sheet.md before upload.
CAP_DIR="$OUT/exposure-caps-$RUN_TAG"
( cd "$PROD" && PYTHONPATH="$PROD/src" "$PROD_PY" "$TOOLS/exposure_cap_book.py" "$K90_DIR" \
    --contests "$CONTESTS_JSON" --entries "$((BOOK_ENTRIES + ${TAIL_SLEEVE:-0}))" --layout "${ENTER_LAYOUT:-sequential}" \
    --output-dir "$CAP_DIR" > "$OUT/exposure-caps-$RUN_TAG.txt" 2>&1 ) \
  && { echo "exposure caps -> $CAP_DIR (sheet $CAP_DIR/exposure_sheet.md)"
       grep -m1 "E\[max\]" "$OUT/exposure-caps-$RUN_TAG.txt" || true; } \
  || echo "EXPOSURE CAPS FAILED (see $OUT/exposure-caps-$RUN_TAG.txt) -- check the injury sheet by hand before upload"
# 6b. Refinement 2 PAPER arm (operator 2026-09-24): the same capped re-selection with tighter caps for Questionable
#     QBs and Questionable players whose latest practice was DNP (both play ~50% vs 72% for Questionable overall).
#     Written beside the report above, never entered; scored Monday against the entered book.
CAP2_DIR="$OUT/exposure-caps-r2-$RUN_TAG"
( cd "$PROD" && PYTHONPATH="$PROD/src" "$PROD_PY" "$TOOLS/exposure_cap_book.py" "$K90_DIR" \
    --contests "$CONTESTS_JSON" --entries "$((BOOK_ENTRIES + ${TAIL_SLEEVE:-0}))" --layout "${ENTER_LAYOUT:-sequential}" \
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
