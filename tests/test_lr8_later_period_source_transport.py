from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import finish_lr8_later_period_source_transport as transport  # noqa: E402


CODE_SHA = "a" * 40
BUILD_ID = "12345678-abcd-abcd-abcd-123456789abc"
IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/"
    "nfl-dfs/nfl-dfs@sha256:" + "b" * 64
)
SOURCE_SHA = "c" * 64
FIT_SHA = "d" * 64
ANATOMY_SHA = "e" * 64


def _digest(label: str) -> str:
    return sha256(label.encode()).hexdigest()


def _receipt(uri: str, label: str | None = None) -> dict[str, object]:
    raw = (uri if label is None else label).encode()
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _input_validation() -> dict[str, object]:
    body: dict[str, object] = {
        "schema": transport.INPUT_VERSION,
        "base_source_object": {
            "uri": transport.later.BASE_SOURCE_URI,
            "generation": transport.later.BASE_SOURCE_GENERATION,
            "sha256": transport.later.BASE_SOURCE_SHA256,
            "bytes": transport.later.BASE_SOURCE_BYTES,
        },
        "fit_freeze_object": _receipt(
            "gs://lr8-later-fixture/label-fit-freeze.json"
        ),
        "fit_freeze_sha256": FIT_SHA,
        "anatomy_artifact_sha256": ANATOMY_SHA,
        "base_source_reopened": True,
        "fit_freeze_reopened": True,
        "uses_realized_later_period_outcomes": False,
        "historical_outcome_lease_acquired": False,
    }
    body["validation_sha256"] = sha256(
        transport.canonical_json(body)
    ).hexdigest()
    return body


def _configured_job() -> dict[str, object]:
    env = transport.configured_env(
        image=IMAGE, code_sha=CODE_SHA, build_id=BUILD_ID,
    )
    return {
        "metadata": {
            "name": transport.JOB,
            "uid": transport.JOB_UID,
            "generation": 2,
        },
        "spec": {"template": {"spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "containers": [{
                    "image": IMAGE,
                    "command": ["bash"],
                    "args": ["-ceu", transport.DISABLED_SCRIPT],
                    "env": [
                        {"name": key, "value": value}
                        for key, value in env.items()
                    ],
                    "resources": {
                        "limits": {
                            "cpu": transport.CPU,
                            "memory": transport.MEMORY,
                        },
                    },
                    "workingDir": "",
                    "volumeMounts": [],
                }],
                "serviceAccountName": transport.SERVICE_ACCOUNT,
                "maxRetries": 0,
                "timeoutSeconds": transport.TIMEOUT_SECONDS,
                "volumes": [],
            }},
        }}},
    }


@pytest.fixture()
def contract() -> dict[str, object]:
    return transport.create_contract(
        job_metadata=_configured_job(),
        input_validation=_input_validation(),
        code_sha=CODE_SHA,
        build_id=BUILD_ID,
        image=IMAGE,
    )


def _summary(execution: str) -> dict[str, object]:
    return {
        "execution": execution,
        "job": transport.JOB,
        "job_uid": transport.JOB_UID,
        "job_generation": "2",
        "job_spec_sha256": transport._job_spec_sha(_configured_job()),  # noqa: SLF001
        "state": "True",
        "counters": {
            "succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0,
        },
        "metadata_sha256": _digest(execution),
    }


def _source_completion() -> dict[str, object]:
    source = _receipt(transport.SOURCE_URI)
    return {
        "schema": transport.SOURCE_COMPLETION_VERSION,
        "attempt_id": transport.ATTEMPT_ID,
        "execution": _summary(transport.JOB + "-r0000"),
        "source_object": source,
        "source_freeze_sha256": SOURCE_SHA,
        "prefix_receipts": [source],
        "strict_terminal_success": True,
        "uses_realized_later_period_outcomes": False,
        "historical_outcome_lease_acquired": False,
    }


def _smoke_completion() -> dict[str, object]:
    smoke = _receipt(transport.SMOKE_URI)
    execution_object = _receipt(transport.SMOKE_EXECUTION_METADATA_URI)
    ledger_object = _receipt(transport.SMOKE_FINISH_LEDGER_URI)
    terminal: dict[str, object] = {
        "schema": transport.later.SMOKE_TERMINAL_VERSION,
        "execution_name": transport.JOB + "-s0000",
        "execution_metadata_object": execution_object,
        "finish_ledger_object": ledger_object,
        "smoke_object": smoke,
        "smoke_sha256": _digest("smoke-cell"),
        "source_freeze_sha256": SOURCE_SHA,
        "anatomy_artifact_sha256": ANATOMY_SHA,
        "task_count": 1,
        "succeeded_count": 1,
        "failed_count": 0,
        "cancelled_count": 0,
        "retried_count": 0,
        "completed_condition": "True",
        "strict_terminal_success": True,
    }
    terminal["terminal_sha256"] = sha256(
        transport.canonical_json(terminal)
    ).hexdigest()
    terminal_raw = transport.canonical_json(terminal)
    terminal_object = {
        "uri": transport.SMOKE_TERMINAL_URI,
        "generation": "1",
        "sha256": sha256(terminal_raw).hexdigest(),
        "bytes": len(terminal_raw),
    }
    receipts = transport._merge_receipts(  # noqa: SLF001
        _source_completion()["prefix_receipts"],
        [smoke, execution_object, ledger_object, terminal_object],
    )
    return {
        "schema": transport.SMOKE_COMPLETION_VERSION,
        "attempt_id": transport.ATTEMPT_ID,
        "execution": _summary(transport.JOB + "-s0000"),
        "smoke_object": smoke,
        "smoke_cell_sha256": terminal["smoke_sha256"],
        "source_freeze_sha256": SOURCE_SHA,
        "anatomy_artifact_sha256": ANATOMY_SHA,
        "smoke_terminal": terminal,
        "smoke_terminal_object": terminal_object,
        "smoke_terminal_manifest_sha256": terminal["terminal_sha256"],
        "prefix_receipts": receipts,
        "strict_terminal_success": True,
        "uses_realized_later_period_outcomes": False,
        "historical_outcome_lease_acquired": False,
    }


def _terminal(
    *, contract: dict[str, object], execution: str, script: str,
) -> dict[str, object]:
    return {
        "metadata": {
            "name": execution,
            "labels": {
                "run.googleapis.com/job": transport.JOB,
                "run.googleapis.com/jobUid": transport.JOB_UID,
                "run.googleapis.com/jobGeneration": contract["job_generation"],
            },
        },
        "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "containers": [{
                    "image": IMAGE,
                    "command": ["bash"],
                    "args": ["-ceu", script],
                    "env": [
                        {"name": key, "value": value}
                        for key, value in contract["env"].items()
                    ],
                    "resources": {
                        "limits": {
                            "cpu": transport.CPU,
                            "memory": transport.MEMORY,
                        },
                    },
                }],
                "serviceAccountName": transport.SERVICE_ACCOUNT,
                "maxRetries": 0,
                "timeoutSeconds": transport.TIMEOUT_SECONDS,
            }},
        },
        "status": {
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1,
            "failedCount": 0,
            "cancelledCount": 0,
            "retriedCount": 0,
        },
    }


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(transport.canonical_json(value))


def test_contract_binds_exact_generation_spec_source_build_and_image(
    contract: dict[str, object],
) -> None:
    job = _configured_job()
    assert contract["job_generation"] == "2"
    assert contract["job_spec_sha256"] == transport._job_spec_sha(job)  # noqa: SLF001
    assert contract["code_sha"] == CODE_SHA
    assert contract["build_id"] == BUILD_ID
    assert contract["image"] == IMAGE
    for poison in ("generation", "args", "env"):
        value = deepcopy(job)
        if poison == "generation":
            value["metadata"]["generation"] = 3
        elif poison == "args":
            value["spec"]["template"]["spec"]["template"]["spec"][
                "containers"
            ][0]["args"] = ["-ceu", "true"]
        else:
            value["spec"]["template"]["spec"]["template"]["spec"][
                "containers"
            ][0]["env"][0]["value"] = "wrong"
        with pytest.raises(transport.LR8LaterTransportError):
            transport.validate_configured_job(value, contract=contract)


def test_build_requires_exact_direct_git_source_and_immutable_digest() -> None:
    digest = IMAGE.rsplit("@", 1)[1]
    build = {
        "id": BUILD_ID,
        "status": "SUCCESS",
        "source": {"gitSource": {"revision": CODE_SHA}},
        "sourceProvenance": {"resolvedGitSource": {"revision": CODE_SHA}},
        "results": {"images": [{"digest": digest}]},
        "steps": [{
            "status": "SUCCESS",
            "exitCode": 0,
            "args": ["\n".join(transport.REQUIRED_BUILD_SMOKES)],
        }],
    }
    transport.validate_build(
        build, build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE,
    )
    for path, value in (
        (("sourceProvenance", "resolvedGitSource", "revision"), "f" * 40),
        (("results", "images"), [{"digest": "sha256:" + "0" * 64}]),
        (("status",), "FAILURE"),
    ):
        poison = deepcopy(build)
        target = poison
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        with pytest.raises(transport.LR8LaterTransportError):
            transport.validate_build(
                poison, build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE,
            )
    missing = deepcopy(build)
    missing["steps"][0]["args"] = [transport.REQUIRED_BUILD_SMOKES[0]]
    with pytest.raises(
        transport.LR8LaterTransportError, match="integration smokes",
    ):
        transport.validate_build(
            missing, build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE,
        )


def test_wrong_base_source_object_fails_before_any_body_read() -> None:
    class NoRead:
        def load(self, _receipt):
            pytest.fail("wrong base identity must fail before storage read")

    with pytest.raises(
        transport.LR8LaterTransportError, match="base source-lock object",
    ):
        transport.validate_inputs(
            base_source=_receipt("gs://wrong/base.json"),
            fit_freeze=_receipt("gs://fixture/fit.json"),
            fit_freeze_sha256=FIT_SHA,
            anatomy_artifact_sha256=ANATOMY_SHA,
            storage=NoRead(),  # type: ignore[arg-type]
        )


def test_scripts_bind_terminal_authority_and_aggregate_fit_hash(
    contract: dict[str, object],
) -> None:
    source = _source_completion()
    smoke = _smoke_completion()
    source_script = transport.source_script(contract)
    smoke_script = transport.smoke_script(contract, source)
    cell_script = transport.cell_script(0, contract, source, smoke)
    cells = [_receipt(transport.cell_uri(index)) for index in range(54)]
    manifest = transport.canonical_json({
        "schema": "lr8-later-terminal-cell-manifest-v1",
        "strict_terminal_success": True,
        "cells": cells,
    })
    aggregate_script = transport.aggregate_script(
        contract, source, smoke, manifest,
    )
    assert " freeze-source " in source_script
    assert "--mode smoke --cell-index 0" in smoke_script
    assert "--mode full --cell-index 0" in cell_script
    for flag in (
        "--smoke-terminal-uri", "--smoke-terminal-generation",
        "--smoke-terminal-sha256", "--smoke-terminal-bytes",
        "--smoke-terminal-manifest-sha256",
    ):
        assert flag in cell_script
        assert flag in aggregate_script
    assert f"--fit-freeze-sha256 {FIT_SHA}" in cell_script
    assert f"--fit-freeze-sha256 {FIT_SHA}" in aggregate_script
    assert "--cell-manifest-sha256" in aggregate_script
    assert "base64 -d" in aggregate_script
    assert "sha256sum" in aggregate_script


@pytest.mark.parametrize(
    "poison", ["generation", "args", "retries", "counter", "uid"],
)
def test_terminal_rejects_generation_spec_retry_and_counter_poison(
    contract: dict[str, object], poison: str,
) -> None:
    script = transport.source_script(contract)
    execution = transport.JOB + "-abc12"
    terminal = _terminal(
        contract=contract, execution=execution, script=script,
    )
    if poison == "generation":
        terminal["metadata"]["labels"][
            "run.googleapis.com/jobGeneration"
        ] = "3"
    elif poison == "args":
        terminal["spec"]["template"]["spec"]["containers"][0][
            "args"
        ] = ["-ceu", "true"]
    elif poison == "retries":
        terminal["spec"]["template"]["spec"]["maxRetries"] = 1
    elif poison == "counter":
        terminal["status"]["retriedCount"] = 1
    else:
        terminal["metadata"]["labels"]["run.googleapis.com/jobUid"] = "wrong"
    with pytest.raises(transport.LR8LaterTransportError):
        transport.validate_terminal(
            terminal, execution=execution, script=script, contract=contract,
        )


def test_finish_source_is_terminal_first(
    tmp_path: Path, contract: dict[str, object],
) -> None:
    _write(tmp_path / "contract.json", contract)
    script = transport.source_script(contract)
    _write(
        tmp_path / "source-launch-intent.json",
        transport.create_intent(
            stage="source", index=None, script=script, contract=contract,
        ),
    )
    execution = transport.JOB + "-abc12"
    (tmp_path / "source-execution.txt").write_bytes(
        transport.ledger_line(execution, transport.SOURCE_URI)
    )
    terminal = _terminal(
        contract=contract, execution=execution, script=script,
    )
    terminal["status"]["conditions"][0]["status"] = "False"

    class NoStorage:
        def inventory(self, _prefix):
            pytest.fail("terminal failure must precede inventory")

    with pytest.raises(
        transport.LR8LaterTransportError, match="strict terminal success",
    ):
        transport.finish_source(
            out=tmp_path, metadata=terminal,
            storage=NoStorage(),  # type: ignore[arg-type]
        )


def _write_cell_launches(
    out: Path, contract: dict[str, object], *, poison_last: bool,
) -> list[dict[str, object]]:
    source = _source_completion()
    smoke = _smoke_completion()
    _write(out / "contract.json", contract)
    _write(out / "source-completion.json", source)
    _write(out / "smoke-completion.json", smoke)
    summaries = []
    for index in range(54):
        script = transport.cell_script(index, contract, source, smoke)
        execution = transport.JOB + f"-a{index:04d}"
        _write(
            out / "cell-launch-intents" / f"cell-{index:02d}.json",
            transport.create_intent(
                stage="cell", index=index, script=script, contract=contract,
            ),
        )
        ledger = out / "cell-execution-ledgers" / f"cell-{index:02d}.txt"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_bytes(
            transport.ledger_line(execution, transport.cell_uri(index))
        )
        terminal = _terminal(
            contract=contract, execution=execution, script=script,
        )
        summaries.append(transport.validate_terminal(
            terminal, execution=execution, script=script, contract=contract,
        ))
        if poison_last and index == 53:
            terminal["status"]["retriedCount"] = 1
        _write(
            out / "cell-terminal-metadata" / f"cell-{index:02d}.json",
            terminal,
        )
    return summaries


def _write_cell_completion(
    out: Path, summaries: list[dict[str, object]],
) -> dict[str, object]:
    cells = [_receipt(transport.cell_uri(index)) for index in range(54)]
    manifest_raw = transport.canonical_json({
        "schema": "lr8-later-terminal-cell-manifest-v1",
        "strict_terminal_success": True,
        "cells": cells,
    })
    manifest_object = {
        "uri": transport.CELL_MANIFEST_URI,
        "generation": "1",
        "sha256": sha256(manifest_raw).hexdigest(),
        "bytes": len(manifest_raw),
    }
    completion = {
        "schema": transport.CELL_COMPLETION_VERSION,
        "attempt_id": transport.ATTEMPT_ID,
        "cell_count": 54,
        "execution_terminals": summaries,
        "cell_manifest_object": manifest_object,
        "cell_manifest_sha256": sha256(manifest_raw).hexdigest(),
        "cell_objects": cells,
        "prefix_receipts": transport._merge_receipts(  # noqa: SLF001
            cells, [manifest_object],
        ),
        "all_cells_strict_terminal_success": True,
        "all_cell_bodies_generation_pinned": True,
        "uses_realized_later_period_outcomes": False,
        "historical_outcome_lease_acquired": False,
    }
    (out / "terminal-cell-manifest.json").write_bytes(manifest_raw)
    _write(out / "cell-completion.json", completion)
    return completion


def test_all_54_terminals_are_validated_before_any_cell_body_read(
    tmp_path: Path, contract: dict[str, object],
) -> None:
    _write_cell_launches(tmp_path, contract, poison_last=True)

    class NoStorage:
        def inventory(self, _prefix):
            pytest.fail("all terminal receipts must validate before inventory")

    with pytest.raises(transport.LR8LaterTransportError, match="counters"):
        transport.finish_cells(
            out=tmp_path,
            terminal_dir=tmp_path / "cell-terminal-metadata",
            storage=NoStorage(),  # type: ignore[arg-type]
        )


def test_cell_completion_resume_replays_all_ordered_terminal_bindings(
    tmp_path: Path, contract: dict[str, object],
) -> None:
    summaries = _write_cell_launches(tmp_path, contract, poison_last=False)
    completion = _write_cell_completion(tmp_path, summaries)

    class NoStorage:
        def inventory(self, _prefix):
            pytest.fail("valid completion replay needs no GCS read")

    assert transport.finish_cells(
        out=tmp_path,
        terminal_dir=tmp_path / "cell-terminal-metadata",
        storage=NoStorage(),  # type: ignore[arg-type]
    ) == completion
    first = tmp_path / "cell-terminal-metadata/cell-00.json"
    second = tmp_path / "cell-terminal-metadata/cell-01.json"
    first_raw, second_raw = first.read_bytes(), second.read_bytes()
    first.write_bytes(second_raw)
    second.write_bytes(first_raw)
    with pytest.raises(transport.LR8LaterTransportError):
        transport.finish_cells(
            out=tmp_path,
            terminal_dir=tmp_path / "cell-terminal-metadata",
            storage=NoStorage(),  # type: ignore[arg-type]
        )


def test_cell_ledger_is_exact_ordered_and_nonpermutable(
    tmp_path: Path,
) -> None:
    for index in range(54):
        path = tmp_path / "cell-execution-ledgers" / f"cell-{index:02d}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(transport.ledger_line(
            transport.JOB + f"-b{index:04d}", transport.cell_uri(index),
        ))
    rows = transport.assemble_cell_ledger(tmp_path).splitlines()
    assert len(rows) == 54
    assert rows[0].decode().endswith("cell-00-2023-w01/cell.json")
    assert rows[-1].decode().endswith("cell-53-2025-w18/cell.json")
    first = tmp_path / "cell-execution-ledgers/cell-00.txt"
    second = tmp_path / "cell-execution-ledgers/cell-01.txt"
    first_raw, second_raw = first.read_bytes(), second.read_bytes()
    first.write_bytes(second_raw)
    second.write_bytes(first_raw)
    with pytest.raises(transport.LR8LaterTransportError):
        transport.assemble_cell_ledger(tmp_path)


def test_cell_manifest_rejects_permutation() -> None:
    cells = [_receipt(transport.cell_uri(index)) for index in range(54)]
    manifest = {
        "schema": "lr8-later-terminal-cell-manifest-v1",
        "strict_terminal_success": True,
        "cells": cells,
    }
    transport._validate_cell_manifest(manifest)  # noqa: SLF001
    manifest["cells"][0], manifest["cells"][1] = (
        manifest["cells"][1], manifest["cells"][0],
    )
    with pytest.raises(transport.LR8LaterTransportError, match="order"):
        transport._validate_cell_manifest(manifest)  # noqa: SLF001


def test_external_json_accepts_arrays_but_rejects_duplicate_keys() -> None:
    assert transport.strict_json_value(b"[]", label="census") == []
    with pytest.raises(transport.LR8LaterTransportError, match="strict JSON"):
        transport.strict_json_value(b'{"a":1,"a":2}', label="census")


def test_local_create_once_recovery_accepts_only_identical_bytes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "immutable.json"
    transport._write_once(path, b"exact")  # noqa: SLF001
    transport._write_once(path, b"exact")  # noqa: SLF001
    with pytest.raises(transport.LR8LaterTransportError, match="differs"):
        transport._write_once(path, b"poison")  # noqa: SLF001


def test_gcs_create_once_recovery_is_generation_pinned_and_exact() -> None:
    objects: dict[str, tuple[int, bytes]] = {}

    class Blob:
        def __init__(self, name: str, generation: int | None = None):
            self.name = name
            self.requested_generation = generation
            self.generation = generation

        def upload_from_string(self, raw: bytes, *, if_generation_match: int):
            assert if_generation_match == 0
            if self.name in objects:
                raise RuntimeError("precondition failed")
            objects[self.name] = (7, raw)
            self.generation = 7

        def reload(self, *, if_generation_match: int | None = None):
            generation, _raw = objects[self.name]
            if self.requested_generation is not None:
                assert self.requested_generation == generation
            if if_generation_match is not None:
                assert if_generation_match == generation
            self.generation = generation

        def download_as_bytes(self, *, if_generation_match: int):
            generation, raw = objects[self.name]
            assert if_generation_match == generation
            return raw

    class Bucket:
        def blob(self, name: str, generation: int | None = None):
            return Blob(name, generation)

    class Client:
        def bucket(self, _name: str):
            return Bucket()

    storage = object.__new__(transport.Storage)
    storage.client = Client()
    uri = "gs://fixture/recovery.json"
    first = storage.publish(uri, b"exact")
    assert storage.publish(uri, b"exact") == first
    with pytest.raises(
        transport.LR8LaterTransportError, match="existing bytes differ",
    ):
        storage.publish(uri, b"poison")


def test_final_completion_is_exact_and_watcher_replays_before_finished() -> None:
    body = {
        "schema": transport.FINAL_COMPLETION_VERSION,
        "attempt_id": transport.ATTEMPT_ID,
        "execution": _summary(transport.JOB + "-z0000"),
        "book_freeze_object": _receipt(transport.BOOK_FREEZE_URI),
        "book_freeze_sha256": _digest("book-freeze"),
        "cell_count": 54,
        "book_cell_count": 108,
        "strict_terminal_success": True,
        "all_inputs_generation_pinned": True,
        "later_period_score_read_licensed": True,
        "uses_realized_later_period_outcomes": False,
        "historical_outcome_lease_acquired": False,
        "production_change_licensed": False,
    }
    assert transport._final_completion(body) == body  # noqa: SLF001
    poison = deepcopy(body)
    poison["all_inputs_generation_pinned"] = False
    with pytest.raises(transport.LR8LaterTransportError):
        transport._final_completion(poison)  # noqa: SLF001
    with pytest.raises(transport.LR8LaterTransportError, match="strict JSON"):
        transport.strict_json_value(b'{"schema":', label="truncated completion")
    watcher = (
        ROOT / "scripts/watch_lr8_later_period_source_queue.sh"
    ).read_text()
    assert watcher.index("validate-final --output-dir") < watcher.index(
        "LR8_LATER_PERIOD_SOURCE_FINISHED"
    )


def test_shell_is_update_only_default_off_bounded_and_terminal_ordered() -> None:
    launcher = (
        ROOT / "scripts/cloud_lr8_later_period_source.sh"
    ).read_text()
    watcher = (
        ROOT / "scripts/watch_lr8_later_period_source_queue.sh"
    ).read_text()
    assert launcher.count("gcloud run jobs update") == 1
    assert launcher.count("gcloud run jobs execute") == 1
    for forbidden in (
        "gcloud run jobs deploy", "gcloud run jobs create",
        "gcloud run jobs delete", "gcloud run jobs executions cancel",
    ):
        assert forbidden not in launcher + watcher
    assert "LR8_LATER_PERIOD_TRANSPORT_DISABLED" in launcher
    assert "literal --execute is required" in launcher + watcher
    assert "LR8_LATER_PERIOD_TRANSPORT_ENABLED" in launcher + watcher
    assert "--tasks 1 --parallelism 1" in launcher
    assert "--max-retries 0" in launcher
    assert "LR8_LATER_MAX_IN_FLIGHT:-6" in launcher
    assert '"$MAX_IN_FLIGHT" -le 8' in launcher
    assert "flock -n 9" in launcher
    assert "for index in $(seq 0 53)" in launcher
    assert "for index in $(seq 0 53)" in watcher
    assert "validate_ready_stage cells" in launcher
    assert "validate_cell_control_plane" in launcher
    assert "finish-source" in watcher
    assert "finish-smoke" in watcher
    assert "finish-cells" in watcher
    assert "finish-aggregate" in watcher
    assert "validate-final" in watcher
    assert watcher.index("finish-source") < watcher.index("finish-smoke")
    assert watcher.index("finish-smoke") < watcher.index("launch-cells")
    assert watcher.index("launch-cells") < watcher.index("finish-cells")
    assert watcher.index("finish-cells") < watcher.index(
        "ensure_launched aggregate"
    )
    assert watcher.index("ensure_launched aggregate") < watcher.index(
        "finish-aggregate"
    )
    assert "gcloud storage" not in watcher
    assert "gsutil" not in watcher
    assert "run_lr8_later_period_source.py" in transport.source_script(
        transport.create_contract(
            job_metadata=_configured_job(),
            input_validation=_input_validation(),
            code_sha=CODE_SHA,
            build_id=BUILD_ID,
            image=IMAGE,
        )
    )
