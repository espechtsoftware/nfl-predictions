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
        # the CLI sweeps declared chain inputs only (O-24), so the artifact carries a declared name
        _week_dir(tmp_path, **{"composite-w2": {"pulled_at": "2026-09-12"}})
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


def test_model_artifacts_are_not_swept_as_inputs(tmp_path):
    """A fitted class model carries its training weeks' locks and a Monday fitted_utc: legitimately before the window."""
    import json
    from datetime import date
    (tmp_path / "class_model.json").write_text(json.dumps({"fitted_utc": "2026-09-28T12:00:00Z", "weeks": [{"lock": "2026-09-13T17:00:00Z"}]}))
    (tmp_path / "other.json").write_text(json.dumps({"salary_pull": "2026-09-13T12:00:00Z"}))
    findings, scanned = rfs.sweep(tmp_path, date(2026, 9, 29))
    assert scanned == 1 and [f["file"] for f in findings] == [str(tmp_path / "other.json")]


class TestOnlyDeclaredInputsAreSwept:
    """O-24 (2026-10-04): a comparison-only LineStar capture saved under the week directory carried 2025 period
    history and put "STALE INPUTS DETECTED -- DO NOT UPLOAD" on the live sheet at 11:02. The CLI now sweeps the
    chain's declared inputs only; a stray file is counted, never flagged, while a stale declared input still is."""

    STRAY = {"Periods": [{"StartDate": "2025-12-18", "EndDate": "2025-12-22"}]}

    def _stray(self, root):
        d = root / "linestar-prelock-top5"
        d.mkdir()
        (d / "capture-0847.json").write_text(json.dumps(self.STRAY))
        (root / "contest-details-20260930.json").write_text(json.dumps({"start": "2025-09-07"}))

    def test_a_stray_file_with_old_dates_does_not_trip_it(self, tmp_path, capsys):
        _week_dir(tmp_path, **{"composite-20261004t1550z-d800-x": {"projection_generated_at": "2026-10-04T15:40:30Z"}})
        self._stray(tmp_path)
        assert rfs.main(["--dir", str(tmp_path), "--after", "2026-09-29"]) == 0
        out = capsys.readouterr().out
        assert "STALE" not in out and "OK" in out
        assert "not scanned: 2 undeclared JSON file(s)" in out and "linestar-prelock-top5" in out

    def test_a_stale_declared_input_still_trips_it_beside_a_stray_file(self, tmp_path, capsys):
        _week_dir(tmp_path, **{"composite-20261004t1550z-d800-x": {"prop_fetch_days": ["2026-09-27", "2026-10-04"]}})
        self._stray(tmp_path)
        assert rfs.main(["--dir", str(tmp_path), "--after", "2026-09-29"]) == 1
        stale = [l for l in capsys.readouterr().out.splitlines() if l.startswith("  STALE")]
        assert len(stale) == 1 and "composite-20261004t1550z-d800-x" in stale[0] and "prop_fetch_days[0]" in stale[0]

    @pytest.mark.parametrize("rel", [
        "build-inputs-20261004T155013Z-L981pr.json", "lever-audit-20261004t1550z-d800-x-union.json",
        "ordering_shadows-20261004t1550z-d800-x-k30.json", "upload-20261004t1550z-d800-x-k80-milly-1-ranks-1-1.receipt.json",
        "ownership_fp-20261004t1550z-d800-x.csv.receipt.json", "contests.json",
        "vetted-x/vetting.json", "composite-x/composite_receipt.json", "hybrid15-x/hybrid_receipt.json",
        "exposure-caps-x/receipt.json", "exposure-caps-r2-x/receipt.json", "cash-shadow-w04-A-x/receipt.json",
        "shadow-x/receipt.json", "paper-r2-x/receipt.json", "after-K110-x/pair-support.json", "ENTER/ENTER-rowmap.json",
    ])
    def test_every_chain_artifact_family_is_declared(self, tmp_path, rel):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"pulled_at": "2026-09-12"}))
        findings, scanned = rfs.sweep(tmp_path, WINDOW, declared=rfs.DECLARED_INPUTS)
        assert scanned == 1 and len(findings) == 1

    @pytest.mark.parametrize("rel", [
        "linestar-prelock-top5/capture.json", "rebuild-20260930/contests.json", "tabpfn-mech-w3/receipt.json",
        "contest-details-20260930.json", "notes.json", "composite-x.json",
    ])
    def test_undeclared_paths_are_not_swept(self, tmp_path, rel):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"pulled_at": "2026-09-12"}))
        assert rfs.sweep(tmp_path, WINDOW, declared=rfs.DECLARED_INPUTS) == ([], 0)

    def test_all_restores_the_full_audit_and_declared_extends_the_list(self, tmp_path, capsys):
        self._stray(tmp_path)
        assert rfs.main(["--dir", str(tmp_path), "--after", "2026-09-29", "--all"]) == 1
        assert rfs.main(["--dir", str(tmp_path), "--after", "2026-09-29", "--declared", "linestar-*/*.json"]) == 1
        assert rfs.main(["--dir", str(tmp_path), "--after", "2026-09-29"]) == 0

    def test_the_chain_never_passes_all(self):
        chain = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_after_build.sh").read_text()
        call = chain.split('receipt_freshness_sweep.py" --dir')[1].split("\n")[0]
        assert "--all" not in call
