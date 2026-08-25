from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from typing import Any, Callable

import pytest

from nfl_dfs.research import corpus_extreme_tail_census as census
from nfl_dfs.research import corpus_extreme_tail_panel_release as release
from nfl_dfs.research import corpus_extreme_tail_support_switch as support
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import corpus_v12_panel_index as panel
from nfl_dfs.research import residual_world_columns as rw


COMMIT = "a" * 40
DIGEST = "sha256:" + "b" * 64
IMAGE = {
    "uri": f"us-central1-docker.pkg.dev/example/research/t230@{DIGEST}",
    "digest": DIGEST,
}
OUTPUT_PREFIX = "gs://fixture-bucket/research/t230/run-001/"
_PANEL_FALSE_FIELDS = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "promotion_authority",
    "decision_authority",
)
_MANIFEST_FALSE_FIELDS = (
    *_PANEL_FALSE_FIELDS[:-2],
    "r6_freeze_authority",
    *_PANEL_FALSE_FIELDS[-2:],
)


def _identity(label: str, ordinal: int) -> dict[str, object]:
    payload = f"{label}:{ordinal}".encode()
    return {
        "uri": f"gs://fixture-bucket/objects/{label}-{ordinal:04d}.json",
        "generation": str(10_000 + ordinal),
        "sha256": sha256(payload).hexdigest(),
        "bytes": len(payload),
    }


def _build_panel() -> tuple[dict[str, object], dict[str, object]]:
    source_completion = _identity("source-completion", 0)
    members: list[dict[str, object]] = []
    object_ordinal = 100
    for source_ordinal in range(panel.V12_SOURCE_TASK_COUNT):
        lane_ordinal = 0 if source_ordinal < 28 else 1
        task_ordinal = source_ordinal if lane_ordinal == 0 else source_ordinal - 28
        arms = []
        for arm_ordinal, arm_id in enumerate(batch.PARAMETER_SET_ORDER):
            arms.append({
                "arm_ordinal": arm_ordinal,
                "parameter_set_id": arm_id,
                "result_identity": _identity("arm", object_ordinal),
            })
            object_ordinal += 1
        members.append({
            "slate_id": f"2023-w{source_ordinal + 1:02d}",
            "lane_ordinal": lane_ordinal,
            "lane_id": "v12a" if lane_ordinal == 0 else "v12b",
            "task_ordinal": task_ordinal,
            "source_task_ordinal": source_ordinal,
            "source_task_authority_sha256": sha256(
                f"source-task:{source_ordinal}".encode()
            ).hexdigest(),
            "task_acceptance_identity": _identity(
                "task-acceptance", 1_000 + source_ordinal
            ),
            "carrier_identity": _identity("carrier", 2_000 + source_ordinal),
            "arms": arms,
        })
    lanes = []
    for lane_ordinal, law in enumerate(panel.V12_LANE_LATTICE):
        lane_members = [
            row for row in members if row["lane_ordinal"] == lane_ordinal
        ]
        lanes.append({
            "lane_ordinal": lane_ordinal,
            "lane_id": law["lane_id"],
            "terminal_receipt_identity": _identity("terminal", lane_ordinal),
            "batch_completion_identity": _identity("completion", lane_ordinal),
            "batch_id": f"fixture-batch-{lane_ordinal}",
            "batch_mode": law["batch_mode"],
            "artifact_source_authority_completion": source_completion,
            "artifact_source_authority_completion_sha256": "c" * 64,
            "source_task_offset": law["source_task_offset"],
            "expected_task_count": law["task_count"],
            "accepted_task_count": law["task_count"],
            "accepted_task_ordinals": list(range(int(law["task_count"]))),
            "task_acceptance_identities_sha256": batch.canonical_sha256([
                row["task_acceptance_identity"] for row in lane_members
            ]),
            "carrier_identities_sha256": batch.canonical_sha256([
                row["carrier_identity"] for row in lane_members
            ]),
            "complete": True,
        })
    body: dict[str, object] = {
        "schema_version": panel.PANEL_INDEX_SCHEMA,
        "publication_mode": panel.PUBLICATION_MODE,
        "panel_id": "v12:" + batch.canonical_sha256([
            row["terminal_receipt_identity"] for row in lanes
        ]),
        "artifact_source_authority_completion": source_completion,
        "artifact_source_authority_completion_sha256": "c" * 64,
        "lane_count": 2,
        "lanes": lanes,
        "accepted_slate_count": panel.V12_SOURCE_TASK_COUNT,
        "accepted_slates": members,
        "exclusions": [],
        "failures": [],
        "missing_tasks": [],
        "coverage": {
            "expected_task_count": panel.V12_SOURCE_TASK_COUNT,
            "accepted_task_count": panel.V12_SOURCE_TASK_COUNT,
            "excluded_task_count": 0,
            "failed_task_count": 0,
            "missing_task_count": 0,
            "complete": True,
        },
        **{field: False for field in _PANEL_FALSE_FIELDS},
    }
    body["panel_index_sha256"] = batch.canonical_sha256(body)
    identity = batch.object_identity_for_json(
        body,
        uri="gs://fixture-bucket/panels/foundry-v12-panel-index-v1.json",
        generation="99123",
    )
    return body, identity


def _manifest() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    panel_index, panel_identity = _build_panel()
    manifest = release.build_t230_panel_execution_manifest_v1(
        panel_index=panel_index,
        panel_index_identity=panel_identity,
        source_commit_sha=COMMIT,
        immutable_image=IMAGE,
        output_prefix=OUTPUT_PREFIX,
    )
    return manifest, panel_index, panel_identity


def _rehash_panel(value: dict[str, object]) -> dict[str, object]:
    lanes = value["lanes"]
    members = value["accepted_slates"]
    assert isinstance(lanes, list)
    assert isinstance(members, list)
    for lane in lanes:
        lane_ordinal = lane["lane_ordinal"]
        lane_members = [
            row for row in members if row["lane_ordinal"] == lane_ordinal
        ]
        lane["task_acceptance_identities_sha256"] = batch.canonical_sha256([
            row["task_acceptance_identity"] for row in lane_members
        ])
        lane["carrier_identities_sha256"] = batch.canonical_sha256([
            row["carrier_identity"] for row in lane_members
        ])
    value.pop("panel_index_sha256", None)
    value["panel_index_sha256"] = batch.canonical_sha256(value)
    return value


def _panel_identity(value: dict[str, object]) -> dict[str, object]:
    return batch.object_identity_for_json(
        value,
        uri="gs://fixture-bucket/panels/changed-panel-index-v1.json",
        generation="99124",
    )


def _rehash_manifest(value: dict[str, object]) -> dict[str, object]:
    members = value["source_members"]
    assert isinstance(members, list)
    value["source_members_sha256"] = batch.canonical_sha256(members)
    for contract_field, hash_field in (
        ("ordinary_r_world_contract", "world_contract_sha256"),
        ("authoritative_generation_dose", "generation_dose_sha256"),
        ("t230_retrieval_contract", "retrieval_contract_sha256"),
        ("support_contract", "support_contract_sha256"),
    ):
        contract = value[contract_field]
        assert isinstance(contract, dict)
        contract.pop(hash_field, None)
        contract[hash_field] = batch.canonical_sha256(contract)
    seed = {
        "schema_version": value["schema_version"],
        "panel_object_identity": value["panel_object_identity"],
        "panel_index_sha256": value["panel_index_sha256"],
        "source_members_sha256": value["source_members_sha256"],
        "source_commit_sha": value["source_commit_sha"],
        "immutable_image": value["immutable_image"],
        "output_prefix": value["output_prefix"],
    }
    value["manifest_id"] = "foundry-t230:" + batch.canonical_sha256(seed)
    value.pop("execution_manifest_sha256", None)
    value["execution_manifest_sha256"] = batch.canonical_sha256(value)
    return value


def _validate(
    manifest: dict[str, object],
    panel_index: dict[str, object],
    panel_identity: dict[str, object],
    **overrides: object,
) -> dict[str, object]:
    arguments: dict[str, object] = {
        "panel_index": panel_index,
        "panel_index_identity": panel_identity,
        "source_commit_sha": COMMIT,
        "immutable_image": IMAGE,
        "output_prefix": OUTPUT_PREFIX,
    }
    arguments.update(overrides)
    return release.validate_t230_panel_execution_manifest_v1(
        manifest, **arguments  # type: ignore[arg-type]
    )


def test_manifest_binds_exact_panel_science_outputs_and_replays() -> None:
    manifest, panel_index, panel_identity = _manifest()
    second = release.build_t230_panel_execution_manifest_v1(
        panel_index=panel_index,
        panel_index_identity=panel_identity,
        source_commit_sha=COMMIT,
        immutable_image=IMAGE,
        output_prefix=OUTPUT_PREFIX,
    )
    assert batch.canonical_json_bytes(second) == batch.canonical_json_bytes(
        manifest
    )
    assert _validate(manifest, panel_index, panel_identity) == manifest
    assert manifest["schema_version"] == (
        "foundry-t230-panel-execution-manifest/v1"
    )
    assert manifest["publication_mode"] == "create_once"
    assert manifest["panel_object_identity"] == panel_identity
    assert manifest["panel_id"] == panel_index["panel_id"]
    assert manifest["panel_index_sha256"] == panel_index["panel_index_sha256"]
    assert manifest["panel_accepted_slates_sha256"] == batch.canonical_sha256(
        panel_index["accepted_slates"]
    )
    members = manifest["source_members"]
    assert isinstance(members, list)
    assert manifest["source_member_count"] == 54
    assert [row["source_ordinal"] for row in members] == list(range(54))
    assert len({row["result_uri"] for row in members}) == 54
    assert len({row["acceptance_uri"] for row in members}) == 54
    assert members[0]["result_uri"] == (
        OUTPUT_PREFIX
        + "slates/00-2023-w01/foundry-t230-slate-analysis-v1.json"
    )
    assert members[-1]["acceptance_uri"] == (
        OUTPUT_PREFIX
        + "slates/53-2023-w54/foundry-t230-slate-acceptance-v1.json"
    )
    assert manifest["source_members_sha256"] == batch.canonical_sha256(members)
    assert manifest["source_arm_order"] == list(batch.PARAMETER_SET_ORDER)
    dose = manifest["authoritative_generation_dose"]
    assert dose["dose_shape"] == [7, 5, 200]
    assert dose["total_visit_count"] == 7_000
    assert dose["generation_dose_sha256"] == batch.canonical_sha256({
        key: value
        for key, value in dose.items()
        if key != "generation_dose_sha256"
    })
    worlds = manifest["ordinary_r_world_contract"]
    assert worlds["worlds_per_block"] == 10_000
    assert worlds["score_world_count"] == 50_000
    retrieval = manifest["t230_retrieval_contract"]
    assert retrieval["entry_budgets"] == [4, 14, 80]
    assert retrieval["ranking_prefix_law"] == (
        "exact-prefix-of-one-deterministic-rank-80"
    )
    assert [
        row["strategy_id"] for row in retrieval["strategy_registry"]
    ] == [
        "coverage-ge-230-v1",
        "bounded-tail-ladder-ge-210-250-v1",
        "block-robust-bounded-tail-ge-210-250-v1",
        "individual-ge-230-rank-v1",
    ]
    assert retrieval["retrieval_contract_sha256"] == batch.canonical_sha256({
        key: value
        for key, value in retrieval.items()
        if key != "retrieval_contract_sha256"
    })
    support_contract = manifest["support_contract"]
    assert support_contract["fold_support"] == {
        "training_block_count": 4,
        "requires_every_training_block_nonzero": True,
        "minimum_opportunity_world_count": 100,
    }
    assert support_contract["final_support"] == {
        "training_block_count": 5,
        "requires_every_training_block_nonzero": True,
        "minimum_opportunity_world_count": 125,
    }
    assert support_contract["panel_support"]["fold_pass_minimum"] == 216
    assert support_contract["panel_support"]["final_pass_minimum"] == 44
    assert support_contract["panel_support"]["authoritative_slate_count"] == 54
    assert support_contract["panel_support"]["fold_gate_total"] == (
        manifest["source_member_count"] * 5
    )
    assert support_contract["panel_support"]["final_gate_total"] == (
        manifest["source_member_count"]
    )
    assert support_contract["support_contract_sha256"] == (
        batch.canonical_sha256({
            key: value
            for key, value in support_contract.items()
            if key != "support_contract_sha256"
        })
    )
    assert all(manifest[field] is False for field in _MANIFEST_FALSE_FIELDS)
    retained_hash = manifest["execution_manifest_sha256"]
    unhashed = {
        key: value
        for key, value in manifest.items()
        if key != "execution_manifest_sha256"
    }
    assert retained_hash == batch.canonical_sha256(unhashed)


@pytest.mark.parametrize(
    "dependency",
    ("source-arms", "world-width", "visit-dose", "support", "panel-lanes"),
)
def test_coherent_imported_dependency_drift_cannot_redefine_the_protocol(
    monkeypatch: pytest.MonkeyPatch,
    dependency: str,
) -> None:
    panel_index, panel_identity = _build_panel()
    if dependency == "source-arms":
        drifted_arms = ("renamed-incumbent", *batch.PARAMETER_SET_ORDER[1:])
        monkeypatch.setattr(batch, "PARAMETER_SET_ORDER", drifted_arms)
        monkeypatch.setattr(census, "SOURCE_ARM_ORDER", drifted_arms)
        monkeypatch.setattr(
            census,
            "SOURCE_ARM_ORDER_SHA256",
            batch.canonical_sha256(list(drifted_arms)),
        )
    elif dependency == "world-width":
        monkeypatch.setattr(rw, "WORLDS_PER_BLOCK", 9_999)
        monkeypatch.setattr(batch, "WORLDS_PER_BLOCK", 9_999)
        monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 9_999)
    elif dependency == "visit-dose":
        monkeypatch.setattr(release, "LEGAL_VISITS_PER_BLOCK", 199)
        monkeypatch.setattr(census, "VISITS_PER_BLOCK", 199)
        monkeypatch.setattr(batch, "SOLVE_ATTEMPTS_PER_BLOCK", 199)
    elif dependency == "support":
        monkeypatch.setattr(
            support, "FOLD_MINIMUM_OPPORTUNITY_WORLDS", 99
        )
        monkeypatch.setattr(
            support, "FINAL_MINIMUM_OPPORTUNITY_WORLDS", 124
        )
        monkeypatch.setattr(support, "GENERAL_SUPPORT_NUMERATOR", 3)
        monkeypatch.setattr(support, "GENERAL_SUPPORT_DENOMINATOR", 4)
        monkeypatch.setattr(support, "AUTHORITATIVE_SLATE_COUNT", 55)
        monkeypatch.setattr(support, "AUTHORITATIVE_FOLD_GATE_COUNT", 275)
        monkeypatch.setattr(support, "AUTHORITATIVE_FINAL_GATE_COUNT", 55)
    else:
        drifted_lanes = deepcopy(panel.V12_LANE_LATTICE)
        drifted_lanes[0]["task_count"] = 29
        drifted_lanes[1]["source_task_offset"] = 29
        monkeypatch.setattr(panel, "V12_SOURCE_TASK_COUNT", 55)
        monkeypatch.setattr(panel, "V12_LANE_LATTICE", drifted_lanes)
    with pytest.raises(
        release.CorpusExtremeTailPanelReleaseError,
        match="frozen dependency constants drifted",
    ):
        release.build_t230_panel_execution_manifest_v1(
            panel_index=panel_index,
            panel_index_identity=panel_identity,
            source_commit_sha=COMMIT,
            immutable_image=IMAGE,
            output_prefix=OUTPUT_PREFIX,
        )


@pytest.mark.parametrize("attack", ("clones", "reorder", "duplicate"))
def test_panel_clone_reorder_and_duplicate_attacks_fail_closed(
    attack: str,
) -> None:
    panel_index, _ = _build_panel()
    members = panel_index["accepted_slates"]
    assert isinstance(members, list)
    if attack == "clones":
        first = deepcopy(members[0])
        clones = []
        for ordinal in range(54):
            clone = deepcopy(first)
            clone["slate_id"] = f"clone-w{ordinal + 1:02d}"
            clone["source_task_ordinal"] = ordinal
            clone["lane_ordinal"] = 0 if ordinal < 28 else 1
            clone["lane_id"] = "v12a" if ordinal < 28 else "v12b"
            clone["task_ordinal"] = ordinal if ordinal < 28 else ordinal - 28
            clones.append(clone)
        panel_index["accepted_slates"] = clones
    elif attack == "reorder":
        members[0], members[1] = members[1], members[0]
    else:
        members[-1] = deepcopy(members[0])
    _rehash_panel(panel_index)
    with pytest.raises(release.CorpusExtremeTailPanelReleaseError):
        release.build_t230_panel_execution_manifest_v1(
            panel_index=panel_index,
            panel_index_identity=_panel_identity(panel_index),
            source_commit_sha=COMMIT,
            immutable_image=IMAGE,
            output_prefix=OUTPUT_PREFIX,
        )


@pytest.mark.parametrize("attack", ("clone", "reorder", "duplicate"))
def test_manifest_member_clone_reorder_and_duplicate_drift_fails_replay(
    attack: str,
) -> None:
    manifest, panel_index, panel_identity = _manifest()
    changed = deepcopy(manifest)
    members = changed["source_members"]
    assert isinstance(members, list)
    if attack == "clone":
        members[-1] = deepcopy(members[0])
        members[-1]["source_ordinal"] = 53
    elif attack == "reorder":
        members[0], members[1] = members[1], members[0]
    else:
        members[-1] = deepcopy(members[0])
    _rehash_manifest(changed)
    with pytest.raises(
        release.CorpusExtremeTailPanelReleaseError,
        match="frozen-input replay",
    ):
        _validate(changed, panel_index, panel_identity)


def _drift_panel_identity(manifest: dict[str, object]) -> None:
    identity = manifest["panel_object_identity"]
    assert isinstance(identity, dict)
    identity["generation"] = "123456789"


def _drift_member_identity(manifest: dict[str, object]) -> None:
    members = manifest["source_members"]
    assert isinstance(members, list)
    members[3]["carrier_identity"] = _identity("carrier-splice", 88_888)


def _drift_member_hash(manifest: dict[str, object]) -> None:
    members = manifest["source_members"]
    assert isinstance(members, list)
    members[3]["panel_member_sha256"] = "d" * 64


@pytest.mark.parametrize(
    "mutator",
    (_drift_panel_identity, _drift_member_identity, _drift_member_hash),
)
def test_identity_and_member_hash_drift_fail_coherent_replay(
    mutator: Callable[[dict[str, object]], None],
) -> None:
    manifest, panel_index, panel_identity = _manifest()
    changed = deepcopy(manifest)
    mutator(changed)
    _rehash_manifest(changed)
    with pytest.raises(release.CorpusExtremeTailPanelReleaseError):
        _validate(changed, panel_index, panel_identity)


@pytest.mark.parametrize("field", ("result_uri", "acceptance_uri"))
def test_deterministic_member_uri_drift_fails_replay(field: str) -> None:
    manifest, panel_index, panel_identity = _manifest()
    changed = deepcopy(manifest)
    members = changed["source_members"]
    assert isinstance(members, list)
    members[7][field] = f"{OUTPUT_PREFIX}wrong/{field}.json"
    _rehash_manifest(changed)
    with pytest.raises(release.CorpusExtremeTailPanelReleaseError):
        _validate(changed, panel_index, panel_identity)


def _drift_dose(manifest: dict[str, object]) -> None:
    manifest["authoritative_generation_dose"]["visits_per_block"] = 199


def _drift_budget(manifest: dict[str, object]) -> None:
    manifest["t230_retrieval_contract"]["entry_budgets"] = [4, 14, 79]


def _drift_strategy_hash(manifest: dict[str, object]) -> None:
    hashes = manifest["t230_retrieval_contract"]["strategy_sha256_by_id"]
    hashes["coverage-ge-230-v1"] = "e" * 64


def _drift_implementation_hash(manifest: dict[str, object]) -> None:
    manifest["t230_retrieval_contract"][
        "selector_implementation_sha256"
    ] = "f" * 64


def _drift_fold_support(manifest: dict[str, object]) -> None:
    manifest["support_contract"]["fold_support"][
        "minimum_opportunity_world_count"
    ] = 99


def _drift_panel_support(manifest: dict[str, object]) -> None:
    manifest["support_contract"]["panel_support"]["fold_pass_minimum"] = 215


@pytest.mark.parametrize(
    "mutator",
    (
        _drift_dose,
        _drift_budget,
        _drift_strategy_hash,
        _drift_implementation_hash,
        _drift_fold_support,
        _drift_panel_support,
    ),
)
def test_dose_budget_strategy_implementation_and_support_drift_fail(
    mutator: Callable[[dict[str, Any]], None],
) -> None:
    manifest, panel_index, panel_identity = _manifest()
    changed = deepcopy(manifest)
    mutator(changed)
    _rehash_manifest(changed)
    with pytest.raises(release.CorpusExtremeTailPanelReleaseError):
        _validate(changed, panel_index, panel_identity)


@pytest.mark.parametrize("field", _MANIFEST_FALSE_FIELDS)
def test_every_manifest_authority_must_remain_literal_false(field: str) -> None:
    manifest, panel_index, panel_identity = _manifest()
    changed = deepcopy(manifest)
    changed[field] = True
    _rehash_manifest(changed)
    with pytest.raises(
        release.CorpusExtremeTailPanelReleaseError,
        match=f"{field} must be false",
    ):
        _validate(changed, panel_index, panel_identity)


def test_panel_self_hash_and_content_identity_fail_closed() -> None:
    panel_index, panel_identity = _build_panel()
    bad_hash = deepcopy(panel_index)
    bad_hash["panel_index_sha256"] = "0" * 64
    with pytest.raises(
        release.CorpusExtremeTailPanelReleaseError, match="self-hash"
    ):
        release.build_t230_panel_execution_manifest_v1(
            panel_index=bad_hash,
            panel_index_identity=panel_identity,
            source_commit_sha=COMMIT,
            immutable_image=IMAGE,
            output_prefix=OUTPUT_PREFIX,
        )
    bad_identity = deepcopy(panel_identity)
    bad_identity["sha256"] = "1" * 64
    with pytest.raises(
        release.CorpusExtremeTailPanelReleaseError,
        match="generation-pinned identity",
    ):
        release.build_t230_panel_execution_manifest_v1(
            panel_index=panel_index,
            panel_index_identity=bad_identity,
            source_commit_sha=COMMIT,
            immutable_image=IMAGE,
            output_prefix=OUTPUT_PREFIX,
        )


@pytest.mark.parametrize(
    ("argument", "value"),
    (
        ("source_commit_sha", "a" * 39),
        ("immutable_image", {"uri": IMAGE["uri"], "digest": "sha256:" + "0" * 64}),
        ("output_prefix", "gs://fixture-bucket/not-a-prefix"),
        ("output_prefix", "gs://fixture-bucket/bad//prefix/"),
        ("output_prefix", "gs://fixture-bucket/bad/../prefix/"),
    ),
)
def test_noncanonical_commit_image_and_output_prefix_are_rejected(
    argument: str, value: object
) -> None:
    panel_index, panel_identity = _build_panel()
    arguments: dict[str, object] = {
        "panel_index": panel_index,
        "panel_index_identity": panel_identity,
        "source_commit_sha": COMMIT,
        "immutable_image": IMAGE,
        "output_prefix": OUTPUT_PREFIX,
    }
    arguments[argument] = value
    with pytest.raises(release.CorpusExtremeTailPanelReleaseError):
        release.build_t230_panel_execution_manifest_v1(
            **arguments  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("argument", "value"),
    (
        ("source_commit_sha", "c" * 40),
        (
            "immutable_image",
            {
                "uri": "example/research/t230@sha256:" + "d" * 64,
                "digest": "sha256:" + "d" * 64,
            },
        ),
        ("output_prefix", "gs://fixture-bucket/research/t230/run-002/"),
    ),
)
def test_preparation_input_drift_after_freeze_fails_replay(
    argument: str, value: object
) -> None:
    manifest, panel_index, panel_identity = _manifest()
    with pytest.raises(release.CorpusExtremeTailPanelReleaseError):
        _validate(
            manifest,
            panel_index,
            panel_identity,
            **{argument: value},
        )


def test_unknown_manifest_field_fails_even_with_a_valid_self_hash() -> None:
    manifest, panel_index, panel_identity = _manifest()
    changed = deepcopy(manifest)
    changed["caller_override"] = False
    _rehash_manifest(changed)
    with pytest.raises(
        release.CorpusExtremeTailPanelReleaseError, match="fields differ"
    ):
        _validate(changed, panel_index, panel_identity)
