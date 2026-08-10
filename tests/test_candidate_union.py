import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.candidate_union import (
    select_candidate_union,
    tail_first_decision,
)


def _bits(worlds: list[int], n: int = 8) -> str:
    values = np.zeros(n, dtype=np.uint8)
    values[worlds] = 1
    return np.packbits(values, bitorder="big").tobytes().hex()


def _row(ix: int, players: str, worlds: list[int], *, selected: bool,
         actual: float | None = None) -> dict:
    return {
        "season": 2025,
        "week": 1,
        "cand_ix": ix,
        "players": players,
        "selected": selected,
        "actual_score": float(150 + ix if actual is None else actual),
        "p_line": len(worlds) / 8,
        "sim_mean": float(160 + ix),
        "n_worlds": 8,
        "clear_bits_194": _bits(worlds),
    }


def test_union_preserves_source_then_adds_only_novel_rosters():
    source = pd.DataFrame([
        _row(0, "a", [0, 1], selected=True),
        _row(1, "b", [2], selected=True),
        _row(2, "c", [3], selected=False),
    ])
    addon = pd.DataFrame([
        _row(8, "a", [0, 1], selected=True, actual=150),
        _row(9, "d", [4, 5], selected=True),
        _row(10, "e", [6], selected=False),
    ])
    # Shared-roster fields must be identical even when panel cand_ix differs.
    addon.loc[addon.players.eq("a"), ["p_line", "sim_mean"]] = [0.25, 160.0]
    union, audit = select_candidate_union(source, addon, entry_count=2)
    assert union.players.tolist() == ["a", "b", "c", "d", "e"]
    assert union.union_origin.tolist() == [
        "source", "source", "source", "addon", "addon"]
    assert int(union.selected.sum()) == 2
    assert audit.novel_addon_candidates.tolist() == [2]
    assert audit.union_candidates.tolist() == [5]


def test_union_rejects_shared_support_mismatch():
    source = pd.DataFrame([
        _row(0, "a", [0], selected=True),
        _row(1, "b", [1], selected=True),
    ])
    addon = source.copy()
    addon.loc[addon.players.eq("a"), "clear_bits_194"] = _bits([7])
    with pytest.raises(ValueError, match="support worlds"):
        select_candidate_union(source, addon, entry_count=2)


def test_union_rejects_incomplete_source_book():
    source = pd.DataFrame([
        _row(0, "a", [0], selected=True),
        _row(1, "b", [1], selected=False),
    ])
    with pytest.raises(ValueError, match="does not select exactly 2"):
        select_candidate_union(source, source.copy(), entry_count=2)


def test_tail_first_decision_is_highest_difference_first():
    source = {"clear_240": 1, "clear_230": 2,
              "clear_220": 5, "clear_210": 12}
    higher_win = {"clear_240": 2, "clear_230": 1,
                  "clear_220": 4, "clear_210": 10}
    result = tail_first_decision(source, higher_win)
    assert result["promotion_candidate"]
    assert not result["pareto_nonworse_210_plus"]
    assert result["first_difference"] == 240

    higher_loss = {"clear_240": 1, "clear_230": 1,
                   "clear_220": 7, "clear_210": 15}
    result = tail_first_decision(source, higher_loss)
    assert not result["promotion_candidate"]
    assert result["first_difference"] == 230

    tied = tail_first_decision(source, source)
    assert tied["tie_through_210"]
    assert not tied["promotion_candidate"]
