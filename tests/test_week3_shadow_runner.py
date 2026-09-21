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


def make_run_rich(tmp, n_cands=80, sims=40, seed=11, K=10):
    """A 12-team / 6-game slate with market_points, game_id and game_start columns, K=10, for the exposure / market / row-shape arms."""
    rng = np.random.default_rng(seed)
    pos = ["QB"] * 5 + ["RB"] * 10 + ["WR"] * 16 + ["TE"] * 8 + ["DST"] * 5
    n = len(pos); teams = [f"T{i % 12}" for i in range(n)]
    ids = [f"p{i:02d}" if pos[i] != "DST" else f"{teams[i]}_DST" for i in range(n)]
    game_of_team = {f"T{t}": f"G{t // 2}" for t in range(12)}; start_of_game = {f"G{g}": ("2026-09-27T17:00:00Z" if g < 4 else "2026-09-27T20:25:00Z") for g in range(6)}
    proj = rng.uniform(4, 20, n).round(2); market = proj.copy(); flagged = rng.choice([i for i in range(n) if pos[i] != "DST"], 6, replace=False)
    market[flagged] = (proj[flagged] * 0.7).round(2)          # served > 1.15 x market for these six
    market[rng.choice(n, 4, replace=False)] = np.nan            # a few rows without a market value
    fr = pd.DataFrame({"id": ids, "name": [f"N{i}" for i in range(n)], "pos": pos, "team": teams, "salary": 4000, "proj": proj, "market_points": market,
                       "game_id": [game_of_team[t] for t in teams], "game_start": [start_of_game[game_of_team[t]] for t in teams]})
    fr.loc[fr.pos == "DST", "proj"] = 8.0
    qbs, dsts = [i for i in range(n) if pos[i] == "QB"], [i for i in range(n) if pos[i] == "DST"]
    rbs, wrs, tes = [i for i in range(n) if pos[i] == "RB"], [i for i in range(n) if pos[i] == "WR"], [i for i in range(n) if pos[i] == "TE"]
    rosters = set()
    while len(rosters) < n_cands:
        flex = int(rng.choice(rbs + wrs + tes)); core = [int(rng.choice(qbs)), int(rng.choice(dsts)), *rng.choice(rbs, 2, replace=False), *rng.choice(wrs, 3, replace=False), int(rng.choice(tes))]
        if flex in core: continue
        rosters.add(tuple(sorted(core + [flex])))
    rosters = sorted(rosters); idx = np.array(rosters)
    banks = [rng.normal(10, 6, (n, sims)).astype(np.float32) for _ in range(2)]
    sys.path.insert(0, str(pathlib.Path(CLONE) / "src")); from nfl2.selectors import select_expected_max
    Td = totals_law(banks, idx); book = select_expected_max(Td, K)
    rank = np.zeros(n_cands); rank[book] = np.arange(1, K + 1)
    cands = pd.DataFrame({"cand": range(n_cands), "players": [",".join(ids[i] for i in r) for r in rosters], "names": ["|".join(fr.name[i] for i in r) for r in rosters], "book_rank": rank})
    run = tmp / "run"; run.mkdir(); fr.to_parquet(run / "frame.parquet"); cands.to_parquet(run / "candidates.parquet")
    np.save(run / "incumbent_player_scores.npy", banks[0]); np.save(run / "corrected_hsim_player_scores.npy", banks[1])
    (run / "receipt.json").write_text(json.dumps({"identity": {"test": True}, "config": {"selector": "dual_emax", "operational_k": K, "sims": sims, "seed": 1, "hsim_seed": 2, "hsim_worlds": sims}}))
    (run / "book.json").write_text(json.dumps({"entries": [{"rank": r + 1, "players": [fr.name[i] for i in rosters[b]]} for r, b in enumerate(book)]}))
    contests = tmp / "contests.json"; contests.write_text(json.dumps([{"name": "milly", "contest_id": "1", "entries": 1}, {"name": "flea", "contest_id": "2", "entries": K - 1}]))
    return run, contests, fr, rosters, banks, idx, book, Td, select_expected_max


def test_exposure_market_and_rowshape_arms(tmp_path):
    run, contests, fr, rosters, banks, idx, book, Td, select_expected_max = make_run_rich(tmp_path); K = len(book)
    r = run_runner(run, contests, tmp_path / "shadow"); assert r.returncode == 0, r.stdout + r.stderr
    m = json.loads((tmp_path / "shadow" / "manifest.json").read_text()); b = json.loads((tmp_path / "shadow" / "books.json").read_text())["arms"]
    assert m["schema"] == "week3-shadow-runner/v2" and m["parity"] == {"membership": True, "order": True, "book_json_names": True}
    for name in ("cap30", "cap20", "marketpull", "cap20pull", "games5", "late3"): assert name in b and name in m["arms"]
    # exposure caps: K unique rows and no player above floor(cap x K) rows when feasible; never relaxed when not
    for name, cap in (("cap30", 0.30), ("cap20", 0.20), ("cap20pull", 0.20)):
        arm = b[name]; limit = int(np.floor(cap * K + 1e-9)); assert arm["max_rows_per_player"] == limit and arm["iterations"] >= 1 and "refill_law" in arm
        if arm["feasible"]:
            assert len(arm["order"]) == K and len(set(arm["order"])) == K
            counts = {}
            for row in arm["candidate_ids"]:
                for p in row: counts[p] = counts.get(p, 0) + 1
            assert max(counts.values()) <= limit and arm["max_exposure_rows"] == max(counts.values())
        else:
            assert arm["order"] == [] and "not relaxed" in arm["note"]
    assert b["cap30"]["feasible"], b["cap30"]
    # market pull: the recorded shifts follow the law and the order is the control selector on the shifted totals
    pj = fr.proj.to_numpy(float); mk = fr.market_points.to_numpy(float); flag = np.isfinite(mk) & (pj > 1.15 * mk) & (fr.pos != "DST").to_numpy()
    delta = np.where(flag, (mk + 0.25 * (pj - mk)) - pj, 0.0); arm = b["marketpull"]
    assert arm["feasible"] and arm["n_shifted_players"] == int(flag.sum()) == 6
    for s in arm["shifted_players"]: k = list(fr.id).index(s["id"]); assert flag[k] and abs(s["delta"] - delta[k]) < 1e-9 and s["delta"] < 0
    shift_rows = np.array([sum(delta[i] for i in r_) for r_ in rosters], dtype=np.float32)
    expected = [int(i) for i in select_expected_max(Td + shift_rows[:, None], K)]
    assert arm["order"] == expected and arm["order"] != b["control"]["order"] or arm["order"] == expected
    # row-shape filters: pool sizes match brute force
    pos = dict(zip(fr.id, fr.pos)); game = dict(zip(fr.id, fr.game_id)); late = dict(zip(fr.id, fr.game_start == "2026-09-27T20:25:00Z"))
    n_games5 = sum(1 for r_ in rosters if len({game[fr.id[i]] for i in r_ if pos[fr.id[i]] != "DST"}) >= 5)
    n_late3 = sum(1 for r_ in rosters if sum(1 for i in r_ if late[fr.id[i]]) >= 3)
    assert b["games5"]["pool"] == n_games5 and b["late3"]["pool"] == n_late3 and b["late3"]["first_kickoff_utc"].startswith("2026-09-27 17:00")
    for name in ("games5", "late3"):
        if b[name]["feasible"]: assert len(b[name]["order"]) == K and all(len(x) == 9 for x in b[name]["candidate_ids"])
        else: assert b[name]["pool"] < K


def test_optional_arms_are_infeasible_without_frame_columns(tmp_path):
    run, contests, *_ = make_run(tmp_path)
    r = run_runner(run, contests, tmp_path / "shadow"); assert r.returncode == 0, r.stdout + r.stderr
    b = json.loads((tmp_path / "shadow" / "books.json").read_text())["arms"]
    for name in ("marketpull", "cap20pull", "games5", "late3"):
        assert b[name]["feasible"] is False and "not approximated" in b[name]["note"] and b[name]["order"] == []
    assert b["cap30"]["max_rows_per_player"] == 1 and b["cap20"]["max_rows_per_player"] == 1
