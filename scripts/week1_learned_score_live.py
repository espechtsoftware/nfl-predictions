"""Learned lineup score applied to a LIVE run dir — both forms:
 (a) learned-book : the paid book re-sorted by the frozen book model v1 (within-book z, includes greedy rank);
 (b) pool-level   : the frozen pool model (no greedy rank) scored over EVERY candidate in candidates.parquet (within-pool z),
     emitting shadow books LEARNED_POOL (top-N by learned), BLEND_Q99 (z learned + z simulated q99 on the selection bank),
     UNION (DEMAX and learned-pool interleaved: every prefix K = DEMAX K/2 + learned K/2).
Each book is an emitter-compatible dir: book.csv (DK slot order, dk_player_id) + frame.parquet + receipt.json.
Historical basis (2026-09-13, out of season on the Neo4j PREREG-083 corpus, 200-candidate pools, 72 slate-arms):
 K=30: LEARNED_POOL +5.11, UNION +3.08, BLEND_Q99 +2.51, RESORT +2.01 vs DEMAX;  K=80: BLEND_Q99 +2.00, UNION +1.92, LEARNED_POOL +1.31.
Usage: python learned_score_live.py RUN_DIR [--entries 90] [--k 30] [--out-root DIR]"""
import argparse, json, pathlib, shutil, sys
from datetime import UTC, datetime
import numpy as np, pandas as pd
sys.path.insert(0, "/home/erich/week1-sunday/tools")
from learned_order_live import COLS, MODEL, lineup_features_vec
SLOTS = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]

def greedy_div(order_idx, lineups, K, cap):
    """Greedy by score with a pairwise-overlap cap (historical rule LEARNED_DIV/BLEND_DIV)."""
    chosen, sets = [], []
    for i in order_idx:
        st = set(lineups[i])
        if all(len(st & c) <= cap for c in sets): chosen.append(i); sets.append(st)
        if len(chosen) == K: break
    return chosen

def concentration(order, lineups, k):
    import itertools
    from collections import Counter
    sets = [set(lineups[i]) for i in order[:k]]; ov = [len(a & b) for a, b in itertools.combinations(sets, 2)]; ex = Counter(p for s in sets for p in s)
    return {"mean_pairwise_overlap": round(float(np.mean(ov)), 2) if ov else 0.0, "pairs_sharing_ge6": round(float(np.mean(np.array(ov) >= 6)), 2) if ov else 0.0, "distinct_players": len(ex), "max_exposure": round(max(ex.values()) / max(len(sets), 1), 2)}

def dk_rows(lineups, fr):
    dkid = fr.dk_player_id.astype(str); pos = fr.pos.astype(str); rows = []
    for ids in lineups:
        by = {"QB": [], "RB": [], "WR": [], "TE": [], "DST": []}
        for i in ids: by[pos[i]].append(i)
        slots = [by["QB"][0], by["RB"][0], by["RB"][1], by["WR"][0], by["WR"][1], by["WR"][2], by["TE"][0]]
        flex = [i for i in ids if i not in slots and pos[i] != "DST"][0]; slots += [flex, by["DST"][0]]
        rows.append([dkid[i] for i in slots])
    return rows

def write_book(out, name, lineups, fr, run, extra):
    d = out / name; d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(dk_rows(lineups, fr), columns=SLOTS).to_csv(d / "book.csv", index=False); shutil.copy(run / "frame.parquet", d / "frame.parquet")
    src = json.loads((run / "receipt.json").read_text()); src.update({"learned_shadow": {"book": name, "source_run": str(run), "built_utc": datetime.now(UTC).isoformat(), **extra}, "written": len(lineups)})
    (d / "receipt.json").write_text(json.dumps(src, indent=1) + "\n"); return d

def main(run, entries, k, out_root, exclude_players=None, overlap_cap=5, exposure_cap=0.40):
    import math
    from collections import Counter
    run = pathlib.Path(run); m = json.loads(MODEL.read_text()); out = pathlib.Path(out_root or (str(run) + "-learned")); out.mkdir(parents=True, exist_ok=True)
    fr = pd.read_parquet(run / "frame.parquet"); fr = fr.set_index(fr.id.astype(str)); fr["salary"] = pd.to_numeric(fr.salary, errors="coerce")
    cands = pd.read_parquet(run / "candidates.parquet"); lineups = [c.split(",") for c in cands.players]
    assert all(all(p in fr.index for p in lu) for lu in lineups), "candidate player outside the frame"
    # production projection quantiles (the historical snapshot's proj_p10/p90/std analog); own_est has no live source
    from google.cloud import bigquery
    c = bigquery.Client(project="nfl-predictions-503414")
    import os; S, W = int(os.environ.get("SEASON", 2026)), int(os.environ.get("WEEK", 1))
    pr = c.query(f"""SELECT dk_player_id, proj_p10, proj_p90, proj_std, generated_at FROM `nfl-predictions-503414.nfl_predictions.player_projections`
                    WHERE season={S} AND week={W} AND generated_at=(SELECT MAX(generated_at) FROM `nfl-predictions-503414.nfl_predictions.player_projections` WHERE season={S} AND week={W})""").result().to_dataframe()
    pr["dk"] = pr.dk_player_id.astype(str); pr = pr.drop_duplicates("dk").set_index("dk"); gen_at = str(pr.generated_at.max())
    dk = fr.dk_player_id.astype(str); num = {}
    for col in COLS:
        if col in ("proj_p10", "proj_p90", "proj_std"): num[col] = pd.Series(pd.to_numeric(pr[col].reindex(dk.values), errors="coerce").to_numpy(), index=fr.index)
        elif col == "own_est": num[col] = pd.Series(np.nan, index=fr.index)
        else: num[col] = pd.to_numeric(fr[col], errors="coerce") if col in fr.columns else pd.Series(np.nan, index=fr.index)
    coverage = {col: int(num[col].notna().sum()) for col in COLS}
    # simulated lineup statistics on the selection bank (incumbent law): q99 and P(>=200) per candidate
    M = np.load(run / "incumbent_player_scores.npy", mmap_mode="r"); assert M.shape[0] == len(fr), (M.shape, len(fr))
    ix = {p: i for i, p in enumerate(fr.index)}; idx = np.array([[ix[p] for p in lu] for lu in lineups]); q99 = np.empty(len(lineups)); p200 = np.empty(len(lineups))
    for s in range(0, len(lineups), 256):
        W = np.zeros((min(256, len(lineups) - s), M.shape[1]), dtype=np.float32)
        for j in range(9): W += M[idx[s:s + 256, j]]
        q99[s:s + 256] = np.quantile(W, 0.99, axis=1); p200[s:s + 256] = (W >= 200).mean(axis=1)
    cands["sim_q99"] = q99; cands["sim_p200"] = p200
    z = lambda x: (x - x.mean()) / (x.std() + 1e-9)
    # (b) pool model over every candidate
    Fp = lineup_features_vec(lineups, fr, num, np.zeros(len(lineups))).reindex(columns=m["features_pool"]).fillna(0.0)
    cands["learned_pool"] = z(Fp).fillna(0.0).to_numpy() @ np.array(m["coef_pool"]); cands["blend_q99"] = z(cands.learned_pool) + z(cands.sim_q99)
    # (a) the paid book (book_rank order) re-sorted by the book model
    book = cands[cands.book_rank.notna()].sort_values("book_rank"); assert len(book) == entries, (len(book), entries)
    paid_rows = pd.read_csv(run / "book.csv", dtype=str); assert [set(r) for r in paid_rows.values.tolist()] == [set(r) for r in dk_rows([lineups[i] for i in book.index], fr)], "book.csv does not match candidates.parquet book_rank"
    Fb = lineup_features_vec([lineups[i] for i in book.index], fr, num, book.book_rank.to_numpy()).reindex(columns=m["features"]).fillna(0.0)
    book = book.assign(learned_book=z(Fb).fillna(0.0).to_numpy() @ np.array(m["coef"]))
    order_book = book.sort_values("learned_book", ascending=False)
    dk2id = dict(zip(fr.dk_player_id.astype(str), fr.index)); excl = {dk2id.get(x, x) for x in (exclude_players or []) if x}
    ok = np.array([not (set(lu) & excl) for lu in lineups]); cands["eligible"] = ok
    pool_order = cands[ok].sort_values("learned_pool", ascending=False); blend_order = cands[ok].sort_values("blend_q99", ascending=False)
    def greedy_div_exp(order_idx, K, cap, exp):
        lim = math.ceil(exp * K); chosen, sets, ex = [], [], Counter()
        for i in order_idx:
            st = set(lineups[i])
            if all(len(st & c) <= cap for c in sets) and all(ex[q] < lim for q in st): chosen.append(i); sets.append(st); ex.update(st)
            if len(chosen) == K: break
        return chosen
    exp40_all = greedy_div_exp(list(pool_order.index), entries, overlap_cap, exposure_cap); today = greedy_div_exp(list(pool_order.index), k, overlap_cap, exposure_cap)
    tset = set(today); rest = [i for i in book.index if i not in tset and ok[i]]; fill = [i for i in exp40_all if i not in tset and i not in set(rest)]
    today90 = today + (rest + fill)[:entries - len(today)]
    union, seen = [], set()
    for a, b in zip(book.index, pool_order.index):
        for i in (a, b):
            if i not in seen and len(union) < entries: seen.add(i); union.append(i)
    demax_set = set(book.index); books = {
        "learned-book": (list(order_book.index), {"model": "book v1 (within-book z, incl greedy rank)", "loso_top30_vs_greedy": m["loso_top30_vs_greedy"]}),
        "learned-pool": (list(pool_order.index[:entries]), {"model": "pool v1 (within-pool z, no greedy rank)", "historical_K30_vs_DEMAX": "+5.11", "historical_K80_vs_DEMAX": "+1.31"}),
        "blend-q99": (list(blend_order.index[:entries]), {"model": "z(learned_pool) + z(sim_q99, incumbent selection bank)", "historical_K30_vs_DEMAX": "+2.51", "historical_K80_vs_DEMAX": "+2.00"}),
        "union": (union, {"model": "DEMAX and learned-pool interleaved (prefix K = DEMAX K/2 + learned K/2)", "historical_K30_vs_DEMAX": "+3.08", "historical_K80_vs_DEMAX": "+1.92"}),
        "learned-div5": (greedy_div(list(pool_order.index), lineups, entries, 5), {"model": "greedy by learned_pool, pairwise overlap <= 5", "historical_K30_vs_DEMAX": "+5.65", "historical_K80_vs_DEMAX": "+2.66"}),
        "blend-div5": (greedy_div(list(blend_order.index), lineups, entries, 5), {"model": "greedy by blend_q99, pairwise overlap <= 5", "historical_K30_vs_DEMAX": "+3.65", "historical_K80_vs_DEMAX": "+2.72"}),
        "learned-div5-exp40": (exp40_all, {"model": f"greedy by learned_pool, pairwise overlap <= {overlap_cap}, single-player exposure <= {exposure_cap:.0%}", "historical_K30_vs_DEMAX": "+6.07", "historical_K80_vs_DEMAX": "+3.17"}),
        "today-30": (today, {"model": f"TODAY'S PRODUCT: first {k} of learned-div5-exp40 over the whole pool (HARD-vetted players excluded: {sorted(excl)})", "historical_K30_vs_DEMAX": "+6.07"}),
        "today-90": (today90, {"model": f"today-30 first, then the paid book's remaining lineups in expected-max order (then learned-div5-exp40 fill)", "historical_K30_vs_DEMAX": "+6.07 (prefix 30)"})}
    summary = {"source_run": str(run), "pool_candidates": int(len(cands)), "entries": entries, "k": k, "production_generated_at": gen_at, "feature_coverage_players": coverage, "built_utc": datetime.now(UTC).isoformat(), "books": {}}
    for name, (order, extra) in books.items():
        extra = {**extra, "source_cand_ids": [int(cands.cand.iloc[i]) for i in order], "overlap_with_paid_book": len(set(order) & demax_set), f"overlap_top{k}_with_paid_top{k}": len(set(order[:k]) & set(book.index[:k])),
                 "mean_sim_q99": float(cands.sim_q99.iloc[order].mean()), f"mean_sim_q99_top{k}": float(cands.sim_q99.iloc[order[:k]].mean()), "mean_sim_p200": float(cands.sim_p200.iloc[order].mean()),
                 "tags": cands.tag.iloc[order].value_counts().to_dict(), "mean_salary": float(cands.salary.iloc[order].mean()), f"concentration_top{k}": concentration(order, lineups, k), "concentration_all": concentration(order, lineups, entries)}
        write_book(out, name, [lineups[i] for i in order], fr, run, extra); summary["books"][name] = {kk: v for kk, v in extra.items() if kk != "source_cand_ids"}
    ex = Counter(q for i in today for q in lineups[i]); nm = fr.display_name.astype(str); ps = fr.pos.astype(str); tm = fr.team.astype(str)
    lines = [f"# today-30 exposure (single-player cap {exposure_cap:.0%} = {math.ceil(exposure_cap * k)} of {k}; pairwise overlap cap {overlap_cap})", "", "| player | pos | team | salary | in lineups | share |", "|---|---|---|---:|---:|---:|"]
    lines += [f"| {nm[q]} | {ps[q]} | {tm[q]} | {int(fr.salary[q])} | {c_} | {c_ / k:.0%} |" for q, c_ in ex.most_common()]
    (out / "today-30" / "exposure.md").write_text("\n".join(lines) + "\n"); summary["today_30"] = {"cand_ids": [int(cands.cand.iloc[i]) for i in today], "excluded_players": sorted(excl), "eligible_candidates": int(ok.sum()), "exposure_top": [(nm[q], c_) for q, c_ in ex.most_common(8)]}
    summary["paid_book"] = {f"concentration_top{k}": concentration(list(book.index), lineups, k), "concentration_all": concentration(list(book.index), lineups, entries), "mean_sim_q99": float(book.sim_q99.mean()), f"mean_sim_q99_top{k}": float(book.sim_q99.head(k).mean()), "mean_sim_p200": float(book.sim_p200.mean()), "tags": book.tag.value_counts().to_dict()}
    cands.assign(learned_book=book.learned_book.reindex(cands.index), learned_pool_pos=cands.learned_pool.rank(ascending=False).astype(int), blend_pos=cands.blend_q99.rank(ascending=False).astype(int)).drop(columns=["names", "all_tags"]).to_csv(out / "candidate_scores.csv", index=False)
    pos = {}
    for name, (order, _) in books.items():
        rank_in = {i: r + 1 for r, i in enumerate(order)}
        pos[name] = {int(book.book_rank.loc[i]): rank_in.get(i) for i in book.index}
    pos["learned_pool_rank_in_pool"] = {int(book.book_rank.loc[i]): int(cands.learned_pool.rank(ascending=False).loc[i]) for i in book.index}
    (out / "paid_book_positions.json").write_text(json.dumps({"source_run": str(run), "positions": pos}, indent=1) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n"); print(json.dumps(summary, indent=1)); print("books under", out)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--entries", type=int, default=90); ap.add_argument("--k", type=int, default=30); ap.add_argument("--out-root")
    ap.add_argument("--exclude-players", default="", help="comma-separated dk_player_ids (HARD-vetted) excluded from every pool-level selection"); ap.add_argument("--overlap-cap", type=int, default=5); ap.add_argument("--exposure-cap", type=float, default=0.40); a = ap.parse_args()
    main(a.run, a.entries, a.k, a.out_root, [x.strip() for x in a.exclude_players.split(",") if x.strip()], a.overlap_cap, a.exposure_cap)
