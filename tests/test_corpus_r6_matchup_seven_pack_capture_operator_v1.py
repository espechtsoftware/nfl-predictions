from __future__ import annotations

from hashlib import sha256
import importlib.util
import inspect
from pathlib import Path

import pytest

from nfl_dfs.research import corpus_r6_matchup_seven_pack_capture_operator_v1 as operator
from nfl_dfs.research import corpus_r6_matchup_seven_pack_capture_v1 as capture
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_paid_source_normalized_snapshot_v1 as snapshot
from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v2 as candidate_v2,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPOSITORY_ROOT / "scripts/run_corpus_r6_matchup_seven_pack_capture_v1.py"


def _identity(label: str, *, uri: str | None = None) -> dict[str, object]:
    raw = label.encode()
    return {
        "uri": uri or f"gs://fixture-input/{label}.json",
        "generation": str(int(sha256(raw).hexdigest()[:12], 16) + 1),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _request() -> dict[str, object]:
    return operator.build_capture_request_v1(
        run_id="sevenpack-operator-test",
        candidate_authority_v2_root_identity=_identity(
            "fixed-root",
            uri=(
                f"gs://{candidate_v2.OUTPUT_BUCKET}/"
                f"{candidate_v2.OUTPUT_NAMESPACE}/fixture-run/"
                f"{candidate_v2.ROOT_FILENAME}"
            ),
        ),
        normalized_snapshot_terminal_identity=_identity(
            "normalized-terminal",
            uri=(
                f"{snapshot.OUTPUT_PREFIX}/fixture-run/"
                "snapshot-terminal.json"
            ),
        ),
    )


def _load_cli() -> object:
    spec = importlib.util.spec_from_file_location("seven_pack_capture_cli", CLI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_request_is_exact_seven_pack_inventory_and_local_validation_only() -> None:
    request = _request()
    assert request["warehouse_query_pack_ids"] == list(capture.WAREHOUSE_PACK_IDS)
    assert request["artifact_pack_ids"] == list(capture.ARTIFACT_PACK_IDS)
    assert len(request["output_uri_inventory"]) == 15
    assert request["output_uri_inventory"] == sorted(request["output_uri_inventory"])
    receipt = operator.validate_request_only_v1(request)
    assert receipt["local_validation_complete"] is True
    assert receipt["cloud_client_constructed"] is False
    assert receipt["warehouse_client_constructed"] is False
    assert receipt["external_read_count"] == 0
    assert receipt["publication_count"] == 0


def test_request_rejects_non_string_run_id_before_inventory_construction() -> None:
    with pytest.raises(capture.CorpusR6MatchupSevenPackCaptureV1Error):
        operator.build_capture_request_v1(
            run_id=12345678,  # type: ignore[arg-type]
            candidate_authority_v2_root_identity=_request()[
                "candidate_authority_v2_root_identity"
            ],
            normalized_snapshot_terminal_identity=_request()[
                "normalized_snapshot_terminal_identity"
            ],
        )


def test_request_has_no_caller_loose_manifest_identity_surface() -> None:
    parameters = set(inspect.signature(operator.build_capture_request_v1).parameters)
    assert parameters == {
        "run_id", "candidate_authority_v2_root_identity",
        "normalized_snapshot_terminal_identity",
    }
    assert "artifact_manifest_identities" not in _request()


def test_task0_derives_manifests_only_after_deep_terminal_reopen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    manifests = {
        source.FANTASY_POINTS_PACK: _identity("fp-manifest"),
        source.SIS_PACK: _identity("sis-manifest"),
    }
    calls: list[tuple[str, object]] = []

    def reopen(**kwargs: object) -> dict[str, object]:
        calls.append(("snapshot", kwargs["terminal_identity"]))
        return {
            "artifact_manifest_identities": manifests,
            "snapshot_reopen_sha256": "a" * 64,
        }

    def preflight(**kwargs: object) -> dict[str, object]:
        calls.append(("preflight", kwargs["artifact_manifest_identities"]))
        return {"input_preflight_sha256": "b" * 64}

    monkeypatch.setattr(operator.snapshot, "reopen_normalized_snapshot_v1", reopen)
    monkeypatch.setattr(capture, "preflight_seven_pack_inputs_v1", preflight)
    receipt = operator.run_task0_v1(
        request_value=request,
        read_exact=lambda _: b"unused",
        environment={operator.TASK0_ENABLE_ENV: "1"},
    )
    assert calls == [
        ("snapshot", request["normalized_snapshot_terminal_identity"]),
        ("preflight", manifests),
    ]
    assert receipt["artifact_manifest_identities"] == manifests
    assert receipt["normalized_snapshot_reopen_sha256"] == "a" * 64


@pytest.mark.parametrize(
    ("mode", "expected_variable"),
    [
        ("task0", operator.TASK0_ENABLE_ENV),
        ("publish", operator.PUBLISH_ENABLE_ENV),
        ("reopen", operator.REOPEN_ENABLE_ENV),
    ],
)
def test_every_external_mode_is_default_off(
    mode: str, expected_variable: str,
) -> None:
    with pytest.raises(
        operator.CorpusR6MatchupSevenPackCaptureOperatorV1Error,
        match=expected_variable,
    ):
        operator.require_mode_enabled_v1(mode, environment={})
    operator.require_mode_enabled_v1(
        mode, environment={expected_variable: "1"}
    )


def test_publish_guard_fails_before_any_callback() -> None:
    calls: list[str] = []
    with pytest.raises(
        operator.CorpusR6MatchupSevenPackCaptureOperatorV1Error,
        match="disabled",
    ):
        operator.run_publish_v1(
            request_value=_request(),
            implementation_authority={},
            query_warehouse=lambda _: calls.append("query") or {},
            read_exact=lambda _: calls.append("read") or b"",
            publish_create_once=lambda _uri, _raw: calls.append("write") or {},
            environment={},
        )
    assert calls == []


def test_task0_guard_fails_before_read_callback() -> None:
    calls: list[str] = []
    with pytest.raises(
        operator.CorpusR6MatchupSevenPackCaptureOperatorV1Error,
        match="disabled",
    ):
        operator.run_task0_v1(
            request_value=_request(),
            read_exact=lambda _: calls.append("read") or b"",
            environment={},
        )
    assert calls == []


def test_implementation_authority_binds_complete_local_runtime_surface(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    root = tmp_path.resolve()
    bytes_by_path = {
        path: f"fixture:{path}".encode() for path in capture.IMPLEMENTATION_PATHS
    }
    monkeypatch.setattr(
        operator,
        "_secure_current_file",
        lambda _root, relative_path: bytes_by_path[relative_path],
    )
    authority = operator.build_clean_implementation_authority_v1(
        repository_root=root,
        git_head=lambda _: "a" * 40,
        git_blob=lambda _root, _commit, path: bytes_by_path[path],
        git_status=lambda _root, _paths: b"",
    )
    assert [value["relative_path"] for value in authority["measurements"]] == list(
        capture.IMPLEMENTATION_PATHS
    )
    assert authority["working_tree_equals_commit_blobs"] is True
    assert authority["local_project_runtime_surface_complete"] is True
    assert authority["third_party_runtime_image_binding_present"] is False
    assert authority["third_party_runtime_image_binding_required_for_authority"] is True


def test_git_free_runtime_authority_remeasures_every_bound_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    bytes_by_path = {
        path: f"fixture:{path}".encode() for path in capture.IMPLEMENTATION_PATHS
    }
    monkeypatch.setattr(
        operator,
        "_secure_current_file",
        lambda _root, relative_path: bytes_by_path[relative_path],
    )
    authority = operator.build_provider_source_implementation_authority_v1(
        repository_root=tmp_path.resolve(), source_commit_sha="a" * 40
    )
    assert operator.reopen_runtime_implementation_authority_v1(
        repository_root=tmp_path.resolve(),
        implementation_authority=authority,
    ) == authority
    bytes_by_path[capture.CORE_MODULE_PATH] += b"changed"
    with pytest.raises(
        operator.CorpusR6MatchupSevenPackCaptureOperatorV1Error,
        match="runtime implementation bytes differ",
    ):
        operator.reopen_runtime_implementation_authority_v1(
            repository_root=tmp_path.resolve(),
            implementation_authority=authority,
        )


def test_public_publish_api_has_no_rows_fallback_or_policy_surface() -> None:
    parameters = set(inspect.signature(capture.publish_seven_pack_capture_v1).parameters)
    assert not parameters & {
        "warehouse_rows",
        "fantasy_points_rows",
        "sis_rows",
        "synthetic_rows",
        "outcome_reader",
        "score_reader",
        "graph_client",
        "policy_client",
    }


def test_cli_requires_an_explicit_subcommand() -> None:
    cli = _load_cli()
    with pytest.raises(SystemExit):
        cli._parser().parse_args([])


def test_cli_uses_isolated_bounded_gcs_transport() -> None:
    cli = _load_cli()
    assert hasattr(cli, "FixedGCSCaptureTransportV1")
    assert "corpus_r6_matchup_batch_candidate_authority_v1" not in inspect.getsource(
        cli
    )


def test_cli_transport_rejects_uninventoried_write_before_backend_call() -> None:
    cli = _load_cli()

    class Client:
        project = capture.PRODUCTION_PROJECT
        api_endpoint = cli.GCS_API_ENDPOINT
        universe_domain = cli.GCS_UNIVERSE_DOMAIN
        _is_emulator_set = False

        def __init__(self) -> None:
            self.bucket_calls = 0

        def bucket(self, _name: str) -> object:
            self.bucket_calls += 1
            raise AssertionError("backend must not be reached")

    client = Client()
    transport = cli.FixedGCSCaptureTransportV1(
        client, expected_write_uris=[]
    )
    with pytest.raises(cli.SevenPackCaptureCliError, match="exact write inventory"):
        transport.publish_create_once("gs://unexpected/object.json", b"{}")
    assert client.bucket_calls == 0


def test_cli_checks_mode_guard_before_gcs_client_construction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    cli = _load_cli()
    request_path = tmp_path / "request.json"
    request_path.write_bytes(source.canonical_json_bytes(_request()))
    calls: list[str] = []
    monkeypatch.delenv(operator.TASK0_ENABLE_ENV, raising=False)
    monkeypatch.setattr(
        cli,
        "_trusted_gcs_transport",
        lambda **_: calls.append("gcs") or None,
    )
    assert cli.main(["task0", "--request", str(request_path)]) == 2
    assert calls == []


def test_cli_capture_plan_freeze_is_default_off_before_gcs_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    cli = _load_cli()
    identity_path = tmp_path / "release-identity.json"
    identity_path.write_bytes(source.canonical_json_bytes(_identity("release")))
    calls: list[str] = []
    monkeypatch.delenv(cli.plan_bridge.FREEZE_ENABLE_ENV, raising=False)
    monkeypatch.setattr(
        cli, "_trusted_gcs_transport", lambda **_: calls.append("gcs") or None
    )
    assert cli.main([
        "freeze-capture-plan",
        "--release-identity", str(identity_path),
        "--repository-root", str(REPOSITORY_ROOT),
        "--confirm-freeze",
    ]) == 2
    assert calls == []
