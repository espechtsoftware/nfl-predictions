from __future__ import annotations

from copy import deepcopy
import base64
from hashlib import sha256

import numpy as np
import pytest

from nfl_dfs.research import corpus_r6_hard230_selector_bridge_v1 as bridge
from nfl_dfs.research import (
    corpus_r6_hard230_selector_confirmation_execution_v1 as execution,
)
from nfl_dfs.research import (
    corpus_r6_hard230_selector_confirmation_v1 as confirmation,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)
from scripts import run_corpus_r6_hard230_selector_confirmation_v1 as operator


def _identity(name: str) -> dict[str, object]:
    raw = name.encode()
    return {
        "uri": f"gs://fixture/{name}.json",
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], dict[str, object]]:
    populations: list[dict[str, object]] = []
    matrices: dict[str, np.ndarray] = {}
    source_selectors = [
        ("native-grouped-rank150", rank_id)
        for _grouped_id, rank_id in bridge.NATIVE_SELECTORS
    ] + [("effective-independent-shots-dpp", bridge.DPP_SELECTOR_ID)]
    for population_ordinal, spec in enumerate(bridge.POPULATION_SPECS):
        role, population_id, *_ = spec
        lineups = []
        for lineup_ordinal in range(150):
            roster = [
                f"p-{population_ordinal}-{lineup_ordinal:03d}-{slot}"
                for slot in range(9)
            ]
            roster_sha = bridge._hash(roster)
            lineups.append(
                {
                    "lineup_id": f"lineup-v1-{roster_sha}",
                    "roster_player_ids": roster,
                    "roster_sha256": roster_sha,
                }
            )
        sampled = [str(row["lineup_id"]) for row in lineups]
        rng = np.random.default_rng(20260829 + population_ordinal)
        matrix = np.ascontiguousarray(
            rng.normal(185.0, 28.0, size=(150, 40)), dtype=np.float64
        )
        matrices[role] = matrix
        source_books = []
        for family, selector_id in source_selectors:
            for budget in confirmation.ENTRY_BUDGETS:
                source_books.append(
                    {
                        "coordinate": {
                            "adapter_id": bridge.ADAPTER_ID,
                            "metric_kind": "selected-book",
                            "population_role": role,
                            "population_id": population_id,
                            "selector_family": family,
                            "selector_id": selector_id,
                            "entry_budget": budget,
                        },
                        "selected_lineup_ids": sampled[:budget],
                    }
                )
        populations.append(
            {
                "population_role": role,
                "population_id": population_id,
                "full_population_lineups": lineups,
                "sampled_lineup_ids": sampled,
                "selector_fit_score_shape": [150, 40],
                "selector_fit_score_matrix_sha256": successor._matrix_sha(matrix),
                "books": source_books,
            }
        )
    source = {
        "source_ordinal": 0,
        "slate_id": "2023-w01",
        "slate_result_sha256": "a" * 64,
        "generator_origin_block": bridge.GENERATOR_ORIGIN_BLOCK,
        "selector_fit_blocks": list(bridge.SELECTOR_BLOCKS),
        "population_results": populations,
    }
    monkeypatch.setattr(
        confirmation.bridge,
        "validate_hard230_selector_slate_v1",
        lambda *_args, **_kwargs: source,
    )
    result = confirmation.build_hard230_selector_confirmation_v1(
        bridge_slate=source,
        bridge_replay_inputs={},
        training_score_matrices=matrices,
    )
    return source, result


def _normalized_source(source: dict[str, object]) -> dict[str, object]:
    return {
        "source_ordinal": source["source_ordinal"],
        "slate_id": source["slate_id"],
        "populations": [
            {
                "population_id": population["population_id"],
                "dimensions": {
                    "population_role": population["population_role"],
                    "population_id": population["population_id"],
                },
                "lineups": population["full_population_lineups"],
            }
            for population in source["population_results"]
        ],
        "books": [],
        "later_source_identity": _identity("later"),
    }


def test_structural_seam_emits_42_gradeable_books_and_rejects_rehashed_escape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, result = _fixture(monkeypatch)
    assert execution.validate_confirmation_slate_structure_v1(
        result, bridge_slate=source
    ) == result
    monkeypatch.setattr(
        execution.bridge,
        "normalized_slate_for_grader_v1",
        lambda value: _normalized_source(value),
    )
    normalized = execution.normalized_confirmation_slate_v1(
        result, bridge_slate=source
    )
    assert len(normalized["books"]) == 42

    forged = deepcopy(result)
    forged_book = forged["books"][0]
    forged_book["selected_lineup_ids"][0] = "outside-sealed-population"
    forged_book["selected_lineup_ids_sha256"] = execution._hash(
        forged_book["selected_lineup_ids"]
    )
    forged_book["book_sha256"] = execution._hash(
        {key: value for key, value in forged_book.items() if key != "book_sha256"}
    )
    forged["books_sha256"] = execution._hash(forged["books"])
    forged["confirmation_sha256"] = execution._hash(
        {
            key: value
            for key, value in forged.items()
            if key != "confirmation_sha256"
        }
    )
    with pytest.raises(
        execution.CorpusR6Hard230SelectorConfirmationExecutionV1Error,
        match="selected book differs",
    ):
        execution.validate_confirmation_slate_structure_v1(
            forged, bridge_slate=source
        )


def test_create_last_terminal_requires_exact_54_and_validates_generic_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_source, base_result = _fixture(monkeypatch)
    source_slates = []
    results = []
    for ordinal in range(54):
        source = deepcopy(base_source)
        source["source_ordinal"] = ordinal
        source["slate_id"] = f"fixture-{ordinal:02d}"
        source["slate_result_sha256"] = sha256(
            f"bridge-{ordinal}".encode()
        ).hexdigest()
        result = deepcopy(base_result)
        result["source_ordinal"] = ordinal
        result["slate_id"] = source["slate_id"]
        result["bridge_slate_sha256"] = source["slate_result_sha256"]
        result["confirmation_sha256"] = execution._hash(
            {
                key: value
                for key, value in result.items()
                if key != "confirmation_sha256"
            }
        )
        source_slates.append(source)
        results.append(result)
    source_terminal = {
        "terminal_uri": "gs://fixture/run/selector-bridge/full-54/terminal.json",
        "terminal_sha256": "b" * 64,
        "output_prefix": "gs://fixture/run/selector-bridge/",
        "later_source_identity": _identity("later"),
        "slate_results": source_slates,
    }
    monkeypatch.setattr(
        execution.bridge,
        "validate_hard230_selector_terminal_v1",
        lambda _value: source_terminal,
    )
    monkeypatch.setattr(
        execution.bridge,
        "normalized_slate_for_grader_v1",
        lambda value: _normalized_source(value),
    )
    prefix = execution.confirmation_output_prefix_v1(source_terminal)
    terminal = execution.build_confirmation_terminal_v1(
        bridge_terminal=source_terminal,
        bridge_terminal_identity={
            **_identity("bridge-terminal"),
            "uri": source_terminal["terminal_uri"],
        },
        task0_smoke_receipt_identity=_identity("smoke"),
        task0_smoke_receipt_sha256="c" * 64,
        terminal_build_receipt_identity=_identity("build"),
        terminal_build_receipt_sha256="d" * 64,
        source_commit_sha="1" * 40,
        immutable_image_digest=f"sha256:{'2' * 64}",
        output_prefix=prefix,
        slate_results=results,
    )
    assert terminal["source_slate_count"] == 54
    assert terminal["uses_realized_outcomes"] is False
    assert execution.validate_confirmation_terminal_v1(
        terminal, bridge_terminal=source_terminal
    ) == terminal
    with pytest.raises(
        execution.CorpusR6Hard230SelectorConfirmationExecutionV1Error,
        match="exactly 54",
    ):
        execution.build_confirmation_terminal_v1(
            bridge_terminal=source_terminal,
            bridge_terminal_identity={
                **_identity("bridge-terminal"),
                "uri": source_terminal["terminal_uri"],
            },
            task0_smoke_receipt_identity=_identity("smoke"),
            task0_smoke_receipt_sha256="c" * 64,
            terminal_build_receipt_identity=_identity("build"),
            terminal_build_receipt_sha256="d" * 64,
            source_commit_sha="1" * 40,
            immutable_image_digest=f"sha256:{'2' * 64}",
            output_prefix=prefix,
            slate_results=results[:-1],
        )


def test_grade_opens_outcomes_only_after_terminal_and_bridge_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    bridge_identity = _identity("bridge-terminal")
    terminal_identity = _identity("confirmation-terminal")
    outcome_identity = _identity("outcome")
    later_identity = _identity("later")
    build_identity = _identity("build")
    smoke_identity = _identity("smoke")
    build = {"build": "receipt"}
    confirmation_sha = "d" * 64
    smoke = {
        "smoke_sha256": "e" * 64,
        "confirmation_sha256": confirmation_sha,
    }
    terminal = {
        "terminal_uri": terminal_identity["uri"],
        "terminal_sha256": "a" * 64,
        "bridge_terminal_identity": bridge_identity,
        "bridge_terminal_sha256": "b" * 64,
        "task0_smoke_receipt_identity": smoke_identity,
        "task0_smoke_receipt_sha256": smoke["smoke_sha256"],
        "terminal_build_receipt_identity": build_identity,
        "terminal_build_receipt_sha256": operator._hash(build),
        "source_commit_sha": "1" * 40,
        "immutable_image_digest": f"sha256:{'2' * 64}",
        "later_source_identity": later_identity,
        "output_prefix": "gs://fixture/run/selector-confirmation-v1/",
        "slate_results": [
            {"slate_id": f"fixture-{ordinal:02d}"} for ordinal in range(54)
        ],
    }
    bridge_terminal = {"terminal_sha256": "b" * 64}
    monkeypatch.setattr(
        operator,
        "_read_json",
        lambda *_args, **_kwargs: (terminal, terminal_identity),
    )
    monkeypatch.setattr(
        operator.execution,
        "validate_terminal_envelope_v1",
        lambda value: events.append("terminal") or value,
    )
    monkeypatch.setattr(
        operator,
        "_read_bridge_terminal",
        lambda *_args, **_kwargs: events.append("bridge")
        or (bridge_terminal, bridge_identity),
    )
    monkeypatch.setattr(
        operator,
        "_replay_all_confirmation_results_v1",
        lambda **_kwargs: events.append("exact-replay")
        or [{"confirmation_sha256": confirmation_sha}],
    )
    monkeypatch.setattr(
        operator,
        "_read_build_authority_v1",
        lambda *_args, **_kwargs: events.append("build")
        or (build, build_identity),
    )
    monkeypatch.setattr(
        operator,
        "_read_task0_smoke_receipt_v1",
        lambda *_args, **_kwargs: events.append("smoke")
        or (smoke, smoke_identity),
    )
    monkeypatch.setattr(
        operator,
        "_validate_smoke_authority_v1",
        lambda **_kwargs: events.append("smoke-bind"),
    )
    monkeypatch.setattr(
        operator.execution,
        "normalized_confirmation_terminal_v1",
        lambda *_args, **_kwargs: events.append("validate-normalize") or tuple(),
    )
    snapshot = {
        "later_source_freeze_identity": later_identity,
        "outcome_snapshot_sha256": "c" * 64,
    }
    slate_keys = {
        ordinal: (2023, ordinal + 1, f"fixture-{ordinal:02d}")
        for ordinal in range(54)
    }
    monkeypatch.setattr(
        operator.grader,
        "open_outcome_snapshot_surface_v1",
        lambda **_kwargs: events.append("outcome")
        or (snapshot, outcome_identity, {}, slate_keys),
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
            raise AssertionError("patched outcome opener owns the read")

    result = operator.grade_from_request_v1(
        {
            "terminal_identity": terminal_identity,
            "outcome_snapshot_identity": outcome_identity,
        },
        store=Store(),
    )
    assert result["complete"] is True
    assert events == [
        "terminal",
        "bridge",
        "build",
        "smoke",
        "smoke-bind",
        "exact-replay",
        "validate-normalize",
        "outcome",
        "score",
        "publish",
    ]


def test_task0_smoke_publishes_and_binds_exact_build_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge_identity = _identity("bridge-terminal")
    build_identity = _identity("build")
    bridge_terminal = {
        "terminal_sha256": "a" * 64,
        "later_source_identity": _identity("later"),
        "output_prefix": "gs://fixture/run/selector-bridge/",
        "slate_results": [{"slate_id": "2023-w01"}],
    }
    output_prefix = "gs://fixture/run/selector-bridge/selector-confirmation-v1/"
    build = {"build": "receipt"}
    monkeypatch.setattr(
        operator,
        "_read_bridge_terminal",
        lambda *_args, **_kwargs: (bridge_terminal, bridge_identity),
    )
    monkeypatch.setattr(
        operator.execution,
        "confirmation_output_prefix_v1",
        lambda _value: output_prefix,
    )
    monkeypatch.setattr(
        operator,
        "_read_build_authority_v1",
        lambda *_args, **_kwargs: (build, build_identity),
    )
    monkeypatch.setattr(
        operator,
        "_derive_one_confirmation_v1",
        lambda **_kwargs: {
            "slate_id": "2023-w01",
            "confirmation_sha256": "b" * 64,
            "book_count": 42,
        },
    )
    published: dict[str, object] = {}

    def publish(**kwargs: object) -> dict[str, object]:
        published.update(kwargs)
        return _identity("smoke")

    monkeypatch.setattr(operator, "_publish_json", publish)
    result = operator.smoke_from_request_v1(
        {
            "bridge_terminal_identity": bridge_identity,
            "terminal_build_receipt_identity": build_identity,
            "source_commit_sha": "1" * 40,
            "immutable_image_digest": f"sha256:{'2' * 64}",
            "output_prefix": output_prefix,
            "source_ordinal": 0,
        },
        store=object(),
    )
    receipt = published["value"]
    assert published["uri"] == f"{output_prefix}task0-smoke/smoke-receipt.json"
    assert receipt["terminal_build_receipt_identity"] == build_identity
    assert receipt["terminal_build_receipt_sha256"] == operator._hash(build)
    assert operator._validate_task0_smoke_receipt_v1(receipt) == receipt
    assert result["complete"] is True
    with pytest.raises(
        operator.RunCorpusR6Hard230SelectorConfirmationV1Error,
        match="source ordinal differs",
    ):
        operator.smoke_from_request_v1(
            {
                "bridge_terminal_identity": bridge_identity,
                "terminal_build_receipt_identity": build_identity,
                "source_commit_sha": "1" * 40,
                "immutable_image_digest": f"sha256:{'2' * 64}",
                "output_prefix": output_prefix,
                "source_ordinal": False,
            },
            store=object(),
        )


def test_derive_is_exactly_54_and_has_no_outcome_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge_identity = _identity("bridge-terminal")
    source_terminal = {
        "terminal_sha256": "a" * 64,
        "later_source_identity": _identity("later"),
        "slate_results": [{"source_ordinal": ordinal} for ordinal in range(54)],
    }
    monkeypatch.setattr(
        operator,
        "_read_bridge_terminal",
        lambda *_args, **_kwargs: (source_terminal, bridge_identity),
    )
    monkeypatch.setattr(
        operator.execution,
        "confirmation_output_prefix_v1",
        lambda _value: "gs://fixture/run/selector-confirmation-v1/",
    )
    seen: list[int] = []
    monkeypatch.setattr(
        operator,
        "_derive_one_confirmation_v1",
        lambda **kwargs: seen.append(int(kwargs["bridge_slate"]["source_ordinal"]))
        or {
            "source_ordinal": kwargs["bridge_slate"]["source_ordinal"],
            "confirmation_sha256": "c" * 64,
        },
    )
    build_identity = _identity("build")
    smoke_identity = _identity("smoke")
    monkeypatch.setattr(
        operator,
        "_read_build_authority_v1",
        lambda *_args, **_kwargs: ({"build": "receipt"}, build_identity),
    )
    monkeypatch.setattr(
        operator,
        "_read_task0_smoke_receipt_v1",
        lambda *_args, **_kwargs: (
            {"confirmation_sha256": "c" * 64, "smoke_sha256": "d" * 64},
            smoke_identity,
        ),
    )
    monkeypatch.setattr(
        operator,
        "_validate_smoke_authority_v1",
        lambda **_kwargs: None,
    )
    terminal = {
        "terminal_uri": "gs://fixture/run/selector-confirmation-v1/full-54/terminal.json",
        "terminal_sha256": "b" * 64,
    }
    monkeypatch.setattr(
        operator.execution,
        "build_confirmation_terminal_v1",
        lambda **_kwargs: terminal,
    )
    monkeypatch.setattr(
        operator,
        "_publish_json",
        lambda **_kwargs: _identity("confirmation-terminal"),
    )
    result = operator.derive_from_request_v1(
        {
            "bridge_terminal_identity": bridge_identity,
            "task0_smoke_receipt_identity": smoke_identity,
            "terminal_build_receipt_identity": build_identity,
            "source_commit_sha": "1" * 40,
            "immutable_image_digest": f"sha256:{'2' * 64}",
            "output_prefix": "gs://fixture/run/selector-confirmation-v1/",
        },
        store=object(),
    )
    assert result["complete"] is True
    assert seen == list(range(54))


def test_grade_replay_rejects_rehashed_in_population_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_slates = [{"source_ordinal": ordinal} for ordinal in range(54)]
    expected = [
        {"source_ordinal": ordinal, "selected_lineup_ids": ["expected"]}
        for ordinal in range(54)
    ]
    persisted = deepcopy(expected)
    persisted[0]["selected_lineup_ids"] = ["other-sampled-lineup"]
    monkeypatch.setattr(
        operator,
        "_derive_one_confirmation_v1",
        lambda **kwargs: expected[int(kwargs["bridge_slate"]["source_ordinal"])],
    )
    with pytest.raises(
        operator.RunCorpusR6Hard230SelectorConfirmationV1Error,
        match=r"result\[0\] differs from exact replay",
    ):
        operator._replay_all_confirmation_results_v1(
            terminal={"slate_results": persisted},
            bridge_terminal={
                "slate_results": source_slates,
                "later_source_identity": _identity("later"),
            },
            store=object(),
        )


def test_cloud_safe_base64_request_is_strict_canonical_json() -> None:
    request = {
        "bridge_terminal_identity": _identity("bridge-terminal"),
        "source_ordinal": 0,
    }
    raw = operator._canonical(request)
    encoded = base64.b64encode(raw).decode("ascii")
    assert operator._load_request_base64(encoded) == request
    with pytest.raises(
        operator.RunCorpusR6Hard230SelectorConfirmationV1Error,
        match="not canonical JSON",
    ):
        operator._load_request_base64(
            base64.b64encode(raw + b"\n").decode("ascii")
        )
