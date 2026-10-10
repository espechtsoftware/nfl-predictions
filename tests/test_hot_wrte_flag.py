"""Study 115's HOT_WRTE1 on the live MIX book (the operator 10-10, "Test today for this week"): union_reselect's hot-flag
loader (study 38 amendment 6y's paper-hot format, written by reports/2026-10-10-paper-hot/paper_hot_flags.py; study 109's
frozen flag = study 65's last_game() at 2.0x, masked to WR / TE), its refusals, its CLI refusals, and its wiring (the host,
the house fallback, the timers and the arm). The rule itself is one more member bound in the row-rule tier (the same
mix_rows machinery study 91's te1 / low1 use), checked live by the W4 ON build."""
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import union_reselect as ur  # noqa: E402

META = {"what": "hot flags (study 109's HOT1)", "x": 2.0, "floor": 5.0, "min_prior": 2, "prior_games": 4, "season": 2026,
        "week": 5, "source": "test", "points": "DK points", "generated_utc": "2026-10-10T00:00:00Z"}
COLS = "dk_player_id,gsis_id,name,pos,last_week,last_pts,prior_mean,prior_n,hot"
ROWS = ["101,g1,W Hot,WR,4,30.0,10.0,4,1",       # 30 >= 2 x 10: hot
        "102,g2,T Hot,TE,4,10.0,4.0,3,1",        # 10 >= 2 x max(4, 5): hot
        "103,g3,R Hot,RB,4,40.0,10.0,4,1",       # hot, but an RB: never in HOT_WRTE1
        "104,g4,Q Hot,QB,4,50.0,20.0,4,1",       # hot, but a QB
        "105,g5,W Cold,WR,4,12.0,10.0,4,0",
        "106,g6,W Few,WR,4,30.0,0.0,1,0"]        # one prior game: never hot


def _write(tmp_path, meta=META, rows=ROWS, name="w05.csv", header=True):
    p = tmp_path / name
    lines = ([f"# {json.dumps(meta)}"] if header else []) + [COLS] + list(rows)
    p.write_text("\n".join(lines) + "\n")
    return p


def _frame(week=5):
    return pd.DataFrame({"id": ["f1", "f2", "f3", "f4", "f5", "f6", "f7"],
                         "dk_player_id": [101.0, 102, 103, 104, 105, 106, 107],      # a float id must match ("101.0" -> "101")
                         "pos": ["WR", "TE", "RB", "QB", "WR", "WR", "WR"], "week": week})


def test_the_ids_are_the_pools_hot_wr_and_te_only(tmp_path):
    ids, dk_ids, meta = ur.hot_wrte_ids(_write(tmp_path), _frame(), set())
    assert ids == {"f1", "f2"} and dk_ids == ["101", "102"]
    assert meta["file_rows"] == 6 and meta["file_hot"] == 4 and meta["week"] == 5 and len(meta["sha256"]) == 64
    assert meta["rule"] == {"x": 2.0, "floor": 5.0, "min_prior": 2, "prior_games": 4}
    ids, dk_ids, _ = ur.hot_wrte_ids(_write(tmp_path), _frame(), {"f2"})      # an excluded player is not in the pool
    assert ids == {"f1"} and dk_ids == ["101"]
    ids, dk_ids, _ = ur.hot_wrte_ids(_write(tmp_path, rows=ROWS[2:]), _frame(), set())   # no hot WR / TE: vacuous, not refused
    assert ids == set() and dk_ids == []


@pytest.mark.parametrize("case", ["missing", "no_meta", "x", "week", "flipped", "dst", "repeat", "nan", "column"])
def test_the_loader_refuses_a_bad_file(tmp_path, case):
    rows, meta, header = list(ROWS), dict(META), True
    if case == "no_meta":
        header = False
    elif case == "x":
        meta["x"] = 1.6
    elif case == "week":
        meta["week"] = 4
    elif case == "flipped":
        rows[4] = "105,g5,W Cold,WR,4,12.0,10.0,4,1"                         # 12 < 2 x 10: hot disagrees with its numbers
    elif case == "dst":
        rows.append("107,g7,D,DST,4,30.0,5.0,4,1")
    elif case == "repeat":
        rows.append("101,g9,W Twin,WR,4,0.0,0.0,0,0")
    elif case == "nan":
        rows[4] = "105,g5,W Cold,WR,4,nan,10.0,4,0"
    p = tmp_path / "none.csv" if case == "missing" else _write(tmp_path, meta, rows, header=header)
    if case == "column":
        p.write_text(p.read_text().replace(",prior_n,", ",n_prior,"))
    with pytest.raises(SystemExit, match="HOT WR/TE REFUSED"):
        ur.hot_wrte_ids(p, _frame(), set())


def test_the_cli_refuses_it_without_the_file_or_the_row_rules():
    base = ["--saturday-run", "x", "--t70-run", "y", "--live-dir", "z", "--entries", "26", "--main", "mix"]
    own = ["--main-own-cap-delta", "15", "--main-own-cap-source", "f.csv", "--main-own-cap-fallback-share", "0.5"]
    rows = ["--mix-portfolio", "mix", "--mix-fill", "rr", "--mix-max-te", "1", "--mix-max-low-own", "1"]
    for extra in (own + rows + ["--mix-max-hot-wrte", "1"],                              # no file
                  own + ["--mix-max-hot-wrte", "1", "--mix-hot-source", "h.csv"],           # no row rules
                  own + rows + ["--mix-max-hot-wrte", "2", "--mix-hot-source", "h.csv"]):   # not the tested value
        with pytest.raises(SystemExit, match="--mix-max-hot-wrte takes 0"):
            ur.main(base + extra)
    for extra in (own + rows + ["--mix-hot-source", "h.csv"], own + rows + ["--mix-max-hot-wrte", "0", "--mix-hot-source", "h.csv"]):
        with pytest.raises(SystemExit, match="--mix-hot-source is read only by --mix-max-hot-wrte"):
            ur.main(base + extra)
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert "!!! HOT WR/TE NOT APPLIED" in src and '"the row rules are not applied"' in src
    assert 'mix_meta["hot_wrte_source"] = hot_meta' in src and "row_bounds = row_bounds + [(hot_ids, 0, a.mix_max_hot_wrte)]" in src
    assert 'mix_meta["hot_wrte"] = {"max_per_row": a.mix_max_hot_wrte, "positions": list(HOT_WRTE_POS), "dk_ids": hot_dk_ids,' in src


def test_a_house_fallback_drops_both_hot_flags_and_their_values():
    lib = ROOT / "scripts" / "union_fallbacks.sh"
    args = ("--main mix --main-cap-share 0.35 --main-own-cap-delta 15 --main-own-cap-source s --main-own-cap-fallback-share 0.5 "
            "--mix-max-te 1 --mix-max-low-own 1 --mix-low-own-pct 3 --mix-max-hot-wrte 1 --mix-hot-source h.csv --y")
    script = f'source "{lib}"; mix_to_house_args {args}; printf "%s|" "${{OUT_ARGS[@]}}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert r.stdout == "--main|pmo_x50|--main-cap-share|0.5|--y|"


def test_the_host_the_timers_and_the_arm_carry_it_only_on_the_row_rules():
    root = ROOT / "scripts"
    host = (root / "sunday_build_host.sh").read_text()
    assert ('    if (( ROW_RULES_ON )) && [[ -s "${UNION_MIX_HOT_SOURCE:-}" ]]; then\n'
            '      UNION_ARGS+=(--mix-max-hot-wrte 1 --mix-hot-source "$UNION_MIX_HOT_SOURCE"); HOT_WRTE_ON=1') in host
    assert 'hot_wrte_alert "the row rules are not on for this run' in host and "grep -q 'HOT WR/TE NOT APPLIED'" in host
    assert '"$UNION_DIR/hot_wrte_not_applied.txt"' in host
    assert host.index("ROW_RULES_ON=1") < host.index("UNION_ARGS+=(--mix-max-hot-wrte 1") < host.index('UNION_RC=0; run_union "${UNION_ARGS[@]}"')
    timers = (root / "arm_week_timers.sh").read_text()
    assert " UNION_MIX_HOT_WRTE_MAX UNION_MIX_HOT_SOURCE " in timers
    arm = (root / "arm_week5_saturday.sh").read_text()
    assert '\nHOT_WRTE_MAX="" ' in arm or '\nHOT_WRTE_MAX="1" ' in arm                    # off, or his yes at the arm
    assert '"$HOT_WRTE_MAX" == 1 && "$ROW_RULES" == te1_low1 && "$HOT_SHA" =~ ^[0-9a-f]{64}$' in arm
    assert "e+=(UNION_MIX_HOT_WRTE_MAX=$HOT_WRTE_MAX UNION_MIX_HOT_SOURCE=$HOT_FILE); else u+=(-u UNION_MIX_HOT_WRTE_MAX -u UNION_MIX_HOT_SOURCE)" in arm
