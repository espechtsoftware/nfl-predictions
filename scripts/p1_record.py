#!/usr/bin/env python3
"""P1's weekly record (the frozen prereg reports/2026-10-07-prereg-p1-contest-edge.md with amendment 1), after settlement.

Per contest class, our ENTERED rows' latent finish score in the SAME week's Millionaire field,
    z = Phi^-1(1 - p),  p = (position - 0.5) / N,
    position = 1 + the Millionaire field's entries (every real entry of ours removed) strictly above the row's points,
    N = that field's size,
against the class's FROZEN break-even z. The unit is the week (equal weights): per class the week's mean z over its
entered rows -- its UNIQUE lineups, the 10-05 method's dedup (it reproduces the 10-05 week means on W1-4); the edge = the mean over PROSPECTIVE weeks (W5 on) of (week mean - break-even z); from W8, with at least 4
prospective weeks, the one-sided 95% t lower bound on those week values ("stake supported" only while it is > 0; the flag
is advice). W1-4 are printed apart as the baseline, never pooled. Beside it, descriptive: each row's own-contest finish
percentile, and the money secondary -- realized tie-split multiples (nfl_raw.v_dk_entry_tier.split_payout_multiple for
our entry ids) and the hit rate against the flat ladders' break-even rate (1 / the pool ratio x the field's paid share).
The 10-05 clustered-model interval is added beside the bound from W8. Behind moneygate_score's reconcile gate.
Counts, rates, z and multiples only (no dollars).

    python scripts/p1_record.py --weeks 1,2,3,4,5 [--out <json>]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import norm, t as student_t

HERE = Path(__file__).resolve().parent
# the frozen break-even z per class (the prereg's §4 table; 10-05 latent model, W5-plan entry-weighted)
BREAK_EVEN = {"flat ticket <= 600": 0.158, "flat ticket > 600": 0.175, "Millionaire": 0.216,
              "large cash GPP": 0.199, "qualifier": 0.207}
PROSPECTIVE_FROM, BOUND_FROM_WEEK, MIN_WEEKS = 5, 8, 4


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod)
    return mod


def contest_kind(details: dict) -> tuple[str, bool, int]:
    """(kind, flat, capacity): kind ticket / cash / mixed from the tiers' prize kinds; flat = every paid position equal."""
    tiers = details.get("payoutSummary") or []
    kinds = {k for t in tiers for k in (t.get("tierPayoutDescriptions") or {})}
    kind = "ticket" if kinds == {"Ticket"} else "cash" if kinds == {"Cash"} else "mixed"
    vals = {round(sum(float(d.get("value") or 0) for d in t.get("payoutDescriptions") or []), 6) for t in tiers}
    cap = int(details.get("maximumEntries") or details.get("max") or 0)
    return kind, len(vals) == 1, cap


def p1_class(name: str, details: dict) -> str:
    kind, flat, cap = contest_kind(details)
    if "Millionaire [$1M" in str(name) and kind == "cash":
        return "Millionaire"
    if kind == "ticket" and flat:
        return "flat ticket <= 600" if cap <= 600 else "flat ticket > 600"
    if kind == "cash" and cap >= 10_000:
        return "large cash GPP"
    if kind == "mixed":
        return "qualifier"
    return "everything else"


def latent_z(points: np.ndarray, milly_others_sorted: np.ndarray) -> np.ndarray:
    """z = Phi^-1(1 - p), p = (position - 0.5) / N, position = 1 + the field's entries strictly above."""
    o = np.asarray(milly_others_sorted, np.int64); n = len(o) + 1            # the field with the row placed in it
    above = len(o) - np.searchsorted(o, np.asarray(points, np.int64), side="right")
    p = (above + 1 - 0.5) / n
    return norm.ppf(1 - p)


def t_lower_bound(values: list[float]) -> float | None:
    n = len(values)
    if n < 2:
        return None
    v = np.asarray(values, float)
    return float(v.mean() - student_t.ppf(0.95, n - 1) * v.std(ddof=1) / math.sqrt(n))


def week_rows(M, W) -> list[dict]:
    """Our entered rows of week W: contest, class, latent z in the Millionaire field, own-contest percentile."""
    milly = M.milly_cid(W)
    if milly is None:
        raise SystemExit(f"W{W.week}: no Millionaire among the week's contests")
    others_m = W.others_sorted(milly)
    ours = W.field[W.field.entry_id.isin(W.ours)]
    rows = []
    for cid, g in ours.groupby("contest_id"):
        det = W.details.get(str(cid))
        if det is None:
            continue                                   # a contest with no ladder (recorded by the caller)
        cls = p1_class(det.get("name", ""), det)
        pts = g.points.to_numpy(np.int64)
        z = latent_z(pts, others_m)
        own = W.others_sorted(str(cid))
        pct = 100.0 * np.searchsorted(own, pts, side="left") / max(len(own), 1)
        rows += [{"contest_id": str(cid), "entry_id": e, "class": cls, "z": float(zz), "own_pct": float(pp),
                  "lineup": frozenset(nm)} for e, zz, pp, nm in zip(g.entry_id, z, pct, g.names)]
    return rows


def class_rows(rows: list[dict]) -> dict[str, list[dict]]:
    """Per class, its UNIQUE entered lineups (the 10-05 method: a lineup entered several times counts once per class;
    it reproduces the 10-05 week means +0.10 / -0.41 / -0.34 / +0.01 on W1-4). Money stays per entry."""
    by: dict[str, dict] = {}
    for r in rows:
        by.setdefault(r["class"], {}).setdefault(r["lineup"], r)
    return {c: list(d.values()) for c, d in by.items()}


def money_lines(M, W, rows: list[dict], split: dict[str, float]) -> dict[str, dict]:
    """Per class (descriptive): entries, hits (a payout > 0), the realized tie-split multiple (the mean of
    v_dk_entry_tier.split_payout_multiple over the class's entries) and, for the flat ladders, the hit rate against the
    break-even rate (1 / the pool ratio x the field's paid share)."""
    out: dict[str, dict] = {}
    for r in rows:
        o = out.setdefault(r["class"], {"entries": 0, "hits": 0, "split_sum": 0.0, "be_rate": [], "field_rate": []})
        m = split.get(r["entry_id"])
        o["entries"] += 1; o["hits"] += int(bool(m and m > 0)); o["split_sum"] += float(m or 0.0)
        det = W.details[r["contest_id"]]; lad = M.Ladder.from_details(det)
        cap = int(det.get("maximumEntries") or det.get("max") or 0)
        pool = float((lad.cash + lad.ticket).sum()); fee = float(det.get("entryFee") or det.get("fee"))
        if cap and pool > 0 and len(set(np.round(lad.cash + lad.ticket, 6))) == 1:
            o["be_rate"].append((fee * cap / pool) * (lad.paid / cap)); o["field_rate"].append(lad.paid / cap)
    for c, o in out.items():
        o["realized_multiple"] = round(o.pop("split_sum") / o["entries"], 4) if o["entries"] else None
        o["hit_rate"] = round(o["hits"] / o["entries"], 4) if o["entries"] else None
        be, fr = o.pop("be_rate"), o.pop("field_rate")
        o["break_even_rate"] = round(float(np.mean(be)), 4) if be else None
        o["field_paid_rate"] = round(float(np.mean(fr)), 4) if fr else None
    return out


def split_multiples(w: int, entry_ids: list[str]) -> dict[str, float]:
    """Our entries' tie-split payout multiples from nfl_raw.v_dk_entry_tier (the prereg's money source)."""
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    if not entry_ids:
        return {}
    d = query_df(f"SELECT entry_id, split_payout_multiple FROM `{settings.raw}.v_dk_entry_tier` "
                 "WHERE season = 2026 AND week = @w AND entry_id IN UNNEST(@ids)", {"w": int(w), "ids": [str(x) for x in entry_ids]})
    return {str(e): (float(m) if m == m else None) for e, m in zip(d.entry_id, d.split_payout_multiple)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--weeks", required=True); ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    weeks = [int(x) for x in a.weeks.split(",")]
    M = _load("moneygate_score")
    rec = json.loads(M.receipt_path().read_text()) if M.receipt_path().is_file() else {}
    miss = [w for w in weeks if w not in rec.get("weeks", [])]
    if miss:
        raise SystemExit(f"P1 RECORD REFUSED: the reconcile receipt does not cover weeks {miss}")
    M.require_reconcile(sorted(rec["weeks"]))
    cfg = M.load_config()
    per_week: dict[int, dict] = {}
    for w in weeks:
        W = M.load_week(cfg, w)
        rows = week_rows(M, W)
        by = class_rows(rows)
        money = money_lines(M, W, rows, split_multiples(w, [r["entry_id"] for r in rows]))
        per_week[w] = {c: {"rows": len(v), "mean_z": float(np.mean([r["z"] for r in v])),
                           "own_pct": float(np.mean([r["own_pct"] for r in v])), "money": money.get(c)} for c, v in by.items()}
        print(f"  W{w}: " + "; ".join(f"{c} {d['rows']} rows, mean z {d['mean_z']:+.3f}, own-contest pct {d['own_pct']:.0f}, "
                                     f"realized x{(d['money'] or {}).get('realized_multiple')} (hits {(d['money'] or {}).get('hits')}"
                                     + (f", break-even rate {d['money']['break_even_rate']} vs field {d['money']['field_paid_rate']}, ours {d['money']['hit_rate']}" if d.get('money') and d['money'].get('break_even_rate') else "")
                                     + ")" for c, d in sorted(per_week[w].items())))
    out = {"weeks": weeks, "break_even": BREAK_EVEN, "per_week": per_week, "classes": {}}
    print(f"P1 RECORD (frozen prereg + amendment 1): weeks {weeks}; prospective from W{PROSPECTIVE_FROM}; bound from W{BOUND_FROM_WEEK} with >= {MIN_WEEKS} weeks")
    for cls, zbe in BREAK_EVEN.items():
        base = {w: per_week[w][cls]["mean_z"] for w in weeks if w < PROSPECTIVE_FROM and cls in per_week[w]}
        pro = {w: per_week[w][cls]["mean_z"] - zbe for w in weeks if w >= PROSPECTIVE_FROM and cls in per_week[w]}
        lb = t_lower_bound(list(pro.values())) if (max(weeks) >= BOUND_FROM_WEEK and len(pro) >= MIN_WEEKS) else None
        flag = None if lb is None else ("stake supported" if lb > 0 else "no evidence for stake")
        out["classes"][cls] = {"break_even_z": zbe, "baseline_week_mean_z": base, "prospective_week_edge": pro,
                               "edge": float(np.mean(list(pro.values()))) if pro else None, "t_lower_bound": lb, "flag": flag}
        if base or pro:
            b = ", ".join(f"W{w} {v:+.3f}" for w, v in base.items())
            p = ", ".join(f"W{w} {v:+.3f}" for w, v in pro.items())
            print(f"  {cls:20s} break-even z {zbe:.3f} | baseline week mean z: {b or '-'} | prospective (week mean - break-even): {p or '-'}"
                  f" | edge {'-' if not pro else format(np.mean(list(pro.values())), '+.3f')} | bound {'-' if lb is None else format(lb, '+.3f')}"
                  f" | {flag or ('no flag: needs W' + str(BOUND_FROM_WEEK) + ' and >= ' + str(MIN_WEEKS) + ' prospective weeks')}")
    if a.out:
        a.out.write_text(json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
