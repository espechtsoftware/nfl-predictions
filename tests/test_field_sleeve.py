"""field_sleeve (the winner-shaped tail sleeve, operator 2026-10-02): the house-rule filter, the ownership targets
(position totals, DST rule, exclusions, coverage), the salary tilt, the chunked sampler, the pick orders, and the build
host's flags. Synthetic frames; the real sampler on Week-4 data is the integration test (HANDOFF)."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import field_sleeve as fs  # noqa: E402


def _frame():
    """Two games (A@B, C@D); per team QB, 2 RB, 3 WR, TE, DST."""
    rows, k = [], 0
    for team, opp, game in (("A", "B", "g1"), ("B", "A", "g1"), ("C", "D", "g2"), ("D", "C", "g2")):
        for pos, n in (("QB", 1), ("RB", 2), ("WR", 3), ("TE", 1), ("DST", 1)):
            for j in range(n):
                pid = f"{team}_DST" if pos == "DST" else f"{team}{pos}{j}"
                rows.append({"id": pid, "dk_player_id": 1000 + k, "name": pid, "pos": pos, "team": team, "opp": opp, "game_id": game,
                             "salary": {"QB": 7000, "RB": 6000, "WR": 5500, "TE": 4000, "DST": 3000}[pos] - 300 * j,
                             "mean_projection": {"QB": 20, "RB": 14, "WR": 13, "TE": 8, "DST": 7}[pos] - j})
                k += 1
    return pd.DataFrame(rows)


def _idx(fr, ids):
    pos = {i: n for n, i in enumerate(fr.id)}
    return np.array([[pos[i] for i in r] for r in ids])


BASE = ["AQB0", "ARB0", "CRB0", "AWR0", "AWR1", "BWR0", "CTE0", "DWR0", "C_DST"]      # g1: QB, RB, 2 WR + B WR = 5


def test_legal_each_house_rule():
    fr = _frame()
    def ok(r, max_game=9, floor=0):
        return bool(fs.legal(_idx(fr, [r]), fr, max_game, floor)[0])
    assert ok(BASE) and ok(BASE, max_game=5)                              # QB + 2 A catchers, B bring-back, 5 from g1
    assert not ok(BASE, max_game=4)                                       # the main book's cap of 4 refuses it
    assert not ok(["AQB0", "ARB0", "CRB0", "AWR0", "CWR0", "BWR0", "CTE0", "DWR0", "C_DST"])     # QB + 1 catcher
    assert not ok(["AQB0", "ARB0", "CRB0", "AWR0", "AWR1", "CWR0", "CTE0", "DWR0", "C_DST"])     # no bring-back
    assert ok(["AQB0", "ARB0", "CRB0", "AWR0", "AWR1", "BWR0", "CTE0", "DWR0", "A_DST"])         # A DST, no B RB: fine
    assert not ok(["AQB0", "ARB0", "BRB0", "AWR0", "AWR1", "BWR0", "CTE0", "DWR0", "A_DST"])     # B RB faces the A DST
    assert not ok(["AQB0", "ARB0", "ARB1", "AWR0", "AWR1", "BWR0", "CTE0", "DWR0", "C_DST"])     # two A RBs
    assert not ok(BASE, floor=60_000)                                     # under the salary floor


def test_ownership_targets_scale_positions_set_dst_and_exclude(tmp_path):
    fr = _frame()
    sk = fr[fr.pos != "DST"]
    pd.DataFrame({"dk_player_id": sk.dk_player_id, "pred_own": np.linspace(30, 2, len(sk))}).to_csv(tmp_path / "own.csv", index=False)
    t, meta = fs.ownership_targets(tmp_path / "own.csv", fr, exclude={"DWR2"})
    pos = dict(zip(fr.id, fr.pos))
    assert "DWR2" not in t
    for p, total in fs.SLOT_TOTALS.items():
        assert sum(v for i, v in t.items() if pos[i] == p) == pytest.approx(total, rel=0.02)   # the tilt restores each total
    assert sum(v for i, v in t.items() if pos[i] == "DST") == pytest.approx(1.0)
    assert meta["salary_tilt"]["after"] <= fs.SALARY_TARGET + 1
    with pytest.raises(ValueError, match="covers"):
        pd.DataFrame({"dk_player_id": sk.dk_player_id[:3], "pred_own": [10, 5, 2]}).to_csv(tmp_path / "few.csv", index=False)
        fs.ownership_targets(tmp_path / "few.csv", fr, exclude=set())
    with pytest.raises(ValueError, match="percentages"):
        pd.DataFrame({"dk_player_id": sk.dk_player_id, "pred_own": 0.1}).to_csv(tmp_path / "frac.csv", index=False)
        fs.ownership_targets(tmp_path / "frac.csv", fr, exclude=set())


def test_salary_tilt_reaches_the_target_keeps_position_totals_and_leaves_cheap_targets_alone():
    sal = {"q1": 8000, "q2": 5000, "r1": 9000, "r2": 4000, "r3": 6000, "r4": 5000, "w1": 9000, "w2": 8000, "w3": 7000, "w4": 4000,
           "w5": 3500, "t1": 7000, "t2": 3000, "d": 3000}
    pos = {i: {"q": "QB", "r": "RB", "w": "WR", "t": "TE", "d": "DST"}[i[0]] for i in sal}
    t = {"q1": 0.8, "q2": 0.2, "r1": 0.8, "r2": 0.4, "r3": 0.6, "r4": 0.6, "w1": 0.9, "w2": 0.8, "w3": 0.8, "w4": 0.5, "w5": 0.45,
         "t1": 0.8, "t2": 0.35, "d": 0.9}
    before0 = fs.mean_lineup_salary(t, pos, sal)
    u, beta, before, after = fs.salary_tilt(t, pos, sal, target=before0 - 1000)     # a Week-4-sized shift (beta 0.03-0.22)
    assert before == before0 and after == pytest.approx(before0 - 1000, abs=5) and beta > 0
    for p in ("QB", "RB", "WR", "TE"):
        assert sum(u[i] for i in u if pos[i] == p) == pytest.approx(sum(t[i] for i in t if pos[i] == p))
    assert u["r1"] < t["r1"] and u["r2"] > t["r2"]
    u2, beta2, _, _ = fs.salary_tilt(dict(t), pos, {i: 1000 for i in sal}, target=49_500)
    assert beta2 == 0.0 and u2 == t


def test_sample_chunks_retries_a_short_chunk_and_fills_n():
    calls = []
    def sampler(fr, targets, m, seed):
        calls.append((m, seed))
        if len(calls) == 2:
            raise RuntimeError("could not fill")
        return np.full((m, 9), seed % 7, dtype=np.int32), {"stack_rate": 0.7}
    S, rec = fs.sample_chunks(None, {}, 120_000, 5, sampler=sampler)
    assert len(S) == 120_000 and rec["retried"] == 1
    assert calls[1] == (50_000, 6) and calls[2] == (10_000, 10_006)


def test_field_candidates_orders_top_by_projection_and_drops_rule_breakers():
    fr = _frame()
    opts = [BASE, ["AQB0", "ARB0", "CRB1", "AWR0", "AWR1", "BWR0", "CTE0", "DWR1", "C_DST"],
            ["AQB0", "ARB1", "CRB0", "AWR1", "AWR2", "BWR1", "CTE0", "CWR0", "C_DST"],
            ["AQB0", "ARB0", "CRB0", "AWR0", "CWR0", "BWR0", "CTE0", "DWR0", "C_DST"]]               # the last breaks the stack
    L = _idx(fr, opts)
    sampler = lambda fr_, targets, m, seed: (np.vstack([L] * (m // 4 + 1))[:m], {})
    rost, ps, rec = fs.field_candidates(fr, {}, 400, 1, 5, 0, "top", sampler=sampler, min_legal=1)
    assert rec["legal"] == 3 and len(rost) == 3 and list(ps) == sorted(ps, reverse=True)
    assert sorted(opts[3]) not in [sorted(r) for r in rost]
    rb, _, rec_b = fs.field_candidates(fr, {}, 400, 1, 5, 0, "band", sampler=sampler, min_legal=1)
    assert rec_b["mode"] == "band" and len(rb) <= 3
    rf, psf, rec_f = fs.field_candidates(fr, {}, 400, 1, 5, 0, "free", sampler=sampler)          # no filter, no minimum
    assert len(rf) == 4 and rec_f["legal"] == 3 and rec_f["house_rules_applied"] is False and list(psf) == sorted(psf, reverse=True)
    assert sorted(opts[3]) in [sorted(r) for r in rf]                                               # the stack-breaker stays
    six = ["AQB0", "ARB0", "ARB1", "AWR0", "AWR1", "BWR0", "ATE0", "DWR0", "C_DST"]                 # 6 from g1
    L6 = np.vstack([L, _idx(fr, [six])])
    rf6, _, _ = fs.field_candidates(fr, {}, 500, 1, 5, 0, "free", sampler=lambda *a_: (np.vstack([L6] * 100)[: a_[2]], {}))
    assert sorted(six) not in [sorted(r) for r in rf6] and len(rf6) == 4                             # free keeps the per-game limit
    with pytest.raises(ValueError, match="satisfy the house rules"):
        fs.field_candidates(fr, {}, 400, 1, 5, 0, "top", sampler=sampler)          # 3 legal < the default 50
    with pytest.raises(ValueError, match="mode"):
        fs.field_candidates(fr, {}, 400, 1, 5, 0, "best", sampler=sampler)


def test_build_host_passes_the_sleeve_flags_and_falls_back_to_the_lag_file():
    host = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_build_host.sh").read_text()
    a = host.index('  if [[ "${UNION_SLEEVE_SOURCE:-mean}" == "field" ]]; then'); b = host.index("\n  fi\n", a) + 5
    block = host[a:b]
    def run(env):
        script = env + "\nUNION_ARGS=(); RUN_TAG=t\n" + block + '\nprintf "%s\\n" "${UNION_ARGS[@]}"'
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True).stdout.split("\n")
    out = run('UNION_SLEEVE_SOURCE=field; UNION_SLEEVE_FIELD_MODE=band; OWN_SRC=/x/tabpfn.csv; OWNERSHIP_LAG=/x/lag.csv')
    assert ["--sleeve-source", "field", "--sleeve-field-mode", "band", "--sleeve-max-per-game", "5", "--sleeve-own-source", "/x/tabpfn.csv"] == [x for x in out if x and not x.startswith("TAIL")]
    out = run('UNION_SLEEVE_SOURCE=field; OWN_SRC=; OWNERSHIP_LAG=/x/lag.csv')
    assert "/x/lag.csv" in out and "top" in out
    assert [x for x in run('UNION_SLEEVE_SOURCE=mean; OWNERSHIP_LAG=/x/lag.csv') if x] == []
