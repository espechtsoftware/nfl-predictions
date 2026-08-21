from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Mapping, Sequence

import pytest

import scripts.prepare_corpus_retrieval_v1_inputs as preparer
from nfl_dfs.research import corpus_retrieval_engine as engine


class MemoryCreateOnceStorage:
    def __init__(self, *, race_uri: str | None = None):
        self.objects: dict[str, tuple[dict[str, object], bytes]] = {}
        self.race_uri = race_uri
        self.pristine_calls: list[list[str]] = []

    def assert_pristine(self, prefixes: Sequence[str]) -> None:
        self.pristine_calls.append(list(prefixes))
        if any(uri.startswith(prefix) for uri in self.objects for prefix in prefixes):
            raise RuntimeError("namespace collision")

    def publish(self, uri: str, raw: bytes, media_type: str) -> dict[str, object]:
        del media_type
        if uri == self.race_uri or uri in self.objects:
            raise RuntimeError("create-once collision")
        identity = {
            "uri": uri,
            "generation": str(1000 + len(self.objects)),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[uri] = (identity, raw)
        return dict(identity)

    def read(self, value: Mapping[str, object]) -> bytes:
        retained = self.objects.get(str(value["uri"]))
        if retained is None or retained[0] != dict(value):
            raise RuntimeError("exact identity is absent")
        return retained[1]


def _write_capture(root: Path) -> None:
    players = [{
        "id": f"p{index:03d}",
        "name": f"Player {index:03d}",
        "pos": ("QB", "RB", "WR", "TE", "DST")[index % 5],
        "team": f"T{index % 32:02d}",
        "opp": f"T{(index + 1) % 32:02d}",
        "game_id": f"game-{index % 16:02d}",
        "salary": 3000 + index,
        "proj": float(index % 30) + 0.25,
    } for index in range(preparer.EXPECTED_PLAYER_COUNT)]
    candidate_rows = []
    for panel_id, count in zip(
        preparer.PANEL_IDS, preparer.EXPECTED_CANDIDATE_COUNTS, strict=True
    ):
        for cand_ix in range(count):
            candidate_rows.append({
                "panel_id": panel_id,
                "season": 2023,
                "week": 1,
                "cand_ix": cand_ix,
                "tag": "boom",
                "all_tags": ["boom"],
                "players": [f"p{index:03d}" for index in range(9)],
            })

    def query_receipt(
        *, job_id: str, sql_sha256: str, rows: list[dict[str, object]],
    ) -> dict[str, object]:
        return {
            "job_id": job_id,
            "project": preparer.PROJECT,
            "location": preparer.LOCATION,
            "sql_sha256": sql_sha256,
            "snapshot_at_utc": preparer.SNAPSHOT_AT,
            "created": "2026-08-21T17:43:00+00:00",
            "started": "2026-08-21T17:43:01+00:00",
            "ended": "2026-08-21T17:43:02+00:00",
            "total_bytes_processed": 1,
            "cache_hit": False,
            "error_result": None,
            "row_count": len(rows),
            "rows_sha256": engine.canonical_sha256(rows),
            "normalized_rows_sha256": engine.canonical_sha256(rows),
        }

    candidate_receipt = query_receipt(
        job_id=preparer.CANDIDATE_JOB_ID,
        sql_sha256=preparer.CANDIDATE_SQL_SHA256,
        rows=candidate_rows,
    )
    player_receipt = query_receipt(
        job_id=preparer.PLAYER_JOB_ID,
        sql_sha256=preparer.PLAYER_SQL_SHA256,
        rows=players,
    )
    query_authority = engine.build_input_query_authority(
        task_id=preparer.TASK_ID,
        snapshot_at_utc=preparer.SNAPSHOT_AT,
        candidate_query=candidate_receipt,
        player_query=player_receipt,
    )
    validation = preparer._self_hash({  # noqa: SLF001
        "schema_version": "corpus-retrieval-input-capture-validation/v1",
        "task_id": preparer.TASK_ID,
        "snapshot_at_utc": preparer.SNAPSHOT_AT,
        "candidate_rows": len(candidate_rows),
        "candidate_rows_by_panel": dict(zip(
            preparer.PANEL_IDS, preparer.EXPECTED_CANDIDATE_COUNTS, strict=True
        )),
        "catalog_players": len(players),
        "candidate_used_players": 9,
        "artifact_blocks": 5,
        "worlds_per_block": engine.WORLDS_PER_BLOCK,
        "actual_outcome_columns_selected": False,
        "uses_realized_outcomes": False,
        "raw_candidate_query_rows_sha256": candidate_receipt["rows_sha256"],
        "raw_player_query_rows_sha256": player_receipt["rows_sha256"],
        "normalized_candidate_rows_sha256": engine.canonical_sha256(
            candidate_rows
        ),
        "normalized_player_rows_sha256": engine.canonical_sha256(players),
        "artifact_origins": [row["origin"] for row in preparer.WORLD_ORIGINS],
    }, "validation_sha256")
    bodies = {
        "candidate-query-rows.json": candidate_rows,
        "player-query-rows.json": players,
        "query-authority.json": query_authority,
        "validation.json": validation,
    }
    root.mkdir()
    raw_bodies = {
        name: engine.canonical_json_bytes(body) for name, body in bodies.items()
    }
    for name, raw in raw_bodies.items():
        (root / name).write_bytes(raw)
    capture = preparer._self_hash({  # noqa: SLF001
        "schema_version": "corpus-retrieval-input-capture/v1",
        "task_id": preparer.TASK_ID,
        "snapshot_at_utc": preparer.SNAPSHOT_AT,
        "files": {
            name: {"sha256": sha256(raw).hexdigest(), "bytes": len(raw)}
            for name, raw in sorted(raw_bodies.items())
        },
        "validation_sha256": validation["validation_sha256"],
        "uses_realized_outcomes": False,
        "published": False,
    }, "capture_sha256")
    (root / "capture.json").write_bytes(engine.canonical_json_bytes(capture))


@pytest.fixture()
def capture_bundle(tmp_path: Path) -> dict[str, object]:
    root = tmp_path / "capture"
    _write_capture(root)
    return preparer._load_capture(root)  # noqa: SLF001


def _fake_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[bytes, dict[str, object], list[dict[str, object]]]:
    source_lock_raw = b'{"source_lock":"fixture"}'
    source_lock_origin = engine.object_identity_for_bytes(
        uri="gs://origin-fixture/source-lock.json",
        generation="901",
        raw=source_lock_raw,
    )
    worlds = []
    frozen = []
    for ordinal, production in enumerate(preparer.WORLD_ORIGINS):
        raw = f"fixture-world-{ordinal}".encode()
        origin = engine.object_identity_for_bytes(
            uri=f"gs://origin-fixture/worlds/R{ordinal}.npz",
            generation=str(910 + ordinal),
            raw=raw,
        )
        row = {
            "block_id": production["block_id"],
            "panel_id": production["panel_id"],
            "expected_candidate_count": production["expected_candidate_count"],
            "origin": origin,
        }
        frozen.append(row)
        worlds.append({**row, "raw": raw})
    monkeypatch.setattr(preparer, "WORLD_ORIGINS", tuple(frozen))
    return source_lock_raw, source_lock_origin, worlds


def _release() -> dict[str, object]:
    digest = "sha256:" + "b" * 64
    return {
        "engine_version": "corpus-retrieval-engine-v1",
        "code_repository": preparer.CODE_REPOSITORY,
        "code_commit": "a" * 40,
        "image_uri": f"us-central1-docker.pkg.dev/p/r/i@{digest}",
        "image_digest": digest,
    }


def test_publication_binds_real_query_identity_and_builds_exact_manifests(
    capture_bundle: dict[str, object], monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_raw, source_origin, worlds = _fake_sources(monkeypatch)
    storage = MemoryCreateOnceStorage()
    result = preparer._publish_input_bundle(  # noqa: SLF001
        capture_bundle=capture_bundle,
        source_lock_raw=source_raw,
        source_lock_origin=source_origin,
        world_sources=worlds,
        engine_release=_release(),
        created_at_utc="2026-08-21T18:00:00Z",
        publish_create_once=storage.publish,
        read_exact=storage.read,
        assert_pristine=storage.assert_pristine,
    )

    query_identity = result["publication_receipt"]["query_authority"]
    candidate = engine.validate_candidate_rows_object(
        engine.parse_canonical_json_bytes(
            storage.read(result["publication_receipt"]["candidate_rows_object"]),
            label="candidate rows",
        )
    )
    players = engine.validate_player_catalog_object(
        engine.parse_canonical_json_bytes(
            storage.read(result["publication_receipt"]["player_catalog_object"]),
            label="player catalog",
        )
    )
    assert candidate["source_authority"] == query_identity
    assert players["source_authority"] == query_identity
    assert storage.read(query_identity) == capture_bundle["query_authority_raw"]
    assert candidate["source_query_receipt"] == capture_bundle[
        "query_authority"
    ]["candidate_query"]

    snapshot = engine.validate_snapshot_manifest(result["snapshot_manifest"])
    suite = engine.validate_suite_manifest(result["suite_manifest"])
    assert suite["snapshot_manifest_identity"] == result[
        "snapshot_manifest_identity"
    ]
    assert snapshot["producer"]["producer_authority"] == result[
        "publication_receipt"
    ]["producer_authority"]
    assert [
        row["artifact_object"] for row in snapshot["tasks"][0]["world_blocks"]
    ] == [row["staged"] for row in result["publication_receipt"]["world_blocks"]]
    assert all(
        row["artifact_object"]["uri"].startswith(preparer.INPUT_PREFIX)
        for row in snapshot["tasks"][0]["world_blocks"]
    )
    assert suite["suite_manifest_uri"] == preparer.SUITE_MANIFEST_URI

    receipt = result["publication_receipt"]
    preparer._validate_self_hash(  # noqa: SLF001
        receipt,
        field="input_publication_sha256",
        label="publication receipt",
    )
    assert receipt["publication_order_before_receipt"][0] == (
        preparer.QUERY_AUTHORITY_URI
    )
    assert preparer.PUBLICATION_RECEIPT_URI not in receipt[
        "publication_order_before_receipt"
    ]
    assert set(storage.objects) == set(preparer._planned_publication_uris())  # noqa: SLF001
    assert storage.read(result["publication_receipt_identity"]) == (
        engine.canonical_json_bytes(receipt)
    )
    assert storage.pristine_calls == [[preparer.INPUT_PREFIX, preparer.OUTPUT_PREFIX]]


def test_capture_content_mutation_fails_before_publication(tmp_path: Path) -> None:
    root = tmp_path / "capture"
    _write_capture(root)
    path = root / "candidate-query-rows.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(
        preparer.RetrievalInputPublicationError,
        match="content identity differs",
    ):
        preparer._load_capture(root)  # noqa: SLF001


def test_same_count_candidate_substitution_fails_before_first_write(
    capture_bundle: dict[str, object], monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_raw, source_origin, worlds = _fake_sources(monkeypatch)
    substituted = deepcopy(capture_bundle)
    substituted["candidate_rows"][0]["tag"] = "lev"
    substituted["candidate_rows"][0]["all_tags"] = ["lev"]
    storage = MemoryCreateOnceStorage()
    with pytest.raises(
        preparer.RetrievalInputPublicationError,
        match="query authority could not bind source bodies",
    ):
        preparer._publish_input_bundle(  # noqa: SLF001
            capture_bundle=substituted,
            source_lock_raw=source_raw,
            source_lock_origin=source_origin,
            world_sources=worlds,
            engine_release=_release(),
            created_at_utc="2026-08-21T18:00:00Z",
            publish_create_once=storage.publish,
            read_exact=storage.read,
            assert_pristine=storage.assert_pristine,
        )
    assert storage.pristine_calls == []
    assert storage.objects == {}


def test_existing_namespace_collision_fails_before_any_write(
    capture_bundle: dict[str, object], monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_raw, source_origin, worlds = _fake_sources(monkeypatch)
    storage = MemoryCreateOnceStorage()
    unrelated = f"{preparer.INPUT_PREFIX}unexpected.json"
    raw = b"existing"
    storage.objects[unrelated] = ({
        "uri": unrelated,
        "generation": "99",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }, raw)
    with pytest.raises(
        preparer.RetrievalInputPublicationError,
        match="namespace is not pristine",
    ):
        preparer._publish_input_bundle(  # noqa: SLF001
            capture_bundle=capture_bundle,
            source_lock_raw=source_raw,
            source_lock_origin=source_origin,
            world_sources=worlds,
            engine_release=_release(),
            created_at_utc="2026-08-21T18:00:00Z",
            publish_create_once=storage.publish,
            read_exact=storage.read,
            assert_pristine=storage.assert_pristine,
        )
    assert set(storage.objects) == {unrelated}


def test_racing_object_collision_never_publishes_snapshot_or_suite(
    capture_bundle: dict[str, object], monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_raw, source_origin, worlds = _fake_sources(monkeypatch)
    storage = MemoryCreateOnceStorage(race_uri=preparer.CANDIDATE_ROWS_URI)
    with pytest.raises(
        preparer.RetrievalInputPublicationError,
        match="create-once publication failed",
    ):
        preparer._publish_input_bundle(  # noqa: SLF001
            capture_bundle=capture_bundle,
            source_lock_raw=source_raw,
            source_lock_origin=source_origin,
            world_sources=worlds,
            engine_release=_release(),
            created_at_utc="2026-08-21T18:00:00Z",
            publish_create_once=storage.publish,
            read_exact=storage.read,
            assert_pristine=storage.assert_pristine,
        )
    assert set(storage.objects) == {preparer.QUERY_AUTHORITY_URI}
    assert preparer.SNAPSHOT_MANIFEST_URI not in storage.objects
    assert preparer.SUITE_MANIFEST_URI not in storage.objects
    assert preparer.PUBLICATION_RECEIPT_URI not in storage.objects
