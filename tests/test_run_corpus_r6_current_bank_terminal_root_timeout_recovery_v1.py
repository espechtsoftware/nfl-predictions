from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_aggregate_v1 as publisher,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as task_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_corpus_r6_current_bank_terminal_root_timeout_recovery_v1.py"


def _module():
    spec = importlib.util.spec_from_file_location("terminal_recovery_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(uri: str, raw: bytes) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _with_hash(module, body: dict[str, object], field: str) -> dict[str, object]:
    retained = deepcopy(body)
    retained.pop(field, None)
    retained[field] = sha256(module.canonical_bytes_v1(retained)).hexdigest()
    return retained


def _recovery_bundle(module) -> dict[str, object]:
    runtime: dict[str, object] = {
        "execution_name": "atlas-cbc-32g-full-2023-w8-v1-recovery",
        "actual_image_digest": "sha256:" + "a" * 64,
        "actual_code_commit": "b" * 40,
        "logical_image_digest": module.FIXED_ORIGINAL_IMAGE_DIGEST,
        "logical_code_commit": module.FIXED_ORIGINAL_CODE_COMMIT,
    }
    publisher_raw = Path(str(module.publisher.__file__)).read_bytes()
    normalized = publisher_raw.replace(
        b"MAXIMUM_PUBLISHER_WALL_SECONDS: Final = 5_400",
        b"MAXIMUM_PUBLISHER_WALL_SECONDS: Final = 1_800",
    )
    build_receipt = _with_hash(module, {
        "schema_version": (
            "corpus-r6-v7-terminal-root-timeout-clean-build-receipt/v1"
        ),
        "build_id": "one-clean-build",
        "build_status": "SUCCESS",
        "source_commit": runtime["actual_code_commit"],
        "source_archive_identity": {
            "uri": (
                "gs://nfl-predictions-503414_cloudbuild/source/"
                "one-clean-build.tgz"
            ),
            "generation": "1",
            "sha256": "c" * 64,
            "bytes": 123,
        },
        "immutable_image_uri": (
            "us-central1-docker.pkg.dev/nfl-predictions-503414/"
            "research/r6-recovery@" + str(runtime["actual_image_digest"])
        ),
        "image_digest": runtime["actual_image_digest"],
        "clean_archive": True,
        "uncommitted_files_included": False,
        "focused_tests_passed": True,
        "focused_test_count": 1,
        "build_context_contract_passed": True,
        "isolated_image_smoke_passed": True,
        "recovery_source_sha256": sha256(SCRIPT.read_bytes()).hexdigest(),
        "publisher_source_sha256": sha256(publisher_raw).hexdigest(),
        "normalized_publisher_source_sha256": sha256(normalized).hexdigest(),
        "recovery_test_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "uses_realized_outcomes": False,
    }, "build_receipt_sha256")
    build_raw = module.canonical_bytes_v1(build_receipt)
    build_identity = _identity(module.FIXED_BUILD_RECEIPT_URI, build_raw)
    topology = module.recovery_topology_v1(
        module.FIXED_ORIGINAL_MANIFEST_IDENTITY
    )
    amendment = _with_hash(module, {
        "schema_version": module.AMENDMENT_SCHEMA,
        "run_id": "20260828-r6-current-bank-crossed-screen-v7",
        "failure_execution_identity": deepcopy(
            module.FIXED_FAILURE_TERMINAL_IDENTITY
        ),
        "original_manifest_identity": deepcopy(
            module.FIXED_ORIGINAL_MANIFEST_IDENTITY
        ),
        "preserved_layer_receipt_identities": deepcopy(
            list(module.FIXED_PREDECESSOR_RECEIPT_IDENTITIES)
        ),
        "original_image_digest": module.FIXED_ORIGINAL_IMAGE_DIGEST,
        "replacement_image_digest": runtime["actual_image_digest"],
        "original_code_commit": module.FIXED_ORIGINAL_CODE_COMMIT,
        "replacement_code_commit": runtime["actual_code_commit"],
        "child_command": list(module.FIXED_CHILD_COMMAND),
        "replacement_build_receipt_identity": build_identity,
        "child_command_sha256": module.FIXED_CHILD_COMMAND_SHA256,
        "request_identity": deepcopy(module.FIXED_REQUEST_IDENTITY),
        "request_sha256": module.FIXED_REQUEST_IDENTITY["sha256"],
        "request_bytes": module.FIXED_REQUEST_IDENTITY["bytes"],
        "process_budget_identity": deepcopy(
            module.FIXED_PROCESS_BUDGET_IDENTITY
        ),
        "publisher_process_budget_sha256": (
            module.FIXED_PUBLISHER_PROCESS_BUDGET_SHA256
        ),
        "read_allowlist_sha256": module.FIXED_READ_ALLOWLIST_SHA256,
        "write_allowlist_sha256": module.FIXED_WRITE_ALLOWLIST_SHA256,
        "root_uri": topology["root_uri"],
        "root_create_once": True,
        "original_child_wall_seconds": module.ORIGINAL_CHILD_WALL_SECONDS,
        "replacement_child_wall_seconds": module.RECOVERY_CHILD_WALL_SECONDS,
        "provider_task_wall_seconds": module.PROVIDER_TASK_WALL_SECONDS,
        "recovery_terminal_evidence_uri": topology["terminal_evidence_uri"],
        "launch_ownership_uri": topology["launch_ownership_uri"],
        "execution_claim_uri": topology["execution_claim_uri"],
        "terminal_receipt_uri": topology["terminal_receipt_uri"],
        "finalize_receipt_uri": topology["finalize_receipt_uri"],
        "policy": {
            "algorithm_changed": False,
            "child_command_changed": False,
            "corpus_fill_licensed": False,
            "graph_mutation_licensed": False,
            "historical_scoring_licensed": False,
            "process_budget_changed": False,
            "realized_outcomes_read": False,
            "request_changed": False,
            "scientific_inputs_changed": False,
            "single_replacement_launch_allowed": True,
        },
    }, "amendment_sha256")
    amendment_raw = module.canonical_bytes_v1(amendment)
    amendment_identity = _identity(topology["amendment_uri"], amendment_raw)
    runtime["amendment_identity"] = amendment_identity
    ownership = _with_hash(module, {
        "schema_version": module.LAUNCH_OWNERSHIP_SCHEMA,
        "run_id": amendment["run_id"],
        "amendment_identity": amendment_identity,
        "original_manifest_identity": deepcopy(
            module.FIXED_ORIGINAL_MANIFEST_IDENTITY
        ),
        "failure_execution_identity": deepcopy(
            module.FIXED_FAILURE_TERMINAL_IDENTITY
        ),
        "failure_execution_name": module.FIXED_FAILED_EXECUTION,
        "job_name": module.FIXED_JOB,
        "job_uid": module.FIXED_JOB_UID,
        "prior_execution_name": module.FIXED_FAILED_EXECUTION,
        "launch_ordinal": 1,
        "execution_claim_uri": topology["execution_claim_uri"],
        "replacement_image_digest": runtime["actual_image_digest"],
        "replacement_code_commit": runtime["actual_code_commit"],
        "replacement_build_receipt_identity": build_identity,
        "recovery_dispatcher_command": [
            "/usr/local/bin/python3.11", "-I", str(SCRIPT).replace(str(ROOT), "/app")
        ],
        "task_count": 1,
        "parallelism": 1,
        "maximum_task_retries": 0,
        "provider_task_wall_seconds": module.PROVIDER_TASK_WALL_SECONDS,
        "maximum_submission_calls": 1,
        "single_submission_consumed_on_acceptance": True,
        "uses_realized_outcomes": False,
        "scientific_inputs_changed": False,
    }, "launch_ownership_sha256")
    ownership_raw = module.canonical_bytes_v1(ownership)
    ownership_identity = _identity(topology["launch_ownership_uri"], ownership_raw)
    runtime["launch_ownership_identity"] = ownership_identity
    return {
        "runtime": runtime,
        "topology": topology,
        "build_receipt": build_receipt,
        "build_raw": build_raw,
        "build_identity": build_identity,
        "amendment": amendment,
        "amendment_raw": amendment_raw,
        "amendment_identity": amendment_identity,
        "ownership": ownership,
        "ownership_raw": ownership_raw,
        "ownership_identity": ownership_identity,
    }


def test_timeout_recovery_all_wall_checkpoints_agree() -> None:
    recovery = _module()
    assert publisher.MAXIMUM_PUBLISHER_WALL_SECONDS == 5_400
    assert recovery.RECOVERY_CHILD_WALL_SECONDS == 5_400
    assert task_manifest.MAXIMUM_DISPATCHER_WALL_SECONDS == 7_260
    assert recovery.PROVIDER_TASK_WALL_SECONDS == 7_260
    assert recovery.ORIGINAL_CHILD_WALL_SECONDS == 1_800
    terminal = next(
        row for row in task_manifest._LAYER_SPECS
        if row.layer_id == "terminal-root"
    )
    # The original immutable V7 manifest remains a 1,800-second authority;
    # only the exact amendment grants the replacement carrier 5,400 seconds.
    assert terminal.maximum_wall_seconds == 1_800
    assert recovery.RECOVERY_CHILD_WALL_SECONDS < recovery.PROVIDER_TASK_WALL_SECONDS


def test_timeout_change_does_not_change_publisher_science_or_memory_constants() -> None:
    assert publisher.MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES == 768_000_000
    assert publisher.MAXIMUM_COMPACT_EVALUATION_STATE_BYTES == 64_000_000
    assert publisher.MAXIMUM_PUBLISHER_PEAK_RSS_BYTES == 24 * 1024**3
    assert publisher.MAXIMUM_PUBLISHER_ADDRESS_SPACE_BYTES == 24 * 1024**3
    assert publisher.REQUIRED_CLOUD_RUN_CONTAINER_MEMORY_BYTES == 32 * 1024**3
    assert publisher.MAXIMUM_PUBLISHER_ENVELOPE_BYTES == 4_000_000
    assert publisher.PUBLISHER_MODES == (
        "publish-nomination",
        "publish-aggregate-finalists",
        "publish-terminal-root",
    )
    assert publisher.MODE_WRITE_ROLES["publish-terminal-root"] == ("root",)


def test_frozen_transport_sources_and_normalized_publisher_source_are_exact() -> None:
    aggregate_path = (
        ROOT / "src/nfl_dfs/research/"
        "corpus_r6_current_bank_crossed_screen_aggregate_v1.py"
    )
    aggregate_raw = aggregate_path.read_bytes()
    normalized = aggregate_raw.replace(
        b"MAXIMUM_PUBLISHER_WALL_SECONDS: Final = 5_400",
        b"MAXIMUM_PUBLISHER_WALL_SECONDS: Final = 1_800",
    )
    assert normalized != aggregate_raw
    assert sha256(normalized).hexdigest() == (
        "075c0b29c17b7d8376a775f80ce7863fd1f060ed2f9522eb10561a2d6f93ff35"
    )
    assert sha256((
        ROOT / "src/nfl_dfs/research/"
        "corpus_r6_current_bank_crossed_screen_task_manifest_v1.py"
    ).read_bytes()).hexdigest() == (
        "c7df1085381496482deb7c732e453964e8018702b3fc5f3ef11d4b8189ef2b1b"
    )
    assert sha256((
        ROOT / "scripts/"
        "run_corpus_r6_current_bank_crossed_screen_task_dispatcher_v1.py"
    ).read_bytes()).hexdigest() == (
        "03900f9601d3f9b1bec268bdcfe6e03b8d8dfcf09ba836287b70e236ab589e08"
    )


def test_preclient_environment_is_exact_and_redirect_free() -> None:
    recovery = _module()
    amendment_raw = b"{}"
    amendment_identity = _identity(
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-current-bank-crossed-screens/20260828-r6-current-bank-"
        "crossed-screen-v7/authorities/terminal-root-timeout-recovery-v1/"
        "amendment.json",
        amendment_raw,
    )
    ownership_identity = _identity(
        f"{recovery.FIXED_RECOVERY_PREFIX}launch-ownership.json", b"{}"
    )
    env = {
        recovery.ENABLE_ENV: "1",
        recovery.AMENDMENT_IDENTITY_ENV: json.dumps(
            amendment_identity, sort_keys=True, separators=(",", ":")
        ),
        recovery.LAUNCH_OWNERSHIP_IDENTITY_ENV: json.dumps(
            ownership_identity, sort_keys=True, separators=(",", ":")
        ),
        recovery.ACTUAL_IMAGE_DIGEST_ENV: "sha256:" + "a" * 64,
        recovery.ACTUAL_CODE_SHA_ENV: "b" * 40,
        "R6_RUNTIME_IMAGE_DIGEST": recovery.FIXED_ORIGINAL_IMAGE_DIGEST,
        "CODE_SHA": recovery.FIXED_ORIGINAL_CODE_COMMIT,
        "GOOGLE_CLOUD_PROJECT": recovery.FIXED_PROJECT,
        "CLOUD_RUN_JOB": recovery.FIXED_JOB,
        "CLOUD_RUN_EXECUTION": "one-execution",
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_COUNT": "1",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
    }
    observed = [
        "/usr/local/bin/python3.11",
        "-I",
        "/app/scripts/run_corpus_r6_current_bank_terminal_root_timeout_recovery_v1.py",
    ]
    retained = recovery.validate_preclient_environment_v1(
        env, observed_command=observed
    )
    assert retained["amendment_identity"] == amendment_identity
    assert retained["launch_ownership_identity"] == ownership_identity
    assert retained["actual_image_digest"] == "sha256:" + "a" * 64
    assert retained["logical_image_digest"] == recovery.FIXED_ORIGINAL_IMAGE_DIGEST


def test_recovery_source_preserves_exact_child_and_process_budget_validation() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "task_manifest.render_child_command_v1" in source
    assert "dispatcher._run_child_bounded_v1" in source
    assert "timeout_seconds=RECOVERY_CHILD_WALL_SECONDS" in source
    assert "task_manifest._exact_task_process_budget_bindings_v1" in source
    assert "read_allowlist_sha256" in source
    assert "write_allowlist_sha256" in source
    assert "transport.prove_exact_identity(publications[0])" in source
    assert "transport.prove_exact_identity(claim_identity)" in source
    assert "terminal_transport.prove_exact_identity(evidence_identity)" in source
    assert '"realized_outcomes_read": False' in source


def test_exact_amendment_ownership_and_clean_build_receipt_validate() -> None:
    recovery = _module()
    bundle = _recovery_bundle(recovery)
    amendment = recovery.validate_amendment_v1(
        bundle["amendment"],
        identity=bundle["amendment_identity"],
        runtime=bundle["runtime"],
    )
    assert recovery.validate_launch_ownership_v1(
        bundle["ownership"],
        identity=bundle["ownership_identity"],
        amendment=amendment,
        runtime=bundle["runtime"],
    )["launch_ordinal"] == 1
    assert recovery.validate_clean_build_receipt_v1(
        bundle["build_receipt"],
        identity=bundle["build_identity"],
        amendment=amendment,
        runtime=bundle["runtime"],
    )["clean_archive"] is True


def test_rehashed_amendment_authority_drift_fails_closed() -> None:
    recovery = _module()
    bundle = _recovery_bundle(recovery)
    cases = []

    def replace(field: str, value: object):
        def mutate(body: dict[str, object]) -> None:
            body[field] = deepcopy(value)
        return mutate

    for field, value in (
        ("original_image_digest", "sha256:" + "e" * 64),
        ("replacement_image_digest", recovery.FIXED_ORIGINAL_IMAGE_DIGEST),
        ("original_code_commit", "e" * 40),
        ("replacement_code_commit", recovery.FIXED_ORIGINAL_CODE_COMMIT),
        ("child_command", ["/bin/false"]),
        ("child_command_sha256", "e" * 64),
        ("request_sha256", "e" * 64),
        ("request_bytes", 1),
        ("publisher_process_budget_sha256", "e" * 64),
        ("read_allowlist_sha256", "e" * 64),
        ("write_allowlist_sha256", "e" * 64),
        ("root_uri", recovery.FIXED_OUTPUT_PREFIX + "other-root.json"),
        ("launch_ownership_uri", recovery.FIXED_RECOVERY_PREFIX + "other.json"),
        ("execution_claim_uri", recovery.FIXED_RECOVERY_PREFIX + "other.json"),
        (
            "recovery_terminal_evidence_uri",
            recovery.FIXED_RECOVERY_PREFIX + "other.json",
        ),
        ("terminal_receipt_uri", recovery.FIXED_RECOVERY_PREFIX + "other.json"),
        ("finalize_receipt_uri", recovery.FIXED_RECOVERY_PREFIX + "other.json"),
    ):
        cases.append((field, replace(field, value)))

    for field in (
        "failure_execution_identity",
        "original_manifest_identity",
        "request_identity",
        "process_budget_identity",
        "replacement_build_receipt_identity",
    ):
        def mutate_identity(body: dict[str, object], field: str = field) -> None:
            identity = deepcopy(body[field])
            identity["generation"] = "999"
            body[field] = identity
        cases.append((field, mutate_identity))
    for index in range(7):
        def mutate_receipt(body: dict[str, object], index: int = index) -> None:
            receipts = deepcopy(body["preserved_layer_receipt_identities"])
            receipts[index]["generation"] = "999"
            body["preserved_layer_receipt_identities"] = receipts
        cases.append((f"receipt-{index}", mutate_receipt))

    for label, mutate in cases:
        changed = deepcopy(bundle["amendment"])
        mutate(changed)
        changed = _with_hash(recovery, changed, "amendment_sha256")
        raw = recovery.canonical_bytes_v1(changed)
        identity = (
            bundle["amendment_identity"]
            if label == "replacement_build_receipt_identity"
            else _identity(bundle["topology"]["amendment_uri"], raw)
        )
        try:
            recovery.validate_amendment_v1(
                changed, identity=identity, runtime=bundle["runtime"]
            )
        except recovery.TerminalRootTimeoutRecoveryV1Error:
            continue
        pytest.fail(f"rehashed amendment drift was accepted: {label}")


def test_rehashed_launch_ownership_and_build_receipt_drift_fail_closed() -> None:
    recovery = _module()
    bundle = _recovery_bundle(recovery)
    amendment = recovery.validate_amendment_v1(
        bundle["amendment"],
        identity=bundle["amendment_identity"],
        runtime=bundle["runtime"],
    )
    ownership_cases = {
        "amendment_identity": {
            **bundle["amendment_identity"], "generation": "999"
        },
        "failure_execution_identity": {
            **recovery.FIXED_FAILURE_TERMINAL_IDENTITY, "generation": "999"
        },
        "execution_claim_uri": recovery.FIXED_RECOVERY_PREFIX + "other.json",
        "launch_ordinal": 2,
        "maximum_submission_calls": 2,
        "replacement_image_digest": recovery.FIXED_ORIGINAL_IMAGE_DIGEST,
        "uses_realized_outcomes": True,
    }
    for field, value in ownership_cases.items():
        changed = deepcopy(bundle["ownership"])
        changed[field] = deepcopy(value)
        changed = _with_hash(recovery, changed, "launch_ownership_sha256")
        raw = recovery.canonical_bytes_v1(changed)
        identity = _identity(bundle["topology"]["launch_ownership_uri"], raw)
        with pytest.raises(recovery.TerminalRootTimeoutRecoveryV1Error):
            recovery.validate_launch_ownership_v1(
                changed, identity=identity, amendment=amendment,
                runtime=bundle["runtime"],
            )

    build_cases = {
        "build_id": "",
        "source_commit": recovery.FIXED_ORIGINAL_CODE_COMMIT,
        "image_digest": recovery.FIXED_ORIGINAL_IMAGE_DIGEST,
        "clean_archive": False,
        "uncommitted_files_included": True,
        "recovery_source_sha256": "e" * 64,
        "publisher_source_sha256": "e" * 64,
        "normalized_publisher_source_sha256": "e" * 64,
        "uses_realized_outcomes": True,
    }
    for field, value in build_cases.items():
        changed = deepcopy(bundle["build_receipt"])
        changed[field] = value
        changed = _with_hash(recovery, changed, "build_receipt_sha256")
        raw = recovery.canonical_bytes_v1(changed)
        identity = _identity(recovery.FIXED_BUILD_RECEIPT_URI, raw)
        amended = deepcopy(amendment)
        amended["replacement_build_receipt_identity"] = identity
        with pytest.raises(recovery.TerminalRootTimeoutRecoveryV1Error):
            recovery.validate_clean_build_receipt_v1(
                changed, identity=identity, amendment=amended,
                runtime=bundle["runtime"],
            )
    changed = deepcopy(bundle["build_receipt"])
    changed["source_archive_identity"] = {
        **changed["source_archive_identity"],
        "uri": "gs://wrong-bucket/source/archive.tgz",
    }
    changed = _with_hash(recovery, changed, "build_receipt_sha256")
    raw = recovery.canonical_bytes_v1(changed)
    identity = _identity(recovery.FIXED_BUILD_RECEIPT_URI, raw)
    amended = deepcopy(amendment)
    amended["replacement_build_receipt_identity"] = identity
    with pytest.raises(recovery.TerminalRootTimeoutRecoveryV1Error):
        recovery.validate_clean_build_receipt_v1(
            changed, identity=identity, amendment=amended,
            runtime=bundle["runtime"],
        )


def test_wrapper_exact_read_budget_is_252_of_256() -> None:
    recovery = _module()
    assert recovery.EXPECTED_PRECHILD_EXACT_READS == (
        3 + (1 + 4 + 3 * 7 + 1 + sum(recovery.FIXED_PREDECESSOR_TASK_COUNTS)) + 3
    )
    assert recovery.EXPECTED_PRECHILD_EXACT_READS == 252
    authority = {
        "predecessor_layer_receipts": [
            {"task_records": [{}] * count}
            for count in recovery.FIXED_PREDECESSOR_TASK_COUNTS
        ]
    }
    recovery.validate_wrapper_read_budget_v1(
        authority=authority, observed_reads=252, maximum_reads=256
    )
    for observed, maximum in ((253, 256), (252, 251)):
        with pytest.raises(recovery.TerminalRootTimeoutRecoveryV1Error):
            recovery.validate_wrapper_read_budget_v1(
                authority=authority,
                observed_reads=observed,
                maximum_reads=maximum,
            )


def _fake_dispatcher_for_execute(
    recovery, bundle: dict[str, object], *, collision: bool,
) -> tuple[object, list[str]]:
    events: list[str] = []
    raw_by_uri = {
        bundle["amendment_identity"]["uri"]: bundle["amendment_raw"],
        bundle["ownership_identity"]["uri"]: bundle["ownership_raw"],
        bundle["build_identity"]["uri"]: bundle["build_raw"],
    }

    class FakeDeadline:
        def __init__(self, seconds: int) -> None:
            assert seconds == recovery.PROVIDER_TASK_WALL_SECONDS

    class FakeTransport:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs["validated_runtime"]["project_id"] == recovery.FIXED_PROJECT
            self._read_count = 0
            self._write_count = 0

        def read_exact(self, identity: dict[str, object]) -> bytes:
            self._read_count += 1
            uri = str(identity["uri"])
            if uri == bundle["amendment_identity"]["uri"]:
                events.append("read:amendment")
            elif uri == bundle["ownership_identity"]["uri"]:
                events.append("read:ownership")
            elif uri == bundle["build_identity"]["uri"]:
                events.append("read:build")
            else:
                events.append("read:unexpected")
            return raw_by_uri[uri]

        def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
            self._write_count += 1
            if uri == bundle["topology"]["execution_claim_uri"]:
                events.append("write:claim")
                if collision:
                    raise RuntimeError("claim collision")
            elif uri == bundle["topology"]["terminal_evidence_uri"]:
                events.append("write:terminal")
            else:
                raise AssertionError(uri)
            return {
                "uri": uri, "generation": "9",
                "sha256": sha256(raw).hexdigest(), "bytes": len(raw),
            }

        def prove_exact_identity(
            self, identity: dict[str, object]
        ) -> dict[str, object]:
            uri = identity["uri"]
            if uri == bundle["topology"]["execution_claim_uri"]:
                events.append("prove:claim")
            elif uri == bundle["topology"]["root_uri"]:
                events.append("prove:root")
            elif uri == bundle["topology"]["terminal_evidence_uri"]:
                events.append("prove:terminal")
            else:
                raise AssertionError(uri)
            return identity

    def run_child(**kwargs: object) -> dict[str, object]:
        events.append("child")
        assert kwargs["timeout_seconds"] == recovery.RECOVERY_CHILD_WALL_SECONDS
        return {
            "exit_code": 0,
            "timed_out": False,
            "stdout_overflow": False,
            "stderr_overflow": False,
            "stdout": b"{}",
            "stderr": b"",
            "elapsed_milliseconds": 2_000_000,
        }

    dispatcher = SimpleNamespace(
        MAXIMUM_EXACT_READS=256,
        EndToEndWallDeadlineV1=FakeDeadline,
        GCSExactReadTransportV1=FakeTransport,
        sanitized_child_environment_v1=lambda **kwargs: events.append("sanitize") or {},
        _run_child_bounded_v1=run_child,
    )
    return dispatcher, events


def test_execution_claim_precedes_all_frozen_reads_and_is_exact_proved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery = _module()
    bundle = _recovery_bundle(recovery)
    dispatcher, events = _fake_dispatcher_for_execute(
        recovery, bundle, collision=False
    )
    authority = {
        "manifest_identity": deepcopy(recovery.FIXED_ORIGINAL_MANIFEST_IDENTITY),
        "predecessor_layer_receipts": [
            {"task_records": [{}] * count}
            for count in recovery.FIXED_PREDECESSOR_TASK_COUNTS
        ],
    }

    def reopen(identity: object, *, read_exact) -> dict[str, object]:
        events.append("reopen:manifest")
        assert identity == recovery.FIXED_ORIGINAL_MANIFEST_IDENTITY
        read_exact.__self__._read_count = 249
        return authority

    task = {
        "child_command": list(recovery.FIXED_CHILD_COMMAND),
        "request": {},
        "child_stdout_byte_ceiling": 4_000_000,
        "child_stderr_byte_ceiling": 8_192,
        "child_command_sha256": recovery.FIXED_CHILD_COMMAND_SHA256,
        "request_sha256": recovery.FIXED_REQUEST_IDENTITY["sha256"],
        "request_bytes": recovery.FIXED_REQUEST_IDENTITY["bytes"],
    }
    monkeypatch.setattr(
        recovery.task_manifest, "reopen_task_manifest_authority_v1", reopen
    )
    monkeypatch.setattr(
        recovery, "_validate_original_task_v1", lambda amendment, value: ({}, task)
    )

    def validate_prechild(**kwargs: object) -> list[dict[str, object]]:
        events.append("validate:prechild")
        kwargs["read_exact"].__self__._read_count += 3
        return [{}]

    monkeypatch.setattr(
        recovery, "validate_frozen_prechild_authorities_v1", validate_prechild
    )
    monkeypatch.setattr(
        recovery.task_manifest,
        "_validate_child_envelope_transport_v1",
        lambda **kwargs: {"task_binding_evidence": {}},
    )
    monkeypatch.setattr(
        recovery.task_manifest,
        "validate_child_task_binding_evidence_v1",
        lambda *args, **kwargs: None,
    )
    root_identity = {
        "uri": bundle["topology"]["root_uri"],
        "generation": "10", "sha256": "d" * 64, "bytes": 2,
    }
    monkeypatch.setattr(
        recovery.task_manifest,
        "_publication_identities_from_child",
        lambda **kwargs: [root_identity],
    )
    result = recovery.execute_recovery_v1(
        runtime=bundle["runtime"], dispatcher=dispatcher
    )
    assert result["task_completed"] is True
    assert events == [
        "read:amendment", "read:ownership", "write:claim", "prove:claim",
        "read:build", "reopen:manifest", "validate:prechild", "sanitize",
        "child", "prove:root", "write:terminal", "prove:terminal",
    ]


def test_existing_execution_claim_aborts_before_manifest_or_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery = _module()
    bundle = _recovery_bundle(recovery)
    dispatcher, events = _fake_dispatcher_for_execute(
        recovery, bundle, collision=True
    )
    manifest_calls = 0
    child_calls = 0

    def forbidden_manifest(*args: object, **kwargs: object) -> object:
        nonlocal manifest_calls
        manifest_calls += 1
        raise AssertionError("manifest reopened after claim collision")

    def forbidden_child(**kwargs: object) -> object:
        nonlocal child_calls
        child_calls += 1
        raise AssertionError("child called after claim collision")

    monkeypatch.setattr(
        recovery.task_manifest,
        "reopen_task_manifest_authority_v1",
        forbidden_manifest,
    )
    dispatcher._run_child_bounded_v1 = forbidden_child
    with pytest.raises(RuntimeError, match="claim collision"):
        recovery.execute_recovery_v1(
            runtime=bundle["runtime"], dispatcher=dispatcher
        )
    assert events == ["read:amendment", "read:ownership", "write:claim"]
    assert manifest_calls == 0
    assert child_calls == 0
