"""Focused mocked tests for the contingent legal-soft-law-v1 policy."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
import sys

import pytest

from nfl_dfs.research.legal_soft_law import (
    A2A_PASS_DISPOSITION,
    B1_MODEL_VERSION,
    B1_REPORT_VERSION,
    ENTRIES,
    PROTOCOL_ID,
    PROTOCOL_STATUS,
    SOFT_LAW_FEATURES,
    LegalSoftLawError,
    _roster_features,
    canonical_json,
    evaluate_payload,
)


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_legal_soft_law as runner  # noqa: E402


def _digest(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _identity(label: str) -> dict:
    return {
        "uri": f"mock://{label}",
        "generation": "123",
        "sha256": _digest(label),
        "bytes": 100,
    }


def _content_identity(label: str, value: object) -> dict:
    raw = canonical_json(value)
    return {
        "uri": f"mock://{label}",
        "generation": "123",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _prerequisites() -> dict:
    a2a_result = {
        "passes": True,
        "disposition": A2A_PASS_DISPOSITION,
        "licenses": {
            "uses_realized_outcomes": True,
            "actual_outcomes_queried": True,
            "candidate_or_lineup_scores_read": False,
            "single_stack_protocol_licensed": True,
            "single_stack_arm_licensed": False,
            "exact80_scoring_licensed": False,
            "prospective_shadow_licensed": False,
            "production_change_licensed": False,
        },
    }
    b1_report = {
        "version": B1_REPORT_VERSION,
        "historical_pass": True,
        "uses_realized_outcomes": True,
        "uses_winner_target_or_feature": False,
        "model": {"version": B1_MODEL_VERSION},
        "licenses": {
            "write_2026_shadow_artifact": True,
            "run_2026_shadow": True,
            "production": False,
            "historical_retune": False,
        },
    }
    model_artifact = {
        "historical_gate_passed": True,
        "production_licensed": False,
        "prospective_shadow_only": True,
    }
    model_artifact["artifact_sha256"] = sha256(
        canonical_json(model_artifact)
    ).hexdigest()
    return {
        "a2a": {
            "result_identity": _content_identity("a2a-result", a2a_result),
            "result": a2a_result,
        },
        "b1": {
            "report_identity": _content_identity("b1-report", b1_report),
            "model_identity": _content_identity("b1-model", model_artifact),
            "report": b1_report,
            "model_artifact": model_artifact,
        },
    }


def _player(
    prefix: str,
    slot: str,
    pos: str,
    team: str,
    opp: str,
    game: str,
    salary: int,
) -> dict:
    return {
        "id": f"{prefix}-{slot}",
        "pos": pos,
        "team": team,
        "opp": opp,
        "game_id": game,
        "salary": salary,
        "slate_eligible": True,
        "prelock_eligible": True,
    }


def _players(prefix: str, shape: str) -> list[dict]:
    common = [
        _player(prefix, "qb", "QB", "A", "B", "g1", 7_000),
        _player(prefix, "rb1", "RB", "C", "D", "g2", 6_500),
        _player(prefix, "rb2", "RB", "E", "F", "g3", 6_000),
        _player(prefix, "dst", "DST", "G", "H", "g4", 3_000),
    ]
    if shape == "incumbent":
        skill = [
            _player(prefix, "wr1", "WR", "A", "B", "g1", 6_500),
            _player(prefix, "wr2", "WR", "B", "A", "g1", 6_000),
            _player(prefix, "wr3", "WR", "I", "J", "g5", 5_500),
            _player(prefix, "wr4", "WR", "K", "L", "g6", 4_500),
            _player(prefix, "te", "TE", "A", "B", "g1", 4_000),
        ]
    elif shape == "exact_one":
        skill = [
            _player(prefix, "wr1", "WR", "A", "B", "g1", 6_500),
            _player(prefix, "wr2", "WR", "B", "A", "g1", 6_000),
            _player(prefix, "wr3", "WR", "I", "J", "g5", 5_500),
            _player(prefix, "wr4", "WR", "K", "L", "g6", 4_500),
            _player(prefix, "te", "TE", "M", "N", "g7", 4_000),
        ]
    elif shape == "legality_only":
        common = [
            _player(prefix, "qb", "QB", "A", "B", "g1", 6_500),
            _player(prefix, "rb1", "RB", "C", "G", "g2", 6_000),
            _player(prefix, "rb2", "RB", "C", "G", "g2", 5_500),
            _player(prefix, "dst", "DST", "G", "C", "g2", 3_000),
        ]
        skill = [
            _player(prefix, "wr1", "WR", "I", "J", "g5", 6_000),
            _player(prefix, "wr2", "WR", "K", "L", "g6", 5_500),
            _player(prefix, "wr3", "WR", "M", "N", "g7", 5_000),
            _player(prefix, "wr4", "WR", "O", "P", "g8", 4_500),
            _player(prefix, "te", "TE", "Q", "R", "g9", 4_000),
        ]
    else:  # pragma: no cover - test helper guard
        raise AssertionError(shape)
    return common + skill


def _derived_features(players: list[dict]) -> dict:
    qb = next(player for player in players if player["pos"] == "QB")
    dst = next(player for player in players if player["pos"] == "DST")
    teams = Counter(player["team"] for player in players)
    games = Counter(player["game_id"] for player in players)
    rb_teams = Counter(
        player["team"] for player in players if player["pos"] == "RB"
    )
    salary = sum(player["salary"] for player in players)
    return {
        "salary_total": salary,
        "unused_salary": 50_000 - salary,
        "qb_partner_count": sum(
            player["pos"] in {"WR", "TE"} and player["team"] == qb["team"]
            for player in players
        ),
        "bring_back_count": sum(
            player["pos"] in {"RB", "WR", "TE"}
            and player["team"] == qb["opp"]
            for player in players
        ),
        "rb_vs_dst_count": sum(
            player["pos"] == "RB" and player["opp"] == dst["team"]
            for player in players
        ),
        "same_team_rb_pair_count": sum(
            count * (count - 1) // 2 for count in rb_teams.values()
        ),
        "games_represented": len(games),
        "teams_represented": len(teams),
        "largest_game_block": max(games.values()),
        "largest_team_block": max(teams.values()),
        "ownership_sum_est": 1.05,
        "duplication_risk_est": 0.02,
    }


def _candidate(prefix: str, sleeve: str, score: float) -> dict:
    shape = "incumbent" if sleeve == "control" else sleeve
    players = _players(prefix, shape)
    return {
        "roster_key": ",".join(sorted(player["id"] for player in players)),
        "players": players,
        "support_sleeve": sleeve,
        "model_score": score,
        "tie_break_p_line": min(score, 1.0),
        "tie_break_q99": 180.0 + score,
        "soft_features": _derived_features(players),
    }


def _budget(label: str, candidate_budget: int = 241) -> dict:
    return {
        "candidate_budget_source": "incumbent-r0-native-count",
        "control_candidate_budget": candidate_budget,
        "treatment_candidate_budget": candidate_budget,
        "control_solve_attempts": 300,
        "treatment_solve_attempts": 300,
        "world_blocks": 5,
        "worlds_per_block": 10_000,
        "seed_ids": [0, 1, 2, 3, 4],
        "world_draw_sha256s": [_digest(f"{label}-world-{i}") for i in range(5)],
        "solve_schedule_sha256": _digest(f"{label}-solves"),
        "entry_count": 80,
    }


def _slate(season: int, week: int, mode: str) -> dict:
    label = f"{season}-{week}"
    control = [
        _candidate(f"{label}-c-{index}", "control", 0.5 - index / 1_000)
        for index in range(241)
    ]
    treatment = [
        *[
            _candidate(f"{label}-i-{index}", "incumbent", 0.20 - index / 2_000)
            for index in range(80)
        ],
        *[
            _candidate(f"{label}-e-{index}", "exact_one", 0.40 - index / 2_000)
            for index in range(80)
        ],
        *[
            _candidate(
                f"{label}-l-{index}", "legality_only", 0.99 - index / 1_000,
            )
            for index in range(81)
        ],
    ]
    row = {
        "season": season,
        "week": week,
        "budget": _budget(label),
        "control": {
            "candidates": control,
            "selected_roster_keys": [row["roster_key"] for row in control[:80]],
        },
        "treatment": {"candidates": treatment},
    }
    if mode == "mocked-historical":
        control_scores = {row["roster_key"]: 180.0 for row in control}
        treatment_scores = {row["roster_key"]: 180.0 for row in treatment}
        control_scores[control[0]["roster_key"]] = 197.0 + week
        treatment_scores[treatment[160]["roster_key"]] = 200.0 + week
        # The final legality-only candidate ranks 81st: it supplies C while
        # remaining outside S, creating a prespecified five-point C-S gap.
        treatment_scores[treatment[-1]["roster_key"]] = 205.0 + week
        row["mock_outcomes"] = {
            "control_scores": control_scores,
            "treatment_scores": treatment_scores,
        }
    return row


def _payload(mode: str = "mocked-outcome-blind") -> dict:
    return {
        "protocol_id": PROTOCOL_ID,
        "protocol_status": PROTOCOL_STATUS,
        "mocked": True,
        "mode": mode,
        "prerequisites": _prerequisites(),
        "snapshot": {
            "snapshot_id": "mock-pit-snapshot",
            "feature_snapshot_at": "2026-08-20T15:00:00-05:00",
            "contest_lock_at": "2026-08-20T16:00:00-05:00",
            "source_identities": [_identity("candidates"), _identity("catalog")],
            "outcome_fields_read": [],
            "winner_fields_read": [],
        },
        "slates": [_slate(2026, 1, mode), _slate(2026, 2, mode)],
    }


def test_mocked_policy_ranks_exact80_without_final_structure_quotas() -> None:
    report = evaluate_payload(_payload())
    assert report["disposition"] == "legal-soft-law-mocked-mechanics-pass"
    assert report["policy"]["final_book_structure_quotas"] == {}
    assert report["policy"]["soft_law_features"] == list(SOFT_LAW_FEATURES)
    for slate in report["slates"]:
        assert len(slate["control_selected_roster_keys"]) == ENTRIES
        assert len(slate["treatment_selected_roster_keys"]) == ENTRIES
        assert slate["treatment_pool_sleeves"] == {
            "incumbent": 80,
            "exact_one": 80,
            "legality_only": 81,
        }
        assert slate["treatment_selected_sleeves"] == {
            "incumbent": 0,
            "exact_one": 0,
            "legality_only": 80,
        }
    assert not any(report["licenses"].values())
    assert report["production_change_licensed"] is False


def test_former_mandates_are_features_not_legality_requirements() -> None:
    report = evaluate_payload(_payload())
    first = report["slates"][0]
    assert first["treatment_selected_sleeves"]["legality_only"] == 80
    payload = _payload()
    open_candidate = payload["slates"][0]["treatment"]["candidates"][160]
    features = open_candidate["soft_features"]
    assert features["salary_total"] < 49_000
    assert features["qb_partner_count"] == 0
    assert features["bring_back_count"] == 0
    assert features["rb_vs_dst_count"] == 2
    assert features["same_team_rb_pair_count"] == 1


def test_one_game_is_a_soft_feature_not_platform_illegality() -> None:
    players = _players("one-game", "incumbent")
    for player in players:
        player["game_id"] = "g1"
    features = _roster_features(players, label="one-game fixture")
    assert features["games_represented"] == 1


@pytest.mark.parametrize("prerequisite", ["a2a", "b1"])
def test_both_prerequisite_passes_are_mandatory(prerequisite: str) -> None:
    payload = _payload()
    if prerequisite == "a2a":
        payload["prerequisites"]["a2a"]["result"]["passes"] = False
        result = payload["prerequisites"]["a2a"]["result"]
        payload["prerequisites"]["a2a"]["result_identity"] = \
            _content_identity("a2a-result", result)
        message = "A2a realized-law"
    else:
        payload["prerequisites"]["b1"]["report"]["historical_pass"] = False
        report = payload["prerequisites"]["b1"]["report"]
        payload["prerequisites"]["b1"]["report_identity"] = \
            _content_identity("b1-report", report)
        message = "B1 corpus-tail"
    with pytest.raises(LegalSoftLawError, match=message):
        evaluate_payload(payload)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda payload: payload["slates"][0]["budget"].update(
                treatment_candidate_budget=242
            ),
            "candidate budgets differ",
        ),
        (
            lambda payload: payload["slates"][0]["budget"].update(
                treatment_solve_attempts=301
            ),
            "solve budgets differ",
        ),
        (
            lambda payload: payload["slates"][0]["budget"].update(
                worlds_per_block=9_999
            ),
            "world budget differs",
        ),
    ],
)
def test_compute_candidate_and_world_budgets_fail_closed(mutation, message: str) -> None:
    payload = _payload()
    mutation(payload)
    with pytest.raises(LegalSoftLawError, match=message):
        evaluate_payload(payload)


def test_dk_legality_and_point_in_time_remain_hard() -> None:
    payload = _payload()
    candidate = payload["slates"][0]["treatment"]["candidates"][160]
    candidate["players"][0]["salary"] = 60_000
    with pytest.raises(LegalSoftLawError, match="salary cap"):
        evaluate_payload(payload)

    payload = _payload()
    payload["snapshot"]["feature_snapshot_at"] = "2026-08-20T16:00:00-05:00"
    with pytest.raises(LegalSoftLawError, match="precede contest lock"):
        evaluate_payload(payload)


def test_outcome_blind_firewall_rejects_nested_outcomes() -> None:
    payload = _payload()
    payload["slates"][0]["treatment"]["candidates"][0]["actual_score"] = 220.0
    with pytest.raises(LegalSoftLawError, match="outcome-blind forbidden field"):
        evaluate_payload(payload)


def test_mocked_historical_on_track_gate_requires_c205_and_gap5() -> None:
    report = evaluate_payload(_payload("mocked-historical"))
    assert report["disposition"] == "legal-soft-law-mocked-on-track"
    gate = report["historical_gate"]
    assert gate["selection_pass"] is True
    assert gate["target_pass"] is True
    assert gate["treatment"]["mean_candidate_ceiling"] == 206.5
    assert gate["treatment"]["mean_conversion_gap"] == 5.0
    assert report["licenses"] == {
        "real_artifact_smoke_licensed": False,
        "freeze_licensed": False,
        "historical_execution_licensed": False,
        "prospective_shadow_licensed": False,
        "production_change_licensed": False,
    }
    assert report["mocked_would_license"] == {
        "prospective_shadow_design": True,
        "target_200_track": True,
    }


def test_smaller_positive_is_incremental_only_not_a_200_claim() -> None:
    payload = _payload("mocked-historical")
    for slate in payload["slates"]:
        scores = slate["mock_outcomes"]["treatment_scores"]
        last = slate["treatment"]["candidates"][-1]["roster_key"]
        scores[last] = 204.0
    report = evaluate_payload(payload)
    assert report["disposition"] == "legal-soft-law-mocked-incremental-only"
    assert report["historical_gate"]["selection_pass"] is True
    assert report["historical_gate"]["target_pass"] is False
    assert report["mocked_would_license"]["prospective_shadow_design"] is True
    assert report["mocked_would_license"]["target_200_track"] is False
    assert not any(report["licenses"].values())
    assert report["production_change_licensed"] is False


def test_mocked_runner_is_canonical_local_and_create_only(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "report.json"
    input_path.write_bytes(canonical_json(_payload()))
    report = runner.run(input_path, output_path)
    assert report["disposition"] == "legal-soft-law-mocked-mechanics-pass"
    assert output_path.read_bytes() == canonical_json(report)
    with pytest.raises(FileExistsError):
        runner.run(input_path, output_path)
    with pytest.raises(ValueError, match="local path"):
        runner._local_path("gs://bucket/object", label="input")
