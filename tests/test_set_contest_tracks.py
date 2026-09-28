"""set_contest_tracks: tail unless the field is small (the 11-entry satellites); tail contests re-ordered by priority;
overrides honoured and disclosed; every gap refuses."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import set_contest_tracks as sct  # noqa: E402


def _details(field, places):
    return {"max": field, "entries": field, "payoutSummary": [{"minPosition": 1, "maxPosition": places}]}


CONTESTS = [
    {"contest_id": 1, "name": "sat20", "entries": 3, "fee": 20},
    {"contest_id": 2, "name": "wildcat", "entries": 2, "fee": 333, "priority": 4},
    {"contest_id": 3, "name": "milly", "entries": 20, "fee": 20, "priority": 1},
    {"contest_id": 4, "name": "supersat", "entries": 5, "fee": 25, "priority": 5},
]
DETAILS = {"1": _details(11, 1), "2": _details(79, 1), "3": _details(161764, 37425), "4": _details(2378, 25)}


def test_small_field_is_mean_everything_else_tail_in_priority_order():
    out, lines, problems = sct.decide(CONTESTS, DETAILS, 20)
    assert problems == []
    assert [(c["name"], c["track"]) for c in out] == [("sat20", "mean"), ("milly", "tail"), ("wildcat", "tail"), ("supersat", "tail")]
    assert out[1]["line_percentile"] == pytest.approx(76.86)
    deals = [ln for ln in lines if ln.startswith("deal:")]
    assert deals == ["deal: sleeve rows 1-20 -> milly (priority 1)", "deal: sleeve rows 21-22 -> wildcat (priority 4)",
                     "deal: sleeve rows 23-27 -> supersat (priority 5)"]


def test_override_wins_and_is_disclosed():
    cs = [dict(CONTESTS[0], track_override="tail", priority=9)] + CONTESTS[1:]
    out, lines, problems = sct.decide(cs, DETAILS, 20)
    assert problems == [] and out[-1]["name"] == "sat20" and out[-1]["track"] == "tail"
    assert any("override; rule said mean" in ln for ln in lines)


def test_tail_without_priority_refuses():
    cs = CONTESTS[:2] + [{k: v for k, v in CONTESTS[2].items() if k != "priority"}] + CONTESTS[3:]
    out, _, problems = sct.decide(cs, DETAILS, 20)
    assert problems == ["3 (milly): tail contest needs an integer priority (1 = dealt first)"] and out == cs


def test_shared_priority_refuses():
    cs = CONTESTS[:3] + [dict(CONTESTS[3], priority=1)]
    _, _, problems = sct.decide(cs, DETAILS, 20)
    assert problems == ["priority 1 is shared by milly and supersat"]


def test_bad_override_and_missing_details_refuse():
    _, _, problems = sct.decide([dict(CONTESTS[0], track_override="class")] + CONTESTS[1:], DETAILS, 20)
    assert problems and "track_override" in problems[0]
    _, _, problems = sct.decide(CONTESTS, {k: v for k, v in DETAILS.items() if k != "4"}, 20)
    assert problems == ["4 (supersat): not in the details file"]
    d = dict(DETAILS); d["2"] = {"max": 79, "payoutSummary": []}
    _, _, problems = sct.decide(CONTESTS, d, 20)
    assert problems == ["2 (wildcat): field size or ladder missing"]


def test_write_reorders_keeps_fields_and_backs_up(tmp_path):
    cfile = tmp_path / "contests.json"; dfile = tmp_path / "details.json"
    cfile.write_text(json.dumps({"week": 4, "contests": CONTESTS})); dfile.write_text(json.dumps(DETAILS))
    assert sct.main(["--contests", str(cfile), "--details", str(dfile)]) == 0
    assert json.loads(cfile.read_text())["contests"] == CONTESTS  # dry run changes nothing
    assert sct.main(["--contests", str(cfile), "--details", str(dfile), "--write"]) == 0
    got = json.loads(cfile.read_text())
    assert got["week"] == 4 and [c["name"] for c in got["contests"]] == ["sat20", "milly", "wildcat", "supersat"]
    assert got["contests"][2]["fee"] == 333 and got["contests"][2]["track"] == "tail"
    assert (tmp_path / "contests.json.bak").exists()


def test_main_refuses_on_gap_and_leaves_file(tmp_path):
    cfile = tmp_path / "contests.json"; dfile = tmp_path / "details.json"
    cfile.write_text(json.dumps(CONTESTS)); dfile.write_text(json.dumps({"1": DETAILS["1"]}))
    assert sct.main(["--contests", str(cfile), "--details", str(dfile), "--write"]) == 2
    assert json.loads(cfile.read_text()) == CONTESTS


def test_all_main_puts_every_contest_on_the_main_track_in_file_order_without_priorities():
    """Operator 2026-09-28 10:07 (configuration A): the class selector orders the whole book over the head layout."""
    cs = [{k: v for k, v in c.items() if k != "priority"} for c in CONTESTS]
    out, lines, problems = sct.decide(cs, DETAILS, 20, all_main=True)
    assert problems == []
    assert [c["name"] for c in out] == [c["name"] for c in CONTESTS] and all(c["track"] == "mean" for c in out)
    assert all("main (class selector" in ln for ln in lines) and not any(ln.startswith("deal:") for ln in lines)
    _, _, problems = sct.decide([dict(cs[0], track_override="tail")] + cs[1:], DETAILS, 20, all_main=True)
    assert problems == ["1 (sat20): track_override 'tail' contradicts --all-main"]


def test_all_main_flag_writes_config_a(tmp_path, capsys):
    cfile = tmp_path / "contests.json"; dfile = tmp_path / "details.json"
    cfile.write_text(json.dumps(CONTESTS)); dfile.write_text(json.dumps(DETAILS))
    assert sct.main(["--contests", str(cfile), "--details", str(dfile), "--all-main", "--write"]) == 0
    assert "configuration A" in capsys.readouterr().out
    got = json.loads(cfile.read_text())
    assert [c["track"] for c in got] == ["mean"] * 4 and got[2]["priority"] == 1   # other fields untouched


def test_rule_line_orders_deepest_line_first_all_main_track_with_deep_flags():
    """Reviewer 2026-09-28 after the Week-1 gate: mean selector for every contest; deepest rows dealt to the deepest lines."""
    cs = [{k: v for k, v in c.items() if k != "priority"} for c in CONTESTS]
    out, lines, problems = sct.decide_by_line(cs, DETAILS, 0.02)
    assert problems == []
    assert [c["name"] for c in out] == ["supersat", "wildcat", "sat20", "milly"]        # p98.95, p98.73, p90.9, p76.9
    assert [c["deep_line"] for c in out] == [True, True, False, False] and all(c["track"] == "mean" for c in out)
    assert lines[0].startswith("supersat") and "dealt #1" in lines[0] and "DEEP" in lines[0]
    _, _, problems = sct.decide_by_line([dict(cs[0], track_override="tail")] + cs[1:], DETAILS, 0.02)
    assert problems == ["1 (sat20): track_override 'tail' is not a mean-track contest; --rule line has no sleeve"]
    _, _, problems = sct.decide_by_line(cs, {k: v for k, v in DETAILS.items() if k != "2"}, 0.02)
    assert problems == ["2 (wildcat): not in the details file"]


def test_rule_line_main_writes_the_order(tmp_path, capsys):
    cfile = tmp_path / "contests.json"; dfile = tmp_path / "details.json"
    cfile.write_text(json.dumps({"week": 4, "contests": CONTESTS})); dfile.write_text(json.dumps(DETAILS))
    assert sct.main(["--contests", str(cfile), "--details", str(dfile), "--rule", "line", "--write"]) == 0
    assert "rule line:" in capsys.readouterr().out
    got = json.loads(cfile.read_text())
    assert got["week"] == 4 and [c["name"] for c in got["contests"]] == ["supersat", "wildcat", "sat20", "milly"]
    assert sct.main(["--contests", str(cfile), "--details", str(dfile), "--rule", "line", "--all-main"]) == 2


def test_deep_as_tail_is_the_laptops_alternative_not_the_default():
    """The laptop's measured 10:29 configuration stays one flag away: deep-line contests + a forced Millionaire on a
    mean-selected sleeve, the Millionaire first, then by depth; main contests keep their depth order before them."""
    cs = [{k: v for k, v in c.items() if k != "priority"} for c in CONTESTS]
    cs[2] = dict(cs[2], track_override="tail")                       # the Millionaire (p76.9) forced onto the sleeve
    out, lines, problems = sct.decide_by_line(cs, DETAILS, 0.02, deep_as_tail=True)
    assert problems == []
    assert [(c["name"], c["track"]) for c in out] == [("sat20", "mean"), ("milly", "tail"), ("supersat", "tail"), ("wildcat", "tail")]
    assert [c["priority"] for c in out[1:]] == [1, 2, 3]
    assert [ln for ln in lines if ln.startswith("deal:")][0] == "deal: sleeve rows 1-20 -> milly (line p76.9, priority 1)"
