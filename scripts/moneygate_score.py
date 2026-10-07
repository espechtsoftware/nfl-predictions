#!/usr/bin/env python3
"""Week-5 money gate, SCORING half (reports/2026-10-04-week5-money-gate-design.md §4-§6 and Addendum 1).

Order of use (each step refuses to run before the previous one passed):
  1. fetch      pull each week's real fields and DK player points into a PRIVATE cache (~/private/moneygate/data):
                W1-3 nfl_raw.contest_entries + nfl_raw.contest_ownership (SELECT only), W4 the 26 local standings files.
  2. reconcile  THE KNOWN-ANSWER GATE (reviewer, CLAUDE.md rule 1). A0, the books actually entered, is scored through the
                SAME code path the arms use (names -> DK points, field placement, tie handling at the lines, ladders,
                tickets at face) and must reproduce the settled results EXACTLY: every entry's points, rank and payout,
                every contest's cashes, and each week's total winnings (cash + tickets at face) against the settled
                entry history. Any mismatch exits 3 and names the contests. Dollars go to ~/private/moneygate only.
  3. score      the arms A1-A4 (design §3) against the real fields and ladders: return multiples (as is and excluding
                each arm's single largest payout), cashes and ticket value by contest class, entry finish percentiles,
                the book percentile and per-contest sign test against M2, the cluster bootstrap, the cluster sign test,
                the permutation false-qualifier rate, and the §5 + Addendum-1 decision rule. Refuses unless a PASS
                reconcile receipt exists for THIS scorer file (sha256) and the same cached data.
  smoke         the full scoring path on Week 4's REAL books, contests and ladders with SYNTHETIC fields and points
                (no outcome is read): CLAUDE.md rule 1's outcome-blind full-path smoke.
  rollback      Addendum 1 point 5: the Week-5 trial's two Monday tests for an adopted arm X vs the A1 paper book.

Conventions (identical for every arm and for A0):
  * points are DraftKings' own per-player FPTS (contest sidebar), summed per lineup in integer hundredths;
  * an arm's entries are placed in the REAL field with every real entry of ours removed; rank = 1 + entries strictly
    above (field and the arm's own entries in that contest); tied entries share the prizes of the positions they occupy,
    split evenly (DraftKings' rule); a ticket counts at its face value from the contest's ladder;
  * a cash = a payout > 0; finish percentile = share of the field (ours removed) strictly below + half the ties, x 100;
  * return multiple = (cash + ticket face) / entry fees.

    python scripts/moneygate_score.py fetch --weeks 1,2,3,4
    python scripts/moneygate_score.py reconcile --weeks 1,2,3,4
    python scripts/moneygate_score.py score [--boot 10000] [--perms 2000]
    python scripts/moneygate_score.py smoke
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import date, timedelta
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

SCORER = Path(__file__).resolve()
CONFIG = Path(os.environ.get("MONEYGATE_CONFIG", Path.home() / "moneygate" / "weeks.json"))
BOOKS = Path(os.environ.get("MONEYGATE_BOOKS", Path.home() / "moneygate" / "books"))
PUBLIC = Path(os.environ.get("MONEYGATE_RESULTS", Path.home() / "moneygate" / "results"))
PRIVATE = Path(os.environ.get("MONEYGATE_PRIVATE", Path.home() / "private" / "moneygate"))
ARMS = ("A1", "A2", "A3", "A4")
ALTERNATIVES = ("A2", "A3", "A4")          # simplest first (§5.3: A2 before A3 before A4)
# each week's Sunday main slate, W1 2026-09-13 + 7 days a week (W1-4 exactly as before; 10-07: W5-18 for the Monday
# reads -- study 38, the monkeys, P3 -- which raised a KeyError for W5)
WEEK_DATES = {w: (date(2026, 9, 13) + timedelta(weeks=w - 1)).isoformat() for w in range(1, 19)}

# ---- the frozen rule (design §5 + Addendum 1 + Addendum 2). Changing any value here is a NEW, disclosed replay. ---
RULE = {
    "A1_weeks": (1, 2, 3, 4),
    "arms": {
        "A2": {"weeks": (1, 2, 3), "b_min": 2, "shown_not_independent": (4,)},   # Addendum 1.1: W4 contaminated
        "A3": {"weeks": (1, 2, 3), "b_min": 2, "shown_not_independent": (4,)},
        "A4": {"weeks": (1, 2, 3, 4), "b_min": 2, "b_weeks": (3, 4), "shown_not_independent": ()},   # A2.2: (b) on W3-4 (A4 = A1 in W1-2)
    },
    "sign_p": 0.20,                 # (c): two-sided, favouring X
    "m2_min": 50.0,                 # (d)
    # Addendum 2.1: (c) uses WEEKS as units with the exact sign test (no forced fail; with 3 or 2 units no arm can reach
    # p < 0.20 -- stated, not hidden). Clusters are reported, not used.
    "ci": (2.5, 97.5),              # the bootstrap range reported (95%)
    "rollback_m2": 50.0, "rollback_pct_gap": 5.0,   # Addendum 1.5
}


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def canon(name: str) -> str:
    return re.sub(r"\s+", " ", str(name)).strip()


def money(s) -> float:
    s = str(s).strip().replace("$", "").replace(",", "")
    return float(s) if s and s.lower() not in ("nan", "none") else 0.0


# =========================================================================================================== core
@dataclass
class Ladder:
    """Prize per finishing position (1-based), cash and ticket face separately."""
    cash: np.ndarray
    ticket: np.ndarray

    @property
    def paid(self) -> int:
        return len(self.cash)

    @classmethod
    def from_details(cls, d: dict) -> "Ladder":
        tiers = d.get("payoutSummary") or []
        if not tiers:
            raise ValueError("no payoutSummary")
        n = max(int(t["maxPosition"]) for t in tiers)
        cash, ticket = np.zeros(n), np.zeros(n)
        for t in tiers:
            lo, hi = int(t["minPosition"]), int(t["maxPosition"])
            kinds = set((t.get("tierPayoutDescriptions") or {}).keys())
            val = sum(float(p.get("value") or 0.0) * float(p.get("quantity") or 1) for p in t.get("payoutDescriptions") or [])
            if not kinds <= {"Cash", "Ticket"} or not kinds:
                raise ValueError(f"tier {lo}-{hi}: unknown prize kinds {kinds}")
            if kinds == {"Ticket"}:
                ticket[lo - 1:hi] += val
            elif kinds == {"Cash"}:
                cash[lo - 1:hi] += val
            else:
                raise ValueError(f"tier {lo}-{hi} mixes cash and tickets; value split unknown")
        return cls(cash, ticket)

    def split(self, rank: np.ndarray, ties: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(cash, ticket) per entry: the mean prize of positions rank .. rank+ties-1 (DraftKings' even tie split)."""
        cc = np.concatenate([[0.0], np.cumsum(self.cash)]); ct = np.concatenate([[0.0], np.cumsum(self.ticket)])
        lo = np.clip(rank - 1, 0, self.paid); hi = np.clip(rank - 1 + ties, 0, self.paid)
        return (cc[hi] - cc[lo]) / ties, (ct[hi] - ct[lo]) / ties


def place(own: np.ndarray, others_sorted: np.ndarray, ladder: Ladder) -> dict:
    """Place one book's entries (integer hundredths) in a contest. others_sorted = the field without ANY real entry of
    ours, ascending. Returns per-entry rank, ties, cash, ticket, payout, finish percentile."""
    own = np.asarray(own, dtype=np.int64)
    o = np.asarray(others_sorted, dtype=np.int64)
    lo_o, hi_o = np.searchsorted(o, own, "left"), np.searchsorted(o, own, "right")
    srt = np.sort(own)
    lo_s, hi_s = np.searchsorted(srt, own, "left"), np.searchsorted(srt, own, "right")
    rank = 1 + (len(o) - hi_o) + (len(own) - hi_s)
    ties = (hi_o - lo_o) + (hi_s - lo_s)
    cash, ticket = ladder.split(rank, ties)
    pct = 100.0 * (lo_o + 0.5 * (hi_o - lo_o)) / max(len(o), 1)
    return {"rank": rank, "ties": ties, "cash": cash, "ticket": ticket, "payout": cash + ticket, "pct": pct}


def lineup_points(names: list[str], fpts: dict[str, int], impute_missing: bool = False) -> tuple[int, list[str]]:
    miss = [n for n in names if n not in fpts]
    if miss and not impute_missing:
        raise KeyError(miss)
    return int(sum(fpts.get(n, 0) for n in names)), miss


def binom_two_sided(k: int, n: int) -> float:
    """Exact two-sided sign-test p (method of small p-values, p = 0.5)."""
    if n == 0:
        return 1.0
    pmf = [math.comb(n, i) / 2 ** n for i in range(n + 1)]
    return float(min(1.0, sum(p for p in pmf if p <= pmf[k] * (1 + 1e-12))))


def clusters(contest_rows: dict[str, set]) -> list[list[str]]:
    """Connected components of contests linked by any shared book row (rows given as lineup keys)."""
    parent = {c: c for c in contest_rows}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    owner: dict = {}
    for c in sorted(contest_rows):
        for r in contest_rows[c]:
            if r in owner:
                a, b = find(owner[r]), find(c)
                if a != b:
                    parent[max(a, b)] = min(a, b)
            else:
                owner[r] = c
    comp = defaultdict(list)
    for c in sorted(contest_rows):
        comp[find(c)].append(c)
    return sorted(comp.values())


def contest_class(dk_name: str) -> str:
    n = str(dk_name)
    if "Millionaire [$1M" in n:
        return "Millionaire"
    if "World Championship Qualifier" in n:
        return "FFWC qualifier"
    if "FFWC" in n:
        return "Satellite FFWC"
    if "MEGA" in n:
        return "Satellite MEGA"
    if "Wildcat" in n:
        return "Satellite Wildcat"
    if "$555" in n:
        return "Satellite $555"
    m = re.search(r"SUPERSat.*\[(\d+)x\]", n)
    if m:
        return f"SuperSat {m.group(1)}x"
    if "Satellite" in n:
        return "Satellite 1-ticket"
    return "Cash GPP"


# ======================================================================================================= loading
def load_config() -> dict:
    return json.loads(CONFIG.read_text())


@dataclass
class Week:
    week: int
    contests: list[dict]                      # routed contests.json (the arms' contests)
    details: dict
    fpts: dict[str, int]                      # canonical name -> hundredths
    ambiguous: set
    field: pd.DataFrame                       # contest_id, entry_id, rank, points (hundredths), names (tuple)
    ours: set                                 # real entry ids of ours (entry history)
    history: pd.DataFrame
    name_of: dict[str, str]                   # dk_player_id -> canonical display name (T-70 frame)
    others: dict[str, np.ndarray] = field(default_factory=dict)

    def others_sorted(self, cid: str) -> np.ndarray:
        if cid not in self.others:
            f = self.field[(self.field.contest_id == cid) & ~self.field.entry_id.isin(self.ours)]
            self.others[cid] = np.sort(f.points.to_numpy(np.int64))
        return self.others[cid]


def data_dir() -> Path:
    return PRIVATE / "data"


def fetch_week(cfg: dict, w: int) -> dict:
    """Write the private cache for week w: field (one row per entry) and DK player points. Returns its receipt."""
    e = cfg["weeks"][str(w)]
    out = data_dir(); out.mkdir(parents=True, exist_ok=True)
    hist = load_history(cfg, w)
    cids = sorted(set(hist.Contest_Key.astype(str)))
    if w in (1, 2, 3):
        from google.cloud import bigquery
        bq = bigquery.Client(project=cfg.get("bq_project", "nfl-predictions-503414"))
        jc = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("w", "INT64", w),
                                                       bigquery.ArrayQueryParameter("c", "STRING", cids)])
        f = bq.query("SELECT DISTINCT contest_id, entry_id, rank, points, players_key FROM `nfl_raw.contest_entries` "
                     "WHERE season = 2026 AND week = @w AND contest_id IN UNNEST(@c)", job_config=jc).to_dataframe()
        p = bq.query("SELECT DISTINCT contest_id, display_name, fpts FROM `nfl_raw.contest_ownership` "
                     "WHERE season = 2026 AND week = @w AND contest_id IN UNNEST(@c)", job_config=jc).to_dataframe()
        f = pd.DataFrame({"contest_id": f.contest_id.astype(str), "entry_id": f.entry_id.astype(str), "rank": f["rank"].astype(int),
                          "points": f.points.astype(float), "names": f.players_key.astype(str).map(lambda s: "|".join(canon(x) for x in s.split("|")))})
        p = pd.DataFrame({"contest_id": p.contest_id.astype(str), "name": p.display_name.map(canon), "fpts": p.fpts.astype(float)})
        src = "bigquery nfl_raw.contest_entries + nfl_raw.contest_ownership (SELECT DISTINCT)"
    else:
        f, p = read_standings_dir(Path(e["standings_dir"]), cids)
        src = f"standings files {e['standings_dir']}"
    if f.duplicated(["contest_id", "entry_id"]).any():
        raise SystemExit(f"W{w}: duplicate (contest, entry) rows in the field")
    fp, fq = out / f"w{w}_field.parquet", out / f"w{w}_fpts.parquet"
    f.to_parquet(fp, index=False); p.to_parquet(fq, index=False)
    rec = {"week": w, "source": src, "contests": cids, "field_rows": len(f), "field_sha256": sha256(fp), "fpts_sha256": sha256(fq)}
    (out / f"w{w}_receipt.json").write_text(json.dumps(rec, indent=1) + "\n")
    return rec


POS_RE = re.compile(r"(?:^|\s)(QB|RB|WR|TE|FLEX|DST)\s")


def parse_lineup(s: str) -> list[str]:
    s = " " + str(s).strip() + " "
    toks = list(POS_RE.finditer(s))
    return [canon(s[m.end():(toks[i + 1].start() if i + 1 < len(toks) else len(s))]) for i, m in enumerate(toks)]


def read_standings_dir(d: Path, cids: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    fr, pr = [], []
    for cid in cids:
        p = d / f"contest-standings-{cid}.csv"
        if p.is_file():
            raw = p.read_text(encoding="utf-8-sig")
        else:
            z = zipfile.ZipFile(d / f"contest-standings-{cid}.zip")
            raw = z.read([n for n in z.namelist() if n.endswith(".csv")][0]).decode("utf-8-sig")
        df = pd.read_csv(io.StringIO(raw), dtype=str, keep_default_na=False)
        ent = df[df["Rank"] != ""]
        fr.append(pd.DataFrame({"contest_id": cid, "entry_id": ent.EntryId.astype(str), "rank": ent.Rank.astype(int),
                                "points": ent.Points.astype(float), "names": ent.Lineup.map(lambda s: "|".join(sorted(parse_lineup(s))))}))
        side = df[df["Player"] != ""]
        pr.append(pd.DataFrame({"contest_id": cid, "name": side.Player.map(canon), "fpts": side.FPTS.astype(float)}))
    return pd.concat(fr, ignore_index=True), pd.concat(pr, ignore_index=True)


def load_history(cfg: dict, w: int) -> pd.DataFrame:
    if cfg.get("entry_history_sha256") and sha256(Path(cfg["entry_history"])) != cfg["entry_history_sha256"]:
        raise SystemExit(f"{cfg['entry_history']} sha256 != the pinned entry history")
    h = pd.read_csv(Path(cfg["entry_history"]), dtype=str)
    h = h[(h.Sport == "NFL") & (h.Contest_Date_EST.str[:10] == WEEK_DATES[w])].copy()
    h["Contest_Key"] = h.Contest_Key.astype(str); h["Entry_Key"] = h.Entry_Key.astype(str)
    return h


def fpts_table(p: pd.DataFrame) -> tuple[dict[str, int], set]:
    g = p.assign(h=(p.fpts * 100).round().astype(np.int64)).groupby("name").h.agg(lambda s: sorted(set(s)))
    amb = {n for n, v in g.items() if len(v) > 1}
    return {n: v[0] for n, v in g.items() if len(v) == 1}, amb


def load_week(cfg: dict, w: int) -> Week:
    e = cfg["weeks"][str(w)]
    d = data_dir()
    rec = json.loads((d / f"w{w}_receipt.json").read_text())
    for k, f in (("field_sha256", d / f"w{w}_field.parquet"), ("fpts_sha256", d / f"w{w}_fpts.parquet")):
        if sha256(f) != rec[k]:
            raise SystemExit(f"W{w}: {f} changed since fetch")
    f = pd.read_parquet(d / f"w{w}_field.parquet")
    f = f.assign(points=(f.points * 100).round().astype(np.int64), names=f.names.map(lambda s: tuple(s.split("|"))))
    fp, amb = fpts_table(pd.read_parquet(d / f"w{w}_fpts.parquet"))
    contests = json.loads((BOOKS / f"w{w}" / "contests.json").read_text())
    details = {str(k): v for k, v in json.loads(Path(e["details"]).read_text()).items()}
    for cid, path in (e.get("extra_details") or {}).items():
        details[str(cid)] = json.loads(Path(path).read_text())
    fr = pd.read_parquet(Path(e["t70_run"]) / "frame.parquet")
    name_of = {str(k).removesuffix(".0"): canon(v) for k, v in zip(fr.dk_player_id.astype(str), fr.display_name)}
    hist = load_history(cfg, w)
    return Week(w, contests, details, fp, amb, f, set(hist.Entry_Key), hist, name_of)


# ======================================================================================================== A0 gate
def reconcile_week(W: Week, exclude: dict[str, str]) -> tuple[dict, list[dict], list[str]]:
    """A0 through the arms' code path. Returns (public summary, private per-entry rows, mismatching contests)."""
    h = W.history
    rows, bad, excluded = [], [], {}
    for cid in sorted(set(h.Contest_Key)):
        hc = h[h.Contest_Key == cid]
        if cid in exclude:
            excluded[cid] = exclude[cid]; continue
        if cid not in W.details:
            excluded[cid] = "no payout ladder"; continue
        lad = Ladder.from_details(W.details[cid])
        fc = W.field[W.field.contest_id == cid]
        mine = fc[fc.entry_id.isin(set(hc.Entry_Key))]
        prob = []
        if len(mine) != len(hc):
            prob.append(f"{len(hc)} entries in the history, {len(mine)} found in the field")
        pts = []
        for names in mine.names:
            try:
                pts.append(lineup_points(list(names), W.fpts)[0])
            except KeyError as k:
                prob.append(f"no DK points for {k.args[0]} (ambiguous: {[n for n in k.args[0] if n in W.ambiguous]})"); pts.append(-1)
        pts = np.array(pts, dtype=np.int64)
        res = place(pts, W.others_sorted(cid), lad)
        fee = float(W.details[cid].get("fee") or W.details[cid].get("entryFee") or 0)
        hk = hc.set_index("Entry_Key")
        for i, (eid, dk_rank, dk_pts) in enumerate(zip(mine.entry_id, mine["rank"], mine.points)):
            hr = hk.loc[eid]
            want = money(hr.Winnings_Non_Ticket) + money(hr.Winnings_Ticket)
            r = {"week": W.week, "contest_id": cid, "entry_id": eid, "points_calc": pts[i] / 100, "points_dk": dk_pts / 100,
                 "points_hist": float(hr.Points), "rank_calc": int(res["rank"][i]), "rank_dk": int(dk_rank), "place_hist": int(hr.Place),
                 "payout_calc": round(float(res["payout"][i]), 2), "payout_hist": round(want, 2),
                 "cash_calc": round(float(res["cash"][i]), 2), "cash_hist": money(hr.Winnings_Non_Ticket),
                 "ticket_calc": round(float(res["ticket"][i]), 2), "ticket_hist": money(hr.Winnings_Ticket),
                 "fee_calc": fee, "fee_hist": money(hr.Entry_Fee), "ties": int(res["ties"][i])}
            r["match"] = (r["points_calc"] == r["points_dk"] and abs(r["points_dk"] - r["points_hist"]) < 0.005
                          and r["rank_calc"] == r["rank_dk"] == r["place_hist"] and abs(r["payout_calc"] - r["payout_hist"]) < 0.005
                          and abs(r["cash_calc"] - r["cash_hist"]) < 0.005 and abs(r["fee_calc"] - r["fee_hist"]) < 0.005)
            rows.append(r)
        cr = [r for r in rows if r["contest_id"] == cid]
        cash_c = sum(r["payout_calc"] > 0 for r in cr); cash_h = sum(r["payout_hist"] > 0 for r in cr)
        if cash_c != cash_h:
            prob.append(f"cashes {cash_c} computed vs {cash_h} settled")
        if not all(r["match"] for r in cr):
            prob.append(f"{sum(not r['match'] for r in cr)} of {len(cr)} entries mismatch (points/rank/payout/fee)")
        if prob:
            bad.append(f"W{W.week} contest {cid}: " + "; ".join(prob))
    calc = sum(r["payout_calc"] for r in rows)
    settled = sum(money(a) + money(b) for k, a, b in zip(h.Contest_Key, h.Winnings_Non_Ticket, h.Winnings_Ticket) if k not in excluded)
    if abs(calc - settled) >= 0.005:
        bad.append(f"W{W.week}: total winnings computed != settled (contests outside the exclusions)")
    n_entries = sum(1 for k in h.Contest_Key if k not in excluded)
    summary = {"week": W.week, "contests_reconciled": len(set(r["contest_id"] for r in rows)), "entries_in_history": int(len(h)),
               "entries_reconciled": len(rows), "entries_expected": n_entries,
               "entries_matching": sum(r["match"] for r in rows), "contests_with_mismatch": len(bad),
               "cashes_computed": sum(r["payout_calc"] > 0 for r in rows), "cashes_settled": sum(r["payout_hist"] > 0 for r in rows),
               "ties_involving_ours": sum(r["ties"] > 1 for r in rows),
               "total_winnings_exact": abs(calc - settled) < 0.005, "excluded": excluded,
               "exact_match": not bad and len(rows) == n_entries}
    return summary, rows, bad


# ======================================================================================================== scoring
@dataclass
class ContestResult:
    cid: str
    cls: str
    n: int
    fee: float
    payouts: np.ndarray
    tickets: np.ndarray
    pct: np.ndarray
    points: np.ndarray            # hundredths
    rows: frozenset               # lineup keys (frozenset of dk ids) dealt into this contest

    @property
    def win(self) -> float:
        return float(self.payouts.sum())

    @property
    def cashes(self) -> int:
        return int((self.payouts > 0).sum())


def score_book(W: Week, layout: dict, impute_missing: bool = False) -> tuple[dict[str, ContestResult], list[str]]:
    out, missing = {}, []
    for c in W.contests:
        cid = str(c["contest_id"])
        lus = layout["contests"][cid]["lineups"]
        if len(lus) != int(c["entries"]):
            raise SystemExit(f"W{W.week} {cid}: layout has {len(lus)} entries, contests.json {c['entries']}")
        pts = []
        for lu in lus:
            names = [W.name_of[x] for x in lu]
            p, m = lineup_points(names, W.fpts, impute_missing); pts.append(p); missing += m
        pts = np.array(pts, dtype=np.int64)
        res = place(pts, W.others_sorted(cid), Ladder.from_details(W.details[cid]))
        fee = float(W.details[cid].get("fee") or W.details[cid].get("entryFee"))
        out[cid] = ContestResult(cid, contest_class(W.details[cid]["name"]), len(lus), fee * len(lus), res["payout"], res["ticket"],
                                 res["pct"], pts, frozenset(frozenset(lu) for lu in lus))
    return out, sorted(set(missing))


def multiple(results: list[dict[str, ContestResult]], ex_largest: bool = False) -> float:
    win = sum(r.win for R in results for r in R.values()); fee = sum(r.fee for R in results for r in R.values())
    if ex_largest:
        win -= max((float(r.payouts.max()) for R in results for r in R.values() if r.n), default=0.0)
    return win / fee if fee else float("nan")


def mean_pct(R: dict[str, ContestResult]) -> float:
    return float(np.concatenate([r.pct for r in R.values()]).mean())


def m2_stats(cfg: dict, w: int):
    """(per-contest M2 DataFrame of cash_/sum_ columns, {cid: n}) from the pm-selection pickles."""
    import pickle
    m = cfg["weeks"][str(w)]["m2"]
    if m.get("sha256") and sha256(Path(m["path"])) != m["sha256"]:
        raise SystemExit(f"W{w}: M2 file {m['path']} sha256 != pin")
    d = pickle.load(open(m["path"], "rb"))
    d = d[int(m["key"])] if m.get("key") is not None else d
    return d["M2"], {str(c): int(n) for c, n in zip(d["cids"], d["n_c"])}


def m2_book_stat(R: dict[str, ContestResult], m2, m2n: dict) -> tuple[float, np.ndarray, list[str]]:
    """The arm's cashes and the M2 books' cashes over the contests where both deal the same number of entries."""
    same = [c for c in R if m2n.get(c) == R[c].n and f"cash_{c}" in m2.columns]
    skipped = [c for c in R if c not in same]
    return float(sum(R[c].cashes for c in same)), m2[[f"cash_{c}" for c in same]].sum(axis=1).to_numpy(float), skipped


def midrank_pct(x: float, dist: np.ndarray) -> float:
    return float(100 * ((dist < x).mean() + 0.5 * (dist == x).mean()))


def contest_sign_vs_m2(R: dict[str, ContestResult], m2, m2n: dict) -> dict:
    above = below = 0
    for c, r in R.items():
        if m2n.get(c) != r.n or f"sum_{c}" not in m2.columns:
            continue
        med = float(np.median(m2[f"sum_{c}"].to_numpy(float)))
        ours = r.points.sum() / 100
        above += ours > med; below += ours < med
    return {"above": int(above), "below": int(below), "p_two_sided": binom_two_sided(int(above), int(above + below)),
            "label": "per-contest, anti-conservative (contests share rows)"}


def week_clusters(Rs: list[dict[str, ContestResult]]) -> list[list[str]]:
    cids = list(Rs[0])
    return clusters({c: set().union(*(R[c].rows for R in Rs)) for c in cids})


def condition_c(X: dict[int, dict], A: dict[int, dict], weeks: tuple) -> dict:
    """Addendum 2.1: the exact sign test of X vs A1 with WEEKS as units (week stat = sum over its contests of the
    difference in mean entry finish percentile). Clusters per week are reported for information only."""
    units, n_cl = [], {}
    for w in weeks:
        n_cl[w] = len(week_clusters([X[w], A[w]]))
        units.append(sum(X[w][c].pct.mean() - A[w][c].pct.mean() for c in X[w]))
    pos = sum(u > 1e-12 for u in units); neg = sum(u < -1e-12 for u in units)
    p = binom_two_sided(pos, pos + neg)
    ok = pos > neg and p < RULE["sign_p"]
    min_p = binom_two_sided(len(units), len(units))
    cpos = sum(X[w][c].pct.mean() > A[w][c].pct.mean() for w in weeks for c in X[w])
    cneg = sum(X[w][c].pct.mean() < A[w][c].pct.mean() for w in weeks for c in X[w])
    return {"unit": "weeks", "units": len(units), "favour_X": int(pos), "favour_A1": int(neg), "p_two_sided": p,
            "min_attainable_p": min_p, "can_license": bool(min_p < RULE["sign_p"]), "clusters_per_week": n_cl, "pass": bool(ok),
            "contest_level": {"favour_X": int(cpos), "favour_A1": int(cneg), "p_two_sided": binom_two_sided(int(cpos), int(cpos + cneg)),
                              "label": "ANTI-CONSERVATIVE (contests share rows)"}}


def milly_cid(W: "Week") -> str | None:
    c = [str(x["contest_id"]) for x in W.contests if contest_class(W.details[str(x["contest_id"])]["name"]) == "Millionaire"]
    return c[0] if c else None


def row_level_line(weeks_data: dict, X: dict[int, dict], A: dict[int, dict], weeks: tuple, perms: int, seed: int) -> dict:
    """Addendum 2.3, DESCRIPTIVE ONLY (never a pass/fail): each distinct book row's finish percentile in that week's
    Millionaire field; mean over the symmetric difference of rows, X - A1; permutation of arm labels within week."""
    rng = np.random.default_rng(seed)
    per_w, pools = {}, []
    for w in weeks:
        W = weeks_data[w]; mc = milly_cid(W)
        if mc is None:
            continue
        field = W.others_sorted(mc)
        rx = set().union(*(r.rows for r in X[w].values())); ra = set().union(*(r.rows for r in A[w].values()))
        only_x, only_a = sorted(rx - ra, key=sorted), sorted(ra - rx, key=sorted)
        def pct(rows):
            pts = np.array([lineup_points([W.name_of[i] for i in r], W.fpts, True)[0] for r in rows], dtype=np.int64)
            lo, hi = np.searchsorted(field, pts, "left"), np.searchsorted(field, pts, "right")
            return 100.0 * (lo + 0.5 * (hi - lo)) / max(len(field), 1)
        px, pa = pct(only_x), pct(only_a)
        per_w[w] = {"rows_only_X": len(px), "rows_only_A1": len(pa), "shared_rows": len(rx & ra),
                    "mean_pct_X": float(px.mean()) if len(px) else None, "mean_pct_A1": float(pa.mean()) if len(pa) else None,
                    "diff": float(px.mean() - pa.mean()) if len(px) and len(pa) else None}
        if len(px) and len(pa):
            pools.append((px, pa))
    if not pools:
        return {"per_week": per_w, "diff": None, "label": "DESCRIPTIVE; no differing rows"}
    def stat(ps):
        return float(np.mean([a.mean() - b.mean() for a, b in ps]))
    obs = stat(pools); cnt = 0
    for _ in range(perms):
        sh = []
        for px, pa in pools:
            z = rng.permutation(np.concatenate([px, pa])); sh.append((z[:len(px)], z[len(px):]))
        cnt += abs(stat(sh)) >= abs(obs) - 1e-12
    return {"per_week": per_w, "diff_mean_over_weeks": obs, "perm_p_two_sided": (cnt + 1) / (perms + 1) if perms else None,
            "effective_n_rows": int(sum(len(a) + len(b) for a, b in pools)),
            "label": "DESCRIPTIVE ONLY (Addendum 2.3), not a pass/fail; ANTI-CONSERVATIVE (rows share players)"}


def evaluate_rule(res: dict[str, dict[int, dict]], m2: dict[int, tuple]) -> dict:
    """Design §5 + Addendum 1 on per-arm, per-week contest results. m2[w] = (M2 frame, n by contest)."""
    out = {"arms": {}}
    A = res["A1"]
    for x in ALTERNATIVES:
        rx = RULE["arms"][x]; ws = rx["weeks"]
        X = res[x]
        a_as = multiple([X[w] for w in ws]) > multiple([A[w] for w in ws])
        a_ex = multiple([X[w] for w in ws], True) > multiple([A[w] for w in ws], True)
        bws = rx.get("b_weeks", ws)
        wins = [w for w in bws if mean_pct(X[w]) > mean_pct(A[w])]
        b = len(wins) >= rx["b_min"]
        c = condition_c(X, A, ws)
        mx = [m2_book_stat(X[w], *m2[w]) for w in ws]
        m2pct = midrank_pct(sum(v[0] for v in mx), np.sum([v[1] for v in mx], axis=0))
        d = m2pct >= RULE["m2_min"]
        out["arms"][x] = {"weeks": list(ws), "a_as_is": bool(a_as), "a_ex_largest": bool(a_ex), "a": bool(a_as and a_ex),
                          "b_weeks_won": wins, "b": bool(b), "c": c, "d_m2_pct": m2pct, "d": bool(d),
                          "qualifies": bool(a_as and a_ex and b and c["pass"] and d)}
    q = [x for x in ALTERNATIVES if out["arms"][x]["qualifies"]]
    out["qualifiers"] = q
    out["recommend"] = q[0] if q else None   # Addendum 2.4: no default arm
    return out


def bootstrap(res: dict[str, dict[int, dict]], arms: tuple, weeks: tuple, n: int, seed: int, ex_largest: bool = False) -> np.ndarray:
    """Pooled multiple per resample for each arm (columns), resampling within-week clusters taken over the union of
    the given arms' rows. ex_largest: each arm's single largest payout (over the weeks) removed before resampling."""
    rng = np.random.default_rng(seed)
    wins = np.zeros((n, len(arms))); fees = np.zeros((n, len(arms)))
    drop = {}
    if ex_largest:
        for a in arms:
            best = max(((w, c, int(np.argmax(r.payouts)), float(r.payouts.max())) for w in weeks for c, r in res[a][w].items() if r.n),
                       key=lambda t: t[3])
            drop[a] = best
    for w in weeks:
        cl = week_clusters([res[a][w] for a in arms])
        W_ = np.zeros((len(cl), len(arms))); F_ = np.zeros((len(cl), len(arms)))
        for k, cs in enumerate(cl):
            for j, a in enumerate(arms):
                for c in cs:
                    r = res[a][w][c]
                    W_[k, j] += r.win - (drop[a][3] if ex_largest and drop[a][0] == w and drop[a][1] == c else 0.0)
                    F_[k, j] += r.fee
        idx = rng.integers(0, len(cl), size=(n, len(cl)))
        wins += W_[idx].sum(axis=1); fees += F_[idx].sum(axis=1)
    return wins / fees


def permute_week(res_w: dict[str, dict], rng, joint: list[list[str]] | None = None) -> dict[str, dict]:
    """Arm labels permuted within the week's joint clusters (union of all four arms' rows)."""
    out = {a: {} for a in ARMS}
    for cs in (joint if joint is not None else week_clusters([res_w[a] for a in ARMS])):
        perm = rng.permutation(len(ARMS))
        for j, a in enumerate(ARMS):
            src = ARMS[perm[j]]
            for c in cs:
                out[a][c] = res_w[src][c]
    return out


def false_qualifier_rate(res: dict[str, dict[int, dict]], m2: dict, n: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    hits = Counter()
    weeks = sorted(res["A1"])
    joint = {w: week_clusters([res[a][w] for a in ARMS]) for w in weeks}
    for _ in range(n):
        pr = {a: {} for a in ARMS}
        for w in weeks:
            pw = permute_week({a: res[a][w] for a in ARMS}, rng, joint[w])
            for a in ARMS:
                pr[a][w] = pw[a]
        ev = evaluate_rule(pr, m2)
        for x in ev["qualifiers"]:
            hits[x] += 1
        hits["any"] += bool(ev["qualifiers"])
    return {"permutations": n, **{k: hits[k] / n for k in (*ALTERNATIVES, "any")},
            "method": "arm labels permuted within each week's joint clusters (union of A1-A4 rows); the full rule applied"}


def summarize_arm(R_by_week: dict[int, dict], weeks: tuple) -> dict:
    per = {}
    for w in weeks:
        R = R_by_week[w]
        cls = defaultdict(lambda: {"entries": 0, "cashes": 0, "fee": 0.0, "win": 0.0, "ticket": 0.0})
        for r in R.values():
            k = cls[r.cls]; k["entries"] += r.n; k["cashes"] += r.cashes; k["fee"] += r.fee; k["win"] += r.win; k["ticket"] += float(r.tickets.sum())
        per[w] = {"multiple": multiple([R]), "multiple_ex_largest": multiple([R], True), "cashes": sum(r.cashes for r in R.values()),
                  "entries": sum(r.n for r in R.values()), "mean_finish_pct": mean_pct(R),
                  "by_class": {c: {"entries": v["entries"], "cashes": v["cashes"], "multiple": v["win"] / v["fee"] if v["fee"] else None,
                                   "ticket_multiple": v["ticket"] / v["fee"] if v["fee"] else None} for c, v in sorted(cls.items())}}
    return per


def pool_skill(cfg: dict, W: Week) -> float | None:
    """Spearman of projected vs realized lineup score over the A1 union pool (the design's 'pool skill' line)."""
    p = BOOKS / f"w{W.week}" / "A1" / "run1" / "candidates.parquet"
    if not p.is_file():
        return None
    cand = pd.read_parquet(p, columns=["players", "proj_sum", "source_run"])
    fr = pd.read_parquet(Path(cfg["weeks"][str(W.week)]["t70_run"]) / "frame.parquet")
    nm = {str(i): canon(n) for i, n in zip(fr.id.astype(str), fr.display_name)}
    real = cand.players.map(lambda s: sum(W.fpts.get(nm[i], np.nan) for i in s.split(",")))
    ok = real.notna()
    return float(pd.Series(cand.proj_sum[ok].to_numpy()).rank().corr(pd.Series(real[ok].to_numpy()).rank()))


def rollback_check(x: dict[str, ContestResult], a1_paper: dict[str, ContestResult], x_m2_pct: float) -> dict:
    """Addendum 1.5: end the trial (Week 6 returns to A1) if X's book is below the M2 median OR X's mean entry finish
    percentile is more than 5 points below the A1 paper book's on the same contests."""
    same = [c for c in x if c in a1_paper]
    gap = float(np.concatenate([x[c].pct for c in same]).mean() - np.concatenate([a1_paper[c].pct for c in same]).mean())
    i, ii = x_m2_pct < RULE["rollback_m2"], gap < -RULE["rollback_pct_gap"]
    return {"m2_pct": x_m2_pct, "finish_pct_gap_vs_A1_paper": gap, "test_i": bool(i), "test_ii": bool(ii),
            "end_trial": bool(i or ii)}


# ============================================================================================================ CLI
def receipt_path() -> Path:
    return PRIVATE / "reconcile_receipt.json"


def cmd_reconcile(cfg: dict, weeks: list[int]) -> int:
    PUBLIC.mkdir(parents=True, exist_ok=True); PRIVATE.mkdir(parents=True, exist_ok=True)
    summaries, rows, bad = [], [], []
    for w in weeks:
        W = load_week(cfg, w)
        s, r, b = reconcile_week(W, {str(k): v for k, v in (cfg["weeks"][str(w)].get("reconcile_exclude") or {}).items()})
        s["notes"] = cfg["weeks"][str(w)].get("reconcile_notes", [])
        summaries.append(s); rows += r; bad += b
    with open(PRIVATE / "reconcile_entries.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["week"]); wr.writeheader(); wr.writerows(rows)
    ok = not bad and all(s["exact_match"] for s in summaries)
    data = {str(w): json.loads((data_dir() / f"w{w}_receipt.json").read_text()) for w in weeks}
    rec = {"status": "PASS" if ok else "FAIL", "scorer_sha256": sha256(SCORER), "weeks": weeks, "data": data, "mismatches": bad}
    receipt_path().write_text(json.dumps(rec, indent=1) + "\n")
    (PUBLIC / "reconcile_summary.json").write_text(json.dumps({"status": rec["status"], "scorer_sha256": rec["scorer_sha256"],
                                                               "weeks": summaries, "mismatching_contests": len(bad)}, indent=1) + "\n")
    for s in summaries:
        print(f"W{s['week']}: {s['entries_matching']}/{s['entries_reconciled']} entries match (expected {s['entries_expected']}); "
              f"contests {s['contests_reconciled']}; cashes {s['cashes_computed']} computed / {s['cashes_settled']} settled; "
              f"total exact {s['total_winnings_exact']}; excluded {s['excluded']}; EXACT {s['exact_match']}")
    if not ok:
        print("RECONCILIATION FAILED -- scoring is blocked until explained:\n  " + "\n  ".join(bad), file=sys.stderr)
        return 3
    print("RECONCILIATION PASS: A0 reproduced exactly through the arms' scoring path")
    return 0


def require_reconcile(weeks: list[int]) -> None:
    if not receipt_path().is_file():
        raise SystemExit("SCORE REFUSED: no reconcile receipt (run `reconcile` first)")
    rec = json.loads(receipt_path().read_text())
    if rec["status"] != "PASS" or rec["scorer_sha256"] != sha256(SCORER) or sorted(rec["weeks"]) != sorted(weeks):
        raise SystemExit(f"SCORE REFUSED: reconcile receipt status {rec['status']}, scorer {rec['scorer_sha256'][:12]} vs {sha256(SCORER)[:12]}, weeks {rec['weeks']}")
    for w in weeks:
        cur = json.loads((data_dir() / f"w{w}_receipt.json").read_text())
        if cur != rec["data"][str(w)]:
            raise SystemExit(f"SCORE REFUSED: W{w} data changed since the reconcile")


def run_scoring(weeks_data: dict[int, Week], layouts: dict[str, dict[int, dict]], m2: dict, boot: int, perms: int, seed: int,
                impute_missing: bool = False, cfg: dict | None = None) -> tuple[dict, dict]:
    res: dict[str, dict[int, dict]] = {a: {} for a in ARMS}
    missing = {}
    for a in ARMS:
        for w, W in weeks_data.items():
            res[a][w], m = score_book(W, layouts[a][w], impute_missing)
            if m:
                missing[f"{a}-W{w}"] = m
    weeks = tuple(sorted(weeks_data))
    pub = {"rule": json.loads(json.dumps(RULE)), "missing_points_imputed_zero": missing, "arms": {}, "comparisons": {}}
    priv = {"arms": {}}
    lo, hi = RULE["ci"]
    for a in ARMS:
        pub["arms"][a] = {"per_week": summarize_arm(res[a], weeks)}
        priv["arms"][a] = {w: {"fees": sum(r.fee for r in res[a][w].values()), "winnings": sum(r.win for r in res[a][w].values()),
                               "tickets": float(sum(r.tickets.sum() for r in res[a][w].values())),
                               "largest_payout": max(float(r.payouts.max()) for r in res[a][w].values())} for w in weeks}
        for w in weeks:
            mm = m2_book_stat(res[a][w], *m2[w])
            pub["arms"][a]["per_week"][w]["m2_book_pct_cashes"] = midrank_pct(mm[0], mm[1])
            pub["arms"][a]["per_week"][w]["m2_contests_skipped_entry_count_differs"] = mm[2]
            pub["arms"][a]["per_week"][w]["sign_vs_m2"] = contest_sign_vs_m2(res[a][w], *m2[w])
            pub["arms"][a]["per_week"][w]["clusters"] = len(week_clusters([res[a][w]]))
        ws = RULE["A1_weeks"] if a in ("A1", "A4") else RULE["arms"][a]["weeks"]
        b = bootstrap(res, (a,), ws, boot, seed)[:, 0]
        be = bootstrap(res, (a,), ws, boot, seed, ex_largest=True)[:, 0]
        mx = [m2_book_stat(res[a][w], *m2[w]) for w in ws]
        pub["arms"][a]["pooled"] = {"weeks": list(ws), "multiple": multiple([res[a][w] for w in ws]),
                                    "multiple_range": [float(np.percentile(b, lo)), float(np.percentile(b, hi))],
                                    "multiple_ex_largest": multiple([res[a][w] for w in ws], True),
                                    "multiple_ex_largest_range": [float(np.percentile(be, lo)), float(np.percentile(be, hi))],
                                    "m2_book_pct_cashes": midrank_pct(sum(v[0] for v in mx), np.sum([v[1] for v in mx], axis=0))}
    A1p = pub["arms"]["A1"]["pooled"]
    q1 = ("No: on Weeks 1-4 the current system would have lost money." if A1p["multiple_range"][1] < 1.0 else
          "Yes." if A1p["multiple_range"][0] > 1.0 else f"Cannot tell from four weeks (point estimate {A1p['multiple']:.3f}x).")
    for x in ALTERNATIVES:
        ws = RULE["arms"][x]["weeks"]
        d = bootstrap(res, ("A1", x), ws, boot, seed)
        diff = d[:, 1] - d[:, 0]
        r = [float(np.percentile(diff, lo)), float(np.percentile(diff, hi))]
        pub["comparisons"][x] = {"weeks": list(ws), "multiple_diff_vs_A1": multiple([res[x][w] for w in ws]) - multiple([res["A1"][w] for w in ws]),
                                 "diff_range": r, "cannot_tell": bool(r[0] <= 0 <= r[1]),
                                 "clusters_per_week": {w: len(week_clusters([res["A1"][w], res[x][w]])) for w in ws},
                                 "not_independent_weeks_shown": {w: {"multiple": multiple([res[x][w]]), "A1_multiple": multiple([res["A1"][w]]),
                                                                     "mean_finish_pct": mean_pct(res[x][w]), "A1_mean_finish_pct": mean_pct(res["A1"][w])}
                                                                 for w in RULE["arms"][x]["shown_not_independent"] if w in weeks}}
    ev = evaluate_rule(res, m2)
    sg = [pub["arms"]["A1"]["per_week"][w]["sign_vs_m2"] for w in RULE["A1_weeks"] if w in weeks]
    up, dn = sum(x["above"] for x in sg), sum(x["below"] for x in sg)
    pub["decision"] = {"q1_would_A1_have_made_money": q1,
                       "q2_A1_vs_M2": {"book_pct_cashes": A1p["m2_book_pct_cashes"],
                                       "sign_vs_m2_by_week": {w: pub["arms"]["A1"]["per_week"][w]["sign_vs_m2"] for w in weeks},
                                       "sign_vs_m2_pooled": {"above": up, "below": dn, "p_two_sided": binom_two_sided(up, up + dn),
                                                             "label": "per-contest, anti-conservative (contests share rows)"}},
                       "q3": ev, "false_qualifier_rate": false_qualifier_rate(res, m2, perms, seed + 1) if perms else None,
                       "q3_answer": (f"{ev['recommend']} meets (a)-(d): a reversible Week-5 trial is possible (rollback: Addendum 1.5); the operator chooses"
                                     if ev["qualifiers"] else
                                     "No arm is statistically preferred (four weeks cannot license any arm: Addendum 2.1); the operator chooses, "
                                     "and any switch is a reversible trial with the written rollback trigger (Addendum 1.5)."),
                       "row_level_descriptive": {x: row_level_line(weeks_data, res[x], res["A1"], RULE["arms"][x]["weeks"], perms, seed + 7)
                                                 for x in ALTERNATIVES}}
    if cfg is not None:
        pub["pool_skill_spearman"] = {w: pool_skill(cfg, W) for w, W in weeks_data.items()}
    return pub, priv


def cmd_score(cfg: dict, weeks: list[int], boot: int, perms: int, seed: int, impute: bool) -> int:
    require_reconcile(weeks)
    data = {w: load_week(cfg, w) for w in weeks}
    layouts = {a: {w: json.loads((BOOKS / f"w{w}" / a / "layout.json").read_text()) for w in weeks} for a in ARMS}
    m2 = {w: m2_stats(cfg, w) for w in weeks}
    pub, priv = run_scoring(data, layouts, m2, boot, perms, seed, impute, cfg)
    pub["scorer_sha256"] = sha256(SCORER)
    pub["book_sha256"] = {a: {w: layouts[a][w]["book_sha256"] for w in weeks} for a in ARMS}
    PUBLIC.mkdir(parents=True, exist_ok=True); PRIVATE.mkdir(parents=True, exist_ok=True)
    (PUBLIC / "score.json").write_text(json.dumps(pub, indent=1, default=float) + "\n")
    (PRIVATE / "score_dollars.json").write_text(json.dumps(priv, indent=1, default=float) + "\n")
    print(json.dumps(pub["decision"], indent=1, default=float))
    return 0


# ------------------------------------------------------------------------------------------------------- smoke
def synthetic_week(w: int, contests: list[dict], details: dict, name_of: dict, layouts: dict, seed: int) -> Week:
    """A Week with FAKE points and FAKE fields over the real contests and ladders (outcome-blind)."""
    rng = np.random.default_rng(seed)
    names = sorted(set(name_of.values()))
    fp = {n: int(rng.integers(0, 3000)) for n in names}
    rows = []
    for c in contests:
        cid = str(c["contest_id"]); size = int(min(int(details[cid].get("max") or 100), 3000))
        pts = rng.normal(11000, 2500, size).round().astype(np.int64)
        rows += [{"contest_id": cid, "entry_id": f"{cid}-{i}", "rank": 0, "points": int(p), "names": ()} for i, p in enumerate(pts)]
    f = pd.DataFrame(rows)
    return Week(w, contests, details, fp, set(), f, set(), pd.DataFrame(), name_of)


def cmd_smoke(cfg: dict, week: int, boot: int, perms: int) -> int:
    e = cfg["weeks"][str(week)]
    contests = json.loads((BOOKS / f"w{week}" / "contests.json").read_text())
    details = {str(k): v for k, v in json.loads(Path(e["details"]).read_text()).items()}
    fr = pd.read_parquet(Path(e["t70_run"]) / "frame.parquet")
    name_of = {str(k).removesuffix(".0"): canon(v) for k, v in zip(fr.dk_player_id.astype(str), fr.display_name)}
    layouts = {a: {week: json.loads((BOOKS / f"w{week}" / a / "layout.json").read_text())} for a in ARMS}
    W = synthetic_week(week, contests, details, name_of, layouts, 7)
    # synthetic M2: 1000 fake books' per-contest cashes and sums
    rng = np.random.default_rng(11)
    m2df = pd.DataFrame({**{f"cash_{c['contest_id']}": rng.integers(0, 2, 1000) for c in contests},
                         **{f"sum_{c['contest_id']}": rng.normal(110 * int(c['entries']), 20, 1000) for c in contests}})
    m2n = {str(c["contest_id"]): int(c["entries"]) for c in contests}
    # four "weeks" = the same Week-4 books under four fake outcome draws, so the pooled rule runs end to end
    data = {k: synthetic_week(k, contests, details, name_of, layouts, 7 + k) for k in (1, 2, 3, 4)}
    lays = {a: {k: layouts[a][week] for k in (1, 2, 3, 4)} for a in ARMS}
    pub, priv = run_scoring(data, lays, {k: (m2df, m2n) for k in (1, 2, 3, 4)}, boot, perms, 5)
    out = PUBLIC.parent / "smoke"; out.mkdir(parents=True, exist_ok=True)
    (out / "smoke_score_SYNTHETIC.json").write_text(json.dumps(pub, indent=1, default=float) + "\n")
    n = sum(len(v["lineups"]) for v in layouts["A1"][week]["contests"].values())
    print(f"SMOKE OK (SYNTHETIC outcomes, real Week-{week} books/contests/ladders): {n} A1 entries placed per arm; "
          f"clusters A1 {pub['arms']['A1']['per_week'][1]['clusters']}; rule evaluated; permutations {perms}; written {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["fetch", "reconcile", "score", "smoke"])
    ap.add_argument("--weeks", default="1,2,3,4")
    ap.add_argument("--boot", type=int, default=10_000); ap.add_argument("--perms", type=int, default=2_000)
    ap.add_argument("--seed", type=int, default=20261009)
    ap.add_argument("--impute-missing-zero", action="store_true",
                    help="score a player absent from every contest sidebar as 0 (default: refuse, naming him)")
    a = ap.parse_args(argv)
    cfg = load_config()
    weeks = [int(w) for w in a.weeks.split(",") if w.strip()]
    if a.cmd == "fetch":
        for w in weeks:
            r = fetch_week(cfg, w)
            print(f"W{w}: {r['field_rows']} field rows in {len(r['contests'])} contests ({r['source']})")
        return 0
    if a.cmd == "reconcile":
        return cmd_reconcile(cfg, weeks)
    if a.cmd == "score":
        return cmd_score(cfg, weeks, a.boot, a.perms, a.seed, a.impute_missing_zero)
    return cmd_smoke(cfg, 4, a.boot, a.perms)


if __name__ == "__main__":
    raise SystemExit(main())
