from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from itertools import combinations, product

import numpy as np
import pytest

from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research import corpus_r6_independent_bank_contract_v1 as contract


class _Store:
    """Small immutable-generation store; identities cannot stand in for bytes."""

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


def _streams(role: str, ordinal: int, worlds: int = 10) -> list[dict[str, object]]:
    base = (1_000 if role == "selection" else 2_000) + ordinal * 10
    return [
        {
            "stream_id": "projection",
            "generator_id": "fixture-projection-v1",
            "seed": base + 1,
            "substream_start": 0,
            "substream_stop": worlds,
            "role_domain": role,
        },
        {
            "stream_id": "role-belief",
            "generator_id": "fixture-role-belief-v1",
            "seed": base + 2,
            "substream_start": 0,
            "substream_stop": worlds,
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


def _bundle() -> dict[str, object]:
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
    module_sources = {
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
        source_commit_sha="a" * 40,
        module_source_identities_by_path=module_sources,
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
        design_id="fixture-ex-ante-design-v1",
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
    design_identity = store.publish_json(
        "gs://fixture/designs/ex-ante.json", design
    )

    def materialize(row: dict[str, object], seed: int) -> tuple[dict[str, object], np.ndarray]:
        draws = np.random.default_rng(seed).normal(
            23.0, 5.0, size=(len(players), 10)
        ).astype(np.float32)
        raw = contract.draw_source_bytes_v1(
            players,
            draws,
            precursor_design_identity=design_identity,
            precursor_design_sha256=str(design["precursor_design_sha256"]),
        )
        source_identity = store.publish(
            f"gs://fixture/draws/{row['member_id']}.bin", raw
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
        members=[row[0] for row in selection_pairs],
    )
    audit_root = contract.build_draw_bank_root_v1(
        bank_id="fixture-audit-bank-v1",
        role="audit",
        members=[row[0] for row in audit_pairs],
    )
    plan = contract.build_independent_bank_plan_v1(
        plan_id="fixture-independent-bank-plan-v1",
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
        "candidate": candidate,
        "candidate_identity": candidate_identity,
        "law": law,
        "law_identity": law_identity,
        "code": code,
        "code_identity": code_identity,
        "design": design,
        "design_identity": design_identity,
        "selection_designs": selection_designs,
        "audit_designs": audit_designs,
        "selection_pairs": selection_pairs,
        "audit_pairs": audit_pairs,
        "selection_root": selection_root,
        "audit_root": audit_root,
        "plan": plan,
        "plan_identity": plan_identity,
    }


def test_plan_is_ex_ante_plan_owned_and_descriptive_only() -> None:
    fixture = _bundle()
    plan = contract.validate_independent_bank_plan_v1(
        fixture["plan"], read_exact=fixture["store"].read_exact
    )
    assert plan["primary_control_id"] == "coverage-194-v1"
    assert plan["primary_strategy_id"] == "strict-230-coverage-v1"
    assert plan["designated_selection_member_id"] == "selection-0"
    assert plan["designated_selection_member_sha256"] == (
        fixture["selection_pairs"][0][0]["draw_bank_member_sha256"]
    )
    assert plan["precision_rule"]["ordered_audit_member_sha256s"] == (
        fixture["audit_root"]["ordered_member_sha256s"]
    )
    assert plan["precision_rule"]["uncertainty_estimator"] == "not-implemented"
    assert plan["inference_claims_allowed"] is False
    assert plan["multi_law_enabled"] is False


def test_code_and_upstream_authorities_require_exact_generation_reopen() -> None:
    fixture = _bundle()
    store = fixture["store"]
    assert contract.validate_code_release_v1(
        fixture["code"], read_exact=store.read_exact
    ) == fixture["code"]

    poisoned = deepcopy(fixture["code"])
    poisoned["modules"][0]["module_source_identity"]["generation"] = "999999"
    poisoned.pop("code_release_sha256")
    poisoned["module_manifest_sha256"] = contract.canonical_sha256_v1(
        poisoned["modules"]
    )
    poisoned["code_release_sha256"] = contract.canonical_sha256_v1(poisoned)
    with pytest.raises(
        contract.CorpusR6IndependentBankContractV1Error,
        match="exact-generation reopen failed",
    ):
        contract.validate_code_release_v1(poisoned, read_exact=store.read_exact)

    fake_candidate_identity = dict(fixture["candidate_identity"])
    fake_candidate_identity["generation"] = "888888"
    with pytest.raises(
        contract.CorpusR6IndependentBankContractV1Error,
        match="exact-generation reopen failed",
    ):
        contract.build_precursor_design_v1(
            design_id="spliced-design",
            candidate_authority_identity=fake_candidate_identity,
            law_release_identity=fixture["law_identity"],
            code_release_identity=fixture["code_identity"],
            selection_member_designs=fixture["selection_designs"],
            audit_member_designs=fixture["audit_designs"],
            designated_selection_member_id="selection-0",
            challengers=[],
            primary_control_id="coverage-194-v1",
            primary_strategy_id="strict-230-coverage-v1",
            primary_metric_id="worlds_gt_230",
            read_exact=store.read_exact,
        )


def test_precursor_freezes_exact_rng_grids_before_bound_draw_sources() -> None:
    fixture = _bundle()
    design = contract.validate_precursor_design_v1(
        fixture["design"], read_exact=fixture["store"].read_exact
    )
    assert design["design_frozen_before_bank_generation"] is True
    assert [row["member_id"] for row in design["selection_member_designs"]] == [
        "selection-0", "selection-1"
    ]
    for member, draws in [
        *fixture["selection_pairs"], *fixture["audit_pairs"]
    ]:
        assert member["precursor_design_identity"] == fixture["design_identity"]
        assert contract.reopen_draw_source_v1(
            source_identity=member["source_identity"],
            players=fixture["players"],
            player_draws=draws,
            precursor_design_identity=fixture["design_identity"],
            precursor_design_sha256=design["precursor_design_sha256"],
            read_exact=fixture["store"].read_exact,
        ) == member["source_identity"]

    overlap = deepcopy(fixture["audit_designs"])
    overlap[0]["rng_streams"][0] = deepcopy(
        fixture["selection_designs"][0]["rng_streams"][0]
    )
    overlap[0]["rng_streams"][0]["role_domain"] = "audit"
    with pytest.raises(
        contract.CorpusR6IndependentBankContractV1Error,
        match="selection/audit design reuses an RNG substream",
    ):
        contract.build_precursor_design_v1(
            design_id="overlap-design",
            candidate_authority_identity=fixture["candidate_identity"],
            law_release_identity=fixture["law_identity"],
            code_release_identity=fixture["code_identity"],
            selection_member_designs=fixture["selection_designs"],
            audit_member_designs=overlap,
            designated_selection_member_id="selection-0",
            challengers=[],
            primary_control_id="coverage-194-v1",
            primary_strategy_id="strict-230-coverage-v1",
            primary_metric_id="worlds_gt_230",
            read_exact=fixture["store"].read_exact,
        )


def test_plan_rejects_reordered_or_coherently_spliced_bank_roots() -> None:
    fixture = _bundle()
    reversed_root = contract.build_draw_bank_root_v1(
        bank_id="reordered-selection",
        role="selection",
        members=list(reversed([row[0] for row in fixture["selection_pairs"]])),
    )
    with pytest.raises(
        contract.CorpusR6IndependentBankContractV1Error,
        match="does not bijectively realize the ex-ante grid",
    ):
        contract.build_independent_bank_plan_v1(
            plan_id="spliced-plan",
            precursor_design=fixture["design"],
            precursor_design_identity=fixture["design_identity"],
            selection_bank_root=reversed_root,
            audit_bank_root=fixture["audit_root"],
            read_exact=fixture["store"].read_exact,
        )

    member = deepcopy(fixture["selection_pairs"][0][0])
    member["precursor_design_sha256"] = "f" * 64
    member.pop("draw_bank_member_sha256")
    member["draw_bank_member_sha256"] = contract.canonical_sha256_v1(member)
    spliced_root = contract.build_draw_bank_root_v1(
        bank_id="coherent-splice",
        role="selection",
        members=[member, fixture["selection_pairs"][1][0]],
    )
    with pytest.raises(
        contract.CorpusR6IndependentBankContractV1Error,
        match="does not bijectively realize the ex-ante grid",
    ):
        contract.build_independent_bank_plan_v1(
            plan_id="spliced-plan",
            precursor_design=fixture["design"],
            precursor_design_identity=fixture["design_identity"],
            selection_bank_root=spliced_root,
            audit_bank_root=fixture["audit_root"],
            read_exact=fixture["store"].read_exact,
        )


def test_matrix_sources_cannot_be_replaced_by_caller_self_hashes() -> None:
    fixture = _bundle()
    member, draws = fixture["selection_pairs"][0]
    changed = draws.copy()
    changed[0, 0] += np.float32(0.5)
    with pytest.raises(
        contract.CorpusR6IndependentBankContractV1Error,
        match="bound player draws differ",
    ):
        contract.validate_draw_bank_member_v1(
            member, players=fixture["players"], player_draws=changed
        )
    with pytest.raises(
        contract.CorpusR6IndependentBankContractV1Error,
        match="identity differs from exact matrix bytes",
    ):
        contract.reopen_draw_source_v1(
            source_identity=member["source_identity"],
            players=fixture["players"],
            player_draws=changed,
            precursor_design_identity=fixture["design_identity"],
            precursor_design_sha256=fixture["design"]["precursor_design_sha256"],
            read_exact=fixture["store"].read_exact,
        )


def test_publication_requires_create_once_and_independent_exact_reopen() -> None:
    store = _Store()
    body = {"schema_version": "fixture/v1", "value": 1}
    identity = contract.publish_body_create_once_v1(
        body,
        uri="gs://fixture/publications/value.json",
        publish_create_once=store.publish,
        read_exact=store.read_exact,
        label="fixture publication",
    )
    assert store.read_exact(identity) == contract.canonical_json_bytes_v1(body)
    with pytest.raises(
        contract.CorpusR6IndependentBankContractV1Error,
        match="create-once publication failed",
    ):
        contract.publish_body_create_once_v1(
            body,
            uri="gs://fixture/publications/value.json",
            publish_create_once=store.publish,
            read_exact=store.read_exact,
            label="fixture publication",
        )

    def fake_publisher(uri: str, raw: bytes) -> dict[str, object]:
        return {
            "uri": uri,
            "generation": "777777",
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }

    with pytest.raises(
        contract.CorpusR6IndependentBankContractV1Error,
        match="exact-generation reopen failed",
    ):
        contract.publish_body_create_once_v1(
            body,
            uri="gs://fixture/publications/fake.json",
            publish_create_once=fake_publisher,
            read_exact=store.read_exact,
            label="fake publication",
        )


def test_cross_law_crn_and_multi_law_weights_remain_fail_closed() -> None:
    fixture = _bundle()
    left = fixture["audit_pairs"][0][0]
    right = deepcopy(left)
    right["law_id"] = "other-law-v1"
    right["law_sha256"] = sha256(b"other-law-v1").hexdigest()
    right.pop("draw_bank_member_sha256")
    right["draw_bank_member_sha256"] = contract.canonical_sha256_v1(right)
    with pytest.raises(
        contract.CorpusR6IndependentBankContractV1Error,
        match="cross-law CRN v1 is disabled",
    ):
        contract.validate_crn_pairing_v1(left, right)
    with pytest.raises(
        contract.CorpusR6IndependentBankContractV1Error,
        match="multi-law weights are disabled",
    ):
        contract.multi_law_weight_derivation_sha256_v1(
            law_ids=["a", "b"],
            calibration_release_sha256s=["a" * 64, "b" * 64],
            weights=[{"law_id": "a", "weight": 0.5}],
        )
