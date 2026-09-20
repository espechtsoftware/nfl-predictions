#!/usr/bin/env python3
"""First-entry promotion on the FINAL delivered book (order-only; membership unchanged).  v1.2 (2026-09-19)

  promote_first.py VET_DIR RUN_DIR OUT_DIR --final-vetting FV_DIR [--contests contests.json]
  promote_first.py --check-packet PACKET_JSON --run-dir RUN_DIR      # reproduce the labs' frozen control promotion

Rule = the labs' frozen `first_delivered_promotion.promote` (APPROVED_RULE_SHA asserted), applied unchanged: among delivered
ranks 1-30 whose tier is clean or soft, the row with the highest mean over the SELECTION worlds moves to rank 1; rows above it
shift down one; ranks 31+ are untouched.

Refusals (exit 2, nothing written) and the unavailable-player STOP (exit 3, nothing written):
  * source identity: VET_DIR/source_receipt.json must be byte-identical to RUN_DIR/receipt.json; replace.json (status OK,
    publishable true, no rehearsal flag set, required_k == book rows == receipt operational_k) must carry input_sha256 for the
    run's frame.parquet, candidates.parquet and both banks equal to the files' current sha256; banks float32 with shape
    (frame rows, receipt sims); candidates count == receipt candidates; replace.json output_sha256 must match book.csv and
    vetting_final.json.
  * final-book vetting (FV_DIR = the cleared vet_book.py run ON THE FINAL BOOK): its book.csv + order_source_ranks must
    reconstruct VET_DIR/book.csv row for row; every player of the book must lie in its evaluated set; risk recomputed from its
    player_flags must agree with its own per-row risk/hard unless a fresh designation raised it.
  * STOP (exit 3): if the final vetting or the replacement receipt marks ANY player of ANY row as unavailable by membership
    (DK/report/features OUT-class status, gated backup QB, placeholder salary), publication must not proceed: re-run the
    replacement with fresh status (the chain's un-promoted upload is unsafe too).  Market-silence HARD flags do not stop.
  * flags bound by position (sequential positions, row salary == frame salary sum, flagged names inside the row); rows are 9
    distinct frame ids, unique lineups, each a candidate of the run; contests.json entries positive integers summing to rows.
Tiers: final vetter weights per player, raised by the fresh DK/report designation in vetting_final.json (O/IR->100, D->3, Q->1);
hard = any weight >= 100; material = risk >= material_threshold; clean/soft otherwise.  Selection means: float32 sums over the
players in frame-row order per bank (== selector's candidate_matrix; bit-exact vs the labs' packet), float64 mean over the
equal-mass concatenation.  Parquet reads are column-allowlisted: frame id, dk_player_id, salary, name; candidates players.
Output OUT_DIR (create-once): book.csv, vetting_final.json (positions renumbered), final_vetting.json, copies of
frame.parquet / source_receipt.json / replace.json, promotion.json (all input/output sha256, permutation, tiers, contest moves).
"""
import argparse, csv, hashlib, json, shutil, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import first_delivered_promotion as fdp

APPROVED_RULE_SHA = "36ffcbcedc9b1b46d5aea5c9d04b425f0b842e3569a53c20802ef39f36af959f"
HARD = 100.0
SLOTS = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
BANKS = ("incumbent_player_scores.npy", "corrected_hsim_player_scores.npy")
FRAME_COLS = ["id", "dk_player_id", "salary", "name"]
OUT_STATUSES = {"o", "out", "ir", "injured reserve", "pup", "nfi", "sus", "suspended"}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def refuse(msg, code=2):
    print(f"PROMOTION {'STOP' if code == 3 else 'REFUSED'}: {msg}", file=sys.stderr); sys.exit(code)


def unavailable_by_flag(fs):
    """True when a vetter/replacement flag string asserts membership unavailability (not market silence)."""
    k, _, v = fs.partition(":"); v = v.strip().lower()
    if k in ("DK", "report", "features") and v in OUT_STATUSES: return True
    if k == "backup_qb" and ("behind-healthy" in v): return True
    if k == "qb" and v.startswith("gated"): return True
    if fs == "placeholder_salary": return True
    return False


def load_run(run, expect_sims=None, expect_rows=None):
    for req in ("frame.parquet", "candidates.parquet", "receipt.json", *BANKS):
        if not (Path(run) / req).exists(): refuse(f"RUN_DIR/{req} missing")
    frame = pd.read_parquet(Path(run) / "frame.parquet", columns=FRAME_COLS)
    banks = [np.load(Path(run) / b, mmap_mode="r", allow_pickle=False) for b in BANKS]
    for b in banks:
        if b.ndim != 2 or b.shape[0] != len(frame): refuse(f"bank shape {b.shape} does not match frame rows {len(frame)}")
        if b.dtype != np.float32: refuse(f"bank dtype {b.dtype} (selector banks are float32)")
        if expect_sims is not None and b.shape[1] != expect_sims: refuse(f"bank worlds {b.shape[1]} != receipt sims {expect_sims}")
    if banks[0].shape[1] != banks[1].shape[1] or banks[0].shape[1] < 2: refuse("banks differ in world count or are too narrow")
    return frame, banks


def candidate_orders(run, frame, expect_count=None):
    """frozenset(frame row indices) -> (candidate index, frame-row-ordered indices) from candidates.parquet (players only)."""
    cands = pd.read_parquet(Path(run) / "candidates.parquet", columns=["players"])
    if expect_count is not None and len(cands) != expect_count: refuse(f"candidates.parquet rows {len(cands)} != receipt candidates {expect_count}")
    id_row = {str(i): k for k, i in enumerate(frame["id"].astype(str))}
    orders = {}
    for c, toks in enumerate(cands["players"]):
        toks = [t.strip() for t in (toks.split(",") if isinstance(toks, str) else list(toks)) if str(t).strip()]
        try: idx = [id_row[t] for t in toks]
        except KeyError as e: refuse(f"candidate {c} token {e} not in frame ids")
        orders.setdefault(frozenset(idx), (c, sorted(idx)))  # frame-row order == the selector's Lineup player order
    return orders


def totals_matrix(rows_idx_ordered, banks):
    n_sel = banks[0].shape[1]; T = np.empty((len(rows_idx_ordered), 2 * n_sel), dtype=np.float32)
    for r, idx in enumerate(rows_idx_ordered):
        for bi, b in enumerate(banks):
            T[r, bi * n_sel:(bi + 1) * n_sel] = b[idx].sum(axis=0)
    if not np.isfinite(T).all(): refuse("non-finite totals in the selection banks")
    return T


def check_packet(packet_path, run):
    if sha(fdp.__file__) != APPROVED_RULE_SHA: refuse("rule file sha is not the approved rule")
    p = json.load(open(packet_path)); frame, banks = load_run(run)
    cands = pd.read_parquet(Path(run) / "candidates.parquet", columns=["players"]); id_row = {str(i): k for k, i in enumerate(frame["id"].astype(str))}
    control = p["books"]["control"]; labels = p["vetting"]["control"]["delivered_clean_or_soft"]
    rows_idx = []
    for c in control:
        toks = cands.iloc[int(c)]["players"]; toks = [t.strip() for t in (toks.split(",") if isinstance(toks, str) else list(toks)) if str(t).strip()]
        rows_idx.append(sorted(id_row[t] for t in toks))
    T = totals_matrix(rows_idx, banks)
    result, info = fdp.promote(list(range(len(control))), [bool(x) for x in labels], T)
    promoted = [control[i] for i in result]; exp = p["promotions"]["control"]; exp_book = p["books"]["control_promoted"]
    ok = (promoted == exp_book) and (info["promoted_from_rank"] == exp["promoted_from_rank"]) and abs(info["selection_mean"] - exp["selection_mean"]) <= 1e-9 and info["eligible_delivered_ranks"] == exp["eligible_delivered_ranks"]
    print(json.dumps({"check": "labs-control-promotion", "promoted_from_rank": info["promoted_from_rank"], "expected_rank": exp["promoted_from_rank"], "selection_mean": info["selection_mean"],
                      "expected_mean": exp["selection_mean"], "abs_diff": abs(info["selection_mean"] - exp["selection_mean"]), "promoted_candidate": promoted[0], "expected_candidate": exp_book[0],
                      "book_equal": promoted == exp_book, "eligible_equal": info["eligible_delivered_ranks"] == exp["eligible_delivered_ranks"], "rule_sha256": sha(fdp.__file__), "PASS": bool(ok)}, indent=1))
    return 0 if ok else 1


def contest_map(contests_path, n):
    blocks, r = [], 1
    for c in json.load(open(contests_path)):
        e = c.get("entries")
        if not isinstance(e, int) or isinstance(e, bool) or e <= 0: refuse(f"contests.json: entries for {c.get('name')!r} must be a positive integer (got {e!r})")
        blocks.append({"name": c["name"], "contest_id": str(c.get("contest_id", "")), "ranks": [r, r + e - 1]}); r += e
    if r - 1 != n: refuse(f"contests.json entries sum {r - 1} != book rows {n}")
    return blocks


def contest_of(blocks, rank):
    for b in blocks:
        if b["ranks"][0] <= rank <= b["ranks"][1]: return b["name"]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vet_dir", nargs="?"); ap.add_argument("run_dir", nargs="?"); ap.add_argument("out_dir", nargs="?")
    ap.add_argument("--final-vetting", help="vet_book.py output dir produced ON THE FINAL BOOK (required)")
    ap.add_argument("--contests", help="contests.json in delivery order (entries per contest)")
    ap.add_argument("--check-packet"); ap.add_argument("--run-dir", dest="check_run")
    a = ap.parse_args()
    if a.check_packet: sys.exit(check_packet(a.check_packet, a.check_run or a.run_dir))
    if not (a.vet_dir and a.run_dir and a.out_dir): ap.error("VET_DIR RUN_DIR OUT_DIR required")
    if sha(fdp.__file__) != APPROVED_RULE_SHA: refuse(f"rule file sha {sha(fdp.__file__)[:16]} is not the approved rule {APPROVED_RULE_SHA[:16]}")
    if not a.final_vetting: refuse("--final-vetting is required: run the cleared vetter on the final book first (no fallback to the pre-replacement vetting)")
    vet, run, out, fv = Path(a.vet_dir), Path(a.run_dir), Path(a.out_dir), Path(a.final_vetting)
    if out.exists(): refuse(f"{out} exists (create-once)")
    for req in ("book.csv", "vetting_final.json", "frame.parquet", "replace.json", "source_receipt.json"):
        if not (vet / req).exists(): refuse(f"{vet / req} missing")
    for req in ("vetting.json", "book.csv", "frame.parquet"):
        if not (fv / req).exists(): refuse(f"{fv / req} missing")
    # ---- replacement receipt: publishability, K, output binding ----
    rep = json.load(open(vet / "replace.json"))
    if rep.get("status") != "OK": refuse(f"replace.json status {rep.get('status')!r}")
    if rep.get("publishable") is not True: refuse("replace.json publishable is not true")
    rf = rep.get("rehearsal_flags") or {}
    if any(bool(v) for v in rf.values()): refuse(f"replace.json rehearsal flags set: {rf}")
    book_sha, vf_sha = sha(vet / "book.csv"), sha(vet / "vetting_final.json")
    osha = rep.get("output_sha256") or {}
    if osha.get("book.csv") != book_sha: refuse("replace.json output_sha256[book.csv] != VET_DIR/book.csv (stale or foreign receipt)")
    if osha.get("vetting_final.json") != vf_sha: refuse("replace.json output_sha256[vetting_final.json] != VET_DIR/vetting_final.json")
    # ---- source identity: run receipt == replacement's source receipt; run files == replacement's recorded input hashes ----
    if not (run / "receipt.json").exists(): refuse("RUN_DIR/receipt.json missing")
    src_sha = sha(vet / "source_receipt.json")
    if sha(run / "receipt.json") != src_sha: refuse("RUN_DIR/receipt.json is not byte-identical to VET_DIR/source_receipt.json (different source run)")
    insha = {Path(k).name: v for k, v in (rep.get("input_sha256") or {}).items()}
    if insha.get("source_receipt.json") != src_sha: refuse("replace.json input_sha256[source_receipt.json] != source_receipt.json")
    for name in ("frame.parquet", "candidates.parquet", *BANKS):
        if name not in insha: refuse(f"replace.json input_sha256 lacks {name}; cannot bind the source run")
        if sha(run / name) != insha[name]: refuse(f"RUN_DIR/{name} sha256 != the replacement's recorded input hash (altered or foreign source file)")
    receipt = json.load(open(run / "receipt.json")); cfg = receipt.get("config") or {}
    sims = cfg.get("sims"); op_k = cfg.get("operational_k"); n_cands = receipt.get("candidates")
    frame, banks = load_run(run, expect_sims=sims, expect_rows=None)
    fsha = sha(run / "frame.parquet")
    if sha(vet / "frame.parquet") != fsha: refuse("VET_DIR/frame.parquet != RUN_DIR/frame.parquet")
    if sha(fv / "frame.parquet") != fsha: refuse("final-vetting frame.parquet != RUN_DIR/frame.parquet")
    dk_row = {str(int(d)): k for k, d in enumerate(frame["dk_player_id"])}
    sal_of = dict(zip(frame["dk_player_id"].astype(int).astype(str), pd.to_numeric(frame["salary"], errors="coerce").fillna(0).astype(int)))
    name_of = dict(zip(frame["dk_player_id"].astype(int).astype(str), frame["name"].astype(str)))
    with open(vet / "book.csv") as f:
        rd = csv.reader(f); hdr = next(rd); rows = [r for r in rd if r]
    if hdr != SLOTS: refuse(f"unexpected book header {hdr}")
    n = len(rows)
    if n < 1: refuse("empty book")
    if rep.get("required_k") != n: refuse(f"replace.json required_k {rep.get('required_k')} != book rows {n}")
    if op_k is not None and op_k != n: refuse(f"receipt operational_k {op_k} != book rows {n}")
    seen = set()
    for i, r in enumerate(rows):
        if len(r) != 9 or len(set(r)) != 9: refuse(f"row {i + 1}: not 9 distinct ids")
        if any(d not in dk_row for d in r): refuse(f"row {i + 1}: id not in frame")
        if frozenset(r) in seen: refuse(f"row {i + 1}: duplicate lineup")
        seen.add(frozenset(r))
    final = json.load(open(vet / "vetting_final.json")); lus = final["lineups"]
    if final.get("publishable") is False: refuse("vetting_final.json publishable is false")
    if len(lus) != n: refuse("vetting_final.json rows != book rows")
    for i, (r, lu) in enumerate(zip(rows, lus)):
        if lu.get("position") != i + 1: refuse(f"vetting_final position {lu.get('position')} at index {i}")
        if int(lu.get("salary", -1)) != sum(sal_of[d] for d in r): refuse(f"row {i + 1}: vetting_final salary {lu.get('salary')} != book row salary {sum(sal_of[d] for d in r)} (flags not bound to this row)")
        names = {name_of[d] for d in r}
        for nm in lu.get("flags", {}):
            if nm not in names: refuse(f"row {i + 1}: flagged player {nm!r} is not in the row")
    # ---- final-book vetting: reconstruct its input and bind row for row ----
    fvj = json.load(open(fv / "vetting.json"))
    if not str(fvj.get("version", "")).startswith("vet-book-"): refuse(f"final vetting version {fvj.get('version')!r}")
    with open(fv / "book.csv") as f:
        rd = csv.reader(f); fh = next(rd); fv_rows = [r for r in rd if r]
    order = fvj.get("order_source_ranks") or []
    if fh != SLOTS or len(fv_rows) != n or len(order) != n or sorted(order) != list(range(1, n + 1)): refuse("final vetting book/order_source_ranks malformed or wrong size")
    recon = [None] * n
    for pos, rk in enumerate(order): recon[rk - 1] = fv_rows[pos]
    if recon != rows: refuse("final vetting was not run on this exact book (reconstructed input rows differ)")
    fl = fvj["lineups"]
    if len(fl) != n or any(int(x["rank"]) != i + 1 for i, x in enumerate(fl)): refuse("final vetting lineups malformed")
    thr = float(fvj["material_threshold"])
    evaluated = {d for r in fv_rows for d in r}
    pflags = fvj.get("player_flags") or {}
    w_vet = {str(v["dk"]): float(v["weight"]) for v in pflags.values()}   # absent == evaluated with no flag (weight 0)
    fl_vet = {str(v["dk"]): list(v.get("flags") or []) for v in pflags.values()}
    # ---- STOP: unavailable-by-membership players anywhere in the final book (final vetter or replacement receipt) ----
    unavailable = {}
    for d, flags in fl_vet.items():
        hits = [fs for fs in flags if unavailable_by_flag(fs)]
        if hits: unavailable.setdefault(d, set()).update(f"final-vetter {h}" for h in hits)
    for i, (r, lu) in enumerate(zip(rows, lus)):
        for nm, flags in lu.get("flags", {}).items():
            hits = [fs for fs in flags if unavailable_by_flag(fs)]
            if hits:
                for d in r:
                    if name_of[d] == nm: unavailable.setdefault(d, set()).update(f"replacement-receipt {h}" for h in hits)
    present = {d: [i + 1 for i, r in enumerate(rows) if d in r] for d in unavailable}
    present = {d: p for d, p in present.items() if p}
    if present:
        detail = "; ".join(f"{name_of[d]} ({', '.join(sorted(unavailable[d]))}) in {len(p)} lineup(s) {p[:8]}{'...' if len(p) > 8 else ''}" for d, p in present.items())
        refuse(f"unavailable player(s) in the final book -- re-run the replacement with fresh status before any publication (the chain's un-promoted upload is unsafe too): {detail}", code=3)
    # ---- tiers: final vetter weights raised by the fresh DK / report designation recorded per row ----
    hard_v = [bool(x["hard"]) for x in fl]; risk_v = [float(x["risk"]) for x in fl]
    for i, x in enumerate(fl):
        if bool(x.get("material")) != ((not hard_v[i]) and risk_v[i] >= thr): refuse(f"rank {i + 1}: vetter material flag inconsistent with threshold")
    def status_weight(v):
        v = v.strip().lower()
        return HARD if v in OUT_STATUSES else 3.0 if v in ("d", "doubtful") else 1.0 if v in ("q", "questionable") else 0.0
    hard, risk, fresh_raise = [], [], []
    for i, (r, lu) in enumerate(zip(rows, lus)):
        if not set(r) <= evaluated: refuse(f"row {i + 1}: player outside the final vetting's evaluated set (coverage gap cannot become clean)")
        tot, h, raised = 0.0, False, []
        for d in r:
            w = w_vet.get(d, 0.0)
            for fs in lu.get("flags", {}).get(name_of[d], []):
                k, _, v = fs.partition(":")
                if k in ("DK", "report"):
                    sw = status_weight(v)
                    if sw > w: raised.append(f"{name_of[d]}: {fs} raises {w} -> {sw}"); w = sw
            tot += w; h = h or w >= HARD
        hard.append(h); risk.append(tot); fresh_raise.append(raised)
        if not raised and (h != hard_v[i] or abs(tot - risk_v[i]) > 0.011): refuse(f"rank {i + 1}: recomputed risk {tot}/{h} != final vetter {risk_v[i]}/{hard_v[i]} without any fresh-status raise (player_flags coverage broken)")
    cos = [(not hard[i]) and risk[i] < thr for i in range(n)]
    # ---- selection means (frame-row order, float32) and the rule ----
    orders = candidate_orders(run, frame, expect_count=n_cands); rows_idx, cand_ids = [], []
    for i, r in enumerate(rows):
        key = frozenset(dk_row[d] for d in r)
        if key not in orders: refuse(f"row {i + 1}: lineup is not a candidate of this run (candidates.parquet)")
        c, idx = orders[key]; rows_idx.append(idx); cand_ids.append(c)
    T = totals_matrix(rows_idx, banks); means = T.mean(axis=1, dtype=np.float64)
    result, info = fdp.promote(list(range(n)), cos, T)
    if sorted(result) != list(range(n)) or set(result[:30]) != set(range(min(30, n))) or result[30:] != list(range(30, n)): refuse("permutation invariants failed")
    blocks = contest_map(a.contests, n) if a.contests else None
    # ---- write ----
    out.mkdir(parents=True, exist_ok=False)
    with open(out / "book.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(SLOTS); w.writerows(rows[i] for i in result)
    new_lus = []
    for p, i in enumerate(result):
        lu = dict(lus[i]); lu["position"] = p + 1; lu["delivered_position_before_promotion"] = i + 1; new_lus.append(lu)
    json.dump({**final, "version": str(final.get("version", "")) + "+promote-first-v1.2", "promotion": info, "lineups": new_lus}, open(out / "vetting_final.json", "w"), indent=1)
    shutil.copy2(fv / "vetting.json", out / "final_vetting.json")
    for fn in ("frame.parquet", "source_receipt.json", "replace.json"):
        shutil.copy2(vet / fn, out / fn)
    k = info["promoted_from_rank"]; moved = list(range(1, k + 1)) if k > 1 else []
    rec = {"tool": "promote_first.py v1.2", "summation": "float32 per bank, players in frame-row order; mean float64 over the equal-mass concatenation",
           "rule_file": "first_delivered_promotion.py", "rule_sha256": sha(fdp.__file__), "approved_rule_sha256": APPROVED_RULE_SHA,
           "inputs": {"vet_dir": str(vet), "run_dir": str(run), "final_vetting_dir": str(fv), "contests": a.contests},
           "input_sha256": {"book.csv": book_sha, "vetting_final.json": vf_sha, "replace.json": sha(vet / "replace.json"), "source_receipt.json": src_sha, "run_receipt.json": sha(run / "receipt.json"),
                            "frame.parquet": fsha, "final_vetting.json": sha(fv / "vetting.json"), "candidates.parquet": sha(run / "candidates.parquet"), **{b: sha(run / b) for b in BANKS}},
           "bindings": {"run_receipt_equals_source_receipt": True, "run_files_match_replacement_input_hashes": True, "bank_shape_dtype_vs_receipt": [list(b.shape) for b in banks],
                        "candidates_count_vs_receipt": n_cands, "required_k": n, "frame_sha_equal_vet_run_fv": True, "replace_receipt_matches_book_and_flags": True,
                        "final_vetting_reconstructs_book_rows": True, "flags_bound_by_position_salary_names": True, "all_rows_are_run_candidates": True, "coverage_complete": True,
                        "publishable": True, "rehearsal_flags": rf, "unavailable_players_in_book": 0},
           "final_vetting_version": fvj.get("version"), "final_vetted_at_utc": fvj.get("vetted_at_utc"), "material_threshold": thr,
           "promotion": info, "changed": k != 1, "permutation": [i + 1 for i in result], "membership_unchanged": True, "first30_set_unchanged": True, "rows_31_on_unchanged": True,
           "tier_counts": {"hard": sum(hard), "material": sum(1 for i in range(n) if not hard[i] and risk[i] >= thr), "clean_or_soft": sum(cos), "rows_raised_by_fresh_status": sum(1 for x in fresh_raise if x)},
           "fresh_status_raises": [{"position": i + 1, "raises": x} for i, x in enumerate(fresh_raise) if x],
           "first30": [{"position_before": i + 1, "position_after": result.index(i) + 1, "candidate": int(cand_ids[i]), "source": lus[i].get("source"), "selection_mean": float(means[i]),
                        "risk": risk[i], "risk_vetter": risk_v[i], "hard": hard[i], "eligible": cos[i], "flags": lus[i].get("flags", {})} for i in range(min(30, n))],
           "contest_blocks": blocks, "moved_rows": [{"position_before": i, "position_after": result.index(i - 1) + 1, "contest_before": contest_of(blocks, i) if blocks else None,
                                                     "contest_after": contest_of(blocks, result.index(i - 1) + 1) if blocks else None} for i in moved],
           "output_sha256": {"book.csv": sha(out / "book.csv"), "vetting_final.json": sha(out / "vetting_final.json"), "final_vetting.json": sha(out / "final_vetting.json")}}
    json.dump(rec, open(out / "promotion.json", "w"), indent=1)
    print(json.dumps({key: rec[key] for key in ("promotion", "changed", "tier_counts", "fresh_status_raises", "moved_rows", "output_sha256")}, indent=1))


if __name__ == "__main__":
    main()
