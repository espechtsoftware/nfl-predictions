"""Offline tests for the thin local R6 outcome-snapshot CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from scripts import run_corpus_r6_full_union_outcome_snapshot_v1 as cli


def test_parser_exposes_only_the_five_offline_contract_stages(tmp_path: Path) -> None:
    identity = tmp_path / "identity.json"
    output = tmp_path / "output.json"
    object_store = tmp_path / "objects"
    object_store.mkdir()
    parsed = cli._parser().parse_args([
        "project-keys",
        "--object-store", str(object_store),
        "--panel-freeze-identity", str(identity),
        "--output", str(output),
    ])
    assert parsed.command == "project-keys"
    assert set(cli._parser()._subparsers._group_actions[0].choices) == {
        "project-keys", "build-smoke-receipt", "validate-smoke-receipt",
        "build-source", "build-snapshot",
    }


def test_smoke_cli_requires_explicit_root_and_projection_identities(
    tmp_path: Path,
) -> None:
    common = [
        "--object-store", str(tmp_path),
        "--projection", str(tmp_path / "projection.json"),
        "--expected-reviewed-source-commit-sha", "a" * 40,
        "--expected-runtime-immutable-image",
        f"registry.example/snapshot@sha256:{'b' * 64}",
        "--snapshot-module-sha256", "c" * 64,
        "--snapshot-cli-sha256", "d" * 64,
        "--snapshot-test-sha256", "e" * 64,
        "--snapshot-cli-test-sha256", "f" * 64,
        "--output", str(tmp_path / "receipt.json"),
    ]
    with pytest.raises(SystemExit):
        cli._parser().parse_args(["build-smoke-receipt", *common])
    parsed = cli._parser().parse_args([
        "build-smoke-receipt",
        "--expected-panel-freeze-identity", str(tmp_path / "root-id.json"),
        "--expected-outcome-key-projection-identity",
        str(tmp_path / "projection-id.json"),
        *common,
    ])
    assert parsed.command == "build-smoke-receipt"


def test_smoke_cli_routes_explicit_identities_to_build_and_validate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    object_store = tmp_path / "objects"
    object_store.mkdir()
    root_identity = {"expected": "root"}
    projection = {"expected": "projection"}
    projection_identity = {"expected": "projection-identity"}
    receipt = {"expected": "receipt"}
    receipt_identity = {"expected": "receipt-identity"}
    values = {
        "root-id.json": root_identity,
        "projection.json": projection,
        "projection-id.json": projection_identity,
        "receipt.json": receipt,
        "receipt-id.json": receipt_identity,
    }
    for name, value in values.items():
        (tmp_path / name).write_bytes(batch.canonical_json_bytes(value))
    captured: list[tuple[str, dict[str, object]]] = []

    def fake_build(**kwargs: object) -> dict[str, object]:
        captured.append(("build", kwargs))
        return {"built": True}

    def fake_validate(
        value: object, **kwargs: object,
    ) -> tuple[dict[str, object], dict[str, object]]:
        captured.append(("validate", {"value": value, **kwargs}))
        return {"validated": True}, {"identity": True}

    monkeypatch.setattr(
        cli.snapshot, "build_actual_root_smoke_receipt_v1", fake_build
    )
    monkeypatch.setattr(
        cli.snapshot, "validate_actual_root_smoke_receipt_v1", fake_validate
    )
    common = [
        "--object-store", str(object_store),
        "--expected-panel-freeze-identity", str(tmp_path / "root-id.json"),
        "--projection", str(tmp_path / "projection.json"),
        "--expected-outcome-key-projection-identity",
        str(tmp_path / "projection-id.json"),
        "--expected-reviewed-source-commit-sha", "a" * 40,
        "--expected-runtime-immutable-image",
        f"registry.example/snapshot@sha256:{'b' * 64}",
        "--snapshot-module-sha256", "c" * 64,
        "--snapshot-cli-sha256", "d" * 64,
        "--snapshot-test-sha256", "e" * 64,
        "--snapshot-cli-test-sha256", "f" * 64,
    ]
    assert cli.main([
        "build-smoke-receipt", *common,
        "--output", str(tmp_path / "built.json"),
    ]) == 0
    assert cli.main([
        "validate-smoke-receipt", *common,
        "--smoke-receipt", str(tmp_path / "receipt.json"),
        "--smoke-receipt-identity", str(tmp_path / "receipt-id.json"),
        "--output", str(tmp_path / "validated.json"),
    ]) == 0
    assert captured[0][0] == "build"
    assert captured[0][1]["panel_freeze_identity"] == root_identity
    assert captured[0][1]["outcome_key_projection_identity"] == (
        projection_identity
    )
    assert captured[1][0] == "validate"
    assert captured[1][1]["expected_panel_freeze_identity"] == root_identity
    assert captured[1][1][
        "expected_outcome_key_projection_identity"
    ] == projection_identity


def test_local_reader_is_content_addressed_and_output_is_create_once(
    tmp_path: Path,
) -> None:
    object_store = tmp_path / "objects"
    object_store.mkdir()
    value = {"fixture": True}
    identity = batch.object_identity_for_json(
        value, uri="gs://fixture/value.json", generation="1"
    )
    object_path = object_store / f"{identity['sha256']}.json"
    object_path.write_bytes(batch.canonical_json_bytes(value))
    reader = cli._LocalExactReader(object_store)
    assert reader(identity) == batch.canonical_json_bytes(value)

    output = tmp_path / "result.json"
    cli._write_create_once(output, value)
    assert output.read_bytes() == batch.canonical_json_bytes(value)
    with pytest.raises(FileExistsError):
        cli._write_create_once(output, value)


def test_create_once_rejects_live_dangling_and_parent_symlinks(
    tmp_path: Path,
) -> None:
    value = {"fixture": True}
    live_target = tmp_path / "live-target.json"
    live_target.write_text("untouched")
    live_link = tmp_path / "live-link.json"
    live_link.symlink_to(live_target)
    with pytest.raises(ValueError, match="symlink"):
        cli._write_create_once(live_link, value)
    assert live_target.read_text() == "untouched"

    dangling = tmp_path / "dangling.json"
    dangling.symlink_to(tmp_path / "absent.json")
    with pytest.raises(ValueError, match="symlink"):
        cli._write_create_once(dangling, value)
    assert dangling.is_symlink()

    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        cli._write_create_once(linked_parent / "result.json", value)
    assert not (real_parent / "result.json").exists()


def test_create_once_cleans_temporary_file_across_install_interruptions(
    tmp_path: Path,
) -> None:
    value = {"fixture": True}
    before_link = tmp_path / "before-link.json"

    def interrupted_link(*args: object, **kwargs: object) -> None:
        raise OSError("simulated interruption before atomic install")

    with pytest.raises(OSError, match="before atomic install"):
        cli._write_create_once(before_link, value, _link=interrupted_link)
    assert not before_link.exists()
    assert list(tmp_path.glob(".before-link.json.*.tmp")) == []

    after_link = tmp_path / "after-link.json"

    def interrupted_after_link() -> None:
        raise RuntimeError("simulated interruption after atomic install")

    with pytest.raises(RuntimeError, match="after atomic install"):
        cli._write_create_once(
            after_link, value, _after_link=interrupted_after_link
        )
    assert after_link.read_bytes() == batch.canonical_json_bytes(value)
    assert list(tmp_path.glob(".after-link.json.*.tmp")) == []
