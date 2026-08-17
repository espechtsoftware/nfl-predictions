from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

from nfl_dfs.analysis import production_law_dependence as production


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _g0_report(
    *, qb_gap=-0.5, ge3_gap=0.5, supported=True, classification="material-miss",
    worlds=10_000,
):
    def cell(gap):
        return {
            "supported": supported,
            "classification": classification if supported else "unsupported",
            "log_simulated_to_realized": gap if supported else None,
        }

    return {
        "population": {"n_sims": worlds, "slates": 54},
        "cells": {
            "qb_wr": cell(qb_gap),
            "multiplicity_ge3": cell(ge3_gap),
            "multiplicity_ge4": cell(ge3_gap),
        },
    }


def _blocks(**kwargs):
    return {name: _g0_report(**kwargs) for name in production.REGISTERED_BLOCKS}


def test_production_law_gate_requires_both_aggregate_and_three_blocks():
    blocks = _blocks()
    result = production.aggregate_remeasurement(
        blocks, _g0_report(worlds=50_000),
    )
    assert result["gate"]["passes"] is True
    assert result["sparse_ledger_prototype_licensed"] is True
    assert result["gate"]["disposition"] == (
        "production-law-shape-reproduced-ledger-prototype-licensed"
    )
    assert result["blocks_are_independent_historical_replications"] is False
    assert result["mandatory_diagnostic_non_gating_cells"] == [
        "multiplicity_ge4"
    ]

    two_qb_blocks = deepcopy(blocks)
    for name in ("R2", "R3", "R4"):
        two_qb_blocks[name]["cells"]["qb_wr"][
            "log_simulated_to_realized"
        ] = 0.5
    failed = production.aggregate_remeasurement(
        two_qb_blocks, _g0_report(worlds=50_000),
    )
    assert failed["gate"]["passes"] is False
    assert failed["gate"]["disposition"] == (
        "partial-production-law-shape-requires-reframe"
    )


def test_production_law_gate_distinguishes_inconclusive_and_not_reproduced():
    unsupported = _blocks(supported=False)
    result = production.aggregate_remeasurement(
        unsupported, _g0_report(supported=False, worlds=50_000),
    )
    assert result["gate"]["disposition"] == (
        "production-law-dependence-inconclusive"
    )

    equivalent = _blocks(qb_gap=0.0, ge3_gap=0.0, classification="equivalent")
    result = production.aggregate_remeasurement(
        equivalent,
        _g0_report(
            qb_gap=0.0, ge3_gap=0.0, classification="equivalent", worlds=50_000,
        ),
    )
    assert result["gate"]["disposition"] == (
        "production-law-shape-not-reproduced-ledger-dropped-or-reframed"
    )


def test_production_law_gate_rejects_incomplete_or_wrong_world_grid():
    blocks = _blocks()
    blocks.pop("R4")
    with pytest.raises(ValueError, match="R0--R4"):
        production.aggregate_remeasurement(blocks, _g0_report(worlds=50_000))
    blocks = _blocks()
    blocks["R0"]["population"]["n_sims"] = 9_999
    with pytest.raises(ValueError, match="world grid"):
        production.aggregate_remeasurement(blocks, _g0_report(worlds=50_000))


def test_production_law_source_lock_and_outcome_firewall_are_explicit():
    lock = (
        ROOT / "scripts/run_production_law_dependence_source_lock.py"
    ).read_text(encoding="utf-8")
    outcome = (
        ROOT / "scripts/run_production_law_dependence_remeasurement.py"
    ).read_text(encoding="utf-8")
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cloudbuild = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    coherent_serialized = (
        ROOT / "scripts/watch_coherent_market_state_historical_serialized.sh"
    ).read_text(encoding="utf-8")
    stack_serialized = (
        ROOT / "scripts/watch_stack_core_shell_historical_serialized.sh"
    ).read_text(encoding="utf-8")
    protocol = (
        ROOT / "reports/2026-08-17-production-law-dependence-remeasurement-protocol.md"
    ).read_text(encoding="utf-8")

    player_sql = lock.split('PLAYER_SQL = f"""', 1)[1].split('"""', 1)[0].lower()
    assert "actual" not in player_sql
    assert "score" not in player_sql
    assert "_validate_artifact_metadata(gcs, artifacts)" in outcome
    assert outcome.index("_validate_artifact_metadata(gcs, artifacts)") < \
        outcome.index("outcomes = _query(bq, OUTCOME_SQL")
    assert "source-lock.json" in lock and "if_generation_match=0" not in lock
    assert "run_production_law_dependence_source_lock.py" in docker
    assert "run_production_law_dependence_remeasurement.py" in docker
    assert "run_production_law_dependence_source_lock.py --help" in cloudbuild
    assert "run_production_law_dependence_remeasurement.py --help" in cloudbuild
    assert "historical_outcome_lease.py\" acquire" in coherent_serialized
    assert "historical_outcome_lease.py\" release" in coherent_serialized
    assert "historical_outcome_lease.py\" acquire" in stack_serialized
    assert "historical_outcome_lease.py\" release" in stack_serialized
    assert "at least three of R0--R4" in protocol


def test_locked_catalog_digest_is_order_and_value_sensitive():
    # Import from scripts only after the package test path has been configured.
    from run_production_law_dependence_remeasurement import _catalog_digest

    rows = [{
        "season": 2023, "week": 1, "player_id": "p1", "position": "QB",
        "team": "AAA", "mean_projection": 20.0,
    }]
    original = _catalog_digest(rows)
    assert original == _catalog_digest(json.loads(json.dumps(rows)))
    changed = deepcopy(rows)
    changed[0]["mean_projection"] = 20.1
    assert original != _catalog_digest(changed)


def test_frozen_transfer_report_is_exact_production_multinomial_grid():
    import run_production_law_dependence_source_lock as source

    hashes = source._validate_local_sources()
    transfer = json.loads(source.TRANSFER_REPORT.read_text(encoding="utf-8"))
    artifacts = source._validate_policy_and_artifacts(transfer)
    assert len(hashes) == 6
    assert len(artifacts) == 270
    assert artifacts[0]["panel_run_id"] == source.SOURCE_PANELS[0]
    assert artifacts[-1]["panel_run_id"] == source.SOURCE_PANELS[-1]
    assert transfer["source_policy_receipt"]["simulation_law"] == {
        "dirichlet_k": None,
        "game_mode": "possession",
        "game_sim_usage_env": "",
        "td_ledger": False,
        "team_factors": True,
        "usage_allocation": "production-multinomial",
    }
