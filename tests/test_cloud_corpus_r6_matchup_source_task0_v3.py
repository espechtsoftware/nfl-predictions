from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/cloud_corpus_r6_matchup_source_task0_v3.sh"
DOCKERFILE = ROOT / "Dockerfile.corpus-r6-matchup-source-v3"
CLOUDBUILD = ROOT / "cloudbuild.corpus-r6-matchup-source-v3.yaml"
TASK0_RUNNER = ROOT / "scripts/run_corpus_r6_matchup_source_task0_v3.py"
SOURCE_RUNNER = ROOT / "scripts/run_corpus_r6_matchup_source_batch_v3.py"


def _stdout_result_python() -> str:
    text = SCRIPT.read_text(encoding="utf-8")
    match = re.search(r"STDOUT_RESULT_PY='\n(.*?)\n'\n", text, re.DOTALL)
    assert match is not None
    return match.group(1)


def _extract_stdout(
    tmp_path: Path,
    logs: list[dict[str, object]],
    *,
    schema: str,
) -> subprocess.CompletedProcess[bytes]:
    log_path = tmp_path / "logs.json"
    log_path.write_bytes(json.dumps(logs).encode("utf-8"))
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            _stdout_result_python(),
            str(ROOT / "src"),
            str(log_path),
            schema,
        ],
        capture_output=True,
        check=False,
    )


def _canonical_timeout(
    tmp_path: Path, task_spec: dict[str, object],
) -> subprocess.CompletedProcess[str]:
    execution_path = tmp_path / "execution.json"
    execution_path.write_text(
        json.dumps({"spec": {"template": {"spec": task_spec}}}),
        encoding="utf-8",
    )
    text = SCRIPT.read_text(encoding="utf-8")
    match = re.search(
        r"^canonical_timeout_seconds\(\) \{\n.*?^\}",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None
    return subprocess.run(
        [
            "bash",
            "-c",
            f'{match.group(0)}\ncanonical_timeout_seconds "$1"',
            "source-v3-timeout-test",
            str(execution_path),
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def _shell_function(text: str, name: str) -> str:
    match = re.search(
        rf"^{re.escape(name)}\(\) \{{\n.*?^\}}",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None
    return match.group(0)


def test_controller_is_syntax_valid_and_exposes_only_explicit_container_modes() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    result = subprocess.run(
        ["bash", str(SCRIPT), "container-help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "container modes: worker verify publish reopen"


def test_controller_requires_provider_bound_worker_verifier_and_publish_receipts() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "EXPECTED_JOB_UID=1f4bcf0a-2300-4afa-9fc1-9981844c8275" in text
    assert "--max-retries 0" in text
    assert "--async --format=json" in text
    assert "execution=$(jq -er '.metadata.name'" in text
    assert "CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_WORKER" in text
    assert "CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_VERIFY" in text
    assert "sourceProvenance.resolvedGitSource.revision == $code" in text
    assert 'require_exact_clean_git "$ROOT" "Commit B checkout"' in text
    assert 'status=$(git -C "$repository" status' in text
    assert '[[ -z "$status" ]]' in text
    assert '-z "$(git -C ' not in text
    assert 'die "$label must be exact-clean"' in text
    assert "CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_VERIFIER_EXECUTION" in text
    assert "--action bind-provider-receipt" not in text
    assert "--action validate-provider-receipt" in text
    assert "bind_controller_provider_receipt" in text
    assert "persist_controller_artifact" in text
    assert "_exact_reopen_provider_receipt_v3" in text
    assert ".provider_execution_spec.phase == \"worker\"" in text
    assert ".provider_execution_spec.phase == \"verify\"" in text
    assert ".operator_output.worker_result_identity" in text
    assert "cp \"$work/worker.json\" \"$payload\"" in text
    assert (
        'cp "$work/verifier.json.provider-receipt.identity.json" "$payload"'
        in text
    )
    assert "--action validate-receipt" not in text
    assert '"$action" =~ ^(worker|verify|publish|reopen|result)$' in text
    assert '"container-run","reopen"' in text
    assert "write_inventory_count == 0" in text
    assert "CORPUS_R6_MATCHUP_SOURCE_V3_PUBLISHER_EXECUTION" in text
    assert '"$ROOT/.venv/bin/python" "$ROOT/$TASK0_RUNNER"' not in text
    assert text.count('"$ROOT/.venv/bin/python" -I "$ROOT/$TASK0_RUNNER"') == 7
    assert text.count('source_root = pathlib.Path(sys.argv.pop(1)).resolve()') == 3
    assert '"$ROOT/src" "$source" "$uri"' in text
    assert '"$ROOT/src" "$spec" "$operator" "$predecessor"' in text
    assert '"$ROOT/src" "$identity"' in text


def test_host_runners_import_modules_from_their_exact_release_tree() -> None:
    probe = """
import pathlib
import runpy
import sys
runner = pathlib.Path(sys.argv[1]).resolve()
namespace = runpy.run_path(str(runner), run_name="_source_v3_origin_probe")
module = namespace[sys.argv[2]]
print(pathlib.Path(module.__file__).resolve())
"""
    expectations = (
        (
            TASK0_RUNNER,
            "task0",
            ROOT / "src/nfl_dfs/research/corpus_r6_matchup_source_task0_v3.py",
        ),
        (
            SOURCE_RUNNER,
            "batch",
            ROOT
            / "src/nfl_dfs/research/corpus_r6_matchup_source_batch_outer_candidate_authority_v3.py",
        ),
    )
    for runner, module_name, expected in expectations:
        result = subprocess.run(
            [sys.executable, "-I", "-c", probe, str(runner), module_name],
            capture_output=True,
            check=False,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert Path(result.stdout.strip()) == expected.resolve()


def test_exact_clean_gate_rejects_dirty_or_unavailable_git_status(
    tmp_path: Path,
) -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    shell = "\n".join(
        (
            'die() { printf \'%s\\n\' "ERROR: $*" >&2; exit 2; }',
            _shell_function(text, "require_exact_clean_git"),
            'require_exact_clean_git "$1" "test checkout"',
        )
    )
    absent = subprocess.run(
        ["bash", "-c", shell, "source-v3-clean-test", str(tmp_path / "absent")],
        capture_output=True,
        check=False,
        text=True,
    )
    assert absent.returncode == 2
    assert "Git status is unavailable" in absent.stderr

    repository = tmp_path / "repository"
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    clean = subprocess.run(
        ["bash", "-c", shell, "source-v3-clean-test", str(repository)],
        capture_output=True,
        check=False,
        text=True,
    )
    assert clean.returncode == 0, clean.stderr

    (repository / "untracked").write_text("dirty", encoding="utf-8")
    dirty = subprocess.run(
        ["bash", "-c", shell, "source-v3-clean-test", str(repository)],
        capture_output=True,
        check=False,
        text=True,
    )
    assert dirty.returncode == 2
    assert "must be exact-clean" in dirty.stderr


def test_controller_deep_validates_provider_execution_and_exact_payload() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert '.metadata.labels["run.googleapis.com/jobUid"] == $expected_job_uid' in text
    assert '.metadata.labels["run.googleapis.com/jobGeneration"]' in text
    assert ".spec.taskCount == 1 and .spec.parallelism == 1" in text
    assert 'then "86400s"' in text
    assert '--arg timeout_seconds "$timeout_seconds"' in text
    assert 'timeout_seconds:$timeout_seconds' in text
    assert '$container.command == ["/bin/bash"]' in text
    assert '"container-run",$phase' in text
    assert '$container.resources.limits == {"cpu":"8","memory":"32Gi"}' in text
    assert "$env.IMAGE_DIGEST == $digest" in text
    assert "$env.CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_REFERENCE == $image" in text
    assert "$env.CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_SOURCE_COMMIT == $code" in text
    assert "payload base64 is not canonical" in text
    assert "MAX_PAYLOAD_BYTES=262144" in text
    assert "MAX_PAYLOAD_BASE64_BYTES=30000" in text
    assert text.count('gzip -n -9 -c') == 2
    assert 'gzip -t "$compressed"' in text
    assert 'gzip -dc "$compressed" >"$target"' in text
    assert "payload gzip encoding is not exact deterministic gzip-n9" in text
    assert 'command -v gzip >/dev/null' in text
    assert "payload_sha256:$payload_sha" in text
    assert "payload_bytes:($payload_bytes | tonumber)" in text
    assert "bound_worker_execution:" in text
    assert "bound_verifier_execution:" in text
    assert "corpus-r6-matchup-source-task0-provider-execution-spec/v3" in text


def test_controller_normalizes_exact_cloud_run_timeout_representations(
    tmp_path: Path,
) -> None:
    for task_spec in (
        {"timeoutSeconds": "86400"},
        {"timeout": "86400s"},
        {"timeout": "86400.000000000s"},
        {"timeoutSeconds": "86400", "timeout": "86400s"},
    ):
        result = _canonical_timeout(tmp_path, task_spec)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "86400s"

    for task_spec in (
        {},
        {"timeoutSeconds": "3600"},
        {"timeoutSeconds": "86400s"},
        {"timeoutSeconds": 86400},
        {"timeoutSeconds": None},
        {"timeoutSeconds": "86400", "timeout": "3600s"},
        {"timeoutSeconds": False, "timeout": "86400s"},
    ):
        result = _canonical_timeout(tmp_path, task_spec)
        assert result.returncode != 0


def test_stdout_result_accepts_one_exclusive_text_or_json_payload_per_phase(
    tmp_path: Path,
) -> None:
    schemas = (
        "corpus-r6-matchup-source-task0-worker-publication/v3",
        "corpus-r6-matchup-source-task0-verifier-receipt/v3",
        "corpus-r6-matchup-source-provider-publication-stdout/v3",
        "corpus-r6-matchup-source-independent-reopen-receipt/v3",
    )
    launcher = SCRIPT.read_text(encoding="utf-8")
    assert "(textPayload:* OR jsonPayload:*)" in launcher
    assert "source.canonical_json_bytes(body)" in launcher
    for schema in schemas:
        assert schema in launcher
        body = {"schema_version": schema, "complete": True, "probe": 1e-7}
        canonical = source.canonical_json_bytes(body) + b"\n"
        text_result = _extract_stdout(
            tmp_path,
            [{"textPayload": source.canonical_json_bytes(body).decode()}],
            schema=schema,
        )
        assert text_result.returncode == 0, text_result.stderr.decode()
        assert text_result.stdout == canonical
        json_result = _extract_stdout(
            tmp_path, [{"jsonPayload": body}], schema=schema,
        )
        assert json_result.returncode == 0, json_result.stderr.decode()
        assert json_result.stdout == canonical


def test_stdout_result_rejects_ambiguous_multiple_or_wrong_schema(
    tmp_path: Path,
) -> None:
    schema = "corpus-r6-matchup-source-task0-worker-publication/v3"
    body = {"schema_version": schema, "complete": True}
    canonical = source.canonical_json_bytes(body).decode()
    bad_logs = (
        [{"textPayload": canonical, "jsonPayload": body}],
        [{"textPayload": canonical}, {"jsonPayload": body}],
        [{"textPayload": "unrelated"}, {"jsonPayload": body}],
        [{"jsonPayload": {**body, "schema_version": "wrong/v3"}}],
        [{"textPayload": json.dumps(body, indent=2)}],
        [{"textPayload": 7}],
        [{"jsonPayload": [body]}],
    )
    for logs in bad_logs:
        result = _extract_stdout(tmp_path, logs, schema=schema)
        assert result.returncode != 0


def test_commit_b_build_preserves_exact_clean_git_runtime() -> None:
    docker = DOCKERFILE.read_text(encoding="utf-8")
    build = CLOUDBUILD.read_text(encoding="utf-8")
    assert "FROM python:3.11-slim" in docker
    assert "COPY . /app" in docker
    assert "git ca-certificates gzip jq libgomp1" in " ".join(docker.split())
    assert "git -C /app rev-parse HEAD" in docker
    assert "git -C /app rev-parse --is-shallow-repository" in docker
    assert "git -C /app status --porcelain --untracked-files=all" in docker
    assert '-z "$(git -C /app status' not in docker
    assert 'pip install --no-cache-dir --editable ".[gcp]"' in docker
    assert "run_corpus_r6_matchup_source_task0_v3.py --help" in docker
    assert "run_corpus_r6_matchup_source_batch_v3.py --help" in docker
    assert "_trusted_dependency_closure_v3" in docker
    assert "_trusted_capture_plan_v3" in docker
    assert "git -C release fetch --no-tags origin '${_CODE_SHA}'" in build
    assert "--depth=1" not in build
    assert "git -C release checkout --detach '${_CODE_SHA}'" in build
    assert "git -C release rev-parse --is-shallow-repository" in build
    assert "git jq libgomp1" in " ".join(build.split())
    assert '-z "$(git' not in build
    assert "pip install --no-cache-dir --editable '.[gcp]'" in build
    assert "_trusted_dependency_closure_v3" in build
    assert "_trusted_capture_plan_v3" in build
    assert "isolated-controller-smoke" in build
    assert build.count("docker run --rm --network none '${_BUILD_IMAGE}'") == 3
    assert "run_corpus_r6_matchup_source_task0_v3.py" in build
    assert "run_corpus_r6_matchup_source_batch_v3.py" in build
