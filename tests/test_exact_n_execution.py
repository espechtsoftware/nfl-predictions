import importlib.util
from pathlib import Path
import sys

from nfl_dfs.optimizer.lineup import Lineup


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "run_exact_n_scorefree", ROOT / "scripts/run_exact_n_scorefree.py",
)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def _legal_lineup():
    rows = [
        ("qb", "QB", "A", "B", "g1", 6000),
        ("wr1", "WR", "A", "B", "g1", 6000),
        ("wr2", "WR", "A", "B", "g1", 6000),
        ("rb1", "RB", "B", "A", "g1", 6000),
        ("rb2", "RB", "C", "D", "g2", 5500),
        ("wr3", "WR", "D", "C", "g2", 5000),
        ("wr4", "WR", "E", "F", "g3", 5000),
        ("te", "TE", "F", "E", "g3", 4500),
        ("dst", "DST", "G", "H", "g4", 5000),
    ]
    return Lineup([
        {
            "id": player_id, "name": player_id, "pos": position,
            "team": team, "opp": opponent, "game_id": game,
            "salary": salary, "proj": 10.0,
        }
        for player_id, position, team, opponent, game, salary in rows
    ])


def test_exact_n_runner_has_independent_production_legality_gate():
    lineup = _legal_lineup()
    assert RUNNER._is_production_legal(lineup)

    lineup.players[4]["team"] = "B"
    assert not RUNNER._is_production_legal(lineup)


def test_exact_n_execution_is_outcome_free_create_only_and_ordered():
    runner = (ROOT / "scripts/run_exact_n_scorefree.py").read_text()
    assert "resolve_panel_artifacts" in runner
    assert "summarize_exact_n_panel" in runner
    assert "candidate_or_lineup_scores_read\": False" in runner
    assert "actual_score" not in runner
    assert "actual_ownership" not in runner

    launcher = (ROOT / "scripts/cloud_exact_n_scorefree.sh").read_text()
    assert "strict ATLAS harvest must precede exact-N" in launcher
    assert "objects describe" in launcher
    assert "--max-retries 0" in launcher
    assert "uses_realized_outcomes=false" in launcher

    finisher = (ROOT / "scripts/cloud_finish_exact_n_scorefree.sh").read_text()
    assert "source_preflight" in finisher
    assert "execution.json" in finisher
    assert 'row.get("type") == "Completed"' in finisher
    assert "licensed_shadow_cardinalities" in finisher
    assert "n80_parity" in finisher

    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "COPY scripts/run_exact_n_scorefree.py" in dockerfile
