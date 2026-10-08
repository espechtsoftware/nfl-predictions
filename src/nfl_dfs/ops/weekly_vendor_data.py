"""One operator-started, fail-closed weekly vendor acquisition workflow.

The command verifies the saved Fantasy Points and SIS sessions before it
starts any long-running work. Once those checks (or terminal login prompts)
finish, it can be left unattended. The Odds API step executes the deployed
Cloud Run job, so the API key remains in Secret Manager rather than the local
``.env`` file.

SCHEDULE (2026-10-06): start it on WEDNESDAY with the SIS acquisition, and never
before Tuesday 13:00 CT. The Route Share importer refuses a source week whose
file was retrieved before noon CT on the day after that week's last kickoff
(Fantasy Points revises Monday-night numbers on Tuesday morning), so an earlier
run fails the Route page loudly (a true FAIL). Thursday's s-features-route
rebuild reads the week imported here. ``--route-operator-early`` overrides the
gate and is recorded.
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
    sis_receiver_copula_weekly,
    sis_team_context_weekly,
)
from . import fantasy_points_downloads as fp
from . import fantasy_points_matchups as fp_matchups
from . import fantasy_points_projections as fp_projections
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
# 2026-09-28 (operator: "Fix that" -- every paid page, every week): the cumulative (1..W-1) page of every windowed
# family, and Advanced Rushing, from target week 4, raw-captured into *_cumulative tables. They run after every
# established Fantasy Points step and are not fatal: a failure is recorded, the run goes on to SIS, and the paid-page
# gate names the pages and fails the run at the end.
FP_CUMULATIVE_ORDER = (
    "advanced-passing-cumulative", "advanced-rushing-cumulative", "route-shape-cumulative", "coverage-cumulative",
    "qb-shell-cumulative", "alignment-cumulative", "advanced-receiving-cumulative",
)
DEFAULT_FP_CUMULATIVE_PLANS = {
    key: PLANS_DIR / f"{fantasy_points_weekly_2026.FAMILIES[key].plan_name}.json" for key in FP_CUMULATIVE_ORDER
}
SIS_PASS_TAIL_VIEWS = (
    ("pass-defense-totals", "all"), ("pass-defense-value", "all"), ("pass-rush-totals", "all"),
    ("pass-defense-totals", "wide"), ("pass-defense-totals", "slot"),
)
# 2026-09-28 (production, Vendor item B): the frozen SIS receiver-copula weekly protocol, wide + slot of week W-1.
# The runner declares it from target week 4 (the first Wednesday run after the build); target weeks 2-3 (source weeks
# 1-2) are one-time backfills with `sis-download receiver-copula-weekly`, not runner pages.
SIS_RECEIVER_COPULA_FIRST_WEEK = 4
PAID_PAGE_GATE = "paid-page-completeness"
# The Fantasy Points projection tables captured every week (fantasy_points_projections' CLI default). `betting` is left
# out: on the operator's plan it is a 3-row preview without the In-Season Betting add-on, below its 10-row floor.
FP_PROJECTION_TABLES = ("dfs", "weekly", "rankings-weekly", "rankings-ros")


SIS_PLANS_DIR = PROJECT_ROOT / "automation" / "sis" / "plans"


def sis_team_context_plan(week: int) -> Path:
    """The tracked in-season SIS team-context plan for the completed week W-1 (one plan per week)."""
    return SIS_PLANS_DIR / f"team-context-2026-w{int(week) - 1:02d}.json"


def _is_team_context_plan(plan: Path | None) -> bool:
    return plan is not None and plan.stem.startswith("team-context-2026-")


def _weeks(first: int, last: int) -> str:
    return f"week {last:02d}" if first == last else f"weeks {first:02d}-{last:02d}"


def paid_pages(week: int, *, sis_plan: Path | None, stage_matchups: bool = True) -> list[dict[str, Any]]:
    """Declare every paid Fantasy Points and SIS page target week W must capture (production's order D, 2026-09-28).

    Each page names the steps that download, validate and load it; it counts as captured only when all of them
    completed. `group` is what a --skip flag can leave out. Without an explicit SIS plan the tracked team-context
    plan of the completed week declares the SIS pages (a missing plan is itself a page that cannot be captured).
    """
    pages: list[dict[str, Any]] = []

    def add(group: str, labels: Sequence[str], steps: Sequence[str]) -> None:
        pages.extend({"page": label, "group": group, "steps": list(steps)} for label in labels)

    if week >= 2:
        add("route-share", [f"fantasy-points route-share {_weeks(week - 1, week - 1)}"],
            ("fantasy-points-route-download", "fantasy-points-route-import"))
        add("defense-proe", [f"fantasy-points offense-proe/Defense {_weeks(week - 1, week - 1)}"],
            ("fantasy-points-defense-proe-download", "fantasy-points-defense-proe-import"))
    add("matchups", [f"fantasy-points {m.key} (live, Week {week})" for m in fp_matchups.MATCHUPS],
        ("fantasy-points-live-matchups", *(("fantasy-points-matchups-stage",) if stage_matchups else ())))
    if week >= 5:
        add("alignment", [f"fantasy-points alignment: receiving-separation-by-alignment/Player "
                          f"{_weeks(week - 4, week - 1)}"],
            ("fantasy-points-alignment-download", "fantasy-points-alignment-import"))
    # 2026-10-05 (reviewer; operator's every-paid-page rule): the DFS-tier projection pages (since 10-02) were captured by
    # hand for Week 4 only. Each table is its own page and its own step; FP serves the current week only, so a week the
    # run misses is lost for good.
    for table in FP_PROJECTION_TABLES:
        add("fp-projections", [f"fantasy-points projections/{table} (live, Week {week})"],
            (f"fantasy-points-projections-{table}",))
    for group, keys in (("fp-families", FP_FAMILY_ORDER if week >= 5 else ()), ("fp-cumulative", FP_CUMULATIVE_ORDER)):
        for key in keys:
            add(group, [f"fantasy-points {key}: {w.report}/{w.context} "
                        f"{_weeks(1 if w.kind == 'cumulative' else week - 4, week - 1)}"
                        for w in fantasy_points_weekly_2026.FAMILIES[key].windows if week >= w.first_target_week],
                (f"fantasy-points-{key}-download", f"fantasy-points-{key}-import"))
    plan = sis_plan if sis_plan is not None else (sis_team_context_plan(week) if week >= 2 else None)
    if plan is not None and plan.is_file():
        team_context = _is_team_context_plan(plan)
        add("sis-team-context" if team_context else "sis-plan",
            [f"sis {spec.report} {_weeks(spec.start_week, spec.end_week)}" for spec in sis.load_plan(plan)],
            ("sis-approved-plan", *(("sis-team-context-import",) if team_context else ())))
    elif plan is not None:
        add("sis-team-context", [f"sis team context {_weeks(week - 1, week - 1)} (no tracked plan {plan.name})"],
            ("sis-team-context-import",))
    if week >= 5:
        first = 1 if week == 5 else week - 1          # as run_pass_tail_weekly_acquisition
        add("sis-pass-tail", [f"sis pass-tail {report}/{view} {_weeks(first, week - 1)}"
                              for report, view in SIS_PASS_TAIL_VIEWS],
            ("sis-pass-tail-download", "sis-pass-tail-import"))
    if week >= SIS_RECEIVER_COPULA_FIRST_WEEK:
        add("sis-receiver-copula", [f"sis receiver-copula wr-cb pass-defense-totals/{alignment} "
                                    f"{_weeks(week - 1, week - 1)}" for alignment, _ in sis.RECEIVER_COPULA_ALIGNMENTS],
            ("sis-receiver-copula-download", "sis-receiver-copula-import"))
    return pages


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
    fp_cumulative_plans: dict[str, Path] | None = None,
    sis_plan: Path | None = None,
    project: str = DEFAULT_PROJECT,
    region: str = DEFAULT_REGION,
    headed: bool = False,
    write_route: bool = True,
    route_operator_early: bool = False,
    write_alignment: bool = True,
    collect_fp_families: bool = True,
    write_fp_families: bool = True,
    capture_matchups: bool = True,
    capture_fp_projections: bool = True,
    stage_matchups: bool = True,
    write_matchups: bool = True,
    capture_sis_pass_tail: bool = True,
    capture_sis_receiver_copula: bool = True,
    write_sis_receiver_copula: bool = True,
    ingest_odds: bool = True,
    ingest_props: bool = False,
    sis_team_context: bool = True,
    write_sis_team_context: bool = True,
    skip_fantasy_points: bool = False,
    login_if_needed: bool = True,
    now: datetime | None = None,
) -> Path:
    """Run all approved target-week acquisition steps and return its manifest."""
    if not 1 <= week <= 18:
        raise ValueError("target week must be within 1..18")
    # --skip-fantasy-points: the SIS-only re-run after an SIS failure (the Fantasy Points files were already captured)
    fp_on = not skip_fantasy_points
    if fp_on and week >= 2:
        _, fp_specs = fp.load_plan(fp_plan)
        fp.select_target_week(fp_specs, week)
    if fp_on and week >= 5:
        _, alignment_specs = fp.load_plan(fp_alignment_plan)
        fp.select_target_week(alignment_specs, week)
    family_plans = {**DEFAULT_FP_FAMILY_PLANS, **(fp_family_plans or {})}
    cumulative_plans = {**DEFAULT_FP_CUMULATIVE_PLANS, **(fp_cumulative_plans or {})}
    cumulative_keys = [key for key in FP_CUMULATIVE_ORDER
                       if week >= fantasy_points_weekly_2026.FAMILIES[key].first_target_week]
    # 2026-09-23 (operator: SIS is paid for and collected EVERY week; no silent fallbacks): one run captures AND loads
    # the SIS team context of the completed week. Without an explicit --sis-plan the tracked plan for W-1 is used; a
    # missing plan fails the run loudly at the SIS stage (after every Fantasy Points step, so nothing FP is lost).
    sis_team_context_missing: str | None = None
    if sis_plan is None and sis_team_context and week >= 2:
        default_plan = sis_team_context_plan(week)
        if default_plan.is_file():
            sis_plan = default_plan
        else:
            sis_team_context_missing = (
                f"no tracked SIS team-context plan {default_plan.relative_to(PROJECT_ROOT)} for completed week "
                f"{week - 1}; add it (copy the previous week's plan and change the week), then re-run with "
                f"--skip-fantasy-points"
            )
    if fp_on and collect_fp_families:
        # every plan this run will use is validated before any session or download
        if week >= 2:
            fp.select_target_week(fp.load_plan(fp_proe_plan)[1], week)
        if week >= 5:
            for key in FP_FAMILY_ORDER:
                fp.select_target_week(fp.load_plan(family_plans[key])[1], week)
        for key in cumulative_keys:
            fp.select_target_week(fp.load_plan(cumulative_plans[key])[1], week)
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
            "route_operator_early": bool(route_operator_early),
            "write_alignment": bool(write_alignment),
            "fantasy_points_defense_proe_plan": (
                str(fp_proe_plan) if collect_fp_families and week >= 2 else None
            ),
            "fantasy_points_family_plans": (
                {key: str(family_plans[key]) for key in FP_FAMILY_ORDER}
                if collect_fp_families and week >= 5 else None
            ),
            "fantasy_points_cumulative_plans": (
                {key: str(cumulative_plans[key]) for key in cumulative_keys}
                if collect_fp_families and cumulative_keys else None
            ),
            "collect_fp_families": bool(collect_fp_families),
            "write_fp_families": bool(write_fp_families),
            "capture_matchups": bool(capture_matchups),
            "stage_matchups": bool(capture_matchups and stage_matchups),
            "write_matchups": bool(write_matchups),
            "capture_sis_pass_tail": bool(capture_sis_pass_tail),
            "capture_sis_receiver_copula": bool(capture_sis_receiver_copula),
            "write_sis_receiver_copula": bool(write_sis_receiver_copula),
            "ingest_odds": bool(ingest_odds),
            "ingest_props": bool(ingest_props),
        },
        "steps": [],
        "status": "running",
    }
    # D. The paid-page gate (production's order, 2026-09-28): every page declared for this week ends the run either
    # captured, left out by a named --skip flag, or FAILED and named in the operator's one line -- never an absent row.
    fp_skip = None if fp_on else "--skip-fantasy-points"
    families_skip = fp_skip or (None if collect_fp_families else "--skip-fp-families")
    skip_flags = {
        "route-share": fp_skip, "alignment": fp_skip, "defense-proe": families_skip,
        "fp-families": families_skip, "fp-cumulative": families_skip,
        "fp-projections": fp_skip or (None if capture_fp_projections else "--skip-fp-projections"),
        "matchups": fp_skip or (None if capture_matchups else "--skip-matchups"),
        "sis-team-context": None if sis_plan is not None or sis_team_context else "--skip-sis-team-context",
        "sis-plan": None, "sis-pass-tail": None if capture_sis_pass_tail else "--skip-sis-pass-tail",
        "sis-receiver-copula": None if capture_sis_receiver_copula else "--skip-sis-receiver-copula",
    }
    audit_only = {
        "route-share": not write_route, "alignment": not write_alignment, "defense-proe": not write_fp_families,
        "fp-families": not write_fp_families, "fp-cumulative": not write_fp_families,
        "matchups": not write_matchups, "sis-team-context": not write_sis_team_context,
        "sis-receiver-copula": not write_sis_receiver_copula,
    }
    manifest["paid_pages"] = {"pages": [
        {**page, "skipped_by": skip_flags[page["group"]], "audit_only": audit_only.get(page["group"], False),
         "status": "pending"}
        for page in paid_pages(week, sis_plan=sis_plan, stage_matchups=stage_matchups)
    ]}
    _persist(manifest_path, manifest)

    def paid_page_verdict() -> list[dict[str, Any]]:
        """Score every declared page against the recorded steps; persist and print the operator's one line."""
        latest = {record["name"]: record for record in manifest["steps"]}
        section = manifest["paid_pages"]
        failed: list[dict[str, Any]] = []
        for page in section["pages"]:
            records = [latest.get(name) for name in page["steps"]]
            if page["skipped_by"]:
                page["status"] = "skipped"
            elif all(record is not None and record["status"] == "complete" for record in records):
                page["status"] = "captured"
            else:
                broken = next((r for r in records if r is not None and r["status"] != "complete"), None)
                page["status"] = "FAILED"
                page["reason"] = (f"{broken['name']} {broken['status']}: {broken.get('error', '')}" if broken
                                  else f"{page['steps'][records.index(None)]} never ran")
                failed.append(page)
        expected = [page for page in section["pages"] if not page["skipped_by"]]
        flags = sorted({page["skipped_by"] for page in section["pages"] if page["skipped_by"]})
        audited = sorted({page["group"] for page in expected if page["audit_only"]})
        line = f"PAID PAGES: {len(expected) - len(failed)} of {len(expected)} paid pages captured for Week {week}"
        if flags:
            line += f" ({len(section['pages']) - len(expected)} skipped by {', '.join(flags)})"
        if audited:
            line += f" (audit-only, not archived or appended: {', '.join(audited)})"
        if failed:
            line += "; NOT CAPTURED: " + "; ".join(f"{page['page']} [{page['reason']}]" for page in failed)
        section.update(expected=len(expected), captured=len(expected) - len(failed), line=line)
        _persist(manifest_path, manifest)
        print(line, flush=True)
        return failed

    def step(name: str, action: Callable[[], Any], *, fatal: bool = True) -> Any:
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
            if not fatal:
                # an unproven page: recorded here, named by the paid-page gate at the end; the run goes on
                _persist(manifest_path, manifest)
                print(f"{name} FAILED ({type(exc).__name__}: {exc}); continuing, the paid-page gate names its pages",
                      flush=True)
                return None
            manifest["status"] = "failed"
            _persist(manifest_path, manifest)
            if name != PAID_PAGE_GATE:
                try:
                    paid_page_verdict()          # names every page this failure leaves uncaptured
                except Exception as verdict_exc:  # never mask the step's own failure
                    print(f"paid-page verdict unavailable: {verdict_exc}", flush=True)
            raise
        record.update({
            "status": "complete",
            "result": _jsonable(result),
            "finished_at_utc": datetime.now(UTC).isoformat(),
        })
        _persist(manifest_path, manifest)
        return result

    needs_fp = fp_on and (capture_matchups or week >= 2)
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
    # SIS session (defect 28, then the operator's 2026-09-23 rule). An attended run renews the session up front as
    # before. An unattended run verifies it IMMEDIATELY BEFORE the first SIS step -- after every Fantasy Points step --
    # so an expired session never loses the FP capture, yet the run still fails closed (non-zero exit) with the
    # renewal command; the SIS-only re-run is `--skip-fantasy-points`. With no SIS step at all the manifest records
    # that the session was not required.
    capture_copula = week >= SIS_RECEIVER_COPULA_FIRST_WEEK and capture_sis_receiver_copula
    sis_steps = (sis_plan is not None or sis_team_context_missing is not None or (week >= 5 and capture_sis_pass_tail)
                 or capture_copula)
    sis_rerun = (f"nfl-weekly-data run --week {week} --skip-fantasy-points --skip-odds --skip-matchups "
                 "--no-login-if-needed")

    def _require_sis_session() -> dict[str, Any]:
        try:
            sis.verify_login(sis_profile_dir, timeout_seconds)
        except Exception as exc:
            raise RuntimeError(
                f"SIS saved session is not usable ({exc}). The Fantasy Points steps of this run are complete. "
                "Renew the session with `sis-download login --terminal-credentials --fresh`, then run "
                f"`{sis_rerun}`"
            ) from exc
        return {"status": "verified", "checked": "immediately before the SIS steps"}

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
    elif not sis_steps:
        # unattended run without an SIS step: recorded, never silently skipped
        step(
            "sis-session",
            lambda: {"status": "not-required", "reason": "no SIS step in this invocation"},
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

    if fp_on and week >= 2:
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
        # NOT fatal (2026-10-06): a vendor revision of stored rows or a file retrieved before the week's settle time is
        # printed loudly by the importer, recorded here, and named by the paid-page gate at the end; the run goes on so
        # the other paid pages (PROE, the families, SIS) are still captured. Nothing is ever deleted automatically.
        step(
            "fantasy-points-route-import",
            lambda: fantasy_points_route_weekly.run(
                fp_manifest.parent,
                target_week=week,
                write=write_route,
                operator_early=route_operator_early,
            ),
            fatal=False,
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
    if fp_on and capture_matchups:
        # not fatal (2026-09-29 sweep): Week 4 is the first week the matchups must be current-season; a vendor still
        # serving last season would otherwise stop the run before the cumulative and SIS pages. The gate names it.
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
            fatal=False,
        )
        if stage_matchups and matchups_manifest is not None:
            step(
                "fantasy-points-matchups-stage",
                lambda: fantasy_points_matchups_weekly.run(
                    Path(matchups_manifest).parent,
                    target_week=week,
                    write=write_matchups,
                ),
                fatal=False,
            )
    if fp_on and week >= 5:
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
        # NOT fatal (2026-10-08, the Route import's 10-06 rule): on 10-08 FP revised weeks 1-4 of the alignment page
        # after Wednesday's capture, the append-once check (correctly) refused it, and -- fatal then -- it stopped the run
        # before the FP projection pages. A refusal is recorded here and named by the paid-page gate; the run goes on.
        step(
            "fantasy-points-alignment-import",
            lambda: fantasy_points_alignment_weekly.run(
                fp_alignment_manifest.parent,
                target_week=week,
                write=write_alignment,
            ),
            fatal=False,
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
    if fp_on and collect_fp_families:
        for key in cumulative_keys:
            cumulative_manifest = step(
                f"fantasy-points-{key}-download",
                lambda key=key: fp.run_downloads(
                    cumulative_plans[key],
                    fp_output_root,
                    fp_profile_dir,
                    headless=not headed,
                    timeout_seconds=timeout_seconds,
                    target_week=week,
                ),
                fatal=False,
            )
            if cumulative_manifest is not None:
                step(
                    f"fantasy-points-{key}-import",
                    lambda key=key, run_dir=Path(cumulative_manifest).parent: fantasy_points_weekly_2026.run(
                        key, run_dir, target_week=week, write=write_fp_families,
                    ),
                    fatal=False,
                )
    if fp_on and capture_fp_projections:
        # not fatal, like the cumulative pages: a failure is recorded and the paid-page gate names the table's page
        for table in FP_PROJECTION_TABLES:
            step(
                f"fantasy-points-projections-{table}",
                lambda table=table: fp_projections.collect(
                    fp_profile_dir, timeout_seconds, season=2026, week=week, which=[table],
                    output_root=fp_profile_dir.parent / "fantasy-points-projections",
                ),
                fatal=False,
            )
    if sis_steps and not login_if_needed:
        step("sis-session", _require_sis_session)
    if sis_team_context_missing is not None:
        def _missing_plan() -> None:
            raise FileNotFoundError(sis_team_context_missing)

        step("sis-team-context-plan", _missing_plan)
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
    if capture_copula:
        # not fatal, like the cumulative pages: a failure is recorded and the paid-page gate names both pages
        copula_dir = sis_output_root / run_id / "receiver-copula"
        acquired = step(
            "sis-receiver-copula-download",
            lambda: sis.run_receiver_copula_weekly_acquisition(
                sis_profile_dir, timeout_seconds, copula_dir, target_week=week,
            ),
            fatal=False,
        )
        if acquired is not None:
            step(
                "sis-receiver-copula-import",
                lambda: sis_receiver_copula_weekly.run(
                    copula_dir, target_week=week, write=write_sis_receiver_copula,
                ),
                fatal=False,
            )

    def _paid_page_gate() -> dict[str, int]:
        if paid_page_verdict():
            raise RuntimeError(manifest["paid_pages"]["line"])
        return {key: manifest["paid_pages"][key] for key in ("expected", "captured")}

    step(PAID_PAGE_GATE, _paid_page_gate)
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
        "--route-operator-early",
        action="store_true",
        help="import a Route Share source week retrieved before its settle time (noon CT the day after its last kickoff); recorded",
    )
    run.add_argument(
        "--audit-only-alignment",
        action="store_true",
        help="validate alignment without archiving/appending the guarded import",
    )
    run.add_argument(
        "--audit-only-fp-families",
        action="store_true",
        help="validate Defense PROE, the last-four families and the cumulative pages without archiving/appending",
    )
    run.add_argument(
        "--skip-fp-families",
        action="store_true",
        help="do not download Defense PROE, the last-four families or the cumulative pages",
    )
    run.add_argument(
        "--audit-only-matchups",
        action="store_true",
        help="validate the matchup staging load without appending",
    )
    run.add_argument("--skip-matchup-stage", action="store_true")
    run.add_argument(
        "--skip-fantasy-points",
        action="store_true",
        help="skip every Fantasy Points step (the SIS-only re-run after an SIS session failure)",
    )
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
    run.add_argument(
        "--skip-fp-projections",
        action="store_true",
        help="do not capture the Fantasy Points projection tables (dfs, weekly, rankings) of the current week",
    )
    run.add_argument("--skip-sis-pass-tail", action="store_true")
    run.add_argument(
        "--skip-sis-receiver-copula",
        action="store_true",
        help="do not download the SIS receiver-copula wide/slot pages of week W-1",
    )
    run.add_argument(
        "--audit-only-sis-receiver-copula",
        action="store_true",
        help="capture the SIS receiver-copula pages but validate their import without archiving/appending",
    )
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
        route_operator_early=args.route_operator_early,
        write_alignment=not args.audit_only_alignment,
        collect_fp_families=not args.skip_fp_families,
        write_fp_families=not args.audit_only_fp_families,
        capture_matchups=not args.skip_matchups,
        capture_fp_projections=not args.skip_fp_projections,
        stage_matchups=not args.skip_matchup_stage,
        write_matchups=not args.audit_only_matchups,
        sis_team_context=not args.skip_sis_team_context,
        skip_fantasy_points=args.skip_fantasy_points,
        write_sis_team_context=not args.audit_only_sis_team_context,
        capture_sis_pass_tail=not args.skip_sis_pass_tail,
        capture_sis_receiver_copula=not args.skip_sis_receiver_copula,
        write_sis_receiver_copula=not args.audit_only_sis_receiver_copula,
        ingest_odds=not args.skip_odds,
        ingest_props=args.include_props,
        login_if_needed=not args.no_login_if_needed,
    )
    print(f"Weekly data workflow complete: {manifest}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
