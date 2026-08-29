from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from nfl_dfs.research import (
    corpus_extreme_tail_generation_additions as generation_source,
)
from nfl_dfs.research import (
    corpus_extreme_tail_hard230_population_successor_v1 as hard_successor,
)
from nfl_dfs.research import corpus_r6_hard230_selector_bridge_v1 as bridge


_OPERATOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_corpus_r6_hard230_selector_bridge_v1.py"
)
_OPERATOR_SPEC = importlib.util.spec_from_file_location(
    "run_corpus_r6_hard230_selector_bridge_v1", _OPERATOR_PATH
)
assert _OPERATOR_SPEC is not None and _OPERATOR_SPEC.loader is not None
operator = importlib.util.module_from_spec(_OPERATOR_SPEC)
_OPERATOR_SPEC.loader.exec_module(operator)


def _identity(name: str, raw_hash: str | None = None) -> dict[str, object]:
    return {
        "uri": f"gs://fixture/{name}.json",
        "generation": "1",
        "sha256": raw_hash or ("a" * 64),
        "bytes": 1,
    }


def test_exact_transport_uses_bounded_large_object_retry_window() -> None:
    raw = b'{"complete":true}'
    calls: list[tuple[str, dict[str, object]]] = []

    class Blob:
        generation = "17"

        def upload_from_string(self, value: bytes, **kwargs: object) -> None:
            assert value == raw
            calls.append(("upload", dict(kwargs)))

        def download_as_bytes(self, **kwargs: object) -> bytes:
            calls.append(("download", dict(kwargs)))
            return raw

    blob = Blob()

    class Bucket:
        def blob(self, _name: str, generation: int | None = None) -> Blob:
            if generation is not None:
                assert generation == 17
            return blob

    class Client:
        def bucket(self, _name: str) -> Bucket:
            return Bucket()

    retry = object()
    transport = operator.GCSExactTransportV1.__new__(
        operator.GCSExactTransportV1
    )
    transport._client = Client()
    transport._retry = retry

    identity = transport.publish_create_once("gs://fixture/terminal.json", raw)

    assert identity == {
        "uri": "gs://fixture/terminal.json",
        "generation": "17",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    assert calls == [
        (
            "upload",
            {
                "content_type": "application/json",
                "if_generation_match": 0,
                "timeout": operator.GCS_IO_TIMEOUT_SECONDS,
                "retry": retry,
            },
        ),
        (
            "download",
            {
                "if_generation_match": 17,
                "timeout": operator.GCS_IO_TIMEOUT_SECONDS,
                "retry": retry,
            },
        ),
    ]


def _fixture(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    rng = np.random.default_rng(20260829)
    player_ids = [f"P{ordinal:04d}" for ordinal in range(240)]
    registry = [{"id": player_id} for player_id in player_ids]
    matrix = np.ascontiguousarray(
        rng.integers(-2_000, 38_000, size=(len(player_ids), 80), dtype=np.int64),
        dtype="<i8",
    )
    matrix_sha = generation_source.canonical_score_matrix_sha256_v1(matrix)
    score_identity = {
        "canonical_score_matrix_sha256": matrix_sha,
        "player_registry_sha256": bridge._hash(registry),
    }

    def population(population_id: str, offset: int) -> dict[str, object]:
        rows = []
        for ordinal in range(160):
            # A deterministic rotating design supplies many distinct legal-size
            # roster sets without making the DPP kernel singular.
            roster = sorted({
                player_ids[(offset + ordinal * 7 + step * 19) % len(player_ids)]
                for step in range(9)
            })
            assert len(roster) == 9
            roster_sha = bridge._hash(roster)
            rows.append({
                "lineup_id": f"lineup-v1-{roster_sha}",
                "roster_player_ids": roster,
                "roster_sha256": roster_sha,
                "first_occurrence_ordinal": ordinal,
                "fit_world_score_vector_sha256": sha256(
                    f"{population_id}:{ordinal}".encode()
                ).hexdigest(),
            })
        return {
            "population_id": population_id,
            "population_lineup_count": len(rows),
            "population_rosters": rows,
            "population_rosters_sha256": bridge._hash(rows),
            "uses_heldout_scores": False,
            "uses_realized_outcomes": False,
        }

    control = population(hard_successor.CONTROL_POPULATION_ID, 0)
    challenger = population(hard_successor.CHALLENGER_POPULATION_ID, 3)
    process_identity = _identity("process")
    task = {
        "task_index": 0,
        "slate_id": "2023-w01",
        "complete": True,
        "process_receipt_identity": process_identity,
        "score_matrix_identity": score_identity,
        "source_member_identity": {"fixture": True},
        "task_result_sha256": "b" * 64,
        "score_blind_control_population_count": 160,
        "score_blind_control_population_sha256": control[
            "population_rosters_sha256"
        ],
        "hard230_challenger_population_count": 160,
        "hard230_challenger_population_sha256": challenger[
            "population_rosters_sha256"
        ],
    }
    process = {
        "task_index": 0,
        "slate_id": "2023-w01",
        "process_receipt_sha256": "c" * 64,
    }
    scientific = {
        "source_lineage": {
            "player_registry_sha256": bridge._hash(registry),
            "score_matrix_sha256": matrix_sha,
        },
        "score_blind_control_population": control,
        "hard230_challenger_population": challenger,
    }
    monkeypatch.setattr(
        bridge,
        "_validated_source_receipts",
        lambda **_kwargs: (task, process, scientific),
    )
    return {
        "source_ordinal": 0,
        "later_source_identity": _identity("later"),
        "task_result_identity": _identity("task"),
        "task_result": task,
        "process_receipt_identity": process_identity,
        "process_receipt": process,
        "player_registry": registry,
        "score_matrix": matrix,
        "score_matrix_identity": score_identity,
    }


def test_bridge_reuses_nested_orders_and_preserves_populations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _fixture(monkeypatch)
    result = bridge.run_hard230_selector_slate_v1(**inputs)

    assert result["schema_version"] == bridge.SLATE_RESULT_SCHEMA
    assert result["equal_sample_lineup_count"] == 160
    assert result["selector_fit_blocks"] == ["R1", "R2", "R3", "R4"]
    assert len(result["population_results"]) == 2
    for population in result["population_results"]:
        assert population["full_population_lineup_count"] == 160
        assert len(population["full_population_lineups"]) == 160
        assert len(population["sampled_lineup_ids"]) == 160
        assert len(population["selector_summaries"]) == 4
        assert len(population["books"]) == 12
        for native in population["selector_summaries"][:3]:
            assert native["exact_grouped_rank80_prefix_parity"] is True
            assert (
                native["grouped_rank80_lineup_ids"]
                == native["ranked_lineup_ids"][:80]
            )
        assert sorted(
            book["coordinate"]["entry_budget"] for book in population["books"]
        ) == [80, 80, 80, 80, 100, 100, 100, 100, 150, 150, 150, 150]

    normalized = bridge.normalized_slate_for_grader_v1(result)
    assert len(normalized["populations"]) == 2
    assert len(normalized["books"]) == 24
    assert all(
        book["coordinate"]["adapter_id"] == bridge.ADAPTER_ID
        for book in normalized["books"]
    )


def test_bridge_pure_replay_and_mutation_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _fixture(monkeypatch)
    result = bridge.run_hard230_selector_slate_v1(**inputs)
    assert bridge.validate_hard230_selector_slate_v1(
        result, **inputs
    ) == result

    forged = deepcopy(result)
    forged["population_results"][0]["books"][0]["selected_lineup_ids"][0] = (
        forged["population_results"][0]["books"][2]["selected_lineup_ids"][-1]
    )
    with pytest.raises(
        bridge.CorpusR6Hard230SelectorBridgeV1Error,
        match="differs from exact pure replay",
    ):
        bridge.validate_hard230_selector_slate_v1(forged, **inputs)


def test_r0_is_excluded_and_rehashed_nonprefix_book_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _fixture(monkeypatch)
    result = bridge.run_hard230_selector_slate_v1(**inputs)
    population = result["population_results"][0]
    original_scores = bridge._lineup_score_matrix_dk(
        lineups=population["full_population_lineups"],
        sampled_ids=population["sampled_lineup_ids"],
        player_ids=[row["id"] for row in inputs["player_registry"]],
        player_score_matrix_milli=inputs["score_matrix"],
    )
    r0_changed = inputs["score_matrix"].copy(order="C")
    worlds_per_block = r0_changed.shape[1] // len(bridge.WORLD_BLOCKS)
    r0_changed[:, :worlds_per_block] += 900_000_000
    changed_scores = bridge._lineup_score_matrix_dk(
        lineups=population["full_population_lineups"],
        sampled_ids=population["sampled_lineup_ids"],
        player_ids=[row["id"] for row in inputs["player_registry"]],
        player_score_matrix_milli=r0_changed,
    )
    np.testing.assert_array_equal(original_scores, changed_scores)

    forged = deepcopy(result)
    forged_population = forged["population_results"][0]
    forged_book = forged_population["books"][0]
    forged_book["selected_lineup_ids"][0] = forged_population[
        "selector_summaries"
    ][0]["ranked_lineup_ids"][100]
    forged_book["selected_lineup_ids_sha256"] = bridge._hash(
        forged_book["selected_lineup_ids"]
    )
    forged_book["book_sha256"] = bridge._hash({
        key: value for key, value in forged_book.items() if key != "book_sha256"
    })
    forged_population["selector_summaries"][0]["book_sha256s"][0] = (
        forged_book["book_sha256"]
    )
    forged_population["selector_summaries_sha256"] = bridge._hash(
        forged_population["selector_summaries"]
    )
    forged_population["books_sha256"] = bridge._hash(forged_population["books"])
    forged_population["population_result_sha256"] = bridge._hash({
        key: value
        for key, value in forged_population.items()
        if key != "population_result_sha256"
    })
    forged["population_results_sha256"] = bridge._hash(
        forged["population_results"]
    )
    forged["slate_result_sha256"] = bridge._hash({
        key: value for key, value in forged.items() if key != "slate_result_sha256"
    })
    with pytest.raises(
        bridge.CorpusR6Hard230SelectorBridgeV1Error,
        match="exact nested prefix",
    ):
        bridge.normalized_slate_for_grader_v1(forged)


def test_terminal_requires_exact_54_and_generic_coordinate_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _fixture(monkeypatch)
    base = bridge.run_hard230_selector_slate_v1(**inputs)
    results = []
    for ordinal in range(54):
        row = deepcopy(base)
        row["source_ordinal"] = ordinal
        row["slate_id"] = f"fixture-{ordinal:02d}"
        row["task_result_identity"] = _identity(f"task-{ordinal}")
        row["process_receipt_identity"] = _identity(f"process-{ordinal}")
        row["task_result_sha256"] = sha256(f"task-{ordinal}".encode()).hexdigest()
        row["process_receipt_sha256"] = sha256(
            f"process-{ordinal}".encode()
        ).hexdigest()
        row["slate_result_sha256"] = bridge._hash({
            key: value for key, value in row.items() if key != "slate_result_sha256"
        })
        results.append(row)

    terminal = bridge.build_hard230_selector_terminal_v1(
        hard230_final_root_identity=_identity("full-root"),
        hard230_final_root_sha256="d" * 64,
        hard230_source_task_manifest_identity=_identity("source-manifest"),
        hard230_source_task_manifest_sha256="e" * 64,
        task0_smoke_receipt_identity=_identity("task0-smoke"),
        task0_smoke_receipt_sha256="f" * 64,
        later_source_identity=base["later_source_identity"],
        output_prefix="gs://fixture/run/selector-bridge/",
        slate_results=results,
    )
    assert bridge.validate_hard230_selector_terminal_v1(terminal) == terminal
    normalized = bridge.normalized_terminal_for_grader_v1(terminal)
    assert len(normalized) == 54
    assert all(len(slate["books"]) == 24 for slate in normalized)

    with pytest.raises(
        bridge.CorpusR6Hard230SelectorBridgeV1Error,
        match="54-slate coverage",
    ):
        bridge.build_hard230_selector_terminal_v1(
            hard230_final_root_identity=_identity("full-root"),
            hard230_final_root_sha256="d" * 64,
            hard230_source_task_manifest_identity=_identity("source-manifest"),
            hard230_source_task_manifest_sha256="e" * 64,
            task0_smoke_receipt_identity=_identity("task0-smoke"),
            task0_smoke_receipt_sha256="f" * 64,
            later_source_identity=base["later_source_identity"],
            output_prefix="gs://fixture/run/selector-bridge/",
            slate_results=results[:-1],
        )


def test_operator_scope_topology_smoke_receipt_and_outcome_binding() -> None:
    source_manifest = {
        "output_prefix": "gs://fixture/hard230/run/",
        "later_source_freeze_identity": _identity("later"),
    }
    prefix = operator._selector_output_prefix(source_manifest)
    assert prefix == "gs://fixture/hard230/run/selector-bridge/"
    assert operator._scope_output_uri(
        output_prefix=prefix, mode="task0-smoke"
    ) != operator._scope_output_uri(output_prefix=prefix, mode="full-54")

    task0_root = {
        "final_root_sha256": "1" * 64,
        "source_task_manifest_identity": _identity("source-manifest"),
        "source_task_manifest_sha256": "2" * 64,
    }
    slate_result = {"slate_result_sha256": "3" * 64}
    result_identity = {
        **_identity("ignored"),
        "uri": operator._scope_output_uri(
            output_prefix=prefix, mode="task0-smoke"
        ),
    }
    receipt = operator._build_task0_smoke_receipt(
        output_prefix=prefix,
        hard230_task0_root=task0_root,
        hard230_task0_root_identity=_identity("task0-root"),
        source_manifest=source_manifest,
        slate_result=slate_result,
        slate_result_identity=result_identity,
    )
    assert operator._validate_task0_smoke_receipt(receipt) == receipt
    forged_receipt = deepcopy(receipt)
    forged_receipt["slate_result_identity"]["uri"] = (
        operator._scope_output_uri(output_prefix=prefix, mode="full-54")
    )
    forged_receipt["smoke_receipt_sha256"] = operator._hash({
        key: value
        for key, value in forged_receipt.items()
        if key != "smoke_receipt_sha256"
    })
    with pytest.raises(
        operator.RunCorpusR6Hard230SelectorBridgeV1Error,
        match="smoke result URI",
    ):
        operator._validate_task0_smoke_receipt(forged_receipt)

    terminal = {
        "later_source_identity": _identity("later"),
        "slate_results": [
            {"slate_id": f"fixture-{ordinal:02d}"} for ordinal in range(54)
        ],
    }
    snapshot = {"later_source_freeze_identity": _identity("later")}
    slate_keys = {
        ordinal: (2023, ordinal + 1, f"fixture-{ordinal:02d}")
        for ordinal in range(54)
    }
    operator._validate_outcome_terminal_binding(
        terminal=terminal, snapshot=snapshot, slate_keys=slate_keys
    )
    mismatched = dict(slate_keys)
    mismatched[0] = (2023, 1, "wrong-slate")
    with pytest.raises(
        operator.RunCorpusR6Hard230SelectorBridgeV1Error,
        match="terminal/outcome source or slate",
    ):
        operator._validate_outcome_terminal_binding(
            terminal=terminal, snapshot=snapshot, slate_keys=mismatched
        )


def test_full54_rejects_task0_smoke_substitution_before_derivation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_identity = _identity("source-manifest")
    required_smoke_root = _identity("required-task0-root")
    later_identity = _identity("later")
    source_manifest = {
        "output_prefix": "gs://fixture/hard230/run/",
        "later_source_freeze_identity": later_identity,
    }
    full_root = {
        "scope_id": "full-54",
        "scientific_task_count": 54,
        "source_task_manifest_identity": source_identity,
        "source_task_manifest_sha256": "1" * 64,
        "required_smoke_final_root_identity": required_smoke_root,
        "required_smoke_final_root_sha256": "2" * 64,
    }
    monkeypatch.setattr(
        operator,
        "_open_final_root",
        lambda *_args, **_kwargs: (
            full_root,
            _identity("full-root"),
            source_manifest,
        ),
    )
    substituted_receipt = {
        "source_task_manifest_identity": source_identity,
        "source_task_manifest_sha256": "1" * 64,
        "hard230_task0_final_root_identity": _identity("wrong-task0-root"),
        "hard230_task0_final_root_sha256": "2" * 64,
        "later_source_identity": later_identity,
        "output_prefix": operator._selector_output_prefix(source_manifest),
    }
    monkeypatch.setattr(
        operator,
        "_replay_task0_smoke_authority",
        lambda **_kwargs: (substituted_receipt, _identity("smoke-receipt")),
    )
    monkeypatch.setattr(
        operator,
        "_derive_slate_results",
        lambda **_kwargs: pytest.fail("full derivation began before smoke gate"),
    )
    with pytest.raises(
        operator.RunCorpusR6Hard230SelectorBridgeV1Error,
        match="lacks its exact task0 smoke authority",
    ):
        operator.derive_from_request_v1({
            "mode": "full-54",
            "hard230_final_root_identity": _identity("full-root"),
            "task0_smoke_receipt_identity": _identity("smoke-receipt"),
            "output_prefix": operator._selector_output_prefix(source_manifest),
        }, store=object())


def test_grade_reuses_create_last_terminal_without_duplicate_selector_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    root_identity = _identity("full-root")
    manifest_identity = _identity("source-manifest")
    smoke_identity = _identity("smoke-receipt")
    later_identity = _identity("later")
    outcome_identity = _identity("outcome")
    output_prefix = "gs://fixture/hard230/run/selector-bridge/"
    terminal = {
        "terminal_uri": f"{output_prefix}full-54/terminal.json",
        "terminal_sha256": "9" * 64,
        "output_prefix": output_prefix,
        "hard230_final_root_identity": root_identity,
        "hard230_final_root_sha256": "1" * 64,
        "hard230_source_task_manifest_identity": manifest_identity,
        "hard230_source_task_manifest_sha256": "2" * 64,
        "task0_smoke_receipt_identity": smoke_identity,
        "task0_smoke_receipt_sha256": "3" * 64,
        "later_source_identity": later_identity,
        "slate_results": [],
    }
    terminal_identity = {
        **_identity("terminal", raw_hash="a" * 64),
        "uri": terminal["terminal_uri"],
    }
    root = {
        "final_root_sha256": "1" * 64,
        "scope_id": "full-54",
        "scientific_task_count": 54,
        "source_task_manifest_identity": manifest_identity,
        "source_task_manifest_sha256": "2" * 64,
    }
    manifest = {
        "later_source_freeze_identity": later_identity,
        "output_prefix": "gs://fixture/hard230/run/",
    }
    smoke = {
        "smoke_receipt_sha256": "3" * 64,
        "source_task_manifest_identity": manifest_identity,
        "source_task_manifest_sha256": "2" * 64,
        "hard230_task0_final_root_identity": _identity("task0-root"),
        "hard230_task0_final_root_sha256": "4" * 64,
    }
    root["required_smoke_final_root_identity"] = smoke[
        "hard230_task0_final_root_identity"
    ]
    root["required_smoke_final_root_sha256"] = smoke[
        "hard230_task0_final_root_sha256"
    ]

    monkeypatch.setattr(
        operator,
        "_read_json",
        lambda *_args, **_kwargs: (terminal, terminal_identity),
    )
    monkeypatch.setattr(
        operator.bridge,
        "validate_hard230_selector_terminal_v1",
        lambda value: events.append("terminal") or value,
    )
    monkeypatch.setattr(
        operator,
        "_open_final_root",
        lambda *_args, **_kwargs: events.append("root")
        or (root, root_identity, manifest),
    )
    monkeypatch.setattr(
        operator,
        "_replay_task0_smoke_authority",
        lambda **_kwargs: events.append("smoke") or (smoke, smoke_identity),
    )
    monkeypatch.setattr(
        operator,
        "_derive_slate_results",
        lambda **_kwargs: pytest.fail("grade duplicated selector derivation"),
    )
    monkeypatch.setattr(
        operator.bridge,
        "normalized_terminal_for_grader_v1",
        lambda _value: events.append("normalize") or tuple(),
    )
    snapshot = {
        "outcome_snapshot_sha256": "5" * 64,
        "later_source_freeze_identity": later_identity,
    }
    monkeypatch.setattr(
        operator.grader,
        "open_outcome_snapshot_surface_v1",
        lambda **_kwargs: events.append("outcome")
        or (snapshot, outcome_identity, {}, {}),
    )
    monkeypatch.setattr(
        operator,
        "_validate_outcome_terminal_binding",
        lambda **_kwargs: events.append("binding"),
    )
    monkeypatch.setattr(
        operator.grader,
        "score_normalized_slates_v1",
        lambda **_kwargs: events.append("score") or [],
    )
    monkeypatch.setattr(
        operator.grader,
        "aggregate_normalized_slate_grades_v1",
        lambda _grades: [],
    )
    monkeypatch.setattr(
        operator,
        "_publish_json",
        lambda **_kwargs: events.append("publish") or _identity("grade"),
    )

    class Store:
        @staticmethod
        def read_exact(_identity_value: object) -> bytes:
            raise AssertionError("patched outcome opener must own exact reads")

    result = operator.grade_from_request_v1({
        "terminal_identity": terminal_identity,
        "outcome_snapshot_identity": outcome_identity,
    }, store=Store())

    assert result["complete"] is True
    assert events == [
        "terminal", "root", "smoke", "normalize", "outcome", "binding",
        "score", "publish",
    ]
