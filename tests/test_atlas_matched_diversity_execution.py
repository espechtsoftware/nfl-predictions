import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from aggregate_atlas_matched_diversity_mvp import aggregate  # noqa: E402
from run_atlas_matched_diversity_mvp import (  # noqa: E402
    FORBIDDEN_QUERY_TOKENS,
    PLAYER_SQL,
    SOURCE_SQL,
)


def _structure(value):
    return {
        "unique_players": value,
        "unique_pairs": value * 10,
        "unique_stack_cores": value * 2,
        "unique_maximum_game_signatures": value,
        "player_entropy_effective_count": float(value),
        "player_simpson_effective_count": float(value),
        "mean_pairwise_roster_overlap": 4.0,
        "score_effective_rank": {
            family: {
                "participation_ratio": float(value),
                "entropy_effective_rank": float(value + 1),
                "top_five_variance_share": 0.8,
            } for family in ("covariance", "correlation")
        },
    }


def _book(p194, p210, p230, structure_value):
    lines = {
        "187": p194 + 0.05, "194": p194, "200": p210 + 0.05,
        "210": p210, "220": p230 + 0.02, "230": p230,
        "240": p230 * 0.8,
    }
    by_block = {
        seed: dict(lines) for seed in ("R0", "R1", "R2", "R3", "R4")
    }
    return {
        "candidate_pool_tail": {
            "aggregate": dict(lines), "by_block": by_block,
        },
        "exact80_tail": {
            "aggregate": dict(lines), "by_block": by_block,
        },
        "candidate_structure": _structure(structure_value),
        "exact80_structure": _structure(structure_value - 1),
    }


def _season_report(season):
    rows = []
    for week in range(1, 19):
        interaction = {
            "P1": [{
                "pair_weight_covered": 0.20,
                "triple_weight_covered": 0.10,
                "triple_weight_total": 0.20,
            } for _ in range(5)],
            "P2": [{
                "pair_weight_covered": 0.25,
                "triple_weight_covered": 0.095,
                "triple_weight_total": 0.20,
            } for _ in range(5)],
        }
        rows.append({
            "season": season, "week": week,
            "uses_realized_outcomes": False, "mechanical_valid": True,
            "global_atlas_additions": 200,
            "native_boom_counts": {f"R{i}": 40 for i in range(5)},
            "P0": _book(0.50, 0.25, 0.10, 30),
            "P1": _book(0.50, 0.25, 0.10, 30),
            "P2": _book(0.48, 0.30, 0.096, 32),
            "interaction_coverage": interaction,
            "top20_player_jaccard_P1_P2": {
                "candidate": 0.60, "exact80": 0.55,
            },
        })
    return {
        "version": "atlas-matched-diversity-mvp-v1",
        "uses_realized_outcomes": False,
        "season": season,
        "code_sha": "a" * 40,
        "analysis_image": "example/image@sha256:" + "b" * 64,
        "source_hashes": {"protocol": "c" * 64},
        "slates": rows,
    }


def test_queries_are_explicitly_score_free():
    query = f"{SOURCE_SQL}\n{PLAYER_SQL}".lower()
    assert not [token for token in FORBIDDEN_QUERY_TOKENS if token in query]


def test_atlas_mvp_runner_is_packaged_and_container_smoked():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cloudbuild = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    runner = "scripts/run_atlas_matched_diversity_mvp.py"
    assert f"COPY {runner} ./scripts/run_atlas_matched_diversity_mvp.py" in dockerfile
    assert f"python {runner} --help" in cloudbuild


def test_three_season_aggregate_applies_frozen_gate(tmp_path):
    paths = []
    for season in (2025, 2023, 2024):
        path = tmp_path / f"season-{season}.json"
        path.write_text(json.dumps(_season_report(season)), encoding="utf-8")
        paths.append(path)
    result = aggregate(paths)
    assert result["mechanical"] == {
        "seasons": [2023, 2024, 2025],
        "slates": 54,
        "all_valid": True,
        "all_global_atlas_additions_200": True,
        "all_native_boom_counts_40": True,
    }
    assert result["gate"]["passes_scorefree_gate"] is True
    assert set(result["tail_delta_by_season"]) == {"2023", "2024", "2025"}
    assert result["production_change_licensed"] is False
    assert result["historical_arm_licensed"] is False
