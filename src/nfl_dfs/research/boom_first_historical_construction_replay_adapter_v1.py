"""PIT replay adapter for the construction x allocation four-cell release.

This is a successor wrapper around
``boom_first_historical_replay_adapter_v1`` mechanics.  The predecessor is
left byte-for-byte unchanged.  The successor broadens only the explicitly
separate diagnostic panel to the exact 2023--2025 Foundry G0 slate index and
passes one exact named construction-preset receipt into every native solve.

No target-slate outcome, warehouse query, object-store read, or candidate
persistence API exists here.  The caller must inject target-outcome-null PIT
frames and immutable composite source identities.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
import hashlib
from typing import Final

import pandas as pd

from ..backtest import engine
from ..optimizer.construction_presets import resolve_construction_preset
from . import boom_first_historical_paired_v1 as paired
from . import boom_first_historical_replay_adapter_v1 as predecessor
from . import corpus_r6_construction_allocation_cross_v1 as cross


ADAPTER_VERSION: Final = (
    "boom-first-historical-construction-allocation-pit-adapter/v1"
)


class ConstructionAllocationReplayAdapterError(ValueError):
    """The injected PIT input or native construction contract differs."""


@dataclass(frozen=True, slots=True)
class ConstructionAllocationSeasonInputs:
    """Injected target-outcome-null inputs for one of 2023, 2024, or 2025."""

    season: int
    panel: pd.DataFrame
    dst_prelock: pd.DataFrame
    market_points: pd.DataFrame
    tabpfn_marginals: pd.DataFrame
    source_identity_by_slate: Mapping[str, Mapping[str, object]]
    source_manifest_by_slate: Mapping[str, Mapping[str, object]]
    lock_identity_by_slate: Mapping[str, Mapping[str, object]]
    audit_bank_identity_by_slate: Mapping[str, Mapping[str, object]]


@dataclass(frozen=True, slots=True)
class _ValidatedConstructionSeason:
    season: int
    panel: pd.DataFrame
    dst_projected: pd.DataFrame
    market_points: pd.DataFrame
    tabpfn_marginals: pd.DataFrame
    source_identity_by_slate: dict[str, Mapping[str, object]]
    source_manifest_by_slate: dict[str, Mapping[str, object]]
    lock_identity_by_slate: dict[str, Mapping[str, object]]
    audit_bank_identity_by_slate: dict[str, Mapping[str, object]]


def _dataframe_receipt(frame: pd.DataFrame) -> dict[str, object]:
    if not isinstance(frame, pd.DataFrame) or frame.columns.duplicated().any():
        raise ConstructionAllocationReplayAdapterError(
            "source frame or columns differ"
        )
    raw = frame.to_json(
        orient="split",
        date_format="iso",
        date_unit="us",
        double_precision=15,
        force_ascii=True,
    ).encode("utf-8")
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "rows": len(frame),
        "columns": [str(column) for column in frame.columns],
    }


def source_frame_receipts_v1(
    *,
    panel: pd.DataFrame,
    dst_projected: pd.DataFrame,
    market_points: pd.DataFrame,
    tabpfn_marginals: pd.DataFrame,
) -> dict[str, dict[str, object]]:
    """Return exact receipts for the four frames consumed by replay."""

    return {
        "mixed_walk_forward_panel": _dataframe_receipt(panel),
        "prelock_dst_projection": _dataframe_receipt(dst_projected),
        "common_lock_market_points": _dataframe_receipt(market_points),
        "tabpfn_marginals": _dataframe_receipt(tabpfn_marginals),
    }


def _validated_season(
    value: ConstructionAllocationSeasonInputs,
) -> _ValidatedConstructionSeason:
    if not isinstance(value, ConstructionAllocationSeasonInputs):
        raise ConstructionAllocationReplayAdapterError(
            "season input has the wrong type"
        )
    if type(value.season) is not int or value.season not in cross.PANEL_SEASONS:
        raise ConstructionAllocationReplayAdapterError(
            "cross adapter permits only 2023, 2024, and 2025"
        )
    try:
        identities = predecessor._validate_source_slates(
            value.season, value.source_identity_by_slate
        )
        expected_weeks = tuple(sorted(
            int(slate_id[-2:]) for slate_id in identities
        ))
        panel = predecessor._validate_panel(
            value.panel,
            season=value.season,
            expected_weeks=expected_weeks,
        )
        dst_projected = predecessor._validate_dst_prelock(
            value.dst_prelock,
            season=value.season,
            expected_weeks=expected_weeks,
        )
        market_points = predecessor._validate_market(
            value.market_points,
            season=value.season,
            expected_weeks=expected_weeks,
        )
        tabpfn_marginals = predecessor._validate_tabpfn(
            value.tabpfn_marginals,
            season=value.season,
        )
        manifests = {
            str(key): dict(item)
            for key, item in value.source_manifest_by_slate.items()
            if isinstance(item, Mapping)
        } if isinstance(value.source_manifest_by_slate, Mapping) else {}
        locks = predecessor._validate_source_slates(
            value.season, value.lock_identity_by_slate
        )
        audits = predecessor._validate_source_slates(
            value.season, value.audit_bank_identity_by_slate
        )
        if set(manifests) != set(identities) or set(locks) != set(
            identities
        ) or set(audits) != set(identities):
            raise ConstructionAllocationReplayAdapterError(
                "source, lock, audit, and manifest slate grids differ"
            )
        frame_receipts = source_frame_receipts_v1(
            panel=panel,
            dst_projected=dst_projected,
            market_points=market_points,
            tabpfn_marginals=tabpfn_marginals,
        )
        normalized_manifests: dict[str, Mapping[str, object]] = {}
        for slate_id in sorted(identities):
            week = int(slate_id[-2:])
            expected_manifest = cross.source_manifest_v1(
                season=value.season,
                week=week,
                slate_id=slate_id,
                input_frame_receipts=frame_receipts,
                lock_identity=locks[slate_id],
                audit_bank_identity=audits[slate_id],
            )
            actual_manifest = cross.validate_source_manifest_v1(
                manifests[slate_id],
                season=value.season,
                week=week,
                slate_id=slate_id,
                audit_bank_identity=audits[slate_id],
            )
            raw = cross.canonical_json_bytes(actual_manifest)
            identity = cross._content_identity(
                identities[slate_id], label=f"{slate_id} source"
            )
            if (
                actual_manifest != expected_manifest
                or identity["sha256"] != hashlib.sha256(raw).hexdigest()
                or identity["bytes"] != len(raw)
            ):
                raise ConstructionAllocationReplayAdapterError(
                    f"{slate_id} source manifest/frame binding differs"
                )
            normalized_manifests[slate_id] = actual_manifest
        return _ValidatedConstructionSeason(
            season=value.season,
            panel=panel,
            dst_projected=dst_projected,
            market_points=market_points,
            tabpfn_marginals=tabpfn_marginals,
            source_identity_by_slate=identities,
            source_manifest_by_slate=normalized_manifests,
            lock_identity_by_slate=locks,
            audit_bank_identity_by_slate=audits,
        )
    except (
        predecessor.BoomFirstReplayAdapterError,
        cross.ConstructionAllocationCrossError,
    ) as exc:
        raise ConstructionAllocationReplayAdapterError(str(exc)) from exc


class ConstructionAllocationReplayNativeBookBuilder(
    predecessor.ProductionReplayNativeBookBuilder
):
    """Same-model/world native builder with construction as an explicit cell."""

    def __init__(self, inputs: Sequence[ConstructionAllocationSeasonInputs]):
        supplied = tuple(inputs)
        if not supplied:
            raise ConstructionAllocationReplayAdapterError(
                "historical replay inputs are empty"
            )
        validated = [_validated_season(value) for value in supplied]
        if len({value.season for value in validated}) != len(validated):
            raise ConstructionAllocationReplayAdapterError(
                "historical replay repeats a season"
            )
        self._seasons = {value.season: value for value in validated}
        self._cache: dict[tuple[int, str, int, int], predecessor._SeedReplay] = {}

    def cross_slates(self) -> tuple[cross.CrossSlate, ...]:
        rows: list[cross.CrossSlate] = []
        for season in sorted(self._seasons):
            data = self._seasons[season]
            source = data.source_identity_by_slate
            for slate_id in sorted(source):
                rows.append(cross.CrossSlate(
                    season=season,
                    week=int(slate_id[-2:]),
                    slate_id=slate_id,
                    source_identity=source[slate_id],
                    source_manifest=data.source_manifest_by_slate[slate_id],
                    audit_bank_identity=data.audit_bank_identity_by_slate[
                        slate_id
                    ],
                ))
        return tuple(rows)

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
        if not isinstance(slate, cross.CrossSlate):
            raise ConstructionAllocationReplayAdapterError(
                "cross slate has the wrong type"
            )
        if cell_id not in cross.CELL_DEFINITION:
            raise ConstructionAllocationReplayAdapterError(
                "construction-allocation cell differs"
            )
        if slate.season not in self._seasons:
            raise ConstructionAllocationReplayAdapterError(
                "cross slate season is unavailable"
            )
        data = self._seasons[slate.season]
        if slate.slate_id not in data.source_identity_by_slate:
            raise ConstructionAllocationReplayAdapterError(
                "cross slate source is unavailable"
            )
        if (
            dict(slate.source_identity)
            != dict(data.source_identity_by_slate[slate.slate_id])
            or dict(slate.source_manifest)
            != dict(data.source_manifest_by_slate[slate.slate_id])
            or dict(slate.audit_bank_identity)
            != dict(data.audit_bank_identity_by_slate[slate.slate_id])
        ):
            raise ConstructionAllocationReplayAdapterError(
                "cross slate source/audit authority differs"
            )
        try:
            projection = predecessor._exact_int(
                projection_seed, label="projection seed"
            )
            role = predecessor._exact_int(role_seed, label="role seed")
            self._validate_seed(seed_label, projection, role)
        except predecessor.BoomFirstReplayAdapterError as exc:
            raise ConstructionAllocationReplayAdapterError(str(exc)) from exc

        definition = cross.CELL_DEFINITION[cell_id]
        preset = resolve_construction_preset(str(
            definition["construction_preset_id"]
        ))
        expected_preset = preset.receipt()
        if dict(construction_preset_receipt) != expected_preset:
            raise ConstructionAllocationReplayAdapterError(
                "construction preset receipt differs"
            )
        expected_environment = cross.cell_environments({
            "CODE_SHA": str(policy_environment.get("CODE_SHA", "")),
        })[cell_id]
        if dict(policy_environment) != expected_environment:
            raise ConstructionAllocationReplayAdapterError(
                "construction-allocation policy environment differs"
            )
        environment = self._seed_environment(
            policy_environment,
            seed_label=seed_label,
            projection_seed=projection,
            role_seed=role,
        )
        try:
            replay_seed = self._materialize_seed(
                data,
                seed_label=seed_label,
                projection_seed=projection,
                role_seed=role,
                environment=environment,
            )
        except predecessor.BoomFirstReplayAdapterError as exc:
            raise ConstructionAllocationReplayAdapterError(str(exc)) from exc

        base = replay_seed.slates[slate.slate_id].copy(deep=True)
        belief = replay_seed.belief_slates[slate.slate_id].copy(deep=True)
        captures: list[engine.CandidateBatch] = []
        try:
            with predecessor._isolated_replay_environment(environment):
                role_row_draws = engine._row_draws(
                    belief,
                    replay_seed.belief_draws,
                    env=environment,
                )
                role_world_receipt = paired.role_player_world_receipt(
                    tuple(belief.id.astype(str)), role_row_draws
                )
                engine.tail_select_lineups(
                    base,
                    base.to_dict("records"),
                    replay_seed.draws,
                    tail_line=cross.TAIL_LINE,
                    n_entries=cross.ENTRIES,
                    stack=preset.stack,
                    construction_preset_receipt=expected_preset,
                    objective_col="proj_tourney",
                    candidate_multiple=int(environment["CAND_MULT"]),
                    candidate_generation_entries=int(
                        environment["MULTISEED_CANDIDATE_ENTRY_BASIS"]
                    ),
                    n_boom_solves=int(environment["N_BOOM"]),
                    n_game_stacks=int(environment["N_GAMESTACK"]),
                    cand_log_table="",
                    cand_log_async=False,
                    cand_log_required=False,
                    belief_slate=belief,
                    belief_draws=replay_seed.belief_draws,
                    policy_env=environment,
                    candidate_capture=captures.append,
                )
        except (TypeError, ValueError) as exc:
            raise ConstructionAllocationReplayAdapterError(
                f"{slate.slate_id}/{cell_id}/{seed_label} generation failed"
            ) from exc
        if len(captures) != 1:
            raise ConstructionAllocationReplayAdapterError(
                f"{slate.slate_id}/{cell_id}/{seed_label} produced "
                f"{len(captures)} native books"
            )
        batch = captures[0]
        _, source_descriptor = cross._source_document_descriptor_v1(
            data.source_manifest_by_slate[slate.slate_id],
            source_identity=data.source_identity_by_slate[slate.slate_id],
            season=slate.season,
            week=slate.week,
            slate_id=slate.slate_id,
            audit_bank_identity=data.audit_bank_identity_by_slate[
                slate.slate_id
            ],
        )
        try:
            engine._validate_candidate_batch(batch)
            predecessor._assert_score_blind_frame(
                pd.DataFrame(batch.player_rows),
                label=f"{slate.slate_id}/{cell_id}/{seed_label} candidate rows",
            )
        except (TypeError, ValueError, predecessor.BoomFirstReplayAdapterError) as exc:
            raise ConstructionAllocationReplayAdapterError(
                "native candidate batch differs"
            ) from exc
        if batch.metadata.get("construction_preset_receipt") != expected_preset:
            raise ConstructionAllocationReplayAdapterError(
                "engine did not retain the exact construction preset receipt"
            )
        for index, lineup in enumerate(batch.candidates):
            forbidden = sorted({
                key
                for player in lineup.players
                for key in player
                if predecessor._is_outcome_field(key)
            })
            if forbidden:
                raise ConstructionAllocationReplayAdapterError(
                    f"candidate {index} contains outcome fields: "
                    + ", ".join(forbidden)
                )
        return replace(batch, metadata={
            **batch.metadata,
            "role_input_mode": "role-player-worlds",
            "role_player_world_receipt": role_world_receipt,
            "source_identity": dict(
                data.source_identity_by_slate[slate.slate_id]
            ),
            "source_document_internal_sha256": source_descriptor[
                "source_document_internal_sha256"
            ],
            "source_descriptor_sha256": source_descriptor[
                "descriptor_sha256"
            ],
            "lock_identity": dict(
                data.lock_identity_by_slate[slate.slate_id]
            ),
            "audit_bank_identity": dict(
                data.audit_bank_identity_by_slate[slate.slate_id]
            ),
            "audit_bank_opened_during_selection": False,
            "historical_construction_allocation_adapter": {
                "version": ADAPTER_VERSION,
                "season": slate.season,
                "week": slate.week,
                "slate_id": slate.slate_id,
                "cell_id": cell_id,
                "construction_preset_id": preset.preset_id,
                "construction_preset_sha256": expected_preset["sha256"],
                "allocation_id": definition["allocation_id"],
                "seed_label": seed_label,
                "projection_seed": projection,
                "role_seed": role,
                "model_ensemble": 1,
                "worlds": int(replay_seed.draws.shape[1]),
                "uses_target_slate_outcomes": False,
                "post_lock_data_read": False,
                "candidate_persistence": False,
                "predecessor_mechanics": predecessor.ADAPTER_VERSION,
            },
        })


def build_score_blind_cross_from_pit_inputs(
    inputs: Sequence[ConstructionAllocationSeasonInputs],
    *,
    panel_id: str,
    code_sha: str,
    image_digest: str,
    panel_authority: cross.CrossPanelAuthority,
) -> dict[str, object]:
    """Run the exact score-blind cross through the no-query PIT adapter."""

    builder = ConstructionAllocationReplayNativeBookBuilder(inputs)
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
    "ConstructionAllocationReplayAdapterError",
    "ConstructionAllocationReplayNativeBookBuilder",
    "ConstructionAllocationSeasonInputs",
    "build_score_blind_cross_from_pit_inputs",
    "source_frame_receipts_v1",
]
