"""Possession-level game simulator (drive-state Markov chain).

Design doc: reports/possession-simulator-design.md. This is the v1 engine
for issue #13 item 6 (flagship) -- a small discrete drive-state Markov
chain that replaces the lognormal per-game factor in `simulate.py` with
one derived from how drives actually end (score, punt, turnover, ...).

The transition weights below are FITTED from `nfl_raw.pbp`, seasons
2018-2025 (48,528 drives, 2,227 games; fit 2026-08-01, replacing the
original hand-calibrated placeholder). Fit semantics, chosen to match how
the engine consumes each table:

- Start zone = the drive's first SCRIMMAGE play (kickoff rows carry the
  kicking-spot yardline; PAT-only pseudo-drives after defensive TDs were
  excluded -- both poisoned earlier fit attempts).
- `end_of_half`/`end_of_game` drives (6.8%) are dropped and the terminal
  probabilities renormalized; correspondingly, drives/team/game moments
  EXCLUDE those drives (mean 10.16, sd 1.65), so points/game stays right.
- `_NEXT_ZONE_WEIGHTS` is the SAME TEAM's next-drive start zone (two
  possession changes later), the quantity `_simulate_team_drives`
  actually consumes. Only td/fg_make/punt/safety are fitted; fg_miss/
  turnover/turnover_on_downs keep the zone-aware `_ZONE_FLIP` heuristic,
  since a single per-terminal distribution can't carry their strong
  dependence on where the drive died.
- Empirical anchors from the same fit: 2.175 pts/drive, 22.1 offensive
  pts/team/game (7/TD + 3/FG accounting), game total 44.2 +/- 13.8, and
  cross-team points correlation 0.016 -- i.e., the two teams' scoring is
  essentially INDEPENDENT in real games (relevant to the team_game_factors
  correlation discussion below).

The module still runs fully offline; the fit script lives in the session
records and is a ~60-line pbp aggregation, easy to re-run when seasons
accumulate.

Gated by `GAME_SIM_MODE` in `simulate.py`; default behavior there
(`GAME_SIM_MODE` unset or "lognormal") is completely unaffected by this
module.
"""

from __future__ import annotations

import numpy as np

ZONES = ("deep_own", "own", "midfield", "fringe", "redzone")
ZONE_INDEX = {name: i for i, name in enumerate(ZONES)}

TERMINALS = ("td", "fg_make", "fg_miss", "punt", "turnover", "turnover_on_downs", "safety")
TERMINAL_INDEX = {name: i for i, name in enumerate(TERMINALS)}

# Points awarded to the drive's own offense. fg_miss/punt/turnover(_on_downs)
# are 0 -- possession simply changes hands. safety is ALSO 0 here: it scores
# for the *defense*, not this offense, so a single team's own-drive sequence
# can't attribute it -- `simulate_game_points` credits the 2 points to the
# opponent's total separately (see `_simulate_team_drives`'s `safeties`).
TERMINAL_POINTS = np.array([7.0, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0])
assert len(TERMINAL_POINTS) == len(TERMINALS)
SAFETY_POINTS = 2.0  # credited to the opponent, not this team's own total

# Terminal-outcome percentages by starting field position, FITTED from
# nfl_raw.pbp 2018-2025 (see module docstring for fit semantics). Zone
# support: own 36,587 drives / midfield 4,961 / deep_own 4,011 / fringe
# 2,107 / redzone 860.
_TERMINAL_WEIGHTS = {
    "deep_own": {"td": 16.74, "fg_make": 9.74, "fg_miss": 1.86, "punt": 50.49, "turnover": 13.95, "turnover_on_downs": 4.62, "safety": 2.6},
    "own": {"td": 22.44, "fg_make": 14.56, "fg_miss": 2.73, "punt": 41.66, "turnover": 12.85, "turnover_on_downs": 5.69, "safety": 0.07},
    "midfield": {"td": 30.51, "fg_make": 22.75, "fg_miss": 4.05, "punt": 25.83, "turnover": 10.09, "turnover_on_downs": 6.78, "safety": 0.0},
    "fringe": {"td": 40.45, "fg_make": 35.19, "fg_miss": 5.84, "punt": 5.47, "turnover": 7.63, "turnover_on_downs": 5.42, "safety": 0.0},
    "redzone": {"td": 57.6, "fg_make": 31.03, "fg_miss": 1.24, "punt": 0.12, "turnover": 5.93, "turnover_on_downs": 4.08, "safety": 0.0},
}

# Same-team NEXT-drive start-zone percentages by terminal outcome (two
# possession changes later -- the quantity `_simulate_team_drives`
# consumes; see its CAUTION docstring), fitted from the same pbp span.
# Terminals not listed (fg_miss, turnover, turnover_on_downs) fall back
# to `_ZONE_FLIP`: their next-start depends strongly on where the drive
# died, which a flat per-terminal distribution can't carry.
_NEXT_ZONE_WEIGHTS = {
    "td": {"deep_own": 8.67, "own": 73.28, "midfield": 11.28, "fringe": 5.05, "redzone": 1.72},
    "fg_make": {"deep_own": 8.4, "own": 73.2, "midfield": 11.28, "fringe": 5.23, "redzone": 1.88},
    "safety": {"deep_own": 10.58, "own": 75.0, "midfield": 7.69, "fringe": 3.85, "redzone": 2.88},
    "punt": {"deep_own": 8.59, "own": 71.6, "midfield": 12.08, "fringe": 5.2, "redzone": 2.53},
}

_ZONE_FLIP = {
    "deep_own": "redzone",
    "own": "fringe",
    "midfield": "midfield",
    "fringe": "own",
    "redzone": "deep_own",
}

MAX_DRIVES_PER_TEAM = 16  # generous upper bound; real games run ~9-13
# Fitted 2018-2025, EXCLUDING end-of-half drives to match the terminal
# table's renormalization (see module docstring): 10.16 +/- 1.65.
MEAN_DRIVES_PER_TEAM = 10.16
DRIVES_PER_TEAM_SD = 1.65


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()}


def _prob_matrix(
    weights_by_row: dict[str, dict[str, float]],
    row_index: dict[str, int],
    col_index: dict[str, int],
) -> np.ndarray:
    matrix = np.zeros((len(row_index), len(col_index)))
    for row_name, weights in weights_by_row.items():
        if not weights:
            continue
        for col_name, p in _normalize(weights).items():
            matrix[row_index[row_name], col_index[col_name]] = p
    return matrix


TERMINAL_PROB_MATRIX = _prob_matrix(_TERMINAL_WEIGHTS, ZONE_INDEX, TERMINAL_INDEX)
_CUM_TERMINAL_PROB = np.cumsum(TERMINAL_PROB_MATRIX, axis=1)

_NEXT_ZONE_PROB_MATRIX = _prob_matrix(_NEXT_ZONE_WEIGHTS, TERMINAL_INDEX, ZONE_INDEX)
_CUM_NEXT_ZONE_PROB = np.cumsum(_NEXT_ZONE_PROB_MATRIX, axis=1)
_EXPLICIT_NEXT_ZONE_TERMINALS = np.array(
    [TERMINAL_INDEX[t] for t in _NEXT_ZONE_WEIGHTS]
)
_ZONE_FLIP_ARRAY = np.array([ZONE_INDEX[_ZONE_FLIP[z]] for z in ZONES])


def _categorical_draw(rng: np.random.Generator, cum_probs: np.ndarray) -> np.ndarray:
    """cum_probs: (n_sims, k) cumulative probabilities per row -> (n_sims,) index draws."""
    u = rng.random(cum_probs.shape[0])
    idx = (u[:, None] > cum_probs).sum(axis=1)
    return np.clip(idx, 0, cum_probs.shape[1] - 1)


def _simulate_team_drives(
    rng: np.random.Generator,
    n_drives: np.ndarray,
    start_zone: str = "own",
) -> tuple[np.ndarray, np.ndarray]:
    """(points, safeties_conceded) across `len(n_drives)` sims, given each
    sim's possession count `n_drives` (int array). `points` is this team's
    own-drive scoring only (TD/FG make); `safeties_conceded` counts drives
    that ended in a safety, which `simulate_game_points` credits to the
    OPPONENT's total, since a safety scores for the defense.

    Does not explicitly simulate the opponent's intervening drives -- the
    next-zone draw approximates the receiving team's expected field
    position from aggregate rates across all possession changes of that
    type, which already folds in the opponent's average drive length.

    CAUTION for the pbp fit (design doc "Next steps" 1): because the
    opponent's drive is skipped, the next-zone distribution consumed here
    is *this same team's* next drive start -- two possession changes
    after the terminal outcome -- NOT the opponent's takeover spot. The
    placeholder table conflates the two (e.g. a turnover in the opponent's
    red zone pins THIS team at deep_own next drive, when causally the
    opponent inherits the bad field position and this team tends to get a
    short field back). Fit the same-team quantity from pbp, or switch to
    explicit alternating possessions."""
    n_drives = np.clip(np.asarray(n_drives, dtype=int), 0, MAX_DRIVES_PER_TEAM)
    n_sims = len(n_drives)
    zone = np.full(n_sims, ZONE_INDEX[start_zone], dtype=int)
    points = np.zeros(n_sims)
    safeties = np.zeros(n_sims)
    max_drives = int(n_drives.max()) if n_sims else 0
    safety_idx = TERMINAL_INDEX["safety"]

    for d in range(max_drives):
        active = d < n_drives
        if not active.any():
            break

        terminal = _categorical_draw(rng, _CUM_TERMINAL_PROB[zone])
        points += np.where(active, TERMINAL_POINTS[terminal], 0.0)
        safeties += np.where(active & (terminal == safety_idx), 1.0, 0.0)

        drawn_zone = _categorical_draw(rng, _CUM_NEXT_ZONE_PROB[terminal])
        explicit = np.isin(terminal, _EXPLICIT_NEXT_ZONE_TERMINALS)
        next_zone = np.where(explicit, drawn_zone, _ZONE_FLIP_ARRAY[zone])
        zone = np.where(active, next_zone, zone)

    return points, safeties


def simulate_team_points(
    rng: np.random.Generator,
    n_drives: np.ndarray,
    start_zone: str = "own",
) -> np.ndarray:
    """This team's own-drive scoring (TD/FG make); always >= 0. Excludes
    safety points conceded TO the opponent -- those only make sense as
    part of a two-team game, see `simulate_game_points`."""
    points, _ = _simulate_team_drives(rng, n_drives, start_zone)
    return points


def simulate_game_points(
    rng: np.random.Generator,
    n_sims: int,
    mean_drives_per_team: float = MEAN_DRIVES_PER_TEAM,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-team total points for `n_sims` independent game draws. Each
    team's drive sequence is simulated independently; the only cross-team
    coupling is (a) drive counts constrained within +/-1 of each other
    (teams alternate possessions in a real game, so counts rarely differ
    by more) and (b) safeties conceded by one team credited to the
    other's total, since that's the only terminal outcome that scores
    for the defense rather than the offense. There is no within-sim
    field-position coupling (a turnover here does not literally hand the
    other simulated team a short field) -- adequate for the shared
    per-game factor this feeds, revisit if team-level asymmetry lands."""
    # Rounded normal, NOT Poisson: Poisson(11) has sd ~3.3 drives, far
    # wider than real games (~1.5-2), and that excess possession variance
    # alone pushed the derived game factor's sd to ~0.45 vs the validated
    # lognormal's 0.18 before this was tightened.
    n_a = np.clip(
        np.rint(rng.normal(mean_drives_per_team, DRIVES_PER_TEAM_SD, n_sims)).astype(int),
        6, MAX_DRIVES_PER_TEAM,
    )
    delta = rng.integers(-1, 2, n_sims)
    n_b = np.clip(n_a + delta, 6, MAX_DRIVES_PER_TEAM)
    import os as _os

    if _os.environ.get("SCRIPT_FEEDBACK", "") not in ("", "0"):
        # A/B lever (external review 1.3, 2026-08-04): game-script
        # feedback. Independent whole-game drive sequences can't express
        # "trailing team speeds up / leader kills clock". Two-half split:
        # sim half 1, then when the half-1 margin exceeds 10 the trailing
        # team gains a half-2 possession and the leader loses one with
        # p=0.5 — fattening both-boom (shootout chase) and blowout
        # (clock-kill) worlds. Downstream factors are mean-normalized,
        # so only the SHAPE changes. Off by default pending its panel.
        h1_a = n_a // 2
        h1_b = n_b // 2
        p1a, s1a = _simulate_team_drives(rng, h1_a)
        p1b, s1b = _simulate_team_drives(rng, h1_b)
        margin = (p1a + SAFETY_POINTS * s1b) - (p1b + SAFETY_POINTS * s1a)
        chase_a = margin < -10
        chase_b = margin > 10
        kill = rng.random(n_sims) < 0.5
        h2_a = np.clip(n_a - h1_a + chase_a.astype(int)
                       - (chase_b & kill).astype(int), 1, MAX_DRIVES_PER_TEAM)
        h2_b = np.clip(n_b - h1_b + chase_b.astype(int)
                       - (chase_a & kill).astype(int), 1, MAX_DRIVES_PER_TEAM)
        p2a, s2a = _simulate_team_drives(rng, h2_a)
        p2b, s2b = _simulate_team_drives(rng, h2_b)
        points_a, safeties_a = p1a + p2a, s1a + s2a
        points_b, safeties_b = p1b + p2b, s1b + s2b
    else:
        points_a, safeties_a = _simulate_team_drives(rng, n_a)
        points_b, safeties_b = _simulate_team_drives(rng, n_b)
    return points_a + SAFETY_POINTS * safeties_b, points_b + SAFETY_POINTS * safeties_a


def game_factor_matrix(
    rng: np.random.Generator,
    n_games: int,
    n_sims: int,
    mean_drives_per_team: float = MEAN_DRIVES_PER_TEAM,
    paces: np.ndarray | None = None,
) -> np.ndarray:
    """Drop-in replacement for `simulate.py`'s lognormal `game_mult` draw:
    shape (n_games, n_sims), one shared multiplier per game per sim (both
    teams in a game get the same value -- the same granularity the
    lognormal factor has today). Used when the caller has no per-player
    team assignment to key an asymmetric factor off of; see
    `team_game_factors` for the team-level version, which is the main
    motivating benefit of a possession sim (see the design doc).

    Mean-preserving empirically over the `n_sims` batch (E[factor] == 1 up
    to sampling noise); use `n_sims` in the thousands, matching
    `simulate.simulate()`'s default of 10,000, for that noise to be small.
    """
    factors = np.empty((n_games, n_sims))
    for i in range(n_games):
        pace = 1.0 if paces is None else float(paces[i])
        pts_a, pts_b = simulate_game_points(rng, n_sims,
                                            mean_drives_per_team * pace)
        total = pts_a + pts_b
        mean = total.mean()
        factors[i] = total / mean if mean > 0 else 1.0
    return factors


def team_game_factors(
    rng: np.random.Generator,
    n_games: int,
    n_sims: int,
    mean_drives_per_team: float = MEAN_DRIVES_PER_TEAM,
    paces: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-TEAM, mean-preserving multipliers -- the asymmetric counterpart
    to `game_factor_matrix`. Each team's factor is that team's own points
    divided by that team's own mean, instead of both teams sharing one
    combined-total factor the way `game_factor_matrix` (and the lognormal
    draw it replaces) does.

    What this does and does NOT deliver: because `simulate_game_points`
    simulates the two teams' drive sequences independently (coupled only
    through drive counts +/-1 and safety credit), the two factors are
    NEARLY INDEPENDENT (measured corr ~0.1-0.2) -- not anticorrelated.
    A blowout world (one factor up while the other is down) occurs only
    as often as independence implies; the engine has no score-differential
    dynamics to make it more likely. Equally important: independence
    REMOVES the within-game cross-team correlation the shared factor
    provided, which is what makes QB + opposing bring-back shootout
    stacks price correctly (README §6.2). Reality sits between corr=1
    (shared) and corr~0 (this): interpret any replay A/B accordingly, and
    if this arm underperforms, the fix is likely a hybrid (shared
    environment component x team-specific component), not abandoning
    team-level factors. See the design doc's "Next steps".

    Returns (factors_a, factors_b), each shape (n_games, n_sims) and
    individually mean-preserving (E[factor] == 1 per team, up to sampling
    noise). `simulate.simulate()` assigns factors_a/factors_b to players
    by which of the two teams in their game they're on.
    """
    factors_a = np.empty((n_games, n_sims))
    factors_b = np.empty((n_games, n_sims))
    for i in range(n_games):
        pace = 1.0 if paces is None else float(paces[i])
        pts_a, pts_b = simulate_game_points(rng, n_sims,
                                            mean_drives_per_team * pace)
        mean_a, mean_b = pts_a.mean(), pts_b.mean()
        factors_a[i] = pts_a / mean_a if mean_a > 0 else 1.0
        factors_b[i] = pts_b / mean_b if mean_b > 0 else 1.0
    return factors_a, factors_b


DIRICHLET_CONCENTRATION_SCALE = float(
    __import__("os").environ.get("DIRICHLET_K", "20.0"))
# DIRICHLET_K env (graveyard review 2026-08-03): K=20 tested negative
# with the ledger itself noting "concentration scale is the retune
# knob" — the retune was never run. Lower K = spikier within-team
# allocations (more next-man-up variance).
MIN_CONCENTRATION = 0.05


def allocate_drive_usage(
    rng: np.random.Generator,
    n_units: float | np.ndarray,
    usage_shares: np.ndarray,
    n_sims: int = 1,
    concentration_scale: float | None = None,
) -> np.ndarray:
    """Split `n_units` (plays, targets, carries...) across a team's
    players for `n_sims` draws, via a Dirichlet distribution centered on
    `usage_shares` (e.g. `target_share_l4`/`carry_share_l4` from
    `models/featureset.py`). Low-share players (backups, committee
    backfields) still draw meaningful upside sometimes -- exactly the
    boom/next-man-up variance this system is built to price -- because
    their Dirichlet concentration is small, not zero.

    `concentration_scale` (research/SBI injection, plan §2.4): when None
    -- every production call -- the module-level DIRICHLET_CONCENTRATION_SCALE
    is used and behavior is byte-identical to before the argument existed;
    a finite value overrides it for calibration experiments only
    (src/nfl_dfs/research/sbi_params.py).

    Returns shape (n_sims, len(usage_shares)) if n_sims > 1, else
    (len(usage_shares),).
    """
    shares = np.asarray(usage_shares, dtype=float)
    total = shares.sum()
    shares = shares / total if total > 0 else np.full_like(shares, 1.0 / len(shares))

    scale = (DIRICHLET_CONCENTRATION_SCALE if concentration_scale is None
             else float(concentration_scale))
    concentration = np.clip(shares * scale, MIN_CONCENTRATION, None)
    drawn = rng.dirichlet(concentration, size=n_sims)  # (n_sims, k)
    units = np.broadcast_to(n_units, (n_sims,)).astype(float)
    allocated = drawn * units[:, None]
    return allocated if n_sims > 1 else allocated[0]
