"""Online conformal calibration and risk control (Workstream E).

Implements plan §9 / §16.6 (reports/emerging-technologies-plan.md):

- **Append-only calibration state** (§9.5): an ordered log of
  ``(timestamp, group labels, nonconformity score)`` records. Records are
  only ever appended, never edited or reordered; timestamps must be
  non-decreasing so the state used for an earlier slate is reproducible
  by truncation. ``fingerprint(n)`` hashes the first-n prefix so tests
  and audits can prove no retroactive alteration.
- **Mondrian groups with a declared fallback hierarchy** (§9.4):
  each record carries labels (e.g. position, role class). Quantile
  lookups resolve through a declared hierarchy — by default
  position -> role_class -> global — skipping any level with fewer than
  ``min_group_size`` scores.
- **Adaptive conformal update** (§9.5), Gibbs & Candès ACI style:
  after each outcome, the per-group miscoverage level alpha_t receives
  coverage-error feedback ``alpha += lr * (alpha_target - err_t)``, so
  sustained under-coverage drives intervals wider and vice versa.
- **Conformal risk control** (§9.7): ``conformal_risk_control`` chooses
  a monotone control parameter (e.g. a distribution scale) against a
  registered bounded loss using the CRC bound
  ``(n * Rhat(lambda) + B) / (n + 1) <= target``.

Guarantee statement (per §9.7's honesty requirement): the ACI update
targets *long-run marginal* coverage per resolved group under the online
protocol — it is not a per-slate or conditional guarantee, and a
marginal per-player guarantee says nothing about a selected portfolio.
CRC's bound holds under exchangeability of the calibration losses with
the deployment loss.

Application is order-preserving (§9.6): corrections widen or narrow the
(q_lo, q_hi) quantiles around the median and never let them cross it.
This module is offline research code — nothing imports BigQuery and no
production path calls it yet (wiring plan lives in the workstream
report, not here).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np

GLOBAL_LEVEL = "global"
DEFAULT_HIERARCHY: tuple[str, ...] = ("position", "role_class")
# ACI's alpha_t is clipped to keep the empirical quantile well defined.
_ALPHA_MIN, _ALPHA_MAX = 1e-3, 0.5


def interval_score(y: float, q_lo: float, q_hi: float) -> float:
    """CQR nonconformity score (Romano et al.): max(q_lo - y, y - q_hi).

    Positive when y falls outside [q_lo, q_hi]; the (1 - alpha) quantile
    of these scores is the additive widening that restores coverage.
    """
    return float(max(q_lo - y, y - q_hi))


@dataclass(frozen=True)
class CalibrationRecord:
    """One immutable calibration observation."""

    timestamp: str  # lexicographically sortable, e.g. "2026-09-14" or "2026w02"
    labels: tuple[tuple[str, str], ...]  # sorted (level, value) pairs
    score: float

    @staticmethod
    def make(timestamp: str, labels: Mapping[str, str], score: float) -> "CalibrationRecord":
        items = tuple(sorted((str(k), str(v)) for k, v in labels.items()))
        return CalibrationRecord(str(timestamp), items, float(score))

    def label(self, level: str) -> str | None:
        for k, v in self.labels:
            if k == level:
                return v
        return None


class CalibrationState:
    """Append-only log of calibration records.

    Invariants (enforced):
    - records are only appended, never mutated or removed;
    - timestamps are non-decreasing (point-in-time discipline: the state
      as of an earlier slate is exactly a prefix of the current state).
    """

    def __init__(self, records: Iterable[CalibrationRecord] = ()) -> None:
        self._records: list[CalibrationRecord] = []
        for r in records:
            self._append(r)

    # -- append-only surface -------------------------------------------------
    def append(self, timestamp: str, labels: Mapping[str, str], score: float) -> CalibrationRecord:
        rec = CalibrationRecord.make(timestamp, labels, score)
        self._append(rec)
        return rec

    def _append(self, rec: CalibrationRecord) -> None:
        if self._records and rec.timestamp < self._records[-1].timestamp:
            raise ValueError(
                f"append-only state: timestamp {rec.timestamp!r} precedes "
                f"last recorded {self._records[-1].timestamp!r}"
            )
        self._records.append(rec)

    @property
    def records(self) -> tuple[CalibrationRecord, ...]:
        """Immutable view; there is deliberately no setter or delete."""
        return tuple(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def fingerprint(self, n: int | None = None) -> str:
        """SHA-256 of the first-n records; proves prefixes never change."""
        upto = len(self._records) if n is None else n
        payload = json.dumps(
            [(r.timestamp, r.labels, r.score) for r in self._records[:upto]],
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(payload).hexdigest()

    # -- lookups -------------------------------------------------------------
    def scores_for(self, level: str, value: str | None, max_window: int | None = None) -> np.ndarray:
        """Scores whose labels match (level, value); GLOBAL_LEVEL matches all.

        ``max_window`` keeps only the most recent scores (recency
        weighting per §9.5, drift response)."""
        if level == GLOBAL_LEVEL:
            picked = [r.score for r in self._records]
        else:
            picked = [r.score for r in self._records if r.label(level) == value]
        if max_window is not None:
            picked = picked[-max_window:]
        return np.asarray(picked, dtype=float)

    # -- persistence (state must survive across slates, §9.5) ---------------
    def to_json(self) -> str:
        return json.dumps(
            [
                {"timestamp": r.timestamp, "labels": list(map(list, r.labels)), "score": r.score}
                for r in self._records
            ]
        )

    @classmethod
    def from_json(cls, payload: str) -> "CalibrationState":
        rows = json.loads(payload)
        return cls(
            CalibrationRecord(
                r["timestamp"], tuple((k, v) for k, v in r["labels"]), float(r["score"])
            )
            for r in rows
        )


@dataclass(frozen=True)
class CorrectedInterval:
    """An issued interval plus full provenance for monitoring (§9.5)."""

    lo: float
    mid: float
    hi: float
    delta: float          # additive widening applied to each side
    level: str            # hierarchy level actually used ("none" = no data)
    group_value: str | None
    n_scores: int         # effective calibration sample size
    alpha: float          # miscoverage level in force for that group


class OnlineConformalCalibrator:
    """Mondrian online conformal correction of predictive quantiles.

    Protocol per observation (a scored player-week):

    1. ``interval(labels, q_lo, q_mid, q_hi)`` -> corrected interval,
       using the current state and the group's adapted alpha.
    2. Once the outcome is known, ``update(labels, y, ...)`` records the
       nonconformity score (append-only) and applies the ACI feedback
       ``alpha += lr * (alpha_target - err)`` at every hierarchy level
       that matched, so fallback levels also stay adapted.
    """

    def __init__(
        self,
        target_coverage: float = 0.9,
        learning_rate: float = 0.05,
        min_group_size: int = 30,
        hierarchy: Sequence[str] = DEFAULT_HIERARCHY,
        max_window: int | None = 2000,
        state: CalibrationState | None = None,
    ) -> None:
        if not 0.5 < target_coverage < 1.0:
            raise ValueError("target_coverage must be in (0.5, 1)")
        self.target_coverage = float(target_coverage)
        self.alpha_target = 1.0 - self.target_coverage
        self.learning_rate = float(learning_rate)
        self.min_group_size = int(min_group_size)
        self.hierarchy = tuple(hierarchy)
        self.max_window = max_window
        self.state = state if state is not None else CalibrationState()
        # alpha per (level, value) key, including the global key.
        self._alpha: dict[tuple[str, str], float] = {}

    # -- group resolution ----------------------------------------------------
    def group_chain(self, labels: Mapping[str, str]) -> list[tuple[str, str]]:
        """Declared fallback chain, most specific first, global last."""
        chain = [(lvl, str(labels[lvl])) for lvl in self.hierarchy if lvl in labels]
        chain.append((GLOBAL_LEVEL, GLOBAL_LEVEL))
        return chain

    def resolve(self, labels: Mapping[str, str]) -> tuple[str, str | None, np.ndarray]:
        """First hierarchy level with >= min_group_size scores; else ("none")."""
        for level, value in self.group_chain(labels):
            scores = self.state.scores_for(level, value, self.max_window)
            if len(scores) >= self.min_group_size:
                return level, value, scores
        return "none", None, np.empty(0)

    def alpha_for(self, level: str, value: str | None) -> float:
        return self._alpha.get((level, value or ""), self.alpha_target)

    # -- correction ----------------------------------------------------------
    def interval(self, labels: Mapping[str, str], q_lo: float, q_mid: float, q_hi: float) -> CorrectedInterval:
        if not q_lo <= q_mid <= q_hi:
            raise ValueError("raw quantiles must satisfy q_lo <= q_mid <= q_hi")
        level, value, scores = self.resolve(labels)
        alpha = self.alpha_for(level, value)
        if len(scores) == 0:
            # No usable group anywhere: pass raw quantiles through unchanged.
            return CorrectedInterval(q_lo, q_mid, q_hi, 0.0, level, value, 0, alpha)
        delta = _conformal_quantile(scores, 1.0 - alpha)
        # Order-preserving application (§9.6): widen/narrow both sides,
        # never crossing the median.
        lo = min(q_mid, q_lo - delta)
        hi = max(q_mid, q_hi + delta)
        return CorrectedInterval(lo, q_mid, hi, delta, level, value, len(scores), alpha)

    # -- online update (ACI, Gibbs & Candès) ---------------------------------
    def update(
        self,
        labels: Mapping[str, str],
        y: float,
        q_lo: float,
        q_mid: float,
        q_hi: float,
        timestamp: str,
    ) -> tuple[CorrectedInterval, bool]:
        """Score an outcome: issue interval, log score, adapt alpha.

        Returns (issued interval, covered)."""
        issued = self.interval(labels, q_lo, q_mid, q_hi)
        covered = issued.lo <= y <= issued.hi
        err = 0.0 if covered else 1.0
        for key in self.group_chain(labels):
            level, value = key
            cur = self._alpha.get((level, value), self.alpha_target)
            nxt = cur + self.learning_rate * (self.alpha_target - err)
            self._alpha[(level, value)] = float(np.clip(nxt, _ALPHA_MIN, _ALPHA_MAX))
        self.state.append(timestamp, labels, interval_score(y, q_lo, q_hi))
        return issued, covered


def _conformal_quantile(scores: np.ndarray, level: float) -> float:
    """Finite-sample conformal quantile: the ceil((n+1)*level)/n empirical
    quantile of the scores (max score when the rank exceeds n)."""
    n = len(scores)
    level = float(np.clip(level, 0.0, 1.0))
    rank = math.ceil((n + 1) * level)
    if rank > n:
        return float(np.max(scores))
    s = np.sort(scores)
    return float(s[rank - 1])


# ---------------------------------------------------------------------------
# Conformal risk control (§9.7)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RiskControlResult:
    chosen: float          # the selected control-parameter value
    chosen_index: int
    achieved_bound: float  # CRC upper bound at the chosen value
    satisfied: bool        # False => even the most conservative value fails
    risks: tuple[float, ...]  # empirical mean loss per candidate value


def conformal_risk_control(
    lambdas: Sequence[float],
    loss_matrix: np.ndarray,
    target_risk: float,
    loss_bound: float = 1.0,
    monotone_tol: float = 1e-9,
) -> RiskControlResult:
    """Choose the least-conservative monotone knob meeting a risk target.

    ``lambdas`` must be ordered from least to most conservative, so the
    registered per-sample loss (rows of ``loss_matrix``, shape
    ``(n_samples, len(lambdas))``, each value in [0, loss_bound]) has
    non-increasing mean along the columns — this monotonicity is what
    the CRC guarantee rides on, so it is *checked*, not assumed.

    Selection: the first lambda whose CRC bound
    ``(n * Rhat + loss_bound) / (n + 1)`` is <= target_risk. If none
    qualifies, the most conservative lambda is returned with
    ``satisfied=False`` — callers must treat that as "no guarantee".
    """
    lam = np.asarray(lambdas, dtype=float)
    losses = np.asarray(loss_matrix, dtype=float)
    if losses.ndim != 2 or losses.shape[1] != len(lam):
        raise ValueError("loss_matrix must be (n_samples, len(lambdas))")
    if len(lam) == 0 or losses.shape[0] == 0:
        raise ValueError("need at least one lambda and one loss sample")
    if np.any(losses < -monotone_tol) or np.any(losses > loss_bound + monotone_tol):
        raise ValueError(f"losses must lie in [0, {loss_bound}]")
    risks = losses.mean(axis=0)
    if np.any(np.diff(risks) > monotone_tol):
        raise ValueError(
            "registered loss is not monotone non-increasing over the lambda "
            "grid; conformal risk control does not apply — fix the "
            "parameterization or the ordering"
        )
    n = losses.shape[0]
    bounds = (n * risks + loss_bound) / (n + 1)
    ok = np.nonzero(bounds <= target_risk)[0]
    if len(ok):
        i = int(ok[0])
        return RiskControlResult(float(lam[i]), i, float(bounds[i]), True, tuple(risks))
    i = len(lam) - 1
    return RiskControlResult(float(lam[i]), i, float(bounds[i]), False, tuple(risks))


def tail_overstatement_loss(claimed_tail_p: np.ndarray, exceeded: np.ndarray) -> np.ndarray:
    """Registered loss for §9.7's first example: overstatement of a
    player's upper-tail probability, max(0, p_hat - 1{y > threshold}).
    Bounded in [0, 1] and monotone in any knob that only shrinks p_hat."""
    p = np.asarray(claimed_tail_p, dtype=float)
    ind = np.asarray(exceeded, dtype=float)
    return np.maximum(0.0, p - ind)


def scale_knob_tail_losses(
    mu: np.ndarray,
    sigma: np.ndarray,
    threshold: float,
    y: np.ndarray,
    scales: Sequence[float],
) -> np.ndarray:
    """Build the CRC loss matrix for the concrete knob "distribution
    scale": claimed tail prob under Normal(mu, sigma * scale) versus the
    realized exceedance. ``scales`` must be ordered descending (shrinking
    the claimed tail = more conservative) so the mean loss is
    non-increasing, as `conformal_risk_control` requires."""
    from scipy.stats import norm

    mu = np.asarray(mu, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    y = np.asarray(y, dtype=float)
    exceeded = (y > threshold).astype(float)
    cols = []
    for s in scales:
        p_hat = norm.sf(threshold, loc=mu, scale=sigma * float(s))
        cols.append(tail_overstatement_loss(p_hat, exceeded))
    return np.column_stack(cols)
