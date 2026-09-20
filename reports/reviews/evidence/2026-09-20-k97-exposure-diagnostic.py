"""Outcome-blind exposure/unique-tail diagnostic for the regenerated K97 book."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


ARCH = Path(os.environ.get(
    "K97_EXPOSURE_ARCHIVE",
    "/home/erich/projects/review-evidence/overnight-20260918/d12800-archive-20260920",
))
BOOK = Path(os.environ.get(
    "K97_EXPOSURE_BOOK",
    "/home/erich/projects/.nfl2-worktrees/prereg101-review-reply/handoffs/receipts/2026-09-20-sunday-live-k97/regen-1048/regen-promoted-book.csv",
))
OUT = Path(os.environ.get(
    "K97_EXPOSURE_OUT",
    "/home/erich/projects/nfl-predictions/reports/reviews/evidence/2026-09-20-k97-exposure-diagnostic-result.json",
))
BANKS = ("incumbent_player_scores.npy", "corrected_hsim_player_scores.npy")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    frame_cols = ["id", "dk_player_id", "display_name", "team_abbr", "position"]
    frame = pd.read_parquet(ARCH / "frame.parquet", columns=frame_cols)
    by_dk = {
        str(int(row.dk_player_id)): row
        for row in frame.itertuples()
        if pd.notna(row.dk_player_id)
    }
    by_id = {str(row.id): row for row in frame.itertuples()}
    frame_idx = {str(value): i for i, value in enumerate(frame["id"].astype(str))}
    with BOOK.open(newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
    assert len(rows) == 98 and all(len(row) == 9 for row in rows[1:])
    rosters = []
    for row in rows[1:]:
        ids = [str(by_dk[value].id) for value in row]
        assert len(set(ids)) == 9
        rosters.append(tuple(ids))
    roster_idx = np.asarray([[frame_idx[value] for value in row] for row in rosters], dtype=np.int32)
    banks = [np.load(ARCH / name, mmap_mode="r", allow_pickle=False) for name in BANKS]
    assert all(bank.shape == (len(frame), 10_000) and bank.dtype == np.float32 for bank in banks)
    totals = np.concatenate(
        [bank[roster_idx].sum(axis=1, dtype=np.float32) for bank in banks], axis=1
    )
    maxima = totals.max(axis=0)
    control = {
        "max_mean": float(maxima.mean(dtype=np.float64)),
        "p220": float((maxima >= 220).mean()),
        "p230": float((maxima >= 230).mean()),
        "p240": float((maxima >= 240).mean()),
    }
    exposures = Counter(player for row in rosters for player in row)
    records = []
    for player, exposure in exposures.most_common():
        affected = np.asarray([player in row for row in rosters])
        remaining_max = totals[~affected].max(axis=0)
        records.append({
            "id": player,
            "name": str(by_id[player].display_name),
            "team": str(by_id[player].team_abbr),
            "position": str(by_id[player].position),
            "exposure": int(exposure),
            "first30_exposure": int(sum(player in row for row in rosters[:30])),
            "max_mean_loss": float(maxima.mean(dtype=np.float64) - remaining_max.mean(dtype=np.float64)),
            "p220_loss_pp": float(100 * ((maxima >= 220).mean() - (remaining_max >= 220).mean())),
            "p230_loss_pp": float(100 * ((maxima >= 230).mean() - (remaining_max >= 230).mean())),
            "p240_loss_pp": float(100 * ((maxima >= 240).mean() - (remaining_max >= 240).mean())),
            "unique_220_worlds": int(((maxima >= 220) & ~(remaining_max >= 220)).sum()),
            "unique_230_worlds": int(((maxima >= 230) & ~(remaining_max >= 230)).sum()),
        })
    result = {
        "schema": "k97-exposure-diagnostic/v1",
        "archive_manifest_sha256": sha(ARCH / "MANIFEST.json"),
        "book_sha256": sha(BOOK),
        "source_files": {name: sha(ARCH / name) for name in ("frame.parquet", *BANKS)},
        "source_frame_columns": frame_cols,
        "rows": len(rosters),
        "worlds": totals.shape[1],
        "control": control,
        "players": records,
        "current_outcomes_read": False,
        "provider_calls": 0,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"control": control, "top": records[:12], "result_sha256": sha(OUT), "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
