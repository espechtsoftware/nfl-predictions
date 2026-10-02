"""Winner-shaped tail sleeve (operator 2026-10-02, after the corpus audit `reports/2026-10-02-corpus-win-audit.md`).

The Millionaire / FFWC / $555 rows (the tail sleeve) were the T highest-projected rows of the union. In Weeks 1 and 3
the real top-0.1% lineups were field-like lineups ranked high by our projection, and our corpus held none of them.
Here the sleeve's candidates are drawn the way the field builds lineups:

  1. targets = the pre-lock ownership predictor the ownership term uses (`pred_own`, %, matched on dk_player_id /
     gsis_id / id), each position scaled to the real field's totals; DSTs (not covered by the predictors) get
     projection-squared weights summing to one slot; unavailable players and skill players under the minimum projection
     get 0; then a salary tilt so a drawn lineup spends like the field (~$49,500);
  2. N lineups from the lab's ownership-consistent field sampler (`field_sampler.py`, vendored verbatim), deduplicated;
  3. kept if they satisfy the house rules with a per-game limit of `max_game` (default 5; the main book keeps 4):
     salary >= the floor, QB + 2 WR/TE, 1 bring-back, no RB facing his own DST, no two RBs of one team;
  4. ordered for the sleeve's greedy pick: `top` = by projected sum; `band` = a seeded shuffle of the rows between the
     97th and 99.5th percentile of the kept rows' projected sums; `free` = EVERY sampled lineup (DK-legal by the
     sampler: cap, salary band, no duplicate player), NO house-rule filter, by projected sum. On L13's 36 slates (blend
     ownership, 12 seeds) `free` led on the mean (+0.12 sd vs the projection sleeve's -0.03), the top 5% (1.48x vs 1.33x)
     and the top 0.1% (1.39x vs 0), and trailed at the top 1% (1.99x vs 2.22x): the operator's Week-4 choice.

Pure functions; union_reselect.py wires them in behind --sleeve-source field and falls back loudly to the projection
sleeve on any failure.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from field_sampler import sample_field

SKILL = ("QB", "RB", "WR", "TE")
BAND = (0.97, 0.995)
MODES = ("top", "band", "free")
SLOT_TOTALS = {"QB": 1.0, "RB": 2.4, "WR": 3.45, "TE": 1.15}


def _key(v: object) -> str:
    s = str(v).strip()
    if s.lower() in ("", "nan", "none", "<na>"):
        return ""
    return s[:-2] if s.endswith(".0") and s[:-2].isdigit() else s


def ownership_targets(source: Path, fr: pd.DataFrame, exclude: set[str], min_coverage: float = 0.9) -> tuple[dict[str, float], dict]:
    """Per frame id, the target share of lineups (0..1). Raises ValueError on an unusable file."""
    own = pd.read_csv(source, dtype=str)
    keys = [c for c in ("dk_player_id", "gsis_id", "id") if c in own.columns]
    if "pred_own" not in own.columns or not keys:
        raise ValueError(f"{source} needs pred_own and one of dk_player_id / gsis_id / id")
    val = pd.to_numeric(own.pred_own, errors="coerce").clip(lower=0.0)
    if not np.all(np.isfinite(val)) or float(val.max()) <= 1.0:
        raise ValueError(f"{source}: pred_own must be finite percentages")
    by = {c: {} for c in keys}
    for c in keys:
        for k, v in zip(own[c].map(_key), val):
            if k:
                by[c][k] = max(float(v), by[c].get(k, 0.0))
    ids = fr.id.astype(str).tolist(); pos = dict(zip(ids, fr.pos.astype(str)))
    proj = dict(zip(ids, pd.to_numeric(fr.mean_projection, errors="coerce").fillna(0.0)))
    dk_of = dict(zip(ids, fr.dk_player_id.map(_key))) if "dk_player_id" in fr.columns else {}
    t: dict[str, float] = {}
    for i in ids:
        if pos[i] not in SKILL or i in exclude:
            continue
        for c in keys:
            k = dk_of.get(i, "") if c == "dk_player_id" else _key(i)
            if k and k in by[c]:
                t[i] = by[c][k] / 100.0
                break
    core = [i for i in ids if pos[i] in SKILL and i not in exclude and proj[i] >= 5.0]
    coverage = sum(1 for i in core if i in t) / len(core) if core else 0.0
    if coverage < min_coverage:
        raise ValueError(f"{source} covers {coverage:.1%} of the skill players projected >= 5 (< {min_coverage:.0%})")
    # the predictors' totals are not the field's (Week-4 lag file: QB 0.77, RB 1.38, WR 1.98, TE 0.93 lineups' worth); the
    # sampler's fitting then fails to fill. Scale each position to the real Millionaire totals (W1-W3: QB 1, RB 2 + FLEX,
    # WR 3 + FLEX, TE 1 + FLEX; FLEX split ~40/45/15), keeping the shape inside the position; no player above 95%.
    raw = {}
    for p, total in SLOT_TOTALS.items():
        ks = [i for i in t if pos[i] == p]
        s = sum(t[i] for i in ks)
        if ks and s > 0:
            for i in ks:
                t[i] = min(0.95, t[i] * total / s)
            raw[p] = round(s, 3)
    dst = [i for i in ids if pos[i] == "DST" and i not in exclude]
    w = np.clip(np.array([proj[i] for i in dst], float), 0.1, None) ** 2
    t.update({i: float(x) for i, x in zip(dst, w / w.sum())})
    sal = dict(zip(ids, pd.to_numeric(fr.salary, errors="coerce").fillna(0.0).astype(float)))
    t, beta, before, after = salary_tilt(t, pos, sal)
    return t, {"salary_tilt": {"beta_per_1000": round(beta, 4), "mean_lineup_salary_before": round(before), "after": round(after),
                               "target": SALARY_TARGET}, "source": str(source), "skill_players_with_a_target": sum(1 for i in t if pos[i] in SKILL),
               "coverage_projected_5": round(coverage, 4), "dst_rule": "projection squared, one slot",
               "position_totals_before_scaling": raw, "position_totals_after": SLOT_TOTALS}


def legal(L: np.ndarray, fr: pd.DataFrame, max_game: int, min_salary: int) -> np.ndarray:
    """House rules on an (n, 9) array of frame row indices (any slot order)."""
    pos = fr.pos.astype(str).to_numpy(); team = fr.team.astype(str).to_numpy(); opp = fr.opp.astype(str).to_numpy()
    game = pd.factorize(fr.game_id.astype(str))[0]; sal = pd.to_numeric(fr.salary, errors="coerce").fillna(0).to_numpy()
    P, Tm = pos[L], team[L]
    qb = np.argmax(P == "QB", axis=1); dst = np.argmax(P == "DST", axis=1); rows = np.arange(len(L))
    qbt = Tm[rows, qb]; qbo = opp[L[rows, qb]]; dsto = opp[L[rows, dst]]
    ok = (P == "QB").sum(1) == 1
    ok &= sal[L].sum(1) >= min_salary
    ok &= (np.isin(P, ["WR", "TE"]) & (Tm == qbt[:, None])).sum(1) >= 2
    ok &= ((Tm == qbo[:, None]) & (P != "DST")).sum(1) >= 1
    ok &= ~((P == "RB") & (Tm == dsto[:, None])).any(1)
    rbteam = np.where(P == "RB", Tm, "")
    srt = np.sort(rbteam, axis=1); ok &= ~((srt[:, 1:] == srt[:, :-1]) & (srt[:, 1:] != "")).any(1)
    gc = np.zeros((len(L), game.max() + 1), np.int16)
    for j in range(L.shape[1]):
        np.add.at(gc, (rows, game[L[:, j]]), 1)
    return ok & (gc.max(1) <= max_game)


SALARY_TARGET = 49_500


def mean_lineup_salary(t: dict[str, float], pos: dict[str, str], sal: dict[str, float]) -> float:
    """Expected salary of a lineup drawn slot by slot from the targets (QB, 2 RB, 3 WR, TE, FLEX, DST), independently."""
    def avg(ps):
        ks = [i for i in t if pos[i] in ps and t[i] > 0]; w = np.array([t[i] for i in ks]); s = np.array([sal[i] for i in ks])
        return float((w * s).sum() / w.sum()) if len(ks) else 0.0
    return avg(("QB",)) + 2 * avg(("RB",)) + 3 * avg(("WR",)) + avg(("TE",)) + avg(("RB", "WR", "TE")) + avg(("DST",))


def salary_tilt(t: dict[str, float], pos: dict[str, str], sal: dict[str, float], target: float = SALARY_TARGET):
    """The pre-lock predictors put the field's ownership on expensive players (Week-4 lag file: a drawn lineup averages
    $52,200; 28% fit under the cap), so the sampler cannot fill. Multiply each target by exp(-beta * salary / 1000) with
    beta solved (bisection) so a drawn lineup averages `target`; each position's total is restored afterwards. beta = 0
    when the targets already spend at or below the target."""
    before = mean_lineup_salary(t, pos, sal)
    if before <= target:
        return t, 0.0, before, before
    def tilted(b):
        u = {i: v * np.exp(-b * sal[i] / 1000.0) for i, v in t.items()}
        for p in set(pos[i] for i in t):
            ks = [i for i in t if pos[i] == p]; s0 = sum(t[i] for i in ks); s1 = sum(u[i] for i in ks)
            for i in ks:
                u[i] = min(0.95, u[i] * s0 / s1) if s1 > 0 else u[i]
        return u
    lo, hi = 0.0, 3.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if mean_lineup_salary(tilted(mid), pos, sal) > target:
            lo = mid
        else:
            hi = mid
    u = tilted(hi)
    return u, hi, before, mean_lineup_salary(u, pos, sal)


CHUNK = 50_000


def sample_chunks(fr: pd.DataFrame, targets: dict[str, float], n: int, seed: int, sampler=sample_field) -> tuple[np.ndarray, dict]:
    """The sampler in chunks of CHUNK lineups, seeds seed, seed+1, ...: its rejection loop can fall a few percent short of
    one large request (Week-4 smoke: 38,074 of 40,000 in an IPF round). A chunk that fails is retried once at a fifth of
    the size; the receipt counts both."""
    parts, rec, k = [], {"chunks": 0, "retried": 0}, 0
    while sum(len(p) for p in parts) < n:
        m = min(CHUNK, n - sum(len(p) for p in parts))
        try:
            L, r = sampler(fr, targets, m, seed + k)
        except RuntimeError:
            rec["retried"] += 1
            L, r = sampler(fr, targets, max(2_000, m // 5), seed + 10_000 + k)
        parts.append(L); rec["chunks"] += 1; k += 1
        rec.update({x: r[x] for x in ("final_abs_ownership_error_sum", "stack_rate", "mean_salary") if x in r})
        if k > 4 * (n // CHUNK + 2):
            raise RuntimeError(f"field sampler: {sum(len(p) for p in parts)} of {n} lineups after {k} chunks")
    return np.vstack(parts)[:n], rec


def field_candidates(fr: pd.DataFrame, targets: dict[str, float], n: int, seed: int, max_game: int, min_salary: int,
                     mode: str, sampler=None, min_legal: int = 50) -> tuple[list[list[str]], np.ndarray, dict]:
    """(rosters as frame-id lists in pick order, their projected sums, receipt)."""
    if mode not in MODES:
        raise ValueError(f"mode {mode!r}")
    S, srec = sample_chunks(fr, targets, n, seed, sampler=sampler or sample_field)
    S = np.unique(np.sort(S, axis=1), axis=0)
    proj = pd.to_numeric(fr.mean_projection, errors="coerce").fillna(0.0).to_numpy(float)
    ok = legal(S, fr, max_game, min_salary)
    K = S if mode == "free" else S[ok]; ps = proj[K].sum(1)
    if mode != "free" and len(K) < min_legal:
        raise ValueError(f"only {len(K)} of {len(S)} sampled lineups satisfy the house rules")
    if mode in ("top", "free"):
        order = np.argsort(-ps, kind="stable")
    else:
        lo, hi = np.quantile(ps, BAND)
        band = np.where((ps >= lo) & (ps <= hi))[0]
        order = np.random.default_rng(seed + 1).permutation(band)
    ids = fr.id.astype(str).to_numpy()
    rec = {"n_sampled": int(n), "distinct": int(len(S)), "legal": int(ok.sum()), "house_rules_applied": mode != "free", "max_game": max_game, "min_salary": min_salary,
           "mode": mode, "seed": seed, "band": list(BAND) if mode == "band" else None, "candidates_in_order": int(len(order)),
           "projected_sum": {"max": round(float(ps.max()), 2), "p99": round(float(np.quantile(ps, .99)), 2),
                             "median": round(float(np.median(ps)), 2)},
           "sampler": {k: srec[k] for k in ("final_abs_ownership_error_sum", "stack_rate", "mean_salary") if k in srec}}
    return [ids[K[i]].tolist() for i in order], ps[order], rec
