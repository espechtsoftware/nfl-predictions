"""ownership_fp: matching FP's ownership to the build frame, the scale rule, and the refusals (synthetic; no BigQuery)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ownership_fp as of  # noqa: E402

FRAME = pd.DataFrame({"id": ["g1", "g2", "g3", "g4", "BUF_DST"], "dk_player_id": [11, 12, 13, 14, 15],
                      "display_name": ["Kenneth Walker III", "Mike Williams", "Mike Williams", "Jalen Coker", "Bills"],
                      "pos": ["RB", "WR", "WR", "WR", "DST"], "team": ["KC", "LAC", "NYJ", "CAR", "BUF"],
                      "mean_projection": [15.0, 9.0, 8.0, 7.0, 7.0]})


def test_match_by_name_and_team_then_unique_name():
    fp = pd.DataFrame({"name": ["Kenneth Walker", "Mike Williams", "Mike Williams", "Jalen Coker", "Bills"],
                       "team": ["KC", "LAC", "NYJ", "CHA", "BUF"], "projected_ownership_pct": [17.0, 4.0, 2.0, 7.0, 9.0]})
    m = of.match_to_frame(fp, FRAME).set_index("id")
    assert m.loc["g1", "fp_own"] == 17.0                                    # suffix-insensitive
    assert m.loc["g2", "fp_own"] == 4.0 and m.loc["g3", "fp_own"] == 2.0   # same name, told apart by team
    assert m.loc["g4", "fp_own"] == 7.0                                    # team code differs (CHA/CAR): unique name matches
    assert m.loc["BUF_DST", "fp_own"] == 9.0


def test_an_ambiguous_name_with_a_wrong_team_is_not_guessed():
    fp = pd.DataFrame({"name": ["Mike Williams"], "team": ["XXX"], "projected_ownership_pct": [5.0]})
    assert of.match_to_frame(fp, FRAME).empty


def test_scale_matches_the_reference_skill_total_on_shared_players():
    m = pd.DataFrame({"display_name": ["A", "B", "C"], "pos": ["RB", "WR", "DST"], "fp_own": [20.0, 10.0, 50.0]})
    ref = pd.DataFrame({"display_name": ["A", "B", "Z"], "pred_own": [9.0, 6.0, 30.0]})
    assert of.scale_factor(m, ref) == pytest.approx(15.0 / 30.0)          # skill only, shared players only
    with pytest.raises(SystemExit, match="FP OWNERSHIP REFUSED: no scale reference"):
        of.scale_factor(m, pd.DataFrame({"display_name": ["Q"], "pred_own": [1.0]}))
