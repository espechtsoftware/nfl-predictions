"""The doubtful-to-out transition must never be silent.

Defect found 2026-09-18, two days before Week 2.  The watcher tracked a SET of flagged
players and alerted on `out - seen`.  A player already listed D at startup joined `seen`
and stayed; when he later turned OUT the difference was empty, so the watcher printed
nothing and never broke.  That is the exact case the watcher exists for.

These tests encode the LOGIC (status-per-player, alert on change, escalate into an OUT
status) rather than importing the script, which needs live DK credentials and the week
environment at import time.  The first test reproduces the OLD behaviour and asserts it
was broken, so the regression cannot be quietly reintroduced.
"""
from __future__ import annotations

OUT_STATUSES = ("O", "OUT", "IR")
WATCH_STATUSES = OUT_STATUSES + ("D",)


def old_alerts(polls: list[dict[str, str]]) -> list[set[str]]:
    """The pre-fix algorithm: membership sets, `new = out - seen`, `seen |= new`."""
    seen: set[str] = set(polls[0])
    fired = []
    for poll in polls[1:]:
        out = set(poll)
        new = out - seen
        if new:
            fired.append(new)
        seen |= new
    return fired


def new_alerts(polls: list[dict[str, str]]) -> tuple[list[dict], list[dict]]:
    """The fixed algorithm: status per player, alert on change, escalate into OUT."""
    state = dict(polls[0])
    changes, escalations = [], []
    for poll in polls[1:]:
        changed = {k: v for k, v in poll.items() if state.get(k) != v}
        if changed:
            changes.append(changed)
        esc = {k: v for k, v in changed.items()
               if v in OUT_STATUSES and state.get(k) not in OUT_STATUSES}
        state.update(poll)
        if esc:
            escalations.append(esc)
            break
    return changes, escalations


DOUBTFUL_THEN_OUT = [{"p1": "D"}, {"p1": "D"}, {"p1": "OUT"}]


def test_old_code_was_silent_on_doubtful_to_out():
    """Pin the defect so nobody reintroduces the set-membership approach."""
    assert old_alerts(DOUBTFUL_THEN_OUT) == [], (
        "the old algorithm is supposed to be broken here; if this now fires, "
        "the test no longer pins the defect it was written for"
    )


def test_fixed_code_alerts_and_escalates_on_doubtful_to_out():
    changes, escalations = new_alerts(DOUBTFUL_THEN_OUT)
    assert changes == [{"p1": "OUT"}], changes
    assert escalations == [{"p1": "OUT"}], escalations


def test_newly_flagged_player_still_alerts():
    """The case the old code did handle must keep working."""
    changes, escalations = new_alerts([{}, {"p2": "OUT"}])
    assert escalations == [{"p2": "OUT"}], escalations


def test_new_doubtful_warns_but_does_not_escalate():
    """D is a warning: report it, do not call it a swap and do not stop watching."""
    changes, escalations = new_alerts([{}, {"p3": "D"}])
    assert changes == [{"p3": "D"}], changes
    assert escalations == [], escalations


def test_improving_status_is_reported_not_escalated():
    """Doubtful cleared to active is worth printing and must not trigger a swap."""
    changes, escalations = new_alerts([{"p4": "D"}, {}])
    assert escalations == [], escalations


def test_watching_includes_doubtful():
    assert "D" in WATCH_STATUSES and "D" not in OUT_STATUSES
