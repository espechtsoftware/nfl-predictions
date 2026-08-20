from __future__ import annotations

import copy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

import pytest

import close_stack_relaxation_carve_post_open as recovery
import finish_stack_relaxation_carve as strict


SOURCE_OUT = (
    Path(__file__).resolve().parents[1]
    / "reports/stack-relaxation-carve-runs"
    / strict.RUN_ID
)


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _execution(cell: strict.Cell) -> dict[str, Any]:
    frozen = strict.FROZEN
    return {
        "metadata": {
            "name": cell.execution,
            "generation": 1,
            "labels": {
                "run.googleapis.com/job": cell.job,
                "run.googleapis.com/jobUid": frozen.job_uid,
                "run.googleapis.com/jobGeneration": frozen.job_generation,
            },
        },
        "spec": {
            "parallelism": 1,
            "taskCount": 1,
            "template": {"spec": {
                "containers": [{
                    "image": frozen.image,
                    "command": ["python"],
                    "args": [
                        "scripts/run_stack_relaxation_carve.py",
                        "--season", str(cell.season),
                        "--week", str(cell.week),
                        "--output-uri", cell.uri,
                    ],
                    "env": [
                        {"name": "CODE_SHA", "value": frozen.code_sha},
                        {"name": "ANALYSIS_IMAGE", "value": frozen.image},
                    ],
                    "resources": {"limits": {"cpu": "4", "memory": "16Gi"}},
                }],
                "maxRetries": 0,
                "timeoutSeconds": "7200",
                "serviceAccountName": frozen.service_account,
            }},
        },
        "status": {
            "observedGeneration": 1,
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1,
            "completionTime": "2026-08-20T04:47:39Z",
        },
    }


class SyntheticRecovery:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.root = tmp_path / "repo"
        self.out = (
            self.root / "reports/stack-relaxation-carve-runs" / strict.RUN_ID
        )
        (self.out / "cells").mkdir(parents=True)
        shutil.copy2(SOURCE_OUT / "aggregate-report.json", self.out)
        shutil.copy2(SOURCE_OUT / "executions.txt", self.out)
        for source in (SOURCE_OUT / "cells").glob("*.json"):
            shutil.copy2(source, self.out / "cells" / source.name)
        self.report = self.root / "reports/2026-08-20-stack-relaxation-carve-results.md"
        self.report.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(recovery.RESULT_REPORT, self.report)
        self.cells = strict._read_ledger(self.out / "executions.txt", strict.FROZEN)
        self.bodies = {
            cell.uri: (self.out / "cells" / cell.stem).read_bytes()
            for cell in self.cells
        }
        self.executions = {
            cell.execution: _execution(cell) for cell in self.cells
        }
        self.inventory = {
            cell.uri: {
                "uri": cell.uri,
                "generation": str(index + 100),
                "metageneration": "1",
                "size": len(self.bodies[cell.uri]),
                "md5_hash": "",
                "crc32c": "",
                "etag": "etag",
                "time_created": "2026-08-20T04:00:00+00:00",
                "updated": "2026-08-20T04:00:00+00:00",
            }
            for index, cell in enumerate(self.cells)
        }
        self.events: list[tuple[Any, ...]] = []
        frozen_aggregate = json.loads(
            (self.out / "aggregate-report.json").read_text(encoding="utf-8")
        )
        monkeypatch.setattr(
            strict, "_aggregate",
            lambda *_args, **_kwargs: copy.deepcopy(frozen_aggregate),
        )
        self.implementation = {
            "source_commit": "a" * 40,
            "freeze_manifest_path": (
                "reports/2026-08-20-a3-post-open-forensic-closure-"
                "implementation-freeze.json"
            ),
            "freeze_manifest_sha256": "d" * 64,
            "implementation": {
                "script": {
                    "path": recovery.IMPLEMENTATION_PATH,
                    "sha256": "b" * 64,
                },
                "tests": {
                    "path": recovery.IMPLEMENTATION_TEST_PATH,
                    "sha256": "c" * 64,
                },
                "protocol": {
                    "path": str(recovery.CLOSURE_PROTOCOL.relative_to(
                        Path(__file__).resolve().parents[1]
                    )),
                    "sha256": recovery.CLOSURE_PROTOCOL_SHA256,
                },
            },
            "operator_approved": True,
            "frozen_at": "2026-08-20T08:00:00+00:00",
        }
        monkeypatch.setattr(recovery, "ROOT", self.root)
        monkeypatch.setattr(recovery, "DEFAULT_OUT", self.out)
        monkeypatch.setattr(recovery, "RESULT_REPORT", self.report)
        monkeypatch.setattr(
            recovery, "_validate_frozen_inputs",
            lambda out, git_loader=recovery._git_blob: (
                self.cells, self.implementation,
            ),
        )

    def execution_loader(self, name: str) -> dict[str, Any]:
        self.events.append(("execution", name))
        return self.executions[name]

    def inventory_loader(self, prefix: str) -> dict[str, dict[str, Any]]:
        self.events.append(("inventory", prefix))
        return self.inventory

    def downloader(self, uri: str, metadata: dict[str, Any]) -> bytes:
        self.events.append(("download", uri, metadata["generation"]))
        return self.bodies[uri]

    @staticmethod
    def lease_absent() -> dict[str, str]:
        return {
            "uri": recovery.LEASE_URI,
            "state": "absent",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def close(self, **overrides: Any) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "operator_approved": True,
            "execution_loader": self.execution_loader,
            "inventory_loader": self.inventory_loader,
            "downloader": self.downloader,
            "lease_absence_loader": self.lease_absent,
        }
        kwargs.update(overrides)
        return recovery.close(self.out, **kwargs)


@pytest.fixture
def synthetic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SyntheticRecovery:
    return SyntheticRecovery(tmp_path, monkeypatch)


def test_post_open_closure_is_ordered_byte_exact_and_idempotent(
    synthetic: SyntheticRecovery,
) -> None:
    before = {
        path.name: _sha(path.read_bytes())
        for path in (synthetic.out / "cells").glob("*.json")
    }
    aggregate_before = (synthetic.out / "aggregate-report.json").read_bytes()
    result = synthetic.close()
    assert result["status"] == "released"
    kinds = [event[0] for event in synthetic.events]
    assert kinds[:54] == ["execution"] * 54
    assert kinds[54] == "inventory"
    assert kinds[55:] == ["download"] * 54
    assert aggregate_before == (synthetic.out / "aggregate-report.json").read_bytes()
    assert before == {
        path.name: _sha(path.read_bytes())
        for path in (synthetic.out / "cells").glob("*.json")
    }
    release = recovery._validate_release(synthetic.out)
    assert release["strict_harvest_completed_before_read"] is False
    assert release["a3_result_transport_to_a7_licensed"] is False
    synthetic.events.clear()
    second = synthetic.close()
    assert second["status"] == "already-released"
    assert synthetic.events == []


def test_all_terminal_metadata_precedes_inventory_and_body_one(
    synthetic: SyntheticRecovery,
) -> None:
    synthetic.executions[synthetic.cells[-1].execution]["status"][
        "succeededCount"
    ] = True
    with pytest.raises(RuntimeError, match="exact nonnegative integer"):
        synthetic.close()
    assert [event[0] for event in synthetic.events] == ["execution"] * 54


def test_inventory_extra_stops_before_body_one(
    synthetic: SyntheticRecovery,
) -> None:
    synthetic.inventory["gs://unexpected/extra.json"] = {
        "uri": "gs://unexpected/extra.json", "generation": "1",
        "metageneration": "1", "size": 1,
    }
    with pytest.raises(RuntimeError, match="live object inventory differs"):
        synthetic.close()
    kinds = [event[0] for event in synthetic.events]
    assert kinds == ["execution"] * 54 + ["inventory"]


@pytest.mark.parametrize(
    ("field", "value"),
    (("generation", "0"), ("size", True)),
)
def test_inventory_rejects_nonpositive_generation_and_boolean_size_before_body_one(
    synthetic: SyntheticRecovery, field: str, value: object,
) -> None:
    synthetic.inventory[synthetic.cells[0].uri][field] = value
    with pytest.raises(RuntimeError, match="object metadata differs"):
        synthetic.close()
    assert [event[0] for event in synthetic.events] == \
        ["execution"] * 54 + ["inventory"]
    assert not (synthetic.out / recovery.CLOSURE_NAME).exists()
    assert not (synthetic.out / recovery.RELEASE_NAME).exists()


def test_remote_body_mismatch_never_replaces_committed_science(
    synthetic: SyntheticRecovery,
) -> None:
    first = synthetic.cells[0]
    original = (synthetic.out / "cells" / first.stem).read_bytes()

    def corrupt(uri: str, metadata: dict[str, Any]) -> bytes:
        synthetic.events.append(("download", uri, metadata["generation"]))
        return b"{}" if uri == first.uri else synthetic.bodies[uri]

    with pytest.raises(RuntimeError, match="differs from result commit"):
        synthetic.close(downloader=corrupt)
    assert (synthetic.out / "cells" / first.stem).read_bytes() == original
    assert not (synthetic.out / recovery.RELEASE_NAME).exists()


def test_aggregate_replay_mismatch_is_terminal(
    synthetic: SyntheticRecovery, monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = strict._aggregate

    def changed(*args: Any, **kwargs: Any) -> dict[str, Any]:
        value = original(*args, **kwargs)
        value["mean_paired_delta_s"] += 0.01
        return value

    monkeypatch.setattr(strict, "_aggregate", changed)
    with pytest.raises(RuntimeError, match="aggregate replay differs"):
        synthetic.close()
    assert not (synthetic.out / recovery.RELEASE_NAME).exists()


def test_ambiguous_lease_leaves_valid_closure_but_no_release(
    synthetic: SyntheticRecovery,
) -> None:
    def ambiguous() -> dict[str, str]:
        raise RuntimeError("auth failed")

    with pytest.raises(RuntimeError, match="auth failed"):
        synthetic.close(lease_absence_loader=ambiguous)
    assert (synthetic.out / recovery.CLOSURE_NAME / "closure.json").is_file()
    assert not (synthetic.out / recovery.RELEASE_NAME).exists()
    synthetic.events.clear()
    result = synthetic.close()
    assert result["status"] == "released"
    assert synthetic.events == []


@pytest.mark.parametrize(
    ("checked_at", "message"),
    (
        (123, "lease absence timestamp differs"),
        ("2000-01-01T00:00:00+00:00", "logical release chronology differs"),
    ),
)
def test_invalid_release_candidate_is_rejected_before_create_once_publication(
    synthetic: SyntheticRecovery, checked_at: object, message: str,
) -> None:
    def invalid_lease() -> dict[str, Any]:
        return {
            "uri": recovery.LEASE_URI,
            "state": "absent",
            "checked_at": checked_at,
        }

    with pytest.raises(RuntimeError, match=message):
        synthetic.close(lease_absence_loader=invalid_lease)
    assert (synthetic.out / recovery.CLOSURE_NAME / "closure.json").is_file()
    assert not (synthetic.out / recovery.RELEASE_NAME).exists()

    synthetic.events.clear()
    result = synthetic.close()
    assert result["status"] == "released"
    assert synthetic.events == []


def test_extra_pending_evidence_is_rejected_before_final_publication(
    synthetic: SyntheticRecovery,
) -> None:
    pending = synthetic.out / recovery.PENDING_NAME
    pending.mkdir()
    (pending / "unreceipted.txt").write_bytes(b"not receipted\n")
    with pytest.raises(RuntimeError, match="evidence inventory differs"):
        synthetic.close()
    assert pending.is_dir()
    assert not (synthetic.out / recovery.CLOSURE_NAME).exists()
    assert not (synthetic.out / recovery.RELEASE_NAME).exists()


@pytest.mark.parametrize(
    "relative",
    ("unreceipted.txt", "execution-metadata/unreceipted.json"),
)
def test_extra_final_evidence_is_rejected(
    synthetic: SyntheticRecovery, relative: str,
) -> None:
    synthetic.close()
    extra = synthetic.out / recovery.CLOSURE_NAME / relative
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_bytes(b"not receipted\n")
    with pytest.raises(RuntimeError, match="evidence inventory differs"):
        recovery._validate_closure(
            synthetic.out, implementation=synthetic.implementation,
        )
    with pytest.raises(RuntimeError, match="evidence inventory differs"):
        synthetic.close()


def test_release_v1_extra_and_license_poison_fail(
    synthetic: SyntheticRecovery,
) -> None:
    synthetic.close()
    path = synthetic.out / recovery.RELEASE_NAME
    valid = json.loads(path.read_text(encoding="utf-8"))
    for mutate in (
        lambda row: row.update(version="stack-relaxation-carve-logical-release-v1"),
        lambda row: row.update(production_change_licensed=True),
        lambda row: row.update(extra="forbidden"),
    ):
        poisoned = dict(valid)
        mutate(poisoned)
        path.write_bytes(recovery._canonical(poisoned))
        with pytest.raises(RuntimeError, match="A3 recovery logical release"):
            recovery._validate_release(synthetic.out)
    path.write_bytes(recovery._canonical(valid))
    recovery._validate_release(synthetic.out)


def test_embedded_closure_type_hash_nested_and_chronology_poisons_fail(
    synthetic: SyntheticRecovery,
) -> None:
    synthetic.close()
    path = synthetic.out / recovery.RELEASE_NAME
    valid = json.loads(path.read_text(encoding="utf-8"))

    def assert_rejected(
        mutate: Any, *, refresh_closure_sha: bool = True,
    ) -> None:
        poisoned = copy.deepcopy(valid)
        mutate(poisoned)
        if refresh_closure_sha:
            poisoned["forensic_closure_sha256"] = _sha(
                recovery._canonical(poisoned["forensic_closure_receipt"])
            )
        path.write_bytes(recovery._canonical(poisoned))
        with pytest.raises(RuntimeError, match="A3 recovery"):
            recovery._validate_release(synthetic.out)

    assert_rejected(
        lambda row: row["forensic_closure_receipt"]["cells"].update(extra=1)
    )
    assert_rejected(
        lambda row: row["forensic_closure_receipt"].update(
            production_change_licensed=0
        )
    )
    assert_rejected(
        lambda row: row.update(operator_approved=1)
    )
    assert_rejected(
        lambda row: row.update(
            historical_outcome_lease_absence_checked_at=123
        )
    )
    assert_rejected(
        lambda row: row["forensic_closure_receipt"].update(
            closed_at="2026-08-21T00:00:00+00:00"
        )
    )
    assert_rejected(
        lambda row: row["forensic_closure_receipt"].update(
            prior_arm_disposition="forged"
        ),
        refresh_closure_sha=False,
    )
    path.write_bytes(recovery._canonical(valid))
    recovery._validate_release(synthetic.out)


def test_frozen_preopen_material_hashes_and_original_result_are_exact() -> None:
    assert recovery._sha(recovery.STRICT_FINISHER) == recovery.STRICT_FINISHER_SHA256
    assert recovery._sha(recovery.STRICT_TEST) == recovery.STRICT_TEST_SHA256
    assert recovery._sha(recovery.PREOPEN_ADDENDUM) == recovery.PREOPEN_ADDENDUM_SHA256
    assert recovery._sha(recovery.CLOSURE_PROTOCOL) == recovery.CLOSURE_PROTOCOL_SHA256
    assert recovery._sha(recovery.RESULT_REPORT) == recovery.RESULT_REPORT_SHA256
    assert recovery._sha(recovery.PAIRED_STATS_PATH) == recovery.PAIRED_STATS_SHA256
    for commit in (strict.FROZEN.code_sha, recovery.RESULT_COMMIT):
        try:
            committed = recovery._git_blob(
                commit, recovery.PAIRED_STATS_RELATIVE,
            )
        except subprocess.CalledProcessError:
            pytest.skip("source checkout does not retain historical Git objects")
        assert _sha(committed) == recovery.PAIRED_STATS_SHA256
    assert recovery._sha(SOURCE_OUT / "aggregate-report.json") == recovery.AGGREGATE_SHA256
    cells = strict._read_ledger(SOURCE_OUT / "executions.txt", strict.FROZEN)
    assert len(cells) == 54
    for relative in [
        str((SOURCE_OUT / "aggregate-report.json").relative_to(recovery.ROOT)),
        str(recovery.RESULT_REPORT.relative_to(recovery.ROOT)),
        *[
            str((SOURCE_OUT / "cells" / cell.stem).relative_to(recovery.ROOT))
            for cell in cells
        ],
    ]:
        assert (recovery.ROOT / relative).read_bytes() == recovery._git_blob(
            recovery.RESULT_COMMIT, relative,
        )


def test_paired_statistics_source_poison_fails_before_cloud_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    poisoned = tmp_path / "paired_max_stats.py"
    poisoned.write_bytes(b"poisoned aggregation dependency\n")
    monkeypatch.setattr(recovery, "PAIRED_STATS_PATH", poisoned)
    with pytest.raises(RuntimeError, match="paired statistics source differs"):
        recovery._validate_frozen_inputs(SOURCE_OUT)


def test_implementation_freeze_is_tracked_and_survives_later_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    paths = {
        "script": recovery.IMPLEMENTATION_PATH,
        "tests": recovery.IMPLEMENTATION_TEST_PATH,
        "protocol": (
            "reports/2026-08-20-a3-post-open-forensic-closure-protocol.md"
        ),
    }
    raw_by_path: dict[str, bytes] = {}
    for key, relative in paths.items():
        raw = f"{key} frozen bytes\n".encode()
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        raw_by_path[relative] = raw
    source_commit = "a" * 40
    current_head = ["b" * 40]
    freeze_relative = (
        "reports/2026-08-20-a3-post-open-forensic-closure-"
        "implementation-freeze.json"
    )
    freeze_path = root / freeze_relative
    freeze = {
        "version": "stack-relaxation-carve-post-open-implementation-freeze-v1",
        "run_id": recovery.RUN_ID,
        "status": "frozen-for-post-open-forensic-closure",
        "source_commit": source_commit,
        "implementation": {
            key: {"path": relative, "sha256": _sha(raw_by_path[relative])}
            for key, relative in paths.items()
        },
        "operator_approved": True,
        "frozen_at": "2026-08-20T08:00:00+00:00",
        "manifest_contains_realized_outcomes": False,
        "cell_rerun_licensed": False,
        "scientific_retest_licensed": False,
        "production_change_licensed": False,
    }
    freeze_path.write_bytes(recovery._canonical(freeze))
    tracked_freeze = freeze_path.read_bytes()

    monkeypatch.setattr(recovery, "ROOT", root)
    monkeypatch.setattr(recovery, "CLOSURE_PROTOCOL", root / paths["protocol"])
    monkeypatch.setattr(
        recovery, "CLOSURE_PROTOCOL_SHA256", _sha(raw_by_path[paths["protocol"]]),
    )
    monkeypatch.setattr(recovery, "_head", lambda: current_head[0])

    def git_loader(commit: str, relative: str) -> bytes:
        if commit == current_head[0] and relative == freeze_relative:
            return tracked_freeze
        if commit == source_commit and relative in raw_by_path:
            return raw_by_path[relative]
        raise AssertionError((commit, relative))

    first = recovery._implementation_identity(
        git_loader, freeze_path=freeze_path,
    )
    assert first["source_commit"] == source_commit
    assert first["freeze_manifest_path"] == freeze_relative
    current_head[0] = "c" * 40
    second = recovery._implementation_identity(
        git_loader, freeze_path=freeze_path,
    )
    assert second == first

    poisoned = dict(freeze)
    poisoned["operator_approved"] = False
    freeze_path.write_bytes(recovery._canonical(poisoned))
    with pytest.raises(RuntimeError, match="differs from HEAD"):
        recovery._implementation_identity(git_loader, freeze_path=freeze_path)
