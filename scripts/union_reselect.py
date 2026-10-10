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
import math
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
from nfl_dfs.inference.mix_shapes import (TOP_WR_RULE_CELLS as MS_TOP_WR_RULE_CELLS, top_receivers as ms_top_receivers,  # noqa: E402
                                         bring_back_top_wr_rule as ms_bb_rule, rule_applies as ms_rule_applies)
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
              dk_status: pd.DataFrame | None, rb_rec_low: set[str] | frozenset = frozenset()) -> tuple[list[list[str]], list[int], dict]:
    """Saturday candidates that survive the T-70 information; returns (rosters, saturday cand index, counts). rb_rec_low: study
    116's RBs below the receptions floor (empty = off)."""
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
        if rb_rec_low and any(i in rb_rec_low for i in ids):
            counts["dropped_below_rb_rec"] += 1; continue
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


def parse_cell_quotas(spec: str) -> dict[str, float]:
    """--mix-cell-quotas "A1=0.40,A2=0.26,B=0.17,C=0.17" (study 56; the operator 10-07, his priority test this week):
    the MIX cells' entry quotas in place of mix_shapes.MIX_CELLS'. Exactly the four MIX cells, every value >= 0 and at least
    one > 0, the sum 1 (within 1e-9); anything else raises ValueError. The cells' RULES are unchanged. A cell at 0 gets no rows
    in either block but stays a cell (study 95's NO_x / ONLY_x arms, nfl2 s95_shapes.py: the quota list S28.QUOTAS with a 0,
    the cell kept, a failed cell's quota still passing to A1, counted) -- the operator 10-09: "we're going to decide the
    percentages of each of the successful shapes first thing in the morning"."""
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
    if any(not v >= 0 for v in out.values()) or not any(v > 0 for v in out.values()):
        raise ValueError("--mix-cell-quotas: every quota must be >= 0, at least one > 0")
    if abs(sum(out.values()) - 1.0) > 1e-9:
        raise ValueError(f"--mix-cell-quotas: the quotas sum to {sum(out.values())}, not 1")
    return {n: out[n] for n in MIX_CELLS}


OWN_CAP_SKILL_SUM = 800.0       # study 89: the predictions are rescaled so the frame's skill players sum to 8 x 100%


def own_cap_rows(source: Path, t70: pd.DataFrame, exclude: set[str], delta_pts: float, k: int,
                 min_coverage: float) -> tuple[dict[str, int], dict]:
    """Study 89's per-player ownership cap (nfl2 experiments/s89_own_cap.py own_cap_rows / pred_blend @ 4d0daa47; the
    operator 10-09: "Live W5 trial if built in time"): every SKILL player of the frame gets
    cap_rows = floor(k x (own / 100 + delta_pts / 100)) MAIN-BOOK rows, where own = the file's fp_own_raw (Fantasy Points'
    projected ownership %, negatives clipped) RESCALED so the frame's skill players sum to OWN_CAP_SKILL_SUM; a skill player
    the file does not name counts as 0% (the lab's form: a prediction of 0 -> the floor(k x delta) rows). DSTs get no cap
    (they keep the DST cap). The file is matched on id (the frame id), then dk_player_id. Refuses (SystemExit 'OWN CAP
    REFUSED: ...') on a missing / unreadable file, non-numeric or fractional values, or a coverage of the pool's skill
    players projected >= OWN_FLOOR_PROJ below min_coverage; never fills a value in."""
    def refuse(why: str):
        raise SystemExit(f"OWN CAP REFUSED: {why}")
    if not 0 < delta_pts <= 50:
        refuse(f"--main-own-cap-delta {delta_pts} outside (0, 50] percentage points")
    if source is None or not Path(source).is_file():
        refuse(f"the ownership file {source} does not exist")
    try:
        own = pd.read_csv(source, dtype=str)
    except (OSError, ValueError) as exc:
        refuse(f"the ownership file {source} is unreadable ({exc})")
    keys = [c for c in ("id", "dk_player_id") if c in own.columns]
    if "fp_own_raw" not in own.columns or not keys:
        refuse(f"the ownership file {source} needs fp_own_raw and id / dk_player_id (has {list(own.columns)})")
    blank = own.fp_own_raw.isna() | (own.fp_own_raw.astype(str).str.strip() == "")    # ownership_fp.py's lag-filled rows:
    val = pd.to_numeric(own.fp_own_raw, errors="coerce")                              # not FP's view -> the player is unnamed
    bad = ~blank & ~np.isfinite(val)
    if len(own) == 0 or bad.any():
        refuse(f"the ownership file {source} holds {int(bad.sum())} fp_own_raw values that are not numbers (of {len(own)})")
    own, val = own[~blank], val[~blank]
    if len(own) == 0:
        refuse(f"the ownership file {source} holds no fp_own_raw value (every row is filled from elsewhere)")
    if float(val.max()) <= 1.0:
        refuse(f"the ownership file {source} tops out at fp_own_raw {float(val.max()):.3f}: fractions, not percentages")
    val = val.clip(lower=0.0)
    by = {c: {} for c in keys}
    for c in keys:
        for kk, v in zip(own[c].map(_key), val):
            if kk:
                by[c][kk] = max(v, by[c].get(kk, 0.0))
    ids = t70.id.astype(str).tolist()
    pos = dict(zip(ids, t70.pos.astype(str)))
    proj = dict(zip(ids, pd.to_numeric(t70.mean_projection, errors="coerce").fillna(0.0)))
    dk_of = dict(zip(ids, t70.dk_player_id.map(_key))) if "dk_player_id" in t70.columns else {}
    raw: dict[str, float] = {}
    for i in ids:
        if pos[i] not in SKILL:
            continue
        for c in keys:
            kk = dk_of.get(i, "") if c == "dk_player_id" else _key(i)
            if kk and kk in by[c]:
                raw[i] = float(by[c][kk])
                break
    core = [i for i in ids if pos[i] in SKILL and i not in exclude and proj[i] >= OWN_FLOOR_PROJ]
    coverage = sum(1 for i in core if i in raw) / len(core) if core else 0.0
    if coverage < min_coverage:
        miss = sorted((i for i in core if i not in raw), key=lambda i: -proj[i])[:8]
        name = dict(zip(ids, t70.name.astype(str)))
        refuse(f"the ownership file {source} names {coverage:.1%} of the pool's skill players projected >= {OWN_FLOOR_PROJ} "
               f"(< {min_coverage:.0%}); missing e.g. {[name[i] for i in miss]}")
    arr = np.array([raw.get(i, 0.0) if pos[i] in SKILL else 0.0 for i in ids], dtype=float)   # the lab's layout: every frame
    total = float(arr.sum())                                                                   # row, 0 off skill (numpy's sum)
    if total <= 0:
        refuse(f"the ownership file {source} sums to {total} over the frame's skill players")
    factor = OWN_CAP_SKILL_SUM / total
    delta = delta_pts / 100.0
    skill_ids = [i for i in ids if pos[i] in SKILL]
    caps = {i: int(math.floor(k * (float(raw.get(i, 0.0) * factor) / 100.0 + delta))) for i in skill_ids}
    pool_caps = [caps[i] for i in skill_ids if i not in exclude]
    meta = {"source": str(source), "source_sha256": sha256_file(Path(source)), "column": "fp_own_raw", "delta_pts": delta_pts,
            "k": k, "rows_without_fp_own_raw": int(blank.sum()), "skill_sum_raw": round(total, 3), "rescale_to": OWN_CAP_SKILL_SUM, "factor": round(factor, 6),
            "matched_skill_players": len(raw), "skill_players": len(skill_ids),
            "unnamed_skill_players_at_0": sum(1 for i in skill_ids if i not in raw), "coverage_projected_5": round(coverage, 4),
            "min_coverage": min_coverage, "cap_rows_hist_pool": dict(sorted(Counter(pool_caps).items())),
            "min_cap_rows": min(pool_caps) if pool_caps else None}
    return caps, meta


def _dk_text(x) -> str | None:
    """A DK player id as text ('123', never '123.0'); None when missing (study 38 6p's _dk)."""
    if x is None or (isinstance(x, float) and not np.isfinite(x)) or str(x).strip() in ("", "nan", "None"):
        return None
    try:
        return str(int(float(x)))
    except ValueError:
        return str(x).strip()


ONE_CATCHER_CELLS = ("B", "C")      # study 93's ONECATCH: the QB + 1 cells (nfl2 experiments/s93_leads.py QB1_CELLS)
GS_FAV_MARGIN, GS_HIGH_Q = 3.0, 2.0 / 3.0                  # study 97's FAV_MARGIN / HIGH_Q (nfl2 s97_game_script.py @ af07583e)


def game_script_sets(t70: pd.DataFrame, pool_ids: set[str]) -> dict:
    """Study 97's scenarios (nfl2 experiments/s97_game_script.py scenarios @ af07583e, module 7df6f324) on the pool's frame rows,
    pre-lock lines only: per team the median implied_team_total and game_total over its pool rows; margin = 2 x implied -
    total; a high-total game = its median total >= the slate's numpy quantile 2/3 over the games; FAV margin >= 3, FAVHI = FAV
    in a high-total game, HIGH, DOGHI = margin < 0 in a high-total game; opp_of = the other team(s) of the team's game. A team
    without both lines is in no set. SystemExit ("GAME SCRIPT REFUSED: ...") when the frame lacks either column."""
    if "implied_team_total" not in t70.columns or "game_total" not in t70.columns:
        raise SystemExit("GAME SCRIPT REFUSED: the T-70 frame lacks implied_team_total / game_total")
    f = t70[t70.id.astype(str).isin(set(pool_ids))]
    g = pd.DataFrame({"team": f.team.astype(str).to_numpy(), "game": f.game_id.astype(str).to_numpy(),
                      "itt": pd.to_numeric(f.implied_team_total, errors="coerce").to_numpy(),
                      "gt": pd.to_numeric(f.game_total, errors="coerce").to_numpy()})
    t = g.groupby("team").agg(itt=("itt", "median"), gt=("gt", "median")).dropna()
    games = g.groupby("game")["gt"].median().dropna()
    cut = float(np.quantile(games.to_numpy(float), GS_HIGH_Q)) if len(games) else float("inf")
    margin = 2.0 * t["itt"] - t["gt"]
    high = t["gt"] >= cut
    teams = {"FAV": set(t.index[margin >= GS_FAV_MARGIN]), "FAVHI": set(t.index[(margin >= GS_FAV_MARGIN) & high]),
             "HIGH": set(t.index[high]), "DOGHI": set(t.index[(margin < 0) & high])}
    tg = g.drop_duplicates("team").set_index("team")["game"]
    opp_of = {a: {b for b in tg.index if b != a and tg[b] == tg[a]} for a in tg.index}
    return {"high_cut": round(cut, 3), "teams": teams, "opp_of": opp_of}


RB_MATE_SCOPES = ("all", "favhi")    # study 97: only RBMATE4_FAVHI passed its pre-fixed rule; the other scopes are not built


def rb_mate_scope_teams(scope: str, t70: pd.DataFrame, pool_ids: set[str]) -> tuple[set[str] | None, str | None]:
    """Study 97's RBMATE4_FAVHI scope: (the QB teams whose (QB, own RB) pairs the RB-mate floor keeps, None) -- the expected
    winners (margin >= 3) of the slate's high-total games, game_script_sets' FAVHI -- or (None, why) when the scope is refused:
    the lines missing, or no (QB, own RB) pair of those teams in the pool. The caller then turns the RB mate OFF for the run (a
    refused scope never widens to every pair: study 96 read the unscoped RB mate PAPER ONLY). scope "all": (None, None)."""
    if scope == "all":
        return None, None
    if scope != "favhi":
        raise ValueError(f"rb_mate scope {scope!r} is not built (only {RB_MATE_SCOPES})")
    try:
        sets = game_script_sets(t70, pool_ids)
    except SystemExit as exc:
        return None, str(exc)
    teams = set(sets["teams"]["FAVHI"])
    f = t70[t70.id.astype(str).isin(set(pool_ids))]
    qb_t = set(f.team[f.pos.astype(str) == "QB"].astype(str))
    rb_t = set(f.team[f.pos.astype(str) == "RB"].astype(str))
    if not (teams & qb_t & rb_t):
        return None, (f"no (QB, own RB) pair of the expected winners of the high-total games (FAVHI {sorted(teams)}; the high-total "
                      f"cut {sets['high_cut']}) in the pool")
    return teams, None


RB_REC_VALUES = (1.5, 2.0)           # study 116's two pre-fixed doses (REC_LOW, REC); 0 = off
RB_REC_GAMES = 4
RB_REC_COLS = ("gsis_id", "rec_games", "rec_sum", "rec_per_game")


def rb_rec_low_ids(source: Path, t70: pd.DataFrame, threshold: float) -> tuple[set[str], dict]:
    """Study 116's RB receptions floor (the operator 10-10: "Let's try another experiment where we have a minimum number of
    receptions for a running back"; nfl2 experiments/s116_rec_floor.py): the frame ids of the RBs whose receptions per game -- the
    mean over his last up-to-4 stat-line games of this season before the week, read from the file written by
    reports/2026-10-10-rb-receptions/rb_rec_file.py -- are BELOW `threshold` (strict: a back at the threshold stays). Matched on the
    frame's gsis_id; an RB absent from the file (no game yet) or without a gsis_id is kept. Refuses (SystemExit 'RB REC FLOOR
    REFUSED: ...') on a missing file, a missing or non-JSON metadata line, games != 4, a season / week that is not the frame's, a
    missing column, no data rows, a non-finite number, a repeated gsis_id, rec_games outside 1..4, or a rec_per_game that is not
    rec_sum / rec_games."""
    def refuse(why: str):
        raise SystemExit(f"RB REC FLOOR REFUSED: {why}")
    if source is None or not Path(source).is_file():
        refuse(f"the receptions file {source} does not exist")
    name = Path(source).name
    lines = Path(source).read_text().splitlines()
    if not lines or not lines[0].startswith("# "):
        refuse(f"{name} has no metadata line")
    try:
        meta = json.loads(lines[0][2:])
    except ValueError:
        refuse(f"{name}: the metadata line is not JSON")
    if not isinstance(meta, dict) or meta.get("games") != RB_REC_GAMES:
        refuse(f"{name}: metadata games = {meta.get('games') if isinstance(meta, dict) else meta!r}, not {RB_REC_GAMES}")
    for key in ("season", "week"):
        got = set(pd.to_numeric(t70[key], errors="coerce").dropna().astype(int)) if key in t70.columns else set()
        if not isinstance(meta.get(key), int) or got != {meta[key]}:
            refuse(f"{name}: {key} {meta.get(key)!r} is not the frame's {sorted(got)}")
    d = pd.read_csv(source, skiprows=1, dtype={"gsis_id": str})
    missing = [c for c in RB_REC_COLS if c not in d.columns]
    if missing:
        refuse(f"{name} lacks {missing}")
    if d.empty:
        refuse(f"{name} has no data rows")
    num = d[["rec_games", "rec_sum", "rec_per_game"]].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(num.to_numpy(float)).all():
        refuse(f"{name}: a non-finite number")
    if d["gsis_id"].isna().any() or d["gsis_id"].duplicated().any():
        refuse(f"{name}: a missing or repeated gsis_id")
    if not num["rec_games"].isin(range(1, RB_REC_GAMES + 1)).all():
        refuse(f"{name}: rec_games outside 1..{RB_REC_GAMES}")
    if not np.allclose(num["rec_per_game"], num["rec_sum"] / num["rec_games"], rtol=0, atol=1e-9):
        refuse(f"{name}: a rec_per_game that is not rec_sum / rec_games")
    rpg = dict(zip(d["gsis_id"].astype(str), num["rec_per_game"].astype(float)))
    rbs = t70[t70.pos.astype(str) == "RB"]
    gs = rbs["gsis_id"] if "gsis_id" in rbs.columns else pd.Series([None] * len(rbs), index=rbs.index)
    low, kept = set(), 0
    for i, g in zip(rbs.id.astype(str), gs):
        v = rpg.get(str(g)) if g is not None and pd.notna(g) else None
        if v is None:
            kept += 1
        elif v < threshold:
            low.add(i)
    dks = dict(zip(t70.id.astype(str), t70["dk_player_id"])) if "dk_player_id" in t70.columns else {}
    return low, {"applied": True, "path": str(source), "sha256": sha256_file(Path(source)), "season": meta["season"],
                 "week": meta["week"], "threshold": threshold, "file_rows": int(len(d)), "pool_rbs": int(len(rbs)),
                 "kept_no_prior": kept, "dropped_ids": sorted(low),
                 "dropped_dk_ids": sorted(k for k in (_dk_text(dks.get(i)) for i in low) if k is not None)}


def one_catcher_line(block: dict | None) -> str:
    """Study 93's one printed line."""
    b = block or {}
    return (f"ONE CATCHER: at most one WR / TE per team on the B / C book rows ({b.get('teams')} teams); ruled "
            f"{b.get('ruled_solves')}, re-solved without it {len(b.get('resolved_without') or [])}; book rows with two WR / TE "
            f"of one team {b.get('pair_rows_book')} (B / C {b.get('pair_rows_bc')})")


def rb_mate_line(block: dict | None) -> str:
    """Study 96's one printed line."""
    b = block or {}
    return (f"RB MATE: the QB's own RB on the first {b.get('rows_cap')} C-cell book rows ({b.get('pairs')} pairs); slots "
            f"{len(b.get('slots') or [])}, ruled {len(b.get('ruled') or [])}, re-solved without it {len(b.get('resolved_without') or [])}")


def row_rule_sets(source: Path, t70: pd.DataFrame, exclude: set[str], low_pct: float) -> tuple[set[str], set[str], dict]:
    """Study 91's row rules (nfl2 experiments/s91_row_rules.py; the W5 paper arm's study 38 6p low_owned, lab b03ddaac): the
    pool's TEs, and the pool's SKILL players whose Fantasy Points projected ownership -- the ownership_fp file's fp_own_raw,
    FP's RAW % -- is below low_pct, matched by the frame id, then the DK id; a blank fp_own_raw (lag-filled) or a player the
    file does not name counts as 0% (low). Refuses (SystemExit 'ROW RULES REFUSED: ...') on a missing file / column or a
    non-number fp_own_raw."""
    def refuse(why: str):
        raise SystemExit(f"ROW RULES REFUSED: {why}")
    if source is None or not Path(source).is_file():
        refuse(f"the ownership file {source} does not exist")
    d = pd.read_csv(source, dtype=str)
    if "fp_own_raw" not in d.columns or "id" not in d.columns:
        refuse(f"{Path(source).name} lacks id / fp_own_raw")
    raw = d["fp_own_raw"].fillna("").astype(str).str.strip()
    num = pd.to_numeric(raw.where(raw != ""), errors="coerce")
    if bool((num.isna() & (raw != "")).any()):
        refuse(f"{Path(source).name}: a non-number fp_own_raw")
    by_id = {str(i): float(v) for i, v in zip(d["id"], num) if pd.notna(v)}
    by_dk = ({kk: float(v) for i, v in zip(d["dk_player_id"], num) if pd.notna(v) and (kk := _dk_text(i)) is not None}
             if "dk_player_id" in d.columns else {})
    pool = t70[~t70.id.astype(str).isin(exclude)]
    dks = pool["dk_player_id"] if "dk_player_id" in pool.columns else pd.Series([None] * len(pool))
    te, low, named, n_skill = set(), set(), 0, 0
    for i, dk, pos in zip(pool.id.astype(str), dks, pool.pos.astype(str)):
        if pos == "TE":
            te.add(i)
        if pos not in SKILL:
            continue
        n_skill += 1
        v = by_id.get(i)
        if v is None and _dk_text(dk) is not None:
            v = by_dk.get(_dk_text(dk))
        named += v is not None
        if v is None or v < low_pct:
            low.add(i)
    return te, low, {"source": str(source), "source_sha256": sha256_file(Path(source)), "low_pct": low_pct,
                     "pool_skill_players": n_skill, "named": named, "low_owned": len(low), "pool_tes": len(te)}


def mix_rows(t70: pd.DataFrame, exclude: set[str], k: int, max_shared: int, cap: int | None, min_salary: int,
             weights: list[int], exposure_cap: int | None = None, dst_cap: int | None = None,
             bonus: dict[str, float] | None = None, portfolio: str = "mix",
             spares: int = 0, qb_cap: int | None = None, fill: str = "group", cover_games: int = 0,
             rs_rows: int = 0, term_rows: int = 0,
             term_bonus: dict[str, float] | None = None,
             cell_quotas: dict[str, float] | None = None,
             bring_back_top_wr: tuple[str, ...] = (),
             bring_back_top_wr_rows: int | None = None,
             own_cap: dict[str, int] | None = None,
             row_bounds: list | None = None,
             one_catcher: bool = False,
             rb_mate_c: int = 0,
             rb_mate_qb_teams: set[str] | None = None) -> tuple[list[list[str]], list[str], dict, list[tuple[list[str], str]]]:
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
    Needs the MIX portfolio, the round-robin fill, no cover, no half-and-half and no whole-book ownership term.
    own_cap (study 89; the operator 10-09 "Live W5 trial if built in time"; default None = off, byte for byte today's book):
    player id -> rows; on every solve while j = len(prev) < k (the book: the live and term blocks; spares never) every player
    already in his own_cap rows is banned too, ONE solve with the solve's other rules; an infeasible solve is re-solved on the
    same state without the ownership bans (the lab's OwnCapBuilder: nfl2 experiments/s89_own_cap.py own_caps @ 4d0daa47),
    recorded as (cell, j).
    row_bounds (study 91; the operator 10-09 "use it in week 5" if better on both draws; default None = off, byte for byte
    today's book): (ids, lo, hi) member bounds -- at most one TE, at most one low-owned skill player -- on every solve while
    j < k (spares never), ONE call with the solve's other rules, INSIDE the ownership cap: infeasible -> the same solve without
    them (the ownership cap kept), recorded (cell, j) (study 38 6p's row_rules @ b03ddaac, entered before own_caps).
    one_catcher (study 93's ONECATCH; the operator 10-09 "Live W5 if built in time"; default False = off, byte for byte today's
    book): on every solve of a QB + 1 cell (B, C) while j < k (the book: the live AND the term block; spares never; A1 / A2
    never) the row holds at most ONE WR / TE of EVERY team: member_bounds (team T's pool WR / TE, 0, 1) for every team T,
    appended to row_bounds, ONE call; infeasible -> the same solve with row_bounds only (the one-catcher dropped first,
    recorded (cell, j)), then row_bounds' own fallback (nfl2 experiments/s93_leads.py lead_rules @ 5f4e1fb9, onepc, inside
    6p's row rules and 89's own_caps). Needs row_bounds, the MIX portfolio, fill rr, no cover, no half-and-half, no study-71
    floor.
    rb_mate_c N (study 94's RBMATE4 with study 93's ONECATCH, read together by study 96; the operator 10-09 "Try live W5 if
    built"; default 0 = off, byte for byte today's book): on the first N C-cell solves while j < k (build order; the live and
    the term block; a slot is taken at the solve, whether ruled or not, so an ownership-cap re-peek takes another; spares
    never) the row holds its QB's OWN RB: the pinned optimize's interaction floor over (QB, RB of the QB's team) pool pairs,
    weight 1, floor 1, in ONE call with row_bounds and the one-catcher bounds; infeasible -> the same solve without the floor
    (recorded), then ONECATCH's own tiers (nfl2 experiments/s96_onecatch_rbmate.py combo_rules @ 3cf3e8eb). Needs one_catcher.
    rb_mate_qb_teams (study 97's RBMATE4_FAVHI scope; default None = every pair): the floor's pairs only for QBs of these teams
    (nfl2 experiments/s97_game_script.py rm_pairs_for @ af07583e); the caller passes rb_mate_scope_teams' FAVHI set."""
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

    # study 71 (default off: () = no cell, every solve below byte for byte as before): in the designated cells (A1 / B, the
    # cells whose rules REQUIRE a bring-back) the row holds its QB's opponent's TOP RECEIVER -- the highest-salaried WR in
    # THIS buildable pool (ties: projection, then id; study 70's top_wr) -- through the pinned optimize()'s interaction
    # floor: weight 1 on every (QB, his opponent's top WR) pair, floor 1 (a lineup holds one QB). A designated solve the
    # floor makes infeasible is re-solved WITHOUT it on the same state, counted and recorded by row identity.
    bb_cells = tuple(bring_back_top_wr or ())
    bb_top: dict[str, str] = {}
    bb_pairs: dict[tuple[str, str], float] = {}
    bb_state: dict = {"phase": "book", "floored": Counter(), "fallbacks": [], "floored_rows": [], "designated_unfloored": 0}
    bb_cap = bring_back_top_wr_rows                            # study 71b (None = every designated solve, as before)
    if bb_cap is not None and (not bb_cells or int(bb_cap) != bb_cap or bb_cap < 1):
        raise ValueError(f"bring_back_top_wr_rows {bb_cap} needs bring_back_top_wr cells and an integer >= 1")
    if bb_cells:
        bad = [c for c in bb_cells if c not in MS_TOP_WR_RULE_CELLS]
        if portfolio != "mix" or bad or len(set(bb_cells)) != len(bb_cells):
            raise ValueError(f"bring_back_top_wr {list(bb_cells)} needs the MIX portfolio and distinct cells from "
                             f"{list(MS_TOP_WR_RULE_CELLS)} (the cells that require a bring-back); got portfolio {portfolio}")
        bb_top = ms_top_receivers(pool)
        bb_pairs = {(p["id"], bb_top[str(p["opp"])]): 1.0 for p in pool if p["pos"] == "QB" and str(p["opp"]) in bb_top}
    name_of_id = {p["id"]: p.get("name") for p in pool}

    def floor_open() -> bool:
        """Study 71b, 84's definition exactly (nfl2 experiments/s71b_topbb_n.py, TopBBNBuilder.solve_with @ c2f5638): the
        floor goes on a designated solve only while j < k AND fewer than N rows have been committed under it, where j =
        len(prev), the rows committed BEFORE the solve -- the row index, not the phase flag. A floored solve that is
        infeasible is re-solved plain and does not count. With a full book (a short MIX book is refused: "MIX MAIN
        REFUSED" / check_main_rows) the spares start at j = k, so a spare never gets the rule under a cap; the phase flag
        only labels the records. No cap: always open (every designated solve, the merged behaviour)."""
        if bb_cap is None:
            return True
        return len(prev) < k and len(bb_state["floored_rows"]) < bb_cap

    own_state: dict = {"ruled": [], "plain": [], "bound": []}

    def peek(name: str, extra_bans: frozenset = frozenset(), use_term: bool = False):
        """Study 89's ownership cap around _peek (absent when own_cap is None): on a book solve (j < k) the players at their
        cap are banned too; infeasible -> the same peek without them, recorded."""
        j = len(prev)
        if not own_cap or j >= k:
            return _peek(name, extra_bans, use_term)
        at = frozenset(p for p, c in count.items() if p in own_cap and c >= own_cap[p])
        got = _peek(name, frozenset(extra_bans) | at, use_term)
        if got[0] is not None:
            own_state["ruled"].append((name, j)); own_state["bound"].append(len(at))
            return got
        own_state["plain"].append((name, j))
        return _peek(name, extra_bans, use_term)

    row_state: dict = {"ruled": [], "plain": []}
    rb = [(sorted(ids), int(lo), int(hi)) for ids, lo, hi in (row_bounds or [])]

    # study 93's ONECATCH (default off: every solve below byte for byte as before): on a B / C book solve the bounds
    # (team T's pool WR / TE, 0, 1) ride with rb in one call; the record lists [cell, j] of the ruled and the dropped solves
    # and the ruled rows by identity.
    oc_state: dict = {"ruled": [], "plain": [], "rows": [], "pending": None}
    oc_bounds: list = []
    if one_catcher:
        if not rb or portfolio != "mix" or fill != "rr" or cover_games or rs_rows or bb_cells:
            raise ValueError(f"one_catcher needs row_bounds, the MIX portfolio, fill rr, no cover, no half-and-half and no "
                             f"study-71 floor (got row bounds {len(rb)}, portfolio {portfolio}, fill {fill}, cover {cover_games}, "
                             f"rs {rs_rows}, top-WR cells {list(bb_cells)})")
        oc_team: dict[str, list[str]] = {}
        for p in pool:
            if p["pos"] in ("WR", "TE"):
                oc_team.setdefault(str(p["team"]), []).append(str(p["id"]))
        oc_bounds = [(sorted(ids), 0, 1) for _, ids in sorted(oc_team.items())]

    # study 94's RBMATE on top of ONECATCH (default 0 = off: every solve below byte for byte as before): the first N C-cell
    # book solves carry the interaction floor over (QB, his team's RB) pairs with rb + the one-catcher bounds in one call.
    rm_state: dict = {"used": [], "ruled": [], "plain": [], "rows": [], "pending": None}
    rm_pairs: dict = {}
    if rb_mate_c:
        if not oc_bounds or int(rb_mate_c) != rb_mate_c or rb_mate_c < 0:
            raise ValueError(f"rb_mate_c {rb_mate_c} needs one_catcher (and so the row rules) and an integer >= 0")
        rm_rbs: dict[str, list[str]] = {}
        for p in pool:
            if p["pos"] == "RB":
                rm_rbs.setdefault(str(p["team"]), []).append(str(p["id"]))
        rm_pairs = {(str(p["id"]), r): 1.0 for p in pool if p["pos"] == "QB" for r in rm_rbs.get(str(p["team"]), [])}
        if rb_mate_qb_teams is not None:                       # study 97's scope: only the QBs of the scope's teams
            team_of = {str(p["id"]): str(p["team"]) for p in pool}
            rm_pairs = {(q, r): w for (q, r), w in rm_pairs.items() if team_of.get(q) in rb_mate_qb_teams}

    def _peek(name: str, extra_bans: frozenset = frozenset(), use_term: bool = False):
        """Study 91's row rules around _solve (absent when row_bounds is None): on a book solve (j < k) the bounds ride as
        member_bounds, one call; infeasible -> the same solve without them, recorded. Called inside peek's ownership cap."""
        j = len(prev)
        if not rb or j >= k:
            return _solve(name, extra_bans, use_term)
        if rb_mate_c and name == "C" and len(rm_state["used"]) < int(rb_mate_c):  # study 94's RBMATE first (absent when off)
            rm_state["used"].append((name, j))                # the slot is taken, ruled or not
            got = _solve(name, extra_bans, use_term, rb + oc_bounds, rm_pairs)   # no pair in the pool: no floor (as the lab)
            if got[0] is not None:
                rm_state["ruled"].append((name, j)); rm_state["pending"] = name
                oc_state["ruled"].append((name, j)); oc_state["pending"] = name
                row_state["ruled"].append((name, j))
                return got
            rm_state["plain"].append((name, j))                # infeasible: the floor dropped, ONECATCH and rb kept
        if oc_bounds and name in ONE_CATCHER_CELLS:            # study 93's ONECATCH first (absent when off)
            got = _solve(name, extra_bans, use_term, rb + oc_bounds)
            if got[0] is not None:
                oc_state["ruled"].append((name, j)); oc_state["pending"] = name
                row_state["ruled"].append((name, j))
                return got
            oc_state["plain"].append((name, j))                # infeasible: the one-catcher dropped, rb kept
        got = _solve(name, extra_bans, use_term, rb)
        if got[0] is not None:
            row_state["ruled"].append((name, j))
            return got
        row_state["plain"].append((name, j))
        return _solve(name, extra_bans, use_term)

    def _solve(name: str, extra_bans: frozenset = frozenset(), use_term: bool = False, member_bounds: list | None = None,
               floor: dict | None = None):
        """The cell's next row on the CURRENT state, not committed: (ids, objective value, fallback) or (None, None, None).
        use_term: on the term block's objective (projection + the capped term). fallback: None, or why a study-71 cell's
        row was built WITHOUT the top-WR floor ("infeasible with the floor" / "no pairs"), or "plain" for a designated solve
        the study-71b cap left without it (not a fallback, not a violation)."""
        _, rules, qmax, which = cells[name]
        bans = {p for p, c in count.items() if exposure_cap is not None and c >= exposure_cap} | set(extra_bans)
        if dst_cap is not None:
            bans |= {p for p, c in count.items() if p in dst_ids and c >= dst_cap}
        if qb_cap is not None:                                  # study 35's per-QB cap (10-06; default off)
            bans |= {p for p, c in count.items() if p in qb_ids and c >= qb_cap}
        use_pool, use_obj = (term_pool, "obj") if use_term else (pool, objective)
        kw = dict(stack=StackRules(**rules), objective_col=use_obj, banned_lineups=prev, max_overlap=max_shared,
                  bans=bans or None, env=env, second_game_pair=games if which == "all" else None, qb_game_max=qmax)
        if member_bounds:                                      # study 91's row rules (absent when off)
            kw["member_bounds"] = member_bounds
        if floor:                                              # study 94's RBMATE floor (absent when off; never with study 71)
            kw.update(interaction_floor_weights=floor, interaction_floor=1.0)
        fb = None
        if name in bb_cells and floor_open():
            lu = optimize(use_pool, interaction_floor_weights=bb_pairs, interaction_floor=1.0, **kw) if bb_pairs else None
            if lu is None:
                fb = "infeasible with the floor" if bb_pairs else "no pairs"
                lu = optimize(use_pool, **kw)
        else:
            if name in bb_cells:                               # study 71b: the cap is closed (or a spare under a cap)
                fb = "plain"
            lu = optimize(use_pool, **kw)
        if lu is None:
            return None, None, None
        return [str(p["id"]) for p in lu.players], float(sum(p.get(use_obj, p["proj"]) for p in lu.players)), fb

    row_value: dict[tuple, float] = {}                         # each committed row's objective sum, as solved (a term row's
                                                               # includes its term; read only to order cover rows, refused with the block)

    def commit(ids: list[str], value: float | None = None, cell: str | None = None, fb: str | None = None) -> list[str]:
        prev.append(frozenset(ids)); count.update(ids)
        if rm_state["pending"] is not None:                    # study 94's record (nothing when off)
            row = sorted(str(i) for i in ids)
            rm_state["rows"].append({"cell": rm_state["pending"], "commit_index": len(prev) - 1, "row": row,
                                     "row_sha256": hashlib.sha256(",".join(row).encode()).hexdigest()})
            rm_state["pending"] = None
        if oc_state["pending"] is not None:                    # study 93's record (nothing when off)
            row = sorted(str(i) for i in ids)
            oc_state["rows"].append({"cell": oc_state["pending"], "commit_index": len(prev) - 1, "row": row,
                                     "row_sha256": hashlib.sha256(",".join(row).encode()).hexdigest()})
            oc_state["pending"] = None
        if value is not None:
            row_value[tuple(ids)] = value
        if cell is not None and cell in bb_cells:              # study 71's record (nothing when off)
            if fb == "plain":                                  # study 71b: a designated row past the cap (or a spare), plain
                if len(prev) - 1 < k:                          # a BOOK row by 84's definition (j < k)
                    bb_state["designated_unfloored"] += 1
            elif fb is None:
                bb_state["floored"][bb_state["phase"]] += 1
                if bb_cap is not None:                          # the floored rows' identities: the rule binds only these
                    row = sorted(str(i) for i in ids)
                    bb_state["floored_rows"].append({"cell": cell, "commit_index": len(prev) - 1, "kind": bb_state["phase"],
                                                     "row": row, "row_sha256": hashlib.sha256(",".join(row).encode()).hexdigest()})
            else:
                q = next((i for i in ids if i in qb_ids), None)
                row = sorted(str(i) for i in ids)
                bb_state["fallbacks"].append({"cell": cell, "commit_index": len(prev) - 1, "kind": bb_state["phase"],
                                              "qb": name_of_id.get(q), "reason": fb, "row": row,
                                              "row_sha256": hashlib.sha256(",".join(row).encode()).hexdigest()})
        return ids

    def solve(name: str, extra_bans: frozenset = frozenset(), use_term: bool = False):
        ids, v, fb = peek(name, extra_bans, use_term)
        return commit(ids, v, name, fb) if ids is not None else None

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
                ids, v, fb = peek(name, frozenset(hard | ms_tier_bans(rs_count, qb_ids, qt) | ms_tier_bans(rs_count, nonqb_ids, nt)))
                if ids is not None:
                    if dn or dq:
                        relaxed.append([rs_done[0], dn, dq])
                    commit(ids, v, name, fb); rs_count.update(ids); rs_done[0] += 1
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
                ids, val, fb = peek(n)
                if ids is None:
                    if "A1" in cells and n != "A1":            # its remaining quota passes to A1 (counted)
                        passes += remaining[n]; remaining["A1"] += remaining[n]
                    remaining[n] = 0
                    continue
                if best is None or val > best[2]:                 # strict: a tie keeps the earlier cell
                    best = (n, ids, val, fb)
            if best is None:
                break
            n, ids, v, fb = best
            rows[n].append(commit(ids, v, n, fb)); remaining[n] -= 1; commit_order.append(n)
    else:
        raise ValueError(f"fill must be 'group', 'value' or 'rr' (got {fill!r})")
    if covered:                                                # a coverage row takes the deal position its projection earns
        rows["A1"] = sorted(rows["A1"], key=lambda ids: -row_value[tuple(ids)])
    got = [len(rows[n]) for n in names]
    spare_rows: list[tuple[list[str], str]] = []
    bb_state["phase"] = "spare"                                # study 71's record: rows solved from here on are spares
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
    if rb:                                                     # study 91's receipt block (absent when off)
        meta["row_rules"] = {"bounds": [{"ids": len(ids), "lo": lo, "hi": hi} for ids, lo, hi in rb],
                             "ruled_solves": len(row_state["ruled"]), "resolved_without": [list(x) for x in row_state["plain"]]}
    if oc_bounds:                                              # study 93's receipt block (absent when off)
        if oc_state["pending"] is not None or len(oc_state["rows"]) != len(oc_state["ruled"]):
            raise ValueError(f"ONE CATCHER RECORD BROKEN: {len(oc_state['ruled'])} ruled solves, {len(oc_state['rows'])} committed, "
                             f"pending {oc_state['pending']}")
        catcher_team = {i: t for t, ids in oc_team.items() for i in ids}

        def paired(r) -> bool:
            return max(Counter(catcher_team[i] for i in r if i in catcher_team).values(), default=0) > 1
        meta["one_catcher"] = {"cells": list(ONE_CATCHER_CELLS), "max_per_team": 1, "teams": len(oc_bounds),
                               "ruled_solves": len(oc_state["ruled"]), "ruled": [list(x) for x in oc_state["ruled"]],
                               "resolved_without": [list(x) for x in oc_state["plain"]], "ruled_rows": oc_state["rows"],
                               "pair_rows_book": sum(1 for r in book if paired(r)),
                               "pair_rows_bc": sum(1 for r, cl in zip(book, cell_of) if cl in ONE_CATCHER_CELLS and paired(r))}
    if rb_mate_c:                                              # study 94's receipt block (absent when off)
        if rm_state["pending"] is not None or len(rm_state["rows"]) != len(rm_state["ruled"]):
            raise ValueError(f"RB MATE RECORD BROKEN: {len(rm_state['ruled'])} ruled solves, {len(rm_state['rows'])} committed, "
                             f"pending {rm_state['pending']}")
        meta["rb_mate"] = {"cell": "C", "rows_cap": int(rb_mate_c), "pairs": len(rm_pairs),
                           "scope": "all" if rb_mate_qb_teams is None else "favhi",
                           "qb_teams": None if rb_mate_qb_teams is None else sorted(rb_mate_qb_teams),
                           "slots": [list(x) for x in rm_state["used"]], "ruled": [list(x) for x in rm_state["ruled"]],
                           "resolved_without": [list(x) for x in rm_state["plain"]], "ruled_rows": rm_state["rows"]}
    if own_cap:                                                # study 89's receipt block (absent when off)
        meta["own_cap"] = {"players": len(own_cap), "ruled_solves": len(own_state["ruled"]),
                           "resolved_without": [list(x) for x in own_state["plain"]],
                           "banned_per_solve_mean": round(float(np.mean(own_state["bound"])), 2) if own_state["bound"] else 0.0,
                           "banned_per_solve_max": max(own_state["bound"]) if own_state["bound"] else 0}
    if bb_cells:                                               # study 71's receipt block (absent when off)
        player = {p["id"]: p for p in pool}
        meta["bring_back_top_wr"] = {
            "cells": list(bb_cells),
            "rule": ("the row's QB's opponent's top receiver (the highest-salaried WR in the buildable pool; ties: projection, "
                     "then id) is in the row (interaction floor 1 over (QB, opponent top WR) pairs)"),
            "top_wr": {t: {"id": i, "name": player[i].get("name"), "salary": int(player[i].get("salary") or 0)} for t, i in bb_top.items()},
            "pairs": len(bb_pairs),
            "qbs_without_top_wr_opponent": sorted(str(p.get("name")) for p in pool if p["pos"] == "QB" and str(p["opp"]) not in bb_top),
            "rows_floored": {"book": int(bb_state["floored"]["book"]), "spares": int(bb_state["floored"]["spare"])},
            "fallbacks": bb_state["fallbacks"]}
        if bb_cap is not None:                                 # study 71b's delta (absent without a cap)
            meta["bring_back_top_wr"].update({"rows_cap": int(bb_cap), "floored_rows": bb_state["floored_rows"],
                                              "designated_unfloored": int(bb_state["designated_unfloored"])})
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


def parse_bring_back_top_wr(spec: str, main: str, portfolio: str | None) -> tuple[str, ...]:
    """--mix-bring-back-top-wr (study 71): "" -> () (off); else distinct cells from mix_shapes.TOP_WR_RULE_CELLS (A1, B: the
    cells that REQUIRE a bring-back; A2 / C forbid one), with --main mix --mix-portfolio mix. SystemExit otherwise."""
    cells = tuple(c.strip() for c in str(spec or "").split(",") if c.strip())
    if not cells:
        return ()
    bad = [c for c in cells if c not in MS_TOP_WR_RULE_CELLS]
    if main != "mix" or portfolio != "mix" or bad or len(set(cells)) != len(cells):
        raise SystemExit(f"--mix-bring-back-top-wr {spec!r}: distinct cells from {list(MS_TOP_WR_RULE_CELLS)} (A2 / C forbid a "
                         f"bring-back), with --main mix --mix-portfolio mix (study 71); got main {main}, portfolio {portfolio}")
    return cells


def parse_bring_back_top_wr_rows(rows: int | None, cells: tuple[str, ...]) -> int | None:
    """--mix-bring-back-top-wr-rows (study 71b): None (unset) = every designated solve; else an integer >= 1, only with
    --mix-bring-back-top-wr cells. SystemExit otherwise."""
    if rows is None:
        return None
    if rows < 1 or not cells:
        raise SystemExit(f"--mix-bring-back-top-wr-rows {rows}: an integer >= 1, with --mix-bring-back-top-wr (study 71b)")
    return int(rows)


def bring_back_top_wr_line(block: dict | None) -> str:
    """Study 71's printed line (and a CAPITALS banner line when any row was built without the floor)."""
    b = block or {}
    fb = b.get("fallbacks") or []
    rf = b.get("rows_floored") or {}
    cells = ",".join(b.get("cells") or [])
    line = (f"BRING-BACK TOP WR: cells {cells}; {rf.get('book', 0)} book rows + {rf.get('spares', 0)} spares floored; "
            f"{len(fb)} fallbacks")
    if b.get("rows_cap") is not None:                          # study 71b
        line += f"; rows cap {b['rows_cap']} ({b.get('designated_unfloored', 0)} designated book rows past it, built plain)"
    if fb:
        where = " ".join(f"{x['cell']}@{x['commit_index']}" for x in fb)
        line += f" (built without the floor: {where})"
        line += f"\n!!! {len(fb)} STUDY-71 ROW(S) BUILT WITHOUT THE TOP-WR FLOOR (recorded in the receipt's bring_back_top_wr.fallbacks)"
    return line


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
    ap.add_argument("--main-own-cap-delta", type=float, default=0.0,
                    help="study 89 (the operator 10-09: 'Live W5 trial if built in time'; default 0 = off, byte for byte today's book): "
                         "with --main mix, every skill player is capped at floor(K x (own / 100 + D / 100)) main-book rows, own = the "
                         "file's fp_own_raw rescaled so the frame's skill players sum to 800%%; e.g. 15 (percentage points)")
    ap.add_argument("--main-own-cap-source", type=Path, default=None,
                    help="with --main-own-cap-delta: the week's ownership_fp csv (id, dk_player_id, fp_own_raw), from scripts/ownership_fp.py")
    ap.add_argument("--main-own-cap-min-coverage", type=float, default=0.9,
                    help="with --main-own-cap-delta: refuse when the file names fewer than this share of the pool's skill players projected >= 5")
    ap.add_argument("--main-own-cap-fallback-share", type=float, default=None,
                    help="with --main-own-cap-delta: when the ownership cap is REFUSED, build with THIS player-cap share instead of "
                         "--main-cap-share (the operator's rule 10-09: the flat 35%% never runs alone; e.g. 0.5) and print an alert")
    ap.add_argument("--mix-max-te", type=int, default=None,
                    help="study 91 (default off): with --main mix and the ownership cap applied, at most this many TEs per main-book row (1)")
    ap.add_argument("--mix-max-low-own", type=int, default=None,
                    help="study 91 (default off): with --main mix and the ownership cap applied, at most this many skill players per "
                         "main-book row whose FP projected ownership (--main-own-cap-source's fp_own_raw, raw %%; blank = 0%%) is below "
                         "--mix-low-own-pct (1)")
    ap.add_argument("--mix-low-own-pct", type=float, default=3.0, help="study 91: the low-ownership threshold in percent (3)")
    ap.add_argument("--mix-rb-mate-c", type=int, default=0,
                    help="study 94's RBMATE4 with ONECATCH (study 96; default 0 = off; only 4, the tested value): the first N "
                         "C-cell BOOK solves hold the QB's own RB (an interaction floor), in one solve with the row rules and "
                         "the one-catcher bounds; infeasible -> without the floor, recorded. Needs --mix-one-catcher-all; LOUDLY off "
                         "whenever ONECATCH is not applied")
    ap.add_argument("--mix-rb-mate-scope", choices=RB_MATE_SCOPES, default="all",
                    help="study 97 (default all = every (QB, own RB) pair, today's --mix-rb-mate-c): favhi = only the QBs of the "
                         "expected winners (margin = 2 x implied - total >= 3) of the slate's high-total games (>= its 2/3 "
                         "quantile); needs --mix-rb-mate-c 4; a refused scope (no lines, no such pair) turns the RB mate OFF, LOUDLY")
    ap.add_argument("--mix-min-rb-rec", type=float, default=0.0,
                    help="study 116's RB receptions floor (default 0 = off; only 1.5 or 2.0, its two pre-fixed doses): an RB whose "
                         "receptions per game (his last up-to-4 stat-line games this season, from --mix-rb-rec-source) is below "
                         "this leaves the pool, with the --min-proj floor (before the caps, row-rule sets, term and RB-mate "
                         "pairs); a refused file builds WITHOUT it, LOUDLY")
    ap.add_argument("--mix-rb-rec-source", type=Path, default=None,
                    help="with --mix-min-rb-rec: the receptions file (reports/2026-10-10-rb-receptions/rb_rec_file.py)")
    ap.add_argument("--mix-one-catcher-all", action="store_true",
                    help="study 93's ONECATCH (default off): every B / C (QB + 1) BOOK solve, the live and the term block alike, "
                         "holds at most ONE WR / TE of every team, in one solve with the row rules; infeasible -> re-solved with "
                         "the row rules only, recorded. Needs --mix-max-te 1 and --mix-max-low-own 1 on the ownership cap; LOUDLY "
                         "off whenever the row rules are not applied")
    ap.add_argument("--main", choices=["mean", "pmo_x50", "mix"], default="mean",
                    help="the main book: mean = the union pool's top-K by projected sum (paper arm); pmo_x50 = K capped plain-mean-optimizer rows solved on the T-70 frame (ENTERS Week 4); "
                         "mix = study 18's shape portfolio: the same capped solves by cell (nfl_dfs.inference.mix_shapes), ordered by the plan's entry-weighted interleave")
    ap.add_argument("--proj-source", type=Path, default=None,
                    help="an override file from scripts/fp_projection_override.py built for THIS T-70 frame: its projections replace "
                         "the frame's mean_projection for the players it holds (operator 10-05: Fantasy Points)")
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
    ap.add_argument("--mix-bring-back-top-wr", default="",
                    help="study 71 (default empty = off): a comma list of MIX cells from A1,B whose rows hold the QB's opponent's "
                         "top receiver (the highest-salaried WR in the buildable pool; ties projection, then id) through the "
                         "optimizer's interaction floor; a solve the floor makes infeasible is built without it and recorded")
    ap.add_argument("--mix-bring-back-top-wr-rows", type=int, default=None,
                    help="study 71b (default unset = every designated solve): the floor goes on designated solves only while "
                         "fewer than N BOOK rows (row index < the book's K) have been committed under it; spares never; an "
                         "infeasible floored solve is built plain, recorded, and does not count")
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
    if a.main_own_cap_delta and a.main != "mix":
        raise SystemExit("--main-own-cap-delta is defined for --main mix (study 89's book)")
    if a.main_own_cap_fallback_share is not None and not (a.main_own_cap_delta and 0 < a.main_own_cap_fallback_share <= 1):
        raise SystemExit("--main-own-cap-fallback-share needs --main-own-cap-delta and a share in (0, 1]")
    if (a.mix_max_te is not None or a.mix_max_low_own is not None) and (a.main != "mix" or not a.main_own_cap_delta
                                                                         or a.main_own_cap_source is None):
        raise SystemExit("--mix-max-te / --mix-max-low-own are defined for --main mix with the ownership cap "
                         "(--main-own-cap-delta and --main-own-cap-source; study 91 is read on his armed package)")
    if any(v is not None and v != 1 for v in (a.mix_max_te, a.mix_max_low_own)) or not 0 < a.mix_low_own_pct <= 20:
        raise SystemExit("--mix-max-te / --mix-max-low-own take 1 (study 91's tested value); --mix-low-own-pct in (0, 20]")
    if a.mix_one_catcher_all and (a.main != "mix" or a.mix_portfolio != "mix" or a.mix_fill != "rr" or a.mix_max_te != 1
                                  or a.mix_max_low_own != 1 or a.mix_cover_games or a.mix_rs_rows or a.mix_bring_back_top_wr
                                  or a.winner_select is not None):
        raise SystemExit("--mix-one-catcher-all is defined on his armed version only (study 93): --main mix --mix-portfolio mix "
                         "--mix-fill rr with the ownership cap and --mix-max-te 1 --mix-max-low-own 1, and no --mix-cover-games / "
                         "--mix-rs-rows / --mix-bring-back-top-wr / --winner-select")
    if a.mix_rb_mate_scope != "all" and a.mix_rb_mate_c != 4:
        raise SystemExit(f"--mix-rb-mate-scope {a.mix_rb_mate_scope} needs --mix-rb-mate-c 4 (study 97 read the scope on the RB mate)")
    if a.mix_min_rb_rec not in (0.0,) + RB_REC_VALUES or (a.mix_min_rb_rec and (a.main != "mix" or a.mix_rb_rec_source is None)):
        raise SystemExit(f"--mix-min-rb-rec {a.mix_min_rb_rec:g}: 0 (off), or {' / '.join(f'{v:g}' for v in RB_REC_VALUES)} "
                         "(study 116's doses) with --main mix and --mix-rb-rec-source")
    if a.mix_rb_rec_source is not None and not a.mix_min_rb_rec:
        raise SystemExit("--mix-rb-rec-source is read only with --mix-min-rb-rec 1.5 or 2")
    if a.mix_rb_mate_c not in (0, 4) or (a.mix_rb_mate_c and not a.mix_one_catcher_all):
        raise SystemExit("--mix-rb-mate-c takes 0 or 4 (study 96's tested value) and needs --mix-one-catcher-all (it was read only on "
                         "top of ONECATCH)")
    if a.main_own_cap_delta and a.main_cap_share != 0.5 and a.main_own_cap_fallback_share is None:
        raise SystemExit("--main-own-cap-delta with --main-cap-share != 0.5 needs --main-own-cap-fallback-share (his rule 10-09: a "
                         "refused ownership cap must never leave the flat player cap running alone)")
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
    bb_cells = parse_bring_back_top_wr(a.mix_bring_back_top_wr, a.main, a.mix_portfolio)
    bb_rows = parse_bring_back_top_wr_rows(a.mix_bring_back_top_wr_rows, bb_cells)
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
    cap = a.max_per_game if a.max_per_game > 0 else None
    rb_rec_low: set[str] = set()                         # study 116: the RBs below the receptions floor leave with --min-proj's
    rb_rec_meta: dict | None = None
    if a.mix_min_rb_rec:
        try:
            rb_rec_low, rb_rec_meta = rb_rec_low_ids(a.mix_rb_rec_source, fr, a.mix_min_rb_rec)
            print(f"RB REC FLOOR: RBs under {a.mix_min_rb_rec:g} receptions per game leave the pool -- {len(rb_rec_low)} of "
                  f"{rb_rec_meta['pool_rbs']} frame RBs ({rb_rec_meta['kept_no_prior']} kept with no game yet; "
                  f"{Path(a.mix_rb_rec_source).name} {rb_rec_meta['sha256'][:8]})", flush=True)
        except SystemExit as exc:
            rb_rec_low, rb_rec_meta = set(), {"applied": False, "not_applied": str(exc), "threshold": a.mix_min_rb_rec,
                                              "path": str(a.mix_rb_rec_source)}
            print(f"\n!!! RB REC FLOOR NOT APPLIED: {exc} -- the book is built without it\n", flush=True)

    # the pool: T-70 rows (the same T-70 rules applied defensively: a clean T-70 build drops nothing here), Saturday
    # survivors, optional PMO rows
    t70_rosters, t70_idx, t70_counts = survivors(t70["cands"], fr, set(), a.min_proj, cap, dk, rb_rec_low)
    t70_set = {frozenset(r) for r in t70_rosters}
    sat_rosters, sat_idx, counts = survivors(sat["cands"], fr, t70_set, a.min_proj, cap, dk, rb_rec_low)
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
        excl = gone | {i for i in proj_all if pos_all[i] in SKILL and not (proj_all[i] >= a.min_proj)} | rb_rec_low
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
            excl_f = set(unavailable_ids(fr, dk)) | {i for i in proj_f if pos_f[i] in SKILL and not (proj_f[i] >= a.min_proj)} | rb_rec_low
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
        excl = gone | {i for i in proj_all if pos_all[i] in SKILL and not (proj_all[i] >= a.min_proj)} | rb_rec_low
        xcap = main_exposure_cap(a.main_cap_share, a.entries)
        cap_share_used = a.main_cap_share
        own_cap, own_cap_meta = None, None
        if a.main_own_cap_delta:                         # study 89: any refusal builds WITHOUT it, LOUDLY (and at the fallback share)
            try:
                own_cap, own_cap_meta = own_cap_rows(a.main_own_cap_source, fr, excl, a.main_own_cap_delta, a.entries,
                                                     a.main_own_cap_min_coverage)
                own_cap_meta.update({"applied": True, "cap_share_used": cap_share_used})
                print(f"OWN CAP: every skill player at most floor({a.entries} x (own / 100 + {a.main_own_cap_delta:g} / 100)) main rows "
                      f"(own = fp_own_raw x {own_cap_meta['factor']:.4f}, the frame's skill players summing to {OWN_CAP_SKILL_SUM:g}%); "
                      f"pool cap rows {own_cap_meta['cap_rows_hist_pool']}; the player cap {xcap} rows also applies", flush=True)
            except SystemExit as exc:
                own_cap, own_cap_meta = None, {"applied": False, "not_applied": str(exc)}
                if a.main_own_cap_fallback_share is not None:
                    cap_share_used = a.main_own_cap_fallback_share
                    xcap = main_exposure_cap(cap_share_used, a.entries)
                    own_cap_meta["fallback_cap_share"] = cap_share_used
                own_cap_meta["cap_share_used"] = cap_share_used
                print(f"\n!!! OWN CAP NOT APPLIED: {exc} -- the book is built without it at the player-cap share {cap_share_used} "
                      f"({xcap} rows)\n", flush=True)
        row_bounds, row_meta = None, None
        if a.mix_max_te is not None or a.mix_max_low_own is not None:   # study 91: only on the applied ownership cap, else LOUDLY off
            if own_cap is None:
                row_meta = {"applied": False, "not_applied": "the ownership cap is not applied"}
            else:
                try:
                    te_ids, low_ids, row_meta = row_rule_sets(a.main_own_cap_source, fr, excl, a.mix_low_own_pct)
                    row_bounds = ([(te_ids, 0, a.mix_max_te)] if a.mix_max_te is not None else []) + \
                                 ([(low_ids, 0, a.mix_max_low_own)] if a.mix_max_low_own is not None else [])
                    row_meta.update({"applied": True, "te_max": a.mix_max_te, "low_own_max": a.mix_max_low_own})
                    print(f"ROW RULES: at most {a.mix_max_te} TE and at most {a.mix_max_low_own} skill player under "
                          f"{a.mix_low_own_pct:g}% FP projected ownership per main row ({len(te_ids)} TEs, {len(low_ids)} low-owned "
                          f"of {row_meta['pool_skill_players']} pool skill players)", flush=True)
                except SystemExit as exc:
                    row_bounds, row_meta = None, {"applied": False, "not_applied": str(exc)}
            if row_bounds is None:
                print(f"\n!!! ROW RULES NOT APPLIED: {row_meta['not_applied']} -- the book is built without them\n", flush=True)
        oc_on, oc_meta = False, None
        if a.mix_one_catcher_all:                            # study 93: only with the applied row rules, else LOUDLY off
            oc_on = bool(row_bounds)
            oc_meta = {"applied": True} if oc_on else {"applied": False, "not_applied": "the row rules are not applied"}
            if not oc_on:
                print(f"\n!!! ONE CATCHER NOT APPLIED: {oc_meta['not_applied']} -- the book is built without it\n", flush=True)
        rm_c, rm_meta = 0, None
        if a.mix_rb_mate_c:                                  # study 96: only with the applied ONECATCH, else LOUDLY off
            rm_c = a.mix_rb_mate_c if oc_on else 0
            rm_meta = {"applied": True} if rm_c else {"applied": False, "not_applied": "ONECATCH is not applied"}
            if not rm_c:
                print(f"\n!!! RB MATE NOT APPLIED: {rm_meta['not_applied']} -- the book is built without it\n", flush=True)
        rm_teams = None
        if rm_c and a.mix_rb_mate_scope != "all":           # study 97's scope: a refusal turns the RB mate OFF, never widens it
            rm_teams, why = rb_mate_scope_teams(a.mix_rb_mate_scope, fr, set(fr.id.astype(str)) - set(excl))
            if why is not None:
                rm_c, rm_teams = 0, None
                rm_meta = {"applied": False, "not_applied": f"scope {a.mix_rb_mate_scope} refused: {why}"}
                print(f"\n!!! RB MATE SCOPE NOT APPLIED: {why} -- the book is built without the RB mate\n", flush=True)
            else:
                rm_meta = {"applied": True, "scope": a.mix_rb_mate_scope, "qb_teams": sorted(rm_teams)}
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
                                                                       cell_quotas=cell_quotas, bring_back_top_wr=bb_cells,
                                                                       bring_back_top_wr_rows=bb_rows, own_cap=own_cap,
                                                                       row_bounds=row_bounds, one_catcher=oc_on, rb_mate_c=rm_c,
                                                                       rb_mate_qb_teams=rm_teams)
            if own_cap_meta is not None:
                mix_meta["own_cap_source"] = own_cap_meta
            if row_meta is not None:
                mix_meta["row_rules_source"] = row_meta
            if oc_meta is not None:
                mix_meta["one_catcher_source"] = oc_meta
            if oc_on:
                print(one_catcher_line(mix_meta.get("one_catcher")), flush=True)
            if rm_meta is not None:
                mix_meta["rb_mate_source"] = rm_meta
            if rm_c:
                print(rb_mate_line(mix_meta.get("rb_mate")), flush=True)
            if rb_rec_meta is not None:                      # study 116 (the format agreed with the lab reviewer 10-10)
                mix_meta["rb_rec_floor_source"] = {k: rb_rec_meta[k] for k in
                                                   ("applied", "path", "sha256", "season", "week", "threshold", "file_rows",
                                                    "not_applied") if k in rb_rec_meta}
                if rb_rec_meta.get("applied"):
                    mix_meta["rb_rec_floor"] = {k: rb_rec_meta[k] for k in
                                                ("threshold", "pool_rbs", "kept_no_prior", "dropped_ids", "dropped_dk_ids")}
            if bb_cells:
                print(bring_back_top_wr_line(mix_meta.get("bring_back_top_wr")), flush=True)
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
                                                                      cell_quotas=cell_quotas, bring_back_top_wr=bb_cells,
                                                                      bring_back_top_wr_rows=bb_rows, own_cap=own_cap,
                                                                      row_bounds=row_bounds, one_catcher=oc_on, rb_mate_c=rm_c,
                                                                       rb_mate_qb_teams=rm_teams)
                main_tags = [TAG_PREFIX + c for c in main_cells]; mix_meta["with_term"] = own_mix
                if oc_on:
                    print("(the ownership-term book) " + one_catcher_line(own_mix.get("one_catcher")), flush=True)
                if rm_c:
                    print("(the ownership-term book) " + rb_mate_line(own_mix.get("rb_mate")), flush=True)
                if bb_cells:
                    print("(the ownership-term book) " + bring_back_top_wr_line(own_mix.get("bring_back_top_wr")), flush=True)
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
            _bt, _bc, _bx, _bq = ms_bb_rule({"config": {"union": {"mix": {"mix": mix_meta}}}})   # study 71 (off: {}, (), set(), None)
            for ids, cell in spare_rows:
                v = list(validate_roster(ids, pos, _st, _so, _ss)) + list(_spare_v(ids, cell, pos, _st, _so, _sg, top_wr=_bt,
                                                                                  top_wr_cells=_bc if ms_rule_applies(ids, _bx, _bq) else ()))
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
        pmo_main = {"exposure_cap": xcap, "exposure_cap_share": cap_share_used, "rows_solved": len(main_rows), "secs": secs_pmo, "max_exposure_used": max(expo.values()),
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
    _bt, _bc, _bx, _bq = ms_bb_rule({"config": {"union": {"mix": {"mix": mix_meta}}}})       # study 71 (off: {}, (), set(), None)
    if a.main == "mix":
        contract["strategy_contract"] = "mix_cells_s18_v1 (house for untagged rows); floor49"
        _game = dict(zip(ids_, fr.game_id.astype(str)))
    for i in book + book_tail:
        v_dk = validate_roster(rosters[i], pos, _team, _opp, _sal)
        if v_dk:
            raise SystemExit(f"written roster fails DK contract: {v_dk}")
        if a.main == "mix" and cell_of_tag(tags[i]) is not None:
            v_cell = shape_violations(rosters[i], cell_of_tag(tags[i]), pos, _team, _opp, _game, top_wr=_bt,
                                      top_wr_cells=_bc if ms_rule_applies(rosters[i], _bx, _bq) else ())
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
