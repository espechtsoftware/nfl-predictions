"""Adversarial exact-byte tests for the repaired Week-1 A5 contracts."""

from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
from dataclasses import dataclass

import pytest

from nfl_dfs.inference.generation_exposure import (
    canonical_json_bytes,
    canonical_sha256,
)
from nfl_dfs.ingest import week1_a5_capture_contracts as capture
from scripts import week1_a5_capture_real_shape_smoke as shape_smoke_cli

PRELOCK_SOURCE_TIME = "2026-09-04T10:55:35.926577+00:00"
BRIDGE_TIME = "2026-09-10T10:00:00Z"
SALARY_PULLED_AT = "2026-09-10T09:00:00+00:00"
ALLOCATION_TIME = "2026-09-11T10:00:00Z"
ALLOCATION_CREATED_AT = "2026-09-11T09:55:00Z"
MANIFEST_TIME = "2026-09-12T10:00:00Z"
MANIFEST_CREATED_AT = "2026-09-12T09:55:00Z"
ACCEPTANCE_SOURCE_TIME = "2026-09-13T15:00:00Z"
PREPARED_UPLOAD_CREATED_AT = "2026-09-13T14:50:00Z"
ACCEPTANCE_RAW_ARCHIVED_AT = "2026-09-13T15:02:00Z"
ACCEPTANCE_ACQUISITION_RECEIPT_TIME = "2026-09-13T15:05:00Z"
ACCEPTANCE_CAPTURE_TIME = "2026-09-13T15:10:00Z"
ACCEPTANCE_CAPTURE_PUBLISH_BY = "2026-09-13T15:15:00Z"
ACCEPTANCE_EVIDENCE_TIME = "2026-09-13T15:20:00Z"
ACCEPTANCE_EVIDENCE_PUBLISH_BY = "2026-09-13T15:30:00Z"
ACCEPTED_AT = "2026-09-13T16:00:00Z"
ACCEPTANCE_RECEIPT_CREATED_AT = "2026-09-13T15:50:00Z"
ROOT_TIME = "2026-09-13T16:30:00Z"
ROOT_CREATED_AT = "2026-09-13T16:20:00Z"
SETTLEMENT_SOURCE_TIME = "2026-09-14T20:00:00Z"
SETTLEMENT_SOURCE_ARCHIVED_AT = "2026-09-14T20:02:00Z"
SETTLEMENT_ACQUISITION_RECEIPT_TIME = "2026-09-14T20:05:00Z"
FINAL_FIELD_CAPTURE_TIME = "2026-09-14T20:10:00Z"
FINAL_FIELD_CAPTURE_PUBLISH_BY = "2026-09-14T20:15:00Z"
FINAL_FIELD_EVIDENCE_TIME = "2026-09-14T20:30:00Z"
FINAL_FIELD_EVIDENCE_CREATED_AT = "2026-09-14T20:20:00Z"
SETTLEMENT_TIME = "2026-09-14T21:00:00Z"
NORMALIZED_FIELD_CREATED_AT = "2026-09-14T20:50:00Z"
PREFIX = "gs://fixture/week1-a5-v3-repair"
FIXTURE_ACCEPTANCE_DOWNLOAD_LOCATOR = (
    "https://fixture.draftkings.invalid/mycontests/active-entry-export.csv"
)


class MemoryStore:
    """Exact-generation store with independently controlled provider time."""

    def __init__(self) -> None:
        self.now = PRELOCK_SOURCE_TIME
        self.next_generation = 1
        self.objects: dict[tuple[str, str], dict[str, object]] = {}

    def publish_create_once(
        self, *, uri: str, raw: bytes, content_type: str
    ) -> dict[str, object]:
        del content_type
        if any(key[0] == uri for key in self.objects):
            raise ValueError("create-once collision")
        generation = str(self.next_generation)
        self.next_generation += 1
        identity = {
            "uri": uri,
            "generation": generation,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[(uri, generation)] = {
            "identity": identity,
            "created_at": self.now,
            "raw": raw,
        }
        return {"identity": identity, "created_at": self.now}

    def read_exact(self, *, identity: dict[str, object]) -> dict[str, object]:
        key = (str(identity["uri"]), str(identity["generation"]))
        if key not in self.objects:
            raise ValueError("exact generation does not exist")
        return copy.deepcopy(self.objects[key])

    def put_raw(self, label: str, raw: bytes, *, created_at: str) -> dict[str, object]:
        self.now = created_at
        receipt = self.publish_create_once(
            uri=f"{PREFIX}/{label}", raw=raw, content_type="application/octet-stream"
        )
        return dict(receipt["identity"])


class MemoryAcquisitionAuthority:
    """Test trust root that recognizes only explicitly issued receipts."""

    def __init__(self) -> None:
        self.records: dict[tuple[str, str], dict[str, object]] = {}

    def register(
        self,
        *,
        store: MemoryStore,
        receipt_identity: dict[str, object],
        authority_event_id: str,
    ) -> None:
        reopened = store.read_exact(identity=receipt_identity)
        key = (str(receipt_identity["uri"]), str(receipt_identity["generation"]))
        self.records[key] = {
            "identity": copy.deepcopy(reopened["identity"]),
            "created_at": reopened["created_at"],
            "raw": reopened["raw"],
            "authority_event_id": authority_event_id,
        }

    def read_authenticated_acquisition(
        self, *, identity: dict[str, object]
    ) -> dict[str, object]:
        key = (str(identity["uri"]), str(identity["generation"]))
        if key not in self.records:
            raise ValueError("receipt was not emitted by the acquisition authority")
        return copy.deepcopy(self.records[key])


def _ref(publication: dict[str, object]) -> dict[str, object]:
    return {
        "artifact_identity": publication["artifact_identity"],
        "semantic_sha256": publication["semantic_sha256"],
    }


def _publish_semantic(
    store: MemoryStore,
    label: str,
    value: dict[str, object],
    *,
    created_at: str,
    not_after: str | None = None,
    not_before: str | None = None,
) -> dict[str, object]:
    store.now = created_at
    return capture.publish_semantic_artifact(
        store,
        uri=f"{PREFIX}/{label}.json",
        artifact=value,
        not_after=not_after,
        not_before=not_before,
    )


def _issue_acquisition(
    *,
    store: MemoryStore,
    authority: MemoryAcquisitionAuthority,
    pin: capture.ContestPin,
    profile: str,
    raw_identity: dict[str, object],
    observed_at: str,
    receipt_created_at: str,
    suffix: str,
    register: bool = True,
    authority_event_id: str | None = None,
) -> dict[str, object]:
    if profile == capture.ACCEPTANCE_ACQUISITION_PROFILE:
        locator = capture.PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR
        if locator is None:
            raise AssertionError("fixture acceptance locator is not pinned")
    elif profile == capture.CONTEST_DETAIL_ACQUISITION_PROFILE:
        locator = f"{capture.FINAL_FIELD_SOURCE_LOCATOR_PREFIX}{pin.contest_id}"
    elif profile == capture.STANDINGS_ACQUISITION_PROFILE:
        locator = f"{capture.FINAL_STANDINGS_SOURCE_LOCATOR_PREFIX}{pin.contest_id}"
    else:
        raise AssertionError(profile)
    raw_created_at = str(store.read_exact(identity=raw_identity)["created_at"])
    event_id = authority_event_id or (
        f"fixture-{pin.contest_id}-{profile.split('/', 1)[0]}-{suffix}"
    )
    is_json = profile == capture.CONTEST_DETAIL_ACQUISITION_PROFILE
    response_content_type = (
        "application/json" if is_json else "text/csv; charset=utf-8"
    )
    response_content_disposition = (
        None if is_json else 'attachment; filename="DraftKings-export.csv"'
    )
    collector_source_commit = "a" * 40
    collector_code_sha256 = "b" * 64
    collector_image_digest = f"sha256:{'c' * 64}"
    trace_identity = store.put_raw(
        f"transport-trace-{pin.role}-{suffix}.json",
        canonical_json_bytes(
            {
                "schema_version": capture.PROVIDER_TRANSPORT_TRACE_SCHEMA,
                "authority_event_id": event_id,
                "request_method": "GET",
                "canonical_locator": locator,
                "authenticated_surface": capture.PROVIDER_AUTHENTICATED_SURFACE,
                "observed_at": observed_at,
                "response_status": 200,
                "response_content_type": response_content_type,
                "response_content_disposition": response_content_disposition,
                "collector_source_commit": collector_source_commit,
                "collector_code_sha256": collector_code_sha256,
                "collector_image_digest": collector_image_digest,
                "raw_object_identity": raw_identity,
            }
        ),
        created_at=raw_created_at,
    )
    receipt = capture.seal_semantic_artifact(
        {
            "schema_version": capture.PROVIDER_ACQUISITION_SCHEMA,
            "authority_profile": capture.PROVIDER_ACQUISITION_AUTHORITY_PROFILE,
            "authority_event_id": event_id,
            "acquisition_profile": profile,
            "source_system": "draftkings",
            "authenticated_surface": capture.PROVIDER_AUTHENTICATED_SURFACE,
            "request_method": "GET",
            "canonical_locator": locator,
            "contest_role": pin.role,
            "contest_id": pin.contest_id,
            "draft_group_id": capture.EXPECTED_DRAFT_GROUP_ID,
            "observed_at": observed_at,
            "response_status": 200,
            "response_content_type": response_content_type,
            "response_content_disposition": response_content_disposition,
            "collector_source_commit": collector_source_commit,
            "collector_code_sha256": collector_code_sha256,
            "collector_image_digest": collector_image_digest,
            "transport_trace_identity": trace_identity,
            "raw_object_identity": raw_identity,
            "raw_provider_created_at": raw_created_at,
        }
    )
    publication = _publish_semantic(
        store,
        f"acquisition-{pin.role}-{suffix}",
        receipt,
        created_at=receipt_created_at,
    )
    if register:
        authority.register(
            store=store,
            receipt_identity=publication["artifact_identity"],
            authority_event_id=event_id,
        )
    return _ref(publication)


def _source_payout_summary(pin: capture.ContestPin) -> list[dict[str, object]]:
    if pin.is_qualifier:
        ticket = ",".join(capture.QUALIFIER_TICKET_NAMES)
        cash_dollars = pin.advertised_prize_pool_micro // 1_000_000 - 70_000
        return [
            {
                "minPosition": 1,
                "maxPosition": 1,
                "payoutDescriptions": [
                    {
                        "order": 1,
                        "payoutDescription": ticket,
                        "payoutDescriptionType": "Text",
                        "quantity": 1,
                        "value": 70_000.0,
                    }
                ],
                "tierPayoutDescriptions": {"Ticket": ticket},
            },
            {
                "minPosition": 2,
                "maxPosition": 2,
                "payoutDescriptions": [
                    {
                        "order": 1,
                        "payoutDescription": f"${cash_dollars}.00",
                        "payoutDescriptionType": "Text",
                        "quantity": 1,
                        "value": float(cash_dollars),
                    }
                ],
                "tierPayoutDescriptions": {"Cash": f"${cash_dollars}.00"},
            },
            {
                "minPosition": 3,
                "maxPosition": pin.advertised_field_capacity,
                "payoutDescriptions": [
                    {
                        "order": 1,
                        "payoutDescription": "$0.00",
                        "payoutDescriptionType": "Text",
                        "quantity": 1,
                        "value": 0.0,
                    }
                ],
                "tierPayoutDescriptions": {"Cash": "$0.00"},
            },
        ]
    prize_dollars = pin.advertised_prize_pool_micro // 1_000_000
    return [
        {
            "minPosition": 1,
            "maxPosition": 1,
            "payoutDescriptions": [
                {
                    "order": 1,
                    "payoutDescription": f"${prize_dollars}.00",
                    "payoutDescriptionType": "Text",
                    "quantity": 1,
                    "value": float(prize_dollars),
                }
            ],
            "tierPayoutDescriptions": {"Cash": f"${prize_dollars}.00"},
        },
        {
            "minPosition": 2,
            "maxPosition": pin.advertised_field_capacity,
            "payoutDescriptions": [
                {
                    "order": 1,
                    "payoutDescription": "$0.00",
                    "payoutDescriptionType": "Text",
                    "quantity": 1,
                    "value": 0.0,
                }
            ],
            "tierPayoutDescriptions": {"Cash": "$0.00"},
        },
    ]


def _source_child(pin: capture.ContestPin) -> dict[str, object]:
    attributes = {"IsQualifier": "true"} if pin.is_qualifier else {}
    return {
        "schema_version": "dk-contest-detail-prelock-source/v1",
        "captured_at": PRELOCK_SOURCE_TIME,
        "contest_id": pin.contest_id,
        "endpoint": f"https://api.draftkings.com/contests/v1/contests/{pin.contest_id}",
        "outcome_fields_read": [],
        "source": {
            "errorStatus": {},
            "contestDetail": {
                "contestKey": pin.contest_id,
                "name": pin.name,
                "draftGroupId": int(capture.EXPECTED_DRAFT_GROUP_ID),
                "contestStartTime": "2026-09-13T17:00:00.0000000Z",
                "contestState": "Upcoming",
                "contestStateDetail": "Upcoming",
                "entryFee": pin.entry_fee_micro // 1_000_000,
                "maximumEntries": pin.advertised_field_capacity,
                "maximumEntriesPerUser": pin.entry_limit,
                "entries": pin.planned_entries,
                "isGuaranteed": True,
                "wasResized": False,
                "totalPayouts": pin.advertised_prize_pool_micro // 1_000_000,
                "attributes": attributes,
                "payoutSummary": _source_payout_summary(pin),
            }
        },
    }


def _install_sources(store: MemoryStore) -> capture.A5SourcePins:
    child_identities: dict[str, dict[str, object]] = {}
    for pin in capture.A5_ROLE_TABLE.values():
        raw = json.dumps(_source_child(pin), sort_keys=True).encode()
        child_identities[pin.contest_id] = store.put_raw(
            f"source-{pin.contest_id}.json", raw, created_at=PRELOCK_SOURCE_TIME
        )
    source_rows = []
    for pin in capture.A5_ROLE_TABLE.values():
        source_rows.append(
            {
                "checks": {
                    "contestKey": True,
                    "contestStartTime": True,
                    "contestState": True,
                    "draftGroupId": True,
                    "entryFee": True,
                    "isQualifier": True,
                    "maximumEntries": True,
                    "maximumEntriesPerUser": True,
                    "name": True,
                    "payoutSummary": True,
                },
                "contest_id": pin.contest_id,
                "identity": child_identities[pin.contest_id],
                "qualifier_ticket_names": (
                    ",".join(capture.QUALIFIER_TICKET_NAMES)
                    if pin.is_qualifier
                    else None
                ),
            }
        )
    terminal = {
        "schema_version": "week1-a5-contest-source-manifest/v1",
        "capture_id": "20260904T105535Z",
        "complete": True,
        "season": 2026,
        "week": 1,
        "draft_group_id": 151307,
        "lock_utc": "2026-09-13T17:00:00+00:00",
        "captured_at": PRELOCK_SOURCE_TIME,
        "contest_sources": source_rows,
        "all_sources_create_once_and_exact_reopened": True,
        "all_sources_upcoming": True,
        "qualifier_ticket_terms_complete": True,
        "paid_entries_created": 0,
        "outcome_fields_read": [],
    }
    terminal_identity = store.put_raw(
        "source-manifest.json",
        json.dumps(terminal, sort_keys=True).encode(),
        created_at=PRELOCK_SOURCE_TIME,
    )
    template_projection = [
        {
            "contest_id": pin.contest_id,
            "contest_template_id": pin.template_id,
        }
        for pin in capture.A5_ROLE_TABLE.values()
    ]
    template_identity = store.put_raw(
        "lobby-template-projection.json",
        canonical_json_bytes(template_projection),
        created_at=PRELOCK_SOURCE_TIME,
    )
    return capture.A5SourcePins(
        manifest_identity=terminal_identity,
        contest_identities=child_identities,
        template_projection_identity=template_identity,
        template_projection_semantic_sha256=canonical_sha256(template_projection),
    )


def _install_bridge_and_books(
    store: MemoryStore,
) -> tuple[dict[str, object], dict[str, dict[str, object]], dict[str, object]]:
    salary_players: list[dict[str, object]] = []
    bridge_players: list[dict[str, object]] = []
    book_entries: dict[str, list[dict[str, object]]] = {
        policy: [] for policy in capture.EXPECTED_POLICIES
    }
    next_id = 1
    for policy in capture.EXPECTED_POLICIES:
        for rank in range(1, capture.EXPECTED_BOOK_SIZE + 1):
            internal_ids: list[str] = []
            draftable_ids: list[int] = []
            for slot_ordinal, slot in enumerate(capture.CLASSIC_SLOTS, start=1):
                internal_id = f"internal-{next_id:05d}"
                dk_player_id = next_id
                draftable_id = 100_000 + next_id
                next_id += 1
                position = "RB" if slot == "FLEX" else slot
                display_name = f"{policy} R{rank} P{slot_ordinal}"
                salary_players.append(
                    {
                        "player_id": dk_player_id,
                        "draftable_id": draftable_id,
                        "name": display_name,
                        "team": f"T{dk_player_id % 32:02d}",
                        "pos": position,
                        "salary": 5_000,
                        "status": "",
                    }
                )
                bridge_players.append(
                    {
                        "internal_player_id": internal_id,
                        "dk_player_id": dk_player_id,
                        "dk_draftable_id": draftable_id,
                        "display_name": display_name,
                        "team": f"T{dk_player_id % 32:02d}",
                        "position": position,
                        "salary": 5_000,
                        "status": "",
                    }
                )
                internal_ids.append(internal_id)
                draftable_ids.append(draftable_id)
            roster_sha = canonical_sha256(sorted(internal_ids))
            book_entries[policy].append(
                {
                    "lineup_rank": rank,
                    "lineup_id": f"lineup-v1-{roster_sha}",
                    "roster_sha256": roster_sha,
                    "internal_player_ids": internal_ids,
                    "slot_dk_draftable_ids": draftable_ids,
                    "salary": 45_000,
                }
            )
    paid_catalog_sha256 = canonical_sha256(
        {
            "draft_group_id": int(capture.EXPECTED_DRAFT_GROUP_ID),
            "pulled_at": SALARY_PULLED_AT,
            "players": salary_players,
        }
    )
    salary_catalog = capture.seal_semantic_artifact(
        {
            "schema_version": capture.SALARY_CATALOG_SCHEMA,
            "slate_id": capture.EXPECTED_SLATE_ID,
            "draft_group_id": capture.EXPECTED_DRAFT_GROUP_ID,
            "pulled_at": SALARY_PULLED_AT,
            "players": salary_players,
            "paid_catalog_sha256": paid_catalog_sha256,
        }
    )
    salary_publication = _publish_semantic(
        store,
        "paid-salary-catalog",
        salary_catalog,
        created_at=BRIDGE_TIME,
        not_after=ALLOCATION_TIME,
    )
    bridge = capture.seal_semantic_artifact(
        {
            "schema_version": capture.PLAYER_BRIDGE_SCHEMA,
            "slate_id": capture.EXPECTED_SLATE_ID,
            "draft_group_id": capture.EXPECTED_DRAFT_GROUP_ID,
            "salary_cap": capture.SALARY_CAP,
            "salary_catalog": _ref(salary_publication),
            "paid_catalog_sha256": paid_catalog_sha256,
            "players": bridge_players,
        }
    )
    bridge_publication = _publish_semantic(
        store,
        "player-bridge",
        bridge,
        created_at=BRIDGE_TIME,
        not_after=ALLOCATION_TIME,
    )
    bridge_ref = _ref(bridge_publication)
    book_refs: dict[str, dict[str, object]] = {}
    for policy in capture.EXPECTED_POLICIES:
        book = capture.seal_semantic_artifact(
            {
                "schema_version": capture.BOOK_SCHEMA,
                "policy": policy,
                "purpose": "paid" if policy == "P_MIX" else "shadow",
                "slate_id": capture.EXPECTED_SLATE_ID,
                "draft_group_id": capture.EXPECTED_DRAFT_GROUP_ID,
                "player_bridge": bridge_ref,
                "entries": book_entries[policy],
            }
        )
        publication = _publish_semantic(
            store,
            f"book-{policy}",
            book,
            created_at=BRIDGE_TIME,
            not_after=ALLOCATION_TIME,
        )
        book_refs[policy] = _ref(publication)
    return bridge_ref, book_refs, bridge


@dataclass
class Cohort:
    store: MemoryStore
    acquisition_authority: MemoryAcquisitionAuthority
    source_pins: capture.A5SourcePins
    pins: capture.A5CapturePins
    bridge_ref: dict[str, object]
    bridge: dict[str, object]
    book_refs: dict[str, dict[str, object]]
    manifests: dict[str, dict[str, object]]
    acceptances: dict[str, dict[str, object]]
    acceptance_values: dict[str, dict[str, object]]
    prepared: dict[str, dict[str, object]]
    evidence: dict[str, dict[str, object]]
    root: dict[str, object]
    root_ref: dict[str, object]


def _install_acceptance(
    store: MemoryStore,
    acquisition_authority: MemoryAcquisitionAuthority,
    pins: capture.A5CapturePins,
    manifest_ref: dict[str, object],
    pin: capture.ContestPin,
    paid_book: dict[str, object],
    bridge: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    k = pin.planned_entries
    permutation = list(range(k))
    if k >= 2:
        permutation[:2] = [1, 0]
    prepared_entries = []
    bridge_by_draftable = {
        item["dk_draftable_id"]: item for item in bridge["players"]
    }
    for export_ordinal, book_ordinal in enumerate(permutation):
        book = paid_book["entries"][book_ordinal]
        entry_id = str(int(pin.contest_id) * 1_000 + export_ordinal + 1)
        prepared_entries.append(
            {
                "export_ordinal": export_ordinal,
                "entry_id": entry_id,
                "internal_player_ids": sorted(
                    bridge_by_draftable[item]["dk_player_id"]
                    for item in book["slot_dk_draftable_ids"]
                ),
                "dk_draftable_ids": sorted(book["slot_dk_draftable_ids"]),
                "paid_input_book_ordinal": book_ordinal,
                "slot_dk_draftable_ids": book["slot_dk_draftable_ids"],
            }
        )
    filled_stream = io.StringIO(newline="")
    filled_writer = csv.writer(filled_stream)
    filled_writer.writerow(
        ["Entry ID", "Contest Name", "Contest ID", "Entry Fee"]
        + list(capture.CLASSIC_SLOTS)
    )
    for entry in prepared_entries:
        filled_writer.writerow(
            [
                entry["entry_id"],
                pin.name,
                pin.contest_id,
                f"${pin.entry_fee_micro // 1_000_000}",
            ]
            + [
                f"Player {draftable_id} ({draftable_id})"
                for draftable_id in entry["slot_dk_draftable_ids"]
            ]
        )
    filled = filled_stream.getvalue().encode()
    filled_identity = store.put_raw(
        f"filled-{pin.role}.csv", filled, created_at=PREPARED_UPLOAD_CREATED_AT
    )
    prepared = {
        "schema_version": "paid-entry-capture/v1",
        "contest_id": pin.contest_id,
        "draft_group_id": capture.EXPECTED_DRAFT_GROUP_ID,
        "salary_catalog_sha256": bridge["paid_catalog_sha256"],
        "csv_sha256": hashlib.sha256(filled).hexdigest(),
        "csv_bytes": len(filled),
        "paid_export_receipt_sha256": hashlib.sha256(b"export").hexdigest(),
        "entries": prepared_entries,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    prepared_identity = store.put_raw(
        f"prepared-{pin.role}.json",
        canonical_json_bytes(prepared),
        created_at=PREPARED_UPLOAD_CREATED_AT,
    )
    provider_observation_identity = store.put_raw(
        f"provider-active-entries-{pin.role}.csv",
        filled,
        created_at=ACCEPTANCE_RAW_ARCHIVED_AT,
    )
    acquisition_receipt = _issue_acquisition(
        store=store,
        authority=acquisition_authority,
        pin=pin,
        profile=capture.ACCEPTANCE_ACQUISITION_PROFILE,
        raw_identity=provider_observation_identity,
        observed_at=ACCEPTANCE_SOURCE_TIME,
        receipt_created_at=ACCEPTANCE_ACQUISITION_RECEIPT_TIME,
        suffix="accepted-entries",
    )
    provider_capture = capture.build_acceptance_provider_capture_v2(
        store=store,
        acquisition_authority=acquisition_authority,
        contest_role=pin.role,
        acquisition_receipt=acquisition_receipt,
        publish_by=ACCEPTANCE_CAPTURE_PUBLISH_BY,
    )
    provider_capture_publication = _publish_semantic(
        store,
        f"accepted-provider-capture-{pin.role}",
        provider_capture,
        created_at=ACCEPTANCE_CAPTURE_TIME,
        not_after=ACCEPTANCE_CAPTURE_PUBLISH_BY,
    )
    evidence = capture.build_accepted_entry_evidence_v2(
        store=store,
        acquisition_authority=acquisition_authority,
        provider_capture=_ref(provider_capture_publication),
        frozen_at=ACCEPTANCE_EVIDENCE_PUBLISH_BY,
    )
    evidence_publication = _publish_semantic(
        store,
        f"accepted-evidence-{pin.role}",
        evidence,
        created_at=ACCEPTANCE_EVIDENCE_TIME,
        not_after=ACCEPTANCE_EVIDENCE_PUBLISH_BY,
    )
    receipt = capture.build_week1_entry_acceptance_v2(
        store=store,
        acquisition_authority=acquisition_authority,
        pins=pins,
        manifest=manifest_ref,
        prepared_capture_identity=prepared_identity,
        filled_upload_identity=filled_identity,
        acceptance_evidence=_ref(evidence_publication),
        accepted_at=ACCEPTED_AT,
    )
    receipt_publication = _publish_semantic(
        store,
        f"acceptance-{pin.role}",
        receipt,
        created_at=ACCEPTANCE_RECEIPT_CREATED_AT,
        not_after=ACCEPTED_AT,
    )
    return _ref(receipt_publication), prepared, _ref(evidence_publication)


def _read_json_ref(store: MemoryStore, value: dict[str, object]) -> dict[str, object]:
    identity = value["artifact_identity"]
    return json.loads(store.read_exact(identity=identity)["raw"])


def _make_cohort(
    *,
    store: MemoryStore,
    acquisition_authority: MemoryAcquisitionAuthority,
    source_pins: capture.A5SourcePins,
) -> Cohort:
    bridge_ref, book_refs, bridge = _install_bridge_and_books(store)
    allocation = capture.build_week1_allocation_authority_v2(
        store=store,
        source_pins=source_pins,
        player_bridge=bridge_ref,
        books=book_refs,
        frozen_at=ALLOCATION_TIME,
    )
    allocation_publication = _publish_semantic(
        store,
        "allocation",
        allocation,
        created_at=ALLOCATION_CREATED_AT,
        not_after=ALLOCATION_TIME,
    )
    pins = capture.A5CapturePins(
        source=source_pins,
        allocation_identity=allocation_publication["artifact_identity"],
        allocation_semantic_sha256=str(allocation_publication["semantic_sha256"]),
    )
    manifests: dict[str, dict[str, object]] = {}
    for pin in capture.A5_ROLE_TABLE.values():
        manifest = capture.build_week1_prelock_manifest_v3(
            store=store,
            pins=pins,
            contest_role=pin.role,
            manifest_frozen_at=MANIFEST_TIME,
        )
        publication = _publish_semantic(
            store,
            f"manifest-{pin.role}",
            manifest,
            created_at=MANIFEST_CREATED_AT,
            not_after=MANIFEST_TIME,
        )
        manifests[pin.role] = _ref(publication)
    paid_book = _read_json_ref(store, book_refs["P_MIX"])
    acceptances: dict[str, dict[str, object]] = {}
    acceptance_values: dict[str, dict[str, object]] = {}
    prepared: dict[str, dict[str, object]] = {}
    evidence: dict[str, dict[str, object]] = {}
    for pin in capture.A5_ROLE_TABLE.values():
        acceptance_ref, prepared_value, evidence_ref = _install_acceptance(
            store,
            acquisition_authority,
            pins,
            manifests[pin.role],
            pin,
            paid_book,
            bridge,
        )
        acceptances[pin.role] = acceptance_ref
        acceptance_values[pin.role] = _read_json_ref(store, acceptance_ref)
        prepared[pin.role] = prepared_value
        evidence[pin.role] = evidence_ref
    root = capture.build_week1_acceptance_root_v2(
        store=store,
        acquisition_authority=acquisition_authority,
        pins=pins,
        manifests=manifests,
        acceptances=acceptances,
        frozen_at=ROOT_TIME,
    )
    root_publication = _publish_semantic(
        store,
        "acceptance-root",
        root,
        created_at=ROOT_CREATED_AT,
        not_after=ROOT_TIME,
    )
    return Cohort(
        store=store,
        acquisition_authority=acquisition_authority,
        source_pins=source_pins,
        pins=pins,
        bridge_ref=bridge_ref,
        bridge=bridge,
        book_refs=book_refs,
        manifests=manifests,
        acceptances=acceptances,
        acceptance_values=acceptance_values,
        prepared=prepared,
        evidence=evidence,
        root=root,
        root_ref=_ref(root_publication),
    )


@pytest.fixture(scope="module")
def cohort() -> Cohort:
    store = MemoryStore()
    acquisition_authority = MemoryAcquisitionAuthority()
    source_pins = _install_sources(store)
    patcher = pytest.MonkeyPatch()
    patcher.setattr(
        capture,
        "PINNED_SOURCE_MANIFEST_IDENTITY",
        source_pins.manifest_identity,
    )
    patcher.setattr(
        capture,
        "PINNED_CONTEST_SOURCE_IDENTITIES",
        source_pins.contest_identities,
    )
    patcher.setattr(
        capture,
        "TEMPLATE_PROJECTION_SEMANTIC_SHA256",
        source_pins.template_projection_semantic_sha256,
    )
    patcher.setattr(
        capture,
        "PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR",
        FIXTURE_ACCEPTANCE_DOWNLOAD_LOCATOR,
    )
    try:
        yield _make_cohort(
            store=store,
            acquisition_authority=acquisition_authority,
            source_pins=source_pins,
        )
    finally:
        patcher.undo()


def _standings_csv(
    cohort: Cohort,
    role: str,
    *,
    roster_drift: bool = False,
) -> bytes:
    accepted = cohort.acceptance_values[role]["realized_entry_lineup_bijection"]
    by_draftable = {
        player["dk_draftable_id"]: player for player in cohort.bridge["players"]
    }
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "Rank",
            "EntryId",
            "Points",
            "TimeRemaining",
            "Lineup",
            "Winnings",
            "Prize",
        ],
    )
    writer.writeheader()
    final_rosters = [list(item["slot_dk_draftable_ids"]) for item in accepted]
    if roster_drift and len(final_rosters) >= 2:
        final_rosters[:2] = [final_rosters[1], final_rosters[0]]
    pin = capture.A5_ROLE_TABLE[role]
    for ordinal, (entry, roster) in enumerate(
        zip(accepted, final_rosters, strict=True), start=1
    ):
        parts: list[str] = []
        for slot, draftable_id in zip(capture.CLASSIC_SLOTS, roster, strict=True):
            parts.extend([slot, str(by_draftable[draftable_id]["display_name"])])
        points = -1 if ordinal == len(accepted) else len(accepted) - ordinal + 1
        writer.writerow(
            {
                "Rank": ordinal,
                "EntryId": entry["entry_id"],
                "Points": points,
                "TimeRemaining": "0",
                "Lineup": " ".join(parts),
                "Winnings": (
                    f"${pin.advertised_prize_pool_micro // 1_000_000}.00"
                    if not pin.is_qualifier and ordinal == 1
                    else f"${pin.advertised_prize_pool_micro // 1_000_000 - 70_000}.00"
                    if pin.is_qualifier and ordinal == 2
                    else "$0.00"
                ),
                "Prize": (
                    capture.QUALIFIER_TICKET_NAMES[0]
                    if pin.is_qualifier and ordinal == 1
                    else ""
                ),
            }
        )
    return output.getvalue().encode()


def _normalized_ref(
    cohort: Cohort,
    role: str,
    *,
    displayed_size: int | None = None,
    evidence_contest_role: str | None = None,
    roster_drift: bool = False,
    suffix: str = "normal",
) -> dict[str, object]:
    raw = _standings_csv(cohort, role, roster_drift=roster_drift)
    raw_identity = cohort.store.put_raw(
        f"standings-{role}-{suffix}.csv",
        raw,
        created_at=SETTLEMENT_SOURCE_ARCHIVED_AT,
    )
    evidence_pin = capture.A5_ROLE_TABLE[evidence_contest_role or role]
    size = displayed_size
    if size is None:
        size = len(cohort.acceptance_values[role]["realized_entry_lineup_bijection"])
    provider_source = {
        "errorStatus": {},
        "contestDetail": {
            "contestKey": evidence_pin.contest_id,
            "draftGroupId": int(capture.EXPECTED_DRAFT_GROUP_ID),
            "contestState": "Completed",
            "contestStateDetail": "Final",
            "entries": size,
        },
    }
    provider_source_identity = cohort.store.put_raw(
        f"final-field-provider-{role}-{suffix}.json",
        canonical_json_bytes(provider_source),
        created_at=SETTLEMENT_SOURCE_ARCHIVED_AT,
    )
    provider_acquisition = _issue_acquisition(
        store=cohort.store,
        authority=cohort.acquisition_authority,
        pin=evidence_pin,
        profile=capture.CONTEST_DETAIL_ACQUISITION_PROFILE,
        raw_identity=provider_source_identity,
        observed_at=SETTLEMENT_SOURCE_TIME,
        receipt_created_at=SETTLEMENT_ACQUISITION_RECEIPT_TIME,
        suffix=f"contest-detail-{suffix}",
    )
    standings_acquisition = _issue_acquisition(
        store=cohort.store,
        authority=cohort.acquisition_authority,
        pin=evidence_pin,
        profile=capture.STANDINGS_ACQUISITION_PROFILE,
        raw_identity=raw_identity,
        observed_at=SETTLEMENT_SOURCE_TIME,
        receipt_created_at=SETTLEMENT_ACQUISITION_RECEIPT_TIME,
        suffix=f"standings-{suffix}",
    )
    provider_capture = capture.build_final_field_provider_capture_v2(
        store=cohort.store,
        acquisition_authority=cohort.acquisition_authority,
        contest_role=evidence_pin.role,
        provider_acquisition_receipt=provider_acquisition,
        standings_acquisition_receipt=standings_acquisition,
        publish_by=FINAL_FIELD_CAPTURE_PUBLISH_BY,
    )
    provider_capture_publication = _publish_semantic(
        cohort.store,
        f"final-field-provider-capture-{role}-{suffix}",
        provider_capture,
        created_at=FINAL_FIELD_CAPTURE_TIME,
        not_after=FINAL_FIELD_CAPTURE_PUBLISH_BY,
        not_before=capture.EXPECTED_LOCK_UTC,
    )
    evidence = capture.build_final_field_evidence_v2(
        store=cohort.store,
        acquisition_authority=cohort.acquisition_authority,
        provider_capture=_ref(provider_capture_publication),
        frozen_at=FINAL_FIELD_EVIDENCE_TIME,
    )
    evidence_publication = _publish_semantic(
        cohort.store,
        f"final-field-evidence-{role}-{suffix}",
        evidence,
        created_at=FINAL_FIELD_EVIDENCE_CREATED_AT,
        not_after=FINAL_FIELD_EVIDENCE_TIME,
        not_before=capture.EXPECTED_LOCK_UTC,
    )
    normalized = capture.build_normalized_standings_v2(
        store=cohort.store,
        acquisition_authority=cohort.acquisition_authority,
        final_field_evidence=_ref(evidence_publication),
        player_bridge=cohort.bridge_ref,
        frozen_at=SETTLEMENT_TIME,
    )
    publication = _publish_semantic(
        cohort.store,
        f"normalized-{role}-{suffix}",
        normalized,
        created_at=NORMALIZED_FIELD_CREATED_AT,
        not_after=SETTLEMENT_TIME,
        not_before=capture.EXPECTED_LOCK_UTC,
    )
    return _ref(publication)


def test_live_capture_remains_hold_without_real_lobby_and_allocation_pins() -> None:
    with pytest.raises(
        capture.Week1A5CaptureContractError, match="allocation raw/semantic identity"
    ):
        capture.live_capture_pins()
    pins = capture.pinned_source_pins()
    assert pins.template_projection_identity is None


def test_real_shape_smoke_is_default_off_before_opening_a_file(tmp_path) -> None:
    missing = tmp_path / "must-not-be-opened.csv"
    with pytest.raises(SystemExit) as exc:
        shape_smoke_cli.main(
            [
                "--phase",
                "prelock-acceptance",
                "--contest-role",
                "milly-5",
                "--acceptance-source",
                str(missing),
            ]
        )
    assert exc.value.code == 2


def test_semantic_hash_and_raw_object_hash_are_distinct_and_both_verify(
    cohort: Cohort,
) -> None:
    evidence_ref = cohort.evidence["milly-5"]
    identity = evidence_ref["artifact_identity"]
    assert identity["sha256"] != evidence_ref["semantic_sha256"]
    raw = cohort.store.read_exact(identity=identity)["raw"]
    parsed = json.loads(raw)
    assert parsed["semantic_sha256"] == evidence_ref["semantic_sha256"]
    assert hashlib.sha256(raw).hexdigest() == identity["sha256"]
    capture.validate_week1_entry_acceptance_v2(
        cohort.acceptance_values["milly-5"],
        store=cohort.store,
        acquisition_authority=cohort.acquisition_authority,
        pins=cohort.pins,
    )


def test_acceptance_rows_rebuild_from_separately_archived_provider_export(
    cohort: Cohort,
) -> None:
    role = "milly-5"
    evidence = _read_json_ref(cohort.store, cohort.evidence[role])
    provider = _read_json_ref(cohort.store, evidence["provider_capture"])
    receipt = cohort.acceptance_values[role]
    assert evidence["raw_observation_identity"] == provider["raw_observation_identity"]
    assert evidence["raw_observation_identity"] != receipt["filled_upload_identity"]
    assert provider["capture_method"] == capture.ACCEPTANCE_CAPTURE_METHOD
    assert provider["observed_entry_count"] == capture.EXPECTED_ROLE_ENTRIES[role]
    capture.validate_accepted_entry_evidence_v2(
        evidence,
        store=cohort.store,
        acquisition_authority=cohort.acquisition_authority,
    )


def test_copied_upload_without_authority_receipt_cannot_become_accepted(
    cohort: Cohort,
) -> None:
    role = "milly-5"
    pin = capture.A5_ROLE_TABLE[role]
    filled_identity = cohort.acceptance_values[role]["filled_upload_identity"]
    copied_raw = cohort.store.read_exact(identity=filled_identity)["raw"]
    copied_identity = cohort.store.put_raw(
        "copied-unsubmitted-upload-as-provider.csv",
        copied_raw,
        created_at=ACCEPTANCE_RAW_ARCHIVED_AT,
    )
    unissued_receipt = _issue_acquisition(
        store=cohort.store,
        authority=cohort.acquisition_authority,
        pin=pin,
        profile=capture.ACCEPTANCE_ACQUISITION_PROFILE,
        raw_identity=copied_identity,
        observed_at=ACCEPTANCE_SOURCE_TIME,
        receipt_created_at=ACCEPTANCE_ACQUISITION_RECEIPT_TIME,
        suffix="copied-upload-unissued",
        register=False,
    )
    with pytest.raises(
        capture.Week1A5CaptureContractError,
        match="not recognized by the authority",
    ):
        capture.build_acceptance_provider_capture_v2(
            store=cohort.store,
            acquisition_authority=cohort.acquisition_authority,
            contest_role=role,
            acquisition_receipt=unissued_receipt,
            publish_by=ACCEPTANCE_CAPTURE_PUBLISH_BY,
        )


@pytest.mark.parametrize(
    "artifact_identity_field",
    ["prepared_capture_identity", "filled_upload_identity"],
)
def test_prepared_and_filled_uploads_must_exist_before_provider_observation(
    cohort: Cohort,
    artifact_identity_field: str,
) -> None:
    cloned = copy.deepcopy(cohort)
    receipt = cloned.acceptance_values["milly-5"]
    identity = receipt[artifact_identity_field]
    key = (str(identity["uri"]), str(identity["generation"]))
    cloned.store.objects[key]["created_at"] = "2026-09-13T15:00:01Z"
    with pytest.raises(
        capture.Week1A5CaptureContractError,
        match="must predate the provider acceptance observation",
    ):
        capture.validate_week1_entry_acceptance_v2(
            receipt,
            store=cloned.store,
            acquisition_authority=cloned.acquisition_authority,
            pins=cloned.pins,
        )


def test_absent_live_acceptance_download_locator_fails_closed(
    cohort: Cohort,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = _read_json_ref(cohort.store, cohort.evidence["milly-5"])
    provider = _read_json_ref(cohort.store, evidence["provider_capture"])
    monkeypatch.setattr(capture, "PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR", None)
    with pytest.raises(
        capture.Week1A5CaptureContractError,
        match="live acceptance acquisition locator is not pinned",
    ):
        capture.validate_acceptance_provider_capture_v2(
            provider,
            store=cohort.store,
            acquisition_authority=cohort.acquisition_authority,
        )


def test_fabricated_normalized_acceptance_cannot_borrow_raw_provider_capture(
    cohort: Cohort,
) -> None:
    evidence = _read_json_ref(cohort.store, cohort.evidence["milly-5"])
    evidence["entries"][0]["entry_id"] = "999999999999999"
    evidence.pop("semantic_sha256")
    fabricated = capture.seal_semantic_artifact(evidence)
    with pytest.raises(
        capture.Week1A5CaptureContractError,
        match="differs from exact provider observation",
    ):
        capture.validate_accepted_entry_evidence_v2(
            fabricated,
            store=cohort.store,
            acquisition_authority=cohort.acquisition_authority,
        )


def test_acceptance_provider_observation_must_precede_raw_archive_creation(
    cohort: Cohort,
) -> None:
    evidence = _read_json_ref(cohort.store, cohort.evidence["milly-5"])
    provider = _read_json_ref(cohort.store, evidence["provider_capture"])
    cloned_store = copy.deepcopy(cohort.store)
    identity = provider["raw_observation_identity"]
    key = (str(identity["uri"]), str(identity["generation"]))
    cloned_store.objects[key]["created_at"] = "2026-09-13T14:59:59Z"
    with pytest.raises(
        capture.Week1A5CaptureContractError,
        match="archives predate the authenticated observation",
    ):
        capture.validate_acceptance_provider_capture_v2(
            provider,
            store=cloned_store,
            acquisition_authority=cohort.acquisition_authority,
        )


def test_acceptance_capture_must_publish_by_prospective_cutoff(
    cohort: Cohort,
) -> None:
    evidence = _read_json_ref(cohort.store, cohort.evidence["milly-5"])
    cloned_store = copy.deepcopy(cohort.store)
    identity = evidence["provider_capture"]["artifact_identity"]
    key = (str(identity["uri"]), str(identity["generation"]))
    cloned_store.objects[key]["created_at"] = "2026-09-13T15:15:01Z"
    with pytest.raises(
        capture.Week1A5CaptureContractError,
        match="published after its cutoff",
    ):
        capture.validate_accepted_entry_evidence_v2(
            evidence,
            store=cloned_store,
            acquisition_authority=cohort.acquisition_authority,
        )


def test_reverse_min_churn_permutation_is_a_valid_realized_bijection(
    cohort: Cohort,
) -> None:
    receipt = cohort.acceptance_values["championship-qualifier-18"]
    edges = receipt["realized_entry_lineup_bijection"]
    assert [(item["entry_index"], item["lineup_rank"]) for item in edges[:2]] == [
        (1, 2),
        (2, 1),
    ]
    assert cohort.root["accepted_entry_count"] == 90


def test_duplicate_or_missing_realized_rank_fails_against_exact_prepared_bytes(
    cohort: Cohort,
) -> None:
    fabricated = copy.deepcopy(
        cohort.acceptance_values["championship-qualifier-18"]
    )
    fabricated["realized_entry_lineup_bijection"][0]["lineup_rank"] = 1
    fabricated.pop("semantic_sha256")
    fabricated = capture.seal_semantic_artifact(fabricated)
    with pytest.raises(
        capture.Week1A5CaptureContractError, match="exact raw evidence projection"
    ):
        capture.validate_week1_entry_acceptance_v2(
            fabricated,
            store=cohort.store,
            acquisition_authority=cohort.acquisition_authority,
            pins=cohort.pins,
        )


def test_fabricated_projection_cannot_borrow_honest_raw_acceptance_identity(
    cohort: Cohort,
) -> None:
    fabricated = copy.deepcopy(cohort.acceptance_values["milly-5"])
    first, second = fabricated["realized_entry_lineup_bijection"][:2]
    first["entry_id"], second["entry_id"] = second["entry_id"], first["entry_id"]
    fabricated.pop("semantic_sha256")
    fabricated = capture.seal_semantic_artifact(fabricated)
    with pytest.raises(
        capture.Week1A5CaptureContractError, match="exact raw evidence projection"
    ):
        capture.validate_week1_entry_acceptance_v2(
            fabricated,
            store=cohort.store,
            acquisition_authority=cohort.acquisition_authority,
            pins=cohort.pins,
        )


@pytest.mark.parametrize("field", ["generation", "bytes", "sha256"])
def test_fabricated_allocation_raw_identity_fails_exact_reopen(
    cohort: Cohort, field: str
) -> None:
    identity = dict(cohort.pins.allocation_identity)
    identity[field] = (
        "999999"
        if field == "generation"
        else int(identity[field]) + 1
        if field == "bytes"
        else "0" * 64
    )
    pins = capture.A5CapturePins(
        source=cohort.source_pins,
        allocation_identity=identity,
        allocation_semantic_sha256=cohort.pins.allocation_semantic_sha256,
    )
    with pytest.raises(
        capture.Week1A5CaptureContractError,
        match="exact reopen|reopened identity",
    ):
        capture.build_week1_prelock_manifest_v3(
            store=cohort.store,
            pins=pins,
            contest_role="milly-5",
            manifest_frozen_at=MANIFEST_TIME,
        )


def test_alternate_allocation_semantic_root_fails_even_with_genuine_raw_object(
    cohort: Cohort,
) -> None:
    pins = capture.A5CapturePins(
        source=cohort.source_pins,
        allocation_identity=cohort.pins.allocation_identity,
        allocation_semantic_sha256="0" * 64,
    )
    with pytest.raises(capture.Week1A5CaptureContractError, match="semantic root"):
        capture.build_week1_prelock_manifest_v3(
            store=cohort.store,
            pins=pins,
            contest_role="milly-5",
            manifest_frozen_at=MANIFEST_TIME,
        )


def test_alternate_terminal_source_identity_fails_before_fact_parsing(
    cohort: Cohort,
) -> None:
    manifest_identity = dict(cohort.source_pins.manifest_identity)
    manifest_identity["bytes"] = int(manifest_identity["bytes"]) + 1
    source_pins = capture.A5SourcePins(
        manifest_identity=manifest_identity,
        contest_identities=cohort.source_pins.contest_identities,
        template_projection_identity=cohort.source_pins.template_projection_identity,
        template_projection_semantic_sha256=(
            cohort.source_pins.template_projection_semantic_sha256
        ),
    )
    with pytest.raises(capture.Week1A5CaptureContractError, match="exact pinned identity"):
        capture.load_pinned_contest_sources(cohort.store, source_pins)


def test_provider_creation_after_lock_invalidates_prelock_acceptance(
    cohort: Cohort,
) -> None:
    cloned = copy.deepcopy(cohort)
    receipt = cloned.acceptance_values["milly-5"]
    identity = receipt["prepared_capture_identity"]
    key = (str(identity["uri"]), str(identity["generation"]))
    cloned.store.objects[key]["created_at"] = "2026-09-13T18:00:00Z"
    with pytest.raises(
        capture.Week1A5CaptureContractError, match="provider creation time"
    ):
        capture.validate_week1_entry_acceptance_v2(
            receipt,
            store=cloned.store,
            acquisition_authority=cloned.acquisition_authority,
            pins=cloned.pins,
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("contest_id", "999999999"),
        ("contest_name", "Fabricated contest"),
        ("draft_group_id", "999999"),
        ("lock_utc", "2026-09-13T18:00:00Z"),
        ("entry_fee_micro", 6_000_000),
        ("advertised_field_capacity", 832_343),
        ("entry_limit", 149),
        ("advertised_prize_pool_micro", 1),
        ("template_id", "999999"),
        ("is_qualifier", True),
        ("qualifier_ticket_destinations", ["Fabricated Ticket"]),
    ],
)
def test_allocation_contest_facts_cannot_be_self_consistently_rewritten(
    cohort: Cohort, field: str, replacement: object
) -> None:
    allocation = json.loads(
        cohort.store.read_exact(identity=cohort.pins.allocation_identity)["raw"]
    )
    allocation["contests"][0][field] = replacement
    allocation.pop("semantic_sha256")
    allocation = capture.seal_semantic_artifact(allocation)
    with pytest.raises(
        capture.Week1A5CaptureContractError,
        match="source/book-derived authority",
    ):
        capture.validate_week1_allocation_authority_v2(
            allocation, store=cohort.store, source_pins=cohort.source_pins
        )


def test_book_identity_cannot_be_paired_with_fabricated_inline_roster(
    cohort: Cohort,
) -> None:
    book = _read_json_ref(cohort.store, cohort.book_refs["P_MIX"])
    book["entries"][0]["lineup_id"] = book["entries"][1]["lineup_id"]
    book.pop("semantic_sha256")
    book = capture.seal_semantic_artifact(book)
    with pytest.raises(capture.Week1A5CaptureContractError, match="lineup_id"):
        capture._validate_book(book, bridge=cohort.bridge)


def test_tie_cent_remainder_is_exact_not_field_sized_tolerance() -> None:
    rows = [
        {
            "entry_id": "1",
            "rank": 1,
            "points_micropoints": 1,
            "cash_payout_micro": 10_000,
            "ticket_destinations": [],
        },
        {
            "entry_id": "2",
            "rank": 1,
            "points_micropoints": 1,
            "cash_payout_micro": 20_000,
            "ticket_destinations": [],
        },
    ]
    ladder = [
        {
            "rank_start": 1,
            "rank_end": 1,
            "kind": "cash",
            "cash_micro": 20_000,
            "ticket_destinations": [],
            "quantity": 1,
        },
        {
            "rank_start": 2,
            "rank_end": 2,
            "kind": "cash",
            "cash_micro": 10_000,
            "ticket_destinations": [],
            "quantity": 1,
        },
    ]
    result = capture._reconcile_source_payouts(rows, ladder)
    assert result["tie_remainder_cents"] == 1
    wrong = copy.deepcopy(rows)
    wrong[0]["cash_payout_micro"] = 0
    with pytest.raises(capture.Week1A5CaptureContractError, match="tie-cent law"):
        capture._reconcile_source_payouts(wrong, ladder)


def test_truncated_raw_field_cannot_masquerade_as_source_backed_underfill(
    cohort: Cohort,
) -> None:
    with pytest.raises(
        capture.Week1A5CaptureContractError,
        match="standings count differs.*final submitted count",
    ):
        _normalized_ref(
            cohort,
            "milly-5",
            displayed_size=58,
            suffix="truncated",
        )


def test_old_false_n_wrapper_is_not_an_authoritative_provider_source(
    cohort: Cohort,
) -> None:
    pin = capture.A5_ROLE_TABLE["milly-5"]
    false_wrapper = canonical_json_bytes(
        {
            "schema_version": capture.FINAL_FIELD_SOURCE_SCHEMA,
            "captured_at": SETTLEMENT_SOURCE_TIME,
            "endpoint": f"https://www.draftkings.com/contest/gamecenter/{pin.contest_id}",
            "source": {
                "contest_id": pin.contest_id,
                "draft_group_id": capture.EXPECTED_DRAFT_GROUP_ID,
                "contest_state": "Settled",
                "displayed_final_field_size": pin.planned_entries,
            },
        }
    )
    with pytest.raises(
        capture.Week1A5CaptureContractError,
        match="source wrappers are retired",
    ):
        capture._parse_final_field_provider_body(false_wrapper)


def test_caller_authored_false_n_and_matching_prefix_lack_provider_authority(
    cohort: Cohort,
) -> None:
    role = "championship-qualifier-18"
    pin = capture.A5_ROLE_TABLE[role]
    standings_raw = _standings_csv(cohort, role)
    standings_identity = cohort.store.put_raw(
        "false-n-matching-prefix.csv",
        standings_raw,
        created_at=SETTLEMENT_SOURCE_ARCHIVED_AT,
    )
    false_provider_body = canonical_json_bytes(
        {
            "errorStatus": {},
            "contestDetail": {
                "contestKey": pin.contest_id,
                "draftGroupId": int(capture.EXPECTED_DRAFT_GROUP_ID),
                "contestState": "Completed",
                "contestStateDetail": "Final",
                "entries": pin.planned_entries,
            },
        }
    )
    false_provider_identity = cohort.store.put_raw(
        "caller-authored-false-n.json",
        false_provider_body,
        created_at=SETTLEMENT_SOURCE_ARCHIVED_AT,
    )
    unissued_provider_receipt = _issue_acquisition(
        store=cohort.store,
        authority=cohort.acquisition_authority,
        pin=pin,
        profile=capture.CONTEST_DETAIL_ACQUISITION_PROFILE,
        raw_identity=false_provider_identity,
        observed_at=SETTLEMENT_SOURCE_TIME,
        receipt_created_at=SETTLEMENT_ACQUISITION_RECEIPT_TIME,
        suffix="false-n-unissued",
        register=False,
    )
    issued_standings_receipt = _issue_acquisition(
        store=cohort.store,
        authority=cohort.acquisition_authority,
        pin=pin,
        profile=capture.STANDINGS_ACQUISITION_PROFILE,
        raw_identity=standings_identity,
        observed_at=SETTLEMENT_SOURCE_TIME,
        receipt_created_at=SETTLEMENT_ACQUISITION_RECEIPT_TIME,
        suffix="false-n-matching-prefix-issued",
    )
    with pytest.raises(
        capture.Week1A5CaptureContractError,
        match="not recognized by the authority",
    ):
        capture.build_final_field_provider_capture_v2(
            store=cohort.store,
            acquisition_authority=cohort.acquisition_authority,
            contest_role=role,
            provider_acquisition_receipt=unissued_provider_receipt,
            standings_acquisition_receipt=issued_standings_receipt,
            publish_by=FINAL_FIELD_CAPTURE_PUBLISH_BY,
        )


def test_final_field_sources_require_separate_authority_events(
    cohort: Cohort,
) -> None:
    role = "championship-qualifier-18"
    pin = capture.A5_ROLE_TABLE[role]
    standings_identity = cohort.store.put_raw(
        "same-event-standings.csv",
        _standings_csv(cohort, role),
        created_at=SETTLEMENT_SOURCE_ARCHIVED_AT,
    )
    provider_identity = cohort.store.put_raw(
        "same-event-contest-detail.json",
        canonical_json_bytes(
            {
                "errorStatus": {},
                "contestDetail": {
                    "contestKey": pin.contest_id,
                    "draftGroupId": int(capture.EXPECTED_DRAFT_GROUP_ID),
                    "contestState": "Completed",
                    "contestStateDetail": "Final",
                    "entries": pin.planned_entries,
                },
            }
        ),
        created_at=SETTLEMENT_SOURCE_ARCHIVED_AT,
    )
    shared_event = f"fixture-{pin.contest_id}-incorrect-shared-event"
    provider_receipt = _issue_acquisition(
        store=cohort.store,
        authority=cohort.acquisition_authority,
        pin=pin,
        profile=capture.CONTEST_DETAIL_ACQUISITION_PROFILE,
        raw_identity=provider_identity,
        observed_at=SETTLEMENT_SOURCE_TIME,
        receipt_created_at=SETTLEMENT_ACQUISITION_RECEIPT_TIME,
        suffix="same-event-provider",
        authority_event_id=shared_event,
    )
    standings_receipt = _issue_acquisition(
        store=cohort.store,
        authority=cohort.acquisition_authority,
        pin=pin,
        profile=capture.STANDINGS_ACQUISITION_PROFILE,
        raw_identity=standings_identity,
        observed_at=SETTLEMENT_SOURCE_TIME,
        receipt_created_at=SETTLEMENT_ACQUISITION_RECEIPT_TIME,
        suffix="same-event-standings",
        authority_event_id=shared_event,
    )
    with pytest.raises(
        capture.Week1A5CaptureContractError,
        match="do not have separate authority events",
    ):
        capture.build_final_field_provider_capture_v2(
            store=cohort.store,
            acquisition_authority=cohort.acquisition_authority,
            contest_role=role,
            provider_acquisition_receipt=provider_receipt,
            standings_acquisition_receipt=standings_receipt,
            publish_by=FINAL_FIELD_CAPTURE_PUBLISH_BY,
        )


def test_matching_false_n_projection_cannot_borrow_exact_provider_body(
    cohort: Cohort,
) -> None:
    role = "championship-qualifier-18"
    normalized_ref = _normalized_ref(cohort, role, suffix="false-n-projection")
    normalized = _read_json_ref(cohort.store, normalized_ref)
    evidence = _read_json_ref(cohort.store, normalized["final_field_evidence"])
    evidence["displayed_final_field_size"] -= 1
    evidence.pop("semantic_sha256")
    fabricated = capture.seal_semantic_artifact(evidence)
    with pytest.raises(
        capture.Week1A5CaptureContractError,
        match="differs from exact raw-source projection",
    ):
        capture.validate_final_field_evidence_v2(
            fabricated,
            store=cohort.store,
            acquisition_authority=cohort.acquisition_authority,
        )


def test_shape_smokes_are_redacted_and_write_free(cohort: Cohort) -> None:
    role = "championship-qualifier-18"
    evidence = _read_json_ref(cohort.store, cohort.evidence[role])
    accepted_raw = cohort.store.read_exact(
        identity=evidence["raw_observation_identity"]
    )["raw"]
    accepted_smoke = capture.inspect_acceptance_provider_bytes_v1(
        accepted_raw,
        contest_role=role,
    )
    assert accepted_smoke["entry_count"] == 3
    assert accepted_smoke["writes_performed"] is False
    assert "entries" not in accepted_smoke

    standings_raw = _standings_csv(cohort, role)
    provider_raw = canonical_json_bytes(
        {
            "errorStatus": {},
            "contestDetail": {
                "contestKey": capture.A5_ROLE_TABLE[role].contest_id,
                "draftGroupId": int(capture.EXPECTED_DRAFT_GROUP_ID),
                "contestState": "Completed",
                "contestStateDetail": "Final",
                "entries": 3,
            },
        }
    )
    final_smoke = capture.inspect_final_field_provider_bytes_v1(
        provider_raw,
        standings_raw,
        contest_role=role,
    )
    assert final_smoke["provider_final_entry_count"] == 3
    assert final_smoke["writes_performed"] is False
    assert "rows" not in final_smoke


def test_cross_wired_complete_field_cannot_settle_another_contest(
    cohort: Cohort,
) -> None:
    normalized_ref = _normalized_ref(
        cohort,
        "milly-5",
        evidence_contest_role="large-20max-3",
        suffix="cross-wired",
    )
    with pytest.raises(capture.Week1A5CaptureContractError, match="omits an accepted"):
        capture.build_week1_settlement_v2(
            store=cohort.store,
            acquisition_authority=cohort.acquisition_authority,
            pins=cohort.pins,
            acceptance_root=cohort.root_ref,
            normalized_standings=normalized_ref,
            settlement_frozen_at="2026-09-14T22:00:00Z",
        )


def test_final_roster_drift_fails_without_frozen_late_swap_transition(
    cohort: Cohort,
) -> None:
    normalized_ref = _normalized_ref(
        cohort, "milly-5", roster_drift=True, suffix="roster-drift"
    )
    with pytest.raises(capture.Week1A5CaptureContractError, match="roster drift"):
        capture.build_week1_settlement_v2(
            store=cohort.store,
            acquisition_authority=cohort.acquisition_authority,
            pins=cohort.pins,
            acceptance_root=cohort.root_ref,
            normalized_standings=normalized_ref,
            settlement_frozen_at="2026-09-14T22:00:00Z",
        )


def test_source_backed_qualifier_ticket_and_negative_score_settle(
    cohort: Cohort,
) -> None:
    role = "championship-qualifier-18"
    normalized_ref = _normalized_ref(cohort, role, suffix="ticket-negative")
    settlement = capture.build_week1_settlement_v2(
        store=cohort.store,
        acquisition_authority=cohort.acquisition_authority,
        pins=cohort.pins,
        acceptance_root=cohort.root_ref,
        normalized_standings=normalized_ref,
        settlement_frozen_at="2026-09-14T22:00:00Z",
    )
    assert settlement["payout_reconciliation"]["expected_ticket_quantity"] == 1
    assert settlement["payout_reconciliation"]["reconciled"] is True
    assert min(item["points_micropoints"] for item in settlement["paid_results"]) < 0
