import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
ENV_SCRIPT = ROOT / "scripts" / "week_env.sh"
LIVE_REPAIR_SHA = "2dc116ce95647a776ba9c36cf194f44d022d03a4"
# The Week-3 pin (2026-09-22): nfl2 9b341d77 -> parent 69f98a75 (Doubtful inactive set) -> which
# descends from 2dc116ce (the reviewed Week-2 live-game input repair). Verified with
# `git merge-base --is-ancestor 2dc116ce 9b341d77` when the pin moved.
LIVE_PIN_SHA = "9b341d77dd34c7e9ba6e82610ba06ccdf6a588ee"


def test_week3_default_keeps_the_reviewed_live_game_input_repair():
    source = ENV_SCRIPT.read_text()
    assert f"NFL2_EXPECT_SHA:-{LIVE_PIN_SHA}" in source, "EXPECT_SHA default is not the reviewed Week-3 pin"
    assert LIVE_REPAIR_SHA[:8] in source, "the pin's lineage to the Week-2 repair is no longer documented"
    assert "e7255e98bf87297452befb61fb508ad4b368b59f" not in source


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
