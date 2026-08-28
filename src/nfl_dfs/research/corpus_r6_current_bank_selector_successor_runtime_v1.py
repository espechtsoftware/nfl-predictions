"""Observed runtime authority for the grouped selector successor child.

This is intentionally a different command and schema from the frozen
64-fit current-bank matrix selector.  The successor may consume the source
selector's scientific matrix capability, but it must never claim that it ran
through the source selector executable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import os
from pathlib import Path
import re
import sys
from typing import Final

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)


RUNTIME_SCHEMA: Final = (
    "corpus-r6-current-bank-grouped-selector-observed-runtime/v1"
)
RUNTIME_MODE: Final = "grouped-successor-matrix-selector"
ENTRYPOINT_RELATIVE_PATH: Final = (
    "scripts/run_corpus_r6_current_bank_selector_successor_v1.py"
)
ENTRYPOINT_IMAGE_PATH: Final = f"/app/{ENTRYPOINT_RELATIVE_PATH}"
PYTHON_EXECUTABLE: Final = "/usr/local/bin/python3.11"
PROCESS_ORDINAL_ENV: Final = "R6_SUCCESSOR_PROCESS_ORDINAL"
FIXED_GCP_PROJECT: Final = "nfl-predictions-503414"
FIXED_STORAGE_ENDPOINT: Final = "https://storage.googleapis.com"

_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}\Z")
_SHA_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_REDIRECT_ENV_KEYS: Final = frozenset({
    "CURL_CA_BUNDLE",
    "GCE_METADATA_HOST",
    "GCE_METADATA_IP",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "LD_AUDIT",
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "PYTHONBREAKPOINT",
    "PYTHONHOME",
    "PYTHONINSPECT",
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
    "REQUESTS_CA_BUNDLE",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
})


class CorpusR6CurrentBankSelectorSuccessorRuntimeV1Error(ValueError):
    """The grouped selector child runtime could not be authenticated."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankSelectorSuccessorRuntimeV1Error(message)


def _canonical(value: object) -> bytes:
    return contract.canonical_json_bytes_v1(value)


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} is already present")
    body[field] = sha256(_canonical(body)).hexdigest()
    return body


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _repository_root_v1() -> Path:
    return Path(__file__).resolve().parents[3]


def entrypoint_source_sha256_v1() -> str:
    path = _repository_root_v1() / ENTRYPOINT_RELATIVE_PATH
    if not path.is_file():
        _fail("grouped selector successor entrypoint is absent")
    return sha256(path.read_bytes()).hexdigest()


def canonical_matrix_selector_command_v1() -> list[str]:
    return [PYTHON_EXECUTABLE, ENTRYPOINT_IMAGE_PATH, "matrix-selector"]


def build_runtime_evidence_v1(
    *,
    environ: Mapping[str, str],
    observed_command: object,
    process_ordinal: int,
    pid: int,
    parent_pid: int,
) -> dict[str, object]:
    environment = dict(environ)
    redirected = [key for key in _REDIRECT_ENV_KEYS if environment.get(key)]
    if redirected:
        _fail("grouped selector runtime redirect environment is forbidden")
    project_values = {
        environment[key]
        for key in ("GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT", "GCP_PROJECT")
        if environment.get(key)
    }
    commit = environment.get("CODE_SHA", "")
    image = environment.get("R6_RUNTIME_IMAGE_DIGEST", "")
    task_text = environment.get("CLOUD_RUN_TASK_INDEX", "")
    process_text = environment.get(PROCESS_ORDINAL_ENV, "")
    if (
        project_values != {FIXED_GCP_PROJECT}
        or environment.get("GOOGLE_CLOUD_PROJECT") != FIXED_GCP_PROJECT
        or _COMMIT_RE.fullmatch(commit) is None
        or not image.startswith("sha256:")
        or _SHA_RE.fullmatch(image[7:]) is None
        or not task_text.isdecimal()
        or not process_text.isdecimal()
        or type(process_ordinal) is not int
        or int(process_text) != process_ordinal
        or type(pid) is not int
        or type(parent_pid) is not int
        or pid < 1
        or parent_pid < 1
        or pid == parent_pid
    ):
        _fail("grouped selector runtime environment/process binding differs")
    job = environment.get("CLOUD_RUN_JOB", "")
    execution = environment.get("CLOUD_RUN_EXECUTION", "")
    if not job or not execution or len(job) > 512 or len(execution) > 512:
        _fail("grouped selector Cloud Run job/execution binding is absent")
    command = [
        str(value)
        for value in _sequence(observed_command, label="observed command")
    ]
    canonical = canonical_matrix_selector_command_v1()
    if command != canonical:
        _fail("grouped selector observed command differs")
    entrypoint_sha256 = entrypoint_source_sha256_v1()
    body = {
        "schema_version": RUNTIME_SCHEMA,
        "runtime_mode": RUNTIME_MODE,
        "project_id": FIXED_GCP_PROJECT,
        "storage_endpoint": FIXED_STORAGE_ENDPOINT,
        "code_commit": commit,
        "image_digest": image,
        "job_name": job,
        "execution_id": execution,
        "task_index": int(task_text),
        "process_ordinal": process_ordinal,
        "pid": pid,
        "parent_pid": parent_pid,
        "python_executable": PYTHON_EXECUTABLE,
        "python_version": sys.version.split()[0],
        "entrypoint_path": ENTRYPOINT_IMAGE_PATH,
        "entrypoint_sha256": entrypoint_sha256,
        "command": canonical,
        "command_sha256": contract.canonical_sha256_v1({
            "command": canonical,
            "entrypoint_sha256": entrypoint_sha256,
        }),
        "redirect_environment_present": False,
        "evidence_strength": "process-environment-observation-only",
        "outer_launch_authority_binding_required": True,
        "source_control_runtime_compatibility_claimed": False,
    }
    return _with_hash(body, field="runtime_evidence_sha256")


def validate_runtime_evidence_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="grouped selector runtime evidence")
    expected_fields = {
        "schema_version", "runtime_mode", "project_id", "storage_endpoint",
        "code_commit", "image_digest", "job_name", "execution_id",
        "task_index", "process_ordinal", "pid", "parent_pid",
        "python_executable", "python_version", "entrypoint_path",
        "entrypoint_sha256", "command", "command_sha256",
        "redirect_environment_present", "evidence_strength",
        "outer_launch_authority_binding_required",
        "source_control_runtime_compatibility_claimed",
        "runtime_evidence_sha256",
    }
    if set(item) != expected_fields:
        _fail("grouped selector runtime evidence fields differ")
    if item["runtime_evidence_sha256"] != contract.canonical_sha256_v1({
        key: row for key, row in item.items() if key != "runtime_evidence_sha256"
    }):
        _fail("grouped selector runtime evidence self hash differs")
    command = canonical_matrix_selector_command_v1()
    if (
        item["schema_version"] != RUNTIME_SCHEMA
        or item["runtime_mode"] != RUNTIME_MODE
        or item["project_id"] != FIXED_GCP_PROJECT
        or item["storage_endpoint"] != FIXED_STORAGE_ENDPOINT
        or _COMMIT_RE.fullmatch(str(item["code_commit"])) is None
        or not str(item["image_digest"]).startswith("sha256:")
        or _SHA_RE.fullmatch(str(item["image_digest"])[7:]) is None
        or item["command"] != command
        or item["python_executable"] != PYTHON_EXECUTABLE
        or item["entrypoint_path"] != ENTRYPOINT_IMAGE_PATH
        or item["entrypoint_sha256"] != entrypoint_source_sha256_v1()
        or item["command_sha256"] != contract.canonical_sha256_v1({
            "command": command,
            "entrypoint_sha256": item["entrypoint_sha256"],
        })
        or item["redirect_environment_present"] is not False
        or item["evidence_strength"]
        != "process-environment-observation-only"
        or item["outer_launch_authority_binding_required"] is not True
        or item["source_control_runtime_compatibility_claimed"] is not False
    ):
        _fail("grouped selector runtime evidence fixed binding differs")
    for field in ("task_index", "process_ordinal", "pid", "parent_pid"):
        if type(item[field]) is not int or item[field] < 0:
            _fail(f"grouped selector runtime {field} differs")
    if item["pid"] < 1 or item["parent_pid"] < 1 or item["pid"] == item["parent_pid"]:
        _fail("grouped selector runtime process identity differs")
    for field in ("job_name", "execution_id", "python_version"):
        if type(item[field]) is not str or not item[field] or len(item[field]) > 512:
            _fail(f"grouped selector runtime {field} differs")
    return item


def derive_current_process_runtime_evidence_v1(*, process_ordinal: int) -> dict[str, object]:
    return build_runtime_evidence_v1(
        environ=os.environ,
        observed_command=canonical_matrix_selector_command_v1(),
        process_ordinal=process_ordinal,
        pid=os.getpid(),
        parent_pid=os.getppid(),
    )


__all__ = [
    "ENTRYPOINT_IMAGE_PATH",
    "ENTRYPOINT_RELATIVE_PATH",
    "PROCESS_ORDINAL_ENV",
    "RUNTIME_MODE",
    "RUNTIME_SCHEMA",
    "CorpusR6CurrentBankSelectorSuccessorRuntimeV1Error",
    "build_runtime_evidence_v1",
    "canonical_matrix_selector_command_v1",
    "derive_current_process_runtime_evidence_v1",
    "entrypoint_source_sha256_v1",
    "validate_runtime_evidence_v1",
]
