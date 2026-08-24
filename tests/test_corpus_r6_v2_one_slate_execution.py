from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace

import numpy as np
import pytest

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_v2_one_slate_execution as execution
from nfl_dfs.research import corpus_v12_import as v12_import
from nfl_dfs.research import corpus_v12_panel_index as panel_index
from nfl_dfs.research import residual_world_columns as rw


SLATE_ID = "2023-w01"
SLATE = {"season": 2023, "week": 1, "slate_id": SLATE_ID}


def _raw(value: object) -> bytes:
    return batch.canonical_json_bytes(value)


def _identity(uri: str, raw: bytes) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _placeholder_identity(name: str) -> dict[str, object]:
    raw = name.encode("utf-8")
    return _identity(f"gs://fixture/{name}", raw)


def _self_hash(value: dict[str, object], field: str) -> dict[str, object]:
    result = dict(value)
    result[field] = batch.canonical_sha256(result)
    return result


def _membership(
    *,
    source_task_ordinal: int,
    acceptance_identity: dict[str, object],
    carrier_identity: dict[str, object],
) -> dict[str, object]:
    return {
        "slate_id": (
            SLATE_ID
            if source_task_ordinal == 0
            else f"2024-w{source_task_ordinal:02d}"
        ),
        "lane_ordinal": 0 if source_task_ordinal < 28 else 1,
        "lane_id": "v12a" if source_task_ordinal < 28 else "v12b",
        "task_ordinal": (
            source_task_ordinal
            if source_task_ordinal < 28 else source_task_ordinal - 28
        ),
        "source_task_ordinal": source_task_ordinal,
        "source_task_authority_sha256": f"{source_task_ordinal + 1:064x}",
        "task_acceptance_identity": acceptance_identity,
        "carrier_identity": carrier_identity,
        "arms": [
            {
                "arm_ordinal": ordinal,
                "parameter_set_id": arm_id,
                "result_identity": _placeholder_identity(
                    f"task-{source_task_ordinal}-arm-{ordinal}.json"
                ),
            }
            for ordinal, arm_id in enumerate(batch.PARAMETER_SET_ORDER)
        ],
    }


def _panel(
    target: dict[str, object], *, authoritative: bool
) -> dict[str, object]:
    accepted = [target]
    if authoritative:
        accepted.extend(
            _membership(
                source_task_ordinal=ordinal,
                acceptance_identity=_placeholder_identity(
                    f"task-{ordinal}-acceptance.json"
                ),
                carrier_identity=_placeholder_identity(f"task-{ordinal}-carrier.json"),
            )
            for ordinal in range(1, panel_index.V12_SOURCE_TASK_COUNT)
        )
    count = len(accepted)
    body = {
        "schema_version": (
            panel_index.PANEL_INDEX_SCHEMA
            if authoritative else execution.FIXTURE_PANEL_SCHEMA
        ),
        "publication_mode": (
            panel_index.PUBLICATION_MODE
            if authoritative else execution.FIXTURE_PUBLICATION_MODE
        ),
        "panel_id": "v12:fixture",
        "accepted_slate_count": count,
        "accepted_slates": accepted,
        "exclusions": [],
        "failures": [],
        "missing_tasks": [],
        "coverage": {
            "expected_task_count": count,
            "accepted_task_count": count,
            "excluded_task_count": 0,
            "failed_task_count": 0,
            "missing_task_count": 0,
            "complete": True,
        },
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "corpus_fill_licensed": False,
        "graph_mutation_licensed": False,
        "live_policy_access_licensed": False,
        "production_change_licensed": False,
        "analytical_authority": False,
        "promotion_authority": False,
        "decision_authority": False,
    }
    return _self_hash(body, "panel_index_sha256")


def _fixture_inputs(*, authoritative_panel: bool = True) -> dict[str, object]:
    acceptance_raw = b"outcome-blind-task-acceptance"
    acceptance_identity = _identity(
        "gs://fixture/task/acceptance.json", acceptance_raw
    )
    source = {"freeze_sha256": "a" * 64}
    source_raw = _raw(source)
    source_identity = _identity("gs://fixture/source/freeze.json", source_raw)
    world_raw = {
        block: f"world-artifact-{block}".encode("utf-8")
        for block in rw.WORLD_BLOCKS
    }
    world_identities = {
        role: _identity(f"gs://fixture/worlds/{block}.npz", world_raw[block])
        for block, role in zip(
            rw.WORLD_BLOCKS, batch.TASK_WORLD_SOURCE_ROLES, strict=True
        )
    }
    sources = {"later_source_freeze": source_identity}
    carrier = {
        "schema_version": batch.TASK_RESULT_SCHEMA,
        "publication_mode": panel_index.PUBLICATION_MODE,
        "task_index": 0,
        "slate_id": SLATE_ID,
        "source_receipts": sources,
        "source_receipt_set_sha256": batch.canonical_sha256(sources),
        "later_source_freeze_manifest_sha256": source["freeze_sha256"],
        "world_artifact_receipts": world_identities,
        "world_artifact_receipt_set_sha256": batch.canonical_sha256(
            world_identities
        ),
    }
    carrier_raw = _raw(carrier)
    carrier_identity = _identity("gs://fixture/task/carrier.json", carrier_raw)
    target = _membership(
        source_task_ordinal=0,
        acceptance_identity=acceptance_identity,
        carrier_identity=carrier_identity,
    )
    panel = _panel(target, authoritative=authoritative_panel)
    panel_raw = _raw(panel)
    panel_identity = _identity("gs://fixture/panel/index.json", panel_raw)
    matchup = {
        "schema_version": runner.MATCHUP_SOURCE_SCHEMA,
        "slate": dict(SLATE),
        "uses_realized_outcomes": False,
    }
    matchup = _self_hash(matchup, "matchup_source_snapshot_sha256")
    matchup_raw = _raw(matchup)
    matchup_identity = _identity(
        "gs://fixture/matchups/source.json", matchup_raw
    )
    store = {
        acceptance_identity["uri"]: acceptance_raw,
        carrier_identity["uri"]: carrier_raw,
        source_identity["uri"]: source_raw,
        panel_identity["uri"]: panel_raw,
        matchup_identity["uri"]: matchup_raw,
        **{
            world_identities[role]["uri"]: world_raw[block]
            for block, role in zip(
                rw.WORLD_BLOCKS, batch.TASK_WORLD_SOURCE_ROLES, strict=True
            )
        },
    }
    return {
        "acceptance_identity": acceptance_identity,
        "carrier": carrier,
        "carrier_identity": carrier_identity,
        "target": target,
        "panel": panel,
        "panel_identity": panel_identity,
        "matchup": matchup,
        "matchup_identity": matchup_identity,
        "source_identity": source_identity,
        "world_identities": world_identities,
        "store": store,
    }


def _install_pipeline_stubs(
    monkeypatch,
    fixture: dict[str, object],
    *,
    authoritative: bool,
) -> list[str]:
    calls: list[str] = []
    compatibility_receipt = {
        "acceptance_receipt_identity": fixture["acceptance_identity"],
        "carrier_identity": fixture["carrier_identity"],
        "slate": dict(SLATE),
        "accepted_task_index": 0 if authoritative else None,
        "authoritative_task_acceptance_verified": authoritative,
        "accepted_task_result_binding_verified": True,
        "compatibility_import_sha256": "1" * 64,
    }
    imported = SimpleNamespace(
        compatibility_receipt=compatibility_receipt,
    )
    reconstructed = SimpleNamespace(
        provenance={
            "slate": dict(SLATE),
            "candidate_provenance_sha256": "2" * 64,
        },
        union_scores=np.zeros((1, 1), dtype=np.float64),
        reconstruction_receipt={
            "reconstruction_sha256": "3" * 64,
            "uses_realized_outcomes": False,
            "promotion_authority": False,
        },
    )

    def validate_matchup(body):
        calls.append("validate-matchup")
        return dict(body)

    def reopen(**kwargs):
        calls.append("reopen")
        assert kwargs["require_authoritative"] is authoritative
        return imported

    def reconstruct(value, **kwargs):
        calls.append("reconstruct")
        assert value is imported
        assert set(kwargs["artifact_bodies"]) == set(rw.WORLD_BLOCKS)
        return reconstructed

    def build_summary(**kwargs):
        calls.append("build-summary")
        return {
            "matchup_summary_sha256": "4" * 64,
            "uses_realized_outcomes": False,
        }

    def run_surface(**kwargs):
        calls.append("run-surface")
        assert kwargs["require_authoritative"] is authoritative
        return {
            "slate": dict(SLATE),
            "retrieval_surface_sha256": "5" * 64,
            "worlds_per_block": (
                rw.WORLDS_PER_BLOCK
                if kwargs["worlds_per_block"] is None
                else kwargs["worlds_per_block"]
            ),
            "admission_cap": kwargs["admission_m"],
            "dose_authority": (
                runner.AUTHORITATIVE_DOSE
                if authoritative else runner.FIXTURE_DOSE
            ),
            "require_authoritative": authoritative,
            "uses_realized_outcomes": False,
            "promotion_authority": False,
        }

    monkeypatch.setattr(runner, "validate_matchup_source_snapshot", validate_matchup)
    monkeypatch.setattr(v12_import, "reopen_v12_task", reopen)
    monkeypatch.setattr(v12_import, "reconstruct_v12_task", reconstruct)
    monkeypatch.setattr(runner, "build_matchup_lineup_summaries", build_summary)
    monkeypatch.setattr(runner, "run_retrieval_surface_v2", run_surface)
    return calls


def _execute(
    fixture: dict[str, object],
    *,
    require_authoritative: bool,
    **overrides,
) -> dict[str, object]:
    return execution.execute_one_slate_r6_v2(
        validated_panel_index=fixture["panel"],
        panel_index_identity=fixture["panel_identity"],
        accepted_slate_membership=fixture["target"],
        task_acceptance_identity=fixture["acceptance_identity"],
        carrier_identity=fixture["carrier_identity"],
        validated_matchup_source_snapshot=fixture["matchup"],
        matchup_source_snapshot_identity=fixture["matchup_identity"],
        read_exact=lambda identity: fixture["store"][identity["uri"]],
        require_authoritative=require_authoritative,
        **overrides,
    )


def test_authoritative_one_slate_orchestration_binds_every_input_and_output(
    monkeypatch,
) -> None:
    fixture = _fixture_inputs(authoritative_panel=True)
    calls = _install_pipeline_stubs(monkeypatch, fixture, authoritative=True)
    result = _execute(fixture, require_authoritative=True)

    assert calls == [
        "validate-matchup",
        "reopen",
        "reconstruct",
        "build-summary",
        "run-surface",
    ]
    assert result["execution_mode"] == (
        "authoritative-dose-one-slate-mechanics-smoke"
    )
    assert result["accepted_slate_membership"] == fixture["target"]
    assert result["later_source_freeze_identity"] == fixture["source_identity"]
    assert result["world_artifact_identities"] == fixture["world_identities"]
    assert result["output_hashes"] == {
        "compatibility_import_sha256": "1" * 64,
        "candidate_provenance_sha256": "2" * 64,
        "reconstruction_sha256": "3" * 64,
        "matchup_summary_sha256": "4" * 64,
        "retrieval_surface_sha256": "5" * 64,
    }
    assert result["matchup_evidence_class"] == (
        execution.MATCHUP_EVIDENCE_RETROSPECTIVE
    )
    assert result["matchup_mechanics_only"] is True
    assert "point_in_time_at_lock" not in result
    assert result["verification"]["canonical_authoritative_dose_verified"] is True
    for field in execution._FALSE_RESULT_AUTHORITY_FIELDS:
        assert result[field] is False
    retained = result["task_result_sha256"]
    assert retained == batch.canonical_sha256({
        key: value for key, value in result.items()
        if key != "task_result_sha256"
    })


def test_fixture_path_is_explicitly_non_authoritative(monkeypatch) -> None:
    fixture = _fixture_inputs(authoritative_panel=False)
    _install_pipeline_stubs(monkeypatch, fixture, authoritative=False)
    result = _execute(
        fixture,
        require_authoritative=False,
        admission_m=80,
        neutral_replicates=1,
        worlds_per_block=2,
    )
    assert result["execution_mode"] == "non-authoritative-fixture-mechanics"
    assert result["configuration"]["require_authoritative"] is False
    assert result["configuration"]["admission_m"] == 80
    assert result["configuration"]["worlds_per_block"] == 2
    assert result["verification"]["canonical_authoritative_dose_verified"] is False
    assert result["retrieval_surface"]["dose_authority"] == runner.FIXTURE_DOSE
    assert result["r6_freeze_authority"] is False
    assert result["promotion_authority"] is False


def test_authoritative_path_rejects_fixture_panel_before_import(monkeypatch) -> None:
    fixture = _fixture_inputs(authoritative_panel=False)
    calls = _install_pipeline_stubs(monkeypatch, fixture, authoritative=True)
    with pytest.raises(
        execution.CorpusR6V2OneSlateExecutionError,
        match="complete accepted v12 panel membership",
    ):
        _execute(fixture, require_authoritative=True)
    assert calls == []


def test_membership_identity_mismatch_fails_before_import(monkeypatch) -> None:
    fixture = _fixture_inputs(authoritative_panel=True)
    calls = _install_pipeline_stubs(monkeypatch, fixture, authoritative=True)
    with pytest.raises(
        execution.CorpusR6V2OneSlateExecutionError,
        match="task acceptance/carrier identities differ",
    ):
        execution.execute_one_slate_r6_v2(
            validated_panel_index=fixture["panel"],
            panel_index_identity=fixture["panel_identity"],
            accepted_slate_membership=fixture["target"],
            task_acceptance_identity=_placeholder_identity("wrong-acceptance.json"),
            carrier_identity=fixture["carrier_identity"],
            validated_matchup_source_snapshot=fixture["matchup"],
            matchup_source_snapshot_identity=fixture["matchup_identity"],
            read_exact=lambda identity: fixture["store"][identity["uri"]],
        )
    assert calls == []


def test_carrier_source_receipt_hash_drift_fails_closed(monkeypatch) -> None:
    fixture = _fixture_inputs(authoritative_panel=False)
    carrier = deepcopy(fixture["carrier"])
    carrier["source_receipt_set_sha256"] = "f" * 64
    carrier_raw = _raw(carrier)
    carrier_identity = _identity("gs://fixture/task/carrier-drift.json", carrier_raw)
    target = _membership(
        source_task_ordinal=0,
        acceptance_identity=fixture["acceptance_identity"],
        carrier_identity=carrier_identity,
    )
    panel = _panel(target, authoritative=False)
    panel_raw = _raw(panel)
    panel_identity = _identity("gs://fixture/panel/index-drift.json", panel_raw)
    fixture["carrier"] = carrier
    fixture["carrier_identity"] = carrier_identity
    fixture["target"] = target
    fixture["panel"] = panel
    fixture["panel_identity"] = panel_identity
    fixture["store"][carrier_identity["uri"]] = carrier_raw
    fixture["store"][panel_identity["uri"]] = panel_raw
    calls = _install_pipeline_stubs(monkeypatch, fixture, authoritative=False)

    with pytest.raises(
        execution.CorpusR6V2OneSlateExecutionError,
        match="carrier source receipt set hash differs",
    ):
        _execute(fixture, require_authoritative=False, admission_m=80, worlds_per_block=2)
    assert calls == []


def test_authoritative_dose_overrides_fail_before_any_exact_read() -> None:
    fixture = _fixture_inputs(authoritative_panel=True)
    reads: list[str] = []
    with pytest.raises(
        execution.CorpusR6V2OneSlateExecutionError,
        match="cannot override registered doses",
    ):
        execution.execute_one_slate_r6_v2(
            validated_panel_index=fixture["panel"],
            panel_index_identity=fixture["panel_identity"],
            accepted_slate_membership=fixture["target"],
            task_acceptance_identity=fixture["acceptance_identity"],
            carrier_identity=fixture["carrier_identity"],
            validated_matchup_source_snapshot=fixture["matchup"],
            matchup_source_snapshot_identity=fixture["matchup_identity"],
            read_exact=lambda identity: reads.append(str(identity["uri"])) or b"",
            admission_m=80,
            require_authoritative=True,
        )
    assert reads == []
