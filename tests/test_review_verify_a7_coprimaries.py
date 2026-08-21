from __future__ import annotations

import ast
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Callable

import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = str(REPO / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import review_verify_a7_coprimaries as review  # noqa: E402


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _threshold_counts(values: list[float]) -> dict[str, int]:
    return {
        str(threshold): sum(value >= threshold for value in values)
        for threshold in review.THRESHOLDS
    }


def _cut(control: list[float], treatment: list[float], *, count: int) -> dict:
    paired, direction = review.paired_report(control, treatment)
    return {
        "gating": count == 80,
        "control_mean": sum(control) / len(control),
        "treatment_mean": sum(treatment) / len(treatment),
        "control_threshold_counts": _threshold_counts(control),
        "treatment_threshold_counts": _threshold_counts(treatment),
        "paired": paired,
        "signed_rank_direction_positive": direction,
        "robustness": {},
    }


def _write_harvest(directory: Path, report: dict[str, Any]) -> Path:
    directory.mkdir(exist_ok=True)
    report_path = directory / "report.json"
    report_path.write_bytes(_canonical(report))
    replay = {
        "version": "a7-strict-science-replay-v1",
        "run_id": review.RUN_ID,
        "baseline_reproduced": True,
        "outcome_replayed": True,
        "uses_realized_outcomes": True,
        "actual_score_query_executed": True,
        "production_change_licensed": False,
        "disposition": report["outcome"]["disposition"],
    }
    (directory / "science-replay.json").write_bytes(_canonical(replay))
    for name in review.FINAL_LEDGER_NAMES - {
        "report.json", "science-replay.json", "completion.txt",
    }:
        path = directory / name
        if not path.exists():
            path.write_bytes(f"synthetic {name}\n".encode("utf-8"))
    completion = "\n".join((
        "validated_at=2026-08-21T00:00:00+00:00",
        f"run_id={review.RUN_ID}",
        f"disposition={report['outcome']['disposition']}",
        "executions=1",
        "objects=1",
        "scientific_bodies=1",
        "strict_science_replay=true",
        f"report_sha256={_sha(report_path)}",
        f"science_replay_sha256={_sha(directory / 'science-replay.json')}",
        f"freeze_manifest_sha256={_sha(directory / 'freeze-manifest.json')}",
        "uses_realized_outcomes=true",
        "actual_score_query_executed=true",
        "production_change_licensed=false",
        "prospective_shadow_licensed=false",
        "historical_outcome_lease_release_licensed=true",
        "historical_outcome_lease_released=false",
    )) + "\n"
    (directory / "completion.txt").write_text(completion, encoding="utf-8")
    ledger = "".join(
        f"{_sha(directory / name)}  {name}\n"
        for name in sorted(review.FINAL_LEDGER_NAMES)
    )
    (directory / "finish.sha256").write_text(ledger, encoding="utf-8")
    return report_path


def _synthetic_harvest(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    control = [199.0] * 54
    treatment = [201.0, 198.0, *([199.0] * 52)]
    slates = []
    index = 0
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            row: dict[str, Any] = {
                "season": season,
                "week": week,
                "uses_realized_outcomes": True,
            }
            for arm, retained in (
                ("control", control[index]),
                ("treatment", treatment[index]),
            ):
                row[arm] = {"realized": {
                    "identities": [
                        [f"{arm}-{season}-{week}-{entry}"]
                        for entry in range(80)
                    ],
                    "scores": [retained] * 80,
                    "prefix_maxima": {
                        "4": retained, "14": retained, "80": retained,
                    },
                }}
            slates.append(row)
            index += 1
    conditions = {
        "mean_delta_positive": True,
        "paired_mean_p_le_0_05": False,
        "signed_rank_direction_positive": True,
        "paired_signed_rank_p_le_0_05": False,
        "194_noninferior_by_one_slate": True,
        "200_noninferior_by_one_slate": True,
    }
    disposition = "historical-null-or-inconclusive-phase-s"
    report = {
        "version": review.RESULT_VERSION,
        "run_id": review.RUN_ID,
        "uses_realized_outcomes": True,
        "actual_score_query_executed": True,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
        "slates": slates,
        "outcome": {
            "protocol_id": review.RUN_ID,
            "uses_realized_outcomes": True,
            "production_change_licensed": False,
            "production_law_scorefree_transfer_licensed": False,
            "prospective_shadow_licensed": False,
            "conditions": conditions,
            "disposition": disposition,
            "cuts": {
                str(count): _cut(control, treatment, count=count)
                for count in (4, 14, 80)
            },
        },
    }
    return _write_harvest(tmp_path / "harvest", report), report


def test_known_answer_exact_statistics_and_no_science_imports() -> None:
    paired, direction = review.paired_report(
        [199.0, 200.0], [201.0, 199.0],
    )
    assert direction is True
    assert paired["mean_diff"] == 0.5
    assert paired["median_diff"] == 0.5
    assert paired["n_treatment_better"] == 1
    assert paired["n_control_better"] == 1
    assert paired["n_tied"] == 0
    assert paired["inference"] == {
        "method": "exact_enumeration",
        "n_nonzero": 2,
        "p_mean_two_sided": 1.0,
        "p_signed_rank_two_sided": 1.0,
        "signed_rank_statistic": 2.0,
    }
    assert paired["threshold_grid"][2] == {
        "threshold": 200,
        "control": 1,
        "treatment": 1,
        "discordant_control_only": 1,
        "discordant_treatment_only": 1,
        "mcnemar_exact_p_two_sided": 1.0,
    }

    tree = ast.parse((REPO / "scripts/review_verify_a7_coprimaries.py").read_text())
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not any(
        name.startswith("nfl_dfs") or "finish_a7_select_ladder" in name
        for name in imported
    )


def test_known_answer_fixed_seed_monte_carlo() -> None:
    paired, direction = review.paired_report([199.0] * 21, [201.0] * 21)
    assert direction is True
    assert paired["inference"] == {
        "method": "monte_carlo",
        "n_nonzero": 21,
        "p_mean_two_sided": 1 / 200_001,
        "p_signed_rank_two_sided": 1 / 200_001,
        "signed_rank_statistic": 231.0,
    }
    assert paired["threshold_grid"][2] == {
        "threshold": 200,
        "control": 0,
        "treatment": 21,
        "discordant_control_only": 0,
        "discordant_treatment_only": 21,
        "mcnemar_exact_p_two_sided": 1 / (2 ** 20),
    }


def test_fully_harvested_nested_outcome_agrees(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    report_path, _report = _synthetic_harvest(tmp_path)
    assert review.main(["--result", str(report_path)]) == 0
    assert "All recomputed statistics and disposition agree" in capsys.readouterr().out


def _corrupt_signed_rank(report: dict[str, Any]) -> None:
    report["outcome"]["cuts"]["80"]["paired"]["inference"][
        "signed_rank_statistic"
    ] = 999.0


def _corrupt_mean_delta(report: dict[str, Any]) -> None:
    report["outcome"]["cuts"]["80"]["paired"]["mean_diff"] = 999.0


def _corrupt_grid(report: dict[str, Any]) -> None:
    report["outcome"]["cuts"]["80"]["paired"]["threshold_grid"][2][
        "discordant_treatment_only"
    ] = 0


def _remove_p_value(report: dict[str, Any]) -> None:
    del report["outcome"]["cuts"]["80"]["paired"]["inference"][
        "p_mean_two_sided"
    ]


def _corrupt_disposition_condition(report: dict[str, Any]) -> None:
    report["outcome"]["conditions"]["paired_mean_p_le_0_05"] = True


@pytest.mark.parametrize(("corrupt", "message"), [
    (_corrupt_mean_delta, "recorded paired != independent recomputation"),
    (_corrupt_signed_rank, "recorded paired != independent recomputation"),
    (_corrupt_grid, "recorded paired != independent recomputation"),
    (_remove_p_value, "recorded paired != independent recomputation"),
    (_corrupt_disposition_condition, "recorded conditions != independent result"),
])
def test_rehashed_statistical_corruption_is_detected(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    corrupt: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    report_path, original = _synthetic_harvest(tmp_path)
    changed = deepcopy(original)
    corrupt(changed)
    _write_harvest(report_path.parent, changed)
    assert review.main(["--result", str(report_path)]) == 1
    assert message in capsys.readouterr().out


def test_partial_or_internally_inconsistent_harvest_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    report_path, report = _synthetic_harvest(tmp_path)
    (report_path.parent / "finish.sha256").unlink()
    assert review.main(["--result", str(report_path)]) == 1
    assert "strict finish ledger is absent" in capsys.readouterr().out

    report["slates"][0]["control"]["realized"]["scores"][0] = 999.0
    _write_harvest(report_path.parent, report)
    assert review.main(["--result", str(report_path)]) == 1
    assert "retained S80 differs" in capsys.readouterr().out
