#!/usr/bin/env python3
"""Did the T-70 build use the DraftKings salary pull made after the 10:30 CT inactives? (the outside review 10-07, M4;
the money-path rule "the T-70 rebuild must use the salary pull made after the 10:30 CT inactives").

    python scripts/check_salary_pull.py <run dir> --after <UTC ISO, the T-70 gate's MIN_PROJ_GENERATED_AT>

The 10:33 t70-pull unit is independent of the 10:50 build. A failed pull left the build on the morning's pull, with stale
DK statuses, and nothing said so. Exit 0 = the receipt's `salary_pull` is at or after --after. Exit 1 = it is older, or
missing, or unparseable; the reason goes to stdout. The build host then marks the dir `salary_pull_stale`, a STOP the
operator clears (SALARY_PULL_STALE_OK=1). Times are compared by content, never as strings.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_dir_publishable import parse_utc  # noqa: E402


def check(run: Path, after: str) -> tuple[bool, str]:
    try:
        pull = json.loads((Path(run) / "receipt.json").read_text()).get("salary_pull")
    except (OSError, ValueError) as exc:
        return False, f"unreadable receipt: {exc}"
    if not pull:
        return False, "the receipt names no salary_pull"
    try:
        stale = parse_utc(pull) < parse_utc(after)
    except (TypeError, ValueError) as exc:
        return False, f"unparseable salary_pull / threshold: {exc}"
    if stale:
        return False, f"the T-70 build used the DK pull of {pull}, before {after} (the 10:30 CT inactives)"
    return True, f"salary pull {pull} is at or after {after}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run", type=Path); ap.add_argument("--after", required=True)
    a = ap.parse_args(argv)
    ok, why = check(a.run, a.after)
    print(why)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
