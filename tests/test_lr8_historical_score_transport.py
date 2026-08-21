from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import finish_lr8_historical_score_transport as transport  # noqa: E402
from nfl_dfs.research import lr8_label_fit_adapter as fit_adapter  # noqa: E402


CODE_SHA = "a" * 40
BUILD_ID = "12345678-abcd-1234-abcd-123456789abc"
IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/"
    "nfl-dfs/nfl-dfs@sha256:" + "b" * 64
)
INPUT_URI = "gs://nfl-predictions-503414-raw/research/fixture/input.json"
FIT_FREEZE_SHA = "6" * 64
ANATOMY_ARTIFACT_SHA = "7" * 64


def _job(mode: transport.ModeSpec, generation: str = "7") -> dict[str, object]:
    env = transport._configured_env(  # noqa: SLF001
        mode=mode, code_sha=CODE_SHA, build_id=BUILD_ID, image=IMAGE,
    )
    return {
        "metadata": {
            "name": transport.JOB,
            "uid": transport.JOB_UID,
            "generation": generation,
        },
        "spec": {"template": {"spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "containers": [{
                    "image": IMAGE,
                    "command": ["bash"],
                    "args": ["-ceu", transport._default_script(mode)],  # noqa: SLF001
                    "env": [
                        {"name": key, "value": value}
                        for key, value in env.items()
                    ],
                    "resources": {
                        "limits": {"cpu": transport.CPU, "memory": transport.MEMORY}
                    },
                }],
                "maxRetries": 0,
                "timeoutSeconds": transport.TIMEOUT_SECONDS,
                "serviceAccountName": transport.SERVICE_ACCOUNT,
                "volumes": [],
            }},
        }}},
    }


def _pin() -> dict[str, str]:
    return transport.input_pin(
        uri=INPUT_URI, generation="3", sha256_value="c" * 64,
        manifest_sha256="d" * 64,
    )


def _input_validation(mode: transport.ModeSpec) -> dict[str, object]:
    identity = (
        {"candidate_rows": 123, "catalog_universe_sha256": "e" * 64}
        if mode.name == "earlier"
        else {"book_cells": 108, "union_players": 456, "union_rosters": 789}
    )
    return {
        "version": transport.VERSION,
        "mode": mode.name,
        "run_id": mode.run_id,
        "pin": _pin(),
        "object_receipt": {
            "uri": INPUT_URI,
            "generation": "3",
            "sha256": "c" * 64,
            "bytes": 999,
        },
        "validated_identity": identity,
    }


def _contract(mode_name: str) -> dict[str, object]:
    mode = transport.MODES[mode_name]
    return transport.create_contract(
        mode=mode, pin=_pin(), input_validation=_input_validation(mode),
        job_metadata=_job(mode), code_sha=CODE_SHA, build_id=BUILD_ID,
        image=IMAGE,
    )


def _lease_raw(mode_name: str) -> bytes:
    mode = transport.MODES[mode_name]
    body = {
        "version": "historical-outcome-active-v1",
        "run_id": mode.run_id,
        "job": transport.JOB,
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "acquired_at": "2026-08-21T12:00:00+00:00",
    }
    raw_body = transport.canonical_json(body)
    return transport.canonical_json({
        "lease": body,
        "object": {
            "uri": fit_adapter.HISTORICAL_OUTCOME_LEASE_URI,
            "generation": "11",
            "sha256": sha256(raw_body).hexdigest(),
            "bytes": len(raw_body),
            "create_only": True,
        },
    })


def _intent(mode_name: str) -> dict[str, object]:
    return transport.create_launch_intent(
        contract=_contract(mode_name), lease_raw=_lease_raw(mode_name),
        launch_claim=_claim(mode_name),
    )


def _claim(mode_name: str) -> dict[str, object]:
    mode = transport.MODES[mode_name]

    def publish(uri: str, body):
        assert uri == mode.launch_claim_uri
        raw = transport.canonical_json(body)
        return ({
            "uri": uri,
            "generation": "19",
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
            "create_only": True,
        }, dict(body))

    return transport.create_launch_claim(
        contract=_contract(mode_name), lease_raw=_lease_raw(mode_name),
        publish=publish,
    )


def _result_objects(mode_name: str) -> dict[str, dict[str, object]]:
    mode = transport.MODES[mode_name]
    return {
        name: {
            "uri": f"{mode.output_prefix}/{name}",
            "generation": str(index + 1),
            "sha256": f"{index + 1:064x}",
            "bytes": 100 + index,
            "create_only": True,
        }
        for index, name in enumerate(mode.output_names)
    }


def _fit_handoff(
    result_objects: dict[str, dict[str, object]],
) -> dict[str, object]:
    return {
        "schema": transport.LABEL_FIT_HANDOFF_SCHEMA,
        "label_fit_freeze_object": result_objects["label-fit-freeze.json"],
        "label_fit_freeze_sha256": FIT_FREEZE_SHA,
        "anatomy_artifact_sha256": ANATOMY_ARTIFACT_SHA,
        "generation_pinned_reopen_validated": True,
        "independent_fit_replay_validated": True,
    }


def _terminal(
    mode_name: str, *, state: str = "True", generation: str = "7",
) -> dict[str, object]:
    contract = _contract(mode_name)
    intent = _intent(mode_name)
    counters = (
        {"succeededCount": 1}
        if state == "True"
        else {"failedCount": 1}
    )
    return {
        "metadata": {
            "name": transport.JOB + "-abc12",
            "labels": {
                "run.googleapis.com/job": transport.JOB,
                "run.googleapis.com/jobUid": transport.JOB_UID,
                "run.googleapis.com/jobGeneration": generation,
            },
        },
        "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "containers": [{
                    "image": IMAGE,
                    "command": intent["command"],
                    "args": intent["args"],
                    "env": [
                        {"name": key, "value": value}
                        for key, value in contract["job"]["env"].items()
                    ],
                    "resources": {
                        "limits": {"cpu": transport.CPU, "memory": transport.MEMORY}
                    },
                }],
                "maxRetries": 0,
                "timeoutSeconds": transport.TIMEOUT_SECONDS,
                "serviceAccountName": transport.SERVICE_ACCOUNT,
            }},
        },
        "status": {
            "conditions": [{"type": "Completed", "status": state}],
            "completionTime": "2026-08-21T12:30:00Z",
            **counters,
        },
    }


def _materialize_earlier_success(out: Path) -> None:
    mode = transport.MODES["earlier"]
    contract = _contract("earlier")
    claim = _claim("earlier")
    intent = _intent("earlier")
    terminal_metadata = _terminal("earlier")
    terminal = transport.validate_terminal(
        terminal_metadata, execution=transport.JOB + "-abc12",
        contract=contract, intent=intent, expected_state="True",
    )
    result_objects = _result_objects("earlier")
    handoff = _fit_handoff(result_objects)
    validation = {
        "version": transport.VERSION,
        "mode": mode.name,
        "run_id": mode.run_id,
        "disposition": "earlier-score-map-and-fit-validated",
        "contract_sha256": contract["contract_sha256"],
        "intent_sha256": intent["intent_sha256"],
        "terminal": terminal,
        "launch_claim_object": claim["object"],
        "input_object": contract["input_object"],
        "result_objects": result_objects,
        "label_fit_handoff": handoff,
        "result_inventory_sha256": "8" * 64,
        "generation_pinned_reopen_validated": True,
        "independent_runner_validation_replayed": True,
        "uses_realized_outcomes": True,
        "historical_outcome_lease_release_required": True,
        "production_change_licensed": False,
    }
    validation_raw = transport.canonical_json(validation)
    validation_sha = sha256(validation_raw).hexdigest()
    local_receipt = transport._label_fit_local_receipt(  # noqa: SLF001
        mode=mode, validation_sha256=validation_sha, handoff=handoff,
    )
    out.mkdir()
    files = {
        "contract.json": transport.canonical_json(contract),
        "launch-claim.json": transport.canonical_json(claim),
        "launch-intent.json": transport.canonical_json(intent),
        "execution.txt": transport.ledger_line(
            transport.JOB + "-abc12", mode.output_prefix,
        ),
        "execution-terminal.json": transport.canonical_json(terminal_metadata),
        "validation.json": validation_raw,
        "label-fit-handoff.json": transport.canonical_json(local_receipt),
        "completion.txt": transport.completion_text(
            mode=mode, disposition=str(validation["disposition"]),
            validation_sha=validation_sha, label_fit_handoff=handoff,
        ),
    }
    for name, raw in files.items():
        (out / name).write_bytes(raw)


@pytest.mark.parametrize("mode_name", ["earlier", "later"])
def test_two_explicit_modes_build_exact_contract_and_runner(mode_name: str) -> None:
    mode = transport.MODES[mode_name]
    contract = _contract(mode_name)
    intent = _intent(mode_name)
    script = intent["args"][1]
    assert contract["mode"] == mode_name
    assert contract["run_id"] == mode.run_id
    assert contract["expected_output_uris"] == list(mode.output_uris)
    assert contract["job"]["name"] == transport.JOB
    assert contract["job"]["uid"] == transport.JOB_UID
    assert contract["job"]["generation"] == "7"
    assert contract["job"]["spec_sha256"] == transport._job_spec_sha(  # noqa: SLF001
        _job(mode)
    )
    assert f"export {mode.enabled_env}=1" in script
    assert "LR8_HISTORICAL_SCORE_LAUNCH_CLAIM_SHA256=" in script
    assert f"exec python {mode.runner}" in script
    assert f"--run-id {mode.run_id}" in script
    assert f"--{mode.input_flag}-generation 3" in script
    assert "base64 -d" in script
    assert intent["sole_execution"] is True
    assert intent["retry_licensed"] is False
    assert intent["launch_claim"] == _claim(mode_name)
    assert contract["launch_claim_uri"] == mode.launch_claim_uri
    assert contract["lease_release_authority_uri"] == mode.release_authority_uri


@pytest.mark.parametrize("poison", ["generation", "spec", "uid", "env", "args"])
def test_ready_rejects_job_identity_or_spec_poison(poison: str) -> None:
    mode = transport.MODES["earlier"]
    contract = _contract("earlier")
    job = _job(mode)
    if poison == "generation":
        job["metadata"]["generation"] = "8"
    elif poison == "spec":
        job["spec"]["template"]["spec"]["template"]["spec"]["timeoutSeconds"] = "9"
    elif poison == "uid":
        job["metadata"]["uid"] = "different"
    elif poison == "env":
        job["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]["env"][0]["value"] = "different"
    else:
        job["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]["args"] = ["-ceu", "true"]
    with pytest.raises(transport.LR8HistoricalTransportError):
        transport.validate_ready(
            contract=contract, job_metadata=job, executions=[], schedulers=[],
            inventory=[], governance_inventory=[],
        )


def test_reuse_rejects_active_scheduler_and_nonempty_prefix() -> None:
    mode = transport.MODES["earlier"]
    active = [{"status": {"conditions": [
        {"type": "Completed", "status": "Unknown"}
    ]}}]
    with pytest.raises(transport.LR8HistoricalTransportError, match="active"):
        transport.validate_reuse(
            job_metadata=_job(mode), executions=active, schedulers=[], inventory=[],
            governance_inventory=[],
        )
    scheduler = [{"httpTarget": {
        "uri": "https://run.googleapis.com/apis/run.googleapis.com/v1/"
        f"namespaces/x/jobs/{transport.JOB}:run"
    }}]
    with pytest.raises(transport.LR8HistoricalTransportError, match="scheduler"):
        transport.validate_reuse(
            job_metadata=_job(mode), executions=[], schedulers=scheduler,
            inventory=[], governance_inventory=[],
        )
    with pytest.raises(transport.LR8HistoricalTransportError, match="not empty"):
        transport.validate_reuse(
            job_metadata=_job(mode), executions=[], schedulers=[],
            inventory=[{"uri": "gs://unexpected"}], governance_inventory=[],
        )
    with pytest.raises(transport.LR8HistoricalTransportError, match="governance"):
        transport.validate_reuse(
            job_metadata=_job(mode), executions=[], schedulers=[], inventory=[],
            governance_inventory=[{"uri": mode.launch_claim_uri}],
        )


def test_ready_rejects_any_prior_execution_of_prepared_generation() -> None:
    terminal = _terminal("earlier")
    with pytest.raises(transport.LR8HistoricalTransportError, match="already"):
        transport.validate_ready(
            contract=_contract("earlier"),
            job_metadata=_job(transport.MODES["earlier"]),
            executions=[terminal], schedulers=[], inventory=[],
            governance_inventory=[],
        )


def test_preexecute_requires_exact_claim_only_inventory() -> None:
    contract = _contract("later")
    claim = _claim("later")
    intent = _intent("later")
    receipt = claim["object"]
    inventory = [{
        "uri": receipt["uri"], "generation": receipt["generation"],
        "bytes": receipt["bytes"],
    }]
    transport.validate_preexecute(
        contract=contract, intent=intent, launch_claim=claim,
        job_metadata=_job(transport.MODES["later"]), executions=[],
        schedulers=[], inventory=[], governance_inventory=inventory,
    )
    with pytest.raises(transport.LR8HistoricalTransportError, match="exact live"):
        transport.validate_preexecute(
            contract=contract, intent=intent, launch_claim=claim,
            job_metadata=_job(transport.MODES["later"]), executions=[],
            schedulers=[], inventory=[], governance_inventory=[],
        )


@pytest.mark.parametrize("field", ["run_id", "job", "code_sha", "image"])
def test_launch_intent_rejects_lease_identity_poison(field: str) -> None:
    value = json.loads(_lease_raw("earlier"))
    value["lease"][field] = "wrong"
    body_raw = transport.canonical_json(value["lease"])
    value["object"]["sha256"] = sha256(body_raw).hexdigest()
    value["object"]["bytes"] = len(body_raw)
    with pytest.raises(transport.LR8HistoricalTransportError):
        transport.create_launch_intent(
            contract=_contract("earlier"),
            lease_raw=transport.canonical_json(value),
            launch_claim=_claim("earlier"),
        )


@pytest.mark.parametrize("poison", ["generation", "args", "retries", "counter"])
def test_terminal_rejects_execution_binding_poison(poison: str) -> None:
    contract = _contract("later")
    intent = _intent("later")
    terminal = _terminal("later")
    if poison == "generation":
        terminal["metadata"]["labels"]["run.googleapis.com/jobGeneration"] = "8"
    elif poison == "args":
        terminal["spec"]["template"]["spec"]["containers"][0]["args"] = ["-ceu", "true"]
    elif poison == "retries":
        terminal["spec"]["template"]["spec"]["maxRetries"] = 1
    else:
        terminal["status"]["failedCount"] = 1
    with pytest.raises(transport.LR8HistoricalTransportError):
        transport.validate_terminal(
            terminal, execution=transport.JOB + "-abc12", contract=contract,
            intent=intent, expected_state="True",
        )


def test_terminal_failure_is_strict_and_receipt_only_completion() -> None:
    receipt = transport.validate_terminal(
        _terminal("earlier", state="False"),
        execution=transport.JOB + "-abc12",
        contract=_contract("earlier"), intent=_intent("earlier"),
        expected_state="False",
    )
    assert receipt["state"] == "False"
    completion = transport.completion_text(
        mode=transport.MODES["earlier"], disposition="terminal-failed-no-retry",
        validation_sha="f" * 64,
    ).decode()
    assert "uses_realized_outcomes=true" in completion
    assert "receipt_only_completion=true" in completion
    assert "evaluation_report" not in completion
    assert "mean_weekly" not in completion


@pytest.mark.parametrize("mode_name", ["earlier", "later"])
def test_finish_is_terminal_first_exact_inventory_and_dispatches_replay(
    mode_name: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    mode = transport.MODES[mode_name]
    contract = _contract(mode_name)
    intent = _intent(mode_name)
    terminal = _terminal(mode_name)
    calls: list[str] = []
    values = {
        uri: (
            {
                "uri": uri, "generation": str(index + 1),
                "sha256": f"{index + 1:064x}", "bytes": 10 + index,
                "create_only": True,
            },
            {"fixture": uri},
        )
        for index, uri in enumerate(mode.output_uris)
    }
    inventory = [
        {
            "uri": uri, "generation": receipt["generation"],
            "bytes": receipt["bytes"],
        }
        for uri, (receipt, _value) in values.items()
    ]

    def inventory_loader(prefix: str):
        calls.append("inventory")
        assert prefix == mode.output_prefix + "/"
        return inventory

    def object_loader(metadata):
        calls.append("object")
        return values[metadata["uri"]]

    def claim_loader(_receipt):
        calls.append("claim")
        claim = _claim(mode_name)
        return claim["object"], claim["claim"]

    def validator(**kwargs):
        calls.append("replay")
        receipts = {
            name: kwargs["loaded"][name][0] for name in mode.output_names
        }
        if mode_name == "later":
            return receipts, None
        return receipts, {
            "schema": transport.LABEL_FIT_HANDOFF_SCHEMA,
            "label_fit_freeze_object": receipts["label-fit-freeze.json"],
            "label_fit_freeze_sha256": FIT_FREEZE_SHA,
            "anatomy_artifact_sha256": ANATOMY_ARTIFACT_SHA,
            "generation_pinned_reopen_validated": True,
            "independent_fit_replay_validated": True,
        }

    target = (
        "_validate_earlier_results" if mode_name == "earlier"
        else "_validate_later_results"
    )
    monkeypatch.setattr(transport, target, validator)
    validation, observed = transport.finish_success(
        contract=contract, intent=intent,
        execution=transport.JOB + "-abc12", terminal_metadata=terminal,
        inventory_loader=inventory_loader, object_loader=object_loader,
        input_loader=lambda: pytest.fail("patched replay owns input"),
        claim_loader=claim_loader,
    )
    assert calls == [
        "claim", "inventory", *(["object"] * len(mode.output_names)), "replay",
    ]
    assert observed == inventory
    assert validation["mode"] == mode_name
    assert validation["generation_pinned_reopen_validated"] is True
    assert validation["independent_runner_validation_replayed"] is True
    assert validation["production_change_licensed"] is False
    if mode_name == "earlier":
        assert validation["label_fit_handoff"]["label_fit_freeze_sha256"] == (
            FIT_FREEZE_SHA
        )
        assert validation["label_fit_handoff"]["anatomy_artifact_sha256"] == (
            ANATOMY_ARTIFACT_SHA
        )
    else:
        assert validation["label_fit_handoff"] is None


@pytest.mark.parametrize(
    "poison",
    ("fit_object", "fit_freeze_sha", "anatomy_sha", "replay_flag"),
)
def test_label_fit_handoff_rejects_prepare_input_poison(poison: str) -> None:
    mode = transport.MODES["earlier"]
    result_objects = _result_objects("earlier")
    handoff = _fit_handoff(result_objects)
    if poison == "fit_object":
        handoff["label_fit_freeze_object"] = {
            **result_objects["label-fit-freeze.json"], "generation": "99",
        }
    elif poison == "fit_freeze_sha":
        handoff["label_fit_freeze_sha256"] = "not-a-sha"
    elif poison == "anatomy_sha":
        handoff["anatomy_artifact_sha256"] = "not-a-sha"
    else:
        handoff["independent_fit_replay_validated"] = False
    with pytest.raises(transport.LR8HistoricalTransportError):
        transport._validated_label_fit_handoff(  # noqa: SLF001
            mode=mode, value=handoff, result_objects=result_objects,
        )


def test_local_fit_receipt_is_replay_checked_and_exposes_prepare_values(
    tmp_path: Path,
) -> None:
    out = tmp_path / "earlier"
    _materialize_earlier_success(out)
    assert transport.label_fit_handoff_values(out) == (
        transport.MODES["earlier"].output_prefix + "/label-fit-freeze.json",
        "4", f"{4:064x}", "103", FIT_FREEZE_SHA,
        ANATOMY_ARTIFACT_SHA,
    )
    completion = (out / "completion.txt").read_text()
    assert f"label_fit_freeze_sha256={FIT_FREEZE_SHA}\n" in completion
    assert f"anatomy_artifact_sha256={ANATOMY_ARTIFACT_SHA}\n" in completion
    local_path = out / "label-fit-handoff.json"
    poisoned = json.loads(local_path.read_bytes())
    poisoned["anatomy_artifact_sha256"] = "0" * 64
    local_path.write_bytes(transport.canonical_json(poisoned))
    with pytest.raises(
        transport.LR8HistoricalTransportError, match="local label-fit receipt",
    ):
        transport.label_fit_handoff_values(out)


def test_later_validation_rejects_earlier_fit_handoff() -> None:
    result_objects = _result_objects("later")
    with pytest.raises(transport.LR8HistoricalTransportError, match="earlier"):
        transport._validated_label_fit_handoff(  # noqa: SLF001
            mode=transport.MODES["later"], value={"unexpected": True},
            result_objects=result_objects,
        )


def test_finish_never_opens_results_before_strict_terminal() -> None:
    calls: list[str] = []
    terminal = _terminal("later")
    terminal["metadata"]["labels"]["run.googleapis.com/jobUid"] = "wrong"
    with pytest.raises(transport.LR8HistoricalTransportError):
        transport.finish_success(
            contract=_contract("later"), intent=_intent("later"),
            execution=transport.JOB + "-abc12", terminal_metadata=terminal,
            inventory_loader=lambda _prefix: calls.append("inventory"),
            object_loader=lambda _metadata: pytest.fail("must not load"),
            input_loader=lambda: pytest.fail("must not load input"),
            claim_loader=lambda _receipt: pytest.fail("must not load claim"),
        )
    assert calls == []


def test_finish_rejects_missing_or_extra_result_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        transport, "_validate_earlier_results", lambda **_kwargs: {},
    )
    mode = transport.MODES["earlier"]
    one = [{"uri": mode.output_uris[0], "generation": "1", "bytes": 1}]
    with pytest.raises(transport.LR8HistoricalTransportError, match="not exact"):
        transport.finish_success(
            contract=_contract("earlier"), intent=_intent("earlier"),
            execution=transport.JOB + "-abc12",
            terminal_metadata=_terminal("earlier"),
            inventory_loader=lambda _prefix: one,
            object_loader=lambda _metadata: pytest.fail("must not load"),
            input_loader=lambda: pytest.fail("must not load"),
            claim_loader=lambda receipt: (
                _claim("earlier")["object"], _claim("earlier")["claim"],
            ),
        )


def test_release_is_durable_before_delete_and_recovers_missing_queue_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _contract("earlier")
    claim = _claim("earlier")
    intent = _intent("earlier")
    terminal = transport.validate_terminal(
        _terminal("earlier"), execution=transport.JOB + "-abc12",
        contract=contract, intent=intent, expected_state="True",
    )
    validation_raw = b'{"validated":true}\n'
    completion_raw = b"strict-completion\n"
    monkeypatch.setattr(
        transport, "_success_files",
        lambda _out: (
            contract, claim, intent, terminal, validation_raw, completion_raw,
        ),
    )

    class FakeStorage:
        def __init__(self) -> None:
            self.objects = {
                claim["object"]["uri"]: (claim["object"], claim["claim"]),
            }
            self.lease_current = True
            self.events: list[str] = []

        def load_create_once(self, receipt):
            return self.objects[receipt["uri"]]

        def publish_create_once(self, *, uri, value, allow_exact_reopen):
            self.events.append("publish:" + uri.rsplit("/", 1)[-1])
            if uri in self.objects:
                receipt, existing = self.objects[uri]
                assert allow_exact_reopen is True
                assert existing == value
                return receipt, existing
            raw = transport.canonical_json(value)
            generation = "21" if "authority" in uri else "22"
            receipt = {
                "uri": uri, "generation": generation,
                "sha256": sha256(raw).hexdigest(), "bytes": len(raw),
                "create_only": True,
            }
            self.objects[uri] = (receipt, dict(value))
            return receipt, dict(value)

        def release_generation(self, *, lease, receipt_value):
            self.events.append("release-generation")
            assert lease == intent["lease"]["body"]
            assert receipt_value == intent["lease"]["object_receipt"]
            self.lease_current = False

        def generation_is_current(self, _receipt):
            return self.lease_current

    storage = FakeStorage()
    transport.release_success(out=tmp_path, storage=storage)  # type: ignore[arg-type]
    assert storage.events[:2] == [
        "publish:lease-release-authority.json", "release-generation",
    ]
    (tmp_path / "queue-completion.txt").unlink()
    (tmp_path / "queue-completion.sha256").unlink()
    transport.release_success(out=tmp_path, storage=storage)  # type: ignore[arg-type]
    transport.validate_queue_completion(
        out=tmp_path, storage=storage,  # type: ignore[arg-type]
    )
    assert (tmp_path / "queue-completion.txt").is_file()
    assert (tmp_path / "queue-completion.sha256").is_file()


def test_shell_transport_is_update_only_and_lease_ordered() -> None:
    cloud = (ROOT / "scripts/cloud_lr8_historical_score_transport.sh").read_text()
    watcher = (
        ROOT / "scripts/watch_lr8_historical_score_transport_queue.sh"
    ).read_text()
    assert "gcloud run jobs update" in cloud
    assert cloud.count("gcloud run jobs execute") == 1
    for forbidden in (
        "gcloud run jobs deploy", "gcloud run jobs create",
        "gcloud run jobs delete", "gcloud run jobs executions cancel",
    ):
        assert forbidden not in cloud + watcher
    launch = cloud[cloud.index('  launch)'):]
    assert launch.index("validate-ready") < launch.index(" acquire ")
    assert launch.index(" acquire ") < launch.index("create-launch-claim")
    assert launch.index("create-launch-claim") < launch.index(
        "create-launch-intent"
    )
    assert launch.index("create-launch-intent") < launch.index(
        "validate-preexecute"
    ) < launch.index("gcloud run jobs execute")
    assert launch.rindex("gcloud run jobs describe") < launch.index(
        "validate-preexecute"
    )
    assert " abandon " not in cloud
    assert watcher.index("execution-terminal.json") < watcher.index(
        "finish-success"
    )
    assert watcher.index("finish-success") < watcher.index("release-success")
    assert watcher.count(" abandon ") == 2


def test_build_gate_requires_both_existing_runner_smokes() -> None:
    steps = [{
        "status": "SUCCESS",
        "exitCode": 0,
        "args": ["\n".join((
            *transport.full_finish.REQUIRED_BUILD_SMOKES,
            *transport._REQUIRED_BUILD_SMOKES,  # noqa: SLF001
        ))],
    }]
    value = {
        "id": BUILD_ID,
        "status": "SUCCESS",
        "source": {"gitSource": {"revision": CODE_SHA}},
        "sourceProvenance": {"resolvedGitSource": {"revision": CODE_SHA}},
        "results": {"images": [{"digest": "sha256:" + "b" * 64}]},
        "steps": steps,
    }
    transport.validate_build(
        value, build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE,
    )
    steps[0]["args"] = ["\n".join(transport.full_finish.REQUIRED_BUILD_SMOKES)]
    with pytest.raises(transport.LR8HistoricalTransportError, match="runner build"):
        transport.validate_build(
            value, build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE,
        )
