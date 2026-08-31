from __future__ import annotations

from copy import deepcopy

import pytest

from nfl_dfs.inference.generation_exposure import canonical_sha256
from nfl_dfs.inference import prospective_generation_shadow_evaluation as shadow
from nfl_dfs.inference import week1_operating_roster_materializer as materializer
from nfl_dfs.inference.week1_operating_book import (
    ALL_BOOM_SOURCE_ID,
    BASE_SOURCE_ORDER,
    BX60_SOURCE_ID,
    CORE_SOURCE_ID,
)
from nfl_dfs.inference.week1_operating_book_suite_adapter import (
    BASE_RETRIEVAL_ID,
)


CAP4_RETRIEVAL_ID = "cap4-production-ladder-prefix-then-fill-k80"


class _Draws:
    def __init__(self, rows: int) -> None:
        self.shape = (rows, 50_000)


def _roster(label: str, ordinal: int) -> list[str]:
    return sorted(
        f"{label}-r{ordinal:03d}-p{player:02d}" for player in range(9)
    )


def _lineup_id(roster: list[str]) -> str:
    return f"lineup-v1-{canonical_sha256(roster)}"


def _roster_books() -> dict[str, list[list[str]]]:
    return {
        arm: [_roster(arm, ordinal) for ordinal in range(80)]
        for arm in shadow.ARM_ORDER
    }


def _refresh_membership_ids(authority: dict[str, object]) -> None:
    rosters = authority["manifest"]["prelock_receipt"]["memberships"]["80"]
    authority["membership_lineup_ids_by_arm"] = {
        arm: [_lineup_id(roster) for roster in rosters[arm]]
        for arm in shadow.ARM_ORDER
    }
    authority["retrieval_lineup_ids_by_population"][CORE_SOURCE_ID][
        BASE_RETRIEVAL_ID
    ] = list(authority["membership_lineup_ids_by_arm"][CORE_SOURCE_ID])


def _authority() -> dict[str, object]:
    roster_books = _roster_books()
    bridge_player_ids = sorted({
        player_id
        for rosters in roster_books.values()
        for roster in rosters
        for player_id in roster
    })
    positions = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST")
    player_identity_bridge = []
    for ordinal, player_id in enumerate(bridge_player_ids):
        position = positions[int(player_id.rsplit("p", 1)[1])]
        team = f"T{ordinal % 32:02d}"
        player_identity_bridge.append({
            "internal_player_id": f"internal-{ordinal:04d}",
            "dk_draftable_id": player_id,
            "gsis_id": None if position == "DST" else f"gsis-{ordinal:04d}",
            "position": position,
            "team": team,
            "dst_team": team if position == "DST" else None,
            "salary": 5_000,
        })
    memberships = {
        arm: [_lineup_id(roster) for roster in roster_books[arm]]
        for arm in shadow.ARM_ORDER
    }
    world_identities = {
        arm: {
            "uri": f"gs://test/{arm}.npz",
            "generation": str(index + 1),
            "sha256": canonical_sha256({"arm": arm}),
            "bytes": 1000 + index,
        }
        for index, arm in enumerate(shadow.ARM_ORDER)
    }
    arm_receipts = {
        arm: {
            "candidate_count": 80,
            "candidate_order_sha256": canonical_sha256(roster_books[arm]),
        }
        for arm in shadow.ARM_ORDER
    }
    context = {
        "season": 2026,
        "week": 1,
        "draft_group_id": "151307",
        "run_id": "week1-test",
        "code_sha": "a" * 40,
        "slate_lock_at": "2026-09-13T17:00:00+00:00",
    }
    return {
        "schema_version": shadow.SUITE_AUTHORITY_SCHEMA,
        "suite_authority_sha256": "a" * 64,
        "complete": True,
        "slate_lock_at": context["slate_lock_at"],
        "manifest": {
            **context,
            "uses_realized_outcomes": False,
            "post_lock_data_read": False,
            "prelock_receipt": {
                "memberships": {"80": roster_books},
                "arm_receipts": arm_receipts,
            },
        },
        "terminal": {
            "uses_realized_outcomes": False,
            "post_lock_data_read": False,
        },
        "world_artifact_identities": world_identities,
        "player_identity_bridge": player_identity_bridge,
        "membership_lineup_ids_by_arm": memberships,
        "retrieval_lineup_ids_by_population": {
            CORE_SOURCE_ID: {
                BASE_RETRIEVAL_ID: memberships[CORE_SOURCE_ID],
                CAP4_RETRIEVAL_ID: [
                    _lineup_id(_roster("cap4", ordinal))
                    for ordinal in range(80)
                ],
            },
        },
    }


def _decoded_artifacts(
    authority: dict[str, object],
) -> dict[str, dict[str, object]]:
    manifest = authority["manifest"]
    context = {
        field: manifest[field]
        for field in (
            "season",
            "week",
            "draft_group_id",
            "run_id",
            "code_sha",
            "slate_lock_at",
        )
    }
    decoded: dict[str, dict[str, object]] = {}
    for source_id in BASE_SOURCE_ORDER:
        rosters = manifest["prelock_receipt"]["memberships"]["80"][source_id]
        player_ids = sorted({player for roster in rosters for player in roster})
        decoded[source_id] = {
            "metadata": {
                "artifact_version": "prospective-recourse-worlds-v1",
                "uses_post_decision_outcomes": False,
                "context": {**context, "arm": source_id},
                "candidate_batch_metadata": {
                    "uses_realized_outcomes": False,
                    "post_lock_data_read": False,
                },
            },
            "generated_at": "2026-08-30T12:00:00+00:00",
            "player_ids": player_ids,
            "player_draws": _Draws(len(player_ids)),
            "candidate_rosters": deepcopy(rosters),
            "sha256": authority["world_artifact_identities"][source_id][
                "sha256"
            ],
        }
    return decoded


def _terminal_envelope(
    authority: dict[str, object],
) -> dict[str, object]:
    arms = []
    for source_id in shadow.ARM_ORDER:
        arms.append({
            "arm_id": source_id,
            "arm_freeze_sha256": canonical_sha256({"freeze": source_id}),
            "book_lineup_ids": authority["membership_lineup_ids_by_arm"][
                source_id
            ],
            "uses_realized_outcomes": False,
            "uses_post_lock_data": False,
            "artifacts": {
                "world": {
                    "identity": deepcopy(
                        authority["world_artifact_identities"][source_id]
                    )
                }
            },
        })
    root = {
        "season": 2026,
        "week": 1,
        "lock_at": authority["slate_lock_at"],
        "suite_authority": authority,
        "suite_authority_sha256": authority["suite_authority_sha256"],
        "terminal_prelock_root_sha256": "b" * 64,
        "arms": arms,
    }
    return {
        "identity": {
            "uri": "gs://test/terminal-root.json",
            "generation": "1",
            "sha256": "c" * 64,
            "bytes": 1234,
        },
        "terminal_prelock_root": root,
        "terminal_prelock_envelope_sha256": "d" * 64,
    }


def _patch_validators(
    monkeypatch: pytest.MonkeyPatch,
    *,
    root_calls: list[object] | None = None,
) -> None:
    monkeypatch.setattr(shadow, "validate_suite_authority_v1", lambda value: value)

    def _validate_root(value: object) -> dict[str, object]:
        if root_calls is not None:
            root_calls.append(value)
        return value["terminal_prelock_root"]

    monkeypatch.setattr(shadow, "validate_terminal_prelock_root_v1", _validate_root)


@pytest.mark.parametrize(
    ("k", "expected_counts"),
    (
        (80, {CORE_SOURCE_ID: 64, ALL_BOOM_SOURCE_ID: 12, BX60_SOURCE_ID: 4}),
        (100, {CORE_SOURCE_ID: 80, ALL_BOOM_SOURCE_ID: 15, BX60_SOURCE_ID: 5}),
    ),
)
def test_terminal_materializer_emits_exact_canonical_rosters(
    monkeypatch: pytest.MonkeyPatch,
    k: int,
    expected_counts: dict[str, int],
) -> None:
    authority = _authority()
    terminal = _terminal_envelope(authority)
    calls: list[object] = []
    _patch_validators(monkeypatch, root_calls=calls)

    result = materializer.build_week1_operating_roster_materialization_v1(
        k=k, terminal_prelock_root=terminal
    )

    assert calls == [terminal]
    assert result["authority_mode"] == materializer.TERMINAL_AUTHORITY_MODE
    assert result["terminal_root_binding"] == {
        "terminal_prelock_root_sha256": "b" * 64,
        "terminal_prelock_envelope_sha256": "d" * 64,
        "terminal_prelock_object_identity": terminal["identity"],
    }
    assert len(result["selected_lineups"]) == k
    assert [
        book["source_id"] for book in result["source_membership_books"]
    ] == list(BASE_SOURCE_ORDER)
    for book in result["source_membership_books"]:
        assert len(book["lineup_ids"]) == 80
        assert len(book["rosters"]) == 80
        assert book["lineup_ids"] == [
            _lineup_id(roster) for roster in book["rosters"]
        ]
    counts = {
        source_id: sum(
            row["source_id"] == source_id for row in result["selected_lineups"]
        )
        for source_id in BASE_SOURCE_ORDER
    }
    assert counts == expected_counts
    assert len({row["lineup_id"] for row in result["selected_lineups"]}) == k
    assert len({tuple(row["player_ids"]) for row in result["selected_lineups"]}) == k
    for row in result["selected_lineups"]:
        assert len(row["player_ids"]) == 9
        assert row["player_ids"] == sorted(row["player_ids"])
        assert row["lineup_id"] == f"lineup-v1-{canonical_sha256(row['player_ids'])}"
        assert row["roster_sha256"] == canonical_sha256(row["player_ids"])
    assert result["cap4_used"] is False
    assert result["tier3_used"] is False
    assert result["uses_realized_outcomes"] is False
    assert result["outcome_fields"] == []
    assert (
        materializer.validate_week1_operating_roster_materialization_v1(result)
        == result
    )


def test_suite_decoded_materializer_binds_all_three_arm_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    decoded = _decoded_artifacts(authority)
    _patch_validators(monkeypatch)

    result = materializer.build_week1_operating_roster_materialization_v1(
        k=100,
        suite_authority=authority,
        decoded_arm_artifacts=decoded,
    )

    assert result["authority_mode"] == materializer.DECODED_AUTHORITY_MODE
    assert result["terminal_root_binding"] is None
    assert len(result["selected_lineups"]) == 100
    for binding in result["source_arm_bindings"]:
        source_id = binding["source_id"]
        assert binding["arm_freeze_sha256"] is None
        assert binding["decoded_artifact_sha256"] == decoded[source_id]["sha256"]
        assert binding["world_artifact_sha256"] == decoded[source_id]["sha256"]
        assert binding["candidate_rosters_sha256"] == canonical_sha256(
            decoded[source_id]["candidate_rosters"]
        )
    assert (
        materializer.validate_week1_operating_roster_materialization_v1(result)
        == result
    )


def test_terminal_and_decoded_modes_resolve_the_same_operating_book(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    _patch_validators(monkeypatch)
    terminal_result = materializer.build_week1_operating_roster_materialization_v1(
        k=80, terminal_prelock_root=_terminal_envelope(authority)
    )
    decoded_result = materializer.build_week1_operating_roster_materialization_v1(
        k=80,
        suite_authority=authority,
        decoded_arm_artifacts=_decoded_artifacts(authority),
    )

    assert terminal_result["selected_lineups"] == decoded_result["selected_lineups"]
    assert terminal_result["selected_lineup_ids_sha256"] == decoded_result[
        "selected_lineup_ids_sha256"
    ]
    assert terminal_result["selected_rosters_sha256"] == decoded_result[
        "selected_rosters_sha256"
    ]


def test_materializer_ignores_cap4_membership_and_globally_deduplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    rosters = authority["manifest"]["prelock_receipt"]["memberships"]["80"]
    rosters[ALL_BOOM_SOURCE_ID][:5] = deepcopy(rosters[CORE_SOURCE_ID][:5])
    rosters[BX60_SOURCE_ID][:3] = deepcopy(rosters[CORE_SOURCE_ID][5:8])
    _refresh_membership_ids(authority)
    terminal = _terminal_envelope(authority)
    _patch_validators(monkeypatch)

    result = materializer.build_week1_operating_roster_materialization_v1(
        k=80, terminal_prelock_root=terminal
    )

    selected_ids = {row["lineup_id"] for row in result["selected_lineups"]}
    cap4_ids = set(
        authority["retrieval_lineup_ids_by_population"][CORE_SOURCE_ID][
            CAP4_RETRIEVAL_ID
        ]
    )
    assert len(selected_ids) == 80
    assert not selected_ids & cap4_ids


@pytest.mark.parametrize(
    "mutation",
    ("artifact-sha", "candidate-order", "outcome-carrier", "missing-arm"),
)
def test_decoded_mode_rejects_unbound_or_outcome_bearing_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    authority = _authority()
    decoded = _decoded_artifacts(authority)
    _patch_validators(monkeypatch)
    if mutation == "artifact-sha":
        decoded[CORE_SOURCE_ID]["sha256"] = "f" * 64
    elif mutation == "candidate-order":
        decoded[ALL_BOOM_SOURCE_ID]["candidate_rosters"] = list(
            reversed(decoded[ALL_BOOM_SOURCE_ID]["candidate_rosters"])
        )
    elif mutation == "outcome-carrier":
        decoded[BX60_SOURCE_ID]["metadata"]["actual_score"] = 220.0
    else:
        decoded.pop(BX60_SOURCE_ID)

    with pytest.raises(materializer.Week1OperatingRosterMaterializerError):
        materializer.build_week1_operating_roster_materialization_v1(
            k=80,
            suite_authority=authority,
            decoded_arm_artifacts=decoded,
        )


def test_decoded_mode_rejects_noncanonical_selected_roster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    decoded = _decoded_artifacts(authority)
    _patch_validators(monkeypatch)
    decoded[CORE_SOURCE_ID]["candidate_rosters"][0] = list(
        reversed(decoded[CORE_SOURCE_ID]["candidate_rosters"][0])
    )

    with pytest.raises(
        materializer.Week1OperatingRosterMaterializerError,
        match="nine unique, sorted",
    ):
        materializer.build_week1_operating_roster_materialization_v1(
            k=80,
            suite_authority=authority,
            decoded_arm_artifacts=decoded,
        )


def test_terminal_mode_rejects_arm_world_binding_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    terminal = _terminal_envelope(authority)
    _patch_validators(monkeypatch)
    source_arm = next(
        arm
        for arm in terminal["terminal_prelock_root"]["arms"]
        if arm["arm_id"] == CORE_SOURCE_ID
    )
    source_arm["artifacts"]["world"]["identity"]["sha256"] = "f" * 64

    with pytest.raises(
        materializer.Week1OperatingRosterMaterializerError,
        match="terminal arm binding differs",
    ):
        materializer.build_week1_operating_roster_materialization_v1(
            k=80, terminal_prelock_root=terminal
        )


@pytest.mark.parametrize("mode", ("neither", "both", "partial-decoded"))
def test_materializer_requires_exactly_one_complete_authority_mode(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    authority = _authority()
    terminal = _terminal_envelope(authority)
    decoded = _decoded_artifacts(authority)
    _patch_validators(monkeypatch)
    kwargs: dict[str, object] = {"k": 80}
    if mode == "both":
        kwargs.update({
            "terminal_prelock_root": terminal,
            "suite_authority": authority,
            "decoded_arm_artifacts": decoded,
        })
    elif mode == "partial-decoded":
        kwargs["suite_authority"] = authority

    with pytest.raises(
        materializer.Week1OperatingRosterMaterializerError,
        match="exactly one|requires both",
    ):
        materializer.build_week1_operating_roster_materialization_v1(**kwargs)


def test_materialization_reopen_rejects_rehashed_roster_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    _patch_validators(monkeypatch)
    result = materializer.build_week1_operating_roster_materialization_v1(
        k=80, terminal_prelock_root=_terminal_envelope(authority)
    )
    forged = deepcopy(result)
    forged["selected_lineups"][0]["player_ids"][0] = "forged-player"
    forged.pop("materialization_sha256")
    forged["materialization_sha256"] = canonical_sha256(forged)

    with pytest.raises(
        materializer.Week1OperatingRosterMaterializerError,
        match="nine unique, sorted|identity or adapter binding|hashes differ",
    ):
        materializer.validate_week1_operating_roster_materialization_v1(forged)


def test_reopen_recomputes_every_unentered_membership_roster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    _patch_validators(monkeypatch)
    result = materializer.build_week1_operating_roster_materialization_v1(
        k=80, terminal_prelock_root=_terminal_envelope(authority)
    )
    forged = deepcopy(result)
    all_boom_book = next(
        book
        for book in forged["source_membership_books"]
        if book["source_id"] == ALL_BOOM_SOURCE_ID
    )
    # Rank 80 is unentered at K80.  Rehash every retained hash to prove the
    # reopen checks roster -> lineup identity rather than trusting digests.
    all_boom_book["rosters"][79][0] = "forged-unentered-player"
    all_boom_book["rosters"][79].sort()
    all_boom_book["rosters_sha256"] = canonical_sha256(
        all_boom_book["rosters"]
    )
    forged["source_membership_books_sha256"] = canonical_sha256(
        forged["source_membership_books"]
    )
    forged.pop("materialization_sha256")
    forged["materialization_sha256"] = canonical_sha256(forged)

    with pytest.raises(
        materializer.Week1OperatingRosterMaterializerError,
        match="membership roster (escapes|.*binding differs)",
    ):
        materializer.validate_week1_operating_roster_materialization_v1(forged)


def test_materialization_reopen_rejects_rehashed_cap4_or_tier3_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    _patch_validators(monkeypatch)
    result = materializer.build_week1_operating_roster_materialization_v1(
        k=80, terminal_prelock_root=_terminal_envelope(authority)
    )
    for field in ("cap4_used", "tier3_used", "uses_realized_outcomes"):
        forged = deepcopy(result)
        forged[field] = True
        forged.pop("materialization_sha256")
        forged["materialization_sha256"] = canonical_sha256(forged)
        with pytest.raises(
            materializer.Week1OperatingRosterMaterializerError,
            match="fixed law differs",
        ):
            materializer.validate_week1_operating_roster_materialization_v1(
                forged
            )
