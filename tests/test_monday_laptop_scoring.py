"""monday_laptop_scoring.sh (2026-09-29 sweep A2): scores every cash-shadow arm the chain wrote under $OUT and exits
non-zero when none exist; a stub scorer stands in for cash_shadow_paper.py and the Millionaire id is given."""
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "reports" / "lab-handoffs" / "monday_laptop_scoring.sh"


def _stub_prod(tmp_path):
    prod = tmp_path / "prod"; (prod / "reports" / "lab-handoffs").mkdir(parents=True); (prod / "src").mkdir()
    (prod / "reports" / "lab-handoffs" / "cash_shadow_paper.py").write_text(
        "import sys\nprint('SCORED', sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[6])\n")
    return prod


def _run(tmp_path, out):
    env = {**os.environ, "PROD": str(_stub_prod(tmp_path)), "PROD_PY": "python3", "OUT": str(out), "MILLY_CONTEST_ID": "196151357",
           "LOG": str(tmp_path / "log.txt")}
    return subprocess.run(["bash", str(SCRIPT), "4"], capture_output=True, text=True, env=env)


def test_scores_every_arm_found(tmp_path):
    out = tmp_path / "week4"; out.mkdir()
    for d in ("cash-shadow-w04-A-sun-d800", "cash-shadow-w04-B-sun-d800", "cash-shadow-w04-A-sun-d3200"):
        (out / d).mkdir(); (out / d / "receipt.json").write_text("{}")
    (out / "cash-shadow-w04-A-broken").mkdir()                      # no receipt: not an arm
    r = _run(tmp_path, out)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.count("SCORED") == 3 and "196151357" in r.stdout and "3 arm(s) scored" in r.stdout


def test_no_arms_is_a_failure_not_a_shrug(tmp_path):
    out = tmp_path / "week4"; out.mkdir()
    r = _run(tmp_path, out)
    assert r.returncode == 2 and "NO CASH-SHADOW ARMS" in r.stdout
