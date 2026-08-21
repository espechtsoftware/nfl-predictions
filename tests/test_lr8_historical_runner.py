from __future__ import annotations

import sys
from pathlib import Path

import pytest

from nfl_dfs.research.lr8_historical_arm import (
    ANATOMY_FEATURES,
    LR8Error,
    TRAINING_CELLS,
    TRAINING_SEASONS,
    canonical_json,
)


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_lr8_historical_arm as runner  # noqa: E402


def _fit_payload() -> dict[str, object]:
    rows = []
    for season, week in TRAINING_CELLS:
        index = len(rows) + 1
        rows.append({
            "season": season,
            "week": week,
            "features": [
                float(((index + column) % 7) + index * (column + 1) / 10)
                for column in range(len(ANATOMY_FEATURES))
            ],
            "realized_total_micro": (
                205_000_000 if index % 2 == 0 else 190_000_000
            ),
        })
    return {
        "schema": "lr8-soft-anatomy-fit-synthetic-v1",
        "synthetic_fixture": True,
        "rows": rows,
    }


def test_synthetic_fit_runner_is_canonical_create_only_and_default_off(tmp_path):
    payload = _fit_payload()
    source = tmp_path / "input.json"
    output = tmp_path / "output.json"
    source.write_bytes(canonical_json(payload))
    artifact = runner.run(source, output)
    assert output.read_bytes() == canonical_json(artifact)
    assert artifact["training_seasons"] == [2019, 2021]
    assert artifact["b1_inputs_used"] is False
    assert artifact["a2a_inputs_used"] is False
    assert artifact["production_change_licensed"] is False
    with pytest.raises(FileExistsError):
        runner.run(source, output)


def test_runner_rejects_noncanonical_and_nonsynthetic_inputs(tmp_path):
    payload = _fit_payload()
    source = tmp_path / "pretty.json"
    source.write_text(__import__("json").dumps(payload, indent=2))
    with pytest.raises(LR8Error, match="not canonical"):
        runner.run(source)
    payload["synthetic_fixture"] = False
    with pytest.raises(LR8Error, match="only its exact synthetic schema"):
        runner.run_payload(payload)


def test_mock_proposal_plan_stops_at_first_null_and_requires_complete_plan():
    roster = [f"p{index}" for index in range(9)]
    assert runner._proposal_plan([roster, None], "A") == (tuple(roster), None)
    with pytest.raises(LR8Error, match="continues after first null"):
        runner._proposal_plan([None, roster], "A")
    with pytest.raises(LR8Error, match="short proposal plan lacks terminal null"):
        runner._proposal_plan([roster], "B")


def test_protocol_records_exact_temporal_and_no_b1_retune_boundary():
    protocol = (
        ROOT / "reports/2026-08-20-lr8-historical-residual-column-protocol-draft.md"
    ).read_text()
    assert "`{2019, 2021}`" in protocol
    assert "Season 2020 is absent" in protocol
    assert "Season 2022 is excluded" in protocol
    assert "Evaluation is the exact\nset `{2023, 2024, 2025}`" in protocol
    assert "B1's 2023--2025 outcome-viewed model" in protocol
    assert "up to eight replacements independently in Fold A" in protocol
    assert "2026 Weeks 1--6 confirmation" in protocol
    assert "35 season-week cells total" in protocol
    assert "8,848 accepted old-law candidates" in protocol
    assert "`cand_ix`, `totals`, and\n   `tail_line`" in protocol
    assert "40 unique exact DK-only solves per\n   block" in protocol
    assert "Role-belief worlds are explicitly unused" in protocol
    assert "repaired R3 2025 Week 1 object SHA" in protocol
    assert "not an untouched statistical holdout" in protocol


def test_runner_has_no_cloud_or_warehouse_client_path():
    source = (ROOT / "scripts/run_lr8_historical_arm.py").read_text()
    assert "from google.cloud" not in source
    assert "import google.cloud" not in source
    assert "storage.Client" not in source
    assert "gcloud" not in source
