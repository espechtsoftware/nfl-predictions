#!/usr/bin/env python3
"""Resume the 2026 NFL production schedulers only after forensic cleanup.

This is the season-start gate paired with cleanup_final_forensic_warehouse.py.
It first re-verifies that the four manifest-bound review tables are absent,
then proves the cleanup receipt is committed on the pushed main history.  No
scheduler is touched unless every scheduler identity can also be described.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


PROJECT = "nfl-predictions-503414"
REGION = "us-central1"
SCHEDULERS = (
    "s-nflverse",
    "s-features",
    "s-features-route",
    "s-train",
    "s-train-k1",
    "s-train-k1-role",
    "s-train-k1-route",
    "s-train-k1-route-role",
    "s-project-tu",
    "s-project-su",
    "s-shadow-k1-early",
    "s-shadow-k1-late",
    "s-shadow-k1-nofloor-early",
    "s-shadow-k1-nofloor-late",
    "s-shadow-k3-early",
    "s-shadow-k3-late",
    "s-shadow-k1-roleunion-early",
    "s-shadow-k1-roleunion-late",
    "s-shadow-k1-route-roleunion-early",
    "s-shadow-k1-route-roleunion-late",
    "s-shadow-archetype-paired-early",
    "s-shadow-archetype-paired-late",
    "s-freeze-tail-early",
    "s-freeze-tail-late",
)


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )


def verify_receipt_in_pushed_main(repo_root: Path, receipt: Path) -> None:
    """Require the exact local receipt bytes in HEAD and pushed origin/main."""
    relative = receipt.resolve().relative_to(repo_root.resolve()).as_posix()
    tracked = _run(["git", "show", f"HEAD:{relative}"], cwd=repo_root).stdout
    if tracked.encode("utf-8") != receipt.read_bytes():
        raise RuntimeError("cleanup receipt differs from the committed HEAD copy")
    _run(["git", "fetch", "origin", "main"], cwd=repo_root)
    _run(
        ["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"],
        cwd=repo_root,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--confirm-manifest-sha", required=True)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume after all checks; without this flag the command is a dry run",
    )
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    manifest = args.manifest.resolve()
    receipt = args.receipt.resolve()
    cleanup = repo_root / "scripts" / "cleanup_final_forensic_warehouse.py"

    _run(
        [
            sys.executable,
            str(cleanup),
            "--manifest",
            str(manifest),
            "--confirm-manifest-sha",
            args.confirm_manifest_sha,
            "--receipt",
            str(receipt),
            "--verify-only",
        ],
        cwd=repo_root,
    )
    verify_receipt_in_pushed_main(repo_root, receipt)

    for scheduler in SCHEDULERS:
        _run(
            [
                "gcloud", "scheduler", "jobs", "describe", scheduler,
                "--project", PROJECT, "--location", REGION,
                "--format=value(name)",
            ],
            cwd=repo_root,
        )
    if not args.resume:
        print(
            "PASS: forensic corpus is absent, receipt is pushed, and all "
            "scheduler identities exist; no scheduler was resumed."
        )
        return 0
    for scheduler in SCHEDULERS:
        _run(
            [
                "gcloud", "scheduler", "jobs", "resume", scheduler,
                "--project", PROJECT, "--location", REGION, "--quiet",
            ],
            cwd=repo_root,
        )
    print(f"PASS: resumed {len(SCHEDULERS)} production schedulers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
