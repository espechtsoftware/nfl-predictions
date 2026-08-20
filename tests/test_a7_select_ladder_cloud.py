from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts/cloud_a7_select_ladder.sh"
WATCHER = ROOT / "scripts/watch_a7_select_ladder_queue.sh"
FINISHER = ROOT / "scripts/finish_a7_select_ladder.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_launcher_is_reuse_only_and_has_no_job_creation_or_cancellation() -> None:
    source = _source(LAUNCHER)
    forbidden = (
        "run jobs deploy", "run jobs create", "run jobs delete",
        "run jobs cancel", "scheduler jobs",
    )
    assert all(token not in source for token in forbidden)
    assert 'JOB=atlas-minimal-c-s2023-w1-v1' in source
    assert 'gcloud run jobs update "$JOB"' in source
    assert 'gcloud run jobs execute "$JOB"' in source
    assert "reuse-only-update-existing" in source


def test_all_retained_gcloud_json_is_captured_then_canonicalized() -> None:
    launcher = _source(LAUNCHER)
    watcher = _source(WATCHER)
    for source in (launcher, watcher):
        assert "capture_gcloud_json()" in source
        assert '"$@" > "$raw"' in source
        assert "canonicalize-external-json" in source
        assert 'rm -- "$raw"' in source
        assert "--format=json >" not in source
    assert launcher.count("capture_gcloud_json ") >= 10
    assert watcher.count("capture_gcloud_json ") >= 1


def test_job_updates_explicitly_clear_mutable_mount_and_workdir_state() -> None:
    source = _source(LAUNCHER)
    assert source.count("--clear-volumes --clear-volume-mounts") == 2
    assert source.count('--workdir="" --startup-probe=""') == 2
    assert source.count("--clear-secrets") == 2
    assert source.count('--set-env-vars "') == 2


def test_build_command_is_exact_direct_git_and_print_only() -> None:
    source = _source(LAUNCHER)
    branch = source[source.index("  build-command)"):source.index(
        "  preflight-prepare)"
    )]
    assert "gcloud builds submit %q" in branch
    assert "https://github.com/espechtsoftware/nfl-predictions.git" in branch
    assert "--git-source-revision=%q" in branch
    assert '"$ROOT/cloudbuild.yaml"' in branch
    assert "gcloud builds submit \"" not in branch


def test_launcher_freezes_exact_three_field_manifest_interface_in_job() -> None:
    source = _source(LAUNCHER)
    for name in (
        "--freeze-manifest-uri",
        "--freeze-manifest-generation",
        "--freeze-manifest-sha256",
        "A7_FREEZE_MANIFEST_URI",
        "A7_FREEZE_MANIFEST_GENERATION",
        "A7_FREEZE_MANIFEST_SHA256",
    ):
        assert name in source
    args = (
        "scripts/run_a7_select_ladder.py,--output-uri,$RESULT_URI,"
        "--freeze-manifest-uri,$FREEZE_URI,"
        "--freeze-manifest-generation,$FREEZE_GENERATION,"
        "--freeze-manifest-sha256,$FREEZE_SHA256"
    )
    assert args in source


def test_transport_has_conscious_self_hash_repair_seams_and_receipts() -> None:
    launcher = _source(LAUNCHER)
    watcher = _source(WATCHER)
    for name in (
        "A7_FINISHER_REPAIR_SHA256",
        "A7_LAUNCHER_REPAIR_SHA256",
        "A7_WATCHER_REPAIR_SHA256",
    ):
        assert name in launcher
        assert name in watcher
    assert '"transport_repair_sha256"' in launcher
    assert '[[ "$repair_value" =~ ^[0-9a-f]{64}$ ]]' in launcher


def test_launcher_has_explicit_serial_preflight_freeze_and_historical_modes() -> None:
    source = _source(LAUNCHER)
    for mode in (
        "preflight-prepare)", "smoke)", "support)", "freeze)",
        "prepare)", "launch)",
    ):
        assert mode in source
    assert source.index("preflight-prepare)") < source.index("smoke)")
    assert source.index("smoke)") < source.index("support)")
    assert source.index("support)") < source.index("freeze)")
    assert source.index("\n  freeze)") < source.index("\n  prepare)")


def test_job_claim_and_prefix_inventory_are_create_once_and_cumulative() -> None:
    launcher = _source(LAUNCHER)
    finisher = _source(FINISHER)
    assert "claim-job" in launcher
    assert launcher.index("validate_prefix_inventory empty") < launcher.index(
        "claim-job"
    ) < launcher.index("validate_prefix_inventory claimed")
    for phase in (
        '"empty": set()', '"claimed": {claim}', '"smoke-complete"',
        '"support-complete"', '"frozen"',
    ):
        assert phase in launcher
    assert "if_generation_match=0" in finisher
    assert "JOB_CLAIM_URI" in finisher


def test_generation_and_full_spec_chain_precede_every_job_execution() -> None:
    source = _source(LAUNCHER)
    assert 'validate_job_chain_before "$short_mode"' in source
    assert 'validate_job_chain_before historical' in source
    assert "prior_job_generation" in source
    assert "prior_job_spec_sha256" in source
    assert "_validate_updated_job_spec" in source
    preflight_execute = source.index(
        'EXECUTION=$(gcloud run jobs execute "$JOB"',
    )
    assert source.index("_validate_updated_job_spec") < preflight_execute
    historical_launch = source.index("  launch)")
    historical_execute = source.index(
        'gcloud run jobs execute "$JOB"', historical_launch,
    )
    assert source.index("_validate_updated_job_spec", historical_launch) < (
        historical_execute
    )


def test_absence_probes_fail_closed_except_on_definitive_not_found() -> None:
    source = _source(LAUNCHER)
    assert "except NotFound:" in source
    assert "gcloud storage ls" not in source
    assert source.count('strict_object_absent "$RESULT_URI"') >= 3
    launch = source.index("  launch)")
    execute = source.index('gcloud run jobs execute "$JOB"', launch)
    assert source.rindex('strict_object_absent "$RESULT_URI"', launch, execute) < execute
    assert "_verified_lease_blob" in source[launch:execute]


def test_build_gate_requires_resolved_repository_source_not_substitution_only() -> None:
    source = _source(FINISHER)
    assert '"resolvedGitSource"' in source
    assert "https://github.com/espechtsoftware/nfl-predictions.git" in source
    assert "local/storage uploads (including dirty worktrees) fail closed" in source
    assert "_expected_cloud_build_steps" in source
    assert '"cloudbuild_config": "cloudbuild.yaml"' in source


def test_launch_requires_prepared_receipt_live_lease_and_create_only_result() -> None:
    source = _source(LAUNCHER)
    launch = source.index("  launch)")
    execute = source.index('gcloud run jobs execute "$JOB"', launch)
    assert source.index("_validate_hash_ledger", launch) < execute
    assert source.index("_verified_lease_blob", launch) < execute
    assert source.index('strict_object_absent "$RESULT_URI"', launch) < execute
    assert source.index("launch-intent.json", launch) < execute
    assert source.index("executions.txt", execute) > execute


def test_historical_build_id_is_cross_bound_before_lease_and_execute() -> None:
    source = _source(LAUNCHER)
    prepare = source.index("\n  prepare)")
    launch = source.index("\n  launch)")
    branch = source[prepare:launch]
    assert 'support_terminal.get("build_id") != build' in branch
    assert 'freeze["preflights"]["support"]["terminal"]["sha256"]' in branch


def test_queue_orders_release_preflights_freeze_prepare_lease_and_finish() -> None:
    source = _source(WATCHER)
    wait = source.index("A7_WAITS_FOR_A3_LOGICAL_RELEASE")
    preflight = source.index('bash "$LAUNCHER" preflight-prepare')
    smoke = source.index('bash "$LAUNCHER" smoke')
    support = source.index('bash "$LAUNCHER" support')
    freeze = source.index('bash "$LAUNCHER" freeze')
    prepare = source.index('bash "$LAUNCHER" prepare')
    acquire = source.index('"$LEASE_TOOL" acquire')
    launch = source.index('bash "$LAUNCHER" launch')
    describe = source.index("jobs executions describe")
    finish = source.index('"$FINISHER" finish')
    close = source.index("LEASE_ACTION=")
    assert wait < preflight < smoke < support < freeze < prepare < acquire
    assert acquire < launch < describe < finish < close


def test_queue_never_reads_result_body_and_holds_ambiguous_lease() -> None:
    source = _source(WATCHER)
    assert "result.json" in source  # exact ledger URI only
    assert "storage cp" not in source
    assert "download_as_bytes" not in source
    assert "jobs cancel" not in source
    assert "lease held for operator review" in source
    assert "historical_outcome_lease_release_licensed" in source


def test_tail_artifact_completion_uses_exact_no_outcome_lease_abandon_branch() -> None:
    source = _source(WATCHER)
    assert '"$USES_REALIZED" = false' in source
    assert '"$DISPOSITION" = tail-artifact-risk-phase-s' in source
    assert "a7-tail-artifact-no-outcome" in source
    assert "abandoned-after-proven-no-outcome-tail-closure" in source
    assert "released-after-realized-outcome" in source
    assert "TAIL_STAGED_RECEIPT" in source
    assert '"$FINISHER" validate-closed' in source
    assert 'cmp -s "$LEASE" "$LEASE_RECEIPT_FOR_HASH"' in source


def test_preflight_terminals_bind_contract_and_inventory_hashes() -> None:
    source = _source(FINISHER)
    for token in (
        "contract_sha256", "job_spec_sha256", "prior_job_generation",
        "prior_job_spec_sha256", "prefix_inventory_before_terminal_sha256",
        "expected_inventory_after_terminal_uris_sha256",
        "prefix_inventory_sha256",
    ):
        assert token in source
    assert "terminal inventory is not bound to known objects" in source
    assert '"lease_tool": "scripts/historical_outcome_lease.py"' in source


def test_terminal_failure_can_only_abandon_its_own_receipted_lease() -> None:
    source = _source(WATCHER)
    false_branch = source[source.index("    False)"):source.index(
        '    Unknown|"")'
    )]
    assert '"$LEASE_TOOL" abandon' in false_branch
    assert '--receipt "$LEASE"' in false_branch
    assert "a7-terminal-failed" in false_branch
    assert "jobs execute" not in false_branch


def test_failure_closure_is_validated_before_any_reacquire_or_relaunch() -> None:
    source = _source(WATCHER)
    closure = source.index("validate-failure-closure")
    acquire = source.index('"$LEASE_TOOL" acquire')
    launch = source.index('bash "$LAUNCHER" launch')
    assert closure < acquire < launch
    assert "historical_retry_licensed" in source
    assert "closed-terminal-failed-no-retry" in source
    assert "closed-prelaunch-no-retry" in source


def test_realized_release_has_durable_resume_before_any_reacquisition() -> None:
    source = _source(WATCHER)
    resume = source.index("A7_SELECT_LADDER_RESUMED_REALIZED_LEASE_CLOSE")
    acquire = source.index('"$LEASE_TOOL" acquire')
    assert resume < acquire
    assert source.count("close-realized-lease") == 2
    assert '"$LEASE_TOOL" release' not in source
    finisher = _source(FINISHER)
    assert "a7-realized-lease-release-intent-v1" in finisher
    assert "delete-only-exact-generation-after-create-only-intent" in finisher
    assert "if_generation_match=generation" in finisher
