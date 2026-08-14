import importlib.util
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location(
    "_sis_asoe_phase_s_retry_ledger",
    Path(__file__).parents[1]
    / "scripts"
    / "update_sis_asoe_phase_s_retry_ledger.py",
)
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)


def _ledgers():
    rows = []
    for arm in ("control", "treatment"):
        for replicate in range(5):
            for season in (2023, 2024, 2025):
                family = f"sisasoe{arm[0]}{replicate}"
                rows.append(
                    f"{arm} {replicate} {season} "
                    f"20260813-sis-asoe-{arm}-r{replicate}-v1 "
                    f"replay-{family}-{season} old-{family}-{season}"
                )
    failed = "old-sisasoet2-2024"
    pending = f"treatment 2 2024 {failed} zero_output\n"
    return "\n".join(rows) + "\n", pending, ""


def test_retry_substitution_updates_all_three_ledgers():
    executions, pending, retries = _ledgers()
    updated, remaining, provenance = ledger.replacement_contents(
        executions, pending, retries, arm="treatment", replicate=2,
        season=2024, panel="20260813-sis-asoe-treatment-r2-v1",
        job="replay-sisasoet2-2024",
        failed_execution="old-sisasoet2-2024",
        retry_execution="replay-sisasoet2-2024-new12", reason="zero_output",
    )
    assert "replay-sisasoet2-2024-new12" in updated
    assert "old-sisasoet2-2024" not in updated
    assert remaining == ""
    assert provenance == (
        "treatment 2 2024 old-sisasoet2-2024 "
        "replay-sisasoet2-2024-new12 zero_output\n"
    )


def test_retry_substitution_rejects_the_wrong_failed_execution():
    executions, pending, retries = _ledgers()
    with pytest.raises(ValueError, match="classified failed execution"):
        ledger.replacement_contents(
            executions, pending, retries, arm="treatment", replicate=2,
            season=2024, panel="20260813-sis-asoe-treatment-r2-v1",
            job="replay-sisasoet2-2024", failed_execution="wrong-execution",
            retry_execution="new-execution", reason="zero_output",
        )


def test_retry_substitution_rejects_a_duplicate_execution_id():
    executions, pending, retries = _ledgers()
    with pytest.raises(ValueError, match="already occurs"):
        ledger.replacement_contents(
            executions, pending, retries, arm="treatment", replicate=2,
            season=2024, panel="20260813-sis-asoe-treatment-r2-v1",
            job="replay-sisasoet2-2024",
            failed_execution="old-sisasoet2-2024",
            retry_execution="old-sisasoec0-2023", reason="zero_output",
        )
