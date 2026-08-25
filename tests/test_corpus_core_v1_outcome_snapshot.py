"""Focused offline tests for the Core v1 reusable outcome snapshot."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.research import corpus_core_v1_outcome_snapshot as snapshot
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_realized_outcome_transport as registered
from nfl_dfs.research import lr8_label_score_map as shared


def _identity(value: object, name: str) -> dict[str, object]:
    return batch.object_identity_for_json(
        value, uri=f"gs://fixture/{name}.json", generation="1"
    )


def _fixture() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    player_ids = ["DST-00", *[f"p{ordinal:02d}" for ordinal in range(8)]]
    roster = sorted(player_ids)
    slates: list[dict[str, object]] = []
    source_slates: list[dict[str, object]] = []
    for source_ordinal in range(54):
        season = 2023 + source_ordinal // 18
        week = source_ordinal % 18 + 1
        slate_id = f"{season}-w{week:02d}"
        slates.append({
            "source_ordinal": source_ordinal,
            "slate": {"season": season, "week": week, "slate_id": slate_id},
            "union_population": {"rosters": [roster]},
        })
        players = [{
            "id": player_id,
            "pos": "DST" if player_id == "DST-00" else "WR",
            "team": "T00" if player_id == "DST-00" else "T01",
        } for player_id in player_ids]
        players.sort(key=lambda value: value["id"])
        source_slates.append({
            "season": season,
            "week": week,
            "slate_id": slate_id,
            "catalog": players,
        })
    source_freeze: dict[str, object] = {"slates": source_slates}
    source_identity = _identity(source_freeze, "later-source")
    catalog: dict[str, object] = {
        "catalog_sha256": "c" * 64,
        "later_source_freeze_identity": source_identity,
        "later_source_freeze_sha256": "f" * 64,
        "slates": slates,
    }
    return catalog, _identity(catalog, "catalog"), source_freeze, source_identity


def _patch_validators(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    catalog, catalog_identity, source_freeze, source_identity = _fixture()
    monkeypatch.setattr(
        snapshot.core, "validate_core_v1_catalog", lambda value: dict(value)
    )
    monkeypatch.setattr(
        snapshot.later_source,
        "validate_source_freeze",
        lambda value, *, expected_freeze_sha256: dict(value),
    )
    return catalog, catalog_identity, source_freeze, source_identity


def _player_source(
    *,
    catalog: dict[str, object],
    keys: tuple[snapshot.CoreOutcomeKey, ...],
    rows: list[dict[str, object]],
    name: str = "player-score-source",
) -> tuple[dict[str, object], dict[str, object]]:
    outcome_payload = [{
        "source_ordinal": row.source_ordinal,
        "season": row.season,
        "week": row.week,
        "slate_id": row.slate_id,
        "source_kind": row.source_kind,
        "source_key": row.source_key,
        "player_id": row.player_id,
    } for row in keys]
    table_receipts = [{
        "table_id": table,
        "etag": "stable",
        "modified": "2026-08-24T00:00:00+00:00",
        "num_rows": 1,
        "schema_sha256": "e" * 64,
    } for table in (registered.SKILL_TABLE, registered.DST_TABLE)]
    lease_body = {
        "version": shared.adapter.HISTORICAL_OUTCOME_LEASE_VERSION,
        "run_id": "core-v1-fixture",
        "job": "core-v1-fixture-job",
        "code_sha": "1" * 40,
        "image": f"us-docker.pkg.dev/test/core@sha256:{'2' * 64}",
        "acquired_at": "2026-08-25T00:00:00+00:00",
    }
    lease_raw = shared.canonical_json(lease_body)
    historical_lease = {
        "body": lease_body,
        "object_receipt": {
            "uri": shared.adapter.HISTORICAL_OUTCOME_LEASE_URI,
            "generation": "1",
            "sha256": sha256(lease_raw).hexdigest(),
            "bytes": len(lease_raw),
            "create_only": True,
        },
    }
    query_job_id = registered.deterministic_query_job_id(
        registered.SupplierConfig(
            run_id=str(lease_body["run_id"]),
            job=str(lease_body["job"]),
            code_sha=str(lease_body["code_sha"]),
            image=str(lease_body["image"]),
            expected_batch_acceptance_object_sha256=str(
                catalog["catalog_sha256"]
            ),
            enabled=True,
        )
    )
    source_snapshot_at = "2026-08-25T00:00:15+00:00"
    query_contract = snapshot.core_query_contract(
        outcome_keys=keys,
        query_job_id=query_job_id,
        source_snapshot_at=source_snapshot_at,
    )
    query_job_receipt = {
        "job_id": query_job_id,
        "location": query_contract["location"],
        "sql_sha256": query_contract["sql_sha256"],
        "parameters_sha256": query_contract["parameters_sha256"],
        "created": "2026-08-25T00:01:00+00:00",
        "started": "2026-08-25T00:01:30+00:00",
        "ended": "2026-08-25T00:02:00+00:00",
        "total_bytes_processed": 1,
        "cache_hit": False,
        "error_result": None,
    }
    catalog_identity = _identity(catalog, "catalog")
    attempt_body: dict[str, object] = {
        "schema_version": snapshot.READ_ATTEMPT_SCHEMA,
        "run_id": lease_body["run_id"],
        "catalog_identity": catalog_identity,
        "catalog_sha256": catalog["catalog_sha256"],
        "later_source_freeze_identity": catalog[
            "later_source_freeze_identity"
        ],
        "later_source_freeze_sha256": catalog["later_source_freeze_sha256"],
        "outcome_key_count": len(keys),
        "outcome_keys": outcome_payload,
        "outcome_keys_sha256": snapshot.canonical_sha256(outcome_payload),
        "query_contract": query_contract,
        "query_contract_sha256": snapshot.canonical_sha256(query_contract),
        "table_receipts_before_query": table_receipts,
        "table_receipt_set_sha256": snapshot.canonical_sha256(table_receipts),
        "historical_outcome_lease": historical_lease,
        "started_at": "2026-08-25T00:00:00+00:00",
        "uses_realized_outcomes_at_creation": False,
        "attempt_precedes_query": True,
        "historical_retry_licensed": False,
        "historical_retune_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    attempt = {
        **attempt_body,
        "attempt_sha256": snapshot.canonical_sha256(attempt_body),
    }
    attempt_identity = _identity(attempt, "read-attempt")
    body: dict[str, object] = {
        "schema_version": snapshot.PLAYER_SOURCE_SCHEMA,
        "catalog_sha256": catalog["catalog_sha256"],
        "attempt": attempt,
        "attempt_identity": attempt_identity,
        "attempt_created_at": "2026-08-25T00:00:30+00:00",
        "later_source_freeze_identity": catalog[
            "later_source_freeze_identity"
        ],
        "later_source_freeze_sha256": catalog["later_source_freeze_sha256"],
        "outcome_key_count": len(keys),
        "outcome_keys_sha256": snapshot.canonical_sha256(outcome_payload),
        "query_contract": query_contract,
        "query_contract_sha256": snapshot.canonical_sha256(query_contract),
        "query_job_id": query_job_id,
        "query_job_receipt": query_job_receipt,
        "query_job_disposition": "created",
        "source_snapshot_at": source_snapshot_at,
        "table_receipts_before_query": table_receipts,
        "table_receipts_after_query": table_receipts,
        "table_receipt_set_sha256": snapshot.canonical_sha256(table_receipts),
        "historical_outcome_lease_before_query": historical_lease,
        "historical_outcome_lease_after_query": historical_lease,
        "historical_outcome_lease_sha256": snapshot.canonical_sha256(
            historical_lease
        ),
        "row_fields": [
            "source_ordinal",
            "season",
            "week",
            "slate_id",
            "source_kind",
            "source_key",
            "player_id",
            "realized_score_micro",
        ],
        "row_count": len(rows),
        "rows_sha256": snapshot.canonical_sha256(rows),
        "rows": rows,
        "one_exact_query": True,
        "query_cache_used": False,
        "table_metadata_stable_during_query": True,
        "historical_outcome_lease_unchanged_during_query": True,
        "full_field_standings_included": False,
        "payout_ladder_included": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    source = {**body, "source_sha256": snapshot.canonical_sha256(body)}
    return source, _identity(source, name)


def test_projection_reuses_registered_query_law_and_snapshot_is_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog, catalog_identity, source_freeze, source_identity = _patch_validators(
        monkeypatch
    )
    keys = snapshot.project_core_outcome_keys(
        catalog=catalog,
        catalog_identity=catalog_identity,
        source_freeze=source_freeze,
        source_freeze_identity=source_identity,
    )
    assert len(keys) == 54 * 9
    assert sum(value.source_kind == "dst" for value in keys) == 54
    assert all(
        value.source_key == "T00"
        for value in keys
        if value.source_kind == "dst"
    )

    query_rows = [{
        "season": value.season,
        "week": value.week,
        "source_kind": value.source_kind,
        "source_key": value.source_key,
        "realized_score": "1.25",
    } for value in sorted(
        keys,
        key=lambda value: (
            value.season, value.week, value.source_kind, value.source_key
        ),
    )]
    rows = snapshot.normalize_authoritative_query_rows(
        query_rows, outcome_keys=keys
    )
    player_source, player_source_identity = _player_source(
        catalog=catalog, keys=keys, rows=rows
    )
    result = snapshot.build_core_outcome_snapshot(
        catalog=catalog,
        catalog_identity=catalog_identity,
        player_source=player_source,
        player_source_identity=player_source_identity,
        outcome_keys=keys,
    )
    assert result["row_count"] == 54 * 9
    assert result["rows"][0]["realized_score_micro"] == 1_250_000
    assert result["full_field_standings_included"] is False
    assert result["payout_ladder_included"] is False
    result_identity = _identity(result, "outcome-snapshot")
    retained, retained_identity, score_map = snapshot.validate_core_outcome_snapshot(
        result,
        identity=result_identity,
        catalog=catalog,
        catalog_identity=catalog_identity,
        player_source=player_source,
        player_source_identity=player_source_identity,
        outcome_keys=keys,
    )
    assert retained == result
    assert retained_identity == result_identity
    assert len(score_map) == 54 * 9

    forged = deepcopy(result)
    forged["rows"][0]["realized_score_micro"] += 1
    forged["rows_sha256"] = snapshot.canonical_sha256(forged["rows"])
    forged_body = {
        key: value
        for key, value in forged.items()
        if key != "outcome_snapshot_sha256"
    }
    forged["outcome_snapshot_sha256"] = snapshot.canonical_sha256(forged_body)
    with pytest.raises(
        snapshot.CorpusCoreV1OutcomeSnapshotError,
        match="snapshot law differs",
    ):
        snapshot.validate_core_outcome_snapshot(
            forged,
            identity=_identity(forged, "forged-outcome-snapshot"),
            catalog=catalog,
            catalog_identity=catalog_identity,
            player_source=player_source,
            player_source_identity=player_source_identity,
            outcome_keys=keys,
        )


def test_projection_rejects_uncovered_player_and_duplicate_source_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog, catalog_identity, source_freeze, source_identity = _patch_validators(
        monkeypatch
    )
    missing = deepcopy(source_freeze)
    missing["slates"][0]["catalog"] = missing["slates"][0]["catalog"][1:]
    missing_identity = _identity(missing, "later-source-missing")
    poisoned_catalog = deepcopy(catalog)
    poisoned_catalog["later_source_freeze_identity"] = missing_identity
    poisoned_catalog_identity = _identity(poisoned_catalog, "catalog-missing")
    with pytest.raises(
        snapshot.CorpusCoreV1OutcomeSnapshotError,
        match="not covered",
    ):
        snapshot.project_core_outcome_keys(
            catalog=poisoned_catalog,
            catalog_identity=poisoned_catalog_identity,
            source_freeze=missing,
            source_freeze_identity=missing_identity,
        )

    duplicate = deepcopy(source_freeze)
    duplicate["slates"][0]["catalog"][1]["pos"] = "DST"
    duplicate["slates"][0]["catalog"][1]["team"] = "T00"
    duplicate_identity = _identity(duplicate, "later-source-duplicate")
    duplicate_catalog = deepcopy(catalog)
    duplicate_catalog["later_source_freeze_identity"] = duplicate_identity
    duplicate_catalog_identity = _identity(duplicate_catalog, "catalog-duplicate")
    with pytest.raises(
        snapshot.CorpusCoreV1OutcomeSnapshotError,
        match="source-key union differs",
    ):
        snapshot.project_core_outcome_keys(
            catalog=duplicate_catalog,
            catalog_identity=duplicate_catalog_identity,
            source_freeze=duplicate,
            source_freeze_identity=duplicate_identity,
        )


def test_snapshot_rejects_missing_row_and_catalog_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog, catalog_identity, source_freeze, source_identity = _patch_validators(
        monkeypatch
    )
    keys = snapshot.project_core_outcome_keys(
        catalog=catalog,
        catalog_identity=catalog_identity,
        source_freeze=source_freeze,
        source_freeze_identity=source_identity,
    )
    rows = [{
        "source_ordinal": value.source_ordinal,
        "season": value.season,
        "week": value.week,
        "slate_id": value.slate_id,
        "source_kind": value.source_kind,
        "source_key": value.source_key,
        "player_id": value.player_id,
        "realized_score_micro": 0,
    } for value in keys]
    missing_source, missing_source_identity = _player_source(
        catalog=catalog, keys=keys, rows=rows[:-1], name="source-missing"
    )
    with pytest.raises(
        snapshot.CorpusCoreV1OutcomeSnapshotError,
        match="row count differs",
    ):
        snapshot.build_core_outcome_snapshot(
            catalog=catalog,
            catalog_identity=catalog_identity,
            player_source=missing_source,
            player_source_identity=missing_source_identity,
            outcome_keys=keys,
        )

    source, source_identity = _player_source(
        catalog=catalog, keys=keys, rows=rows
    )
    drifted = deepcopy(catalog)
    drifted["catalog_sha256"] = "d" * 64
    with pytest.raises(
        snapshot.CorpusCoreV1OutcomeSnapshotError,
        match="identity",
    ):
        snapshot.build_core_outcome_snapshot(
            catalog=drifted,
            catalog_identity=catalog_identity,
            player_source=source,
            player_source_identity=source_identity,
            outcome_keys=keys,
        )


def test_source_identity_and_source_rows_are_one_exact_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog, catalog_identity, source_freeze, source_identity = _patch_validators(
        monkeypatch
    )
    keys = snapshot.project_core_outcome_keys(
        catalog=catalog,
        catalog_identity=catalog_identity,
        source_freeze=source_freeze,
        source_freeze_identity=source_identity,
    )
    rows = [{
        "source_ordinal": value.source_ordinal,
        "season": value.season,
        "week": value.week,
        "slate_id": value.slate_id,
        "source_kind": value.source_kind,
        "source_key": value.source_key,
        "player_id": value.player_id,
        "realized_score_micro": 0,
    } for value in sorted(
        keys,
        key=lambda value: (
            value.season, value.week, value.source_kind, value.source_key
        ),
    )]
    source, source_object_identity = _player_source(
        catalog=catalog, keys=keys, rows=rows
    )
    mismatched_identity = _identity(
        {**source, "rows": []}, "different-source-object"
    )
    with pytest.raises(
        snapshot.CorpusCoreV1OutcomeSnapshotError,
        match="content SHA-256 differs",
    ):
        snapshot.build_core_outcome_snapshot(
            catalog=catalog,
            catalog_identity=catalog_identity,
            player_source=source,
            player_source_identity=mismatched_identity,
            outcome_keys=keys,
        )

    poisoned = deepcopy(source)
    poisoned["rows"][0]["source_key"] = "NON-UNION"
    poisoned_body = {
        key: value for key, value in poisoned.items() if key != "source_sha256"
    }
    poisoned["rows_sha256"] = snapshot.canonical_sha256(poisoned["rows"])
    poisoned_body = {
        key: value for key, value in poisoned.items() if key != "source_sha256"
    }
    poisoned["source_sha256"] = snapshot.canonical_sha256(poisoned_body)
    poisoned_identity = _identity(poisoned, "poisoned-source")
    with pytest.raises(
        snapshot.CorpusCoreV1OutcomeSnapshotError,
        match="non-union query key",
    ):
        snapshot.build_core_outcome_snapshot(
            catalog=catalog,
            catalog_identity=catalog_identity,
            player_source=poisoned,
            player_source_identity=poisoned_identity,
            outcome_keys=keys,
        )

    cached = deepcopy(source)
    cached["query_job_receipt"]["cache_hit"] = True
    cached_body = {
        key: value for key, value in cached.items() if key != "source_sha256"
    }
    cached["source_sha256"] = snapshot.canonical_sha256(cached_body)
    with pytest.raises(
        snapshot.CorpusCoreV1OutcomeSnapshotError,
        match="used cache",
    ):
        snapshot.build_core_outcome_snapshot(
            catalog=catalog,
            catalog_identity=catalog_identity,
            player_source=cached,
            player_source_identity=_identity(cached, "cached-source"),
            outcome_keys=keys,
        )

    late_attempt = deepcopy(source)
    late_attempt["attempt_created_at"] = "2026-08-25T00:01:01+00:00"
    late_attempt_body = {
        key: value
        for key, value in late_attempt.items()
        if key != "source_sha256"
    }
    late_attempt["source_sha256"] = snapshot.canonical_sha256(
        late_attempt_body
    )
    with pytest.raises(
        snapshot.CorpusCoreV1OutcomeSnapshotError,
        match="chronology",
    ):
        snapshot.build_core_outcome_snapshot(
            catalog=catalog,
            catalog_identity=catalog_identity,
            player_source=late_attempt,
            player_source_identity=_identity(late_attempt, "late-attempt-source"),
            outcome_keys=keys,
        )

    assert source_object_identity["sha256"] == snapshot.canonical_sha256(source)


def test_registered_query_law_rejects_reorder_extra_and_inexact_decimal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog, catalog_identity, source_freeze, source_identity = _patch_validators(
        monkeypatch
    )
    keys = snapshot.project_core_outcome_keys(
        catalog=catalog,
        catalog_identity=catalog_identity,
        source_freeze=source_freeze,
        source_freeze_identity=source_identity,
    )
    query_rows = [{
        "season": value.season,
        "week": value.week,
        "source_kind": value.source_kind,
        "source_key": value.source_key,
        "realized_score": "1.25",
    } for value in sorted(
        keys,
        key=lambda value: (
            value.season, value.week, value.source_kind, value.source_key
        ),
    )]
    with pytest.raises(snapshot.CorpusCoreV1OutcomeSnapshotError, match="ordered"):
        snapshot.normalize_authoritative_query_rows(
            list(reversed(query_rows)), outcome_keys=keys
        )
    extra = deepcopy(query_rows)
    extra[0]["unknown"] = True
    with pytest.raises(snapshot.CorpusCoreV1OutcomeSnapshotError, match="fields"):
        snapshot.normalize_authoritative_query_rows(extra, outcome_keys=keys)
    inexact = deepcopy(query_rows)
    inexact[0]["realized_score"] = "0.0000001"
    with pytest.raises(snapshot.CorpusCoreV1OutcomeSnapshotError):
        snapshot.normalize_authoritative_query_rows(inexact, outcome_keys=keys)
