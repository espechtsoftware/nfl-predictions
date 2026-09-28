"""The watcher's publish gate: audit_passed required; union mode needs config.union or union_failed; audit_failed never."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_dir_publishable as rp  # noqa: E402


def _run(tmp_path, union=False, files=("receipt.json", "candidates.parquet", "incumbent_player_scores.npy")):
    d = tmp_path / "r"; d.mkdir(exist_ok=True)
    for f in files:
        (d / f).write_text(json.dumps({"config": {"union": {"t70_run": "x"} if union else None}}) if f == "receipt.json" else "x")
    return d


def test_incomplete_run_dir_is_not_publishable(tmp_path):
    d = _run(tmp_path, files=("receipt.json",))
    ok, why = rp.publishable(d, False)
    assert not ok and "not written yet" in why


def test_audit_marker_gates_publication(tmp_path):
    d = _run(tmp_path)
    ok, why = rp.publishable(d, False)
    assert not ok and "audit_passed" in why
    (d / "audit_passed").touch()
    assert rp.publishable(d, False) == (True, "publishable")
    (d / "audit_failed").touch()
    ok, why = rp.publishable(d, False)
    assert not ok and "refused" in why


def test_union_mode_publishes_only_the_union_or_a_marked_fallback(tmp_path):
    plain = _run(tmp_path); (plain / "audit_passed").touch()
    ok, why = rp.publishable(plain, True)
    assert not ok and "union" in why
    (plain / "union_failed").touch()
    assert rp.publishable(plain, True)[0]
    u = tmp_path / "u"; u.mkdir()
    for f in ("candidates.parquet", "incumbent_player_scores.npy", "audit_passed"):
        (u / f).write_text("x")
    (u / "receipt.json").write_text(json.dumps({"config": {"union": {"t70_run": "x"}}}))
    assert rp.publishable(u, True)[0]


def test_rehearsal_override_is_explicit(tmp_path):
    d = _run(tmp_path)
    ok, why = rp.publishable(d, False, audit_gate=False)
    assert ok and "rehearsal override" in why
    assert rp.main([str(d)]) == 1 and rp.main([str(d), "--no-audit-gate"]) == 0
