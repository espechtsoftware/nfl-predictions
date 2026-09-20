#!/usr/bin/env python3
"""Archive manifest + fixed-book component gap for a completed live run directory (read-only).

  manifest_and_gap.py RUN_DIR OUT_JSON [--k N]

Writes OUT_JSON with: sha256/bytes of every file in RUN_DIR; the receipt's identity, inputs.content_hashes,
inputs.games, banks, config, built_utc/lock_utc/draft_group/written; and the fixed-book component gap on the
delivered book (first K rows of book.csv, default all): per-world lineup totals from each saved player-score
bank joined through frame.dk_player_id, book-max mean and P(>= 200/220) under each bank and under the pooled
(equal-mass concatenation) mixture. Records explicitly that hsim calibration weights are NOT captured.
No actuals are read; nothing is written inside RUN_DIR.
"""
import hashlib, json, sys, os
import numpy as np, pandas as pd

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    run = sys.argv[1]; out = sys.argv[2]
    k = None
    if "--k" in sys.argv:
        k = int(sys.argv[sys.argv.index("--k") + 1])
    files = {}
    for name in sorted(os.listdir(run)):
        p = os.path.join(run, name)
        if os.path.isfile(p):
            files[name] = {"sha256": sha(p), "bytes": os.path.getsize(p)}
    receipt = json.load(open(os.path.join(run, "receipt.json")))
    frame = pd.read_parquet(os.path.join(run, "frame.parquet"))
    book = pd.read_csv(os.path.join(run, "book.csv"))
    if k is not None:
        book = book.head(k)
    idx = {int(v): i for i, v in enumerate(frame["dk_player_id"].astype(int).tolist())}
    rows = [[idx[int(v)] for v in r] for r in book.values.tolist()]
    if any(len(r) != 9 for r in rows):
        raise SystemExit("book rows must have 9 mapped players")
    banks = {"incumbent": np.load(os.path.join(run, "incumbent_player_scores.npy")),
             "hsim": np.load(os.path.join(run, "corrected_hsim_player_scores.npy"))}
    gap = {}
    maxes = {}
    for name, bank in banks.items():
        if bank.shape[0] != len(frame):
            raise SystemExit(f"{name} bank rows {bank.shape[0]} != frame rows {len(frame)}")
        totals = np.stack([bank[r, :].sum(axis=0) for r in rows])       # lineups x worlds
        bm = totals.max(axis=0)                                           # book max per world
        maxes[name] = bm
        gap[name] = {"worlds": int(bank.shape[1]), "book_max_mean": float(bm.mean()),
                     "p_ge_200": float((bm >= 200).mean()), "p_ge_220": float((bm >= 220).mean()),
                     "lineup_mean_total": float(totals.mean())}
    pooled = np.concatenate([maxes["incumbent"], maxes["hsim"]])
    gap["pooled_equal_mass"] = {"worlds": int(pooled.size), "book_max_mean": float(pooled.mean()),
                                "p_ge_200": float((pooled >= 200).mean()), "p_ge_220": float((pooled >= 220).mean())}
    gap["hsim_minus_incumbent"] = {"book_max_mean": gap["hsim"]["book_max_mean"] - gap["incumbent"]["book_max_mean"],
                                   "p_ge_220_pp": 100 * (gap["hsim"]["p_ge_220"] - gap["incumbent"]["p_ge_220"])}
    doc = {
        "run_dir": os.path.abspath(run), "book_rows_scored": int(len(book)), "frame_rows": int(len(frame)),
        "files": files,
        "receipt": {key: receipt.get(key) for key in ("identity", "banks", "config", "built_utc", "lock_utc",
                                                      "draft_group", "written", "season", "week", "candidates",
                                                      "book_k80_is_nested_prefix", "a5_sidecars", "salary_pull")},
        "receipt_inputs": {key: receipt.get("inputs", {}).get(key) for key in
                           ("content_hashes", "games", "book_contract", "injury_source", "market_means",
                            "tabpfn_rows", "proj_tourney", "universe", "excluded_injury_out_names")},
        "not_captured": ["hsim calibration weights / pilot intermediates (no run retains them; reconstruction is not original capture)"],
        "fixed_book_component_gap": gap,
        "note": "descriptive fixed-book quantities under each saved bank; not an efficacy estimate; no actuals read",
    }
    json.dump(doc, open(out, "w"), indent=1, default=str)
    g = gap
    print(f"{run}: {len(book)} lineups x {len(frame)} players | incumbent {g['incumbent']['book_max_mean']:.2f} / P220 {100*g['incumbent']['p_ge_220']:.2f}% | "
          f"hsim {g['hsim']['book_max_mean']:.2f} / P220 {100*g['hsim']['p_ge_220']:.2f}% | pooled {g['pooled_equal_mass']['book_max_mean']:.2f} / {100*g['pooled_equal_mass']['p_ge_220']:.2f}% | gap {g['hsim_minus_incumbent']['book_max_mean']:+.2f} pts, {g['hsim_minus_incumbent']['p_ge_220_pp']:+.2f} pp -> {out}")

if __name__ == "__main__":
    main()
