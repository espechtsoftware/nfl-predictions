import importlib.util
from pathlib import Path

import pandas as pd
import pytest

_P = Path(__file__).resolve().parents[1] / "scripts" / "ownership_sets.py"
_spec = importlib.util.spec_from_file_location("ownership_sets", _P)
osets = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(osets)


def _pred():
    pos = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "DST", "WR", "RB"]
    return pd.DataFrame({"pos": pos, "pred_own": [30, 25, 2, 18, 1, 9, 0.5, 15, 3, 4.0]})


def test_sets_are_rank_defined_and_sized_by_the_shares():
    s = osets.assign_sets(_pred(), chalk_share=0.2, low_share=0.5)
    assert sorted(s.loc[s.set == "CHALK", "pred_own"]) == [25, 30]          # top 2 of 10
    low = s[s.set == "LOW"]
    assert len(low) == round(0.5 * 9)                                        # 9 skill players
    assert set(low.pos) <= set(osets.SKILL)                                  # DST never LOW
    assert low.pred_own.max() <= s[(s.set == "MID") & s.pos.isin(osets.SKILL)].pred_own.min()


def test_chalk_is_never_empty_even_with_compressed_predictions():
    p = _pred().assign(pred_own=lambda d: d.pred_own / 10)                   # nobody predicted >= 20%
    s = osets.assign_sets(p, chalk_share=0.01, low_share=0.3)
    assert (s.set == "CHALK").sum() == 1


def test_set_shares_counts_chalk_over_all_and_low_over_skill_only():
    h = pd.DataFrame({"season": 2024, "week": 1,
                      "pos": ["QB", "WR", "WR", "DST"], "own": [25.0, 3.0, 10.0, 1.0]})
    chalk, low = osets.set_shares(h)
    assert chalk == pytest.approx(1 / 4)
    assert low == pytest.approx(1 / 3)


def test_replay_sets_are_walk_forward_and_write_one_file_per_slate(tmp_path, monkeypatch):
    import numpy as np
    import pandas as pd
    seen = []

    class M:
        def predict(self, X):
            return np.log(np.linspace(30, 1, len(X)) + 0.1)

    def fake_fit(train):
        seen.append(sorted(train.season.unique().tolist()))
        return M()
    monkeypatch.setattr(osets, "fit", fake_fit)
    rows = []
    for season in (2022, 2023, 2024):
        for week in (1, 2):
            for i in range(40):
                pos = ["QB", "RB", "WR", "TE", "DST"][i % 5]
                rows.append({"season": season, "week": week, "id": f"p{i}", "gsis_id": f"g{i}", "name": f"P {i}",
                             "team": "T", "pos": pos, "salary": 4000 + 100 * i, "proj": 5 + i % 7,
                             "proj_p90": 10 + i % 7, "implied_team_total": 22.0, "own": float(i % 25)})
    d = osets.add_features(pd.DataFrame(rows), ["season", "week"])
    recs = osets.replay_sets(d, [2023, 2024], tmp_path)
    assert seen == [[2022], [2022, 2023]], "season S must be fit on seasons before S only"
    assert [r["fit_seasons"] for r in recs] == [[2022], [2022], [2022, 2023], [2022, 2023]]
    f = pd.read_csv(tmp_path / "2024-w02.csv")
    assert list(f.columns) == ["gsis_id", "id", "display_name", "pos", "team", "salary", "proj", "pred_own", "pred_rank", "set"]
    assert set(f["set"]) <= {"LOW", "MID", "CHALK"} and (f["set"] == "CHALK").sum() >= 1
    import pytest
    with pytest.raises(SystemExit, match="prior fold"):
        osets.replay_sets(d, [2022], tmp_path)
