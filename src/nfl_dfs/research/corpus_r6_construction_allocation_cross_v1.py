"""Outcome-blind construction-preset x candidate-allocation experiment.

This release is intentionally separate from the five-arm prospective
generation shadow.  It answers one narrower historical question on the exact
Foundry G0 54-slate panel: does the 160-leverage/40-boom versus
40-leverage/160-boom allocation effect change when candidate construction is
the named incumbent GPP preset versus DraftKings Classic legality only?

The module owns only score-blind contracts and deterministic selection.  It
does not query a warehouse, read realized outcomes, publish objects, or alter
the adopted policy.  A caller injects native ``CandidateBatch`` objects built
from one immutable point-in-time slate authority.  Realized grading lives in
``corpus_r6_construction_allocation_grade_v1`` and create-once publication in
``corpus_r6_construction_allocation_cross_operator_v1``.
"""

from __future__ import annotations

import base64
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Final
import zlib

import numpy as np

from ..backtest.engine import CandidateBatch, _validate_candidate_batch
from ..inference.generation_exposure import validate_ledger
from ..inference.multiseed_portfolio import combine_cbwu_books
from ..inference.production_policy import ADOPTED_CLASSIC_POLICY
from ..optimizer.construction_presets import (
    INCUMBENT_GPP_PRESET_ID,
    LEGALITY_ONLY_PRESET_ID,
    ConstructionPreset,
    resolve_construction_preset,
)
from ..optimizer.lineup import select_from_support, select_tail_entries
from .boom_first_historical_paired_v1 import role_player_world_receipt
from . import corpus_r6_boom_first_allocation_v1 as frozen_allocation


VERSION: Final = "corpus-r6-construction-allocation-cross-v1"
REGISTRY_SCHEMA: Final = "corpus-r6-construction-allocation-registry/v1"
SELECTION_SCHEMA: Final = "corpus-r6-construction-allocation-selection/v1"
SOURCE_MANIFEST_SCHEMA: Final = (
    "corpus-r6-construction-allocation-source-manifest/v1"
)
SOURCE_DESCRIPTOR_SCHEMA: Final = (
    "corpus-r6-construction-allocation-source-descriptor/v1"
)
SELECTION_CERTIFICATE_SCHEMA: Final = (
    "corpus-r6-construction-allocation-selector-support/v2"
)
PANEL_SEASONS: Final = (2023, 2024, 2025)
FOUNDRY_G0_PANEL_ID: Final = (
    "v12:ef445e2b31a7756609b458753dc064318b58ea2912e9277071c08fd0d07392e0"
)
FOUNDRY_G0_PANEL_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-parametric/research/"
        "corpus-parametric-research/panels/20260823-foundry-production-v12/"
        "foundry-v12-combined-panel-index-v1.json"
    ),
    "generation": "1787663639938214",
    "sha256": "4d41acd9277e525cd8521071b62390281c442d6324db1e3f5812bf59920c16f9",
    "bytes": 209_279,
}
EXPECTED_SLATE_IDS: Final = tuple(
    f"{season}-w{week:02d}"
    for season in PANEL_SEASONS
    for week in range(1, 19)
)
SEED_LABELS: Final = ("R0", "R1", "R2", "R3", "R4")
WORLDS_PER_BLOCK: Final = 10_000
CORE_SOLVES_PER_BLOCK: Final = 200
ROLE_SOLVES_PER_BLOCK: Final = 12
TAIL_LINE: Final = 194.0
ENTRIES: Final = 80
PREFIXES: Final = (20, 40, 80)
THRESHOLDS: Final = (194, 200, 210, 220, 230, 240)

ALLOCATION_INCUMBENT: Final = "lev160-boom40"
ALLOCATION_BOOM_FIRST: Final = "lev40-boom160"
ALLOCATION_ORDER: Final = (ALLOCATION_INCUMBENT, ALLOCATION_BOOM_FIRST)
PRESET_ORDER: Final = (INCUMBENT_GPP_PRESET_ID, LEGALITY_ONLY_PRESET_ID)


def _cell_id(preset_id: str, allocation_id: str) -> str:
    return f"{preset_id}--{allocation_id}"


CELL_ORDER: Final = tuple(
    _cell_id(preset_id, allocation_id)
    for preset_id in PRESET_ORDER
    for allocation_id in ALLOCATION_ORDER
)
CELL_DEFINITION: Final = {
    _cell_id(preset_id, allocation_id): {
        "construction_preset_id": preset_id,
        "allocation_id": allocation_id,
        "leverage": 160 if allocation_id == ALLOCATION_INCUMBENT else 40,
        "boom": 40 if allocation_id == ALLOCATION_INCUMBENT else 160,
    }
    for preset_id in PRESET_ORDER
    for allocation_id in ALLOCATION_ORDER
}

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CODE_SHA = re.compile(r"^[0-9a-f]{7,40}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")
_OUTCOME_NAMES = frozenset({
    "actual", "actual_score", "contest_rank", "dk_points", "dst_dk_points",
    "field_rank", "final_score", "outcome", "payout", "realized",
    "realized_score", "roi", "settled_score", "was_active", "winner",
    "winner_score",
})


class ConstructionAllocationCrossError(ValueError):
    """The score-blind four-cell release differs from its frozen contract."""


def _fail(message: str) -> None:
    raise ConstructionAllocationCrossError(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ConstructionAllocationCrossError(
            "value is not canonical JSON"
        ) from exc


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _content_identity(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} is not a content identity")
    required = {"uri", "generation", "sha256", "bytes"}
    if not required <= set(value):
        _fail(f"{label} lacks content identity fields")
    uri = value.get("uri")
    generation = value.get("generation")
    digest = value.get("sha256")
    size = value.get("bytes")
    if (
        type(uri) is not str
        or not uri
        or type(generation) not in {str, int}
        or not str(generation)
        or type(digest) is not str
        or _SHA256.fullmatch(digest) is None
        or type(size) is not int
        or size <= 0
    ):
        _fail(f"{label} content identity differs")
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": digest,
        "bytes": size,
    }


_SOURCE_FRAME_ROLES: Final = (
    "mixed_walk_forward_panel",
    "prelock_dst_projection",
    "common_lock_market_points",
    "tabpfn_marginals",
)


def _frame_receipt(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "sha256", "bytes", "rows", "columns",
    }:
        _fail(f"{label} frame receipt differs")
    digest = value.get("sha256")
    size = value.get("bytes")
    rows = value.get("rows")
    columns = value.get("columns")
    if (
        type(digest) is not str
        or _SHA256.fullmatch(digest) is None
        or type(size) is not int
        or size <= 0
        or type(rows) is not int
        or rows < 0
        or not isinstance(columns, list)
        or not columns
        or any(type(column) is not str or not column for column in columns)
        or len(columns) != len(set(columns))
    ):
        _fail(f"{label} frame receipt differs")
    return {
        "sha256": digest,
        "bytes": size,
        "rows": rows,
        "columns": list(columns),
    }


def source_manifest_v1(
    *,
    season: int,
    week: int,
    slate_id: str,
    input_frame_receipts: Mapping[str, Mapping[str, object]],
    lock_identity: Mapping[str, object],
    audit_bank_identity: Mapping[str, object],
) -> dict[str, object]:
    """Bind every model/market frame and the predeclared audit bank.

    The returned document is the exact byte body named by
    :attr:`CrossSlate.source_identity`; an opaque URI or digest is not enough.
    """

    if (
        type(season) is not int
        or type(week) is not int
        or slate_id != f"{season}-w{week:02d}"
        or season not in PANEL_SEASONS
        or not 1 <= week <= 18
    ):
        _fail("source manifest slate differs")
    if not isinstance(input_frame_receipts, Mapping) or set(
        input_frame_receipts
    ) != set(_SOURCE_FRAME_ROLES):
        _fail("source manifest frame roles differ")
    frames = {
        role: _frame_receipt(
            input_frame_receipts[role], label=f"source manifest {role}"
        )
        for role in _SOURCE_FRAME_ROLES
    }
    body: dict[str, object] = {
        "schema_version": SOURCE_MANIFEST_SCHEMA,
        "season": season,
        "week": week,
        "slate_id": slate_id,
        "input_frame_receipts": frames,
        "lock_identity": _content_identity(
            lock_identity, label=f"{slate_id} common-lock authority"
        ),
        "audit_bank_identity": _content_identity(
            audit_bank_identity, label=f"{slate_id} audit bank"
        ),
        "audit_bank_role": "independent-diagnostic-only",
        "audit_bank_opened_during_selection": False,
        "all_four_cells_share_exact_inputs": True,
        "uses_target_slate_outcomes": False,
        "post_lock_data_read": False,
    }
    return {**body, "manifest_sha256": canonical_sha256(body)}


def validate_source_manifest_v1(
    value: object,
    *,
    season: int,
    week: int,
    slate_id: str,
    audit_bank_identity: Mapping[str, object],
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("source manifest is not a mapping")
    item = dict(value)
    retained = item.pop("manifest_sha256", None)
    if (
        type(retained) is not str
        or _SHA256.fullmatch(retained) is None
        or canonical_sha256(item) != retained
        or item.get("schema_version") != SOURCE_MANIFEST_SCHEMA
        or item.get("season") != season
        or item.get("week") != week
        or item.get("slate_id") != slate_id
        or item.get("audit_bank_role") != "independent-diagnostic-only"
        or item.get("audit_bank_opened_during_selection") is not False
        or item.get("all_four_cells_share_exact_inputs") is not True
        or item.get("uses_target_slate_outcomes") is not False
        or item.get("post_lock_data_read") is not False
    ):
        _fail("source manifest differs")
    expected = source_manifest_v1(
        season=season,
        week=week,
        slate_id=slate_id,
        input_frame_receipts=item.get("input_frame_receipts", {}),
        lock_identity=item.get("lock_identity", {}),
        audit_bank_identity=audit_bank_identity,
    )
    if expected != {**item, "manifest_sha256": retained}:
        _fail("source manifest canonical replay differs")
    return expected


def _source_document_descriptor_v1(
    value: object,
    *,
    source_identity: Mapping[str, object],
    season: int,
    week: int,
    slate_id: str,
    audit_bank_identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    """Validate either a PIT manifest or the already-frozen 54-slate snapshot."""

    if not isinstance(value, Mapping):
        _fail(f"{slate_id} source document is not a mapping")
    schema = value.get("schema_version")
    if schema == SOURCE_MANIFEST_SCHEMA:
        document = validate_source_manifest_v1(
            value,
            season=season,
            week=week,
            slate_id=slate_id,
            audit_bank_identity=audit_bank_identity,
        )
        lock_identity = _content_identity(
            document["lock_identity"], label=f"{slate_id} common lock"
        )
        internal_sha = str(document["manifest_sha256"])
        validation_law = "pit-frame-manifest-canonical-replay"
    elif schema == frozen_allocation.GENERATION_SNAPSHOT_SCHEMA:
        try:
            document = frozen_allocation.validate_generation_snapshot_v1(value)
        except frozen_allocation.CorpusR6BoomFirstAllocationV1Error as exc:
            raise ConstructionAllocationCrossError(str(exc)) from exc
        if (
            document.get("season") != season
            or document.get("week") != week
            or document.get("slate_id") != slate_id
            or document.get("uses_realized_outcomes") is not False
        ):
            _fail(f"{slate_id} frozen generation snapshot differs")
        lock_identity = _content_identity(
            document.get("later_source_identity"),
            label=f"{slate_id} later-source lock",
        )
        internal_sha = str(document.get("generation_snapshot_sha256", ""))
        validation_law = "boom-first-generation-snapshot-v1-exact-replay"
    else:
        _fail(f"{slate_id} source document schema differs")
    if _SHA256.fullmatch(internal_sha) is None:
        _fail(f"{slate_id} source document internal identity differs")
    identity = _content_identity(source_identity, label=f"{slate_id} source")
    raw = canonical_json_bytes(document)
    if (
        identity["sha256"] != hashlib.sha256(raw).hexdigest()
        or identity["bytes"] != len(raw)
    ):
        _fail(f"{slate_id} source identity is not bound to its exact document")
    audit = _content_identity(
        audit_bank_identity, label=f"{slate_id} audit bank"
    )
    body: dict[str, object] = {
        "schema_version": SOURCE_DESCRIPTOR_SCHEMA,
        "season": season,
        "week": week,
        "slate_id": slate_id,
        "source_document_schema": schema,
        "source_document_internal_sha256": internal_sha,
        "source_identity": identity,
        "lock_identity": lock_identity,
        "audit_bank_identity": audit,
        "validation_law": validation_law,
        "source_document_exact_bytes_validated": True,
        "uses_target_slate_outcomes": False,
        "post_lock_data_read": False,
    }
    return document, {**body, "descriptor_sha256": canonical_sha256(body)}


def _validate_source_descriptor_v1(
    value: object,
    *,
    source_identity: Mapping[str, object],
    season: int,
    week: int,
    slate_id: str,
    audit_bank_identity: Mapping[str, object],
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("source descriptor is not a mapping")
    item = dict(value)
    retained = item.pop("descriptor_sha256", None)
    expected_schema = item.get("source_document_schema")
    expected_law = {
        SOURCE_MANIFEST_SCHEMA: "pit-frame-manifest-canonical-replay",
        frozen_allocation.GENERATION_SNAPSHOT_SCHEMA: (
            "boom-first-generation-snapshot-v1-exact-replay"
        ),
    }.get(expected_schema)
    if (
        type(retained) is not str
        or _SHA256.fullmatch(retained) is None
        or canonical_sha256(item) != retained
        or item.get("schema_version") != SOURCE_DESCRIPTOR_SCHEMA
        or item.get("season") != season
        or item.get("week") != week
        or item.get("slate_id") != slate_id
        or expected_law is None
        or item.get("validation_law") != expected_law
        or item.get("source_document_exact_bytes_validated") is not True
        or item.get("uses_target_slate_outcomes") is not False
        or item.get("post_lock_data_read") is not False
        or _SHA256.fullmatch(str(item.get(
            "source_document_internal_sha256", ""
        ))) is None
        or item.get("source_identity")
        != _content_identity(source_identity, label=f"{slate_id} source")
        or item.get("audit_bank_identity")
        != _content_identity(
            audit_bank_identity, label=f"{slate_id} audit bank"
        )
    ):
        _fail("source descriptor differs")
    _content_identity(item.get("lock_identity"), label=f"{slate_id} lock")
    return {**item, "descriptor_sha256": retained}


def _outcome_field(name: object) -> bool:
    value = str(name).strip().lower()
    return (
        value in _OUTCOME_NAMES
        or value.startswith("y_")
        or value.startswith("realized_")
        or value.endswith("_actual")
    )


def _forbidden_paths(value: object, *, path: str) -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            child = f"{path}.{key}"
            if _outcome_field(key):
                found.append(child)
            found.extend(_forbidden_paths(nested, path=child))
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            found.extend(_forbidden_paths(nested, path=f"{path}[{index}]"))
    return found


@dataclass(frozen=True, slots=True)
class CrossSlate:
    """One immutable, target-outcome-null slate in the exact G0 panel."""

    season: int
    week: int
    slate_id: str
    source_identity: Mapping[str, object]
    source_manifest: Mapping[str, object]
    audit_bank_identity: Mapping[str, object]

    def __post_init__(self) -> None:
        if type(self.season) is not int or type(self.week) is not int:
            _fail("slate season/week must be exact integers")
        if self.season not in PANEL_SEASONS or not 1 <= self.week <= 18:
            _fail("slate lies outside the exact 2023-2025 panel")
        if self.slate_id != f"{self.season}-w{self.week:02d}":
            _fail("slate ID must be canonical season-week")
        _source_document_descriptor_v1(
            self.source_manifest,
            source_identity=self.source_identity,
            season=self.season,
            week=self.week,
            slate_id=self.slate_id,
            audit_bank_identity=self.audit_bank_identity,
        )


@dataclass(frozen=True, slots=True)
class CrossPanelAuthority:
    """Create-once identity for the exact ordered Foundry G0 54-slate panel."""

    panel_id: str
    expected_slate_ids: Sequence[str]
    identity: Mapping[str, object]


NativeBookBuilder = Callable[
    [CrossSlate, str, str, int, int, Mapping[str, str], Mapping[str, object]],
    CandidateBatch,
]


def _identity_fields(
    *, panel_id: str, code_sha: str, image_digest: str,
) -> tuple[str, str, str]:
    panel = str(panel_id).strip()
    code = str(code_sha).strip().lower()
    image = str(image_digest).strip().lower()
    if _ID.fullmatch(panel) is None:
        _fail("panel ID differs")
    if _CODE_SHA.fullmatch(code) is None:
        _fail("code SHA differs")
    if not image.startswith("sha256:") or _SHA256.fullmatch(image[7:]) is None:
        _fail("immutable image digest differs")
    return panel, code, image


def _preset_receipt(preset_id: str) -> dict[str, object]:
    receipt = resolve_construction_preset(preset_id).receipt()
    if (
        receipt.get("base_preset_id") != preset_id
        or _SHA256.fullmatch(str(receipt.get("sha256", ""))) is None
        or receipt.get("effective_id")
        != f"{preset_id}@sha256:{receipt['sha256']}"
    ):
        _fail(f"{preset_id} receipt differs")
    return receipt


def cell_environments(
    base: Mapping[str, str] | None = None,
) -> dict[str, dict[str, str]]:
    """Resolve the exact four cell environments as explicit data."""

    result: dict[str, dict[str, str]] = {}
    for cell_id in CELL_ORDER:
        definition = CELL_DEFINITION[cell_id]
        preset = resolve_construction_preset(
            str(definition["construction_preset_id"])
        )
        environment = ADOPTED_CLASSIC_POLICY.engine_environment(
            base, construction_preset=preset,
        )
        boom = int(definition["boom"])
        environment.update({
            "N_LEV": str(definition["leverage"]),
            "N_BOOM": str(boom),
            "GEN_TOTAL_BUDGET": str(boom + ROLE_SOLVES_PER_BLOCK),
            "BOOM_UNIQUE_FILL": "0",
            "PROSPECTIVE_GENERATION_EXPOSURE": "1",
            "PROSPECTIVE_SHADOW_ID": f"2026-{cell_id}-diagnostic-v1",
        })
        result[cell_id] = environment
    validate_cell_environments(result)
    return result


def validate_cell_environments(
    value: Mapping[str, Mapping[str, str]],
) -> dict[str, object]:
    """Fail closed on budget, construction, or non-factor environment drift."""

    if not isinstance(value, Mapping) or set(value) != set(CELL_ORDER):
        _fail("construction-allocation cell order differs")
    construction_keys = set(
        resolve_construction_preset(INCUMBENT_GPP_PRESET_ID)
        .optimizer_environment()
    )
    allocation_keys = {
        "N_LEV", "N_BOOM", "GEN_TOTAL_BUDGET", "PROSPECTIVE_SHADOW_ID",
    }
    reference = dict(value[CELL_ORDER[0]])
    hashes: dict[str, str] = {}
    for cell_id in CELL_ORDER:
        environment = value[cell_id]
        definition = CELL_DEFINITION[cell_id]
        if not isinstance(environment, Mapping) or any(
            type(key) is not str or type(item) is not str
            for key, item in environment.items()
        ):
            _fail(f"{cell_id} environment is not string-to-string")
        preset = resolve_construction_preset(
            str(definition["construction_preset_id"])
        )
        expected_construction = preset.optimizer_environment()
        if any(environment.get(key) != expected for key, expected in (
            expected_construction.items()
        )):
            _fail(f"{cell_id} construction environment differs")
        if (
            environment.get("N_LEV") != str(definition["leverage"])
            or environment.get("N_BOOM") != str(definition["boom"])
            or environment.get("GEN_TOTAL_BUDGET")
            != str(int(definition["boom"]) + ROLE_SOLVES_PER_BLOCK)
            or environment.get("N_EPISTEMIC") != str(ROLE_SOLVES_PER_BLOCK)
            or environment.get("EPISTEMIC_FAMILY") != "role_draws"
            or environment.get("MODEL_ENSEMBLE") != "1"
            or environment.get("MULTISEED_PORTFOLIO") != "CBWU"
            or environment.get("MULTISEED_WORLDS_PER_BLOCK")
            != str(WORLDS_PER_BLOCK)
            or environment.get("MULTISEED_CANDIDATE_ENTRY_BASIS") != "80"
            or environment.get("SELECT_LSE") != "0"
            or environment.get("SELECT_LADDER") != ""
            or environment.get("PROSPECTIVE_GENERATION_EXPOSURE") != "1"
            or environment.get("BOOM_UNIQUE_FILL") != "0"
        ):
            _fail(f"{cell_id} fixed generation or retrieval law differs")
        for key in set(reference) | set(environment):
            if key in allocation_keys or key in construction_keys:
                continue
            if reference.get(key) != environment.get(key):
                _fail(f"cell environments differ outside factors at {key}")
        hashes[cell_id] = canonical_sha256(dict(sorted(environment.items())))
    return {
        "cell_order": list(CELL_ORDER),
        "environment_sha256": hashes,
        "only_declared_factor_differences": True,
        "same_role_family_and_dose": True,
        "same_model_market_seed_retry_and_selector_law": True,
    }


def registry_document(
    *, code_sha: str,
) -> dict[str, object]:
    """Return the complete score-blind four-cell registry."""

    if _CODE_SHA.fullmatch(str(code_sha).strip().lower()) is None:
        _fail("registry code SHA differs")
    environments = cell_environments({"CODE_SHA": str(code_sha).lower()})
    policy = ADOPTED_CLASSIC_POLICY
    if (
        tuple(f"R{index}" for index in range(len(policy.multiseed_seed_pairs)))
        != SEED_LABELS
        or policy.multiseed_worlds_per_block != WORLDS_PER_BLOCK
        or policy.default_entries != ENTRIES
        or policy.tail_line != TAIL_LINE
    ):
        _fail("adopted policy no longer matches the frozen cross")
    cells = []
    for cell_id in CELL_ORDER:
        definition = CELL_DEFINITION[cell_id]
        cells.append({
            "cell_id": cell_id,
            "construction_preset_id": definition["construction_preset_id"],
            "construction_preset_receipt": _preset_receipt(
                str(definition["construction_preset_id"])
            ),
            "allocation_id": definition["allocation_id"],
            "per_block_requested": {
                "leverage": definition["leverage"],
                "boom": definition["boom"],
                "core": CORE_SOLVES_PER_BLOCK,
                "role": ROLE_SOLVES_PER_BLOCK,
            },
            "per_slate_requested": {
                "leverage": int(definition["leverage"]) * len(SEED_LABELS),
                "boom": int(definition["boom"]) * len(SEED_LABELS),
                "core": CORE_SOLVES_PER_BLOCK * len(SEED_LABELS),
                "role": ROLE_SOLVES_PER_BLOCK * len(SEED_LABELS),
            },
            "environment_sha256": canonical_sha256(dict(sorted(
                environments[cell_id].items()
            ))),
        })
    body: dict[str, object] = {
        "schema_version": REGISTRY_SCHEMA,
        "version": VERSION,
        "code_sha": str(code_sha).lower(),
        "panel_seasons": list(PANEL_SEASONS),
        "foundry_g0_panel_id": FOUNDRY_G0_PANEL_ID,
        "foundry_g0_panel_identity": dict(FOUNDRY_G0_PANEL_IDENTITY),
        "expected_slate_ids": list(EXPECTED_SLATE_IDS),
        "slate_count": len(EXPECTED_SLATE_IDS),
        "seed_pairs": [
            {
                "seed_label": f"R{index}",
                "projection_seed": int(projection),
                "role_seed": int(role),
            }
            for index, (projection, role) in enumerate(
                policy.multiseed_seed_pairs
            )
        ],
        "worlds_per_block": WORLDS_PER_BLOCK,
        "generation_blocks_per_slate": len(SEED_LABELS),
        "tail_line": TAIL_LINE,
        "selection": "incumbent-greedy-tail-coverage-194",
        "entry_count": ENTRIES,
        "prefixes": list(PREFIXES),
        "thresholds": list(THRESHOLDS),
        "cells": cells,
        "bounded_execution": {
            "walk_forward_seed_model_materializations": (
                len(PANEL_SEASONS) * len(SEED_LABELS)
            ),
            "shared_slate_world_bank_slices": (
                len(EXPECTED_SLATE_IDS) * len(SEED_LABELS)
            ),
            "native_candidate_books": (
                len(EXPECTED_SLATE_IDS) * len(SEED_LABELS) * len(CELL_ORDER)
            ),
            "requested_core_optimizer_solves": (
                len(EXPECTED_SLATE_IDS)
                * len(SEED_LABELS)
                * len(CELL_ORDER)
                * CORE_SOLVES_PER_BLOCK
            ),
            "requested_role_optimizer_solves": (
                len(EXPECTED_SLATE_IDS)
                * len(SEED_LABELS)
                * len(CELL_ORDER)
                * ROLE_SOLVES_PER_BLOCK
            ),
            "model_world_bank_reused_across_all_four_cells": True,
            "no_unregistered_cell_or_adaptive_retry_budget": True,
        },
        "primary_estimand": "k80-allocation-by-construction-difference-in-differences",
        "historical_evidence_status": "descriptive-diagnostic-only",
        "uses_target_slate_outcomes": False,
        "automatic_policy_promotion": False,
        "existing_five_arm_suite_modified": False,
    }
    return {**body, "registry_sha256": canonical_sha256(body)}


def validate_registry(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("registry is not a mapping")
    item = dict(value)
    retained = item.pop("registry_sha256", None)
    if (
        type(retained) is not str
        or _SHA256.fullmatch(retained) is None
        or canonical_sha256(item) != retained
    ):
        _fail("registry self-hash differs")
    expected = registry_document(code_sha=str(item.get("code_sha", "")))
    if expected != {**item, "registry_sha256": retained}:
        _fail("registry canonical replay differs")
    return expected


def _array_receipt(
    value: np.ndarray, *, player_ids: Sequence[str] | None = None,
) -> dict[str, object]:
    array = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    header: dict[str, object] = {
        "dtype": array.dtype.str,
        "shape": [int(part) for part in array.shape],
    }
    if player_ids is not None:
        header["player_ids"] = list(player_ids)
    digest.update(canonical_json_bytes(header))
    digest.update(array.tobytes(order="C"))
    return {
        "dtype": array.dtype.str,
        "shape": [int(part) for part in array.shape],
        "sha256": digest.hexdigest(),
    }


def _validate_array_receipt(
    value: object,
    *,
    label: str,
    expected_shape: Sequence[int] | None = None,
    require_player_ids: bool = False,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} array receipt differs")
    required = {"dtype", "shape", "sha256"}
    if require_player_ids:
        required.add("player_ids")
    if set(value) != required:
        _fail(f"{label} array receipt differs")
    dtype = value.get("dtype")
    shape = value.get("shape")
    digest = value.get("sha256")
    if (
        type(dtype) is not str
        or not dtype
        or not isinstance(shape, list)
        or not shape
        or any(type(part) is not int or part < 0 for part in shape)
        or (expected_shape is not None and shape != [int(x) for x in expected_shape])
        or type(digest) is not str
        or _SHA256.fullmatch(digest) is None
    ):
        _fail(f"{label} array receipt differs")
    if require_player_ids:
        player_ids = value.get("player_ids")
        if (
            not isinstance(player_ids, list)
            or len(player_ids) != shape[0]
            or any(type(player_id) is not str or not player_id for player_id in player_ids)
            or len(player_ids) != len(set(player_ids))
        ):
            _fail(f"{label} player identity differs")
    return dict(value)


def _compressed_array(value: np.ndarray) -> dict[str, object]:
    array = np.ascontiguousarray(value)
    raw = array.tobytes(order="C")
    compressed = zlib.compress(raw, level=9)
    return {
        "dtype": array.dtype.str,
        "shape": [int(part) for part in array.shape],
        "raw_bytes": len(raw),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "codec": "zlib-9-base64",
        "payload": base64.b64encode(compressed).decode("ascii"),
        "payload_bytes": len(compressed),
        "payload_sha256": hashlib.sha256(compressed).hexdigest(),
    }


def _reopen_compressed_array(
    value: object,
    *,
    label: str,
    expected_dtype: str,
    expected_shape: Sequence[int],
) -> np.ndarray:
    if not isinstance(value, Mapping) or set(value) != {
        "dtype", "shape", "raw_bytes", "raw_sha256", "codec", "payload",
        "payload_bytes", "payload_sha256",
    }:
        _fail(f"{label} compressed array differs")
    if (
        value.get("dtype") != expected_dtype
        or value.get("shape") != [int(part) for part in expected_shape]
        or value.get("codec") != "zlib-9-base64"
        or type(value.get("raw_bytes")) is not int
        or int(value["raw_bytes"]) < 0
        or type(value.get("payload_bytes")) is not int
        or int(value["payload_bytes"]) <= 0
        or _SHA256.fullmatch(str(value.get("raw_sha256", ""))) is None
        or _SHA256.fullmatch(str(value.get("payload_sha256", ""))) is None
        or type(value.get("payload")) is not str
    ):
        _fail(f"{label} compressed array differs")
    try:
        compressed = base64.b64decode(value["payload"], validate=True)
    except (ValueError, TypeError) as exc:
        raise ConstructionAllocationCrossError(
            f"{label} base64 differs"
        ) from exc
    if (
        len(compressed) != value["payload_bytes"]
        or hashlib.sha256(compressed).hexdigest() != value["payload_sha256"]
    ):
        _fail(f"{label} compressed payload identity differs")
    try:
        raw = zlib.decompress(compressed)
    except zlib.error as exc:
        raise ConstructionAllocationCrossError(
            f"{label} compressed payload differs"
        ) from exc
    if (
        len(raw) != value["raw_bytes"]
        or hashlib.sha256(raw).hexdigest() != value["raw_sha256"]
    ):
        _fail(f"{label} raw identity differs")
    dtype = np.dtype(expected_dtype)
    expected_size = int(np.prod(expected_shape, dtype=np.int64)) * dtype.itemsize
    if len(raw) != expected_size:
        _fail(f"{label} raw size differs")
    return np.frombuffer(raw, dtype=dtype).reshape(tuple(expected_shape)).copy()


def _coverage_selection_certificate(
    totals: np.ndarray,
    *,
    selected_ordinals: Sequence[int],
    candidate_matrix_receipt: Mapping[str, object],
) -> dict[str, object]:
    """Persist the exact score-blind support consumed by the K80 selector.

    The selector needs the candidate-by-world 194-clear mask and the exact
    mean-score tiebreaker, not the full floating-point totals matrix.  The mask
    is bit-packed before compression.  A later process can therefore replay
    ``select_from_support`` from the persisted production input rather than
    trusting a producer-declared path or a post-hoc marginal-gain summary.
    """

    # Match ``select_tail_entries`` exactly: it promotes the candidate matrix
    # to the platform float dtype before computing either clear masks or means.
    matrix = np.asarray(totals, dtype=float)
    if matrix.ndim != 2 or not np.isfinite(matrix).all():
        _fail("selector certificate matrix differs")
    candidate_count, world_count = matrix.shape
    if candidate_count < ENTRIES or world_count <= 0:
        _fail("selector certificate dimensions differ")
    clears = matrix >= TAIL_LINE
    mean_totals = matrix.mean(axis=1).astype("<f8")
    packed_clears = np.packbits(
        np.ascontiguousarray(clears).reshape(-1), bitorder="little"
    ).astype("|u1", copy=False)
    selector_support_header = {
        "candidate_count": candidate_count,
        "world_count": world_count,
        "tail_line": TAIL_LINE,
        "bitorder": "little",
        "clear_mask_raw_bytes": int(packed_clears.nbytes),
        "mean_totals_raw_bytes": int(mean_totals.nbytes),
    }
    support_digest = hashlib.sha256()
    support_digest.update(canonical_json_bytes(selector_support_header))
    support_digest.update(packed_clears.tobytes(order="C"))
    support_digest.update(mean_totals.tobytes(order="C"))
    replayed = select_from_support(
        clears, clears.mean(axis=1), matrix.mean(axis=1), ENTRIES
    )
    expected = [int(value) for value in selected_ordinals]
    if replayed != expected:
        _fail(
            "selector certificate does not reproduce K80: "
            f"support={replayed[:12]} expected={expected[:12]}"
        )
    body: dict[str, object] = {
        "schema_version": SELECTION_CERTIFICATE_SCHEMA,
        "selector": "incumbent-greedy-tail-coverage",
        "tail_line": TAIL_LINE,
        "entry_count": ENTRIES,
        "candidate_count": candidate_count,
        "world_count": world_count,
        "candidate_matrix_receipt": dict(candidate_matrix_receipt),
        "selector_support_header": selector_support_header,
        "selector_support_sha256": support_digest.hexdigest(),
        "clear_mask_packbits": _compressed_array(packed_clears),
        "mean_totals": _compressed_array(mean_totals),
        "selected_candidate_ordinals": expected,
    }
    return {**body, "certificate_sha256": canonical_sha256(body)}


def _validate_coverage_selection_certificate(
    value: object,
    *,
    candidate_count: int,
    candidate_matrix_receipt: Mapping[str, object],
    selected_ordinals: Sequence[int],
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("selector certificate is not a mapping")
    item = dict(value)
    retained = item.pop("certificate_sha256", None)
    world_count = item.get("world_count")
    packed_bytes = (candidate_count * int(world_count or 0) + 7) // 8
    expected_header = {
        "candidate_count": candidate_count,
        "world_count": world_count,
        "tail_line": TAIL_LINE,
        "bitorder": "little",
        "clear_mask_raw_bytes": packed_bytes,
        "mean_totals_raw_bytes": candidate_count * np.dtype("<f8").itemsize,
    }
    if (
        type(retained) is not str
        or _SHA256.fullmatch(retained) is None
        or canonical_sha256(item) != retained
        or item.get("schema_version") != SELECTION_CERTIFICATE_SCHEMA
        or item.get("selector") != "incumbent-greedy-tail-coverage"
        or item.get("tail_line") != TAIL_LINE
        or item.get("entry_count") != ENTRIES
        or item.get("candidate_count") != candidate_count
        or type(world_count) is not int
        or world_count <= 0
        or item.get("selector_support_header") != expected_header
        or _SHA256.fullmatch(str(item.get("selector_support_sha256", "")))
        is None
        or item.get("candidate_matrix_receipt")
        != dict(candidate_matrix_receipt)
        or item.get("selected_candidate_ordinals")
        != [int(value) for value in selected_ordinals]
    ):
        _fail("selector certificate differs")
    packed_clears = _reopen_compressed_array(
        item.get("clear_mask_packbits"),
        label="selector packed clear mask",
        expected_dtype="|u1",
        expected_shape=(packed_bytes,),
    )
    mean_totals = _reopen_compressed_array(
        item.get("mean_totals"),
        label="selector mean totals",
        expected_dtype="<f8",
        expected_shape=(candidate_count,),
    )
    if not np.isfinite(mean_totals).all():
        _fail("selector certificate statistics differ")
    support_digest = hashlib.sha256()
    support_digest.update(canonical_json_bytes(expected_header))
    support_digest.update(packed_clears.tobytes(order="C"))
    support_digest.update(mean_totals.tobytes(order="C"))
    if support_digest.hexdigest() != item["selector_support_sha256"]:
        _fail("selector support identity differs")
    bit_count = candidate_count * world_count
    clears = np.unpackbits(
        packed_clears, bitorder="little", count=bit_count
    ).reshape((candidate_count, world_count)).astype(bool, copy=False)
    replayed = select_from_support(
        clears,
        clears.mean(axis=1),
        mean_totals,
        ENTRIES,
    )
    if replayed != [int(value) for value in selected_ordinals]:
        _fail("selector certificate K80 replay differs")
    return {**item, "certificate_sha256": retained}


def _roster(lineup: object, *, label: str) -> tuple[str, ...]:
    ids = tuple(sorted(str(value) for value in getattr(lineup, "ids", ())))
    if len(ids) != 9 or len(set(ids)) != 9 or any(not value for value in ids):
        _fail(f"{label} is not an exact-nine roster")
    return ids


def _player_catalog(batch: CandidateBatch) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    required = {"id", "pos", "team", "opp", "game_id", "salary"}
    for raw in batch.player_rows:
        if not isinstance(raw, Mapping) or not required <= set(raw):
            _fail("candidate player catalog lacks construction fields")
        salary = raw["salary"]
        if (
            isinstance(salary, bool)
            or not isinstance(salary, (int, float))
            or not math.isfinite(float(salary))
            or int(salary) != float(salary)
            or not 0 < int(salary) <= 50_000
        ):
            _fail("candidate player salary differs")
        row = {
            "id": str(raw["id"]),
            "pos": str(raw["pos"]),
            "team": str(raw["team"]),
            "opp": str(raw["opp"]),
            "game_id": str(raw["game_id"]),
            "salary": int(salary),
        }
        if (
            any(not str(row[key]) for key in (
                "id", "pos", "team", "opp", "game_id"
            ))
            or row["pos"] not in {"QB", "RB", "WR", "TE", "DST"}
        ):
            _fail("candidate player catalog contains an empty identity")
        rows.append(row)
    ids = [row["id"] for row in rows]
    if ids != list(batch.player_ids) or len(set(ids)) != len(ids):
        _fail("candidate player catalog/order differs")
    return rows


def _lineup_anatomy(
    roster: Sequence[str], catalog_by_id: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    try:
        rows = [catalog_by_id[str(player_id)] for player_id in roster]
    except KeyError as exc:
        _fail("selected roster is outside the player catalog")
    qbs = [row for row in rows if row["pos"] == "QB"]
    dsts = [row for row in rows if row["pos"] == "DST"]
    if len(qbs) != 1 or len(dsts) != 1:
        _fail("selected roster does not contain exact-one QB and DST")
    position_counts = Counter(str(row["pos"]) for row in rows)
    salary = sum(int(row["salary"]) for row in rows)
    team_count = len({str(row["team"]) for row in rows})
    dk_classic_legal = (
        position_counts.get("QB", 0) == 1
        and position_counts.get("DST", 0) == 1
        and position_counts.get("RB", 0) in {2, 3}
        and position_counts.get("WR", 0) in {3, 4}
        and position_counts.get("TE", 0) in {1, 2}
        and sum(position_counts.get(key, 0) for key in ("RB", "WR", "TE"))
        == 7
        and set(position_counts) <= {"QB", "RB", "WR", "TE", "DST"}
        and salary <= 50_000
        and team_count >= 2
    )
    if not dk_classic_legal:
        _fail("selected roster violates DraftKings Classic legality")
    qb = qbs[0]
    same_team_catchers = sum(
        row["pos"] in {"WR", "TE"} and row["team"] == qb["team"]
        for row in rows
    )
    bring_backs = sum(
        row["pos"] in {"RB", "WR", "TE"} and row["team"] == qb["opp"]
        for row in rows
    )
    rb_teams = [str(row["team"]) for row in rows if row["pos"] == "RB"]
    dst = dsts[0]
    rb_vs_dst = any(
        row["pos"] == "RB" and row["team"] == dst["opp"]
        for row in rows
    )
    return {
        "salary": salary,
        "team_count": team_count,
        "dk_classic_legal": dk_classic_legal,
        "game_count": len({str(row["game_id"]) for row in rows}),
        "qb_same_team_pass_catchers": same_team_catchers,
        "qb_opponent_bring_backs": bring_backs,
        "rb_vs_dst": rb_vs_dst,
        "two_rb_same_team": len(rb_teams) != len(set(rb_teams)),
        "punt_count_at_or_below_4000": sum(
            int(row["salary"]) <= 4_000 for row in rows
        ),
    }


def _preset_satisfied(
    anatomy: Mapping[str, object], preset: ConstructionPreset,
) -> bool:
    return (
        anatomy["dk_classic_legal"] is True
        and int(anatomy["salary"]) >= preset.min_salary
        and int(anatomy["game_count"]) >= preset.min_games
        and int(anatomy["qb_same_team_pass_catchers"])
        >= preset.stack.qb_stack_min
        and int(anatomy["qb_opponent_bring_backs"])
        >= preset.stack.bring_back_min
        and (
            not preset.stack.forbid_rb_vs_dst
            or anatomy["rb_vs_dst"] is False
        )
        and (
            not preset.stack.forbid_two_rb_same_team
            or anatomy["two_rb_same_team"] is False
        )
    )


def _rule_incidence(
    rosters: Sequence[Sequence[str]],
    catalog: Sequence[Mapping[str, object]],
    preset_id: str,
) -> dict[str, object]:
    by_id = {str(row["id"]): row for row in catalog}
    if len(by_id) != len(catalog):
        _fail("player catalog repeats an identity")
    preset = resolve_construction_preset(preset_id)
    anatomy = [_lineup_anatomy(roster, by_id) for roster in rosters]
    if not anatomy:
        _fail("rule incidence requires selected rosters")
    counts = {
        "draftkings_classic_legal": sum(
            row["dk_classic_legal"] is True for row in anatomy
        ),
        "salary_at_least_49000": sum(
            int(row["salary"]) >= 49_000 for row in anatomy
        ),
        "uses_at_least_two_games": sum(
            int(row["game_count"]) >= 2 for row in anatomy
        ),
        "qb_has_at_least_two_same_team_pass_catchers": sum(
            int(row["qb_same_team_pass_catchers"]) >= 2 for row in anatomy
        ),
        "qb_has_at_least_one_opponent_bring_back": sum(
            int(row["qb_opponent_bring_backs"]) >= 1 for row in anatomy
        ),
        "avoids_rb_vs_dst": sum(row["rb_vs_dst"] is False for row in anatomy),
        "avoids_two_rb_same_team": sum(
            row["two_rb_same_team"] is False for row in anatomy
        ),
        "satisfies_named_preset": sum(
            _preset_satisfied(row, preset) for row in anatomy
        ),
    }
    return {
        "selected_count": len(anatomy),
        "counts": counts,
        "salary_min": min(int(row["salary"]) for row in anatomy),
        "salary_max": max(int(row["salary"]) for row in anatomy),
        "game_count_distribution": dict(sorted(Counter(
            str(row["game_count"]) for row in anatomy
        ).items())),
        "qb_stack_count_distribution": dict(sorted(Counter(
            str(row["qb_same_team_pass_catchers"]) for row in anatomy
        ).items())),
        "bring_back_count_distribution": dict(sorted(Counter(
            str(row["qb_opponent_bring_backs"]) for row in anatomy
        ).items())),
        "punt_count_distribution": dict(sorted(Counter(
            str(row["punt_count_at_or_below_4000"]) for row in anatomy
        ).items())),
        "all_selected_satisfy_named_preset": (
            counts["satisfies_named_preset"] == len(anatomy)
        ),
    }


def _selected_overlap(rosters: Sequence[Sequence[str]]) -> dict[str, object]:
    normalized = [frozenset(str(value) for value in roster) for roster in rosters]
    counts = Counter()
    maximum = 0
    for left in range(len(normalized)):
        for right in range(left + 1, len(normalized)):
            overlap = len(normalized[left] & normalized[right])
            counts[str(overlap)] += 1
            maximum = max(maximum, overlap)
    return {
        "pair_count": sum(counts.values()),
        "maximum_player_overlap": maximum,
        "overlap_distribution": dict(sorted(counts.items())),
    }


def _set_overlap(left: Sequence[Sequence[str]], right: Sequence[Sequence[str]]) -> dict[str, object]:
    left_set = {tuple(str(value) for value in roster) for roster in left}
    right_set = {tuple(str(value) for value in roster) for roster in right}
    intersection = len(left_set & right_set)
    union = len(left_set | right_set)
    return {
        "left_count": len(left_set),
        "right_count": len(right_set),
        "intersection": intersection,
        "union": union,
        "jaccard": 1.0 if union == 0 else intersection / union,
    }


def _ledger_summary(
    value: object,
    *, cell_id: str,
    seed_label: str,
    leverage: int,
    boom: int,
    allocation: Mapping[str, object],
) -> dict[str, object]:
    try:
        ledger = validate_ledger(value)
    except Exception as exc:
        raise ConstructionAllocationCrossError(
            f"{cell_id}/{seed_label} exposure ledger differs"
        ) from exc
    expected = {"boom": boom, "leverage": leverage}
    if ledger["source_label"] != seed_label or ledger[
        "expected_requests_by_family"
    ] != expected:
        _fail(f"{cell_id}/{seed_label} exposure census differs")
    status = ledger["status_counts"]
    if (
        status["new"] + status["dup"]
        != int(allocation["leverage_successful"])
        + int(allocation["boom_successful"])
        or status["new"]
        != int(allocation["leverage_unique"])
        + int(allocation["boom_unique_added"])
        or status["dup"] != int(allocation["boom_duplicates"])
        or status["error"]
        != int(allocation["leverage_solver_errors"])
        + int(allocation["boom_solver_errors"])
        or status["infeasible"]
        != int(allocation["leverage_infeasible"])
        + int(allocation["boom_infeasible"])
    ):
        _fail(f"{cell_id}/{seed_label} exposure/allocation telemetry differs")
    return {
        "ledger_sha256": ledger["ledger_sha256"],
        "row_manifest_sha256": ledger["row_manifest_sha256"],
        "expected_requests_by_family": dict(ledger[
            "expected_requests_by_family"
        ]),
        "attempt_count": ledger["attempt_count"],
        "retry_attempt_count": (
            int(ledger["attempt_count"]) - leverage - boom
        ),
        "status_counts": dict(ledger["status_counts"]),
        "failure_or_exhaustion_count": (
            int(status["error"])
            + int(status["infeasible"])
            + int(status["exhausted"])
        ),
        "duration_seconds_by_family": dict(ledger[
            "duration_seconds_by_family"
        ]),
        "total_duration_seconds": ledger["total_duration_seconds"],
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }


def _native_receipt(
    batch: CandidateBatch,
    *,
    cell_id: str,
    seed_label: str,
    expected_preset: Mapping[str, object],
    expected_source_identity: Mapping[str, object],
    expected_source_descriptor: Mapping[str, object],
    expected_audit_bank_identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        _validate_candidate_batch(batch)
    except (TypeError, ValueError) as exc:
        raise ConstructionAllocationCrossError(
            f"{cell_id}/{seed_label} native batch differs: {exc}"
        ) from exc
    forbidden = _forbidden_paths({
        "player_rows": batch.player_rows,
        "candidates": [lineup.players for lineup in batch.candidates],
        "metadata": batch.metadata,
    }, path=f"{cell_id}.{seed_label}")
    if forbidden:
        _fail("score-blind native batch contains outcome fields: " + ", ".join(
            forbidden[:8]
        ))
    definition = CELL_DEFINITION[cell_id]
    leverage = int(definition["leverage"])
    boom = int(definition["boom"])
    allocation = batch.metadata.get("generation_allocation")
    timing = batch.metadata.get("generation_timing_seconds")
    if not isinstance(allocation, Mapping) or not isinstance(timing, Mapping):
        _fail(f"{cell_id}/{seed_label} lacks operational telemetry")
    expected_allocation = {
        "leverage_requested": leverage,
        "boom_requested": boom,
        "boom_attempted": boom,
        "ce_requested": 0,
        "role_or_epistemic_requested": ROLE_SOLVES_PER_BLOCK,
        "gumbel_requested": 0,
        "core_requested": CORE_SOLVES_PER_BLOCK,
        "total_requested_with_replacement_families": (
            CORE_SOLVES_PER_BLOCK + ROLE_SOLVES_PER_BLOCK
        ),
    }
    if any(allocation.get(key) != expected for key, expected in (
        expected_allocation.items()
    )):
        _fail(f"{cell_id}/{seed_label} requested-solve receipt differs")
    if allocation.get("boom_unique_fill") is not False:
        _fail(f"{cell_id}/{seed_label} boom unique-fill differs")
    telemetry_keys = (
        "leverage_solve_attempts", "leverage_solver_errors",
        "leverage_infeasible", "leverage_successful", "leverage_unique",
        "boom_successful", "boom_solver_errors", "boom_infeasible",
        "boom_failures", "boom_unique_added", "boom_duplicates",
    )
    for key in telemetry_keys:
        if type(allocation.get(key)) is not int or int(allocation[key]) < 0:
            _fail(f"{cell_id}/{seed_label} solver telemetry differs")
    if (
        int(allocation["leverage_unique"])
        != int(allocation["leverage_successful"])
        or int(allocation["leverage_solve_attempts"])
        != int(allocation["leverage_successful"])
        + int(allocation["leverage_infeasible"])
        + int(allocation["leverage_solver_errors"])
        or int(allocation["leverage_solve_attempts"]) > leverage * 2
        or int(allocation["boom_unique_added"])
        + int(allocation["boom_duplicates"])
        != int(allocation["boom_successful"])
        or int(allocation["boom_successful"])
        + int(allocation["boom_solver_errors"])
        + int(allocation["boom_infeasible"])
        != boom
        or int(allocation["boom_failures"])
        != int(allocation["boom_solver_errors"])
        + int(allocation["boom_infeasible"])
    ):
        _fail(f"{cell_id}/{seed_label} solver work reconciliation differs")
    if batch.metadata.get("construction_preset_receipt") != expected_preset:
        _fail(f"{cell_id}/{seed_label} construction preset receipt differs")
    if (
        batch.metadata.get("source_identity")
        != dict(expected_source_identity)
        or batch.metadata.get("source_document_internal_sha256")
        != expected_source_descriptor.get("source_document_internal_sha256")
        or batch.metadata.get("source_descriptor_sha256")
        != expected_source_descriptor.get("descriptor_sha256")
        or batch.metadata.get("audit_bank_identity")
        != dict(expected_audit_bank_identity)
        or batch.metadata.get("lock_identity")
        != expected_source_descriptor.get("lock_identity")
        or batch.metadata.get("audit_bank_opened_during_selection") is not False
    ):
        _fail(f"{cell_id}/{seed_label} source/audit authority differs")
    player_ids = tuple(str(value) for value in batch.player_ids)
    if len(player_ids) != len(set(player_ids)):
        _fail(f"{cell_id}/{seed_label} player IDs collide")
    draws = np.asarray(batch.row_draws)
    totals = np.asarray(batch.candidate_totals)
    if (
        draws.shape != (len(player_ids), WORLDS_PER_BLOCK)
        or totals.shape != (len(batch.candidates), WORLDS_PER_BLOCK)
        or not np.isfinite(draws).all()
        or not np.isfinite(totals).all()
    ):
        _fail(f"{cell_id}/{seed_label} world matrix differs")
    role_mode = batch.metadata.get("role_input_mode")
    if role_mode == "role-player-worlds":
        role_receipt = batch.metadata.get("role_player_world_receipt")
        normalized_role = role_player_world_receipt(player_ids, draws)
        # The role worlds are usually distinct from base worlds.  Their
        # complete receipt is supplied by the adapter, so validate shape/hash
        # syntax rather than replacing it with the base-world hash above.
        if (
            not isinstance(role_receipt, Mapping)
            or set(role_receipt) != set(normalized_role)
            or role_receipt.get("world_count") != WORLDS_PER_BLOCK
            or role_receipt.get("player_count") != len(player_ids)
            or role_receipt.get("shape") != normalized_role["shape"]
            or role_receipt.get("player_ids_sha256")
            != normalized_role["player_ids_sha256"]
            or _SHA256.fullmatch(str(role_receipt.get(
                "player_world_sha256", ""
            ))) is None
        ):
            _fail(f"{cell_id}/{seed_label} role world identity differs")
        normalized_role_receipt = dict(role_receipt)
    elif role_mode == "frozen-role12-candidate-identities":
        role_receipt = batch.metadata.get("frozen_role_input_receipt")
        if (
            not isinstance(role_receipt, Mapping)
            or set(role_receipt) != {
                "schema_version", "requested_count", "candidate_rows_sha256",
                "role_rosters_sha256", "world_artifact_sha256",
                "uses_target_slate_outcomes",
            }
            or role_receipt.get("schema_version")
            != "corpus-r6-frozen-role12-input/v1"
            or role_receipt.get("requested_count") != ROLE_SOLVES_PER_BLOCK
            or any(
                _SHA256.fullmatch(str(role_receipt.get(key, ""))) is None
                for key in (
                    "candidate_rows_sha256", "role_rosters_sha256",
                    "world_artifact_sha256",
                )
            )
            or role_receipt.get("uses_target_slate_outcomes") is not False
        ):
            _fail(f"{cell_id}/{seed_label} frozen role input differs")
        normalized_role_receipt = dict(role_receipt)
    else:
        _fail(f"{cell_id}/{seed_label} role input mode differs")
    ledger = _ledger_summary(
        batch.metadata.get("generation_exposure_ledger"),
        cell_id=cell_id,
        seed_label=seed_label,
        leverage=leverage,
        boom=boom,
        allocation=allocation,
    )
    timing_out: dict[str, float] = {}
    for key in (
        "leverage", "primary_boom", "all_generation_through_candidate_matrix",
    ):
        raw = timing.get(key)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            _fail(f"{cell_id}/{seed_label} timing receipt differs")
        number = float(raw)
        if not math.isfinite(number) or number < 0:
            _fail(f"{cell_id}/{seed_label} timing receipt differs")
        timing_out[key] = number
    rosters = [list(_roster(
        lineup, label=f"{cell_id}/{seed_label} candidate"
    )) for lineup in batch.candidates]
    scientific = {
        "seed_label": seed_label,
        "candidate_count": len(rosters),
        "candidate_order_sha256": canonical_sha256(rosters),
        "player_count": len(player_ids),
        "player_ids_sha256": canonical_sha256(list(player_ids)),
        "player_world_receipt": _array_receipt(draws, player_ids=player_ids),
        "candidate_matrix_receipt": _array_receipt(totals),
        "role_input_mode": role_mode,
        "role_input_receipt": normalized_role_receipt,
        "construction_preset_sha256": expected_preset["sha256"],
        "source_identity": dict(expected_source_identity),
        "source_document_internal_sha256": expected_source_descriptor[
            "source_document_internal_sha256"
        ],
        "source_descriptor_sha256": expected_source_descriptor[
            "descriptor_sha256"
        ],
        "lock_identity": dict(expected_source_descriptor["lock_identity"]),
        "audit_bank_identity": dict(expected_audit_bank_identity),
        "audit_bank_opened_during_selection": False,
        "generation_allocation": dict(allocation),
        "exposure_ledger_summary": ledger,
    }
    return scientific, timing_out


def panel_authority_receipt_v1(
    authority: CrossPanelAuthority,
    *,
    panel_id: str,
) -> dict[str, object]:
    """Bind the complete immutable G0 panel independently of task sharding.

    A one-slate worker is responsible for only one coordinate, but it must
    still carry the authority for the complete ordered 54-slate experiment.
    Keeping that check separate from observed task membership lets sharded
    execution preserve the same panel contract as the monolithic builder.
    """

    if not isinstance(authority, CrossPanelAuthority):
        _fail("exact immutable panel authority is required")
    expected = [str(value) for value in authority.expected_slate_ids]
    if (
        authority.panel_id != FOUNDRY_G0_PANEL_ID
        or expected != list(EXPECTED_SLATE_IDS)
        or _content_identity(
            authority.identity, label="G0 panel authority"
        ) != FOUNDRY_G0_PANEL_IDENTITY
    ):
        _fail("panel membership differs from exact G0 54-slate authority")
    return {
        "foundry_g0_panel_id": authority.panel_id,
        "selection_panel_id": panel_id,
        "expected_slate_ids": expected,
        "identity": dict(FOUNDRY_G0_PANEL_IDENTITY),
        "membership_matches": True,
    }


def _panel_authority(
    authority: CrossPanelAuthority,
    *, panel_id: str, observed_slate_ids: Sequence[str],
) -> dict[str, object]:
    receipt = panel_authority_receipt_v1(authority, panel_id=panel_id)
    if list(observed_slate_ids) != list(EXPECTED_SLATE_IDS):
        _fail("panel membership differs from exact G0 54-slate authority")
    return receipt


def build_score_blind_slate_v1(
    slate: CrossSlate,
    native_book_builder: NativeBookBuilder,
    *,
    code_sha: str,
    registry: Mapping[str, object] | None = None,
    environments: Mapping[str, Mapping[str, str]] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    """Build one outcome-blind slate row and its timing row.

    This is the compute-heavy, side-effect-free unit used both by the direct
    panel builder and by one-task-per-slate Cloud Run execution.  Scientific
    content and operational timing are returned separately so timing can
    never enter the scientific identity.
    """

    code = str(code_sha).strip().lower()
    if _CODE_SHA.fullmatch(code) is None:
        _fail("slate builder code SHA differs")
    if not isinstance(slate, CrossSlate):
        _fail("slate builder requires one CrossSlate")
    if not callable(native_book_builder):
        _fail("native-book builder is not callable")
    normalized_registry = validate_registry(
        registry_document(code_sha=code) if registry is None else registry
    )
    if normalized_registry.get("code_sha") != code:
        _fail("slate builder registry/code binding differs")
    if environments is None:
        normalized_environments = cell_environments({"CODE_SHA": code})
    else:
        if not isinstance(environments, Mapping):
            _fail("slate builder environments differ")
        normalized_environments = {
            str(cell_id): dict(environment)
            for cell_id, environment in environments.items()
            if isinstance(environment, Mapping)
        }
        validate_cell_environments(normalized_environments)
    environment_hashes = {
        str(row["cell_id"]): str(row["environment_sha256"])
        for row in normalized_registry["cells"]
    }
    if set(normalized_environments) != set(CELL_ORDER) or any(
        canonical_sha256(dict(sorted(normalized_environments[cell_id].items())))
        != environment_hashes.get(cell_id)
        for cell_id in CELL_ORDER
    ):
        _fail("slate builder environment/registry binding differs")

    source_identity = _content_identity(
        slate.source_identity, label=f"{slate.slate_id} source"
    )
    audit_bank_identity = _content_identity(
        slate.audit_bank_identity,
        label=f"{slate.slate_id} audit bank",
    )
    _source_document, source_descriptor = _source_document_descriptor_v1(
        slate.source_manifest,
        source_identity=source_identity,
        season=slate.season,
        week=slate.week,
        slate_id=slate.slate_id,
        audit_bank_identity=audit_bank_identity,
    )
    native_batches: dict[str, dict[str, CandidateBatch]] = {
        cell: {} for cell in CELL_ORDER
    }
    native_receipts: dict[str, list[dict[str, object]]] = {
        cell: [] for cell in CELL_ORDER
    }
    native_timings: dict[str, list[dict[str, object]]] = {
        cell: [] for cell in CELL_ORDER
    }
    for seed in normalized_registry["seed_pairs"]:
        seed_label = str(seed["seed_label"])
        for cell_id in CELL_ORDER:
            preset_receipt = _preset_receipt(str(
                CELL_DEFINITION[cell_id]["construction_preset_id"]
            ))
            batch = native_book_builder(
                slate,
                cell_id,
                seed_label,
                int(seed["projection_seed"]),
                int(seed["role_seed"]),
                dict(normalized_environments[cell_id]),
                dict(preset_receipt),
            )
            science, timing = _native_receipt(
                batch,
                cell_id=cell_id,
                seed_label=seed_label,
                expected_preset=preset_receipt,
                expected_source_identity=source_identity,
                expected_source_descriptor=source_descriptor,
                expected_audit_bank_identity=audit_bank_identity,
            )
            native_batches[cell_id][seed_label] = batch
            native_receipts[cell_id].append(science)
            native_timings[cell_id].append({
                "seed_label": seed_label,
                **timing,
            })
        reference = native_batches[CELL_ORDER[0]][seed_label]
        reference_role_mode = native_receipts[CELL_ORDER[0]][-1][
            "role_input_mode"
        ]
        reference_role = native_receipts[CELL_ORDER[0]][-1][
            "role_input_receipt"
        ]
        for cell_id in CELL_ORDER[1:]:
            batch = native_batches[cell_id][seed_label]
            if batch.player_ids != reference.player_ids or not np.array_equal(
                batch.row_draws, reference.row_draws
            ):
                _fail(
                    f"{slate.slate_id}/{seed_label} input/player worlds "
                    "differ across cells"
                )
            if (
                native_receipts[cell_id][-1]["role_input_mode"]
                != reference_role_mode
                or native_receipts[cell_id][-1]["role_input_receipt"]
                != reference_role
            ):
                _fail(
                    f"{slate.slate_id}/{seed_label} role worlds differ "
                    "across cells"
                )

    combined: dict[str, CandidateBatch] = {}
    cell_rows: dict[str, dict[str, object]] = {}
    candidate_rosters_by_cell: dict[str, list[list[str]]] = {}
    selected_rosters_by_cell: dict[str, list[list[str]]] = {}
    reference_catalog: list[dict[str, object]] | None = None
    for cell_id in CELL_ORDER:
        try:
            combined[cell_id] = combine_cbwu_books(
                native_batches[cell_id],
                SEED_LABELS,
                expected_worlds_per_book=WORLDS_PER_BLOCK,
            )
        except (TypeError, ValueError) as exc:
            raise ConstructionAllocationCrossError(
                f"{slate.slate_id}/{cell_id} CBWU combination failed: {exc}"
            ) from exc
        batch = combined[cell_id]
        candidate_matrix_receipt = _array_receipt(
            np.asarray(batch.candidate_totals)
        )
        picked = select_tail_entries(
            batch.candidate_totals,
            ENTRIES,
            TAIL_LINE,
            env=dict(normalized_environments[cell_id]),
        )
        if len(picked) != ENTRIES or len(set(picked)) != ENTRIES:
            _fail(f"{slate.slate_id}/{cell_id} selection is not exact K80")
        candidates = [list(_roster(
            lineup, label=f"{slate.slate_id}/{cell_id} candidate"
        )) for lineup in batch.candidates]
        selected = [candidates[index] for index in picked]
        if len({tuple(roster) for roster in selected}) != ENTRIES:
            _fail(f"{slate.slate_id}/{cell_id} selected rosters repeat")
        catalog = _player_catalog(batch)
        if reference_catalog is None:
            reference_catalog = catalog
        elif catalog != reference_catalog:
            _fail(f"{slate.slate_id} player catalog differs across cells")
        preset_id = str(CELL_DEFINITION[cell_id]["construction_preset_id"])
        incidence = _rule_incidence(selected, catalog, preset_id)
        if incidence["all_selected_satisfy_named_preset"] is not True:
            _fail(f"{slate.slate_id}/{cell_id} violates its named preset")
        selected_tags = []
        for ordinal in picked:
            lineup = batch.candidates[ordinal]
            tags = sorted(str(value) for value in batch.all_tags.get(
                lineup.ids, ()
            ))
            selected_tags.append(tags)
        candidate_rosters_by_cell[cell_id] = candidates
        selected_rosters_by_cell[cell_id] = selected
        cell_rows[cell_id] = {
            "cell_id": cell_id,
            "construction_preset_id": preset_id,
            "construction_preset_receipt": _preset_receipt(preset_id),
            "allocation_id": CELL_DEFINITION[cell_id]["allocation_id"],
            "native_books": native_receipts[cell_id],
            "combined_candidate_count": len(candidates),
            "combined_candidate_order_sha256": canonical_sha256(candidates),
            "combined_candidate_rosters": candidates,
            "combined_candidate_matrix_receipt": candidate_matrix_receipt,
            "selected_candidate_ordinals": [int(index) for index in picked],
            "selection_certificate": _coverage_selection_certificate(
                np.asarray(batch.candidate_totals),
                selected_ordinals=picked,
                candidate_matrix_receipt=candidate_matrix_receipt,
            ),
            "selected_rosters": selected,
            "selected_order_sha256": canonical_sha256(selected),
            "selected_generator_tags": selected_tags,
            "selected_generator_tag_counts": dict(sorted(Counter(
                tag for tags in selected_tags for tag in tags
            ).items())),
            "selected_book_overlap": _selected_overlap(selected),
            "selected_rule_incidence": incidence,
            "retrieval_law": {
                "selector": "incumbent-greedy-tail-coverage",
                "tail_line": TAIL_LINE,
                "entry_count": ENTRIES,
                "prefixes": list(PREFIXES),
            },
        }
    assert reference_catalog is not None
    reference_batch = combined[CELL_ORDER[0]]
    combined_world_receipt = _array_receipt(
        np.asarray(reference_batch.row_draws),
        player_ids=tuple(str(value) for value in reference_batch.player_ids),
    )
    for cell_id in CELL_ORDER[1:]:
        batch = combined[cell_id]
        if batch.player_ids != reference_batch.player_ids or not np.array_equal(
            batch.row_draws, reference_batch.row_draws
        ):
            _fail(f"{slate.slate_id} combined selection worlds differ")
    overlap_rows: dict[str, object] = {}
    for left_index, left in enumerate(CELL_ORDER):
        for right in CELL_ORDER[left_index + 1:]:
            key = f"{left}__vs__{right}"
            overlap_rows[key] = {
                "candidate": _set_overlap(
                    candidate_rosters_by_cell[left],
                    candidate_rosters_by_cell[right],
                ),
                "selected": _set_overlap(
                    selected_rosters_by_cell[left],
                    selected_rosters_by_cell[right],
                ),
            }
    scientific_slate = {
        "season": slate.season,
        "week": slate.week,
        "slate_id": slate.slate_id,
        "source_identity": source_identity,
        "source_descriptor": source_descriptor,
        "lock_identity": dict(source_descriptor["lock_identity"]),
        "audit_bank_identity": audit_bank_identity,
        "audit_bank_opened_during_selection": False,
        "player_catalog": reference_catalog,
        "player_catalog_sha256": canonical_sha256(reference_catalog),
        "combined_selection_world_receipt": combined_world_receipt,
        "same_source_input_all_cells": True,
        "same_lock_input_all_cells": True,
        "same_audit_bank_all_cells": True,
        "same_player_worlds_all_cells": True,
        "same_role_worlds_all_cells": True,
        "pairwise_population_overlap": overlap_rows,
        "cells": cell_rows,
    }
    timing_slate = {
        "slate_id": slate.slate_id,
        "cells": native_timings,
    }
    return scientific_slate, timing_slate


def assemble_score_blind_cross_v1(
    scientific_slates: Sequence[Mapping[str, object]],
    timing_slates: Sequence[Mapping[str, object]],
    *,
    panel_id: str,
    code_sha: str,
    image_digest: str,
    panel_authority: CrossPanelAuthority,
    registry: Mapping[str, object] | None = None,
    _expected_selection_slate_ids: Sequence[str] | None = None,
) -> dict[str, object]:
    """Assemble deterministic slate rows into the canonical panel receipt."""

    panel, code, image = _identity_fields(
        panel_id=panel_id, code_sha=code_sha, image_digest=image_digest,
    )
    expected_selection = tuple(
        EXPECTED_SLATE_IDS
        if _expected_selection_slate_ids is None
        else _expected_selection_slate_ids
    )
    if (
        not expected_selection
        or len(expected_selection) != len(set(expected_selection))
        or any(slate_id not in EXPECTED_SLATE_IDS for slate_id in expected_selection)
    ):
        _fail("assembled selection coordinates differ")
    scientific_rows = [dict(row) for row in scientific_slates]
    timing_rows = [dict(row) for row in timing_slates]
    if (
        [row.get("slate_id") for row in scientific_rows]
        != list(expected_selection)
        or [row.get("slate_id") for row in timing_rows]
        != list(expected_selection)
    ):
        _fail("assembled selection slate order differs")
    authority = panel_authority_receipt_v1(
        panel_authority, panel_id=panel,
    )
    normalized_registry = validate_registry(
        registry_document(code_sha=code) if registry is None else registry
    )
    if normalized_registry.get("code_sha") != code:
        _fail("assembled selection registry/code binding differs")

    scientific_body: dict[str, object] = {
        "schema_version": SELECTION_SCHEMA,
        "version": VERSION,
        "panel_id": panel,
        "panel_authority": authority,
        "code_sha": code,
        "image_digest": image,
        "registry": normalized_registry,
        "registry_sha256": normalized_registry["registry_sha256"],
        "cell_order": list(CELL_ORDER),
        "seed_labels": list(SEED_LABELS),
        "worlds_per_block": WORLDS_PER_BLOCK,
        "blocks_per_slate": len(SEED_LABELS),
        "requested_core_solves_per_block": CORE_SOLVES_PER_BLOCK,
        "requested_core_solves_per_cell_slate": (
            CORE_SOLVES_PER_BLOCK * len(SEED_LABELS)
        ),
        "role_solves_per_block": ROLE_SOLVES_PER_BLOCK,
        "tail_line": TAIL_LINE,
        "entry_count": ENTRIES,
        "prefixes": list(PREFIXES),
        "thresholds": list(THRESHOLDS),
        "slate_count": len(scientific_rows),
        "slates": scientific_rows,
        "selection_frozen_before_target_slate_outcome_join": True,
        "target_slate_outcomes_already_existed_before_replay": True,
        "target_slate_outcomes_read_during_selection": False,
        "uses_target_slate_outcomes": False,
        "post_lock_data_read": False,
        "all_four_cells_share_exact_input_and_world_identities": True,
        "all_four_cells_share_exact_lock_and_audit_bank_identities": True,
        "audit_bank_opened_during_selection": False,
        "source_manifests_content_bound": True,
        "k80_selection_independently_replayable": True,
        "construction_supplied_only_by_exact_named_receipt": True,
        "historical_evidence_status": "descriptive-diagnostic-only",
        "automatic_policy_promotion": False,
        "production_policy_authority": False,
        "existing_five_arm_suite_modified": False,
    }
    scientific_hash = canonical_sha256(scientific_body)
    receipt_body = {
        **scientific_body,
        "scientific_sha256": scientific_hash,
        "execution_observations": {
            "generation_timing_seconds": timing_rows,
        },
    }
    return {**receipt_body, "receipt_sha256": canonical_sha256(receipt_body)}


def build_score_blind_cross_v1(
    slates: Sequence[CrossSlate],
    native_book_builder: NativeBookBuilder,
    *,
    panel_id: str,
    code_sha: str,
    image_digest: str,
    panel_authority: CrossPanelAuthority,
) -> dict[str, object]:
    """Generate and freeze the exact four-cell K80 books without outcomes."""

    panel, code, image = _identity_fields(
        panel_id=panel_id, code_sha=code_sha, image_digest=image_digest,
    )
    if not callable(native_book_builder):
        _fail("native-book builder is not callable")
    supplied = tuple(slates)
    if not supplied or not all(isinstance(row, CrossSlate) for row in supplied):
        _fail("panel contains a non-CrossSlate row")
    ordered = sorted(supplied, key=lambda row: row.slate_id)
    slate_ids = [row.slate_id for row in ordered]
    if len(set(slate_ids)) != len(slate_ids):
        _fail("panel repeats a slate")
    _panel_authority(
        panel_authority, panel_id=panel, observed_slate_ids=slate_ids,
    )
    registry = validate_registry(registry_document(code_sha=code))
    environments = cell_environments({"CODE_SHA": code})
    scientific_slates: list[dict[str, object]] = []
    timing_slates: list[dict[str, object]] = []
    for slate in ordered:
        scientific_slate, timing_slate = build_score_blind_slate_v1(
            slate,
            native_book_builder,
            code_sha=code,
            registry=registry,
            environments=environments,
        )
        scientific_slates.append(scientific_slate)
        timing_slates.append(timing_slate)
    return assemble_score_blind_cross_v1(
        scientific_slates,
        timing_slates,
        panel_id=panel,
        code_sha=code,
        image_digest=image,
        panel_authority=panel_authority,
        registry=registry,
    )


def validate_score_blind_cross_v1(
    value: object,
    *,
    _expected_selection_slate_ids: Sequence[str] | None = None,
) -> dict[str, object]:
    """Reopen the complete score-blind receipt before publication/grading."""

    if not isinstance(value, Mapping):
        _fail("selection receipt is not a mapping")
    expected_selection = tuple(
        EXPECTED_SLATE_IDS
        if _expected_selection_slate_ids is None
        else _expected_selection_slate_ids
    )
    expected_order = {
        slate_id: ordinal
        for ordinal, slate_id in enumerate(EXPECTED_SLATE_IDS)
    }
    if (
        not expected_selection
        or len(expected_selection) != len(set(expected_selection))
        or any(slate_id not in expected_order for slate_id in expected_selection)
        or list(expected_selection) != sorted(
            expected_selection, key=expected_order.__getitem__
        )
    ):
        _fail("selection validation coordinates differ")
    item = dict(value)
    retained = item.pop("receipt_sha256", None)
    if (
        type(retained) is not str
        or _SHA256.fullmatch(retained) is None
        or canonical_sha256(item) != retained
    ):
        _fail("selection receipt self-hash differs")
    scientific_hash = item.get("scientific_sha256")
    observations = item.get("execution_observations")
    scientific = {
        key: nested for key, nested in item.items()
        if key not in {"scientific_sha256", "execution_observations"}
    }
    if (
        type(scientific_hash) is not str
        or _SHA256.fullmatch(scientific_hash) is None
        or canonical_sha256(scientific) != scientific_hash
        or not isinstance(observations, Mapping)
    ):
        _fail("selection scientific identity differs")
    if (
        scientific.get("schema_version") != SELECTION_SCHEMA
        or scientific.get("version") != VERSION
        or scientific.get("cell_order") != list(CELL_ORDER)
        or scientific.get("seed_labels") != list(SEED_LABELS)
        or scientific.get("worlds_per_block") != WORLDS_PER_BLOCK
        or scientific.get("blocks_per_slate") != len(SEED_LABELS)
        or scientific.get("requested_core_solves_per_block")
        != CORE_SOLVES_PER_BLOCK
        or scientific.get("requested_core_solves_per_cell_slate")
        != CORE_SOLVES_PER_BLOCK * len(SEED_LABELS)
        or scientific.get("role_solves_per_block") != ROLE_SOLVES_PER_BLOCK
        or scientific.get("tail_line") != TAIL_LINE
        or scientific.get("entry_count") != ENTRIES
        or scientific.get("prefixes") != list(PREFIXES)
        or scientific.get("thresholds") != list(THRESHOLDS)
        or scientific.get("uses_target_slate_outcomes") is not False
        or scientific.get("post_lock_data_read") is not False
        or scientific.get("selection_frozen_before_target_slate_outcome_join")
        is not True
        or scientific.get("target_slate_outcomes_already_existed_before_replay")
        is not True
        or scientific.get("target_slate_outcomes_read_during_selection")
        is not False
        or scientific.get("automatic_policy_promotion") is not False
        or scientific.get("existing_five_arm_suite_modified") is not False
        or scientific.get("target_slate_outcomes_already_existed_before_replay")
        is not True
        or scientific.get(
            "all_four_cells_share_exact_input_and_world_identities"
        ) is not True
        or scientific.get(
            "all_four_cells_share_exact_lock_and_audit_bank_identities"
        ) is not True
        or scientific.get("audit_bank_opened_during_selection") is not False
        or scientific.get("source_manifests_content_bound") is not True
        or scientific.get("k80_selection_independently_replayable") is not True
        or scientific.get(
            "construction_supplied_only_by_exact_named_receipt"
        ) is not True
        or scientific.get("historical_evidence_status")
        != "descriptive-diagnostic-only"
        or scientific.get("production_policy_authority") is not False
    ):
        _fail("selection fixed law differs")
    _identity_fields(
        panel_id=str(scientific.get("panel_id", "")),
        code_sha=str(scientific.get("code_sha", "")),
        image_digest=str(scientific.get("image_digest", "")),
    )
    registry = validate_registry(scientific.get("registry"))
    if scientific.get("registry_sha256") != registry["registry_sha256"]:
        _fail("selection registry binding differs")
    authority = scientific.get("panel_authority")
    if (
        not isinstance(authority, Mapping)
        or authority.get("foundry_g0_panel_id") != FOUNDRY_G0_PANEL_ID
        or authority.get("selection_panel_id") != scientific.get("panel_id")
        or authority.get("expected_slate_ids") != list(EXPECTED_SLATE_IDS)
        or authority.get("membership_matches") is not True
        or authority.get("identity") != FOUNDRY_G0_PANEL_IDENTITY
    ):
        _fail("selection panel authority differs")
    _content_identity(authority.get("identity"), label="selection panel authority")
    slates = scientific.get("slates")
    if (
        not isinstance(slates, list)
        or [row.get("slate_id") for row in slates if isinstance(row, Mapping)]
        != list(expected_selection)
        or scientific.get("slate_count") != len(expected_selection)
    ):
        _fail("selection does not contain the exact 54-slate panel")
    for slate in slates:
        if not isinstance(slate, Mapping):
            _fail("selection slate row differs")
        slate_id = str(slate.get("slate_id", ""))
        season = slate.get("season")
        week = slate.get("week")
        if (
            type(season) is not int
            or type(week) is not int
            or slate_id != f"{season}-w{week:02d}"
        ):
            _fail("selection slate identity differs")
        source_identity = _content_identity(
            slate.get("source_identity"), label="slate source"
        )
        audit_bank_identity = _content_identity(
            slate.get("audit_bank_identity"), label="slate audit bank"
        )
        source_descriptor = _validate_source_descriptor_v1(
            slate.get("source_descriptor"),
            source_identity=source_identity,
            season=season,
            week=week,
            slate_id=slate_id,
            audit_bank_identity=audit_bank_identity,
        )
        if (
            slate.get("lock_identity") != source_descriptor["lock_identity"]
            or slate.get("audit_bank_opened_during_selection") is not False
        ):
            _fail("selection slate source binding differs")
        catalog = slate.get("player_catalog")
        if (
            not isinstance(catalog, list)
            or canonical_sha256(catalog) != slate.get("player_catalog_sha256")
        ):
            _fail("selection player catalog differs")
        cells = slate.get("cells")
        if not isinstance(cells, Mapping) or set(cells) != set(CELL_ORDER):
            _fail("selection cell grid differs")
        candidates_by_cell: dict[str, list[list[str]]] = {}
        selected_by_cell: dict[str, list[list[str]]] = {}
        native_by_cell: dict[str, list[Mapping[str, object]]] = {}
        for cell_id in CELL_ORDER:
            cell = cells[cell_id]
            if not isinstance(cell, Mapping):
                _fail("selection cell row differs")
            definition = CELL_DEFINITION[cell_id]
            preset_id = str(definition["construction_preset_id"])
            candidates = cell.get("combined_candidate_rosters")
            selected = cell.get("selected_rosters")
            ordinals = cell.get("selected_candidate_ordinals")
            matrix_receipt = cell.get("combined_candidate_matrix_receipt")
            if (
                cell.get("cell_id") != cell_id
                or cell.get("construction_preset_id") != preset_id
                or cell.get("construction_preset_receipt")
                != _preset_receipt(preset_id)
                or cell.get("allocation_id") != definition["allocation_id"]
                or not isinstance(candidates, list)
                or cell.get("combined_candidate_count") != len(candidates)
                or canonical_sha256(candidates)
                != cell.get("combined_candidate_order_sha256")
                or not isinstance(selected, list)
                or len(selected) != ENTRIES
                or canonical_sha256(selected) != cell.get("selected_order_sha256")
                or not isinstance(ordinals, list)
                or len(ordinals) != ENTRIES
                or len(set(ordinals)) != ENTRIES
                or any(type(index) is not int or not 0 <= index < len(candidates)
                       for index in ordinals)
                or [candidates[index] for index in ordinals] != selected
            ):
                _fail("selection candidate/K80 membership differs")
            if any(
                not isinstance(roster, list)
                or len(roster) != 9
                or len(set(roster)) != 9
                or any(type(player_id) is not str or not player_id for player_id in roster)
                for roster in candidates
            ):
                _fail("selection candidate roster differs")
            catalog_by_id = {str(row["id"]): row for row in catalog}
            preset = resolve_construction_preset(preset_id)
            for roster in candidates:
                if not set(roster) <= set(catalog_by_id) or not _preset_satisfied(
                    _lineup_anatomy(roster, catalog_by_id), preset
                ):
                    _fail("selection candidate violates its named preset")
            _validate_array_receipt(
                matrix_receipt,
                label="combined candidate matrix",
                expected_shape=(
                    len(candidates), WORLDS_PER_BLOCK * len(SEED_LABELS)
                ),
            )
            _validate_coverage_selection_certificate(
                cell.get("selection_certificate"),
                candidate_count=len(candidates),
                candidate_matrix_receipt=matrix_receipt,
                selected_ordinals=ordinals,
            )
            expected_retrieval_law = {
                "selector": "incumbent-greedy-tail-coverage",
                "tail_line": TAIL_LINE,
                "entry_count": ENTRIES,
                "prefixes": list(PREFIXES),
            }
            tags = cell.get("selected_generator_tags")
            if (
                cell.get("retrieval_law") != expected_retrieval_law
                or not isinstance(tags, list)
                or len(tags) != ENTRIES
                or any(
                    not isinstance(row, list)
                    or row != sorted(row)
                    or any(type(tag) is not str or not tag for tag in row)
                    for row in tags
                )
                or cell.get("selected_generator_tag_counts")
                != dict(sorted(Counter(
                    tag for row in tags for tag in row
                ).items()))
            ):
                _fail("selection retrieval/tag trace differs")
            expected_incidence = _rule_incidence(selected, catalog, preset_id)
            if cell.get("selected_rule_incidence") != expected_incidence:
                _fail("selection rule-incidence trace differs")
            if cell.get("selected_book_overlap") != _selected_overlap(selected):
                _fail("selection within-book overlap trace differs")
            native = cell.get("native_books")
            if not isinstance(native, list) or len(native) != len(SEED_LABELS):
                _fail("selection native-book grid differs")
            for expected_label, row in zip(SEED_LABELS, native, strict=True):
                if not isinstance(row, Mapping):
                    _fail("selection native-book receipt differs")
                allocation = row.get("generation_allocation", {})
                exposure = row.get("exposure_ledger_summary", {})
                status = (
                    exposure.get("status_counts", {})
                    if isinstance(exposure, Mapping) else {}
                )
                definition = CELL_DEFINITION[cell_id]
                leverage = int(definition["leverage"])
                boom = int(definition["boom"])
                if (
                    row.get("seed_label") != expected_label
                    or row.get("construction_preset_sha256")
                    != _preset_receipt(preset_id)["sha256"]
                    or not isinstance(allocation, Mapping)
                    or allocation.get("leverage_requested") != leverage
                    or allocation.get("boom_requested") != boom
                    or allocation.get("boom_attempted") != boom
                    or allocation.get("role_or_epistemic_requested")
                    != ROLE_SOLVES_PER_BLOCK
                    or allocation.get("core_requested")
                    != CORE_SOLVES_PER_BLOCK
                    or allocation.get("boom_unique_fill") is not False
                    or any(
                        type(allocation.get(key)) is not int
                        or int(allocation[key]) < 0
                        for key in (
                            "leverage_successful", "boom_successful",
                            "leverage_unique", "boom_unique_added",
                            "boom_duplicates", "leverage_solver_errors",
                            "boom_solver_errors", "leverage_infeasible",
                            "boom_infeasible",
                        )
                    )
                    or not isinstance(exposure, Mapping)
                    or exposure.get("expected_requests_by_family")
                    != {"boom": boom, "leverage": leverage}
                    or type(exposure.get("attempt_count")) is not int
                    or type(exposure.get("retry_attempt_count")) is not int
                    or exposure.get("retry_attempt_count")
                    != exposure.get("attempt_count") - CORE_SOLVES_PER_BLOCK
                    or not isinstance(status, Mapping)
                    or set(status)
                    != {"dup", "error", "exhausted", "infeasible", "new"}
                    or any(type(value) is not int or value < 0 for value in (
                        status.values()
                    ))
                    or sum(status.values()) != exposure.get("attempt_count")
                    or status.get("new", 0) + status.get("dup", 0)
                    != allocation.get("leverage_successful", -1)
                    + allocation.get("boom_successful", -1)
                    or status.get("new", 0)
                    != allocation.get("leverage_unique", -1)
                    + allocation.get("boom_unique_added", -1)
                    or status.get("dup", 0)
                    != allocation.get("boom_duplicates", -1)
                    or exposure.get("failure_or_exhaustion_count")
                    != status.get("error", 0)
                    + status.get("infeasible", 0)
                    + status.get("exhausted", 0)
                    or _SHA256.fullmatch(str(exposure.get("ledger_sha256", "")))
                    is None
                    or _SHA256.fullmatch(str(exposure.get(
                        "row_manifest_sha256", ""
                    ))) is None
                    or row.get("source_identity") != source_identity
                    or row.get("source_document_internal_sha256")
                    != source_descriptor["source_document_internal_sha256"]
                    or row.get("source_descriptor_sha256")
                    != source_descriptor["descriptor_sha256"]
                    or row.get("lock_identity")
                    != source_descriptor["lock_identity"]
                    or row.get("audit_bank_identity") != audit_bank_identity
                    or row.get("audit_bank_opened_during_selection") is not False
                ):
                    _fail("selection native-book receipt differs")
                player_count = row.get("player_count")
                candidate_count = row.get("candidate_count")
                if (
                    type(player_count) is not int
                    or player_count <= 0
                    or type(candidate_count) is not int
                    or candidate_count <= 0
                ):
                    _fail("selection native-book dimensions differ")
                _validate_array_receipt(
                    row.get("player_world_receipt"),
                    label="native player worlds",
                    expected_shape=(player_count, WORLDS_PER_BLOCK),
                )
                _validate_array_receipt(
                    row.get("candidate_matrix_receipt"),
                    label="native candidate matrix",
                    expected_shape=(candidate_count, WORLDS_PER_BLOCK),
                )
            native_by_cell[cell_id] = native
            candidates_by_cell[cell_id] = candidates
            selected_by_cell[cell_id] = selected
        for seed_index, seed_label in enumerate(SEED_LABELS):
            reference_native = native_by_cell[CELL_ORDER[0]][seed_index]
            for cell_id in CELL_ORDER[1:]:
                candidate_native = native_by_cell[cell_id][seed_index]
                if (
                    candidate_native.get("seed_label") != seed_label
                    or candidate_native.get("player_count")
                    != reference_native.get("player_count")
                    or candidate_native.get("player_ids_sha256")
                    != reference_native.get("player_ids_sha256")
                    or candidate_native.get("player_world_receipt")
                    != reference_native.get("player_world_receipt")
                    or candidate_native.get("role_input_mode")
                    != reference_native.get("role_input_mode")
                    or candidate_native.get("role_input_receipt")
                    != reference_native.get("role_input_receipt")
                ):
                    _fail("selection native equal-input/world trace differs")
        reference_player_count = len(catalog)
        _validate_array_receipt(
            slate.get("combined_selection_world_receipt"),
            label="combined selection worlds",
            expected_shape=(
                reference_player_count,
                WORLDS_PER_BLOCK * len(SEED_LABELS),
            ),
        )
        expected_overlap: dict[str, object] = {}
        for left_index, left in enumerate(CELL_ORDER):
            for right in CELL_ORDER[left_index + 1:]:
                expected_overlap[f"{left}__vs__{right}"] = {
                    "candidate": _set_overlap(
                        candidates_by_cell[left], candidates_by_cell[right]
                    ),
                    "selected": _set_overlap(
                        selected_by_cell[left], selected_by_cell[right]
                    ),
                }
        if slate.get("pairwise_population_overlap") != expected_overlap:
            _fail("selection pairwise population overlap differs")
        if any(slate.get(key) is not True for key in (
            "same_source_input_all_cells",
            "same_lock_input_all_cells",
            "same_audit_bank_all_cells",
            "same_player_worlds_all_cells",
            "same_role_worlds_all_cells",
        )):
            _fail("selection equal-input/world trace differs")
    timings = observations.get("generation_timing_seconds")
    if (
        set(observations) != {"generation_timing_seconds"}
        or not isinstance(timings, list)
        or [row.get("slate_id") for row in timings if isinstance(row, Mapping)]
        != list(expected_selection)
    ):
        _fail("selection execution observations differ")
    for row in timings:
        if not isinstance(row, Mapping) or set(row) != {"slate_id", "cells"}:
            _fail("selection timing slate differs")
        cells = row.get("cells")
        if not isinstance(cells, Mapping) or set(cells) != set(CELL_ORDER):
            _fail("selection timing cell grid differs")
        for cell_id in CELL_ORDER:
            values = cells[cell_id]
            if (
                not isinstance(values, list)
                or len(values) != len(SEED_LABELS)
                or [value.get("seed_label") for value in values if isinstance(value, Mapping)]
                != list(SEED_LABELS)
            ):
                _fail("selection timing seed grid differs")
            for timing in values:
                if not isinstance(timing, Mapping) or set(timing) != {
                    "seed_label", "leverage", "primary_boom",
                    "all_generation_through_candidate_matrix",
                }:
                    _fail("selection timing receipt differs")
                for key in (
                    "leverage", "primary_boom",
                    "all_generation_through_candidate_matrix",
                ):
                    value = timing[key]
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(float(value))
                        or float(value) < 0
                    ):
                        _fail("selection timing value differs")
    return {**item, "receipt_sha256": retained}


__all__ = [
    "ALLOCATION_BOOM_FIRST",
    "ALLOCATION_INCUMBENT",
    "ALLOCATION_ORDER",
    "CELL_DEFINITION",
    "CELL_ORDER",
    "CORE_SOLVES_PER_BLOCK",
    "ConstructionAllocationCrossError",
    "CrossPanelAuthority",
    "CrossSlate",
    "ENTRIES",
    "EXPECTED_SLATE_IDS",
    "FOUNDRY_G0_PANEL_ID",
    "FOUNDRY_G0_PANEL_IDENTITY",
    "PANEL_SEASONS",
    "NativeBookBuilder",
    "PREFIXES",
    "PRESET_ORDER",
    "REGISTRY_SCHEMA",
    "ROLE_SOLVES_PER_BLOCK",
    "SEED_LABELS",
    "SELECTION_SCHEMA",
    "SELECTION_CERTIFICATE_SCHEMA",
    "SOURCE_MANIFEST_SCHEMA",
    "SOURCE_DESCRIPTOR_SCHEMA",
    "TAIL_LINE",
    "THRESHOLDS",
    "VERSION",
    "WORLDS_PER_BLOCK",
    "assemble_score_blind_cross_v1",
    "build_score_blind_cross_v1",
    "build_score_blind_slate_v1",
    "canonical_json_bytes",
    "canonical_sha256",
    "cell_environments",
    "panel_authority_receipt_v1",
    "registry_document",
    "source_manifest_v1",
    "validate_cell_environments",
    "validate_registry",
    "validate_score_blind_cross_v1",
    "validate_source_manifest_v1",
]
