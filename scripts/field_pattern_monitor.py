#!/usr/bin/env python3
"""Weekly real-field pattern monitor (the outside reviewer, 10-07; descriptive monitoring, no rule).

Every week with a real Millionaire field adds one independent outcome. For each week in ~/moneygate/weeks.json with a
T-70 run (or --weeks), on the week's largest contest:

1. The sub-$4,000 pattern: the Mantel-Haenszel odds ratio of a top-1% finish WITHIN each user-week (users with 20+
   entries), for lineups with 2+ sub-$4k non-DST players vs 0-1, and 1+ vs none; 95% interval by bootstrap over
   user-weeks. W1-4 (10-07): 2+ vs 0-1 OR 1.88 [1.74, 2.01], by week 1.69 / 2.46 / 2.30 / 2.10.
2. Game coverage: the share of lineups whose QB comes from the game with the k-th highest total (field, its top 1%,
   and our T-70 book), beside the 2014-2025 base rate of that game holding the slate's best stack (QB + 2 teammates +
   1 opponent) -- the top-4 games together 0.55.

User names are fingerprinted server-side (FARM_FINGERPRINT) and never downloaded. Output: aggregates only.
Usage: python field_pattern_monitor.py [--weeks 5,6] [--out CSV] [--min-entries 20]
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

# 2014-2025 Sunday main slates (207, 13:00-16:30 ET kickoffs, >= 6 games): P(the game with the k-th highest closing
# total holds the slate's best QB + 2 + 1 stack); k = 7 is the per-game rate of the 7th and lower.
HIST_P_BEST_STACK = {1: 0.217, 2: 0.140, 3: 0.106, 4: 0.087, 5: 0.068, 6: 0.097, 7: 0.053}
CHEAP_MAX_SALARY = 4000


def game_total_ranks(frame: pd.DataFrame) -> dict:
    """Games ranked by total, highest = 1; ties broken by game_id order (groupby sorts by it), the convention the
    2014-2025 base rates used. Tied totals are common (e.g. two games at 47.5), so the tie rule moves games between ranks."""
    gt = frame.groupby("game_id").game_total.max().astype(float)
    return gt.rank(ascending=False, method="first").astype(int).to_dict()


def mh_odds_ratio(cells: pd.DataFrame, exposed) -> tuple[float, pd.Series, pd.Series]:
    """Mantel-Haenszel odds ratio from per-stratum cells.

    cells: columns week, u (the stratum is week x u), k, n (lineups), t (top-1% lineups). exposed: k -> bool.
    Returns (OR, numerator terms, denominator terms) per stratum; strata with one exposure level only add zero."""
    s = cells.assign(E=exposed(cells.k)).groupby(["week", "u", "E"])[["n", "t"]].sum().unstack("E", fill_value=0)
    for col in (("n", True), ("t", True), ("n", False), ("t", False)):
        if col not in s.columns:
            s[col] = 0
    a = s[("t", True)]; b = s[("n", True)] - a; c = s[("t", False)]; d = s[("n", False)] - c; n = a + b + c + d
    num = (a * d / n).where(n > 0, 0.0); den = (b * c / n).where(n > 0, 0.0)
    return (float(num.sum() / den.sum()) if den.sum() > 0 else float("nan")), num, den


def bootstrap_ci(num: pd.Series, den: pd.Series, reps: int = 1000, seed: int = 5) -> tuple[float, float]:
    rng = np.random.default_rng(seed); nv, dv = num.values, den.values
    bs = [nv[i].sum() / dv[i].sum() for i in (rng.integers(0, len(nv), len(nv)) for _ in range(reps)) if dv[i].sum() > 0]
    return float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def main() -> None:
    from google.cloud import bigquery
    ap = argparse.ArgumentParser(); ap.add_argument("--weeks", default=None); ap.add_argument("--out", default=None)
    ap.add_argument("--min-entries", type=int, default=20); ap.add_argument("--season", type=int, default=2026)
    a = ap.parse_args()
    cfg = json.loads((Path.home() / "moneygate/weeks.json").read_text())
    weeks = [int(x) for x in a.weeks.split(",")] if a.weeks else sorted(int(k) for k, v in cfg["weeks"].items() if v.get("t70_run"))
    bq = bigquery.Client(); U, F, G, rows = [], [], [], []
    for w in weeks:
        t70 = Path(cfg["weeks"][str(w)]["t70_run"]); fr = pd.read_parquet(t70 / "frame.parquet")
        fn = fr.drop_duplicates("display_name")
        cid = bq.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = {a.season} AND week = {w} GROUP BY 1 "
                       "ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe()
        if cid.empty:
            print(f"W{w}: no real field loaded yet -- skipped", flush=True); continue
        cid = cid.contest_id.iloc[0]
        kmap = game_total_ranks(fr)
        qrank = [int(kmap.get(g, 0)) if p == "QB" else 0 for g, p in zip(fn.game_id, fn.pos)]
        base = """WITH m AS (SELECT n, s, p, q FROM UNNEST(@names) n WITH OFFSET i JOIN UNNEST(@sal) s WITH OFFSET j ON i = j
                    JOIN UNNEST(@pos) p WITH OFFSET k ON i = k JOIN UNNEST(@qrank) q WITH OFFSET l ON i = l),
          e AS (SELECT DISTINCT entry_id, rank, expected_entries ne, FARM_FINGERPRINT(TRIM(SPLIT(entry_name, ' (')[OFFSET(0)])) u, players_key
                FROM `nfl_raw.contest_entries` WHERE contest_id = @c AND season = @season AND week = @w),
          x AS (SELECT e.u, e.entry_id, ANY_VALUE(e.rank) <= 0.01 * ANY_VALUE(e.ne) top1, LEAST(COUNTIF(m.s < @cheap AND m.p != 'DST'), 3) k,
                       MAX(IF(m.p = 'QB', m.q, NULL)) qk FROM e, UNNEST(SPLIT(e.players_key, '|')) nm LEFT JOIN m ON m.n = nm GROUP BY e.u, e.entry_id)"""
        jc = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("c", "STRING", cid), bigquery.ScalarQueryParameter("w", "INT64", w),
            bigquery.ScalarQueryParameter("season", "INT64", a.season), bigquery.ScalarQueryParameter("cheap", "INT64", CHEAP_MAX_SALARY),
            bigquery.ArrayQueryParameter("names", "STRING", fn.display_name.astype(str).tolist()),
            bigquery.ArrayQueryParameter("sal", "INT64", [int(x) for x in fn.salary]),
            bigquery.ArrayQueryParameter("pos", "STRING", fn.pos.astype(str).tolist()), bigquery.ArrayQueryParameter("qrank", "INT64", qrank)])
        u = bq.query(base + f", big AS (SELECT u FROM x GROUP BY u HAVING COUNT(*) >= {int(a.min_entries)}) "
                     "SELECT u, k, COUNT(*) n, COUNTIF(top1) t FROM x JOIN big USING (u) GROUP BY u, k", job_config=jc).to_dataframe()
        f = bq.query(base + " SELECT k, LEAST(IFNULL(qk, 0), 7) qk, COUNT(*) n, COUNTIF(top1) t FROM x GROUP BY k, qk", job_config=jc).to_dataframe()
        u["week"] = w; f["week"] = w; U.append(u); F.append(f)
        book = t70 / "book.csv"; bk = []
        if book.exists():
            dk2k = {str(int(i)): min(int(kmap.get(g, 0)), 7) for i, g, p in zip(pd.to_numeric(fr.dk_player_id, errors="coerce").fillna(-1), fr.game_id, fr.pos) if p == "QB"}
            bk = [next((dk2k[v] for v in r if v in dk2k), 0) for r in pd.read_csv(book, dtype=str).values]
        for k in range(1, 8):
            fk = f[f.qk == k]; fq = f[f.qk > 0]
            G.append({"week": w, "k": k, "field": fk.n.sum() / fq.n.sum(), "top1": fk.t.sum() / max(fq.t.sum(), 1),
                      "book": (np.mean([x == k for x in bk]) if bk else np.nan), "hist_p_best_stack": HIST_P_BEST_STACK[k]})
        print(f"W{w}: contest {cid}, lineups {int(f.n.sum()):,}, multi-entry users {u.u.nunique():,}, book rows {len(bk)}", flush=True)
    if not U:
        print("no weeks with a real field"); return
    U = pd.concat(U, ignore_index=True); F = pd.concat(F, ignore_index=True); G = pd.DataFrame(G)
    print(f"\n(1) within user-week Mantel-Haenszel OR of a top-1% finish (users with {a.min_entries}+ entries), 95% bootstrap over user-weeks")
    for label, ex in (("2+ sub-$4k vs 0-1", lambda k: k >= 2), ("1+ sub-$4k vs none", lambda k: k >= 1)):
        est, num, den = mh_odds_ratio(U, ex); lo, hi = bootstrap_ci(num, den)
        rows.append({"week": "pooled", "stat": label, "value": round(est, 3), "lo": round(lo, 3), "hi": round(hi, 3)})
        per = []
        for w in sorted(U.week.unique()):
            e_w, n_w, d_w = mh_odds_ratio(U[U.week == w], ex); l_w, h_w = bootstrap_ci(n_w, d_w)
            rows.append({"week": int(w), "stat": label, "value": round(e_w, 3), "lo": round(l_w, 3), "hi": round(h_w, 3)}); per.append(f"W{w} {e_w:.2f}")
        print(f"  {label:20s} pooled {est:.2f} [{lo:.2f}, {hi:.2f}]; " + ", ".join(per))
    r = F.groupby(["week", "k"])[["n", "t"]].sum(); r["rate_%"] = (100 * r.t / r.n).round(2)
    print("\n    whole-field top-1% rate % by sub-$4k count (3 = 3+)"); print(r["rate_%"].unstack(0).to_string())
    print("\n(2) share of lineups by the QB's game total rank (7 = 7th or lower, summed) vs the 2014-2025 base rate of holding the best stack (7: per game)")
    print(G.pivot_table(index="k", values=["field", "top1", "book", "hist_p_best_stack"], aggfunc="mean").round(3).to_string())
    top4 = G[G.k <= 4].groupby("week")[["field", "top1", "book"]].sum().round(2)
    print("    top-4 games' share by week (base rate 0.55):"); print(top4.to_string())
    for w, t in top4.iterrows():
        for col in ("field", "top1", "book"):
            rows.append({"week": int(w), "stat": f"top4_games_share_{col}", "value": t[col], "lo": np.nan, "hi": np.nan})
    if a.out:
        pd.DataFrame(rows).to_csv(a.out, index=False); print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
