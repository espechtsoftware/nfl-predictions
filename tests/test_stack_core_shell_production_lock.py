from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from run_stack_core_shell_production_lock import (  # noqa: E402
    SCORE_FREE_COMPLETION_URI,
    SCORE_FREE_REPORT_URI,
    SCORE_FREE_RUN_ID,
    _scorefree_license,
)
from run_stack_core_shell_scorefree import RUN_ID  # noqa: E402
from stack_core_shell_sources import (  # noqa: E402
    PROTOCOL_SHA256,
    SOURCE_PANELS,
    validate_local_sources,
)


class _Blob:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.size = len(raw)
        self.generation = "987"
        self.updated = datetime(2026, 8, 17, tzinfo=timezone.utc)

    def reload(self) -> None:
        return None

    def download_as_bytes(self) -> bytes:
        return self.raw


class _Bucket:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    def blob(self, name: str) -> _Blob:
        return _Blob(self.objects[name])


class _Client:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    def bucket(self, _name: str) -> _Bucket:
        return _Bucket(self.objects)


def _licensed_objects() -> tuple[_Client, str, str]:
    report = {
        "version": "stack-core-shell-scorefree-report-v1",
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": True,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_hashes": validate_local_sources(),
        "source_panels": list(SOURCE_PANELS),
        "disposition": "stack-core-shell-shadow-licensed",
        "gate": {
            "passes_scorefree_gate": True,
            "disposition": "stack-core-shell-shadow-licensed",
        },
        "mechanical": {
            "seasons": [2023, 2024, 2025], "slates": 54,
            "heldout_folds": 270, "worlds_per_fold": 10_000,
            "source_artifacts": 270, "all_valid": True,
        },
        "code_sha": "a" * 40,
        "analysis_image": "example@sha256:" + "b" * 64,
    }
    report_raw = (json.dumps(report, sort_keys=True) + "\n").encode()
    report_sha = sha256(report_raw).hexdigest()
    completion_raw = (
        f"run_id={SCORE_FREE_RUN_ID}\n"
        f"report_sha256={report_sha}\n"
        "disposition=stack-core-shell-shadow-licensed\n"
        "uses_realized_outcomes=false\n"
        "historical_scoring_licensed=true\n"
        "production_change_licensed=false\n"
        f"accepted_execution_ledger_sha256={'c' * 64}\n"
    ).encode()
    completion_sha = sha256(completion_raw).hexdigest()
    objects = {
        SCORE_FREE_REPORT_URI.split("/", 3)[-1]: report_raw,
        SCORE_FREE_COMPLETION_URI.split("/", 3)[-1]: completion_raw,
    }
    return _Client(objects), report_sha, completion_sha


def test_production_lock_requires_strict_positive_scorefree_license() -> None:
    client, report_sha, completion_sha = _licensed_objects()
    receipt = _scorefree_license(
        client, report_sha256=report_sha,
        completion_sha256=completion_sha,
    )
    assert receipt["disposition"] == "stack-core-shell-shadow-licensed"
    assert receipt["scorefree_execution_ledger_sha256"] == "c" * 64
    assert receipt["report"]["sha256"] == report_sha


def test_production_lock_rejects_unlicensed_scorefree_completion() -> None:
    client, report_sha, completion_sha = _licensed_objects()
    key = SCORE_FREE_COMPLETION_URI.split("/", 3)[-1]
    raw = client.objects[key].replace(
        b"historical_scoring_licensed=true",
        b"historical_scoring_licensed=false",
    )
    client.objects[key] = raw
    try:
        _scorefree_license(
            client,
            report_sha256=report_sha,
            completion_sha256=sha256(raw).hexdigest(),
        )
    except RuntimeError as exc:
        assert "completion differs" in str(exc)
    else:
        raise AssertionError("negative score-free completion was accepted")
