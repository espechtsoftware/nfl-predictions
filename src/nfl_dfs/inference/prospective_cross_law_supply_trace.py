"""Outcome-free attribution for cross-law candidate supply and selection.

``boom:xlaw`` is a producer-provenance tag.  A discovery solve may attach
that tag to a roster that was already present in the native base pool, so the
tag alone is not evidence that cross-law supplied a candidate.  This module
uses the canonical solve ledger's ``new``/``dup`` distinction and the CBWU
source-block tag to freeze the actual supply contribution at the candidate
pool and selected K20/K40/K80 prefixes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Final

from ..backtest.engine import CandidateBatch
from ..optimizer.lineup import Lineup
from .generation_exposure import canonical_sha256, validate_ledger


TRACE_SCHEMA: Final = "prospective-cross-law-selected-supply-trace/v1"
FAMILY: Final = "boom:xlaw"
PREFIXES: Final = (20, 40, 80)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
DEFINITION: Final = {
    "genuinely_new_discovery_candidate": (
        "exact roster has status=new in the canonical boom:xlaw ledger "
        "for its assigned candidate_seed:R0-R4 block"
    ),
    "duplicate_attempt_provenance_only_candidate": (
        "existing roster has boom:xlaw producer provenance from a "
        "status=dup attempt but no status=new row in its assigned block"
    ),
    "producer_tag_is_not_supply_evidence": True,
    "selection_scoring_bank": "untouched-base-player-world-bank",
}


class ProspectiveCrossLawSupplyTraceError(ValueError):
    """Cross-law supply attribution differed from the frozen contract."""


def _fail(message: str) -> None:
    raise ProspectiveCrossLawSupplyTraceError(message)


def _roster_sha256(lineup: Lineup) -> str:
    roster = sorted(str(value) for value in lineup.ids)
    if (
        len(roster) != 9
        or len(set(roster)) != 9
        or any(not value for value in roster)
    ):
        _fail("cross-law supply trace roster identity differs")
    return canonical_sha256(roster)


def _dk_lineup_id(
    lineup: Lineup,
    dk_id_by_player_id: Mapping[object, str | int],
) -> str:
    try:
        roster = sorted(str(dk_id_by_player_id[value]) for value in lineup.ids)
    except KeyError as exc:
        raise ProspectiveCrossLawSupplyTraceError(
            "cross-law supply trace lacks a DK player identity"
        ) from exc
    if (
        len(roster) != 9
        or len(set(roster)) != 9
        or any(not value for value in roster)
    ):
        _fail("cross-law supply trace DK roster identity differs")
    return f"lineup-v1-{canonical_sha256(roster)}"


def _source_block(
    lineup: Lineup,
    batch: CandidateBatch,
    *,
    candidate_ordinal: int,
    block_labels: Sequence[str],
) -> tuple[str, tuple[str, ...]]:
    raw_sources = batch.metadata.get("candidate_source_blocks")
    if (
        not isinstance(raw_sources, Sequence)
        or isinstance(raw_sources, (str, bytes))
        or len(raw_sources) != len(batch.candidates)
    ):
        _fail("cross-law supply lacks its roster-aligned source-block authority")
    source = str(raw_sources[candidate_ordinal])
    if source not in block_labels:
        _fail("cross-law supply candidate source block differs")
    tags = tuple(str(value) for value in batch.all_tags.get(lineup.ids, ()))
    sources = [
        label
        for label in block_labels
        if f"candidate_seed:{label}" in tags
    ]
    if sources != [source]:
        _fail("cross-law supply candidate lacks one exact CBWU source block")
    return source, tags


def _block_status_authority(
    transform_receipts_by_block: Mapping[str, Mapping[str, object]],
    *,
    block_labels: Sequence[str],
) -> tuple[
    dict[str, dict[str, object]],
    dict[str, set[str]],
    dict[str, set[str]],
]:
    if set(transform_receipts_by_block) != set(block_labels):
        _fail("cross-law supply transform-receipt block grid differs")
    block_receipts: dict[str, dict[str, object]] = {}
    new_by_block: dict[str, set[str]] = {}
    duplicate_by_block: dict[str, set[str]] = {}
    for block in block_labels:
        container = transform_receipts_by_block[block]
        if not isinstance(container, Mapping) or set(container) != {
            "cross_law_discovery"
        }:
            _fail(f"cross-law supply {block} transform registry differs")
        receipt = container["cross_law_discovery"]
        if not isinstance(receipt, Mapping):
            _fail(f"cross-law supply {block} transform receipt differs")
        try:
            ledger = validate_ledger(receipt.get("exposure_ledger"))
        except Exception as exc:
            raise ProspectiveCrossLawSupplyTraceError(
                f"cross-law supply {block} exposure ledger differs"
            ) from exc
        if ledger["expected_requests_by_family"] != {FAMILY: 60}:
            _fail(f"cross-law supply {block} requested-solve census differs")
        rows = ledger["rows"]
        new_rows = [row for row in rows if row["status"] == "new"]
        duplicate_rows = [row for row in rows if row["status"] == "dup"]
        new_hashes = {str(row["roster_sha256"]) for row in new_rows}
        duplicate_hashes = {
            str(row["roster_sha256"]) for row in duplicate_rows
        }
        if len(new_hashes) != len(new_rows):
            _fail(f"cross-law supply {block} repeats a new roster")
        duplicate_only_rows = [
            row for row in duplicate_rows
            if str(row["roster_sha256"]) not in new_hashes
        ]
        duplicate_of_new_rows = [
            row for row in duplicate_rows
            if str(row["roster_sha256"]) in new_hashes
        ]
        block_receipts[block] = {
            "exposure_ledger_sha256": ledger["ledger_sha256"],
            "attempt_count": ledger["attempt_count"],
            "newly_supplied_attempt_count": len(new_rows),
            "duplicate_attempt_count": len(duplicate_rows),
            "duplicate_provenance_only_attempt_count": len(
                duplicate_only_rows
            ),
            "duplicate_of_newly_supplied_attempt_count": len(
                duplicate_of_new_rows
            ),
            "unsuccessful_attempt_count": sum(
                int(ledger["status_counts"].get(status, 0))
                for status in ("error", "infeasible", "exhausted")
            ),
            "newly_supplied_roster_sha256s": [
                row["roster_sha256"] for row in new_rows
            ],
            "duplicate_attempt_roster_sha256s": [
                row["roster_sha256"] for row in duplicate_rows
            ],
            "duplicate_provenance_only_roster_sha256s": sorted({
                str(row["roster_sha256"]) for row in duplicate_only_rows
            }),
        }
        block_receipts[block]["receipt_sha256"] = canonical_sha256(
            block_receipts[block]
        )
        new_by_block[block] = new_hashes
        duplicate_by_block[block] = duplicate_hashes
    return block_receipts, new_by_block, duplicate_by_block


def _selection_projection(
    lineups: Sequence[Lineup],
    classification_by_roster: Mapping[frozenset[object], Mapping[str, object]],
) -> dict[str, object]:
    newly_supplied: list[str] = []
    duplicate_only: list[str] = []
    provenance: list[str] = []
    for lineup in lineups:
        classification = classification_by_roster.get(lineup.ids)
        if classification is None:
            _fail("cross-law selected lineup escapes the frozen candidate pool")
        lineup_id = str(classification["dk_lineup_id"])
        kind = classification["classification"]
        if kind == "newly-supplied-discovery":
            newly_supplied.append(lineup_id)
            provenance.append(lineup_id)
        elif kind == "duplicate-attempt-provenance-only":
            duplicate_only.append(lineup_id)
            provenance.append(lineup_id)
        elif kind != "no-cross-law-provenance":
            _fail("cross-law supply classification differs")
    projection: dict[str, object] = {
        "selected_count": len(lineups),
        "genuinely_new_discovery_candidate_count": len(newly_supplied),
        "duplicate_attempt_provenance_only_candidate_count": len(
            duplicate_only
        ),
        "any_cross_law_provenance_candidate_count": len(provenance),
        "genuinely_new_discovery_lineup_ids": newly_supplied,
        "duplicate_attempt_provenance_only_lineup_ids": duplicate_only,
        "any_cross_law_provenance_lineup_ids": provenance,
    }
    projection["projection_sha256"] = canonical_sha256(projection)
    return projection


def _selection_projection_from_ids(
    lineup_ids: Sequence[str],
    classification_by_lineup_id: Mapping[str, str],
) -> dict[str, object]:
    newly_supplied: list[str] = []
    duplicate_only: list[str] = []
    provenance: list[str] = []
    for raw_lineup_id in lineup_ids:
        lineup_id = str(raw_lineup_id)
        classification = classification_by_lineup_id.get(lineup_id)
        if classification == "newly-supplied-discovery":
            newly_supplied.append(lineup_id)
            provenance.append(lineup_id)
        elif classification == "duplicate-attempt-provenance-only":
            duplicate_only.append(lineup_id)
            provenance.append(lineup_id)
        elif classification != "no-cross-law-provenance":
            _fail("cross-law supply classification differs")
    projection: dict[str, object] = {
        "selected_count": len(lineup_ids),
        "genuinely_new_discovery_candidate_count": len(newly_supplied),
        "duplicate_attempt_provenance_only_candidate_count": len(
            duplicate_only
        ),
        "any_cross_law_provenance_candidate_count": len(provenance),
        "genuinely_new_discovery_lineup_ids": newly_supplied,
        "duplicate_attempt_provenance_only_lineup_ids": duplicate_only,
        "any_cross_law_provenance_lineup_ids": provenance,
    }
    projection["projection_sha256"] = canonical_sha256(projection)
    return projection


def _validate_projection(
    value: object,
    ordered_lineup_ids: Sequence[str],
    *,
    label: str,
    newly_supplied_ids: set[str] | None = None,
    duplicate_only_ids: set[str] | None = None,
) -> tuple[dict[str, object], set[str], set[str]]:
    fields = {
        "selected_count",
        "genuinely_new_discovery_candidate_count",
        "duplicate_attempt_provenance_only_candidate_count",
        "any_cross_law_provenance_candidate_count",
        "genuinely_new_discovery_lineup_ids",
        "duplicate_attempt_provenance_only_lineup_ids",
        "any_cross_law_provenance_lineup_ids",
        "projection_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail(f"cross-law supply {label} projection fields differ")
    item = dict(value)
    retained_hash = item.pop("projection_sha256")
    if retained_hash != canonical_sha256(item):
        _fail(f"cross-law supply {label} projection hash differs")
    new_ids = [str(value) for value in item[
        "genuinely_new_discovery_lineup_ids"
    ]]
    duplicate_ids = [str(value) for value in item[
        "duplicate_attempt_provenance_only_lineup_ids"
    ]]
    provenance_ids = [str(value) for value in item[
        "any_cross_law_provenance_lineup_ids"
    ]]
    new_set = set(new_ids)
    duplicate_set = set(duplicate_ids)
    ordered = [str(value) for value in ordered_lineup_ids]
    if (
        len(new_set) != len(new_ids)
        or len(duplicate_set) != len(duplicate_ids)
        or new_set & duplicate_set
        or new_set | duplicate_set != set(provenance_ids)
        or new_ids != [value for value in ordered if value in new_set]
        or duplicate_ids != [value for value in ordered if value in duplicate_set]
        or provenance_ids != [
            value for value in ordered if value in new_set | duplicate_set
        ]
        or item["selected_count"] != len(ordered)
        or item["genuinely_new_discovery_candidate_count"] != len(new_ids)
        or item["duplicate_attempt_provenance_only_candidate_count"]
        != len(duplicate_ids)
        or item["any_cross_law_provenance_candidate_count"]
        != len(provenance_ids)
    ):
        _fail(f"cross-law supply {label} projection differs")
    if newly_supplied_ids is not None and new_set != (
        set(ordered) & newly_supplied_ids
    ):
        _fail(f"cross-law supply {label} new-supply membership differs")
    if duplicate_only_ids is not None and duplicate_set != (
        set(ordered) & duplicate_only_ids
    ):
        _fail(f"cross-law supply {label} duplicate membership differs")
    return {**item, "projection_sha256": retained_hash}, new_set, duplicate_set


def validate_selected_supply_trace(
    value: object,
    *,
    candidate_lineup_ids: Sequence[str],
    candidate_internal_roster_sha256s: Sequence[str],
    selected_lineup_ids: Sequence[str],
    candidate_source_blocks: Sequence[str],
    transform_receipts_by_block: Mapping[str, Mapping[str, object]],
    block_labels: Sequence[str] = ("R0", "R1", "R2", "R3", "R4"),
) -> dict[str, object]:
    """Exact-reopen one frozen trace against pools, books, and ledgers."""

    fields = {
        "schema_version",
        "definition",
        "block_order",
        "prefixes",
        "per_block_attempt_authority",
        "candidate_pool",
        "selected_prefixes",
        "classification_rows_sha256",
        "uses_realized_outcomes",
        "post_lock_data_read",
        "complete",
        "trace_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("cross-law selected-supply trace fields differ")
    item = dict(value)
    retained_hash = item.pop("trace_sha256")
    if retained_hash != canonical_sha256(item):
        _fail("cross-law selected-supply trace hash differs")
    labels = tuple(str(value) for value in block_labels)
    candidates = [str(value) for value in candidate_lineup_ids]
    internal_roster_sha256s = [
        str(value) for value in candidate_internal_roster_sha256s
    ]
    selected = [str(value) for value in selected_lineup_ids]
    sources = [str(value) for value in candidate_source_blocks]
    if (
        item["schema_version"] != TRACE_SCHEMA
        or item["definition"] != DEFINITION
        or item["block_order"] != list(labels)
        or item["prefixes"] != list(PREFIXES)
        or item["uses_realized_outcomes"] is not False
        or item["post_lock_data_read"] is not False
        or item["complete"] is not True
        or len(candidates) < PREFIXES[-1]
        or len(set(candidates)) != len(candidates)
        or len(selected) != PREFIXES[-1]
        or not set(selected) <= set(candidates)
        or len(sources) != len(candidates)
        or len(internal_roster_sha256s) != len(candidates)
        or len(set(internal_roster_sha256s)) != len(
            internal_roster_sha256s
        )
        or any(
            _SHA256.fullmatch(value) is None
            for value in internal_roster_sha256s
        )
        or any(source not in labels for source in sources)
    ):
        _fail("cross-law selected-supply trace fixed law differs")
    expected_blocks, new_by_block, duplicate_by_block = (
        _block_status_authority(
            transform_receipts_by_block, block_labels=labels
        )
    )
    if item["per_block_attempt_authority"] != expected_blocks:
        _fail("cross-law selected-supply attempt authority differs")

    classification_rows: list[dict[str, object]] = []
    classification_by_lineup_id: dict[str, str] = {}
    for ordinal, (lineup_id, roster_sha256, source) in enumerate(zip(
        candidates, internal_roster_sha256s, sources, strict=True,
    )):
        if roster_sha256 in new_by_block[source]:
            classification = "newly-supplied-discovery"
        elif roster_sha256 in duplicate_by_block[source]:
            classification = "duplicate-attempt-provenance-only"
        else:
            classification = "no-cross-law-provenance"
        classification_rows.append({
            "candidate_ordinal": ordinal,
            "source_block": source,
            "internal_roster_sha256": roster_sha256,
            "dk_lineup_id": lineup_id,
            "classification": classification,
        })
        classification_by_lineup_id[lineup_id] = classification
    if item["classification_rows_sha256"] != canonical_sha256(
        classification_rows
    ):
        _fail("cross-law selected-supply classification rows differ")

    candidate_projection, new_ids, duplicate_ids = _validate_projection(
        item["candidate_pool"], candidates, label="candidate-pool"
    )
    expected_candidate_projection = _selection_projection_from_ids(
        candidates, classification_by_lineup_id
    )
    if candidate_projection != expected_candidate_projection:
        _fail("cross-law selected-supply candidate membership differs")
    selected_prefixes = item["selected_prefixes"]
    if not isinstance(selected_prefixes, Mapping) or set(
        selected_prefixes
    ) != {str(value) for value in PREFIXES}:
        _fail("cross-law selected-supply prefix grid differs")
    for prefix in PREFIXES:
        projection, _, _ = _validate_projection(
            selected_prefixes[str(prefix)],
            selected[:prefix],
            label=f"K{prefix}",
            newly_supplied_ids=new_ids,
            duplicate_only_ids=duplicate_ids,
        )
        expected_projection = _selection_projection_from_ids(
            selected[:prefix], classification_by_lineup_id
        )
        if projection != expected_projection:
            _fail(f"cross-law selected-supply K{prefix} membership differs")
    return {
        **item,
        "candidate_pool": candidate_projection,
        "trace_sha256": retained_hash,
    }


def build_selected_supply_trace(
    batch: CandidateBatch,
    selected: Sequence[Lineup],
    dk_id_by_player_id: Mapping[object, str | int],
    transform_receipts_by_block: Mapping[str, Mapping[str, object]],
    *,
    block_labels: Sequence[str] = ("R0", "R1", "R2", "R3", "R4"),
    prefixes: Sequence[int] = PREFIXES,
) -> dict[str, object]:
    """Freeze genuine cross-law supply separately from attempt provenance.

    A roster is genuine supply only when its assigned CBWU source block has a
    canonical ``status=new`` discovery row for that exact roster.  A selected
    base roster that merely acquired ``boom:xlaw`` through a ``status=dup``
    attempt is reported separately and never counted as new supply.
    """

    labels = tuple(str(value) for value in block_labels)
    retained_prefixes = tuple(int(value) for value in prefixes)
    if (
        labels != ("R0", "R1", "R2", "R3", "R4")
        or retained_prefixes != PREFIXES
        or len(selected) != PREFIXES[-1]
    ):
        _fail("cross-law supply trace frozen blocks or prefixes differ")
    if len(batch.candidates) < PREFIXES[-1]:
        _fail("cross-law supply candidate pool is below exact K80")
    block_receipts, new_by_block, duplicate_by_block = (
        _block_status_authority(
            transform_receipts_by_block, block_labels=labels
        )
    )

    classification_by_roster: dict[
        frozenset[object], dict[str, object]
    ] = {}
    classification_rows: list[dict[str, object]] = []
    for ordinal, lineup in enumerate(batch.candidates):
        source, tags = _source_block(
            lineup,
            batch,
            candidate_ordinal=ordinal,
            block_labels=labels,
        )
        roster_hash = _roster_sha256(lineup)
        has_provenance = FAMILY in tags
        newly_supplied = roster_hash in new_by_block[source]
        duplicate_attempted = roster_hash in duplicate_by_block[source]
        if newly_supplied and not has_provenance:
            _fail("new cross-law supply lacks its producer provenance")
        if has_provenance and not (newly_supplied or duplicate_attempted):
            _fail("cross-law producer provenance lacks a solve-ledger row")
        if newly_supplied:
            classification = "newly-supplied-discovery"
        elif has_provenance:
            classification = "duplicate-attempt-provenance-only"
        else:
            classification = "no-cross-law-provenance"
        row = {
            "candidate_ordinal": ordinal,
            "source_block": source,
            "internal_roster_sha256": roster_hash,
            "dk_lineup_id": _dk_lineup_id(lineup, dk_id_by_player_id),
            "classification": classification,
        }
        classification_rows.append(row)
        classification_by_roster[lineup.ids] = row
    if len(classification_by_roster) != len(batch.candidates):
        _fail("cross-law supply candidate pool repeats a roster")

    candidate_pool = _selection_projection(
        batch.candidates, classification_by_roster
    )
    selected_prefixes = {
        str(prefix): _selection_projection(
            selected[:prefix], classification_by_roster
        )
        for prefix in PREFIXES
    }
    body: dict[str, object] = {
        "schema_version": TRACE_SCHEMA,
        "definition": dict(DEFINITION),
        "block_order": list(labels),
        "prefixes": list(PREFIXES),
        "per_block_attempt_authority": block_receipts,
        "candidate_pool": candidate_pool,
        "selected_prefixes": selected_prefixes,
        "classification_rows_sha256": canonical_sha256(classification_rows),
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
        "complete": True,
    }
    body["trace_sha256"] = canonical_sha256(body)
    return body


__all__ = [
    "FAMILY",
    "DEFINITION",
    "PREFIXES",
    "TRACE_SCHEMA",
    "ProspectiveCrossLawSupplyTraceError",
    "build_selected_supply_trace",
    "validate_selected_supply_trace",
]
