"""Frozen-candidate portfolio and missed-winner diagnostics.

The helpers in this module never regenerate candidates or resimulate a slate.
They apply the production coverage selector to the immutable support masks
persisted by replay, which makes entry-count and selection-line comparisons
paired counterfactuals on exactly the same candidate worlds.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from nfl_dfs.optimizer.lineup import select_from_support


MASK_COLUMNS = {
    187.0: "clear_bits_187",
    194.0: "clear_bits_194",
    200.0: "clear_bits_200",
}
ACTUAL_THRESHOLDS = (187.0, 194.0, 200.0, 210.0, 220.0, 230.0, 240.0)


def decode_clear_bits(value: str, n_worlds: int) -> np.ndarray:
    """Decode one big-endian hexadecimal replay support mask."""
    if not isinstance(value, str) or not value:
        raise ValueError("clear-world mask is empty")
    raw = np.frombuffer(bytes.fromhex(value), dtype=np.uint8)
    bits = np.unpackbits(raw, bitorder="big")
    if len(bits) < n_worlds:
        raise ValueError(
            f"mask contains {len(bits)} bits, fewer than {n_worlds} worlds")
    return bits[:n_worlds].astype(bool)


def slate_support(rows: pd.DataFrame, select_line: float) -> tuple[pd.DataFrame,
                                                                   np.ndarray]:
    """Return cand_ix-sorted rows and the requested candidate/world mask."""
    if select_line not in MASK_COLUMNS:
        raise ValueError(
            f"selection line {select_line:g} has no persisted mask; "
            f"choose one of {sorted(MASK_COLUMNS)}")
    needed = {"cand_ix", "n_worlds", MASK_COLUMNS[select_line]}
    missing = needed - set(rows.columns)
    if missing:
        raise ValueError(f"candidate rows missing {sorted(missing)}")
    if rows.empty:
        raise ValueError("candidate slate is empty")
    ordered = rows.sort_values("cand_ix").reset_index(drop=True)
    if ordered.cand_ix.duplicated().any():
        raise ValueError("candidate slate has duplicate cand_ix")
    n_worlds = int(ordered.n_worlds.iloc[0])
    if n_worlds <= 0 or not ordered.n_worlds.eq(n_worlds).all():
        raise ValueError("n_worlds is invalid or inconsistent within slate")
    column = MASK_COLUMNS[select_line]
    support = np.stack(
        [decode_clear_bits(value, n_worlds) for value in ordered[column]])
    return ordered, support


def select_slate(rows: pd.DataFrame, entry_count: int,
                 select_line: float = 194.0) -> tuple[pd.DataFrame, np.ndarray,
                                                     np.ndarray]:
    """Reselect one frozen slate with the production coverage algorithm.

    Returns the ordered candidate frame, the full support matrix, and the
    positional indices selected from that frame.
    """
    if entry_count <= 0:
        raise ValueError("entry_count must be positive")
    ordered, support = slate_support(rows, select_line)
    needed = {"sim_mean", "actual_score", "players"}
    missing = needed - set(ordered.columns)
    if missing:
        raise ValueError(f"candidate rows missing {sorted(missing)}")
    picked = select_from_support(
        support, support.mean(axis=1),
        ordered.sim_mean.to_numpy(dtype=float), entry_count)
    return ordered, support, np.asarray(picked, dtype=int)


def _descending_rank(values: pd.Series, position: int) -> int:
    numeric = pd.to_numeric(values, errors="coerce")
    target = numeric.iloc[position]
    if not np.isfinite(target):
        return len(values)
    return int((numeric > target).sum()) + 1


def _best_swap_delta(support: np.ndarray, picked: np.ndarray,
                     oracle_pos: int) -> tuple[int, int]:
    """Best coverage change from swapping an oracle into the portfolio.

    A zero delta means at least one selected candidate could be replaced by
    the hindsight winner without reducing the final simulated-world coverage.
    This is diagnostic only: actual outcomes are never available pre-lock.
    """
    if oracle_pos in set(picked.tolist()):
        return 0, len(picked)
    baseline = int(np.any(support[picked], axis=0).sum())
    best = -support.shape[1]
    nonnegative = 0
    for dropped in picked:
        kept = picked[picked != dropped]
        swapped = np.append(kept, oracle_pos)
        delta = int(np.any(support[swapped], axis=0).sum()) - baseline
        best = max(best, delta)
        nonnegative += int(delta >= 0)
    return best, nonnegative


def swap_frontier(support: np.ndarray,
                  picked: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Best one-for-one coverage swap for every candidate in one slate.

    Returns two candidate-length arrays: the best change in covered worlds
    and the number of selected entries that candidate can replace without
    reducing coverage. This exposes whether a hindsight winner's zero-cost
    swap is unusual or one of many equivalent simulated portfolios.
    """
    support = np.asarray(support, dtype=bool)
    picked = np.asarray(picked, dtype=int)
    if support.ndim != 2 or not len(picked):
        raise ValueError("support must be 2-D and picked must be nonempty")
    if picked.min() < 0 or picked.max() >= len(support):
        raise ValueError("picked contains an out-of-range candidate index")

    selected_support = support[picked]
    selected_count = selected_support.sum(axis=0)
    covered = selected_count > 0
    unique_support = selected_support & (selected_count == 1)
    unique_counts = unique_support.sum(axis=1, dtype=np.int32)
    new_worlds = np.count_nonzero(support & ~covered, axis=1)
    # 10,000 worlds fit safely in int16; cast the matrix-product result to
    # int32 before subtraction so future larger world counts remain safe.
    overlap = (support.astype(np.int16)
               @ unique_support.T.astype(np.int16)).astype(np.int32)
    losses = unique_counts[None, :] - overlap
    deltas = new_worlds[:, None] - losses
    return deltas.max(axis=1), (deltas >= 0).sum(axis=1)


def evaluate_portfolio(rows: pd.DataFrame, entry_count: int,
                       select_line: float = 194.0) -> tuple[pd.DataFrame,
                                                           pd.DataFrame]:
    """Reselect every slate and return slate diagnostics plus membership.

    The membership frame is keyed by season/week/cand_ix and is useful for
    auditing all high-scoring candidates, not only the single slate oracle.
    """
    needed = {"season", "week", "actual_score", "p_line", "sim_mean",
              "sim_q99", "tag", "players"}
    missing = needed - set(rows.columns)
    if missing:
        raise ValueError(f"candidate panel missing {sorted(missing)}")
    if rows.empty:
        raise ValueError("candidate panel is empty")

    slate_rows: list[dict] = []
    memberships: list[pd.DataFrame] = []
    for (season, week), group in rows.groupby(["season", "week"], sort=True):
        ordered, support, picked = select_slate(
            group, entry_count=entry_count, select_line=select_line)
        if len(picked) != min(entry_count, len(ordered)):
            raise ValueError(
                f"selector returned {len(picked)} entries for "
                f"{int(season)} week {int(week)}")

        actual = pd.to_numeric(ordered.actual_score, errors="coerce")
        if actual.isna().any():
            raise ValueError(
                f"missing actual score in {int(season)} week {int(week)}")
        oracle_pos = int(actual.to_numpy().argmax())
        selected_actual = actual.iloc[picked].to_numpy(dtype=float)
        selected_best_local = int(selected_actual.argmax())
        selected_best_pos = int(picked[selected_best_local])
        selected_set = set(picked.tolist())
        oracle_selected = oracle_pos in selected_set

        covered = np.any(support[picked], axis=0)
        oracle_worlds = support[oracle_pos]
        oracle_new_worlds = int(np.count_nonzero(oracle_worlds & ~covered))
        oracle_clear_worlds = int(np.count_nonzero(oracle_worlds))
        swap_delta, free_swaps = _best_swap_delta(
            support, picked, oracle_pos)

        oracle_players = set(str(ordered.players.iloc[oracle_pos]).split(","))
        best_players = set(
            str(ordered.players.iloc[selected_best_pos]).split(","))
        slate_rows.append({
            "season": int(season),
            "week": int(week),
            "entry_count": int(len(picked)),
            "select_line": float(select_line),
            "selected_best": float(selected_actual[selected_best_local]),
            "selected_best_cand_ix": int(
                ordered.cand_ix.iloc[selected_best_pos]),
            "oracle": float(actual.iloc[oracle_pos]),
            "oracle_cand_ix": int(ordered.cand_ix.iloc[oracle_pos]),
            "regret": float(
                actual.iloc[oracle_pos] - selected_actual[selected_best_local]),
            "oracle_selected": bool(oracle_selected),
            "oracle_tag": str(ordered.tag.iloc[oracle_pos]),
            "oracle_players": str(ordered.players.iloc[oracle_pos]),
            "selected_best_players": str(
                ordered.players.iloc[selected_best_pos]),
            "roster_overlap": int(len(oracle_players & best_players)),
            "oracle_actual_rank": _descending_rank(actual, oracle_pos),
            "oracle_p_line": float(ordered.p_line.iloc[oracle_pos]),
            "oracle_p_line_rank": _descending_rank(
                ordered.p_line, oracle_pos),
            "oracle_sim_mean": float(ordered.sim_mean.iloc[oracle_pos]),
            "oracle_sim_mean_rank": _descending_rank(
                ordered.sim_mean, oracle_pos),
            "oracle_sim_q99": float(ordered.sim_q99.iloc[oracle_pos]),
            "oracle_sim_q99_rank": _descending_rank(
                ordered.sim_q99, oracle_pos),
            "oracle_clear_worlds": oracle_clear_worlds,
            "oracle_new_worlds_after_portfolio": oracle_new_worlds,
            "covered_worlds": int(np.count_nonzero(covered)),
            "best_oracle_swap_coverage_delta": int(swap_delta),
            "nonnegative_oracle_swaps": int(free_swaps),
            "n_candidates": int(len(ordered)),
        })

        member = ordered[["cand_ix"]].copy()
        member.insert(0, "week", int(week))
        member.insert(0, "season", int(season))
        member["portfolio_selected"] = False
        member.loc[picked, "portfolio_selected"] = True
        memberships.append(member)
    return pd.DataFrame(slate_rows), pd.concat(memberships, ignore_index=True)


def portfolio_summary(slates: pd.DataFrame,
                      thresholds: Iterable[float] = ACTUAL_THRESHOLDS) -> dict:
    """Summarize realized weekly maxima and frozen-pool opportunity."""
    if slates.empty:
        raise ValueError("slate summary is empty")
    selected = pd.to_numeric(slates.selected_best, errors="raise")
    oracle = pd.to_numeric(slates.oracle, errors="raise")
    report = {
        "slates": int(len(slates)),
        "entry_count": int(slates.entry_count.iloc[0]),
        "select_line": float(slates.select_line.iloc[0]),
        "mean_weekly_max": float(selected.mean()),
        "median_weekly_max": float(selected.median()),
        "q90_weekly_max": float(selected.quantile(0.9)),
        "max_weekly_max": float(selected.max()),
        "mean_regret": float((oracle - selected).mean()),
        "oracle_selected_weeks": int(slates.oracle_selected.sum()),
    }
    for threshold in thresholds:
        label = f"ge_{int(threshold)}"
        report[label] = int((selected >= threshold).sum())
        report[f"oracle_{label}"] = int((oracle >= threshold).sum())
        report[f"recoverable_{label}"] = int(
            ((oracle >= threshold) & (selected < threshold)).sum())
    return report


def season_summary(slates: pd.DataFrame,
                   thresholds: Iterable[float] = (194.0, 200.0)) -> pd.DataFrame:
    """Per-season realized maximum counts for stability inspection."""
    rows: list[dict] = []
    for season, group in slates.groupby("season", sort=True):
        row = {
            "season": int(season),
            "slates": int(len(group)),
            "mean_weekly_max": float(group.selected_best.mean()),
            "mean_regret": float(group.regret.mean()),
        }
        for threshold in thresholds:
            label = f"ge_{int(threshold)}"
            row[label] = int((group.selected_best >= threshold).sum())
            row[f"oracle_{label}"] = int((group.oracle >= threshold).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def missed_oracles(slates: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Slates whose pool contained a threshold clear but the book did not."""
    out = slates[(slates.oracle >= threshold)
                 & (slates.selected_best < threshold)].copy()
    return out.sort_values(
        ["oracle", "regret"], ascending=False).reset_index(drop=True)


def high_unselected_candidates(rows: pd.DataFrame, membership: pd.DataFrame,
                               threshold: float) -> pd.DataFrame:
    """Every realized high score omitted from a reselected portfolio."""
    keys = ["season", "week", "cand_ix"]
    joined = rows.merge(membership, on=keys, validate="one_to_one")
    rank_cols = (("p_line", "p_line_rank"),
                 ("sim_mean", "sim_mean_rank"),
                 ("sim_q99", "sim_q99_rank"))
    for value_col, rank_col in rank_cols:
        joined[rank_col] = joined.groupby(
            ["season", "week"])[value_col].rank(
            method="min", ascending=False).astype(int)
    out = joined[
        (~joined.portfolio_selected)
        & (pd.to_numeric(joined.actual_score, errors="coerce") >= threshold)
    ].copy()
    return out.sort_values(
        ["actual_score", "season", "week"], ascending=[False, True, True])
