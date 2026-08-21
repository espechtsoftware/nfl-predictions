"""Pure score-free sharding core for the LR8 earlier-period source.

The monolithic LR8 source builder is scientifically authoritative.  This
module only changes transport granularity: one registered slate/block cell is
prepared and solved at a time, then exactly seventy accepted cells are
reassembled into the same :class:`~lr8_training_source.TrainingSourceBundle`.
Preparation and execution receipts are validated and retained in the returned
aggregate envelope, but are deliberately absent from the scientific freeze.

There are no warehouse, object-store, Cloud Run, or solver clients here.
Callers supply already-read score-free source rows and a solver callback.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
import math
from typing import Final

import numpy as np

from nfl_dfs.research import lr8_historical_arm as lr8
from nfl_dfs.research import lr8_training_source as training
from nfl_dfs.research import residual_world_columns as rw


PREPARED_CELL_VERSION: Final = "lr8-full-source-prepared-cell-v1"
CELL_SHARD_VERSION: Final = "lr8-full-source-cell-shard-v1"
AGGREGATE_VERSION: Final = "lr8-full-source-shard-aggregate-v1"
FLOAT32_DTYPE_STR: Final = np.dtype(np.float32).str
EXPECTED_CELL_KEYS: Final = tuple(
    (season, week, block)
    for season, week in training.EXPECTED_SLATE_KEYS
    for block in training.BLOCK_ORDER
)
EXPECTED_CELLS: Final = len(EXPECTED_CELL_KEYS)


class LR8FullSourceShardError(ValueError):
    """A fail-closed LR8 source-shard contract violation."""


@dataclass(frozen=True, slots=True)
class ObjectReceipt:
    """Immutable, generation-pinned GCS content identity."""

    uri: str
    generation: str
    sha256: str
    bytes: int

    def as_dict(self) -> dict[str, object]:
        return {
            "uri": self.uri,
            "generation": self.generation,
            "sha256": self.sha256,
            "bytes": self.bytes,
        }


@dataclass(frozen=True, slots=True)
class PITCellReplay:
    """The score-free PIT replay inputs for one registered cell."""

    target_season: int
    block: str
    projection_seed: int
    source_environment_role_seed_nonoperative: int
    replay_path_id: str
    model_training_seasons: tuple[int, ...]
    model_fit_input_sha256: str
    model_fit_sha256: str
    fit_source_receipts: tuple[Mapping[str, object] | ObjectReceipt, ...]
    slate: training.ReplaySlateWorlds
    target_player_labels_read: bool = False
    candidate_labels_read: bool = False
    candidate_world_family: str = training.CANDIDATE_WORLD_FAMILY
    role_belief_worlds_used: bool = False
    b1_inputs_used: bool = False
    a2a_inputs_used: bool = False
    later_period_inputs_used: bool = False


@dataclass(frozen=True, slots=True)
class PreparedCell:
    """Immutable scientific inputs for one of the exact seventy cells."""

    version: str
    cell_index: int
    season: int
    week: int
    block: str
    players: tuple[rw.PlayerSpec, ...]
    incumbent_candidates: tuple[tuple[str, ...], ...]
    catalog_sha256: str
    incumbent_candidates_sha256: str
    catalog_source_receipts: tuple[ObjectReceipt, ...]
    incumbent_source_receipts: tuple[ObjectReceipt, ...]
    projection_seed: int
    source_environment_role_seed_nonoperative: int
    replay_path_id: str
    model_training_seasons: tuple[int, ...]
    model_fit_input_sha256: str
    model_fit_sha256: str
    fit_source_receipts: tuple[ObjectReceipt, ...]
    player_ids: tuple[str, ...]
    player_ids_sha256: str
    player_draws_dtype: str
    player_draws_shape: tuple[int, int]
    player_draws_bytes: bytes = field(compare=False, repr=False)
    player_draws_bytes_sha256: str
    player_draws_sha256: str
    draw_source_receipts: tuple[ObjectReceipt, ...]
    prepared_cell_sha256: str


@dataclass(frozen=True, slots=True)
class CellShard:
    """One accepted-cell envelope around an existing frozen block source."""

    version: str
    prepared: PreparedCell
    frozen_block: training.FrozenBlockSource
    preparation_receipt: ObjectReceipt
    execution_attempt_receipt: ObjectReceipt
    accepted: bool
    frozen_block_sha256: str
    shard_sha256: str


@dataclass(frozen=True, slots=True)
class CellExecutionProvenance:
    """Transport provenance intentionally excluded from the science freeze."""

    cell_index: int
    season: int
    week: int
    block: str
    preparation_receipt: ObjectReceipt
    execution_attempt_receipt: ObjectReceipt
    shard_sha256: str


@dataclass(frozen=True, slots=True)
class AggregatedTrainingSource:
    """Strict aggregate plus its byte-exact authoritative freeze."""

    version: str
    bundle: training.TrainingSourceBundle
    freeze_manifest: Mapping[str, object] = field(compare=False, repr=False)
    freeze_bytes: bytes = field(compare=False, repr=False)
    cell_provenance: tuple[CellExecutionProvenance, ...]


def _receipt(
    value: Mapping[str, object] | ObjectReceipt,
    *,
    label: str,
) -> ObjectReceipt:
    raw = value.as_dict() if isinstance(value, ObjectReceipt) else value
    try:
        normalized = training._normalized_receipt(raw, label=label)  # noqa: SLF001
    except training.LR8TrainingSourceError as exc:
        raise LR8FullSourceShardError(str(exc)) from exc
    return ObjectReceipt(
        uri=str(normalized["uri"]),
        generation=str(normalized["generation"]),
        sha256=str(normalized["sha256"]),
        bytes=int(normalized["bytes"]),
    )


def _receipts(
    values: Sequence[Mapping[str, object] | ObjectReceipt],
    *,
    label: str,
) -> tuple[ObjectReceipt, ...]:
    if isinstance(values, (str, bytes)):
        raise LR8FullSourceShardError(f"{label} must be a receipt sequence")
    result = tuple(
        _receipt(value, label=f"{label}[{index}]")
        for index, value in enumerate(values)
    )
    if not result:
        raise LR8FullSourceShardError(f"{label} must not be empty")
    if len(set(result)) != len(result):
        raise LR8FullSourceShardError(f"{label} repeats a content identity")
    return result


def _receipt_dicts(values: Sequence[ObjectReceipt]) -> tuple[dict[str, object], ...]:
    return tuple(value.as_dict() for value in values)


def _exact_cell_index(value: object) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise LR8FullSourceShardError("cell index must be an exact integer")
    result = int(value)
    if not 0 <= result < EXPECTED_CELLS:
        raise LR8FullSourceShardError("cell index is outside the exact 70-cell grid")
    return result


def _expected_key(cell_index: int) -> tuple[int, int, str]:
    return EXPECTED_CELL_KEYS[_exact_cell_index(cell_index)]


def _false(value: object, *, label: str) -> None:
    if not isinstance(value, bool) or value is not False:
        raise LR8FullSourceShardError(f"{label} must be literal False")


def _draws_from_prepared(value: PreparedCell) -> np.ndarray:
    if value.player_draws_dtype != FLOAT32_DTYPE_STR:
        raise LR8FullSourceShardError("prepared draw dtype differs from float32")
    if value.player_draws_shape != (
        len(value.player_ids), training.WORLDS_PER_BLOCK
    ):
        raise LR8FullSourceShardError("prepared draw shape differs")
    expected_bytes = math.prod(value.player_draws_shape) * np.dtype(np.float32).itemsize
    if not isinstance(value.player_draws_bytes, bytes) or (
        len(value.player_draws_bytes) != expected_bytes
    ):
        raise LR8FullSourceShardError("prepared draw byte length differs")
    if sha256(value.player_draws_bytes).hexdigest() != value.player_draws_bytes_sha256:
        raise LR8FullSourceShardError("prepared draw byte hash differs")
    draws = np.frombuffer(value.player_draws_bytes, dtype=np.float32).reshape(
        value.player_draws_shape
    )
    if not draws.flags.c_contiguous or not np.isfinite(draws).all():
        raise LR8FullSourceShardError(
            "prepared draws must be exact finite contiguous float32 bytes"
        )
    if training.array_sha256(draws) != value.player_draws_sha256:
        raise LR8FullSourceShardError("prepared scientific draw hash differs")
    draws.flags.writeable = False
    return draws


def _prepared_payload(value: PreparedCell) -> dict[str, object]:
    return {
        "version": value.version,
        "cell_index": value.cell_index,
        "season": value.season,
        "week": value.week,
        "block": value.block,
        "catalog": training._catalog_payload(value.players),  # noqa: SLF001
        "catalog_sha256": value.catalog_sha256,
        "incumbent_candidates": [list(row) for row in value.incumbent_candidates],
        "incumbent_candidates_sha256": value.incumbent_candidates_sha256,
        "catalog_source_receipts": [
            receipt.as_dict() for receipt in value.catalog_source_receipts
        ],
        "incumbent_source_receipts": [
            receipt.as_dict() for receipt in value.incumbent_source_receipts
        ],
        "projection_seed": value.projection_seed,
        "source_environment_role_seed_nonoperative": (
            value.source_environment_role_seed_nonoperative
        ),
        "replay_path_id": value.replay_path_id,
        "model_training_seasons": list(value.model_training_seasons),
        "model_fit_input_sha256": value.model_fit_input_sha256,
        "model_fit_sha256": value.model_fit_sha256,
        "fit_source_receipts": [
            receipt.as_dict() for receipt in value.fit_source_receipts
        ],
        "player_ids": list(value.player_ids),
        "player_ids_sha256": value.player_ids_sha256,
        "player_draws": {
            "dtype": value.player_draws_dtype,
            "shape": list(value.player_draws_shape),
            "bytes": len(value.player_draws_bytes),
            "bytes_sha256": value.player_draws_bytes_sha256,
            "array_sha256": value.player_draws_sha256,
        },
        "draw_source_receipts": [
            receipt.as_dict() for receipt in value.draw_source_receipts
        ],
        "target_player_labels_read": False,
        "candidate_labels_read": False,
        "candidate_world_family": training.CANDIDATE_WORLD_FAMILY,
        "role_belief_worlds_used": False,
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "later_period_inputs_used": False,
    }


def _validate_prepared(value: PreparedCell) -> np.ndarray:
    if not isinstance(value, PreparedCell) or value.version != PREPARED_CELL_VERSION:
        raise LR8FullSourceShardError("prepared cell identity differs")
    key = _expected_key(value.cell_index)
    if (value.season, value.week, value.block) != key:
        raise LR8FullSourceShardError("prepared cell is outside registered order")
    if (
        value.projection_seed,
        value.source_environment_role_seed_nonoperative,
    ) != training.BLOCK_SEED_PAIRS[value.block]:
        raise LR8FullSourceShardError("prepared cell seed pair differs")
    if value.replay_path_id != training.PIT_REPLAY_PATH_ID:
        raise LR8FullSourceShardError("prepared cell replay path differs")
    if value.model_training_seasons != training.MODEL_TRAINING_SEASONS[value.season]:
        raise LR8FullSourceShardError("prepared cell fit seasons differ")
    try:
        players = training._players(value.players)  # noqa: SLF001
        incumbents = training._identities(  # noqa: SLF001
            value.incumbent_candidates, label="prepared incumbent candidates"
        )
        training._strict_sha256(  # noqa: SLF001
            value.model_fit_input_sha256, label="prepared fit input hash"
        )
        training._strict_sha256(  # noqa: SLF001
            value.model_fit_sha256, label="prepared fit hash"
        )
    except training.LR8TrainingSourceError as exc:
        raise LR8FullSourceShardError(str(exc)) from exc
    if players != value.players or incumbents != value.incumbent_candidates:
        raise LR8FullSourceShardError("prepared catalog/incumbent normalization differs")
    if training.catalog_sha256(players) != value.catalog_sha256:
        raise LR8FullSourceShardError("prepared catalog hash differs")
    if training.identities_sha256(incumbents) != value.incumbent_candidates_sha256:
        raise LR8FullSourceShardError("prepared incumbent hash differs")
    for roster in incumbents:
        try:
            lr8.audit_dk_classic_identity(players, roster)
        except lr8.LR8Error as exc:
            raise LR8FullSourceShardError(
                "prepared incumbent is not DK Classic legal"
            ) from exc
    if value.player_ids != tuple(player.player_id for player in players):
        raise LR8FullSourceShardError("prepared player ids are not catalog-aligned")
    if training.player_ids_sha256(value.player_ids) != value.player_ids_sha256:
        raise LR8FullSourceShardError("prepared player id hash differs")
    for receipts, label in (
        (value.catalog_source_receipts, "prepared catalog receipts"),
        (value.incumbent_source_receipts, "prepared incumbent receipts"),
        (value.fit_source_receipts, "prepared fit receipts"),
        (value.draw_source_receipts, "prepared draw receipts"),
    ):
        if _receipts(receipts, label=label) != receipts:
            raise LR8FullSourceShardError(f"{label} normalization differs")
    draws = _draws_from_prepared(value)
    if training.canonical_sha256(_prepared_payload(value)) != value.prepared_cell_sha256:
        raise LR8FullSourceShardError("prepared cell hash differs")
    return draws


def prepare_cell(
    *,
    cell_index: int,
    canonical_source: training.CanonicalSlateSource,
    replay: PITCellReplay,
) -> PreparedCell:
    """Normalize and hash one score-free cell without solving it."""
    index = _exact_cell_index(cell_index)
    expected_season, expected_week, expected_block = _expected_key(index)
    if not isinstance(replay, PITCellReplay):
        raise LR8FullSourceShardError("PIT cell replay has the wrong type")
    if (
        replay.target_season,
        replay.slate.season,
        replay.slate.week,
        replay.block,
    ) != (
        expected_season,
        expected_season,
        expected_week,
        expected_block,
    ):
        raise LR8FullSourceShardError("PIT cell replay key differs")
    try:
        players, incumbents, catalog_receipts_raw, incumbent_receipts_raw = (
            training._normalize_canonical_source(canonical_source)  # noqa: SLF001
        )
    except training.LR8TrainingSourceError as exc:
        raise LR8FullSourceShardError(str(exc)) from exc
    if (canonical_source.season, canonical_source.week) != (
        expected_season, expected_week
    ):
        raise LR8FullSourceShardError("canonical source cell key differs")

    if (
        replay.projection_seed,
        replay.source_environment_role_seed_nonoperative,
    ) != training.BLOCK_SEED_PAIRS[expected_block]:
        raise LR8FullSourceShardError("PIT cell replay seed pair differs")
    if replay.replay_path_id != training.PIT_REPLAY_PATH_ID:
        raise LR8FullSourceShardError("PIT cell replay is not score-free")
    if replay.model_training_seasons != training.MODEL_TRAINING_SEASONS[expected_season]:
        raise LR8FullSourceShardError("PIT cell fit seasons differ")
    for label, actual in (
        ("target_player_labels_read", replay.target_player_labels_read),
        ("candidate_labels_read", replay.candidate_labels_read),
        ("role_belief_worlds_used", replay.role_belief_worlds_used),
        ("b1_inputs_used", replay.b1_inputs_used),
        ("a2a_inputs_used", replay.a2a_inputs_used),
        ("later_period_inputs_used", replay.later_period_inputs_used),
    ):
        _false(actual, label=label)
    if replay.candidate_world_family != training.CANDIDATE_WORLD_FAMILY:
        raise LR8FullSourceShardError("PIT cell world family differs")
    try:
        training._strict_sha256(  # noqa: SLF001
            replay.model_fit_input_sha256, label="PIT cell fit input hash"
        )
        training._strict_sha256(  # noqa: SLF001
            replay.model_fit_sha256, label="PIT cell fit hash"
        )
    except training.LR8TrainingSourceError as exc:
        raise LR8FullSourceShardError(str(exc)) from exc
    fit_receipts = _receipts(replay.fit_source_receipts, label="PIT fit receipts")

    row = replay.slate
    if not isinstance(row, training.ReplaySlateWorlds):
        raise LR8FullSourceShardError("PIT cell slate has the wrong type")
    if row.target_outcome_fields_read != ():
        raise LR8FullSourceShardError("PIT cell read a target outcome field")
    try:
        ids = training._strict_player_ids(row.player_ids)  # noqa: SLF001
        ids_digest = training._strict_sha256(  # noqa: SLF001
            row.player_ids_sha256, label="PIT cell player ids hash"
        )
        draws_digest = training._strict_sha256(  # noqa: SLF001
            row.player_draws_sha256, label="PIT cell player draws hash"
        )
    except training.LR8TrainingSourceError as exc:
        raise LR8FullSourceShardError(str(exc)) from exc
    if training.player_ids_sha256(ids) != ids_digest:
        raise LR8FullSourceShardError("PIT cell player ids hash differs")
    source_draws = np.asarray(row.player_draws)
    if (
        source_draws.dtype != np.float32
        or source_draws.shape != (len(ids), training.WORLDS_PER_BLOCK)
        or not source_draws.flags.c_contiguous
        or not np.isfinite(source_draws).all()
        or training.array_sha256(source_draws) != draws_digest
    ):
        raise LR8FullSourceShardError(
            "PIT cell draws must be exact finite contiguous float32 x 10000"
        )
    canonical_ids = tuple(player.player_id for player in players)
    if set(ids) != set(canonical_ids):
        raise LR8FullSourceShardError("PIT cell player universe differs")
    source_rows = {player_id: position for position, player_id in enumerate(ids)}
    aligned = np.array(
        source_draws[[source_rows[player_id] for player_id in canonical_ids]],
        dtype=np.float32,
        copy=True,
        order="C",
    )
    aligned.flags.writeable = False
    draw_bytes = aligned.tobytes(order="C")
    value = PreparedCell(
        version=PREPARED_CELL_VERSION,
        cell_index=index,
        season=expected_season,
        week=expected_week,
        block=expected_block,
        players=players,
        incumbent_candidates=incumbents,
        catalog_sha256=canonical_source.catalog_sha256,
        incumbent_candidates_sha256=(
            canonical_source.incumbent_candidates_sha256
        ),
        catalog_source_receipts=_receipts(
            catalog_receipts_raw, label="catalog source receipts"
        ),
        incumbent_source_receipts=_receipts(
            incumbent_receipts_raw, label="incumbent source receipts"
        ),
        projection_seed=replay.projection_seed,
        source_environment_role_seed_nonoperative=(
            replay.source_environment_role_seed_nonoperative
        ),
        replay_path_id=replay.replay_path_id,
        model_training_seasons=replay.model_training_seasons,
        model_fit_input_sha256=replay.model_fit_input_sha256,
        model_fit_sha256=replay.model_fit_sha256,
        fit_source_receipts=fit_receipts,
        player_ids=canonical_ids,
        player_ids_sha256=training.player_ids_sha256(canonical_ids),
        player_draws_dtype=aligned.dtype.str,
        player_draws_shape=(len(canonical_ids), training.WORLDS_PER_BLOCK),
        player_draws_bytes=draw_bytes,
        player_draws_bytes_sha256=sha256(draw_bytes).hexdigest(),
        player_draws_sha256=training.array_sha256(aligned),
        draw_source_receipts=_receipts(
            row.source_receipts, label="PIT cell draw receipts"
        ),
        prepared_cell_sha256="",
    )
    object.__setattr__(
        value,
        "prepared_cell_sha256",
        training.canonical_sha256(_prepared_payload(value)),
    )
    _validate_prepared(value)
    return value


def _attempt_payload(attempt: training.SolveAttempt) -> dict[str, object]:
    return {
        "block": attempt.block,
        "projection_seed": attempt.projection_seed,
        "world_index": attempt.world_index,
        "roster": list(attempt.roster),
        "objective_micro": attempt.objective_micro,
        "admitted_unique": attempt.admitted_unique,
        "request_sha256": attempt.request_sha256,
        "evidence_receipts": list(attempt.evidence_receipts),
        "evidence_manifest_sha256": attempt.evidence_manifest_sha256,
    }


def _candidate_payload(candidate: training.FrozenCandidate) -> dict[str, object]:
    return training._candidate_freeze_payload(candidate)  # noqa: SLF001


def _validate_block(
    prepared: PreparedCell,
    block: training.FrozenBlockSource,
) -> str:
    draws = _validate_prepared(prepared)
    if not isinstance(block, training.FrozenBlockSource):
        raise LR8FullSourceShardError("cell shard block has the wrong type")
    if (
        block.block,
        block.projection_seed,
        block.source_environment_role_seed_nonoperative,
    ) != (
        prepared.block,
        prepared.projection_seed,
        prepared.source_environment_role_seed_nonoperative,
    ):
        raise LR8FullSourceShardError("cell shard block identity differs")
    if block.player_ids != prepared.player_ids:
        raise LR8FullSourceShardError("cell shard player ids differ")
    block_draws = np.asarray(block.player_draws)
    if (
        block_draws.dtype != np.float32
        or block_draws.shape != prepared.player_draws_shape
        or not block_draws.flags.c_contiguous
        or not np.isfinite(block_draws).all()
        or block_draws.tobytes(order="C") != prepared.player_draws_bytes
        or training.array_sha256(block_draws) != prepared.player_draws_sha256
        or block.player_ids_sha256 != prepared.player_ids_sha256
        or block.player_draws_sha256 != prepared.player_draws_sha256
    ):
        raise LR8FullSourceShardError("cell shard exact draw bytes differ")
    order = training.deterministic_world_order(draws)
    if (
        block.world_order != order
        or block.world_order_sha256 != training.canonical_sha256(list(order))
    ):
        raise LR8FullSourceShardError("cell shard world order differs")
    normalized_source = _receipts(
        block.source_receipts, label="cell shard draw source receipts"
    )
    if normalized_source != prepared.draw_source_receipts:
        raise LR8FullSourceShardError("cell shard draw receipts differ")

    attempts = block.solve_attempts
    if not training.UNIQUE_OPTIMA_PER_BLOCK <= len(attempts) <= (
        training.MAX_SOLVE_ATTEMPTS_PER_BLOCK
    ):
        raise LR8FullSourceShardError("cell shard solve-attempt count is outside 40..80")
    if tuple(attempt.world_index for attempt in attempts) != order[:len(attempts)]:
        raise LR8FullSourceShardError("cell shard solve attempts are not an ordered prefix")
    by_id = {player.player_id: index for index, player in enumerate(prepared.players)}
    micro = rw.to_micro_dk(draws)
    admitted_candidates: list[training.FrozenCandidate] = []
    seen: set[tuple[str, ...]] = set()
    attempt_payloads: list[dict[str, object]] = []
    for attempt in attempts:
        if (
            attempt.block != prepared.block
            or attempt.projection_seed != prepared.projection_seed
        ):
            raise LR8FullSourceShardError("cell shard solve-attempt identity differs")
        request = training._solve_request(  # noqa: SLF001
            season=prepared.season,
            week=prepared.week,
            block=prepared.block,
            players=prepared.players,
            player_draws=draws,
            world_index=attempt.world_index,
            incumbents=prepared.incumbent_candidates,
            catalog_digest=prepared.catalog_sha256,
            incumbent_digest=prepared.incumbent_candidates_sha256,
        )
        try:
            roster = lr8.audit_dk_classic_identity(
                prepared.players, attempt.roster
            )
        except lr8.LR8Error as exc:
            raise LR8FullSourceShardError(
                "cell shard solve attempt is not DK Classic legal"
            ) from exc
        if roster in prepared.incumbent_candidates:
            raise LR8FullSourceShardError("cell shard solve attempt repeats incumbent")
        objective = int(
            micro[[by_id[player_id] for player_id in roster], attempt.world_index].sum(
                dtype=np.int64
            )
        )
        evidence = _receipts(
            attempt.evidence_receipts, label="cell shard solve evidence"
        )
        evidence_dicts = _receipt_dicts(evidence)
        admitted = roster not in seen
        if (
            attempt.roster != roster
            or attempt.objective_micro != objective
            or not isinstance(attempt.admitted_unique, bool)
            or attempt.admitted_unique is not admitted
            or attempt.request_sha256 != request.request_sha256
            or tuple(attempt.evidence_receipts) != evidence_dicts
            or attempt.evidence_manifest_sha256
            != training.canonical_sha256(list(evidence_dicts))
        ):
            raise LR8FullSourceShardError("cell shard solve-attempt receipt differs")
        attempt_payloads.append(_attempt_payload(attempt))
        if not admitted:
            continue
        if len(seen) >= training.UNIQUE_OPTIMA_PER_BLOCK:
            raise LR8FullSourceShardError("cell shard continued after forty optima")
        seen.add(roster)
        anatomy = tuple(lr8.lineup_anatomy(prepared.players, roster))
        admitted_candidates.append(training.FrozenCandidate(
            season=prepared.season,
            week=prepared.week,
            roster=roster,
            anatomy_features=anatomy,
            first_source_block=prepared.block,
            first_source_world_index=attempt.world_index,
            source_occurrences=((prepared.block, attempt.world_index),),
        ))
    if len(admitted_candidates) != training.UNIQUE_OPTIMA_PER_BLOCK:
        raise LR8FullSourceShardError("cell shard does not contain forty unique optima")
    if tuple(admitted_candidates) != block.candidates:
        raise LR8FullSourceShardError(
            "cell shard candidates or cross-block source occurrences differ"
        )
    if training.canonical_sha256(attempt_payloads) != block.solve_attempts_sha256:
        raise LR8FullSourceShardError("cell shard ordered solve-attempt hash differs")
    candidate_identity_payload = [list(row.roster) for row in block.candidates]
    anatomy_payload = [{
        "roster": list(row.roster),
        "features": training._anatomy_payload(row.anatomy_features),  # noqa: SLF001
    } for row in block.candidates]
    legality_payload = [{
        "roster": list(row.roster),
        "hard_domain_id": training.HARD_DOMAIN_ID,
        "dk_classic_legal": True,
        "former_house_rules_applied": [],
    } for row in block.candidates]
    if (
        block.candidate_identities_sha256
        != training.canonical_sha256(candidate_identity_payload)
        or block.anatomy_sha256 != training.canonical_sha256(anatomy_payload)
        or block.legality_sha256 != training.canonical_sha256(legality_payload)
    ):
        raise LR8FullSourceShardError("cell shard candidate freeze hash differs")
    payload = {
        "prepared_cell_sha256": prepared.prepared_cell_sha256,
        "block": block.block,
        "projection_seed": block.projection_seed,
        "source_environment_role_seed_nonoperative": (
            block.source_environment_role_seed_nonoperative
        ),
        "player_ids_sha256": block.player_ids_sha256,
        "player_draws_sha256": block.player_draws_sha256,
        "world_order_sha256": block.world_order_sha256,
        "source_receipts": [receipt.as_dict() for receipt in normalized_source],
        "ordered_solve_attempts": attempt_payloads,
        "ordered_solve_attempts_sha256": block.solve_attempts_sha256,
        "unique_candidates": [_candidate_payload(row) for row in block.candidates],
        "candidate_identities_sha256": block.candidate_identities_sha256,
        "anatomy_sha256": block.anatomy_sha256,
        "legality_sha256": block.legality_sha256,
    }
    return training.canonical_sha256(payload)


def _shard_payload(value: CellShard) -> dict[str, object]:
    return {
        "version": value.version,
        "cell_index": value.prepared.cell_index,
        "season": value.prepared.season,
        "week": value.prepared.week,
        "block": value.prepared.block,
        "prepared_cell_sha256": value.prepared.prepared_cell_sha256,
        "preparation_receipt": value.preparation_receipt.as_dict(),
        "execution_attempt_receipt": value.execution_attempt_receipt.as_dict(),
        "accepted": value.accepted,
        "frozen_block_sha256": value.frozen_block_sha256,
    }


def wrap_cell_shard(
    prepared: PreparedCell,
    frozen_block: training.FrozenBlockSource,
    *,
    preparation_receipt: Mapping[str, object] | ObjectReceipt,
    execution_attempt_receipt: Mapping[str, object] | ObjectReceipt,
    accepted: bool = True,
) -> CellShard:
    """Validate and wrap an already-produced ``FrozenBlockSource``."""
    block_digest = _validate_block(prepared, frozen_block)
    if not isinstance(accepted, bool):
        raise LR8FullSourceShardError("cell acceptance must be a literal bool")
    value = CellShard(
        version=CELL_SHARD_VERSION,
        prepared=prepared,
        frozen_block=frozen_block,
        preparation_receipt=_receipt(
            preparation_receipt, label="cell preparation receipt"
        ),
        execution_attempt_receipt=_receipt(
            execution_attempt_receipt, label="cell execution-attempt receipt"
        ),
        accepted=accepted,
        frozen_block_sha256=block_digest,
        shard_sha256="",
    )
    object.__setattr__(
        value, "shard_sha256", training.canonical_sha256(_shard_payload(value))
    )
    return value


def solve_prepared_cell(
    prepared: PreparedCell,
    solve_world: training.WorldSolver,
    *,
    preparation_receipt: Mapping[str, object] | ObjectReceipt,
    execution_attempt_receipt: Mapping[str, object] | ObjectReceipt,
) -> CellShard:
    """Solve one prepared cell through the existing authoritative block law."""
    if not callable(solve_world):
        raise LR8FullSourceShardError("world solver must be callable")
    draws = _validate_prepared(prepared)
    try:
        block = training._solve_block(  # noqa: SLF001
            season=prepared.season,
            week=prepared.week,
            block=prepared.block,
            players=prepared.players,
            player_ids=prepared.player_ids,
            player_draws=draws,
            world_receipts=_receipt_dicts(prepared.draw_source_receipts),
            incumbents=prepared.incumbent_candidates,
            catalog_digest=prepared.catalog_sha256,
            incumbent_digest=prepared.incumbent_candidates_sha256,
            solve_world=solve_world,
        )
    except training.LR8TrainingSourceError as exc:
        raise LR8FullSourceShardError(str(exc)) from exc
    return wrap_cell_shard(
        prepared,
        block,
        preparation_receipt=preparation_receipt,
        execution_attempt_receipt=execution_attempt_receipt,
    )


def _validate_shard(value: CellShard) -> None:
    if not isinstance(value, CellShard) or value.version != CELL_SHARD_VERSION:
        raise LR8FullSourceShardError("cell shard identity differs")
    if not isinstance(value.accepted, bool) or value.accepted is not True:
        raise LR8FullSourceShardError("strict aggregate requires accepted cells")
    block_digest = _validate_block(value.prepared, value.frozen_block)
    if block_digest != value.frozen_block_sha256:
        raise LR8FullSourceShardError("cell shard block hash differs")
    if _receipt(
        value.preparation_receipt, label="cell preparation receipt"
    ) != value.preparation_receipt:
        raise LR8FullSourceShardError("cell preparation receipt differs")
    if _receipt(
        value.execution_attempt_receipt, label="cell execution-attempt receipt"
    ) != value.execution_attempt_receipt:
        raise LR8FullSourceShardError("cell execution-attempt receipt differs")
    if training.canonical_sha256(_shard_payload(value)) != value.shard_sha256:
        raise LR8FullSourceShardError("cell shard envelope hash differs")


def _same_slate_source(left: PreparedCell, right: PreparedCell) -> bool:
    return (
        left.players == right.players
        and left.incumbent_candidates == right.incumbent_candidates
        and left.catalog_sha256 == right.catalog_sha256
        and left.incumbent_candidates_sha256 == right.incumbent_candidates_sha256
        and left.catalog_source_receipts == right.catalog_source_receipts
        and left.incumbent_source_receipts == right.incumbent_source_receipts
    )


def _same_fit(left: PreparedCell, right: PreparedCell) -> bool:
    return (
        left.model_training_seasons == right.model_training_seasons
        and left.model_fit_input_sha256 == right.model_fit_input_sha256
        and left.model_fit_sha256 == right.model_fit_sha256
        and left.fit_source_receipts == right.fit_source_receipts
    )


def aggregate_cell_shards(
    shards: Sequence[CellShard],
) -> AggregatedTrainingSource:
    """Require and reassemble the exact ordered seventy-cell source grid."""
    if isinstance(shards, (str, bytes)):
        raise LR8FullSourceShardError("cell shards must be a sequence")
    rows = tuple(shards)
    if len(rows) != EXPECTED_CELLS:
        raise LR8FullSourceShardError("strict aggregate requires exactly 70 cells")
    for index, shard in enumerate(rows):
        _validate_shard(shard)
        if shard.prepared.cell_index != index or (
            shard.prepared.season,
            shard.prepared.week,
            shard.prepared.block,
        ) != EXPECTED_CELL_KEYS[index]:
            raise LR8FullSourceShardError(
                "cell shards are not in exact registered order"
            )
    if len({row.prepared.cell_index for row in rows}) != EXPECTED_CELLS:
        raise LR8FullSourceShardError("cell shard indices repeat")
    if len({row.preparation_receipt for row in rows}) != EXPECTED_CELLS:
        raise LR8FullSourceShardError("cell preparation receipts repeat")
    if len({row.execution_attempt_receipt for row in rows}) != EXPECTED_CELLS:
        raise LR8FullSourceShardError("cell execution-attempt receipts repeat")

    by_key = {
        (row.prepared.season, row.prepared.week, row.prepared.block): row
        for row in rows
    }
    frozen_slates: list[training.FrozenTrainingSlate] = []
    for season, week in training.EXPECTED_SLATE_KEYS:
        r0 = by_key[(season, week, "R0")]
        r1 = by_key[(season, week, "R1")]
        if not _same_slate_source(r0.prepared, r1.prepared):
            raise LR8FullSourceShardError("R0/R1 slate source receipts differ")
        if not _same_fit(r0.prepared, r1.prepared):
            raise LR8FullSourceShardError("R0/R1 PIT fit binding differs")
        blocks = (r0.frozen_block, r1.frozen_block)
        pre = tuple(candidate for block in blocks for candidate in block.candidates)
        if len(pre) != training.PRE_CROSS_BLOCK_CANDIDATES:
            raise LR8FullSourceShardError("R0/R1 pre-dedup budget differs")
        post = training._merge_cross_block_candidates(pre)  # noqa: SLF001
        if not training.UNIQUE_OPTIMA_PER_BLOCK <= len(post) <= (
            training.PRE_CROSS_BLOCK_CANDIDATES
        ):
            raise LR8FullSourceShardError("R0/R1 cross-block union is malformed")
        if any(
            candidate.roster in r0.prepared.incumbent_candidates
            for candidate in post
        ):
            raise LR8FullSourceShardError("cross-block union repeats an incumbent")
        frozen_slates.append(training.FrozenTrainingSlate(
            season=season,
            week=week,
            players=r0.prepared.players,
            incumbent_candidates=r0.prepared.incumbent_candidates,
            catalog_sha256=r0.prepared.catalog_sha256,
            incumbent_candidates_sha256=(
                r0.prepared.incumbent_candidates_sha256
            ),
            catalog_source_receipts=_receipt_dicts(
                r0.prepared.catalog_source_receipts
            ),
            incumbent_source_receipts=_receipt_dicts(
                r0.prepared.incumbent_source_receipts
            ),
            blocks=blocks,
            pre_cross_block_candidate_count=len(pre),
            pre_cross_block_sha256=training.canonical_sha256([
                _candidate_payload(candidate) for candidate in pre
            ]),
            post_cross_block_candidates=post,
            post_cross_block_sha256=training.canonical_sha256([
                _candidate_payload(candidate) for candidate in post
            ]),
            cross_block_duplicates=len(pre) - len(post),
        ))

    replay_blocks: list[training.PITReplayBlock] = []
    for season in training.TARGET_SEASONS:
        for block_name in training.BLOCK_ORDER:
            season_cells = [
                by_key[(season, week, block_name)].prepared
                for week in training.EXPECTED_WEEKS[season]
            ]
            first = season_cells[0]
            if any(not _same_fit(first, cell) for cell in season_cells[1:]):
                raise LR8FullSourceShardError(
                    "target-season PIT fit binding changes across weeks"
                )
            replay_blocks.append(training.PITReplayBlock(
                target_season=season,
                block=block_name,
                projection_seed=first.projection_seed,
                source_environment_role_seed_nonoperative=(
                    first.source_environment_role_seed_nonoperative
                ),
                replay_path_id=first.replay_path_id,
                model_training_seasons=first.model_training_seasons,
                model_fit_input_sha256=first.model_fit_input_sha256,
                model_fit_sha256=first.model_fit_sha256,
                fit_source_receipts=_receipt_dicts(first.fit_source_receipts),
                slates=tuple(training.ReplaySlateWorlds(
                    season=cell.season,
                    week=cell.week,
                    player_ids=cell.player_ids,
                    player_draws=_draws_from_prepared(cell),
                    player_ids_sha256=cell.player_ids_sha256,
                    player_draws_sha256=cell.player_draws_sha256,
                    source_receipts=_receipt_dicts(cell.draw_source_receipts),
                    target_outcome_fields_read=(),
                ) for cell in season_cells),
                target_player_labels_read=False,
                candidate_labels_read=False,
                candidate_world_family=training.CANDIDATE_WORLD_FAMILY,
                role_belief_worlds_used=False,
                b1_inputs_used=False,
                a2a_inputs_used=False,
                later_period_inputs_used=False,
            ))
    for season in training.TARGET_SEASONS:
        season_blocks = [
            block for block in replay_blocks if block.target_season == season
        ]
        if not _same_fit(
            by_key[(season, training.EXPECTED_WEEKS[season][0], "R0")].prepared,
            by_key[(season, training.EXPECTED_WEEKS[season][0], "R1")].prepared,
        ) or len({block.model_fit_input_sha256 for block in season_blocks}) != 1:
            raise LR8FullSourceShardError("R0/R1 target-season refit differs")

    bundle = training.TrainingSourceBundle(
        protocol_id=training.PROTOCOL_ID,
        version=training.SOURCE_VERSION,
        canonical_panel_id=training.CANONICAL_PANEL_ID,
        target_seasons=training.TARGET_SEASONS,
        slate_keys=training.EXPECTED_SLATE_KEYS,
        replay_blocks=tuple(replay_blocks),
        slates=tuple(frozen_slates),
    )
    try:
        freeze = training.freeze_training_source(bundle)
        freeze_bytes = training.canonical_json(freeze)
    except training.LR8TrainingSourceError as exc:
        raise LR8FullSourceShardError(str(exc)) from exc
    provenance = tuple(CellExecutionProvenance(
        cell_index=row.prepared.cell_index,
        season=row.prepared.season,
        week=row.prepared.week,
        block=row.prepared.block,
        preparation_receipt=row.preparation_receipt,
        execution_attempt_receipt=row.execution_attempt_receipt,
        shard_sha256=row.shard_sha256,
    ) for row in rows)
    return AggregatedTrainingSource(
        version=AGGREGATE_VERSION,
        bundle=bundle,
        freeze_manifest=freeze,
        freeze_bytes=freeze_bytes,
        cell_provenance=provenance,
    )


__all__ = [
    "AGGREGATE_VERSION",
    "CELL_SHARD_VERSION",
    "EXPECTED_CELL_KEYS",
    "EXPECTED_CELLS",
    "PREPARED_CELL_VERSION",
    "AggregatedTrainingSource",
    "CellExecutionProvenance",
    "CellShard",
    "LR8FullSourceShardError",
    "ObjectReceipt",
    "PITCellReplay",
    "PreparedCell",
    "aggregate_cell_shards",
    "prepare_cell",
    "solve_prepared_cell",
    "wrap_cell_shard",
]
