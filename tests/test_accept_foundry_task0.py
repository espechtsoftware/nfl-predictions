from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "accept_foundry_task0",
    Path(__file__).resolve().parents[1]
    / "scripts/foundry/accept_foundry_task0.py",
)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def _arm(ordinal: int) -> dict[str, object]:
    return {
        "profile": {
            "ordinal": ordinal,
            "parameter_set_id": f"parameter-set-{ordinal}",
        },
        "coverage": {
            "scheduled_visits": 1000,
            "attempted_visits": 1000,
            "optimal_visits": 1000,
            "unique_candidates": 400,
            "selected_entries": 80,
        },
        "visit_rosters": [["p1"]] * 1000,
        "unique_rosters": [["p1"]] * 400,
        "selected_rosters": [["p1"]] * 80,
    }


def test_census_passes_only_on_full_optimal_matrix() -> None:
    arms = [_arm(ordinal) for ordinal in range(7)]
    rows, defects = gate._census(arms)
    assert defects == []
    assert len(rows) == 7
    assert all(row["optimal_visits"] == 1000 for row in rows)

    # The exact v4 failure signature: non-optimal cells.
    poisoned = deepcopy(arms)
    poisoned[3]["coverage"]["optimal_visits"] = 909
    _, defects = gate._census(poisoned)
    assert defects == ["arm 3 optimal_visits=909"]

    short_schedule = deepcopy(arms)
    short_schedule[0]["coverage"]["scheduled_visits"] = 999
    _, defects = gate._census(short_schedule)
    assert defects == ["arm 0 scheduled_visits=999"]

    missing_roster_rows = deepcopy(arms)
    missing_roster_rows[6]["visit_rosters"] = [["p1"]] * 998
    _, defects = gate._census(missing_roster_rows)
    assert defects == ["arm 6 visit_roster_rows=998"]

    empty_roster = deepcopy(arms)
    empty_roster[2]["visit_rosters"][500] = []
    _, defects = gate._census(empty_roster)
    assert defects == ["arm 2 has an empty visit roster"]

    drifted_selection = deepcopy(arms)
    drifted_selection[1]["coverage"]["selected_entries"] = 79
    _, defects = gate._census(drifted_selection)
    assert defects == ["arm 1 selected_entries differ from rosters"]

    drifted_unique = deepcopy(arms)
    drifted_unique[4]["coverage"]["unique_candidates"] = 399
    _, defects = gate._census(drifted_unique)
    assert defects == ["arm 4 unique_candidates differ from rosters"]


def test_gate_refuses_existing_outputs_and_bad_receipt(tmp_path) -> None:
    existing = tmp_path / "task0-acceptance-pass.json"
    existing.write_text("{}")
    receipt = tmp_path / "000-verifier-accepted.json"
    receipt.write_text('{"accepted": true, "partial_result": false}')
    code = gate.main([
        "--carrier-uri", "gs://bucket/carrier.json",
        "--carrier-generation", "1",
        "--carrier-sha256", "0" * 64,
        "--carrier-bytes", "10",
        "--verifier-accepted-receipt", str(receipt),
        "--receipt-output", str(tmp_path / "receipt.json"),
        "--pass-gate-output", str(existing),
    ])
    assert code == 2

    code = gate.main([
        "--carrier-uri", "gs://bucket/carrier.json",
        "--carrier-generation", "1",
        "--carrier-sha256", "0" * 64,
        "--carrier-bytes", "10",
        "--verifier-accepted-receipt", str(tmp_path / "absent.json"),
        "--receipt-output", str(tmp_path / "receipt2.json"),
        "--pass-gate-output", str(tmp_path / "pass2.json"),
    ])
    assert code == 2


def test_gate_name_matches_driver_contract() -> None:
    driver = (
        Path(__file__).resolve().parents[1]
        / "scripts/foundry/foundry_batch_driver.sh"
    ).read_text()
    assert f'.gate == "{gate.GATE_NAME}"' in driver
    assert "task0-acceptance-pass.json" in driver
    assert ".solver_all_optimal == true" in driver
    assert ".verifier_accepted == true" in driver
    assert ".uses_realized_outcomes == false" in driver
