"""One operator-started, fail-closed weekly vendor acquisition workflow.

The command verifies the saved Fantasy Points and SIS sessions before it
starts any long-running work. Once those checks (or terminal login prompts)
finish, it can be left unattended. The Odds API step executes the deployed
Cloud Run job, so the API key remains in Secret Manager rather than the local
``.env`` file.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Sequence

from ..ingest import fantasy_points_route_weekly
from . import fantasy_points_downloads as fp
from . import fantasy_points_matchups as fp_matchups
from . import sis_downloads as sis


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROJECT = "nfl-predictions-503414"
DEFAULT_REGION = "us-central1"
DEFAULT_FP_PLAN = (
    PROJECT_ROOT
    / "automation"
    / "fantasy_points"
    / "plans"
    / "2026-route-share-weekly-v1.json"
)


def _stamp(now: datetime | None = None) -> str:
    current = now or datetime.now(UTC)
    return current.strftime("%Y%m%dT%H%M%SZ")


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _persist(path: Path, manifest: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        json.dumps(_jsonable(manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _ensure_session(
    name: str,
    verify: Callable[[], None],
    login: Callable[[], None],
) -> None:
    try:
        verify()
        return
    except Exception as exc:
        print(f"{name} saved session needs renewal: {exc}")
    login()
    verify()


def _run_cloud_job(job: str, *, project: str, region: str) -> str:
    command = [
        "gcloud", "run", "jobs", "execute", job,
        "--project", project,
        "--region", region,
        "--wait",
        "--quiet",
        "--format=value(metadata.name)",
    ]
    result = subprocess.run(
        command, check=True, text=True, capture_output=True
    )
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    matches = re.findall(rf"\b{re.escape(job)}-[a-z0-9]+\b", output)
    return matches[-1] if matches else result.stdout.strip()


def run_week(
    *,
    week: int,
    fp_profile_dir: Path,
    sis_profile_dir: Path,
    timeout_seconds: float,
    output_root: Path,
    fp_output_root: Path,
    sis_output_root: Path,
    fp_plan: Path = DEFAULT_FP_PLAN,
    sis_plan: Path | None = None,
    project: str = DEFAULT_PROJECT,
    region: str = DEFAULT_REGION,
    headed: bool = False,
    write_route: bool = True,
    capture_matchups: bool = True,
    ingest_odds: bool = True,
    ingest_props: bool = False,
    login_if_needed: bool = True,
    now: datetime | None = None,
) -> Path:
    """Run all approved target-week acquisition steps and return its manifest."""
    if not 1 <= week <= 18:
        raise ValueError("target week must be within 1..18")
    if week >= 2:
        _, fp_specs = fp.load_plan(fp_plan)
        fp.select_target_week(fp_specs, week)
    if sis_plan is not None:
        sis.load_plan(sis_plan)
        sis.plan_request_ceiling(sis_plan)
    run_id = f"{_stamp(now)}__season-2026-week-{week:02d}"
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = run_dir / "manifest.json"
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "season": 2026,
        "target_week": week,
        "started_at_utc": (now or datetime.now(UTC)).isoformat(),
        "project": project,
        "region": region,
        "configuration": {
            "fantasy_points_plan": str(fp_plan) if week >= 2 else None,
            "sis_plan": str(sis_plan) if sis_plan is not None else None,
            "write_route": bool(write_route),
            "capture_matchups": bool(capture_matchups),
            "ingest_odds": bool(ingest_odds),
            "ingest_props": bool(ingest_props),
        },
        "steps": [],
        "status": "running",
    }
    _persist(manifest_path, manifest)

    def step(name: str, action: Callable[[], Any]) -> Any:
        record: dict[str, Any] = {
            "name": name,
            "status": "running",
            "started_at_utc": datetime.now(UTC).isoformat(),
        }
        manifest["steps"].append(record)
        _persist(manifest_path, manifest)
        try:
            result = action()
        except Exception as exc:
            record.update({
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "finished_at_utc": datetime.now(UTC).isoformat(),
            })
            manifest["status"] = "failed"
            _persist(manifest_path, manifest)
            raise
        record.update({
            "status": "complete",
            "result": _jsonable(result),
            "finished_at_utc": datetime.now(UTC).isoformat(),
        })
        _persist(manifest_path, manifest)
        return result

    needs_fp = capture_matchups or week >= 2
    if needs_fp:
        if login_if_needed:
            step(
                "fantasy-points-session",
                lambda: _ensure_session(
                    "Fantasy Points",
                    lambda: fp.verify_login(fp_profile_dir, timeout_seconds),
                    lambda: fp.interactive_login(
                        fp_profile_dir, timeout_seconds, terminal_credentials=True
                    ),
                ),
            )
        else:
            step(
                "fantasy-points-session",
                lambda: fp.verify_login(fp_profile_dir, timeout_seconds),
            )
    if login_if_needed:
        step(
            "sis-session",
            lambda: _ensure_session(
                "SIS",
                lambda: sis.verify_login(sis_profile_dir, timeout_seconds),
                lambda: sis.interactive_login(
                    sis_profile_dir, timeout_seconds, terminal_credentials=True
                ),
            ),
        )
    else:
        step(
            "sis-session",
            lambda: sis.verify_login(sis_profile_dir, timeout_seconds),
        )

    if ingest_odds:
        step(
            "odds-api-game-lines",
            lambda: _run_cloud_job("ingest-odds", project=project, region=region),
        )
    if ingest_props:
        step(
            "odds-api-player-props",
            lambda: _run_cloud_job("ingest-props", project=project, region=region),
        )

    fp_manifest: Path | None = None
    if week >= 2:
        fp_manifest = step(
            "fantasy-points-route-download",
            lambda: fp.run_downloads(
                fp_plan,
                fp_output_root,
                fp_profile_dir,
                headless=not headed,
                timeout_seconds=timeout_seconds,
                target_week=week,
            ),
        )
    if capture_matchups:
        step(
            "fantasy-points-live-matchups",
            lambda: fp_matchups.run(
                season=2026,
                week=week,
                output_root=fp_output_root,
                profile_dir=fp_profile_dir,
                headless=not headed,
                timeout_seconds=timeout_seconds,
                archive=True,
            ),
        )
    if sis_plan is not None:
        step(
            "sis-approved-plan",
            lambda: sis.run_plan(
                sis_profile_dir,
                timeout_seconds,
                sis_output_root / run_id,
                sis_plan,
            ),
        )
    if fp_manifest is not None:
        step(
            "fantasy-points-route-import",
            lambda: fantasy_points_route_weekly.run(
                fp_manifest.parent,
                target_week=week,
                write=write_route,
            ),
        )

    manifest["status"] = "complete"
    manifest["finished_at_utc"] = datetime.now(UTC).isoformat()
    _persist(manifest_path, manifest)
    return manifest_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfl-weekly-data",
        description="Verify paid sessions, then run approved weekly data acquisition",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--fp-profile-dir", type=Path, default=fp.default_profile_dir())
    parser.add_argument("--sis-profile-dir", type=Path, default=sis.default_profile_dir())
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("verify-login", help="verify both saved vendor sessions")
    login = subparsers.add_parser("login", help="renew both vendor sessions in sequence")
    login.add_argument("--terminal-credentials", action="store_true")
    run = subparsers.add_parser("run", help="run the target-week acquisition workflow")
    run.add_argument("--week", type=int, required=True)
    run.add_argument("--fp-plan", type=Path, default=DEFAULT_FP_PLAN)
    run.add_argument("--sis-plan", type=Path)
    run.add_argument("--project", default=DEFAULT_PROJECT)
    run.add_argument("--region", default=DEFAULT_REGION)
    run.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "weekly-data-runs")
    run.add_argument(
        "--fp-output-root", type=Path,
        default=PROJECT_ROOT / "fantasy-points" / "automated",
    )
    run.add_argument(
        "--sis-output-root", type=Path, default=PROJECT_ROOT / "sis" / "weekly"
    )
    run.add_argument("--headed", action="store_true")
    run.add_argument(
        "--audit-only-route",
        action="store_true",
        help="validate Route Share without archiving/appending the guarded import",
    )
    run.add_argument("--include-props", action="store_true")
    run.add_argument("--skip-odds", action="store_true")
    run.add_argument("--skip-matchups", action="store_true")
    run.add_argument("--no-login-if-needed", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "verify-login":
        fp.verify_login(args.fp_profile_dir, args.timeout)
        sis.verify_login(args.sis_profile_dir, args.timeout)
        return 0
    if args.command == "login":
        fp.interactive_login(
            args.fp_profile_dir,
            args.timeout,
            terminal_credentials=args.terminal_credentials,
        )
        sis.interactive_login(
            args.sis_profile_dir,
            args.timeout,
            terminal_credentials=args.terminal_credentials,
        )
        return 0
    manifest = run_week(
        week=args.week,
        fp_profile_dir=args.fp_profile_dir,
        sis_profile_dir=args.sis_profile_dir,
        timeout_seconds=args.timeout,
        output_root=args.output_root,
        fp_output_root=args.fp_output_root,
        sis_output_root=args.sis_output_root,
        fp_plan=args.fp_plan,
        sis_plan=args.sis_plan,
        project=args.project,
        region=args.region,
        headed=args.headed,
        write_route=not args.audit_only_route,
        capture_matchups=not args.skip_matchups,
        ingest_odds=not args.skip_odds,
        ingest_props=args.include_props,
        login_if_needed=not args.no_login_if_needed,
    )
    print(f"Weekly data workflow complete: {manifest}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
