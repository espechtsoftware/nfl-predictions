#!/usr/bin/env python3
"""Run one immutable R6 held-out slate evaluation.

Usage: ``...evaluation_v1.py evaluate-slate < request.json``.  The request is
validated, the execution/runtime gate is checked, and redirect environments
are rejected before a cloud client can be constructed.
"""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import sys
from typing import Final, Mapping

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_evaluation_v1 as evaluator,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as task_manifest,
)


ENABLE_ENV: Final = "R6_CURRENT_BANK_EVALUATION_PUBLICATION_ENABLED"
MAXIMUM_REQUEST_BYTES: Final = 128_000
MAXIMUM_PROCESS_COMMAND_BYTES: Final = 4_096


class RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(RuntimeError):
    """The guarded held-out evaluator CLI failed closed."""


def _read_stdin_bounded_v1() -> bytes:
    raw = sys.stdin.buffer.read(MAXIMUM_REQUEST_BYTES + 1)
    if len(raw) > MAXIMUM_REQUEST_BYTES or sys.stdin.buffer.read(1):
        raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            "evaluator request exceeds its byte ceiling"
        )
    return raw


def observed_process_command_v1(raw_cmdline: bytes | None = None) -> list[str]:
    """Read the kernel-observed command; never synthesize it from this code."""
    try:
        if raw_cmdline is None:
            with Path("/proc/self/cmdline").open("rb") as handle:
                raw = handle.read(MAXIMUM_PROCESS_COMMAND_BYTES + 1)
                trailing = handle.read(1)
        else:
            raw = raw_cmdline
            trailing = b""
    except OSError as exc:
        raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            "kernel process command is unavailable"
        ) from exc
    if (
        type(raw) is not bytes
        or not raw
        or len(raw) > MAXIMUM_PROCESS_COMMAND_BYTES
        or trailing
        or not raw.endswith(b"\0")
    ):
        raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            "kernel process command differs"
        )
    encoded = raw[:-1].split(b"\0")
    if len(encoded) != 3 or any(not field for field in encoded):
        raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            "kernel process command shape differs"
        )
    try:
        observed = [field.decode("utf-8", errors="strict") for field in encoded]
    except UnicodeDecodeError as exc:
        raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            "kernel process command is not UTF-8"
        ) from exc
    retained = [
        str(Path(observed[0]).resolve()),
        str(Path(observed[1]).resolve()),
        observed[2],
    ]
    if retained != evaluator.canonical_evaluator_command_v1():
        raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            "kernel process command is not the canonical evaluator entrypoint"
        )
    return retained


def framed_envelope_bytes_v1(envelope: Mapping[str, object]) -> bytes:
    """Frame one JSON line while bounding every byte written to stdout."""
    envelope_raw = contract.canonical_json_bytes_v1(envelope)
    framed = envelope_raw + b"\n"
    if len(framed) > evaluator.MAXIMUM_ENVELOPE_BYTES:
        raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            "evaluator envelope exceeds its stdout byte ceiling"
        )
    return framed


def bind_task_evidence_to_envelope_v1(
    envelope_value: Mapping[str, object],
    binding_evidence_value: Mapping[str, object],
    request_value: Mapping[str, object],
) -> dict[str, object]:
    """Bind dispatcher authority into the evaluator's self-hashed envelope."""
    envelope = dict(envelope_value)
    request = evaluator.validate_evaluator_request_v1(request_value)
    if "task_binding_evidence" in envelope:
        raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            "evaluator envelope already contains task binding evidence"
        )
    prior_hash = envelope.pop("evaluator_envelope_sha256", None)
    if (
        type(prior_hash) is not str
        or prior_hash != contract.canonical_sha256_v1(envelope)
    ):
        raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            "unbound evaluator envelope self-hash differs"
        )
    evidence = dict(binding_evidence_value)
    evidence_fields = {
        "schema_version", "contract_id", "manifest_identity",
        "task_manifest_sha256", "layer_id", "phase", "process_role",
        "task_index", "source_ordinal", "process_ordinal",
        "task_binding_sha256", "request_sha256", "request_bytes",
        "expected_outputs_sha256", "child_command_sha256",
        "manifest_generation_exact_reopen_required",
        "caller_request_or_command_accepted", "policy",
        "child_task_binding_evidence_sha256",
    }
    evidence_without_hash = dict(evidence)
    evidence_hash = evidence_without_hash.pop(
        "child_task_binding_evidence_sha256", None
    )
    expected_layer = (
        "broad-evaluation-result"
        if request["phase"] == contract.BROAD_SCREEN_PHASE
        else "confirmation-evaluation-result"
    )
    expected_role = (
        "broad-evaluator"
        if request["phase"] == contract.BROAD_SCREEN_PHASE
        else "confirmation-evaluator"
    )
    request_raw = contract.canonical_json_bytes_v1(request)
    if (
        set(evidence) != evidence_fields
        or evidence_hash != contract.canonical_sha256_v1(evidence_without_hash)
        or evidence.get("schema_version")
        != task_manifest.CHILD_TASK_BINDING_EVIDENCE_SCHEMA
        or evidence.get("contract_id") != contract.CONTRACT_ID
        or evidence.get("layer_id") != expected_layer
        or evidence.get("process_role") != expected_role
        or evidence.get("task_index") != request.get("source_ordinal")
        or evidence.get("request_sha256")
        != sha256(request_raw).hexdigest()
        or evidence.get("request_bytes") != len(request_raw)
        or envelope.get("evaluator_request_sha256")
        != request.get("evaluator_request_sha256")
        or evidence.get("phase") != envelope.get("phase")
        or request.get("phase") != envelope.get("phase")
        or evidence.get("source_ordinal") != envelope.get("source_ordinal")
        or request.get("source_ordinal") != envelope.get("source_ordinal")
        or evidence.get("process_ordinal") != envelope.get("process_ordinal")
        or request.get("process_ordinal") != envelope.get("process_ordinal")
        or evidence.get("manifest_generation_exact_reopen_required") is not True
        or evidence.get("caller_request_or_command_accepted") is not False
        or evidence.get("policy") != contract.POLICY_CLAIMS
    ):
        raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            "evaluator task binding evidence differs from its result envelope"
        )
    envelope["task_binding_evidence"] = evidence
    envelope["evaluator_envelope_sha256"] = contract.canonical_sha256_v1(
        envelope
    )
    return envelope


def validate_preclient_invocation_v1(
    *, argv: list[str], environ: Mapping[str, str], raw_request: bytes,
    pid: int, parent_pid: int,
) -> tuple[dict[str, object], dict[str, object]]:
    """Reject every request/runtime/gate error before cloud construction."""
    if argv != evaluator.canonical_evaluator_command_v1():
        raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            "evaluator command differs from the canonical entrypoint"
        )
    if environ.get(ENABLE_ENV) != "1":
        raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            f"evaluator publication requires exact {ENABLE_ENV}=1"
        )
    request = evaluator.validate_evaluator_request_v1(
        evaluator.strict_json_v1(raw_request, label="stdin evaluator request")
    )
    runtime = evaluator.derive_observed_runtime_evidence_v1(
        source_ordinal=int(request["source_ordinal"]),
        phase=str(request["phase"]),
        environ=environ,
        argv=argv,
        pid=pid,
        parent_pid=parent_pid,
    )
    return request, runtime


class GCSExactCreateOnceTransportV1:
    """Generation-pinned GET and strict create-if-absent publication.

    This type deliberately exposes no listing, metadata resolution, reload, or
    current-generation method.  A collision is recoverable only through an
    exact prior identity supplied in the canonical evaluator request.
    """

    def __init__(self) -> None:
        try:
            from google.cloud import storage
        except Exception as exc:  # pragma: no cover - cloud-only dependency
            raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
                "google-cloud-storage is required"
            ) from exc
        self._client = storage.Client(
            project=evaluator.FIXED_GCP_PROJECT,
            client_options={"api_endpoint": evaluator.FIXED_STORAGE_ENDPOINT},
        )

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if not uri.startswith("gs://"):
            raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
                "evaluator object URI must use gs://"
            )
        bucket, marker, name = uri[5:].partition("/")
        if not marker or not bucket or not name or name.endswith("/"):
            raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
                "evaluator object URI differs"
            )
        return bucket, name

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        identity = contract._safe_object_identity(
            identity_value, label="evaluator GCS exact read"
        )
        bucket, name = self._parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        blob = self._client.bucket(bucket).blob(name, generation=generation)
        try:
            raw = blob.download_as_bytes(if_generation_match=generation)
        except Exception as exc:  # pragma: no cover - cloud dependent
            raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
                "evaluator generation-pinned GET failed"
            ) from exc
        if len(raw) != identity["bytes"] or sha256(raw).hexdigest() != identity["sha256"]:
            raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
                "evaluator exact-read body differs"
            )
        return raw

    def publish_create_once(
        self, uri: str, raw: bytes,
        prior_identity: Mapping[str, object] | None,
    ) -> dict[str, object]:
        if type(raw) is not bytes:
            raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
                "evaluation publication must be bytes"
            )
        bucket, name = self._parts(uri)
        # Supplying a prior identity selects exact resume, never a new create.
        # A missing recorded generation therefore fails its pinned GET instead
        # of silently forking a replacement generation.
        if prior_identity is not None:
            prior = contract._safe_object_identity(
                prior_identity, label="recorded prior evaluation identity"
            )
            if prior["uri"] != uri or self.read_exact(prior) != raw:
                raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
                    "recorded evaluation resume body differs"
                )
            return prior
        blob = self._client.bucket(bucket).blob(name)
        try:
            blob.upload_from_string(
                raw, content_type="application/json", if_generation_match=0
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ not in {"Conflict", "PreconditionFailed"}:
                raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
                    "strict create-once evaluation publication failed"
                ) from exc
            raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
                "evaluation collision lacks a recorded exact identity"
            ) from exc
        generation = str(blob.generation or "")
        if not generation.isdecimal() or generation.startswith("0"):
            raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
                "created evaluation generation is unavailable"
            )
        created = {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if self.read_exact(created) != raw:
            raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
                "created evaluation exact reopen differs"
            )
        return created


def main() -> int:
    raw = _read_stdin_bounded_v1()
    try:
        parsed_binding = task_manifest.parse_child_task_binding_environment_v1(
            os.environ
        )
        argv = observed_process_command_v1()
        request, runtime = validate_preclient_invocation_v1(
            argv=argv,
            environ=os.environ,
            raw_request=raw,
            pid=os.getpid(),
            parent_pid=os.getppid(),
        )
        expected_layer = (
            "broad-evaluation-result"
            if request["phase"] == contract.BROAD_SCREEN_PHASE
            else "confirmation-evaluation-result"
        )
        if (
            parsed_binding["layer_id"] != expected_layer
            or parsed_binding["task_index"] != request["source_ordinal"]
            or parsed_binding["manifest_identity"]["bytes"]
            > task_manifest.MAXIMUM_MANIFEST_BYTES
            or parsed_binding["request_sha256"] != sha256(raw).hexdigest()
            or parsed_binding["child_command_sha256"]
            != contract.canonical_sha256_v1({
                "command": argv,
                "entrypoint_sha256": sha256(
                    Path(__file__).read_bytes()
                ).hexdigest(),
            })
        ):
            raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
                "preclient evaluator task layer/index binding differs"
            )
        transport = GCSExactCreateOnceTransportV1()
        binding_evidence = task_manifest.reopen_child_task_binding_v1(
            environ=os.environ,
            raw_request=raw,
            observed_command=argv,
            read_exact=transport.read_exact,
            expected_process_role=(
                "broad-evaluator"
                if request["phase"] == contract.BROAD_SCREEN_PHASE
                else "confirmation-evaluator"
            ),
            expected_phase=str(request["phase"]),
            expected_source_ordinal=int(request["source_ordinal"]),
            expected_process_ordinal=int(request["process_ordinal"]),
        )
        envelope = evaluator.run_evaluator_v1(
            request,
            observed_runtime=runtime,
            read_exact=transport.read_exact,
            publish_create_once=transport.publish_create_once,
        )
        envelope = bind_task_evidence_to_envelope_v1(
            envelope, binding_evidence, request
        )
    except Exception as exc:
        raise RunCorpusR6CurrentBankCrossedScreenEvaluationV1Error(
            "current-bank held-out evaluation failed"
        ) from exc
    sys.stdout.buffer.write(framed_envelope_bytes_v1(envelope))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
