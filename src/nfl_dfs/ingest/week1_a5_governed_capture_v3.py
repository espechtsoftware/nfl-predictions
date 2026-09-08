"""Ledger-bound successor contracts for governed Week-1 A5 capture.

The frozen v2 capture contracts prove the provider bytes and the acquisition
receipt, but do not carry the root-last issuance-ledger generation into the
derived artifact.  This additive v3 layer keeps those contracts intact while
making the exact ledger identity and provider creation time durable.  Every
downstream build reopens the authority, compares the retained ledger record,
and proves that the stored provider capture was created only after the ledger.

This module is evidence-only.  It does not contact DraftKings, publish an
artifact, score a lineup, or mutate production state.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, Protocol

from nfl_dfs.ingest import week1_a5_capture_contracts as legacy

ACCEPTANCE_PROVIDER_CAPTURE_SCHEMA: Final = (
    "dk-accepted-entry-provider-capture/v3"
)
ACCEPTED_EVIDENCE_SCHEMA: Final = "dk-accepted-entry-evidence/v3"
FINAL_FIELD_PROVIDER_CAPTURE_SCHEMA: Final = (
    "dk-final-field-provider-capture/v3"
)
FINAL_FIELD_EVIDENCE_SCHEMA: Final = "dk-final-field-evidence/v3"

_AUTHORITY_READ_FIELDS = {
    "identity",
    "created_at",
    "raw",
    "authority_event_id",
    "authority_ledger_identity",
    "authority_ledger_created_at",
    "authority_ledger_publish_by",
}
_LEDGER_RECORD_FIELDS = {
    "authority_event_id",
    "identity",
    "provider_created_at",
    "publish_by",
}


class LedgerBoundProviderAcquisitionAuthority(Protocol):
    """Authority that returns the exact root-last ledger it authenticated."""

    def read_authenticated_acquisition(
        self, *, identity: Mapping[str, object]
    ) -> Mapping[str, object]: ...

    def read_authenticated_acquisition_with_ledger(
        self, *, identity: Mapping[str, object]
    ) -> Mapping[str, object]: ...


def _authority_ledger_record(
    *,
    store: legacy.ImmutableObjectStore,
    acquisition_authority: LedgerBoundProviderAcquisitionAuthority,
    acquisition_receipt: object,
    expected_event_id: object,
    publish_by: object,
    phase: str,
    label: str,
) -> dict[str, object]:
    """Reopen one receipt and return its authenticated durable ledger edge."""

    publish_text, cutoff = legacy._publish_by(
        publish_by,
        label=f"{label} publish_by",
        phase=phase,
    )
    reference = legacy._semantic_ref(
        acquisition_receipt, label=f"{label} acquisition receipt"
    )
    receipt = legacy._reopen_exact(
        store,
        reference["artifact_identity"],
        label=f"{label} acquisition receipt",
        not_after=cutoff,
    )
    try:
        authority_read = legacy._mapping(
            acquisition_authority.read_authenticated_acquisition_with_ledger(
                identity=receipt.identity
            ),
            label=f"{label} ledger-bound authority read",
        )
    except Exception as exc:
        if isinstance(exc, legacy.Week1A5CaptureContractError):
            raise
        raise legacy.Week1A5CaptureContractError(
            f"{label} is not recognized by the ledger-bound authority"
        ) from exc
    legacy._exact(
        authority_read,
        _AUTHORITY_READ_FIELDS,
        label=f"{label} ledger-bound authority read",
    )
    legacy._identity_equal(
        authority_read["identity"],
        receipt.identity,
        label=f"{label} authority-issued receipt identity",
    )
    authority_created_at, _ = legacy._timestamp(
        authority_read["created_at"],
        label=f"{label} authority receipt creation time",
    )
    if authority_created_at != receipt.created_at:
        legacy._fail(f"{label} authority receipt creation time differs")
    authority_raw = authority_read["raw"]
    if not isinstance(authority_raw, bytes) or authority_raw != receipt.raw:
        legacy._fail(f"{label} authority receipt bytes differ")
    event_id = legacy._authority_event(
        authority_read["authority_event_id"],
        label=f"{label} authority event ID",
    )
    expected = legacy._authority_event(
        expected_event_id,
        label=f"{label} expected authority event ID",
    )
    if event_id != expected:
        legacy._fail(f"{label} authority event differs")
    ledger_identity = legacy._identity(
        authority_read["authority_ledger_identity"],
        label=f"{label} authority ledger identity",
    )
    ledger_created_at, ledger_created = legacy._timestamp(
        authority_read["authority_ledger_created_at"],
        label=f"{label} authority ledger creation time",
    )
    ledger_publish_by, _ = legacy._publish_by(
        authority_read["authority_ledger_publish_by"],
        label=f"{label} authority ledger publish_by",
        phase=phase,
    )
    if ledger_publish_by != publish_text:
        legacy._fail(f"{label} authority ledger uses another cutoff")
    if ledger_created < receipt.created:
        legacy._fail(f"{label} authority ledger predates its receipt")
    if ledger_created > cutoff:
        legacy._fail(f"{label} authority ledger is after its cutoff")
    return {
        "authority_event_id": event_id,
        "identity": ledger_identity,
        "provider_created_at": ledger_created_at,
        "publish_by": ledger_publish_by,
    }


def _validate_ledger_record(
    value: object,
    *,
    expected_event_id: object,
    publish_by: object,
    phase: str,
    label: str,
) -> dict[str, object]:
    row = legacy._mapping(value, label=label)
    legacy._exact(row, _LEDGER_RECORD_FIELDS, label=label)
    event_id = legacy._authority_event(
        row["authority_event_id"], label=f"{label} authority event ID"
    )
    expected = legacy._authority_event(
        expected_event_id, label=f"{label} expected authority event ID"
    )
    if event_id != expected:
        legacy._fail(f"{label} authority event differs")
    publish_text, _ = legacy._publish_by(
        publish_by, label=f"{label} parent publish_by", phase=phase
    )
    ledger_publish_by, _ = legacy._publish_by(
        row["publish_by"], label=f"{label} publish_by", phase=phase
    )
    if ledger_publish_by != publish_text:
        legacy._fail(f"{label} cutoff differs from its provider capture")
    return {
        "authority_event_id": event_id,
        "identity": legacy._identity(row["identity"], label=f"{label} identity"),
        "provider_created_at": legacy._timestamp(
            row["provider_created_at"], label=f"{label} provider creation time"
        )[0],
        "publish_by": ledger_publish_by,
    }


def _assert_ledger_precedes_capture(
    record: object,
    *,
    capture_created: object,
    expected_event_id: object,
    publish_by: object,
    phase: str,
    label: str,
) -> dict[str, object]:
    retained = _validate_ledger_record(
        record,
        expected_event_id=expected_event_id,
        publish_by=publish_by,
        phase=phase,
        label=label,
    )
    _, ledger_created = legacy._timestamp(
        retained["provider_created_at"], label=f"{label} provider creation time"
    )
    _, derived_created = legacy._timestamp(
        capture_created, label="stored provider-capture creation time"
    )
    if ledger_created > derived_created:
        legacy._fail("stored provider capture predates an authority ledger")
    return retained


def build_acceptance_provider_capture_v3(
    *,
    store: legacy.ImmutableObjectStore,
    acquisition_authority: LedgerBoundProviderAcquisitionAuthority,
    contest_role: object,
    acquisition_receipt: object,
    publish_by: object,
) -> dict[str, object]:
    """Bind one active-entry acquisition and its exact issuance ledger."""

    base = legacy.build_acceptance_provider_capture_v2(
        store=store,
        acquisition_authority=acquisition_authority,
        contest_role=contest_role,
        acquisition_receipt=acquisition_receipt,
        publish_by=publish_by,
    )
    ledger = _authority_ledger_record(
        store=store,
        acquisition_authority=acquisition_authority,
        acquisition_receipt=acquisition_receipt,
        expected_event_id=base["acquisition_authority_event_id"],
        publish_by=base["publish_by"],
        phase="prelock",
        label="acceptance acquisition",
    )
    body = dict(base)
    body.pop("semantic_sha256")
    body["schema_version"] = ACCEPTANCE_PROVIDER_CAPTURE_SCHEMA
    body["authority_ledger"] = ledger
    return legacy.seal_semantic_artifact(body)


def validate_acceptance_provider_capture_v3(
    value: object,
    *,
    store: legacy.ImmutableObjectStore,
    acquisition_authority: LedgerBoundProviderAcquisitionAuthority,
) -> dict[str, object]:
    row = legacy.validate_semantic_artifact(
        value, label="acceptance provider capture v3"
    )
    legacy._exact(
        row,
        {
            "schema_version",
            "source_system",
            "capture_method",
            "source_locator",
            "contest_role",
            "contest_id",
            "draft_group_id",
            "observed_at",
            "publish_by",
            "acquisition_receipt",
            "acquisition_authority_event_id",
            "authority_ledger",
            "raw_observation_identity",
            "observed_entry_count",
            "entry_projection_sha256",
            "semantic_sha256",
        },
        label="acceptance provider capture v3",
    )
    if row["schema_version"] != ACCEPTANCE_PROVIDER_CAPTURE_SCHEMA:
        legacy._fail("acceptance provider capture v3 schema differs")
    rebuilt = build_acceptance_provider_capture_v3(
        store=store,
        acquisition_authority=acquisition_authority,
        contest_role=row["contest_role"],
        acquisition_receipt=row["acquisition_receipt"],
        publish_by=row["publish_by"],
    )
    if row != rebuilt:
        legacy._fail("acceptance provider capture differs from durable authority")
    return row


def build_accepted_entry_evidence_v3(
    *,
    store: legacy.ImmutableObjectStore,
    acquisition_authority: LedgerBoundProviderAcquisitionAuthority,
    provider_capture: object,
    frozen_at: object,
) -> dict[str, object]:
    """Derive accepted entries after proving ledger-before-capture order."""

    frozen_text, frozen = legacy._publish_by(
        frozen_at, label="accepted-entry evidence v3 frozen_at", phase="prelock"
    )
    capture_ref = legacy._semantic_ref(
        provider_capture, label="acceptance provider capture v3"
    )
    capture_raw, capture_obj = legacy._reopen_semantic(
        store,
        capture_ref["artifact_identity"],
        label="acceptance provider capture v3",
        expected_semantic_sha256=capture_ref["semantic_sha256"],
        not_after=frozen,
    )
    provider = validate_acceptance_provider_capture_v3(
        capture_raw,
        store=store,
        acquisition_authority=acquisition_authority,
    )
    provider_cutoff = legacy._publish_by(
        provider["publish_by"],
        label="acceptance provider capture v3 publish_by",
        phase="prelock",
    )[1]
    if capture_obj.created > provider_cutoff:
        legacy._fail("acceptance provider capture was published after its cutoff")
    if provider_cutoff > frozen:
        legacy._fail("acceptance provider capture cutoff is after evidence cutoff")
    _assert_ledger_precedes_capture(
        provider["authority_ledger"],
        capture_created=capture_obj.created_at,
        expected_event_id=provider["acquisition_authority_event_id"],
        publish_by=provider["publish_by"],
        phase="prelock",
        label="acceptance authority ledger",
    )
    raw_obj = legacy._reopen_exact(
        store,
        provider["raw_observation_identity"],
        label="raw accepted-entry provider observation",
        not_after=provider_cutoff,
    )
    if capture_obj.created < raw_obj.created:
        legacy._fail("acceptance provider capture predates its raw archive")
    pin = legacy._pin_for_role(provider["contest_role"])
    entries = legacy._parse_active_entry_export(raw_obj.raw, pin=pin)
    return legacy.seal_semantic_artifact(
        {
            "schema_version": ACCEPTED_EVIDENCE_SCHEMA,
            "complete": True,
            "observed_at": provider["observed_at"],
            "frozen_at": frozen_text,
            "contest_role": pin.role,
            "contest_id": pin.contest_id,
            "draft_group_id": legacy.EXPECTED_DRAFT_GROUP_ID,
            "provider_capture": capture_ref,
            "raw_observation_identity": raw_obj.identity,
            "entries": entries,
        }
    )


def validate_accepted_entry_evidence_v3(
    value: object,
    *,
    store: legacy.ImmutableObjectStore,
    acquisition_authority: LedgerBoundProviderAcquisitionAuthority,
) -> dict[str, object]:
    row = legacy.validate_semantic_artifact(value, label="accepted-entry evidence v3")
    legacy._exact(
        row,
        {
            "schema_version",
            "complete",
            "observed_at",
            "frozen_at",
            "contest_role",
            "contest_id",
            "draft_group_id",
            "provider_capture",
            "raw_observation_identity",
            "entries",
            "semantic_sha256",
        },
        label="accepted-entry evidence v3",
    )
    if row["schema_version"] != ACCEPTED_EVIDENCE_SCHEMA:
        legacy._fail("accepted-entry evidence v3 schema differs")
    rebuilt = build_accepted_entry_evidence_v3(
        store=store,
        acquisition_authority=acquisition_authority,
        provider_capture=row["provider_capture"],
        frozen_at=row["frozen_at"],
    )
    if row != rebuilt:
        legacy._fail("accepted-entry evidence differs from exact provider capture")
    return row


def build_final_field_provider_capture_v3(
    *,
    store: legacy.ImmutableObjectStore,
    acquisition_authority: LedgerBoundProviderAcquisitionAuthority,
    contest_role: object,
    provider_acquisition_receipt: object,
    standings_acquisition_receipt: object,
    publish_by: object,
) -> dict[str, object]:
    """Bind both settled-field acquisitions and their separate ledgers."""

    base = legacy.build_final_field_provider_capture_v2(
        store=store,
        acquisition_authority=acquisition_authority,
        contest_role=contest_role,
        provider_acquisition_receipt=provider_acquisition_receipt,
        standings_acquisition_receipt=standings_acquisition_receipt,
        publish_by=publish_by,
    )
    provider_ledger = _authority_ledger_record(
        store=store,
        acquisition_authority=acquisition_authority,
        acquisition_receipt=provider_acquisition_receipt,
        expected_event_id=base["provider_authority_event_id"],
        publish_by=base["publish_by"],
        phase="postlock",
        label="contest-detail acquisition",
    )
    standings_ledger = _authority_ledger_record(
        store=store,
        acquisition_authority=acquisition_authority,
        acquisition_receipt=standings_acquisition_receipt,
        expected_event_id=base["standings_authority_event_id"],
        publish_by=base["publish_by"],
        phase="postlock",
        label="standings acquisition",
    )
    if provider_ledger["identity"] == standings_ledger["identity"]:
        legacy._fail("final-field acquisitions share one authority ledger")
    body = dict(base)
    body.pop("semantic_sha256")
    body["schema_version"] = FINAL_FIELD_PROVIDER_CAPTURE_SCHEMA
    body["provider_authority_ledger"] = provider_ledger
    body["standings_authority_ledger"] = standings_ledger
    return legacy.seal_semantic_artifact(body)


def validate_final_field_provider_capture_v3(
    value: object,
    *,
    store: legacy.ImmutableObjectStore,
    acquisition_authority: LedgerBoundProviderAcquisitionAuthority,
) -> dict[str, object]:
    row = legacy.validate_semantic_artifact(
        value, label="final-field provider capture v3"
    )
    legacy._exact(
        row,
        {
            "schema_version",
            "source_system",
            "capture_method",
            "source_locator",
            "contest_role",
            "contest_id",
            "draft_group_id",
            "provider_observed_at",
            "standings_observed_at",
            "publish_by",
            "provider_acquisition_receipt",
            "standings_acquisition_receipt",
            "provider_authority_event_id",
            "standings_authority_event_id",
            "provider_authority_ledger",
            "standings_authority_ledger",
            "raw_provider_body_identity",
            "raw_standings_identity",
            "provider_contest_state",
            "provider_contest_state_detail",
            "provider_final_entry_count",
            "parsed_standings_entry_count",
            "semantic_sha256",
        },
        label="final-field provider capture v3",
    )
    if row["schema_version"] != FINAL_FIELD_PROVIDER_CAPTURE_SCHEMA:
        legacy._fail("final-field provider capture v3 schema differs")
    rebuilt = build_final_field_provider_capture_v3(
        store=store,
        acquisition_authority=acquisition_authority,
        contest_role=row["contest_role"],
        provider_acquisition_receipt=row["provider_acquisition_receipt"],
        standings_acquisition_receipt=row["standings_acquisition_receipt"],
        publish_by=row["publish_by"],
    )
    if row != rebuilt:
        legacy._fail("final-field provider capture differs from durable authority")
    return row


def build_final_field_evidence_v3(
    *,
    store: legacy.ImmutableObjectStore,
    acquisition_authority: LedgerBoundProviderAcquisitionAuthority,
    provider_capture: object,
    frozen_at: object,
) -> dict[str, object]:
    """Derive the settled field after proving both ledger-order edges."""

    frozen_text, frozen = legacy._publish_by(
        frozen_at, label="final-field evidence v3 frozen_at", phase="postlock"
    )
    _, lock = legacy._timestamp(legacy.EXPECTED_LOCK_UTC, label="A5 lock")
    capture_ref = legacy._semantic_ref(
        provider_capture, label="final-field provider capture v3"
    )
    capture_raw, capture_obj = legacy._reopen_semantic(
        store,
        capture_ref["artifact_identity"],
        label="final-field provider capture v3",
        expected_semantic_sha256=capture_ref["semantic_sha256"],
        not_after=frozen,
        not_before=lock,
    )
    provider = validate_final_field_provider_capture_v3(
        capture_raw,
        store=store,
        acquisition_authority=acquisition_authority,
    )
    capture_cutoff = legacy._publish_by(
        provider["publish_by"],
        label="final-field provider capture v3 publish_by",
        phase="postlock",
    )[1]
    if capture_obj.created > capture_cutoff:
        legacy._fail("final-field provider capture was published after its cutoff")
    if capture_cutoff > frozen:
        legacy._fail("final-field provider capture cutoff is after evidence cutoff")
    _assert_ledger_precedes_capture(
        provider["provider_authority_ledger"],
        capture_created=capture_obj.created_at,
        expected_event_id=provider["provider_authority_event_id"],
        publish_by=provider["publish_by"],
        phase="postlock",
        label="contest-detail authority ledger",
    )
    _assert_ledger_precedes_capture(
        provider["standings_authority_ledger"],
        capture_created=capture_obj.created_at,
        expected_event_id=provider["standings_authority_event_id"],
        publish_by=provider["publish_by"],
        phase="postlock",
        label="standings authority ledger",
    )
    provider_obj = legacy._reopen_exact(
        store,
        provider["raw_provider_body_identity"],
        label="raw final-field provider response",
        not_after=capture_cutoff,
        not_before=lock,
    )
    standings_obj = legacy._reopen_exact(
        store,
        provider["raw_standings_identity"],
        label="raw complete standings",
        not_after=capture_cutoff,
        not_before=lock,
    )
    if capture_obj.created < max(provider_obj.created, standings_obj.created):
        legacy._fail("final-field provider capture predates one of its raw archives")
    return legacy.seal_semantic_artifact(
        {
            "schema_version": FINAL_FIELD_EVIDENCE_SCHEMA,
            "contest_id": provider["contest_id"],
            "draft_group_id": provider["draft_group_id"],
            "settled": True,
            "provider_contest_state": provider["provider_contest_state"],
            "provider_contest_state_detail": provider[
                "provider_contest_state_detail"
            ],
            "displayed_final_field_size": provider["provider_final_entry_count"],
            "captured_at": provider["provider_observed_at"],
            "standings_captured_at": provider["standings_observed_at"],
            "frozen_at": frozen_text,
            "provider_capture": capture_ref,
            "provider_source_identity": provider_obj.identity,
            "raw_standings_identity": standings_obj.identity,
        }
    )


def validate_final_field_evidence_v3(
    value: object,
    *,
    store: legacy.ImmutableObjectStore,
    acquisition_authority: LedgerBoundProviderAcquisitionAuthority,
) -> dict[str, object]:
    row = legacy.validate_semantic_artifact(value, label="final-field evidence v3")
    legacy._exact(
        row,
        {
            "schema_version",
            "contest_id",
            "draft_group_id",
            "settled",
            "provider_contest_state",
            "provider_contest_state_detail",
            "displayed_final_field_size",
            "captured_at",
            "standings_captured_at",
            "frozen_at",
            "provider_capture",
            "provider_source_identity",
            "raw_standings_identity",
            "semantic_sha256",
        },
        label="final-field evidence v3",
    )
    if row["schema_version"] != FINAL_FIELD_EVIDENCE_SCHEMA:
        legacy._fail("final-field evidence v3 schema differs")
    rebuilt = build_final_field_evidence_v3(
        store=store,
        acquisition_authority=acquisition_authority,
        provider_capture=row["provider_capture"],
        frozen_at=row["frozen_at"],
    )
    if row != rebuilt:
        legacy._fail("final-field evidence differs from exact provider capture")
    return row


__all__ = [
    "ACCEPTANCE_PROVIDER_CAPTURE_SCHEMA",
    "ACCEPTED_EVIDENCE_SCHEMA",
    "FINAL_FIELD_EVIDENCE_SCHEMA",
    "FINAL_FIELD_PROVIDER_CAPTURE_SCHEMA",
    "LedgerBoundProviderAcquisitionAuthority",
    "build_acceptance_provider_capture_v3",
    "build_accepted_entry_evidence_v3",
    "build_final_field_evidence_v3",
    "build_final_field_provider_capture_v3",
    "validate_acceptance_provider_capture_v3",
    "validate_accepted_entry_evidence_v3",
    "validate_final_field_evidence_v3",
    "validate_final_field_provider_capture_v3",
]
