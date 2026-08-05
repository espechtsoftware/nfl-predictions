"""Foundation-model challenger shadow benchmark (Workstream F).

Implements plan §10.2 / §10.3 / §16.7 (reports/emerging-technologies-plan.md):
a walk-forward benchmark on per-week player usage sequences (targets or
carries per week) comparing simple sequence baselines against
time-series foundation-model challengers. Foundation outputs do not
enter production unless they beat these baselines walk-forward (§10.2),
with cold-start populations examined separately (§10.3) — hence the
by-history-length breakdown.

Baselines (all implemented here):
  last      last observed value
  roll4     rolling mean of the last 4 observations
  ewm       exponentially weighted mean (halflife 3)
  kalman    local-level state-space filter (random-walk level + obs
            noise; signal-to-noise chosen per series by one-step-ahead
            Gaussian log-likelihood on history only)

Challenger slots:
  chronos   amazon/chronos-bolt-tiny via `pip install chronos-forecasting`,
            CPU. Only imported when requested (--challengers chronos);
            install/download failures are reported verbatim as
            UNAVAILABLE, never silently skipped.
  tabfm     NOT a sequence model — access status is reported by
            `--availability` (see TABFM_STATUS); its benchmark belongs
            to plan §10.1 on tabular player-week rows, out of scope here.

Metrics: MAE on the median forecast plus pinball loss at q10/q50/q90,
overall and by history length (1-2, 3-5, 6-10, 11+ weeks of history).

Modes:
  --mode synthetic          fully offline synthetic usage sequences (default)
  --mode csv --csv PATH     real sequences later; CSV needs columns
                            player_id, y and either t or season,week
                            (sorted per player by t or (season, week))

Examples:
  python scripts/foundation_shadow.py                       # baselines, synthetic
  python scripts/foundation_shadow.py --challengers chronos # + chronos if usable
  python scripts/foundation_shadow.py --availability        # challenger status only
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np
import pandas as pd

QUANTS = (0.1, 0.5, 0.9)
Z = {0.1: -1.2816, 0.5: 0.0, 0.9: 1.2816}
HISTORY_BUCKETS = ((1, 2), (3, 5), (6, 10), (11, 10**9))

# Status of the TabFM challenger, checked 2026-08-05 (plan §10.1 slot —
# tabular, not sequence, so it is *reported* here but benchmarked in the
# TabFM workstream): pip package `tabfm` exists (v1.0.1, Google Research,
# https://github.com/google-research/tabfm), JAX-based with optional
# torch/cuda extras; weights fetched via huggingface-hub at runtime. So:
# pip-accessible, no special API key documented, GPU optional.
TABFM_STATUS = (
    "AVAILABLE via pip (`pip install tabfm`, v1.0.1, google-research/tabfm, "
    "JAX + huggingface-hub weights) — tabular model, benchmark belongs to "
    "plan §10.1, not this sequence harness"
)


# ---------------------------------------------------------------------------
# Synthetic sequences (offline; used by tests)
# ---------------------------------------------------------------------------

def synthetic_usage_sequences(
    n_players: int = 60, n_weeks: int = 34, seed: int = 7
) -> pd.DataFrame:
    """Weekly usage counts (targets/carries) with the plan's §10.2 realities:
    role tiers, slow drift, mid-history role changes, and missed-game zeros."""
    rng = np.random.default_rng(seed)
    rows = []
    tiers = np.array([16.0, 8.0, 4.0])  # bell-cow / committee / satellite
    for p in range(n_players):
        rate = tiers[p % 3] * rng.uniform(0.8, 1.2)
        can_shift = n_weeks > 6 and rng.random() < 0.3
        shift_week = rng.integers(6, n_weeks) if can_shift else None
        for t in range(1, n_weeks + 1):
            rate = max(0.5, rate + rng.normal(0, 0.35))
            if shift_week is not None and t == shift_week:
                rate = max(0.5, rate * rng.choice([0.4, 1.8]))  # role change
            missed = rng.random() < 0.06  # inactive/bye: a true zero week
            y = 0 if missed else rng.poisson(rate)
            rows.append({"player_id": f"P{p:03d}", "t": t, "y": int(y)})
    return pd.DataFrame(rows)


def load_csv_sequences(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "player_id" not in df.columns or "y" not in df.columns:
        raise SystemExit("CSV needs columns: player_id, y, and t or season+week")
    if "t" in df.columns:
        df = df.sort_values(["player_id", "t"])
    elif {"season", "week"}.issubset(df.columns):
        df = df.sort_values(["player_id", "season", "week"])
        df["t"] = df.groupby("player_id").cumcount() + 1
    else:
        raise SystemExit("CSV needs an ordering: column t, or season+week")
    return df[["player_id", "t", "y"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Baseline forecasters: history -> (q10, q50, q90). History is strictly
# the past (walk-forward); each returns monotone quantiles, floored at 0.
# ---------------------------------------------------------------------------

def _spread_quantiles(point: float, sd: float) -> tuple[float, float, float]:
    sd = float(max(sd, 0.75))  # count data: never claim near-zero spread
    q = tuple(max(0.0, point + Z[lvl] * sd) for lvl in QUANTS)
    return (min(q[0], q[1]), q[1], max(q[2], q[1]))


def _trailing_sd(h: np.ndarray) -> float:
    if len(h) >= 3:
        return float(np.std(np.diff(h), ddof=1)) / np.sqrt(2) * 1.5
    return float(np.std(h, ddof=0)) if len(h) > 1 else max(1.0, 0.5 * abs(h[-1]))


def forecast_last(h: np.ndarray) -> tuple[float, float, float]:
    return _spread_quantiles(float(h[-1]), _trailing_sd(h))


def forecast_rolling(h: np.ndarray, k: int = 4) -> tuple[float, float, float]:
    return _spread_quantiles(float(np.mean(h[-k:])), _trailing_sd(h))


def forecast_ewm(h: np.ndarray, halflife: float = 3.0) -> tuple[float, float, float]:
    w = 0.5 ** (np.arange(len(h) - 1, -1, -1) / halflife)
    point = float(np.sum(w * h) / np.sum(w))
    var = float(np.sum(w * (h - point) ** 2) / np.sum(w)) if len(h) > 1 else 1.0
    return _spread_quantiles(point, np.sqrt(max(var, 0.25)))


def forecast_kalman(h: np.ndarray) -> tuple[float, float, float]:
    """Local-level model: level_t = level_{t-1} + eta, y_t = level_t + eps.
    The signal-to-noise ratio q = var(eta)/var(eps) is picked per series
    by one-step-ahead log-likelihood over a small grid — history only."""
    if len(h) < 3:
        return forecast_last(h)
    r = max(float(np.var(np.diff(h))) / 2.0, 0.25)  # obs-noise heuristic
    best = (-np.inf, None)
    for q_ratio in (0.01, 0.05, 0.15, 0.5, 1.5):
        m, pvar = float(h[0]), r
        ll = 0.0
        for y in h[1:]:
            pvar_pred = pvar + q_ratio * r
            f = pvar_pred + r  # one-step predictive variance
            ll += -0.5 * (np.log(2 * np.pi * f) + (y - m) ** 2 / f)
            k = pvar_pred / f
            m = m + k * (y - m)
            pvar = (1 - k) * pvar_pred
        if ll > best[0]:
            best = (ll, (m, pvar + q_ratio * r + r))
    m, fvar = best[1]
    return _spread_quantiles(float(m), float(np.sqrt(fvar)))


BASELINES: dict[str, Callable[[np.ndarray], tuple[float, float, float]]] = {
    "last": forecast_last,
    "roll4": forecast_rolling,
    "ewm": forecast_ewm,
    "kalman": forecast_kalman,
}


# ---------------------------------------------------------------------------
# Chronos challenger (guarded import — tests never touch this path)
# ---------------------------------------------------------------------------

def chronos_availability() -> tuple[bool, str]:
    """Try to load the smallest chronos model on CPU; report exactly."""
    try:
        from chronos import BaseChronosPipeline  # noqa: F401
    except Exception as e:  # ImportError or anything transitive
        return False, f"UNAVAILABLE — import failed: {type(e).__name__}: {e}"
    try:
        _load_chronos()
    except Exception as e:
        return False, f"UNAVAILABLE — model load failed: {type(e).__name__}: {e}"
    return True, "AVAILABLE — chronos-forecasting, amazon/chronos-bolt-tiny, CPU"


_CHRONOS = None


def _load_chronos():
    global _CHRONOS
    if _CHRONOS is None:
        from chronos import BaseChronosPipeline

        _CHRONOS = BaseChronosPipeline.from_pretrained(
            "amazon/chronos-bolt-tiny", device_map="cpu"
        )
    return _CHRONOS


def chronos_predict_batch(histories: list[np.ndarray]) -> np.ndarray:
    """One-step-ahead q10/q50/q90 for a batch of histories -> (n, 3)."""
    import torch

    pipe = _load_chronos()
    ctx = [torch.tensor(h, dtype=torch.float32) for h in histories]
    q, _mean = pipe.predict_quantiles(ctx, prediction_length=1, quantile_levels=list(QUANTS))
    out = q[:, 0, :].numpy()  # (n, 3)
    out = np.maximum(out, 0.0)
    out.sort(axis=1)  # enforce monotone quantiles
    return out


# ---------------------------------------------------------------------------
# Walk-forward harness
# ---------------------------------------------------------------------------

@dataclass
class Prediction:
    method: str
    player_id: str
    t: int
    hist_len: int
    y: float
    q10: float
    q50: float
    q90: float


def run_walk_forward(
    df: pd.DataFrame, challengers: Sequence[str] = ()
) -> tuple[pd.DataFrame, dict[str, str]]:
    """For every series and every week t with >= 1 week of history,
    forecast y_t from y_{<t} only. Returns (predictions, challenger notes)."""
    notes: dict[str, str] = {}
    series = {
        pid: g.sort_values("t")["y"].to_numpy(dtype=float)
        for pid, g in df.groupby("player_id")
    }
    preds: list[Prediction] = []
    for pid, ys in series.items():
        for t in range(1, len(ys)):
            h = ys[:t]
            for name, fn in BASELINES.items():
                q10, q50, q90 = fn(h)
                preds.append(Prediction(name, pid, t + 1, t, float(ys[t]), q10, q50, q90))

    use_chronos = "chronos" in challengers
    if use_chronos:
        ok, msg = chronos_availability()
        notes["chronos"] = msg
        if ok:
            # Batch by target index t so contexts share a call.
            max_t = max(len(v) for v in series.values())
            for t in range(1, max_t):
                pids = [p for p, v in series.items() if len(v) > t]
                hists = [series[p][:t] for p in pids]
                q = chronos_predict_batch(hists)
                for i, p in enumerate(pids):
                    preds.append(
                        Prediction(
                            "chronos", p, t + 1, t, float(series[p][t]),
                            float(q[i, 0]), float(q[i, 1]), float(q[i, 2]),
                        )
                    )
    notes.setdefault("chronos", "not requested (pass --challengers chronos)")
    notes["tabfm"] = TABFM_STATUS
    return pd.DataFrame([p.__dict__ for p in preds]), notes


def pinball(y: np.ndarray, q: np.ndarray, level: float) -> float:
    d = y - q
    return float(np.mean(np.maximum(level * d, (level - 1) * d)))


def summarize(preds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    buckets = [("all", 1, 10**9)] + [
        (f"h{lo}-{hi if hi < 10**9 else '+'}", lo, hi) for lo, hi in HISTORY_BUCKETS
    ]
    for method, g in preds.groupby("method"):
        for name, lo, hi in buckets:
            m = g[(g.hist_len >= lo) & (g.hist_len <= hi)]
            if not len(m):
                continue
            y = m.y.to_numpy()
            rows.append({
                "method": method,
                "bucket": name,
                "n": len(m),
                "mae": float(np.mean(np.abs(y - m.q50.to_numpy()))),
                "pinball10": pinball(y, m.q10.to_numpy(), 0.1),
                "pinball50": pinball(y, m.q50.to_numpy(), 0.5),
                "pinball90": pinball(y, m.q90.to_numpy(), 0.9),
            })
    out = pd.DataFrame(rows)
    return out.sort_values(["bucket", "mae"]).reset_index(drop=True)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=("synthetic", "csv"), default="synthetic")
    ap.add_argument("--csv", help="CSV path for --mode csv")
    ap.add_argument("--challengers", nargs="*", default=[],
                    choices=("chronos",), help="challenger slots to attempt")
    ap.add_argument("--players", type=int, default=60)
    ap.add_argument("--weeks", type=int, default=34)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--json-out", help="write the summary table as JSON here")
    ap.add_argument("--availability", action="store_true",
                    help="only report challenger availability and exit")
    args = ap.parse_args(argv)

    if args.availability:
        ok, msg = chronos_availability()
        print(f"chronos: {msg}")
        print(f"tabfm:   {TABFM_STATUS}")
        return 0

    if args.mode == "csv":
        if not args.csv:
            ap.error("--mode csv requires --csv PATH")
        df = load_csv_sequences(args.csv)
    else:
        df = synthetic_usage_sequences(args.players, args.weeks, args.seed)

    preds, notes = run_walk_forward(df, challengers=args.challengers)
    table = summarize(preds)

    print(f"\nWalk-forward usage-sequence benchmark ({args.mode}, "
          f"{df.player_id.nunique()} series, {len(preds)} predictions)")
    print(table.to_string(index=False,
                          float_format=lambda v: f"{v:.3f}"))
    print("\nChallenger availability:")
    for k, v in notes.items():
        print(f"  {k}: {v}")
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump({"summary": table.to_dict("records"), "notes": notes}, f, indent=2)
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
