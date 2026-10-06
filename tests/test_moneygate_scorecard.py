"""The scorecard's per-lineup features (synthetic)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("moneygate_scorecard", ROOT / "scripts" / "moneygate_scorecard.py")
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)


def test_lineup_features_shape_rb_and_dual():
    team = {"Q": "A", "W1": "A", "W2": "A", "R1": "A", "B": "B", "R2": "B", "C1": "C", "D1": "D", "DST": "A"}
    pos = {"Q": "QB", "W1": "WR", "W2": "TE", "R1": "RB", "B": "WR", "R2": "RB", "C1": "WR", "D1": "WR", "DST": "DST"}
    opp = {"A": "B", "B": "A", "C": "D", "D": "C"}
    sal = {p: 5000 for p in team}; sal["C1"] = 3500
    f = S.lineup_features(["Q", "W1", "W2", "R1", "B", "R2", "C1", "D1", "DST"], team, pos, sal, opp, {"Q": 10.0}, set())
    assert f["qb_plus2"] and not f["qb_plus1"] and f["bringback"] and f["in_qb_game"] == 6 and f["dual"]
    assert f["rb_with_qb"] and f["rb_bb"] and f["rb_dst"] and f["games"] == 2 and f["sub4k"] == 1 and f["own_sum"] == 10.0
    assert S.lineup_features(["W1", "B"], team, pos, sal, opp, {}, set()) is None   # no QB -> skipped
