"""Outcome-blind paired world-bootstrap intervals for marginal-tail swaps.

This replays only the five declared candidate/rank substitutions from the
marginal-tail screen. It reads frame identity/name/DK-id columns, candidate
rosters, the archived book, receipt, and the two selection banks. It never
reads realized outcomes or provider data.
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
    "D12800_TAIL_BOOTSTRAP_OUT",
    str(HERE / "2026-09-20-d12800-tail-swap-bootstrap-result.json"),
))
BANK_NAMES = ("incumbent_player_scores.npy", "corrected_hsim_player_scores.npy")
SCREEN_RESULT = HERE / "2026-09-20-d12800-marginal-tail-screen-result.json"
SEED = 20260920
BOOTSTRAPS = 1000

# Ranks were chosen by the outcome-blind marginal screen's best single-row
# replacement diagnostics, before this interval calculation.
ARM_RANKS = {
    1334: {"max_mean": 8, "max_p220": 80, "max_p230": 72, "max_p240": 41},
    2765: {"max_mean": 8, "max_p220": 80, "max_p230": 72, "max_p240": 41},
    7399: {"max_mean": 8, "max_p220": 80, "max_p230": 72, "max_p240": 41},
    5211: {"max_mean": 96, "max_p220": 80, "max_p230": 72, "max_p240": 41},
    2396: {"max_mean": 97, "max_p220": 80, "max_p230": 72, "max_p240": 41},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_book(path: Path) -> list[list[str]]:
    with path.open(newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
    assert len(rows) == 98 and all(len(row) == 9 for row in rows[1:])
    return rows[1:]


def metric_values(maxima: np.ndarray) -> dict[str, float]:
    return {
        "max_mean": float(maxima.mean(dtype=np.float64)),
        "max_p220": float((maxima >= 220).mean()),
        "max_p230": float((maxima >= 230).mean()),
        "max_p240": float((maxima >= 240).mean()),
    }


def bootstrap_delta(delta: np.ndarray, rng: np.random.Generator) -> dict[str, float]:
    # Resample worlds in moderate batches to keep the index matrix bounded.
    values = np.empty(BOOTSTRAPS, dtype=np.float64)
    for start in range(0, BOOTSTRAPS, 100):
        stop = min(start + 100, BOOTSTRAPS)
        indices = rng.integers(0, len(delta), size=(stop - start, len(delta)), dtype=np.int32)
        values[start:stop] = delta[indices].mean(axis=1, dtype=np.float64)
    return {
        "point": float(delta.mean(dtype=np.float64)),
        "ci95_low": float(np.quantile(values, 0.025)),
        "ci95_high": float(np.quantile(values, 0.975)),
        "bootstrap_replicates": BOOTSTRAPS,
    }


def main() -> None:
    manifest = json.loads((ARCH / "MANIFEST.json").read_text())
    by_name = {item["name"]: item for item in manifest["objects"]}
    required = ["frame.parquet", "candidates.parquet", "book.csv", "receipt.json", *BANK_NAMES]
    for name in required:
        assert sha(ARCH / name) == by_name[name]["sha256_local"], name
    assert SCREEN_RESULT.exists()

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

    rows_to_score = selected + list(ARM_RANKS)
    row_totals = pooled[roster_idx[rows_to_score]].sum(axis=1, dtype=np.float32)
    control_rows = row_totals[: len(selected)]
    control_max = control_rows.max(axis=0)
    prefix = np.maximum.accumulate(control_rows, axis=0)
    suffix = np.maximum.accumulate(control_rows[::-1], axis=0)[::-1]
    without = []
    for rank in range(len(selected)):
        if rank == 0:
            without.append(suffix[1])
        elif rank == len(selected) - 1:
            without.append(prefix[-2])
        else:
            without.append(np.maximum(prefix[rank - 1], suffix[rank + 1]))
    without = np.asarray(without)
    rng = np.random.default_rng(SEED)

    arms = {}
    for offset, (candidate, ranks) in enumerate(ARM_RANKS.items()):
        candidate_total = row_totals[len(selected) + offset]
        arm_result = {
            "candidate": candidate,
            "names": str(candidates.names.iloc[candidate]).split("|"),
            "ranks": ranks,
            "metrics": {},
        }
        for metric_name, rank in ranks.items():
            swapped_max = np.maximum(without[rank - 1], candidate_total)
            arm_result["metrics"][metric_name] = {
                "rank": rank,
                "displaced_candidate": int(selected[rank - 1]),
                "point_metrics": metric_values(swapped_max),
                "delta": {
                    key: bootstrap_delta(
                        (swapped_max >= int(key.removeprefix("max_p")))
                        .astype(np.float64)
                        - (control_max >= int(key.removeprefix("max_p"))).astype(np.float64),
                        rng,
                    ) if key in ("max_p220", "max_p230", "max_p240") else bootstrap_delta(swapped_max - control_max, rng)
                    for key in ("max_mean", "max_p220", "max_p230", "max_p240")
                },
            }
            # The selected objective's delta is the primary field; the full
            # delta vector is retained for cross-threshold tradeoffs.
        arms[str(candidate)] = arm_result

    result = {
        "schema": "d12800-tail-swap-world-bootstrap/v1",
        "archive_manifest_sha256": sha(ARCH / "MANIFEST.json"),
        "screen_result_sha256": sha(SCREEN_RESULT),
        "source_files": {name: sha(ARCH / name) for name in required},
        "seed": SEED,
        "bootstraps": BOOTSTRAPS,
        "control_metrics": metric_values(control_max),
        "arms": arms,
        "current_outcomes_read": False,
        "provider_calls": 0,
        "source_columns": {
            "frame": ["id", "dk_player_id", "name"],
            "candidates": ["cand", "players", "names"],
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"control_metrics": result["control_metrics"], "arms": arms, "result_sha256": sha(OUT), "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
