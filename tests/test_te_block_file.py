"""scripts/te_block_file.py: the pass-catching tight-end term-block file (offline, synthetic frame)."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location("te_block_file", Path(__file__).resolve().parents[1] / "scripts" / "te_block_file.py")
TB = importlib.util.module_from_spec(spec); spec.loader.exec_module(TB)


def frame():
    # 8 teams' players; TEs A (0.20 share, faces T1), B (0.10, faces T2), C (0.18, faces T3); a cheap WR; a QB; a DST
    rows = [("A", "TE", "X1", "T1", 5000, 0.20), ("B", "TE", "X2", "T2", 3500, 0.10), ("C", "TE", "X3", "T3", 4500, 0.18),
            ("D", "WR", "X4", "T4", 3800, 0.12), ("E", "QB", "X5", "T5", 6500, 0.0), ("F", "DST", "X6", "T6", 3000, 0.0)]
    df = pd.DataFrame(rows, columns=["display_name", "pos", "team", "opp", "salary", "target_share_l4"])
    df["dk_player_id"] = range(1, len(df) + 1); df["id"] = list("abcdef")
    # the opponents' pass defense (lower = tougher): T1 toughest ... T6 softest, plus two more teams so 6+ opponents exist
    epa = {"T1": -0.30, "T2": -0.20, "T3": 0.10, "T4": 0.15, "T5": 0.20, "T6": 0.30}
    df["epa_per_dropback_allowed_l6"] = df.opp.map(epa)
    return df


def test_pass_catching_tes_only():
    out = TB.build(frame(), 2.0)
    assert list(out.columns) == TB.COLUMNS
    assert dict(zip(out.display_name, out.bonus_points)) == {"A": 2.0, "B": 0.0, "C": 2.0, "D": 0.0, "E": 0.0}   # DST omitted
    assert (out.pred_own * TB.TILT).round(6).tolist() == out.bonus_points.tolist()


def test_tough_pass_d_restricts_to_the_toughest_third():
    out = TB.build(frame(), 2.0, tough_pass_d=True)
    assert dict(zip(out.display_name, out.bonus_points))["A"] == 2.0          # faces T1 (toughest)
    assert dict(zip(out.display_name, out.bonus_points))["C"] == 0.0          # faces T3 (not in the toughest third)


def test_with_cheap_adds_the_cheap_rule():
    out = TB.build(frame(), 2.0, with_cheap=True)
    b = dict(zip(out.display_name, out.bonus_points))
    assert b["A"] == 2.0 and b["C"] == 2.0 and b["B"] == 2.0 and b["D"] == 2.0 and b["E"] == 0.0   # B, D under $4,000


@pytest.mark.parametrize("mutate, kw, msg", [
    (lambda f: f.drop(columns=["target_share_l4"]), {}, "target_share_l4"),
    (lambda f: f.assign(dk_player_id=[1, 1, 3, 4, 5, 6]), {}, "duplicated"),
    (lambda f: f.assign(target_share_l4=0.0), {}, "no player carries"),
    (lambda f: f.drop(columns=["epa_per_dropback_allowed_l6"]), {"tough_pass_d": True}, "epa_per_dropback"),
])
def test_refusals(mutate, kw, msg):
    with pytest.raises(ValueError, match=msg):
        TB.build(mutate(frame()), 2.0, **kw)


def test_main_is_create_once(tmp_path):
    f = tmp_path / "frame.parquet"; frame().to_parquet(f); out = tmp_path / "te2.csv"
    assert TB.main(["--season", "2026", "--week", "5", "--frame", str(f), "--out", str(out)]) == 0
    before = out.read_bytes()
    assert TB.main(["--season", "2026", "--week", "5", "--frame", str(f), "--out", str(out)]) == 3
    assert out.read_bytes() == before
