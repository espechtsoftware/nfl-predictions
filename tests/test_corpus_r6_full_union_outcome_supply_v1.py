"""Focused offline tests for the recoverable R6 full-union outcome supply."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_outcome_snapshot_v1 as snapshot
from nfl_dfs.research import corpus_r6_full_union_outcome_supply_v1 as supply
from nfl_dfs.research import corpus_realized_outcome_transport as registered
from nfl_dfs.research import lr8_label_score_map as shared


SNAPSHOT_MODULE_SHA = "5" * 64
SNAPSHOT_CLI_SHA = "6" * 64
SNAPSHOT_TEST_SHA = "7" * 64
SNAPSHOT_CLI_TEST_SHA = "8" * 64


def _identity(value: object, *, name: str) -> dict[str, object]:
    return batch.object_identity_for_json(
        value, uri=f"gs://r6-outcome-test/{name}.json", generation="1"
    )


def _config(*, enabled: bool = True) -> supply.FullUnionOutcomeSupplyConfigV1:
    return supply.FullUnionOutcomeSupplyConfigV1(
        run_id="r6-full-union-score-test",
        job="r6-realized-job",
        code_sha="a" * 40,
        image=f"us-docker.pkg.dev/test/r6@sha256:{'b' * 64}",
        enabled=enabled,
    )


def _root_identity() -> dict[str, object]:
    return {
        "uri": (
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "corpus-r6-full-union-freezes/fixture/panel-freeze.json"
        ),
        "generation": "11",
        "sha256": "1" * 64,
        "bytes": 123,
    }


def _lease(config: supply.FullUnionOutcomeSupplyConfigV1) -> dict[str, object]:
    body = {
        "version": shared.adapter.HISTORICAL_OUTCOME_LEASE_VERSION,
        "run_id": config.run_id,
        "job": config.job,
        "code_sha": config.code_sha,
        "image": config.image,
        "acquired_at": "2026-08-26T00:00:00+00:00",
    }
    raw = shared.canonical_json(body)
    return {
        "body": body,
        "object_receipt": {
            "uri": shared.adapter.HISTORICAL_OUTCOME_LEASE_URI,
            "generation": "10",
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
            "create_only": True,
        },
    }


def _metadata(table: str, *, etag: str = "stable") -> dict[str, object]:
    return {
        "table_id": table,
        "etag": etag,
        "modified": "2026-08-25T00:00:00+00:00",
        "num_rows": 100,
        "schema_sha256": "d" * 64,
    }


def _fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    dict[str, object],
    dict[str, object],
    tuple[snapshot.OutcomeKeyV1, ...],
]:
    root_identity = _root_identity()
    later_identity = {
        "uri": "gs://r6-outcome-test/later-source-freeze.json",
        "generation": "9",
        "sha256": "2" * 64,
        "bytes": 456,
    }
    keys = (
        snapshot.OutcomeKeyV1(
            source_ordinal=0,
            season=2023,
            week=1,
            slate_id="2023-w01",
            player_id="AAA-DST",
            position="DST",
            team="AAA",
            source_kind="dst",
            source_key="AAA",
        ),
        snapshot.OutcomeKeyV1(
            source_ordinal=0,
            season=2023,
            week=1,
            slate_id="2023-w01",
            player_id="00-player",
            position="WR",
            team="AAA",
            source_kind="skill",
            source_key="00-player",
        ),
    )
    key_payload = [
        {
            "source_ordinal": row.source_ordinal,
            "season": row.season,
            "week": row.week,
            "slate_id": row.slate_id,
            "player_id": row.player_id,
            "position": row.position,
            "team": row.team,
            "source_kind": row.source_kind,
            "source_key": row.source_key,
        }
        for row in keys
    ]
    projection = {
        "schema_version": snapshot.OUTCOME_KEY_PROJECTION_SCHEMA,
        "panel_freeze_identity": root_identity,
        "panel_freeze_sha256": "3" * 64,
        "later_source_freeze_identity": later_identity,
        "later_source_freeze_sha256": "4" * 64,
        "outcome_key_count": len(keys),
        "outcome_keys_sha256": supply.canonical_sha256(key_payload),
        "complete": True,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
    }
    projection["outcome_key_projection_sha256"] = supply.canonical_sha256(
        projection
    )

    def project(*, panel_freeze_identity, read_exact):
        assert panel_freeze_identity == root_identity
        assert callable(read_exact)
        return dict(projection)

    def validate_projection(value, *, identity, read_exact):
        assert callable(read_exact)
        normalized = batch.validate_json_identity(
            value, identity, label="fixture projection"
        )
        assert dict(value) == projection
        return dict(value), normalized, keys

    def validate_smoke(
        value,
        *,
        identity,
        expected_panel_freeze_identity,
        outcome_key_projection,
        expected_outcome_key_projection_identity,
        expected_reviewed_source_commit_sha,
        expected_runtime_immutable_image,
        expected_snapshot_module_sha256,
        expected_snapshot_cli_sha256,
        expected_snapshot_test_sha256,
        expected_snapshot_cli_test_sha256,
        read_exact,
    ):
        assert callable(read_exact)
        assert expected_panel_freeze_identity == root_identity
        assert outcome_key_projection == projection
        assert value["outcome_key_projection_identity"] == (
            expected_outcome_key_projection_identity
        )
        assert expected_reviewed_source_commit_sha == "a" * 40
        assert expected_runtime_immutable_image == (
            f"us-docker.pkg.dev/test/r6@sha256:{'b' * 64}"
        )
        assert expected_snapshot_module_sha256 == SNAPSHOT_MODULE_SHA
        assert expected_snapshot_cli_sha256 == SNAPSHOT_CLI_SHA
        assert expected_snapshot_test_sha256 == SNAPSHOT_TEST_SHA
        assert expected_snapshot_cli_test_sha256 == SNAPSHOT_CLI_TEST_SHA
        normalized = batch.validate_json_identity(
            value, identity, label="fixture smoke receipt"
        )
        return dict(value), normalized

    def build_source(
        *,
        outcome_key_projection,
        outcome_key_projection_identity,
        registered_integer_micro_rows,
        read_exact,
    ):
        assert outcome_key_projection == projection
        assert callable(read_exact)
        rows = [dict(row) for row in registered_integer_micro_rows]
        body = {
            "schema_version": snapshot.REALIZED_SOURCE_SCHEMA,
            "outcome_key_projection_identity": outcome_key_projection_identity,
            "outcome_key_projection_sha256": projection[
                "outcome_key_projection_sha256"
            ],
            "panel_freeze_identity": root_identity,
            "panel_freeze_sha256": projection["panel_freeze_sha256"],
            "later_source_freeze_identity": later_identity,
            "later_source_freeze_sha256": projection[
                "later_source_freeze_sha256"
            ],
            "row_count": len(rows),
            "rows": rows,
        }
        body["realized_source_sha256"] = supply.canonical_sha256(body)
        return body

    def validate_source(
        value,
        *,
        identity,
        outcome_key_projection,
        outcome_key_projection_identity,
        read_exact,
    ):
        expected = build_source(
            outcome_key_projection=outcome_key_projection,
            outcome_key_projection_identity=outcome_key_projection_identity,
            registered_integer_micro_rows=value["rows"],
            read_exact=read_exact,
        )
        assert value == expected
        normalized = batch.validate_json_identity(
            value, identity, label="fixture source"
        )
        return dict(value), normalized, [dict(row) for row in value["rows"]]

    def build_snapshot(
        *,
        outcome_key_projection,
        outcome_key_projection_identity,
        realized_source,
        realized_source_identity,
        read_exact,
    ):
        assert outcome_key_projection == projection
        assert callable(read_exact)
        body = {
            "schema_version": snapshot.OUTCOME_SNAPSHOT_SCHEMA,
            "outcome_key_projection_identity": outcome_key_projection_identity,
            "panel_freeze_identity": root_identity,
            "later_source_freeze_identity": later_identity,
            "realized_source_identity": realized_source_identity,
            "realized_source_sha256": realized_source[
                "realized_source_sha256"
            ],
            "row_count": realized_source["row_count"],
            "rows_sha256": supply.canonical_sha256(realized_source["rows"]),
        }
        body["outcome_snapshot_sha256"] = supply.canonical_sha256(body)
        return body

    def validate_snapshot(value, *, identity, **kwargs):
        expected = build_snapshot(**kwargs)
        assert value == expected
        normalized = batch.validate_json_identity(
            value, identity, label="fixture snapshot"
        )
        return dict(value), normalized, {}

    monkeypatch.setattr(
        supply.snapshot, "project_required_outcome_keys_v1", project
    )
    monkeypatch.setattr(
        supply.snapshot, "validate_outcome_key_projection_v1",
        validate_projection,
    )
    monkeypatch.setattr(
        supply.snapshot,
        "validate_actual_root_smoke_receipt_v1",
        validate_smoke,
    )
    monkeypatch.setattr(
        supply.snapshot, "build_realized_source_from_registered_rows_v1",
        build_source,
    )
    monkeypatch.setattr(
        supply.snapshot, "validate_realized_source_v1", validate_source
    )
    monkeypatch.setattr(
        supply.snapshot, "build_outcome_snapshot_v1", build_snapshot
    )
    monkeypatch.setattr(
        supply.snapshot, "validate_outcome_snapshot_v1", validate_snapshot
    )
    return root_identity, projection, keys


class _Publisher:
    def __init__(self, events: list[str]):
        self.events = events
        self.objects: dict[str, registered.PublishedObject] = {}
        self.fail_before: str | None = None
        self.fail_after: str | None = None

    @staticmethod
    def _created_at(name: str) -> str:
        time_by_name = {
            "outcome-key-projection.json": (0, 10),
            "actual-root-smoke-receipt.json": (0, 30),
            "read-attempt.json": (3, 30),
            "query-evidence.json": (6, 30),
            "realized-source.json": (7, 30),
            "outcome-snapshot.json": (8, 30),
            "completion.json": (9, 30),
        }
        minute, second = time_by_name[name]
        return datetime(
            2026, 8, 26, 0, minute, second, tzinfo=timezone.utc
        ).isoformat()

    def __call__(self, uri: str, raw: bytes) -> registered.PublishedObject:
        name = uri.rsplit("/", 1)[-1]
        if self.fail_before == name:
            self.fail_before = None
            raise RuntimeError(f"fixture crash before {name}")
        existing = self.objects.get(uri)
        if existing is not None:
            return registered.PublishedObject(
                receipt=existing.receipt,
                reopened_raw=existing.reopened_raw,
                created_at=existing.created_at,
                created=False,
            )
        self.events.append(f"publish:{name}")
        result = registered.PublishedObject(
            receipt={
                "uri": uri,
                "generation": str(100 + len(self.objects)),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
                "create_only": True,
            },
            reopened_raw=raw,
            created_at=self._created_at(name),
            created=True,
        )
        self.objects[uri] = result
        if self.fail_after == name:
            self.fail_after = None
            raise RuntimeError(f"fixture ambiguous crash after {name}")
        return result

    def read_known(self, uri: str) -> registered.PublishedObject | None:
        existing = self.objects.get(uri)
        if existing is None:
            return None
        return registered.PublishedObject(
            receipt=existing.receipt,
            reopened_raw=existing.reopened_raw,
            created_at=existing.created_at,
            created=False,
        )


def _clock() -> Callable[[], datetime]:
    values = iter((
        datetime(2026, 8, 26, 0, 1, tzinfo=timezone.utc),
        datetime(2026, 8, 26, 0, 2, tzinfo=timezone.utc),
    ))
    return lambda: next(values)


class _QueryStore:
    def __init__(self, keys: tuple[snapshot.OutcomeKeyV1, ...]):
        self.rows = [
            {
                "season": row.season,
                "week": row.week,
                "source_kind": row.source_kind,
                "source_key": row.source_key,
                "realized_score": "12.25",
            }
            for row in sorted(
                keys,
                key=lambda row: (
                    row.season, row.week, row.source_kind, row.source_key
                ),
            )
        ]
        self.calls = 0
        self.creations = 0
        self.fail_once = False
        self.spec: registered.QuerySpec | None = None
        self.receipt: dict[str, object] | None = None

    def __call__(
        self, spec: registered.QuerySpec,
    ) -> supply.FullUnionOutcomeQueryResultV1:
        self.calls += 1
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("fixture crash before fixed-ID query creation")
        if self.receipt is None:
            self.creations += 1
            self.spec = spec
            self.receipt = {
                "job_id": spec.job_id,
                "location": spec.location,
                "sql_sha256": spec.sql_sha256,
                "parameters_sha256": spec.parameters_sha256,
                "created": "2026-08-26T00:04:00+00:00",
                "started": "2026-08-26T00:04:30+00:00",
                "ended": "2026-08-26T00:05:00+00:00",
                "total_bytes_processed": 1,
                "cache_hit": False,
                "error_result": None,
            }
            disposition = "created"
        else:
            assert self.spec == spec
            disposition = "recovered"
        return supply.FullUnionOutcomeQueryResultV1(
            disposition=disposition,
            result=shared.QueryResult(
                rows=self.rows, job_receipt=dict(self.receipt)
            ),
        )


def _content_identity(value: registered.PublishedObject) -> dict[str, object]:
    return {
        key: value.receipt[key]
        for key in ("uri", "generation", "sha256", "bytes")
    }


def _prime_smoke(
    *,
    config: supply.FullUnionOutcomeSupplyConfigV1,
    root_identity: dict[str, object],
    projection: dict[str, object],
    publisher: _Publisher,
) -> tuple[
    dict[str, object], dict[str, object],
    dict[str, object], dict[str, object],
]:
    projection_object = publisher(
        f"{config.output_root}/outcome-key-projection.json",
        supply.canonical_json_bytes(projection),
    )
    projection_identity = _content_identity(projection_object)
    smoke = {
        "schema_version": snapshot.ACTUAL_ROOT_SMOKE_RECEIPT_SCHEMA,
        "panel_freeze_identity": root_identity,
        "panel_freeze_sha256": projection["panel_freeze_sha256"],
        "outcome_key_projection_identity": projection_identity,
        "outcome_key_projection_sha256": projection[
            "outcome_key_projection_sha256"
        ],
        "reviewed_source_commit_sha": config.code_sha,
        "runtime_immutable_image": config.image,
    }
    smoke["actual_root_smoke_receipt_sha256"] = supply.canonical_sha256(
        smoke
    )
    smoke_object = publisher(
        f"{config.output_root}/actual-root-smoke-receipt.json",
        supply.canonical_json_bytes(smoke),
    )
    return projection, projection_identity, smoke, _content_identity(smoke_object)


def _run(
    *,
    config: supply.FullUnionOutcomeSupplyConfigV1,
    root_identity: dict[str, object],
    projection: dict[str, object],
    lease: dict[str, object],
    publisher: _Publisher,
    query: _QueryStore,
    clock: Callable[[], datetime],
    metadata: Callable[[str], dict[str, object]] = _metadata,
    lease_verifier: Callable[[], dict[str, object]] | None = None,
) -> supply.FullUnionOutcomeSupplyV1:
    (
        retained_projection,
        projection_identity,
        smoke,
        smoke_identity,
    ) = _prime_smoke(
        config=config,
        root_identity=root_identity,
        projection=projection,
        publisher=publisher,
    )
    return supply.supply_full_union_outcome_snapshot_v1(
        config=config,
        panel_freeze_identity=root_identity,
        outcome_key_projection=retained_projection,
        outcome_key_projection_identity=projection_identity,
        actual_root_smoke_receipt=smoke,
        actual_root_smoke_receipt_identity=smoke_identity,
        snapshot_module_sha256=SNAPSHOT_MODULE_SHA,
        snapshot_cli_sha256=SNAPSHOT_CLI_SHA,
        snapshot_test_sha256=SNAPSHOT_TEST_SHA,
        snapshot_cli_test_sha256=SNAPSHOT_CLI_TEST_SHA,
        read_exact=lambda identity: b"unused by patched snapshot fixture",
        verify_lease=(
            (lambda: lease) if lease_verifier is None else lease_verifier
        ),
        read_table_metadata=metadata,
        get_or_create_query=query,
        publish=publisher,
        read_known=publisher.read_known,
        clock=clock,
    )


def test_supply_binds_root_and_attempt_before_one_fixed_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_identity, projection, keys = _fixture(monkeypatch)
    config = _config()
    events: list[str] = []
    publisher = _Publisher(events)
    query = _QueryStore(keys)

    def execute(spec: registered.QuerySpec):
        events.append("query")
        return query(spec)

    (
        retained_projection,
        projection_identity,
        smoke,
        smoke_identity,
    ) = _prime_smoke(
        config=config,
        root_identity=root_identity,
        projection=projection,
        publisher=publisher,
    )
    result = supply.supply_full_union_outcome_snapshot_v1(
        config=config,
        panel_freeze_identity=root_identity,
        outcome_key_projection=retained_projection,
        outcome_key_projection_identity=projection_identity,
        actual_root_smoke_receipt=smoke,
        actual_root_smoke_receipt_identity=smoke_identity,
        snapshot_module_sha256=SNAPSHOT_MODULE_SHA,
        snapshot_cli_sha256=SNAPSHOT_CLI_SHA,
        snapshot_test_sha256=SNAPSHOT_TEST_SHA,
        snapshot_cli_test_sha256=SNAPSHOT_CLI_TEST_SHA,
        read_exact=lambda identity: b"unused",
        verify_lease=lambda: _lease(config),
        read_table_metadata=_metadata,
        get_or_create_query=execute,
        publish=publisher,
        read_known=publisher.read_known,
        clock=_clock(),
    )

    assert query.calls == query.creations == 1
    assert events.index("publish:read-attempt.json") < events.index("query")
    assert events.index("query") < events.index("publish:query-evidence.json")
    assert result.attempt["panel_freeze_identity"] == root_identity
    assert result.attempt["panel_freeze_sha256"] == projection[
        "panel_freeze_sha256"
    ]
    assert result.attempt["actual_root_smoke_receipt_identity"] == (
        smoke_identity
    )
    assert result.query_evidence[
        "actual_root_smoke_receipt_identity"
    ] == smoke_identity
    assert result.completion[
        "actual_root_smoke_receipt_identity"
    ] == smoke_identity
    assert result.realized_source["later_source_freeze_identity"] == (
        projection["later_source_freeze_identity"]
    )
    assert result.outcome_snapshot["panel_freeze_identity"] == root_identity
    assert root_identity["sha256"] in result.completion["query_job_id"]
    assert config.run_id.replace("-", "_") in result.completion["query_job_id"]
    assert result.query_evidence["query_cache_used"] is False
    assert result.completion["one_historical_outcome_read"] is True
    assert result.completion["rank_available"] is False
    assert result.completion["roi_available"] is False
    assert result.completion["decision_authority"] is False


def test_supply_is_default_off_before_any_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_identity, _, _ = _fixture(monkeypatch)
    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("default-off supply invoked a callback")

    with pytest.raises(
        supply.CorpusR6FullUnionOutcomeSupplyV1Error, match="default-off"
    ):
        supply.supply_full_union_outcome_snapshot_v1(
            config=_config(enabled=False),
            panel_freeze_identity=root_identity,
            outcome_key_projection={},
            outcome_key_projection_identity={},
            actual_root_smoke_receipt={},
            actual_root_smoke_receipt_identity={},
            snapshot_module_sha256=SNAPSHOT_MODULE_SHA,
            snapshot_cli_sha256=SNAPSHOT_CLI_SHA,
            snapshot_test_sha256=SNAPSHOT_TEST_SHA,
            snapshot_cli_test_sha256=SNAPSHOT_CLI_TEST_SHA,
            read_exact=forbidden,
            verify_lease=forbidden,
            read_table_metadata=forbidden,
            get_or_create_query=forbidden,
            publish=forbidden,
            read_known=forbidden,
            clock=forbidden,
        )
    assert called is False


@pytest.mark.parametrize(
    "crash_point",
    (
        "after-attempt",
        "after-query",
        "after-evidence",
        "after-source",
        "after-snapshot",
        "after-completion",
    ),
)
def test_every_partial_state_recovers_without_a_second_query_job(
    monkeypatch: pytest.MonkeyPatch, crash_point: str,
) -> None:
    root_identity, projection, keys = _fixture(monkeypatch)
    config = _config()
    lease = _lease(config)
    publisher = _Publisher([])
    query = _QueryStore(keys)
    if crash_point == "after-attempt":
        query.fail_once = True
    elif crash_point == "after-query":
        publisher.fail_before = "query-evidence.json"
    elif crash_point == "after-evidence":
        publisher.fail_before = "realized-source.json"
    elif crash_point == "after-source":
        publisher.fail_before = "outcome-snapshot.json"
    elif crash_point == "after-snapshot":
        publisher.fail_before = "completion.json"

    clock = _clock()

    def run() -> supply.FullUnionOutcomeSupplyV1:
        return _run(
            config=config,
            root_identity=root_identity,
            projection=projection,
            lease=lease,
            publisher=publisher,
            query=query,
            clock=clock,
        )

    if crash_point == "after-completion":
        first = run()
        assert first.completion["one_exact_query_job"] is True
    else:
        with pytest.raises(supply.CorpusR6FullUnionOutcomeSupplyV1Error):
            run()
    recovered = run()
    assert recovered.completion["one_exact_query_job"] is True
    assert query.creations == 1
    assert len(publisher.objects) == 7

    observed_calls = query.calls

    def forbidden(*args, **kwargs):
        raise AssertionError("closed recovery invoked a live callback")

    (
        retained_projection,
        projection_identity,
        smoke,
        smoke_identity,
    ) = _prime_smoke(
        config=config,
        root_identity=root_identity,
        projection=projection,
        publisher=publisher,
    )
    replayed = supply.supply_full_union_outcome_snapshot_v1(
        config=config,
        panel_freeze_identity=root_identity,
        outcome_key_projection=retained_projection,
        outcome_key_projection_identity=projection_identity,
        actual_root_smoke_receipt=smoke,
        actual_root_smoke_receipt_identity=smoke_identity,
        snapshot_module_sha256=SNAPSHOT_MODULE_SHA,
        snapshot_cli_sha256=SNAPSHOT_CLI_SHA,
        snapshot_test_sha256=SNAPSHOT_TEST_SHA,
        snapshot_cli_test_sha256=SNAPSHOT_CLI_TEST_SHA,
        read_exact=lambda identity: b"unused",
        verify_lease=forbidden,
        read_table_metadata=forbidden,
        get_or_create_query=forbidden,
        publish=forbidden,
        read_known=publisher.read_known,
        clock=forbidden,
    )
    assert replayed.completion == recovered.completion
    assert query.calls == observed_calls


def test_ambiguous_query_evidence_upload_recovers_by_known_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_identity, projection, keys = _fixture(monkeypatch)
    config = _config()
    publisher = _Publisher([])
    publisher.fail_after = "query-evidence.json"

    result = _run(
        config=config,
        root_identity=root_identity,
        projection=projection,
        lease=_lease(config),
        publisher=publisher,
        query=_QueryStore(keys),
        clock=_clock(),
    )

    assert result.query_evidence_identity["uri"].endswith(
        "/query-evidence.json"
    )


def test_supply_rejects_reordered_authoritative_query_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_identity, projection, keys = _fixture(monkeypatch)
    config = _config()
    query = _QueryStore(keys)
    query.rows.reverse()
    with pytest.raises(
        supply.CorpusR6FullUnionOutcomeSupplyV1Error,
        match="exact ordered player/DST union",
    ):
        _run(
            config=config,
            root_identity=root_identity,
            projection=projection,
            lease=_lease(config),
            publisher=_Publisher([]),
            query=query,
            clock=_clock(),
        )
    assert query.creations == 1


@pytest.mark.parametrize(
    ("drift_point", "message", "lease_sequence"),
    (
        ("before", "changed before the query", ("stable", "drift")),
        ("during", "changed during the query", ("stable", "stable", "drift")),
    ),
)
def test_supply_rejects_lease_drift_before_or_during_query(
    monkeypatch: pytest.MonkeyPatch,
    drift_point: str,
    message: str,
    lease_sequence: tuple[str, ...],
) -> None:
    root_identity, projection, keys = _fixture(monkeypatch)
    config = _config()
    stable = _lease(config)
    drift = deepcopy(stable)
    drift["object_receipt"]["generation"] = "11"
    values = iter(
        deepcopy(stable) if marker == "stable" else deepcopy(drift)
        for marker in lease_sequence
    )
    query = _QueryStore(keys)

    with pytest.raises(
        supply.CorpusR6FullUnionOutcomeSupplyV1Error, match=message
    ):
        _run(
            config=config,
            root_identity=root_identity,
            projection=projection,
            lease=stable,
            publisher=_Publisher([]),
            query=query,
            clock=_clock(),
            lease_verifier=lambda: next(values),
        )
    assert query.creations == (0 if drift_point == "before" else 1)


def test_supply_rejects_table_drift_and_inexact_float_scores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_identity, projection, keys = _fixture(monkeypatch)
    config = _config()
    publisher = _Publisher([])
    reads = 0

    def drifting_metadata(table: str) -> dict[str, object]:
        nonlocal reads
        reads += 1
        return _metadata(table, etag="before" if reads <= 4 else "after")

    with pytest.raises(
        supply.CorpusR6FullUnionOutcomeSupplyV1Error,
        match="metadata changed during",
    ):
        _run(
            config=config,
            root_identity=root_identity,
            projection=projection,
            lease=_lease(config),
            publisher=publisher,
            query=_QueryStore(keys),
            clock=_clock(),
            metadata=drifting_metadata,
        )

    publisher = _Publisher([])
    query = _QueryStore(keys)
    query.rows[0]["realized_score"] = 12.25
    with pytest.raises(
        supply.CorpusR6FullUnionOutcomeSupplyV1Error,
        match="exact decimal data",
    ):
        _run(
            config=config,
            root_identity=root_identity,
            projection=projection,
            lease=_lease(config),
            publisher=publisher,
            query=query,
            clock=_clock(),
        )
