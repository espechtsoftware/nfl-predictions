from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import finish_a7_production_law_transfer as transport  # noqa: E402


class FakeReader:
    def __init__(self) -> None:
        self.values: dict[str, tuple[str, bytes]] = {}
        self.next_generation = 100

    @staticmethod
    def _metadata(uri: str, generation: str, raw: bytes) -> dict:
        return {
            "uri": uri,
            "generation": generation,
            "metageneration": "1",
            "bytes": len(raw),
            "sha256": sha256(raw).hexdigest(),
        }

    def inventory(self, prefix: str) -> dict[str, dict]:
        return {
            uri: self._metadata(uri, generation, raw)
            for uri, (generation, raw) in self.values.items()
            if uri.startswith(prefix)
        }

    def load(self, uri: str, generation: str):
        observed_generation, raw = self.values[uri]
        assert observed_generation == generation
        return self._metadata(uri, generation, raw), raw

    def create_or_validate(self, uri: str, raw: bytes):
        if uri in self.values:
            generation, existing = self.values[uri]
            if existing != raw:
                raise RuntimeError("existing differs")
            return self._metadata(uri, generation, raw), raw
        generation = str(self.next_generation)
        self.next_generation += 1
        self.values[uri] = (generation, raw)
        return self._metadata(uri, generation, raw), raw


def _predecessor() -> dict:
    return {
        "version": "a7-production-law-transfer-predecessor-license-v1",
        "source_run_id": "source",
        "production_law_scorefree_transfer_licensed": True,
        "prospective_shadow_licensed": False,
        "production_change_licensed": False,
    }


def _image() -> str:
    return (
        "us-central1-docker.pkg.dev/nfl-predictions-503414/"
        "nfl-dfs/nfl-dfs@sha256:" + "b" * 64
    )


def _job(*, generation: int, contract: dict | None = None) -> dict:
    if contract is None:
        contract = transport.inert_contract(code_sha="a" * 40, image=_image())
    container = {
        "image": contract["image"],
        "command": contract["command"],
        "args": contract["args"],
        "env": [
            {"name": key, "value": value}
            for key, value in contract["env"].items()
        ],
        "resources": {"limits": contract["resources"]},
    }
    return {
        "metadata": {
            "name": transport.JOB,
            "uid": "job-uid",
            "generation": generation,
        },
        "spec": {"template": {"spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "containers": [container],
                "maxRetries": 0,
                "timeoutSeconds": transport.TIMEOUT_SECONDS,
                "serviceAccountName": transport.SERVICE_ACCOUNT,
            }},
        }}},
    }


def _execution(
    *, phase: str, intent: dict, terminal: str | None = None,
) -> dict:
    contract = intent["contract"]
    container = {
        "image": contract["image"],
        "command": contract["command"],
        "args": contract["args"],
        "env": [
            {"name": key, "value": value}
            for key, value in contract["env"].items()
        ],
        "resources": {"limits": contract["resources"]},
    }
    value = {
        "metadata": {
            "name": f"{transport.JOB}-abc12",
            "generation": 1,
            "labels": {
                "run.googleapis.com/job": transport.JOB,
                "run.googleapis.com/jobUid": intent["job"]["uid"],
                "run.googleapis.com/jobGeneration": intent["job"]["generation"],
            },
        },
        "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "containers": [container],
                "maxRetries": 0,
                "timeoutSeconds": transport.TIMEOUT_SECONDS,
                "serviceAccountName": transport.SERVICE_ACCOUNT,
            }},
        },
    }
    if terminal is not None:
        value["status"] = {
            "observedGeneration": 1,
            "conditions": [{"type": "Completed", "status": terminal}],
            "completionTime": "2026-08-21T12:00:00+00:00",
            "succeededCount": 1 if terminal == "True" else 0,
            "failedCount": 1 if terminal == "False" else 0,
        }
    return value


def _prepare(monkeypatch, tmp_path: Path):
    predecessor = _predecessor()
    monkeypatch.setattr(transport, "_validate_predecessor", lambda: predecessor)
    reader = FakeReader()
    code_sha = "a" * 40
    image = _image()
    claim = transport.create_job_claim(
        code_sha=code_sha,
        image=image,
        build_id="build-12345678",
        build_metadata={"id": "build-12345678"},
        job_before=_job(generation=1),
        executions_before=[],
        schedulers_before=[],
        receipt_path=tmp_path / "job-claim-receipt.json",
        reader=reader,
        build_validator=lambda *args, **kwargs: None,
        commit_validator=lambda value: None,
    )
    deployment = transport.prepare_deployment(
        claim_path=tmp_path / "job-claim-receipt.json",
        job_after=_job(generation=2),
        executions_after=[],
        schedulers_after=[],
        receipt_path=tmp_path / "deployment-receipt.json",
        reader=reader,
    )
    return predecessor, reader, claim, deployment


def test_predecessor_gate_precedes_any_reader(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def reject():
        calls.append("predecessor")
        raise transport.TransferTransportError("not positive")

    monkeypatch.setattr(transport, "_validate_predecessor", reject)
    monkeypatch.setattr(
        transport, "_reader", lambda: calls.append("storage") or FakeReader(),
    )
    with pytest.raises(transport.TransferTransportError, match="not positive"):
        transport.create_job_claim(
            code_sha="bad", image="bad", build_id="bad",
            build_metadata={}, job_before={}, executions_before=[],
            schedulers_before=[], receipt_path=tmp_path / "claim.json",
        )
    assert calls == ["predecessor"]


def test_claim_and_one_time_inert_deployment_are_create_only(
    monkeypatch, tmp_path: Path,
) -> None:
    _, reader, claim, deployment = _prepare(monkeypatch, tmp_path)
    assert claim["object"]["create_only"] is True
    assert deployment["object"]["create_only"] is True
    assert deployment["deployment"]["job"]["generation"] == "2"
    assert deployment["deployment"]["contract"]["args"] == [
        transport.SCRIPT_PATH, "--help",
    ]
    assert deployment["deployment"]["contract"]["max_retries"] == 0
    assert deployment["deployment"]["licenses"] == transport.science.licenses()
    assert set(reader.values) == {
        transport.JOB_CLAIM_URI, transport.DEPLOYMENT_URI,
    }


def test_job_must_be_idle_and_unscheduled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(transport, "_validate_predecessor", _predecessor)
    running = [{"status": {"conditions": []}}]
    with pytest.raises(transport.TransferTransportError, match="not idle"):
        transport.create_job_claim(
            code_sha="a" * 40, image=_image(), build_id="build-12345678",
            build_metadata={}, job_before=_job(generation=1),
            executions_before=running, schedulers_before=[],
            receipt_path=tmp_path / "claim.json", reader=FakeReader(),
            build_validator=lambda *args, **kwargs: None,
            commit_validator=lambda value: None,
        )

    scheduled = [{"httpTarget": {"uri": f"x/jobs/{transport.JOB}:run"}}]
    with pytest.raises(transport.TransferTransportError, match="scheduler"):
        transport.create_job_claim(
            code_sha="a" * 40, image=_image(), build_id="build-12345678",
            build_metadata={}, job_before=_job(generation=1),
            executions_before=[], schedulers_before=scheduled,
            receipt_path=tmp_path / "claim-2.json", reader=FakeReader(),
            build_validator=lambda *args, **kwargs: None,
            commit_validator=lambda value: None,
        )


def test_smoke_intent_and_launch_claim_recheck_exact_empty_generation(
    monkeypatch, tmp_path: Path,
) -> None:
    _, reader, _, deployment = _prepare(monkeypatch, tmp_path)
    intent = transport.create_phase_intent(
        phase="smoke", out=tmp_path,
        deployment_path=tmp_path / "deployment-receipt.json",
        job_current=_job(generation=2), executions_current=[],
        schedulers_current=[], reader=reader,
    )
    assert intent["intent"]["contract"]["args"] == [
        transport.SCRIPT_PATH, "run", "--mode", "real-artifact-smoke",
        "--output-uri", transport.runner.SMOKE_OUTPUT_URI,
    ]
    assert intent["intent"]["expected_prior_executions"] == []
    launch = transport.create_launch_claim(
        phase="smoke", out=tmp_path, job_current=_job(generation=2),
        executions_current=[], schedulers_current=[], reader=reader,
    )
    assert launch["launch_claim"]["execution_name_known"] is False
    assert launch["launch_claim"]["retry_licensed"] is False
    assert deployment["deployment"]["job"] == launch["launch_claim"]["job"]


def test_unexpected_same_generation_execution_poison_closes(
    monkeypatch, tmp_path: Path,
) -> None:
    _, reader, _, deployment = _prepare(monkeypatch, tmp_path)
    row = {
        "metadata": {
            "name": f"{transport.JOB}-foreign",
            "labels": {
                "run.googleapis.com/jobUid": deployment["deployment"]["job"]["uid"],
                "run.googleapis.com/jobGeneration": "2",
            },
        },
        "status": {"conditions": [{"type": "Completed", "status": "True"}]},
    }
    with pytest.raises(
        transport.TransferTransportError, match="unexpected execution",
    ):
        transport.create_phase_intent(
            phase="smoke", out=tmp_path,
            deployment_path=tmp_path / "deployment-receipt.json",
            job_current=_job(generation=2), executions_current=[row],
            schedulers_current=[], reader=reader,
        )


def test_register_execution_is_exact_create_once_no_relaunch(
    monkeypatch, tmp_path: Path,
) -> None:
    _, reader, _, _ = _prepare(monkeypatch, tmp_path)
    intent = transport.create_phase_intent(
        phase="smoke", out=tmp_path,
        deployment_path=tmp_path / "deployment-receipt.json",
        job_current=_job(generation=2), executions_current=[],
        schedulers_current=[], reader=reader,
    )
    transport.create_launch_claim(
        phase="smoke", out=tmp_path, job_current=_job(generation=2),
        executions_current=[], schedulers_current=[], reader=reader,
    )
    response = _execution(phase="smoke", intent=intent["intent"])
    receipt = transport.register_execution(
        phase="smoke", out=tmp_path, execute_response=response, reader=reader,
    )
    assert receipt["execution_claim"]["relaunch_licensed"] is False
    assert (tmp_path / "smoke/executions.txt").read_text() == (
        f"{transport.JOB} {transport.JOB}-abc12\n"
    )
    poisoned = deepcopy(response)
    poisoned["metadata"]["name"] = f"{transport.JOB}-other"
    with pytest.raises(transport.TransferTransportError):
        transport.register_execution(
            phase="smoke", out=tmp_path,
            execute_response=poisoned, reader=reader,
        )


def test_terminal_contract_requires_one_success_and_zero_retries() -> None:
    contract = transport.registered_contract(
        phase="smoke", code_sha="a" * 40, image=_image(), prerequisites={},
    )
    intent = {
        "job": {
            "name": transport.JOB, "uid": "job-uid", "generation": "2",
            "spec_sha256": "c" * 64,
        },
        "contract": contract,
        "contract_sha256": sha256(transport._canonical_json(contract)).hexdigest(),
    }
    execution = _execution(phase="smoke", intent=intent, terminal="True")
    receipt = transport._validate_execution_contract(
        execution, phase="smoke", intent=intent,
        execution_name=f"{transport.JOB}-abc12", require_terminal=True,
    )
    assert receipt["counters"] == {
        "succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0,
    }
    execution["status"]["retriedCount"] = 1
    with pytest.raises(transport.TransferTransportError, match="terminal success"):
        transport._validate_execution_contract(
            execution, phase="smoke", intent=intent,
            execution_name=f"{transport.JOB}-abc12", require_terminal=True,
        )


def test_harvest_body_firewall_rejects_before_storage(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        transport, "_validate_predecessor",
        lambda: calls.append("predecessor") or _predecessor(),
    )
    monkeypatch.setattr(
        transport, "_load_wrapper",
        lambda *args, **kwargs: {
            "intent": {
                "job": {"uid": "u", "generation": "1"},
                "contract": {},
            },
            "execution_claim": {"execution_name": "bad"},
        },
    )
    monkeypatch.setattr(
        transport, "_reader", lambda: calls.append("storage") or FakeReader(),
    )
    with pytest.raises(transport.TransferTransportError):
        transport.harvest_phase(
            phase="smoke", out=Path("/unused"), execution_metadata={},
        )
    assert calls == ["predecessor"]


def test_support_and_full_contracts_pin_prior_objects() -> None:
    smoke = {
        "uri": transport.runner.SMOKE_OUTPUT_URI,
        "generation": "1", "metageneration": "1", "bytes": 10,
        "sha256": "c" * 64,
    }
    query = {"candidates": "d" * 64, "players": "e" * 64}
    support = transport.registered_contract(
        phase="support", code_sha="a" * 40, image=_image(),
        prerequisites={"query_sha256": query, "smoke": smoke},
    )
    assert support["args"][-6:] == [
        "--smoke-generation", "1", "--smoke-sha256", "c" * 64,
        "--smoke-bytes", "10",
    ]
    freeze = {
        "uri": transport.runner.FREEZE_MANIFEST_URI,
        "generation": "2", "metageneration": "1", "bytes": 20,
        "sha256": "f" * 64,
    }
    full = transport.registered_contract(
        phase="full", code_sha="a" * 40, image=_image(),
        prerequisites={"query_sha256": query, "freeze": freeze},
    )
    assert full["args"][-6:] == [
        "--freeze-generation", "2", "--freeze-sha256", "f" * 64,
        "--freeze-bytes", "20",
    ]


def test_prefix_inventory_rejects_any_extra_object() -> None:
    reader = FakeReader()
    reader.values["gs://x/prefix/a"] = ("1", b"{}\n")
    reader.values["gs://x/prefix/extra"] = ("2", b"{}\n")
    with pytest.raises(transport.TransferTransportError, match="inventory differs"):
        transport._validate_prefix_inventory(
            reader, expected={"gs://x/prefix/a"},
        )


def test_launcher_and_watcher_are_reuse_only_terminal_first() -> None:
    launcher = (
        ROOT / "scripts/cloud_a7_production_law_transfer.sh"
    ).read_text(encoding="utf-8")
    watcher = (
        ROOT / "scripts/watch_a7_production_law_transfer_queue.sh"
    ).read_text(encoding="utf-8")
    assert launcher.count("gcloud run jobs update") == 1
    assert "--max-retries 0" in launcher
    assert "gcloud run jobs execute" in launcher and "--async" in launcher
    assert "execute call ambiguous; raw retained and no relaunch" in launcher
    assert "A7_TRANSFER_EXECUTION_RECOVERED" in launcher
    assert "gcloud run jobs create" not in launcher
    assert "gcloud run jobs delete" not in launcher
    assert "historical_outcome_lease" not in launcher + watcher
    assert watcher.index("gate_predecessor || return 2") < watcher.index(
        "gcloud run jobs executions describe"
    )
    # Terminal-first resume: a retained terminal-execution.json harvests
    # immediately, before any cloud poll; live polling harvests only after
    # an observed Completed=True state.
    assert watcher.index('"$FINISHER" harvest') < watcher.index(
        "state=$(phase_state"
    )
    assert watcher.index("state=$(phase_state") < watcher.rindex(
        '"$FINISHER" harvest'
    )


def test_transport_is_packaged_and_build_smoked() -> None:
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cloudbuild = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    for name in (
        "finish_a7_production_law_transfer.py",
        "cloud_a7_production_law_transfer.sh",
        "watch_a7_production_law_transfer_queue.sh",
    ):
        assert docker.count(name) == 2
        assert name in cloudbuild
