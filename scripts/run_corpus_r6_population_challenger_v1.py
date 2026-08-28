#!/usr/bin/env python3
"""Dispatch one source ordinal through all F7/F8/F9 population profiles."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

from nfl_dfs.research import (
    corpus_r6_population_challenger_authority_v1 as authority,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_runtime_v1 as runtime,
)
from nfl_dfs.research import corpus_r6_population_profiles_v1 as profiles


MAXIMUM_COMMAND_BYTES = 4_096


class RunCorpusR6PopulationChallengerV1Error(RuntimeError):
    """The population challenger dispatcher failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6PopulationChallengerV1Error(message)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return authority.object_identity_v1(value, label=label)
    except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise RunCorpusR6PopulationChallengerV1Error(str(exc)) from exc


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        return authority.strict_json_bytes_v1(raw, label=label)
    except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise RunCorpusR6PopulationChallengerV1Error(str(exc)) from exc


def _parse_identity_text(value: str, *, label: str) -> dict[str, object]:
    if not value or len(value.encode("utf-8")) > 2_048:
        _fail(f"{label} environment is absent or oversized")
    return _identity(
        _strict_json(value.encode("utf-8"), label=label), label=label
    )


def observed_dispatcher_command_v1(raw_cmdline: bytes | None = None) -> list[str]:
    if raw_cmdline is None:
        try:
            raw = Path("/proc/self/cmdline").read_bytes()
        except OSError as exc:
            raise RunCorpusR6PopulationChallengerV1Error(
                "dispatcher kernel command is unavailable"
            ) from exc
    else:
        raw = raw_cmdline
    if (
        type(raw) is not bytes
        or not raw
        or len(raw) > MAXIMUM_COMMAND_BYTES
        or not raw.endswith(b"\0")
    ):
        _fail("dispatcher kernel command bytes differ")
    fields = raw[:-1].split(b"\0")
    if len(fields) != 4 or any(not row for row in fields):
        _fail("dispatcher kernel command shape differs")
    try:
        values = [row.decode("utf-8") for row in fields]
    except UnicodeDecodeError as exc:
        raise RunCorpusR6PopulationChallengerV1Error(
            "dispatcher kernel command is not UTF-8"
        ) from exc
    return [os.path.abspath(values[0]), values[1], values[2], values[3]]


class GCSExactTransportV1:
    """Generation-exact reads and create-once equal-byte retry recovery."""

    def __init__(self) -> None:
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import storage
        except Exception as exc:  # pragma: no cover - cloud dependency
            raise RuntimeError("google-cloud-storage is required") from exc
        self._client = storage.Client(
            project=authority.FIXED_GCP_PROJECT,
            client_options=ClientOptions(
                api_endpoint=authority.FIXED_STORAGE_ENDPOINT
            ),
        )
        self._cache: dict[tuple[str, str, str, int], bytes] = {}

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if not uri.startswith("gs://"):
            _fail("GCS URI must use gs://")
        bucket, separator, name = uri[5:].partition("/")
        if not separator or not bucket or not name:
            _fail("GCS URI is malformed")
        return bucket, name

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        identity = _identity(identity_value, label="GCS exact read")
        key = (
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )
        if key in self._cache:
            return self._cache[key]
        bucket_name, object_name = self._parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        blob = self._client.bucket(bucket_name).blob(
            object_name, generation=generation
        )
        raw = blob.download_as_bytes(
            if_generation_match=generation, retry=None
        )
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("generation-exact GCS bytes differ")
        self._cache[key] = raw
        return raw

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if type(raw) is not bytes or not raw:
            _fail("create-once publication bytes differ")
        bucket_name, object_name = self._parts(uri)
        blob = self._client.bucket(bucket_name).blob(object_name)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
                retry=None,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ not in {"Conflict", "PreconditionFailed"}:
                raise
            current = self._client.bucket(bucket_name).blob(object_name)
            current.reload(retry=None)
            if current.generation is None:
                _fail("create-once collision lacks an existing generation")
            identity = {
                "uri": uri,
                "generation": str(current.generation),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
            if self.read_exact(identity) != raw:
                _fail("create-once collision bytes differ")
            return identity
        if blob.generation is None:
            _fail("create-once upload lacks a generation")
        identity = {
            "uri": uri,
            "generation": str(blob.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if self.read_exact(identity) != raw:
            _fail("create-once publication exact reopen differs")
        return identity


def execute_environment_task_v1(
    environment: Mapping[str, str] | None = None,
    *,
    store: GCSExactTransportV1 | None = None,
    observed_command: list[str] | None = None,
) -> dict[str, object]:
    env = dict(os.environ if environment is None else environment)
    if env.get(authority.ENABLE_ENV) != "1":
        _fail("population challenger execution is not exactly enabled")
    inherited = sorted(set(env) & profiles.STRUCTURE_ENV_KEYS)
    if inherited:
        _fail(f"ambient inherited structure keys are forbidden: {inherited}")
    manifest_identity = _parse_identity_text(
        env.get(authority.MANIFEST_IDENTITY_ENV, ""),
        label="challenger manifest identity",
    )
    task_index_raw = env.get("CLOUD_RUN_TASK_INDEX", "")
    if not task_index_raw.isdecimal() or task_index_raw.startswith("+"):
        _fail("CLOUD_RUN_TASK_INDEX must be a canonical decimal integer")
    task_index = int(task_index_raw)
    transport = GCSExactTransportV1() if store is None else store
    raw_manifest = transport.read_exact(manifest_identity)
    manifest = authority.validate_task_manifest_v1(
        _strict_json(raw_manifest, label="challenger task manifest")
    )
    authority.bind_body_to_identity_v1(
        manifest, manifest_identity, label="challenger task manifest"
    )
    command = observed_dispatcher_command_v1() if observed_command is None else list(
        observed_command
    )
    expected = list(authority.DISPATCHER_COMMAND)
    if command != expected:
        _fail("observed dispatcher command differs from manifest authority")
    request = authority.task_request_v1(manifest, task_index=task_index)
    return runtime.execute_task_v1(
        request,
        read_exact=transport.read_exact,
        publish_create_once=transport.publish_create_once,
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args != ["task"]:
        raise SystemExit("usage: ...population_challenger_v1.py task")
    completion = execute_environment_task_v1()
    runtime.validate_task_completion_v1(completion)
    sys.stdout.buffer.write(authority.canonical_bytes_v1(completion))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
