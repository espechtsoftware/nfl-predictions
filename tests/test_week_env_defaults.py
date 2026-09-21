import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
ENV_SCRIPT = ROOT / "scripts" / "week_env.sh"
LIVE_REPAIR_SHA = "2dc116ce95647a776ba9c36cf194f44d022d03a4"


def test_week3_default_keeps_the_reviewed_live_game_input_repair():
    source = ENV_SCRIPT.read_text()
    assert LIVE_REPAIR_SHA in source
    assert "e7255e98bf87297452befb61fb508ad4b368b59f" not in source


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
