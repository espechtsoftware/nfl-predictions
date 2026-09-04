"""Static fail-closed contract for the GPU cache's bounded live refresh."""

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_upcoming_only_reuses_and_guards_the_existing_cache() -> None:
    source = (ROOT / "scripts/tabpfn_gen/gen.py").read_text(encoding="utf-8")

    assert 'UPCOMING_ONLY = os.environ.get("TABPFN_UPCOMING_ONLY", "").strip()' in source
    assert 'TABPFN_UPCOMING_ONLY=1 requires TABPFN_UPCOMING=season:week' in source
    assert 'upcoming-only refresh is allowed only for the mutable live cache' in source
    assert 'validate_output_frame(cached, "existing live cache")' in source
    assert "existing live cache lacks immutable metadata" in source
    assert 'existing live cache lacks historical seasons' in source
    assert 'current_cache_meta.etag != base_cache["etag"]' in source
    assert 'live cache changed after upcoming-only read' in source
    assert 'drop_duplicates(\n    ["season", "week", "gsis_id"], keep="last")' in source


def test_gpu_state_is_released_between_fits() -> None:
    source = (ROOT / "scripts/tabpfn_gen/gen.py").read_text(encoding="utf-8")

    assert "gc.collect()" in source
    assert "torch.cuda.empty_cache()" in source
