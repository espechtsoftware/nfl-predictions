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
