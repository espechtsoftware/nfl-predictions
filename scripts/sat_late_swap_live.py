#!/usr/bin/env python3
"""Score-based satellite late swap, live (operator decision 2026-09-28: enters in Week 4; PREREG-L11 +11.1% tickets in
aggregate, paired 30-32 so not supported by the frozen rule -- the operator's call).

At about 2:40 CT, before the 3:05 lock, each entered book row's late-game players are re-chosen to maximize the row's
EXPECTED TICKETS: the sum over the contests it is entered in of P(final >= that contest's live line). The policy is
the lab's nfl2.sat_late_swap (pinned clone on PYTHONPATH). This script only PROPOSES swaps: it prints the ROW:OUT_DD:IN_DD
tokens for sunday_swap.sh (the LAST stdout line, bare, as late_inactive_swaps.py prints them: `scripts/sunday_swap.sh $(python
scripts/sat_late_swap_live.py ... | tail -1)`), which re-checks locks, the fresh DK feed and roster legality before writing.

Worlds: the T-70 run dir's two sidecar banks (players x worlds, frame-row aligned). An early-game player = his live DK
points (scripts/live_dk_points.py snapshot, ESPN) + his draw x the fraction of his game remaining; a late-game player =
his full draw.
Live line per contest: the Millionaire field's conditional final-score quantile at the contest's paid share (1 - paid /
entries, from the payout ladder), plus the contest type's strength offset (a satellite field is stronger than the
Millionaire's; Week-3 offsets below, refit each Monday). The field comes from the operator's manual Millionaire
"Export CSV" click (every entry's lineup). Without it the script refuses (exit 3): no swaps, the entries stand.
Late inactives: live, a fresh DK status snapshot (--snapshot, `sunday_live_relayout.sh`'s `id,status,game_start` CSV,
<= 30 min old, covering >= 90% of the frame) is required. A late-game player out by it (O/OUT/IR/D..., or absent from it,
as in late_inactive_swaps.py) scores 0 in every world and is never swapped in. Run it AFTER late_inactive_swaps.py (R4),
on the bundle R4's swaps re-published.
Only flat-payout contests (satellites: every paid place wins the same ticket) get a line. A row that also sits in a
top-heavy contest (the Millionaire, a cash qualifier) is left exactly as entered and receipted: there the last paid
place is a min-cash, and chasing it would trade the row's top-prize equity for a safe cash.

    PYTHONPATH=$CLONE/src:$PROD/src python scripts/sat_late_swap_live.py --bundle <published bundle dir> \\
        --run-dir <T-70 run dir> --details contest-details.json --live-points live.json --field-export milly.csv \\
        [--snapshot dk-status.csv] [--now ISO] [--out receipt.json]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_dk_points import norm  # noqa: E402

# Satellite line minus the Millionaire's final-score quantile at the same percentile, Week 3 (HANDOFF 0ea1ed74), with
# our own entries removed from the satellite fields (scripts/fit_late_swap_offsets.py, 2026-09-28: sat20 6.5 -> 5.8, the
# 11-entry sats we won had set the line at our own score; the rest unchanged). Refit each Monday; pass --offsets.
DEFAULT_OFFSETS = {"supersat2": 2.7, "supersat25hi": 0.6, "supersat25lo": 5.3, "wildcat": 3.5, "sat13mega": 3.3,
                   "sat13": 3.3, "sat20": 5.8, "ffwc18": 6.0, "ffwc": 23.2, "milly20": 0.0}
SLOTS = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
ACCEPTS = {"QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"}, "FLEX": {"RB", "WR", "TE"}, "DST": {"DST"}}
OUT = {"O", "OUT", "IR", "D", "DOUBTFUL", "INJURED RESERVE", "SUSPENDED", "PUP", "NA"}   # = late_inactive_swaps.py


def late_status_out(snapshot: pd.DataFrame, fr: pd.DataFrame, late: np.ndarray) -> tuple[set[str], float]:
    """Late-game frame ids that are out by the live DK status snapshot (id = dk_player_id, status), and the share of
    frame players the snapshot covers. As in late_inactive_swaps.py a player absent from the snapshot counts as out."""
    st = dict(zip(snapshot["id"].astype(str), snapshot["status"].fillna("").astype(str).str.upper()))
    dk = fr.dk_player_id.astype("Int64").astype(str).tolist()
    ids = fr.id.astype(str).tolist()
    cover = sum(d in st for d in dk) / max(1, len(dk))
    return {i for i, d, l in zip(ids, dk, late) if l and (d not in st or st[d] in OUT)}, cover
ESPN_TO_DK = {"WSH": "WAS", "LAR": "LA", "JAC": "JAX"}
LAYOUT_RE = re.compile(r"^(?P<name>[A-Za-z0-9_]+)-(?P<cid>\d+): (?P<n>\d+) entries .*?book rows (?P<rows>[\d,\-]+);")


def expand_rows(spec: str) -> list[int]:
    """'1,3,19-20' -> [1, 3, 19, 20] (the layout writes runs as ranges)."""
    out = []
    for part in spec.split(","):
        lo, _, hi = part.partition("-")
        out += list(range(int(lo), int(hi or lo) + 1))
    return out


class Refuse(RuntimeError):
    pass


def parse_layout(path: Path) -> list[dict]:
    out = []
    for line in path.read_text().splitlines():
        m = LAYOUT_RE.match(line.strip())
        if m:
            rows = expand_rows(m["rows"])
            if len(rows) != int(m["n"]):
                raise Refuse(f"layout line for {m['cid']}: {len(rows)} rows for {m['n']} entries")
            out.append({"name": m["name"], "cid": m["cid"], "entries": int(m["n"]), "rows": rows})
    if not out:
        raise Refuse(f"{path}: no contest lines parsed")
    n_lines = sum(1 for line in path.read_text().splitlines() if " entries = " in line)
    if n_lines != len(out):
        raise Refuse(f"{path}: parsed {len(out)} of {n_lines} contest lines")
    return out


def flat_payout(ladder: dict) -> bool | None:
    """True when every paid place pays the same (a satellite's tickets); False when it is top-heavy; None when the
    ladder has no positive value at all (unknown -- the caller refuses the run, never files it as top-heavy). The
    score-based swap maximizes P(final >= the last paid place), which is the right objective only for a flat ladder:
    for a top-heavy contest (the Millionaire, a cash-and-seat qualifier) it would steer rows toward a safe min-cash."""
    vals = {round(float(x.get("value", 0) or 0), 2) for t in ladder.get("payoutSummary", [])
            for x in t.get("payoutDescriptions", []) if float(x.get("value", 0) or 0) > 0}
    return None if not vals else len(vals) == 1


def paid_places(ladder: dict) -> tuple[int, int]:
    paid = 0
    for t in ladder.get("payoutSummary", []):
        if any(float(x.get("value", 0) or 0) > 0 for x in t.get("payoutDescriptions", [])):
            paid = max(paid, int(t["maxPosition"]))
    return paid, int(ladder.get("entries") or ladder.get("max") or 0)


def game_fraction_left(g: dict) -> float:
    st = str(g.get("status", ""))
    if st == "STATUS_FINAL":
        return 0.0
    if st in ("STATUS_SCHEDULED", "STATUS_PREGAME"):
        return 1.0
    try:
        period = int(g.get("period") or 1); mm, ss = str(g.get("clock") or "15:00").split(":")
        left = max(0, 4 - period) * 900 + int(mm) * 60 + int(ss)
    except (ValueError, TypeError):
        return 0.5
    return float(min(1.0, max(0.0, left / 3600.0)))


def conditional_worlds(fr: pd.DataFrame, bank: np.ndarray, live: dict, now: pd.Timestamp) -> tuple[np.ndarray, np.ndarray, dict]:
    """(cond players x worlds, late mask, receipt)."""
    starts = pd.to_datetime(fr.game_start, utc=True, errors="coerce")
    late = (starts > now).to_numpy()
    teams_of_game = {}
    for g in live["games"]:
        for t in g.get("teams", []):
            teams_of_game[ESPN_TO_DK.get(t, t)] = g
    pts = {(ESPN_TO_DK.get(p["team"], p["team"]), norm(p["name"])): float(p["dk_points"]) for p in live["players"] if not p.get("dst")}
    dst = {ESPN_TO_DK.get(p["team"], p["team"]): float(p["dk_points"]) for p in live["players"] if p.get("dst")}
    cond = bank.astype(np.float64).copy()
    matched = missing_game = 0
    for i, r in enumerate(fr.itertuples()):
        if late[i]:
            continue
        team = str(r.team); g = teams_of_game.get(team)
        if g is None:
            missing_game += 1; continue
        frac = game_fraction_left(g)
        if r.pos == "DST":
            live_pts = dst.get(team, 0.0)
        else:
            live_pts = pts.get((team, norm(str(r.display_name))), 0.0)
            matched += int((team, norm(str(r.display_name))) in pts)
        cond[i] = live_pts + bank[i] * frac
    return cond, late, {"early_players": int((~late).sum()), "early_matched_to_live": matched,
                        "early_teams_without_live_game": missing_game}


def field_lineups(export: Path, fr: pd.DataFrame, limit: int, seed: int) -> tuple[np.ndarray, float]:
    """Frame-row index arrays for up to `limit` entries of the Millionaire export (the DK standings CSV)."""
    from nfl_dfs.ingest.ownership_import import parse_lineup_slots   # the lineup-string splitter only: a mid-slate
    raw = pd.read_csv(export, dtype=str, keep_default_na=False)          # export is not a settled file
    lineups = raw.get("Lineup", pd.Series(dtype=str)).astype(str)
    lineups = lineups[lineups.str.strip() != ""]
    if len(lineups) > limit:
        lineups = lineups.sample(limit, random_state=seed)
    key = {(norm(str(n))): k for k, n in enumerate(fr.display_name.astype(str))}
    rows, hit, tot = [], 0, 0
    for s in lineups:
        items = parse_lineup_slots(s); r = []
        for it in items:
            tot += 1; k = key.get(norm(it["player"]))
            if k is not None:
                hit += 1; r.append(k)
        if len(r) == 9:
            rows.append(r)
    return np.array(rows, dtype=np.int32), hit / max(tot, 1)


class RowSkip(RuntimeError):
    pass


def pair_tokens(row_no: int, cells: list[str], late_before: list[str], late_after: list[str], dd: dict[str, str],
                pos: dict[str, str], salary: dict[str, float], cap: float = 50_000) -> list[str]:
    """Ordered ROW:OUT_DD:IN_DD tokens that turn the row's late cells into `late_after`.

    apply_swaps.py replaces one cell per token, in order, and validates the roster after EVERY token (a failed token is
    skipped and later tokens see the unchanged row), so the order must keep every intermediate lineup legal: no player
    twice, salary <= the cap. A re-seat of a kept late player (e.g. from FLEX to a WR cell so a newcomer can take FLEX)
    is two tokens: the newcomer into his cell first, then the kept player into the departing player's cell.
    Assignments that keep kept players in their own cells are preferred. A row with no legal order raises RowSkip."""
    open_cells = [cells.index(dd[p]) for p in late_before]
    choices = []
    for perm in permutations(late_after):
        if all(pos[p] in ACCEPTS[SLOTS[c]] for p, c in zip(perm, open_cells)):
            choices.append((sum(1 for p, c in zip(perm, open_cells) if dd[p] == cells[c]), perm))
    if not choices:
        raise RowSkip(f"row {row_no}: the chosen late players do not fit the open cells")
    for _stay, perm in sorted(choices, key=lambda x: -x[0]):
        pending = [(c, cells[c], dd[p]) for p, c in zip(perm, open_cells) if dd[p] != cells[c]]
        for order in permutations(pending):
            row = list(cells); ok = True; toks = []
            for c, old, new in order:
                if row[c] != old or new in row:
                    ok = False; break
                row[c] = new
                if sum(salary[x] for x in row[:9]) > cap:
                    ok = False; break
                toks.append(f"{row_no}:{old}:{new}")
            if ok:
                return toks
    raise RowSkip(f"row {row_no}: no order of one-cell replacements keeps every intermediate lineup legal")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bundle", type=Path, required=True); ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--details", type=Path, required=True); ap.add_argument("--live-points", type=Path, required=True)
    ap.add_argument("--field-export", type=Path); ap.add_argument("--snapshot", type=Path)
    ap.add_argument("--offsets", type=Path, help="JSON {contest type: points}; default: the Week-3 offsets")
    ap.add_argument("--now", default=None); ap.add_argument("--out", type=Path)
    ap.add_argument("--field-limit", type=int, default=20_000); ap.add_argument("--worlds", type=int, default=4_000)
    ap.add_argument("--max-live-age-min", type=float, default=15.0)
    ap.add_argument("--max-snapshot-age-min", type=float, default=30.0)
    ap.add_argument("--rehearsal", action="store_true", help="replays only: skip the live-snapshot age check (receipted)")
    a = ap.parse_args()
    from nfl2.sat_late_swap import late_world_quantiles, swap_entry
    now = pd.Timestamp(a.now) if a.now else pd.Timestamp.now(tz="UTC")
    now = now.tz_localize("UTC") if now.tzinfo is None else now
    receipt: dict = {"now": now.isoformat(), "inputs": {k: str(getattr(a, k)) for k in ("bundle", "run_dir", "details", "live_points",
                                                                                          "field_export", "snapshot")}}
    try:
        if a.field_export is None or not a.field_export.is_file():
            raise Refuse("no Millionaire field export: live lines cannot be computed; NO SWAPS (the entries stand)")
        live = json.loads(a.live_points.read_text())
        age = (now - pd.Timestamp(live["taken_utc"])).total_seconds() / 60
        receipt["rehearsal"] = bool(a.rehearsal)
        if not a.rehearsal and (age > a.max_live_age_min or age < -5):
            raise Refuse(f"live-points snapshot is {age:.1f} min old (limit {a.max_live_age_min}); take a fresh one")
        layout = parse_layout(a.bundle / "ENTER-layout.txt")
        keepers = next(a.bundle.glob("ENTER-all-rows-*-KEEPERS.csv"))
        upload = [r for r in csv.reader(keepers.open())][1:]
        fr = pd.read_parquet(a.run_dir / "frame.parquet").reset_index(drop=True)
        inc = np.load(a.run_dir / "incumbent_player_scores.npy"); hs = np.load(a.run_dir / "corrected_hsim_player_scores.npy")
        if inc.shape[0] != len(fr) or hs.shape[0] != len(fr):
            raise Refuse(f"sidecar banks ({inc.shape[0]}, {hs.shape[0]} rows) do not align with the frame ({len(fr)})")
        rng = np.random.default_rng(20261004)
        cols = np.concatenate([rng.choice(inc.shape[1], a.worlds // 2, replace=False),
                               inc.shape[1] + rng.choice(hs.shape[1], a.worlds - a.worlds // 2, replace=False)])
        bank = np.concatenate([inc, hs], axis=1)[:, cols]
        cond, late, crec = conditional_worlds(fr, bank, live, now)
        receipt["worlds"] = {"n": int(bank.shape[1]), **crec}
        # late inactives: a fresh DK status snapshot is required live; an out late player scores 0 in every world, so
        # keeping him is valued honestly and he is never swapped in
        if a.snapshot is None or not a.snapshot.is_file():
            if not a.rehearsal:
                raise Refuse("no DK status snapshot (--snapshot): late inactives unknown; NO SWAPS (the entries stand)")
            status_out, cover = set(), None
        else:
            if not a.rehearsal:
                sage = (datetime.now(timezone.utc).timestamp() - a.snapshot.stat().st_mtime) / 60
                if sage > a.max_snapshot_age_min:
                    raise Refuse(f"DK status snapshot is {sage:.1f} min old (limit {a.max_snapshot_age_min}); take a fresh one")
            status_out, cover = late_status_out(pd.read_csv(a.snapshot, dtype=str), fr, late)
            if cover < 0.9:
                raise Refuse(f"DK status snapshot covers {cover:.1%} of the frame's players; take a full one")
        for i in status_out:
            cond[fr.index[fr.id.astype(str) == i][0]] = 0.0
        receipt["late_out"] = {"snapshot_cover": None if cover is None else round(cover, 4),
                               "players": sorted(fr.set_index(fr.id.astype(str)).loc[sorted(status_out), "name"].astype(str))}
        # field and lines
        fidx, frate = field_lineups(a.field_export, fr, a.field_limit, 7)
        if frate < 0.95 or len(fidx) < 1000:
            raise Refuse(f"Millionaire export matched {frate:.1%} of player slots / {len(fidx)} full lineups to the frame")
        ftot = np.concatenate([cond[ch].sum(axis=1) for ch in np.array_split(fidx, max(1, len(fidx) // 2000))], axis=0)
        det = json.loads(a.details.read_text())
        offsets = json.loads(a.offsets.read_text()) if a.offsets else DEFAULT_OFFSETS
        lines = {}
        for c in layout:
            if c["cid"] not in det:
                raise Refuse(f"no payout ladder for contest {c['cid']} ({c['name']})")
            if flat_payout(det[c["cid"]]) is None:
                raise Refuse(f"contest {c['cid']} ({c['name']}): payout ladder has no positive value (unknown ladder)")
            paid, n = paid_places(det[c["cid"]])
            if paid <= 0 or n <= 0:
                raise Refuse(f"contest {c['cid']}: ladder has no paid places / entries")
            q = 1 - paid / n
            lines[c["cid"]] = float(np.quantile(ftot, q)) + float(offsets.get(c["name"], 0.0))
        receipt["field"] = {"entries": int(len(fidx)), "slot_match": round(frate, 4)}
        flat = {c["cid"]: flat_payout(det[c["cid"]]) for c in layout}
        receipt["lines"] = {c["cid"]: {"name": c["name"], "line": round(lines[c["cid"]], 2), "flat_payout": flat[c["cid"]]} for c in layout}
        # rows
        ids = fr.id.astype(str).tolist(); row_of = {i: k for k, i in enumerate(ids)}
        dd_to_id = dict(zip(fr.dk_draftable_id.astype("Int64").astype(str), ids))
        id_to_dd = {v: k for k, v in dd_to_id.items()}
        pos = dict(zip(ids, fr.pos.astype(str)))
        dd_salary = dict(zip(fr.dk_draftable_id.astype("Int64").astype(str), pd.to_numeric(fr.salary, errors="coerce").fillna(99_999)))
        rec = fr.assign(id=fr.id.astype(str))[["id", "name", "pos", "team", "opp", "game_id", "salary", "proj"]].to_dict("records")
        players = {r["id"]: r for r in rec}
        late_ids = {i for i, l in zip(ids, late) if l}
        late_pool = [players[i] for i in ids if i in late_ids and i not in status_out]
        worlds = late_world_quantiles(cond, [row_of[i] for i in late_ids], 30) if late_ids else []
        contests_of_row: dict[int, list[str]] = {}
        for c in layout:
            for r in c["rows"]:
                contests_of_row.setdefault(r, []).append(c["cid"])
        tokens, per_row, tickets_keep, tickets_new = [], [], 0.0, 0.0
        for rno, cells in enumerate(upload, start=1):
            cids = contests_of_row.get(rno)
            if not cids:
                continue
            if not all(flat[c] for c in cids):             # a row in a top-heavy contest stays as entered (receipted)
                per_row.append({"row": rno, "contests": cids, "swapped": False, "p_keep": None, "p_new": None,
                                "skipped": "in a top-heavy contest: " + ",".join(c for c in cids if not flat[c])})
                continue
            rid = [dd_to_id[c] for c in cells[:9]]
            slots = {pid: SLOTS[k] for k, pid in enumerate(rid)}
            res = swap_entry(rid, late_ids, players, cond, row_of, [lines[c] for c in cids], pos, {}, late_pool, worlds,
                             slots=slots)
            tickets_keep += res["p_keep"] or 0.0; tickets_new += res["p_new"] or 0.0
            entry = {"row": rno, "contests": cids, "p_keep": res["p_keep"], "p_new": res["p_new"], "swapped": res["swapped"]}
            if res["swapped"]:
                before = [i for i in rid if i in late_ids]
                after = [i for i in res["ids"] if i in late_ids]
                try:
                    toks = pair_tokens(rno, cells[:9], before, after, id_to_dd, pos, dd_salary)
                    tokens += toks; entry["tokens"] = toks
                except RowSkip as e:                          # the row stays as entered; receipted, never silent
                    entry.update({"swapped": False, "skipped": str(e)}); tickets_new += (res["p_keep"] - res["p_new"])
            per_row.append(entry)
        receipt.update({"rows": per_row, "rows_swapped": sum(r["swapped"] for r in per_row),
                        "rows_skipped": [r["row"] for r in per_row if r.get("skipped")],
                        "expected_tickets_keep": round(tickets_keep, 3), "expected_tickets_swap": round(tickets_new, 3),
                        "tokens": tokens})
        print(f"lines: " + ", ".join(f"{v['name']} {v['line']:.1f}" for v in receipt["lines"].values()))
        print(f"rows swapped {receipt['rows_swapped']} of {len(per_row)}; expected tickets {tickets_keep:.2f} -> {tickets_new:.2f}")
        if not tokens:
            print("NO SWAPS", file=sys.stderr)
        print(" ".join(tokens))            # last stdout line = bare tokens, as late_inactive_swaps.py: sunday_swap.sh $(... | tail -1)
        code = 0
    except Refuse as e:
        receipt["refused"] = str(e); print(f"REFUSED: {e}", file=sys.stderr); code = 3
    if a.out:
        a.out.write_text(json.dumps(receipt, indent=1, default=str))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
