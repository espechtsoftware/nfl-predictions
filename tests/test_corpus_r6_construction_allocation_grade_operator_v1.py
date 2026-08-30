from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.research import (
    corpus_r6_construction_allocation_grade_operator_v1 as subject,
)
from nfl_dfs.research import corpus_r6_construction_allocation_cross_operator_v1 as selection_operator
from nfl_dfs.research import corpus_r6_construction_allocation_cross_v1 as cross
from nfl_dfs.research import corpus_r6_construction_allocation_grade_v1 as grade_science


CODE_SHA = "a" * 40
IMAGE = "us-central1-docker.pkg.dev/fixture/repo/image@sha256:" + "b" * 64
OUTPUT_PREFIX = "gs://fixture/grades"
OUTCOME_COMPLETION_URI = (
    subject.RECOGNIZED_OUTCOME_NAMESPACE
    + "fixture-catalog-outcomes-v1/completion.json"
)


def _identity(uri: str, raw: bytes, generation: str = "17", *, create: bool = False):
    result = {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    if create:
        result["create_once"] = True
    return result


class _Store:
    def __init__(self) -> None:
        self.rows: dict[str, tuple[str, bytes]] = {}
        self.writes: list[str] = []

    def prime(self, identity, raw: bytes) -> None:
        self.rows[str(identity["uri"])] = (str(identity["generation"]), raw)

    def read(self, identity) -> bytes:
        generation, raw = self.rows[str(identity["uri"])]
        assert generation == str(identity["generation"])
        return raw

    def publish(self, uri: str, raw: bytes):
        assert uri not in self.rows
        generation = str(1000 + len(self.writes))
        identity = _identity(uri, raw, generation, create=True)
        self.rows[uri] = (generation, raw)
        self.writes.append(uri)
        return identity


class _Lease:
    def __init__(self) -> None:
        self.calls = 0
        authority = _outcome_authority()
        self.active = {
            "body": authority.lease_body,
            "object_receipt": authority.lease_identity,
        }

    def __call__(self, *, expected_identity, catalog_run_id):
        assert expected_identity == self.active["object_receipt"]
        assert catalog_run_id == self.active["body"]["run_id"]
        self.calls += 1
        return self.active


def _selection_envelope() -> dict[str, object]:
    terminal_raw = b'{"fixture":"selection-terminal"}'
    body = {
        "schema_version": selection_operator.TERMINAL_ENVELOPE_SCHEMA,
        "terminal_identity": _identity(
            "gs://fixture/selection/terminal.json", terminal_raw, create=True
        ),
        "complete": True,
        "create_once": True,
        "uses_target_slate_outcomes": False,
    }
    return {**body, "envelope_sha256": subject._hash(body)}


def _fake_selection_reopen(envelope, *, read_exact):
    del read_exact
    if envelope["terminal_identity"]["uri"] != "gs://fixture/selection/terminal.json":
        raise ValueError("forged selection terminal")
    return {
        "selection": {
            "receipt_sha256": "c" * 64,
            "scientific_sha256": "d" * 64,
            "slates": [{
                "season": 2023,
                "week": 1,
                "slate_id": "2023-w01",
            }],
        },
        "upstream_reopen_receipt": {"receipt_sha256": "e" * 64},
        "complete": True,
        "outcome_data_accessed": False,
    }


def _outcome_authority() -> subject.OpenedOutcomeAuthorityV1:
    lease_body = {
        "version": "historical-outcome-active-v1",
        "run_id": "fixture-catalog-outcomes-v1",
        "job": "fixture-catalog-job",
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "acquired_at": "2026-08-30T12:00:00+00:00",
    }
    lease_raw = subject._canonical(lease_body) + b"\n"
    lease_identity = _identity(
        subject.HISTORICAL_OUTCOME_LEASE_URI, lease_raw, generation="18"
    )
    completion = {
        "run_id": "fixture-catalog-outcomes-v1",
        "historical_outcome_lease_identity": lease_identity,
        "completion_sha256": "1" * 64,
    }
    completion_identity = {
        "uri": OUTCOME_COMPLETION_URI,
        "generation": "19",
        "sha256": "f" * 64,
        "bytes": 123,
    }
    snapshot = {"outcome_snapshot_sha256": "3" * 64}
    snapshot_identity = {
        "uri": OUTCOME_COMPLETION_URI.replace("completion.json", "outcome-snapshot.json"),
        "generation": "21",
        "sha256": "4" * 64,
        "bytes": 100,
    }
    players = {f"player-{index}": 10_000_000 + index for index in range(9)}
    closure = subject._with_hash({
        "schema_version": subject.OUTCOME_CLOSURE_SCHEMA,
        "fixture": True,
    }, field="closure_sha256")
    return subject.OpenedOutcomeAuthorityV1(
        completion=completion,
        completion_identity=completion_identity,
        snapshot=snapshot,
        snapshot_identity=snapshot_identity,
        player_scores={(0, player): score for player, score in players.items()},
        slate_keys={0: (2023, 1, "2023-w01")},
        lease_body=lease_body,
        lease_identity=lease_identity,
        lease_body_sha256=subject._hash(lease_body),
        closure_receipt=closure,
    )


def _report(name: str = "expected") -> dict[str, object]:
    body = {"schema_version": "fixture-grade/v1", "name": name}
    return {**body, "report_sha256": subject._hash(body)}


@pytest.fixture
def compact(monkeypatch):
    monkeypatch.setattr(cross, "EXPECTED_SLATE_IDS", ("2023-w01",))
    monkeypatch.setattr(
        selection_operator, "reopen_terminal_bundle_v1", _fake_selection_reopen
    )
    def open_authority(*args, verify_live_lease, **kwargs):
        del args, kwargs
        authority = _outcome_authority()
        subject._live_lease_receipt(
            verify_live_lease(
                expected_identity=authority.lease_identity,
                catalog_run_id=str(authority.completion["run_id"]),
            ),
            expected_identity=authority.lease_identity,
            catalog_run_id=str(authority.completion["run_id"]),
        )
        return authority

    monkeypatch.setattr(subject, "open_recognized_outcome_authority_v1", open_authority)
    monkeypatch.setattr(
        grade_science, "grade_published_cross_v1",
        lambda *args, **kwargs: _report(),
    )
    monkeypatch.setattr(
        grade_science, "validate_published_grade_v1",
        lambda value: dict(value),
    )


def _prepare(store: _Store):
    return subject.prepare_grade_manifest_v1(
        run_id="fixture-grade-run-v1",
        grade_id="fixture-grade-v1",
        frozen_at="2026-08-30T12:00:00Z",
        code_sha=CODE_SHA,
        immutable_image=IMAGE,
        output_prefix=OUTPUT_PREFIX,
        selection_terminal_envelope=_selection_envelope(),
        outcome_authority_identity={
            "uri": OUTCOME_COMPLETION_URI,
            "generation": "19",
            "sha256": "f" * 64,
            "bytes": 123,
        },
        read_exact=store.read,
        publish_create_once=store.publish,
    )


def test_grade_publishes_children_then_terminal_recomputes_and_preserves_catalog_lease(
    compact,
) -> None:
    store = _Store()
    prepared = _prepare(store)
    lease = _Lease()
    result = subject.publish_grade_v1(
        manifest_identity=prepared["manifest_identity"],
        code_sha=CODE_SHA,
        immutable_image=IMAGE,
        read_exact=store.read,
        publish_create_once=store.publish,
        verify_live_lease=lease,
    )
    assert result["complete"] is True
    assert result["historical_outcome_lease_released"] is False
    assert result["lease_release_owner"] == "external-launcher-watcher"
    assert lease.calls >= 4
    assert store.writes[-1].endswith("/grade-terminal.json")
    reopened = subject.reopen_grade_terminal_v1(
        result["terminal_envelope"], read_exact=store.read,
        verify_live_lease=lease,
    )
    assert reopened["grade_independently_recomputed"] is True
    assert reopened["outcome_document_count"] == 1
    assert reopened["object_listing_used"] is False
    assert reopened["scientific_object_delete_used"] is False


def test_grade_reverifies_live_lease_before_first_realized_child_publish(
    compact,
) -> None:
    store = _Store()
    prepared = _prepare(store)

    class _PrepublicationLease(_Lease):
        def __call__(self, *, expected_identity, catalog_run_id):
            receipt = super().__call__(
                expected_identity=expected_identity,
                catalog_run_id=catalog_run_id,
            )
            if self.calls == 2:
                assert store.writes == [prepared["manifest_identity"]["uri"]]
            return receipt

    lease = _PrepublicationLease()
    result = subject.publish_grade_v1(
        manifest_identity=prepared["manifest_identity"],
        code_sha=CODE_SHA,
        immutable_image=IMAGE,
        read_exact=store.read,
        publish_create_once=store.publish,
        verify_live_lease=lease,
    )
    assert result["complete"] is True
    assert lease.calls >= 5


def test_self_rehashed_forged_selection_terminal_is_rejected_before_outcomes(
    compact,
) -> None:
    store = _Store()
    forged = _selection_envelope()
    forged["terminal_identity"] = {
        **forged["terminal_identity"],
        "uri": "gs://fixture/selection/forged-terminal.json",
    }
    body = dict(forged)
    body.pop("envelope_sha256")
    forged["envelope_sha256"] = subject._hash(body)
    with pytest.raises(
        subject.ConstructionAllocationGradeOperatorV1Error,
        match="selection terminal/predecessor closure",
    ):
        subject.prepare_grade_manifest_v1(
            run_id="fixture-grade-forged-v1",
            grade_id="fixture-grade-v1",
            frozen_at="2026-08-30T12:00:00Z",
            code_sha=CODE_SHA,
            immutable_image=IMAGE,
            output_prefix=OUTPUT_PREFIX,
            selection_terminal_envelope=forged,
            outcome_authority_identity={
                "uri": OUTCOME_COMPLETION_URI,
                "generation": "19",
                "sha256": "f" * 64,
                "bytes": 123,
            },
            read_exact=store.read,
            publish_create_once=store.publish,
        )
    assert store.writes == []


def test_forged_outcome_authority_namespace_is_rejected_without_read(compact) -> None:
    store = _Store()
    with pytest.raises(
        subject.ConstructionAllocationGradeOperatorV1Error,
        match="recognized outcome completion namespace",
    ):
        subject.prepare_grade_manifest_v1(
            run_id="fixture-grade-forged-outcome-v1",
            grade_id="fixture-grade-v1",
            frozen_at="2026-08-30T12:00:00Z",
            code_sha=CODE_SHA,
            immutable_image=IMAGE,
            output_prefix=OUTPUT_PREFIX,
            selection_terminal_envelope=_selection_envelope(),
            outcome_authority_identity={
                "uri": "gs://forged/outcome/completion.json",
                "generation": "19",
                "sha256": "f" * 64,
                "bytes": 123,
            },
            read_exact=store.read,
            publish_create_once=store.publish,
        )
    assert store.writes == []


def test_forged_live_catalog_lease_generation_is_rejected_before_grade_children(
    compact,
) -> None:
    store = _Store()
    prepared = _prepare(store)
    lease = _Lease()

    def forged_lease(*, expected_identity, catalog_run_id):
        receipt = lease(
            expected_identity=expected_identity, catalog_run_id=catalog_run_id
        )
        return {
            "body": receipt["body"],
            "object_receipt": {
                **receipt["object_receipt"],
                "generation": "forged-generation",
            },
        }

    with pytest.raises(
        subject.ConstructionAllocationGradeOperatorV1Error,
        match="historical-outcome lease authority differs",
    ):
        subject.publish_grade_v1(
            manifest_identity=prepared["manifest_identity"],
            code_sha=CODE_SHA,
            immutable_image=IMAGE,
            read_exact=store.read,
            publish_create_once=store.publish,
            verify_live_lease=forged_lease,
        )
    assert store.writes == [prepared["manifest_identity"]["uri"]]


def test_self_rehashed_forged_outcome_completion_is_rejected() -> None:
    identities = {
        name: {
            "uri": f"gs://fixture/{name}.json",
            "generation": "17",
            "sha256": "a" * 64,
            "bytes": 100,
        }
        for name in (
            "outcome_key_projection", "registered_request", "query_evidence",
            "realized_source", "outcome_snapshot", "historical_outcome_lease",
        )
    }
    body = {
        "schema_version": subject.RECOGNIZED_OUTCOME_COMPLETION_SCHEMA,
        "run_id": "fixture-catalog-outcomes-v1",
        "outcome_key_projection_identity": identities["outcome_key_projection"],
        "registered_request_identity": identities["registered_request"],
        "query_evidence_identity": identities["query_evidence"],
        "realized_source_identity": identities["realized_source"],
        "outcome_snapshot_identity": identities["outcome_snapshot"],
        "historical_outcome_lease_identity": identities["historical_outcome_lease"],
        "source_snapshot_at": "2026-08-26T23:58:47.451523+00:00",
        "source_slate_count": 54,
        "outcome_key_count": 29_605,
        "delta_query_key_count": 15_358,
        "one_historical_outcome_read": True,
        "one_exact_query_job": True,
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": "external-launcher-watcher",
        # A self-consistent hash cannot authorize a completion that admits
        # lineup scoring in the separately frozen truth-source stage.
        "lineup_scoring_performed": True,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
        "complete": True,
    }
    forged = {**body, "completion_sha256": subject._hash(body)}
    raw = subject._canonical(forged)
    identity = _identity(OUTCOME_COMPLETION_URI, raw, generation="19")
    store = _Store()
    store.prime(identity, raw)
    lease_calls = []
    with pytest.raises(
        subject.ConstructionAllocationGradeOperatorV1Error,
        match="recognized outcome completion differs",
    ):
        subject.open_recognized_outcome_authority_v1(
            identity, read_exact=store.read,
            verify_live_lease=lambda **kwargs: lease_calls.append(kwargs),
        )
    assert lease_calls == []


def test_self_consistent_forged_grade_is_rejected_by_recomputation(
    compact, monkeypatch,
) -> None:
    store = _Store()
    prepared = _prepare(store)
    result = subject.publish_grade_v1(
        manifest_identity=prepared["manifest_identity"],
        code_sha=CODE_SHA,
        immutable_image=IMAGE,
        read_exact=store.read,
        publish_create_once=store.publish,
        verify_live_lease=_Lease(),
    )
    original_envelope = result["terminal_envelope"]
    original_terminal = subject._parse_document(
        store.read(original_envelope["terminal_identity"]), label="terminal"
    )

    forged_report = _report("forged-but-self-consistent")
    forged_report_raw = subject._canonical(forged_report)
    forged_report_identity = _identity(
        original_terminal["grade_report_identity"]["uri"], forged_report_raw,
        generation="900", create=True,
    )
    store.prime(forged_report_identity, forged_report_raw)
    forged_terminal = deepcopy(original_terminal)
    forged_terminal["grade_report_identity"] = forged_report_identity
    forged_terminal["grade_report_sha256"] = forged_report["report_sha256"]
    terminal_body = dict(forged_terminal)
    terminal_body.pop("terminal_sha256")
    forged_terminal["terminal_sha256"] = subject._hash(terminal_body)
    forged_terminal_raw = subject._canonical(forged_terminal)
    forged_terminal_identity = _identity(
        original_envelope["terminal_identity"]["uri"], forged_terminal_raw,
        generation="901", create=True,
    )
    store.prime(forged_terminal_identity, forged_terminal_raw)
    forged_envelope = deepcopy(original_envelope)
    forged_envelope["terminal_identity"] = forged_terminal_identity
    forged_envelope["terminal_sha256"] = forged_terminal["terminal_sha256"]
    envelope_body = dict(forged_envelope)
    envelope_body.pop("envelope_sha256")
    forged_envelope["envelope_sha256"] = subject._hash(envelope_body)

    # Stored forged report passes its own validator; independent recomputation
    # still returns the expected report and must reject it.
    monkeypatch.setattr(
        grade_science, "validate_published_grade_v1", lambda value: dict(value)
    )
    with pytest.raises(
        subject.ConstructionAllocationGradeOperatorV1Error,
        match="does not equal independent recomputation",
    ):
        subject.reopen_grade_terminal_v1(
            forged_envelope, read_exact=store.read,
            verify_live_lease=_Lease(),
        )
