#!/usr/bin/env python3
"""Publish the 54 sealed current-bank five-fold projection bundles."""

from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path
import sys
from typing import Any, Final, Mapping

from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_contract_v1 as contract
from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_projection_v1 as projection
from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_task_manifest_v1 as task_manifest


PROJECT: Final = "nfl-predictions-503414"
ENABLE_ENV: Final = "R6_CURRENT_BANK_PROJECTION_PUBLICATION_ENABLED"
FIXED_STORAGE_ENDPOINT: Final = "https://storage.googleapis.com"
FORBIDDEN_REDIRECT_ENV: Final = (
    "STORAGE_EMULATOR_HOST",
    "CLOUDSDK_API_ENDPOINT_OVERRIDES_STORAGE",
    "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
    "PYTHONHOME",
    "PYTHONPATH",
    "LD_PRELOAD",
    "R6_GCS_ENDPOINT",
    "R6_PROJECT_OVERRIDE",
    "R6_PROJECTION_COMMAND",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "GRPC_DEFAULT_SSL_ROOTS_FILE_PATH",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GOOGLE_API_USE_MTLS_ENDPOINT",
    "GOOGLE_API_USE_CLIENT_CERTIFICATE",
    "GCE_METADATA_HOST",
    "GCE_METADATA_ROOT",
    "GCE_METADATA_IP",
    "CLOUDSDK_CONFIG",
)
MAXIMUM_REQUEST_BYTES: Final = 512_000
MAXIMUM_PROCESS_COMMAND_BYTES: Final = 65_536
MAXIMUM_STDOUT_BYTES: Final = 4_000_000


class RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(RuntimeError):
    """The guarded projection publisher failed closed."""


def _object_identity_v1(value: object, *, label: str) -> dict[str, object]:
    return contract._safe_object_identity(value, label=label)


def _read_stdin_bounded_v1() -> bytes:
    raw = sys.stdin.buffer.read(MAXIMUM_REQUEST_BYTES + 1)
    if len(raw) > MAXIMUM_REQUEST_BYTES or sys.stdin.buffer.read(1):
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "projection task request exceeds its byte ceiling"
        )
    return raw


def observed_process_command_v1(
    raw_cmdline: bytes | None = None,
) -> list[str]:
    """Read the bounded kernel-observed command, including frozen arguments."""
    try:
        if raw_cmdline is None:
            with Path("/proc/self/cmdline").open("rb") as handle:
                raw = handle.read(MAXIMUM_PROCESS_COMMAND_BYTES + 1)
                trailing = handle.read(1)
        else:
            raw = raw_cmdline
            trailing = b""
    except OSError as exc:
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "kernel process command is unavailable"
        ) from exc
    if (
        type(raw) is not bytes
        or not raw
        or len(raw) > MAXIMUM_PROCESS_COMMAND_BYTES
        or trailing
        or not raw.endswith(b"\0")
    ):
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "kernel process command differs"
        )
    encoded = raw[:-1].split(b"\0")
    if len(encoded) < 2 or any(not field for field in encoded):
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "kernel process command shape differs"
        )
    try:
        observed = [field.decode("utf-8", errors="strict") for field in encoded]
    except UnicodeDecodeError as exc:
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "kernel process command is not UTF-8"
        ) from exc
    retained = [
        str(Path(observed[0]).resolve()),
        str(Path(observed[1]).resolve()),
        *observed[2:],
    ]
    if (
        retained[0] != str(Path(sys.executable).resolve())
        or retained[1] != str(Path(__file__).resolve())
    ):
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "kernel process entrypoint differs"
        )
    return retained


def _full_binding_evidence_v1(
    evidence_value: Mapping[str, object], *, raw_request: bytes,
) -> dict[str, object]:
    evidence = dict(evidence_value)
    fields = {
        "schema_version", "contract_id", "manifest_identity",
        "task_manifest_sha256", "layer_id", "phase", "process_role",
        "task_index", "source_ordinal", "process_ordinal",
        "task_binding_sha256", "request_sha256", "request_bytes",
        "expected_outputs_sha256", "child_command_sha256",
        "manifest_generation_exact_reopen_required",
        "caller_request_or_command_accepted", "policy",
        "child_task_binding_evidence_sha256",
    }
    without_hash = dict(evidence)
    digest = without_hash.pop("child_task_binding_evidence_sha256", None)
    if (
        set(evidence) != fields
        or digest != contract.canonical_sha256_v1(without_hash)
        or evidence.get("schema_version")
        != task_manifest.CHILD_TASK_BINDING_EVIDENCE_SCHEMA
        or evidence.get("contract_id") != contract.CONTRACT_ID
        or evidence.get("layer_id") != "projection"
        or evidence.get("phase") != "projection"
        or evidence.get("process_role") != "projection-publisher"
        or evidence.get("task_index") != 0
        or evidence.get("source_ordinal") is not None
        or evidence.get("process_ordinal") != 0
        or evidence.get("request_sha256") != sha256(raw_request).hexdigest()
        or evidence.get("request_bytes") != len(raw_request)
        or evidence.get("manifest_generation_exact_reopen_required") is not True
        or evidence.get("caller_request_or_command_accepted") is not False
        or evidence.get("policy") != contract.POLICY_CLAIMS
    ):
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "projection child task binding evidence differs"
        )
    return evidence


def _validated_projection_budget_execution_v1(
    value: Mapping[str, object], *, process_budget: Mapping[str, object],
    projection_identities: object,
) -> dict[str, object]:
    execution = dict(value)
    reads = process_budget.get("read_allowlist")
    writes = process_budget.get("write_allowlist")
    if (
        set(execution) != {
            "read_ledger", "read_ledger_sha256", "read_object_count",
            "write_ledger", "write_ledger_sha256", "write_object_count",
            "read_budget_exhausted", "write_budget_exhausted",
        }
        or not isinstance(reads, list)
        or len(reads) != 4 + contract.EXACT_STRUCTURAL_OBJECT_COUNT
        or not isinstance(writes, list)
        or len(writes) != contract.PANEL_SLATE_COUNT
        or not isinstance(projection_identities, list)
        or len(projection_identities) != contract.PANEL_SLATE_COUNT
    ):
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "projection budget execution shape differs"
        )
    core_reads = [*reads[:2], *reads[4:]]
    expected_read_ledger = [
        {
            "ordinal": index,
            "role": (
                str(row.get("role")) if index < 2
                else f"structural-{index - 2:03d}"
            ),
            "identity": row.get("identity"),
        }
        for index, row in enumerate(core_reads)
    ]
    expected_write_ledger = [
        {
            "ordinal": descriptor.get("ordinal"),
            "role": descriptor.get("role"),
            "uri": descriptor.get("uri"),
            "maximum_bytes": descriptor.get("max_bytes"),
            "publication_identity": projection_identities[index],
            "exact_generation_reopen_proved": True,
        }
        for index, descriptor in enumerate(writes)
    ]
    expected = {
        "read_ledger": expected_read_ledger,
        "read_ledger_sha256": contract.canonical_sha256_v1(
            expected_read_ledger
        ),
        "read_object_count": len(expected_read_ledger),
        "write_ledger": expected_write_ledger,
        "write_ledger_sha256": contract.canonical_sha256_v1(
            expected_write_ledger
        ),
        "write_object_count": len(expected_write_ledger),
        "read_budget_exhausted": True,
        "write_budget_exhausted": True,
    }
    if execution != expected:
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "projection budget execution ledger differs"
        )
    return expected


def bind_task_evidence_to_summary_v1(
    summary_value: Mapping[str, object], evidence_value: Mapping[str, object],
    *, request_value: Mapping[str, object], raw_request: bytes,
    process_budget_value: Mapping[str, object],
    runtime_observation_value: Mapping[str, object],
    budget_execution_value: Mapping[str, object],
) -> dict[str, object]:
    summary = dict(summary_value)
    request = task_manifest.validate_projection_task_request_v1(request_value)
    process_budget = dict(process_budget_value)
    process_budget_identity = _object_identity_v1(
        request["process_budget_identity"],
        label="bound projection process budget identity",
    )
    process_budget_raw = contract.canonical_json_bytes_v1(process_budget)
    runtime_observation = dict(runtime_observation_value)
    runtime_without_hash = dict(runtime_observation)
    runtime_hash = runtime_without_hash.pop("runtime_observation_sha256", None)
    projection_identities = summary.get("projection_identities")
    budget_execution = _validated_projection_budget_execution_v1(
        budget_execution_value,
        process_budget=process_budget,
        projection_identities=projection_identities,
    )
    read_ledger = budget_execution["read_ledger"]
    write_ledger = budget_execution["write_ledger"]
    prior_hash = summary.pop("projection_execution_summary_sha256", None)
    if (
        "task_binding_evidence" in summary
        or type(prior_hash) is not str
        or prior_hash != contract.canonical_sha256_v1(summary)
        or contract.canonical_json_bytes_v1(request) != raw_request
        or summary.get("design_identity") != request.get("design_identity")
        or summary.get("topology_identity") != request.get("topology_identity")
        or process_budget_identity["bytes"] != len(process_budget_raw)
        or process_budget_identity["sha256"]
        != sha256(process_budget_raw).hexdigest()
        or process_budget.get("process_role") != "projection-publisher"
        or process_budget.get("publisher_process_budget_sha256")
        != contract.canonical_sha256_v1({
            key: value for key, value in process_budget.items()
            if key != "publisher_process_budget_sha256"
        })
        or runtime_hash != contract.canonical_sha256_v1(runtime_without_hash)
        or runtime_observation.get("process_role") != "projection-publisher"
        or runtime_observation.get("process_budget_identity")
        != process_budget_identity
        or runtime_observation.get("process_budget_sha256")
        != process_budget.get("publisher_process_budget_sha256")
        or [row.get("publication_identity") for row in write_ledger]
        != projection_identities
        or budget_execution.get("read_ledger_sha256")
        != contract.canonical_sha256_v1(read_ledger)
        or budget_execution.get("write_ledger_sha256")
        != contract.canonical_sha256_v1(write_ledger)
        or budget_execution.get("read_object_count")
        != 2 + contract.EXACT_STRUCTURAL_OBJECT_COUNT
        or budget_execution.get("write_object_count")
        != contract.PANEL_SLATE_COUNT
        or len(read_ledger) != budget_execution.get("read_object_count")
        or len(write_ledger) != budget_execution.get("write_object_count")
        or budget_execution.get("read_budget_exhausted") is not True
        or budget_execution.get("write_budget_exhausted") is not True
    ):
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "unbound projection summary authority differs"
        )
    summary["projection_task_request_sha256"] = request[
        "projection_task_request_sha256"
    ]
    summary["process_budget_identity"] = process_budget_identity
    summary["publisher_process_budget_sha256"] = process_budget[
        "publisher_process_budget_sha256"
    ]
    summary["runtime_observation"] = runtime_observation
    summary["runtime_observation_sha256"] = runtime_hash
    summary.update(budget_execution)
    summary["task_binding_evidence"] = _full_binding_evidence_v1(
        evidence_value, raw_request=raw_request
    )
    summary["projection_execution_summary_sha256"] = (
        contract.canonical_sha256_v1(summary)
    )
    return summary


def build_projection_runtime_observation_v1(
    *, authority: Mapping[str, object], request: Mapping[str, object],
    observed_command: list[str], environ: Mapping[str, str],
) -> dict[str, object]:
    """Bind the frozen component command and separately proven full child argv."""
    bootstrap = dict(authority["bootstrap_manifest"])
    budget = dict(authority["projection_process_budget"])
    authorization = dict(authority["pre_design_run_authorization"])
    process_spec = contract.bootstrap_process_spec_v1(
        bootstrap, process_role="projection-publisher"
    )
    chain = process_spec.get("process_chain")
    if not isinstance(chain, list) or len(chain) != 1:
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "projection bootstrap process chain differs"
        )
    component = dict(chain[0])
    component_command = component.get("command")
    if (
        not isinstance(component_command, list)
        or observed_command[:len(component_command)] != component_command
        or environ.get("CLOUD_RUN_JOB")
        != authorization.get("reused_job_name")
        or environ.get("CLOUD_RUN_TASK_INDEX") != "0"
    ):
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "projection runtime component observation differs"
        )
    try:
        return contract.build_runtime_observation_v1(
            bootstrap_manifest=bootstrap,
            bootstrap_manifest_identity=request[
                "bootstrap_manifest_identity"
            ],
            process_budget=budget,
            process_budget_identity=request["process_budget_identity"],
            launch_intent_identity=request[
                "pre_design_run_authorization_identity"
            ],
            observed_code_commit=environ.get("CODE_SHA", ""),
            observed_image_digest=environ.get(
                "R6_RUNTIME_IMAGE_DIGEST", ""
            ),
            # The runtime record binds the immutable two-token component.
            # Full dynamic argv is independently kernel-observed and bound by
            # the selected manifest task's child evidence.
            observed_command=component_command,
            observed_entrypoint_sha256=sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
            cloud_job_name=environ.get("CLOUD_RUN_JOB", ""),
            cloud_execution_name=environ.get("CLOUD_RUN_EXECUTION", ""),
            cloud_task_index=0,
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "projection runtime observation differs"
        ) from exc


def framed_summary_bytes_v1(summary: Mapping[str, object]) -> bytes:
    framed = contract.canonical_json_bytes_v1(summary) + b"\n"
    if len(framed) > MAXIMUM_STDOUT_BYTES:
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "projection summary exceeds its stdout byte ceiling"
        )
    return framed


def _add_identity(parser: argparse.ArgumentParser, prefix: str) -> None:
    parser.add_argument(f"--{prefix}-uri", required=True)
    parser.add_argument(f"--{prefix}-generation", required=True)
    parser.add_argument(f"--{prefix}-sha256", required=True)
    parser.add_argument(f"--{prefix}-bytes", required=True, type=int)


def _identity(args: argparse.Namespace, prefix: str) -> dict[str, object]:
    name = prefix.replace("-", "_")
    return {
        "uri": getattr(args, f"{name}_uri"),
        "generation": getattr(args, f"{name}_generation"),
        "sha256": getattr(args, f"{name}_sha256"),
        "bytes": getattr(args, f"{name}_bytes"),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--project", default=PROJECT)
    _add_identity(parser, "design")
    _add_identity(parser, "topology")
    parser.add_argument(
        "--resume-identity-json",
        action="append",
        default=[],
        help=(
            "Previously recorded exact projection identity as canonical JSON; "
            "repeat once per already-created output. No current-generation "
            "lookup is permitted."
        ),
    )
    return parser


def _require_gate(args: argparse.Namespace) -> None:
    if args.execute is not True:
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "--execute is required"
        )
    if args.project != PROJECT:
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "projection publication project differs"
        )
    if os.environ.get(ENABLE_ENV) != "1":
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            f"projection publication requires exact {ENABLE_ENV}=1"
        )
    redirected = [name for name in FORBIDDEN_REDIRECT_ENV if os.environ.get(name)]
    if redirected:
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "projection storage endpoint redirect is forbidden"
        )


def _resume_identities_v1(args: argparse.Namespace) -> dict[str, dict[str, object]]:
    retained: dict[str, dict[str, object]] = {}
    for offset, raw_value in enumerate(args.resume_identity_json):
        try:
            parsed = task_manifest.strict_json_v1(
                raw_value.encode("utf-8"),
                label=f"resume identity[{offset}]",
            )
        except (AttributeError, UnicodeError, ValueError) as exc:
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                f"resume identity[{offset}] is not canonical JSON"
            ) from exc
        identity = _object_identity_v1(
            parsed, label=f"resume identity[{offset}]"
        )
        uri = str(identity["uri"])
        if (
            not uri.startswith(contract.OUTPUT_NAMESPACE)
            or "/projections/" not in uri
            or uri in retained
        ):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "resume projection identity URI differs or repeats"
            )
        retained[uri] = identity
    return retained


def _validated_request_v1(
    args: argparse.Namespace,
) -> tuple[dict[str, object], dict[str, object], dict[str, dict[str, object]]]:
    """Reject every semantic/redirect error before a cloud client exists."""
    _require_gate(args)
    design = _object_identity_v1(
        _identity(args, "design"), label="projection design identity"
    )
    topology = _object_identity_v1(
        _identity(args, "topology"), label="projection topology identity"
    )
    return design, topology, _resume_identities_v1(args)


class _StrictProjectionObjectStore:
    """Exact GET plus create-if-absent; collision needs a recorded identity.

    This adapter deliberately has no LIST, metadata resolution, or
    current-generation method. The enclosing budget/core path owns the single
    immediate generation-exact output reopen, including resume-body proof.
    """

    def __init__(self, *, project: str) -> None:
        try:
            from google.cloud import storage
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "google-cloud-storage is required for projection publication"
            ) from exc
        self._client = storage.Client(
            project=project,
            client_options={"api_endpoint": FIXED_STORAGE_ENDPOINT},
        )

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if not uri.startswith("gs://"):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "projection object URI must use gs://"
            )
        bucket, marker, name = uri[5:].partition("/")
        if not marker or not bucket or not name or name.endswith("/"):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "projection object URI differs"
            )
        return bucket, name

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        identity = _object_identity_v1(
            identity_value, label="projection exact read"
        )
        bucket, name = self._parts(str(identity["uri"]))
        blob = self._client.bucket(bucket).blob(
            name, generation=int(str(identity["generation"]))
        )
        try:
            raw = blob.download_as_bytes(
                if_generation_match=int(str(identity["generation"]))
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "projection generation-pinned GET failed"
            ) from exc
        if (
            len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "projection exact-read body differs"
            )
        return raw

    def publish_create_once(
        self,
        uri: str,
        raw: bytes,
        *,
        prior_identity: Mapping[str, object] | None,
    ) -> dict[str, object]:
        if prior_identity is not None:
            prior = _object_identity_v1(
                prior_identity, label="recorded resume projection identity"
            )
            if (
                prior["uri"] != uri
                or prior["bytes"] != len(raw)
                or prior["sha256"] != sha256(raw).hexdigest()
            ):
                raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                    "recorded projection resume identity differs"
                )
            return prior
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ not in {"PreconditionFailed", "Conflict"}:
                raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                    "strict create-once projection publication failed"
                ) from exc
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "projection collision lacks a recorded exact identity"
            ) from exc
        generation = str(blob.generation or "")
        if not generation.isdigit() or generation.startswith("0"):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "created projection generation is unavailable"
            )
        created = {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        return created


class _ProjectionBudgetedObjectStoreV1:
    """Expose only the exact core reads/writes compiled before execution."""

    def __init__(
        self, *, store: Any, process_budget: Mapping[str, object],
        process_budget_identity: Mapping[str, object],
        request: Mapping[str, object],
    ) -> None:
        budget = dict(process_budget)
        reads = [dict(row) for row in budget["read_allowlist"]]
        writes = [dict(row) for row in budget["write_allowlist"]]
        common_roles = [
            "design", "topology", "bootstrap-manifest", "launch-intent",
        ]
        if (
            budget.get("process_role") != "projection-publisher"
            or [row.get("role") for row in reads[:4]] != common_roles
            or len(reads) != 4 + contract.EXACT_STRUCTURAL_OBJECT_COUNT
            or [row.get("role") for row in reads[4:]]
            != [
                f"scientific-{index:03d}"
                for index in range(contract.EXACT_STRUCTURAL_OBJECT_COUNT)
            ]
            or len(writes) != contract.PANEL_SLATE_COUNT
            or any(row.get("role") != "projection" for row in writes)
            or reads[0].get("identity") != request.get("design_identity")
            or reads[1].get("identity") != request.get("topology_identity")
            or reads[2].get("identity")
            != request.get("bootstrap_manifest_identity")
            or reads[3].get("identity")
            != request.get("pre_design_run_authorization_identity")
        ):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "projection publisher process budget lattice differs"
            )
        self._store = store
        self._budget = budget
        self._budget_identity = _object_identity_v1(
            process_budget_identity,
            label="projection publisher process budget identity",
        )
        core_read_rows = [*reads[:2], *reads[4:]]
        self._expected_reads = [
            _object_identity_v1(
                row["identity"], label=f"projection budget read[{index}]"
            )
            for index, row in enumerate(core_read_rows)
        ]
        self._expected_read_roles = [
            "design", "topology",
            *[
                f"structural-{index:03d}"
                for index in range(contract.EXACT_STRUCTURAL_OBJECT_COUNT)
            ],
        ]
        self._writes = writes
        self._read_index = 0
        self._write_index = 0
        self._published: list[dict[str, object]] = []
        self._publication_raw: list[bytes] = []
        self._publication_reopened: list[bool] = []

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        identity = _object_identity_v1(
            identity_value, label="budgeted projection read"
        )
        if self._read_index == len(self._expected_reads):
            output_index = len(self._published) - 1
            if (
                output_index < 0
                or self._publication_reopened[output_index]
                or identity != self._published[output_index]
            ):
                raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                    "projection output reopen differs from its exact write"
                )
            raw = self._store.read_exact(identity)
            if raw != self._publication_raw[output_index]:
                raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                    "projection output exact-reopen body differs"
                )
            self._publication_reopened[output_index] = True
            return raw
        if (
            self._read_index >= len(self._expected_reads)
            or identity != self._expected_reads[self._read_index]
        ):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "projection read differs from its exact process budget"
            )
        raw = self._store.read_exact(identity)
        self._read_index += 1
        return raw

    def publish_create_once(
        self, uri: str, raw: bytes, *,
        prior_identity: Mapping[str, object] | None,
    ) -> dict[str, object]:
        if self._read_index != len(self._expected_reads):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "projection publication began before read-budget exhaustion"
            )
        if self._write_index >= len(self._writes):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "projection publication exceeds its process budget"
            )
        if (
            self._publication_reopened
            and self._publication_reopened[-1] is not True
        ):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "projection publication preceded prior exact reopen"
            )
        descriptor = self._writes[self._write_index]
        if (
            type(raw) is not bytes
            or descriptor.get("ordinal") != self._write_index + 1
            or descriptor.get("uri") != uri
            or descriptor.get("create_once") is not True
            or type(descriptor.get("max_bytes")) is not int
            or not 0 < len(raw) <= int(descriptor["max_bytes"])
        ):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "projection write differs from its exact process budget"
            )
        returned = _object_identity_v1(
            self._store.publish_create_once(
                uri, raw, prior_identity=prior_identity
            ),
            label="budgeted projection publication",
        )
        if (
            returned["uri"] != uri
            or returned["bytes"] != len(raw)
            or returned["sha256"] != sha256(raw).hexdigest()
        ):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "budgeted projection publication identity differs"
            )
        self._published.append(returned)
        self._publication_raw.append(raw)
        self._publication_reopened.append(False)
        self._write_index += 1
        return returned

    def require_complete(self) -> dict[str, object]:
        if (
            self._read_index != len(self._expected_reads)
            or self._write_index != len(self._writes)
            or len(self._published) != len(self._writes)
            or self._publication_reopened != [True] * len(self._writes)
        ):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "projection process budget did not exhaust exactly"
            )
        read_ledger = [
            {"ordinal": index, "role": self._expected_read_roles[index],
             "identity": identity}
            for index, identity in enumerate(self._expected_reads)
        ]
        write_ledger = [
            {
                "ordinal": self._writes[index]["ordinal"],
                "role": self._writes[index]["role"],
                "uri": self._writes[index]["uri"],
                "maximum_bytes": self._writes[index]["max_bytes"],
                "publication_identity": identity,
                "exact_generation_reopen_proved": True,
            }
            for index, identity in enumerate(self._published)
        ]
        return {
            "read_ledger": read_ledger,
            "read_ledger_sha256": contract.canonical_sha256_v1(read_ledger),
            "read_object_count": self._read_index,
            "write_ledger": write_ledger,
            "write_ledger_sha256": contract.canonical_sha256_v1(write_ledger),
            "write_object_count": self._write_index,
            "read_budget_exhausted": True,
            "write_budget_exhausted": True,
        }


def reopen_controller_projection_task_after_client_v1(
    *, parsed_binding: Mapping[str, object], environ: Mapping[str, str],
    raw_request: bytes, observed_command: list[str], read_exact: Any,
) -> tuple[dict[str, object], dict[str, object]]:
    """Validate the selected task first, then replay its complete authority."""
    manifest_identity = _object_identity_v1(
        parsed_binding.get("manifest_identity"),
        label="controller projection task manifest identity",
    )
    if manifest_identity["bytes"] > task_manifest.MAXIMUM_MANIFEST_BYTES:
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "projection task manifest exceeds its pre-read ceiling"
        )
    manifest_raw = read_exact(manifest_identity)
    manifest = task_manifest.strict_json_v1(
        manifest_raw, label="controller projection task manifest"
    )
    immediate = task_manifest.validate_child_task_binding_v1(
        manifest,
        manifest_identity=manifest_identity,
        environ=environ,
        raw_request=raw_request,
        observed_command=observed_command,
        expected_process_role="projection-publisher",
        expected_phase="projection",
        expected_process_ordinal=0,
    )
    manifest_replays = 0

    def read_with_manifest_cache(
        identity_value: Mapping[str, object],
    ) -> bytes:
        nonlocal manifest_replays
        identity = _object_identity_v1(
            identity_value, label="controller projection authority identity"
        )
        if identity == manifest_identity:
            manifest_replays += 1
            if manifest_replays != 1:
                raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                    "projection task manifest cache replay count differs"
                )
            return manifest_raw
        return read_exact(identity)

    authority = task_manifest.reopen_task_manifest_authority_v1(
        manifest_identity, read_exact=read_with_manifest_cache
    )
    replayed = task_manifest.validate_child_task_binding_v1(
        authority["manifest"],
        manifest_identity=authority["manifest_identity"],
        environ=environ,
        raw_request=raw_request,
        observed_command=observed_command,
        expected_process_role="projection-publisher",
        expected_phase="projection",
        expected_process_ordinal=0,
    )
    if (
        manifest_replays != 1
        or contract.canonical_json_bytes_v1(immediate)
        != contract.canonical_json_bytes_v1(replayed)
    ):
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "projection controller task authority replay differs"
        )
    return immediate, authority


def _run(
    args: argparse.Namespace,
    *,
    store: Any,
) -> dict[str, object]:
    design_identity, topology_identity, resume_by_uri = _validated_request_v1(args)

    def read_exact(identity_value: Mapping[str, object]) -> bytes:
        identity = _object_identity_v1(
            identity_value, label="projection CLI exact read"
        )
        return store.read_exact(identity)

    def publish_create_once(uri: str, raw: bytes) -> dict[str, object]:
        return store.publish_create_once(
            uri,
            raw,
            prior_identity=resume_by_uri.get(uri),
        )

    return projection.publish_projection_layer_v1(
        design_identity=design_identity,
        topology_identity=topology_identity,
        read_exact=read_exact,
        publish_create_once=publish_create_once,
    )


def main() -> None:
    raw_request = _read_stdin_bounded_v1()
    try:
        parsed_binding = task_manifest.parse_child_task_binding_environment_v1(
            os.environ
        )
        request = task_manifest.validate_projection_task_request_v1(
            task_manifest.strict_json_v1(
                raw_request, label="stdin projection task request"
            )
        )
        if (
            parsed_binding["layer_id"] != "projection"
            or parsed_binding["task_index"] != 0
            or parsed_binding["manifest_identity"]["bytes"]
            > task_manifest.MAXIMUM_MANIFEST_BYTES
        ):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "preclient projection task layer/index binding differs"
            )
        observed_command = observed_process_command_v1()
        if (
            parsed_binding["request_sha256"]
            != sha256(raw_request).hexdigest()
            or parsed_binding["child_command_sha256"]
            != contract.canonical_sha256_v1({
                "command": observed_command,
                "entrypoint_sha256": sha256(
                    Path(__file__).read_bytes()
                ).hexdigest(),
            })
        ):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "preclient projection request/command binding differs"
            )
        try:
            args = _parser().parse_args(observed_command[2:])
        except SystemExit as exc:
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "projection command arguments differ"
            ) from exc
        # Reject dry/misdirected invocations before constructing any cloud
        # client, so a missing gate cannot even acquire an input transport.
        design, topology, resumes = _validated_request_v1(args)
        expected_resumes = {
            str(identity["uri"]): identity
            for identity in request["prior_projection_identities"]
            if identity is not None
        }
        if (
            design != request["design_identity"]
            or topology != request["topology_identity"]
            or resumes != expected_resumes
        ):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "projection command/request authority differs"
            )
        store = _StrictProjectionObjectStore(project=args.project)
        binding_evidence, authority = (
            reopen_controller_projection_task_after_client_v1(
                parsed_binding=parsed_binding,
                environ=os.environ,
                raw_request=raw_request,
                observed_command=observed_command,
                read_exact=store.read_exact,
            )
        )
        process_budget = authority.get("projection_process_budget")
        if not isinstance(process_budget, Mapping):
            raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
                "projection process budget authority is absent"
            )
        runtime_observation = build_projection_runtime_observation_v1(
            authority=authority,
            request=request,
            observed_command=observed_command,
            environ=os.environ,
        )
        budgeted_store = _ProjectionBudgetedObjectStoreV1(
            store=store,
            process_budget=process_budget,
            process_budget_identity=request["process_budget_identity"],
            request=request,
        )
        summary = _run(args, store=budgeted_store)
        budget_execution = budgeted_store.require_complete()
        summary = bind_task_evidence_to_summary_v1(
            summary,
            binding_evidence,
            request_value=request,
            raw_request=raw_request,
            process_budget_value=process_budget,
            runtime_observation_value=runtime_observation,
            budget_execution_value=budget_execution,
        )
    except Exception as exc:
        raise RunCorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "current-bank projection publication failed"
        ) from exc
    sys.stdout.buffer.write(framed_summary_bytes_v1(summary))


if __name__ == "__main__":
    main()
