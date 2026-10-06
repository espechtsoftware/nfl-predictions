"""scripts/s38_snapshot.sh (study 38's pre-lock snapshot): offline paths on synthetic files. The no-term export path
needs BigQuery and is exercised by hand (W4 frame, an old --now, no vendor call; HANDOFF 10-06)."""
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "s38_snapshot.sh"


def _setup(tmp_path: Path, own: bool = True, proj: bool = True, proj_copy_differs: bool = False):
    ud, out = tmp_path / "ud", tmp_path / "out"
    ud.mkdir(); out.mkdir()
    (ud / "frame.parquet").write_text("frame")
    (ud / "receipt.json").write_text('{"built_utc": "2026-10-11T15:55:00Z", "lock_utc": "2099-01-01 17:00:00+00:00"}')
    (out / "proj_fp-T.csv").write_text("proj")
    (out / "proj_fp-T.csv.json").write_text("{}")
    (out / "ownership_fp-T.csv").write_text("own")
    (out / "contests.json").write_text("[]")
    (tmp_path / "details.json").write_text("{}")
    src = out / "proj_fp-T.csv"
    if proj_copy_differs:
        src = out / "other.csv"; src.write_text("different")
    args = "--saturday-run auto --entries 26"
    if proj:
        args += f" --proj-source {src}"
    if own:
        args += f" --main-own-tilt 0.20 --main-own-source {out / 'ownership_fp-T.csv'}"
    (out / "union-args-T.txt").write_text(args + "\n")
    return ud, out


def _run(tmp_path, ud, out, dest, overrides="-", env=None):
    return subprocess.run(["bash", str(SCRIPT), str(ud), str(out), "T", str(tmp_path / "details.json"), overrides, str(dest)],
                          capture_output=True, text=True, env=env)


def test_happy_path_copies_one_file_per_pattern_and_manifests_every_sha(tmp_path):
    ud, out = _setup(tmp_path)
    r = _run(tmp_path, ud, out, tmp_path / "dest")
    assert r.returncode == 0, r.stdout + r.stderr
    files = sorted(p.name for p in (tmp_path / "dest").iterdir() if not p.name.startswith("."))
    assert files == ["MANIFEST.txt", "contest-details.json", "contests.json", "frame.parquet", "ownership_fp-T.csv",
                     "plan-overrides.json", "proj_fp-T.csv", "proj_fp-T.csv.json", "union-args-T.txt", "union-receipt.json"]
    manifest = (tmp_path / "dest" / "MANIFEST.txt").read_text()
    for f in files:
        if f != "MANIFEST.txt":
            assert hashlib.sha256((tmp_path / "dest" / f).read_bytes()).hexdigest() in manifest, f
    assert (tmp_path / "dest" / "plan-overrides.json").read_text().strip() == "{}"
    assert "dk-status" not in " ".join(files)          # production passes no --dk-status (O-16): none is copied


def test_create_once_and_never_under_a_week_dir(tmp_path):
    ud, out = _setup(tmp_path)
    assert _run(tmp_path, ud, out, tmp_path / "dest").returncode == 0
    again = _run(tmp_path, ud, out, tmp_path / "dest")
    assert again.returncode == 1 and "exists (create-once" in again.stdout
    week = _run(tmp_path, ud, out, Path.home() / "week99-sunday" / "snap")
    assert week.returncode == 1 and "never under ~/weekN-sunday" in week.stdout


def test_refuses_a_proj_source_that_differs_from_out_and_a_week_without_fp(tmp_path):
    ud, out = _setup(tmp_path, proj_copy_differs=True)
    r = _run(tmp_path, ud, out, tmp_path / "dest")
    assert r.returncode == 1 and "differs from" in r.stdout
    t2 = tmp_path / "b"; t2.mkdir()
    ud2, out2 = _setup(t2, proj=False)
    r2 = _run(t2, ud2, out2, t2 / "dest")
    assert r2.returncode == 1 and "no --proj-source" in r2.stdout


def test_a_no_term_week_needs_the_export_env(tmp_path):
    ud, out = _setup(tmp_path, own=False)
    r = subprocess.run(["bash", str(SCRIPT), str(ud), str(out), "T", str(tmp_path / "details.json"), "-", str(tmp_path / "dest")],
                       capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home())})
    assert r.returncode != 0 and "no-term week" in r.stdout          # SEASON/WEEK/PROD/PROD_PY unset: it stops, loudly


def test_refuses_at_or_after_the_lock_by_the_union_receipt(tmp_path):
    """Reviewer R2 (10-06): pre-lock by content; the lock comes from the union receipt and the snapshot time (or
    S38_NOW) must be strictly before it. The receipt is kept as union-receipt.json for the build's own check."""
    import os
    ud, out = _setup(tmp_path)
    (ud / "receipt.json").write_text('{"built_utc": "2026-10-11T15:55:00Z", "lock_utc": "2026-10-11 17:00:00+00:00"}')
    env = {**os.environ, "S38_NOW": "2026-10-11T17:00:00Z"}
    r = _run(tmp_path, ud, out, tmp_path / "dest", env=env)
    assert r.returncode == 1 and "at or after the lock" in r.stdout and not (tmp_path / "dest").exists()
    ok = _run(tmp_path, ud, out, tmp_path / "dest2", env={**os.environ, "S38_NOW": "2026-10-11T16:59:59Z"})
    assert ok.returncode == 0, ok.stdout
    assert (tmp_path / "dest2" / "union-receipt.json").read_text() == (ud / "receipt.json").read_text()
    norec = tmp_path / "c"; norec.mkdir(); ud3, out3 = _setup(norec)
    (ud3 / "receipt.json").write_text('{"built_utc": "x"}')
    r3 = _run(norec, ud3, out3, norec / "dest")
    assert r3.returncode == 1 and "no lock_utc" in r3.stdout


def test_a_failed_copy_stops_the_tool(tmp_path):
    """Reviewer R1 (10-06): without set -e a failed cp continued and printed 'snapshot written' over a partial copy."""
    import os
    if os.geteuid() == 0:
        import pytest
        pytest.skip("root reads unreadable files")
    ud, out = _setup(tmp_path)
    (out / "contests.json").chmod(0)
    try:
        r = _run(tmp_path, ud, out, tmp_path / "dest")
    finally:
        (out / "contests.json").chmod(0o644)
    assert r.returncode == 1 and "copy failed: contests.json" in r.stdout and "snapshot written" not in r.stdout
    assert (tmp_path / "dest" / "SNAPSHOT-FAILED.txt").exists() and not (tmp_path / "dest" / "MANIFEST.txt").exists()
