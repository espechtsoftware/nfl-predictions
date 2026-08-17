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
    assert source.index('SEASON=2023\nWEEK=1') < source.index(
        "for SEASON in 2023 2024 2025"
    )
    assert source.index('bash "$CANARY_VALIDATOR"') < source.index(
        "for SEASON in 2023 2024 2025"
    )
    assert 'released_after_canary=53' in source


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

    assert '[ "$(wc -l < "$PRIMARY_EXECUTIONS")" = 54 ]' in source
    assert '[ "$(wc -l < "$ACCEPTED_EXECUTIONS")" = 54 ]' in source
    assert 'done < "$ACCEPTED_EXECUTIONS"' in source
    assert '"retry_executions=$RETRY_COUNT"' in source
    assert "max_replacement_executions_per_cell=1" in source
    assert "execution is not terminal successful" in source
    assert 'row.get("mechanical_valid") is not True' in source
    assert 'row.get("global_atlas_additions")!=200' in source
    assert 'set(row.get("native_boom_counts",{}).values())!={40}' in source
    assert '"slates":54' in source
    assert "aggregate contains outcomes" in source


def test_repair5_platform_retry_is_narrow_and_attempt_receipted() -> None:
    protocol = (
        ROOT / "reports/2026-08-16-atlas-repair5-bounded-platform-retry-amendment.md"
    )
    resolver = (
        ROOT / "scripts/cloud_prepare_atlas_matched_diversity_repair5_attempts.sh"
    )
    finisher = ROOT / "scripts/cloud_finish_atlas_matched_diversity_repair5.sh"
    assert sha256(protocol.read_bytes()).hexdigest() == (
        "d464660b72e669d261d7f6d4800b3e59d55726b56e7003c5e3e806f38fa987a0"
    )
    assert sha256(resolver.read_bytes()).hexdigest() == (
        "705b65e5164b775361a2efe1440059f76978c3701c192179a40d85f4b0c27093"
    )
    assert sha256(finisher.read_bytes()).hexdigest() == (
        "fe7a069e42bfece580ff4f312bc2990bd31339932713d834c2c123bbc431cdd9"
    )

    source = resolver.read_text(encoding="utf-8")
    assert "internal error running task" in source.lower()
    for disallowed in (
        "configured memory limit",
        "timeout",
        "signal",
        "sigkill",
        "solver",
        "cbc",
        "nonzero exit",
    ):
        assert disallowed in source
    assert 'gcloud storage ls "$URI"' in source
    assert 'gcloud run jobs execute "$JOB"' in source
    assert "gcloud run jobs deploy" not in source
    assert "gcloud storage cp" not in source
    assert "accepted-executions.txt" in source
    assert "max_replacement_executions_per_cell" in source
    assert '"effect_fields_inspected": False' in source


def test_repair5_real_path_canary_is_frozen_and_bound() -> None:
    amendment = (
        ROOT / "reports/2026-08-16-atlas-repair5-real-path-canary-amendment.md"
    )
    validator = ROOT / "scripts/cloud_wait_atlas_repair5_canary.sh"
    launcher = ROOT / "scripts/cloud_atlas_matched_diversity_repair5.sh"
    resolver = ROOT / "scripts/cloud_prepare_atlas_matched_diversity_repair5_attempts.sh"
    finisher = ROOT / "scripts/cloud_finish_atlas_matched_diversity_repair5.sh"
    assert sha256(amendment.read_bytes()).hexdigest() == (
        "b2d0e32dabeb87bb1a67bee58c01f00c4c0d97e3fac9d1f7181bfcee50abc242"
    )
    assert sha256(validator.read_bytes()).hexdigest() == (
        "e1c82612f231976563f0df12ffbe9f5e2db1aebfae636f61b723ad8699ae1411"
    )
    for path in (launcher, resolver, finisher):
        source = path.read_text(encoding="utf-8")
        assert "canary-completion.txt" in source
        assert "grid-release.txt" in source
        assert "released_after_canary" in source
    source = validator.read_text(encoding="utf-8")
    assert "ATLAS repair5 canary must precede the other 53 cells" in source
    assert 'gcloud storage objects describe "$URI"' in source
    assert "gcloud storage cp" not in source
    assert '"cpu": "8", "memory": "32Gi"' in source
    assert 'task.get("maxRetries") != 0' in source
    assert "ATLAS_REPAIR5_REAL_PATH_CANARY_FAILED" in source


def test_repair5_historical_canary_binding_is_frozen_before_results() -> None:
    amendment = (
        ROOT
        / "reports/2026-08-16-atlas-historical-score-repair5-canary-binding-amendment.md"
    )
    assert sha256(amendment.read_bytes()).hexdigest() == (
        "c893d958b300484e0468d84763267ee89211178127bf84fc664a9bbc8170ee1e"
    )
    text = amendment.read_text(encoding="utf-8")
    assert "before repair5 launch" in text
    assert "canary-completion.txt" in text
    assert "grid-release.txt" in text
    assert "accepted-executions.txt" in text


def test_repair5_historical_attempt_binding_is_frozen_before_results() -> None:
    amendment = (
        ROOT / "reports/2026-08-16-atlas-historical-score-attempt-binding-amendment.md"
    ).read_text(encoding="utf-8")
    assert "before repair5 launch" in amendment
    assert "before any repair5 score-free or" in amendment
    assert "accepted-executions.txt" in amendment
    assert "attempt-resolution.json" in amendment
    assert "primary-execution-metadata.sha256" in amendment
    assert "whether its score-free" in amendment


def test_repair5_queue_watcher_resolves_attempts_before_finishing_or_census() -> None:
    source = (ROOT / "scripts/watch_atlas_repair5_queue.sh").read_text(
        encoding="utf-8"
    )
    resolver = "cloud_prepare_atlas_matched_diversity_repair5_attempts.sh"
    finisher = "cloud_finish_atlas_matched_diversity_repair5.sh"
    census = "cloud_harvest_atlas_repair5_terminal_census.sh"
    assert source.index(resolver) < source.index(finisher)
    assert source.index(resolver) < source.index(census)
    assert "accepted-executions.txt" in source
    assert 'attempt_rc" -ne 10' in source
    assert "ATLAS_REPAIR5_ACCEPTED_STATUS" in source


def test_repair5_failure_census_is_frozen_and_score_free() -> None:
    protocol = ROOT / "reports/2026-08-16-atlas-repair5-terminal-census-protocol.md"
    census = ROOT / "scripts/cloud_harvest_atlas_repair5_terminal_census.sh"
    assert sha256(protocol.read_bytes()).hexdigest() == (
        "94a792d80c4a908aed56034add9635478c738a29522554670c09360458561d0f"
    )
    source = census.read_text(encoding="utf-8")
    assert "20260816-atlas-matched-diversity-mvp-v1-repair5" in source
    assert 'status_counts["False"] < 1' in source
    assert '"cpu": "8", "memory": "32Gi"' in source
    assert 'task.get("maxRetries") != 0' in source
    assert "gcloud storage ls" in source
    assert "gcloud storage cp" not in source
    assert '"effect_fields_inspected": False' in source
    assert '"historical_scoring_licensed": False' in source
    assert '"continuous_parity_capacity_released": True' in source
    assert "attempt-resolution.json" in source
    assert "retry-executions.txt" in source
    assert "terminal-census-retry-execution-metadata" in source
    assert "accepted-population-with-platform-replacements" in source
    assert "census includes nonterminal retry" in source


def test_repair4_narrative_empty_inventory_hash_matches_machine_ledger() -> None:
    run = (
        ROOT / "reports/atlas-matched-diversity-runs/"
        "20260816-atlas-matched-diversity-mvp-v1-repair4"
    )
    inventory = run / "terminal-census-object-inventory.txt"
    ledger = (run / "terminal-census-object-inventory.sha256").read_text(
        encoding="utf-8",
    ).split()[0]
    actual = sha256(inventory.read_bytes()).hexdigest()
    narrative = (
        ROOT / "reports/2026-08-16-atlas-repair4-terminal-census-result.md"
    ).read_text(encoding="utf-8")

    assert len(ledger) == 64
    assert actual == ledger
    assert f"`{actual}`" in narrative
