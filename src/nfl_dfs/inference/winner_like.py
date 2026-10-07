"""Study 48's winner-likeness score on the live book, and study 48b's order (the operator 10-06/07: "would there be any
benefit to loading them into Neo4j and looking at each of them quickly and seeing if it looks like a winner?" ... "I
want to do it right away" ... "Test tonight, aim for Week 5").

The score is the linear predictor of a logistic model frozen in the lab (`winner_like_all53.json`, sha256 41169d44...,
fitted on all 53 2022-24 slates with experiments/s48_winner_like.py c22d2811):

    score = beta[0] + sum_j beta[j+1] * (x_j - mu_j) / sd_j

over 24 lineup features, mirrored VERBATIM from the lab's `structural`, `player_facts`, `rank_pct`, `mean_over_skill`
and `features` (parity-tested to 1e-9 on the lab's private fixture). Every input is pre-lock: the T-70 frame's lagged
columns (missing = 0), FP's PROJECTED ownership (a percentile rank among the slate's QB / RB / WR / TE), the players'
regular-season touchdowns / pass attempts over their last 4 / 8 games strictly before the week, and `hist` = 0 live
(its all-53 coefficient is -0.01; the lab's history feature came from sampled fields).

The use (study 48b's DEAL_SCORE): re-order the book's main rows by score, descending, ties keeping the book order,
before enter_layout -- the head deal then puts the most winner-like rows on the big-entry ranks.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

MODEL_PATH = Path(__file__).with_name("winner_like_all53.json")
MODEL_SHA256 = "41169d44f3befeee"                     # the lab's results/s48/MODEL_all53.json (prefix)
SKILL = ("QB", "RB", "WR", "TE")
FEATURES = ("mates", "bringback", "rb_mate", "in_qb_game", "top_game", "salary", "own_rank", "hist",
            "rz_targets", "ez_targets", "gl_carries", "target_share", "carry_share", "snap_share", "wopr", "route_share",
            "vacated", "qb_implied", "qb_spread", "qb_game_total", "td_l4", "td_l8", "qb_pass_td_l4", "qb_att_l4")
FRAME_FACTS = ("rz20_targets_l4", "ez_targets_l4", "gl3_carries_l4", "target_share_l4", "carry_share_l4", "snap_share_l4",
               "wopr_l4", "fp_route_share_l4", "team_vacated_target_share", "implied_team_total", "spread", "game_total")
LAG_COLUMNS = ("td_l4", "td_l8", "pass_td_l4", "att_l4")
# Study 48e's frozen GATE threshold (q 0.50): the all-53 model's median score (hist = 0, as live) of the 31,858 training
# top-1% rows of the 53 slates; lab results/s48e/LIVE_TAU.json sha256 d1c8aaaa2b9202c69614ab8ced19deddc892105586aacb705ac0a33f0a4cd209
# @ c59fa5b (scripts/s48e_live_tau.py, which refits the model and asserts it equal to MODEL_all53). Resolved from here,
# never retyped (CLAUDE.md lesson 7); a different tau needs the explicit override (research / rehearsal only).
FROZEN_GATE_TAU = -4.49767187489062


def load_model(path: Path = MODEL_PATH) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    raw = Path(path).read_bytes()
    if not hashlib.sha256(raw).hexdigest().startswith(MODEL_SHA256):
        raise SystemExit(f"WINNER ORDER REFUSED: {path} is not the frozen all-53 model ({MODEL_SHA256})")
    m = json.loads(raw)
    if tuple(m["features"]) != FEATURES:
        raise SystemExit("WINNER ORDER REFUSED: the model's features are not FEATURES, in order")
    return np.asarray(m["mu"], float), np.asarray(m["sd"], float), np.asarray(m["beta"], float)


def game_top(fr: pd.DataFrame) -> str | None:
    """The slate's top-total game (pre-lock game_total, highest first, ties by game id): the lab's game_ranks rank 1."""
    g = fr[["game_id", "game_total"]].dropna().drop_duplicates("game_id")
    g = g.sort_values(["game_total", "game_id"], ascending=[False, True])
    return str(g.game_id.iloc[0]) if len(g) else None


def slate_arrays(players: pd.DataFrame, top_game: str | None) -> dict:
    """Per-player arrays in the lab's form (players: one row per frame player with pos, team, opp, game_id, salary, the
    FRAME_FACTS and the LAG_COLUMNS; missing = 0)."""
    A = {"pos": players.pos.astype(str).to_numpy(), "team": players.team.astype(str).to_numpy(),
         "opp": players.opp.astype(str).to_numpy(), "game": players.game_id.astype(str).to_numpy(),
         "sal": pd.to_numeric(players.salary, errors="coerce").fillna(0).to_numpy(float), "top": top_game}
    for c in FRAME_FACTS + LAG_COLUMNS:
        A[c] = pd.to_numeric(players[c], errors="coerce").fillna(0.0).to_numpy(float) if c in players.columns else np.zeros(len(players))
    return A


def player_facts(L: np.ndarray, A: dict) -> dict:
    """The lab's player_facts, verbatim."""
    pos = A["pos"][L]; r = np.arange(len(L)); q = (pos == "QB").argmax(axis=1)
    rb, wrte = pos == "RB", (pos == "WR") | (pos == "TE"); nq = rb | wrte
    v = lambda c: A[c][L]                                     # noqa: E731
    mean_over = lambda x, mask: np.where(mask.any(axis=1), (x * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1), 0.0)   # noqa: E731
    return {"rz_targets": (v("rz20_targets_l4") * nq).sum(axis=1), "ez_targets": (v("ez_targets_l4") * nq).sum(axis=1),
            "gl_carries": (v("gl3_carries_l4") * (rb | (pos == "QB"))).sum(axis=1),
            "target_share": mean_over(v("target_share_l4"), wrte), "carry_share": mean_over(v("carry_share_l4"), rb),
            "snap_share": mean_over(v("snap_share_l4"), nq), "wopr": mean_over(v("wopr_l4"), wrte),
            "route_share": mean_over(v("fp_route_share_l4"), wrte), "vacated": mean_over(v("team_vacated_target_share"), wrte),
            "qb_implied": v("implied_team_total")[r, q], "qb_spread": v("spread")[r, q], "qb_game_total": v("game_total")[r, q],
            "td_l4": (v("td_l4") * nq).sum(axis=1), "td_l8": (v("td_l8") * nq).sum(axis=1),
            "qb_pass_td_l4": v("pass_td_l4")[r, q], "qb_att_l4": v("att_l4")[r, q]}


def structural(L: np.ndarray, A: dict) -> dict:
    """The lab's structural, verbatim."""
    pos, team, opp, game, sal = A["pos"][L], A["team"][L], A["opp"][L], A["game"][L], A["sal"][L]
    isqb = pos == "QB"
    if not np.all(isqb.sum(axis=1) == 1):
        raise ValueError("a lineup without exactly one QB")
    q = isqb.argmax(axis=1); r = np.arange(len(L))
    qt, qo, qg = team[r, q][:, None], opp[r, q][:, None], game[r, q][:, None]
    wrte = (pos == "WR") | (pos == "TE"); skill_nq = wrte | (pos == "RB"); nodst = pos != "DST"
    return {"mates": np.minimum((wrte & (team == qt)).sum(axis=1), 3).astype(float),
            "bringback": (skill_nq & (team == qo)).any(axis=1).astype(float),
            "rb_mate": ((pos == "RB") & (team == qt)).any(axis=1).astype(float),
            "in_qb_game": (nodst & (game == qg)).sum(axis=1).astype(float),
            "top_game": (nodst & (game == A["top"])).sum(axis=1).astype(float),
            "salary": sal.sum(axis=1) / 50_000.0}


def rank_pct(values: np.ndarray, pos: np.ndarray) -> np.ndarray:
    """The lab's rank_pct, verbatim: the percentile rank (0..1, average ties) of each SKILL player's value; NaN else."""
    out = np.full(len(values), np.nan)
    sk = np.isin(pos, SKILL)
    out[sk] = pd.Series(values[sk]).rank(method="average", pct=True).to_numpy()
    return out


def mean_over_skill(L: np.ndarray, per_row: np.ndarray, pos: np.ndarray) -> np.ndarray:
    v = per_row[L]; sk = np.isin(pos[L], SKILL)
    v = np.where(sk, v, np.nan)
    return np.nanmean(v, axis=1)


def features(L: np.ndarray, A: dict, own_rank: np.ndarray, hist: np.ndarray) -> pd.DataFrame:
    f = structural(L, A)
    f["own_rank"] = mean_over_skill(L, own_rank, A["pos"])
    f["hist"] = mean_over_skill(L, np.nan_to_num(hist, nan=0.0), A["pos"])
    f.update(player_facts(L, A))
    return pd.DataFrame(f)[list(FEATURES)]


def score(Z: np.ndarray, model) -> np.ndarray:
    mu, sd, beta = model
    return np.column_stack([np.ones(len(Z)), (Z - mu) / sd]) @ beta


def order_by_score(scores) -> list[int]:
    """Study 48b's DEAL_SCORE: book positions by score, descending; ties keep the book order."""
    s = list(scores)
    return sorted(range(len(s)), key=lambda i: (-s[i], i))


def score_book(rows: list[list[str]], players: pd.DataFrame, model=None) -> tuple[np.ndarray, pd.DataFrame]:
    """Score book rows (each 9 frame ids) against per-player inputs (index = frame id; columns pos, team, opp, game_id,
    salary, FRAME_FACTS, LAG_COLUMNS, own_proj = FP's projected ownership, optional hist). Returns (scores, features)."""
    model = model or load_model()
    ids = list(players.index.astype(str))
    at = {p: i for i, p in enumerate(ids)}
    missing = sorted({p for r in rows for p in r if p not in at})
    if missing:
        raise ValueError(f"book players without inputs: {missing[:5]}")
    L = np.array([[at[p] for p in r] for r in rows])
    A = slate_arrays(players.reset_index(drop=True), game_top(players))
    own = rank_pct(pd.to_numeric(players["own_proj"], errors="coerce").fillna(0.0).to_numpy(float), A["pos"])
    hist = pd.to_numeric(players["hist"], errors="coerce").to_numpy(float) if "hist" in players.columns else np.zeros(len(players))
    F = features(L, A, own, hist)
    return score(F.to_numpy(float), model), F
