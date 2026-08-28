from __future__ import annotations

from hashlib import sha256
import json
import sys
from time import monotonic

import pytest

from scripts import (
    run_corpus_r6_current_bank_crossed_screen_task_dispatcher_v1 as dispatcher,
)


def _identity(uri: str, raw: bytes, *, generation: int = 7) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class _FixedDeadline:
    @staticmethod
    def remaining_seconds() -> float:
        return 123.0


def test_dispatcher_kernel_command_is_fixed_image_authority() -> None:
    command = dispatcher.canonical_dispatcher_command_v1()
    assert command == [
        "/usr/local/bin/python3.11",
        "-I",
        "/app/scripts/run_corpus_r6_current_bank_crossed_screen_task_dispatcher_v1.py",
    ]
    raw = b"\0".join(token.encode("utf-8") for token in command) + b"\0"
    assert dispatcher.kernel_observed_dispatcher_command_v1(raw) == command
    with pytest.raises(
        dispatcher.RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error,
        match="canonical entrypoint",
    ):
        dispatcher.validate_preclient_invocation_v1(
            observed_command=[sys.executable, __file__],
            environ={},
            raw_stdin=b"",
        )


def test_preclient_runtime_retains_exact_selected_kernel_environment() -> None:
    manifest_identity = _identity(
        (
            f"gs://{dispatcher.FIXED_BUCKET}/research/"
            "corpus-r6-current-bank-crossed-screens/fixture/"
            "authorities/task-manifests/00-projection.json"
        ),
        b"manifest",
    )
    raw_identity = json.dumps(
        manifest_identity, sort_keys=True, separators=(",", ":")
    )
    environment = {
        dispatcher.ENABLE_ENV: "1",
        dispatcher.task_manifest.DISPATCH_MANIFEST_IDENTITY_ENV: raw_identity,
        dispatcher.task_manifest.DISPATCH_RESUME_AUTHORITY_IDENTITY_ENV: (
            dispatcher.task_manifest.ABSENT_RESUME_AUTHORITY_ENV_VALUE
        ),
        "GOOGLE_CLOUD_PROJECT": dispatcher.task_manifest.FIXED_GCP_PROJECT,
        "CODE_SHA": "a" * 40,
        "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "b" * 64,
        "CLOUD_RUN_JOB": "fixture-job",
        "CLOUD_RUN_EXECUTION": "fixture-execution",
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_COUNT": "1",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
    }
    runtime = dispatcher.validate_preclient_invocation_v1(
        observed_command=dispatcher.canonical_dispatcher_command_v1(),
        environ=environment,
        raw_stdin=b"",
    )
    assert runtime["dispatcher_selected_environment"] == environment
    assert runtime["observed_dispatcher_command"] == (
        dispatcher.canonical_dispatcher_command_v1()
    )
    drifted = dict(environment)
    drifted["CLOUD_RUN_TASK_ATTEMPT"] = "1"
    with pytest.raises(
        dispatcher.RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error,
        match="index/count/attempt",
    ):
        dispatcher.validate_preclient_invocation_v1(
            observed_command=dispatcher.canonical_dispatcher_command_v1(),
            environ=drifted,
            raw_stdin=b"",
        )
    loader_redirect = dict(environment)
    loader_redirect["LD_AUDIT"] = "/tmp/forbidden.so"
    with pytest.raises(
        dispatcher.RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error,
        match="redirect is forbidden",
    ):
        dispatcher.validate_preclient_invocation_v1(
            observed_command=dispatcher.canonical_dispatcher_command_v1(),
            environ=loader_redirect,
            raw_stdin=b"",
        )


def test_child_stdin_backpressure_is_inside_shared_wall_deadline() -> None:
    started = monotonic()
    result = dispatcher._run_child_bounded_v1(
        command=[
            sys.executable,
            "-c",
            "import time; time.sleep(30)",
        ],
        input_bytes=b"x" * 2_000_000,
        environment={},
        stdout_ceiling=1_024,
        stderr_ceiling=1_024,
        timeout_seconds=1,
    )
    elapsed = monotonic() - started
    assert result["timed_out"] is True
    assert result["exit_code"] == 255
    assert elapsed < 5


def test_child_writer_delivers_complete_request_without_extra_copy_contract() -> None:
    request = b"request-body" * 80_000
    result = dispatcher._run_child_bounded_v1(
        command=[
            sys.executable,
            "-c",
            (
                "import sys; data=sys.stdin.buffer.read(); "
                "sys.stdout.buffer.write(str(len(data)).encode())"
            ),
        ],
        input_bytes=request,
        environment={},
        stdout_ceiling=1_024,
        stderr_ceiling=1_024,
        timeout_seconds=5,
    )
    assert result == {
        "exit_code": 0,
        "stdout": str(len(request)).encode("ascii"),
        "stderr": b"",
        "timed_out": False,
        "stdout_overflow": False,
        "stderr_overflow": False,
        "elapsed_milliseconds": result["elapsed_milliseconds"],
    }


def test_exact_transport_range_caps_at_expected_bytes_plus_one() -> None:
    raw = b'"bounded-authority"'
    calls: list[dict[str, object]] = []

    class Blob:
        def download_as_bytes(self, **kwargs: object) -> bytes:
            calls.append(dict(kwargs))
            return raw

    class Bucket:
        @staticmethod
        def blob(_name: str, *, generation: int) -> Blob:
            assert generation == 7
            return Blob()

    class Client:
        @staticmethod
        def bucket(_name: str) -> Bucket:
            return Bucket()

    transport = object.__new__(dispatcher.GCSExactReadTransportV1)
    transport._client = Client()
    transport._wall_deadline = _FixedDeadline()
    transport._base_retry = None
    transport._read_count = 0
    transport._proof_count = 0
    transport._write_count = 0
    identity = _identity(
        f"gs://{dispatcher.FIXED_BUCKET}/fixture/bounded.json", raw
    )
    assert transport.read_exact(identity) == raw
    assert calls == [{
        "start": 0,
        "end": len(raw),
        "if_generation_match": 7,
        "timeout": 123.0,
        "retry": None,
    }]

    class OverlongBlob(Blob):
        def download_as_bytes(self, **kwargs: object) -> bytes:
            calls.append(dict(kwargs))
            return raw + b"x"

    class OverlongBucket(Bucket):
        @staticmethod
        def blob(_name: str, *, generation: int) -> OverlongBlob:
            assert generation == 7
            return OverlongBlob()

    class OverlongClient(Client):
        @staticmethod
        def bucket(_name: str) -> OverlongBucket:
            return OverlongBucket()

    transport._client = OverlongClient()
    with pytest.raises(
        dispatcher.RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error,
        match="body differs",
    ):
        transport.read_exact(identity)


def test_exact_transport_streams_opaque_identity_without_retaining_body() -> None:
    raw = b"x" * 2_000_000
    calls: list[dict[str, object]] = []

    class Blob:
        def __init__(self, body: bytes) -> None:
            self.body = body

        def download_to_file(self, sink: object, **kwargs: object) -> None:
            calls.append(dict(kwargs))
            for start in range(0, len(self.body), 65_536):
                sink.write(self.body[start:start + 65_536])

    class Bucket:
        def __init__(self, body: bytes) -> None:
            self.body = body

        def blob(self, _name: str, *, generation: int) -> Blob:
            assert generation == 7
            return Blob(self.body)

    class Client:
        def __init__(self, body: bytes) -> None:
            self.body = body

        def bucket(self, _name: str) -> Bucket:
            return Bucket(self.body)

    transport = object.__new__(dispatcher.GCSExactReadTransportV1)
    transport._client = Client(raw)
    transport._wall_deadline = _FixedDeadline()
    transport._base_retry = None
    transport._read_count = 0
    transport._proof_count = 0
    transport._write_count = 0
    identity = _identity(
        f"gs://{dispatcher.FIXED_BUCKET}/fixture/opaque.bin", raw
    )
    assert transport.prove_exact_identity(identity) == identity
    assert calls == [{
        "start": 0,
        "end": len(raw),
        "raw_download": True,
        "if_generation_match": 7,
        "checksum": None,
        "single_shot_download": False,
        "timeout": 123.0,
        "retry": None,
    }]

    transport._client = Client(raw + b"y")
    with pytest.raises(
        dispatcher.RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error,
        match="proof differs",
    ):
        transport.prove_exact_identity(identity)


def test_end_to_end_deadline_fails_closed_after_expiry() -> None:
    now = [10.0]
    deadline = dispatcher.EndToEndWallDeadlineV1(
        2.0, clock=lambda: now[0]
    )
    assert deadline.remaining_seconds() == 2.0
    now[0] = 12.0
    with pytest.raises(
        dispatcher.RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error,
        match="end-to-end wall deadline",
    ):
        deadline.remaining_seconds()


def test_failure_diagnostic_is_bounded_redacted_and_non_authoritative() -> None:
    stderr = (
        b"Traceback (most recent call last):\n"
        b"credential=do-not-log-this\n"
        b"FixtureError: projection matrix is absent token=also-secret\n"
    )
    result = {
        "exit_code": 17,
        "stdout": b"science-output-is-never-excerpted",
        "stderr": stderr,
        "timed_out": False,
        "stdout_overflow": False,
        "stderr_overflow": False,
        "elapsed_milliseconds": 12,
    }
    raw = dispatcher._failure_diagnostic_v1(
        result, terminalization_error=None
    ).encode("utf-8")
    diagnostic = json.loads(raw)

    assert len(raw) <= dispatcher.MAXIMUM_FAILURE_DIAGNOSTIC_BYTES
    assert diagnostic["channel"] == "non-authoritative-dispatcher-stderr"
    assert diagnostic["classification"] == "child-nonzero-exit"
    assert diagnostic["child_exit_code"] == 17
    assert diagnostic["child_stderr_bytes"] == len(stderr)
    assert diagnostic["child_stderr_sha256"] == sha256(stderr).hexdigest()
    assert "FixtureError: projection matrix is absent" in diagnostic[
        "sanitized_stderr_excerpt"
    ]
    assert "do-not-log-this" not in raw.decode("utf-8")
    assert "also-secret" not in raw.decode("utf-8")
    assert "science-output-is-never-excerpted" not in raw.decode("utf-8")
    assert diagnostic[
        "raw_child_streams_embedded_in_science_authority"
    ] is False

    contract_rejection = json.loads(dispatcher._failure_diagnostic_v1(
        result,
        terminalization_error=ValueError("password: hidden contract mismatch"),
    ))
    assert contract_rejection["classification"] == (
        "child-terminal-contract-rejected"
    )
    assert contract_rejection["terminalization_error_type"] == "ValueError"
    assert "hidden" not in contract_rejection["terminalization_error"]
