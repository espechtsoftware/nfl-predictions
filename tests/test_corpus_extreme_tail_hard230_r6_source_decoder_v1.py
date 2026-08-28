from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json

import numpy as np
import pytest

from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import (
    corpus_extreme_tail_hard230_r6_source_decoder_v1 as decoder,
)


SLATE = "2023-w01"


def _players() -> list[dict[str, object]]:
    rows = [
        ("a-qb", "QB", "A", "B", "g1"),
        ("a-rb", "RB", "A", "B", "g1"),
        ("a-wr1", "WR", "A", "B", "g1"),
        ("a-wr2", "WR", "A", "B", "g1"),
        ("a-wr3", "WR", "A", "B", "g1"),
        ("b-rb", "RB", "B", "A", "g1"),
        ("b-wr1", "WR", "B", "A", "g1"),
        ("b-wr2", "WR", "B", "A", "g1"),
        ("c-dst", "DST", "C", "D", "g2"),
        ("c-te", "TE", "C", "D", "g2"),
        ("c-wr1", "WR", "C", "D", "g2"),
        ("c-wr2", "WR", "C", "D", "g2"),
    ]
    return [
        {
            "id": player_id,
            "pos": position,
            "team": team,
            "opp": opponent,
            "game_id": game,
            "salary": 5_500,
        }
        for player_id, position, team, opponent, game in sorted(rows)
    ]


def _artifact(
    *, block_ordinal: int, players: list[dict[str, object]], bad_id: bool = False,
    oversized_score: bool = False,
) -> bytes:
    player_ids = [str(row["id"]) for row in players]
    if block_ordinal % 2:
        player_ids.reverse()
    if bad_id:
        player_ids[-1] = "not-in-pit-catalog"
    values_by_id = {
        str(row["id"]): np.float32(index + 1 + block_ordinal / 10)
        for index, row in enumerate(players)
    }
    if oversized_score:
        values_by_id[player_ids[0]] = np.float32(1_000.25)
    draws = np.stack([
        np.full(
            decoder.WORLDS_PER_BLOCK,
            values_by_id.get(player_id, np.float32(0.0)),
            dtype=np.float32,
        )
        for player_id in player_ids
    ])
    output = BytesIO()
    np.savez_compressed(
        output,
        cand_ix=np.arange(2, dtype=np.int64),
        totals=np.zeros((2, decoder.WORLDS_PER_BLOCK), dtype=np.float32),
        tail_line=np.asarray([194.0], dtype=np.float32),
        player_ids=np.asarray(player_ids),
        player_draws=draws,
    )
    return output.getvalue()


class _MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, dict[str, object]]] = {}
        self.read_uris: list[str] = []

    def add(self, uri: str, payload: bytes, *, generation: int) -> dict[str, object]:
        identity = {
            "uri": uri,
            "generation": str(generation),
            "sha256": sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
        self.objects[uri] = (payload, identity)
        return dict(identity)

    def publish(self, uri: str, payload: bytes) -> dict[str, object]:
        if uri in self.objects:
            prior, identity = self.objects[uri]
            if prior != payload:
                raise RuntimeError("create-once collision differs")
            return dict(identity)
        return self.add(uri, payload, generation=len(self.objects) + 100)

    def read(self, identity: dict[str, object]) -> bytes:
        self.read_uris.append(str(identity["uri"]))
        payload, retained = self.objects[str(identity["uri"])]
        if retained != identity:
            raise RuntimeError("generation-pinned identity differs")
        return payload


def _fixture(
    monkeypatch: pytest.MonkeyPatch,
    *,
    bad_block: str | None = None,
    oversized_block: str | None = None,
) -> tuple[_MemoryStore, dict[str, object], list[dict[str, object]]]:
    store = _MemoryStore()
    players = _players()
    receipts = []
    for ordinal, block in enumerate(decoder.WORLD_BLOCKS):
        payload = _artifact(
            block_ordinal=ordinal,
            players=players,
            bad_id=block == bad_block,
            oversized_score=block == oversized_block,
        )
        identity = store.add(
            f"gs://hard230-decoder-fixture/input/{block}.npz",
            payload,
            generation=ordinal + 1,
        )
        receipts.append({
            "season": 2023,
            "week": 1,
            "block": block,
            "panel_run_id": f"fixture-{block}",
            "candidate_rows": 2,
            "updated": "2026-08-28T00:00:00+00:00",
            **identity,
        })
    freeze = {
        "freeze_sha256": "f" * 64,
        "slates": [{
            "slate_id": SLATE,
            "catalog": players,
            "catalog_sha256": legal.canonical_sha256(players),
            "artifact_receipts": receipts,
        }],
    }
    source_raw = json.dumps(
        freeze, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    source_identity = store.add(
        "gs://hard230-decoder-fixture/input/later-source-freeze.json",
        source_raw,
        generation=20,
    )

    calls: list[str] = []

    def validate_source(value, *, expected_freeze_sha256):
        calls.append(expected_freeze_sha256)
        assert value == freeze
        return value

    monkeypatch.setattr(
        decoder.later, "validate_source_freeze", validate_source
    )
    store.validation_calls = calls  # type: ignore[attr-defined]
    return store, source_identity, players


def _run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    bad_block: str | None = None,
    oversized_block: str | None = None,
):
    store, source_identity, players = _fixture(
        monkeypatch,
        bad_block=bad_block,
        oversized_block=oversized_block,
    )
    result = decoder.materialize_hard230_r6_source_v1(
        later_source_freeze_identity=source_identity,
        slate_id=SLATE,
        heldout_block="R4",
        output_prefix="gs://hard230-decoder-fixture/output/2023-w01/holdout-R4",
        read_exact=store.read,
        publish_create_once=store.publish,
    )
    return result, store, players


def test_decoder_aligns_r_blocks_and_emits_exact_successor_source(monkeypatch):
    result, store, players = _run(monkeypatch)
    assert result.training_blocks == ("R0", "R1", "R2", "R3")
    assert result.score_matrix.dtype == np.dtype("<i8")
    assert result.score_matrix.shape == (len(players), 40_000)
    assert result.score_matrix.flags.c_contiguous
    assert result.score_matrix.flags.writeable is False
    for player_index in range(len(players)):
        for block_index in range(4):
            source_value = np.float32(player_index + 1 + block_index / 10)
            expected = int(np.rint(float(source_value) * 1_000.0))
            assert result.score_matrix[player_index, block_index * 10_000] == expected
    assert result.source_member_identity["member_sha256"] == (
        result.source_member_identity["object_identity"]["sha256"]
    )
    assert result.score_matrix_identity["canonical_score_matrix_sha256"] == (
        result.source_lineage["score_matrix_sha256"]
    )
    assert result.derivation_proof["conversion_law_id"] == decoder.CONVERSION_LAW_ID
    assert result.derivation_proof["candidate_totals_materialized"] is False
    assert getattr(store, "validation_calls") == ["f" * 64]
    assert not any(uri.endswith("/R4.npz") for uri in store.read_uris)
    assert [row["block_id"] for row in result.score_block_identities] == [
        "R0", "R1", "R2", "R3"
    ]


def test_decoder_publication_is_create_once_and_byte_identical(monkeypatch):
    first, store, _ = _run(monkeypatch)
    source_identity = store.objects[
        "gs://hard230-decoder-fixture/input/later-source-freeze.json"
    ][1]
    second = decoder.materialize_hard230_r6_source_v1(
        later_source_freeze_identity=source_identity,
        slate_id=SLATE,
        heldout_block="R4",
        output_prefix="gs://hard230-decoder-fixture/output/2023-w01/holdout-R4",
        read_exact=store.read,
        publish_create_once=store.publish,
    )
    assert first.source_member_identity == second.source_member_identity
    assert first.matrix_artifact_identity == second.matrix_artifact_identity
    assert first.derivation_proof_identity == second.derivation_proof_identity
    assert np.array_equal(first.score_matrix, second.score_matrix)


def test_decoder_fails_before_publication_on_player_universe_drift(monkeypatch):
    store, source_identity, _ = _fixture(monkeypatch, bad_block="R2")
    with pytest.raises(
        decoder.Hard230R6SourceDecoderV1Error,
        match="R2 player IDs do not equal",
    ):
        decoder.materialize_hard230_r6_source_v1(
            later_source_freeze_identity=source_identity,
            slate_id=SLATE,
            heldout_block="R4",
            output_prefix="gs://hard230-decoder-fixture/output/drift",
            read_exact=store.read,
            publish_create_once=store.publish,
        )
    assert not any("/output/" in uri for uri in store.objects)


def test_decoder_fails_closed_on_milli_bound(monkeypatch):
    with pytest.raises(
        decoder.Hard230R6SourceDecoderV1Error,
        match="exceeds the milli-DK bound",
    ):
        _run(monkeypatch, oversized_block="R1")


def test_header_smoke_reads_only_shapes_and_dtypes(monkeypatch):
    store, _, _ = _fixture(monkeypatch)
    raw, identity = store.objects[
        "gs://hard230-decoder-fixture/input/R0.npz"
    ]
    receipt = {
        "block": "R0",
        "candidate_rows": 2,
        **identity,
    }
    smoke = decoder.smoke_r6_world_artifact_header_v1(receipt, raw)
    assert smoke["player_count"] == len(_players())
    assert smoke["player_draws_shape"] == [len(_players()), 10_000]
    assert smoke["player_draws_dtype"] == "<f4"
    assert smoke["array_values_materialized"] is False
    assert smoke["candidate_totals_materialized"] is False
    assert smoke["tail_line_materialized"] is False
    assert smoke["outcome_columns_read"] == []


def test_exact_input_read_detects_payload_tamper(monkeypatch):
    store, source_identity, _ = _fixture(monkeypatch)
    uri = "gs://hard230-decoder-fixture/input/R0.npz"
    _, identity = store.objects[uri]
    store.objects[uri] = (b"tampered", identity)
    with pytest.raises(
        decoder.Hard230R6SourceDecoderV1Error,
        match="R0 artifact differs from its exact content identity",
    ):
        decoder.materialize_hard230_r6_source_v1(
            later_source_freeze_identity=source_identity,
            slate_id=SLATE,
            heldout_block="R4",
            output_prefix="gs://hard230-decoder-fixture/output/tamper",
            read_exact=store.read,
            publish_create_once=store.publish,
        )
