from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib

import pytest

from nfl_dfs.inference import prospective_generation_shadow_evaluation as shadow
from nfl_dfs.inference import week1_operating_book_operator as operator


LOCK_AT = "2026-09-13T17:00:00+00:00"
ROOT_CREATED = "2026-09-13T13:00:00+00:00"
SOURCE_CREATED = "2026-09-13T14:00:00+00:00"
OUTPUT_CREATED = "2026-09-13T15:00:00+00:00"
ROOT_URI = "gs://test/prelock/terminal-root.json"
SOURCE_URI = "gs://test/prelock/terminal-envelope.json"
TARGET_URI = "gs://test/prelock/week1-operating-book.json"


class FakeStore:
    def __init__(self, *, publish_created_at: str = OUTPUT_CREATED) -> None:
        self.publish_created_at = publish_created_at
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}
        self.next_generation = 1
        self.read_count_by_uri: dict[str, int] = {}
        self.forge_reopen_uri: str | None = None

    def seed(self, *, uri: str, value: dict[str, object], created_at: str):
        raw = shadow.canonical_json_bytes_v1(value)
        identity = {
            "uri": uri,
            "generation": "1",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[(uri, "1")] = (raw, created_at)
        return identity

    def publish_create_once(self, *, uri: str, raw: bytes, content_type: str):
        assert content_type == "application/json"
        if any(key[0] == uri for key in self.objects):
            raise operator.Week1OperatingBookOperatorError(
                f"create-once collision at {uri}"
            )
        generation = str(self.next_generation)
        self.next_generation += 1
        self.objects[(uri, generation)] = (raw, self.publish_created_at)
        return {
            "identity": {
                "uri": uri,
                "generation": generation,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            },
            "created_at": self.publish_created_at,
        }

    def read_exact(self, *, identity):
        key = (str(identity["uri"]), str(identity["generation"]))
        raw, created_at = self.objects[key]
        self.read_count_by_uri[key[0]] = self.read_count_by_uri.get(key[0], 0) + 1
        if self.forge_reopen_uri == key[0]:
            raw = raw + b" "
        return {
            "identity": dict(identity),
            "created_at": created_at,
            "raw": raw,
        }


def _root(
    *,
    week: int = 1,
    slate_id: str = "dk-151307",
    draft_group_id: str = "151307",
    lock_at: str = LOCK_AT,
) -> dict[str, object]:
    return {
        "season": 2026,
        "week": week,
        "slate_id": slate_id,
        "lock_at": lock_at,
        "terminal_prelock_root_sha256": "f" * 64,
        "suite_authority_sha256": "a" * 64,
        "suite_authority": {
            "manifest": {
                "season": 2026,
                "week": week,
                "draft_group_id": draft_group_id,
                "slate_lock_at": lock_at,
            }
        },
    }


def _terminal(
    root_identity: dict[str, object],
    *,
    root_value: dict[str, object] | None = None,
) -> dict[str, object]:
    retained_root = root_value or _root()
    return {
        "schema_version": "test-terminal-envelope/v1",
        "identity": root_identity,
        "storage_created_at": ROOT_CREATED,
        "terminal_prelock_root": retained_root,
        "terminal_prelock_root_sha256": retained_root[
            "terminal_prelock_root_sha256"
        ],
        "terminal_prelock_envelope_sha256": "e" * 64,
    }


def _materialization(
    k: int,
    *,
    root_identity: dict[str, object] | None = None,
    terminal: dict[str, object] | None = None,
) -> dict[str, object]:
    if root_identity is None:
        retained_root = _root()
        raw = shadow.canonical_json_bytes_v1(retained_root)
        root_identity = {
            "uri": ROOT_URI,
            "generation": "1",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
    retained_terminal = terminal or _terminal(root_identity)
    token = f"{k:02x}"[-2:] * 32
    return {
        "authority_mode": "terminal-prelock-envelope",
        "k": k,
        "slate_context": {
            "season": 2026,
            "week": 1,
            "draft_group_id": "151307",
            "run_id": "week1-test",
            "code_sha": "a" * 40,
            "slate_lock_at": LOCK_AT,
        },
        "suite_authority_sha256": "a" * 64,
        "materialization_sha256": token,
        "adapter_envelope_sha256": "b" * 64,
        "selected_lineup_ids_sha256": "c" * 64,
        "source_membership_books_sha256": "d" * 64,
        "terminal_root_binding": {
            "terminal_prelock_root_sha256": retained_terminal[
                "terminal_prelock_root_sha256"
            ],
            "terminal_prelock_envelope_sha256": retained_terminal[
                "terminal_prelock_envelope_sha256"
            ],
            "terminal_prelock_object_identity": root_identity,
        },
        "adapter_envelope": {
            "compositor_receipt": {"contract_sha256": "e" * 64}
        },
    }


def _arrange(
    monkeypatch: pytest.MonkeyPatch,
    *,
    publish_created_at: str = OUTPUT_CREATED,
    k: int = 80,
    root_value: dict[str, object] | None = None,
) -> tuple[FakeStore, dict[str, object], list[tuple[int, object]]]:
    store = FakeStore(publish_created_at=publish_created_at)
    retained_root = root_value or _root()
    root_identity = store.seed(
        uri=ROOT_URI, value=retained_root, created_at=ROOT_CREATED
    )
    terminal = _terminal(root_identity, root_value=retained_root)
    source_identity = store.seed(
        uri=SOURCE_URI, value=terminal, created_at=SOURCE_CREATED
    )
    calls: list[tuple[int, object]] = []
    materialization = _materialization(
        k, root_identity=root_identity, terminal=terminal
    )

    def validate_root(value: object) -> dict[str, object]:
        assert value == terminal
        return terminal["terminal_prelock_root"]  # type: ignore[return-value]

    def build(*, k: int, terminal_prelock_root: object):
        calls.append((k, terminal_prelock_root))
        return deepcopy(materialization)

    monkeypatch.setattr(shadow, "validate_terminal_prelock_root_v1", validate_root)
    monkeypatch.setattr(
        shadow,
        "validate_terminal_prelock_root_body_v1",
        lambda value: value,
    )
    monkeypatch.setattr(
        shadow,
        "bind_terminal_prelock_root_v1",
        lambda **_kwargs: deepcopy(terminal),
    )
    monkeypatch.setattr(
        operator, "build_week1_operating_roster_materialization_v1", build
    )
    monkeypatch.setattr(
        operator,
        "validate_week1_operating_roster_materialization_v1",
        lambda value: value,
    )
    return store, source_identity, calls


@pytest.mark.parametrize("k", (80, 100))
def test_publish_exact_reopens_and_binds_the_operating_book(
    monkeypatch: pytest.MonkeyPatch, k: int
) -> None:
    store, source_identity, calls = _arrange(monkeypatch, k=k)
    receipt = operator.publish_week1_operating_book_v1(
        store=store,
        terminal_prelock_envelope_identity=source_identity,
        target_uri=TARGET_URI,
        k=k,
        observed_at="2026-09-13T14:30:00+00:00",
    )

    root_identity = store.objects[(ROOT_URI, "1")]
    expected_terminal = _terminal({
        "uri": ROOT_URI,
        "generation": "1",
        "sha256": hashlib.sha256(root_identity[0]).hexdigest(),
        "bytes": len(root_identity[0]),
    })
    assert calls == [(k, expected_terminal)]
    assert receipt["complete"] is True
    assert receipt["k"] == k
    assert receipt["source_terminal_prelock_envelope_identity"] == source_identity
    assert receipt["source_terminal_prelock_root_identity"] == expected_terminal[
        "identity"
    ]
    assert receipt["slate_id"] == "dk-151307"
    assert receipt["target_uri"] == TARGET_URI
    assert receipt["materialization_identity"]["uri"] == TARGET_URI
    assert store.read_count_by_uri[SOURCE_URI] == 1
    assert store.read_count_by_uri[ROOT_URI] == 1
    assert store.read_count_by_uri[TARGET_URI] == 1
    assert receipt["independent_exact_reopen"] is True
    assert receipt["cap4_used"] is False
    assert receipt["tier3_used"] is False
    assert receipt["uses_realized_outcomes"] is False
    assert operator.validate_week1_operating_book_publication_v1(receipt) == receipt


def test_create_once_collision_fails_without_overwrite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, source_identity, _calls = _arrange(monkeypatch)
    kwargs = {
        "store": store,
        "terminal_prelock_envelope_identity": source_identity,
        "target_uri": TARGET_URI,
        "k": 80,
        "observed_at": "2026-09-13T14:30:00+00:00",
    }
    operator.publish_week1_operating_book_v1(**kwargs)
    retained = next(
        raw for (uri, _generation), (raw, _created) in store.objects.items()
        if uri == TARGET_URI
    )
    with pytest.raises(
        operator.Week1OperatingBookOperatorError, match="collision"
    ):
        operator.publish_week1_operating_book_v1(**kwargs)
    assert next(
        raw for (uri, _generation), (raw, _created) in store.objects.items()
        if uri == TARGET_URI
    ) == retained


def test_preflight_rejects_at_or_after_lock_before_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, source_identity, _calls = _arrange(monkeypatch)
    with pytest.raises(
        operator.Week1OperatingBookOperatorError, match="at or after lock"
    ):
        operator.publish_week1_operating_book_v1(
            store=store,
            terminal_prelock_envelope_identity=source_identity,
            target_uri=TARGET_URI,
            k=80,
            observed_at=LOCK_AT,
        )
    assert not any(uri == TARGET_URI for uri, _generation in store.objects)


def test_trusted_late_creation_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, source_identity, _calls = _arrange(
        monkeypatch, publish_created_at=LOCK_AT
    )
    with pytest.raises(Exception, match="storage publication/reopen failed"):
        operator.publish_week1_operating_book_v1(
            store=store,
            terminal_prelock_envelope_identity=source_identity,
            target_uri=TARGET_URI,
            k=80,
            observed_at="2026-09-13T14:30:00+00:00",
        )


def test_exact_source_identity_drift_fails_before_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, source_identity, calls = _arrange(monkeypatch)
    forged = {**source_identity, "sha256": "f" * 64}
    with pytest.raises(Exception, match="exact reopen failed"):
        operator.publish_week1_operating_book_v1(
            store=store,
            terminal_prelock_envelope_identity=forged,
            target_uri=TARGET_URI,
            k=80,
            observed_at="2026-09-13T14:30:00+00:00",
        )
    assert calls == []


@pytest.mark.parametrize(
    "root_value",
    (
        _root(week=2),
        _root(slate_id="dk-999999"),
        _root(draft_group_id="999999"),
        _root(lock_at="2026-09-20T17:00:00+00:00"),
    ),
)
def test_wrong_week1_slate_context_fails_before_materialization(
    monkeypatch: pytest.MonkeyPatch,
    root_value: dict[str, object],
) -> None:
    store, source_identity, calls = _arrange(
        monkeypatch, root_value=root_value
    )
    with pytest.raises(
        operator.Week1OperatingBookOperatorError,
        match="not the frozen 2026 Week-1 main slate",
    ):
        operator.publish_week1_operating_book_v1(
            store=store,
            terminal_prelock_envelope_identity=source_identity,
            target_uri=TARGET_URI,
            k=80,
            observed_at="2026-09-13T14:30:00+00:00",
        )
    assert calls == []


def test_embedded_terminal_root_exact_reopen_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, source_identity, calls = _arrange(monkeypatch)
    store.forge_reopen_uri = ROOT_URI
    with pytest.raises(
        operator.Week1OperatingBookOperatorError,
        match="exact reopen failed",
    ):
        operator.publish_week1_operating_book_v1(
            store=store,
            terminal_prelock_envelope_identity=source_identity,
            target_uri=TARGET_URI,
            k=80,
            observed_at="2026-09-13T14:30:00+00:00",
        )
    assert calls == []


def test_independent_reopen_byte_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, source_identity, _calls = _arrange(monkeypatch)
    store.forge_reopen_uri = TARGET_URI
    with pytest.raises(Exception, match="storage publication/reopen failed"):
        operator.publish_week1_operating_book_v1(
            store=store,
            terminal_prelock_envelope_identity=source_identity,
            target_uri=TARGET_URI,
            k=80,
            observed_at="2026-09-13T14:30:00+00:00",
        )


@pytest.mark.parametrize("k", (20, 40, 60, 150, True))
def test_unsupported_k_is_rejected_before_any_read(
    monkeypatch: pytest.MonkeyPatch, k: object
) -> None:
    store, source_identity, calls = _arrange(monkeypatch)
    with pytest.raises(operator.Week1OperatingBookOperatorError, match="K must be"):
        operator.publish_week1_operating_book_v1(
            store=store,
            terminal_prelock_envelope_identity=source_identity,
            target_uri=TARGET_URI,
            k=k,  # type: ignore[arg-type]
            observed_at="2026-09-13T14:30:00+00:00",
        )
    assert calls == []


def test_rehashed_receipt_cannot_claim_cap4_tier3_or_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, source_identity, _calls = _arrange(monkeypatch)
    receipt = operator.publish_week1_operating_book_v1(
        store=store,
        terminal_prelock_envelope_identity=source_identity,
        target_uri=TARGET_URI,
        k=80,
        observed_at="2026-09-13T14:30:00+00:00",
    )
    for field in ("cap4_used", "tier3_used", "uses_realized_outcomes"):
        forged = deepcopy(receipt)
        forged[field] = True
        forged.pop("publication_receipt_sha256")
        from nfl_dfs.inference.generation_exposure import canonical_sha256

        forged["publication_receipt_sha256"] = canonical_sha256(forged)
        with pytest.raises(
            operator.Week1OperatingBookOperatorError,
            match="fixed pre-lock law differs",
        ):
            operator.validate_week1_operating_book_publication_v1(forged)


def test_rehashed_receipt_cannot_add_context_outcome_or_carrier_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, source_identity, _calls = _arrange(monkeypatch)
    receipt = operator.publish_week1_operating_book_v1(
        store=store,
        terminal_prelock_envelope_identity=source_identity,
        target_uri=TARGET_URI,
        k=80,
        observed_at="2026-09-13T14:30:00+00:00",
    )
    from nfl_dfs.inference.generation_exposure import canonical_sha256

    context_forged = deepcopy(receipt)
    context_forged["slate_context"]["actual_score"] = 250.0
    context_forged.pop("publication_receipt_sha256")
    context_forged["publication_receipt_sha256"] = canonical_sha256(
        context_forged
    )
    with pytest.raises(
        operator.Week1OperatingBookOperatorError,
        match="fixed pre-lock law differs",
    ):
        operator.validate_week1_operating_book_publication_v1(context_forged)

    uri_forged = deepcopy(receipt)
    uri_forged["source_terminal_prelock_envelope_identity"]["uri"] = (
        "gs://test/outcomes/terminal-envelope.json"
    )
    uri_forged.pop("publication_receipt_sha256")
    uri_forged["publication_receipt_sha256"] = canonical_sha256(uri_forged)
    with pytest.raises(
        operator.Week1OperatingBookOperatorError,
        match="identity differs",
    ):
        operator.validate_week1_operating_book_publication_v1(uri_forged)


def test_exact_read_accepts_only_the_published_week1_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, source_identity, _calls = _arrange(monkeypatch)
    publication = operator.publish_week1_operating_book_v1(
        store=store,
        terminal_prelock_envelope_identity=source_identity,
        target_uri=TARGET_URI,
        k=80,
        observed_at="2026-09-13T14:30:00+00:00",
    )
    reopened = operator.read_week1_operating_book_v1(
        store=store,
        materialization_identity=publication["materialization_identity"],
    )
    assert reopened == {
        "identity": publication["materialization_identity"],
        "storage_created_at": OUTPUT_CREATED,
        "materialization": _materialization(80),
    }
    assert store.read_count_by_uri[ROOT_URI] == 2

    store.forge_reopen_uri = TARGET_URI
    with pytest.raises(
        operator.Week1OperatingBookOperatorError, match="exact read failed"
    ):
        operator.read_week1_operating_book_v1(
            store=store,
            materialization_identity=publication["materialization_identity"],
        )


def test_exact_read_rejects_drift_in_the_bound_terminal_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, source_identity, _calls = _arrange(monkeypatch)
    publication = operator.publish_week1_operating_book_v1(
        store=store,
        terminal_prelock_envelope_identity=source_identity,
        target_uri=TARGET_URI,
        k=80,
        observed_at="2026-09-13T14:30:00+00:00",
    )
    store.forge_reopen_uri = ROOT_URI
    with pytest.raises(
        operator.Week1OperatingBookOperatorError,
        match="terminal-root exact reopen/rebuild failed",
    ):
        operator.read_week1_operating_book_v1(
            store=store,
            materialization_identity=publication["materialization_identity"],
        )
