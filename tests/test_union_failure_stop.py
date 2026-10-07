"""The outside review 10-07, H1 / M5 / the grep LOW: a failed union under the week's settings is a STOP with a banner, the
watcher puts the STOP on TODAY, and the ownership-term retry no longer fires on a term-block refusal."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = (ROOT / "scripts" / "sunday_build_host.sh").read_text()
AFTER = (ROOT / "scripts" / "sunday_after_build.sh").read_text()


def _union_fail_src() -> str:
    m = re.search(r"^union_fail\(\) \{\n.*?^\}\n", HOST, re.S | re.M)
    assert m, "union_fail() not found in the host"
    return m.group(0)


def _call(tmp_path, **env):
    k90 = tmp_path / "k90"; k90.mkdir(exist_ok=True); out = tmp_path / "out"; out.mkdir(exist_ok=True)
    script = _union_fail_src() + f'K90_DIR="{k90}"; OUT="{out}"; RUN_TAG=t1\nunion_fail "the union build audit failed"\n'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30,
                       env={"PATH": "/usr/bin:/bin", **env})
    return r, k90, out


def test_every_union_failure_exit_goes_through_union_fail():
    assert HOST.count('touch "$K90_DIR/union_failed"') == 1                 # only inside union_fail()
    assert len(re.findall(r'union_fail "[^"]+"; (?:rm -rf "\$UNION_DIR"; )?exit 1', HOST)) == 5


def test_under_mix_or_a_term_block_the_failure_is_a_stop_with_a_banner(tmp_path):
    r, k90, out = _call(tmp_path, UNION_MAIN="mix", UNION_TERM_BLOCK_ROWS="8")
    assert r.returncode == 0 and (k90 / "union_failed").is_file() and (k90 / "union_required").is_file()
    assert "UNION FAILED (the union build audit failed) under UNION_MAIN=mix, term block 8 rows" in (k90 / "union_required").read_text()
    assert (out / "ALERT-union-failed-t1.txt").is_file() and "!!! UNION FAILED for t1" in r.stdout
    (tmp_path / "b").mkdir()
    r, k90, _ = _call(tmp_path / "b", UNION_MAIN="mean", UNION_TERM_BLOCK_ROWS="0")
    assert (k90 / "union_failed").is_file() and not (k90 / "union_required").exists()   # a house week keeps the fallback


def test_the_ownership_term_retry_is_anchored():
    assert "grep -q 'OWN TERM REFUSED'" not in HOST and "grep 'OWN TERM REFUSED'" not in HOST
    assert HOST.count("'^OWN TERM REFUSED'") == 4
    log = "\n!!! TERM BLOCK NOT APPLIED: SystemExit: OWN TERM REFUSED: x -- the book is built without it\nMIX MAIN REFUSED: y\n"
    assert not re.search(r"^OWN TERM REFUSED", log, re.M)                      # the term block's line does not trigger it
    assert re.search(r"^OWN TERM REFUSED", "OWN TERM REFUSED: the file is short\n", re.M)


def test_the_watcher_passes_the_override_and_puts_a_stop_on_today():
    assert '$( [[ "${UNION_FAILED_OK:-0}" == "1" ]] && echo --accept-union-failed )' in AFTER
    assert '[[ "$why" == term_block_missing:* || "$why" == union_required:* ]]' in AFTER
    assert '>> "$OUT/TODAY-30-LATEST.md"' in AFTER and 'after_build.stops' in AFTER
    timers = (ROOT / "scripts" / "arm_week_timers.sh").read_text()
    assert " UNION_FAILED_OK " in timers
