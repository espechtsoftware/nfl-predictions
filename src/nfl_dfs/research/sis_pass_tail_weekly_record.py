"""SIS pass-tail weekly decision record (O-3 Amendment 1, frozen 2026-10-05).

The frozen 2026-09-22 pass bar decides only on BOOK maxima at the 194 line
(criteria 1-4), calibrated on the August boom-40 generation. Amendment 1 moves
the books to the current money path, so that bar ends unadjudicated, and both
parts of the pair are read here instead, under adoption track v2:

* DISTRIBUTION (the two TabPFN caches, exactly as frozen): per player-week the
  quantile score QS = 2 * mean over the 13 registered levels of the pinball
  loss (a discrete CRPS), treatment minus control, on Sunday-main QB/WR/TE
  player-weeks with an active outcome. Week statistic D_w = mean difference
  (negative = the SIS treatment is better). RB and each position: reported.
* BOOKS (companion, current money path): per registered seed pair the realized
  maximum of each exact-80 book; week statistic L_w = mean over the five seeds
  of (treatment max - control max) (positive = better). Clears at
  187/194/200/210/220/230/240: reported, never decisive.

Decision (each part separately, week-clustered): with n complete weeks,
t = mean / (sd / sqrt(n)), Student t with n-1 df. One interim look after Week
11 is scored (needs n >= 7; two-sided 0.001) and the final read after Week 18
(needs the 10-week floor; two-sided 0.05). BETTER / WORSE when |t| clears the
look's critical value with that sign -- and, at the final read, BETTER also
needs every leave-one-week-out mean to keep the sign. Otherwise NO DIFFERENCE;
below the floor, NO VERDICT. Weekly values are displayed as they land and are
descriptive (adoption track v2 section 3); only these two looks decide.

Pure functions only: the inputs (caches, actuals, manifests, DK points) are
read by the caller under the settled-slate gate.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats

QUANTILE_LEVELS = (0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
                   0.60, 0.70, 0.80, 0.90, 0.95, 0.99)
QUANTILE_COLUMNS = tuple(f"q{int(level * 100):02d}" for level in QUANTILE_LEVELS)
PRIMARY_POSITIONS = ("QB", "WR", "TE")
REPORTED_LINES = (187, 194, 200, 210, 220, 230, 240)
FLOOR_WEEKS = 10
INTERIM_AFTER_WEEK = 11
INTERIM_MIN_WEEKS = 7
INTERIM_ALPHA = 0.001
FINAL_ALPHA = 0.05
COMPANION_CONTRACT = "pass-tail-v1-a1-companion"


def quantile_score(quantiles: pd.DataFrame, outcome: pd.Series) -> pd.Series:
    """2 x mean pinball loss over the registered levels (a discrete CRPS)."""
    y = pd.to_numeric(outcome, errors="raise").to_numpy(float)
    total = np.zeros(len(y))
    for level, column in zip(QUANTILE_LEVELS, QUANTILE_COLUMNS):
        q = pd.to_numeric(quantiles[column], errors="raise").to_numpy(float)
        diff = y - q
        total += np.maximum(level * diff, (level - 1.0) * diff)
    return pd.Series(2.0 * total / len(QUANTILE_LEVELS), index=quantiles.index)


def distribution_week(
    control: pd.DataFrame, treatment: pd.DataFrame, outcomes: pd.DataFrame,
) -> dict:
    """One week's paired distribution score (treatment - control)."""
    keys = ["season", "week", "gsis_id"]
    need = {*keys, *QUANTILE_COLUMNS}
    for name, frame in (("control", control), ("treatment", treatment)):
        if missing := need - set(frame.columns):
            raise ValueError(f"{name} cache lacks {sorted(missing)}")
        if frame.duplicated(keys).any():
            raise ValueError(f"{name} cache repeats player-week keys")
    if missing := {*keys, "position", "dk_points", "was_active"} - set(outcomes.columns):
        raise ValueError(f"outcomes lack {sorted(missing)}")
    if outcomes.duplicated(keys).any():
        raise ValueError("outcomes repeat player-week keys")
    left = control.set_index(keys)
    right = treatment.set_index(keys)
    if not left.index.sort_values().equals(right.index.sort_values()):
        raise ValueError("the two caches cover different player-weeks")
    scored = outcomes[outcomes.was_active.fillna(False).astype(bool)
                      & outcomes.dk_points.notna()].set_index(keys)
    common = left.index.intersection(scored.index)
    qs_c = quantile_score(left.loc[common, list(QUANTILE_COLUMNS)],
                          scored.loc[common, "dk_points"])
    qs_t = quantile_score(right.loc[common, list(QUANTILE_COLUMNS)],
                          scored.loc[common, "dk_points"])
    frame = pd.DataFrame({"position": scored.loc[common, "position"].astype(str),
                          "d": qs_t - qs_c})
    primary = frame[frame.position.isin(PRIMARY_POSITIONS)]
    return {
        "rows": int(len(frame)),
        "primary_rows": int(len(primary)),
        "statistic": float(primary.d.mean()) if len(primary) else None,
        "by_position": {
            str(pos): {"rows": int(len(g)), "mean_d": float(g.d.mean())}
            for pos, g in frame.groupby("position")
        },
    }


def _book_totals(memberships: Sequence[Sequence[str]],
                 points: Mapping[str, float]) -> np.ndarray:
    # A rostered player with no scored row is an inactive: 0 DK points.
    return np.array([sum(float(points.get(str(p), 0.0)) for p in row)
                     for row in memberships])


def lineup_week(manifest: Mapping, points_by_draftable: Mapping[str, float]) -> dict:
    """One week's paired book score from ONE selected companion manifest."""
    seeds = sorted({book["seed_label"] for book in manifest["books"].values()})
    per_seed = {}
    for label in seeds:
        out = {}
        for arm in ("control", "treatment"):
            totals = _book_totals(manifest["books"][f"{label}-{arm}"]["memberships"],
                                  points_by_draftable)
            out[arm] = {"max": float(totals.max()),
                        **{f"ge_{line}": int((totals >= line).sum())
                           for line in REPORTED_LINES}}
        out["max_difference"] = out["treatment"]["max"] - out["control"]["max"]
        per_seed[label] = out
    return {
        "seeds": len(per_seed),
        "statistic": float(np.mean([v["max_difference"] for v in per_seed.values()])),
        "per_seed": per_seed,
    }


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def select_week_manifest(manifests: Iterable[Mapping], *, lock_utc: datetime,
                         settings_sha256: str) -> Mapping | None:
    """The week's ONE graded companion manifest, keyed by content identity.

    Live, non-dry-run, the companion contract with this sha, all ten books,
    no empty-marginal fallback, generated before lock. Identical copies (by
    content sha256) collapse to one; of distinct complete manifests the
    earliest generated wins (a later re-run never replaces a frozen week).
    """
    eligible: dict[str, Mapping] = {}
    for manifest in manifests:
        contract = manifest.get("contract") or {}
        if (not manifest.get("live") or manifest.get("dry_run")
                or contract.get("contract") != COMPANION_CONTRACT
                or contract.get("settings_sha256") != settings_sha256
                or len(manifest.get("books") or {}) != 10
                or (manifest.get("marginal_reads") or {}).get("empty_fallbacks", 1) != 0
                or datetime.fromisoformat(manifest["generated_at"]) >= lock_utc):
            continue
        eligible.setdefault(_canonical_sha256(manifest), manifest)
    if not eligible:
        return None
    return min(eligible.values(), key=lambda m: m["generated_at"])


def candidate_id(row: Mapping) -> str:
    """Content identity of one candidate: week, book (seed/arm), sorted players."""
    panel = str(row["panel_run_id"])
    book = "-".join(panel.rsplit("-", 2)[-2:])  # e.g. r0-control
    players = row["players"]
    if isinstance(players, str):
        players = json.loads(players) if players.startswith("[") else players.split(",")
    return _canonical_sha256([int(row["season"]), int(row["week"]), book,
                              sorted(str(p) for p in players)])


def candidates_for_manifest(rows: pd.DataFrame, manifest: Mapping) -> pd.DataFrame:
    """Candidate rows of the selected manifest only, retry duplicates removed.

    A retried execution writes its rows under a new run id; rows of panels the
    selected manifest does not name are dropped, and any remaining duplicate
    of the same candidate (same week, book and players) counts once.
    """
    panels = {book["panel_run_id"] for book in manifest["books"].values()}
    kept = rows[rows.panel_run_id.isin(panels)].copy()
    kept["candidate_id"] = [candidate_id(r) for r in kept.to_dict("records")]
    return kept.drop_duplicates("candidate_id").reset_index(drop=True)


def decision(weekly: Sequence[float], *, look: str, better: str) -> dict:
    """Week-clustered read of one part. better: 'lower' or 'higher'."""
    if look not in ("interim", "final") or better not in ("lower", "higher"):
        raise ValueError("look must be interim|final, better lower|higher")
    values = np.asarray([v for v in weekly if v is not None], float)
    n = len(values)
    need = INTERIM_MIN_WEEKS if look == "interim" else FLOOR_WEEKS
    if n < need:
        return {"look": look, "weeks": n, "verdict": "NO VERDICT",
                "reason": f"needs {need} complete weeks"}
    mean = float(values.mean())
    se = float(values.std(ddof=1) / np.sqrt(n))
    t_value = mean / se if se > 0 else (np.inf * np.sign(mean) if mean else 0.0)
    alpha = INTERIM_ALPHA if look == "interim" else FINAL_ALPHA
    critical = float(stats.t.ppf(1 - alpha / 2, n - 1))
    sign = -1.0 if better == "lower" else 1.0
    if sign * t_value >= critical:
        verdict = "BETTER"
        if look == "final":
            lowo = [(values.sum() - v) / (n - 1) for v in values]
            if not all(sign * m > 0 for m in lowo):
                verdict = "NO DIFFERENCE"
    elif -sign * t_value >= critical:
        verdict = "WORSE"
    else:
        verdict = "NO DIFFERENCE"
    return {"look": look, "weeks": n, "mean": mean, "se": se, "t": float(t_value),
            "critical": critical, "verdict": verdict}


__all__ = [
    "COMPANION_CONTRACT", "FLOOR_WEEKS", "INTERIM_AFTER_WEEK", "PRIMARY_POSITIONS",
    "QUANTILE_COLUMNS", "QUANTILE_LEVELS", "REPORTED_LINES", "candidate_id",
    "candidates_for_manifest", "decision", "distribution_week", "lineup_week",
    "quantile_score", "select_week_manifest",
]
