"""Study 116's RB receptions floor on the live MIX book (the operator 10-10: "Let's try another experiment where we have a minimum
number of receptions for a running back"; live only if 116 and its re-check pass): union_reselect's receptions-file loader (the
format agreed with the lab reviewer 10-10, written by reports/2026-10-10-rb-receptions/rb_rec_file.py), its refusals, the
generator's window, the survivors() drop, the CLI refusals and the wiring (the host, the house fallback, the timers, the
runtime check, the arm and study 38's snapshot). The pool effect is checked live by the W4 ON build."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import union_reselect as ur  # noqa: E402

META = {"season": 2026, "week": 5, "games": 4, "source": "test", "generated_utc": "2026-10-10T00:00:00Z"}
COLS = "gsis_id,rec_games,rec_sum,rec_per_game"
ROWS = ["g1,4,4.0,1.0",          # 1.0: below 1.5 and 2.0
        "g2,4,6.0,1.5",          # 1.5: stays at 1.5 (strict), leaves at 2.0
        "g3,2,4.0,2.0",          # 2.0: stays at both (strict)
        "g4,3,10.0,3.3333333333333335",
        "g5,1,0.0,0.0",          # a WR at 0: never touched (RBs only)
        "g9,4,2.0,0.5"]          # not in the frame


def _write(tmp_path, meta=META, rows=ROWS, name="w05.csv", header=True):
    p = tmp_path / name
    lines = ([f"# {json.dumps(meta)}"] if header else []) + [COLS] + list(rows)
    p.write_text("\n".join(lines) + "\n")
    return p


def _frame(week=5, season=2026):
    return pd.DataFrame({"id": ["f1", "f2", "f3", "f4", "f5", "f6", "f7"],
                         "gsis_id": ["g1", "g2", "g3", "g4", "g5", "g6", None],
                         "dk_player_id": [101.0, 102, 103, 104, 105, 106, 107],
                         "pos": ["RB", "RB", "RB", "RB", "WR", "RB", "RB"], "week": week, "season": season})


def test_the_floor_drops_rbs_strictly_below_it_and_keeps_rbs_without_a_game(tmp_path):
    low, meta = ur.rb_rec_low_ids(_write(tmp_path), _frame(), 2.0)
    assert low == {"f1", "f2"}                                        # g3 at exactly 2.0 stays; g5 is a WR
    assert meta["applied"] and meta["threshold"] == 2.0 and meta["file_rows"] == 6 and meta["pool_rbs"] == 6
    assert meta["kept_no_prior"] == 2                                 # f6 (no game in the file) and f7 (no gsis_id)
    assert meta["dropped_ids"] == ["f1", "f2"] and meta["dropped_dk_ids"] == ["101", "102"] and len(meta["sha256"]) == 64
    assert (meta["season"], meta["week"]) == (2026, 5)
    low, meta = ur.rb_rec_low_ids(_write(tmp_path), _frame(), 1.5)
    assert low == {"f1"} and meta["dropped_dk_ids"] == ["101"]        # g2 at exactly 1.5 stays


@pytest.mark.parametrize("case", ["missing", "no_meta", "not_json", "games", "week", "season", "column", "no_rows", "nan",
                                  "repeat", "rec_games", "ratio"])
def test_the_loader_refuses_a_bad_file(tmp_path, case):
    rows, meta, header = list(ROWS), dict(META), True
    if case == "no_meta":
        header = False
    elif case == "games":
        meta["games"] = 3
    elif case == "week":
        meta["week"] = 4
    elif case == "season":
        meta["season"] = 2025
    elif case == "no_rows":
        rows = []
    elif case == "nan":
        rows[0] = "g1,4,nan,1.0"
    elif case == "repeat":
        rows.append("g1,4,8.0,2.0")
    elif case == "rec_games":
        rows[0] = "g1,5,5.0,1.0"
    elif case == "ratio":
        rows[0] = "g1,4,4.0,1.1"
    p = tmp_path / "none.csv" if case == "missing" else _write(tmp_path, meta, rows, header=header)
    if case == "column":
        p.write_text(p.read_text().replace(",rec_sum,", ",receptions,"))
    if case == "not_json":
        p.write_text("# {season: 2026}\n" + "\n".join([COLS] + rows) + "\n")
    with pytest.raises(SystemExit, match="RB REC FLOOR REFUSED"):
        ur.rb_rec_low_ids(p, _frame(), 2.0)


def test_survivors_drop_a_supply_roster_holding_a_floored_rb():
    t70 = pd.DataFrame({"id": ["q", "r1", "r2", "w"], "pos": ["QB", "RB", "RB", "WR"], "mean_projection": [20.0, 10.0, 10.0, 10.0],
                        "game_id": ["a", "a", "b", "b"], "dk_player_id": [1, 2, 3, 4]})
    cands = pd.DataFrame({"players": ["q,r1,w", "q,r2,w"], "tag": ["x", "y"]})
    rosters, idx, counts = ur.survivors(cands, t70, set(), 1.0, None, None, {"r1"})
    assert rosters == [["q", "r2", "w"]] and idx == [1] and counts["dropped_below_rb_rec"] == 1
    rosters, idx, counts = ur.survivors(cands, t70, set(), 1.0, None, None)          # off by default: nothing dropped
    assert len(rosters) == 2 and "dropped_below_rb_rec" not in counts


def test_the_generator_window_is_the_last_four_stat_line_games():
    spec = importlib.util.spec_from_file_location("rb_rec_file", ROOT / "reports" / "2026-10-10-rb-receptions" / "rb_rec_file.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    w = pd.DataFrame({"gsis_id": ["a"] * 5 + ["b"], "week": [1, 2, 3, 4, 6, 2], "receptions": [9.0, 1.0, 2.0, 3.0, 4.0, 0.0]})
    g = gen.window(w).set_index("gsis_id")
    assert g.loc["a"].tolist() == [4, 10.0, 2.5] and g.loc["b"].tolist() == [1, 0.0, 0.0]     # week 1's 9 falls out of a's window
    with pytest.raises(SystemExit, match="repeated"):
        gen.window(pd.concat([w, w.iloc[:1]]))


def test_the_cli_refuses_a_dose_it_did_not_test_and_a_file_without_the_floor():
    base = ["--saturday-run", "x", "--t70-run", "y", "--live-dir", "z", "--entries", "26", "--main", "mix"]
    for extra in (["--mix-min-rb-rec", "2.5", "--mix-rb-rec-source", "r.csv"],     # not a tested dose
                  ["--mix-min-rb-rec", "2.0"]):                                    # no file
        with pytest.raises(SystemExit, match="--mix-min-rb-rec"):
            ur.main(base + extra)
    with pytest.raises(SystemExit, match="--mix-min-rb-rec"):                       # MIX main only
        ur.main(["--saturday-run", "x", "--t70-run", "y", "--live-dir", "z", "--entries", "26", "--main", "mean",
                 "--mix-min-rb-rec", "2.0", "--mix-rb-rec-source", "r.csv"])
    with pytest.raises(SystemExit, match="--mix-rb-rec-source is read only"):
        ur.main(base + ["--mix-rb-rec-source", "r.csv"])
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert "!!! RB REC FLOOR NOT APPLIED" in src
    assert src.count("(proj_all[i] >= a.min_proj)} | rb_rec_low\n") == 2 and "(proj_f[i] >= a.min_proj)} | rb_rec_low\n" in src
    assert src.count(", a.min_proj, cap, dk, rb_rec_low)") == 2
    assert 'mix_meta["rb_rec_floor_source"]' in src and 'mix_meta["rb_rec_floor"]' in src


def test_a_house_fallback_drops_both_floor_flags_and_their_values():
    lib = ROOT / "scripts" / "union_fallbacks.sh"
    args = ("--main mix --main-cap-share 0.35 --main-own-cap-delta 15 --main-own-cap-source s --main-own-cap-fallback-share 0.5 "
            "--mix-max-te 1 --mix-max-low-own 1 --mix-low-own-pct 3 --mix-min-rb-rec 2.0 --mix-rb-rec-source r.csv --y")
    script = f'source "{lib}"; mix_to_house_args {args}; printf "%s|" "${{OUT_ARGS[@]}}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert r.stdout == "--main|pmo_x50|--main-cap-share|0.5|--y|"


def test_the_host_the_timers_the_runtime_check_the_arm_and_the_snapshot_carry_it():
    root = ROOT / "scripts"
    host = (root / "sunday_build_host.sh").read_text()
    assert ('      UNION_ARGS+=(--mix-min-rb-rec "$UNION_MIX_MIN_RB_REC" --mix-rb-rec-source "$UNION_MIX_RB_REC_SOURCE"); '
            'RB_REC_ON=1') in host
    assert "grep -q 'RB REC FLOOR NOT APPLIED'" in host and '"$UNION_DIR/rb_rec_floor_not_applied.txt"' in host
    assert host.index("UNION_ARGS+=(--mix-min-rb-rec") < host.index('UNION_RC=0; run_union "${UNION_ARGS[@]}"')
    timers = (root / "arm_week_timers.sh").read_text()
    assert " UNION_MIX_MIN_RB_REC UNION_MIX_RB_REC_SOURCE " in timers
    check = (root / "check_week_runtime.py").read_text()
    assert 'os.environ.get("UNION_MIX_MIN_RB_REC", "")' in check and 'os.environ.get("UNION_MIX_RB_REC_SOURCE", "")' in check
    arm = (root / "arm_week5_saturday.sh").read_text()
    assert '\nRB_REC_MIN="" ' in arm or '\nRB_REC_MIN="2.0" ' in arm or '\nRB_REC_MIN="1.5" ' in arm
    assert '"$RB_REC_MIN" =~ ^(1\\.5|2\\.0)$ && "$SHAPE" == mixt && "$RB_REC_SHA" =~ ^[0-9a-f]{64}$' in arm
    assert '[[ -z "$RB_REC_MIN" || "$RB_REC_FILE" == "$HOME/private/paper-corun/rbrec/w05.csv" ]]' in arm
    assert ("e+=(UNION_MIX_MIN_RB_REC=$RB_REC_MIN UNION_MIX_RB_REC_SOURCE=$RB_REC_FILE); "
            "else u+=(-u UNION_MIX_MIN_RB_REC -u UNION_MIX_RB_REC_SOURCE)") in arm
    snap = (root / "s38_snapshot.sh").read_text()
    assert 'PREC=${S38_RB_REC_FILE:-}' in snap and 'cp -p "$PREC" "$DEST/rb-rec-$(basename "$PREC")"' in snap
    assert 'SRC["rb-rec-$(basename "$PREC")"]="$PREC"' in snap
