"""scripts/check_term_block_file.py: the arm refuses a term-block file the armed cap would silently clip (offline)."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_term_block_file", ROOT / "scripts" / "check_term_block_file.py")
CT = importlib.util.module_from_spec(spec); spec.loader.exec_module(CT)
spec = importlib.util.spec_from_file_location("cheap_block_file", ROOT / "scripts" / "cheap_block_file.py")
CB = importlib.util.module_from_spec(spec); spec.loader.exec_module(CB)


def frame():
    return pd.DataFrame({"dk_player_id": [1, 2, 3, 4, 5, 6], "id": ["a", "b", "c", "d", "e", "BUF_DST"],
                         "display_name": list("ABCDEF"), "pos": ["QB", "RB", "WR", "TE", "WR", "DST"],
                         "team": ["X"] * 6, "opp": ["Y"] * 6, "salary": [6000, 3900, 4000, 3000, 3999, 2500]})


def test_the_cheap_writers_files_pass_at_their_own_cap_and_a_plus4_file_is_refused_under_cap_2(tmp_path):
    assert "3 of 5 players carry a bonus (largest 2, cap 2)" in CT.check(CB.build(frame(), 2.0), 2.0, 0.20)
    assert CT.check(CB.build(frame(), 4.0), 4.0, 0.20).startswith("3 of 5")
    with pytest.raises(ValueError, match="exceeds the cap 2"):
        CT.check(CB.build(frame(), 4.0), 2.0, 0.20)
    f = tmp_path / "cheap4.csv"; CB.build(frame(), 4.0).to_csv(f, index=False)
    assert CT.main([str(f), "--cap", "2.0"]) == 3 and CT.main([str(f), "--cap", "4.0"]) == 0


def test_the_cap_must_be_in_the_unions_range():
    for cap in (0.0, -1.0, 5.5):
        with pytest.raises(ValueError, match="outside the union's range"):
            CT.check(CB.build(frame(), 2.0), cap, 0.20)
    assert CT.check(CB.build(frame(), 2.0), 5.0, 0.20).startswith("3 of 5")


def test_a_bonus_file_whose_pred_own_is_not_bonus_over_tilt_is_refused():
    d = CB.build(frame(), 2.0); d.loc[d.bonus_points > 0, "pred_own"] = 20.0      # a +4 pred_own under a +2 bonus column
    with pytest.raises(ValueError, match="pred_own is not bonus_points / 0.2"):
        CT.check(d, 2.0, 0.20)


@pytest.mark.parametrize("mutate, msg", [
    (lambda d: d.drop(columns="pred_own"), "no pred_own column"),
    (lambda d: d.assign(dk_player_id=[1, 1, 3, 4, 5]), "duplicated dk_player_id"),
    (lambda d: d.assign(bonus_points=-d.bonus_points, pred_own=-d.pred_own), "a negative bonus"),
    (lambda d: d.assign(bonus_points=0.0, pred_own=0.0), "no player carries a bonus"),
])
def test_malformed_bonus_files_are_refused(mutate, msg):
    with pytest.raises(ValueError, match=msg):
        CT.check(mutate(CB.build(frame(), 2.0)), 2.0, 0.20)


def test_the_prior_top_form_without_bonus_points_passes_with_a_note():
    d = pd.DataFrame({"dk_player_id": [1, 2], "pred_own": [42.4, 3.0], "prior_top": [0.8, 0.1]})
    assert "the prior-top form" in CT.check(d, 2.0, 0.20)


def test_the_week5_arm_runs_the_check_with_its_cap_and_passes_the_cap_to_the_union():
    arm = (ROOT / "scripts" / "arm_week5_saturday.sh").read_text()
    assert "\nTERM_CAP=2.0 " in arm and "UNION_TERM_BLOCK_CAP=$TERM_CAP" in arm and "UNION_TERM_BLOCK_CAP=2.0" not in arm
    assert '"$PY" "$P/scripts/check_term_block_file.py" "$P/$TERM_FILE" --cap "$TERM_CAP" --require-bonus' in arm


def test_the_armed_check_refuses_the_prior_top_form():
    """The outside review 10-07, M2: --require-bonus (the arm's live block) refuses a file without bonus_points."""
    d = pd.DataFrame({"dk_player_id": [1, 2], "pred_own": [42.4, 3.0], "prior_top": [0.8, 0.1]})
    with pytest.raises(ValueError, match="paper-only form"):
        CT.check(d, 2.0, 0.20, require_bonus=True)
    assert "carry a bonus" in CT.check(CB.build(frame(), 2.0), 2.0, 0.20, require_bonus=True)
