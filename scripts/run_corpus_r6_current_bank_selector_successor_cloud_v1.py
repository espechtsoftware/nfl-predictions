#!/usr/bin/env python3
"""Prepare or execute a manifest-bound 54-task selector successor batch."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
import argparse
import errno
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Final

import numpy as np

from nfl_dfs.research import (
    corpus_legal_feasibility as legal,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_selection_fold_worker_v1 as worker,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as source_manifest,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_cloud_v1 as cloud,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_process_adapter_v1 as adapter,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_runtime_v1 as child_runtime,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_rank150_dpp_mode_v1 as rank150_dpp_mode,
)
from nfl_dfs.research import lr8_later_period_source as later
from nfl_dfs.research import residual_world_columns as worlds


MAXIMUM_COMMAND_BYTES: Final = 4_096
MAXIMUM_CHILD_STDERR_BYTES: Final = 256_000


class RunCorpusR6CurrentBankSelectorSuccessorCloudV1Error(RuntimeError):
    """The manifest-bound selector successor executable failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6CurrentBankSelectorSuccessorCloudV1Error(message)


def _canonical(value: object) -> bytes:
    return contract.canonical_json_bytes_v1(value)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunCorpusR6CurrentBankSelectorSuccessorCloudV1Error(
            f"{label} is not JSON"
        ) from exc
    item = _mapping(value, label=label)
    if _canonical(item) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return contract._safe_object_identity(value, label=label)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise RunCorpusR6CurrentBankSelectorSuccessorCloudV1Error(str(exc)) from exc


def _parse_identity_text(value: str, *, label: str) -> dict[str, object]:
    if not value or len(value.encode("utf-8")) > 2_048:
        _fail(f"{label} environment is absent or oversized")
    return _identity(
        _strict_json(value.encode("utf-8"), label=label), label=label
    )


def _selector_process_mode(value: Mapping[str, object]) -> str:
    if (
        value.get("schema_version") == cloud.RANK150_DPP_TASK_MANIFEST_SCHEMA
        and value.get("selector_process_mode")
        == cloud.RANK150_DPP_SELECTOR_MODE
    ):
        return cloud.RANK150_DPP_SELECTOR_MODE
    if (
        value.get("schema_version") == cloud.TASK_MANIFEST_SCHEMA
        and "selector_process_mode" not in value
    ):
        return cloud.GROUPED_SELECTOR_MODE
    _fail("successor task manifest selector mode differs")


def _observed_dispatcher_command(raw_cmdline: bytes | None = None) -> list[str]:
    if raw_cmdline is None:
        try:
            raw = Path("/proc/self/cmdline").read_bytes()
        except OSError as exc:
            raise RunCorpusR6CurrentBankSelectorSuccessorCloudV1Error(
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
    if len(fields) != 3 or any(not row for row in fields):
        _fail("dispatcher kernel command shape differs")
    try:
        values = [row.decode("utf-8") for row in fields]
    except UnicodeDecodeError as exc:
        raise RunCorpusR6CurrentBankSelectorSuccessorCloudV1Error(
            "dispatcher kernel command is not UTF-8"
        ) from exc
    return [os.path.abspath(values[0]), values[1], values[2]]


class GCSExactTransportV1:
    """Fixed-project exact reads and create-once equal-byte recovery."""

    def __init__(self) -> None:
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import storage
        except Exception as exc:  # pragma: no cover - cloud dependency
            raise RuntimeError("google-cloud-storage is required") from exc
        self._client = storage.Client(
            project=cloud.FIXED_GCP_PROJECT,
            client_options=ClientOptions(api_endpoint=cloud.FIXED_STORAGE_ENDPOINT),
        )
        self._cache: dict[tuple[str, str, str, int], bytes] = {}
        self.observed_exact_identities: list[dict[str, object]] = []

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
        raw = blob.download_as_bytes(if_generation_match=generation, retry=None)
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("generation-exact GCS bytes differ")
        self._cache[key] = raw
        self.observed_exact_identities.append(identity)
        return raw

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if type(raw) is not bytes or not raw:
            _fail("create-once publication bytes differ")
        bucket_name, object_name = self._parts(uri)
        blob = self._client.bucket(bucket_name).blob(object_name)
        try:
            blob.upload_from_string(
                raw, content_type="application/json", if_generation_match=0,
                retry=None,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ not in {"Conflict", "PreconditionFailed"}:
                raise
            # Output-only retry recovery.  Scientific inputs remain strictly
            # generation-pinned and never use current-generation lookup.
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


def _read_json_identity(
    identity_value: object, *, store: GCSExactTransportV1, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    return _strict_json(store.read_exact(identity), label=label), identity


@contextmanager
def _readonly_anonymous_matrix_fd_v1(
    scores_value: object, descriptor_value: object,
):
    descriptor = worker._validate_matrix_descriptor_v1(descriptor_value)
    scores = np.asarray(scores_value)
    if (
        scores.dtype != np.dtype(np.float64)
        or list(scores.shape) != descriptor["shape"]
        or not scores.flags.c_contiguous
        or not np.isfinite(scores).all()
    ):
        _fail("successor sealed matrix source differs")
    matrix = np.ascontiguousarray(scores, dtype="<f8")
    raw = memoryview(matrix).cast("B")
    raw_digest = sha256()
    scientific_digest = sha256()
    scientific_digest.update(_canonical({
        "dtype": "float64-le", "shape": list(descriptor["shape"]),
    }))
    scientific_digest.update(b"\0")
    target_fd = worker.MATRIX_ANONYMOUS_FD
    try:
        writable_fd = os.memfd_create(
            worker.MATRIX_MEMFD_NAME,
            os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING,
        )
    except (AttributeError, OSError) as exc:
        raise RunCorpusR6CurrentBankSelectorSuccessorCloudV1Error(
            "successor sealed matrix memfd cannot be created"
        ) from exc
    readonly_fd: int | None = None
    target_owned = False
    try:
        offset = 0
        while offset < raw.nbytes:
            chunk = raw[offset:min(offset + worker.MATRIX_HASH_CHUNK_BYTES, raw.nbytes)]
            written = 0
            while written < chunk.nbytes:
                count = os.write(writable_fd, chunk[written:])
                if count < 1:
                    _fail("successor matrix memfd write made no progress")
                written += count
            raw_digest.update(chunk)
            scientific_digest.update(chunk)
            offset += chunk.nbytes
        if (
            offset != descriptor["raw_bytes"]
            or os.fstat(writable_fd).st_size != descriptor["raw_bytes"]
            or raw_digest.hexdigest() != descriptor["raw_sha256"]
            or scientific_digest.hexdigest() != descriptor["matrix_sha256"]
        ):
            _fail("successor matrix memfd hash/size differs")
        fcntl.fcntl(writable_fd, fcntl.F_ADD_SEALS, worker.MATRIX_REQUIRED_SEALS)
        if fcntl.fcntl(writable_fd, fcntl.F_GET_SEALS) != worker.MATRIX_REQUIRED_SEALS:
            _fail("successor matrix memfd seal set differs")
        readonly_fd = os.open(
            f"/proc/self/fd/{writable_fd}", os.O_RDONLY | os.O_CLOEXEC
        )
        os.close(writable_fd)
        writable_fd = -1
        try:
            os.fstat(target_fd)
        except OSError as exc:
            if exc.errno != errno.EBADF:
                raise
        else:
            _fail("successor fixed matrix FD is occupied")
        os.dup2(readonly_fd, target_fd, inheritable=True)
        target_owned = True
        os.close(readonly_fd)
        readonly_fd = None
        if (
            fcntl.fcntl(target_fd, fcntl.F_GET_SEALS)
            != worker.MATRIX_REQUIRED_SEALS
            or fcntl.fcntl(target_fd, fcntl.F_GETFL) & os.O_ACCMODE
            != os.O_RDONLY
            or os.readlink(f"/proc/self/fd/{target_fd}")
            != worker.MATRIX_MEMFD_LINK_TARGET
        ):
            _fail("successor inherited matrix FD authority differs")
        yield target_fd
    finally:
        if writable_fd >= 0:
            os.close(writable_fd)
        if readonly_fd is not None:
            os.close(readonly_fd)
        if target_owned:
            try:
                os.close(target_fd)
            except OSError as exc:
                if exc.errno != errno.EBADF:
                    raise


def _spawn_matrix_child_v1(
    *, request: Mapping[str, object], scores: np.ndarray,
    selector_process_mode: str,
) -> dict[str, object]:
    raw_request = _canonical(request)
    environment = dict(os.environ)
    capability = request["matrix_capability"]
    environment.pop(child_runtime.PROCESS_ORDINAL_ENV, None)
    environment.pop(rank150_dpp_mode.PROCESS_ORDINAL_ENV, None)
    if selector_process_mode == cloud.GROUPED_SELECTOR_MODE:
        environment[child_runtime.PROCESS_ORDINAL_ENV] = str(
            capability["process_ordinal"]
        )
        command = child_runtime.canonical_matrix_selector_command_v1()
        result_ceiling = adapter.FOLD_RECEIPT_BYTE_CEILING
    elif selector_process_mode == cloud.RANK150_DPP_SELECTOR_MODE:
        environment[rank150_dpp_mode.PROCESS_ORDINAL_ENV] = str(
            capability["process_ordinal"]
        )
        command = rank150_dpp_mode.canonical_matrix_selector_command_v1()
        result_ceiling = rank150_dpp_mode.FOLD_RECEIPT_BYTE_CEILING
    else:
        _fail("successor matrix child selector mode is not registered")
    with _readonly_anonymous_matrix_fd_v1(
        scores, capability["matrix_descriptor"]
    ) as matrix_fd, tempfile.TemporaryFile() as input_file:
        input_file.write(raw_request)
        input_file.seek(0)
        process = subprocess.Popen(
            command,
            stdin=input_file,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            pass_fds=(matrix_fd,),
        )
        stdout, stderr = process.communicate()
    if len(stderr) > MAXIMUM_CHILD_STDERR_BYTES:
        _fail("successor matrix child stderr exceeds ceiling")
    if process.returncode != 0:
        _fail(f"successor matrix child exited {process.returncode}")
    if not stdout or len(stdout) > result_ceiling:
        _fail("successor matrix child stdout byte count differs")
    return _strict_json(stdout, label="successor matrix child result")


def _artifact_identity(receipt_value: object) -> dict[str, object]:
    row = _mapping(receipt_value, label="world artifact receipt")
    return _identity({
        "uri": row.get("uri"),
        "generation": row.get("generation"),
        "sha256": row.get("sha256"),
        "bytes": row.get("bytes"),
    }, label="world artifact identity")


def _validate_later_source(value: Mapping[str, object]) -> dict[str, object]:
    expected = value.get("freeze_sha256")
    if type(expected) is not str:
        _fail("later source lacks its frozen SHA-256")
    return later.validate_source_freeze(
        value, expected_freeze_sha256=expected
    )


def _players(catalog: object) -> tuple[object, ...]:
    if not isinstance(catalog, list) or not catalog:
        _fail("later source catalog differs")
    rows = tuple(worlds.PlayerSpec.from_mapping(row) for row in catalog)
    if tuple(row.player_id for row in rows) != tuple(
        sorted(row.player_id for row in rows)
    ):
        _fail("later source catalog order differs")
    return rows


def _load_slate_artifacts_v1(
    *,
    bundle: Mapping[str, object],
    store: GCSExactTransportV1,
) -> tuple[tuple[object, ...], dict[str, np.ndarray]]:
    projection = bundle["fold_projections"][0]
    source_raw = store.read_exact(projection["later_source_identity"])
    source = _validate_later_source(
        _strict_json(source_raw, label="later source")
    )
    matches = [
        row for row in source.get("slates", [])
        if isinstance(row, Mapping) and row.get("slate_id") == bundle["slate_id"]
    ]
    if len(matches) != 1:
        _fail("successor slate is absent or repeated in later source")
    slate = dict(matches[0])
    players = _players(slate.get("catalog"))
    player_ids = tuple(row.player_id for row in players)
    receipt_rows = slate.get("artifact_receipts")
    if (
        not isinstance(receipt_rows, list)
        or len(receipt_rows) != contract.FOLDS_PER_SLATE
    ):
        _fail("successor world artifact receipt lattice differs")
    receipts = {str(row["block"]): dict(row) for row in receipt_rows}
    if list(receipts) != list(contract.WORLD_BLOCKS):
        _fail("successor world artifact receipt order differs")
    expected_worlds = projection["world_artifact_identities"]
    aligned: dict[str, np.ndarray] = {}
    for block in contract.WORLD_BLOCKS:
        identity = _artifact_identity(receipts[block])
        if identity != expected_worlds[f"world_artifact_{block.lower()}"]:
            _fail("successor source/projection world identity differs")
        loaded = later.load_artifact_worlds(receipts[block], store.read_exact(identity))
        loaded_ids = tuple(str(value) for value in loaded.player_ids)
        draws = np.asarray(loaded.player_draws)
        if (
            loaded.block != block
            or set(loaded_ids) != set(player_ids)
            or len(set(loaded_ids)) != len(loaded_ids)
            or draws.dtype != np.dtype(np.float32)
            or draws.shape != (len(loaded_ids), contract.WORLDS_PER_BLOCK)
            or not np.isfinite(draws).all()
        ):
            _fail("successor world artifact matrix authority differs")
        ordinal = {player_id: index for index, player_id in enumerate(loaded_ids)}
        aligned[block] = np.ascontiguousarray(
            draws[[ordinal[player_id] for player_id in player_ids]],
            dtype=np.float32,
        )
    return players, aligned


def _open_dispatch_authorities_v1(
    *,
    manifest_identity: Mapping[str, object],
    task_index: int,
    store: GCSExactTransportV1,
) -> dict[str, object]:
    manifest_raw = store.read_exact(manifest_identity)
    manifest_value = _strict_json(
        manifest_raw, label="successor task manifest"
    )
    if manifest_value.get("task_manifest_sha256") != contract.canonical_sha256_v1({
        key: row for key, row in manifest_value.items()
        if key != "task_manifest_sha256"
    }):
        _fail("successor task manifest self hash differs")
    source_value, source_identity = _read_json_identity(
        manifest_value.get("source_control_task_manifest_identity"),
        store=store,
        label="source control task manifest",
    )
    source = source_manifest.validate_task_manifest_v1(source_value)
    if source_identity != manifest_value.get("source_control_task_manifest_identity"):
        _fail("source control manifest identity differs")
    bootstrap_value, bootstrap_identity = _read_json_identity(
        manifest_value.get("bootstrap_identity"),
        store=store,
        label="successor bootstrap",
    )
    bootstrap = cloud.validate_bootstrap_v1(bootstrap_value)
    manifest = cloud.validate_task_manifest_v1(
        manifest_value,
        source_task_manifest=source,
        bootstrap=bootstrap,
    )
    selector_process_mode = _selector_process_mode(manifest)
    if (
        manifest_identity["uri"]
        != f"{manifest['output_prefix']}authorities/task-manifest.json"
        or manifest["task_count"] != cloud.TASK_COUNT
        or not 0 <= task_index < cloud.TASK_COUNT
    ):
        _fail("successor task manifest URI/task lattice differs")
    binding = manifest["task_bindings"][task_index]
    source_task = source["task_bindings"][task_index]
    if (
        binding["source_task_binding_sha256"]
        != source_task["task_binding_sha256"]
        or binding["source_task_science_binding_sha256"]
        != source_task["task_science_binding_sha256"]
        or binding["source_request_sha256"] != source_task["request_sha256"]
    ):
        _fail("successor/source task binding differs")
    return {
        "manifest": manifest,
        "source_manifest": source,
        "bootstrap": bootstrap,
        "bootstrap_identity": bootstrap_identity,
        "binding": binding,
        "source_task": source_task,
        "selector_process_mode": selector_process_mode,
    }


def _load_task_authorities_v1(
    *,
    opened: Mapping[str, object],
    store: GCSExactTransportV1,
) -> dict[str, object]:
    manifest = opened["manifest"]
    selector_process_mode = str(opened["selector_process_mode"])
    binding = opened["binding"]
    source_task = opened["source_task"]
    source = int(binding["source_ordinal"])
    request = source_task["request"]
    launch_identity = _identity(
        manifest["run_authorization_identity"],
        label="successor run authorization",
    )
    launch_raw = store.read_exact(launch_identity)
    launch_body = _strict_json(launch_raw, label="successor run authorization")
    authorization: dict[str, object] | None = None
    if launch_body.get("schema_version") in {
        cloud.RUN_AUTHORIZATION_SCHEMA,
        cloud.RANK150_DPP_RUN_AUTHORIZATION_SCHEMA,
    }:
        authorization = cloud.validate_run_authorization_v1(launch_body)
        if (
            authorization["source_task_manifest_identity"]
            != manifest["source_control_task_manifest_identity"]
            or authorization["output_prefix"] != manifest["output_prefix"]
            or authorization["code_commit"] != manifest["code_commit"]
            or authorization["image_digest"] != manifest["image_digest"]
            or (
                authorization.get("selector_process_mode")
                == cloud.RANK150_DPP_SELECTOR_MODE
            )
            != (
                selector_process_mode == cloud.RANK150_DPP_SELECTOR_MODE
            )
        ):
            _fail("successor run authorization differs from task manifest")
    design_value, design_identity = _read_json_identity(
        request["design_identity"], store=store, label="source design"
    )
    topology_value, topology_identity = _read_json_identity(
        request["topology_identity"], store=store, label="source topology"
    )
    bundle_value, bundle_identity = _read_json_identity(
        request["projection_bundle_identity"],
        store=store,
        label="source projection bundle",
    )
    try:
        design = contract.validate_design_authority_v1(
            design_value, publication_identity=design_identity
        )
        topology = contract.validate_result_topology_v1(topology_value)
        contract._bind_canonical_body_to_identity_v1(
            topology, topology_identity, label="source topology"
        )
        bundle = contract.validate_projection_bundle_authority_v1(
            bundle_value,
            publication_identity=bundle_identity,
            topology=topology,
            topology_identity=topology_identity,
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise RunCorpusR6CurrentBankSelectorSuccessorCloudV1Error(
            f"successor source authority differs: {exc}"
        ) from exc
    if (
        design["topology"] != topology
        or bundle["source_ordinal"] != source
        or bundle_identity != binding["projection_bundle_identity"]
    ):
        _fail("successor design/topology/bundle binding differs")
    slate_budget_value, slate_budget_identity = _read_json_identity(
        binding["slate_process_budget_identity"],
        store=store,
        label="successor slate process budget",
    )
    slate_budget = cloud.validate_slate_process_budget_v1(slate_budget_value)
    source_budgets: list[dict[str, object]] = []
    successor_budgets: list[dict[str, object]] = []
    for fold in range(contract.FOLDS_PER_SLATE):
        source_budget_value, source_budget_identity = _read_json_identity(
            binding["source_process_budget_identities"][fold],
            store=store,
            label=f"source process budget[{fold}]",
        )
        successor_budget_value, successor_budget_identity = _read_json_identity(
            binding["successor_process_budget_identities"][fold],
            store=store,
            label=f"successor process budget[{fold}]",
        )
        try:
            source_budget = contract.validate_process_budget_v1(
                source_budget_value
            )
            expected_source = contract.compile_process_budget_v1(
                process_role="broad-fold-selector",
                projection_bundle=bundle,
                projection_bundle_identity=bundle_identity,
                topology=topology,
                topology_identity=topology_identity,
                source_ordinal=source,
                fold_ordinal=fold,
            )
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise RunCorpusR6CurrentBankSelectorSuccessorCloudV1Error(
                f"source process budget[{fold}] differs: {exc}"
            ) from exc
        if _canonical(source_budget) != _canonical(expected_source):
            _fail("source process budget exact replay differs")
        if selector_process_mode == cloud.GROUPED_SELECTOR_MODE:
            successor_budget = adapter.validate_successor_process_budget_v1(
                successor_budget_value,
                source_process_budget=source_budget,
                source_process_budget_identity=source_budget_identity,
                source_projection=bundle["fold_projections"][fold],
            )
        else:
            successor_budget = rank150_dpp_mode.validate_process_budget_v1(
                successor_budget_value,
                source_process_budget=source_budget,
                source_process_budget_identity=source_budget_identity,
                source_projection=bundle["fold_projections"][fold],
            )
        source_budgets.append({
            "body": source_budget, "identity": source_budget_identity
        })
        successor_budgets.append({
            "body": successor_budget, "identity": successor_budget_identity
        })
    return {
        **dict(opened),
        "design": design,
        "topology": topology,
        "bundle": bundle,
        "bundle_identity": bundle_identity,
        "launch_identity": launch_identity,
        "run_authorization": authorization,
        "slate_budget": slate_budget,
        "slate_budget_identity": slate_budget_identity,
        "source_budgets": source_budgets,
        "successor_budgets": successor_budgets,
    }


def _run_five_folds_v1(
    *, authorities: Mapping[str, object], store: GCSExactTransportV1,
) -> list[dict[str, object]]:
    bundle = authorities["bundle"]
    selector_process_mode = str(authorities["selector_process_mode"])
    source = int(authorities["binding"]["source_ordinal"])
    players, draws_by_block = _load_slate_artifacts_v1(
        bundle=bundle, store=store
    )
    rosters_by_fold = [
        [tuple(row["roster_player_ids"]) for row in projection["candidates"]]
        for projection in bundle["fold_projections"]
    ]
    receipts: list[dict[str, object]] = []
    for fold, projection in enumerate(bundle["fold_projections"]):
        training_blocks = list(projection["training_blocks"])
        if training_blocks != [
            block for block in contract.WORLD_BLOCKS
            if block != contract.WORLD_BLOCKS[fold]
        ]:
            _fail("successor fold training-block isolation differs")
        player_draws = np.ascontiguousarray(
            np.concatenate(
                [draws_by_block[block] for block in training_blocks], axis=1
            ),
            dtype=np.float32,
        )
        scores = np.asarray(legal.cross_score_full_union(
            players,
            player_draws,
            rosters_by_fold[fold],
            expected_worlds=4 * contract.WORLDS_PER_BLOCK,
        ))
        if (
            scores.dtype != np.dtype(np.float64)
            or list(scores.shape) != projection["expected_training_score_shape"]
            or not np.isfinite(scores).all()
            or legal._score_matrix_sha256(scores)
            != projection["expected_training_score_matrix_sha256"]
            or contract._float64_matrix_sha256_v1(
                scores, label="successor broker score matrix"
            ) != projection["expected_training_score_matrix_sha256"]
        ):
            _fail("successor four-block cross-scored matrix differs")
        source_budget = authorities["source_budgets"][fold]
        successor_budget = authorities["successor_budgets"][fold]
        samples = contract.deterministic_equal_count_samples_from_projection_v1(
            projection, phase=contract.BROAD_SCREEN_PHASE
        )
        capability = worker.build_matrix_capability_v1(
            phase=contract.BROAD_SCREEN_PHASE,
            source_ordinal=source,
            fold_ordinal=fold,
            projection=projection,
            process_budget=source_budget["body"],
            training_score_matrix=scores,
            samples=samples,
            nominee_keys=None,
        )
        child_request = cloud.build_matrix_child_request_v1(
            source_process_budget=source_budget["body"],
            source_process_budget_identity=source_budget["identity"],
            successor_process_budget=successor_budget["body"],
            successor_process_budget_identity=successor_budget["identity"],
            matrix_capability=capability,
            launch_intent_identity=authorities["launch_identity"],
            selector_process_mode=selector_process_mode,
        )
        receipt = _spawn_matrix_child_v1(
            request=child_request,
            scores=scores,
            selector_process_mode=selector_process_mode,
        )
        receipt_hash_field = (
            "successor_fold_receipt_sha256"
            if selector_process_mode == cloud.GROUPED_SELECTOR_MODE
            else "rank150_dpp_fold_receipt_sha256"
        )
        budget_identity_field = (
            "successor_process_budget_identity"
            if selector_process_mode == cloud.GROUPED_SELECTOR_MODE
            else "process_budget_identity"
        )
        if (
            receipt.get(receipt_hash_field)
            != contract.canonical_sha256_v1({
                key: row for key, row in receipt.items()
                if key != receipt_hash_field
            })
            or receipt.get("source_ordinal") != source
            or receipt.get("fold_ordinal") != fold
            or receipt.get(budget_identity_field)
            != successor_budget["identity"]
        ):
            _fail("successor matrix child fold receipt differs")
        receipts.append(receipt)
        del player_draws, scores, capability, child_request
    return receipts


def _identity_key(value: object) -> tuple[str, str, str, int]:
    identity = _identity(value, label="identity ledger row")
    return (
        str(identity["uri"]), str(identity["generation"]),
        str(identity["sha256"]), int(identity["bytes"]),
    )


def execute_dispatch_once_v1(
    *,
    manifest_identity: Mapping[str, object],
    dispatcher_runtime_evidence: Mapping[str, object],
    store: GCSExactTransportV1,
) -> dict[str, object]:
    runtime = cloud.validate_dispatcher_runtime_evidence_v1(
        dispatcher_runtime_evidence
    )
    task_index = int(runtime["task_index"])
    opened = _open_dispatch_authorities_v1(
        manifest_identity=manifest_identity,
        task_index=task_index,
        store=store,
    )
    manifest = opened["manifest"]
    manifest_mode = str(opened["selector_process_mode"])
    runtime_mode = (
        cloud.RANK150_DPP_SELECTOR_MODE
        if runtime.get("selector_process_mode")
        == cloud.RANK150_DPP_SELECTOR_MODE
        else cloud.GROUPED_SELECTOR_MODE
    )
    if (
        runtime_mode != manifest_mode
        or runtime["code_commit"] != manifest["code_commit"]
        or runtime["image_digest"] != manifest["image_digest"]
    ):
        _fail("successor dispatcher runtime differs from manifest bootstrap")
    authorities = _load_task_authorities_v1(opened=opened, store=store)
    run_authorization = authorities.get("run_authorization")
    if (
        isinstance(run_authorization, Mapping)
        and runtime["job_name"] != run_authorization.get("reused_job_name")
    ):
        _fail("successor runtime job differs from run authorization")
    fold_receipts = _run_five_folds_v1(
        authorities=authorities, store=store
    )
    budget = authorities["slate_budget"]
    expected_reads = {
        _identity_key(row["identity"]) for row in budget["read_allowlist"]
    }
    governing = {
        _identity_key(manifest_identity),
        _identity_key(authorities["slate_budget_identity"]),
    }
    observed_reads = {
        _identity_key(row) for row in store.observed_exact_identities
    } - governing
    if observed_reads != expected_reads:
        _fail("successor dispatcher exact read ledger differs from slate budget")
    slate_result = cloud.build_slate_result_v1(
        task_manifest=manifest,
        task_manifest_identity=manifest_identity,
        task_binding=authorities["binding"],
        bootstrap=authorities["bootstrap"],
        slate_process_budget=budget,
        slate_process_budget_identity=authorities["slate_budget_identity"],
        fold_receipts=fold_receipts,
        dispatcher_runtime_evidence=runtime,
    )
    raw_result = _canonical(slate_result)
    write = budget["write_allowlist"][0]
    if (
        write["uri"] != authorities["binding"]["result_uri"]
        or len(raw_result) > write["max_bytes"]
    ):
        _fail("successor result publication differs from exact slate budget")
    result_identity = store.publish_create_once(write["uri"], raw_result)
    return cloud.build_task_result_envelope_v1(
        slate_result=slate_result,
        slate_result_identity=result_identity,
    )


def _write_local_create_once(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if path.read_bytes() != raw:
            _fail("local create-once result collision differs")


def _prepare_mode(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-file", required=True)
    parser.add_argument("--output-file", required=True)
    args = parser.parse_args(argv)
    request = _strict_json(
        Path(args.request_file).read_bytes(), label="successor prepare request"
    )
    common_fields = {
        "source_task_manifest_identity", "output_prefix", "code_commit",
        "image_digest",
    }
    selector_process_mode = str(request.get(
        "selector_process_mode", cloud.GROUPED_SELECTOR_MODE
    ))
    permitted = {
        frozenset(common_fields | {"run_authorization_identity"}),
        frozenset(common_fields | {"reused_job_name"}),
    }
    if selector_process_mode == cloud.RANK150_DPP_SELECTOR_MODE:
        permitted = {
            frozenset(set(fields) | {"selector_process_mode"})
            for fields in permitted
        }
    elif selector_process_mode != cloud.GROUPED_SELECTOR_MODE:
        _fail("successor prepare selector mode is not registered")
    if frozenset(request) not in permitted:
        _fail("successor prepare request fields differ")
    store = GCSExactTransportV1()
    result = cloud.prepare_task_manifest_v1(
        source_task_manifest_identity=request["source_task_manifest_identity"],
        output_prefix=str(request["output_prefix"]),
        code_commit=str(request["code_commit"]),
        image_digest=str(request["image_digest"]),
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
        run_authorization_identity=request.get("run_authorization_identity"),
        reused_job_name=(
            str(request["reused_job_name"])
            if "reused_job_name" in request
            else None
        ),
        selector_process_mode=selector_process_mode,
    )
    _write_local_create_once(Path(args.output_file), _canonical(result))
    return 0


def _dispatch_mode() -> int:
    command = _observed_dispatcher_command()
    runtime = cloud.build_dispatcher_runtime_evidence_v1(
        environ=os.environ,
        observed_command=command,
        pid=os.getpid(),
        parent_pid=os.getppid(),
    )
    manifest_identity = _parse_identity_text(
        os.environ.get(cloud.MANIFEST_IDENTITY_ENV, ""),
        label="successor task manifest identity",
    )
    store = GCSExactTransportV1()
    envelope = execute_dispatch_once_v1(
        manifest_identity=manifest_identity,
        dispatcher_runtime_evidence=runtime,
        store=store,
    )
    raw = _canonical(envelope)
    if len(raw) > cloud.MAXIMUM_TASK_RESULT_ENVELOPE_BYTES:
        _fail("successor task result stdout exceeds ceiling")
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "prepare":
        return _prepare_mode(args[1:])
    if args:
        raise SystemExit(
            "usage: ...selector_successor_cloud_v1.py "
            "[prepare --request-file PATH --output-file PATH]"
        )
    return _dispatch_mode()


if __name__ == "__main__":
    raise SystemExit(main())
