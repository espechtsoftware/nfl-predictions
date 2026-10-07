#!/usr/bin/env python3
"""The week's cheap-player term-block file (the outside reviewer, 10-07: the Milly graph's within-portfolio finding --
the regulars' top-1% lineups carried more sub-$4,000 players in all four 2026 weeks -- and the 8-row block replay on
W2-4, ahead of LIVE in all three weeks at +2 and +4; reports/2026-10-07-graph-cheap-players-finding.md). The union's
--term-block-* vehicle builds N rows on projection + min(tilt x pred_own, cap); with pred_own = bonus / 0.20, tilt 0.20
and cap = POINTS the block adds exactly POINTS projected points to every non-DST player under $4,000 and nothing to
anyone else (a preference, not a mandate; the expensive players are not ruled out).

    bonus = POINTS if pos in (QB, RB, WR, TE) and salary < 4000 else 0

Public data only (DraftKings salaries and positions); no vendor values. Output (the format own_bonus reads, the same
columns as matchup_block_file.py): dk_player_id, id, display_name, pos, team, opp, pred_own, bonus_points; every skill
player of the source once (a bonus of 0 included), the DST omitted. Refuses (exit 3) a source without skill players, a
missing or duplicated dk_player_id, a non-positive POINTS, a week where no player carries a bonus, or an --out that
already exists (create-once).

The source (one of):
  --group G   RECOMMENDED: every player of draft group G's newest DraftKings salary pull (nfl_raw.dk_salaries). Salaries
              and positions are fixed for the week, so a file written days ahead still holds a row for a player who joins
              the T-70 frame later (an elevation, a status upgrade). The 10-07 code review: a file written from an
              earlier frame left 6-9 of Week 4's 134 T-70 sub-$4,000 skill players without the bonus (Sterling Shepard
              6.8, Zach Ertz 6.6, ...), while every tested form used the T-70 frame. Extra rows are harmless: the union's
              own_bonus maps only the frame's players.
  --frame F   a frame.parquet (the original form; misses players who are not in that frame).

    python scripts/cheap_block_file.py --season 2026 --week 5 --group 154468 --points 2.0 --out <path>/cheap2-w5.csv
    (the union then: --term-block-rows 8 --term-block-source <file> --term-block-tilt 0.20 --term-block-cap-points 2.0)
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

TILT = 0.20
CHEAP_MAX_SALARY = 4000
SKILL = ("QB", "RB", "WR", "TE")
COLUMNS = ["dk_player_id", "id", "display_name", "pos", "team", "opp", "pred_own", "bonus_points"]


def build(frame: pd.DataFrame, points: float) -> pd.DataFrame:
    """The block file's rows; raises ValueError rather than write a file the union would misread."""
    if not points > 0:
        raise ValueError(f"points must be positive (got {points})")
    fr = frame[frame["pos"].astype(str).isin(SKILL)].copy()
    if fr.empty:
        raise ValueError("the frame holds no skill players")
    ids = pd.to_numeric(fr["dk_player_id"], errors="coerce")
    if ids.isna().any():
        raise ValueError(f"{int(ids.isna().sum())} skill players have no dk_player_id")
    if ids.duplicated().any():
        raise ValueError(f"{int(ids.duplicated().sum())} duplicated dk_player_id values")
    sal = pd.to_numeric(fr["salary"], errors="coerce")
    bonus = np.where(sal.notna() & (sal < CHEAP_MAX_SALARY), float(points), 0.0)
    if not (bonus > 0).any():
        raise ValueError("no player carries a cheap bonus (own_bonus would refuse the file as fractions)")
    out = pd.DataFrame({"dk_player_id": ids.astype("int64"), "id": fr.get("id", pd.Series(index=fr.index, dtype=str)).astype(str),
                        "display_name": fr["display_name"].astype(str), "pos": fr["pos"].astype(str),
                        "team": fr.get("team", pd.Series(index=fr.index, dtype=str)).astype(str),
                        "opp": fr.get("opp", pd.Series(index=fr.index, dtype=str)).astype(str),
                        "pred_own": np.round(bonus / TILT, 4), "bonus_points": bonus})
    return out[COLUMNS].reset_index(drop=True)


def frame_from_dk_pull(pull: pd.DataFrame) -> pd.DataFrame:
    """ONE DraftKings salary pull of a draft group (nfl_raw.dk_salaries rows) as the columns build() reads: every player
    DraftKings lists for the slate. id and opp are left empty (the union matches the file on dk_player_id)."""
    if pull.empty:
        raise ValueError("the salary pull is empty")
    if "pulled_at" in pull.columns and pull["pulled_at"].nunique() != 1:
        raise ValueError(f"the rows come from {pull['pulled_at'].nunique()} pulls (one pull expected)")
    return pd.DataFrame({"dk_player_id": pull["dk_player_id"].values, "id": "", "display_name": pull["display_name"].astype(str).values,
                         "pos": pull["position"].astype(str).values, "team": pull["team_abbr"].astype(str).values, "opp": "",
                         "salary": pull["salary"].values})


def load_dk_pull(group: int, before: str | None = None) -> pd.DataFrame:
    """The newest pull of draft group `group` (before `before`, a UTC timestamp, when given) from nfl_raw.dk_salaries."""
    from google.cloud import bigquery
    try:
        from nfl_dfs.config import settings
        client, table = bigquery.Client(project=settings.project), f"{settings.raw}.dk_salaries"
    except Exception:                                   # run outside the production package: the default project
        client, table = bigquery.Client(), "nfl_raw.dk_salaries"
    params = [bigquery.ScalarQueryParameter("g", "INT64", int(group))]
    cond = ""
    if before:
        params.append(bigquery.ScalarQueryParameter("b", "TIMESTAMP", before)); cond = "AND pulled_at < @b"
    q = f"""SELECT pulled_at, dk_player_id, display_name, team_abbr, position, salary FROM `{table}`
            WHERE draft_group_id = @g {cond} QUALIFY pulled_at = MAX(pulled_at) OVER ()"""
    return client.query(q, job_config=bigquery.QueryJobConfig(query_parameters=params)).to_dataframe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--group", type=int, help="draft group id: every player of its newest DraftKings salary pull (recommended)")
    src.add_argument("--frame", type=Path, help="a frame.parquet (misses players not in that frame)")
    ap.add_argument("--pulled-before", default=None, help="with --group: the newest pull before this UTC timestamp")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--points", type=float, default=2.0, help="projected points added per sub-$4,000 non-DST player (the cap)")
    a = ap.parse_args(argv)
    if a.out.exists():
        print(f"CHEAP BLOCK FILE REFUSED: {a.out} exists (create-once; remove it deliberately to rewrite)", file=sys.stderr)
        return 3
    try:
        if a.group is not None:
            pull = load_dk_pull(a.group, a.pulled_before)
            frame = frame_from_dk_pull(pull)
            source = f"draft group {a.group} pull {pd.Timestamp(pull.pulled_at.iloc[0]).isoformat()} ({len(pull)} players)"
        else:
            frame = pd.read_parquet(a.frame)
            source = f"frame sha256 {hashlib.sha256(a.frame.read_bytes()).hexdigest()[:8]}"
        out = build(frame, a.points)
    except ValueError as e:
        print(f"CHEAP BLOCK FILE REFUSED: {e}", file=sys.stderr)
        return 3
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)
    print(f"cheap block file {a.season} W{a.week}: {int((out.bonus_points > 0).sum())} of {len(out)} skill players get +{a.points:g} "
          f"({source}) -> {a.out} (sha256 {hashlib.sha256(a.out.read_bytes()).hexdigest()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
