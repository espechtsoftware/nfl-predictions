from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "build_generation_shadow_suite_image.sh"
DOCKERFILE = ROOT / "Dockerfile.generation-shadow-suite"
DOCKERIGNORE = ROOT / "Dockerfile.generation-shadow-suite.dockerignore"
BUILD_CONFIG = ROOT / "cloudbuild.generation-shadow-suite.yaml"
TEST_SUPPORT_SCRIPTS = (
    "aggregate_coherent_market_state_scorefree.py",
    "coherent_market_state_sources.py",
    "run_cbwu_seed_order_audit.py",
    "run_corpus_r6_current_bank_crossed_screen_evaluation_v1.py",
    "run_legal_soft_law.py",
    "verify_deployment.py",
)
WEEK1_OPERATOR_SCRIPT = "publish_week1_operating_book.py"


def _run(*args: str, cwd: Path) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def _committed_fixture(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    (repo / "src" / "nfl_dfs").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "scripts").mkdir()
    (repo / "reports").mkdir()
    (repo / "sql").mkdir()

    shutil.copy2(DOCKERFILE, repo / DOCKERFILE.name)
    shutil.copy2(DOCKERIGNORE, repo / DOCKERIGNORE.name)
    (repo / BUILD_CONFIG.name).write_text(
        "steps:\n"
        "  - args:\n"
        "      - src/nfl_dfs/__init__.py\n"
        "      - tests/test_placeholder.py\n",
        encoding="utf-8",
    )
    (repo / "cloudbuild.yaml").write_text(
        "steps:\n  - name: python\n    args: ['PYTHONPATH=src pytest']\n",
        encoding="utf-8",
    )
    shutil.copy2(BUILD_SCRIPT, repo / "scripts" / BUILD_SCRIPT.name)
    (repo / "scripts" / "cloud_generation_shadow_suite.sh").write_text(
        "#!/usr/bin/env bash\nexit 0\n", encoding="utf-8"
    )
    (repo / "scripts" / WEEK1_OPERATOR_SCRIPT).write_text(
        "raise SystemExit(0)\n", encoding="utf-8"
    )
    (repo / "scripts" / "unrelated_research_driver.py").write_text(
        "raise SystemExit('must not be uploaded')\n", encoding="utf-8"
    )
    for script_name in TEST_SUPPORT_SCRIPTS:
        (repo / "scripts" / script_name).write_text(
            "# exact allowlisted test support\n", encoding="utf-8"
        )
    (repo / "pyproject.toml").write_text(
        "[build-system]\nrequires=['setuptools']\n", encoding="utf-8"
    )
    (repo / "README.md").write_text("committed readme\n", encoding="utf-8")
    (repo / "src" / "nfl_dfs" / "__init__.py").write_text(
        "ARCHIVE_MARKER = 'committed-source'\n", encoding="utf-8"
    )
    (repo / "tests" / "test_placeholder.py").write_text(
        "def test_placeholder(): assert True\n", encoding="utf-8"
    )
    (repo / "reports" / "large-unrelated-artifact.bin").write_bytes(b"x" * 4096)
    (repo / "sql" / "unrelated.sql").write_text("select 1;\n", encoding="utf-8")

    _run("git", "init", "-q", cwd=repo)
    _run("git", "add", ".", cwd=repo)
    _run(
        "git", "-c", "user.name=Build Test", "-c",
        "user.email=build-test@example.invalid", "commit", "-qm", "fixture",
        cwd=repo,
    )
    code_sha = _run("git", "rev-parse", "HEAD", cwd=repo)
    _run("git", "update-ref", "refs/remotes/origin/main", code_sha, cwd=repo)
    assert len(code_sha) == 40
    return repo, code_sha


def _fake_gcloud(tmp_path: Path) -> tuple[Path, Path]:
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    capture = tmp_path / "gcloud-capture.json"
    fake = binary_dir / "gcloud"
    fake.write_text(
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
if args[:2] == ['builds', 'submit'] and len(args) >= 3:
    context = Path(args[2])
    record = {
        'args': args,
        'files': sorted(
            str(path.relative_to(context))
            for path in context.rglob('*')
            if path.is_file()
        ),
        'source': (context / 'src/nfl_dfs/__init__.py').read_text(),
    }
    Path(os.environ['GCLOUD_CAPTURE']).write_text(json.dumps(record, sort_keys=True))
    print('submitted build 12345678-1234-1234-1234-123456789abc SUCCESS')
elif args[:3] == ['builds', 'describe', '12345678-1234-1234-1234-123456789abc']:
    print('sha256:' + 'a' * 64)
else:
    raise SystemExit(97)
""",
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    return binary_dir, capture


def test_clean_archive_submit_is_commit_bound_and_excludes_unrelated_trees(
    tmp_path: Path,
) -> None:
    repo, code_sha = _committed_fixture(tmp_path)
    binary_dir, capture = _fake_gcloud(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{binary_dir}:{os.environ['PATH']}",
        "GCLOUD_CAPTURE": str(capture),
    }

    result = subprocess.run(
        ["bash", str(BUILD_SCRIPT), "--execute", code_sha],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    image = (
        "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
        f"nfl-dfs:generation-shadow-{code_sha}"
    )
    assert result.stdout.splitlines() == [
        "BUILD_ID=12345678-1234-1234-1234-123456789abc",
        f"CODE_SHA={code_sha}",
        f"BUILD_IMAGE_TAG={image}",
        f"IMAGE={image.rsplit(':', 1)[0]}@sha256:{'a' * 64}",
    ]

    record = json.loads(capture.read_text(encoding="utf-8"))
    assert record["source"] == "ARCHIVE_MARKER = 'committed-source'\n"
    files = set(record["files"])
    assert "src/nfl_dfs/__init__.py" in files
    assert "tests/test_placeholder.py" in files
    assert "scripts/build_generation_shadow_suite_image.sh" in files
    assert "scripts/cloud_generation_shadow_suite.sh" in files
    assert f"scripts/{WEEK1_OPERATOR_SCRIPT}" in files
    assert "cloudbuild.yaml" in files
    for script_name in TEST_SUPPORT_SCRIPTS:
        assert f"scripts/{script_name}" in files
    assert not any(path.startswith("reports/") for path in files)
    assert not any(path.startswith("sql/") for path in files)
    assert "scripts/unrelated_research_driver.py" not in files
    assert not any(path.startswith(".git/") for path in files)

    args = record["args"]
    assert args[:2] == ["builds", "submit"]
    assert f"_CODE_SHA={code_sha},_BUILD_IMAGE={image}" in next(
        arg for arg in args if arg.startswith("--substitutions=")
    )
    assert _run("git", "status", "--porcelain=v1", cwd=repo) == ""
    build_context_root = repo / ".build-contexts"
    assert build_context_root.is_dir()
    assert list(build_context_root.iterdir()) == []


def test_dirty_worktree_cannot_enter_exact_commit_archive(tmp_path: Path) -> None:
    repo, code_sha = _committed_fixture(tmp_path)
    binary_dir, capture = _fake_gcloud(tmp_path)
    (repo / "untracked-work.txt").write_text("not committed\n", encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{binary_dir}:{os.environ['PATH']}",
        "GCLOUD_CAPTURE": str(capture),
    }

    result = subprocess.run(
        ["bash", str(BUILD_SCRIPT), "--execute", code_sha],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(capture.read_text(encoding="utf-8"))
    assert "untracked-work.txt" not in record["files"]


def test_committed_build_reference_must_exist_before_cloud_submission(
    tmp_path: Path,
) -> None:
    repo, _ = _committed_fixture(tmp_path)
    (repo / BUILD_CONFIG.name).write_text(
        "steps:\n"
        "  - args:\n"
        "      - src/nfl_dfs/__init__.py\n"
        "      - tests/test_absent_from_commit.py\n",
        encoding="utf-8",
    )
    _run("git", "add", BUILD_CONFIG.name, cwd=repo)
    _run(
        "git", "-c", "user.name=Build Test", "-c",
        "user.email=build-test@example.invalid", "commit", "-qm",
        "missing build reference", cwd=repo,
    )
    code_sha = _run("git", "rev-parse", "HEAD", cwd=repo)
    _run("git", "update-ref", "refs/remotes/origin/main", code_sha, cwd=repo)
    binary_dir, capture = _fake_gcloud(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{binary_dir}:{os.environ['PATH']}",
        "GCLOUD_CAPTURE": str(capture),
    }

    result = subprocess.run(
        ["bash", str(BUILD_SCRIPT), "--execute", code_sha],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert (
        "Cloud Build references an absent committed file: "
        "tests/test_absent_from_commit.py"
    ) in result.stderr
    assert not capture.exists()


def test_submit_helper_requires_explicit_execute(tmp_path: Path) -> None:
    repo, _ = _committed_fixture(tmp_path)
    binary_dir, capture = _fake_gcloud(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{binary_dir}:{os.environ['PATH']}",
        "GCLOUD_CAPTURE": str(capture),
    }

    result = subprocess.run(
        ["bash", str(BUILD_SCRIPT)],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "usage:" in result.stderr
    assert not capture.exists()


def test_runtime_image_and_cloud_build_use_only_the_dedicated_context() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    dockerignore = DOCKERIGNORE.read_text(encoding="utf-8")
    build = BUILD_CONFIG.read_text(encoding="utf-8")

    assert "ARG SOURCE_COMMIT_SHA=unknown" in dockerfile
    assert 'org.opencontainers.image.revision="${SOURCE_COMMIT_SHA}"' in dockerfile
    assert 'IMAGE_SOURCE_COMMIT_SHA="${SOURCE_COMMIT_SHA}"' in dockerfile
    assert "COPY src ./src" in dockerfile
    assert 'RUN pip install --no-cache-dir ".[gcp]"' in dockerfile
    assert "COPY ." not in dockerfile
    copy_lines = "\n".join(
        line for line in dockerfile.splitlines() if line.startswith("COPY ")
    )
    for excluded in ("reports", "tests", "scripts", "sql", "HANDOFF", "CLAUDE"):
        assert excluded not in copy_lines

    assert dockerignore.splitlines()[0] == "**"
    assert "!src/**" in dockerignore
    assert "!README.md" in dockerignore
    assert "!pyproject.toml" in dockerignore

    assert "test ! -e reports" in build
    assert "test ! -e sql" in build
    assert "test ! -e .git" in build
    assert "Dockerfile.generation-shadow-suite" in build
    assert "tests/test_generation_shadow_clean_build.py" in build
    assert "src/nfl_dfs/inference/prospective_boom_first.py" in build
    assert "tests/test_prospective_boom_first.py" in build
    assert "src/nfl_dfs/inference/prospective_cross_law_supply_trace.py" in build
    assert "tests/test_prospective_cross_law_supply_trace.py" in build
    assert "src/nfl_dfs/inference/week1_operating_book_operator.py" in build
    assert "tests/test_publish_week1_operating_book_script.py" in build
    assert "scripts/publish_week1_operating_book.py" in build
    assert "- '${_BUILD_IMAGE}'" in build
