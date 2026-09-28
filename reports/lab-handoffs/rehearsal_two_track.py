#!/usr/bin/env python3
"""Week-4 dress rehearsal on an archived week (operator ask 2026-09-27; laptop task 3). Read-only; writes nothing.

Replays the Week-4 plan on the week's REAL entered pool with the real code:
  * the lab's two_track selectors (select_top_mean with the ownership tilt and the DST cap; select_tail_sleeve by
    P(total >= line) over the run dir's two persisted player-world banks, as the live build does);
  * production's enter_layout (head layout, per-contest track, mean rows in mean order = ENTER_ORDER=greedy);
  * Q4b approximated after the fact: candidates holding a skill player projected under MIN_PROJ are dropped (the live
    build drops those players before generation; the archived pool was built without it);
then places every contest's rows into that contest's REAL field (our own entries removed) and scores them on realized
points (contest_ownership fpts by display name, as the Monday scoreboard does).

Ticket line per contest: the contest's own field at quantile --line-q (default p90; DraftKings satellites pay about the
top 9-11%); an 11-entry single-ticket satellite pays only a strict first place. The Millionaire also reports min-cash
(--milly-cash) and the best row's finish. Tickets are therefore APPROXIMATE unless production supplies each contest's
paid count; every arm is scored the same way, so the comparison between arms is like for like.

  PYTHONPATH=<lab two-track checkout>/src:<this repo>/src python reports/lab-handoffs/rehearsal_two_track.py \
      --run-dir RUN_DIR --season 2026 --week 3 --sizes SIZES --tail milly20,ffwc,ffwc18 --sets OWNERSHIP_SETS \
      [--names-map sat13=sat13mega]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_arm_outcomes import parse_sizes  # noqa: E402


def load_pool(run: Path):
    fr = pd.read_parquet(run / "frame.parquet").reset_index(drop=True)
    c = pd.read_parquet(run / "candidates.parquet")
    row = {str(i): k for k, i in enumerate(fr.id.astype(str))}
    idx = np.array([[row[i] for i in p.split(",")] for p in c.players], dtype=np.int32)
    return fr, c, idx


def totals(bank: np.ndarray, idx: np.ndarray, chunk: int = 2000) -> np.ndarray:
    out = np.empty((len(idx), bank.shape[1]), dtype=np.float32)
    for s in range(0, len(idx), chunk):
        out[s:s + chunk] = bank[idx[s:s + chunk]].sum(axis=1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", type=Path, required=True); ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True); ap.add_argument("--sizes", required=True)
    ap.add_argument("--tail", default="milly20,ffwc,ffwc18", help="contest names on the tail track")
    ap.add_argument("--sets", type=Path, required=True, help="the week's ownership sets file (dk_player_id, pred_own)")
    ap.add_argument("--names-map", default="sat13=sat13mega", help="spec name=warehouse contest_name pairs")
    ap.add_argument("--tilt", type=float, default=0.1); ap.add_argument("--dst-cap", type=float, default=0.25)
    ap.add_argument("--min-proj", type=float, default=1.0); ap.add_argument("--tail-line", type=float, default=210.0)
    ap.add_argument("--line-q", type=float, default=90.0); ap.add_argument("--milly-cash", type=float, default=149.5)
    ap.add_argument("--details", type=Path, help="contest details JSON keyed by contest id (payoutSummary ladders): exact paid "
                                                  "places replace the p-quantile line")
    ap.add_argument("--show-value", action="store_true", help="also print payout value per arm (private: never commit it)")
    ap.add_argument("--tail-selector", choices=["pline", "emax", "class"], default="pline",
                    help="how the tail sleeve is chosen (live_week --tail-sleeve-selector)")
    ap.add_argument("--class-model", type=Path, help="with --tail-selector class: the fit_field_class_model.py JSON")
    ap.add_argument("--allow-unidentified", action="store_true",
                    help="proceed when our entries cannot be found in the fields (e.g. a week entered through a vetting path); "
                         "fields then include our own entries and the ENTERED line is skipped (disclosed)")
    ap.add_argument("--main-selector", choices=["mean", "class"], default="mean",
                    help="how the satellite (mean-track) rows are chosen: projected sum, or the class model's score")
    a = ap.parse_args()
    from nfl2.two_track import load_own_estimates, own_sums, select_tail_sleeve, select_top_mean
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    from nfl_dfs.inference.enter_layout import assign_ranks

    fr, c, idx = load_pool(a.run_dir)
    ids = fr.id.astype(str).to_numpy(); pos = fr.pos.astype(str).to_numpy()
    names = fr.display_name.astype(str).to_numpy()
    mp = pd.to_numeric(fr.mean_projection, errors="coerce").fillna(0.0).to_numpy(float)
    psum = mp[idx].sum(axis=1)
    rosters = [frozenset(r) for r in map(tuple, idx)]
    skill_low = (np.isin(pos, ["QB", "RB", "WR", "TE"]) & (mp < a.min_proj))
    playable = ~skill_low[idx].any(axis=1)
    dk = fr.dk_player_id.map(lambda v: str(int(v)) if pd.notna(v) else "").to_numpy()
    osum, cov = own_sums([[dk[j] for j in r] for r in idx], load_own_estimates(a.sets))
    dst_of = [str(next(j for j in r if pos[j] == "DST")) for r in idx]
    inc = np.load(a.run_dir / "incumbent_player_scores.npy"); hs = np.load(a.run_dir / "corrected_hsim_player_scores.npy")
    tot = np.concatenate([totals(inc, idx), totals(hs, idx)], axis=1); del inc, hs

    # contests, tracks, layout
    contests = parse_sizes(a.sizes)
    tail = set(a.tail.split(",")) if a.tail else set()
    for ct in contests:
        ct["track"] = "tail" if ct["name"] in tail else "mean"
    ranks = assign_ranks(contests, "head")
    t_rows = sum(int(ct["entries"]) for ct in contests if ct["track"] == "tail")
    need = max(max(r) + 1 for r in ranks if r)
    k_mean = need - t_rows

    # realized points and the real fields
    fp = query_df(f"SELECT display_name, MAX(fpts) f FROM `{settings.raw}.contest_ownership` WHERE season={a.season} "
                  f"AND week={a.week} GROUP BY 1")
    real = dict(zip(fp.display_name.astype(str), fp.f.astype(float)))
    act = np.array([real.get(n, 0.0) for n in names])[idx].sum(axis=1)
    ent = query_df(f"""SELECT contest_id, contest_name, entry_name, points, lineup_slots_json FROM `{settings.raw}.contest_entries`
                       WHERE season={a.season} AND week={a.week}
                       QUALIFY ROW_NUMBER() OVER (PARTITION BY contest_id, entry_id ORDER BY imported_at DESC) = 1""")
    ent["user"] = ent.entry_name.astype(str).str.extract(r"^([^ (]+)")[0]
    # our handle: the user whose lineups match the archived book most often (kept in memory only, never printed)
    book = pd.read_csv(a.run_dir / "book.csv", dtype=str)
    name_of = dict(zip(dk, names))
    book_sets = {frozenset(name_of.get(x, "") for x in r) for r in book.to_numpy().tolist()}
    ent["pset"] = ent.lineup_slots_json.map(lambda s: frozenset(i["player"] for i in json.loads(s)))
    ours = ent[ent.pset.isin(book_sets)].user.value_counts()
    if ours.empty or ours.iloc[0] < 50:
        if not a.allow_unidentified:
            raise SystemExit("could not identify our entries in the fields (fewer than 50 book matches)")
        print("NOTE: our entries were not identified; the fields include them and the ENTERED line is skipped")
        me = None
    else:
        me = ours.index[0]
    nmap = dict(p.split("=") for p in a.names_map.split(",") if p)
    by_label = {}
    for cid, g in ent.groupby("contest_id"):
        by_label.setdefault(str(g.contest_name.iloc[0]), []).append(cid)
    ladders = {}
    if a.details:
        det = json.loads(a.details.read_text())
        for cid, d in det.items():
            pay = {}
            for t in d.get("payoutSummary", []):
                v = sum(float(x.get("value", 0.0)) * (x.get("quantity") or 1) for x in t.get("payoutDescriptions", []))
                for r in range(int(t["minPosition"]), int(t["maxPosition"]) + 1):
                    pay[r] = v
            ladders[str(cid)] = pay
    used = Counter()
    fields = []
    for ct in contests:
        lab = nmap.get(ct["name"], ct["name"])
        cids = sorted(by_label.get(lab, []))
        if used[lab] >= len(cids):
            raise SystemExit(f"no warehouse contest left for {ct['name']} (label {lab})")
        cid = cids[used[lab]]; used[lab] += 1
        g = ent[ent.contest_id == cid]
        if a.details and str(cid) not in ladders:
            raise SystemExit(f"--details has no payout ladder for contest {cid}")
        fields.append({"cid": cid, "pay": ladders.get(str(cid)), "others": np.sort(g.loc[g.user != me, "points"].to_numpy(float)),
                       "ours": g.loc[g.user == me, "points"].to_numpy(float), "n": len(g)})

    sleeve_note = a.tail_selector
    class_scores = None
    if a.tail_selector == "class" or a.main_selector == "class":
        from nfl2.class_selector import load_model, pool_features, prelock_map, salary_legal_optimum, score
        cm, cm_sha = load_model(a.class_model); qs, pm = prelock_map(a.class_model)
        opt = salary_legal_optimum(fr)
        class_scores = score(cm, pool_features([list(r) for r in idx], fr, qs, opt))
        sleeve_note = f"class (model sha {cm_sha[:12]}, map weeks {pm['map_weeks']}, this frame's optimum {opt:.1f})"

    def sleeve_rows(cand: np.ndarray) -> list[int]:
        if not t_rows:
            return []
        if a.tail_selector == "emax":
            from nfl2.selectors import select_expected_max
            return [int(cand[j]) for j in select_expected_max(tot[cand], t_rows)]
        if a.tail_selector == "class":
            return [int(cand[j]) for j in select_top_mean(class_scores[cand], [rosters[i] for i in cand], t_rows, max_shared=7)]
        return [int(cand[j]) for j in select_tail_sleeve(tot[cand], t_rows, a.tail_line, [rosters[i] for i in cand])]

    def arm_rows(tilt: float, dst_cap: float | None, mean_only_dual: bool = False) -> list[int]:
        cand = np.flatnonzero(playable)
        score = (class_scores[cand] if a.main_selector == "class" else psum[cand]) + tilt * osum[cand]
        kw = {}
        if dst_cap:
            kw = {"dst_of": [dst_of[i] for i in cand], "dst_cap": max(1, math.floor(dst_cap * k_mean))}
        mean_rows = [int(cand[j]) for j in select_top_mean(score, [rosters[i] for i in cand], k_mean, max_shared=7, **kw)]
        return mean_rows + sleeve_rows(cand)

    def paid(p: np.ndarray, f: dict) -> tuple[int, float]:
        """Exact: rank each of our rows among the other entrants and our own rows (1 + strictly higher scores)."""
        allp = np.concatenate([f["others"], p])
        rk = np.array([1 + int((allp > x).sum()) for x in p])
        vals = np.array([f["pay"].get(int(r), 0.0) for r in rk])
        return int((vals > 0).sum()), float(vals.sum())

    def score_arm(rows: list[int]) -> dict:
        pts = act[rows]
        out = {"tickets": 0, "value": 0.0, "by_type": Counter(), "milly_best": None}
        for ct, rk, f in zip(contests, ranks, fields):
            p = pts[rk]
            if f["pay"] is not None:
                won, val = paid(p, f); out["value"] += val
            elif f["n"] <= 12:                                  # single-ticket small satellite: strict first place
                won = int((p > f["others"].max()).sum() > 0) if len(f["others"]) else 0
            else:
                line = float(np.percentile(np.concatenate([f["others"], p]), a.line_q))
                won = int((p >= line).sum())
            if ct["name"] == "milly20":
                out["milly_best"] = round(float(p.max()), 2)
                out["milly_cash"] = int((p >= a.milly_cash).sum())
                out["milly_best_finish"] = int((f["others"] > p.max()).sum()) + 1
            out["tickets"] += won; out["by_type"][ct["name"]] += won
        out["mean_pts"] = round(float(np.mean(np.concatenate([pts[rk] for rk in ranks]))), 2)
        out["by_type"] = dict(out["by_type"])
        return out

    entered = {"tickets": 0, "value": 0.0, "by_type": Counter()}
    for ct, f in zip(contests, fields if me is not None else []):
        p = f["ours"]
        if f["pay"] is not None:
            won, val = paid(p, f); entered["value"] += val
        elif f["n"] <= 12:
            won = int(len(p) and (p.max() > f["others"].max()))
        else:
            won = int((p >= np.percentile(np.concatenate([f["others"], p]), a.line_q)).sum())
        entered["tickets"] += won; entered["by_type"][ct["name"]] += won
    entered["mean_pts"] = round(float(np.concatenate([f["ours"] for f in fields]).mean()), 2) if me is not None else float("nan")
    entered["by_type"] = dict(entered["by_type"])

    print(f"pool {len(c)} candidates ({int((~playable).sum())} hold a skill player projected < {a.min_proj}); ownership "
          f"slot coverage {cov:.3f}; layout: {len(contests)} contests, {need} rows = {k_mean} mean + {t_rows} sleeve "
          f"(tail: {sorted(tail)}, sleeve by {sleeve_note}; main rows by {a.main_selector}); " + ("EXACT payout ladders" if a.details else f"line = field p{a.line_q:g} (11-entry satellites: strict first place)"))
    arms = {"ENTERED (as played)": entered,
            "PLAN (mean + tilt + DST cap + sleeve)": score_arm(arm_rows(a.tilt, a.dst_cap)),
            "PLAN without tilt": score_arm(arm_rows(0.0, a.dst_cap)),
            "plain mean (no tilt, no DST cap) + sleeve": score_arm(arm_rows(0.0, None))}
    for k, v in arms.items():
        print(f"\n{k}: paid entries {v['tickets']}; mean points per entry {v['mean_pts']}"
              + (f"; payout value {v['value']:.2f}" if a.show_value else "")
              + (f"; Millionaire best {v['milly_best']} (finish {v['milly_best_finish']}), rows >= min-cash {v['milly_cash']}"
                 if v.get("milly_best") is not None else ""))
        print("  by contest type: " + ", ".join(f"{n} {t}" for n, t in sorted(v["by_type"].items())))
    if t_rows:
        cand = np.flatnonzero(playable); srow = sleeve_rows(cand)
        print(f"\nsleeve rows ({a.tail_selector}): realized {[round(float(act[i]), 1) for i in srow]}")


if __name__ == "__main__":
    main()
