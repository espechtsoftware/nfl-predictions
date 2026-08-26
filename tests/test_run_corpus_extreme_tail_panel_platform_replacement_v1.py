from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
import inspect
import json
from pathlib import Path
import subprocess
import sys

import pytest

from nfl_dfs.research import corpus_extreme_tail_panel_platform_replacement_v1 as replacement
from nfl_dfs.research import corpus_extreme_tail_panel_transport as transport
from nfl_dfs.research import corpus_parametric_batch as batch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import run_corpus_extreme_tail_panel_platform_replacement_v1 as controller


FLAGS_PATH = "/tmp/t230-ordinal6-attempt1-flags.json"
EXECUTION = replacement.REUSE_JOB + "-abcde"
EVIDENCE = {
    "uri": "gs://nfl-predictions-503414-raw/frozen/image-evidence.json",
    "generation": "123",
    "sha256": "a" * 64,
    "bytes": 321,
}


def _identity(uri: str, raw: bytes, generation: str = "101") -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _rehash(value: dict[str, object], field: str) -> None:
    value.pop(field, None)
    value[field] = batch.canonical_sha256(value)


def _false_closure() -> dict[str, bool]:
    return {field: False for field in controller._FALSE_AUTHORITY_FIELDS}


def _live_job() -> dict[str, object]:
    return {
        **controller._expected_live_job_projection_v1(),
        "describe_argv": list(replacement.LIVE_JOB_DESCRIBE_ARGV),
        "describe_stdout_sha256": "b" * 64,
        "describe_stdout_bytes": 4096,
        "cloud_describe_exactly_validated": True,
    }


def _intent(
    plan: Mapping[str, object], live_job: Mapping[str, object]
) -> dict[str, object]:
    body = {
        "schema_version": replacement.INTENT_SCHEMA,
        "run_id": transport.RUN_ID,
        "operation": replacement.OPERATION,
        "source_ordinal": replacement.SOURCE_ORDINAL,
        "max_replacement_worker_executions": 1,
        "replacement_worker_launch_plan": deepcopy(dict(plan)),
        "replacement_worker_launch_plan_sha256": plan[
            "worker_launch_plan_sha256"
        ],
        "replacement_live_job_projection": deepcopy(dict(live_job)),
        "replacement_live_job_projection_sha256": batch.canonical_sha256(
            live_job
        ),
        "post_submission_receipt_validation_law": deepcopy(
            dict(plan["post_submission_receipt_validation_law"])
        ),
        **_false_closure(),
    }
    body["platform_replacement_intent_sha256"] = batch.canonical_sha256(body)
    return body


class MemoryBackend:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[dict[str, object], bytes]] = {}
        self.generation = 100
        self.create_calls: list[str] = []
        self.probe_calls: list[str] = []
        self.race_intent = False
        self.ambiguous_intent_create = False
        self.fail_create_uri: str | None = None
        self.ambiguous_probe_uri: str | None = None

    def create(self, uri: str, raw: bytes) -> dict[str, object]:
        self.create_calls.append(uri)
        if self.fail_create_uri == uri:
            raise OSError("fixture create ambiguity")
        if uri == replacement.REPLACEMENT_INTENT_URI and self.ambiguous_intent_create:
            raise OSError("fixture intent create ambiguity")
        if uri == replacement.REPLACEMENT_INTENT_URI and self.race_intent:
            self.race_intent = False
            self._put(uri, raw)
            raise transport.JournalObjectExists(uri)
        if uri in self.objects:
            raise transport.JournalObjectExists(uri)
        return self._put(uri, raw)

    def _put(self, uri: str, raw: bytes) -> dict[str, object]:
        self.generation += 1
        retained = _identity(uri, raw, str(self.generation))
        self.objects[uri] = (retained, raw)
        return dict(retained)

    def read(self, identity: Mapping[str, object]) -> bytes:
        retained, raw = self.objects[str(identity["uri"])]
        assert retained == dict(identity)
        return raw

    def read_known_uri(self, uri: str) -> tuple[dict[str, object], bytes]:
        if uri not in self.objects:
            raise FileNotFoundError(uri)
        identity, raw = self.objects[uri]
        return dict(identity), raw

    def probe_known_uri_metadata(self, uri: str) -> Mapping[str, object] | None:
        self.probe_calls.append(uri)
        if uri == self.ambiguous_probe_uri:
            return "ambiguous"  # type: ignore[return-value]
        if uri not in self.objects:
            return None
        return dict(self.objects[uri][0])

    def observe_primary_terminal(self, execution_name: str) -> Mapping[str, object]:
        raise AssertionError(f"test-only injected candidate must own {execution_name}")


class FakeCloud:
    def __init__(self) -> None:
        self.live_job = _live_job()
        self.submission = controller.SubmissionObservation(
            returncode=0,
            stdout=(EXECUTION + "\n").encode("ascii"),
            stderr=b"",
        )
        self.submit_exception: Exception | None = None
        self.submitted_projection_mutation: tuple[str, object] | None = None
        self.live_job_mutation: tuple[str, object] | None = None
        self.second_live_job_mutation: tuple[str, object] | None = None
        self.job_observations = 0
        self.submission_calls = 0
        self.execution_observations = 0
        self.argv: tuple[str, ...] | None = None
        self.flags: dict[str, object] | None = None

    def observe_reused_job(self) -> Mapping[str, object]:
        self.job_observations += 1
        result = deepcopy(self.live_job)
        if self.live_job_mutation is not None:
            result[self.live_job_mutation[0]] = self.live_job_mutation[1]
        if (
            self.job_observations == 2
            and self.second_live_job_mutation is not None
        ):
            result[self.second_live_job_mutation[0]] = (
                self.second_live_job_mutation[1]
            )
        return result

    def submit(
        self,
        *,
        argv: Sequence[str],
        execution_flags: Mapping[str, object],
    ) -> controller.SubmissionObservation:
        self.submission_calls += 1
        self.argv = tuple(argv)
        self.flags = deepcopy(dict(execution_flags))
        if self.submit_exception is not None:
            raise self.submit_exception
        return self.submission

    def observe_submitted_execution(
        self,
        *,
        execution_name: str,
        worker_launch_plan_sha256: str,
        execution_flags_sha256: str,
    ) -> Mapping[str, object]:
        self.execution_observations += 1
        assert self.flags is not None
        result: dict[str, object] = {
            "schema_version": controller.SUBMITTED_EXECUTION_PROJECTION_SCHEMA,
            "execution_name": execution_name,
            "job": replacement.REUSE_JOB,
            "image": replacement.FROZEN_D2_URI,
            "service_account": replacement.SERVICE_ACCOUNT,
            "cpu": "8",
            "memory": "32Gi",
            "task_count": 1,
            "parallelism": 1,
            "max_retries": 0,
            "task_timeout_seconds": transport.TASK_TIMEOUT_SECONDS,
            "command": ["bash"],
            "args": deepcopy(self.flags["--args"]),
            "configured_environment": deepcopy(
                self.flags["--update-env-vars"]
            ),
            "runtime_evidence_volume": controller._expected_live_job_projection_v1()[
                "runtime_evidence_volume"
            ],
            "full_execution_envelope_exactly_validated": True,
            "worker_launch_plan_sha256": worker_launch_plan_sha256,
            "execution_flags_sha256": execution_flags_sha256,
            "describe_argv": controller._submitted_execution_describe_argv(
                execution_name
            ),
            "describe_stdout_sha256": "c" * 64,
            "describe_stdout_bytes": 8192,
        }
        if self.submitted_projection_mutation is not None:
            result[self.submitted_projection_mutation[0]] = (
                self.submitted_projection_mutation[1]
            )
        return result


class CandidateFixture:
    def __init__(self) -> None:
        self.calls = 0
        self.raise_error: Exception | None = None
        self.omit_plan = False

    def __call__(
        self,
        *,
        backend: MemoryBackend,
        replacement_worker_launch_plan: Mapping[str, object],
        replacement_live_job_projection: Mapping[str, object],
    ) -> Mapping[str, object]:
        del backend
        self.calls += 1
        if self.raise_error is not None:
            raise self.raise_error
        intent = _intent(
            replacement_worker_launch_plan,
            replacement_live_job_projection,
        )
        if self.omit_plan:
            del intent["replacement_worker_launch_plan"]
            _rehash(intent, "platform_replacement_intent_sha256")
        return {
            "schema_version": "test-candidate/v1",
            "disposition": "offline-intent-candidate-only",
            "intent_identity": None,
            "intent": intent,
            "intent_created_by_this_invocation": False,
            "cloud_execution_submission_allowed_this_invocation": False,
            "same_process_launch_controller_review_required": True,
            "resolve_only": True,
            **_false_closure(),
        }


def _validate_test_intent(value: object) -> Mapping[str, object]:
    assert isinstance(value, Mapping)
    item = deepcopy(dict(value))
    retained = item.pop("platform_replacement_intent_sha256")
    assert retained == batch.canonical_sha256(item)
    assert item["max_replacement_worker_executions"] == 1
    return dict(value)


def _existing_resolver(
    *,
    backend: MemoryBackend,
    replacement_worker_launch_plan: Mapping[str, object],
    replacement_live_job_projection: Mapping[str, object],
) -> Mapping[str, object]:
    del replacement_worker_launch_plan, replacement_live_job_projection
    identity, _raw = backend.read_known_uri(replacement.REPLACEMENT_INTENT_URI)
    return {
        "disposition": "equal-existing-intent-resolve-only",
        "intent_identity": identity,
        "intent_created_by_this_invocation": False,
        "cloud_execution_submission_allowed_this_invocation": False,
        "resolve_only": True,
        **_false_closure(),
    }


def _launch(
    backend: MemoryBackend,
    cloud: FakeCloud,
    *,
    candidate: CandidateFixture | None = None,
    existing_resolver=_existing_resolver,
) -> dict[str, object]:
    retained_candidate = candidate or CandidateFixture()
    return controller._launch_replacement_worker_same_process_v1(
        backend=backend,
        submitter=cloud,
        flags_path=FLAGS_PATH,
        candidate_builder=retained_candidate,
        existing_intent_resolver=existing_resolver,
        intent_validator=_validate_test_intent,
        evidence_resolver=lambda _backend: deepcopy(EVIDENCE),
    )


def test_launch_plan_is_deterministic_direct_core_attempt_one() -> None:
    left = controller.build_worker_launch_plan_v1(
        image_evidence_identity=EVIDENCE, flags_path=FLAGS_PATH
    )
    right = controller.build_worker_launch_plan_v1(
        image_evidence_identity=EVIDENCE, flags_path=FLAGS_PATH
    )

    assert left == right == controller.validate_worker_launch_plan_v1(left)
    assert left["runtime_attempt_ordinal"] == 1
    assert left["max_submission_calls"] == 1
    assert left["max_retries"] == 0
    assert left["task_count"] == left["parallelism"] == 1
    assert "run-slate" in left["runtime_payload"]
    assert "--runtime-attempt-ordinal 1" in left["runtime_payload"]
    assert " run-stage" not in left["runtime_payload"]
    assert "--async" in left["gcloud_argv"]
    assert left["dynamic_environment_fields"] == [
        "T230_REPLACEMENT_INTENT_GENERATION",
        "T230_REPLACEMENT_INTENT_SHA256",
        "T230_REPLACEMENT_INTENT_BYTES",
    ]
    assert all(left[field] is False for field in controller._FALSE_AUTHORITY_FIELDS)


def test_flags_are_exact_plan_payload_plus_created_intent_derivation() -> None:
    plan = controller.build_worker_launch_plan_v1(
        image_evidence_identity=EVIDENCE, flags_path=FLAGS_PATH
    )
    raw = b'{"intent":"fixture"}'
    identity = _identity(replacement.REPLACEMENT_INTENT_URI, raw)
    flags = controller.build_worker_execution_flags_v1(
        launch_plan=plan, replacement_intent_identity=identity
    )

    assert controller.validate_worker_execution_flags_v1(flags) == flags
    assert flags["flags"]["--args"] == ["-ceu", plan["runtime_payload"]]
    environment = flags["flags"]["--update-env-vars"]
    assert environment["T230_REPLACEMENT_INTENT_URI"] == identity["uri"]
    assert environment["T230_REPLACEMENT_INTENT_GENERATION"] == "101"
    assert environment["T230_REPLACEMENT_INTENT_SHA256"] == identity["sha256"]
    assert environment["T230_REPLACEMENT_INTENT_BYTES"] == str(identity["bytes"])

    tampered = deepcopy(flags)
    tampered["flags"]["--args"][1] += "\ntrue"
    tampered["flags_sha256"] = batch.canonical_sha256(tampered["flags"])
    tampered["flags_bytes"] = len(batch.canonical_json_bytes(tampered["flags"]))
    _rehash(tampered, "execution_flags_envelope_sha256")
    with pytest.raises(controller.T230PlatformReplacementControllerError):
        controller.validate_worker_execution_flags_v1(tampered)


def test_public_launch_entry_exposes_no_candidate_validator_or_evidence_injection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parameters = inspect.signature(
        controller.launch_replacement_worker_same_process_v1
    ).parameters
    assert set(parameters) == {"backend", "submitter"}
    captured: dict[str, object] = {}

    def fake_private(**kwargs):
        captured.update(kwargs)
        return {"disposition": "fixed-public-launch-fixture"}

    monkeypatch.setattr(
        controller, "_launch_replacement_worker_same_process_v1", fake_private
    )
    result = controller.launch_replacement_worker_same_process_v1(
        backend=object(), submitter=object()
    )
    assert result["disposition"] == "fixed-public-launch-fixture"
    assert captured["flags_path"] == (
        replacement.REAL_ARTIFACT_PREFLIGHT_FLAGS_PATH
    )


def test_first_creator_submits_once_then_publishes_exact_handshake() -> None:
    backend = MemoryBackend()
    cloud = FakeCloud()

    result = _launch(backend, cloud)

    assert result["disposition"] == (
        "replacement-worker-submitted-once-handshake-durable"
    )
    assert result["submission_call_count"] == 1
    assert cloud.submission_calls == cloud.execution_observations == 1
    assert cloud.job_observations == 2
    assert cloud.argv is not None and "--async" in cloud.argv
    assert set(backend.objects) >= {
        replacement.REPLACEMENT_INTENT_URI,
        replacement.REPLACEMENT_LAUNCH_OWNERSHIP_URI,
        replacement.REPLACEMENT_STAGE_START_URI,
    }
    assert replacement.REPLACEMENT_EXECUTION_TERMINAL_URI not in backend.objects
    ownership = json.loads(
        backend.objects[replacement.REPLACEMENT_LAUNCH_OWNERSHIP_URI][1]
    )
    assert ownership["submission_call_count"] == 1
    assert ownership["configured_environment_entry_count"] > 0
    assert ownership["request_consumed"] is True


def test_handshake_receipts_reject_coherently_rehashed_widening_and_drift() -> None:
    backend = MemoryBackend()
    cloud = FakeCloud()
    _launch(backend, cloud)
    ownership = json.loads(
        backend.objects[replacement.REPLACEMENT_LAUNCH_OWNERSHIP_URI][1]
    )
    stage_start = json.loads(
        backend.objects[replacement.REPLACEMENT_STAGE_START_URI][1]
    )

    assert controller._validate_worker_launch_ownership_v1(
        ownership, replacement_intent_validator=_validate_test_intent
    ) == ownership
    assert (
        controller._validate_replacement_worker_stage_start_v1(
            stage_start, replacement_intent_validator=_validate_test_intent
        )
        == stage_start
    )

    ownership_extra = deepcopy(ownership)
    ownership_extra["coherently_rehashed_extra"] = False
    _rehash(ownership_extra, "launch_ownership_sha256")
    ownership_false_authority = deepcopy(ownership)
    ownership_false_authority["uses_realized_outcomes"] = True
    _rehash(ownership_false_authority, "launch_ownership_sha256")
    ownership_projection_drift = deepcopy(ownership)
    ownership_projection_drift["submitted_execution_projection"]["image"] = (
        "mutable:latest"
    )
    ownership_projection_drift["submitted_execution_projection_sha256"] = (
        batch.canonical_sha256(
            ownership_projection_drift["submitted_execution_projection"]
        )
    )
    _rehash(ownership_projection_drift, "launch_ownership_sha256")
    ownership_intent_hash_drift = deepcopy(ownership)
    ownership_intent_hash_drift["platform_replacement_intent_sha256"] = (
        "f" * 64
    )
    _rehash(ownership_intent_hash_drift, "launch_ownership_sha256")
    ownership_exact_intent_drift = deepcopy(ownership)
    embedded_intent = ownership_exact_intent_drift["replacement_intent"]
    embedded_intent["max_replacement_worker_executions"] = 2
    _rehash(embedded_intent, "platform_replacement_intent_sha256")
    embedded_intent_raw = batch.canonical_json_bytes(embedded_intent)
    ownership_exact_intent_drift["platform_replacement_intent_sha256"] = (
        embedded_intent["platform_replacement_intent_sha256"]
    )
    ownership_exact_intent_drift["replacement_intent_identity"]["sha256"] = (
        sha256(embedded_intent_raw).hexdigest()
    )
    ownership_exact_intent_drift["replacement_intent_identity"]["bytes"] = (
        len(embedded_intent_raw)
    )
    _rehash(ownership_exact_intent_drift, "launch_ownership_sha256")
    for candidate in (
        ownership_extra,
        ownership_false_authority,
        ownership_projection_drift,
        ownership_intent_hash_drift,
        ownership_exact_intent_drift,
    ):
        with pytest.raises(controller.T230PlatformReplacementControllerError):
            controller._validate_worker_launch_ownership_v1(
                candidate, replacement_intent_validator=_validate_test_intent
            )

    stage_extra = deepcopy(stage_start)
    stage_extra["coherently_rehashed_extra"] = False
    _rehash(stage_extra, "replacement_stage_start_sha256")
    stage_envelope_drift = deepcopy(stage_start)
    stage_envelope_drift["execution_envelope"]["max_retries"] = 1
    _rehash(stage_envelope_drift, "replacement_stage_start_sha256")
    stage_lineage_drift = deepcopy(stage_start)
    stage_lineage_drift["compute_release_identity"]["generation"] = "999"
    _rehash(stage_lineage_drift, "replacement_stage_start_sha256")
    stage_false_authority = deepcopy(stage_start)
    stage_false_authority["lane_resume_licensed"] = True
    _rehash(stage_false_authority, "replacement_stage_start_sha256")
    stage_intent_hash_drift = deepcopy(stage_start)
    nested_ownership = stage_intent_hash_drift["launch_ownership"]
    nested_ownership["platform_replacement_intent_sha256"] = "f" * 64
    _rehash(nested_ownership, "launch_ownership_sha256")
    stage_intent_hash_drift["launch_ownership_sha256"] = nested_ownership[
        "launch_ownership_sha256"
    ]
    nested_raw = batch.canonical_json_bytes(nested_ownership)
    stage_intent_hash_drift["launch_ownership_identity"]["sha256"] = (
        sha256(nested_raw).hexdigest()
    )
    stage_intent_hash_drift["launch_ownership_identity"]["bytes"] = len(
        nested_raw
    )
    _rehash(stage_intent_hash_drift, "replacement_stage_start_sha256")
    stage_exact_intent_drift = deepcopy(stage_start)
    nested_ownership = stage_exact_intent_drift["launch_ownership"]
    embedded_intent = nested_ownership["replacement_intent"]
    embedded_intent["max_replacement_worker_executions"] = 2
    _rehash(embedded_intent, "platform_replacement_intent_sha256")
    embedded_intent_raw = batch.canonical_json_bytes(embedded_intent)
    nested_ownership["platform_replacement_intent_sha256"] = embedded_intent[
        "platform_replacement_intent_sha256"
    ]
    nested_ownership["replacement_intent_identity"]["sha256"] = sha256(
        embedded_intent_raw
    ).hexdigest()
    nested_ownership["replacement_intent_identity"]["bytes"] = len(
        embedded_intent_raw
    )
    _rehash(nested_ownership, "launch_ownership_sha256")
    stage_exact_intent_drift["replacement_intent_identity"] = deepcopy(
        nested_ownership["replacement_intent_identity"]
    )
    stage_exact_intent_drift["launch_ownership_sha256"] = nested_ownership[
        "launch_ownership_sha256"
    ]
    nested_raw = batch.canonical_json_bytes(nested_ownership)
    stage_exact_intent_drift["launch_ownership_identity"]["sha256"] = sha256(
        nested_raw
    ).hexdigest()
    stage_exact_intent_drift["launch_ownership_identity"]["bytes"] = len(
        nested_raw
    )
    _rehash(stage_exact_intent_drift, "replacement_stage_start_sha256")
    for candidate in (
        stage_extra,
        stage_envelope_drift,
        stage_lineage_drift,
        stage_false_authority,
        stage_intent_hash_drift,
        stage_exact_intent_drift,
    ):
        with pytest.raises(controller.T230PlatformReplacementControllerError):
            controller._validate_replacement_worker_stage_start_v1(
                candidate, replacement_intent_validator=_validate_test_intent
            )


def test_in_worker_guard_exactly_checks_receipts_and_false_authority() -> None:
    assert set(inspect.signature(
        controller.validate_worker_launch_ownership_v1
    ).parameters) == {"value"}
    assert set(inspect.signature(
        controller.validate_replacement_worker_stage_start_v1
    ).parameters) == {"value"}
    guard = controller._handshake_guard_source_v1()
    assert "assert set(ownership)==set(" in guard
    assert "assert set(start)==set(" in guard
    assert "assert start['launch_ownership']==ownership" in guard
    assert "for field in" in guard
    for field in controller._FALSE_AUTHORITY_FIELDS:
        assert field in guard


def test_existing_equal_and_create_race_are_resolve_only_with_zero_submit() -> None:
    existing_backend = MemoryBackend()
    existing_backend._put(replacement.REPLACEMENT_INTENT_URI, b"existing")
    existing_cloud = FakeCloud()
    candidate = CandidateFixture()

    existing = _launch(existing_backend, existing_cloud, candidate=candidate)

    assert existing["disposition"] == "replacement-intent-existing-resolve-only"
    assert existing_cloud.submission_calls == 0
    assert candidate.calls == 0

    racing_backend = MemoryBackend()
    racing_backend.race_intent = True
    racing_cloud = FakeCloud()
    racing = _launch(racing_backend, racing_cloud)
    assert racing["disposition"] == "replacement-intent-existing-resolve-only"
    assert racing_cloud.submission_calls == 0
    assert replacement.REPLACEMENT_LAUNCH_OWNERSHIP_URI not in racing_backend.objects


def test_invalid_live_job_candidate_and_ambiguous_create_never_submit() -> None:
    live_backend = MemoryBackend()
    live_cloud = FakeCloud()
    live_cloud.live_job_mutation = ("max_retries", 1)
    with pytest.raises(controller.T230PlatformReplacementControllerError):
        _launch(live_backend, live_cloud)
    assert live_cloud.submission_calls == 0
    assert live_backend.objects == {}

    candidate_backend = MemoryBackend()
    candidate_cloud = FakeCloud()
    invalid_candidate = CandidateFixture()
    invalid_candidate.omit_plan = True
    with pytest.raises(controller.T230PlatformReplacementControllerError):
        _launch(candidate_backend, candidate_cloud, candidate=invalid_candidate)
    assert candidate_cloud.submission_calls == 0
    assert candidate_backend.objects == {}

    create_backend = MemoryBackend()
    create_backend.ambiguous_intent_create = True
    create_cloud = FakeCloud()
    with pytest.raises(controller.T230PlatformReplacementControllerError):
        _launch(create_backend, create_cloud)
    assert create_cloud.submission_calls == 0


def test_precreate_live_job_drift_never_creates_intent_or_submits() -> None:
    backend = MemoryBackend()
    cloud = FakeCloud()
    cloud.second_live_job_mutation = ("max_retries", 1)

    with pytest.raises(controller.T230PlatformReplacementControllerError):
        _launch(backend, cloud)

    assert cloud.job_observations == 2
    assert cloud.submission_calls == 0
    assert backend.create_calls == []
    assert backend.objects == {}


@pytest.mark.parametrize(
    "observation",
    [
        controller.SubmissionObservation(1, b"", b"failed"),
        controller.SubmissionObservation(0, b"", b""),
        controller.SubmissionObservation(0, b"not-an-execution\n", b""),
        controller.SubmissionObservation(
            0, (replacement.FAILED_EXECUTION + "\n").encode("ascii"), b""
        ),
    ],
)
def test_nonzero_or_ambiguous_response_is_consumed_and_durably_terminal(
    observation: controller.SubmissionObservation,
) -> None:
    backend = MemoryBackend()
    cloud = FakeCloud()
    cloud.submission = observation

    result = _launch(backend, cloud)

    assert result["disposition"] == (
        "replacement-worker-submission-ambiguous-consumed"
    )
    assert cloud.submission_calls == 1
    assert cloud.execution_observations == 0
    assert replacement.REPLACEMENT_EXECUTION_TERMINAL_URI in backend.objects
    assert replacement.REPLACEMENT_LAUNCH_OWNERSHIP_URI not in backend.objects
    assert replacement.REPLACEMENT_STAGE_START_URI not in backend.objects


def test_adapter_exception_and_known_execution_envelope_mismatch_are_terminal() -> None:
    exception_backend = MemoryBackend()
    exception_cloud = FakeCloud()
    exception_cloud.submit_exception = OSError("lost submission response")
    exception_result = _launch(exception_backend, exception_cloud)
    assert exception_result["submission_call_count"] == 1
    assert exception_cloud.submission_calls == 1
    assert replacement.REPLACEMENT_EXECUTION_TERMINAL_URI in exception_backend.objects

    mismatch_backend = MemoryBackend()
    mismatch_cloud = FakeCloud()
    mismatch_cloud.submitted_projection_mutation = ("image", "mutable:latest")
    mismatch_result = _launch(mismatch_backend, mismatch_cloud)
    assert mismatch_result["disposition"] == (
        "replacement-worker-submitted-envelope-unverified-consumed"
    )
    assert mismatch_cloud.submission_calls == 1
    assert mismatch_cloud.execution_observations == 1
    assert replacement.REPLACEMENT_EXECUTION_TERMINAL_URI in mismatch_backend.objects
    assert replacement.REPLACEMENT_LAUNCH_OWNERSHIP_URI not in mismatch_backend.objects


def test_post_submit_publication_failure_never_makes_a_second_submit_call() -> None:
    backend = MemoryBackend()
    backend.fail_create_uri = replacement.REPLACEMENT_LAUNCH_OWNERSHIP_URI
    cloud = FakeCloud()

    result = _launch(backend, cloud)

    assert result["disposition"] == (
        "replacement-worker-ownership-undurable-consumed"
    )
    assert cloud.submission_calls == 1
    assert cloud.execution_observations == 1
    assert replacement.REPLACEMENT_EXECUTION_TERMINAL_URI in backend.objects
    assert replacement.REPLACEMENT_STAGE_START_URI not in backend.objects

    start_backend = MemoryBackend()
    start_backend.fail_create_uri = replacement.REPLACEMENT_STAGE_START_URI
    start_cloud = FakeCloud()
    start_result = _launch(start_backend, start_cloud)
    assert start_result["disposition"] == (
        "replacement-worker-stage-start-undurable-consumed"
    )
    assert start_cloud.submission_calls == 1
    assert replacement.REPLACEMENT_LAUNCH_OWNERSHIP_URI in start_backend.objects
    assert replacement.REPLACEMENT_EXECUTION_TERMINAL_URI in start_backend.objects


def test_controller_grants_no_bridge_resume_finalizer_or_scoring_action() -> None:
    source = (
        ROOT / "scripts/run_corpus_extreme_tail_panel_platform_replacement_v1.py"
    ).read_text(encoding="utf-8")
    assert "def launch_replacement_worker_same_process_v1" in source
    assert "bridge_verifier_submitted\": False" in source
    assert "lane_resume_allowed\": False" in source
    assert "historical_scoring_licensed" in source
    assert "gcloud run jobs executions list" not in source
    assert "gcloud storage ls" not in source


def _frozen_primary_payload() -> str:
    source = (
        ROOT / "scripts/cloud_corpus_extreme_tail_panel_v1_reuse.sh"
    ).read_text(encoding="utf-8")
    payload = source.split("cat <<'RUNTIME'\n", 1)[1].split(
        "\nRUNTIME\n", 1
    )[0]
    assert len(payload.encode("utf-8")) == (
        replacement.FROZEN_PRIMARY_RUNTIME_PAYLOAD_BYTES
    )
    assert sha256(payload.encode("utf-8")).hexdigest() == (
        replacement.FROZEN_PRIMARY_RUNTIME_PAYLOAD_SHA256
    )
    return payload


def _task_spec(
    *,
    args: list[str],
    configured_environment: Mapping[str, str],
    omitted_value_names: frozenset[str] = frozenset(),
) -> dict[str, object]:
    environment_rows: list[dict[str, str]] = []
    for key, value in sorted(configured_environment.items()):
        row = {"name": key}
        if key not in omitted_value_names:
            row["value"] = value
        environment_rows.append(row)
    return {
        "containers": [{
            "image": replacement.FROZEN_D2_URI,
            "command": ["bash"],
            "args": args,
            "env": environment_rows,
            "resources": {"limits": {"cpu": "8", "memory": "32Gi"}},
            "volumeMounts": [{
                "name": "foundry-t230-runtime-evidence",
                "mountPath": "/etc/nfl-dfs",
            }],
        }],
        "maxRetries": 0,
        "serviceAccountName": replacement.SERVICE_ACCOUNT,
        "timeoutSeconds": "21600",
        "volumes": [{
            "name": "foundry-t230-runtime-evidence",
            "emptyDir": {"medium": "Memory", "sizeLimit": "1Mi"},
        }],
    }


def _execution_body(
    *,
    execution_name: str,
    args: list[str],
    configured_environment: Mapping[str, str],
    terminal: bool,
    omitted_value_names: frozenset[str] = frozenset(),
) -> dict[str, object]:
    body: dict[str, object] = {
        "apiVersion": "run.googleapis.com/v1",
        "kind": "Execution",
        "metadata": {
            "name": execution_name,
            "labels": {"run.googleapis.com/job": replacement.REUSE_JOB},
        },
        "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {
                "spec": _task_spec(
                    args=args,
                    configured_environment=configured_environment,
                    omitted_value_names=omitted_value_names,
                )
            },
        },
    }
    if terminal:
        body["status"] = {
            "completionTime": "2026-08-25T22:00:00Z",
            "conditions": [{
                "type": "Completed",
                "status": "False",
                "message": (
                    "Task atlas-minimal-c-s2023-w1-v1-rffts-task0 failed "
                    "with exit code: 0 and message: Internal error."
                ),
            }],
            "failedCount": 1,
        }
    return body


def _primary_task_body() -> dict[str, object]:
    return {
        "apiVersion": "run.googleapis.com/v1",
        "kind": "Task",
        "metadata": {
            "name": replacement.FAILED_TASK,
            "labels": {
                "run.googleapis.com/execution": replacement.FAILED_EXECUTION,
                "run.googleapis.com/job": replacement.REUSE_JOB,
                "cloud.googleapis.com/location": transport.REGION,
            },
        },
        "spec": {},
        "status": {
            "conditions": [{
                "type": "Completed",
                "status": "False",
                "message": "Internal error.",
            }],
            "lastAttemptResult": {
                "status": {"code": 13, "message": "Internal error."},
            },
        },
    }


def _job_body() -> dict[str, object]:
    return {
        "apiVersion": "run.googleapis.com/v1",
        "kind": "Job",
        "metadata": {"name": replacement.REUSE_JOB},
        "spec": {
            "template": {
                "spec": {
                    "taskCount": 1,
                    "parallelism": 1,
                    "template": {
                        "spec": _task_spec(
                            args=[
                                "-ceu",
                                "python scripts/run_corpus_extreme_tail_panel_transport_v1.py parked",
                            ],
                            configured_environment={},
                        )
                    },
                }
            }
        },
    }


def _json_raw(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _production_shaped_primary_environment() -> dict[str, str]:
    assert len(controller._CLOUD_RUN_NAME_ONLY_EMPTY_ENVIRONMENT_NAMES) == 16
    assert controller._CLOUD_RUN_NAME_ONLY_EMPTY_ENVIRONMENT_NAMES == frozenset(
        replacement.PRIMARY_NAME_ONLY_EMPTY_ENVIRONMENT_NAMES
    )
    return {
        "EXACT_NONEMPTY_FIXTURE": "1",
        **{
            name: ""
            for name in controller._CLOUD_RUN_NAME_ONLY_EMPTY_ENVIRONMENT_NAMES
        },
    }


def _install_subprocess_responses(
    monkeypatch: pytest.MonkeyPatch, responses: Sequence[bytes]
) -> list[list[str]]:
    retained = iter(responses)
    calls: list[list[str]] = []

    def fake_run(argv, **_kwargs):
        calls.append(list(argv))
        return subprocess.CompletedProcess(
            args=list(argv), returncode=0, stdout=next(retained), stderr=b""
        )

    monkeypatch.setattr(controller.subprocess, "run", fake_run)
    return calls


def test_production_primary_observer_accepts_exact_one_task_and_exact_argv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = _production_shaped_primary_environment()
    omitted = controller._CLOUD_RUN_NAME_ONLY_EMPTY_ENVIRONMENT_NAMES
    payload = _frozen_primary_payload()
    execution_body = _execution_body(
        execution_name=replacement.FAILED_EXECUTION,
        args=["-ceu", payload],
        configured_environment=environment,
        terminal=True,
        omitted_value_names=omitted,
    )
    task_body = _primary_task_body()
    calls = _install_subprocess_responses(
        monkeypatch, [_json_raw(execution_body), _json_raw([task_body])]
    )

    projection = controller.SubprocessCloudSubmitter().observe_primary_terminal(
        execution_name=replacement.FAILED_EXECUTION,
        expected_environment=environment,
    )

    assert projection["system_platform_error_observed"] is True
    assert projection["configured_environment_entry_count"] == 17
    assert projection["task_spec"] == {}
    assert projection["task_status_index_present"] is False
    assert projection["task_status_retried_present"] is False
    assert projection["task_last_attempt_exit_code_present"] is False
    assert projection["execution_completed_message_exit_code"] == 0
    assert {
        "cloud_task_index",
        "cloud_task_attempt",
        "cloud_task_retry_count",
        "reported_exit_code",
    }.isdisjoint(projection)
    assert calls == [
        list(replacement.EXECUTION_DESCRIBE_ARGV),
        list(replacement.TASK_DESCRIBE_ARGV),
    ]
    assert calls[1] == [
        "gcloud", "beta", "run", "jobs", "executions", "tasks", "list",
        f"--execution={replacement.FAILED_EXECUTION}",
        f"--project={transport.PROJECT}",
        f"--region={transport.REGION}",
        "--limit=2", "--format=json",
    ]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-expected-nonempty",
        "missing-unknown",
        "value-from",
        "extra-key",
    ],
)
def test_primary_observer_rejects_unfrozen_name_only_and_nonliteral_rows(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    environment = _production_shaped_primary_environment()
    omitted = controller._CLOUD_RUN_NAME_ONLY_EMPTY_ENVIRONMENT_NAMES
    payload = _frozen_primary_payload()
    execution_body = _execution_body(
        execution_name=replacement.FAILED_EXECUTION,
        args=["-ceu", payload],
        configured_environment=environment,
        terminal=True,
        omitted_value_names=omitted,
    )
    task_body = _primary_task_body()
    rows = execution_body["spec"]["template"]["spec"]["containers"][0]["env"]
    if mutation == "missing-expected-nonempty":
        next(
            row for row in rows
            if row["name"] == "EXACT_NONEMPTY_FIXTURE"
        ).pop("value")
    elif mutation == "missing-unknown":
        rows.append({"name": "T230_UNKNOWN_NAME_ONLY"})
    elif mutation == "value-from":
        rows[0]["valueFrom"] = {"secretKeyRef": {"name": "forbidden"}}
    elif mutation == "extra-key":
        rows[0]["unexpected"] = False
    _install_subprocess_responses(
        monkeypatch, [_json_raw(execution_body), _json_raw([task_body])]
    )

    with pytest.raises(controller.T230PlatformReplacementControllerError):
        controller.SubprocessCloudSubmitter().observe_primary_terminal(
            execution_name=replacement.FAILED_EXECUTION,
            expected_environment=environment,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "zero-tasks",
        "two-tasks",
        "wrong-task",
        "wrong-execution-label",
        "wrong-job-label",
        "wrong-location-label",
        "last-attempt-message-punctuation",
        "task-condition-message-punctuation",
        "execution-completed-message-punctuation",
        "status-code",
        "fabricated-task-spec",
        "task-index-present-zero",
        "task-index-present-different",
        "task-retried-present-zero",
        "task-retried-present-different",
        "task-exit-code-present-zero",
        "task-exit-code-present-different",
        "execution-image",
        "execution-environment",
    ],
)
def test_production_primary_observer_rejects_task_and_envelope_drift(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    expected_environment = {"EXACT_FIXTURE": "1"}
    payload = _frozen_primary_payload()
    execution_body = _execution_body(
        execution_name=replacement.FAILED_EXECUTION,
        args=["-ceu", payload],
        configured_environment=expected_environment,
        terminal=True,
    )
    task_body = _primary_task_body()
    task_rows = [task_body]
    if mutation == "zero-tasks":
        task_rows = []
    elif mutation == "two-tasks":
        task_rows = [task_body, deepcopy(task_body)]
    elif mutation == "wrong-task":
        task_body["metadata"]["name"] += "-other"
    elif mutation == "wrong-execution-label":
        task_body["metadata"]["labels"]["run.googleapis.com/execution"] = "other"
    elif mutation == "wrong-job-label":
        task_body["metadata"]["labels"]["run.googleapis.com/job"] = "other"
    elif mutation == "wrong-location-label":
        task_body["metadata"]["labels"]["cloud.googleapis.com/location"] = "other"
    elif mutation == "last-attempt-message-punctuation":
        task_body["status"]["lastAttemptResult"]["status"]["message"] = "Internal error"
    elif mutation == "task-condition-message-punctuation":
        task_body["status"]["conditions"][0]["message"] = "Internal error"
    elif mutation == "execution-completed-message-punctuation":
        execution_body["status"]["conditions"][0]["message"] = (
            "Task atlas-minimal-c-s2023-w1-v1-rffts-task0 failed with "
            "exit code: 0 and message: Internal error"
        )
    elif mutation == "status-code":
        task_body["status"]["lastAttemptResult"]["status"]["code"] = 12
    elif mutation == "fabricated-task-spec":
        task_body["spec"] = _task_spec(
            args=["-ceu", payload],
            configured_environment=expected_environment,
        )
    elif mutation == "task-index-present-zero":
        task_body["status"]["index"] = 0
    elif mutation == "task-index-present-different":
        task_body["status"]["index"] = 1
    elif mutation == "task-retried-present-zero":
        task_body["status"]["retried"] = 0
    elif mutation == "task-retried-present-different":
        task_body["status"]["retried"] = 1
    elif mutation == "task-exit-code-present-zero":
        task_body["status"]["lastAttemptResult"]["exitCode"] = 0
    elif mutation == "task-exit-code-present-different":
        task_body["status"]["lastAttemptResult"]["exitCode"] = 1
    elif mutation == "execution-image":
        execution_body["spec"]["template"]["spec"]["containers"][0]["image"] = "mutable:latest"
    elif mutation == "execution-environment":
        execution_body["spec"]["template"]["spec"]["containers"][0]["env"][0]["value"] = "2"
    _install_subprocess_responses(
        monkeypatch, [_json_raw(execution_body), _json_raw(task_rows)]
    )

    with pytest.raises(controller.T230PlatformReplacementControllerError):
        controller.SubprocessCloudSubmitter().observe_primary_terminal(
            execution_name=replacement.FAILED_EXECUTION,
            expected_environment=expected_environment,
        )


def test_production_cloud_adapter_validates_live_and_submitted_envelopes_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    flags_path = str(tmp_path / "flags.json")
    plan = controller.build_worker_launch_plan_v1(
        image_evidence_identity=EVIDENCE, flags_path=flags_path
    )
    intent_raw = b'{"intent":"production-adapter-fixture"}'
    intent_identity = _identity(replacement.REPLACEMENT_INTENT_URI, intent_raw)
    flags_envelope = controller.build_worker_execution_flags_v1(
        launch_plan=plan, replacement_intent_identity=intent_identity
    )
    submitted_body = _execution_body(
        execution_name=EXECUTION,
        args=deepcopy(flags_envelope["flags"]["--args"]),
        configured_environment=deepcopy(
            flags_envelope["flags"]["--update-env-vars"]
        ),
        terminal=False,
    )
    calls = _install_subprocess_responses(
        monkeypatch,
        [_json_raw(_job_body()), (EXECUTION + "\n").encode(), _json_raw(submitted_body)],
    )
    cloud = controller.SubprocessCloudSubmitter()

    live = controller.validate_live_reused_job_projection_v1(
        cloud.observe_reused_job()
    )
    observation = cloud.submit(
        argv=plan["gcloud_argv"],
        execution_flags=flags_envelope["flags"],
    )
    submitted = controller.validate_submitted_execution_projection_v1(
        cloud.observe_submitted_execution(
            execution_name=EXECUTION,
            worker_launch_plan_sha256=plan["worker_launch_plan_sha256"],
            execution_flags_sha256=flags_envelope["flags_sha256"],
        ),
        execution_name=EXECUTION,
        launch_plan=plan,
        execution_flags=flags_envelope,
    )

    assert live["configured_environment"] == {}
    assert observation.stdout == (EXECUTION + "\n").encode()
    assert submitted["configured_environment"] == flags_envelope["flags"][
        "--update-env-vars"
    ]
    execute_calls = [row for row in calls if row[:4] == ["gcloud", "run", "jobs", "execute"]]
    assert len(execute_calls) == 1
    assert calls[0] == list(replacement.LIVE_JOB_DESCRIBE_ARGV)
    assert calls[2] == controller._submitted_execution_describe_argv(EXECUTION)
    assert (tmp_path / "flags.json").stat().st_mode & 0o777 == 0o600

    missing = deepcopy(submitted)
    del missing["worker_launch_plan_sha256"]
    extra = deepcopy(submitted)
    extra["coherently_rehashed_extra"] = False
    wrong_plan_hash = deepcopy(submitted)
    wrong_plan_hash["worker_launch_plan_sha256"] = "d" * 64
    wrong_flags_hash = deepcopy(submitted)
    wrong_flags_hash["execution_flags_sha256"] = "e" * 64
    for candidate in (missing, extra, wrong_plan_hash, wrong_flags_hash):
        with pytest.raises(controller.T230PlatformReplacementControllerError):
            controller.validate_submitted_execution_projection_v1(
                candidate,
                execution_name=EXECUTION,
                launch_plan=plan,
                execution_flags=flags_envelope,
            )


def test_production_live_and_submitted_drift_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    drifted_job = _job_body()
    drifted_job["spec"]["template"]["spec"]["template"]["spec"]["maxRetries"] = 1
    _install_subprocess_responses(monkeypatch, [_json_raw(drifted_job)])
    with pytest.raises(controller.T230PlatformReplacementControllerError):
        controller.validate_live_reused_job_projection_v1(
            controller.SubprocessCloudSubmitter().observe_reused_job()
        )

    flags_path = str(tmp_path / "drift-flags.json")
    plan = controller.build_worker_launch_plan_v1(
        image_evidence_identity=EVIDENCE, flags_path=flags_path
    )
    identity = _identity(replacement.REPLACEMENT_INTENT_URI, b"intent")
    flags = controller.build_worker_execution_flags_v1(
        launch_plan=plan, replacement_intent_identity=identity
    )
    drifted_execution = _execution_body(
        execution_name=EXECUTION,
        args=deepcopy(flags["flags"]["--args"]),
        configured_environment=deepcopy(flags["flags"]["--update-env-vars"]),
        terminal=False,
    )
    drifted_execution["spec"]["template"]["spec"]["containers"][0]["image"] = "mutable:latest"
    _install_subprocess_responses(
        monkeypatch,
        [(EXECUTION + "\n").encode(), _json_raw(drifted_execution)],
    )
    cloud = controller.SubprocessCloudSubmitter()
    cloud.submit(argv=plan["gcloud_argv"], execution_flags=flags["flags"])
    observed = cloud.observe_submitted_execution(
        execution_name=EXECUTION,
        worker_launch_plan_sha256=plan["worker_launch_plan_sha256"],
        execution_flags_sha256=flags["flags_sha256"],
    )
    with pytest.raises(controller.T230PlatformReplacementControllerError):
        controller.validate_submitted_execution_projection_v1(
            observed,
            execution_name=EXECUTION,
            launch_plan=plan,
            execution_flags=flags,
        )


@pytest.mark.parametrize(
    "environment_row",
    [
        {"name": "T230_PRED1_URI"},
        {"name": "T230_UNKNOWN_NAME_ONLY"},
        {
            "name": "T230_PRED1_URI",
            "valueFrom": {"secretKeyRef": {"name": "forbidden"}},
        },
        {"name": "T230_PRED1_URI", "unexpected": False},
    ],
)
def test_live_job_rejects_every_unconfigured_name_only_or_nonliteral_row(
    monkeypatch: pytest.MonkeyPatch,
    environment_row: dict[str, object],
) -> None:
    job_body = _job_body()
    rows = job_body["spec"]["template"]["spec"]["template"]["spec"][
        "containers"
    ][0]["env"]
    rows.append(deepcopy(environment_row))
    calls = _install_subprocess_responses(monkeypatch, [_json_raw(job_body)])

    with pytest.raises(controller.T230PlatformReplacementControllerError):
        controller.validate_live_reused_job_projection_v1(
            controller.SubprocessCloudSubmitter().observe_reused_job()
        )
    assert calls == [list(replacement.LIVE_JOB_DESCRIBE_ARGV)]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-expected-nonempty",
        "known-frozen-empty-name-only-extra",
        "unknown-name-only",
        "value-from",
        "extra-key",
    ],
)
def test_submitted_execution_rejects_name_only_and_nonliteral_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
) -> None:
    plan = controller.build_worker_launch_plan_v1(
        image_evidence_identity=EVIDENCE,
        flags_path=str(tmp_path / f"{mutation}-flags.json"),
    )
    identity = _identity(replacement.REPLACEMENT_INTENT_URI, b"intent")
    flags = controller.build_worker_execution_flags_v1(
        launch_plan=plan, replacement_intent_identity=identity
    )
    execution_body = _execution_body(
        execution_name=EXECUTION,
        args=deepcopy(flags["flags"]["--args"]),
        configured_environment=deepcopy(flags["flags"]["--update-env-vars"]),
        terminal=False,
    )
    rows = execution_body["spec"]["template"]["spec"]["containers"][0]["env"]
    if mutation == "missing-expected-nonempty":
        rows[0].pop("value")
    elif mutation == "known-frozen-empty-name-only-extra":
        rows.append({"name": "T230_PRED1_URI"})
    elif mutation == "unknown-name-only":
        rows.append({"name": "T230_UNKNOWN_NAME_ONLY"})
    elif mutation == "value-from":
        rows[0].pop("value")
        rows[0]["valueFrom"] = {"secretKeyRef": {"name": "forbidden"}}
    elif mutation == "extra-key":
        rows[0]["unexpected"] = False
    calls = _install_subprocess_responses(
        monkeypatch,
        [(EXECUTION + "\n").encode(), _json_raw(execution_body)],
    )
    cloud = controller.SubprocessCloudSubmitter()
    cloud.submit(argv=plan["gcloud_argv"], execution_flags=flags["flags"])

    with pytest.raises(controller.T230PlatformReplacementControllerError):
        observed = cloud.observe_submitted_execution(
            execution_name=EXECUTION,
            worker_launch_plan_sha256=plan["worker_launch_plan_sha256"],
            execution_flags_sha256=flags["flags_sha256"],
        )
        controller.validate_submitted_execution_projection_v1(
            observed,
            execution_name=EXECUTION,
            launch_plan=plan,
            execution_flags=flags,
        )
    execute_calls = [
        row for row in calls
        if row[:4] == ["gcloud", "run", "jobs", "execute"]
    ]
    assert len(execute_calls) == 1
    assert calls[-1] == controller._submitted_execution_describe_argv(EXECUTION)


class _Blob:
    def __init__(self, state: dict[str, object], generation: int | None) -> None:
        self._state = state
        self._requested_generation = generation

    @property
    def generation(self):
        return self._state.get("generation")

    def reload(self) -> None:
        if "raw" not in self._state:
            from google.api_core.exceptions import NotFound

            raise NotFound("fixture absent")

    def upload_from_string(self, raw: bytes, **_kwargs) -> None:
        if "raw" in self._state:
            from google.api_core.exceptions import PreconditionFailed

            raise PreconditionFailed("fixture collision")
        self._state["raw"] = raw
        self._state["generation"] = 7

    def download_as_bytes(self, **_kwargs) -> bytes:
        self._state["downloads"] = int(self._state.get("downloads", 0)) + 1
        return self._state["raw"]


class _Bucket:
    def __init__(self, objects: dict[str, dict[str, object]]) -> None:
        self._objects = objects

    def blob(self, name: str, generation: int | None = None) -> _Blob:
        return _Blob(self._objects.setdefault(name, {}), generation)


class _Client:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, object]] = {}

    def bucket(self, _name: str) -> _Bucket:
        return _Bucket(self.objects)


def test_production_gcs_backend_uses_exact_name_metadata_and_create_once() -> None:
    client = _Client()
    backend = controller.GCSPlatformReplacementBackend(
        client, controller.SubprocessCloudSubmitter()
    )
    uri = "gs://fixture-bucket/exact/object.json"

    assert backend.probe_known_uri_metadata(uri) is None
    assert client.objects["exact/object.json"].get("downloads", 0) == 0
    identity = backend.create(uri, b"{}")
    metadata = backend.probe_known_uri_metadata(uri)
    assert metadata["uri"] == uri and metadata["content_inspected"] is False
    assert backend.read(identity) == b"{}"
    with pytest.raises(transport.JournalObjectExists):
        backend.create(uri, b'{"unequal":true}')


def test_production_cli_wires_only_reviewed_live_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    captured: dict[str, object] = {}

    class DummyStorage:
        @staticmethod
        def Client(*, project: str):
            captured["project"] = project
            return object()

    monkeypatch.setenv(controller.ENABLE_ENV, "1")
    import google.cloud

    monkeypatch.setattr(google.cloud, "storage", DummyStorage, raising=False)
    monkeypatch.setattr(
        controller,
        "GCSPlatformReplacementBackend",
        lambda client, cloud: (client, cloud),
    )

    def fake_launch(*, backend, submitter):
        captured.update({
            "backend": backend,
            "submitter": submitter,
        })
        return {"disposition": "offline-cli-wiring-fixture"}

    monkeypatch.setattr(
        controller, "launch_replacement_worker_same_process_v1", fake_launch
    )
    assert controller.main(["launch-worker", "--execute"]) == 0
    assert captured["project"] == transport.PROJECT
    assert "offline-cli-wiring-fixture" in capsys.readouterr().out


def test_read_only_preflight_private_boundary_never_creates_or_submits() -> None:
    assert set(inspect.signature(
        controller.preflight_replacement_worker_real_artifacts_v1
    ).parameters) == {"backend", "submitter"}
    backend = MemoryBackend()
    cloud = FakeCloud()
    captured: dict[str, object] = {}

    def fake_builder(
        *, backend, replacement_worker_launch_plan,
        replacement_live_job_projection,
    ):
        captured["backend"] = backend
        captured["plan"] = replacement_worker_launch_plan
        captured["live"] = replacement_live_job_projection
        return {
            "replacement_worker_launch_plan_sha256": (
                replacement_worker_launch_plan["worker_launch_plan_sha256"]
            ),
            "live_job_projection_sha256": batch.canonical_sha256(
                replacement_live_job_projection
            ),
            "gcs_publication_count": 0,
            "cloud_submit_count": 0,
            "realized_outcomes_read": False,
            "result_or_effect_content_inspected": False,
            "review_lock_read": False,
            "intent_built": False,
            "intent_published": False,
            "passed": True,
            **_false_closure(),
        }

    receipt = controller._preflight_replacement_worker_real_artifacts_v1(
        backend=backend,
        submitter=cloud,
        evidence_resolver=lambda _backend: deepcopy(EVIDENCE),
        preflight_builder=fake_builder,
        preflight_validator=lambda value: value,
    )

    assert receipt["passed"] is True
    assert captured["backend"] is backend
    assert captured["plan"]["flags_path"] == (
        replacement.REAL_ARTIFACT_PREFLIGHT_FLAGS_PATH
    )
    assert cloud.job_observations == 1
    assert cloud.submission_calls == 0
    assert backend.create_calls == []


def test_preflight_cli_uses_fixed_tracked_output_and_blocks_second_invocation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    calls = 0

    class DummyStorage:
        @staticmethod
        def Client(*, project: str):
            assert project == transport.PROJECT
            return object()

    import google.cloud

    monkeypatch.setattr(google.cloud, "storage", DummyStorage, raising=False)
    monkeypatch.setattr(transport, "REPOSITORY_ROOT", tmp_path)
    (
        tmp_path
        / replacement.REAL_ARTIFACT_PREFLIGHT_RECEIPT_RELATIVE_PATH
    ).parent.mkdir(parents=True)
    monkeypatch.setattr(
        controller,
        "GCSPlatformReplacementBackend",
        lambda client, cloud: (client, cloud),
    )

    def fake_preflight(*, backend, submitter):
        nonlocal calls
        calls += 1
        assert backend[0] is not None
        assert isinstance(submitter, controller.SubprocessCloudSubmitter)
        return {"schema_version": "offline-preflight-cli-fixture/v1"}

    monkeypatch.setattr(
        controller, "preflight_replacement_worker_real_artifacts_v1",
        fake_preflight,
    )
    assert controller.main(["preflight-worker", "--preflight"]) == 0
    receipt_path = (
        tmp_path / replacement.REAL_ARTIFACT_PREFLIGHT_RECEIPT_RELATIVE_PATH
    )
    assert receipt_path.read_bytes() == (
        b'{"schema_version":"offline-preflight-cli-fixture/v1"}\n'
    )
    assert calls == 1
    assert "offline-preflight-cli-fixture" in capsys.readouterr().out
    with pytest.raises(controller.T230PlatformReplacementControllerError):
        controller.main(["preflight-worker", "--preflight"])
    assert calls == 1


def test_preflight_cli_rejects_dangling_fixed_output_symlink_before_cloud(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls = {"client": 0, "preflight": 0}
    receipt_path = (
        tmp_path / replacement.REAL_ARTIFACT_PREFLIGHT_RECEIPT_RELATIVE_PATH
    )
    receipt_path.parent.mkdir(parents=True)
    dangling_target = tmp_path / "outside" / "unexpected-preflight.json"
    receipt_path.symlink_to(dangling_target)

    class DummyStorage:
        @staticmethod
        def Client(*, project: str):
            calls["client"] += 1
            return object()

    import google.cloud

    monkeypatch.setattr(google.cloud, "storage", DummyStorage, raising=False)
    monkeypatch.setattr(transport, "REPOSITORY_ROOT", tmp_path)

    def fake_preflight(*, backend, submitter):
        calls["preflight"] += 1
        return {"unexpected": True}

    monkeypatch.setattr(
        controller, "preflight_replacement_worker_real_artifacts_v1",
        fake_preflight,
    )
    with pytest.raises(
        controller.T230PlatformReplacementControllerError,
        match="preflight receipt already exists",
    ):
        controller.main(["preflight-worker", "--preflight"])

    assert calls == {"client": 0, "preflight": 0}
    assert receipt_path.is_symlink()
    assert not dangling_target.exists()
