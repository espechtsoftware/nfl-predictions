"""Static safety contract for the collection-only CFB deployment."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy/deploy_jobs.sh"


def _schedule(source: str, scheduler: str) -> str:
    matches = re.findall(
        rf'^sched\s+{re.escape(scheduler)}\s+ingest-cfb\s+"([^"]+)"$',
        source,
        flags=re.MULTILINE,
    )
    assert len(matches) == 1
    return matches[0]


def _hours(schedule: str) -> set[int]:
    minute, hour_field, *_ = schedule.split()
    assert minute == "0"
    hours = set()
    for part in hour_field.split(","):
        if "-" in part:
            start, end = map(int, part.split("-", maxsplit=1))
            hours.update(range(start, end + 1))
        else:
            hours.add(int(part))
    return hours


def test_cfb_job_has_zero_retries_without_changing_the_default() -> None:
    source = DEPLOY.read_text(encoding="utf-8")

    assert "max_retries=${8:-1}" in source
    assert '--max-retries "$max_retries"' in source
    assert re.search(
        r'^job\s+ingest-cfb\s+ingest-cfb\s+2Gi\s+1\s+'
        r'"INGEST_CFB_ENABLED=1"\s+""\s+3600\s+0$',
        source,
        flags=re.MULTILINE,
    )


def test_cfb_schedules_do_not_overlap_on_saturday() -> None:
    source = DEPLOY.read_text(encoding="utf-8")
    daily = _schedule(source, "s-cfb")
    saturday = _schedule(source, "s-cfb-sat")

    assert daily == "0 10,14,18 * * *"
    assert saturday == "0 8,9,11,12,13 * * 6"
    assert _hours(daily).isdisjoint(_hours(saturday))


def test_nfl_contest_capture_is_declarative_and_nonretrying() -> None:
    source = DEPLOY.read_text(encoding="utf-8")

    assert re.search(
        r'^job\s+ingest-contests\s+ingest-contests\s+2Gi\s+1\s+'
        r'"INGEST_CONTESTS_ENABLED=1"\s+""\s+900\s+0$',
        source,
        flags=re.MULTILINE,
    )
    assert re.search(
        r'^sched\s+s-contests\s+ingest-contests\s+"0 10 \* \* 3-6"$',
        source,
        flags=re.MULTILINE,
    )
    assert re.search(
        r'^sched\s+s-contests-sun\s+ingest-contests\s+"0 6-11 \* \* 7"$',
        source,
        flags=re.MULTILINE,
    )


def test_us_dfs_capture_is_isolated_nonretrying_and_prelock() -> None:
    source = DEPLOY.read_text(encoding="utf-8")

    assert re.search(
        r'^job\s+ingest-us-dfs\s+ingest-us-dfs\s+2Gi\s+1\s+'
        r'"ODDS_US_DFS_ENABLED=1\|ODDS_US_DFS_MIN_REMAINING=5000"\s+'
        r'"ODDS_API_KEY=odds-api-key:latest"\s+900\s+0$',
        source,
        flags=re.MULTILINE,
    )
    assert re.search(
        r'^sched\s+s-us-dfs\s+ingest-us-dfs\s+"30 10 \* \* 3-6"$',
        source,
        flags=re.MULTILINE,
    )
    assert re.search(
        r'^sched\s+s-us-dfs-sun\s+ingest-us-dfs\s+'
        r'"30 6,8,10,11 \* \* 0"$',
        source,
        flags=re.MULTILINE,
    )
