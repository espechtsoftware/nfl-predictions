from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from scripts import run_corpus_r6_paid_source_normalized_snapshot_v1 as cli
from nfl_dfs.research import corpus_r6_paid_source_normalized_snapshot_v1 as snapshot
from tests import test_corpus_r6_paid_source_normalized_snapshot_v1 as fixture


def _write(path: Path, value: object) -> Path:
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def _enabled(variable: str) -> dict[str, str]:
    return {variable: cli.ENABLE_VALUE}


def test_validate_is_canonical_and_constructs_no_external_client(
    tmp_path: Path,
) -> None:
    request = fixture._request()
    path = _write(tmp_path / "request.json", request)
    assert cli.run(["validate", "--request", str(path)]) == request


def test_task0_is_default_off_before_code_or_query_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = fixture._request()
    path = _write(tmp_path / "request.json", request)
    monkeypatch.setattr(
        cli,
        "_verify_request_code",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("code verifier constructed")
        ),
    )
    with pytest.raises(
        cli.PaidSourceNormalizedSnapshotCliV1Error,
        match="snapshot task0 is disabled",
    ):
        cli.run(
            [
                "task0", "--request", str(path), "--repository-root",
                str(Path(__file__).resolve().parents[1]), "--execute",
            ],
            environ={},
            query_warehouse=lambda spec: (_ for _ in ()).throw(
                AssertionError("query constructed")
            ),
        )


def test_enabled_task0_is_nonpublishing_and_uses_only_one_fixed_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = fixture._request()
    path = _write(tmp_path / "request.json", request)
    monkeypatch.setattr(cli, "_verify_request_code", lambda *args, **kwargs: None)
    seen: list[dict[str, object]] = []

    def query(spec: dict[str, object]) -> dict[str, object]:
        seen.append(dict(spec))
        return fixture._query_result(dict(spec))

    result = cli.run(
        [
            "task0", "--request", str(path), "--repository-root",
            str(Path(__file__).resolve().parents[1]), "--execute",
        ],
        environ=_enabled(cli.TASK0_ENV),
        query_warehouse=query,
    )
    assert len(seen) == 1
    assert seen[0] == request["query_specs"][0]
    assert result["publication_count"] == 0
    assert result["publication_callback_present"] is False
    assert result["write_api_reachable_from_task0"] is False
    assert result["runtime_principal_write_authority_status"] == "not-evaluated"
    assert result["uses_realized_outcomes"] is False


def test_task0_warehouse_view_exposes_no_publication_surface() -> None:
    class Warehouse:
        def __call__(self, spec: object) -> object:
            return {"spec": spec}

        def publish(self, value: object) -> None:
            raise AssertionError("publication must not be reachable")

    view = cli.Task0ReadOnlyWarehouseViewV1(Warehouse())
    assert view({"fixed": True}) == {"spec": {"fixed": True}}
    assert not hasattr(view, "publish")


def test_publish_is_default_off_before_store_or_query_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = fixture._request()
    task0 = fixture._task0(request)
    request_path = _write(tmp_path / "request.json", request)
    receipt_path = _write(tmp_path / "task0.json", task0)
    monkeypatch.setattr(
        cli,
        "_verify_request_code",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("code verifier constructed")
        ),
    )
    with pytest.raises(
        cli.PaidSourceNormalizedSnapshotCliV1Error,
        match="snapshot publish is disabled",
    ):
        cli.run(
            [
                "publish", "--request", str(request_path),
                "--task0-receipt", str(receipt_path), "--repository-root",
                str(Path(__file__).resolve().parents[1]), "--execute",
            ],
            environ={},
            query_warehouse=lambda spec: (_ for _ in ()).throw(
                AssertionError("query constructed")
            ),
            store=object(),
        )


def test_enabled_publish_and_independent_reopen_use_exact_injected_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = fixture._request()
    task0 = fixture._task0(request)
    request_path = _write(tmp_path / "request.json", request)
    receipt_path = _write(tmp_path / "task0.json", task0)
    monkeypatch.setattr(cli, "_verify_request_code", lambda *args, **kwargs: None)

    class Store(fixture.Store):
        publish_create_once = fixture.Store.publish
        read_exact = fixture.Store.read

    store = Store()
    published = cli.run(
        [
            "publish", "--request", str(request_path),
            "--task0-receipt", str(receipt_path), "--repository-root",
            str(Path(__file__).resolve().parents[1]), "--execute",
        ],
        environ=_enabled(cli.PUBLISH_ENV),
        query_warehouse=lambda spec: fixture._query_result(dict(spec)),
        store=store,
    )
    assert published["complete"] is True
    assert len(store.writes) == 13
    identity_path = _write(
        tmp_path / "terminal-identity.json", published["terminal_identity"]
    )
    reopened = cli.run(
        [
            "reopen", "--terminal-identity", str(identity_path), "--execute",
        ],
        environ=_enabled(cli.REOPEN_ENV),
        store=store,
        query_warehouse=lambda spec: (_ for _ in ()).throw(
            AssertionError("reopen queried BigQuery")
        ),
    )
    assert reopened["complete"] is True
    assert reopened[
        "both_manifests_and_all_exact_predecessors_reopened"
    ] is True
    assert reopened["recognized_outcome_callback_present"] is False
    assert reopened["outcome_artifacts_read"] == []


def test_build_request_binds_exact_clean_code_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "_code_identity", lambda root: dict(fixture.CODE))
    result = cli.run([
        "build-request", "--run-id", "snapshot-cli-fixture-v1",
        "--snapshot-at-utc", "2026-08-30T12:00:00Z",
        "--repository-root", str(Path(__file__).resolve().parents[1]),
    ])
    assert result["projection_code_identity"] == fixture.CODE
    assert result["authoritative_pit"] is False
    assert result["uses_realized_outcomes"] is False


def test_detached_runtime_code_binding_needs_exact_image_commit_and_module(
    tmp_path: Path,
) -> None:
    module = tmp_path / snapshot.MODULE_PATH
    module.parent.mkdir(parents=True)
    module.write_bytes(b"exact projection module\n")
    commit = "c" * 40
    (tmp_path / "SOURCE_COMMIT").write_text(commit + "\n", encoding="ascii")
    module_sha = sha256(module.read_bytes()).hexdigest()
    request = {"projection_code_identity": {
        "source_commit_sha": commit,
        "module_path": snapshot.MODULE_PATH,
        "module_sha256": module_sha,
    }}
    cli._verify_request_code(
        request,
        repository_root=tmp_path,
        environment={
            cli.IMAGE_SOURCE_SHA_ENV: commit,
            cli.MODULE_SHA_ENV: module_sha,
        },
    )
    module.write_bytes(b"substituted projection module\n")
    with pytest.raises(
        cli.PaidSourceNormalizedSnapshotCliV1Error,
        match="detached image code binding differs",
    ):
        cli._verify_request_code(
            request,
            repository_root=tmp_path,
            environment={
                cli.IMAGE_SOURCE_SHA_ENV: commit,
                cli.MODULE_SHA_ENV: module_sha,
            },
        )
