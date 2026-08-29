from __future__ import annotations

from hashlib import sha256
import inspect
from pathlib import Path
import subprocess
from types import MappingProxyType, SimpleNamespace

import pytest

from nfl_dfs.research import corpus_r6_fixed_g0_catalog_recovery_v1 as core
from scripts import run_corpus_r6_fixed_g0_catalog_recovery_v1 as operator
from scripts import run_corpus_r6_fixed_g0_catalog_recovery_focused_v1 as focused_launcher


def _identity_from_raw(uri: str, raw: bytes, generation: str = "17") -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _json_identity(uri: str, body: object, generation: str = "17") -> tuple[dict[str, object], bytes]:
    raw = core.canonical_json_bytes(body)
    return _identity_from_raw(uri, raw, generation), raw


def _measurements() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for ordinal, path in enumerate(core.IMPLEMENTATION_PATHS, start=1):
        rows.append({
            "relative_path": path,
            "sha256": f"{ordinal:064x}",
            "bytes": ordinal,
        })
    catalog_row = next(
        row
        for row in rows
        if row["relative_path"] == core.adapter.FIXED_CATALOG_MODULE_PATH
    )
    catalog_row["sha256"] = core.adapter.FIXED_CATALOG_MODULE_SHA256
    catalog_row["bytes"] = core.adapter.FIXED_CATALOG_MODULE_BYTES
    return rows


class _ExactStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], tuple[dict[str, object], bytes]] = {}
        self.resolve_calls = 0
        self.create_calls = 0

    def seed(self, identity: dict[str, object], raw: bytes) -> None:
        self.rows[(str(identity["uri"]), str(identity["generation"]))] = (identity, raw)

    def reload_generation(self, uri: str, generation: str) -> dict[str, object]:
        return dict(self.rows[(uri, generation)][0])

    def download_generation(self, uri: str, generation: str) -> bytes:
        return self.rows[(uri, generation)][1]

    def resolve_current(self, uri: str) -> dict[str, object]:
        self.resolve_calls += 1
        matches = [row for (row_uri, _), row in self.rows.items() if row_uri == uri]
        if not matches:
            raise core.adapter.ObjectNotFoundV1Error("missing")
        return dict(matches[-1][0])

    def create_if_absent(self, uri: str, raw: bytes, precondition: int) -> dict[str, object]:
        del uri, raw, precondition
        self.create_calls += 1
        raise AssertionError("smoke store cannot create")

    def transport(self) -> core.adapter.GenerationTransportV1:
        return core.adapter.GenerationTransportV1(
            reload_generation=self.reload_generation,
            download_generation=self.download_generation,
            resolve_current=self.resolve_current,
            create_if_absent=self.create_if_absent,
        )


def _smoke_fixture() -> tuple[SimpleNamespace, _ExactStore, list[dict[str, object]]]:
    acceptance, acceptance_raw = _json_identity(
        "gs://frozen-inputs/task-acceptance.json", {"kind": "acceptance"}
    )
    carrier, carrier_raw = _json_identity(
        "gs://frozen-inputs/task-carrier.json", {"kind": "carrier"}
    )
    panel_body = {
        "accepted_slates": [{
            "task_acceptance_identity": acceptance,
            "carrier_identity": carrier,
        }]
    }
    panel, panel_raw = _json_identity(
        str(core.adapter.FIXED_PINS.panel_identity["uri"]), panel_body
    )
    lane_terminal, lane_terminal_raw = _json_identity(
        "gs://frozen-inputs/lane-terminal.json", {"kind": "lane-terminal"}
    )
    lane_completion, lane_completion_raw = _json_identity(
        "gs://frozen-inputs/lane-completion.json", {"kind": "lane-completion"}
    )
    later, later_raw = _json_identity(
        "gs://frozen-inputs/later-source.json", {"kind": "later"}
    )
    source, source_raw = _json_identity(
        "gs://frozen-inputs/source-completion.json", {"kind": "source"}
    )
    ordered = [
        panel,
        lane_terminal,
        lane_completion,
        later,
        source,
        acceptance,
        carrier,
    ]
    store = _ExactStore()
    for identity, raw in zip(
        ordered,
        [
            panel_raw,
            lane_terminal_raw,
            lane_completion_raw,
            later_raw,
            source_raw,
            acceptance_raw,
            carrier_raw,
        ],
        strict=True,
    ):
        store.seed(identity, raw)
    inputs = SimpleNamespace(
        source_task_ordinals=(0,),
        task_acceptance_body_count=1,
        carrier_body_count=1,
        structural_players=(({"player_id": "p0"},),),
        task_evidence_bindings=({
            "task_acceptance_identity": acceptance,
            "carrier_identity": carrier,
        },),
        tracked_root_binding={"panel_object_identity": panel},
        lane_terminal_identities=(lane_terminal,),
        lane_completion_identities=(lane_completion,),
        later_source_identity=later,
        source_completion_identity=source,
        pin_set_sha256="a" * 64,
    )
    return inputs, store, ordered


def test_smoke_emits_exact_allowlisted_read_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs, store, ordered = _smoke_fixture()
    monkeypatch.setattr(
        operator,
        "_planned_source_audit_v1",
        lambda **_kwargs: core.TransportAuditV1(
            store.transport(), mode="read_only", allowed_read_identities=ordered
        ),
    )

    def derive(**kwargs: object) -> SimpleNamespace:
        transport = kwargs["transport"]
        assert kwargs["task_evidence_ordinals"] == (0,)
        for identity in [ordered[0], *ordered]:
            transport.reload_generation(identity["uri"], identity["generation"])
            transport.download_generation(identity["uri"], identity["generation"])
        return inputs

    monkeypatch.setattr(operator.adapter, "_derive_pinned_projection_inputs_v1", derive)
    evidence = operator.run_smoke_v1(
        repository=SimpleNamespace(read_tracked=lambda *_args: b"tracked"),
        source_commit_sha="b" * 40,
        implementation_measurements=_measurements(),
        module_origins=core.expected_module_origins_v1(),
        base_review=object(),
        base_transport=store.transport(),
    )

    assert evidence["transport_audit"]["generation_reload_identities"] == [ordered[0], *ordered]
    assert evidence["transport_audit"]["generation_download_identities"] == [ordered[0], *ordered]
    assert evidence["transport_audit"]["denied_read_attempts"] == []
    assert evidence["world_matrix_bodies_read"] is False
    assert evidence["world_schedule_bodies_read"] is False
    assert evidence["result_object_bodies_read"] is False


@pytest.mark.parametrize("role", ["world-matrix", "world-schedule", "result-object"])
def test_transport_runtime_denies_forbidden_unallowlisted_body(role: str) -> None:
    safe, safe_raw = _json_identity("gs://frozen-inputs/safe.json", {"safe": True})
    forbidden, forbidden_raw = _json_identity(
        f"gs://frozen-inputs/{role}.json", {"forbidden": role}
    )
    store = _ExactStore()
    store.seed(safe, safe_raw)
    store.seed(forbidden, forbidden_raw)
    audit = core.TransportAuditV1(
        store.transport(), mode="read_only", allowed_read_identities=[safe]
    )
    transport = audit.transport()

    with pytest.raises(
        core.CorpusR6FixedG0CatalogRecoveryV1Error,
        match="outside the exact runtime allowlist",
    ):
        transport.reload_generation(forbidden["uri"], forbidden["generation"])
    assert audit.snapshot_v1()["denied_read_attempts"] == [{
        "uri": forbidden["uri"],
        "generation": forbidden["generation"],
    }]


def test_panel_body_cannot_auto_authorize_unplanned_source_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forbidden_raw = b"forbidden"
    forbidden = _identity_from_raw("gs://frozen-inputs/world-object", forbidden_raw)
    panel_raw = core.canonical_json_bytes(
        {"accepted_slates": [{"carrier_identity": forbidden}]}
    )
    panel = _identity_from_raw("gs://frozen-inputs/panel", panel_raw)
    allowed_raw = b"allowed"
    allowed = _identity_from_raw("gs://frozen-inputs/allowed", allowed_raw)
    store = _ExactStore()
    for identity, raw in (
        (panel, panel_raw), (allowed, allowed_raw), (forbidden, forbidden_raw)
    ):
        store.seed(identity, raw)
    monkeypatch.setattr(
        core.adapter, "FIXED_PINS", SimpleNamespace(panel_identity=panel)
    )
    audit = core.TransportAuditV1(
        store.transport(), mode="read_only", allowed_read_identities=[panel]
    )
    core.adapter.read_generation_exact_v1(panel, transport=audit.transport())
    audit.bind_planned_read_identities_v1([panel, allowed])
    with pytest.raises(
        core.CorpusR6FixedG0CatalogRecoveryV1Error,
        match="outside the exact runtime allowlist",
    ):
        audit.transport().download_generation(
            forbidden["uri"], forbidden["generation"]
        )


def test_read_only_transport_denies_output_contact_before_base() -> None:
    safe, safe_raw = _json_identity("gs://frozen-inputs/safe.json", {"safe": True})
    store = _ExactStore()
    store.seed(safe, safe_raw)
    transport = core.TransportAuditV1(
        store.transport(), mode="read_only", allowed_read_identities=[safe]
    ).transport()
    with pytest.raises(core.CorpusR6FixedG0CatalogRecoveryV1Error):
        transport.resolve_current(core.OUTER_ATTESTATION_URI)
    with pytest.raises(core.CorpusR6FixedG0CatalogRecoveryV1Error):
        transport.create_if_absent(core.OUTER_ATTESTATION_URI, b"x", 0)
    assert store.resolve_calls == 0
    assert store.create_calls == 0


def test_publish_transport_denies_unplanned_and_premature_outer_zero_contact() -> None:
    store = _ExactStore()
    audit = core.TransportAuditV1(
        store.transport(),
        mode="publish",
        allowed_read_identities=[],
        planned_output_uris=core.planned_inner_output_uris_v1(),
    )
    transport = audit.transport()
    for uri in (
        f"{core.adapter.FIXED_CATALOG_NAMESPACE}unexpected.json",
        core.OUTER_ATTESTATION_URI,
    ):
        with pytest.raises(
            core.CorpusR6FixedG0CatalogRecoveryV1Error,
            match="outside the active exact publication plan",
        ):
            transport.resolve_current(uri)
        with pytest.raises(
            core.CorpusR6FixedG0CatalogRecoveryV1Error,
            match="outside the active exact publication plan",
        ):
            transport.create_if_absent(uri, b"x", 0)
    planned = core.planned_inner_output_uris_v1()[0]
    with pytest.raises(
        core.CorpusR6FixedG0CatalogRecoveryV1Error,
        match="not prebound",
    ):
        transport.resolve_current(planned)
    with pytest.raises(
        core.CorpusR6FixedG0CatalogRecoveryV1Error,
        match="not prebound",
    ):
        transport.create_if_absent(planned, b"x", 0)
    assert store.resolve_calls == 0
    assert store.create_calls == 0


def test_reopen_rejects_nonfixed_outer_before_context_or_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrong = _identity_from_raw(
        f"{core.adapter.FIXED_CATALOG_NAMESPACE}not-the-root.json", b"x"
    )
    monkeypatch.setattr(
        operator,
        "_clean_context",
        lambda: pytest.fail("repository/source contact must not occur"),
    )
    with pytest.raises(
        operator.RunCorpusR6FixedG0CatalogRecoveryV1Error,
        match="URI differs",
    ):
        operator.run_reopen_production_v1(
            outer_identity=wrong,
            backend_factory=lambda: pytest.fail("backend must not be constructed"),
        )


def test_runtime_origin_check_rejects_foreign_runner(tmp_path: Path) -> None:
    with pytest.raises(
        core.CorpusR6FixedG0CatalogRecoveryV1Error,
        match="runtime module origins differ",
    ):
        core.verify_module_origins_v1(
            core.REPOSITORY_ROOT, runner_file=tmp_path / "foreign-runner.py"
        )
    with pytest.raises(RuntimeError, match="pytest import escaped"):
        focused_launcher._require_trusted_pytest_origin(
            str(core.REPOSITORY_ROOT / "pytest/__init__.py")
        )
    with pytest.raises(RuntimeError, match="project import escaped"):
        focused_launcher._require_exact_project_origin(
            str(core.REPOSITORY_ROOT / "nfl_dfs/__init__.py"),
            core.REPOSITORY_ROOT / core.NFL_DFS_INIT_PATH,
        )
    hostile_src = tmp_path / "src"
    hostile_src.mkdir()
    marker = tmp_path / "shadow-executed"
    (hostile_src / "scripts.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        "import sys, types\n"
        "__file__ = '/forged/repository/scripts/__init__.py'\n"
        "sys.modules['scripts.run_corpus_r6_fixed_g0_catalog_recovery_v1'] = "
        "types.ModuleType('scripts.run_corpus_r6_fixed_g0_catalog_recovery_v1')\n"
    )
    with pytest.raises(RuntimeError, match="project import escaped"):
        focused_launcher._require_exact_project_origin(
            str(hostile_src / "scripts.py"),
            core.REPOSITORY_ROOT / core.SCRIPTS_INIT_PATH,
        )
    assert Path(focused_launcher._scripts.__file__).resolve() == (
        core.REPOSITORY_ROOT / core.SCRIPTS_INIT_PATH
    ).resolve()
    assert Path(focused_launcher._runner.__file__).resolve() == (
        core.REPOSITORY_ROOT / core.RUNNER_PATH
    ).resolve()
    hostile_launch = subprocess.run(
        [
            str(core.REPOSITORY_ROOT / ".venv/bin/python"),
            "-I",
            "-c",
            (
                "import runpy,sys;"
                f"sys.path.insert(0,{str(hostile_src)!r});"
                f"sys.argv=[{str(core.REPOSITORY_ROOT / core.FOCUSED_WRAPPER_PATH)!r},'--definitely-invalid'];"
                f"runpy.run_path({str(core.REPOSITORY_ROOT / core.FOCUSED_WRAPPER_PATH)!r},run_name='__main__')"
            ),
        ],
        cwd=core.REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert hostile_launch.returncode != 0
    assert not marker.exists()
    assert focused_launcher.sys.path.index(str(focused_launcher.SOURCE_ROOT)) < (
        focused_launcher.sys.path.index(str(focused_launcher.REPOSITORY_ROOT))
    )


def _authority(
    *,
    current_head: str = "e" * 40,
    final_commit: str = "d" * 40,
    marker_commit: str = "e" * 40,
) -> tuple[core.PublicationCapabilityV1, core.TrackedAttemptBindingV1]:
    measurements = _measurements()
    implementation_commit = "b" * 40
    review_commit = "c" * 40
    review_file = {
        "relative_path": core.REVIEW_LOCK_PATH,
        "sha256": "1" * 64,
        "bytes": 1,
    }
    final_file = {
        "relative_path": core.FINAL_LOCK_PATH,
        "sha256": "2" * 64,
        "bytes": 1,
    }
    smoke_file = {
        "relative_path": core.SMOKE_EVIDENCE_PATH,
        "sha256": "3" * 64,
        "bytes": 1,
    }
    empty_file = {
        "relative_path": core.EMPTY_PREFIX_EVIDENCE_PATH,
        "sha256": "4" * 64,
        "bytes": 1,
    }
    review = {"recovery_review_lock_sha256": "5" * 64}
    final = {
        "implementation_commit_sha": implementation_commit,
        "implementation_measurements": measurements,
        "review_lock_commit_sha": review_commit,
        "review_lock_file": review_file,
        "review_lock_internal_sha256": "5" * 64,
        "recovery_final_lock_sha256": "6" * 64,
        "catalog_projection_gcs_create_once_licensed": True,
        "request_authoritative_inner_publication": False,
        "outer_attestation_root_last_required": True,
        "recovery_attempt_ordinal": core.RECOVERY_ATTEMPT_ORDINAL,
        "maximum_lifetime_projection_attempts": core.MAXIMUM_LIFETIME_PROJECTION_ATTEMPTS,
        "historical_evidence": [],
        "historical_evidence_manifest_sha256": core.canonical_sha256([]),
        "smoke_evidence_file": smoke_file,
        "smoke_evidence_sha256": "7" * 64,
        "empty_prefix_evidence_file": empty_file,
        "empty_prefix_evidence_sha256": "8" * 64,
    }
    capability_body = {
        "current_clean_commit_sha": current_head,
        "implementation_commit_sha": implementation_commit,
        "implementation_measurements": measurements,
        "review_lock_commit_sha": review_commit,
        "review_lock_file": review_file,
        "review_lock_internal_sha256": "5" * 64,
        "final_lock_commit_sha": final_commit,
        "final_lock_file": final_file,
        "final_lock_internal_sha256": "6" * 64,
        "review_lock_sha256": core.canonical_sha256(review),
        "final_lock_sha256": core.canonical_sha256(final),
    }
    capability = core.PublicationCapabilityV1(
        current_clean_commit_sha=current_head,
        implementation_commit_sha=implementation_commit,
        implementation_measurements=tuple(measurements),
        review_lock_commit_sha=review_commit,
        review_lock_file=MappingProxyType(review_file),
        review_lock_internal_sha256="5" * 64,
        final_lock_commit_sha=final_commit,
        final_lock_file=MappingProxyType(final_file),
        final_lock_internal_sha256="6" * 64,
        review_lock=MappingProxyType(review),
        final_lock=MappingProxyType(final),
        base_adapter_review=object(),
        capability_sha256=core.canonical_sha256(capability_body),
    )
    build_capability = capability
    if current_head != final_commit:
        build_capability, _ = _authority(
            current_head=final_commit,
            final_commit=final_commit,
            marker_commit=marker_commit,
        )
    marker = core.build_attempt_marker_v1(capability=build_capability)
    marker_raw = core.canonical_json_bytes(marker) + b"\n"
    binding = core.TrackedAttemptBindingV1(
        reopened_at_commit_sha=current_head,
        marker_commit_sha=marker_commit,
        marker=MappingProxyType(marker),
        marker_file=MappingProxyType(core.file_binding(core.ATTEMPT_PATH, marker_raw)),
        marker_internal_sha256=str(marker["recovery_attempt_sha256"]),
    )
    return capability, binding


def test_empty_prefix_evidence_requires_observed_zero_inventory() -> None:
    evidence = core.build_empty_prefix_evidence_v1(
        checked_at_utc="2026-08-27T12:00:00Z",
        source_commit_sha="b" * 40,
        implementation_measurements=_measurements(),
        observed_prefix_inventory=[],
    )
    assert core.validate_empty_prefix_evidence_v1(
        evidence,
        implementation_commit_sha="b" * 40,
        implementation_measurements=_measurements(),
    ) == evidence
    extra = [{
        "uri": f"{core.adapter.FIXED_CATALOG_NAMESPACE}unexpected.json",
        "generation": "1",
        "bytes": 1,
    }]
    with pytest.raises(
        core.CorpusR6FixedG0CatalogRecoveryV1Error,
        match="found existing catalog objects",
    ):
        core.build_empty_prefix_evidence_v1(
            checked_at_utc="2026-08-27T12:00:00Z",
            source_commit_sha="b" * 40,
            implementation_measurements=_measurements(),
            observed_prefix_inventory=extra,
        )


def test_production_empty_prefix_census_uses_real_backend_list_and_fails_nonempty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    backend = SimpleNamespace(
        list_prefix_inventory=lambda prefix: (
            calls.append(prefix)
            or [{"uri": f"{prefix}occupied", "generation": "1", "bytes": 1}]
        )
    )
    repository = SimpleNamespace(read_tracked=lambda *_args: b"smoke")
    smoke = {
        "source_commit_sha": "a" * 40,
        "implementation_measurements": _measurements(),
    }
    monkeypatch.setattr(
        operator,
        "_clean_context",
        lambda: (repository, "b" * 40, _measurements(), {}),
    )
    monkeypatch.setattr(core, "_parse_json", lambda *_args, **_kwargs: smoke)
    monkeypatch.setattr(core, "validate_smoke_evidence_v1", lambda _value: smoke)
    monkeypatch.setattr(
        operator,
        "_reviewed_implementation_from_smoke_v1",
        lambda **_kwargs: ("a" * 40, _measurements()),
    )
    with pytest.raises(
        core.CorpusR6FixedG0CatalogRecoveryV1Error,
        match="found existing catalog objects",
    ):
        operator.run_empty_prefix_census_production_v1(
            checked_at_utc="2026-08-27T12:00:00Z",
            backend_factory=lambda: backend,
        )
    assert calls == [core.adapter.FIXED_CATALOG_NAMESPACE]


def test_recovery_gcs_backend_list_blobs_empty_and_canonical_order() -> None:
    prefix = core.adapter.FIXED_CATALOG_NAMESPACE
    tail = prefix.removeprefix("gs://")
    bucket, _, object_prefix = tail.partition("/")
    calls: list[tuple[str, str]] = []
    blobs = [
        SimpleNamespace(name=f"{object_prefix}z.json", generation="2", size=9),
        SimpleNamespace(name=f"{object_prefix}a.json", generation="1", size=3),
    ]
    client = SimpleNamespace(
        list_blobs=lambda got_bucket, *, prefix: (
            calls.append((got_bucket, prefix)) or list(blobs)
        )
    )
    backend = operator.RecoveryGCSBackendV1(SimpleNamespace(_client=client))
    rows = backend.list_prefix_inventory(prefix)
    assert [row["uri"] for row in rows] == [
        f"gs://{bucket}/{object_prefix}a.json",
        f"gs://{bucket}/{object_prefix}z.json",
    ]
    assert calls == [(bucket, object_prefix)]
    blobs.clear()
    assert backend.list_prefix_inventory(prefix) == []


@pytest.mark.parametrize(
    ("generation", "size", "name"),
    [
        (None, 1, "valid.json"),
        ("1", None, "valid.json"),
        ("1", 1, "../escape.json"),
    ],
)
def test_recovery_gcs_backend_rejects_malformed_list_metadata(
    generation: object,
    size: object,
    name: str,
) -> None:
    prefix = core.adapter.FIXED_CATALOG_NAMESPACE
    tail = prefix.removeprefix("gs://")
    bucket, _, object_prefix = tail.partition("/")
    blob = SimpleNamespace(
        name=f"{object_prefix}{name}", generation=generation, size=size
    )
    client = SimpleNamespace(list_blobs=lambda *_args, **_kwargs: [blob])
    backend = operator.RecoveryGCSBackendV1(SimpleNamespace(_client=client))
    with pytest.raises(Exception):
        backend.list_prefix_inventory(prefix)


def test_focused_test_receipt_rejects_fabricated_three_case_scope() -> None:
    output_raw = (
        b'<?xml version="1.0" encoding="utf-8"?>'
        b'<testsuites><testsuite name="pytest" errors="0" failures="0" '
        b'skipped="0" tests="3" time="0.10" '
        b'timestamp="2026-08-27T12:00:00-05:00">'
        + b"".join(
            f'<testcase classname="{classname}" name="case-{ordinal}"/>'.encode()
            for ordinal, classname in enumerate(core.FOCUSED_TEST_CLASSNAMES)
        )
        + b'</testsuite></testsuites>'
    )
    for forged in (
        output_raw,
        output_raw.replace(b'tests="3"', b'tests="99"'),
        output_raw.replace(
            core.FOCUSED_TEST_CLASSNAMES[0].encode(), b"tests.foreign_suite"
        ),
    ):
        with pytest.raises(core.CorpusR6FixedG0CatalogRecoveryV1Error):
            core.build_focused_test_receipt_v1(
                implementation_commit_sha="b" * 40,
                implementation_measurements=_measurements(),
                output_file=core.file_binding(core.FOCUSED_TEST_OUTPUT_PATH, forged),
                exact_output_raw=forged,
            )


def test_closed_focused_runner_owns_constant_argv_exit_and_junit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "reports").mkdir()
    implementation_head = "a" * 40
    artifact_head = "b" * 40
    smoke = {
        "source_commit_sha": implementation_head,
        "implementation_measurements": _measurements(),
    }
    repository = SimpleNamespace(read_tracked=lambda *_args: b"smoke")
    monkeypatch.setattr(operator, "REPOSITORY_ROOT", tmp_path)
    runtime_junit = tmp_path / "runtime-junit.xml"
    monkeypatch.setattr(core, "FOCUSED_TEST_RUNTIME_JUNIT_PATH", str(runtime_junit))
    monkeypatch.setattr(
        operator,
        "_clean_context",
        lambda: (repository, artifact_head, _measurements(), {}),
    )
    monkeypatch.setattr(core, "validate_smoke_evidence_v1", lambda _value: smoke)
    monkeypatch.setattr(core, "_parse_json", lambda *_args, **_kwargs: smoke)
    ancestry: list[tuple[str, str]] = []
    monkeypatch.setattr(
        core,
        "require_git_ancestor_v1",
        lambda _repository, *, ancestor_commit_sha, descendant_commit_sha, label: (
            ancestry.append((ancestor_commit_sha, descendant_commit_sha))
        ),
    )
    monkeypatch.setattr(
        core,
        "reopen_implementation_v1",
        lambda *_args, **_kwargs: _measurements(),
    )
    parity: list[str] = []
    monkeypatch.setattr(
        core,
        "verify_current_implementation_v1",
        lambda _repository, *, current_head, reviewed_measurements: (
            parity.append(current_head)
        ),
    )
    original_build = core.build_focused_test_receipt_v1

    def reviewed_build(**kwargs: object) -> dict[str, object]:
        assert kwargs["implementation_commit_sha"] == implementation_head
        assert kwargs["implementation_measurements"] == _measurements()
        return original_build(**kwargs)

    monkeypatch.setattr(core, "build_focused_test_receipt_v1", reviewed_build)
    monkeypatch.setenv("PYTHONPATH", "/hostile/injection")
    monkeypatch.setenv("PYTEST_ADDOPTS", "-p hostile --ignore=tests")
    observed_argv: list[str] = []

    def closed_run(
        argv: list[str], *, cwd: Path, check: bool, env: dict[str, str]
    ) -> object:
        assert check is False
        assert env == operator.FOCUSED_TEST_ENV
        assert env["PYTHONPATH"] == ""
        assert env["PYTEST_ADDOPTS"] == ""
        assert env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
        observed_argv.extend(argv)
        junit = (
            b'<testsuites><testsuite tests="3" failures="0" errors="0" skipped="0" '
            b'timestamp="2026-08-27T12:00:00-05:00">'
            + b"".join(
                f'<testcase classname="{name}" name="case-{ordinal}"/>'.encode()
                for ordinal, name in enumerate(core.FOCUSED_TEST_CLASSNAMES)
            )
            + b'</testsuite></testsuites>'
        )
        path = Path(core.FOCUSED_TEST_RUNTIME_JUNIT_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(junit)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(operator.subprocess, "run", closed_run)
    with pytest.raises(
        core.CorpusR6FixedG0CatalogRecoveryV1Error,
        match="semantics",
    ):
        operator.run_focused_tests_production_v1()
    assert observed_argv == list(core.FOCUSED_TEST_COMMAND)
    assert ancestry == [(implementation_head, artifact_head)]
    assert parity == [artifact_head]
    assert not (tmp_path / core.FOCUSED_TEST_RECEIPT_PATH).exists()


def test_local_authority_create_is_atomic_exact_resumable_and_collision_safe(
    tmp_path: Path,
) -> None:
    relative = "reports/authority.json"
    body = {"schema_version": "fixture/v1", "complete": True}
    first = core.write_local_create_once_v1(
        repository_root=tmp_path,
        relative_path=relative,
        body=body,
    )
    second = core.write_local_create_once_v1(
        repository_root=tmp_path,
        relative_path=relative,
        body=body,
    )
    assert second == first
    assert not list((tmp_path / "reports").glob(".*.tmp"))
    with pytest.raises(
        core.CorpusR6FixedG0CatalogRecoveryV1Error,
        match="collision differs",
    ):
        core.write_local_create_once_v1(
            repository_root=tmp_path,
            relative_path=relative,
            body={"schema_version": "fixture/v1", "complete": False},
        )


def test_git_ancestry_rejects_unrelated_commits() -> None:
    repository = SimpleNamespace(
        _run=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("unrelated"))
    )
    with pytest.raises(
        core.CorpusR6FixedG0CatalogRecoveryV1Error,
        match="Git ancestry differs",
    ):
        core.require_git_ancestor_v1(
            repository,
            ancestor_commit_sha="a" * 40,
            descendant_commit_sha="b" * 40,
            label="adversarial-unrelated",
        )


def test_mutation_boundary_has_no_caller_capability_parameters() -> None:
    parameters = inspect.signature(operator.run_publish_v1).parameters
    assert parameters == {}


class _Repository:
    def __init__(self, head: str) -> None:
        self.head = head
        self.clean_calls = 0

    def require_current_clean_head(self) -> str:
        self.clean_calls += 1
        return self.head

    def read_tracked(self, commit: str, path: str) -> bytes:
        del commit, path
        return b"tracked"


def test_mutation_boundary_resolves_tracked_authority_before_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(core.ENABLE_ENV, "1")
    repository = _Repository("e" * 40)
    events: list[str] = []
    monkeypatch.setattr(core, "verify_module_origins_v1", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(core, "measure_implementation_v1", lambda *_args, **_kwargs: _measurements())

    def resolve(**_kwargs: object) -> tuple[object, object]:
        events.append("resolve")
        raise core.CorpusR6FixedG0CatalogRecoveryV1Error("tracked attempt absent")

    monkeypatch.setattr(core, "resolve_tracked_attempt_binding_v1", resolve)

    def backend_factory() -> object:
        events.append("backend")
        return pytest.fail("backend must remain unopened")

    monkeypatch.setattr(operator.adapter, "SubprocessGitRepositoryV1", lambda _root: repository)
    monkeypatch.setattr(operator, "_default_backend_factory", backend_factory)

    with pytest.raises(
        core.CorpusR6FixedG0CatalogRecoveryV1Error,
        match="tracked attempt absent",
    ):
        operator.run_publish_v1()
    assert events == ["resolve"]
    assert repository.clean_calls == 1


def test_mutation_boundary_env_gate_precedes_repository_and_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(core.ENABLE_ENV, raising=False)
    with pytest.raises(
        operator.RunCorpusR6FixedG0CatalogRecoveryV1Error,
        match="publication is parked",
    ):
        operator.run_publish_v1()


def test_tracked_attempt_uses_introduction_commit_across_head_advancement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    final_commit = "d" * 40
    marker_commit = "e" * 40
    current_head = "f" * 40
    capability, expected_binding = _authority(
        current_head=current_head,
        final_commit=final_commit,
        marker_commit=marker_commit,
    )
    marker_raw = core.canonical_json_bytes(dict(expected_binding.marker)) + b"\n"
    calls: list[tuple[str, str]] = []

    class Repository:
        def read_tracked(self, commit: str, path: str) -> bytes:
            calls.append((commit, path))
            return marker_raw

    monkeypatch.setattr(core, "resolve_final_capability_v1", lambda *_args, **_kwargs: capability)
    monkeypatch.setattr(core, "tracked_file_introduction_commit_v1", lambda *_args, **_kwargs: marker_commit)
    monkeypatch.setattr(core, "require_git_ancestor_v1", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        core, "require_commit_reachable_from_remote_v1", lambda *_args, **_kwargs: None
    )

    resolved_capability, binding = core.resolve_tracked_attempt_binding_v1(
        repository=Repository(), current_head=current_head
    )
    assert resolved_capability is capability
    assert binding.marker_commit_sha == marker_commit
    assert binding.reopened_at_commit_sha == current_head
    assert (marker_commit, core.ATTEMPT_PATH) in calls


def test_resolved_attempt_rejects_unrelated_head_and_introduced_byte_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    final_commit, marker_commit, head = "d" * 40, "e" * 40, "f" * 40
    capability, expected = _authority(
        current_head=head, final_commit=final_commit, marker_commit=marker_commit
    )
    marker_raw = core.canonical_json_bytes(dict(expected.marker)) + b"\n"

    class Repository:
        def __init__(self, mutate_intro: bool) -> None:
            self.mutate_intro = mutate_intro

        def read_tracked(self, commit: str, _path: str) -> bytes:
            if self.mutate_intro and commit == marker_commit:
                return marker_raw + b"changed"
            return marker_raw

    monkeypatch.setattr(core, "resolve_final_capability_v1", lambda *_args, **_kwargs: capability)
    monkeypatch.setattr(core, "tracked_file_introduction_commit_v1", lambda *_args, **_kwargs: marker_commit)
    monkeypatch.setattr(core, "require_commit_reachable_from_remote_v1", lambda *_args, **_kwargs: None)

    def ancestry(_repository: object, *, label: str, **_kwargs: object) -> None:
        if label == "attempt-to-current":
            raise core.CorpusR6FixedG0CatalogRecoveryV1Error("Git ancestry differs")

    monkeypatch.setattr(core, "require_git_ancestor_v1", ancestry)
    with pytest.raises(core.CorpusR6FixedG0CatalogRecoveryV1Error, match="ancestry"):
        core.resolve_tracked_attempt_binding_v1(repository=Repository(False), current_head=head)

    monkeypatch.setattr(core, "require_git_ancestor_v1", lambda *_args, **_kwargs: None)
    with pytest.raises(
        core.CorpusR6FixedG0CatalogRecoveryV1Error,
        match="differs from its tracked binding",
    ):
        core.resolve_tracked_attempt_binding_v1(repository=Repository(True), current_head=head)


def test_remote_durability_is_exactly_origin_main_and_rejects_unreachable() -> None:
    calls: list[tuple[str, ...]] = []

    class Repository:
        def _run(self, args: list[str], *, label: str) -> bytes:
            del label
            calls.append(tuple(args))
            if args[:2] == ["rev-parse", "--verify"]:
                return ("f" * 40 + "\n").encode()
            raise RuntimeError("not ancestor")

    with pytest.raises(core.CorpusR6FixedG0CatalogRecoveryV1Error, match="ancestry"):
        core.require_commit_reachable_from_remote_v1(
            Repository(), commit_sha="e" * 40
        )
    assert calls[0] == ("rev-parse", "--verify", core.DURABLE_REMOTE_REF)
    assert not any("refs/remotes" == part for call in calls for part in call)


def _manifest_identity(ordinal: int) -> dict[str, object]:
    raw = f"manifest-{ordinal}".encode()
    return _identity_from_raw(
        f"{core.adapter.FIXED_CATALOG_NAMESPACE}object-{ordinal:03d}.json",
        raw,
        str(1000 + ordinal),
    )


def test_outer_bytes_and_validation_survive_head_advancement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    final_commit = "d" * 40
    marker_commit = "e" * 40
    h1 = "f" * 40
    h2 = "9" * 40
    capability_h1, binding_h1 = _authority(
        current_head=h1, final_commit=final_commit, marker_commit=marker_commit
    )
    capability_h2, binding_h2 = _authority(
        current_head=h2, final_commit=final_commit, marker_commit=marker_commit
    )
    release = {"release_sha256": "a" * 64, "task_count": 54}
    release_raw = core.canonical_json_bytes(release)
    release_identity = _identity_from_raw(
        f"{core.adapter.FIXED_CATALOG_NAMESPACE}catalog-release.json",
        release_raw,
        "2001",
    )
    receipt = core._self_hash({
        "catalog_release_identity": release_identity,
        "catalog_release_sha256": release["release_sha256"],
        "task_count": 54,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }, "replay_receipt_sha256")
    receipt_raw = core.canonical_json_bytes(receipt)
    receipt_identity = _identity_from_raw(
        f"{core.adapter.FIXED_CATALOG_NAMESPACE}{core.adapter.REPLAY_RECEIPT_FILENAME}",
        receipt_raw,
        "2002",
    )
    manifest: list[dict[str, object]] = []
    for ordinal in range(core.EXPECTED_INNER_OBJECT_COUNT):
        if ordinal < 108:
            role = "catalog_derivation_receipt" if ordinal % 2 == 0 else "player_catalog"
            source_ordinal: int | None = ordinal // 2
            identity = _manifest_identity(ordinal)
        elif ordinal == 108:
            role = "catalog_release"
            source_ordinal = None
            identity = release_identity
        else:
            role = "inner_replay_receipt"
            source_ordinal = None
            identity = receipt_identity
        manifest.append({
            "object_ordinal": ordinal,
            "role": role,
            "source_task_ordinal": source_ordinal,
            "identity": identity,
        })
    monkeypatch.setattr(core.catalog, "validate_release_v1", lambda *_args, **_kwargs: release)
    monkeypatch.setattr(core, "ordered_inner_object_manifest_v1", lambda **_kwargs: manifest)

    outer_h1 = core.build_outer_attestation_v1(
        capability=capability_h1,
        attempt_binding=binding_h1,
        release_identity=release_identity,
        release=release,
        replay_receipt_identity=receipt_identity,
        replay_receipt=receipt,
    )
    outer_h2 = core.build_outer_attestation_v1(
        capability=capability_h2,
        attempt_binding=binding_h2,
        release_identity=release_identity,
        release=release,
        replay_receipt_identity=receipt_identity,
        replay_receipt=receipt,
    )
    assert core.canonical_json_bytes(outer_h1) == core.canonical_json_bytes(outer_h2)
    assert core.validate_outer_attestation_v1(
        outer_h1,
        capability=capability_h2,
        attempt_binding=binding_h2,
    ) == outer_h1


def test_outer_builder_rejects_receipt_identity_not_bound_to_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capability, binding = _authority()
    release = {"release_sha256": "a" * 64, "task_count": 54}
    release_raw = core.canonical_json_bytes(release)
    release_identity = _identity_from_raw(
        f"{core.adapter.FIXED_CATALOG_NAMESPACE}catalog-release.json", release_raw
    )
    receipt = core._self_hash({
        "catalog_release_identity": release_identity,
        "catalog_release_sha256": release["release_sha256"],
    }, "replay_receipt_sha256")
    wrong_receipt_identity = _identity_from_raw(
        f"{core.adapter.FIXED_CATALOG_NAMESPACE}{core.adapter.REPLAY_RECEIPT_FILENAME}",
        b"different",
    )
    monkeypatch.setattr(core.catalog, "validate_release_v1", lambda *_args, **_kwargs: release)
    monkeypatch.setattr(core, "ordered_inner_object_manifest_v1", lambda **_kwargs: [])
    with pytest.raises(
        core.CorpusR6FixedG0CatalogRecoveryV1Error,
        match="inner chain differs",
    ):
        core.build_outer_attestation_v1(
            capability=capability,
            attempt_binding=binding,
            release_identity=release_identity,
            release=release,
            replay_receipt_identity=wrong_receipt_identity,
            replay_receipt=receipt,
        )


def test_authoritative_outer_reopen_rejects_corrupt_generation_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capability, binding = _authority()
    release = {"release_sha256": "a" * 64, "task_count": 54}
    release_raw = core.canonical_json_bytes(release)
    release_identity = _identity_from_raw(
        f"{core.adapter.FIXED_CATALOG_NAMESPACE}catalog-release.json", release_raw
    )
    receipt = core._self_hash({
        "catalog_release_identity": release_identity,
        "catalog_release_sha256": release["release_sha256"],
        "task_count": 54,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }, "replay_receipt_sha256")
    receipt_identity = _identity_from_raw(
        f"{core.adapter.FIXED_CATALOG_NAMESPACE}{core.adapter.REPLAY_RECEIPT_FILENAME}",
        core.canonical_json_bytes(receipt),
    )
    manifest = [
        {
            "object_ordinal": ordinal,
            "role": "catalog_derivation_receipt" if ordinal < 108 and ordinal % 2 == 0 else (
                "player_catalog" if ordinal < 108 else (
                    "catalog_release" if ordinal == 108 else "inner_replay_receipt"
                )
            ),
            "source_task_ordinal": ordinal // 2 if ordinal < 108 else None,
            "identity": (
                _manifest_identity(ordinal) if ordinal < 108 else (
                    release_identity if ordinal == 108 else receipt_identity
                )
            ),
        }
        for ordinal in range(core.EXPECTED_INNER_OBJECT_COUNT)
    ]
    monkeypatch.setattr(core.catalog, "validate_release_v1", lambda *_args, **_kwargs: release)
    monkeypatch.setattr(core, "ordered_inner_object_manifest_v1", lambda **_kwargs: manifest)
    outer = core.build_outer_attestation_v1(
        capability=capability,
        attempt_binding=binding,
        release_identity=release_identity,
        release=release,
        replay_receipt_identity=receipt_identity,
        replay_receipt=receipt,
    )
    raw = core.canonical_json_bytes(outer)
    identity = _identity_from_raw(core.OUTER_ATTESTATION_URI, raw)
    store = _ExactStore()
    store.seed(identity, raw + b"corruption")
    audit = core.TransportAuditV1(
        store.transport(), mode="read_only", allowed_read_identities=[identity]
    )
    with pytest.raises(
        core.adapter.CorpusR6FixedG0AdapterV1Error,
        match="generation-specific download failed",
    ):
        core._reopen_outer_structure_v1(
            outer_identity=identity,
            capability=capability,
            attempt_binding=binding,
            transport=audit.transport(),
        )


def test_outer_manifest_uri_order_is_validated_before_any_inner_binding() -> None:
    outer_raw = b"outer"
    outer_identity = _identity_from_raw(core.OUTER_ATTESTATION_URI, outer_raw)
    store = _ExactStore()
    store.seed(outer_identity, outer_raw)
    audit = core.TransportAuditV1(
        store.transport(), mode="read_only", allowed_read_identities=[outer_identity]
    )
    core.adapter.read_generation_exact_v1(
        outer_identity, transport=audit.transport()
    )
    identities = [
        _identity_from_raw(uri, f"body-{ordinal}".encode(), str(ordinal + 1))
        for ordinal, uri in enumerate(core.planned_inner_output_uris_v1())
    ]
    before = dict(audit.allowed_read_identities)
    with pytest.raises(
        core.CorpusR6FixedG0CatalogRecoveryV1Error,
        match="URI tuple differs",
    ):
        audit.bind_attested_output_identities_v1(list(reversed(identities)))
    assert audit.allowed_read_identities == before


class _MemoryRecoveryBackend:
    def __init__(self) -> None:
        self.by_uri: dict[str, tuple[dict[str, object], bytes]] = {}
        self.next_generation = 3000
        self.events: list[tuple[str, str]] = []
        self.fail_download_uri_once: str | None = None
        self.fail_create_call_once: int | None = None
        self.create_call_count = 0
        self.fail_list_call_once: int | None = None
        self.list_call_count = 0
        self.inject_extra_on_list_call: int | None = None
        self.inject_outer_after_list_call: int | None = None
        self.write_then_raise_call: int | None = None
        self.unknown_raise_call: int | None = None
        self.collision_race_call: int | None = None
        self.collision_race_wrong_bytes = False
        self.invalid_success_call: int | None = None
        self.collision_without_visible_call: int | None = None

    def seed(self, uri: str, raw: bytes) -> dict[str, object]:
        self.next_generation += 1
        identity = _identity_from_raw(uri, raw, str(self.next_generation))
        self.by_uri[uri] = (identity, raw)
        return identity

    def reload_generation(self, uri: str, generation: str) -> dict[str, object]:
        self.events.append(("reload", uri))
        identity, _ = self.by_uri[uri]
        if identity["generation"] != generation:
            raise RuntimeError("wrong generation")
        return dict(identity)

    def download_generation(self, uri: str, generation: str) -> bytes:
        self.events.append(("download", uri))
        identity, raw = self.by_uri[uri]
        if identity["generation"] != generation:
            raise RuntimeError("wrong generation")
        if self.fail_download_uri_once == uri:
            self.fail_download_uri_once = None
            raise RuntimeError("simulated crash after outer creation")
        return raw

    def resolve_current(self, uri: str) -> dict[str, object]:
        self.events.append(("resolve", uri))
        if uri not in self.by_uri:
            raise core.adapter.ObjectNotFoundV1Error("missing")
        return dict(self.by_uri[uri][0])

    def create_if_absent(self, uri: str, raw: bytes, precondition: int) -> dict[str, object]:
        self.events.append(("create", uri))
        self.create_call_count += 1
        if self.fail_create_call_once == self.create_call_count:
            self.fail_create_call_once = None
            raise RuntimeError("simulated create crash")
        if self.write_then_raise_call == self.create_call_count:
            self.write_then_raise_call = None
            self.seed(uri, raw)
            raise RuntimeError("response lost after durable write")
        if self.unknown_raise_call == self.create_call_count:
            self.unknown_raise_call = None
            raise RuntimeError("ambiguous create without visible generation")
        if self.collision_race_call == self.create_call_count:
            self.collision_race_call = None
            self.seed(uri, b"wrong" if self.collision_race_wrong_bytes else raw)
            raise core.adapter.ObjectAlreadyExistsV1Error("collision race")
        if self.collision_without_visible_call == self.create_call_count:
            self.collision_without_visible_call = None
            raise core.adapter.ObjectAlreadyExistsV1Error("invisible collision race")
        if self.invalid_success_call == self.create_call_count:
            self.invalid_success_call = None
            return _identity_from_raw(uri, b"invalid-success", "999999")
        if precondition != 0:
            raise RuntimeError("wrong precondition")
        if uri in self.by_uri:
            raise core.adapter.ObjectAlreadyExistsV1Error("occupied")
        return self.seed(uri, raw)

    def transport(self) -> core.adapter.GenerationTransportV1:
        return core.adapter.GenerationTransportV1(
            reload_generation=self.reload_generation,
            download_generation=self.download_generation,
            resolve_current=self.resolve_current,
            create_if_absent=self.create_if_absent,
        )

    def list_prefix_inventory(self, prefix: str) -> list[dict[str, object]]:
        self.list_call_count += 1
        if self.fail_list_call_once == self.list_call_count:
            self.fail_list_call_once = None
            raise RuntimeError("simulated prefix census crash")
        if self.inject_extra_on_list_call == self.list_call_count:
            self.inject_extra_on_list_call = None
            self.seed(f"{prefix}post-root-extra.json", b"extra")
        rows = core.normalize_prefix_inventory_v1(sorted([
            {
                "uri": identity["uri"],
                "generation": identity["generation"],
                "bytes": identity["bytes"],
            }
            for uri, (identity, _) in self.by_uri.items()
            if uri.startswith(prefix)
        ], key=lambda row: str(row["uri"])))
        if self.inject_outer_after_list_call == self.list_call_count:
            self.inject_outer_after_list_call = None
            self.seed(core.OUTER_ATTESTATION_URI, b"racing-wrong-outer")
        return rows


def _call_publish(
    monkeypatch: pytest.MonkeyPatch,
    *,
    repository: _Repository,
    backend: _MemoryRecoveryBackend,
) -> dict[str, object]:
    monkeypatch.setattr(
        operator.adapter, "SubprocessGitRepositoryV1", lambda _root: repository
    )
    monkeypatch.setattr(operator, "_default_backend_factory", lambda: backend)
    monkeypatch.setattr(
        operator,
        "_planned_source_audit_v1",
        lambda **_kwargs: core.TransportAuditV1(
            backend.transport(),
            mode="publish",
            allowed_read_identities=[],
            planned_output_uris=core.planned_inner_output_uris_v1(),
        ),
    )
    return operator.run_publish_v1()


def _inner_uri(ordinal: int) -> str:
    return core.planned_inner_output_uris_v1()[ordinal]


def _inner_raw(ordinal: int) -> bytes:
    return f"inner-body-{ordinal}".encode()


def _install_publication_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    repository: _Repository,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    manifest: list[dict[str, object]] = []
    outer = {
        "schema_version": "test-outer/v1",
        "recovery_attestation_sha256": "f" * 64,
        "inner_object_manifest": manifest,
    }
    replay_receipt = {
        "task_count": 54,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "replay_receipt_sha256": "a" * 64,
    }
    monkeypatch.setattr(core, "verify_module_origins_v1", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(core, "measure_implementation_v1", lambda *_args, **_kwargs: _measurements())
    monkeypatch.setattr(core, "source_read_allowlist_v1", lambda **_kwargs: [])

    def resolve_authority(**_kwargs: object) -> tuple[object, object]:
        return _authority(current_head=repository.head)

    monkeypatch.setattr(core, "resolve_tracked_attempt_binding_v1", resolve_authority)

    def publish_inner(**kwargs: object) -> dict[str, object]:
        transport = kwargs["transport"]
        manifest.clear()
        for ordinal in range(core.EXPECTED_INNER_OBJECT_COUNT):
            identity = core.adapter.publish_create_once_resumable_v1(
                _inner_uri(ordinal), _inner_raw(ordinal), transport=transport
            )
            manifest.append({"identity": identity})
        return {
            "catalog_release_identity": manifest[-2]["identity"],
            "replay_receipt_identity": manifest[-1]["identity"],
            "replay_receipt": replay_receipt,
        }

    monkeypatch.setattr(operator.adapter, "_publish_pinned_projection_release_v1", publish_inner)

    def reopen_inner(**_kwargs: object) -> dict[str, object]:
        return {
            "catalog_release_identity": manifest[-2]["identity"],
            "catalog_release": {"task_count": 54, "release_sha256": "b" * 64},
            "replay_receipt_identity": manifest[-1]["identity"],
            "replay_receipt": replay_receipt,
        }

    monkeypatch.setattr(operator, "_inner_result_exact_reopen", reopen_inner)
    monkeypatch.setattr(core, "ordered_inner_object_manifest_v1", lambda **_kwargs: manifest)
    monkeypatch.setattr(core, "build_outer_attestation_v1", lambda **_kwargs: outer)

    def reopen_outer(**kwargs: object) -> dict[str, object]:
        identity = core.adapter._normalized_identity(
            kwargs["outer_identity"], label="test outer identity"
        )
        raw = core.adapter.read_generation_exact_v1(
            identity, transport=kwargs["transport"]
        )
        assert core.batch.parse_canonical_json_bytes(raw, label="test outer") == outer
        return {"outer_identity": identity, "outer_attestation": outer}

    monkeypatch.setattr(core, "_reopen_outer_structure_v1", reopen_outer)
    return manifest, outer


@pytest.mark.parametrize("preexisting_inner_count", [0, 12])
def test_publication_fresh_and_partial_inner_resume_are_outer_last(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    preexisting_inner_count: int,
) -> None:
    monkeypatch.setenv(core.ENABLE_ENV, "1")
    repository = _Repository("e" * 40)
    backend = _MemoryRecoveryBackend()
    for ordinal in range(preexisting_inner_count):
        backend.seed(_inner_uri(ordinal), _inner_raw(ordinal))
    _install_publication_fakes(monkeypatch, repository=repository)

    summary = _call_publish(monkeypatch, repository=repository, backend=backend)
    create_uris = [uri for action, uri in backend.events if action == "create"]
    assert create_uris[-1] == core.OUTER_ATTESTATION_URI
    assert len(summary["terminal_prefix_inventory"]) == core.EXPECTED_TOTAL_OBJECT_COUNT
    assert summary["transport_audit"]["reopened_count"] == preexisting_inner_count
    assert summary["transport_audit"]["planned_output_uris"] == list(
        core.planned_inner_output_uris_v1()
    )
    assert summary["transport_audit"]["outer_uri_active"] is True
    assert len(summary["transport_audit"]["expected_create_sha256_by_uri"]) == core.EXPECTED_TOTAL_OBJECT_COUNT
    assert len(summary["transport_audit"]["expected_create_bytes_by_uri"]) == core.EXPECTED_TOTAL_OBJECT_COUNT
    assert summary["complete"] is True


def test_publication_resumes_after_crash_with_outer_already_created_and_new_head(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(core.ENABLE_ENV, "1")
    repository = _Repository("e" * 40)
    backend = _MemoryRecoveryBackend()
    backend.fail_download_uri_once = core.OUTER_ATTESTATION_URI
    _install_publication_fakes(monkeypatch, repository=repository)

    with pytest.raises(operator.RunCorpusR6FixedG0CatalogRecoveryV1Error) as first:
        _call_publish(monkeypatch, repository=repository, backend=backend)
    assert first.value.partial_summary["outer_presence_state"] == "unknown"
    assert core.OUTER_ATTESTATION_URI in backend.by_uri

    repository.head = "f" * 40
    summary = _call_publish(monkeypatch, repository=repository, backend=backend)
    assert summary["complete"] is True
    assert summary["transport_audit"]["created_count"] == 0
    assert summary["transport_audit"]["reopened_count"] == core.EXPECTED_TOTAL_OBJECT_COUNT


def test_publication_rejects_mutated_occupied_outer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(core.ENABLE_ENV, "1")
    repository = _Repository("e" * 40)
    backend = _MemoryRecoveryBackend()
    backend.seed(core.OUTER_ATTESTATION_URI, b"mutated outer")
    _install_publication_fakes(monkeypatch, repository=repository)

    with pytest.raises(operator.RunCorpusR6FixedG0CatalogRecoveryV1Error) as raised:
        _call_publish(monkeypatch, repository=repository, backend=backend)
    # Presence alone is not authoritative: the occupied root failed its exact
    # body reopen and therefore remains unknown rather than confirmed-present.
    assert raised.value.partial_summary["outer_presence_state"] == "unknown"
    assert raised.value.partial_summary["complete"] is False


def test_terminal_prefix_inventory_rejects_unrelated_extra_object(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(core.ENABLE_ENV, "1")
    repository = _Repository("e" * 40)
    backend = _MemoryRecoveryBackend()
    backend.seed(
        f"{core.adapter.FIXED_CATALOG_NAMESPACE}unexpected-extra.json", b"extra"
    )
    _install_publication_fakes(monkeypatch, repository=repository)

    with pytest.raises(
        operator.RunCorpusR6FixedG0CatalogRecoveryV1Error,
        match="pre-write recovery output inventory contains an unplanned URI",
    ):
        _call_publish(monkeypatch, repository=repository, backend=backend)
    assert backend.events == []
    assert set(backend.by_uri) == {
        f"{core.adapter.FIXED_CATALOG_NAMESPACE}unexpected-extra.json"
    }


@pytest.mark.parametrize("crash_create", [1, 37, 109, 110])
def test_publication_resumes_after_nth_inner_including_release_receipt_crash(
    monkeypatch: pytest.MonkeyPatch,
    crash_create: int,
) -> None:
    monkeypatch.setenv(core.ENABLE_ENV, "1")
    repository = _Repository("e" * 40)
    backend = _MemoryRecoveryBackend()
    backend.fail_create_call_once = crash_create
    _install_publication_fakes(monkeypatch, repository=repository)
    with pytest.raises(operator.RunCorpusR6FixedG0CatalogRecoveryV1Error):
        _call_publish(monkeypatch, repository=repository, backend=backend)
    assert core.OUTER_ATTESTATION_URI not in backend.by_uri
    summary = _call_publish(monkeypatch, repository=repository, backend=backend)
    assert summary["complete"] is True
    assert len(summary["pre_root_prefix_inventory"]) == core.EXPECTED_INNER_OBJECT_COUNT


def test_publication_resumes_sparse_inner_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(core.ENABLE_ENV, "1")
    repository = _Repository("e" * 40)
    backend = _MemoryRecoveryBackend()
    for ordinal in (0, 17, 63, 108, 109):
        backend.seed(_inner_uri(ordinal), _inner_raw(ordinal))
    _install_publication_fakes(monkeypatch, repository=repository)
    summary = _call_publish(monkeypatch, repository=repository, backend=backend)
    assert summary["complete"] is True
    assert summary["transport_audit"]["reopened_count"] == 5


def test_inner_collision_fails_before_outer_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(core.ENABLE_ENV, "1")
    repository = _Repository("e" * 40)
    backend = _MemoryRecoveryBackend()
    backend.seed(_inner_uri(37), b"wrong occupied bytes")
    _install_publication_fakes(monkeypatch, repository=repository)
    with pytest.raises(operator.RunCorpusR6FixedG0CatalogRecoveryV1Error):
        _call_publish(monkeypatch, repository=repository, backend=backend)
    assert core.OUTER_ATTESTATION_URI not in backend.by_uri


def test_pre_root_census_crash_retries_without_outer_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(core.ENABLE_ENV, "1")
    repository = _Repository("e" * 40)
    backend = _MemoryRecoveryBackend()
    backend.fail_list_call_once = 1
    _install_publication_fakes(monkeypatch, repository=repository)
    with pytest.raises(operator.RunCorpusR6FixedG0CatalogRecoveryV1Error):
        _call_publish(monkeypatch, repository=repository, backend=backend)
    assert core.OUTER_ATTESTATION_URI not in backend.by_uri
    assert _call_publish(monkeypatch, repository=repository, backend=backend)["complete"] is True


@pytest.mark.parametrize("create_call", [37, 111])
def test_ambiguous_write_then_raise_and_collision_race_recover_exact_bytes(
    monkeypatch: pytest.MonkeyPatch,
    create_call: int,
) -> None:
    monkeypatch.setenv(core.ENABLE_ENV, "1")
    for mode in ("write-then-raise", "collision"):
        repository = _Repository("e" * 40)
        backend = _MemoryRecoveryBackend()
        if mode == "write-then-raise":
            backend.write_then_raise_call = create_call
        else:
            backend.collision_race_call = create_call
        _install_publication_fakes(monkeypatch, repository=repository)
        summary = _call_publish(monkeypatch, repository=repository, backend=backend)
        assert summary["complete"] is True
        if mode == "write-then-raise":
            expected_uri = (
                _inner_uri(create_call - 1)
                if create_call <= core.EXPECTED_INNER_OBJECT_COUNT
                else core.OUTER_ATTESTATION_URI
            )
            assert expected_uri in summary["transport_audit"][
                "ambiguous_create_recovered_uris"
            ]
            assert expected_uri in {
                row["uri"]
                for row in summary["transport_audit"][
                    "current_resolution_identities"
                ]
            }


def test_ambiguous_unknown_not_absent_is_explicit_in_partial_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(core.ENABLE_ENV, "1")
    repository = _Repository("e" * 40)
    backend = _MemoryRecoveryBackend()
    backend.unknown_raise_call = 7
    _install_publication_fakes(monkeypatch, repository=repository)
    with pytest.raises(operator.RunCorpusR6FixedG0CatalogRecoveryV1Error) as raised:
        _call_publish(monkeypatch, repository=repository, backend=backend)
    assert raised.value.partial_summary["transport_audit"][
        "unknown_not_absent_uris"
    ] == [_inner_uri(6)]
    assert core.OUTER_ATTESTATION_URI not in backend.by_uri


def test_ambiguous_outer_create_reports_unknown_presence_not_absence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(core.ENABLE_ENV, "1")
    for mode in ("unknown", "invalid-success", "invisible-412"):
        repository = _Repository("e" * 40)
        backend = _MemoryRecoveryBackend()
        if mode == "unknown":
            backend.unknown_raise_call = core.EXPECTED_TOTAL_OBJECT_COUNT
        elif mode == "invalid-success":
            backend.invalid_success_call = core.EXPECTED_TOTAL_OBJECT_COUNT
        else:
            backend.collision_without_visible_call = core.EXPECTED_TOTAL_OBJECT_COUNT
        _install_publication_fakes(monkeypatch, repository=repository)
        with pytest.raises(operator.RunCorpusR6FixedG0CatalogRecoveryV1Error) as raised:
            _call_publish(monkeypatch, repository=repository, backend=backend)
        assert raised.value.partial_summary["outer_presence_state"] == "unknown"
        if mode == "unknown":
            assert raised.value.partial_summary["transport_audit"][
                "unknown_not_absent_uris"
            ] == [core.OUTER_ATTESTATION_URI]


def test_collision_race_with_different_bytes_is_never_confirmed_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(core.ENABLE_ENV, "1")
    for create_call in (11, core.EXPECTED_TOTAL_OBJECT_COUNT):
        repository = _Repository("e" * 40)
        backend = _MemoryRecoveryBackend()
        backend.collision_race_call = create_call
        backend.collision_race_wrong_bytes = True
        _install_publication_fakes(monkeypatch, repository=repository)
        with pytest.raises(operator.RunCorpusR6FixedG0CatalogRecoveryV1Error) as raised:
            _call_publish(monkeypatch, repository=repository, backend=backend)
        if create_call == core.EXPECTED_TOTAL_OBJECT_COUNT:
            assert raised.value.partial_summary["outer_presence_state"] == "unknown"
        else:
            assert core.OUTER_ATTESTATION_URI not in backend.by_uri


def test_post_root_exact_census_rejects_object_created_after_pre_root_census(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(core.ENABLE_ENV, "1")
    repository = _Repository("e" * 40)
    backend = _MemoryRecoveryBackend()
    backend.inject_extra_on_list_call = 3
    _install_publication_fakes(monkeypatch, repository=repository)
    with pytest.raises(
        operator.RunCorpusR6FixedG0CatalogRecoveryV1Error,
        match="terminal recovery output inventory differs",
    ) as raised:
        _call_publish(monkeypatch, repository=repository, backend=backend)
    assert core.OUTER_ATTESTATION_URI in backend.by_uri
    assert len(raised.value.partial_summary["terminal_prefix_inventory"]) == 112

    # A wrong root racing into existence after the exact-110 LIST but before
    # resolve is neither confirmed absent nor exact-confirmed present.
    repository = _Repository("e" * 40)
    backend = _MemoryRecoveryBackend()
    backend.inject_outer_after_list_call = 2
    _install_publication_fakes(monkeypatch, repository=repository)
    with pytest.raises(operator.RunCorpusR6FixedG0CatalogRecoveryV1Error) as raced:
        _call_publish(monkeypatch, repository=repository, backend=backend)
    assert raced.value.partial_summary["outer_presence_state"] == "unknown"
    assert core.OUTER_ATTESTATION_URI in raced.value.partial_summary[
        "transport_audit"
    ]["current_resolution_uris"]


def test_terminal_list_crash_resumes_existing_exact_outer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(core.ENABLE_ENV, "1")
    repository = _Repository("e" * 40)
    backend = _MemoryRecoveryBackend()
    backend.fail_list_call_once = 3
    _install_publication_fakes(monkeypatch, repository=repository)
    with pytest.raises(operator.RunCorpusR6FixedG0CatalogRecoveryV1Error):
        _call_publish(monkeypatch, repository=repository, backend=backend)
    assert core.OUTER_ATTESTATION_URI in backend.by_uri
    summary = _call_publish(monkeypatch, repository=repository, backend=backend)
    assert summary["complete"] is True
    assert summary["pre_root_state"] == "exact-111-resume-existing-root"


def test_authoritative_reopen_invokes_inner_chain_and_exact_prefix_census(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capability, binding = _authority()
    backend = _MemoryRecoveryBackend()
    manifest: list[dict[str, object]] = []
    for ordinal in range(core.EXPECTED_INNER_OBJECT_COUNT):
        identity = backend.seed(_inner_uri(ordinal), _inner_raw(ordinal))
        manifest.append({"identity": identity})
    outer_body = core.canonical_json_bytes({"outer": True})
    outer_identity = backend.seed(core.OUTER_ATTESTATION_URI, outer_body)
    release = {"task_count": 54, "release_sha256": "b" * 64}
    receipt = {
        "task_count": 54,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "replay_receipt_sha256": "a" * 64,
    }
    outer = {
        "inner_catalog_release_identity": manifest[-2]["identity"],
        "inner_catalog_release_sha256": release["release_sha256"],
        "inner_replay_receipt_identity": manifest[-1]["identity"],
        "inner_replay_receipt_sha256": receipt["replay_receipt_sha256"],
        "inner_object_manifest": manifest,
        "inner_object_manifest_sha256": core.canonical_sha256(manifest),
        "recovery_attestation_sha256": "f" * 64,
    }
    monkeypatch.setattr(
        core, "validate_outer_attestation_v1", lambda *_args, **_kwargs: outer
    )
    monkeypatch.setattr(
        operator,
        "_planned_source_audit_v1",
        lambda **_kwargs: core.TransportAuditV1(
            backend.transport(),
            mode="read_only",
            allowed_read_identities=[
                outer_identity,
                *(row["identity"] for row in manifest),
            ],
        ),
    )
    monkeypatch.setattr(
        core,
        "_reopen_outer_structure_v1",
        lambda **_kwargs: {
            "outer_identity": outer_identity,
            "outer_attestation": outer,
        },
    )
    inner_calls = 0

    def reopen_inner(**_kwargs: object) -> dict[str, object]:
        nonlocal inner_calls
        inner_calls += 1
        return {
            "catalog_release_identity": manifest[-2]["identity"],
            "catalog_release": release,
            "replay_receipt_identity": manifest[-1]["identity"],
            "replay_receipt": receipt,
        }

    monkeypatch.setattr(operator, "_inner_result_exact_reopen", reopen_inner)
    monkeypatch.setattr(core, "ordered_inner_object_manifest_v1", lambda **_kwargs: manifest)
    summary = operator.run_reopen_v1(
        capability=capability,
        attempt_binding=binding,
        repository=SimpleNamespace(read_tracked=lambda *_args: b"tracked"),
        outer_identity=outer_identity,
        backend=backend,
    )
    assert inner_calls == 1
    assert summary["inner_object_count"] == core.EXPECTED_INNER_OBJECT_COUNT
    assert len(summary["terminal_prefix_inventory"]) == core.EXPECTED_TOTAL_OBJECT_COUNT
    assert summary["cloud_mutation_performed"] is False
