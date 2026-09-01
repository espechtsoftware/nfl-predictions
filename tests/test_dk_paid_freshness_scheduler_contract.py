"""Deployment contract for the paid DraftKings salary freshness boundary."""

from __future__ import annotations

import re
from pathlib import Path

from nfl_dfs.optimizer.paid_classic_book_v2 import (
    PAID_CLASSIC_CATALOG_MAX_AGE,
)


ROOT = Path(__file__).resolve().parents[1]


def test_live_dk_scheduler_supports_paid_catalog_freshness_boundary() -> None:
    """The sole DK scheduler must refresh faster than the paid max age."""

    deploy = (ROOT / "deploy/deploy_jobs.sh").read_text(encoding="utf-8")
    setup = (ROOT / "infra/setup_schedule.sh").read_text(encoding="utf-8")
    deploy_schedules = re.findall(
        r'^sched\s+s-dk\s+ingest-dk\s+"([^"]+)"$',
        deploy,
        flags=re.MULTILINE,
    )
    setup_schedules = re.findall(
        r'^sched\s+s-dk\s+"([^"]+)"\s+ingest-dk\b',
        setup,
        flags=re.MULTILINE,
    )

    assert deploy_schedules == ["0 * * * 3-7"]
    assert setup_schedules == deploy_schedules
    assert '--time-zone "America/Chicago"' in deploy
    assert '--time-zone "America/Chicago"' in setup
    scheduler_interval_seconds = 60 * 60
    assert scheduler_interval_seconds < (
        PAID_CLASSIC_CATALOG_MAX_AGE.total_seconds()
    )


def test_design_guide_describes_the_deployed_paid_dk_cadence() -> None:
    guide = (ROOT / "docs/design-guide.md").read_text(encoding="utf-8")

    assert "`s-dk` runs hourly Wednesday-Sunday" in guide
    assert "DK slates 1×/day" not in guide
