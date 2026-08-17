"""Identity-only analysis for the frozen nested same-law capacity curve."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from hashlib import sha256
from itertools import combinations
import json
from typing import Any

import numpy as np
import pandas as pd

from .exact_p_generator_census import (
    BASE_FAMILIES,
    FORBIDDEN_COLUMNS,
    _audit_exact_p,
    _base_tags,
    _shape,
    canonical_roster,
)


PROTOCOL_ID = "20260817-same-law-capacity-curve-v1"
BOOK_ORDER = tuple(f"R{index}" for index in range(50))
SCALES = (("1x", 5), ("2x", 10), ("5x", 25), ("10x", 50))
STRUCTURE_FIELDS = (
    "salary",
    "distinct_games",
    "maximum_game_count",
    "qb_stack_size",
    "bring_back_count",
)
EXISTING_SEEDS = {
    "R0": (0, 7331),
    "R1": (1137260708, 2690847602),
    "R2": (2875959182, 1630284992),
    "R3": (253722715, 3374646876),
    "R4": (1643280042, 3977633467),
}
SUMMARY_QUANTILES = (0.10, 0.25, 0.75, 0.90)
CAPACITY_FORBIDDEN_COLUMNS = FORBIDDEN_COLUMNS | frozenset({
    "score",
    "candidate_score",
    "candidate_total",
    "candidate_totals",
    "projected_score",
    "simulated_score",
    "score_mean",
    "proj",
    "projection",
    "mean",
    "support",
    "support_mask",
    "p187",
    "p194",
    "p200",
    "p210",
    "p220",
    "p230",
    "p240",
    "q90",
    "q99",
    "p_line",
    "selected",
    "mean_projection",
    "actual_fpts",
})


def _require(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    if missing := columns - set(frame):
        raise ValueError(f"{label} lacks columns {sorted(missing)}")


def _reject_outcomes(frame: pd.DataFrame, label: str) -> None:
    if forbidden := CAPACITY_FORBIDDEN_COLUMNS & set(frame):
        raise ValueError(f"{label} contains forbidden columns {sorted(forbidden)}")


def _derived_seed(replicate: str, kind: str) -> int:
    raw = f"nfl-dfs|{PROTOCOL_ID}|{replicate}|{kind}".encode()
    return int.from_bytes(sha256(raw).digest()[:4], "big")


def validate_seed_ledger(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Validate the exact R0--R49 prospectively frozen seed population."""
    _require(
        frame,
        {"replicate", "projection_seed", "role_seed", "source"},
        "capacity seed ledger",
    )
    if len(frame) != 50 or frame.replicate.astype(str).tolist() != list(BOOK_ORDER):
        raise ValueError("capacity seed ledger order/population differs")
    output: list[dict[str, Any]] = []
    observed_values: list[int] = []
    for row in frame.itertuples(index=False):
        replicate = str(row.replicate)
        projection_seed = int(row.projection_seed)
        role_seed = int(row.role_seed)
        if not (
            0 <= projection_seed < 2**32 and 0 <= role_seed < 2**32
        ):
            raise ValueError("capacity seed leaves unsigned 32-bit range")
        if replicate in EXISTING_SEEDS:
            expected = EXISTING_SEEDS[replicate]
            expected_source = "existing-phase-s"
        else:
            expected = (
                _derived_seed(replicate, "projection"),
                _derived_seed(replicate, "role"),
            )
            expected_source = "sha256-first32be"
        if (projection_seed, role_seed) != expected or str(row.source) != expected_source:
            raise ValueError(f"capacity seed identity differs for {replicate}")
        observed_values.extend((projection_seed, role_seed))
        output.append({
            "replicate": replicate,
            "projection_seed": projection_seed,
            "role_seed": role_seed,
            "source": expected_source,
        })
    if len(set(observed_values)) != 100:
        raise ValueError("capacity seed values are not globally unique")
    return output


def _summary(values: Iterable[float]) -> dict[str, Any]:
    array = np.asarray(list(values), dtype=float)
    if not len(array):
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "minimum": None,
            "maximum": None,
            "p10": None,
            "p25": None,
            "p75": None,
            "p90": None,
        }
    if not np.isfinite(array).all():
        raise ValueError("capacity summary contains a non-finite value")
    quantiles = np.quantile(array, SUMMARY_QUANTILES)
    return {
        "count": int(len(array)),
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "minimum": float(np.min(array)),
        "maximum": float(np.max(array)),
        "p10": float(quantiles[0]),
        "p25": float(quantiles[1]),
        "p75": float(quantiles[2]),
        "p90": float(quantiles[3]),
    }


def _structure_summary(
    players: pd.DataFrame,
    rosters: Iterable[tuple[str, ...]],
) -> dict[str, Any]:
    shapes = [_shape(players, roster) for roster in sorted(set(rosters))]
    return {
        field: _summary(float(shape[field]) for shape in shapes)
        for field in STRUCTURE_FIELDS
    }


def _pairs(roster: Sequence[str]) -> set[tuple[str, str]]:
    return {tuple(sorted(pair)) for pair in combinations(roster, 2)}


def _stack_cores(
    players: pd.DataFrame,
    roster: Sequence[str],
) -> set[tuple[str, str, str]]:
    by_id = players.set_index("id", drop=False)
    chosen = by_id.loc[list(roster)]
    qbs = chosen[chosen.pos.eq("QB")]
    if len(qbs) != 1:
        raise ValueError("capacity roster does not contain exactly one QB")
    qb = qbs.iloc[0]
    catchers = sorted(
        chosen.loc[
            chosen.team.eq(str(qb.team)) & chosen.pos.isin(("WR", "TE")),
            "id",
        ].astype(str)
    )
    return {
        (str(qb.id), first, second)
        for first, second in combinations(catchers, 2)
    }


def _slate_records(
    players: pd.DataFrame,
    candidates: pd.DataFrame,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for book_index, replicate in enumerate(BOOK_ORDER):
        group = candidates[candidates.replicate.astype(str).eq(replicate)].copy()
        indices = pd.to_numeric(group.cand_ix, errors="raise").astype(int).tolist()
        if indices != list(range(len(indices))):
            raise ValueError(f"capacity candidate indices differ for {replicate}")
        seen: set[tuple[str, ...]] = set()
        for row in group.itertuples(index=False):
            roster = canonical_roster(row.players)
            if roster in seen:
                raise ValueError(f"capacity book {replicate} repeats a roster")
            seen.add(roster)
            audit = _audit_exact_p(players, roster)
            if not audit["passes"]:
                raise ValueError(
                    f"capacity candidate is illegal: {replicate} {audit['failures']}"
                )
            records.append({
                "replicate": replicate,
                "book_index": book_index,
                "cand_ix": int(row.cand_ix),
                "roster": roster,
                "families": _base_tags(row.all_tags, row.tag),
            })
    return records


def _one_slate(
    *,
    season: int,
    week: int,
    players: pd.DataFrame,
    candidates: pd.DataFrame,
    exact_p: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not _audit_exact_p(players, exact_p)["passes"]:
        raise ValueError("capacity exact-P identity is not independently legal")
    records = _slate_records(players, candidates)
    prior_rosters: set[tuple[str, ...]] = set()
    prior_family: dict[str, set[tuple[str, ...]]] = {
        family: set() for family in BASE_FAMILIES
    }
    prior_players: set[str] = set()
    prior_pairs: set[tuple[str, str]] = set()
    prior_cores: set[tuple[str, str, str]] = set()
    prior_multi: set[tuple[str, ...]] = set()
    prior_family_yield: dict[str, float] = {}
    prior_all_yield: float | None = None
    output: list[dict[str, Any]] = []
    for scale, book_count in SCALES:
        active = [row for row in records if row["book_index"] < book_count]
        by_roster: dict[tuple[str, ...], dict[str, Any]] = {}
        for row in active:
            by_roster.setdefault(row["roster"], row)
        rosters = set(by_roster)
        if not prior_rosters.issubset(rosters):
            raise ValueError("capacity nested candidate identities are not monotone")
        added_books = book_count if not output else book_count - output[-1]["book_count"]
        new_rosters = rosters - prior_rosters
        marginal_yield = len(new_rosters) / added_books
        family_metrics: dict[str, Any] = {}
        family_sets: dict[str, set[tuple[str, ...]]] = {}
        for family in BASE_FAMILIES:
            raw = [row for row in active if family in row["families"]]
            identities = {row["roster"] for row in raw}
            family_sets[family] = identities
            new_identities = identities - prior_family[family]
            yield_per_book = len(new_identities) / added_books
            family_metrics[family] = {
                "raw_memberships": len(raw),
                "distinct_identities": len(identities),
                "new_distinct_identities": len(new_identities),
                "marginal_yield_per_new_book": float(yield_per_book),
                "marginal_yield_slope": (
                    None
                    if family not in prior_family_yield
                    else float(yield_per_book - prior_family_yield[family])
                ),
                "new_identity_structure": _structure_summary(
                    players, new_identities,
                ),
            }
        multi_raw = [row for row in active if len(row["families"]) > 1]
        multi_identities = {row["roster"] for row in multi_raw}
        player_reach = {player for roster in rosters for player in roster}
        pair_reach = {pair for roster in rosters for pair in _pairs(roster)}
        core_reach = {
            core for roster in rosters for core in _stack_cores(players, roster)
        }
        distances = [9 - len(set(roster) & set(exact_p)) for roster in rosters]
        minimum_distance = min(distances)
        nearest_count = sum(value == minimum_distance for value in distances)
        exact_pairs = _pairs(exact_p)
        exact_cores = _stack_cores(players, exact_p)
        row = {
            "season": season,
            "week": week,
            "scale": scale,
            "book_count": book_count,
            "new_book_count": added_books,
            "raw_candidates": len(active),
            "distinct_rosters": len(rosters),
            "duplicate_candidates": len(active) - len(rosters),
            "duplicate_rate": float((len(active) - len(rosters)) / len(active)),
            "distinct_yield_ratio": float(len(rosters) / len(active)),
            "new_distinct_rosters": len(new_rosters),
            "marginal_yield_per_new_book": float(marginal_yield),
            "marginal_yield_slope": (
                None
                if prior_all_yield is None
                else float(marginal_yield - prior_all_yield)
            ),
            "families": family_metrics,
            "multi_family": {
                "raw_memberships": len(multi_raw),
                "distinct_identities": len(multi_identities),
                "new_distinct_identities": len(multi_identities - prior_multi),
            },
            "reach": {
                "players": len(player_reach),
                "new_players": len(player_reach - prior_players),
                "pairs": len(pair_reach),
                "new_pairs": len(pair_reach - prior_pairs),
                "stack_cores": len(core_reach),
                "new_stack_cores": len(core_reach - prior_cores),
            },
            "exact_p": {
                "present": exact_p in rosters,
                "minimum_replacement_distance": int(minimum_distance),
                "nearest_identity_count": int(nearest_count),
                "players_reached": len(set(exact_p) & player_reach),
                "players_total": 9,
                "pairs_reached": len(exact_pairs & pair_reach),
                "pairs_total": 36,
                "stack_cores_reached": len(exact_cores & core_reach),
                "stack_cores_total": len(exact_cores),
            },
            "new_identity_structure": {
                "all": _structure_summary(players, new_rosters),
                **{
                    family: family_metrics[family]["new_identity_structure"]
                    for family in BASE_FAMILIES
                },
            },
        }
        output.append(row)
        prior_rosters = rosters
        prior_family = family_sets
        prior_players = player_reach
        prior_pairs = pair_reach
        prior_cores = core_reach
        prior_multi = multi_identities
        prior_all_yield = marginal_yield
        prior_family_yield = {
            family: float(metrics["marginal_yield_per_new_book"])
            for family, metrics in family_metrics.items()
        }
    return output


def _aggregate(cells: list[dict[str, Any]]) -> dict[str, Any]:
    metric_paths = {
        "raw_candidates": lambda row: row["raw_candidates"],
        "distinct_rosters": lambda row: row["distinct_rosters"],
        "duplicate_rate": lambda row: row["duplicate_rate"],
        "distinct_yield_ratio": lambda row: row["distinct_yield_ratio"],
        "new_distinct_rosters": lambda row: row["new_distinct_rosters"],
        "marginal_yield_per_new_book": lambda row: row[
            "marginal_yield_per_new_book"
        ],
        "minimum_replacement_distance": lambda row: row["exact_p"][
            "minimum_replacement_distance"
        ],
        "players_reached": lambda row: row["reach"]["players"],
        "pairs_reached": lambda row: row["reach"]["pairs"],
        "stack_cores_reached": lambda row: row["reach"]["stack_cores"],
    }
    by_scale: dict[str, Any] = {}
    by_season: dict[str, Any] = {}
    for scale, _ in SCALES:
        subset = [row for row in cells if row["scale"] == scale]
        by_scale[scale] = {
            key: _summary(fn(row) for row in subset)
            for key, fn in metric_paths.items()
        }
        by_scale[scale]["exact_p_present_slates"] = sum(
            bool(row["exact_p"]["present"]) for row in subset
        )
        by_scale[scale]["families"] = {
            family: {
                "distinct_identities": _summary(
                    row["families"][family]["distinct_identities"]
                    for row in subset
                ),
                "new_distinct_identities": _summary(
                    row["families"][family]["new_distinct_identities"]
                    for row in subset
                ),
                "marginal_yield_per_new_book": _summary(
                    row["families"][family]["marginal_yield_per_new_book"]
                    for row in subset
                ),
            }
            for family in BASE_FAMILIES
        }
    for season in sorted({row["season"] for row in cells}):
        by_season[str(season)] = {}
        for scale, _ in SCALES:
            subset = [
                row for row in cells
                if row["season"] == season and row["scale"] == scale
            ]
            by_season[str(season)][scale] = {
                key: _summary(fn(row) for row in subset)
                for key, fn in metric_paths.items()
            }
    distance_steps: dict[str, Any] = {}
    by_key = {
        (row["season"], row["week"], row["scale"]): row for row in cells
    }
    for index, (scale, _) in enumerate(SCALES):
        if index == 0:
            distance_steps[scale] = None
            continue
        prior_scale = SCALES[index - 1][0]
        counts = {"improved": 0, "tied": 0, "worsened": 0}
        for season, week in sorted({(r["season"], r["week"]) for r in cells}):
            old = by_key[(season, week, prior_scale)]["exact_p"][
                "minimum_replacement_distance"
            ]
            new = by_key[(season, week, scale)]["exact_p"][
                "minimum_replacement_distance"
            ]
            counts["improved" if new < old else "worsened" if new > old else "tied"] += 1
        distance_steps[scale] = counts
    yield_rankings: dict[str, Any] = {}
    for scale, _ in SCALES:
        subset = [row for row in cells if row["scale"] == scale]
        ordered = sorted(
            subset,
            key=lambda row: (
                row["distinct_yield_ratio"], row["season"], row["week"],
            ),
        )
        render = lambda row: {
            "season": row["season"],
            "week": row["week"],
            "distinct_yield_ratio": row["distinct_yield_ratio"],
            "raw_candidates": row["raw_candidates"],
            "distinct_rosters": row["distinct_rosters"],
        }
        yield_rankings[scale] = {
            "smallest": [render(row) for row in ordered[:10]],
            "largest": [render(row) for row in reversed(ordered[-10:])],
        }
    return {
        "by_scale": by_scale,
        "by_season": by_season,
        "minimum_distance_step_counts": distance_steps,
        "distinct_yield_rankings": yield_rankings,
    }


def analyze_same_law_capacity_curve(
    players: pd.DataFrame,
    candidates: pd.DataFrame,
    exact_p_rosters: pd.DataFrame,
    *,
    expected_slates: int,
) -> dict[str, Any]:
    """Validate and compute the complete four-scale identity-only curve."""
    for frame, label in (
        (players, "capacity players"),
        (candidates, "capacity candidates"),
        (exact_p_rosters, "capacity exact P"),
    ):
        _reject_outcomes(frame, label)
    keys = {"season", "week"}
    _require(
        players,
        keys | {"id", "pos", "team", "opp", "game_id", "salary"},
        "capacity players",
    )
    _require(
        candidates,
        keys | {"replicate", "cand_ix", "players", "tag", "all_tags"},
        "capacity candidates",
    )
    _require(exact_p_rosters, keys | {"players"}, "capacity exact P")
    if candidates.empty or players.empty or exact_p_rosters.empty:
        raise ValueError("capacity input population is empty")
    slate_keys = sorted({
        tuple(map(int, row))
        for row in exact_p_rosters[["season", "week"]].to_numpy()
    })
    if len(slate_keys) != expected_slates or len(exact_p_rosters) != expected_slates:
        raise ValueError("capacity exact-P slate population differs")
    for frame, label in ((players, "players"), (candidates, "candidates")):
        observed = {
            tuple(map(int, row))
            for row in frame[["season", "week"]].drop_duplicates().to_numpy()
        }
        if observed != set(slate_keys):
            raise ValueError(f"capacity {label} slate population differs")
    if set(candidates.replicate.astype(str)) != set(BOOK_ORDER):
        raise ValueError("capacity candidate book population differs")
    if candidates.duplicated(["replicate", "season", "week", "cand_ix"]).any():
        raise ValueError("capacity candidate source identity repeats")
    cells: list[dict[str, Any]] = []
    for season, week in slate_keys:
        player_slate = players[
            players.season.astype(int).eq(season)
            & players.week.astype(int).eq(week)
        ].copy()
        player_slate["id"] = player_slate.id.astype(str)
        player_slate["pos"] = player_slate.pos.astype(str).str.upper().replace({
            "DEF": "DST",
        })
        player_slate["team"] = player_slate.team.astype(str)
        player_slate["opp"] = player_slate.opp.astype(str)
        if player_slate.id.duplicated().any():
            raise ValueError("capacity player ID repeats within a slate")
        candidate_slate = candidates[
            candidates.season.astype(int).eq(season)
            & candidates.week.astype(int).eq(week)
        ].copy().sort_values(
            ["replicate", "cand_ix"],
            key=lambda column: (
                column.map({book: index for index, book in enumerate(BOOK_ORDER)})
                if column.name == "replicate"
                else column
            ),
            kind="stable",
        )
        if candidate_slate.groupby("replicate", sort=False).ngroups != 50:
            raise ValueError("capacity slate does not contain all 50 books")
        exact_rows = exact_p_rosters[
            exact_p_rosters.season.astype(int).eq(season)
            & exact_p_rosters.week.astype(int).eq(week)
        ]
        if len(exact_rows) != 1:
            raise ValueError("capacity exact-P slate identity differs")
        cells.extend(_one_slate(
            season=season,
            week=week,
            players=player_slate,
            candidates=candidate_slate,
            exact_p=canonical_roster(exact_rows.iloc[0].players),
        ))
    expected_cells = expected_slates * len(SCALES)
    if len(cells) != expected_cells:
        raise ValueError("capacity scale/slate grid differs")
    result = {
        "version": "same-law-capacity-curve-v1",
        "protocol_id": PROTOCOL_ID,
        "uses_realized_outcome_values": False,
        "uses_outcome_derived_exact_p_identity": True,
        "production_change_licensed": False,
        "population": {
            "slates": expected_slates,
            "books": 50,
            "book_slate_cells": expected_slates * 50,
            "scales": [scale for scale, _ in SCALES],
        },
        "cells": cells,
        "aggregate": _aggregate(cells),
        "disposition": "complete-descriptive-capacity-curve",
    }
    # Exercise deterministic JSON serialization now; NaN/Inf are forbidden.
    json.dumps(result, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return result


__all__ = [
    "BOOK_ORDER",
    "PROTOCOL_ID",
    "SCALES",
    "analyze_same_law_capacity_curve",
    "validate_seed_ledger",
]
