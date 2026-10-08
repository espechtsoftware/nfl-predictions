"""scripts/field_sharpness.py (study row 68): the frozen fit, the source rule and the printed line (offline)."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("field_sharpness", Path(__file__).resolve().parents[1] / "scripts" / "field_sharpness.py")
FS = importlib.util.module_from_spec(spec); spec.loader.exec_module(FS)


def test_frozen_fit_reproduces_the_2026_weeks_already_seen():
    # 2026 W1-4 (winning score, slate top-10) as computed on 2026-10-08; residuals +9.5 / +5.6 / +6.3 / -10.6
    seen = [(273.98, 36.216, 9.5035), (232.38, 30.302, 5.5675), (239.80, 31.354, 6.2877), (234.20, 33.130, -10.6229)]
    for win, top10, r in seen:
        assert FS.residual(win, top10) == pytest.approx(r, abs=0.01)
    assert FS.expected(30.0) == pytest.approx(33.831007 + 6.368607 * 30.0)


def test_source_rule():
    assert FS.choose_source("auto", 600) == "actuals"
    assert FS.choose_source("auto", 9) == "milly"
    assert FS.choose_source("milly", 600) == "milly"
    with pytest.raises(ValueError):
        FS.choose_source("vegas", 600)


def test_top10_needs_ten_players():
    assert FS.top10_mean(list(range(1, 21))) == pytest.approx(sum(range(11, 21)) / 10)
    with pytest.raises(ValueError, match="needs 10"):
        FS.top10_mean([30.0] * 9)


def test_line_names_the_source_field_size_and_provenance():
    line = FS.season_line(2026, 5, 250.0, 161764, 32.0, "milly", "123", [9.5, 5.6, 6.3, -10.6, 2.4])
    assert "(milly)" in line and "161,764 entries" in line and "f1689126" in line
    assert "residual +12.4" in line                       # 250 - (33.831007 + 6.368607 x 32) = 12.37
    assert "2026 to date +2.6 over 5 week(s)" in line
    assert "2023 +1.1 / 2024 -4.1 / 2025 +2.6" in line
