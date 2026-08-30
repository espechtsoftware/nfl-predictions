from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import inspect
import json

import pytest

from nfl_dfs.inference import generation_exposure as exposure
from nfl_dfs.inference import prospective_cross_law_supply_trace as supply
from nfl_dfs.inference import prospective_generation_shadow_evaluation as shadow
from nfl_dfs.inference import prospective_generation_shadow_suite as generation_suite
from nfl_dfs.inference import prospective_generation_shadow_field_bridge as field_bridge
from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.inference.prospective_generation_shadow_registry import registry_document


_BLOCKS = ("R0", "R1", "R2", "R3", "R4")
_BASE_RETRIEVAL = "incumbent-cbwu-coverage-194-k80"
_CAP4_RETRIEVAL = "cap4-production-ladder-prefix-then-fill-k80"
_FAMILIES = {
    "incumbent-160-40": {"boom": 40, "leverage": 160, "role_epistemic": 12},
    "boom-first-40-160": {"boom": 160, "leverage": 40, "role_epistemic": 12},
    "cross-law-40-100-60": {
        "boom": 100, "cross_law_boom": 60, "leverage": 40,
        "role_epistemic": 12,
    },
    "boom-dose-40-360": {
        "boom": 360, "leverage": 40, "role_epistemic": 12,
    },
    "ceiling-all-boom-0-200": {"boom": 200, "role_epistemic": 12},
}
_NATIVE_FAMILIES = {
    "incumbent-160-40": {"boom": 40, "leverage": 160, "role_epistemic": 12},
    "boom-first-40-160": {"boom": 160, "leverage": 40, "role_epistemic": 12},
    "cross-law-40-100-60": {
        "boom": 100, "leverage": 40, "role_epistemic": 12,
    },
    "boom-dose-40-360": {
        "boom": 360, "leverage": 40, "role_epistemic": 12,
    },
    "ceiling-all-boom-0-200": {
        "boom": 0, "leverage": 0, "role_epistemic": 12,
    },
}
_TRANSFORM_FAMILIES = {
    "cross-law-40-100-60": {"boom:xlaw": 60},
    "ceiling-all-boom-0-200": {"boom": 200},
}


def _selected_supply_trace(
    arm: Mapping[str, object],
    roster_by_digest: Mapping[str, list[str]],
    generation_metadata: Mapping[str, object],
) -> tuple[dict[str, object], list[str]]:
    import numpy as np

    from nfl_dfs.backtest.engine import CandidateBatch
    from nfl_dfs.optimizer.lineup import Lineup

    candidates = [
        Lineup([{"id": player_id} for player_id in roster_by_digest[
            str(lineup_id).removeprefix("lineup-v1-")
        ]])
        for lineup_id in arm["candidate_lineup_ids"]
    ]
    transform_receipts = generation_metadata[
        "native_generation_transform_receipts"
    ]
    source_by_digest: dict[str, str] = {}
    cross_law_by_block: dict[str, set[str]] = {}
    for block in _BLOCKS:
        native = generation_metadata[
            "native_generation_exposure_ledgers"
        ][block]
        for row in native["rows"]:
            if row["roster_sha256"] is not None:
                source_by_digest.setdefault(str(row["roster_sha256"]), block)
        cross_law = transform_receipts[block]["cross_law_discovery"][
            "exposure_ledger"
        ]
        cross_law_by_block[block] = {
            str(row["roster_sha256"])
            for row in cross_law["rows"]
            if row["roster_sha256"] is not None
        }
        for digest in cross_law_by_block[block]:
            source_by_digest.setdefault(digest, block)
    candidate_sources: list[str] = []
    all_tags = {}
    for lineup in candidates:
        digest = supply._roster_sha256(lineup)
        source = source_by_digest[digest]
        candidate_sources.append(source)
        tags = [f"candidate_seed:{source}"]
        if digest in cross_law_by_block[source]:
            tags.append(supply.FAMILY)
        all_tags[lineup.ids] = tuple(tags)
    player_ids = tuple(f"p{value:03d}" for value in range(180))
    batch = CandidateBatch(
        candidates=tuple(candidates),
        candidate_totals=np.zeros((len(candidates), 1), dtype=np.float32),
        player_ids=player_ids,
        player_rows=tuple({"id": value} for value in player_ids),
        row_draws=np.zeros((len(player_ids), 1), dtype=np.float32),
        all_tags=all_tags,
        metadata={"candidate_source_blocks": candidate_sources},
    )
    trace = supply.build_selected_supply_trace(
        batch,
        candidates[:80],
        {value: value for value in player_ids},
        transform_receipts,
    )
    return trace, candidate_sources


def _native_input_receipts(player_count: int = 180) -> dict[str, object]:
    candidate = {
        "sha256": shadow.canonical_sha256_v1(
            {"fixture": "candidate-input", "players": player_count}
        ),
        "rows": player_count,
        "columns": ["id"],
    }
    role = {
        "sha256": shadow.canonical_sha256_v1(
            {"fixture": "role-candidate-input", "players": player_count}
        ),
        "rows": player_count,
        "columns": ["id"],
    }
    construction = ADOPTED_CLASSIC_POLICY.construction_preset().receipt()
    return {
        block: {
            "model_version": "fixture-model-v1",
            "role_model_version": "fixture-role-model-v1",
            "candidate_input_receipt": dict(candidate),
            "role_candidate_input_receipt": dict(role),
            "construction_preset_receipt": dict(construction),
        }
        for block in _BLOCKS
    }


def _paired_native_input_authority(
    generation_metadata_by_arm: Mapping[str, Mapping[str, object]],
    *,
    player_count: int,
) -> dict[str, object]:
    reference = shadow.native_input_source_projection(
        generation_metadata_by_arm[shadow.ARM_ORDER[0]][
            "native_generation_receipts"
        ][_BLOCKS[0]],
        label="fixture native input/source receipt",
    )
    reference_sha256 = shadow.canonical_sha256_v1(reference)
    player_ids = [f"p{value:03d}" for value in range(player_count)]
    construction = reference["construction_preset_receipt"]
    body: dict[str, object] = {
        "schema_version": (
            "prospective-generation-paired-native-input-authority/v1"
        ),
        "arm_order": list(shadow.ARM_ORDER),
        "block_labels": list(_BLOCKS),
        "native_source_projection": reference,
        "native_source_projection_sha256": reference_sha256,
        "native_source_projection_sha256_by_arm": {
            arm_id: {
                block: reference_sha256 for block in _BLOCKS
            }
            for arm_id in shadow.ARM_ORDER
        },
        "effective_player_source_identity": {
            "candidate_input_receipt": reference[
                "candidate_input_receipt"
            ],
            "role_candidate_input_receipt": reference[
                "role_candidate_input_receipt"
            ],
            "player_count": player_count,
            "internal_player_id_order_sha256": shadow.canonical_sha256_v1(
                player_ids
            ),
            "artifact_player_id_order_sha256": shadow.canonical_sha256_v1(
                player_ids
            ),
        },
        "effective_model_source_identity": {
            "model_version": reference["model_version"],
            "role_model_version": reference["role_model_version"],
        },
        "effective_construction_source_identity": {
            "effective_id": construction["effective_id"],
            "sha256": construction["sha256"],
        },
        "all_arm_blocks_byte_identical_inputs": True,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    body["authority_sha256"] = shadow.canonical_sha256_v1(body)
    return shadow.validate_paired_native_input_authority(
        body,
        expected_arm_order=shadow.ARM_ORDER,
        expected_block_labels=_BLOCKS,
    )


def _player_identity_bridge(player_count: int) -> list[dict[str, object]]:
    positions = (
        ["QB"] * 20
        + ["RB"] * 40
        + ["WR"] * 60
        + ["TE"] * 20
        + ["WR"] * 20
        + ["DST"] * 20
    )
    return [{
        "internal_player_id": f"p{ordinal:03d}",
        "dk_draftable_id": f"p{ordinal:03d}",
        "gsis_id": (
            None if positions[ordinal] == "DST" else f"gsis-{ordinal:03d}"
        ),
        "position": positions[ordinal],
        "team": f"T{ordinal % 8}",
        "dst_team": (
            f"T{ordinal % 8}" if positions[ordinal] == "DST" else None
        ),
        "salary": 5_000,
    } for ordinal in range(player_count)]


def _identity(
    label: str, *, generation: int = 1, sha256: str | None = None,
    byte_count: int | None = None,
) -> dict[str, object]:
    return {
        "uri": f"gs://fixture-authority/prospective/{label}.json",
        "generation": str(generation),
        "sha256": sha256 or shadow.canonical_sha256_v1({"label": label}),
        "bytes": byte_count or 100 + len(label),
    }


def _artifact(
    label: str, frozen_at: datetime, storage_created_at: datetime, *,
    identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return shadow.build_create_once_artifact_v1(
        identity=identity or _identity(label), frozen_at=frozen_at,
        storage_created_at=storage_created_at,
    )


def _modeled(offset: int = 0) -> dict[str, dict[str, int]]:
    return {
        "20": {"194": 100_000 + offset, "210": 50_000, "220": 20_000},
        "40": {"194": 200_000 + offset, "210": 90_000, "220": 40_000},
        "80": {"194": 300_000 + offset, "210": 140_000, "220": 60_000},
    }


def _arm(
    arm_id: str, *, frozen_at: datetime, storage_created_at: datetime,
    simulation_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    world_identity: Mapping[str, object], crossing_sha256: str,
) -> tuple[
    dict[str, object], dict[str, list[str]], dict[str, object]
]:
    ledgers: dict[str, dict[str, object]] = {}
    native_ledgers: dict[str, dict[str, object]] = {}
    transform_receipts: dict[str, dict[str, object]] = {}
    roster_by_digest: dict[str, list[str]] = {}
    ordered_digests: list[str] = []
    transform_digests: list[str] = []
    arm_ordinal = shadow.ARM_ORDER.index(arm_id)
    for block_ordinal, block in enumerate(_BLOCKS):
        builder = exposure.SolveExposureLedger(source_label=f"{arm_id}:{block}")
        attempt_key = arm_ordinal * 100_000 + block_ordinal * 10_000
        for family_ordinal, (family, count) in enumerate(
            sorted(_NATIVE_FAMILIES[arm_id].items())
        ):
            for ordinal in range(count):
                key = attempt_key + family_ordinal * 1_000 + ordinal
                roster = _fixture_roster(key)
                row = builder.record(
                    family=family, requested_ordinal=ordinal, world_id=ordinal,
                    duration_seconds=0.01, status="new", roster_ids=roster,
                )
                digest = str(row["roster_sha256"])
                roster_by_digest[digest] = roster
                ordered_digests.append(digest)
        native = builder.finalize(
            expected_requests_by_family=_NATIVE_FAMILIES[arm_id]
        )
        native_ledgers[block] = native
        transform_families = _TRANSFORM_FAMILIES.get(arm_id)
        transform_ledger = None
        block_transform_receipts: dict[str, object] = {}
        if transform_families is not None:
            transform_key = (
                "cross_law_discovery"
                if arm_id == "cross-law-40-100-60"
                else "all_boom_ceiling"
            )
            transform_builder = exposure.SolveExposureLedger(
                source_label=f"{block.lower()}-{transform_key}"
            )
            for family_ordinal, (family, count) in enumerate(
                sorted(transform_families.items())
            ):
                for ordinal in range(count):
                    key = attempt_key + 5_000 + family_ordinal * 1_000 + ordinal
                    roster = _fixture_roster(key)
                    row = transform_builder.record(
                        family=family, requested_ordinal=ordinal,
                        world_id=ordinal, duration_seconds=0.02,
                        status="new", roster_ids=roster,
                    )
                    digest = str(row["roster_sha256"])
                    roster_by_digest[digest] = roster
                    ordered_digests.append(digest)
                    transform_digests.append(digest)
            transform_ledger = transform_builder.finalize(
                expected_requests_by_family=transform_families
            )
            outer: dict[str, object] = {
                (
                    "exposure_ledger"
                    if transform_key == "cross_law_discovery"
                    else "solve_exposure_ledger"
                ): transform_ledger,
                "uses_realized_outcomes": False,
            }
            if transform_key == "cross_law_discovery":
                outer["production_influence_trace_sha256"] = (
                    shadow.canonical_sha256_v1(
                        {"influence": block, "fixture": True}
                    )
                )
            outer["receipt_sha256"] = shadow.canonical_sha256_v1(outer)
            block_transform_receipts[transform_key] = outer
        transform_receipts[block] = block_transform_receipts
        ledgers[block] = {"native": native, "transform": transform_ledger}
    if arm_id == "cross-law-40-100-60":
        # Keep one genuine discovery candidate in every selected prefix so
        # decoded-artifact tests exercise a nonzero semantic reopen.
        first_discovery = transform_digests[0]
        ordered_digests = [
            first_discovery,
            *(digest for digest in ordered_digests if digest != first_discovery),
        ]
    candidates = [
        f"lineup-v1-{digest}" for digest in ordered_digests[:160]
    ]
    kwargs: dict[str, object] = {}
    if arm_id in {"incumbent-160-40", "boom-first-40-160"}:
        kwargs = {
            "cap4_book_lineup_ids": candidates[40:120],
            "cap4_modeled_probability_ppm": _modeled(10_000),
            "cap4_book_artifact": _artifact(
                f"{arm_id}-cap4", frozen_at, storage_created_at,
                identity=world_identity,
            ),
        }
    freeze = shadow.build_arm_freeze_v1(
        arm_id=arm_id, population_label=f"population:{arm_id}",
        cap_label=_BASE_RETRIEVAL, operational_k=80,
        candidate_lineup_ids=candidates, book_lineup_ids=candidates[:80],
        modeled_probability_ppm=_modeled(),
        exposure_ledgers_by_block=ledgers,
        artifacts={
            name: _artifact(
                f"{arm_id}-{name}", frozen_at, storage_created_at,
                identity=world_identity,
            )
            for name in ("book", "candidate_pool", "exposure_ledger", "world")
        },
        shared_simulation_identity=simulation_identity,
        untouched_selection_bank_identity=selection_identity,
        seed_crossing_sha256=crossing_sha256, **kwargs,
    )
    return freeze, roster_by_digest, {
        "native_generation_receipts": _native_input_receipts(),
        "native_generation_exposure_ledgers": native_ledgers,
        "native_generation_transform_receipts": transform_receipts,
    }


def _gcs_receipt(
    identity: Mapping[str, object], created_at: datetime,
) -> dict[str, object]:
    return {
        **identity, "generation": int(str(identity["generation"])),
        "gcs_time_created": created_at.isoformat(),
        "precedes_slate_lock": True, "create_only": True,
    }


def _world_receipt(
    identity: Mapping[str, object], created_at: datetime,
) -> dict[str, object]:
    return {
        **identity, "generation": int(str(identity["generation"])),
        "gcs_time_created": created_at.isoformat(), "create_only": True,
    }


def _array_receipt(label: str, shape: list[int]) -> dict[str, object]:
    return {
        "sha256": shadow.canonical_sha256_v1({"array": label, "shape": shape}),
        "dtype": "<f4", "shape": shape,
        "bytes": 4 * shape[0] * shape[1],
    }


def _fixture_roster(key: int) -> list[str]:
    """Return one globally unique, legal nine-player fixture roster."""

    digit0 = key % 20
    offsets = [
        digit0,
        ((key // 20) + digit0) % 20,
        ((key // 400) + 3 * digit0) % 20,
        ((key // 8_000) + 7 * digit0) % 20,
        ((key // 160_000) + 9 * digit0) % 20,
        ((key // 20) + 11 * digit0 + 3) % 20,
        ((key // 400) + 13 * digit0 + 5) % 20,
        ((key // 8_000) + 17 * digit0 + 7) % 20,
        (digit0 + 1) % 20,
    ]
    return [
        f"p{slot * 20 + offsets[slot]:03d}" for slot in range(9)
    ]


def _suite_diagnostics(offset: float = 0.0) -> dict[str, object]:
    return {
        "probabilities_are_descriptive_not_calibrated": True,
        "coverage_line_label": "optimistic-194",
        "prefixes": {
            str(prefix): {
                "simulated_mean_max": 180.0 + prefix / 10,
                "simulated_p_max_at_least": {
                    str(threshold): max(0.0, min(
                        1.0, (1.0 if threshold <= 220 else 0.0) + offset
                    ))
                    for threshold in shadow.REALIZED_THRESHOLDS_DK
                },
            }
            for prefix in shadow.PREFIX_SIZES
        },
        "selected_family_counts": {}, "candidate_family_tail_rates": {},
    }


def _retrieval_diagnostics(offset: float = 0.0) -> dict[str, object]:
    return {
        "probabilities_are_in_sample_descriptive_not_calibrated": True,
        "simulated_mean_book_max": 190.0,
        "simulated_p_book_max_at_least": {
            str(threshold): max(0.0, min(
                1.0, (1.0 if threshold <= 220 else 0.0) + offset
            ))
            for threshold in shadow.REALIZED_THRESHOLDS_DK
        },
    }


def _audit_diagnostics_from_modeled(
    modeled: Mapping[str, Mapping[str, int]],
) -> dict[str, object]:
    return {
        "probabilities_are_out_of_selection_sample_audit_estimates": True,
        "audit_world_count": 10_000,
        "used_for_selection": False,
        "prefixes": {
            str(prefix): {
                "simulated_mean_max": 180.0 + prefix / 10,
                "simulated_p_max_at_least": {
                    str(threshold): (
                        modeled[str(prefix)].get(str(threshold), 0)
                        / shadow.PROBABILITY_SCALE
                    )
                    for threshold in shadow.REALIZED_THRESHOLDS_DK
                },
            }
            for prefix in shadow.PREFIX_SIZES
        },
    }


def _audit_diagnostics(offset_ppm: int = 0) -> dict[str, object]:
    return _audit_diagnostics_from_modeled(_modeled(offset_ppm))


def _suite_authority(
    *, week: int, lock_at: datetime, generated_at: datetime,
    world_created_at: datetime, manifest_created_at: datetime,
    terminal_created_at: datetime, arms: list[dict[str, object]],
    roster_by_arm: Mapping[str, Mapping[str, list[str]]],
    generation_metadata_by_arm: Mapping[str, Mapping[str, object]],
    audit_identity: Mapping[str, object],
    shared_world_receipt: Mapping[str, object] | None = None,
    audit_world_receipt: Mapping[str, object] | None = None,
) -> dict[str, object]:
    retained_shared_world_receipt = (
        dict(shared_world_receipt)
        if shared_world_receipt is not None
        else _array_receipt("shared-worlds", [180, 50_000])
    )
    player_count = int(retained_shared_world_receipt["shape"][0])
    paired_native_input_authority = _paired_native_input_authority(
        generation_metadata_by_arm,
        player_count=player_count,
    )
    reference_native_receipt = generation_metadata_by_arm[
        shadow.ARM_ORDER[0]
    ]["native_generation_receipts"][_BLOCKS[0]]
    audit_input_binding = generation_suite.build_independent_audit_input_binding(
        paired_native_input_authority=paired_native_input_authority,
        observed_model_version=str(reference_native_receipt["model_version"]),
        observed_candidate_input_receipt=reference_native_receipt[
            "candidate_input_receipt"
        ],
        observed_internal_player_ids=[
            f"p{value:03d}" for value in range(player_count)
        ],
    )
    memberships: dict[str, dict[str, list[list[str]]]] = {
        str(prefix): {} for prefix in shadow.PREFIX_SIZES
    }
    arm_receipts: dict[str, object] = {}
    retrieval_populations: dict[str, object] = {}
    for arm in arms:
        arm_id = str(arm["arm_id"])
        rosters = [
            roster_by_arm[arm_id][str(lineup).removeprefix("lineup-v1-")]
            for lineup in arm["book_lineup_ids"]
        ]
        for prefix in shadow.PREFIX_SIZES:
            memberships[str(prefix)][arm_id] = rosters[:prefix]
        transform = arm_id in {
            "cross-law-40-100-60", "ceiling-all-boom-0-200"
        }
        work = {}
        transform_hashes: dict[str, dict[str, str]] = {}
        for block in _BLOCKS:
            ledger_block = arm["exposure_ledgers_by_block"][block]
            ledger = ledger_block["native"]
            transform_ledger = ledger_block["transform"]
            transform_digest = (
                None if transform_ledger is None
                else transform_ledger["ledger_sha256"]
            )
            work[block] = {
                "unit": "one-10000-world-generation-block",
                "native_ledger_sha256": ledger["ledger_sha256"],
                "native_expected_requests_by_family": ledger[
                    "expected_requests_by_family"
                ],
                "native_status_counts": ledger["status_counts"],
                "native_duration_seconds_by_family": ledger[
                    "duration_seconds_by_family"
                ],
                "native_total_duration_seconds": ledger["total_duration_seconds"],
                "transform_ledger_sha256": (
                    transform_digest
                ),
                "transform_expected_requests_by_family": {},
                "transform_status_counts": (
                    {} if transform_ledger is None
                    else transform_ledger["status_counts"]
                ),
                "transform_duration_seconds_by_family": (
                    {} if transform_ledger is None
                    else transform_ledger["duration_seconds_by_family"]
                ),
                "requested_composite_core": (
                    400 if arm_id == "boom-dose-40-360" else 200
                ),
                "requested_role": 12,
                "natural_uniqueness_collisions_failures_and_runtime_receipted": True,
            }
            work[block]["transform_expected_requests_by_family"] = (
                {} if transform_ledger is None
                else transform_ledger["expected_requests_by_family"]
            )
            transform_hashes[block] = (
                {
                    (
                        "cross_law_discovery"
                        if arm_id == "cross-law-40-100-60"
                        else "all_boom_ceiling"
                    ): str(
                        generation_metadata_by_arm[arm_id][
                            "native_generation_transform_receipts"
                        ][block][
                            (
                                "cross_law_discovery"
                                if arm_id == "cross-law-40-100-60"
                                else "all_boom_ceiling"
                            )
                        ]["receipt_sha256"]
                    )
                }
                if transform else {}
            )
        candidate_rosters = [
            roster_by_arm[arm_id][str(lineup).removeprefix("lineup-v1-")]
            for lineup in arm["candidate_lineup_ids"]
        ]
        arm_receipts[arm_id] = {
            "candidate_count": len(arm["candidate_lineup_ids"]),
            "selected_count": 80,
            "candidate_order_sha256": shadow.canonical_sha256_v1(
                candidate_rosters
            ),
            "selected_order_sha256": shadow.canonical_sha256_v1(rosters),
            "candidate_matrix_receipt": _array_receipt(
                f"{arm_id}-candidate-matrix",
                [len(arm["candidate_lineup_ids"]), 50_000],
            ),
            "native_exposure_ledger_sha256": {
                block: arm["exposure_ledgers_by_block"][block]["native"][
                    "ledger_sha256"
                ]
                for block in _BLOCKS
            },
            "native_transform_receipt_sha256": transform_hashes,
            "per_block_requested_work": work,
            "simulated_diagnostics": _suite_diagnostics(),
            "independent_audit_diagnostics": _audit_diagnostics_from_modeled(
                arm["modeled_probability_ppm"]
            ),
        }
        if arm_id in {"incumbent-160-40", "boom-first-40-160"}:
            candidates = list(arm["candidate_lineup_ids"])
            retrievals = {}
            for retrieval_id, selected in (
                (_BASE_RETRIEVAL, list(arm["book_lineup_ids"])),
                (_CAP4_RETRIEVAL,
                 list(arm["retrieval_interaction"]["book_lineup_ids"])),
            ):
                retrievals[retrieval_id] = {
                    "selected_lineup_ids": selected,
                    "selected_lineup_ids_sha256": shadow.canonical_sha256_v1(
                        selected
                    ),
                    "uses_realized_outcomes": False,
                    "post_lock_data_read": False,
                    "simulated_diagnostics": _retrieval_diagnostics(
                        0.01 if retrieval_id == _CAP4_RETRIEVAL else 0.0
                    ),
                    "independent_audit_diagnostics": (
                        _audit_diagnostics_from_modeled(
                            arm["retrieval_interaction"][
                                "modeled_probability_ppm"
                            ]
                            if retrieval_id == _CAP4_RETRIEVAL
                            else arm["modeled_probability_ppm"]
                        )
                    ),
                }
            retrieval_populations[arm_id] = {
                "population_id": arm_id, "candidate_count": len(candidates),
                "candidate_lineup_ids": candidates,
                "candidate_lineup_ids_sha256": shadow.canonical_sha256_v1(
                    candidates
                ),
                "retrievals": retrievals,
                "same_candidate_pool_for_both_official_retrievals": True,
                "candidate_solves_requested_by_crossing": 0,
            }
    cross_law_arm = next(
        arm for arm in arms
        if arm["arm_id"] == "cross-law-40-100-60"
    )
    selected_supply_trace, candidate_source_blocks = _selected_supply_trace(
        cross_law_arm,
        roster_by_arm["cross-law-40-100-60"],
        generation_metadata_by_arm["cross-law-40-100-60"],
    )
    generation_metadata_by_arm["cross-law-40-100-60"][
        "candidate_source_blocks"
    ] = candidate_source_blocks
    for arm_id in shadow.ARM_ORDER:
        arm_receipts[arm_id][
            "cross_law_selected_supply_trace_sha256"
        ] = (
            selected_supply_trace["trace_sha256"]
            if arm_id == "cross-law-40-100-60"
            else None
        )
    retained_audit_world_receipt = audit_world_receipt or _array_receipt(
        "audit-worlds", [player_count, 10_000]
    )
    crossing = {
        "schema_version": "prospective-generation-retrieval-crossing/v1",
        "population_order": ["incumbent-160-40", "boom-first-40-160"],
        "retrieval_order": [_BASE_RETRIEVAL, _CAP4_RETRIEVAL],
        "cell_order": [], "entry_budget": 80, "shared_selection_bank": {},
        "independent_score_only_audit_bank": {
            "player_world_matrix_receipt": retained_audit_world_receipt,
            "world_count": 10_000,
            "used_for_selection": False,
            "distinct_from_every_selection_block": True,
        },
        "selection_laws": {},
        "report_thresholds": list(shadow.REALIZED_THRESHOLDS_DK),
        "populations": retrieval_populations,
        "candidate_generation_reused": True,
        "candidate_solves_requested_by_crossing": 0,
        "shared_generation_exposure_ledger_modified": False,
        "selector_runtime_seconds": 0.1,
        "uses_realized_outcomes": False, "post_lock_data_read": False,
        "historical_scoring_performed": False, "production_enabled": False,
        "science_sha256_excluding_runtime": shadow.canonical_sha256_v1(
            {"fixture": "retrieval-science"}
        ),
    }
    crossing["receipt_sha256"] = shadow.canonical_sha256_v1(crossing)
    audit_bank = {
        "schema_version": shadow.AUDIT_BANK_SCHEMA,
        "world_seed": 2_026_083_001, "world_count": 10_000,
        "model_version": "fixture-model-v1",
        "player_order_sha256": shadow.canonical_sha256_v1(
            [f"p{value:03d}" for value in range(player_count)]
        ),
        "input_binding": audit_input_binding,
        "input_binding_sha256": audit_input_binding["binding_sha256"],
        "world_bank_receipt": retained_audit_world_receipt,
        "candidate_solves_run": 0,
        "used_for_selection": False, "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    audit_bank["receipt_sha256"] = shadow.canonical_sha256_v1(audit_bank)
    prelock = {
        "schema_version": "prospective-generation-multiarm-prelock/v2",
        "suite_version": "prospective-generation-shadow-suite-v2",
        "registry": registry_document(), "entries": 80,
        "prefixes": list(shadow.PREFIX_SIZES),
        "thresholds": list(shadow.REALIZED_THRESHOLDS_DK),
        "player_worlds_identical_across_all_arms": True,
        "player_worlds_receipt": retained_shared_world_receipt,
        "independent_audit_world_bank": audit_bank,
        "independent_audit_input_binding": audit_input_binding,
        "independent_audit_input_binding_sha256": audit_input_binding[
            "binding_sha256"
        ],
        "audit_world_bank_distinct_from_all_five_selection_blocks": True,
        "audit_world_bank_used_for_selection": False,
        "arm_receipts": arm_receipts,
        "paired_native_input_authority": paired_native_input_authority,
        "paired_native_input_authority_sha256": (
            paired_native_input_authority["authority_sha256"]
        ),
        "cross_law_selected_supply_trace": selected_supply_trace,
        "cross_law_selected_supply_trace_sha256": (
            selected_supply_trace["trace_sha256"]
        ),
        "generation_retrieval_crossing": crossing,
        "generation_retrieval_crossing_sha256": crossing["receipt_sha256"],
        "memberships": memberships,
        "memberships_sha256": shadow.canonical_sha256_v1(memberships),
        "uses_realized_outcomes": False, "post_lock_data_read": False,
        "production_enabled": False,
    }
    prelock["receipt_sha256"] = shadow.canonical_sha256_v1(prelock)
    code_sha = "a" * 40
    context = {
        "suite_version": "prospective-generation-shadow-suite-v2",
        "run_id": f"fixture-week-{week}", "season": 2026, "week": week,
        "draft_group_id": 1000 + week,
        "slate_lock_at": lock_at.isoformat(), "code_sha": code_sha,
        "image_source_commit_sha": code_sha,
        "image_uri": f"us-docker.pkg.dev/fixture/shadow@sha256:{'b' * 64}",
        "registry_sha256": registry_document()["registry_sha256"],
    }
    worlds = {
        str(arm["arm_id"]): _world_receipt(
            arm["artifacts"]["world"]["identity"], world_created_at
        )
        for arm in arms
    }
    audit_world = _world_receipt(audit_identity, world_created_at)
    discovery_worlds = {
        block: _world_receipt(
            _identity(
                f"week-{week}-cross-law-{block}-world",
                generation=6000 + week * 10 + ordinal,
            ),
            world_created_at,
        )
        for ordinal, block in enumerate(_BLOCKS)
    }
    def _partial(receipt: Mapping[str, object]) -> dict[str, object]:
        return {
            key: receipt[key] for key in (
                "uri", "generation", "sha256", "gcs_time_created", "create_only"
            )
        }
    persistence = {
        "schema_version": "prospective-cross-law-persisted-world-binding/v1",
        "base_selection_world_artifact": _partial(
            worlds["cross-law-40-100-60"]
        ),
        "discovery_generation_world_artifacts": {
            block: _partial(discovery_worlds[block]) for block in _BLOCKS
        },
        "independent_audit_world_artifact": _partial(audit_world),
        "per_block_influence_trace_sha256": {
            block: generation_metadata_by_arm["cross-law-40-100-60"][
                "native_generation_transform_receipts"
            ][block]["cross_law_discovery"][
                "production_influence_trace_sha256"
            ] for block in _BLOCKS
        },
        "selected_supply_trace_sha256": selected_supply_trace[
            "trace_sha256"
        ],
        "discovery_worlds_used_for_generation_only": True,
        "all_selection_scores_from_untouched_base_bank": True,
        "audit_worlds_used_for_selection": False,
        "all_objects_create_only_and_prelock": True,
        "uses_realized_outcomes": False,
    }
    persistence["binding_sha256"] = shadow.canonical_sha256_v1(persistence)
    player_identity_bridge = _player_identity_bridge(player_count)
    manifest = {
        "schema_version": "prospective-generation-shadow-manifest/v2",
        **context, "generated_at": generated_at.isoformat(),
        "prelock_receipt": prelock, "world_artifacts": worlds,
        "player_identity_bridge": player_identity_bridge,
        "player_identity_bridge_sha256": shadow.canonical_sha256_v1(
            player_identity_bridge
        ),
        "independent_audit_world_artifact": audit_world,
        "independent_audit_input_binding": audit_input_binding,
        "independent_audit_input_binding_sha256": audit_input_binding[
            "binding_sha256"
        ],
        "cross_law_discovery_world_artifacts": discovery_worlds,
        "cross_law_persistence_binding": persistence,
        "uses_realized_outcomes": False, "post_lock_data_read": False,
        "production_enabled": False,
    }
    manifest_identity = _identity(
        f"week-{week}-manifest", generation=7000 + week,
        sha256=shadow.canonical_sha256_v1(manifest),
        byte_count=len(shadow.canonical_json_bytes_v1(manifest)),
    )
    terminal = {
        "schema_version": "prospective-generation-shadow-terminal/v2",
        "complete": True, **context,
        "manifest": _gcs_receipt(manifest_identity, manifest_created_at),
        "world_artifacts": worlds,
        "independent_audit_world_artifact": audit_world,
        "cross_law_discovery_world_artifacts": discovery_worlds,
        "cross_law_persistence_binding": persistence,
        "cross_law_selected_supply_trace": selected_supply_trace,
        "cross_law_selected_supply_trace_sha256": selected_supply_trace[
            "trace_sha256"
        ],
        "paired_native_input_authority": paired_native_input_authority,
        "paired_native_input_authority_sha256": (
            paired_native_input_authority["authority_sha256"]
        ),
        "independent_audit_input_binding": audit_input_binding,
        "independent_audit_input_binding_sha256": audit_input_binding[
            "binding_sha256"
        ],
        "memberships_sha256": prelock["memberships_sha256"],
        "generation_retrieval_crossing_sha256": crossing["receipt_sha256"],
        "uses_realized_outcomes": False, "post_lock_data_read": False,
        "production_enabled": False,
    }
    terminal["terminal_receipt_sha256"] = shadow.canonical_sha256_v1(terminal)
    terminal_identity = _identity(
        f"week-{week}-terminal", generation=8000 + week,
        sha256=shadow.canonical_sha256_v1(terminal),
        byte_count=len(shadow.canonical_json_bytes_v1(terminal)),
    )
    return shadow.build_suite_authority_v1(
        manifest=manifest, terminal=terminal,
        terminal_receipt=_gcs_receipt(terminal_identity, terminal_created_at),
    )


def _raw_score_identity(
    *, week: int, slate_id: str, captured_at: datetime,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    score_rows = sorted(rows, key=lambda row: str(row["lineup_id"]))
    payload = {
        "schema_version": shadow.REALIZED_SCORE_SOURCE_SCHEMA,
        "season": 2026, "week": week, "slate_id": slate_id,
        "captured_at": captured_at.isoformat(),
        "producer_class": "independent-realized-lineup-score-source",
        "independent_from_generation": True,
        "terminal_prelock_root_binding_present": False,
        "lineup_count": len(score_rows), "lineup_rows": score_rows,
        "lineup_rows_sha256": shadow.canonical_sha256_v1(score_rows),
    }
    return {
        **_identity(f"scores-{week}", generation=8500 + week),
        "uri": f"gs://fixture-outcomes/scores/week-{week}.json",
        "sha256": shadow.canonical_sha256_v1(payload),
        "bytes": len(shadow.canonical_json_bytes_v1(payload)),
    }


def _raw_outcome_identity(
    *, week: int, slate_id: str, captured_at: datetime,
    rows: list[dict[str, object]], score_identity: Mapping[str, object],
) -> dict[str, object]:
    capture = {
        "status": "unavailable-raw-score-only",
        "evidence_scope": "raw-score-only-no-contest-ev",
        "complete_field_rank_claim_allowed": False,
        "contest_ev_claim_allowed": False,
        "allocation_recommendation_allowed": False, "complete": False,
    }
    payload = {
        "schema_version": "prospective-generation-shadow-outcome-source-content/v2",
        "season": 2026, "week": week, "slate_id": slate_id,
        "captured_at": captured_at.isoformat(), "field_metrics_available": False,
        "realized_score_source_identity": dict(score_identity),
        "contest_field_capture": capture,
        "lineup_rows": sorted(rows, key=lambda row: str(row["lineup_id"])),
    }
    return {
        **_identity(f"outcome-{week}", generation=9000 + week),
        "uri": f"gs://fixture-outcomes/realized/week-{week}.json",
        "sha256": shadow.canonical_sha256_v1(payload),
        "bytes": len(shadow.canonical_json_bytes_v1(payload)),
    }


def _case(week: int = 1, *, include_internal: bool = False):
    week1_lock = datetime(2026, 9, 13, 17, tzinfo=timezone.utc)
    lock_at = week1_lock + timedelta(days=7 * (week - 1))
    generated = lock_at - timedelta(hours=3)
    worlds_created = lock_at - timedelta(hours=2, minutes=45)
    manifest_created = lock_at - timedelta(hours=2, minutes=30)
    terminal_created = lock_at - timedelta(hours=2, minutes=20)
    root_frozen = lock_at - timedelta(hours=2)
    prereg = shadow.build_preregistration_v1(
        registered_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        week1_lock_at=week1_lock,
    )
    audit = _identity(f"week-{week}-audit")
    fit = {f"fit{i}": _identity(f"week-{week}-fit-{i}") for i in range(2)}
    world = {
        f"world{i}": _identity(f"week-{week}-world-{i}") for i in range(2)
    }
    crossed = {
        f"fit{i}--world{j}": _identity(f"week-{week}-cross-{i}-{j}")
        for i in range(2) for j in range(2)
    }
    crossing = shadow.build_seed_crossing_v1(
        fit_seed_identities=fit, world_seed_identities=world,
        crossed_slot_identities=crossed,
    )
    world_ids = {
        arm: _identity(f"week-{week}-{arm}-world", generation=100 + week)
        for arm in shadow.ARM_ORDER
    }
    simulation = world_ids[shadow.ARM_ORDER[0]]
    selection = world_ids[shadow.ARM_ORDER[0]]
    pairs = [
        _arm(
            arm, frozen_at=generated, storage_created_at=worlds_created,
            simulation_identity=simulation, selection_identity=selection,
            world_identity=world_ids[arm],
            crossing_sha256=str(crossing["seed_crossing_sha256"]),
        )
        for arm in shadow.ARM_ORDER
    ]
    arms = [pair[0] for pair in pairs]
    shared_draws = None
    shared_world_receipt = None
    audit_draws = None
    audit_world_receipt = None
    if include_internal:
        import numpy as np
        from nfl_dfs.inference.prospective_boom_first import (
            _array_receipt as _real_array_receipt,
        )

        shared_draws = np.full((180, 50_000), 25.0, dtype=np.float32)
        shared_world_receipt = _real_array_receipt(shared_draws)
        audit_draws = np.full((180, 10_000), 24.0, dtype=np.float32)
        audit_world_receipt = _real_array_receipt(audit_draws)
        audit_projection = {
            "player_ids": [f"p{value:03d}" for value in range(180)],
            "player_draws": audit_draws,
        }
        for freeze, roster_by_digest, _metadata in pairs:
            candidate_projection = {
                "candidate_rosters": [
                    roster_by_digest[
                        str(lineup_id).removeprefix("lineup-v1-")
                    ]
                    for lineup_id in freeze["candidate_lineup_ids"]
                ],
                **audit_projection,
            }
            base_modeled = shadow._decoded_modeled_probability_ppm(
                candidate_projection,
                freeze["book_lineup_ids"],
                arm_id=str(freeze["arm_id"]),
                label="fixture independent audit",
                score_world_projection=audit_projection,
            )
            freeze["modeled_probability_ppm"] = base_modeled
            freeze["modeled_probability_sha256"] = (
                shadow.canonical_sha256_v1(base_modeled)
            )
            interaction = freeze["retrieval_interaction"]
            if interaction is not None:
                cap_modeled = shadow._decoded_modeled_probability_ppm(
                    candidate_projection,
                    interaction["book_lineup_ids"],
                    arm_id=str(freeze["arm_id"]),
                    label="fixture cap independent audit",
                    score_world_projection=audit_projection,
                )
                interaction["modeled_probability_ppm"] = cap_modeled
                interaction["modeled_probability_sha256"] = (
                    shadow.canonical_sha256_v1(cap_modeled)
                )
            _rehash(freeze, "arm_freeze_sha256")
    suite = _suite_authority(
        week=week, lock_at=lock_at, generated_at=generated,
        world_created_at=worlds_created,
        manifest_created_at=manifest_created,
        terminal_created_at=terminal_created, arms=arms,
        roster_by_arm={str(pair[0]["arm_id"]): pair[1] for pair in pairs},
        generation_metadata_by_arm={
            str(pair[0]["arm_id"]): pair[2] for pair in pairs
        },
        audit_identity=audit, shared_world_receipt=shared_world_receipt,
        audit_world_receipt=audit_world_receipt,
    )
    root = shadow.build_terminal_prelock_root_v1(
        preregistration=prereg, season=2026, week=week,
        slate_id=f"2026-w{week:02d}", frozen_at=root_frozen,
        lock_at=lock_at,
        seed_crossing=crossing, suite_authority=suite, arms=arms,
    )
    envelope = shadow.bind_terminal_prelock_root_v1(
        root=root,
        uri=f"gs://fixture-authority/prospective/week-{week}-root.json",
        generation=10_000 + week,
        storage_created_at=lock_at - timedelta(hours=1, minutes=50),
    )
    base = {
        "incumbent-160-40": 180_000_000,
        "boom-first-40-160": 190_000_000,
        "cross-law-40-100-60": 196_000_000,
        "boom-dose-40-360": 192_000_000,
        "ceiling-all-boom-0-200": 175_000_000,
    }
    rows = [
        {"lineup_id": lineup, "realized_score_micro": base[str(arm["arm_id"])]
         + ordinal * 100_000}
        for arm in arms
        for ordinal, lineup in enumerate(arm["candidate_lineup_ids"])
    ]
    captured = lock_at + timedelta(days=1)
    score_identity = _raw_score_identity(
        week=week, slate_id=f"2026-w{week:02d}",
        captured_at=captured, rows=rows,
    )
    snapshot = shadow.build_outcome_snapshot_v1(
        season=2026, week=week, slate_id=f"2026-w{week:02d}",
        captured_at=captured,
        outcome_source_identity=_raw_outcome_identity(
            week=week, slate_id=f"2026-w{week:02d}",
            captured_at=captured, rows=rows, score_identity=score_identity,
        ),
        realized_score_source_identity=score_identity,
        lineup_rows=rows, field_metrics_available=False,
    )
    if include_internal:
        return prereg, root, envelope, snapshot, {
            "suite": suite, "crossing": crossing, "pairs": pairs,
            "shared_draws": shared_draws, "world_ids": world_ids,
            "audit_draws": audit_draws, "audit_identity": audit,
        }
    return prereg, root, envelope, snapshot


def _rehash(mapping: dict[str, object], field: str) -> None:
    mapping.pop(field, None)
    mapping[field] = shadow.canonical_sha256_v1(mapping)


def _rehash_arm(arm: dict[str, object]) -> None:
    _rehash(arm, "arm_freeze_sha256")


def _rehash_root(root: dict[str, object]) -> None:
    root["arms_sha256"] = shadow.canonical_sha256_v1(root["arms"])
    _rehash(root, "terminal_prelock_root_sha256")


def _grade_series(grade: dict[str, object], count: int) -> list[dict[str, object]]:
    result = []
    for week in range(1, count + 1):
        row = deepcopy(grade)
        row["week"] = week
        row["slate_id"] = f"2026-w{week:02d}"
        row["terminal_prelock_root_identity"] = _identity(
            f"grade-root-{week}", generation=20_000 + week
        )
        row["terminal_prelock_root_sha256"] = shadow.canonical_sha256_v1(
            {"root": week}
        )
        row["outcome_source_identity"] = _identity(
            f"grade-outcome-{week}", generation=30_000 + week
        )
        row["realized_score_source_identity"] = _identity(
            f"grade-scores-{week}", generation=35_000 + week
        )
        row["outcome_snapshot_sha256"] = shadow.canonical_sha256_v1(
            {"outcome": week}
        )
        row["seed_crossing_sha256"] = shadow.canonical_sha256_v1(
            {"seed-crossing": week}
        )
        _rehash(row, "weekly_grade_sha256")
        result.append(row)
    return result


def _bind_grade_roots_to_safety(
    grades: list[dict[str, object]],
    receipts: list[dict[str, object]],
) -> list[dict[str, object]]:
    by_week = {int(receipt["week"]): receipt for receipt in receipts}
    retained = deepcopy(grades)
    for grade in retained:
        receipt = by_week.get(int(grade["week"]))
        if receipt is None:
            continue
        grade["terminal_prelock_root_identity"] = deepcopy(
            receipt["terminal_prelock_envelope"]["identity"]
        )
        grade["terminal_prelock_root_sha256"] = receipt[
            "terminal_safety_authority"
        ]["terminal_prelock_root_sha256"]
        _rehash(grade, "weekly_grade_sha256")
    return retained


_SAFETY_RECEIPT_CACHE: dict[int, dict[str, object]] = {}


def _safety_receipt(
    prereg: Mapping[str, object], *, week: int, failed: bool = False
) -> dict[str, object]:
    observed_at = datetime(
        2026, 9, 14, 12, tzinfo=timezone.utc
    ) + timedelta(days=7 * (week - 1))
    envelope = None
    envelope_identity = None
    if not failed:
        cached = _SAFETY_RECEIPT_CACHE.get(week)
        if cached is not None:
            return cached
        case_prereg, _root, envelope, _snapshot = _case(week)
        assert case_prereg == prereg
        envelope_identity = _identity(
            f"safety-{week}-envelope-object",
            generation=40_000 + week,
            sha256=shadow.canonical_sha256_v1(envelope),
            byte_count=len(shadow.canonical_json_bytes_v1(envelope)),
        )
    receipt = shadow.build_weekly_safety_receipt_v1(
        preregistration=prereg,
        week=week,
        slate_id=f"2026-w{week:02d}",
        observed_at=(observed_at if failed else None),
        terminal_prelock_envelope=envelope,
        terminal_prelock_envelope_identity=envelope_identity,
    )
    if not failed:
        _SAFETY_RECEIPT_CACHE[week] = receipt
    return receipt


def _decoded_arm_artifacts(
    internal: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    suite = internal["suite"]
    manifest = suite["manifest"]
    draws = internal["shared_draws"]
    decoded: dict[str, dict[str, object]] = {}
    for freeze, roster_by_digest, generation_metadata in internal["pairs"]:
        arm_id = str(freeze["arm_id"])
        candidate_rosters = [
            tuple(
                roster_by_digest[
                    str(lineup_id).removeprefix("lineup-v1-")
                ]
            )
            for lineup_id in freeze["candidate_lineup_ids"]
        ]
        decoded[arm_id] = {
            "metadata": {
                "artifact_version": "prospective-recourse-worlds-v1",
                "generated_at": manifest["generated_at"],
                "portfolio": "CBWU",
                "candidate_batch_metadata": {
                    "portfolio": "CBWU", "world_blocks": 5,
                    "worlds_per_block": [10_000] * 5,
                    **generation_metadata,
                    "uses_realized_outcomes": False,
                },
                "context": {
                    field: manifest[field] for field in (
                        "season", "week", "draft_group_id", "run_id",
                        "code_sha", "slate_lock_at",
                    )
                } | {"arm": arm_id},
                "uses_post_decision_outcomes": False,
            },
            "player_ids": [f"p{value:03d}" for value in range(180)],
            "player_draws": draws,
            "candidate_rosters": candidate_rosters,
            "sha256": internal["world_ids"][arm_id]["sha256"],
        }
    return decoded


def _decoded_audit_artifact(
    internal: Mapping[str, object],
) -> dict[str, object]:
    manifest = internal["suite"]["manifest"]
    audit_receipt = internal["suite"][
        "independent_audit_world_bank_receipt"
    ]
    audit_input_binding = internal["suite"][
        "independent_audit_input_binding"
    ]
    return {
        "metadata": {
            "artifact_version": "prospective-recourse-worlds-v1",
            "generated_at": manifest["generated_at"],
            "candidate_batch_metadata": {
                "artifact_role": "independent-score-only-audit-world-bank",
                "audit_bank_receipt": deepcopy(audit_receipt),
                "independent_audit_input_binding": deepcopy(
                    audit_input_binding
                ),
                "independent_audit_input_binding_sha256": (
                    audit_input_binding["binding_sha256"]
                ),
                "candidate_solves_run": 0,
                "used_for_selection": False,
                "uses_realized_outcomes": False,
                "post_lock_data_read": False,
            },
            "context": {
                field: manifest[field] for field in (
                    "season", "week", "draft_group_id", "run_id",
                    "code_sha", "slate_lock_at",
                )
            } | {"arm": "independent-audit-world-bank"},
            "uses_post_decision_outcomes": False,
        },
        "player_ids": [f"p{value:03d}" for value in range(180)],
        "player_draws": internal["audit_draws"],
        "candidate_rosters": [],
        "sha256": internal["audit_identity"]["sha256"],
    }


def test_complete_five_arm_freeze_grade_and_exact_horizons() -> None:
    prereg, root, envelope, snapshot = _case()
    assert prereg["operational_k"] == 80
    assert prereg["family_level_decision_rule"][
        "minimum_practically_important_effect_micro"
    ] == 2_000_000
    assert shadow.validate_terminal_prelock_root_v1(envelope) == root
    assert [arm["arm_id"] for arm in root["arms"]] == list(shadow.ARM_ORDER)
    assert [arm["requested_core_solve_count_per_block"] for arm in root["arms"]] == [
        200, 200, 200, 400, 200
    ]
    assert [arm["requested_solve_count_per_slate"] for arm in root["arms"]] == [
        1060, 1060, 1060, 2060, 1060
    ]
    grade = shadow.grade_realized_week_v1(
        terminal_prelock_root=envelope, outcome_snapshot=snapshot
    )
    assert [row["sign"] for row in grade["paired_operational_contrasts"]] == [
        "win", "win", "win", "loss"
    ]
    assert len(grade["arm_results"][0]["prefix_results"][-1]["thresholds"]) == 6
    assert len(grade["retrieval_crossing_cells"]) == 4
    assert grade["contest_field_evidence_scope"] == "raw-score-only-no-contest-ev"

    eight = shadow.evaluate_prospective_shadow_v1(
        preregistration=prereg, weekly_grades=_grade_series(grade, 8)
    )
    assert eight["horizon"] == "eight-week-integrity-severe-harm-only"
    assert all(not row["efficacy_eligible"] for row in eight["family_rule_decisions"])
    assert len(eight["population_cap_calibration"]) == 63
    nine = shadow.evaluate_prospective_shadow_v1(
        preregistration=prereg, weekly_grades=_grade_series(grade, 9)
    )
    assert nine["horizon"] == "post-interim-accrual-no-decision"
    assert all(not row["checkpoint_eligible"] for row in nine["family_rule_decisions"])
    full = shadow.evaluate_prospective_shadow_v1(
        preregistration=prereg, weekly_grades=_grade_series(grade, 18)
    )
    assert full["horizon"] == "full-season-first-efficacy-estimate"
    assert full["full_season_uncertainty_reported"] is True
    assert all(row["uncertainty_95pct"] for row in full["paired_aggregates"])
    assert len(full["retrieval_crossing_aggregates"]) == 4
    assert all(
        [row["entry_count"] for row in cell["prefix_aggregates"]]
        == [20, 40, 80]
        for cell in full["retrieval_crossing_aggregates"]
    )
    assert len(full["retrieval_effect_aggregates"]) == 6
    assert {
        row["entry_count"]
        for row in full["retrieval_effect_aggregates"]
    } == {20, 40, 80}
    assert all(
        set(row["threshold_hit_deltas"])
        == {"194", "200", "210", "220", "230", "240"}
        and row["selected_weekly_maximum_effect"]["uncertainty_95pct"][
            "method"
        ] == "slate-level-paired-t-interval-95pct"
        and row["pool_oracle_effect"]["uncertainty_95pct"] is not None
        and row["selector_regret_effect"]["uncertainty_95pct"] is not None
        for row in full["retrieval_effect_aggregates"]
    )
    interactions = full["retrieval_interaction_aggregate"]["prefix_aggregates"]
    assert [row["entry_count"] for row in interactions] == [20, 40, 80]
    assert all(
        row["effect_families"]["selected_weekly_maximum"]
        ["difference_in_differences"]["uncertainty_95pct"]["method"]
        == "slate-level-paired-t-interval-95pct"
        and set(row["threshold_hit_effects"])
        == {"194", "200", "210", "220", "230", "240"}
        for row in interactions
    )
    assert full["structural_synthesis"]["concordance_status"] == (
        "not-concordant-or-not-resolved"
    )
    assert full["structural_synthesis"]["disposition"] == (
        "continue-unchanged-accrual-into-2027"
    )
    assert full["automatic_adoption"] is False


def test_week8_safety_family_is_frozen_before_week1_and_fails_closed() -> None:
    prereg = shadow.build_preregistration_v1(
        registered_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        week1_lock_at=datetime(2026, 9, 13, 17, tzinfo=timezone.utc),
    )
    rule = prereg["week8_safety_rule"]
    assert rule["receipt_weeks"] == list(range(1, 9))
    assert len(rule["expected_book_ids"]) == 7
    assert rule["thresholds"]["maximum_missing_expected_book_count"] == 0
    assert rule["thresholds"]["maximum_illegal_lineup_count"] == 0
    assert rule["thresholds"]["maximum_solve_failure_count"] == 0
    assert rule["thresholds"]["maximum_exposure_violation_count"] == 0
    assert rule["efficacy_or_promotion_allowed"] is False

    failed = _safety_receipt(prereg, week=1, failed=True)
    assert failed["integrity_gate_status"] == "fail"
    assert failed["terminal_prelock_envelope_identity"] is None
    assert failed["safety_metrics"]["missing_expected_book_count"] == 7
    assert failed["safety_metrics"]["missing_required_source_count"] == 6
    assert failed["safety_metrics"]["solve_failure_count"] is None
    assert "solve_failure_count" in failed["unvalidated_metric_ids"]
    assert "missing-terminal" in failed["reason_vector"]
    assert "unvalidated-illegal-lineups" in failed["reason_vector"]
    assert shadow.validate_weekly_safety_receipt_v1(
        failed, preregistration=prereg
    ) == failed

    forged = deepcopy(failed)
    forged["reason_vector"] = []
    _rehash(forged, "weekly_safety_receipt_sha256")
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="derived terminal lineage",
    ):
        shadow.validate_weekly_safety_receipt_v1(
            forged, preregistration=prereg
        )

    dummy = {"claimed_zero_counts": True, "evidence": "arbitrary-bytes"}
    dummy_identity = _identity(
        "dummy-safety-terminal",
        sha256=shadow.canonical_sha256_v1(dummy),
        byte_count=len(shadow.canonical_json_bytes_v1(dummy)),
    )
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="terminal prelock envelope fields differ",
    ):
        shadow.build_weekly_safety_receipt_v1(
            preregistration=prereg,
            week=1,
            slate_id="2026-w01",
            observed_at=datetime(2026, 9, 14, 12, tzinfo=timezone.utc),
            terminal_prelock_envelope=dummy,
            terminal_prelock_envelope_identity=dummy_identity,
        )


def test_week8_integrity_requires_exact_complete_receipts_and_never_promotes(
) -> None:
    prereg, _root, envelope, snapshot = _case()
    grade = shadow.grade_realized_week_v1(
        terminal_prelock_root=envelope, outcome_snapshot=snapshot
    )
    grades = _grade_series(grade, 8)

    absent = shadow.evaluate_prospective_shadow_v1(
        preregistration=prereg, weekly_grades=grades
    )
    assert absent["week8_integrity_gate"]["integrity_gate_status"] == (
        "not_evaluated"
    )
    assert all(
        row["efficacy_rule_satisfied"] is False
        for row in absent["family_rule_decisions"]
    )

    pass_receipts = [
        _safety_receipt(prereg, week=week) for week in range(1, 9)
    ]
    assert all(
        receipt["observed_at"]
        == receipt["terminal_prelock_envelope"]["storage_created_at"]
        for receipt in pass_receipts
    )
    grades = _bind_grade_roots_to_safety(grades, pass_receipts)
    assert all(
        receipt["safety_metrics"]["illegal_lineup_count"] == 0
        and receipt["safety_metrics"]["solve_failure_count"] == 0
        and receipt["safety_metrics"]["duplicate_lineup_count"] == 0
        and receipt["terminal_safety_authority"][
            "membership_metrics_exactly_derivable"
        ] is True
        for receipt in pass_receipts
    )

    envelope = pass_receipts[0]["terminal_prelock_envelope"]
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="caller observation time differs from trusted storage time",
    ):
        shadow.build_weekly_safety_receipt_v1(
            preregistration=prereg,
            week=1,
            slate_id="2026-w01",
            observed_at=datetime(2026, 9, 13, 12, tzinfo=timezone.utc),
            terminal_prelock_envelope=envelope,
            terminal_prelock_envelope_identity=pass_receipts[0][
                "terminal_prelock_envelope_identity"
            ],
        )
    passed = shadow.evaluate_prospective_shadow_v1(
        preregistration=prereg,
        weekly_grades=grades,
        weekly_safety_receipts=pass_receipts,
    )
    assert passed["week8_integrity_gate"]["integrity_gate_status"] == "pass"
    assert passed["week8_integrity_gate"]["complete_receipt_set"] is True
    assert all(
        row["efficacy_eligible"] is False
        and row["efficacy_promotion_authorized"] is False
        for row in passed["family_rule_decisions"]
    )

    failed_receipts = list(pass_receipts)
    failed_receipts[2] = _safety_receipt(prereg, week=3, failed=True)
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="lacks a terminal-present safety lineage",
    ):
        shadow.evaluate_prospective_shadow_v1(
            preregistration=prereg,
            weekly_grades=grades,
            weekly_safety_receipts=failed_receipts,
        )

    mismatched = deepcopy(grades)
    mismatched[0]["terminal_prelock_root_identity"] = _identity(
        "wrong-safety-grade-root", generation=99_991
    )
    _rehash(mismatched[0], "weekly_grade_sha256")
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="root lineages differ",
    ):
        shadow.evaluate_prospective_shadow_v1(
            preregistration=prereg,
            weekly_grades=mismatched,
            weekly_safety_receipts=pass_receipts,
        )


def test_failed_suite_can_reach_week8_integrity_without_successful_terminal(
) -> None:
    prereg = shadow.build_preregistration_v1(
        registered_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        week1_lock_at=datetime(2026, 9, 13, 17, tzinfo=timezone.utc),
    )
    receipts = [
        _safety_receipt(prereg, week=week, failed=(week == 4))
        for week in range(1, 9)
    ]
    evaluation = shadow.evaluate_prospective_shadow_v1(
        preregistration=prereg,
        weekly_grades=[],
        weekly_safety_receipts=receipts,
    )
    assert evaluation["completed_week_count"] == 8
    assert evaluation["graded_week_count"] == 0
    assert evaluation["horizon"] == "eight-week-integrity-severe-harm-only"
    assert evaluation["week8_integrity_gate"]["integrity_gate_status"] == "fail"
    assert evaluation["week8_integrity_gate"]["metric_totals"][
        "missing_terminal_count"
    ] == 1
    assert evaluation["family_rule_decisions"] == []
    assert evaluation["contest_ev_claim_allowed"] is False


def test_full_season_cannot_satisfy_efficacy_without_week8_safety_pass() -> None:
    prereg, _root, envelope, snapshot = _case()
    grade = shadow.grade_realized_week_v1(
        terminal_prelock_root=envelope, outcome_snapshot=snapshot
    )
    result = shadow.evaluate_prospective_shadow_v1(
        preregistration=prereg,
        weekly_grades=_grade_series(grade, 18),
    )
    assert result["week8_integrity_gate"]["integrity_gate_status"] == (
        "not_evaluated"
    )
    assert all(
        row["efficacy_eligible"] is False
        and row["efficacy_rule_satisfied"] is False
        and row["efficacy_promotion_authorized"] is False
        for row in result["family_rule_decisions"]
    )


def test_only_primary_contrast_can_satisfy_full_season_efficacy_rule() -> None:
    prereg, _root, envelope, snapshot = _case()
    assert prereg["all_five_arms_required_before_week1"] is True
    assert prereg["arm_omission_allowed"] is False
    assert all(
        role["arm_status"] == "required"
        and role["required_before_week1"] is True
        for role in prereg["arm_decision_roles"].values()
    )
    grade = shadow.grade_realized_week_v1(
        terminal_prelock_root=envelope, outcome_snapshot=snapshot
    )
    safety_receipts = [
        _safety_receipt(prereg, week=week) for week in range(1, 9)
    ]
    grades = _bind_grade_roots_to_safety(
        _grade_series(grade, 18), safety_receipts
    )
    result = shadow.evaluate_prospective_shadow_v1(
        preregistration=prereg,
        weekly_grades=grades,
        weekly_safety_receipts=safety_receipts,
    )
    decisions = {
        row["challenger_arm"]: row
        for row in result["family_rule_decisions"]
    }
    primary = decisions["boom-first-40-160"]
    assert primary["decision_role"] == "primary-efficacy-rule"
    assert primary["primary_efficacy_rule_satisfaction_allowed"] is True
    assert primary["efficacy_eligible"] is True
    assert primary["primary_efficacy_rule_satisfied"] is True
    assert primary["efficacy_rule_satisfied"] is True
    for arm_id in (
        "cross-law-40-100-60",
        "boom-dose-40-360",
        "ceiling-all-boom-0-200",
    ):
        diagnostic = decisions[arm_id]
        assert diagnostic["numeric_diagnostic_criteria_reported"] is True
        assert diagnostic["decision_role"] == "diagnostic-only"
        assert diagnostic[
            "primary_efficacy_rule_satisfaction_allowed"
        ] is False
        assert diagnostic["promotion_equivalent_efficacy_allowed"] is False
        assert diagnostic["efficacy_eligible"] is False
        assert diagnostic["primary_efficacy_rule_satisfied"] is False
        assert diagnostic["efficacy_rule_satisfied"] is False
    assert result["retrieval_interaction_aggregate"]["decision_role"] == (
        "key-secondary-mechanism"
    )
    assert result["retrieval_interaction_aggregate"][
        "primary_efficacy_rule_satisfaction_allowed"
    ] is False
    synthesis = result["structural_synthesis"]
    assert synthesis["concordance_status"] == "concordant"
    assert synthesis["disposition"] == (
        "human-review-candidate-no-automatic-adoption"
    )
    assert all(synthesis["condition_vector"].values())
    assert synthesis["historical_object_read_during_evaluation"] is False
    assert synthesis["automatic_adoption"] is False


def test_actual_suite_decoded_bundle_adapter_is_operational() -> None:
    prereg, _root, _envelope, _snapshot, internal = _case(
        include_internal=True
    )
    decoded = _decoded_arm_artifacts(internal)
    selected_supply_trace = internal["suite"][
        "cross_law_selected_supply_trace"
    ]
    assert selected_supply_trace["candidate_pool"][
        "genuinely_new_discovery_candidate_count"
    ] > 0
    assert all(
        selected_supply_trace["selected_prefixes"][str(prefix)][
            "genuinely_new_discovery_candidate_count"
        ] > 0
        for prefix in shadow.PREFIX_SIZES
    )
    rebuilt = shadow.build_terminal_prelock_root_from_suite_v2(
        preregistration=prereg,
        seed_crossing=internal["crossing"],
        suite_authority=internal["suite"],
        decoded_arm_artifacts=decoded,
        decoded_audit_artifact=_decoded_audit_artifact(internal),
    )
    assert [arm["arm_id"] for arm in rebuilt["arms"]] == list(
        shadow.ARM_ORDER
    )
    assert all(
        arm["exposure_ledger_mode"]
        == "suite-native-plus-transform-ledgers"
        for arm in rebuilt["arms"]
    )
    assert all(
        len({_identity_key["sha256"] for _identity_key in (
            descriptor["identity"] for descriptor in arm["artifacts"].values()
        )}) == 1
        for arm in rebuilt["arms"]
    )

    # A self-consistent, fully rehashed trace may not move genuine discovery
    # attribution from its status=new ledger roster to an unrelated roster.
    forged_suite = deepcopy(internal["suite"])
    forged_trace = deepcopy(selected_supply_trace)
    cross_law_freeze = next(
        pair[0] for pair in internal["pairs"]
        if pair[0]["arm_id"] == "cross-law-40-100-60"
    )
    candidate_ids = list(cross_law_freeze["candidate_lineup_ids"])
    book_ids = list(cross_law_freeze["book_lineup_ids"])
    original_new = set(forged_trace["candidate_pool"][
        "genuinely_new_discovery_lineup_ids"
    ])
    original_duplicate = set(forged_trace["candidate_pool"][
        "duplicate_attempt_provenance_only_lineup_ids"
    ])
    true_selected_new = next(
        lineup_id for lineup_id in book_ids[:20]
        if lineup_id in original_new
    )
    false_selected_new = next(
        lineup_id for lineup_id in book_ids[:20]
        if lineup_id not in original_new | original_duplicate
    )
    forged_new = (original_new - {true_selected_new}) | {
        false_selected_new
    }
    for prefix, projection in (
        (len(candidate_ids), forged_trace["candidate_pool"]),
        *(
            (prefix, forged_trace["selected_prefixes"][str(prefix)])
            for prefix in shadow.PREFIX_SIZES
        ),
    ):
        order = candidate_ids if prefix == len(candidate_ids) else book_ids[:prefix]
        new_ids = [lineup_id for lineup_id in order if lineup_id in forged_new]
        duplicate_ids = [
            lineup_id for lineup_id in order
            if lineup_id in original_duplicate
        ]
        projection["genuinely_new_discovery_candidate_count"] = len(new_ids)
        projection["duplicate_attempt_provenance_only_candidate_count"] = len(
            duplicate_ids
        )
        projection["any_cross_law_provenance_candidate_count"] = len(
            new_ids
        ) + len(duplicate_ids)
        projection["genuinely_new_discovery_lineup_ids"] = new_ids
        projection["duplicate_attempt_provenance_only_lineup_ids"] = (
            duplicate_ids
        )
        projection["any_cross_law_provenance_lineup_ids"] = [
            lineup_id for lineup_id in order
            if lineup_id in forged_new | original_duplicate
        ]
        _rehash(projection, "projection_sha256")
    cross_law_decoded = decoded["cross-law-40-100-60"]
    source_blocks = cross_law_decoded["metadata"][
        "candidate_batch_metadata"
    ]["candidate_source_blocks"]
    forged_rows = []
    for ordinal, (lineup_id, roster, source) in enumerate(zip(
        candidate_ids,
        cross_law_decoded["candidate_rosters"],
        source_blocks,
        strict=True,
    )):
        classification = "no-cross-law-provenance"
        if lineup_id in forged_new:
            classification = "newly-supplied-discovery"
        elif lineup_id in original_duplicate:
            classification = "duplicate-attempt-provenance-only"
        forged_rows.append({
            "candidate_ordinal": ordinal,
            "source_block": source,
            "internal_roster_sha256": exposure.roster_identity(roster)[
                "roster_sha256"
            ],
            "dk_lineup_id": lineup_id,
            "classification": classification,
        })
    forged_trace["classification_rows_sha256"] = (
        shadow.canonical_sha256_v1(forged_rows)
    )
    _rehash(forged_trace, "trace_sha256")
    forged_suite["cross_law_selected_supply_trace"] = forged_trace
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="selected-supply trace differs",
    ):
        shadow._decoded_suite_arm_freezes_v2(
            suite=forged_suite,
            decoded_arm_artifacts=decoded,
            decoded_audit_artifact=_decoded_audit_artifact(internal),
            seed_crossing_sha256=internal["crossing"][
                "seed_crossing_sha256"
            ],
        )

    forged = dict(decoded)
    bad_arm = dict(forged[shadow.ARM_ORDER[0]])
    bad_rosters = list(bad_arm["candidate_rosters"])
    bad_rosters.pop()
    bad_arm["candidate_rosters"] = bad_rosters
    forged[shadow.ARM_ORDER[0]] = bad_arm
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="pool/world projection",
    ):
        shadow.build_terminal_prelock_root_from_suite_v2(
            preregistration=prereg,
            seed_crossing=internal["crossing"],
            suite_authority=internal["suite"],
            decoded_arm_artifacts=forged,
            decoded_audit_artifact=_decoded_audit_artifact(internal),
        )


@pytest.mark.parametrize(
    "source_field",
    (
        "candidate_input_receipt",
        "role_candidate_input_receipt",
        "model_version",
        "role_model_version",
        "construction_preset_receipt",
    ),
)
def test_decoded_suite_rejects_native_input_source_drift(
    source_field: str,
) -> None:
    prereg, _root, _envelope, _snapshot, internal = _case(
        include_internal=True
    )
    decoded = _decoded_arm_artifacts(internal)
    arm_id = "boom-dose-40-360"
    forged = deepcopy(decoded)
    receipt = forged[arm_id]["metadata"]["candidate_batch_metadata"][
        "native_generation_receipts"
    ]["R3"]
    if source_field in {
        "candidate_input_receipt", "role_candidate_input_receipt"
    }:
        receipt[source_field]["sha256"] = "f" * 64
    elif source_field == "construction_preset_receipt":
        receipt[source_field]["min_games"] += 1
    else:
        receipt[source_field] += "-drift"
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="native input/source",
    ):
        shadow.build_terminal_prelock_root_from_suite_v2(
            preregistration=prereg,
            seed_crossing=internal["crossing"],
            suite_authority=internal["suite"],
            decoded_arm_artifacts=forged,
            decoded_audit_artifact=_decoded_audit_artifact(internal),
        )


def test_suite_audit_input_binding_survives_clean_json_reopen() -> None:
    _prereg, _root, _envelope, _snapshot, internal = _case(
        include_internal=True
    )
    reopened = json.loads(json.dumps(internal["suite"], sort_keys=True))
    assert shadow.validate_suite_authority_v1(reopened) == reopened


def test_decoded_audit_rejects_input_authority_mismatch() -> None:
    prereg, _root, _envelope, _snapshot, internal = _case(
        include_internal=True
    )
    forged = _decoded_audit_artifact(internal)
    forged_binding = forged["metadata"]["candidate_batch_metadata"][
        "independent_audit_input_binding"
    ]
    forged_binding["audit_observed_main_source_identity"][
        "model_version"
    ] = "fixture-model-drift"
    forged_binding.pop("binding_sha256")
    forged_binding["binding_sha256"] = shadow.canonical_sha256_v1(
        forged_binding
    )
    forged["metadata"]["candidate_batch_metadata"][
        "independent_audit_input_binding_sha256"
    ] = forged_binding["binding_sha256"]
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="independent-audit input/source receipt",
    ):
        shadow.build_terminal_prelock_root_from_suite_v2(
            preregistration=prereg,
            seed_crossing=internal["crossing"],
            suite_authority=internal["suite"],
            decoded_arm_artifacts=_decoded_arm_artifacts(internal),
            decoded_audit_artifact=forged,
        )


def test_complete_field_bridge_keeps_actual_and_counterfactual_facts_separate() -> None:
    prereg, _root, envelope, raw_snapshot = _case()
    rows = [{
        "lineup_id": row["lineup_id"],
        "realized_score_micro": row["realized_score_micro"],
        "actual_field_rank": None,
        "actual_field_percentile_ppm": None,
        "counterfactual_field_rank": 101,
        "counterfactual_field_percentile_ppm": 0,
        "duplicates": 0,
        "split_payout_micro": 0,
        "entered_in_contest": False,
        "matching_entry_ids": [],
        "actual_split_payout_applicable": False,
    } for row in raw_snapshot["lineup_rows"]]
    component_names = (
        "payout_table", "field_rosters", "field_ownership",
        "participant_strength", "player_identity", "shadow_entry_mapping",
    )
    components = {
        name: _identity(f"field-{name}", generation=40_000 + ordinal)
        for ordinal, name in enumerate(component_names)
    }
    capture = {
        "contest_id": "fixture-contest", "field_size": 100,
        "entry_fee_micro": 20_000_000,
        "payout_table_identity": components["payout_table"],
        "field_rosters_identity": components["field_rosters"],
        "field_ownership_identity": components["field_ownership"],
        "participant_strength_identity": components["participant_strength"],
        "shadow_entry_mapping_identity": components["shadow_entry_mapping"],
            "complete": True, "status": "complete-contest-field-capture",
            "evidence_scope": (
                "raw-score-and-complete-field-ranks-no-counterfactual-contest-ev"
            ),
            "complete_field_rank_claim_allowed": True,
            "contest_ev_claim_allowed": False,
        "allocation_recommendation_allowed": False,
    }
    bridge = {
        "schema_version": field_bridge.BRIDGE_SCHEMA,
        "season": 2026, "week": 1, "slate_id": "2026-w01",
        "captured_at": raw_snapshot["captured_at"],
        "terminal_prelock_root_identity": envelope["identity"],
        "terminal_prelock_root_sha256": envelope[
            "terminal_prelock_root_sha256"
        ],
        "membership_projection_sha256": shadow.canonical_sha256_v1(
            {"fixture": "memberships"}
        ),
        "status": "complete-contest-field-capture",
        "evidence_scope": (
            "raw-score-and-complete-field-ranks-no-counterfactual-contest-ev"
        ),
        "complete_contest_field_capture": True,
        "complete_field_rank_claim_allowed": True,
        "contest_ev_claim_allowed": False,
        "allocation_recommendation_allowed": False,
        "deficiencies": [],
        "capture_source_identity": _identity(
            "field-capture-source", generation=41_000
        ),
        "realized_score_source_identity": raw_snapshot[
            "realized_score_source_identity"
        ],
        "component_identities": components,
        "component_payload_sha256_by_name": {
            name: components[name]["sha256"] for name in component_names
        },
        "evaluator_contest_field_capture": capture,
        "evaluator_lineup_rows": rows,
        "evaluator_lineup_rows_sha256": shadow.canonical_sha256_v1(rows),
        "entered_shadow_lineup_count": 0,
        "not_entered_shadow_lineup_count": len(rows),
        "every_frozen_lineup_mapped_entered_or_not_entered": True,
        "actual_payout_never_imputed_for_unentered_lineup": True,
        "uses_realized_outcomes": True,
    }
    bridge["field_bridge_sha256"] = shadow.canonical_sha256_v1(bridge)
    payload = shadow.build_outcome_source_payload_from_field_bridge_v1(
        terminal_prelock_root=envelope, field_bridge=bridge
    )
    outcome_identity = _identity(
        "complete-field-outcome", generation=42_000,
        sha256=shadow.canonical_sha256_v1(payload),
        byte_count=len(shadow.canonical_json_bytes_v1(payload)),
    )
    snapshot = shadow.build_outcome_snapshot_from_field_bridge_v1(
        terminal_prelock_root=envelope, field_bridge=bridge,
        outcome_source_identity=outcome_identity,
    )
    grade = shadow.grade_realized_week_v1(
        terminal_prelock_root=envelope, outcome_snapshot=snapshot
    )
    metric = grade["arm_results"][0]["prefix_results"][-1]["field_metrics"]
    assert metric["best_realized_lineup_actual_field_rank"] is None
    assert metric["best_realized_lineup_counterfactual_field_rank"] == 101
    assert metric["best_realized_lineup_duplicates"] == 0
    assert metric["best_realized_lineup_actual_split_payout_applicable"] is False

    evaluation = shadow.evaluate_prospective_shadow_v1(
        preregistration=prereg, weekly_grades=[grade]
    )
    for cell in evaluation["retrieval_crossing_aggregates"]:
        for prefix in cell["prefix_aggregates"]:
            assert prefix["field_availability"] == {
                "complete_field_capture_week_count": 1,
                "missing_field_capture_week_count": 0,
                "complete_for_every_week": True,
                "evidence_scope": "complete-field-every-week",
            }
            field_summary = prefix["complete_field_metrics"]
            assert field_summary["best_counterfactual_field_rank"] == 101
            assert field_summary["entered_lineup_observation_count"] == 0
            assert field_summary["best_lineup_duplicate_sum"] == 0
            assert field_summary["total_actual_split_payout_micro"] == 0
            assert field_summary["contest_ev_imputed"] is False

    bad_rows = [dict(row) for row in rows]
    bad_rows[0]["duplicates"] = 1
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="unentered contest facts",
    ):
        shadow.build_outcome_snapshot_v1(
            season=2026, week=1, slate_id="2026-w01",
            captured_at=raw_snapshot["captured_at"],
            outcome_source_identity=outcome_identity,
            realized_score_source_identity=raw_snapshot[
                "realized_score_source_identity"
            ],
            lineup_rows=bad_rows, field_metrics_available=True,
            contest_field_capture=capture,
        )


def test_shared_hash_and_repaired_ledger_leakage_fail() -> None:
    assert shadow.canonical_sha256_v1({"a": [1]}) == exposure.canonical_sha256(
        {"a": [1]}
    )
    _, root, _, _ = _case()
    arm = deepcopy(root["arms"][0])
    ledger = arm["exposure_ledgers_by_block"]["R0"]["native"]
    ledger["rows"][0]["uses_realized_outcomes"] = True
    _rehash(ledger["rows"][0], "row_sha256")
    ledger["row_manifest_sha256"] = shadow.canonical_sha256_v1(ledger["rows"])
    _rehash(ledger, "ledger_sha256")
    arm["exposure_ledger_sha256_by_block"]["R0"]["native"] = ledger[
        "ledger_sha256"
    ]
    _rehash_arm(arm)
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="realized outcomes",
    ):
        shadow.validate_arm_freeze_v1(arm)


def test_bank_mismatch_and_reused_seed_identity_fail() -> None:
    _, root, _, _ = _case()
    broken = deepcopy(root)
    broken["arms"][1]["untouched_selection_bank_identity"] = _identity("other")
    _rehash_arm(broken["arms"][1])
    _rehash_root(broken)
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="bank, seed, resource",
    ):
        shadow.validate_terminal_prelock_root_body_v1(broken)
    crossing = deepcopy(root["seed_crossing"])
    crossing["fit_seed_slots"][1]["identity"] = crossing["fit_seed_slots"][0][
        "identity"
    ]
    for row in crossing["crossed_slots"]:
        if row["fit_seed_slot"] == "fit1":
            row["fit_seed_identity"] = crossing["fit_seed_slots"][0]["identity"]
    crossing["crossed_slots_sha256"] = shadow.canonical_sha256_v1(
        crossing["crossed_slots"]
    )
    _rehash(crossing, "seed_crossing_sha256")
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="distinct artifacts",
    ):
        shadow.validate_seed_crossing_v1(crossing)
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="exactly two slots",
    ):
        shadow.build_seed_crossing_v1(
            fit_seed_identities={
                "fit0": _identity("fit0"),
                "fit1": _identity("fit1"),
                "fit2": _identity("fit2"),
            },
            world_seed_identities={
                "world0": _identity("world0"),
                "world1": _identity("world1"),
            },
            crossed_slot_identities={
                f"fit{fit}--world{world}": _identity(
                    f"fit{fit}-world{world}"
                )
                for fit in range(3) for world in range(2)
            },
        )


def test_missing_attempt_and_unledgered_candidate_fail() -> None:
    _, root, _, _ = _case()
    arm = deepcopy(root["arms"][0])
    ledger = arm["exposure_ledgers_by_block"]["R0"]["native"]
    ledger["rows"].pop()
    ledger["attempt_count"] -= 1
    ledger["status_counts"]["new"] -= 1
    ledger["row_manifest_sha256"] = shadow.canonical_sha256_v1(ledger["rows"])
    for field, source in (
        ("duration_seconds_by_family", "family"),
        ("duration_seconds_by_status", "status"),
    ):
        ledger[field] = {
            key: sum(float(row["duration_seconds"]) for row in ledger["rows"]
                     if row[source] == key)
            for key in ledger[field]
        }
    ledger["total_duration_seconds"] = sum(
        float(row["duration_seconds"]) for row in ledger["rows"]
    )
    _rehash(ledger, "ledger_sha256")
    arm["exposure_ledger_sha256_by_block"]["R0"]["native"] = ledger[
        "ledger_sha256"
    ]
    arm["solve_attempt_count_per_block"]["R0"] -= 1
    arm["solve_attempt_count_per_slate"] -= 1
    _rehash_arm(arm)
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="requested-solve census",
    ):
        shadow.validate_arm_freeze_v1(arm)

    arm = deepcopy(root["arms"][0])
    forged = f"lineup-v1-{shadow.canonical_sha256_v1({'forged': True})}"
    arm["candidate_lineup_ids"].append(forged)
    arm["candidate_lineup_ids_sha256"] = shadow.canonical_sha256_v1(
        arm["candidate_lineup_ids"]
    )
    arm["book_lineup_ids"][0] = forged
    arm["book_lineup_ids_sha256"] = shadow.canonical_sha256_v1(
        arm["book_lineup_ids"]
    )
    arm["prefixes"] = {
        str(prefix): arm["book_lineup_ids"][:prefix]
        for prefix in shadow.PREFIX_SIZES
    }
    arm["prefixes_sha256"] = shadow.canonical_sha256_v1(arm["prefixes"])
    _rehash_arm(arm)
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="unledgered provenance",
    ):
        shadow.validate_arm_freeze_v1(arm)


def test_postlock_mutation_arm_omission_and_prefix_fail() -> None:
    _, root, _, _ = _case()
    broken = deepcopy(root)
    broken["arms"][0]["artifacts"]["book"]["storage_created_at"] = (
        datetime.fromisoformat(str(root["lock_at"])) + timedelta(minutes=1)
    ).isoformat()
    _rehash_arm(broken["arms"][0])
    _rehash_root(broken)
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="after the prelock boundary",
    ):
        shadow.validate_terminal_prelock_root_body_v1(broken)
    omitted = deepcopy(root)
    omitted["arms"].pop()
    _rehash_root(omitted)
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError, match="arm lattice"
    ):
        shadow.validate_terminal_prelock_root_body_v1(omitted)
    arm = deepcopy(root["arms"][0])
    arm["prefixes"]["20"] = arm["book_lineup_ids"][1:21]
    arm["prefixes_sha256"] = shadow.canonical_sha256_v1(arm["prefixes"])
    _rehash_arm(arm)
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError, match="prefix"
    ):
        shadow.validate_arm_freeze_v1(arm)


class _PoisonOutcome(Mapping[str, object]):
    def __getitem__(self, key: str) -> object:
        raise AssertionError("outcome read before freeze rejection")

    def __iter__(self) -> Iterator[str]:
        raise AssertionError("outcome read before freeze rejection")

    def __len__(self) -> int:
        raise AssertionError("outcome read before freeze rejection")


def test_grader_separation_and_outcome_authentication() -> None:
    assert list(inspect.signature(shadow.grade_realized_week_v1).parameters) == [
        "terminal_prelock_root", "outcome_snapshot"
    ]
    _, _, envelope, snapshot = _case()
    broken = deepcopy(envelope)
    broken["terminal_prelock_root"]["arms"].pop()
    with pytest.raises(shadow.ProspectiveGenerationShadowEvaluationError):
        shadow.grade_realized_week_v1(
            terminal_prelock_root=broken, outcome_snapshot=_PoisonOutcome()
        )
    forged = deepcopy(snapshot)
    forged["lineup_rows"][0]["realized_score_micro"] += 50_000_000
    forged["lineup_rows_sha256"] = shadow.canonical_sha256_v1(
        forged["lineup_rows"]
    )
    _rehash(forged, "outcome_snapshot_sha256")
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="does not bind",
    ):
        shadow.grade_realized_week_v1(
            terminal_prelock_root=envelope, outcome_snapshot=forged
        )
    linked = deepcopy(snapshot)
    linked["terminal_prelock_root_sha256"] = envelope[
        "terminal_prelock_root_sha256"
    ]
    _rehash(linked, "outcome_snapshot_sha256")
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="snapshot fields differ",
    ):
        shadow.grade_realized_week_v1(
            terminal_prelock_root=envelope, outcome_snapshot=linked
        )


def test_suite_adapter_and_evaluation_tampering_fail() -> None:
    prereg, root, envelope, snapshot = _case()
    suite = deepcopy(root["suite_authority"])
    suite["terminal"]["uses_realized_outcomes"] = True
    _rehash(suite["terminal"], "terminal_receipt_sha256")
    _rehash(suite, "suite_authority_sha256")
    with pytest.raises(shadow.ProspectiveGenerationShadowEvaluationError):
        shadow.validate_suite_authority_v1(suite)
    grade = shadow.grade_realized_week_v1(
        terminal_prelock_root=envelope, outcome_snapshot=snapshot
    )
    evaluation = shadow.evaluate_prospective_shadow_v1(
        preregistration=prereg, weekly_grades=_grade_series(grade, 8)
    )
    pristine = deepcopy(evaluation)
    evaluation["family_rule_decisions"][0]["efficacy_rule_satisfied"] = True
    evaluation["population_cap_calibration"][0] = {"forged": True}
    _rehash(evaluation, "evaluation_sha256")
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="arithmetic or lineage",
    ):
        shadow.validate_prospective_shadow_evaluation_v1(evaluation)

    forged_crossing = deepcopy(pristine)
    forged_crossing["retrieval_effect_aggregates"][0][
        "threshold_hit_deltas"
    ]["240"] = 99
    _rehash(forged_crossing, "evaluation_sha256")
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="arithmetic or lineage",
    ):
        shadow.validate_prospective_shadow_evaluation_v1(forged_crossing)

    forged_synthesis = deepcopy(pristine)
    forged_synthesis["structural_synthesis"]["disposition"] = (
        "automatic-adoption"
    )
    _rehash(forged_synthesis, "evaluation_sha256")
    with pytest.raises(
        shadow.ProspectiveGenerationShadowEvaluationError,
        match="arithmetic or lineage",
    ):
        shadow.validate_prospective_shadow_evaluation_v1(forged_synthesis)


def test_outcome_requires_full_frozen_candidate_union() -> None:
    _, _, envelope, snapshot = _case()
    incomplete = deepcopy(snapshot)
    incomplete["lineup_rows"].pop()
    incomplete["lineup_count"] -= 1
    incomplete["lineup_rows_sha256"] = shadow.canonical_sha256_v1(
        incomplete["lineup_rows"]
    )
    _rehash(incomplete, "outcome_snapshot_sha256")
    with pytest.raises(shadow.ProspectiveGenerationShadowEvaluationError):
        shadow.grade_realized_week_v1(
            terminal_prelock_root=envelope, outcome_snapshot=incomplete
        )
