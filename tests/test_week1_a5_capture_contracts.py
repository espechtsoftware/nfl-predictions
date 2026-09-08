"""Adversarial tests for immutable Week-1 A5 capture contracts."""

from __future__ import annotations

import copy
import hashlib

import pytest

from nfl_dfs.inference.generation_exposure import canonical_sha256
from nfl_dfs.ingest import week1_a5_capture_contracts as capture

LOCK = "2026-09-13T17:00:00+00:00"
FROZEN = "2026-09-12T15:00:00Z"
ACCEPTED = "2026-09-13T15:30:00Z"
ROOT_FROZEN = "2026-09-13T16:00:00Z"
PREFIX = "gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/fixture/"
ROLE_SPECS = {
    "milly-5": ("193028206", 60, 57, 5_000_000, 57),
    "large-20max-3": ("193028208", 25, 20, 3_000_000, 20),
    "championship-qualifier-18": ("194478066", 5, 3, 18_000_000, 3),
    "championship-qualifier-5": ("194478065", 12, 10, 5_000_000, 10),
}


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _identity(
    label: str, *, digest: str | None = None, byte_count: int = 10
) -> dict[str, object]:
    return {
        "uri": f"{PREFIX}{label}.json",
        "generation": "1",
        "sha256": digest or _digest(label),
        "bytes": byte_count,
    }


def _lineup(policy: str, rank: int) -> str:
    return f"lineup-v1-{_digest(f'{policy}-{rank}')}"


def _allocation() -> dict[str, object]:
    contests: list[dict[str, object]] = []
    for role, (contest_id, capacity, entry_limit, fee, _k) in ROLE_SPECS.items():
        contests.append(
            {
                "role": role,
                "contest_id": contest_id,
                "contest_name": f"Fixture {role}",
                "draft_group_id": "151307",
                "field_cap": capacity,
                "entry_limit": entry_limit,
                "entry_fee_micro": fee,
                "lock_utc": LOCK,
                "planned_entries": capture.EXPECTED_ROLE_ENTRIES[role],
                "metadata_identity": _identity(f"{role}-metadata"),
                "payout_identity": _identity(f"{role}-payout"),
                "ticket_terms_identity": _identity(f"{role}-ticket"),
            }
        )
    paid: list[dict[str, object]] = []
    shadows: list[dict[str, object]] = []
    for role, (contest_id, _cap, _limit, _fee, k) in ROLE_SPECS.items():
        for rank in range(1, k + 1):
            paid.append(
                {
                    "contest_role": role,
                    "contest_id": contest_id,
                    "entry_index": rank,
                    "lineup_rank": rank,
                    "lineup_id": _lineup("P_MIX", rank),
                }
            )
            for policy in capture.SHADOW_POLICIES:
                shadows.append(
                    {
                        "book_id": policy,
                        "contest_role": role,
                        "contest_id": contest_id,
                        "entry_index": rank,
                        "lineup_rank": rank,
                        "lineup_id": _lineup(policy, rank),
                    }
                )
    body: dict[str, object] = {
        "schema_version": "week1-a5-contest-allocation/v1",
        "allocation_id": "2026-w01-a5-57-20-3-10-v1",
        "complete": True,
        "season": 2026,
        "week": 1,
        "draft_group_id": "151307",
        "lock_utc": LOCK,
        "participation_package_identity": _identity("package"),
        "selection_receipt_sha256": _digest("selection"),
        "book_identities": {
            "P_MIX": {
                "selection_receipt_sha256": _digest("selection"),
                "ordered_lineup_ids_sha256": _digest("pmix-order"),
            },
            "P_CTRL": {
                "selection_receipt_sha256": _digest("selection"),
                "ordered_lineup_ids_sha256": _digest("pctrl-order"),
            },
            "D400_DEMAX": {
                "artifact_identity": _identity("d400"),
                "ordered_lineup_ids_sha256": _digest("d400-order"),
            },
            "D800_WEMAX": {
                "artifact_identity": _identity("d800"),
                "ordered_lineup_ids_sha256": _digest("d800-order"),
            },
        },
        "paid_policy": "P_MIX",
        "fallback_policy": "P_CTRL",
        "shadow_policies": list(capture.SHADOW_POLICIES),
        "contests": contests,
        "paid_entry_edges": paid,
        "shadow_entry_edges": shadows,
        "planned_entry_count": 90,
        "planned_spend_micro": 449_000_000,
        "accepted_entry_receipts_pending": True,
        "outcome_fields_read": [],
    }
    body["allocation_sha256"] = canonical_sha256(body)
    return body


def _allocation_identity(allocation: dict[str, object]) -> dict[str, object]:
    return _identity("allocation", digest=str(allocation["allocation_sha256"]))


def _book_binding(policy: str, k: int) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    policy_offset = capture.EXPECTED_POLICIES.index(policy) * 100_000
    for rank in range(1, k + 1):
        internal = [policy_offset + rank * 100 + i for i in range(1, 10)]
        slot_ids = [policy_offset + rank * 1000 + i for i in range(1, 10)]
        entries.append(
            {
                "lineup_rank": rank,
                "lineup_id": _lineup(policy, rank),
                "roster_sha256": canonical_sha256(sorted(internal)),
                "internal_player_ids": internal,
                "slot_dk_draftable_ids": slot_ids,
            }
        )
    return {
        "schema_version": capture.BOOK_BINDING_SCHEMA,
        "policy": policy,
        "purpose": "paid" if policy == "P_MIX" else "shadow",
        "artifact_identity": _identity(f"{policy}-book-{k}"),
        "entries": entries,
    }


def _manifest(allocation: dict[str, object], role: str) -> dict[str, object]:
    _contest_id, capacity, _limit, _fee, k = ROLE_SPECS[role]
    sources = {
        name: {"identity": _identity(f"{role}-{name}"), "captured_at": FROZEN}
        for name in (
            "contest_metadata",
            "payout_ladder",
            "late_swap",
            "current_entries",
        )
    }
    return capture.build_week1_prelock_manifest_v3(
        allocation=allocation,
        allocation_identity=_allocation_identity(allocation),
        contest_role=role,
        slate_id=capture.EXPECTED_SLATE_ID,
        advertised_field_capacity=capacity,
        entries_observed_at_freeze=capacity - 2,
        entries_observed_at=FROZEN,
        manifest_frozen_at=FROZEN,
        late_swap={
            "enabled": True,
            "policy": "dk-classic",
            "state_at_freeze": "prelock",
        },
        payout_ladder_underfill_policy="prelock-applicable-ranks-only",
        payout_ladder=[
            {
                "rank_start": 1,
                "rank_end": capacity,
                "payout_micro": 1,
                "award_label": "fixture",
            }
        ],
        source_identities=sources,
        book_bindings=[
            _book_binding(policy, k) for policy in capture.EXPECTED_POLICIES
        ],
        correction_lineage={
            "revision": 0,
            "supersedes_manifest_sha256": None,
            "reason": "initial",
        },
    )


def _manifest_identity(manifest: dict[str, object], role: str) -> dict[str, object]:
    return _identity(f"{role}-manifest", digest=str(manifest["manifest_sha256"]))


def _acceptance(
    allocation: dict[str, object], manifest: dict[str, object], role: str
) -> dict[str, object]:
    contest_id, _capacity, _limit, _fee, _k = ROLE_SPECS[role]
    paid_book = manifest["a5_binding"]["book_bindings"][0]
    entries = paid_book["entries"]
    role_offset = list(ROLE_SPECS).index(role) * 1000
    prepared_rows: list[dict[str, object]] = []
    accepted_rows: list[dict[str, object]] = []
    for ordinal, book in enumerate(entries):
        entry_id = str(10_000 + role_offset + ordinal)
        prepared_rows.append(
            {
                "export_ordinal": ordinal,
                "entry_id": entry_id,
                "internal_player_ids": list(book["internal_player_ids"]),
                "dk_draftable_ids": sorted(book["slot_dk_draftable_ids"]),
                "paid_input_book_ordinal": ordinal,
                "slot_dk_draftable_ids": list(book["slot_dk_draftable_ids"]),
            }
        )
        accepted_rows.append(
            {
                "entry_id": entry_id,
                "contest_id": contest_id,
                "draft_group_id": "151307",
                "slot_dk_draftable_ids": list(book["slot_dk_draftable_ids"]),
                "status": "accepted",
            }
        )
    prepared: dict[str, object] = {
        "schema_version": "paid-entry-capture/v1",
        "contest_id": contest_id,
        "draft_group_id": "151307",
        "salary_catalog_sha256": _digest("catalog"),
        "csv_sha256": _digest(f"{role}-filled-csv"),
        "csv_bytes": 500,
        "paid_export_receipt_sha256": _digest("export"),
        "entries": prepared_rows,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    return capture.build_week1_entry_acceptance_v1(
        manifest=manifest,
        manifest_identity=_manifest_identity(manifest, role),
        allocation=allocation,
        allocation_identity=_allocation_identity(allocation),
        prepared_capture=prepared,
        prepared_capture_identity=_identity(
            f"{role}-prepared", digest=canonical_sha256(prepared)
        ),
        filled_upload_identity=_identity(
            f"{role}-filled", digest=str(prepared["csv_sha256"]), byte_count=500
        ),
        acceptance_evidence_rows=accepted_rows,
        acceptance_evidence_identity=_identity(f"{role}-acceptance-evidence"),
        accepted_at=ACCEPTED,
    )


def _cohort() -> tuple[
    dict[str, object],
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
    dict[str, object],
]:
    allocation = _allocation()
    manifests = {role: _manifest(allocation, role) for role in ROLE_SPECS}
    receipts = {
        role: _acceptance(allocation, manifests[role], role) for role in ROLE_SPECS
    }
    root = capture.build_week1_acceptance_root_v1(
        allocation=allocation,
        allocation_identity=_allocation_identity(allocation),
        manifests_by_role=manifests,
        receipts_by_role=receipts,
        receipt_identities_by_role={
            role: _identity(f"{role}-receipt", digest=str(receipt["acceptance_sha256"]))
            for role, receipt in receipts.items()
        },
        frozen_at=ROOT_FROZEN,
    )
    return allocation, manifests, receipts, root


def _rehash(value: dict[str, object], field: str) -> None:
    value.pop(field, None)
    value[field] = canonical_sha256(value)


def test_prelock_v3_keeps_capacity_current_fill_and_final_size_separate() -> None:
    allocation = _allocation()
    manifest = _manifest(allocation, "milly-5")
    contest = manifest["contest"]
    assert contest["advertised_field_capacity"] == 60
    assert contest["entries_observed_at_freeze"] == 58
    assert "field_size" not in contest
    assert "observed_final_field_size" not in contest
    assert manifest["a5_binding"]["planned_entries"] == 57
    assert [book["policy"] for book in manifest["a5_binding"]["book_bindings"]] == list(
        capture.EXPECTED_POLICIES
    )


def test_prelock_v3_rejects_wrong_contest_and_postlock_or_outcome_mutation() -> None:
    allocation = _allocation()
    manifest = _manifest(allocation, "milly-5")
    wrong = copy.deepcopy(manifest)
    wrong["contest"]["contest_id"] = "999"
    _rehash(wrong, "manifest_sha256")
    with pytest.raises(capture.Week1A5CaptureContractError, match="contest identity"):
        capture.validate_week1_prelock_manifest_v3(wrong, allocation=allocation)

    wrong_group = copy.deepcopy(manifest)
    wrong_group["contest"]["draft_group_id"] = "151999"
    _rehash(wrong_group, "manifest_sha256")
    with pytest.raises(capture.Week1A5CaptureContractError, match="contest identity"):
        capture.validate_week1_prelock_manifest_v3(wrong_group, allocation=allocation)

    postlock = copy.deepcopy(manifest)
    postlock["manifest_frozen_at"] = "2026-09-13T18:00:00Z"
    _rehash(postlock, "manifest_sha256")
    with pytest.raises(capture.Week1A5CaptureContractError, match="precede lock"):
        capture.validate_week1_prelock_manifest_v3(postlock, allocation=allocation)

    leaked = copy.deepcopy(manifest)
    leaked["contest"]["observed_final_field_size"] = 59
    _rehash(leaked, "manifest_sha256")
    with pytest.raises(capture.Week1A5CaptureContractError, match="fields differ"):
        capture.validate_week1_prelock_manifest_v3(leaked, allocation=allocation)


def test_prelock_correction_requires_exact_predecessor() -> None:
    allocation = _allocation()
    manifest = _manifest(allocation, "milly-5")
    manifest["correction_lineage"] = {
        "revision": 1,
        "supersedes_manifest_sha256": None,
        "reason": "capacity correction",
    }
    _rehash(manifest, "manifest_sha256")
    with pytest.raises(
        capture.Week1A5CaptureContractError, match="supersedes_manifest"
    ):
        capture.validate_week1_prelock_manifest_v3(manifest, allocation=allocation)


def test_entry_acceptance_binds_exact_entry_ids_rosters_and_ordinal_bridge() -> None:
    allocation = _allocation()
    manifest = _manifest(allocation, "championship-qualifier-18")
    receipt = _acceptance(allocation, manifest, "championship-qualifier-18")
    assert [row["a5_entry_index"] for row in receipt["entries"]] == [1, 2, 3]
    assert [row["a5_lineup_rank"] for row in receipt["entries"]] == [1, 2, 3]
    assert receipt["ordinal_bridge"]["prepared_export_base"] == 0
    assert receipt["ordinal_bridge"]["a5_entry_base"] == 1

    drift = copy.deepcopy(receipt)
    drift["entries"][0]["entry_id"] = "999999"
    drift["entries"][0]["lineup_id"] = drift["entries"][1]["lineup_id"]
    _rehash(drift, "acceptance_sha256")
    with pytest.raises(capture.Week1A5CaptureContractError, match="duplicate|differs"):
        capture.validate_week1_entry_acceptance_v1(
            drift, manifest=manifest, allocation=allocation
        )

    roster_drift = copy.deepcopy(receipt)
    roster_drift["entries"][0]["internal_player_ids"][0] += 900_000
    roster_drift["entries"][0]["roster_sha256"] = canonical_sha256(
        sorted(roster_drift["entries"][0]["internal_player_ids"])
    )
    _rehash(roster_drift, "acceptance_sha256")
    with pytest.raises(capture.Week1A5CaptureContractError, match="differs"):
        capture.validate_week1_entry_acceptance_v1(
            roster_drift, manifest=manifest, allocation=allocation
        )


def test_entry_acceptance_rejects_postlock_acceptance() -> None:
    allocation = _allocation()
    manifest = _manifest(allocation, "championship-qualifier-18")
    receipt = _acceptance(allocation, manifest, "championship-qualifier-18")
    receipt["accepted_at"] = "2026-09-13T18:00:00Z"
    _rehash(receipt, "acceptance_sha256")
    with pytest.raises(capture.Week1A5CaptureContractError, match="before lock"):
        capture.validate_week1_entry_acceptance_v1(
            receipt, manifest=manifest, allocation=allocation
        )


def test_four_contest_root_requires_all_four_and_exactly_ninety_entries() -> None:
    allocation, manifests, receipts, root = _cohort()
    assert root["accepted_entry_count"] == 90
    assert [row["planned_entries"] for row in root["required_contests"]] == [
        57,
        20,
        3,
        10,
    ]
    missing = dict(receipts)
    missing.pop("milly-5")
    with pytest.raises(capture.Week1A5CaptureContractError, match="all exact A5 roles"):
        capture.build_week1_acceptance_root_v1(
            allocation=allocation,
            allocation_identity=_allocation_identity(allocation),
            manifests_by_role=manifests,
            receipts_by_role=missing,
            receipt_identities_by_role={},
            frozen_at=ROOT_FROZEN,
        )


def _settlement_rows(
    receipt: dict[str, object], final_size: int, *, tie_first: bool = False
) -> list[dict[str, object]]:
    entry_ids = [str(row["entry_id"]) for row in receipt["entries"]]
    entry_ids.extend(str(900_000 + i) for i in range(final_size - len(entry_ids)))
    rows: list[dict[str, object]] = []
    for ordinal, entry_id in enumerate(entry_ids):
        rank = ordinal + 1
        points = (final_size - ordinal) * 1_000_000
        payout = 1
        if tie_first and ordinal < 2:
            rank, points, payout = 1, final_size * 1_000_000, 80
        rows.append(
            {
                "entry_id": entry_id,
                "rank": rank,
                "points_micropoints": points,
                "payout_micro": payout,
            }
        )
    return rows


def _settlement(
    allocation: dict[str, object],
    manifests: dict[str, dict[str, object]],
    receipts: dict[str, dict[str, object]],
    root: dict[str, object],
    *,
    final_size: int,
    rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    role = "milly-5"
    standings = rows or _settlement_rows(receipts[role], final_size)
    return capture.build_week1_settlement_v1(
        manifest=manifests[role],
        manifest_identity=_manifest_identity(manifests[role], role),
        allocation=allocation,
        allocation_identity=_allocation_identity(allocation),
        acceptance_root=root,
        acceptance_root_identity=_identity(
            "acceptance-root", digest=str(root["acceptance_root_sha256"])
        ),
        manifests_by_role=manifests,
        receipts_by_role=receipts,
        standings_source_identity=_identity("settled-standings"),
        normalized_standings_identity=_identity(
            "normalized-standings", digest=canonical_sha256(standings)
        ),
        standings_rows=standings,
        observed_final_field_size=final_size,
        captured_at="2026-09-14T23:00:00Z",
        confirm_settled=True,
        confirm_full_field=True,
        correction_lineage={
            "revision": 0,
            "supersedes_settlement_sha256": None,
            "reason": "initial",
        },
    )


def test_underfilled_settlement_keeps_capacity_immutable_and_reconciles_applicable_ranks() -> (
    None
):
    allocation, manifests, receipts, root = _cohort()
    settlement = _settlement(allocation, manifests, receipts, root, final_size=59)
    assert settlement["advertised_field_capacity"] == 60
    assert settlement["observed_final_field_size"] == 59
    assert settlement["underfilled_vs_advertised"] is True
    assert settlement["applicable_payout_reconciliation"] == {
        "underfill_policy": "prelock-applicable-ranks-only",
        "applicable_rank_count": 59,
        "scheduled_applicable_prize_pool_micro": 59,
        "observed_prize_pool_micro": 59,
        "maximum_tie_rounding_residual_micro": 0,
        "reconciled": True,
    }
    assert manifests["milly-5"]["contest"]["entries_observed_at_freeze"] == 58


def test_filled_settlement_is_not_labeled_underfilled() -> None:
    allocation, manifests, receipts, root = _cohort()
    settlement = _settlement(allocation, manifests, receipts, root, final_size=60)
    assert settlement["observed_final_field_size"] == 60
    assert settlement["underfilled_vs_advertised"] is False
    assert settlement["applicable_payout_reconciliation"]["applicable_rank_count"] == 60


def test_settlement_reconciles_ties_across_payout_positions() -> None:
    allocation, manifests, receipts, root = _cohort()
    manifest = manifests["milly-5"]
    manifest["payout_ladder"] = [
        {"rank_start": 1, "rank_end": 1, "payout_micro": 100, "award_label": "first"},
        {"rank_start": 2, "rank_end": 2, "payout_micro": 60, "award_label": "second"},
        {"rank_start": 3, "rank_end": 60, "payout_micro": 1, "award_label": "other"},
    ]
    _rehash(manifest, "manifest_sha256")
    # Rebuild this contest's acceptance against the corrected pre-lock manifest,
    # then the four-contest root; no pre-lock object is overwritten in reality.
    receipts["milly-5"] = _acceptance(allocation, manifest, "milly-5")
    root = capture.build_week1_acceptance_root_v1(
        allocation=allocation,
        allocation_identity=_allocation_identity(allocation),
        manifests_by_role=manifests,
        receipts_by_role=receipts,
        receipt_identities_by_role={
            role: _identity(f"tie-{role}", digest=str(receipt["acceptance_sha256"]))
            for role, receipt in receipts.items()
        },
        frozen_at=ROOT_FROZEN,
    )
    rows = _settlement_rows(receipts["milly-5"], 59, tie_first=True)
    settlement = _settlement(
        allocation, manifests, receipts, root, final_size=59, rows=rows
    )
    assert settlement["applicable_payout_reconciliation"]["reconciled"] is True
    assert (
        settlement["applicable_payout_reconciliation"]["observed_prize_pool_micro"]
        == 217
    )


def test_settlement_rejects_impossible_or_partial_field_and_missing_predecessor() -> (
    None
):
    allocation, manifests, receipts, root = _cohort()
    rows = _settlement_rows(receipts["milly-5"], 59)
    with pytest.raises(capture.Week1A5CaptureContractError, match="exceeds advertised"):
        _settlement(allocation, manifests, receipts, root, final_size=61, rows=rows)
    with pytest.raises(capture.Week1A5CaptureContractError, match="row count differs"):
        _settlement(allocation, manifests, receipts, root, final_size=60, rows=rows)

    settlement = _settlement(allocation, manifests, receipts, root, final_size=59)
    settlement["correction_lineage"] = {
        "revision": 1,
        "supersedes_settlement_sha256": None,
        "reason": "official correction",
    }
    _rehash(settlement, "settlement_sha256")
    with pytest.raises(
        capture.Week1A5CaptureContractError, match="supersedes_settlement"
    ):
        capture.validate_week1_settlement_v1(
            settlement,
            manifest=manifests["milly-5"],
            allocation=allocation,
            acceptance_root=root,
            manifests_by_role=manifests,
            receipts_by_role=receipts,
            standings_rows=rows,
        )


def test_underfilled_official_ladder_requires_separate_settlement_authority() -> None:
    allocation, manifests, receipts, root = _cohort()
    manifest = manifests["milly-5"]
    manifest["contest"]["payout_ladder_underfill_policy"] = "official-settlement-ladder"
    _rehash(manifest, "manifest_sha256")
    receipts["milly-5"] = _acceptance(allocation, manifest, "milly-5")
    root = capture.build_week1_acceptance_root_v1(
        allocation=allocation,
        allocation_identity=_allocation_identity(allocation),
        manifests_by_role=manifests,
        receipts_by_role=receipts,
        receipt_identities_by_role={
            role: _identity(
                f"official-{role}", digest=str(receipt["acceptance_sha256"])
            )
            for role, receipt in receipts.items()
        },
        frozen_at=ROOT_FROZEN,
    )
    with pytest.raises(
        capture.Week1A5CaptureContractError,
        match="requires a successor schema",
    ):
        _settlement(allocation, manifests, receipts, root, final_size=59)
