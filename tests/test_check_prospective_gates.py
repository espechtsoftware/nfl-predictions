"""Adversarial tests for the prospective-gate checker.

Each test breaks the world on purpose and asserts the checker NOTICES.  A test that
merely re-runs the check against the real project would prove nothing -- that is the
same silence the checker exists to end.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "check_prospective_gates",
    Path(__file__).resolve().parents[1] / "scripts" / "check_prospective_gates.py",
)
cpg = importlib.util.module_from_spec(SPEC)
sys.modules["check_prospective_gates"] = cpg
assert SPEC.loader is not None
SPEC.loader.exec_module(cpg)


NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)  # Saturday before Week 5


def NOW_MINUS(days: float) -> str:
    return (NOW - timedelta(days=days)).isoformat().replace("+00:00", "Z")


def _execution(name: str, completed: str | None, finished: str) -> dict:
    """One `gcloud run jobs executions list --format=json` row, as the provider returns it."""
    status: dict = {"conditions": [{"type": "Started", "status": "True"}]}
    if completed is not None:
        status["conditions"].insert(0, {"type": "Completed", "status": completed})
        status["completionTime"] = finished
        status["failedCount" if completed == "False" else "succeededCount"] = 1
    return {"metadata": {"name": name, "creationTimestamp": finished}, "status": status}


@pytest.fixture
def world(monkeypatch):
    """A healthy world: every registered scheduler ENABLED, every job on-policy."""
    state = {s: {"state": "ENABLED", "schedule": "20 10 * * 7"}
             for g in cpg.GATES.values()
             for s in g["schedulers"] + g.get("input_schedulers", [])}
    state.update({s: {"state": "PAUSED", "schedule": "0 0 * * 7"} for s in cpg.DORMANT})
    envs: dict[str, dict[str, str]] = {}
    for gate in cpg.GATES.values():
        for s in gate["schedulers"]:
            # Two registry keys may audit one job (a frozen key and its companion). Where
            # their contracts agree a healthy job satisfies both; where they conflict
            # (CBWU_OI_CONTRACT) the current, non-superseded contract wins -- see _as_of
            # for a world audited before the companion's first week.
            if gate.get("superseded_from_week") is not None:
                continue
            want = (gate.get("require_env_by_scheduler") or {}).get(s, gate["require_env"])
            envs.setdefault(f"job-for-{s}", {}).update(want or {})
    for gate in cpg.GATES.values():
        if gate.get("superseded_from_week") is None:
            continue
        for s in gate["schedulers"]:
            for key, value in (gate["require_env"] or {}).items():
                envs.setdefault(f"job-for-{s}", {}).setdefault(key, value)
    for gate in cpg.GATES.values():
        if gate.get("require_code_ancestors"):
            for s in gate["schedulers"]:
                envs.setdefault(f"job-for-{s}", {}).setdefault("CODE_SHA", "c0ffee0c0ffee0")
            for s in gate.get("input_schedulers", []) if gate.get("same_env_include_inputs") else ():
                envs.setdefault(f"job-for-{s}", {}).setdefault("CODE_SHA", "c0ffee0c0ffee0")
    # Every image contains every required fix unless a test says otherwise (offline).
    monkeypatch.setattr(cpg, "code_contains", lambda code_sha, commit: True)
    monkeypatch.setattr(cpg, "schedulers", lambda: state)
    monkeypatch.setattr(cpg, "scheduler_target", lambda s: f"job-for-{s}")
    monkeypatch.setattr(cpg, "job_env", lambda j: envs.get(j, {}))
    # Every job's newest run succeeded yesterday (offline; the provider is injected).
    runs: dict[str, list[dict] | None] = {}
    monkeypatch.setattr(cpg, "job_executions",
                        lambda j: runs.get(j, [_execution(f"{j}-ok", "True", NOW_MINUS(1))]))
    return state, envs


def _as_of(envs, week):
    """A healthy job before a companion took over carries the then-live contract."""
    for gate in cpg.GATES.values():
        until = gate.get("superseded_from_week")
        if until is not None and week < until:
            for s in gate["schedulers"]:
                envs[f"job-for-{s}"].update(gate["require_env"] or {})


def test_healthy_world_passes(world):
    _, envs = world
    errors, _, _ = cpg.audit(week=5)
    assert errors == [], errors
    _as_of(envs, 2)
    errors, _, _ = cpg.audit(week=2)
    assert errors == [], errors


def test_paused_scheduler_in_graded_window_is_an_error(world):
    state, _ = world
    state["s-shadow-k1-route-roleunion-early"]["state"] = "PAUSED"
    errors, _, _ = cpg.audit(week=2)
    assert any("not ENABLED" in e and "s-shadow-k1-route-roleunion-early" in e for e in errors), errors


def test_missing_scheduler_is_an_error(world):
    """A deleted job must not read as 'fine'; absence is the loudest silence."""
    state, _ = world
    del state["s-shadow-k1-roleunion-late"]
    errors, _, _ = cpg.audit(week=2)
    assert any("MISSING" in e for e in errors), errors


def test_off_policy_job_is_an_error(world):
    """The exact 2026-09-18 failure: armed, but comparing a policy we do not run."""
    _, envs = world
    envs["job-for-s-shadow-k1-roleunion-early"] = {"N_BOOM": "28"}
    errors, _, _ = cpg.audit(week=2)
    assert any("contradicts the declared policy" in e for e in errors), errors


def test_unclassified_shadow_scheduler_is_an_error(world):
    state, _ = world
    state["s-shadow-brand-new-thing"] = {"state": "PAUSED", "schedule": "0 9 * * 7"}
    errors, _, _ = cpg.audit(week=2)
    assert any("UNCLASSIFIED" in e and "s-shadow-brand-new-thing" in e for e in errors), errors


def test_gate_outside_its_window_is_not_an_error(world, monkeypatch):
    """A gate more than the lookahead away is a note, never an error.

    2026-09-22: this used to lean on sis-pass-tail being the far-off gate, so it broke
    when that row was ruled dormant. It now supplies its own far-off gate.
    """
    state, _ = world
    for s in cpg.GATES["fp-route-share-2026"]["schedulers"]:
        state[s]["state"] = "PAUSED"
    gate = {"doc": "scripts/check_prospective_gates.py", "first_week": 12, "last_week": 18,
            "floor_weeks": None, "schedulers": ["s-synthetic-faroff"], "require_env": None,
            "adjudicates": "synthetic", "in_season_value": None, "note": "test fixture"}
    monkeypatch.setitem(cpg.GATES, "synthetic-faroff-2026", gate)
    state["s-synthetic-faroff"] = {"state": "PAUSED", "schedule": "0 0 * * 7"}
    _as_of(world[1], 1)
    errors, _, notes = cpg.audit(week=1)
    assert errors == [], errors
    assert any("dormant this week" in n for n in notes), notes


def test_upcoming_gate_warns_but_does_not_fail(world, monkeypatch):
    """Two weeks of warning before a gate starts grading, so there is time to fix it.

    2026-09-22: this used to reach into the real sis-pass-tail entry, so it tested a
    registry row rather than the lookahead mechanism and broke when that row was ruled
    dormant. It now injects its own upcoming gate and tests the behaviour.
    """
    state, _ = world
    gate = {"doc": "scripts/check_prospective_gates.py", "first_week": 5, "last_week": 18,
            "floor_weeks": None, "schedulers": ["s-synthetic-upcoming"], "require_env": None,
            "adjudicates": "synthetic", "in_season_value": None, "note": "test fixture"}
    monkeypatch.setitem(cpg.GATES, "synthetic-upcoming-2026", gate)
    state["s-synthetic-upcoming"] = {"state": "PAUSED", "schedule": "0 0 * * 7"}
    errors, warnings, _ = cpg.audit(week=3)
    assert not any("synthetic-upcoming" in e for e in errors), errors
    assert any("synthetic-upcoming" in w and "not ENABLED" in w for w in warnings), warnings


def test_paused_input_trainer_in_graded_window_is_an_error(world):
    """The 2026-09-22 failure: shadows ENABLED, their weekly trainers PAUSED since August,
    so every graded week would have compared August models."""
    state, _ = world
    state["s-train-k1-route"]["state"] = "PAUSED"
    errors, _, _ = cpg.audit(week=3)
    assert any("not ENABLED" in e and "s-train-k1-route" in e for e in errors), errors


def test_sis_pass_tail_gate_warns_before_week_5_and_fails_from_week_5(world):
    state, _ = world
    for s in cpg.GATES["sis-pass-tail-2026"]["schedulers"]:
        state[s]["state"] = "PAUSED"
    errors, warnings, _ = cpg.audit(week=3)
    assert not any("sis-pass-tail-2026" in e for e in errors), errors
    assert any("sis-pass-tail-2026" in w and "not ENABLED" in w for w in warnings), warnings
    errors, _, _ = cpg.audit(week=5)
    assert any("sis-pass-tail-2026" in e and "not ENABLED" in e for e in errors), errors


SIS_JOBS = ("job-for-s-tabpfn-sis-pass-tail-control",
            "job-for-s-tabpfn-sis-pass-tail-treatment",
            "job-for-s-shadow-sis-pass-tail-paired")
SIS_KEYS = ("sis-pass-tail-2026", "sis-pass-tail-2026-companion-v1")


def test_sis_pass_tail_contract_is_split(world):
    """O-3 Amendment 1: the unrunnable 15de4020 pin became two declared contracts."""
    _, envs = world
    dist = cpg.GATES["sis-pass-tail-2026"]
    comp = cpg.GATES["sis-pass-tail-2026-companion-v1"]
    assert dist["superseded_require_env"] == {
        "CODE_SHA": "15de40206963b5db9e6a4acff0f865833678d44d"}
    assert dist["require_env"] == {"SIS_PASS_TAIL_CONTRACT": "pass-tail-v1-a1"}
    assert comp["require_env"]["SIS_PASS_TAIL_CONTRACT"] == "pass-tail-v1-a1-companion"
    assert (comp["require_env"]["N_BOOM"], comp["require_env"]["N_LEV"]) == ("160", "40")
    assert dist["in_season_value"] is False and comp["in_season_value"] is True
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert not any(e.startswith(SIS_KEYS) for e in errors), errors
    # Today's deployed env (the 15de4020 jobs: no contract) contradicts both, per job.
    for job in SIS_JOBS:
        envs[job].pop("SIS_PASS_TAIL_CONTRACT")
    errors, _, _ = cpg.audit(week=5, now=NOW)
    hits = [e for e in errors if e.startswith(SIS_KEYS)
            and "contradicts the declared policy" in e]
    assert len(hits) == 3, errors


def test_sis_paired_job_on_the_august_generation_is_an_error(world):
    _, envs = world
    envs[SIS_JOBS[2]].update({"N_BOOM": "40", "N_LEV": ""})
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert any(e.startswith("sis-pass-tail-2026-companion-v1:") and "N_BOOM" in e
               for e in errors), errors


def test_sis_cache_job_with_the_other_arms_env_is_an_error(world):
    _, envs = world
    envs[SIS_JOBS[0]]["TABPFN_SIS_PASS_TAIL_LIVE_ARM"] = "treatment"
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert any(SIS_JOBS[0] in e and "TABPFN_SIS_PASS_TAIL_LIVE_ARM" in e
               for e in errors), errors


def test_sis_jobs_must_share_one_code_sha(world):
    """The paired job reads the caches: the three jobs are ONE build or nothing."""
    _, envs = world
    envs[SIS_JOBS[2]]["CODE_SHA"] = "beef" * 10
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert any(e.startswith("sis-pass-tail-2026-companion-v1:")
               and "must carry ONE CODE_SHA" in e for e in errors), errors
    envs[SIS_JOBS[2]]["CODE_SHA"] = envs[SIS_JOBS[0]]["CODE_SHA"]
    envs[SIS_JOBS[1]]["CODE_SHA"] = "beef" * 10
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert any(e.startswith("sis-pass-tail-2026:") and "must carry ONE CODE_SHA" in e
               for e in errors), errors
    envs[SIS_JOBS[1]].pop("CODE_SHA")
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert any("must carry ONE CODE_SHA" in e and "<unset>" in e for e in errors), errors


def test_sis_paused_cache_input_fails_the_companion(world):
    state, _ = world
    state["s-tabpfn-sis-pass-tail-treatment"]["state"] = "PAUSED"
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert any(e.startswith("sis-pass-tail-2026-companion-v1:") and "not ENABLED" in e
               for e in errors), errors


def test_sis_job_on_an_image_without_the_pool_fix_is_an_error(world, monkeypatch):
    """O-27 class: 15de4020 predates 193e1b44, so a Sunday run would read the stale
    full-week draft group after a Thursday game -- an invalid week that looks complete."""
    monkeypatch.setattr(cpg, "code_contains",
                        lambda code_sha, commit: not commit.startswith("193e1b44"))
    errors, _, _ = cpg.audit(week=5, now=NOW)
    hits = [e for e in errors if e.startswith(SIS_KEYS) and "193e1b44" in e]
    assert len(hits) == 3, errors
    errors, warnings, _ = cpg.audit(week=3, now=NOW)
    assert not any(e.startswith(SIS_KEYS) and "193e1b44" in e for e in errors)
    assert any(w.startswith(SIS_KEYS) and "193e1b44" in w for w in warnings)


def test_code_contains_reads_real_git_history():
    """15de4020 (the registered build) lacks both required fixes; the line has them."""
    spec = cpg.GATES["sis-pass-tail-2026-companion-v1"]["require_code_ancestors"]
    old = "15de40206963b5db9e6a4acff0f865833678d44d"
    if cpg.code_contains(old, old) is None:
        pytest.skip("git history unavailable")
    for commit in spec:
        assert cpg.code_contains(old, commit) is False, commit
        assert cpg.code_contains("HEAD", commit) is True, commit


def test_every_dormant_entry_carries_a_reason():
    """The dormant list stops a scheduler being audited, so it must justify itself."""
    for name, reason in cpg.DORMANT.items():
        assert isinstance(reason, str) and len(reason.strip()) > 20, name


def test_every_gate_names_a_doc_that_exists():
    root = Path(__file__).resolve().parents[1]
    for gate, spec in cpg.GATES.items():
        assert (root / spec["doc"]).is_file(), f"{gate} names a missing doc: {spec['doc']}"


# --- O-25 / O-27 (2026-10-05): the companion contract and run outcomes -----------------

ROUTE_JOBS = ("job-for-s-shadow-k1-roleunion-early", "job-for-s-shadow-k1-route-roleunion-early")


def test_original_route_share_key_keeps_its_contract_and_verdict_text():
    spec = cpg.GATES["fp-route-share-2026"]
    assert spec["require_env"] == {"N_BOOM": "160", "N_LEV": "40"}
    assert spec["first_week"] == 2 and spec["last_week"] == 18
    assert spec["adjudicates"].startswith("gate verdict after ALL of weeks 2-18")


def test_companion_registry_equals_the_image_guard_contract():
    """One contract, three places (guard, registry, update command): they cannot diverge."""
    from nfl_dfs.inference import tail_shadow

    spec = cpg.GATES["fp-route-share-2026-companion-v1"]
    assert spec["require_env"] == tail_shadow.route_share_job_environment("companion-v1")
    assert spec["require_env"]["ROUTE_SHARE_CONTRACT"] == "companion-v1"
    assert {k: spec["require_env"][k] for k in ("N_BOOM", "N_LEV", "N_CE")} == {
        "N_BOOM": "160", "N_LEV": "40", "N_CE": "0"}  # companion section 2
    assert spec["schedulers"] == cpg.GATES["fp-route-share-2026"]["schedulers"]
    assert spec["in_season_value"] is True
    root = Path(__file__).resolve().parents[1]
    assert (root / spec["policy_doc"]).is_file()


def test_todays_mixed_env_contradicts_the_companion(world):
    """The live Weeks 3-4 env (N_CE=12, budget 52 beside N_BOOM=160) is not companion v1."""
    _, envs = world
    for job in ROUTE_JOBS:
        envs[job].update({"N_CE": "12", "GEN_TOTAL_BUDGET": "52"})
        envs[job].pop("ROUTE_SHARE_CONTRACT")
    errors, _, _ = cpg.audit(week=5, now=NOW)
    hits = [e for e in errors if e.startswith("fp-route-share-2026-companion-v1:")
            and "contradicts the declared policy" in e]
    assert len(hits) == 2, errors
    assert all("N_CE" in e and "ROUTE_SHARE_CONTRACT" in e for e in hits), hits
    assert not any(e.startswith("fp-route-share-2026:") for e in errors), errors


def test_original_key_is_superseded_from_week_5_and_says_why(world, monkeypatch):
    """From W5 only the companion key audits the four schedulers: one failure, one line."""
    state, _ = world
    spec = cpg.GATES["fp-route-share-2026"]
    assert spec["superseded_from_week"] == 5
    assert spec["superseded_by"] == "fp-route-share-2026-companion-v1"
    assert spec["superseded_reason"] == (
        "superseded by fp-route-share-2026-companion-v1 from W5; W2 under the old contract, "
        "W3-W4 failed (O-25); history kept")
    successor = cpg.GATES[spec["superseded_by"]]
    assert successor["first_week"] == spec["superseded_from_week"]
    assert set(spec["schedulers"]) <= set(successor["schedulers"])
    state["s-shadow-k1-roleunion-early"]["state"] = "PAUSED"
    monkeypatch.setattr(cpg, "job_executions",
                        lambda j: [_execution("dead", "False", NOW_MINUS(6))])
    for week in (5, 6, 18):
        errors, _, notes = cpg.audit(week=week, now=NOW)
        assert not any(e.startswith("fp-route-share-2026:") for e in errors), errors
        assert any(e.startswith("fp-route-share-2026-companion-v1:") and "not ENABLED" in e
                   for e in errors), errors
        assert any(n.startswith("fp-route-share-2026: SUPERSEDED from week 5") and
                   "W3-W4 failed (O-25)" in n for n in notes), notes


def test_original_key_still_audits_before_week_5(world):
    state, _ = world
    state["s-shadow-k1-roleunion-early"]["state"] = "PAUSED"
    errors, _, _ = cpg.audit(week=4, now=NOW)
    assert any(e.startswith("fp-route-share-2026:") and "not ENABLED" in e
               for e in errors), errors


def test_companion_records_the_insufficient_rule(world):
    spec = cpg.GATES["fp-route-share-2026-companion-v1"]
    weeks = spec["last_week"] - spec["first_week"] + 1
    assert (weeks, spec["floor_weeks"]) == (14, 12)
    assert spec["max_missed_weeks"] == weeks - spec["floor_weeks"] == 2
    assert "INSUFFICIENT" in spec["insufficient_rule"]
    _, _, notes = cpg.audit(week=5, now=NOW)
    assert any("fp-route-share-2026-companion-v1: may lose at most 2" in n for n in notes)


def test_failed_newest_execution_is_an_error(world, monkeypatch):
    """O-25: ENABLED and on-policy, yet every run died at the image guard."""
    failing = {j: [_execution(f"{j}-b", "False", NOW_MINUS(6)),
                   _execution(f"{j}-a", "False", NOW_MINUS(6.1))] for j in ROUTE_JOBS}
    monkeypatch.setattr(cpg, "job_executions",
                        lambda j: failing.get(j, [_execution("ok", "True", NOW_MINUS(1))]))
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert any("newest finished execution FAILED" in e and f"{ROUTE_JOBS[0]}-b" in e
               for e in errors), errors


def test_success_after_failures_passes_but_reports_the_lost_runs(world, monkeypatch):
    rows = [_execution("dry-ok", "True", NOW_MINUS(2)),
            _execution("sun-late", "False", NOW_MINUS(6)),
            _execution("sun-early", "False", NOW_MINUS(6.1))]
    monkeypatch.setattr(cpg, "job_executions", lambda j: rows)
    errors, _, notes = cpg.audit(week=5, now=NOW)
    assert not any("FAILED" in e for e in errors), errors
    assert any("sun-late" in n and "sun-early" in n for n in notes), notes


def test_running_execution_does_not_mask_a_failed_one(world, monkeypatch):
    rows = [_execution("running", None, NOW_MINUS(0.1)),
            _execution("dead", "False", NOW_MINUS(1))]
    monkeypatch.setattr(cpg, "job_executions", lambda j: rows)
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert any("FAILED (dead)" in e for e in errors), errors


def test_no_execution_within_cadence_after_a_graded_week_is_an_error(world, monkeypatch):
    monkeypatch.setattr(cpg, "job_executions",
                        lambda j: [_execution("old", "True", NOW_MINUS(30))])
    # W6: the companion graded W5, so a run must have finished within the cadence.
    errors, _, _ = cpg.audit(week=6, now=NOW)
    assert any(e.startswith("fp-route-share-2026-companion-v1:")
               and "no finished execution within 8 days" in e for e in errors), errors
    # W5: its first graded week; nothing was owed last week.
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert not any(e.startswith("fp-route-share-2026-companion-v1:")
                   and "no finished execution" in e for e in errors), errors


def test_unreadable_execution_history_is_an_error(world, monkeypatch):
    monkeypatch.setattr(cpg, "job_executions", lambda j: None)
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert any("could not read its executions" in e for e in errors), errors


def test_dormant_but_enabled_failing_job_is_an_error(world, monkeypatch):
    """O-27: DORMANT said 'ENABLED and running' while every run failed."""
    state, _ = world
    name = "s-shadow-archetype-paired-early"
    assert name in cpg.DORMANT
    state[name]["state"] = "ENABLED"
    monkeypatch.setattr(
        cpg, "job_executions",
        lambda j: ([_execution("dead", "False", NOW_MINUS(6))]
                   if j == f"job-for-{name}"
                   else [_execution("ok", "True", NOW_MINUS(1))]))
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert any(f"DORMANT-but-ENABLED {name}" in e and "FAILED" in e for e in errors), errors
    # Paused, the same failing history is not this check's business.
    state[name]["state"] = "PAUSED"
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert not any("DORMANT-but-ENABLED" in e for e in errors), errors


def test_enabled_scheduler_may_not_be_dormant_even_when_its_runs_succeed(world):
    """O-9/O-27: 'dormant' exempts a job from every gate check, so it may not fire."""
    state, _ = world
    name = "s-shadow-k1-early"
    state[name]["state"] = "ENABLED"
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert any(f"DORMANT-but-ENABLED {name}" in e and "may not fire" in e
               for e in errors), errors


# --- O-27: the CBWU-OI pair is a gate, not a dormant job -----------------------------

CBWU = "cbwu-oi-2026-companion-v1"
FROZEN = "cbwu-oi-2026"
CBWU_JOBS = ("job-for-s-shadow-cbwu-oi-paired-early", "job-for-s-shadow-cbwu-oi-paired-late")


def test_cbwu_oi_schedulers_are_a_gate_not_dormant():
    for key in (CBWU, FROZEN):
        spec = cpg.GATES[key]
        assert spec["schedulers"] == ["s-shadow-cbwu-oi-paired-early",
                                      "s-shadow-cbwu-oi-paired-late"]
        assert not set(spec["schedulers"]) & set(cpg.DORMANT)
        assert spec["require_code_ancestors"] == cpg.POOL_FIX_193E1B44
    companion = cpg.GATES[CBWU]
    assert (companion["first_week"], companion["last_week"]) == (5, 18)
    assert companion["in_season_value"] is True
    assert companion["policy_doc"] == "reports/2026-09-19-in-season-adoption-track.md"


def test_frozen_cbwu_oi_key_is_superseded_from_week_5_and_says_why(world):
    spec = cpg.GATES[FROZEN]
    assert spec["superseded_from_week"] == 5 and spec["superseded_by"] == CBWU
    assert spec["superseded_reason"] == (
        "operator 2026-10-04: moved to the current policy; the frozen 160/40 comparison "
        "ends (W1 only), not adjudicated")
    assert spec["require_env"] == {"CBWU_OI_CONTRACT": "2026-cbwu-oi-v1"}
    errors, _, notes = cpg.audit(week=5, now=NOW)
    assert not any(e.startswith(f"{FROZEN}:") for e in errors), errors
    assert any(n.startswith(f"{FROZEN}: SUPERSEDED from week 5") for n in notes), notes


def test_cbwu_oi_registry_equals_the_runner_contract():
    """The checker, verify_deployment and the runner name ONE derived contract."""
    from nfl_dfs.inference import prospective_shadow as ps

    assert cpg.GATES[CBWU]["require_env"] == ps.cbwu_oi_job_environment(
        ps.CBWU_OI_COMPANION_V1)
    assert cpg.GATES[FROZEN]["require_env"] == ps.cbwu_oi_job_environment(
        ps.CBWU_OI_FROZEN_V1)


def test_cbwu_oi_job_on_the_frozen_contract_is_an_error_from_week_5(world):
    _, envs = world
    for job in CBWU_JOBS:
        envs[job]["CBWU_OI_CONTRACT"] = "2026-cbwu-oi-v1"
        envs[job]["N_BOOM"] = "40"
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert any(e.startswith(f"{CBWU}:") and "contradicts the declared policy" in e
               for e in errors), errors


def test_cbwu_oi_job_without_its_contract_is_an_error(world):
    _, envs = world
    for job in CBWU_JOBS:
        envs[job].pop("CBWU_OI_CONTRACT")
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert any(e.startswith(f"{CBWU}:") and "contradicts the declared policy" in e
               for e in errors), errors


def test_stale_image_is_an_error(world, monkeypatch):
    """The O-27 root cause: a job pinned to an image that predates the pool fix."""
    monkeypatch.setattr(cpg, "code_contains",
                        lambda code_sha, commit: code_sha != "918f5574ee9f")
    _, envs = world
    envs[CBWU_JOBS[0]]["CODE_SHA"] = "918f5574ee9f"
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert any(e.startswith(f"{CBWU}:") and "predates required fix 193e1b44" in e
               for e in errors), errors
    # Only the stale job is named; the up-to-date sibling is not.
    assert all(CBWU_JOBS[1] not in e for e in errors if "predates" in e), errors


def test_unverifiable_or_missing_code_sha_is_an_error(world, monkeypatch):
    _, envs = world
    envs[CBWU_JOBS[0]].pop("CODE_SHA")
    monkeypatch.setattr(cpg, "code_contains", lambda code_sha, commit: None)
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert any("declares no CODE_SHA" in e for e in errors), errors
    assert any("cannot tell whether CODE_SHA" in e for e in errors), errors


def test_companion_pair_also_requires_the_pool_fix(world, monkeypatch):
    """Rule 4 sweep: the Route Share pair builds from the same live pool query."""
    monkeypatch.setattr(cpg, "code_contains", lambda code_sha, commit: False)
    errors, _, _ = cpg.audit(week=5, now=NOW)
    assert any(e.startswith("fp-route-share-2026-companion-v1:") and "predates" in e
               for e in errors), errors


def test_frozen_cbwu_oi_lost_weeks_are_reported_while_it_audits(world):
    _, envs = world
    _as_of(envs, 4)
    _, _, notes = cpg.audit(week=4, now=NOW)
    assert sum(n.startswith(f"{FROZEN}: week ") and "no frozen panel" in n
               for n in notes) == 3, notes


def test_todays_cbwu_oi_job_fails_three_ways(world, monkeypatch):
    """Reproduce the live 10-04 state: old image, no contract, every run failed."""
    monkeypatch.setattr(cpg, "code_contains",
                        lambda code_sha, commit: not code_sha.startswith("918f5574"))
    _, envs = world
    for job in CBWU_JOBS:
        envs[job] = {"GCP_PROJECT": "nfl-predictions-503414",
                     "CODE_SHA": "918f5574ee9f8f9be68b194994cf897c06706c8d"}
    monkeypatch.setattr(
        cpg, "job_executions",
        lambda j: ([_execution("shadow-cbwu-oi-paired-xjrm9", "False", NOW_MINUS(6))]
                   if j in CBWU_JOBS else [_execution("ok", "True", NOW_MINUS(1))]))
    errors, _, _ = cpg.audit(week=5, now=NOW)
    mine = [e for e in errors if e.startswith(f"{CBWU}:")]
    assert any("contradicts the declared policy" in e for e in mine), mine
    assert any("predates required fix" in e for e in mine), mine
    assert any("FAILED (shadow-cbwu-oi-paired-xjrm9)" in e for e in mine), mine


def test_code_contains_reads_real_ancestry():
    """Against this repository: the 09-06 image lacks the fix, the fix contains itself."""
    fix = next(iter(cpg.POOL_FIX_193E1B44))
    stale = cpg.code_contains("918f5574ee9f8f9be68b194994cf897c06706c8d", fix)
    if stale is None:
        pytest.skip("shallow clone: the 2026-09 history is not available")
    assert stale is False
    assert cpg.code_contains(fix, fix) is True


def test_execution_outcome_reads_the_provider_shape():
    name, state, when = cpg.execution_outcome(_execution("x", "False", NOW_MINUS(1)))
    assert (name, state) == ("x", "FAILED") and when is not None
    assert cpg.execution_outcome(_execution("y", "True", NOW_MINUS(1)))[1] == "SUCCEEDED"
    assert cpg.execution_outcome(_execution("z", None, NOW_MINUS(1)))[1] == "RUNNING"
