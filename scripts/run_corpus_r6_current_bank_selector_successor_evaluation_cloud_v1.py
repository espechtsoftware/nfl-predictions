#!/usr/bin/env python3
"""Execute the successor held-out evaluator or its terminal aggregate."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

import numpy as np

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_evaluation_v1 as scoring_primitives,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_evaluation_cloud_v1 as cloud,
)


class SuccessorEvaluationEntrypointV1Error(RuntimeError):
    """The guarded successor evaluation entrypoint failed closed."""


def _fail(message: str) -> None:
    raise SuccessorEvaluationEntrypointV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SuccessorEvaluationEntrypointV1Error(f"{label} is not JSON") from exc
    body = _mapping(value, label=label)
    if contract.canonical_json_bytes_v1(body) != raw:
        _fail(f"{label} is not canonical JSON")
    return body


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return contract._safe_object_identity(value, label=label)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise SuccessorEvaluationEntrypointV1Error(str(exc)) from exc


def _identity_from_environment(key: str) -> dict[str, object]:
    value = os.environ.get(key, "")
    if not value or len(value.encode("utf-8")) > 2_048:
        _fail(f"{key} is absent or oversized")
    return _identity(
        _strict_json(value.encode("utf-8"), label=key), label=key
    )


def _observed_command() -> list[str]:
    try:
        raw = Path("/proc/self/cmdline").read_bytes()
    except OSError as exc:
        raise SuccessorEvaluationEntrypointV1Error(
            "kernel command is unavailable"
        ) from exc
    if not raw or not raw.endswith(b"\0") or len(raw) > 8_192:
        _fail("kernel command bytes differ")
    parts = raw[:-1].split(b"\0")
    if len(parts) != 4 or any(not value for value in parts):
        _fail("kernel command shape differs")
    try:
        command = [value.decode("utf-8") for value in parts]
    except UnicodeDecodeError as exc:
        raise SuccessorEvaluationEntrypointV1Error(
            "kernel command is not UTF-8"
        ) from exc
    command[0] = os.path.abspath(command[0])
    return command


class GCSExactTransportV1:
    """Fixed-project generation reads and create-once exact publication."""

    def __init__(self) -> None:
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import storage
        except Exception as exc:  # pragma: no cover - cloud dependency
            raise SuccessorEvaluationEntrypointV1Error(
                "google-cloud-storage is required"
            ) from exc
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
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )
        if key in self._cache:
            return self._cache[key]
        bucket, name = self._parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        blob = self._client.bucket(bucket).blob(name, generation=generation)
        raw = blob.download_as_bytes(if_generation_match=generation, retry=None)
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
            _fail("create-once bytes differ")
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        try:
            blob.upload_from_string(
                raw, content_type="application/json",
                if_generation_match=0, retry=None,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ not in {"Conflict", "PreconditionFailed"}:
                raise
            existing = self._client.bucket(bucket).blob(name)
            existing.reload(retry=None)
            if existing.generation is None:
                _fail("create-once collision lacks generation")
            identity = {
                "uri": uri,
                "generation": str(existing.generation),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
            if self.read_exact(identity) != raw:
                _fail("create-once collision bytes differ")
            return identity
        if blob.generation is None:
            _fail("create-once publication lacks generation")
        identity = {
            "uri": uri,
            "generation": str(blob.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if self.read_exact(identity) != raw:
            _fail("create-once publication exact reopen differs")
        return identity


def _score_heldout(
    *, projection: Mapping[str, object], later_source_body: Mapping[str, object],
    heldout_artifact_identity: Mapping[str, object], raw_artifact: bytes,
) -> np.ndarray:
    """Use only the control's solver-free NPZ decoding/scoring primitives."""
    try:
        slate, players = scoring_primitives._later_slate_v1(
            later_source_body, slate_id=str(projection["slate_id"])
        )
        receipt = scoring_primitives._artifact_receipt_v1(
            slate,
            block=str(projection["heldout_block"]),
            expected_identity=heldout_artifact_identity,
        )
        return scoring_primitives._score_heldout_fold_v1(
            projection=projection,
            players=players,
            receipt=receipt,
            raw_artifact=raw_artifact,
            load_artifact_worlds=scoring_primitives._load_artifact_worlds_v1,
            cross_score=scoring_primitives._cross_score_full_union_v1,
        )
    except scoring_primitives.CorpusR6CurrentBankCrossedScreenEvaluationV1Error as exc:
        raise SuccessorEvaluationEntrypointV1Error(
            f"heldout scoring primitive failed: {exc}"
        ) from exc


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {
        cloud.MODE_EVALUATE, cloud.MODE_AGGREGATE,
    }:
        _fail("exactly one fixed runtime mode is required")
    mode = sys.argv[1]
    store = GCSExactTransportV1()
    identity_key = (
        cloud.MANIFEST_IDENTITY_ENV
        if mode == cloud.MODE_EVALUATE
        else cloud.TERMINAL_MANIFEST_IDENTITY_ENV
    )
    manifest_identity = _identity_from_environment(identity_key)
    manifest = _strict_json(
        store.read_exact(manifest_identity), label=f"{mode} manifest"
    )
    runtime = cloud.derive_runtime_evidence_v1(
        mode=mode,
        environ=os.environ,
        observed_command=_observed_command(),
        pid=os.getpid(),
        parent_pid=os.getppid(),
    )
    if mode == cloud.MODE_EVALUATE:
        envelope = cloud.run_evaluator_task_v1(
            task_manifest=manifest,
            task_manifest_identity=manifest_identity,
            observed_runtime=runtime,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
            score_heldout=_score_heldout,
        )
    else:
        envelope = cloud.run_terminal_task_v1(
            terminal_manifest=manifest,
            terminal_manifest_identity=manifest_identity,
            observed_runtime=runtime,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
    sys.stdout.buffer.write(contract.canonical_json_bytes_v1(envelope) + b"\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        sys.stderr.write(f"{exc.__class__.__name__}: {exc}\n")
        raise SystemExit(1) from None
