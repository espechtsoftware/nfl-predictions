#!/usr/bin/env python3
"""Prepare or execute the 54-slate F7/F8/F9 crossed-selector batch."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from hashlib import sha256
import os
from pathlib import Path
import sys

from nfl_dfs.research import (
    corpus_r6_population_challenger_authority_v1 as population_authority,
)
from nfl_dfs.research import corpus_r6_population_crossed_cloud_v1 as cloud
from nfl_dfs.research import corpus_r6_population_profiles_v1 as profiles


MAXIMUM_COMMAND_BYTES = 4_096


class RunCorpusR6PopulationCrossedCloudV1Error(RuntimeError):
    """The population-crossed operator/dispatcher failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6PopulationCrossedCloudV1Error(message)


def _canonical(value: object) -> bytes:
    try:
        return population_authority.canonical_bytes_v1(value)
    except population_authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise RunCorpusR6PopulationCrossedCloudV1Error(str(exc)) from exc


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        return population_authority.strict_json_bytes_v1(raw, label=label)
    except population_authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise RunCorpusR6PopulationCrossedCloudV1Error(str(exc)) from exc


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return population_authority.object_identity_v1(value, label=label)
    except population_authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise RunCorpusR6PopulationCrossedCloudV1Error(str(exc)) from exc


def _parse_identity_text(value: str, *, label: str) -> dict[str, object]:
    if not value or len(value.encode("utf-8")) > 2_048:
        _fail(f"{label} environment is absent or oversized")
    return _identity(
        _strict_json(value.encode("utf-8"), label=label), label=label
    )


def observed_dispatcher_command_v1(
    raw_cmdline: bytes | None = None,
) -> list[str]:
    if raw_cmdline is None:
        try:
            raw = Path("/proc/self/cmdline").read_bytes()
        except OSError as exc:
            raise RunCorpusR6PopulationCrossedCloudV1Error(
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
        raise RunCorpusR6PopulationCrossedCloudV1Error(
            "dispatcher kernel command is not UTF-8"
        ) from exc
    return [os.path.abspath(values[0]), values[1], values[2], values[3]]


class GCSExactTransportV1:
    """Generation-exact reads plus create-once equal-byte retry recovery."""

    def __init__(self) -> None:
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import storage
        except Exception as exc:  # pragma: no cover - cloud dependency
            raise RuntimeError("google-cloud-storage is required") from exc
        self._client = storage.Client(
            project=cloud.FIXED_GCP_PROJECT,
            client_options=ClientOptions(
                api_endpoint=cloud.FIXED_STORAGE_ENDPOINT
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
            str(identity["uri"]),
            str(identity["generation"]),
            str(identity["sha256"]),
            int(identity["bytes"]),
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


def _write_local_create_once(path: Path, raw: bytes) -> None:
    if path.exists():
        if path.read_bytes() != raw:
            _fail("local create-once output collision differs")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def execute_environment_task_v1(
    environment: Mapping[str, str] | None = None,
    *,
    store: GCSExactTransportV1 | None = None,
    observed_command: list[str] | None = None,
) -> dict[str, object]:
    env = dict(os.environ if environment is None else environment)
    if env.get(cloud.ENABLE_ENV) != "1":
        _fail("population-crossed execution is not exactly enabled")
    inherited = sorted(set(env) & profiles.STRUCTURE_ENV_KEYS)
    if inherited:
        _fail(f"ambient inherited structure keys are forbidden: {inherited}")
    manifest_identity = _parse_identity_text(
        env.get(cloud.MANIFEST_IDENTITY_ENV, ""),
        label="population-crossed manifest identity",
    )
    task_index_raw = env.get("CLOUD_RUN_TASK_INDEX", "")
    if not task_index_raw.isdecimal() or task_index_raw.startswith("+"):
        _fail("CLOUD_RUN_TASK_INDEX must be a canonical decimal integer")
    task_index = int(task_index_raw)
    transport = GCSExactTransportV1() if store is None else store
    raw_manifest = transport.read_exact(manifest_identity)
    manifest = cloud.validate_task_manifest_v1(
        _strict_json(raw_manifest, label="population-crossed task manifest")
    )
    command = (
        observed_dispatcher_command_v1()
        if observed_command is None
        else list(observed_command)
    )
    if command != list(cloud.DISPATCHER_COMMAND):
        _fail("observed dispatcher command differs from manifest authority")
    return cloud.execute_task_v1(
        task_manifest=manifest,
        task_manifest_identity=manifest_identity,
        task_index=task_index,
        read_exact=transport.read_exact,
        publish_create_once=transport.publish_create_once,
    )


def _prepare_mode(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-file", required=True)
    parser.add_argument("--output-file", required=True)
    args = parser.parse_args(argv)
    request = _strict_json(
        Path(args.request_file).read_bytes(),
        label="population-crossed prepare request",
    )
    expected = {
        "population_task_manifest_identity",
        "population_task_result_identities",
        "output_prefix",
        "code_commit",
        "image_digest",
        "reused_job_name",
    }
    if set(request) != expected:
        _fail("population-crossed prepare request fields differ")
    store = GCSExactTransportV1()
    result = cloud.prepare_task_manifest_v1(
        population_task_manifest_identity=request[
            "population_task_manifest_identity"
        ],
        population_task_result_identities=request[
            "population_task_result_identities"
        ],
        output_prefix=str(request["output_prefix"]),
        code_commit=str(request["code_commit"]),
        image_digest=str(request["image_digest"]),
        reused_job_name=str(request["reused_job_name"]),
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    _write_local_create_once(Path(args.output_file), _canonical(result))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "prepare":
        return _prepare_mode(args[1:])
    if args == ["task"]:
        completion = execute_environment_task_v1()
        raw = _canonical(completion)
        if len(raw) > cloud.MAXIMUM_TASK_COMPLETION_BYTES:
            _fail("population-crossed task stdout exceeds its byte ceiling")
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()
        return 0
    raise SystemExit(
        "usage: ...population_crossed_cloud_v1.py "
        "task | prepare --request-file PATH --output-file PATH"
    )


if __name__ == "__main__":
    raise SystemExit(main())
