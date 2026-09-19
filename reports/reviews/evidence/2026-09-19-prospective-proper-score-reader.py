"""Outcome-gated prospective proper-score reader (v2).

Scores the control and salary-repaired predictive laws against realized Sunday-main outcomes
with CRPS. Protocol: reports/2026-09-19-prospective-proper-score-protocol.md, frozen prelock.

Scores LAWS, not books. Clusters are games. One slate nominates nothing.

v2 corrections, from the laptop's review of v1 (`78187fb3`):
  * CRPS is the score of the ISSUED empirical distribution (denominator n*n), NOT the fair
    ensemble estimator n*(n-1). The banks are the forecast, not a sample from it. The fair
    correction is invalid on a deterministic stratified concatenation and breaks convexity:
    for components [0,2] and [0,2] with y=1 it returns component 0 and pooled 1/3, a gain of
    -1/3 for identical forecasts. See Ferro (2013) on fair vs issued-distribution scores.
  * The clock is injected, never a CLI argument; v1's `--now` let any caller bypass the gate.
  * Outcome identity is established by a pinned MANIFEST (season/week/group/scoring/slate/
    finalized games), not by a file hash alone: a hash pins which bytes, not which slate.
  * Gate is after the SUNDAY-MAIN slate settles. Week-2 Thursday labels already exist.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEASON, WEEK, DRAFT_GROUP, SLATE = 2026, 2, 153428, "sunday_main"
SCORING = "dk_classic_v1"
SETTLE_AFTER_UTC = dt.datetime(2026, 9, 21, 2, 0, tzinfo=dt.timezone.utc)   # after the main slate finalizes
COMPONENTS = ("I_audit", "H_audit")
POSITIONS = ("QB", "RB", "WR", "TE", "DST")
ROSTER_SIZE = 9
BOOTSTRAP = 10_000
MIN_CLUSTERS = 8
SEED = 20260920


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def opened(rec, root):
    p = root / rec["path"] if not Path(rec["path"]).is_absolute() else Path(rec["path"])
    got = sha(p)
    assert got == rec["sha256"], f"{p}: sha256 {got} != manifest {rec['sha256']}"
    return p


def crps(samples, y):
    """CRPS of the issued empirical distribution: E|X-y| - 1/2 E|X-X'| with denominator n*n.

    Convex in the distribution, so the equal-width pooled mixture scores no worse than the
    mean of its components' scores, with equality for identical components.
    """
    x = np.sort(np.asarray(samples, dtype=np.float64), axis=1)
    y = np.asarray(y, dtype=np.float64)
    n = x.shape[1]
    assert n > 1, "CRPS needs at least two draws"
    term1 = np.abs(x - y[:, None]).mean(axis=1)
    w = 2.0 * np.arange(1, n + 1) - n - 1.0
    return term1 - (x * w).sum(axis=1) / (n * n)


def pit(samples, y):
    x = np.asarray(samples, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    below = (x < y[:, None]).sum(axis=1)
    ties = (x == y[:, None]).sum(axis=1)
    return (below + 0.5 * ties) / x.shape[1]


def cluster_bootstrap(diffs, clusters, rng, b=BOOTSTRAP):
    keys = np.unique(clusters)
    k = len(keys)
    if k < MIN_CLUSTERS:
        return dict(point=float(diffs.mean()), clusters=int(k), interval=None,
                    note=f"fewer than {MIN_CLUSTERS} game clusters; no interval emitted")
    sums = np.array([diffs[clusters == g].sum() for g in keys], dtype=np.float64)
    counts = np.array([(clusters == g).sum() for g in keys], dtype=np.float64)
    idx = rng.integers(0, k, size=(b, k))
    reps = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    lo, hi = np.percentile(reps, [2.5, 97.5])
    return dict(point=float(diffs.mean()), clusters=int(k),
                interval=[float(lo), float(hi)], bootstrap_replicates=int(b))


def check_actuals_identity(manifest):
    """A hash pins which bytes; only the manifest establishes which slate they describe."""
    for field, want in (("season", SEASON), ("week", WEEK), ("draft_group", DRAFT_GROUP),
                        ("slate", SLATE), ("scoring", SCORING)):
        got = manifest.get(field)
        assert got == want, f"actuals manifest {field}={got!r}, expected {want!r}"
    assert manifest.get("source"), "actuals manifest must name its source"
    games = manifest.get("games")
    assert isinstance(games, list) and games, "actuals manifest must list the slate's games"
    unfinished = [g.get("game_id") for g in games if str(g.get("status", "")).upper() != "FINAL"]
    assert not unfinished, f"actuals manifest has non-final games: {unfinished}"
    assert manifest.get("all_games_final") is True, "actuals manifest must assert all_games_final"


def load_arm(spec, root):
    frame = pd.read_parquet(opened(spec["frame"], root))
    assert len(frame) == frame.id.nunique(), "frame ids are not unique"
    assert frame.id.notna().all(), "frame has null ids"
    banks = {}
    for name in COMPONENTS:
        a = np.load(opened(spec["banks"][name], root), allow_pickle=False)
        assert a.ndim == 2, f"{name}: bank must be 2-D, got shape {a.shape}"
        assert a.shape[0] == len(frame), f"{name}: {a.shape[0]} rows for a {len(frame)}-player frame"
        assert a.shape[1] > 1, f"{name}: degenerate draw width {a.shape[1]}"
        assert np.isfinite(a).all(), f"{name}: non-finite draws"
        banks[name] = a
    widths = {b.shape[1] for b in banks.values()}
    assert len(widths) == 1, f"components must share a draw width for an equal-weight mixture: {widths}"
    return frame, banks


def load_book(spec, root, ids):
    orders = json.loads(opened(spec, root).read_text())
    assert isinstance(orders, list) and orders, "book must be a non-empty list of lineups"
    seen = set()
    for lineup in orders:
        assert isinstance(lineup, list) and len(lineup) == ROSTER_SIZE, f"lineup is not {ROSTER_SIZE} players"
        assert len(set(lineup)) == ROSTER_SIZE, f"lineup has duplicate players: {lineup}"
        assert all(isinstance(p, str) and p for p in lineup), "lineup has a null or non-string id"
        key = ",".join(sorted(lineup))
        assert key not in seen, f"book contains a duplicate lineup: {key}"
        seen.add(key)
    return orders


def main(argv=None, clock=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--actuals", required=True, help="realized Sunday-main player points")
    ap.add_argument("--actuals-manifest", required=True, help="identity contract for --actuals")
    ap.add_argument("--actuals-manifest-sha256", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    # The clock is injected by tests; there is deliberately no CLI override of the gate.
    now = clock() if clock else dt.datetime.now(dt.timezone.utc)
    assert now > SETTLE_AFTER_UTC, (
        f"outcome gate: {now.isoformat()} is before the Sunday-main settle point "
        f"{SETTLE_AFTER_UTC.isoformat()}")

    got_manifest = sha(a.actuals_manifest)
    assert got_manifest == a.actuals_manifest_sha256, (
        f"actuals manifest sha256 {got_manifest} != pinned {a.actuals_manifest_sha256}")
    am = json.loads(Path(a.actuals_manifest).read_text())
    check_actuals_identity(am)
    got_actuals = sha(a.actuals)
    assert got_actuals == am["actuals_sha256"], (
        f"actuals sha256 {got_actuals} != manifest {am['actuals_sha256']}")

    out = Path(a.out)
    assert not out.exists(), f"{out} exists; this reader writes once"

    root = Path(a.bundle)
    manifest = json.loads((root / "manifest.json").read_text())
    arms = {name: load_arm(spec, root) for name, spec in manifest["arms"].items()}
    assert set(arms) == {"control", "salaryfix"}, sorted(arms)

    act = (pd.read_parquet(a.actuals) if a.actuals.endswith(".parquet")
           else pd.DataFrame(json.loads(Path(a.actuals).read_text())))
    assert act.id.notna().all(), "actuals contain null ids"
    act["id"] = act.id.astype(str)
    assert len(act) == act.id.nunique(), "actuals contain duplicate ids"
    assert act.points.notna().all(), "actuals contain null points; supply only settled rows"
    assert np.isfinite(pd.to_numeric(act.points, errors="coerce")).all(), "actuals contain non-finite points"
    realized = dict(zip(act.id, act.points.astype(float)))

    ids = {n: [str(i) for i in fr.id] for n, (fr, _) in arms.items()}
    common = sorted(set(ids["control"]) & set(ids["salaryfix"]) & set(realized))
    support = {
        "control_players": len(ids["control"]), "salaryfix_players": len(ids["salaryfix"]),
        "settled_actuals": len(realized), "scored_common_key": len(common),
        "in_frames_without_outcome": sorted((set(ids["control"]) & set(ids["salaryfix"])) - set(realized)),
        "control_only": sorted(set(ids["control"]) - set(ids["salaryfix"])),
        "salaryfix_only": sorted(set(ids["salaryfix"]) - set(ids["control"])),
        "policy": "common-key only; players absent from either arm or unsettled are excluded, never zero-imputed",
    }
    assert common, "no common-key players with settled outcomes"

    # Metadata must agree across arms for every scored player, or the frames describe different worlds.
    meta = {n: fr.set_index(fr.id.astype(str)).loc[common] for n, (fr, _) in arms.items()}
    for col in ("pos", "team", "opp"):
        mismatched = sorted(np.asarray(common)[
            (meta["control"][col].astype(str).to_numpy() != meta["salaryfix"][col].astype(str).to_numpy())])
        assert not mismatched, f"arms disagree on {col} for {mismatched[:10]}"
    support["metadata_checked"] = ["pos", "team", "opp"]

    y = np.array([realized[i] for i in common], dtype=np.float64)
    pos = meta["control"].pos.astype(str).to_numpy()
    game = np.array([f"{min(t, o)}-{max(t, o)}" for t, o in
                     zip(meta["control"].team.astype(str), meta["control"].opp.astype(str))])

    laws, rows_for = {}, {}
    for arm, (fr, banks) in arms.items():
        index = {str(pid): k for k, pid in enumerate(fr.id)}
        rows_for[arm] = index
        sel = [index[i] for i in common]
        for c in COMPONENTS:
            laws[f"{arm}_{c.split('_')[0]}"] = banks[c][sel]
        laws[f"{arm}_mixture"] = np.concatenate([banks[c][sel] for c in COMPONENTS], axis=1)

    per_player = {name: crps(s, y) for name, s in laws.items()}
    pits = {name: pit(s, y) for name, s in laws.items()}

    strata = {"overall": np.ones(len(common), dtype=bool)}
    strata.update({f"pos_{p}": pos == p for p in POSITIONS})
    if "prior_eligible_ids" in manifest:
        elig = set(json.loads(opened(manifest["prior_eligible_ids"], root).read_text()))
        strata["prior_eligible"] = np.array([i in elig for i in common])
        support["prior_eligible_supplied"] = len(elig)
        support["prior_eligible_scored"] = int(strata["prior_eligible"].sum())
    else:
        support["prior_eligible_supplied"] = None
        support["prior_eligible_note"] = "no id list in the bundle; stratum unavailable, not silently skipped"

    rng = np.random.default_rng(SEED)
    scores, contrast = {}, {}
    for sname, mask in strata.items():
        if not mask.any():
            scores[sname] = {"n": 0, "note": "no scored players in this stratum"}
            continue
        scores[sname] = {"n": int(mask.sum()),
                         "mean_crps": {k: float(v[mask].mean()) for k, v in per_player.items()},
                         "mean_pit": {k: float(v[mask].mean()) for k, v in pits.items()}}
        for arm in ("control", "salaryfix"):
            comp = np.mean([per_player[f"{arm}_{c.split('_')[0]}"][mask].mean() for c in COMPONENTS])
            scores[sname][f"{arm}_mean_of_component_crps"] = float(comp)
            scores[sname][f"{arm}_mixture_gain_over_averaging"] = float(
                comp - per_player[f"{arm}_mixture"][mask].mean())
        d = per_player["salaryfix_mixture"][mask] - per_player["control_mixture"][mask]
        contrast[sname] = cluster_bootstrap(d, game[mask], rng)
        contrast[sname]["direction"] = "negative favours the repaired law (CRPS is lower-is-better)"

    # Books: every book under EVERY law, as in the existing cross-audits. Descriptive only.
    books, entered = {}, manifest.get("entered_book")
    descriptive = {"note": ("descriptive only; overlapping lineups and a single maximum carry no interval. "
                            "Aggregated in float64, which does not reproduce the build's float32 summation order."),
                   "book_identity": ("entered book declared in the bundle manifest" if entered else
                                     "PROSPECTIVE SHADOW BOOKS: no entered-book identity supplied")}
    for arm, (fr, banks) in arms.items():
        if "book_orders" not in manifest["arms"][arm]:
            continue
        orders = load_book(manifest["arms"][arm]["book_orders"], root, ids[arm])
        expected = manifest["arms"][arm].get("expected_book_size")
        assert expected is None or len(orders) == expected, (
            f"{arm}: book has {len(orders)} lineups, manifest expects {expected}")
        books[arm] = orders
    for arm, orders in books.items():
        missing = sorted({p for o in orders for p in o} - set(realized))
        if missing:
            descriptive[arm] = {"scoreable": False, "players_without_outcome": missing}
            continue
        real = np.array([sum(realized[p] for p in o) for o in orders], dtype=np.float64)
        row = {"scoreable": True, "lineups": len(orders), "realized_max": float(real.max()),
               "is_entered_book": bool(entered == arm), "under_law": {}}
        for law_arm, (fr, banks) in arms.items():
            index = rows_for[law_arm]
            absent = sorted({p for o in orders for p in o} - set(index))
            if absent:
                row["under_law"][law_arm] = {"scoreable": False, "players_absent_from_law_frame": absent}
                continue
            pooled = np.concatenate([banks[c] for c in COMPONENTS], axis=1)
            totals = np.stack([pooled[[index[p] for p in o]].sum(axis=0, dtype=np.float64) for o in orders])
            row["under_law"][f"{law_arm}_mixture"] = {
                "mean_lineup_crps": float(crps(totals, real).mean()),
                "predicted_max_mean": float(totals.max(axis=0).mean()),
                "realized_max_crps": float(crps(totals.max(axis=0)[None, :], real.max()[None])[0]),
                "realized_max_pit": float(pit(totals.max(axis=0)[None, :], real.max()[None])[0])}
        descriptive[arm] = row

    result = dict(
        protocol="reports/2026-09-19-prospective-proper-score-protocol.md", reader_version="v2",
        scope=("Prospective CRPS comparison of frozen predictive laws on one Sunday-main slate. Scores laws, "
               "not books. Clusters are games; players and lineups are NOT independent replications. "
               "No decision rule, threshold or adoption trigger: one slate nominates nothing."),
        crps_estimator="issued empirical distribution, denominator n*n (not the fair ensemble estimator)",
        generated_utc=now.isoformat(), settle_after_utc=SETTLE_AFTER_UTC.isoformat(),
        actuals=dict(path=str(a.actuals), sha256=got_actuals, manifest_sha256=got_manifest,
                     identity={k: am.get(k) for k in ("season", "week", "draft_group", "slate", "scoring", "source")},
                     games=len(am["games"]), settled_rows=len(realized)),
        bundle=dict(path=str(root), manifest_sha256=sha(root / "manifest.json")),
        draws={k: int(v.shape[1]) for k, v in laws.items()},
        support=support, scores=scores, contrast=contrast, descriptive=descriptive,
        reader_sha256=sha(__file__))
    with out.open("x") as f:
        json.dump(result, f, indent=2, allow_nan=False, default=str)
    print(json.dumps({"scored": len(common), "clusters": contrast["overall"]["clusters"],
                      "overall_mean_crps": scores["overall"]["mean_crps"],
                      "repaired_minus_control": contrast["overall"]}, indent=2), flush=True)
    return result


if __name__ == "__main__":
    main()
