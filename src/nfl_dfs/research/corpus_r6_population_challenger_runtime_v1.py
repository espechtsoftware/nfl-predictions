"""Executable shared-bank runtime for the F7/F8/F9 challenger.

One prepared slate and one canonical R0--R4 visit schedule are reused across
all three profiles.  Models remain fresh per cell.  The production entrypoint
hard-codes the retained exact CBC solver and validates its canonical proof;
the separately named test seam permits a bounded injected solver but marks
all returned objects non-authoritative.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
from typing import Final

from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_authority_v1 as authority,
)
from nfl_dfs.research import corpus_r6_population_profiles_v1 as profiles
from nfl_dfs.research import lr8_later_period_source as later
from nfl_dfs.research import residual_world_columns as rw


LINEUP_ID_SCHEMA: Final = "corpus-r6-population-challenger-lineup-identity/v1"
VISIT_RESULT_SCHEMA: Final = "corpus-r6-population-challenger-visit-result/v1"
SOURCE_AUTHORITY_SCHEMA: Final = "corpus-r6-population-challenger-source/v1"
TASK_COMPLETION_SCHEMA: Final = (
    "corpus-r6-population-challenger-task-completion/v1"
)

SolverCallback = Callable[[legal.SolveRequest], legal.SolveOutcome]


class CorpusR6PopulationChallengerRuntimeV1Error(ValueError):
    """The shared population challenger runtime failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6PopulationChallengerRuntimeV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return authority.object_identity_v1(value, label=label)
    except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationChallengerRuntimeV1Error(str(exc)) from exc


def _hash(value: object) -> str:
    return authority.canonical_sha256_v1(value)


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} is already present")
    return {**body, field: _hash(body)}


def _exact_read_bytes_v1(
    identity_value: object,
    *,
    read_exact: authority.ReadExact,
    label: str,
    maximum_bytes: int,
) -> tuple[bytes, dict[str, object]]:
    identity = _identity(identity_value, label=label)
    if identity["bytes"] > maximum_bytes:
        _fail(f"{label} exceeds its exact byte ceiling")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} generation-exact bytes differ")
    return raw, identity


def _projection_source_authority_v1(
    projection_value: object,
    *,
    projection_identity: Mapping[str, object],
    expected_source_ordinal: int,
) -> dict[str, object]:
    try:
        projection = contract.validate_projection_bundle_v1(projection_value)
    except Exception as exc:
        raise CorpusR6PopulationChallengerRuntimeV1Error(
            f"projection bundle is invalid: {exc}"
        ) from exc
    if (
        projection.get("source_ordinal") != expected_source_ordinal
        or _mapping(projection.get("policy"), label="projection policy")
        != contract.POLICY_CLAIMS
    ):
        _fail("projection ordinal/outcome-blind policy differs")
    folds = _sequence(projection.get("fold_projections"), label="fold projections")
    if len(folds) != len(rw.WORLD_BLOCKS):
        _fail("projection fold count differs")
    later_identities: list[dict[str, object]] = []
    world_sets: list[dict[str, object]] = []
    task_result_identities: list[dict[str, object]] = []
    for expected_block, raw in zip(rw.WORLD_BLOCKS, folds, strict=True):
        fold = _mapping(raw, label=f"projection fold {expected_block}")
        if fold.get("heldout_block") != expected_block:
            _fail("projection fold order differs")
        later_identities.append(_identity(
            fold.get("later_source_identity"), label="later source"
        ))
        worlds = _mapping(
            fold.get("world_artifact_identities"), label="world artifacts"
        )
        expected_keys = [
            f"world_artifact_{block.casefold()}" for block in rw.WORLD_BLOCKS
        ]
        if list(worlds) != expected_keys:
            _fail("world artifact key order differs")
        world_sets.append({
            key: _identity(identity, label=key) for key, identity in worlds.items()
        })
        task_result_identities.append(_identity(
            fold.get("source_task_result_identity"),
            label="source bank task result",
        ))
    if (
        len({_hash(row) for row in later_identities}) != 1
        or len({_hash(row) for row in world_sets}) != 1
        or len({_hash(row) for row in task_result_identities}) != 1
    ):
        _fail("projection folds do not bind one shared source/world set")
    body = {
        "schema": SOURCE_AUTHORITY_SCHEMA,
        "source_ordinal": expected_source_ordinal,
        "slate_id": projection["slate_id"],
        "projection_bundle_identity": dict(projection_identity),
        "projection_bundle_sha256": projection["projection_bundle_sha256"],
        "later_source_identity": later_identities[0],
        "world_artifact_identities": world_sets[0],
        "world_artifact_identities_sha256": _hash(world_sets[0]),
        "source_bank_task_result_identity": task_result_identities[0],
        "fold_projection_sha256s": projection["fold_projection_sha256s"],
        "outcome_fields_read": [],
        "uses_realized_outcomes": False,
    }
    return {**body, "source_authority_sha256": _hash(body)}


def _prepared_slate_v1(
    source: Mapping[str, object], *, read_exact: authority.ReadExact
) -> later.PreparedLaterSlate:
    later_body, later_identity = authority.exact_read_json_v1(
        source["later_source_identity"],
        read_exact=read_exact,
        label="later source freeze",
        maximum_bytes=authority.MAXIMUM_LATER_SOURCE_BYTES,
    )
    internal_freeze_sha = later_body.get("freeze_sha256")
    if type(internal_freeze_sha) is not str:
        _fail("later source internal freeze hash is absent")
    try:
        frozen = later.validate_source_freeze(
            later_body, expected_freeze_sha256=internal_freeze_sha
        )
    except Exception as exc:
        raise CorpusR6PopulationChallengerRuntimeV1Error(
            f"later source freeze is invalid: {exc}"
        ) from exc
    slate_id = source["slate_id"]
    matches = [row for row in frozen["slates"] if row.get("slate_id") == slate_id]
    if len(matches) != 1:
        _fail("later source does not contain exactly one requested slate")
    slate = matches[0]
    expected_worlds = _mapping(
        source["world_artifact_identities"], label="source world identities"
    )
    receipts = _sequence(slate.get("artifact_receipts"), label="artifact receipts")
    if len(receipts) != len(rw.WORLD_BLOCKS):
        _fail("later source artifact receipt count differs")
    bodies: dict[str, bytes] = {}
    for block, receipt_raw in zip(rw.WORLD_BLOCKS, receipts, strict=True):
        receipt = _mapping(receipt_raw, label=f"later source {block} receipt")
        if receipt.get("block") != block:
            _fail("later source artifact block order differs")
        expected_identity = _identity(
            expected_worlds[f"world_artifact_{block.casefold()}"],
            label=f"expected {block} artifact",
        )
        observed_identity = _identity({
            key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")
        }, label=f"later source {block} artifact")
        if observed_identity != expected_identity:
            _fail("projection/later-source world artifact identity differs")
        body, _ = _exact_read_bytes_v1(
            expected_identity,
            read_exact=read_exact,
            label=f"world artifact {block}",
            maximum_bytes=authority.MAXIMUM_WORLD_ARTIFACT_BYTES,
        )
        bodies[block] = body
    try:
        prepared = later.prepare_later_slate(
            frozen,
            expected_source_freeze_sha256=internal_freeze_sha,
            season=int(slate["season"]),
            week=int(slate["week"]),
            artifact_bodies=bodies,
        )
    except Exception as exc:
        raise CorpusR6PopulationChallengerRuntimeV1Error(
            f"shared five-block slate preparation failed: {exc}"
        ) from exc
    if prepared.slate_id != slate_id:
        _fail("prepared slate identity differs")
    return prepared


def _schedule_and_objectives_v1(
    prepared: later.PreparedLaterSlate,
    work: profiles.SharedSolverWork,
) -> tuple[tuple[rw.WorldId, ...], tuple[tuple[int, ...], ...], str]:
    try:
        schedule = legal.canonical_visit_schedule(
            prepared, visits_per_block=work.solve_attempts_per_block
        )
    except Exception as exc:
        raise CorpusR6PopulationChallengerRuntimeV1Error(
            f"canonical shared visit schedule failed: {exc}"
        ) from exc
    schedule_rows = [
        {"block": world.block, "index": world.index} for world in schedule
    ]
    schedule_sha = _hash(schedule_rows)
    expected_counts = Counter(world.block for world in schedule)
    if (
        tuple(dict.fromkeys(world.block for world in schedule))
        != work.world_blocks
        or expected_counts
        != Counter({
            block: work.solve_attempts_per_block for block in work.world_blocks
        })
        or len(schedule) != work.solves_per_profile_per_slate
    ):
        _fail("canonical schedule does not equal the registered work dose")
    objectives: list[tuple[int, ...]] = []
    for world in schedule:
        column = rw.WORLD_BLOCKS.index(world.block) * rw.WORLDS_PER_BLOCK + world.index
        if prepared.world_ids[column] != world:
            _fail("schedule/source world identity differs")
        try:
            objectives.append(legal._micro_objective(
                prepared.player_draws, world_column=column
            ))
        except Exception as exc:
            raise CorpusR6PopulationChallengerRuntimeV1Error(
                f"world objective construction failed: {exc}"
            ) from exc
    return schedule, tuple(objectives), schedule_sha


def _lineup_identity_v1(
    *,
    slate_id: str,
    profile_id: str,
    profile_sha256: str,
    roster: tuple[str, ...],
) -> dict[str, object]:
    return _with_hash({
        "schema": LINEUP_ID_SCHEMA,
        "slate_id": slate_id,
        "profile_id": profile_id,
        "profile_sha256": profile_sha256,
        "roster": list(roster),
    }, field="lineup_sha256")


def _normalize_profile_outcome_v1(
    value: object,
    *,
    request: legal.SolveRequest,
    profile_id: str,
) -> legal.SolveOutcome:
    """Reconstruct an outcome without the incumbent QB+2 house-rule audit.

    ``corpus_legal_feasibility._normalize_solver_outcome`` delegates profile
    compliance to ``house_rule_violations``.  That helper defines a violation
    relative to the incumbent QB+2/bring-back-one baseline and then considers
    any nonzero requested minimum "active"; consequently F9's exact QB+1 is
    rejected as though it still requested QB+2.  This adapter retains the
    original DK, objective, rank, radix, and combined-optimum reconstruction
    but delegates strategic compliance to the complete named profile audit.
    """
    if not isinstance(value, legal.SolveOutcome) or not isinstance(
        value.status, legal.SolverStatus
    ):
        return legal.SolveOutcome(
            legal.SolverStatus.ERROR,
            detail="solver callback result type/status differs",
        )
    if type(value.detail) is not str:
        return legal.SolveOutcome(
            legal.SolverStatus.ERROR, detail="solver detail type differs"
        )
    if value.status is not legal.SolverStatus.OPTIMAL:
        if value.roster is not None:
            return legal.SolveOutcome(
                legal.SolverStatus.ERROR,
                detail="non-optimal solver status carried a roster",
            )
        return value
    if (
        value.roster is None
        or type(value.primary_optimum_micro) is not int
        or type(value.secondary_rank_sum) is not int
        or type(value.lexicographic_radix) is not int
        or type(value.combined_optimum) is not int
    ):
        return legal.SolveOutcome(
            legal.SolverStatus.ERROR,
            detail="optimal solver evidence is incomplete",
        )
    try:
        identity = legal.audit_dk_classic(request.model.players, value.roster)
        profiles.audit_profile_roster_v1(
            request.model.players, identity, profile_id
        )
    except Exception as exc:
        return legal.SolveOutcome(
            legal.SolverStatus.ERROR, detail=f"profile audit failed: {exc}"
        )
    player_index = {
        player.player_id: index
        for index, player in enumerate(request.model.players)
    }
    achieved = sum(
        request.objective_micro[player_index[player_id]]
        for player_id in identity
    )
    rank_by_id = {
        player_id: rank + 1
        for rank, player_id in enumerate(sorted(player_index))
    }
    rank_sum = sum(rank_by_id[player_id] for player_id in identity)
    radix = rw.ROSTER_SIZE * (len(request.model.players) - rw.ROSTER_SIZE) + 1
    if (
        achieved != value.primary_optimum_micro
        or rank_sum != value.secondary_rank_sum
        or value.lexicographic_radix != radix
        or value.combined_optimum != achieved * radix - rank_sum
    ):
        return legal.SolveOutcome(
            legal.SolverStatus.ERROR,
            detail="solver objective/rank evidence does not reconstruct",
        )
    return legal.SolveOutcome(
        legal.SolverStatus.OPTIMAL,
        roster=identity,
        primary_optimum_micro=achieved,
        secondary_rank_sum=rank_sum,
        lexicographic_radix=radix,
        combined_optimum=achieved * radix - rank_sum,
        solver_proof=value.solver_proof,
        detail=value.detail,
    )


def _execute_equal_work_v1(
    *,
    prepared: later.PreparedLaterSlate,
    schedule: tuple[rw.WorldId, ...],
    objectives: tuple[tuple[int, ...], ...],
    schedule_sha256: str,
    source_authority: Mapping[str, object],
    work: profiles.SharedSolverWork,
    solver: SolverCallback,
    authoritative: bool,
    solver_authority: Mapping[str, object] | None,
) -> dict[str, dict[str, object]]:
    if (
        len(schedule) != work.solves_per_profile_per_slate
        or len(objectives) != len(schedule)
        or not callable(solver)
    ):
        _fail("equal-work execution inputs differ")
    source = _mapping(source_authority, label="source authority")
    source_sha = source.get("source_authority_sha256")
    if source_sha != _hash({
        key: item for key, item in source.items()
        if key != "source_authority_sha256"
    }):
        _fail("source authority self-hash differs")
    if authoritative:
        if solver is not legal.default_cbc_solver or solver_authority is None:
            _fail("authoritative execution requires the hard-coded CBC callback")
        solver_sha = legal.canonical_sha256(dict(solver_authority))
    else:
        solver_sha = None
    registry = profiles.population_profile_registry_v1()
    work_payload = work.payload()
    work_sha = _hash(work_payload)
    schedule_rows = [
        {"block": world.block, "index": world.index} for world in schedule
    ]
    if _hash(schedule_rows) != schedule_sha256:
        _fail("shared visit schedule hash differs")
    results: dict[str, dict[str, object]] = {}
    for profile_index, profile in enumerate(profiles.population_profiles_v1()):
        visit_rows: list[dict[str, object]] = []
        rosters: list[tuple[str, ...]] = []
        for visit_ordinal, (world, objective) in enumerate(
            zip(schedule, objectives, strict=True)
        ):
            construction_serial = profile_index * len(schedule) + visit_ordinal
            try:
                model = profiles.build_profile_model_v1(
                    prepared.players,
                    profile.profile_id,
                    objective,
                    construction_serial=construction_serial,
                    model_name=(
                        f"population_challenger_f{profile.ordinal:02d}_"
                        f"visit_{visit_ordinal:04d}"
                    ),
                    inherited_surface=profiles.InheritedConstraintSurface(),
                )
                request = legal.SolveRequest(
                    variant_ordinal=profile.ordinal,
                    parameter_set_id=profile.profile_id,
                    visit_ordinal=visit_ordinal,
                    world=world,
                    objective_micro=objective,
                    timeout_seconds=work.solver_timeout_seconds,
                    model=model,
                )
                raw_outcome = solver(request)
                outcome = _normalize_profile_outcome_v1(
                    raw_outcome,
                    request=request,
                    profile_id=profile.profile_id,
                )
                if authoritative:
                    legal._validate_authoritative_solver_proof(
                        outcome, solver_authority_sha256=str(solver_sha)
                    )
            except Exception as exc:
                raise CorpusR6PopulationChallengerRuntimeV1Error(
                    f"{profile.profile_id} visit {visit_ordinal} failed: {exc}"
                ) from exc
            if outcome.status is not legal.SolverStatus.OPTIMAL or outcome.roster is None:
                _fail(
                    f"{profile.profile_id} visit {visit_ordinal} did not finish optimal"
                )
            try:
                shape = profiles.audit_profile_roster_v1(
                    prepared.players, outcome.roster, profile.profile_id
                )
            except Exception as exc:
                raise CorpusR6PopulationChallengerRuntimeV1Error(
                    f"{profile.profile_id} visit {visit_ordinal} profile audit failed: {exc}"
                ) from exc
            roster = tuple(shape["roster"])
            rosters.append(roster)
            proof_payload: dict[str, object] | None = None
            proof_sha: str | None = None
            if authoritative:
                assert outcome.solver_proof is not None
                proof_payload = authority.strict_json_bytes_v1(
                    outcome.solver_proof.canonical_payload,
                    label="solver proof",
                )
                proof_sha = outcome.solver_proof.proof_sha256
            lineup_identity = _lineup_identity_v1(
                slate_id=prepared.slate_id,
                profile_id=profile.profile_id,
                profile_sha256=profile.fingerprint,
                roster=roster,
            )
            visit_rows.append(_with_hash({
                "schema": VISIT_RESULT_SCHEMA,
                "visit_ordinal": visit_ordinal,
                "world": {"block": world.block, "index": world.index},
                "construction_serial": construction_serial,
                "objective_micro_sha256": _hash(list(objective)),
                "lineup_identity": lineup_identity,
                "profile_shape": {
                    key: shape[key] for key in (
                        "salary", "qb_partner_count", "bring_back_count",
                        "opposing_wr_count", "max_from_game", "rb_vs_dst_count",
                        "same_team_rb_pair_count",
                    )
                },
                "primary_optimum_micro": outcome.primary_optimum_micro,
                "secondary_rank_sum": outcome.secondary_rank_sum,
                "lexicographic_radix": outcome.lexicographic_radix,
                "combined_optimum": outcome.combined_optimum,
                "solver_proof_sha256": proof_sha,
                "solver_proof": proof_payload,
            }, field="visit_result_sha256"))
        if len(visit_rows) != work.solves_per_profile_per_slate:
            _fail("profile visit count differs from equal work")
        occurrence_count = Counter(rosters)
        first_visit: dict[tuple[str, ...], int] = {}
        for visit_ordinal, roster in enumerate(rosters):
            first_visit.setdefault(roster, visit_ordinal)
        unique_rows = []
        for roster, first_ordinal in sorted(
            first_visit.items(), key=lambda item: item[1]
        ):
            identity = _lineup_identity_v1(
                slate_id=prepared.slate_id,
                profile_id=profile.profile_id,
                profile_sha256=profile.fingerprint,
                roster=roster,
            )
            unique_rows.append({
                "first_visit_ordinal": first_ordinal,
                "occurrence_count": occurrence_count[roster],
                "lineup_identity": identity,
            })
        body = _with_hash({
            "schema": authority.PROFILE_LINEUPS_SCHEMA,
            "slate": {
                "season": prepared.season,
                "week": prepared.week,
                "slate_id": prepared.slate_id,
            },
            "source_authority": source,
            "source_authority_sha256": source_sha,
            "profile": profile.payload(),
            "profile_sha256": profile.fingerprint,
            "profile_registry_sha256": registry["registry_sha256"],
            "work": work_payload,
            "work_sha256": work_sha,
            "world_schedule": schedule_rows,
            "world_schedule_sha256": schedule_sha256,
            "attempt_count": len(visit_rows),
            "all_attempts_optimal": True,
            "visit_results": visit_rows,
            "visit_results_sha256": _hash(visit_rows),
            "unique_lineup_count": len(unique_rows),
            "unique_lineups": unique_rows,
            "unique_lineups_sha256": _hash(unique_rows),
            "solver_authority": (
                None if solver_authority is None else dict(solver_authority)
            ),
            "solver_authority_sha256": solver_sha,
            "authoritative_solver_proofs_complete": authoritative,
            "raw_solver_log_and_solution_bodies_persisted": False,
            "outcome_fields_read": [],
            "uses_realized_outcomes": False,
            "historical_scoring_performed": False,
            "production_default_change_licensed": False,
            "promotion_authority": False,
            "test_only": not authoritative,
        }, field="lineups_sha256")
        results[profile.profile_id] = validate_profile_lineups_v1(
            body, players=prepared.players
        )
    if tuple(results) != profiles.PROFILE_ORDER:
        _fail("profile execution order differs")
    schedule_hashes = {row["world_schedule_sha256"] for row in results.values()}
    work_hashes = {row["work_sha256"] for row in results.values()}
    attempt_counts = {row["attempt_count"] for row in results.values()}
    source_hashes = {row["source_authority_sha256"] for row in results.values()}
    if any(len(values) != 1 for values in (
        schedule_hashes, work_hashes, attempt_counts, source_hashes
    )):
        _fail("profile matrices do not share equal source/schedule/work")
    return results


def validate_profile_lineups_v1(
    value: object,
    *,
    players: Sequence[rw.PlayerSpec] | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="profile lineups")
    expected = {
        "schema", "slate", "source_authority", "source_authority_sha256",
        "profile", "profile_sha256", "profile_registry_sha256", "work",
        "work_sha256", "world_schedule", "world_schedule_sha256",
        "attempt_count", "all_attempts_optimal", "visit_results",
        "visit_results_sha256", "unique_lineup_count", "unique_lineups",
        "unique_lineups_sha256", "solver_authority", "solver_authority_sha256",
        "authoritative_solver_proofs_complete",
        "raw_solver_log_and_solution_bodies_persisted", "outcome_fields_read",
        "uses_realized_outcomes", "historical_scoring_performed",
        "production_default_change_licensed", "promotion_authority",
        "test_only", "lineups_sha256",
    }
    if set(item) != expected or item.get("schema") != authority.PROFILE_LINEUPS_SCHEMA:
        _fail("profile lineups fields/schema differ")
    if item["lineups_sha256"] != _hash({
        key: row for key, row in item.items() if key != "lineups_sha256"
    }):
        _fail("profile lineups self-hash differs")
    profile_raw = _mapping(item["profile"], label="profile payload")
    profile_id = profile_raw.get("profile_id")
    profile = profiles.population_profile_v1(str(profile_id))
    if (
        profile_raw != profile.payload()
        or item["profile_sha256"] != profile.fingerprint
        or item["profile_registry_sha256"]
        != profiles.population_profile_registry_v1()["registry_sha256"]
        or item["work_sha256"] != _hash(item["work"])
        or item["world_schedule_sha256"] != _hash(item["world_schedule"])
        or item["visit_results_sha256"] != _hash(item["visit_results"])
        or item["unique_lineups_sha256"] != _hash(item["unique_lineups"])
        or item["all_attempts_optimal"] is not True
        or item["raw_solver_log_and_solution_bodies_persisted"] is not False
        or item["outcome_fields_read"] != []
        or item["uses_realized_outcomes"] is not False
        or item["historical_scoring_performed"] is not False
        or item["production_default_change_licensed"] is not False
        or item["promotion_authority"] is not False
    ):
        _fail("profile lineups fixed authority differs")
    source = _mapping(item["source_authority"], label="lineups source authority")
    if (
        source.get("source_authority_sha256")
        != _hash({
            key: row for key, row in source.items()
            if key != "source_authority_sha256"
        })
        or item["source_authority_sha256"]
        != source.get("source_authority_sha256")
    ):
        _fail("profile lineups source authority differs")
    work_raw = _mapping(item["work"], label="lineups work")
    try:
        work = profiles.SharedSolverWork(
            world_blocks=tuple(work_raw["world_blocks"]),
            worlds_per_block=work_raw["worlds_per_block"],
            solve_attempts_per_block=work_raw["solve_attempts_per_block"],
            solver_timeout_seconds=work_raw["solver_timeout_seconds"],
            selected_entry_budget=work_raw["selected_entry_budget"],
        )
    except Exception as exc:
        raise CorpusR6PopulationChallengerRuntimeV1Error(
            f"profile lineups work is invalid: {exc}"
        ) from exc
    if work.payload() != work_raw:
        _fail("profile lineups work reconstruction differs")
    schedule = _sequence(item["world_schedule"], label="world schedule")
    visits = _sequence(item["visit_results"], label="visit results")
    if (
        len(schedule) != work.solves_per_profile_per_slate
        or item["attempt_count"] != len(schedule)
        or len(visits) != len(schedule)
    ):
        _fail("profile lineups visit coverage differs")
    expected_blocks = [
        block
        for block in work.world_blocks
        for _ in range(work.solve_attempts_per_block)
    ]
    observed_blocks: list[object] = []
    observed_worlds: set[tuple[object, object]] = set()
    for world_raw in schedule:
        world = _mapping(world_raw, label="scheduled world")
        if set(world) != {"block", "index"}:
            _fail("scheduled world fields differ")
        block = world["block"]
        index = world["index"]
        if (
            type(block) is not str
            or type(index) is not int
            or index < 0
            or index >= work.worlds_per_block
            or (block, index) in observed_worlds
        ):
            _fail("scheduled world identity/range differs")
        observed_blocks.append(block)
        observed_worlds.add((block, index))
    if observed_blocks != expected_blocks:
        _fail("scheduled world block/work order differs")
    slate = _mapping(item["slate"], label="lineups slate")
    observed_rosters: list[tuple[str, ...]] = []
    for expected_ordinal, (world_raw, visit_raw) in enumerate(
        zip(schedule, visits, strict=True)
    ):
        world = _mapping(world_raw, label="scheduled world")
        visit = _mapping(visit_raw, label="visit result")
        if (
            visit.get("schema") != VISIT_RESULT_SCHEMA
            or visit.get("visit_ordinal") != expected_ordinal
            or visit.get("world") != world
            or visit.get("construction_serial")
            != profiles.PROFILE_ORDER.index(profile.profile_id) * len(schedule)
            + expected_ordinal
            or visit.get("visit_result_sha256") != _hash({
                key: row for key, row in visit.items()
                if key != "visit_result_sha256"
            })
        ):
            _fail("visit result order/identity differs")
        lineup = _mapping(visit.get("lineup_identity"), label="lineup identity")
        if lineup.get("lineup_sha256") != _hash({
            key: row for key, row in lineup.items() if key != "lineup_sha256"
        }) or (
            lineup.get("schema") != LINEUP_ID_SCHEMA
            or lineup.get("slate_id") != slate.get("slate_id")
            or lineup.get("profile_id") != profile.profile_id
            or lineup.get("profile_sha256") != profile.fingerprint
        ):
            _fail("visit lineup identity differs")
        roster = tuple(_sequence(lineup.get("roster"), label="lineup roster"))
        observed_rosters.append(roster)
        if players is not None:
            try:
                observed_shape = profiles.audit_profile_roster_v1(
                    players, roster, profile.profile_id
                )
            except Exception as exc:
                raise CorpusR6PopulationChallengerRuntimeV1Error(
                    f"profile lineup legality differs: {exc}"
                ) from exc
            expected_shape = {
                key: observed_shape[key] for key in (
                    "salary", "qb_partner_count", "bring_back_count",
                    "opposing_wr_count", "max_from_game", "rb_vs_dst_count",
                    "same_team_rb_pair_count",
                )
            }
            if visit.get("profile_shape") != expected_shape:
                _fail("visit profile-shape receipt differs")
        proof = visit.get("solver_proof")
        proof_sha = visit.get("solver_proof_sha256")
        if item["authoritative_solver_proofs_complete"] is True:
            proof_body = _mapping(proof, label="solver proof")
            if (
                proof_body.get("proof_sha256") != proof_sha
                or proof_sha != _hash({
                    key: row for key, row in proof_body.items()
                    if key != "proof_sha256"
                })
            ):
                _fail("visit solver proof identity differs")
        elif proof is not None or proof_sha is not None:
            _fail("non-authoritative visit unexpectedly carries a solver proof")
    unique = _sequence(item["unique_lineups"], label="unique lineups")
    first: dict[tuple[str, ...], int] = {}
    counts = Counter(observed_rosters)
    for ordinal, roster in enumerate(observed_rosters):
        first.setdefault(roster, ordinal)
    if item["unique_lineup_count"] != len(first) or len(unique) != len(first):
        _fail("unique lineup count differs")
    expected_unique = []
    for roster, first_ordinal in sorted(first.items(), key=lambda row: row[1]):
        expected_unique.append({
            "first_visit_ordinal": first_ordinal,
            "occurrence_count": counts[roster],
            "lineup_identity": _lineup_identity_v1(
                slate_id=str(slate["slate_id"]),
                profile_id=profile.profile_id,
                profile_sha256=profile.fingerprint,
                roster=roster,
            ),
        })
    if unique != expected_unique:
        _fail("first-occurrence unique lineup projection differs")
    if (
        item["authoritative_solver_proofs_complete"] is True
        and (item["test_only"] is not False or item["solver_authority"] is None)
    ) or (
        item["authoritative_solver_proofs_complete"] is False
        and item["test_only"] is not True
    ):
        _fail("profile lineup execution-authority flag differs")
    if item["authoritative_solver_proofs_complete"] is True:
        solver = _mapping(item["solver_authority"], label="solver authority")
        if item["solver_authority_sha256"] != legal.canonical_sha256(solver):
            _fail("profile lineup solver authority differs")
    elif item["solver_authority"] is not None or item[
        "solver_authority_sha256"
    ] is not None:
        _fail("test-only profile unexpectedly carries solver authority")
    return item


def execute_equal_work_for_test_v1(
    *,
    prepared: later.PreparedLaterSlate,
    work: profiles.SharedSolverWork,
    solver: SolverCallback,
    source_authority: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    """Bounded offline seam; results are explicitly non-authoritative."""
    schedule, objectives, schedule_sha = _schedule_and_objectives_v1(prepared, work)
    return _execute_equal_work_v1(
        prepared=prepared,
        schedule=schedule,
        objectives=objectives,
        schedule_sha256=schedule_sha,
        source_authority=source_authority,
        work=work,
        solver=solver,
        authoritative=False,
        solver_authority=None,
    )


def _build_task_result_v1(
    *,
    request: Mapping[str, object],
    source_authority: Mapping[str, object],
    profile_bodies: Mapping[str, Mapping[str, object]],
    profile_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    request_item = authority.validate_task_request_v1(request)
    if tuple(profile_bodies) != profiles.PROFILE_ORDER or tuple(
        profile_identities
    ) != profiles.PROFILE_ORDER:
        _fail("task result profile order differs")
    rows = []
    for profile_id in profiles.PROFILE_ORDER:
        body = validate_profile_lineups_v1(profile_bodies[profile_id])
        if body["test_only"] is not False:
            _fail("task result cannot bind test-only profile lineups")
        identity = authority.bind_body_to_identity_v1(
            body, profile_identities[profile_id], label=f"{profile_id} lineups"
        )
        rows.append({
            "profile_id": profile_id,
            "profile_sha256": body["profile_sha256"],
            "lineups_sha256": body["lineups_sha256"],
            "lineups_identity": identity,
            "attempt_count": body["attempt_count"],
            "unique_lineup_count": body["unique_lineup_count"],
            "world_schedule_sha256": body["world_schedule_sha256"],
            "work_sha256": body["work_sha256"],
        })
    if (
        len({row["world_schedule_sha256"] for row in rows}) != 1
        or len({row["work_sha256"] for row in rows}) != 1
        or len({row["attempt_count"] for row in rows}) != 1
    ):
        _fail("task result profiles do not retain equal work/schedule")
    body = _with_hash({
        "schema": authority.TASK_RESULT_SCHEMA,
        "task_index": request_item["task_index"],
        "source_ordinal": request_item["source_ordinal"],
        "request_sha256": request_item["request_sha256"],
        "source_authority": dict(source_authority),
        "source_authority_sha256": source_authority["source_authority_sha256"],
        "profile_results": rows,
        "profile_results_sha256": _hash(rows),
        "profile_count": len(rows),
        "solves_per_profile": request_item["solves_per_profile"],
        "total_solves": request_item["total_solves"],
        "all_profiles_complete": True,
        "equal_solver_work_confirmed": True,
        "equal_world_schedule_confirmed": True,
        "outcome_fields_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_performed": False,
        "production_default_change_licensed": False,
        "promotion_authority": False,
    }, field="task_result_sha256")
    return validate_task_result_v1(body)


def validate_task_result_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="challenger task result")
    expected = {
        "schema", "task_index", "source_ordinal", "request_sha256",
        "source_authority", "source_authority_sha256", "profile_results",
        "profile_results_sha256", "profile_count", "solves_per_profile",
        "total_solves", "all_profiles_complete", "equal_solver_work_confirmed",
        "equal_world_schedule_confirmed", "outcome_fields_read",
        "uses_realized_outcomes", "historical_scoring_performed",
        "production_default_change_licensed", "promotion_authority",
        "task_result_sha256",
    }
    if set(item) != expected or item.get("schema") != authority.TASK_RESULT_SCHEMA:
        _fail("challenger task result fields/schema differ")
    if item["task_result_sha256"] != _hash({
        key: row for key, row in item.items() if key != "task_result_sha256"
    }):
        _fail("challenger task result self-hash differs")
    rows = _sequence(item["profile_results"], label="profile results")
    if (
        item["profile_results_sha256"] != _hash(rows)
        or item["profile_count"] != len(profiles.PROFILE_ORDER)
        or [row.get("profile_id") for row in rows] != list(profiles.PROFILE_ORDER)
        or item["solves_per_profile"] != authority.SOLVES_PER_PROFILE_PER_SLATE
        or item["total_solves"] != authority.SOLVES_PER_TASK
        or any(row.get("attempt_count") != item["solves_per_profile"] for row in rows)
        or len({row.get("world_schedule_sha256") for row in rows}) != 1
        or len({row.get("work_sha256") for row in rows}) != 1
        or item["all_profiles_complete"] is not True
        or item["equal_solver_work_confirmed"] is not True
        or item["equal_world_schedule_confirmed"] is not True
        or item["outcome_fields_read"] != []
        or item["uses_realized_outcomes"] is not False
        or item["historical_scoring_performed"] is not False
        or item["production_default_change_licensed"] is not False
        or item["promotion_authority"] is not False
    ):
        _fail("challenger task result completeness/safety differs")
    for row in rows:
        _identity(row.get("lineups_identity"), label="profile lineups")
    return item


def build_task_completion_v1(
    *,
    task_result: Mapping[str, object],
    task_result_identity: Mapping[str, object],
) -> dict[str, object]:
    """Bind the task-result object's immutable generation for terminal output."""
    result = validate_task_result_v1(task_result)
    identity = authority.bind_body_to_identity_v1(
        result, task_result_identity, label="challenger task result"
    )
    profile_identities = {
        str(row["profile_id"]): _identity(
            row["lineups_identity"], label="completion profile lineups"
        )
        for row in result["profile_results"]
    }
    body = {
        "schema": TASK_COMPLETION_SCHEMA,
        "task_index": result["task_index"],
        "source_ordinal": result["source_ordinal"],
        "task_result_sha256": result["task_result_sha256"],
        "task_result_identity": identity,
        "profile_lineup_identities": profile_identities,
        "profile_lineup_identities_sha256": _hash(profile_identities),
        "all_profiles_complete": True,
        "outcome_fields_read": [],
        "uses_realized_outcomes": False,
    }
    return {**body, "task_completion_sha256": _hash(body)}


def validate_task_completion_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="challenger task completion")
    expected = {
        "schema", "task_index", "source_ordinal", "task_result_sha256",
        "task_result_identity", "profile_lineup_identities",
        "profile_lineup_identities_sha256", "all_profiles_complete",
        "outcome_fields_read", "uses_realized_outcomes",
        "task_completion_sha256",
    }
    if set(item) != expected or item.get("schema") != TASK_COMPLETION_SCHEMA:
        _fail("challenger task completion fields/schema differ")
    if item["task_completion_sha256"] != _hash({
        key: row for key, row in item.items() if key != "task_completion_sha256"
    }):
        _fail("challenger task completion self-hash differs")
    result_identity = _identity(
        item["task_result_identity"], label="completion task result"
    )
    profile_identities = _mapping(
        item["profile_lineup_identities"], label="completion profile identities"
    )
    if (
        tuple(profile_identities) != profiles.PROFILE_ORDER
        or item["profile_lineup_identities_sha256"] != _hash(profile_identities)
        or item["all_profiles_complete"] is not True
        or item["outcome_fields_read"] != []
        or item["uses_realized_outcomes"] is not False
    ):
        _fail("challenger task completion identity/safety differs")
    if (
        type(item["task_result_sha256"]) is not str
        or len(item["task_result_sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in item[
            "task_result_sha256"
        ])
    ):
        _fail("challenger task result self-hash differs")
    for profile_id, identity in profile_identities.items():
        _identity(identity, label=f"completion {profile_id} lineups")
    return item


def execute_task_v1(
    request_value: object,
    *,
    read_exact: authority.ReadExact,
    publish_create_once: authority.PublishCreateOnce,
) -> dict[str, object]:
    """Execute and publish one exact source-ordinal task authoritatively."""
    request = authority.validate_task_request_v1(request_value)
    profiles.require_neutral_inherited_constraints_v1(
        profiles.InheritedConstraintSurface()
    )
    projection_body, projection_identity = authority.exact_read_json_v1(
        request["projection_bundle_identity"],
        read_exact=read_exact,
        label="projection bundle",
        maximum_bytes=authority.MAXIMUM_PROJECTION_BUNDLE_BYTES,
    )
    source = _projection_source_authority_v1(
        projection_body,
        projection_identity=projection_identity,
        expected_source_ordinal=int(request["source_ordinal"]),
    )
    prepared = _prepared_slate_v1(source, read_exact=read_exact)
    schedule, objectives, schedule_sha = _schedule_and_objectives_v1(
        prepared, authority.DEFAULT_WORK
    )
    try:
        solver_authority = legal._cbc_runtime_authority()
    except Exception as exc:
        raise CorpusR6PopulationChallengerRuntimeV1Error(
            f"exact CBC runtime authority failed: {exc}"
        ) from exc
    bodies = _execute_equal_work_v1(
        prepared=prepared,
        schedule=schedule,
        objectives=objectives,
        schedule_sha256=schedule_sha,
        source_authority=source,
        work=authority.DEFAULT_WORK,
        solver=legal.default_cbc_solver,
        authoritative=True,
        solver_authority=solver_authority,
    )
    outputs = _mapping(request["expected_outputs"], label="expected outputs")
    output_uris = _mapping(
        outputs["profile_lineup_uris"], label="profile lineup URIs"
    )
    identities: dict[str, dict[str, object]] = {}
    for profile_id in profiles.PROFILE_ORDER:
        identities[profile_id] = authority.publish_canonical_create_once_v1(
            uri=str(output_uris[profile_id]),
            value=bodies[profile_id],
            maximum_bytes=authority.MAXIMUM_PROFILE_LINEUPS_BYTES,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
        )
    result = _build_task_result_v1(
        request=request,
        source_authority=source,
        profile_bodies=bodies,
        profile_identities=identities,
    )
    result_identity = authority.publish_canonical_create_once_v1(
        uri=str(outputs["task_result_uri"]),
        value=result,
        maximum_bytes=authority.MAXIMUM_TASK_RESULT_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    return validate_task_completion_v1(build_task_completion_v1(
        task_result=result,
        task_result_identity=result_identity,
    ))


__all__ = [
    "CorpusR6PopulationChallengerRuntimeV1Error",
    "LINEUP_ID_SCHEMA",
    "SOURCE_AUTHORITY_SCHEMA",
    "TASK_COMPLETION_SCHEMA",
    "VISIT_RESULT_SCHEMA",
    "build_task_completion_v1",
    "execute_equal_work_for_test_v1",
    "execute_task_v1",
    "validate_profile_lineups_v1",
    "validate_task_completion_v1",
    "validate_task_result_v1",
]
