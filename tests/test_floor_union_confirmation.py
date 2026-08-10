import numpy as np
import pandas as pd

import nfl_dfs.research.floor_union_confirmation as confirmation


def _bits(worlds: list[int], n: int = 8) -> str:
    values = np.zeros(n, dtype=np.uint8)
    values[worlds] = 1
    return np.packbits(values, bitorder="big").tobytes().hex()


def _row(ix, players, worlds, selected, actual, salary=49_000):
    return {
        "season": 2025,
        "week": 1,
        "cand_ix": ix,
        "players": players,
        "selected": selected,
        "selected_rank": ix if selected else None,
        "actual_score": actual,
        "salary": salary,
        "p_line": len(worlds) / 8,
        "sim_mean": 160.0 + ix,
        "n_worlds": 8,
        **{
            f"clear_bits_{threshold}": _bits(worlds)
            for threshold in (187, 194, 200, 210, 220)
        },
    }


def test_union_must_beat_source_and_incumbent(monkeypatch):
    monkeypatch.setattr(confirmation, "EXPECTED_SLATES", 1)
    monkeypatch.setattr(confirmation, "EXPECTED_ENTRIES", 2)
    source = pd.DataFrame([
        _row(0, "a", [0, 1], True, 205.0),
        _row(1, "b", [2], True, 198.0),
        _row(2, "c", [3], False, 180.0),
    ])
    addon = pd.DataFrame([
        _row(8, "a", [0, 1], True, 205.0),
        _row(9, "d", [4, 5, 6], True, 241.0, salary=47_500),
    ])
    # The shared roster is an identical simulation row despite a new cand_ix.
    addon.loc[addon.players.eq("a"), "sim_mean"] = 160.0
    incumbent = source.copy()
    report = confirmation.evaluate_union(source, addon, incumbent)
    assert report["disposition"] == "promote-floor-union"
    assert report["union"]["clear_240"] == 1
    assert report["candidate_audit"]["novel_addon_candidates"] == 1
    assert report["candidate_audit"]["novel_salary_min"] == 47_500


def test_union_does_not_promote_when_it_loses_to_incumbent(monkeypatch):
    monkeypatch.setattr(confirmation, "EXPECTED_SLATES", 1)
    monkeypatch.setattr(confirmation, "EXPECTED_ENTRIES", 2)
    source = pd.DataFrame([
        _row(0, "a", [0, 1], True, 205.0),
        _row(1, "b", [2], True, 198.0),
        _row(2, "c", [3], False, 180.0),
    ])
    addon = pd.DataFrame([
        _row(8, "a", [0, 1], True, 205.0),
        _row(9, "d", [4, 5, 6], True, 221.0, salary=47_500),
    ])
    addon.loc[addon.players.eq("a"), "sim_mean"] = 160.0
    incumbent = source.copy()
    incumbent.loc[incumbent.players.eq("a"), "actual_score"] = 241.0
    report = confirmation.evaluate_union(source, addon, incumbent)
    assert report["versus_source"]["promotion_candidate"]
    assert not report["versus_incumbent"]["promotion_candidate"]
    assert report["disposition"] == "keep-corrected-incumbent"
