from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from nfl_dfs.inference import prospective_generation_shadow_operator as operator


UTC = timezone.utc
WEEK1_LOCK = datetime(2026, 9, 13, 17, tzinfo=UTC)


class MemoryStore:
    def __init__(self, *, now: datetime) -> None:
        self.now = now
        self.objects: dict[str, dict[str, object]] = {}
        self.next_generation = 100
        self.events: list[tuple[str, str]] = []

    def advance(self, seconds: int = 1) -> None:
        self.now += timedelta(seconds=seconds)

    def inject_raw(
        self,
        uri: str,
        raw: bytes,
        *,
        created_at: datetime | None = None,
    ) -> dict[str, object]:
        if uri in self.objects:
            raise AssertionError("test fixture URI reused")
        generation = str(self.next_generation)
        self.next_generation += 1
        identity = {
            "uri": uri,
            "generation": generation,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[uri] = {
            "identity": identity,
            "created_at": (created_at or self.now).isoformat(),
            "raw": raw,
        }
        return identity

    def inject_json(
        self,
        uri: str,
        value: Mapping[str, object],
        *,
        created_at: datetime | None = None,
    ) -> dict[str, object]:
        return self.inject_raw(
            uri,
            operator.evaluation.canonical_json_bytes_v1(value),
            created_at=created_at,
        )

    def publish_create_once(
        self, *, uri: str, raw: bytes, content_type: str
    ) -> Mapping[str, object]:
        self.events.append(("publish", uri))
        if uri in self.objects:
            raise operator.ProspectiveGenerationShadowOperatorError(
                f"create-once collision at {uri}"
            )
        identity = self.inject_raw(uri, raw, created_at=self.now)
        result = {
            "identity": identity,
            "created_at": self.now.isoformat(),
        }
        self.advance()
        return result

    def read_exact(
        self, *, identity: Mapping[str, object]
    ) -> Mapping[str, object]:
        uri = str(identity["uri"])
        self.events.append(("read", uri))
        retained = self.objects[uri]
        if retained["identity"] != dict(identity):
            raise operator.ProspectiveGenerationShadowOperatorError(
                "generation-pinned identity differs"
            )
        return dict(retained)


def _inject_json(
    store: MemoryStore,
    label: str,
    value: Mapping[str, object],
    *,
    created_at: datetime,
) -> dict[str, object]:
    return store.inject_json(
        f"gs://shadow-fixture/prelock/{label}.json",
        value,
        created_at=created_at,
    )


def test_preregistration_is_create_once_before_week1_and_never_adopts() -> None:
    store = MemoryStore(now=datetime(2026, 8, 30, 12, tzinfo=UTC))
    result = operator.publish_preregistration_v1(
        store=store,
        target_uri="gs://shadow-fixture/prelock/preregistration.json",
        registered_at=datetime(2026, 8, 30, 11, tzinfo=UTC),
        week1_lock_at=WEEK1_LOCK,
    )

    assert result["schema_version"] == operator.PREREGISTRATION_PUBLICATION_SCHEMA
    assert result["automatic_adoption"] is False
    assert result["allocation_recommendation_allowed"] is False
    identity = result["preregistration_identity"]
    published = store.objects[identity["uri"]]
    value = json.loads(published["raw"])
    assert operator.evaluation.validate_preregistration_v1(value) == value
    assert value["week1_lock_at"] == WEEK1_LOCK.isoformat()

    with pytest.raises(
        operator.ProspectiveGenerationShadowOperatorError,
        match="collision",
    ):
        operator.publish_preregistration_v1(
            store=store,
            target_uri="gs://shadow-fixture/prelock/preregistration.json",
            registered_at=datetime(2026, 8, 30, 11, tzinfo=UTC),
            week1_lock_at=WEEK1_LOCK,
        )


def test_seed_crossing_exact_reopens_every_source_before_publication() -> None:
    created = datetime(2026, 8, 30, 10, tzinfo=UTC)
    store = MemoryStore(now=created + timedelta(hours=1))
    fit = {
        f"fit{index}": store.inject_raw(
            f"gs://shadow-fixture/prelock/fit-{index}.bin",
            f"fit-{index}".encode(),
            created_at=created,
        )
        for index in range(2)
    }
    world = {
        f"world{index}": store.inject_raw(
            f"gs://shadow-fixture/prelock/world-{index}.bin",
            f"world-{index}".encode(),
            created_at=created,
        )
        for index in range(2)
    }
    crossed = {
        f"fit{i}--world{j}": store.inject_raw(
            f"gs://shadow-fixture/prelock/cross-{i}-{j}.bin",
            f"cross-{i}-{j}".encode(),
            created_at=created,
        )
        for i in range(2)
        for j in range(2)
    }

    result = operator.publish_seed_crossing_v1(
        store=store,
        target_uri="gs://shadow-fixture/prelock/seed-crossing.json",
        fit_seed_identities=fit,
        world_seed_identities=world,
        crossed_slot_identities=crossed,
        must_precede=WEEK1_LOCK,
    )

    assert result["all_sources_exact_reopened"] is True
    assert result["source_identity_count"] == 8
    assert [event[0] for event in store.events] == ["read"] * 8 + ["publish"]
    value = json.loads(
        store.objects[result["seed_crossing_identity"]["uri"]]["raw"]
    )
    assert operator.evaluation.validate_seed_crossing_v1(value) == value


def test_prelock_adapter_reopens_suite_bundles_and_publishes_root_then_envelope(
    monkeypatch,
) -> None:
    created = WEEK1_LOCK - timedelta(hours=4)
    store = MemoryStore(now=WEEK1_LOCK - timedelta(hours=1))
    prereg_identity = _inject_json(
        store, "prereg", {"kind": "prereg"}, created_at=created
    )
    seed_identity = _inject_json(
        store, "seed", {"kind": "seed"}, created_at=created
    )
    manifest = {"schema_version": "suite-manifest"}
    terminal = {
        "schema_version": "suite-terminal",
        "slate_lock_at": WEEK1_LOCK.isoformat(),
    }
    manifest_identity = _inject_json(
        store, "manifest", manifest, created_at=created
    )
    terminal_identity = _inject_json(
        store, "terminal", terminal, created_at=created
    )
    arm_identities = {
        arm: store.inject_raw(
            f"gs://shadow-fixture/prelock/{arm}.npz",
            f"bundle:{arm}".encode(),
            created_at=created,
        )
        for arm in operator._ARM_ORDER
    }
    audit_identity = store.inject_raw(
        "gs://shadow-fixture/prelock/audit.npz", b"audit", created_at=created
    )
    discovery_identities = {
        block: store.inject_raw(
            f"gs://shadow-fixture/prelock/discovery-{block}.npz",
            block.encode(),
            created_at=created,
        )
        for block in ("R0", "R1", "R2", "R3", "R4")
    }

    monkeypatch.setattr(
        operator.evaluation,
        "validate_preregistration_v1",
        lambda value: value,
    )
    monkeypatch.setattr(
        operator.evaluation,
        "validate_seed_crossing_v1",
        lambda value: value,
    )

    def fake_suite_authority(**kwargs):
        assert kwargs["manifest"] == manifest
        assert kwargs["terminal"] == terminal
        assert kwargs["terminal_receipt"]["generation"] == (
            terminal_identity["generation"]
        )
        return {
            "world_artifact_identities": arm_identities,
            "world_storage_created_at_by_arm": {
                arm: created.isoformat() for arm in operator._ARM_ORDER
            },
            "independent_audit_world_artifact_identity": audit_identity,
            "independent_audit_world_storage_created_at": created.isoformat(),
            "cross_law_discovery_world_artifact_identities": (
                discovery_identities
            ),
            "cross_law_discovery_world_storage_created_at": {
                block: created.isoformat() for block in discovery_identities
            },
        }

    monkeypatch.setattr(
        operator.evaluation, "build_suite_authority_v1", fake_suite_authority
    )
    decoded = []
    monkeypatch.setattr(
        operator,
        "decode_recourse_world_artifact",
        lambda raw, digest: decoded.append((raw, digest)) or {"sha256": digest},
    )
    root = {
        "season": 2026,
        "week": 1,
        "slate_id": "dk-123",
        "frozen_at": (WEEK1_LOCK - timedelta(hours=2)).isoformat(),
        "lock_at": WEEK1_LOCK.isoformat(),
        "terminal_prelock_root_sha256": "a" * 64,
    }
    monkeypatch.setattr(
        operator.evaluation,
        "build_terminal_prelock_root_from_suite_v2",
        lambda **kwargs: root,
    )

    def fake_bind(**kwargs):
        return {
            "storage_created_at": kwargs["storage_created_at"],
            "terminal_prelock_root": kwargs["root"],
            "terminal_prelock_envelope_sha256": "b" * 64,
        }

    monkeypatch.setattr(
        operator.evaluation, "bind_terminal_prelock_root_v1", fake_bind
    )
    monkeypatch.setattr(
        operator.evaluation,
        "validate_terminal_prelock_root_v1",
        lambda envelope: envelope["terminal_prelock_root"],
    )

    result = operator.publish_prelock_terminal_from_suite_v1(
        store=store,
        preregistration_identity=prereg_identity,
        seed_crossing_identity=seed_identity,
        suite_manifest_identity=manifest_identity,
        suite_terminal_identity=terminal_identity,
        terminal_root_uri="gs://shadow-fixture/prelock/evaluation-root.json",
        terminal_envelope_uri=(
            "gs://shadow-fixture/prelock/evaluation-envelope.json"
        ),
    )

    assert len(decoded) == len(operator._ARM_ORDER) + 1
    assert decoded[-1][0] == b"audit"
    assert result["outcome_access_performed"] is False
    assert result["production_change_licensed"] is False
    writes = [event[1] for event in store.events if event[0] == "publish"]
    assert writes[-2:] == [
        "gs://shadow-fixture/prelock/evaluation-root.json",
        "gs://shadow-fixture/prelock/evaluation-envelope.json",
    ]
    reads = [event[1] for event in store.events if event[0] == "read"]
    assert set(arm_identities[arm]["uri"] for arm in operator._ARM_ORDER) <= set(
        reads
    )
    assert audit_identity["uri"] in reads
    assert set(identity["uri"] for identity in discovery_identities.values()) <= set(
        reads
    )


def _postlock_fixture(monkeypatch, *, complete_field: bool):
    root = {
        "season": 2026,
        "week": 1,
        "slate_id": "dk-123",
        "lock_at": WEEK1_LOCK.isoformat(),
    }
    embedded_created = WEEK1_LOCK - timedelta(hours=2)
    envelope = {
        "storage_created_at": embedded_created.isoformat(),
        "terminal_prelock_root": root,
    }
    store = MemoryStore(now=WEEK1_LOCK + timedelta(days=1, minutes=1))
    envelope_identity = store.inject_json(
        "gs://shadow-fixture/prelock/evaluation-envelope.json",
        envelope,
        created_at=WEEK1_LOCK - timedelta(hours=1),
    )
    score_captured_at = WEEK1_LOCK + timedelta(days=1)
    score_rows = [{"lineup_id": "l1", "realized_score_micro": 1}]
    score_identity = store.inject_json(
        "gs://shadow-fixture/independent-scorer/week-01/realized-scores.json",
        {
            "schema_version": operator.evaluation.REALIZED_SCORE_SOURCE_SCHEMA,
            "season": 2026,
            "week": 1,
            "slate_id": "dk-123",
            "captured_at": score_captured_at.isoformat(),
            "producer_class": "independent-realized-lineup-score-source",
            "independent_from_generation": True,
            "terminal_prelock_root_binding_present": False,
            "lineup_count": 1,
            "lineup_rows": score_rows,
            "lineup_rows_sha256": operator._canonical_sha256(score_rows),
        },
        created_at=score_captured_at + timedelta(seconds=30),
    )
    events: list[str] = []
    monkeypatch.setattr(
        operator.evaluation,
        "validate_terminal_prelock_root_v1",
        lambda value: events.append("validate-root") or root,
    )
    monkeypatch.setattr(
        operator,
        "_resolve_full_field_inputs",
        lambda **kwargs: ({"field": "ready"} if complete_field else {}),
    )
    component_payloads = {
        name: {"schema_version": name} for name in operator._FIELD_COMPONENT_NAMES
    }
    raw_bridge = {
        "status": "raw-score-only-no-contest-ev",
        "evidence_scope": "raw-score-only-no-contest-ev",
        "complete_contest_field_capture": False,
        "complete_field_rank_claim_allowed": False,
        "contest_ev_claim_allowed": False,
    }
    preparation = {
        "status": "ready-for-create-once-component-binding",
        "component_payloads": component_payloads,
    }
    monkeypatch.setattr(
        operator.field_bridge,
        "prepare_contest_field_bridge_v1",
        lambda **kwargs: preparation if complete_field else raw_bridge,
    )
    complete_bridge = {
        "status": "complete-contest-field-capture",
        "evidence_scope": "raw-score-and-contest-field-utility",
        "complete_contest_field_capture": True,
        "complete_field_rank_claim_allowed": True,
        "contest_ev_claim_allowed": True,
    }
    monkeypatch.setattr(
        operator.field_bridge,
        "bind_contest_field_bridge_v1",
        lambda **kwargs: complete_bridge,
    )
    monkeypatch.setattr(
        operator.field_bridge,
        "validate_contest_field_bridge_v1",
        lambda value: value,
    )
    monkeypatch.setattr(
        operator.evaluation,
        "build_outcome_source_payload_from_field_bridge_v1",
        lambda **kwargs: {"schema_version": "outcome-source"},
    )
    monkeypatch.setattr(
        operator.evaluation,
        "build_outcome_snapshot_from_field_bridge_v1",
        lambda **kwargs: {
            "schema_version": "snapshot",
            "outcome_snapshot_sha256": "c" * 64,
        },
    )
    monkeypatch.setattr(
        operator.evaluation,
        "grade_realized_week_v1",
        lambda **kwargs: {
            "schema_version": "grade",
            "weekly_grade_sha256": "d" * 64,
        },
    )
    return store, envelope_identity, score_identity, events


@pytest.mark.parametrize(
    ("complete_field", "expected_write_count", "expected_status"),
    [
        (False, 5, "raw-score-only-no-contest-ev"),
        (True, 11, "complete-contest-field-capture"),
    ],
)
def test_postlock_operator_publishes_raw_or_complete_field_without_allocation(
    monkeypatch, complete_field, expected_write_count, expected_status
) -> None:
    store, envelope_identity, score_identity, events = _postlock_fixture(
        monkeypatch, complete_field=complete_field
    )
    result = operator.publish_postlock_week_v1(
        store=store,
        terminal_prelock_envelope_identity=envelope_identity,
        captured_at=WEEK1_LOCK + timedelta(days=1),
        realized_score_source_identity=score_identity,
        output_prefix_uri="gs://shadow-fixture/postlock/week-01/run-a",
        field_inputs={"present": True} if complete_field else None,
    )

    assert events == ["validate-root"]
    assert result["field_status"] == expected_status
    assert result["complete_contest_field_capture"] is complete_field
    assert result["contest_ev_claim_allowed"] is complete_field
    assert result["allocation_recommendation_allowed"] is False
    assert result["automatic_adoption"] is False
    assert result["production_change_licensed"] is False
    writes = [event for event in store.events if event[0] == "publish"]
    assert len(writes) == expected_write_count
    assert not any(uri.endswith("/realized-scores.json") for _, uri in writes)
    assert writes[-1][1].endswith("/publication-terminal.json")
    component_writes = [uri for _, uri in writes if "/field-components/" in uri]
    assert len(component_writes) == (6 if complete_field else 0)


def test_evaluation_reopens_each_grade_and_cannot_auto_adopt(monkeypatch) -> None:
    store = MemoryStore(now=WEEK1_LOCK + timedelta(days=60))
    prereg_identity = store.inject_json(
        "gs://shadow-fixture/prelock/preregistration.json",
        {"schema_version": "prereg"},
        created_at=WEEK1_LOCK - timedelta(days=1),
    )
    grade_identities = [
        store.inject_json(
            f"gs://shadow-fixture/postlock/week-{week:02d}/grade.json",
            {"week": week},
            created_at=WEEK1_LOCK + timedelta(days=7 * week),
        )
        for week in (1, 2)
    ]
    monkeypatch.setattr(
        operator.evaluation,
        "validate_preregistration_v1",
        lambda value: value,
    )
    monkeypatch.setattr(
        operator.evaluation,
        "validate_realized_week_grade_v1",
        lambda value: value,
    )
    result_payload = {
        "season": 2026,
        "completed_week_count": 2,
        "completed_weeks": [1, 2],
        "horizon": "accrual-before-eight-week-interim",
        "decision_scope": "not-yet-eligible",
        "contest_ev_claim_allowed": False,
        "evaluation_sha256": "e" * 64,
    }
    monkeypatch.setattr(
        operator.evaluation,
        "evaluate_prospective_shadow_v1",
        lambda **kwargs: result_payload,
    )

    result = operator.publish_evaluation_v1(
        store=store,
        preregistration_identity=prereg_identity,
        weekly_grade_identities=grade_identities,
        target_uri="gs://shadow-fixture/postlock/evaluations/week-02.json",
    )

    assert result["human_decision_required"] is True
    assert result["automatic_adoption"] is False
    assert result["allocation_recommendation_allowed"] is False
    assert result["decision_scope"] == "not-yet-eligible"
    assert result["weekly_grade_identities"] == grade_identities


def test_field_input_reopen_accepts_archived_pretty_receipt_and_derives_apply(
    monkeypatch,
) -> None:
    from nfl_dfs.ingest import ownership_import

    created = WEEK1_LOCK + timedelta(days=1)
    store = MemoryStore(now=created + timedelta(minutes=1))
    source_uri = "gs://shadow-fixture/postlock/capture/source.csv"
    source_raw = b"exact-dk-export"
    source_identity = store.inject_raw(
        source_uri, source_raw, created_at=created
    )
    receipt_uri = "gs://shadow-fixture/postlock/capture/receipt.json"
    manifest = {
        "receipt_uri": receipt_uri,
        "source": {
            "uri": source_uri,
            "sha256": source_identity["sha256"],
            "bytes": source_identity["bytes"],
        },
        "contest": {"expected_entries": 2},
    }
    pretty = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    manifest_identity = store.inject_raw(
        receipt_uri, pretty, created_at=created
    )
    validated = {"entries": object(), "ownership": object()}
    monkeypatch.setattr(
        ownership_import,
        "_validate_full_field_payload",
        lambda path, payload, expected_entries: (
            validated
            if (path, payload, expected_entries)
            == (source_uri, source_raw, 2)
            else pytest.fail("capture bytes or field size drifted")
        ),
    )

    result = operator._resolve_full_field_inputs(
        store=store,
        lock_at=WEEK1_LOCK,
        field_inputs={
            "capture_manifest_identity": manifest_identity,
            "capture_source_identity": source_identity,
            "entry_fee_micro": 20_000_000,
            "payout_table_rows": [],
            "participant_strength_rows": [],
            "player_identity_rows": [],
        },
    )

    assert result["capture_manifest"]["status"] == "applied"
    assert result["validated_capture"] is validated
    assert result["capture_source_identity"] == source_identity


def test_cli_is_default_off_before_constructing_a_cloud_client(monkeypatch) -> None:
    monkeypatch.setattr(
        operator,
        "GCSImmutableObjectStore",
        lambda: pytest.fail("cloud client must not be constructed"),
    )
    with pytest.raises(
        operator.ProspectiveGenerationShadowOperatorError,
        match="default-off",
    ):
        operator.main([
            "preregister",
            "--target-uri",
            "gs://shadow-fixture/prelock/preregistration.json",
            "--registered-at",
            "2026-08-30T00:00:00+00:00",
            "--week1-lock-at",
            WEEK1_LOCK.isoformat(),
        ])


def test_main_cli_forwards_to_bounded_operator(monkeypatch) -> None:
    from nfl_dfs import cli

    captured = []
    monkeypatch.setattr(operator, "main", captured.append)
    cli.main([
        "shadow-generation-operator",
        "preregister",
        "--target-uri",
        "gs://shadow-fixture/prelock/preregistration.json",
    ])
    assert captured == [[
        "preregister",
        "--target-uri",
        "gs://shadow-fixture/prelock/preregistration.json",
    ]]


class _FakeBlob:
    def __init__(self, uri: str) -> None:
        self.uri = uri
        self.generation = "321"
        self.time_created = datetime(2026, 8, 30, 12, tzinfo=UTC)
        self.raw = b""
        self.upload_match = None
        self.download_matches: list[int] = []

    def upload_from_string(self, raw, *, content_type, if_generation_match):
        self.raw = raw
        self.upload_match = if_generation_match

    def reload(self):
        return None

    def download_as_bytes(self, *, if_generation_match):
        self.download_matches.append(if_generation_match)
        return self.raw


class _FakeBucket:
    def __init__(self, bucket: str) -> None:
        self.bucket = bucket
        self.blobs: dict[str, _FakeBlob] = {}

    def blob(self, name: str, generation=None):
        return self.blobs.setdefault(name, _FakeBlob(f"gs://{self.bucket}/{name}"))

    def get_blob(self, name: str, generation: int):
        blob = self.blobs[name]
        assert generation == int(blob.generation)
        return blob


class _FakeClient:
    def __init__(self) -> None:
        self.buckets: dict[str, _FakeBucket] = {}

    def bucket(self, name: str):
        return self.buckets.setdefault(name, _FakeBucket(name))


def test_gcs_store_uses_absence_precondition_and_generation_pinned_reopen() -> None:
    client = _FakeClient()
    store = operator.GCSImmutableObjectStore(client)
    raw = b'{"canonical":true}'
    published = store.publish_create_once(
        uri="gs://shadow-fixture/prelock/object.json",
        raw=raw,
        content_type="application/json",
    )
    blob = client.bucket("shadow-fixture").blobs["prelock/object.json"]
    assert blob.upload_match == 0
    assert blob.download_matches == [321]

    reopened = store.read_exact(identity=published["identity"])
    assert reopened["raw"] == raw
    assert blob.download_matches == [321, 321]
