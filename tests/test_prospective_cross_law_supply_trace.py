from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.inference.generation_exposure import SolveExposureLedger
from nfl_dfs.inference import prospective_cross_law_supply_trace as supply
from nfl_dfs.optimizer.lineup import Lineup


def _lineups() -> tuple[list[dict[str, object]], tuple[Lineup, ...]]:
    players: list[dict[str, object]] = [{
        "id": f"p{index:03d}",
        "name": f"P{index}",
        "pos": "WR",
        "team": f"T{index % 8}",
        "opp": f"T{(index + 1) % 8}",
        "game_id": f"G{index % 4}",
        "salary": 5_000,
    } for index in range(88)]
    return players, tuple(
        Lineup([*players[:8], players[8 + index]], tag="lev")
        for index in range(80)
    )


def _empty_discovery_ledger(label: str) -> dict[str, object]:
    builder = SolveExposureLedger(source_label=f"{label}-xlaw")
    for ordinal in range(60):
        builder.record(
            family=supply.FAMILY,
            requested_ordinal=ordinal,
            status="exhausted",
        )
    return builder.finalize(
        expected_requests_by_family={supply.FAMILY: 60}
    )


def _fixture() -> tuple[
    CandidateBatch,
    tuple[Lineup, ...],
    dict[str, str],
    dict[str, dict[str, object]],
]:
    players, lineups = _lineups()
    blocks = ("R0", "R1", "R2", "R3", "R4")
    all_tags = {
        lineup.ids: ("lev", f"candidate_seed:{blocks[index // 16]}")
        for index, lineup in enumerate(lineups)
    }
    batch = CandidateBatch(
        candidates=lineups,
        candidate_totals=np.zeros((80, 50_000), dtype=np.float32),
        player_ids=tuple(player["id"] for player in players),
        player_rows=tuple(players),
        row_draws=np.zeros((88, 50_000), dtype=np.float32),
        all_tags=all_tags,
        metadata={
            "portfolio": "CBWU",
            "candidate_source_blocks": [
                blocks[index // 16] for index in range(80)
            ],
        },
    )
    transforms = {
        block: {
            "cross_law_discovery": {
                "exposure_ledger": _empty_discovery_ledger(block)
            }
        }
        for block in blocks
    }
    mapping = {
        player["id"]: f"dk-{index:03d}"
        for index, player in enumerate(players)
    }
    return batch, lineups, mapping, transforms


def _r0_new_and_duplicate_ledger(
    lineups: tuple[Lineup, ...],
) -> dict[str, object]:
    builder = SolveExposureLedger(
        source_label="r0-xlaw",
        existing_rosters=(lineups[0].ids,),
    )
    builder.record(
        family=supply.FAMILY,
        requested_ordinal=0,
        status="dup",
        roster_ids=lineups[0].ids,
    )
    builder.record(
        family=supply.FAMILY,
        requested_ordinal=1,
        status="new",
        roster_ids=lineups[1].ids,
    )
    # A later repeat of genuinely new supply remains a duplicate attempt,
    # but it must not relabel the supplied roster as provenance-only.
    builder.record(
        family=supply.FAMILY,
        requested_ordinal=2,
        status="dup",
        roster_ids=lineups[1].ids,
    )
    for ordinal in range(3, 60):
        builder.record(
            family=supply.FAMILY,
            requested_ordinal=ordinal,
            status="exhausted",
        )
    return builder.finalize(
        expected_requests_by_family={supply.FAMILY: 60}
    )


def test_selected_trace_does_not_count_duplicate_provenance_as_new_supply(
) -> None:
    batch, lineups, mapping, transforms = _fixture()
    transforms["R0"] = {
        "cross_law_discovery": {
            "exposure_ledger": _r0_new_and_duplicate_ledger(lineups)
        }
    }
    tags = dict(batch.all_tags)
    tags[lineups[0].ids] = (
        "lev", supply.FAMILY, "candidate_seed:R0",
    )
    tags[lineups[1].ids] = (
        supply.FAMILY, "candidate_seed:R0",
    )
    batch = replace(batch, all_tags=tags)

    trace = supply.build_selected_supply_trace(
        batch, lineups, mapping, transforms
    )

    assert trace["definition"]["producer_tag_is_not_supply_evidence"] is True
    assert trace["candidate_pool"][
        "genuinely_new_discovery_candidate_count"
    ] == 1
    assert trace["candidate_pool"][
        "duplicate_attempt_provenance_only_candidate_count"
    ] == 1
    for prefix in ("20", "40", "80"):
        selected = trace["selected_prefixes"][prefix]
        assert selected["genuinely_new_discovery_candidate_count"] == 1
        assert selected[
            "duplicate_attempt_provenance_only_candidate_count"
        ] == 1
        assert selected["any_cross_law_provenance_candidate_count"] == 2
        assert set(selected["genuinely_new_discovery_lineup_ids"]).isdisjoint(
            selected["duplicate_attempt_provenance_only_lineup_ids"]
        )
    r0 = trace["per_block_attempt_authority"]["R0"]
    assert r0["newly_supplied_attempt_count"] == 1
    assert r0["duplicate_attempt_count"] == 2
    assert r0["duplicate_provenance_only_attempt_count"] == 1
    assert r0["duplicate_of_newly_supplied_attempt_count"] == 1
    assert trace["uses_realized_outcomes"] is False
    assert len(trace["trace_sha256"]) == 64
    candidate_ids = [
        supply._dk_lineup_id(lineup, mapping) for lineup in lineups
    ]
    assert supply.validate_selected_supply_trace(
        trace,
        candidate_lineup_ids=candidate_ids,
        candidate_internal_roster_sha256s=[
            supply._roster_sha256(lineup) for lineup in lineups
        ],
        selected_lineup_ids=candidate_ids,
        candidate_source_blocks=batch.metadata["candidate_source_blocks"],
        transform_receipts_by_block=transforms,
    ) == trace


def test_rehashed_forged_new_supply_membership_is_rejected() -> None:
    batch, lineups, mapping, transforms = _fixture()
    transforms["R0"] = {
        "cross_law_discovery": {
            "exposure_ledger": _r0_new_and_duplicate_ledger(lineups)
        }
    }
    tags = dict(batch.all_tags)
    tags[lineups[0].ids] = (
        "lev", supply.FAMILY, "candidate_seed:R0",
    )
    tags[lineups[1].ids] = (
        supply.FAMILY, "candidate_seed:R0",
    )
    batch = replace(batch, all_tags=tags)
    trace = supply.build_selected_supply_trace(
        batch, lineups, mapping, transforms
    )
    candidate_ids = [
        supply._dk_lineup_id(lineup, mapping) for lineup in lineups
    ]
    internal_hashes = [
        supply._roster_sha256(lineup) for lineup in lineups
    ]

    forged = deepcopy(trace)
    true_new_id = candidate_ids[1]
    false_new_id = candidate_ids[2]
    duplicate_id = candidate_ids[0]
    for projection in (
        forged["candidate_pool"],
        *forged["selected_prefixes"].values(),
    ):
        projection["genuinely_new_discovery_lineup_ids"] = [false_new_id]
        projection["any_cross_law_provenance_lineup_ids"] = [
            duplicate_id, false_new_id,
        ]
        projection.pop("projection_sha256")
        projection["projection_sha256"] = supply.canonical_sha256(
            projection
        )
    forged_rows = []
    for ordinal, (lineup_id, roster_sha256, source) in enumerate(zip(
        candidate_ids,
        internal_hashes,
        batch.metadata["candidate_source_blocks"],
        strict=True,
    )):
        classification = "no-cross-law-provenance"
        if lineup_id == duplicate_id:
            classification = "duplicate-attempt-provenance-only"
        elif lineup_id == false_new_id:
            classification = "newly-supplied-discovery"
        assert lineup_id != true_new_id or classification == (
            "no-cross-law-provenance"
        )
        forged_rows.append({
            "candidate_ordinal": ordinal,
            "source_block": source,
            "internal_roster_sha256": roster_sha256,
            "dk_lineup_id": lineup_id,
            "classification": classification,
        })
    forged["classification_rows_sha256"] = supply.canonical_sha256(
        forged_rows
    )
    forged.pop("trace_sha256")
    forged["trace_sha256"] = supply.canonical_sha256(forged)

    with pytest.raises(
        supply.ProspectiveCrossLawSupplyTraceError,
        match="classification rows differ",
    ):
        supply.validate_selected_supply_trace(
            forged,
            candidate_lineup_ids=candidate_ids,
            candidate_internal_roster_sha256s=internal_hashes,
            selected_lineup_ids=candidate_ids,
            candidate_source_blocks=batch.metadata[
                "candidate_source_blocks"
            ],
            transform_receipts_by_block=transforms,
        )


def test_unledgered_cross_law_provenance_fails_closed() -> None:
    batch, lineups, mapping, transforms = _fixture()
    tags = dict(batch.all_tags)
    tags[lineups[0].ids] = (
        "lev", supply.FAMILY, "candidate_seed:R0",
    )
    batch = replace(batch, all_tags=tags)

    with pytest.raises(
        supply.ProspectiveCrossLawSupplyTraceError,
        match="provenance lacks a solve-ledger row",
    ):
        supply.build_selected_supply_trace(
            batch, lineups, mapping, transforms
        )


def test_new_discovery_roster_requires_cross_law_producer_tag() -> None:
    batch, lineups, mapping, transforms = _fixture()
    transforms["R0"] = {
        "cross_law_discovery": {
            "exposure_ledger": _r0_new_and_duplicate_ledger(lineups)
        }
    }

    with pytest.raises(
        supply.ProspectiveCrossLawSupplyTraceError,
        match="new cross-law supply lacks",
    ):
        supply.build_selected_supply_trace(
            batch, lineups, mapping, transforms
        )
