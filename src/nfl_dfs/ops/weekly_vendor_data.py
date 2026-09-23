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

from ..ingest import (
    fantasy_points_alignment_weekly,
    fantasy_points_defense_proe_weekly,
    fantasy_points_matchups_weekly,
    fantasy_points_route_weekly,
    fantasy_points_weekly_2026,
    sis_pass_tail_weekly,
    sis_team_context_weekly,
)
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
DEFAULT_FP_ALIGNMENT_PLAN = (
    PROJECT_ROOT
    / "automation"
    / "fantasy_points"
    / "plans"
    / "2026-alignment-last-four-weekly-v1.json"
)


PLANS_DIR = PROJECT_ROOT / "automation" / "fantasy_points" / "plans"
# 2026-09-23 (operator directive): every paid Fantasy Points family with history is collected every week.
# Defense PROE from target week 2 (source week W-1); the five last-four families from target week 5, in this order
# (qb-shell parses with the same week's coverage run, so coverage comes first).
DEFAULT_FP_PROE_PLAN = PLANS_DIR / f"{fantasy_points_defense_proe_weekly.PLAN_NAME}.json"
FP_FAMILY_ORDER = ("advanced-passing", "route-shape", "coverage", "qb-shell", "advanced-receiving")
DEFAULT_FP_FAMILY_PLANS = {
    key: PLANS_DIR / f"{fantasy_points_weekly_2026.FAMILIES[key].plan_name}.json" for key in FP_FAMILY_ORDER
}


SIS_PLANS_DIR = PROJECT_ROOT / "automation" / "sis" / "plans"


def sis_team_context_plan(week: int) -> Path:
    """The tracked in-season SIS team-context plan for the completed week W-1 (one plan per week)."""
    return SIS_PLANS_DIR / f"team-context-2026-w{int(week) - 1:02d}.json"


def _is_team_context_plan(plan: Path | None) -> bool:
    return plan is not None and plan.stem.startswith("team-context-2026-")


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
    fp_alignment_plan: Path = DEFAULT_FP_ALIGNMENT_PLAN,
    fp_proe_plan: Path = DEFAULT_FP_PROE_PLAN,
    fp_family_plans: dict[str, Path] | None = None,
    sis_plan: Path | None = None,
    project: str = DEFAULT_PROJECT,
    region: str = DEFAULT_REGION,
    headed: bool = False,
    write_route: bool = True,
    write_alignment: bool = True,
    collect_fp_families: bool = True,
    write_fp_families: bool = True,
    capture_matchups: bool = True,
    stage_matchups: bool = True,
    write_matchups: bool = True,
    capture_sis_pass_tail: bool = True,
    ingest_odds: bool = True,
    ingest_props: bool = False,
    sis_team_context: bool = True,
    write_sis_team_context: bool = True,
    login_if_needed: bool = True,
    now: datetime | None = None,
) -> Path:
    """Run all approved target-week acquisition steps and return its manifest."""
    if not 1 <= week <= 18:
        raise ValueError("target week must be within 1..18")
    if week >= 2:
        _, fp_specs = fp.load_plan(fp_plan)
        fp.select_target_week(fp_specs, week)
    if week >= 5:
        _, alignment_specs = fp.load_plan(fp_alignment_plan)
        fp.select_target_week(alignment_specs, week)
    family_plans = {**DEFAULT_FP_FAMILY_PLANS, **(fp_family_plans or {})}
    # 2026-09-23: one run captures AND loads the SIS team context of the completed week. Without an explicit
    # --sis-plan the tracked plan for W-1 is used when it exists; when it does not, the manifest says so (never silent).
    sis_team_context_missing: str | None = None
    sis_plan_is_default = False
    if sis_plan is None and sis_team_context and week >= 2:
        default_plan = sis_team_context_plan(week)
        if default_plan.is_file():
            sis_plan = default_plan
            sis_plan_is_default = True
        else:
            sis_team_context_missing = f"no tracked plan {default_plan.name}; author it to load week {week - 1}"
    if collect_fp_families:
        # every plan this run will use is validated before any session or download
        if week >= 2:
            fp.select_target_week(fp.load_plan(fp_proe_plan)[1], week)
        if week >= 5:
            for key in FP_FAMILY_ORDER:
                fp.select_target_week(fp.load_plan(family_plans[key])[1], week)
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
            "fantasy_points_alignment_plan": (
                str(fp_alignment_plan) if week >= 5 else None
            ),
            "sis_plan": str(sis_plan) if sis_plan is not None else None,
            "sis_team_context_import": bool(_is_team_context_plan(sis_plan)),
            "write_sis_team_context": bool(write_sis_team_context),
            "write_route": bool(write_route),
            "write_alignment": bool(write_alignment),
            "fantasy_points_defense_proe_plan": (
                str(fp_proe_plan) if collect_fp_families and week >= 2 else None
            ),
            "fantasy_points_family_plans": (
                {key: str(family_plans[key]) for key in FP_FAMILY_ORDER}
                if collect_fp_families and week >= 5 else None
            ),
            "collect_fp_families": bool(collect_fp_families),
            "write_fp_families": bool(write_fp_families),
            "capture_matchups": bool(capture_matchups),
            "stage_matchups": bool(capture_matchups and stage_matchups),
            "write_matchups": bool(write_matchups),
            "capture_sis_pass_tail": bool(capture_sis_pass_tail),
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
    # 2026-09-21 (Week-2 post-mortem; defect 28): the SIS session is required only when an SIS step will run in this
    # invocation (an approved plan, or the pass-tail acquisition from week 5). Requiring it unconditionally lost the
    # whole Week-2 Fantasy Points capture to an expired SIS session on 2026-09-17. When no SIS step runs, the manifest
    # records that the session was not required (never a silent skip); when one runs, an expired session still stops
    # the run before any step.
    # The default team-context plan never costs the Fantasy Points capture (defect 28): when it is the only SIS step,
    # an expired session skips the team-context import (recorded) instead of stopping the run. An explicit --sis-plan
    # or the week-5 pass-tail acquisition still requires the session and fails closed.
    needs_sis = (sis_plan is not None and not sis_plan_is_default) or (week >= 5 and capture_sis_pass_tail)
    optional_sis = sis_plan_is_default and not needs_sis

    def _verify_optional_sis() -> dict[str, Any]:
        nonlocal sis_plan, sis_team_context_missing
        try:
            sis.verify_login(sis_profile_dir, timeout_seconds)
        except Exception as exc:
            sis_team_context_missing = f"SIS session unavailable ({exc}); team-context capture skipped"
            sis_plan = None
            return {"status": "expired-optional", "reason": str(exc),
                    "effect": "the default SIS team-context capture is skipped; every other step proceeds"}
        return {"status": "verified", "required_by": "default SIS team-context plan"}

    if login_if_needed:
        # attended run: the operator is at the terminal, so the SIS session is renewed every week as before
        step(
            "sis-session",
            lambda: (
                sis.interactive_login(
                    sis_profile_dir,
                    timeout_seconds,
                    terminal_credentials=True,
                    force_fresh=True,
                ),
                sis.verify_login(sis_profile_dir, timeout_seconds),
            ),
        )
    elif needs_sis:
        step(
            "sis-session",
            lambda: sis.verify_login(sis_profile_dir, timeout_seconds),
        )
    elif optional_sis:
        step("sis-session", _verify_optional_sis)
    else:
        # unattended run without an SIS step: recorded, never silently skipped
        step(
            "sis-session",
            lambda: {"status": "not-required", "reason": "no SIS step in this invocation (no approved plan; pass-tail acquisition starts at week 5)"},
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
        step(
            "fantasy-points-route-import",
            lambda: fantasy_points_route_weekly.run(
                fp_manifest.parent,
                target_week=week,
                write=write_route,
            ),
        )
        if collect_fp_families:
            proe_manifest = step(
                "fantasy-points-defense-proe-download",
                lambda: fp.run_downloads(
                    fp_proe_plan,
                    fp_output_root,
                    fp_profile_dir,
                    headless=not headed,
                    timeout_seconds=timeout_seconds,
                    target_week=week,
                ),
            )
            step(
                "fantasy-points-defense-proe-import",
                lambda: fantasy_points_defense_proe_weekly.run(
                    proe_manifest.parent,
                    target_week=week,
                    write=write_fp_families,
                ),
            )
    if capture_matchups:
        matchups_manifest = step(
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
        if stage_matchups:
            step(
                "fantasy-points-matchups-stage",
                lambda: fantasy_points_matchups_weekly.run(
                    Path(matchups_manifest).parent,
                    target_week=week,
                    write=write_matchups,
                ),
            )
    if week >= 5:
        fp_alignment_manifest = step(
            "fantasy-points-alignment-download",
            lambda: fp.run_downloads(
                fp_alignment_plan,
                fp_output_root,
                fp_profile_dir,
                headless=not headed,
                timeout_seconds=timeout_seconds,
                target_week=week,
            ),
        )
        step(
            "fantasy-points-alignment-import",
            lambda: fantasy_points_alignment_weekly.run(
                fp_alignment_manifest.parent,
                target_week=week,
                write=write_alignment,
            ),
        )
        if collect_fp_families:
            family_dirs: dict[str, Path] = {}
            for key in FP_FAMILY_ORDER:
                family_manifest = step(
                    f"fantasy-points-{key}-download",
                    lambda key=key: fp.run_downloads(
                        family_plans[key],
                        fp_output_root,
                        fp_profile_dir,
                        headless=not headed,
                        timeout_seconds=timeout_seconds,
                        target_week=week,
                    ),
                )
                family_dirs[key] = Path(family_manifest).parent
                step(
                    f"fantasy-points-{key}-import",
                    lambda key=key: fantasy_points_weekly_2026.run(
                        key,
                        family_dirs[key],
                        target_week=week,
                        write=write_fp_families,
                        coverage_dir=family_dirs.get("coverage") if key == "qb-shell" else None,
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
        if _is_team_context_plan(sis_plan):
            step(
                "sis-team-context-import",
                lambda: sis_team_context_weekly.run(
                    sis_output_root / run_id,
                    sis_plan,
                    write=write_sis_team_context,
                ),
            )
    elif sis_team_context_missing is not None:
        step(
            "sis-team-context-import",
            lambda: {"status": "not-available", "reason": sis_team_context_missing},
        )
    if week >= 5 and capture_sis_pass_tail:
        sis_pass_tail_dir = sis_output_root / run_id / "pass-tail"
        step(
            "sis-pass-tail-download",
            lambda: sis.run_pass_tail_weekly_acquisition(
                sis_profile_dir,
                timeout_seconds,
                sis_pass_tail_dir,
                target_week=week,
            ),
        )
        step(
            "sis-pass-tail-import",
            lambda: sis_pass_tail_weekly.run(
                sis_pass_tail_dir,
                target_week=week,
                write=True,
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
    run.add_argument(
        "--fp-alignment-plan", type=Path, default=DEFAULT_FP_ALIGNMENT_PLAN
    )
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
    run.add_argument(
        "--audit-only-alignment",
        action="store_true",
        help="validate alignment without archiving/appending the guarded import",
    )
    run.add_argument(
        "--audit-only-fp-families",
        action="store_true",
        help="validate Defense PROE and the last-four families without archiving/appending",
    )
    run.add_argument(
        "--skip-fp-families",
        action="store_true",
        help="do not download Defense PROE or the last-four families",
    )
    run.add_argument(
        "--audit-only-matchups",
        action="store_true",
        help="validate the matchup staging load without appending",
    )
    run.add_argument("--skip-matchup-stage", action="store_true")
    run.add_argument(
        "--skip-sis-team-context",
        action="store_true",
        help="do not default --sis-plan to the tracked team-context plan for the completed week",
    )
    run.add_argument(
        "--audit-only-sis-team-context",
        action="store_true",
        help="capture the SIS team-context plan but validate its import without appending",
    )
    run.add_argument("--include-props", action="store_true")
    run.add_argument("--skip-odds", action="store_true")
    run.add_argument("--skip-matchups", action="store_true")
    run.add_argument("--skip-sis-pass-tail", action="store_true")
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
            force_fresh=True,
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
        fp_alignment_plan=args.fp_alignment_plan,
        sis_plan=args.sis_plan,
        project=args.project,
        region=args.region,
        headed=args.headed,
        write_route=not args.audit_only_route,
        write_alignment=not args.audit_only_alignment,
        collect_fp_families=not args.skip_fp_families,
        write_fp_families=not args.audit_only_fp_families,
        capture_matchups=not args.skip_matchups,
        stage_matchups=not args.skip_matchup_stage,
        write_matchups=not args.audit_only_matchups,
        sis_team_context=not args.skip_sis_team_context,
        write_sis_team_context=not args.audit_only_sis_team_context,
        capture_sis_pass_tail=not args.skip_sis_pass_tail,
        ingest_odds=not args.skip_odds,
        ingest_props=args.include_props,
        login_if_needed=not args.no_login_if_needed,
    )
    print(f"Weekly data workflow complete: {manifest}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
