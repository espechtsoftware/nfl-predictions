"""Focused callback tests for the one-query Core v1 outcome supply."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from hashlib import sha256

import pytest

from nfl_dfs.research import corpus_core_v1_outcome_snapshot as snapshot
from nfl_dfs.research import corpus_core_v1_outcome_supply as supply
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_realized_outcome_transport as registered
from nfl_dfs.research import lr8_label_score_map as shared


def _identity(value: object, *, name: str) -> dict[str, object]:
    return batch.object_identity_for_json(
        value, uri=f"gs://core-outcome-test/{name}.json", generation="1"
    )


def _fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    tuple[snapshot.CoreOutcomeKey, ...],
]:
    source_freeze: dict[str, object] = {"fixture": "later-source"}
    source_freeze_identity = _identity(source_freeze, name="later-source")
    slates: list[dict[str, object]] = []
    keys: list[snapshot.CoreOutcomeKey] = []
    for source_ordinal in range(54):
        season = 2023 + source_ordinal // 18
        week = source_ordinal % 18 + 1
        slate_id = f"{season}-w{week:02d}"
        players = [f"s{source_ordinal:02d}-DST", *[
            f"s{source_ordinal:02d}-p{index:02d}" for index in range(8)
        ]]
        roster = sorted(players)
        slates.append({
            "source_ordinal": source_ordinal,
            "slate": {"season": season, "week": week, "slate_id": slate_id},
            "union_population": {"rosters": [roster]},
        })
        for player_id in roster:
            is_dst = player_id.endswith("-DST")
            keys.append(snapshot.CoreOutcomeKey(
                source_ordinal=source_ordinal,
                season=season,
                week=week,
                slate_id=slate_id,
                player_id=player_id,
                source_kind="dst" if is_dst else "skill",
                source_key=f"T{source_ordinal:02d}" if is_dst else player_id,
            ))
    retained_keys = tuple(sorted(
        keys, key=lambda row: (row.source_ordinal, row.player_id)
    ))
    catalog: dict[str, object] = {
        "catalog_sha256": "c" * 64,
        "later_source_freeze_identity": source_freeze_identity,
        "later_source_freeze_sha256": "f" * 64,
        "slates": slates,
    }
    catalog_identity = _identity(catalog, name="catalog")
    monkeypatch.setattr(
        supply.core, "validate_core_v1_catalog", lambda value: dict(value)
    )
    monkeypatch.setattr(
        snapshot.core, "validate_core_v1_catalog", lambda value: dict(value)
    )
    monkeypatch.setattr(
        supply.snapshot,
        "project_core_outcome_keys",
        lambda **kwargs: retained_keys,
    )
    return (
        catalog,
        catalog_identity,
        source_freeze,
        source_freeze_identity,
        retained_keys,
    )


def _config(*, enabled: bool = True) -> supply.CoreOutcomeSupplyConfig:
    return supply.CoreOutcomeSupplyConfig(
        run_id="core-v1-score-test",
        job="core-v1-realized-job",
        code_sha="a" * 40,
        image=f"us-docker.pkg.dev/test/core@sha256:{'b' * 64}",
        enabled=enabled,
    )


def _lease(config: supply.CoreOutcomeSupplyConfig) -> dict[str, object]:
    body = {
        "version": shared.adapter.HISTORICAL_OUTCOME_LEASE_VERSION,
        "run_id": config.run_id,
        "job": config.job,
        "code_sha": config.code_sha,
        "image": config.image,
        "acquired_at": "2026-08-25T00:00:00+00:00",
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
        "modified": "2026-08-24T00:00:00+00:00",
        "num_rows": 100,
        "schema_sha256": "d" * 64,
    }


class _Publisher:
    def __init__(self, events: list[str]):
        self.events = events
        self.payloads: dict[str, bytes] = {}
        self.objects: dict[str, registered.PublishedObject] = {}
        self._ordinal = 0
        self.fail_before: str | None = None
        self.fail_after: str | None = None

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
        self._ordinal += 1
        self.events.append(f"publish:{name}")
        self.payloads[uri] = raw
        created = datetime(
            2026, 8, 25, 0, 2 + self._ordinal * 2, tzinfo=timezone.utc
        ).isoformat()
        result = registered.PublishedObject(
            receipt={
                "uri": uri,
                "generation": str(100 + self._ordinal),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
                "create_only": True,
            },
            reopened_raw=raw,
            created_at=created,
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
        datetime(2026, 8, 25, 0, 1, tzinfo=timezone.utc),
        datetime(2026, 8, 25, 0, 2, tzinfo=timezone.utc),
    ))
    return lambda: next(values)


def _query_rows(
    keys: tuple[snapshot.CoreOutcomeKey, ...],
) -> list[dict[str, object]]:
    return [{
        "season": row.season,
        "week": row.week,
        "source_kind": row.source_kind,
        "source_key": row.source_key,
        "realized_score": "12.25",
    } for row in sorted(
        keys,
        key=lambda row: (row.season, row.week, row.source_kind, row.source_key),
    )]


class _QueryStore:
    def __init__(self, keys: tuple[snapshot.CoreOutcomeKey, ...]):
        self.rows = _query_rows(keys)
        self.calls = 0
        self.creations = 0
        self.fail_once = False
        self.poison_parameters = False
        self._receipt: dict[str, object] | None = None
        self._spec: registered.QuerySpec | None = None

    def __call__(
        self, spec: registered.QuerySpec,
    ) -> supply.CoreOutcomeQueryResult:
        self.calls += 1
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("fixture crash before fixed-ID job creation")
        if self._receipt is None:
            self.creations += 1
            self._spec = spec
            self._receipt = {
                "job_id": spec.job_id,
                "location": spec.location,
                "sql_sha256": spec.sql_sha256,
                "parameters_sha256": spec.parameters_sha256,
                "created": "2026-08-25T00:05:00+00:00",
                "started": "2026-08-25T00:05:30+00:00",
                "ended": "2026-08-25T00:06:00+00:00",
                "total_bytes_processed": 1,
                "cache_hit": False,
                "error_result": None,
            }
            disposition = "created"
        else:
            assert self._spec == spec
            disposition = "recovered"
        receipt = dict(self._receipt)
        if self.poison_parameters:
            receipt["parameters_sha256"] = "f" * 64
        return supply.CoreOutcomeQueryResult(
            disposition=disposition,
            result=shared.QueryResult(rows=self.rows, job_receipt=receipt),
        )


def test_supply_publishes_attempt_before_one_query_and_reusable_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog, catalog_identity, freeze, freeze_identity, keys = _fixture(monkeypatch)
    config = _config()
    lease = _lease(config)
    events: list[str] = []
    publisher = _Publisher(events)
    query_rows = [{
        "season": row.season,
        "week": row.week,
        "source_kind": row.source_kind,
        "source_key": row.source_key,
        "realized_score": "12.25",
    } for row in sorted(
        keys,
        key=lambda row: (row.season, row.week, row.source_kind, row.source_key),
    )]
    query_count = 0

    def execute(spec: registered.QuerySpec) -> supply.CoreOutcomeQueryResult:
        nonlocal query_count
        query_count += 1
        events.append("query")
        return supply.CoreOutcomeQueryResult(
            disposition="created",
            result=shared.QueryResult(rows=query_rows, job_receipt={
                "job_id": spec.job_id,
                "location": spec.location,
                "sql_sha256": spec.sql_sha256,
                "parameters_sha256": spec.parameters_sha256,
                "created": "2026-08-25T00:05:00+00:00",
                "started": "2026-08-25T00:05:30+00:00",
                "ended": "2026-08-25T00:06:00+00:00",
                "total_bytes_processed": 1,
                "cache_hit": False,
                "error_result": None,
            }),
        )

    result = supply.supply_core_v1_outcome_snapshot(
        config=config,
        catalog=catalog,
        catalog_identity=catalog_identity,
        source_freeze=freeze,
        source_freeze_identity=freeze_identity,
        verify_lease=lambda: lease,
        read_table_metadata=_metadata,
        get_or_create_query=execute,
        publish=publisher,
        read_known=publisher.read_known,
        clock=_clock(),
    )

    assert query_count == 1
    assert events.index("publish:read-attempt.json") < events.index("query")
    assert result.player_source["row_count"] == len(keys)
    assert result.outcome_snapshot["row_count"] == len(keys)
    assert result.completion["one_historical_outcome_read"] is True
    assert result.completion["historical_outcome_lease_release_required"] is True
    assert result.completion["rank_available"] is False
    assert result.completion["roi_available"] is False


def test_supply_rejects_table_drift_after_the_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog, catalog_identity, freeze, freeze_identity, keys = _fixture(monkeypatch)
    config = _config()
    lease = _lease(config)
    publisher = _Publisher([])
    reads = 0

    def metadata(table: str) -> dict[str, object]:
        nonlocal reads
        reads += 1
        return _metadata(table, etag="before" if reads <= 4 else "after")

    def execute(spec: registered.QuerySpec) -> supply.CoreOutcomeQueryResult:
        rows = [{
            "season": row.season,
            "week": row.week,
            "source_kind": row.source_kind,
            "source_key": row.source_key,
            "realized_score": "0",
        } for row in sorted(
            keys,
            key=lambda row: (
                row.season, row.week, row.source_kind, row.source_key
            ),
        )]
        return supply.CoreOutcomeQueryResult(
            disposition="created",
            result=shared.QueryResult(rows=rows, job_receipt={
            "job_id": spec.job_id,
            "location": spec.location,
            "sql_sha256": spec.sql_sha256,
            "parameters_sha256": spec.parameters_sha256,
            "created": "2026-08-25T00:05:00+00:00",
            "started": "2026-08-25T00:05:30+00:00",
            "ended": "2026-08-25T00:06:00+00:00",
            "total_bytes_processed": 1,
            "cache_hit": False,
            "error_result": None,
            }),
        )

    with pytest.raises(
        supply.CorpusCoreV1OutcomeSupplyError,
        match="metadata changed",
    ):
        supply.supply_core_v1_outcome_snapshot(
            config=config,
            catalog=catalog,
            catalog_identity=catalog_identity,
            source_freeze=freeze,
            source_freeze_identity=freeze_identity,
            verify_lease=lambda: lease,
            read_table_metadata=metadata,
            get_or_create_query=execute,
            publish=publisher,
            read_known=publisher.read_known,
            clock=_clock(),
        )


def test_supply_is_default_off_before_any_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog, catalog_identity, freeze, freeze_identity, _ = _fixture(monkeypatch)
    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("default-off supply invoked a callback")

    with pytest.raises(
        supply.CorpusCoreV1OutcomeSupplyError,
        match="default-off",
    ):
        supply.supply_core_v1_outcome_snapshot(
            config=_config(enabled=False),
            catalog=catalog,
            catalog_identity=catalog_identity,
            source_freeze=freeze,
            source_freeze_identity=freeze_identity,
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
        "after-source",
        "after-snapshot",
        "after-completion",
    ),
)
def test_supply_recovers_every_partial_publication_without_a_second_job(
    monkeypatch: pytest.MonkeyPatch,
    crash_point: str,
) -> None:
    catalog, catalog_identity, freeze, freeze_identity, keys = _fixture(monkeypatch)
    config = _config()
    lease = _lease(config)
    publisher = _Publisher([])
    query = _QueryStore(keys)
    lease_calls = 0
    metadata_calls = 0

    def verify() -> dict[str, object]:
        nonlocal lease_calls
        lease_calls += 1
        return lease

    def metadata(table: str) -> dict[str, object]:
        nonlocal metadata_calls
        metadata_calls += 1
        return _metadata(table)

    if crash_point == "after-attempt":
        query.fail_once = True
    elif crash_point == "after-query":
        publisher.fail_before = "player-score-source.json"
    elif crash_point == "after-source":
        publisher.fail_before = "player-outcome-snapshot.json"
    elif crash_point == "after-snapshot":
        publisher.fail_before = "completion.json"

    clock = _clock()

    def run() -> supply.CoreOutcomeSupply:
        return supply.supply_core_v1_outcome_snapshot(
            config=config,
            catalog=catalog,
            catalog_identity=catalog_identity,
            source_freeze=freeze,
            source_freeze_identity=freeze_identity,
            verify_lease=verify,
            read_table_metadata=metadata,
            get_or_create_query=query,
            publish=publisher,
            read_known=publisher.read_known,
            clock=clock,
        )

    if crash_point == "after-completion":
        first = run()
        assert first.completion["one_historical_outcome_read"] is True
    else:
        with pytest.raises(supply.CorpusCoreV1OutcomeSupplyError):
            run()
    recovered = run()
    assert recovered.completion["one_historical_outcome_read"] is True
    assert query.creations == 1
    assert len(publisher.objects) == 4

    observed = (lease_calls, metadata_calls, query.calls)

    def forbidden(*args, **kwargs):
        raise AssertionError("completed recovery invoked a live callback")

    replayed = supply.supply_core_v1_outcome_snapshot(
        config=config,
        catalog=catalog,
        catalog_identity=catalog_identity,
        source_freeze=freeze,
        source_freeze_identity=freeze_identity,
        verify_lease=forbidden,
        read_table_metadata=forbidden,
        get_or_create_query=forbidden,
        publish=forbidden,
        read_known=publisher.read_known,
        clock=forbidden,
    )
    assert replayed.completion == recovered.completion
    assert (lease_calls, metadata_calls, query.calls) == observed


def test_supply_recovers_an_ambiguous_successful_upload_by_known_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog, catalog_identity, freeze, freeze_identity, keys = _fixture(monkeypatch)
    config = _config()
    publisher = _Publisher([])
    publisher.fail_after = "player-score-source.json"
    result = supply.supply_core_v1_outcome_snapshot(
        config=config,
        catalog=catalog,
        catalog_identity=catalog_identity,
        source_freeze=freeze,
        source_freeze_identity=freeze_identity,
        verify_lease=lambda: _lease(config),
        read_table_metadata=_metadata,
        get_or_create_query=_QueryStore(keys),
        publish=publisher,
        read_known=publisher.read_known,
        clock=_clock(),
    )
    assert result.player_source_identity["uri"].endswith(
        "/player-score-source.json"
    )


def test_supply_rejects_a_mismatched_recovered_fixed_id_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog, catalog_identity, freeze, freeze_identity, keys = _fixture(monkeypatch)
    config = _config()
    publisher = _Publisher([])
    publisher.fail_before = "player-score-source.json"
    query = _QueryStore(keys)

    def run() -> supply.CoreOutcomeSupply:
        return supply.supply_core_v1_outcome_snapshot(
            config=config,
            catalog=catalog,
            catalog_identity=catalog_identity,
            source_freeze=freeze,
            source_freeze_identity=freeze_identity,
            verify_lease=lambda: _lease(config),
            read_table_metadata=_metadata,
            get_or_create_query=query,
            publish=publisher,
            read_known=publisher.read_known,
            clock=_clock(),
        )

    with pytest.raises(supply.CorpusCoreV1OutcomeSupplyError):
        run()
    query.poison_parameters = True
    with pytest.raises(
        supply.CorpusCoreV1OutcomeSupplyError,
        match="query job identity differs",
    ):
        run()
    assert query.creations == 1
