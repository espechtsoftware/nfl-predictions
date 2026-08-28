from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_evaluation_cloud_v1 as cloud,
)


def _identity(uri: str, tag: str) -> dict[str, object]:
    raw = tag.encode("utf-8")
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _body_identity(uri: str, value: object) -> dict[str, object]:
    raw = contract.canonical_json_bytes_v1(value)
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _prefix() -> str:
    return contract.OUTPUT_NAMESPACE + "fixture-successor-evaluation/"


@dataclass
class _Store:
    objects: dict[tuple[str, str], bytes]

    def __init__(self) -> None:
        self.objects = {}
        self.publications: list[str] = []

    def add(self, uri: str, value: object) -> dict[str, object]:
        raw = contract.canonical_json_bytes_v1(value)
        identity = {
            "uri": uri,
            "generation": "1",
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[(uri, "1")] = raw
        return identity

    def read_exact(self, identity: dict[str, object]) -> bytes:
        return self.objects[(str(identity["uri"]), str(identity["generation"]))]

    def publish(self, uri: str, raw: bytes) -> dict[str, object]:
        self.publications.append(uri)
        identity = {
            "uri": uri,
            "generation": "9001",
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[(uri, "9001")] = raw
        return identity


def _worlds(source: int) -> dict[str, dict[str, object]]:
    return {
        f"world_artifact_{block.lower()}": _identity(
            f"gs://fixture/worlds/{source:03d}/{block}.npz",
            f"world-{source}-{block}",
        )
        for block in contract.WORLD_BLOCKS
    }


def _budget(source: int) -> dict[str, object]:
    return cloud.build_evaluator_process_budget_v1(
        source_ordinal=source,
        slate_id=f"slate-{source:03d}",
        selection_task_manifest_identity=_identity(
            "gs://fixture/selection-manifest.json", "selection-manifest"
        ),
        source_task_manifest_identity=_identity(
            "gs://fixture/source-manifest.json", "source-manifest"
        ),
        selection_bootstrap_identity=_identity(
            "gs://fixture/selection-bootstrap.json", "selection-bootstrap"
        ),
        evaluator_bootstrap_identity=_identity(
            "gs://fixture/evaluator-bootstrap.json", "evaluator-bootstrap"
        ),
        run_authorization_identity=_identity(
            "gs://fixture/evaluator-run.json", "evaluator-run"
        ),
        selection_result_identity=_identity(
            f"gs://fixture/selection/{source:03d}.json", f"selection-{source}"
        ),
        projection_bundle_identity=_identity(
            f"gs://fixture/projection/{source:03d}.json", f"projection-{source}"
        ),
        later_source_identity=_identity(
            f"gs://fixture/later/{source:03d}.json", f"later-{source}"
        ),
        world_artifact_identities=_worlds(source),
        result_uri=f"{_prefix()}evaluations/source-{source:03d}.json",
    )


def _manifest() -> dict[str, object]:
    bindings = []
    for source in range(contract.PANEL_SLATE_COUNT):
        bindings.append(cloud.build_task_binding_v1(
            source_ordinal=source,
            slate_id=f"slate-{source:03d}",
            selection_task_binding_sha256=f"{source + 1:064x}",
            selection_result_identity=_identity(
                f"gs://fixture/selection/{source:03d}.json",
                f"selection-{source}",
            ),
            projection_bundle_identity=_identity(
                f"gs://fixture/projection/{source:03d}.json",
                f"projection-{source}",
            ),
            process_budget_identity=_identity(
                f"gs://fixture/budgets/{source:03d}.json",
                f"budget-{source}",
            ),
            result_uri=f"{_prefix()}evaluations/source-{source:03d}.json",
        ))
    return cloud.build_task_manifest_v1(
        output_prefix=_prefix(),
        selection_task_manifest_identity=_identity(
            "gs://fixture/selection-manifest.json", "selection-manifest"
        ),
        source_task_manifest_identity=_identity(
            "gs://fixture/source-manifest.json", "source-manifest"
        ),
        selection_bootstrap_identity=_identity(
            "gs://fixture/selection-bootstrap.json", "selection-bootstrap"
        ),
        evaluator_bootstrap_identity=_identity(
            "gs://fixture/evaluator-bootstrap.json", "evaluator-bootstrap"
        ),
        run_authorization_identity=_identity(
            "gs://fixture/evaluator-run.json", "evaluator-run"
        ),
        code_commit="a" * 40,
        image_digest="sha256:" + "b" * 64,
        task_bindings=bindings,
    )


def test_distinct_evaluator_budget_has_exact_scientific_reads_and_zero_fits() -> None:
    budget = _budget(7)
    assert cloud.validate_evaluator_process_budget_v1(budget) == budget
    assert budget["selector_fit_count"] == 0
    assert budget["source_control_evaluator_compatible"] is False
    assert [row["role"] for row in budget["read_allowlist"][-6:]] == [
        "later-source",
        *[f"heldout-world-{block}" for block in contract.WORLD_BLOCKS],
    ]
    assert budget["write_allowlist"] == [{
        "role": "successor-evaluation-result",
        "uri": f"{_prefix()}evaluations/source-007.json",
        "max_bytes": cloud.MAXIMUM_EVALUATION_RESULT_BYTES,
        "create_once": True,
    }]


def test_manifest_and_reused_job_config_register_separate_entrypoint() -> None:
    manifest = _manifest()
    assert cloud.validate_task_manifest_v1(manifest) == manifest
    identity = _body_identity(
        f"{_prefix()}authorities/evaluator-task-manifest.json", manifest
    )
    config = cloud.build_evaluation_job_configuration_v1(
        task_manifest=manifest,
        task_manifest_identity=identity,
        reused_job_name="fixture-reused-job",
    )
    assert config["task_count"] == 54
    assert config["parallelism"] == 54
    assert config["max_retries"] == 0
    assert config["new_job_creation_allowed"] is False
    assert config["container_args"][-1] == cloud.MODE_EVALUATE
    assert "crossed_screen_evaluation_v1.py" not in " ".join(
        config["container_args"]
    )


def test_runtime_is_exact_mode_task_and_immutable_image_bound() -> None:
    environment = {
        cloud.ENABLE_ENV: "1",
        "GOOGLE_CLOUD_PROJECT": cloud.FIXED_GCP_PROJECT,
        "CODE_SHA": "a" * 40,
        "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "b" * 64,
        "CLOUD_RUN_JOB": "fixture-reused-job",
        "CLOUD_RUN_EXECUTION": "fixture-execution",
        "CLOUD_RUN_TASK_INDEX": "9",
        "CLOUD_RUN_TASK_COUNT": "54",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
    }
    runtime = cloud.derive_runtime_evidence_v1(
        mode=cloud.MODE_EVALUATE,
        environ=environment,
        observed_command=cloud.canonical_command_v1(cloud.MODE_EVALUATE),
        pid=101,
        parent_pid=1,
    )
    assert runtime["task_index"] == 9
    assert runtime["source_control_evaluator_compatibility_claimed"] is False
    mutated = dict(environment)
    mutated["CLOUD_RUN_TASK_ATTEMPT"] = "1"
    with pytest.raises(
        cloud.CorpusR6CurrentBankSelectorSuccessorEvaluationCloudV1Error,
        match="observed runtime differs",
    ):
        cloud.derive_runtime_evidence_v1(
            mode=cloud.MODE_EVALUATE,
            environ=mutated,
            observed_command=cloud.canonical_command_v1(cloud.MODE_EVALUATE),
            pid=101,
            parent_pid=1,
        )


def test_scientific_gate_is_ordered_generation_exact_and_exhaustive() -> None:
    rows = [{
        "role": "later-source",
        "identity": _identity("gs://fixture/later.json", "later"),
    }, *[
        {
            "role": f"heldout-world-{block}",
            "identity": _identity(
                f"gs://fixture/{block}.npz", f"world-{block}"
            ),
        }
        for block in contract.WORLD_BLOCKS
    ]]
    bodies = {
        (row["identity"]["uri"], row["identity"]["generation"]): (
            "later".encode()
            if row["role"] == "later-source"
            else f"world-{row['role'][-2:]}".encode()
        )
        for row in rows
    }
    gate = cloud.ExactScientificReadGateV1(
        rows=rows,
        read_exact=lambda identity: bodies[(
            identity["uri"], identity["generation"]
        )],
    )
    with pytest.raises(
        cloud.CorpusR6CurrentBankSelectorSuccessorEvaluationCloudV1Error,
        match="role/order/identity",
    ):
        gate.read("heldout-world-R0", rows[1]["identity"])
    for row in rows:
        gate.read(str(row["role"]), row["identity"])
    assert len(gate.require_complete()) == 6


def test_terminal_budget_is_exact_54_and_has_no_outcome_capability() -> None:
    manifest = _manifest()
    manifest_identity = _body_identity(
        f"{_prefix()}authorities/evaluator-task-manifest.json", manifest
    )
    results = [
        _identity(
            f"{_prefix()}evaluations/source-{source:03d}.json",
            f"evaluation-{source}",
        )
        for source in range(contract.PANEL_SLATE_COUNT)
    ]
    budget = cloud.build_terminal_process_budget_v1(
        evaluator_task_manifest_identity=manifest_identity,
        evaluation_result_identities=results,
        result_uri=f"{_prefix()}terminal-aggregate.json",
    )
    assert cloud.validate_terminal_process_budget_v1(budget) == budget
    assert budget["read_object_count"] == 55
    assert budget["realized_outcome_read_allowed"] is False
    assert all("outcome" not in row["role"] for row in budget["read_allowlist"])
    budget_identity = _body_identity(
        f"{_prefix()}authorities/terminal-process-budget.json", budget
    )
    terminal_manifest = cloud.build_terminal_manifest_v1(
        evaluator_task_manifest_identity=manifest_identity,
        terminal_process_budget_identity=budget_identity,
        code_commit="a" * 40,
        image_digest="sha256:" + "b" * 64,
        reused_job_name="fixture-reused-job",
    )
    assert cloud.validate_terminal_manifest_v1(terminal_manifest) == terminal_manifest
    terminal_identity = _body_identity(
        f"{_prefix()}authorities/terminal-manifest.json", terminal_manifest
    )
    config = cloud.build_terminal_job_configuration_v1(
        terminal_manifest=terminal_manifest,
        terminal_manifest_identity=terminal_identity,
        reused_job_name="fixture-reused-job",
    )
    assert config["task_count"] == config["parallelism"] == 1
    assert config["container_args"][-1] == cloud.MODE_AGGREGATE


def test_entrypoint_uses_only_solver_free_control_scoring_primitives() -> None:
    source = Path(
        "scripts/run_corpus_r6_current_bank_selector_successor_evaluation_cloud_v1.py"
    ).read_text(encoding="utf-8")
    assert "run_evaluator_v1(" not in source
    assert "build_evaluation_result_v1(" not in source
    assert "_score_heldout_fold_v1(" in source
    assert "_load_artifact_worlds_v1" in source


def test_preparer_publishes_one_bootstrap_54_budgets_and_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Store()
    source_identity = store.add("gs://fixture/source.json", {"fixture": "source"})
    selection_bootstrap_identity = store.add(
        "gs://fixture/selection-bootstrap.json", {"fixture": "bootstrap"}
    )
    selection_tasks = []
    selection_result_identities = []
    for source in range(contract.PANEL_SLATE_COUNT):
        selection_uri = f"gs://fixture/selections/source-{source:03d}.json"
        result = {
            "source_ordinal": source,
            "slate_id": f"slate-{source:03d}",
        }
        result_identity = store.add(selection_uri, result)
        selection_result_identities.append(result_identity)
        projection0 = {
            "later_source_identity": _identity(
                f"gs://fixture/later/{source:03d}.json", f"later-{source}"
            ),
            "world_artifact_identities": _worlds(source),
        }
        bundle = {
            "source_ordinal": source,
            "slate_id": f"slate-{source:03d}",
            "fold_projections": [projection0],
        }
        bundle_identity = store.add(
            f"gs://fixture/projections/source-{source:03d}.json", bundle
        )
        selection_tasks.append({
            "task_binding_sha256": f"{source + 1:064x}",
            "result_uri": selection_uri,
            "projection_bundle_identity": bundle_identity,
        })
    selection_manifest = {
        "source_control_task_manifest_identity": source_identity,
        "bootstrap_identity": selection_bootstrap_identity,
        "task_bindings": selection_tasks,
    }
    selection_manifest_identity = store.add(
        "gs://fixture/selection-manifest.json", selection_manifest
    )
    monkeypatch.setattr(
        cloud.selection_cloud,
        "validate_task_manifest_v1",
        lambda value, **_kwargs: dict(value),
    )
    monkeypatch.setattr(
        contract, "validate_projection_bundle_v1", lambda value: dict(value)
    )
    monkeypatch.setattr(
        cloud.evaluation,
        "_validate_selection_slate_result_v1",
        lambda value, **_kwargs: dict(value),
    )
    prepared = cloud.prepare_evaluation_task_manifest_v1(
        selection_task_manifest_identity=selection_manifest_identity,
        selection_result_identities=selection_result_identities,
        output_prefix=_prefix(),
        code_commit="a" * 40,
        image_digest="sha256:" + "b" * 64,
        reused_job_name="fixture-reused-job",
        read_exact=store.read_exact,
        publish_create_once=store.publish,
    )
    assert prepared["task_count"] == 54
    assert len(prepared["process_budget_identities"]) == 54
    assert prepared["selector_fit_count"] == 0
    assert prepared["job_configuration"]["task_count"] == 54
    assert len(store.publications) == 57  # run auth, bootstrap, 54 budgets, manifest


def test_terminal_preparer_requires_bound_54_result_panel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Store()
    manifest = _manifest()
    manifest_identity = store.add(
        f"{_prefix()}authorities/evaluator-task-manifest.json", manifest
    )
    identities = []
    for source, binding in enumerate(manifest["task_bindings"]):
        result = {
            "source_ordinal": source,
            "slate_id": binding["slate_id"],
            "execution_authority_present": True,
            "execution_binding": {
                "task_manifest_identity": manifest_identity,
                "process_budget_identity": binding["process_budget_identity"],
            },
        }
        identities.append(store.add(binding["result_uri"], result))
    monkeypatch.setattr(
        cloud.evaluation,
        "validate_evaluation_result_v1",
        lambda value: dict(value),
    )
    prepared = cloud.prepare_terminal_manifest_v1(
        evaluator_task_manifest_identity=manifest_identity,
        evaluation_result_identities=identities,
        result_uri=f"{_prefix()}terminal-aggregate.json",
        reused_job_name="fixture-reused-job",
        read_exact=store.read_exact,
        publish_create_once=store.publish,
    )
    assert prepared["evaluation_count"] == 54
    assert prepared["job_configuration"]["task_count"] == 1
    assert prepared["job_configuration"]["new_job_creation_allowed"] is False
