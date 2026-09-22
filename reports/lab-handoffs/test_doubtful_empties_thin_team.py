"""Laptop -> nfl2: excluding "D" can empty a team's ACT skill set and hard-fail.

Run against nfl2 (NOT this repo):

    PYTHONPATH=<nfl2 worktree>/src <venv>/python -m pytest \
        reports/lab-handoffs/test_doubtful_empties_thin_team.py

At nfl2 69f98a7 the first test FAILS and the second PASSES. That is the defect:
apply_dk_status_invariant runs at scripts/live_week.py:79, before
apply_roster_status_invariant at :88, so a player who is roster-ACT and DK-"D" is
removed first -- and if he was his team's only ACT skill player, the roster
invariant then raises on a team that still has non-ACT skill rows.

NOT reachable for Week 3 draft group 153769: minimum 19 skill survivors per team
against a threshold of 1. Filed for after the slate, not as a Sunday blocker.
"""

import pandas as pd
import pytest

from nfl2.live import apply_dk_status_invariant, apply_roster_status_invariant


def _thin_team_frame():
    """A team whose only active-roster skill player is DK-Doubtful.

    The non-ACT team-mate matters: it keeps THIN in `source_teams` after the D
    removal, which is what turns a quiet drop into a raise.
    """
    return pd.DataFrame([
        dict(id="1", name="Thin Starter",  pos="WR", team="THIN",
             roster_status="ACT", status="D"),
        dict(id="2", name="Thin Practice", pos="WR", team="THIN",
             roster_status="INA", status=None),
        dict(id="3", name="Normal One",    pos="RB", team="OKAY",
             roster_status="ACT", status=None),
        dict(id="4", name="Normal Two",    pos="QB", team="OKAY",
             roster_status="ACT", status=None),
    ])


def test_dropping_doubtful_must_not_empty_a_teams_active_set():
    """Desired behaviour. FAILS at 69f98a7 -- this is the report.

    A guard should keep a D player whose removal would leave his team with zero
    ACT skill rows, and record the retention in the receipt.
    """
    fr, _ = apply_dk_status_invariant(_thin_team_frame())
    fr, _ = apply_roster_status_invariant(fr)          # raises RuntimeError today
    assert (fr.team == "THIN").sum() >= 1


def test_the_same_frame_was_fine_before_the_rule_changed(monkeypatch):
    """The failure is introduced by adding "D", not pre-existing."""
    import nfl2.live as live

    monkeypatch.setattr(live, "DK_INACTIVE_STATUSES", frozenset({"O", "OUT", "IR"}))
    fr, receipt = live.apply_dk_status_invariant(_thin_team_frame())
    assert receipt["removed"] == 0
    assert receipt["retained_designations"] == {"D": 1}
    fr, _ = live.apply_roster_status_invariant(fr)      # no raise under the old rule
    assert (fr.team == "THIN").sum() == 1
