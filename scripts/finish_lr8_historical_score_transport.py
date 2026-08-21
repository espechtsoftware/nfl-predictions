#!/usr/bin/env python3
"""Fail-closed transport/harvest authority for the two LR8 score reads.

The executable score suppliers remain ``run_lr8_label_score_map.py`` and
``run_lr8_later_period_evaluation.py``.  This module only binds their shared
Cloud Run transport, performs terminal-first generation-pinned harvest, and
replays the validators exported by those suppliers.
"""

from __future__ import annotations

import argparse
import base64
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import Any, Final


ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT / "src", ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import finish_lr8_full_source_shards as full_finish  # noqa: E402
import run_lr8_label_score_map as earlier_runner  # noqa: E402
import run_lr8_later_period_evaluation as later_runner  # noqa: E402
from nfl_dfs.research import lr8_label_fit_adapter as fit_adapter  # noqa: E402
from nfl_dfs.research import lr8_label_score_map as earlier_supplier  # noqa: E402
from nfl_dfs.research import lr8_later_period_evaluation as later_supplier  # noqa: E402


PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
JOB: Final = "atlas-md-prefix-r4-smoke"
JOB_UID: Final = "51545eb0-59e4-424e-91c9-98dd318285f4"
SERVICE_ACCOUNT: Final = "817589974517-compute@developer.gserviceaccount.com"
CPU: Final = "8"
MEMORY: Final = "32Gi"
TIMEOUT_SECONDS: Final = "21600"
LEASE_TMP: Final = "/tmp/lr8-historical-outcome-lease.json"
VERSION: Final = "lr8-shared-historical-score-transport-v1"
LABEL_FIT_HANDOFF_SCHEMA: Final = "lr8-label-fit-handoff-v1"
LABEL_FIT_LOCAL_RECEIPT_SCHEMA: Final = "lr8-label-fit-local-receipt-v1"
_COMMIT = re.compile(r"[0-9a-f]{40}")
_BUILD = re.compile(r"[0-9A-Za-z-]{8,80}")
_GENERATION = re.compile(r"[1-9][0-9]*")
_SHA = re.compile(r"[0-9a-f]{64}")
_IMAGE = re.compile(
    r"us-central1-docker\.pkg\.dev/nfl-predictions-503414/"
    r"nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}"
)
_EXECUTION = re.compile(rf"{re.escape(JOB)}-[a-z0-9]{{5}}")
_SAFE_GCS = re.compile(r"gs://[A-Za-z0-9._-]+/[A-Za-z0-9._/-]+")
_REQUIRED_BUILD_SMOKES: Final = (
    "python scripts/run_lr8_label_score_map.py --help >/dev/null",
    "python scripts/run_lr8_later_period_evaluation.py --help >/dev/null",
)


class LR8HistoricalTransportError(RuntimeError):
    """A shared historical-score transport invariant failed closed."""


@dataclass(frozen=True, slots=True)
class ModeSpec:
    name: str
    run_id: str
    runner: str
    enabled_env: str
    output_prefix: str
    output_names: tuple[str, ...]
    input_flag: str

    @property
    def out(self) -> Path:
        return ROOT / "reports/lr8-historical-score-runs" / self.run_id

    @property
    def output_uris(self) -> tuple[str, ...]:
        return tuple(f"{self.output_prefix}/{name}" for name in self.output_names)

    @property
    def governance_prefix(self) -> str:
        return (
            "gs://nfl-predictions-503414-raw/research-governance/"
            f"lr8-historical-score-transport/{self.run_id}"
        )

    @property
    def launch_claim_uri(self) -> str:
        return f"{self.governance_prefix}/launch-job-use-claim.json"

    @property
    def release_authority_uri(self) -> str:
        return f"{self.governance_prefix}/lease-release-authority.json"

    @property
    def release_completion_uri(self) -> str:
        return f"{self.governance_prefix}/lease-release-completion.json"


MODES: Final = {
    "earlier": ModeSpec(
        name="earlier",
        run_id="20260821-lr8-label-score-map-v1",
        runner="scripts/run_lr8_label_score_map.py",
        enabled_env=earlier_runner.ENABLED_ENV,
        output_prefix=(
            "gs://nfl-predictions-503414-raw/research/"
            "lr8-authoritative-label-score-map/"
            "20260821-lr8-label-score-map-v1"
        ),
        output_names=(
            "label-read-attempt.json",
            "authoritative-score-source.json",
            "authoritative-score-map.json",
            "label-fit-freeze.json",
        ),
        input_flag="training-source",
    ),
    "later": ModeSpec(
        name="later",
        run_id="20260821-lr8-later-period-v1",
        runner="scripts/run_lr8_later_period_evaluation.py",
        enabled_env=later_runner.ENABLED_ENV,
        output_prefix=(
            "gs://nfl-predictions-503414-raw/research/"
            "lr8-later-period-evaluation/20260821-lr8-later-period-v1"
        ),
        output_names=(
            "later-period-read-attempt.json",
            "later-period-player-score-source.json",
            "later-period-evaluation.json",
        ),
        input_flag="book-freeze",
    ),
}


def _mode(value: str) -> ModeSpec:
    try:
        return MODES[value]
    except KeyError as exc:
        raise LR8HistoricalTransportError("historical-score mode differs") from exc


def canonical_json(value: object) -> bytes:
    try:
        return (
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise LR8HistoricalTransportError("value is not canonical JSON") from exc


def strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    def reject_constant(value: str) -> None:
        raise ValueError(value)

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(key)
            result[key] = value
        return result

    try:
        value = json.loads(
            raw, object_pairs_hook=unique, parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise LR8HistoricalTransportError(f"{label} is not strict JSON") from exc
    if not isinstance(value, dict):
        raise LR8HistoricalTransportError(f"{label} must be a JSON object")
    return value


def _load(path: Path, *, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise LR8HistoricalTransportError(f"{label} file is absent")
    try:
        return strict_json(path.read_bytes(), label=label)
    except OSError as exc:
        raise LR8HistoricalTransportError(f"{label} file is unreadable") from exc


def _write_once(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != raw:
            raise LR8HistoricalTransportError(f"immutable local file differs: {path}")


def _digest(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise LR8HistoricalTransportError(f"{label} differs")
    return value


def _exact_int(value: object, *, label: str) -> int:
    if isinstance(value, bool):
        raise LR8HistoricalTransportError(f"{label} differs")
    try:
        result = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise LR8HistoricalTransportError(f"{label} differs") from exc
    if str(value) != str(result) or result < 0:
        raise LR8HistoricalTransportError(f"{label} differs")
    return result


def input_pin(
    *, uri: str, generation: str, sha256_value: str, manifest_sha256: str,
) -> dict[str, str]:
    if (
        _SAFE_GCS.fullmatch(uri) is None
        or ".." in uri.removeprefix("gs://").split("/")
        or _GENERATION.fullmatch(generation) is None
    ):
        raise LR8HistoricalTransportError("input object identity differs")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": _digest(sha256_value, label="input object hash"),
        "manifest_sha256": _digest(
            manifest_sha256, label="input manifest hash"
        ),
    }


def _receipt(
    *, uri: str, generation: str, raw: bytes, create_only: bool = False,
) -> dict[str, object]:
    result: dict[str, object] = {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    if create_only:
        result["create_only"] = True
    return result


def _create_only_receipt(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "uri", "generation", "sha256", "bytes", "create_only",
    }:
        raise LR8HistoricalTransportError(f"{label} receipt differs")
    uri = value.get("uri")
    generation = value.get("generation")
    if (
        not isinstance(uri, str)
        or _SAFE_GCS.fullmatch(uri) is None
        or not isinstance(generation, str)
        or _GENERATION.fullmatch(generation) is None
        or _SHA.fullmatch(str(value.get("sha256"))) is None
        or _exact_int(value.get("bytes"), label=f"{label} bytes") < 1
        or value.get("create_only") is not True
    ):
        raise LR8HistoricalTransportError(f"{label} receipt differs")
    return dict(value)


def _lease_contract(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {"lease", "object"}:
        raise LR8HistoricalTransportError("historical lease receipt differs")
    body = value["lease"]
    receipt = value["object"]
    if not isinstance(body, Mapping) or not isinstance(receipt, Mapping):
        raise LR8HistoricalTransportError("historical lease receipt differs")
    return {"body": dict(body), "object_receipt": dict(receipt)}


def _default_script(mode: ModeSpec) -> str:
    return (
        f"echo LR8_HISTORICAL_SCORE_TRANSPORT_DISABLED_{mode.name.upper()} >&2; "
        "exit 78"
    )


def _configured_env(
    *, mode: ModeSpec, code_sha: str, build_id: str, image: str,
) -> dict[str, str]:
    return {
        "ANALYSIS_IMAGE": image,
        "CODE_SHA": code_sha,
        "LR8_BUILD_ID": build_id,
        "LR8_HISTORICAL_SCORE_TRANSPORT_MODE": mode.name,
        "LR8_HISTORICAL_SCORE_TRANSPORT_RUN_ID": mode.run_id,
    }


def _job_parts(value: Mapping[str, object]) -> tuple[Mapping[str, object], Mapping[str, object]]:
    try:
        outer = value["spec"]["template"]["spec"]  # type: ignore[index]
        task = full_finish._task_spec(value)  # noqa: SLF001
    except (KeyError, TypeError, full_finish.LR8FullSourceFinishError) as exc:
        raise LR8HistoricalTransportError("Cloud Run job structure differs") from exc
    if not isinstance(outer, Mapping):
        raise LR8HistoricalTransportError("Cloud Run job structure differs")
    return outer, task


def _job_generation(value: Mapping[str, object]) -> str:
    try:
        return full_finish._job_generation(value)  # noqa: SLF001
    except full_finish.LR8FullSourceFinishError as exc:
        raise LR8HistoricalTransportError(str(exc)) from exc


def _job_spec_sha(value: Mapping[str, object]) -> str:
    spec = value.get("spec")
    if not isinstance(spec, Mapping) or not spec:
        raise LR8HistoricalTransportError("Cloud Run job spec differs")
    return sha256(canonical_json(spec)).hexdigest()


def validate_configured_job(
    value: Mapping[str, object], *, mode: ModeSpec, code_sha: str,
    build_id: str, image: str, generation: str | None = None,
    spec_sha256: str | None = None,
) -> None:
    try:
        full_finish._job_identity(value, job=JOB, job_uid=JOB_UID)  # noqa: SLF001
    except full_finish.LR8FullSourceFinishError as exc:
        raise LR8HistoricalTransportError(str(exc)) from exc
    observed_generation = _job_generation(value)
    observed_spec = _job_spec_sha(value)
    if (
        generation is not None and observed_generation != generation
    ) or (spec_sha256 is not None and observed_spec != spec_sha256):
        raise LR8HistoricalTransportError("configured job generation/spec differs")
    outer, task = _job_parts(value)
    containers = task.get("containers")
    if (
        not isinstance(containers, list)
        or len(containers) != 1
        or not isinstance(containers[0], Mapping)
    ):
        raise LR8HistoricalTransportError("configured job container differs")
    container = containers[0]
    env_rows = container.get("env", [])
    if not isinstance(env_rows, list) or any(
        not isinstance(row, Mapping)
        or set(row) != {"name", "value"}
        or not isinstance(row["name"], str)
        or not isinstance(row["value"], str)
        for row in env_rows
    ):
        raise LR8HistoricalTransportError("configured job environment differs")
    env = {str(row["name"]): str(row["value"]) for row in env_rows}
    if len(env) != len(env_rows):
        raise LR8HistoricalTransportError("configured job environment repeats")
    if (
        _exact_int(outer.get("taskCount"), label="job task count") != 1
        or _exact_int(outer.get("parallelism"), label="job parallelism") != 1
        or _exact_int(task.get("maxRetries"), label="job retries") != 0
        or container.get("image") != image
        or container.get("command") != ["bash"]
        or container.get("args") != ["-ceu", _default_script(mode)]
        or env != _configured_env(
            mode=mode, code_sha=code_sha, build_id=build_id, image=image,
        )
        or task.get("serviceAccountName") != SERVICE_ACCOUNT
        or container.get("resources", {}).get("limits")
        != {"cpu": CPU, "memory": MEMORY}
        or str(task.get("timeoutSeconds")) != TIMEOUT_SECONDS
        or container.get("workingDir", "") != ""
        or container.get("volumeMounts", []) != []
        or container.get("startupProbe") not in (None, {})
        or task.get("volumes", []) != []
    ):
        raise LR8HistoricalTransportError("configured job executable contract differs")


def _completion_state(value: Mapping[str, object]) -> str:
    status = value.get("status")
    if not isinstance(status, Mapping):
        raise LR8HistoricalTransportError("execution status differs")
    conditions = status.get("conditions", [])
    if not isinstance(conditions, list):
        raise LR8HistoricalTransportError("execution conditions differ")
    rows = [
        row for row in conditions
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    if not rows:
        return "Unknown"
    if len(rows) != 1 or rows[0].get("status") not in {"Unknown", "True", "False"}:
        raise LR8HistoricalTransportError("execution Completed condition differs")
    return str(rows[0]["status"])


def validate_reuse(
    *, job_metadata: Mapping[str, object], executions: object,
    schedulers: object, inventory: object, governance_inventory: object,
    forbidden_generation: str | None = None,
    forbidden_run_id: str | None = None,
) -> None:
    try:
        full_finish._job_identity(job_metadata, job=JOB, job_uid=JOB_UID)  # noqa: SLF001
    except full_finish.LR8FullSourceFinishError as exc:
        raise LR8HistoricalTransportError(str(exc)) from exc
    if not isinstance(executions, list) or any(
        not isinstance(row, Mapping) or _completion_state(row) == "Unknown"
        for row in executions
    ):
        raise LR8HistoricalTransportError("reused job has an active execution")
    if forbidden_generation is not None and _GENERATION.fullmatch(
        forbidden_generation
    ) is None:
        raise LR8HistoricalTransportError("forbidden job generation differs")
    if forbidden_run_id is not None and forbidden_run_id not in {
        mode.run_id for mode in MODES.values()
    }:
        raise LR8HistoricalTransportError("forbidden transport run differs")
    for row in executions:
        assert isinstance(row, Mapping)
        metadata = row.get("metadata")
        labels = metadata.get("labels") if isinstance(metadata, Mapping) else None
        if (
            forbidden_generation is not None
            and isinstance(labels, Mapping)
            and str(labels.get("run.googleapis.com/jobGeneration"))
            == forbidden_generation
        ):
            raise LR8HistoricalTransportError(
                "prepared job generation already has an execution"
            )
        if forbidden_run_id is not None:
            try:
                task = row["spec"]["template"]["spec"]  # type: ignore[index]
                containers = task["containers"]  # type: ignore[index]
            except (KeyError, TypeError):
                containers = []
            if isinstance(containers, list):
                for container in containers:
                    if not isinstance(container, Mapping):
                        continue
                    env_rows = container.get("env", [])
                    if not isinstance(env_rows, list):
                        continue
                    if any(
                        isinstance(env, Mapping)
                        and env.get("name")
                        == "LR8_HISTORICAL_SCORE_TRANSPORT_RUN_ID"
                        and env.get("value") == forbidden_run_id
                        for env in env_rows
                    ):
                        raise LR8HistoricalTransportError(
                            "transport run already has an execution"
                        )
    if not isinstance(schedulers, list):
        raise LR8HistoricalTransportError("scheduler census differs")
    needle = f"/jobs/{JOB}:run"
    for row in schedulers:
        if not isinstance(row, Mapping):
            raise LR8HistoricalTransportError("scheduler row differs")
        target = row.get("httpTarget", {})
        if isinstance(target, Mapping) and needle in str(target.get("uri", "")):
            raise LR8HistoricalTransportError("scheduler targets reused job")
    if inventory != []:
        raise LR8HistoricalTransportError("historical result prefix is not empty")
    if governance_inventory != []:
        raise LR8HistoricalTransportError(
            "historical launch/release governance prefix is not empty"
        )


def validate_build(
    value: object, *, build_id: str, code_sha: str, image: str,
) -> None:
    try:
        full_finish.validate_build_metadata(
            value, build_id=build_id, code_sha=code_sha, image=image,
        )
    except full_finish.LR8FullSourceFinishError as exc:
        raise LR8HistoricalTransportError(str(exc)) from exc
    assert isinstance(value, Mapping)
    steps = value.get("steps", [])
    rendered = "\n".join(
        str(item)
        for row in steps if isinstance(row, Mapping)
        for item in row.get("args", []) if isinstance(row.get("args", []), list)
    )
    if any(smoke not in rendered for smoke in _REQUIRED_BUILD_SMOKES):
        raise LR8HistoricalTransportError(
            "historical-score runner build smokes are absent"
        )


class Storage:
    """Generation-pinned GCS reader; construction is itself a cloud boundary."""

    def __init__(self) -> None:
        from google.cloud import storage

        self._client = storage.Client(project=PROJECT)

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        bucket, separator, name = uri.removeprefix("gs://").partition("/")
        if _SAFE_GCS.fullmatch(uri) is None or not separator or not name:
            raise LR8HistoricalTransportError("GCS URI differs")
        return bucket, name

    def inventory(self, prefix: str) -> list[dict[str, object]]:
        bucket, name = self._parts(prefix)
        rows: list[dict[str, object]] = []
        for blob in self._client.list_blobs(bucket, prefix=name):
            if blob.generation is None or blob.size is None:
                raise LR8HistoricalTransportError("GCS metadata is incomplete")
            rows.append({
                "uri": f"gs://{bucket}/{blob.name}",
                "generation": str(blob.generation),
                "bytes": int(blob.size),
            })
        rows.sort(key=lambda row: str(row["uri"]))
        return rows

    def load_pin(
        self, pin: Mapping[str, str], *, create_only: bool = False,
    ) -> tuple[dict[str, object], dict[str, object]]:
        uri = pin["uri"]
        generation = pin["generation"]
        bucket, name = self._parts(uri)
        generation_int = int(generation)
        blob = self._client.bucket(bucket).blob(name, generation=generation_int)
        try:
            blob.reload(if_generation_match=generation_int)
            raw = blob.download_as_bytes(if_generation_match=generation_int)
        except Exception as exc:
            raise LR8HistoricalTransportError(
                "generation-pinned GCS read failed"
            ) from exc
        observed = _receipt(
            uri=uri, generation=str(blob.generation), raw=raw,
            create_only=create_only,
        )
        if observed["generation"] != generation or observed["sha256"] != pin["sha256"]:
            raise LR8HistoricalTransportError("generation-pinned object differs")
        return observed, strict_json(raw, label="generation-pinned object")

    def load_inventory(
        self, metadata: Mapping[str, object],
    ) -> tuple[dict[str, object], dict[str, object]]:
        uri = metadata.get("uri")
        generation = metadata.get("generation")
        size = metadata.get("bytes")
        if (
            not isinstance(uri, str)
            or not isinstance(generation, str)
            or _GENERATION.fullmatch(generation) is None
            or _exact_int(size, label="inventory byte count") < 1
        ):
            raise LR8HistoricalTransportError("inventory object differs")
        receipt, value = self._load_without_sha(
            uri=uri, generation=generation, size=int(size)
        )
        return receipt, value

    def _load_without_sha(
        self, *, uri: str, generation: str, size: int,
    ) -> tuple[dict[str, object], dict[str, object]]:
        bucket, name = self._parts(uri)
        generation_int = int(generation)
        blob = self._client.bucket(bucket).blob(name, generation=generation_int)
        try:
            raw = blob.download_as_bytes(if_generation_match=generation_int)
        except Exception as exc:
            raise LR8HistoricalTransportError(
                "generation-pinned result read failed"
            ) from exc
        if len(raw) != size:
            raise LR8HistoricalTransportError("result object byte count differs")
        return (
            _receipt(uri=uri, generation=generation, raw=raw, create_only=True),
            strict_json(raw, label="historical result object"),
        )

    def publish_create_once(
        self, *, uri: str, value: Mapping[str, object], allow_exact_reopen: bool,
    ) -> tuple[dict[str, object], dict[str, object]]:
        raw = canonical_json(value)
        bucket_name, name = self._parts(uri)
        blob = self._client.bucket(bucket_name).blob(name)
        try:
            blob.upload_from_string(
                raw, content_type="application/json", if_generation_match=0,
            )
        except Exception as publish_error:
            if not allow_exact_reopen:
                raise LR8HistoricalTransportError(
                    "create-once governance publication failed"
                ) from publish_error
            try:
                blob.reload()
                generation = str(blob.generation)
                pinned = self._client.bucket(bucket_name).blob(
                    name, generation=int(generation),
                )
                reopened = pinned.download_as_bytes(
                    if_generation_match=int(generation)
                )
            except Exception as reopen_error:
                raise LR8HistoricalTransportError(
                    "ambiguous governance publication did not reopen exactly"
                ) from reopen_error
            if reopened != raw:
                raise LR8HistoricalTransportError(
                    "existing governance publication differs"
                ) from publish_error
        try:
            blob.reload()
            generation = str(blob.generation)
            pinned = self._client.bucket(bucket_name).blob(
                name, generation=int(generation),
            )
            reopened = pinned.download_as_bytes(if_generation_match=int(generation))
        except Exception as exc:
            raise LR8HistoricalTransportError(
                "created governance publication did not reopen"
            ) from exc
        if reopened != raw or _GENERATION.fullmatch(generation) is None:
            raise LR8HistoricalTransportError(
                "created governance publication differs"
            )
        receipt = _receipt(
            uri=uri, generation=generation, raw=reopened, create_only=True,
        )
        return receipt, strict_json(reopened, label="governance publication")

    def load_create_once(
        self, receipt_value: Mapping[str, object],
    ) -> tuple[dict[str, object], dict[str, object]]:
        receipt = _create_only_receipt(
            receipt_value, label="governance object",
        )
        bucket_name, name = self._parts(str(receipt["uri"]))
        generation = int(str(receipt["generation"]))
        try:
            live = self._client.bucket(bucket_name).blob(name)
            live.reload()
            if str(live.generation) != str(receipt["generation"]):
                raise LR8HistoricalTransportError(
                    "governance object is not the live generation"
                )
            pinned = self._client.bucket(bucket_name).blob(
                name, generation=generation,
            )
            raw = pinned.download_as_bytes(if_generation_match=generation)
        except LR8HistoricalTransportError:
            raise
        except Exception as exc:
            raise LR8HistoricalTransportError(
                "generation-pinned governance reopen failed"
            ) from exc
        observed = _receipt(
            uri=str(receipt["uri"]), generation=str(receipt["generation"]),
            raw=raw, create_only=True,
        )
        if observed != receipt:
            raise LR8HistoricalTransportError("governance object receipt differs")
        return observed, strict_json(raw, label="governance object")

    def release_generation(
        self, *, lease: Mapping[str, object], receipt_value: Mapping[str, object],
    ) -> None:
        receipt = _create_only_receipt(receipt_value, label="historical lease")
        uri = str(receipt["uri"])
        bucket_name, name = self._parts(uri)
        expected_generation = int(str(receipt["generation"]))
        expected_raw = canonical_json(lease)
        if (
            receipt["sha256"] != sha256(expected_raw).hexdigest()
            or receipt["bytes"] != len(expected_raw)
        ):
            raise LR8HistoricalTransportError("historical lease receipt differs")

        def current_generation() -> str | None:
            from google.api_core.exceptions import NotFound

            latest = self._client.bucket(bucket_name).blob(name)
            try:
                latest.reload()
            except NotFound:
                return None
            except Exception as exc:
                raise LR8HistoricalTransportError(
                    "historical lease current-generation check failed"
                ) from exc
            return str(latest.generation)

        current = current_generation()
        if current is None or current != str(expected_generation):
            return
        pinned = self._client.bucket(bucket_name).blob(
            name, generation=expected_generation,
        )
        try:
            raw = pinned.download_as_bytes(if_generation_match=expected_generation)
        except Exception as exc:
            raise LR8HistoricalTransportError(
                "historical lease generation reopen failed"
            ) from exc
        if raw != expected_raw:
            raise LR8HistoricalTransportError("historical lease body differs")
        try:
            pinned.delete(if_generation_match=expected_generation)
        except Exception as delete_error:
            if current_generation() == str(expected_generation):
                raise LR8HistoricalTransportError(
                    "historical lease generation release failed"
                ) from delete_error

    def generation_is_current(self, receipt_value: Mapping[str, object]) -> bool:
        from google.api_core.exceptions import NotFound

        receipt = _create_only_receipt(receipt_value, label="released object")
        bucket_name, name = self._parts(str(receipt["uri"]))
        latest = self._client.bucket(bucket_name).blob(name)
        try:
            latest.reload()
        except NotFound:
            return False
        except Exception as exc:
            raise LR8HistoricalTransportError(
                "released generation current-state check failed"
            ) from exc
        return str(latest.generation) == str(receipt["generation"])

def validate_input(
    *, mode: ModeSpec, pin: Mapping[str, str], storage: Storage,
) -> dict[str, object]:
    receipt, value = storage.load_pin(pin)
    if mode.name == "earlier":
        source = fit_adapter._validate_source(  # noqa: SLF001
            value,
            expected_manifest_sha256=pin["manifest_sha256"],
            training_source_receipt=receipt,
        )
        identity = {
            "candidate_rows": len(source.candidates),
            "catalog_universe_sha256": source.catalog_universe_sha256,
        }
    else:
        books = later_supplier.validate_book_freeze(
            value,
            expected_freeze_sha256=pin["manifest_sha256"],
            object_receipt=receipt,
        )
        identity = {
            "book_cells": len(books.cells),
            "union_players": len(books.catalog),
            "union_rosters": len(books.rosters),
        }
    return {
        "version": VERSION,
        "mode": mode.name,
        "run_id": mode.run_id,
        "pin": dict(pin),
        "object_receipt": receipt,
        "validated_identity": identity,
    }


def create_contract(
    *, mode: ModeSpec, pin: Mapping[str, str], input_validation: Mapping[str, object],
    job_metadata: Mapping[str, object], code_sha: str, build_id: str, image: str,
) -> dict[str, object]:
    if (
        _COMMIT.fullmatch(code_sha) is None
        or _BUILD.fullmatch(build_id) is None
        or _IMAGE.fullmatch(image) is None
    ):
        raise LR8HistoricalTransportError("build/image identity differs")
    expected_input = {
        "version": VERSION,
        "mode": mode.name,
        "run_id": mode.run_id,
        "pin": dict(pin),
        "object_receipt": input_validation.get("object_receipt"),
        "validated_identity": input_validation.get("validated_identity"),
    }
    if dict(input_validation) != expected_input:
        raise LR8HistoricalTransportError("input validation receipt differs")
    receipt = input_validation.get("object_receipt")
    identity = input_validation.get("validated_identity")
    valid_identity = False
    if isinstance(identity, Mapping):
        if mode.name == "earlier":
            valid_identity = (
                set(identity) == {"candidate_rows", "catalog_universe_sha256"}
                and _exact_int(
                    identity.get("candidate_rows"), label="input candidate rows"
                ) > 0
                and _SHA.fullmatch(str(identity.get("catalog_universe_sha256")))
                is not None
            )
        else:
            valid_identity = (
                set(identity) == {"book_cells", "union_players", "union_rosters"}
                and _exact_int(identity.get("book_cells"), label="book cells") == 108
                and _exact_int(
                    identity.get("union_players"), label="union players"
                ) > 0
                and _exact_int(
                    identity.get("union_rosters"), label="union rosters"
                ) > 0
            )
    if not isinstance(receipt, Mapping) or (
        not valid_identity
        or set(receipt) != {"uri", "generation", "sha256", "bytes"}
        or receipt.get("uri") != pin["uri"]
        or receipt.get("generation") != pin["generation"]
        or receipt.get("sha256") != pin["sha256"]
        or _exact_int(receipt.get("bytes"), label="input receipt bytes") < 1
    ):
        raise LR8HistoricalTransportError("input receipt does not bind its pin")
    validate_configured_job(
        job_metadata, mode=mode, code_sha=code_sha, build_id=build_id, image=image,
    )
    contract: dict[str, object] = {
        "version": VERSION,
        "mode": mode.name,
        "run_id": mode.run_id,
        "code_sha": code_sha,
        "build_id": build_id,
        "image": image,
        "input": dict(pin),
        "input_object": dict(receipt),
        "input_validation_sha256": sha256(canonical_json(input_validation)).hexdigest(),
        "output_prefix": mode.output_prefix,
        "expected_output_uris": list(mode.output_uris),
        "governance_prefix": mode.governance_prefix,
        "launch_claim_uri": mode.launch_claim_uri,
        "lease_release_authority_uri": mode.release_authority_uri,
        "lease_release_completion_uri": mode.release_completion_uri,
        "job": {
            "name": JOB,
            "uid": JOB_UID,
            "generation": _job_generation(job_metadata),
            "spec_sha256": _job_spec_sha(job_metadata),
            "task_count": 1,
            "parallelism": 1,
            "max_retries": 0,
            "timeout_seconds": TIMEOUT_SECONDS,
            "service_account": SERVICE_ACCOUNT,
            "resources": {"cpu": CPU, "memory": MEMORY},
            "command": ["bash"],
            "args": ["-ceu", _default_script(mode)],
            "env": _configured_env(
                mode=mode, code_sha=code_sha, build_id=build_id, image=image,
            ),
        },
        "sole_execution": True,
        "outcome_read_before_attempt_forbidden": True,
        "lease_acquired_during_prepare": False,
        "production_change_licensed": False,
    }
    contract["contract_sha256"] = sha256(canonical_json(contract)).hexdigest()
    return validate_contract(contract)


def validate_contract(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise LR8HistoricalTransportError("transport contract differs")
    result = dict(value)
    digest = result.pop("contract_sha256", None)
    fields = {
        "version", "mode", "run_id", "code_sha", "build_id", "image",
        "input", "input_object", "input_validation_sha256", "output_prefix",
        "expected_output_uris", "governance_prefix", "launch_claim_uri",
        "lease_release_authority_uri", "lease_release_completion_uri", "job",
        "sole_execution",
        "outcome_read_before_attempt_forbidden", "lease_acquired_during_prepare",
        "production_change_licensed",
    }
    if set(result) != fields:
        raise LR8HistoricalTransportError("transport contract fields differ")
    mode = _mode(str(result.get("mode")))
    pin_value = result.get("input")
    if not isinstance(pin_value, Mapping) or set(pin_value) != {
        "uri", "generation", "sha256", "manifest_sha256",
    }:
        raise LR8HistoricalTransportError("transport input pin differs")
    pin = input_pin(
        uri=str(pin_value["uri"]), generation=str(pin_value["generation"]),
        sha256_value=str(pin_value["sha256"]),
        manifest_sha256=str(pin_value["manifest_sha256"]),
    )
    job = result.get("job")
    receipt = result.get("input_object")
    if not isinstance(job, Mapping) or not isinstance(receipt, Mapping):
        raise LR8HistoricalTransportError("transport authority differs")
    expected_job = {
        "name": JOB,
        "uid": JOB_UID,
        "generation": job.get("generation"),
        "spec_sha256": job.get("spec_sha256"),
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "timeout_seconds": TIMEOUT_SECONDS,
        "service_account": SERVICE_ACCOUNT,
        "resources": {"cpu": CPU, "memory": MEMORY},
        "command": ["bash"],
        "args": ["-ceu", _default_script(mode)],
        "env": _configured_env(
            mode=mode, code_sha=str(result.get("code_sha")),
            build_id=str(result.get("build_id")), image=str(result.get("image")),
        ),
    }
    if (
        result.get("version") != VERSION
        or result.get("run_id") != mode.run_id
        or _COMMIT.fullmatch(str(result.get("code_sha"))) is None
        or _BUILD.fullmatch(str(result.get("build_id"))) is None
        or _IMAGE.fullmatch(str(result.get("image"))) is None
        or result.get("output_prefix") != mode.output_prefix
        or result.get("expected_output_uris") != list(mode.output_uris)
        or result.get("governance_prefix") != mode.governance_prefix
        or result.get("launch_claim_uri") != mode.launch_claim_uri
        or result.get("lease_release_authority_uri") != mode.release_authority_uri
        or result.get("lease_release_completion_uri")
        != mode.release_completion_uri
        or receipt.get("uri") != pin["uri"]
        or receipt.get("generation") != pin["generation"]
        or receipt.get("sha256") != pin["sha256"]
        or job != expected_job
        or _GENERATION.fullmatch(str(job.get("generation"))) is None
        or _SHA.fullmatch(str(job.get("spec_sha256"))) is None
        or _SHA.fullmatch(str(result.get("input_validation_sha256"))) is None
        or result.get("sole_execution") is not True
        or result.get("outcome_read_before_attempt_forbidden") is not True
        or result.get("lease_acquired_during_prepare") is not False
        or result.get("production_change_licensed") is not False
        or digest != sha256(canonical_json(result)).hexdigest()
    ):
        raise LR8HistoricalTransportError("transport contract authority differs")
    result["contract_sha256"] = digest
    return result


def validate_ready(
    *, contract: Mapping[str, object], job_metadata: Mapping[str, object],
    executions: object, schedulers: object, inventory: object,
    governance_inventory: object,
) -> None:
    frozen = validate_contract(contract)
    mode = _mode(str(frozen["mode"]))
    validate_reuse(
        job_metadata=job_metadata, executions=executions,
        schedulers=schedulers, inventory=inventory,
        governance_inventory=governance_inventory,
        forbidden_generation=str(frozen["job"]["generation"]),  # type: ignore[index]
        forbidden_run_id=mode.run_id,
    )
    job = frozen["job"]
    assert isinstance(job, Mapping)
    validate_configured_job(
        job_metadata, mode=mode, code_sha=str(frozen["code_sha"]),
        build_id=str(frozen["build_id"]), image=str(frozen["image"]),
        generation=str(job["generation"]), spec_sha256=str(job["spec_sha256"]),
    )


def _validated_lease(
    *, mode: ModeSpec, contract: Mapping[str, object], lease_raw: bytes,
) -> dict[str, object]:
    lease_value = strict_json(lease_raw, label="historical lease receipt")
    normalized = _lease_contract(lease_value)
    lease_config = earlier_supplier.SupplierConfig(
        mode.run_id, JOB, str(contract["code_sha"]), str(contract["image"]),
        str(contract["input"]["manifest_sha256"]),  # type: ignore[index]
        True,
    )
    try:
        return earlier_supplier._validate_lease(  # noqa: SLF001
            normalized, config=lease_config,
        )
    except earlier_supplier.LR8ScoreMapError as exc:
        raise LR8HistoricalTransportError(str(exc)) from exc


ClaimPublisher = Callable[
    [str, Mapping[str, object]],
    tuple[dict[str, object], dict[str, object]],
]


def _launch_claim_body(
    *, contract: Mapping[str, object], lease_raw: bytes,
) -> dict[str, object]:
    frozen = validate_contract(contract)
    mode = _mode(str(frozen["mode"]))
    lease = _validated_lease(mode=mode, contract=frozen, lease_raw=lease_raw)
    job = frozen["job"]
    assert isinstance(job, Mapping)
    return {
        "schema": "lr8-historical-score-launch-job-use-claim-v1",
        "version": VERSION,
        "mode": mode.name,
        "run_id": mode.run_id,
        "contract_sha256": frozen["contract_sha256"],
        "code_sha": frozen["code_sha"],
        "build_id": frozen["build_id"],
        "image": frozen["image"],
        "input": frozen["input"],
        "input_object": frozen["input_object"],
        "job": {
            "name": JOB,
            "uid": JOB_UID,
            "generation": job["generation"],
            "spec_sha256": job["spec_sha256"],
        },
        "historical_outcome_lease": lease,
        "lease_receipt_sha256": sha256(lease_raw).hexdigest(),
        "sole_execution": True,
        "retry_licensed": False,
        "held_through_terminal_and_lease_release": True,
    }


def create_launch_claim(
    *, contract: Mapping[str, object], lease_raw: bytes, publish: ClaimPublisher,
) -> dict[str, object]:
    frozen = validate_contract(contract)
    mode = _mode(str(frozen["mode"]))
    body = _launch_claim_body(contract=frozen, lease_raw=lease_raw)
    receipt, reopened = publish(mode.launch_claim_uri, body)
    if reopened != body:
        raise LR8HistoricalTransportError("launch claim reopen differs")
    value = {"claim": body, "object": receipt}
    return validate_launch_claim(value, contract=frozen)


def validate_launch_claim(
    value: object, *, contract: Mapping[str, object],
) -> dict[str, object]:
    frozen = validate_contract(contract)
    if not isinstance(value, Mapping) or set(value) != {"claim", "object"}:
        raise LR8HistoricalTransportError("launch claim differs")
    body = value["claim"]
    if not isinstance(body, Mapping):
        raise LR8HistoricalTransportError("launch claim body differs")
    lease = body.get("historical_outcome_lease")
    if not isinstance(lease, Mapping):
        raise LR8HistoricalTransportError("launch claim lease differs")
    lease_raw = canonical_json({
        "lease": lease.get("body"), "object": lease.get("object_receipt"),
    })
    expected = _launch_claim_body(contract=frozen, lease_raw=lease_raw)
    receipt = _create_only_receipt(value["object"], label="launch claim")
    mode = _mode(str(frozen["mode"]))
    raw = canonical_json(body)
    if (
        dict(body) != expected
        or receipt["uri"] != mode.launch_claim_uri
        or receipt["sha256"] != sha256(raw).hexdigest()
        or receipt["bytes"] != len(raw)
    ):
        raise LR8HistoricalTransportError("launch claim authority differs")
    return {"claim": dict(body), "object": receipt}


def _runner_script(
    *, mode: ModeSpec, contract: Mapping[str, object], lease_raw: bytes,
    claim: Mapping[str, object],
) -> str:
    pin = contract["input"]
    assert isinstance(pin, Mapping)
    encoded = base64.b64encode(lease_raw).decode("ascii")
    claim_object = claim["object"]
    assert isinstance(claim_object, Mapping)
    common = (
        f"--execute --project {PROJECT} --run-id {mode.run_id} --job {JOB} "
        f"--code-sha {contract['code_sha']} --image {contract['image']}"
    )
    source = (
        f"--{mode.input_flag}-uri {pin['uri']} "
        f"--{mode.input_flag}-generation {pin['generation']} "
        f"--{mode.input_flag}-sha256 {pin['sha256']} "
        f"--{mode.input_flag}-manifest-sha256 {pin['manifest_sha256']}"
    )
    return (
        f"set -eu; test ! -e {LEASE_TMP}; "
        f"printf '%s' '{encoded}' | base64 -d > {LEASE_TMP}; "
        "export LR8_HISTORICAL_SCORE_LAUNCH_CLAIM_SHA256="
        f"{claim_object['sha256']}; export {mode.enabled_env}=1; "
        f"exec python {mode.runner} {common} {source} "
        f"--historical-lease-receipt {LEASE_TMP}"
    )


def create_launch_intent(
    *, contract: Mapping[str, object], lease_raw: bytes,
    launch_claim: Mapping[str, object],
) -> dict[str, object]:
    frozen = validate_contract(contract)
    mode = _mode(str(frozen["mode"]))
    validated_lease = _validated_lease(
        mode=mode, contract=frozen, lease_raw=lease_raw,
    )
    claim = validate_launch_claim(launch_claim, contract=frozen)
    if claim["claim"]["historical_outcome_lease"] != validated_lease:  # type: ignore[index]
        raise LR8HistoricalTransportError("launch claim lease differs")
    script = _runner_script(
        mode=mode, contract=frozen, lease_raw=lease_raw, claim=claim,
    )
    intent: dict[str, object] = {
        "version": VERSION,
        "mode": mode.name,
        "run_id": mode.run_id,
        "contract_sha256": frozen["contract_sha256"],
        "lease": validated_lease,
        "lease_receipt_sha256": sha256(lease_raw).hexdigest(),
        "lease_receipt_base64": base64.b64encode(lease_raw).decode("ascii"),
        "launch_claim": claim,
        "command": ["bash"],
        "args": ["-ceu", script],
        "runner_script_sha256": sha256(script.encode("utf-8")).hexdigest(),
        "sole_execution": True,
        "retry_licensed": False,
    }
    intent["intent_sha256"] = sha256(canonical_json(intent)).hexdigest()
    return validate_launch_intent(intent, contract=frozen, launch_claim=claim)


def validate_launch_intent(
    value: object, *, contract: Mapping[str, object],
    launch_claim: Mapping[str, object] | None = None,
) -> dict[str, object]:
    frozen = validate_contract(contract)
    if not isinstance(value, Mapping):
        raise LR8HistoricalTransportError("launch intent differs")
    result = dict(value)
    digest = result.pop("intent_sha256", None)
    fields = {
        "version", "mode", "run_id", "contract_sha256", "lease",
        "lease_receipt_sha256", "lease_receipt_base64", "launch_claim",
        "command", "args", "runner_script_sha256", "sole_execution",
        "retry_licensed",
    }
    if set(result) != fields:
        raise LR8HistoricalTransportError("launch intent fields differ")
    mode = _mode(str(frozen["mode"]))
    try:
        lease_raw = base64.b64decode(
            str(result.get("lease_receipt_base64")), validate=True,
        )
    except (ValueError, TypeError) as exc:
        raise LR8HistoricalTransportError("launch lease encoding differs") from exc
    validated_lease = _validated_lease(
        mode=mode, contract=frozen, lease_raw=lease_raw,
    )
    claim = validate_launch_claim(result.get("launch_claim"), contract=frozen)
    if launch_claim is not None and claim != validate_launch_claim(
        launch_claim, contract=frozen,
    ):
        raise LR8HistoricalTransportError("local launch claim differs")
    script = _runner_script(
        mode=mode, contract=frozen, lease_raw=lease_raw, claim=claim,
    )
    if (
        result.get("version") != VERSION
        or result.get("mode") != mode.name
        or result.get("run_id") != mode.run_id
        or result.get("contract_sha256") != frozen["contract_sha256"]
        or result.get("lease") != validated_lease
        or result.get("lease_receipt_sha256") != sha256(lease_raw).hexdigest()
        or claim["claim"]["historical_outcome_lease"] != validated_lease  # type: ignore[index]
        or result.get("command") != ["bash"]
        or result.get("args") != ["-ceu", script]
        or result.get("runner_script_sha256")
        != sha256(script.encode("utf-8")).hexdigest()
        or result.get("sole_execution") is not True
        or result.get("retry_licensed") is not False
        or digest != sha256(canonical_json(result)).hexdigest()
    ):
        raise LR8HistoricalTransportError("launch intent authority differs")
    result["intent_sha256"] = digest
    return result


def validate_preexecute(
    *, contract: Mapping[str, object], intent: Mapping[str, object],
    launch_claim: Mapping[str, object], job_metadata: Mapping[str, object],
    executions: object, schedulers: object, inventory: object,
    governance_inventory: object,
) -> None:
    frozen = validate_contract(contract)
    claim = validate_launch_claim(launch_claim, contract=frozen)
    launch = validate_launch_intent(
        intent, contract=frozen, launch_claim=claim,
    )
    mode = _mode(str(frozen["mode"]))
    job = frozen["job"]
    assert isinstance(job, Mapping)
    validate_configured_job(
        job_metadata, mode=mode, code_sha=str(frozen["code_sha"]),
        build_id=str(frozen["build_id"]), image=str(frozen["image"]),
        generation=str(job["generation"]), spec_sha256=str(job["spec_sha256"]),
    )
    validate_reuse(
        job_metadata=job_metadata, executions=executions,
        schedulers=schedulers, inventory=inventory, governance_inventory=[],
        forbidden_generation=str(job["generation"]),
        forbidden_run_id=mode.run_id,
    )
    claim_object = claim["object"]
    assert isinstance(claim_object, Mapping)
    expected_inventory = [{
        "uri": claim_object["uri"],
        "generation": claim_object["generation"],
        "bytes": claim_object["bytes"],
    }]
    if governance_inventory != expected_inventory:
        raise LR8HistoricalTransportError(
            "launch claim is not the exact live governance inventory"
        )
    if launch["launch_claim"] != claim:
        raise LR8HistoricalTransportError("pre-execution launch claim differs")


def ledger_line(execution: str, prefix: str) -> bytes:
    if _EXECUTION.fullmatch(execution) is None or prefix not in {
        spec.output_prefix for spec in MODES.values()
    }:
        raise LR8HistoricalTransportError("execution ledger identity differs")
    return f"{JOB} {execution} {prefix}\n".encode("utf-8")


def parse_ledger(path: Path, *, mode: ModeSpec) -> str:
    if path.is_symlink() or not path.is_file():
        raise LR8HistoricalTransportError("execution ledger is absent")
    raw = path.read_bytes()
    fields = raw.decode("utf-8", errors="strict").split()
    if len(fields) != 3 or fields[0] != JOB or fields[2] != mode.output_prefix:
        raise LR8HistoricalTransportError("execution ledger differs")
    expected = ledger_line(fields[1], fields[2])
    if raw != expected:
        raise LR8HistoricalTransportError("execution ledger is not canonical")
    return fields[1]


def validate_terminal(
    value: Mapping[str, object], *, execution: str,
    contract: Mapping[str, object], intent: Mapping[str, object],
    expected_state: str,
) -> dict[str, object]:
    frozen = validate_contract(contract)
    launch = validate_launch_intent(intent, contract=frozen)
    if expected_state not in {"True", "False"} or _completion_state(value) != expected_state:
        raise LR8HistoricalTransportError("execution terminal state differs")
    metadata = value.get("metadata")
    spec = value.get("spec")
    status = value.get("status")
    if not all(isinstance(row, Mapping) for row in (metadata, spec, status)):
        raise LR8HistoricalTransportError("execution metadata structure differs")
    assert isinstance(metadata, Mapping) and isinstance(spec, Mapping)
    assert isinstance(status, Mapping)
    labels = metadata.get("labels")
    job = frozen["job"]
    assert isinstance(job, Mapping)
    if (
        metadata.get("name") != execution
        or _EXECUTION.fullmatch(execution) is None
        or not isinstance(labels, Mapping)
        or labels.get("run.googleapis.com/job") != JOB
        or labels.get("run.googleapis.com/jobUid") != JOB_UID
        or str(labels.get("run.googleapis.com/jobGeneration")) != job["generation"]
    ):
        raise LR8HistoricalTransportError("execution job binding differs")
    if (
        _exact_int(spec.get("taskCount"), label="execution task count") != 1
        or _exact_int(spec.get("parallelism"), label="execution parallelism") != 1
    ):
        raise LR8HistoricalTransportError("execution is not one-task serial")
    task = spec.get("template", {}).get("spec", {})  # type: ignore[union-attr]
    if not isinstance(task, Mapping):
        raise LR8HistoricalTransportError("execution task differs")
    containers = task.get("containers")
    if (
        not isinstance(containers, list)
        or len(containers) != 1
        or not isinstance(containers[0], Mapping)
    ):
        raise LR8HistoricalTransportError("execution container differs")
    container = containers[0]
    env_rows = container.get("env", [])
    if not isinstance(env_rows, list) or any(
        not isinstance(row, Mapping) or set(row) != {"name", "value"}
        for row in env_rows
    ):
        raise LR8HistoricalTransportError("execution environment differs")
    env = {str(row["name"]): row["value"] for row in env_rows}
    if len(env) != len(env_rows) or (
        _exact_int(task.get("maxRetries"), label="execution retries") != 0
        or container.get("image") != frozen["image"]
        or container.get("command") != launch["command"]
        or container.get("args") != launch["args"]
        or env != job["env"]
        or task.get("serviceAccountName") != SERVICE_ACCOUNT
        or container.get("resources", {}).get("limits")
        != {"cpu": CPU, "memory": MEMORY}
        or str(task.get("timeoutSeconds")) != TIMEOUT_SECONDS
    ):
        raise LR8HistoricalTransportError("execution executable contract differs")
    counters = {
        key: _exact_int(status.get(field, 0), label=f"execution {key}")
        for field, key in (
            ("succeededCount", "succeeded"),
            ("failedCount", "failed"),
            ("cancelledCount", "cancelled"),
            ("retriedCount", "retried"),
        )
    }
    if not status.get("completionTime") or counters["retried"] != 0:
        raise LR8HistoricalTransportError("execution terminal receipt differs")
    if expected_state == "True" and counters != {
        "succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0,
    }:
        raise LR8HistoricalTransportError("execution success counters differ")
    if expected_state == "False" and (
        counters["succeeded"] != 0
        or counters["failed"] + counters["cancelled"] != 1
    ):
        raise LR8HistoricalTransportError("execution failure counters differ")
    return {
        "execution": execution,
        "state": expected_state,
        "counters": counters,
        "metadata_sha256": sha256(canonical_json(value)).hexdigest(),
        "launch_claim_object": launch["launch_claim"]["object"],  # type: ignore[index]
    }


ObjectLoader = Callable[
    [Mapping[str, object]],
    tuple[dict[str, object], dict[str, object]],
]


def _exact_results(
    *, mode: ModeSpec, inventory: object, loader: ObjectLoader,
) -> tuple[list[dict[str, object]], dict[str, tuple[dict[str, object], dict[str, object]]]]:
    if not isinstance(inventory, list) or any(
        not isinstance(row, Mapping) for row in inventory
    ):
        raise LR8HistoricalTransportError("result inventory differs")
    by_uri = {str(row["uri"]): row for row in inventory}
    if len(by_uri) != len(inventory) or set(by_uri) != set(mode.output_uris):
        raise LR8HistoricalTransportError("result inventory is not exact")
    loaded: dict[str, tuple[dict[str, object], dict[str, object]]] = {}
    normalized_inventory: list[dict[str, object]] = []
    for uri in mode.output_uris:
        metadata = by_uri[uri]
        receipt, value = loader(metadata)
        if (
            receipt.get("uri") != uri
            or receipt.get("generation") != metadata.get("generation")
            or receipt.get("bytes") != metadata.get("bytes")
            or receipt.get("create_only") is not True
        ):
            raise LR8HistoricalTransportError("result receipt differs")
        loaded[uri.rsplit("/", 1)[1]] = (receipt, value)
        normalized_inventory.append(dict(metadata))
    return normalized_inventory, loaded


def _expected_lease(intent: Mapping[str, object]) -> dict[str, object]:
    lease = intent.get("lease")
    if not isinstance(lease, Mapping):
        raise LR8HistoricalTransportError("launch lease binding differs")
    return dict(lease)


def _validate_earlier_results(
    *, contract: Mapping[str, object], intent: Mapping[str, object],
    loaded: Mapping[str, tuple[dict[str, object], dict[str, object]]],
    input_loader: Callable[[], tuple[dict[str, object], dict[str, object]]],
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    pin = contract["input"]
    assert isinstance(pin, Mapping)
    input_receipt, input_value = input_loader()
    frozen_source = fit_adapter._validate_source(  # noqa: SLF001
        input_value,
        expected_manifest_sha256=str(pin["manifest_sha256"]),
        training_source_receipt=input_receipt,
    )
    attempt_receipt, attempt = loaded["label-read-attempt.json"]
    source_receipt, source = loaded["authoritative-score-source.json"]
    map_receipt, score_map = loaded["authoritative-score-map.json"]
    fit_receipt, fit_value = loaded["label-fit-freeze.json"]
    _, provenance = fit_adapter._score_map(  # noqa: SLF001
        score_map, score_map_receipt=map_receipt, frozen_source=frozen_source,
    )
    validated_fit = fit_adapter.validate_label_fit_freeze(
        fit_value, expected_freeze_sha256=str(fit_value.get("freeze_sha256")),
    )
    if (
        validated_fit["training_source"]["object_receipt"] != input_receipt
        or validated_fit["training_source"]["manifest_sha256"]
        != pin["manifest_sha256"]
        or validated_fit["score_provenance"] != provenance
        or provenance["label_read_attempt"] != attempt
        or provenance["label_read_attempt_object"] != attempt_receipt
        or provenance["score_source_extract"] != source
        or provenance["score_source_extract_object"] != source_receipt
        or provenance["score_map_object"] != map_receipt
        or attempt.get("historical_outcome_lease") != _expected_lease(intent)
    ):
        raise LR8HistoricalTransportError("earlier result transitive binding differs")
    receipts = {
        name: loaded[name][0] for name in MODES["earlier"].output_names
    }
    handoff = {
        "schema": LABEL_FIT_HANDOFF_SCHEMA,
        "label_fit_freeze_object": fit_receipt,
        "label_fit_freeze_sha256": _digest(
            validated_fit.get("freeze_sha256"), label="label-fit freeze hash",
        ),
        "anatomy_artifact_sha256": _digest(
            validated_fit.get("anatomy_artifact_sha256"),
            label="anatomy artifact hash",
        ),
        "generation_pinned_reopen_validated": True,
        "independent_fit_replay_validated": True,
    }
    return receipts, handoff


def _validate_later_results(
    *, contract: Mapping[str, object], intent: Mapping[str, object],
    loaded: Mapping[str, tuple[dict[str, object], dict[str, object]]],
    input_loader: Callable[[], tuple[dict[str, object], dict[str, object]]],
) -> tuple[dict[str, dict[str, object]], None]:
    pin = contract["input"]
    assert isinstance(pin, Mapping)
    input_receipt, input_value = input_loader()
    books = later_supplier.validate_book_freeze(
        input_value,
        expected_freeze_sha256=str(pin["manifest_sha256"]),
        object_receipt=input_receipt,
    )
    attempt_receipt, attempt = loaded["later-period-read-attempt.json"]
    source_receipt, source = loaded["later-period-player-score-source.json"]
    _evaluation_receipt, evaluation = loaded["later-period-evaluation.json"]
    lease = _expected_lease(intent)
    if attempt.get("historical_outcome_lease") != lease:
        raise LR8HistoricalTransportError("later-period lease binding differs")
    attempt_identity = later_supplier._attempt_identity(  # noqa: SLF001
        attempt_receipt, lease,
    )
    later_supplier._replay(  # noqa: SLF001
        books=books,
        source=source,
        source_receipt=source_receipt,
        evaluation=evaluation,
        attempt=attempt,
        attempt_receipt=attempt_receipt,
        attempt_identity=attempt_identity,
    )
    return (
        {name: loaded[name][0] for name in MODES["later"].output_names},
        None,
    )


def _validated_label_fit_handoff(
    *, mode: ModeSpec, value: object,
    result_objects: Mapping[str, object],
) -> dict[str, object] | None:
    if mode.name == "later":
        if value is not None:
            raise LR8HistoricalTransportError(
                "later result carries an earlier label-fit handoff"
            )
        return None
    required = {
        "schema", "label_fit_freeze_object", "label_fit_freeze_sha256",
        "anatomy_artifact_sha256", "generation_pinned_reopen_validated",
        "independent_fit_replay_validated",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise LR8HistoricalTransportError("label-fit handoff fields differ")
    result = dict(value)
    fit_object = _create_only_receipt(
        result["label_fit_freeze_object"], label="label-fit handoff object",
    )
    if (
        result.get("schema") != LABEL_FIT_HANDOFF_SCHEMA
        or fit_object != result_objects.get("label-fit-freeze.json")
        or result.get("generation_pinned_reopen_validated") is not True
        or result.get("independent_fit_replay_validated") is not True
    ):
        raise LR8HistoricalTransportError("label-fit handoff authority differs")
    result["label_fit_freeze_object"] = fit_object
    result["label_fit_freeze_sha256"] = _digest(
        result.get("label_fit_freeze_sha256"), label="label-fit freeze hash",
    )
    result["anatomy_artifact_sha256"] = _digest(
        result.get("anatomy_artifact_sha256"), label="anatomy artifact hash",
    )
    return result


def _label_fit_local_receipt(
    *, mode: ModeSpec, validation_sha256: str,
    handoff: Mapping[str, object],
) -> dict[str, object]:
    if mode.name != "earlier":
        raise LR8HistoricalTransportError("label-fit local receipt mode differs")
    return {
        "schema": LABEL_FIT_LOCAL_RECEIPT_SCHEMA,
        "mode": mode.name,
        "run_id": mode.run_id,
        "validation_sha256": _digest(
            validation_sha256, label="label-fit validation hash",
        ),
        "label_fit_freeze_object": handoff["label_fit_freeze_object"],
        "label_fit_freeze_sha256": handoff["label_fit_freeze_sha256"],
        "anatomy_artifact_sha256": handoff["anatomy_artifact_sha256"],
        "generation_pinned_reopen_validated": True,
        "independent_fit_replay_validated": True,
        "historical_outcome_lease_release_required": True,
        "later_source_prepare_values_complete": True,
        "production_change_licensed": False,
    }


def finish_success(
    *, contract: Mapping[str, object], intent: Mapping[str, object],
    execution: str, terminal_metadata: Mapping[str, object],
    inventory_loader: Callable[[str], object], object_loader: ObjectLoader,
    input_loader: Callable[[], tuple[dict[str, object], dict[str, object]]],
    claim_loader: ObjectLoader,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    frozen = validate_contract(contract)
    launch = validate_launch_intent(intent, contract=frozen)
    terminal = validate_terminal(
        terminal_metadata, execution=execution, contract=frozen,
        intent=launch, expected_state="True",
    )
    claim = launch["launch_claim"]
    assert isinstance(claim, Mapping)
    claim_object = claim["object"]
    assert isinstance(claim_object, Mapping)
    reopened_claim_receipt, reopened_claim = claim_loader(claim_object)
    if (
        reopened_claim_receipt != claim_object
        or reopened_claim != claim["claim"]
    ):
        raise LR8HistoricalTransportError("live launch claim differs")
    mode = _mode(str(frozen["mode"]))
    inventory, loaded = _exact_results(
        mode=mode, inventory=inventory_loader(mode.output_prefix + "/"),
        loader=object_loader,
    )
    if mode.name == "earlier":
        receipts, label_fit_handoff = _validate_earlier_results(
            contract=frozen, intent=launch, loaded=loaded,
            input_loader=input_loader,
        )
        disposition = "earlier-score-map-and-fit-validated"
    else:
        receipts, label_fit_handoff = _validate_later_results(
            contract=frozen, intent=launch, loaded=loaded,
            input_loader=input_loader,
        )
        disposition = "later-exact-union-evaluation-validated"
    validation = {
        "version": VERSION,
        "mode": mode.name,
        "run_id": mode.run_id,
        "disposition": disposition,
        "contract_sha256": frozen["contract_sha256"],
        "intent_sha256": launch["intent_sha256"],
        "terminal": terminal,
        "launch_claim_object": dict(claim_object),
        "input_object": frozen["input_object"],
        "result_objects": receipts,
        "label_fit_handoff": label_fit_handoff,
        "result_inventory_sha256": sha256(canonical_json(inventory)).hexdigest(),
        "generation_pinned_reopen_validated": True,
        "independent_runner_validation_replayed": True,
        "uses_realized_outcomes": True,
        "historical_outcome_lease_release_required": True,
        "production_change_licensed": False,
    }
    return validation, inventory


def completion_text(
    *, mode: ModeSpec, disposition: str, validation_sha: str,
    label_fit_handoff: Mapping[str, object] | None = None,
) -> bytes:
    if not disposition or _SHA.fullmatch(validation_sha) is None:
        raise LR8HistoricalTransportError("completion identity differs")
    handoff_lines = ""
    if label_fit_handoff is not None:
        normalized = _validated_label_fit_handoff(
            mode=mode, value=label_fit_handoff,
            result_objects={
                "label-fit-freeze.json": label_fit_handoff.get(
                    "label_fit_freeze_object"
                ),
            },
        )
        assert normalized is not None
        local = _label_fit_local_receipt(
            mode=mode, validation_sha256=validation_sha, handoff=normalized,
        )
        handoff_lines = (
            f"label_fit_freeze_sha256={normalized['label_fit_freeze_sha256']}\n"
            f"anatomy_artifact_sha256={normalized['anatomy_artifact_sha256']}\n"
            "label_fit_local_receipt_sha256="
            f"{sha256(canonical_json(local)).hexdigest()}\n"
        )
    elif mode.name == "later":
        handoff_lines = "label_fit_handoff_not_applicable=true\n"
    return (
        f"run_id={mode.run_id}\n"
        f"mode={mode.name}\n"
        "uses_realized_outcomes=true\n"
        f"disposition={disposition}\n"
        f"validation_sha256={validation_sha}\n"
        f"{handoff_lines}"
        "receipt_only_completion=true\n"
        "production_change_licensed=false\n"
    ).encode("utf-8")


def _success_files(
    out: Path,
) -> tuple[
    dict[str, object], dict[str, object], dict[str, object],
    dict[str, object], bytes, bytes,
]:
    contract, claim, intent, execution, terminal_metadata = _finish_paths(out)
    terminal = validate_terminal(
        terminal_metadata, execution=execution, contract=contract,
        intent=intent, expected_state="True",
    )
    validation_path = out / "validation.json"
    validation = _load(validation_path, label="successful validation")
    validation_raw = canonical_json(validation)
    if validation_path.read_bytes() != validation_raw:
        raise LR8HistoricalTransportError("successful validation is not canonical")
    mode = _mode(str(contract["mode"]))
    fields = {
        "version", "mode", "run_id", "disposition", "contract_sha256",
        "intent_sha256", "terminal", "launch_claim_object", "input_object",
        "result_objects", "label_fit_handoff", "result_inventory_sha256",
        "generation_pinned_reopen_validated",
        "independent_runner_validation_replayed", "uses_realized_outcomes",
        "historical_outcome_lease_release_required",
        "production_change_licensed",
    }
    result_objects = validation.get("result_objects")
    expected_names = set(mode.output_names)
    if not isinstance(result_objects, Mapping) or set(result_objects) != expected_names:
        raise LR8HistoricalTransportError("successful result receipts differ")
    for name, receipt in result_objects.items():
        normalized = _create_only_receipt(receipt, label=f"result {name}")
        if normalized["uri"] != f"{mode.output_prefix}/{name}":
            raise LR8HistoricalTransportError("successful result URI differs")
    label_fit_handoff = _validated_label_fit_handoff(
        mode=mode, value=validation.get("label_fit_handoff"),
        result_objects=result_objects,
    )
    claim_object = claim["object"]
    if (
        set(validation) != fields
        or validation.get("version") != VERSION
        or validation.get("mode") != mode.name
        or validation.get("run_id") != mode.run_id
        or not validation.get("disposition")
        or validation.get("contract_sha256") != contract["contract_sha256"]
        or validation.get("intent_sha256") != intent["intent_sha256"]
        or validation.get("terminal") != terminal
        or validation.get("launch_claim_object") != claim_object
        or validation.get("input_object") != contract["input_object"]
        or _SHA.fullmatch(str(validation.get("result_inventory_sha256"))) is None
        or validation.get("generation_pinned_reopen_validated") is not True
        or validation.get("independent_runner_validation_replayed") is not True
        or validation.get("uses_realized_outcomes") is not True
        or validation.get("historical_outcome_lease_release_required") is not True
        or validation.get("production_change_licensed") is not False
    ):
        raise LR8HistoricalTransportError("successful validation authority differs")
    local_handoff_path = out / "label-fit-handoff.json"
    if label_fit_handoff is None:
        if local_handoff_path.exists():
            raise LR8HistoricalTransportError(
                "later result carries a local label-fit receipt"
            )
    else:
        expected_local_handoff = _label_fit_local_receipt(
            mode=mode, validation_sha256=sha256(validation_raw).hexdigest(),
            handoff=label_fit_handoff,
        )
        if (
            local_handoff_path.is_symlink()
            or not local_handoff_path.is_file()
            or local_handoff_path.read_bytes()
            != canonical_json(expected_local_handoff)
        ):
            raise LR8HistoricalTransportError("local label-fit receipt differs")
    completion_path = out / "completion.txt"
    if completion_path.is_symlink() or not completion_path.is_file():
        raise LR8HistoricalTransportError("successful completion is absent")
    completion_raw = completion_path.read_bytes()
    expected_completion = completion_text(
        mode=mode, disposition=str(validation["disposition"]),
        validation_sha=sha256(validation_raw).hexdigest(),
        label_fit_handoff=label_fit_handoff,
    )
    if completion_raw != expected_completion:
        raise LR8HistoricalTransportError("successful completion differs")
    return contract, claim, intent, terminal, validation_raw, completion_raw


def label_fit_handoff_values(out: Path) -> tuple[str, ...]:
    contract, _claim, _intent, _terminal, validation_raw, _completion_raw = (
        _success_files(out)
    )
    mode = _mode(str(contract["mode"]))
    if mode.name != "earlier":
        raise LR8HistoricalTransportError("label-fit handoff mode differs")
    validation = strict_json(validation_raw, label="successful validation")
    result_objects = validation.get("result_objects")
    if not isinstance(result_objects, Mapping):
        raise LR8HistoricalTransportError("successful result receipts differ")
    handoff = _validated_label_fit_handoff(
        mode=mode, value=validation.get("label_fit_handoff"),
        result_objects=result_objects,
    )
    assert handoff is not None
    receipt = _create_only_receipt(
        handoff["label_fit_freeze_object"], label="label-fit handoff object",
    )
    return (
        str(receipt["uri"]), str(receipt["generation"]),
        str(receipt["sha256"]), str(receipt["bytes"]),
        str(handoff["label_fit_freeze_sha256"]),
        str(handoff["anatomy_artifact_sha256"]),
    )


def _release_authority_body(
    *, contract: Mapping[str, object], claim: Mapping[str, object],
    intent: Mapping[str, object], terminal: Mapping[str, object],
    validation_raw: bytes, completion_raw: bytes,
) -> dict[str, object]:
    return {
        "schema": "lr8-historical-score-lease-release-authority-v1",
        "version": VERSION,
        "mode": contract["mode"],
        "run_id": contract["run_id"],
        "contract_sha256": contract["contract_sha256"],
        "intent_sha256": intent["intent_sha256"],
        "launch_claim_object": claim["object"],
        "historical_outcome_lease": intent["lease"],
        "terminal": terminal,
        "validation_sha256": sha256(validation_raw).hexdigest(),
        "completion_sha256": sha256(completion_raw).hexdigest(),
        "generation_matched_release_only": True,
        "create_once_before_release": True,
        "production_change_licensed": False,
    }


def _release_completion_body(
    *, contract: Mapping[str, object], intent: Mapping[str, object],
    authority_object: Mapping[str, object],
) -> dict[str, object]:
    lease = intent["lease"]
    assert isinstance(lease, Mapping)
    lease_receipt = lease["object_receipt"]
    assert isinstance(lease_receipt, Mapping)
    return {
        "schema": "lr8-historical-score-lease-release-completion-v1",
        "version": VERSION,
        "mode": contract["mode"],
        "run_id": contract["run_id"],
        "contract_sha256": contract["contract_sha256"],
        "intent_sha256": intent["intent_sha256"],
        "release_authority_object": dict(authority_object),
        "released_lease_uri": lease_receipt["uri"],
        "released_lease_generation": lease_receipt["generation"],
        "released_generation_no_longer_current": True,
        "idempotent_release_recovery": True,
        "production_change_licensed": False,
    }


def _publication_wrapper(
    *, value: Mapping[str, object], expected_body: Mapping[str, object],
    expected_uri: str, label: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {"body", "object"}:
        raise LR8HistoricalTransportError(f"{label} wrapper differs")
    if value["body"] != expected_body:
        raise LR8HistoricalTransportError(f"{label} body differs")
    receipt = _create_only_receipt(value["object"], label=label)
    raw = canonical_json(expected_body)
    if (
        receipt["uri"] != expected_uri
        or receipt["sha256"] != sha256(raw).hexdigest()
        or receipt["bytes"] != len(raw)
    ):
        raise LR8HistoricalTransportError(f"{label} object differs")
    return {"body": dict(expected_body), "object": receipt}


def _queue_completion_bytes(
    *, mode: ModeSpec, completion_raw: bytes,
    claim_object: Mapping[str, object], authority_object: Mapping[str, object],
    release_object: Mapping[str, object],
) -> bytes:
    return (
        f"run_id={mode.run_id}\n"
        f"mode={mode.name}\n"
        f"completion_sha256={sha256(completion_raw).hexdigest()}\n"
        f"launch_claim_object_sha256={claim_object['sha256']}\n"
        f"lease_release_authority_object_sha256={authority_object['sha256']}\n"
        f"lease_release_completion_object_sha256={release_object['sha256']}\n"
        "historical_outcome_lease_released=true\n"
        "receipt_only_queue_completion=true\n"
    ).encode("utf-8")


def release_success(*, out: Path, storage: Storage) -> None:
    contract, claim, intent, terminal, validation_raw, completion_raw = (
        _success_files(out)
    )
    mode = _mode(str(contract["mode"]))
    claim_object = claim["object"]
    assert isinstance(claim_object, Mapping)
    live_claim_receipt, live_claim = storage.load_create_once(claim_object)
    if live_claim_receipt != claim_object or live_claim != claim["claim"]:
        raise LR8HistoricalTransportError("release launch claim differs")

    authority_body = _release_authority_body(
        contract=contract, claim=claim, intent=intent, terminal=terminal,
        validation_raw=validation_raw, completion_raw=completion_raw,
    )
    authority_receipt, reopened_authority = storage.publish_create_once(
        uri=mode.release_authority_uri, value=authority_body,
        allow_exact_reopen=True,
    )
    if reopened_authority != authority_body:
        raise LR8HistoricalTransportError("release authority reopen differs")
    authority_wrapper = {"body": authority_body, "object": authority_receipt}
    _write_once(
        out / "lease-release-authority.json", canonical_json(authority_wrapper),
    )

    lease = intent["lease"]
    assert isinstance(lease, Mapping)
    lease_body = lease["body"]
    lease_receipt = lease["object_receipt"]
    assert isinstance(lease_body, Mapping) and isinstance(lease_receipt, Mapping)
    storage.release_generation(lease=lease_body, receipt_value=lease_receipt)
    if storage.generation_is_current(lease_receipt):
        raise LR8HistoricalTransportError(
            "released historical lease generation remains current"
        )

    release_body = _release_completion_body(
        contract=contract, intent=intent, authority_object=authority_receipt,
    )
    release_receipt, reopened_release = storage.publish_create_once(
        uri=mode.release_completion_uri, value=release_body,
        allow_exact_reopen=True,
    )
    if reopened_release != release_body:
        raise LR8HistoricalTransportError("release completion reopen differs")
    release_wrapper = {"body": release_body, "object": release_receipt}
    _write_once(
        out / "lease-release-completion.json", canonical_json(release_wrapper),
    )
    queue_raw = _queue_completion_bytes(
        mode=mode, completion_raw=completion_raw,
        claim_object=claim_object, authority_object=authority_receipt,
        release_object=release_receipt,
    )
    _write_once(out / "queue-completion.txt", queue_raw)
    _write_once(
        out / "queue-completion.sha256",
        f"{sha256(queue_raw).hexdigest()}  queue-completion.txt\n".encode("utf-8"),
    )


def validate_queue_completion(*, out: Path, storage: Storage) -> None:
    contract, claim, intent, terminal, validation_raw, completion_raw = (
        _success_files(out)
    )
    mode = _mode(str(contract["mode"]))
    claim_object = claim["object"]
    assert isinstance(claim_object, Mapping)
    live_claim_receipt, live_claim = storage.load_create_once(claim_object)
    if live_claim_receipt != claim_object or live_claim != claim["claim"]:
        raise LR8HistoricalTransportError("completed launch claim differs")
    authority_body = _release_authority_body(
        contract=contract, claim=claim, intent=intent,
        terminal=terminal,
        validation_raw=validation_raw,
        completion_raw=completion_raw,
    )
    authority_wrapper = _publication_wrapper(
        value=_load(
            out / "lease-release-authority.json", label="release authority",
        ),
        expected_body=authority_body, expected_uri=mode.release_authority_uri,
        label="release authority",
    )
    authority_receipt, authority_value = storage.load_create_once(
        authority_wrapper["object"],  # type: ignore[arg-type]
    )
    if authority_receipt != authority_wrapper["object"] or authority_value != authority_body:
        raise LR8HistoricalTransportError("live release authority differs")
    release_body = _release_completion_body(
        contract=contract, intent=intent,
        authority_object=authority_wrapper["object"],  # type: ignore[arg-type]
    )
    release_wrapper = _publication_wrapper(
        value=_load(
            out / "lease-release-completion.json", label="release completion",
        ),
        expected_body=release_body, expected_uri=mode.release_completion_uri,
        label="release completion",
    )
    release_receipt, release_value = storage.load_create_once(
        release_wrapper["object"],  # type: ignore[arg-type]
    )
    if release_receipt != release_wrapper["object"] or release_value != release_body:
        raise LR8HistoricalTransportError("live release completion differs")
    lease = intent["lease"]
    assert isinstance(lease, Mapping)
    lease_receipt = lease["object_receipt"]
    assert isinstance(lease_receipt, Mapping)
    if storage.generation_is_current(lease_receipt):
        raise LR8HistoricalTransportError("completed lease generation is current")
    queue_path = out / "queue-completion.txt"
    sha_path = out / "queue-completion.sha256"
    if any(path.is_symlink() or not path.is_file() for path in (queue_path, sha_path)):
        raise LR8HistoricalTransportError("queue completion ledger is absent")
    expected_queue = _queue_completion_bytes(
        mode=mode, completion_raw=completion_raw, claim_object=claim_object,
        authority_object=authority_wrapper["object"],  # type: ignore[arg-type]
        release_object=release_wrapper["object"],  # type: ignore[arg-type]
    )
    expected_sha = (
        f"{sha256(expected_queue).hexdigest()}  queue-completion.txt\n"
    ).encode("utf-8")
    if queue_path.read_bytes() != expected_queue or sha_path.read_bytes() != expected_sha:
        raise LR8HistoricalTransportError("queue completion ledger differs")


def _cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    mode_values = sub.add_parser("mode-values")
    mode_values.add_argument("--mode", required=True)
    canonicalize = sub.add_parser("canonicalize-external-json")
    canonicalize.add_argument("--raw", type=Path, required=True)
    canonicalize.add_argument("--output", type=Path, required=True)
    inventory = sub.add_parser("inventory")
    inventory.add_argument("--prefix", required=True)
    inventory.add_argument("--output", type=Path, required=True)
    build = sub.add_parser("validate-build")
    build.add_argument("--metadata", type=Path, required=True)
    build.add_argument("--build-id", required=True)
    build.add_argument("--code-sha", required=True)
    build.add_argument("--image", required=True)
    reuse = sub.add_parser("validate-reuse")
    reuse.add_argument("--job-metadata", type=Path, required=True)
    reuse.add_argument("--executions", type=Path, required=True)
    reuse.add_argument("--schedulers", type=Path, required=True)
    reuse.add_argument("--inventory", type=Path, required=True)
    reuse.add_argument("--governance-inventory", type=Path, required=True)
    validate_source = sub.add_parser("validate-input")
    validate_source.add_argument("--mode", required=True)
    _pin_arguments(validate_source)
    validate_source.add_argument("--output", type=Path, required=True)
    create = sub.add_parser("create-contract")
    create.add_argument("--mode", required=True)
    _pin_arguments(create)
    create.add_argument("--input-validation", type=Path, required=True)
    create.add_argument("--job-metadata", type=Path, required=True)
    create.add_argument("--code-sha", required=True)
    create.add_argument("--build-id", required=True)
    create.add_argument("--image", required=True)
    create.add_argument("--output", type=Path, required=True)
    ready = sub.add_parser("validate-ready")
    _ready_arguments(ready)
    claim = sub.add_parser("create-launch-claim")
    claim.add_argument("--contract", type=Path, required=True)
    claim.add_argument("--lease", type=Path, required=True)
    claim.add_argument("--output", type=Path, required=True)
    intent = sub.add_parser("create-launch-intent")
    intent.add_argument("--contract", type=Path, required=True)
    intent.add_argument("--lease", type=Path, required=True)
    intent.add_argument("--claim", type=Path, required=True)
    intent.add_argument("--output", type=Path, required=True)
    launch = sub.add_parser("launch-script")
    launch.add_argument("--contract", type=Path, required=True)
    launch.add_argument("--intent", type=Path, required=True)
    launch.add_argument("--claim", type=Path, required=True)
    preexecute = sub.add_parser("validate-preexecute")
    _ready_arguments(preexecute)
    preexecute.add_argument("--intent", type=Path, required=True)
    preexecute.add_argument("--claim", type=Path, required=True)
    ledger = sub.add_parser("ledger")
    ledger.add_argument("--mode", required=True)
    ledger.add_argument("--execution", required=True)
    ledger.add_argument("--output", type=Path, required=True)
    ledger_args = sub.add_parser("ledger-values")
    ledger_args.add_argument("--mode", required=True)
    ledger_args.add_argument("--ledger", type=Path, required=True)
    poll = sub.add_parser("poll-state")
    poll.add_argument("--metadata", type=Path, required=True)
    finish = sub.add_parser("finish-success")
    finish.add_argument("--mode", required=True)
    finish.add_argument("--output-dir", type=Path, required=True)
    close = sub.add_parser("close-failure")
    close.add_argument("--mode", required=True)
    close.add_argument("--output-dir", type=Path, required=True)
    close.add_argument("--state", choices=("True", "False"), required=True)
    close.add_argument("--disposition", required=True)
    release = sub.add_parser("release-success")
    release.add_argument("--mode", required=True)
    release.add_argument("--output-dir", type=Path, required=True)
    queue = sub.add_parser("validate-queue-completion")
    queue.add_argument("--mode", required=True)
    queue.add_argument("--output-dir", type=Path, required=True)
    handoff = sub.add_parser("label-fit-handoff-values")
    handoff.add_argument("--output-dir", type=Path, required=True)
    return parser


def _pin_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input-uri", required=True)
    parser.add_argument("--input-generation", required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--input-manifest-sha256", required=True)


def _ready_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--job-metadata", type=Path, required=True)
    parser.add_argument("--executions", type=Path, required=True)
    parser.add_argument("--schedulers", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--governance-inventory", type=Path, required=True)


def _args_pin(args: argparse.Namespace) -> dict[str, str]:
    return input_pin(
        uri=args.input_uri, generation=args.input_generation,
        sha256_value=args.input_sha256,
        manifest_sha256=args.input_manifest_sha256,
    )


def _finish_paths(
    out: Path,
) -> tuple[
    dict[str, object], dict[str, object], dict[str, object], str,
    dict[str, object],
]:
    contract = validate_contract(_load(out / "contract.json", label="contract"))
    claim = validate_launch_claim(
        _load(out / "launch-claim.json", label="launch claim"),
        contract=contract,
    )
    intent = validate_launch_intent(
        _load(out / "launch-intent.json", label="launch intent"),
        contract=contract, launch_claim=claim,
    )
    mode = _mode(str(contract["mode"]))
    execution = parse_ledger(out / "execution.txt", mode=mode)
    terminal = _load(out / "execution-terminal.json", label="terminal execution")
    return contract, claim, intent, execution, terminal


def main(argv: Sequence[str] | None = None) -> int:
    args = _cli().parse_args(argv)
    if args.command == "mode-values":
        mode = _mode(args.mode)
        print(mode.run_id)
        print(mode.output_prefix)
        print(mode.out)
        print(mode.governance_prefix)
    elif args.command == "canonicalize-external-json":
        value = strict_json(args.raw.read_bytes(), label="external JSON")
        _write_once(args.output, canonical_json(value))
    elif args.command == "inventory":
        _write_once(args.output, canonical_json(Storage().inventory(args.prefix)))
    elif args.command == "validate-build":
        validate_build(
            _load(args.metadata, label="build metadata"), build_id=args.build_id,
            code_sha=args.code_sha, image=args.image,
        )
    elif args.command == "validate-reuse":
        validate_reuse(
            job_metadata=_load(args.job_metadata, label="job metadata"),
            executions=json.loads(args.executions.read_bytes()),
            schedulers=json.loads(args.schedulers.read_bytes()),
            inventory=json.loads(args.inventory.read_bytes()),
            governance_inventory=json.loads(
                args.governance_inventory.read_bytes()
            ),
        )
    elif args.command == "validate-input":
        value = validate_input(
            mode=_mode(args.mode), pin=_args_pin(args), storage=Storage(),
        )
        _write_once(args.output, canonical_json(value))
    elif args.command == "create-contract":
        value = create_contract(
            mode=_mode(args.mode), pin=_args_pin(args),
            input_validation=_load(
                args.input_validation, label="input validation",
            ),
            job_metadata=_load(args.job_metadata, label="configured job"),
            code_sha=args.code_sha, build_id=args.build_id, image=args.image,
        )
        _write_once(args.output, canonical_json(value))
    elif args.command == "validate-ready":
        validate_ready(
            contract=_load(args.contract, label="contract"),
            job_metadata=_load(args.job_metadata, label="launch job"),
            executions=json.loads(args.executions.read_bytes()),
            schedulers=json.loads(args.schedulers.read_bytes()),
            inventory=json.loads(args.inventory.read_bytes()),
            governance_inventory=json.loads(
                args.governance_inventory.read_bytes()
            ),
        )
    elif args.command == "create-launch-claim":
        contract = _load(args.contract, label="contract")
        storage = Storage()
        value = create_launch_claim(
            contract=contract, lease_raw=args.lease.read_bytes(),
            publish=lambda uri, body: storage.publish_create_once(
                uri=uri, value=body, allow_exact_reopen=False,
            ),
        )
        _write_once(args.output, canonical_json(value))
    elif args.command == "create-launch-intent":
        contract = _load(args.contract, label="contract")
        value = create_launch_intent(
            contract=contract, lease_raw=args.lease.read_bytes(),
            launch_claim=_load(args.claim, label="launch claim"),
        )
        _write_once(args.output, canonical_json(value))
    elif args.command == "launch-script":
        contract = _load(args.contract, label="contract")
        value = validate_launch_intent(
            _load(args.intent, label="launch intent"), contract=contract,
            launch_claim=_load(args.claim, label="launch claim"),
        )
        print(value["args"][1], end="")  # type: ignore[index]
    elif args.command == "validate-preexecute":
        validate_preexecute(
            contract=_load(args.contract, label="contract"),
            intent=_load(args.intent, label="launch intent"),
            launch_claim=_load(args.claim, label="launch claim"),
            job_metadata=_load(args.job_metadata, label="pre-execution job"),
            executions=json.loads(args.executions.read_bytes()),
            schedulers=json.loads(args.schedulers.read_bytes()),
            inventory=json.loads(args.inventory.read_bytes()),
            governance_inventory=json.loads(
                args.governance_inventory.read_bytes()
            ),
        )
    elif args.command == "ledger":
        mode = _mode(args.mode)
        _write_once(args.output, ledger_line(args.execution, mode.output_prefix))
    elif args.command == "ledger-values":
        mode = _mode(args.mode)
        execution = parse_ledger(args.ledger, mode=mode)
        print(JOB)
        print(execution)
        print(mode.output_prefix)
    elif args.command == "poll-state":
        print(_completion_state(_load(args.metadata, label="execution poll")))
    elif args.command == "finish-success":
        out = args.output_dir
        contract, _claim, intent, execution, terminal = _finish_paths(out)
        mode = _mode(args.mode)
        if mode.name != contract["mode"]:
            raise LR8HistoricalTransportError("finish mode differs")
        storage = Storage()
        pin = contract["input"]
        assert isinstance(pin, Mapping)
        validation, inventory = finish_success(
            contract=contract, intent=intent, execution=execution,
            terminal_metadata=terminal, inventory_loader=storage.inventory,
            object_loader=storage.load_inventory,
            input_loader=lambda: storage.load_pin(pin),  # type: ignore[arg-type]
            claim_loader=storage.load_create_once,
        )
        validation_raw = canonical_json(validation)
        result_objects = validation["result_objects"]
        assert isinstance(result_objects, Mapping)
        label_fit_handoff = _validated_label_fit_handoff(
            mode=mode, value=validation["label_fit_handoff"],
            result_objects=result_objects,
        )
        _write_once(out / "result-inventory.json", canonical_json(inventory))
        _write_once(out / "validation.json", validation_raw)
        if label_fit_handoff is not None:
            local_handoff = _label_fit_local_receipt(
                mode=mode,
                validation_sha256=sha256(validation_raw).hexdigest(),
                handoff=label_fit_handoff,
            )
            _write_once(
                out / "label-fit-handoff.json", canonical_json(local_handoff),
            )
        _write_once(
            out / "completion.txt",
            completion_text(
                mode=mode, disposition=str(validation["disposition"]),
                validation_sha=sha256(validation_raw).hexdigest(),
                label_fit_handoff=label_fit_handoff,
            ),
        )
    elif args.command == "close-failure":
        out = args.output_dir
        contract, _claim, intent, execution, terminal = _finish_paths(out)
        mode = _mode(args.mode)
        if mode.name != contract["mode"]:
            raise LR8HistoricalTransportError("failure mode differs")
        receipt = validate_terminal(
            terminal, execution=execution, contract=contract, intent=intent,
            expected_state=args.state,
        )
        failure = {
            "version": VERSION,
            "mode": mode.name,
            "run_id": mode.run_id,
            "disposition": args.disposition,
            "terminal": receipt,
            "retry_licensed": False,
            "uses_realized_outcomes": True,
            "production_change_licensed": False,
        }
        raw = canonical_json(failure)
        _write_once(out / "failure.json", raw)
        _write_once(
            out / "completion.txt",
            completion_text(
                mode=mode, disposition=args.disposition,
                validation_sha=sha256(raw).hexdigest(),
            ),
        )
    elif args.command == "release-success":
        mode = _mode(args.mode)
        contract = validate_contract(
            _load(args.output_dir / "contract.json", label="contract")
        )
        if contract["mode"] != mode.name:
            raise LR8HistoricalTransportError("release mode differs")
        release_success(out=args.output_dir, storage=Storage())
    elif args.command == "validate-queue-completion":
        mode = _mode(args.mode)
        contract = validate_contract(
            _load(args.output_dir / "contract.json", label="contract")
        )
        if contract["mode"] != mode.name:
            raise LR8HistoricalTransportError("queue mode differs")
        validate_queue_completion(out=args.output_dir, storage=Storage())
    elif args.command == "label-fit-handoff-values":
        for value in label_fit_handoff_values(args.output_dir):
            print(value)
    else:  # pragma: no cover - argparse owns this boundary
        raise LR8HistoricalTransportError("command differs")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        LR8HistoricalTransportError,
        fit_adapter.LR8LabelFitError,
        later_supplier.LR8LaterPeriodError,
        earlier_supplier.LR8ScoreMapError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
