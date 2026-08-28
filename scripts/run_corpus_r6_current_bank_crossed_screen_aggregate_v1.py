#!/usr/bin/env python3
"""Run one fixed R6 deterministic publisher.

Usage is one of::

    ...aggregate_v1.py publish-nomination < request.json
    ...aggregate_v1.py publish-aggregate-finalists < request.json
    ...aggregate_v1.py publish-terminal-root < request.json

The canonical request, execution gate, command, observed runtime, and redirect
environment are validated before the fixed-project cloud client is created.
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
    corpus_r6_current_bank_crossed_screen_aggregate_v1 as publisher,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as task_manifest,
)


ENABLE_ENV: Final = "R6_CURRENT_BANK_AGGREGATE_PUBLICATION_ENABLED"
MAXIMUM_REQUEST_BYTES: Final = 512_000
MAXIMUM_STDOUT_BYTES: Final = 4_000_000
MAXIMUM_PROCESS_COMMAND_BYTES: Final = 4_096
FIXED_BUCKET: Final = "nfl-predictions-503414-corpus-retrieval"


class RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(RuntimeError):
    """The guarded deterministic-publisher CLI failed closed."""


def _read_stdin_bounded_v1() -> bytes:
    raw = sys.stdin.buffer.read(MAXIMUM_REQUEST_BYTES + 1)
    if len(raw) > MAXIMUM_REQUEST_BYTES or sys.stdin.buffer.read(1):
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "publisher request exceeds its byte ceiling"
        )
    return raw


def observed_process_command_v1(raw_cmdline: bytes | None = None) -> list[str]:
    """Read one bounded canonical command from the kernel process record."""
    try:
        if raw_cmdline is None:
            with Path("/proc/self/cmdline").open("rb") as command_stream:
                raw = command_stream.read(MAXIMUM_PROCESS_COMMAND_BYTES + 1)
                trailing = command_stream.read(1)
            if len(raw) > MAXIMUM_PROCESS_COMMAND_BYTES or trailing:
                raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                    "kernel process command exceeds byte ceiling"
                )
        else:
            raw = raw_cmdline
    except OSError as exc:
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "kernel process command is unavailable"
        ) from exc
    if (
        type(raw) is not bytes
        or not raw
        or len(raw) > MAXIMUM_PROCESS_COMMAND_BYTES
        or not raw.endswith(b"\0")
    ):
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "kernel process command differs"
        )
    encoded = raw[:-1].split(b"\0")
    if len(encoded) != 3 or any(not field for field in encoded):
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "kernel process command shape differs"
        )
    try:
        observed = [field.decode("utf-8", errors="strict") for field in encoded]
    except UnicodeDecodeError as exc:
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "kernel process command is not UTF-8"
        ) from exc
    retained = [
        str(Path(observed[0]).resolve()),
        str(Path(observed[1]).resolve()),
        observed[2],
    ]
    if (
        retained[2] not in publisher.PUBLISHER_MODES
        or retained != publisher.canonical_publisher_command_v1(retained[2])
    ):
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "kernel process command is not the canonical publisher entrypoint"
        )
    return retained


def bind_task_evidence_to_publisher_envelope_v1(
    envelope_value: Mapping[str, object],
    binding_evidence_value: Mapping[str, object],
    *,
    request: Mapping[str, object],
    raw_request: bytes,
) -> dict[str, object]:
    """Self-hash the exact controller task binding into one publisher result."""
    envelope = dict(envelope_value)
    if "task_binding_evidence" in envelope:
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "publisher envelope already contains task binding evidence"
        )
    prior_hash = envelope.pop("publisher_envelope_sha256", None)
    if (
        type(prior_hash) is not str
        or prior_hash != contract.canonical_sha256_v1(envelope)
    ):
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "unbound publisher envelope self-hash differs"
        )
    evidence = dict(binding_evidence_value)
    expected_evidence_fields = {
        "schema_version", "contract_id", "manifest_identity",
        "task_manifest_sha256", "layer_id", "phase", "process_role",
        "task_index", "source_ordinal", "process_ordinal",
        "task_binding_sha256", "request_sha256", "request_bytes",
        "expected_outputs_sha256", "child_command_sha256",
        "manifest_generation_exact_reopen_required",
        "caller_request_or_command_accepted", "policy",
        "child_task_binding_evidence_sha256",
    }
    expected_layer = {
        publisher.PUBLISH_NOMINATION: "nomination",
        publisher.PUBLISH_AGGREGATE_FINALISTS: "aggregate-finalists",
        publisher.PUBLISH_TERMINAL_ROOT: "terminal-root",
    }.get(request.get("mode"))
    hash_fields = (
        "task_manifest_sha256", "task_binding_sha256", "request_sha256",
        "expected_outputs_sha256", "child_command_sha256",
        "child_task_binding_evidence_sha256",
    )
    if (
        set(evidence) != expected_evidence_fields
        or evidence.get("child_task_binding_evidence_sha256")
        != contract.canonical_sha256_v1({
            key: value for key, value in evidence.items()
            if key != "child_task_binding_evidence_sha256"
        })
        or evidence.get("schema_version")
        != task_manifest.CHILD_TASK_BINDING_EVIDENCE_SCHEMA
        or evidence.get("contract_id") != contract.CONTRACT_ID
        or any(
            type(evidence.get(field)) is not str
            or len(str(evidence.get(field))) != 64
            or any(character not in "0123456789abcdef"
                   for character in str(evidence.get(field)))
            for field in hash_fields
        )
        or contract._safe_object_identity(
            evidence.get("manifest_identity"),
            label="publisher binding manifest identity",
        ) != evidence.get("manifest_identity")
        or evidence.get("layer_id") != expected_layer
        or evidence.get("request_sha256") != sha256(raw_request).hexdigest()
        or evidence.get("request_bytes") != len(raw_request)
        or envelope.get("publisher_request_sha256")
        != request.get("publisher_request_sha256")
        or evidence.get("phase")
        != {
            publisher.PUBLISH_NOMINATION: contract.BROAD_SCREEN_PHASE,
            publisher.PUBLISH_AGGREGATE_FINALISTS: contract.CONFIRMATION_PHASE,
            publisher.PUBLISH_TERMINAL_ROOT: "terminal",
        }.get(request.get("mode"))
        or evidence.get("process_role") != request.get("process_role")
        or evidence.get("task_index") != 0
        or evidence.get("source_ordinal") is not None
        or evidence.get("process_ordinal") != 0
        or evidence.get("manifest_generation_exact_reopen_required") is not True
        or evidence.get("caller_request_or_command_accepted") is not False
        or evidence.get("policy") != contract.POLICY_CLAIMS
        or envelope.get("mode") != request.get("mode")
        or envelope.get("process_role") != request.get("process_role")
        or envelope.get("process_ordinal") != 0
    ):
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "publisher task binding evidence differs from its result envelope"
        )
    envelope["task_binding_evidence"] = evidence
    envelope["publisher_envelope_sha256"] = contract.canonical_sha256_v1(
        envelope
    )
    return envelope


def reopen_controller_task_after_client_v1(
    *,
    parsed_binding: Mapping[str, object],
    environ: Mapping[str, str],
    raw_request: bytes,
    observed_command: list[str],
    read_exact,
    expected_process_role: str,
    expected_phase: str,
    expected_process_ordinal: int,
) -> dict[str, object]:
    """Validate the selected task before any non-manifest authority read."""
    if type(expected_process_ordinal) is not int or expected_process_ordinal != 0:
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "controller publisher process ordinal differs"
        )
    manifest_identity = contract._safe_object_identity(
        parsed_binding.get("manifest_identity"),
        label="controller publisher task manifest identity",
    )
    if int(manifest_identity["bytes"]) > task_manifest.MAXIMUM_MANIFEST_BYTES:
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "controller publisher task manifest exceeds byte ceiling"
        )
    manifest_raw = read_exact(manifest_identity)
    manifest = task_manifest.strict_json_v1(
        manifest_raw, label="controller publisher task manifest"
    )
    immediate = task_manifest.validate_child_task_binding_v1(
        manifest,
        manifest_identity=manifest_identity,
        environ=environ,
        raw_request=raw_request,
        observed_command=observed_command,
        expected_process_role=expected_process_role,
        expected_phase=expected_phase,
        expected_process_ordinal=expected_process_ordinal,
    )
    cached_manifest_replays = 0

    def read_with_manifest_cache(identity_value: Mapping[str, object]) -> bytes:
        nonlocal cached_manifest_replays
        retained = contract._safe_object_identity(
            identity_value, label="controller publisher authority identity"
        )
        if retained == manifest_identity:
            cached_manifest_replays += 1
            if cached_manifest_replays != 1:
                raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                    "controller task manifest cache replay count differs"
                )
            return manifest_raw
        return read_exact(retained)

    replayed = task_manifest.reopen_child_task_binding_v1(
        environ=environ,
        raw_request=raw_request,
        observed_command=observed_command,
        read_exact=read_with_manifest_cache,
        expected_process_role=expected_process_role,
        expected_phase=expected_phase,
        expected_process_ordinal=expected_process_ordinal,
    )
    if (
        cached_manifest_replays != 1
        or contract.canonical_json_bytes_v1(replayed)
        != contract.canonical_json_bytes_v1(immediate)
    ):
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "controller task binding authority replay differs"
        )
    return immediate


def validate_preclient_invocation_v1(
    *, argv: list[str], environ: Mapping[str, str], raw_request: bytes,
    pid: int, parent_pid: int,
) -> tuple[dict[str, object], dict[str, object]]:
    """Reject semantic, gate, runtime, command, and redirect faults first."""
    if len(argv) != 3 or argv[2] not in publisher.PUBLISHER_MODES:
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "publisher command mode differs"
        )
    mode = argv[2]
    if argv != publisher.canonical_publisher_command_v1(mode):
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "publisher command differs from the canonical entrypoint"
        )
    if environ.get(ENABLE_ENV) != "1":
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            f"publisher publication requires exact {ENABLE_ENV}=1"
        )
    request = publisher.validate_publisher_request_v1(
        publisher.strict_json_v1(raw_request, label="stdin publisher request")
    )
    if request["mode"] != mode:
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "publisher request mode differs from command"
        )
    runtime = publisher.derive_observed_runtime_evidence_v1(
        mode=mode,
        environ=environ,
        argv=argv,
        pid=pid,
        parent_pid=parent_pid,
    )
    return request, runtime


class GCSExactCreateOnceTransportV1:
    """Generation-exact GET plus strict create/resume, with no resolver API.

    No list, reload, metadata lookup, or current-generation method is exposed.
    A collision can resume only through the exact prior identity already in
    the canonical request; both new-create and resume return only after a
    generation-pinned byte comparison.
    """

    def __init__(self) -> None:
        try:
            from google.cloud import storage
        except Exception as exc:  # pragma: no cover - cloud-only dependency
            raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                "google-cloud-storage is required"
            ) from exc
        self._client = storage.Client(
            project=publisher.FIXED_GCP_PROJECT,
            client_options={"api_endpoint": publisher.FIXED_STORAGE_ENDPOINT},
        )

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if not uri.startswith("gs://"):
            raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                "publisher object URI must use gs://"
            )
        bucket, marker, name = uri[5:].partition("/")
        if (
            not marker
            or bucket != FIXED_BUCKET
            or not name
            or name.endswith("/")
            or "//" in name
        ):
            raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                "publisher object URI differs from the fixed research bucket"
            )
        return bucket, name

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        identity = contract._safe_object_identity(
            identity_value, label="publisher GCS exact read"
        )
        if int(identity["bytes"]) > (
            publisher.MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES
        ):
            raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                "publisher exact read exceeds process body ceiling"
            )
        bucket, name = self._parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        blob = self._client.bucket(bucket).blob(name, generation=generation)
        try:
            # GCS range ends are inclusive.  Request exactly expected+1 bytes:
            # an exact object returns its full expected body, while a larger
            # generation returns one sentinel byte and fails the size bind.
            raw = blob.download_as_bytes(
                start=0, end=int(identity["bytes"]),
                if_generation_match=generation, retry=None,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                "publisher generation-pinned GET failed"
            ) from exc
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                "publisher exact-read body differs"
            )
        return raw

    def publish_create_once(
        self, uri: str, raw: bytes,
        prior_identity: Mapping[str, object] | None,
    ) -> dict[str, object]:
        if type(raw) is not bytes:
            raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                "publisher publication must be bytes"
            )
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
                retry=None,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ not in {"Conflict", "PreconditionFailed"}:
                raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                    "strict create-once publisher publication failed"
                ) from exc
            if prior_identity is None:
                raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                    "publisher collision lacks a recorded exact identity"
                ) from exc
            prior = contract._safe_object_identity(
                prior_identity, label="recorded prior publisher identity"
            )
            if (
                prior["uri"] != uri
                or prior["bytes"] != len(raw)
                or prior["sha256"] != sha256(raw).hexdigest()
                or self.read_exact(prior) != raw
            ):
                raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                    "recorded publisher collision body differs"
                ) from exc
            return prior
        generation = str(blob.generation or "")
        if not generation.isdecimal() or generation.startswith("0"):
            raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                "created publisher generation is unavailable"
            )
        created = {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if self.read_exact(created) != raw:
            raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                "created publisher exact reopen differs"
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
        expected_layer = {
            publisher.PUBLISH_NOMINATION: "nomination",
            publisher.PUBLISH_AGGREGATE_FINALISTS: "aggregate-finalists",
            publisher.PUBLISH_TERMINAL_ROOT: "terminal-root",
        }[str(request["mode"])]
        if (
            parsed_binding["layer_id"] != expected_layer
            or parsed_binding["task_index"] != 0
        ):
            raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                "preclient publisher task layer/index binding differs"
            )
        observed_child_command_sha256 = contract.canonical_sha256_v1({
            "command": argv,
            "entrypoint_sha256": sha256(Path(argv[1]).read_bytes()).hexdigest(),
        })
        if (
            parsed_binding["request_sha256"] != sha256(raw).hexdigest()
            or parsed_binding["child_command_sha256"]
            != observed_child_command_sha256
        ):
            raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                "preclient publisher request/command scalar binding differs"
            )
        if publisher._require_address_space_limit_v1() != (
            publisher.MAXIMUM_PUBLISHER_ADDRESS_SPACE_BYTES
        ):
            raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                "publisher address-space precharge differs"
            )
        transport = GCSExactCreateOnceTransportV1()
        binding_evidence = reopen_controller_task_after_client_v1(
            parsed_binding=parsed_binding,
            environ=os.environ,
            raw_request=raw,
            observed_command=argv,
            read_exact=transport.read_exact,
            expected_process_role=str(request["process_role"]),
            expected_phase={
                publisher.PUBLISH_NOMINATION: contract.BROAD_SCREEN_PHASE,
                publisher.PUBLISH_AGGREGATE_FINALISTS:
                    contract.CONFIRMATION_PHASE,
                publisher.PUBLISH_TERMINAL_ROOT: "terminal",
            }[str(request["mode"])],
            expected_process_ordinal=0,
        )
        envelope = publisher.run_publisher_v1(
            request,
            observed_runtime=runtime,
            read_exact=transport.read_exact,
            publish_create_once=transport.publish_create_once,
        )
        envelope = bind_task_evidence_to_publisher_envelope_v1(
            envelope,
            binding_evidence,
            request=request,
            raw_request=raw,
        )
        output = contract.canonical_json_bytes_v1(envelope) + b"\n"
        if len(output) > MAXIMUM_STDOUT_BYTES:
            raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
                "publisher envelope exceeds its stdout byte ceiling"
            )
    except Exception as exc:
        raise RunCorpusR6CurrentBankCrossedScreenAggregateV1Error(
            "current-bank deterministic publication failed"
        ) from exc
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
