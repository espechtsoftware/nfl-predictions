from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from itertools import combinations, product

import numpy as np
import pytest

from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research import corpus_r6_independent_bank_contract_v1 as contract
from nfl_dfs.research import corpus_r6_selector_audit_v1 as audit


class _Store:
    def __init__(self) -> None:
        self._next_generation = 1
        self._objects: dict[tuple[str, str], tuple[dict[str, object], bytes]] = {}
        self._uris: set[str] = set()

    def publish(self, uri: str, raw: bytes) -> dict[str, object]:
        if uri in self._uris:
            raise RuntimeError("create-once precondition failed")
        generation = str(self._next_generation)
        self._next_generation += 1
        identity = {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self._objects[(uri, generation)] = (identity, raw)
        self._uris.add(uri)
        return dict(identity)

    def publish_json(self, uri: str, body: object) -> dict[str, object]:
        return self.publish(uri, contract.canonical_json_bytes_v1(body))

    def read_exact(self, identity: object) -> bytes:
        if not isinstance(identity, dict):
            raise KeyError("identity differs")
        key = (str(identity.get("uri")), str(identity.get("generation")))
        expected, raw = self._objects[key]
        if identity != expected:
            raise KeyError("identity differs")
        return raw


def _players() -> tuple[rw.PlayerSpec, ...]:
    rows: list[rw.PlayerSpec] = []
    groups = (
        ("q", "QB", 2),
        ("r", "RB", 5),
        ("w", "WR", 8),
        ("t", "TE", 3),
        ("d", "DST", 2),
    )
    ordinal = 0
    for prefix, position, count in groups:
        for index in range(count):
            rows.append(rw.PlayerSpec(
                player_id=f"{prefix}{index:02d}",
                position=position,
                team=f"T{ordinal:02d}",
                opponent=f"O{ordinal:02d}",
                game_id=f"G{ordinal % 5}",
                salary=4_000,
            ))
            ordinal += 1
    return tuple(rows)


def _candidate_rosters(
    players: tuple[rw.PlayerSpec, ...], count: int = 84
) -> tuple[list[str], dict[str, tuple[str, ...]]]:
    by_position = {
        position: [row.player_id for row in players if row.position == position]
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    rosters = sorted({
        tuple(sorted((qb, *rbs, *wrs, te, dst)))
        for qb, rbs, wrs, te, dst in product(
            by_position["QB"],
            combinations(by_position["RB"], 2),
            combinations(by_position["WR"], 4),
            by_position["TE"],
            by_position["DST"],
        )
    })[:count]
    ids = [f"L{index:03d}" for index in range(len(rosters))]
    return ids, dict(zip(ids, rosters, strict=True))


def _streams(role: str, ordinal: int) -> list[dict[str, object]]:
    base = (1_000 if role == "selection" else 2_000) + ordinal * 10
    return [
        {
            "stream_id": "projection",
            "generator_id": "fixture-projection-v1",
            "seed": base + 1,
            "substream_start": 0,
            "substream_stop": 10,
            "role_domain": role,
        },
        {
            "stream_id": "role-belief",
            "generator_id": "fixture-role-belief-v1",
            "seed": base + 2,
            "substream_start": 0,
            "substream_stop": 10,
            "role_domain": role,
        },
    ]


def _design_row(
    role: str, ordinal: int, generation_code: dict[str, str]
) -> dict[str, object]:
    return {
        "member_id": f"{role}-{ordinal}",
        "slate_id": "2025-w01",
        "replicate": ordinal,
        "role": role,
        "block_ordinal": 0,
        "world_count": 10,
        "rng_streams": _streams(role, ordinal),
        "generation_code_identity": generation_code,
    }


def _build_fixture() -> dict[str, object]:
    store = _Store()
    players = _players()
    candidate_ids, rosters = _candidate_rosters(players)
    candidate = contract.build_candidate_authority_v1(
        candidate_authority_id="fixture-candidates-v1",
        candidate_lineup_ids=candidate_ids,
        roster_by_lineup_id=rosters,
    )
    candidate_identity = store.publish_json(
        "gs://fixture/authorities/candidates.json", candidate
    )
    law = contract.build_law_release_v1(
        law_id="fixture-law-v1",
        law_definition={"distribution": "fixture-normal-v1", "world_count": 10},
    )
    law_identity = store.publish_json("gs://fixture/authorities/law.json", law)
    generator_path = "src/nfl_dfs/research/fixture_draw_generator.py"
    sources = {
        contract.CONTRACT_MODULE_PATH: store.publish(
            "gs://fixture/code/contract.py", b"contract-module-v2"
        ),
        contract.SELECTOR_AUDIT_MODULE_PATH: store.publish(
            "gs://fixture/code/selector.py", b"selector-module-v2"
        ),
        generator_path: store.publish(
            "gs://fixture/code/generator.py", b"generator-module-v1"
        ),
    }
    code = contract.build_code_release_v1(
        source_commit_sha="b" * 40,
        module_source_identities_by_path=sources,
        read_exact=store.read_exact,
    )
    code_identity = store.publish_json("gs://fixture/authorities/code.json", code)
    generation_code = next(
        dict(row["code_identity"])
        for row in code["modules"]
        if row["code_identity"]["module_path"] == generator_path
    )
    selection_designs = [
        _design_row("selection", ordinal, generation_code) for ordinal in range(2)
    ]
    audit_designs = [
        _design_row("audit", ordinal, generation_code) for ordinal in range(2)
    ]
    design = contract.build_precursor_design_v1(
        design_id="fixture-design-v1",
        candidate_authority_identity=candidate_identity,
        law_release_identity=law_identity,
        code_release_identity=code_identity,
        selection_member_designs=selection_designs,
        audit_member_designs=audit_designs,
        designated_selection_member_id="selection-0",
        challengers=[],
        primary_control_id="coverage-194-v1",
        primary_strategy_id="strict-230-coverage-v1",
        primary_metric_id="worlds_gt_230",
        read_exact=store.read_exact,
    )
    design_identity = store.publish_json("gs://fixture/designs/design.json", design)

    def materialize(row: dict[str, object], seed: int) -> tuple[dict[str, object], np.ndarray]:
        draws = np.random.default_rng(seed).normal(
            23.0, 5.0, size=(len(players), 10)
        ).astype(np.float32)
        source_identity = store.publish(
            f"gs://fixture/draws/{row['member_id']}.bin",
            contract.draw_source_bytes_v1(
                players,
                draws,
                precursor_design_identity=design_identity,
                precursor_design_sha256=str(design["precursor_design_sha256"]),
            ),
        )
        member = contract.bind_draw_bank_member_v1(
            member_id=str(row["member_id"]),
            slate_id=str(row["slate_id"]),
            law_id=str(law["law_id"]),
            law_sha256=str(law["law_sha256"]),
            replicate=int(row["replicate"]),
            role=str(row["role"]),
            block_ordinal=int(row["block_ordinal"]),
            rng_streams=row["rng_streams"],
            source_identity=source_identity,
            precursor_design_identity=design_identity,
            generation_code_identity=row["generation_code_identity"],
            players=players,
            player_draws=draws,
            read_exact=store.read_exact,
        )
        return member, draws

    selection_pairs = [
        materialize(row, 100 + ordinal)
        for ordinal, row in enumerate(selection_designs)
    ]
    audit_pairs = [
        materialize(row, 200 + ordinal)
        for ordinal, row in enumerate(audit_designs)
    ]
    selection_root = contract.build_draw_bank_root_v1(
        bank_id="fixture-selection-bank-v1",
        role="selection",
        members=[pair[0] for pair in selection_pairs],
    )
    audit_root = contract.build_draw_bank_root_v1(
        bank_id="fixture-audit-bank-v1",
        role="audit",
        members=[pair[0] for pair in audit_pairs],
    )
    plan = contract.build_independent_bank_plan_v1(
        plan_id="fixture-plan-v1",
        precursor_design=design,
        precursor_design_identity=design_identity,
        selection_bank_root=selection_root,
        audit_bank_root=audit_root,
        read_exact=store.read_exact,
    )
    plan_identity = store.publish_json("gs://fixture/plans/plan.json", plan)
    return {
        "store": store,
        "players": players,
        "candidate_ids": candidate_ids,
        "rosters": rosters,
        "selection_pairs": selection_pairs,
        "audit_pairs": audit_pairs,
        "plan": plan,
        "plan_identity": plan_identity,
    }


@pytest.fixture
def fixture(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    return _build_fixture()


def _freeze_authority(
    fixture: dict[str, object], index: int
) -> tuple[dict[str, object], dict[str, object]]:
    member, draws = fixture["selection_pairs"][index]
    freeze = audit.cross_score_and_freeze_books_v1(
        independent_bank_plan=fixture["plan"],
        independent_bank_plan_identity=fixture["plan_identity"],
        selection_member=member,
        players=fixture["players"],
        player_draws=draws,
        read_exact=fixture["store"].read_exact,
    )
    authority = audit.authoritative_replay_book_freeze_v1(
        freeze,
        players=fixture["players"],
        player_draws=draws,
        independent_bank_plan=fixture["plan"],
        independent_bank_plan_identity=fixture["plan_identity"],
        publication_uri=f"gs://fixture/publications/freeze-{index}.json",
        publish_create_once=fixture["store"].publish,
        read_exact=fixture["store"].read_exact,
    )
    return freeze, authority


def _audit_authority(
    fixture: dict[str, object],
    freeze_authority: dict[str, object],
    index: int,
) -> tuple[dict[str, object], dict[str, object]]:
    member, draws = fixture["audit_pairs"][index]
    result = audit.evaluate_books_on_audit_player_draws_v1(
        audit_member=member,
        players=fixture["players"],
        player_draws=draws,
        book_freeze_authority=freeze_authority,
        independent_bank_plan=fixture["plan"],
        independent_bank_plan_identity=fixture["plan_identity"],
        read_exact=fixture["store"].read_exact,
    )
    authority = audit.authoritative_replay_selector_audit_v1(
        result,
        players=fixture["players"],
        player_draws=draws,
        book_freeze_authority=freeze_authority,
        independent_bank_plan=fixture["plan"],
        independent_bank_plan_identity=fixture["plan_identity"],
        publication_uri=f"gs://fixture/publications/audit-{index}.json",
        publish_create_once=fixture["store"].publish,
        read_exact=fixture["store"].read_exact,
    )
    return result, authority


def test_full_fixed_ledger_is_exact_descriptive_and_plan_owned(
    fixture: dict[str, object],
) -> None:
    freeze, freeze_authority = _freeze_authority(fixture, 0)
    assert freeze["freeze_role"] == "designated-audit-book"
    assert freeze["book_count"] == 8
    assert all(book["entry_count"] == 80 for book in freeze["books"])

    result_authorities = [
        _audit_authority(fixture, freeze_authority, index)[1]
        for index in range(2)
    ]
    summary = audit.summarize_fixed_audit_ledger_v1(
        independent_bank_plan=fixture["plan"],
        independent_bank_plan_identity=fixture["plan_identity"],
        book_freeze_authorities=[freeze_authority],
        audit_result_authorities=result_authorities,
        read_exact=fixture["store"].read_exact,
    )
    assert summary["ordered_audit_member_sha256s"] == fixture["plan"][
        "audit_bank_root"
    ]["ordered_member_sha256s"]
    assert summary["fixed_ledger_exhausted"] is True
    assert summary["analysis_mode"] == "descriptive-fixed-ledger-no-inference-v1"
    assert summary["uncertainty_estimator"] == "not-implemented"
    assert summary["inference_claims_allowed"] is False
    assert summary["primary_strategy_id"] == "strict-230-coverage-v1"
    assert summary["primary_comparison"]["compared_strategy_id"] == (
        "strict-230-coverage-v1"
    )
    assert summary["primary_metric_result"]["metric_id"] == "worlds_gt_230"
    assert len(summary["book_freeze_authority_sha256s"]) == 1


def test_repeat_selection_consumes_the_exact_selection_grid(
    fixture: dict[str, object],
) -> None:
    _, designated = _freeze_authority(fixture, 0)
    diagnostic_freeze, diagnostic = _freeze_authority(fixture, 1)
    assert diagnostic_freeze["freeze_role"] == "repeat-selection-diagnostic"
    summary = audit.summarize_repeat_selection_v1(
        book_freeze_authorities=[designated, diagnostic],
        independent_bank_plan=fixture["plan"],
        independent_bank_plan_identity=fixture["plan_identity"],
        read_exact=fixture["store"].read_exact,
    )
    assert summary["selection_member_sha256s"] == fixture["plan"][
        "selection_bank_root"
    ]["ordered_member_sha256s"]
    assert summary["replicate_count"] == 2

    with pytest.raises(
        audit.CorpusR6SelectorAuditV1Error,
        match="exact selection grid",
    ):
        audit.summarize_repeat_selection_v1(
            book_freeze_authorities=[designated, designated],
            independent_bank_plan=fixture["plan"],
            independent_bank_plan_identity=fixture["plan_identity"],
            read_exact=fixture["store"].read_exact,
        )


def test_diagnostic_selection_book_cannot_open_the_audit_bank(
    fixture: dict[str, object],
) -> None:
    _, diagnostic = _freeze_authority(fixture, 1)
    member, draws = fixture["audit_pairs"][0]
    with pytest.raises(
        audit.CorpusR6SelectorAuditV1Error,
        match="ex-ante designated selection book",
    ):
        audit.evaluate_books_on_audit_player_draws_v1(
            audit_member=member,
            players=fixture["players"],
            player_draws=draws,
            book_freeze_authority=diagnostic,
            independent_bank_plan=fixture["plan"],
            independent_bank_plan_identity=fixture["plan_identity"],
            read_exact=fixture["store"].read_exact,
        )


def test_book_trace_schema_rejects_coherent_extra_fields(
    fixture: dict[str, object],
) -> None:
    freeze, _ = _freeze_authority(fixture, 0)
    poisoned = deepcopy(freeze)
    poisoned["books"][0]["selection_trace"][0]["post_hoc_note"] = "extra"
    poisoned["books"][0].pop("selection_book_sha256")
    poisoned["books"][0]["selection_book_sha256"] = contract.canonical_sha256_v1(
        poisoned["books"][0]
    )
    poisoned.pop("book_freeze_sha256")
    poisoned["book_freeze_sha256"] = contract.canonical_sha256_v1(poisoned)
    with pytest.raises(
        audit.CorpusR6SelectorAuditV1Error,
        match="selection trace row fields differ",
    ):
        audit.validate_book_freeze_v1(poisoned)


def test_audit_authority_rejects_a_coherently_rehashed_nonexact_union(
    fixture: dict[str, object],
) -> None:
    _, freeze_authority = _freeze_authority(fixture, 0)
    result, authority = _audit_authority(fixture, freeze_authority, 0)
    assert len(result["audit_union_lineup_ids"]) >= 81
    poisoned_result = deepcopy(result)
    poisoned_result["audit_union_lineup_ids"] = poisoned_result[
        "audit_union_lineup_ids"
    ][1:]
    poisoned_result["audit_union_lineup_ids_sha256"] = contract.canonical_sha256_v1(
        poisoned_result["audit_union_lineup_ids"]
    )
    binding = poisoned_result["audit_matrix_binding"]
    binding["candidate_lineup_ids_sha256"] = poisoned_result[
        "audit_union_lineup_ids_sha256"
    ]
    binding["score_matrix_shape"][0] -= 1
    binding.pop("matrix_binding_sha256")
    binding["matrix_binding_sha256"] = contract.canonical_sha256_v1(binding)
    for book in poisoned_result["books"]:
        book["audit_matrix_binding_sha256"] = binding["matrix_binding_sha256"]
        book.pop("audit_book_sha256")
        book["audit_book_sha256"] = contract.canonical_sha256_v1(book)
    poisoned_result.pop("selector_audit_sha256")
    poisoned_result["selector_audit_sha256"] = contract.canonical_sha256_v1(
        poisoned_result
    )
    assert audit.validate_selector_audit_result_v1(poisoned_result) == poisoned_result

    poisoned_authority = deepcopy(authority)
    poisoned_authority["selector_audit_result"] = poisoned_result
    poisoned_authority["selector_audit_sha256"] = poisoned_result[
        "selector_audit_sha256"
    ]
    poisoned_authority["selector_audit_publication_identity"] = fixture[
        "store"
    ].publish_json("gs://fixture/publications/poisoned-audit.json", poisoned_result)
    poisoned_authority.pop("selector_audit_result_authority_sha256")
    poisoned_authority["selector_audit_result_authority_sha256"] = (
        contract.canonical_sha256_v1(poisoned_authority)
    )
    with pytest.raises(
        audit.CorpusR6SelectorAuditV1Error,
        match="union differs from the exact frozen-book union",
    ):
        audit.validate_selector_audit_result_authority_v1(
            poisoned_authority,
            book_freeze_authority=freeze_authority,
            independent_bank_plan=fixture["plan"],
            independent_bank_plan_identity=fixture["plan_identity"],
            read_exact=fixture["store"].read_exact,
        )


def test_caller_self_attested_publication_identity_has_no_authority(
    fixture: dict[str, object],
) -> None:
    freeze, authority = _freeze_authority(fixture, 0)
    fake = deepcopy(authority)
    raw = contract.canonical_json_bytes_v1(freeze)
    fake["book_freeze_publication_identity"] = {
        "uri": "gs://fixture/publications/invented-freeze.json",
        "generation": "999999",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    fake.pop("book_freeze_authority_sha256")
    fake["book_freeze_authority_sha256"] = contract.canonical_sha256_v1(fake)
    with pytest.raises(
        audit.CorpusR6SelectorAuditV1Error,
        match="exact-generation reopen failed",
    ):
        audit.validate_book_freeze_authority_v1(
            fake,
            independent_bank_plan=fixture["plan"],
            independent_bank_plan_identity=fixture["plan_identity"],
            read_exact=fixture["store"].read_exact,
        )


def test_fixed_ledger_rejects_missing_or_reordered_members(
    fixture: dict[str, object],
) -> None:
    _, freeze_authority = _freeze_authority(fixture, 0)
    authorities = [
        _audit_authority(fixture, freeze_authority, index)[1]
        for index in range(2)
    ]
    for invalid in (authorities[:1], list(reversed(authorities))):
        with pytest.raises(
            audit.CorpusR6SelectorAuditV1Error,
            match="exact fixed ledger in order",
        ):
            audit.summarize_fixed_audit_ledger_v1(
                independent_bank_plan=fixture["plan"],
                independent_bank_plan_identity=fixture["plan_identity"],
                book_freeze_authorities=[freeze_authority],
                audit_result_authorities=invalid,
                read_exact=fixture["store"].read_exact,
            )


def test_matrix_replay_rejects_changed_draw_bytes(
    fixture: dict[str, object],
) -> None:
    member, draws = fixture["selection_pairs"][0]
    changed = draws.copy()
    changed[0, 0] += np.float32(1.0)
    with pytest.raises(
        audit.CorpusR6SelectorAuditV1Error,
        match="draw source exact-generation reopen failed",
    ):
        audit.cross_score_and_freeze_books_v1(
            independent_bank_plan=fixture["plan"],
            independent_bank_plan_identity=fixture["plan_identity"],
            selection_member=member,
            players=fixture["players"],
            player_draws=changed,
            read_exact=fixture["store"].read_exact,
        )
