from __future__ import annotations

import hashlib

import numpy as np
import pytest

from nfl_dfs.inference import week1_participation_mixture as pmix


def _players() -> list[str]:
    return [f"p{index:03d}" for index in range(100)]


def _rosters(players: list[str]) -> list[list[str]]:
    return [
        [players[(start + offset) % len(players)] for offset in range(9)]
        for start in range(90)
    ]


def _lineup_ids(rosters: list[list[str]]) -> list[str]:
    return [
        "lineup-v1-" + hashlib.sha256("|".join(sorted(roster)).encode()).hexdigest()
        for roster in rosters
    ]


def _artifact() -> dict[str, object]:
    return {
        "uri": "gs://nfl-predictions-503414-raw/week1/prelock/injury.json",
        "generation": "123",
        "sha256": "a" * 64,
        "bytes": 1234,
    }


def _snapshot(players: list[str], *, status: str = "Questionable") -> dict:
    return pmix.build_prelock_snapshot_v1(
        player_ids=players,
        observations=[
            {
                "player_id": players[0],
                "injury_status": status,
                "practice_level": "DNP",
                "source_modified_at": "2026-09-03T20:00:00+00:00",
            },
            {
                "player_id": players[1],
                "injury_status": "Doubtful",
                "practice_level": "LIMITED",
                "source_modified_at": "2026-09-03T20:01:00+00:00",
            },
        ],
        provider="nflverse-injuries",
        provider_observed_at="2026-09-03T20:05:00+00:00",
        ingested_at="2026-09-03T20:06:00+00:00",
        cutoff_at="2026-09-03T20:10:00+00:00",
        max_snapshot_age_seconds=600,
        raw_artifact=_artifact(),
    )


def _map() -> dict:
    history = []
    for season in (2022, 2023, 2024, 2025):
        history.extend([
            {
                "season": season,
                "injury_status": "Questionable",
                "practice_level": 0,
                "was_active": season in {2023, 2024},
            },
            {
                "season": season,
                "injury_status": "Doubtful",
                "practice_level": 1,
                "was_active": season == 2024,
            },
        ])
    return pmix.fit_participation_map_v1(history)


def _selection_inputs() -> dict[str, object]:
    players = _players()
    rosters = _rosters(players)
    rng = np.random.default_rng(44)
    return {
        "player_ids": players,
        "lineup_ids": _lineup_ids(rosters),
        "rosters": rosters,
        "incumbent_player_scores": rng.uniform(0, 35, size=(100, 64)).astype(np.float32),
        "corrected_hsim_player_scores": rng.uniform(0, 35, size=(100, 64)).astype(np.float32),
        "snapshot": _snapshot(players),
        "participation_map": _map(),
        "mixture_seed": 2157,
    }


def test_snapshot_retains_raw_values_and_explicit_absence() -> None:
    players = _players()
    snapshot = _snapshot(players)

    assert snapshot["rows"][0]["raw_injury_status"] == "Questionable"
    assert snapshot["rows"][0]["injury_status"] == "Questionable"
    assert snapshot["rows"][0]["practice_level"] == 0
    assert snapshot["rows"][2]["provider_row_present"] is False
    assert snapshot["rows"][2]["injury_status"] is None
    assert snapshot["outcome_fields_read"] == []
    assert pmix.validate_prelock_snapshot_v1(snapshot, player_ids=players) == snapshot


def test_snapshot_rejects_unknown_and_stale_inputs() -> None:
    players = _players()
    with pytest.raises(pmix.Week1ParticipationMixtureError, match="unknown injury"):
        _snapshot(players, status="Maybe")

    with pytest.raises(pmix.Week1ParticipationMixtureError, match="stale"):
        pmix.build_prelock_snapshot_v1(
            player_ids=players,
            observations=[],
            provider="nflverse-injuries",
            provider_observed_at="2026-09-03T19:00:00+00:00",
            ingested_at="2026-09-03T19:01:00+00:00",
            cutoff_at="2026-09-03T20:10:00+00:00",
            max_snapshot_age_seconds=600,
            raw_artifact=_artifact(),
        )


def test_snapshot_hash_tamper_fails_closed() -> None:
    players = _players()
    snapshot = _snapshot(players)
    snapshot["rows"][0]["practice_level"] = 2
    with pytest.raises(pmix.Week1ParticipationMixtureError, match="SHA-256"):
        pmix.validate_prelock_snapshot_v1(snapshot, player_ids=players)


def test_map_is_prior_season_only_and_beta_smoothed() -> None:
    fitted = _map()
    assert fitted["trained_seasons"] == [2022, 2023, 2024, 2025]
    assert fitted["p_active"]["Questionable|0"] == pytest.approx(0.5)
    assert fitted["p_active"]["Doubtful|1"] == pytest.approx(0.375)
    assert fitted["map_sha256"]


def test_selection_is_same_supply_exact_k_and_replayable() -> None:
    inputs = _selection_inputs()
    first = pmix.build_participation_selection_v1(**inputs)
    second = pmix.build_participation_selection_v1(**inputs)

    assert first == second
    assert len(first["P_CTRL"]["ordered_lineup_ids"]) == 80
    assert len(first["P_MIX"]["ordered_lineup_ids"]) == 80
    assert first["candidate_count"] == 90
    assert first["designation_count"] == 2
    assert first["outcome_fields_read"] == []
    assert list(map(int, first["a5_prefixes"])) == [3, 10, 20, 57]
    for prefix in (3, 10, 20, 57):
        view = first["a5_prefixes"][str(prefix)]
        assert len(view["P_CTRL"]) == prefix
        assert len(view["P_MIX"]) == prefix

    certificate = pmix.certify_participation_replay_v1(**inputs)
    assert certificate["deterministic_exact_replay"] is True
    assert certificate["selection_receipt_sha256"] == first[
        "selection_receipt_sha256"
    ]
    assert certificate["fallback_on_any_validation_failure"] == "P_CTRL"


def test_missing_live_probability_fails_to_control_fallback_boundary() -> None:
    inputs = _selection_inputs()
    participation_map = dict(inputs["participation_map"])
    participation_map["p_active"] = {
        "Questionable|0": participation_map["p_active"]["Questionable|0"]
    }
    base = dict(participation_map)
    base.pop("map_sha256")
    from nfl_dfs.inference.generation_exposure import canonical_sha256

    participation_map["map_sha256"] = canonical_sha256(base)
    inputs["participation_map"] = participation_map
    with pytest.raises(pmix.Week1ParticipationMixtureError, match="lacks live class"):
        pmix.build_participation_selection_v1(**inputs)


def test_out_player_in_candidate_supply_fails_closed() -> None:
    inputs = _selection_inputs()
    inputs["snapshot"] = _snapshot(inputs["player_ids"], status="Out")
    with pytest.raises(pmix.Week1ParticipationMixtureError, match="designated Out"):
        pmix.build_participation_selection_v1(**inputs)
