import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def _runner():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    path = ROOT / "scripts/run_cbwu_oi_construction_diagnostic.py"
    spec = importlib.util.spec_from_file_location("cbwu_oi_construction", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _legal_players():
    rows = [
        ("qb", "QB", "A", "B", "g1", 7_000),
        ("rb1", "RB", "C", "D", "g2", 6_000),
        ("rb2", "RB", "D", "C", "g2", 6_000),
        ("rb3", "RB", "E", "F", "g3", 6_000),
        ("wr1", "WR", "A", "B", "g1", 6_000),
        ("wr2", "WR", "A", "B", "g1", 6_000),
        ("wr3", "WR", "B", "A", "g1", 6_000),
        ("te", "TE", "F", "E", "g3", 4_000),
        ("dst", "DST", "G", "H", "g4", 2_000),
    ]
    return [
        {
            "id": player_id,
            "pos": pos,
            "team": team,
            "opp": opp,
            "game_id": game,
            "salary": salary,
        }
        for player_id, pos, team, opp, game, salary in rows
    ]


def test_structure_requires_full_legal_roster_and_reports_shape():
    runner = _runner()
    result = runner._structure(_legal_players())
    assert result["salary"] == 49_000
    assert result["distinct_games"] == 4
    assert result["qb_stack_count"] == 2
    assert result["bring_back_count"] == 1
    assert result["rb_salary"] == 18_000

    invalid = _legal_players()
    invalid[-2] = {**invalid[-2], "pos": "K"}
    try:
        runner._structure(invalid)
    except ValueError as exc:
        assert "shape" in str(exc)
    else:
        raise AssertionError("unexpected positions must fail legality")


def test_score_pool_reports_c_and_exact_p_distance():
    runner = _runner()
    first = tuple(f"p{index}" for index in range(9))
    second = (*first[:-1], "x")
    structure = runner._structure(_legal_players())
    static = {
        "identities": [first, second],
        "structures": [structure, structure],
        "pair_reach": 40,
        "stack_core_reach": 5,
    }
    actuals = {player: 1.0 for player in first}
    actuals["x"] = 10.0
    p_static = runner._exact_p_static(static, first)
    result = runner._score_pool(static, actuals, p_static)
    assert result["c_score"] == 18.0
    assert result["c_identity"] == list(second)
    assert result["c_tie_count"] == 1
    assert result["minimum_swaps_to_exact_p"] == 0
    assert result["exact_p_player_slots_represented"] == 9


def test_cloud_runner_is_frozen_outcome_delayed_and_packaged():
    runner = _runner()
    source = (
        ROOT / "scripts/run_cbwu_oi_construction_diagnostic.py"
    ).read_text(encoding="utf-8")
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert runner.PROTOCOL_SHA256 == (
        "3b458263b165b380e6adf1efdf6ed08fb423c91d6988b5741aa32b11beafe1ec"
    )
    assert runner.CBWU_REPORT_SHA256 == (
        "556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33"
    )
    assert source.index("actual_frame = _query") > source.index(
        "for season, week in slates"
    )
    assert '"scores_cbwu_oi_selected_80": False' in source
    assert '"historical_arm_licensed": False' in source
    assert "COPY scripts/run_cbwu_oi_construction_diagnostic.py" in docker

    launch = (
        ROOT / "scripts/cloud_cbwu_oi_construction_diagnostic.sh"
    ).read_text(encoding="utf-8")
    finish = (
        ROOT / "scripts/cloud_finish_cbwu_oi_construction_diagnostic.sh"
    ).read_text(encoding="utf-8")
    assert "gcloud storage objects describe" in launch
    assert "--memory 32Gi" in launch
    assert "--max-retries 0" in launch
    assert "uses_realized_candidate_scores=true" in launch
    assert "scores_cbwu_oi_selected_80=false" in launch
    assert "len(r.get(\"source_artifacts\", [])) != 270" in finish
    assert "canonical corrected C tails do not reproduce" in finish
    assert "selected-book field leaked" in finish
