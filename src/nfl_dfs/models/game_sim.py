"""Possession-level game simulator (drive-state Markov chain).

Design doc: reports/possession-simulator-design.md. This is the v1 engine
for issue #13 item 6 (flagship) -- a small discrete drive-state Markov
chain that replaces the lognormal per-game factor in `simulate.py` with
one derived from how drives actually end (score, punt, turnover, ...).

The transition weights below are a PLACEHOLDER: calibrated only to be
roughly plausible NFL aggregates (~11-12 drives/team/game, ~2.0-2.2
points/drive), not fit from real play-by-play. Fitting them from
`nfl_raw.pbp` needs BigQuery access this module was written without --
see the design doc's "Next steps". Everything here runs fully offline so
the engine and the usage-allocation math built on it can be developed and
tested without GCP.

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

# Raw (unnormalized) weights: terminal-outcome likelihood by starting field
# position, deep_own -> redzone. Placeholder -- see module docstring.
_TERMINAL_WEIGHTS = {
    "deep_own": {"td": 12, "fg_make": 7, "fg_miss": 1, "punt": 58, "turnover": 12, "turnover_on_downs": 1, "safety": 1},
    "own": {"td": 20, "fg_make": 12, "fg_miss": 3, "punt": 45, "turnover": 12, "turnover_on_downs": 3, "safety": 0},
    "midfield": {"td": 27, "fg_make": 16, "fg_miss": 3, "punt": 28, "turnover": 11, "turnover_on_downs": 5, "safety": 0},
    "fringe": {"td": 32, "fg_make": 21, "fg_miss": 4, "punt": 10, "turnover": 10, "turnover_on_downs": 6, "safety": 0},
    "redzone": {"td": 58, "fg_make": 18, "fg_miss": 2, "punt": 2, "turnover": 10, "turnover_on_downs": 5, "safety": 0},
}

# Raw weights for where the *next* offense starts after each terminal
# outcome (kickoff touchback -> "own", punt -> field-position-dependent,
# safety free-kick -> short field around midfield). Terminals not listed
# here (fg_miss, turnover, turnover_on_downs) fall back to `_ZONE_FLIP`:
# possession changed roughly where the drive was, so the new offense's
# zone is the mirror image of the old one.
_NEXT_ZONE_WEIGHTS = {
    "td": {"own": 1},
    "fg_make": {"own": 1},
    "safety": {"midfield": 5, "fringe": 4, "redzone": 1},
    "punt": {"deep_own": 2, "own": 11, "midfield": 4, "fringe": 1},
}

_ZONE_FLIP = {
    "deep_own": "redzone",
    "own": "fringe",
    "midfield": "midfield",
    "fringe": "own",
    "redzone": "deep_own",
}

MAX_DRIVES_PER_TEAM = 16  # generous upper bound; real games run ~9-13
DRIVES_PER_TEAM_SD = 1.8  # real drives/team/game sd, placeholder like the rest


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
    mean_drives_per_team: float = 11.0,
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
    points_a, safeties_a = _simulate_team_drives(rng, n_a)
    points_b, safeties_b = _simulate_team_drives(rng, n_b)
    return points_a + SAFETY_POINTS * safeties_b, points_b + SAFETY_POINTS * safeties_a


def game_factor_matrix(
    rng: np.random.Generator,
    n_games: int,
    n_sims: int,
    mean_drives_per_team: float = 11.0,
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
        pts_a, pts_b = simulate_game_points(rng, n_sims, mean_drives_per_team)
        total = pts_a + pts_b
        mean = total.mean()
        factors[i] = total / mean if mean > 0 else 1.0
    return factors


def team_game_factors(
    rng: np.random.Generator,
    n_games: int,
    n_sims: int,
    mean_drives_per_team: float = 11.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-TEAM, mean-preserving multipliers -- the asymmetric counterpart
    to `game_factor_matrix`. Each team's factor is that team's own points
    divided by that team's own mean, so a blowout shows up as one team's
    factor rising while the other's falls in the same sim, instead of
    both teams sharing one combined-total factor the way
    `game_factor_matrix` (and the lognormal draw it replaces) does. This
    is the game-script asymmetry the design doc's "Why" section cites as
    the possession sim's main motivation over the shared lognormal factor.

    Returns (factors_a, factors_b), each shape (n_games, n_sims) and
    individually mean-preserving (E[factor] == 1 per team, up to sampling
    noise). `simulate.simulate()` assigns factors_a/factors_b to players
    by which of the two teams in their game they're on.
    """
    factors_a = np.empty((n_games, n_sims))
    factors_b = np.empty((n_games, n_sims))
    for i in range(n_games):
        pts_a, pts_b = simulate_game_points(rng, n_sims, mean_drives_per_team)
        mean_a, mean_b = pts_a.mean(), pts_b.mean()
        factors_a[i] = pts_a / mean_a if mean_a > 0 else 1.0
        factors_b[i] = pts_b / mean_b if mean_b > 0 else 1.0
    return factors_a, factors_b


DIRICHLET_CONCENTRATION_SCALE = 20.0
MIN_CONCENTRATION = 0.05


def allocate_drive_usage(
    rng: np.random.Generator,
    n_units: float | np.ndarray,
    usage_shares: np.ndarray,
    n_sims: int = 1,
) -> np.ndarray:
    """Split `n_units` (plays, targets, carries...) across a team's
    players for `n_sims` draws, via a Dirichlet distribution centered on
    `usage_shares` (e.g. `target_share_l4`/`carry_share_l4` from
    `models/featureset.py`). Low-share players (backups, committee
    backfields) still draw meaningful upside sometimes -- exactly the
    boom/next-man-up variance this system is built to price -- because
    their Dirichlet concentration is small, not zero.

    Returns shape (n_sims, len(usage_shares)) if n_sims > 1, else
    (len(usage_shares),).
    """
    shares = np.asarray(usage_shares, dtype=float)
    total = shares.sum()
    shares = shares / total if total > 0 else np.full_like(shares, 1.0 / len(shares))

    concentration = np.clip(shares * DIRICHLET_CONCENTRATION_SCALE, MIN_CONCENTRATION, None)
    drawn = rng.dirichlet(concentration, size=n_sims)  # (n_sims, k)
    units = np.broadcast_to(n_units, (n_sims,)).astype(float)
    allocated = drawn * units[:, None]
    return allocated if n_sims > 1 else allocated[0]
