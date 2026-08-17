from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from run_stack_core_shell_historical_score import (  # noqa: E402
    _actual_maps,
    _native_actual_parity,
)


def _players() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "season": season,
            "week": week,
            "player_id": f"{season}-{week}-p{index}",
            "actual": 1.0,
        }
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
        for index in range(9)
    ])


def test_historical_actual_source_requires_full_grid_and_native_parity() -> None:
    maps = _actual_maps(_players())
    roster = ",".join(f"2023-1-p{index}" for index in range(9))
    sources = pd.DataFrame({
        "season": [2023] * 68_199,
        "week": [1] * 68_199,
        "players": [roster] * 68_199,
        "actual_score": [9.0] * 68_199,
    })
    parity = _native_actual_parity(sources, maps)
    assert parity["registered_candidate_rows"] == 68_199
    assert parity["maximum_absolute_error"] == 0.0

    sources.loc[0, "actual_score"] = 8.0
    try:
        _native_actual_parity(sources, maps)
    except RuntimeError as exc:
        assert "actual-score parity differs" in str(exc)
    else:
        raise AssertionError("mismatched native actual score was accepted")


def test_historical_actual_source_rejects_incomplete_slate_grid() -> None:
    players = _players()
    players = players[
        ~(
            players.season.eq(2025)
            & players.week.eq(18)
        )
    ]
    try:
        _actual_maps(players)
    except RuntimeError as exc:
        assert "outcome grid differs" in str(exc)
    else:
        raise AssertionError("incomplete historical outcome grid was accepted")
