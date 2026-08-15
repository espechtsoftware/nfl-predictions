from __future__ import annotations

import copy
import hashlib
import json

import pandas as pd
import pytest

from nfl_dfs.research.final_forensic import (
    ANALYSIS_CHECKLIST,
    BETWEEN_ARM_VARIANCE_PANEL_IDS,
    FreezeManifestError,
    PROTOCOL_ID,
    REQUIRED_FORENSIC_ARTIFACT_PATHS,
    REQUIRED_MECHANISM_FAMILIES,
    REQUIRED_OUTPUTS,
    WAREHOUSE_TABLE_SCHEMAS,
    WAREHOUSE_TABLE_PREFIX,
    audit_roster,
    build_freeze_manifest,
    canonical_game_id,
    decompose_slate,
    manifest_digest,
    recourse_ceiling_slate,
    report_inventory,
    sha256_file,
    validate_freeze_manifest,
)


def _between_arm_contract():
    slates = [f"2019-{week:02d}" for week in range(1, 18)] + [
        f"{season}-{week:02d}"
        for season in (2021, 2022, 2023, 2024, 2025)
        for week in range(1, 19)
    ]
    encoded = json.dumps(
        slates, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "source_table": (
            "nfl-predictions-503414.nfl_predictions.replay_candidates"
        ),
        "panel_ids": list(BETWEEN_ARM_VARIANCE_PANEL_IDS),
        "common_slates": slates,
        "common_slate_sha256": hashlib.sha256(encoded).hexdigest(),
        "expected_entries_by_panel": {
            panel: 80 for panel in BETWEEN_ARM_VARIANCE_PANEL_IDS
        },
        "expected_panel_count": 14,
        "expected_common_slate_count": 107,
        "estimand": "selected-arm fixed-effect dispersion after slate removal",
        "selection_bias": "launched panels are a selected sample",
        "use_restriction": "may not revive or re-adjudicate rejected arms",
    }


def test_canonical_game_id_ignores_source_direction_and_format():
    assert canonical_game_id("BUF", "NYJ") == "BUF|NYJ"
    assert canonical_game_id("NYJ", "BUF") == "BUF|NYJ"


def test_roster_game_legality_uses_matchup_not_source_game_id():
    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "WR", "TE", "DST"]
    salaries = [6500, 6500, 6000, 6000, 5500, 5000, 4500, 4500, 4500]
    one_game = pd.DataFrame([
        {
            "id": f"p{index}", "pos": position,
            "team": "A" if index != 2 else "B",
            "opp": "B" if index != 2 else "A",
            "game_id": f"source-{index}", "salary": salary, "actual": 10.0,
        }
        for index, (position, salary) in enumerate(zip(positions, salaries, strict=True))
    ])
    roster = one_game.id.tolist()
    # Include a same-game salary-feasible roster whose raw source ids look
    # different; canonical matching must still reject it as one game.
    audit = audit_roster(one_game, roster)
    assert not audit["valid"]
    assert "fewer than two games" in audit["failures"]


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


def test_hpcs_reports_salary_floor_cost_and_thin_candidate_support():
    players = pd.concat([
        _players(),
        pd.DataFrame([{
            "id": "wr_f", "pos": "WR", "team": "E", "opp": "F",
            "game_id": "E@F", "salary": 3000, "actual": 80.0,
        }]),
    ], ignore_index=True)
    actuals = players.set_index("id").actual.to_dict()
    floor_legal = [
        "qb_a", "rb_c", "rb_d", "wr_a", "wr_b", "wr_c", "wr_d", "te_a",
        "dst_a",
    ]
    roster, score = _candidate(floor_legal, actuals)
    candidates = pd.DataFrame([{
        "players": roster,
        "actual_score": score,
        "selected": True,
        "selected_rank": 0,
    }])

    result = decompose_slate(players, candidates, expected_entries=1)

    assert result["H_no_salary_floor"]["actual_score"] > result["H"]["actual_score"]
    assert "wr_f" in result["H_no_salary_floor"]["players"]
    assert "wr_f" not in result["H"]["players"]
    assert result["salary_floor_policy"]["realized_score_cost"] > 0
    support = result["candidate_support_frequency"]
    assert support["players_appearing_once"] == 9
    assert support["players_appearing_fewer_than_five_candidates"] == 9
    assert support["appearance_bands"] == {
        "1": 9, "2_to_4": 0, "5_to_9": 0, "10_plus": 0,
    }


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


def test_recourse_ceiling_locks_early_core_and_uses_only_late_replacements():
    players = _players()
    players["kickoff_time"] = players.team.map(
        lambda team: "13:00" if team in {"A", "B"} else "16:25"
    )
    actuals = players.set_index("id").actual.to_dict()
    source = [
        "qb_c", "rb_a", "rb_b", "wr_a", "wr_b", "wr_c", "wr_d", "te_c",
        "dst_c",
    ]
    roster, score = _candidate(source, actuals)
    candidates = pd.DataFrame([{
        "players": roster, "actual_score": score, "selected": True,
        "selected_rank": 0,
    }])

    report = recourse_ceiling_slate(
        players, candidates, expected_entries=1, compute_liveness=True
    )

    assert report["ceiling_gain"] > 0
    assert report["status"] == "computed_perfect_information_upper_bound"
    assert report["decision_stages_minutes"] == [780, 985]
    assert report["realistic_recourse"]["status"] == (
        "unidentifiable_from_frozen_summary_corpus"
    )
    assert report["per_stage_liveness"]["status"] == (
        "computed_for_incumbent_locked_cores"
    )
    assert report["per_stage_liveness"]["stages"][0][
        "perfect_information_live_entries"
    ]["187"] in {0, 1}
    assert set(report["source_early_players"]) == {
        "rb_a", "rb_b", "wr_a", "wr_b"
    }
    assert set(report["source_early_players"]) <= set(
        report["final_roster"]["players"]
    )


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
    artifacts = _write_required_artifacts(tmp_path)
    inventory = report_inventory(tmp_path)
    manifest = {
        "protocol_id": PROTOCOL_ID,
        "analysis_image": "repo/image@sha256:" + "a" * 64,
        "analysis_code_sha": "c" * 40,
        "outcome_query_after_freeze_only": True,
        "between_arm_variance": _between_arm_contract(),
        "warehouse_retention": _warehouse_retention(),
        "analysis_checklist": [
            {
                "id": item_id,
                "evidence_class": evidence_class,
                "required_disposition": disposition,
            }
            for item_id, evidence_class, disposition in ANALYSIS_CHECKLIST
        ],
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
        "artifacts": artifacts,
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


def _write_required_artifacts(tmp_path):
    artifacts = []
    for relative in REQUIRED_FORENSIC_ARTIFACT_PATHS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture for {relative}\n", encoding="utf-8")
        artifacts.append({"path": relative, "sha256": sha256_file(path)})
    return artifacts


def _warehouse_retention():
    return {
        "retention_days": 90,
        "write_disposition": "WRITE_EMPTY",
        "extension_policy": "extend_only_until_cleanup_deadline",
        "isolation_dataset": "nfl-predictions-503414.nfl_forensic_review",
        "cleanup_policy": "delete_after_review_before_week1",
        "cleanup_deadline": "before_first_2026_production_build",
        "tables": [
            {
                "id": table_id,
                "table": WAREHOUSE_TABLE_PREFIX + table_id,
                "schema": copy.deepcopy(schema),
            }
            for table_id, schema in WAREHOUSE_TABLE_SCHEMAS.items()
        ],
    }


def test_freeze_manifest_is_complete_and_hash_verified(tmp_path):
    manifest = _manifest(tmp_path)
    result = validate_freeze_manifest(manifest, repo_root=tmp_path)
    assert result["outputs"] == 9
    assert result["mechanism_families"] == 13
    assert result["protocols"] == 1
    assert len(manifest["analysis_checklist"]) == 40


def test_freeze_manifest_accepts_one_consistent_repair_table_suffix(tmp_path):
    manifest = _manifest(tmp_path)
    for row in manifest["warehouse_retention"]["tables"]:
        row["table"] += "_repair4"
    manifest["manifest_sha256"] = manifest_digest(manifest)
    validate_freeze_manifest(manifest, repo_root=tmp_path)

    manifest["warehouse_retention"]["tables"][0]["table"] += "_wrong"
    manifest["manifest_sha256"] = manifest_digest(manifest)
    with pytest.raises(FreezeManifestError, match="warehouse table name is invalid"):
        validate_freeze_manifest(manifest, repo_root=tmp_path)


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

    manifest = _manifest(tmp_path)
    (tmp_path / "reports" / "late-review.md").write_text(
        "late\n", encoding="utf-8"
    )
    with pytest.raises(FreezeManifestError, match="inventory membership drift"):
        validate_freeze_manifest(manifest, repo_root=tmp_path)


def test_freeze_manifest_rejects_mutated_self_digest(tmp_path):
    manifest = _manifest(tmp_path)
    bad = copy.deepcopy(manifest)
    bad["production"]["policy_id"] = "mutated"
    with pytest.raises(FreezeManifestError, match="manifest_sha256 differs"):
        validate_freeze_manifest(bad, repo_root=tmp_path)


def test_freeze_manifest_rejects_unpinned_required_artifact(tmp_path):
    manifest = _manifest(tmp_path)
    manifest["artifacts"] = manifest["artifacts"][1:]
    manifest["manifest_sha256"] = manifest_digest(manifest)
    with pytest.raises(FreezeManifestError, match="not pinned"):
        validate_freeze_manifest(manifest, repo_root=tmp_path)


def test_freeze_manifest_rejects_incomplete_analysis_checklist(tmp_path):
    manifest = _manifest(tmp_path)
    manifest["analysis_checklist"] = manifest["analysis_checklist"][:-1]
    manifest["manifest_sha256"] = manifest_digest(manifest)
    with pytest.raises(FreezeManifestError, match="analysis checklist"):
        validate_freeze_manifest(manifest, repo_root=tmp_path)


def test_freeze_manifest_rejects_short_or_mutated_warehouse_retention(tmp_path):
    manifest = _manifest(tmp_path)
    manifest["warehouse_retention"]["retention_days"] = 30
    manifest["manifest_sha256"] = manifest_digest(manifest)
    with pytest.raises(FreezeManifestError, match="retention_days"):
        validate_freeze_manifest(manifest, repo_root=tmp_path)

    manifest = _manifest(tmp_path)
    manifest["warehouse_retention"]["tables"][0]["schema"][0]["mode"] = "NULLABLE"
    manifest["manifest_sha256"] = manifest_digest(manifest)
    with pytest.raises(FreezeManifestError, match="warehouse schema differs"):
        validate_freeze_manifest(manifest, repo_root=tmp_path)


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
    _write_required_artifacts(tmp_path)
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
        analysis_code_sha="c" * 40,
        production=production,
        panels=panels,
        between_arm_variance=_between_arm_contract(),
        warehouse_retention=_warehouse_retention(),
        registry_path=registry,
    )

    assert manifest["arm_ledger"][0]["operator_override"] == "none"
    assert manifest["arm_ledger"][0]["execution_ids"] == []
    assert manifest["manifest_sha256"] == manifest_digest(manifest)
    artifact_paths = {row["path"] for row in manifest["artifacts"]}
    assert set(REQUIRED_FORENSIC_ARTIFACT_PATHS) <= artifact_paths
    assert "reports/registry.json" in artifact_paths
