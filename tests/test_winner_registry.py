from __future__ import annotations

from pathlib import Path

import pytest

from nfl_dfs.research import winner_registry as registry_module

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def registry() -> dict[str, object]:
    return registry_module.build_winner_registry(ROOT / "reports")


def test_registry_reconciles_the_documented_population(registry):
    assert registry["contest_count"] == 68
    assert registry["governed_cohort_count"] == 51
    assert registry["per_season_contest_counts"] == {
        "2019": 17, "2023": 17, "2024": 17, "2025": 17,
    }
    exclusion = registry["excluded_duplicates"][0]
    assert (exclusion["season"], exclusion["week"]) == (2024, 9)
    assert exclusion["rows_excluded"] == 9
    assert all(
        len(contest["players"]) == 9 for contest in registry["contests"]
    )


def test_registry_records_the_known_defects_exactly(registry):
    flag_counts: dict[str, int] = {}
    for contest in registry["contests"]:
        for flag in contest["integrity_flags"]:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
    assert flag_counts["raw-salary-total-above-cap"] == 5
    assert flag_counts["missing-salary"] == 1
    assert flag_counts["summary-salary-used-missing"] == 3
    assert flag_counts["article-score-disagrees"] >= 10
    assert set(registry["provenance_gaps"]) == {
        "contest-id-absent", "source-url-absent", "capture-time-absent",
    }


def test_registry_self_hash_and_contest_lookup(registry):
    remainder = {
        key: value for key, value in registry.items()
        if key != "winner_registry_sha256"
    }
    assert registry_module.canonical_sha256(remainder) == (
        registry["winner_registry_sha256"]
    )
    contest = registry_module.registry_contest(registry, 2023, 1)
    assert contest["slate_key"] == "2023-w01"
    assert contest["roster_points_total"] == pytest.approx(233.24)
    assert contest["governed_cohort"] is True
    with pytest.raises(
        registry_module.WinnerRegistryError, match="no contest"
    ):
        registry_module.registry_contest(registry, 2020, 1)


def test_registry_never_grants_authority(registry):
    assert registry["promotion_authority"] is False
    assert "NEVER a live feature input" in registry["outcome_scope"]
