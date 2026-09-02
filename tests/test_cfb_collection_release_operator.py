"""Fail-closed contract for the scoped CFB collection release operator."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATOR = ROOT / "scripts/deploy_cfb_collection_repair_smoke.sh"

BUILD_ID = "e3ebcc13-ba90-409b-b7d1-ce835adf23bf"
SOURCE_SHA = "31fa0d82c81b140f7853fa7de0bbd6f880890957"
IMAGE_DIGEST = (
    "sha256:78c905ff383cd6ddaded89d515d14d85617d7138398ec161f91e079655f02f80"
)
OLD_IMAGE_DIGEST = (
    "sha256:6c556b9e7ff4685e89ec2f4efcff542aa8c5f1f2b62f181999cb81cbb9beb893"
)
JOB_UID = "2a1902a6-3bff-4511-9647-3340b1815ec9"


def _source() -> str:
    return OPERATOR.read_text(encoding="utf-8")


def test_operator_is_valid_bash_and_has_only_two_public_modes() -> None:
    subprocess.run(["bash", "-n", str(OPERATOR)], check=True)
    source = _source()

    assert '[[ "$MODE" == "--preflight" || "$MODE" == "--execute" ]]' in source
    assert "--dry-run" not in source
    assert "--force" not in source


def test_operator_pins_exact_build_source_image_and_live_prestate() -> None:
    source = _source()

    assert f'BUILD_ID="{BUILD_ID}"' in source
    assert f'SOURCE_SHA="{SOURCE_SHA}"' in source
    assert IMAGE_DIGEST in source
    assert OLD_IMAGE_DIGEST in source
    assert f'JOB_UID="{JOB_UID}"' in source
    assert 'PRE_GENERATION=10' in source
    assert '.status == "SUCCESS"' in source
    assert '.substitutions._CODE_SHA == $source' in source
    assert '.results.images[0].digest == $digest' in source
    assert 'gcloud artifacts docker images describe "$IMAGE_TAG"' in source
    assert '.image_summary.fully_qualified_digest == $image' in source


def test_mutations_are_guarded_by_the_shared_ingest_cfb_lane() -> None:
    source = _source()
    registry = source.index('exec "$SOURCE_ROOT/scripts/launcher_registry.sh" run')
    preflight = source.index("capture_and_verify_preflight")
    update = source.index('gcloud run jobs update "$JOB"')

    assert registry < update
    assert preflight < update
    assert '--lane "$JOB"' in source
    assert '--owner production' in source
    assert '--target-prefixes "$RUN_PREFIX"' in source
    assert 'NFL_LAUNCHER_REGISTRY_RECEIPT_SHA256' in source
    assert '.target_run_id_prefixes == [$prefix]' in source


def test_job_and_scheduler_mutations_have_exactly_the_allowed_surface() -> None:
    source = _source()

    assert (
        'gcloud run jobs update "$JOB" \\\n'
        '  --project="$PROJECT" --region="$REGION" \\\n'
        '  --image="$IMAGE" --max-retries=0 --quiet'
    ) in source
    assert (
        'gcloud scheduler jobs update http "$SATURDAY_SCHEDULER" \\\n'
        '  --project="$PROJECT" --location="$REGION" \\\n'
        '  --schedule="$NEW_SATURDAY_SCHEDULE" --quiet'
    ) in source
    assert 'NEW_SATURDAY_SCHEDULE="0 8,9,11,12,13 * * 6"' in source
    assert 'DAILY_SCHEDULE="0 10,14,18 * * *"' in source
    assert "gcloud scheduler jobs resume" not in source
    assert "gcloud scheduler jobs pause" not in source
    assert "deploy/deploy_jobs.sh" not in source
    assert "gcloud run jobs deploy" not in source
    assert "--set-env-vars" not in source
    assert "--service-account" not in source
    assert "rollback" not in source.lower()


def test_post_update_job_comparison_uses_null_input_mode() -> None:
    source = _source()
    body = source[
        source.index("verify_release_job() {"):
        source.index('gcloud run jobs update "$JOB"')
    ]

    # This comparison is built entirely from --slurpfile values.  Without
    # -n, a registry-launched noninteractive child reaches EOF and aborts
    # after the singular job update but before the smoke.
    assert "jq -e -n \\\n" in body


def test_scheduler_contract_stays_paused_and_only_saturday_cron_can_change() -> None:
    source = _source()

    assert source.count('.state == "PAUSED"') >= 1
    assert 'die "the daily CFB scheduler changed"' in source
    assert 'die "the Saturday scheduler changed outside its schedule"' in source
    assert '"SCHEDULERS=PAUSED"' in source
    assert "scheduler-daily-terminal.json" in source
    assert "scheduler-saturday-terminal.json" in source


def test_exactly_one_execute_call_is_reconciled_without_retry() -> None:
    source = _source()
    execute_calls = re.findall(r"^gcloud run jobs execute ", source, re.MULTILINE)

    assert len(execute_calls) == 1
    assert '--async --format=json' in source
    assert "execute.return-code" in source
    assert "new-executions.json" in source
    assert 'length' in source
    assert "more than one provider execution appeared" in source
    assert "terminal provider execution inventory differs" in source
    assert '.status.succeededCount == 1' in source
    assert '(.status.retriedCount // 0) == 0' in source
    assert 'verify_release_job "$STATE_DIR/job-before-launch.json"' in source
    assert "gcloud run jobs executions cancel" not in source


def test_bq_settlement_has_exact_zero_baseline_and_noop_escape_hatch() -> None:
    source = _source()

    assert "nfl_raw.cfb_dk_salaries" in source
    assert "nfl_raw.dk_contest_fills" in source
    assert 'WHERE sport = "CFB"' in source
    assert 'all(.[]; .row_count == "0" and .max_pulled_at == null)' in source
    assert 'contains("No upcoming CFB draft groups")' in source
    assert '(.textPayload | type) == "string"' in source
    assert '(.jsonPayload.message | type) == "string"' in source
    assert 'ACCEPTANCE="salary-rows-and-max-advanced"' in source
    assert 'ACCEPTANCE="no-upcoming-draft-groups"' in source
    assert "successful smoke neither advanced CFB data nor logged the exact no-op" in source
    assert 'labels.\\"run.googleapis.com/execution_name\\"' in source


def test_advanced_acceptance_requires_valid_new_salary_rows() -> None:
    source = _source()

    assert (
        '$new.cfb_dk_salaries.row_count > $old.cfb_dk_salaries.row_count'
        in source
    )
    assert '$new.cfb_dk_salaries.max_pulled_at >' in source
    assert 'season IS NULL OR season != 2026' in source
    assert 'slate_type NOT IN ("classic", "showdown")' in source
    assert 'position IN ("QB", "RB", "WR")' in source
    assert '(slate_type = "showdown" AND position = "K")' in source
    assert 'salary IS NULL OR salary <= 0' in source
    assert 'dk_player_id IS NULL OR dk_player_id <= 0' in source
    assert 'dk_draftable_id IS NULL OR dk_draftable_id <= 0' in source
    assert 'sport IS NULL OR sport != "CFB"' in source
    assert 'start_time IS NULL' in source
    assert 'new CFB salary/contest rows failed the settlement contract' in source


def test_preflight_exits_before_any_provider_mutation() -> None:
    source = _source()
    preflight_exit = source.index('if [[ "$MODE" == "--preflight" ]]')
    job_update = source.index('gcloud run jobs update "$JOB"')
    scheduler_update = source.index(
        'gcloud scheduler jobs update http "$SATURDAY_SCHEDULER"'
    )
    execute = source.index('gcloud run jobs execute "$JOB"')

    assert preflight_exit < job_update < scheduler_update < execute
