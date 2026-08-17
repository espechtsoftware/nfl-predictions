import importlib.util
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_atlas_repair6_code_diff.py"


def _module():
    spec = importlib.util.spec_from_file_location("atlas_repair6_diff", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_repair6_code_diff_is_exact_and_outcome_free():
    result = _module().validate()
    assert result["disposition"] == "valid-exact-identity-tiebreak-extension"
    assert result["tolerances"] == [1e-6, 1e-5, 1e-4]
    assert result["uses_realized_outcomes"] is False
    assert result["candidate_or_lineup_scores_read"] is False
    assert result["production_change_licensed"] is False


def test_repair6_code_diff_is_exact_without_git_history(monkeypatch):
    module = _module()

    def no_history(*args, **kwargs):
        raise subprocess.CalledProcessError(128, args[0])

    monkeypatch.setattr(module.subprocess, "run", no_history)
    result = module.validate()

    assert result["disposition"] == "valid-exact-identity-tiebreak-extension"
    assert result["repair5_source_sha256"] == module.REPAIR5_SOURCE_SHA256
    assert result["repair6_source_sha256"] == module.REPAIR6_SOURCE_SHA256
    assert result["repair6_diff_sha256"] == module.REPAIR6_DIFF_SHA256
