from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from scripts import run_corpus_r6_paid_source_fp_sis_v1 as cli
from nfl_dfs.research import paid_source_ablation_execution_v1 as execution
from tests import test_paid_source_ablation_execution_v1 as fixture


def _write(path: Path, value: object) -> Path:
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def _environment(*, outcomes: bool) -> dict[str, str]:
    return {
        cli.ENABLE_ENV: cli.ENABLE_VALUE,
        cli.OUTCOMES_ENV: str(outcomes).lower(),
        cli.CODE_SHA_ENV: fixture.CODE_SHA,
        cli.IMAGE_SOURCE_SHA_ENV: fixture.CODE_SHA,
        cli.IMAGE_DIGEST_ENV: fixture.DIGEST,
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_COUNT": "1",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
    }


def _task0_receipt(request: dict[str, object]) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": execution.TASK0_SCHEMA,
        "execution_request_sha256": request["execution_request_sha256"],
        "run_id": request["run_id"],
        "source_v3_release_identity": request["source_v3_release_identity"],
        "discovery_matrix_freeze_terminal_identity": request[
            "discovery_matrix_freeze_terminal_identity"
        ],
        "discovery_matrix_registry_reopen_sha256": "c" * 64,
        "task0_world_matrix_identity": request[
            "discovery_matrix_freeze_terminal_identity"
        ],
        "runtime_build_attestation_sha256": "d" * 64,
        "task0_slate_support_census_sha256": "e" * 64,
        "task0_source_task_ordinal": 0,
        "task0_k80_feasible_all_four_cells": True,
        "all_54_input_identities_frozen": True,
        "full_cohort_execution_launched": False,
        "publication_performed": False,
        "publication_callback_present": False,
        "write_api_reachable_from_task0": False,
        "runtime_principal_write_authority_status": "not-evaluated",
        "recognized_outcome_callback_present": False,
        "runtime_principal_outcome_authority_status": "not-evaluated",
        "outcome_artifacts_read": [],
        "world_matrix_body_read_count": 1,
        "matrix_streamed_to_disk_and_memmapped": True,
        "selection_bank_r0_r3_float64_exact": True,
        "r4_body_read": False,
        "mechanical_launch_gate_passed": True,
        "complete": True,
        **execution._policy(uses_realized_outcomes=False),
    }
    body["task0_receipt_sha256"] = fixture.registry.canonical_sha256(body)
    return body


def test_validate_is_client_free_and_canonical(tmp_path: Path) -> None:
    request, _, _, _ = fixture._request_fixture()
    path = _write(tmp_path / "request.json", request)
    result = cli.run(["validate", "--request", str(path)])
    assert result == request


def test_public_build_request_needs_only_typed_score_free_inputs(
    tmp_path: Path,
) -> None:
    request, _, _, _ = fixture._request_fixture()
    prepare = {
        "schema_version": cli.PREPARE_INPUT_SCHEMA,
        "run_id": request["run_id"],
        "frozen_at": request["frozen_at"],
        "source_v3_release_identity": request["source_v3_release_identity"],
        "discovery_matrix_freeze_terminal_identity": request[
            "discovery_matrix_freeze_terminal_identity"
        ],
        "runtime_build_attestation_identity": request[
            "runtime_build_attestation_identity"
        ],
    }
    path = _write(tmp_path / "prepare.json", prepare)
    assert cli.run([
        "build-request", "--input", str(path),
        "--code-sha", fixture.CODE_SHA,
        "--immutable-image", fixture.IMAGE,
        "--build-id", fixture.BUILD_ID,
    ]) == request


def test_task0_stays_default_off_before_store_or_reopener(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, _, _, _ = fixture._request_fixture()
    path = _write(tmp_path / "request.json", request)
    monkeypatch.setattr(
        cli, "_source_reopener",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("constructed")),
    )
    with pytest.raises(
        cli.PaidSourceFpSisCliV1Error,
        match="runtime enable/code/image/outcome gate",
    ):
        cli.run(["task0", "--request", str(path), "--execute"], environ={})


def test_task0_enabled_passes_only_reader_and_fixed_source_reopener(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, _, _, _ = fixture._request_fixture()
    path = _write(tmp_path / "request.json", request)

    class Reader:
        def read_exact(self, identity: object) -> bytes:
            return b"fixture"

        def fetch_exact_to_file(self, identity: object, path: Path) -> None:
            raise AssertionError("execution mock must own the callback")

        def publish_create_once(self, uri: str, raw: bytes) -> object:
            raise AssertionError("task0 must not expose publication")

    sentinel = object()
    monkeypatch.setattr(cli, "_source_reopener", lambda **kwargs: sentinel)

    def task0(value: object, **kwargs: object) -> dict[str, object]:
        assert value == request
        assert callable(kwargs["read_exact"])
        assert callable(kwargs["fetch_exact_to_file"])
        assert Path(kwargs["matrix_workspace"]).is_absolute()
        assert callable(kwargs["reopen_discovery_matrix_registry"])
        assert kwargs["canonical_source_v3_reopen_by_ordinal"] is sentinel
        assert "publish_create_once" not in kwargs
        return {"complete": True, "publication_performed": False}

    monkeypatch.setattr(execution, "run_fp_sis_task0_v1", task0)
    result = cli.run(
        ["task0", "--request", str(path), "--execute"],
        environ=_environment(outcomes=False),
        read_store=Reader(),
    )
    assert result == {"complete": True, "publication_performed": False}


def test_task0_store_view_exposes_no_publish_api(tmp_path: Path) -> None:
    class Store:
        def read_exact(self, identity: object) -> bytes:
            return b"fixture"

        def fetch_exact_to_file(self, identity: object, path: Path) -> None:
            path.write_bytes(b"fixture")

        def publish_create_once(self, uri: str, raw: bytes) -> object:
            raise AssertionError("publication must not be reachable")

    view = cli.ExactReadOnlyFileStoreViewV1(Store())
    assert callable(view.read_exact)
    assert callable(view.fetch_exact_to_file)
    assert not hasattr(view, "publish_create_once")


def test_cloud_task0_gate_rejects_locally_rehashed_receipt() -> None:
    request, _, _, _ = fixture._request_fixture()
    request_sha = sha256(fixture.registry.canonical_json_bytes(request)).hexdigest()
    cloud_result = fixture._task0_provider_gate(request)
    assert cli.validate_cloud_task0_launch_gate_v1(
        request_value=request,
        cloud_result_value=cloud_result,
        request_file_sha256=request_sha,
        code_sha=fixture.CODE_SHA,
        immutable_image=fixture.IMAGE,
        build_id=fixture.BUILD_ID,
        task0_execution="atlas-cbc-32g-full-2023-w8-v1-abc12",
    ) == cloud_result

    # The public provider-gate validator has no separate receipt input.  A
    # locally rehashed receipt therefore cannot be paired with an otherwise
    # exact provider result, which is the former unsafe host seam.
    rehashed = deepcopy(cloud_result["operator_receipt"])
    rehashed["task0_slate_support_census_sha256"] = "f" * 64
    rehashed.pop("task0_receipt_sha256")
    rehashed["task0_receipt_sha256"] = fixture.registry.canonical_sha256(rehashed)
    assert execution.validate_fp_sis_task0_receipt_v1(
        rehashed, request_value=request
    ) == rehashed
    assert rehashed != cloud_result["operator_receipt"]
    assert "task0_receipt_value" not in (
        cli.validate_cloud_task0_launch_gate_v1.__annotations__
    )


def test_terminal_reopen_has_no_writer_or_outcome_callback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    terminal_identity = {
        "uri": "gs://fixture-bucket/paid/terminal.json",
        "generation": "1",
        "sha256": "c" * 64,
        "bytes": 100,
        "create_once": True,
    }
    request = {
        "schema_version": cli.TERMINAL_REOPEN_REQUEST_SCHEMA,
        "terminal_identity": terminal_identity,
        "terminal_sha256": "d" * 64,
        "code_sha": fixture.CODE_SHA,
        "immutable_image": fixture.IMAGE,
        "image_digest": fixture.DIGEST,
    }
    path = _write(tmp_path / "reopen.json", request)

    class Reader:
        def read_exact(self, identity: object) -> bytes:
            return b"fixture"

    def reopen(**kwargs: object) -> dict[str, object]:
        assert kwargs["terminal_identity"] == terminal_identity
        assert callable(kwargs["read_exact"])
        return {"complete": True, "uses_realized_outcomes": False}

    monkeypatch.setattr(execution, "reopen_fp_sis_score_free_terminal_v1", reopen)
    result = cli.run(
        ["reopen", "--request", str(path), "--execute"],
        environ=_environment(outcomes=False),
        write_store=Reader(),
    )
    assert result["complete"] is True

    wrong_image = dict(request)
    wrong_image["immutable_image"] = "registry.example/other/image@" + fixture.DIGEST
    wrong_path = _write(tmp_path / "wrong-image.json", wrong_image)
    with pytest.raises(
        cli.PaidSourceFpSisCliV1Error,
        match="runtime enable/code/image/outcome gate",
    ):
        cli.run(
            ["reopen", "--request", str(wrong_path), "--execute"],
            environ=_environment(outcomes=False),
            write_store=Reader(),
        )


def test_grade_reopen_is_derived_score_mode_and_does_not_construct_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    grade_identity = {
        "uri": "gs://fixture-bucket/paid/grade.json",
        "generation": "2",
        "sha256": "e" * 64,
        "bytes": 200,
        "create_once": True,
    }
    request = {
        "schema_version": cli.GRADE_REOPEN_REQUEST_SCHEMA,
        "grade_identity": grade_identity,
        "code_sha": fixture.CODE_SHA,
        "immutable_image": fixture.IMAGE,
        "image_digest": fixture.DIGEST,
    }
    path = _write(tmp_path / "grade-reopen.json", request)

    class Reader:
        def read_exact(self, identity: object) -> bytes:
            return b"fixture"

    monkeypatch.setattr(
        execution,
        "reopen_fp_sis_grade_v1",
        lambda **kwargs: {
            "complete": True,
            "outcome_snapshot_reread": False,
            "historical_outcome_lease_reread": False,
        },
    )
    result = cli.run(
        ["grade-reopen", "--request", str(path), "--execute"],
        environ=_environment(outcomes=True),
        write_store=Reader(),
        lease_verifier_factory=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("lease verifier constructed")
        ),
    )
    assert result["outcome_snapshot_reread"] is False
    assert result["historical_outcome_lease_reread"] is False
