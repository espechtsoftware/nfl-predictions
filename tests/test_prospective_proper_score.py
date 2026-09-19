"""Adversarial tests for the prospective proper-score reader.

Synthetic fixtures only -- no Week-2 actuals are queried or materialized here, per the
laptop's instruction in 2026-09-19-laptop-prospective-scoring-task-and-runtime.md.
Each test tries to BREAK one claim the protocol makes rather than re-performing it.
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

SRC = Path(__file__).resolve().parents[1] / "reports/reviews/evidence/2026-09-19-prospective-proper-score-reader.py"
_spec = importlib.util.spec_from_file_location("pps_reader", SRC)
pps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pps)

AFTER = "2026-09-21T12:00:00+00:00"
BEFORE = "2026-09-20T12:00:00+00:00"


def gaussian_crps(mu, sigma, y):
    """Closed form: sigma * [z(2*Phi(z)-1) + 2*phi(z) - 1/sqrt(pi)]."""
    z = (y - mu) / sigma
    return sigma * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))


def sha_bytes(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build_bundle(tmp, n_players=40, n_games=10, draws=2000, shift=0.0, seed=0, eligible=True,
                 component_spread=0.0):
    """A synthetic two-arm bundle. `shift` biases the salaryfix arm's mean away from truth;
    `component_spread` separates I_audit from H_audit so the two components are genuinely
    different laws rather than two samples of one."""
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
    frame = pd.DataFrame({"id": ids, "pos": pos, "team": team, "opp": opp})
    truth = rng.uniform(8, 20, size=n_players)
    outcomes = truth + rng.normal(0, 5, size=n_players)

    root = tmp / "bundle"
    root.mkdir(parents=True, exist_ok=True)
    fp = root / "frame.parquet"
    frame.to_parquet(fp)
    manifest = {"arms": {}}
    for arm, bias in (("control", 0.0), ("salaryfix", shift)):
        banks = {}
        for sign, comp in ((-1.0, "I_audit"), (1.0, "H_audit")):
            centre = truth[:, None] + bias + sign * component_spread
            b = (centre + rng.normal(0, 5, size=(n_players, draws))).astype(np.float32)
            bp = root / f"{arm}_{comp}.npy"
            np.save(bp, b)
            banks[comp] = {"path": bp.name, "sha256": sha_bytes(bp)}
        manifest["arms"][arm] = {"frame": {"path": fp.name, "sha256": sha_bytes(fp)}, "banks": banks}
    if eligible:
        ep = root / "eligible.json"
        ep.write_text(json.dumps(ids[:7]))
        manifest["prior_eligible_ids"] = {"path": ep.name, "sha256": sha_bytes(ep)}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=1))

    ap = tmp / "actuals.parquet"
    pd.DataFrame({"id": ids, "points": outcomes}).to_parquet(ap)
    return root, ap, frame, outcomes


def run(root, actuals, out, now=AFTER, actuals_sha=None):
    argv = ["reader", "--bundle", str(root), "--actuals", str(actuals),
            "--actuals-sha256", actuals_sha or sha_bytes(actuals), "--out", str(out), "--now", now]
    old, sys.argv = sys.argv, argv
    try:
        pps.main()
    finally:
        sys.argv = old
    return json.loads(Path(out).read_text())


# ---- the score itself -------------------------------------------------------------------

def test_crps_matches_the_closed_form_gaussian():
    """If the estimator is wrong, every number in the report is wrong."""
    rng = np.random.default_rng(7)
    mu, sigma = 12.0, 4.0
    samples = rng.normal(mu, sigma, size=(3, 400_000))
    y = np.array([12.0, 4.0, 22.0])
    got = pps.crps(samples, y)
    want = gaussian_crps(mu, sigma, y)
    assert np.allclose(got, want, atol=0.02), (got, want)


def test_crps_is_proper_the_true_law_wins():
    """A biased law must score WORSE. A score that fails this cannot adjudicate anything."""
    rng = np.random.default_rng(3)
    truth = rng.normal(15, 5, size=(200, 4000))
    y = rng.normal(15, 5, size=200)
    biased = truth + 6.0
    assert pps.crps(truth, y).mean() < pps.crps(biased, y).mean()


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
    """CRPS is convex in F, so the pooled mixture scores strictly better than the mean of its
    components whenever those components are genuinely different laws -- which is the real
    case (incumbent vs hsim). Averaging component scores answers a different question."""
    root, actuals, _, _ = build_bundle(tmp_path, n_players=300, n_games=14, draws=4000,
                                       component_spread=6.0, seed=5)
    r = run(root, actuals, tmp_path / "o.json")
    for arm in ("control", "salaryfix"):
        assert r["scores"]["overall"][f"{arm}_mixture_gain_over_averaging"] > 0.05


def test_mixture_and_averaging_agree_when_components_are_identical(tmp_path):
    """With one law duplicated the population gap is exactly zero, so the estimator must sit
    on zero rather than drifting -- this pins the sign convention and the pooling arithmetic."""
    root, actuals, _, _ = build_bundle(tmp_path, n_players=300, n_games=14, draws=4000,
                                       component_spread=0.0, seed=5)
    r = run(root, actuals, tmp_path / "o.json")
    for arm in ("control", "salaryfix"):
        assert abs(r["scores"]["overall"][f"{arm}_mixture_gain_over_averaging"]) < 1e-3


def test_mixture_uses_pooled_draws_not_averaged_scores(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path, draws=1500, seed=6)
    r = run(root, actuals, tmp_path / "o.json")
    assert r["draws"]["control_mixture"] == 3000
    assert r["draws"]["control_I"] == 1500


# ---- the outcome gate -------------------------------------------------------------------

def test_refuses_to_run_before_the_lock(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    with pytest.raises(AssertionError, match="outcome gate"):
        run(root, actuals, tmp_path / "o.json", now=BEFORE)


def test_refuses_an_actuals_file_whose_hash_does_not_match(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    with pytest.raises(AssertionError, match="actuals sha256"):
        run(root, actuals, tmp_path / "o.json", actuals_sha="0" * 64)


def test_refuses_to_overwrite_an_existing_result(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    out = tmp_path / "o.json"
    run(root, actuals, out)
    with pytest.raises(AssertionError, match="writes once"):
        run(root, actuals, out)


def test_refuses_a_bundle_artifact_with_a_tampered_hash(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    m = json.loads((root / "manifest.json").read_text())
    m["arms"]["control"]["banks"]["I_audit"]["sha256"] = "1" * 64
    (root / "manifest.json").write_text(json.dumps(m))
    with pytest.raises(AssertionError, match="sha256"):
        run(root, actuals, tmp_path / "o.json")


def test_detects_a_silently_mutated_bank(tmp_path):
    """The hash must be checked against CONTENT, so editing the array is caught."""
    root, actuals, _, _ = build_bundle(tmp_path)
    p = root / "control_I_audit.npy"
    b = np.load(p)
    b[0, 0] += 1.0
    np.save(p, b)
    with pytest.raises(AssertionError, match="sha256"):
        run(root, actuals, tmp_path / "o.json")


# ---- support and imputation -------------------------------------------------------------

def test_players_without_outcomes_are_excluded_and_named_never_zeroed(tmp_path):
    root, actuals, _, outcomes = build_bundle(tmp_path, n_players=40)
    df = pd.read_parquet(actuals).iloc[:-3]
    df.to_parquet(actuals)
    r = run(root, actuals, tmp_path / "o.json")
    assert r["support"]["scored_common_key"] == 37
    assert sorted(r["support"]["in_frames_without_outcome"]) == ["p37", "p38", "p39"]
    assert "never zero-imputed" in r["support"]["policy"]


def test_duplicate_and_null_actuals_are_rejected(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    df = pd.read_parquet(actuals)
    pd.concat([df, df.iloc[:1]]).to_parquet(actuals)
    with pytest.raises(AssertionError, match="duplicate"):
        run(root, actuals, tmp_path / "o.json")
    df.loc[0, "points"] = np.nan
    df.to_parquet(actuals)
    with pytest.raises(AssertionError, match="null points"):
        run(root, actuals, tmp_path / "o2.json")


def test_missing_eligible_list_is_reported_not_silently_skipped(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path, eligible=False)
    r = run(root, actuals, tmp_path / "o.json")
    assert "prior_eligible" not in r["scores"]
    assert r["support"]["prior_eligible_supplied"] is None
    assert "not silently skipped" in r["support"]["prior_eligible_note"]


# ---- clustering -------------------------------------------------------------------------

def test_no_interval_below_the_cluster_floor(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path, n_players=20, n_games=3)
    r = run(root, actuals, tmp_path / "o.json")
    assert r["contrast"]["overall"]["interval"] is None
    assert "fewer than 8" in r["contrast"]["overall"]["note"]


def test_clustering_widens_the_interval_when_games_are_correlated():
    """If the bootstrap ignored clusters this interval would be far too narrow -- the
    protocol's whole uncertainty claim rests on it."""
    rng = np.random.default_rng(2)
    n_games, per = 12, 30
    clusters = np.repeat([f"g{i}" for i in range(n_games)], per)
    shared = rng.normal(0, 1.0, size=n_games)
    diffs = np.repeat(shared, per) + rng.normal(0, 0.05, size=n_games * per)
    clustered = pps.cluster_bootstrap(diffs, clusters, np.random.default_rng(0))
    iid = pps.cluster_bootstrap(diffs, np.arange(len(diffs)).astype(str), np.random.default_rng(0))
    w_c = clustered["interval"][1] - clustered["interval"][0]
    w_i = iid["interval"][1] - iid["interval"][0]
    assert w_c > 4 * w_i, (w_c, w_i)


def test_bootstrap_is_deterministic_under_the_frozen_seed(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path, seed=9)
    a = run(root, actuals, tmp_path / "a.json")
    b = run(root, actuals, tmp_path / "b.json")
    assert a["contrast"]["overall"] == b["contrast"]["overall"]


# ---- end to end -------------------------------------------------------------------------

def test_a_genuinely_worse_arm_is_detected_with_the_right_sign(tmp_path):
    """Bias the salaryfix law away from truth; its CRPS must rise (positive contrast)."""
    root, actuals, _, _ = build_bundle(tmp_path, n_players=300, n_games=14, shift=7.0, seed=4)
    r = run(root, actuals, tmp_path / "o.json")
    c = r["contrast"]["overall"]
    assert c["point"] > 0 and c["interval"][0] > 0
    assert "negative favours the repaired law" in c["direction"]


def test_report_carries_no_decision_rule(tmp_path):
    root, actuals, _, _ = build_bundle(tmp_path)
    r = run(root, actuals, tmp_path / "o.json")
    assert "one slate nominates nothing" in r["scope"]
    assert r["reader_sha256"] == sha_bytes(SRC)


# ---- descriptive book block -------------------------------------------------------------

def add_books(root, ids, per_arm=("control", "salaryfix"), n=6, missing=False):
    """Attach entered-lineup orders to the bundle so the descriptive block runs."""
    m = json.loads((root / "manifest.json").read_text())
    for arm in per_arm:
        pool = list(ids)
        if missing and arm == "salaryfix":
            pool = pool + ["ghost"]
        orders = [[pool[(k * 9 + j) % len(pool)] for j in range(9)] for k in range(n)]
        if missing and arm == "salaryfix":
            orders[0][0] = "ghost"
        bp = root / f"{arm}_book.json"
        bp.write_text(json.dumps(orders))
        m["arms"][arm]["book_orders"] = {"path": bp.name, "sha256": sha_bytes(bp)}
    (root / "manifest.json").write_text(json.dumps(m))


def test_descriptive_book_block_scores_lineups_and_the_maximum(tmp_path):
    root, actuals, frame, outcomes = build_bundle(tmp_path, n_players=40, n_games=10, seed=12)
    add_books(root, list(frame.id))
    r = run(root, actuals, tmp_path / "o.json")
    d = r["descriptive"]["control"]
    assert d["scoreable"] is True and d["lineups"] == 6
    assert 0.0 <= d["realized_max_pit"] <= 1.0
    assert d["realized_max"] > 0
    assert "no interval" in r["descriptive"]["note"]


def test_descriptive_block_reports_unscoreable_arm_without_crashing(tmp_path):
    """A book player with no settled outcome must be named, not zero-imputed or fatal."""
    root, actuals, frame, _ = build_bundle(tmp_path, n_players=40, n_games=10, seed=13)
    add_books(root, list(frame.id), missing=True)
    r = run(root, actuals, tmp_path / "o.json")
    assert r["descriptive"]["control"]["scoreable"] is True
    assert r["descriptive"]["salaryfix"]["scoreable"] is False
    assert r["descriptive"]["salaryfix"]["players_without_outcome"] == ["ghost"]


def test_book_block_absent_for_an_arm_that_supplies_no_orders(tmp_path):
    root, actuals, frame, _ = build_bundle(tmp_path, n_players=40, n_games=10, seed=14)
    add_books(root, list(frame.id), per_arm=("control",))
    r = run(root, actuals, tmp_path / "o.json")
    assert "control" in r["descriptive"] and "salaryfix" not in r["descriptive"]
