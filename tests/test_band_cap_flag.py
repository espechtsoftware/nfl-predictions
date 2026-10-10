"""The band cap (the operator 10-10: "at most ONE RB/WR/TE with salary in [5300, 6000] per row"): union_reselect's band set and
its CLI refusals, and the wiring (the host, the house fallback, the timers, the runtime check and the arm, with the operator's
pinned exclusion file). The rule itself is one more member bound in the row-rule tier (the mix_rows machinery study 91's te1 / low1
use), checked live by the W4 ON build."""
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import union_reselect as ur  # noqa: E402


def _frame():
    return pd.DataFrame({"id": ["r1", "w1", "t1", "w2", "q1", "w3", "r2"],
                         "pos": ["RB", "WR", "TE", "WR", "QB", "WR", "RB"],
                         "salary": [5300, 6000, 5500, 6100, 5600, 5299, 5800]})


def test_the_band_set_is_inclusive_rb_wr_te_and_after_the_exclusions():
    assert ur.band_ids(_frame(), set(), 5300, 6000) == {"r1", "w1", "t1", "r2"}    # 5300 and 6000 in; 6100 / 5299 out; QB never
    assert ur.band_ids(_frame(), {"r2"}, 5300, 6000) == {"r1", "w1", "t1"}         # an excluded player is not in the pool
    assert ur.band_ids(_frame(), set(), 7000, 8000) == set()                      # vacuous, not refused


@pytest.mark.parametrize("spec", ["5300-6000", "6000:5300", "500:600", "5300:30000", "a:b", None])
def test_a_bad_band_is_refused(spec):
    with pytest.raises(SystemExit, match="--mix-band"):
        ur.parse_band(spec)


def test_the_cli_refuses_the_cap_without_its_band_or_the_row_rules():
    base = ["--saturday-run", "x", "--t70-run", "y", "--live-dir", "z", "--entries", "26", "--main", "mix"]
    own = ["--main-own-cap-delta", "15", "--main-own-cap-source", "f.csv", "--main-own-cap-fallback-share", "0.5"]
    rows = ["--mix-portfolio", "mix", "--mix-fill", "rr", "--mix-max-te", "1", "--mix-max-low-own", "1"]
    for extra in (own + rows + ["--mix-max-band", "1"],                            # no band
                  own + ["--mix-max-band", "1", "--mix-band", "5300:6000"],           # no row rules
                  own + rows + ["--mix-max-band", "2", "--mix-band", "5300:6000"]):   # not 0 / 1
        with pytest.raises(SystemExit, match="--mix-max-band takes 0"):
            ur.main(base + extra)
    with pytest.raises(SystemExit, match="--mix-band is read only"):
        ur.main(base + own + rows + ["--mix-band", "5300:6000"])
    with pytest.raises(SystemExit, match="--mix-band"):
        ur.main(base + own + rows + ["--mix-max-band", "1", "--mix-band", "6000:5300"])
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert "!!! BAND CAP NOT APPLIED" in src and "row_bounds = row_bounds + [(band_set, 0, int(a.mix_max_band))]" in src
    assert 'mix_meta["band_cap_source"] = dict(band_meta)' in src and '"ids": sorted(band_set)' in src


def test_a_house_fallback_drops_both_band_flags_and_their_values():
    lib = ROOT / "scripts" / "union_fallbacks.sh"
    args = ("--main mix --main-cap-share 0.35 --main-own-cap-delta 15 --main-own-cap-source s --main-own-cap-fallback-share 0.5 "
            "--mix-max-te 1 --mix-max-low-own 1 --mix-low-own-pct 3 --mix-max-band 1 --mix-band 5300:6000 --y")
    script = f'source "{lib}"; mix_to_house_args {args}; printf "%s|" "${{OUT_ARGS[@]}}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert r.stdout == "--main|pmo_x50|--main-cap-share|0.5|--y|"


def test_the_host_the_timers_the_runtime_check_and_the_arm_carry_it():
    root = ROOT / "scripts"
    host = (root / "sunday_build_host.sh").read_text()
    assert 'UNION_ARGS+=(--mix-max-band 1 --mix-band "$UNION_MIX_BAND"); BAND_ON=1' in host
    assert "grep -q 'BAND CAP NOT APPLIED'" in host and '"$UNION_DIR/band_cap_not_applied.txt"' in host
    assert host.index("ROW_RULES_ON=1") < host.index("UNION_ARGS+=(--mix-max-band 1") < host.index('UNION_RC=0; run_union "${UNION_ARGS[@]}"')
    timers = (root / "arm_week_timers.sh").read_text()
    assert " UNION_MIX_MAX_BAND UNION_MIX_BAND " in timers and " UNION_DK_STATUS" in timers
    check = (root / "check_week_runtime.py").read_text()
    assert 'os.environ.get("UNION_MIX_MAX_BAND", "")' in check and 'os.environ.get("UNION_MIX_BAND", "")' in check
    arm = (root / "arm_week5_saturday.sh").read_text()
    assert ('if [[ -n "$DK_STATUS_FILE" ]]; then e+=(UNION_DK_STATUS=$DK_STATUS_FILE); else u+=(-u UNION_DK_STATUS); fi') in arm
    assert ('if [[ -n "$MAX_BAND" ]]; then e+=(UNION_MIX_MAX_BAND=$MAX_BAND UNION_MIX_BAND=$BAND); '
            'else u+=(-u UNION_MIX_MAX_BAND -u UNION_MIX_BAND); fi') in arm
    assert '"$DK_STATUS_FILE" == "$HOME/week5-sunday/dk-status-w05.csv" && "$DK_STATUS_SHA" =~ ^[0-9a-f]{64}$' in arm
    assert '"$MAX_BAND" == 1 && "$BAND" =~ ^[0-9]{4,5}:[0-9]{4,5}$ && "$ROW_RULES" == te1_low1' in arm
