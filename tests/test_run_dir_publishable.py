"""The watcher's publish gate: audit_passed required; union mode needs config.union or union_failed; audit_failed never."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_dir_publishable as rp  # noqa: E402


def _run(tmp_path, union=False, files=("receipt.json", "candidates.parquet", "incumbent_player_scores.npy")):
    d = tmp_path / "r"; d.mkdir(exist_ok=True)
    for f in files:
        (d / f).write_text(json.dumps({"config": {"union": {"t70_run": "x"} if union else None}}) if f == "receipt.json" else "x")
    return d


def test_incomplete_run_dir_is_not_publishable(tmp_path):
    d = _run(tmp_path, files=("receipt.json",))
    ok, why = rp.publishable(d, False)
    assert not ok and "not written yet" in why


def test_audit_marker_gates_publication(tmp_path):
    d = _run(tmp_path)
    ok, why = rp.publishable(d, False)
    assert not ok and "audit_passed" in why
    (d / "audit_passed").touch()
    assert rp.publishable(d, False) == (True, "publishable")
    (d / "audit_failed").touch()
    ok, why = rp.publishable(d, False)
    assert not ok and "refused" in why


def test_union_mode_publishes_only_the_union_or_a_marked_fallback(tmp_path):
    plain = _run(tmp_path); (plain / "audit_passed").touch()
    ok, why = rp.publishable(plain, True)
    assert not ok and "union" in why
    (plain / "union_failed").touch()
    assert rp.publishable(plain, True)[0]
    u = tmp_path / "u"; u.mkdir()
    for f in ("candidates.parquet", "incumbent_player_scores.npy", "audit_passed"):
        (u / f).write_text("x")
    (u / "receipt.json").write_text(json.dumps({"config": {"union": {"t70_run": "x"}}}))
    assert rp.publishable(u, True)[0]


def test_rehearsal_override_is_explicit(tmp_path):
    d = _run(tmp_path)
    ok, why = rp.publishable(d, False, audit_gate=False)
    assert ok and "rehearsal override" in why
    assert rp.main([str(d)]) == 1 and rp.main([str(d), "--no-audit-gate"]) == 0


def test_group_window_and_superseded_gate_publication(tmp_path):
    d = _run(tmp_path); (d / "audit_passed").touch()
    (d / "receipt.json").write_text(json.dumps({"draft_group": 154078, "built_utc": "2026-10-03 15:00:00+00:00", "config": {}}))
    assert rp.publishable(d, False, group="154078", built_after="2026-10-03T05:00:00")[0]
    ok, why = rp.publishable(d, False, group="154077")
    assert not ok and "draft group" in why
    ok, why = rp.publishable(d, False, built_after="2026-10-03T16:00:00")
    assert not ok and "before this week's window" in why
    (d / "superseded").touch()
    ok, why = rp.publishable(d, False)
    assert not ok and "superseded" in why


def test_parse_utc_compares_the_lab_form_and_iso_by_content():
    assert rp.parse_utc("2026-10-03 15:00:00.123456+00:00") > rp.parse_utc("2026-10-03T05:00:00")
    assert rp.parse_utc("2026-10-03T15:00:00Z") == rp.parse_utc("2026-10-03 15:00:00+00:00")


def test_a_missing_term_block_stops_publication_until_the_operator_accepts(tmp_path):
    """The reviewer (10-07): a decided live rule must not go missing silently -- a union the host marked
    term_block_missing is not published unless --accept-term-block-missing (TERM_BLOCK_MISSING_OK=1, his decision)."""
    d = _run(tmp_path, union=True); (d / "audit_passed").touch()
    assert rp.publishable(d, True) == (True, "publishable")
    (d / "term_block_missing").write_text("2026-10-11T15:50Z run x: TERM BLOCK MISSING: not applied: OWN TERM REFUSED\n")
    ok, why = rp.publishable(d, True)
    assert not ok and "term_block_missing" in why and "OWN TERM REFUSED" in why and "TERM_BLOCK_MISSING_OK=1" in why
    assert rp.publishable(d, True, accept_term_block_missing=True) == (True, "publishable")
    assert rp.main([str(d), "--union-mode"]) == 1 and rp.main([str(d), "--union-mode", "--accept-term-block-missing"]) == 0


def test_a_union_failure_under_the_weeks_settings_stops_publication_until_the_operator_accepts(tmp_path):
    """The outside review 10-07, H1: a T-70 dir the host marked union_failed AND union_required (the union failed while the
    week's construction lives in it: MIX or a live term block) is not published -- the plain T-70 book has none of it --
    unless --accept-union-failed (UNION_FAILED_OK=1). union_failed alone stays the fallback (a house-shape week)."""
    d = _run(tmp_path, union=False); (d / "audit_passed").touch(); (d / "union_failed").touch()
    assert rp.publishable(d, True) == (True, "publishable")                                  # the old fallback
    (d / "union_required").write_text("2026-10-11T15:52Z run x: UNION FAILED (the union build audit failed) under UNION_MAIN=mix\n")
    ok, why = rp.publishable(d, True)
    assert not ok and why.startswith("union_required:") and "UNION_FAILED_OK=1" in why and "build audit failed" in why
    assert rp.publishable(d, True, accept_union_failed=True) == (True, "publishable")
    assert rp.main([str(d), "--union-mode"]) == 1 and rp.main([str(d), "--union-mode", "--accept-union-failed"]) == 0


def test_a_stale_salary_pull_stops_publication_until_the_operator_accepts(tmp_path):
    """The outside review 10-07, M4: a build marked salary_pull_stale is a STOP (SALARY_PULL_STALE_OK=1 enters it)."""
    d = _run(tmp_path, union=True); (d / "audit_passed").touch()
    (d / "salary_pull_stale").write_text("2026-10-11T15:52Z run x: SALARY PULL STALE: the T-70 build used the DK pull of 14:05\n")
    ok, why = rp.publishable(d, True)
    assert not ok and why.startswith("salary_pull_stale:") and "SALARY_PULL_STALE_OK=1" in why
    assert rp.publishable(d, True, accept_salary_pull_stale=True) == (True, "publishable")
    assert rp.main([str(d), "--union-mode", "--accept-salary-pull-stale"]) == 0
