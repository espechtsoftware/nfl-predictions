"""ACTION 2 + ACTION 3 (post-review-6 plan §A4, §B3): frozen-pool
counterfactuals on the promoted canonical panel. No new simulation,
no new MILP — everything is recomputed from persisted masks using the
SAME selector helper production used.

ACTION 2 — leave-one-generator-out, both bounds (Sol's design):
  conservative: drop candidates produced EXCLUSIVELY by the generator
  aggressive:   drop every candidate whose tag set contains it
ACTION 3 — tail-line sensitivity: reselect at 187 / 194 / 200 from the
  preregistered masks and score EVERY portfolio at ALL thresholds, so
  an objective is never judged only on the line it optimized.

  python scripts/frozen_pool_analysis.py <panel_run_id>
"""
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.optimizer.lineup import select_from_support  # noqa: E402

N_ENTRIES = 40
LINES = (187.0, 194.0, 200.0)


def _bits(h, n):
    return np.unpackbits(np.frombuffer(bytes.fromhex(h), dtype=np.uint8),
                         bitorder="big")[:n].astype(bool)


def _load(panel):
    d = query_df(f"""
        SELECT season, week, cand_ix, tag, all_tags, selected, selected_rank,
               sim_mean, actual_score, n_worlds,
               clear_bits_187, clear_bits_194, clear_bits_200
        FROM `{settings.predictions}.replay_candidates`
        WHERE panel_run_id = '{panel}' AND research_eligible""")
    d["tags"] = d.all_tags.map(
        lambda s: json.loads(s) if isinstance(s, str) else [])
    return d


def _select(g, line_col, keep_mask, n=N_ENTRIES):
    """Reselect from a (possibly reduced) frozen pool."""
    sub = g[keep_mask]
    if len(sub) < n:
        return None
    nw = int(sub.n_worlds.iloc[0])
    clears = np.stack([_bits(b, nw) for b in sub[line_col]])
    picked = select_from_support(clears, clears.mean(axis=1),
                                 sub.sim_mean.to_numpy(), n)
    return sub.iloc[picked]


def action2(d):
    print("\n" + "=" * 78)
    print("ACTION 2 — leave-one-generator-out (frozen pool, both bounds)")
    print("=" * 78)
    tags = sorted({t for lst in d.tags for t in lst})
    base_rows, rows = [], []
    for (s, w), g in d.groupby(["season", "week"]):
        sel = g[g.selected]
        base_rows.append({"season": s, "week": w,
                          "sel_best": sel.actual_score.max(),
                          "oracle": g.actual_score.max()})
    base = pd.DataFrame(base_rows)
    b_clears = int((base.sel_best >= 194).sum())
    print(f"baseline (as shipped): {b_clears}/{len(base)} clears, "
          f"mean best {base.sel_best.mean():.1f}, "
          f"mean regret {(base.oracle - base.sel_best).mean():.1f}")

    for tg in tags:
        for bound in ("conservative", "aggressive"):
            per = []
            for (s, w), g in d.groupby(["season", "week"]):
                if bound == "conservative":
                    keep = ~g.tags.map(lambda L, t=tg: L == [t])
                else:
                    keep = ~g.tags.map(lambda L, t=tg: t in L)
                out = _select(g, "clear_bits_194", keep.to_numpy())
                if out is None:
                    continue
                per.append({"season": s, "week": w,
                            "sel_best": out.actual_score.max(),
                            "pool_oracle": g[keep].actual_score.max(),
                            "dropped": int((~keep).sum())})
            p = pd.DataFrame(per)
            if p.empty:
                continue
            m = base.merge(p, on=["season", "week"], suffixes=("_b", ""))
            rows.append({
                "generator": tg, "bound": bound,
                "dropped_avg": round(p.dropped.mean(), 1),
                "clears": int((m.sel_best >= 194).sum()),
                "d_clears": int((m.sel_best >= 194).sum()) - b_clears,
                "d_mean_best": round(m.sel_best.mean() - m.sel_best_b.mean(), 2),
                "d_pool_oracle": round(
                    (m.pool_oracle - m.oracle).mean(), 2),
            })
    r = pd.DataFrame(rows)
    print("\n(negative d_clears = removing that generator COSTS tails)")
    print(r.to_string(index=False))
    return r


def action3(d):
    print("\n" + "=" * 78)
    print("ACTION 3 — tail-line sensitivity (every portfolio scored at ALL lines)")
    print("=" * 78)
    out = []
    for line, col in zip(LINES, ("clear_bits_187", "clear_bits_194",
                                 "clear_bits_200")):
        per = []
        for (s, w), g in d.groupby(["season", "week"]):
            sel = _select(g, col, np.ones(len(g), dtype=bool))
            if sel is None:
                continue
            per.append({"season": s, "week": w,
                        "best": sel.actual_score.max(),
                        "oracle": g.actual_score.max()})
        p = pd.DataFrame(per)
        out.append({
            "select_line": int(line),
            "c187": int((p.best >= 187).sum()),
            "c194": int((p.best >= 194).sum()),
            "c200": int((p.best >= 200).sum()),
            "mean_best": round(p.best.mean(), 1),
            "median": round(p.best.median(), 1),
            "q90": round(p.best.quantile(0.9), 1),
            "mean_regret": round((p.oracle - p.best).mean(), 1),
            "worst_season": round(
                p.groupby("season").best.mean().min(), 1),
        })
    r = pd.DataFrame(out)
    print(r.to_string(index=False))
    return r


def main():
    panel = sys.argv[1]
    d = _load(panel)
    print(f"panel {panel}: {len(d):,} candidates, "
          f"{d.groupby(['season','week']).ngroups} slates")
    a2 = action2(d)
    a3 = action3(d)
    a2.to_csv("/home/erich/nfl-panels/action2_logo.csv", index=False)
    a3.to_csv("/home/erich/nfl-panels/action3_tailline.csv", index=False)
    print("\nsaved -> ~/nfl-panels/action2_logo.csv, action3_tailline.csv")


if __name__ == "__main__":
    main()
