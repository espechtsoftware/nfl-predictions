"""The blocker watch guards the Saturday prop landing. It must never be able to change
anything -- a reporter that can mutate is a reporter nobody dares run on a timer."""
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "week3_blocker_watch.sh"

# verbs that write, start, or destroy. `bq query` is read-only; `bq load`/`bq rm` are not.
MUTATING = [
    "bq load", "bq rm", "bq mk", "bq cp", "bq insert",
    "jobs execute", "jobs deploy", "jobs update", "jobs delete",
    "schedulers resume", "scheduler jobs resume", "scheduler jobs pause",
    "gsutil rm", "gsutil cp", "gcloud storage rm",
    "INSERT INTO", "DELETE FROM", "UPDATE ", "CREATE OR REPLACE", "TRUNCATE", "MERGE ",
    "systemd-run", "nohup", "setsid", "git push", "git checkout",
]


def test_the_script_exists_and_is_executable():
    assert SCRIPT.is_file(), "the watch must be tracked, not live in a session cron"
    assert SCRIPT.stat().st_mode & 0o111, SCRIPT


def test_the_watch_cannot_write_start_or_destroy_anything():
    body = SCRIPT.read_text()
    # the arming instructions are a COMMENT; strip comments before scanning.
    code = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    found = [v for v in MUTATING if v.lower() in code.lower()]
    assert not found, f"the watch must stay read-only; found {found}"


@pytest.mark.parametrize("needle", ["rosters_weekly", "prop_lines", "prop_match_preflight"])
def test_it_watches_both_blockers_and_names_the_tool(needle):
    """Rosters alone was the error: props are the binding constraint and land Saturday."""
    assert needle in SCRIPT.read_text(), needle


def test_it_carries_the_model_only_batch_trap():
    """Between rosters landing and props landing, project-slate SUCCEEDS and writes a
    100%-model batch. A future reader must not mistake that for success."""
    body = SCRIPT.read_text()
    assert "100%" in body and "NOT a good batch" in body


def test_it_emits_one_machine_readable_line():
    """So a timer's log can be grepped without parsing prose."""
    assert 'week3-blocker-watch season=' in SCRIPT.read_text()
