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
import json

import numpy as np
import pandas as pd

from ..backtest.engine import CandidateBatch
from ..optimizer.lineup import Lineup
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


def combine_cbwu_books(
    books: Mapping[str, CandidateBatch],
    seed_order: Sequence[str],
    *,
    expected_worlds_per_book: int | None = None,
    tolerance: float = 1e-4,
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

    budget = len(base.candidates)
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


__all__ = ["combine_archetype_shadow_books", "combine_cbwu_books"]
