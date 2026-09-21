import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "player_score.py"
SPEC = importlib.util.spec_from_file_location("player_score", SCRIPT)
player_score = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(player_score)


def write_receipt(tmp_path, **values):
    run = tmp_path / "week3-run"
    run.mkdir()
    (run / "receipt.json").write_text(json.dumps(values))
    return run


def test_scope_is_derived_from_run_receipt(tmp_path):
    run = write_receipt(tmp_path, season=2026, week=3, run_id="week3-live-a")

    assert player_score.resolve_scope(run, None, None) == {
        "season": 2026,
        "week": 3,
        "run_id": "week3-live-a",
    }


def test_scope_rejects_stale_explicit_week(tmp_path):
    run = write_receipt(tmp_path, season=2026, week=3, run_id="week3-live-a")

    with pytest.raises(player_score.ScopeError, match="disagrees"):
        player_score.resolve_scope(run, 2026, 1)


def test_scope_fails_closed_without_receipt_or_target(tmp_path):
    with pytest.raises(player_score.ScopeError, match="missing run receipt"):
        player_score.resolve_scope(tmp_path / "missing", None, None)

    run = write_receipt(tmp_path, run_id="unscoped")
    with pytest.raises(player_score.ScopeError, match="season/week"):
        player_score.resolve_scope(run, None, None)
