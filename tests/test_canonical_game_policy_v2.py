"""Focused conformance tests for production canonical-game policy v2."""

from __future__ import annotations

from copy import deepcopy

import pytest

from nfl_dfs.optimizer.game_identity import (
    CANONICAL_GAME_POLICY_ID,
    audit_classic_roster_semantics,
    canonical_game_counts,
    player_game_identity,
    resolve_game_lock_key,
)
from nfl_dfs.optimizer.lineup import optimize
from nfl_dfs.research.candidate_features import candidate_aggregates
from nfl_dfs.backtest.engine import _canonical_game_projection
from nfl_dfs.research.corpus_r6_historical_neo4j_slice_v1 import (
    _dk_structural_phenotype,
)
from nfl_dfs.research.corpus_retrieval_engine import _lineup_features


def _player(
    player_id: int, pos: str, team: str, opp: str, game_id: str, proj: float,
) -> dict:
    return {
        "id": player_id,
        "name": f"P{player_id}",
        "pos": pos,
        "team": team,
        "opp": opp,
        "game_id": game_id,
        "salary": 5_000,
        "proj": proj,
    }


def _pool() -> list[dict]:
    # Two physical games, deliberately mixing provider IDs and directional
    # team strings, including historical LAR/LA aliases on the DST row.
    specs = [
        (1, "QB", "LA", "SEA", "2026_01_SEA_LA", 30),
        (2, "RB", "LA", "SEA", "2026_01_SEA_LA", 29),
        (3, "RB", "SEA", "LA", "2026_01_SEA_LA", 28),
        (4, "WR", "LA", "SEA", "2026_01_SEA_LA", 27),
        (5, "WR", "SEA", "LA", "2026_01_SEA_LA", 26),
        (6, "TE", "LA", "SEA", "2026_01_SEA_LA", 25),
        (7, "DST", "SEA", "LAR", "SEA@LAR", 24),
        (8, "QB", "KC", "BUF", "BUF@KC", 12),
        (9, "RB", "KC", "BUF", "KC@BUF", 11),
        (10, "RB", "BUF", "KC", "2026_01_BUF_KC", 10),
        (11, "WR", "KC", "BUF", "2026_01_BUF_KC", 9),
        (12, "WR", "BUF", "KC", "BUF@KC", 8),
        (13, "WR", "KC", "BUF", "KC@BUF", 7),
        (14, "TE", "BUF", "KC", "BUF@KC", 6),
        (15, "DST", "BUF", "KC", "BUF@KC", 5),
        (16, "WR", "SEA", "LA", "SEA@LA", 4),
        (17, "TE", "SEA", "LA", "SEA@LA", 3),
    ]
    return [_player(*spec) for spec in specs]


def test_mixed_nflverse_directional_and_dst_aliases_are_one_game() -> None:
    game_one = _pool()[:7]
    assert canonical_game_counts(game_one) == {"LA|SEA": 7}
    dst = player_game_identity(game_one[-1])
    assert dst.canonical_game_key == "LA|SEA"
    assert dst.raw_game_id == "SEA@LAR"


def test_backtest_top_and_dark_game_ranking_uses_physical_game() -> None:
    import pandas as pd

    ranked = _canonical_game_projection(pd.DataFrame(_pool()))
    assert list(ranked.index) == ["LA|SEA", "BUF|KC"]
    assert ranked["LA|SEA"] == sum(row["proj"] for row in _pool()[:7]) + 7


def test_one_physical_game_cannot_satisfy_two_game_rule() -> None:
    one_game = _pool()[:7] + [deepcopy(_pool()[3]), deepcopy(_pool()[4])]
    one_game[-2]["id"] = 103
    one_game[-2]["game_id"] = "LA@SEA"
    one_game[-1]["id"] = 104
    one_game[-1]["game_id"] = "SEA@LA"
    assert optimize(one_game, min_games=2) is None


def test_canonical_cap_and_representation_invariance() -> None:
    pool = _pool()
    first = optimize(pool, min_games=1, max_per_game=5)
    assert first is not None
    assert max(canonical_game_counts(first.players).values()) <= 5

    alternate = deepcopy(pool)
    for row in alternate:
        row["game_id"] = f"{row['team']}@{row['opp']}"
    second = optimize(alternate, min_games=1, max_per_game=5)
    assert second is not None
    assert first.ids == second.ids


def test_game_lock_includes_all_representations_and_fails_closed() -> None:
    pool = _pool()
    lineup = optimize(pool, game_lock=("2026_01_SEA_LA", 5))
    assert lineup is not None
    assert canonical_game_counts(lineup.players)["LA|SEA"] >= 5
    with pytest.raises(ValueError, match="zero matches"):
        optimize(pool, game_lock=("unknown", 1))
    with pytest.raises(ValueError, match="only 9 players"):
        optimize(pool, game_lock=("LA|SEA", 10))

    ambiguous = deepcopy(pool)
    ambiguous[7]["game_id"] = "2026_01_SEA_LA"
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_game_lock_key(ambiguous, "2026_01_SEA_LA", minimum=1)


def test_final_boundary_and_candidate_features_agree() -> None:
    lineup = optimize(_pool(), min_games=2, max_per_game=6)
    assert lineup is not None
    audit = audit_classic_roster_semantics(lineup.players)
    import pandas as pd

    features = candidate_aggregates(pd.DataFrame(_pool()), list(lineup.ids))
    assert audit["canonical_game_policy_id"] == CANONICAL_GAME_POLICY_ID
    assert features["canonical_game_policy_id"] == CANONICAL_GAME_POLICY_ID
    assert audit["canonical_game_count"] == features["canonical_n_games"]
    assert audit["canonical_max_players_same_game"] == (
        features["canonical_max_from_game"]
    )
    catalog = {str(row["id"]): row for row in lineup.players}
    roster = list(catalog)
    neo4j = _dk_structural_phenotype(roster, catalog)
    retrieval = _lineup_features(roster, catalog)
    assert neo4j["canonical_distinct_game_count"] == (
        audit["canonical_game_count"]
    )
    assert neo4j["canonical_maximum_same_game_count"] == (
        audit["canonical_max_players_same_game"]
    )
    assert retrieval["canonical_game_count"] == audit["canonical_game_count"]
    assert retrieval["canonical_max_players_same_game"] == (
        audit["canonical_max_players_same_game"]
    )

    invalid = deepcopy(lineup.players)
    invalid[0]["opp"] = invalid[0]["team"]
    with pytest.raises(ValueError, match="identical"):
        audit_classic_roster_semantics(invalid)
