"""Outcome-blind cross-law discovery candidate transform.

This is the exact prospective mechanism nominated by handoff 003.  A native
CBWU seed book must already have requested 40 leverage and 100 incumbent boom
solves.  The transform rank-transports that seed book's player-world matrix
under one fixed widened-coupling law, visits the 60 highest-total discovery
worlds, and performs exactly one MILP solve per visit under the same explicit
construction policy.  Novel rosters are appended; duplicates are ledgered.

The discovery law is generation-only.  Every candidate score, including each
new roster, is rebuilt exclusively from the untouched base ``row_draws``.
No realized outcome, cloud mutation, persistence, selector, or production
policy operation is available in this module.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from hashlib import sha256
from itertools import combinations
import json
import math
import re
import time
from typing import Final

import numpy as np
from scipy.special import ndtri

from ..backtest.engine import CandidateBatch, _validate_candidate_batch
from ..optimizer.lineup import Lineup, StackRules, optimize
from .generation_exposure import (
    LEDGER_SCHEMA,
    SolveExposureLedger,
    canonical_sha256,
    roster_identity,
    validate_ledger,
)


VERSION: Final = "prospective-cross-law-discovery-v2"
RECEIPT_SCHEMA: Final = "prospective-cross-law-discovery-receipt/v2"
INFLUENCE_TRACE_SCHEMA: Final = (
    "prospective-cross-law-production-influence-trace/v1"
)
EXPOSURE_SCHEMA: Final = LEDGER_SCHEMA
FAMILY: Final = "boom:xlaw"
BASE_WORLD_COUNT: Final = 10_000
DISCOVERY_ATTEMPTS: Final = 60
BASE_LEVERAGE_ATTEMPTS: Final = 40
BASE_BOOM_ATTEMPTS: Final = 100
SEED_LABELS: Final = ("R0", "R1", "R2", "R3", "R4")
OBJECTIVE_COLUMN: Final = "proj_cross_law_discovery"
LAW: Final = {
    "law": "symmetric-widened-game-coupling-rank-transport",
    "lam_lo": 0.0,
    "lam_hi": 1.0,
    "base": 0.5,
    "slope": 0.0,
    "lam_team": 0.7,
    "dst_untouched": True,
    "marginal_restoration": "exact-bitwise-rank-transport",
    "selection_bank": "untouched-base-row-draws",
}
LAW_SHA256: Final = ""

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_OUTCOME_TOKENS: Final = ("actual", "realized", "outcome")


class ProspectiveCrossLawDiscoveryError(ValueError):
    """The discovery transform or its independent validation failed closed."""


def _fail(message: str) -> None:
    raise ProspectiveCrossLawDiscoveryError(message)


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProspectiveCrossLawDiscoveryError(
            "cross-law value is not canonical JSON"
        ) from exc


# Filled after the canonical helper exists, while retaining a public constant.
LAW_SHA256 = canonical_sha256(LAW)


def _array_receipt(value: np.ndarray) -> dict[str, object]:
    array = np.ascontiguousarray(value)
    header = _canonical_json_bytes({
        "dtype": array.dtype.str,
        "shape": list(array.shape),
    })
    raw = header + b"\n" + array.tobytes(order="C")
    return {
        "sha256": sha256(raw).hexdigest(),
        "dtype": array.dtype.str,
        "shape": list(array.shape),
        "bytes": int(array.nbytes),
    }


def _identity_token(value: object) -> dict[str, object]:
    if isinstance(value, str) and value:
        return {"type": "str", "value": value}
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        return {"type": "int", "value": int(value)}
    _fail("cross-law player identity must be one nonempty string or integer")


def _roster_sha256(lineup: Lineup) -> str:
    if not isinstance(lineup, Lineup) or len(lineup.ids) != 9:
        _fail("cross-law solver returned a non-nine-player roster")
    try:
        return str(roster_identity(lineup.ids)["roster_sha256"])
    except Exception as exc:
        raise ProspectiveCrossLawDiscoveryError(
            "cross-law solver roster identity differs"
        ) from exc


def _bitwise_multiset_sha256(row: np.ndarray) -> str:
    array = np.ascontiguousarray(row)
    if array.ndim != 1 or array.dtype.kind != "f":
        _fail("cross-law marginal row must be one floating vector")
    width = int(array.dtype.itemsize)
    pieces = array.view(np.uint8).reshape(array.size, width)
    ordered = sorted(bytes(piece) for piece in pieces)
    return sha256(b"".join(ordered)).hexdigest()


def _marginal_manifest(
    draws: np.ndarray, player_ids: Sequence[object],
) -> list[dict[str, object]]:
    if draws.shape[0] != len(player_ids):
        _fail("cross-law marginal/player census differs")
    return [
        {
            "player_id": _identity_token(player_id),
            "dtype": draws.dtype.str,
            "world_count": int(draws.shape[1]),
            "bitwise_multiset_sha256": _bitwise_multiset_sha256(draws[index]),
        }
        for index, player_id in enumerate(player_ids)
    ]


def _same_team_co_boom_trace(
    base: np.ndarray,
    discovery: np.ndarray,
    *,
    teams: Sequence[str],
    positions: Sequence[str],
) -> dict[str, object]:
    """Outcome-free mechanism trace used by the lab's stage-3 diagnostic."""

    eligible_teams = _ordered_unique([
        team for team, position in zip(teams, positions, strict=True)
        if position != "DST"
    ])

    def _rate(draws: np.ndarray) -> tuple[float, int]:
        q90 = np.quantile(draws, 0.9, axis=1)
        values = []
        for team in eligible_teams:
            indices = [
                index for index, observed in enumerate(teams)
                if observed == team and positions[index] != "DST"
            ]
            if len(indices) < 3:
                continue
            hot = draws[indices] > q90[indices, None]
            values.append(float((hot.sum(axis=0) >= 2).mean()))
        return (float(np.mean(values)) if values else 0.0, len(values))

    base_rate, base_teams = _rate(base)
    discovery_rate, discovery_teams = _rate(discovery)
    if base_teams != discovery_teams:
        _fail("cross-law joint-trace team census differs")
    return {
        "definition": (
            "mean-across-teams-p-world-at-least-2-skill-players-above-"
            "their-bank-specific-q90"
        ),
        "eligible_team_count": base_teams,
        "base_rate": base_rate,
        "discovery_rate": discovery_rate,
        "discovery_minus_base": discovery_rate - base_rate,
        "uses_realized_outcomes": False,
    }


def _world_rank_trace(
    base: np.ndarray,
    discovery: np.ndarray,
) -> dict[str, object]:
    """Exact rank displacement for the player-sum world ordering.

    The production discovery solver uses descending player-sum worlds.  The
    two rank vectors below use that exact stable-ascending-then-reverse order,
    including its deterministic descending world-index tie break.  Because
    both vectors are permutations, Spearman's rho has the closed form used
    here and does not depend on a statistics-library tie convention.
    """

    if base.shape != discovery.shape or base.ndim != 2:
        _fail("cross-law world-rank banks differ")
    base_totals = base.sum(axis=0)
    discovery_totals = discovery.sum(axis=0)
    base_order = np.argsort(base_totals, kind="stable")[::-1]
    discovery_order = np.argsort(discovery_totals, kind="stable")[::-1]
    world_count = int(base.shape[1])
    base_rank = np.empty(world_count, dtype=np.int64)
    discovery_rank = np.empty(world_count, dtype=np.int64)
    base_rank[base_order] = np.arange(world_count, dtype=np.int64)
    discovery_rank[discovery_order] = np.arange(world_count, dtype=np.int64)
    displacement = base_rank - discovery_rank
    squared_distance = int(np.dot(displacement, displacement))
    denominator = world_count * (world_count * world_count - 1)
    rho = 1.0 - (6.0 * squared_distance / denominator)
    top = min(DISCOVERY_ATTEMPTS, world_count)
    overlap = len(set(base_order[:top].tolist()) & set(
        discovery_order[:top].tolist()
    ))
    return {
        "definition": (
            "spearman-rho-of-descending-all-player-world-sum-ranks;"
            "stable-ascending-argsort-then-reverse;ties-by-descending-world-id"
        ),
        "world_count": world_count,
        "sum_squared_rank_displacement": squared_distance,
        "spearman_rho": float(rho),
        "base_world_order_sha256": canonical_sha256([
            int(value) for value in base_order
        ]),
        "discovery_world_order_sha256": canonical_sha256([
            int(value) for value in discovery_order
        ]),
        "top_world_count": top,
        "top_world_overlap_count": overlap,
        "top_world_jaccard": float(overlap / (2 * top - overlap)),
        "base_world_total_receipt": _array_receipt(base_totals),
        "discovery_world_total_receipt": _array_receipt(discovery_totals),
        "uses_realized_outcomes": False,
    }


def _pair_dependence(
    left: np.ndarray,
    right: np.ndarray,
) -> dict[str, float | None]:
    """Binary-event joint rate, independence excess, and phi coefficient."""

    if left.dtype != np.bool_ or right.dtype != np.bool_ or left.shape != right.shape:
        _fail("cross-law dependence event vectors differ")
    left_rate = float(left.mean())
    right_rate = float(right.mean())
    joint_rate = float(np.logical_and(left, right).mean())
    excess = joint_rate - left_rate * right_rate
    denominator = math.sqrt(
        left_rate * (1.0 - left_rate) * right_rate * (1.0 - right_rate)
    )
    return {
        "left_rate": left_rate,
        "right_rate": right_rate,
        "joint_rate": joint_rate,
        "independence_excess": float(excess),
        "phi": None if denominator == 0.0 else float(excess / denominator),
    }


def _dependence_summary(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    if not rows:
        return {
            "pair_count": 0,
            "base_mean_joint_rate": None,
            "discovery_mean_joint_rate": None,
            "base_mean_independence_excess": None,
            "discovery_mean_independence_excess": None,
            "base_mean_phi": None,
            "discovery_mean_phi": None,
        }

    def _mean(path: tuple[str, str]) -> float | None:
        values = [
            row[path[0]][path[1]]  # type: ignore[index]
            for row in rows
            if row[path[0]][path[1]] is not None  # type: ignore[index]
        ]
        return None if not values else float(np.mean(values, dtype=np.float64))

    return {
        "pair_count": len(rows),
        "base_mean_joint_rate": _mean(("base", "joint_rate")),
        "discovery_mean_joint_rate": _mean(("discovery", "joint_rate")),
        "base_mean_independence_excess": _mean(
            ("base", "independence_excess")
        ),
        "discovery_mean_independence_excess": _mean(
            ("discovery", "independence_excess")
        ),
        "base_mean_phi": _mean(("base", "phi")),
        "discovery_mean_phi": _mean(("discovery", "phi")),
    }


def _joint_dependence_trace(
    base: np.ndarray,
    discovery: np.ndarray,
    *,
    games: Sequence[str],
    teams: Sequence[str],
    positions: Sequence[str],
) -> dict[str, object]:
    """Outcome-free team/game co-boom and cross-team tail dependence.

    A player is hot when its draw is strictly above its base-bank q90.  Exact
    marginal preservation means those thresholds are also discovery-bank q90
    thresholds.  A team/game co-boom event has at least two hot non-DST
    players in that group.  Cross-team dependence compares those team co-boom
    event vectors, separately for opposing/same-game teams and teams in
    different games.
    """

    if (
        base.shape != discovery.shape
        or len(games) != base.shape[0]
        or len(teams) != base.shape[0]
        or len(positions) != base.shape[0]
    ):
        _fail("cross-law joint-dependence inputs differ")
    thresholds = np.quantile(base, 0.9, axis=1, method="linear")
    base_hot = base > thresholds[:, None]
    discovery_hot = discovery > thresholds[:, None]
    skill = [index for index, pos in enumerate(positions) if pos != "DST"]

    team_members: dict[str, list[int]] = {}
    game_members: dict[str, list[int]] = {}
    team_games: dict[str, set[str]] = {}
    for index in skill:
        team_members.setdefault(teams[index], []).append(index)
        game_members.setdefault(games[index], []).append(index)
        team_games.setdefault(teams[index], set()).add(games[index])
    if any(len(observed) != 1 for observed in team_games.values()):
        _fail("cross-law team appears in multiple games")

    def _group_rows(
        members: Mapping[str, Sequence[int]],
    ) -> tuple[list[dict[str, object]], dict[str, tuple[np.ndarray, np.ndarray]]]:
        rows: list[dict[str, object]] = []
        events: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for group in sorted(members):
            indices = list(members[group])
            if len(indices) < 2:
                continue
            base_event = base_hot[indices].sum(axis=0) >= 2
            discovery_event = discovery_hot[indices].sum(axis=0) >= 2
            base_rate = float(base_event.mean())
            discovery_rate = float(discovery_event.mean())
            rows.append({
                "group": group,
                "skill_player_count": len(indices),
                "base_rate": base_rate,
                "discovery_rate": discovery_rate,
                "discovery_minus_base": discovery_rate - base_rate,
            })
            events[group] = (base_event, discovery_event)
        return rows, events

    team_rows, team_events = _group_rows(team_members)
    game_rows, _ = _group_rows(game_members)
    pair_rows: list[dict[str, object]] = []
    eligible_teams = sorted(team_events)
    for left, right in combinations(eligible_teams, 2):
        left_game = next(iter(team_games[left]))
        right_game = next(iter(team_games[right]))
        category = "same_game_cross_team" if left_game == right_game else (
            "different_game_cross_team"
        )
        pair_rows.append({
            "left_team": left,
            "right_team": right,
            "category": category,
            "base": _pair_dependence(
                team_events[left][0], team_events[right][0]
            ),
            "discovery": _pair_dependence(
                team_events[left][1], team_events[right][1]
            ),
        })
    same_game = [
        row for row in pair_rows
        if row["category"] == "same_game_cross_team"
    ]
    different_game = [
        row for row in pair_rows
        if row["category"] == "different_game_cross_team"
    ]
    return {
        "definition": {
            "hot_player": (
                "draw-strictly-above-player-base-bank-q90;"
                "numpy-quantile-linear"
            ),
            "team_co_boom": "at-least-2-hot-non-DST-players-on-team",
            "game_co_boom": "at-least-2-hot-non-DST-players-in-game",
            "cross_team_dependence": (
                "pairwise-team-co-boom-joint-rate,independence-excess,phi"
            ),
            "group_aggregation": "unweighted-arithmetic-mean-over-groups/pairs",
        },
        "threshold_receipt": _array_receipt(thresholds),
        "team_co_boom": {
            "eligible_team_count": len(team_rows),
            "rows": team_rows,
            "rows_sha256": canonical_sha256(team_rows),
            "base_mean_rate": (
                float(np.mean([row["base_rate"] for row in team_rows]))
                if team_rows else None
            ),
            "discovery_mean_rate": (
                float(np.mean([row["discovery_rate"] for row in team_rows]))
                if team_rows else None
            ),
        },
        "game_co_boom": {
            "eligible_game_count": len(game_rows),
            "rows": game_rows,
            "rows_sha256": canonical_sha256(game_rows),
            "base_mean_rate": (
                float(np.mean([row["base_rate"] for row in game_rows]))
                if game_rows else None
            ),
            "discovery_mean_rate": (
                float(np.mean([row["discovery_rate"] for row in game_rows]))
                if game_rows else None
            ),
        },
        "cross_team_dependence": {
            "same_game_cross_team": _dependence_summary(same_game),
            "different_game_cross_team": _dependence_summary(different_game),
            "all_cross_team": _dependence_summary(pair_rows),
            "pair_rows_sha256": canonical_sha256(pair_rows),
        },
        "uses_realized_outcomes": False,
    }


def _rank_transport(row: np.ndarray, latent: np.ndarray) -> np.ndarray:
    """Reorder one row so its ranks follow ``latent``, ties by world index."""

    if row.ndim != 1 or latent.ndim != 1 or row.shape != latent.shape:
        _fail("cross-law rank-transport vectors differ")
    order = np.argsort(latent, kind="stable")
    ranks = np.empty(order.size, dtype=np.int64)
    ranks[order] = np.arange(order.size, dtype=np.int64)
    return np.sort(row, kind="stable")[ranks]


def _ordered_unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    retained: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            retained.append(value)
    return retained


def _discovery_seed(
    *,
    season: int,
    week: int,
    cbwu_seed_label: str,
    base_world_receipt: Mapping[str, object],
) -> tuple[int, dict[str, object]]:
    material = {
        "schema_version": "prospective-cross-law-discovery-seed/v1",
        "season": season,
        "week": week,
        "cbwu_seed_label": cbwu_seed_label,
        "base_world_receipt": dict(base_world_receipt),
        "law_sha256": LAW_SHA256,
    }
    encoded = _canonical_json_bytes(material)
    digest = sha256(encoded).digest()
    return int.from_bytes(digest[:8], "big"), {
        **material,
        "seed_material_sha256": digest.hex(),
        "seed_material_byte_count": len(encoded),
        "canonicalization": (
            "UTF-8 JSON;sort_keys=true;separators=comma-colon;"
            "ensure_ascii=false;allow_nan=false"
        ),
        "derivation": (
            "SHA256(canonical-seed-material);first-8-digest-bytes;"
            "unsigned-big-endian-uint64"
        ),
        "seed_digest_first_8_bytes_hex": digest[:8].hex(),
        "numpy_generator": "numpy.random.default_rng-PCG64",
        "factor_draw_order": (
            "ordered-game:regime-uniforms,game-standard-normals,"
            "ordered-team-standard-normals"
        ),
        "numpy_seed_uint64": int.from_bytes(digest[:8], "big"),
    }


def _validate_player_rows(
    batch: CandidateBatch,
) -> tuple[list[str], list[str], list[str], tuple[int, ...]]:
    games: list[str] = []
    teams: list[str] = []
    positions: list[str] = []
    dst_indices: list[int] = []
    for index, raw_row in enumerate(batch.player_rows):
        if not isinstance(raw_row, Mapping):
            _fail(f"cross-law player row[{index}] is not a mapping")
        row = dict(raw_row)
        for key, value in row.items():
            normalized = str(key).strip().lower()
            if any(token in normalized for token in _OUTCOME_TOKENS):
                absent = value is None or (
                    isinstance(value, (float, np.floating))
                    and math.isnan(float(value))
                )
                if not absent:
                    _fail("cross-law transform received realized outcome data")
        position = str(row.get("pos") or "").strip().upper()
        team = str(row.get("team") or "").strip()
        game = str(row.get("game_id") or "").strip()
        if not position or not team:
            _fail(f"cross-law player row[{index}] lacks position/team")
        if position == "DST":
            dst_indices.append(index)
        elif not game:
            _fail(f"cross-law non-DST player row[{index}] lacks game_id")
        games.append(game)
        teams.append(team)
        positions.append(position)
    if not dst_indices:
        _fail("cross-law player universe lacks DST rows")
    return games, teams, positions, tuple(dst_indices)


def _apply_discovery_overlay(
    base_draws: np.ndarray,
    *,
    games: Sequence[str],
    teams: Sequence[str],
    positions: Sequence[str],
    seed: int,
) -> np.ndarray:
    """Apply the exact fixed law while preserving each row's bit multiset."""

    base = np.asarray(base_draws)
    if (
        base.ndim != 2
        or base.dtype.kind != "f"
        or base.shape[1] != BASE_WORLD_COUNT
        or not np.isfinite(base).all()
        or len(games) != base.shape[0]
        or len(teams) != base.shape[0]
        or len(positions) != base.shape[0]
    ):
        _fail("cross-law base player-world bank differs")
    rng = np.random.default_rng(seed)
    discovery = np.array(base, copy=True, order="C")
    for game in _ordered_unique(list(games)):
        if not game:
            continue
        indices = [
            index
            for index, observed in enumerate(games)
            if observed == game and positions[index] != "DST"
        ]
        if len(indices) < 2:
            continue
        regime = rng.random(base.shape[1]) < LAW["base"]
        lam = np.where(regime, LAW["lam_hi"], LAW["lam_lo"])
        game_factor = rng.standard_normal(base.shape[1])
        team_factors = {
            team: rng.standard_normal(base.shape[1])
            for team in _ordered_unique([teams[index] for index in indices])
        }
        for index in indices:
            row = discovery[index]
            if float(np.std(row, dtype=np.float64)) < 1e-9:
                continue
            order = np.argsort(row, kind="stable")
            ranks = np.empty(row.size, dtype=np.int64)
            ranks[order] = np.arange(1, row.size + 1, dtype=np.int64)
            z0 = ndtri(ranks.astype(np.float64) / (row.size + 1.0))
            latent = (
                z0
                + lam * game_factor
                + LAW["lam_team"] * team_factors[teams[index]]
            )
            discovery[index] = _rank_transport(row, latent)

    base_manifest = _marginal_manifest(base, range(base.shape[0]))
    discovery_manifest = _marginal_manifest(
        discovery, range(discovery.shape[0])
    )
    if base_manifest != discovery_manifest:
        _fail("cross-law overlay drifted at least one player marginal")
    for index, position in enumerate(positions):
        if position == "DST" and (
            _array_receipt(base[index]) != _array_receipt(discovery[index])
        ):
            _fail("cross-law overlay changed a DST row")
    return discovery


def _construction_binding(
    batch: CandidateBatch,
    *,
    stack: StackRules,
    policy_env: Mapping[str, str],
    locks: frozenset[object],
) -> dict[str, object]:
    if not isinstance(stack, StackRules):
        _fail("cross-law transform requires explicit StackRules")
    if not isinstance(policy_env, Mapping) or any(
        type(key) is not str or type(value) is not str
        for key, value in policy_env.items()
    ):
        _fail("cross-law optimizer environment must be string-to-string")
    receipt_value = batch.metadata.get("construction_preset_receipt")
    if not isinstance(receipt_value, Mapping):
        _fail("cross-law base batch lacks its construction preset receipt")
    receipt = dict(receipt_value)
    retained_sha = receipt.pop("sha256", None)
    effective_id = receipt.pop("effective_id", None)
    if (
        type(retained_sha) is not str
        or _SHA256.fullmatch(retained_sha) is None
        or retained_sha != canonical_sha256(receipt)
        or effective_id
        != f"{receipt.get('base_preset_id')}@sha256:{retained_sha}"
        or receipt.get("schema_version") != "classic-construction-preset-v1"
        or receipt.get("stack") != asdict(stack)
    ):
        _fail("cross-law construction preset/StackRules binding differs")
    expected_env = {
        "MIN_LINEUP_SALARY": str(receipt["min_salary"]),
        "MIN_GAMES": str(receipt["min_games"]),
        "PUNT_MIN": str(receipt["punt_min"]),
        "PUNT_MAX": (
            "" if receipt["punt_max_salary"] is None
            else str(receipt["punt_max_salary"])
        ),
        "PUNT_STRICT": "1" if receipt["punt_strict"] else "",
        "VALUE2_MIN": str(receipt["value2_min"]),
        "VALUE2_MAX": str(receipt["value2_max"]),
        "OWN_BARBELL": "1" if receipt["own_barbell"] else "",
        "OWN_BARBELL_LOW": str(receipt["own_barbell_low"]),
        "OWN_BARBELL_HIGH": str(receipt["own_barbell_high"]),
        "OWN_BARBELL_NLOW": str(receipt["own_barbell_nlow"]),
        "OWN_BARBELL_NHIGH": str(receipt["own_barbell_nhigh"]),
        "MAX_PER_GAME": str(receipt["max_per_game"]),
        "MIN_LOWOWN": str(receipt["min_lowown"]),
        "MAX_OVERLAP": str(receipt["max_overlap"]),
    }
    for key, expected in expected_env.items():
        if policy_env.get(key) != expected:
            _fail(f"cross-law optimizer environment differs at {key}")
    universe = set(batch.player_ids)
    if not locks <= universe:
        _fail("cross-law locks escape the base player universe")
    lock_tokens = [_identity_token(value) for value in locks]
    lock_tokens.sort(key=lambda value: _canonical_json_bytes(value))
    return {
        "construction_preset_receipt": dict(receipt_value),
        "stack_rules": asdict(stack),
        "optimizer_environment_sha256": canonical_sha256(dict(policy_env)),
        "locks": lock_tokens,
        "locks_sha256": canonical_sha256(lock_tokens),
        "same_stack_rules_as_base": True,
    }


def _construction_audit_row(
    lineup: Lineup,
    *,
    source_by_id: Mapping[object, Mapping[str, object]],
    all_source_rows: Sequence[Mapping[str, object]],
    preset: Mapping[str, object],
    stack: StackRules,
    locks: frozenset[object],
) -> dict[str, object]:
    """Audit one solver result against DK legality and the bound preset."""

    violations: list[str] = []
    raw_ids = [player.get("id") for player in lineup.players]
    if len(raw_ids) != 9 or len(set(raw_ids)) != 9:
        violations.append("roster-size-or-duplicate-player")
    try:
        authoritative = [source_by_id[player_id] for player_id in raw_ids]
    except KeyError:
        authoritative = []
        violations.append("player-outside-authoritative-pool")
    if authoritative:
        for observed, expected in zip(
            lineup.players, authoritative, strict=True
        ):
            if any(observed.get(key) != expected.get(key) for key in (
                "id", "pos", "team", "opp", "game_id", "salary",
            )):
                violations.append("solver-mutated-construction-field")
                break

    positions = Counter(str(row.get("pos") or "") for row in authoritative)
    expected_positions = (
        positions.get("QB") == 1
        and positions.get("DST") == 1
        and 2 <= positions.get("RB", 0) <= 3
        and 3 <= positions.get("WR", 0) <= 4
        and 1 <= positions.get("TE", 0) <= 2
        and sum(positions.values()) == 9
    )
    if not expected_positions:
        violations.append("dk-position-shape")
    teams = Counter(str(row.get("team") or "") for row in authoritative)
    if len(teams) < 2 or (teams and max(teams.values()) > 8):
        violations.append("dk-team-shape")
    salary = sum(int(row.get("salary") or 0) for row in authoritative)
    minimum_salary = int(preset.get("min_salary") or 0)
    if not minimum_salary <= salary <= 50_000:
        violations.append("salary-bounds")
    games = {
        str(row.get("game_id")) for row in authoritative
        if row.get("game_id")
    }
    if len(games) < int(preset.get("min_games") or 1):
        violations.append("minimum-games")
    if not locks <= set(raw_ids):
        violations.append("locks")

    qbs = [row for row in authoritative if row.get("pos") == "QB"]
    if len(qbs) == 1:
        qb = qbs[0]
        same_team_catchers = sum(
            row.get("team") == qb.get("team")
            and row.get("pos") in {"WR", "TE"}
            for row in authoritative
        )
        bring_backs = sum(
            row.get("team") == qb.get("opp")
            and row.get("pos") in {"RB", "WR", "TE"}
            for row in authoritative
        )
        if same_team_catchers < stack.qb_stack_min:
            violations.append("qb-stack-min")
        if (
            stack.qb_stack_max is not None
            and same_team_catchers > stack.qb_stack_max
        ):
            violations.append("qb-stack-max")
        if bring_backs < stack.bring_back_min:
            violations.append("bring-back-min")
        if (
            stack.bring_back_max is not None
            and bring_backs > stack.bring_back_max
        ):
            violations.append("bring-back-max")

    selected_rbs = [row for row in authoritative if row.get("pos") == "RB"]
    selected_dsts = [row for row in authoritative if row.get("pos") == "DST"]
    has_rb_vs_dst = any(
        rb.get("team") == dst.get("opp")
        for rb in selected_rbs for dst in selected_dsts
    )
    if stack.forbid_rb_vs_dst and has_rb_vs_dst:
        violations.append("forbid-rb-vs-dst")
    if stack.require_rb_vs_dst and not has_rb_vs_dst:
        violations.append("require-rb-vs-dst")
    rb_teams = Counter(str(row.get("team") or "") for row in selected_rbs)
    has_same_team_rbs = bool(rb_teams) and max(rb_teams.values()) >= 2
    if stack.forbid_two_rb_same_team and has_same_team_rbs:
        violations.append("forbid-two-rb-same-team")
    if stack.require_two_rb_same_team and not has_same_team_rbs:
        violations.append("require-two-rb-same-team")

    punt_min = int(preset.get("punt_min") or 0)
    punt_max = preset.get("punt_max_salary")
    if punt_min and punt_max is not None:
        if preset.get("punt_strict") and any(
            "punt_elig" in row for row in all_source_rows
        ):
            eligible = {
                row["id"] for row in all_source_rows if row.get("punt_elig")
            }
        else:
            eligible = {
                row["id"] for row in all_source_rows
                if int(row.get("salary") or 0) <= int(punt_max)
            }
        if eligible and len(set(raw_ids) & eligible) < punt_min:
            violations.append("punt-min")
    value2_min = int(preset.get("value2_min") or 0)
    if value2_min:
        value2_max = int(preset.get("value2_max") or 5_300)
        eligible = {
            row["id"] for row in all_source_rows
            if row.get("pos") != "DST"
            and int(row.get("salary") or 0) <= value2_max
        }
        if len(eligible) >= value2_min and len(set(raw_ids) & eligible) < value2_min:
            violations.append("value2-min")
    if preset.get("own_barbell") and any(
        row.get("own_est") is not None for row in all_source_rows
    ):
        low = float(preset.get("own_barbell_low") or 0.05)
        high = float(preset.get("own_barbell_high") or 0.20)
        low_ids = {
            row["id"] for row in all_source_rows
            if row.get("pos") != "DST" and float(row.get("own_est") or 0) <= low
        }
        high_ids = {
            row["id"] for row in all_source_rows
            if row.get("pos") != "DST" and float(row.get("own_est") or 0) >= high
        }
        if (
            len(low_ids) >= int(preset.get("own_barbell_nlow") or 0)
            and len(set(raw_ids) & low_ids)
            < int(preset.get("own_barbell_nlow") or 0)
        ):
            violations.append("own-barbell-low")
        if (
            len(high_ids) >= int(preset.get("own_barbell_nhigh") or 0)
            and len(set(raw_ids) & high_ids)
            < int(preset.get("own_barbell_nhigh") or 0)
        ):
            violations.append("own-barbell-high")
    max_per_game = int(preset.get("max_per_game") or 0)
    if max_per_game:
        game_counts = Counter(
            str(row.get("game_id")) for row in authoritative
            if row.get("game_id")
        )
        if game_counts and max(game_counts.values()) > max_per_game:
            violations.append("max-per-game")
    min_lowown = int(preset.get("min_lowown") or 0)
    if min_lowown:
        eligible = {row["id"] for row in all_source_rows if row.get("low_own")}
        required = min(min_lowown, len(eligible))
        if eligible and len(set(raw_ids) & eligible) < required:
            violations.append("min-low-own")

    if violations:
        _fail(
            "cross-law candidate violates bound construction: "
            + ",".join(sorted(set(violations)))
        )
    return {
        "roster_sha256": _roster_sha256(lineup),
        "salary": salary,
        "position_counts": dict(sorted(positions.items())),
        "team_count": len(teams),
        "game_count": len(games),
        "dk_legality_pass": True,
        "salary_pass": True,
        "stack_rules_pass": True,
        "construction_preset_pass": True,
    }


def _construction_integrity_trace(
    batch: CandidateBatch,
    candidates: Sequence[Lineup],
    *,
    base_candidate_count: int,
    construction: Mapping[str, object],
    stack: StackRules,
    locks: frozenset[object],
) -> dict[str, object]:
    raw_preset = construction.get("construction_preset_receipt")
    if not isinstance(raw_preset, Mapping):
        _fail("cross-law construction audit lacks preset")
    preset = dict(raw_preset)
    source_by_id = {
        row["id"]: row for row in batch.player_rows
        if isinstance(row, Mapping) and "id" in row
    }
    if len(source_by_id) != len(batch.player_rows):
        _fail("cross-law construction audit player universe differs")
    rows = [
        _construction_audit_row(
            lineup,
            source_by_id=source_by_id,
            all_source_rows=batch.player_rows,
            preset=preset,
            stack=stack,
            locks=locks,
        )
        for lineup in candidates
    ]
    base_rows = rows[:base_candidate_count]
    discovery_rows = rows[base_candidate_count:]
    legality_law = {
        "roster_size": 9,
        "salary_cap": 50_000,
        "position_shape": "QB1,DST1,RB2-3,WR3-4,TE1-2",
        "minimum_teams": 2,
        "maximum_from_one_team": 8,
    }
    salary_law = {
        "dk_salary_cap": 50_000,
        "construction_min_salary": int(preset.get("min_salary") or 0),
    }
    return {
        "definition": (
            "authoritative-player-row-audit-of-DK-legality,salary,locks,"
            "stack-rules-and-every-active-bound-construction-preset-rule"
        ),
        "base_candidate_count": len(base_rows),
        "discovery_candidate_count": len(discovery_rows),
        "all_candidate_count": len(rows),
        "dk_legality_law": legality_law,
        "dk_legality_law_sha256": canonical_sha256(legality_law),
        "salary_law": salary_law,
        "salary_law_sha256": canonical_sha256(salary_law),
        "construction_preset_receipt_sha256": str(preset.get("sha256")),
        "stack_rules": asdict(stack),
        "stack_rules_sha256": canonical_sha256(asdict(stack)),
        "optimizer_environment_sha256": construction.get(
            "optimizer_environment_sha256"
        ),
        "locks_sha256": construction.get("locks_sha256"),
        "base_audit_manifest_sha256": canonical_sha256(base_rows),
        "discovery_audit_manifest_sha256": canonical_sha256(discovery_rows),
        "complete_audit_manifest_sha256": canonical_sha256(rows),
        "base_prefix_unchanged": True,
        "same_construction_preset_for_base_and_discovery": True,
        "same_stack_rules_for_base_and_discovery": True,
        "same_salary_rules_for_base_and_discovery": True,
        "same_legality_rules_for_base_and_discovery": True,
        "all_candidates_pass": True,
        "uses_realized_outcomes": False,
    }


def _candidate_influence_trace(
    *,
    base_candidates: Sequence[Lineup],
    ledger: Mapping[str, object],
) -> dict[str, object]:
    rows = ledger.get("rows")
    if not isinstance(rows, Sequence):
        _fail("cross-law candidate influence ledger differs")
    base_sets = [set(map(str, lineup.ids)) for lineup in base_candidates]
    prior_discovery: list[set[str]] = []
    trace_rows: list[dict[str, object]] = []
    for ordinal, ledger_row in enumerate(rows):
        if not isinstance(ledger_row, Mapping):
            _fail("cross-law candidate influence row differs")
        raw_player_ids = ledger_row.get("player_ids")
        if not isinstance(raw_player_ids, Sequence) or isinstance(
            raw_player_ids, (str, bytes)
        ):
            _fail("cross-law candidate influence solve lacks roster")
        roster = set(map(str, raw_player_ids))
        if len(roster) != 9:
            _fail("cross-law candidate influence roster differs")
        base_overlap = max((len(roster & other) for other in base_sets), default=0)
        discovery_overlap = max(
            (len(roster & other) for other in prior_discovery), default=0
        )
        status = str(ledger_row.get("status"))
        exact = status == "dup"
        trace_rows.append({
            "attempt_ordinal": ordinal,
            "roster_sha256": ledger_row.get("roster_sha256"),
            "status": status,
            "duplicate_origin": ledger_row.get("duplicate_origin"),
            "max_shared_players_with_base": base_overlap,
            "max_shared_players_with_prior_discovery": discovery_overlap,
            "near_duplicate_of_base": (not exact and base_overlap == 8),
            "near_duplicate_of_prior_discovery": (
                not exact and discovery_overlap == 8
            ),
        })
        prior_discovery.append(roster)
    exact_count = sum(row["status"] == "dup" for row in trace_rows)
    near_base = sum(row["near_duplicate_of_base"] for row in trace_rows)
    near_prior = sum(
        row["near_duplicate_of_prior_discovery"] for row in trace_rows
    )
    new_count = sum(row["status"] == "new" for row in trace_rows)
    failure_count = sum(
        int(ledger.get("status_counts", {}).get(status, 0))  # type: ignore[union-attr]
        for status in ("error", "infeasible", "exhausted")
    )
    attempt_count = len(trace_rows)
    durations = [float(row["duration_seconds"]) for row in rows]
    attempt_hashes = {
        str(row["roster_sha256"]) for row in trace_rows
        if row["roster_sha256"] is not None
    }
    base_hashes = {_roster_sha256(lineup) for lineup in base_candidates}
    intersection = len(attempt_hashes & base_hashes)
    union = len(attempt_hashes | base_hashes)
    return {
        "definition": {
            "exact_duplicate": "identical-nine-player-roster",
            "near_duplicate": (
                "non-exact-roster-sharing-exactly-eight-of-nine-player-IDs"
            ),
            "family_yield": "unique-new-discovery-rosters/attempted-solves",
            "rates_denominator": "all-60-requested-discovery-solves",
        },
        "attempt_count": attempt_count,
        "successful_solve_count": attempt_count - failure_count,
        "solve_failure_count": failure_count,
        "solve_failure_rate": float(failure_count / attempt_count),
        "solve_runtime_seconds": {
            "total": float(sum(durations)),
            "mean_per_attempt": float(np.mean(durations, dtype=np.float64)),
            "minimum_attempt": float(min(durations)),
            "maximum_attempt": float(max(durations)),
            "ledger_duration_seconds_by_family": dict(
                ledger.get("duration_seconds_by_family", {})
            ),
            "ledger_duration_seconds_by_status": dict(
                ledger.get("duration_seconds_by_status", {})
            ),
        },
        "exact_duplicate_count": exact_count,
        "exact_duplicate_rate": float(exact_count / attempt_count),
        "near_duplicate_of_base_count": near_base,
        "near_duplicate_of_base_rate": float(near_base / attempt_count),
        "near_duplicate_of_prior_discovery_count": near_prior,
        "near_duplicate_of_prior_discovery_rate": float(
            near_prior / attempt_count
        ),
        "unique_family_yield_count": new_count,
        "unique_family_yield_rate": float(new_count / attempt_count),
        "discovery_attempt_base_population_exact_jaccard": (
            float(intersection / union) if union else 0.0
        ),
        "trace_rows_sha256": canonical_sha256(trace_rows),
        "attempt_roster_manifest_sha256": canonical_sha256([
            row["roster_sha256"] for row in trace_rows
        ]),
        "uses_realized_outcomes": False,
    }


def _production_influence_trace(
    *,
    base: np.ndarray,
    discovery: np.ndarray,
    player_ids: Sequence[object],
    games: Sequence[str],
    teams: Sequence[str],
    positions: Sequence[str],
    base_marginals: Sequence[Mapping[str, object]],
    discovery_marginals: Sequence[Mapping[str, object]],
    seed_receipt: Mapping[str, object],
    candidate_trace: Mapping[str, object],
    construction_trace: Mapping[str, object],
) -> dict[str, object]:
    if list(base_marginals) != list(discovery_marginals):
        _fail("cross-law influence trace marginal proof differs")
    proof_rows = [{
        "player_id": _identity_token(player_id),
        "base_bitwise_multiset_sha256": base_marginals[index][
            "bitwise_multiset_sha256"
        ],
        "discovery_bitwise_multiset_sha256": discovery_marginals[index][
            "bitwise_multiset_sha256"
        ],
        "identical": True,
    } for index, player_id in enumerate(player_ids)]
    base_receipt = _array_receipt(base)
    discovery_receipt = _array_receipt(discovery)
    body: dict[str, object] = {
        "schema_version": INFLUENCE_TRACE_SCHEMA,
        "law_sha256": LAW_SHA256,
        "seed_derivation_receipt": dict(seed_receipt),
        "per_player_marginal_proof": {
            "definition": (
                "sorted-raw-floating-value-byte-multiset-per-player;"
                "rank-order-may-change,value-bits-may-not"
            ),
            "player_count": len(proof_rows),
            "world_count_per_player": int(base.shape[1]),
            "identical_player_count": len(proof_rows),
            "all_bitwise_multisets_identical": True,
            "base_manifest_sha256": canonical_sha256(base_marginals),
            "discovery_manifest_sha256": canonical_sha256(
                discovery_marginals
            ),
            "proof_rows_sha256": canonical_sha256(proof_rows),
        },
        "joint_dependence": _joint_dependence_trace(
            base,
            discovery,
            games=games,
            teams=teams,
            positions=positions,
        ),
        "world_rank_correlation": _world_rank_trace(base, discovery),
        "candidate_novelty_and_yield": dict(candidate_trace),
        "construction_integrity": dict(construction_trace),
        "world_content_binding": {
            "base_world_bank_receipt": base_receipt,
            "discovery_world_bank_receipt": discovery_receipt,
            "base_world_bank_sha256": base_receipt["sha256"],
            "discovery_world_bank_sha256": discovery_receipt["sha256"],
            "selection_scoring_bank": "base",
            "discovery_bank_used_for_selection_scoring": False,
            "suite_must_persist_base_and_discovery_create_only": True,
            "suite_must_bind_independent_audit_bank_identity": True,
            "suite_owns_selected_discovery_candidate_count": True,
        },
        "uses_realized_outcomes": False,
        "outcome_columns_read": [],
        "cloud_mutation_performed": False,
        "complete": True,
    }
    body["influence_trace_sha256"] = canonical_sha256(body)
    return body


def _validate_native_allocation(batch: CandidateBatch) -> dict[str, int | bool]:
    value = batch.metadata.get("generation_allocation")
    if not isinstance(value, Mapping):
        _fail("cross-law base batch lacks native generation allocation")
    expected = {
        "leverage_requested": BASE_LEVERAGE_ATTEMPTS,
        "leverage_solve_attempts": BASE_LEVERAGE_ATTEMPTS,
        "leverage_solver_errors": 0,
        "leverage_infeasible": 0,
        "leverage_successful": BASE_LEVERAGE_ATTEMPTS,
        "boom_requested": BASE_BOOM_ATTEMPTS,
        "boom_attempted": BASE_BOOM_ATTEMPTS,
        "boom_successful": BASE_BOOM_ATTEMPTS,
        "boom_solver_errors": 0,
        "boom_infeasible": 0,
        "boom_failures": 0,
        "boom_unique_fill": False,
        "core_requested": BASE_LEVERAGE_ATTEMPTS + BASE_BOOM_ATTEMPTS,
    }
    for key, expected_value in expected.items():
        observed = value.get(key)
        if type(observed) is not type(expected_value) or observed != expected_value:
            _fail(f"cross-law native allocation differs at {key}")
    return expected


def _candidate_totals(
    candidates: Sequence[Lineup],
    *,
    player_ids: Sequence[object],
    base_draws: np.ndarray,
) -> np.ndarray:
    row_by_id = {player_id: index for index, player_id in enumerate(player_ids)}
    totals: list[np.ndarray] = []
    for ordinal, lineup in enumerate(candidates):
        try:
            rows = [row_by_id[player["id"]] for player in lineup.players]
        except (KeyError, TypeError) as exc:
            raise ProspectiveCrossLawDiscoveryError(
                f"cross-law candidate[{ordinal}] escapes the base universe"
            ) from exc
        if len(rows) != 9 or len(set(rows)) != 9:
            _fail(f"cross-law candidate[{ordinal}] roster differs")
        totals.append(np.asarray(base_draws)[rows].sum(axis=0))
    if not totals:
        _fail("cross-law candidate pool is empty")
    return np.stack(totals)


def _validated_inputs(
    batch: CandidateBatch,
    *,
    season: int,
    week: int,
    cbwu_seed_label: str,
    stack: StackRules,
    policy_env: Mapping[str, str],
    locks: frozenset[object],
) -> tuple[
    np.ndarray,
    list[str],
    list[str],
    list[str],
    tuple[int, ...],
    dict[str, object],
    dict[str, object],
]:
    _validate_candidate_batch(batch)
    if type(season) is not int or not 2000 <= season <= 2100:
        _fail("cross-law season differs")
    if type(week) is not int or not 1 <= week <= 18:
        _fail("cross-law week differs")
    if cbwu_seed_label not in SEED_LABELS:
        _fail("cross-law CBWU seed label differs")
    if batch.metadata.get("season") != season or batch.metadata.get("week") != week:
        _fail("cross-law base batch season/week differs")
    if "cross_law_discovery" in batch.metadata:
        _fail("cross-law base batch was already transformed")
    base_draws = np.asarray(batch.row_draws)
    if (
        base_draws.ndim != 2
        or base_draws.dtype.kind != "f"
        or base_draws.shape[1] != BASE_WORLD_COUNT
        or not np.isfinite(base_draws).all()
    ):
        _fail("cross-law base row_draws are not one finite 10,000-world bank")
    base_totals = _candidate_totals(
        batch.candidates,
        player_ids=batch.player_ids,
        base_draws=base_draws,
    )
    if _array_receipt(base_totals) != _array_receipt(batch.candidate_totals):
        _fail("cross-law base candidate scores are not from base row_draws")
    games, teams, positions, dst_indices = _validate_player_rows(batch)
    allocation = _validate_native_allocation(batch)
    construction = _construction_binding(
        batch, stack=stack, policy_env=policy_env, locks=locks
    )
    return (
        base_draws,
        games,
        teams,
        positions,
        dst_indices,
        {str(key): value for key, value in allocation.items()},
        construction,
    )


def build_cross_law_discovery_batch(
    base_batch: CandidateBatch,
    *,
    season: int,
    week: int,
    cbwu_seed_label: str,
    stack: StackRules,
    policy_env: Mapping[str, str],
    locks: frozenset[object] = frozenset(),
) -> CandidateBatch:
    """Perform the exact 60-attempt generation-only discovery treatment."""

    (
        base_draws,
        games,
        teams,
        positions,
        dst_indices,
        allocation,
        construction,
    ) = _validated_inputs(
        base_batch,
        season=season,
        week=week,
        cbwu_seed_label=cbwu_seed_label,
        stack=stack,
        policy_env=policy_env,
        locks=locks,
    )
    # Fail before treatment solves if the native/base candidates do not in
    # fact obey the construction receipt that the arm claims to preserve.
    _construction_integrity_trace(
        base_batch,
        base_batch.candidates,
        base_candidate_count=len(base_batch.candidates),
        construction=construction,
        stack=stack,
        locks=locks,
    )
    base_world_receipt = _array_receipt(base_draws)
    seed, seed_receipt = _discovery_seed(
        season=season,
        week=week,
        cbwu_seed_label=cbwu_seed_label,
        base_world_receipt=base_world_receipt,
    )
    discovery = _apply_discovery_overlay(
        base_draws,
        games=games,
        teams=teams,
        positions=positions,
        seed=seed,
    )
    base_marginals = _marginal_manifest(base_draws, base_batch.player_ids)
    discovery_marginals = _marginal_manifest(discovery, base_batch.player_ids)
    if base_marginals != discovery_marginals:
        _fail("cross-law discovery marginal manifest differs from base")
    joint_trace = _same_team_co_boom_trace(
        base_draws,
        discovery,
        teams=teams,
        positions=positions,
    )
    world_order = np.argsort(discovery.sum(axis=0), kind="stable")[::-1]
    if len(world_order) < DISCOVERY_ATTEMPTS:
        _fail("cross-law discovery world bank is short")

    candidates = list(base_batch.candidates)
    seen = {lineup.ids for lineup in candidates}
    all_tags = {
        key: list(value) for key, value in base_batch.all_tags.items()
    }
    exposure = SolveExposureLedger(
        source_label=f"{cbwu_seed_label.lower()}-cross-law",
        existing_rosters=(lineup.ids for lineup in candidates),
    )
    new_candidates: list[Lineup] = []
    for attempt, raw_world in enumerate(world_order[:DISCOVERY_ATTEMPTS]):
        world = int(raw_world)
        sim_pool = [
            {
                **dict(player),
                OBJECTIVE_COLUMN: float(discovery[index, world]),
            }
            for index, player in enumerate(base_batch.player_rows)
        ]
        solve_started = time.perf_counter()
        try:
            lineup = optimize(
                sim_pool,
                stack=stack,
                objective_col=OBJECTIVE_COLUMN,
                locks=set(locks),
                env=dict(policy_env),
            )
        except Exception as exc:
            exposure.record(
                family=FAMILY,
                requested_ordinal=attempt,
                world_id=world,
                status="error",
                duration_seconds=float(time.perf_counter() - solve_started),
            )
            raise ProspectiveCrossLawDiscoveryError(
                f"cross-law discovery MILP attempt[{attempt}] failed"
            ) from exc
        duration_seconds = float(time.perf_counter() - solve_started)
        if lineup is None:
            exposure.record(
                family=FAMILY,
                requested_ordinal=attempt,
                world_id=world,
                status="infeasible",
                duration_seconds=duration_seconds,
            )
            _fail(f"cross-law discovery MILP attempt[{attempt}] was infeasible")
        roster_hash = _roster_sha256(lineup)
        duplicate = lineup.ids in seen
        row = exposure.record(
            family=FAMILY,
            requested_ordinal=attempt,
            world_id=world,
            status="dup" if duplicate else "new",
            roster_ids=lineup.ids,
            duration_seconds=duration_seconds,
        )
        if row["roster_sha256"] != roster_hash:
            _fail("cross-law shared exposure roster hash differs")
        tags = all_tags.setdefault(lineup.ids, [])
        if FAMILY not in tags:
            tags.append(FAMILY)
        if not duplicate:
            lineup.tag = FAMILY
            seen.add(lineup.ids)
            candidates.append(lineup)
            new_candidates.append(lineup)
    ledger = exposure.finalize(
        expected_requests_by_family={FAMILY: DISCOVERY_ATTEMPTS}
    )
    if ledger["attempt_count"] != DISCOVERY_ATTEMPTS:
        _fail("cross-law discovery attempt ledger is short")

    # The solver receives copied player mappings only.  Recheck the source
    # array now, then build every score from that source rather than discovery.
    if _array_receipt(base_batch.row_draws) != base_world_receipt:
        _fail("cross-law discovery mutated the base selection bank")
    combined_totals = _candidate_totals(
        candidates,
        player_ids=base_batch.player_ids,
        base_draws=base_draws,
    )
    new_count = len(new_candidates)
    duplicate_count = DISCOVERY_ATTEMPTS - new_count
    candidate_trace = _candidate_influence_trace(
        base_candidates=base_batch.candidates,
        ledger=ledger,
    )
    construction_trace = _construction_integrity_trace(
        base_batch,
        candidates,
        base_candidate_count=len(base_batch.candidates),
        construction=construction,
        stack=stack,
        locks=locks,
    )
    influence_trace = _production_influence_trace(
        base=base_draws,
        discovery=discovery,
        player_ids=base_batch.player_ids,
        games=games,
        teams=teams,
        positions=positions,
        base_marginals=base_marginals,
        discovery_marginals=discovery_marginals,
        seed_receipt=seed_receipt,
        candidate_trace=candidate_trace,
        construction_trace=construction_trace,
    )
    receipt: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA,
        "version": VERSION,
        "family": FAMILY,
        "season": season,
        "week": week,
        "cbwu_seed_label": cbwu_seed_label,
        "law": dict(LAW),
        "law_sha256": LAW_SHA256,
        "seed_receipt": seed_receipt,
        "base_world_bank_receipt": base_world_receipt,
        "discovery_world_bank_receipt": _array_receipt(discovery),
        "base_marginal_manifest_sha256": canonical_sha256(base_marginals),
        "discovery_marginal_manifest_sha256": canonical_sha256(
            discovery_marginals
        ),
        "all_player_marginals_bitwise_identical": True,
        "dst_row_indices": list(dst_indices),
        "dst_rows_bitwise_untouched": True,
        "same_team_co_boom_trace": joint_trace,
        "production_influence_trace": influence_trace,
        "production_influence_trace_sha256": influence_trace[
            "influence_trace_sha256"
        ],
        "discovery_world_order_sha256": canonical_sha256(
            [int(value) for value in world_order]
        ),
        "attempted_world_indices": [
            int(value) for value in world_order[:DISCOVERY_ATTEMPTS]
        ],
        "attempt_count": DISCOVERY_ATTEMPTS,
        "milp_attempt_count": DISCOVERY_ATTEMPTS,
        "solver_error_count": 0,
        "infeasible_count": 0,
        "new_candidate_count": new_count,
        "duplicate_candidate_count": duplicate_count,
        "base_candidate_count": len(base_batch.candidates),
        "transformed_candidate_count": len(candidates),
        "native_generation_allocation": allocation,
        "construction_binding": construction,
        "exposure_ledger": ledger,
        "exposure_ledger_sha256": ledger["ledger_sha256"],
        "base_candidate_totals_receipt": _array_receipt(
            base_batch.candidate_totals
        ),
        "transformed_candidate_totals_receipt": _array_receipt(
            combined_totals
        ),
        "all_candidate_selection_scores_from_untouched_base_row_draws": True,
        "discovery_worlds_used_for_selection_scoring": False,
        "deduplicated_against_complete_existing_base_pool": True,
        "uses_realized_outcomes": False,
        "outcome_columns_read": [],
        "cloud_mutation_performed": False,
        "production_policy_changed": False,
        "complete": True,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    transformed = CandidateBatch(
        candidates=tuple(candidates),
        candidate_totals=combined_totals,
        player_ids=base_batch.player_ids,
        player_rows=base_batch.player_rows,
        row_draws=base_batch.row_draws,
        all_tags={key: tuple(value) for key, value in all_tags.items()},
        metadata={
            **base_batch.metadata,
            "cross_law_discovery": receipt,
            "uses_realized_outcomes": False,
            "production_enabled": False,
        },
    )
    return validate_cross_law_discovery_batch(
        base_batch,
        transformed,
        season=season,
        week=week,
        cbwu_seed_label=cbwu_seed_label,
        stack=stack,
        policy_env=policy_env,
        locks=locks,
    )


def validate_cross_law_discovery_batch(
    base_batch: CandidateBatch,
    transformed: CandidateBatch,
    *,
    season: int,
    week: int,
    cbwu_seed_label: str,
    stack: StackRules,
    policy_env: Mapping[str, str],
    locks: frozenset[object] = frozenset(),
) -> CandidateBatch:
    """Independently validate the base-law scoring and full discovery receipt."""

    (
        base_draws,
        games,
        teams,
        positions,
        dst_indices,
        allocation,
        construction,
    ) = _validated_inputs(
        base_batch,
        season=season,
        week=week,
        cbwu_seed_label=cbwu_seed_label,
        stack=stack,
        policy_env=policy_env,
        locks=locks,
    )
    _validate_candidate_batch(transformed)
    if (
        transformed.player_ids != base_batch.player_ids
        or transformed.player_rows != base_batch.player_rows
        or _array_receipt(transformed.row_draws) != _array_receipt(base_draws)
        or tuple(lineup.ids for lineup in transformed.candidates[:len(base_batch.candidates)])
        != tuple(lineup.ids for lineup in base_batch.candidates)
    ):
        _fail("cross-law transformed base/player/world prefix differs")
    expected_totals = _candidate_totals(
        transformed.candidates,
        player_ids=base_batch.player_ids,
        base_draws=base_draws,
    )
    if _array_receipt(expected_totals) != _array_receipt(
        transformed.candidate_totals
    ):
        _fail("cross-law transformed candidate scores are not base-law scores")
    raw_receipt = transformed.metadata.get("cross_law_discovery")
    if not isinstance(raw_receipt, Mapping):
        _fail("cross-law transformed batch lacks its receipt")
    receipt = dict(raw_receipt)
    retained_hash = receipt.pop("receipt_sha256", None)
    if (
        type(retained_hash) is not str
        or _SHA256.fullmatch(retained_hash) is None
        or retained_hash != canonical_sha256(receipt)
    ):
        _fail("cross-law discovery receipt self-hash differs")
    base_world_receipt = _array_receipt(base_draws)
    seed, seed_receipt = _discovery_seed(
        season=season,
        week=week,
        cbwu_seed_label=cbwu_seed_label,
        base_world_receipt=base_world_receipt,
    )
    discovery = _apply_discovery_overlay(
        base_draws,
        games=games,
        teams=teams,
        positions=positions,
        seed=seed,
    )
    world_order = np.argsort(discovery.sum(axis=0), kind="stable")[::-1]
    base_marginals = _marginal_manifest(base_draws, base_batch.player_ids)
    discovery_marginals = _marginal_manifest(discovery, base_batch.player_ids)
    try:
        ledger = validate_ledger(receipt.get("exposure_ledger"))
    except Exception as exc:
        raise ProspectiveCrossLawDiscoveryError(
            "cross-law shared exposure ledger differs"
        ) from exc
    ledger_rows = ledger["rows"]
    if ledger["attempt_count"] != DISCOVERY_ATTEMPTS:
        _fail("cross-law exposure ledger census differs")
    base_hashes = {_roster_sha256(lineup) for lineup in base_batch.candidates}
    seen_hashes = set(base_hashes)
    new_hashes: list[str] = []
    for attempt, row_value in enumerate(ledger_rows):
        if not isinstance(row_value, Mapping):
            _fail(f"cross-law exposure[{attempt}] is not a mapping")
        row = dict(row_value)
        roster_hash = row.get("roster_sha256")
        expected_status = "dup" if roster_hash in seen_hashes else "new"
        if (
            row.get("family") != FAMILY
            or row.get("source_label") != f"{cbwu_seed_label.lower()}-cross-law"
            or row.get("requested_ordinal") != attempt
            or row.get("retry_ordinal") != 0
            or row.get("world_id") != int(world_order[attempt])
            or type(roster_hash) is not str
            or _SHA256.fullmatch(roster_hash) is None
            or row.get("status") != expected_status
        ):
            _fail(f"cross-law exposure[{attempt}] differs")
        if expected_status == "new":
            new_hashes.append(roster_hash)
            seen_hashes.add(roster_hash)
    added = transformed.candidates[len(base_batch.candidates):]
    if new_hashes != [_roster_sha256(lineup) for lineup in added]:
        _fail("cross-law exposure/new-candidate order differs")
    candidate_trace = _candidate_influence_trace(
        base_candidates=base_batch.candidates,
        ledger=ledger,
    )
    construction_trace = _construction_integrity_trace(
        base_batch,
        transformed.candidates,
        base_candidate_count=len(base_batch.candidates),
        construction=construction,
        stack=stack,
        locks=locks,
    )
    influence_trace = _production_influence_trace(
        base=base_draws,
        discovery=discovery,
        player_ids=base_batch.player_ids,
        games=games,
        teams=teams,
        positions=positions,
        base_marginals=base_marginals,
        discovery_marginals=discovery_marginals,
        seed_receipt=seed_receipt,
        candidate_trace=candidate_trace,
        construction_trace=construction_trace,
    )
    expected_fields = {
        "schema_version": RECEIPT_SCHEMA,
        "version": VERSION,
        "family": FAMILY,
        "season": season,
        "week": week,
        "cbwu_seed_label": cbwu_seed_label,
        "law": dict(LAW),
        "law_sha256": LAW_SHA256,
        "seed_receipt": seed_receipt,
        "base_world_bank_receipt": base_world_receipt,
        "discovery_world_bank_receipt": _array_receipt(discovery),
        "base_marginal_manifest_sha256": canonical_sha256(base_marginals),
        "discovery_marginal_manifest_sha256": canonical_sha256(
            discovery_marginals
        ),
        "all_player_marginals_bitwise_identical": True,
        "dst_row_indices": list(dst_indices),
        "dst_rows_bitwise_untouched": True,
        "same_team_co_boom_trace": _same_team_co_boom_trace(
            base_draws,
            discovery,
            teams=teams,
            positions=positions,
        ),
        "production_influence_trace": influence_trace,
        "production_influence_trace_sha256": influence_trace[
            "influence_trace_sha256"
        ],
        "discovery_world_order_sha256": canonical_sha256(
            [int(value) for value in world_order]
        ),
        "attempted_world_indices": [
            int(value) for value in world_order[:DISCOVERY_ATTEMPTS]
        ],
        "attempt_count": DISCOVERY_ATTEMPTS,
        "milp_attempt_count": DISCOVERY_ATTEMPTS,
        "solver_error_count": 0,
        "infeasible_count": 0,
        "new_candidate_count": len(new_hashes),
        "duplicate_candidate_count": DISCOVERY_ATTEMPTS - len(new_hashes),
        "base_candidate_count": len(base_batch.candidates),
        "transformed_candidate_count": len(transformed.candidates),
        "native_generation_allocation": allocation,
        "construction_binding": construction,
        "exposure_ledger": ledger,
        "exposure_ledger_sha256": ledger["ledger_sha256"],
        "base_candidate_totals_receipt": _array_receipt(
            base_batch.candidate_totals
        ),
        "transformed_candidate_totals_receipt": _array_receipt(expected_totals),
        "all_candidate_selection_scores_from_untouched_base_row_draws": True,
        "discovery_worlds_used_for_selection_scoring": False,
        "deduplicated_against_complete_existing_base_pool": True,
        "uses_realized_outcomes": False,
        "outcome_columns_read": [],
        "cloud_mutation_performed": False,
        "production_policy_changed": False,
        "complete": True,
    }
    if receipt != expected_fields:
        _fail("cross-law discovery receipt fields/content differ")
    return transformed


def rebuild_cross_law_discovery_world_matrix(
    base_batch: CandidateBatch,
    cross_law_receipt: Mapping[str, object],
) -> np.ndarray:
    """Outcome-blindly rebuild and validate the receipt-bound discovery bank.

    This is the persistence seam for the suite.  It performs no I/O: the
    caller owns create-only publication and binds that provider identity into
    the suite terminal receipt.  ``base_batch`` may be the native batch or
    its transformed successor because both retain the untouched base row bank.
    """

    _validate_candidate_batch(base_batch)
    if not isinstance(cross_law_receipt, Mapping):
        _fail("cross-law rebuild receipt differs")
    receipt = dict(cross_law_receipt)
    retained_hash = receipt.pop("receipt_sha256", None)
    if (
        type(retained_hash) is not str
        or _SHA256.fullmatch(retained_hash) is None
        or retained_hash != canonical_sha256(receipt)
        or receipt.get("schema_version") != RECEIPT_SCHEMA
        or receipt.get("version") != VERSION
        or receipt.get("law") != LAW
        or receipt.get("law_sha256") != LAW_SHA256
        or receipt.get("uses_realized_outcomes") is not False
        or receipt.get("outcome_columns_read") != []
    ):
        _fail("cross-law rebuild receipt fixed law differs")
    season = receipt.get("season")
    week = receipt.get("week")
    label = receipt.get("cbwu_seed_label")
    if (
        type(season) is not int
        or type(week) is not int
        or label not in SEED_LABELS
        or base_batch.metadata.get("season") != season
        or base_batch.metadata.get("week") != week
    ):
        _fail("cross-law rebuild slate identity differs")
    games, teams, positions, dst_indices = _validate_player_rows(base_batch)
    base = np.asarray(base_batch.row_draws)
    base_receipt = _array_receipt(base)
    if receipt.get("base_world_bank_receipt") != base_receipt:
        _fail("cross-law rebuild base world identity differs")
    seed, seed_receipt = _discovery_seed(
        season=season,
        week=week,
        cbwu_seed_label=str(label),
        base_world_receipt=base_receipt,
    )
    if receipt.get("seed_receipt") != seed_receipt:
        _fail("cross-law rebuild seed derivation differs")
    discovery = _apply_discovery_overlay(
        base,
        games=games,
        teams=teams,
        positions=positions,
        seed=seed,
    )
    discovery_receipt = _array_receipt(discovery)
    base_marginals = _marginal_manifest(base, base_batch.player_ids)
    discovery_marginals = _marginal_manifest(discovery, base_batch.player_ids)
    order = np.argsort(discovery.sum(axis=0), kind="stable")[::-1]
    if (
        receipt.get("discovery_world_bank_receipt") != discovery_receipt
        or receipt.get("base_marginal_manifest_sha256")
        != canonical_sha256(base_marginals)
        or receipt.get("discovery_marginal_manifest_sha256")
        != canonical_sha256(discovery_marginals)
        or receipt.get("all_player_marginals_bitwise_identical") is not True
        or receipt.get("dst_row_indices") != list(dst_indices)
        or receipt.get("dst_rows_bitwise_untouched") is not True
        or receipt.get("discovery_world_order_sha256")
        != canonical_sha256([int(value) for value in order])
        or receipt.get("attempted_world_indices")
        != [int(value) for value in order[:DISCOVERY_ATTEMPTS]]
    ):
        _fail("cross-law rebuilt discovery world proof differs")
    raw_trace = receipt.get("production_influence_trace")
    if not isinstance(raw_trace, Mapping):
        _fail("cross-law rebuild influence trace differs")
    trace = dict(raw_trace)
    trace_hash = trace.pop("influence_trace_sha256", None)
    if (
        type(trace_hash) is not str
        or trace_hash != canonical_sha256(trace)
        or receipt.get("production_influence_trace_sha256") != trace_hash
        or trace.get("schema_version") != INFLUENCE_TRACE_SCHEMA
        or trace.get("law_sha256") != LAW_SHA256
        or trace.get("seed_derivation_receipt") != seed_receipt
        or trace.get("joint_dependence") != _joint_dependence_trace(
            base,
            discovery,
            games=games,
            teams=teams,
            positions=positions,
        )
        or trace.get("world_rank_correlation")
        != _world_rank_trace(base, discovery)
    ):
        _fail("cross-law rebuilt influence trace proof differs")
    binding = trace.get("world_content_binding")
    marginal = trace.get("per_player_marginal_proof")
    if (
        not isinstance(binding, Mapping)
        or binding.get("base_world_bank_receipt") != base_receipt
        or binding.get("discovery_world_bank_receipt") != discovery_receipt
        or binding.get("selection_scoring_bank") != "base"
        or binding.get("discovery_bank_used_for_selection_scoring") is not False
        or not isinstance(marginal, Mapping)
        or marginal.get("base_manifest_sha256")
        != canonical_sha256(base_marginals)
        or marginal.get("discovery_manifest_sha256")
        != canonical_sha256(discovery_marginals)
        or marginal.get("all_bitwise_multisets_identical") is not True
    ):
        _fail("cross-law rebuilt influence world binding differs")
    rebuilt = np.array(discovery, copy=True, order="C")
    rebuilt.setflags(write=False)
    return rebuilt


__all__ = [
    "BASE_BOOM_ATTEMPTS",
    "BASE_LEVERAGE_ATTEMPTS",
    "BASE_WORLD_COUNT",
    "DISCOVERY_ATTEMPTS",
    "EXPOSURE_SCHEMA",
    "FAMILY",
    "INFLUENCE_TRACE_SCHEMA",
    "LAW",
    "LAW_SHA256",
    "ProspectiveCrossLawDiscoveryError",
    "RECEIPT_SCHEMA",
    "SEED_LABELS",
    "VERSION",
    "build_cross_law_discovery_batch",
    "rebuild_cross_law_discovery_world_matrix",
    "validate_cross_law_discovery_batch",
]
