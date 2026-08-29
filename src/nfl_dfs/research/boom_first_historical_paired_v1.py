"""Production-shaped, score-blind boom-first historical comparison core.

This module deliberately does not query BigQuery, GCS, or a realized-score
table.  A caller supplies one outcome-blind native-book builder and explicit
content identities for the point-in-time slate inputs.  The core invokes that
builder for the production R0--R4 seed pairs under the exact incumbent and
boom-first allocations, verifies identical player worlds, applies production
CBWU and line-194 coverage selection, and freezes the ordered 80-entry books.

Target-slate realized scoring is a separate function.  It accepts only the
development seasons (2023 and 2024), revalidates the score-blind receipt, and
joins an explicit realized-outcome mapping after selection has already been
hashed.  Prior-season realized labels may still train a later target season in
the injected walk-forward builder; receipts therefore make the narrower and
accurate no-target-slate-outcome claim.  The sealed 2025 season is rejected at
every public boundary.

The injected-builder seam is intentional.  The existing generic historical
replay constructs one native seed book and cannot reproduce the five-book
production CBWU path without modifying established replay code.  Keeping the
scientific core here allows a later thin data adapter while preserving the
new-file-only integration boundary.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re
from typing import Any

import numpy as np

from ..backtest.engine import CandidateBatch, _validate_candidate_batch
from ..inference.multiseed_portfolio import combine_cbwu_books
from ..inference.production_policy import ADOPTED_CLASSIC_POLICY
from ..optimizer.lineup import select_tail_entries


SELECTION_SCHEMA = "boom-first-historical-paired-selection/v1"
GRADE_SCHEMA = "boom-first-historical-paired-grade/v1"
DEVELOPMENT_SEASONS = frozenset({2023, 2024})
SEALED_OUTCOME_SEASONS = frozenset({2025})
PREFIX_SIZES = (20, 40, 80)
TAIL_LINE = 194.0
TAIL_THRESHOLDS = (194, 200, 210, 220, 230)
ENTRIES = 80
ARM_ORDER = ("control", "treatment")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_CODE_SHA = re.compile(r"^[0-9a-f]{7,40}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")
_FORBIDDEN_OUTCOME_FIELDS = frozenset({
    "actual",
    "actual_score",
    "dk_points",
    "final_score",
    "realized_score",
    "contest_rank",
    "payout",
    "roi",
})


class BoomFirstHistoricalPairedError(ValueError):
    """Raised when the paired historical contract cannot be proved."""


@dataclass(frozen=True)
class DevelopmentSlate:
    """One outcome-blind development-panel slate and its content identity."""

    season: int
    week: int
    slate_id: str
    source_identity: Mapping[str, object]

    def __post_init__(self) -> None:
        if type(self.season) is not int or type(self.week) is not int:
            raise BoomFirstHistoricalPairedError(
                "development slate season/week must be exact integers"
            )
        season = int(self.season)
        week = int(self.week)
        slate_id = str(self.slate_id)
        if season in SEALED_OUTCOME_SEASONS or season not in DEVELOPMENT_SEASONS:
            raise BoomFirstHistoricalPairedError(
                "boom-first historical comparison permits only development "
                "seasons 2023 and 2024; sealed 2025 is forbidden"
            )
        if not 1 <= week <= 18:
            raise BoomFirstHistoricalPairedError("development slate week differs")
        if slate_id != f"{season}-w{week:02d}":
            raise BoomFirstHistoricalPairedError(
                "development slate ID must be canonical season-week"
            )


@dataclass(frozen=True)
class DevelopmentPanelAuthority:
    """Immutable authority for the exact historical slate membership.

    An authority is optional for fixture/smoke construction.  Without one the
    resulting receipt is explicitly not ready to satisfy Gate H1.  When it is
    supplied, its ordered slate membership must exactly match the constructed
    panel and its content identity is frozen into the scientific receipt.
    """

    panel_id: str
    expected_slate_ids: Sequence[str]
    identity: Mapping[str, object]


NativeBookBuilder = Callable[
    [DevelopmentSlate, str, str, int, int, Mapping[str, str]], CandidateBatch
]


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _content_identity(value: Mapping[str, object], *, label: str) -> dict:
    if not isinstance(value, Mapping):
        raise BoomFirstHistoricalPairedError(f"{label} is not a mapping")
    required = {"uri", "generation", "sha256", "bytes"}
    missing = required - set(value)
    if missing:
        raise BoomFirstHistoricalPairedError(
            f"{label} lacks content identity fields: {sorted(missing)}"
        )
    uri = str(value["uri"]).strip()
    generation = str(value["generation"]).strip()
    sha256 = str(value["sha256"]).strip().lower()
    size = value["bytes"]
    if not uri or not generation or _SHA.fullmatch(sha256) is None:
        raise BoomFirstHistoricalPairedError(f"{label} content identity differs")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise BoomFirstHistoricalPairedError(f"{label}.bytes differs")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256,
        "bytes": int(size),
    }


def _validated_panel_authority(
    value: DevelopmentPanelAuthority | None,
    *,
    panel_id: str,
    observed_slate_ids: Sequence[str],
) -> dict[str, object]:
    if value is None:
        return {
            "supplied": False,
            "panel_id": None,
            "expected_slate_ids": None,
            "identity": None,
            "membership_matches": False,
        }
    if not isinstance(value, DevelopmentPanelAuthority):
        raise BoomFirstHistoricalPairedError(
            "development panel authority has the wrong type"
        )
    authority_panel = str(value.panel_id).strip()
    if _ID.fullmatch(authority_panel) is None or authority_panel != panel_id:
        raise BoomFirstHistoricalPairedError(
            "development panel authority ID differs"
        )
    raw_ids = value.expected_slate_ids
    if isinstance(raw_ids, (str, bytes)) or not isinstance(raw_ids, Sequence):
        raise BoomFirstHistoricalPairedError(
            "development panel authority slate index differs"
        )
    expected = [str(slate_id) for slate_id in raw_ids]
    if (
        not expected
        or len(set(expected)) != len(expected)
        or expected != sorted(expected)
    ):
        raise BoomFirstHistoricalPairedError(
            "development panel authority slate index differs"
        )
    for slate_id in expected:
        match = re.fullmatch(r"(20\d{2})-w(\d{2})", slate_id)
        if match is None:
            raise BoomFirstHistoricalPairedError(
                "development panel authority slate index differs"
            )
        season, week = int(match.group(1)), int(match.group(2))
        if (
            season not in DEVELOPMENT_SEASONS
            or season in SEALED_OUTCOME_SEASONS
            or not 1 <= week <= 18
        ):
            raise BoomFirstHistoricalPairedError(
                "development panel authority includes a forbidden slate"
            )
    observed = list(observed_slate_ids)
    if expected != observed:
        raise BoomFirstHistoricalPairedError(
            "development panel membership differs from immutable authority"
        )
    return {
        "supplied": True,
        "panel_id": authority_panel,
        "expected_slate_ids": expected,
        "identity": _content_identity(
            value.identity, label="development panel authority"
        ),
        "membership_matches": True,
    }


def _h1_readiness(
    *,
    panel_authority: Mapping[str, object],
    observed_seasons: Sequence[int],
) -> dict[str, object]:
    authority_supplied = panel_authority.get("supplied") is True
    seasons_complete = list(observed_seasons) == sorted(DEVELOPMENT_SEASONS)
    selection_inputs_complete = authority_supplied and seasons_complete
    blockers: list[str] = []
    if not authority_supplied:
        blockers.append("immutable_panel_authority_missing")
    if not seasons_complete:
        blockers.append("required_development_seasons_missing")
    blockers.append("required_statistical_diagnostics_not_implemented")
    return {
        "immutable_panel_authority_supplied": authority_supplied,
        "required_development_seasons_present": seasons_complete,
        "score_blind_selection_ready_for_h1_grading": selection_inputs_complete,
        "statistical_diagnostics_implemented": False,
        "h1_complete": False,
        "promotion_eligible": False,
        "blockers": blockers,
    }


def _forbidden_paths(value: object, *, path: str) -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            child = f"{path}.{key}"
            if str(key).lower() in _FORBIDDEN_OUTCOME_FIELDS:
                found.append(child)
            found.extend(_forbidden_paths(nested, path=child))
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            found.extend(_forbidden_paths(nested, path=f"{path}[{index}]"))
    return found


def _normalised_player_ids(batch: CandidateBatch, *, label: str) -> tuple[str, ...]:
    player_ids = tuple(str(value) for value in batch.player_ids)
    if len(set(player_ids)) != len(player_ids):
        raise BoomFirstHistoricalPairedError(
            f"{label} player IDs collide after canonical string conversion"
        )
    return player_ids


def _roster(lineup, *, label: str) -> tuple[str, ...]:
    ids = tuple(sorted(str(value) for value in lineup.ids))
    if len(ids) != 9 or len(set(ids)) != 9:
        raise BoomFirstHistoricalPairedError(f"{label} roster is not exact-nine")
    return ids


def _array_sha256(array: np.ndarray, *, player_ids: tuple[str, ...]) -> str:
    values = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(_canonical_json({
        "dtype": values.dtype.str,
        "shape": list(values.shape),
        "player_ids": list(player_ids),
    }))
    digest.update(values.tobytes(order="C"))
    return digest.hexdigest()


def role_player_world_receipt(
    player_ids: Sequence[object], worlds: np.ndarray,
) -> dict[str, object]:
    """Build the canonical receipt for one native role-belief world matrix."""

    ids = tuple(str(value) for value in player_ids)
    values = np.asarray(worlds)
    if (
        not ids
        or len(set(ids)) != len(ids)
        or values.ndim != 2
        or values.shape[0] != len(ids)
        or values.shape[1] < 1
        or not np.isfinite(values).all()
    ):
        raise BoomFirstHistoricalPairedError("role player worlds differ")
    return {
        "player_count": len(ids),
        "world_count": int(values.shape[1]),
        "dtype": values.dtype.str,
        "shape": [int(value) for value in values.shape],
        "player_ids_sha256": _sha256(list(ids)),
        "player_world_sha256": _array_sha256(values, player_ids=ids),
    }


def _validated_role_player_world_receipt(
    value: object,
    *,
    label: str,
    expected_worlds: int,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise BoomFirstHistoricalPairedError(
            f"{label} lacks role player-world receipt"
        )
    expected_keys = {
        "player_count",
        "world_count",
        "dtype",
        "shape",
        "player_ids_sha256",
        "player_world_sha256",
    }
    if set(value) != expected_keys:
        raise BoomFirstHistoricalPairedError(
            f"{label} role player-world receipt fields differ"
        )
    player_count = value["player_count"]
    world_count = value["world_count"]
    shape = value["shape"]
    dtype = value["dtype"]
    if (
        isinstance(player_count, bool)
        or not isinstance(player_count, int)
        or player_count < 1
        or isinstance(world_count, bool)
        or not isinstance(world_count, int)
        or world_count != expected_worlds
        or shape != [player_count, world_count]
        or not isinstance(dtype, str)
        or not dtype
        or _SHA.fullmatch(str(value["player_ids_sha256"])) is None
        or _SHA.fullmatch(str(value["player_world_sha256"])) is None
    ):
        raise BoomFirstHistoricalPairedError(
            f"{label} role player-world receipt differs"
        )
    return {
        "player_count": player_count,
        "world_count": world_count,
        "dtype": dtype,
        "shape": list(shape),
        "player_ids_sha256": str(value["player_ids_sha256"]),
        "player_world_sha256": str(value["player_world_sha256"]),
    }


def _candidate_sha256(batch: CandidateBatch, *, label: str) -> str:
    return _sha256([
        list(_roster(lineup, label=f"{label} candidate"))
        for lineup in batch.candidates
    ])


def _validated_arm_environments(code_sha: str) -> dict[str, dict[str, str]]:
    policy = ADOPTED_CLASSIC_POLICY
    if not hasattr(policy, "boom_first_control_environment") or not hasattr(
        policy, "boom_first_shadow_environment"
    ):
        raise BoomFirstHistoricalPairedError(
            "production policy lacks the preregistered boom-first environments"
        )
    base = {"CODE_SHA": code_sha}
    control = policy.boom_first_control_environment(base)
    treatment = policy.boom_first_shadow_environment(base)
    environments = {"control": control, "treatment": treatment}

    common = {
        "MODEL_REGISTRY_VARIANT": "tail_k1",
        "MODEL_ENSEMBLE": "1",
        "N_EPISTEMIC": "12",
        "EPISTEMIC_FAMILY": "role_draws",
        "N_QB_VARIANTS": "4",
        "N_GAMESTACK": "4",
        "N_DARKGAME": "10",
        "CAND_MULT": "2",
        "MIN_LINEUP_SALARY": "49000",
        "MULTISEED_PORTFOLIO": "CBWU",
        "MULTISEED_WORLDS_PER_BLOCK": str(
            policy.multiseed_worlds_per_block
        ),
        "MULTISEED_CANDIDATE_ENTRY_BASIS": "80",
        "SELECT_LSE": "0",
        "SELECT_LADDER": "",
        "BOOM_UNIQUE_FILL": "0",
    }
    for arm, env in environments.items():
        drift = {
            key: (env.get(key), expected)
            for key, expected in common.items()
            if env.get(key) != expected
        }
        if drift:
            raise BoomFirstHistoricalPairedError(
                f"{arm} production-shaped environment differs: {drift}"
            )

    expected_arm = {
        "control": {"N_LEV": "160", "N_BOOM": "40", "GEN_TOTAL_BUDGET": "52"},
        "treatment": {
            "N_LEV": "40",
            "N_BOOM": "160",
            "GEN_TOTAL_BUDGET": "172",
        },
    }
    for arm, expected in expected_arm.items():
        if any(environments[arm].get(key) != value for key, value in expected.items()):
            raise BoomFirstHistoricalPairedError(
                f"{arm} leverage/boom allocation differs"
            )
    changed = {
        key
        for key in set(control) | set(treatment)
        if control.get(key) != treatment.get(key)
    }
    allowed_changed = {
        "GEN_TOTAL_BUDGET",
        "N_BOOM",
        "N_LEV",
        "PROSPECTIVE_SHADOW_ID",
    }
    if changed != allowed_changed:
        raise BoomFirstHistoricalPairedError(
            f"boom-first environment delta differs: {sorted(changed)}"
        )
    return environments


def _validated_native_receipt(
    batch: CandidateBatch,
    *,
    arm: str,
    seed_label: str,
    expected_worlds: int,
) -> tuple[dict[str, object], dict[str, float]]:
    try:
        _validate_candidate_batch(batch)
    except (TypeError, ValueError) as exc:
        raise BoomFirstHistoricalPairedError(
            f"{arm}/{seed_label} native candidate batch differs: {exc}"
        ) from exc
    forbidden = _forbidden_paths(
        {
            "player_rows": batch.player_rows,
            "candidates": [lineup.players for lineup in batch.candidates],
            "metadata": batch.metadata,
        },
        path=f"{arm}.{seed_label}",
    )
    if forbidden:
        raise BoomFirstHistoricalPairedError(
            "score-blind native book contains outcome fields: "
            + ", ".join(forbidden[:8])
        )
    draws = np.asarray(batch.row_draws)
    totals = np.asarray(batch.candidate_totals)
    if (
        draws.shape[1] != expected_worlds
        or totals.shape[1] != expected_worlds
        or not np.isfinite(draws).all()
        or not np.isfinite(totals).all()
    ):
        raise BoomFirstHistoricalPairedError(
            f"{arm}/{seed_label} world matrix differs"
        )
    role_worlds = _validated_role_player_world_receipt(
        batch.metadata.get("role_player_world_receipt"),
        label=f"{arm}/{seed_label}",
        expected_worlds=expected_worlds,
    )
    allocation = batch.metadata.get("generation_allocation")
    timing = batch.metadata.get("generation_timing_seconds")
    if not isinstance(allocation, Mapping) or not isinstance(timing, Mapping):
        raise BoomFirstHistoricalPairedError(
            f"{arm}/{seed_label} lacks generation allocation/timing receipts"
        )
    expected_lev, expected_boom = (
        (160, 40) if arm == "control" else (40, 160)
    )
    expected = {
        "leverage_requested": expected_lev,
        "leverage_solve_attempts": expected_lev,
        "leverage_solver_errors": 0,
        "leverage_infeasible": 0,
        "leverage_successful": expected_lev,
        "leverage_unique": expected_lev,
        "boom_requested": expected_boom,
        "boom_attempted": expected_boom,
        "boom_successful": expected_boom,
        "boom_solver_errors": 0,
        "boom_infeasible": 0,
        "boom_failures": 0,
        "ce_requested": 0,
        "role_or_epistemic_requested": 12,
        "gumbel_requested": 0,
        "core_requested": 200,
        "total_requested_with_replacement_families": 212,
    }
    if any(allocation.get(key) != value for key, value in expected.items()):
        raise BoomFirstHistoricalPairedError(
            f"{arm}/{seed_label} requested-solve receipt differs"
        )
    if allocation.get("boom_unique_fill") is not False:
        raise BoomFirstHistoricalPairedError(
            f"{arm}/{seed_label} boom unique-fill must remain off"
        )
    for key in ("boom_unique_added", "boom_duplicates"):
        value = allocation.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise BoomFirstHistoricalPairedError(
                f"{arm}/{seed_label} solver telemetry differs"
            )
    if (
        allocation["boom_unique_added"] + allocation["boom_duplicates"]
        != expected_boom
    ):
        raise BoomFirstHistoricalPairedError(
            f"{arm}/{seed_label} boom solver work is incomplete"
        )
    timing_out: dict[str, float] = {}
    for key in ("leverage", "primary_boom", "all_generation_through_candidate_matrix"):
        value = timing.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise BoomFirstHistoricalPairedError(
                f"{arm}/{seed_label} timing receipt differs"
            )
        number = float(value)
        if not math.isfinite(number) or number < 0:
            raise BoomFirstHistoricalPairedError(
                f"{arm}/{seed_label} timing receipt differs"
            )
        timing_out[key] = number

    player_ids = _normalised_player_ids(batch, label=f"{arm}/{seed_label}")
    scientific = {
        "seed_label": seed_label,
        "candidate_count": len(batch.candidates),
        "candidate_sha256": _candidate_sha256(
            batch, label=f"{arm}/{seed_label}"
        ),
        "player_count": len(batch.player_ids),
        "world_count": int(draws.shape[1]),
        "player_world_sha256": _array_sha256(draws, player_ids=player_ids),
        "role_player_world_receipt": role_worlds,
        "generation_allocation": dict(allocation),
    }
    return scientific, timing_out


def _validate_identity_fields(
    *, panel_id: str, code_sha: str, image_digest: str
) -> tuple[str, str, str]:
    panel = str(panel_id).strip()
    code = str(code_sha).strip().lower()
    image = str(image_digest).strip().lower()
    if _ID.fullmatch(panel) is None:
        raise BoomFirstHistoricalPairedError("panel ID differs")
    if _CODE_SHA.fullmatch(code) is None:
        raise BoomFirstHistoricalPairedError("code SHA differs")
    if not image.startswith("sha256:") or _SHA.fullmatch(image[7:]) is None:
        raise BoomFirstHistoricalPairedError("immutable image digest differs")
    return panel, code, image


def build_score_blind_development_panel(
    slates: Sequence[DevelopmentSlate],
    native_book_builder: NativeBookBuilder,
    *,
    panel_id: str,
    code_sha: str,
    image_digest: str,
    panel_authority: DevelopmentPanelAuthority | None = None,
) -> dict[str, object]:
    """Freeze same-world control/treatment exact-80 books without outcomes.

    The builder is invoked as ``builder(slate, arm, seed_label,
    projection_seed, role_seed, policy_env)``.  It must return a complete
    native :class:`CandidateBatch` captured before CBWU selection.
    """

    panel, code, image = _validate_identity_fields(
        panel_id=panel_id, code_sha=code_sha, image_digest=image_digest
    )
    if not callable(native_book_builder):
        raise BoomFirstHistoricalPairedError("native-book builder is not callable")
    supplied_slates = tuple(slates)
    if not all(isinstance(slate, DevelopmentSlate) for slate in supplied_slates):
        raise BoomFirstHistoricalPairedError(
            "development panel contains a non-DevelopmentSlate row"
        )
    ordered_slates = sorted(
        supplied_slates,
        key=lambda slate: (slate.season, slate.week, slate.slate_id),
    )
    if not ordered_slates:
        raise BoomFirstHistoricalPairedError("development panel is empty")
    slate_ids = [slate.slate_id for slate in ordered_slates]
    if len(set(slate_ids)) != len(slate_ids):
        raise BoomFirstHistoricalPairedError("development panel repeats a slate")
    observed_seasons = sorted({slate.season for slate in ordered_slates})
    authority_receipt = _validated_panel_authority(
        panel_authority,
        panel_id=panel,
        observed_slate_ids=slate_ids,
    )
    h1_readiness = _h1_readiness(
        panel_authority=authority_receipt,
        observed_seasons=observed_seasons,
    )

    policy = ADOPTED_CLASSIC_POLICY
    if (
        policy.model_ensemble != 1
        or policy.default_entries != ENTRIES
        or policy.tail_line != TAIL_LINE
        or len(policy.multiseed_seed_pairs) != 5
    ):
        raise BoomFirstHistoricalPairedError("adopted production policy differs")
    environments = _validated_arm_environments(code)
    seed_rows = [
        {
            "seed_label": f"R{index}",
            "projection_seed": int(projection_seed),
            "role_seed": int(role_seed),
        }
        for index, (projection_seed, role_seed) in enumerate(
            policy.multiseed_seed_pairs
        )
    ]
    seed_order = tuple(row["seed_label"] for row in seed_rows)
    scientific_slates: list[dict[str, object]] = []
    timing_slates: list[dict[str, object]] = []

    for slate in ordered_slates:
        source_identity = _content_identity(
            slate.source_identity, label=f"{slate.slate_id} source"
        )
        books: dict[str, dict[str, CandidateBatch]] = {
            arm: {} for arm in ARM_ORDER
        }
        native_science: dict[str, list[dict[str, object]]] = {
            arm: [] for arm in ARM_ORDER
        }
        native_timing: dict[str, list[dict[str, object]]] = {
            arm: [] for arm in ARM_ORDER
        }
        # Interleave arms by seed so a changing external input cannot silently
        # create a wide temporal gap. Exact matrix equality still decides.
        for seed in seed_rows:
            label = str(seed["seed_label"])
            for arm in ARM_ORDER:
                batch = native_book_builder(
                    slate,
                    arm,
                    label,
                    int(seed["projection_seed"]),
                    int(seed["role_seed"]),
                    dict(environments[arm]),
                )
                scientific, timing = _validated_native_receipt(
                    batch,
                    arm=arm,
                    seed_label=label,
                    expected_worlds=policy.multiseed_worlds_per_block,
                )
                books[arm][label] = batch
                native_science[arm].append(scientific)
                native_timing[arm].append({
                    "seed_label": label,
                    **timing,
                })
            control_batch = books["control"][label]
            treatment_batch = books["treatment"][label]
            if control_batch.player_ids != treatment_batch.player_ids:
                raise BoomFirstHistoricalPairedError(
                    f"{slate.slate_id}/{label} player order differs across arms"
                )
            if not np.array_equal(
                control_batch.row_draws, treatment_batch.row_draws
            ):
                raise BoomFirstHistoricalPairedError(
                    f"{slate.slate_id}/{label} player worlds differ across arms"
                )
            if (
                native_science["control"][-1]["role_player_world_receipt"]
                != native_science["treatment"][-1][
                    "role_player_world_receipt"
                ]
            ):
                raise BoomFirstHistoricalPairedError(
                    f"{slate.slate_id}/{label} role player worlds differ across arms"
                )

        combined: dict[str, CandidateBatch] = {}
        selected: dict[str, list[tuple[str, ...]]] = {}
        arm_rows: dict[str, dict[str, object]] = {}
        for arm in ARM_ORDER:
            try:
                combined[arm] = combine_cbwu_books(
                    books[arm],
                    seed_order,
                    expected_worlds_per_book=policy.multiseed_worlds_per_block,
                )
            except (TypeError, ValueError) as exc:
                raise BoomFirstHistoricalPairedError(
                    f"{slate.slate_id}/{arm} CBWU combination failed: {exc}"
                ) from exc
            picked = select_tail_entries(
                combined[arm].candidate_totals,
                ENTRIES,
                TAIL_LINE,
                env=dict(environments[arm]),
            )
            if len(picked) != ENTRIES or len(set(picked)) != ENTRIES:
                raise BoomFirstHistoricalPairedError(
                    f"{slate.slate_id}/{arm} selection is not exact-80"
                )
            rosters = [
                _roster(
                    combined[arm].candidates[index],
                    label=f"{slate.slate_id}/{arm} selected",
                )
                for index in picked
            ]
            if len(set(rosters)) != ENTRIES:
                raise BoomFirstHistoricalPairedError(
                    f"{slate.slate_id}/{arm} selected rosters repeat"
                )
            selected[arm] = rosters
            player_ids = _normalised_player_ids(
                combined[arm], label=f"{slate.slate_id}/{arm} combined"
            )
            combined_rosters = [
                list(_roster(
                    lineup,
                    label=f"{slate.slate_id}/{arm} combined candidate",
                ))
                for lineup in combined[arm].candidates
            ]
            arm_rows[arm] = {
                "combined_candidate_count": len(combined[arm].candidates),
                "combined_candidate_sha256": _sha256(combined_rosters),
                "combined_candidate_rosters": combined_rosters,
                "combined_world_count": int(combined[arm].row_draws.shape[1]),
                "combined_player_world_sha256": _array_sha256(
                    combined[arm].row_draws, player_ids=player_ids
                ),
                "combined_role_player_world_sha256": _sha256([
                    row["role_player_world_receipt"]
                    for row in native_science[arm]
                ]),
                "native_books": native_science[arm],
                "selected_rosters": [list(roster) for roster in rosters],
                "selected_rosters_sha256": _sha256(
                    [list(roster) for roster in rosters]
                ),
            }
        if combined["control"].player_ids != combined["treatment"].player_ids:
            raise BoomFirstHistoricalPairedError(
                f"{slate.slate_id} combined player order differs"
            )
        if not np.array_equal(
            combined["control"].row_draws,
            combined["treatment"].row_draws,
        ):
            raise BoomFirstHistoricalPairedError(
                f"{slate.slate_id} combined player worlds differ"
            )
        if (
            arm_rows["control"]["combined_role_player_world_sha256"]
            != arm_rows["treatment"]["combined_role_player_world_sha256"]
        ):
            raise BoomFirstHistoricalPairedError(
                f"{slate.slate_id} combined role player worlds differ"
            )
        control_set = set(selected["control"])
        treatment_set = set(selected["treatment"])
        scientific_slates.append({
            "season": slate.season,
            "week": slate.week,
            "slate_id": slate.slate_id,
            "source_identity": source_identity,
            "same_player_worlds": True,
            "same_role_player_worlds": True,
            "selected_overlap": len(control_set & treatment_set),
            "selected_union": len(control_set | treatment_set),
            "arms": arm_rows,
        })
        timing_slates.append({
            "slate_id": slate.slate_id,
            "arms": native_timing,
        })

    env_receipts = {
        arm: {
            "values": dict(sorted(env.items())),
            "sha256": _sha256(dict(sorted(env.items()))),
        }
        for arm, env in environments.items()
    }
    scientific_body: dict[str, object] = {
        "schema_version": SELECTION_SCHEMA,
        "panel_id": panel,
        "code_sha": code,
        "image_digest": image,
        "policy_id": policy.policy_id,
        "policy_source_panel": policy.source_panel,
        "model_registry_variant": policy.model_variant,
        "model_ensemble": policy.model_ensemble,
        "tail_line": TAIL_LINE,
        "entry_count": ENTRIES,
        "prefix_sizes": list(PREFIX_SIZES),
        "development_seasons": observed_seasons,
        "allowed_development_seasons": sorted(DEVELOPMENT_SEASONS),
        "sealed_outcome_seasons": sorted(SEALED_OUTCOME_SEASONS),
        "panel_authority": authority_receipt,
        "h1_readiness": h1_readiness,
        "seed_pairs": seed_rows,
        "environment_receipts": env_receipts,
        "requested_allocation": {
            "control": {"leverage": 160, "boom": 40, "core": 200},
            "treatment": {"leverage": 40, "boom": 160, "core": 200},
            "common": {
                "role": 12,
                "qb_variants_max": 32,
                "game_stacks_max": 12,
                "dark_games_max": 10,
            },
            "nominal_full_slate_requested_per_native_book": 266,
            "requested_family_slots_per_five_book_arm": 1060,
            "nominal_all_requested_per_five_book_arm": 1330,
            "equal_core_requested": True,
        },
        "slate_count": len(scientific_slates),
        "slates": scientific_slates,
        "selection_completed_before_target_slate_outcomes": True,
        "uses_target_slate_outcomes": False,
        "prior_only_historical_labels_may_train_later_targets": True,
        "sealed_2025_outcomes_read": False,
        "development_only": True,
        "automatic_promotion": False,
        "production_policy_authority": False,
    }
    scientific_sha256 = _sha256(scientific_body)
    receipt_body = {
        **scientific_body,
        "scientific_sha256": scientific_sha256,
        # Wall-clock observations are auditable but deliberately excluded
        # from the scientific identity above.
        "execution_observations": {"generation_timing_seconds": timing_slates},
    }
    return {
        **receipt_body,
        "receipt_sha256": _sha256(receipt_body),
    }


def validate_score_blind_selection_receipt(value: Mapping[str, object]) -> dict:
    """Revalidate a selection receipt before any outcome mapping is accepted."""

    if not isinstance(value, Mapping):
        raise BoomFirstHistoricalPairedError("selection receipt is not a mapping")
    receipt = dict(value)
    receipt_sha = receipt.pop("receipt_sha256", None)
    if not isinstance(receipt_sha, str) or _SHA.fullmatch(receipt_sha) is None:
        raise BoomFirstHistoricalPairedError("selection receipt SHA differs")
    if _sha256(receipt) != receipt_sha:
        raise BoomFirstHistoricalPairedError("selection receipt self-hash differs")
    scientific_sha = receipt.get("scientific_sha256")
    observations = receipt.get("execution_observations")
    scientific = {
        key: row
        for key, row in receipt.items()
        if key not in {"scientific_sha256", "execution_observations"}
    }
    if (
        not isinstance(scientific_sha, str)
        or _SHA.fullmatch(scientific_sha) is None
        or _sha256(scientific) != scientific_sha
        or not isinstance(observations, Mapping)
    ):
        raise BoomFirstHistoricalPairedError(
            "selection scientific identity differs"
        )
    if (
        scientific.get("schema_version") != SELECTION_SCHEMA
        or scientific.get("uses_target_slate_outcomes") is not False
        or scientific.get(
            "selection_completed_before_target_slate_outcomes"
        ) is not True
        or scientific.get(
            "prior_only_historical_labels_may_train_later_targets"
        ) is not True
        or scientific.get("sealed_2025_outcomes_read") is not False
        or scientific.get("development_only") is not True
        or scientific.get("automatic_promotion") is not False
        or scientific.get("production_policy_authority") is not False
    ):
        raise BoomFirstHistoricalPairedError("selection authority differs")
    allowed_seasons = scientific.get("allowed_development_seasons")
    if allowed_seasons != sorted(DEVELOPMENT_SEASONS):
        raise BoomFirstHistoricalPairedError("selection development panel differs")
    slates = scientific.get("slates")
    if not isinstance(slates, list) or not slates:
        raise BoomFirstHistoricalPairedError("selection slate rows differ")
    if any(not isinstance(row, Mapping) for row in slates):
        raise BoomFirstHistoricalPairedError("selection slate rows differ")
    slate_ids = [str(row.get("slate_id", "")) for row in slates]
    if slate_ids != sorted(slate_ids) or len(set(slate_ids)) != len(slate_ids):
        raise BoomFirstHistoricalPairedError("selection slate order differs")
    try:
        observed_seasons = sorted({int(row.get("season", 0)) for row in slates})
    except (TypeError, ValueError) as exc:
        raise BoomFirstHistoricalPairedError(
            "selection development panel differs"
        ) from exc
    if (
        scientific.get("development_seasons") != observed_seasons
        or any(season not in DEVELOPMENT_SEASONS for season in observed_seasons)
        or 2025 in observed_seasons
    ):
        raise BoomFirstHistoricalPairedError("selection development panel differs")
    authority = scientific.get("panel_authority")
    if not isinstance(authority, Mapping):
        raise BoomFirstHistoricalPairedError("selection panel authority differs")
    if authority.get("supplied") is True:
        if (
            authority.get("panel_id") != scientific.get("panel_id")
            or authority.get("expected_slate_ids") != slate_ids
            or authority.get("membership_matches") is not True
        ):
            raise BoomFirstHistoricalPairedError(
                "selection panel authority differs"
            )
        _content_identity(
            authority.get("identity"), label="selection panel authority"
        )
    elif dict(authority) != {
        "supplied": False,
        "panel_id": None,
        "expected_slate_ids": None,
        "identity": None,
        "membership_matches": False,
    }:
        raise BoomFirstHistoricalPairedError("selection panel authority differs")
    expected_h1 = _h1_readiness(
        panel_authority=authority,
        observed_seasons=observed_seasons,
    )
    if scientific.get("h1_readiness") != expected_h1:
        raise BoomFirstHistoricalPairedError("selection H1 readiness differs")
    for row in slates:
        if (
            not isinstance(row, Mapping)
            or int(row.get("season", 0)) not in DEVELOPMENT_SEASONS
            or int(row.get("season", 0)) in SEALED_OUTCOME_SEASONS
        ):
            raise BoomFirstHistoricalPairedError("selection includes a sealed slate")
        arms = row.get("arms")
        if not isinstance(arms, Mapping) or set(arms) != set(ARM_ORDER):
            raise BoomFirstHistoricalPairedError("selection arm rows differ")
        for arm in ARM_ORDER:
            native_books = arms[arm].get("native_books")
            if not isinstance(native_books, list) or len(native_books) != 5:
                raise BoomFirstHistoricalPairedError(
                    "native role player-world receipt grid differs"
                )
            for native in native_books:
                if not isinstance(native, Mapping):
                    raise BoomFirstHistoricalPairedError(
                        "native role player-world receipt differs"
                    )
                _validated_role_player_world_receipt(
                    native.get("role_player_world_receipt"),
                    label="native book",
                    expected_worlds=(
                        ADOPTED_CLASSIC_POLICY.multiseed_worlds_per_block
                    ),
                )
            expected_role_sha = _sha256([
                native["role_player_world_receipt"]
                for native in native_books
            ])
            if (
                arms[arm].get("combined_role_player_world_sha256")
                != expected_role_sha
            ):
                raise BoomFirstHistoricalPairedError(
                    "combined role player-world receipt differs"
                )
            memberships = arms[arm].get("selected_rosters")
            if not isinstance(memberships, list) or len(memberships) != ENTRIES:
                raise BoomFirstHistoricalPairedError(
                    "selection membership is not exact-80"
                )
            if _sha256(memberships) != arms[arm].get("selected_rosters_sha256"):
                raise BoomFirstHistoricalPairedError(
                    "selection membership hash differs"
                )
            candidates = arms[arm].get("combined_candidate_rosters")
            if (
                not isinstance(candidates, list)
                or len(candidates) != arms[arm].get("combined_candidate_count")
                or _sha256(candidates)
                != arms[arm].get("combined_candidate_sha256")
                or any(
                    not isinstance(roster, list)
                    or len(roster) != 9
                    or len(set(map(str, roster))) != 9
                    for roster in candidates
                )
            ):
                raise BoomFirstHistoricalPairedError(
                    "combined candidate membership/hash differs"
                )
        if (
            row.get("same_role_player_worlds") is not True
            or arms["control"].get("combined_role_player_world_sha256")
            != arms["treatment"].get("combined_role_player_world_sha256")
        ):
            raise BoomFirstHistoricalPairedError(
                "paired role player-world receipts differ"
            )
    return {**receipt, "receipt_sha256": receipt_sha}


def _points_micro(value: object, *, label: str) -> int:
    if isinstance(value, bool):
        raise BoomFirstHistoricalPairedError(f"{label} is not a score")
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BoomFirstHistoricalPairedError(f"{label} is not a score") from exc
    if not decimal.is_finite():
        raise BoomFirstHistoricalPairedError(f"{label} is not finite")
    scaled = decimal * Decimal(1_000_000)
    if scaled != scaled.to_integral_value():
        raise BoomFirstHistoricalPairedError(
            f"{label} exceeds six-decimal micro-point precision"
        )
    return int(scaled)


def _actual_map(value: Mapping[object, object], *, label: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise BoomFirstHistoricalPairedError(f"{label} is not a mapping")
    result: dict[str, int] = {}
    for raw_id, raw_score in value.items():
        player_id = str(raw_id)
        if not player_id or player_id in result:
            raise BoomFirstHistoricalPairedError(
                f"{label} player IDs are empty or collide"
            )
        result[player_id] = _points_micro(
            raw_score, label=f"{label}[{player_id}]"
        )
    if not result:
        raise BoomFirstHistoricalPairedError(f"{label} is empty")
    return result


def grade_development_panel(
    selection_receipt: Mapping[str, object],
    *,
    grade_id: str,
    actual_points_by_slate: Mapping[str, Mapping[object, object]],
    outcome_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Grade frozen books on their target-slate development outcomes only."""

    selection = validate_score_blind_selection_receipt(selection_receipt)
    grade = str(grade_id).strip()
    if _ID.fullmatch(grade) is None:
        raise BoomFirstHistoricalPairedError("grade ID differs")
    slate_rows = selection["slates"]
    slate_ids = [str(row["slate_id"]) for row in slate_rows]
    if set(actual_points_by_slate) != set(slate_ids):
        raise BoomFirstHistoricalPairedError(
            "realized outcome slate keys differ from the frozen development panel"
        )
    if set(outcome_identities) != set(slate_ids):
        raise BoomFirstHistoricalPairedError(
            "realized outcome identity keys differ from the frozen panel"
        )

    weekly_rows: list[dict[str, object]] = []
    for slate in slate_rows:
        season = int(slate["season"])
        if season in SEALED_OUTCOME_SEASONS or season not in DEVELOPMENT_SEASONS:
            raise BoomFirstHistoricalPairedError(
                "grader refuses sealed or non-development outcomes"
            )
        slate_id = str(slate["slate_id"])
        actuals = _actual_map(
            actual_points_by_slate[slate_id], label=f"{slate_id} actuals"
        )
        outcome_identity = _content_identity(
            outcome_identities[slate_id], label=f"{slate_id} outcomes"
        )
        arm_scores: dict[str, list[int]] = {}
        pool_scores: dict[str, list[int]] = {}
        for arm in ARM_ORDER:
            rosters = slate["arms"][arm]["selected_rosters"]
            scores: list[int] = []
            for ordinal, roster in enumerate(rosters):
                if not isinstance(roster, list) or len(roster) != 9:
                    raise BoomFirstHistoricalPairedError(
                        f"{slate_id}/{arm} roster {ordinal} differs"
                    )
                missing = [
                    str(player)
                    for player in roster
                    if str(player) not in actuals
                ]
                if missing:
                    raise BoomFirstHistoricalPairedError(
                        f"{slate_id}/{arm} roster {ordinal} lacks realized players: "
                        + ", ".join(missing)
                    )
                scores.append(sum(actuals[str(player)] for player in roster))
            arm_scores[arm] = scores
            candidates = slate["arms"][arm]["combined_candidate_rosters"]
            candidate_scores: list[int] = []
            for ordinal, roster in enumerate(candidates):
                missing = [
                    str(player)
                    for player in roster
                    if str(player) not in actuals
                ]
                if missing:
                    raise BoomFirstHistoricalPairedError(
                        f"{slate_id}/{arm} candidate {ordinal} lacks realized "
                        "players: " + ", ".join(missing)
                    )
                candidate_scores.append(
                    sum(actuals[str(player)] for player in roster)
                )
            pool_scores[arm] = candidate_scores

        pool_oracles: dict[str, tuple[int, int]] = {}
        for arm in ARM_ORDER:
            best_ordinal = max(
                range(len(pool_scores[arm])),
                key=lambda index: pool_scores[arm][index],
            )
            pool_oracles[arm] = (
                pool_scores[arm][best_ordinal],
                best_ordinal,
            )

        prefix_rows: list[dict[str, object]] = []
        for prefix in PREFIX_SIZES:
            arm_max: dict[str, tuple[int, int]] = {}
            for arm in ARM_ORDER:
                prefix_scores = arm_scores[arm][:prefix]
                best_ordinal = max(
                    range(prefix), key=lambda index: prefix_scores[index]
                )
                arm_max[arm] = (prefix_scores[best_ordinal], best_ordinal)
            control_micro, control_ordinal = arm_max["control"]
            treatment_micro, treatment_ordinal = arm_max["treatment"]
            control_oracle_micro, control_oracle_ordinal = pool_oracles[
                "control"
            ]
            treatment_oracle_micro, treatment_oracle_ordinal = pool_oracles[
                "treatment"
            ]
            prefix_rows.append({
                "prefix": prefix,
                "control_weekly_max_micro": control_micro,
                "control_weekly_max_points": control_micro / 1_000_000,
                "control_best_ordinal": control_ordinal,
                "control_best_roster": slate["arms"]["control"][
                    "selected_rosters"
                ][control_ordinal],
                "treatment_weekly_max_micro": treatment_micro,
                "treatment_weekly_max_points": treatment_micro / 1_000_000,
                "treatment_best_ordinal": treatment_ordinal,
                "treatment_best_roster": slate["arms"]["treatment"][
                    "selected_rosters"
                ][treatment_ordinal],
                "paired_delta_micro": treatment_micro - control_micro,
                "paired_delta_points": (
                    treatment_micro - control_micro
                ) / 1_000_000,
                "control_pool_oracle_micro": control_oracle_micro,
                "control_pool_oracle_points": (
                    control_oracle_micro / 1_000_000
                ),
                "control_pool_oracle_ordinal": control_oracle_ordinal,
                "control_selector_regret_points": (
                    control_oracle_micro - control_micro
                ) / 1_000_000,
                "treatment_pool_oracle_micro": treatment_oracle_micro,
                "treatment_pool_oracle_points": (
                    treatment_oracle_micro / 1_000_000
                ),
                "treatment_pool_oracle_ordinal": treatment_oracle_ordinal,
                "treatment_selector_regret_points": (
                    treatment_oracle_micro - treatment_micro
                ) / 1_000_000,
            })
        weekly_rows.append({
            "season": season,
            "week": int(slate["week"]),
            "slate_id": slate_id,
            "outcome_identity": outcome_identity,
            "prefixes": prefix_rows,
        })

    aggregate_rows: list[dict[str, object]] = []
    for prefix in PREFIX_SIZES:
        rows = [
            next(row for row in slate["prefixes"] if row["prefix"] == prefix)
            for slate in weekly_rows
        ]
        control = [int(row["control_weekly_max_micro"]) for row in rows]
        treatment = [int(row["treatment_weekly_max_micro"]) for row in rows]
        deltas = [right - left for left, right in zip(control, treatment, strict=True)]
        control_oracles = [int(row["control_pool_oracle_micro"]) for row in rows]
        treatment_oracles = [
            int(row["treatment_pool_oracle_micro"]) for row in rows
        ]
        thresholds = []
        for threshold in TAIL_THRESHOLDS:
            threshold_micro = threshold * 1_000_000
            control_hits = [score >= threshold_micro for score in control]
            treatment_hits = [score >= threshold_micro for score in treatment]
            thresholds.append({
                "threshold": threshold,
                "control_weeks": sum(control_hits),
                "treatment_weeks": sum(treatment_hits),
                "paired_gains": sum(
                    right and not left
                    for left, right in zip(
                        control_hits, treatment_hits, strict=True
                    )
                ),
                "paired_losses": sum(
                    left and not right
                    for left, right in zip(
                        control_hits, treatment_hits, strict=True
                    )
                ),
            })
        aggregate_rows.append({
            "prefix": prefix,
            "slate_count": len(rows),
            "control_sum_weekly_max_micro": sum(control),
            "control_mean_weekly_max_points": (
                sum(control) / len(control) / 1_000_000
            ),
            "treatment_sum_weekly_max_micro": sum(treatment),
            "treatment_mean_weekly_max_points": (
                sum(treatment) / len(treatment) / 1_000_000
            ),
            "paired_delta_sum_micro": sum(deltas),
            "paired_mean_delta_points": (
                sum(deltas) / len(deltas) / 1_000_000
            ),
            "treatment_wins": sum(delta > 0 for delta in deltas),
            "ties": sum(delta == 0 for delta in deltas),
            "treatment_losses": sum(delta < 0 for delta in deltas),
            "control_mean_pool_oracle_points": (
                sum(control_oracles) / len(control_oracles) / 1_000_000
            ),
            "treatment_mean_pool_oracle_points": (
                sum(treatment_oracles) / len(treatment_oracles) / 1_000_000
            ),
            "control_mean_selector_regret_points": (
                sum(
                    oracle - selected
                    for oracle, selected in zip(
                        control_oracles, control, strict=True
                    )
                ) / len(control) / 1_000_000
            ),
            "treatment_mean_selector_regret_points": (
                sum(
                    oracle - selected
                    for oracle, selected in zip(
                        treatment_oracles, treatment, strict=True
                    )
                ) / len(treatment) / 1_000_000
            ),
            "thresholds": thresholds,
        })

    report_body: dict[str, object] = {
        "schema_version": GRADE_SCHEMA,
        "grade_id": grade,
        "selection_panel_id": selection["panel_id"],
        "selection_receipt_sha256": selection["receipt_sha256"],
        "selection_scientific_sha256": selection["scientific_sha256"],
        "policy_id": selection["policy_id"],
        "tail_line": TAIL_LINE,
        "entry_count": ENTRIES,
        "prefix_sizes": list(PREFIX_SIZES),
        "development_seasons": list(selection["development_seasons"]),
        "slate_count": len(weekly_rows),
        "weekly_results": weekly_rows,
        "aggregate_results": aggregate_rows,
        "target_slate_outcomes_read_for_grading": True,
        "target_slate_outcomes_absent_during_selection": True,
        "prior_only_historical_labels_may_have_trained_later_targets": True,
        "development_target_outcomes_only": True,
        "sealed_2025_outcomes_read": False,
        "selection_completed_before_target_slate_outcomes": True,
        "h1_readiness": dict(selection["h1_readiness"]),
        "automatic_promotion": False,
        "production_policy_authority": False,
    }
    return {
        **report_body,
        "report_sha256": _sha256(report_body),
    }


__all__ = [
    "ARM_ORDER",
    "BoomFirstHistoricalPairedError",
    "DEVELOPMENT_SEASONS",
    "DevelopmentPanelAuthority",
    "DevelopmentSlate",
    "ENTRIES",
    "GRADE_SCHEMA",
    "PREFIX_SIZES",
    "SEALED_OUTCOME_SEASONS",
    "SELECTION_SCHEMA",
    "TAIL_LINE",
    "TAIL_THRESHOLDS",
    "build_score_blind_development_panel",
    "grade_development_panel",
    "role_player_world_receipt",
    "validate_score_blind_selection_receipt",
]
