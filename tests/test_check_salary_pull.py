"""The outside review 10-07, M4: the T-70 build must have used the DK salary pull made after the 10:30 CT inactives."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_salary_pull as C  # noqa: E402

AFTER = "2026-10-11T15:30:00+00:00"                                     # 10:30 CDT


def _run(tmp_path, pull):
    d = tmp_path / "r"; d.mkdir(exist_ok=True)
    (d / "receipt.json").write_text(json.dumps({"salary_pull": pull} if pull is not None else {}))
    return d


def test_the_1033_pull_passes_in_the_labs_str_form(tmp_path):
    ok, why = C.check(_run(tmp_path, "2026-10-11 15:33:13.856511+00:00"), AFTER)          # W4's receipt form
    assert ok and "at or after" in why


def test_a_morning_pull_missing_or_unparseable_fails(tmp_path):
    ok, why = C.check(_run(tmp_path, "2026-10-11 14:05:00+00:00"), AFTER)
    assert not ok and "before 2026-10-11T15:30:00+00:00" in why
    assert C.check(_run(tmp_path, None), AFTER) == (False, "the receipt names no salary_pull")
    assert not C.check(_run(tmp_path, "yesterday"), AFTER)[0]
    assert C.main([str(_run(tmp_path, "2026-10-11 14:05:00+00:00")), "--after", AFTER]) == 1
