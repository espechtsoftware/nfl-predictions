import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from nfl_dfs.ops import weekly_vendor_data as weekly


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
        "verify-fp", "verify-sis", "ingest-odds", "ingest-props",
        "route-download", "route-import-True", "matchups", "sis-plan",
    ]
    manifest = json.loads(manifest_path.read_text())
    assert manifest["status"] == "complete"
    assert manifest["target_week"] == 2
    assert [step["status"] for step in manifest["steps"]] == ["complete"] * 8


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
        now=datetime(2026, 9, 30, 14, tzinfo=UTC),
    )
    assert events == [
        "2026-route-share-weekly-v1.json",
        "route-import",
        "2026-alignment-last-four-weekly-v1.json",
        "alignment-import-False",
        "sis-pass-tail-download",
        "sis-pass-tail-import",
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

    weekly.run_week(
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
    assert events == ["verify-fp", "verify-sis"]


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
