#!/usr/bin/env python3
"""Resume 2026 production schedulers only after aggregate forensic cleanup.

No scheduler mutation occurs until the immutable repair3-plus-repair4 cleanup
receipt has passed and all 27 schedulers exactly match the tracked paused-state,
cadence, timezone, HTTP method, and Cloud Run target contract.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


PROJECT = "nfl-predictions-503414"
REGION = "us-central1"
TIME_ZONE = "America/Chicago"
SCHEDULER_SERVICE_ACCOUNT = (
    "817589974517-compute@developer.gserviceaccount.com"
)

# Frozen from deploy/deploy_jobs.sh and deploy/deploy_sis_pass_tail_cache.sh.
# Values are (Cloud Run job name, cron cadence).
SCHEDULER_CONTRACTS: dict[str, tuple[str, str]] = {
    "s-nflverse": ("ingest-nflverse", "0 5 * * *"),
    "s-features": ("build-features", "30 6 * * 2"),
    "s-features-route": ("build-features", "30 6 * * 4"),
    "s-train": ("train-weekly", "30 7 * * 2"),
    "s-train-k1": ("train-weekly-k1", "30 8 * * 2"),
    "s-train-k1-role": ("train-weekly-k1-role", "45 8 * * 2"),
    "s-train-k1-route": ("train-weekly-k1-route", "30 7 * * 4"),
    "s-train-k1-route-role": ("train-weekly-k1-route-role", "0 8 * * 4"),
    "s-project-tu": ("project-slate", "30 9 * * 2"),
    "s-project-su": ("project-slate", "0 6-11 * * 7"),
    "s-shadow-k1-early": ("shadow-k1", "30 10 * * 7"),
    "s-shadow-k1-late": ("shadow-k1", "20 11 * * 7"),
    "s-shadow-k1-nofloor-early": ("shadow-k1-nofloor", "30 10 * * 7"),
    "s-shadow-k1-nofloor-late": ("shadow-k1-nofloor", "20 11 * * 7"),
    "s-shadow-k3-early": ("shadow-k3", "30 10 * * 7"),
    "s-shadow-k3-late": ("shadow-k3", "20 11 * * 7"),
    "s-shadow-k1-roleunion-early": ("shadow-k1-roleunion", "20 10 * * 7"),
    "s-shadow-k1-roleunion-late": ("shadow-k1-roleunion", "10 11 * * 7"),
    "s-shadow-k1-route-roleunion-early": (
        "shadow-k1-route-roleunion", "20 10 * * 7"
    ),
    "s-shadow-k1-route-roleunion-late": (
        "shadow-k1-route-roleunion", "10 11 * * 7"
    ),
    "s-shadow-archetype-paired-early": (
        "shadow-archetype-paired", "15 9 * * 7"
    ),
    "s-shadow-archetype-paired-late": (
        "shadow-archetype-paired", "30 10 * * 7"
    ),
    "s-tabpfn-sis-pass-tail-control": (
        "tabpfn-sis-pass-tail-live-control", "15 9 * * 4"
    ),
    "s-tabpfn-sis-pass-tail-treatment": (
        "tabpfn-sis-pass-tail-live-treatment", "20 9 * * 4"
    ),
    "s-shadow-sis-pass-tail-paired": (
        "shadow-sis-pass-tail-paired", "0 6 * * 7"
    ),
    "s-freeze-tail-early": ("freeze-tail-early", "5 11 * * 7"),
    "s-freeze-tail-late": ("freeze-tail-late", "50 11 * * 7"),
}
SCHEDULERS = tuple(SCHEDULER_CONTRACTS)


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )


def _target_uri(job: str) -> str:
    return (
        f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/"
        f"{REGION}/jobs/{job}:run"
    )


def verify_receipt_in_pushed_main(repo_root: Path, receipt: Path) -> None:
    """Require the exact local receipt bytes in HEAD and pushed origin/main."""
    relative = receipt.resolve().relative_to(repo_root.resolve()).as_posix()
    receipt_bytes = receipt.read_bytes()
    tracked = _run(["git", "show", f"HEAD:{relative}"], cwd=repo_root).stdout
    if tracked.encode("utf-8") != receipt_bytes:
        raise RuntimeError("cleanup receipt differs from the committed HEAD copy")
    _run(["git", "fetch", "origin", "main"], cwd=repo_root)
    _run(
        ["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"],
        cwd=repo_root,
    )
    pushed = _run(
        ["git", "show", f"origin/main:{relative}"], cwd=repo_root
    ).stdout
    if pushed.encode("utf-8") != receipt_bytes:
        raise RuntimeError("cleanup receipt differs from pushed origin/main copy")


def verify_scheduler_contract(
    scheduler: str,
    description: Mapping[str, Any],
    *,
    expected_state: str = "PAUSED",
) -> None:
    if scheduler not in SCHEDULER_CONTRACTS:
        raise RuntimeError(f"scheduler is outside the frozen inventory: {scheduler}")
    if expected_state not in {"PAUSED", "ENABLED"}:
        raise RuntimeError(f"unsupported scheduler state contract: {expected_state}")
    job, schedule = SCHEDULER_CONTRACTS[scheduler]
    http_target = description.get("httpTarget") or {}
    actual = {
        "name": description.get("name"),
        "state": description.get("state"),
        "schedule": description.get("schedule"),
        "timeZone": description.get("timeZone"),
        "uri": http_target.get("uri"),
        "httpMethod": http_target.get("httpMethod"),
        "oauthServiceAccount": (http_target.get("oauthToken") or {}).get(
            "serviceAccountEmail"
        ),
        "bodyPresent": "body" in http_target,
    }
    expected = {
        "name": f"projects/{PROJECT}/locations/{REGION}/jobs/{scheduler}",
        "state": expected_state,
        "schedule": schedule,
        "timeZone": TIME_ZONE,
        "uri": _target_uri(job),
        "httpMethod": "POST",
        "oauthServiceAccount": SCHEDULER_SERVICE_ACCOUNT,
        "bodyPresent": False,
    }
    if actual != expected:
        raise RuntimeError(
            f"scheduler contract differs for {scheduler}: "
            f"expected={expected!r}, actual={actual!r}"
        )


def preflight_scheduler_contracts(
    repo_root: Path,
    *,
    expected_state: str = "PAUSED",
) -> None:
    """Describe and verify every scheduler against one exact state contract."""
    failures: list[str] = []
    for scheduler in SCHEDULERS:
        try:
            result = _run(
                [
                    "gcloud", "scheduler", "jobs", "describe", scheduler,
                    "--project", PROJECT, "--location", REGION, "--format=json",
                ],
                cwd=repo_root,
            )
            description = json.loads(result.stdout)
            if not isinstance(description, dict):
                raise RuntimeError("description is not a JSON object")
            verify_scheduler_contract(
                scheduler, description, expected_state=expected_state
            )
        except Exception as exc:
            failures.append(f"{scheduler}: {exc}")
    if failures:
        raise RuntimeError(
            f"scheduler {expected_state} contract failed: " + "; ".join(failures)
        )


def _scheduler_mutation(
    repo_root: Path,
    action: str,
    scheduler: str,
) -> None:
    if action not in {"pause", "resume"}:
        raise RuntimeError(f"unsupported scheduler mutation: {action}")
    _run(
        [
            "gcloud", "scheduler", "jobs", action, scheduler,
            "--project", PROJECT, "--location", REGION, "--quiet",
        ],
        cwd=repo_root,
    )


def resume_scheduler_contracts(repo_root: Path) -> None:
    """Resume atomically, rolling every attempted scheduler back on failure."""
    attempted: list[str] = []
    try:
        for scheduler in SCHEDULERS:
            # Include the in-flight scheduler because a failed CLI response can
            # follow a server-side state change.
            attempted.append(scheduler)
            _scheduler_mutation(repo_root, "resume", scheduler)
        preflight_scheduler_contracts(repo_root, expected_state="ENABLED")
        return
    except Exception as resume_error:
        rollback_failures: list[str] = []
        for scheduler in reversed(attempted):
            try:
                _scheduler_mutation(repo_root, "pause", scheduler)
            except Exception as exc:
                rollback_failures.append(f"pause {scheduler}: {exc}")
        try:
            # This checks all 27, including schedulers not reached by the
            # failed resume loop and any ambiguous in-flight mutation.
            preflight_scheduler_contracts(repo_root, expected_state="PAUSED")
        except Exception as exc:
            rollback_failures.append(f"PAUSED postcondition: {exc}")

        if rollback_failures:
            raise RuntimeError(
                "scheduler resume failed. Rollback could not prove atomic "
                "PAUSED state: " + "; ".join(rollback_failures)
            ) from resume_error
        raise RuntimeError(
            "scheduler resume failed; rollback restored all 27 schedulers "
            "to PAUSED."
        ) from resume_error


def _cleanup_preflight_command(
    cleanup: Path,
    manifests: list[Path],
    confirmations: list[str],
    receipt: Path,
) -> list[str]:
    if len(manifests) != len(confirmations):
        raise RuntimeError("each --manifest requires one paired typed SHA")
    command = [sys.executable, str(cleanup)]
    for manifest, confirmation in zip(manifests, confirmations, strict=True):
        command.extend([
            "--manifest", str(manifest),
            "--confirm-manifest-sha", confirmation,
        ])
    command.extend(["--receipt", str(receipt), "--verify-only"])
    return command


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, action="append", type=Path)
    parser.add_argument(
        "--confirm-manifest-sha", required=True, action="append"
    )
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume after all checks; without this flag the command is a dry run",
    )
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    manifests = [path.resolve() for path in args.manifest]
    receipt = args.receipt.resolve()
    cleanup = repo_root / "scripts" / "cleanup_final_forensic_warehouse.py"

    _run(
        _cleanup_preflight_command(
            cleanup, manifests, args.confirm_manifest_sha, receipt
        ),
        cwd=repo_root,
    )
    verify_receipt_in_pushed_main(repo_root, receipt)
    preflight_scheduler_contracts(repo_root)

    if not args.resume:
        print(
            "PASS: aggregate forensic corpus is absent, the immutable receipt "
            "is pushed, and all 27 scheduler contracts are exactly PAUSED; "
            "no scheduler was resumed."
        )
        return 0
    resume_scheduler_contracts(repo_root)
    print(f"PASS: resumed {len(SCHEDULERS)} production schedulers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
