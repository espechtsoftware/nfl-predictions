#!/usr/bin/env python3
"""Week-3 selection-only shadow runner (production-owned; lab assignment 2026-09-20).

Reads ONE immutable lab run directory (frame.parquet, candidates.parquet, the two 429 x sims player-score banks,
receipt.json, book.json) and the week's contests.json, rebuilds the delivered selector's input EXACTLY (float32 sums of
bank rows in frame-row order per bank, equal-mass concatenation of the two banks), verifies control parity (membership
AND order) against the delivered book, then runs each intervention SEPARATELY on the same pool:

  control      the delivered `nfl2.selectors.select_expected_max` (dual_emax) from the pinned lab release
  ladder016    PREREG-016 `cap_prefix_then_fill`: inclusive rungs 194/200/210/220, weights 1/2/6/12, gamma 4, mean tie-break
  floor8       row filter: lowest served non-DST projection >= 8, then the control selector
  nodepth4     row filter: at most 3 same-team WR/TE with the QB, then the control selector

Operational K is read from contests.json (sum of entries). Infeasible arms (fewer than K rows after a filter) are
recorded, never relaxed. Outputs (all outcome-blind; nothing here reads a score): manifest.json (input hashes, selector
module hash, config), books.json (ordered candidate indices and rosters per arm, contest blocks), diagnostics.json
(pooled and per-bank simulated max statistics, membership overlap with control, prefix summaries). --label rehearsal
writes a REHEARSAL marker. No file under the run directory is modified.

  LAB_PY scripts/week3_shadow_runner.py --run RUN_DIR --contests contests.json --clone LAB_CLONE --out OUT_DIR [--label rehearsal]
"""
import argparse, hashlib, json, os, pathlib, sys, time
import numpy as np, pandas as pd

RUNGS = {194.0: 1.0, 200.0: 2.0, 210.0: 6.0, 220.0: 12.0}
GAMMA = 4
FLOOR = 8.0
MAX_SAME_TEAM_WRTE = 3
BANKS = ["incumbent_player_scores.npy", "corrected_hsim_player_scores.npy"]
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True); ap.add_argument("--contests", required=True); ap.add_argument("--clone", required=True)
ap.add_argument("--out", required=True); ap.add_argument("--label", default="live", choices=["live", "rehearsal"])
ap.add_argument("--chunk", type=int, default=1000)
ap.add_argument("--expect-sha", default=None, help="fail closed unless the clone's git HEAD equals this full sha and the tree is clean")
a = ap.parse_args()
run, out = pathlib.Path(a.run), pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
import subprocess
clone_head = subprocess.run(["git", "-C", a.clone, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or None
clone_dirty = bool(subprocess.run(["git", "-C", a.clone, "status", "--porcelain"], capture_output=True, text=True).stdout.strip()) if clone_head else None
if a.expect_sha and (clone_head != a.expect_sha or clone_dirty):
    (out / "CLONE-IDENTITY-FAILED").write_text(f"clone HEAD {clone_head} dirty={clone_dirty} != expected {a.expect_sha}\n"); sys.exit(4)
sys.path.insert(0, str(pathlib.Path(a.clone) / "src"))
from nfl2.selectors import select_expected_max, cap_prefix_then_fill  # noqa: E402  (the delivered implementations)
import nfl2.selectors as _sel  # noqa: E402

t0 = time.time()
receipt = json.loads((run / "receipt.json").read_text())
fr = pd.read_parquet(run / "frame.parquet", columns=["id", "name", "pos", "team", "salary", "proj"])
cands = pd.read_parquet(run / "candidates.parquet")
book = json.loads((run / "book.json").read_text())["entries"]
contests = json.load(open(a.contests)); contests = contests if isinstance(contests, list) else contests["contests"]
K = int(sum(int(c["entries"]) for c in contests))
assert receipt["config"]["operational_k"] == K, f"contests K {K} != receipt operational_k {receipt['config']['operational_k']}"
assert receipt["config"]["selector"] == "dual_emax", receipt["config"]["selector"]
sims = int(receipt["config"]["sims"])
banks = [np.load(run / b) for b in BANKS]
for b in banks: assert b.shape == (len(fr), sims) and b.dtype == np.float32, (b.shape, b.dtype)
ids = fr.id.astype(str).tolist(); row_of = {i: k for k, i in enumerate(ids)}
players = [p.split(",") for p in cands.players.astype(str)]
assert all(len(p) == 9 for p in players)
idx = np.array([sorted(row_of[p] for p in ps) for ps in players], dtype=np.int64)   # frame-row order
n = len(cands)

def totals(bank):
    T = np.empty((n, bank.shape[1]), dtype=np.float32)
    for s in range(0, n, a.chunk):
        e = min(n, s + a.chunk); acc = bank[idx[s:e, 0]].copy()
        for j in range(1, 9): acc += bank[idx[s:e, j]]          # sequential float32 accumulation, frame-row order
        T[s:e] = acc
    return T
Ts = [totals(b) for b in banks]; Td = np.concatenate(Ts, axis=1); del Ts
print(f"pool {n} x {Td.shape[1]} worlds built in {time.time()-t0:.0f}s; K={K}", flush=True)

# control + parity
t1 = time.time(); control = list(select_expected_max(Td, K)); print(f"control selected in {time.time()-t1:.0f}s", flush=True)
delivered = cands.book_rank.fillna(0).astype(int)
deliv_order = [int(i) for i in np.argsort(delivered.values, kind="stable") if delivered.values[i] > 0]
deliv_order = sorted(deliv_order, key=lambda i: delivered.values[i])
parity_membership = set(control) == set(deliv_order); parity_order = control == deliv_order
names_by_cand = cands.names.astype(str).tolist()
book_names = [sorted(e["players"]) for e in book]
parity_book_json = [sorted(names_by_cand[i].split("|")) for i in control] == book_names
print(f"parity: membership {parity_membership} order {parity_order} book.json {parity_book_json}", flush=True)
if not (parity_membership and parity_order and parity_book_json):
    (out / "PARITY-FAILED").write_text("control did not reproduce the delivered book; treatments not reported\n")
    sys.exit(3)

pos = dict(zip(ids, fr.pos.astype(str))); team = dict(zip(ids, fr.team.astype(str))); proj = dict(zip(ids, pd.to_numeric(fr.proj, errors="coerce")))
rosters = [frozenset(ps) for ps in players]
def qb_of(ps): return next(p for p in ps if pos[p] == "QB")
min_proj = np.array([min(proj[p] for p in ps if pos[p] != "DST") for ps in players])
depth = np.array([sum(1 for p in ps if pos[p] in ("WR", "TE") and team[p] == team[qb_of(ps)]) for ps in players])
mean_total = Td.mean(axis=1, dtype=np.float64)

def run_filtered(mask, name):
    keep = np.flatnonzero(mask)
    if len(keep) < K:
        return {"arm": name, "feasible": False, "pool": int(len(keep)), "order": [], "note": f"only {len(keep)} rows after the filter; K={K}; not relaxed"}
    sel = select_expected_max(Td[keep], K)
    return {"arm": name, "feasible": True, "pool": int(len(keep)), "order": [int(keep[i]) for i in sel]}

arms = {"control": {"arm": "control", "feasible": True, "pool": n, "order": [int(i) for i in control]}}
t1 = time.time()
clears = {r: (Td >= r) for r in RUNGS}
order016, prefix016 = cap_prefix_then_fill(clears, RUNGS, K, rosters, GAMMA, mean_total=mean_total); del clears
arms["ladder016"] = {"arm": "ladder016", "feasible": len(order016) == K, "pool": n, "order": [int(i) for i in order016], "prefix_count": int(prefix016),
                     "rungs_inclusive": {str(int(r)): w for r, w in RUNGS.items()}, "gamma": GAMMA, "tie_break": "pooled mean total"}
print(f"ladder016 in {time.time()-t1:.0f}s (prefix {prefix016})", flush=True)
arms["floor8"] = run_filtered(min_proj >= FLOOR, "floor8"); arms["floor8"].update({"floor": FLOOR, "applies_to": "lowest served proj among non-DST players"})
arms["nodepth4"] = run_filtered(depth <= MAX_SAME_TEAM_WRTE, "nodepth4"); arms["nodepth4"].update({"max_same_team_wrte": MAX_SAME_TEAM_WRTE})
print("arms done", {k: (v["feasible"], v["pool"]) for k, v in arms.items()}, flush=True)

# contest blocks (sequential layout: contests.json order)
blocks, p0 = [], 0
for c in contests:
    e = int(c["entries"]); blocks.append({"name": c.get("name"), "contest_id": str(c.get("contest_id", "")), "rows": [p0 + 1, p0 + e]}); p0 += e

def diag(order):
    if not order: return None
    Tb = Td[order]; mx = Tb.max(axis=0)
    per_bank = {}
    for bi, bname in enumerate(BANKS):
        sl = slice(bi * sims, (bi + 1) * sims); m = mx[sl]
        per_bank[bname] = {"max_mean": float(m.mean()), "p200": float((m >= 200).mean()), "p220": float((m >= 220).mean()), "p230": float((m >= 230).mean()), "p240": float((m >= 240).mean())}
    pref = {}
    for b in blocks:
        rows = order[b["rows"][0] - 1: b["rows"][1]]
        if rows: pm = Td[rows].max(axis=0); pref[b["name"]] = {"rows": b["rows"], "max_mean": float(pm.mean()), "p220": float((pm >= 220).mean())}
    return {"pooled": {"max_mean": float(mx.mean()), "p194": float((mx >= 194).mean()), "p200": float((mx >= 200).mean()), "p210": float((mx >= 210).mean()),
                       "p220": float((mx >= 220).mean()), "p230": float((mx >= 230).mean()), "p240": float((mx >= 240).mean())},
            "per_bank": per_bank, "row_mean_of_means": float(mean_total[order].mean()), "prefix_blocks": pref,
            "overlap_with_control": len(set(order) & set(control)), "order_positions_equal_control": sum(1 for i, j in zip(order, control) if i == j)}

diagnostics = {k: diag(v["order"]) for k, v in arms.items()}
books = {k: {**v, "rosters": [names_by_cand[i].split("|") for i in v["order"]], "candidate_ids": [players[i] for i in v["order"]]} for k, v in arms.items()}
manifest = {"schema": "week3-shadow-runner/v1", "label": a.label, "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "run_dir": str(run),
            "inputs_sha256": {f: sha(run / f) for f in ["frame.parquet", "candidates.parquet", "receipt.json", "book.json", *BANKS]},
            "contests_sha256": sha(a.contests), "K": K, "sims_per_bank": sims, "banks": BANKS, "pool_size": n,
            "selector_module": {"path": str(pathlib.Path(_sel.__file__)), "sha256": sha(_sel.__file__)}, "lab_clone": a.clone, "lab_clone_head": clone_head, "lab_clone_dirty": clone_dirty, "expect_sha": a.expect_sha,
            "receipt_identity": receipt.get("identity"), "receipt_selector": {k: receipt["config"].get(k) for k in ("selector", "seed", "hsim_seed", "hsim_worlds", "operational_k")},
            "totals_law": "per bank: float32 sequential sum of bank rows in ascending frame-row order; equal-mass concatenation [incumbent | corrected_hsim]",
            "parity": {"membership": parity_membership, "order": parity_order, "book_json_names": parity_book_json},
            "arms": {"control": "nfl2.selectors.select_expected_max", "ladder016": "nfl2.selectors.cap_prefix_then_fill inclusive 194/200/210/220 w 1/2/6/12 gamma 4",
                     "floor8": f"row filter min non-DST served proj >= {FLOOR} then control", "nodepth4": f"row filter same-team WR/TE with QB <= {MAX_SAME_TEAM_WRTE} then control"},
            "current_outcomes_read": False, "runner_sha256": sha(__file__), "seconds": round(time.time() - t0, 1)}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n"); (out / "books.json").write_text(json.dumps({"blocks": blocks, "arms": books}, indent=2) + "\n")
(out / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
if a.label == "rehearsal": (out / "REHEARSAL").write_text("rehearsal run on an archived artifact; not a Week-3 prelock output\n")
print(json.dumps({k: {"feasible": arms[k]["feasible"], "pool": arms[k]["pool"], **({"max_mean": round(d["pooled"]["max_mean"], 3), "p220": round(d["pooled"]["p220"], 5), "p230": round(d["pooled"]["p230"], 5), "p240": round(d["pooled"]["p240"], 5), "overlap": d["overlap_with_control"]} if (d := diagnostics[k]) else {})} for k in arms}, indent=1))
print(f"done in {time.time()-t0:.0f}s -> {out}")
