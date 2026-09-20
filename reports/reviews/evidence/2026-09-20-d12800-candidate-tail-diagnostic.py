"""Outcome-blind D12800 candidate-tail versus selected-book diagnostic.

This reads only candidate roster/selection metadata, frame identity/name/DK-id
columns, the two selection banks, and the archived book. It computes pooled
simulated P220/P230 for every candidate to measure whether tail-rich supply is
being lost before delivery. It never reads realized outcomes or provider data.
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
    "D12800_TAIL_DIAGNOSTIC_OUT",
    str(HERE / "2026-09-20-d12800-candidate-tail-diagnostic-result.json"),
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


def main() -> None:
    manifest = json.loads((ARCH / "MANIFEST.json").read_text())
    by_name = {item["name"]: item for item in manifest["objects"]}
    required = ["frame.parquet", "candidates.parquet", "book.csv", "receipt.json", *BANK_NAMES]
    for name in required:
        assert sha(ARCH / name) == by_name[name]["sha256_local"], name

    frame = pd.read_parquet(ARCH / "frame.parquet", columns=["id", "dk_player_id", "name"])
    candidates = pd.read_parquet(
        ARCH / "candidates.parquet",
        columns=["cand", "players", "names", "sel_mean", "sel_p194", "aud_mean", "aud_p194", "gen_mean"],
    )
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

    n = len(candidates)
    metrics = {
        "mean": np.empty(n, dtype=np.float64),
        "p220": np.empty(n, dtype=np.float64),
        "p230": np.empty(n, dtype=np.float64),
    }
    # Keep the working tensor bounded while evaluating every candidate against
    # both 10,000-world banks.
    for start in range(0, n, 256):
        stop = min(start + 256, n)
        totals = pooled[roster_idx[start:stop]].sum(axis=1, dtype=np.float32)
        metrics["mean"][start:stop] = totals.mean(axis=1, dtype=np.float64)
        metrics["p220"][start:stop] = (totals >= 220).mean(axis=1, dtype=np.float64)
        metrics["p230"][start:stop] = (totals >= 230).mean(axis=1, dtype=np.float64)

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
    roster_sets = [set(row) for row in roster_idx.tolist()]
    selected_rank = {candidate: rank for rank, candidate in enumerate(selected, start=1)}

    ranking = {}
    overlap = {}
    best_unselected = {}
    for metric_name, values in metrics.items():
        order = np.argsort(-values, kind="stable")
        ranking[metric_name] = [int(x) for x in order[:20]]
        overlap[metric_name] = {
            "top_97_selected": int(len(set(map(int, order[:97])) & selected_set)),
            "top_500_selected": int(len(set(map(int, order[:500])) & selected_set)),
            "top_1000_selected": int(len(set(map(int, order[:1000])) & selected_set)),
            "selected_best_rank": int(next(i for i, candidate in enumerate(order) if int(candidate) in selected_set) + 1),
        }
        candidate = next(int(candidate) for candidate in order if int(candidate) not in selected_set)
        best_unselected[metric_name] = {
            "candidate": candidate,
            "tail_rank": int(np.where(order == candidate)[0][0] + 1),
            "value": float(values[candidate]),
            "sel_mean": float(candidates.sel_mean.iloc[candidate]),
            "sel_p194": float(candidates.sel_p194.iloc[candidate]),
            "names": str(candidates.names.iloc[candidate]).split("|"),
        }
        nearest = sorted(
            (
                len(roster_sets[candidate] & roster_sets[selected_candidate]),
                selected_rank[selected_candidate],
                selected_candidate,
            )
            for selected_candidate in selected
        )
        best_unselected[metric_name]["nearest_selected_by_roster_overlap"] = [
            {
                "shared_players": int(shared),
                "selected_rank": int(rank),
                "selected_candidate": int(selected_candidate),
                "selected_names": str(candidates.names.iloc[selected_candidate]).split("|"),
            }
            for shared, rank, selected_candidate in sorted(nearest, key=lambda item: (-item[0], item[1]))[:5]
        ]

    selected_rows = candidates.iloc[selected]
    summaries = {
        "selected": {
            metric_name: {
                "mean": float(values[selected].mean()),
                "median": float(np.median(values[selected])),
                "max": float(values[selected].max()),
            }
            for metric_name, values in metrics.items()
        },
        "pool": {
            metric_name: {
                "mean": float(values.mean()),
                "median": float(np.median(values)),
                "max": float(values.max()),
            }
            for metric_name, values in metrics.items()
        },
        "selection_metadata": {
            "selected_sel_mean_mean": float(selected_rows.sel_mean.mean()),
            "pool_sel_mean_mean": float(candidates.sel_mean.mean()),
            "selected_sel_p194_mean": float(selected_rows.sel_p194.mean()),
            "pool_sel_p194_mean": float(candidates.sel_p194.mean()),
        },
    }
    result = {
        "schema": "d12800-candidate-tail-diagnostic/v1",
        "archive_manifest_sha256": sha(ARCH / "MANIFEST.json"),
        "source_files": {name: sha(ARCH / name) for name in required},
        "candidate_count": n,
        "selected_count": len(selected),
        "selected_candidates": selected,
        "ranking_top20": ranking,
        "overlap": overlap,
        "best_unselected": best_unselected,
        "summaries": summaries,
        "current_outcomes_read": False,
        "provider_calls": 0,
        "source_columns": {
            "frame": ["id", "dk_player_id", "name"],
            "candidates": ["cand", "players", "names", "sel_mean", "sel_p194", "aud_mean", "aud_p194", "gen_mean"],
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"overlap": overlap, "best_unselected": best_unselected, "result_sha256": sha(OUT), "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
