from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_PATH = Path(__file__).parents[1] / "scripts" / "compare_pit_tier1.py"
_SPEC = spec_from_file_location("_compare_pit_tier1", _PATH)
assert _SPEC and _SPEC.loader
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_tier1_comparator_is_packaged_in_runtime_image():
    dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text(
        encoding="utf-8"
    )
    assert (
        "COPY scripts/compare_pit_tier1.py "
        "./scripts/compare_pit_tier1.py"
    ) in dockerfile


def _metrics(values, mean=180.0):
    report = {f"clear_{threshold}": int(values.get(threshold, 0))
              for threshold in _MODULE.THRESHOLDS}
    report["mean_best"] = mean
    return report


def test_lexicographic_decision_prioritizes_highest_non_tied_threshold():
    source = _metrics({240: 2, 230: 3, 220: 5, 210: 7, 200: 13})
    treatment = _metrics({240: 2, 230: 4, 220: 4, 210: 9, 200: 20})
    result = _MODULE.lexicographic_decision(source, treatment)
    assert result["first_difference"] == 230
    assert result["treatment_selected"]

    treatment["clear_230"] = 2
    result = _MODULE.lexicographic_decision(source, treatment)
    assert result["first_difference"] == 230
    assert not result["treatment_selected"]


def test_lexicographic_decision_uses_mean_only_after_full_grid_tie():
    source = _metrics({}, mean=180.0)
    treatment = _metrics({}, mean=180.1)
    result = _MODULE.lexicographic_decision(source, treatment)
    assert result["first_difference"] is None
    assert result["tiebreaker"] == "mean_best"
    assert result["treatment_selected"]
