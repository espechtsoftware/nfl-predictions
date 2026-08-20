"""Production transport for the licensed fixed-budget CBWU portfolio.

This module contains no feature construction, optimizer search, realized
scores, or post-lock inputs.  It combines complete native candidate books
using the frozen score-blind quota/fill law and cross-scores the resulting
rosters in equal independent world blocks.  The engine then applies its
unchanged exact production selector and persistence path.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
from itertools import combinations
import json

import numpy as np
import pandas as pd

from ..backtest.engine import CandidateBatch
from ..optimizer.lineup import Lineup, select_tail_entries
from .archetype_candidate_allocator import allocate_archetype_budget


def _canonical_roster(lineup: Lineup) -> frozenset:
    if len(lineup.players) != 9 or len(lineup.ids) != 9:
        raise ValueError("candidate roster must contain nine unique players")
    return lineup.ids


def _validate_native_book(
    name: str,
    batch: CandidateBatch,
    *,
    expected_worlds: int | None,
    tolerance: float,
) -> None:
    totals = np.asarray(batch.candidate_totals, dtype=np.float32)
    draws = np.asarray(batch.row_draws, dtype=np.float32)
    if totals.ndim != 2 or totals.shape[0] != len(batch.candidates):
        raise ValueError(f"{name} candidate totals are misaligned")
    if draws.ndim != 2 or draws.shape[0] != len(batch.player_ids):
        raise ValueError(f"{name} player worlds are misaligned")
    if draws.shape[1] != totals.shape[1]:
        raise ValueError(f"{name} candidate/player world counts differ")
    if expected_worlds is not None and totals.shape[1] != expected_worlds:
        raise ValueError(
            f"{name} has {totals.shape[1]} worlds; expected {expected_worlds}")
    if len(set(batch.player_ids)) != len(batch.player_ids):
        raise ValueError(f"{name} player ids repeat")
    id_to_row = {player_id: index for index, player_id in enumerate(
        batch.player_ids)}
    seen: set[frozenset] = set()
    for index, lineup in enumerate(batch.candidates):
        roster = _canonical_roster(lineup)
        if roster in seen:
            raise ValueError(f"{name} contains duplicate rosters")
        seen.add(roster)
        try:
            rows = [id_to_row[player_id] for player_id in roster]
        except KeyError as exc:
            raise ValueError(f"{name} roster is outside its player universe") \
                from exc
        reconstructed = draws[rows].sum(axis=0)
        if not np.allclose(
            reconstructed, totals[index], rtol=0.0, atol=tolerance
        ):
            raise ValueError(f"{name} native candidate totals do not reconstruct")


def _select_tail_entries_bitpacked(
    candidate_totals: np.ndarray,
    n_entries: int,
    tail_line: float,
) -> list[int]:
    """Exact binary-coverage selector with a compact score-free work matrix.

    This reproduces ``select_tail_entries(..., SELECT_LSE=0)`` but avoids
    rescanning one Boolean value per world for every remaining candidate at
    every greedy step. It is used only by the potentially much larger
    complete-union repair.
    """
    totals = np.asarray(candidate_totals)
    if totals.ndim != 2 or totals.shape[1] == 0 or not np.isfinite(totals).all():
        raise ValueError("CBWU-OI candidate totals must be one finite matrix")
    clears = totals >= float(tail_line)
    packed = np.packbits(clears, axis=1, bitorder="little")
    p_line = clears.mean(axis=1)
    mean_total = totals.mean(axis=1, dtype=np.float64)
    limit = min(int(n_entries), len(totals))
    selected: list[int] = []
    covered = np.zeros(packed.shape[1], dtype=np.uint8)
    remaining = set(range(len(totals)))
    # NumPy 1.26 is the package floor; ``np.bitwise_count`` is newer. A fixed
    # byte lookup preserves the same compact operation there.
    byte_popcount = np.unpackbits(
        np.arange(256, dtype=np.uint8)[:, None], axis=1
    ).sum(axis=1, dtype=np.uint8)
    while len(selected) < limit and remaining:
        gains = byte_popcount[
            np.bitwise_and(packed, np.bitwise_not(covered))
        ].sum(axis=1)
        best = max(
            remaining,
            key=lambda index: (
                int(gains[index]), p_line[index], mean_total[index]
            ),
        )
        if not gains[best]:
            break
        selected.append(best)
        covered |= packed[best]
        remaining.discard(best)
    fill = sorted(
        remaining,
        key=lambda index: (p_line[index], mean_total[index]),
        reverse=True,
    )
    selected += fill[:limit - len(selected)]
    return selected


def combine_cbwu_books(
    books: Mapping[str, CandidateBatch],
    seed_order: Sequence[str],
    *,
    expected_worlds_per_book: int | None = None,
    tolerance: float = 1e-4,
    fixed_candidate_budget: int | None = None,
) -> CandidateBatch:
    """Build the frozen fixed-budget candidate + world union.

    The candidate budget is the first seed's native pool size.  Exact-roster
    deduplication assigns a roster to the first seed that supplied it.  Source
    quotas and deterministic deficit filling use ``seed_order`` only; neither
    simulated nor realized score enters candidate allocation.
    """
    order = tuple(seed_order)
    if len(order) != 5 or len(set(order)) != 5:
        raise ValueError("CBWU requires exactly five distinct registered seeds")
    if set(books) != set(order):
        missing = sorted(set(order) - set(books))
        extra = sorted(set(books) - set(order))
        raise ValueError(
            f"CBWU seed books differ (missing={missing}, extra={extra})")

    base = books[order[0]]
    base_universe = set(base.player_ids)
    for name in order:
        batch = books[name]
        _validate_native_book(
            name, batch, expected_worlds=expected_worlds_per_book,
            tolerance=tolerance)
        if set(batch.player_ids) != base_universe:
            raise ValueError("CBWU player-id universes differ across seeds")

    budget = (
        len(base.candidates)
        if fixed_candidate_budget is None else int(fixed_candidate_budget)
    )
    if budget <= 0:
        raise ValueError("CBWU base candidate budget is empty")

    buckets: dict[str, list[tuple[Lineup, tuple[str, ...]]]] = {
        name: [] for name in order
    }
    seen: set[frozenset] = set()
    novelty: dict[str, int] = {}
    for name in order:
        batch = books[name]
        for lineup in batch.candidates:
            roster = _canonical_roster(lineup)
            if roster in seen:
                continue
            seen.add(roster)
            tags = batch.all_tags.get(roster, (lineup.tag or "lev",))
            buckets[name].append((lineup, tuple(tags)))
        novelty[name] = len(buckets[name])

    base_quota, remainder = divmod(budget, len(order))
    chosen: list[tuple[str, Lineup, tuple[str, ...]]] = []
    used = {name: 0 for name in order}
    for seed_index, name in enumerate(order):
        quota = base_quota + int(seed_index < remainder)
        take = min(quota, len(buckets[name]))
        chosen.extend(
            (name, lineup, tags)
            for lineup, tags in buckets[name][:take]
        )
        used[name] = take
    while len(chosen) < budget:
        advanced = False
        for name in order:
            if used[name] < len(buckets[name]):
                lineup, tags = buckets[name][used[name]]
                chosen.append((name, lineup, tags))
                used[name] += 1
                advanced = True
                if len(chosen) == budget:
                    break
        if not advanced:
            raise ValueError("CBWU union cannot fill the fixed candidate budget")

    base_by_id = dict(zip(base.player_ids, base.player_rows, strict=True))
    rebuilt: list[Lineup] = []
    all_tags: dict[frozenset, tuple[str, ...]] = {}
    source_counts = {name: 0 for name in order}
    for name, source, tags in chosen:
        players = [base_by_id[player["id"]] for player in source.players]
        lineup = Lineup(players, tag=source.tag)
        roster = lineup.ids
        source_tag = f"candidate_seed:{name}"
        combined_tags = tuple(dict.fromkeys((*tags, source_tag)))
        rebuilt.append(lineup)
        all_tags[roster] = combined_tags
        source_counts[name] += 1

    world_blocks: list[np.ndarray] = []
    row_blocks: list[np.ndarray] = []
    for world_name in order:
        world = books[world_name]
        world_index = {
            player_id: index for index, player_id in enumerate(world.player_ids)
        }
        rows_in_base_order = [world_index[player_id] for player_id in base.player_ids]
        aligned_draws = np.asarray(
            world.row_draws[rows_in_base_order], dtype=np.float32)
        row_blocks.append(aligned_draws)
        roster_totals = np.stack([
            aligned_draws[[
                index for index, player_id in enumerate(base.player_ids)
                if player_id in lineup.ids
            ]].sum(axis=0)
            for lineup in rebuilt
        ]).astype(np.float32)
        world_blocks.append(roster_totals)

    combined_totals = np.concatenate(world_blocks, axis=1)
    combined_rows = np.concatenate(row_blocks, axis=1)
    if combined_totals.shape != (budget, combined_rows.shape[1]):
        raise ValueError("CBWU combined candidate worlds are misaligned")

    return CandidateBatch(
        candidates=tuple(rebuilt),
        candidate_totals=combined_totals,
        player_ids=base.player_ids,
        player_rows=base.player_rows,
        row_draws=combined_rows,
        all_tags=all_tags,
        metadata={
            "portfolio": "CBWU",
            "candidate_budget": budget,
            "candidate_source_counts": source_counts,
            "novel_candidates_by_seed": novelty,
            "world_blocks": len(order),
            "worlds_per_block": [
                int(books[name].row_draws.shape[1]) for name in order
            ],
        },
    )


def combine_cbwu_order_invariant_books(
    books: Mapping[str, CandidateBatch],
    seed_order: Sequence[str],
    *,
    tail_line: float = 194.0,
    expected_worlds_per_book: int | None = None,
    tolerance: float = 1e-4,
) -> CandidateBatch:
    """Build the frozen CBWU-OI-v1 complete-union candidate book.

    ``seed_order`` is validated but deliberately cannot affect candidate
    identity, world-block order, attribution, or ranking.  Every distinct
    native roster is cross-scored on the canonical R0--R4 world blocks, then
    the unchanged tail selector admits exactly the registered R0 candidate
    budget.  This is an outcome-free research repair and is not called by the
    production policy.
    """
    if not np.isfinite(tail_line):
        raise ValueError("CBWU-OI tail line must be finite")
    supplied_order = tuple(seed_order)
    canonical_order = tuple(sorted(books))
    if len(supplied_order) != 5 or len(set(supplied_order)) != 5:
        raise ValueError("CBWU-OI requires five distinct registered seeds")
    if set(supplied_order) != set(books) or canonical_order != (
        "R0", "R1", "R2", "R3", "R4"
    ):
        raise ValueError("CBWU-OI requires exact registered seeds R0--R4")

    base = books["R0"]
    base_universe = set(base.player_ids)
    for name in canonical_order:
        batch = books[name]
        _validate_native_book(
            name,
            batch,
            expected_worlds=expected_worlds_per_book,
            tolerance=tolerance,
        )
        if set(batch.player_ids) != base_universe:
            raise ValueError("CBWU-OI player-id universes differ across seeds")
    budget = len(base.candidates)
    if budget <= 0:
        raise ValueError("CBWU-OI R0 candidate budget is empty")

    # Candidate identity and metadata are aggregated symmetrically.  No
    # first-supplier identity survives this boundary.
    union: dict[tuple[str, ...], dict[str, object]] = {}
    for name in canonical_order:
        batch = books[name]
        for lineup in batch.candidates:
            roster = tuple(sorted(str(player_id) for player_id in _canonical_roster(
                lineup
            )))
            tags = batch.all_tags.get(lineup.ids, (lineup.tag or "lev",))
            row = union.setdefault(roster, {"tags": set(), "seeds": set()})
            row["tags"].update(str(tag) for tag in tags)
            row["seeds"].add(name)
    roster_keys = sorted(union)
    if len(roster_keys) < budget:
        raise ValueError("CBWU-OI complete union cannot fill the R0 budget")

    base_by_id = {
        str(player_id): player
        for player_id, player in zip(base.player_ids, base.player_rows, strict=True)
    }
    try:
        union_lineups = [
            Lineup([base_by_id[player_id] for player_id in roster], tag="lev")
            for roster in roster_keys
        ]
    except KeyError as exc:
        raise ValueError("CBWU-OI roster is outside the player universe") from exc

    roster_rows = np.asarray([
        [base.player_ids.index(player_id) for player_id in lineup.ids]
        for lineup in union_lineups
    ], dtype=np.int64)
    row_blocks: list[np.ndarray] = []
    total_blocks: list[np.ndarray] = []
    for name in canonical_order:
        world = books[name]
        world_index = {
            str(player_id): index for index, player_id in enumerate(world.player_ids)
        }
        rows_in_base_order = [
            world_index[str(player_id)] for player_id in base.player_ids
        ]
        aligned = np.asarray(world.row_draws[rows_in_base_order], dtype=np.float32)
        row_blocks.append(aligned)
        total_blocks.append(aligned[roster_rows].sum(axis=1).astype(np.float32))
    union_totals = np.concatenate(total_blocks, axis=1)
    combined_rows = np.concatenate(row_blocks, axis=1)
    admitted = _select_tail_entries_bitpacked(union_totals, budget, tail_line)
    if len(admitted) != budget or len(set(admitted)) != budget:
        raise ValueError("CBWU-OI selector did not return the exact R0 budget")

    candidates = tuple(union_lineups[index] for index in admitted)
    candidate_totals = union_totals[admitted]
    all_tags: dict[frozenset, tuple[str, ...]] = {}
    appearance_counts: dict[str, int] = {}
    for lineup, union_index in zip(candidates, admitted, strict=True):
        roster = roster_keys[union_index]
        tags = union[roster]["tags"]
        seeds = union[roster]["seeds"]
        combined_tags = tuple(sorted({
            *(str(tag) for tag in tags),
            *(f"candidate_seed:{seed}" for seed in seeds),
            "candidate_admission:cbwu-oi-v1",
        }))
        all_tags[lineup.ids] = combined_tags
        appearance_counts[_candidate_key(lineup)] = len(seeds)

    return CandidateBatch(
        candidates=candidates,
        candidate_totals=candidate_totals,
        player_ids=base.player_ids,
        player_rows=base.player_rows,
        row_draws=combined_rows,
        all_tags=all_tags,
        metadata={
            "portfolio": "CBWU_OI_V1",
            "production_enabled": False,
            "uses_realized_outcomes": False,
            "tail_line": float(tail_line),
            "candidate_budget": budget,
            "complete_union_candidates": len(union_lineups),
            "canonical_seed_order": list(canonical_order),
            "native_appearance_counts": appearance_counts,
            "world_blocks": len(canonical_order),
            "worlds_per_block": [
                int(books[name].row_draws.shape[1]) for name in canonical_order
            ],
        },
    )


def combine_cbwu_volume_books(
    books: Mapping[str, CandidateBatch],
    seed_order: Sequence[str],
    *,
    tail_line: float = 194.0,
    expected_worlds_per_book: int | None = None,
    tolerance: float = 1e-4,
    world_seed_labels: Sequence[str] = ("R0", "R1", "R2", "R3", "R4"),
) -> CandidateBatch:
    """Build the frozen volume-OI admission book (B2-prime, prospective).

    CANDIDATES come from every supplied seed book (R0..R{k-1}, k >= 5);
    the WORLD BLOCKS and the CANDIDATE BUDGET stay the registered
    production instrument (the canonical R0--R4 blocks and the R0 native
    pool size). This is exactly the retrospective B2-prime admission —
    selected mean S rose monotonically with admitted volume at the fixed
    budget — expressed as a weekly prospective mechanism. Order-invariant
    by construction: candidate identity, attribution, and ranking cannot
    depend on ``seed_order``. Outcome-free; never called by the
    production policy — a separately labeled shadow job must opt in.
    """
    if not np.isfinite(tail_line):
        raise ValueError("CBWU volume tail line must be finite")
    supplied_order = tuple(seed_order)
    canonical_order = tuple(sorted(books, key=lambda name: int(name[1:])))
    expected_labels = tuple(f"R{index}" for index in range(len(books)))
    if len(supplied_order) < 5 or len(set(supplied_order)) != len(
            supplied_order):
        raise ValueError(
            "CBWU volume requires at least five distinct registered seeds")
    if set(supplied_order) != set(books) or canonical_order != expected_labels:
        raise ValueError(
            "CBWU volume requires contiguous registered seeds R0..R{k-1}")
    world_labels = tuple(world_seed_labels)
    if world_labels != ("R0", "R1", "R2", "R3", "R4"):
        raise ValueError(
            "CBWU volume scores on the registered R0--R4 world blocks")
    if not set(world_labels) <= set(books):
        raise ValueError("CBWU volume world blocks are missing")

    base = books["R0"]
    base_universe = set(base.player_ids)
    for name in canonical_order:
        batch = books[name]
        _validate_native_book(
            name,
            batch,
            expected_worlds=expected_worlds_per_book,
            tolerance=tolerance,
        )
        if set(batch.player_ids) != base_universe:
            raise ValueError(
                "CBWU volume player-id universes differ across seeds")
    budget = len(base.candidates)
    if budget <= 0:
        raise ValueError("CBWU volume R0 candidate budget is empty")

    # Symmetric aggregation over EVERY book: no first-supplier identity.
    union: dict[tuple[str, ...], dict[str, object]] = {}
    for name in canonical_order:
        batch = books[name]
        for lineup in batch.candidates:
            roster = tuple(sorted(
                str(player_id) for player_id in _canonical_roster(lineup)))
            tags = batch.all_tags.get(lineup.ids, (lineup.tag or "lev",))
            row = union.setdefault(roster, {"tags": set(), "seeds": set()})
            row["tags"].update(str(tag) for tag in tags)
            row["seeds"].add(name)
    roster_keys = sorted(union)
    if len(roster_keys) < budget:
        raise ValueError("CBWU volume union cannot fill the R0 budget")

    base_by_id = {
        str(player_id): player
        for player_id, player in zip(
            base.player_ids, base.player_rows, strict=True)
    }
    try:
        union_lineups = [
            Lineup([base_by_id[player_id] for player_id in roster], tag="lev")
            for roster in roster_keys
        ]
    except KeyError as exc:
        raise ValueError(
            "CBWU volume roster is outside the player universe") from exc

    roster_rows = np.asarray([
        [base.player_ids.index(player_id) for player_id in lineup.ids]
        for lineup in union_lineups
    ], dtype=np.int64)
    row_blocks: list[np.ndarray] = []
    total_blocks: list[np.ndarray] = []
    for name in world_labels:
        world = books[name]
        world_index = {
            str(player_id): index
            for index, player_id in enumerate(world.player_ids)
        }
        rows_in_base_order = [
            world_index[str(player_id)] for player_id in base.player_ids
        ]
        aligned = np.asarray(
            world.row_draws[rows_in_base_order], dtype=np.float32)
        row_blocks.append(aligned)
        total_blocks.append(aligned[roster_rows].sum(axis=1).astype(np.float32))
    union_totals = np.concatenate(total_blocks, axis=1)
    combined_rows = np.concatenate(row_blocks, axis=1)
    admitted = _select_tail_entries_bitpacked(union_totals, budget, tail_line)
    if len(admitted) != budget or len(set(admitted)) != budget:
        raise ValueError(
            "CBWU volume selector did not return the exact R0 budget")

    candidates = tuple(union_lineups[index] for index in admitted)
    candidate_totals = union_totals[admitted]
    all_tags: dict[frozenset, tuple[str, ...]] = {}
    appearance_counts: dict[str, int] = {}
    for lineup, union_index in zip(candidates, admitted, strict=True):
        roster = roster_keys[union_index]
        tags = union[roster]["tags"]
        seeds = union[roster]["seeds"]
        combined_tags = tuple(sorted({
            *(str(tag) for tag in tags),
            *(f"candidate_seed:{seed}" for seed in seeds),
            "candidate_admission:cbwu-volume-v1",
        }))
        all_tags[lineup.ids] = combined_tags
        appearance_counts[_candidate_key(lineup)] = len(seeds)

    return CandidateBatch(
        candidates=candidates,
        candidate_totals=candidate_totals,
        player_ids=base.player_ids,
        player_rows=base.player_rows,
        row_draws=combined_rows,
        all_tags=all_tags,
        metadata={
            "portfolio": "CBWU_VOLUME_V1",
            "production_enabled": False,
            "uses_realized_outcomes": False,
            "tail_line": float(tail_line),
            "candidate_budget": budget,
            "candidate_books": len(canonical_order),
            "complete_union_candidates": len(union_lineups),
            "canonical_seed_order": list(canonical_order),
            "native_appearance_counts": appearance_counts,
            "world_blocks": len(world_labels),
            "worlds_per_block": [
                int(books[name].row_draws.shape[1]) for name in world_labels
            ],
        },
    )


def audit_cbwu_seed_orders(
    books: Mapping[str, CandidateBatch],
    seed_order: Sequence[str],
    *,
    n_entries: int,
    tail_line: float,
    expected_worlds_per_book: int | None = None,
) -> dict:
    """Rotate first-source/quota order without consulting realized scores."""
    canonical = tuple(seed_order)
    if len(canonical) != 5 or len(set(canonical)) != 5:
        raise ValueError("CBWU order audit requires five registered seeds")
    budget = len(books[canonical[0]].candidates)
    rotations = tuple(
        canonical[offset:] + canonical[:offset] for offset in range(5)
    )
    rows = []
    canonical_candidates: set[frozenset] | None = None
    canonical_selected: set[frozenset] | None = None

    def tuple_count(lineups: Sequence[Lineup], size: int) -> int:
        found = set()
        for lineup in lineups:
            ids = sorted(str(player_id) for player_id in lineup.ids)
            found.update(combinations(ids, size))
        return len(found)

    for rotation in rotations:
        combined = combine_cbwu_books(
            books,
            rotation,
            expected_worlds_per_book=expected_worlds_per_book,
            fixed_candidate_budget=budget,
        )
        picked = select_tail_entries(
            combined.candidate_totals,
            n_entries,
            tail_line,
            env={"SELECT_LSE": "0"},
        )
        candidate_set = {lineup.ids for lineup in combined.candidates}
        selected_lineups = [combined.candidates[index] for index in picked]
        selected_set = {lineup.ids for lineup in selected_lineups}
        if canonical_candidates is None:
            canonical_candidates = candidate_set
            canonical_selected = selected_set
        assert canonical_candidates is not None
        assert canonical_selected is not None
        candidate_shared = len(candidate_set & canonical_candidates)
        selected_shared = len(selected_set & canonical_selected)
        rows.append({
            "seed_order": list(rotation),
            "candidate_budget": len(combined.candidates),
            "candidate_source_counts": combined.metadata[
                "candidate_source_counts"
            ],
            "candidate_identity_jaccard_vs_canonical": float(
                candidate_shared / len(candidate_set | canonical_candidates)
            ),
            "selected_identity_jaccard_vs_canonical": float(
                selected_shared / len(selected_set | canonical_selected)
            ),
            "candidate_pair_coverage": tuple_count(combined.candidates, 2),
            "candidate_triple_coverage": tuple_count(combined.candidates, 3),
            "selected_pair_coverage": tuple_count(selected_lineups, 2),
            "selected_triple_coverage": tuple_count(selected_lineups, 3),
            "selected_world_coverage": float(np.mean(
                np.any(combined.candidate_totals[picked] >= tail_line, axis=0)
            )),
        })
    return {
        "version": "cbwu-seed-order-scorefree-v1",
        "uses_realized_outcomes": False,
        "canonical_seed_order": list(canonical),
        "fixed_candidate_budget": budget,
        "n_entries": int(n_entries),
        "tail_line": float(tail_line),
        "rotations": rows,
    }


def _candidate_key(lineup: Lineup) -> str:
    canonical = json.dumps(
        sorted(str(player_id) for player_id in lineup.ids),
        separators=(",", ":"),
    )
    return sha256(canonical.encode()).hexdigest()


def _lineup_structure(lineup: Lineup) -> dict[str, int]:
    rows = list(lineup.players)
    quarterbacks = [
        player for player in rows if str(player.get("pos", "")).upper() == "QB"
    ]
    if len(quarterbacks) != 1:
        raise ValueError("archetype shadow candidate must contain one quarterback")
    qb = quarterbacks[0]
    qb_team = str(qb.get("team", ""))
    qb_opp = str(qb.get("opp", ""))
    if not qb_team or not qb_opp:
        raise ValueError("archetype shadow quarterback lacks team/opponent")
    skill = [
        player for player in rows
        if str(player.get("pos", "")).upper() != "DST"
    ]
    teams = Counter(str(player.get("team", "")) for player in skill)
    if not teams or "" in teams:
        raise ValueError("archetype shadow candidate lacks team metadata")
    stack_positions = {"RB", "WR", "TE"}
    return {
        "largest_team_block": max(teams.values()),
        "qb_stack_count": sum(
            str(player.get("team")) == qb_team
            and str(player.get("pos", "")).upper() in stack_positions
            for player in rows
        ),
        "bring_back_count": sum(
            str(player.get("team")) == qb_opp
            and str(player.get("pos", "")).upper() in stack_positions
            for player in rows
        ),
    }


def combine_archetype_shadow_books(
    books: Mapping[str, CandidateBatch],
    seed_order: Sequence[str],
    *,
    tail_line: float = 194.0,
    expected_worlds_per_book: int | None = None,
    tolerance: float = 1e-4,
) -> CandidateBatch:
    """Build the fixed-budget 2026 archetype-allocation CBWU shadow.

    Every native book is generated and validated exactly as in production.
    Exact-roster deduplication keeps the incumbent first-source attribution.
    The treatment changes only which already-generated unique candidates fill
    the native-book-sized union.  Native source totals supply q99 and
    ``P(score >= tail_line)``; no realized outcome or final selector is read.

    This function is intentionally not called by the production policy.
    """
    if not np.isfinite(tail_line):
        raise ValueError("archetype shadow tail line must be finite")
    order = tuple(seed_order)
    if len(order) != 5 or len(set(order)) != 5:
        raise ValueError("archetype shadow requires five registered seeds")
    if set(books) != set(order):
        missing = sorted(set(order) - set(books))
        extra = sorted(set(books) - set(order))
        raise ValueError(
            f"archetype seed books differ (missing={missing}, extra={extra})"
        )
    base = books[order[0]]
    base_universe = set(base.player_ids)
    for name in order:
        batch = books[name]
        _validate_native_book(
            name,
            batch,
            expected_worlds=expected_worlds_per_book,
            tolerance=tolerance,
        )
        if set(batch.player_ids) != base_universe:
            raise ValueError("archetype shadow player-id universes differ")
    budget = len(base.candidates)
    if budget <= 0:
        raise ValueError("archetype shadow base candidate budget is empty")

    union: dict[str, tuple[str, Lineup, tuple[str, ...]]] = {}
    features: list[dict] = []
    novelty = {name: 0 for name in order}
    seen: set[frozenset] = set()
    for name in order:
        batch = books[name]
        totals = np.asarray(batch.candidate_totals, dtype=np.float32)
        for index, lineup in enumerate(batch.candidates):
            roster = _canonical_roster(lineup)
            if roster in seen:
                continue
            seen.add(roster)
            novelty[name] += 1
            key = _candidate_key(lineup)
            if key in union:
                raise ValueError("archetype candidate key collision")
            tags = batch.all_tags.get(roster, (lineup.tag or "lev",))
            union[key] = (name, lineup, tuple(tags))
            native = totals[index]
            if not np.isfinite(native).all():
                raise ValueError("archetype native candidate totals are nonfinite")
            features.append({
                "candidate_key": key,
                "source_seed": name,
                "sim_q99": float(np.quantile(native, 0.99)),
                "p_line": float(np.mean(native >= tail_line)),
                **_lineup_structure(lineup),
            })
    feature_frame = pd.DataFrame(features)
    selected, allocation_receipt = allocate_archetype_budget(
        feature_frame, budget, order
    )
    chosen = [
        (*union[str(row.candidate_key)], str(row.candidate_key))
        for row in selected.itertuples(index=False)
    ]

    base_by_id = dict(zip(base.player_ids, base.player_rows, strict=True))
    rebuilt: list[Lineup] = []
    all_tags: dict[frozenset, tuple[str, ...]] = {}
    source_counts = {name: 0 for name in order}
    for name, source, tags, _key in chosen:
        players = [base_by_id[player["id"]] for player in source.players]
        lineup = Lineup(players, tag=source.tag)
        source_tag = f"candidate_seed:{name}"
        archetype = str(selected.loc[
            selected.candidate_key.eq(_key), "archetype"
        ].iloc[0])
        archetype_tag = f"candidate_archetype:{archetype}"
        all_tags[lineup.ids] = tuple(dict.fromkeys(
            (*tags, source_tag, archetype_tag)
        ))
        rebuilt.append(lineup)
        source_counts[name] += 1

    world_blocks: list[np.ndarray] = []
    row_blocks: list[np.ndarray] = []
    base_index = {player_id: index for index, player_id in enumerate(base.player_ids)}
    for world_name in order:
        world = books[world_name]
        world_index = {
            player_id: index for index, player_id in enumerate(world.player_ids)
        }
        rows_in_base_order = [world_index[player_id] for player_id in base.player_ids]
        aligned_draws = np.asarray(
            world.row_draws[rows_in_base_order], dtype=np.float32
        )
        row_blocks.append(aligned_draws)
        roster_totals = np.stack([
            aligned_draws[[base_index[player_id] for player_id in lineup.ids]].sum(
                axis=0
            )
            for lineup in rebuilt
        ]).astype(np.float32)
        world_blocks.append(roster_totals)
    combined_totals = np.concatenate(world_blocks, axis=1)
    combined_rows = np.concatenate(row_blocks, axis=1)
    if combined_totals.shape != (budget, combined_rows.shape[1]):
        raise ValueError("archetype combined candidate worlds are misaligned")

    return CandidateBatch(
        candidates=tuple(rebuilt),
        candidate_totals=combined_totals,
        player_ids=base.player_ids,
        player_rows=base.player_rows,
        row_draws=combined_rows,
        all_tags=all_tags,
        metadata={
            "portfolio": "CBWU_ARCHETYPE_SHADOW",
            "parent_portfolio": "CBWU",
            "candidate_budget": budget,
            "candidate_source_counts": source_counts,
            "novel_candidates_by_seed": novelty,
            "world_blocks": len(order),
            "worlds_per_block": [
                int(books[name].row_draws.shape[1]) for name in order
            ],
            "tail_line": float(tail_line),
            "native_summary_source": "first-source native candidate totals",
            "allocation_receipt": allocation_receipt,
            "production_enabled": False,
        },
    )


__all__ = [
    "audit_cbwu_seed_orders",
    "combine_archetype_shadow_books",
    "combine_cbwu_books",
]
