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


def test_a_term_block_week_copies_the_term_file_with_its_sha_and_refuses_without_it(tmp_path):
    """Study 38 amendment 6 (10-07): the union's --term-block-source travels with the snapshot (sha in MANIFEST.txt);
    a union naming --term-block-rows without a readable term file is refused."""
    ud, out = _setup(tmp_path, own=False)
    term = tmp_path / "priortop-w5.csv"; term.write_text("dk_player_id,pred_own\n1,10\n")
    args = (out / "union-args-T.txt").read_text().strip() + f" --term-block-rows 8 --term-block-source {term}"
    (out / "union-args-T.txt").write_text(args + "\n")
    env = {"S38_NO_COLLECT": "1", "SEASON": "2026", "WEEK": "5", "PROD": str(ROOT), "PROD_PY": "/bin/false", "PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    (out / "ownership_lag.csv").write_text("x")
    r = _run(tmp_path, ud, out, tmp_path / "dest", env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    copied = tmp_path / "dest" / "priortop-w5.csv"
    assert copied.read_text() == term.read_text()
    manifest = (tmp_path / "dest" / "MANIFEST.txt").read_text()
    assert hashlib.sha256(term.read_bytes()).hexdigest() in manifest and str(term) in manifest
    term.unlink()
    r2 = _run(tmp_path, ud, out, tmp_path / "dest2", env=env)
    assert r2.returncode == 1 and "--term-block-rows 8 but the term file" in r2.stdout


def test_the_paper_term_file_is_copied_as_paper_term_with_its_sha(tmp_path):
    """Study 38 amendment 6b (10-07; the operator: the prior-top block on paper): S38_PAPER_TERM_FILE is copied as
    paper-term-<basename> with its sha in MANIFEST.txt; a named but missing file is refused; unset copies nothing."""
    import os
    ud, out = _setup(tmp_path)
    paper = tmp_path / "priortop-w5.csv"; paper.write_text("dk_player_id,pred_own\n1,10\n")
    env = dict(os.environ, S38_PAPER_TERM_FILE=str(paper))
    r = _run(tmp_path, ud, out, tmp_path / "dest", env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    copied = tmp_path / "dest" / "paper-term-priortop-w5.csv"
    assert copied.read_text() == paper.read_text()
    assert hashlib.sha256(paper.read_bytes()).hexdigest() in (tmp_path / "dest" / "MANIFEST.txt").read_text()
    r2 = _run(tmp_path, ud, out, tmp_path / "dest2", env=dict(os.environ, S38_PAPER_TERM_FILE=str(tmp_path / "none.csv")))
    assert r2.returncode == 1 and "S38_PAPER_TERM_FILE" in r2.stdout
    env3 = {k: v for k, v in os.environ.items() if k != "S38_PAPER_TERM_FILE"}
    r3 = _run(tmp_path, ud, out, tmp_path / "dest3", env=env3)
    assert r3.returncode == 0 and not any(p.name.startswith("paper-term") for p in (tmp_path / "dest3").iterdir())


def test_the_paper_dvp_file_is_copied_as_paper_dvp_with_its_sha_beside_the_paper_term(tmp_path):
    """Study 38 amendment 6c (10-07; the operator: the FP-means DvP arm on paper): S38_PAPER_DVP_FILE (written by
    scripts/paper_dvp_file.py) is copied as paper-dvp-<basename> with its sha in MANIFEST.txt, beside the paper term
    file; a named but missing file is refused; unset copies nothing."""
    import os
    ud, out = _setup(tmp_path)
    paper = tmp_path / "priortop-w5.csv"; paper.write_text("dk_player_id,pred_own\n1,10\n")
    dvp = tmp_path / "w05.csv"; dvp.write_text("dk_player_id,pos,z,slope,adj_points,weeks,n\n1,WR,0.5,0.6,0.3,4,152\n")
    base = {k: v for k, v in os.environ.items() if k not in ("S38_PAPER_TERM_FILE", "S38_PAPER_DVP_FILE")}
    r = _run(tmp_path, ud, out, tmp_path / "dest", env=dict(base, S38_PAPER_TERM_FILE=str(paper), S38_PAPER_DVP_FILE=str(dvp)))
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "dest" / "paper-dvp-w05.csv").read_bytes() == dvp.read_bytes()
    assert (tmp_path / "dest" / "paper-term-priortop-w5.csv").read_bytes() == paper.read_bytes()
    manifest = (tmp_path / "dest" / "MANIFEST.txt").read_text()
    assert hashlib.sha256(dvp.read_bytes()).hexdigest() in manifest and "paper-dvp-w05.csv" in manifest
    r2 = _run(tmp_path, ud, out, tmp_path / "dest2", env=dict(base, S38_PAPER_DVP_FILE=str(tmp_path / "none.csv")))
    assert r2.returncode == 1 and "S38_PAPER_DVP_FILE" in r2.stdout and not (tmp_path / "dest2").exists()
    r3 = _run(tmp_path, ud, out, tmp_path / "dest3", env=base)
    assert r3.returncode == 0 and not any(p.name.startswith("paper-dvp") for p in (tmp_path / "dest3").iterdir())


def test_the_paper_factor_file_is_copied_as_paper_factor_with_its_sha_beside_the_others(tmp_path):
    """Study 38 amendment 6d (10-07): S38_PAPER_FACTOR_FILE (written by scripts/paper_factor_file.py) is copied as
    paper-factor-<basename> with its sha in MANIFEST.txt, beside the paper term and DvP files; a named but missing
    file is refused; unset copies nothing."""
    import os
    ud, out = _setup(tmp_path)
    paper = tmp_path / "priortop-w5.csv"; paper.write_text("dk_player_id,pred_own\n1,10\n")
    dvp = tmp_path / "w05.csv"; dvp.write_text('# {"slope": 0.6}\ndk_player_id,gsis_id,pos,opp,z,slope,fp,adj_points\n1,00-1,WR,NO,0.5,0.6,12,12.3\n')
    fac = tmp_path / "f05.csv"
    fac.write_text('# {"study": "38 amendment 6d"}\ndk_player_id,gsis_id,pos,team,opp,b_matchup,b_vacated,b_market,b_combined,fp\n1,00-1,WR,ATL,NO,0.5,0,0,0.5,12\n')
    keys = ("S38_PAPER_TERM_FILE", "S38_PAPER_DVP_FILE", "S38_PAPER_FACTOR_FILE")
    base = {k: v for k, v in os.environ.items() if k not in keys}
    r = _run(tmp_path, ud, out, tmp_path / "dest", env=dict(base, S38_PAPER_TERM_FILE=str(paper), S38_PAPER_DVP_FILE=str(dvp),
                                                            S38_PAPER_FACTOR_FILE=str(fac)))
    assert r.returncode == 0, r.stdout + r.stderr
    for name, src in (("paper-factor-f05.csv", fac), ("paper-dvp-w05.csv", dvp), ("paper-term-priortop-w5.csv", paper)):
        assert (tmp_path / "dest" / name).read_bytes() == src.read_bytes()
    manifest = (tmp_path / "dest" / "MANIFEST.txt").read_text()
    assert hashlib.sha256(fac.read_bytes()).hexdigest() in manifest and "paper-factor-f05.csv" in manifest
    r2 = _run(tmp_path, ud, out, tmp_path / "dest2", env=dict(base, S38_PAPER_FACTOR_FILE=str(tmp_path / "none.csv")))
    assert r2.returncode == 1 and "S38_PAPER_FACTOR_FILE" in r2.stdout and not (tmp_path / "dest2").exists()
    r3 = _run(tmp_path, ud, out, tmp_path / "dest3", env=base)
    assert r3.returncode == 0 and not any(p.name.startswith("paper-factor") for p in (tmp_path / "dest3").iterdir())


def test_the_paper_matchup_block_file_is_copied_as_paper_mblock_beside_the_live_cheap_block(tmp_path):
    """Study 38 amendment 6i (10-07): with the CHEAP block live, S38_PAPER_MBLOCK_FILE (the matchup block's file) is copied
    as paper-mblock-<basename> with its sha in MANIFEST.txt; a named but missing file is refused; unset copies nothing."""
    import os
    ud, out = _setup(tmp_path)
    mb = tmp_path / "matchup-w5.csv"; mb.write_text("dk_player_id,id,display_name,pos,team,opp,pred_own,bonus_points\n1,a,A,WR,X,Y,5.0,1.0\n")
    keys = ("S38_PAPER_TERM_FILE", "S38_PAPER_DVP_FILE", "S38_PAPER_FACTOR_FILE", "S38_PAPER_MBLOCK_FILE")
    base = {k: v for k, v in os.environ.items() if k not in keys}
    r = _run(tmp_path, ud, out, tmp_path / "dest", env=dict(base, S38_PAPER_MBLOCK_FILE=str(mb)))
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "dest" / "paper-mblock-matchup-w5.csv").read_bytes() == mb.read_bytes()
    manifest = (tmp_path / "dest" / "MANIFEST.txt").read_text()
    assert hashlib.sha256(mb.read_bytes()).hexdigest() in manifest and "paper-mblock-matchup-w5.csv" in manifest
    r2 = _run(tmp_path, ud, out, tmp_path / "dest2", env=dict(base, S38_PAPER_MBLOCK_FILE=str(tmp_path / "none.csv")))
    assert r2.returncode == 1 and "S38_PAPER_MBLOCK_FILE" in r2.stdout and not (tmp_path / "dest2").exists()
    r3 = _run(tmp_path, ud, out, tmp_path / "dest3", env=base)
    assert r3.returncode == 0 and not any(p.name.startswith("paper-mblock") for p in (tmp_path / "dest3").iterdir())


def test_the_paper_hot_file_is_copied_as_paper_hot_with_its_sha_beside_the_others(tmp_path):
    """Study 38 amendment 6y (10-10; the operator, relaying the researcher: a HOT1 paper arm): S38_PAPER_HOT_FILE (written by
    reports/2026-10-10-paper-hot/paper_hot_flags.py as ~/private/paper-corun/hot/w05.csv) is copied as paper-hot-<basename>
    with its sha in MANIFEST.txt; a named but missing file is refused; unset copies nothing."""
    import os
    ud, out = _setup(tmp_path)
    hot = tmp_path / "w05.csv"
    hot.write_text('# {"what": "hot flags (study 109\'s HOT1)"}\ndk_player_id,gsis_id,name,pos,last_week,last_pts,prior_mean,prior_n,hot\n1,a,A,WR,4,30.0,10.0,4,1\n')
    keys = ("S38_PAPER_TERM_FILE", "S38_PAPER_DVP_FILE", "S38_PAPER_FACTOR_FILE", "S38_PAPER_MBLOCK_FILE", "S38_PAPER_HOT_FILE")
    base = {k: v for k, v in os.environ.items() if k not in keys}
    r = _run(tmp_path, ud, out, tmp_path / "dest", env=dict(base, S38_PAPER_HOT_FILE=str(hot)))
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "dest" / "paper-hot-w05.csv").read_bytes() == hot.read_bytes()
    manifest = (tmp_path / "dest" / "MANIFEST.txt").read_text()
    assert hashlib.sha256(hot.read_bytes()).hexdigest() in manifest and "paper-hot-w05.csv" in manifest and str(hot) in manifest
    r2 = _run(tmp_path, ud, out, tmp_path / "dest2", env=dict(base, S38_PAPER_HOT_FILE=str(tmp_path / "none.csv")))
    assert r2.returncode == 1 and "S38_PAPER_HOT_FILE" in r2.stdout and not (tmp_path / "dest2").exists()
    r3 = _run(tmp_path, ud, out, tmp_path / "dest3", env=base)
    assert r3.returncode == 0 and not any(p.name.startswith("paper-hot") for p in (tmp_path / "dest3").iterdir())


def test_the_paper_tdblock_file_is_copied_as_paper_tdblock_with_its_sha_beside_the_others(tmp_path):
    """Study 38 amendment 6z4 (10-10; the operator, "queue these", the afternoon page's item 3): S38_PAPER_TDBLOCK_FILE (written by
    scripts/td_value_block_file.py as ~/private/paper-corun/tdblock/w05.csv) is copied as paper-tdblock-<basename> with its sha in
    MANIFEST.txt; a named but missing file is refused; unset copies nothing."""
    import os
    ud, out = _setup(tmp_path)
    td = tmp_path / "w05.csv"
    td.write_text("dk_player_id,id,display_name,pos,team,opp,pred_own,bonus_points\n1,a,A,WR,X,Y,5.0,1.0\n")
    keys = ("S38_PAPER_TERM_FILE", "S38_PAPER_DVP_FILE", "S38_PAPER_FACTOR_FILE", "S38_PAPER_MBLOCK_FILE", "S38_PAPER_HOT_FILE",
            "S38_PAPER_TDBLOCK_FILE")
    base = {k: v for k, v in os.environ.items() if k not in keys}
    r = _run(tmp_path, ud, out, tmp_path / "dest", env=dict(base, S38_PAPER_TDBLOCK_FILE=str(td)))
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "dest" / "paper-tdblock-w05.csv").read_bytes() == td.read_bytes()
    manifest = (tmp_path / "dest" / "MANIFEST.txt").read_text()
    assert hashlib.sha256(td.read_bytes()).hexdigest() in manifest and "paper-tdblock-w05.csv" in manifest and str(td) in manifest
    r2 = _run(tmp_path, ud, out, tmp_path / "dest2", env=dict(base, S38_PAPER_TDBLOCK_FILE=str(tmp_path / "none.csv")))
    assert r2.returncode == 1 and "S38_PAPER_TDBLOCK_FILE" in r2.stdout and not (tmp_path / "dest2").exists()
    r3 = _run(tmp_path, ud, out, tmp_path / "dest3", env=base)
    assert r3.returncode == 0 and not any(p.name.startswith("paper-tdblock") for p in (tmp_path / "dest3").iterdir())


def test_a_package_week_copies_the_own_cap_file_and_generates_none(tmp_path):
    """Study 38 amendment 6o (10-09, his W5 package): a union with --main-own-cap-delta > 0 read --main-own-cap-source;
    the snapshot copies that file as named (sha and source in MANIFEST.txt) and runs no ownership export (no env needed)."""
    ud, out = _setup(tmp_path, own=False)
    cap = out / "ownership_fp-T.csv"
    args = (out / "union-args-T.txt").read_text().strip() + f" --main-cap-share 0.35 --main-own-cap-delta 15 --main-own-cap-source {cap}"
    (out / "union-args-T.txt").write_text(args + "\n")
    r = _run(tmp_path, ud, out, tmp_path / "dest", env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "amendment 6o" in r.stdout and "generating" not in r.stdout
    dest = tmp_path / "dest"
    assert (dest / "ownership_fp-T.csv").read_text() == "own" and not (dest / ".ownership_export.log").exists()
    line = next(x for x in (dest / "MANIFEST.txt").read_text().splitlines() if "  ownership_fp-T.csv  " in x)
    assert line.startswith(hashlib.sha256(b"own").hexdigest()) and str(cap) in line


def test_a_package_week_without_its_own_cap_file_is_refused(tmp_path):
    for i, extra in enumerate((" --main-own-cap-delta 15", " --main-own-cap-delta 15 --main-own-cap-source /nowhere/ownership_fp-T.csv")):
        t = tmp_path / str(i); t.mkdir()
        ud, out = _setup(t, own=False)
        (out / "union-args-T.txt").write_text((out / "union-args-T.txt").read_text().strip() + extra + "\n")
        r = _run(t, ud, out, t / "dest", env={"PATH": "/usr/bin:/bin", "HOME": str(t)})
        assert r.returncode == 1 and "own-cap file" in r.stdout and not (t / "dest").exists(), extra


def test_an_own_cap_file_and_a_term_file_with_one_name_but_two_contents_are_refused(tmp_path):
    ud, out = _setup(tmp_path)                                   # the term reads out/ownership_fp-T.csv ("own")
    other = tmp_path / "elsewhere"; other.mkdir(); (other / "ownership_fp-T.csv").write_text("different")
    args = (out / "union-args-T.txt").read_text().strip() + f" --main-own-cap-delta 15 --main-own-cap-source {other / 'ownership_fp-T.csv'}"
    (out / "union-args-T.txt").write_text(args + "\n")
    r = _run(tmp_path, ud, out, tmp_path / "dest")
    assert r.returncode == 1 and "share the name ownership_fp-T.csv but differ" in r.stdout
