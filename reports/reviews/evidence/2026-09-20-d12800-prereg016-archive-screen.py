"""Outcome-blind exploratory replay of PREREG-016 on the archived D12800 pool.

This is an in-sample mechanism check: it reuses the two banks that produced
the archived dual_emax book.  It is not a prospective selector result and
cannot authorize a live change.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/erich/projects/nfl2/src")
from nfl2.selectors import cap_prefix_then_fill, greedy_ladder  # noqa: E402


ARCH = Path(os.environ.get(
    "D12800_SCREEN_ARCHIVE",
    "/home/erich/projects/review-evidence/overnight-20260918/d12800-archive-20260920",
))
OUT = Path(os.environ.get(
    "D12800_SCREEN_OUT",
    "/home/erich/projects/nfl-predictions/reports/reviews/evidence/2026-09-20-d12800-prereg016-archive-screen-result.json",
))
BANKS = ("incumbent_player_scores.npy", "corrected_hsim_player_scores.npy")
RUNG_WEIGHTS = {194.0: 1.0, 200.0: 2.0, 210.0: 6.0, 220.0: 12.0}
PREFIXES = (1, 10, 20, 30, 40, 80, 97)
THRESHOLDS = (194, 200, 210, 220, 230, 240)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def player_totals(bank: np.ndarray, roster_indices: list[np.ndarray]) -> np.ndarray:
    """Sum nine player rows per candidate in bounded chunks."""
    out = np.empty((len(roster_indices), bank.shape[1]), dtype=np.float32)
    for start in range(0, len(roster_indices), 256):
        stop = min(start + 256, len(roster_indices))
        idx = np.asarray(roster_indices[start:stop], dtype=np.int32)
        out[start:stop] = bank[idx].sum(axis=1, dtype=np.float32)
    return out


def parse_book(path: Path, dk_to_id: dict[str, str]) -> list[frozenset[str]]:
    with path.open(newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
    return [frozenset(dk_to_id[str(value)] for value in row) for row in rows[1:]]


def metrics(totals: np.ndarray, order: list[int]) -> dict[str, object]:
    selected = totals[np.asarray(order, dtype=np.int32)]
    maxima = selected.max(axis=0)
    row_rates = {
        str(t): float((selected >= t).mean()) for t in THRESHOLDS
    }
    prefixes = {}
    for k in PREFIXES:
        pm = selected[:k].max(axis=0)
        prefixes[str(k)] = {
            "max_mean": float(pm.mean(dtype=np.float64)),
            **{f"p{t}": float((pm >= t).mean()) for t in THRESHOLDS},
        }
    return {
        "max_mean": float(maxima.mean(dtype=np.float64)),
        **{f"p{t}": float((maxima >= t).mean()) for t in THRESHOLDS},
        "individual_row_mean": float(selected.mean(dtype=np.float64)),
        "individual_row_rates": row_rates,
        "prefixes": prefixes,
    }


def overlap_stats(rosters: list[frozenset[str]], order: list[int]) -> dict[str, float | int]:
    chosen = [rosters[i] for i in order]
    vals = [len(chosen[i] & chosen[j]) for i in range(len(chosen)) for j in range(i)]
    return {
        "pairs": len(vals),
        "mean_pair_overlap": float(np.mean(vals)) if vals else 0.0,
        "max_pair_overlap": int(max(vals)) if vals else 0,
    }


def main() -> None:
    frame_cols = ["id", "dk_player_id", "display_name", "team_abbr", "position"]
    frame = pd.read_parquet(ARCH / "frame.parquet", columns=frame_cols)
    ids = frame["id"].astype(str).tolist()
    id_to_idx = {value: i for i, value in enumerate(ids)}
    dk_to_id = {
        str(int(row.dk_player_id)): str(row.id)
        for row in frame.itertuples()
        if pd.notna(row.dk_player_id)
    }

    candidate_cols = ["cand", "players", "names", "salary", "sel_mean", "sel_p194"]
    candidates = pd.read_parquet(ARCH / "candidates.parquet", columns=candidate_cols)
    candidate_rosters = []
    roster_indices = []
    for raw in candidates["players"].astype(str):
        roster = frozenset(raw.split(","))
        assert len(roster) == 9 and roster.issubset(id_to_idx)
        candidate_rosters.append(roster)
        roster_indices.append(np.asarray([id_to_idx[x] for x in raw.split(",")], dtype=np.int32))

    banks = [np.load(ARCH / name, mmap_mode="r", allow_pickle=False) for name in BANKS]
    assert all(bank.shape == (len(frame), 10_000) and bank.dtype == np.float32 for bank in banks)
    bank_totals = [player_totals(bank, roster_indices) for bank in banks]
    pooled = np.concatenate(bank_totals, axis=1)
    mean_total = pooled.mean(axis=1, dtype=np.float64)

    raw_book = parse_book(ARCH / "book.csv", dk_to_id)
    by_roster = {roster: i for i, roster in enumerate(candidate_rosters)}
    dual_order = [by_roster[roster] for roster in raw_book]
    assert len(dual_order) == 97 and len(set(dual_order)) == 97

    clear_by_rung = {rung: pooled >= rung for rung in RUNG_WEIGHTS}
    ladder_order, prefix_count = cap_prefix_then_fill(
        clear_by_rung, RUNG_WEIGHTS, 97, candidate_rosters, 4, mean_total=mean_total
    )
    assert len(ladder_order) == 97 and len(set(ladder_order)) == 97
    uncapped_order = greedy_ladder(
        clear_by_rung, RUNG_WEIGHTS, 97, mean_total=mean_total
    )
    assert len(uncapped_order) == 97 and len(set(uncapped_order)) == 97

    def bank_views(order: list[int]) -> dict[str, object]:
        return {
            "pooled": metrics(pooled, order),
            "incumbent": metrics(bank_totals[0], order),
            "corrected_hsim": metrics(bank_totals[1], order),
        }

    result = {
        "schema": "d12800-prereg016-archive-screen/v1",
        "archive_manifest_sha256": sha(ARCH / "MANIFEST.json"),
        "archive_receipt_sha256": sha(ARCH / "receipt.json"),
        "source_files": {
            name: sha(ARCH / name)
            for name in ("frame.parquet", "candidates.parquet", *BANKS, "book.csv")
        },
        "source_frame_columns": frame_cols,
        "source_candidate_columns": candidate_cols,
        "candidate_count": len(candidate_rosters),
        "worlds_per_bank": bank_totals[0].shape[1],
        "pooled_worlds": pooled.shape[1],
        "control": {
            "selector": "dual_emax",
            "book_sha256": sha(ARCH / "book.csv"),
            "candidate_indices": dual_order,
            "metrics": bank_views(dual_order),
            "overlap": overlap_stats(candidate_rosters, dual_order),
        },
        "treatment": {
            "selector": "cap_prefix_then_fill",
            "rungs": list(RUNG_WEIGHTS),
            "weights": RUNG_WEIGHTS,
            "gamma": 4,
            "mean_tiebreak": True,
            "prefix_count": int(prefix_count),
            "candidate_indices": ladder_order,
            "candidate_ids": [int(candidates.iloc[i].cand) for i in ladder_order],
            "metrics": bank_views(ladder_order),
            "overlap": overlap_stats(candidate_rosters, ladder_order),
        },
        "uncapped_ladder": {
            "selector": "greedy_ladder",
            "candidate_indices": uncapped_order,
            "metrics": bank_views(uncapped_order),
            "overlap": overlap_stats(candidate_rosters, uncapped_order),
        },
        "cap_engagement": {
            "order_equal_to_uncapped": ladder_order == uncapped_order,
            "positions_different": int(sum(a != b for a, b in zip(ladder_order, uncapped_order))),
            "shared_members": int(len(set(ladder_order) & set(uncapped_order))),
            "prefix_count": int(prefix_count),
        },
        "current_outcomes_read": False,
        "provider_calls": 0,
        "interpretation": "in-sample mechanism screen; not a prospective result or adoption authorization",
    }
    # Fill paired differences after result structure exists without duplicating
    # the full metric payload.
    cm = result["control"]["metrics"]["pooled"]
    tm = result["treatment"]["metrics"]["pooled"]
    diff_keys = ["max_mean", *[f"p{t}" for t in THRESHOLDS], "individual_row_mean"]
    result["paired_treatment_minus_control"] = {
        key: float(tm[key] - cm[key]) for key in diff_keys
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "control": result["control"]["metrics"]["pooled"],
        "treatment": result["treatment"]["metrics"]["pooled"],
        "prefix_count": prefix_count,
        "result_sha256": sha(OUT),
        "out": str(OUT),
    }, indent=2))


if __name__ == "__main__":
    main()
