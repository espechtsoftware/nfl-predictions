"""scripts/cheap_block_file.py: the cheap-player term-block file (offline, synthetic frame)."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location("cheap_block_file", Path(__file__).resolve().parents[1] / "scripts" / "cheap_block_file.py")
CB = importlib.util.module_from_spec(spec); spec.loader.exec_module(CB)


def frame():
    return pd.DataFrame({"dk_player_id": [1, 2, 3, 4, 5, 6], "id": ["a", "b", "c", "d", "e", "BUF_DST"],
                         "display_name": list("ABCDEF"), "pos": ["QB", "RB", "WR", "TE", "WR", "DST"],
                         "team": ["X"] * 6, "opp": ["Y"] * 6, "salary": [6000, 3900, 4000, 3000, 3999, 2500]})


def test_bonus_only_under_4000_and_no_dst():
    out = CB.build(frame(), 2.0)
    assert list(out.columns) == CB.COLUMNS
    assert dict(zip(out.display_name, out.bonus_points)) == {"A": 0.0, "B": 2.0, "C": 0.0, "D": 2.0, "E": 2.0}
    assert "F" not in set(out.display_name)                            # the DST is omitted
    assert (out.pred_own * CB.TILT).round(6).tolist() == out.bonus_points.tolist()   # tilt 0.20 x pred_own = the bonus


def test_points_scale_the_bonus():
    assert CB.build(frame(), 4.0).bonus_points.max() == 4.0


@pytest.mark.parametrize("mutate, msg", [
    (lambda f: f.assign(pos="DST"), "no skill players"),
    (lambda f: f.assign(dk_player_id=[1, 1, 3, 4, 5, 6]), "duplicated"),
    (lambda f: f.assign(dk_player_id=[None, 2, 3, 4, 5, 6]), "no dk_player_id"),
    (lambda f: f.assign(salary=5000), "no player carries"),
])
def test_refusals(mutate, msg):
    with pytest.raises(ValueError, match=msg):
        CB.build(mutate(frame()), 2.0)


def test_non_positive_points_refused():
    with pytest.raises(ValueError, match="positive"):
        CB.build(frame(), 0.0)


def pull():
    return pd.DataFrame({"pulled_at": ["2026-10-04T15:33:00Z"] * 5, "dk_player_id": [1, 2, 3, 7, 6],
                         "display_name": ["A", "B", "C", "G", "F"], "team_abbr": ["X"] * 5,
                         "position": ["QB", "RB", "WR", "TE", "DST"], "salary": [6000, 3900, 4000, 3200, 2500]})


def test_frame_from_dk_pull_feeds_build():
    out = CB.build(CB.frame_from_dk_pull(pull()), 2.0)
    assert list(out.columns) == CB.COLUMNS
    assert dict(zip(out.display_name, out.bonus_points)) == {"A": 0.0, "B": 2.0, "C": 0.0, "G": 2.0}   # the DST omitted
    assert set(out["id"]) == {""} and set(out["opp"]) == {""}            # the union matches on dk_player_id


def test_the_pull_keeps_a_player_the_frame_lacks():
    from_frame = set(CB.build(frame(), 2.0).dk_player_id)
    from_pull = set(CB.build(CB.frame_from_dk_pull(pull()), 2.0).dk_player_id)
    assert 7 in from_pull and 7 not in from_frame                       # a late addition still has his row


def test_two_pulls_refused():
    p = pull(); p.loc[0, "pulled_at"] = "2026-10-04T09:00:00Z"
    with pytest.raises(ValueError, match="2 pulls"):
        CB.frame_from_dk_pull(p)


def test_main_is_create_once(tmp_path):
    f = tmp_path / "frame.parquet"; frame().to_parquet(f)
    out = tmp_path / "cheap2.csv"
    assert CB.main(["--season", "2026", "--week", "5", "--frame", str(f), "--out", str(out)]) == 0
    before = out.read_bytes()
    assert CB.main(["--season", "2026", "--week", "5", "--frame", str(f), "--out", str(out)]) == 3
    assert out.read_bytes() == before


def test_main_needs_exactly_one_source(tmp_path):
    with pytest.raises(SystemExit):
        CB.main(["--season", "2026", "--week", "5", "--out", str(tmp_path / "x.csv")])
