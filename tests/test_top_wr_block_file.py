"""scripts/top_wr_block_file.py: the top-receiver term-block file (offline, synthetic frame)."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location("top_wr_block_file", Path(__file__).resolve().parents[1] / "scripts" / "top_wr_block_file.py")
TW = importlib.util.module_from_spec(spec); spec.loader.exec_module(TW)


def frame():
    # team X: WRs A ($7,800) and B ($6,000); team Y: WRs C and D tied at $7,000 (C projects higher); a cheap RB; a QB; a DST
    rows = [("a", "A", "WR", "X", 7800, 18.0), ("b", "B", "WR", "X", 6000, 15.0), ("c", "C", "WR", "Y", 7000, 16.0),
            ("d", "D", "WR", "Y", 7000, 14.0), ("e", "E", "RB", "X", 3900, 8.0), ("f", "F", "QB", "Y", 6500, 19.0),
            ("g", "G", "DST", "X", 3000, 7.0)]
    df = pd.DataFrame(rows, columns=["id", "display_name", "pos", "team", "salary", "mean_projection"])
    df["dk_player_id"] = range(1, len(df) + 1); df["opp"] = df.team.map({"X": "Y", "Y": "X"})
    return df


def test_each_teams_highest_salaried_wr_only():
    out = TW.build(frame(), 2.0)
    assert list(out.columns) == TW.COLUMNS
    assert dict(zip(out.display_name, out.bonus_points)) == {"A": 2.0, "B": 0.0, "C": 2.0, "D": 0.0, "E": 0.0, "F": 0.0}
    assert "G" not in set(out.display_name)                                       # the DST is omitted
    assert (out.pred_own * TW.TILT).round(6).tolist() == out.bonus_points.tolist()  # tilt 0.20 x pred_own = the bonus


def test_salary_tie_goes_to_the_higher_projection():
    f = frame(); f.loc[f.id == "d", "mean_projection"] = 17.0
    b = dict(zip(*[TW.build(f, 2.0)[c] for c in ("display_name", "bonus_points")]))
    assert b["D"] == 2.0 and b["C"] == 0.0


def test_with_cheap_adds_the_cheap_rule():
    b = dict(zip(*[TW.build(frame(), 2.0, with_cheap=True)[c] for c in ("display_name", "bonus_points")]))
    assert b == {"A": 2.0, "B": 0.0, "C": 2.0, "D": 0.0, "E": 2.0, "F": 0.0}


@pytest.mark.parametrize("mutate, msg", [
    (lambda f: f.drop(columns=["salary"]), "salary"),
    (lambda f: f.assign(dk_player_id=[1, 1, 3, 4, 5, 6, 7]), "duplicated"),
    (lambda f: f.assign(pos="DST"), "no skill players"),
    (lambda f: f[f.pos != "WR"], "no player carries"),
])
def test_refusals(mutate, msg):
    with pytest.raises(ValueError, match=msg):
        TW.build(mutate(frame()), 2.0)


def test_non_positive_points_refused():
    with pytest.raises(ValueError, match="positive"):
        TW.build(frame(), 0.0)


def test_main_is_create_once(tmp_path):
    f = tmp_path / "frame.parquet"; frame().to_parquet(f); out = tmp_path / "topwr2.csv"
    assert TW.main(["--season", "2026", "--week", "5", "--frame", str(f), "--out", str(out)]) == 0
    before = out.read_bytes()
    assert TW.main(["--season", "2026", "--week", "5", "--frame", str(f), "--out", str(out)]) == 3
    assert out.read_bytes() == before


# ---- --base (production's review 10-08): the live cheap file, with ONLY the frame's top receivers flagged
def base_text(points=2.0):
    """A cheap_block_file.py-style base: every frame skill player plus a group-only row (empty id), cheap rows at +POINTS."""
    f = frame()
    sk = f[f.pos != "DST"]
    b = pd.DataFrame({"dk_player_id": list(sk.dk_player_id) + [99], "id": list(sk.id) + [""],
                      "display_name": list(sk.display_name) + ["Late Add"], "pos": list(sk.pos) + ["WR"],
                      "team": list(sk.team) + ["X"], "opp": [""] * (len(sk) + 1)})
    sal = list(sk.salary) + [3500]
    b["bonus_points"] = [points if s < 4000 else 0.0 for s in sal]
    b["pred_own"] = (b.bonus_points / 0.20).round(4)
    import io as _io
    buf = _io.StringIO(); b[TW.COLUMNS].to_csv(buf, index=False)
    return buf.getvalue()


def test_base_flags_only_the_top_receivers_and_keeps_every_other_line():
    text = base_text()
    new, flagged = TW.on_base(text, frame(), 2.0)
    old_lines, new_lines = text.splitlines(), new.splitlines()
    assert len(old_lines) == len(new_lines) and old_lines[0] == new_lines[0]
    changed = [i for i, (a, b) in enumerate(zip(old_lines, new_lines)) if a != b]
    assert [new_lines[i].split(",")[2] for i in changed] == ["A", "C"]          # the two teams' top-salaried WRs only
    assert all(new_lines[i].endswith(",10.0,2.0") for i in changed)             # the base's own bonus strings
    assert "99,,Late Add,WR,X,,10.0,2.0" in new_lines                           # the group-only cheap row is untouched
    assert sorted(flagged) == ["1", "3"]


def test_base_refuses_a_top_receiver_it_lacks():
    text = "\n".join(l for l in base_text().splitlines() if not l.startswith("1,")) + "\n"   # drop A (dk 1)
    with pytest.raises(ValueError, match="not in the base"):
        TW.on_base(text, frame(), 2.0)


def test_base_refuses_other_bonuses():
    with pytest.raises(ValueError, match="not all 0 or POINTS"):
        TW.on_base(base_text(points=4.0), frame(), 2.0)


def test_main_base_end_to_end_and_refusals(tmp_path):
    f = tmp_path / "frame.parquet"; frame().to_parquet(f)
    base = tmp_path / "cheap2.csv"; base.write_text(base_text())
    out = tmp_path / "cheaptopwr2.csv"
    args = ["--season", "2026", "--week", "5", "--frame", str(f), "--base", str(base), "--out", str(out)]
    assert TW.main(args) == 0
    assert TW.main(args) == 3                                                    # create-once
    assert TW.main(args[:-1] + [str(tmp_path / "x.csv"), "--with-cheap"]) == 3    # --base with --with-cheap


# ---- --min-salary (study 70's CHEAPEXPWR2_B8): the top WR is picked first, then floored; no fall-through
def test_min_salary_floor_without_fall_through():
    b = dict(zip(*[TW.build(frame(), 2.0, min_salary=7500)[c] for c in ("display_name", "bonus_points")]))
    assert b["A"] == 2.0                        # team X's top WR, $7,800
    assert b["C"] == 0.0 and b["D"] == 0.0      # team Y's top WR (C, $7,000) is under the floor; D is never promoted
    b = dict(zip(*[TW.build(frame(), 2.0, min_salary=7000)[c] for c in ("display_name", "bonus_points")]))
    assert b["A"] == 2.0 and b["C"] == 2.0 and b["D"] == 0.0


def test_min_salary_with_cheap_keeps_the_cheap_rows():
    b = dict(zip(*[TW.build(frame(), 2.0, with_cheap=True, min_salary=7500)[c] for c in ("display_name", "bonus_points")]))
    assert b == {"A": 2.0, "B": 0.0, "C": 0.0, "D": 0.0, "E": 2.0, "F": 0.0}


def test_min_salary_on_base_flags_only_the_qualifying_top_wr():
    text = base_text()
    new, flagged = TW.on_base(text, frame(), 2.0, min_salary=7500)
    changed = [b.split(",")[2] for a, b in zip(text.splitlines(), new.splitlines()) if a != b]
    assert changed == ["A"] and flagged == ["1"]


def test_min_salary_refusals(tmp_path):
    with pytest.raises(ValueError, match=">= 0"):
        TW.build(frame(), 2.0, min_salary=-1)
    with pytest.raises(ValueError, match="no team's top WR"):
        TW.on_base(base_text(), frame(), 2.0, min_salary=9000)
    f = tmp_path / "frame.parquet"; frame().to_parquet(f)
    assert TW.main(["--season", "2026", "--week", "5", "--frame", str(f), "--min-salary", "-1", "--out", str(tmp_path / "x.csv")]) == 3
