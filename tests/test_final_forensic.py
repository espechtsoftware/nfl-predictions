from __future__ import annotations

import copy

import pandas as pd
import pytest

from nfl_dfs.research.final_forensic import (
    FreezeManifestError,
    PROTOCOL_ID,
    REQUIRED_MECHANISM_FAMILIES,
    REQUIRED_OUTPUTS,
    audit_roster,
    build_freeze_manifest,
    decompose_slate,
    manifest_digest,
    report_inventory,
    validate_freeze_manifest,
)


def _players() -> pd.DataFrame:
    rows = [
        ("qb_a", "QB", "A", "B", "A@B", 7000, 30),
        ("qb_c", "QB", "C", "D", "C@D", 6500, 20),
        ("rb_a", "RB", "A", "B", "A@B", 6500, 25),
        ("rb_b", "RB", "B", "A", "A@B", 6000, 20),
        ("rb_c", "RB", "C", "D", "C@D", 6000, 22),
        ("rb_d", "RB", "D", "C", "C@D", 5500, 18),
        ("wr_a", "WR", "A", "B", "A@B", 6500, 30),
        ("wr_b", "WR", "B", "A", "A@B", 6000, 20),
        ("wr_c", "WR", "C", "D", "C@D", 5500, 25),
        ("wr_d", "WR", "D", "C", "C@D", 5000, 18),
        ("wr_e", "WR", "E", "F", "E@F", 4500, 40),
        ("te_a", "TE", "A", "B", "A@B", 4500, 15),
        ("te_c", "TE", "C", "D", "C@D", 4000, 12),
        ("dst_a", "DST", "A", "B", "A@B", 3000, 10),
        ("dst_c", "DST", "C", "D", "C@D", 2500, 8),
    ]
    return pd.DataFrame(
        rows, columns=["id", "pos", "team", "opp", "game_id", "salary", "actual"]
    )


def _candidate(ids: list[str], actuals: dict[str, float]) -> tuple[str, float]:
    return ",".join(ids), sum(actuals[player] for player in ids)


def test_hpcs_decomposition_reconstructs_and_orders_layers():
    players = _players()
    actuals = players.set_index("id").actual.to_dict()
    high = [
        "qb_a", "rb_c", "rb_d", "wr_a", "wr_b", "wr_c", "wr_d", "te_a",
        "dst_a",
    ]
    low = [
        "qb_c", "rb_a", "rb_b", "wr_a", "wr_b", "wr_c", "wr_d", "te_c",
        "dst_c",
    ]
    high_players, high_score = _candidate(high, actuals)
    low_players, low_score = _candidate(low, actuals)
    candidates = pd.DataFrame([
        {"players": high_players, "actual_score": high_score,
         "selected": False, "selected_rank": None},
        {"players": low_players, "actual_score": low_score,
         "selected": True, "selected_rank": 0},
    ])

    result = decompose_slate(
        players, candidates, expected_entries=1, min_salary=0
    )

    assert result["H"]["actual_score"] >= result["P"]["actual_score"]
    assert result["P"]["actual_score"] >= result["C"]["actual_score"]
    assert result["C"]["actual_score"] == high_score
    assert result["S"]["actual_score"] == low_score
    assert result["gaps"]["selection"] == high_score - low_score
    assert "wr_e" in result["H"]["players"]
    assert "wr_e" not in result["P"]["players"]


def test_hpcs_rejects_candidate_score_drift():
    players = _players()
    ids = [
        "qb_a", "rb_c", "rb_d", "wr_a", "wr_b", "wr_c", "wr_d", "te_a",
        "dst_a",
    ]
    candidates = pd.DataFrame([{
        "players": ",".join(ids), "actual_score": 999.0,
        "selected": True, "selected_rank": 0,
    }])
    with pytest.raises(ValueError, match="score fails reconstruction"):
        decompose_slate(players, candidates, expected_entries=1, min_salary=0)


def test_independent_roster_audit_catches_rb_against_dst():
    ids = [
        "qb_a", "rb_b", "rb_c", "wr_a", "wr_b", "wr_c", "wr_d", "te_a",
        "dst_a",
    ]
    result = audit_roster(_players(), ids, min_salary=0)
    assert not result["valid"]
    assert "RB faces selected DST" in result["failures"]


def _manifest(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "arm-protocol.md").write_text("protocol\n", encoding="utf-8")
    (reports / "arm-result.md").write_text("result\n", encoding="utf-8")
    inventory = report_inventory(tmp_path)
    manifest = {
        "protocol_id": PROTOCOL_ID,
        "analysis_image": "repo/image@sha256:" + "a" * 64,
        "outcome_query_after_freeze_only": True,
        "production": {
            "policy_id": "policy",
            "fallback_policy_id": "fallback",
            "service_revision": "revision",
            "service_image": "repo/image@sha256:" + "b" * 64,
            "component_panel": "component",
            "position_panel": "position",
            "cbwu_panel": "cbwu",
        },
        "panels": [
            {
                "id": name,
                "table": "project.dataset.table",
                "expected_rows": 1,
                "expected_slates": 1,
                "seasons": [2025],
                "prelock_row_hash": "1",
                "estimand": name,
                "scope_boundary": "fixture",
            }
            for name in ("component", "position", "cbwu")
        ],
        "artifacts": [],
        "report_inventory": inventory,
        "protocol_exclusions": [],
        "result_exclusions": [],
        "arm_ledger": [{
            "id": "arm",
            "family": REQUIRED_MECHANISM_FAMILIES[0],
            "stage": "marginal",
            "status": "rejected",
            "protocol_paths": ["reports/arm-protocol.md"],
            "result_paths": ["reports/arm-result.md"],
            "execution_ids": [],
            "gate": "fixture gate failed",
            "operator_override": "none",
            "cloud_cost_status": "not_identifiable",
            "production_relevance": "none",
            "transfer_boundary": "fixture only",
        }],
        "analysis_contract": [
            {"id": output, "output_path": f"{output}.json", "schema": ["id"]}
            for output in REQUIRED_OUTPUTS
        ],
        "mechanism_taxonomy": [
            {
                "id": family,
                "disposition_rule": "every idea must be terminally classified",
                "falsifier_rule": "prospective evidence may falsify closure",
            }
            for family in REQUIRED_MECHANISM_FAMILIES
        ],
    }
    manifest["manifest_sha256"] = manifest_digest(manifest)
    return manifest


def test_freeze_manifest_is_complete_and_hash_verified(tmp_path):
    manifest = _manifest(tmp_path)
    result = validate_freeze_manifest(manifest, repo_root=tmp_path)
    assert result["outputs"] == 9
    assert result["mechanism_families"] == 12
    assert result["protocols"] == 1


def test_freeze_manifest_rejects_unaccounted_protocol(tmp_path):
    manifest = _manifest(tmp_path)
    manifest["arm_ledger"][0]["protocol_paths"] = []
    manifest["manifest_sha256"] = manifest_digest(manifest)
    with pytest.raises(FreezeManifestError, match="unaccounted protocols"):
        validate_freeze_manifest(manifest, repo_root=tmp_path)


def test_freeze_manifest_rejects_unaccounted_result(tmp_path):
    manifest = _manifest(tmp_path)
    manifest["arm_ledger"][0]["result_paths"] = []
    manifest["manifest_sha256"] = manifest_digest(manifest)
    with pytest.raises(FreezeManifestError, match="unaccounted results"):
        validate_freeze_manifest(manifest, repo_root=tmp_path)


def test_freeze_manifest_rejects_open_status_and_file_drift(tmp_path):
    manifest = _manifest(tmp_path)
    manifest["arm_ledger"][0]["status"] = "pending"
    manifest["manifest_sha256"] = manifest_digest(manifest)
    with pytest.raises(FreezeManifestError, match="open status"):
        validate_freeze_manifest(manifest, repo_root=tmp_path)

    manifest = _manifest(tmp_path)
    changed = tmp_path / "reports" / "arm-result.md"
    changed.write_text("changed\n", encoding="utf-8")
    with pytest.raises(FreezeManifestError, match="inventoried size drift"):
        validate_freeze_manifest(manifest, repo_root=tmp_path)


def test_freeze_manifest_rejects_mutated_self_digest(tmp_path):
    manifest = _manifest(tmp_path)
    bad = copy.deepcopy(manifest)
    bad["production"]["policy_id"] = "mutated"
    with pytest.raises(FreezeManifestError, match="manifest_sha256 differs"):
        validate_freeze_manifest(bad, repo_root=tmp_path)


def test_build_freeze_manifest_expands_reviewed_registry(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    protocol = reports / "arm-protocol.md"
    result = reports / "arm-result.md"
    protocol.write_text("protocol\n", encoding="utf-8")
    result.write_text("result\n", encoding="utf-8")
    closure = reports / "2026-08-11-final-preseason-forensic-closure-protocol.md"
    closure.write_text("closure\n", encoding="utf-8")
    registry = reports / "registry.json"
    registry.write_text(
        "["
        "{\"id\":\"arm\","
        f"\"family\":\"{REQUIRED_MECHANISM_FAMILIES[0]}\","
        "\"stage\":\"fixture\",\"status\":\"rejected\","
        "\"protocol_paths\":[\"reports/arm-protocol.md\"],"
        "\"result_paths\":[\"reports/arm-result.md\"],"
        "\"gate\":\"failed fixture gate\","
        "\"production_relevance\":\"none\","
        "\"transfer_boundary\":\"fixture only\"}"
        "]",
        encoding="utf-8",
    )
    production = {
        "policy_id": "policy",
        "fallback_policy_id": "fallback",
        "service_revision": "revision",
        "service_image": "repo/service@sha256:" + "b" * 64,
        "component_panel": "component",
        "position_panel": "position",
        "cbwu_panel": "cbwu",
    }
    panels = [
        {
            "id": name,
            "table": "project.dataset.table",
            "expected_rows": 1,
            "expected_slates": 1,
            "seasons": [2025],
            "prelock_row_hash": "1",
            "estimand": name,
            "scope_boundary": "fixture",
        }
        for name in ("component", "position", "cbwu")
    ]

    manifest = build_freeze_manifest(
        repo_root=tmp_path,
        analysis_image="repo/analyzer@sha256:" + "a" * 64,
        production=production,
        panels=panels,
        registry_path=registry,
    )

    assert manifest["arm_ledger"][0]["operator_override"] == "none"
    assert manifest["arm_ledger"][0]["execution_ids"] == []
    assert manifest["manifest_sha256"] == manifest_digest(manifest)
