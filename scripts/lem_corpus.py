"""Large Event Model corpus builder (research round 9, 2026-08-03).

Tokenizes nflverse play-by-play into per-game event sequences for a
GPT-style next-event model (EventGPT/LEM lineage). Deliberately shares
its state space with the possession-Markov engine (models/game_sim.py)
so the two are directly comparable on held-out next-event log-loss —
the LEM must beat the Markov engine's transition model before it earns
sim integration (GAME_SIM_MODE=lem).

Token = one play, factored as a tuple flattened to a small vocab:
  quarter(1-5) | down(0-4) | dist bucket(4) | yardline bucket(10)
  | score-diff bucket(7) | event type(12) | yards bucket(9)
Vocab ~ a few thousand composite tokens; sequences ~140 plays/game.

Usage:
  python scripts/lem_corpus.py --stats            # vocab + size report
  python scripts/lem_corpus.py --out corpus.parquet  # full export
GPU training plan (queued, not run here): nanoGPT ~10M params, block
size 256, one 24GB GPU for hours-scale training; eval = next-event
log-loss on held-out seasons (walk-forward: train <=2023, eval 2024-25).
"""
import argparse

import numpy as np
import pandas as pd

EVENT_TYPES = ["pass_short", "pass_deep", "pass_incomplete", "sack",
               "rush", "scramble", "punt", "field_goal", "kickoff",
               "turnover", "touchdown", "other"]


def tokenize(pbp: pd.DataFrame) -> pd.DataFrame:
    d = pbp.copy()

    def ev(r):
        if r.get("touchdown") == 1:
            return "touchdown"
        if (r.get("interception") == 1 or r.get("fumble_lost") == 1):
            return "turnover"
        if r.get("sack") == 1:
            return "sack"
        pt = r.get("play_type")
        if pt == "pass":
            if r.get("complete_pass") != 1:
                return "pass_incomplete"
            return "pass_deep" if (r.get("air_yards") or 0) >= 15 else "pass_short"
        if pt == "run":
            return "scramble" if r.get("qb_scramble") == 1 else "rush"
        if pt in ("punt", "field_goal", "kickoff"):
            return pt
        return "other"

    d["ev"] = d.apply(ev, axis=1)
    d["tok"] = (
        d.qtr.clip(1, 5).astype(int).astype(str)
        + "|" + d.down.fillna(0).astype(int).astype(str)
        + "|" + pd.cut(d.ydstogo.fillna(10), [-1, 3, 7, 12, 99],
                       labels=["s", "m", "l", "xl"]).astype(str)
        + "|" + (d.yardline_100.fillna(50) // 10).astype(int).astype(str)
        + "|" + pd.cut(d.score_differential.fillna(0),
                       [-99, -17, -9, -3, 3, 9, 17, 99],
                       labels=list("abcdefg")).astype(str)
        + "|" + d.ev
        + "|" + pd.cut(d.yards_gained.fillna(0),
                       [-99, -1, 0, 3, 7, 12, 20, 40, 99],
                       labels=list("01234567")).astype(str)
    )
    return d[["game_id", "season", "play_id", "tok"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--seasons", default="1999-2025")
    args = ap.parse_args()
    import sys
    sys.path.insert(0, "src")
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings

    lo, hi = (int(x) for x in args.seasons.split("-"))
    pbp = query_df(f"""
      SELECT game_id, season, play_id, qtr, down, ydstogo, yardline_100,
             score_differential, play_type, complete_pass, air_yards,
             sack, qb_scramble, touchdown, interception, fumble_lost,
             yards_gained
      FROM `{settings.raw}.pbp`
      WHERE season BETWEEN {lo} AND {hi} AND play_type IS NOT NULL
      ORDER BY game_id, play_id""")
    toks = tokenize(pbp)
    vocab = toks.tok.value_counts()
    print(f"plays {len(toks):,}  games {toks.game_id.nunique():,}  "
          f"vocab {len(vocab):,}  top: {list(vocab.head(5).index)}")
    if args.out:
        toks.to_parquet(args.out, index=False)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
