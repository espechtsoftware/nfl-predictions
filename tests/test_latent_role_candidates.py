import hashlib

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest import engine
from nfl_dfs.optimizer.lineup import Lineup


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _promotion(sequence: int, marker: float) -> tuple[str, np.ndarray]:
    source = ("inactive", "dormant", "rotation", "secondary")[sequence - 1]
    promoted = ("dormant", "rotation", "secondary", "primary")[sequence - 1]
    name = (
        f"latent_promotion:{sequence}:player-{sequence}:"
        f"{source}>{promoted}:{_sha(f'promotion-{sequence}')}"
    )
    return name, np.full(30, marker, dtype=float)


def _sample(attempt: int, marker: float) -> tuple[str, np.ndarray]:
    name = f"latent_sampled:{attempt}:draw:{attempt + 100}:{_sha(f'sample-{attempt}')}"
    return name, np.full(30, marker, dtype=float)


def _players() -> list[dict]:
    return [
        {
            "id": f"p{index:02d}",
            "name": f"P{index:02d}",
            "pos": "WR",
            "team": "A",
            "opp": "B",
            "game_id": "A-B",
            "salary": 5_000,
            "proj": 10.0,
        }
        for index in range(30)
    ]


def test_latent_scenario_contract_is_strict_and_copies_vectors():
    scenarios = [*(_promotion(i, float(i)) for i in range(1, 5))]
    scenarios.extend(_sample(i, float(i)) for i in range(1, 10))
    validated = engine._validated_latent_role_scenarios(
        scenarios, n_players=30, n_slots=12,
    )
    assert len(validated) == 13
    scenarios[0][1][0] = 999.0
    assert validated[0][1][0] == 1.0

    malformed = list(validated)
    malformed[4] = (malformed[4][0].replace(_sha("sample-1"), "x" * 64),
                    malformed[4][1])
    with pytest.raises(ValueError, match="sampled identity"):
        engine._validated_latent_role_scenarios(
            malformed, n_players=30, n_slots=12,
        )

    reversed_attempts = list(validated)
    reversed_attempts[4], reversed_attempts[5] = (
        reversed_attempts[5], reversed_attempts[4]
    )
    with pytest.raises(ValueError, match="strictly ordered"):
        engine._validated_latent_role_scenarios(
            reversed_attempts, n_players=30, n_slots=12,
        )


def test_latent_candidate_dose_consumes_failures_and_duplicates(monkeypatch):
    players = _players()
    scenarios = [*(_promotion(i, float(i)) for i in range(1, 5))]
    scenarios.extend(_sample(i, float(i)) for i in range(5, 17))
    existing = frozenset(player["id"] for player in players[21:30])

    def fake_optimize(pool, **kwargs):
        marker = int(pool[0]["proj_epi"])
        if marker == 5:
            return Lineup(players=players[21:30])
        if marker == 6:
            raise RuntimeError("solver unavailable")
        if marker == 7:
            return None
        if marker == 8:
            return Lineup(players=players[0:9])
        start = marker - 1 if marker <= 4 else marker - 5
        return Lineup(players=players[start:start + 9])

    monkeypatch.setattr(engine, "optimize", fake_optimize)
    receipt: list[dict] = []
    generated = engine._latent_role_candidates(
        players,
        scenarios,
        stack=None,
        locks=set(),
        env={},
        existing={existing},
        optimization_receipt=receipt,
    )
    assert len(generated) == 12
    assert [name.split(":")[1] for _, name in generated[:4]] == [
        "1", "2", "3", "4",
    ]
    assert [int(name.split(":")[1]) for _, name in generated[4:]] == list(
        range(9, 17)
    )
    assert [row["disposition"] for row in receipt[4:8]] == [
        "duplicate", "optimization_error", "infeasible", "duplicate",
    ]
    assert len(receipt) == 16
    assert sum(row["disposition"] == "accepted" for row in receipt) == 12
    assert all(
        row["roster_sha256"] is None
        or len(row["roster_sha256"]) == 64
        for row in receipt
    )


def test_latent_promotion_duplicate_invalidates_and_records(monkeypatch):
    players = _players()
    scenarios = [*(_promotion(i, float(i)) for i in range(1, 5))]
    scenarios.extend(_sample(i, float(i)) for i in range(1, 9))
    duplicate = Lineup(players=players[:9])
    monkeypatch.setattr(engine, "optimize", lambda *args, **kwargs: duplicate)
    receipt: list[dict] = []
    with pytest.raises(RuntimeError, match="not a novel optimum"):
        engine._latent_role_candidates(
            players,
            scenarios,
            stack=None,
            locks=set(),
            env={},
            existing={duplicate.ids},
            optimization_receipt=receipt,
        )
    assert receipt[0]["kind"] == "promotion"
    assert receipt[0]["disposition"] == "duplicate"
    assert len(receipt[0]["roster_sha256"]) == 64


def test_tail_engine_routes_exact_latent_dose_into_captured_book(monkeypatch):
    players = _players()
    for index, player in enumerate(players):
        player["actual"] = 10.0
        player["draw_idx"] = index
        player["season"] = 2026
        player["week"] = 1
    slate = pd.DataFrame(players)
    draws = np.stack([
        np.full(20, index + 1.0, dtype=float)
        for index in range(len(players))
    ])
    existing = Lineup(players=players[21:30], tag="lev")
    monkeypatch.setattr(engine, "optimize_many", lambda *args, **kwargs: [existing])

    def fake_optimize(pool, **kwargs):
        marker = int(pool[0]["proj_epi"])
        return Lineup(players=players[marker - 1:marker + 8])

    monkeypatch.setattr(engine, "optimize", fake_optimize)
    scenarios = [*(_promotion(i, float(i)) for i in range(1, 5))]
    scenarios.extend(_sample(i, float(i + 4)) for i in range(1, 9))
    optimization_receipt: list[dict] = []
    captured = []
    env = {
        "GEN_TOTAL_BUDGET": "12",
        "N_EPISTEMIC": "12",
        "N_BOOM": "0",
        "EPISTEMIC_FAMILY": engine.LATENT_ROLE_FAMILY,
        "N_QB_VARIANTS": "0",
        "N_GAMESTACK": "0",
        "N_DARKGAME": "0",
        "MIN_LINEUP_SALARY": "0",
    }
    selected = engine.tail_select_lineups(
        slate,
        players,
        draws,
        tail_line=194.0,
        n_entries=2,
        stack=None,
        objective_col="proj",
        policy_env=env,
        explicit_epistemic_scenarios=scenarios,
        latent_optimization_receipt=optimization_receipt,
        latent_scenario_receipt={
            "uses_realized_outcomes": False,
            "artifact_sha256": _sha("artifact"),
        },
        candidate_capture=captured.append,
    )
    assert len(selected) == 2
    assert len(captured) == 1
    batch = captured[0]
    assert len(batch.candidates) == 13
    assert sum(lineup.tag == "epi" for lineup in batch.candidates) == 12
    assert len(optimization_receipt) == 12
    assert all(
        row["disposition"] == "accepted" for row in optimization_receipt
    )
    assert batch.metadata["latent_optimization_receipt"] == tuple(
        optimization_receipt
    )
    assert batch.metadata["latent_scenario_receipt"][
        "uses_realized_outcomes"
    ] is False
