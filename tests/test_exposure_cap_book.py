"""The cap tool must reproduce the delivered selection before it is trusted to change it,
and must fail closed rather than emit a book that quietly ignores a cap.

Week 2 is the motivating case: a player listed Doubtful at build time held 48 of 97 rows
including the Millionaire seat and scored 0.0.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import exposure_cap_book as ecb  # noqa: E402

N_PLAYERS, N_WORLDS = 60, 64


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    """A synthetic run directory in the shape live_week.py --emit-a5-sidecars writes."""
    rng = np.random.default_rng(7)
    d = tmp_path / "run"
    d.mkdir()
    pos = (["QB"] * 8 + ["RB"] * 16 + ["WR"] * 22 + ["TE"] * 8 + ["DST"] * 6)
    frame = pd.DataFrame({
        "id": [f"p{i:02d}" for i in range(N_PLAYERS)],
        "display_name": [f"Player {i:02d}" for i in range(N_PLAYERS)],
        "position": pos,
        "salary": rng.integers(3000, 9000, N_PLAYERS),
        "report_status": [None] * N_PLAYERS,
    })
    # Player 05 is Doubtful; player 06 Questionable. Both are made attractive so a greedy
    # that ignores status would take them often.
    frame.loc[5, "report_status"] = "Doubtful"
    frame.loc[6, "report_status"] = "Questionable"

    inc = rng.gamma(3.0, 4.0, (N_PLAYERS, N_WORLDS)).astype(np.float32)
    hsm = rng.gamma(3.0, 4.0, (N_PLAYERS, N_WORLDS)).astype(np.float32)
    inc[5] *= 3.0; hsm[5] *= 3.0
    inc[6] *= 3.0; hsm[6] *= 3.0

    # Player 10 is a chalk magnet: strong, and present in most of the pool. Without a cap
    # the greedy concentrates on him, which is what gives the cap something to bite on.
    inc[10] *= 4.0; hsm[10] *= 4.0
    rosters = []
    for j in range(400):
        pick = rng.choice(N_PLAYERS, size=9, replace=False)
        if j % 4 and 10 not in pick:
            pick[0] = 10
        rosters.append(pick)
    cands = pd.DataFrame({
        "cand": range(len(rosters)),
        "players": [",".join(frame.id.iloc[r]) for r in rosters],
        "names": [",".join(frame.display_name.iloc[r]) for r in rosters],
        "tag": "boom",
        "salary": [int(frame.salary.iloc[r].sum()) for r in rosters],
    })
    t_inc = np.stack([inc[r].sum(axis=0) for r in rosters])
    cands["sel_mean"] = t_inc.mean(axis=1).astype(np.float32)

    frame.to_parquet(d / "frame.parquet")
    cands.to_parquet(d / "candidates.parquet")
    np.save(d / "incumbent_player_scores.npy", inc)
    np.save(d / "corrected_hsim_player_scores.npy", hsm)
    (d / "receipt.json").write_text(json.dumps({
        "identity": {"sha": "0" * 40},
        "a5_sidecars": {
            "incumbent_player_scores": {"sha256": _sha(d / "incumbent_player_scores.npy")},
            "corrected_hsim_player_scores": {"sha256": _sha(d / "corrected_hsim_player_scores.npy")},
        }}))
    return d


CONTESTS = [{"name": "major", "contest_id": "1", "entries": 10, "keep": 10, "fee": 20},
            {"name": "sat_a", "contest_id": "2", "entries": 6, "keep": 6, "fee": 5},
            {"name": "single", "contest_id": "3", "entries": 1, "keep": 1, "fee": 3}]


def _contests(tmp_path: Path, contests=CONTESTS) -> Path:
    p = tmp_path / "contests.json"
    p.write_text(json.dumps(contests))
    return p


def _run(run_dir, tmp_path, *args, entries=17):
    out = tmp_path / f"out{len(list(tmp_path.glob('out*')))}"
    ecb.main([str(run_dir), "--contests", str(_contests(tmp_path)), "--entries", str(entries),
              "--output-dir", str(out), *args])
    return out, json.loads((out / "receipt.json").read_text())


def _rows(out: Path, run_dir: Path, player: str) -> int:
    book = pd.read_csv(out / "capped_book.csv")
    names = pd.read_parquet(run_dir / "frame.parquet").set_index("id").display_name
    return sum(player in [names[i] for i in spec.split(",")] for spec in book.players)


# --------------------------------------------------------------- the gate first


def test_without_caps_the_tool_reproduces_the_plain_expected_max_selection(run_dir):
    run = ecb.load_run(run_dir)
    k = 17
    loose = np.full(len(run.frame), k, dtype=np.int32)
    book, _ = ecb.select_capped(run, k, player_caps=loose)
    # reference: the same greedy written plainly, no heap, no laziness
    t = np.concatenate([run.t_inc, run.t_hs], axis=1).astype(np.float64)
    cur = np.full(t.shape[1], -np.inf)
    ref, taken = [], np.zeros(t.shape[0], dtype=bool)
    for _ in range(k):
        base = 0.0 if not ref else cur.mean()
        g = np.maximum(t, cur).mean(axis=1) - base
        g[taken] = -np.inf
        i = int(np.argmax(g))
        taken[i] = True; ref.append(i); cur = np.maximum(cur, t[i])
    assert book == ref


# ------------------------------------------------------------------- the rules


def test_a_doubtful_player_takes_no_rows_and_the_sheet_says_so(run_dir, tmp_path):
    out, receipt = _run(run_dir, tmp_path)
    assert _rows(out, run_dir, "Player 05") == 0
    assert receipt["cap_reasons"]["Player 05"] == "Doubtful -> 0 rows"
    assert "Doubtful" in (out / "exposure_sheet.md").read_text()


def test_the_doubtful_player_is_otherwise_attractive_enough_to_be_selected(run_dir, tmp_path):
    """Without this the previous test would pass against a pool that never wanted him."""
    out, _ = _run(run_dir, tmp_path, "--doubtful-max-share", "1.0")
    assert _rows(out, run_dir, "Player 05") > 0


def test_no_player_exceeds_the_per_contest_cap_inside_any_contest(run_dir, tmp_path):
    out, _ = _run(run_dir, tmp_path, "--contest-max-share", "0.5")
    book = pd.read_csv(out / "capped_book.csv")
    start = 0
    for c in CONTESTS:
        n = int(c["entries"])
        cap = max(1, int(0.5 * n))
        held: dict[str, int] = {}
        for spec in book.players[start:start + n]:
            for pid in spec.split(","):
                held[pid] = held.get(pid, 0) + 1
        assert max(held.values()) <= cap, f"{c['name']} breaches its cap of {cap}"
        start += n


def test_the_per_contest_cap_actually_binds(run_dir, tmp_path):
    """A cap nothing reaches proves nothing: the loose run must breach the tight cap."""
    loose, _ = _run(run_dir, tmp_path, "--contest-max-share", "1.0",
                    "--player-max-share", "1.0", "--dst-max-share", "1.0",
                    "--questionable-max-share", "1.0", "--doubtful-max-share", "1.0")
    book = pd.read_csv(loose / "capped_book.csv")
    held: dict[str, int] = {}
    for spec in book.players[:10]:
        for pid in spec.split(","):
            held[pid] = held.get(pid, 0) + 1
    assert max(held.values()) > max(1, int(0.5 * 10))


def test_a_contest_too_small_to_constrain_is_named_not_silently_ignored(run_dir, tmp_path):
    _, receipt = _run(run_dir, tmp_path, "--contest-max-share", "0.5")
    # names are deduplicated with a count ("single x1"), because the receipt is committed
    # and contests.json is the stake plan: aggregates only, never a per-contest breakdown.
    unconstrained = receipt["contests_unconstrained_by_contest_cap"]
    assert any(u.startswith("single x") for u in unconstrained), unconstrained
    assert len(unconstrained) == len(set(unconstrained))


# ------------------------------------------------------------- failing closed


def test_missing_world_banks_are_an_error_not_a_different_objective(run_dir, tmp_path):
    (run_dir / "incumbent_player_scores.npy").unlink()
    with pytest.raises(ecb.CapError, match="emit-a5-sidecars"):
        _run(run_dir, tmp_path)


def test_a_world_bank_that_does_not_match_the_receipt_is_refused(run_dir, tmp_path):
    bank = np.load(run_dir / "corrected_hsim_player_scores.npy")
    bank[0, 0] += np.float32(1.0)
    np.save(run_dir / "corrected_hsim_player_scores.npy", bank)
    with pytest.raises(ecb.CapError, match="sha256"):
        _run(run_dir, tmp_path)


def test_a_roster_to_player_mapping_drift_is_caught_before_anything_is_selected(run_dir):
    cands = pd.read_parquet(run_dir / "candidates.parquet")
    cands["sel_mean"] = cands.sel_mean + 5.0
    cands.to_parquet(run_dir / "candidates.parquet")
    with pytest.raises(ecb.CapError, match="roster-to-player mapping"):
        ecb.load_run(run_dir)


def test_caps_that_cannot_fill_the_book_fail_rather_than_emit_a_short_one(run_dir, tmp_path):
    with pytest.raises(ecb.CapError, match="only"):
        _run(run_dir, tmp_path, "--player-max-share", "0.06", "--dst-max-share", "0.06")


def test_a_per_contest_cap_the_greedy_cannot_satisfy_names_the_position_it_stuck_on(run_dir, tmp_path):
    """Selection fills positions in order, so a tight per-contest cap can dead-end even
    when some assignment exists. That must be a loud refusal, never a breaching book."""
    with pytest.raises(ecb.CapError, match="book position"):
        _run(run_dir, tmp_path, "--contest-max-share", "0.12")


def test_an_unknown_layout_is_refused(run_dir, tmp_path):
    with pytest.raises(SystemExit):
        _run(run_dir, tmp_path, "--layout", "sideways")


def test_top_layout_puts_the_first_rank_in_every_contest(run_dir):
    positions = ecb.contest_of_position(CONTESTS, 17, "top")
    assert positions[0] == [0, 1, 2]
    assert positions[5] == [0, 1]          # sat_a's last row, still inside major's 10
    assert positions[6] == [0]             # past sat_a, still inside major
    seq = ecb.contest_of_position(CONTESTS, 17, "sequential")
    assert seq[0] == [0] and seq[10] == [1] and seq[16] == [2]


# ---- refinement 2 (operator 2026-09-24): tighter caps for Questionable QBs and missed-last-practice Questionables


def _status_frame():
    return pd.DataFrame({
        "display_name": ["qbQ", "qbH", "wrQdnp", "wrQlim", "rbH", "dst"],
        "position": ["QB", "QB", "WR", "WR", "RB", "DST"],
        "report_status": ["Questionable", None, "Questionable", "Questionable", None, None],
        "practice_level": [1.0, 2.0, 0.0, 1.0, 2.0, None],
    })


def test_refinement2_caps_are_off_by_default():
    caps, _ = ecb.build_player_caps(_status_frame(), 100, player_share=0.3, dst_share=0.2, doubtful_share=0.0,
                                    questionable_share=0.10)
    assert list(caps) == [10, 30, 10, 10, 30, 20]


def test_refinement2_caps_bind_only_their_groups():
    caps, why = ecb.build_player_caps(_status_frame(), 100, player_share=0.3, dst_share=0.2, doubtful_share=0.0,
                                      questionable_share=0.10, questionable_qb_share=0.05, questionable_dnp_share=0.03)
    assert list(caps) == [5, 30, 3, 10, 30, 20]
    assert why["qbQ"].startswith("Questionable QB") and why["wrQdnp"].startswith("Questionable, missed last practice")
    assert why["wrQlim"].startswith("Questionable ->")


def test_refinement2_missed_practice_cap_needs_practice_level():
    fr = _status_frame().drop(columns=["practice_level"])
    with pytest.raises(ecb.CapError, match="practice_level"):
        ecb.build_player_caps(fr, 100, player_share=0.3, dst_share=0.2, doubtful_share=0.0, questionable_share=0.10,
                              questionable_dnp_share=0.05)
