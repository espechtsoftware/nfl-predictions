"""Offline contract for the dedicated current-bank crossed-screen image."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile.r6-current-bank-crossed-screen"
BUILD_CONFIG = ROOT / "cloudbuild.r6-current-bank-crossed-screen.yaml"
BUILD_IGNORE = ROOT / ".gcloudignore.r6-current-bank-crossed-screen"
REPORT = "reports/2026-08-27-r6-current-bank-crossed-screen-preoutput-contract.md"

MODULE_PATHS = (
    "src/nfl_dfs/research/corpus_r6_current_bank_crossed_screen_contract_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_crossed_screen_projection_preparation_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_crossed_screen_layer_preparation_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_crossed_screen_selector_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_crossed_screen_projection_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_crossed_screen_selection_assembler_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_crossed_screen_selection_fold_worker_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_crossed_screen_evaluation_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_crossed_screen_aggregate_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_crossed_screen_task_manifest_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_selector_successor_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_selector_successor_runtime_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_selector_successor_process_adapter_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_selector_successor_cloud_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_selector_rank150_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_diversity_selector_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_selector_rank150_dpp_mode_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_selector_successor_evaluation_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_selector_successor_evaluation_cloud_v1.py",
    "src/nfl_dfs/research/corpus_r6_current_bank_selector_successor_realized_bridge_v1.py",
    "src/nfl_dfs/research/corpus_extreme_tail_hard230_population_successor_v1.py",
    "src/nfl_dfs/research/corpus_extreme_tail_hard230_population_process_v1.py",
    "src/nfl_dfs/research/corpus_extreme_tail_hard230_r6_source_decoder_v1.py",
    "src/nfl_dfs/research/corpus_extreme_tail_hard230_r6_cloud_entrypoint_v1.py",
    "src/nfl_dfs/research/corpus_extreme_tail_hard230_r6_run_controller_v1.py",
    "src/nfl_dfs/research/corpus_r6_population_challenger_authority_v1.py",
    "src/nfl_dfs/research/corpus_r6_population_challenger_runtime_v1.py",
    "src/nfl_dfs/research/corpus_r6_population_challenger_cloud_v1.py",
    "src/nfl_dfs/research/corpus_r6_population_crossed_scoring_v1.py",
    "src/nfl_dfs/research/corpus_r6_population_crossed_cloud_v1.py",
    "src/nfl_dfs/research/corpus_r6_l2_base_rate_v1.py",
    "src/nfl_dfs/research/corpus_r6_l2_base_rate_runtime_v1.py",
    "src/nfl_dfs/research/corpus_r6_l2b_panel_cloud_v1.py",
    "src/nfl_dfs/research/corpus_r6_l2b_panel_operator_v1.py",
    "src/nfl_dfs/research/corpus_r6_l2b_pit_target_panel_v1.py",
    "src/nfl_dfs/research/corpus_r6_novel_roster_realized_grader_v1.py",
    "src/nfl_dfs/research/corpus_r6_l2b_selector_adapter_v1.py",
)
MODULE_NAMES = tuple(Path(path).stem for path in MODULE_PATHS)
RUNNERS = (
    "scripts/run_corpus_r6_current_bank_crossed_screen_projection_v1.py",
    "scripts/run_corpus_r6_current_bank_crossed_screen_selection_v1.py",
    "scripts/run_corpus_r6_current_bank_crossed_screen_evaluation_v1.py",
    "scripts/run_corpus_r6_current_bank_crossed_screen_aggregate_v1.py",
    "scripts/run_corpus_r6_current_bank_crossed_screen_task_dispatcher_v1.py",
    "scripts/run_corpus_r6_current_bank_terminal_root_timeout_recovery_v1.py",
    "scripts/run_corpus_r6_current_bank_selector_successor_cloud_v1.py",
    "scripts/run_corpus_r6_current_bank_selector_successor_evaluation_cloud_v1.py",
    "scripts/run_corpus_r6_current_bank_selector_successor_v1.py",
    "scripts/run_corpus_r6_current_bank_selector_rank150_dpp_v1.py",
    "scripts/run_corpus_r6_current_bank_selector_successor_realized_bridge_v1.py",
    "scripts/run_corpus_extreme_tail_hard230_r6_cloud_v1.py",
    "scripts/run_corpus_r6_population_challenger_v1.py",
    "scripts/run_corpus_r6_population_crossed_cloud_v1.py",
    "scripts/run_corpus_r6_l2b_panel_cloud_v1.py",
    "scripts/run_corpus_r6_l2b_selector_adapter_v1.py",
)
BUILD_ONLY_SCRIPTS = (
    "scripts/run_corpus_extreme_tail_hard230_r6_score_run_v1.py",
    "scripts/run_corpus_r6_population_challenger_cloud_v1.py",
    "scripts/materialize_corpus_r6_l2b_pit_target_panel_v1.py",
    "scripts/run_corpus_r6_novel_roster_realized_grader_v1.py",
)
OPERATOR = "scripts/run_corpus_r6_current_bank_crossed_screen_cloud_v1.py"
DISPATCHER = "scripts/run_corpus_r6_current_bank_crossed_screen_task_dispatcher_v1.py"
CANONICAL_DISPATCHER = (
    "/usr/local/bin/python3.11",
    "-I",
    f"/app/{DISPATCHER}",
)
FOCUSED_TESTS = (
    "tests/test_corpus_r6_current_bank_crossed_screen_selector_v1.py",
    "tests/test_corpus_r6_current_bank_crossed_screen_projection_preparation_execution_v1.py",
    "tests/test_corpus_r6_current_bank_crossed_screen_layer_preparation_v1.py",
    "tests/test_corpus_r6_current_bank_crossed_screen_projection_v1.py",
    "tests/test_corpus_r6_current_bank_crossed_screen_selection_execution_v1.py",
    "tests/test_corpus_r6_current_bank_crossed_screen_evaluation_execution_v1.py",
    "tests/test_corpus_r6_current_bank_crossed_screen_aggregate_execution_v1.py",
    "tests/test_corpus_r6_current_bank_crossed_screen_task_manifest_execution_v1.py",
    "tests/test_corpus_r6_current_bank_crossed_screen_task_dispatcher_v1.py",
    "tests/test_run_corpus_r6_current_bank_terminal_root_timeout_recovery_v1.py",
    "tests/test_corpus_r6_current_bank_selector_successor_v1.py",
    "tests/test_corpus_r6_current_bank_selector_successor_cloud_v1.py",
    "tests/test_corpus_r6_current_bank_selector_successor_evaluation_v1.py",
    "tests/test_corpus_r6_current_bank_selector_successor_evaluation_cloud_v1.py",
    "tests/test_corpus_r6_current_bank_selector_rank150_dpp_mode_v1.py",
    "tests/test_corpus_r6_current_bank_selector_successor_realized_bridge_v1.py",
    "tests/test_run_corpus_r6_current_bank_selector_successor_realized_bridge_v1.py",
    "tests/test_corpus_extreme_tail_hard230_r6_cloud_entrypoint_v1.py",
    "tests/test_corpus_extreme_tail_hard230_r6_run_controller_v1.py",
    "tests/test_corpus_r6_population_challenger_authority_v1.py",
    "tests/test_corpus_r6_population_challenger_runtime_v1.py",
    "tests/test_corpus_r6_population_challenger_cloud_v1.py",
    "tests/test_corpus_r6_population_crossed_scoring_v1.py",
    "tests/test_corpus_r6_population_crossed_cloud_v1.py",
    "tests/test_corpus_r6_l2b_panel_cloud_v1.py",
    "tests/test_corpus_r6_l2b_pit_target_panel_v1.py",
    "tests/test_corpus_r6_novel_roster_realized_grader_v1.py",
    "tests/test_run_corpus_r6_novel_roster_realized_grader_v1.py",
    "tests/test_corpus_r6_l2b_selector_adapter_v1.py",
    "tests/test_r6_current_bank_crossed_screen_build_contract.py",
    "tests/test_run_corpus_r6_current_bank_crossed_screen_cloud_v1.py",
)
FOCUSED_TEST_FIXTURES = (
    "tests/test_corpus_r6_current_bank_crossed_screen_contract_v1.py",
    "tests/test_corpus_r6_current_bank_selector_successor_authority_v1.py",
    "tests/test_corpus_r6_current_bank_selector_successor_process_adapter_v1.py",
)


def _build() -> dict[str, object]:
    retained = yaml.safe_load(BUILD_CONFIG.read_text(encoding="utf-8"))
    assert isinstance(retained, dict)
    return retained


def test_runtime_surface_contains_only_the_required_source_and_entrypoints() -> None:
    source = DOCKERFILE.read_text(encoding="utf-8")
    assert source.startswith("FROM python:3.14.4-slim\n")
    assert "WORKDIR /app" in source
    assert "COPY src /app/src" in source
    assert "COPY scripts /app/scripts" not in source
    assert "COPY . " not in source
    assert "COPY sql" not in source
    assert "COPY tests" not in source
    assert "ln -s /usr/local/bin/python3.14 /usr/local/bin/python3.11" in source
    assert '"numpy==2.5.1" "scipy==1.18.0"' in source
    for runner in RUNNERS:
        assert runner in source
    assert source.count(REPORT) == 2
    assert 'pip install --no-cache-dir --editable ".[gcp]"' in source
    assert ".[gcp,dev]" not in source
    assert ".[gcp,app]" not in source
    assert ".[gcp,graph]" not in source
    assert "PYTHONPATH" not in source
    expected_cmd = "CMD [" + ", ".join(
        f'"{token}"' for token in CANONICAL_DISPATCHER
    ) + "]"
    assert source.rstrip().endswith(expected_cmd)


def test_runtime_os_and_python_resources_are_narrow_and_reproducible() -> None:
    source = DOCKERFILE.read_text(encoding="utf-8")
    assert (
        "apt-get install -y --no-install-recommends libgomp1" in source
    )
    assert "rm -rf /var/lib/apt/lists/*" in source
    assert "ENV PYTHON" not in source
    assert "PYTHONPATH" not in source
    assert "PYTHONHOME" not in source
    for forbidden in (
        "gcloud", "gsutil", "git ", "curl ", "wget ", "neo4j", "uvicorn",
    ):
        assert forbidden not in source.lower()


def test_cloud_build_compiles_and_import_smokes_the_complete_boundary() -> None:
    source = BUILD_CONFIG.read_text(encoding="utf-8")
    assert "name: python:3.14.4-slim" in source
    assert "ln -s /usr/local/bin/python3.14 /usr/local/bin/python3.11" in source
    assert "'numpy==2.5.1' 'scipy==1.18.0'" in source
    compile_section = source.split("-m py_compile", 1)[1].split(
        "/usr/local/bin/python3.11 -I -c", 1
    )[0]
    for path in (*MODULE_PATHS, *RUNNERS, *BUILD_ONLY_SCRIPTS, OPERATOR):
        assert compile_section.count(path) == 1
    import_section = source.split(
        '/usr/local/bin/python3.11 -I -c "from nfl_dfs.research import ', 1
    )[1].split('"', 1)[0]
    for module in MODULE_NAMES:
        assert import_section.count(module) == 1


def test_cloud_build_runs_only_the_focused_current_bank_tests() -> None:
    source = BUILD_CONFIG.read_text(encoding="utf-8")
    pytest_section = source.split("-m pytest", 1)[1].split(
        "\n\n  - name:", 1
    )[0]
    observed = tuple(re.findall(r"tests/[a-zA-Z0-9_]+\.py", pytest_section))
    assert observed == FOCUSED_TESTS
    assert "test_corpus_r6_current_bank_crossed_screen_contract_v1.py" not in (
        observed
    )
    assert "pytest tests" not in source
    assert "-o addopts=''" in pytest_section


def test_build_order_and_image_publication_are_exact() -> None:
    config = _build()
    assert [step["id"] for step in config["steps"]] == [
        "focused-current-bank-contract-tests",
        "build-current-bank-runtime",
        "smoke-isolated-dispatcher-boundary",
    ]
    build_step = config["steps"][1]
    assert build_step["args"] == [
        "build", "--pull", "-f",
        "Dockerfile.r6-current-bank-crossed-screen",
        "-t", "${_IMAGE}", ".",
    ]
    assert config["images"] == ["${_IMAGE}"]
    assert config["timeout"] == "3600s"
    assert config["options"] == {
        "logging": "LEGACY",
        "machineType": "E2_HIGHCPU_8",
    }


def test_image_smoke_uses_fixed_isolated_dispatcher_and_no_network() -> None:
    source = BUILD_CONFIG.read_text(encoding="utf-8")
    smoke = source.split("id: smoke-isolated-dispatcher-boundary", 1)[1]
    normalized_smoke = " ".join(smoke.replace("\\\n", " ").split())
    assert smoke.count("docker run --rm --network=none '${_IMAGE}'") == 5
    assert " ".join(CANONICAL_DISPATCHER) in normalized_smoke
    assert "Path(nfl_dfs.__file__).resolve() == root/'src/nfl_dfs/__init__.py'" in smoke
    assert "'PYTHONPATH' not in os.environ" in smoke
    assert "'PYTHONHOME' not in os.environ" in smoke
    assert "specs=m.canonical_bootstrap_process_specs_v1()" in smoke
    assert "len(specs) == len(c.PROCESS_ROLES)" in smoke
    assert "sc.matrix_process_spec_v1(selector_process_mode=sc.RANK150_DPP_SELECTOR_MODE)" in smoke
    assert "rb.cloud_entrypoint_registration_v1()['command']" in smoke
    assert "h.ENTRYPOINT_COMMAND" in smoke
    assert "hc.CONTROLLER_ENTRYPOINT_COMMAND" in smoke
    assert "corpus_r6_l2b_selector_adapter_v1 as l2s" in smoke
    assert "scripts/run_corpus_r6_l2b_selector_adapter_v1.py" in smoke
    assert "run_corpus_r6_current_bank_terminal_root_timeout_recovery_v1.py" in smoke
    assert "corpus-r6-v7-terminal-root-timeout-recovery-failure/v1" in smoke
    assert f"/app/{DISPATCHER} --help" in normalized_smoke
    assert "task dispatcher failed closed: dispatcher kernel command token count differs" in smoke
    assert "task dispatcher failed closed: dispatcher requires exact R6_CURRENT_BANK_TASK_DISPATCH_ENABLED=1" in smoke
    assert "google-cloud-storage" not in smoke.lower()
    assert "gcloud" not in smoke.lower()


def test_cloud_build_has_no_deployment_or_external_data_authority() -> None:
    source = BUILD_CONFIG.read_text(encoding="utf-8").lower()
    for forbidden in (
        "gcloud run", "gcloud storage", "gsutil", "bq ", "neo4j",
        "deploy", "iam", "secret",
    ):
        assert forbidden not in source
    assert "selector_successor_realized_bridge_v1.py publish --" not in source
    assert "run_corpus_extreme_tail_hard230_r6_cloud_v1.py execute-task --" not in source


def test_dedicated_build_context_is_an_exact_small_allowlist() -> None:
    expected = {
        "**",
        "!.gcloudignore.r6-current-bank-crossed-screen",
        "!pyproject.toml",
        "!README.md",
        "!Dockerfile.r6-current-bank-crossed-screen",
        "!cloudbuild.r6-current-bank-crossed-screen.yaml",
        "!src/",
        "!src/**",
        "!scripts/",
        "!scripts/__init__.py",
        *(f"!{path}" for path in RUNNERS),
        *(f"!{path}" for path in BUILD_ONLY_SCRIPTS),
        f"!{OPERATOR}",
        "!reports/",
        f"!{REPORT}",
        "!tests/",
        *(f"!{path}" for path in FOCUSED_TEST_FIXTURES),
        *(f"!{path}" for path in FOCUSED_TESTS),
    }
    observed = {
        line.strip()
        for line in BUILD_IGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert observed == expected
    assert BUILD_CONFIG.read_text(encoding="utf-8").startswith(
        "# Submit only with:\n"
        "# gcloud builds submit --ignore-file=.gcloudignore.r6-current-bank-crossed-screen"
    )
    for bulky_or_sensitive in (
        ".git/", "data/", "reports/corpus-parametric-runs/",
        "reports/t230-production-runs/", "sql/", ".venv/",
    ):
        assert f"!{bulky_or_sensitive}" not in observed


def test_all_cloud_build_shell_steps_parse_offline() -> None:
    for step in _build()["steps"]:
        if step.get("entrypoint") != "bash":
            continue
        script = step["args"][-1].replace("$$", "$")
        completed = subprocess.run(
            ["bash", "-n"],
            input=script,
            text=True,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 0, (
            step["id"], completed.stdout, completed.stderr
        )
