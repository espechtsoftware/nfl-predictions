"""Week-3 chalk sleeve wiring (operator 2026-09-25): CHALK_SLEEVE_SETS reaches every paid build, and the receipt check
fails closed unless the receipt shows exactly the armed state (tested SLEEVE_L2 when on; no sleeve when off)."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOST = (ROOT / "scripts" / "sunday_build_host.sh").read_text()
BOOK = (ROOT / "scripts" / "sunday_runbook.sh").read_text()
CHECK = re.search(r"<<'CAPEOF'[^\n]*\n(.*?)\nCAPEOF", HOST, re.S).group(1)
L2 = {"low_max": 2, "chalk_rule": "top-15 by pred_own", "share": 0.25, "min_salary": 49500, "solves": 640, "of_boom": 2560}


def _check(tmp_path, arm, want_cap="4", sleeve=""):
    (tmp_path / "receipt.json").write_text(json.dumps({"config": {"arm": arm}}))
    return subprocess.run([sys.executable, "-c", CHECK, str(tmp_path), want_cap, sleeve], capture_output=True).returncode


def test_every_paid_build_carries_the_sleeve_args():
    assert HOST.count('--emit-a5-sidecars "${MPG_ARGS[@]}" ${SLEEVE_ARGS[@]+"${SLEEVE_ARGS[@]}"}') == 2
    assert "--chalk-sleeve-sets $CHALK_SLEEVE_SETS --chalk-sleeve-low-max 2 --chalk-sleeve-chalk-k 15" in BOOK


@pytest.mark.parametrize("arm,sleeve,rc", [
    ({"max_per_game": 4}, "", 0),                                   # off, receipt without a sleeve
    ({"max_per_game": 4, "chalk_sleeve": L2}, "/x/sets.csv", 0),    # on, the tested sleeve
    ({"max_per_game": 4}, "/x/sets.csv", 1),                        # armed on but the build did not apply it
    ({"max_per_game": 4, "chalk_sleeve": L2}, "", 1),               # a sleeve nobody armed
    ({"max_per_game": 4, "chalk_sleeve": {**L2, "low_max": 1}}, "/x/sets.csv", 1),   # not the tested arm
])
def test_receipt_check_matches_the_armed_state(tmp_path, arm, sleeve, rc):
    assert _check(tmp_path, arm, sleeve=sleeve) == rc
