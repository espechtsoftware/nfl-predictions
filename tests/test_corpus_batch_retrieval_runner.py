from __future__ import annotations

from itertools import combinations, product

import numpy as np
import pytest

from nfl_dfs.research import corpus_batch_retrieval_runner as runner
from nfl_dfs.research import corpus_legal_feasibility as core
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.lr8_later_period_source import PreparedLaterSlate


def _players() -> tuple[rw.PlayerSpec, ...]:
    rows = (
        ("q-a", "QB", "A", "B", "g1"), ("q-c", "QB", "C", "D", "g2"),
        ("rb-a1", "RB", "A", "B", "g1"), ("rb-a2", "RB", "A", "B", "g1"),
        ("rb-b", "RB", "B", "A", "g1"), ("rb-c", "RB", "C", "D", "g2"),
        ("rb-d", "RB", "D", "C", "g2"), ("rb-e", "RB", "E", "F", "g3"),
        ("wr-a1", "WR", "A", "B", "g1"), ("wr-a2", "WR", "A", "B", "g1"),
        ("wr-b", "WR", "B", "A", "g1"), ("wr-c1", "WR", "C", "D", "g2"),
        ("wr-c2", "WR", "C", "D", "g2"), ("wr-d", "WR", "D", "C", "g2"),
        ("wr-e", "WR", "E", "F", "g3"), ("wr-f", "WR", "F", "E", "g3"),
        ("te-a", "TE", "A", "B", "g1"), ("te-b", "TE", "B", "A", "g1"),
        ("te-c", "TE", "C", "D", "g2"), ("te-d", "TE", "D", "C", "g2"),
        ("te-e", "TE", "E", "F", "g3"), ("dst-b", "DST", "B", "A", "g1"),
        ("dst-c", "DST", "C", "D", "g2"), ("dst-e", "DST", "E", "F", "g3"),
    )
    return tuple(sorted((
        rw.PlayerSpec(pid, pos, team, opp, gid, 5_500)
        for pid, pos, team, opp, gid in rows
    ), key=lambda player: player.player_id))


def _rosters(players, *, count):
    by_position = {
        position: [p.player_id for p in players if p.position == position]
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    result = []
    for qb, rbs, wrs, te, dst in product(
        by_position["QB"], combinations(by_position["RB"], 2),
        combinations(by_position["WR"], 4), by_position["TE"],
        by_position["DST"],
    ):
        roster = tuple(sorted((qb, *rbs, *wrs, te, dst)))
        try:
            core.audit_dk_classic(players, roster)
        except core.CorpusLegalFeasibilityError:
            continue
        result.append(roster)
        if len(result) == count:
            return tuple(result)
    raise AssertionError("fixture universe too small")


def _prepared(players) -> PreparedLaterSlate:
    row = np.arange(len(players), dtype=np.float32)[:, None]
    column = (
        np.arange(core.EXPECTED_WORLD_COUNT, dtype=np.float32)[None, :] % 11
    ) / np.float32(3.0)
    draws = np.ascontiguousarray(np.float32(12.0) + row / 7 + column)
    draws.flags.writeable = False
    return PreparedLaterSlate(
        season=2023, week=1, slate_id="2023-w01",
        players=players,
        world_ids=tuple(
            rw.WorldId(block, index)
            for block in rw.WORLD_BLOCKS
            for index in range(rw.WORLDS_PER_BLOCK)
        ),
        player_draws=draws,
        incumbent_candidates=(),
        source_freeze_sha256="a" * 64,
        artifact_sha256_by_block={
            block: f"{ordinal + 1:064x}"
            for ordinal, block in enumerate(rw.WORLD_BLOCKS)
        },
    )


def _variant_result(prepared, rosters, parameter_set_id, ordinal):
    unique, _ = core.first_occurrence_unique(rosters)
    scores = core.cross_score_full_union(
        prepared.players, prepared.player_draws, unique
    )
    selected_indices = list(range(min(3, len(unique))))
    selected = np.ascontiguousarray(
        scores[np.asarray(selected_indices, dtype=np.int64)],
        dtype=np.float64,
    )
    selected.flags.writeable = False
    return {
        "slate": {"season": 2023, "week": 1, "slate_id": "2023-w01"},
        "later_source_freeze_manifest_sha256": "a" * 64,
        "artifact_sha256_by_block": dict(
            prepared.artifact_sha256_by_block
        ),
        "profile": {"ordinal": ordinal,
                    "parameter_set_id": parameter_set_id},
        "unique_rosters": [list(roster) for roster in unique],
        "candidate_score_sha256": core._score_matrix_sha256(scores),
        "selector": {"selected_indices": selected_indices},
        "selected_score_sha256": core._score_matrix_sha256(selected),
    }


@pytest.fixture(scope="module")
def surface():
    players = _players()
    rosters = _rosters(players, count=250)
    prepared = _prepared(players)
    return players, rosters, prepared


def test_reconstruction_verifies_and_rejects_tampering(
    surface, monkeypatch
):
    players, rosters, prepared = surface
    monkeypatch.setattr(
        runner, "prepare_later_slate",
        lambda *args, **kwargs: prepared,
    )
    variants = [
        _variant_result(prepared, rosters[:60], "incumbent", 0),
        _variant_result(prepared, rosters[40:120], "remove-qb-stack", 1),
    ]
    bodies = {
        block: f"body-{block}".encode()
        for block in rw.WORLD_BLOCKS
    }
    expected = {
        block: __import__("hashlib").sha256(raw).hexdigest()
        for block, raw in bodies.items()
    }
    for variant in variants:
        variant["artifact_sha256_by_block"] = expected
    result = runner.reconstruct_and_verify(
        variants, source_freeze={}, artifact_bodies=bodies,
    )
    assert all(row["verified"] for row in result["arm_receipts"])
    # Cross-arm union is first-occurrence: 60 + 80 with 20 overlapping.
    assert len(result["union_rosters"]) == 120
    assert result["union_scores"].shape == (
        120, core.EXPECTED_WORLD_COUNT
    )
    tampered = [dict(variants[0]), variants[1]]
    rotated = list(tampered[0]["unique_rosters"])
    tampered[0]["unique_rosters"] = rotated[1:] + rotated[:1]
    with pytest.raises(
        runner.CorpusBatchRetrievalError, match="reconstructed candidate"
    ):
        runner.reconstruct_and_verify(
            tampered, source_freeze={}, artifact_bodies=bodies,
        )


def test_matchup_scores_apply_starter_gate():
    rosters = [("a", "b"), ("c", "d"), ("x", "y")]
    rows = [
        {"gsis_id": "a", "family": "receiver", "matchup_edge_score": 0.8},
        {"gsis_id": "b", "family": "qb", "matchup_edge_score": 0.9,
         "qb_depth1": False},
        {"gsis_id": "c", "family": "qb", "matchup_edge_score": 0.6,
         "qb_depth1": True},
    ]
    scores = runner.matchup_lineup_scores(rosters, rows)
    assert scores[0] == pytest.approx(0.8)  # backup QB ignored
    assert scores[1] == pytest.approx(0.6)
    assert scores[2] == pytest.approx(0.0)


def test_retrieval_surface_builds_all_declared_books(surface):
    players, rosters, prepared = surface
    unique, _ = core.first_occurrence_unique(rosters)
    scores = core.cross_score_full_union(
        players, prepared.player_draws, unique
    )
    rng = np.random.default_rng(3)
    lineup_matchup = rng.uniform(size=len(unique))
    incumbent = {"incumbent": [list(r) for r in unique[:80]]}
    receipt = runner.run_retrieval_surface(
        union_rosters=unique,
        union_scores=scores,
        incumbent_books=incumbent,
        lineup_matchup=lineup_matchup,
    )
    books = receipt["books"]
    assert "incumbent:incumbent" in books
    for mode in runner.ADMISSION_MODES:
        for strategy_id in (
            "expected-max-v1", "block-supported-tail-ladder-v1",
            "regime-robust-ladder-v1",
        ):
            key = f"{mode}:{strategy_id}"
            assert key in books
            assert books[key]["book_size"] == 80
    assert receipt["matchup_admitted_count"] == runner.ADMISSION_M
    assert receipt["adoption_authority"] is False
    full = books["full-union:expected-max-v1"]
    assert full["discovery_expected_max"] > 0
    assert "heldout_expected_max_descriptive" in full
