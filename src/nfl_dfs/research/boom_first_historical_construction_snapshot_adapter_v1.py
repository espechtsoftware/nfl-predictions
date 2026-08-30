"""Exact-snapshot adapter for the construction x allocation cross.

The already-frozen boom-first generation snapshots contain every score-blind
player row, registered role-12 roster, and R0--R4 player-world artifact needed
to run the four construction/allocation cells.  This adapter consumes those
objects by generation-exact identity and deliberately exposes no warehouse,
object-listing, publication, or outcome API.

Only immutable prepared block inputs are cached.  Candidate generation is
rerun for every cell so the named construction preset remains the treatment,
while all four cells share byte-identical player worlds and frozen role input.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
import hashlib
from io import BytesIO
import json
from typing import Final

import numpy as np
import pandas as pd

from ..backtest import engine
from ..backtest.payout import gpp
from ..optimizer.construction_presets import resolve_construction_preset
from . import corpus_r6_boom_first_allocation_v1 as frozen_allocation
from . import corpus_r6_construction_allocation_cross_v1 as cross
from . import lr8_later_period_source as later_source


ADAPTER_VERSION: Final = (
    "boom-first-historical-construction-snapshot-adapter/v1"
)
FROZEN_ROLE_INPUT_SCHEMA: Final = "corpus-r6-frozen-role12-input/v1"

ReadExact = Callable[[Mapping[str, object]], bytes]


class ConstructionSnapshotAdapterError(ValueError):
    """An exact snapshot, world artifact, or generation call differed."""


def _fail(message: str) -> None:
    raise ConstructionSnapshotAdapterError(message)


def _content_identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return cross._content_identity(value, label=label)
    except cross.ConstructionAllocationCrossError as exc:
        raise ConstructionSnapshotAdapterError(str(exc)) from exc


def _exact_read(
    identity: Mapping[str, object], *, read_exact: ReadExact, label: str,
) -> bytes:
    try:
        raw = read_exact(dict(identity))
    except Exception as exc:
        raise ConstructionSnapshotAdapterError(
            f"{label} generation-exact read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or hashlib.sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact bytes differ from identity")
    return raw


@dataclass(frozen=True, slots=True)
class FrozenSnapshotBinding:
    """Two authorities supplied for one score-blind historical slate."""

    snapshot_identity: Mapping[str, object]
    audit_bank_identity: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class _SnapshotState:
    snapshot_identity: Mapping[str, object]
    snapshot: Mapping[str, object]
    audit_bank_identity: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class _PreparedBlock:
    seed_label: str
    slate: pd.DataFrame
    player_draws: np.ndarray
    artifact_totals: np.ndarray
    native_rows: pd.DataFrame
    role_identities: tuple[frozenset[str], ...]
    frozen_role_input_receipt: Mapping[str, object]
    artifact_identity: Mapping[str, object]


def _decode_snapshot(
    binding: FrozenSnapshotBinding, *, read_exact: ReadExact,
) -> _SnapshotState:
    if not isinstance(binding, FrozenSnapshotBinding):
        _fail("snapshot binding has the wrong type")
    identity = _content_identity(
        binding.snapshot_identity, label="generation snapshot"
    )
    audit = _content_identity(binding.audit_bank_identity, label="audit bank")
    raw = _exact_read(identity, read_exact=read_exact, label="generation snapshot")
    try:
        value = json.loads(raw)
        frozen = frozen_allocation.validate_generation_snapshot_v1(value)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        frozen_allocation.CorpusR6BoomFirstAllocationV1Error,
    ) as exc:
        raise ConstructionSnapshotAdapterError(
            "generation snapshot cannot be validated"
        ) from exc
    canonical = frozen_allocation.canonical_json_bytes_v1(frozen)
    if raw != canonical:
        _fail("generation snapshot body is not its exact canonical document")
    return _SnapshotState(
        snapshot_identity=identity,
        snapshot=frozen,
        audit_bank_identity=audit,
    )


def _native_frame(rows: Sequence[Mapping[str, object]]) -> pd.DataFrame:
    return pd.DataFrame([{
        "panel_run_id": row["panel_run_id"],
        "season": row["season"],
        "week": row["week"],
        "cand_ix": row["cand_ix"],
        "tag": row["tag"],
        "players": ",".join(str(value) for value in row["player_ids"]),
        "player_ids": [str(value) for value in row["player_ids"]],
        "score_artifact_uri": row["score_artifact_uri"],
        "score_artifact_sha256": row["score_artifact_sha256"],
    } for row in rows])


def _artifact_arrays(
    receipt: Mapping[str, object], *, raw: bytes,
) -> dict[str, np.ndarray]:
    try:
        validated = later_source.load_artifact_worlds(receipt, raw)
        with np.load(BytesIO(raw), allow_pickle=False) as artifact:
            values = {
                "cand_ix": np.asarray(artifact["cand_ix"]),
                "totals": np.asarray(artifact["totals"]),
                "tail_line": np.asarray(artifact["tail_line"]),
                "player_ids": np.asarray(artifact["player_ids"]).astype(str),
                "player_draws": np.asarray(
                    artifact["player_draws"], dtype=np.float32
                ),
            }
    except (later_source.LR8LaterSourceError, KeyError, ValueError) as exc:
        raise ConstructionSnapshotAdapterError(
            "world artifact cannot be reconstructed"
        ) from exc
    if (
        tuple(values["player_ids"].tolist()) != validated.player_ids
        or not np.array_equal(values["player_draws"], validated.player_draws)
        or values["tail_line"].size != 1
        or float(values["tail_line"].reshape(-1)[0]) != cross.TAIL_LINE
    ):
        _fail("world artifact player worlds or tail line differ")
    return values


def _slate_frame(
    rows: Sequence[Mapping[str, object]], *, player_ids: np.ndarray,
) -> pd.DataFrame:
    frame = pd.DataFrame(list(rows)).copy(deep=True)
    if frame.empty or "id" not in frame or frame.columns.duplicated().any():
        _fail("snapshot player frame differs")
    frame["id"] = frame["id"].astype(str)
    if frame["id"].duplicated().any():
        _fail("snapshot player IDs repeat")
    ordered_ids = [str(value) for value in player_ids]
    if not ordered_ids or len(ordered_ids) != len(set(ordered_ids)):
        _fail("artifact player IDs are empty or repeat")
    indexed = frame.set_index("id", drop=False)
    if set(indexed.index) != set(ordered_ids):
        _fail("snapshot and artifact player catalogs differ")
    result = indexed.loc[ordered_ids].reset_index(drop=True)
    if not result["pos"].astype(str).str.upper().eq("DST").any():
        _fail("world artifact carries no DST row")
    result["draw_idx"] = np.arange(len(result), dtype=int)
    return result


def _prepare_block(
    state: _SnapshotState,
    *,
    seed_label: str,
    read_exact: ReadExact,
) -> _PreparedBlock:
    if seed_label not in cross.SEED_LABELS:
        _fail("seed label lies outside R0--R4")
    index = cross.SEED_LABELS.index(seed_label)
    seed = dict(state.snapshot["seeds"][index])
    if seed.get("block") != seed_label:
        _fail("snapshot seed order differs")
    receipt = dict(seed["artifact_receipt"])
    artifact_identity = _content_identity(
        {key: receipt.get(key) for key in ("uri", "generation", "sha256", "bytes")},
        label=f"{state.snapshot['slate_id']}/{seed_label} world artifact",
    )
    raw = _exact_read(
        artifact_identity,
        read_exact=read_exact,
        label=f"{state.snapshot['slate_id']}/{seed_label} world artifact",
    )
    artifact = _artifact_arrays(receipt, raw=raw)
    slate = _slate_frame(seed["player_rows"], player_ids=artifact["player_ids"])
    draws = np.ascontiguousarray(artifact["player_draws"], dtype=np.float32)
    if draws.shape != (len(slate), cross.WORLDS_PER_BLOCK):
        _fail("snapshot player-world matrix differs")
    dst = slate["pos"].astype(str).str.upper().eq("DST").to_numpy()
    if not dst.any() or float(draws[dst].std(axis=1).max()) != 0.0:
        _fail("snapshot DST world rows differ")
    native_rows = _native_frame(seed["candidate_rows"])
    role_rows = native_rows[
        native_rows["tag"].astype(str).eq("epi")
    ].sort_values("cand_ix", kind="stable")
    if len(role_rows) != cross.ROLE_SOLVES_PER_BLOCK:
        _fail("frozen candidate source is not exact role12")
    role_rosters = [
        [str(value) for value in row]
        for row in role_rows["player_ids"].tolist()
    ]
    role_identities = tuple(frozenset(row) for row in role_rosters)
    if (
        any(len(row) != 9 or len(set(row)) != 9 for row in role_rosters)
        or len(set(role_identities)) != cross.ROLE_SOLVES_PER_BLOCK
    ):
        _fail("frozen role12 roster identities differ")
    player_index = {
        str(player_id): ordinal
        for ordinal, player_id in enumerate(slate["id"].astype(str))
    }
    totals = np.asarray(artifact["totals"])
    for (_, row), roster in zip(role_rows.iterrows(), role_rosters, strict=True):
        cand_ix = int(row["cand_ix"])
        if not 0 <= cand_ix < totals.shape[0] or any(
            player_id not in player_index for player_id in roster
        ):
            _fail("frozen role12 candidate lies outside the artifact")
        rebuilt = draws[[player_index[player_id] for player_id in roster]].sum(
            axis=0
        )
        if not np.allclose(rebuilt, totals[cand_ix], atol=1e-4, rtol=0.0):
            _fail("frozen role12 totals differ from player worlds")
    role_receipt = {
        "schema_version": FROZEN_ROLE_INPUT_SCHEMA,
        "requested_count": cross.ROLE_SOLVES_PER_BLOCK,
        "candidate_rows_sha256": str(seed["candidate_rows_sha256"]),
        "role_rosters_sha256": cross.canonical_sha256(role_rosters),
        "world_artifact_sha256": str(artifact_identity["sha256"]),
        "uses_target_slate_outcomes": False,
    }
    return _PreparedBlock(
        seed_label=seed_label,
        slate=slate,
        player_draws=draws,
        artifact_totals=np.asarray(totals),
        native_rows=native_rows,
        role_identities=role_identities,
        frozen_role_input_receipt=role_receipt,
        artifact_identity=artifact_identity,
    )


def _incumbent_reproduction_receipt(
    batch: engine.CandidateBatch, *, prepared: _PreparedBlock,
) -> dict[str, object]:
    """Require the current named incumbent/control cell to hit its sentinel."""

    expected_rows = prepared.native_rows.sort_values("cand_ix", kind="stable")
    expected = [
        tuple(sorted(str(value) for value in roster))
        for roster in expected_rows["player_ids"]
    ]
    observed = [
        tuple(sorted(str(value) for value in lineup.ids))
        for lineup in batch.candidates
    ]
    totals = np.asarray(batch.candidate_totals, dtype=np.float64)
    frozen_totals = np.asarray(prepared.artifact_totals, dtype=np.float64)
    if observed != expected or totals.shape != frozen_totals.shape:
        _fail("incumbent construction/allocation sentinel roster lattice differs")
    maximum_delta = float(np.abs(totals - frozen_totals).max(initial=0.0))
    if maximum_delta > 1e-6:
        _fail("incumbent construction/allocation sentinel world totals differ")
    return {
        "schema_version": "corpus-r6-frozen-incumbent-reproduction/v1",
        "candidate_count": len(observed),
        "candidate_order_sha256": cross.canonical_sha256(
            [list(roster) for roster in observed]
        ),
        "candidate_matrix_sha256": cross._array_receipt(totals)["sha256"],
        "maximum_total_delta": maximum_delta,
        "exact_roster_order": True,
        "exact_world_totals": True,
        "uses_target_slate_outcomes": False,
    }


class FrozenSnapshotConstructionNativeBookBuilder:
    """NativeBookBuilder over exact boom-first snapshots and world artifacts."""

    def __init__(
        self,
        bindings: Sequence[FrozenSnapshotBinding],
        *,
        read_exact: ReadExact,
        require_exact_panel: bool = True,
    ) -> None:
        if not callable(read_exact):
            _fail("read_exact callback is not callable")
        supplied = tuple(bindings)
        if not supplied:
            _fail("snapshot bindings are empty")
        states = [_decode_snapshot(binding, read_exact=read_exact) for binding in supplied]
        slate_ids = [str(state.snapshot["slate_id"]) for state in states]
        ordinals = [int(state.snapshot["source_ordinal"]) for state in states]
        if len(set(slate_ids)) != len(slate_ids) or len(set(ordinals)) != len(ordinals):
            _fail("snapshot bindings repeat a slate or source ordinal")
        if require_exact_panel and tuple(sorted(slate_ids)) != tuple(
            cross.EXPECTED_SLATE_IDS
        ):
            _fail("snapshot bindings are not the exact Foundry G0 54-slate panel")
        self._read_exact = read_exact
        self._states = {
            str(state.snapshot["slate_id"]): state for state in states
        }
        self._prepared: dict[tuple[str, str], _PreparedBlock] = {}

    def cross_slates(self) -> tuple[cross.CrossSlate, ...]:
        return tuple(
            cross.CrossSlate(
                season=int(state.snapshot["season"]),
                week=int(state.snapshot["week"]),
                slate_id=slate_id,
                source_identity=dict(state.snapshot_identity),
                source_manifest=dict(state.snapshot),
                audit_bank_identity=dict(state.audit_bank_identity),
            )
            for slate_id, state in sorted(self._states.items())
        )

    @staticmethod
    def _validate_seed(
        seed_label: str, projection_seed: int, role_seed: int,
    ) -> None:
        expected = {
            f"R{index}": (int(projection), int(role))
            for index, (projection, role) in enumerate(
                cross.ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs
            )
        }
        if (
            seed_label not in expected
            or type(projection_seed) is not int
            or type(role_seed) is not int
            or (projection_seed, role_seed) != expected[seed_label]
        ):
            _fail("R0--R4 seed identity differs")

    def _prepared_block(self, slate_id: str, seed_label: str) -> _PreparedBlock:
        key = (slate_id, seed_label)
        if key not in self._prepared:
            # Cross generation is seed-major/cell-minor. Retain only the one
            # block shared by the four adjacent cells; carrying 270 large NPZ
            # matrices through the full panel would defeat the fast path.
            self._prepared.clear()
            self._prepared[key] = _prepare_block(
                self._states[slate_id],
                seed_label=seed_label,
                read_exact=self._read_exact,
            )
        return self._prepared[key]

    def __call__(
        self,
        slate: cross.CrossSlate,
        cell_id: str,
        seed_label: str,
        projection_seed: int,
        role_seed: int,
        policy_environment: Mapping[str, str],
        construction_preset_receipt: Mapping[str, object],
    ) -> engine.CandidateBatch:
        if not isinstance(slate, cross.CrossSlate) or slate.slate_id not in self._states:
            _fail("cross slate is unavailable from the frozen snapshot set")
        state = self._states[slate.slate_id]
        if (
            dict(slate.source_identity) != dict(state.snapshot_identity)
            or dict(slate.source_manifest) != dict(state.snapshot)
            or dict(slate.audit_bank_identity) != dict(state.audit_bank_identity)
        ):
            _fail("cross slate authority differs from the frozen snapshot")
        if cell_id not in cross.CELL_DEFINITION:
            _fail("construction-allocation cell differs")
        self._validate_seed(seed_label, projection_seed, role_seed)
        definition = cross.CELL_DEFINITION[cell_id]
        preset = resolve_construction_preset(str(definition["construction_preset_id"]))
        expected_preset = preset.receipt()
        if dict(construction_preset_receipt) != expected_preset:
            _fail("construction preset receipt differs")
        code_sha = str(policy_environment.get("CODE_SHA", ""))
        expected_environment = cross.cell_environments({"CODE_SHA": code_sha})[
            cell_id
        ]
        if dict(policy_environment) != expected_environment:
            _fail("construction-allocation policy environment differs")

        prepared = self._prepared_block(slate.slate_id, seed_label)
        run_environment = dict(expected_environment)
        run_environment.update({
            "REPLAY_PROJECTION_SEED": str(projection_seed),
            "ROLE_BELIEF_SEED": str(role_seed),
            "MULTISEED_SOURCE_LABEL": seed_label,
            # Role beliefs were frozen as exact candidate identities.  They
            # enter the dedup universe at the original family boundary and
            # are injected below; no alternate role worlds are regenerated.
            "N_EPISTEMIC": "0",
        })
        captures: list[engine.CandidateBatch] = []
        try:
            selected = engine.tail_select_lineups(
                prepared.slate.copy(deep=True),
                prepared.slate.to_dict("records"),
                prepared.player_draws,
                tail_line=cross.TAIL_LINE,
                n_entries=cross.ENTRIES,
                stack=preset.stack,
                construction_preset_receipt=expected_preset,
                objective_col="proj_tourney",
                candidate_multiple=int(run_environment["CAND_MULT"]),
                candidate_generation_entries=int(
                    run_environment["MULTISEED_CANDIDATE_ENTRY_BASIS"]
                ),
                n_boom_solves=int(run_environment["N_BOOM"]),
                n_game_stacks=int(run_environment["N_GAMESTACK"]),
                contest=gpp(),
                sharp_fraction=0.0,
                cand_log_table="",
                cand_log_async=False,
                cand_log_required=False,
                policy_env=run_environment,
                candidate_capture=captures.append,
                preseeded_role_identities=prepared.role_identities,
            )
        except Exception as exc:
            raise ConstructionSnapshotAdapterError(
                f"{slate.slate_id}/{cell_id}/{seed_label} generation failed"
            ) from exc
        if len(captures) != 1 or not selected:
            _fail(
                f"{slate.slate_id}/{cell_id}/{seed_label} did not produce "
                "one native book"
            )
        try:
            batch = frozen_allocation.inject_frozen_role12_v1(
                captures[0],
                native_rows=prepared.native_rows,
                slate=prepared.slate,
                artifact_totals=prepared.artifact_totals,
            )
            engine._validate_candidate_batch(batch)
            _source, descriptor = cross._source_document_descriptor_v1(
                state.snapshot,
                source_identity=state.snapshot_identity,
                season=int(state.snapshot["season"]),
                week=int(state.snapshot["week"]),
                slate_id=slate.slate_id,
                audit_bank_identity=state.audit_bank_identity,
            )
        except (
            frozen_allocation.CorpusR6BoomFirstAllocationV1Error,
            cross.ConstructionAllocationCrossError,
            TypeError,
            ValueError,
        ) as exc:
            raise ConstructionSnapshotAdapterError(
                f"{slate.slate_id}/{cell_id}/{seed_label} native batch differs"
            ) from exc
        if batch.metadata.get("construction_preset_receipt") != expected_preset:
            _fail("engine did not retain the exact construction preset receipt")
        sentinel = None
        if cell_id == (
            f"{cross.PRESET_ORDER[0]}--{cross.ALLOCATION_INCUMBENT}"
        ):
            sentinel = _incumbent_reproduction_receipt(
                batch, prepared=prepared
            )
        return replace(batch, metadata={
            **dict(batch.metadata),
            "role_input_mode": "frozen-role12-candidate-identities",
            "frozen_role_input_receipt": dict(
                prepared.frozen_role_input_receipt
            ),
            "source_identity": dict(state.snapshot_identity),
            "source_document_internal_sha256": descriptor[
                "source_document_internal_sha256"
            ],
            "source_descriptor_sha256": descriptor["descriptor_sha256"],
            "lock_identity": dict(descriptor["lock_identity"]),
            "audit_bank_identity": dict(state.audit_bank_identity),
            "audit_bank_opened_during_selection": False,
            "incumbent_control_reproduction": sentinel,
            "historical_construction_snapshot_adapter": {
                "version": ADAPTER_VERSION,
                "season": int(state.snapshot["season"]),
                "week": int(state.snapshot["week"]),
                "slate_id": slate.slate_id,
                "source_ordinal": int(state.snapshot["source_ordinal"]),
                "cell_id": cell_id,
                "construction_preset_id": preset.preset_id,
                "construction_preset_sha256": expected_preset["sha256"],
                "allocation_id": definition["allocation_id"],
                "seed_label": seed_label,
                "projection_seed": projection_seed,
                "role_seed": role_seed,
                "model_ensemble": 1,
                "worlds": cross.WORLDS_PER_BLOCK,
                "generation_snapshot_sha256": state.snapshot[
                    "generation_snapshot_sha256"
                ],
                "world_artifact_identity": dict(prepared.artifact_identity),
                "player_world_receipt": cross._array_receipt(
                    np.asarray(batch.row_draws),
                    player_ids=tuple(str(value) for value in batch.player_ids),
                ),
                "uses_target_slate_outcomes": False,
                "post_lock_data_read": False,
                "candidate_persistence": False,
                "prepared_input_cache_only": True,
            },
        })


def build_score_blind_cross_from_snapshots(
    bindings: Sequence[FrozenSnapshotBinding],
    *,
    read_exact: ReadExact,
    panel_id: str,
    code_sha: str,
    image_digest: str,
    panel_authority: cross.CrossPanelAuthority,
) -> dict[str, object]:
    """Run the exact 54-slate score-blind cross from frozen snapshots."""

    builder = FrozenSnapshotConstructionNativeBookBuilder(
        bindings, read_exact=read_exact, require_exact_panel=True
    )
    return cross.build_score_blind_cross_v1(
        builder.cross_slates(),
        builder,
        panel_id=panel_id,
        code_sha=code_sha,
        image_digest=image_digest,
        panel_authority=panel_authority,
    )


__all__ = [
    "ADAPTER_VERSION",
    "ConstructionSnapshotAdapterError",
    "FrozenSnapshotBinding",
    "FrozenSnapshotConstructionNativeBookBuilder",
    "build_score_blind_cross_from_snapshots",
]
