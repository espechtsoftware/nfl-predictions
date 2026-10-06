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
    week's REAL contests.json (what enter_layout deals by rank afterwards)."""
    from . import enter_layout as EL
    c = json.loads(Path(plan).read_text()); c = c if isinstance(c, list) else c["contests"]
    contests = [{**{k_: v for k_, v in x.items() if k_ != "ranks"}, "track": "mean"}
                for x in c if str(x.get("track", "mean")) != "tail"]
    if not contests:
        raise ValueError(f"{plan}: no mean-track contests")
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
    if cell not in MIX_CELLS:
        raise ValueError(f"unknown mix cell in tag {t!r}")
    return cell


def shape_violations(ids, cell: str | None, pos: dict, team: dict, opp: dict, game: dict) -> list[str]:
    """What a roster breaks of its cell's shape (cell None = the house shape, A1's rules). Empty list = conforms."""
    rules_cell = cell or HOUSE_CELL
    if rules_cell not in MIX_CELLS:
        return [f"unknown cell {cell!r}"]
    _, r, qmax, pair = MIX_CELLS[rules_cell]
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
