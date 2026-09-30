"""Dealing variants on the same books (rows + field percentiles saved per slate by 11_panel_term_tabpfn.py), on the
week's plan under the head layout: as armed; L25's small-contest overlap limit (2-5 entries) at M; the limit extended to
every multi-entry contest; an overlap limit across the single-entry contests; a per-contest exposure cap. Per contest
class: tickets as a multiple of the field's expectation, P(a contest cashes at least once), slates with no ticket.
    PLAN_FILE=<contests.json> ENTER_LAYOUT_PY=<enter_layout.py at the tip> PANEL_DIR=<dir> python read_dealing.py <run dir> [...]"""
import json, glob, os, sys, importlib.util, collections, math
import numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location("el", os.environ["ENTER_LAYOUT_PY"]); el = importlib.util.module_from_spec(spec); sys.modules["el"] = el; spec.loader.exec_module(el)
plan = json.load(open(os.environ["PLAN_FILE"]))
main_c = [x for x in plan if x.get("track", "mean") == "mean"]
base_ranks = [r for x, r in zip(plan, el.assign_ranks(plan, "head")) if x.get("track", "mean") == "mean"]
lo = min(min(r) for r in base_ranks); base_ranks = [[i - lo for i in r] for r in base_ranks]
K = max(max(r) for r in base_ranks) + 1
def cls(x):
    n = int(x["entries"]); return "single" if n == 1 else ("2-5" if n <= 5 else ("10" if n <= 10 else "20"))
lines = [float(x["line_percentile"]) / 100 for x in main_c]
W = os.environ["PANEL_DIR"]

def limit(ranks, rp, M, max_entries):
    """L25's limit through the tip's own function, with the size ceiling widened when asked."""
    old = el.SMALL_MAX_ENTRIES; el.SMALL_MAX_ENTRIES = max_entries
    try:
        out, _ = el.limit_small_overlap(main_c, ranks, rp, M)
    finally:
        el.SMALL_MAX_ENTRIES = old
    return out

def singles_limit(ranks, rp, M):
    """The single-entry contests take rows that pairwise share <= M players, in rank order, instead of rows 1..s."""
    out = [list(r) for r in ranks]
    idx = [i for i, x in enumerate(main_c) if int(x["entries"]) == 1 and "ranks" not in x]
    chosen = []
    for i in sorted(idx, key=lambda i: ranks[i][0]):
        for r in range(K):
            if r in chosen: continue
            if all(len(rp[r] & rp[c]) <= M for c in chosen):
                out[i] = [r]; chosen.append(r); break
    return out

def exposure_cap(ranks, rp, share):
    """Per contest of n >= 2 rows: a player may sit in at most ceil(share * n) of its rows; rows are re-dealt in rank
    order (the first head rank kept), wrapping within the mean ranks."""
    out = [list(r) for r in ranks]
    for i, x in enumerate(main_c):
        n = len(ranks[i])
        if n < 2 or "ranks" in x: continue
        cap = max(1, math.ceil(share * n)); got = [ranks[i][0]]; cnt = collections.Counter(rp[ranks[i][0]])
        order = ranks[i][1:] + [r for r in range(K) if r not in ranks[i]]
        for r in order:
            if len(got) == n: break
            if r in got: continue
            if all(cnt[p] < cap for p in rp[r]):
                got.append(r); cnt.update(rp[r])
        if len(got) < n: got = list(ranks[i])          # keep head rows (the live fallback)
        out[i] = got
    return out

VARIANTS = {
    "head (armed)": lambda rp: base_ranks,
    "L25 limit 2-5, M=5": lambda rp: limit(base_ranks, rp, 5, 5),
    "L25 limit 2-5, M=4": lambda rp: limit(base_ranks, rp, 4, 5),
    "limit 2-10, M=5": lambda rp: limit(base_ranks, rp, 5, 10),
    "limit 2-10, M=4": lambda rp: limit(base_ranks, rp, 4, 10),
    "limit ALL multi, M=5": lambda rp: limit(base_ranks, rp, 5, 20),
    "limit ALL multi, M=6": lambda rp: limit(base_ranks, rp, 6, 20),
    "singles M=5 + limit 2-10 M=5": lambda rp: singles_limit(limit(base_ranks, rp, 5, 10), rp, 5),
    "singles M=4 + limit 2-10 M=5": lambda rp: singles_limit(limit(base_ranks, rp, 5, 10), rp, 4),
    "singles M=6 + limit 2-10 M=5": lambda rp: singles_limit(limit(base_ranks, rp, 5, 10), rp, 6),
    "exposure cap 50% per contest": lambda rp: exposure_cap(base_ranks, rp, 0.5),
}
classes = ("single", "2-5", "10", "20", "all")
res = collections.defaultdict(lambda: collections.defaultdict(list))
n_slates = 0
for d in sys.argv[1:]:
    for f in sorted(glob.glob(f"{W}/{d}/*.json")):
        R = json.load(open(f)); n_slates += 1
        for arm, v in R["arms"].items():
            rows = v["rows"]; pct = np.array(v["pct"])
            assert len(rows) >= K, (len(rows), K)
            rp = [frozenset(r) for r in rows[:K]]
            for name, fn in VARIANTS.items():
                rk = fn(rp)
                per = {}
                for c in classes:
                    tix = 0; cash = 0; ncon = 0; exp = 0.0; changed = 0
                    for i, x in enumerate(main_c):
                        if c != "all" and cls(x) != c: continue
                        hit = int((pct[rk[i]] >= lines[i]).sum()); tix += hit; cash += (hit > 0); ncon += 1
                        exp += len(rk[i]) * (1 - lines[i]); changed += (sorted(rk[i]) != sorted(base_ranks[i]))
                    per[c] = (tix, cash, ncon, exp, changed)
                res[(arm, name)]["per"].append(per)
print(f"{n_slates} slate-banks; main rows {K}; classes by contest count:", collections.Counter(cls(x) for x in main_c))
rows_out = []
for (arm, name), v in res.items():
    row = {"arm": arm, "dealing": name}
    for c in classes:
        tix = np.array([p[c][0] for p in v["per"]]); cash = np.array([p[c][1] for p in v["per"]]); ncon = v["per"][0][c][2]; exp = v["per"][0][c][3]
        chg = np.mean([p[c][4] for p in v["per"]])
        row[f"{c}: tix x field"] = round(float(tix.mean() / exp), 2)
        row[f"{c}: P(contest cashes)"] = round(float(cash.mean() / ncon), 3)
        row[f"{c}: slates w/ 0"] = round(float((tix == 0).mean()), 2)
        if c != "all": row[f"{c}: contests changed"] = round(float(chg), 1)
    rows_out.append(row)
t = pd.DataFrame(rows_out); pd.set_option("display.width", 400); pd.set_option("display.max_columns", 60)
for c in classes:
    cols = ["arm", "dealing"] + [k for k in t.columns if k.startswith(c + ":")]
    print(f"\n== class {c}"); print(t[cols].to_string(index=False))

# ---- paired reads against the armed dealing, per class: tickets (x field) and P(contest cashes), 90% intervals ----
rng = np.random.default_rng(21)
seas = []
for d in sys.argv[1:]:
    for f in sorted(glob.glob(f"{W}/{d}/*.json")):
        seas.append(json.load(open(f))["season"])
seas = np.array(seas)
def boot(dv, n=3000):
    ys = sorted(set(seas)); out = []
    for _ in range(n):
        idx = np.concatenate([rng.choice(np.where(seas == y)[0], (seas == y).sum()) for y in ys]); out.append(dv[idx].mean())
    return np.percentile(out, [5, 95])
print("\n== paired against 'head (armed)', per class (Δ tickets as a share of the field's expectation; Δ P(contest cashes)); 90% intervals")
prows = []
for (arm, name), v in res.items():
    if name == "head (armed)": continue
    h = res[(arm, "head (armed)")]["per"]
    row = {"arm": arm, "dealing": name}
    for c in classes:
        exp = v["per"][0][c][3]; ncon = v["per"][0][c][2]
        dt = np.array([p[c][0] - q[c][0] for p, q in zip(v["per"], h)]) / exp
        dc = np.array([p[c][1] - q[c][1] for p, q in zip(v["per"], h)]) / ncon
        lo_, hi_ = boot(dt); lo2, hi2 = boot(dc)
        row[f"{c}: Δtix"] = f"{dt.mean():+.2f} [{lo_:+.2f},{hi_:+.2f}] {int((dt > 0).sum())}-{int((dt < 0).sum())}"
        row[f"{c}: ΔP(cash)"] = f"{dc.mean():+.3f} [{lo2:+.3f},{hi2:+.3f}]"
    prows.append(row)
pt = pd.DataFrame(prows)
for c in classes:
    print(f"\n-- {c}"); print(pt[["arm", "dealing", f"{c}: Δtix", f"{c}: ΔP(cash)"]].to_string(index=False))
