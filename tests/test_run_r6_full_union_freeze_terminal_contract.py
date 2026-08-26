from __future__ import annotations

import json
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests import test_validate_r6_full_union_lane_terminal_v1 as terminal_test


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "run_r6_full_union_freeze_cloud_v1.sh"


def _source() -> str:
    return LAUNCHER.read_text(encoding="utf-8")


def _function_fragment() -> str:
    source = _source()
    start = source.index("require_terminal_execution()")
    end = source.index("common_csv=", start)
    return source[start:end]


def _envelope(*, completed: str = "True", failed: int = 0,
              running: int = 0, image: str = "repo@sha256:" + "a" * 64,
              args: list[str] | None = None) -> dict[str, object]:
    retained_args = ["runner.py", "--source-offset", "0"] if args is None else args
    return {
        "metadata": {
            "name": "projects/p/locations/r/executions/lane-job-abc12",
            "labels": {"run.googleapis.com/job": "lane-job"},
        },
        "spec": {
            "taskCount": 28,
            "parallelism": 4,
            "template": {"spec": {
                "maxRetries": 0,
                "timeoutSeconds": "7200",
                "serviceAccountName": "runner@example.invalid",
                "containers": [{
                    "image": image,
                    "command": ["python"],
                    "args": retained_args,
                    "resources": {"limits": {"cpu": "4", "memory": "16Gi"}},
                    "env": [
                        {"name": "R6_FULL_UNION_PANEL_FREEZE_PRODUCTION_ENABLED", "value": "1"},
                        {"name": "R6_FULL_UNION_PANEL_FREEZE_RUNTIME_IMAGE", "value": image},
                    ],
                }],
            }},
        },
        "status": {
            "completionTime": "2026-08-26T15:00:00Z",
            "conditions": [{"type": "Completed", "status": completed}],
            "succeededCount": 28,
            "failedCount": failed,
            "runningCount": running,
        },
    }


def _run_contract(tmp_path: Path, envelope: dict[str, object]) -> subprocess.CompletedProcess[str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    fake_gcloud = fake_bin / "gcloud"
    fake_gcloud.write_text(
        "#!/usr/bin/env bash\ncat \"$R6_TEST_ENVELOPE\"\n",
        encoding="utf-8",
    )
    fake_gcloud.chmod(0o755)
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir(exist_ok=True)
    (run_dir / "lane-a-execution.txt").write_text("lane-job-abc12\n", encoding="utf-8")
    driver = tmp_path / "driver.sh"
    driver.write_text(
        "set -euo pipefail\n"
        "project=p\nregion=r\n"
        f"R6_FREEZE_RUN_DIR={run_dir!s}\n"
        "R6_FREEZE_IMAGE=repo@sha256:" + "a" * 64 + "\n"
        "R6_FREEZE_CODE_SHA=" + "b" * 40 + "\n"
        f"R6_FREEZE_PYTHON={sys.executable}\n"
        "service_account=runner@example.invalid\n"
        + _function_fragment()
        + f'require_terminal_execution "{run_dir}/lane-a-execution.txt" '
          'lane-a lane-job 28 4 "runner.py,--source-offset,0"\n',
        encoding="utf-8",
    )
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "R6_TEST_ENVELOPE": str(envelope_path),
    }
    return subprocess.run(
        ["bash", str(driver)], check=False, capture_output=True, text=True, env=env,
    )


def _run_authorization(
    tmp_path: Path, envelope: dict[str, object], *, declared: str | None = None,
    repair_receipts: dict[int, bytes] | None = None,
) -> subprocess.CompletedProcess[str]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    fake_bin = tmp_path / "bin"; fake_bin.mkdir()
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps(envelope))
    gcloud = fake_bin / "gcloud"
    gcloud.write_text('#!/usr/bin/env bash\nif [[ "$*" == *repair3* ]]; then cat "$R6_TEST_REPAIR_ENVELOPE"; else cat "$R6_TEST_ENVELOPE"; fi\n')
    gcloud.chmod(0o755)
    run_dir = tmp_path / "run"; run_dir.mkdir()
    (run_dir / "lane-a-execution.txt").write_text("lane-job-abc12\n")
    for ordinal, raw in (repair_receipts or {}).items():
        (run_dir / f"repair-{ordinal}-terminal-receipt.json").write_bytes(raw)
        (run_dir / f"repair-{ordinal}-execution.txt").write_text(f"lane-job-repair{ordinal}\n")
        (run_dir / f"status-after-repair-{ordinal}.json").write_text(json.dumps({
            "completed_source_ordinals": [ordinal], "missing_source_ordinals": [],
            "result_only_source_ordinals": [],
        }))
    driver = tmp_path / "authorize.sh"
    driver.write_text(
        "set -euo pipefail\nproject=p\nregion=r\n"
        f"R6_FREEZE_RUN_DIR={run_dir}\n"
        "R6_FREEZE_IMAGE=repo@sha256:" + "a" * 64 + "\n"
        "R6_FREEZE_CODE_SHA=" + "b" * 40 + "\n"
        f"R6_FREEZE_PYTHON={sys.executable}\n"
        "service_account=runner@example.invalid\njob_a=lane-job\njob_b=other-job\n"
        'common_csv="runner.py"\nbinding_csv="--binding,x"\n'
        + _function_fragment()
        + 'require_lane_success_or_exact_repairs "$R6_FREEZE_RUN_DIR/lane-a-execution.txt" '
          'lane-a lane-job 28 4 "runner.py,--source-offset,0" 0 '
          'R6_FREEZE_LANE_A_REPAIRED_ORDINALS\n'
    )
    repair_envelope_path = tmp_path / "repair-envelope.json"
    repair_envelope_path.write_text(json.dumps(_repair_envelope(3)))
    env = {"PATH": f"{fake_bin}:{os.environ['PATH']}", "R6_TEST_ENVELOPE": str(envelope_path),
           "R6_TEST_REPAIR_ENVELOPE": str(repair_envelope_path)}
    if declared is not None:
        env["R6_FREEZE_LANE_A_REPAIRED_ORDINALS"] = declared
    return subprocess.run(["bash", str(driver)], env=env, capture_output=True, text=True)


def _repair_envelope(ordinal: int) -> dict[str, object]:
    envelope = _envelope()
    envelope["metadata"] = {"name": f"lane-job-repair{ordinal}", "labels": {"run.googleapis.com/job": "lane-job"}}
    envelope["spec"]["taskCount"] = 1  # type: ignore[index]
    envelope["spec"]["parallelism"] = 1  # type: ignore[index]
    envelope["spec"]["template"]["spec"]["containers"][0]["args"] = ["runner.py", "--source-ordinal", str(ordinal), "--binding", "x"]  # type: ignore[index]
    envelope["status"]["succeededCount"] = 1  # type: ignore[index]
    return envelope


def _repair_receipt(ordinal: int) -> bytes:
    envelope = _repair_envelope(ordinal)
    return terminal_test.cli._canonical(terminal_test.cli.build_receipt(
        envelope, lane=f"repair-{ordinal}", execution=f"lane-job-repair{ordinal}",
        job="lane-job", image="repo@sha256:" + "a" * 64, code_sha="b" * 40,
        service_account="runner@example.invalid", task_count=1, parallelism=1,
        expected_args=["runner.py", "--source-ordinal", str(ordinal), "--binding", "x"],
    ))


def test_terminal_success_persists_create_once_equal_receipt(tmp_path: Path) -> None:
    first = _run_contract(tmp_path, _envelope())
    assert first.returncode == 0, first.stderr
    receipt_path = tmp_path / "run" / "lane-a-terminal-receipt.json"
    raw_receipt = receipt_path.read_bytes()
    assert not raw_receipt.endswith(b"\n")
    receipt = json.loads(receipt_path.read_text())
    expected = terminal_test.cli.build_receipt(
        _envelope(), lane="lane-a", execution="lane-job-abc12", job="lane-job",
        image="repo@sha256:" + "a" * 64, code_sha="b" * 40,
        service_account="runner@example.invalid", task_count=28, parallelism=4,
        expected_args=["runner.py", "--source-offset", "0"],
    )
    assert raw_receipt == terminal_test.cli._canonical(expected)
    assert receipt["completed_condition"] == "True"
    assert receipt["task_count"] == receipt["succeeded_count"] == 28
    assert receipt["failed_count"] == receipt["running_count"] == 0
    retained_hash = receipt.pop("terminal_receipt_sha256")
    assert retained_hash == sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    recovered = _run_contract(tmp_path, _envelope())
    assert recovered.returncode == 0, recovered.stderr
    changed = _envelope()
    changed["status"]["completionTime"] = "2026-08-26T15:00:01Z"  # type: ignore[index]
    collision = _run_contract(tmp_path, changed)
    assert collision.returncode != 0
    assert "terminal receipt collision differs" in collision.stderr


def test_false_unknown_failed_running_and_runtime_splices_fail_closed(tmp_path: Path) -> None:
    mutations = (
        {"completed": "False"},
        {"completed": "Unknown"},
        {"failed": 1},
        {"running": 1},
        {"image": "repo@sha256:" + "b" * 64},
        {"args": ["runner.py", "--source-offset", "28"]},
    )
    for index, mutation in enumerate(mutations):
        case = tmp_path / str(index)
        case.mkdir()
        result = _run_contract(case, _envelope(**mutation))
        assert result.returncode != 0, mutation
        assert not (case / "run" / "lane-a-terminal-receipt.json").exists()


def test_finish_requires_both_exact_lane_terminal_receipts() -> None:
    source = _source()
    finish_status = source.rindex(
        'run_cli status "${manifest_args[@]}" >"${R6_FREEZE_RUN_DIR}/status-before-finish.json"'
    )
    preceding = source[source.rfind("fi", 0, finish_status) + 2:finish_status]
    assert preceding.count("require_lane_success_or_exact_repairs") == 2
    assert '"$job_a" 28 4 "$lane_a_csv"' in preceding
    assert '"$job_b" 26 4 "$lane_b_csv"' in preceding
    assert "validate_r6_full_union_lane_terminal_v1.py" in source
    assert "--require-success" in source
    assert '"$lane_a_csv" 0' in source
    assert '"$lane_b_csv" 0' in source
    assert "terminal_success" in source


def test_authorization_executes_all_success_and_exact_repair_paths(tmp_path: Path) -> None:
    assert _run_authorization(tmp_path / "success", _envelope()).returncode == 0
    failed = _envelope(completed="False", failed=1)
    failed["status"]["succeededCount"] = 27  # type: ignore[index]
    exact = _run_authorization(
        tmp_path / "repair", failed, declared="3", repair_receipts={3: _repair_receipt(3)}
    )
    assert exact.returncode == 0, exact.stderr


@pytest.mark.parametrize("declared", ["", "3,3", "28"])
def test_repair_authorization_rejects_count_duplicate_and_out_of_lane(
    tmp_path: Path, declared: str,
) -> None:
    failed = _envelope(completed="False", failed=1)
    failed["status"]["succeededCount"] = 27  # type: ignore[index]
    result = _run_authorization(
        tmp_path, failed, declared=declared, repair_receipts={3: _repair_receipt(3), 28: _repair_receipt(28)}
    )
    assert result.returncode != 0


def test_repair_authorization_rejects_self_hash_mismatch(tmp_path: Path) -> None:
    failed = _envelope(completed="False", failed=1)
    failed["status"]["succeededCount"] = 27  # type: ignore[index]
    receipt = json.loads(_repair_receipt(3)); receipt["terminal_receipt_sha256"] = "f" * 64
    result = _run_authorization(
        tmp_path, failed, declared="3",
        repair_receipts={3: json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()},
    )
    assert result.returncode != 0


def test_post_repair_status_executes_exact_completed_not_missing_or_result_only(
    tmp_path: Path,
) -> None:
    status = tmp_path / "status.json"
    driver = tmp_path / "status.sh"
    driver.write_text("set -euo pipefail\n" + _function_fragment() +
                      f'validate_post_repair_status "{status}" 3\n')
    status.write_text(json.dumps({
        "completed_source_ordinals": [3],
        "missing_source_ordinals": [],
        "result_only_source_ordinals": [],
    }))
    assert subprocess.run(["bash", str(driver)]).returncode == 0
    status.write_text(json.dumps({
        "completed_source_ordinals": [3],
        "missing_source_ordinals": [3],
        "result_only_source_ordinals": [],
    }))
    assert subprocess.run(["bash", str(driver)]).returncode != 0
