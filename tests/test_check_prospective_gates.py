"""Adversarial tests for the prospective-gate checker.

Each test breaks the world on purpose and asserts the checker NOTICES.  A test that
merely re-runs the check against the real project would prove nothing -- that is the
same silence the checker exists to end.
"""
from __future__ import annotations

import importlib.util
import sys
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
            envs[f"job-for-{s}"] = dict(gate["require_env"] or {})
    monkeypatch.setattr(cpg, "schedulers", lambda: state)
    monkeypatch.setattr(cpg, "scheduler_target", lambda s: f"job-for-{s}")
    monkeypatch.setattr(cpg, "job_env", lambda j: envs.get(j, {}))
    return state, envs


def test_healthy_world_passes(world):
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


def test_sis_pass_tail_gate_pins_the_frozen_code_identity(world):
    """Its policy is frozen in code, not env, so the contract is the protocol's CODE_SHA."""
    _, envs = world
    spec = cpg.GATES["sis-pass-tail-2026"]
    assert spec["require_env"] == {"CODE_SHA": "15de40206963b5db9e6a4acff0f865833678d44d"}
    envs["job-for-s-shadow-sis-pass-tail-paired"] = {"CODE_SHA": "deadbeef"}
    errors, _, _ = cpg.audit(week=5)
    assert any("contradicts the declared policy" in e for e in errors), errors


def test_every_dormant_entry_carries_a_reason():
    """The dormant list stops a scheduler being audited, so it must justify itself."""
    for name, reason in cpg.DORMANT.items():
        assert isinstance(reason, str) and len(reason.strip()) > 20, name


def test_every_gate_names_a_doc_that_exists():
    root = Path(__file__).resolve().parents[1]
    for gate, spec in cpg.GATES.items():
        assert (root / spec["doc"]).is_file(), f"{gate} names a missing doc: {spec['doc']}"
