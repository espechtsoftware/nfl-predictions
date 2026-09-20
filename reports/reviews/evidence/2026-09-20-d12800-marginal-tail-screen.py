"""Outcome-blind marginal-tail screen against the archived D12800 K97 book.

For every candidate, this computes the additional simulated worlds in which
the candidate would make the current book maximum clear 220, 230, or 240.
It also evaluates one-row replacements for the strongest marginal candidates.
Only frame identity/name/DK-id columns, candidate rosters, the book, receipt,
and the two selection banks are read. Current outcomes and provider data are
never opened.
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
    "D12800_MARGINAL_TAIL_OUT",
    str(HERE / "2026-09-20-d12800-marginal-tail-screen-result.json"),
))
BANK_NAMES = ("incumbent_player_scores.npy", "corrected_hsim_player_scores.npy")
THRESHOLDS = (220, 230, 240)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_book(path: Path) -> list[list[str]]:
    with path.open(newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
    assert len(rows) == 98 and all(len(row) == 9 for row in rows[1:])
    return rows[1:]


def metrics(maxima: np.ndarray) -> dict[str, float]:
    return {
        "max_mean": float(maxima.mean(dtype=np.float64)),
        "max_p220": float((maxima >= 220).mean()),
        "max_p230": float((maxima >= 230).mean()),
        "max_p240": float((maxima >= 240).mean()),
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

    selected_totals = pooled[roster_idx[selected]].sum(axis=1, dtype=np.float32)
    current_max = selected_totals.max(axis=0)
    control = metrics(current_max)
    # Exact max of the book after removing each possible row. Prefix/suffix
    # maxima handle ties correctly and avoid a 97x97x20,000 tensor.
    prefix = np.maximum.accumulate(selected_totals, axis=0)
    suffix = np.maximum.accumulate(selected_totals[::-1], axis=0)[::-1]
    without = []
    for rank in range(len(selected)):
        if rank == 0:
            without.append(suffix[1])
        elif rank == len(selected) - 1:
            without.append(prefix[-2])
        else:
            without.append(np.maximum(prefix[rank - 1], suffix[rank + 1]))
    without = np.asarray(without)

    n = len(candidates)
    candidate_mean = np.empty(n, dtype=np.float64)
    candidate_p = {threshold: np.empty(n, dtype=np.float64) for threshold in (220, 230, 240)}
    marginal = {threshold: np.empty(n, dtype=np.int32) for threshold in THRESHOLDS}
    mean_lift = np.empty(n, dtype=np.float64)
    # One pass over the full pool keeps the high-tail screen independent of
    # the candidate generation order while bounding the temporary tensor.
    for start in range(0, n, 256):
        stop = min(start + 256, n)
        totals = pooled[roster_idx[start:stop]].sum(axis=1, dtype=np.float32)
        candidate_mean[start:stop] = totals.mean(axis=1, dtype=np.float64)
        mean_lift[start:stop] = np.maximum(totals, current_max).mean(axis=1, dtype=np.float64) - control["max_mean"]
        for threshold in THRESHOLDS:
            candidate_p[threshold][start:stop] = (totals >= threshold).mean(axis=1, dtype=np.float64)
            marginal[threshold][start:stop] = ((current_max < threshold) & (totals >= threshold)).sum(axis=1, dtype=np.int32)

    ladder_score = marginal[220] + 2 * marginal[230] + 4 * marginal[240]

    def order_for(values: np.ndarray) -> list[int]:
        order = np.argsort(-values, kind="stable")
        return [int(index) for index in order if int(index) not in selected_set][:20]

    rankings = {
        "marginal_220": order_for(marginal[220]),
        "marginal_230": order_for(marginal[230]),
        "marginal_240": order_for(marginal[240]),
        "tail_ladder_220_230_240": order_for(ladder_score),
        "mean_lift": order_for(mean_lift),
    }

    def candidate_record(index: int) -> dict[str, object]:
        roster = set(roster_idx[index])
        overlaps = sorted(
            (len(roster & set(roster_idx[selected_candidate])), rank, selected_candidate)
            for rank, selected_candidate in enumerate(selected, start=1)
        )
        nearest = [
            {"shared_players": int(shared), "selected_rank": int(rank), "selected_candidate": int(selected_candidate)}
            for shared, rank, selected_candidate in sorted(overlaps, key=lambda item: (-item[0], item[1]))[:5]
        ]
        return {
            "candidate": int(index),
            "names": str(candidates.names.iloc[index]).split("|"),
            "individual_mean": float(candidate_mean[index]),
            "individual_p220": float(candidate_p[220][index]),
            "individual_p230": float(candidate_p[230][index]),
            "individual_p240": float(candidate_p[240][index]),
            "marginal_worlds_220": int(marginal[220][index]),
            "marginal_worlds_230": int(marginal[230][index]),
            "marginal_worlds_240": int(marginal[240][index]),
            "marginal_ladder_score": int(ladder_score[index]),
            "marginal_mean_lift": float(mean_lift[index]),
            "nearest_selected_by_roster_overlap": nearest,
        }

    top_records = {
        name: [candidate_record(index) for index in indices[:10]]
        for name, indices in rankings.items()
    }

    # For the strongest marginal-tail candidates, find the best single-row
    # replacement under each max-of-book metric. This is a diagnostic, not a
    # production reselection proposal.
    swap_candidates = rankings["tail_ladder_220_230_240"][:10]
    swap_results = {}
    for index in swap_candidates:
        totals = pooled[roster_idx[index]].sum(axis=0, dtype=np.float32)
        best = {}
        for rank in range(len(selected)):
            maxima = np.maximum(without[rank], totals)
            value = metrics(maxima)
            for metric_name in ("max_mean", "max_p220", "max_p230", "max_p240"):
                prior = best.get(metric_name)
                if prior is None or value[metric_name] > prior["value"]:
                    best[metric_name] = {
                        "value": value[metric_name],
                        "delta_vs_control": value[metric_name] - control[metric_name],
                        "displaced_rank": rank + 1,
                        "displaced_candidate": int(selected[rank]),
                        "displaced_names": str(candidates.names.iloc[selected[rank]]).split("|"),
                    }
        swap_results[str(index)] = {
            "candidate": candidate_record(index),
            "best_single_row_replacement": best,
        }

    # Check whether the pooled marginal candidates are supported by both
    # equal-mass components. This is still a descriptive shadow; no component
    # is preferred for production and no audit bank is opened.
    component_results = {}
    for label, bank in zip(("incumbent", "corrected_hsim"), banks):
        component_selected = bank[roster_idx[selected]].sum(axis=1, dtype=np.float32)
        component_current_max = component_selected.max(axis=0)
        component_prefix = np.maximum.accumulate(component_selected, axis=0)
        component_suffix = np.maximum.accumulate(component_selected[::-1], axis=0)[::-1]
        component_without = []
        for rank in range(len(selected)):
            if rank == 0:
                component_without.append(component_suffix[1])
            elif rank == len(selected) - 1:
                component_without.append(component_prefix[-2])
            else:
                component_without.append(np.maximum(component_prefix[rank - 1], component_suffix[rank + 1]))
        component_without = np.asarray(component_without)
        component_control = metrics(component_current_max)
        component_swaps = {}
        for index in swap_candidates:
            totals = bank[roster_idx[index]].sum(axis=0, dtype=np.float32)
            best = {}
            for rank in range(len(selected)):
                value = metrics(np.maximum(component_without[rank], totals))
                for metric_name in ("max_mean", "max_p220", "max_p230", "max_p240"):
                    prior = best.get(metric_name)
                    if prior is None or value[metric_name] > prior["value"]:
                        best[metric_name] = {
                            "value": value[metric_name],
                            "delta_vs_control": value[metric_name] - component_control[metric_name],
                            "displaced_rank": rank + 1,
                            "displaced_candidate": int(selected[rank]),
                        }
            component_swaps[str(index)] = best
        component_results[label] = {"control_metrics": component_control, "best_swaps": component_swaps}

    result = {
        "schema": "d12800-marginal-tail-screen/v1",
        "archive_manifest_sha256": sha(ARCH / "MANIFEST.json"),
        "source_files": {name: sha(ARCH / name) for name in required},
        "candidate_count": n,
        "selected_count": len(selected),
        "control": {"metrics": control, "selected_candidates": selected},
        "rankings_top20_unselected": rankings,
        "top10_records": top_records,
        "top10_tail_ladder_swap_diagnostics": swap_results,
        "component_tail_ladder_swap_diagnostics": component_results,
        "current_outcomes_read": False,
        "provider_calls": 0,
        "source_columns": {
            "frame": ["id", "dk_player_id", "name"],
            "candidates": ["cand", "players", "names"],
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "control": control,
        "rankings_top20_unselected": rankings,
        "top10_tail_ladder_swap_diagnostics": swap_results,
        "result_sha256": sha(OUT),
        "out": str(OUT),
    }, indent=2))


if __name__ == "__main__":
    main()
