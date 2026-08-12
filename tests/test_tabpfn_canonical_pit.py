from pathlib import Path

import pandas as pd

from scripts.validate_tabpfn_canonical_pit import validate_report, validate_table


def test_canonical_pit_cache_is_write_once_and_provenance_bound():
    text = (
        Path(__file__).parents[1] / "scripts" / "tabpfn_gen" / "gen.py"
    ).read_text(encoding="utf-8")
    assert 'PIT_OUTPUT_TABLE = "tabpfn_projections_pit_v2"' in text
    assert "WriteDisposition.WRITE_EMPTY" in text
    assert "content_checksum" in text
    assert "schema_sha256" in text
    assert "feature_contract_sha256" in text
    assert "TABPFN_GEN_JSON=" in text
    assert "PIT-clean canonical cache has forbidden envs" in text
    build = (
        Path(__file__).parents[1]
        / "scripts" / "tabpfn_gen" / "cloudbuild.yaml"
    ).read_text(encoding="utf-8")
    assert "scripts/tabpfn_gen/Dockerfile" in build
    assert "${_IMAGE}" in build
    dockerfile = (
        Path(__file__).parents[1] / "scripts" / "tabpfn_gen" / "Dockerfile"
    ).read_text(encoding="utf-8")
    assert "COPY scripts/tabpfn_gen/gen.py /app/gen.py" in dockerfile
    assert "COPY scripts/tabpfn_gen/features.txt /app/features.txt" in dockerfile


def test_canonical_pit_validator_is_fail_closed():
    source = {
        "table": "p.nfl_features.player_week_training",
        "last_modified": "2026-08-11T00:00:00+00:00",
        "schema_sha256": "schema",
        "content_checksum": 123,
        "rows": 2,
        "active_rows": 1,
        "inactive_rows": 1,
    }
    report = {
        "disposition": "tabpfn-canonical-cache-generated",
        "code_sha": "abcdef1",
        "output_table": "p.nfl_features.tabpfn_projections_pit_v2",
        "write_disposition": "WRITE_EMPTY",
        "output_rows": 2,
        "unique_keys": 2,
        "target_seasons": [2019, 2021, 2022, 2023, 2024, 2025],
        "context_law": "all-prior-nonnull-labels",
        "context_max": 28_000,
        "random_seed": 7,
        "n_estimators": 4,
        "feature_contract_sha256": "features",
        "training_source": source,
    }
    assert validate_report(
        report,
        code_sha="abcdef1",
        feature_sha="features",
        source_identity=source,
        expected_rows=2,
    )["passes"]
    report["training_source"] = {**source, "content_checksum": 124}
    assert not validate_report(
        report,
        code_sha="abcdef1",
        feature_sha="features",
        source_identity=source,
        expected_rows=2,
    )["passes"]


def test_canonical_pit_table_validator_requires_exact_keys_and_quantiles():
    qcols = [
        "q01", "q05", "q10", "q20", "q30", "q40", "q50",
        "q60", "q70", "q80", "q90", "q95", "q99",
    ]
    keys = pd.DataFrame({
        "season": [2019, 2021, 2022, 2023, 2024, 2025],
        "week": [1] * 6,
        "gsis_id": [f"p{i}" for i in range(6)],
    })
    table = keys.copy()
    table["mean"] = 5.0
    for index, col in enumerate(qcols):
        table[col] = float(index)
    assert validate_table(table, keys)["passes"]
    table.loc[0, "q50"] = -10.0
    assert not validate_table(table, keys)["passes"]
