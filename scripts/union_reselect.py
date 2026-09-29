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

The run dir carries the T-70 run's frame, sidecar banks, universe and exposure ledgers unchanged; a union corpus
(`candidates.parquet` with `source_run` = t70 | saturday | pmo); `book.csv` / `book.json`; and a receipt copied from the
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


def pmo_rows(t70: pd.DataFrame, exclude: set[str], n: int, max_shared: int, cap: int | None, min_salary: int,
             existing: set[frozenset], exposure_cap: int | None = None, dst_cap: int | None = None) -> list[list[str]]:
    """Plain-mean-optimizer rows on the T-70 frame (L13's R5 form), skipping rosters already in the pool. With
    exposure_cap (L13's PMO_X50: max(1, N // 2)), a player already in that many PMO rows is banned from later solves --
    the form L13 SUPPORTED at p89 (+27.7% tickets vs MEAN, both seasons); the uncapped form was NOT SUPPORTED."""
    from nfl2.core.lineup import optimize                      # the pinned lab clone on PYTHONPATH
    from nfl2.pipeline import PRODUCTION_STACK
    pool = [p for i, p in frame_players(t70).items() if i not in exclude]
    dst_ids = {p["id"] for p in pool if p["pos"] == "DST"}
    env = {"MIN_LINEUP_SALARY": str(min_salary)}
    if cap is not None:
        env["MAX_PER_GAME"] = str(cap)
    prev: list[frozenset] = [frozenset(r) for r in existing]
    rows: list[list[str]] = []
    count: Counter = Counter()
    tries = 0
    while len(rows) < n and tries < 3 * n:
        tries += 1
        bans = {p for p, c in count.items() if exposure_cap is not None and c >= exposure_cap}
        if dst_cap is not None:
            bans |= {p for p, c in count.items() if p in dst_ids and c >= dst_cap}
        bans = bans or None
        lu = optimize(pool, stack=PRODUCTION_STACK, objective_col="proj", banned_lineups=prev, max_overlap=max_shared, bans=bans, env=env)
        if lu is None:
            break
        ids = [str(p["id"]) for p in lu.players]
        prev.append(frozenset(ids))
        if frozenset(ids) in existing:
            continue
        rows.append(ids); existing.add(frozenset(ids)); count.update(ids)
    if len(rows) < n:
        print(f"PMO: {len(rows)} of {n} rows solved (the frame ran out of distinct legal rows under the caps)", file=sys.stderr)
    return rows


class _LU:                                                   # what dk_csv / validate need from a lineup
    def __init__(self, players: list[dict], tag: str):
        self.players, self.tag = players, tag

    @property
    def salary(self) -> int:
        return int(sum(p["salary"] for p in self.players))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--saturday-run", required=True, help="a run dir, or 'auto' (newest --saturday-dose run in --live-dir built before the T-70 run)")
    ap.add_argument("--saturday-dose", default="2560/10240")
    ap.add_argument("--group", help="with --saturday-run auto: this week's draft group (a run dir for another group is never the supply)")
    ap.add_argument("--saturday-after", help="with --saturday-run auto: ISO UTC window start (a smoke or an old build built before it is never the supply)")
    ap.add_argument("--t70-run", type=Path, required=True)
    ap.add_argument("--live-dir", type=Path, required=True, help="the live results tree the union dir is created in (results/live/<season>-w<WW>)")
    ap.add_argument("--entries", type=int, required=True); ap.add_argument("--tail-sleeve", type=int, default=0)
    ap.add_argument("--mean-max-shared", type=int, default=7); ap.add_argument("--mean-dst-cap", type=float, default=0.25)
    ap.add_argument("--min-proj", type=float, default=1.0); ap.add_argument("--max-per-game", type=int, default=4)
    ap.add_argument("--min-salary", type=int, default=49_000); ap.add_argument("--pmo", type=int, default=0)
    ap.add_argument("--pmo-cap-share", type=float, default=0.5, help="PMO per-player exposure cap as a share of --pmo rows (L13's PMO_X50 = 0.5; 0 = uncapped, NOT supported by L13)")
    ap.add_argument("--main-dst-cap", type=float, default=None,
                    help="with --main pmo_x50: a DST in >= floor(share*K) rows is banned from later solves (operator's open question; "
                         "the tested arm had none -- Week 3 put two busting DSTs in 25 and 22 of 58 rows). Default none.")
    ap.add_argument("--sleeve-includes-main", action="store_true",
                    help="with --main pmo_x50: let the tail sleeve also pick from the optimizer's rows (they project highest, so they would take "
                         "most of it). Default off: the sleeve is the union pool's mean selection, the form rehearsed at 23/40 paid.")
    ap.add_argument("--main", choices=["mean", "pmo_x50"], default="mean",
                    help="the main book: mean = the union pool's top-K by projected sum (paper arm); pmo_x50 = K capped plain-mean-optimizer rows solved on the T-70 frame (ENTERS Week 4)")
    ap.add_argument("--dk-status", type=Path); ap.add_argument("--tail-line", type=float, default=None)
    ap.add_argument("--out", type=Path, help="explicit output dir (default: <live-dir>/<utc stamp>-union-<t70 sha7>)")
    ap.add_argument("--rehearsal", action="store_true", help="paper: accept a T-70 run built with another selector (Week 3 was dual_emax); "
                                                            "the receipt records rehearsal=true; never point --out into the live tree")
    a = ap.parse_args(argv)
    if a.rehearsal and (a.out is None or a.live_dir in a.out.resolve().parents):
        raise SystemExit("--rehearsal needs --out outside --live-dir")
    from nfl2.two_track import select_top_mean, tail_probability   # the pinned lab clone on PYTHONPATH
    from nfl2.live import dk_csv
    from nfl2.validator import validate_roster

    t70 = load_run(a.t70_run)
    cfg = t70["receipt"].get("config", {})
    if cfg.get("selector") != "mean" and not a.rehearsal:
        raise SystemExit(f"the union is defined for the mean selector; the T-70 receipt says {cfg.get('selector')!r}")
    if a.saturday_run == "auto":
        lev, boom = (int(x) for x in a.saturday_dose.split("/"))
        sat_dir = pick_saturday_run(a.live_dir, lev, boom, str(t70["receipt"].get("built_utc", "")), group=a.group, after=a.saturday_after)
    if str(t70["receipt"].get("config", {}).get("lev")) + "/" + str(t70["receipt"].get("config", {}).get("boom")) == a.saturday_dose:
        raise SystemExit(f"the T-70 run {a.t70_run.name} IS a {a.saturday_dose} build (the Saturday supply itself); no union for it")
    else:
        sat_dir = Path(a.saturday_run)
    sat = load_run(sat_dir)
    if parse_utc(sat["receipt"].get("built_utc", "")) >= parse_utc(t70["receipt"].get("built_utc", "")):
        raise SystemExit(f"the Saturday run {sat_dir.name} was built at or after the T-70 run {a.t70_run.name}")
    fr = t70["frame"]
    inc, hs = (np.load(a.t70_run / b) for b in BANKS)
    if inc.shape[0] != len(fr) or hs.shape[0] != len(fr):
        raise SystemExit("T-70 banks do not match the T-70 frame's rows")
    dk = pd.read_csv(a.dk_status, dtype=str) if a.dk_status else None
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
    if a.main == "pmo_x50" and a.pmo > 0:
        raise SystemExit("--pmo (extra pool rows) is for --main mean; --main pmo_x50 solves the main book itself")
    if a.pmo > 0:
        gone = unavailable_ids(fr, dk)
        proj_all = dict(zip(fr.id.astype(str), pd.to_numeric(fr.mean_projection, errors="coerce")))
        pos_all = dict(zip(fr.id.astype(str), fr.pos.astype(str)))
        excl = gone | {i for i in proj_all if pos_all[i] in SKILL and not (proj_all[i] >= a.min_proj)}
        existing = t70_set | {frozenset(r) for r in sat_rosters}
        xcap = max(1, int(a.pmo_cap_share * a.pmo)) if a.pmo_cap_share > 0 else None
        pm = pmo_rows(fr, excl, a.pmo, a.mean_max_shared, cap, a.min_salary, existing, exposure_cap=xcap)
        rosters += pm; source += ["pmo"] * len(pm); tags += ["pmo"] * len(pm); sat_cand += [None] * len(pm); n_pmo = len(pm)
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
    if a.main == "pmo_x50":
        import time as _time
        gone = unavailable_ids(fr, dk)
        proj_all = dict(zip(fr.id.astype(str), pd.to_numeric(fr.mean_projection, errors="coerce")))
        pos_all = dict(zip(fr.id.astype(str), fr.pos.astype(str)))
        excl = gone | {i for i in proj_all if pos_all[i] in SKILL and not (proj_all[i] >= a.min_proj)}
        xcap = max(1, int(0.5 * a.entries))
        t_pmo = _time.time()
        dcap = max(1, int(a.main_dst_cap * a.entries)) if a.main_dst_cap else None
        main_rows = pmo_rows(fr, excl, a.entries, a.mean_max_shared, cap, a.min_salary, set(), exposure_cap=xcap, dst_cap=dcap)
        secs_pmo = round(_time.time() - t_pmo, 1)
        if len(main_rows) < a.entries:
            raise SystemExit(f"PMO_X50 MAIN REFUSED: {len(main_rows)} of {a.entries} rows solved on the T-70 frame under the caps "
                             f"(exposure cap {xcap}, overlap {a.mean_max_shared}, per-game {cap}, salary floor {a.min_salary}); the union's mean main stands")
        # the PMO rows join the corpus (source pmo_x50) and ARE the main book, in solve order; a PMO row that duplicates a pool
        # roster is still the PMO row (the corpus keeps both; the book is unique by construction)
        base = len(rosters)
        rosters += main_rows; source += ["pmo_x50"] * len(main_rows); tags += ["pmo_x50"] * len(main_rows); sat_cand += [None] * len(main_rows)
        frozen = [frozenset(r) for r in rosters]; score = projected_sum(rosters, proj)
        book = list(range(base, base + a.entries))
        sleeve_score = score if a.sleeve_includes_main else np.where(np.arange(len(rosters)) < base, score, -np.inf)
        expo = Counter(p for i in book for p in rosters[i])
        dst_expo = Counter(p for i in book for p in rosters[i] if pos[p] == "DST")
        pmo_main = {"exposure_cap": xcap, "rows_solved": len(main_rows), "secs": secs_pmo, "max_exposure_used": max(expo.values()),
                    "sleeve_includes_main": bool(a.sleeve_includes_main),
                    "distinct_players": len(expo), "dst_cap": dcap if dcap else "none (the tested arm had none)",
                    "max_dst_rows_used": max(dst_expo.values()), "dst_rows": dict(dst_expo.most_common(3))}
        dst_args = {}
    else:
        book = select_top_mean(score, frozen, a.entries, max_shared=a.mean_max_shared, **dst_args)
        sleeve_score = score
    book_tail = select_top_mean(np.where(np.isfinite(sleeve_score), sleeve_score, -1e9), frozen, a.tail_sleeve, max_shared=a.mean_max_shared) if a.tail_sleeve else []
    if len(book) != a.entries or len(set(book)) != a.entries or (a.tail_sleeve and len(book_tail) != a.tail_sleeve):
        raise SystemExit("the selector did not return the requested rows")

    # contract revalidation of every written roster (as live_week.py)
    ids_ = fr.id.astype(str).tolist()
    _team = dict(zip(ids_, fr.team.astype(str))); _opp = dict(zip(ids_, fr.opp.astype(str)))
    _sal = dict(zip(ids_, pd.to_numeric(fr.salary, errors="coerce").fillna(0).astype(int)))
    contract = {"dk_contract": "dk_classic_v1", "strategy_contract": "house_qb2_bb1_floor49_v1", "dk_violations": 0, "strategy_violations": 0}
    for i in book + book_tail:
        v_dk = validate_roster(rosters[i], pos, _team, _opp, _sal)
        if v_dk:
            raise SystemExit(f"written roster fails DK contract: {v_dk}")
        if validate_roster(rosters[i], pos, _team, _opp, _sal, salary_floor=a.min_salary, qb_stack_min=2, bring_back_min=1,
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
    players_by_id = frame_players(fr)
    lus = [_LU([players_by_id[i] for i in rosters[k]], tags[k]) for k in range(len(rosters))]
    n_written = dk_csv([lus[i] for i in book + book_tail], fr, out / "book.csv")
    if n_written != need:
        raise SystemExit(f"dk_csv wrote {n_written} rows for a {a.entries}+{a.tail_sleeve} book")
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
                                 + [f for f in ("book_wemax.csv", "book_wemax.json", *BANKS) if (out / f).is_file()]})
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
                     "selection": ("union_reselect.py --main pmo_x50: K capped plain-mean-optimizer rows on the T-70 frame in solve order (L13 PMO_X50); "
                                   if a.main == "pmo_x50" else
                                   "union_reselect.py --main mean: top-K by sum of the T-70 mean_projection under the overlap cap and the DST cap; ")
                                  + "the tail sleeve top-T of the union pool by the same score (may repeat main rows)",
                     "min_proj": a.min_proj, "max_per_game": cap, "tool": {"path": str(tool), "sha256": sha256_file(tool), "production_sha": prod_sha}}
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
    if pmo_main:
        conf["union"]["pmo_x50"] = pmo_main
    conf["main_selector_used"] = a.main
    if a.tail_sleeve:
        conf["tail_sleeve"] = {"rows": a.tail_sleeve, "line": tail_line, "selector": "mean", "selector_used": "mean", "class": {},
                               "worlds": "incumbent selection + corrected hsim", "book_rows": f"{a.entries + 1}..{a.entries + a.tail_sleeve}",
                               "repeats_of_main_rows": len(set(book_tail) & set(book)),
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
