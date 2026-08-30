"""Run and freeze the complete 2026 prospective generation-shadow family.

Every arm uses the same deterministic five base-law simulation/selection
banks.  Alternative laws may propose candidates, but only the untouched base
bank selects them.  The module is outcome-blind; realized grading lives in a
separate module and can run only from the terminal prelock root.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
import re
import time
from typing import Final

import numpy as np
import pandas as pd

from ..backtest.engine import CandidateBatch, _validate_candidate_batch
from ..config import settings
from ..optimizer.lineup import Lineup, select_tail_entries
from .generation_exposure import canonical_sha256, validate_ledger
from .production_policy import ADOPTED_CLASSIC_POLICY
from .prospective_boom_first import (
    _array_receipt,
    _artifact_batch_without_runtime_timing,
    _slate_identity,
    _validated_cloud_execution_context,
    _validated_image_uri,
    player_identity_bridge,
    validate_constraint_contract,
)
from .prospective_cross_law_discovery import (
    build_cross_law_discovery_batch,
    rebuild_cross_law_discovery_world_matrix,
)
from .prospective_generation_retrieval_crossing import (
    POPULATION_ORDER as RETRIEVAL_POPULATION_ORDER,
    build_generation_retrieval_crossing,
)
from .prospective_generation_shadow_registry import (
    registry_document,
    validate_registry,
)
from .prospective_shadow import _canonical_dk_roster, _validated_code_sha
from .recourse_worlds import persist_recourse_world_artifact


VERSION: Final = "prospective-generation-shadow-suite-v2"
MANIFEST_SCHEMA: Final = "prospective-generation-shadow-manifest/v2"
TERMINAL_SCHEMA: Final = "prospective-generation-shadow-terminal/v2"
ENTRIES: Final = 80
TAIL_LINE: Final = 194.0
PREFIXES: Final = (20, 40, 80)
THRESHOLDS: Final = (194, 200, 210, 220, 230, 240)
SEED_LABELS: Final = ("R0", "R1", "R2", "R3", "R4")
WORLDS_PER_BLOCK: Final = 10_000
AUDIT_WORLD_SEED: Final = 2_026_083_001
AUDIT_WORLD_COUNT: Final = 10_000
ARM_ORDER: Final = (
    "incumbent-160-40",
    "boom-first-40-160",
    "cross-law-40-100-60",
    "boom-dose-40-360",
    "ceiling-all-boom-0-200",
)
COMPARATOR_BY_ARM: Final = {
    "boom-first-40-160": "incumbent-160-40",
    "cross-law-40-100-60": "boom-first-40-160",
    "boom-dose-40-360": "boom-first-40-160",
    "ceiling-all-boom-0-200": "boom-first-40-160",
}
_ENV_ARM_KEYS: Final = frozenset({
    "N_LEV",
    "N_BOOM",
    "GEN_TOTAL_BUDGET",
    "PROSPECTIVE_SHADOW_ID",
})
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class ProspectiveGenerationShadowError(ValueError):
    """The frozen prospective family differed from its contract."""


def _fail(message: str) -> None:
    raise ProspectiveGenerationShadowError(message)


def arm_environments(
    base: Mapping[str, str] | None = None,
) -> dict[str, dict[str, str]]:
    """Resolve all five predeclared arms from the adopted policy."""

    policy = ADOPTED_CLASSIC_POLICY
    control = policy.boom_first_control_environment(base)
    boom_first = policy.boom_first_shadow_environment(base)
    environments = {
        "incumbent-160-40": control,
        "boom-first-40-160": boom_first,
        "cross-law-40-100-60": {
            **boom_first,
            "GEN_TOTAL_BUDGET": "112",
            "N_BOOM": "100",
            "PROSPECTIVE_SHADOW_ID": "2026-cross-law-discovery-v1",
        },
        "boom-dose-40-360": {
            **boom_first,
            "GEN_TOTAL_BUDGET": "372",
            "N_BOOM": "360",
            "PROSPECTIVE_SHADOW_ID": "2026-boom-dose-360-v1",
        },
        # This native base produces only the fixed non-core families.  The
        # isolated transform adds exactly 200 ceiling-ordered boom solves.
        "ceiling-all-boom-0-200": {
            **boom_first,
            "GEN_TOTAL_BUDGET": "12",
            "N_LEV": "0",
            "N_BOOM": "0",
            "PROSPECTIVE_SHADOW_ID": "2026-ceiling-all-boom-v1-unpassed",
        },
    }
    for environment in environments.values():
        environment["PROSPECTIVE_GENERATION_EXPOSURE"] = "1"
    validate_arm_environments(environments)
    return environments


def validate_arm_environments(
    environments: Mapping[str, Mapping[str, str]],
) -> dict[str, object]:
    if tuple(environments) != ARM_ORDER:
        _fail("prospective arm order differs")
    # Values are per one R0--R4 10,000-world block.  The environment's
    # GEN_TOTAL_BUDGET covers boom+role replacement families, not leverage.
    expected_native = {
        "incumbent-160-40": (160, 40, 52, 0),
        "boom-first-40-160": (40, 160, 172, 0),
        "cross-law-40-100-60": (40, 100, 112, 60),
        "boom-dose-40-360": (40, 360, 372, 0),
        "ceiling-all-boom-0-200": (0, 0, 12, 200),
    }
    reference = dict(environments[ARM_ORDER[0]])
    hashes: dict[str, str] = {}
    for arm in ARM_ORDER:
        environment = environments[arm]
        if not isinstance(environment, Mapping) or any(
            type(key) is not str or type(value) is not str
            for key, value in environment.items()
        ):
            _fail(f"{arm} environment is not string-to-string")
        leverage, boom, replacement_total, transformed_boom = expected_native[arm]
        if (
            environment.get("N_LEV") != str(leverage)
            or environment.get("N_BOOM") != str(boom)
            or environment.get("GEN_TOTAL_BUDGET") != str(replacement_total)
            or environment.get("PROSPECTIVE_GENERATION_EXPOSURE") != "1"
            or environment.get("MULTISEED_PORTFOLIO") != "CBWU"
            or environment.get("SELECT_LSE") != "0"
            or environment.get("SELECT_LADDER") != ""
            or environment.get("BOOM_UNIQUE_FILL", "0") not in {"", "0"}
        ):
            _fail(f"{arm} allocation or fixed selector differs")
        for key in set(reference) | set(environment):
            if key in _ENV_ARM_KEYS:
                continue
            if reference.get(key) != environment.get(key):
                _fail(f"arm environments differ outside allocation at {key}")
        hashes[arm] = canonical_sha256(dict(sorted(environment.items())))
    return {
        "arm_order": list(ARM_ORDER),
        "allocation_unit": "per-r0-r4-10000-world-block",
        "generation_blocks_per_slate": len(SEED_LABELS),
        "per_block_allocations": {
            arm: {
                "leverage": values[0],
                "base_boom": values[1],
                "role": 12,
                "transformed_boom": values[3],
                "requested_core": values[0] + values[1] + values[3],
                "requested_replacement_budget_native": values[2],
                "requested_core_plus_role": (
                    values[0] + values[1] + values[3] + 12
                ),
            }
            for arm, values in expected_native.items()
        },
        "per_slate_five_block_allocations": {
            arm: {
                "leverage": values[0] * len(SEED_LABELS),
                "base_boom": values[1] * len(SEED_LABELS),
                "role": 12 * len(SEED_LABELS),
                "transformed_boom": values[3] * len(SEED_LABELS),
                "requested_core": (
                    values[0] + values[1] + values[3]
                ) * len(SEED_LABELS),
            }
            for arm, values in expected_native.items()
        },
        "environment_sha256": hashes,
        "counts_are_per_block_not_per_slate": True,
        "equal_budget_arms_request_1000_core_solves_per_slate": True,
        "boom_dose_requests_2000_core_solves_per_slate": True,
        "all_nonallocation_environment_values_identical": True,
    }


def _validated_transform_ledger(
    arm: str,
    receipt: Mapping[str, object],
) -> dict[str, object] | None:
    if arm == "cross-law-40-100-60":
        value = receipt.get("exposure_ledger")
        expected_family, expected_count = "boom:xlaw", 60
    elif arm == "ceiling-all-boom-0-200":
        value = receipt.get("solve_exposure_ledger")
        expected_family, expected_count = "boom", 200
    else:
        if receipt:
            _fail(f"{arm} carries an undeclared native transform")
        return None
    try:
        ledger = validate_ledger(value)
    except Exception as exc:
        raise ProspectiveGenerationShadowError(
            f"{arm} transform exposure ledger differs"
        ) from exc
    if ledger["expected_requests_by_family"] != {
        expected_family: expected_count
    }:
        _fail(f"{arm} transform requested-solve census differs")
    return ledger


def _validated_per_block_work(
    arm: str,
    label: str,
    native: Mapping[str, object],
    transform_receipt: Mapping[str, object],
    *,
    reference_auxiliary: Mapping[str, int] | None,
) -> tuple[dict[str, object], dict[str, int]]:
    expected_native_core = {
        "incumbent-160-40": {"leverage": 160, "boom": 40},
        "boom-first-40-160": {"leverage": 40, "boom": 160},
        "cross-law-40-100-60": {"leverage": 40, "boom": 100},
        "boom-dose-40-360": {"leverage": 40, "boom": 360},
        "ceiling-all-boom-0-200": {"leverage": 0, "boom": 0},
    }[arm]
    ledger = validate_ledger(native)
    expected = {
        str(key): int(value)
        for key, value in ledger["expected_requests_by_family"].items()
    }
    for family, count in {
        **expected_native_core,
        "role_epistemic": 12,
    }.items():
        if expected.get(family) != count:
            _fail(f"{arm}/{label} {family} requested-solve census differs")
    auxiliary = {
        key: value
        for key, value in expected.items()
        if key not in {"leverage", "boom", "role_epistemic"}
    }
    if reference_auxiliary is not None and auxiliary != dict(
        reference_auxiliary
    ):
        _fail(f"{arm}/{label} frozen auxiliary-family census differs")
    transform = _validated_transform_ledger(
        arm, transform_receipt
    )
    transformed_core = 0 if transform is None else sum(
        int(value)
        for value in transform["expected_requests_by_family"].values()
    )
    native_core = expected["leverage"] + expected["boom"]
    expected_composite = 400 if arm == "boom-dose-40-360" else 200
    if native_core + transformed_core != expected_composite:
        _fail(f"{arm}/{label} composite core-solve census differs")
    return ({
        "unit": "one-10000-world-generation-block",
        "native_ledger_sha256": ledger["ledger_sha256"],
        "native_expected_requests_by_family": expected,
        "native_status_counts": ledger["status_counts"],
        "native_duration_seconds_by_family": ledger[
            "duration_seconds_by_family"
        ],
        "native_total_duration_seconds": ledger["total_duration_seconds"],
        "transform_ledger_sha256": (
            None if transform is None else transform["ledger_sha256"]
        ),
        "transform_expected_requests_by_family": (
            {} if transform is None else transform[
                "expected_requests_by_family"
            ]
        ),
        "transform_status_counts": (
            {} if transform is None else transform["status_counts"]
        ),
        "transform_duration_seconds_by_family": (
            {} if transform is None else transform[
                "duration_seconds_by_family"
            ]
        ),
        "requested_composite_core": native_core + transformed_core,
        "requested_role": expected["role_epistemic"],
        "natural_uniqueness_collisions_failures_and_runtime_receipted": True,
    }, auxiliary)


def _draft_group_lock_at(store, draft_group_id: int) -> datetime:
    slates = store.classic_slates()
    required = {"draft_group_id", "game_start"}
    if not required <= set(slates.columns):
        _fail("classic slate authority lacks draft-group lock fields")
    group = slates[slates["draft_group_id"] == draft_group_id]
    if group.empty:
        _fail("draft group is absent from classic slate authority")
    starts = pd.to_datetime(group["game_start"], utc=True, errors="coerce")
    if starts.isna().any():
        _fail("draft group carries an invalid game start")
    return starts.min().to_pydatetime().astimezone(timezone.utc)


def _candidate_totals_for_draws(
    batch: CandidateBatch,
    row_draws: np.ndarray,
) -> np.ndarray:
    draws = np.asarray(row_draws)
    if (
        draws.ndim != 2
        or draws.shape[0] != len(batch.player_ids)
        or not np.isfinite(draws).all()
    ):
        _fail("candidate scoring world bank differs")
    row_by_id = {
        player_id: index for index, player_id in enumerate(batch.player_ids)
    }
    try:
        return np.stack([
            draws[[
                row_by_id[player["id"]] for player in lineup.players
            ]].sum(axis=0)
            for lineup in batch.candidates
        ]).astype(np.float32)
    except (KeyError, TypeError) as exc:
        raise ProspectiveGenerationShadowError(
            "candidate roster escapes the shared player bank"
        ) from exc


def build_independent_audit_world_bank(
    *,
    season: int,
    week: int,
    allowed_ids: set,
    salary_overrides: Mapping[int, int],
    policy_env: Mapping[str, str],
    model_variant: str,
    expected_model_k: int,
    expected_player_ids: Sequence[object],
    expected_model_version: str,
) -> tuple[np.ndarray, dict[str, object]]:
    """Build one score-only world bank; no candidate solve or selection runs."""

    from .live_lineups import build_slate_with_draws
    from ..backtest.engine import _row_draws

    audit_env = dict(policy_env)
    audit_env["MULTISEED_SOURCE_LABEL"] = "AUDIT"
    slate, raw_draws = build_slate_with_draws(
        season,
        week,
        n_sims=AUDIT_WORLD_COUNT,
        seed=AUDIT_WORLD_SEED,
        lev_scale=1.0,
        apply_notes=False,
        model_variant=model_variant,
        allowed_ids=allowed_ids,
        salary_overrides=dict(salary_overrides),
        policy_env=audit_env,
        expected_model_k=expected_model_k,
        route_source_policy=False,
        log_ownership_shadow=False,
    )
    expected = list(expected_player_ids)
    if set(slate["id"]) != set(expected):
        _fail("independent audit bank player universe differs")
    slate = slate.set_index("id", drop=False).loc[expected].reset_index(drop=True)
    if list(slate["id"]) != expected:
        _fail("independent audit bank player order differs")
    model_version = str(slate.attrs.get("model_version") or "")
    if not model_version or model_version != expected_model_version:
        _fail("independent audit bank fitted model identity differs")
    draws = np.asarray(_row_draws(slate, raw_draws, env=audit_env), dtype=np.float32)
    if draws.shape != (len(expected), AUDIT_WORLD_COUNT):
        _fail("independent audit world matrix shape differs")
    receipt = {
        "schema_version": "prospective-generation-independent-audit-bank/v1",
        "world_seed": AUDIT_WORLD_SEED,
        "world_count": AUDIT_WORLD_COUNT,
        "model_version": model_version,
        "player_order_sha256": canonical_sha256([str(value) for value in expected]),
        "world_bank_receipt": _array_receipt(draws),
        "candidate_solves_run": 0,
        "used_for_selection": False,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return draws, receipt


def _selected_for_batch(
    arm: str,
    batch: CandidateBatch,
    returned: Sequence[Lineup],
    environment: Mapping[str, str],
) -> list[Lineup]:
    if len(batch.candidates) < ENTRIES:
        _fail(f"{arm} candidate pool is below exact-80")
    indices = select_tail_entries(
        batch.candidate_totals, ENTRIES, TAIL_LINE, env=environment
    )
    expected = [batch.candidates[index] for index in indices]
    if (
        len(expected) != ENTRIES
        or len(returned) != ENTRIES
        or [lineup.ids for lineup in returned]
        != [lineup.ids for lineup in expected]
        or len({lineup.ids for lineup in returned}) != ENTRIES
    ):
        _fail(f"{arm} returned book differs from exact coverage-194 order")
    return expected


def _recomputed_candidate_totals(batch: CandidateBatch) -> np.ndarray:
    return _candidate_totals_for_draws(batch, np.asarray(batch.row_draws))


def multiarm_prelock_receipt(
    batches: Mapping[str, CandidateBatch],
    selected: Mapping[str, Sequence[Lineup]],
    dk_id_by_player_id: Mapping[object, str | int],
    environments: Mapping[str, Mapping[str, str]],
    *,
    audit_row_draws: np.ndarray,
    audit_bank_receipt: Mapping[str, object],
) -> dict[str, object]:
    """Validate and hash every pool/book without reading an outcome."""

    environment_contract = validate_arm_environments(environments)
    if tuple(batches) != ARM_ORDER or tuple(selected) != ARM_ORDER:
        _fail("prospective multiarm batch/book grid differs")
    base = batches[ARM_ORDER[0]]
    _validate_candidate_batch(base)
    world_receipt = _array_receipt(base.row_draws)
    audit_draws = np.asarray(audit_row_draws, dtype=np.float32)
    if audit_draws.shape != (len(base.player_ids), AUDIT_WORLD_COUNT):
        _fail("independent audit bank shape differs")
    if not np.isfinite(audit_draws).all():
        _fail("independent audit bank is nonfinite")
    if any(
        np.array_equal(
            audit_draws,
            np.asarray(base.row_draws)[
                :, block * WORLDS_PER_BLOCK:(block + 1) * WORLDS_PER_BLOCK
            ],
        )
        for block in range(len(SEED_LABELS))
    ):
        _fail("independent audit bank repeats a selection/generation block")
    audit_receipt = dict(audit_bank_receipt)
    retained_audit_hash = audit_receipt.pop("receipt_sha256", None)
    if (
        retained_audit_hash != canonical_sha256(audit_receipt)
        or audit_receipt.get("world_bank_receipt") != _array_receipt(audit_draws)
        or audit_receipt.get("candidate_solves_run") != 0
        or audit_receipt.get("used_for_selection") is not False
        or audit_receipt.get("uses_realized_outcomes") is not False
    ):
        _fail("independent audit-bank receipt differs")
    audit_receipt["receipt_sha256"] = retained_audit_hash
    if base.metadata.get("portfolio") != "CBWU":
        _fail("prospective control is not a CBWU batch")
    arm_receipts: dict[str, object] = {}
    memberships: dict[str, dict[str, list[list[str]]]] = {
        str(prefix): {} for prefix in PREFIXES
    }
    model_versions: set[tuple[str, str]] = set()
    reference_auxiliary_by_label: dict[str, dict[str, int]] = {}
    for arm in ARM_ORDER:
        batch = batches[arm]
        _validate_candidate_batch(batch)
        if (
            batch.metadata.get("portfolio") != "CBWU"
            or batch.metadata.get("world_blocks") != 5
            or batch.metadata.get("worlds_per_block") != [10_000] * 5
            or batch.player_ids != base.player_ids
            or not np.array_equal(batch.row_draws, base.row_draws)
        ):
            _fail(f"{arm} does not share the exact CBWU selection bank")
        recomputed = _recomputed_candidate_totals(batch)
        if not np.array_equal(recomputed, batch.candidate_totals):
            _fail(f"{arm} candidate totals are not from the base bank")
        expected = _selected_for_batch(
            arm, batch, selected[arm], environments[arm]
        )
        native_ledgers = batch.metadata.get(
            "native_generation_exposure_ledgers"
        )
        if not isinstance(native_ledgers, Mapping) or set(native_ledgers) != set(
            SEED_LABELS
        ):
            _fail(f"{arm} native exposure-ledger grid differs")
        normalized_ledgers = {
            label: validate_ledger(native_ledgers[label])
            for label in SEED_LABELS
        }
        transform_receipts = batch.metadata.get(
            "native_generation_transform_receipts"
        )
        if not isinstance(transform_receipts, Mapping) or set(
            transform_receipts
        ) != set(SEED_LABELS):
            _fail(f"{arm} native transform-receipt grid differs")
        expected_transform = (
            "cross_law_discovery" if arm == "cross-law-40-100-60"
            else "all_boom_ceiling" if arm == "ceiling-all-boom-0-200"
            else None
        )
        block_work: dict[str, object] = {}
        for label in SEED_LABELS:
            keys = set(transform_receipts[label])
            if keys != ({expected_transform} if expected_transform else set()):
                _fail(f"{arm}/{label} transform receipt differs")
            transform_value = (
                {}
                if expected_transform is None
                else transform_receipts[label][expected_transform]
            )
            block_receipt, auxiliary = _validated_per_block_work(
                arm,
                label,
                normalized_ledgers[label],
                transform_value,
                reference_auxiliary=(
                    None
                    if arm == ARM_ORDER[0]
                    else reference_auxiliary_by_label[label]
                ),
            )
            if arm == ARM_ORDER[0]:
                reference_auxiliary_by_label[label] = auxiliary
            block_work[label] = block_receipt
        rosters = [
            _canonical_dk_roster(lineup, dict(dk_id_by_player_id))
            for lineup in expected
        ]
        candidate_rosters = [
            _canonical_dk_roster(lineup, dict(dk_id_by_player_id))
            for lineup in batch.candidates
        ]
        for prefix in PREFIXES:
            memberships[str(prefix)][arm] = rosters[:prefix]
        main = {
            str(getattr(lineup, "model_version", "") or "")
            for lineup in expected
        }
        role = {
            str(getattr(lineup, "role_model_version", "") or "")
            for lineup in expected
        }
        if len(main) != 1 or not next(iter(main)) or len(role) != 1 or not next(
            iter(role)
        ):
            _fail(f"{arm} selected model identity is not singular")
        model_versions.add((next(iter(main)), next(iter(role))))
        arm_receipts[arm] = {
            "candidate_count": len(batch.candidates),
            "selected_count": ENTRIES,
            "candidate_order_sha256": canonical_sha256(candidate_rosters),
            "selected_order_sha256": canonical_sha256(rosters),
            "candidate_matrix_receipt": _array_receipt(
                batch.candidate_totals
            ),
            "native_exposure_ledger_sha256": {
                label: normalized_ledgers[label]["ledger_sha256"]
                for label in SEED_LABELS
            },
            "native_transform_receipt_sha256": {
                label: {
                    key: str(value.get("receipt_sha256") or "")
                    for key, value in transform_receipts[label].items()
                }
                for label in SEED_LABELS
            },
            "per_block_requested_work": block_work,
            "simulated_diagnostics": _simulated_diagnostics(
                batch, expected
            ),
            "independent_audit_diagnostics": _simulated_diagnostics(
                batch,
                expected,
                candidate_totals=_candidate_totals_for_draws(
                    batch, audit_draws
                ),
            ),
        }
    if len(model_versions) != 1:
        _fail("prospective arms used different fitted model identities")
    _cap4_books, retrieval_crossing = build_generation_retrieval_crossing(
        {arm: batches[arm] for arm in RETRIEVAL_POPULATION_ORDER},
        {arm: selected[arm] for arm in RETRIEVAL_POPULATION_ORDER},
        dk_id_by_player_id,
        independent_audit_row_draws=audit_draws,
    )
    cross_arm = {}
    for challenger, comparator in COMPARATOR_BY_ARM.items():
        challenger_pool = {
            lineup.ids for lineup in batches[challenger].candidates
        }
        comparator_pool = {
            lineup.ids for lineup in batches[comparator].candidates
        }
        challenger_book = [lineup.ids for lineup in selected[challenger]]
        comparator_book = [lineup.ids for lineup in selected[comparator]]
        pool_union = challenger_pool | comparator_pool
        book_union = set(challenger_book) | set(comparator_book)
        cross_arm[challenger] = {
            "comparator": comparator,
            "candidate_jaccard": (
                len(challenger_pool & comparator_pool) / len(pool_union)
            ),
            "selected_jaccard": (
                len(set(challenger_book) & set(comparator_book))
                / len(book_union)
            ),
            "selected_prefix_overlap": {
                str(prefix): len(
                    set(challenger_book[:prefix])
                    & set(comparator_book[:prefix])
                )
                for prefix in PREFIXES
            },
            "historical_gain_added_to_comparator": False,
        }
    receipt = {
        "schema_version": "prospective-generation-multiarm-prelock/v2",
        "suite_version": VERSION,
        "registry": validate_registry(registry_document()),
        "environment_contract": environment_contract,
        "tail_line": TAIL_LINE,
        "entries": ENTRIES,
        "prefixes": list(PREFIXES),
        "thresholds": list(THRESHOLDS),
        "player_worlds_identical_across_all_arms": True,
        "player_worlds_receipt": world_receipt,
        "independent_audit_world_bank": audit_receipt,
        "audit_world_bank_distinct_from_all_five_selection_blocks": True,
        "audit_world_bank_used_for_selection": False,
        "model_version": next(iter(model_versions))[0],
        "role_model_version": next(iter(model_versions))[1],
        "arm_receipts": arm_receipts,
        "generation_retrieval_crossing": retrieval_crossing,
        "generation_retrieval_crossing_sha256": retrieval_crossing[
            "receipt_sha256"
        ],
        "paired_comparisons": cross_arm,
        "memberships": memberships,
        "memberships_sha256": canonical_sha256(memberships),
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
        "production_enabled": False,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def _simulated_diagnostics(
    batch: CandidateBatch,
    selected: Sequence[Lineup],
    *,
    candidate_totals: np.ndarray | None = None,
) -> dict[str, object]:
    totals = (
        np.asarray(batch.candidate_totals)
        if candidate_totals is None
        else np.asarray(candidate_totals)
    )
    if totals.shape[0] != len(batch.candidates) or totals.ndim != 2:
        _fail("simulated diagnostic candidate matrix differs")
    index_by_roster = {
        lineup.ids: index for index, lineup in enumerate(batch.candidates)
    }
    selected_rows = np.asarray([
        totals[index_by_roster[lineup.ids]]
        for lineup in selected
    ])
    by_prefix: dict[str, object] = {}
    for prefix in PREFIXES:
        matrix = selected_rows[:prefix]
        maxima = matrix.max(axis=0)
        by_prefix[str(prefix)] = {
            "simulated_mean_max": float(maxima.mean()),
            "simulated_p_max_at_least": {
                str(threshold): float((maxima >= threshold).mean())
                for threshold in THRESHOLDS
            },
        }
    by_family: dict[str, list[int]] = {}
    for index, lineup in enumerate(batch.candidates):
        for tag in batch.all_tags.get(
            lineup.ids, (lineup.tag or "unknown",)
        ):
            by_family.setdefault(str(tag), []).append(index)
    selected_family_counts: dict[str, int] = {}
    for lineup in selected:
        for tag in batch.all_tags.get(
            lineup.ids, (lineup.tag or "unknown",)
        ):
            key = str(tag)
            selected_family_counts[key] = selected_family_counts.get(key, 0) + 1
    return {
        "probabilities_are_descriptive_not_calibrated": True,
        "coverage_line_label": "optimistic-194",
        "prefixes": by_prefix,
        "selected_family_counts": dict(sorted(selected_family_counts.items())),
        "candidate_family_tail_rates": {
            family: {
                str(threshold): float(
                    (totals[indices] >= threshold).mean()
                )
                for threshold in THRESHOLDS
            }
            for family, indices in sorted(by_family.items())
        },
    }


def _json_create_only(
    storage_client,
    *,
    bucket_name: str,
    object_name: str,
    value: Mapping[str, object],
    must_precede: datetime,
) -> dict[str, object]:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    blob = storage_client.bucket(bucket_name).blob(object_name)
    blob.upload_from_string(
        payload,
        content_type="application/json",
        if_generation_match=0,
    )
    reload_blob = getattr(blob, "reload", None)
    if not callable(reload_blob):
        _fail("create-only JSON object cannot prove trusted creation time")
    reload_blob()
    generation = getattr(blob, "generation", None)
    if generation in (None, ""):
        _fail("create-only JSON object lacks its durable GCS generation")
    created = getattr(blob, "time_created", None)
    if (
        created is None
        or getattr(created, "tzinfo", None) is None
        or created.utcoffset() is None
    ):
        _fail("create-only JSON object lacks trusted GCS creation time")
    created = created.astimezone(timezone.utc)
    if created >= must_precede:
        _fail("create-only JSON object was not frozen before slate lock")
    return {
        "uri": f"gs://{bucket_name}/{object_name}",
        "generation": int(generation),
        "sha256": canonical_sha256(value),
        "bytes": len(payload),
        "gcs_time_created": created.isoformat(),
        "precedes_slate_lock": True,
        "create_only": True,
    }


def run(
    *,
    store=None,
    season: int | None = None,
    week: int | None = None,
    draft_group_id: int | None = None,
    expected_lock_at: datetime | str | None = None,
    generated_at: datetime | None = None,
    storage_client=None,
    bucket_name: str | None = None,
) -> dict[str, object]:
    """Build all arms, freeze artifacts, then publish one terminal root."""

    started = time.perf_counter()
    code_sha = _validated_code_sha(os.environ.get("CODE_SHA"))
    image_source_commit_sha = str(
        os.environ.get("IMAGE_SOURCE_COMMIT_SHA") or ""
    ).strip().lower()
    if (
        re.fullmatch(r"[0-9a-f]{40}", code_sha) is None
        or image_source_commit_sha != code_sha
    ):
        _fail("generation-shadow image source commit differs from CODE_SHA")
    image_uri = _validated_image_uri(os.environ.get("IMAGE_URI"))
    cloud_context = _validated_cloud_execution_context(os.environ)
    if store is None:
        from ..app.store import BigQueryStore

        store = BigQueryStore()
    if (
        season is None
        or week is None
        or draft_group_id is None
        or expected_lock_at is None
    ):
        _fail(
            "season, week, draft_group_id, and expected_lock_at must be "
            "supplied explicitly; automatic slate selection is forbidden"
        )
    season, week, draft_group_id = int(season), int(week), int(draft_group_id)
    if season != 2026 or not 1 <= week <= 18:
        _fail("generation-shadow suite v1 is frozen to the 2026 season")
    stamp = generated_at or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        _fail("generation-shadow generated_at must be timezone-aware")
    stamp = stamp.astimezone(timezone.utc)
    lock_at = _draft_group_lock_at(store, draft_group_id)
    if isinstance(expected_lock_at, str):
        try:
            expected_lock = datetime.fromisoformat(
                expected_lock_at.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise ProspectiveGenerationShadowError(
                "expected_lock_at is not an ISO-8601 timestamp"
            ) from exc
    elif isinstance(expected_lock_at, datetime):
        expected_lock = expected_lock_at
    else:  # Defensive even though the missing-value branch above has fired.
        _fail("expected_lock_at must be an ISO-8601 timestamp")
    if (
        expected_lock.tzinfo is None
        or expected_lock.utcoffset() is None
        or expected_lock.astimezone(timezone.utc) != lock_at
    ):
        _fail("supplied slate lock differs from the frozen draft-group authority")
    if stamp >= lock_at:
        _fail("generation-shadow suite started at or after slate lock")
    run_id = (
        f"prospective-generation-{season}w{week:02d}-"
        f"{cloud_context['cloud_run_execution']}"
    )
    bucket = bucket_name or settings.gcs_bucket
    root = f"generation_shadow/{season}/week-{week:02d}/{run_id}"
    allowed, salary_overrides, dk_mapping = _slate_identity(
        store, draft_group_id
    )
    policy = ADOPTED_CLASSIC_POLICY
    construction = policy.construction_preset()
    constraint_contract = validate_constraint_contract(construction.stack)
    environments = arm_environments(os.environ)
    common = {
        "season": season,
        "week": week,
        "n_entries": ENTRIES,
        "stack": construction.stack,
        "tail_line": TAIL_LINE,
        "lev_scale": 1.0,
        "allowed_ids": allowed,
        "salary_overrides": salary_overrides,
        "apply_notes": False,
        "model_variant": policy.model_variant,
        "cand_log_table": f"{settings.predictions}.live_candidates_shadow",
        "cand_log_async": False,
        "cand_log_required": True,
        "expected_model_k": policy.model_ensemble,
        "belief_model_variant": policy.role_model_variant,
        "construction_preset_receipt": construction.receipt(),
    }

    from .live_lineups import build_sim_lineups

    batches: dict[str, CandidateBatch] = {}
    books: dict[str, list[Lineup]] = {}
    build_seconds: dict[str, float] = {}
    cross_law_native_batches: dict[str, CandidateBatch] = {}
    for arm in ARM_ORDER:
        environment = environments[arm]
        native_transform = None
        if arm == "cross-law-40-100-60":
            def _cross_law_transform(
                label: str,
                batch: CandidateBatch,
                env=environment,
            ) -> CandidateBatch:
                transformed = build_cross_law_discovery_batch(
                    batch,
                    season=season,
                    week=week,
                    cbwu_seed_label=label,
                    stack=construction.stack,
                    policy_env=env,
                    locks=frozenset(),
                )
                cross_law_native_batches[label] = transformed
                return transformed

            native_transform = _cross_law_transform
        elif arm == "ceiling-all-boom-0-200":
            from .prospective_all_boom_ceiling import (
                all_boom_ceiling_environment,
                build_all_boom_ceiling_batch,
            )

            ceiling_environment = all_boom_ceiling_environment(os.environ)
            native_transform = lambda label, batch, env=ceiling_environment: (
                build_all_boom_ceiling_batch(
                    batch,
                    batch,
                    stack=construction.stack,
                    locks=frozenset(),
                    env=env,
                    construction_preset_receipt=construction.receipt(),
                    source_label=label.lower(),
                )
            )
        captured: list[CandidateBatch] = []
        arm_started = time.perf_counter()
        books[arm] = build_sim_lineups(
            **common,
            panel_run_id=f"{run_id}-{arm}",
            candidate_run_type=f"prospective_generation_{arm}",
            policy_env=environment,
            _candidate_capture=captured.append,
            _native_candidate_transform=native_transform,
        )
        build_seconds[arm] = float(time.perf_counter() - arm_started)
        if len(captured) != 1:
            _fail(f"{arm} did not capture exactly one combined book")
        batches[arm] = captured[0]

    if set(cross_law_native_batches) != set(SEED_LABELS):
        _fail("cross-law native block capture differs")

    control_batch = batches[ARM_ORDER[0]]
    native_receipts = control_batch.metadata.get(
        "native_generation_receipts"
    )
    if not isinstance(native_receipts, Mapping):
        _fail("control batch lacks native generation receipts")
    r0_receipt = native_receipts.get("R0")
    if not isinstance(r0_receipt, Mapping):
        _fail("control batch lacks its R0 generation receipt")
    expected_model_version = str(r0_receipt.get("model_version") or "")
    if not expected_model_version:
        _fail("control batch lacks its fitted model identity")
    audit_draws, audit_bank_receipt = build_independent_audit_world_bank(
        season=season,
        week=week,
        allowed_ids=set(allowed),
        salary_overrides=salary_overrides,
        policy_env=environments[ARM_ORDER[0]],
        model_variant=policy.model_variant,
        expected_model_k=policy.model_ensemble,
        expected_player_ids=control_batch.player_ids,
        expected_model_version=expected_model_version,
    )
    prelock = multiarm_prelock_receipt(
        batches,
        books,
        dk_mapping,
        environments,
        audit_row_draws=audit_draws,
        audit_bank_receipt=audit_bank_receipt,
    )
    identity_bridge = player_identity_bridge(batches[ARM_ORDER[0]], dk_mapping)
    context = {
        "suite_version": VERSION,
        "run_id": run_id,
        "season": season,
        "week": week,
        "draft_group_id": draft_group_id,
        "slate_lock_at": lock_at.isoformat(),
        "code_sha": code_sha,
        "image_source_commit_sha": image_source_commit_sha,
        "image_uri": image_uri,
        **cloud_context,
        "production_policy": policy.policy_id,
        "registry_sha256": prelock["registry"]["registry_sha256"],
    }
    artifacts: dict[str, object] = {}
    discovery_world_artifacts: dict[str, object] = {}
    if datetime.now(timezone.utc) >= lock_at:
        _fail("generation-shadow candidate builds did not finish before lock")
    for arm in ARM_ORDER:
        artifact = persist_recourse_world_artifact(
            _artifact_batch_without_runtime_timing(batches[arm]),
            dk_mapping,
            generated_at=stamp,
            bucket_name=bucket,
            object_name=f"{root}/arms/{arm}.npz",
            context={**context, "arm": arm},
            storage_client=storage_client,
            require_trusted_creation_time=True,
        )
        if (
            artifact.get("create_only") is not True
            or not isinstance(artifact.get("generation"), int)
            or not artifact.get("gcs_time_created")
            or datetime.fromisoformat(
                str(artifact["gcs_time_created"])
            ).astimezone(timezone.utc) >= lock_at
        ):
            _fail(
                f"{arm} world artifact lacks a trusted prelock identity"
            )
        artifacts[arm] = artifact
    for label in SEED_LABELS:
        native = cross_law_native_batches[label]
        raw_receipt = native.metadata.get("cross_law_discovery")
        if not isinstance(raw_receipt, Mapping):
            _fail(f"cross-law {label} lacks its discovery receipt")
        discovery_draws = rebuild_cross_law_discovery_world_matrix(
            native, raw_receipt
        )
        discovery_batch = CandidateBatch(
            candidates=native.candidates,
            candidate_totals=_candidate_totals_for_draws(
                native, discovery_draws
            ),
            player_ids=native.player_ids,
            player_rows=native.player_rows,
            row_draws=discovery_draws,
            all_tags=native.all_tags,
            metadata={
                "artifact_role": "cross-law-generation-only-discovery-bank",
                "cbwu_seed_label": label,
                "cross_law_discovery_receipt": dict(raw_receipt),
                "used_for_selection": False,
                "uses_realized_outcomes": False,
                "post_lock_data_read": False,
            },
        )
        discovery_artifact = persist_recourse_world_artifact(
            discovery_batch,
            dk_mapping,
            generated_at=stamp,
            bucket_name=bucket,
            object_name=f"{root}/cross-law-discovery/{label}.npz",
            context={
                **context,
                "arm": "cross-law-40-100-60",
                "artifact_role": "generation-only-discovery-world-bank",
                "cbwu_seed_label": label,
            },
            storage_client=storage_client,
            require_trusted_creation_time=True,
        )
        if (
            discovery_artifact.get("create_only") is not True
            or not isinstance(discovery_artifact.get("generation"), int)
            or not discovery_artifact.get("gcs_time_created")
            or datetime.fromisoformat(
                str(discovery_artifact["gcs_time_created"])
            ).astimezone(timezone.utc) >= lock_at
        ):
            _fail(
                f"cross-law {label} discovery artifact lacks a trusted "
                "prelock identity"
            )
        discovery_world_artifacts[label] = discovery_artifact
    audit_batch = CandidateBatch(
        candidates=control_batch.candidates,
        candidate_totals=_candidate_totals_for_draws(
            control_batch, audit_draws
        ),
        player_ids=control_batch.player_ids,
        player_rows=control_batch.player_rows,
        row_draws=audit_draws,
        all_tags=control_batch.all_tags,
        metadata={
            "artifact_role": "independent-score-only-audit-world-bank",
            "audit_bank_receipt": audit_bank_receipt,
            "candidate_solves_run": 0,
            "used_for_selection": False,
            "uses_realized_outcomes": False,
            "post_lock_data_read": False,
        },
    )
    audit_artifact = persist_recourse_world_artifact(
        audit_batch,
        dk_mapping,
        generated_at=stamp,
        bucket_name=bucket,
        object_name=f"{root}/audit/independent-world-bank.npz",
        context={**context, "arm": "independent-audit-world-bank"},
        storage_client=storage_client,
        require_trusted_creation_time=True,
    )
    if (
        audit_artifact.get("create_only") is not True
        or not isinstance(audit_artifact.get("generation"), int)
        or not audit_artifact.get("gcs_time_created")
        or datetime.fromisoformat(
            str(audit_artifact["gcs_time_created"])
        ).astimezone(timezone.utc) >= lock_at
    ):
        _fail("independent audit artifact lacks a trusted prelock identity")
    cross_law_persistence_binding = {
        "schema_version": "prospective-cross-law-persisted-world-binding/v1",
        "base_selection_world_artifact": {
            key: artifacts["cross-law-40-100-60"].get(key)
            for key in (
                "uri", "generation", "sha256", "gcs_time_created", "create_only"
            )
        },
        "discovery_generation_world_artifacts": {
            label: {
                key: discovery_world_artifacts[label].get(key)
                for key in (
                    "uri", "generation", "sha256", "gcs_time_created", "create_only"
                )
            }
            for label in SEED_LABELS
        },
        "independent_audit_world_artifact": {
            key: audit_artifact.get(key)
            for key in (
                "uri", "generation", "sha256", "gcs_time_created", "create_only"
            )
        },
        "per_block_influence_trace_sha256": {
            label: str(
                cross_law_native_batches[label].metadata[
                    "cross_law_discovery"
                ]["production_influence_trace_sha256"]
            )
            for label in SEED_LABELS
        },
        "discovery_worlds_used_for_generation_only": True,
        "all_selection_scores_from_untouched_base_bank": True,
        "audit_worlds_used_for_selection": False,
        "all_objects_create_only_and_prelock": True,
        "uses_realized_outcomes": False,
    }
    cross_law_persistence_binding["binding_sha256"] = canonical_sha256(
        cross_law_persistence_binding
    )
    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client()
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        **context,
        "generated_at": stamp.isoformat(),
        "constraint_contract": constraint_contract,
        "prelock_receipt": prelock,
        "player_identity_bridge": identity_bridge,
        "player_identity_bridge_sha256": canonical_sha256(identity_bridge),
        "environment_receipts": {
            arm: {
                "sha256": canonical_sha256(
                    dict(sorted(environments[arm].items()))
                ),
                "values": dict(sorted(environments[arm].items())),
            }
            for arm in ARM_ORDER
        },
        "world_artifacts": artifacts,
        "cross_law_discovery_world_artifacts": discovery_world_artifacts,
        "cross_law_persistence_binding": cross_law_persistence_binding,
        "independent_audit_world_artifact": audit_artifact,
        "build_seconds": build_seconds,
        "elapsed_before_manifest_seconds": float(
            time.perf_counter() - started
        ),
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
        "production_enabled": False,
    }
    manifest_receipt = _json_create_only(
        storage_client,
        bucket_name=bucket,
        object_name=f"{root}/manifest.json",
        value=manifest,
        must_precede=lock_at,
    )
    terminal = {
        "schema_version": TERMINAL_SCHEMA,
        "complete": True,
        **context,
        "manifest": manifest_receipt,
        "world_artifacts": {
            arm: {
                key: artifacts[arm].get(key)
                for key in (
                    "uri",
                    "generation",
                    "sha256",
                    "bytes",
                    "gcs_time_created",
                    "create_only",
                )
            }
            for arm in ARM_ORDER
        },
        "independent_audit_world_artifact": {
            key: audit_artifact.get(key)
            for key in (
                "uri",
                "generation",
                "sha256",
                "bytes",
                "gcs_time_created",
                "create_only",
            )
        },
        "cross_law_discovery_world_artifacts": {
            label: {
                key: discovery_world_artifacts[label].get(key)
                for key in (
                    "uri",
                    "generation",
                    "sha256",
                    "bytes",
                    "gcs_time_created",
                    "create_only",
                )
            }
            for label in SEED_LABELS
        },
        "cross_law_persistence_binding": cross_law_persistence_binding,
        "memberships_sha256": prelock["memberships_sha256"],
        "generation_retrieval_crossing_sha256": prelock[
            "generation_retrieval_crossing_sha256"
        ],
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
        "production_enabled": False,
    }
    terminal["terminal_receipt_sha256"] = canonical_sha256(terminal)
    terminal_receipt = _json_create_only(
        storage_client,
        bucket_name=bucket,
        object_name=f"{root}/terminal.json",
        value=terminal,
        must_precede=lock_at,
    )
    return {
        **manifest,
        "manifest_receipt": manifest_receipt,
        "terminal_receipt": terminal_receipt,
        "complete": True,
    }


def main(
    *,
    season: int,
    week: int,
    draft_group_id: int,
    expected_lock_at: datetime | str,
) -> None:
    result = run(
        season=season,
        week=week,
        draft_group_id=draft_group_id,
        expected_lock_at=expected_lock_at,
    )
    print(json.dumps({
        "complete": result["complete"],
        "run_id": result["run_id"],
        "cloud_run_execution": result["cloud_run_execution"],
        "manifest": result["manifest_receipt"],
        "terminal": result["terminal_receipt"],
        "registry_sha256": result["registry_sha256"],
        "production_enabled": False,
    }, sort_keys=True))


__all__ = [
    "ARM_ORDER",
    "COMPARATOR_BY_ARM",
    "ENTRIES",
    "PREFIXES",
    "TAIL_LINE",
    "THRESHOLDS",
    "VERSION",
    "arm_environments",
    "main",
    "multiarm_prelock_receipt",
    "run",
    "validate_arm_environments",
]
