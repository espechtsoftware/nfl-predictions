"""Hermetic adversaries for the terminal-first current-bank score bridge."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_contract_v1 as contract
from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_realized_bridge_v1 as bridge

_PREFIX = contract.OUTPUT_NAMESPACE + "synthetic-realized-bridge/"
_OUTCOME_PREFIX = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-full-union-attributions/synthetic-realized-bridge"
)


def _raw(value: object) -> bytes:
    return batch.canonical_json_bytes(value)


def _rehash(value: dict[str, object], field: str) -> None:
    value.pop(field, None)
    value[field] = batch.canonical_sha256(value)


def _identity(uri: str, value: object, generation: str = "1") -> dict[str, object]:
    raw = _raw(value)
    return {"uri": uri, "generation": generation,
            "sha256": sha256(raw).hexdigest(), "bytes": len(raw)}


def _fake_identity(uri: str, label: str) -> dict[str, object]:
    return {"uri": uri, "generation": "1", "sha256": sha256(label.encode()).hexdigest(),
            "bytes": len(label.encode()) or 1}


def _process_specs() -> list[dict[str, object]]:
    result = []
    for role in contract.PROCESS_ROLES:
        components = (("artifact-broker", "matrix-selector")
                      if role.endswith("fold-selector") else ("main",))
        result.append({"process_role": role, "process_chain": [{
            "component_role": component,
            "command": ["python", f"scripts/{role}-{component}.py"],
            "entrypoint_path": f"scripts/{role}-{component}.py",
            "entrypoint_sha256": sha256(f"{role}:{component}".encode()).hexdigest(),
        } for component in components]})
    return result


def _persisted_score_shard() -> dict[str, object]:
    score_module = bridge.score_authority
    lineup_rows = []
    maximum = 179_000_000
    for index in range(80):
        lineup_id = f"persisted-lineup-{index:03d}"
        roster = [f"player-{index:03d}-{slot}" for slot in range(9)]
        score = 100_000_000 + index * 1_000_000
        lineup_rows.append({
            "source_ordinal": 0, "slate_id": "2023-w01",
            "union_index": index, "lineup_id": lineup_id,
            "roster_player_ids": roster,
            "roster_identity_sha256": batch.canonical_sha256(roster),
            "realized_score_micro": score,
            "realized_union_rank": 79 - index,
            "realized_score_tie_count": 1,
            "union_maximum_score_micro": maximum,
            "regret_to_union_maximum_micro": maximum - score,
            "at_or_above_thresholds_dk": [
                threshold for threshold in score_module.THRESHOLDS_DK
                if score >= threshold * score_module.MICRO_DK_PER_POINT
            ],
            "training_origin_blocks": ["R0"],
            "training_source_arms": ["incumbent"],
            "training_occurrence_counts_by_block": {"R0": 1},
            "training_source_arms_by_block": {"R0": ["incumbent"]},
            "training_occurrence_count": 1,
            "source_arm_count": 1, "origin_block_count": 1,
            "multi_arm_origin": False, "multi_block_origin": False,
            "selected_book_count": 0, "selected_scope_count": 0,
            "selected_strategy_count": 0, "selected_any": False,
            "missed_by_every_book": True,
        })
    scope_rows = [{"ordinal": index} for index in range(6 * 80)]
    book_rows = [{"ordinal": index} for index in range(48)]
    selection_rows = [{"ordinal": index} for index in range(48 * 80)]
    body = {
        "schema_version": score_module.SLATE_ATTRIBUTION_SCHEMA,
        "source_ordinal": 0, "slate_id": "2023-w01",
        "panel_freeze_identity": dict(contract.PANEL_IDENTITY),
        "slate_freeze_identity": _fake_identity("gs://synthetic/slate.json", "slate"),
        "task_result_identity": _fake_identity("gs://synthetic/task.json", "task"),
        "task_result_sha256": "1" * 64,
        "slate_grade_identity": _fake_identity("gs://synthetic/grade.json", "grade"),
        "slate_grade_sha256": "2" * 64,
        "candidate_provenance_sha256": "3" * 64,
        "candidate_provenance_resolution": "arm-block-count-summary-only",
        "exact_generation_occurrence_rows_available": False,
        "player_realized_contributions_available": False,
        "point_in_time_player_traits_attached": False,
        "thresholds_dk": list(score_module.THRESHOLDS_DK),
        "realized_union_rank_law": (
            "zero-based-score-desc-lineup-id-ascending-tiebreak-not-contest-rank"
        ),
        "selector_regret_law": (
            "realized-eligible-maximum-minus-selected-maximum-descriptive-only"
        ),
        "lineup_count": len(lineup_rows), "lineup_rows": lineup_rows,
        "lineup_rows_sha256": batch.canonical_sha256(lineup_rows),
        "scope_membership_count": len(scope_rows),
        "scope_membership_rows": scope_rows,
        "scope_membership_rows_sha256": batch.canonical_sha256(scope_rows),
        "book_count": len(book_rows), "book_rows": book_rows,
        "book_rows_sha256": batch.canonical_sha256(book_rows),
        "selection_count": len(selection_rows), "selection_rows": selection_rows,
        "selection_rows_sha256": batch.canonical_sha256(selection_rows),
        "contest_metrics": {"availability": "unavailable", "reason": (
            "full_field_standings_duplicate_tie_settlement_and_"
            "payout_ladder_not_supplied"
        ), "rank": None, "roi_micro_usd": None},
        "fill_effect_interpretation": "descriptive-only-pooled-multi-arm",
        "uses_realized_outcomes": True, "no_rescore": True,
        "projected_from_persisted_union_score_lookup": True, "complete": True,
        **{field: False for field in score_module._SHARD_FALSE_FIELDS},
    }
    _rehash(body, "slate_attribution_sha256")
    return body


def _persisted_score_root() -> dict[str, object]:
    score_module = bridge.score_authority
    prefix = score_module.OUTPUT_NAMESPACE + "synthetic-score-authority"
    descriptors = []
    for source in range(54):
        slate_id = f"2023-w{source + 1:02d}"
        uri = f"{prefix}/slate-attributions/{source:02d}-{slate_id}.json"
        row = {
            "schema_version": score_module.ATTRIBUTION_DESCRIPTOR_SCHEMA,
            "source_ordinal": source, "slate_id": slate_id, "target_uri": uri,
            "slate_attribution_identity": _fake_identity(uri, f"shard:{source}"),
            "slate_attribution_sha256": sha256(f"body:{source}".encode()).hexdigest(),
            "slate_freeze_identity": _fake_identity(
                f"gs://synthetic/slate-{source}.json", f"slate:{source}"
            ),
            "task_result_identity": _fake_identity(
                f"gs://synthetic/task-{source}.json", f"task:{source}"
            ),
            "task_result_sha256": sha256(f"task-body:{source}".encode()).hexdigest(),
            "slate_grade_identity": _fake_identity(
                f"gs://synthetic/grade-{source}.json", f"grade:{source}"
            ),
            "slate_grade_sha256": sha256(f"grade-body:{source}".encode()).hexdigest(),
            "lineup_count": 80, "scope_membership_count": 480,
            "book_count": 48, "selection_count": 3840,
        }
        _rehash(row, "slate_attribution_object_sha256")
        descriptors.append(row)
    body = {
        "schema_version": score_module.ATTRIBUTION_RELEASE_SCHEMA,
        "publication_mode": score_module.PUBLICATION_MODE,
        "target_uri": f"{prefix}/attribution-release.json",
        "run_id": "synthetic-score-authority",
        "grade_completion_identity": _fake_identity(
            "gs://synthetic/completion.json", "completion"
        ),
        "persisted_grade_root_identity": _fake_identity(
            "gs://synthetic/grade-root.json", "grade-root"
        ),
        "panel_freeze_identity": dict(contract.PANEL_IDENTITY),
        "panel_freeze_sha256": contract.PANEL_SELF_SHA256,
        "source_slate_count": 54,
        "slate_attribution_objects": descriptors,
        "slate_attribution_objects_sha256": batch.canonical_sha256(descriptors),
        "lineup_count": 54 * 80, "scope_membership_count": 54 * 480,
        "book_count": 54 * 48, "selection_count": 54 * 3840,
        "reads_freeze_and_grade_artifacts_only": True,
        "uses_realized_outcomes": True, "no_rescore": True, "complete": True,
        "all_shard_identities_resolved_before_root_build": True,
        "every_shard_exact_reopened_and_predecessor_replayed": True,
        "root_create_once_requested_last": True,
        **{field: False for field in score_module._ROOT_FALSE_FIELDS},
    }
    _rehash(body, "attribution_release_sha256")
    return body


class _Store:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str, str, int], bytes] = {}
        self.calls: list[dict[str, object]] = []

    @staticmethod
    def key(value: object) -> tuple[str, str, str, int]:
        row = dict(value)  # type: ignore[arg-type]
        return (str(row["uri"]), str(row["generation"]),
                str(row["sha256"]), int(row["bytes"]))

    def put(self, identity: object, value: object) -> None:
        self.values[self.key(identity)] = _raw(value)

    def read_exact(self, identity: object) -> bytes:
        row = dict(identity)  # type: ignore[arg-type]
        self.calls.append(row)
        return self.values[self.key(row)]


def test_pure_score_authority_adapter_accepts_exact_root_and_rows():
    root = _persisted_score_root()
    shard = _persisted_score_shard()
    assert (
        bridge.score_authority.validate_attribution_release_score_authority_v1(root)
        == root
    )
    assert bridge.score_authority.validate_slate_score_row_authority_v1(shard) == shard
    bad_root = deepcopy(root)
    bad_root["lineup_rescore_performed"] = True
    _rehash(bad_root, "attribution_release_sha256")
    with pytest.raises(
        bridge.score_authority.CorpusR6CurrentBankRealizedScoreAuthorityAdapterV1Error,
        match="no-rescore authority",
    ):
        bridge.score_authority.validate_attribution_release_score_authority_v1(bad_root)
    bad_shard = deepcopy(shard)
    bad_shard["lineup_rows"][0]["realized_score_micro"] += 1
    bad_shard["lineup_rows_sha256"] = batch.canonical_sha256(bad_shard["lineup_rows"])
    _rehash(bad_shard, "slate_attribution_sha256")
    with pytest.raises(
        bridge.score_authority.CorpusR6CurrentBankRealizedScoreAuthorityAdapterV1Error,
        match="rank/regret",
    ):
        bridge.score_authority.validate_slate_score_row_authority_v1(bad_shard)


def _finalist_rows() -> list[dict[str, object]]:
    strategy = {sid: ordinal for ordinal, sid, _ in contract.STRATEGY_IDENTITIES}
    return [
        {"view_id": "U", "profile_id": "all-profiles", "profile_ordinal": -1,
         "strategy_id": "coverage-194-v1", "strategy_ordinal": strategy["coverage-194-v1"],
         "prefix_size": 80, "roles": ["mandatory-current-union-control"],
         "passes_simulated_p200_noninferiority": None},
        {"view_id": "U", "profile_id": "all-profiles", "profile_ordinal": -1,
         "strategy_id": "tail-ladder-200-210-220-v1",
         "strategy_ordinal": strategy["tail-ladder-200-210-220-v1"],
         "prefix_size": 80, "roles": ["mandatory-current-union-tail-control"],
         "passes_simulated_p200_noninferiority": None},
        {"view_id": contract.isolated_view_id_v1(0), "profile_id": "incumbent",
         "profile_ordinal": 0, "strategy_id": "coverage-194-v1",
         "strategy_ordinal": strategy["coverage-194-v1"], "prefix_size": 80,
         "roles": ["mandatory-legacy-profile-sentinel"],
         "passes_simulated_p200_noninferiority": None},
    ]


@pytest.fixture
def case(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    topology = contract.build_result_topology_v1(_PREFIX)
    topology_identity = _identity("gs://synthetic/authorities/topology.json", topology)
    run_identity = _fake_identity("gs://synthetic/authorities/run.json", "run")
    bootstrap = contract.build_bootstrap_manifest_v1(
        topology=topology, topology_identity=topology_identity,
        run_identity=run_identity, code_commit="a" * 40,
        image_digest="sha256:" + "b" * 64, process_specs=_process_specs())
    bootstrap_identity = _identity("gs://synthetic/authorities/bootstrap.json", bootstrap)
    design = contract.build_design_v1(
        output_prefix=_PREFIX,
        code_identity=_fake_identity("gs://synthetic/code.py", "code"),
        report_identity=_fake_identity("gs://synthetic/report.md", "report"),
        topology_identity=topology_identity, bootstrap_manifest=bootstrap,
        bootstrap_manifest_identity=bootstrap_identity)
    design_identity = _identity(f"{_PREFIX}design.json", design)
    slates = [f"synthetic-2024-w{source + 1:02d}" for source in range(54)]
    selected_ids = [f"lineup-{index:03d}" for index in range(80)]

    def descriptors(role: str) -> list[dict[str, object]]:
        return [row for row in topology["objects"] if row["role"] == role]

    projection_ids = [_fake_identity(str(row["uri"]), f"p:{i}")
                      for i, row in enumerate(descriptors("projection"))]
    selection_desc = descriptors("confirmation-selection-receipt")
    evaluation_desc = descriptors("confirmation-evaluation-result")
    selections, selection_ids, evaluations, evaluation_ids = [], [], [], []
    for source in range(54):
        selection = {"source_ordinal": source, "slate_id": slates[source],
                     "selection_receipt_sha256": sha256(f"s:{source}".encode()).hexdigest()}
        selection_identity = _identity(str(selection_desc[source]["uri"]), selection)
        evaluation = {"source_ordinal": source, "slate_id": slates[source],
                      "selection_receipt_identity": selection_identity}
        evaluation_identity = _identity(str(evaluation_desc[source]["uri"]), evaluation)
        selections.append(selection); selection_ids.append(selection_identity)
        evaluations.append(evaluation); evaluation_ids.append(evaluation_identity)
    selection_entries = [{"source_ordinal": i, "slate_id": slates[i],
                          "identity": selection_ids[i]} for i in range(54)]
    evaluation_entries = [{"source_ordinal": i, "slate_id": slates[i],
                           "identity": evaluation_ids[i]} for i in range(54)]
    broad_exec = {"logical_fold_selection_count": 270, "selector_os_process_count": 540,
                  "child_execution_evidence_sha256s_sha256": "1" * 64}
    confirm_exec = {"logical_fold_selection_count": 270, "selector_os_process_count": 540,
                    "child_execution_evidence_sha256s_sha256": "2" * 64}
    aggregate = {
        "design_publication_identity": design_identity, "design_sha256": design["design_sha256"],
        "topology": topology, "topology_identity": topology_identity,
        "aggregate_mechanics_sha256": "3" * 64,
        "confirmation_selection_layer": {"entries": selection_entries},
        "confirmation_evaluation_layer": {"entries": evaluation_entries},
        "broad_phase_execution_authority": broad_exec,
        "confirmation_phase_execution_authority": confirm_exec,
    }
    aggregate_identity = _identity(f"{_PREFIX}aggregate.json", aggregate)
    finalist_function = {"finalists": _finalist_rows(), "finalist_function_sha256": "4" * 64}
    finalist = {"finalists": finalist_function, "finalist_publication_sha256": "5" * 64}
    finalist_identity = _identity(f"{_PREFIX}confirmed-finalists.json", finalist)

    monkeypatch.setattr(contract, "validate_aggregate_mechanics_authority_v1",
        lambda value, publication_identity: aggregate)
    monkeypatch.setattr(contract, "validate_finalist_publication_authority_v1",
        lambda value, publication_identity, aggregate, aggregate_publication_identity: finalist)

    def selection_validator(value: object, *, identity: object, source_ordinal: int,
                            expected_uri: str, expected_projection_identity: object,
                            expected_topology_identity: object, **authority: object):
        assert value == selections[source_ordinal]
        assert identity == selection_ids[source_ordinal]
        assert expected_uri == selection_desc[source_ordinal]["uri"]
        assert expected_projection_identity == projection_ids[source_ordinal]
        assert expected_topology_identity == topology_identity
        assert authority["expected_bootstrap_identity"] == bootstrap_identity
        assert authority["expected_launch_identity"] == bootstrap["run_identity"]
        retained = dict(value)
        retained["fold_receipt_sha256s"] = [
            sha256(f"fold:{source_ordinal}:{fold}".encode()).hexdigest() for fold in range(5)]
        return retained, [[] for _ in range(5)]

    finalists = bridge._finalist_registry_v1(finalist_function["finalists"])

    def evaluation_cross(**kwargs: object):
        source = int(kwargs["source_ordinal"])
        selection = kwargs["selection"]
        return {(str(row["view_id"]), str(row["strategy_id"]), fold, replicate): {
            "selection_receipt_identity": selection_ids[source],
            "selection_receipt_sha256": selection["selection_receipt_sha256"],
            "selection_fold_receipt_sha256": selection["fold_receipt_sha256s"][fold],
            "selection_cell_sha256": sha256(
                f"cell:{source}:{fold}:{replicate}:{row['view_id']}:{row['strategy_id']}".encode()).hexdigest(),
            "selected_lineup_ids": selected_ids,
            "selected_lineup_ids_sha256": batch.canonical_sha256(selected_ids),
            "evaluation_identity": evaluation_ids[source],
            "evaluation_result_sha256": sha256(f"e:{source}".encode()).hexdigest(),
        } for row in finalists for fold in range(5) for replicate in range(32)}

    monkeypatch.setattr(bridge, "_validate_selection_receipt_v1", selection_validator)
    monkeypatch.setattr(bridge, "_cross_evaluation_v1", evaluation_cross)
    role_ids = {
        "design": [design_identity], "projection": projection_ids,
        "broad-selection-receipt": [_fake_identity(str(row["uri"]), f"bs:{i}")
                                    for i, row in enumerate(descriptors("broad-selection-receipt"))],
        "broad-evaluation-result": [_fake_identity(str(row["uri"]), f"be:{i}")
                                    for i, row in enumerate(descriptors("broad-evaluation-result"))],
        "nomination": [_fake_identity(str(descriptors("nomination")[0]["uri"]), "n")],
        "confirmation-selection-receipt": selection_ids,
        "confirmation-evaluation-result": evaluation_ids,
        "aggregate": [aggregate_identity], "confirmed-finalists": [finalist_identity],
    }
    offsets = {role: 0 for role in role_ids}
    predecessors = []
    for descriptor in topology["objects"][:-1]:
        role = str(descriptor["role"]); identity = role_ids[role][offsets[role]]
        offsets[role] += 1
        predecessors.append({"ordinal": descriptor["ordinal"], "role": role, "identity": identity})
    root = {
        "schema_version": contract.ROOT_SCHEMA, "contract_id": contract.CONTRACT_ID,
        "design_publication_identity": design_identity, "topology_sha256": topology["topology_sha256"],
        "aggregate_publication_identity": aggregate_identity,
        "aggregate_mechanics_sha256": "3" * 64,
        "finalist_publication_identity": finalist_identity,
        "finalist_publication_sha256": "5" * 64,
        "broad_logical_fold_selection_count": 270, "broad_selector_os_process_count": 540,
        "confirmation_logical_fold_selection_count": 270,
        "confirmation_selector_os_process_count": 540,
        "broad_child_execution_evidence_ledger_sha256": "1" * 64,
        "confirmation_child_execution_evidence_ledger_sha256": "2" * 64,
        "predecessor_count": 274, "predecessors": predecessors,
        "predecessors_sha256": batch.canonical_sha256(predecessors),
        "predecessor_opener_call_count": 274, "retained_full_evaluation_body_count": 0,
        "retained_compact_evaluation_record_count": 108,
        "retained_compact_evaluation_state_bytes": 1000,
        "streaming_body_list_accepted": False,
        "terminal_reconstruction_law": "stream-exact-ordinal-reduce-evaluations-rebuild-aggregate-finalist",
        "publication_order_law": "strict-ordinal-create-once-root-last",
        "policy": dict(contract.POLICY_CLAIMS),
    }
    _rehash(root, "root_sha256")
    root_identity = _identity(f"{_PREFIX}root.json", root)
    terminal_store = _Store()
    for identity, body in [(root_identity, root), (design_identity, design),
                           (aggregate_identity, aggregate), (finalist_identity, finalist),
                           *zip(selection_ids, selections, strict=True),
                           *zip(evaluation_ids, evaluations, strict=True)]:
        terminal_store.put(identity, body)

    shards, shard_ids, outcome_descriptors = [], [], []
    for source, slate_id in enumerate(slates):
        shard = {"source_ordinal": source, "slate_id": slate_id,
                 "panel_freeze_identity": dict(contract.PANEL_IDENTITY),
                 "slate_attribution_sha256": sha256(f"shard:{source}".encode()).hexdigest(),
                 "lineup_rows": [{"lineup_id": lineup_id,
                    "realized_score_micro": 150_000_000 + index * 1_000_000 + source}
                    for index, lineup_id in enumerate(selected_ids)]}
        shard["lineup_rows_sha256"] = batch.canonical_sha256(shard["lineup_rows"])
        uri = f"{_OUTCOME_PREFIX}/slate-attributions/{source:02d}-{slate_id}.json"
        sid = _identity(uri, shard, str(source + 1))
        shards.append(shard); shard_ids.append(sid)
        outcome_descriptors.append({"source_ordinal": source, "slate_id": slate_id,
            "slate_attribution_identity": sid,
            "slate_attribution_sha256": shard["slate_attribution_sha256"]})
    outcome_root = {"target_uri": f"{_OUTCOME_PREFIX}/attribution-release.json",
        "grade_completion_identity": _fake_identity(
            f"{_OUTCOME_PREFIX}/grade-completion.json", "grade-completion"
        ),
        "persisted_grade_root_identity": _fake_identity(
            f"{_OUTCOME_PREFIX}/persisted-grade-root.json", "persisted-grade-root"
        ),
        "panel_freeze_identity": dict(contract.PANEL_IDENTITY),
        "panel_freeze_sha256": contract.PANEL_SELF_SHA256,
        "slate_attribution_objects": outcome_descriptors,
        "attribution_release_sha256": "6" * 64}
    outcome_identity = _identity(str(outcome_root["target_uri"]), outcome_root, "55")
    monkeypatch.setattr(bridge.score_authority, "validate_attribution_release_score_authority_v1",
                        lambda value: value)
    monkeypatch.setattr(bridge.score_authority, "validate_slate_score_row_authority_v1",
                        lambda value: value)
    outcome_store = _Store(); outcome_store.put(outcome_identity, outcome_root)
    outcome_store.put(shard_ids[0], shards[0])
    return locals()


def test_smoke_opens_all_terminal_pairs_before_outcome_and_never_rescores(case):
    report = bridge.build_realized_score_bridge_v1(
        terminal_root_identity=case["root_identity"],
        outcome_authority_identity=case["outcome_identity"],
        mode=bridge.MODE_ONE_SLATE_SMOKE,
        read_terminal_exact=case["terminal_store"].read_exact,
        read_outcome_exact=case["outcome_store"].read_exact)
    assert len(case["terminal_store"].calls) == 112
    assert len(case["outcome_store"].calls) == 2
    assert report["terminal_confirmation_pair_count"] == 54
    assert report["terminal_proof_complete_before_outcome_open"] is True
    assert report["lineup_rescore_performed"] is False
    assert report["final_all_block_fit_book_absent"] is True
    first_slate = report["strategy_results"][0]["book_paths"][0]["slates"][0]
    assert first_slate["no_rescore_score_authority_identity"] == case["shard_ids"][0]
    assert first_slate["no_rescore_lineup_rows_sha256"] == case["shards"][0][
        "lineup_rows_sha256"
    ]
    assert all(row["confirmation_path_count"] == 160
               and not row["path_mean_distribution"]["headline_path_selected"]
               and row["slate_cluster_bootstrap_95_ci"] is None
               for row in report["strategy_results"])


def test_terminal_failure_makes_zero_outcome_calls(case):
    root = deepcopy(case["root"]); root["predecessors"][0]["role"] = "projection"
    root["predecessors_sha256"] = batch.canonical_sha256(root["predecessors"])
    _rehash(root, "root_sha256")
    identity = _identity(str(case["root_identity"]["uri"]), root, "999")
    store = _Store()
    store.values.update(case["terminal_store"].values)
    store.put(identity, root)
    outcome_calls = []
    def forbidden(value): outcome_calls.append(value); raise AssertionError("early outcome")
    with pytest.raises(bridge.CorpusR6CurrentBankRealizedBridgeV1Error):
        bridge.build_realized_score_bridge_v1(
            terminal_root_identity=identity, outcome_authority_identity=case["outcome_identity"],
            mode=bridge.MODE_ONE_SLATE_SMOKE, read_terminal_exact=store.read_exact,
            read_outcome_exact=forbidden)
    assert outcome_calls == []


def _cell(
    selected: list[str],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    strategy = contract.frozen_strategies_v1()[0]; sampled = sorted(selected)
    ledger_rows = [{"lineup_id": lid, "score_row_sha256": sha256(lid.encode()).hexdigest()}
                   for lid in sampled]
    full_ledger = {"dtype": "float64-le", "world_count": 40_000, "row_count": len(sampled),
        "lineup_ids_sha256": batch.canonical_sha256(sampled), "rows": ledger_rows,
        "rows_sha256": batch.canonical_sha256(ledger_rows),
        "score_matrix_shape": [len(sampled), 40_000], "score_matrix_sha256": "7" * 64}
    ledger = {"dtype": "float64-le", "world_count": 40_000, "row_count": len(sampled),
        "lineup_ids_sha256": batch.canonical_sha256(sampled), "rows": ledger_rows,
        "rows_sha256": batch.canonical_sha256(ledger_rows),
        "source_full_rows_sha256": full_ledger["rows_sha256"],
        "source_full_score_matrix_sha256": full_ledger["score_matrix_sha256"]}
    roster_sha = "8" * 64
    prefixes = [{"prefix_size": size,
        "selected_lineup_ids_sha256": batch.canonical_sha256(selected[:size]),
        "selected_rosters_sha256": roster_sha,
        "prefix_payload_sha256": sha256(f"prefix:{size}".encode()).hexdigest()}
        for size in contract.PREFIX_SIZES]
    ordinal = {lid: i for i, lid in enumerate(sampled)}
    trace = [{"selection_ordinal": i, "lineup_id": lid,
              "sampled_lineup_ordinal": ordinal[lid],
              "score_row_sha256": ledger_rows[ordinal[lid]]["score_row_sha256"]}
             for i, lid in enumerate(selected)]
    body = {"replicate": 0, "view_id": "U", "sampled_lineup_ids": sampled,
        "sampled_lineup_ids_sha256": batch.canonical_sha256(sampled),
        "rank_seed_sha256": "9" * 64, "strategy_ordinal": strategy["ordinal"],
        "strategy_id": strategy["strategy_id"], "strategy_sha256": strategy["strategy_sha256"],
        "executable_fingerprint_sha256": contract.strategy_executable_fingerprint_v1(strategy),
        "training_score_row_ledger": ledger, "selected_lineup_ids": selected,
        "selected_lineup_ids_sha256": batch.canonical_sha256(selected),
        "selected_rosters_sha256": roster_sha, "prefixes": prefixes,
        "selection_trace": trace, "selection_trace_sha256": batch.canonical_sha256(trace)}
    _rehash(body, "selection_cell_sha256")
    return body, strategy, full_ledger


def test_cell_rejects_duplicate_and_outside_frozen_candidate():
    selected = [f"lineup-{i:03d}" for i in range(80)]
    valid, strategy, full_ledger = _cell(selected)
    assert bridge._validate_cell_v1(valid, expected_replicate=0,
        expected_strategy_by_id={str(strategy["strategy_id"]): strategy},
        expected_full_score_row_ledger=full_ledger) == valid
    for replacement in (selected[0], "outside-frozen-confirmation"):
        changed = deepcopy(valid); changed["selected_lineup_ids"][-1] = replacement
        changed["selected_lineup_ids_sha256"] = batch.canonical_sha256(changed["selected_lineup_ids"])
        _rehash(changed, "selection_cell_sha256")
        with pytest.raises(bridge.CorpusR6CurrentBankRealizedBridgeV1Error,
                           match="missing/extra/duplicate/outside"):
            bridge._validate_cell_v1(changed, expected_replicate=0,
                expected_strategy_by_id={str(strategy["strategy_id"]): strategy},
                expected_full_score_row_ledger=full_ledger)
    extra, extra_strategy, extra_full = _cell(
        [f"lineup-{i:03d}" for i in range(81)]
    )
    with pytest.raises(bridge.CorpusR6CurrentBankRealizedBridgeV1Error,
                       match="missing/extra/duplicate/outside"):
        bridge._validate_cell_v1(
            extra, expected_replicate=0,
            expected_strategy_by_id={str(extra_strategy["strategy_id"]): extra_strategy},
            expected_full_score_row_ledger=extra_full,
        )


def test_cell_rejects_re_self_hashed_score_row_trace_relabel():
    selected = [f"lineup-{i:03d}" for i in range(80)]
    valid, strategy, full_ledger = _cell(selected)
    changed = deepcopy(valid)
    changed["selection_trace"][0]["score_row_sha256"] = "a" * 64
    changed["selection_trace_sha256"] = batch.canonical_sha256(
        changed["selection_trace"]
    )
    _rehash(changed, "selection_cell_sha256")
    with pytest.raises(bridge.CorpusR6CurrentBankRealizedBridgeV1Error,
                       match="selection trace differs"):
        bridge._validate_cell_v1(
            changed, expected_replicate=0,
            expected_strategy_by_id={str(strategy["strategy_id"]): strategy},
            expected_full_score_row_ledger=full_ledger,
        )


def test_full_54_summary_keeps_all_paths_and_emits_distribution_ci(case):
    terminal = bridge.reopen_terminal_confirmation_books_v1(
        terminal_root_identity=case["root_identity"],
        read_terminal_exact=case["terminal_store"].read_exact)
    scored = {source: {
        "identity": case["shard_ids"][source],
        "slate_attribution_sha256": case["shards"][source]["slate_attribution_sha256"],
        "lineup_rows_sha256": batch.canonical_sha256(case["shards"][source]["lineup_rows"]),
        "scores": {lid: 150_000_000 + i * 1_000_000 + source
                   for i, lid in enumerate(case["selected_ids"])}
    } for source in range(54)}
    result = bridge._score_strategy_paths_v1(
        finalist=terminal["finalists"][0], terminal=terminal, scored_slates=scored,
        mode=bridge.MODE_FULL_PANEL, outcome_identity=case["outcome_identity"],
        outcome_root_sha256=case["outcome_root"]["attribution_release_sha256"])
    expected = sum(229_000_000 + source for source in range(54)) * 160
    assert result["scored_book_count"] == 160 * 54
    assert result["primary_mean_weekly_maximum_micro"] == {
        "numerator": expected, "denominator": 160 * 54}
    assert result["strictly_gt_200_book_count"] == 160 * 54
    assert result["slate_cluster_bootstrap_95_ci"]["resample_count"] == 10_000
    assert result["path_mean_distribution"]["headline_path_selected"] is False


def test_wrong_outcome_panel_fails_before_shard(case, monkeypatch):
    bad = deepcopy(case["outcome_root"])
    bad["panel_freeze_identity"] = _fake_identity("gs://synthetic/wrong.json", "wrong")
    identity = _identity(str(case["outcome_identity"]["uri"]), bad, "998")
    store = _Store(); store.put(identity, bad)
    monkeypatch.setattr(
        bridge.score_authority,
        "validate_attribution_release_score_authority_v1",
        lambda value: value,
    )
    with pytest.raises(bridge.CorpusR6CurrentBankRealizedBridgeV1Error, match="corpus differs"):
        bridge.build_realized_score_bridge_v1(
            terminal_root_identity=case["root_identity"], outcome_authority_identity=identity,
            mode=bridge.MODE_ONE_SLATE_SMOKE,
            read_terminal_exact=case["terminal_store"].read_exact,
            read_outcome_exact=store.read_exact)
    assert len(store.calls) == 1


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate"])
def test_outcome_slate_lattice_rejects_missing_extra_duplicate(case, mutation):
    bad = deepcopy(case["outcome_root"])
    if mutation == "missing":
        bad["slate_attribution_objects"].pop()
    elif mutation == "extra":
        bad["slate_attribution_objects"].append(
            deepcopy(bad["slate_attribution_objects"][-1])
        )
    else:
        bad["slate_attribution_objects"][1]["slate_id"] = bad[
            "slate_attribution_objects"
        ][0]["slate_id"]
    identity = _identity(str(case["outcome_identity"]["uri"]), bad, "997")
    store = _Store(); store.put(identity, bad)
    with pytest.raises(bridge.CorpusR6CurrentBankRealizedBridgeV1Error,
                       match="slate lattice differs"):
        bridge.build_realized_score_bridge_v1(
            terminal_root_identity=case["root_identity"],
            outcome_authority_identity=identity,
            mode=bridge.MODE_ONE_SLATE_SMOKE,
            read_terminal_exact=case["terminal_store"].read_exact,
            read_outcome_exact=store.read_exact,
        )
    assert len(store.calls) == 1


@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_outcome_lineup_lattice_rejects_missing_or_duplicate(case, mutation):
    shard = deepcopy(case["shards"][0])
    if mutation == "missing":
        shard["lineup_rows"].pop()
    else:
        shard["lineup_rows"][-1]["lineup_id"] = shard["lineup_rows"][0]["lineup_id"]
    shard["lineup_rows_sha256"] = batch.canonical_sha256(shard["lineup_rows"])
    shard_identity = _identity(
        str(case["shard_ids"][0]["uri"]), shard, "996",
    )
    root = deepcopy(case["outcome_root"])
    root["slate_attribution_objects"][0]["slate_attribution_identity"] = shard_identity
    root_identity = _identity(str(case["outcome_identity"]["uri"]), root, "996")
    store = _Store(); store.put(root_identity, root); store.put(shard_identity, shard)
    message = "missing from no-rescore" if mutation == "missing" else "lineup repeats"
    with pytest.raises(bridge.CorpusR6CurrentBankRealizedBridgeV1Error, match=message):
        bridge.build_realized_score_bridge_v1(
            terminal_root_identity=case["root_identity"],
            outcome_authority_identity=root_identity,
            mode=bridge.MODE_ONE_SLATE_SMOKE,
            read_terminal_exact=case["terminal_store"].read_exact,
            read_outcome_exact=store.read_exact,
        )
    assert len(store.calls) == 2


def test_cli_import_is_clean_and_injected_boundary_runs(case):
    path = Path("scripts/run_corpus_r6_current_bank_crossed_screen_realized_bridge_v1.py")
    spec = importlib.util.spec_from_file_location("realized_bridge_cli_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    terminal, outcome = case["root_identity"], case["outcome_identity"]
    argv = ["--mode", bridge.MODE_ONE_SLATE_SMOKE,
        "--terminal-root-uri", str(terminal["uri"]),
        "--terminal-root-generation", str(terminal["generation"]),
        "--terminal-root-sha256", str(terminal["sha256"]),
        "--terminal-root-bytes", str(terminal["bytes"]),
        "--outcome-authority-uri", str(outcome["uri"]),
        "--outcome-authority-generation", str(outcome["generation"]),
        "--outcome-authority-sha256", str(outcome["sha256"]),
        "--outcome-authority-bytes", str(outcome["bytes"])]
    result = module.run_with_readers_v1(argv, terminal_reader=case["terminal_store"],
                                        outcome_reader=case["outcome_store"])
    assert result["schema_version"] == bridge.BRIDGE_SCHEMA


def test_cli_clean_subprocess_import_has_no_scorer_or_cloud_client():
    script = str(Path(
        "scripts/run_corpus_r6_current_bank_crossed_screen_realized_bridge_v1.py"
    ).resolve())
    code = (
        "import importlib.util,sys;"
        "p=sys.argv[1];"
        "s=importlib.util.spec_from_file_location('bridge_clean_import',p);"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        "forbidden=('corpus_r6_full_union_realized_grading_v1',"
        "'corpus_r6_full_union_outcome_snapshot_v1','google.cloud.storage');"
        "assert not any(any(x in name for x in forbidden) for name in sys.modules);"
        "print('clean')"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code, script], check=False,
        capture_output=True, text=True, timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "clean"
