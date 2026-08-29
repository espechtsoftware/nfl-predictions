from __future__ import annotations

from hashlib import sha256
from pathlib import PurePosixPath
from types import SimpleNamespace

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_outcome_supply_v1 as base_supply
from nfl_dfs.research import corpus_realized_outcome_transport as registered
from nfl_dfs.research import lr8_label_score_map as shared
from scripts import run_corpus_r6_catalog_wide_outcome_successor_v1 as operator


class FakeStore:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.objects: dict[str, registered.PublishedObject] = {}
        self._generation = 0

    def seed(self, identity: dict[str, object], body: dict[str, object]) -> None:
        raw = batch.canonical_json_bytes(body)
        assert identity["sha256"] == sha256(raw).hexdigest()
        assert identity["bytes"] == len(raw)
        self.objects[str(identity["uri"])] = registered.PublishedObject(
            receipt={**identity, "create_only": True},
            reopened_raw=raw,
            created_at="2026-08-29T00:00:00+00:00",
            created=False,
        )

    def read_exact(self, value: dict[str, object]) -> bytes:
        self.events.append(f"read:{PurePosixPath(str(value['uri'])).name}")
        observed = self.objects[str(value["uri"])]
        for key in ("uri", "generation", "sha256", "bytes"):
            assert str(observed.receipt[key]) == str(value[key])
        return observed.reopened_raw

    def resolve_known(
        self, uri: str, *, absent_ok: bool
    ) -> registered.PublishedObject | None:
        del absent_ok
        self.events.append(f"resolve:{PurePosixPath(uri).name}")
        return self.objects.get(uri)

    def resolve_required(self, uri: str) -> registered.PublishedObject:
        value = self.resolve_known(uri, absent_ok=False)
        assert value is not None
        return value

    def publish(self, uri: str, raw: bytes) -> registered.PublishedObject:
        name = PurePosixPath(uri).name
        self.events.append(f"publish:{name}")
        existing = self.objects.get(uri)
        if existing is not None:
            assert existing.reopened_raw == raw
            return registered.PublishedObject(
                receipt=existing.receipt,
                reopened_raw=raw,
                created_at=existing.created_at,
                created=False,
            )
        self._generation += 1
        identity = {
            "uri": uri,
            "generation": str(self._generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        value = registered.PublishedObject(
            receipt={**identity, "create_only": True},
            reopened_raw=raw,
            created_at="2026-08-29T00:00:00+00:00",
            created=True,
        )
        self.objects[uri] = value
        return value

    def replace(
        self, uri: str, body: dict[str, object], *, generation: str
    ) -> registered.PublishedObject:
        raw = batch.canonical_json_bytes(body)
        identity = {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        value = registered.PublishedObject(
            receipt={**identity, "create_only": True},
            reopened_raw=raw,
            created_at="2026-08-29T00:00:00+00:00",
            created=False,
        )
        self.objects[uri] = value
        return value


def config(*, enabled: bool = True) -> operator.OperatorConfigV1:
    return operator.OperatorConfigV1(
        run_id="20260829-catalog-wide-test-v1",
        job="shared-outcome-job",
        code_sha="a" * 40,
        image="us-docker.pkg.dev/test/image@sha256:" + "b" * 64,
        enabled=enabled,
    )


def projection_pair() -> tuple[dict[str, object], dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(operator.EXPECTED_CATALOG_KEY_COUNT):
        source_ordinal = index % operator.EXPECTED_SOURCE_SLATE_COUNT
        season = 2023 + source_ordinal // 18
        week = source_ordinal % 18 + 1
        is_delta_dst = index == operator.EXPECTED_BASE_KEY_COUNT
        player_id = "DST_ZZZ" if is_delta_dst else f"p-{index:05d}"
        team = "ZZZ" if is_delta_dst else f"T{source_ordinal:02d}"
        rows.append(
            {
                "source_ordinal": source_ordinal,
                "season": season,
                "week": week,
                "slate_id": f"{season}-w{week:02d}",
                "player_id": player_id,
                "position": "DST" if is_delta_dst else "WR",
                "team": team,
                "source_kind": "dst" if is_delta_dst else "skill",
                "source_key": team if is_delta_dst else player_id,
            }
        )
    projection = {
        "source_slate_count": operator.EXPECTED_SOURCE_SLATE_COUNT,
        "outcome_key_count": len(rows),
        "outcome_keys": rows,
        "outcome_key_projection_sha256": operator.successor.digest(rows),
    }
    predecessor_rows = rows[: operator.EXPECTED_BASE_KEY_COUNT]
    predecessor = {
        "source_slate_count": operator.EXPECTED_SOURCE_SLATE_COUNT,
        "outcome_key_count": len(predecessor_rows),
        "outcome_keys": predecessor_rows,
    }
    return projection, predecessor


def test_default_disabled_precedes_every_transport_boundary() -> None:
    events: list[str] = []
    with pytest.raises(
        operator.CatalogWideOutcomeOperatorV1Error, match="disabled"
    ):
        operator.prepare_v1(config=config(enabled=False), store=FakeStore(events))
    assert events == []


def test_prepare_publishes_exact_delta_request_before_any_lease_or_query() -> None:
    events: list[str] = []
    store = FakeStore(events)
    projection, predecessor = projection_pair()

    prepared = operator._publish_prepared_v1(
        config=config(),
        store=store,
        projection=projection,
        predecessor=predecessor,
    )

    assert events == [
        "publish:outcome-key-projection.json",
        "publish:registered-request.json",
    ]
    assert len(prepared.delta_keys) == 15_358
    assert prepared.request["queried_key_count"] == 15_358
    assert prepared.request["source_snapshot_at"] == (
        "2026-08-26T23:58:47.451523+00:00"
    )
    assert prepared.request["uses_realized_outcomes"] is False
    assert prepared.request["query_execution_performed"] is False
    assert prepared.request["query_contract"]["job_id"] == prepared.query_spec.job_id
    assert prepared.request["query_contract"]["query_count"] == 1
    assert prepared.request["query_contract"]["use_query_cache"] is False
    assert not any("lease" in event or "query" in event for event in events)


def test_supply_recovers_fixed_job_and_publishes_strict_chain_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    store = FakeStore(events)
    projection, predecessor = projection_pair()
    base_rows = [
        {
            "source_ordinal": row["source_ordinal"],
            "player_id": row["player_id"],
        }
        for row in predecessor["outcome_keys"]
    ]
    base_body = {"rows": base_rows, "outcome_snapshot_sha256": "c" * 64}
    base_identity = batch.object_identity_for_json(
        base_body, uri="gs://fixture/base-outcome-snapshot.json", generation="31"
    )
    monkeypatch.setattr(operator, "BASE_OUTCOME_SNAPSHOT_IDENTITY", base_identity)
    monkeypatch.setattr(operator, "BASE_OUTCOME_SNAPSHOT_SHA256", "c" * 64)
    store.seed(base_identity, base_body)
    prepared = operator._publish_prepared_v1(
        config=config(), store=store, projection=projection, predecessor=predecessor
    )
    later_source = {"outcome_blind": True}
    monkeypatch.setattr(
        operator,
        "_build_outcome_blind_projection_v1",
        lambda **_kwargs: (projection, predecessor, later_source),
    )
    monkeypatch.setattr(
        operator.successor,
        "validate_catalog_wide_projection_v1",
        lambda value, **kwargs: (dict(value), dict(kwargs["identity"])),
    )

    lease_body = {"lease": "one-live-generation"}
    lease_raw = batch.canonical_json_bytes(lease_body)
    lease_identity = {
        "uri": operator.base_runner.shared.adapter.HISTORICAL_OUTCOME_LEASE_URI,
        "generation": "44",
        "sha256": sha256(lease_raw).hexdigest(),
        "bytes": len(lease_raw),
    }
    lease_value = {
        "body": lease_body,
        "object_receipt": {**lease_identity, "create_only": True},
    }
    lease_calls = 0

    def lease_verifier() -> dict[str, object]:
        nonlocal lease_calls
        lease_calls += 1
        events.append("lease:verify")
        return lease_value

    query_calls = 0

    def query(spec: registered.QuerySpec) -> base_supply.FullUnionOutcomeQueryResultV1:
        nonlocal query_calls
        query_calls += 1
        events.append(f"query:{spec.job_id}")
        rows = sorted(
            (
                {
                    "season": row["season"],
                    "week": row["week"],
                    "source_kind": row["source_kind"],
                    "source_key": row["source_key"],
                    "realized_score": 1,
                }
                for row in prepared.delta_keys
            ),
            key=lambda row: (
                row["season"],
                row["week"],
                row["source_kind"],
                row["source_key"],
            ),
        )
        receipt = {
            "job_id": spec.job_id,
            "location": spec.location,
            "sql_sha256": spec.sql_sha256,
            "parameters_sha256": spec.parameters_sha256,
            "cache_hit": False,
            "error_result": None,
        }
        return base_supply.FullUnionOutcomeQueryResultV1(
            result=shared.QueryResult(rows=rows, job_receipt=receipt),
            disposition="recovered",
        )

    def runtime_factory() -> operator.QueryRuntimeV1:
        events.append("runtime:create")
        return operator.QueryRuntimeV1(
            metadata_reader=lambda table: {
                "table_id": table,
                "etag": "stable",
                "modified": "2026-08-26T00:00:00+00:00",
                "num_rows": 100,
                "schema_sha256": "d" * 64,
            },
            get_or_create_query=query,
        )

    def source_builder(**kwargs: object) -> dict[str, object]:
        assert kwargs["delta_registered_rows"]
        assert kwargs["query_evidence_identity"]["uri"].endswith(
            "/query-evidence.json"
        )
        return {"stage": "source", "realized_source_sha256": "e" * 64}

    def snapshot_builder(**kwargs: object) -> dict[str, object]:
        assert kwargs["realized_source_identity"]["uri"].endswith(
            "/realized-source.json"
        )
        return {"stage": "snapshot", "outcome_snapshot_sha256": "f" * 64}

    monkeypatch.setattr(
        operator.successor, "build_catalog_wide_realized_source_v1", source_builder
    )
    monkeypatch.setattr(
        operator.successor, "build_catalog_wide_snapshot_v1", snapshot_builder
    )
    monkeypatch.setattr(
        operator.successor,
        "validate_catalog_wide_realized_source_v1",
        lambda value, **kwargs: (dict(value), dict(kwargs["identity"])),
    )
    monkeypatch.setattr(
        operator.successor,
        "validate_catalog_wide_snapshot_v1",
        lambda value, **_kwargs: ({}, {(0, "fixture"): 1}),
    )

    result = operator.supply_v1(
        config=config(),
        store=store,
        lease_verifier=lease_verifier,
        query_runtime_factory=runtime_factory,
    )

    publications = [event for event in events if event.startswith("publish:")]
    assert publications == [
        "publish:outcome-key-projection.json",
        "publish:registered-request.json",
        "publish:query-evidence.json",
        "publish:realized-source.json",
        "publish:outcome-snapshot.json",
        "publish:completion.json",
    ]
    assert events.index("publish:registered-request.json") < events.index(
        "lease:verify"
    )
    assert events.index("lease:verify") < events.index("runtime:create")
    assert query_calls == 1
    assert result.recovered_complete is False
    assert result.completion["historical_outcome_lease_release_required"] is True
    assert result.completion["lease_release_owner"] == "external-launcher-watcher"

    # Restart after evidence: source/snapshot/completion are reconstructed,
    # while the already recovered fixed-ID job is never invoked again.
    store.objects.pop(operator._source_uri(config()))
    store.objects.pop(operator._snapshot_uri(config()))
    store.objects.pop(operator._completion_uri(config()))
    after_evidence = operator.supply_v1(
        config=config(),
        store=store,
        lease_verifier=lease_verifier,
        query_runtime_factory=runtime_factory,
    )
    assert after_evidence.recovered_complete is False
    assert query_calls == 1

    # Restart after source, then after snapshot, exercises each persisted
    # boundary without resubmitting or reconstructing another query job.
    store.objects.pop(operator._snapshot_uri(config()))
    store.objects.pop(operator._completion_uri(config()))
    after_source = operator.supply_v1(
        config=config(),
        store=store,
        lease_verifier=lease_verifier,
        query_runtime_factory=runtime_factory,
    )
    assert after_source.recovered_complete is False
    assert query_calls == 1
    store.objects.pop(operator._completion_uri(config()))
    after_snapshot = operator.supply_v1(
        config=config(),
        store=store,
        lease_verifier=lease_verifier,
        query_runtime_factory=runtime_factory,
    )
    assert after_snapshot.recovered_complete is False
    assert query_calls == 1

    prior_event_count = len(events)
    recovered = operator.supply_v1(
        config=config(),
        store=store,
        lease_verifier=lease_verifier,
        query_runtime_factory=runtime_factory,
    )
    assert recovered.recovered_complete is True
    assert query_calls == 1
    assert lease_calls == 8
    assert not any(
        event.startswith("publish:") for event in events[prior_event_count:]
    )

    # A rehashed, generically openable snapshot is not enough: it must equal
    # the body rebuilt from the exact evidence/source chain.
    valid_snapshot = store.objects[operator._snapshot_uri(config())]
    valid_completion = store.objects[operator._completion_uri(config())]
    store.objects.pop(operator._completion_uri(config()))
    store.replace(
        operator._snapshot_uri(config()),
        {"stage": "snapshot", "outcome_snapshot_sha256": "0" * 64},
        generation="900",
    )
    with pytest.raises(
        operator.CatalogWideOutcomeOperatorV1Error, match="recovered-chain replay"
    ):
        operator.supply_v1(
            config=config(),
            store=store,
            lease_verifier=lease_verifier,
            query_runtime_factory=runtime_factory,
        )
    assert query_calls == 1
    store.objects[operator._snapshot_uri(config())] = valid_snapshot

    # A self-hashed completion pointing at a stale snapshot generation also
    # fails before it can claim terminal recovery.
    stale_completion = batch.parse_canonical_json_bytes(
        valid_completion.reopened_raw, label="valid completion"
    )
    assert isinstance(stale_completion, dict)
    stale_snapshot_body = {
        "stage": "snapshot",
        "outcome_snapshot_sha256": "1" * 64,
    }
    stale_snapshot_raw = batch.canonical_json_bytes(stale_snapshot_body)
    stale_completion["outcome_snapshot_identity"] = {
        "uri": operator._snapshot_uri(config()),
        "generation": "901",
        "sha256": sha256(stale_snapshot_raw).hexdigest(),
        "bytes": len(stale_snapshot_raw),
    }
    stale_completion["completion_sha256"] = operator.successor.digest(
        {
            key: value
            for key, value in stale_completion.items()
            if key != "completion_sha256"
        }
    )
    store.replace(
        operator._completion_uri(config()), stale_completion, generation="902"
    )
    with pytest.raises(
        operator.CatalogWideOutcomeOperatorV1Error,
        match="not the exact current object",
    ):
        operator.supply_v1(
            config=config(),
            store=store,
            lease_verifier=lease_verifier,
            query_runtime_factory=runtime_factory,
        )
    assert query_calls == 1
