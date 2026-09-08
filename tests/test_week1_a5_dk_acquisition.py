"""Adversarial tests for the governed Week-1 DraftKings source authority."""

from __future__ import annotations

import copy
import csv
import hashlib
import inspect
import io
import json
from dataclasses import dataclass

import pytest

from nfl_dfs.inference.generation_exposure import canonical_json_bytes
from nfl_dfs.ingest import week1_a5_capture_contracts as capture
from nfl_dfs.ingest import week1_a5_dk_acquisition as acquisition

FIXTURE_LOCATOR = "https://fixture.draftkings.invalid/account/active.csv"
OBSERVED_AT = "2026-09-13T15:00:00Z"
CREATED_AT = "2026-09-13T15:02:00Z"
EVENT_ID = "dk-a5-20260913T150000Z-0123456789abcdef0123456789abcdef"


class MemoryStore:
    def __init__(self, *, now: str = CREATED_AT) -> None:
        self.now = now
        self.next_generation = 1
        self.objects: dict[tuple[str, str], dict[str, object]] = {}

    def publish_create_once(
        self, *, uri: str, raw: bytes, content_type: str
    ) -> dict[str, object]:
        del content_type
        if any(existing_uri == uri for existing_uri, _ in self.objects):
            raise ValueError("create-once collision")
        generation = str(self.next_generation)
        self.next_generation += 1
        identity = {
            "uri": uri,
            "generation": generation,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        value = {
            "identity": identity,
            "created_at": self.now,
            "raw": raw,
        }
        self.objects[(uri, generation)] = value
        return {"identity": copy.deepcopy(identity), "created_at": self.now}

    def read_exact(self, *, identity: dict[str, object]) -> dict[str, object]:
        key = (str(identity["uri"]), str(identity["generation"]))
        if key not in self.objects:
            raise ValueError("unknown exact generation")
        return copy.deepcopy(self.objects[key])


class MemoryLedgerReader:
    def __init__(
        self,
        store: MemoryStore,
        governance: acquisition.CollectorGovernance,
    ) -> None:
        self.store = store
        self._governance = governance

    def governance(self) -> dict[str, object]:
        return self._governance.as_dict()

    def read_single_generation(self, *, uri: str) -> dict[str, object]:
        matches = [
            value
            for (stored_uri, _), value in self.store.objects.items()
            if stored_uri == uri
        ]
        if len(matches) != 1:
            raise ValueError("ledger URI does not have one generation")
        return copy.deepcopy(matches[0])


@dataclass
class FixedTransport:
    event: acquisition.TransportEvent
    calls: list[tuple[str, str]]

    def perform(self, *, method: str, locator: str) -> acquisition.TransportEvent:
        self.calls.append((method, locator))
        return self.event


def _governance() -> acquisition.CollectorGovernance:
    return acquisition.CollectorGovernance(
        authority_bucket_metageneration="7",
        retention_seconds=31_536_000,
        retention_locked=True,
        versioning_enabled=True,
        uniform_bucket_level_access=True,
        object_creator_members=(
            "serviceAccount:dk-capture@nfl-predictions-503414.iam.gserviceaccount.com",
        ),
        object_viewer_members=(
            "serviceAccount:dk-capture@nfl-predictions-503414.iam.gserviceaccount.com",
            "serviceAccount:dk-reader@nfl-predictions-503414.iam.gserviceaccount.com",
        ),
        public_members=(),
    )


def _policy() -> acquisition.CollectorAllowlist:
    fixture_family = acquisition.LocatorFamily(
        "https", "fixture.draftkings.invalid", "/account/"
    )
    standings_family = acquisition.LocatorFamily(
        "https", "www.draftkings.com", "/contest/exportfullstandingscsv/"
    )
    return acquisition._build_allowlist(
        source_commit="a" * 40,
        code_sha256=acquisition._module_sha256(),
        image_digest=f"sha256:{'b' * 64}",
        collector_service_account=(
            "dk-capture@nfl-predictions-503414.iam.gserviceaccount.com"
        ),
        authority_reader_service_account=(
            "dk-reader@nfl-predictions-503414.iam.gserviceaccount.com"
        ),
        governance=_governance(),
        acceptance_effective_families=(fixture_family,),
        standings_effective_families=(standings_family,),
    )


def _active_entry_csv(role: str = "milly-5") -> bytes:
    pin = capture.A5_ROLE_TABLE[role]
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        ["Entry ID", "Contest Name", "Contest ID", "Entry Fee"]
        + list(capture.CLASSIC_SLOTS)
    )
    for ordinal in range(pin.planned_entries):
        base = ordinal * 20 + 1
        draftables = [base + offset for offset in range(9)]
        writer.writerow(
            [
                str(int(pin.contest_id) * 1_000 + ordinal + 1),
                pin.name,
                pin.contest_id,
                f"${pin.entry_fee_micro // 1_000_000}",
            ]
            + [f"Player {value} ({value})" for value in draftables]
        )
    return output.getvalue().encode()


def _transport(raw: bytes | None = None) -> FixedTransport:
    return FixedTransport(
        event=acquisition.TransportEvent(
            body=raw or _active_entry_csv(),
            observed_at=OBSERVED_AT,
            hops=(
                acquisition.TransportHop(
                    locator=FIXTURE_LOCATOR,
                    status=200,
                    redirect_target=None,
                ),
            ),
            response_content_type="text/csv; charset=utf-8",
            response_content_disposition='attachment; filename="entries.csv"',
            session_profile=acquisition.COLLECTOR_SESSION_PROFILE,
        ),
        calls=[],
    )


@dataclass
class IssuedFixture:
    evidence: MemoryStore
    ledger: MemoryStore
    policy: acquisition.CollectorAllowlist
    authority: acquisition.ProductionDraftKingsAcquisitionAuthority
    issuance: acquisition.CollectorIssuance
    transport: FixedTransport


@pytest.fixture
def issued(monkeypatch: pytest.MonkeyPatch) -> IssuedFixture:
    monkeypatch.setattr(capture, "PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR", FIXTURE_LOCATOR)
    evidence = MemoryStore()
    ledger = MemoryStore(now="2026-09-13T15:03:00Z")
    policy = _policy()
    transport = _transport()
    issuance = acquisition._collect_with_reviewed_ports(
        policy=policy,
        evidence_store=evidence,
        ledger_writer=ledger,
        transport=transport,
        profile=capture.ACCEPTANCE_ACQUISITION_PROFILE,
        contest_role="milly-5",
        authority_event_id=EVENT_ID,
    )
    authority = acquisition._authority_from_reviewed_ports(
        policy=policy,
        evidence=evidence,
        ledger=MemoryLedgerReader(ledger, policy.governance),
    )
    return IssuedFixture(evidence, ledger, policy, authority, issuance, transport)


def _replace_ledger_event(
    issued: IssuedFixture,
    mutate: object,
) -> None:
    identity = issued.issuance.ledger_identity
    key = (str(identity["uri"]), str(identity["generation"]))
    stored = issued.ledger.objects[key]
    event = json.loads(stored["raw"])
    event.pop("semantic_sha256")
    mutate(event)
    sealed = capture.seal_semantic_artifact(event)
    raw = canonical_json_bytes(sealed)
    new_identity = {
        **identity,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    stored["identity"] = new_identity
    stored["raw"] = raw


def test_collector_derives_and_issues_exact_transport_event(
    issued: IssuedFixture,
) -> None:
    assert issued.transport.calls == [("GET", FIXTURE_LOCATOR)]
    authenticated = issued.authority.read_authenticated_acquisition(
        identity=issued.issuance.acquisition_receipt["artifact_identity"]
    )
    assert authenticated["authority_event_id"] == EVENT_ID
    receipt = json.loads(authenticated["raw"])
    assert receipt["response_content_type"] == "text/csv; charset=utf-8"
    assert receipt["response_content_disposition"] == (
        'attachment; filename="entries.csv"'
    )
    assert receipt["collector_source_commit"] == issued.policy.source_commit
    assert receipt["collector_image_digest"] == issued.policy.image_digest
    assert issued.issuance.redacted_transport["effective_locator"] == {
        "redacted_locator": FIXTURE_LOCATOR,
        "locator_sha256": hashlib.sha256(FIXTURE_LOCATOR.encode()).hexdigest(),
        "query_parameter_names": [],
    }


def test_authority_is_read_only_and_not_caller_constructible(
    issued: IssuedFixture,
) -> None:
    assert not hasattr(issued.authority, "register")
    assert not hasattr(issued.authority, "publish")
    with pytest.raises(
        acquisition.Week1A5DraftKingsAcquisitionError,
        match="not caller-constructible",
    ):
        acquisition.ProductionDraftKingsAcquisitionAuthority(
            token=object(),
            evidence=issued.evidence,
            ledger=MemoryLedgerReader(issued.ledger, issued.policy.governance),
            policy=issued.policy,
        )


def test_live_publishers_have_no_authority_or_store_injection_surface() -> None:
    for function in (
        acquisition.publish_live_acceptance_provider_capture_v2,
        acquisition.publish_live_final_field_provider_capture_v2,
    ):
        parameters = inspect.signature(function).parameters
        assert "acquisition_authority" not in parameters
        assert "authority" not in parameters
        assert "store" not in parameters
        assert "uri" not in parameters

    class MirrorAuthority:
        def read_authenticated_acquisition(
            self, *, identity: dict[str, object]
        ) -> dict[str, object]:
            return {"identity": identity}

    with pytest.raises(TypeError):
        acquisition.publish_live_acceptance_provider_capture_v2(
            contest_role="milly-5",
            acquisition_receipt={},
            publish_by="2026-09-13T16:00:00Z",
            execute_live_publication=True,
            acquisition_authority=MirrorAuthority(),  # type: ignore[call-arg]
        )


def test_live_surfaces_fail_before_client_or_transport_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contacted = False

    def contact(_: str) -> object:
        nonlocal contacted
        contacted = True
        raise AssertionError("provider client must not be constructed")

    monkeypatch.setattr(acquisition, "_google_storage_client", contact)
    with pytest.raises(
        acquisition.Week1A5DraftKingsAcquisitionError,
        match="default-off",
    ):
        acquisition.run_live_authenticated_acquisition(
            acquisition_profile=capture.ACCEPTANCE_ACQUISITION_PROFILE,
            contest_role="milly-5",
        )
    with pytest.raises(
        acquisition.Week1A5DraftKingsAcquisitionError,
        match="remains HOLD",
    ):
        acquisition.run_live_authenticated_acquisition(
            acquisition_profile=capture.ACCEPTANCE_ACQUISITION_PROFILE,
            contest_role="milly-5",
            execute_live_acquisition=True,
        )
    with pytest.raises(
        acquisition.Week1A5DraftKingsAcquisitionError,
        match="remains HOLD",
    ):
        acquisition.publish_live_acceptance_provider_capture_v2(
            contest_role="milly-5",
            acquisition_receipt={},
            publish_by="2026-09-13T16:00:00Z",
            execute_live_publication=True,
        )
    with pytest.raises(
        acquisition.Week1A5DraftKingsAcquisitionError,
        match="remains HOLD",
    ):
        acquisition.publish_live_final_field_provider_capture_v2(
            contest_role="milly-5",
            provider_acquisition_receipt={},
            standings_acquisition_receipt={},
            publish_by="2026-09-16T00:00:00Z",
            execute_live_publication=True,
        )
    assert contacted is False


def test_unknown_receipt_generation_and_copied_upload_are_not_issued(
    issued: IssuedFixture,
) -> None:
    honest = issued.issuance.acquisition_receipt["artifact_identity"]
    copied_raw = issued.evidence.read_exact(identity=honest)["raw"]
    copied = issued.evidence.publish_create_once(
        uri=(
            f"gs://{issued.policy.evidence_bucket}/{issued.policy.evidence_prefix}/"
            "copied-filled-upload/acquisition-receipt.json"
        ),
        raw=copied_raw,
        content_type="application/json",
    )["identity"]
    with pytest.raises((ValueError, acquisition.Week1A5DraftKingsAcquisitionError)):
        issued.authority.read_authenticated_acquisition(identity=copied)
    unknown = {**honest, "generation": str(int(str(honest["generation"])) + 1000)}
    with pytest.raises((ValueError, acquisition.Week1A5DraftKingsAcquisitionError)):
        issued.authority.read_authenticated_acquisition(identity=unknown)


def test_unapproved_collector_image_fails_before_capture_publication(
    issued: IssuedFixture,
) -> None:
    _replace_ledger_event(
        issued,
        lambda event: event.__setitem__("collector_image_digest", f"sha256:{'f' * 64}"),
    )
    with pytest.raises(
        acquisition.Week1A5DraftKingsAcquisitionError, match="identity differs"
    ):
        issued.authority.read_authenticated_acquisition(
            identity=issued.issuance.acquisition_receipt["artifact_identity"]
        )
    before = len(issued.evidence.objects)
    with pytest.raises(capture.Week1A5CaptureContractError, match="not recognized"):
        capture.build_acceptance_provider_capture_v2(
            store=issued.evidence,
            acquisition_authority=issued.authority,
            contest_role="milly-5",
            acquisition_receipt=issued.issuance.acquisition_receipt,
            publish_by="2026-09-13T15:30:00Z",
        )
    assert len(issued.evidence.objects) == before


def test_recognized_event_cross_wired_role_contest_fails_before_publication(
    issued: IssuedFixture,
) -> None:
    _replace_ledger_event(
        issued,
        lambda event: event.__setitem__(
            "contest_id", capture.A5_ROLE_TABLE["large-20max-3"].contest_id
        ),
    )
    with pytest.raises(
        acquisition.Week1A5DraftKingsAcquisitionError, match="cross-wired"
    ):
        issued.authority.read_authenticated_acquisition(
            identity=issued.issuance.acquisition_receipt["artifact_identity"]
        )
    before = len(issued.evidence.objects)
    with pytest.raises(capture.Week1A5CaptureContractError, match="not recognized"):
        capture.build_acceptance_provider_capture_v2(
            store=issued.evidence,
            acquisition_authority=issued.authority,
            contest_role="milly-5",
            acquisition_receipt=issued.issuance.acquisition_receipt,
            publish_by="2026-09-13T15:30:00Z",
        )
    assert len(issued.evidence.objects) == before


def test_tampered_raw_or_trace_cannot_be_recognized(issued: IssuedFixture) -> None:
    receipt_identity = issued.issuance.acquisition_receipt["artifact_identity"]
    receipt = json.loads(issued.evidence.read_exact(identity=receipt_identity)["raw"])
    raw_identity = receipt["raw_object_identity"]
    raw_key = (str(raw_identity["uri"]), str(raw_identity["generation"]))
    issued.evidence.objects[raw_key]["raw"] = b"substituted bytes"
    with pytest.raises(
        acquisition.Week1A5DraftKingsAcquisitionError,
        match="exact read changed bytes",
    ):
        issued.authority.read_authenticated_acquisition(identity=receipt_identity)


def test_tampered_transport_trace_cannot_be_recognized(issued: IssuedFixture) -> None:
    receipt_identity = issued.issuance.acquisition_receipt["artifact_identity"]
    receipt = json.loads(issued.evidence.read_exact(identity=receipt_identity)["raw"])
    trace_identity = receipt["transport_trace_identity"]
    trace_key = (str(trace_identity["uri"]), str(trace_identity["generation"]))
    issued.evidence.objects[trace_key]["raw"] = b"{}"
    with pytest.raises(
        acquisition.Week1A5DraftKingsAcquisitionError,
        match="exact read changed bytes",
    ):
        issued.authority.read_authenticated_acquisition(identity=receipt_identity)


def test_ledger_redirect_projection_is_exactly_validated(issued: IssuedFixture) -> None:
    def mutate(event: dict[str, object]) -> None:
        transport = event["transport_event"]
        assert isinstance(transport, dict)
        chain = transport["redirect_chain"]
        assert isinstance(chain, list)
        hop = chain[0]
        assert isinstance(hop, dict)
        hop["unreviewed_field"] = "forged"

    _replace_ledger_event(issued, mutate)
    with pytest.raises(
        acquisition.Week1A5DraftKingsAcquisitionError,
        match="fields differ",
    ):
        issued.authority.read_authenticated_acquisition(
            identity=issued.issuance.acquisition_receipt["artifact_identity"]
        )


def test_self_authored_matching_final_n_cannot_enter_authority(
    issued: IssuedFixture,
) -> None:
    honest_identity = issued.issuance.acquisition_receipt["artifact_identity"]
    honest = json.loads(issued.evidence.read_exact(identity=honest_identity)["raw"])
    honest.pop("semantic_sha256")
    pin = capture.A5_ROLE_TABLE["milly-5"]
    honest.update(
        {
            "authority_event_id": (
                "dk-a5-20260914T200000Z-fedcba9876543210fedcba9876543210"
            ),
            "acquisition_profile": capture.CONTEST_DETAIL_ACQUISITION_PROFILE,
            "canonical_locator": (
                f"{capture.FINAL_FIELD_SOURCE_LOCATOR_PREFIX}{pin.contest_id}"
            ),
            "observed_at": "2026-09-14T20:00:00Z",
            "response_content_type": "application/json",
            "response_content_disposition": None,
        }
    )
    forged = capture.seal_semantic_artifact(honest)
    publication = capture.publish_semantic_artifact(
        issued.evidence,
        uri=(
            f"gs://{issued.policy.evidence_bucket}/{issued.policy.evidence_prefix}/"
            "self-authored-final-n/acquisition-receipt.json"
        ),
        artifact=forged,
    )
    with pytest.raises((ValueError, acquisition.Week1A5DraftKingsAcquisitionError)):
        issued.authority.read_authenticated_acquisition(
            identity=publication["artifact_identity"]
        )


def test_redirect_chain_and_locator_family_are_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(capture, "PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR", FIXTURE_LOCATOR)
    policy = _policy()
    event = acquisition.TransportEvent(
        body=_active_entry_csv(),
        observed_at=OBSERVED_AT,
        hops=(
            acquisition.TransportHop(FIXTURE_LOCATOR, 302, "/account/final.csv"),
            acquisition.TransportHop(
                "https://evil.invalid/account/final.csv", 200, None
            ),
        ),
        response_content_type="text/csv",
        response_content_disposition='attachment; filename="entries.csv"',
        session_profile=acquisition.COLLECTOR_SESSION_PROFILE,
    )
    with pytest.raises(
        acquisition.Week1A5DraftKingsAcquisitionError,
        match="discontinuous|family allowlist",
    ):
        acquisition._collect_with_reviewed_ports(
            policy=policy,
            evidence_store=MemoryStore(),
            ledger_writer=MemoryStore(),
            transport=FixedTransport(event, []),
            profile=capture.ACCEPTANCE_ACQUISITION_PROFILE,
            contest_role="milly-5",
            authority_event_id=EVENT_ID,
        )


def test_governance_change_invalidates_previously_issued_event(
    issued: IssuedFixture,
) -> None:
    weakened = acquisition.CollectorGovernance(
        **{
            **issued.policy.governance.__dict__,
            "public_members": ("allAuthenticatedUsers",),
        }
    )
    authority = acquisition._authority_from_reviewed_ports(
        policy=issued.policy,
        evidence=issued.evidence,
        ledger=MemoryLedgerReader(issued.ledger, weakened),
    )
    with pytest.raises(
        acquisition.Week1A5DraftKingsAcquisitionError,
        match="public access",
    ):
        authority.read_authenticated_acquisition(
            identity=issued.issuance.acquisition_receipt["artifact_identity"]
        )
