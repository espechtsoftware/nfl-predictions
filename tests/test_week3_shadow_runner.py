"""Offline tests for the Week-3 shadow runner and reader on a synthetic run directory.
Requires the pinned lab clone for `nfl2.selectors` (skipped when absent): NFL2_CLONE env or the Week-2 release path."""
import csv, json, os, pathlib, subprocess, sys
import numpy as np, pandas as pd, pytest

CLONE = os.environ.get("NFL2_CLONE", "/home/erich/projects/.nfl2-worktrees/week2-release-2dc116c")
PY = sys.executable
ROOT = pathlib.Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not pathlib.Path(CLONE, "src", "nfl2", "selectors.py").exists(), reason="pinned lab clone not present")


def totals_law(banks, idx):
    out = []
    for b in banks:
        acc = b[idx[:, 0]].copy()
        for j in range(1, 9): acc += b[idx[:, j]]
        out.append(acc)
    return np.concatenate(out, axis=1)


def make_run(tmp, n_cands=30, sims=40, seed=7):
    rng = np.random.default_rng(seed)
    pos = ["QB"] * 3 + ["RB"] * 4 + ["WR"] * 6 + ["TE"] * 3 + ["DST"] * 2
    teams = ["A", "B", "C"] * 6
    n = len(pos); ids = [f"p{i:02d}" if pos[i] != "DST" else f"{teams[i]}_DST" for i in range(n)]
    fr = pd.DataFrame({"id": ids, "name": [f"N{i}" for i in range(n)], "pos": pos, "team": teams[:n], "salary": 4000, "proj": rng.uniform(4, 20, n).round(2)})
    fr.loc[fr.pos == "DST", "proj"] = 8.0
    qbs, dsts, rest = [i for i in range(n) if pos[i] == "QB"], [i for i in range(n) if pos[i] == "DST"], [i for i in range(n) if pos[i] not in ("QB", "DST")]
    rosters = set()
    while len(rosters) < n_cands:
        r = tuple(sorted([rng.choice(qbs), rng.choice(dsts), *rng.choice(rest, 7, replace=False)])); rosters.add(r)
    rosters = sorted(rosters); idx = np.array(rosters)
    banks = [rng.normal(10, 6, (n, sims)).astype(np.float32) for _ in range(2)]
    sys.path.insert(0, str(pathlib.Path(CLONE) / "src")); from nfl2.selectors import select_expected_max
    K = 5; book = select_expected_max(totals_law(banks, idx), K)
    rank = np.zeros(n_cands); rank[book] = np.arange(1, K + 1)
    cands = pd.DataFrame({"cand": range(n_cands), "players": [",".join(ids[i] for i in r) for r in rosters], "names": ["|".join(fr.name[i] for i in r) for r in rosters], "book_rank": rank})
    run = tmp / "run"; run.mkdir(); fr.to_parquet(run / "frame.parquet"); cands.to_parquet(run / "candidates.parquet")
    np.save(run / "incumbent_player_scores.npy", banks[0]); np.save(run / "corrected_hsim_player_scores.npy", banks[1])
    (run / "receipt.json").write_text(json.dumps({"identity": {"test": True}, "config": {"selector": "dual_emax", "operational_k": K, "sims": sims, "seed": 1, "hsim_seed": 2, "hsim_worlds": sims}}))
    (run / "book.json").write_text(json.dumps({"entries": [{"rank": r + 1, "players": [fr.name[i] for i in rosters[b]]} for r, b in enumerate(book)]}))
    contests = tmp / "contests.json"; contests.write_text(json.dumps([{"name": "milly", "contest_id": "1", "entries": 1}, {"name": "flea", "contest_id": "2", "entries": 4}]))
    return run, contests, fr, rosters, banks, idx, book


def run_runner(run, contests, out, label="rehearsal", clone=CLONE, expect_sha=None):
    cmd = [PY, str(ROOT / "scripts" / "week3_shadow_runner.py"), "--run", str(run), "--contests", str(contests), "--clone", clone, "--out", str(out), "--label", label, "--chunk", "7"]
    if expect_sha is not None: cmd += ["--expect-sha", expect_sha]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_runner_parity_and_arms(tmp_path):
    run, contests, fr, rosters, banks, idx, book = make_run(tmp_path)
    r = run_runner(run, contests, tmp_path / "shadow"); assert r.returncode == 0, r.stdout + r.stderr
    m = json.loads((tmp_path / "shadow" / "manifest.json").read_text()); b = json.loads((tmp_path / "shadow" / "books.json").read_text())
    assert m["parity"] == {"membership": True, "order": True, "book_json_names": True} and m["K"] == 5 and m["current_outcomes_read"] is False
    clone_sha = subprocess.check_output(["git", "-C", CLONE, "rev-parse", "HEAD"], text=True).strip()
    assert m["lab_clone_commit"] == clone_sha and m["lab_clone_clean"] is True and m["lab_clone_expected_sha"] is None
    assert b["arms"]["control"]["order"] == [int(i) for i in book]
    pos = dict(zip(fr.id, fr.pos)); team = dict(zip(fr.id, fr.team)); proj = dict(zip(fr.id, fr.proj))
    n_floor = sum(1 for r_ in rosters if min(proj[fr.id[i]] for i in r_ if pos[fr.id[i]] != "DST") >= 8)
    def depth(r_):
        qb = next(fr.id[i] for i in r_ if pos[fr.id[i]] == "QB"); return sum(1 for i in r_ if pos[fr.id[i]] in ("WR", "TE") and team[fr.id[i]] == team[qb])
    n_depth = sum(1 for r_ in rosters if depth(r_) <= 3)
    n_floor10 = sum(1 for r_ in rosters if min(proj[fr.id[i]] for i in r_ if pos[fr.id[i]] != "DST") >= 10); n_depth2 = sum(1 for r_ in rosters if depth(r_) <= 2)
    assert b["arms"]["floor8"]["pool"] == n_floor and b["arms"]["nodepth4"]["pool"] == n_depth
    assert b["arms"]["floor10"]["pool"] == n_floor10 and b["arms"]["depth2"]["pool"] == n_depth2
    for k in ("ladder016", "floor8", "floor10", "nodepth4", "depth2"):
        arm = b["arms"][k]
        if arm["feasible"]: assert len(arm["order"]) == 5 and len(set(arm["order"])) == 5 and all(len(x) == 9 for x in arm["candidate_ids"])
        else: assert arm["pool"] < 5
    assert (tmp_path / "shadow" / "REHEARSAL").exists()


def test_runner_enforces_clone_identity(tmp_path):
    run, contests, *_ = make_run(tmp_path)
    clone_sha = subprocess.check_output(["git", "-C", CLONE, "rev-parse", "HEAD"], text=True).strip()
    ok = run_runner(run, contests, tmp_path / "shadow-ok", expect_sha=clone_sha)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    wrong = run_runner(run, contests, tmp_path / "shadow-wrong", expect_sha="0" * 40)
    assert wrong.returncode == 2 and "LAB CLONE IDENTITY FAILED" in wrong.stderr

    dirty = tmp_path / "dirty-clone"
    subprocess.run(["git", "init", "-q", str(dirty)], check=True)
    (dirty / "tracked").write_text("clean commit\n")
    subprocess.run(["git", "-C", str(dirty), "add", "tracked"], check=True)
    subprocess.run(["git", "-C", str(dirty), "-c", "user.name=shadow-test", "-c", "user.email=shadow-test@example.invalid", "commit", "-qm", "init"], check=True)
    (dirty / "untracked").write_text("must fail closed\n")
    dirty_run = run_runner(run, contests, tmp_path / "shadow-dirty", clone=str(dirty))
    assert dirty_run.returncode == 2 and "clone is dirty" in dirty_run.stderr


def test_runner_fails_closed_on_parity(tmp_path):
    run, contests, *_ = make_run(tmp_path)
    c = pd.read_parquet(run / "candidates.parquet"); ranked = c.index[c.book_rank > 0].tolist()
    c.loc[ranked[0], "book_rank"], c.loc[ranked[1], "book_rank"] = c.loc[ranked[1], "book_rank"], c.loc[ranked[0], "book_rank"]   # swap two delivered ranks
    c.to_parquet(run / "candidates.parquet")
    r = run_runner(run, contests, tmp_path / "shadow"); assert r.returncode == 3 and (tmp_path / "shadow" / "PARITY-FAILED").exists()


def test_reader_arithmetic_and_fail_closed(tmp_path):
    run, contests, fr, rosters, banks, idx, book = make_run(tmp_path)
    assert run_runner(run, contests, tmp_path / "shadow").returncode == 0
    oc = tmp_path / "outcomes.csv"
    with open(oc, "w", newline="") as h:
        w = csv.writer(h); w.writerow(["id", "actual_points"]); [w.writerow([pid, float(i)]) for i, pid in enumerate(fr.id)]
    r = subprocess.run([PY, str(ROOT / "scripts" / "week3_shadow_reader.py"), "--shadow", str(tmp_path / "shadow"), "--run", str(run), "--clone", CLONE, "--out", str(tmp_path / "read"), "--outcomes", str(oc)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    rep = json.loads((tmp_path / "read" / "realized.json").read_text()); ctrl = rep["arms"]["control"]
    exp = [float(sum(i for i in rosters[b])) for b in book]                       # actual = frame row index
    assert ctrl["realized_rows"] == exp and ctrl["realized_max"] == max(exp) and rep["pool_oracle"] == max(float(sum(r_)) for r_ in rosters)
    assert ctrl["regret"] == rep["pool_oracle"] - max(exp) and ctrl["prefix_blocks"]["milly"]["rows"] == [1, 1]
    assert ctrl["prefixes"]["20"]["rows"] == 5 and ctrl["prefixes"]["20"]["realized_max"] == max(exp) and ctrl["rank_of_realized_best"] == exp.index(max(exp)) + 1
    assert ctrl["prefixes"]["20"]["any_220"] == (max(exp) >= 220) and "40" in ctrl["prefixes"] and "80" in ctrl["prefixes"]
    bad = tmp_path / "bad.csv"; bad.write_text("id,actual_points\np00,1.0\n")
    r2 = subprocess.run([PY, str(ROOT / "scripts" / "week3_shadow_reader.py"), "--shadow", str(tmp_path / "shadow"), "--run", str(run), "--clone", CLONE, "--out", str(tmp_path / "read2"), "--outcomes", str(bad)], capture_output=True, text=True)
    assert r2.returncode == 3 and (tmp_path / "read2" / "READER-FAILED").exists()
    r3 = subprocess.run([PY, str(ROOT / "scripts" / "week3_shadow_reader.py"), "--shadow", str(tmp_path / "shadow"), "--run", str(run), "--clone", CLONE, "--out", str(tmp_path / "read3"), "--synthetic-world", "3"], capture_output=True, text=True)
    assert r3.returncode == 0 and (tmp_path / "read3" / "REHEARSAL").exists()

    duplicate = tmp_path / "duplicate.csv"
    with open(duplicate, "w", newline="") as h:
        w = csv.writer(h); w.writerow(["id", "actual_points"]); [w.writerow([pid, float(i)]) for i, pid in enumerate(fr.id)]; w.writerow([str(fr.id.iloc[0]), 0.0])
    r4 = subprocess.run([PY, str(ROOT / "scripts" / "week3_shadow_reader.py"), "--shadow", str(tmp_path / "shadow"), "--run", str(run), "--clone", CLONE, "--out", str(tmp_path / "read4"), "--outcomes", str(duplicate)], capture_output=True, text=True)
    assert r4.returncode == 3 and (tmp_path / "read4" / "READER-FAILED").exists()

    # The runner manifest binds the complete run.  A changed artifact must
    # invalidate the reader even when the changed file remains parseable.
    (run / "receipt.json").write_text((run / "receipt.json").read_text() + "\n")
    r5 = subprocess.run([PY, str(ROOT / "scripts" / "week3_shadow_reader.py"), "--shadow", str(tmp_path / "shadow"), "--run", str(run), "--clone", CLONE, "--out", str(tmp_path / "read5"), "--synthetic-world", "3"], capture_output=True, text=True)
    assert r5.returncode == 3 and "hash mismatch" in r5.stderr and (tmp_path / "read5" / "READER-FAILED").exists()
