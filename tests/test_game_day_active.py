"""O-32 correction protocol: the one shared game-day ACT repair, and its OFF-by-default switch in the six analyses."""
import importlib
import inspect
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs import cli
from nfl_dfs.analysis import game_day_active as G

ROOT = Path(__file__).resolve().parents[1]
MODULES = {"fantasy-points-defense-proe-diagnostic": "fantasy_points_defense_proe",
           "fantasy-points-qb-shell-diagnostic": "fantasy_points_qb_shell",
           "market-tail-diagnostic": "market_tail_disagreement",
           "ngs-receiver-tail-diagnostic": "ngs_receiver_tail",
           "pass-participation-proxy": "pass_participation"}


def _rows():
    return pd.DataFrame({"season": [2023, 2023, 2023, 2024], "week": [5, 5, 5, 6],
                         "gsis_id": ["a", "b", "c", "a"], "actual": [12.0, 0.0, 0.0, 9.0], "x": [1, 2, 3, 4]})


def test_keeps_act_drops_inactive_and_missing_roster_rows_with_audit():
    active = pd.DataFrame({"season": [2023, 2023, 2024], "week": [5, 5, 6], "gsis_id": ["a", "b", "a"],
                           "act": [True, False, True]})
    kept, audit = G.filter_game_day_active(_rows(), active)
    assert list(kept.x) == [1, 4] and list(kept.columns) == list(_rows().columns)
    assert audit == {"rule": "O-32 game-day rosters_weekly status ACT", "rows_in": 4, "rows_kept": 2,
                     "dropped_not_act": 1, "dropped_no_roster_row": 1}


def test_keys_are_type_normalised_and_required():
    active = pd.DataFrame({"season": ["2023"], "week": ["5"], "gsis_id": ["a"], "act": [True]})
    kept, _ = G.filter_game_day_active(_rows().iloc[:1], active)
    assert len(kept) == 1
    with pytest.raises(ValueError, match="needs"):
        G.filter_game_day_active(_rows().drop(columns="gsis_id"), active)


@pytest.mark.parametrize("cmd,mod", sorted(MODULES.items()))
def test_switch_is_off_by_default_and_the_cli_passes_it(cmd, mod, monkeypatch):
    m = importlib.import_module(f"nfl_dfs.analysis.{mod}")
    assert inspect.signature(m.run).parameters["game_day_active"].default is False
    assert "from .game_day_active import apply as _active" in inspect.getsource(m.run)
    seen = {}
    monkeypatch.setattr(m, "run", lambda panel, *, game_day_active=False: seen.update(g=game_day_active))
    cli.main([cmd]); assert seen["g"] is False
    cli.main([cmd, "--game-day-active"]); assert seen["g"] is True


def test_market_movement_script_has_the_switch():
    text = (ROOT / "scripts" / "market_movement_eval.py").read_text()
    assert '"--game-day-active" in sys.argv[1:]' in text and "game_day_active import apply" in text
