#!/usr/bin/env python3
"""Study 60's weekly record (the prereg reports/2026-10-08-prereg-study60-cash-line.md), after settlement.

From P3's weekly arms (scripts/p3_arms.sh's arms.json), the rows a big-contest ticket could take, in book.csv order:
    R0 #1, R0 #2   the ENTERED book's rows 1-2
    FP #1          MEAN_MILP's row 1 (the plain capped optimizer on the live projections, FP's from W5)
    PROPS #1, #2   PROPS_MILP's rows 1-2 (props-implied DK points where a player has props)
and the pairs R0 PAIR = {R0 #1, R0 #2}, MIXED = {R0 #1, PROPS #1} ({R0 #1, PROPS #2} when PROPS #1 is R0 #1's lineup)
and PROPS PAIR = {PROPS #1, PROPS #2}. Two lineups are the same when they hold the same nine players in any order.

Each row's real points (moneygate_score's week tables: canonical names, hundredths; a name nobody in the field rostered
scores 0 and is counted, as P3) give P1's latent z in the SAME week's Millionaire field (p1_record.latent_z, unchanged:
z = Phi^-1(1 - p), p = (position - 0.5) / N, position = 1 + the field's entries (ours removed) strictly above, N = those
entries + 1). A pair's z is its better row's.
    D1 = z(PROPS #1) - z(R0 #1)        one ticket
    D2 = z(MIXED) - z(R0 PAIR)         two tickets
Looks at W8, W12 and W18 over the valid prospective weeks (W5 on) up to the look: a look with fewer than 4 valid weeks
reads "too few valid weeks"; DEAD LEVER when the lineups were the same in more than 80% of them; else the two-sided 90%
t interval (each side P1's one-sided 95% bound, n - 1 df): lower > 0 "the props row is the better ...", upper < 0 "the
book's row is the better ...", otherwise "no difference shown". Advice; the operator decides.
Descriptive: each row's position in every contest of the week's private ladder file (1 + the contest's entries, ours
removed, strictly above; a hit at or inside its line: cash500_last_position for big / gpp, seat_last_position for sat),
the Millionaire top-20% proxy line (p <= 0.20), FP #1 against R0 #1, PROPS PAIR against R0 PAIR. W2-4 are the in-sample
baseline (the P3 replay), printed apart and never pooled. Behind moneygate_score's reconcile gate, as P1's reader.
z, positions, counts and rates only (no dollars).

    python scripts/s60_record.py --weeks 2,3,4,5 --arms 2=<p3 arms dir>,3=<dir>,4=<dir>,5=<dir> [--ladders <dir>] [--out <json>]
    python scripts/s60_record.py --census --arms 2=<dir>,...   (outcome-blind: which lineups are the same; reads no points)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import t as student_t

HERE = Path(__file__).resolve().parent
P1_SHA256 = "ea142610e30320b03d4b4d66270abea571088950df3855d48d90ff895267bbb8"   # p1_record.py, P1's frozen reader (amendment 2)
ARMS = ("ENTERED", "MEAN_MILP", "PROPS_MILP")
ROWS = ("R0 #1", "R0 #2", "FP #1", "PROPS #1", "PROPS #2")
PROSPECTIVE_FROM, LOOKS, MIN_WEEKS, DEAD_SHARE = 5, (8, 12, 18), 4, 0.80
ONE_SIDED = 0.95                                   # each side of the two-sided 90% interval (P1's one-sided 95% bound)
PROXY_P = 0.20                                     # the Millionaire field's top 20%: "about any cash" in a $333+ contest
LADDERS = Path.home() / "private" / "cash-line"
DECISIONS = {"D1": "single ticket", "D2": "second ticket"}


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod)
    return mod


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def book_rows(path: Path, n: int = 2) -> list[tuple[str, ...]]:
    """The book's first n rows as player-id tuples (book.csv: a header, then one lineup of nine ids per line)."""
    with open(path, newline="") as fh:
        rd = csv.reader(fh)
        next(rd)
        rows = [tuple(x.strip().removesuffix(".0") for x in r) for r, _ in zip(rd, range(n))]
    if len(rows) < n or any(len(r) != 9 or len(set(r)) != 9 for r in rows):
        raise SystemExit(f"STUDY 60 REFUSED: {path} has fewer than {n} rows of nine distinct players")
    return rows


def same(a, b) -> bool:
    """The same lineup: the same nine players, in any order."""
    return frozenset(a) == frozenset(b)


def same_pair(p, q) -> bool:
    return {frozenset(x) for x in p} == {frozenset(x) for x in q}


def arm_status(arms: dict, arm: str) -> tuple[bool, str, Path | None]:
    """(valid, reason, book): P3's void flag, its twin builds identical, the book read is the build (content identity);
    ENTERED must also be the entered book byte for byte."""
    a = (arms.get("arms") or {}).get(arm)
    if not a:
        return False, f"{arm} not in arms.json", None
    if a.get("void"):
        return False, f"{arm} void: {a['void']}", None
    b = a.get("builds") or []
    if len(b) != 2 or b[0] != b[1]:
        return False, f"{arm}: its twin builds differ", None
    book = Path(a["book"])
    if not book.is_file() or sha256(book) != b[0]:
        return False, f"{arm}: {book} is not the recorded build", None
    if arm == "ENTERED" and (arms.get("week_void") or b[0] != arms.get("entered_book_sha256")):
        return False, "ENTERED is not the entered book (P3's week is void)", None
    return True, "", book


def week_rows(arms_dir: Path) -> dict:
    """Outcome-blind: the week's candidate rows and pairs from P3's arms, with each arm's validity. No points read."""
    arms = json.loads((Path(arms_dir) / "arms.json").read_text())
    st = {arm: arm_status(arms, arm) for arm in ARMS}
    rows: dict[str, tuple | None] = dict.fromkeys(ROWS)
    if st["ENTERED"][0]:
        rows["R0 #1"], rows["R0 #2"] = book_rows(st["ENTERED"][2], 2)
    if st["MEAN_MILP"][0]:
        rows["FP #1"] = book_rows(st["MEAN_MILP"][2], 1)[0]
    if st["PROPS_MILP"][0]:
        rows["PROPS #1"], rows["PROPS #2"] = book_rows(st["PROPS_MILP"][2], 2)
    pairs: dict[str, tuple | None] = {"R0 PAIR": None, "MIXED": None, "PROPS PAIR": None}
    if rows["R0 #1"]:
        pairs["R0 PAIR"] = (rows["R0 #1"], rows["R0 #2"])
    if rows["R0 #1"] and rows["PROPS #1"]:
        px = rows["PROPS #2"] if same(rows["PROPS #1"], rows["R0 #1"]) else rows["PROPS #1"]
        pairs["MIXED"] = (rows["R0 #1"], px)
    if rows["PROPS #1"]:
        pairs["PROPS PAIR"] = (rows["PROPS #1"], rows["PROPS #2"])
    valid = {"D1": st["ENTERED"][0] and st["PROPS_MILP"][0], "D2": st["ENTERED"][0] and st["PROPS_MILP"][0],
             "FP": st["ENTERED"][0] and st["MEAN_MILP"][0]}
    ident = {"D1": valid["D1"] and same(rows["PROPS #1"], rows["R0 #1"]),
             "D2": valid["D2"] and same_pair(pairs["MIXED"], pairs["R0 PAIR"]),
             "FP": valid["FP"] and same(rows["FP #1"], rows["R0 #1"])}
    return {"rows": rows, "pairs": pairs, "valid": valid, "same": ident,
            "void": {arm: s[1] for arm, s in st.items() if not s[0]}}


def position_and_p(points: int, others_sorted: np.ndarray) -> tuple[int, float]:
    """P1's convention: position = 1 + the entries strictly above; p = (position - 0.5) / N, N = entries + 1."""
    o = np.asarray(others_sorted, np.int64)
    above = int(len(o) - np.searchsorted(o, np.int64(points), side="right"))
    return above + 1, (above + 0.5) / (len(o) + 1)


def ladder_rows(week: int, ladders: Path) -> list[dict]:
    """The week's private ladder file (positions only), sha-checked against <file>.sha256."""
    f = ladders / f"cash-lines-w{week:02d}.csv"
    if not f.is_file():
        return []
    want = (f.parent / (f.name + ".sha256")).read_text().split()[0]
    if sha256(f) != want:
        raise SystemExit(f"STUDY 60 REFUSED: {f} does not match its .sha256")
    with open(f, newline="") as fh:
        return list(csv.DictReader(fh))


def line_of(row: dict) -> int:
    """big / gpp: the last position paying $500+ cash; sat: the last seat."""
    return int(row["cash500_last_position"]) if row["role"] in ("big", "gpp") else int(row["seat_last_position"])


def score_week(M, P1, W, wr: dict, lad: list[dict]) -> dict:
    """The rows' real points, latent z in the Millionaire field, pair z, D1 / D2 / FP, the proxy line and the ladder hits."""
    milly = M.milly_cid(W)
    if milly is None:
        raise SystemExit(f"W{W.week}: no Millionaire among the week's contests")
    om = W.others_sorted(milly)
    pts, z, miss = {}, {}, {}
    for r, lu in wr["rows"].items():
        if lu is None:
            continue
        try:
            names = [W.name_of[str(x)] for x in lu]
        except KeyError as e:
            raise SystemExit(f"W{W.week}: {r} holds player id {e} not in the week's T-70 frame") from None
        p, m = M.lineup_points(names, W.fpts, impute_missing=True)
        pts[r], miss[r] = int(p), len(m)
        z[r] = float(P1.latent_z(np.asarray([p], np.int64), om)[0])
    zr = {tuple(sorted(lu)): z[r] for r, lu in wr["rows"].items() if lu is not None}
    pz = {k: max(zr[tuple(sorted(a))] for a in pr) for k, pr in wr["pairs"].items() if pr is not None}
    d = {}
    if wr["valid"]["D1"]:
        d["D1"] = z["PROPS #1"] - z["R0 #1"]
        d["D2"] = pz["MIXED"] - pz["R0 PAIR"]
    if wr["valid"]["FP"]:
        d["FP"] = z["FP #1"] - z["R0 #1"]
    if "PROPS PAIR" in pz and "R0 PAIR" in pz:
        d["PROPS PAIR"] = pz["PROPS PAIR"] - pz["R0 PAIR"]
    proxy = {r: position_and_p(pts[r], om)[1] <= PROXY_P for r in pts}
    hits = []
    for c in lad:
        cid, line = str(c["contest_id"]), line_of(c)
        o = W.others_sorted(cid)
        if len(o) == 0:
            hits.append({"contest_id": cid, "role": c["role"], "line": line, "no_field": True})
            continue
        pos = {r: position_and_p(pts[r], o)[0] for r in pts}
        hits.append({"contest_id": cid, "role": c["role"], "line": line, "size": int(c["size"]), "position": pos,
                     "hit": {r: (line > 0 and q <= line) for r, q in pos.items()},
                     "own_pct": {r: 100.0 * (1 - (q - 0.5) / (len(o) + 1)) for r, q in pos.items()}})
    return {"points": pts, "missing_names": miss, "z": z, "pair_z": pz, "d": d, "proxy_top20": proxy, "ladder": hits}


def read_look(values: list[float], same_flags: list[bool], what: str) -> dict:
    """One decision at one look: too few weeks / DEAD LEVER / the two-sided 90% t interval's reading."""
    n = len(values)
    if n < MIN_WEEKS:
        return {"n": n, "reading": f"too few valid weeks ({n} < {MIN_WEEKS})"}
    share = float(np.mean(same_flags))
    v = np.asarray(values, float); mean = float(v.mean())
    half = float(student_t.ppf(ONE_SIDED, n - 1) * v.std(ddof=1) / math.sqrt(n))
    out = {"n": n, "same_share": share, "mean": mean, "lo": mean - half, "hi": mean + half}
    if share > DEAD_SHARE:
        out["reading"] = f"DEAD LEVER (the lineups were the same in {sum(same_flags)} of {n} valid weeks)"
    elif mean - half > 0:
        out["reading"] = f"the props row is the better {what}"
    elif mean + half < 0:
        out["reading"] = f"the book's row is the better {what}"
    else:
        out["reading"] = "no difference shown"
    return out


def looks_due(weeks: list[int]) -> list[int]:
    return [L for L in LOOKS if L <= max(weeks)]


def parse_arms(text: str) -> dict[int, Path]:
    out = {}
    for part in text.split(","):
        w, _, d = part.partition("=")
        out[int(w)] = Path(d).expanduser()
    return out


def census(arms: dict[int, Path]) -> dict:
    """Outcome-blind support: per week, which candidate lineups are the same, and each arm's validity. Reads no points."""
    out = {}
    for w, d in sorted(arms.items()):
        wr = week_rows(d)
        out[w] = {"same": wr["same"], "valid": wr["valid"], "void": wr["void"]}
        print(f"  W{w}: valid D1/D2 {wr['valid']['D1']}, FP {wr['valid']['FP']}; the same lineup: PROPS #1 = R0 #1 "
              f"{wr['same']['D1']}, MIXED = R0 PAIR {wr['same']['D2']}, FP #1 = R0 #1 {wr['same']['FP']}"
              + (f"; void {wr['void']}" if wr["void"] else ""))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--weeks", default=None); ap.add_argument("--arms", required=True)
    ap.add_argument("--ladders", type=Path, default=LADDERS); ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--census", action="store_true", help="outcome-blind: which lineups are the same; reads no points")
    a = ap.parse_args(argv)
    arms = parse_arms(a.arms)
    print(f"STUDY 60 RECORD  sha256 {sha256(Path(__file__))}  p1_record {sha256(HERE / 'p1_record.py')[:12]}")
    if a.census:
        print("OUTCOME-BLIND IDENTITY CENSUS (lineups only)")
        res = census(arms)
        if a.out:
            a.out.write_text(json.dumps({"census": res}, indent=1, default=str) + "\n")
        return 0
    if sha256(HERE / "p1_record.py") != P1_SHA256:
        raise SystemExit(f"STUDY 60 REFUSED: p1_record.py is not the frozen {P1_SHA256[:12]}")
    weeks = [int(x) for x in a.weeks.split(",")] if a.weeks else sorted(arms)
    if set(weeks) - set(arms):
        raise SystemExit(f"STUDY 60 REFUSED: no P3 arms dir for weeks {sorted(set(weeks) - set(arms))}")
    M = _load("moneygate_score"); P1 = _load("p1_record")
    rec = json.loads(M.receipt_path().read_text()) if M.receipt_path().is_file() else {}
    miss = [w for w in weeks if w not in rec.get("weeks", [])]
    if miss:
        raise SystemExit(f"STUDY 60 REFUSED: the reconcile receipt does not cover weeks {miss}")
    M.require_reconcile(sorted(rec["weeks"]))
    cfg = M.load_config()
    per_week = {}
    for w in weeks:
        wr = week_rows(arms[w])
        s = score_week(M, P1, M.load_week(cfg, w), wr, ladder_rows(w, a.ladders))
        per_week[w] = {"valid": wr["valid"], "same": wr["same"], "void": wr["void"], **s}
        tag = "BASELINE (in-sample)" if w < PROSPECTIVE_FROM else "PROSPECTIVE"
        print(f"  W{w} {tag}: z " + ", ".join(f"{r} {v:+.3f}" for r, v in s["z"].items())
              + " | " + ", ".join(f"{k} {v:+.3f}" for k, v in s["d"].items())
              + f" | same: D1 {wr['same']['D1']}, D2 {wr['same']['D2']}, FP {wr['same']['FP']}"
              + f" | Millionaire top 20%: " + ", ".join(r for r, h in s["proxy_top20"].items() if h)
              + (f" | missing names {sum(s['missing_names'].values())}" if sum(s["missing_names"].values()) else "")
              + (f" | void {wr['void']}" if wr["void"] else ""))
        for h in s["ladder"]:
            if h.get("no_field"):
                print(f"      {h['contest_id']} {h['role']} line {h['line']}: no field")
            else:
                print(f"      {h['contest_id']} {h['role']:3s} line {h['line']:>6} of {h['size']:>7}: "
                      + ", ".join(f"{r} {q}{' HIT' if h['hit'][r] else ''}" for r, q in h["position"].items()))
    pro = [w for w in weeks if w >= PROSPECTIVE_FROM]
    out = {"weeks": weeks, "per_week": per_week, "looks": {}}
    print(f"STUDY 60 (prereg 2026-10-08): prospective from W{PROSPECTIVE_FROM}; looks at W{', W'.join(map(str, LOOKS))}; "
          f"the two-sided 90% t interval (each side a one-sided 95% bound); DEAD LEVER above {DEAD_SHARE:.0%} the same")
    for k, what in DECISIONS.items():
        vals = [(w, per_week[w]["d"][k], per_week[w]["same"][k]) for w in pro if per_week[w]["valid"][k]]
        print(f"  {k} ({what}): " + (", ".join(f"W{w} {v:+.3f}{' (same)' if s else ''}" for w, v, s in vals) or "no valid prospective week"))
        for L in looks_due(weeks):
            upto = [(v, s) for w, v, s in vals if w <= L]
            r = read_look([v for v, _ in upto], [s for _, s in upto], what)
            out["looks"].setdefault(k, {})[L] = r
            print(f"    LOOK W{L}: n {r['n']}" + (f", mean {r['mean']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}] (two-sided 90%)"
                                                if "mean" in r else "") + f" -> {r['reading']}")
    if a.out:
        a.out.write_text(json.dumps(out, indent=1, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
