import json
import os
import sys
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
ENV_SCRIPT = ROOT / "scripts" / "week_env.sh"
LIVE_REPAIR_SHA = "2dc116ce95647a776ba9c36cf194f44d022d03a4"
# The Week-3 pin (2026-09-22): nfl2 9b341d77 -> parent 69f98a75 (Doubtful inactive set) -> which
# descends from 2dc116ce (the reviewed Week-2 live-game input repair). Verified with
# `git merge-base --is-ancestor 2dc116ce 9b341d77` when the pin moved.
# 2026-09-25: advanced to 65305f5a (parent 9b341d77, one commit: LIVE_FLEX_LATEST, default off in nfl2).
LIVE_PIN_SHA = "65305f5a6c33dba6ffa299813ee689b618bbcd30"


def test_week3_default_keeps_the_reviewed_live_game_input_repair():
    source = ENV_SCRIPT.read_text()
    assert f"NFL2_EXPECT_SHA:-{LIVE_PIN_SHA}" in source, "EXPECT_SHA default is not the reviewed Week-3 pin"
    assert LIVE_REPAIR_SHA[:8] in source, "the pin's lineage to the Week-2 repair is no longer documented"
    assert "e7255e98bf87297452befb61fb508ad4b368b59f" not in source


def test_week3_default_puts_the_latest_starter_in_flex():
    source = ENV_SCRIPT.read_text()
    assert "export LIVE_FLEX_LATEST=${LIVE_FLEX_LATEST:-1}" in source


def test_week3_default_turns_the_per_game_cap_on():
    source = ENV_SCRIPT.read_text()
    assert "export MAX_PER_GAME=${MAX_PER_GAME:-4}" in source


def test_missing_contests_file_fails_with_an_actionable_message(tmp_path):
    missing = tmp_path / "contests.json"
    env = os.environ.copy()
    env.update({
        "GROUP": "153769",
        "SEASON": "2026",
        "OUT": str(tmp_path / "out"),
        "CONTESTS_JSON": str(missing),
        "PROD_PY": "/bin/false",
    })
    result = subprocess.run(
        ["bash", "-c", f"source {ENV_SCRIPT}; week_env 3"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert f"contests file missing: {missing}" in result.stderr


def test_two_track_contests_split_mean_rows_and_the_tail_sleeve(tmp_path):
    """Operator 2026-09-27: BOOK_ENTRIES is the mean-track row count the builder receives; TAIL_SLEEVE the Millionaire
    rows appended after them. Under head with 19 one-entry satellites + a 20-entry supersat + a tail Millionaire seat:
    mean rows = 4 head + 15 unique + 16 unique = 35 (no 90-row floor since 2026-09-28); sleeve = 1."""
    contests = tmp_path / "contests.json"
    cs = [{"name": "sat20", "contest_id": str(1000 + i), "entries": 1, "keep": 1} for i in range(19)]
    cs += [{"name": "supersat", "contest_id": "2000", "entries": 20, "keep": 20},
           {"name": "milly20", "contest_id": "3000", "entries": 1, "keep": 1, "track": "tail"}]
    contests.write_text(json.dumps(cs))
    env = os.environ.copy()
    env.update({"GROUP": "153769", "SEASON": "2026", "OUT": str(tmp_path / "out"), "CONTESTS_JSON": str(contests),
                "ENTER_LAYOUT": "head", "PROD_PY": sys.executable, "PROD": str(ROOT)})
    r = subprocess.run(["bash", "-c", f"source {ENV_SCRIPT}; week_env 3 >/dev/null && echo $BOOK_ENTRIES $TAIL_SLEEVE $LIVE_SELECTOR $LIVE_MIN_PROJ $MEAN_OWN_TILT $MEAN_DST_CAP $ENTER_FLAG_LATE_Q_ONLY $T70_ACTIVE_Q $T70_VACATED_BUMP $TAIL_SLEEVE_SELECTOR $CLASS_SLEEVE_EVERY"],
                       env=env, text=True, capture_output=True, check=False)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["35", "1", "mean", "1.0", "0", "0.25", "1", "1", "1", "mean", "2"]   # reviewer 2026-09-28 10:30: mean everywhere, class sleeve 2, class withdrawn   # operator decisions 2026-09-28 as defaults
