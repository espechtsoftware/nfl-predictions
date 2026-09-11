from __future__ import annotations

import json
import os
import re
import stat
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/cloud_corpus_r6_paid_source_discovery_matrix_freeze_v1.sh"
CODE_SHA = "1" * 40
BUILD_ID = "11111111-2222-3333-4444-555555555555"
IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
    "nfl-dfs@sha256:" + "a" * 64
)
JOB = "atlas-cbc-32g-full-2023-w8-v1"


def _install_fake_git(directory: Path) -> None:
    fake = directory / "git"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"root = {str(ROOT)!r}\n"
        f"code = {CODE_SHA!r}\n"
        "args = sys.argv[1:]\n"
        "if args == ['rev-parse', '--show-toplevel']:\n"
        "    print(root)\n"
        "elif args == ['-C', root, 'rev-parse', 'HEAD']:\n"
        "    print(code)\n"
        "elif args == ['-C', root, 'rev-parse', '--verify', "
        "'refs/remotes/origin/main^{commit}']:\n"
        "    print(code)\n"
        "elif args == ['-C', root, 'status', '--porcelain', "
        "'--untracked-files=all']:\n"
        "    mode = __import__('os').environ.get('GIT_STATUS_MODE', 'clean')\n"
        "    if mode == 'dirty':\n"
        "        print('?? untracked.txt')\n"
        "    elif mode == 'failure':\n"
        "        raise SystemExit(91)\n"
        "else:\n"
        "    print('unexpected fake git call: ' + ' '.join(args), file=sys.stderr)\n"
        "    raise SystemExit(98)\n",
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)


def _install_fake_gcloud(directory: Path) -> Path:
    calls = directory / "gcloud-calls.log"
    fake = directory / "gcloud"
    fake.write_text(
        r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
calls = Path(os.environ["FAKE_GCLOUD_CALLS"])
with calls.open("a", encoding="utf-8") as handle:
    handle.write(" ".join(args) + "\n")

job = "atlas-cbc-32g-full-2023-w8-v1"
job_uid = "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
if args[:3] == ["run", "jobs", "describe"]:
    body = {
        "metadata": {"name": job, "uid": job_uid},
        "status": {
            "conditions": [{"type": "Ready", "status": "True"}],
            "latestCreatedExecution": {"name": job + "-old00"},
        },
    }
    if os.environ.get("LATEST_MODE") == "missing-latest":
        body["status"].pop("latestCreatedExecution")
    print(json.dumps(body))
    raise SystemExit

if args[:4] == ["run", "jobs", "executions", "describe"]:
    mode = os.environ.get("LATEST_MODE", "success")
    status = {
        "conditions": [{
            "type": "Completed",
            "status": "True" if mode == "success" else "False",
        }],
        "completionTime": "2026-09-01T23:35:49.869929Z",
        "succeededCount": 1 if mode == "success" else 0,
        "failedCount": 1 if mode in {"failed", "contradictory"} else 0,
        "cancelledCount": 1 if mode == "cancelled" else 0,
        "runningCount": 1 if mode in {"running", "contradictory"} else 0,
    }
    if mode in {"running", "unknown"}:
        status.pop("completionTime")
    if mode == "running":
        status["conditions"][0]["status"] = "Unknown"
    if mode == "unknown":
        status["conditions"] = [{"type": "Started", "status": "True"}]
    if mode == "zero-terminal-count":
        status["failedCount"] = 0
    labels = {"run.googleapis.com/job": job}
    if mode == "wrong-job":
        labels["run.googleapis.com/job"] = "another-job"
    print(json.dumps({"metadata": {"labels": labels}, "status": status}))
    raise SystemExit

if args[:3] == ["run", "jobs", "update"]:
    raise SystemExit

if args[:3] == ["run", "jobs", "execute"]:
    print(job + "-new00")
    raise SystemExit

print("unexpected fake gcloud call: " + " ".join(args), file=sys.stderr)
raise SystemExit(97)
''',
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    return calls


def _run_host_action(
    tmp_path: Path,
    action: str,
    mode: str,
    *,
    git_status_mode: str = "clean",
) -> tuple[subprocess.CompletedProcess[str], str]:
    tmp_path.mkdir(parents=True)
    _install_fake_git(tmp_path)
    calls = _install_fake_gcloud(tmp_path)
    payload = tmp_path / "payload.json"
    payload.write_text("{}", encoding="utf-8")
    argv = ["bash", str(SCRIPT), action, IMAGE, CODE_SHA, BUILD_ID]
    if action == "install":
        pass
    elif action == "task0":
        argv.append(str(payload))
    else:
        argv.extend([str(payload), JOB + "-old00"])
    result = subprocess.run(
        argv,
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "FAKE_GCLOUD_CALLS": str(calls),
            "LATEST_MODE": mode,
            "GIT_STATUS_MODE": git_status_mode,
        },
        text=True,
        capture_output=True,
        check=False,
    )
    return result, (
        calls.read_text(encoding="utf-8") if calls.exists() else ""
    )


def test_cloud_shell_is_syntax_valid_and_default_off() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    result = subprocess.run(
        ["bash", str(SCRIPT), "container-help"],
        check=True, capture_output=True, text=True,
    )
    assert result.stdout.strip() == "container modes: task0 task reopen-task"
    text = SCRIPT.read_text(encoding="utf-8")
    assert "--max-retries 0" in text
    assert "--tasks 54 --parallelism 54" in text
    assert "jobs executions list" not in text
    assert "storage ls" not in text
    assert "task0)" in text
    assert "task0-gate" in text
    assert "extract_task0_receipt" in text
    assert "gcloud logging read" in text
    assert "run.googleapis.com%2Fstdout" in text
    assert "TASK0_GATE_B64" in text
    assert 'structured = row.get("jsonPayload")' in text
    assert '.spec.template.spec.timeoutSeconds == "21600"' in text
    assert "reopen-task)" in text
    assert "reopen-collect)" in text
    assert "rm -rf \"$tmp\"" in text
    assert 'trap "rm -rf -- \'$work\'" EXIT' in text
    assert "cleanup_container()" not in text
    assert "submit_output=$(gcloud builds submit" in text
    assert "grep -Eo '[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}'" in text
    assert '[[ "${#build_ids[@]}" -eq 1 ]]' in text
    assert "IMAGE_SOURCE_COMMIT_SHA=$CODE_SHA" not in text
    assert "cat /app/SOURCE_COMMIT" in text
    assert '[[ "$ACTION" =~ ^(install|task0|task|reopen-task)$ ]]' in text
    assert 'require_exact_clean_git "$ROOT" "host checkout"' in text
    terminal_gate = text.index("reused job latest execution is not terminal and idle")
    assert terminal_gate < text.index('gcloud run jobs update "$JOB"')
    assert terminal_gate < text.index('gcloud run jobs execute "$JOB"')


def test_container_fails_before_payload_without_enable_gate() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "container-run", "task"],
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 2
    assert "matrix freezer disabled" in result.stderr


@pytest.mark.parametrize("mode", ["dirty", "failure"])
def test_host_mutation_rejects_non_exact_clean_checkout_before_cloud_mutation(
    tmp_path: Path,
    mode: str,
) -> None:
    result, calls = _run_host_action(
        tmp_path / mode, "install", "success", git_status_mode=mode,
    )
    assert result.returncode == 2
    assert (
        "host checkout must be exact-clean" in result.stderr
        if mode == "dirty"
        else "host checkout Git status is unavailable" in result.stderr
    )
    assert calls == ""


def test_container_cleanup_survives_local_scope_exit(tmp_path: Path) -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    match = re.search(r'^  (trap "rm -rf -- \'\$work\'" EXIT)$', text, re.MULTILINE)
    assert match is not None
    work = tmp_path / "payload-work"
    shell = f"""
set -euo pipefail
container_scope() {{
  local work={work!s}
  mkdir -p "$work"
  : >"$work/payload.json"
  {match.group(1)}
}}
container_scope
[[ -f {work!s}/payload.json ]]
"""
    result = subprocess.run(
        ["bash", "-c", shell], text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not work.exists()


@pytest.mark.parametrize("mode", ["success", "failed", "cancelled"])
def test_install_accepts_exact_terminal_idle_predecessor(
    tmp_path: Path,
    mode: str,
) -> None:
    result, calls = _run_host_action(tmp_path / mode, "install", mode)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"installed": True, "default_off": True}
    assert f"run jobs update {JOB}" in calls
    assert "run jobs execute" not in calls


@pytest.mark.parametrize("action", ["install", "task0", "task", "reopen-task"])
@pytest.mark.parametrize(
    "mode",
    ["running", "unknown", "contradictory", "zero-terminal-count", "wrong-job"],
)
def test_mutating_actions_reject_unsafe_latest_before_cloud_mutation(
    tmp_path: Path,
    action: str,
    mode: str,
) -> None:
    result, calls = _run_host_action(tmp_path / f"{action}-{mode}", action, mode)
    assert result.returncode == 2
    assert "latest execution is not terminal and idle" in result.stderr
    assert f"run jobs update {JOB}" not in calls
    assert f"run jobs execute {JOB}" not in calls


@pytest.mark.parametrize("action", ["install", "task0", "task", "reopen-task"])
def test_mutating_actions_reject_absent_latest_before_cloud_mutation(
    tmp_path: Path,
    action: str,
) -> None:
    result, calls = _run_host_action(
        tmp_path / action,
        action,
        "missing-latest",
    )
    assert result.returncode == 2
    assert "lacks an exact latest execution" in result.stderr
    assert "run jobs executions describe" not in calls
    assert f"run jobs update {JOB}" not in calls
    assert f"run jobs execute {JOB}" not in calls
