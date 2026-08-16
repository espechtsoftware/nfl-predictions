import math
from pathlib import Path
import sys

import pytest

from nfl_dfs.analysis.atlas_historical_score import (
    THRESHOLDS,
    aggregate_diagnostic,
    canonical_roster,
    compare_slate,
    score_rosters,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from run_atlas_historical_score_diagnostic import (  # noqa: E402
    PLAYER_SQL,
    SOURCE_SQL,
    UPSTREAM_CODE_SHA,
    UPSTREAM_EXECUTION_NAMES,
    UPSTREAM_EXECUTIONS,
    UPSTREAM_IMAGE,
    UPSTREAM_PREFIX,
    _validate_execution,
)


def _roster(prefix: str, index: int):
    return canonical_roster(f"{prefix}-{index}-{slot}" for slot in range(9))


def _slate(season: int, week: int, treatment_score: float = 180.0):
    p1 = [_roster("native", index) for index in range(80)]
    atlas = [_roster("atlas", index) for index in range(200)]
    p2 = [*p1[:-1], atlas[0]]
    actual = {}
    for roster in [*p1, *atlas]:
        for player_id in roster:
            actual[player_id] = 20.0
    for player_id in atlas[0]:
        actual[player_id] = treatment_score / 9.0
    return compare_slate(
        season=season,
        week=week,
        p1_candidates=p1,
        p2_candidates=p2,
        p1_selected=p1,
        p2_selected=p2,
        actual_by_id=actual,
        atlas_rosters=atlas,
    )


def test_compare_slate_scores_equal_budget_and_atlas_conversion():
    row = _slate(2023, 1, 207.0)
    assert row["candidate_budget"] == 80
    assert row["books"]["P1"]["C"]["maximum"] == 180.0
    assert math.isclose(row["books"]["P2"]["C"]["maximum"], 207.0)
    assert row["books"]["P2"]["C"]["thresholds"]["200"] is True
    assert row["atlas"]["in_P2_candidates"] == 1
    assert row["atlas"]["in_P2_exact80"] == 1
    assert math.isclose(row["atlas"]["generated_maximum"], 207.0)
    assert row["candidate_treatment_only_crossings"]["200"] == {
        "treatment_only": True,
        "treatment_winner_is_atlas": True,
        "treatment_winner_survives_exact80": True,
        "selected_book_also_crosses": True,
    }


def test_aggregate_applies_frozen_two_slate_signal_rule():
    rows = []
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            treatment = 205.0 if season == 2023 and week in (1, 2) else 180.0
            rows.append(_slate(season, week, treatment))
    result = aggregate_diagnostic(rows)
    assert result["books"]["P1"]["S"]["threshold_counts"]["200"] == 0
    assert result["books"]["P2"]["S"]["threshold_counts"]["200"] == 2
    assert result["distinct_crossings"]["S"]["200"]["net"] == 2
    assert result["gate"] == {
        "selected_200_net": 2,
        "selected_210_net": 0,
        "candidate_200_net": 2,
        "historical_tail_signal_positive": True,
        "disposition": "historical-tail-signal-positive",
    }
    assert result["production_change_licensed"] is False
    assert set(result["by_season"]) == {"2023", "2024", "2025"}
    assert set(result["books"]["P2"]["C"]["threshold_counts"]) == {
        f"{line:g}" for line in THRESHOLDS
    }


def test_score_rosters_fails_closed_on_missing_outcome():
    with pytest.raises(ValueError, match="missing realized score"):
        score_rosters([_roster("missing", 0)], {})


def test_compare_slate_rejects_non_exact_80_selection():
    p1 = [_roster("native", index) for index in range(80)]
    atlas = [_roster("atlas", index) for index in range(200)]
    actual = {player_id: 1.0 for roster in [*p1, *atlas] for player_id in roster}
    with pytest.raises(ValueError, match="exact 80"):
        compare_slate(
            season=2023, week=1,
            p1_candidates=p1, p2_candidates=p1,
            p1_selected=p1[:-1], p2_selected=p1,
            actual_by_id=actual, atlas_rosters=atlas,
        )


def test_historical_runner_queries_only_required_realized_score_fields():
    source = SOURCE_SQL.lower()
    player = PLAYER_SQL.lower()
    assert "actual_score" in source
    assert " actual" in player
    for forbidden in ("ownership", "payout", "contest_rank", "actual_rank"):
        assert forbidden not in f"{source}\n{player}"


def test_historical_runner_is_packaged_and_container_smoked():
    runner = "scripts/run_atlas_historical_score_diagnostic.py"
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cloudbuild = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    assert f"COPY {runner} ./{runner}" in dockerfile
    assert f"python {runner} --help" in cloudbuild


def test_upstream_execution_binding_accepts_only_frozen_shape():
    season = 2023
    week = 1
    value = {
        "metadata": {"name": UPSTREAM_EXECUTIONS[(season, week)]},
        "status": {
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1, "failedCount": 0,
            "completionTime": "2026-08-16T12:00:00Z",
        },
        "spec": {
            "parallelism": 1, "taskCount": 1,
            "template": {"spec": {
                "containers": [{
                    "image": UPSTREAM_IMAGE, "command": ["python"],
                    "args": [
                        "scripts/run_atlas_matched_diversity_mvp.py",
                        "--season", str(season), "--week", str(week),
                        "--output-uri",
                        f"{UPSTREAM_PREFIX}/slate-{season}-{week}.json",
                    ],
                    "env": [
                        {"name": "CODE_SHA", "value": UPSTREAM_CODE_SHA},
                        {"name": "ANALYSIS_IMAGE", "value": UPSTREAM_IMAGE},
                    ],
                    "resources": {"limits": {"cpu": "1", "memory": "4Gi"}},
                }],
                "maxRetries": 0, "timeoutSeconds": "43200",
                "serviceAccountName": (
                    "817589974517-compute@developer.gserviceaccount.com"
                ),
            }},
        },
    }
    _validate_execution(value, season, week)
    value["spec"]["template"]["spec"]["maxRetries"] = 1
    with pytest.raises(RuntimeError, match="resources"):
        _validate_execution(value, season, week)


def test_upstream_execution_grid_is_exactly_54_unique_shards():
    expected = {
        (season, week)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
    }
    assert set(UPSTREAM_EXECUTIONS) == expected
    assert len(set(UPSTREAM_EXECUTIONS.values())) == 54
    assert UPSTREAM_EXECUTION_NAMES == {
        f"{season}-{week}": name
        for (season, week), name in UPSTREAM_EXECUTIONS.items()
    }


def test_historical_cloud_contract_requires_repair2_strict_harvest():
    launcher = (
        ROOT / "scripts/cloud_atlas_historical_score_diagnostic.sh"
    ).read_text(encoding="utf-8")
    finisher = (
        ROOT / "scripts/cloud_finish_atlas_historical_score_diagnostic.sh"
    ).read_text(encoding="utf-8")
    assert "20260816-atlas-matched-diversity-mvp-v1-repair2" in launcher
    assert "20260816-atlas-matched-diversity-mvp-v1-repair1" not in launcher
    assert "UPSTREAM_EXECUTION_LEDGER_SHA" in launcher
    assert "sharded_upstream_amendment_sha256" in launcher
    assert '= 54 ]' in launcher
    assert "expected_executions" in finisher
