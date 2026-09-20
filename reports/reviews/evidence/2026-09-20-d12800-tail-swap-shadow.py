"""Outcome-blind one-row shadow swaps for the D12800 tail diagnostic.

The experiment keeps the archived K97 book fixed and substitutes the strongest
unselected high-tail candidate into one delivered rank at a time. It reads
only frame identity/name/DK-id columns, candidate rosters, the archived book,
the receipt, and the two selection banks. It never reads realized outcomes or
provider data and cannot alter a live book.
"""
import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).parent
ARCH = Path(os.environ.get(
    "D12800_ARCHIVE",
    "/home/erich/projects/review-evidence/overnight-20260918/d12800-archive-20260920",
))
OUT = Path(os.environ.get(
    "D12800_TAIL_SWAP_OUT",
    str(HERE / "2026-09-20-d12800-tail-swap-shadow-result.json"),
))
BANK_NAMES = ("incumbent_player_scores.npy", "corrected_hsim_player_scores.npy")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_book(path: Path) -> list[list[str]]:
    with path.open(newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
    assert len(rows) == 98 and all(len(row) == 9 for row in rows[1:])
    return rows[1:]


def portfolio_metrics(totals: np.ndarray) -> dict[str, float]:
    maxima = totals.max(axis=0)
    return {
        "max_mean": float(maxima.mean(dtype=np.float64)),
        "max_median": float(np.median(maxima)),
        "max_p220": float((maxima >= 220).mean()),
        "max_p230": float((maxima >= 230).mean()),
        "row_mean_average": float(totals.mean(axis=1, dtype=np.float64).mean()),
        "row_p220_average": float((totals >= 220).mean(axis=1, dtype=np.float64).mean()),
        "row_p230_average": float((totals >= 230).mean(axis=1, dtype=np.float64).mean()),
    }


def main() -> None:
    manifest = json.loads((ARCH / "MANIFEST.json").read_text())
    by_name = {item["name"]: item for item in manifest["objects"]}
    required = ["frame.parquet", "candidates.parquet", "book.csv", "receipt.json", *BANK_NAMES]
    for name in required:
        assert sha(ARCH / name) == by_name[name]["sha256_local"], name

    frame = pd.read_parquet(ARCH / "frame.parquet", columns=["id", "dk_player_id", "name"])
    candidates = pd.read_parquet(ARCH / "candidates.parquet", columns=["cand", "players", "names"])
    receipt = json.loads((ARCH / "receipt.json").read_text())
    assert len(candidates) == receipt["candidates"] == 12555
    assert receipt["config"]["operational_k"] == 97
    frame_idx = {str(value): i for i, value in enumerate(frame["id"].astype(str))}
    dk_to_id = dict(zip(frame.dk_player_id.astype(int).astype(str), frame.id.astype(str)))
    rosters = []
    for players in candidates.players:
        ids = [token.strip() for token in players.split(",") if token.strip()]
        assert len(ids) == 9 and len(set(ids)) == 9
        rosters.append([frame_idx[token] for token in ids])
    roster_idx = np.asarray(rosters, dtype=np.int32)
    banks = [np.load(ARCH / name, mmap_mode="r", allow_pickle=False) for name in BANK_NAMES]
    assert all(bank.shape == (len(frame), 10000) and bank.dtype == np.float32 for bank in banks)
    pooled = np.concatenate(banks, axis=1)

    candidate_by_roster = {
        frozenset(indices): int(i) for i, indices in enumerate(roster_idx.tolist())
    }
    book = load_book(ARCH / "book.csv")
    selected = []
    for row in book:
        ids = [dk_to_id[value] for value in row]
        selected.append(candidate_by_roster[frozenset(frame_idx[value] for value in ids)])
    assert len(selected) == len(set(selected)) == 97
    selected_set = set(selected)
    candidate = 848
    assert candidate not in selected_set

    rows_to_score = selected + [candidate]
    row_totals = pooled[roster_idx[rows_to_score]].sum(axis=1, dtype=np.float32)
    control = row_totals[: len(selected)]
    candidate_totals = row_totals[-1]
    control_metrics = portfolio_metrics(control)

    swaps = {}
    for rank in (8, 46, 97):
        variant = control.copy()
        displaced = selected[rank - 1]
        variant[rank - 1] = candidate_totals
        metrics = portfolio_metrics(variant)
        swaps[str(rank)] = {
            "inserted_candidate": candidate,
            "displaced_candidate": int(displaced),
            "displaced_names": str(candidates.names.iloc[displaced]).split("|"),
            "inserted_names": str(candidates.names.iloc[candidate]).split("|"),
            "inserted_to_displaced_shared_players": int(
                len(set(roster_idx[candidate]) & set(roster_idx[displaced]))
            ),
            "metrics": metrics,
            "delta_vs_control": {
                key: float(metrics[key] - control_metrics[key])
                for key in metrics
            },
        }

    result = {
        "schema": "d12800-tail-swap-shadow/v1",
        "archive_manifest_sha256": sha(ARCH / "MANIFEST.json"),
        "source_files": {name: sha(ARCH / name) for name in required},
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "control": {"selected_candidates": selected, "metrics": control_metrics},
        "swaps": swaps,
        "current_outcomes_read": False,
        "provider_calls": 0,
        "source_columns": {
            "frame": ["id", "dk_player_id", "name"],
            "candidates": ["cand", "players", "names"],
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"control": control_metrics, "swaps": swaps, "result_sha256": sha(OUT), "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
