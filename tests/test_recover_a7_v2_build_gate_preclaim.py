from __future__ import annotations

import copy
from datetime import datetime, timezone
from hashlib import sha256
import json
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

import recover_a7_v2_build_gate_preclaim as recovery  # noqa: E402


class FakeBlob:
    def __init__(self, client: "FakeStorage", name: str) -> None:
        self.client = client
        self.name = name

    def reload(self) -> None:
        self.client.events.append(("reload", self.name))
        if self.name not in self.client.objects:
            raise NotFound("missing")


class FakeBucket:
    def __init__(self, client: "FakeStorage") -> None:
        self.client = client

    def blob(self, name: str) -> FakeBlob:
        return FakeBlob(self.client, name)


class FakeStorage:
    def __init__(self) -> None:
        self.objects: set[str] = set()
        self.list_override: list[str] | None = None
        self.events: list[tuple[str, str]] = []

    def bucket(self, name: str) -> FakeBucket:
        assert name == "nfl-predictions-503414-raw"
        return FakeBucket(self)

    def list_blobs(self, bucket: str, *, prefix: str) -> list[FakeBlob]:
        assert bucket == "nfl-predictions-503414-raw"
        self.events.append(("list", prefix))
        names = self.list_override
        if names is None:
            names = sorted(
                name for name in self.objects if name.startswith(prefix)
            )
        return [FakeBlob(self, name) for name in names]


def _copy(root: Path, relative: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / relative, target)


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


class Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "repo"
        for relative in {
            *recovery.FROZEN_UNCHANGED_PATHS,
            *recovery.FRESH_COMMIT_PATHS,
            recovery.prior.ANCHOR_JOB_PATH,
            recovery.prior.ANCHOR_EXECUTIONS_PATH,
            recovery.prior.ANCHOR_LAST_EXECUTION_PATH,
        }:
            _copy(self.root, relative)
        self.old_blobs = {
            relative: (self.root / relative).read_bytes()
            for relative in recovery.FROZEN_UNCHANGED_PATHS
        }
        self.fresh_blobs = {
            relative: (self.root / relative).read_bytes()
            for relative in recovery.FRESH_COMMIT_PATHS
        }

        self.shell = (
            self.root / "reports/a7-select-ladder-preflight-runs"
            / recovery.RUN_ID
        )
        self.shell.mkdir(parents=True)
        (self.shell / ".inventory-empty").write_bytes(b"")
        smoke = "\n".join(
            (
                "run_a2a_rank_factor_split_census.py --help >/dev/null",
                "run_b1_corpus_tail_model.py --help >/dev/null",
                "watch_a7_select_ladder_queue.sh",
            )
        )
        self.build = {
            "id": recovery.OLD_BUILD_ID,
            "status": "SUCCESS",
            "source": {"gitSource": {
                "url": recovery.GIT_SOURCE_URL,
                "revision": recovery.OLD_CODE_SHA,
            }},
            "substitutions": {"_IMAGE": recovery.OLD_IMAGE_TAG},
            "steps": [{}, {}, {"args": ["-ceu", smoke]}],
            "results": {"images": [{
                "name": recovery.OLD_IMAGE_TAG,
                "digest": recovery.OLD_IMAGE.rsplit("@", 1)[1],
            }]},
        }
        build_raw = _canonical(self.build)
        (self.shell / "build-metadata.json").write_bytes(build_raw)
        self.shell_stat = recovery.prior._stat_receipt(self.shell)
        self.entry_stats = {
            name: recovery.prior._stat_receipt(self.shell / name)
            for name in (".inventory-empty", "build-metadata.json")
        }
        self.entry_sha = {
            ".inventory-empty": _digest(b""),
            "build-metadata.json": _digest(build_raw),
        }

        self.log = tmp_path / "a7-v2.log"
        self.log.write_bytes(
            b"RuntimeError: A7 build/test/image gate differs\n"
            b"ERROR: A7 preflight preparation stopped; immutable directory retained\n"
        )
        self.log_stat = recovery.prior._stat_receipt(self.log)
        self.log_sha = _digest(self.log.read_bytes())
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
        self.storage = FakeStorage()

        self.job = json.loads(
            (self.root / recovery.prior.ANCHOR_JOB_PATH).read_text()
        )
        self.job.setdefault("status", {})["latestCreatedExecution"] = {
            "name": recovery.prior.LAST_EXECUTION,
            "creationTimestamp": "2026-08-21T00:04:13.549125Z",
            "completionTimestamp": "2026-08-21T00:17:24.845961Z",
            "completionStatus": "EXECUTION_SUCCEEDED",
        }
        old = json.loads(
            (self.root / recovery.prior.ANCHOR_EXECUTIONS_PATH).read_text()
        )
        last = json.loads(
            (self.root / recovery.prior.ANCHOR_LAST_EXECUTION_PATH).read_text()
        )
        self.executions = [last, *old]
        self.schedulers: list[dict[str, Any]] = []
        self.processes: list[dict[str, Any]] = []
        self.fresh_code_sha = "f" * 40

    def old_git(self, root: Path, code_sha: str, relative: str) -> bytes:
        assert code_sha == recovery.OLD_CODE_SHA
        if relative == "scripts/finish_a7_select_ladder.py":
            return b"old finisher build-step contract\n"
        return self.old_blobs[relative]

    def fresh_git(self, root: Path, code_sha: str, relative: str) -> bytes:
        assert code_sha == self.fresh_code_sha
        return self.fresh_blobs[relative]

    def run(self, **overrides: Any) -> dict[str, Any]:
        options = {
            "execute": True,
            "fresh_code_sha": self.fresh_code_sha,
            "root": self.root,
            "shell": self.shell,
            "historical_out": self.historical_out,
            "historical_pending": self.historical_pending,
            "archive": self.archive,
            "log_path": self.log,
            "expected_shell_stat": self.shell_stat,
            "expected_entry_stats": self.entry_stats,
            "expected_entry_sha256": self.entry_sha,
            "expected_log_stat": self.log_stat,
            "expected_log_sha256": self.log_sha,
            "client": self.storage,
            "job_loader": lambda: copy.deepcopy(self.job),
            "executions_loader": lambda: copy.deepcopy(self.executions),
            "schedulers_loader": lambda: copy.deepcopy(self.schedulers),
            "process_loader": lambda: copy.deepcopy(self.processes),
            "old_git_loader": self.old_git,
            "fresh_git_loader": self.fresh_git,
            "env": {},
            "now": lambda: datetime(
                2026, 8, 21, 6, 30, tzinfo=timezone.utc,
            ),
        }
        options.update(overrides)
        return recovery.recover(**options)


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


def test_exact_failed_preclaim_shell_and_log_are_archived(
    harness: Harness,
) -> None:
    inode = harness.shell.stat().st_ino
    log_raw = harness.log.read_bytes()
    result = harness.run()

    archived = harness.archive / recovery.ARCHIVED_SHELL_NAME
    assert not harness.shell.exists()
    assert archived.stat().st_ino == inode
    assert sorted(path.name for path in archived.iterdir()) == [
        ".inventory-empty", "build-metadata.json",
    ]
    assert (harness.archive / recovery.ARCHIVED_LOG_NAME).read_bytes() == log_raw
    assert result["licenses"] == {
        "same_v2_fresh_exact_source_build_licensed": True,
        "same_v2_first_preflight_prepare_claim_licensed": True,
        "old_build_or_image_reuse_licensed": False,
        "repair_override_licensed": False,
        "preflight_retry_licensed": False,
        "historical_scoring_licensed": False,
        "prospective_shadow_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "production_change_licensed": False,
    }
    incident = json.loads((harness.archive / "incident.json").read_text())
    assert not any(incident["outcome_boundary"].values())
    assert incident["cloud_boundary"]["job_claim_absent"] is True
    assert [kind for kind, _name in harness.storage.events].count("list") == 2
    assert [kind for kind, _name in harness.storage.events].count("reload") == 16


def test_recovery_requires_explicit_gate_fresh_commit_and_new_archive(
    harness: Harness,
) -> None:
    with pytest.raises(RuntimeError, match="explicit execute"):
        harness.run(execute=False)
    with pytest.raises(RuntimeError, match="fresh repair source identity differs"):
        harness.run(fresh_code_sha=recovery.OLD_CODE_SHA)
    harness.archive.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="archive already exists"):
        harness.run()
    assert harness.shell.is_dir()


@pytest.mark.parametrize(
    "poison, message",
    [
        ("extra-shell", "shell identity differs|shell population differs"),
        ("build", "build-metadata.json identity differs|entry bytes differ"),
        ("log", "watcher log identity differs|watcher log differs"),
        ("frozen-source", "frozen source changed"),
        ("fresh-source", "fresh committed source differs"),
        ("repair-env", "forbids repair overrides"),
        ("cloud-prefix", "cloud prefix is not empty"),
        ("lease", "required-absent object exists"),
        ("job", "job identity/spec changed"),
        ("execution", "execution census population changed"),
        ("scheduler", "reused job is scheduled"),
        ("process", "process still exists"),
        ("historical", "historical local output unexpectedly exists"),
    ],
)
def test_every_ambiguity_fails_before_archive(
    harness: Harness, poison: str, message: str,
) -> None:
    overrides: dict[str, Any] = {}
    if poison == "extra-shell":
        (harness.shell / "extra").write_bytes(b"x")
    elif poison == "build":
        (harness.shell / "build-metadata.json").write_bytes(b"{}\n")
    elif poison == "log":
        harness.log.write_bytes(b"")
    elif poison == "frozen-source":
        path = harness.root / recovery.FROZEN_UNCHANGED_PATHS[0]
        path.write_bytes(path.read_bytes() + b"drift\n")
    elif poison == "fresh-source":
        overrides["fresh_git_loader"] = lambda *_args: b"different"
    elif poison == "repair-env":
        overrides["env"] = {"A7_FINISHER_REPAIR_SHA256": "a" * 64}
    elif poison == "cloud-prefix":
        _, name = recovery.prior._gcs_parts(recovery.prior.JOB_CLAIM_URI)
        harness.storage.list_override = [name]
    elif poison == "lease":
        _, name = recovery.prior._gcs_parts(recovery.prior.LEASE_URI)
        harness.storage.objects.add(name)
    elif poison == "job":
        harness.job["metadata"]["generation"] = "13"
    elif poison == "execution":
        harness.executions.pop()
    elif poison == "scheduler":
        harness.schedulers.append({"httpTarget": {
            "uri": "https://run.googleapis.com/v2/p/l/jobs/"
            f"{recovery.prior.JOB}:run",
        }})
    elif poison == "process":
        harness.processes.append({
            "pid": 123, "command": "bash scripts/cloud_a7_select_ladder.sh",
        })
    elif poison == "historical":
        harness.historical_out.mkdir(parents=True)
    else:  # pragma: no cover
        raise AssertionError(poison)

    with pytest.raises(RuntimeError, match=message):
        harness.run(**overrides)
    assert harness.shell.is_dir()
    assert not harness.archive.exists()
