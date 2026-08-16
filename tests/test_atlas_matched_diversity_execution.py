import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from aggregate_atlas_matched_diversity_mvp import aggregate  # noqa: E402
from aggregate_atlas_matched_diversity_shards import assemble  # noqa: E402
from run_atlas_matched_diversity_mvp import (  # noqa: E402
    FORBIDDEN_QUERY_TOKENS,
    PLAYER_SQL,
    SOURCE_SQL,
    SHARDING_REPAIR,
    SHARDING_REPAIR_SHA256,
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


def test_sharding_repair_hash_and_exact_54_assembly(tmp_path):
    import hashlib

    assert hashlib.sha256(SHARDING_REPAIR.read_bytes()).hexdigest() == (
        SHARDING_REPAIR_SHA256
    )
    paths = []
    for season in (2023, 2024, 2025):
        source = _season_report(season)
        for week, row in enumerate(source["slates"], start=1):
            payload = {
                **{key: source[key] for key in (
                    "version", "uses_realized_outcomes", "season", "code_sha",
                    "analysis_image", "source_hashes",
                )},
                "shard_week": week,
                "slates": [row],
            }
            path = tmp_path / f"slate-{season}-{week}.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            paths.append(path)
    assembled = assemble(list(reversed(paths)))
    assert [row["season"] for row in assembled] == [2023, 2024, 2025]
    assert all(len(row["slates"]) == 18 for row in assembled)
    season_paths = []
    for report in assembled:
        path = tmp_path / f"season-{report['season']}.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        season_paths.append(path)
    assert aggregate(season_paths)["mechanical"]["slates"] == 54


def test_sharded_launcher_uses_frozen_single_thread_resources():
    launcher = (ROOT / "scripts/cloud_atlas_matched_diversity_shards.sh").read_text(
        encoding="utf-8"
    )
    finisher = (
        ROOT / "scripts/cloud_finish_atlas_matched_diversity_shards.sh"
    ).read_text(encoding="utf-8")
    assert '--cpu 1 --memory 4Gi' in launcher
    assert '--max-retries 0 --task-timeout 12h' in launcher
    assert '--week,"$WEEK",--output-uri,"$URI"' in launcher
    assert '"timeoutSeconds"))!="43200"' in finisher
    assert 'wc -l < "$EXECUTIONS")" = 54' in finisher


def test_single_shard_retry_is_exact_and_one_cell_only():
    import hashlib

    protocol = ROOT / "reports/2026-08-16-atlas-mvp-cbc-single-shard-retry.md"
    expected = "bc55775c5a98a7027a0c117cf5371a67cc886c6da34dcdb7b1031bd6a471c455"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == expected
    retry = (
        ROOT / "scripts/cloud_retry_atlas_matched_diversity_shard.sh"
    ).read_text(encoding="utf-8")
    assert f"PROTOCOL_SHA={expected}" in retry
    assert "SEASON=2024" in retry and "WEEK=7" in retry
    assert "ORIGINAL_EXEC=atlas-md-s2024-w7-r2-r9gnq" in retry
    assert 'gcloud run jobs execute "$JOB"' in retry
    assert "gcloud run jobs deploy" not in retry
    assert "PulpSolverError" in retry
    assert 'len(left)!=54 or len(right)!=54' in retry


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
