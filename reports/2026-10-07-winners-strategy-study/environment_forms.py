"""The no-hindsight version of experiment C (operator 10-07: anything actionable?): sampled-world lineups under GENERIC
environment forms, the same four forms every week, chosen before any outcome:
  F1 the QB's game is the slate's top total, his team the favourite   F2 top total, underdog
  F3 the QB's game ranks 2nd-3rd by total, favourite                   F4 2nd-3rd total, underdog
Each form: one lineup per simulated world (that week's archived T-70 worlds, production's order), 125 worlds, duplicates
skipped; no stack, salary or ownership rule (the winners' shapes varied). Book-level read: a 32-row 'coverage book' of the
first 8 lineups of each form vs the first 32 sampled-world lineups with no form rule and vs the first 32 projection-order
lineups: rows in the real top 1%, rows in the top 100, the best row. Usage: environment_forms.py OUT_DIR [--weeks 1,2,3,4]"""
import argparse, importlib.util, json, sys, time
from pathlib import Path
import numpy as np, pandas as pd, pulp
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("WSS", HERE / "winners_strategy_study.py"); WSS = importlib.util.module_from_spec(spec); sys.modules["WSS"] = WSS; spec.loader.exec_module(WSS)
FORMS = {"F1_top_fav": {"qb_total_rank": "1", "qb_fav": "fav"}, "F2_top_dog": {"qb_total_rank": "1", "qb_fav": "dog"},
         "F3_2nd3rd_fav": {"qb_total_rank": "2-3", "qb_fav": "fav"}, "F4_2nd3rd_dog": {"qb_total_rank": "2-3", "qb_fav": "dog"}}
ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--weeks", default="1,2,3,4"); ap.add_argument("--n", type=int, default=125)
a = ap.parse_args(); OUT = Path(a.out); OUT.mkdir(parents=True, exist_ok=True); lf = open(OUT / "log-forms.txt", "a")
def P(s): print(s, flush=True); lf.write(s + "\n"); lf.flush()
for w in [int(x) for x in a.weeks.split(",")]:
    t0 = time.time(); W, fr, f = WSS.load_week(w); N = len(f); pts = np.sort(f.points.values); winner = float(pts[-1]) / 100
    lines = {"top1pct": float(pts[int(0.99 * N)]) / 100, "top100": float(pts[-100]) / 100, "hit": winner - WSS.WITHIN}
    worlds = np.load(Path(WSS.CFG["weeks"][str(w)]["t70_run"]) / "incumbent_player_scores.npy", mmap_mode="r"); assert worlds.shape[0] == len(fr)
    order = np.argsort(-np.asarray(worlds).sum(axis=0))
    P(f"== W{w}: winner {winner:.1f}; top 1% {lines['top1pct']:.1f}; top 100 {lines['top100']:.1f}; within 10 {lines['hit']:.1f}")
    res = {}
    def run(tag, rules, n, objective="world"):
        seen, rows = set(), []
        if objective == "proj":
            m, x, ids = WSS.make_model(fr, rules, "proj")
            for _ in range(n):
                L = WSS.solve(m, x, ids)
                if L is None: break
                m += pulp.lpSum(x[i] for i in L) <= 7; rows.append(float(fr.actual.iloc[L].sum()))
            return rows
        for k in order:
            if len(rows) >= n: break
            frk = fr.assign(proj=np.asarray(worlds[:, k], dtype=float)); m, x, ids = WSS.make_model(frk, rules, "proj"); L = WSS.solve(m, x, ids)
            if L is None: continue
            key = tuple(sorted(L))
            if key in seen: continue
            seen.add(key); rows.append(float(fr.actual.iloc[L].sum()))
        return rows
    for tag, rules in FORMS.items():
        r = run(tag, rules, a.n); res[tag] = r
        fst = {k: next((i + 1 for i, v in enumerate(r) if v >= line), None) for k, line in lines.items()}
        P(f"   {tag:14s} built {len(r)}: first top-1% {fst['top1pct']}, top-100 {fst['top100']}, within-10 {fst['hit']}; best {max(r) if r else float('nan'):.1f}; top-1% rows {sum(v >= lines['top1pct'] for v in r)} ({time.time()-t0:.0f}s)")
    res["no_form_world"] = run("no_form_world", {}, 32); res["projection_order"] = run("projection_order", {}, 32, "proj")
    book = [v for tag in FORMS for v in res[tag][:8]]
    for tag, rows in (("coverage book (8 per form, 32 rows)", book), ("sampled worlds, no form (32)", res["no_form_world"]), ("projection order, no form (32)", res["projection_order"])):
        P(f"   BOOK {tag:38s}: top-1% rows {sum(v >= lines['top1pct'] for v in rows)}, top-100 rows {sum(v >= lines['top100'] for v in rows)}, best {max(rows):.1f}")
    (OUT / f"forms-w{w}.json").write_text(json.dumps({"week": w, "lines": lines, "winner": winner, "rows": res}, indent=1))
