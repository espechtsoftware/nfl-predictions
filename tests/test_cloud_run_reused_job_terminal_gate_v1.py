from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JOB = "atlas-cbc-32g-full-2023-w8-v1"
SCRIPTS = (
    "scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh",
    "scripts/cloud_corpus_r6_matchup_seven_pack_capture_v1.sh",
    "scripts/cloud_corpus_r6_matchup_source_task0_v3.sh",
    "scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh",
    "scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh",
)


def _terminal_gate(relative_path: str) -> str:
    text = (ROOT / relative_path).read_text(encoding="utf-8")
    match = re.search(
        r"jq -e --arg job \"\$JOB\" '(?P<program>.*?)\n\s*' \"\$[^\"]+\" "
        r">/dev/null \|\| \\\n\s*die \"reused job latest execution is not "
        r"terminal and idle\"",
        text,
        re.DOTALL,
    )
    assert match is not None, relative_path
    return match.group("program")


def _provider_execution(mode: str) -> dict[str, object]:
    condition_status = "True" if mode == "success" else "False"
    status: dict[str, object] = {
        "conditions": [{"type": "Completed", "status": condition_status}],
        "completionTime": "2026-09-01T23:35:49.869929Z",
        "succeededCount": 1 if mode == "success" else 0,
        "failedCount": 1 if mode in {"failed", "contradictory"} else 0,
        "cancelledCount": 1 if mode == "cancelled" else 0,
        "runningCount": 1 if mode in {"running", "contradictory"} else 0,
    }
    if mode == "running":
        status["conditions"] = [{"type": "Completed", "status": "Unknown"}]
        status.pop("completionTime")
    elif mode == "unknown":
        status["conditions"] = [{"type": "Started", "status": "True"}]
        status.pop("completionTime")
    elif mode == "zero-terminal-count":
        status["failedCount"] = 0
    labels = {"run.googleapis.com/job": JOB}
    if mode == "wrong-job":
        labels["run.googleapis.com/job"] = "another-job"
    return {"metadata": {"labels": labels}, "status": status}


def _gate_accepts(relative_path: str, mode: str) -> bool:
    result = subprocess.run(
        ["jq", "-e", "--arg", "job", JOB, _terminal_gate(relative_path)],
        input=json.dumps(_provider_execution(mode)),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode in {0, 1}, result.stderr
    return result.returncode == 0


@pytest.mark.parametrize("relative_path", SCRIPTS)
@pytest.mark.parametrize("mode", ("success", "failed", "cancelled"))
def test_shared_job_gate_accepts_exact_terminal_idle_execution(
    relative_path: str,
    mode: str,
) -> None:
    assert _gate_accepts(relative_path, mode)


@pytest.mark.parametrize("relative_path", SCRIPTS)
@pytest.mark.parametrize(
    "mode",
    ("running", "unknown", "contradictory", "zero-terminal-count", "wrong-job"),
)
def test_shared_job_gate_rejects_unsafe_or_unowned_execution(
    relative_path: str,
    mode: str,
) -> None:
    assert not _gate_accepts(relative_path, mode)
