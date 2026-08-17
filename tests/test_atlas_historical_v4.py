from hashlib import sha256
from pathlib import Path
import sys

import pytest

from nfl_dfs.research.atlas_historical_v4_sources import (
    HISTORICAL_PREFIX,
    HISTORICAL_RUN_ID,
    PROTOCOL_SHA256,
    validate_shard,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from run_atlas_historical_score_diagnostic_v4 import (  # noqa: E402
    OUTPUT_URI,
    PLAYER_SQL,
    SOURCE_SQL,
    UPSTREAM_RECEIPT_URI,
)


def _shard():
    construction = {}
    for seed in ("R0", "R1", "R2", "R3", "R4"):
        construction[seed] = {"enumeration": {
            "uses_realized_outcomes": False, "candidate_count": 40,
            "proposals": [
                {"accepted": True, "roster": [f"p{i}" for i in range(9)]}
                for _ in range(40)
            ],
        }}
    return {
        "version": "atlas-matched-diversity-mvp-v1",
        "uses_realized_outcomes": False, "code_sha": "a" * 40,
        "analysis_image": "image@sha256:" + "b" * 64,
        "season": 2023, "shard_week": 7,
        "slates": [{
            "season": 2023, "week": 7, "mechanical_valid": True,
            "uses_realized_outcomes": False, "global_atlas_additions": 200,
            "native_boom_counts": {f"R{i}": 40 for i in range(5)},
            "construction": construction,
            "P1": {
                "candidate_budget": 100, "exact80_indices": list(range(80)),
                "exact80_identities": [[f"p{i}" for i in range(9)]] * 80,
            },
            "P2": {
                "candidate_budget": 100, "exact80_indices": list(range(80)),
                "exact80_identities": [[f"p{i}" for i in range(9)]] * 80,
            },
        }],
    }


def test_historical_v4_validates_one_exact_hybrid_shard():
    value = _shard()
    row = validate_shard(
        value, season=2023, week=7, source="repair6",
        code_sha="a" * 40, image="image@sha256:" + "b" * 64,
    )
    assert row["global_atlas_additions"] == 200


def test_historical_v4_rejects_malformed_exact80_source():
    value = _shard()
    value["slates"][0]["P2"]["exact80_indices"].pop()
    with pytest.raises(RuntimeError, match="exact-80"):
        validate_shard(
            value, season=2023, week=7, source="repair6",
            code_sha="a" * 40, image="image@sha256:" + "b" * 64,
        )


def test_historical_v4_protocol_queries_and_destinations_are_frozen():
    protocol = ROOT / "reports/2026-08-17-atlas-historical-score-v4-hybrid-protocol.md"
    assert sha256(protocol.read_bytes()).hexdigest() == PROTOCOL_SHA256
    combined = f"{SOURCE_SQL}\n{PLAYER_SQL}".lower()
    assert "actual_score" in combined and " actual" in combined
    for forbidden in ("ownership", "payout", "contest_rank", "actual_rank"):
        assert forbidden not in combined
    assert UPSTREAM_RECEIPT_URI == f"{HISTORICAL_PREFIX}/upstream-receipt.json"
    assert OUTPUT_URI == f"{HISTORICAL_PREFIX}/report.json"
    assert HISTORICAL_RUN_ID == "20260817-atlas-historical-score-diagnostic-v4"


def test_historical_v4_is_packaged_smoked_and_lease_controlled():
    runner = "scripts/run_atlas_historical_score_diagnostic_v4.py"
    assert f"COPY {runner} ./{runner}" in (ROOT / "Dockerfile").read_text()
    assert f"python {runner} --help" in (ROOT / "cloudbuild.yaml").read_text()
    launcher = (ROOT / "scripts/cloud_atlas_historical_score_diagnostic_v4.sh").read_text()
    watcher = (ROOT / "scripts/watch_atlas_historical_v4_queue.sh").read_text()
    for token in (
        "--upstream-receipt-generation", "--upstream-receipt-sha256",
        "--cpu 8", "--memory 32Gi", "--max-retries 0", "--task-timeout 8h",
    ):
        assert token in launcher
    assert 'historical_outcome_lease.py" acquire' in launcher
    assert 'historical_outcome_lease.py" release' in watcher
    assert "valid-complete-repair6-hybrid-population" in watcher
