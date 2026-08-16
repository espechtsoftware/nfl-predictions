import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/run_atlas_cbc_resource_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("atlas_cbc_resource", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_resource_diagnostic_population_and_firewall():
    assert MODULE.ALLOWED_CELLS == {(2024, 7), (2024, 15), (2024, 16)}
    source = SOURCE.read_text(encoding="utf-8")
    assert "actual_score" not in source
    assert "actual_rank" not in source
    assert "memory.events" in source
    assert "oom_kill_delta" in source
    assert "terminating_signal" in source
    assert "enumerate_matched_diversity_lineups" in source


def test_tracked_process_records_returncode_signal_and_oom_delta(monkeypatch):
    snapshots = iter([
        {
            "version": 2, "path": "/cg", "events": {"oom_kill": 3},
            "memory_current": 100, "memory_peak": 200,
            "memory_max": 1000, "available": True,
        },
        {
            "version": 2, "path": "/cg", "events": {"oom_kill": 4},
            "memory_current": 120, "memory_peak": 950,
            "memory_max": 1000, "available": True,
        },
    ])

    class FakeProcess:
        def wait(self):
            return -9

    monkeypatch.setattr(MODULE, "_read_cgroup_snapshot", lambda: next(snapshots))
    monkeypatch.setattr(MODULE, "_ORIGINAL_POPEN", lambda *a, **k: FakeProcess())
    monkeypatch.setattr(MODULE, "_FIRST_CGROUP_BEFORE", None)
    monkeypatch.setattr(MODULE, "_LAST_CHILD", None)
    monkeypatch.setattr(MODULE, "_OOM_KILL_DELTA_TOTAL", 0)
    monkeypatch.setattr(MODULE, "_MAX_PEAK_BYTES", None)
    monkeypatch.setattr(MODULE, "_MAX_PEAK_RATIO", None)
    process = MODULE._tracking_popen(["cbc"])
    assert process.wait() == -9
    summary = MODULE._resource_summary()
    assert summary["last_child"]["returncode"] == -9
    assert summary["last_child"]["terminating_signal"] == "SIGKILL"
    assert summary["oom_kill_delta_total"] == 1
    assert summary["maximum_memory_peak_bytes"] == 950
    assert summary["maximum_memory_peak_ratio"] == 0.95


def test_launcher_and_finisher_bind_exact_resource_diagnostic():
    launcher = (
        ROOT / "scripts/cloud_atlas_cbc_resource_diagnostic.sh"
    ).read_text(encoding="utf-8")
    finisher = (
        ROOT / "scripts/cloud_finish_atlas_cbc_resource_diagnostic.sh"
    ).read_text(encoding="utf-8")
    assert "for WEEK in 7 15 16" in launcher
    assert "--cpu 1 --memory 4Gi" in launcher
    assert "--max-retries 0 --task-timeout 12h" in launcher
    assert 'SOURCE_SHA=$(sha256sum "$SOURCE"' in launcher
    assert "oom-kill-confirmed" in finisher
    assert "isolated-r0-success-memory-pressure" in finisher
    assert "pressure_ratio_boundary" in finisher
    assert 'done[0].get("status") not in {"True","False"}' in finisher


def test_protocol_freezes_memory_interpretation_before_launch():
    protocol = (
        ROOT / "reports/2026-08-16-atlas-cbc-resource-diagnostic-protocol.md"
    ).read_text(encoding="utf-8")
    assert "before\neither native-log diagnostic reached terminal state" in protocol
    assert "one CPU and 4 GiB" in protocol
    assert "memory.peak / memory.max" in protocol
    assert "0.80" in protocol
