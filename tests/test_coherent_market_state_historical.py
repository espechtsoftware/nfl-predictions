from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

SCRIPTS = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from nfl_dfs.analysis.coherent_market_state_historical import (
    CANONICAL_FOLD,
    VERSION,
    aggregate_historical,
    score_slate,
)
import run_coherent_market_state_historical_score as runner  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


def _roster(offset: int) -> list[str]:
    return [f"p{offset + value}" for value in range(9)]


def _fold(season: int = 2023, week: int = 1) -> dict:
    control = [_roster(value * 9) for value in range(80)]
    treatment = deepcopy(control)
    treatment[-12:] = [_roster(1_000 + value * 9) for value in range(12)]
    return {
        "uses_realized_outcomes": False,
        "mechanical_valid": True,
        "season": season,
        "week": week,
        "heldout_block": CANONICAL_FOLD,
        "control_entries": 80,
        "treatment_entries": 80,
        "candidate_budget": 80,
        "control_candidate_rosters": control,
        "treatment_candidate_rosters": treatment,
        "control_selected_rosters": deepcopy(control),
        "treatment_selected_rosters": deepcopy(treatment),
        "added": [{
            "team": f"T{value // 4}",
            "state": "model" if value % 4 < 2 else "market",
            "state_index": value % 2 + 1,
            "roster": treatment[-12 + value],
        } for value in range(12)],
        "removed": [{"roster": control[-12 + value]} for value in range(12)],
    }


def _actuals() -> dict[str, float]:
    return {
        f"p{value}": (30.0 if value >= 1_000 else 20.0)
        for value in range(1_200)
    }


def test_score_slate_uses_one_exact80_canonical_fold() -> None:
    result = score_slate(_fold(), _actuals())
    assert result["version"] == VERSION
    assert result["canonical_fold"] == "R0"
    assert result["books"]["selected"]["control"]["rosters"] == 80
    assert result["books"]["selected"]["treatment"]["rosters"] == 80
    assert result["books"]["selected"]["control"]["maximum"] == 180.0
    assert result["books"]["selected"]["treatment"]["maximum"] == 270.0
    assert sum(row["selected"] for row in result["added"]) == 12


def test_score_slate_rejects_noncanonical_fold_and_selection_escape() -> None:
    fold = _fold()
    fold["heldout_block"] = "R1"
    try:
        score_slate(fold, _actuals())
    except ValueError as exc:
        assert "canonical fold" in str(exc)
    else:
        raise AssertionError("historical scorer accepted a selected fold")
    fold = _fold()
    fold["treatment_selected_rosters"][0] = _roster(900)
    try:
        score_slate(fold, _actuals())
    except ValueError as exc:
        assert "leaves candidates" in str(exc)
    else:
        raise AssertionError("historical scorer accepted an escaped selection")


def test_aggregate_applies_frozen_tail_gate_once_over_54_slates() -> None:
    rows = []
    actuals = _actuals()
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            rows.append(score_slate(_fold(season, week), actuals))
    report = aggregate_historical(rows)
    assert report["population"] == {
        "seasons": [2023, 2024, 2025], "slates": 54,
    }
    assert report["gate"]["selected_200_net"] == 54
    assert report["gate"]["candidate_200_net"] == 54
    assert report["gate"]["historical_tail_signal_positive"] is True
    assert len(report["leave_one_slate_out"]) == 54


def test_historical_protocol_and_upstream_receipt_are_frozen() -> None:
    assert sha256(runner.PROTOCOL.read_bytes()).hexdigest() == \
        runner.PROTOCOL_SHA256
    strict = {
        key: "a" * 64 for key in (
            "manifest", "primary_executions", "retry_executions",
            "accepted_executions", "attempt_resolution", "completion",
            "execution_metadata", "object_metadata", "shards", "report",
            "report_upload",
        )
    }

    def receipt(uri: str) -> dict:
        return {
            "uri": uri, "generation": "1", "sha256": "b" * 64,
            "bytes": 100, "updated": "2026-08-17T00:00:00Z",
        }

    accepted = []
    metadata = {}
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            job = f"coherent-state-s{season}-w{week}-v1"
            execution = f"{job}-primary"
            uri = f"{runner.UPSTREAM_PREFIX}/slate-{season}-{week}.json"
            accepted.append({
                "season": season, "week": week, "job": job,
                "execution": execution, "uri": uri,
            })
            metadata[execution] = {
                "metadata": {"name": execution},
                "spec": {
                    "parallelism": 1,
                    "taskCount": 1,
                    "template": {"spec": {
                        "containers": [{
                            "image": "example/image@sha256:" + "d" * 64,
                            "command": ["python"],
                            "args": [
                                "scripts/run_coherent_market_state_scorefree.py",
                                "--season", str(season), "--week", str(week),
                                "--output-uri", uri,
                            ],
                            "env": [
                                {"name": "CODE_SHA", "value": "c" * 40},
                                {"name": "ANALYSIS_IMAGE", "value": (
                                    "example/image@sha256:" + "d" * 64
                                )},
                            ],
                            "resources": {"limits": {
                                "cpu": "4", "memory": "16Gi",
                            }},
                        }],
                        "maxRetries": 0,
                        "timeoutSeconds": 14400,
                        "serviceAccountName": (
                            "817589974517-compute@developer.gserviceaccount.com"
                        ),
                    }},
                },
                "status": {
                    "conditions": [{"type": "Completed", "status": "True"}],
                    "succeededCount": 1, "failedCount": 0,
                    "completionTime": "2026-08-17T00:00:00Z",
                },
            }

    value = {
        "version": "coherent-market-state-historical-upstream-receipt-v1",
        "run_id": runner.UPSTREAM_RUN_ID,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": True,
        "code_sha": "c" * 40,
        "image": "example/image@sha256:" + "d" * 64,
        "primary_executions": 54,
        "accepted_execution_count": 54,
        "slates": 54,
        "folds": 270,
        "strict_harvest_sha256": strict,
        "report_object": receipt(f"{runner.UPSTREAM_PREFIX}/report.json"),
        "shard_objects": [
            {
                "season": season, "week": week,
                **receipt(
                    f"{runner.UPSTREAM_PREFIX}/slate-{season}-{week}.json"
                ),
            }
            for season in (2023, 2024, 2025) for week in range(1, 19)
        ],
        "accepted_executions": accepted,
        "execution_metadata": metadata,
    }
    runner._validate_upstream_receipt(value)
    value["shard_objects"][0]["generation"] = ""
    try:
        runner._validate_upstream_receipt(value)
    except RuntimeError as exc:
        assert "object receipt differs" in str(exc)
    else:
        raise AssertionError("historical scorer accepted mutable shard identity")


def test_historical_transport_waits_for_valid_full_scorefree_harvest() -> None:
    launcher = (
        ROOT / "scripts/cloud_coherent_market_state_historical_score.sh"
    ).read_text(encoding="utf-8")
    finisher = (
        ROOT / "scripts/cloud_finish_coherent_market_state_historical_score.sh"
    ).read_text(encoding="utf-8")
    watcher = (
        ROOT / "scripts/watch_coherent_market_state_historical_score_queue.sh"
    ).read_text(encoding="utf-8")
    runner_source = (
        ROOT / "scripts/run_coherent_market_state_historical_score.py"
    ).read_text(encoding="utf-8")
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    build = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    assert "validate_coherent_market_state_attempts.py" in launcher
    assert "historical_scoring_licensed" in launcher
    assert runner_source.index("_validate_upstream_receipt(receipt)") < \
        runner_source.index("sources = _query")
    assert runner_source.index("reproduced = aggregate_scorefree(paths)") < \
        runner_source.index("sources = _query")
    assert "--cpu 4 --memory 16Gi" in launcher
    assert "--max-retries 0 --task-timeout 2h" in launcher
    assert "gcloud storage cp" not in launcher
    assert "gcloud storage cp" in finisher
    assert watcher.index('UPSTREAM/completion.txt') < watcher.index(
        "cloud_coherent_market_state_historical_score.sh"
    )
    assert 'row.get("type") == "Completed"' in watcher
    assert "run_coherent_market_state_historical_score.py" in docker
    assert "run_coherent_market_state_historical_score.py --help" in build
    for script in (
        "cloud_coherent_market_state_historical_score.sh",
        "cloud_finish_coherent_market_state_historical_score.sh",
        "watch_coherent_market_state_historical_score_queue.sh",
    ):
        subprocess.run(
            ["bash", "-n", str(ROOT / "scripts" / script)], check=True,
        )
