from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import combinations

import numpy as np
import pytest

from nfl_dfs.research import lr8_full_source_shards as shards
from nfl_dfs.research import lr8_historical_arm as lr8
from nfl_dfs.research import lr8_training_source as training
from nfl_dfs.research import residual_world_columns as rw


def _digest(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _receipt(label: str, *, generation: str = "1") -> dict[str, object]:
    return {
        "uri": f"gs://lr8-fixture/{label}",
        "generation": generation,
        "sha256": _digest(label),
        "bytes": len(label) + 1,
    }


def _players() -> tuple[rw.PlayerSpec, ...]:
    rows: list[rw.PlayerSpec] = []
    positions = {
        "QB": 1,
        "RB": 4,
        "WR": 4,
        "TE": 2,
        "DST": 1,
    }
    teams = ("A", "B", "C", "D")
    opponents = {"A": "B", "B": "A", "C": "D", "D": "C"}
    games = {"A": "G1", "B": "G1", "C": "G2", "D": "G2"}
    serial = 0
    for position, count in positions.items():
        for offset in range(count):
            team = teams[(serial + offset) % len(teams)]
            rows.append(rw.PlayerSpec(
                player_id=f"{position}{offset}",
                position=position,
                team=team,
                opponent=opponents[team],
                game_id=games[team],
                salary=4_000,
            ))
        serial += count
    return tuple(sorted(rows, key=lambda row: row.player_id))


def _legal_rosters(
    players: tuple[rw.PlayerSpec, ...], *, count: int,
) -> tuple[tuple[str, ...], ...]:
    by_position = {
        position: tuple(
            player.player_id for player in players if player.position == position
        )
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    result: list[tuple[str, ...]] = []
    shapes = ((2, 3, 2), (2, 4, 1), (3, 3, 1))
    for qb in by_position["QB"]:
        for dst in by_position["DST"]:
            for rb_count, wr_count, te_count in shapes:
                for rbs in combinations(by_position["RB"], rb_count):
                    for wrs in combinations(by_position["WR"], wr_count):
                        for tes in combinations(by_position["TE"], te_count):
                            roster = rw.canonical_identity((qb, dst, *rbs, *wrs, *tes))
                            try:
                                lr8.audit_dk_classic_identity(players, roster)
                            except lr8.LR8Error:
                                continue
                            result.append(roster)
                            if len(result) == count:
                                return tuple(result)
    raise AssertionError("fixture did not produce enough legal rosters")


def _solver(rosters: tuple[tuple[str, ...], ...]):
    def solve(request: training.WorldSolveRequest) -> training.ExactWorldOptimum:
        label = f"evidence/{request.request_sha256}.json"
        return training.ExactWorldOptimum(
            roster=rosters[request.world_index % training.UNIQUE_OPTIMA_PER_BLOCK],
            request_sha256=request.request_sha256,
            objective_micro=0,
            evidence_receipts=(_receipt(label),),
            exact_optimal=True,
            canonical_roster_tiebreak=True,
            dk_classic_only=True,
            incumbent_no_goods_enforced=True,
            house_rules_applied=(),
        )

    return solve


@dataclass(frozen=True)
class GridFixture:
    cells: tuple[shards.CellShard, ...]
    canonical_sources: tuple[training.CanonicalSlateSource, ...]
    replay_blocks: tuple[training.PITReplayBlock, ...]
    solve_world: training.WorldSolver


@pytest.fixture(scope="module")
def grid() -> GridFixture:
    players = _players()
    rosters = _legal_rosters(players, count=41)
    candidates = rosters[:training.UNIQUE_OPTIMA_PER_BLOCK]
    incumbent = (rosters[training.UNIQUE_OPTIMA_PER_BLOCK],)
    solve_world = _solver(candidates)
    catalog_hash = training.catalog_sha256(players)
    incumbent_hash = training.identities_sha256(incumbent)
    player_ids = tuple(player.player_id for player in players)
    draws = np.zeros(
        (len(players), training.WORLDS_PER_BLOCK), dtype=np.float32, order="C"
    )
    draws.flags.writeable = False
    player_ids_hash = training.player_ids_sha256(player_ids)
    draws_hash = training.array_sha256(draws)

    canonical_by_key: dict[tuple[int, int], training.CanonicalSlateSource] = {}
    replay_rows: dict[tuple[int, str], list[training.ReplaySlateWorlds]] = {}
    prepared_cells: list[shards.PreparedCell] = []
    for index, (season, week, block) in enumerate(shards.EXPECTED_CELL_KEYS):
        source = canonical_by_key.get((season, week))
        if source is None:
            source = training.CanonicalSlateSource(
                season=season,
                week=week,
                panel_id=training.CANONICAL_PANEL_ID,
                players=players,
                incumbent_candidates=incumbent,
                catalog_sha256=catalog_hash,
                incumbent_candidates_sha256=incumbent_hash,
                catalog_source_receipts=(
                    _receipt(f"catalog/{season}/{week}.json"),
                ),
                incumbent_source_receipts=(
                    _receipt(f"incumbent/{season}/{week}.json"),
                ),
                candidate_totals_loaded=False,
                outcome_fields_read=(),
            )
            canonical_by_key[(season, week)] = source
        replay_row = training.ReplaySlateWorlds(
            season=season,
            week=week,
            player_ids=player_ids,
            player_draws=draws,
            player_ids_sha256=player_ids_hash,
            player_draws_sha256=draws_hash,
            source_receipts=(
                _receipt(f"draw/{season}/{week}/{block}.bin"),
            ),
            target_outcome_fields_read=(),
        )
        replay_rows.setdefault((season, block), []).append(replay_row)
        prepared_cells.append(shards.prepare_cell(
            cell_index=index,
            canonical_source=source,
            replay=shards.PITCellReplay(
                target_season=season,
                block=block,
                projection_seed=training.BLOCK_SEED_PAIRS[block][0],
                source_environment_role_seed_nonoperative=(
                    training.BLOCK_SEED_PAIRS[block][1]
                ),
                replay_path_id=training.PIT_REPLAY_PATH_ID,
                model_training_seasons=training.MODEL_TRAINING_SEASONS[season],
                model_fit_input_sha256=_digest(f"fit-input/{season}"),
                model_fit_sha256=_digest(f"fit-model/{season}"),
                fit_source_receipts=(
                    _receipt(f"fit-source/{season}.json"),
                ),
                slate=replay_row,
            ),
        ))

    cell_shards = tuple(shards.solve_prepared_cell(
        prepared,
        solve_world,
        preparation_receipt=_receipt(
            f"prepared/{prepared.cell_index}.json",
            generation=str(prepared.cell_index + 1),
        ),
        execution_attempt_receipt=_receipt(
            f"attempt/{prepared.cell_index}.json",
            generation=str(prepared.cell_index + 101),
        ),
    ) for prepared in prepared_cells)
    replay_blocks = tuple(training.PITReplayBlock(
        target_season=season,
        block=block,
        projection_seed=training.BLOCK_SEED_PAIRS[block][0],
        source_environment_role_seed_nonoperative=training.BLOCK_SEED_PAIRS[block][1],
        replay_path_id=training.PIT_REPLAY_PATH_ID,
        model_training_seasons=training.MODEL_TRAINING_SEASONS[season],
        model_fit_input_sha256=_digest(f"fit-input/{season}"),
        model_fit_sha256=_digest(f"fit-model/{season}"),
        fit_source_receipts=(_receipt(f"fit-source/{season}.json"),),
        slates=tuple(replay_rows[(season, block)]),
    ) for season in training.TARGET_SEASONS for block in training.BLOCK_ORDER)
    return GridFixture(
        cells=cell_shards,
        canonical_sources=tuple(
            canonical_by_key[key] for key in training.EXPECTED_SLATE_KEYS
        ),
        replay_blocks=replay_blocks,
        solve_world=solve_world,
    )


def _replace_cell(
    cells: tuple[shards.CellShard, ...],
    index: int,
    value: shards.CellShard,
) -> tuple[shards.CellShard, ...]:
    result = list(cells)
    result[index] = value
    return tuple(result)


def _rehash_prepared(value: shards.PreparedCell) -> shards.PreparedCell:
    result = replace(value, prepared_cell_sha256="")
    object.__setattr__(
        result,
        "prepared_cell_sha256",
        training.canonical_sha256(shards._prepared_payload(result)),
    )
    return result


def test_exact_cell_order_and_byte_equivalent_authoritative_freeze(grid: GridFixture):
    assert shards.EXPECTED_CELLS == 70
    assert shards.EXPECTED_CELL_KEYS[:4] == (
        (2019, 1, "R0"),
        (2019, 1, "R1"),
        (2019, 2, "R0"),
        (2019, 2, "R1"),
    )
    assert shards.EXPECTED_CELL_KEYS[-2:] == (
        (2021, 18, "R0"),
        (2021, 18, "R1"),
    )
    aggregate = shards.aggregate_cell_shards(grid.cells)
    monolithic = training.build_training_source(
        grid.canonical_sources,
        grid.replay_blocks,
        grid.solve_world,
    )
    expected_bytes = training.canonical_json(
        training.freeze_training_source(monolithic)
    )
    assert aggregate.freeze_bytes == expected_bytes
    assert training.canonical_json(aggregate.freeze_manifest) == expected_bytes
    assert len(aggregate.bundle.slates) == training.EXPECTED_SLATES
    assert len(aggregate.cell_provenance) == shards.EXPECTED_CELLS
    assert "cell_provenance" not in aggregate.freeze_manifest
    # R0/R1 deliberately overlap completely in this fixture.  The aggregate
    # must merge, rather than duplicate or reject, those scientific rows.
    first = aggregate.bundle.slates[0]
    assert first.cross_block_duplicates == 40
    assert len(first.post_cross_block_candidates) == 40
    assert all(
        candidate.source_occurrences[0][0] == "R0"
        and candidate.source_occurrences[1][0] == "R1"
        for candidate in first.post_cross_block_candidates
    )


def test_cell_gap_duplicate_and_order_poisons(grid: GridFixture):
    with pytest.raises(shards.LR8FullSourceShardError, match="exactly 70"):
        shards.aggregate_cell_shards(grid.cells[:-1])
    duplicate = (grid.cells[0], grid.cells[0], *grid.cells[2:])
    with pytest.raises(shards.LR8FullSourceShardError, match="registered order"):
        shards.aggregate_cell_shards(duplicate)
    reordered = (grid.cells[1], grid.cells[0], *grid.cells[2:])
    with pytest.raises(shards.LR8FullSourceShardError, match="registered order"):
        shards.aggregate_cell_shards(reordered)


def test_hash_and_exact_draw_byte_poisons(grid: GridFixture):
    bad_hash = replace(grid.cells[0], shard_sha256="0" * 64)
    with pytest.raises(shards.LR8FullSourceShardError, match="envelope hash"):
        shards.aggregate_cell_shards(_replace_cell(grid.cells, 0, bad_hash))

    original = grid.cells[0]
    raw = bytearray(original.prepared.player_draws_bytes)
    raw[0:4] = np.float32(1.0).tobytes()
    bad_prepared = replace(original.prepared, player_draws_bytes=bytes(raw))
    bad_draw = replace(original, prepared=bad_prepared)
    with pytest.raises(shards.LR8FullSourceShardError, match="draw byte hash"):
        shards.aggregate_cell_shards(_replace_cell(grid.cells, 0, bad_draw))


def test_generation_pinned_slate_and_fit_receipt_drift_poison(grid: GridFixture):
    original = grid.cells[1]
    receipt = original.prepared.catalog_source_receipts[0]
    prepared = _rehash_prepared(replace(
        original.prepared,
        catalog_source_receipts=(replace(receipt, generation="999"),),
    ))
    rewrapped = shards.wrap_cell_shard(
        prepared,
        original.frozen_block,
        preparation_receipt=original.preparation_receipt,
        execution_attempt_receipt=original.execution_attempt_receipt,
    )
    with pytest.raises(shards.LR8FullSourceShardError, match="slate source receipts"):
        shards.aggregate_cell_shards(_replace_cell(grid.cells, 1, rewrapped))

    fit_receipt = original.prepared.fit_source_receipts[0]
    fit_prepared = _rehash_prepared(replace(
        original.prepared,
        fit_source_receipts=(replace(fit_receipt, generation="998"),),
    ))
    fit_rewrapped = shards.wrap_cell_shard(
        fit_prepared,
        original.frozen_block,
        preparation_receipt=original.preparation_receipt,
        execution_attempt_receipt=original.execution_attempt_receipt,
    )
    with pytest.raises(shards.LR8FullSourceShardError, match="PIT fit binding"):
        shards.aggregate_cell_shards(_replace_cell(grid.cells, 1, fit_rewrapped))


@pytest.mark.parametrize("attempt_count", [39, 81])
def test_solve_attempt_count_must_be_within_40_and_80(
    grid: GridFixture, attempt_count: int,
):
    original = grid.cells[0]
    attempts = original.frozen_block.solve_attempts
    poisoned_attempts = (
        attempts[:attempt_count]
        if attempt_count <= len(attempts)
        else tuple(attempts[index % len(attempts)] for index in range(attempt_count))
    )
    block = replace(original.frozen_block, solve_attempts=poisoned_attempts)
    poisoned = replace(original, frozen_block=block)
    with pytest.raises(shards.LR8FullSourceShardError, match="40..80"):
        shards.aggregate_cell_shards(_replace_cell(grid.cells, 0, poisoned))


def test_cross_block_occurrence_poison_is_rejected(grid: GridFixture):
    original = grid.cells[1]
    candidate = original.frozen_block.candidates[0]
    poisoned_candidate = replace(
        candidate,
        source_occurrences=(("R0", candidate.first_source_world_index),),
    )
    block = replace(
        original.frozen_block,
        candidates=(poisoned_candidate, *original.frozen_block.candidates[1:]),
    )
    poisoned = replace(original, frozen_block=block)
    with pytest.raises(
        shards.LR8FullSourceShardError,
        match="cross-block source occurrences",
    ):
        shards.aggregate_cell_shards(_replace_cell(grid.cells, 1, poisoned))


def test_attempt_and_execution_receipt_poisons(grid: GridFixture):
    original = grid.cells[0]
    attempt = original.frozen_block.solve_attempts[0]
    evidence = dict(attempt.evidence_receipts[0])
    evidence["generation"] = "9999"
    poisoned_attempt = replace(attempt, evidence_receipts=(evidence,))
    block = replace(
        original.frozen_block,
        solve_attempts=(poisoned_attempt, *original.frozen_block.solve_attempts[1:]),
    )
    poisoned = replace(original, frozen_block=block)
    with pytest.raises(shards.LR8FullSourceShardError, match="receipt differs"):
        shards.aggregate_cell_shards(_replace_cell(grid.cells, 0, poisoned))

    execution = replace(
        original.execution_attempt_receipt,
        generation=str(int(original.execution_attempt_receipt.generation) + 1),
    )
    execution_poison = replace(original, execution_attempt_receipt=execution)
    with pytest.raises(shards.LR8FullSourceShardError, match="envelope hash"):
        shards.aggregate_cell_shards(
            _replace_cell(grid.cells, 0, execution_poison)
        )


def test_preparation_rejects_noncontiguous_or_nonfinite_draws(grid: GridFixture):
    prepared = grid.cells[0].prepared
    source = training.CanonicalSlateSource(
        season=prepared.season,
        week=prepared.week,
        panel_id=training.CANONICAL_PANEL_ID,
        players=prepared.players,
        incumbent_candidates=prepared.incumbent_candidates,
        catalog_sha256=prepared.catalog_sha256,
        incumbent_candidates_sha256=prepared.incumbent_candidates_sha256,
        catalog_source_receipts=tuple(
            receipt.as_dict() for receipt in prepared.catalog_source_receipts
        ),
        incumbent_source_receipts=tuple(
            receipt.as_dict() for receipt in prepared.incumbent_source_receipts
        ),
    )
    base = np.frombuffer(
        prepared.player_draws_bytes, dtype=np.float32
    ).reshape(prepared.player_draws_shape)
    noncontiguous = np.zeros(
        (prepared.player_draws_shape[1], prepared.player_draws_shape[0]),
        dtype=np.float32,
    ).T
    assert not noncontiguous.flags.c_contiguous

    def replay(draws: np.ndarray) -> shards.PITCellReplay:
        return shards.PITCellReplay(
            target_season=prepared.season,
            block=prepared.block,
            projection_seed=prepared.projection_seed,
            source_environment_role_seed_nonoperative=(
                prepared.source_environment_role_seed_nonoperative
            ),
            replay_path_id=prepared.replay_path_id,
            model_training_seasons=prepared.model_training_seasons,
            model_fit_input_sha256=prepared.model_fit_input_sha256,
            model_fit_sha256=prepared.model_fit_sha256,
            fit_source_receipts=prepared.fit_source_receipts,
            slate=training.ReplaySlateWorlds(
                season=prepared.season,
                week=prepared.week,
                player_ids=prepared.player_ids,
                player_draws=draws,
                player_ids_sha256=prepared.player_ids_sha256,
                player_draws_sha256=training.array_sha256(draws),
                source_receipts=prepared.draw_source_receipts,
            ),
        )

    with pytest.raises(shards.LR8FullSourceShardError, match="contiguous"):
        shards.prepare_cell(
            cell_index=prepared.cell_index,
            canonical_source=source,
            replay=replay(noncontiguous),
        )
    poisoned = np.array(base, copy=True, order="C")
    poisoned[0, 0] = np.nan
    with pytest.raises(shards.LR8FullSourceShardError, match="contiguous"):
        shards.prepare_cell(
            cell_index=prepared.cell_index,
            canonical_source=source,
            replay=replay(poisoned),
        )
