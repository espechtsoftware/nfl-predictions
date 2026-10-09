"""Study 18's shape portfolio (MIX) for the live money path: the ONE definition of its cells, the row allocation, the
entry-weighted interleave and a per-cell shape check, shared by scripts/union_reselect.py (`--main mix`), the lever audit
and the Sunday replacement vetting (reviewer 2026-10-05: every consumer of the house shape must read each row's cell).

Cells, allocation and interleave are VERBATIM from nfl2 experiments/s18_stack_shapes.py @ 5869a1b (preregistration
production ff205145). The shape check counts exactly as the pinned lab's optimize() constrains
(nfl2.core.lineup._apply_stack_rules / _apply_game_shape @ f69598b):
  * stack mates = WR/TE on the QB's team; a bring-back = RB/WR/TE on the QB's opponent;
  * qb_game_max = non-DST players from the QB's game (the QB included);
  * a second-game pair = some game OTHER than the QB's with >= 1 non-DST player from EACH of its two teams;
  * always (the house): no RB on the team the lineup's DST faces, no two RBs of one team.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

# name -> (entry quota, StackRules kwargs, qb_game_max, second-game pair: None | "all")
MIX_CELLS: dict[str, tuple[float, dict, int | None, str | None]] = {
    "A1": (0.30, {"qb_stack_min": 2, "bring_back_min": 1}, None, None),                                   # the house shape
    "A2": (0.14, {"qb_stack_min": 2, "bring_back_min": 0, "bring_back_max": 0}, None, None),
    "B": (0.28, {"qb_stack_min": 1, "qb_stack_max": 1, "bring_back_min": 1}, 3, "all"),
    "C": (0.28, {"qb_stack_min": 1, "qb_stack_max": 1, "bring_back_min": 0, "bring_back_max": 0}, 3, None),
}
# Named portfolios (`union_reselect --mix-portfolio`). `ws` is study 18's WS arm, the one that PASSED (Addendum 129):
# the whole book in ONE cell -- QB + >= 1 WR/TE, bring-back optional, <= 3 from the QB's game, a second-game pair from
# any game -- solved row after row like s18's whole_book(WS) (no pass to another cell).
PORTFOLIOS: dict[str, dict[str, tuple[float, dict, int | None, str | None]]] = {
    "mix": MIX_CELLS,
    "ws": {"WS": (1.0, {"qb_stack_min": 1, "bring_back_min": 0}, 3, "all")},
}
ALL_CELLS = {name: cell for cells in PORTFOLIOS.values() for name, cell in cells.items()}
HOUSE_CELL = "A1"
TAG_PREFIX = "mix_"
LIVE_PIN = "f69598ba559202969cc91d9fbdee7f64996e97af"   # the lab re-pin whose optimize() holds second_game_pair / qb_game_max


def allocate(shares: list[float], k: int) -> list[int]:
    """Rows per cell: floor(share x k), the remainder to the largest fractional parts (ties: the earlier cell)."""
    raw = [s * k for s in shares]
    n = [int(np.floor(x)) for x in raw]
    for i in sorted(range(len(raw)), key=lambda i: (-(raw[i] - n[i]), i))[: k - sum(n)]:
        n[i] += 1
    return n


def interleave(counts: list[int], quotas: list[float], weights: list[int]) -> list[int]:
    """Rank r goes to the cell (with rows left) furthest below its quota of the entries dealt so far, weighting rank r by
    the layout's multiplicity w_r (ties: the earlier cell)."""
    taken, ent, seq = [0] * len(counts), [0.0] * len(counts), []
    for r in range(sum(counts)):
        w = weights[r] if r < len(weights) else 0
        tot = sum(ent) + w
        live = [j for j in range(len(counts)) if taken[j] < counts[j]]
        j = max(live, key=lambda j: (quotas[j] * tot - ent[j], -j))
        seq.append(j); taken[j] += 1; ent[j] += w
    return seq


def plan_weights(plan: Path, k: int, layout: str = "head") -> list[int]:
    """w_r = the plan's mean-track entries the layout deals to rank r, before the small-contest overlap limit, from the
    week's REAL contests.json (what enter_layout deals by rank afterwards). Contest pins ("ranks") are KEPT (O-35,
    2026-10-06): the operator's Rev2 pins his Milly super-satellites to rows 1-5, so rank 1 carries 10 entries, and a
    weight that ignored the pins would allocate the cells against the wrong entry shares. Only head / spread honour
    pins; a pinned plan under another layout refuses (enter_layout would ignore the pins)."""
    from . import enter_layout as EL
    c = json.loads(Path(plan).read_text()); c = c if isinstance(c, list) else c["contests"]
    contests = [{**x, "track": "mean"} for x in c if str(x.get("track", "mean")) != "tail"]
    if not contests:
        raise ValueError(f"{plan}: no mean-track contests")
    if layout not in ("head", "spread") and any("ranks" in x for x in contests):
        raise ValueError(f"{plan}: pinned contests need the head or spread layout (got {layout!r}; O-35)")
    w = [0] * k
    for rr in EL.assign_ranks(contests, layout):
        for r in rr:
            if r < k:
                w[r] += 1
    return w


def cell_of_tag(tag: object) -> str | None:
    """The cell a candidate tag names ('mix_B' -> 'B'); None for any other tag (house rows)."""
    t = str(tag)
    if not t.startswith(TAG_PREFIX):
        return None
    cell = t[len(TAG_PREFIX):]
    if cell not in ALL_CELLS:
        raise ValueError(f"unknown mix cell in tag {t!r}")
    return cell


TOP_WR_RULE_CELLS = ("A1", "B")      # study 71: the MIX cells whose rules REQUIRE a bring-back (bring_back_min >= 1)


def top_receivers(players) -> dict[str, str]:
    """Study 71 (the same definition as study 70's top_wr, nfl2 experiments/s70_topwr.py d622a211): each team's
    highest-salaried WR among `players` -- the solve's BUILDABLE pool, an iterable of dicts with id, pos, team, salary
    and proj -- ties: the higher proj, then the id; a missing or non-numeric salary counts as 0. Returns team -> id."""
    best: dict[str, tuple] = {}
    for p in players:
        if str(p.get("pos")) != "WR":
            continue
        try:
            sal = float(p.get("salary"))
        except (TypeError, ValueError):
            sal = 0.0
        sal = 0.0 if sal != sal else sal                     # NaN -> 0, as study 70's fillna(0.0)
        try:
            proj = float(p.get("proj"))
        except (TypeError, ValueError):
            proj = 0.0
        proj = 0.0 if proj != proj else proj
        key = (-sal, -proj, str(p.get("id")))
        t = str(p.get("team"))
        if t not in best or key < best[t][0]:
            best[t] = (key, str(p.get("id")))
    return {t: v[1] for t, v in sorted(best.items())}


def bring_back_top_wr_rule(receipt: dict, vet_receipt: dict | None = None
                           ) -> tuple[dict[str, str], tuple[str, ...], set[frozenset], set[frozenset] | None]:
    """Study 71's ONE reader (production's amendment d, 10-08): the union receipt's bring_back_top_wr block(s) ->
    (top_wr: team -> frame id, cells, exempt_rows: the rows built WITHOUT the floor, each a frozenset of frame ids).
    The book's own block sits at config.union.mix.mix.bring_back_top_wr; an ownership-term main adds the term call's block
    at config.union.mix.mix.with_term.bring_back_top_wr (its fallbacks are exempt too). vet_receipt (vet_replace_v4's
    replace.json) adds its house-fallback rows (bring_back_top_wr_exempt), A1 WITHOUT the rule. The 4th value, required_rows,
    is None without a study-71b cap (the rule binds every designated row but the exempt ones) and, with a cap, the
    identities of the rows built UNDER the floor (the rule binds ONLY those). Off / absent = ({}, (), set(), None)."""
    union = ((receipt or {}).get("config") or {}).get("union") or {}
    mix = (union.get("mix") or {}).get("mix") or {}
    blocks = [b for b in (mix.get("bring_back_top_wr"), (mix.get("with_term") or {}).get("bring_back_top_wr")) if b]
    if not blocks:
        return {}, (), set(), None
    top = {str(t): str(v["id"]) for t, v in (blocks[0].get("top_wr") or {}).items()}
    cells = tuple(str(c) for c in blocks[0].get("cells") or ())
    exempt = {frozenset(str(i) for i in f["row"]) for b in blocks for f in (b.get("fallbacks") or [])}
    exempt |= {frozenset(str(i) for i in f["row"]) for f in ((vet_receipt or {}).get("bring_back_top_wr_exempt") or [])}
    capped = [b for b in blocks if b.get("rows_cap") is not None]
    required = {frozenset(str(i) for i in f["row"]) for b in capped for f in (b.get("floored_rows") or [])} if capped else None
    return top, cells, exempt, required


def rule_applies(row, exempt: set, required: set | None) -> bool:
    """Study 71 / 71b: whether a designated-cell row is bound by the top-WR rule -- without a cap, every row but the exempt
    ones; with a cap, ONLY the rows built under the floor (`required`)."""
    r = frozenset(str(i) for i in row)
    return (r in required) if required is not None else (r not in exempt)


# Study 73 (84's rule, 10-08; the operator: "for each of the five highest projected games ... requiring the quarterback and his
# top pass catcher"): the first G BOOK solves of the QB+1 cells, in build order, each carry ONE game's (QB, top pass catcher)
# pair through the pinned optimize()'s interaction floor. union_reselect --mix-top-game-qb1 G (default 0 = off).
TOP_GAME_CELLS = ("B", "C")


def top_game_pairs(pool, game_total: dict, team_itt: dict, g: int) -> list[dict]:
    """84's games and pairs (nfl2 experiments/s73_topg_qb1.py game_order / game_pairs @ b402cdd, parity-tested against their
    verbatim text) on the union's buildable pool (player dicts: id, name, pos, team, game_id, salary, proj -- proj is the
    projection the union solves on, the term block's term never included). The pool QBs' games by game_total descending,
    ties by game_id ascending; the top g. Game k's side: its teams with a pool QB, first by (-the team's implied total,
    -the side's top pool-QB proj, team code); its QB: that side's pool QB first by (-proj, id); his top pass catcher: the
    team's pool WR / TE first by (-proj, -salary, id). A game whose side has no pass catcher keeps pair None and is
    SKIPPED: it never takes a solve (no backfill). game_total: game_id -> total; team_itt: team -> its implied total.
    ValueError on a ranked game without a total or a side without an implied total."""
    qbs = [p for p in pool if p["pos"] == "QB"]
    games = sorted({str(p["game_id"]) for p in qbs})
    for gm in games:
        t = game_total.get(gm)
        if t is None or not np.isfinite(float(t)):
            raise ValueError(f"game {gm} has no game_total")
    out = []
    for k, gm in enumerate(sorted(games, key=lambda x: (-float(game_total[x]), x))[:g], start=1):
        sides = []
        for team in sorted({str(p["team"]) for p in qbs if str(p["game_id"]) == gm}):
            v = team_itt.get(team)
            if v is None or not np.isfinite(float(v)):
                raise ValueError(f"team {team} has no implied_team_total")
            top = min((p for p in qbs if str(p["game_id"]) == gm and str(p["team"]) == team),
                      key=lambda p: (-float(p["proj"]), str(p["id"])))
            sides.append(((-float(v), -float(top["proj"]), team), top))
        (itt_neg, _, team), qb = min(sides, key=lambda s: s[0])
        pcs = [p for p in pool if p["pos"] in ("WR", "TE") and str(p["team"]) == team]
        pc = min(pcs, key=lambda p: (-float(p["proj"]), -float(p.get("salary") or 0), str(p["id"]))) if pcs else None
        out.append({"k": k, "game_id": gm, "game_total": float(game_total[gm]), "qb": qb, "pc": pc, "itt": -itt_neg,
                    "pair": (str(qb["id"]), str(pc["id"])) if pc is not None else None})
    return out


def top_game_qb1_rows(receipt: dict) -> dict[frozenset, tuple[str, str]]:
    """Study 73's ONE reader: the union receipt's top_game_qb1 block(s) (config.union.mix.mix.top_game_qb1 and an
    ownership-term main's with_term block) -> {forced row identity: (QB_k, PC_k)}. Off / absent = {}. A dropped game's
    plain row is not forced, and a replacement row is never one."""
    union = ((receipt or {}).get("config") or {}).get("union") or {}
    mix = (union.get("mix") or {}).get("mix") or {}
    out: dict[frozenset, tuple[str, str]] = {}
    for b in (mix.get("top_game_qb1"), (mix.get("with_term") or {}).get("top_game_qb1")):
        if not b:
            continue
        pair = {int(g["k"]): (str(g["qb"]["id"]), str(g["pc"]["id"])) for g in b.get("games") or [] if g.get("pc")}
        for f in b.get("forced") or []:
            out[frozenset(str(i) for i in f["row"])] = pair[int(f["k"])]
    return out


def top_game_violations(ids, forced: dict) -> list[str]:
    """Study 73: a row whose identity is a forced row must hold its game's QB and pass catcher (the floor's output);
    every other row: nothing (a vet replacement is never bound)."""
    have = {str(i) for i in ids}
    pair = forced.get(frozenset(have))
    if not pair:
        return []
    miss = [x for x in pair if x not in have]
    return [f"top-game pair missing: {', '.join(miss)} (the forced pair {pair[0]} + {pair[1]})"] if miss else []


def shape_violations(ids, cell: str | None, pos: dict, team: dict, opp: dict, game: dict, *,
                     top_wr: dict | None = None, top_wr_cells=()) -> list[str]:
    """What a roster breaks of its cell's shape (cell None = the house shape, A1's rules). Empty list = conforms.
    Study 71 (default off): when `cell` is one of `top_wr_cells` and `top_wr` (team -> frame id) names a top receiver for
    the QB's opponent, the row must hold him. A caller passes top_wr MINUS its own excluded players (a top WR ruled out
    later removes the rule for that opponent; his team's next WR is never promoted) and exempts the receipt's fallback
    rows by identity. The house shape (cell None) never carries the rule."""
    rules_cell = cell or HOUSE_CELL
    if rules_cell not in ALL_CELLS:
        return [f"unknown cell {cell!r}"]
    _, r, qmax, pair = ALL_CELLS[rules_cell]
    ids = list(ids)
    qbs = [i for i in ids if pos.get(i) == "QB"]
    if len(qbs) != 1:
        return [f"{len(qbs)} QBs"]
    q = qbs[0]; qt, qo = team.get(q), opp.get(q)
    v: list[str] = []
    mates = sum(1 for i in ids if pos.get(i) in ("WR", "TE") and team.get(i) == qt)
    bring = sum(1 for i in ids if pos.get(i) in ("RB", "WR", "TE") and team.get(i) == qo)
    if mates < r.get("qb_stack_min", 0):
        v.append(f"{mates} stack mates < {r['qb_stack_min']}")
    if r.get("qb_stack_max") is not None and mates > r["qb_stack_max"]:
        v.append(f"{mates} stack mates > {r['qb_stack_max']}")
    if bring < r.get("bring_back_min", 0):
        v.append(f"{bring} bring-backs < {r['bring_back_min']}")
    if r.get("bring_back_max") is not None and bring > r["bring_back_max"]:
        v.append(f"{bring} bring-backs > {r['bring_back_max']}")
    if cell is not None and cell in tuple(top_wr_cells or ()) and top_wr:
        w = top_wr.get(qo)
        if w is not None and w not in set(ids):
            v.append(f"top-WR bring-back missing: {qo}'s top receiver {w}")
    skill = [i for i in ids if pos.get(i) != "DST"]
    unmapped = [i for i in skill if game.get(i) in (None, "", "None", "nan")]
    if unmapped:                         # a missing game id could fake a pair or dodge the QB-game cap: fail, never guess
        return v + [f"players without a game id: {unmapped[:3]}"]
    qg = game.get(q)
    if qmax is not None and sum(1 for i in skill if game.get(i) == qg) > qmax:
        v.append(f"{sum(1 for i in skill if game.get(i) == qg)} players from the QB's game > {qmax}")
    if pair == "all":
        teams_by_game: dict = {}
        for i in skill:
            if game.get(i) != qg:
                teams_by_game.setdefault(game.get(i), set()).add(team.get(i))
        if not any(len(t) == 2 for t in teams_by_game.values()):
            v.append("no second-game pair")
    dst = [i for i in ids if pos.get(i) == "DST"]
    rbs = [i for i in ids if pos.get(i) == "RB"]
    if any(team.get(rb) == opp.get(d) for rb in rbs for d in dst):     # the lab: an RB of the team the DST faces
        v.append("an RB faces the lineup's DST")
    if len({team.get(rb) for rb in rbs}) < len(rbs):
        v.append("two RBs of one team")
    return v


def book_cells(book_sets: list[frozenset], tagged: list[tuple[frozenset, str]], k_main: int) -> list[str | None]:
    """Each book row's cell from the run's candidates (roster -> its first mix_<cell> tag; other tags give None). The first
    k_main positions are the MIX main block: every one of them must resolve, or ValueError names the 1-based positions --
    a mix book is never vetted as house by default (reviewer 2026-10-05). Positions past k_main (the tail sleeve) may be
    None: they keep the house rules, as before."""
    cell_of_set: dict[frozenset, str] = {}
    for roster, tag in tagged:
        cell = cell_of_tag(tag)
        if cell is not None:
            cell_of_set.setdefault(roster, cell)
    cells = [cell_of_set.get(r) for r in book_sets]
    missing = [p + 1 for p in range(min(k_main, len(cells))) if cells[p] is None]
    if missing:
        raise ValueError(f"MIX ROWS WITHOUT A CELL TAG: main-block positions {missing[:12]}"
                         + (f" (+{len(missing) - 12} more)" if len(missing) > 12 else "") + " -- refusing to vet a mix book as house")
    return cells


# ---------------------------------------------------------------- study 46: the half-and-half book (operator 10-06)
# The regulars' tiers for an RS block of n rows inside a 26-row book, VERBATIM from the lab's frozen
# experiments/s46_half_half.py (lab ee6624d, sha256 30647fef...): (block QB cap, QB tiers, block non-QB cap, non-QB tiers).
# A tier (r, m): once m players of the group hold >= r rows OF THE RS BLOCK, every other player of the group at r - 1
# RS rows is banned. The block caps are never relaxed.
RS_BOOK_ROWS = 26
RS_TIERS = {13: (3, ((3, 1), (2, 3)), 7, ((7, 1), (6, 2), (5, 4), (4, 7), (3, 12), (2, 22))),
            9: (3, ((3, 1), (2, 2)), 6, ((6, 1), (5, 1), (4, 3), (3, 7), (2, 15))),
            17: (4, ((4, 1), (3, 2), (2, 4)), 9, ((9, 1), (8, 2), (7, 3), (6, 4), (5, 7), (4, 11), (3, 17), (2, 27)))}


def tier_bans(count, group: set, tiers) -> set:
    """Study 37 verbatim: for each tier (r, m), once m players of `group` hold >= r rows, ban every other player of the
    group at r - 1."""
    bans: set = set()
    for r, m in tiers:
        if sum(1 for p in group if count.get(p, 0) >= r) >= m:
            bans |= {p for p in group if count.get(p, 0) == r - 1}
    return bans


def relaxations(qb_tiers: tuple, nq_tiers: tuple):
    """Study 37 verbatim (the loud fallback's order): all tiers first; then the non-QB tiers dropped from the lowest r
    upward, one more each time; then (all non-QB tiers dropped) the QB tiers from the lowest r upward. Yields (qb tiers
    kept, non-QB tiers kept, non-QB dropped, QB dropped)."""
    nq, qt = sorted(nq_tiers), sorted(qb_tiers)
    for d in range(len(nq) + 1):
        yield tuple(qt), tuple(nq[d:]), d, 0
    for d in range(1, len(qt) + 1):
        yield tuple(qt[d:]), (), len(nq), d


def block_positions(k_book: int, n_rs: int) -> tuple[list[int], list[int]]:
    """Study 46's rule 4 verbatim: (the RS block's book positions, the live block's). The smaller block (RS on a tie) at
    floor((2i + 1) k / (2n)); the other block the remaining positions in order."""
    n_live = k_book - n_rs
    if not 0 <= n_rs <= k_book:
        raise ValueError(f"n_rs {n_rs} outside 0..{k_book}")
    if n_rs == 0 or n_live == 0:
        return (list(range(k_book)), []) if n_live == 0 else ([], list(range(k_book)))
    minor = min(n_rs, n_live)
    mpos = [((2 * i + 1) * k_book) // (2 * minor) for i in range(minor)]
    rest = [p for p in range(k_book) if p not in set(mpos)]
    return (mpos, rest) if n_rs <= n_live else (rest, mpos)
