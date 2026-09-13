"""Front-30 hybrid: the selector's greedy core (ranks 1..C) plus the broadest lineups of the remainder (most distinct
games, then fewest from one game, then greedy rank) -- written as an emitter-compatible sibling run dir.  Outcome-blind.
Usage: python hybrid30.py RUN_DIR [--core 15] [--k 30] [--output-dir DIR]"""
import argparse, csv, json, pathlib, shutil
from collections import Counter
from datetime import UTC, datetime
import pandas as pd

SLOTS = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--core", type=int, default=15); ap.add_argument("--k", type=int, default=30); ap.add_argument("--output-dir"); a = ap.parse_args()
    run = pathlib.Path(a.run); out = pathlib.Path(a.output_dir or (str(run) + f"-hybrid{a.core}")); out.mkdir(parents=True, exist_ok=True)
    f = pd.read_parquet(run / "frame.parquet"); game = dict(zip(f.dk_player_id.astype(str), f.game_id.astype(str))); name = dict(zip(f.dk_player_id.astype(str), f.display_name.astype(str)))
    with (run / "book.csv").open(newline="") as h: rows = list(csv.reader(h))
    assert tuple(rows[0]) == SLOTS, rows[0]
    book = rows[1:]; n = len(book)
    counts = [Counter(game[c] for c in r) for r in book]
    core = list(range(min(a.core, n))); rest = sorted(range(len(core), n), key=lambda i: (-len(counts[i]), max(counts[i].values()), i))
    pick = core + rest[:a.k - len(core)]
    with (out / "book.csv").open("w", newline="") as h:
        w = csv.writer(h); w.writerow(SLOTS); [w.writerow(book[i]) for i in pick]
    with (out / "book_names.csv").open("w", newline="") as h:
        w = csv.writer(h); w.writerow(("hybrid_rank", "source_rank", "games", "max_game") + SLOTS)
        for r_, i in enumerate(pick, 1): w.writerow([r_, i + 1, len(counts[i]), max(counts[i].values())] + [name[c] for c in book[i]])
    shutil.copy(run / "frame.parquet", out / "frame.parquet"); shutil.copy(run / "receipt.json", out / "source_receipt.json")
    rec = {"version": "hybrid30-v1", "source_run": str(run), "core": a.core, "k": a.k, "source_ranks": [i + 1 for i in pick], "built_utc": datetime.now(UTC).isoformat(),
           "mean_games": sum(len(counts[i]) for i in pick) / len(pick), "greedy30_mean_games": sum(len(counts[i]) for i in range(min(a.k, n))) / min(a.k, n)}
    (out / "hybrid_receipt.json").write_text(json.dumps(rec, indent=1) + "\n"); print(json.dumps(rec)); print("book ->", out / "book.csv")

if __name__ == "__main__":
    main()
