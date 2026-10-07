"""Winners' strategy study (operator 2026-10-06): for each 2026 week, (1) describe the lineups that won the Millionaire or
came within 10 points of the winner, by attributes a PRE-LOCK builder can act on; (2) turn the distinctive attributes into
a ladder of build rules (shape -> game environment -> salary structure -> pre-lock ownership); (3) enumerate lineups under
each rule set in projection order (the projection we played: ours W1-3, Fantasy Points W4) until one scores within 10 points
of the winner, logging how deep the search went; (4) run every week's final rule set on the other weeks (the fair test).
Hindsight by design: the rules are extracted from outcomes. The cross-week numbers are the only ones that generalize.

Usage: python winners_strategy_study.py OUT_DIR [--weeks 1,2,3,4] [--nmax 1500] [--test]
"""
from __future__ import annotations
import argparse, importlib.util, json, sys, time
from collections import Counter
from pathlib import Path
import numpy as np, pandas as pd, pulp

PROD = Path.home() / "projects/nfl-predictions"
spec = importlib.util.spec_from_file_location("MS", PROD / "scripts" / "moneygate_score.py"); MS = importlib.util.module_from_spec(spec); sys.modules["MS"] = MS; spec.loader.exec_module(MS)
CFG = MS.load_config()
SKILL = ("RB", "WR", "TE"); INACTIVE = {"O", "IR", "D", "NA", "OUT"}
FP_W4 = Path.home() / ".cache/laptop-agent/rehearsal/inputs/proj_fp-w4.csv"
OWN = {3: Path.home() / "moneygate/inputs/own/w3_ownership_sets.csv", 4: Path.home() / "moneygate/inputs/own/w4_ownership_fp.csv"}
WITHIN = 10.0

# ----------------------------------------------------------------------------- data
def load_week(w: int):
    W = MS.load_week(CFG, w); milly = MS.milly_cid(W)
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("dk_player_id").copy()
    fr["id"] = fr.dk_player_id.astype("Int64").astype(str)
    fr["pos"] = fr.pos.astype(str); fr["team"] = fr.team.astype(str); fr["opp"] = fr.opp.astype(str); fr["game"] = fr.game_id.astype(str)
    fr["salary"] = pd.to_numeric(fr.salary).astype(int)
    fr["total"] = pd.to_numeric(fr.total_line, errors="coerce"); fr["spread"] = pd.to_numeric(fr.spread_line, errors="coerce")
    fr["proj"] = pd.to_numeric(fr.mean_projection if "mean_projection" in fr else fr.proj, errors="coerce").fillna(0.0)
    if w == 4 and FP_W4.exists():
        fp = pd.read_csv(FP_W4); m = dict(zip(fp.dk_draftable_id.astype("Int64").astype(str), fp.fp))
        fpv = fr.dk_draftable_id.astype("Int64").astype(str).map(m); fr["proj"] = np.where(fpv.notna(), fpv, fr.proj); fr["proj_source"] = "fp"
    else:
        fr["proj_source"] = "ours"
    name_of = {str(k): v for k, v in W.name_of.items()}
    fr["fname"] = fr.id.map(name_of).fillna(fr.display_name.astype(str).map(MS.canon))
    fr["actual"] = fr.fname.map(lambda n: W.fpts.get(n, 0) / 100.0)
    fr["status_s"] = fr.status.astype(str) if "status" in fr else "None"
    fr["eligible"] = ~fr.status_s.isin(INACTIVE)
    # pre-lock ownership where a file exists
    fr["pown"] = np.nan
    if w in OWN and OWN[w].exists():
        o = pd.read_csv(OWN[w]); key = "dk_player_id" if "dk_player_id" in o else "id"
        fr["pown"] = fr.id.map(dict(zip(o[key].astype("Int64").astype(str), pd.to_numeric(o.pred_own, errors="coerce"))))
    # game-level pre-lock facts
    gt = fr.groupby("game")["total"].max(); fr["total_rank"] = fr.game.map(gt.rank(ascending=False, method="min"))
    fr["top_total_game"] = fr.total_rank == 1
    qb = fr[fr.pos == "QB"].sort_values("salary", ascending=False); fr["qb_rank"] = np.nan; fr.loc[qb.index, "qb_rank"] = np.arange(1, len(qb) + 1)
    # field
    f = W.field[W.field.contest_id.astype(str) == milly].copy(); f["points"] = pd.to_numeric(f.points); f["rank"] = pd.to_numeric(f["rank"])
    f["names"] = f.names.apply(lambda v: [MS.canon(str(n)) for n in (v if isinstance(v, (list, tuple)) else MS.parse_lineup(str(v)))])
    idx = {n: i for i, n in enumerate(fr.fname)}
    def to_idx(ns):
        out = [idx.get(n, -1) for n in ns]; return out if len(out) == 9 else None
    f["ix"] = f.names.apply(to_idx)
    f = f[f.ix.notna()].copy(); f["resolved"] = f.ix.apply(lambda v: all(i >= 0 for i in v))
    # realized ownership
    cnt = Counter(i for v in f.ix for i in v if i >= 0); fr["rown"] = [100.0 * cnt.get(i, 0) / len(f) for i in range(len(fr))]
    return W, fr.reset_index(drop=True), f.reset_index(drop=True)

# ----------------------------------------------------------------------------- attributes
def lineup_attrs(fr: pd.DataFrame, ix: list[int]) -> dict | None:
    if any(i < 0 for i in ix): return None
    p = fr.iloc[ix]; q = p[p.pos == "QB"]
    if len(q) != 1: return None
    q = q.iloc[0]; sk = p[p.pos.isin(SKILL)]
    mates = int((sk.team == q.team).sum()); bb = int((sk.team == q.opp).sum())
    games = p.game.nunique(); other = sk[sk.game != q.game].groupby("game").size()
    left = 50000 - int(p.salary.sum()); te = p[p.pos == "TE"]; dst = p[p.pos == "DST"]
    a = {"mates": "3+" if mates >= 3 else str(mates), "bb": "2+" if bb >= 2 else str(bb),
         "flex": "RB" if (p.pos == "RB").sum() == 3 else "TE" if (p.pos == "TE").sum() == 2 else "WR",
         "games": "<=4" if games <= 4 else "5" if games == 5 else "6+", "dual": "yes" if (other >= 2).any() else "no",
         "qb_total_rank": "1" if q.total_rank == 1 else "2-3" if q.total_rank <= 3 else "4+", "qb_fav": "fav" if q.spread < 0 else "dog",
         "top_total_n": "0" if int(p.top_total_game.sum()) == 0 else "1-2" if int(p.top_total_game.sum()) <= 2 else "3+",
         "dst_price": "exp" if int(dst.salary.iloc[0]) >= 3500 else "cheap",
         "salary_left": "0-200" if left <= 200 else "201-1000" if left <= 1000 else "1001+",
         "cheap": "0" if (sk.salary <= 4000).sum() == 0 else "1" if (sk.salary <= 4000).sum() == 1 else "2+",
         "qb_tier": "top3" if q.qb_rank <= 3 else "mid" if q.qb_rank <= 8 else "cheap", "te_price": "cheap" if int(te.salary.min()) <= 3500 else "not"}
    if fr.pown.notna().any():
        po = p.pown.fillna(0.0); a["max_own"] = "<=15" if po.max() <= 15 else "15-30" if po.max() <= 30 else "30+"
        a["n_low_own"] = "0" if (po < 5).sum() == 0 else "1" if (po < 5).sum() == 1 else "2+"
        a["own_sum"] = "<80" if po.sum() < 80 else "80-120" if po.sum() <= 120 else "120+"
    return a
LAYERS = [("shape", ["mates", "bb", "flex", "games", "dual"]), ("environment", ["qb_total_rank", "qb_fav", "top_total_n", "dst_price"]),
          ("salary", ["salary_left", "cheap", "qb_tier", "te_price"]), ("ownership", ["max_own", "n_low_own", "own_sum"])]
MIN_LIFT = 1.2

def describe(fr, f, winner):
    """attribute shares for the within-10 cluster, the top 100 and the field; the chosen value per attribute."""
    res = f[f.resolved]; sample = res if len(res) <= 60000 else res.sample(60000, random_state=7)
    A = {"cluster": [lineup_attrs(fr, ix) for ix in res[res.points >= winner * 100 - WITHIN * 100].ix],
         "top100": [lineup_attrs(fr, ix) for ix in res[res["rank"] <= 100].ix], "field": [lineup_attrs(fr, ix) for ix in sample.ix]}
    A = {k: [a for a in v if a] for k, v in A.items()}
    keys = sorted({k for a in A["field"] for k in a})
    table, chosen = {}, {}
    for k in keys:
        sh = {g: Counter(a[k] for a in A[g]) for g in A}; n = {g: max(1, len(A[g])) for g in A}
        vals = sorted({v for g in A for v in sh[g]})
        table[k] = {v: {g: round(sh[g].get(v, 0) / n[g], 3) for g in A} for v in vals}
        src = "cluster" if len(A["cluster"]) >= 4 else "top100"           # a 2-3 lineup cluster is read with the top 100
        mode, share = sh[src].most_common(1)[0]; share /= n[src]
        lift = share / max(table[k][mode]["field"], 1e-9)
        chosen[k] = {"value": mode, "share": round(share, 3), "field": table[k][mode]["field"], "lift": round(lift, 2), "source": src,
                     "use": bool(share >= 0.5 and lift >= MIN_LIFT)}
    return {"n": {g: len(A[g]) for g in A}, "unresolved_cluster": int((~f[f.points >= winner * 100 - WITHIN * 100].resolved).sum()),
            "table": table, "chosen": chosen}

# ----------------------------------------------------------------------------- the builder
def make_model(fr: pd.DataFrame, rules: dict, objective: str):
    """the MILP for one rule set; cuts are added by the caller (incremental enumeration)."""
    P = fr[fr.eligible & (fr.proj > 0) | (fr.pos == "DST") & fr.eligible].copy()
    P = P[P.salary > 0]; ids = list(P.index)
    m = pulp.LpProblem("l", pulp.LpMaximize); x = {i: pulp.LpVariable(f"x{i}", cat="Binary") for i in ids}
    val = P.actual if objective == "actual" else P.proj
    m += pulp.lpSum(float(val[i]) * x[i] for i in ids)
    pos = P.pos
    def S(mask): return pulp.lpSum(x[i] for i in ids if mask[i])
    m += S(pos == "QB") == 1; m += S(pos == "DST") == 1; m += S(pos.isin(SKILL)) == 7
    rb, wr, te = S(pos == "RB"), S(pos == "WR"), S(pos == "TE")
    fl = rules.get("flex"); m += rb == (3 if fl == "RB" else 2) if fl in ("RB",) else rb >= 2; 
    if fl == "WR": m += wr == 4
    elif fl == "TE": m += te == 2
    else:
        m += rb <= 3; m += wr >= 3; m += wr <= 4; m += te >= 1; m += te <= 2
        if fl == "RB": m += wr == 3; m += te == 1
    sal = pulp.lpSum(int(P.salary[i]) * x[i] for i in ids); m += sal <= 50000
    lo, hi = {"0-200": (49800, 50000), "201-1000": (49000, 49799), "1001+": (0, 48999)}.get(rules.get("salary_left"), (49000, 50000))
    m += sal >= lo; m += sal <= hi
    teams = sorted(P.team.unique()); games = sorted(P.game.unique())
    q = {t: S((pos == "QB") & (P.team == t)) for t in teams}
    km = {"0": (0, 0), "1": (1, 1), "2": (2, 2), "3+": (3, 7)}.get(rules.get("mates")); bm = {"0": (0, 0), "1": (1, 1), "2+": (2, 7)}.get(rules.get("bb"))
    for t in teams:
        mates = S(pos.isin(SKILL) & (P.team == t)); opp = P[P.team == t].opp.iloc[0]; bbs = S(pos.isin(SKILL) & (P.team == opp))
        if km: m += mates >= km[0] * q[t]; m += mates <= km[1] * q[t] + 7 * (1 - q[t])
        if bm: m += bbs >= bm[0] * q[t]; m += bbs <= bm[1] * q[t] + 7 * (1 - q[t])
    qg = {g: S((pos == "QB") & (P.game == g)) for g in games}
    if rules.get("dual") == "no":
        for g in games: m += S(pos.isin(SKILL) & (P.game == g)) <= 1 + 7 * qg[g]
    elif rules.get("dual") == "yes":
        z = {g: pulp.LpVariable(f"z{g}", cat="Binary") for g in games}
        for g in games: m += 2 * z[g] <= S(pos.isin(SKILL) & (P.game == g)); m += z[g] <= 1 - qg[g]
        m += pulp.lpSum(z.values()) >= 1
    if rules.get("games"):
        y = {g: pulp.LpVariable(f"y{g}", cat="Binary") for g in games}
        for g in games:
            m += y[g] <= S(P.game == g)
            for i in ids:
                if P.game[i] == g: m += y[g] >= x[i]
        gl, gh = {"<=4": (2, 4), "5": (5, 5), "6+": (6, 9)}[rules["games"]]; m += pulp.lpSum(y.values()) >= gl; m += pulp.lpSum(y.values()) <= gh
    ban = pd.Series(False, index=ids)
    r = rules.get("qb_total_rank")
    if r: ban |= (pos == "QB") & ~{"1": P.total_rank == 1, "2-3": (P.total_rank >= 2) & (P.total_rank <= 3), "4+": P.total_rank >= 4}[r]
    if rules.get("qb_fav"): ban |= (pos == "QB") & ((P.spread >= 0) if rules["qb_fav"] == "fav" else (P.spread < 0))
    if rules.get("qb_tier"): ban |= (pos == "QB") & ~{"top3": P.qb_rank <= 3, "mid": (P.qb_rank > 3) & (P.qb_rank <= 8), "cheap": P.qb_rank > 8}[rules["qb_tier"]]
    if rules.get("dst_price"): ban |= (pos == "DST") & ((P.salary < 3500) if rules["dst_price"] == "exp" else (P.salary >= 3500))
    if rules.get("max_own") and P.pown.notna().any(): ban |= P.pown.fillna(0) > {"<=15": 15, "15-30": 30, "30+": 999}[rules["max_own"]]
    for i in ids:
        if ban[i]: m += x[i] == 0
    if rules.get("top_total_n"):
        tl, th = {"0": (0, 0), "1-2": (1, 2), "3+": (3, 9)}[rules["top_total_n"]]; tt = S(P.top_total_game.astype(bool)); m += tt >= tl; m += tt <= th
    if rules.get("cheap"):
        cl, ch = {"0": (0, 0), "1": (1, 1), "2+": (2, 7)}[rules["cheap"]]; cc = S(pos.isin(SKILL) & (P.salary <= 4000)); m += cc >= cl; m += cc <= ch
    if rules.get("te_price") == "cheap": m += S((pos == "TE") & (P.salary <= 3500)) >= 1
    if P.pown.notna().any():
        po = P.pown.fillna(0.0)
        if rules.get("n_low_own"):
            nl, nh = {"0": (0, 0), "1": (1, 1), "2+": (2, 9)}[rules["n_low_own"]]; lowc = S(po < 5); m += lowc >= nl; m += lowc <= nh
        if rules.get("own_sum"):
            sl, shh = {"<80": (0, 79.9), "80-120": (80, 120), "120+": (120, 900)}[rules["own_sum"]]; os_ = pulp.lpSum(float(po[i]) * x[i] for i in ids); m += os_ >= sl; m += os_ <= shh
    return m, x, ids

def solve(m, x, ids, time_limit: int = 60):
    m.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=time_limit))
    if pulp.LpStatus[m.status] != "Optimal": return None
    return [i for i in ids if x[i].value() > 0.5]

def build(fr, rules, objective, prev, max_shared: int = 7):
    m, x, ids = make_model(fr, rules, objective)
    for L in prev: m += pulp.lpSum(x[i] for i in L if i in x) <= max_shared
    return solve(m, x, ids)

def enumerate_until(fr, rules, winner, lines, nmax, log, tag):
    """projection-ordered enumeration (each lineup differs from every earlier one by >= 2 players) until a lineup scores
    within WITHIN of the winner; returns the log record."""
    t0 = time.time(); prev = []; best = (-1.0, None); first = {k: None for k in ("hit", "top100", "top1pct", "top400")}
    m, x, ids = make_model(fr, rules, "proj")
    for n in range(1, nmax + 1):
        L = solve(m, x, ids)
        if L is None:
            log(f"    {tag}: infeasible / exhausted at n={n}"); break
        m += pulp.lpSum(x[i] for i in L) <= 7                       # the next lineup differs by >= 2 players from this one
        prev.append(L); act = float(fr.actual.iloc[L].sum())
        if act > best[0]: best = (act, L)
        for k, line in lines.items():
            if first[k] is None and act >= line: first[k] = n
        if first["hit"] is None and act >= winner - WITHIN: first["hit"] = n
        if first["hit"] is not None: break
        if n % 100 == 0: log(f"    {tag}: n={n} best {best[0]:.1f} (winner {winner:.1f}) {time.time()-t0:.0f}s")
    def desc(L): return [f"{fr.display_name.iloc[i]} {fr.pos.iloc[i]} {fr.team.iloc[i]} ${int(fr.salary.iloc[i])} {fr.actual.iloc[i]:.1f}" for i in sorted(L, key=lambda i: (fr.pos.iloc[i], -fr.salary.iloc[i]))] if L else None
    return {"n_built": len(prev), "first": first, "best_actual": round(best[0], 2), "best_lineup": desc(best[1]),
            "hit_lineup": desc(prev[first["hit"] - 1]) if first["hit"] else None, "secs": round(time.time() - t0, 1)}

# ----------------------------------------------------------------------------- driver
def run_week(w, out, nmax, log, test=False):
    W, fr, f = load_week(w); winner = float(f.points.max()) / 100.0; N = len(f)
    pts = np.sort(f.points.values); lines = {"top400": float(pts[-400]) / 100 if len(pts) >= 400 else winner, "top100": float(pts[-100]) / 100, "top1pct": float(pts[int(0.99 * len(pts))]) / 100, "hit": winner - WITHIN}
    d = describe(fr, f, winner)
    rec = {"week": w, "field": N, "winner": winner, "lines": lines, "proj_source": fr.proj_source.iloc[0], "frame_players": int(len(fr)), "describe": d, "layers": []}
    log(f"W{w}: field {N:,} winner {winner:.2f}; cluster {d['n']['cluster']} (unresolved in frame: {d['unresolved_cluster']}); top-1% {lines['top1pct']:.1f}; 100th {lines['top100']:.1f}")
    for k, c in d["chosen"].items(): log(f"    {k:14s} {c['value']:8s} share {c['share']:.2f} field {c['field']:.2f} lift {c['lift']:.2f} {'USE' if c['use'] else ''} ({c['source']})")
    rules = {}; hit_rules = None
    layers = [("L0 unconstrained", [])] + LAYERS
    for name, keys in layers:
        add = {k: d["chosen"][k]["value"] for k in keys if k in d["chosen"] and d["chosen"][k]["use"]}
        if name != "L0 unconstrained" and not add: log(f"  {name}: no distinctive attribute; skipped"); continue
        rules = {**rules, **add}
        O = build(fr, rules, "actual", []); oracle = float(fr.actual.iloc[O].sum()) if O else None
        log(f"  {name}: rules {rules} | oracle {oracle if oracle is None else round(oracle, 1)} (winner {winner:.1f})")
        entry = {"layer": name, "rules": dict(rules), "oracle": None if oracle is None else round(oracle, 2), "can_hit": bool(oracle is not None and oracle >= winner - WITHIN)}
        if entry["can_hit"]:
            entry["enum"] = enumerate_until(fr, rules, winner, lines, 30 if test else nmax, log, f"W{w} {name}")
            log(f"    -> first hit {entry['enum']['first']['hit']}, first top-1% {entry['enum']['first']['top1pct']}, first top-100 {entry['enum']['first']['top100']}, best {entry['enum']['best_actual']}")
            if entry["enum"]["first"]["hit"]: hit_rules = dict(rules)
        rec["layers"].append(entry)
        (out / f"week{w}.json").write_text(json.dumps(rec, indent=1, default=str))
        if hit_rules: break
    rec["final_rules"] = hit_rules or rules; rec["hit"] = hit_rules is not None
    (out / f"week{w}.json").write_text(json.dumps(rec, indent=1, default=str)); return rec

def cross(weeks, recs, out, nmax, log, test=False):
    res = {}
    for w_from in weeks:
        rules = recs[w_from]["final_rules"]
        for w_to in weeks:
            if w_to == w_from: continue
            W, fr, f = load_week(w_to); winner = float(f.points.max()) / 100.0; pts = np.sort(f.points.values)
            lines = {"top400": float(pts[-400]) / 100, "top100": float(pts[-100]) / 100, "top1pct": float(pts[int(0.99 * len(pts))]) / 100, "hit": winner - WITHIN}
            r = {k: v for k, v in rules.items() if not (k in ("max_own", "n_low_own", "own_sum") and fr.pown.isna().all())}
            O = build(fr, r, "actual", []); oracle = float(fr.actual.iloc[O].sum()) if O else None
            e = {"rules": r, "oracle": None if oracle is None else round(oracle, 2), "winner": winner, "lines": lines}
            log(f"  rules of W{w_from} on W{w_to}: oracle {e['oracle']} (winner {winner:.1f})")
            if oracle is not None: e["enum"] = enumerate_until(fr, r, winner, lines, 30 if test else nmax, log, f"W{w_from}->W{w_to}")
            res[f"{w_from}->{w_to}"] = e; (out / "cross.json").write_text(json.dumps(res, indent=1, default=str))
    return res

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--weeks", default="1,2,3,4"); ap.add_argument("--nmax", type=int, default=1500); ap.add_argument("--test", action="store_true")
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True); weeks = [int(x) for x in a.weeks.split(",")]
    lf = open(out / "log.txt", "a")
    def log(s): print(s, flush=True); lf.write(s + "\n"); lf.flush()
    log(f"== winners strategy study {time.strftime('%Y-%m-%d %H:%M:%S')} weeks {weeks} nmax {a.nmax} test {a.test}")
    recs = {}
    for w in weeks:
        p = out / f"week{w}.json"
        if p.exists() and json.loads(p.read_text()).get("final_rules") is not None and not a.test:
            recs[w] = json.loads(p.read_text()); log(f"W{w}: loaded from checkpoint"); continue
        recs[w] = run_week(w, out, a.nmax, log, a.test)
    log("== cross-week runs"); cross(weeks, recs, out, a.nmax, log, a.test); log("== done")
if __name__ == "__main__":
    main()
