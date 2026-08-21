from __future__ import annotations

import base64
import copy
from datetime import datetime, timezone
from hashlib import sha256
import json
import lzma
from pathlib import Path
import shutil
import sys
from typing import Any

from google.api_core.exceptions import NotFound
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import recover_a7_v2_empty_preflight_shell as recovery  # noqa: E402


HISTORICAL_FINISHER = "scripts/finish_a7_select_ladder.py"
HISTORICAL_FINISHER_FIXTURE = (
    ROOT / "tests/fixtures/a7_v2_empty_preflight_shell"
    / "finish_a7_select_ladder.py.xz.b64"
)


class FakeBlob:
    def __init__(self, client: "FakeStorage", name: str) -> None:
        self.client = client
        self.name = name

    def reload(self) -> None:
        self.client.events.append(("reload", self.name))
        if self.name not in self.client.objects:
            raise NotFound("missing")


class FakeBucket:
    def __init__(self, client: "FakeStorage", name: str) -> None:
        self.client = client
        self.name = name

    def blob(self, name: str) -> FakeBlob:
        return FakeBlob(self.client, name)


class FakeStorage:
    def __init__(self) -> None:
        self.objects: set[str] = set()
        self.list_override: list[str] | None = None
        self.events: list[tuple[str, str]] = []

    def bucket(self, name: str) -> FakeBucket:
        assert name == "nfl-predictions-503414-raw"
        return FakeBucket(self, name)

    def list_blobs(self, bucket: str, *, prefix: str) -> list[FakeBlob]:
        assert bucket == "nfl-predictions-503414-raw"
        self.events.append(("list", prefix))
        names = self.list_override
        if names is None:
            names = sorted(name for name in self.objects if name.startswith(prefix))
        return [FakeBlob(self, name) for name in names]


def _copy(root: Path, relative: str) -> None:
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / relative, destination)


def _historical_finisher_bytes() -> bytes:
    encoded = b"".join(HISTORICAL_FINISHER_FIXTURE.read_bytes().split())
    raw = lzma.decompress(
        base64.b64decode(encoded, validate=True)
    )
    assert sha256(raw).hexdigest() == recovery.FROZEN_SOURCE_SHA256[
        HISTORICAL_FINISHER
    ]
    return raw


class Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "repo"
        for relative in (
            recovery.PROTOCOL_PATH,
            *recovery.FROZEN_SOURCE_SHA256,
            recovery.ANCHOR_JOB_PATH,
            recovery.ANCHOR_EXECUTIONS_PATH,
            recovery.ANCHOR_LAST_EXECUTION_PATH,
        ):
            if relative == HISTORICAL_FINISHER:
                destination = self.root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(_historical_finisher_bytes())
            else:
                _copy(self.root, relative)

        self.shell = (
            self.root / "reports/a7-select-ladder-preflight-runs"
            / recovery.RUN_ID
        )
        self.shell.mkdir(parents=True)
        self.log = tmp_path / "a7-v2.log"
        self.log.write_bytes(b"")
        self.archive = (
            self.root / "reports/a7-select-ladder-preflight-recovery-runs"
            / recovery.RECOVERY_ID
        )
        self.historical_out = (
            self.root / "reports/a7-select-ladder-runs" / recovery.RUN_ID
        )
        self.historical_pending = (
            self.root / "reports/a7-select-ladder-runs"
            / f".{recovery.RUN_ID}.prepare.pending"
        )
        self.expected_shell_stat = recovery._stat_receipt(self.shell)
        self.expected_log_stat = recovery._stat_receipt(self.log)
        self.storage = FakeStorage()

        self.job = json.loads(
            (self.root / recovery.ANCHOR_JOB_PATH).read_text(encoding="utf-8")
        )
        self.job.setdefault("status", {})["latestCreatedExecution"] = {
            "name": recovery.LAST_EXECUTION,
            "creationTimestamp": "2026-08-21T00:04:13.549125Z",
            "completionTimestamp": "2026-08-21T00:17:24.845961Z",
            "completionStatus": "EXECUTION_SUCCEEDED",
        }
        prior = json.loads(
            (self.root / recovery.ANCHOR_EXECUTIONS_PATH).read_text(
                encoding="utf-8"
            )
        )
        last = json.loads(
            (self.root / recovery.ANCHOR_LAST_EXECUTION_PATH).read_text(
                encoding="utf-8"
            )
        )
        self.executions = [last, *prior]
        self.schedulers: list[dict[str, Any]] = []
        self.processes: list[dict[str, Any]] = []

    def run(self, **overrides: Any) -> dict[str, Any]:
        options = {
            "execute": True,
            "root": self.root,
            "shell": self.shell,
            "historical_out": self.historical_out,
            "historical_pending": self.historical_pending,
            "archive": self.archive,
            "log_path": self.log,
            "expected_shell_stat": self.expected_shell_stat,
            "expected_log_stat": self.expected_log_stat,
            "client": self.storage,
            "job_loader": lambda: copy.deepcopy(self.job),
            "executions_loader": lambda: copy.deepcopy(self.executions),
            "schedulers_loader": lambda: copy.deepcopy(self.schedulers),
            "process_loader": lambda: copy.deepcopy(self.processes),
            "git_loader": self.git_loader,
            "now": lambda: datetime(
                2026, 8, 21, 5, 30, tzinfo=timezone.utc
            ),
        }
        options.update(overrides)
        return recovery.recover(**options)

    @staticmethod
    def git_loader(root: Path, code_sha: str, relative: str) -> bytes:
        assert code_sha == recovery.CODE_SHA
        return (root / relative).read_bytes()


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


def test_registered_source_identity_matches_durable_recovery_incident() -> None:
    incident_path = (
        ROOT / "reports/a7-select-ladder-preflight-recovery-runs"
        / recovery.RECOVERY_ID / "incident.json"
    )
    incident = json.loads(incident_path.read_text(encoding="utf-8"))
    assert incident["source"] == {
        "build_id": recovery.BUILD_ID,
        "code_sha": recovery.CODE_SHA,
        "frozen_source_sha256": dict(recovery.FROZEN_SOURCE_SHA256),
        "image": recovery.IMAGE,
    }
    assert sha256(
        (ROOT / recovery.PROTOCOL_PATH).read_bytes()
    ).hexdigest() == recovery.PROTOCOL_SHA256


def test_exact_empty_shell_is_archived_atomically_with_canonical_evidence(
    harness: Harness,
) -> None:
    inode = harness.shell.stat().st_ino
    result = harness.run()

    archived = harness.archive / recovery.ARCHIVED_SHELL_NAME
    assert result["licenses"]["same_v2_first_preflight_prepare_licensed"] is True
    assert result["licenses"]["preflight_retry_licensed"] is False
    assert not harness.shell.exists()
    assert archived.is_dir() and not list(archived.iterdir())
    assert archived.stat().st_ino == inode
    assert (harness.archive / "recovery.sha256").is_file()
    incident = json.loads(
        (harness.archive / "incident.json").read_text(encoding="utf-8")
    )
    assert incident["interrupted_watcher"]["cause_proven"] is False
    assert incident["outcome_boundary"] == {
        "actual_score_query_executed": False,
        "execution_created": False,
        "historical_look_consumed": False,
        "historical_outcome_lease_acquired": False,
        "job_claim_created": False,
        "job_updated": False,
        "preflight_attempt_created": False,
        "scientific_artifact_body_read": False,
    }
    # The recovery has metadata list/reload calls only; the fake deliberately
    # exposes no upload, update, execute, delete, or body-download operation.
    assert harness.storage.events[0][0] == "list"
    # The entire absence boundary is checked once for the receipt and again
    # after evidence fsync, immediately before the final atomic rename.
    assert [kind for kind, _name in harness.storage.events].count("reload") == 16


def test_recovery_requires_explicit_gate_and_refuses_archive_collision(
    harness: Harness,
) -> None:
    with pytest.raises(RuntimeError, match="explicit execute"):
        harness.run(execute=False)
    harness.archive.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="archive already exists"):
        harness.run()
    assert harness.shell.is_dir()


@pytest.mark.parametrize(
    "poison, message",
    [
        ("nonempty-shell", "identity differs|not exactly empty"),
        ("cloud-prefix", "cloud prefix is not empty"),
        ("lease-present", "required-absent object exists"),
        ("job-drift", "job identity/spec changed"),
        ("new-execution", "execution census population changed"),
        ("nonterminal-execution", "not strictly terminal"),
        ("scheduler", "reused job is scheduled"),
        ("process", "process still exists"),
        ("historical-local", "historical run unexpectedly exists"),
        ("source-drift", "frozen local source differs"),
    ],
)
def test_every_ambiguity_fails_before_the_shell_moves(
    harness: Harness, poison: str, message: str,
) -> None:
    if poison == "nonempty-shell":
        (harness.shell / "unexpected").write_text("x", encoding="utf-8")
    elif poison == "cloud-prefix":
        _, name = recovery._gcs_parts(recovery.JOB_CLAIM_URI)
        harness.storage.list_override = [name]
    elif poison == "lease-present":
        _, name = recovery._gcs_parts(recovery.LEASE_URI)
        harness.storage.objects.add(name)
    elif poison == "job-drift":
        harness.job["metadata"]["generation"] = "13"
    elif poison == "new-execution":
        extra = copy.deepcopy(harness.executions[0])
        extra["metadata"]["name"] = f"{recovery.JOB}-new01"
        harness.executions.append(extra)
    elif poison == "nonterminal-execution":
        harness.executions[0]["status"]["conditions"] = []
    elif poison == "scheduler":
        harness.schedulers.append({
            "httpTarget": {
                "uri": "https://run.googleapis.com/v2/projects/p/locations/r/jobs/"
                f"{recovery.JOB}:run"
            }
        })
    elif poison == "process":
        harness.processes.append({
            "pid": recovery.INCIDENT_PID,
            "command": "bash scripts/watch_a7_select_ladder_queue.sh",
        })
    elif poison == "historical-local":
        harness.historical_out.mkdir(parents=True)
    elif poison == "source-drift":
        target = harness.root / HISTORICAL_FINISHER
        target.write_bytes(target.read_bytes() + b"drift\n")
    else:  # pragma: no cover - parameter list is closed above
        raise AssertionError(poison)

    with pytest.raises(RuntimeError, match=message):
        harness.run()
    assert harness.shell.is_dir()
    assert not harness.archive.exists()
