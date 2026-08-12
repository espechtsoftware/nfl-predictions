from pathlib import Path


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
