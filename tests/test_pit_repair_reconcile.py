from pathlib import Path


def test_pit_repair_reconciliation_is_outcome_free_and_fail_closed():
    text = (
        Path(__file__).parents[1] / "scripts" / "pit_repair_reconcile.py"
    ).read_text(encoding="utf-8")
    assert "actual" not in text.lower()
    assert "y_dk_points" not in text
    assert '"passes": all(checks.values())' in text
    assert "USAGE_ALLOWED_CHANGES" in text
    assert "TRAINING_ALLOWED_CHANGES" in text
    assert "57_550" in text
    assert "8_312" in text
