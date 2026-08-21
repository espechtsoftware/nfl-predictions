from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

import pytest

from nfl_dfs.research import lr8_label_fit_adapter as adapter
from nfl_dfs.research import lr8_label_score_map as supplier
from nfl_dfs.research import lr8_training_source as source
from nfl_dfs.research import residual_world_columns as rw


def _content_receipt(uri: str, raw: bytes) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _create_receipt(uri: str, value: dict[str, object]) -> dict[str, object]:
    raw = supplier.canonical_json(value)
    return {**_content_receipt(uri, raw), "create_only": True}


def _catalog(season: int, week: int) -> list[dict[str, object]]:
    prefix = f"{season}-{week:02d}"
    rows = (
        (f"{prefix}-dst", "DST", "NE", "NYJ", "g0", 3_000),
        (f"{prefix}-q", "QB", "A", "B", "g1", 5_000),
        (f"{prefix}-r1", "RB", "C", "D", "g2", 4_000),
        (f"{prefix}-r2", "RB", "D", "C", "g2", 4_000),
        (f"{prefix}-t", "TE", "B", "A", "g1", 4_000),
        (f"{prefix}-w1", "WR", "A", "B", "g1", 4_000),
        (f"{prefix}-w2", "WR", "B", "A", "g1", 4_000),
        (f"{prefix}-w3", "WR", "C", "D", "g2", 4_000),
        (f"{prefix}-w4", "WR", "E", "F", "g3", 3_000),
    )
    return sorted(({
        "id": player_id,
        "pos": position,
        "team": team,
        "opp": opponent,
        "game_id": game_id,
        "salary": salary,
    } for player_id, position, team, opponent, game_id, salary in rows),
        key=lambda row: row["id"],
    )


def _training_source() -> tuple[dict[str, object], dict[str, object]]:
    body: dict[str, object] = {
        "slates": [{
            "season": season,
            "week": week,
            "catalog": _catalog(season, week),
        } for season, week in source.EXPECTED_SLATE_KEYS],
    }
    frozen = {**body, "manifest_sha256": supplier.canonical_sha256(body)}
    raw = supplier.canonical_json(frozen)
    receipt = _content_receipt(
        "gs://test/lr8/training-source-freeze.json", raw
    )
    return frozen, receipt


def _config(*, enabled: bool = True) -> supplier.SupplierConfig:
    frozen, _ = _training_source()
    return supplier.SupplierConfig(
        run_id="20260821-lr8-label-score-map-v1",
        job="atlas-md-prefix-r4-smoke",
        code_sha="1" * 40,
        image="us-central1-docker.pkg.dev/test/repo/image@sha256:" + "2" * 64,
        expected_source_manifest_sha256=str(frozen["manifest_sha256"]),
        enabled=enabled,
    )


def _lease(config: supplier.SupplierConfig) -> dict[str, object]:
    body = {
        "version": adapter.HISTORICAL_OUTCOME_LEASE_VERSION,
        "run_id": config.run_id,
        "job": config.job,
        "code_sha": config.code_sha,
        "image": config.image,
        "acquired_at": "2026-08-21T00:00:00+00:00",
    }
    return {
        "body": body,
        "object_receipt": _create_receipt(
            adapter.HISTORICAL_OUTCOME_LEASE_URI, body
        ),
    }


def _query_rows(frozen: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    for slate in frozen["slates"]:
        for player in slate["catalog"]:
            is_dst = player["pos"] == "DST"
            rows.append({
                "season": slate["season"],
                "week": slate["week"],
                "source_kind": "dst" if is_dst else "skill",
                "source_key": (
                    str(player["team"]).upper() if is_dst else player["id"]
                ),
                "realized_score": Decimal("-1") if is_dst else Decimal("10.25"),
            })
    return sorted(rows, key=lambda row: (
        row["season"], row["week"], row["source_kind"], row["source_key"]
    ))


class Harness:
    def __init__(self, config: supplier.SupplierConfig) -> None:
        self.config = config
        self.lease = _lease(config)
        self.events: list[str] = []
        self.published: list[tuple[str, dict[str, object]]] = []
        self.query_mutator = lambda rows: rows
        self.job_mutator = lambda value: value
        self.metadata_mutator = lambda table, call, value: value
        self.lease_mutator = lambda call, value: value
        self.metadata_calls = 0
        self.lease_calls = 0
        self.query_calls = 0
        self.stamp_mutator = lambda name, stamp: stamp
        self.clock_values = iter((
            datetime(2026, 8, 21, 0, 0, 1, tzinfo=timezone.utc),
            datetime(2026, 8, 21, 0, 0, 3, tzinfo=timezone.utc),
        ))

    def clock(self) -> datetime:
        self.events.append("clock")
        return next(self.clock_values)

    def verify_lease(self) -> dict[str, object]:
        self.lease_calls += 1
        self.events.append(f"lease-{self.lease_calls}")
        return self.lease_mutator(self.lease_calls, deepcopy(self.lease))

    def metadata(self, table: str) -> dict[str, object]:
        self.metadata_calls += 1
        self.events.append(f"metadata-{self.metadata_calls}")
        value = {
            "table_id": table,
            "etag": f"etag/{table}",
            "modified": "2026-08-20T00:00:00+00:00",
            "num_rows": 10_000,
            "schema_sha256": sha256(table.encode()).hexdigest(),
        }
        return self.metadata_mutator(table, self.metadata_calls, value)

    def query(self, spec: supplier.QuerySpec) -> supplier.QueryResult:
        self.query_calls += 1
        self.events.append("query")
        assert self.published[0][0].endswith("label-read-attempt.json")
        frozen, _ = _training_source()
        rows = self.query_mutator(_query_rows(frozen))
        receipt = {
            "job_id": spec.job_id,
            "location": spec.location,
            "sql_sha256": spec.sql_sha256,
            "parameters_sha256": spec.parameters_sha256,
            "created": "2026-08-21T00:00:04+00:00",
            "started": "2026-08-21T00:00:05+00:00",
            "ended": "2026-08-21T00:00:06+00:00",
            "total_bytes_processed": 123,
            "cache_hit": False,
            "error_result": None,
        }
        return supplier.QueryResult(
            rows=rows,
            job_receipt=self.job_mutator(receipt),
        )

    def publish(self, uri: str, raw: bytes) -> supplier.PublishedObject:
        self.events.append("publish")
        body = json.loads(raw)
        self.published.append((uri, body))
        stamp = self.stamp_mutator(Path(uri).name, {
            "label-read-attempt.json": "2026-08-21T00:00:02+00:00",
            "authoritative-score-source.json": "2026-08-21T00:00:07+00:00",
            "authoritative-score-map.json": "2026-08-21T00:00:08+00:00",
        }[Path(uri).name])
        receipt = {
            **_content_receipt(uri, raw),
            "create_only": True,
        }
        return supplier.PublishedObject(
            receipt=receipt,
            reopened_raw=raw,
            created_at=stamp,
            created=True,
        )


def _run(
    monkeypatch: pytest.MonkeyPatch,
    harness: Harness | None = None,
) -> tuple[supplier.ScoreMapSupply, Harness, dict[str, object]]:
    config = harness.config if harness is not None else _config()
    active = harness or Harness(config)
    frozen, receipt = _training_source()
    monkeypatch.setattr(adapter, "frozen_fit_candidates", lambda *args, **kwargs: ())
    result = supplier.supply_authoritative_score_map(
        config=config,
        training_source_freeze=frozen,
        training_source_receipt=receipt,
        verify_lease=active.verify_lease,
        read_table_metadata=active.metadata,
        execute_query=active.query,
        publish=active.publish,
        clock=active.clock,
    )
    return result, active, frozen


def test_default_off_precedes_source_clock_and_every_callback(monkeypatch):
    config = replace(_config(), enabled=False, expected_source_manifest_sha256="bad")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("default-off supplier performed work")

    monkeypatch.setattr(adapter, "frozen_fit_candidates", forbidden)
    with pytest.raises(supplier.LR8ScoreMapError, match="default-off"):
        supplier.supply_authoritative_score_map(
            config=config,
            training_source_freeze={},
            training_source_receipt={},
            verify_lease=forbidden,
            read_table_metadata=forbidden,
            execute_query=forbidden,
            publish=forbidden,
            clock=forbidden,
        )


def test_query_is_exact_frozen_35_slate_player_dst_boundary(monkeypatch):
    frozen, receipt = _training_source()
    monkeypatch.setattr(adapter, "frozen_fit_candidates", lambda *args, **kwargs: ())
    catalog, _, _ = supplier._validate_training_source(
        frozen,
        expected_manifest_sha256=str(frozen["manifest_sha256"]),
        receipt=receipt,
    )
    spec = supplier.build_query_spec(
        config=_config(),
        catalog=catalog,
        source_snapshot_at="2026-08-21T00:00:03+00:00",
    )
    params = {item.name: item for item in spec.parameters}
    assert params["target_seasons"].value == [2019, 2021]
    assert len(params["skill_keys"].value) == 35 * 8
    assert len(params["dst_keys"].value) == 35
    assert all(
        key.startswith(("2019|", "2021|"))
        for key in (*params["skill_keys"].value, *params["dst_keys"].value)
    )
    sql = f" {spec.sql.lower()} "
    assert supplier.SKILL_TABLE.lower() in sql
    assert supplier.DST_TABLE.lower() in sql
    assert "for system_time as of @source_snapshot_at" in sql
    assert "union all" in sql
    for forbidden in (
        " contest", " ownership", " payout", " standing", " winner",
        " candidate", " lineup", " insert ", " update ", " merge ",
        " delete ",
    ):
        assert forbidden not in sql


def test_success_is_attempt_first_single_query_and_adapter_compatible(monkeypatch):
    result, harness, frozen = _run(monkeypatch)
    assert harness.query_calls == 1
    assert harness.lease_calls == 2
    assert harness.metadata_calls == 4
    assert [Path(uri).name for uri, _ in harness.published] == [
        "label-read-attempt.json",
        "authoritative-score-source.json",
        "authoritative-score-map.json",
    ]
    assert harness.events.index("publish") < harness.events.index("query")
    assert result.attempt["uses_realized_outcomes_at_creation"] is False
    assert result.attempt["retry_licensed"] is False
    assert result.score_map["target_seasons"] == [2019, 2021]
    assert result.score_map["slate_keys"] == [
        list(key) for key in source.EXPECTED_SLATE_KEYS
    ]
    assert len(result.score_map["rows"]) == 35 * 9
    assert result.score_map["score_rows_sha256"] == adapter.canonical_sha256(
        result.score_map["rows"]
    )
    assert set(result.score_map) == {
        "schema", "protocol_id", "supplier_boundary",
        "training_source_manifest_sha256", "training_source_object",
        "target_seasons", "slate_keys", "row_fields", "score_unit",
        "catalog_universe_sha256", "authoritative_source_id",
        "query_identity", "query_sha256", "score_source_receipts",
        "score_source_extract", "score_source_extract_receipt",
        "label_read_attempt", "label_read_attempt_receipt", "rows",
        "score_rows_sha256", "b1_inputs_used", "a2a_inputs_used",
        "winner_inputs_used", "later_period_inputs_used",
        "production_inputs_used",
    }
    assert all(
        result.score_map[field] is False for field in (
            "b1_inputs_used", "a2a_inputs_used", "winner_inputs_used",
            "later_period_inputs_used", "production_inputs_used",
        )
    )
    assert all(
        set(row) == set(adapter.SCORE_ROW_FIELDS)
        for row in result.score_map["rows"]
    )
    assert {row["realized_score_micro"] for row in result.score_map["rows"]} == {
        -1_000_000, 10_250_000,
    }
    assert result.score_map["score_source_extract"] == result.source_extract
    assert result.score_map["score_source_extract_receipt"] == (
        result.source_extract_receipt
    )

    catalogs = {}
    universe = []
    for slate in frozen["slates"]:
        key = (slate["season"], slate["week"])
        catalogs[key] = tuple(
            rw.PlayerSpec.from_mapping(row) for row in slate["catalog"]
        )
        universe.extend({
            "season": slate["season"],
            "week": slate["week"],
            "player_id": row["id"],
            "position": row["pos"],
        } for row in slate["catalog"])
    validated_source = adapter._ValidatedSource(
        manifest_sha256=str(frozen["manifest_sha256"]),
        object_receipt=dict(result.score_map["training_source_object"]),
        candidates=(),
        catalogs=catalogs,
        catalog_universe_sha256=adapter.canonical_sha256(universe),
        candidate_surface_sha256="0" * 64,
    )
    scores, provenance = adapter._score_map(
        result.score_map,
        score_map_receipt=result.score_map_receipt,
        frozen_source=validated_source,
    )
    assert len(scores) == 35 * 9
    assert provenance["score_map_object"] == result.score_map_receipt


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda rows: rows.pop(), "coverage differs"),
        (lambda rows: rows.append(dict(rows[0])), "repeats a source key"),
        (
            lambda rows: rows.append({
                **rows[0], "season": 2023, "source_key": "later-player",
            }),
            "non-2019/2021",
        ),
        (
            lambda rows: rows[0].__setitem__("realized_score", float("nan")),
            "exact decimal",
        ),
        (
            lambda rows: rows[0].__setitem__("winner_score", Decimal("1")),
            "row fields differ",
        ),
    ],
)
def test_query_rows_fail_closed_before_source_or_map_publication(
    monkeypatch, mutator, message,
):
    harness = Harness(_config())
    harness.query_mutator = lambda rows: (mutator(rows), rows)[1]
    with pytest.raises(supplier.LR8ScoreMapError, match=message):
        _run(monkeypatch, harness)
    assert harness.query_calls == 1
    assert [Path(uri).name for uri, _ in harness.published] == [
        "label-read-attempt.json"
    ]


def test_attempt_collision_or_lease_drift_prevents_or_stops_query(monkeypatch):
    frozen, receipt = _training_source()
    config = _config()
    monkeypatch.setattr(adapter, "frozen_fit_candidates", lambda *args, **kwargs: ())
    harness = Harness(config)

    def collision(uri: str, raw: bytes) -> supplier.PublishedObject:
        return supplier.PublishedObject(
            receipt={**_content_receipt(uri, raw), "create_only": True},
            reopened_raw=raw,
            created_at="2026-08-21T00:00:02+00:00",
            created=False,
        )

    with pytest.raises(supplier.LR8ScoreMapError, match="created exactly once"):
        supplier.supply_authoritative_score_map(
            config=config,
            training_source_freeze=frozen,
            training_source_receipt=receipt,
            verify_lease=harness.verify_lease,
            read_table_metadata=harness.metadata,
            execute_query=harness.query,
            publish=collision,
            clock=harness.clock,
        )
    assert harness.query_calls == 0

    drifted = Harness(config)
    drifted.lease_mutator = lambda call, value: (
        value if call == 1 else {
            **value,
            "object_receipt": {
                **value["object_receipt"], "generation": "2",
            },
        }
    )
    with pytest.raises(supplier.LR8ScoreMapError, match="lease changed|lease receipt"):
        _run(monkeypatch, drifted)
    assert drifted.query_calls == 1
    assert [Path(uri).name for uri, _ in drifted.published] == [
        "label-read-attempt.json"
    ]


def test_uri_alias_fails_before_lease_or_query_and_map_follows_extract(monkeypatch):
    frozen, receipt = _training_source()
    config = _config()
    monkeypatch.setattr(adapter, "frozen_fit_candidates", lambda *args, **kwargs: ())
    aliased = {
        **receipt,
        "uri": f"{config.output_root}/authoritative-score-source.json",
    }
    harness = Harness(config)
    with pytest.raises(supplier.LR8ScoreMapError, match="alias before outcome"):
        supplier.supply_authoritative_score_map(
            config=config,
            training_source_freeze=frozen,
            training_source_receipt=aliased,
            verify_lease=harness.verify_lease,
            read_table_metadata=harness.metadata,
            execute_query=harness.query,
            publish=harness.publish,
            clock=harness.clock,
        )
    assert harness.lease_calls == harness.query_calls == 0
    assert harness.published == []

    reversed_time = Harness(config)
    reversed_time.stamp_mutator = lambda name, stamp: (
        "2026-08-21T00:00:06.500000+00:00"
        if name == "authoritative-score-map.json" else stamp
    )
    with pytest.raises(supplier.LR8ScoreMapError, match="create-once reopen"):
        _run(monkeypatch, reversed_time)
    assert [Path(uri).name for uri, _ in reversed_time.published] == [
        "label-read-attempt.json",
        "authoritative-score-source.json",
        "authoritative-score-map.json",
    ]


@pytest.mark.parametrize(
    ("value", "expected", "message"),
    [
        (Decimal("10.250000000"), 10_250_000, None),
        (Decimal("10.250000001"), None, "exact micro-DK"),
        (None, None, "exact decimal"),
        (Decimal("Infinity"), None, "non-finite"),
        (Decimal(supplier._MICRO_LIMIT + 1) / Decimal(1_000_000), None,
         "roster-sum range"),
    ],
)
def test_micro_score_exact_decimal_boundary(value, expected, message):
    if message is None:
        assert supplier._micro_score(value) == expected
    else:
        with pytest.raises(supplier.LR8ScoreMapError, match=message):
            supplier._micro_score(value)


def test_source_and_query_provenance_drift_fail_closed(monkeypatch):
    frozen, receipt = _training_source()
    config = _config()
    monkeypatch.setattr(adapter, "frozen_fit_candidates", lambda *args, **kwargs: ())
    stale = dict(receipt)
    stale["sha256"] = "0" * 64
    harness = Harness(config)
    with pytest.raises(supplier.LR8ScoreMapError, match="canonical bytes"):
        supplier.supply_authoritative_score_map(
            config=config,
            training_source_freeze=frozen,
            training_source_receipt=stale,
            verify_lease=harness.verify_lease,
            read_table_metadata=harness.metadata,
            execute_query=harness.query,
            publish=harness.publish,
            clock=harness.clock,
        )
    assert harness.lease_calls == 0

    bad_job = Harness(config)
    bad_job.job_mutator = lambda value: {**value, "parameters_sha256": "0" * 64}
    with pytest.raises(supplier.LR8ScoreMapError, match="job identity"):
        _run(monkeypatch, bad_job)
    assert [Path(uri).name for uri, _ in bad_job.published] == [
        "label-read-attempt.json"
    ]

    changing_table = Harness(config)
    changing_table.metadata_mutator = lambda table, call, value: (
        {**value, "etag": "changed"} if call > 2 else value
    )
    with pytest.raises(supplier.LR8ScoreMapError, match="changed during query"):
        _run(monkeypatch, changing_table)
    assert [Path(uri).name for uri, _ in changing_table.published] == [
        "label-read-attempt.json"
    ]


def test_module_has_no_remote_client_or_later_decision_path():
    text = Path(supplier.__file__).read_text(encoding="utf-8")
    assert "google.cloud" not in text
    assert "bigquery.Client" not in text
    assert "storage.Client" not in text
    assert "fit_soft_anatomy_law" not in text
    assert "ANATOMY_LABEL_MICRO" not in text
    assert "EVALUATION_SEASONS" not in text
