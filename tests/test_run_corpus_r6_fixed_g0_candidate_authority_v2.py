from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import inspect
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import Any

import pytest

from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v1 as candidate_v1
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v2 as candidate
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_release_v2 as release
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from scripts import run_corpus_r6_fixed_g0_candidate_authority_v2 as operator
from tests import test_corpus_r6_fixed_g0_candidate_authority_release_v1 as v1_fixture
from tests import test_corpus_r6_fixed_g0_candidate_authority_release_v2 as v2_fixture


RUN_ID = "20260830-real-candidate-authority-v2"
HEAD = "a" * 40


def test_bound_api_commit_matches_pinned_file_hashes() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    for relative_path, expected_sha256 in operator._BOUND_FILES.items():
        tracked = subprocess.run(
            [
                "git",
                "-C",
                str(repository_root),
                "show",
                f"{operator.BOUND_API_COMMIT}:{relative_path}",
            ],
            check=True,
            capture_output=True,
        ).stdout
        assert sha256(tracked).hexdigest() == expected_sha256


def _context(
    outer_identity: dict[str, object] | None = None,
    outer_sha: str | None = None,
) -> operator.LocalAuthorityContextV2:
    outer = deepcopy(
        outer_identity
        or operator._EXPECTED_RECOVERY_RECEIPT["outer_attestation_identity"]
    )
    return operator.LocalAuthorityContextV2(
        repository_root=Path("/fixture/repository"),
        repository=SimpleNamespace(),
        clean_head=HEAD,
        origin_main=HEAD,
        module_origins={"operator": operator.OPERATOR_PATH},
        recovery_receipt_file={
            "relative_path": operator.RECOVERY_RECEIPT_PATH,
            "sha256": operator.RECOVERY_RECEIPT_FILE_SHA256,
            "bytes": operator.RECOVERY_RECEIPT_BYTES,
        },
        catalog_recovery_outer_identity=outer,
        catalog_recovery_outer_attestation_sha256=(
            outer_sha
            or str(
                operator._EXPECTED_RECOVERY_RECEIPT[
                    "outer_attestation_sha256"
                ]
            )
        ),
    )


def _material(context: operator.LocalAuthorityContextV2) -> dict[str, object]:
    artifacts = [
        v1_fixture._candidate_artifact(ordinal)
        for ordinal in range(source.TASK_COUNT)
    ]
    sidecars = [
        v1_fixture._sidecar(ordinal, artifacts[ordinal])
        for ordinal in range(source.TASK_COUNT)
    ]
    predecessors = [
        {
            "source_task_ordinal": ordinal,
            "catalog_binding": {"fixture": ordinal},
        }
        for ordinal in range(source.TASK_COUNT)
    ]
    body: dict[str, object] = {
        "schema_version": candidate.MATERIAL_SCHEMA,
        "task_count": source.TASK_COUNT,
        "arm_result_count": source.TASK_COUNT * candidate_v1.EXPECTED_ARM_COUNT,
        "candidate_artifacts": artifacts,
        "candidate_artifact_manifest_sha256": operator.canonical_sha256(artifacts),
        "lineage_sidecars": sidecars,
        "lineage_sidecar_manifest_sha256": operator.canonical_sha256(sidecars),
        "slate_predecessor_bindings": predecessors,
        "slate_predecessor_manifest_sha256": operator.canonical_sha256(
            predecessors
        ),
        "catalog_inner_object_count": 110,
        "catalog_recovery_outer_identity": dict(
            context.catalog_recovery_outer_identity
        ),
        "catalog_recovery_outer_attestation_sha256": (
            context.catalog_recovery_outer_attestation_sha256
        ),
        "candidate_filter_applied": False,
        "selected_rosters_used_as_population": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }
    body["candidate_material_sha256"] = operator.canonical_sha256(body)
    return body


def _memory_store() -> tuple[v1_fixture.MemoryExactStore, SimpleNamespace]:
    memory = v1_fixture.MemoryExactStore()
    return memory, SimpleNamespace(
        read_exact=memory.read_exact,
        publish_create_once=memory.create_once,
    )


def _install_public_context(
    monkeypatch: pytest.MonkeyPatch,
    *,
    context: operator.LocalAuthorityContextV2,
    store: object,
) -> None:
    monkeypatch.setattr(operator, "_prepare_local_context", lambda _root: context)
    monkeypatch.setattr(operator, "_default_store_factory", lambda project: store)


def test_public_signatures_expose_no_inner_outer_payload_or_root_bypass() -> None:
    assert tuple(inspect.signature(operator.run_prepublish_production_v2).parameters) == (
        "run_id",
        "project",
        "repository_root",
        "execute",
    )
    assert tuple(inspect.signature(operator.run_publish_production_v2).parameters) == (
        "run_id",
        "project",
        "repository_root",
        "execute",
        "confirm_165_object_publication",
    )
    assert tuple(inspect.signature(operator.run_reopen_production_v2).parameters) == (
        "root_identity_file",
        "project",
        "repository_root",
        "execute",
    )
    banned = {
        "catalog_replay_receipt_identity",
        "catalog_recovery_outer_identity",
        "candidate_payload",
        "candidate_material",
        "root_identity",
        "read_exact",
        "publish_create_once",
        "backend_factory",
        "store_factory",
    }
    for function in (
        operator.run_prepublish_production_v2,
        operator.run_publish_production_v2,
        operator.run_reopen_production_v2,
    ):
        assert banned.isdisjoint(inspect.signature(function).parameters)


def test_bound_reopen_api_signature_gate_is_exact() -> None:
    operator._require_bound_api_signatures()
    assert tuple(
        inspect.signature(
            release.reopen_fixed_g0_candidate_authority_release_v2
        ).parameters
    ) == (
        "root_identity",
        "repository_root",
        "read_exact",
        "git_head",
        "git_blob",
        "git_status",
    )


def test_exact_gcs_surface_has_no_list_current_overwrite_or_delete() -> None:
    public = {
        name
        for name, value in inspect.getmembers(
            operator.ExactGCSStoreV2, predicate=callable
        )
        if not name.startswith("_")
    }
    assert public == {"read_exact", "publish_create_once"}
    for forbidden in (
        "list",
        "list_blobs",
        "resolve_current",
        "open_known",
        "overwrite",
        "delete",
    ):
        assert not hasattr(operator.ExactGCSStoreV2, forbidden)


def test_fixed_receipt_validation_rejects_alternate_authority() -> None:
    repository = SimpleNamespace(_run=lambda _args, label: b"")
    outer, outer_sha = operator._validate_recovery_receipt(
        deepcopy(operator._EXPECTED_RECOVERY_RECEIPT),
        repository=repository,
        current_head=HEAD,
    )
    assert outer == operator._EXPECTED_RECOVERY_RECEIPT[
        "outer_attestation_identity"
    ]
    assert outer_sha == operator._EXPECTED_RECOVERY_RECEIPT[
        "outer_attestation_sha256"
    ]

    alternate = deepcopy(operator._EXPECTED_RECOVERY_RECEIPT)
    alternate["outer_attestation_identity"]["generation"] = "1788047679701106"
    with pytest.raises(
        operator.RunCorpusR6FixedG0CandidateAuthorityV2Error,
        match="differs from the fixed receipt",
    ):
        operator._validate_recovery_receipt(
            alternate,
            repository=repository,
            current_head=HEAD,
        )


def test_strict_receipt_parser_rejects_duplicate_and_nonfinite_json() -> None:
    with pytest.raises(
        operator.RunCorpusR6FixedG0CandidateAuthorityV2Error,
        match="repeats JSON key",
    ):
        operator._parse_strict_json(b'{"complete":true,"complete":false}', label="x")
    with pytest.raises(
        operator.RunCorpusR6FixedG0CandidateAuthorityV2Error,
        match="non-finite",
    ):
        operator._parse_strict_json(b'{"x":NaN}', label="x")


class _FakeRepository:
    def __init__(
        self,
        root: Path,
        *,
        receipt_raw: bytes,
        dirty: bool = False,
        origin_main: str = HEAD,
    ) -> None:
        self.repository_root = root
        self.receipt_raw = receipt_raw
        self.dirty = dirty
        self.origin_main = origin_main

    def require_current_clean_head(self) -> str:
        if self.dirty:
            raise RuntimeError("dirty")
        return HEAD

    def _run(self, args: list[str], *, label: str) -> bytes:
        del label
        if args[:2] == ["symbolic-ref", "-q"]:
            raise RuntimeError("detached")
        if args[:2] == ["rev-parse", "--verify"]:
            return f"{self.origin_main}\n".encode()
        if args[:2] == ["merge-base", "--is-ancestor"]:
            return b""
        if args and args[0] == "status":
            return b""
        raise AssertionError(args)

    def read_tracked(self, commit: str, relative_path: str) -> bytes:
        del commit
        if relative_path == operator.OPERATOR_PATH:
            return b"tracked operator"
        if relative_path == operator.RECOVERY_RECEIPT_PATH:
            return self.receipt_raw
        raise AssertionError(relative_path)


def _local_root_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    dirty: bool = False,
    origin_main: str = HEAD,
) -> tuple[Path, bytes]:
    root = tmp_path.resolve()
    operator_path = root / operator.OPERATOR_PATH
    receipt_path = root / operator.RECOVERY_RECEIPT_PATH
    operator_path.parent.mkdir(parents=True)
    receipt_path.parent.mkdir(parents=True)
    operator_path.write_bytes(b"tracked operator")
    receipt_raw = (
        Path(__file__).resolve().parents[1] / operator.RECOVERY_RECEIPT_PATH
    ).read_bytes()
    receipt_path.write_bytes(receipt_raw)
    repository = _FakeRepository(
        root,
        receipt_raw=receipt_raw,
        dirty=dirty,
        origin_main=origin_main,
    )
    monkeypatch.setattr(
        operator.adapter,
        "SubprocessGitRepositoryV1",
        lambda _root: repository,
    )
    monkeypatch.setattr(operator, "_verify_module_origins", lambda _root: {})
    monkeypatch.setattr(
        operator,
        "_require_unchanged_bound_file",
        lambda **_kwargs: None,
    )
    return root, receipt_raw


def test_local_context_requires_clean_detached_head_equal_origin_main(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root, _ = _local_root_fixture(monkeypatch, tmp_path)
    context = operator._prepare_local_context(root)
    assert context.clean_head == context.origin_main == HEAD
    assert context.catalog_recovery_outer_identity == (
        operator._EXPECTED_RECOVERY_RECEIPT["outer_attestation_identity"]
    )


@pytest.mark.parametrize(
    ("dirty", "origin", "message"),
    [
        (True, HEAD, "tracked-clean"),
        (False, "b" * 40, "equal origin/main"),
    ],
)
def test_dirty_or_diverged_git_fails_closed_before_cloud_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    dirty: bool,
    origin: str,
    message: str,
) -> None:
    root, _ = _local_root_fixture(
        monkeypatch,
        tmp_path,
        dirty=dirty,
        origin_main=origin,
    )
    calls: list[str] = []
    monkeypatch.setattr(
        operator,
        "_default_store_factory",
        lambda _project: calls.append("client"),
    )
    with pytest.raises(
        operator.RunCorpusR6FixedG0CandidateAuthorityV2Error,
        match=message,
    ):
        operator.run_prepublish_production_v2(
            run_id=RUN_ID,
            project=operator.PROJECT,
            repository_root=root,
            execute=True,
        )
    assert calls == []


def test_current_receipt_byte_change_fails_before_cloud_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root, _ = _local_root_fixture(monkeypatch, tmp_path)
    (root / operator.RECOVERY_RECEIPT_PATH).write_bytes(b"{}")
    calls: list[str] = []
    monkeypatch.setattr(
        operator,
        "_default_store_factory",
        lambda _project: calls.append("client"),
    )
    with pytest.raises(
        operator.RunCorpusR6FixedG0CandidateAuthorityV2Error,
        match="receipt bytes differ",
    ):
        operator.run_prepublish_production_v2(
            run_id=RUN_ID,
            project=operator.PROJECT,
            repository_root=root,
            execute=True,
        )
    assert calls == []


def test_prepublish_real_derivation_validates_all_54_without_write_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context()
    material = _material(context)
    calls: list[dict[str, object]] = []

    def derive(**kwargs: object) -> dict[str, object]:
        assert "publish_create_once" not in kwargs
        assert kwargs["catalog_recovery_outer_identity"] == (
            context.catalog_recovery_outer_identity
        )
        calls.append(dict(kwargs))
        return deepcopy(material)

    monkeypatch.setattr(
        operator.candidate, "derive_fixed_g0_candidate_material_v2", derive
    )
    store = SimpleNamespace(read_exact=lambda _identity: b"")
    _install_public_context(monkeypatch, context=context, store=store)
    receipt = operator.run_prepublish_production_v2(
        run_id=RUN_ID,
        project=operator.PROJECT,
        repository_root=context.repository_root,
        execute=True,
    )

    assert len(calls) == 1
    assert receipt["complete"] is True
    assert receipt["task_count"] == 54
    assert receipt["validated_source_task_ordinals"] == list(range(54))
    assert receipt["write_capability_exposed"] is False
    assert receipt["cloud_mutation_performed"] is False
    assert receipt["outcome_data_accessed"] is False
    retained_hash = receipt.pop("operator_receipt_sha256")
    assert retained_hash == operator.canonical_sha256(receipt)


def test_prepublish_rejects_one_bad_artifact_among_54(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context()
    material = _material(context)
    material["candidate_artifacts"][53]["source_task_ordinal"] = 0
    material["candidate_material_sha256"] = operator.canonical_sha256(
        {
            key: value
            for key, value in material.items()
            if key != "candidate_material_sha256"
        }
    )
    monkeypatch.setattr(
        operator.candidate,
        "derive_fixed_g0_candidate_material_v2",
        lambda **_kwargs: material,
    )
    _install_public_context(
        monkeypatch,
        context=context,
        store=SimpleNamespace(read_exact=lambda _identity: b""),
    )
    with pytest.raises(Exception):
        operator.run_prepublish_production_v2(
            run_id=RUN_ID,
            project=operator.PROJECT,
            repository_root=context.repository_root,
            execute=True,
        )


def test_publication_audit_enforces_exact_165_sequence_and_v2_root_last() -> None:
    identities: list[dict[str, object]] = []

    def publish(uri: str, raw: bytes) -> dict[str, object]:
        identity = {
            "uri": uri,
            "generation": str(len(identities) + 1),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        identities.append(identity)
        return identity

    audit = operator.PublicationAuditV2(
        run_id=RUN_ID, publish_create_once=publish
    )
    for ordinal, uri in enumerate(audit.expected_uris):
        raw = operator.canonical_json_bytes({"ordinal": ordinal})
        identity = audit.publish_create_once(uri, raw)
    audit.require_complete(identity)

    prefix = release.output_prefix_for_run_v2(RUN_ID)
    assert len(identities) == 165
    assert identities[-1]["uri"] == f"{prefix}{release.ROOT_FILENAME}"
    assert f"{prefix}candidate-authority-release.json" not in {
        row["uri"] for row in identities
    }
    with pytest.raises(
        operator.RunCorpusR6FixedG0CandidateAuthorityV2Error,
        match="more than 165",
    ):
        audit.publish_create_once(
            f"{prefix}extra.json", operator.canonical_json_bytes({"extra": True})
        )


def test_publication_audit_rejects_wrong_first_uri_before_provider_mutation() -> None:
    calls: list[str] = []
    audit = operator.PublicationAuditV2(
        run_id=RUN_ID,
        publish_create_once=lambda uri, _raw: calls.append(uri),
    )
    prefix = release.output_prefix_for_run_v2(RUN_ID)
    with pytest.raises(
        operator.RunCorpusR6FixedG0CandidateAuthorityV2Error,
        match="URI/order differs",
    ):
        audit.publish_create_once(
            f"{prefix}candidate-authority-release.json",
            operator.canonical_json_bytes({"legacy": True}),
        )
    assert calls == []


@pytest.mark.parametrize(("successful_before_failure", "mutated"), [(0, False), (3, True)])
def test_partial_publication_receipt_truthfully_reports_collision_state(
    monkeypatch: pytest.MonkeyPatch,
    successful_before_failure: int,
    mutated: bool,
) -> None:
    context = _context()
    expected = operator._expected_publication_uris(RUN_ID)
    store_rows: dict[tuple[str, str], bytes] = {}
    create_calls = 0

    def create_once(uri: str, raw: bytes) -> dict[str, object]:
        nonlocal create_calls
        if create_calls == successful_before_failure:
            raise RuntimeError("fixture collision")
        create_calls += 1
        identity = {
            "uri": uri,
            "generation": str(create_calls),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        store_rows[(uri, str(create_calls))] = raw
        return identity

    def fail_publish(**kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        publish = kwargs["publish_create_once"]
        for ordinal in range(successful_before_failure + 1):
            publish(
                expected[ordinal],
                operator.canonical_json_bytes({"ordinal": ordinal}),
            )
        raise AssertionError("unreachable")

    monkeypatch.setattr(
        operator.release,
        "publish_fixed_g0_candidate_authority_release_v2",
        fail_publish,
    )
    _install_public_context(
        monkeypatch,
        context=context,
        store=SimpleNamespace(
            read_exact=lambda identity: store_rows[
                (str(identity["uri"]), str(identity["generation"]))
            ],
            publish_create_once=create_once,
        ),
    )
    with pytest.raises(
        operator.RunCorpusR6FixedG0CandidateAuthorityV2Error
    ) as raised:
        operator.run_publish_production_v2(
            run_id=RUN_ID,
            project=operator.PROJECT,
            repository_root=context.repository_root,
            execute=True,
            confirm_165_object_publication=True,
        )
    partial = raised.value.partial_receipt
    assert partial is not None
    assert partial["create_once_success_count"] == successful_before_failure
    assert partial["create_once_attempt_count"] == successful_before_failure + 1
    assert partial["cloud_mutation_performed"] is mutated
    assert partial["v2_root_published"] is False
    assert partial["legacy_v1_root_published"] is False
    assert partial["complete"] is False


def test_real_release_fixture_publishes_165_then_independently_reopens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory, store = _memory_store()
    state = v2_fixture._install_core_fixture(monkeypatch, store=memory)
    binding = state["binding"]
    context = _context(
        deepcopy(binding["catalog_recovery_outer_identity"]),
        str(binding["catalog_recovery_outer_attestation_sha256"]),
    )
    _install_public_context(monkeypatch, context=context, store=store)

    receipt = operator.run_publish_production_v2(
        run_id=RUN_ID,
        project=operator.PROJECT,
        repository_root=context.repository_root,
        execute=True,
        confirm_165_object_publication=True,
    )
    prefix = release.output_prefix_for_run_v2(RUN_ID)
    assert len(memory.create_calls) == 165
    assert memory.create_calls[-1] == f"{prefix}{release.ROOT_FILENAME}"
    assert f"{prefix}candidate-authority-release.json" not in memory.create_calls
    assert receipt["create_once_success_count"] == 165
    assert receipt["v2_root_published_last"] is True
    assert receipt["independent_full_v2_reopen_complete"] is True
    assert receipt["cloud_mutation_performed"] is True
    assert receipt["unrelated_cloud_mutation_performed"] is False


def test_reopen_rejects_legacy_root_before_context_or_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prefix = release.output_prefix_for_run_v2(RUN_ID)
    raw = operator.canonical_json_bytes(
        {
            "uri": f"{prefix}candidate-authority-release.json",
            "generation": "1",
            "sha256": "a" * 64,
            "bytes": 1,
        }
    )
    path = (tmp_path / "legacy.identity.json").resolve()
    path.write_bytes(raw + b"\n")
    calls: list[str] = []
    monkeypatch.setattr(
        operator,
        "_prepare_local_context",
        lambda _root: calls.append("context"),
    )
    monkeypatch.setattr(
        operator,
        "_default_store_factory",
        lambda _project: calls.append("client"),
    )
    with pytest.raises(
        operator.RunCorpusR6FixedG0CandidateAuthorityV2Error,
        match="legacy v1 root rejected",
    ):
        operator.run_reopen_production_v2(
            root_identity_file=path,
            project=operator.PROJECT,
            repository_root=Path("/unused"),
            execute=True,
        )
    assert calls == []


def test_reopen_accepts_only_direct_canonical_generation_pinned_identity(
    tmp_path: Path,
) -> None:
    prefix = release.output_prefix_for_run_v2(RUN_ID)
    identity = {
        "uri": f"{prefix}{release.ROOT_FILENAME}",
        "generation": "9",
        "sha256": "a" * 64,
        "bytes": 7,
    }
    direct = (tmp_path / "direct.json").resolve()
    direct.write_bytes(operator.canonical_json_bytes(identity) + b"\n")
    assert operator._load_v2_root_identity_file(direct) == (identity, RUN_ID)

    wrapped = (tmp_path / "wrapped.json").resolve()
    wrapped.write_bytes(
        operator.canonical_json_bytes({"root_identity": identity}) + b"\n"
    )
    with pytest.raises(
        operator.RunCorpusR6FixedG0CandidateAuthorityV2Error,
        match="directly contain only one identity",
    ):
        operator._load_v2_root_identity_file(wrapped)


def test_public_read_only_reopen_calls_full_v2_reopener_without_writes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    memory, store = _memory_store()
    state = v2_fixture._install_core_fixture(monkeypatch, store=memory)
    binding = state["binding"]
    context = _context(
        deepcopy(binding["catalog_recovery_outer_identity"]),
        str(binding["catalog_recovery_outer_attestation_sha256"]),
    )
    _install_public_context(monkeypatch, context=context, store=store)
    publication = operator.run_publish_production_v2(
        run_id=RUN_ID,
        project=operator.PROJECT,
        repository_root=context.repository_root,
        execute=True,
        confirm_165_object_publication=True,
    )
    root_identity = publication["candidate_authority_root_identity"]
    identity_file = (tmp_path / "root.identity.json").resolve()
    identity_file.write_bytes(
        operator.canonical_json_bytes(root_identity) + b"\n"
    )
    create_count = len(memory.create_calls)

    reopened = operator.run_reopen_production_v2(
        root_identity_file=identity_file,
        project=operator.PROJECT,
        repository_root=context.repository_root,
        execute=True,
    )
    assert len(memory.create_calls) == create_count
    assert reopened["candidate_authority_root_identity"] == root_identity
    assert reopened["full_v2_predecessor_replay_complete"] is True
    assert reopened["write_capability_exposed"] is False
    assert reopened["cloud_mutation_performed"] is False
    assert reopened["outcome_data_accessed"] is False


def test_default_off_cli_emits_canonical_failure_before_context_or_client(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        operator,
        "_prepare_local_context",
        lambda _root: calls.append("context"),
    )
    monkeypatch.setattr(
        operator,
        "_default_store_factory",
        lambda _project: calls.append("client"),
    )
    assert operator.main(
        [
            "prepublish",
            "--run-id",
            RUN_ID,
            "--project",
            operator.PROJECT,
            "--repository-root",
            "/tmp/unused-candidate-v2-worktree",
        ]
    ) == 1
    raw = capfd.readouterr().out.encode()
    assert raw.endswith(b"\n")
    body = json.loads(raw)
    assert operator.canonical_json_bytes(body) + b"\n" == raw
    assert body["complete"] is False
    assert body["cloud_mutation_performed"] is False
    assert body["outcome_data_accessed"] is False
    assert calls == []
