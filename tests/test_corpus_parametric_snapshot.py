from __future__ import annotations

from hashlib import sha256
from itertools import combinations, product
import json

import numpy as np
import pytest

from nfl_dfs.research import corpus_legal_feasibility as core
from nfl_dfs.research import corpus_parametric_snapshot as snapshot
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_parametric_batch import (
    PARAMETER_ORDER,
    PARAMETER_SET_ORDER,
)
from nfl_dfs.research.effective_policy_rule_inventory import (
    generate_effective_policy_rule_inventory,
)
from nfl_dfs.research.lr8_later_period_source import PreparedLaterSlate
from pathlib import Path

import scripts.compare_corpus_task_science as compare_cli


ROOT = Path(__file__).resolve().parents[1]


def _players(*, salary: int = 5_500) -> tuple[rw.PlayerSpec, ...]:
    rows = (
        ("q-a", "QB", "A", "B", "g1"), ("q-c", "QB", "C", "D", "g2"),
        ("rb-a1", "RB", "A", "B", "g1"), ("rb-a2", "RB", "A", "B", "g1"),
        ("rb-b", "RB", "B", "A", "g1"), ("rb-c", "RB", "C", "D", "g2"),
        ("rb-d", "RB", "D", "C", "g2"), ("rb-e", "RB", "E", "F", "g3"),
        ("wr-a1", "WR", "A", "B", "g1"), ("wr-a2", "WR", "A", "B", "g1"),
        ("wr-b", "WR", "B", "A", "g1"), ("wr-c1", "WR", "C", "D", "g2"),
        ("wr-c2", "WR", "C", "D", "g2"), ("wr-d", "WR", "D", "C", "g2"),
        ("wr-e", "WR", "E", "F", "g3"), ("wr-f", "WR", "F", "E", "g3"),
        ("te-a", "TE", "A", "B", "g1"), ("te-b", "TE", "B", "A", "g1"),
        ("te-c", "TE", "C", "D", "g2"), ("te-d", "TE", "D", "C", "g2"),
        ("te-e", "TE", "E", "F", "g3"), ("dst-b", "DST", "B", "A", "g1"),
        ("dst-c", "DST", "C", "D", "g2"), ("dst-e", "DST", "E", "F", "g3"),
    )
    return tuple(sorted((
        rw.PlayerSpec(player_id, position, team, opponent, game_id, salary)
        for player_id, position, team, opponent, game_id in rows
    ), key=lambda player: player.player_id))


def _legal_rosters(
    players: tuple[rw.PlayerSpec, ...], *, count: int
) -> tuple[tuple[str, ...], ...]:
    by_position = {
        position: [
            player.player_id for player in players
            if player.position == position
        ]
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    result: list[tuple[str, ...]] = []
    for qb, rbs, wrs, te, dst in product(
        by_position["QB"],
        combinations(by_position["RB"], 2),
        combinations(by_position["WR"], 4),
        by_position["TE"],
        by_position["DST"],
    ):
        roster = tuple(sorted((qb, *rbs, *wrs, te, dst)))
        try:
            core.audit_dk_classic(players, roster)
            if core.house_rule_violations(players, roster):
                continue
        except core.CorpusLegalFeasibilityError:
            continue
        result.append(roster)
        if len(result) == count:
            return tuple(result)
    raise AssertionError("fixture roster universe is too small")


@pytest.fixture(scope="module")
def fixture_payloads() -> dict[str, object]:
    players = _players()
    rosters = _legal_rosters(players, count=40)
    world_ids = tuple(
        rw.WorldId(block, index)
        for block in rw.WORLD_BLOCKS
        for index in range(rw.WORLDS_PER_BLOCK)
    )
    row = np.arange(len(players), dtype=np.float32)[:, None]
    column = (
        np.arange(core.EXPECTED_WORLD_COUNT, dtype=np.float32)[None, :] % 13
    ) / np.float32(50.0)
    draws = np.ascontiguousarray(np.float32(7.0) + row / 9 + column)
    draws.flags.writeable = False
    prepared = PreparedLaterSlate(
        season=2023,
        week=1,
        slate_id="2023-w01",
        players=players,
        world_ids=world_ids,
        player_draws=draws,
        incumbent_candidates=rosters[:30],
        source_freeze_sha256="a" * 64,
        artifact_sha256_by_block={
            block: f"{index + 1:064x}"
            for index, block in enumerate(rw.WORLD_BLOCKS)
        },
    )
    inventory = generate_effective_policy_rule_inventory(ROOT)
    call_counter = {"count": 0}

    def varied_solver(request: core.SolveRequest) -> core.SolveOutcome:
        roster = rosters[call_counter["count"] % len(rosters)]
        call_counter["count"] += 1
        return core._make_mock_optimal_outcome(request, roster)

    matrix = core._execute_generation_matrix_for_test(
        prepared,
        inventory,
        solver=varied_solver,
        semantic_environment={},
        visits_per_block=2,
    )
    payload_rows: list[tuple[bytes, dict[str, object]]] = []
    for variant in matrix.variants:
        unique, first_indices = core.first_occurrence_unique(
            variant.visit_rosters
        )
        selected = unique[: min(3, len(unique))]
        selector = core.SelectorReceipt(
            candidate_count=len(unique),
            world_count=core.EXPECTED_WORLD_COUNT,
            entry_count=len(selected),
            tail_line_dk=core.TAIL_LINE_DK,
            selected_indices=tuple(range(len(selected))),
            tie_law_applied="fixture-only",
        )
        census = core.ViolationCensus(
            unique_candidate_counts=tuple(
                (name, 0) for name in PARAMETER_ORDER
            ),
            visit_counts=tuple((name, 0) for name in PARAMETER_ORDER),
            selected_counts=tuple((name, 0) for name in PARAMETER_ORDER),
        )
        raw, _ = core._build_variant_result_payload(
            matrix=matrix,
            variant=variant,
            unique=unique,
            first_indices=first_indices,
            candidate_score_sha256="1" * 64,
            selector=selector,
            selected_rosters=selected,
            selected_score_sha256="2" * 64,
            census=census,
        )
        uri = (
            "gs://fixture/task/"
            f"{variant.profile.parameter_set_id}/result.json"
        )
        identity = {
            "uri": uri,
            "generation": "1",
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        payload_rows.append((raw, identity))
    carrier_body: dict[str, object] = {
        "schema_version": "fixture-carrier/v1",
        "variant_result_objects": [
            {
                "ordinal": ordinal,
                "parameter_set_id": PARAMETER_SET_ORDER[ordinal],
                "object_identity": identity,
            }
            for ordinal, (_, identity) in enumerate(payload_rows)
        ],
    }
    carrier_body["task_result_sha256"] = core.canonical_sha256(carrier_body)
    carrier_raw = core.canonical_json_bytes(carrier_body)
    store = {
        identity["uri"]: raw for raw, identity in payload_rows
    }
    return {
        "payload_rows": payload_rows,
        "carrier_raw": carrier_raw,
        "carrier_identity": {
            "uri": "gs://fixture/task/task-result.json",
            "generation": "1",
            "sha256": sha256(carrier_raw).hexdigest(),
            "bytes": len(carrier_raw),
        },
        "store": store,
    }


def _read_exact_from(store: dict[str, bytes]):
    def read_exact(identity: dict[str, object]) -> bytes:
        return store[str(identity["uri"])]

    return read_exact


def _mutated_payload(
    raw: bytes, mutate,
) -> tuple[bytes, dict[str, object]]:
    body = json.loads(raw.decode("utf-8"))
    body.pop("result_sha256")
    mutate(body)
    body["result_sha256"] = core.canonical_sha256(body)
    new_raw = core.canonical_json_bytes(body)
    return new_raw, {
        "uri": "gs://fixture/mutated/result.json",
        "generation": "1",
        "sha256": sha256(new_raw).hexdigest(),
        "bytes": len(new_raw),
    }


def test_reader_validates_real_engine_payloads_and_projects_science(
    fixture_payloads,
) -> None:
    carrier, variants = snapshot.read_task_variant_results(
        fixture_payloads["carrier_raw"],
        carrier_identity=fixture_payloads["carrier_identity"],
        read_exact=_read_exact_from(fixture_payloads["store"]),
        require_authoritative=False,
    )
    assert len(variants) == 7
    assert [row["profile"]["ordinal"] for row in variants] == list(range(7))
    projection = snapshot.extract_task_science(variants)
    assert projection["schema"] == snapshot.SCIENCE_PROJECTION_SCHEMA
    assert projection["arm_count"] == 7
    assert projection["slate"] == {
        "season": 2023, "week": 1, "slate_id": "2023-w01",
    }
    for arm in projection["arms"]:
        assert set(arm) == set(snapshot.SCIENCE_ARM_FIELDS)
        assert arm["visit_rosters"]
    remainder = {
        key: value for key, value in projection.items()
        if key != "science_projection_sha256"
    }
    assert core.canonical_sha256(remainder) == (
        projection["science_projection_sha256"]
    )


def test_compare_ignores_image_bindings_and_catches_science_drift(
    fixture_payloads,
) -> None:
    read_exact = _read_exact_from(fixture_payloads["store"])
    _, baseline_variants = snapshot.read_task_variant_results(
        fixture_payloads["carrier_raw"],
        carrier_identity=fixture_payloads["carrier_identity"],
        read_exact=read_exact,
        require_authoritative=False,
    )
    baseline = snapshot.extract_task_science(baseline_variants)

    def rebuild_challenger(arm_ordinal: int, mutate):
        rows = list(fixture_payloads["payload_rows"])
        raw, _ = rows[arm_ordinal]
        rows[arm_ordinal] = _mutated_payload(raw, mutate)
        variants = [
            snapshot.validate_variant_result_bytes(
                row_raw, identity=identity, require_authoritative=False
            )
            for row_raw, identity in rows
        ]
        return snapshot.extract_task_science(variants)

    image_shift = rebuild_challenger(
        2, lambda body: body.update(attempt_ledger_sha256="f" * 64)
    )
    receipt = snapshot.compare_task_science(
        baseline, image_shift,
        baseline_label="v4", challenger_label="v5",
    )
    assert receipt["equivalent"] is True
    assert receipt["comparison"] == "science-only"
    assert receipt["differing_fields"] == []
    assert "attempt_ledger_sha256" in receipt[
        "excluded_image_variant_fields"
    ]

    def flip_roster(body: dict[str, object]) -> None:
        rosters = body["visit_rosters"]
        rosters[0] = list(reversed(rosters[0]))

    science_shift = rebuild_challenger(3, flip_roster)
    failed = snapshot.compare_task_science(
        baseline, science_shift,
        baseline_label="v4", challenger_label="v5",
    )
    assert failed["equivalent"] is False
    assert {
        (row["arm_ordinal"], row["field"])
        for row in failed["differing_fields"]
    } == {(3, "visit_rosters")}


def test_reader_rejects_tampering_and_authority_gaps(
    fixture_payloads,
) -> None:
    raw, identity = fixture_payloads["payload_rows"][0]
    tampered = raw.replace(b"2023-w01", b"2023-w02", 1)
    with pytest.raises(
        snapshot.CorpusParametricSnapshotError, match="identity differs"
    ):
        snapshot.validate_variant_result_bytes(
            tampered, identity=identity, require_authoritative=False
        )
    with pytest.raises(
        snapshot.CorpusParametricSnapshotError, match="self-hash differs"
    ):
        snapshot.validate_variant_result_bytes(
            tampered, require_authoritative=False
        )
    flagged, flagged_identity = _mutated_payload(
        raw, lambda body: body.update(uses_realized_outcomes=True)
    )
    with pytest.raises(
        snapshot.CorpusParametricSnapshotError, match="guards differ"
    ):
        snapshot.validate_variant_result_bytes(
            flagged, identity=flagged_identity, require_authoritative=False
        )
    with pytest.raises(
        snapshot.CorpusParametricSnapshotError,
        match="lacks a source binding",
    ):
        snapshot.validate_variant_result_bytes(
            raw, identity=identity, require_authoritative=True
        )
    carrier = json.loads(fixture_payloads["carrier_raw"].decode("utf-8"))
    carrier.pop("task_result_sha256")
    rows = carrier["variant_result_objects"]
    rows[0], rows[1] = rows[1], rows[0]
    carrier["task_result_sha256"] = core.canonical_sha256(carrier)
    swapped_raw = core.canonical_json_bytes(carrier)
    with pytest.raises(
        snapshot.CorpusParametricSnapshotError, match="ordering differs"
    ):
        snapshot.read_task_variant_results(
            swapped_raw,
            carrier_identity=None,
            read_exact=_read_exact_from(fixture_payloads["store"]),
            require_authoritative=False,
        )


def test_cli_refuses_existing_outputs_before_any_cloud_contact(
    tmp_path,
) -> None:
    existing = tmp_path / "receipt.json"
    existing.write_bytes(b"{}")
    argv = [
        "--baseline-carrier-uri", "gs://x/a.json",
        "--baseline-carrier-generation", "1",
        "--baseline-carrier-sha256", "a" * 64,
        "--baseline-carrier-bytes", "10",
        "--challenger-carrier-uri", "gs://x/b.json",
        "--challenger-carrier-generation", "1",
        "--challenger-carrier-sha256", "b" * 64,
        "--challenger-carrier-bytes", "10",
        "--baseline-label", "v4",
        "--challenger-label", "v5",
        "--receipt-output", str(existing),
        "--pass-gate-output", str(tmp_path / "gate.json"),
    ]
    assert compare_cli.main(argv) == 2
