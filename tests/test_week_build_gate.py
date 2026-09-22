"""Exercise the shell entrypoint with isolated providers and a recording driver."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize("gate_code", [0, 1, 7])
def test_gate_precedes_driver_and_propagates_failure(tmp_path, gate_code):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    root = Path(__file__).resolve().parents[1]
    shutil.copy2(root / "scripts/run_week_build.sh", scripts)
    (scripts / "week_env.sh").write_text('''week_env() {
      export WEEK="$1" SEASON=2026 GROUP=153769 OUT="$TEST_ROOT" PROD="$TEST_ROOT"
      export PROD_PY="$TEST_ROOT/fake-python"
      export CHOSEN_FILE="$TEST_ROOT/dose file.env" CONTESTS_JSON="$TEST_ROOT/contests file.json"
    }
''')
    interpreter = tmp_path / "fake-python"
    interpreter.write_text('''#!/usr/bin/env bash
set -eu
case "$1" in
  */check_week_runtime.py) exit 0;;
  */check_build_inputs.py)
    printf '%s\\n' "$@" > "$TEST_ROOT/gate-args"
    exit "$GATE_CODE";;
esac
exit 99
''')
    interpreter.chmod(0o755)
    driver = scripts / "sunday_build_host.sh"
    driver.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$TEST_ROOT/driver-args"\n')
    driver.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k not in {"WEEK", "GROUP"}}
    env.update(TEST_ROOT=str(tmp_path), GATE_CODE=str(gate_code))
    result = subprocess.run(["bash", str(scripts / "run_week_build.sh"), "3", "argument with spaces"], env=env, capture_output=True, text=True)
    assert result.returncode == gate_code, result.stderr
    args = (tmp_path / "gate-args").read_text().splitlines()
    assert args[1:9] == ["--season", "2026", "--week", "3", "--chosen-dose", str(tmp_path / "dose file.env"), "--contests", str(tmp_path / "contests file.json")]
    assert args[9:11] == ["--draft-group", "153769"], "the gate must be told which DK draft group to size against"
    assert args[11] == "--receipt"
    assert Path(args[12]).is_file()
    assert (tmp_path / "driver-args").exists() == (gate_code == 0)
    if gate_code == 0:
        assert (tmp_path / "driver-args").read_text().strip() == "argument with spaces"
