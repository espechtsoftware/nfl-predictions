from __future__ import annotations

from pathlib import Path

from nfl_dfs.research import (
    corpus_r6_construction_allocation_collector_repair_v1 as repair,
)


ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT / "scripts/cloud_corpus_r6_construction_allocation_collector_repair_v1.sh"
GENERIC = ROOT / "scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh"


def test_recovery_launcher_is_exactly_bound_to_the_known_failure() -> None:
    text = RECOVERY.read_text()
    assert str(repair.FAILED_COLLECT_EXECUTION["name"]) in text
    assert str(repair.FAILED_COLLECT_EXECUTION["uid"]) in text
    assert str(repair.FAILED_COLLECT_EXECUTION["completion_time"]) in text
    assert repair.SOURCE_CODE_SHA in text
    assert repair.SOURCE_IMAGE_DIGEST in text
    assert repair.SOURCE_MANIFEST_IDENTITY["sha256"] in text
    assert '[[ "$ACTION" =~ ^(collect|reopen)$ ]]' in text


def test_recovery_launcher_cannot_run_shard_tasks_or_outcomes() -> None:
    text = RECOVERY.read_text()
    launch = text[text.index("gcloud run jobs execute"):]
    assert "--tasks 1" in launch
    assert "container-collect,--execute" in launch
    assert "TARGET_OUTCOMES_ALLOWED=false" in text
    assert "container-task" not in text
    assert "--tasks 54" not in launch


def test_generic_launcher_does_not_admit_the_recovery_action() -> None:
    text = GENERIC.read_text()
    assert "repair-collect" not in text
    assert "collector-repair" not in text
