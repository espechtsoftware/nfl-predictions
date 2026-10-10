"""scripts/union_fallbacks.sh: a refused MIX main re-runs as the HOUSE main (--main pmo_x50, the ownership term kept, the
--mix-* flags dropped), loudly; a partial failure or any other refusal never triggers it (reviewer 2026-10-05: exercise
the fallback path itself, not just its message). The real functions run against a stand-in union_reselect."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "scripts" / "union_fallbacks.sh"

HARNESS = r'''
set -uo pipefail
source "$LIB"
OUT="$1"; RUN_TAG=t1; UNION_MAIN="$2"; FIRST_LOG="$3"
CALLS="$OUT/calls.txt"
run_union() {          # the stand-in: refuses a MIX main, writes a union dir line for anything else
  printf '%s\n' "$*" >> "$CALLS"
  if [[ " $* " == *" --main mix "* ]]; then echo "MIX MAIN REFUSED: 90 of 105 rows solved" > "$OUT/union-$RUN_TAG.txt"; return 2; fi
  echo "UNION -> $OUT/union-dir" > "$OUT/union-$RUN_TAG.txt"; return 0
}
UNION_ARGS=(--t70-run R --main "$UNION_MAIN" --mix-plan /w/contests.json --mix-layout head --main-own-tilt 0.2 --main-own-source /w/own.csv)
if [[ "$FIRST_LOG" == "run" ]]; then UNION_RC=0; run_union "${UNION_ARGS[@]}" || UNION_RC=$?
else echo "$FIRST_LOG" > "$OUT/union-$RUN_TAG.txt"; UNION_RC=2; fi
mix_fallback
echo "RC=$UNION_RC EFFECTIVE=$UNION_MAIN_EFFECTIVE"
'''


def _run(tmp_path, main, first="run"):
    r = subprocess.run(["bash", "-c", HARNESS, "harness", str(tmp_path), main, first], env={"LIB": str(LIB), "PATH": "/usr/bin:/bin"},
                       capture_output=True, text=True, timeout=30)
    calls = (tmp_path / "calls.txt").read_text().splitlines() if (tmp_path / "calls.txt").exists() else []
    return r, calls


def test_a_refused_mix_reruns_as_the_house_main_with_the_term_kept(tmp_path):
    r, calls = _run(tmp_path, "mix")
    assert r.returncode == 0, r.stderr
    assert len(calls) == 2
    assert "--main mix" in calls[0] and "--mix-plan /w/contests.json" in calls[0]
    assert calls[1] == "--t70-run R --main pmo_x50 --main-own-tilt 0.2 --main-own-source /w/own.csv"
    assert "MIX REFUSED -> HOUSE MAIN (C) for t1: MIX MAIN REFUSED: 90 of 105 rows solved" in r.stdout
    assert r.stdout.strip().endswith("RC=0 EFFECTIVE=pmo_x50")
    assert (tmp_path / "union-t1-mix-refused.txt").read_text().startswith("MIX MAIN REFUSED")


def test_no_fallback_when_the_main_was_not_mix_or_the_refusal_is_another(tmp_path):
    a = tmp_path / "a"; a.mkdir()
    r, calls = _run(a, "pmo_x50")
    assert len(calls) == 1 and r.stdout.strip().endswith("RC=0 EFFECTIVE=pmo_x50")      # pmo_x50 ran and succeeded: no-op
    b = tmp_path / "b"; b.mkdir()
    r, calls = _run(b, "mix", first="OWN TERM REFUSED: the file is short")
    assert calls == [] and r.stdout.strip().endswith("RC=2 EFFECTIVE=mix")              # not a MIX refusal: untouched


def test_mix_to_house_args_only_rewrites_the_main_value():
    script = f'source "{LIB}"; mix_to_house_args --main mix --mix-plan p --x mix --mix-layout head --mix-portfolio ws --mix-spares 15 --y; printf "%s|" "${{OUT_ARGS[@]}}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert r.stdout == "--main|pmo_x50|--x|mix|--y|"


def test_mix_to_house_args_drops_every_mix_only_flag():
    """2026-10-07: each of these needs --main mix, so the house main refused with any of them aboard (UNION FAILED instead
    of C). The fallback drops them -- the live term block, the quotas, the fill, the cover, the half, winner select and the
    priority order -- and keeps the ownership term and the rest."""
    args = ("--main mix --mix-plan p --mix-layout head --mix-portfolio mix --mix-spares 15 --mix-fill rr "
            "--mix-cell-quotas A1=0.44,A2=0.28,B=0.14,C=0.14 --mix-cover-games 2 --mix-rs-rows 9 --term-block-rows 8 "
            "--term-block-source /w/cheap2-w5.csv --term-block-tilt 0.20 --term-block-cap-points 2.0 "
            "--term-block-min-coverage 0.5 --winner-select /w/win.csv --priority-order --main-qb-cap-rows 5 "
            "--main-own-tilt 0.2 --main-own-source /w/own.csv --winner-order /w/win2.csv --y")
    script = f'source "{LIB}"; mix_to_house_args {args}; printf "%s|" "${{OUT_ARGS[@]}}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert r.stdout == ("--main|pmo_x50|--main-qb-cap-rows|5|--main-own-tilt|0.2|--main-own-source|/w/own.csv|"
                        "--winner-order|/w/win2.csv|--y|")


def test_the_host_sources_the_fallback_before_the_pmo_block():
    host = (ROOT / "scripts" / "sunday_build_host.sh").read_text()
    i_src, i_call = host.index('source "$PROD/scripts/union_fallbacks.sh"'), host.index("\n  mix_fallback ")
    i_pmo = host.index("'PMO_X50 MAIN REFUSED' \"$OUT/union-$RUN_TAG.txt\"")
    assert i_src < i_call < i_pmo
    assert '[[ "${UNION_MAIN:-mean}" == "mix" ]] && UNION_ARGS+=(--mix-plan "$CONTESTS_JSON" --mix-layout "${ENTER_LAYOUT:-head}" --mix-portfolio "${UNION_MIX_PORTFOLIO:?UNION_MAIN=mix needs UNION_MIX_PORTFOLIO=mix|ws}" --mix-spares "${UNION_MIX_SPARES:-15}")' in host
    assert '( "${UNION_MAIN:-mean}" == "pmo_x50" || "${UNION_MAIN:-mean}" == "mix" ) && "${UNION_MAIN_OWN_TILT:-0}" != "0"' in host


def test_a_house_fallback_of_his_package_drops_the_ownership_cap_and_restores_the_player_cap():
    """His 10-09 package (HANDOFF 5380e0e7): the ownership cap's flags are MIX-only, and the flat 35% never runs alone, so a
    house fallback of a package run drops them AND sets the player cap back to the package's fallback share, in place."""
    args = ("--main mix --main-cap-share 0.35 --mix-fill rr --main-own-cap-delta 15 --main-own-cap-source /w/own_fp.csv "
            "--main-own-cap-fallback-share 0.5 --main-own-cap-min-coverage 0.9 --main-dst-cap 0.25 --y")
    script = f'source "{LIB}"; mix_to_house_args {args}; printf "%s|" "${{OUT_ARGS[@]}}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert r.stdout == "--main|pmo_x50|--main-cap-share|0.5|--main-dst-cap|0.25|--y|"
    # without the package nothing about the player cap changes
    script = f'source "{LIB}"; mix_to_house_args --main mix --main-cap-share 0.5 --y; printf "%s|" "${{OUT_ARGS[@]}}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert r.stdout == "--main|pmo_x50|--main-cap-share|0.5|--y|"
    # a package run that named no --main-cap-share still gets the fallback share
    script = f'source "{LIB}"; mix_to_house_args --main mix --main-own-cap-delta 15 --main-own-cap-source s --y; printf "%s|" "${{OUT_ARGS[@]}}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert r.stdout == "--main|pmo_x50|--y|--main-cap-share|0.5|"


def test_a_house_fallback_drops_his_test2_row_rules():
    """His 10-09 test 2: the row rules are MIX-only, so the house fallback drops them (with the package's flags)."""
    args = ("--main mix --main-cap-share 0.35 --main-own-cap-delta 15 --main-own-cap-source s --main-own-cap-fallback-share 0.5 "
            "--mix-max-te 1 --mix-max-low-own 1 --mix-low-own-pct 3 --y")
    script = f'source "{LIB}"; mix_to_house_args {args}; printf "%s|" "${{OUT_ARGS[@]}}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert r.stdout == "--main|pmo_x50|--main-cap-share|0.5|--y|"


def test_a_house_fallback_drops_the_one_catcher_flag():
    """Study 93's ONECATCH (his 10-09 'Live W5 if built in time'): MIX-only and valueless, so the house fallback drops the bare
    flag with the row rules and keeps the next argument."""
    args = ("--main mix --main-cap-share 0.35 --main-own-cap-delta 15 --main-own-cap-source s --main-own-cap-fallback-share 0.5 "
            "--mix-max-te 1 --mix-max-low-own 1 --mix-low-own-pct 3 --mix-one-catcher-all --y")
    script = f'source "{LIB}"; mix_to_house_args {args}; printf "%s|" "${{OUT_ARGS[@]}}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert r.stdout == "--main|pmo_x50|--main-cap-share|0.5|--y|"


def test_a_house_fallback_drops_the_rb_mate_flag_and_its_value():
    """Study 96's RB mate (his 10-09 'Try live W5 if built'): MIX-only, so the house fallback drops --mix-rb-mate-c AND its
    value, with ONECATCH and the row rules."""
    args = ("--main mix --main-cap-share 0.35 --main-own-cap-delta 15 --main-own-cap-source s --main-own-cap-fallback-share 0.5 "
            "--mix-max-te 1 --mix-max-low-own 1 --mix-low-own-pct 3 --mix-one-catcher-all --mix-rb-mate-c 4 --y")
    script = f'source "{LIB}"; mix_to_house_args {args}; printf "%s|" "${{OUT_ARGS[@]}}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert r.stdout == "--main|pmo_x50|--main-cap-share|0.5|--y|"


def test_a_house_fallback_drops_the_a1_full_stack_flag():
    """Study 102's full game stack (10-10): MIX-only and valueless, so the house fallback drops the bare flag with ONECATCH and
    the row rules and keeps the next argument."""
    args = ("--main mix --main-cap-share 0.35 --main-own-cap-delta 15 --main-own-cap-source s --main-own-cap-fallback-share 0.5 "
            "--mix-max-te 1 --mix-max-low-own 1 --mix-low-own-pct 3 --mix-one-catcher-all --mix-a1-full-stack --y")
    script = f'source "{LIB}"; mix_to_house_args {args}; printf "%s|" "${{OUT_ARGS[@]}}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert r.stdout == "--main|pmo_x50|--main-cap-share|0.5|--y|"
