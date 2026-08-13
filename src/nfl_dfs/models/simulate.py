"""Monte Carlo composition of component predictions (guide §6.2).

Each draw samples opportunity (Poisson), conversion (Binomial), and yardage
(Gamma with the predicted per-unit rate as its mean), then scores the stat
line with real DK rules — bonuses included, which is the entire point: the
mean never sees the 100-yard cliff, the draws do.

Distributions are chosen so the simulated mean equals the analytic
composition of the components (Poisson/Binomial/Gamma all preserve their
means); a biased sampler would silently shift every projection.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

from .scoring import StatLine, dk_points


log = logging.getLogger(__name__)


# Cloud Run can place otherwise identical executions on different CPU
# microarchitectures. Sub-ULP component prediction differences are harmless
# as point estimates but can cross a discrete Poisson/binomial threshold and
# then be amplified by marginal rank shaping. Quantize only at the simulator
# boundary so training and persisted model predictions retain full precision
# while seeded worlds remain portable across workers.
SIM_COMPONENT_DECIMALS = 10


def canonicalize_simulation_components(comps: pd.DataFrame) -> pd.DataFrame:
    """Return stable float64 component means for seeded outcome sampling."""
    values = comps.to_numpy(dtype=np.float64, copy=True)
    finite = np.isfinite(values)
    values[finite] = np.round(values[finite], SIM_COMPONENT_DECIMALS)
    # Normalize signed zero because its byte representation is otherwise
    # different even though every numeric operation treats it as zero.
    values[values == 0.0] = 0.0
    return pd.DataFrame(values, index=comps.index, columns=comps.columns)


def simulation_component_sha256(comps: pd.DataFrame) -> str:
    """Deterministic fingerprint used to audit cross-execution parity."""
    values = comps.to_numpy(dtype="<f8", copy=True)
    # The sampler converts missing component means to zero, so the audit hash
    # records the exact effective input rather than platform-specific NaN bits.
    values = np.nan_to_num(values, nan=0.0, posinf=np.inf, neginf=-np.inf)
    payload = "\x1f".join(map(str, comps.columns)).encode() + values.tobytes()
    return hashlib.sha256(payload).hexdigest()


def _game_team_unit_codes(
    n: int,
    game_ids: pd.Series | None,
    team_ids: pd.Series,
) -> np.ndarray:
    """Factorize the allocation unit available to a live weekly slate.

    Season replay passes many weeks to :func:`simulate` at once. Team alone
    is therefore not an allocation unit: it would make every appearance by a
    franchise share one season-wide opportunity pool. Missing identifiers get
    row-unique sentinels so unknown fringe players cannot acquire synthetic
    dependence merely because their metadata are absent.

    ``game_ids=None`` retains the narrow unit-test/research behavior where the
    supplied frame itself is one game and teams are the available unit.
    """
    teams = pd.Series(team_ids).reset_index(drop=True)
    if len(teams) != n:
        raise ValueError("team_ids must align one-to-one with components")
    teams = teams.where(
        teams.notna(), "_none_team_" + teams.index.astype(str)
    ).astype(str)

    if game_ids is None:
        games = pd.Series(["_game"] * n)
    else:
        games = pd.Series(game_ids).reset_index(drop=True)
        if len(games) != n:
            raise ValueError("game_ids must align one-to-one with components")
        games = games.where(
            games.notna(), "_none_game_" + games.index.astype(str)
        ).astype(str)

    units = pd.MultiIndex.from_arrays([games, teams])
    return pd.factorize(units)[0]

# Gamma shape per unit of opportunity: higher = tighter yardage around the
# predicted rate. ~2 per touch reproduces observed per-catch/carry variance.
_YARDS_SHAPE = 2.0


@dataclass
class SimResult:
    summary: pd.DataFrame
    draws: np.ndarray | None = None


def _gamma_yards(
    rng: np.random.Generator, count: np.ndarray, per_unit: np.ndarray
) -> np.ndarray:
    """Total yards over `count` opportunities averaging `per_unit` each.
    Gamma(shape=count*k, scale=per_unit/k) has mean count*per_unit."""
    shape = count * _YARDS_SHAPE
    scale = np.broadcast_to(per_unit / _YARDS_SHAPE, shape.shape)
    out = np.zeros(shape.shape)
    pos = shape > 0
    out[pos] = rng.gamma(shape[pos], scale[pos])
    return out


GAME_FACTOR_SIGMA = 0.18  # lognormal sigma of the shared per-game factor


def _td_event_ledger(
    rng: np.random.Generator,
    rec_means: np.ndarray,
    pass_means: np.ndarray,
    team_codes: np.ndarray,
    game_mult: np.ndarray,
    n_sims: int,
    alloc_k: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Team-level passing-TD ledger (TD_LEDGER=1). For each team: draw
    the team's passing-TD count once per sim (Poisson on the summed
    passer means, scaled by the team's game factor), then allocate the
    SAME totals to catchers (multinomial on receiving-TD shares, with
    an "other" bucket reconciling unrostered catchers) and to passers.
    Preserves every player's marginal mean; creates the QB<->receiver
    same-event covariance and couples TDs to the game environment.
    Teams with no rostered passer fall back to independent draws.

    `alloc_k` (research/SBI injection, plan §2.4): when None -- every
    production call -- allocation is the exact multinomial on mean TD
    shares, byte-identical to before the argument existed. A finite
    value switches to Dirichlet-multinomial (per-sim shares drawn from
    Dirichlet(alloc_k * mean_shares), then multinomial), which keeps
    each player's marginal TD mean but makes realized shares burstier
    -- the passing-TD allocation concentration parameter registered in
    src/nfl_dfs/research/sbi_params.py."""
    n = len(rec_means)
    rec_tds = np.zeros((n, n_sims), dtype=np.int64)
    pass_tds = np.zeros((n, n_sims), dtype=np.int64)
    for t in np.unique(team_codes):
        team = np.flatnonzero(team_codes == t)
        rows_q = team[pass_means[team] > 0]
        rows_r = team[rec_means[team] > 0]
        team_pass = float(pass_means[rows_q].sum())
        rec_sum = float(rec_means[rows_r].sum())
        # the unit's TRUE event count reconciles both sides: the larger
        # of the passer-mean sum and the catcher-mean sum, so NEITHER
        # side's marginal means get scaled (review #5 round 3 — the old
        # scale-down broke receiver marginals when rec_sum > team_pass).
        # The other-bucket on each side absorbs the difference.
        total_mean = max(team_pass, rec_sum)
        if total_mean <= 0 or not len(rows_q):
            # no rostered passer (or DST-only) — independent fallback
            for i in team:
                if rec_means[i] > 0:
                    rec_tds[i] = rng.poisson(rec_means[i], n_sims)
                if pass_means[i] > 0:
                    pass_tds[i] = rng.poisson(pass_means[i], n_sims)
            continue
        gm = game_mult[team[0]]  # shared within the (game, team) unit
        T = rng.poisson(total_mean * gm)
        probs_r = np.concatenate([rec_means[rows_r] / total_mean,
                                  [max(0.0, 1.0 - rec_sum / total_mean)]])
        if alloc_k is None:
            alloc_r = rng.multinomial(T, probs_r)  # (n_sims, k+1)
        else:
            # E[Dirichlet(k*p)] = p (up to the tiny alpha floor guarding
            # zero-mass buckets), so marginal TD means are preserved.
            p_r = rng.dirichlet(np.clip(alloc_k * probs_r, 1e-3, None),
                                size=T.shape[0])
            alloc_r = rng.multinomial(T, p_r)
        for j, i in enumerate(rows_r):
            rec_tds[i] = alloc_r[:, j]
        probs_q = np.concatenate([pass_means[rows_q] / total_mean,
                                  [max(0.0, 1.0 - team_pass / total_mean)]])
        if alloc_k is None:
            alloc_q = rng.multinomial(T, probs_q)
        else:
            p_q = rng.dirichlet(np.clip(alloc_k * probs_q, 1e-3, None),
                                size=T.shape[0])
            alloc_q = rng.multinomial(T, p_q)
        for j, i in enumerate(rows_q):
            pass_tds[i] = alloc_q[:, j]
    return rec_tds, pass_tds


def simulate(
    comps: pd.DataFrame,
    n_sims: int = 10_000,
    seed: int | None = None,
    keep_draws: bool = False,
    game_ids: pd.Series | None = None,
    team_ids: pd.Series | None = None,
    game_totals: pd.Series | None = None,
    bigplay_rate: pd.Series | None = None,
    params: dict[str, float] | None = None,
    env: Mapping[str, str] | None = None,
) -> SimResult:
    """game_ids (aligned to comps) enables correlated game environments:
    one shared lognormal factor per (game, sim) scales every player's
    opportunity in that game, so shootouts lift whole games together.
    Milly winners take 50-80% of their points from one game — without this
    the simulator prices such lineups as near-impossible. Mean-preserving
    (E[factor]=1), so projections are unchanged; only the joint tail moves.

    team_ids (aligned to comps, optional): only consulted when
    GAME_SIM_MODE=possession. Lets the two teams in a game draw DIFFERENT
    mean-preserving factors (game_sim.team_game_factors) instead of one
    shared value — the game-script asymmetry (leading team runs more,
    trailing team's DST/receivers skew differently) that's the possession
    sim's whole motivation over the shared lognormal factor. Without
    team_ids, possession mode falls back to one shared factor per game
    (game_sim.game_factor_matrix), same granularity as the lognormal draw.

    params (research/SBI calibration, plan §6 + §2.4): optional overrides
    for the registered simulator parameters — keys `game_factor_sigma`
    (lognormal sigma of the shared game factor), `usage_dirichlet_k`
    (within-team usage concentration; only fires under
    GAME_SIM_USAGE=dirichlet), `td_alloc_k` (passing-TD allocation
    concentration; only fires under TD_LEDGER=1). params=None — every
    production call — is REQUIRED to be byte-identical to the pre-params
    sampler: same RNG stream order, same draws (tests/test_sbi.py pins
    golden checksums). See src/nfl_dfs/research/sbi_params.py."""
    raw_components = comps
    comps = canonicalize_simulation_components(comps)
    raw_values = raw_components.to_numpy(dtype=np.float64)
    stable_values = comps.to_numpy(dtype=np.float64)
    finite = np.isfinite(raw_values) & np.isfinite(stable_values)
    max_adjustment = (float(np.max(np.abs(raw_values[finite]
                                         - stable_values[finite])))
                      if finite.any() else 0.0)
    log.info(
        "simulation components raw_sha256=%s stable_sha256=%s decimals=%d "
        "max_adjustment=%.3g",
        simulation_component_sha256(raw_components),
        simulation_component_sha256(comps), SIM_COMPONENT_DECIMALS,
        max_adjustment,
    )
    rng = np.random.default_rng(seed)
    n = len(comps)
    runtime_env = os.environ if env is None else env
    params = params or {}
    _sigma = float(params.get("game_factor_sigma", GAME_FACTOR_SIGMA))
    _usage_k = params.get("usage_dirichlet_k")  # None -> game_sim default
    _td_k = params.get("td_alloc_k")  # None -> exact multinomial (production)

    game_mult = np.ones((n, n_sims))
    if game_ids is not None:
        # NaN game_ids get UNIQUE labels (2026-08-04 audit): one shared
        # "_none" group gave unrelated fringe/cold-start players a common
        # game factor — fake cross-player correlation exactly where the
        # boom/tail machinery is most credulous.
        _g = pd.Series(game_ids).reset_index(drop=True)
        _g = _g.where(_g.notna(), "_none_" + _g.index.astype(str))
        codes, uniq = pd.factorize(_g.to_numpy())
        # GAME_SIM_MODE=possession swaps the lognormal game factor for the
        # drive-state Markov engine in game_sim.py (issue #13 item 6). Read
        # at call time like the other A/B env flags (N_DARKGAME, ALT_CEIL).
        # Off by default -- see reports/possession-simulator-design.md; its
        # transition probabilities are a placeholder, not yet fit from pbp.
        if runtime_env.get("GAME_SIM_MODE", "lognormal") == "possession":
            from . import game_sim
            # GAME_SIM_PACE=vegas conditions each game's DRIVE COUNT on its
            # vegas total (game_totals aligned to comps; pace = total /
            # slate mean). Pace is the only strength channel that survives
            # a mean-preserving factor -- an efficiency tilt (raising a
            # team's TD prob) cancels when the factor divides by its own
            # raised mean -- and it adds back a vegas-grounded shared
            # environment between the two teams' factors.
            paces = None
            if (runtime_env.get("GAME_SIM_PACE", "") == "vegas"
                    and game_totals is not None):
                gt = pd.to_numeric(pd.Series(game_totals).reset_index(drop=True),
                                   errors="coerce").to_numpy()
                per_game = pd.Series(gt).groupby(pd.Series(codes)).first()
                per_game = per_game.reindex(range(len(uniq))).to_numpy()
                league = np.nanmean(per_game)
                if league and not np.isnan(league) and league > 0:
                    paces = np.where(np.isnan(per_game), 1.0, per_game / league)
            # GAME_SIM_TEAM_FACTORS=0 forces the shared per-game factor even
            # when team_ids are supplied -- the middle arm of the 3-arm A/B
            # (lognormal / possession-shared / possession-team), so a team-arm
            # result can be attributed to team independence vs the drive
            # engine itself. See the design doc's correlation caveat.
            team_arm = runtime_env.get("GAME_SIM_TEAM_FACTORS", "1") != "0"
            if team_ids is not None and team_arm:
                team_series = pd.Series(team_ids).fillna("_none").reset_index(drop=True)
                game_series = pd.Series(codes)
                # Row order within each game group is player order, not a
                # kickoff coin flip -- "first" just needs to be a stable,
                # consistent pick per game so both of a game's teams land
                # on different slots; which team is slot 0 vs 1 doesn't
                # matter since factors_a/factors_b are symmetric in intent.
                first_team = team_series.groupby(game_series).transform("first")
                slot = (team_series != first_team).astype(int).to_numpy()
                factors_a, factors_b = game_sim.team_game_factors(
                    rng, len(uniq), n_sims, paces=paces)
                game_mult = np.where(slot[:, None] == 0, factors_a[codes], factors_b[codes])
            else:
                g = game_sim.game_factor_matrix(rng, len(uniq), n_sims, paces=paces)
                game_mult = g[codes]
        else:
            # _sigma == GAME_FACTOR_SIGMA whenever params is absent; the
            # lognormal call consumes the identical RNG stream either way.
            g = rng.lognormal(-_sigma ** 2 / 2, _sigma,
                              (len(uniq), n_sims))
            game_mult = g[codes]

    def col(name: str) -> np.ndarray:
        return np.nan_to_num(comps[name].to_numpy(dtype=float))[:, None]

    def opp(name: str) -> np.ndarray:
        """Opportunity means, scaled by the shared game factor per sim."""
        return col(name) * game_mult

    # GAME_SIM_USAGE=dirichlet (+ team_ids): correlated within-team usage.
    # Instead of each player independently Poisson-ing around their own
    # mean, each TEAM's total opportunity mean is split across teammates
    # by a Dirichlet draw centered on their shares
    # (game_sim.allocate_drive_usage), then Poisson-ed. Teammates become
    # negatively correlated (WR1 boom <-> WR2 squeeze) and low-share
    # players occasionally draw real volume -- the next-man-up boom
    # variance Addendum 24 found under-modeled. Mean-preserving:
    # E[Dirichlet share] = prior share. Off by default; same call-time
    # env pattern as GAME_SIM_MODE.
    usage_dirichlet = (runtime_env.get("GAME_SIM_USAGE", "") == "dirichlet"
                       and team_ids is not None)
    team_codes = None
    if usage_dirichlet:
        team_codes = _game_team_unit_codes(n, game_ids, team_ids)

    def opp_draw(name: str) -> np.ndarray:
        """Integer opportunity draws for stat `name` (targets/carries)."""
        means = opp(name)
        if not usage_dirichlet:
            return rng.poisson(means)
        from . import game_sim
        base = np.nan_to_num(comps[name].to_numpy(dtype=float))
        means = means.copy()
        for t in np.unique(team_codes):
            rows = np.flatnonzero((team_codes == t) & (base > 0))
            if len(rows) < 2:
                continue  # nothing to reallocate within
            shares = base[rows] / base[rows].sum()
            totals = means[rows].sum(axis=0)  # (n_sims,) game-factor-scaled
            alloc = game_sim.allocate_drive_usage(
                rng, totals, shares, n_sims=n_sims,
                concentration_scale=_usage_k)
            means[rows] = np.atleast_2d(alloc).T
        return rng.poisson(means)

    # TD_LEDGER=1 (review #5, Sol; grouping + RNG-parity fixes from
    # review #5 round 3): a passing TD and its catch are ONE EVENT.
    # The ledger draws each (GAME, TEAM) unit's passing-TD count once
    # (game-factor scaled) and allocates the same totals to catchers
    # and passers. When OFF (default), the draw ORDER below is byte-
    # identical to the pre-ledger sampler — the 2026-08-05 draw-order
    # regression shifted every default stream and forced a baseline
    # rebase; never again.
    td_ledger = (runtime_env.get("TD_LEDGER", "") not in ("", "0")
                 and team_ids is not None)
    _unit_codes = None
    if td_ledger:
        # group by (game, team): a season-level frame has each team in
        # ~17 games — factorizing team alone pooled a team's whole
        # season into one TD draw (the invalid TDLEDGER arm).
        _unit_codes = _game_team_unit_codes(n, game_ids, team_ids)

    targets = opp_draw("targets")
    receptions = rng.binomial(targets, col("catch_rate"))
    rec_yards = _gamma_yards(rng, receptions, col("ypr"))
    if not td_ledger:
        rec_tds = rng.poisson(col("rec_tds"), (n, n_sims))

    carries = opp_draw("carries")
    rush_yards = _gamma_yards(rng, carries, col("ypc"))
    rush_tds = rng.poisson(col("rush_tds"), (n, n_sims))

    attempts = rng.poisson(opp("pass_attempts"))
    pass_yards = _gamma_yards(rng, attempts, col("ypa"))
    if not td_ledger:
        pass_tds = rng.poisson(col("pass_tds"), (n, n_sims))
    interceptions = rng.poisson(col("interceptions"), (n, n_sims))

    if td_ledger:
        rec_tds, pass_tds = _td_event_ledger(
            rng, np.nan_to_num(comps["rec_tds"].to_numpy(dtype=float)),
            np.nan_to_num(comps["pass_tds"].to_numpy(dtype=float)),
            _unit_codes, game_mult, n_sims, alloc_k=_td_k)

    draws = dk_points(
        StatLine(
            pass_yards=pass_yards,
            pass_tds=pass_tds,
            interceptions=interceptions,
            rush_yards=rush_yards,
            rush_tds=rush_tds,
            receptions=receptions,
            rec_yards=rec_yards,
            rec_tds=rec_tds,
        )
    )

    # Big-play mixture (env BIGPLAY, off by default): explicit house-call
    # events for deep-threat profiles. Linear widening cannot create the
    # LUMP a deep WR's true distribution has (the 2-long-TD eruption --
    # Fuller 56.7 @ $4.5k, the event class real Milly winners are built
    # on, Addendum 38). Each event adds TD + long-catch yardage; the
    # expected addition is subtracted so E[row] is EXACTLY unchanged --
    # only the shape moves, mass migrates from the middle to the far
    # tail. bigplay_rate (aligned to comps) carries expected events/game
    # per player; callers derive it from the deep-target profile.
    if bigplay_rate is not None:
        rate = np.nan_to_num(
            pd.Series(bigplay_rate).reset_index(drop=True)
            .to_numpy(dtype=float)).clip(0.0, 0.5)[:, None]
        if rate.any():
            events = rng.poisson(rate, (n, n_sims))
            # long TD: 6 (TD) + 1 (catch) + ~45yd => ~4.5 yardage points
            yds = 30.0 + rng.exponential(15.0, (n, n_sims))
            lump_pts = 6.0 + 1.0 + yds / 10.0
            mean_lump = 6.0 + 1.0 + 4.5
            draws = draws + events * lump_pts - rate * mean_lump

    # proj_tail: mean of the top quartile of outcomes (ETR's ceiling
    # definition, vendor audit 2026-08-03) — a tail AVERAGE is more
    # stable than the p90 point and weighs the far tail the p90 ignores.
    srt = np.sort(draws, axis=1)
    q3 = srt[:, int(0.75 * srt.shape[1]):]
    summary = pd.DataFrame(
        {
            "proj_points": draws.mean(axis=1),
            "proj_p10": np.percentile(draws, 10, axis=1),
            "proj_p50": np.percentile(draws, 50, axis=1),
            "proj_p90": np.percentile(draws, 90, axis=1),
            "proj_tail": q3.mean(axis=1),
            "proj_std": draws.std(axis=1),
            "p_20_plus": (draws >= 20.0).mean(axis=1),
        },
        index=comps.index,
    )
    return SimResult(summary=summary, draws=draws if keep_draws else None)
