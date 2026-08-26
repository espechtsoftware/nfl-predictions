from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cloud_r6_full_union_score_chain_v1.sh"
DOCKERFILE = ROOT / "Dockerfile.r6-post-freeze"
COMPILE_CLI = ROOT / "scripts" / "compile_corpus_r6_full_union_query_v1.py"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_help_is_offline_inert_and_shell_is_valid() -> None:
    syntax = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr
    result = subprocess.run(
        ["bash", str(SCRIPT), "help"],
        cwd=ROOT,
        env={"PATH": os.environ["PATH"]},
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "outcome-blind actual-root smoke" in result.stdout
    assert "R6_SCORE_RUN_ID is required" not in result.stderr


def test_reuses_one_existing_digest_job_with_bounded_execution() -> None:
    source = _source()
    assert 'gcloud run jobs describe "$JOB"' in source
    assert 'gcloud run jobs update "$JOB"' in source
    assert 'gcloud run jobs execute "$JOB"' in source
    assert '--tasks 1 --parallelism 1' in source
    assert '--max-retries 0' in source
    assert '[[ "$IMAGE" =~ @sha256:[0-9a-f]{64}$ ]]' in source
    for forbidden in (
        "gcloud run jobs create",
        "gcloud run jobs deploy",
        "gcloud run jobs delete",
        "gcloud projects get-iam-policy",
        "gcloud storage buckets get-iam-policy",
        "neo4j-admin",
        "cypher-shell",
    ):
        assert forbidden not in source.lower()


def test_runner_paths_match_the_post_freeze_image_layout() -> None:
    source = _source()
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "WORKDIR /opt/nfl-predictions" in dockerfile
    assert "/opt/nfl-predictions/scripts/" in source
    assert "/app/scripts" not in source


def test_smoke_closes_and_exact_known_objects_resolve_before_lease() -> None:
    source = _source()
    ensure = source.index("ensure_smoke_closed()")
    acquire = source.index("acquire_or_resolve_lease()")
    supply = source.index("supply_stage()")
    supply_body = source[supply:source.index("grade_stage()", supply)]
    assert ensure < acquire < supply
    assert supply_body.index("ensure_smoke_closed") < supply_body.index(
        "acquire_or_resolve_lease"
    )
    ensure_body = source[ensure:acquire]
    assert "stage_token smoke R6_FULL_UNION_ACTUAL_ROOT_SMOKE_ENABLED" in ensure_body
    assert "wait_terminal" in ensure_body
    assert '"${smoke_args[@]}"' in ensure_body
    assert "$SUPPLY_PREFIX/outcome-key-projection.json" in ensure_body
    assert "$SUPPLY_PREFIX/actual-root-smoke-receipt.json" in ensure_body
    assert "R6_FULL_UNION_ACTUAL_ROOT_SMOKE_ENABLED" in source
    assert "R6_FULL_UNION_OUTCOME_SUPPLY_ENABLED" in source
    assert "actual-root-smoke-receipt.json\" actual-root-smoke" in source
    assert "--expected-lease-generation" in source


def test_server_compile_receipt_is_required_before_smoke_supply_or_grade() -> None:
    source = _source()
    compile_stage = source[
        source.index("compile_stage()") : source.index("ensure_compile_closed()")
    ]
    ensure_compile = source[
        source.index("ensure_compile_closed()") : source.index("smoke()")
    ]
    smoke = source[source.index("smoke()") : source.index("ensure_smoke_closed()")]
    supply = source[source.index("supply_stage()") : source.index("grade_stage()")]
    grade = source[source.index("grade_stage()") : source.index("finish()")]
    finish = source[source.index("finish()") : source.index("status()")]

    assert "R6_FULL_UNION_QUERY_COMPILE_ENABLED" in compile_stage
    assert "query-compile-receipt.json" in compile_stage
    assert "validate_compile_receipt" in compile_stage
    assert "wait_terminal" in ensure_compile
    assert "validate_compile_receipt" in ensure_compile
    assert smoke.index("ensure_compile_closed") < smoke.index("preflight")
    assert supply.index("ensure_compile_closed") < supply.index("preflight")
    assert supply.index("ensure_compile_closed") < supply.index(
        "acquire_or_resolve_lease"
    )
    assert grade.index("ensure_compile_closed") < grade.index("preflight")
    assert "ensure_compile_closed" in finish
    assert 'run) compile_stage; smoke; supply_stage; grade_stage; finish ;;' in source


def test_compile_identity_is_bound_into_every_post_compile_stage_token() -> None:
    source = _source()
    token = source[source.index("stage_token()") : source.index("stage_env_json()")]
    launch = source[source.index("launch_stage()") : source.index("validate_compile_receipt()")]
    binding = source[
        source.index("compile_binding_json()") : source.index("compile_stage()")
    ]

    assert 'compile_binding="$(compile_binding_json "$stage")"' in token
    assert '"$SERVICE_ACCOUNT" "$compile_binding"' in token
    assert "query_compile_receipt:$compile_binding" in launch
    for field in (
        "uri:$uri",
        "generation:$generation",
        "sha256:$sha256",
        "bytes:$bytes",
        "compile_receipt_sha256:$self_hash",
        "sql_sha256:$sql_sha256",
    ):
        assert field in binding


def test_compile_stage_argv_matches_packaged_cli_and_receipt_contract() -> None:
    source = _source()
    cli_source = COMPILE_CLI.read_text(encoding="utf-8")
    compile_args = source[source.index("compile_args=(") : source.index(
        "\n\npreflight()", source.index("compile_args=(")
    )]
    validator = source[
        source.index("validate_compile_receipt()") : source.index(
            "compile_stage()"
        )
    ]
    for option in (
        "--execute",
        "--project",
        "--location",
        "--code-sha",
        "--image",
        "--receipt",
        "--receipt-uri",
    ):
        assert option in compile_args
        if option != "--execute":
            assert f'add_argument("{option}"' in cli_source
    for field in (
        "runtime_git_head",
        "runtime_git_worktree_clean",
        "query_module_sha256",
        "compile_script_sha256",
        "compile_receipt_sha256",
    ):
        assert field in validator
    assert "compiled_epoch - snapshot_epoch == 60" in validator
    assert 'payload_sha="$(sha256sum "$payload"' in validator
    assert 'payload_bytes="$(wc -c <"$payload"' in validator
    assert '$SUPPLY_PREFIX/query-compile-receipt.json' in validator


def test_missing_compile_evidence_fails_before_any_gcloud_call(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    marker = tmp_path / "gcloud-called"
    fake_gcloud = fake_bin / "gcloud"
    fake_gcloud.write_text(
        "#!/usr/bin/env bash\nprintf called >\"$FAKE_GCLOUD_MARKER\"\nexit 99\n",
        encoding="utf-8",
    )
    fake_gcloud.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_GCLOUD_MARKER": str(marker),
        "R6_SCORE_RUN_ID": "offline-r6-score-run",
        "R6_SCORE_JOB": "atlas-minimal-c-s2023-w1-v1",
        "R6_SCORE_SERVICE_ACCOUNT": (
            "817589974517-compute@developer.gserviceaccount.com"
        ),
        "R6_SCORE_CODE_SHA": "a" * 40,
        "R6_SCORE_IMAGE": (
            "us-central1-docker.pkg.dev/nfl-predictions-503414/"
            "nfl-dfs/nfl-dfs@sha256:" + "b" * 64
        ),
        "R6_SCORE_RUN_DIR": str(tmp_path / "run"),
        "R6_PANEL_FREEZE_URI": (
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "corpus-r6-full-union-freezes/"
            "20260826-foundry-v12-r6-full-union-freeze-v1/panel-freeze.json"
        ),
        "R6_PANEL_FREEZE_GENERATION": "1787759999999999",
        "R6_PANEL_FREEZE_SHA256": "c" * 64,
        "R6_PANEL_FREEZE_BYTES": "10",
        "R6_SNAPSHOT_MODULE_SHA256": "d" * 64,
        "R6_SNAPSHOT_CLI_SHA256": "e" * 64,
        "R6_SNAPSHOT_TEST_SHA256": "f" * 64,
        "R6_SNAPSHOT_CLI_TEST_SHA256": "0" * 64,
    }
    result = subprocess.run(
        ["bash", str(SCRIPT), "smoke"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "query compile launch intent is absent" in result.stderr
    assert not marker.exists()


def test_ambiguous_launch_is_claimed_and_never_blindly_reinvoked() -> None:
    source = _source()
    launch = source[source.index("launch_stage()") : source.index("smoke()")]
    assert "launch-intent.json" in launch
    assert "R6_CHAIN_STAGE_TOKEN" in source
    assert "recover_execution" in launch
    assert "execution-name recovery is ambiguous" in source
    assert "prior launch remains ambiguous; blind relaunch is forbidden" in launch
    assert "launch response is ambiguous; rerun only for exact recovery" in launch
    assert 'write_equal "$stage_dir/execution-name.txt"' in launch
    assert 'write_equal "$stage_dir/launch-intent.json" "$intent"' in launch
    assert '[[ "$WRITE_EQUAL_CREATED" == true ]] || intent_preexisted=true' in launch


def test_stage_intent_and_recovery_bind_gate_exact_argv_and_upstream_pins() -> None:
    source = _source()
    token = source[source.index("stage_token()") : source.index("stage_env_json()")]
    launch = source[source.index("launch_stage()") : source.index("smoke()")]
    recover = source[source.index("recover_execution()") : source.index("wait_terminal()")]
    assert (
        'printf \'%s\\0\' "$PROJECT" "$REGION" "$RUN_ID" "$JOB" '
        '"$stage" "$gate"' in token
    )
    assert 'printf \'%s\\0\' "$@"' in token
    assert "sha256sum | awk '{print $1}'" in token
    assert "argv_sha256:$argv_sha" in launch
    assert "gate:$gate" in launch
    assert "project:$project" in launch
    assert "region:$region" in launch
    assert "execution_env:$env" in launch
    assert "all_panel_snapshot_upstream_identities_bound_in_argv:true" in launch
    assert '$containers[0].args == $argv' in recover
    assert "== $expected_env" in recover
    for pin in (
        "--panel-freeze-generation",
        "--snapshot-module-sha256",
        "--expected-lease-generation",
    ):
        assert pin in source
    for prefix in (
        "outcome-supply-completion",
        "outcome-key-projection",
        "realized-source",
        "outcome-snapshot",
    ):
        assert f"identity_arg \"$RUN_DIR/objects/" in source
        assert prefix in source


def test_terminal_receipts_and_known_gcs_identities_are_retained() -> None:
    source = _source()
    assert "terminal-execution.json" in source
    assert "terminal-receipt.json" in source
    assert "gcloud storage objects describe" in source
    assert 'exact_uri="${uri}#${generation}"' in source
    assert 'gcloud storage cat "$exact_uri"' in source
    for name in (
        "outcome-key-projection.json",
        "actual-root-smoke-receipt.json",
        "supply-completion.json",
        "realized-source.json",
        "outcome-snapshot.json",
        "persisted-grade-root.json",
        "grade-completion.json",
    ):
        assert name in source


@pytest.mark.parametrize(
    ("metadata_name", "accepted"),
    [
        ("atlas-minimal-c-s2023-w1-v1-fplqf", True),
        (
            "projects/nfl-predictions-503414/locations/us-central1/jobs/"
            "atlas-minimal-c-s2023-w1-v1/executions/"
            "atlas-minimal-c-s2023-w1-v1-fplqf",
            True,
        ),
        ("atlas-minimal-c-s2023-w1-v1-fplqf-extra", False),
        ("prefix-atlas-minimal-c-s2023-w1-v1-fplqf", False),
        ("atlas-minimal-c-s2023-w1-v1-fplqf/extra", False),
        (
            "projects/other-project/locations/us-central1/jobs/"
            "atlas-minimal-c-s2023-w1-v1/executions/"
            "atlas-minimal-c-s2023-w1-v1-fplqf",
            False,
        ),
        (
            "projects/nfl-predictions-503414/locations/us-east1/jobs/"
            "atlas-minimal-c-s2023-w1-v1/executions/"
            "atlas-minimal-c-s2023-w1-v1-fplqf",
            False,
        ),
        (
            "projects/nfl-predictions-503414/locations/us-central1/jobs/"
            "other-job/executions/atlas-minimal-c-s2023-w1-v1-fplqf",
            False,
        ),
        (
            "projects/nfl-predictions-503414/locations/us-central1/jobs/"
            "atlas-minimal-c-s2023-w1-v1/executions/"
            "atlas-minimal-c-s2023-w1-v1-fplqf-extra",
            False,
        ),
    ],
)
def test_terminal_execution_name_accepts_only_short_or_qualified_exact_match(
    metadata_name: str, accepted: bool,
) -> None:
    source = _source()
    name_filter = (
        '(.metadata.name == $execution)\n'
        '          or (.metadata.name == (\n'
        '            "projects/" + $project + "/locations/" + $region\n'
        '            + "/jobs/" + $job + "/executions/" + $execution\n'
        '          ))'
    )
    assert name_filter in source
    result = subprocess.run(
        [
            "jq",
            "-e",
            "--arg",
            "execution",
            "atlas-minimal-c-s2023-w1-v1-fplqf",
            "--arg",
            "project",
            "nfl-predictions-503414",
            "--arg",
            "region",
            "us-central1",
            "--arg",
            "job",
            "atlas-minimal-c-s2023-w1-v1",
            name_filter,
        ],
        input=json.dumps({"metadata": {"name": metadata_name}}),
        check=False,
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) is accepted


def test_one_supply_then_grade_then_strict_generation_matched_release() -> None:
    source = _source()
    run_line = "run) compile_stage; smoke; supply_stage; grade_stage; finish ;;"
    assert run_line in source
    supply = source.index("supply_stage()")
    grade = source.index("grade_stage()")
    finish = source.index("finish()")
    assert supply < grade < finish
    assert source.count(
        "/opt/nfl-predictions/scripts/run_corpus_r6_full_union_outcome_supply_v1.py supply"
    ) == 1
    assert source.count(
        "/opt/nfl-predictions/scripts/run_corpus_r6_full_union_realized_grade_v1.py --execute"
    ) == 1
    assert "R6_FULL_UNION_REALIZED_GRADE_ENABLED" in source
    assert "materialize-r6-full-union-completion" in source
    assert "--required-contract r6-full-union" in source
    assert '--execution "$RUN_DIR/stages/grade/terminal-execution.json"' in source
    assert '--release-intent "$RUN_DIR/lease-release-intent.json"' in source
    assert '--release-receipt "$RUN_DIR/lease-release-receipt.json"' in source
    assert "validate-release-receipt" in source


def test_preflight_is_repeatable_and_retains_only_immutable_contract_shape() -> None:
    source = _source()
    preflight = source[source.index("preflight()") : source.index("stage_token()")]
    smoke = source[source.index("smoke()") : source.index("ensure_smoke_closed()")]
    supply = source[source.index("supply_stage()") : source.index("grade_stage()")]
    assert "preflight" in smoke
    assert "preflight" in supply
    assert 'local after="$RUN_DIR/job-config.json"' in preflight
    assert "job-before.json" not in preflight
    assert "resourceVersion" not in preflight
    assert "generation" not in preflight
    assert "createTimestamp" not in preflight
    assert 'schema_version:"r6-full-union-isolated-job-contract/v1"' in preflight
    assert "write_equal \"$after\"" in preflight
    for clear_flag in (
        "--args=\"\"",
        "--clear-env-vars",
        "--clear-secrets",
        "--clear-volume-mounts",
        "--clear-volumes",
        "--clear-cloudsql-instances",
        "--clear-vpc-connector",
        "--clear-network",
    ):
        assert clear_flag in preflight
    assert "--clear-network-tags" not in preflight
    assert '--service-account "$SERVICE_ACCOUNT"' in preflight
    assert "$task.serviceAccountName == $service_account" in preflight
    assert "(($containers[0].args // []) == [])" in preflight
    assert "(($containers[0].env // []) == [])" in preflight
    assert "(($task.volumes // []) == [])" in preflight
    assert "(($task.vpcAccess // {}) == {})" in preflight


@pytest.mark.parametrize(
    "service_account",
    [
        "817589974517-compute@developer.gserviceaccount.com",
        "r6-score-runtime@nfl-predictions-503414.iam.gserviceaccount.com",
    ],
)
def test_actual_job_service_accounts_and_panel_root_survive_repeatable_preflight(
    tmp_path: Path, service_account: str,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_gcloud = fake_bin / "gcloud"
    fake_gcloud.write_text(
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
state = Path(os.environ["FAKE_GCLOUD_STATE"])
if args[:3] == ["run", "jobs", "describe"]:
    count = int(state.read_text() if state.exists() else "0") + 1
    state.write_text(str(count))
    print(json.dumps({
        "metadata": {
            "name": os.environ["R6_SCORE_JOB"],
            "resourceVersion": f"mutable-{count}",
            "generation": count,
            "createTimestamp": f"2026-08-26T12:00:0{count}Z",
        },
        "spec": {"template": {"spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "maxRetries": 0,
                "timeoutSeconds": "28800",
                "serviceAccountName": os.environ["R6_SCORE_SERVICE_ACCOUNT"],
                "volumes": [],
                "vpcAccess": {},
                "containers": [{
                    "image": os.environ["R6_SCORE_IMAGE"],
                    "command": ["python"],
                    "args": [],
                    "env": [],
                    "volumeMounts": [],
                    "resources": {"limits": {"cpu": "8", "memory": "32Gi"}},
                }],
            }},
        }}},
    }, sort_keys=True))
elif args[:3] == ["run", "jobs", "update"]:
    if "--clear-network" not in args:
        raise SystemExit("preflight did not clear direct VPC access")
    if "--clear-network-tags" in args:
        raise SystemExit("preflight passed mutually exclusive network clear flags")
else:
    raise SystemExit(f"unexpected offline gcloud call: {args}")
""",
        encoding="utf-8",
    )
    fake_gcloud.chmod(0o755)
    run_dir = tmp_path / "run"
    state = tmp_path / "describe-count.txt"
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_GCLOUD_STATE": str(state),
        "R6_SCORE_RUN_ID": "offline-r6-score-run",
        "R6_SCORE_JOB": "atlas-minimal-c-s2023-w1-v1",
        "R6_SCORE_SERVICE_ACCOUNT": service_account,
        "R6_SCORE_CODE_SHA": "a" * 40,
        "R6_SCORE_IMAGE": (
            "us-central1-docker.pkg.dev/fixture/r6@sha256:" + "b" * 64
        ),
        "R6_SCORE_RUN_DIR": str(run_dir),
        "R6_PANEL_FREEZE_URI": (
            "gs://nfl-predictions-503414-corpus-retrieval/"
            "research/corpus-r6-full-union-freezes/"
            "20260826-foundry-v12-r6-full-union-freeze-v1/panel-freeze.json"
        ),
        "R6_PANEL_FREEZE_GENERATION": "1787759999999999",
        "R6_PANEL_FREEZE_SHA256": "c" * 64,
        "R6_PANEL_FREEZE_BYTES": "10",
        "R6_SNAPSHOT_MODULE_SHA256": "d" * 64,
        "R6_SNAPSHOT_CLI_SHA256": "e" * 64,
        "R6_SNAPSHOT_TEST_SHA256": "f" * 64,
        "R6_SNAPSHOT_CLI_TEST_SHA256": "0" * 64,
    }
    first = subprocess.run(
        ["bash", str(SCRIPT), "preflight"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0, first.stderr
    retained = (run_dir / "job-config.json").read_bytes()
    second = subprocess.run(
        ["bash", str(SCRIPT), "preflight"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert second.returncode == 0, second.stderr
    assert (run_dir / "job-config.json").read_bytes() == retained
    contract = json.loads(retained)
    assert contract["job"] == "atlas-minimal-c-s2023-w1-v1"
    assert contract["service_account"] == service_account
    assert "resourceVersion" not in contract
    assert "generation" not in contract
    assert "createTimestamp" not in contract
    assert state.read_text(encoding="utf-8") == "4"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "R6_SCORE_SERVICE_ACCOUNT",
            "817589974517-compute@other-project.iam.gserviceaccount.com",
            "service account differs",
        ),
        (
            "R6_PANEL_FREEZE_URI",
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "other-family/run-identity/panel-freeze.json",
            "panel URI differs",
        ),
        ("R6_PANEL_FREEZE_GENERATION", "0", "panel generation differs"),
        ("R6_PANEL_FREEZE_SHA256", "C" * 64, "panel SHA differs"),
        ("R6_PANEL_FREEZE_BYTES", "0", "panel bytes differ"),
    ],
)
def test_wrong_service_account_or_panel_identity_fails_before_job_access(
    tmp_path: Path, field: str, value: str, message: str,
) -> None:
    env = {
        **os.environ,
        "R6_SCORE_RUN_ID": "offline-r6-score-run",
        "R6_SCORE_JOB": "atlas-minimal-c-s2023-w1-v1",
        "R6_SCORE_SERVICE_ACCOUNT": (
            "817589974517-compute@developer.gserviceaccount.com"
        ),
        "R6_SCORE_CODE_SHA": "a" * 40,
        "R6_SCORE_IMAGE": "fixture/r6@sha256:" + "b" * 64,
        "R6_SCORE_RUN_DIR": str(tmp_path / "run"),
        "R6_PANEL_FREEZE_URI": (
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "corpus-r6-full-union-freezes/"
            "20260826-foundry-v12-r6-full-union-freeze-v1/panel-freeze.json"
        ),
        "R6_PANEL_FREEZE_GENERATION": "1787759999999999",
        "R6_PANEL_FREEZE_SHA256": "c" * 64,
        "R6_PANEL_FREEZE_BYTES": "10",
        "R6_SNAPSHOT_MODULE_SHA256": "d" * 64,
        "R6_SNAPSHOT_CLI_SHA256": "e" * 64,
        "R6_SNAPSHOT_TEST_SHA256": "f" * 64,
        "R6_SNAPSHOT_CLI_TEST_SHA256": "0" * 64,
    }
    env[field] = value
    result = subprocess.run(
        ["bash", str(SCRIPT), "preflight"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert message in result.stderr


def test_grade_runtime_name_is_not_predicted_by_launcher() -> None:
    source = _source()
    grade = source[source.index("grade_stage()") : source.index("finish()")]
    assert "--execution=" not in grade
    assert "--job=" not in grade
    assert "CLOUD_RUN_EXECUTION" not in source
    assert "CLOUD_RUN_JOB" not in source
    assert "--code-sha=$CODE_SHA" in grade
    assert "--image=$IMAGE" in grade
