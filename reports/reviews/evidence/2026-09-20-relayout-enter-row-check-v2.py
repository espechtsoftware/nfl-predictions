"""Independent synthetic review of the corrected ENTER re-layout row check.

The fixture deliberately exercises the two supported layouts and a genuine
top-layout block contest. It uses no production lineup, outcome, or provider
data. The assertions verify both the exit/publish decision and the exact rows
written to each per-contest ENTER file.
"""
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


HERE = Path(__file__).parent
TOOL = Path(
    "/home/erich/projects/.nfl2-worktrees/prereg101-review-reply/"
    "handoffs/tools/promote-first-v1.2/relayout_enter.sh"
)
VERIFY_PROD = Path("/home/erich/projects/.nfl-predictions-worktrees/qb-gate-review-20260919")
PY = "/home/erich/projects/nfl-predictions/.venv/bin/python"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contest_rows(path: Path, contest: dict) -> list[list[str]]:
    pattern = f"ENTER-{contest['name']}-{contest['contest_id']}-*-entries-KEEP-first-*.csv"
    files = sorted(path.glob(pattern))
    assert len(files) == 1, (contest, files)
    return list(csv.reader(files[0].open(newline="")))[1:]


def run(root: Path, name: str, contests: list[dict], layout: str | None) -> dict:
    case = root / name
    case.mkdir()
    contests_path = case / "contests.json"
    contests_path.write_text(json.dumps(contests) + "\n")
    upload = case / "upload.csv"
    with upload.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"])
        for i in range(1, 6):
            writer.writerow([f"r{i}-{j}" for j in range(9)])

    env = dict(
        os.environ,
        CONTESTS_JSON=str(contests_path),
        PROD=str(VERIFY_PROD),
        PY=PY,
    )
    if layout is None:
        env.pop("ENTER_LAYOUT", None)
    else:
        env["ENTER_LAYOUT"] = layout
    proc = subprocess.run(
        ["bash", str(TOOL), str(upload), str(case), f"synthetic-{name}"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    enter = case / "ENTER"
    actual = {c["name"]: contest_rows(enter, c) for c in contests} if enter.exists() else {}
    if layout in (None, "sequential"):
        expected = {
            "milly": [[f"r1-{j}" for j in range(9)], [f"r3-{j}" for j in range(9)]],
            "flea": [[f"r2-{j}" for j in range(9)], [f"r4-{j}" for j in range(9)], [f"r5-{j}" for j in range(9)]],
        }
    elif layout == "top":
        expected = {
            "milly": [[f"r1-{j}" for j in range(9)], [f"r2-{j}" for j in range(9)]],
            # A block contest advances the block cursor; ordinary top contests
            # intentionally do not consume it and repeat the prefix.
            "flea": [[f"r1-{j}" for j in range(9)], [f"r2-{j}" for j in range(9)], [f"r3-{j}" for j in range(9)]],
        }
    else:
        raise AssertionError(layout)
    assert proc.returncode == 0, (name, proc.stdout, proc.stderr)
    assert enter.is_symlink(), (name, enter)
    assert actual == expected, (name, actual, expected)
    return {
        "name": name,
        "requested_layout": layout or "unset (script default)",
        "exit_code": proc.returncode,
        "enter_is_symlink": enter.is_symlink(),
        "actual_rows": actual,
        "expected_rows": expected,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def main() -> None:
    root = Path(
        tempfile.mkdtemp(
            prefix="relayout-enter-row-check-v2-",
            dir="/home/erich/projects/review-evidence/overnight-20260918",
        )
    )
    base = [
        {"name": "milly", "contest_id": "1", "entries": 2, "keep": 1},
        {"name": "flea", "contest_id": "2", "entries": 3, "keep": 1},
    ]
    blocked = [dict(base[0]), dict(base[1], block=True)]
    cases = [
        run(root, "default-sequential", base, None),
        run(root, "explicit-sequential", base, "sequential"),
        run(root, "explicit-top", base, "top"),
        run(root, "top-with-real-block", blocked, "top"),
    ]
    result = {
        "schema": "promotion-v2.1-relayout-row-check/v2",
        "tool_sha256": sha(TOOL),
        "verifier_sha256": sha(VERIFY_PROD / "scripts/verify_enter_bundle.py"),
        "synthetic_contests": base,
        "blocked_top_contests": blocked,
        "cases": cases,
        "no_production_inputs": True,
        "current_outcomes_read": False,
        "root": str(root),
    }
    out = HERE / "2026-09-20-relayout-enter-row-check-v2-result.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "tool_sha256": result["tool_sha256"],
                "cases": [
                    {
                        "name": c["name"],
                        "layout": c["requested_layout"],
                        "exit": c["exit_code"],
                        "enter_symlink": c["enter_is_symlink"],
                    }
                    for c in cases
                ],
                "result_sha256": sha(out),
                "result": str(out),
                "root": str(root),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
