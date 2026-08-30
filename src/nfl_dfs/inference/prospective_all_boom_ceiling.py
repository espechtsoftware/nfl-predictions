"""Optional, unpassed PREREG-017 ceiling-ordered all-boom shadow.

This module is deliberately isolated from the money path.  It implements the
lab's exact ``world_mode="ceiling"`` quantity -- the sum of the top one QB,
three RBs, four WRs and two TEs in each world -- rather than the different
ATLAS slot-pattern-plus-DST proxy.  The quantity is only a score-blind world
scheduler; every roster is still solved under the incumbent production
construction preset and every candidate is selected on an untouched base-law
world bank with the coverage-194 selector.

The historical PREREG-017 arm did not pass its family-wise primary bound.  All
public receipts therefore retain ``unpassed_optional`` and explicitly deny
adoption and production enablement.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import re
from time import perf_counter
from typing import Final

import numpy as np

from ..backtest.engine import CandidateBatch, _validate_candidate_batch
from ..optimizer.construction_presets import ConstructionPreset
from ..optimizer.lineup import (
    MAX_FROM_TEAM,
    ROSTER_SIZE,
    SALARY_CAP,
    Lineup,
    StackRules,
    optimize,
    select_tail_entries,
)
from .generation_exposure import (
    SolveExposureLedger,
    canonical_sha256,
    validate_ledger,
)
from .production_policy import ADOPTED_CLASSIC_POLICY


VERSION: Final = "prospective-all-boom-ceiling-shadow-v1"
SHADOW_ID: Final = "2026-all-boom-ceiling-unpassed-optional-v1"
EVIDENCE_STATUS: Final = "unpassed_optional"
WORLD_ORDER_ID: Final = "nfl2-prereg017-legal-roster-ceiling-v1"
SELECTION_ID: Final = "base-law-coverage-194-v1"
PRELOCK_SCHEMA: Final = "prospective-all-boom-ceiling-prelock/v1"
TRANSFORM_SCHEMA: Final = "prospective-all-boom-ceiling-transform/v1"
BOOM_ATTEMPTS: Final = 200
LEVERAGE_ATTEMPTS: Final = 0
CORE_ATTEMPTS: Final = 200
ROLE_ATTEMPTS: Final = 12
ENTRIES: Final = 80
TAIL_LINE: Final = 194.0
WORLDS_PER_BANK: Final = 10_000
POSITION_CAPS: Final = (("QB", 1), ("RB", 3), ("WR", 4), ("TE", 2))

_OBJECTIVE_COLUMN = "_all_boom_ceiling_world_points"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_LABEL = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
_AUXILIARY_FAMILIES = frozenset({"epi", "qbvar", "game", "dark"})
_FALSE_DISCLOSURES = frozenset({
    "uses_realized_outcomes",
    "uses_post_lock_outcomes",
    "uses_fantasy_or_lineup_outcomes",
    "post_lock_data_read",
})
_FORBIDDEN_OUTCOME_KEYS = frozenset({
    "actual",
    "actuals",
    "actual_points",
    "actual_score",
    "contest_payout",
    "contest_rank",
    "dk_actual_points",
    "fantasy_points_actual",
    "outcome",
    "outcomes",
    "payout",
    "realized",
    "realized_points",
    "realized_score",
    "settled_points",
    "winnings",
})
_PLAYER_IDENTITY_FIELDS = ("id", "pos", "team", "opp", "game_id", "salary")


class AllBoomCeilingContractError(ValueError):
    """The frozen optional-shadow contract was not satisfied."""

    def __init__(self, message: str, *, exposure_ledger: dict | None = None):
        super().__init__(message)
        self.exposure_ledger = exposure_ledger


WorldSolver = Callable[..., Lineup | None]


def _fail(message: str, *, exposure_ledger: dict | None = None) -> None:
    raise AllBoomCeilingContractError(
        message, exposure_ledger=exposure_ledger,
    )


def _canonical_datetime(value: object, *, label: str) -> datetime:
    if isinstance(value, str):
        raw = value.strip().replace("Z", "+00:00")
        try:
            value = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise AllBoomCeilingContractError(
                f"{label} is not an ISO timestamp"
            ) from exc
    if not isinstance(value, datetime) or value.tzinfo is None or (
        value.utcoffset() is None
    ):
        _fail(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _array_receipt(value: np.ndarray) -> dict[str, object]:
    array = np.ascontiguousarray(value)
    header = json.dumps({
        "dtype": array.dtype.str,
        "shape": list(array.shape),
    }, sort_keys=True, separators=(",", ":")).encode("ascii")
    return {
        "sha256": sha256(header + b"\n" + array.tobytes(order="C")).hexdigest(),
        "dtype": array.dtype.str,
        "shape": list(array.shape),
        "bytes": int(array.nbytes),
    }


def _assert_outcome_free(value: object, *, path: str) -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key).strip().lower()
            child = f"{path}.{key}"
            if key in _FALSE_DISCLOSURES:
                if item is not False:
                    _fail(f"{child} must be false")
                continue
            if (
                key in _FORBIDDEN_OUTCOME_KEYS
                or key.startswith("actual_")
                or key.startswith("realized_")
                or key.startswith("outcome_")
                or key.startswith("post_lock_outcome")
            ):
                _fail(f"{child} is an outcome field")
            _assert_outcome_free(item, path=child)
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, item in enumerate(value):
            _assert_outcome_free(item, path=f"{path}[{index}]")


def _player_identity(batch: CandidateBatch) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for expected_id, raw in zip(
        batch.player_ids, batch.player_rows, strict=True,
    ):
        if not isinstance(raw, Mapping):
            _fail("candidate world bank contains a malformed player row")
        missing = set(_PLAYER_IDENTITY_FIELDS) - set(raw)
        if missing:
            _fail(
                "candidate world bank player identity lacks "
                + ", ".join(sorted(missing))
            )
        if raw["id"] != expected_id:
            _fail("candidate world bank player order differs")
        position = str(raw["pos"]).upper()
        salary = raw["salary"]
        if type(salary) is not int or salary <= 0:
            _fail("candidate world bank salary is not a positive integer")
        rows.append({
            "id": str(expected_id),
            "pos": position,
            "team": str(raw["team"]),
            "opp": str(raw["opp"]),
            "game_id": str(raw["game_id"]),
            "salary": salary,
        })
    return rows


def _validate_world_bank(batch: CandidateBatch, *, label: str) -> dict[str, object]:
    try:
        _validate_candidate_batch(batch)
    except (TypeError, ValueError) as exc:
        raise AllBoomCeilingContractError(
            f"{label} CandidateBatch differs: {exc}"
        ) from exc
    draws = np.asarray(batch.row_draws)
    if draws.shape[1] != WORLDS_PER_BANK:
        _fail(
            f"{label} must contain exactly {WORLDS_PER_BANK} base-law worlds"
        )
    if not np.issubdtype(draws.dtype, np.number) or not np.isfinite(draws).all():
        _fail(f"{label} worlds must be finite numeric values")
    _assert_outcome_free(batch.player_rows, path=f"{label}.player_rows")
    _assert_outcome_free(batch.metadata, path=f"{label}.metadata")
    identity = _player_identity(batch)
    body: dict[str, object] = {
        "law": "production-base-law",
        "worlds": _array_receipt(draws),
        "player_identity_sha256": canonical_sha256(identity),
        "players": len(identity),
        "uses_realized_outcomes": False,
        "uses_post_lock_outcomes": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return body


def lab_legal_roster_ceiling_values(
    row_draws: np.ndarray,
    player_rows: Sequence[Mapping[str, object]],
) -> np.ndarray:
    """Return PREREG-017's exact score-blind scheduling quantity.

    Despite its historical name, this is a positional-cap upper bound, not an
    exact legal MILP optimum.  It intentionally omits DST and simultaneously
    includes the maximum RB, WR and TE counts.  Those details distinguish it
    from the later ATLAS proxy and are frozen here byte-for-byte in meaning.
    """
    draws = np.asarray(row_draws)
    if draws.ndim != 2 or draws.shape[0] != len(player_rows) or (
        draws.shape[1] == 0
    ):
        _fail("legal-roster-ceiling player worlds are misaligned")
    if not np.issubdtype(draws.dtype, np.number) or not np.isfinite(draws).all():
        _fail("legal-roster-ceiling worlds must be finite numeric values")
    positions = np.asarray([
        str(row.get("pos", row.get("position", ""))).upper()
        for row in player_rows
    ], dtype=object)
    bound = np.zeros(draws.shape[1])
    for position, count in POSITION_CAPS:
        subset = draws[positions == position]
        # This mirrors nfl2.pipeline.world_order: sort each position down the
        # player axis, take its legal maximum count, then add the four sums.
        if len(subset):
            bound += np.sort(subset, axis=0)[::-1][:count].sum(axis=0)
    if not np.isfinite(bound).all():  # defensive against exotic numeric dtypes
        _fail("legal-roster-ceiling values are nonfinite")
    return bound


def legal_roster_ceiling_world_order(
    row_draws: np.ndarray,
    player_rows: Sequence[Mapping[str, object]],
) -> np.ndarray:
    """Reproduce the lab's literal ``np.argsort(bound)[::-1]`` order."""
    values = lab_legal_roster_ceiling_values(row_draws, player_rows)
    return np.argsort(values)[::-1].astype(np.int64, copy=False)


def all_boom_ceiling_environment(
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return the isolated production-law environment for this one arm."""
    env = ADOPTED_CLASSIC_POLICY.engine_environment(base)
    env.update({
        "GEN_TOTAL_BUDGET": str(BOOM_ATTEMPTS + ROLE_ATTEMPTS),
        "N_LEV": str(LEVERAGE_ATTEMPTS),
        "N_BOOM": str(BOOM_ATTEMPTS),
        "BOOM_UNIQUE_FILL": "0",
        "PROSPECTIVE_SHADOW_ID": SHADOW_ID,
    })
    return env


def all_boom_noncore_environment(
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the fixed non-core source batch consumed by the arm transform."""
    env = ADOPTED_CLASSIC_POLICY.engine_environment(base)
    env.update({
        "GEN_TOTAL_BUDGET": str(ROLE_ATTEMPTS),
        "N_LEV": "0",
        "N_BOOM": "0",
        "BOOM_UNIQUE_FILL": "0",
        "PROSPECTIVE_SHADOW_ID": (
            "2026-all-boom-ceiling-noncore-source-v1"
        ),
    })
    return env


def validate_all_boom_ceiling_environment(
    env: Mapping[str, str],
) -> dict[str, object]:
    if not isinstance(env, Mapping):
        _fail("all-boom ceiling environment is not a mapping")
    expected = all_boom_ceiling_environment(env)
    observed = {str(key): str(value) for key, value in env.items()}
    if observed != expected:
        differing = sorted({
            *set(observed) ^ set(expected),
            *(key for key in set(observed) & set(expected)
              if observed[key] != expected[key]),
        })
        _fail(
            "all-boom ceiling environment drifts at "
            + ", ".join(differing)
        )
    if observed.get("ATLAS_BOOM_WORLD_RANKING") not in (None, "", "0"):
        _fail("all-boom ceiling arm must not use the ATLAS proxy")
    return {
        "sha256": canonical_sha256(dict(sorted(observed.items()))),
        "values": dict(sorted(observed.items())),
        "core_allocation": {"leverage": 0, "boom": 200, "total": 200},
        "noncore_role_requested": ROLE_ATTEMPTS,
        "evidence_status": EVIDENCE_STATUS,
        "production_enabled": False,
    }


def _expected_preset() -> ConstructionPreset:
    return ADOPTED_CLASSIC_POLICY.construction_preset()


def _validate_construction(
    stack: StackRules,
    locks: set[object] | frozenset[object],
    receipt: Mapping[str, object],
) -> tuple[ConstructionPreset, dict[str, object]]:
    preset = _expected_preset()
    expected = preset.receipt()
    if not isinstance(stack, StackRules) or stack != preset.stack:
        _fail("all-boom ceiling stack differs from the production preset")
    if type(locks) not in {set, frozenset} or locks:
        _fail("all-boom ceiling shadow requires an empty prelock lock set")
    if not isinstance(receipt, Mapping) or dict(receipt) != expected:
        _fail("all-boom ceiling construction preset receipt differs")
    return preset, expected


def _canonical_tags(tags: Sequence[object]) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(tag) for tag in tags))
    if not normalized or any(not tag for tag in normalized):
        _fail("passthrough candidate tags are incomplete")
    return normalized


def _validate_passthrough_batch(
    batch: CandidateBatch,
    *,
    preset_receipt: Mapping[str, object],
) -> dict[str, object]:
    allocation = batch.metadata.get("generation_allocation")
    if not isinstance(allocation, Mapping):
        _fail("non-core source lacks a generation-allocation receipt")
    required = {
        "leverage_requested": 0,
        "boom_requested": 0,
        "core_requested": 0,
        "ce_requested": 0,
        "role_or_epistemic_requested": ROLE_ATTEMPTS,
        "gumbel_requested": 0,
        "total_requested_with_replacement_families": ROLE_ATTEMPTS,
    }
    for key, expected in required.items():
        value = allocation.get(key)
        if type(value) is not int or value != expected:
            _fail(f"non-core source {key} does not prove {expected}")
    for key in (
        "leverage_solve_attempts",
        "leverage_successful",
        "boom_attempted",
        "boom_successful",
        "boom_solver_errors",
        "boom_infeasible",
        "boom_duplicates",
        "boom_failures",
        "boom_unique_added",
    ):
        if key in allocation and allocation[key] != 0:
            _fail(f"non-core source unexpectedly performed {key}")
    if allocation.get("boom_unique_fill", False) is not False:
        _fail("non-core source enabled boom unique-fill")
    if dict(batch.metadata.get("construction_preset_receipt") or {}) != dict(
        preset_receipt
    ):
        _fail("non-core source construction preset receipt differs")
    if not batch.candidates:
        _fail("non-core source produced no fixed production candidates")
    roster_keys = {lineup.ids for lineup in batch.candidates}
    if set(batch.all_tags) != roster_keys:
        _fail("non-core source all-tags census differs")
    family_counts: Counter[str] = Counter()
    for lineup in batch.candidates:
        tags = _canonical_tags(batch.all_tags[lineup.ids])
        primary = {tag.split(":", 1)[0] for tag in tags}
        if primary & {"lev", "boom"}:
            _fail("non-core source contains a core lev/boom candidate")
        allowed = primary & _AUXILIARY_FAMILIES
        if not allowed or str(lineup.tag).split(":", 1)[0] not in (
            _AUXILIARY_FAMILIES
        ):
            _fail("non-core source contains an unrecognized candidate family")
        family_counts.update(allowed)
    body: dict[str, object] = {
        "candidate_count": len(batch.candidates),
        "candidate_order_sha256": canonical_sha256([
            sorted(str(player_id) for player_id in lineup.ids)
            for lineup in batch.candidates
        ]),
        "family_candidate_counts": dict(sorted(family_counts.items())),
        "core_requested": 0,
        "core_candidates_present": False,
        "construction_preset_sha256": preset_receipt["sha256"],
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return body


def _validate_lineup(
    lineup: Lineup,
    *,
    source_by_id: Mapping[object, Mapping[str, object]],
    preset: ConstructionPreset,
) -> Lineup:
    if not isinstance(lineup, Lineup):
        _fail("boom solver did not return a Lineup")
    if len(lineup.players) != ROSTER_SIZE or len(lineup.ids) != ROSTER_SIZE:
        _fail("boom solver returned a non-nine-player roster")
    rebuilt: list[dict] = []
    for player in lineup.players:
        player_id = player.get("id")
        source = source_by_id.get(player_id)
        if source is None:
            _fail("boom solver returned a player outside the source universe")
        if any(player.get(field) != source.get(field) for field in (
            "id", "pos", "team", "opp", "game_id", "salary"
        )):
            _fail("boom solver mutated a player identity or salary")
        rebuilt.append(dict(source))
    canonical = Lineup(rebuilt, tag="boom")
    positions = Counter(str(player["pos"]).upper() for player in rebuilt)
    if (
        positions["QB"] != 1
        or positions["DST"] != 1
        or not 2 <= positions["RB"] <= 3
        or not 3 <= positions["WR"] <= 4
        or not 1 <= positions["TE"] <= 2
        or sum(positions.values()) != ROSTER_SIZE
    ):
        _fail("boom solver roster violates Classic position bounds")
    if not preset.min_salary <= canonical.salary <= SALARY_CAP:
        _fail("boom solver roster violates the production salary bounds")
    teams = Counter(str(player["team"]) for player in rebuilt)
    if max(teams.values()) > MAX_FROM_TEAM:
        _fail("boom solver roster exceeds the production team cap")
    games = {str(player.get("game_id") or "") for player in rebuilt}
    games.discard("")
    if len(games) < preset.min_games:
        _fail("boom solver roster violates the production game minimum")
    qb = next(player for player in rebuilt if str(player["pos"]).upper() == "QB")
    qb_team, qb_opp = str(qb["team"]), str(qb["opp"])
    catchers = sum(
        str(player["team"]) == qb_team
        and str(player["pos"]).upper() in {"WR", "TE"}
        for player in rebuilt
    )
    bring_backs = sum(
        str(player["team"]) == qb_opp
        and str(player["pos"]).upper() in {"RB", "WR", "TE"}
        for player in rebuilt
    )
    if catchers < preset.stack.qb_stack_min:
        _fail("boom solver roster violates the production QB stack")
    if bring_backs < preset.stack.bring_back_min:
        _fail("boom solver roster violates the production bring-back")
    dst = next(player for player in rebuilt if str(player["pos"]).upper() == "DST")
    if preset.stack.forbid_rb_vs_dst and any(
        str(player["pos"]).upper() == "RB"
        and str(player["team"]) == str(dst["opp"])
        for player in rebuilt
    ):
        _fail("boom solver roster contains an RB against its DST")
    if preset.stack.forbid_two_rb_same_team:
        rb_teams = Counter(
            str(player["team"]) for player in rebuilt
            if str(player["pos"]).upper() == "RB"
        )
        if rb_teams and max(rb_teams.values()) > 1:
            _fail("boom solver roster contains two same-team RBs")
    if preset.max_per_game and max(
        Counter(str(player["game_id"]) for player in rebuilt).values()
    ) > preset.max_per_game:
        _fail("boom solver roster violates the production game cap")
    return canonical


def _production_world_solver(
    *,
    player_rows: Sequence[Mapping[str, object]],
    world_scores: np.ndarray,
    world_id: int,
    stack: StackRules,
    locks: frozenset[object],
    env: Mapping[str, str],
    preset: ConstructionPreset,
) -> Lineup | None:
    del world_id  # retained in the injectable solver API and exposure ledger
    pool = [
        {**dict(player), _OBJECTIVE_COLUMN: float(world_scores[index])}
        for index, player in enumerate(player_rows)
    ]
    return optimize(
        pool,
        stack=stack,
        objective_col=_OBJECTIVE_COLUMN,
        locks=set(locks),
        max_overlap=preset.max_overlap,
        punt_max_salary=preset.punt_max_salary,
        punt_min=preset.punt_min,
        min_salary=preset.min_salary,
        max_per_game=preset.max_per_game,
        min_games=preset.min_games,
        env=env,
    )


def build_all_boom_ceiling_batch(
    generation_base: CandidateBatch,
    selection_base: CandidateBatch,
    *,
    stack: StackRules,
    locks: set[object] | frozenset[object],
    env: Mapping[str, str],
    construction_preset_receipt: Mapping[str, object] | None = None,
    source_label: str = "all_boom_ceiling",
    passthrough_candidates: bool = True,
    solve_world: WorldSolver | None = None,
) -> CandidateBatch:
    """Build one native production-shaped PREREG-017 candidate batch.

    ``generation_base`` must be a separately generated, core-zero native
    batch containing only the fixed production role/epistemic, QB-variant,
    game and dark candidates.  They pass through unchanged.  The transform
    then attempts exactly 200 boom solves, dedupes against those candidates,
    and recomputes every candidate total on ``selection_base``.  Thus the
    generation scheduler can change while the selection law remains base.
    """
    if passthrough_candidates is not True:
        _fail("the prospective suite requires passthrough_candidates=True")
    if _SOURCE_LABEL.fullmatch(str(source_label)) is None:
        _fail("all-boom ceiling source label is not normalized")
    generation_receipt = _validate_world_bank(
        generation_base, label="generation base",
    )
    selection_receipt = _validate_world_bank(
        selection_base, label="selection base",
    )
    if generation_base.player_ids != selection_base.player_ids or (
        generation_receipt["player_identity_sha256"]
        != selection_receipt["player_identity_sha256"]
    ):
        _fail("generation and selection base player identities differ")
    environment_receipt = validate_all_boom_ceiling_environment(env)
    raw_preset_receipt = construction_preset_receipt or (
        generation_base.metadata.get("construction_preset_receipt")
    )
    preset, preset_receipt = _validate_construction(
        stack, locks, raw_preset_receipt,
    )
    passthrough_receipt = _validate_passthrough_batch(
        generation_base, preset_receipt=preset_receipt,
    )

    generation_draws = np.asarray(generation_base.row_draws)
    selection_draws = np.asarray(selection_base.row_draws)
    player_rows = tuple(dict(row) for row in generation_base.player_rows)
    source_by_id = {
        player_id: row for player_id, row in zip(
            generation_base.player_ids, player_rows, strict=True,
        )
    }
    ceilings = lab_legal_roster_ceiling_values(
        generation_draws, player_rows,
    )
    world_order = legal_roster_ceiling_world_order(
        generation_draws, player_rows,
    )
    chosen_worlds = world_order[:BOOM_ATTEMPTS]
    if len(chosen_worlds) != BOOM_ATTEMPTS:
        _fail("all-boom ceiling world bank cannot fund 200 attempts")

    candidates = [
        Lineup([dict(source_by_id[player["id"]]) for player in lineup.players],
               tag=lineup.tag)
        for lineup in generation_base.candidates
    ]
    seen: dict[frozenset, int] = {
        lineup.ids: index for index, lineup in enumerate(candidates)
    }
    all_tags = {
        roster: list(_canonical_tags(tags))
        for roster, tags in generation_base.all_tags.items()
    }
    ledger_builder = SolveExposureLedger(
        source_label=str(source_label),
        existing_rosters=(lineup.ids for lineup in candidates),
    )
    solver = solve_world or _production_world_solver
    invalid_error: BaseException | None = None
    for requested_ordinal, raw_world_id in enumerate(chosen_worlds):
        world_id = int(raw_world_id)
        solve_started = perf_counter()
        try:
            solved = solver(
                player_rows=player_rows,
                world_scores=np.asarray(generation_draws[:, world_id]).copy(),
                world_id=world_id,
                stack=stack,
                locks=frozenset(locks),
                env=environment_receipt["values"],
                preset=preset,
            )
        except Exception as exc:  # every requested solve still gets a row
            solve_duration = perf_counter() - solve_started
            ledger_builder.record(
                family="boom",
                requested_ordinal=requested_ordinal,
                world_id=world_id,
                duration_seconds=solve_duration,
                status="error",
            )
            if invalid_error is None:
                invalid_error = exc
            continue
        solve_duration = perf_counter() - solve_started
        if solved is None:
            ledger_builder.record(
                family="boom",
                requested_ordinal=requested_ordinal,
                world_id=world_id,
                duration_seconds=solve_duration,
                status="infeasible",
            )
            continue
        try:
            lineup = _validate_lineup(
                solved, source_by_id=source_by_id, preset=preset,
            )
        except AllBoomCeilingContractError as exc:
            ledger_builder.record(
                family="boom",
                requested_ordinal=requested_ordinal,
                world_id=world_id,
                duration_seconds=solve_duration,
                status="error",
            )
            if invalid_error is None:
                invalid_error = exc
            continue
        status = "dup" if lineup.ids in seen else "new"
        ledger_builder.record(
            family="boom",
            requested_ordinal=requested_ordinal,
            world_id=world_id,
            duration_seconds=solve_duration,
            status=status,
            roster_ids=lineup.ids,
        )
        tags = all_tags.setdefault(lineup.ids, [])
        for tag in ("boom", "shadow:all_boom_ceiling"):
            if tag not in tags:
                tags.append(tag)
        if status == "new":
            seen[lineup.ids] = len(candidates)
            candidates.append(lineup)

    ledger = ledger_builder.finalize(
        expected_requests_by_family={"boom": BOOM_ATTEMPTS},
    )
    status_counts = ledger["status_counts"]
    failures = status_counts["error"] + status_counts["infeasible"] + (
        status_counts["exhausted"]
    )
    if ledger["attempt_count"] != BOOM_ATTEMPTS or failures:
        detail = "all-boom ceiling did not complete 200 successful attempts"
        if invalid_error is not None:
            detail += f": {type(invalid_error).__name__}"
        _fail(detail, exposure_ledger=ledger)
    if status_counts["new"] + status_counts["dup"] != BOOM_ATTEMPTS:
        _fail(
            "all-boom ceiling successful-attempt census differs",
            exposure_ledger=ledger,
        )
    if len(candidates) < ENTRIES:
        _fail("all-boom ceiling pool cannot fill exact-80", exposure_ledger=ledger)

    selection_index = {
        player_id: index for index, player_id in enumerate(selection_base.player_ids)
    }
    candidate_totals = np.stack([
        selection_draws[[selection_index[player_id] for player_id in lineup.ids]].sum(
            axis=0
        )
        for lineup in candidates
    ])
    allocation = {
        "leverage_requested": 0,
        "leverage_unique": 0,
        "leverage_solve_attempts": 0,
        "leverage_solver_errors": 0,
        "leverage_infeasible": 0,
        "leverage_successful": 0,
        "boom_requested": BOOM_ATTEMPTS,
        "boom_attempted": BOOM_ATTEMPTS,
        "boom_successful": BOOM_ATTEMPTS,
        "boom_solver_errors": 0,
        "boom_infeasible": 0,
        "boom_duplicates": int(status_counts["dup"]),
        "boom_failures": 0,
        "boom_unique_added": int(status_counts["new"]),
        "boom_unique_fill": False,
        "ce_requested": 0,
        "role_or_epistemic_requested": ROLE_ATTEMPTS,
        "gumbel_requested": 0,
        "core_requested": CORE_ATTEMPTS,
        "total_requested_with_replacement_families": (
            CORE_ATTEMPTS + ROLE_ATTEMPTS
        ),
        "unique_candidates_after_all_families": len(candidates),
    }
    world_order_receipt: dict[str, object] = {
        "algorithm_id": WORLD_ORDER_ID,
        "lab_contract_exact": True,
        "atlas_proxy_used": False,
        "is_exact_milp_legal_optimum": False,
        "position_caps": {position: count for position, count in POSITION_CAPS},
        "dst_included": False,
        "tie_break": "numpy-argsort-reversed",
        "ordering_expression": "np.argsort(bound)[::-1]",
        "world_count": int(len(world_order)),
        "attempt_world_ids": [int(value) for value in chosen_worlds],
        "ceiling_values_receipt": _array_receipt(ceilings),
        "full_order_sha256": canonical_sha256([
            int(value) for value in world_order
        ]),
    }
    world_order_receipt["receipt_sha256"] = canonical_sha256(
        world_order_receipt
    )
    transform_receipt: dict[str, object] = {
        "schema_version": TRANSFORM_SCHEMA,
        "shadow_version": VERSION,
        "shadow_id": SHADOW_ID,
        "evidence_status": EVIDENCE_STATUS,
        "production_enabled": False,
        "adoption_authorized": False,
        "uses_realized_outcomes": False,
        "uses_post_lock_outcomes": False,
        "uses_fantasy_or_lineup_outcomes": False,
        "post_lock_data_read": False,
        "generation_allocation": allocation,
        "passthrough_receipt": passthrough_receipt,
        "solve_exposure_ledger": ledger,
        "solve_exposure_ledger_sha256": ledger["ledger_sha256"],
        "world_order_receipt": world_order_receipt,
        "generation_world_bank_receipt": generation_receipt,
        "selection_world_bank_receipt": selection_receipt,
        "environment_receipt": environment_receipt,
        "construction_preset_receipt": preset_receipt,
    }
    _assert_outcome_free(
        transform_receipt, path="all_boom_ceiling transform receipt",
    )
    transform_receipt["receipt_sha256"] = canonical_sha256(
        transform_receipt
    )
    metadata = {
        **dict(generation_base.metadata),
        "portfolio": "PROSPECTIVE_ALL_BOOM_CEILING_NATIVE_V1",
        "shadow_version": VERSION,
        "shadow_id": SHADOW_ID,
        "evidence_status": EVIDENCE_STATUS,
        "production_enabled": False,
        "adoption_authorized": False,
        "uses_realized_outcomes": False,
        "uses_post_lock_outcomes": False,
        "uses_fantasy_or_lineup_outcomes": False,
        "post_lock_data_read": False,
        "tail_line": TAIL_LINE,
        "selection_id": SELECTION_ID,
        "selection_law": "untouched-production-base-law",
        "selection_environment": {},
        "generation_allocation": allocation,
        "passthrough_candidates": True,
        "passthrough_receipt": passthrough_receipt,
        "solve_exposure_ledger": ledger,
        "world_order_receipt": world_order_receipt,
        "generation_world_bank_receipt": generation_receipt,
        "selection_world_bank_receipt": selection_receipt,
        "environment_receipt": environment_receipt,
        "construction_preset_receipt": preset_receipt,
        "all_boom_ceiling": transform_receipt,
    }
    result = CandidateBatch(
        candidates=tuple(candidates),
        candidate_totals=np.asarray(candidate_totals),
        player_ids=selection_base.player_ids,
        player_rows=selection_base.player_rows,
        row_draws=selection_base.row_draws,
        all_tags={roster: tuple(tags) for roster, tags in all_tags.items()},
        metadata=metadata,
    )
    validate_all_boom_ceiling_batch(result)
    return result


def validate_all_boom_ceiling_batch(batch: CandidateBatch) -> dict[str, object]:
    receipt = _validate_world_bank(batch, label="all-boom ceiling batch")
    metadata = batch.metadata
    fixed = {
        "shadow_version": VERSION,
        "shadow_id": SHADOW_ID,
        "evidence_status": EVIDENCE_STATUS,
        "production_enabled": False,
        "adoption_authorized": False,
        "uses_realized_outcomes": False,
        "uses_post_lock_outcomes": False,
        "uses_fantasy_or_lineup_outcomes": False,
        "post_lock_data_read": False,
        "tail_line": TAIL_LINE,
        "selection_id": SELECTION_ID,
        "selection_law": "untouched-production-base-law",
        "selection_environment": {},
        "passthrough_candidates": True,
    }
    for key, expected in fixed.items():
        if metadata.get(key) != expected:
            _fail(f"all-boom ceiling batch {key} differs")
    allocation = metadata.get("generation_allocation")
    expected_allocation = {
        "leverage_requested": 0,
        "boom_requested": BOOM_ATTEMPTS,
        "boom_attempted": BOOM_ATTEMPTS,
        "boom_successful": BOOM_ATTEMPTS,
        "boom_solver_errors": 0,
        "boom_infeasible": 0,
        "boom_failures": 0,
        "boom_unique_fill": False,
        "core_requested": CORE_ATTEMPTS,
        "role_or_epistemic_requested": ROLE_ATTEMPTS,
        "total_requested_with_replacement_families": (
            CORE_ATTEMPTS + ROLE_ATTEMPTS
        ),
    }
    if not isinstance(allocation, Mapping) or any(
        allocation.get(key) != value for key, value in expected_allocation.items()
    ):
        _fail("all-boom ceiling batch allocation differs")
    ledger = validate_ledger(metadata.get("solve_exposure_ledger"))
    if (
        ledger["expected_requests_by_family"] != {"boom": BOOM_ATTEMPTS}
        or ledger["attempt_count"] != BOOM_ATTEMPTS
        or ledger["status_counts"]["error"]
        or ledger["status_counts"]["infeasible"]
        or ledger["status_counts"]["exhausted"]
        or ledger["status_counts"]["new"] + ledger["status_counts"]["dup"]
        != BOOM_ATTEMPTS
    ):
        _fail("all-boom ceiling exposure ledger is incomplete")
    order = metadata.get("world_order_receipt")
    if not isinstance(order, Mapping) or (
        order.get("algorithm_id") != WORLD_ORDER_ID
        or order.get("lab_contract_exact") is not True
        or order.get("atlas_proxy_used") is not False
        or order.get("is_exact_milp_legal_optimum") is not False
        or order.get("position_caps") != dict(POSITION_CAPS)
        or order.get("dst_included") is not False
        or order.get("tie_break") != "numpy-argsort-reversed"
        or order.get("ordering_expression") != "np.argsort(bound)[::-1]"
        or len(order.get("attempt_world_ids", ())) != BOOM_ATTEMPTS
    ):
        _fail("all-boom ceiling world-order receipt differs")
    order_body = dict(order)
    retained_order_sha = order_body.pop("receipt_sha256", None)
    if (
        _SHA256.fullmatch(str(retained_order_sha)) is None
        or canonical_sha256(order_body) != retained_order_sha
    ):
        _fail("all-boom ceiling world-order receipt hash differs")
    attempt_worlds = order["attempt_world_ids"]
    if (
        any(type(world) is not int or not 0 <= world < WORLDS_PER_BANK
            for world in attempt_worlds)
        or len(set(attempt_worlds)) != BOOM_ATTEMPTS
        or [row["world_id"] for row in ledger["rows"]] != attempt_worlds
    ):
        _fail("all-boom ceiling attempted-world ledger differs")
    passthrough = metadata.get("passthrough_receipt")
    if not isinstance(passthrough, Mapping):
        _fail("all-boom ceiling passthrough receipt is absent")
    passthrough_body = dict(passthrough)
    retained_passthrough_sha = passthrough_body.pop("receipt_sha256", None)
    if (
        _SHA256.fullmatch(str(retained_passthrough_sha)) is None
        or canonical_sha256(passthrough_body) != retained_passthrough_sha
        or passthrough.get("core_requested") != 0
        or passthrough.get("core_candidates_present") is not False
    ):
        _fail("all-boom ceiling passthrough receipt differs")
    if (
        allocation.get("boom_unique_added") != ledger["status_counts"]["new"]
        or allocation.get("boom_duplicates") != ledger["status_counts"]["dup"]
        or passthrough.get("candidate_count") + ledger["status_counts"]["new"]
        != len(batch.candidates)
        or allocation.get("unique_candidates_after_all_families")
        != len(batch.candidates)
    ):
        _fail("all-boom ceiling candidate/ledger census differs")
    if set(batch.all_tags) != {lineup.ids for lineup in batch.candidates}:
        _fail("all-boom ceiling all-tags census differs")
    for lineup in batch.candidates:
        tags = _canonical_tags(batch.all_tags[lineup.ids])
        if lineup.tag == "boom" and "boom" not in tags:
            _fail("all-boom ceiling generated candidate lacks its boom tag")
    environment = metadata.get("environment_receipt")
    if not isinstance(environment, Mapping) or (
        validate_all_boom_ceiling_environment(
            environment.get("values") if isinstance(
                environment.get("values"), Mapping
            ) else {}
        ) != environment
    ):
        _fail("all-boom ceiling environment receipt differs")
    selection_world_receipt = metadata.get("selection_world_bank_receipt")
    if selection_world_receipt != receipt:
        _fail("all-boom ceiling selection-world receipt differs")
    if metadata.get("construction_preset_receipt") != _expected_preset().receipt():
        _fail("all-boom ceiling batch construction preset differs")
    index = {player_id: row for row, player_id in enumerate(batch.player_ids)}
    rebuilt = np.stack([
        np.asarray(batch.row_draws)[[index[player_id] for player_id in lineup.ids]].sum(
            axis=0
        )
        for lineup in batch.candidates
    ])
    if not np.array_equal(rebuilt, np.asarray(batch.candidate_totals)):
        _fail("all-boom ceiling candidate totals are not from the base law")
    transform = metadata.get("all_boom_ceiling")
    if not isinstance(transform, Mapping):
        _fail("all-boom ceiling unified transform receipt is absent")
    _assert_outcome_free(
        transform, path="all_boom_ceiling unified transform receipt",
    )
    transform_fields = {
        "schema_version",
        "shadow_version",
        "shadow_id",
        "evidence_status",
        "production_enabled",
        "adoption_authorized",
        "uses_realized_outcomes",
        "uses_post_lock_outcomes",
        "uses_fantasy_or_lineup_outcomes",
        "post_lock_data_read",
        "generation_allocation",
        "passthrough_receipt",
        "solve_exposure_ledger",
        "solve_exposure_ledger_sha256",
        "world_order_receipt",
        "generation_world_bank_receipt",
        "selection_world_bank_receipt",
        "environment_receipt",
        "construction_preset_receipt",
        "receipt_sha256",
    }
    if set(transform) != transform_fields:
        _fail("all-boom ceiling unified transform receipt fields differ")
    transform_body = dict(transform)
    retained_transform_sha = transform_body.pop("receipt_sha256")
    if (
        _SHA256.fullmatch(str(retained_transform_sha)) is None
        or canonical_sha256(transform_body) != retained_transform_sha
    ):
        _fail("all-boom ceiling unified transform receipt hash differs")
    transform_fixed = {
        "schema_version": TRANSFORM_SCHEMA,
        "shadow_version": VERSION,
        "shadow_id": SHADOW_ID,
        "evidence_status": EVIDENCE_STATUS,
        "production_enabled": False,
        "adoption_authorized": False,
        "uses_realized_outcomes": False,
        "uses_post_lock_outcomes": False,
        "uses_fantasy_or_lineup_outcomes": False,
        "post_lock_data_read": False,
    }
    if any(transform.get(key) != value for key, value in transform_fixed.items()):
        _fail("all-boom ceiling unified transform fixed law differs")
    bound_components = {
        "generation_allocation": "generation_allocation",
        "passthrough_receipt": "passthrough_receipt",
        "solve_exposure_ledger": "solve_exposure_ledger",
        "world_order_receipt": "world_order_receipt",
        "generation_world_bank_receipt": "generation_world_bank_receipt",
        "selection_world_bank_receipt": "selection_world_bank_receipt",
        "environment_receipt": "environment_receipt",
        "construction_preset_receipt": "construction_preset_receipt",
    }
    if any(
        transform.get(transform_key) != metadata.get(metadata_key)
        for transform_key, metadata_key in bound_components.items()
    ) or transform.get("solve_exposure_ledger_sha256") != ledger["ledger_sha256"]:
        _fail("all-boom ceiling unified transform binding differs")
    candidate_order = [
        sorted(str(player_id) for player_id in lineup.ids)
        for lineup in batch.candidates
    ]
    return {
        "candidate_count": len(batch.candidates),
        "candidate_order_sha256": canonical_sha256(candidate_order),
        "candidate_totals_receipt": _array_receipt(batch.candidate_totals),
        "selection_world_bank_receipt": receipt,
        "exposure_ledger_sha256": ledger["ledger_sha256"],
        "transform_receipt_sha256": retained_transform_sha,
        "evidence_status": EVIDENCE_STATUS,
        "production_enabled": False,
        "uses_realized_outcomes": False,
    }


def select_all_boom_ceiling_book(
    batch: CandidateBatch,
) -> tuple[list[Lineup], dict[str, object]]:
    """Run only the frozen base-law exact-80 coverage-194 selector."""
    batch_receipt = validate_all_boom_ceiling_batch(batch)
    if len(batch.candidates) < ENTRIES:
        _fail("all-boom ceiling candidate pool is below exact-80")
    picked = list(select_tail_entries(
        np.asarray(batch.candidate_totals), ENTRIES, TAIL_LINE, env={},
    ))
    if len(picked) != ENTRIES or len(set(picked)) != ENTRIES or any(
        type(index) is not int or not 0 <= index < len(batch.candidates)
        for index in picked
    ):
        _fail("all-boom ceiling selector did not return exact-80")
    lineups = [batch.candidates[index] for index in picked]
    rosters = [
        sorted(str(player_id) for player_id in lineup.ids)
        for lineup in lineups
    ]
    receipt = {
        "selection_id": SELECTION_ID,
        "law": "untouched-production-base-law",
        "selector": "greedy-binary-tail-coverage",
        "selector_environment": {},
        "tail_line": TAIL_LINE,
        "entries": ENTRIES,
        "selected_candidate_indices": picked,
        "selected_rosters_sha256": canonical_sha256(rosters),
        "candidate_order_sha256": batch_receipt["candidate_order_sha256"],
        "candidate_totals_receipt": batch_receipt[
            "candidate_totals_receipt"
        ],
        "uses_realized_outcomes": False,
        "uses_post_lock_outcomes": False,
        "production_enabled": False,
        "evidence_status": EVIDENCE_STATUS,
    }
    receipt["selection_receipt_sha256"] = canonical_sha256(receipt)
    return lineups, receipt


def _create_only_identity(value: object, *, label: str) -> dict[str, object]:
    required = {
        "uri", "generation", "sha256", "bytes", "create_only", "created_at",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        _fail(f"{label} create-only identity fields differ")
    uri = str(value["uri"])
    digest = str(value["sha256"])
    generation = value["generation"]
    size = value["bytes"]
    if not uri.startswith("gs://") or uri.count("/") < 3:
        _fail(f"{label} URI is not a complete gs:// identity")
    if type(generation) not in {int, str} or not str(generation).isdigit() or (
        int(generation) <= 0
    ):
        _fail(f"{label} generation is invalid")
    if _SHA256.fullmatch(digest) is None:
        _fail(f"{label} SHA-256 is invalid")
    if type(size) is not int or size <= 0:
        _fail(f"{label} byte count is invalid")
    if value["create_only"] is not True:
        _fail(f"{label} was not created with a create-only precondition")
    created = _canonical_datetime(value["created_at"], label=f"{label} created_at")
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": digest,
        "bytes": size,
        "create_only": True,
        "created_at": created.isoformat(),
    }


def _validate_selection_receipt(
    value: object,
    *,
    batch: CandidateBatch | None = None,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("all-boom ceiling selection receipt is not a mapping")
    item = dict(value)
    retained = item.pop("selection_receipt_sha256", None)
    if _SHA256.fullmatch(str(retained)) is None or canonical_sha256(item) != retained:
        _fail("all-boom ceiling selection receipt hash differs")
    fixed = {
        "selection_id": SELECTION_ID,
        "law": "untouched-production-base-law",
        "selector": "greedy-binary-tail-coverage",
        "selector_environment": {},
        "tail_line": TAIL_LINE,
        "entries": ENTRIES,
        "uses_realized_outcomes": False,
        "uses_post_lock_outcomes": False,
        "production_enabled": False,
        "evidence_status": EVIDENCE_STATUS,
    }
    if any(item.get(key) != expected for key, expected in fixed.items()):
        _fail("all-boom ceiling selection receipt fixed law differs")
    picked = item.get("selected_candidate_indices")
    if not isinstance(picked, list) or len(picked) != ENTRIES or (
        any(type(index) is not int for index in picked)
    ) or len(set(picked)) != ENTRIES:
        _fail("all-boom ceiling selection receipt is not exact-80")
    if batch is not None:
        replay_lineups, replay = select_all_boom_ceiling_book(batch)
        del replay_lineups
        if replay != {**item, "selection_receipt_sha256": retained}:
            _fail("all-boom ceiling selection receipt does not replay")
    return {**item, "selection_receipt_sha256": retained}


def build_prelock_receipt(
    batch: CandidateBatch,
    selection_receipt: Mapping[str, object],
    *,
    generated_at: datetime,
    lock_at: datetime,
    generation_world_object: Mapping[str, object],
    selection_world_object: Mapping[str, object],
    candidate_object: Mapping[str, object],
) -> dict[str, object]:
    """Build the body that must itself be persisted create-only before lock."""
    batch_receipt = validate_all_boom_ceiling_batch(batch)
    selected = _validate_selection_receipt(selection_receipt, batch=batch)
    generated = _canonical_datetime(generated_at, label="receipt generated_at")
    lock = _canonical_datetime(lock_at, label="slate lock_at")
    if generated >= lock:
        _fail("all-boom ceiling receipt was not generated before lock")
    objects = {
        "generation_world_bank": _create_only_identity(
            generation_world_object, label="generation world bank",
        ),
        "selection_world_bank": _create_only_identity(
            selection_world_object, label="selection world bank",
        ),
        "candidate_batch": _create_only_identity(
            candidate_object, label="candidate batch",
        ),
    }
    if any(
        _canonical_datetime(item["created_at"], label=f"{name} created_at")
        > generated
        for name, item in objects.items()
    ):
        _fail("all-boom ceiling object was created after its receipt")
    if any(
        _canonical_datetime(item["created_at"], label=f"{name} created_at")
        >= lock
        for name, item in objects.items()
    ):
        _fail("all-boom ceiling object was not frozen before lock")
    ledger = validate_ledger(batch.metadata["solve_exposure_ledger"])
    body: dict[str, object] = {
        "schema_version": PRELOCK_SCHEMA,
        "complete": True,
        "shadow_version": VERSION,
        "shadow_id": SHADOW_ID,
        "evidence_status": EVIDENCE_STATUS,
        "generated_at": generated.isoformat(),
        "lock_at": lock.isoformat(),
        "strictly_prelock": True,
        "objects": objects,
        "batch_receipt": batch_receipt,
        "selection_receipt": selected,
        "solve_exposure_ledger": ledger,
        "persistence_contract": {
            "if_generation_match": 0,
            "create_only": True,
            "receipt_must_be_persisted_before_lock": True,
        },
        "uses_realized_outcomes": False,
        "uses_post_lock_outcomes": False,
        "uses_fantasy_or_lineup_outcomes": False,
        "post_lock_data_read": False,
        "production_enabled": False,
        "adoption_authorized": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return validate_prelock_receipt(body)


def validate_prelock_receipt(value: object) -> dict[str, object]:
    fields = {
        "schema_version", "complete", "shadow_version", "shadow_id",
        "evidence_status", "generated_at", "lock_at", "strictly_prelock",
        "objects", "batch_receipt", "selection_receipt",
        "solve_exposure_ledger", "persistence_contract",
        "uses_realized_outcomes", "uses_post_lock_outcomes",
        "uses_fantasy_or_lineup_outcomes", "post_lock_data_read",
        "production_enabled", "adoption_authorized", "receipt_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("all-boom ceiling prelock receipt fields differ")
    item = dict(value)
    retained = item.pop("receipt_sha256")
    if _SHA256.fullmatch(str(retained)) is None or canonical_sha256(item) != retained:
        _fail("all-boom ceiling prelock receipt hash differs")
    fixed = {
        "schema_version": PRELOCK_SCHEMA,
        "complete": True,
        "shadow_version": VERSION,
        "shadow_id": SHADOW_ID,
        "evidence_status": EVIDENCE_STATUS,
        "strictly_prelock": True,
        "uses_realized_outcomes": False,
        "uses_post_lock_outcomes": False,
        "uses_fantasy_or_lineup_outcomes": False,
        "post_lock_data_read": False,
        "production_enabled": False,
        "adoption_authorized": False,
        "persistence_contract": {
            "if_generation_match": 0,
            "create_only": True,
            "receipt_must_be_persisted_before_lock": True,
        },
    }
    if any(item.get(key) != expected for key, expected in fixed.items()):
        _fail("all-boom ceiling prelock receipt fixed law differs")
    generated = _canonical_datetime(item["generated_at"], label="generated_at")
    lock = _canonical_datetime(item["lock_at"], label="lock_at")
    if generated >= lock:
        _fail("all-boom ceiling prelock receipt crosses lock")
    objects = item.get("objects")
    if not isinstance(objects, Mapping) or set(objects) != {
        "generation_world_bank", "selection_world_bank", "candidate_batch",
    }:
        _fail("all-boom ceiling prelock object census differs")
    normalized_objects = {
        name: _create_only_identity(identity, label=name)
        for name, identity in objects.items()
    }
    if normalized_objects != objects or any(
        _canonical_datetime(identity["created_at"], label=f"{name} created_at")
        >= lock
        for name, identity in normalized_objects.items()
    ):
        _fail("all-boom ceiling prelock object identity differs")
    validate_ledger(item["solve_exposure_ledger"])
    _validate_selection_receipt(item["selection_receipt"])
    _assert_outcome_free(item, path="prelock_receipt")
    return {**item, "receipt_sha256": retained}


__all__ = [
    "AllBoomCeilingContractError",
    "BOOM_ATTEMPTS",
    "CORE_ATTEMPTS",
    "ENTRIES",
    "EVIDENCE_STATUS",
    "LEVERAGE_ATTEMPTS",
    "POSITION_CAPS",
    "PRELOCK_SCHEMA",
    "SELECTION_ID",
    "SHADOW_ID",
    "TAIL_LINE",
    "TRANSFORM_SCHEMA",
    "VERSION",
    "WORLD_ORDER_ID",
    "WORLDS_PER_BANK",
    "all_boom_ceiling_environment",
    "all_boom_noncore_environment",
    "build_all_boom_ceiling_batch",
    "build_prelock_receipt",
    "lab_legal_roster_ceiling_values",
    "legal_roster_ceiling_world_order",
    "select_all_boom_ceiling_book",
    "validate_all_boom_ceiling_batch",
    "validate_all_boom_ceiling_environment",
    "validate_prelock_receipt",
]
