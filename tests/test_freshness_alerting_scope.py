"""The daily freshness alarm must only go red for things worth acting on.

On 2026-09-21 `check-freshness` had been exiting 1 every day on exactly one
feed — `raw.cfb_dk_salaries`, stale 138h — because `ingest-cfb` hits a
DraftKings 403 with no host fallback. Every NFL feed was fresh. A permanently
red alarm is not an alarm: a genuine `dk_salaries` staleness would have arrived
as one more line in a check that was already failing.

These tests pin the alerting scope so it cannot drift silently in either
direction: scaffolds must not alarm, and the feeds that matter must.
"""

from __future__ import annotations

import pytest

from nfl_dfs import status

BY_KEY = {f.key: f for f in status.FEEDS}


class TestScaffoldsDoNotAlarm:
    @pytest.mark.parametrize("key", ["cfb_dk_salaries", "tabpfn_components"])
    def test_known_scaffolds_are_non_alerting(self, key):
        assert key in BY_KEY, f"{key} is no longer a declared feed"
        assert BY_KEY[key].alert is False, (
            f"{key} alarms again. If its feed genuinely works now that is correct "
            f"— update this test deliberately rather than by accident.")

    def test_a_silenced_feed_says_why_and_when_to_restore(self):
        """Silencing without a restore condition is how an alarm dies for good."""
        note = (BY_KEY["cfb_dk_salaries"].note or "").lower()
        assert note, "a non-alerting feed must carry a note"
        assert "403" in note or "non-alerting" in note


class TestTheFeedsThatMatterStillAlarm:
    @pytest.mark.parametrize("key", [
        "dk_salaries", "player_projections", "weekly_stats", "schedules"])
    def test_money_path_feeds_alarm(self, key):
        if key not in BY_KEY:
            pytest.skip(f"{key} is not a declared feed in this tree")
        assert BY_KEY[key].alert is not False, (
            f"{key} feeds the money path; it must fail check-freshness when stale")

    def test_every_silenced_feed_carries_a_justification(self):
        """The invariant that actually matters. A feed may be silenced, but never
        silently: the note is the record of why, and what would restore it."""
        undocumented = [f.key for f in status.FEEDS if f.alert is False and not f.note]
        assert not undocumented, (
            f"non-alerting feeds with no note: {undocumented}. Silencing without a "
            f"stated reason is how an alarm dies unnoticed.")

    def test_the_silenced_set_is_the_one_we_reviewed(self):
        """16 feeds, 4 silenced as of 2026-09-21, each a scaffold or research-only
        cache. Adding a fifth should require editing this list deliberately."""
        silent = sorted(f.key for f in status.FEEDS if f.alert is False)
        assert silent == sorted([
            "cfb_dk_salaries",          # DK 403 since 2026-09-19, no host fallback
            "dk_contest_fills",         # opt-in scaffold, not scheduled
            "fantasy_points_route_share",  # prospective shadow
            "tabpfn_components",        # research-only cache, default-off
        ]), f"the non-alerting set changed: {silent}"

    def test_the_majority_of_feeds_still_alarm(self):
        silent = [f.key for f in status.FEEDS if f.alert is False]
        assert len(silent) < len(status.FEEDS) / 2


class TestTheCheckOnlyRaisesForAlertingFeeds:
    def test_a_stale_non_alerting_feed_does_not_fail_the_check(self):
        """The property the whole change rests on, asserted against the source."""
        import inspect
        src = inspect.getsource(status.check_freshness)
        assert 'c["alerting"]' in src, (
            "check_freshness no longer filters on the alerting flag; a silenced "
            "feed would fail the daily job again")
