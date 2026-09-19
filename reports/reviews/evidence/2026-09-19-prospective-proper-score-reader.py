"""Outcome-gated prospective proper-score reader.

Scores the control and salary-repaired predictive laws against realized outcomes with CRPS.
Protocol: reports/2026-09-19-prospective-proper-score-protocol.md (frozen before the lock).

Scores LAWS, not books.  Clusters are games.  One slate nominates nothing.
Refuses to run before the lock, refuses an unpinned actuals artifact, writes once.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

LOCK_UTC = dt.datetime(2026, 9, 20, 17, 0, tzinfo=dt.timezone.utc)
COMPONENTS = ("I_audit", "H_audit")
POSITIONS = ("QB", "RB", "WR", "TE", "DST")
BOOTSTRAP = 10_000
MIN_CLUSTERS = 8
SEED = 20260920


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def opened(rec, root):
    """Resolve a manifest entry and verify its content hash before any read."""
    p = root / rec["path"] if not Path(rec["path"]).is_absolute() else Path(rec["path"])
    got = sha(p)
    assert got == rec["sha256"], f"{p}: sha256 {got} != manifest {rec['sha256']}"
    return p


def crps(samples, y):
    """Fair (unbiased) sample CRPS, lower is better.  samples (P, n) float, y (P,) float.

    CRPS = E|X-y| - 1/2 E|X-X'|; the second term is computed in closed form from the
    sorted sample, so cost is a sort rather than an n^2 pairwise matrix.
    """
    x = np.sort(np.asarray(samples, dtype=np.float64), axis=1)
    y = np.asarray(y, dtype=np.float64)
    n = x.shape[1]
    assert n > 1, "CRPS needs at least two draws"
    term1 = np.abs(x - y[:, None]).mean(axis=1)
    w = 2.0 * np.arange(1, n + 1) - n - 1.0          # sum_i (2i-n-1) x_(i) = sum_{i<j}(x_j-x_i)
    term2 = (x * w).sum(axis=1) / (n * (n - 1.0))    # = 1/2 E|X-X'| under the fair estimator
    return term1 - term2


def pit(samples, y):
    """Probability-integral transform of y under the empirical predictive, mid-rank convention."""
    x = np.asarray(samples, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    below = (x < y[:, None]).sum(axis=1)
    ties = (x == y[:, None]).sum(axis=1)
    return (below + 0.5 * ties) / x.shape[1]


def cluster_bootstrap(diffs, clusters, rng, b=BOOTSTRAP):
    """Resample whole games with replacement; ratio estimator handles unequal cluster sizes."""
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


def load_arm(spec, root):
    """Frame + audit banks for one arm, every artifact hash-checked, row order pinned to the frame."""
    frame = pd.read_parquet(opened(spec["frame"], root))
    assert len(frame) == frame.id.nunique(), "frame ids are not unique"
    banks = {}
    for name in COMPONENTS:
        a = np.load(opened(spec["banks"][name], root), allow_pickle=False)
        assert a.dtype == np.float32 and a.shape[0] == len(frame) and np.isfinite(a).all(), name
        banks[name] = a
    widths = {b.shape[1] for b in banks.values()}
    assert len(widths) == 1, f"audit banks disagree on draw count: {widths}"
    return frame, banks


def laws_for(arm, frame, banks, rows):
    """Six laws.  The mixture is the POOLED sample, not the mean of component scores:
    CRPS is convex in F, so CRPS(mixture) <= mean of component CRPS, and only the pooled
    sample represents dual_emax's equal-mass concatenation."""
    out = {f"{arm}_{c.split('_')[0]}": banks[c][rows] for c in COMPONENTS}
    out[f"{arm}_mixture"] = np.concatenate([banks[c][rows] for c in COMPONENTS], axis=1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True, help="directory holding manifest.json and artifacts")
    ap.add_argument("--actuals", required=True, help="parquet/json of realized player points")
    ap.add_argument("--actuals-sha256", required=True, help="pinned hash of --actuals")
    ap.add_argument("--out", required=True)
    ap.add_argument("--now", default=None, help="ISO instant, for tests only; defaults to wall clock")
    a = ap.parse_args()

    now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    assert now > LOCK_UTC, f"outcome gate: {now.isoformat()} is before the lock {LOCK_UTC.isoformat()}"
    got = sha(a.actuals)
    assert got == a.actuals_sha256, f"actuals sha256 {got} != pinned {a.actuals_sha256}"
    out = Path(a.out)
    assert not out.exists(), f"{out} exists; this reader writes once"

    root = Path(a.bundle)
    manifest = json.loads((root / "manifest.json").read_text())
    arms = {name: load_arm(spec, root) for name, spec in manifest["arms"].items()}
    assert set(arms) == {"control", "salaryfix"}, sorted(arms)

    act = (pd.read_parquet(a.actuals) if a.actuals.endswith(".parquet")
           else pd.DataFrame(json.loads(Path(a.actuals).read_text())))
    act["id"] = act.id.astype(str)
    assert len(act) == act.id.nunique(), "actuals contain duplicate ids"
    assert act.points.notna().all(), "actuals contain null points; supply only settled rows"
    realized = dict(zip(act.id, act.points.astype(float)))

    # Common-key universe: scored players must exist in BOTH arms and have a settled outcome.
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

    y = np.array([realized[i] for i in common], dtype=np.float64)
    meta = arms["control"][0].set_index(arms["control"][0].id.astype(str)).loc[common]
    pos = meta.pos.astype(str).to_numpy()
    game = np.array([f"{min(t, o)}-{max(t, o)}" for t, o in zip(meta.team.astype(str), meta.opp.astype(str))])

    laws = {}
    for arm, (fr, banks) in arms.items():
        index = {str(pid): k for k, pid in enumerate(fr.id)}
        laws.update(laws_for(arm, fr, banks, [index[i] for i in common]))

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
        # Convexity check: the pooled mixture must not score worse than its components' mean.
        for arm in ("control", "salaryfix"):
            comp = np.mean([per_player[f"{arm}_{c.split('_')[0]}"][mask].mean() for c in COMPONENTS])
            scores[sname][f"{arm}_mean_of_component_crps"] = float(comp)
            scores[sname][f"{arm}_mixture_gain_over_averaging"] = float(
                comp - per_player[f"{arm}_mixture"][mask].mean())
        d = per_player["salaryfix_mixture"][mask] - per_player["control_mixture"][mask]
        contrast[sname] = cluster_bootstrap(d, game[mask], rng)
        contrast[sname]["direction"] = "negative favours the repaired law (CRPS is lower-is-better)"

    # Descriptive only: entered lineups and the book maximum.  Heavily overlapping, n=1 for the max.
    descriptive = {"note": "descriptive only; overlapping lineups and a single maximum carry no interval"}
    for arm, (fr, banks) in arms.items():
        if "book_orders" in manifest["arms"][arm]:
            orders = json.loads(opened(manifest["arms"][arm]["book_orders"], root).read_text())
            index = {str(pid): k for k, pid in enumerate(fr.id)}
            missing = sorted({p for o in orders for p in o} - set(realized))
            if missing:
                descriptive[arm] = {"scoreable": False, "players_without_outcome": missing}
                continue
            pooled = np.concatenate([banks[c] for c in COMPONENTS], axis=1)
            totals = np.stack([pooled[[index[p] for p in o]].sum(axis=0, dtype=np.float64) for o in orders])
            real = np.array([sum(realized[p] for p in o) for o in orders], dtype=np.float64)
            descriptive[arm] = {
                "scoreable": True, "lineups": len(orders),
                "mean_lineup_crps_mixture": float(crps(totals, real).mean()),
                "realized_max": float(real.max()),
                "predicted_max_mean": float(totals.max(axis=0).mean()),
                "realized_max_crps": float(crps(totals.max(axis=0)[None, :], real.max()[None])[0]),
                "realized_max_pit": float(pit(totals.max(axis=0)[None, :], real.max()[None])[0]),
            }

    result = dict(
        protocol="reports/2026-09-19-prospective-proper-score-protocol.md",
        scope=("Prospective CRPS comparison of frozen predictive laws on one slate. Scores laws, not books. "
               "Clusters are games; players and lineups are NOT independent replications. "
               "No decision rule, threshold or adoption trigger: one slate nominates nothing."),
        generated_utc=now.isoformat(), lock_utc=LOCK_UTC.isoformat(),
        actuals=dict(path=str(a.actuals), sha256=got, settled_rows=len(realized)),
        bundle=dict(path=str(root), manifest_sha256=sha(root / "manifest.json")),
        draws={k: int(v.shape[1]) for k, v in laws.items()},
        support=support, scores=scores, contrast=contrast, descriptive=descriptive,
        reader_sha256=sha(__file__))
    with out.open("x") as f:
        json.dump(result, f, indent=2, allow_nan=False, default=str)
    print(json.dumps({"scored": len(common), "clusters": contrast["overall"]["clusters"],
                      "overall_mean_crps": scores["overall"]["mean_crps"],
                      "repaired_minus_control": contrast["overall"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
