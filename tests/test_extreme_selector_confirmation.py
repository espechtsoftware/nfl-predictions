import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.extreme_selector_confirmation import evaluate_panel


def _bits(worlds: list[int], n: int = 8) -> str:
    values = np.zeros(n, dtype=np.uint8)
    values[worlds] = 1
    return np.packbits(values, bitorder="big").tobytes().hex()


def _panel() -> pd.DataFrame:
    rows = []
    supports = [
        ([0, 1, 2, 3], [0, 1, 2], [0, 1], [0], [0]),
        ([4, 5, 6], [4, 5], [4, 5], [4], [4]),
        ([0, 4, 6], [0, 4], [0, 4], [0, 4], [0, 4]),
    ]
    for ix, support in enumerate(supports):
        s187, s194, s200, s210, s220 = support
        rows.append({
            "season": 2025,
            "week": 1,
            "cand_ix": ix,
            "players": ",".join(f"p{ix}{slot}" for slot in range(9)),
            "selected": ix in (0, 1),
            "selected_rank": ix if ix in (0, 1) else None,
            "actual_score": [205.0, 198.0, 241.0][ix],
            "p_line": len(s194) / 8,
            "sim_mean": [170.0, 169.0, 168.0][ix],
            "n_worlds": 8,
            "clear_bits_187": _bits(s187),
            "clear_bits_194": _bits(s194),
            "clear_bits_200": _bits(s200),
            "clear_bits_210": _bits(s210),
            "clear_bits_220": _bits(s220),
        })
    return pd.DataFrame(rows)


def test_confirmation_reproduces_control_and_applies_tail_law():
    report = evaluate_panel(_panel(), expected_slates=1, entry_count=2)
    assert report["control"]["clear_240"] == 0
    assert report["extreme"]["clear_240"] == 1
    assert report["disposition"] == "promote-extreme-selector"
    assert report["tail_first_decision"]["first_difference"] == 240
    assert report["pool_oracle_identical"]["clear_240"] == 1


def test_confirmation_fails_if_persisted_book_does_not_reproduce():
    panel = _panel()
    panel["selected"] = [True, False, True]
    with pytest.raises(ValueError, match="does not reproduce"):
        evaluate_panel(panel, expected_slates=1, entry_count=2)
