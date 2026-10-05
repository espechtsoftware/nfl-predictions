import json

import pytest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from nfl_dfs.ops import weekly_vendor_data as weekly


PROJECTION_CALLS: list = []


@pytest.fixture(autouse=True)
def _stub_fp_projections(monkeypatch):
    """The projection pages drive a real browser; every test stubs the collector and records the tables it asked for."""
    PROJECTION_CALLS.clear()

    def fake_collect(profile_dir, timeout_s, *, season, week, which, output_root):
        PROJECTION_CALLS.append((season, week, tuple(which)))
        return {"tables": {k: {"rows": 1} for k in which}, "failures": {}}

    monkeypatch.setattr(weekly.fp_projections, "collect", fake_collect)


def test_cloud_job_uses_deployed_secret_backed_job(monkeypatch):
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        return SimpleNamespace(
            stdout="ingest-odds-abc12\n", stderr="", returncode=0
        )

    monkeypatch.setattr(weekly.subprocess, "run", fake_run)
    execution = weekly._run_cloud_job(
        "ingest-odds", project="project-id", region="region-id"
    )
    assert execution == "ingest-odds-abc12"
    assert observed["command"] == [
        "gcloud", "run", "jobs", "execute", "ingest-odds",
        "--project", "project-id", "--region", "region-id",
        "--wait", "--quiet", "--format=value(metadata.name)",
    ]
    assert observed["kwargs"]["check"] is True


def test_run_week_preflights_sessions_then_runs_all_selected_steps(
    monkeypatch, tmp_path
):
    events = []
    fp_run = tmp_path / "fp-run"
    fp_run.mkdir()
    fp_manifest = fp_run / "manifest.json"
    fp_manifest.write_text("{}")
    sis_plan = tmp_path / "sis-plan.json"
    sis_plan.write_text("{}")

    monkeypatch.setattr(weekly.fp, "load_plan", lambda *_: ({}, [object()]))
    monkeypatch.setattr(weekly.fp, "select_target_week", lambda specs, _: specs)
    monkeypatch.setattr(weekly.sis, "load_plan", lambda *_: [])
    monkeypatch.setattr(weekly.sis, "plan_request_ceiling", lambda *_: 10)

    monkeypatch.setattr(
        weekly.fp, "verify_login",
        lambda *_: events.append("verify-fp"),
    )
    monkeypatch.setattr(
        weekly.sis, "verify_login",
        lambda *_: events.append("verify-sis"),
    )
    monkeypatch.setattr(
        weekly, "_run_cloud_job",
        lambda job, **_: events.append(job) or f"{job}-exec",
    )
    monkeypatch.setattr(
        weekly.fp, "run_downloads",
        lambda *_args, **_kwargs: events.append("route-download") or fp_manifest,
    )
    monkeypatch.setattr(
        weekly.fantasy_points_route_weekly, "run",
        lambda *_args, **kwargs: events.append(
            f"route-import-{kwargs['write']}"
        ) or {"append_rows": 10},
    )
    monkeypatch.setattr(
        weekly.fp_matchups, "run",
        lambda **_kwargs: events.append("matchups") or Path("matchups/manifest.json"),
    )
    monkeypatch.setattr(
        weekly.fantasy_points_defense_proe_weekly, "run",
        lambda *_args, **kwargs: events.append(f"proe-import-{kwargs['write']}") or {},
    )
    monkeypatch.setattr(
        weekly.fantasy_points_matchups_weekly, "run",
        lambda path, **kwargs: events.append(f"matchups-stage-{path}-{kwargs['write']}") or {},
    )
    monkeypatch.setattr(
        weekly.sis, "run_plan",
        lambda *_args, **_kwargs: events.append("sis-plan") or {"completed": 2},
    )

    manifest_path = weekly.run_week(
        week=2,
        fp_profile_dir=tmp_path / "fp-profile",
        sis_profile_dir=tmp_path / "sis-profile",
        timeout_seconds=10,
        output_root=tmp_path / "runs",
        fp_output_root=tmp_path / "fp-output",
        sis_output_root=tmp_path / "sis-output",
        fp_plan=tmp_path / "fp-plan.json",
        sis_plan=sis_plan,
        ingest_props=True,
        login_if_needed=False,
        now=datetime(2026, 9, 16, 14, tzinfo=UTC),
    )

    assert events == [
        "verify-fp", "ingest-odds", "ingest-props",
        "route-download", "route-import-True", "route-download", "proe-import-True",
        "matchups", "matchups-stage-matchups-True", "verify-sis", "sis-plan",
    ]
    manifest = json.loads(manifest_path.read_text())
    assert manifest["status"] == "complete"
    assert manifest["target_week"] == 2
    assert [step["status"] for step in manifest["steps"]] == ["complete"] * 16
    assert manifest["steps"][-1]["name"] == "paid-page-completeness"
    assert manifest["paid_pages"]["line"] == "PAID PAGES: 9 of 9 paid pages captured for Week 2"


def test_run_week_forces_fresh_sis_login(monkeypatch, tmp_path):
    events = []
    monkeypatch.setattr(
        weekly.fp, "verify_login", lambda *_: events.append("verify-fp")
    )
    monkeypatch.setattr(
        weekly.sis,
        "interactive_login",
        lambda *_args, **kwargs: events.append(
            ("login-sis", kwargs["terminal_credentials"], kwargs["force_fresh"])
        ),
    )
    monkeypatch.setattr(
        weekly.sis, "verify_login", lambda *_: events.append("verify-sis")
    )

    weekly.run_week(
        week=1,
        fp_profile_dir=tmp_path / "fp-profile",
        sis_profile_dir=tmp_path / "sis-profile",
        timeout_seconds=10,
        output_root=tmp_path / "runs",
        fp_output_root=tmp_path / "fp-output",
        sis_output_root=tmp_path / "sis-output",
        capture_matchups=False,
        capture_sis_pass_tail=False,
        ingest_odds=False,
        login_if_needed=True,
        now=datetime(2026, 9, 2, 14, tzinfo=UTC),
    )
    assert events == [("login-sis", True, True), "verify-sis"]


def test_week_five_adds_frozen_alignment_download_and_import(
    monkeypatch, tmp_path
):
    events = []
    route_run = tmp_path / "route-run"
    alignment_run = tmp_path / "alignment-run"
    route_run.mkdir()
    alignment_run.mkdir()
    (route_run / "manifest.json").write_text("{}")
    (alignment_run / "manifest.json").write_text("{}")

    monkeypatch.setattr(weekly.fp, "load_plan", lambda *_: ({}, [object()]))
    monkeypatch.setattr(weekly.fp, "select_target_week", lambda specs, _: specs)
    monkeypatch.setattr(weekly.fp, "verify_login", lambda *_: None)
    monkeypatch.setattr(weekly.sis, "verify_login", lambda *_: None)
    monkeypatch.setattr(
        weekly.fp,
        "run_downloads",
        lambda plan, *_args, **_kwargs: (
            events.append(plan.name)
            or (
                alignment_run / "manifest.json"
                if "alignment" in plan.name
                else route_run / "manifest.json"
            )
        ),
    )
    monkeypatch.setattr(
        weekly.fantasy_points_route_weekly, "run",
        lambda *_args, **_kwargs: events.append("route-import") or {},
    )
    monkeypatch.setattr(
        weekly.fantasy_points_alignment_weekly, "run",
        lambda *_args, **kwargs: events.append(
            f"alignment-import-{kwargs['write']}"
        ) or {},
    )
    monkeypatch.setattr(
        weekly.sis, "run_pass_tail_weekly_acquisition",
        lambda *_args, **_kwargs: events.append("sis-pass-tail-download") or {},
    )
    monkeypatch.setattr(
        weekly.sis_pass_tail_weekly, "run",
        lambda *_args, **_kwargs: events.append("sis-pass-tail-import") or {},
    )
    monkeypatch.setattr(
        weekly.sis, "run_receiver_copula_weekly_acquisition",
        lambda *_args, **kwargs: events.append(
            f"sis-receiver-copula-download-{kwargs['target_week']}") or {},
    )
    monkeypatch.setattr(
        weekly.sis_receiver_copula_weekly, "run",
        lambda *_args, **kwargs: events.append(
            f"sis-receiver-copula-import-{kwargs['write']}") or {},
    )
    monkeypatch.setattr(
        weekly.fantasy_points_defense_proe_weekly, "run",
        lambda *_args, **kwargs: events.append(f"proe-import-{kwargs['write']}") or {},
    )
    monkeypatch.setattr(
        weekly.fantasy_points_weekly_2026, "run",
        lambda key, *_args, **kwargs: events.append(f"{key}-import-{kwargs['write']}") or {},
    )

    weekly.run_week(
        week=5,
        fp_profile_dir=tmp_path / "fp-profile",
        sis_profile_dir=tmp_path / "sis-profile",
        timeout_seconds=10,
        output_root=tmp_path / "runs",
        fp_output_root=tmp_path / "fp-output",
        sis_output_root=tmp_path / "sis-output",
        capture_matchups=False,
        ingest_odds=False,
        login_if_needed=False,
        write_alignment=False,
        write_fp_families=False,
        sis_team_context=False,
        now=datetime(2026, 9, 30, 14, tzinfo=UTC),
    )
    assert events == [
        "2026-route-share-weekly-v1.json",
        "route-import",
        "2026-defense-proe-weekly-v1.json",
        "proe-import-False",
        "2026-alignment-last-four-weekly-v1.json",
        "alignment-import-False",
        "2026-advanced-passing-last-four-weekly-v1.json",
        "advanced-passing-import-False",
        "2026-route-shape-last-four-weekly-v1.json",
        "route-shape-import-False",
        "2026-coverage-last-four-weekly-v1.json",
        "coverage-import-False",
        "2026-qb-shell-fit-last-four-weekly-v1.json",
        "qb-shell-import-False",
        "2026-advanced-receiving-support-windows-weekly-v1.json",
        "advanced-receiving-import-False",
        # the cumulative pages follow every established step, and --audit-only-fp-families covers them too
        *[event for key in weekly.FP_CUMULATIVE_ORDER for event in (
            weekly.DEFAULT_FP_CUMULATIVE_PLANS[key].name, f"{key}-import-False")],
        "sis-pass-tail-download",
        "sis-pass-tail-import",
        "sis-receiver-copula-download-5",
        "sis-receiver-copula-import-True",
    ]


def test_run_week_verifies_sis_but_does_not_query_without_approved_plan(
    monkeypatch, tmp_path
):
    events = []
    monkeypatch.setattr(
        weekly.fp, "verify_login", lambda *_: events.append("verify-fp")
    )
    monkeypatch.setattr(
        weekly.sis, "verify_login", lambda *_: events.append("verify-sis")
    )
    monkeypatch.setattr(
        weekly.fp_matchups, "run", lambda **_: Path("matchups/manifest.json")
    )
    monkeypatch.setattr(weekly.fantasy_points_matchups_weekly, "run", lambda *_a, **_k: {})

    manifest_path = weekly.run_week(
        week=1,
        fp_profile_dir=tmp_path / "fp-profile",
        sis_profile_dir=tmp_path / "sis-profile",
        timeout_seconds=10,
        output_root=tmp_path / "runs",
        fp_output_root=tmp_path / "fp-output",
        sis_output_root=tmp_path / "sis-output",
        ingest_odds=False,
        sis_plan=None,
        login_if_needed=False,
        now=datetime(2026, 9, 2, 14, tzinfo=UTC),
    )
    # 2026-09-21 (defect 28): the SIS session is verified only when an SIS step runs; this week-2 run has none, so the
    # step is recorded as not required and the Fantasy Points capture proceeds
    assert events == ["verify-fp"]
    manifest = json.loads(manifest_path.read_text())
    sis_step = next(s for s in manifest["steps"] if s["name"] == "sis-session")
    assert sis_step["result"]["status"] == "not-required"


def test_failed_step_is_durable(monkeypatch, tmp_path):
    monkeypatch.setattr(weekly.fp, "verify_login", lambda *_: None)
    monkeypatch.setattr(weekly.sis, "verify_login", lambda *_: None)
    monkeypatch.setattr(
        weekly, "_run_cloud_job",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("quota")),
    )

    try:
        weekly.run_week(
            week=1,
            fp_profile_dir=tmp_path / "fp-profile",
            sis_profile_dir=tmp_path / "sis-profile",
            timeout_seconds=10,
            output_root=tmp_path / "runs",
            fp_output_root=tmp_path / "fp-output",
            sis_output_root=tmp_path / "sis-output",
            capture_matchups=True,
            login_if_needed=False,
            now=datetime(2026, 9, 2, 14, tzinfo=UTC),
        )
    except RuntimeError as exc:
        assert str(exc) == "quota"
    else:  # pragma: no cover
        raise AssertionError("workflow unexpectedly succeeded")

    manifest_path = next((tmp_path / "runs").glob("*/manifest.json"))
    manifest = json.loads(manifest_path.read_text())
    assert manifest["status"] == "failed"
    assert manifest["steps"][-1]["name"] == "odds-api-game-lines"
    assert manifest["steps"][-1]["error"] == "quota"


def test_expired_sis_session_fails_the_run_only_after_every_fantasy_points_step(monkeypatch, tmp_path):
    """Defect 28 + the operator's 2026-09-23 rule: an expired SIS session never loses the Fantasy Points capture
    (every FP step runs first), and the run still fails closed at the SIS step with the renewal and re-run commands."""
    events = []
    monkeypatch.setattr(weekly.fp, "load_plan", lambda *_: ({}, [object()]))
    monkeypatch.setattr(weekly.fp, "select_target_week", lambda specs, _: specs)
    monkeypatch.setattr(weekly.fp, "verify_login", lambda *_: events.append("verify-fp"))

    def expired(*_):
        raise RuntimeError("SIS saved session is missing, expired, or cannot load Player Leaderboards")

    monkeypatch.setattr(weekly.sis, "verify_login", expired)
    monkeypatch.setattr(weekly.sis, "interactive_login", lambda *a, **k: events.append("login-sis"))
    monkeypatch.setattr(weekly.sis, "run_plan", lambda *a, **k: events.append("sis-capture"))
    monkeypatch.setattr(weekly.fp, "run_downloads", lambda *a, **k: events.append("fp-download") or (tmp_path / "fp" / "manifest.json"))
    monkeypatch.setattr(weekly.fantasy_points_route_weekly, "run", lambda *a, **k: events.append("fp-import") or {"rows": 1})
    monkeypatch.setattr(weekly.fantasy_points_defense_proe_weekly, "run", lambda *a, **k: events.append("proe-import") or {})
    with pytest.raises(RuntimeError, match="sis-download login.*--skip-fantasy-points"):
        weekly.run_week(
            week=3, fp_profile_dir=tmp_path / "fp-profile", sis_profile_dir=tmp_path / "sis-profile", timeout_seconds=10,
            output_root=tmp_path / "runs", fp_output_root=tmp_path / "fp-output", sis_output_root=tmp_path / "sis-output",
            capture_matchups=False, capture_sis_pass_tail=True, ingest_odds=False, login_if_needed=False,
            now=datetime(2026, 9, 21, 4, tzinfo=UTC),
        )
    assert events == ["verify-fp", "fp-download", "fp-import", "fp-download", "proe-import"]   # FP captured, no SIS
    manifest = json.loads(next((tmp_path / "runs").glob("*/manifest.json")).read_text())
    assert manifest["status"] == "failed" and manifest["steps"][-1]["name"] == "sis-session"
    assert manifest["configuration"]["sis_plan"].endswith("team-context-2026-w02.json")


def test_expired_sis_session_still_stops_a_run_that_needs_sis(monkeypatch, tmp_path):
    monkeypatch.setattr(weekly.fp, "load_plan", lambda *_: ({}, [object()]))
    monkeypatch.setattr(weekly.fp, "select_target_week", lambda specs, _: specs)
    monkeypatch.setattr(weekly.fp, "verify_login", lambda *_: None)
    monkeypatch.setattr(weekly.sis, "load_plan", lambda *_: [])
    monkeypatch.setattr(weekly.sis, "plan_request_ceiling", lambda *_: 10)

    def expired(*_):
        raise RuntimeError("SIS saved session is missing, expired, or cannot load Player Leaderboards")

    monkeypatch.setattr(weekly.sis, "verify_login", expired)
    downloads = []
    monkeypatch.setattr(weekly.fp, "run_downloads", lambda *a, **k: downloads.append(1) or (tmp_path / "fp" / "manifest.json"))
    monkeypatch.setattr(weekly.fantasy_points_route_weekly, "run", lambda *a, **k: {})
    monkeypatch.setattr(weekly.fantasy_points_defense_proe_weekly, "run", lambda *a, **k: {})
    monkeypatch.setattr(weekly.sis, "run_plan", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no SIS query past the gate")))
    plan = tmp_path / "sis-plan.json"; plan.write_text("[]")
    with pytest.raises(RuntimeError, match="SIS saved session is not usable"):
        weekly.run_week(
            week=3, fp_profile_dir=tmp_path / "fp-profile", sis_profile_dir=tmp_path / "sis-profile", timeout_seconds=10,
            output_root=tmp_path / "runs", fp_output_root=tmp_path / "fp-output", sis_output_root=tmp_path / "sis-output",
            sis_plan=plan, capture_matchups=False, capture_sis_pass_tail=False, ingest_odds=False, login_if_needed=False,
            now=datetime(2026, 9, 21, 4, tzinfo=UTC),
        )
    assert downloads, "the Fantasy Points capture runs before the SIS gate"


def test_qb_shell_import_receives_the_same_weeks_coverage_run(monkeypatch, tmp_path):
    """The five last-four families run in order after alignment; qb-shell is parsed with the coverage run's directory."""
    runs = {}

    def download(plan, *_args, **_kwargs):
        run_dir = tmp_path / plan.stem
        run_dir.mkdir(exist_ok=True)
        (run_dir / "manifest.json").write_text("{}")
        runs[plan.stem] = run_dir
        return run_dir / "manifest.json"

    seen = []
    monkeypatch.setattr(weekly.fp, "verify_login", lambda *_: None)
    monkeypatch.setattr(weekly.sis, "verify_login", lambda *_: None)
    monkeypatch.setattr(weekly.fp, "run_downloads", download)
    monkeypatch.setattr(weekly.fantasy_points_route_weekly, "run", lambda *_a, **_k: {})
    monkeypatch.setattr(weekly.fantasy_points_alignment_weekly, "run", lambda *_a, **_k: {})
    monkeypatch.setattr(weekly.fantasy_points_defense_proe_weekly, "run", lambda *_a, **_k: {})
    monkeypatch.setattr(
        weekly.fantasy_points_weekly_2026, "run",
        lambda key, run_dir, **kwargs: seen.append((key, run_dir.name, kwargs.get("coverage_dir"), kwargs["target_week"])) or {},
    )
    weekly.run_week(
        week=6, fp_profile_dir=tmp_path / "fp", sis_profile_dir=tmp_path / "sis", timeout_seconds=10,
        output_root=tmp_path / "runs", fp_output_root=tmp_path / "fp-out", sis_output_root=tmp_path / "sis-out",
        capture_matchups=False, capture_sis_pass_tail=False, capture_sis_receiver_copula=False, ingest_odds=False,
        login_if_needed=False, sis_team_context=False, now=datetime(2026, 10, 7, 14, tzinfo=UTC),
    )
    assert [key for key, *_ in seen] == [*weekly.FP_FAMILY_ORDER, *weekly.FP_CUMULATIVE_ORDER]
    shell = next(item for item in seen if item[0] == "qb-shell")
    assert shell[2] == runs["2026-coverage-last-four-weekly-v1"] and shell[3] == 6
    assert all(item[2] is None for item in seen if item[0] != "qb-shell")


def _quiet_fp(monkeypatch, tmp_path, events):
    monkeypatch.setattr(weekly.fp, "verify_login", lambda *_: None)
    monkeypatch.setattr(weekly.fp, "run_downloads", lambda *a, **k: (tmp_path / "fp" / "manifest.json"))
    monkeypatch.setattr(weekly.fantasy_points_route_weekly, "run", lambda *a, **k: {})
    monkeypatch.setattr(weekly.fantasy_points_defense_proe_weekly, "run", lambda *a, **k: {})
    monkeypatch.setattr(weekly.sis, "verify_login", lambda *_: events.append("verify-sis"))


def test_default_team_context_plan_is_captured_and_loaded(monkeypatch, tmp_path):
    """One Wednesday run captures AND loads the completed week's SIS team context (tracked plan for W-1)."""
    events = []
    _quiet_fp(monkeypatch, tmp_path, events)
    monkeypatch.setattr(weekly.sis, "run_plan", lambda profile, timeout, out, plan: events.append(("capture", plan.name)) or {})
    monkeypatch.setattr(weekly.sis_team_context_weekly, "run",
                        lambda out, plan, **kw: events.append(("import", plan.name, kw["write"])) or {})
    manifest_path = weekly.run_week(
        week=3, fp_profile_dir=tmp_path / "fp", sis_profile_dir=tmp_path / "sis", timeout_seconds=10,
        output_root=tmp_path / "runs", fp_output_root=tmp_path / "fp-out", sis_output_root=tmp_path / "sis-out",
        capture_matchups=False, ingest_odds=False, login_if_needed=False, now=datetime(2026, 9, 23, 20, tzinfo=UTC),
    )
    assert events == ["verify-sis", ("capture", "team-context-2026-w02.json"),
                      ("import", "team-context-2026-w02.json", True)]
    config = json.loads(manifest_path.read_text())["configuration"]
    assert config["sis_plan"].endswith("team-context-2026-w02.json") and config["sis_team_context_import"]


def test_a_week_without_a_tracked_team_context_plan_fails_loudly_after_fantasy_points(monkeypatch, tmp_path):
    events = []
    _quiet_fp(monkeypatch, tmp_path, events)
    monkeypatch.setattr(weekly, "SIS_PLANS_DIR", tmp_path / "no-plans")
    monkeypatch.setattr(weekly, "PROJECT_ROOT", tmp_path)
    with pytest.raises(FileNotFoundError, match=r"team-context-2026-w03\.json.*--skip-fantasy-points"):
        weekly.run_week(
            week=4, fp_profile_dir=tmp_path / "fp", sis_profile_dir=tmp_path / "sis", timeout_seconds=10,
            output_root=tmp_path / "runs", fp_output_root=tmp_path / "fp-out", sis_output_root=tmp_path / "sis-out",
            capture_matchups=False, capture_sis_pass_tail=False, ingest_odds=False, login_if_needed=False,
            now=datetime(2026, 9, 30, 20, tzinfo=UTC),
        )
    steps = [s["name"] for s in json.loads(next((tmp_path / "runs").glob("*/manifest.json")).read_text())["steps"]]
    assert steps.index("fantasy-points-route-import") < steps.index("sis-team-context-plan") == len(steps) - 1


def test_skip_fantasy_points_is_the_sis_only_rerun(monkeypatch, tmp_path):
    events = []
    monkeypatch.setattr(weekly.fp, "verify_login", lambda *_: events.append("verify-fp"))
    monkeypatch.setattr(weekly.fp, "run_downloads", lambda *a, **k: events.append("fp-download"))
    monkeypatch.setattr(weekly.sis, "verify_login", lambda *_: events.append("verify-sis"))
    monkeypatch.setattr(weekly.sis, "run_plan", lambda profile, timeout, out, plan: events.append(("capture", plan.name)))
    monkeypatch.setattr(weekly.sis_team_context_weekly, "run", lambda out, plan, **kw: events.append(("import", plan.name)))
    manifest_path = weekly.run_week(
        week=3, fp_profile_dir=tmp_path / "fp", sis_profile_dir=tmp_path / "sis", timeout_seconds=10,
        output_root=tmp_path / "runs", fp_output_root=tmp_path / "fp-out", sis_output_root=tmp_path / "sis-out",
        capture_matchups=False, ingest_odds=False, login_if_needed=False, skip_fantasy_points=True,
        now=datetime(2026, 9, 23, 22, tzinfo=UTC),
    )
    assert events == ["verify-sis", ("capture", "team-context-2026-w02.json"), ("import", "team-context-2026-w02.json")]
    assert json.loads(manifest_path.read_text())["status"] == "complete"


def test_every_remaining_run_week_has_a_tracked_team_context_plan_for_the_completed_week():
    """So the Wednesday run never depends on someone authoring next week's plan (weeks 3-18 -> completed weeks 2-17)."""
    from nfl_dfs.ops import sis_downloads as sis

    for week in range(3, 19):
        (spec, *_), plan = sis.load_plan(weekly.sis_team_context_plan(week)), weekly.sis_team_context_plan(week)
        specs = sis.load_plan(plan)
        assert {(s.season, s.start_week, s.end_week) for s in specs} == {(2026, week - 1, week - 1)}, plan.name
        assert len(specs) == 11 and sis.plan_request_ceiling(plan) <= 60


def test_week_four_declares_every_paid_page():
    """Production's order D (2026-09-28): the declared list for Wednesday 09-30 (target Week 4, completed Week 3)."""
    pages = weekly.paid_pages(4, sis_plan=None)
    labels = [page["page"] for page in pages]
    assert len(labels) == len(set(labels)) == 31
    groups = [page["group"] for page in pages]
    assert {g: groups.count(g) for g in groups} == {
        "route-share": 1, "defense-proe": 1, "matchups": 3, "fp-projections": 4, "fp-cumulative": 9, "sis-team-context": 11,
        "sis-receiver-copula": 2,
    }
    assert "sis receiver-copula wr-cb pass-defense-totals/wide week 03" in labels
    assert "sis receiver-copula wr-cb pass-defense-totals/slot week 03" in labels
    assert "fantasy-points advanced-rushing-cumulative: advanced-rushing/Player weeks 01-03" in labels
    assert "fantasy-points advanced-passing-cumulative: advanced-passing/Player weeks 01-03" in labels
    assert "fantasy-points route-share week 03" in labels and "sis pass-defense-totals week 03" in labels
    for week in range(2, 19):                                   # unique every week; last-four join from Week 5
        pages = weekly.paid_pages(week, sis_plan=None)
        assert len({page["page"] for page in pages}) == len(pages)
        groups = {page["group"] for page in pages}
        assert {"alignment", "fp-families", "sis-pass-tail"} <= groups if week >= 5 else "fp-families" not in groups
        assert ("sis-receiver-copula" in groups) == (week >= 4)


def _wednesday(monkeypatch, tmp_path, events, *, fail=None):
    """Every Week-4 capture faked; `fail` names one step action that raises."""
    def act(name, value=None):
        events.append(name)
        if name == fail:
            raise RuntimeError(f"{name} broke")
        return value

    def download(plan, *_a, **_k):
        run_dir = tmp_path / "fp" / plan.stem
        run_dir.mkdir(parents=True, exist_ok=True)
        return act(plan.stem, run_dir / "manifest.json")

    monkeypatch.setattr(weekly.fp, "verify_login", lambda *_: None)
    monkeypatch.setattr(weekly.sis, "verify_login", lambda *_: None)
    monkeypatch.setattr(weekly.fp, "run_downloads", download)
    monkeypatch.setattr(weekly.fantasy_points_route_weekly, "run", lambda *a, **k: act("route-import", {}))
    monkeypatch.setattr(weekly.fantasy_points_defense_proe_weekly, "run", lambda *a, **k: act("proe-import", {}))
    monkeypatch.setattr(weekly.fp_matchups, "run", lambda **_: act("matchups", tmp_path / "m" / "manifest.json"))
    monkeypatch.setattr(weekly.fantasy_points_matchups_weekly, "run", lambda *a, **k: act("matchups-stage", {}))
    monkeypatch.setattr(weekly.fantasy_points_weekly_2026, "run",
                        lambda key, run_dir, **kw: act(f"{key}-import-{kw['write']}", {}))
    monkeypatch.setattr(weekly.sis, "run_plan", lambda *a, **k: act("sis-capture", {}))
    monkeypatch.setattr(weekly.sis_team_context_weekly, "run", lambda *a, **k: act("sis-import", {}))
    monkeypatch.setattr(weekly.sis, "run_receiver_copula_weekly_acquisition",
                        lambda *a, **k: act("sis-receiver-copula-download", {"passes": True}))
    monkeypatch.setattr(weekly.sis_receiver_copula_weekly, "run",
                        lambda *a, **k: act(f"sis-receiver-copula-import-{k['write']}", {}))
    return dict(
        week=4, fp_profile_dir=tmp_path / "fp-profile", sis_profile_dir=tmp_path / "sis-profile", timeout_seconds=10,
        output_root=tmp_path / "runs", fp_output_root=tmp_path / "fp-out", sis_output_root=tmp_path / "sis-out",
        ingest_odds=False, login_if_needed=False, now=datetime(2026, 9, 30, 14, 30, tzinfo=UTC),
    )


def test_wednesday_week_four_run_captures_every_paid_page(monkeypatch, tmp_path, capsys):
    """`nfl-weekly-data run --week 4 --skip-odds --no-login-if-needed`: the cumulative pages run after every
    established Fantasy Points step and before SIS, and the operator reads one line."""
    events = []
    manifest_path = weekly.run_week(**_wednesday(monkeypatch, tmp_path, events))
    cumulative = [e for key in weekly.FP_CUMULATIVE_ORDER
                  for e in (weekly.DEFAULT_FP_CUMULATIVE_PLANS[key].stem, f"{key}-import-True")]
    assert events == ["2026-route-share-weekly-v1", "route-import", "2026-defense-proe-weekly-v1", "proe-import",
                      "matchups", "matchups-stage", *cumulative, "sis-capture", "sis-import",
                      "sis-receiver-copula-download", "sis-receiver-copula-import-True"]
    manifest = json.loads(manifest_path.read_text())
    assert manifest["status"] == "complete" and manifest["steps"][-1]["result"] == {"expected": 31, "captured": 31}
    assert {page["status"] for page in manifest["paid_pages"]["pages"]} == {"captured"}
    assert "PAID PAGES: 31 of 31 paid pages captured for Week 4\n" in capsys.readouterr().out
    assert manifest["configuration"]["fantasy_points_cumulative_plans"].keys() == set(weekly.FP_CUMULATIVE_ORDER)


def test_a_failed_cumulative_page_is_named_and_fails_the_run_after_sis_is_captured(monkeypatch, tmp_path, capsys):
    events = []
    with pytest.raises(RuntimeError, match=r"PAID PAGES: 30 of 31 .*NOT CAPTURED: fantasy-points "
                                           r"advanced-rushing-cumulative: advanced-rushing/Player weeks 01-03"):
        weekly.run_week(**_wednesday(monkeypatch, tmp_path, events, fail="advanced-rushing-cumulative-import-True"))
    assert events[-4:] == ["sis-capture", "sis-import", "sis-receiver-copula-download",
                           "sis-receiver-copula-import-True"]            # SIS was not lost to the vendor page
    assert "route-shape-cumulative-import-True" in events                 # nor were the pages after it
    manifest = json.loads(next((tmp_path / "runs").glob("*/manifest.json")).read_text())
    assert manifest["status"] == "failed" and manifest["steps"][-1]["name"] == "paid-page-completeness"
    (failed,) = [page for page in manifest["paid_pages"]["pages"] if page["status"] == "FAILED"]
    assert failed["reason"].startswith("fantasy-points-advanced-rushing-cumulative-import failed")


def test_a_fatal_failure_still_names_every_page_it_leaves_uncaptured(monkeypatch, tmp_path, capsys):
    """Defense PROE's import is fatal (its schedule check is the W-1 completeness gate ahead of the cumulative pages)."""
    events = []
    with pytest.raises(RuntimeError, match="proe-import broke"):
        weekly.run_week(**_wednesday(monkeypatch, tmp_path, events, fail="proe-import"))
    manifest = json.loads(next((tmp_path / "runs").glob("*/manifest.json")).read_text())
    assert manifest["steps"][-1]["name"] == "fantasy-points-defense-proe-import"     # no step after the failure
    status = {page["page"]: page for page in manifest["paid_pages"]["pages"]}
    assert status["fantasy-points route-share week 03"]["status"] == "captured"
    assert status["fantasy-points offense-proe/Defense week 03"]["reason"].startswith(
        "fantasy-points-defense-proe-import failed")
    assert status["sis pass-defense-totals week 03"]["reason"] == "sis-approved-plan never ran"
    assert "PAID PAGES: 1 of 31 paid pages captured for Week 4; NOT CAPTURED:" in capsys.readouterr().out


def test_a_failed_matchups_capture_is_named_and_the_run_goes_on(monkeypatch, tmp_path, capsys):
    """2026-09-29 sweep: the matchups steps are not fatal (Week 4 is their first current-season week)."""
    events = []
    with pytest.raises(RuntimeError, match=r"PAID PAGES: 28 of 31 .*NOT CAPTURED: fantasy-points qb-coverage-matchup"):
        weekly.run_week(**_wednesday(monkeypatch, tmp_path, events, fail="matchups"))
    assert "matchups-stage" not in events and "sis-capture" in events                  # no stage; SIS still ran


def test_skipped_pages_are_named_not_failed(monkeypatch, tmp_path, capsys):
    """The SIS-only re-run: the Fantasy Points pages are named as skipped by the flag, never counted as captured."""
    events = []
    kwargs = _wednesday(monkeypatch, tmp_path, events)
    weekly.run_week(**{**kwargs, "skip_fantasy_points": True, "capture_matchups": False})
    assert events == ["sis-capture", "sis-import", "sis-receiver-copula-download", "sis-receiver-copula-import-True"]
    assert ("PAID PAGES: 13 of 13 paid pages captured for Week 4 (18 skipped by --skip-fantasy-points)\n"
            in capsys.readouterr().out)


def test_a_failed_receiver_copula_download_is_named_and_the_run_goes_on(monkeypatch, tmp_path, capsys):
    """Vendor item B: the copula steps are not fatal; the gate names both pages of week W-1 and fails the run."""
    events = []
    with pytest.raises(RuntimeError, match=r"PAID PAGES: 29 of 31 .*NOT CAPTURED: sis receiver-copula wr-cb "
                                           r"pass-defense-totals/wide week 03"):
        weekly.run_week(**_wednesday(monkeypatch, tmp_path, events, fail="sis-receiver-copula-download"))
    assert events[-1] == "sis-receiver-copula-download"                 # no import of a failed acquisition
    manifest = json.loads(next((tmp_path / "runs").glob("*/manifest.json")).read_text())
    failed = [page for page in manifest["paid_pages"]["pages"] if page["status"] == "FAILED"]
    assert [page["group"] for page in failed] == ["sis-receiver-copula"] * 2
    assert all(page["reason"].startswith("sis-receiver-copula-download failed") for page in failed)


def test_receiver_copula_skip_and_audit_only_flags(monkeypatch, tmp_path, capsys):
    events = []
    kwargs = _wednesday(monkeypatch, tmp_path, events)
    weekly.run_week(**{**kwargs, "capture_sis_receiver_copula": False})
    assert "sis-receiver-copula-download" not in events
    assert ("PAID PAGES: 29 of 29 paid pages captured for Week 4 (2 skipped by --skip-sis-receiver-copula)\n"
            in capsys.readouterr().out)
    events.clear()
    weekly.run_week(**{**kwargs, "write_sis_receiver_copula": False, "output_root": tmp_path / "runs-2"})
    assert events[-1] == "sis-receiver-copula-import-False"
    assert ("PAID PAGES: 31 of 31 paid pages captured for Week 4 (audit-only, not archived or appended: "
            "sis-receiver-copula)\n" in capsys.readouterr().out)


def test_receiver_copula_cli_flags_reach_the_run(monkeypatch):
    seen = {}
    monkeypatch.setattr(weekly, "run_week", lambda **kwargs: seen.update(kwargs) or Path("manifest.json"))
    weekly.main(["run", "--week", "4", "--skip-sis-receiver-copula", "--audit-only-sis-receiver-copula"])
    assert seen["capture_sis_receiver_copula"] is False and seen["write_sis_receiver_copula"] is False
    weekly.main(["run", "--week", "4"])
    assert seen["capture_sis_receiver_copula"] is True and seen["write_sis_receiver_copula"] is True


def test_fp_projection_pages_are_captured_one_table_per_step_and_a_failure_is_named(monkeypatch, tmp_path, capsys):
    """2026-10-05 (reviewer): the DFS-tier projection tables are paid pages of every week. Each table is its own page and
    its own non-fatal step; a failed table is named by the gate after SIS was captured, and the flag skips all four."""
    events = []
    kwargs = _wednesday(monkeypatch, tmp_path, events)
    weekly.run_week(**kwargs)
    assert PROJECTION_CALLS == [(2026, 4, (t,)) for t in weekly.FP_PROJECTION_TABLES]
    assert "betting" not in weekly.FP_PROJECTION_TABLES        # a 3-row preview on the operator's plan
    capsys.readouterr()

    def broken(profile_dir, timeout_s, *, season, week, which, output_root):
        if which == ["dfs"]:
            raise RuntimeError("dfs: no table payload was observed")
        return {"tables": {}, "failures": {}}

    monkeypatch.setattr(weekly.fp_projections, "collect", broken)
    events.clear()
    with pytest.raises(RuntimeError, match=r"PAID PAGES: 30 of 31 .*NOT CAPTURED: fantasy-points projections/dfs "
                                           r"\(live, Week 4\) \[fantasy-points-projections-dfs failed: dfs: no table"):
        weekly.run_week(**{**kwargs, "output_root": tmp_path / "runs-2"})
    assert "sis-capture" in events                                  # the vendor page never costs the SIS capture
    events.clear(); PROJECTION_CALLS.clear()
    monkeypatch.setattr(weekly.fp_projections, "collect", lambda *a, **k: PROJECTION_CALLS.append(k))
    weekly.run_week(**{**kwargs, "capture_fp_projections": False, "output_root": tmp_path / "runs-3"})
    assert PROJECTION_CALLS == []
    assert "PAID PAGES: 27 of 27 paid pages captured for Week 4 (4 skipped by --skip-fp-projections)\n" in capsys.readouterr().out


def test_cli_skip_fp_projections_flag(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(weekly, "run_week", lambda **k: seen.update(k) or tmp_path / "m.json")
    weekly.main(["run", "--week", "5", "--skip-fp-projections", "--no-login-if-needed"])
    assert seen["capture_fp_projections"] is False
    weekly.main(["run", "--week", "5", "--no-login-if-needed"])
    assert seen["capture_fp_projections"] is True
