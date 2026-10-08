#!/usr/bin/env python3
"""The T-70 UNION (operator 2026-09-28: "authorize the union at T-70 now; it repairs the regression from dropping the lev
batch"). One selection step, no solver time at T-70 unless --pmo asks for it.

Takes the Saturday paid build (lev + boom, D12800) and the Sunday T-70 build (lev 0 + boom + class sleeve on the T-70
projections), and writes a NEW run dir beside them in the live results tree:
  * the T-70 pool, unchanged;
  * every Saturday candidate that survives the T-70 information: no player absent from the T-70 frame, none OUT / IR /
    Doubtful / inactive by the T-70 frame (and the DK status snapshot, if given), no skill player projected under
    --min-proj on the T-70 frame (Q4b), the per-game cap respected, and not already in the T-70 pool;
  * optionally --pmo N plain-mean-optimizer rows solved on the T-70 frame (L13's R5 form: sequential MILP on the
    served mean projection, house rules, the per-game cap, the salary floor, <= max-shared with every earlier row);
then builds the book. `--main mean` (the paper arm): the main book = top-K by the sum of the T-70 `mean_projection` under
the overlap cap and the DST cap, exactly as the pinned live_week.py does for --selector mean. `--main pmo_x50` (ENTERS
Week 4, operator 2026-09-28 14:05, L13's SUPPORTED form): the main book = K sequential plain-mean-optimizer solves on the
T-70 frame in solve order (objective the served mean_projection, house rules, the per-game cap, the salary floor,
<= 7 shared with every earlier row, and a per-player exposure cap: a player in >= floor(0.5 K) rows is banned from later
solves, DST included; NO 25% DST cap -- the tested arm had none). Either way the tail sleeve = top-T of the union pool by
projected sum under the overlap cap (it may repeat main rows). Every written roster is revalidated against the DK contract.
A pmo_x50 main that cannot reach K rows REFUSES (exit 2, named); the chain then builds the mean main loudly.

`--main-own-tilt L --main-own-source FILE` (with --main pmo_x50; default 0 = as entered in Week 4): the optimizer's
objective for a skill player becomes mean_projection + L x predicted ownership % (FILE's `pred_own`, the week's blended
ownership file from scripts/ownership_blend.py; DST and players the file does not name get no term). The plain-mean rows
are solved as well: they stay the tail sleeve's supply (so the sleeve is the sleeve of the L = 0 build, row for row) and
are written as `book_main_control.csv`, Monday's paper comparison. An ownership file that is missing, unreadable, holds a
value below -0.5 or a non-number, or covers fewer than --main-own-min-coverage of the pool's skill players projected
>= 5 REFUSES before any solve ("OWN TERM REFUSED", exit 2); the chain then builds the L = 0 union loudly.

The run dir carries the T-70 run's frame, sidecar banks, universe and exposure ledgers unchanged; a union corpus
(`candidates.parquet` with `source_run` = t70 | saturday | pmo | pmo_x50 | pmo_x50_control); `book.csv` / `book.json`; and a receipt copied from the
T-70 run's with `config.union` (both source runs, their receipts' identities and sha256s, the survivor counts), the new
`written` and `candidates`, and the selection receipt. `config.lev` / `config.boom` stay the T-70 run's, so the
after-build watcher promotes the union under the chosen dose like any other run dir; its timestamp is newer than the
T-70 run's, so it is the newest matching book.

    PYTHONPATH=<pinned nfl2 src>:$PROD/src python scripts/union_reselect.py --saturday-run <D12800 run dir> \\
        --t70-run <T-70 run dir> --live-dir <results/live/<season>-w<WW>> --entries K --tail-sleeve T \\
        [--dk-status dk-status-<utc>.csv] [--pmo 0] [--min-proj 1.0] [--mean-dst-cap 0.25] [--max-per-game 4]
    --saturday-run auto picks the newest run dir in --live-dir whose receipt lev/boom equal --saturday-dose (2560/10240).

Fails closed (exit 2, the reason named) on: a T-70 receipt whose selector is not mean, a Saturday run built after the
T-70 run, a frame/bank mismatch, fewer survivors than K + T, a written roster that fails the DK contract, or an output
dir that already exists. Nothing is uploaded; the chain's verify_k90 and audit_build_levers run on the result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r1c_sunday_reselect import BANKS, OUT_STATUSES, unavailable_ids  # noqa: E402
from run_dir_publishable import parse_utc  # noqa: E402
from nfl_dfs.inference.mix_shapes import (RS_BOOK_ROWS as MS_RS_BOOK_ROWS, RS_TIERS as MS_RS_TIERS,  # noqa: E402
                                         block_positions as ms_block_positions, relaxations as ms_relaxations,
                                         tier_bans as ms_tier_bans)
from nfl_dfs.inference.mix_shapes import (MIX_CELLS, PORTFOLIOS, TAG_PREFIX, allocate as mix_allocate, interleave as mix_interleave,  # noqa: E402
                                           plan_weights as mix_weights, shape_violations, cell_of_tag)

SKILL = ("QB", "RB", "WR", "TE")
COPY = ("frame.parquet", "universe_ledger.parquet", "exposure_ledger.json", "book_wemax.csv", "book_wemax.json", *BANKS)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_run(run: Path) -> dict:
    need = ["frame.parquet", "candidates.parquet", "receipt.json", *BANKS]
    missing = [f for f in need if not (run / f).is_file()]
    if missing:
        raise SystemExit(f"{run}: missing {missing}")
    fr = pd.read_parquet(run / "frame.parquet").reset_index(drop=True)
    cands = pd.read_parquet(run / "candidates.parquet").reset_index(drop=True)
    receipt = json.loads((run / "receipt.json").read_text())
    return {"dir": run, "frame": fr, "cands": cands, "receipt": receipt}


def pick_saturday_run(live_dir: Path, lev: int, boom: int, before: str, group: str | None = None, after: str | None = None) -> Path:
    """The newest run dir in live_dir whose receipt lev/boom equal the Saturday dose, built before the T-70 run and (when
    given) after this week's window start, on this week's draft group, with its sidecars, not superseded, not itself a union."""
    hits = []
    for d in sorted(p for p in live_dir.iterdir() if p.is_dir()):
        try:
            r = json.loads((d / "receipt.json").read_text())
        except (OSError, ValueError):
            continue
        c = r.get("config", {})
        if (c.get("lev"), c.get("boom")) != (lev, boom) or c.get("union") or (d / "superseded").is_file():
            continue
        if group is not None and str(r.get("draft_group")) != str(group):
            continue
        try:
            b = parse_utc(r.get("built_utc", ""))
        except (TypeError, ValueError):
            continue
        if b < parse_utc(before) and (after is None or b >= parse_utc(after)) and all((d / x).is_file() for x in BANKS):
            hits.append(d)
    if not hits:
        raise SystemExit(f"no Saturday run dir with lev/boom {lev}/{boom} (sidecars, group {group}, built in [{after}, {before})) under {live_dir}")
    return hits[-1]


def resolve_saturday_run(saturday_run: str, saturday_dose: str, live_dir: Path, t70_receipt: dict, t70_name: str,
                         group: str | None, after: str | None) -> Path:
    """The Saturday supply's run dir. saturday_dose is one dose or an ORDERED list ("2560/10240,1280/5120"; operator
    2026-10-01, cracks audit B): 'auto' takes the newest qualifying run of the first dose, else of the next, and says so
    loudly. A T-70 run that IS any listed Saturday dose gets no union. Anything but 'auto' is the named dir. (Week-4
    smoke 2026-10-01: an if/else mis-nesting overwrote the auto-picked dir with Path('auto').)"""
    doses = [d.strip() for d in str(saturday_dose).split(",") if d.strip()]
    if not doses:
        raise SystemExit("--saturday-dose is empty")
    c = t70_receipt.get("config", {})
    if f"{c.get('lev')}/{c.get('boom')}" in doses:
        raise SystemExit(f"the T-70 run {t70_name} IS a {c.get('lev')}/{c.get('boom')} build (a Saturday supply dose); no union for it")
    if saturday_run != "auto":
        return Path(saturday_run)
    misses = []
    for k, dose in enumerate(doses):
        lev, boom = (int(x) for x in dose.split("/"))
        try:
            d = pick_saturday_run(live_dir, lev, boom, str(t70_receipt.get("built_utc", "")), group=group, after=after)
        except SystemExit as exc:
            misses.append(f"{dose}: {exc}")
            continue
        if k:
            print(f"!!! SATURDAY SUPPLY FALLBACK: {'; '.join(misses)} -> using the {dose} supply {d.name}", flush=True)
        return d
    raise SystemExit("no Saturday supply for any listed dose: " + " | ".join(misses))

def game_cap_ok(ids: list[str], game_of: dict[str, str], cap: int | None) -> bool:
    if cap is None:
        return True
    return max(Counter(game_of[i] for i in ids).values()) <= cap


def survivors(sat_cands: pd.DataFrame, t70: pd.DataFrame, t70_rosters: set[frozenset], min_proj: float, cap: int | None,
              dk_status: pd.DataFrame | None) -> tuple[list[list[str]], list[int], dict]:
    """Saturday candidates that survive the T-70 information; returns (rosters, saturday cand index, counts)."""
    ids_t70 = set(t70.id.astype(str))
    gone = unavailable_ids(t70, dk_status)
    proj = dict(zip(t70.id.astype(str), pd.to_numeric(t70.mean_projection, errors="coerce")))
    pos = dict(zip(t70.id.astype(str), t70.pos.astype(str)))
    game_of = dict(zip(t70.id.astype(str), t70.game_id.astype(str)))
    low = {i for i in ids_t70 if pos[i] in SKILL and not (proj[i] >= min_proj)}
    counts = Counter()
    out_rosters, out_idx = [], []
    for k, cell in enumerate(sat_cands["players"].astype(str)):
        ids = cell.split(",")
        if any(i not in ids_t70 for i in ids):
            counts["dropped_missing_from_t70"] += 1; continue
        if any(i in gone for i in ids):
            counts["dropped_unavailable"] += 1; continue
        if any(i in low for i in ids):
            counts["dropped_below_min_proj"] += 1; continue
        if not game_cap_ok(ids, game_of, cap):
            counts["dropped_game_cap"] += 1; continue
        if frozenset(ids) in t70_rosters:
            counts["dropped_duplicate_of_t70"] += 1; continue
        out_rosters.append(ids); out_idx.append(k); counts["survivors"] += 1
    counts["saturday_pool"] = int(len(sat_cands)); counts["unavailable_players"] = sorted(gone)
    return out_rosters, out_idx, dict(counts)


def projected_sum(rosters: list[list[str]], proj: dict[str, float]) -> np.ndarray:
    out = np.empty(len(rosters))
    for k, ids in enumerate(rosters):
        try:
            out[k] = sum(proj[i] for i in ids)
        except KeyError as exc:
            raise SystemExit(f"roster {k} holds {exc} which the T-70 frame does not project") from None
    if not np.all(np.isfinite(out)):
        raise SystemExit("a roster's projected sum is not finite")
    return out


def frame_players(t70: pd.DataFrame) -> dict[str, dict]:
    """Player dicts in the lab's shape (id, name, pos, team, opp, salary, game_id, proj) by frame id."""
    cols = {"id": t70.id.astype(str), "name": t70.name.astype(str), "pos": t70.pos.astype(str), "team": t70.team.astype(str),
            "opp": t70.opp.astype(str), "salary": pd.to_numeric(t70.salary, errors="coerce").fillna(0).astype(int),
            "game_id": t70.game_id.astype(str), "proj": pd.to_numeric(t70.mean_projection, errors="coerce").fillna(0.0).astype(float)}
    df = pd.DataFrame(cols)
    return {r["id"]: r for r in df.to_dict("records")}


# Study 1 (production reports/2026-10-05-prereg-study1-deconcentration.md): P(a game at pre-lock total rank r is among the
# week's 3 highest-scoring games), 2014-2021 OUTCOMES only; rank 15+ = 0.08. --main-game-cap p3 (default off) caps the
# share of main rows holding >= 3 players from game g at min(0.5, P3[rank_g]); then later solves take <= 2 from g (member_bounds (ids, 0, 2), the pinned lab 32cdb61's form).
GAME_CAP_P3 = {1: 0.409, 2: 0.336, 3: 0.234, 4: 0.241, 5: 0.255, 6: 0.255, 7: 0.153, 8: 0.197, 9: 0.182, 10: 0.182,
               11: 0.095, 12: 0.124, 13: 0.161, 14: 0.080}
GAME_CAP_P3_TAIL = 0.08


def game_row_caps(t70: pd.DataFrame, n: int) -> dict[str, int]:
    """Per game: the most main rows that may hold >= 3 of its players, floor(min(0.5, P3[rank]) * n). Rank = the
    frame's pre-lock game total, highest first, ties by game id."""
    import math
    tot = "game_total" if "game_total" in t70.columns else "total_line"
    g = t70[["game_id", tot]].copy()
    g["game_id"] = g.game_id.astype(str)
    g[tot] = pd.to_numeric(g[tot], errors="coerce")
    g = g.groupby("game_id", as_index=False)[tot].max()
    known = g[g[tot].notna()].sort_values([tot, "game_id"], ascending=[False, True]).reset_index(drop=True)
    caps = {gid: int(math.floor(min(0.5, GAME_CAP_P3.get(i + 1, GAME_CAP_P3_TAIL)) * n)) for i, gid in enumerate(known.game_id)}
    missing = sorted(set(g.game_id) - set(known.game_id))
    if missing:                                                  # no pre-lock total: ranked last, the tail cap (reviewer 10-05)
        print(f"GAME CAP WARNING: no pre-lock total for {missing}; they get the tail cap", file=sys.stderr)
        caps.update({gid: int(math.floor(GAME_CAP_P3_TAIL * n)) for gid in missing})
    return caps


def check_main_rows(rows: list, entries: int, gcaps: dict | None, bonus: dict | None) -> None:
    """The main book must hold `entries` rows. A short solve is refused and named for its cause: the per-game cap when it
    is on (with or without the term), else the ownership term (reviewer 10-05: the refusal is symmetric)."""
    if len(rows) >= entries:
        return
    if gcaps is not None:
        raise SystemExit(f"GAME CAP REFUSED: {len(rows)} of {entries} rows solved under the per-game cap"
                         + (" (with the ownership term)" if bonus else ""))
    raise SystemExit(f"OWN TERM REFUSED: {len(rows)} of {entries} rows solved with the ownership term under the caps; "
                     "the plain-mean main (as entered) stands")


def heavy_games(players) -> set[str]:
    """Study 1: the games a row holds >= 3 players from (QB and DST count, as MAX_PER_GAME counts them)."""
    c = Counter(str(p["game_id"]) for p in players)
    return {g for g, k in c.items() if k >= 3}


OWN_FLOOR_PROJ = 5.0          # coverage of the ownership file is counted over the pool's skill players projected at least this
OWN_TILT_MAX = 0.5            # the tested range is 0.05-0.40 points per ownership point; anything above is a typo


def _key(v: object) -> str:
    """An id as the frame spells it: '1164402.0' and 1164402 are both '1164402'; a missing value is ''."""
    s = str(v).strip()
    if s.lower() in ("", "nan", "none", "<na>"):
        return ""
    return s[:-2] if s.endswith(".0") and s[:-2].isdigit() else s


def own_bonus(source: Path, t70: pd.DataFrame, exclude: set[str], tilt: float, min_coverage: float) -> tuple[dict[str, float], dict]:
    """The ownership term per frame id, in projection points: tilt x predicted ownership % (negatives clipped to 0), skill
    players only. The file is matched on dk_player_id, then on gsis_id / id against the frame's id. Refuses (SystemExit
    'OWN TERM REFUSED: ...') on every gap named in the module docstring; never fills a value in."""
    def refuse(why: str):
        raise SystemExit(f"OWN TERM REFUSED: {why}; the plain-mean main (as entered) stands")
    if not 0 < tilt <= OWN_TILT_MAX:
        refuse(f"--main-own-tilt {tilt} outside (0, {OWN_TILT_MAX}]")
    if source is None or not Path(source).is_file():
        refuse(f"the ownership file {source} does not exist")
    try:
        own = pd.read_csv(source, dtype=str)
    except (OSError, ValueError) as exc:
        refuse(f"the ownership file {source} is unreadable ({exc})")
    keys = [c for c in ("dk_player_id", "gsis_id", "id") if c in own.columns]
    if "pred_own" not in own.columns or not keys:
        refuse(f"the ownership file {source} needs pred_own and one of dk_player_id / gsis_id / id (has {list(own.columns)})")
    val = pd.to_numeric(own.pred_own, errors="coerce")
    if len(own) == 0 or not np.all(np.isfinite(val)):
        refuse(f"the ownership file {source} holds {int((~np.isfinite(val)).sum())} pred_own values that are not numbers (of {len(own)})")
    if float(val.min()) < -0.5:
        refuse(f"the ownership file {source} holds pred_own {float(val.min()):.2f} (below -0.5: not a percentage)")
    if float(val.max()) <= 1.0:
        refuse(f"the ownership file {source} tops out at pred_own {float(val.max()):.3f}: fractions, not percentages")
    clipped = int((val < 0).sum())
    val = val.clip(lower=0.0)
    by = {c: {} for c in keys}
    for c in keys:
        for k, v in zip(own[c].map(_key), val):
            if k:
                by[c][k] = max(v, by[c].get(k, 0.0))            # a player listed twice (two slots) keeps his larger value
    ids = t70.id.astype(str).tolist()
    pos = dict(zip(ids, t70.pos.astype(str)))
    proj = dict(zip(ids, pd.to_numeric(t70.mean_projection, errors="coerce").fillna(0.0)))
    dk_of = dict(zip(ids, t70.dk_player_id.map(_key))) if "dk_player_id" in t70.columns else {}
    found: dict[str, float] = {}
    how: Counter = Counter()
    for i in ids:
        if pos[i] not in SKILL:
            continue
        for c in keys:
            k = dk_of.get(i, "") if c == "dk_player_id" else _key(i)
            if k and k in by[c]:
                found[i] = float(by[c][k]); how[c] += 1
                break
    core = [i for i in ids if pos[i] in SKILL and i not in exclude and proj[i] >= OWN_FLOOR_PROJ]
    covered = sum(1 for i in core if i in found)
    coverage = covered / len(core) if core else 0.0
    if coverage < min_coverage:
        miss = sorted((i for i in core if i not in found), key=lambda i: -proj[i])[:8]
        name = dict(zip(ids, t70.name.astype(str)))
        refuse(f"the ownership file {source} names {covered} of the pool's {len(core)} skill players projected >= {OWN_FLOOR_PROJ} "
               f"({coverage:.1%} < {min_coverage:.0%}); missing e.g. {[name[i] for i in miss]}")
    bonus = {i: tilt * v for i, v in found.items() if v > 0 and i not in exclude}
    top = sorted(bonus, key=lambda i: -bonus[i])[:5]
    name = dict(zip(ids, t70.name.astype(str)))
    meta = {"tilt": tilt, "source": str(source), "source_sha256": sha256_file(Path(source)), "file_rows": int(len(own)),
            "matched_skill_players": len(found), "matched_by": dict(how), "coverage_projected_5": round(coverage, 4),
            "min_coverage": min_coverage, "negatives_clipped": clipped, "players_with_a_term": len(bonus),
            "largest_terms": [{"id": i, "name": name[i], "pred_own": round(found[i], 2), "points": round(bonus[i], 2)} for i in top]}
    return bonus, meta


def pmo_rows(t70: pd.DataFrame, exclude: set[str], n: int, max_shared: int, cap: int | None, min_salary: int,
             existing: set[frozenset], exposure_cap: int | None = None, dst_cap: int | None = None,
             bonus: dict[str, float] | None = None, game_caps: dict[str, int] | None = None,
             qb_cap: int | None = None) -> list[list[str]]:
    """Plain-mean-optimizer rows on the T-70 frame (L13's R5 form), skipping rosters already in the pool. With
    exposure_cap (L13's PMO_X50: max(1, N // 2)), a player already in that many PMO rows is banned from later solves --
    the form L13 SUPPORTED at p89 (+27.7% tickets vs MEAN, both seasons); the uncapped form was NOT SUPPORTED. With
    bonus (own_bonus), the objective is the projection plus the player's ownership term; without it, the call is the
    one entered in Week 4."""
    from nfl2.core.lineup import optimize                      # the pinned lab clone on PYTHONPATH
    from nfl2.pipeline import PRODUCTION_STACK
    pool = [p for i, p in frame_players(t70).items() if i not in exclude]
    objective = "proj"
    if bonus:
        pool = [dict(p, obj=p["proj"] + float(bonus.get(p["id"], 0.0))) for p in pool]
        objective = "obj"
    dst_ids = {p["id"] for p in pool if p["pos"] == "DST"}
    qb_ids = {p["id"] for p in pool if p["pos"] == "QB"}
    env = {"MIN_LINEUP_SALARY": str(min_salary)}
    if cap is not None:
        env["MAX_PER_GAME"] = str(cap)
    prev: list[frozenset] = [frozenset(r) for r in existing]
    rows: list[list[str]] = []
    count: Counter = Counter()
    heavy: Counter = Counter()                                  # study 1: rows holding >= 3 players from a game
    by_game: dict[str, list] = {}
    for p in pool:
        by_game.setdefault(str(p["game_id"]), []).append(p["id"])
    tries = 0
    while len(rows) < n and tries < 3 * n:
        tries += 1
        bans = {p for p, c in count.items() if exposure_cap is not None and c >= exposure_cap}
        if dst_cap is not None:
            bans |= {p for p, c in count.items() if p in dst_ids and c >= dst_cap}
        if qb_cap is not None:                                  # study 35's per-QB cap (10-06; default off)
            bans |= {p for p, c in count.items() if p in qb_ids and c >= qb_cap}
        bans = bans or None
        sets = None
        if game_caps is not None:
            full = sorted(g for g, c in heavy.items() if c >= game_caps.get(g, n))
            sets = [(by_game[g], 0, 2) for g in full if g in by_game] or None    # the pinned lab's member_bounds: (ids, lo, hi)
        lu = optimize(pool, stack=PRODUCTION_STACK, objective_col=objective, banned_lineups=prev, max_overlap=max_shared, bans=bans, env=env,
                      **({"member_bounds": sets} if sets else {}))
        if lu is None:
            break
        ids = [str(p["id"]) for p in lu.players]
        prev.append(frozenset(ids))
        if frozenset(ids) in existing:
            continue
        rows.append(ids); existing.add(frozenset(ids)); count.update(ids)
        heavy.update(heavy_games(lu.players))
    if len(rows) < n:
        print(f"PMO: {len(rows)} of {n} rows solved (the frame ran out of distinct legal rows under the caps)", file=sys.stderr)
    return rows


class _LU:                                                   # what dk_csv / validate need from a lineup
    def __init__(self, players: list[dict], tag: str):
        self.players, self.tag = players, tag

    @property
    def salary(self) -> int:
        return int(sum(p["salary"] for p in self.players))



def select_top_mean_player_cap(scores, rosters, k: int, max_shared: int | None, player_cap: int, pre: tuple = ()) -> list[int]:
    """The pinned lab's select_top_mean (greedy top-k by score, ties by index, a repeated roster skipped, pairwise overlap
    <= max_shared) plus a per-player exposure cap: a row is skipped when any of its players already sits in player_cap
    chosen rows. Used only when the tail sleeve's cap is set (UNION_SLEEVE_CAP); without it the lab's function runs as
    before. Raises RuntimeError on a shortfall, as the lab's does."""
    s = np.asarray(scores, dtype=float)
    if len(s) != len(rosters):
        raise ValueError(f"{len(s)} scores for {len(rosters)} rosters")
    if not np.all(np.isfinite(s)):
        raise ValueError("scores must be finite")
    if player_cap < 1:
        raise ValueError(f"player_cap must be >= 1 (got {player_cap})")
    # `pre` (the field sleeve's split, 10-02): rows already in the sleeve; they count toward k, the overlap and the cap
    chosen: list[int] = list(pre)
    taken: list[frozenset] = [rosters[i] for i in pre]
    seen: set[frozenset] = set(taken)
    n_in: Counter = Counter(p for r in taken for p in r)
    if len(chosen) >= k:
        return chosen[:k]
    for i in sorted(range(len(s)), key=lambda j: (-s[j], j)):
        r = rosters[i]
        if r in seen:
            continue
        if any(n_in[p] >= player_cap for p in r):
            continue
        if max_shared is not None and any(len(r & t) > max_shared for t in taken):
            continue
        chosen.append(i); taken.append(r); seen.add(r); n_in.update(r)
        if len(chosen) == k:
            return chosen
    raise RuntimeError(f"tail sleeve: only {len(chosen)} rows satisfy the overlap cap (max_shared={max_shared}) and the "
                       f"player cap ({player_cap}); {k} required")


def sleeve_exposure(rows: list[int], rosters, fr) -> dict:
    """Outcome-blind concentration of a book slice: max rows per player and the five most-used players (id, name, rows)."""
    n = Counter(p for i in rows for p in rosters[i])
    name = dict(zip(fr.id.astype(str), fr.name.astype(str)))
    return {"rows": len(rows), "distinct_players": len(n), "max_rows_per_player": max(n.values()) if n else 0,
            "top5": [{"id": p, "name": name.get(p), "rows": c} for p, c in n.most_common(5)]}


def main_exposure_cap(share: float, k: int) -> int:
    """The main book's per-player exposure cap in rows: a player in this many rows is banned from later solves.
    int(share * K) with a floor of 1, the form L13 and L17 tested (0.5 at K = 36 -> 18)."""
    if not 0 < share <= 1:
        raise ValueError(f"exposure cap share must be in (0, 1] (got {share})")
    return max(1, int(share * k))


def apply_proj_source(fr: pd.DataFrame, csv_path: Path, frame_path: Path) -> tuple[pd.DataFrame, dict]:
    """--proj-source (operator 2026-10-05: Fantasy Points' projections replace ours): the override file written by
    scripts/fp_projection_override.py FOR THIS FRAME (its sidecar names the frame's sha256; any other frame REFUSES). The
    frame's mean_projection is replaced for every player the file holds; the rest keep ours; ours stays beside it as
    mean_projection_ours. Everything downstream (the pool's projection floor, the main or mix solves, the sleeve's
    projected sums) reads the replaced column. The simulations (banks) stay ours: FP gives a mean only."""
    meta_path = Path(str(csv_path) + ".json")
    if not (Path(csv_path).is_file() and meta_path.is_file()):
        raise SystemExit(f"PROJ SOURCE REFUSED: {csv_path} or its .json sidecar is missing")
    meta = json.loads(meta_path.read_text())
    if meta.get("frame_sha256") != sha256_file(frame_path):
        raise SystemExit(f"PROJ SOURCE REFUSED: {csv_path} was built for another frame ({str(meta.get('frame_sha256'))[:12]})")
    if meta.get("csv_sha256") != sha256_file(Path(csv_path)):
        raise SystemExit(f"PROJ SOURCE REFUSED: {csv_path} does not match its sidecar's sha256")
    ov = pd.read_csv(csv_path, dtype={"id": str})
    fp = dict(zip(ov["id"].astype(str), pd.to_numeric(ov["fp"], errors="coerce")))
    if any(not np.isfinite(v) for v in fp.values()):
        raise SystemExit(f"PROJ SOURCE REFUSED: {csv_path} holds a non-number")
    out = fr.copy()
    out["mean_projection_ours"] = out["mean_projection"]
    ids = out["id"].astype(str)
    hit = ids.isin(set(fp))
    out.loc[hit, "mean_projection"] = ids[hit].map(fp).astype(float)
    return out, {"file": str(csv_path), "sha256": sha256_file(Path(csv_path)), "capture": meta.get("capture"),
                 "gates": {k: v for k, v in (meta.get("gates") or {}).items() if k != "top15_abs_diff"},
                 "before_inactives": meta.get("before_inactives"), "replaced": int(hit.sum()), "kept_ours": int((~hit).sum()),
                 "note": "FP's mean replaces ours in selection; the simulations (banks) stay ours"}


LATE_SCRATCH_RULE = ("nfl_dfs.inference.cascade_adjust.find_t70_vacated_targets on the frame with ONLY the late scratches "
                     "marked OUT: the depth-2 same-position teammate of a depth-1 RB / WR / TE scratch gets T70_VACATED_TABLE's "
                     "gross (RB +1.6, TE +1.6, WR +0.7), the next-man-up bump production's T-70 project-slate adds when it sees "
                     "the scratch (T70_VACATED_BUMP=1; in Week 4 it equalled the gross for 5 of 5 targets, the model cascade's "
                     "share being smaller). Not reproduced: the model cascade's smaller spread to other teammates, and the "
                     "backup-QB path")


def _late_banner(msg: str) -> None:
    print("!" * 80 + f"\n!!! LATE-SCRATCH BUMP: {msg}\n" + "!" * 80, flush=True)


def late_scratch_bump(fr: pd.DataFrame, fp: dict[str, float] | None, dk_status: pd.DataFrame | None,
                      min_fp: float) -> tuple[pd.DataFrame, dict]:
    """--proj-source-late-scratch-bump (the outside reviewer 2026-10-08; default off). FP's numbers replace ours, but FP's
    last Sunday update can predate a scratch (Week 4: 08:58 CT, before the 10:30 inactives). The scratched player is still
    removed (unavailable_ids), yet his teammates keep FP's pre-news numbers. Here a LATE SCRATCH is a frame skill player
    unavailable_ids() marks out (the frame's statuses + the --dk-status snapshot) whom FP still projects at or above
    `min_fp`, so FP has not processed the scratch. A scratch FP already projects under it adds nothing. Each late scratch's
    next-man-up bump (LATE_SCRATCH_RULE) is added to the teammate's FP number. A teammate is never bumped when he is
    himself unavailable, has no FP number (ours is kept, untouched), or sits under `min_fp` (a bump never resurrects a
    player the source has below the pool's floor). mean_projection_ours is never changed.

    Returns (frame, record). Missing inputs or any error: the frame comes back UNCHANGED with a banner and record['not_applied']
    (the build never fails here). Without a --dk-status snapshot a banner says the step is blind to scratches posted after
    the frame's DK pull: that pull already removed its O / IR / D players from the frame (O-16)."""
    rec: dict = {"applied": False, "rule": LATE_SCRATCH_RULE, "min_fp": float(min_fp), "dk_status": dk_status is not None,
                 "late_scratches": [], "bumps": [], "skipped": [], "fp_already_processed": [], "total_points": 0.0}

    def noop(why: str) -> tuple[pd.DataFrame, dict]:
        _late_banner(f"NOT APPLIED -- {why}; the projections are used unchanged")
        rec["not_applied"] = why
        return fr, rec

    if fp is None:
        return noop("the FP override file could not be read")
    need = {"id", "team", "pos", "depth_rank", "mean_projection", "mean_projection_ours"}
    if not need <= set(fr.columns):
        return noop(f"the frame lacks {sorted(need - set(fr.columns))} (mean_projection_ours = the FP source was applied)")
    try:
        from nfl_dfs.inference import cascade_adjust as CA
        ids = fr["id"].astype(str).reset_index(drop=True)
        if ids.duplicated().any():
            return noop("the frame repeats an id")
        pos = fr["pos"].astype(str).str.upper().reset_index(drop=True)
        team = fr["team"].astype(str).reset_index(drop=True)
        depth = pd.to_numeric(fr["depth_rank"], errors="coerce").astype(float).reset_index(drop=True)
        cur = pd.to_numeric(fr["mean_projection"], errors="coerce").astype(float).reset_index(drop=True)
        nm = fr["name"] if "name" in fr else fr.get("display_name", fr["id"])
        name = dict(zip(ids, nm.astype(str)))
        at = {i: k for k, i in enumerate(ids)}
        dep = lambda i: None if np.isnan(depth[at[i]]) else int(depth[at[i]])  # noqa: E731
        if dk_status is None:
            _late_banner("NO --dk-status SNAPSHOT: only the frame's own statuses are read, and the frame's DK pull already "
                         "removed its O / IR / D players, so a scratch DK posts AFTER that pull is INVISIBLE here (O-16)")
        gone = unavailable_ids(fr, dk_status)
        fpv = {str(i): float(v) for i, v in fp.items() if v is not None and np.isfinite(v)}
        scratches: list[str] = []
        for i in sorted(gone):
            if i not in at or pos[at[i]] not in SKILL:
                continue
            who = {"id": i, "name": name[i], "pos": pos[at[i]], "team": team[at[i]], "depth_rank": dep(i), "fp": fpv.get(i)}
            if i not in fpv:
                rec["skipped"].append({**who, "why": "no FP number for the scratch (FP's view of him unknown)"})
            elif fpv[i] < min_fp:
                rec["fp_already_processed"].append(who)        # FP already has him (near) zero: its teammates' numbers moved
            else:
                scratches.append(i); rec["late_scratches"].append(who)
        st = (fr["status"] if "status" in fr else pd.Series("", index=fr.index)).fillna("").astype(str).str.upper().str.strip()
        inj = (fr["injury_status"] if "injury_status" in fr else pd.Series("", index=fr.index)).fillna("").astype(str).str.upper().str.strip()
        absent = set(ids[(st.isin(CA.ABSENT_STATUSES) | inj.isin({"OUT", "DOUBTFUL"})).to_numpy()])
        g = pd.DataFrame({"gsis_id": ids, "team": team, "position": pos, "depth_rank": depth,
                          "status": np.where(ids.isin(scratches), "OUT", ""), "injury_status": ""})
        gross = CA.find_t70_vacated_targets(g) if scratches else {}
        for s in scratches:
            if pos[at[s]] == "QB":
                rec["skipped"].append({"scratch": name[s], "scratch_id": s, "why": "QB: the backup-QB path is not reproduced here"})
            elif dep(s) != 1:
                rec["skipped"].append({"scratch": name[s], "scratch_id": s,
                                       "why": f"depth_rank {dep(s)}: the T-70 rule bumps only a depth-1 starter's depth-2 teammate"})
            elif not any(team[at[m]] == team[at[s]] and pos[at[m]] == pos[at[s]] for m in gross):
                rec["skipped"].append({"scratch": name[s], "scratch_id": s, "why": "no depth-2 same-position teammate on the slate"})
        out = fr.copy()
        col = out.columns.get_loc("mean_projection")
        for m, pts in sorted(gross.items()):
            k = at[m]
            by = [s for s in scratches if team[at[s]] == team[k] and pos[at[s]] == pos[k] and dep(s) == 1]
            entry = {"teammate": name[m], "teammate_id": m, "pos": pos[k], "team": team[k],
                     "scratch": [name[s] for s in by], "scratch_id": by, "points": round(float(pts), 4)}
            if m in gone or m in absent:
                rec["skipped"].append({**entry, "why": "the teammate is himself unavailable"})
            elif m not in fpv:
                rec["skipped"].append({**entry, "why": "the teammate has no FP number: ours is kept (not bumped twice)"})
            elif not cur[k] >= min_fp:
                rec["skipped"].append({**entry, "why": f"FP has him at {cur[k]:.2f}, under {min_fp}: never resurrected"})
            else:
                after = float(cur[k]) + float(pts)
                out.iat[k, col] = after
                rec["bumps"].append({**entry, "before": round(float(cur[k]), 4), "after": round(after, 4)})
                print(f"LATE-SCRATCH BUMP: {name[m]} ({pos[k]} {team[k]}) +{pts:.2f} for {' / '.join(name[s] for s in by)} "
                      f"(out, FP still {', '.join(f'{fpv[s]:.2f}' for s in by)}): {cur[k]:.2f} -> {after:.2f}", flush=True)
        rec["total_points"] = round(sum(b["points"] for b in rec["bumps"]), 4)
        rec["applied"] = True
        print(f"LATE-SCRATCH BUMP: {len(scratches)} late scratch(es) FP still projects >= {min_fp} (of {len(gone)} unavailable "
              f"frame players; {len(rec['fp_already_processed'])} FP already has under it); {len(rec['bumps'])} teammate(s) "
              f"bumped, {rec['total_points']:.2f} points; {len(rec['skipped'])} skipped (named in the receipt)", flush=True)
        return out, rec
    except Exception as exc:                                   # noqa: BLE001 -- a refinement never stops the build
        rec.update({"bumps": [], "total_points": 0.0})
        return noop(f"{type(exc).__name__}: {exc}")


def late_scratch_bump_step(fr: pd.DataFrame, proj_source: Path | None, proj_meta: dict, dk_status: pd.DataFrame | None,
                           min_fp: float) -> pd.DataFrame:
    """main()'s call, made only with --proj-source-late-scratch-bump: reads the override file apply_proj_source verified, runs
    late_scratch_bump, and records it as proj_meta['late_scratch_bump'] (the receipt's config.union.proj_source). Without
    a projection source in use there is nothing to bump: a banner, the frame unchanged, nothing recorded."""
    if not proj_meta or proj_source is None:
        _late_banner("NOT APPLIED -- no projection source is in use (--proj-source absent or refused): ours is used, "
                     "nothing was overwritten")
        return fr
    try:
        ov = pd.read_csv(proj_source, dtype={"id": str})
        fp: dict[str, float] | None = dict(zip(ov["id"].astype(str), pd.to_numeric(ov["fp"], errors="coerce")))
    except Exception:                                          # noqa: BLE001 -- late_scratch_bump names it and does nothing
        fp = None
    fr, proj_meta["late_scratch_bump"] = late_scratch_bump(fr, fp, dk_status, min_fp)
    return fr


def parse_cell_quotas(spec: str) -> dict[str, float]:
    """--mix-cell-quotas "A1=0.40,A2=0.26,B=0.17,C=0.17" (study 56; the operator 10-07, his priority test this week):
    the MIX cells' entry quotas in place of mix_shapes.MIX_CELLS'. Exactly the four MIX cells, every value > 0, the sum 1
    (within 1e-9); anything else raises ValueError. The cells' RULES are unchanged."""
    out: dict[str, float] = {}
    for part in str(spec).split(","):
        name, sep, val = part.strip().partition("=")
        if not sep or not name.strip():
            raise ValueError(f"--mix-cell-quotas: {part!r} is not CELL=QUOTA")
        name = name.strip()
        if name in out:
            raise ValueError(f"--mix-cell-quotas: {name} given twice")
        try:
            out[name] = float(val)
        except ValueError:
            raise ValueError(f"--mix-cell-quotas: {name}={val!r} is not a number") from None
    if set(out) != set(MIX_CELLS):
        raise ValueError(f"--mix-cell-quotas: the cells must be exactly {sorted(MIX_CELLS)} (got {sorted(out)})")
    if any(not v > 0 for v in out.values()):
        raise ValueError("--mix-cell-quotas: every quota must be > 0")
    if abs(sum(out.values()) - 1.0) > 1e-9:
        raise ValueError(f"--mix-cell-quotas: the quotas sum to {sum(out.values())}, not 1")
    return {n: out[n] for n in MIX_CELLS}


def mix_rows(t70: pd.DataFrame, exclude: set[str], k: int, max_shared: int, cap: int | None, min_salary: int,
             weights: list[int], exposure_cap: int | None = None, dst_cap: int | None = None,
             bonus: dict[str, float] | None = None, portfolio: str = "mix",
             spares: int = 0, qb_cap: int | None = None, fill: str = "group", cover_games: int = 0,
             rs_rows: int = 0, term_rows: int = 0,
             term_bonus: dict[str, float] | None = None,
             cell_quotas: dict[str, float] | None = None) -> tuple[list[list[str]], list[str], dict, list[tuple[list[str], str]]]:
    """study 18's MIX book on the T-70 frame: cells solved largest first (ties: the earlier cell) through ONE shared state
    (banned lineups, the per-player exposure cap, the DST cap, <= max_shared with every earlier row); a cell row that cannot
    be solved passes to A1 (counted); then the rows are ordered by the entry-weighted interleave of the plan's weights.
    Returns (rows in book order, each row's cell, meta, spares). s18's mix_book with production's objective
    (mean_projection, or mean_projection + the ownership term with bonus), production's caps and env.
    spares (reviewer 2026-10-06, the blocking finding: a WS row could not be replaced on Sunday, since no house candidate
    fits WS): AFTER the k book rows, `spares` more rows are solved through the SAME running state (banned lineups, counts),
    with the caps the caller computed from the book's entries (never from k + spares), allocated over the cells by quota
    (ws: all WS), with the same pass to A1. They are never book rows: the caller adds them to the candidate corpus as the
    Sunday replacement step's in-shape supply. A short spare tail is not a refusal (meta records requested / built). The
    book rows are identical with or without spares (they are solved first).
    fill (the operator 10-06: "are we putting our best strategy first for a given QB?"; study 42): "group" (default, as
    before) solves each cell's quota consecutively, largest cell first, so a capped QB's or player's uses go to the EARLIEST
    cells; "value" PEEKS the next row of every cell with quota left on the current state and COMMITS the highest-objective
    one (ties: the earlier cell in the group order), repeating until the quotas are met -- the capped uses go to the best
    rows across cells. A cell that cannot solve passes its remaining quota to A1 (counted); A1 failing ends the fill.
    "rr" (round-robin; the outside reviewer 10-06, the winners' shapes follow the game script, not the QB) takes the cells
    in the group order in turn, one row each while its quota lasts, so the top QBs get a row in each shape; the same pass
    to A1. The caps, overlap, quotas, interleave and spares are unchanged in every fill.
    cover_games N (study 43; the operator 10-06 "study 43 sounds the most interesting"; default 0 = off, byte for byte
    today's book): BEFORE any fill, for each of the pool's top-N games by pre-lock game_total (highest first, ties by game
    id), one A1 row with every QB NOT in that game banned for that solve, committed through the shared state and counted
    toward A1's quota; a game whose row cannot be built, or with A1's quota used up, is recorded as missed. Then the fill
    runs on the remaining quotas; then, only if a coverage row exists, A1's rows are ordered by objective sum, descending
    and stable (a coverage row takes the deal position its projection earns).
    rs_rows n (study 46, the half-and-half book; the operator 10-06 "keep working on this until you figure out a strategy
    like that person's strategy that works"; default 0 = off, byte for byte today's book): THE RULES of the lab's frozen
    experiments/s46_half_half.py -- (1) one state: the player / DST / QB caps and the overlap limit count every row;
    (2) the live block (k - n rows) fills FIRST, round-robin on the quotas at ITS size; (3) then the RS block (n rows),
    round-robin on the quotas at its size, with the regulars' tiers (mix_shapes.RS_TIERS[n]) on the RS block's OWN rows:
    hard block caps, and an infeasible RS row solved with the fewest tiers dropped (study 37's order), recorded;
    (4) positions: mix_shapes.block_positions; (5) each block interleaved on the head weights of ITS positions;
    (6) the spares after the book, without tiers. Needs the MIX portfolio, the round-robin fill, no cover, k 26.
    term_rows n with term_bonus (the prior-top term block; the operator 10-07: "Live, capped, part of book"; default 0 =
    off, byte for byte today's book): study 46's block mechanics with an objective in place of the tiers -- one state (caps,
    QB cap, overlap); the live block (k - n rows) fills FIRST, round-robin on the quotas at its size, on the plain
    objective; then the term block (n rows), round-robin on the quotas at its size, on projection + term_bonus (points per
    frame id, already capped by the caller); positions mix_shapes.block_positions(k, n) (the term block takes the first
    list); each block interleaved on the head weights of ITS positions; the spares after the book on the plain objective.
    Needs the MIX portfolio, the round-robin fill, no cover, no half-and-half and no whole-book ownership term."""
    from nfl2.core.lineup import StackRules, optimize          # the pinned lab clone on PYTHONPATH (>= f69598b)
    pool = [p for i, p in frame_players(t70).items() if i not in exclude]
    objective = "proj"
    if bonus:
        pool = [dict(p, obj=p["proj"] + float(bonus.get(p["id"], 0.0))) for p in pool]
        objective = "obj"
    dst_ids = {p["id"] for p in pool if p["pos"] == "DST"}
    qb_ids = {p["id"] for p in pool if p["pos"] == "QB"}
    games = sorted({str(p["game_id"]) for p in pool if p["pos"] in SKILL})    # the REAL game ids (skill rows)
    env = {"MIN_LINEUP_SALARY": str(min_salary)}
    if cap is not None:
        env["MAX_PER_GAME"] = str(cap)
    cells = PORTFOLIOS[portfolio]                              # mix: study 18's MIX cells; ws: one whole-book cell
    names = list(cells)
    quotas = [cells[n][0] for n in names]
    if cell_quotas is not None:                               # study 56's switch (default None: MIX_CELLS, as before)
        if portfolio != "mix" or set(cell_quotas) != set(names):
            raise ValueError(f"cell_quotas {sorted(cell_quotas)} need the MIX portfolio's cells {names} (got portfolio {portfolio})")
        quotas = [float(cell_quotas[n]) for n in names]      # every allocate / interleave below reads this one list
    target = mix_allocate(quotas, k)
    prev: list[frozenset] = []
    count: Counter = Counter()
    rows: dict[str, list[list[str]]] = {n: [] for n in names}
    passes = 0

    term_pool = None
    if term_rows:
        if portfolio != "mix" or fill != "rr" or cover_games or rs_rows or bonus or not term_bonus or not 0 < term_rows < k:
            raise ValueError(f"term_rows {term_rows} needs the MIX portfolio, fill rr, no cover / half / whole-book term, a "
                             f"term_bonus and 0 < n < k (got portfolio {portfolio}, fill {fill}, cover {cover_games}, "
                             f"rs {rs_rows}, bonus {bool(bonus)}, term players {len(term_bonus or {})}, k {k})")
        term_pool = [dict(p, obj=p["proj"] + float(term_bonus.get(p["id"], 0.0))) for p in pool]

    def peek(name: str, extra_bans: frozenset = frozenset(), use_term: bool = False):
        """The cell's next row on the CURRENT state, not committed: (ids, objective value) or (None, None). use_term: on the
        term block's objective (projection + the capped term)."""
        _, rules, qmax, which = cells[name]
        bans = {p for p, c in count.items() if exposure_cap is not None and c >= exposure_cap} | set(extra_bans)
        if dst_cap is not None:
            bans |= {p for p, c in count.items() if p in dst_ids and c >= dst_cap}
        if qb_cap is not None:                                  # study 35's per-QB cap (10-06; default off)
            bans |= {p for p, c in count.items() if p in qb_ids and c >= qb_cap}
        use_pool, use_obj = (term_pool, "obj") if use_term else (pool, objective)
        lu = optimize(use_pool, stack=StackRules(**rules), objective_col=use_obj, banned_lineups=prev, max_overlap=max_shared,
                      bans=bans or None, env=env, second_game_pair=games if which == "all" else None, qb_game_max=qmax)
        if lu is None:
            return None, None
        return [str(p["id"]) for p in lu.players], float(sum(p.get(use_obj, p["proj"]) for p in lu.players))

    row_value: dict[tuple, float] = {}                         # each committed row's objective sum, as solved (a term row's
                                                               # includes its term; read only to order cover rows, refused with the block)

    def commit(ids: list[str], value: float | None = None) -> list[str]:
        prev.append(frozenset(ids)); count.update(ids)
        if value is not None:
            row_value[tuple(ids)] = value
        return ids

    def solve(name: str, extra_bans: frozenset = frozenset(), use_term: bool = False):
        ids, v = peek(name, extra_bans, use_term)
        return commit(ids, v) if ids is not None else None

    group_order = sorted(range(len(names)), key=lambda i: (-target[i], i))
    commit_order: list[str] = []
    left = dict(zip(names, target))                            # quotas still to fill (the coverage rows use A1's first)
    cover_list, covered, cover_missed = [], [], []
    if rs_rows and (portfolio != "mix" or fill != "rr" or cover_games or k != MS_RS_BOOK_ROWS or rs_rows not in MS_RS_TIERS):
        raise ValueError(f"rs_rows {rs_rows} needs the MIX portfolio, fill rr, no cover and a {MS_RS_BOOK_ROWS}-row book "
                         f"(rs_rows in {sorted(MS_RS_TIERS)}); got portfolio {portfolio}, fill {fill}, cover {cover_games}, k {k}")
    if cover_games:
        if "A1" not in cells:
            raise ValueError("cover_games needs the MIX portfolio (an A1 cell)")
        if "game_total" not in t70.columns:
            raise SystemExit("COVER REFUSED: the T-70 frame has no game_total (the pre-lock total ranks the games)")
        pool_ids = {p["id"] for p in pool}
        gt = t70[t70.id.astype(str).isin(pool_ids)][["game_id", "game_total"]].copy()
        gt["game_id"] = gt.game_id.astype(str); gt["game_total"] = pd.to_numeric(gt.game_total, errors="coerce")
        gt = gt.dropna().drop_duplicates("game_id").sort_values(["game_total", "game_id"], ascending=[False, True])
        cover_list = [str(g) for g in gt.game_id.tolist()[:int(cover_games)]]
        qb_game = {p["id"]: str(p["game_id"]) for p in pool if p["pos"] == "QB"}
        for g in cover_list:                                   # coverage first: an A1 row with its QB from game g
            if left["A1"] <= 0:
                cover_missed.append(g); continue
            ids = solve("A1", frozenset(q for q, gg in qb_game.items() if gg != g))
            if ids is None:
                cover_missed.append(g); continue
            rows["A1"].append(ids); left["A1"] -= 1; covered.append(g); commit_order.append("A1")
    blocks: list[str] = []
    rs_meta: dict = {}
    term_meta: dict = {}
    if rs_rows:                                                # study 46: two blocks through the one state
        nonqb_ids = {p["id"] for p in pool if p["pos"] not in ("QB", "DST")}
        qcap_b, qt0, ncap_b, nt0 = MS_RS_TIERS[rs_rows]
        rs_count: Counter = Counter()
        relaxed: list = []
        rs_done = [0]                                          # RS rows committed so far (the relaxed record's index)

        def solve_rs(name: str):
            hard = {q for q in qb_ids if rs_count.get(q, 0) >= qcap_b} | {q for q in nonqb_ids if rs_count.get(q, 0) >= ncap_b}
            for qt, nt, dn, dq in ms_relaxations(qt0, nt0):
                ids, v = peek(name, frozenset(hard | ms_tier_bans(rs_count, qb_ids, qt) | ms_tier_bans(rs_count, nonqb_ids, nt)))
                if ids is not None:
                    if dn or dq:
                        relaxed.append([rs_done[0], dn, dq])
                    commit(ids, v); rs_count.update(ids); rs_done[0] += 1
                    return ids
            return None

        def fill_block(n_rows: int, rs: bool, tag: str) -> tuple[dict, list[int], dict]:
            tb = mix_allocate(quotas, n_rows)
            order_b = sorted(range(len(names)), key=lambda i: (-tb[i], i))
            rem = dict(zip(names, tb)); rows_b: dict = {n: [] for n in names}; mb = {"passes": 0, "dropped": 0}
            while any(rem[n] > 0 for n in names):
                for i in order_b:
                    n = names[i]
                    if rem[n] <= 0:
                        continue
                    ids = solve_rs(n) if rs else solve(n)
                    if ids is None:
                        if n == "A1":
                            mb["dropped"] += rem["A1"]; rem["A1"] = 0
                        else:
                            mb["passes"] += rem[n]; rem["A1"] += rem[n]; rem[n] = 0
                        continue
                    rows_b[n].append(ids); rem[n] -= 1; commit_order.append(tag + n)
            return rows_b, tb, mb

        rs_pos, live_pos = ms_block_positions(k, rs_rows)
        live_rows, live_t, live_m = fill_block(len(live_pos), False, "L:")
        rs_rows_b, rs_t, rs_m = fill_block(len(rs_pos), True, "R:")
        slots: dict = {}
        for P, rows_b, tag in ((live_pos, live_rows, "L"), (rs_pos, rs_rows_b, "R")):
            got_b = [len(rows_b[n]) for n in names]
            seq_b = mix_interleave(got_b, quotas, [weights[q] if q < len(weights) else 0 for q in P])
            ptr = [0] * len(names)
            for q, j in zip(P, seq_b):
                slots[q] = (rows_b[names[j]][ptr[j]], names[j], tag); ptr[j] += 1
        for n in names:
            rows[n] = live_rows[n] + rs_rows_b[n]
        passes = live_m["passes"] + rs_m["passes"]
        rs_meta = {"rs_rows": rs_rows, "rs_positions": rs_pos, "relaxed": relaxed,
                   "live_block": {"target_rows": dict(zip(names, live_t)), "cell_rows": {n: len(live_rows[n]) for n in names}, **live_m},
                   "rs_block": {"target_rows": dict(zip(names, rs_t)), "cell_rows": {n: len(rs_rows_b[n]) for n in names}, **rs_m},
                   "tiers": {"qb_cap": qcap_b, "qb_tiers": qt0, "nonqb_cap": ncap_b, "nonqb_tiers": nt0}}
    elif term_rows:                                            # the prior-top term block: two blocks through the one state
        def fill_term_block(n_rows: int, use_term: bool, tag: str) -> tuple[dict, list[int], dict]:
            tb = mix_allocate(quotas, n_rows)
            order_b = sorted(range(len(names)), key=lambda i: (-tb[i], i))
            rem = dict(zip(names, tb)); rows_b: dict = {n: [] for n in names}; mb = {"passes": 0, "dropped": 0}
            while any(rem[n] > 0 for n in names):
                for i in order_b:
                    n = names[i]
                    if rem[n] <= 0:
                        continue
                    ids = solve(n, use_term=use_term)
                    if ids is None:
                        if n == "A1":
                            mb["dropped"] += rem["A1"]; rem["A1"] = 0
                        else:
                            mb["passes"] += rem[n]; rem["A1"] += rem[n]; rem[n] = 0
                        continue
                    rows_b[n].append(ids); rem[n] -= 1; commit_order.append(tag + n)
            return rows_b, tb, mb

        t_pos, live_pos = ms_block_positions(k, term_rows)
        live_rows, live_t, live_m = fill_term_block(len(live_pos), False, "L:")
        term_rows_b, term_t, term_m = fill_term_block(len(t_pos), True, "T:")
        slots = {}
        for P, rows_b, tag in ((live_pos, live_rows, "L"), (t_pos, term_rows_b, "T")):
            got_b = [len(rows_b[n]) for n in names]
            seq_b = mix_interleave(got_b, quotas, [weights[q] if q < len(weights) else 0 for q in P])
            ptr = [0] * len(names)
            for q, j in zip(P, seq_b):
                slots[q] = (rows_b[names[j]][ptr[j]], names[j], tag); ptr[j] += 1
        for n in names:
            rows[n] = live_rows[n] + term_rows_b[n]
        passes = live_m["passes"] + term_m["passes"]
        tb_sorted = sorted(term_bonus.items(), key=lambda t: -t[1])
        term_meta = {"term_rows": term_rows, "term_positions": t_pos,
                     "live_block": {"target_rows": dict(zip(names, live_t)), "cell_rows": {n: len(live_rows[n]) for n in names}, **live_m},
                     "term_block": {"target_rows": dict(zip(names, term_t)), "cell_rows": {n: len(term_rows_b[n]) for n in names}, **term_m},
                     "players_with_a_term": len(term_bonus), "max_points": round(tb_sorted[0][1], 4) if tb_sorted else None,
                     "players_at_the_cap": sum(1 for _, v in tb_sorted if tb_sorted and abs(v - tb_sorted[0][1]) < 1e-9)}
    elif fill == "group":
        for i in group_order:
            for _ in range(left[names[i]]):
                cell, ids = names[i], solve(names[i])
                if ids is None and "A1" in cells:              # MIX: a cell row that cannot be solved passes to A1
                    passes += 1; cell = "A1"
                    ids = solve("A1")
                if ids is None:
                    break
                rows[cell].append(ids); commit_order.append(cell)
    elif fill == "rr":
        remaining = dict(left)
        while any(remaining[n] > 0 for n in names):
            for i in group_order:
                n = names[i]
                if remaining[n] <= 0:
                    continue
                ids = solve(n)
                if ids is None:
                    if "A1" in cells and n != "A1":            # its remaining quota passes to A1 (counted)
                        passes += remaining[n]; remaining["A1"] += remaining[n]
                    remaining[n] = 0
                    continue
                rows[n].append(ids); remaining[n] -= 1; commit_order.append(n)
    elif fill == "value":
        remaining = dict(left)
        while any(remaining[n] > 0 for n in names):
            best = None
            for i in group_order:
                n = names[i]
                if remaining[n] <= 0:
                    continue
                ids, val = peek(n)
                if ids is None:
                    if "A1" in cells and n != "A1":            # its remaining quota passes to A1 (counted)
                        passes += remaining[n]; remaining["A1"] += remaining[n]
                    remaining[n] = 0
                    continue
                if best is None or val > best[2]:                 # strict: a tie keeps the earlier cell
                    best = (n, ids, val)
            if best is None:
                break
            n, ids, v = best
            rows[n].append(commit(ids, v)); remaining[n] -= 1; commit_order.append(n)
    else:
        raise ValueError(f"fill must be 'group', 'value' or 'rr' (got {fill!r})")
    if covered:                                                # a coverage row takes the deal position its projection earns
        rows["A1"] = sorted(rows["A1"], key=lambda ids: -row_value[tuple(ids)])
    got = [len(rows[n]) for n in names]
    spare_rows: list[tuple[list[str], str]] = []
    if spares:
        s_target = mix_allocate(quotas, spares)
        for i in sorted(range(len(names)), key=lambda i: (-s_target[i], i)):
            for _ in range(s_target[i]):
                cell, ids = names[i], solve(names[i])
                if ids is None and "A1" in cells:
                    cell = "A1"
                    ids = solve("A1")
                if ids is None:
                    break
                spare_rows.append((ids, cell))
    if rs_rows or term_rows:                                   # each block on its positions; a short block closes up
        book, cell_of = [], []
        for q in sorted(slots):
            book.append(slots[q][0]); cell_of.append(slots[q][1]); blocks.append(slots[q][2])
    else:
        seq = mix_interleave(got, quotas, weights)
        pos = [0] * len(names); book, cell_of = [], []
        for j in seq:
            book.append(rows[names[j]][pos[j]]); cell_of.append(names[j]); pos[j] += 1
    dealt = Counter(); tot = 0
    for r, cell in enumerate(cell_of):
        w = weights[r] if r < len(weights) else 0
        dealt[cell] += w; tot += w
    meta = {"cells": {n: {"quota": q, "target_rows": t, "rows": g} for n, q, t, g in zip(names, quotas, target, got)},
            "cell_quotas_override": dict(cell_quotas) if cell_quotas is not None else None,
            "passes_to_A1": passes, "rows_solved": len(book), "pair_games": len(games), "fill": fill,
            "commit_order": commit_order,
            "cover": {"games": int(cover_games), "ranked": cover_list, "covered": covered, "missed": cover_missed},
            "half": ({**rs_meta, "blocks": blocks} if rs_rows else None),
            "term": ({**term_meta, "blocks": blocks} if term_rows else None),
            "entry_shares_before_overlap_limit": {n: round(dealt[n] / tot, 4) if tot else None for n in names},
            "rules": {n: {"quota": cells[n][0], "stack": cells[n][1], "qb_game_max": cells[n][2],
                          "second_game_pair": cells[n][3]} for n in names}, "portfolio": portfolio,
            "spares": {"requested": int(spares), "built": len(spare_rows), "cells": dict(Counter(c for _, c in spare_rows)),
                       "caps_from_book_entries": k},
            "source": ("nfl2 experiments/s18_stack_shapes.py @ 5869a1b (CELLS, allocate, interleave, mix_book)" if portfolio == "mix"
                       else "nfl2 experiments/s18_stack_shapes.py @ 5869a1b (WS, whole_book; PASSED, Addendum 129)")}
    return book, cell_of, meta, spare_rows


def apply_winner_order(book: list[int], rosters: list, fr: pd.DataFrame, inputs_path: Path) -> tuple[list[int], dict]:
    """Study 48b's DEAL_SCORE on the live book: score each main row with study 48's frozen model
    (nfl_dfs.inference.winner_like) and order the rows by score, descending, ties keeping the book order."""
    from nfl_dfs.inference import winner_like as WL
    missing = [c for c in WL.FRAME_FACTS if c not in fr.columns]
    if missing:                                          # never score with a model column silently zeroed (the reviewer, 10-07)
        raise ValueError(f"the frame lacks the model's columns {missing}")
    inp = pd.read_csv(inputs_path, dtype={"id": str}).drop_duplicates("id").set_index("id")
    cols = ["pos", "team", "opp", "game_id", "salary", "game_total"] + list(WL.FRAME_FACTS)
    players = fr.assign(id=fr["id"].astype(str)).drop_duplicates("id").set_index("id")[list(dict.fromkeys(cols))]
    players = players.join(inp[["own_proj", *WL.LAG_COLUMNS]], how="left")
    rows = [[str(x) for x in rosters[i]] for i in book]
    scores, feats = WL.score_book(rows, players)
    order = WL.order_by_score(scores)
    new = [book[o] for o in order]
    return new, {"model_sha256": sha256_file(WL.MODEL_PATH), "inputs": str(inputs_path),
                 "inputs_sha256": sha256_file(Path(inputs_path)), "scores_in_book_order": [round(float(x), 6) for x in scores],
                 "order": order, "moved": int(sum(o != i for i, o in enumerate(order))), "hist": "0 (live; study 48's port notes)"}


def winner_select(book_rows: list, book_cells: list[str], spares: list, fr: pd.DataFrame, inputs_path: Path,
                  weights: list[int], limits: tuple) -> tuple[list, list[str], list, dict]:
    """Study 48d's SEL_CELL on the live book (lab s48d_winner_select.py, `selections` + `interleaved`): score the book rows
    (indices 0..k-1, book order) and the spares (k.., build order); per cell keep its book count of the most winner-like
    rows (ties: the book row, then the index); within a cell, index order; then study 28's entry-weighted interleave on the
    head weights. The rows not chosen become the spares, in index order. Production's caps and overlap are re-checked on
    the chosen book."""
    from collections import Counter as _C
    from itertools import combinations as _comb
    from nfl_dfs.inference import winner_like as WL
    if not spares:
        raise ValueError("no spares were built (--mix-spares 0): nothing to select from")
    missing = [c for c in WL.FRAME_FACTS if c not in fr.columns]
    if missing:
        raise ValueError(f"the frame lacks the model's columns {missing}")
    inp = pd.read_csv(inputs_path, dtype={"id": str}).drop_duplicates("id").set_index("id")
    cols = list(dict.fromkeys(["pos", "team", "opp", "game_id", "salary", "game_total", *WL.FRAME_FACTS]))
    players = fr.assign(id=fr["id"].astype(str)).drop_duplicates("id").set_index("id")[cols]
    players = players.join(inp[["own_proj", *WL.LAG_COLUMNS]], how="left")
    rows_all = [[str(x) for x in r] for r in book_rows] + [[str(x) for x in ids] for ids, _ in spares]
    cells_all = list(book_cells) + [c for _, c in spares]
    scores, _ = WL.score_book(rows_all, players)
    k, n = len(book_rows), len(rows_all)
    key = lambda i: (-scores[i], i >= k, i)                                            # noqa: E731
    names = list(MIX_CELLS)
    book_count = _C(book_cells)
    sel = {c: sorted(sorted([i for i in range(n) if cells_all[i] == c], key=key)[:book_count.get(c, 0)]) for c in names}
    got = [len(sel[c]) for c in names]
    seq = mix_interleave(got, [MIX_CELLS[c][0] for c in names], weights)
    ptr = [0] * len(names); order = []
    for j in seq:
        order.append(sel[names[j]][ptr[j]]); ptr[j] += 1
    if sorted(order) != sorted(i for c in names for i in sel[c]) or len(order) != k:
        raise ValueError(f"the interleave placed {len(order)} of {k} rows")
    chosen = [rows_all[i] for i in order]
    xcap, dcap, qcap, ms = limits
    pos = dict(zip(players.index, players.pos.astype(str)))
    cnt = _C(p for r in chosen for p in r)
    qb = _C(next(p for p in r if pos.get(p) == "QB") for r in chosen)
    shared = max(len(set(a) & set(b)) for a, b in _comb(chosen, 2))
    bad = []
    if xcap is not None and max(v for p, v in cnt.items() if pos.get(p) != "DST") > xcap:
        bad.append("player cap")
    if dcap is not None and max((v for p, v in cnt.items() if pos.get(p) == "DST"), default=0) > dcap:
        bad.append("DST cap")
    if qcap is not None and max(qb.values()) > qcap:
        bad.append("QB cap")
    if shared > ms:
        bad.append(f"overlap {shared} > {ms}")
    if bad:
        raise ValueError(f"the chosen book breaks {bad}")
    taken = set(order)
    new_spares = [(rows_all[i], cells_all[i]) for i in range(n) if i not in taken]
    meta = {"model_sha256": sha256_file(WL.MODEL_PATH), "inputs": str(inputs_path), "inputs_sha256": sha256_file(Path(inputs_path)),
            "scores_built_order": [round(float(x), 6) for x in scores], "chosen_built_index_in_book_order": order,
            "spares_in": int(sum(i >= k for i in order)), "rule": "SEL_CELL (study 48d)", "hist": "0 (live)"}
    return chosen, [cells_all[i] for i in order], new_spares, meta


def selected_entry_shares(cells: list[str], weights: list[int]) -> dict:
    """The entry-weighted cell shares of the book as CHOSEN (mix_rows' own formula, over the selected rows' cells)."""
    dealt, tot = Counter(), 0
    for r, c in enumerate(cells):
        w = weights[r] if r < len(weights) else 0
        dealt[c] += w; tot += w
    return {c: round(dealt[c] / tot, 4) if tot else None for c in MIX_CELLS}


def winner_select_or_fallback(book_rows, book_cells, spares, fr, inputs_path, weights, limits):
    """winner_select, or -- on any failure -- the book and spares as built, with the reason (LOUD; never stops a union)."""
    try:
        return winner_select(book_rows, book_cells, spares, fr, inputs_path, weights, limits)
    except (ValueError, KeyError, OSError, SystemExit) as exc:
        return book_rows, book_cells, spares, {"not_applied": str(exc)}


def apply_priority_order(book: list[int], rosters: list, fr: pd.DataFrame, term: dict | None,
                         cells: list[str] | None = None, weights: list[int] | None = None) -> tuple[list[int], dict]:
    """Priority-first dealing (the operator 10-07; nfl_dfs.inference.priority_deal.priority_order): a live term block's
    rows keep their positions (the reviewer's c9028505 rule) and the other main rows are sorted among the other positions
    by the frozen score, highest first, ties keeping the book order. The rows themselves never change."""
    from nfl_dfs.inference import priority_deal as PD
    need = ["pos", "team", "opp", "salary"]
    missing = [c for c in need if c not in fr.columns]
    if missing:
        raise ValueError(f"the frame lacks {missing}")
    pl = fr.assign(id=fr["id"].astype(str)).drop_duplicates("id").set_index("id")[need]
    maps = {c: pl[c].to_dict() for c in need}
    rows = [[str(x) for x in rosters[i]] for i in book]
    blocks = (term or {}).get("blocks") or []
    if blocks and len(blocks) != len(book):
        raise ValueError(f"the term block's position list holds {len(blocks)} entries for a {len(book)}-row book")
    fixed = [j for j, b in enumerate(blocks) if b == "T"]
    perm, scores = PD.priority_order(rows, maps["pos"], maps["team"], maps["opp"], maps["salary"], fixed, return_scores=True)
    new = [book[o] for o in perm]
    meta = {"rule": "nfl_dfs.inference.priority_deal.priority_order: +2 QB with 2+ teammates, +1 a bring-back, +1 2+ non-DST "
                    "under 4,000; a live block keeps its positions, the others sorted by score (stable, highest first)",
            "module_sha256": sha256_file(Path(PD.__file__)), "fixed_positions": fixed, "scores_in_book_order": scores,
            "order": perm, "moved": int(sum(o != i for i, o in enumerate(perm))),
            "scores_in_new_order": [scores[o] for o in perm], "score_counts": {str(k): v for k, v in sorted(Counter(scores).items())}}
    if cells is not None and weights is not None:
        meta["entry_shares_after"] = selected_entry_shares([cells[o] for o in perm], weights)
    return new, meta


def priority_order_or_fallback(book: list[int], rosters: list, fr: pd.DataFrame, term: dict | None,
                               cells: list[str] | None = None, weights: list[int] | None = None) -> tuple[list[int], dict]:
    """apply_priority_order, or -- on any failure -- the book's own order with the reason (printed LOUDLY by the caller and
    recorded in the receipt and priority_order_fallback.txt). The order is a refinement: it never stops a union."""
    try:
        return apply_priority_order(book, rosters, fr, term, cells, weights)
    except (ValueError, KeyError, OSError, SystemExit) as exc:
        return book, {"not_applied": f"{type(exc).__name__}: {exc}"}


def winner_order_or_fallback(book: list[int], rosters: list, fr: pd.DataFrame, inputs_path: Path) -> tuple[list[int], dict]:
    """apply_winner_order, or -- on any failure -- the book's own order with the reason (printed LOUDLY by the caller and
    recorded in the receipt and winner_order_fallback.txt). The order is a refinement: it never stops a union."""
    try:
        return apply_winner_order(book, rosters, fr, inputs_path)
    except (ValueError, KeyError, OSError, SystemExit) as exc:
        return book, {"not_applied": str(exc)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--saturday-run", required=True, help="a run dir, or 'auto' (newest --saturday-dose run in --live-dir built before the T-70 run)")
    ap.add_argument("--saturday-dose", default="2560/10240", help="one dose or an ordered list, e.g. 2560/10240,1280/5120 (the first with a qualifying run is the supply)")
    ap.add_argument("--group", help="with --saturday-run auto: this week's draft group (a run dir for another group is never the supply)")
    ap.add_argument("--saturday-after", help="with --saturday-run auto: ISO UTC window start (a smoke or an old build built before it is never the supply)")
    ap.add_argument("--t70-run", type=Path, required=True)
    ap.add_argument("--live-dir", type=Path, required=True, help="the live results tree the union dir is created in (results/live/<season>-w<WW>)")
    ap.add_argument("--entries", type=int, required=True); ap.add_argument("--tail-sleeve", type=int, default=0)
    ap.add_argument("--mean-max-shared", type=int, default=7); ap.add_argument("--mean-dst-cap", type=float, default=0.25)
    ap.add_argument("--min-proj", type=float, default=1.0); ap.add_argument("--max-per-game", type=int, default=4)
    ap.add_argument("--min-salary", type=int, default=49_000); ap.add_argument("--pmo", type=int, default=0)
    ap.add_argument("--pmo-cap-share", type=float, default=0.5, help="PMO per-player exposure cap as a share of --pmo rows (L13's PMO_X50 = 0.5; 0 = uncapped, NOT supported by L13)")
    ap.add_argument("--main-cap-share", type=float, default=0.5,
                    help="with --main pmo_x50: a player in >= int(share*K) rows is banned from later solves (L13's PMO_X50 = 0.5, as "
                         "entered; L17: 0.67/0.8/uncapped HARMFUL). At K=36: 0.5 -> 18, 0.4 -> 14, 0.34 -> 12, 0.25 -> 9")
    ap.add_argument("--sleeve-cap-share", type=float, default=None,
                    help="the tail sleeve's per-player exposure cap as a share of T: a row is skipped when a player in it already "
                         "sits in int(share*T) sleeve rows. Default none (as entered). A short capped sleeve falls back, named, "
                         "to the uncapped sleeve. UNTESTED until PREREG-L19 reads")
    ap.add_argument("--main-qb-cap-rows", type=int, default=None,
                    help="with --main pmo_x50 or mix: a QB already in this many book rows is banned from later solves (study 35's "
                         "per-QB cap in ROWS, the unit the study calibrates; operator 10-06: QB diversity). Default none (off): "
                         "UNTESTED until study 35 reads.")
    ap.add_argument("--main-qb-cap-k", type=int, default=None,
                    help="the book size --main-qb-cap-rows was calibrated at (study 35: 26); required with it, and the union "
                         "REFUSES when --entries differs (the K-dependence lesson)")
    ap.add_argument("--main-dst-cap", type=float, default=None,
                    help="with --main pmo_x50: a DST in >= floor(share*K) rows is banned from later solves (operator's open question; "
                         "the tested arm had none -- Week 3 put two busting DSTs in 25 and 22 of 58 rows). Default none.")
    ap.add_argument("--sleeve-includes-main", action="store_true",
                    help="with --main pmo_x50: let the tail sleeve also pick from the optimizer's rows (they project highest, so they would take "
                         "most of it). Default off: the sleeve is the union pool's mean selection, the form rehearsed at 23/40 paid.")
    ap.add_argument("--main-game-cap", choices=["off", "p3"], default="off",
                    help="study 1 (default off): with --main pmo_x50, cap the share of main rows holding >= 3 players from game g at "
                         "min(0.5, P3[total rank of g]) (2014-21 outcomes); the plain control rows stay uncapped")
    ap.add_argument("--main-own-tilt", type=float, default=0.0,
                    help="with --main pmo_x50: projection points added to a skill player's objective per point of predicted ownership %% "
                         "(reviewer 2026-09-29: 0.20 with the blended file). Default 0 = the plain-mean optimizer, as entered in Week 4")
    ap.add_argument("--main-own-source", type=Path, default=None,
                    help="with --main-own-tilt: the week's ownership file (pred_own in %%, dk_player_id / gsis_id), from scripts/ownership_blend.py")
    ap.add_argument("--main-own-min-coverage", type=float, default=0.9,
                    help="with --main-own-tilt: refuse when the file names fewer than this share of the pool's skill players projected >= 5")
    ap.add_argument("--main", choices=["mean", "pmo_x50", "mix"], default="mean",
                    help="the main book: mean = the union pool's top-K by projected sum (paper arm); pmo_x50 = K capped plain-mean-optimizer rows solved on the T-70 frame (ENTERS Week 4); "
                         "mix = study 18's shape portfolio: the same capped solves by cell (nfl_dfs.inference.mix_shapes), ordered by the plan's entry-weighted interleave")
    ap.add_argument("--proj-source", type=Path, default=None,
                    help="an override file from scripts/fp_projection_override.py built for THIS T-70 frame: its projections replace "
                         "the frame's mean_projection for the players it holds (operator 10-05: Fantasy Points)")
    ap.add_argument("--proj-source-late-scratch-bump", action="store_true",
                    help="with --proj-source: a frame player unavailable at the build (the frame's statuses + --dk-status) whom "
                         "FP still projects >= --min-proj is a scratch FP has not processed; his depth-2 same-position teammate "
                         "gets our T-70 next-man-up bump on top of FP's number (late_scratch_bump; the outside reviewer "
                         "10-08). Default off. Missing inputs: a banner, no change")
    ap.add_argument("--mix-portfolio", choices=sorted(PORTFOLIOS), default=None,
                    help="with --main mix: mix = study 18's four-cell MIX; ws = study 18's WS (one whole-book cell; PASSED)")
    ap.add_argument("--mix-plan", type=Path, default=None, help="with --main mix: the week's contests.json (the interleave's entry weights)")
    ap.add_argument("--mix-spares", type=int, default=0,
                    help="with --main mix: spare rows solved after the book under the same running caps (caps from --entries), "
                         "added to the candidate corpus (source mix_spare, tagged with their cell) as the Sunday replacement "
                         "step's in-shape supply; never book rows (reviewer 2026-10-06; study 24 sized S = 15)")
    ap.add_argument("--mix-cover-games", type=int, default=0,
                    help="with --main mix: before the fill, one A1 row with its QB from each of the top-N games by pre-lock "
                         "total, counted toward A1's quota (study 43; default 0 = off)")
    ap.add_argument("--winner-select", type=Path, default=None,
                    help="study 48d: build the MIX book with its spares, then keep, per cell, its book count of the most "
                         "winner-like rows (study 48's frozen score) among the cell's book rows and spares; the rest become "
                         "the spares. The file is scripts/winner_like_inputs.py's inputs for THIS frame (default off)")
    ap.add_argument("--term-block-rows", type=int, default=0,
                    help="the prior-top term block (the operator 10-07: 'Live, capped, part of book'): N of the MIX book's rows "
                         "built on projection + min(tilt x pred_own, cap) from --term-block-source, after the live block, "
                         "through one state (default 0 = off)")
    ap.add_argument("--term-block-source", type=Path, default=None,
                    help="with --term-block-rows: the term file (dk_player_id, pred_own), e.g. the prior-top file")
    ap.add_argument("--term-block-tilt", type=float, default=0.20, help="with --term-block-rows: points per pred_own unit")
    ap.add_argument("--term-block-cap-points", type=float, default=2.0, help="with --term-block-rows: the largest term, in points")
    ap.add_argument("--term-block-min-coverage", type=float, default=0.5, help="with --term-block-rows: own_bonus's coverage gate")
    ap.add_argument("--winner-order", type=Path, default=None,
                    help="study 48b: re-order the main book by study 48's winner-likeness score (descending, ties keep the "
                         "book order) before writing book.csv; the file is scripts/winner_like_inputs.py's per-player inputs "
                         "for THIS frame (default off)")
    ap.add_argument("--priority-order", action="store_true",
                    help="with --main mix: priority-first dealing (the operator 10-07): a live term block's rows keep their "
                         "positions, the other main rows are sorted among theirs by nfl_dfs.inference.priority_deal's frozen "
                         "score, highest first, ties keeping the book order (default off: the book's own order)")
    ap.add_argument("--mix-rs-rows", type=int, default=0,
                    help="with --main mix: the half-and-half book (study 46): the last N of 26 rows built under the regulars' "
                         "tiers (9, 13 or 17), the rest as today, through one state (default 0 = off; needs --mix-fill rr)")
    ap.add_argument("--mix-fill", choices=["group", "value", "rr"], default="group",
                    help="with --main mix: group (default) = each cell's quota consecutively, largest cell first; value = at each "
                         "step the highest-objective next row across the cells (a capped QB's uses go to his best rows; study 42); rr = the "
                         "cells in turn, one row each (a row per shape for the top QBs; the outside reviewer, study 42)")
    ap.add_argument("--mix-cell-quotas", default=None,
                    help="with --main mix --mix-portfolio mix: the MIX cells' entry quotas 'A1=..,A2=..,B=..,C=..' (> 0, sum 1) in "
                         "place of mix_shapes.MIX_CELLS' (study 56, fewer QB + 1 rows; the operator 10-07). Unset = today's book, "
                         "byte for byte; the cells' rules are unchanged")
    ap.add_argument("--mix-layout", choices=["sequential", "top", "head", "spread"], default="head",
                    help="with --main mix: the layout enter_layout deals with (ENTER_LAYOUT)")
    ap.add_argument("--sleeve-source", choices=["mean", "field"], default="mean",
                    help="field: the tail sleeve's rows come from a field-like sample built from the pre-lock ownership predictor "
                         "(scripts/field_sleeve.py; operator 2026-10-02); any failure falls back LOUDLY to the projection sleeve")
    ap.add_argument("--sleeve-own-source", type=Path, default=None, help="the ownership file for --sleeve-source field (default: --main-own-source)")
    ap.add_argument("--sleeve-field-n", type=int, default=200_000); ap.add_argument("--sleeve-field-seed", type=int, default=2026)
    ap.add_argument("--sleeve-field-mode", choices=["top", "band", "free"], default="top",
                    help="free = no house-rule filter on the sampled rows (DK-legal only); see field_sleeve.py")
    ap.add_argument("--sleeve-field-keep", type=int, default=2000, help="field rows added to the pool, in pick order")
    ap.add_argument("--sleeve-field-rows", type=int, default=None,
                    help="with --sleeve-source field: only the first N sleeve rows from the field (the deal gives row 1 to the "
                         "Millionaire); the rest from the projection sleeve, chosen with the field rows taken (default: all)")
    ap.add_argument("--sleeve-max-per-game", type=int, default=5, help="per-game limit for the field sleeve's rows (the main book keeps --max-per-game)")
    ap.add_argument("--dk-status", type=Path); ap.add_argument("--tail-line", type=float, default=None)
    ap.add_argument("--out", type=Path, help="explicit output dir (default: <live-dir>/<utc stamp>-union-<t70 sha7>)")
    ap.add_argument("--rehearsal", action="store_true", help="paper: accept a T-70 run built with another selector (Week 3 was dual_emax); "
                                                            "the receipt records rehearsal=true; never point --out into the live tree")
    a = ap.parse_args(argv)
    if a.main_qb_cap_rows is not None and not (1 <= a.main_qb_cap_rows <= a.entries and a.main in ("pmo_x50", "mix")):
        raise SystemExit(f"--main-qb-cap-rows must be 1..entries with --main pmo_x50 or mix (got {a.main_qb_cap_rows}, main {a.main})")
    if a.main_qb_cap_rows is not None and a.main_qb_cap_k != a.entries:
        raise SystemExit(f"QB CAP REFUSED: --main-qb-cap-rows {a.main_qb_cap_rows} was calibrated at K {a.main_qb_cap_k}, but this "
                         f"book is K {a.entries}; {a.main_qb_cap_rows} rows is not the studied share here (re-calibrate)")
    if a.main_qb_cap_rows is not None:
        print(f"QB CAP: qb_cap_rows {a.main_qb_cap_rows} at K {a.entries} = {a.main_qb_cap_rows / a.entries:.2f} of rows "
              f"(calibrated at K {a.main_qb_cap_k}; study 35)", flush=True)
    if not 0 < a.main_cap_share <= 1:
        raise SystemExit(f"--main-cap-share must be in (0, 1] (got {a.main_cap_share})")
    if a.sleeve_cap_share is not None and not 0 < a.sleeve_cap_share <= 1:
        raise SystemExit(f"--sleeve-cap-share must be in (0, 1] (got {a.sleeve_cap_share})")
    if a.rehearsal and (a.out is None or a.live_dir in a.out.resolve().parents):
        raise SystemExit("--rehearsal needs --out outside --live-dir")
    if a.main_own_tilt and a.main not in ("pmo_x50", "mix"):
        raise SystemExit("--main-own-tilt is defined for --main pmo_x50 / mix (the term sits in the optimizer's objective)")
    if a.term_block_rows and (a.main != "mix" or a.mix_portfolio != "mix" or a.mix_fill != "rr" or a.mix_rs_rows or a.mix_cover_games
                              or a.main_own_tilt or a.winner_order is not None or a.winner_select is not None
                              or a.term_block_source is None or not 0 < a.term_block_rows < a.entries
                              or not 0 < a.term_block_cap_points <= 5.0):
        raise SystemExit("--term-block-rows needs --main mix --mix-portfolio mix --mix-fill rr, a --term-block-source, "
                         "0 < rows < entries, a cap in (0, 5] points, and no half / cover / whole-book term / winner order or select")
    if a.winner_select is not None and (a.main != "mix" or a.mix_portfolio != "mix" or not a.mix_spares or a.winner_order is not None
                                        or a.main_own_tilt or a.mix_rs_rows or a.mix_cover_games):
        raise SystemExit("--winner-select needs --main mix --mix-portfolio mix with spares, no ownership term, no half-and-half, "
                         "no cover, and not --winner-order (study 48d)")
    if a.priority_order and (a.main != "mix" or a.mix_portfolio != "mix" or a.winner_order is not None or a.winner_select is not None
                             or a.main_own_tilt or a.mix_rs_rows or a.mix_cover_games):
        raise SystemExit("--priority-order needs --main mix --mix-portfolio mix, and no winner order or select, ownership "
                         "term, half-and-half or cover (untested together)")
    if a.mix_rs_rows and (a.main != "mix" or a.mix_portfolio != "mix" or a.mix_fill != "rr" or a.mix_cover_games
                          or a.mix_rs_rows not in (9, 13, 17) or a.entries != 26):
        raise SystemExit("--mix-rs-rows N (9, 13 or 17) needs --main mix, --mix-portfolio mix, --mix-fill rr, no cover and "
                         "--entries 26 (study 46)")
    cell_quotas = None
    if a.mix_cell_quotas is not None:
        if a.main != "mix" or a.mix_portfolio != "mix":
            raise SystemExit("--mix-cell-quotas needs --main mix --mix-portfolio mix (study 56)")
        try:
            cell_quotas = parse_cell_quotas(a.mix_cell_quotas)
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
        print(f"MIX CELL QUOTAS (study 56's switch): {cell_quotas} in place of "
              f"{ {n: c[0] for n, c in MIX_CELLS.items()} }")
    if a.mix_cover_games and (a.main != "mix" or a.mix_portfolio != "mix" or not 0 < a.mix_cover_games <= 8):
        raise SystemExit("--mix-cover-games N (1..8) needs --main mix with --mix-portfolio mix (study 43)")
    if a.main == "mix" and (a.mix_plan is None or not a.mix_plan.is_file()):
        raise SystemExit(f"--main mix needs --mix-plan (the week's contests.json; got {a.mix_plan})")
    if a.main == "mix" and a.mix_portfolio is None:
        raise SystemExit("--main mix needs --mix-portfolio mix|ws (no default: the chosen arm, stated)")
    if a.main == "mix" and a.main_game_cap != "off":
        raise SystemExit("--main-game-cap (study 1) is not defined with --main mix")
    if not 0 <= a.mix_spares <= 50:
        raise SystemExit(f"--mix-spares must be 0..50 (got {a.mix_spares})")
    if a.mix_spares and a.main != "mix":
        raise SystemExit("--mix-spares is defined with --main mix only")
    from nfl2.two_track import select_top_mean, tail_probability   # the pinned lab clone on PYTHONPATH
    from nfl2.live import dk_csv
    from nfl2.validator import validate_roster

    t70 = load_run(a.t70_run)
    cfg = t70["receipt"].get("config", {})
    if cfg.get("selector") != "mean" and not a.rehearsal:
        raise SystemExit(f"the union is defined for the mean selector; the T-70 receipt says {cfg.get('selector')!r}")
    sat_dir = resolve_saturday_run(a.saturday_run, a.saturday_dose, a.live_dir, t70["receipt"], a.t70_run.name, a.group, a.saturday_after)
    sat = load_run(sat_dir)
    if parse_utc(sat["receipt"].get("built_utc", "")) >= parse_utc(t70["receipt"].get("built_utc", "")):
        raise SystemExit(f"the Saturday run {sat_dir.name} was built at or after the T-70 run {a.t70_run.name}")
    fr = t70["frame"]
    proj_meta: dict = {}
    if a.proj_source is not None:                        # FP's projections replace ours (operator 10-05); off by default
        fr, proj_meta = apply_proj_source(fr, a.proj_source, a.t70_run / "frame.parquet")
        print(f"PROJECTION SOURCE: {a.proj_source} -- FP for {proj_meta['replaced']} frame players, ours for {proj_meta['kept_ours']}")
    inc, hs = (np.load(a.t70_run / b) for b in BANKS)
    if inc.shape[0] != len(fr) or hs.shape[0] != len(fr):
        raise SystemExit("T-70 banks do not match the T-70 frame's rows")
    dk = pd.read_csv(a.dk_status, dtype=str) if a.dk_status else None
    if a.proj_source_late_scratch_bump:                  # the outside reviewer 10-08; off by default (an OFF union is unchanged)
        fr = late_scratch_bump_step(fr, a.proj_source, proj_meta, dk, a.min_proj)
    cap = a.max_per_game if a.max_per_game > 0 else None

    # the pool: T-70 rows (the same T-70 rules applied defensively: a clean T-70 build drops nothing here), Saturday
    # survivors, optional PMO rows
    t70_rosters, t70_idx, t70_counts = survivors(t70["cands"], fr, set(), a.min_proj, cap, dk)
    t70_set = {frozenset(r) for r in t70_rosters}
    sat_rosters, sat_idx, counts = survivors(sat["cands"], fr, t70_set, a.min_proj, cap, dk)
    counts["t70_pool"] = t70_counts.pop("saturday_pool"); t70_counts.pop("unavailable_players", None)
    counts["t70_dropped"] = {k: v for k, v in t70_counts.items() if k.startswith("dropped")}
    rosters = t70_rosters + sat_rosters
    source = ["t70"] * len(t70_rosters) + ["saturday"] * len(sat_rosters)
    tags = list(t70["cands"]["tag"].astype(str).iloc[t70_idx]) + list(sat["cands"]["tag"].astype(str).iloc[sat_idx])
    sat_cand = [None] * len(t70_rosters) + [int(i) for i in sat_idx]
    n_pmo = 0
    if a.main in ("pmo_x50", "mix") and a.pmo > 0:
        raise SystemExit(f"--pmo (extra pool rows) is for --main mean; --main {a.main} solves the main book itself")
    if a.pmo > 0:
        gone = unavailable_ids(fr, dk)
        proj_all = dict(zip(fr.id.astype(str), pd.to_numeric(fr.mean_projection, errors="coerce")))
        pos_all = dict(zip(fr.id.astype(str), fr.pos.astype(str)))
        excl = gone | {i for i in proj_all if pos_all[i] in SKILL and not (proj_all[i] >= a.min_proj)}
        existing = t70_set | {frozenset(r) for r in sat_rosters}
        xcap = max(1, int(a.pmo_cap_share * a.pmo)) if a.pmo_cap_share > 0 else None
        pm = pmo_rows(fr, excl, a.pmo, a.mean_max_shared, cap, a.min_salary, existing, exposure_cap=xcap)
        rosters += pm; source += ["pmo"] * len(pm); tags += ["pmo"] * len(pm); sat_cand += [None] * len(pm); n_pmo = len(pm)
    # the winner-shaped sleeve's candidates (operator 2026-10-02): appended before any PMO row so every index stays put
    field_meta: dict = {"requested": a.sleeve_source == "field"}
    field_pick: list[int] = []
    n_field_start = len(rosters)
    if a.sleeve_source == "field" and a.tail_sleeve:
        try:
            import field_sleeve as FS
            proj_f = dict(zip(fr.id.astype(str), pd.to_numeric(fr.mean_projection, errors="coerce")))
            pos_f = dict(zip(fr.id.astype(str), fr.pos.astype(str)))
            excl_f = set(unavailable_ids(fr, dk)) | {i for i in proj_f if pos_f[i] in SKILL and not (proj_f[i] >= a.min_proj)}
            src = a.sleeve_own_source or a.main_own_source
            if src is None or not Path(src).is_file():
                raise ValueError(f"no ownership file ({src})")
            targets, tmeta = FS.ownership_targets(Path(src), fr, excl_f)
            f_rost, _f_ps, fmeta = FS.field_candidates(fr, targets, a.sleeve_field_n, a.sleeve_field_seed, a.sleeve_max_per_game,
                                                       a.min_salary, a.sleeve_field_mode,
                                                       report_ids=[r["id"] for r in tmeta.get("top15", [])])
            # The capped pick runs over the FULL ordered field list BEFORE anything joins the pool (production review R1,
            # 06:00): a pick that cannot fill T under the caps raises here, nothing is added, and the projection sleeve
            # (as entered) runs with the banner; a pool row can never stand in for a field row.
            pcap_f = main_exposure_cap(a.sleeve_cap_share, a.tail_sleeve) if a.sleeve_cap_share is not None else a.tail_sleeve
            fsets = [frozenset(r) for r in f_rost]
            pick = select_top_mean_player_cap(np.arange(len(f_rost), 0, -1, dtype=float), fsets, a.tail_sleeve, a.mean_max_shared, pcap_f)
            chosen = [f_rost[i] for i in pick]                    # appended even when one equals a pool roster
            have = {frozenset(r) for r in rosters} | {fsets[i] for i in pick}
            picked = set(pick)
            rest = [r for k, r in enumerate(f_rost) if k not in picked and fsets[k] not in have][: a.sleeve_field_keep]
            field_pick = list(range(len(rosters), len(rosters) + len(chosen)))
            rosters += chosen + rest; n_add = len(chosen) + len(rest)
            source += ["field"] * n_add; tags += ["field"] * n_add; sat_cand += [None] * n_add
            fmeta["drawn_share"] = {r["name"]: {"predicted": r["predicted"], "tilted": r["tilted"],
                                                "drawn": fmeta.get("drawn_share", {}).get(r["id"])} for r in tmeta.pop("top15", [])}
            field_meta.update({"targets": tmeta, **fmeta, "rows_added": n_add, "pick_ranks_in_field_order": [int(i) for i in pick],
                               "player_cap": pcap_f, "source_sha256": sha256_file(Path(src))})
        except Exception as exc:                                   # noqa: BLE001 -- the fallback must catch everything
            field_pick = []
            field_meta.update({"used": False, "failed": f"{type(exc).__name__}: {exc}"})
            print("!" * 80 + f"\n!!! FIELD SLEEVE FAILED ({field_meta['failed']}) -- THE PROJECTION SLEEVE IS USED\n" + "!" * 80, flush=True)
    n_field = len(rosters) - n_field_start
    need = a.entries + a.tail_sleeve
    if len(rosters) < need:
        raise SystemExit(f"the union holds {len(rosters)} rosters; the book needs {need}")

    # the Week-4 mean selection, as live_week.py --selector mean [--tail-sleeve T --tail-sleeve-selector mean]
    proj = dict(zip(fr.id.astype(str), pd.to_numeric(fr.mean_projection, errors="coerce").astype(float)))
    score = projected_sum(rosters, proj)
    frozen = [frozenset(r) for r in rosters]
    pos = dict(zip(fr.id.astype(str), fr.pos.astype(str)))
    dst_args = {}
    dst_cap = None
    if a.mean_dst_cap is not None:
        import math
        dst_cap = max(1, math.floor(a.mean_dst_cap * a.entries))
        dst_args = {"dst_of": [next(i for i in r if pos[i] == "DST") for r in rosters], "dst_cap": dst_cap}
    pmo_main: dict = {}
    mix_meta: dict = {}
    if a.main in ("pmo_x50", "mix"):
        import time as _time
        gone = unavailable_ids(fr, dk)
        proj_all = dict(zip(fr.id.astype(str), pd.to_numeric(fr.mean_projection, errors="coerce")))
        pos_all = dict(zip(fr.id.astype(str), fr.pos.astype(str)))
        excl = gone | {i for i in proj_all if pos_all[i] in SKILL and not (proj_all[i] >= a.min_proj)}
        xcap = main_exposure_cap(a.main_cap_share, a.entries)
        dcap = max(1, int(a.main_dst_cap * a.entries)) if a.main_dst_cap else None
        qcap = a.main_qb_cap_rows
        bonus, own_meta = own_bonus(a.main_own_source, fr, excl, a.main_own_tilt, a.main_own_min_coverage) if a.main_own_tilt else ({}, {})
        t_pmo = _time.time()
        plain_tags = main_tags = None
        spare_rows: list = []
        if a.main == "mix":
            weights = mix_weights(a.mix_plan, a.entries, a.mix_layout)
            term_rows, term_bonus, term_src = 0, None, None
            if a.term_block_rows:                            # the prior-top term block: any failure builds the book without it, LOUDLY
                try:
                    raw, term_src = own_bonus(a.term_block_source, fr, excl, a.term_block_tilt, a.term_block_min_coverage)
                    term_bonus = {i: min(v, a.term_block_cap_points) for i, v in raw.items()}
                    term_rows = a.term_block_rows
                    term_src = {**term_src, "cap_points": a.term_block_cap_points,
                                "players_capped": sum(1 for v in raw.values() if v > a.term_block_cap_points)}
                    print(f"TERM BLOCK: {term_rows} of {a.entries} rows on projection + min({a.term_block_tilt} x pred_own, "
                          f"{a.term_block_cap_points}) from {a.term_block_source} ({len(term_bonus)} players with a term, "
                          f"{term_src['players_capped']} at the cap)")
                except (SystemExit, Exception) as exc:
                    term_src = {"not_applied": f"{type(exc).__name__}: {exc}"}
                    print(f"\n!!! TERM BLOCK NOT APPLIED: {term_src['not_applied']} -- the book is built without it\n")
            plain_rows, plain_cells, mix_meta, plain_spares = mix_rows(fr, excl, a.entries, a.mean_max_shared, cap, a.min_salary,
                                                                       weights, exposure_cap=xcap, dst_cap=dcap, qb_cap=qcap,
                                                                       portfolio=a.mix_portfolio, fill=a.mix_fill,
                                                                       cover_games=a.mix_cover_games, rs_rows=a.mix_rs_rows,
                                                                       spares=0 if bonus else a.mix_spares,
                                                                       term_rows=term_rows, term_bonus=term_bonus,
                                                                       cell_quotas=cell_quotas)
            if a.term_block_rows:
                mix_meta["term_source"] = term_src
            spare_rows = plain_spares
            if a.winner_select is not None:                  # study 48d: choose the book by the winner-likeness score
                plain_rows, plain_cells, spare_rows, sel_meta = winner_select_or_fallback(
                    plain_rows, plain_cells, spare_rows, fr, a.winner_select, weights,
                    (xcap, dcap, qcap, a.mean_max_shared))
                mix_meta["winner_select"] = sel_meta
                if "not_applied" not in sel_meta:            # the reviewer's NOTE 1: the as-built fields kept apart, the shares recomputed
                    mix_meta["pre_selection"] = {f: mix_meta.pop(f) for f in ("commit_order", "entry_shares_before_overlap_limit")
                                                 if f in mix_meta}
                    mix_meta["entry_shares_before_overlap_limit"] = selected_entry_shares(plain_cells, weights)
                if "not_applied" in sel_meta:
                    print(f"\n!!! WINNER SELECTION NOT APPLIED: {sel_meta['not_applied']} -- the book stands as built\n")
                else:
                    print(f"WINNER SELECTION: {sel_meta['spares_in']} spare(s) replace book rows (model {sel_meta['model_sha256'][:12]})")
            plain_tags = [TAG_PREFIX + c for c in plain_cells]; main_tags = plain_tags
            mix_meta.update({"plan": str(a.mix_plan), "plan_sha256": sha256_file(a.mix_plan), "layout": a.mix_layout,
                             "weights_nonzero_ranks": sum(1 for w in weights if w), "weights_entries": sum(weights)})
        else:
            plain_rows = pmo_rows(fr, excl, a.entries, a.mean_max_shared, cap, a.min_salary, set(), exposure_cap=xcap, dst_cap=dcap, qb_cap=qcap)
        secs_pmo = round(_time.time() - t_pmo, 1)
        if len(plain_rows) < a.entries:
            label = "MIX MAIN REFUSED" if a.main == "mix" else "PMO_X50 MAIN REFUSED"
            raise SystemExit(f"{label}: {len(plain_rows)} of {a.entries} rows solved on the T-70 frame under the caps "
                             f"(exposure cap {xcap}, overlap {a.mean_max_shared}, per-game {cap}, salary floor {a.min_salary}); "
                             + ("the chain builds the HOUSE main (C)" if a.main == "mix" else "the union's mean main stands"))
        main_rows = plain_rows
        gcaps = game_row_caps(fr, a.entries) if a.main_game_cap == "p3" else None
        if gcaps is not None and not bonus:
            main_rows = pmo_rows(fr, excl, a.entries, a.mean_max_shared, cap, a.min_salary, set(), exposure_cap=xcap, dst_cap=dcap, qb_cap=qcap, game_caps=gcaps)
            check_main_rows(main_rows, a.entries, gcaps, bonus)
        if bonus:
            t_own = _time.time()
            if a.main == "mix":
                main_rows, main_cells, own_mix, spare_rows = mix_rows(fr, excl, a.entries, a.mean_max_shared, cap, a.min_salary,
                                                                      weights, exposure_cap=xcap, dst_cap=dcap, qb_cap=qcap, bonus=bonus,
                                                                      portfolio=a.mix_portfolio, spares=a.mix_spares, fill=a.mix_fill,
                                                                      cover_games=a.mix_cover_games, rs_rows=a.mix_rs_rows,
                                                                      cell_quotas=cell_quotas)
                main_tags = [TAG_PREFIX + c for c in main_cells]; mix_meta["with_term"] = own_mix
            else:
                main_rows = pmo_rows(fr, excl, a.entries, a.mean_max_shared, cap, a.min_salary, set(), exposure_cap=xcap, dst_cap=dcap, qb_cap=qcap, bonus=bonus,
                                     game_caps=gcaps)
            own_meta["secs"] = round(_time.time() - t_own, 1)
            check_main_rows(main_rows, a.entries, gcaps, bonus)
        # the PMO rows join the corpus (source pmo_x50) and ARE the main book, in solve order; a PMO row that duplicates a pool
        # roster is still the PMO row (the corpus keeps both; the book is unique by construction). With the ownership term
        # the plain-mean rows keep these places (source pmo_x50_control: the sleeve's supply, as entered) and the term's
        # rows follow them; a term row equal to a plain row IS that row.
        base = len(rosters)
        rosters += plain_rows; source += [a.main] * len(plain_rows); tags += plain_tags or ["pmo_x50"] * len(plain_rows); sat_cand += [None] * len(plain_rows)
        book = list(range(base, base + a.entries))
        sleeve_until = len(rosters)                              # the sleeve never reads past the plain rows
        if bonus:
            at = {frozenset(r): base + k for k, r in enumerate(plain_rows)}
            book = []
            for j, r in enumerate(main_rows):
                if frozenset(r) in at:
                    book.append(at[frozenset(r)])
                    if main_tags is not None:
                        tags[at[frozenset(r)]] = main_tags[j]           # a shared row takes the cell it holds in THIS book
                else:
                    book.append(len(rosters)); rosters.append(r); source.append(a.main); tags.append(main_tags[j] if main_tags else "pmo_x50"); sat_cand.append(None)
            in_book = set(book)
            for k in range(base, base + len(plain_rows)):
                if k not in in_book:
                    source[k] = f"{a.main}_control"
        if a.main == "mix" and a.mix_spares:
            # the spares (the book's own objective: built by the call that built the book) join the corpus LAST -- past the
            # plain rows the sleeve reads and past every book row -- as the replacement step's in-shape supply. Each is
            # re-checked here (DK legality, its cell's shape, the salary floor); a failing spare is dropped LOUDLY, never
            # written (the audit would fail the whole build on it), and never a refusal of the book.
            from nfl_dfs.inference.mix_shapes import shape_violations as _spare_v
            _st = dict(zip(fr.id.astype(str), fr.team.astype(str))); _so = dict(zip(fr.id.astype(str), fr.opp.astype(str)))
            _sg = dict(zip(fr.id.astype(str), fr.game_id.astype(str)))
            _ss = dict(zip(fr.id.astype(str), pd.to_numeric(fr.salary, errors="coerce").fillna(0).astype(int)))
            dropped = []
            for ids, cell in spare_rows:
                v = list(validate_roster(ids, pos, _st, _so, _ss)) + list(_spare_v(ids, cell, pos, _st, _so, _sg))
                if v or sum(_ss[p] for p in ids) < a.min_salary:
                    dropped.append({"cell": cell, "problems": v or ["salary floor"]})
                    continue
                rosters.append(ids); source.append(f"{a.main}_spare"); tags.append(TAG_PREFIX + cell); sat_cand.append(None)
            if dropped:
                print("!" * 80 + f"\n!!! {len(dropped)} MIX SPARE ROW(S) DROPPED (failed their re-check): {dropped[:2]}\n" + "!" * 80, flush=True)
            mix_meta["spares"] = {"requested": a.mix_spares, "built": len(spare_rows), "written": len(spare_rows) - len(dropped),
                                  "dropped": dropped, "objective": "with the ownership term" if bonus else "plain",
                                  "caps_from_book_entries": a.entries, "source": f"{a.main}_spare"}
            if len(spare_rows) - len(dropped) < a.mix_spares:
                print(f"MIX SPARES: {len(spare_rows) - len(dropped)} of {a.mix_spares} written (a short spare tail is not a refusal)", flush=True)
        frozen = [frozenset(r) for r in rosters]; score = projected_sum(rosters, proj)
        sleeve_score = np.where(np.arange(len(rosters)) < (sleeve_until if a.sleeve_includes_main else base), score, -np.inf)
        if bonus:
            own_pts = {i: v / a.main_own_tilt for i, v in bonus.items()}
            control = list(range(base, base + a.entries))
            own_meta.update({"rows_shared_with_the_plain_main": len(set(book) & set(control)),
                             "projected_sum_mean": {"with_term": round(float(score[book].mean()), 3), "plain": round(float(score[control].mean()), 3)},
                             "pred_own_sum_mean": {"with_term": round(float(np.mean([sum(own_pts.get(p, 0.0) for p in rosters[i]) for i in book])), 2),
                                                   "plain": round(float(np.mean([sum(own_pts.get(p, 0.0) for p in rosters[i]) for i in control])), 2)},
                             "control_book": "book_main_control.csv"})
        expo = Counter(p for i in book for p in rosters[i])
        dst_expo = Counter(p for i in book for p in rosters[i] if pos[p] == "DST")
        pmo_main = {"exposure_cap": xcap, "exposure_cap_share": a.main_cap_share, "rows_solved": len(main_rows), "secs": secs_pmo, "max_exposure_used": max(expo.values()),
                    "sleeve_includes_main": bool(a.sleeve_includes_main),
                    "distinct_players": len(expo), "dst_cap": dcap if dcap else "none (the tested arm had none)",
                    "max_dst_rows_used": max(dst_expo.values()), "dst_rows": dict(dst_expo.most_common(3)),
                    "qb_cap_rows": qcap if qcap else "none (off)", "qb_cap_k": a.main_qb_cap_k,
                    "max_qb_rows_used": max(Counter(p for i in book for p in rosters[i] if pos[p] == "QB").values()),
                    "own_term": own_meta if bonus else {"tilt": 0.0}}
        if a.main == "mix":
            pmo_main["mix"] = mix_meta
        dst_args = {}
    else:
        is_field = (np.arange(len(rosters)) >= n_field_start) & (np.arange(len(rosters)) < n_field_start + n_field)
        book = select_top_mean(np.where(is_field, -1e9, score), frozen, a.entries, max_shared=a.mean_max_shared, **dst_args)
        sleeve_score = score
    tail_scores = np.where(np.isfinite(sleeve_score), sleeve_score, -1e9)
    if n_field and not field_pick:                                 # production R2: the fallback is the sleeve as entered
        tail_scores[n_field_start:n_field_start + n_field] = -1e9
    sleeve_cap: dict = {"share": None, "rows": None, "fell_back": False}
    book_tail = []
    if field_pick:
        if not all(n_field_start <= i < n_field_start + n_field for i in field_pick) or len(field_pick) != a.tail_sleeve:
            raise SystemExit(f"field sleeve pick {field_pick} is not {a.tail_sleeve} field rows")      # cannot happen; fail closed
        book_tail = list(field_pick)
        field_meta["used"] = True
        sleeve_cap = {"share": a.sleeve_cap_share, "rows": field_meta.get("player_cap"), "fell_back": False}
        k_f = a.sleeve_field_rows
        if k_f is not None and 0 < k_f < a.tail_sleeve:
            # the split (reviewer's suggestion A, 10-02): field rows for the first k_f sleeve rows, the projection sleeve for
            # the rest, chosen with the field rows already taken; a shortfall keeps the all-field sleeve, LOUDLY
            proj_scores = tail_scores.copy(); proj_scores[n_field_start:n_field_start + n_field] = -1e9
            try:
                book_tail = select_top_mean_player_cap(proj_scores, frozen, a.tail_sleeve, a.mean_max_shared,
                                                       field_meta.get("player_cap") or a.tail_sleeve, pre=tuple(field_pick[:k_f]))
                if any(n_field_start <= i < n_field_start + n_field for i in book_tail[k_f:]):
                    raise RuntimeError("a field row was picked as a projection row")
                field_meta["split"] = {"field_rows": k_f, "projection_rows": a.tail_sleeve - k_f}
            except RuntimeError as e:
                book_tail = list(field_pick)
                field_meta["split"] = {"requested": k_f, "failed": str(e)}
                print("!" * 80 + f"\n!!! FIELD SLEEVE SPLIT FAILED ({e}) -- ALL {a.tail_sleeve} SLEEVE ROWS ARE FIELD ROWS\n" + "!" * 80, flush=True)
    if a.tail_sleeve and not book_tail and a.sleeve_cap_share is not None:
        pcap = main_exposure_cap(a.sleeve_cap_share, a.tail_sleeve)
        sleeve_cap = {"share": a.sleeve_cap_share, "rows": pcap, "fell_back": False}
        try:
            book_tail = select_top_mean_player_cap(tail_scores, frozen, a.tail_sleeve, a.mean_max_shared, pcap)
        except RuntimeError as e:
            print(f"TAIL SLEEVE CAP FELL BACK: {e}; the uncapped sleeve (as entered) stands")
            sleeve_cap["fell_back"] = True; sleeve_cap["error"] = str(e)
    if a.tail_sleeve and not book_tail:
        book_tail = select_top_mean(tail_scores, frozen, a.tail_sleeve, max_shared=a.mean_max_shared)
    if len(book) != a.entries or len(set(book)) != a.entries or (a.tail_sleeve and len(book_tail) != a.tail_sleeve):
        raise SystemExit("the selector did not return the requested rows")

    # contract revalidation of every written roster (as live_week.py)
    ids_ = fr.id.astype(str).tolist()
    _team = dict(zip(ids_, fr.team.astype(str))); _opp = dict(zip(ids_, fr.opp.astype(str)))
    _sal = dict(zip(ids_, pd.to_numeric(fr.salary, errors="coerce").fillna(0).astype(int)))
    contract = {"dk_contract": "dk_classic_v1", "strategy_contract": "house_qb2_bb1_floor49_v1", "dk_violations": 0, "strategy_violations": 0}
    if a.main == "mix":
        contract["strategy_contract"] = "mix_cells_s18_v1 (house for untagged rows); floor49"
        _game = dict(zip(ids_, fr.game_id.astype(str)))
    for i in book + book_tail:
        v_dk = validate_roster(rosters[i], pos, _team, _opp, _sal)
        if v_dk:
            raise SystemExit(f"written roster fails DK contract: {v_dk}")
        if a.main == "mix" and cell_of_tag(tags[i]) is not None:
            v_cell = shape_violations(rosters[i], cell_of_tag(tags[i]), pos, _team, _opp, _game)
            if v_cell:                                     # the solver produced a row its own cell forbids: fail closed
                raise SystemExit(f"MIX MAIN REFUSED: row {rosters[i]} ({tags[i]}) breaks its cell: {v_cell}")
            if sum(_sal[p] for p in rosters[i]) < a.min_salary:
                contract["strategy_violations"] += 1
        elif validate_roster(rosters[i], pos, _team, _opp, _sal, salary_floor=a.min_salary, qb_stack_min=2, bring_back_min=1,
                           forbid_rb_vs_dst=True, forbid_two_rb_same_team=True):
            contract["strategy_violations"] += 1

    # the run dir
    t70_sha7 = str(t70["receipt"].get("identity", {}).get("sha", "nosha"))[:7]
    out = a.out or a.live_dir / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}-union-{t70_sha7}"
    if out.exists() or out.with_name(out.name + ".tmp").exists():
        raise SystemExit(f"{out} exists; a union is written once")
    final_out, out = out, out.with_name(out.name + ".tmp")     # written under .tmp, renamed once complete (never half-eligible)
    out.mkdir(parents=True)
    for f in COPY:
        if (a.t70_run / f).is_file():
            shutil.copyfile(a.t70_run / f, out / f)
    if proj_meta:                                        # the projections this book was selected on travel with it
        shutil.copyfile(a.proj_source, out / "proj_source.csv"); shutil.copyfile(str(a.proj_source) + ".json", out / "proj_source.csv.json")
    winner_meta = None
    if a.winner_order is not None:                       # study 48b: the most winner-like rows first (the head deal's big ranks)
        book, winner_meta = winner_order_or_fallback(book, rosters, fr, a.winner_order)
        if "not_applied" in winner_meta:
            print(f"\n!!! WINNER ORDER NOT APPLIED: {winner_meta['not_applied']} -- the book keeps its own order\n")
            (out / "winner_order_fallback.txt").write_text(f"winner order NOT applied: {winner_meta['not_applied']}\n")
        else:
            print(f"WINNER ORDER: {winner_meta['moved']} of {len(book)} book positions moved (model {winner_meta['model_sha256'][:12]})")
    priority_meta = None
    if a.priority_order:                                 # priority-first dealing (the operator 10-07): the block keeps its ranks
        _cells = [str(tags[i])[len(TAG_PREFIX):] if str(tags[i]).startswith(TAG_PREFIX) else None for i in book]
        book, priority_meta = priority_order_or_fallback(book, rosters, fr, mix_meta.get("term"),
                                                         _cells if None not in _cells else None, weights)
        if "not_applied" in priority_meta:
            print(f"\n!!! PRIORITY ORDER NOT APPLIED: {priority_meta['not_applied']} -- the book keeps its own order\n")
            (out / "priority_order_fallback.txt").write_text(f"priority order NOT applied: {priority_meta['not_applied']}\n")
        else:
            print(f"PRIORITY ORDER: {priority_meta['moved']} of {len(book)} book positions moved; block positions kept "
                  f"{priority_meta['fixed_positions']}; scores in the new order {priority_meta['scores_in_new_order']} "
                  f"(module {priority_meta['module_sha256'][:12]})")
    players_by_id = frame_players(fr)
    lus = [_LU([players_by_id[i] for i in rosters[k]], tags[k]) for k in range(len(rosters))]
    n_written = dk_csv([lus[i] for i in book + book_tail], fr, out / "book.csv")
    if n_written != need:
        raise SystemExit(f"dk_csv wrote {n_written} rows for a {a.entries}+{a.tail_sleeve} book")
    if pmo_main.get("own_term", {}).get("tilt"):
        # PAPER: the main as entered in Week 4 (no ownership term), in solve order; never uploaded, scored Monday beside the book
        if dk_csv([lus[i] for i in range(base, base + a.entries)], fr, out / "book_main_control.csv") != a.entries:
            raise SystemExit("dk_csv did not write the control main")
    row_of = {i: r for r, i in enumerate(ids_)}
    idx = np.array([[row_of[i] for i in r] for r in rosters])
    sel = inc[idx].sum(axis=1); aud = hs[idx].sum(axis=1)             # candidates x worlds, per bank
    tail_line = a.tail_line if a.tail_line is not None else float((cfg.get("tail_sleeve") or {}).get("line", 210.0))
    p_tail = tail_probability(np.concatenate([sel, aud], axis=1), tail_line)
    rank_of = {i: r + 1 for r, i in enumerate(book)}; rank_tail = {i: a.entries + r + 1 for r, i in enumerate(book_tail)}
    corpus = pd.DataFrame({
        "cand": range(len(rosters)), "players": [",".join(sorted(r)) for r in rosters],
        "names": ["|".join(players_by_id[i]["name"] for i in r) for r in rosters],
        "tag": tags, "salary": [lu.salary for lu in lus],
        "book_rank": [rank_of.get(i) for i in range(len(rosters))], "book_rank_cov": np.nan,
        "sel_mean": sel.mean(axis=1).astype(np.float32), "sel_p194": (sel >= 194).mean(axis=1),
        "aud_mean": aud.mean(axis=1).astype(np.float32), "aud_p194": (aud >= 194).mean(axis=1),
        "gen_mean": sel.mean(axis=1).astype(np.float32), "book_rank_wemax": np.nan, "all_tags": tags,
        "book_rank_tail": [rank_tail.get(i) for i in range(len(rosters))], f"p_tail_{int(tail_line)}": p_tail,
        "proj_sum": score, "source_run": source, "saturday_cand": pd.array(sat_cand, dtype="Int64")})
    corpus.to_parquet(out / "candidates.parquet")
    json.dump({"entries": [{"rank": r + 1, "players": [players_by_id[i]["name"] for i in rosters[k]], "salary": lus[k].salary, "tag": tags[k],
                            "sel_mean": float(sel[k].mean()), "sel_p194": float((sel[k] >= 194).mean()),
                            "aud_mean": float(aud[k].mean()), "aud_p194": float((aud[k] >= 194).mean()),
                            "proj_sum": float(score[k]), "source_run": source[k]} for r, k in enumerate(book)],
               **({"tail_sleeve": [{"rank": a.entries + r + 1, "players": [players_by_id[i]["name"] for i in rosters[k]], "salary": lus[k].salary,
                                    "tag": tags[k], "p_line": float(p_tail[k]), "sel_mean": float(sel[k].mean()), "aud_mean": float(aud[k].mean()),
                                    "proj_sum": float(score[k]), "source_run": source[k]} for r, k in enumerate(book_tail)]} if book_tail else {})},
              open(out / "book.json", "w"), indent=1)
    by_src = Counter(source[i] for i in book); by_src_tail = Counter(source[i] for i in book_tail)
    tool = Path(__file__).resolve()
    prod_sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=tool.parent).stdout.strip()
    receipt = dict(t70["receipt"])
    receipt.update({"built_utc": str(datetime.now(timezone.utc)), "written": n_written, "candidates": len(rosters),
                    "book_k80_is_nested_prefix": True,
                    "artifacts": ["book.csv", "book.json", "candidates.parquet", "frame.parquet", "exposure_ledger.json"]
                                 + [f for f in ("book_wemax.csv", "book_wemax.json", "book_main_control.csv", *BANKS) if (out / f).is_file()]})
    conf = dict(cfg)
    conf["union"] = {"saturday_run": str(sat_dir), "t70_run": str(a.t70_run),
                     "saturday_identity": sat["receipt"].get("identity"), "t70_identity": t70["receipt"].get("identity"),
                     "saturday_config": {k: sat["receipt"].get("config", {}).get(k) for k in ("lev", "boom", "selector", "operational_k")},
                     "input_sha256": {"saturday_candidates": sha256_file(sat_dir / "candidates.parquet"), "t70_candidates": sha256_file(a.t70_run / "candidates.parquet"),
                                      "t70_frame": sha256_file(a.t70_run / "frame.parquet"), **{b: sha256_file(a.t70_run / b) for b in BANKS}},
                     "dk_status": str(a.dk_status) if a.dk_status else None, "counts": counts, "pmo_rows": n_pmo,
                     "pmo": {"requested": a.pmo, "solved": n_pmo, "exposure_cap_share": a.pmo_cap_share,
                             "form": "pmo rows into the mean-selected union (UNTESTED: not L13's arm; the mean selector re-picks without the cap)" if a.pmo else "none"},
                     "pool": {"t70": len(t70_rosters), "saturday": len(sat_rosters), "pmo": n_pmo, "total": len(rosters)},
                     "book_by_source": dict(by_src), "tail_by_source": dict(by_src_tail),
                     "selection": ("union_reselect.py --main pmo_x50: K capped plain-mean-optimizer rows on the T-70 frame in solve order (L13 PMO_X50)"
                                   + (f", objective = mean + {a.main_own_tilt} x predicted ownership % (skill players)" if a.main_own_tilt else "") + "; "
                                   if a.main == "pmo_x50" else
                                   (f"union_reselect.py --main mix --mix-portfolio {a.mix_portfolio}: study 18's shape portfolio, K capped plain-mean-optimizer rows "
                                    "on the T-70 frame by cell " + ("(A1 30 / A2 14 / B 28 / C 28 % of entries), in the plan's entry-weighted interleave order"
                                                                    if a.mix_portfolio == "mix" else "(WS: QB + >= 1, bring-back optional, <= 3 from the QB's game, a second-game pair; one cell)"))
                                   + (f", objective = mean + {a.main_own_tilt} x predicted ownership % (skill players)" if a.main_own_tilt else "") + "; "
                                   if a.main == "mix" else
                                   "union_reselect.py --main mean: top-K by sum of the T-70 mean_projection under the overlap cap and the DST cap; ")
                                  + "the tail sleeve top-T of the union pool by the same score (may repeat main rows)",
                     "min_proj": a.min_proj, "max_per_game": cap, "main_game_cap": a.main_game_cap, "tool": {"path": str(tool), "sha256": sha256_file(tool), "production_sha": prod_sha}}
    conf["operational_k"] = a.entries
    conf["selector"] = "mean"                       # LIVE_SELECTOR; the main's own form is config.union.main / main_selector_used
    if a.rehearsal:
        conf["union"]["rehearsal"] = {"t70_selector_was": cfg.get("selector"), "note": "PAPER: never entered"}
    conf["mean_max_shared"] = a.mean_max_shared
    conf["book_projected_sum"] = {"first": round(float(score[book[0]]), 3), "last": round(float(score[book[-1]]), 3), "mean": round(float(score[book].mean()), 3)}
    if dst_cap is not None and a.main == "mean":
        conf["mean_dst_cap"] = {"share": a.mean_dst_cap, "max_rows_per_dst": dst_cap, "max_rows_used": max(Counter(dst_args["dst_of"][i] for i in book).values())}
    else:
        conf.pop("mean_dst_cap", None)
    conf["union"]["main"] = a.main
    if proj_meta:
        # the reviewer's guard (10-06, O-22): any BOOK player without an FP projection was selected on our mean; name them
        _fp_ids = set(pd.read_csv(a.proj_source, dtype={"id": str})["id"].astype(str))
        _nm = dict(zip(fr["id"].astype(str), fr["display_name"].astype(str)))
        _ours = sorted({_nm.get(str(i), str(i)) for k in book + book_tail for i in rosters[k] if str(i) not in _fp_ids})
        proj_meta["book_players_ours"] = _ours
        print(f"PROJECTION SOURCE: book players on OUR projection (no FP): {len(_ours)}" + (f" -- {_ours}" if _ours else ""))
        conf["union"]["proj_source"] = proj_meta
    conf["union"]["winner_order"] = winner_meta if winner_meta is not None else "off"
    if priority_meta is not None:                        # only when on: an OFF union's receipt stays byte-identical
        conf["union"]["priority_order"] = priority_meta
    if pmo_main:
        conf["union"]["pmo_x50" if a.main == "pmo_x50" else a.main] = pmo_main
    conf["main_selector_used"] = a.main
    if a.tail_sleeve:
        used_field = bool(field_meta.get("used"))
        conf["tail_sleeve"] = {"rows": a.tail_sleeve, "line": tail_line, "selector": "field" if a.sleeve_source == "field" else "mean",
                               "selector_used": (f"field_{a.sleeve_field_mode}" + ("+mean" if "field_rows" in field_meta.get("split", {}) else ""))
                                                if used_field else "mean", "class": {}, "field": field_meta,
                               "worlds": "incumbent selection + corrected hsim", "book_rows": f"{a.entries + 1}..{a.entries + a.tail_sleeve}",
                               "repeats_of_main_rows": len({frozen[i] for i in book_tail} & {frozen[i] for i in book}),   # by roster (field rows may duplicate a pool roster)
                               "player_cap": sleeve_cap, "exposure": sleeve_exposure(book_tail, rosters, fr),
                               "p_line_first": round(float(p_tail[book_tail[0]]), 5), "p_line_last": round(float(p_tail[book_tail[-1]]), 5)}
    else:
        conf.pop("tail_sleeve", None)
    receipt["config"] = conf
    receipt.setdefault("inputs", {})["book_contract"] = contract
    (out / "receipt.json").write_text(json.dumps(receipt, indent=1) + "\n")
    out.rename(final_out); out = final_out
    print(f"UNION -> {out}\n  main {a.main}{(' ' + json.dumps(pmo_main)) if pmo_main else ''}\n  pool: t70 {len(t70_rosters)} (of {counts['t70_pool']}; dropped {counts['t70_dropped']}) + saturday {len(sat_rosters)} (of {counts['saturday_pool']}; dropped "
          f"{counts.get('dropped_missing_from_t70', 0)} missing, {counts.get('dropped_unavailable', 0)} unavailable, "
          f"{counts.get('dropped_below_min_proj', 0)} below min-proj, {counts.get('dropped_game_cap', 0)} game cap, "
          f"{counts.get('dropped_duplicate_of_t70', 0)} duplicates) + pmo {n_pmo} = {len(rosters)}\n"
          f"  book {a.entries} by source {dict(by_src)}; sleeve {a.tail_sleeve} by source {dict(by_src_tail)}; "
          f"projected sum first/last/mean {conf['book_projected_sum']}; strategy violations {contract['strategy_violations']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
