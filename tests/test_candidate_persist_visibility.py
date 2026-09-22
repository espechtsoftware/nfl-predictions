"""The candidate write must not be able to vanish without trace.

`predictions.live_candidates` carries `lever_env` -- the only record of which
levers produced a book -- and held zero 2026 rows on 2026-09-21, so the Week-2
post-mortem could not say what generation consumed. The write runs on a
`daemon=True` thread, and a daemon thread is killed at interpreter exit, so a
build finishing shortly after starting the write discards it with no exception
and no log line.

Fire-and-forget is correct: a stalled warehouse call must never block a Sunday
build. These tests pin the weaker property that makes it survivable -- the
outcome is observable, and a caller may wait on its own terms.
"""

import threading
import time

import pytest

from nfl_dfs.backtest import engine


@pytest.fixture(autouse=True)
def _reset():
    engine._CANDIDATE_PERSIST.clear()
    engine._CANDIDATE_PERSIST.update({"state": "not_attempted"})
    engine._CANDIDATE_PERSIST_THREADS.clear()
    yield
    engine._CANDIDATE_PERSIST_THREADS.clear()


def test_status_starts_as_not_attempted():
    assert engine.candidate_persist_status()["state"] == "not_attempted"


def test_status_is_a_copy_not_the_live_dict():
    """A caller must not be able to corrupt the record it is reading."""
    s = engine.candidate_persist_status()
    s["state"] = "tampered"
    assert engine.candidate_persist_status()["state"] == "not_attempted"


def test_flush_waits_for_an_in_flight_write_and_reports_ok():
    done = threading.Event()

    def _slow():
        time.sleep(0.2)
        engine._CANDIDATE_PERSIST["state"] = "ok"
        done.set()

    engine._CANDIDATE_PERSIST.update({"state": "started"})
    th = threading.Thread(target=_slow, daemon=True)
    engine._CANDIDATE_PERSIST_THREADS.append(th)
    th.start()
    out = engine.flush_candidate_persistence(timeout=5.0)
    assert done.is_set()
    assert out["state"] == "ok"
    assert not engine._CANDIDATE_PERSIST_THREADS


def test_a_write_still_running_at_flush_deadline_is_reported_not_silent():
    """The daemon-abandonment case. It must surface as `timeout`, never as ok."""
    stop = threading.Event()

    def _hang():
        stop.wait(30)

    engine._CANDIDATE_PERSIST.update({"state": "started"})
    th = threading.Thread(target=_hang, daemon=True)
    engine._CANDIDATE_PERSIST_THREADS.append(th)
    th.start()
    try:
        out = engine.flush_candidate_persistence(timeout=0.2)
        assert out["state"] == "timeout", (
            "an unfinished candidate write reported something other than timeout; "
            "on a daemon thread that is indistinguishable from discarded")
        assert out["timeout_seconds"] == 0.2
    finally:
        stop.set()


def test_flush_is_harmless_when_nothing_was_attempted():
    assert engine.flush_candidate_persistence(timeout=0.1)["state"] == "not_attempted"
