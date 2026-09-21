"""Tests for the weekly receipt freshness sweep.

The sweep exists because the 2026-09-21 staleness defect left exactly one trace:
a timestamp in a receipt. The tool that read Week-1 data for a Week-2 book did
not fail, and its coverage count looked healthy. Checking that trace mechanically
every week is cheaper than hoping someone reads a receipt.

Each test breaks the property it claims.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "receipt_freshness_sweep.py"
_spec = importlib.util.spec_from_file_location("receipt_freshness_sweep", _SRC)
rfs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rfs)

WINDOW = date(2026, 9, 15)


def _week_dir(tmp_path, **artifacts):
    for name, doc in artifacts.items():
        d = tmp_path / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "receipt.json").write_text(json.dumps(doc))
    return tmp_path


class TestItCatchesTheRealDefect:
    def test_the_week2_composite_shape_is_flagged(self, tmp_path):
        """The actual receipt that went undetected for a week."""
        root = _week_dir(tmp_path, composite={
            "version": "player-score-v1",
            "projection_generated_at": "2026-09-13 16:03:49.796412+00:00",
            "prop_fetch_days": ["2026-09-12", "2026-09-13"],
            "players": 149, "coverage": {"prod_proj": 134}})
        findings, scanned = rfs.sweep(root, WINDOW)
        assert scanned == 1
        fields = {f["field"] for f in findings}
        assert "projection_generated_at" in fields
        assert {"prop_fetch_days[0]", "prop_fetch_days[1]"} <= fields

    def test_a_current_week_receipt_is_clean(self, tmp_path):
        root = _week_dir(tmp_path, composite={
            "projection_generated_at": "2026-09-20 16:02:22+00:00",
            "prop_fetch_days": ["2026-09-19", "2026-09-20"]})
        findings, _ = rfs.sweep(root, WINDOW)
        assert findings == []

    def test_one_stale_field_among_fresh_ones_is_still_caught(self, tmp_path):
        """Partial staleness is the dangerous case: most of it looks right."""
        root = _week_dir(tmp_path, composite={
            "projection_generated_at": "2026-09-20 16:02:22+00:00",
            "prop_fetch_days": ["2026-09-12", "2026-09-20"]})
        findings, _ = rfs.sweep(root, WINDOW)
        assert [f["field"] for f in findings] == ["prop_fetch_days[0]"]

    def test_the_boundary_date_is_inside_the_window(self, tmp_path):
        root = _week_dir(tmp_path, a={"pulled_at": "2026-09-15"})
        assert rfs.sweep(root, WINDOW)[0] == []

    def test_the_day_before_the_window_is_flagged(self, tmp_path):
        root = _week_dir(tmp_path, a={"pulled_at": "2026-09-14"})
        assert len(rfs.sweep(root, WINDOW)[0]) == 1


class TestBackwardLookingFieldsAreNotNoise:
    """A sweep that cries wolf gets switched off, so benign fields must pass."""

    @pytest.mark.parametrize("field", [
        "dk_ppg_source_date", "prior_season_window", "targets_l4_from",
        "receiving_l6_start", "backup_history_since", "career_since"])
    def test_legitimately_old_fields_are_skipped(self, tmp_path, field):
        root = _week_dir(tmp_path, a={field: "2025-09-01"})
        assert rfs.sweep(root, WINDOW)[0] == []

    def test_an_extra_benign_name_can_be_supplied(self, tmp_path):
        root = _week_dir(tmp_path, a={"baseline_panel_date": "2026-08-07"})
        assert len(rfs.sweep(root, WINDOW)[0]) == 1
        assert rfs.sweep(root, WINDOW, rfs.DEFAULT_BENIGN + ("baseline_panel",))[0] == []

    def test_benign_matching_is_case_insensitive(self, tmp_path):
        root = _week_dir(tmp_path, a={"DK_PPG_AS_OF": "2025-09-01"})
        assert rfs.sweep(root, WINDOW)[0] == []


class TestItDoesNotBreakOnRealDirectories:
    def test_unparseable_json_is_skipped_not_fatal(self, tmp_path):
        (tmp_path / "bad").mkdir()
        (tmp_path / "bad" / "receipt.json").write_text("{not json")
        _week_dir(tmp_path, good={"pulled_at": "2026-09-14"})
        findings, scanned = rfs.sweep(tmp_path, WINDOW)
        assert scanned == 1 and len(findings) == 1

    def test_a_directory_with_no_receipts_is_clean(self, tmp_path):
        findings, scanned = rfs.sweep(tmp_path, WINDOW)
        assert findings == [] and scanned == 0

    def test_non_date_strings_are_ignored(self, tmp_path):
        root = _week_dir(tmp_path, a={"note": "run 2026 of the pipeline", "sha": "abc123"})
        assert rfs.sweep(root, WINDOW)[0] == []

    def test_nested_documents_are_searched(self, tmp_path):
        root = _week_dir(tmp_path, a={"inputs": {"market": {"pulled": "2026-09-12"}}})
        findings, _ = rfs.sweep(root, WINDOW)
        assert findings[0]["field"] == "inputs.market.pulled"


class TestExitCode:
    def test_it_exits_one_when_something_is_stale(self, tmp_path, capsys):
        _week_dir(tmp_path, a={"pulled_at": "2026-09-12"})
        assert rfs.main(["--dir", str(tmp_path), "--after", "2026-09-15"]) == 1
        assert "STALE" in capsys.readouterr().out

    def test_it_exits_zero_when_everything_is_current(self, tmp_path, capsys):
        _week_dir(tmp_path, a={"pulled_at": "2026-09-20"})
        assert rfs.main(["--dir", str(tmp_path), "--after", "2026-09-15"]) == 0
        assert "OK" in capsys.readouterr().out

    def test_a_bad_after_date_is_rejected(self, tmp_path):
        with pytest.raises(SystemExit):
            rfs.main(["--dir", str(tmp_path), "--after", "week-3"])

    def test_a_missing_directory_is_rejected(self, tmp_path):
        with pytest.raises(SystemExit):
            rfs.main(["--dir", str(tmp_path / "nope"), "--after", "2026-09-15"])


class TestItIsWiredIntoTheSundayChain:
    """A check nobody runs is not a check."""

    def test_the_after_build_chain_runs_the_sweep(self):
        chain = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_after_build.sh").read_text()
        assert "receipt_freshness_sweep.py" in chain
        assert "--after \"$WINDOW_START\"" in chain

    def test_the_window_is_derived_from_the_slate_not_hardcoded(self):
        """A hardcoded window is the same defect wearing a different hat."""
        chain = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_after_build.sh").read_text()
        line = next(l for l in chain.splitlines() if "WINDOW_START=" in l and "date -u" in l)
        assert "$SUNDAY" in line, line

    def test_a_hit_reaches_the_page_the_operator_reads(self):
        chain = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_after_build.sh").read_text()
        # The name appears twice (the -f guard and the call); take everything
        # after the last occurrence, which is the reporting block.
        block = chain.split("receipt_freshness_sweep.py")[-1]
        assert "STALE INPUTS DETECTED" in block
        assert "TODAY-30-LATEST.md" in block

    def test_the_clean_case_also_reaches_the_page(self):
        """Silence must not be the only signal for OK; say so explicitly."""
        chain = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_after_build.sh").read_text()
        assert "INPUT FRESHNESS: OK" in chain
