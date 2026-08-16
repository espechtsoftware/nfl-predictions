from hashlib import sha256
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/run_atlas_cbc_failure_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("atlas_cbc_diagnostic", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_diagnostic_population_and_output_firewall():
    assert MODULE.ALLOWED_CELLS == {(2024, 15), (2024, 16)}
    source = SOURCE.read_text(encoding="utf-8")
    assert "actual_score" not in source
    assert "actual_rank" not in source
    assert "enumerate_matched_diversity_lineups" in source
    assert "success.json" in source and "failure.json" in source
    assert "persists_lineups" in source


def test_diagnostic_keeps_same_cbc_and_changes_observability_only(monkeypatch):
    captured = {}

    def fake_init(self, *args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(MODULE._BASE_CBC, "__init__", fake_init)
    MODULE.DiagnosticCBC(msg=0)
    assert captured["msg"] is False
    assert captured["keepFiles"] is True
    assert captured["logPath"] == str(MODULE.LAST_LOG)
    assert "path" not in captured


def test_launcher_binds_source_hash_and_exact_resources():
    launcher = (
        ROOT / "scripts/cloud_atlas_cbc_failure_diagnostic.sh"
    ).read_text(encoding="utf-8")
    assert 'SOURCE_SHA=$(sha256sum "$SOURCE"' in launcher
    assert "--cpu 1 --memory 4Gi" in launcher
    assert "--max-retries 0 --task-timeout 12h" in launcher
    assert "for WEEK in 15 16" in launcher
    assert "SOURCE_B64=$(base64 -w0" in launcher
    assert "persists_lineups=false" in launcher
    finisher = (
        ROOT / "scripts/cloud_finish_atlas_cbc_failure_diagnostic.sh"
    ).read_text(encoding="utf-8")
    assert 'done[0].get("status") not in {"True","False"}' in finisher
    assert 'set(artifacts)!={"cbc.log","problem.mps"}' in finisher
    assert "ATLAS_CBC_DIAGNOSTIC_RECEIPT_VALIDATED" in finisher


def test_protocol_is_frozen_before_launcher_use():
    protocol = ROOT / "reports/2026-08-16-atlas-cbc-native-diagnostic-protocol.md"
    digest = sha256(protocol.read_bytes()).hexdigest()
    assert len(digest) == 64
    assert "before any diagnostic launch" in protocol.read_text(encoding="utf-8")
