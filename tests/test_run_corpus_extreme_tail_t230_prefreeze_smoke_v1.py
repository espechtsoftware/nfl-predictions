from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from nfl_dfs.research import corpus_extreme_tail_panel_execution as execution
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_v2_one_slate_execution as accepted


ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    path = ROOT / "scripts/run_corpus_extreme_tail_t230_prefreeze_smoke_v1.py"
    spec = importlib.util.spec_from_file_location("t230_prefreeze_smoke_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


def _identity(label: str, ordinal: int) -> dict[str, object]:
    raw = f"{label}:{ordinal}".encode()
    return {
        "uri": f"gs://fixture-bucket/{label}-{ordinal}.json",
        "generation": str(10_000 + ordinal),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class ReadOnlyStore:
    def read(self, _identity):
        raise AssertionError("mocked smoke path unexpectedly exact-read storage")


def _fixture_panel():
    member = {
        "source_task_ordinal": 0,
        "slate_id": execution.PREFREEZE_SMOKE_SLATE_ID,
        "task_acceptance_identity": _identity("task-acceptance", 0),
        "carrier_identity": _identity("carrier", 0),
    }
    members = [member]
    for ordinal in range(1, execution.AUTHORITATIVE_SLATE_COUNT):
        members.append({
            "source_task_ordinal": ordinal,
            "slate_id": f"2023-w{ordinal + 1:02d}",
            "task_acceptance_identity": _identity("task-acceptance", ordinal),
            "carrier_identity": _identity("carrier", ordinal),
        })
    panel_identity = {
        "uri": execution.FROZEN_G0_PANEL_URI,
        "generation": "1787663639938214",
        "sha256": "a" * 64,
        "bytes": 209_279,
    }
    publication_receipt = {
        "panel_object_identity": panel_identity,
        "publication_receipt_sha256": "b" * 64,
    }
    publication_binding = {"sha256": "c" * 64}
    lane_bindings = [
        {
            "lane_ordinal": ordinal,
            "sha256": str(ordinal + 1) * 64,
            "bytes": 100 + ordinal,
            "terminal_receipt_identity": _identity("terminal", ordinal),
        }
        for ordinal in range(2)
    ]
    return (
        publication_binding,
        publication_receipt,
        {"accepted_slates": members},
        lane_bindings,
        panel_identity,
        member,
    )


def _structural_hashes(panel_identity):
    retained = {
        field: "d" * 64
        for field in execution._PREFREEZE_SMOKE_STRUCTURAL_HASH_KEYS
    }
    retained["panel_object_identity_sha256"] = batch.canonical_sha256(
        panel_identity
    )
    return retained


def _all_keys(value):
    if isinstance(value, dict):
        result = set(value)
        for item in value.values():
            result.update(_all_keys(item))
        return result
    if isinstance(value, list):
        result = set()
        for item in value:
            result.update(_all_keys(item))
        return result
    return set()


def test_fixed_ordinal_smoke_emits_only_compact_nonrelease_structure(
    monkeypatch, tmp_path
) -> None:
    (
        publication_binding,
        publication_receipt,
        panel_body,
        lane_bindings,
        panel_identity,
        member,
    ) = _fixture_panel()
    calls = []
    runtime = cli._nonrelease_fixture_runtime_binding_v1()
    reconstructed = SimpleNamespace(
        slate_id=execution.PREFREEZE_SMOKE_SLATE_ID,
        accepted_slate_membership=member,
        task_acceptance_identity=member["task_acceptance_identity"],
        carrier_identity=member["carrier_identity"],
        reconstructed=SimpleNamespace(
            reconstruction_receipt={
                "uses_realized_outcomes": False,
                "promotion_authority": False,
            }
        ),
    )
    monkeypatch.setattr(
        execution,
        "_replay_raw_published_v12_panel_v1",
        lambda **_kwargs: (
            publication_binding,
            publication_receipt,
            panel_body,
            lane_bindings,
        ),
    )

    def reconstruct(**kwargs):
        calls.append(("reconstruct", kwargs))
        return reconstructed

    monkeypatch.setattr(accepted, "reconstruct_one_accepted_v12_slate", reconstruct)
    monkeypatch.setattr(
        execution,
        "_input_artifact_bindings",
        lambda *_args, **_kwargs: {"fixture": True},
    )

    def science(reconstructed_slate):
        calls.append(("science", reconstructed_slate))
        return execution._T230ScienceStack({}, {}, {})

    monkeypatch.setattr(execution, "_execute_t230_science_stack_v1", science)
    monkeypatch.setattr(
        cli,
        "_project_structural_hashes",
        lambda **_kwargs: _structural_hashes(panel_identity),
    )
    output = tmp_path / "prefreeze-smoke.json"
    receipt = cli.run(
        ["--execute", "--receipt-output", str(output)],
        store=ReadOnlyStore(),
        runtime_binding=runtime,
    )

    assert [name for name, _value in calls] == ["reconstruct", "science"]
    reconstruction_kwargs = calls[0][1]
    assert reconstruction_kwargs["accepted_slate_membership"] == member
    assert reconstruction_kwargs["require_authoritative"] is True
    assert receipt["source_ordinal"] == 0
    assert receipt["slate_id"] == "2023-w01"
    assert receipt["panel_object_identity"] == panel_identity
    assert receipt["runtime_binding"]["release_validation_eligible"] is False
    assert receipt["verification"]["selector_effects_inspected"] is False
    assert output.read_bytes() == batch.canonical_json_bytes(receipt) + b"\n"
    forbidden = {
        "support_observation",
        "folds",
        "final_fit",
        "books",
        "selected_lineup_ids",
        "marginal_trace",
        "metrics",
        "union_scores",
    }
    assert not (forbidden & _all_keys(receipt))
    for field in execution._PREFREEZE_SMOKE_FALSE_AUTHORITY_FIELDS:
        assert receipt[field] is False


def test_smoke_rejects_nonzero_first_panel_member(monkeypatch) -> None:
    replay = list(_fixture_panel()[:4])
    replay[2] = deepcopy(replay[2])
    replay[2]["accepted_slates"][0]["source_task_ordinal"] = 1
    monkeypatch.setattr(
        execution,
        "_replay_raw_published_v12_panel_v1",
        lambda **_kwargs: tuple(replay),
    )
    with pytest.raises(
        cli.CorpusExtremeTailT230PrefreezeSmokeError,
        match="ordinal zero differs",
    ):
        cli.run(
            ["--execute"],
            store=ReadOnlyStore(),
            runtime_binding=cli._nonrelease_fixture_runtime_binding_v1(),
        )


def test_release_validator_rejects_fixture_runtime_and_authority_drift(
) -> None:
    _publication, _receipt, _panel, _lanes, panel_identity, _member = (
        _fixture_panel()
    )
    runtime = cli._nonrelease_fixture_runtime_binding_v1()
    receipt = execution.build_t230_prefreeze_smoke_receipt_v1(
        panel_object_identity=panel_identity,
        source_commit_sha=runtime["source_commit_sha"],
        immutable_candidate_image=runtime["immutable_candidate_image"],
        runtime_binding=runtime,
        structural_hashes=_structural_hashes(panel_identity),
        require_release_runtime=False,
    )
    with pytest.raises(
        execution.CorpusExtremeTailPanelExecutionError,
        match="Cloud Run runtime binding differs",
    ):
        execution.validate_t230_prefreeze_smoke_receipt_v1(
            receipt,
            expected_panel_object_identity=panel_identity,
            expected_source_commit_sha=runtime["source_commit_sha"],
            expected_immutable_candidate_image=runtime[
                "immutable_candidate_image"
            ],
            require_release_runtime=True,
        )
    forged = deepcopy(receipt)
    forged["selector_effect_inspection_licensed"] = True
    forged.pop("prefreeze_smoke_receipt_sha256")
    forged["prefreeze_smoke_receipt_sha256"] = batch.canonical_sha256(forged)
    with pytest.raises(
        execution.CorpusExtremeTailPanelExecutionError,
        match="selector_effect_inspection_licensed must be false",
    ):
        execution.validate_t230_prefreeze_smoke_receipt_v1(
            forged,
            expected_panel_object_identity=panel_identity,
            expected_source_commit_sha=runtime["source_commit_sha"],
            expected_immutable_candidate_image=runtime[
                "immutable_candidate_image"
            ],
            require_release_runtime=False,
        )


def test_real_runtime_binds_candidate_digest_cloud_execution_and_source(
    monkeypatch,
) -> None:
    commit = "e" * 40
    files = [
        {"path": path, "sha256": str(ordinal + 5) * 64, "bytes": 100 + ordinal}
        for ordinal, path in enumerate(execution.PREFREEZE_SMOKE_IMPLEMENTATION_PATHS)
    ]
    digest = "sha256:" + "f" * 64
    image_uri = (
        "us-central1-docker.pkg.dev/fixture/research/t230@" + digest
    )
    monkeypatch.setenv(cli.ENABLE_ENV, "1")
    monkeypatch.setenv(cli.CANDIDATE_IMAGE_ENV, image_uri)
    monkeypatch.setenv("CLOUD_RUN_JOB", execution.PREFREEZE_SMOKE_CLOUD_RUN_JOB)
    monkeypatch.setenv(
        "CLOUD_RUN_EXECUTION", execution.PREFREEZE_SMOKE_CLOUD_RUN_JOB + "-abcde"
    )
    monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "0")
    monkeypatch.setenv("CLOUD_RUN_TASK_ATTEMPT", "0")
    monkeypatch.setenv("CLOUD_RUN_TASK_COUNT", "1")
    monkeypatch.setattr(cli, "_tracked_source_bindings", lambda: (commit, files))

    runtime = cli._measure_cloud_run_runtime_binding()
    assert runtime["release_validation_eligible"] is True
    assert runtime["source_commit_sha"] == commit
    assert runtime["immutable_candidate_image"]["uri"] == image_uri
    assert runtime["cloud_run_task_attempt"] == 0
    _publication, _receipt, _panel, _lanes, panel_identity, _member = (
        _fixture_panel()
    )
    receipt = execution.build_t230_prefreeze_smoke_receipt_v1(
        panel_object_identity=panel_identity,
        source_commit_sha=commit,
        immutable_candidate_image=runtime["immutable_candidate_image"],
        runtime_binding=runtime,
        structural_hashes=_structural_hashes(panel_identity),
        require_release_runtime=True,
    )
    assert execution.validate_t230_prefreeze_smoke_receipt_v1(
        receipt,
        expected_panel_object_identity=panel_identity,
        expected_source_commit_sha=commit,
        expected_immutable_candidate_image=runtime["immutable_candidate_image"],
        require_release_runtime=True,
    ) == receipt


def test_cli_has_no_slate_dose_strategy_or_output_uri_knobs() -> None:
    parser = cli._parser()
    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
    }
    assert option_strings == {"-h", "--help", "--execute", "--receipt-output"}


def test_gcs_read_store_rejects_generation_matched_content_identity_drift() -> None:
    expected = b"expected"

    class Blob:
        def download_as_bytes(self, *, if_generation_match, retry):
            assert if_generation_match == 7
            assert retry is None
            return b"differed"

    class Bucket:
        def blob(self, name, *, generation):
            assert name == "object.json"
            assert generation == 7
            return Blob()

    class Client:
        def bucket(self, name):
            assert name == "fixture-bucket"
            return Bucket()

    identity = {
        "uri": "gs://fixture-bucket/object.json",
        "generation": "7",
        "sha256": sha256(expected).hexdigest(),
        "bytes": len(expected),
    }
    with pytest.raises(
        cli.CorpusExtremeTailT230PrefreezeSmokeError,
        match="content identity",
    ):
        cli.GCSReadStore(Client()).read(identity)
