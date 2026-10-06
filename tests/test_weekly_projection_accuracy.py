"""The weekly ours / FP / blend accuracy reader (scripts/weekly_projection_accuracy.py), frozen 2026-10-06 before any
Week-5 outcome: the population rules, the game-cluster bootstrap, the revisit check. Offline: synthetic frames."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("weekly_projection_accuracy", ROOT / "scripts" / "weekly_projection_accuracy.py")
WPA = importlib.util.module_from_spec(spec); spec.loader.exec_module(WPA)


def _nm(k: int) -> str:
    """A letter-only name (the name key drops digits)."""
    return f"Player {chr(97 + k // 26)}{chr(97 + k % 26)}"


def _frame(n=24, week=5, games=6):
    rows = []
    for k in range(n):
        rows.append({"id": f"p{k}", "display_name": _nm(k), "pos": ["QB", "RB", "WR", "TE"][k % 4], "game_id": f"g{k % games}",
                     "gsis_id": f"00-{k:04d}", "season": 2026, "week": week, "dk_draftable_id": float(1000 + k), "mean_projection": 4.0 + k})
    rows.append({"id": "BUF_DST", "display_name": "Bills", "pos": "DST", "game_id": "g0", "gsis_id": "None", "season": 2026,
                 "week": week, "dk_draftable_id": 2000.0, "mean_projection": 7.0})
    return pd.DataFrame(rows)


def _fp(fr, scale=1.1):
    return pd.DataFrame({"slate_player_id": fr.dk_draftable_id.astype(int).astype(str), "fantasy_points": fr.mean_projection * scale,
                         "name": "not used for the join"})


def _actual(fr, noise=0.0, seed=0):
    rng = np.random.default_rng(seed)
    return pd.Series((fr.mean_projection + noise * rng.normal(size=len(fr))).to_numpy(), index=fr.display_name.map(WPA.norm))


def _active(fr, inactive=()):
    return pd.DataFrame({"season": 2026, "week": fr.week, "gsis_id": fr.gsis_id, "act": ~fr.id.isin(inactive)})


def test_population_joins_fp_by_draftable_id_and_keeps_skill_players_only():
    fr = _frame(); d, audit = WPA.population(fr, _fp(fr), _actual(fr), _active(fr))
    assert set(d.pos) <= set(WPA.SKILL) and len(d) == 24 and audit["population"] == 24 and audit["games"] == 6
    assert np.allclose(d.fp, d.ours * 1.1) and np.allclose(d.blend, 0.5 * d.ours + 0.5 * d.fp)


def test_each_drop_is_counted():
    fr = _frame()
    fr.loc[0, "mean_projection"] = 1.0                          # p0: ours 1.0 and FP 1.1 -> below 3 on both
    fp = _fp(fr)
    fp = fp[fp.slate_player_id != "1001"]                       # p1: no FP projection
    fr.loc[3, "display_name"] = _nm(2)                      # p2 / p3 share a name -> both dropped
    act = _actual(fr).drop(WPA.norm(_nm(4)))                # p4: no actual
    d, audit = WPA.population(fr, fp, act, _active(fr, inactive={"p5"}))   # p5: not ACT
    assert audit["eligible_ge3"] == 23 and audit["dropped_no_fp"] == 1 and audit["dropped_name_collision"] == 2
    assert audit["dropped_no_actual"] == 1 and audit["dropped_not_act"] == 1 and audit["population"] == 18
    assert not set(d.id) & {"p0", "p1", "p2", "p3", "p4", "p5"}


def test_eligibility_is_either_source_at_least_3():
    fr = _frame(); fr.loc[0, "mean_projection"] = 2.0
    fp = _fp(fr); fp.loc[0, "fantasy_points"] = 3.5             # ours 2.0, FP 3.5: eligible
    d, _ = WPA.population(fr, fp, _actual(fr), _active(fr))
    assert "p0" in set(d.id)


def test_bootstrap_is_deterministic_and_reads_the_better_source():
    fr = _frame(n=48, games=12)
    act = pd.Series(fr.mean_projection.to_numpy() * 1.1, index=fr.display_name.map(WPA.norm))   # FP is exact
    d, _ = WPA.population(fr, _fp(fr), act, _active(fr))
    a, b = WPA.bootstrap(d), WPA.bootstrap(d)
    assert a == b
    assert a["ours_vs_fp"]["mean"] < 0 and a["ours_vs_fp"]["share_better"] == 0.0     # ours never beats an exact FP
    assert a["blend_vs_ours"]["share_better"] == 1.0
    assert any("no source beats FP" in m for m in WPA.revisit(d, a))


def test_pooled_bootstrap_resamples_games_within_each_week():
    w4, _ = WPA.population(_frame(week=4), _fp(_frame(week=4)), _actual(_frame(week=4)), _active(_frame(week=4)))
    one = _frame(n=4, week=5, games=1)                          # week 5: one game, always drawn once
    w5, _ = WPA.population(one, _fp(one), _actual(one), _active(one))
    pooled = pd.concat([w4, w5], ignore_index=True)
    assert pooled.groupby(["season", "week", "game"]).ngroups == 7
    bs = WPA.bootstrap(pooled, b=50)
    assert set(bs) == {"ours_vs_fp", "blend_vs_fp", "blend_vs_ours"}


def test_the_revisit_check_needs_lower_mae_and_95_percent():
    fr = _frame(n=48, games=12)
    d, _ = WPA.population(fr, _fp(fr, scale=1.5), _actual(fr), _active(fr))       # ours exact, FP 50% high
    msgs = WPA.revisit(d, WPA.bootstrap(d))
    assert any(m.startswith("OURS BEATS FP") for m in msgs)
    boot = WPA.bootstrap(d); boot["ours_vs_fp"]["share_better"] = 0.94
    boot["blend_vs_fp"]["share_better"] = 0.94
    assert any("no source beats FP" in m for m in WPA.revisit(d, boot))


def test_frozen_constants():
    assert (WPA.MIN_PROJ, WPA.B, WPA.SEED, WPA.REVISIT_SHARE) == (3.0, 2000, 1, 0.95)
    assert WPA.SKILL == ("QB", "RB", "WR", "TE")


def test_an_act_player_scoring_zero_stays_and_an_inactive_one_goes():
    fr = _frame(); act = _actual(fr)
    act[WPA.norm(_nm(6))] = 0.0; act[WPA.norm(_nm(7))] = 0.0
    d, audit = WPA.population(fr, _fp(fr), act, _active(fr, inactive={"p7"}))
    assert "p6" in set(d.id) and float(d.set_index("id").actual["p6"]) == 0.0
    assert "p7" not in set(d.id) and audit["dropped_not_act"] == 1


def test_a_name_shared_with_a_dst_or_any_slate_player_is_dropped():
    fr = _frame(); fr.loc[0, "display_name"] = "Bills"            # a skill player named like the DST
    d, audit = WPA.population(fr, _fp(fr), _actual(fr), _active(fr))
    assert "p0" not in set(d.id) and audit["dropped_name_collision"] == 1


def test_the_printed_rule_matches_the_frozen_text(tmp_path, capsys):
    doc = WPA.__doc__
    assert "at least 95% of the pooled resamples are better (B 2000, seed 1)" in doc
    assert "B 2000, seed 1" in doc and ">= 3" in doc
    for wk in (4, 5):
        fr = _frame(week=wk); d, _ = WPA.population(fr, _fp(fr), _actual(fr, noise=2.0, seed=wk), _active(fr))
        d.to_csv(tmp_path / f"accuracy-2026-w{wk:02d}.csv", index=False)
    assert WPA.main(["pool", "--out-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert ("REVISIT RULE: a source beats FP when its pooled MAE is lower than FP's AND at least 95% of B 2000 "
            "game-cluster resamples (seed 1, games resampled within week) are better") in out
    assert "REVISIT CHECK:" in out and "POOLED: players 48" in out and out.count("player rows: accuracy-2026-w0") == 2


def test_the_written_rows_are_order_independent():
    fr = _frame(); a, _ = WPA.population(fr, _fp(fr), _actual(fr), _active(fr))
    b, _ = WPA.population(fr.sample(frac=1.0, random_state=3), _fp(fr), _actual(fr), _active(fr))
    assert a.to_csv(index=False) == b.to_csv(index=False)


def test_the_fp_cutoff_is_the_t70_build_not_the_lock(tmp_path):
    run = tmp_path / "run"; run.mkdir(); frame = run / "frame.parquet"
    try:
        WPA.resolve_cutoff(frame, None, "2026-10-11T17:00:00Z")
        raise AssertionError("no receipt must refuse")
    except SystemExit as e:
        assert "no built_utc" in str(e)
    (run / "receipt.json").write_text('{"built_utc": "2026-10-11 15:50:47.4+00:00"}')
    cut, src = WPA.resolve_cutoff(frame, None, "2026-10-11T17:00:00Z")
    assert cut == "2026-10-11T15:50:47.400000+00:00" and src == "receipt.json built_utc"
    assert WPA.resolve_cutoff(frame, "2026-10-11T15:45:00Z", "2026-10-11T17:00:00Z") == ("2026-10-11T15:45:00+00:00", "--capture-before")
    try:
        WPA.resolve_cutoff(frame, "2026-10-11T17:05:00Z", "2026-10-11T17:00:00Z")
        raise AssertionError("a cutoff after the lock must refuse")
    except SystemExit as e:
        assert "after the lock" in str(e)


def test_the_reader_refuses_without_an_explicit_project(monkeypatch, tmp_path):
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    a = type("A", (), {"frame": tmp_path / "frame.parquet", "season": 2026, "week": 5, "lock_utc": "2026-10-11T17:00:00Z",
                       "contest": "1", "capture_before": None})()
    try:
        WPA.load_week(a)
        raise AssertionError("an unset GCP_PROJECT must refuse")
    except SystemExit as e:
        assert "GCP_PROJECT is not set" in str(e)


def test_tail_lines_are_descriptive_deterministic_and_leave_the_revisit_check_alone(tmp_path, capsys):
    """The outside review (10-06): top-decile hit and ownership-weighted MAE are printed, labelled DESCRIPTIVE, and the
    revisit check's output is byte-for-byte what it was without them."""
    fr = _frame(week=5); d, _ = WPA.population(fr, _fp(fr), _actual(fr, noise=2.0, seed=5), _active(fr))
    t1, t2 = WPA.tail_metrics(d), WPA.tail_metrics(d.sample(frac=1.0, random_state=3))
    assert t1 == t2                                                   # ties broken by id: order-independent
    assert all(0.0 <= t1[s]["top_decile_hit"] <= 1.0 for s in WPA.SOURCES)
    perfect = d.assign(ours=d.actual)
    assert WPA.tail_metrics(perfect)["ours"]["top_decile_hit"] == 1.0
    own = pd.DataFrame({"season": d.season, "week": d.week, "nkey": d.name.map(WPA.norm), "own": 1.0})
    t = WPA.tail_metrics(d, own)
    for s in WPA.SOURCES:                                             # equal weights reproduce the plain MAE
        assert abs(t[s]["own_weighted_MAE"] - (d[s] - d.actual).abs().mean()) < 1e-12
    heavy = own.assign(own=np.where(np.arange(len(own)) == 0, 1000.0, 1e-9))
    e0 = abs(d["fp"].iloc[0] - d.actual.iloc[0])
    assert abs(WPA.tail_metrics(d, heavy)["fp"]["own_weighted_MAE"] - e0) < 1e-3
    d.to_csv(tmp_path / "accuracy-2026-w05.csv", index=False)
    assert WPA.main(["pool", "--out-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert WPA.TAIL_LABEL in out and "own-weighted" not in out        # no ownership file: no weighted MAE in pool
    rules = [x for x in out.splitlines() if x.startswith(("REVISIT RULE", "REVISIT CHECK"))]
    assert len(rules) >= 2 and "TAIL" not in " ".join(rules)
    own.to_csv(tmp_path / "ownership-2026-w05.csv", index=False)
    assert WPA.main(["pool", "--out-dir", str(tmp_path)]) == 0
    out2 = capsys.readouterr().out
    assert "own-weighted MAE" in out2 and out2.count("player rows: accuracy-") == 1   # the ownership file is never pooled as rows
    assert [x for x in out2.splitlines() if x.startswith(("REVISIT RULE", "REVISIT CHECK"))] == rules


def test_a_shared_ownership_name_carries_no_weight_and_never_misaligns():
    """Reviewer hardening (10-06): two contest names normalising to one key must not duplicate rows in the join."""
    fr = _frame(week=5); d, _ = WPA.population(fr, _fp(fr), _actual(fr, noise=2.0, seed=5), _active(fr))
    own = pd.DataFrame({"season": d.season, "week": d.week, "nkey": d.name.map(WPA.norm), "own": 1.0})
    dup = pd.concat([own, own.iloc[[0]].assign(own=50.0)], ignore_index=True)    # the first player's key twice
    t = WPA.tail_metrics(d, dup)
    e = (d["ours"] - d.actual).abs()
    assert abs(t["ours"]["own_weighted_MAE"] - e.iloc[1:].mean()) < 1e-12        # the shared key is dropped, the rest weigh 1
