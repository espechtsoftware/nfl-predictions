"""Contract for the read-only settlement of the exact CFB repair smoke."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTLEMENT = ROOT / "scripts/settle_cfb_collection_repair_smoke.sh"


def _source() -> str:
    return SETTLEMENT.read_text(encoding="utf-8")


def test_settlement_is_exact_bound_and_valid_bash() -> None:
    subprocess.run(["bash", "-n", str(SETTLEMENT)], check=True)
    source = _source()

    assert '[[ $# -eq 1 && "$1" == "--settle" ]]' in source
    assert 'EXECUTION="ingest-cfb-rwcqr"' in source
    assert 'EXECUTION_UID="e4c4e5cf-1862-46e2-be94-1751a66dc683"' in source
    assert 'JOB_GENERATION=11' in source
    assert 'ARTIFACT_DIR="$SOURCE_ROOT/.tmp/cfb-collection-release.WlLILm"' in source
    assert "sha256:78c905ff383cd6ddaded89d515d14d85617d7138398ec161f91e079655f02f80" in source


def test_settlement_has_no_cloud_or_bq_mutation_surface() -> None:
    source = _source()

    forbidden_cloud = (
        r"^gcloud run jobs (execute|update|deploy)",
        r"^gcloud run jobs executions (cancel|delete)",
        r"^gcloud scheduler jobs (update|resume|pause|delete|create)",
        r"^gcloud builds (submit|cancel)",
    )
    for pattern in forbidden_cloud:
        assert not re.search(pattern, source, flags=re.MULTILINE)

    assert source.count("bq query ") == 2
    for statement in ("INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "DROP"):
        assert not re.search(rf"['\"]{statement}\b", source)
    assert "provider_mutation_performed:false" in source
    assert "bq_mutation_performed:false" in source
    assert "execution_launched:false" in source


def test_settlement_pins_and_reopens_original_evidence() -> None:
    source = _source()

    expected_hashes = (
        "c867b08af73b56dbf3092473dc92cfca69aa2a4e06552820e46ba42609e46d7e",
        "77150eff1c8a76683e39feeb27e9661e719c57245e24e7ede10c82027134e589",
        "48645a5d5cfccb96d8f64f794bc1bcd6430e46dfbf291dd6fba8045d3f63419f",
        "b8e14fa56869f1351ec3fa37a34e3493992f79c5043efc933efd31784b0e171c",
        "2bc3b79dcc3e263534f52ad31e977d47b3e52b884c0a5d5d40670c3261ee1a33",
    )
    assert all(digest in source for digest in expected_hashes)
    assert 'gcloud run jobs executions describe "$EXECUTION"' in source
    assert 'gcloud run jobs executions list --job="$JOB"' in source
    assert "gcloud logging read" in source
    assert 'cmp -s "$ARTIFACT_DIR/execution-terminal.json"' in source
    assert 'cmp -s "$ARTIFACT_DIR/executions-terminal.json"' in source
    assert 'cmp -s "$ARTIFACT_DIR/execution-logs.json"' in source
    assert 'cmp -s "$ARTIFACT_DIR/bq-after.json"' in source


def test_terminal_identity_requires_success_zero_retries_and_generation_11() -> None:
    source = _source()

    assert '.metadata.labels."run.googleapis.com/jobGeneration" == "11"' in source
    assert '.status.succeededCount == 1' in source
    assert '(.status.failedCount // 0) == 0' in source
    assert '(.status.cancelledCount // 0) == 0' in source
    assert '(.status.retriedCount // 0) == 0' in source
    assert '.status.executionCount == 130' in source
    assert '.status.latestCreatedExecution.name == $execution' in source
    assert '.status.latestCreatedExecution.completionStatus == "EXECUTION_SUCCEEDED"' in source


def test_position_amendment_is_only_k_on_showdown() -> None:
    source = _source()

    assert 'position IN ("QB", "RB", "WR")' in source
    assert '(slate_type = "showdown" AND position = "K")' in source
    assert 'COUNTIF(slate_type = "showdown" AND position = "K")' in source
    assert 'COUNTIF(slate_type != "showdown" AND position = "K")' in source
    assert 'showdown_k_rows:"29"' in source
    assert 'non_showdown_k_rows:"0"' in source
    assert 'original_invalid_rows:29' in source
    assert 'corrected_invalid_rows:0' in source


def test_counts_logs_and_time_boundary_are_exact() -> None:
    source = _source()

    assert 'SMOKE_STARTED_AT="2026-09-02T04:25:01Z"' in source
    assert 'COMPLETION_TIME="2026-09-02T04:28:59.074510Z"' in source
    assert 'row_count:"2134"' in source
    assert 'row_count:"2076"' in source
    assert 'Loading 2134 rows into nfl-predictions-503414.nfl_raw.cfb_dk_salaries' in source
    assert 'Loading 2076 rows into nfl-predictions-503414.nfl_raw.dk_contest_fills' in source
    assert 'Polled 2076 CFB contests across 11 draft groups' in source
    assert "length == 11 and add == 2134" in source


def test_receipt_is_local_create_once_and_discloses_settlement_only() -> None:
    source = _source()

    assert '[[ ! -e "$RECEIPT" && ! -L "$RECEIPT" ]]' in source
    assert 'ln "$RECEIPT_TEMP" "$RECEIPT"' in source
    assert 'schema "cfb-collection-repair-smoke/v1"' in source
    assert "settlement_only:true" in source
    assert 'acceptance:"salary-rows-and-max-advanced"' in source
    assert 'reason:"original validator excluded 29 valid showdown kicker rows"' in source
    assert '"SCHEDULERS=PAUSED"' in source
