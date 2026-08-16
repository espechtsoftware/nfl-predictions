from __future__ import annotations

from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_repair5_protocol_and_immutable_sources_are_exact() -> None:
    expected = {
        "scripts/run_atlas_matched_diversity_mvp.py": (
            "0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740"
        ),
        "scripts/render_atlas_matched_diversity_repair4_command.py": (
            "69d0ed1187bf59176a857e0bc822f65bd9aea2ffd211ffc247312796bfaeb671"
        ),
        "reports/2026-08-16-atlas-mvp-resource-only-repair5.md": (
            "5acc93c2b3a59931aa17dbc67d98fca81d3a6ac047011cfe1a9a81aa1ee8550e"
        ),
        "reports/2026-08-16-atlas-cbc-32g-full-cell-preflight-protocol.md": (
            "b848dcc4ce0cdc6c3cac07f5ffb2ad6cbaa233a2457dc0286034ff3d50840788"
        ),
    }
    for relative, digest in expected.items():
        assert sha256((ROOT / relative).read_bytes()).hexdigest() == digest


def test_repair5_launcher_requires_strict_preflight_and_census() -> None:
    source = (
        ROOT / "scripts/cloud_atlas_matched_diversity_repair5.sh"
    ).read_text(encoding="utf-8")

    assert "full-cell-r0-complete-at-32g" in source
    assert 'completion.get("status")!="True"' in source
    assert 'meta.get("metadata",{}).get("name")!=' in source
    assert "configured memory limit was reached" in source
    assert 'census.get("executions")!=54' in source
    assert 'census.get("effect_fields_inspected") is not False' in source
    assert "preflight_completion_sha256=" in source
    assert "preflight_execution_metadata_sha256=" in source
    assert "preflight_shard_sha256=" in source
    assert source.index("ATLAS repair5 smoke marker differs") < source.index(
        "for SEASON in 2023 2024 2025"
    )


def test_repair5_cloud_contract_is_new_binary_resource_only_grid() -> None:
    launcher = (
        ROOT / "scripts/cloud_atlas_matched_diversity_repair5.sh"
    ).read_text(encoding="utf-8")
    finisher = (
        ROOT / "scripts/cloud_finish_atlas_matched_diversity_repair5.sh"
    ).read_text(encoding="utf-8")

    for source in (launcher, finisher):
        assert "20260816-atlas-matched-diversity-mvp-v1-repair5" in source
        assert "resource-envelope-only" in source
        assert "interaction_auxiliaries=binary" in source
        assert "uses_realized_outcomes=false" in source
        assert "production_change_licensed=false" in source
    assert 'JOB="atlas-md-s${SEASON}-w${WEEK}-r5"' in launcher
    assert "--cpu 8 --memory 32Gi" in launcher
    assert "--max-retries 0" in launcher
    assert "--task-timeout 12h" in launcher
    assert 'job!=f"atlas-md-s{season}-w{week}-r5"' in finisher
    assert '{"cpu":"8","memory":"32Gi"}' in finisher
    assert 'task.get("maxRetries")!=0' in finisher
    assert 'str(task.get("timeoutSeconds"))!="43200"' in finisher


def test_repair5_finisher_requires_complete_mechanical_population() -> None:
    source = (
        ROOT / "scripts/cloud_finish_atlas_matched_diversity_repair5.sh"
    ).read_text(encoding="utf-8")

    assert '[ "$(wc -l < "$EXECUTIONS")" = 54 ]' in source
    assert "execution is not terminal successful" in source
    assert 'row.get("mechanical_valid") is not True' in source
    assert 'row.get("global_atlas_additions")!=200' in source
    assert 'set(row.get("native_boom_counts",{}).values())!={40}' in source
    assert '"slates":54' in source
    assert "aggregate contains outcomes" in source
