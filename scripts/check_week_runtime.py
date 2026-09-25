#!/usr/bin/env python3
"""Fail-closed preflight for the tracked Sunday money path.

This check is intentionally outcome-blind. It verifies identities, paths, tools, contest metadata and the chosen-dose
contract before a timer can launch a build or watcher. It does not query BigQuery or DraftKings; the build's own
provider checks remain responsible for fresh data.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


HELPERS = (
    "ordering_shadows.py", "hybrid30.py", "vet_book.py", "player_score.py", "book_sheet.py",
    "fill_dk_entries.py", "qb_classify.py", "qb_flags.py", "vet_replace_v4.py", "verify_enter_bundle.py",
)


def fail(message):
    print(f"WEEK RUNTIME PREFLIGHT FAILED: {message}", file=sys.stderr)
    raise SystemExit(2)


def git(root, *args):
    p = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)
    if p.returncode:
        fail(f"git {' '.join(args)} failed in {root}: {p.stderr.strip()}")
    return p.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=("build", "watchers"), required=True)
    args = ap.parse_args()
    required = ("SEASON", "WEEK", "WEEKDIR", "SUNDAY", "GROUP", "OUT", "CLONE", "PROD", "PROD_PY", "LAB_PY",
                "TOOLS", "CONTESTS_JSON", "LIVE_DIR", "EXPECT_SHA", "BOOK_ENTRIES")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        fail("missing environment: " + ", ".join(missing))
    prod = Path(os.environ["PROD"]); clone = Path(os.environ["CLONE"]); tools = Path(os.environ["TOOLS"])
    if not prod.is_dir(): fail(f"production checkout missing: {prod}")
    if not clone.is_dir(): fail(f"live clone missing: {clone}")
    if not tools.is_dir(): fail(f"tools directory missing: {tools}")
    for name in ("PROD_PY", "LAB_PY"):
        p = Path(os.environ[name])
        if not p.is_file() or not os.access(p, os.X_OK): fail(f"{name} is not executable: {p}")
    sha = os.environ["EXPECT_SHA"]
    if not re.fullmatch(r"[0-9a-f]{40}", sha): fail(f"EXPECT_SHA must be a full 40-character commit: {sha!r}")
    fixture_sha = "e7255e98bf87297452befb61fb508ad4b368b59f"
    if sha == fixture_sha and os.environ.get("ALLOW_FIXTURE_PIN") != "1":
        fail("EXPECT_SHA is the compatibility fixture e7255e98...; export the approved Week-3 pin (or set ALLOW_FIXTURE_PIN=1 only for a deliberate rehearsal)")
    actual = git(clone, "rev-parse", "HEAD")
    if actual != sha: fail(f"live clone identity {actual} != EXPECT_SHA {sha}")
    if git(clone, "status", "--porcelain"): fail(f"live clone is dirty: {clone}")
    if git(prod, "status", "--porcelain"): fail(f"production checkout is dirty: {prod}")
    if not (clone / "scripts/live_week.py").is_file(): fail("live clone has no scripts/live_week.py")
    if not (prod / "scripts/sunday_build_host.sh").is_file(): fail("production checkout has no sunday_build_host.sh")
    missing_tools = [name for name in HELPERS if not (tools / name).is_file()]
    if missing_tools: fail("missing tracked/helper tools: " + ", ".join(missing_tools))
    contests_path = Path(os.environ["CONTESTS_JSON"])
    if not contests_path.is_file(): fail(f"contest file missing: {contests_path}")
    try:
        contests = json.loads(contests_path.read_text())
    except Exception as exc:
        fail(f"contest file is not JSON: {exc}")
    if not isinstance(contests, list) or not contests: fail("contests.json must be a non-empty list")
    total = 0
    for contest in contests:
        if not isinstance(contest, dict) or not {"name", "contest_id", "entries", "keep"}.issubset(contest):
            fail(f"contest entry lacks name/id/entries/keep: {contest!r}")
        if "REPLACE" in json.dumps(contest): fail(f"contest template marker remains: {contest!r}")
        if not str(contest["contest_id"]).isdigit(): fail(f"contest id is not numeric: {contest!r}")
        if int(contest["entries"]) < int(contest["keep"]): fail(f"keep exceeds entries: {contest!r}")
        total += int(contest["entries"])
    book_entries = int(os.environ["BOOK_ENTRIES"])
    layout = os.environ.get("ENTER_LAYOUT") or "sequential"
    sys.path.insert(0, str(prod / "src"))
    from nfl_dfs.inference import enter_layout   # the one layout rule (2026-09-24)
    try:
        required_entries = enter_layout.rows_needed(contests, layout)
    except enter_layout.LayoutError as exc:
        fail(str(exc))
    if book_entries < max(90, required_entries):
        fail(f"BOOK_ENTRIES={book_entries} cannot satisfy {layout} contest layout (needs {max(90, required_entries)})")
    if layout != "sequential":                  # laptop review F2: show every contest's ranks at arming time
        print(f"{layout} layout, {required_entries} distinct lineups:")
        for line in enter_layout.rank_summary(contests, layout):
            print("  " + line)
    sleeve = os.environ.get("CHALK_SLEEVE_SETS") or ""
    if sleeve and not Path(sleeve).is_file():
        fail(f"CHALK_SLEEVE_SETS={sleeve} does not exist; build it with ownership_sets.py sets --lag-features before arming")
    order = os.environ.get("ENTER_ORDER") or "greedy"
    if order not in enter_layout.ORDERS: fail(f"unknown ENTER_ORDER {order!r}; expected one of {enter_layout.ORDERS}")
    if order == "fewest-low":
        sets = Path(os.environ.get("OWNERSHIP_SETS", ""))
        if not sets.is_file():
            fail(f"ENTER_ORDER=fewest-low needs the Saturday sets file OWNERSHIP_SETS={sets} (scripts/ownership_sets.py sets "
                 f"--week {os.environ['WEEK']} --group {os.environ['GROUP']} --out {sets}); write it before arming")
    if args.role == "watchers":
        chosen = Path(os.environ.get("CHOSEN_FILE", ""))
        if not chosen.is_file(): fail(f"chosen dose file missing: {chosen}; write CHOSEN_LEV/CHOSEN_BOOM before arming watchers")
        text = chosen.read_text()
        for name in ("CHOSEN_LEV", "CHOSEN_BOOM"):
            if not re.search(rf"^\s*{name}\s*=\s*[0-9]+\s*$", text, re.MULTILINE):
                fail(f"chosen dose file lacks {name}=integer: {chosen}")
    print(f"week runtime preflight ok: role={args.role} season={os.environ['SEASON']} week={os.environ['WEEK']} "
          f"group={os.environ['GROUP']} book_entries={book_entries} layout={layout} order={order} clone={actual} tools={tools}")


if __name__ == "__main__":
    main()
