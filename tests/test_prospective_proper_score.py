"""Adversarial tests for the prospective proper-score reader (v2).

Synthetic fixtures only -- no Week-2 actuals are queried or materialized here.
Each test tries to BREAK one claim the protocol makes rather than re-performing it.
"""
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

SRC = Path(__file__).resolve().parents[1] / "reports/reviews/evidence/2026-09-19-prospective-proper-score-reader.py"
_spec = importlib.util.spec_from_file_location("pps_reader", SRC)
pps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pps)


def AFTER():
    return dt.datetime(2026, 9, 21, 12, 0, tzinfo=dt.timezone.utc)


def BEFORE_SETTLE():
    """Lock has passed and Thursday labels exist, but the main slate has not settled."""
    return dt.datetime(2026, 9, 20, 23, 0, tzinfo=dt.timezone.utc)


def gaussian_crps(mu, sigma, y):
    z = (y - mu) / sigma
    return sigma * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))


def sha_bytes(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_actuals_manifest(tmp, actuals, n_games=10, **over):
    m = {"season": 2026, "week": 2, "draft_group": 153428, "slate": "sunday_main",
         "scoring": "dk_classic_v1", "source": "synthetic-fixture",
         "games": [{"game_id": f"g{i}", "status": "FINAL"} for i in range(n_games)],
         "all_games_final": True, "actuals_sha256": sha_bytes(actuals)}
    m.update(over)
    p = tmp / "actuals_manifest.json"
    p.write_text(json.dumps(m, indent=1))
    return p


def build_bundle(tmp, n_players=40, n_games=10, draws=2000, shift=0.0, seed=0, eligible=True,
                 component_spread=0.0):
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(2 * n_games)]
    ids, pos, team, opp = [], [], [], []
    for k in range(n_players):
        g = k % n_games
        home, away = teams[2 * g], teams[2 * g + 1]
        ids.append(f"p{k}")
        pos.append(("QB", "RB", "WR", "TE", "DST")[k % 5])
        team.append(home if k % 2 else away)
        opp.append(away if k % 2 else home)
    row_game = [f"g{k % n_games}" for k in range(n_players)]
    frame = pd.DataFrame({"id": ids, "pos": pos, "team": team, "opp": opp, "game_id": row_game})
    slate = [{"game_id": f"g{g}", "home": teams[2 * g], "away": teams[2 * g + 1]} for g in range(n_games)]
    truth = rng.uniform(8, 20, size=n_players)
    outcomes = truth + rng.normal(0, 5, size=n_players)

    root = tmp / "bundle"
    root.mkdir(parents=True, exist_ok=True)
    manifest = {"arms": {}}
    for arm, bias in (("control", 0.0), ("salaryfix", shift)):
        fp = root / f"{arm}_frame.parquet"
        frame.to_parquet(fp)
        banks = {}
        for sign, comp in ((-1.0, "I_audit"), (1.0, "H_audit")):
            b = (truth[:, None] + bias + sign * component_spread +
                 rng.normal(0, 5, size=(n_players, draws))).astype(np.float32)
            bp = root / f"{arm}_{comp}.npy"
            np.save(bp, b)
            banks[comp] = {"path": bp.name, "sha256": sha_bytes(bp)}
        manifest["arms"][arm] = {"frame": {"path": fp.name, "sha256": sha_bytes(fp)}, "banks": banks}
    if eligible:
        ep = root / "eligible.json"
        ep.write_text(json.dumps(ids[:7]))
        manifest["prior_eligible_ids"] = {"path": ep.name, "sha256": sha_bytes(ep)}
    manifest["games"] = slate
    (root / "manifest.json").write_text(json.dumps(manifest, indent=1))

    ap = tmp / "actuals.parquet"
    pd.DataFrame({"id": ids, "points": outcomes, "season": 2026, "week": 2,
                  "game_id": row_game}).to_parquet(ap)
    write_actuals_manifest(tmp, ap, n_games=n_games)
    return root, ap, frame, outcomes


def run(root, actuals, out, clock=AFTER, manifest=None, manifest_sha=None):
    mp = manifest or (Path(actuals).parent / "actuals_manifest.json")
    argv = ["--bundle", str(root), "--actuals", str(actuals), "--actuals-manifest", str(mp),
            "--actuals-manifest-sha256", manifest_sha or sha_bytes(mp), "--out", str(out)]
    pps.main(argv=argv, clock=clock)
    return json.loads(Path(out).read_text())


# ---- the score itself -------------------------------------------------------------------

def test_crps_matches_the_closed_form_gaussian():
    rng = np.random.default_rng(7)
    samples = rng.normal(12.0, 4.0, size=(3, 400_000))
    y = np.array([12.0, 4.0, 22.0])
    assert np.allclose(pps.crps(samples, y), gaussian_crps(12.0, 4.0, y), atol=0.02)


def test_the_laptops_duplicate_array_counterexample():
    """Exact case from the v1 review. With the fair estimator n*(n-1) the component scores 0
    and the pooled duplicate scores 1/3 -- a NEGATIVE mixture gain for identical forecasts.
    The issued-distribution estimator must give 0.5 and 0.5, gain exactly zero."""
    comp = np.array([[0.0, 2.0]])
    pooled = np.array([[0.0, 0.0, 2.0, 2.0]])
    y = np.array([1.0])
    assert pps.crps(comp, y)[0] == pytest.approx(0.5)
    assert pps.crps(pooled, y)[0] == pytest.approx(0.5)
    assert pps.crps(comp, y)[0] - pps.crps(pooled, y)[0] == pytest.approx(0.0, abs=1e-12)


def test_identical_component_arrays_give_exactly_zero_mixture_gain():
    """Byte-identical arrays, zero tolerance -- not 'independent draws from one law'."""
    rng = np.random.default_rng(1)
    a = rng.normal(12, 5, size=(50, 400))
    y = rng.normal(12, 5, size=50)
    pooled = np.concatenate([a, a.copy()], axis=1)
    assert np.allclose(pps.crps(a, y), pps.crps(pooled, y), atol=1e-12)


def test_crps_is_proper_the_true_law_wins():
    rng = np.random.default_rng(3)
    truth = rng.normal(15, 5, size=(200, 4000))
    y = rng.normal(15, 5, size=200)
    assert pps.crps(truth, y).mean() < pps.crps(truth + 6.0, y).mean()


def test_crps_rejects_a_degenerate_single_draw():
    with pytest.raises(AssertionError):
        pps.crps(np.zeros((2, 1)), np.zeros(2))


def test_pit_is_uniform_for_a_calibrated_law():
    rng = np.random.default_rng(11)
    s = rng.normal(0, 1, size=(4000, 500))
    y = rng.normal(0, 1, size=4000)
    assert abs(pps.pit(s, y).mean() - 0.5) < 0.02


# ---- the mixture claim ------------------------------------------------------------------

def test_pooled_mixture_beats_averaging_when_components_differ(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path, n_players=300, n_games=14, draws=4000,
                                       component_spread=6.0, seed=5)
    r = run(root, actuals, tmp_path / "o.json")
    for arm in ("control", "salaryfix"):
        assert r["scores"]["overall"][f"{arm}_mixture_gain_over_averaging"] > 0.05


def test_mixture_uses_pooled_draws(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path, draws=1500, seed=6)
    r = run(root, actuals, tmp_path / "o.json")
    assert r["draws"]["control_mixture"] == 3000 and r["draws"]["control_I"] == 1500


def test_mismatched_component_widths_are_refused(tmp_path):
    """Unequal widths would make the pooled sample an unequal-weight mixture."""
    root, actuals, _, _ = build_bundle(tmp_path, draws=1000)
    p = root / "control_H_audit.npy"
    np.save(p, np.load(p)[:, :500])
    m = json.loads((root / "manifest.json").read_text())
    m["arms"]["control"]["banks"]["H_audit"]["sha256"] = sha_bytes(p)
    (root / "manifest.json").write_text(json.dumps(m))
    with pytest.raises(AssertionError, match="share a draw width"):
        run(root, actuals, tmp_path / "o.json")


# ---- the outcome gate -------------------------------------------------------------------

def test_refuses_before_the_sunday_main_settle_point(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    with pytest.raises(AssertionError, match="outcome gate"):
        run(root, actuals, tmp_path / "o.json", clock=BEFORE_SETTLE)


def test_the_gate_has_no_cli_override(tmp_path):
    """v1 exposed --now, which let any caller walk past the gate. Behavioural, not a
    string scan: argparse must reject the flag outright."""
    root, actuals, _, _ = build_bundle(tmp_path)
    mp = tmp_path / "actuals_manifest.json"
    argv = ["--bundle", str(root), "--actuals", str(actuals), "--actuals-manifest", str(mp),
            "--actuals-manifest-sha256", sha_bytes(mp), "--out", str(tmp_path / "o.json"),
            "--now", "2099-01-01T00:00:00+00:00"]
    with pytest.raises(SystemExit):
        pps.main(argv=argv, clock=BEFORE_SETTLE)
    assert not (tmp_path / "o.json").exists()
    assert "def main(argv=None, clock=None)" in SRC.read_text()


def test_refuses_a_manifest_whose_hash_does_not_match(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    with pytest.raises(AssertionError, match="manifest sha256"):
        run(root, actuals, tmp_path / "o.json", manifest_sha="0" * 64)


def test_refuses_actuals_that_do_not_match_the_manifest(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    df = pd.read_parquet(actuals)
    df.loc[0, "points"] = df.loc[0, "points"] + 1.0
    df.to_parquet(actuals)
    with pytest.raises(AssertionError, match="actuals sha256"):
        run(root, actuals, tmp_path / "o.json")


@pytest.mark.parametrize("field,value", [("season", 2025), ("week", 3), ("draft_group", 999999),
                                         ("slate", "thursday"), ("scoring", "fanduel")])
def test_wrong_slate_identity_is_refused_even_with_a_valid_hash(tmp_path, field, value):
    """A hash pins which bytes, not which slate."""
    root, actuals, _, _ = build_bundle(tmp_path)
    mp = write_actuals_manifest(tmp_path, actuals, **{field: value})
    with pytest.raises(AssertionError, match=field):
        run(root, actuals, tmp_path / "o.json", manifest=mp)


def test_incomplete_games_are_refused(tmp_path):
    """The full forecast slate is present, so identity passes; one game is still in progress."""
    root, actuals, _, _ = build_bundle(tmp_path)
    games = [{"game_id": f"g{i}", "status": "FINAL"} for i in range(10)]
    games[3]["status"] = "IN_PROGRESS"
    mp = write_actuals_manifest(tmp_path, actuals, games=games)
    with pytest.raises(AssertionError, match="non-final games"):
        run(root, actuals, tmp_path / "o.json", manifest=mp)


def test_missing_all_games_final_assertion_is_refused(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    mp = write_actuals_manifest(tmp_path, actuals, all_games_final=False)
    with pytest.raises(AssertionError, match="all_games_final"):
        run(root, actuals, tmp_path / "o.json", manifest=mp)


def test_refuses_to_overwrite_an_existing_result(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    out = tmp_path / "o.json"
    run(root, actuals, out)
    with pytest.raises(AssertionError, match="writes once"):
        run(root, actuals, out)


def test_detects_a_silently_mutated_bank(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    p = root / "control_I_audit.npy"
    b = np.load(p)
    b[0, 0] += 1.0
    np.save(p, b)
    with pytest.raises(AssertionError, match="sha256"):
        run(root, actuals, tmp_path / "o.json")


# ---- support, imputation and cross-arm consistency ---------------------------------------

def test_players_without_outcomes_are_excluded_and_named_never_zeroed(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path, n_players=40)
    pd.read_parquet(actuals).iloc[:-3].to_parquet(actuals)
    write_actuals_manifest(tmp_path, actuals)
    r = run(root, actuals, tmp_path / "o.json")
    assert r["support"]["scored_common_key"] == 37
    assert sorted(r["support"]["in_frames_without_outcome"]) == ["p37", "p38", "p39"]
    assert "never zero-imputed" in r["support"]["policy"]


def test_nonfinite_points_are_refused(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    df = pd.read_parquet(actuals)
    df.loc[0, "points"] = np.inf
    df.to_parquet(actuals)
    write_actuals_manifest(tmp_path, actuals)
    with pytest.raises(AssertionError, match="non-finite points"):
        run(root, actuals, tmp_path / "o.json")


def test_null_ids_are_refused(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    df = pd.read_parquet(actuals)
    df.loc[0, "id"] = None
    df.to_parquet(actuals)
    write_actuals_manifest(tmp_path, actuals)
    with pytest.raises(AssertionError, match="null ids"):
        run(root, actuals, tmp_path / "o.json")


def test_arms_disagreeing_on_player_metadata_are_refused(tmp_path):
    """Different team/opp across arms means the frames describe different worlds."""
    root, actuals, _, _ = build_bundle(tmp_path)
    fp = root / "salaryfix_frame.parquet"
    fr = pd.read_parquet(fp)
    fr.loc[0, "team"] = "ZZZ"
    fr.to_parquet(fp)
    m = json.loads((root / "manifest.json").read_text())
    m["arms"]["salaryfix"]["frame"]["sha256"] = sha_bytes(fp)
    (root / "manifest.json").write_text(json.dumps(m))
    with pytest.raises(AssertionError, match="disagree on team"):
        run(root, actuals, tmp_path / "o.json")


def test_missing_eligible_list_is_reported_not_silently_skipped(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path, eligible=False)
    r = run(root, actuals, tmp_path / "o.json")
    assert "prior_eligible" not in r["scores"]
    assert r["support"]["prior_eligible_supplied"] is None


# ---- clustering -------------------------------------------------------------------------

def test_no_interval_below_the_cluster_floor(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path, n_players=20, n_games=3)  # manifest games follow n_games
    r = run(root, actuals, tmp_path / "o.json")
    assert r["contrast"]["overall"]["interval"] is None
    assert "fewer than 8" in r["contrast"]["overall"]["note"]


def test_clustering_widens_the_interval_when_games_are_correlated():
    rng = np.random.default_rng(2)
    n_games, per = 12, 30
    clusters = np.repeat([f"g{i}" for i in range(n_games)], per)
    diffs = np.repeat(rng.normal(0, 1.0, size=n_games), per) + rng.normal(0, 0.05, size=n_games * per)
    c = pps.cluster_bootstrap(diffs, clusters, np.random.default_rng(0))
    i = pps.cluster_bootstrap(diffs, np.arange(len(diffs)).astype(str), np.random.default_rng(0))
    assert (c["interval"][1] - c["interval"][0]) > 4 * (i["interval"][1] - i["interval"][0])


def test_bootstrap_is_deterministic_under_the_frozen_seed(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path, seed=9)
    a = run(root, actuals, tmp_path / "a.json")
    b = run(root, actuals, tmp_path / "b.json")
    assert a["contrast"]["overall"] == b["contrast"]["overall"]


# ---- books ------------------------------------------------------------------------------

def add_books(root, ids, per_arm=("control", "salaryfix"), n=6, expected=None, corrupt=None):
    m = json.loads((root / "manifest.json").read_text())
    for arm in per_arm:
        orders = [[ids[(k * 9 + j) % len(ids)] for j in range(9)] for k in range(n)]
        if corrupt == "duplicate_player":
            orders[0][1] = orders[0][0]
        elif corrupt == "duplicate_lineup":
            orders[1] = list(orders[0])
        elif corrupt == "short":
            orders[0] = orders[0][:8]
        bp = root / f"{arm}_book.json"
        bp.write_text(json.dumps(orders))
        m["arms"][arm]["book_orders"] = {"path": bp.name, "sha256": sha_bytes(bp)}
        m["arms"][arm]["expected_book_size"] = len(orders) if expected is None else expected
    (root / "manifest.json").write_text(json.dumps(m))


def test_books_are_scored_under_every_law_not_only_their_own(tmp_path):
    root, actuals, frame, _ = build_bundle(tmp_path, n_players=40, n_games=10, seed=12)
    add_books(root, list(frame.id))
    r = run(root, actuals, tmp_path / "o.json")
    for arm in ("control", "salaryfix"):
        laws = r["descriptive"][arm]["under_law"]
        assert {"control_mixture", "salaryfix_mixture"} <= set(laws)
        assert 0.0 <= laws["control_mixture"]["realized_max_pit"] <= 1.0


def test_books_are_labelled_prospective_shadow_without_an_entered_identity(tmp_path):
    root, actuals, frame, _ = build_bundle(tmp_path, n_players=40, n_games=10, seed=13)
    add_books(root, list(frame.id))
    r = run(root, actuals, tmp_path / "o.json")
    assert "PROSPECTIVE SHADOW BOOKS" in r["descriptive"]["book_identity"]
    assert r["descriptive"]["control"]["is_entered_book"] is False
    assert "float32 summation order" in r["descriptive"]["note"]


def test_declared_entered_book_is_labelled(tmp_path):
    root, actuals, frame, _ = build_bundle(tmp_path, n_players=40, n_games=10, seed=14)
    add_books(root, list(frame.id))
    m = json.loads((root / "manifest.json").read_text())
    m["entered_book"] = "control"
    (root / "manifest.json").write_text(json.dumps(m))
    r = run(root, actuals, tmp_path / "o.json")
    assert r["descriptive"]["control"]["is_entered_book"] is True
    assert r["descriptive"]["salaryfix"]["is_entered_book"] is False


@pytest.mark.parametrize("corrupt,match", [("duplicate_player", "duplicate players"),
                                           ("duplicate_lineup", "duplicate lineup"),
                                           ("short", "not 9 players")])
def test_malformed_books_are_refused(tmp_path, corrupt, match):
    root, actuals, frame, _ = build_bundle(tmp_path, n_players=40, n_games=10, seed=15)
    add_books(root, list(frame.id), corrupt=corrupt)
    with pytest.raises(AssertionError, match=match):
        run(root, actuals, tmp_path / "o.json")


def test_book_size_must_match_the_manifest(tmp_path):
    root, actuals, frame, _ = build_bundle(tmp_path, n_players=40, n_games=10, seed=16)
    add_books(root, list(frame.id), n=6, expected=97)
    with pytest.raises(AssertionError, match="manifest expects 97"):
        run(root, actuals, tmp_path / "o.json")


# ---- end to end -------------------------------------------------------------------------

def test_a_genuinely_worse_arm_is_detected_with_the_right_sign(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path, n_players=300, n_games=14, shift=7.0, seed=4)
    r = run(root, actuals, tmp_path / "o.json")
    c = r["contrast"]["overall"]
    assert c["point"] > 0 and c["interval"][0] > 0


def test_report_carries_no_decision_rule_and_declares_its_estimator(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    r = run(root, actuals, tmp_path / "o.json")
    assert "one slate nominates nothing" in r["scope"]
    assert "denominator n*n" in r["crps_estimator"]
    assert r["reader_sha256"] == sha_bytes(SRC)


# ---- the actuals must be THE forecast slate ---------------------------------------------

def test_extra_game_in_the_actuals_manifest_is_refused(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    m = json.loads((tmp_path / "actuals_manifest.json").read_text())
    m["games"].append({"game_id": "gZZ", "status": "FINAL"})
    mp = tmp_path / "actuals_manifest.json"
    mp.write_text(json.dumps(m))
    with pytest.raises(AssertionError, match="outside the forecast slate"):
        run(root, actuals, tmp_path / "o.json", manifest=mp)


def test_missing_game_in_the_actuals_manifest_is_refused(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    m = json.loads((tmp_path / "actuals_manifest.json").read_text())
    m["games"] = m["games"][:-1]
    mp = tmp_path / "actuals_manifest.json"
    mp.write_text(json.dumps(m))
    with pytest.raises(AssertionError, match="missing forecast games"):
        run(root, actuals, tmp_path / "o.json", manifest=mp)


def test_duplicate_game_in_the_actuals_manifest_is_refused(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    m = json.loads((tmp_path / "actuals_manifest.json").read_text())
    m["games"].append(dict(m["games"][0]))
    mp = tmp_path / "actuals_manifest.json"
    mp.write_text(json.dumps(m))
    with pytest.raises(AssertionError, match="duplicate game_ids"):
        run(root, actuals, tmp_path / "o.json", manifest=mp)


def test_actual_rows_from_another_week_are_refused(tmp_path):
    """Week-2 Thursday labels exist; a row from the wrong week must not slip in."""
    root, actuals, _, _ = build_bundle(tmp_path)
    df = pd.read_parquet(actuals)
    df.loc[0, "week"] = 1
    df.to_parquet(actuals)
    write_actuals_manifest(tmp_path, actuals)
    with pytest.raises(AssertionError, match="another week"):
        run(root, actuals, tmp_path / "o.json")


def test_actual_rows_from_an_off_slate_game_are_refused(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    df = pd.read_parquet(actuals)
    df.loc[0, "game_id"] = "gZZ"
    df.to_parquet(actuals)
    write_actuals_manifest(tmp_path, actuals)
    with pytest.raises(AssertionError, match="outside the forecast slate"):
        run(root, actuals, tmp_path / "o.json")


def test_actuals_must_bind_rows_to_a_game(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    pd.read_parquet(actuals).drop(columns=["game_id"]).to_parquet(actuals)
    write_actuals_manifest(tmp_path, actuals)
    with pytest.raises(AssertionError, match="bind every row to its game_id"):
        run(root, actuals, tmp_path / "o.json")


def test_player_belonging_to_no_forecast_game_is_refused(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    for arm in ("control", "salaryfix"):
        fp = root / f"{arm}_frame.parquet"
        fr = pd.read_parquet(fp)
        fr.loc[0, "opp"] = "ZZZ"
        fr.to_parquet(fp)
        m = json.loads((root / "manifest.json").read_text())
        m["arms"][arm]["frame"]["sha256"] = sha_bytes(fp)
        (root / "manifest.json").write_text(json.dumps(m))
    with pytest.raises(AssertionError, match="match no forecast game"):
        run(root, actuals, tmp_path / "o.json")


def test_metadata_mismatch_is_caught_even_without_an_outcome(tmp_path):
    """The check runs on the full cross-arm universe, so a missing outcome cannot hide it."""
    root, actuals, _, _ = build_bundle(tmp_path, n_players=40)
    fp = root / "salaryfix_frame.parquet"
    fr = pd.read_parquet(fp)
    fr.loc[39, "pos"] = "QB" if fr.loc[39, "pos"] != "QB" else "WR"
    fr.to_parquet(fp)
    m = json.loads((root / "manifest.json").read_text())
    m["arms"]["salaryfix"]["frame"]["sha256"] = sha_bytes(fp)
    (root / "manifest.json").write_text(json.dumps(m))
    pd.read_parquet(actuals).iloc[:-1].to_parquet(actuals)   # p39 has NO outcome
    write_actuals_manifest(tmp_path, actuals)
    with pytest.raises(AssertionError, match="disagree on pos"):
        run(root, actuals, tmp_path / "o.json")


def test_supplied_book_must_declare_its_expected_size(tmp_path):
    root, actuals, frame, _ = build_bundle(tmp_path, n_players=40, n_games=10, seed=17)
    add_books(root, list(frame.id))
    m = json.loads((root / "manifest.json").read_text())
    del m["arms"]["control"]["expected_book_size"]
    (root / "manifest.json").write_text(json.dumps(m))
    with pytest.raises(AssertionError, match="must declare expected_book_size"):
        run(root, actuals, tmp_path / "o.json")


# ---- each actual must belong to the player's OWN forecast game ---------------------------

def test_on_slate_but_wrong_game_is_refused(tmp_path):
    """The laptop's reproduction: p0 moves from g0 to g1. Both are valid slate games, and v3
    accepted it because it checked each half separately but never that they matched."""
    root, actuals, _, _ = build_bundle(tmp_path, n_players=40, n_games=10)
    df = pd.read_parquet(actuals)
    assert df.loc[0, "game_id"] == "g0"
    df.loc[0, "game_id"] = "g1"
    df.to_parquet(actuals)
    write_actuals_manifest(tmp_path, actuals)
    with pytest.raises(AssertionError, match="wrong forecast game"):
        run(root, actuals, tmp_path / "o.json")


def test_frame_game_id_contradicting_its_own_sides_is_refused(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path, n_players=40, n_games=10)
    fp = root / "control_frame.parquet"
    fr = pd.read_parquet(fp)
    fr.loc[0, "game_id"] = "g2"          # sides still say g0
    fr.to_parquet(fp)
    m = json.loads((root / "manifest.json").read_text())
    m["arms"]["control"]["frame"]["sha256"] = sha_bytes(fp)
    (root / "manifest.json").write_text(json.dumps(m))
    with pytest.raises(AssertionError, match="wrong forecast game"):
        run(root, actuals, tmp_path / "o.json")


def test_arm_only_player_is_game_bound_too(tmp_path):
    """A player present in one arm only is never in the cross-arm universe, so the metadata and
    orphan checks skip him -- but he can still be scored descriptively in that arm's book."""
    root, actuals, _, _ = build_bundle(tmp_path, n_players=40, n_games=10)
    fp = root / "salaryfix_frame.parquet"
    fr = pd.read_parquet(fp)
    extra = pd.DataFrame([{"id": "extra1", "pos": "WR", "team": "T0", "opp": "T1", "game_id": "g0"}])
    pd.concat([fr, extra], ignore_index=True).to_parquet(fp)
    for comp in ("I_audit", "H_audit"):
        bp = root / f"salaryfix_{comp}.npy"
        b = np.load(bp)
        np.save(bp, np.vstack([b, b[:1]]))
    m = json.loads((root / "manifest.json").read_text())
    m["arms"]["salaryfix"]["frame"]["sha256"] = sha_bytes(fp)
    for comp in ("I_audit", "H_audit"):
        m["arms"]["salaryfix"]["banks"][comp]["sha256"] = sha_bytes(root / f"salaryfix_{comp}.npy")
    (root / "manifest.json").write_text(json.dumps(m))
    df = pd.read_parquet(actuals)
    df = pd.concat([df, pd.DataFrame([{"id": "extra1", "points": 11.0, "season": 2026,
                                       "week": 2, "game_id": "g4"}])], ignore_index=True)  # wrong game
    df.to_parquet(actuals)
    write_actuals_manifest(tmp_path, actuals)
    with pytest.raises(AssertionError, match="wrong forecast game"):
        run(root, actuals, tmp_path / "o.json")


def test_correct_game_binding_passes_and_is_recorded(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path, n_players=40, n_games=10)
    r = run(root, actuals, tmp_path / "o.json")
    assert "own forecast fixture" in r["support"]["player_game_binding"]
    assert r["support"]["forecast_games"] == 10
