"""Backtest engine (guide §10): reconstruct historical slates, project with
point-in-time features only, build lineups, score against actuals, simulate
contest outcomes, report ROI.

Run over 3+ full seasons before risking money: single-season DFS results
are noise, and a bad model looks great over 17 weeks about as often as it
looks bad.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from time import perf_counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field as dc_field, replace as dc_replace

import numpy as np
import pandas as pd

from ..optimizer.lineup import (Lineup, StackRules, optimize, optimize_many,
                                select_tail_entries)
from ..research.candidate_features import PLAYER_SNAPSHOT_FEATURES
from . import field as field_sim
from .payout import Contest, roi

log = logging.getLogger(__name__)

REQUIRED_COLS = {"id", "name", "pos", "team", "opp", "game_id",
                 "salary", "proj", "actual"}


# ADOPTED generation budget. The independent-seed CE confirmation did not
# reproduce its initial threshold gain (26 clears vs the 27-boom control),
# so production uses the proven boom-only baseline. These are CODE defaults,
# not deployment env vars, so a redeploy cannot silently change generation.
GEN_TOTAL_BUDGET = 40      # replacement slots shared by boom/CE/EPI
DEFAULT_N_CE = 0
DEFAULT_N_BOOM = GEN_TOTAL_BUDGET                  # 40


# Replacement slots used by the archived CE paired-panel protocol. Both
# arms protect this many: 12 CE in treatment, 12 boom in control.
REPLACEMENT_SLOTS = 12
LATENT_ROLE_FAMILY = "latent_role_states"
_LATENT_STATE_ORDER = ("inactive", "dormant", "rotation", "secondary", "primary")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


# Every env capable of changing projections, simulation, generation, or
# selection belongs in the immutable candidate row.  The original short
# allow-list omitted EXTRA_FEATURES, so a feature treatment looked identical
# to its baseline in the warehouse; a later audit (2026-08-18, N5) found the
# same gap for SCRIPT_FEEDBACK, SCHAAKE_K, and nine optimizer knobs.  The
# registry is module-level so tests/test_lever_registry.py can enforce that
# every score-relevant environment read in the simulation/generation path is
# either registered here or explicitly exempted as infrastructure.
# Infrastructure destinations/credentials are deliberately out.  Adding a key
# here changes no recorded receipt unless a run actually sets that key.
_lever_keys = {
    "ALT_CEIL", "ATLAS_BOOM_WORLD_RANKING",
    "BIGPLAY", "BLEND_MODEL_WEIGHT", "BOOM_UNIQUE_FILL", "CAND_MULT",
    "CE_GAMES", "CE_SEED", "CONSTRUCTION_PRESET_ID",
    "DIRICHLET_K", "DIV_TILT", "DROP_FEATURES", "DST_CORR_DRAWS",
    "DST_PUNT_BONUS", "EMP_MARGINALS", "EMP_POS",
    "EPISTEMIC_FAMILY", "EPISTEMIC_W", "EXTRA_FEATURES",
    "ENSEMBLE_WORLD_MODE", "ENSEMBLE_WORLD_SEED",
    "FORBID_RB_DST", "FORBID_TWO_RB_SAME_TEAM",
    "GAME_SIM_MODE", "GAME_SIM_PACE", "GAME_SIM_TEAM_FACTORS",
    "GAME_SIM_USAGE", "GEN_POOL_CAP", "GEN_POOL_CAP_MAP",
    "GEN_TOTAL_BUDGET", "GUMBEL_MODE", "GUMBEL_SCALE",
    "GUMBEL_SEED", "HYPER_BOOM", "LEV_PENALTY",
    "LEV_POS_WEIGHTS", "LEV_SHAPE", "M4_QBLOCK", "MAX_OVERLAP",
    "MAX_PER_GAME", "MAX_QBS",
    "MIN_GAMES", "MIN_LINEUP_SALARY", "MIN_LOWOWN", "MODEL_ENSEMBLE",
    "MULTISEED_CANDIDATE_ENTRY_BASIS", "MULTISEED_PORTFOLIO",
    "MULTISEED_SEED_PAIRS", "MULTISEED_WORLDS_PER_BLOCK",
    "ARCHETYPE_ALLOCATION_VERSION", "ARCHETYPE_TAIL_LINE",
    "PROSPECTIVE_SHADOW_ID",
    "PROSPECTIVE_GENERATION_EXPOSURE",
    "MODEL_ENSEMBLE_MIX", "MODEL_REGISTRY_VARIANT",
    "N_BOOM", "N_CE", "N_DARKGAME", "N_LEV",
    "N_EPISTEMIC", "N_GAMESTACK", "N_GUMBEL", "N_LOWSAL",
    "N_ROUTE_TAIL", "N_COVERAGE_TAIL",
    "CAND_ARTIFACT_PLAYER_WORLDS",
    "N_MIDQB", "N_NOSTACK", "N_QB_VARIANTS", "OWN_BARBELL",
    "OWN_BARBELL_HIGH", "OWN_BARBELL_LOW", "OWN_BARBELL_NHIGH",
    "OWN_BARBELL_NLOW",
    "OWN_MODEL", "PEAK_SLICE", "PUNT_BOOM", "PUNT_BOOM_WR",
    "PUNT_MAX", "PUNT_MIN", "PUNT_SLOPE", "PUNT_STRICT", "PUNT_VALUE",
    "Q99_WILD", "QD_CELLS", "RATE_DENOM_WEIGHTS",
    "REPLACEMENT_SLOTS", "ROOKIE_WIDEN", "SCHAAKE_DIAG",
    "REPLAY_PROJECTION_SEED",
    "SIS_ASOE_BETA", "SIS_ASOE_TARGET_ALLOCATION",
    "SCHAAKE_DIAG_ONLY", "SCHAAKE_DIAG_STRICT", "SCHAAKE_K",
    "OPEN_BOOM_SOLVES", "SINGLE_STACK_BOOM_SOLVES",
    "SCHAAKE_TEMPLATE_MODE", "SCRIPT_FEEDBACK",
    "SELECT_LADDER", "SELECT_LSE", "SELECT_OBJ",
    "SERVED_POSITION_SCALES", "SERVED_TAIL_SCALE", "SHAPE_MIX",
    "SIM_WIDEN_DRAWS",
    "STACK_BRING_BACK",
    "STACK_QB_MIN", "TABPFN_COMPONENTS", "TABPFN_MARGINALS",
    "TABPFN_MARGINAL_TABLE",
    "TABPFN_MEAN", "TD_LEDGER", "TD_LEDGER_RANK_COUPLING",
    "TD_COMPETITIVE_WR_ALLOCATION",
    "TD_COMP_WR_EXACT80_LICENSED",
    "TD_COMP_WR_PROTOCOL_SHA256",
    "TD_COMP_WR_REFERENCE_REPORT_SHA256",
    "TD_COMP_WR_TREATMENT_REPORT_SHA256",
    "TRAIN_MAX_WEEK",
    "VALUE2_MAX", "VALUE2_MIN",
    "ROLE_BELIEF_FEATURES", "ROLE_BELIEF_SEED", "WR_BOOM",
}

# Environment keys the simulation/generation path may read WITHOUT lever
# registration: infrastructure destinations and provenance identity only.
# A key on this list must never change a projection, draw, candidate, or
# selection.  tests/test_lever_registry.py enforces the partition.
_lever_exempt_keys = frozenset({
    "CAND_ARTIFACT_BUCKET",   # GCS destination for score artifacts
    "CAND_FEATURE_TABLE",     # BigQuery feature-snapshot destination
    "CAND_LOG_TABLE",         # BigQuery candidate table destination
    "CODE_SHA",               # provenance fallback when .git is absent
    "MULTISEED_SOURCE_LABEL", # R0--R4 exposure-ledger provenance label
    "PANEL_RUN_ID",           # provenance label
    "REPLAY_LINEUPS_TABLE",   # BigQuery lineup table destination
    "SEEDS",                  # provenance metadata joined into run seeds
})


@dataclass(frozen=True)
class CandidateBatch:
    """A complete preselection candidate book and its aligned worlds.

    The live multi-seed portfolio needs to combine independently generated
    candidate books before running the unchanged production selector.  Keeping
    this boundary inside the engine means the final combined book still uses
    the existing oracle diagnostics, candidate persistence, score artifacts,
    thesis repair and selection code rather than a parallel implementation.
    """

    candidates: tuple[Lineup, ...]
    candidate_totals: np.ndarray
    player_ids: tuple[object, ...]
    player_rows: tuple[dict, ...]
    row_draws: np.ndarray
    all_tags: dict[frozenset, tuple[str, ...]]
    metadata: dict = dc_field(default_factory=dict)


def _validate_candidate_batch(batch: CandidateBatch) -> None:
    """Fail closed on a malformed capture/transform boundary."""
    if not isinstance(batch, CandidateBatch):
        raise TypeError("candidate transform must return CandidateBatch")
    n_candidates = len(batch.candidates)
    totals = np.asarray(batch.candidate_totals)
    row_draws = np.asarray(batch.row_draws)
    if totals.ndim != 2 or totals.shape[0] != n_candidates:
        raise ValueError("candidate batch totals are misaligned")
    if row_draws.ndim != 2 or row_draws.shape[0] != len(batch.player_ids):
        raise ValueError("candidate batch player worlds are misaligned")
    if totals.shape[1] != row_draws.shape[1]:
        raise ValueError("candidate and player world counts differ")
    if len(batch.player_rows) != len(batch.player_ids):
        raise ValueError("candidate batch player rows are misaligned")
    if len(set(batch.player_ids)) != len(batch.player_ids):
        raise ValueError("candidate batch player ids repeat")
    universe = set(batch.player_ids)
    roster_keys = []
    for lineup in batch.candidates:
        if len(lineup.players) != 9 or len(lineup.ids) != 9:
            raise ValueError("candidate batch contains an invalid roster")
        if not lineup.ids <= universe:
            raise ValueError("candidate roster is outside the player universe")
        roster_keys.append(lineup.ids)
    if len(set(roster_keys)) != len(roster_keys):
        raise ValueError("candidate batch contains duplicate rosters")


def pool_cap_for_slate(season: int, week: int, env: dict | None = None
                       ) -> int:
    """Per-slate cap, from GEN_POOL_CAP_MAP if present else GEN_POOL_CAP.

    A single scalar cap cannot equalize paired pools: realized counts
    vary by slate (~157-174 in the prior panel), so one number leaves
    some control slates under it and cuts some treatment slates and not
    others. The map is emitted by the CE-off control run keyed
    "season-week" and consumed verbatim by the treatment.
    """
    e = {} if env is None else env
    raw = e.get("GEN_POOL_CAP_MAP", "")
    if raw:
        try:
            import json as _json

            m = _json.loads(raw)
            v = m.get(f"{season}-{week}")
            if v is not None:
                return int(v)
            log.warning("no cap-map entry for %s wk%s — slate uncapped",
                        season, week)
            return 0
        except Exception:
            log.exception("GEN_POOL_CAP_MAP unparsable; falling back")
    return int(e.get("GEN_POOL_CAP", "0") or 0)


def trim_pool_to_cap(cands: list, cap: int, quotas: dict[str, int],
                     protect: tuple[str, ...] = ("ce", "epi"),
                     ) -> tuple[list, dict[str, int], dict[str, int]]:
    """Quota-aware deterministic trim -> (kept, retained, dropped).

    Tail truncation (`cands[:cap]`) is NOT a fair pool-size control:
    generators append in a fixed order, so the batch under test — CE is
    generated after lev/boom — is preferentially discarded, producing
    equal-sized pools but an unequal-opportunity comparison.

    Rules:
      * tags in `protect` (the arms under test) keep their full quota
        and are trimmed only if the protected set ALONE exceeds the cap
      * every other tag contributes proportionally via deterministic
        ROUND-ROBIN across tags (latest generation index first), so no
        single incumbent batch absorbs the whole trim and no tag is
        silently trim-eligible just because it lacks a quota entry
      * per-tag retained/dropped counts are returned for logging, so a
        confirmatory run can prove what its cap actually did
    """
    if cap <= 0 or len(cands) <= cap:
        keep = list(cands)
        dropped_idx: set[int] = set()
    else:
        by_tag: dict[str, list[int]] = {}
        for i, lu in enumerate(cands):
            by_tag.setdefault(lu.tag or "lev", []).append(i)
        protected: set[int] = set()
        pool_by_tag: dict[str, list[int]] = {}
        for tag, idxs in by_tag.items():
            if tag in protect:
                q = int(quotas.get(tag, len(idxs)))
                protected.update(idxs[:q])
                pool_by_tag[tag] = idxs[q:]
            else:
                pool_by_tag[tag] = list(idxs)
        n_drop = len(cands) - cap
        dropped_idx = set()
        # deterministic round-robin over tags, sorted for reproducibility
        while n_drop > 0 and any(pool_by_tag.values()):
            for tag in sorted(pool_by_tag):
                if n_drop <= 0:
                    break
                if pool_by_tag[tag]:
                    dropped_idx.add(pool_by_tag[tag].pop())  # latest first
                    n_drop -= 1
        if n_drop > 0:  # protected alone exceeds the cap
            prot_by_tag: dict[str, list[int]] = {}
            for i in sorted(protected):
                prot_by_tag.setdefault(cands[i].tag or "lev", []).append(i)
            while n_drop > 0 and any(prot_by_tag.values()):
                for tag in sorted(prot_by_tag):
                    if n_drop <= 0:
                        break
                    if prot_by_tag[tag]:
                        dropped_idx.add(prot_by_tag[tag].pop())
                        n_drop -= 1
        keep = [lu for i, lu in enumerate(cands) if i not in dropped_idx]
    retained: dict[str, int] = {}
    for lu in keep:
        retained[lu.tag or "lev"] = retained.get(lu.tag or "lev", 0) + 1
    dropped: dict[str, int] = {}
    for i in dropped_idx:
        t = cands[i].tag or "lev"
        dropped[t] = dropped.get(t, 0) + 1
    return keep, retained, dropped


def resolve_generation_budget(n_boom_solves: int | None = None,
                              env: dict | None = None
                              ) -> tuple[int, int, int]:
    """-> (n_ce, n_epistemic, n_boom) under one fixed total budget.

    Rules (agreed 2026-08-06):
      * no env               -> 0 CE / 40 boom, 40 total
      * explicit N_CE and/or N_EPISTEMIC without N_BOOM
                             -> boom = 40 - N_CE - N_EPISTEMIC
      * explicit N_BOOM      -> override, used verbatim
    Naively defaulting the boom ARGUMENT to 28 would double-subtract
    (28 - 12 = 16), which is why the resolution lives here instead of
    in the signature.
    """
    e = {} if env is None else env
    total = int(e.get("GEN_TOTAL_BUDGET", GEN_TOTAL_BUDGET)
                or GEN_TOTAL_BUDGET)
    n_ce = int(e.get("N_CE", DEFAULT_N_CE) or 0)
    n_epi = int(e.get("N_EPISTEMIC", "0") or 0)
    if "N_BOOM" in e:
        n_boom = int(e.get("N_BOOM") or 0)
    elif n_boom_solves is not None and n_boom_solves != GEN_TOTAL_BUDGET:
        # an explicit caller-supplied budget still wins over the default
        n_boom = max(0, n_boom_solves - n_ce - n_epi)
    else:
        # Bounds: without an explicit N_BOOM the total is a CONTRACT.
        # N_CE=50 previously yielded 50 CE / 0 boom while still claiming
        # a 40-slot budget; clamp loudly instead of silently exceeding.
        if n_ce + n_epi > total:
            log.warning("generation budget exceeded: N_CE=%d + N_EPISTEMIC=%d "
                        "> %d — clamping to the total", n_ce, n_epi, total)
            if n_ce >= total:
                n_ce, n_epi = total, 0
            else:
                n_epi = total - n_ce
        n_boom = max(0, total - n_ce - n_epi)
    return n_ce, n_epi, n_boom


def resolve_leverage_solves(
    candidate_multiple: int,
    candidate_generation_entries: int,
    env: dict | None = None,
) -> int:
    """Resolve the exact leverage-family solve count.

    The incumbent remains ``CAND_MULT * candidate_generation_entries``.
    ``N_LEV`` is an explicit research/shadow override for allocations that
    the integer multiplier cannot express, notably 40 leverage solves at the
    production 80-entry basis. Empty is treated as absent; a supplied value
    must be a canonical nonnegative integer so deployment typos fail before
    any optimizer work begins.
    """
    multiple = int(candidate_multiple)
    entries = int(candidate_generation_entries)
    if multiple < 0 or entries < 0:
        raise ValueError(
            "candidate multiplier and generation entries must be nonnegative"
        )
    e = {} if env is None else env
    raw = e.get("N_LEV")
    if raw in (None, ""):
        return multiple * entries
    if (
        not isinstance(raw, str)
        or re.fullmatch(r"0|[1-9][0-9]*", raw) is None
    ):
        raise ValueError("N_LEV must be a canonical nonnegative integer")
    return int(raw)


def _boom_structure_carve_counts(env, n_boom_solves: int) -> tuple[int, int]:
    """Return validated ``(open, exact-single-stack)`` boom carve doses."""
    values: list[int] = []
    for key in ("OPEN_BOOM_SOLVES", "SINGLE_STACK_BOOM_SOLVES"):
        raw = env.get(key, "0")
        if raw == "":
            raw = "0"
        if not isinstance(raw, str) or re.fullmatch(r"0|[1-9][0-9]*", raw) is None:
            raise ValueError(f"{key} must be a canonical nonnegative integer")
        value = int(raw)
        if value > n_boom_solves:
            raise ValueError(
                f"{key}={value} exceeds the {n_boom_solves} boom-solve budget")
        values.append(value)
    if values[0] and values[1]:
        raise ValueError(
            "OPEN_BOOM_SOLVES and SINGLE_STACK_BOOM_SOLVES are mutually exclusive")
    return values[0], values[1]


def effective_generation_config(env: dict | None = None) -> dict:
    """The config a RUNNING process will actually use, including any
    deployment override. The manifest proves CODE defaults; this proves
    what the live service resolved, so an unintended research override is
    visible in logs and health output rather than silent."""
    e = os.environ if env is None else env
    n_ce, n_epi, n_boom = resolve_generation_budget(env=e)
    n_lev_raw = e.get("N_LEV")
    n_lev = (
        None
        if n_lev_raw in (None, "")
        else resolve_leverage_solves(0, 0, env=e)
    )
    open_boom_solves, single_stack_boom_solves = (
        _boom_structure_carve_counts(e, n_boom)
    )
    n_gumbel = int(e.get("N_GUMBEL", "0") or 0)
    research_only = (
        "EPISTEMIC_FAMILY", "ROLE_BELIEF_FEATURES", "ROLE_BELIEF_SEED",
        "REPLAY_PROJECTION_SEED",
        "SIS_ASOE_TARGET_ALLOCATION", "SIS_ASOE_BETA",
        "TD_LEDGER_RANK_COUPLING",
        "GEN_POOL_CAP", "GEN_POOL_CAP_MAP", "GEN_TOTAL_BUDGET",
        "REPLACEMENT_SLOTS",
    )
    return {"n_ce": n_ce, "n_epistemic": n_epi, "n_boom": n_boom,
            "n_gumbel": n_gumbel,
            "total": n_ce + n_epi + n_boom + n_gumbel,
            "matches_adopted_default": (n_ce, n_epi, n_boom) ==
                                       (DEFAULT_N_CE, 0, DEFAULT_N_BOOM)
                                       and n_gumbel == 0
                                       and open_boom_solves == 0
                                       and single_stack_boom_solves == 0
                                       and n_lev is None
                                       and not any(k in e for k in research_only),
            "n_lev_override": n_lev,
            "ce_seed": int(e.get("CE_SEED", "1701") or 1701),
            "epistemic_family": e.get("EPISTEMIC_FAMILY", "standard"),
            "role_belief_seed": int(e.get("ROLE_BELIEF_SEED", "7331")
                                    or 7331),
            "replay_projection_seed": int(
                e.get("REPLAY_PROJECTION_SEED", "0") or 0),
            "gumbel_seed": int(e.get("GUMBEL_SEED", "4700") or 4700),
            "gumbel_mode": e.get("GUMBEL_MODE", "independent"),
            "overrides": {k: e[k] for k in
                          ("N_CE", "N_EPISTEMIC", "N_BOOM", "N_LEV", "CE_SEED",
                           "EPISTEMIC_FAMILY", "ROLE_BELIEF_FEATURES",
                           "ROLE_BELIEF_SEED",
                           "REPLAY_PROJECTION_SEED",
                           "SIS_ASOE_TARGET_ALLOCATION", "SIS_ASOE_BETA",
                           "TD_LEDGER_RANK_COUPLING",
                           "N_GUMBEL", "GUMBEL_SEED", "GUMBEL_SCALE",
                           "GUMBEL_MODE",
                           "OPEN_BOOM_SOLVES", "SINGLE_STACK_BOOM_SOLVES",
                           "REPLACEMENT_SLOTS", "GEN_TOTAL_BUDGET",
                           "GEN_POOL_CAP", "GEN_POOL_CAP_MAP") if k in e}}


def _gumbel_rng(env: dict | None = None) -> np.random.Generator:
    """Reproducible perturb-and-MAP stream for an auditable research arm."""
    e = {} if env is None else env
    return np.random.default_rng(int(e.get("GUMBEL_SEED", "4700") or 4700))


def _gumbel_perturbations(pool: list[dict], rng: np.random.Generator,
                          scale: float, mode: str = "independent"
                          ) -> np.ndarray:
    """Draw player objective shocks for perturb-and-MAP generation.

    ``hierarchical`` assigns equal variance to shared game, shared team,
    and idiosyncratic player components. Because Gumbel variance is
    proportional to scale squared, scaling each component by 1/sqrt(3)
    preserves the independent arm's total marginal perturbation variance.
    Players on opposing teams have target correlation 1/3; players on the
    same team have target correlation 2/3. This is one frozen mechanism,
    not a fitted or swept hyperparameter family.
    """
    if mode == "independent":
        return rng.gumbel(0.0, scale, size=len(pool))
    if mode != "hierarchical":
        raise ValueError(f"unknown GUMBEL_MODE={mode!r}")

    component_scale = scale / np.sqrt(3.0)
    # Center each component. The common mean is irrelevant to a MILP argmax,
    # but centering keeps diagnostics interpretable when levels are combined.
    center = np.euler_gamma * component_scale
    game_keys = [str(p.get("game_id") or f"__game_{i}")
                 for i, p in enumerate(pool)]
    team_keys = [(game_keys[i], str(p.get("team") or f"__team_{i}"))
                 for i, p in enumerate(pool)]
    game_shock = {k: rng.gumbel(0.0, component_scale) - center
                  for k in dict.fromkeys(game_keys)}
    team_shock = {k: rng.gumbel(0.0, component_scale) - center
                  for k in dict.fromkeys(team_keys)}
    player_shock = rng.gumbel(0.0, component_scale, size=len(pool)) - center
    return np.asarray([game_shock[game_keys[i]] + team_shock[team_keys[i]]
                       + player_shock[i] for i in range(len(pool))])


def _epistemic_scenarios(pool: list[dict], objective_col: str
                         ) -> list[tuple[str, np.ndarray]]:
    """Complete, preregisterable alternative mean vectors.

    Ensemble members are the primary scenarios.  Market/model alternatives
    are included only when the slate actually has those point-in-time
    inputs.  Game-specific alternatives replace the complete vector for a
    high-disagreement game; no player receives an independent p99-style
    bump merely because its disagreement magnitude is large.
    """
    if not pool:
        return []
    base = np.asarray([float(p[objective_col]) for p in pool])
    scenarios: list[tuple[str, np.ndarray]] = []
    member_cols = sorted({c for p in pool for c in p
                          if c.startswith("ensemble_point_")})
    for col in member_cols:
        values = np.asarray([p.get(col, np.nan) for p in pool], dtype=float)
        have = np.isfinite(values)
        if have.any():
            scenarios.append((col, np.where(have, values, base)))

    model = np.asarray([p.get("model_points_pre", np.nan) for p in pool],
                       dtype=float)
    market = np.asarray([p.get("market_points", np.nan) for p in pool],
                        dtype=float)
    have_model = np.isfinite(model)
    have_market = np.isfinite(market)
    if have_model.any() and have_market.any():
        mdl = np.where(have_model, model, base)
        mkt = np.where(have_market, market, mdl)
        w = float(os.environ.get("EPISTEMIC_W", "0.85"))
        scenarios.extend([
            ("market_heavy", w * mkt + (1.0 - w) * mdl),
            ("model_heavy", w * mdl + (1.0 - w) * mkt),
        ])
        game_scores: dict[str, float] = {}
        for i, p in enumerate(pool):
            gid = p.get("game_id")
            if gid and have_market[i] and have_model[i]:
                game_scores[gid] = game_scores.get(gid, 0.0) + abs(
                    model[i] - market[i])
        for gid in sorted(game_scores, key=game_scores.get, reverse=True)[:2]:
            in_game = np.asarray([p.get("game_id") == gid for p in pool])
            scenarios.append((f"game_model:{gid}",
                              np.where(in_game, mdl, base)))
            scenarios.append((f"game_market:{gid}",
                              np.where(in_game, mkt, base)))
    return scenarios


def _role_belief_scenarios(
    belief_slate: pd.DataFrame,
    belief_draws: np.ndarray,
    n_slots: int,
    env: Mapping[str, str] | None = None,
) -> list[tuple[str, np.ndarray]]:
    """Frozen role-model alternatives used only for candidate generation.

    Four slots reproduce the alternative model's leverage/mean family using
    the role slate's tournament objective. Remaining slots reproduce its boom
    family using the highest-total alternate-model worlds. The caller still
    scores every resulting roster with the baseline draw matrix.
    """
    if n_slots <= 0:
        return []
    objective = ("proj_tourney" if "proj_tourney" in belief_slate.columns
                 else "proj")
    mean = pd.to_numeric(belief_slate[objective], errors="coerce").to_numpy(
        dtype=float)
    if not np.isfinite(mean).all():
        raise ValueError("role-belief objective contains missing values")
    rd = _row_draws(belief_slate, belief_draws, env=env)
    if rd.shape[0] != len(belief_slate):
        raise ValueError("role-belief draw rows do not match the slate")
    mean_slots = min(4, n_slots)
    scenarios = [(f"role_mean:{i + 1}", mean.copy())
                 for i in range(mean_slots)]
    order = np.argsort(rd.sum(axis=0))[::-1]
    for rank, draw_ix in enumerate(order[:n_slots - mean_slots], start=1):
        scenarios.append((f"role_draw:{rank}:{int(draw_ix)}",
                          rd[:, draw_ix].astype(float, copy=True)))
    return scenarios


def _validated_latent_role_scenarios(
    scenarios: Sequence[tuple[str, np.ndarray]] | None,
    *,
    n_players: int,
    n_slots: int,
) -> list[tuple[str, np.ndarray]]:
    """Validate the frozen four-promotion/eight-sampled scenario contract."""
    if n_slots != 12:
        raise ValueError("latent role-state candidate dose must be exactly 12")
    if scenarios is None:
        raise RuntimeError("latent role-state scenarios are unavailable")
    normalized: list[tuple[str, np.ndarray]] = []
    names: list[str] = []
    for raw_name, raw_vector in scenarios:
        name = str(raw_name)
        vector = np.asarray(raw_vector, dtype=float)
        if vector.shape != (n_players,) or not np.isfinite(vector).all():
            raise ValueError(
                f"latent role-state scenario {name!r} is misaligned/nonfinite"
            )
        if name in names:
            raise ValueError("latent role-state scenario names repeat")
        names.append(name)
        normalized.append((name, vector.copy()))

    promotions = normalized[:4]
    if len(promotions) != 4:
        raise ValueError("latent role-state scenarios have fewer than 4 promotions")
    for sequence, (name, _) in enumerate(promotions, start=1):
        parts = name.split(":")
        if (
            len(parts) != 5
            or parts[0] != "latent_promotion"
            or parts[1] != str(sequence)
            or not parts[2]
            or ">" not in parts[3]
            or _SHA256_PATTERN.fullmatch(parts[4]) is None
        ):
            raise ValueError("latent role-state promotion order differs")
        source_state, promoted_state = parts[3].split(">", maxsplit=1)
        if (
            source_state not in _LATENT_STATE_ORDER
            or promoted_state not in _LATENT_STATE_ORDER
            or _LATENT_STATE_ORDER.index(promoted_state)
            <= _LATENT_STATE_ORDER.index(source_state)
        ):
            raise ValueError("latent role-state promotion identity is malformed")

    sampled = normalized[4:]
    attempts = []
    for name, _ in sampled:
        parts = name.split(":")
        if (
            len(parts) != 5
            or parts[0] != "latent_sampled"
            or parts[2] != "draw"
            or _SHA256_PATTERN.fullmatch(parts[4]) is None
        ):
            raise ValueError("latent role-state sampled identity is malformed")
        try:
            attempt = int(parts[1])
            draw_index = int(parts[3])
        except ValueError as exc:
            raise ValueError(
                "latent role-state sampled identity is malformed"
            ) from exc
        if not 1 <= attempt <= 50 or draw_index < 0:
            raise ValueError("latent role-state attempt/draw index is invalid")
        attempts.append(attempt)
    if attempts != sorted(set(attempts)):
        raise ValueError("latent role-state attempts are not strictly ordered")
    if len(sampled) < 8:
        raise ValueError("latent role-state scenarios have fewer than 8 samples")
    return normalized


def _latent_role_candidates(
    pool: list[dict],
    scenarios: Sequence[tuple[str, np.ndarray]],
    *,
    stack: StackRules | None,
    locks: set,
    env: dict,
    existing: set[frozenset],
    optimization_receipt: list[dict],
) -> list[tuple[Lineup, str]]:
    """Optimize the frozen four means and first eight novel sampled worlds."""
    if optimization_receipt:
        raise ValueError("latent role optimization receipt must start empty")
    produced: list[tuple[Lineup, str]] = []
    seen = set(existing)

    def _record(
        scenario: str,
        kind: str,
        disposition: str,
        lineup: Lineup | None = None,
        error: Exception | None = None,
    ) -> None:
        roster_sha256 = None
        if lineup is not None:
            payload = "\n".join(sorted(str(pid) for pid in lineup.ids))
            roster_sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        optimization_receipt.append({
            "scenario": scenario,
            "kind": kind,
            "disposition": disposition,
            "roster_sha256": roster_sha256,
            "error_type": type(error).__name__ if error is not None else None,
        })

    for sname, vector in scenarios[:4]:
        spool = [
            {**player, "proj_epi": float(vector[index])}
            for index, player in enumerate(pool)
        ]
        try:
            lineup = optimize(
                spool, stack=stack, objective_col="proj_epi",
                locks=set(locks), env=env,
            )
        except Exception as exc:
            _record(sname, "promotion", "optimization_error", error=exc)
            raise RuntimeError(
                f"latent role promotion {sname} optimization failed"
            ) from exc
        if lineup is None:
            _record(sname, "promotion", "infeasible")
            raise RuntimeError(
                f"latent role promotion {sname} is not a novel optimum"
            )
        if lineup.ids in seen:
            _record(sname, "promotion", "duplicate", lineup=lineup)
            raise RuntimeError(
                f"latent role promotion {sname} is not a novel optimum"
            )
        _record(sname, "promotion", "accepted", lineup=lineup)
        seen.add(lineup.ids)
        produced.append((lineup, sname))

    sampled_added = 0
    for sname, vector in scenarios[4:]:
        if sampled_added >= 8:
            break
        spool = [
            {**player, "proj_epi": float(vector[index])}
            for index, player in enumerate(pool)
        ]
        try:
            lineup = optimize(
                spool, stack=stack, objective_col="proj_epi",
                locks=set(locks), env=env,
            )
        except Exception as exc:
            _record(sname, "sampled", "optimization_error", error=exc)
            log.warning(
                "latent sampled scenario %s optimization failed: %s",
                sname, exc,
            )
            continue
        if lineup is None:
            _record(sname, "sampled", "infeasible")
            continue
        if lineup.ids in seen:
            _record(sname, "sampled", "duplicate", lineup=lineup)
            continue
        _record(sname, "sampled", "accepted", lineup=lineup)
        seen.add(lineup.ids)
        produced.append((lineup, sname))
        sampled_added += 1
    if len(produced) != 12 or sampled_added != 8:
        raise RuntimeError(
            "latent role-state generator did not produce exact "
            f"4+8 novel candidates (promotion=4 sampled={sampled_added})"
        )
    return produced


@dataclass
class WeekResult:
    season: int
    week: int
    lineups: list[Lineup]
    lineup_scores: list[float]
    percentiles: list[float]
    winnings: list[float]


@dataclass
class BacktestResult:
    weeks: list[WeekResult] = dc_field(default_factory=list)
    contest: Contest | None = None
    construction_preset_receipt: dict | None = None

    @property
    def total_roi(self) -> float:
        w = [x for wk in self.weeks for x in wk.winnings]
        return roi(np.array(w), self.contest.entry_fee) if w else 0.0

    def roi_by_season(self) -> dict[int, float]:
        out: dict[int, list[float]] = {}
        for wk in self.weeks:
            out.setdefault(wk.season, []).extend(wk.winnings)
        return {s: roi(np.array(w), self.contest.entry_fee) for s, w in out.items()}

    def summary(self) -> str:
        lines = [f"contest={self.contest.name}  entries={sum(len(w.winnings) for w in self.weeks)}"]
        for season, r in sorted(self.roi_by_season().items()):
            lines.append(f"  {season}: ROI {r:+.1%}")
        lines.append(f"  TOTAL: ROI {self.total_roi:+.1%}")
        med = np.median([p for wk in self.weeks for p in wk.percentiles] or [0])
        lines.append(f"  median finish percentile: {med:.1%} (lower is better)")
        return "\n".join(lines)


def leakage_guard(slate: pd.DataFrame) -> None:
    """Cheap structural checks that the slate frame is point-in-time: the
    projection must not equal the actual (a copied column is the classic
    reconstruction bug), and required columns exist."""
    missing = REQUIRED_COLS - set(slate.columns)
    if missing:
        raise ValueError(f"Slate missing columns: {sorted(missing)}")
    both = slate.dropna(subset=["proj", "actual"])
    if len(both) >= 30 and np.allclose(both["proj"], both["actual"]):
        raise AssertionError(
            "proj == actual for the whole slate; projections were "
            "reconstructed from the answer key."
        )


def _row_draws(slate: pd.DataFrame, draws: np.ndarray,
               env: dict | None = None) -> np.ndarray:
    """Per-slate-row draw matrix, aligned to slate row order. Rows without a
    draw (DST, draw_idx == -1) get their static projection in every sim.

    DST_CORR_DRAWS=1 (A/B, 2026-08-01): constants mean the tail selector
    can never prefer a DST for its boom worlds, even though DST scoring
    anti-correlates with the opposing offense (turnovers, points-allowed
    brackets) and 7/17 winning 2025 Milly punts were DSTs (Addendum 24).
    With the gate on, each DST row gets mean-preserving draws scaled by
    the INVERSE of its opponent's simulated offense total: mult =
    clip(2 - opp_total/mean, 0.3, 1.7), renormalized to mean 1."""
    runtime_env = {} if env is None else env

    di = slate["draw_idx"].to_numpy(dtype=int)
    out = np.empty((len(slate), draws.shape[1]), dtype=np.float32)
    has = di >= 0
    out[has] = draws[di[has]]
    out[~has] = slate["proj"].to_numpy(dtype=float)[~has, None]
    if runtime_env.get("DST_CORR_DRAWS") and (~has).any() and "opp" in slate.columns:
        # Fitted 2026-08-01 from 4,390 team-games 2018-25: DST DK points
        # correlate -0.491 with the opposing offense's total fantasy
        # points, with relative sd 0.93 (mean 6.2, sd 5.8). The first
        # (nulled) version had it backwards on both axes: ~-0.9 corr but
        # only ~0.3 rel-sd. Draws hit the measured moments exactly:
        # mult = 1 + rel_sd*(corr*z_opp + sqrt(1-corr^2)*z_iid), floored
        # (DK DST brackets go to -4) and renormalized to mean 1.
        DST_OPP_CORR, DST_REL_SD = -0.491, 0.93
        rng = np.random.default_rng(70921)  # distinct from marginal rng(seed+7) — audit
        teams = slate["team"].to_numpy()
        opps = slate["opp"].to_numpy()
        for i in np.flatnonzero(~has):
            rows = np.flatnonzero(has & (teams == opps[i]))
            if not len(rows):
                continue
            tot = draws[di[rows]].sum(axis=0)
            sd = tot.std()
            if sd <= 0 or tot.mean() <= 0:
                continue
            z_opp = (tot - tot.mean()) / sd
            z_iid = rng.standard_normal(tot.shape[0])
            mult = 1.0 + DST_REL_SD * (DST_OPP_CORR * z_opp
                                       + np.sqrt(1 - DST_OPP_CORR ** 2) * z_iid)
            mult = np.clip(mult, -0.7, None)
            out[i] = out[i] * (mult / mult.mean())
    return out


def _score_artifact_payload(
    cand_totals: np.ndarray,
    tail_line: float,
    *,
    slate: pd.DataFrame | None = None,
    row_draws: np.ndarray | None = None,
    include_player_worlds: bool = False,
) -> bytes:
    """Encode the immutable per-slate simulation artifact.

    Candidate totals are always retained.  Research panels may additionally
    retain the aligned player-by-world matrix so a roster found by one
    independent search seed can be scored honestly in every other seed's
    worlds.  The opt-in payload is deliberately stored in the same
    checksummed object; it does not change simulation or selection behavior.
    """
    import io

    totals = np.asarray(cand_totals, dtype=np.float32)
    if totals.ndim != 2:
        raise ValueError("candidate totals must be a two-dimensional matrix")
    arrays: dict[str, np.ndarray] = {
        "cand_ix": np.arange(len(totals), dtype=np.int32),
        "totals": totals,
        "tail_line": np.asarray(tail_line, dtype=np.float32),
    }
    if include_player_worlds:
        if slate is None or row_draws is None:
            raise ValueError(
                "player-world artifacts require the aligned slate and draws"
            )
        worlds = np.asarray(row_draws, dtype=np.float32)
        if worlds.ndim != 2 or worlds.shape[0] != len(slate):
            raise ValueError("player worlds do not align with the slate")
        if worlds.shape[1] != totals.shape[1]:
            raise ValueError("player and candidate world counts differ")
        player_ids = slate["id"].astype(str).to_numpy(dtype=str)
        if len(set(player_ids.tolist())) != len(player_ids):
            raise ValueError("player-world artifact ids are not unique")
        arrays["player_ids"] = player_ids
        arrays["player_draws"] = worlds
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arrays)
    return buffer.getvalue()


def _tier_thresholds(contest: Contest) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized form of Contest.payout_for_rank: cumulative field
    fractions and dollar payouts per tier."""
    cums, pays = [], []
    c = 0.0
    for top_frac, mult in contest.tiers:
        c += top_frac
        cums.append(c)
        pays.append(contest.entry_fee * mult)
    return np.asarray(cums), np.asarray(pays)


def select_dollar_entries(
    slate: pd.DataFrame,
    rd: np.ndarray,
    cands: list[Lineup],
    cand_totals: np.ndarray,
    n_entries: int,
    contest: Contest,
    sharp_fraction: float = 0.0,
    max_overlap: int = 7,
    n_field: int = 1000,
    n_sim_sub: int = 2000,
    seed: int = 42,
) -> list[int]:
    """SELECT_OBJ=dollars (2026-08-01): expected-DOLLARS entry selection.

    The tail-line objective is a step function at one line; real payouts
    are a curve. Here each candidate is scored by its expected winnings:
    a subsampled simulated FIELD (ownership-weighted lineups, scored in
    the SAME correlated sims as our candidates via the draw matrix) gives
    each candidate a per-sim rank, the contest curve converts rank to
    dollars, and E[$] is additive across entries -- so selection is
    greedy by E[$] under the uniqueness (max_overlap) constraint. This
    was issue #13's "expected-dollars objective once field model exists";
    the LineStar ownership model is that field model (pass model_own on
    the slate to use it)."""
    own_vec = (slate["model_own"].to_numpy()
               if "model_own" in slate.columns and slate["model_own"].notna().all()
               else None)
    fld = field_sim.sample_field(slate, n_lineups=n_field, seed=seed,
                                 ownership=own_vec,
                                 sharp_fraction=sharp_fraction)
    if not fld:
        return list(range(min(n_entries, len(cands))))
    rng = np.random.default_rng(seed)
    k_idx = rng.choice(rd.shape[1], size=min(n_sim_sub, rd.shape[1]),
                       replace=False)
    rd_sub = rd[:, k_idx]
    F = np.stack([rd_sub[f].sum(axis=0) for f in fld])  # (n_field, K)
    cums, pays = _tier_thresholds(contest)
    ct = cand_totals[:, k_idx]
    # Tail-resolved rank estimation (Addendum 34 fix): a coarse sampled
    # field resolves ranks only to 1/n_field, but GPP payouts concentrate
    # at 1e-5 of the field -- "beat the whole sample" spans $10..$100k.
    # Hybrid: empirical count where >= EMP_MIN field lineups are ahead;
    # otherwise a normal-tail extrapolation of the per-sim field score
    # distribution, capped by the empirical upper bound so the parametric
    # tail can only REFINE below sample resolution, never contradict it.
    EMP_MIN = 10
    from scipy.stats import norm

    mu = F.mean(axis=0)                                     # per-sim field mean
    sd = np.maximum(F.std(axis=0), 1e-6)
    n_f = F.shape[0]
    ev = np.empty(len(cands))
    for c in range(len(cands)):
        counts = (F > ct[c][None, :]).sum(axis=0)           # field ahead, sampled
        p_emp = counts / n_f
        p_par = norm.sf((ct[c] - mu) / sd)
        p_cap = (counts + 1.0) / n_f                        # empirical upper bound
        p = np.where(counts >= EMP_MIN, p_emp, np.minimum(p_par, p_cap))
        frac = p + 1.0 / contest.field_size                 # ~rank/field_size
        idx = np.searchsorted(cums, frac, side="left")
        pay = np.where(idx < len(pays), pays[np.minimum(idx, len(pays) - 1)], 0.0)
        ev[c] = float(pay.mean())
    order = np.argsort(ev)[::-1]
    picked: list[int] = []
    sel_ids: list[frozenset] = []
    for i in order:
        if len(picked) >= n_entries:
            break
        if all(len(cands[i].ids & s) <= max_overlap for s in sel_ids):
            picked.append(int(i))
            sel_ids.append(cands[i].ids)
    for i in order:  # fill if the overlap constraint ran the list dry
        if len(picked) >= n_entries:
            break
        if int(i) not in picked:
            picked.append(int(i))
    return picked


def route_tail_candidates(
    pool: list[dict],
    source_candidates: list[Lineup],
    *,
    stack: StackRules | None,
    locks: set,
    env: dict,
    n_candidates: int = 12,
) -> list[Lineup]:
    """Build the frozen added-budget Route Share candidate batch."""
    if n_candidates != 12:
        raise ValueError("the frozen Route Share candidate dose is 12")
    if not pool or any("route_delta_30" not in player for player in pool):
        raise ValueError("Route Share candidate signal is missing")
    delta = pd.to_numeric(pd.Series([
        player["route_delta_30"] for player in pool
    ]), errors="coerce").fillna(0.0)
    if not np.isfinite(delta.to_numpy(dtype=float)).all():
        raise ValueError("Route Share candidate signal is non-finite")
    if any("proj_tourney" not in player for player in pool):
        raise ValueError("Route Share requires the incumbent tourney objective")
    route_pool = [{
        **player,
        "proj_route_tail": float(
            player["proj_tourney"] + 30.0 * delta.iloc[index]),
    } for index, player in enumerate(pool)]
    banned = [lineup.ids for lineup in source_candidates]
    seen = set(banned)
    added: list[Lineup] = []
    for _ in range(n_candidates):
        lineup = optimize(
            route_pool, stack=stack, objective_col="proj_route_tail",
            locks=set(locks), banned_lineups=list(banned), max_overlap=8,
            env=env)
        if lineup is None or lineup.ids in seen:
            raise RuntimeError(
                "Route Share generator did not produce a novel roster")
        lineup.tag = "route_tail"
        banned.append(lineup.ids)
        seen.add(lineup.ids)
        added.append(lineup)
    return added


def coverage_tail_candidates(
    pool: list[dict],
    source_candidates: list[Lineup],
    *,
    stack: StackRules | None,
    locks: set,
    env: dict,
    n_candidates: int = 12,
) -> list[Lineup]:
    """Build the frozen added-budget prior-season coverage-fit batch."""
    if n_candidates != 12:
        raise ValueError("the frozen coverage-fit candidate dose is 12")
    if not pool or any("coverage_delta_30" not in player for player in pool):
        raise ValueError("coverage-fit candidate signal is missing")
    delta = pd.to_numeric(pd.Series([
        player["coverage_delta_30"] for player in pool
    ]), errors="coerce").fillna(0.0)
    if not np.isfinite(delta.to_numpy(dtype=float)).all():
        raise ValueError("coverage-fit candidate signal is non-finite")
    if any("proj_tourney" not in player for player in pool):
        raise ValueError("coverage-fit requires the incumbent tourney objective")
    coverage_pool = [{
        **player,
        "proj_coverage_tail": float(
            player["proj_tourney"] + 30.0 * delta.iloc[index]),
    } for index, player in enumerate(pool)]
    banned = [lineup.ids for lineup in source_candidates]
    seen = set(banned)
    added: list[Lineup] = []
    for _ in range(n_candidates):
        lineup = optimize(
            coverage_pool, stack=stack, objective_col="proj_coverage_tail",
            locks=set(locks), banned_lineups=list(banned), max_overlap=8,
            env=env)
        if lineup is None or lineup.ids in seen:
            raise RuntimeError(
                "coverage-fit generator did not produce a novel roster")
        lineup.tag = "coverage_tail"
        banned.append(lineup.ids)
        seen.add(lineup.ids)
        added.append(lineup)
    return added


def _boom_world_order(
    rd: np.ndarray,
    positions: Sequence[str],
    runtime_env,
) -> np.ndarray:
    """World visit order for the boom family.

    Control (default): descending total simulated slate points — the
    incumbent ranking. With ATLAS_BOOM_WORLD_RANKING set (research-only;
    the minimal world-selection C test, protocol
    20260818-atlas-minimal-world-selection-c-v1), rank instead by the
    roster-shaped attainable upper bound with the deterministic world-id
    tiebreak. Never set on production deployments; the key is recorded in
    the immutable lever set so any treatment is self-identifying in BQ.
    """
    if runtime_env.get("ATLAS_BOOM_WORLD_RANKING"):
        from ..analysis.atlas_world_ranking import (
            rank_worlds,
            roster_slot_upper_bound,
        )
        return rank_worlds(
            roster_slot_upper_bound(rd, positions), rd.shape[1])
    return np.argsort(rd.sum(axis=0))[::-1]


def tail_select_lineups(
    slate: pd.DataFrame,
    pool: list[dict],
    draws: np.ndarray,
    tail_line: float,
    n_entries: int,
    stack: StackRules | None,
    objective_col: str,
    candidate_multiple: int = 2,
    candidate_generation_entries: int | None = None,
    n_boom_solves: int = 40,
    n_game_stacks: int = 4,
    n_per_game: int = 3,
    contest: Contest | None = None,
    sharp_fraction: float = 0.0,
    locks: set | None = None,
    theses: list[dict] | None = None,
    cand_log_table: str | None = None,
    cand_log_async: bool = False,
    cand_log_required: bool = False,
    panel_run_id: str | None = None,
    candidate_run_type: str | None = None,
    belief_slate: pd.DataFrame | None = None,
    belief_draws: np.ndarray | None = None,
    explicit_epistemic_scenarios: (
        Sequence[tuple[str, np.ndarray]] | None
    ) = None,
    latent_optimization_receipt: list[dict] | None = None,
    latent_scenario_receipt: dict | None = None,
    policy_env: dict | None = None,
    candidate_capture: Callable[[CandidateBatch], None] | None = None,
    candidate_transform: (
        Callable[[CandidateBatch], CandidateBatch] | None
    ) = None,
    preseeded_role_identities: Sequence[frozenset] | None = None,
    construction_preset_receipt: Mapping[str, object] | None = None,
) -> list[Lineup]:
    """Entry selection on P(best-of-N >= tail_line) (guide: issue #5).

    Candidates come from two generators: the diverse leverage-objective
    batch (what we entered before), plus one solve per top-total sim —
    'if the slate booms like THIS, what's the best lineup?' — which yields
    genuinely boom-correlated entries the mean objective never builds.
    Selection is greedy sim-coverage (see select_tail_entries)."""
    if cand_log_required and cand_log_async:
        raise ValueError(
            "required candidate persistence cannot run asynchronously")
    runtime_env = {} if policy_env is None else policy_env
    generation_started = perf_counter()
    rd = _row_draws(slate, draws, env=runtime_env)
    locks = locks or set()
    # Dose lever (env N_BOOM, 2026-08-05 attribution: boom solves are
    # 13% of candidates but produce the weekly BEST in 29/54 weeks).
    baseline_boom_solves = n_boom_solves
    n_ce, n_epi, n_boom_solves = resolve_generation_budget(
        n_boom_solves, env=runtime_env)
    generation_entries = (
        n_entries if candidate_generation_entries is None
        else int(candidate_generation_entries)
    )
    if generation_entries < n_entries:
        raise ValueError(
            "candidate generation entry basis cannot be below selected entries")
    n_lev_solves = resolve_leverage_solves(
        candidate_multiple, generation_entries, env=runtime_env,
    )
    exposure_enabled = str(
        runtime_env.get("PROSPECTIVE_GENERATION_EXPOSURE", "") or ""
    ) == "1"
    exposure_ledger = None
    exposure_expected: dict[str, int] = {}
    if exposure_enabled:
        if theses:
            raise ValueError(
                "prospective exposure shadows do not support ad-hoc theses"
            )
        unsupported_exposure_families = (
            "HYPER_BOOM",
            "N_CE",
            "N_GUMBEL",
            "N_NOSTACK",
            "N_LOWSAL",
            "Q99_WILD",
            "QD_CELLS",
            "N_MIDQB",
            "N_ROUTE_TAIL",
            "N_COVERAGE_TAIL",
        )
        active_unsupported = [
            key for key in unsupported_exposure_families
            if int(runtime_env.get(key, "0") or 0) != 0
        ]
        if active_unsupported:
            raise ValueError(
                "prospective exposure ledger lacks complete attempt capture "
                f"for {active_unsupported}"
            )
        from ..inference.generation_exposure import SolveExposureLedger

        exposure_ledger = SolveExposureLedger(
            source_label=str(
                runtime_env.get("MULTISEED_SOURCE_LABEL") or "single"
            )
        )
        exposure_expected.update({
            "leverage": int(n_lev_solves),
            "boom": int(n_boom_solves),
        })

    def _record_exposure(
        *,
        family: str,
        requested_ordinal: int,
        status: str,
        retry_ordinal: int = 0,
        world_id: int | None = None,
        duration_seconds: float = 0.0,
        roster_ids=None,
    ) -> None:
        if exposure_ledger is not None:
            exposure_ledger.record(
                family=family,
                requested_ordinal=requested_ordinal,
                retry_ordinal=retry_ordinal,
                world_id=world_id,
                duration_seconds=duration_seconds,
                status=status,
                roster_ids=roster_ids,
            )

    def _leverage_attempt(event: Mapping[str, object]) -> None:
        _record_exposure(
            family="leverage",
            requested_ordinal=int(event["requested_ordinal"]),
            retry_ordinal=int(event["retry_ordinal"]),
            duration_seconds=float(event["duration_seconds"]),
            status=str(event["status"]),
            roster_ids=event.get("roster_ids"),
        )

    leverage_telemetry: dict[str, int] = {}
    leverage_started = perf_counter()
    cands = optimize_many(pool,
                          n_lineups=n_lev_solves,
                          stack=stack, objective_col=objective_col,
                          locks=set(locks), env=runtime_env,
                          telemetry=leverage_telemetry,
                          attempt_callback=(
                              _leverage_attempt if exposure_enabled else None
                          ))
    leverage_seconds = perf_counter() - leverage_started
    leverage_unique = len(cands)
    if exposure_ledger is not None:
        observed_leverage = {
            int(row["requested_ordinal"])
            for row in exposure_ledger.rows
            if row["family"] == "leverage"
        }
        for requested_ordinal in range(n_lev_solves):
            if requested_ordinal not in observed_leverage:
                _record_exposure(
                    family="leverage",
                    requested_ordinal=requested_ordinal,
                    status="exhausted",
                )
    # Multi-tag provenance (review #6, Sol): `seen` dedupes rosters, so a
    # lineup produced by BOTH lev and boom was attributed only to lev —
    # first-producer bias that invalidates generator analysis. all_tags
    # records EVERY producer; _note() is called at each generator site.
    all_tags: dict = {}

    def _note(ids, tag: str) -> None:
        tags = all_tags.setdefault(ids, [])
        if tag not in tags:
            tags.append(tag)
    for lu in cands:
        _note(lu.ids, "lev")
        lu.tag = "lev"
    seen = {lu.ids for lu in cands}
    epi_family = runtime_env.get("EPISTEMIC_FAMILY", "standard")
    if n_epi and epi_family == "role_draws":
        if (explicit_epistemic_scenarios is not None
                or latent_optimization_receipt is not None
                or latent_scenario_receipt is not None):
            raise ValueError("role_draws cannot receive latent scenarios/receipt")
        if belief_slate is None or belief_draws is None:
            raise RuntimeError(
                "role_draws treatment requires alternate belief slate/draws")
        if list(slate["id"]) != list(belief_slate["id"]):
            raise ValueError("baseline and role-belief slate ids are misaligned")
        epi_scenarios = _role_belief_scenarios(
            belief_slate, belief_draws, n_epi, env=runtime_env)
    elif n_epi and epi_family == LATENT_ROLE_FAMILY:
        if belief_slate is not None or belief_draws is not None:
            raise ValueError(
                "latent role-state scenarios cannot receive a belief slate"
            )
        if latent_optimization_receipt is None:
            raise ValueError("latent role-state optimization receipt is required")
        if not isinstance(latent_scenario_receipt, dict):
            raise ValueError("latent role-state scenario receipt is required")
        if latent_scenario_receipt.get("uses_realized_outcomes") is not False:
            raise ValueError("latent role-state scenario receipt is not score-free")
        epi_scenarios = _validated_latent_role_scenarios(
            explicit_epistemic_scenarios,
            n_players=len(pool),
            n_slots=n_epi,
        )
    elif n_epi and epi_family in ("", "standard"):
        if (explicit_epistemic_scenarios is not None
                or latent_optimization_receipt is not None
                or latent_scenario_receipt is not None):
            raise ValueError("standard EPI cannot receive latent scenarios/receipt")
        epi_scenarios = _epistemic_scenarios(pool, objective_col)
    elif n_epi:
        raise ValueError(f"unknown EPISTEMIC_FAMILY={epi_family!r}")
    else:
        if (explicit_epistemic_scenarios is not None
                or latent_optimization_receipt is not None
                or latent_scenario_receipt is not None):
            raise ValueError("latent scenarios/receipt require a nonzero dose")
        epi_scenarios = []
    if n_epi and not epi_scenarios:
        # A replacement arm must not silently remove incumbent generation
        # when its new point-in-time inputs are absent (the former behavior
        # made 2019/21/22 exactly 16 candidates smaller).
        log.warning("EPI inputs unavailable; restoring %d boom solves", n_epi)
        n_boom_solves = min(baseline_boom_solves,
                            n_boom_solves + n_epi)

    # Thesis candidates (2026-08-03, OWS "Bink Machine" pattern): each
    # thesis {players: [ids], min: k} guarantees the POOL holds enough
    # combo-containing builds; the post-selection repair below enforces
    # the portfolio floor. Builds TOWARD correlated convictions (pairs
    # with watchlist conversions) instead of only capping exposure.
    for th in (theses or []):
        combo = set(th.get("players") or ())
        need = int(th.get("min") or 0)
        if not combo or need <= 0:
            continue
        banned_th: list = []
        for _ in range(max(need, 2)):
            try:
                lu = optimize(pool, stack=stack, objective_col=objective_col,
                              locks=combo | set(locks),
                              banned_lineups=banned_th, max_overlap=7,
                              env=runtime_env)
            except Exception:
                break
            if lu is None:
                break
            banned_th.append(lu.ids)
            if lu is not None:
                _note(lu.ids, "thesis")   # every producer (A2.1)
            if lu.ids not in seen:
                lu.tag = "thesis"
                seen.add(lu.ids)
                cands.append(lu)
    if exposure_ledger is not None:
        exposure_expected["boom"] = int(n_boom_solves)
    boom_order = _boom_world_order(rd, slate["pos"].tolist(), runtime_env)
    # Research lever (env BOOM_UNIQUE_FILL, default off; N6/S5 arm,
    # protocol reports/2026-08-18-boom-unique-fill-protocol.md): the default
    # primary pass solves exactly the top-N worlds, so duplicate optima
    # silently deliver fewer than N unique boom candidates, and the CE/EPI
    # replacement passes both resume from a cursor that is never advanced.
    # With the lever set, the primary pass walks further down the world
    # order until exactly N unique boom rosters exist, and every boom pass
    # advances the shared cursor past the worlds it attempted.  Default
    # behavior is byte-identical to before the lever existed.
    boom_unique_fill = str(
        runtime_env.get("BOOM_UNIQUE_FILL", "") or "") not in ("", "0")
    if exposure_enabled and boom_unique_fill:
        raise ValueError(
            "prospective exposure ledger requires fixed requested boom work"
        )
    boom_cursor = 0 if boom_unique_fill else n_boom_solves
    boom_solve_attempts = 0
    boom_solve_successes = 0
    boom_solver_errors = 0
    boom_infeasible = 0
    boom_duplicates = 0
    # Fixed-budget structure carves. OPEN_BOOM_SOLVES is the closed A3
    # comparator. SINGLE_STACK_BOOM_SOLVES is a separate, default-off seam:
    # exactly k of the same deterministic boom visits require exactly one
    # QB WR/TE partner while preserving every incumbent bring-back, salary,
    # RB and game rule. They are mutually exclusive and never add solve slots.
    open_boom_solves, single_stack_boom_solves = (
        _boom_structure_carve_counts(runtime_env, n_boom_solves)
    )
    carve_count = open_boom_solves or single_stack_boom_solves
    if carve_count and stack is None:
        raise ValueError("boom structure carves require incumbent StackRules")
    if open_boom_solves:
        carve_key = "OPEN_BOOM_SOLVES"
        carve_tag = "open"
        carve_stack = dc_replace(
            stack, qb_stack_min=0, bring_back_min=0)
    elif single_stack_boom_solves:
        carve_key = "SINGLE_STACK_BOOM_SOLVES"
        carve_tag = "single_stack"
        carve_stack = dc_replace(
            stack, qb_stack_min=1, qb_stack_max=1)
    else:
        carve_key = ""
        carve_tag = ""
        carve_stack = None
    carve_stride = max(1, n_boom_solves // carve_count) if carve_count else 0
    carve_visits = {
        index * carve_stride for index in range(carve_count)
    }
    carve_attempts = 0
    carve_added = 0
    carve_rosters: set[frozenset] = set()

    def _add_boom(
        sim_indices,
        unique_target: int | None = None,
        apply_structure_carve: bool = False,
        exposure_family: str | None = None,
    ) -> int:
        nonlocal boom_cursor, boom_solve_attempts, boom_solve_successes
        nonlocal boom_solver_errors, boom_infeasible, boom_duplicates
        nonlocal carve_attempts, carve_added
        added = 0
        consumed = 0
        for k in sim_indices:
            if unique_target is not None and added >= unique_target:
                break
            exposure_request = consumed
            boom_solve_attempts += 1
            is_carved = apply_structure_carve and consumed in carve_visits
            consumed += 1
            if is_carved:
                carve_attempts += 1
            sim_pool = [{**p, "proj_sim": float(rd[i, k])}
                        for i, p in enumerate(pool)]
            solve_started = perf_counter()
            try:
                lu = optimize(sim_pool,
                              stack=carve_stack if is_carved else stack,
                              objective_col="proj_sim",
                              locks=set(locks), env=runtime_env)
            except Exception as exc:  # CBC subprocess flake: skip this draw
                solve_duration = perf_counter() - solve_started
                boom_solver_errors += 1
                if exposure_family is not None:
                    _record_exposure(
                        family=exposure_family,
                        requested_ordinal=exposure_request,
                        world_id=int(k),
                        duration_seconds=solve_duration,
                        status="error",
                    )
                if is_carved:
                    raise RuntimeError(
                        f"{carve_key} carved boom solve failed") from exc
                log.warning("boom-draw solve failed: %s", exc)
                continue
            solve_duration = perf_counter() - solve_started
            if is_carved and lu is None:
                boom_infeasible += 1
                if exposure_family is not None:
                    _record_exposure(
                        family=exposure_family,
                        requested_ordinal=exposure_request,
                        world_id=int(k),
                        duration_seconds=solve_duration,
                        status="infeasible",
                    )
                raise RuntimeError(f"{carve_key} carved boom solve was infeasible")
            if lu is None and exposure_family is not None:
                _record_exposure(
                    family=exposure_family,
                    requested_ordinal=exposure_request,
                    world_id=int(k),
                    duration_seconds=solve_duration,
                    status="infeasible",
                )
            elif lu is not None and exposure_family is not None:
                _record_exposure(
                    family=exposure_family,
                    requested_ordinal=exposure_request,
                    world_id=int(k),
                    duration_seconds=solve_duration,
                    status="dup" if lu.ids in seen else "new",
                    roster_ids=lu.ids,
                )
            if lu is not None:
                boom_solve_successes += 1
                _note(lu.ids, "boom")
                if is_carved:
                    # Secondary tag only: downstream family quotas continue
                    # to key on the primary "boom" tag.
                    _note(lu.ids, carve_tag)
                    carve_rosters.add(lu.ids)
            if lu is not None and lu.ids not in seen:
                if is_carved:
                    carve_added += 1
                lu.tag = "boom"
                seen.add(lu.ids)
                cands.append(lu)
                added += 1
            elif lu is None:
                boom_infeasible += 1
            elif not is_carved:
                # A valid solve can reproduce a roster already generated by
                # leverage or an earlier boom world.  That is deduplication,
                # not a solver failure, and is deliberately allowed in the
                # equal-requested-work boom-first experiment.
                boom_duplicates += 1
        if boom_unique_fill:
            boom_cursor += consumed
        return added

    primary_boom_started = perf_counter()
    primary_attempts_before = boom_solve_attempts
    primary_successes_before = boom_solve_successes
    primary_solver_errors_before = boom_solver_errors
    primary_infeasible_before = boom_infeasible
    primary_duplicates_before = boom_duplicates
    if boom_unique_fill:
        _primary_boom = _add_boom(
            boom_order, unique_target=n_boom_solves,
            apply_structure_carve=True,
            exposure_family="boom" if exposure_enabled else None)
        log.info(
            "boom unique-fill: %d/%d unique candidates from %d worlds "
            "attempted", _primary_boom, n_boom_solves, boom_cursor)
    else:
        _primary_boom = _add_boom(
            boom_order[:n_boom_solves], apply_structure_carve=True,
            exposure_family="boom" if exposure_enabled else None)
    primary_boom_attempts = boom_solve_attempts - primary_attempts_before
    primary_boom_successes = boom_solve_successes - primary_successes_before
    primary_boom_solver_errors = (
        boom_solver_errors - primary_solver_errors_before
    )
    primary_boom_infeasible = boom_infeasible - primary_infeasible_before
    primary_boom_duplicates = boom_duplicates - primary_duplicates_before
    primary_boom_failures = (
        primary_boom_solver_errors + primary_boom_infeasible
    )
    primary_boom_seconds = perf_counter() - primary_boom_started
    if carve_count and (
            carve_attempts != carve_count or len(carve_rosters) != carve_count
            or carve_added != carve_count):
        raise RuntimeError(
            f"{carve_key} shortfall: expected {carve_count} distinct carved "
            f"additions from {carve_count} visits, got {carve_added} additions, "
            f"{len(carve_rosters)} distinct rosters, and {carve_attempts} visits")
    # A/B lever (env HYPER_BOOM=<n games>, off by default; review #4
    # round 2): the sim's sampled worlds may never realize the
    # perfectly-collinear game scripts that break slates (45-42
    # shootouts where every participant hits p95+ TOGETHER). Rather
    # than wait for the sampler to roll one, MANUFACTURE it: for each
    # of the top-N games by projected total, build a synthetic world
    # where every player in that game sits at his own p98 draw and
    # everyone else at p50, then MILP-solve it. Injection via the
    # candidate pool (tag "hyper") — selection still decides.
    import os as _os

    n_hyper = int(runtime_env.get("HYPER_BOOM", "0") or 0)
    if n_hyper:
        game_tot: dict = {}
        for p in pool:
            gid = p.get("game_id")
            if gid:
                game_tot[gid] = game_tot.get(gid, 0.0) + float(p["proj"])
        q_hi = np.quantile(rd, 0.98, axis=1)
        q_md = np.quantile(rd, 0.50, axis=1)
        for gid in sorted(game_tot, key=game_tot.get,
                          reverse=True)[:n_hyper]:
            hpool = [{**p, "proj_hyper": float(
                q_hi[i] if p.get("game_id") == gid else q_md[i])}
                for i, p in enumerate(pool)]
            try:
                lu = optimize(hpool, stack=stack,
                              objective_col="proj_hyper",
                              locks=set(locks), env=runtime_env)
            except Exception as exc:
                log.warning("hyper-boom solve failed: %s", exc)
                continue
            if lu is not None:
                _note(lu.ids, "hyper")   # every producer (A2.1)
            if lu is not None and lu.ids not in seen:
                lu.tag = "hyper"
                seen.add(lu.ids)
                cands.append(lu)
    # Research lever (env N_CE, off by default; scoring plan §10): candidates
    # from LEARNED rare worlds. A cross-entropy loop searches the
    # bounded knob space (pace, pass tilt, scoring split, usage
    # concentration) for environments whose legal constrained oracle is
    # elite, then MILP-solves the elite worlds. Parameters are independent
    # per game; the former slate-global deformation and illegal greedy
    # nine-player proxy did not implement the preregistered experiment.
    if n_ce:
        ce_added = 0
        try:
            from ..research.ce_worlds import apply_knobs, ce_iterate

            game_totals: dict[str, float] = {}
            for p in pool:
                gid = p.get("game_id")
                if gid:
                    game_totals[gid] = game_totals.get(gid, 0.0) + float(
                        p[objective_col])
            max_games = int(runtime_env.get("CE_GAMES", "4") or 4)
            active_games = sorted(game_totals, key=game_totals.get,
                                  reverse=True)[:max_games]
            active = np.asarray([p.get("game_id") in active_games
                                 for p in pool])
            if not active.any():
                raise ValueError("CE requires game_id on the player pool")
            active_pool_idx = np.flatnonzero(active)
            active_game = pd.Categorical(
                [pool[i].get("game_id") for i in active_pool_idx],
                categories=active_games, ordered=True).codes
            active_team = pd.factorize(pd.Series(
                [pool[i].get("team") for i in active_pool_idx]).fillna("_"))[0]
            active_pass = np.asarray([
                str(pool[i].get("pos")) in ("QB", "WR", "TE")
                for i in active_pool_idx])
            base_mean = rd.mean(axis=1)

            def _world(knobs):
                w = base_mean.copy()
                w[active] = apply_knobs(
                    base_mean[active, None], knobs, active_team, active_pass,
                    active_game)[:, 0]
                return w

            def _score_world(knobs):
                w = _world(knobs)
                scored = [{**p, "proj_ce": float(w[i])}
                          for i, p in enumerate(pool)]
                lu = optimize(scored, stack=stack, objective_col="proj_ce",
                              locks=set(locks), env=runtime_env)
                if lu is None:
                    return -1e9
                return float(sum(w[i] for i, p in enumerate(pool)
                                 if p["id"] in lu.ids))

            # CE_SEED (2026-08-06): the world search was pinned to a
            # literal, so an 'independent seed' rerun would have
            # re-drawn the SAME elite worlds and proved nothing.
            ce_seed = int(runtime_env.get('CE_SEED', '1701') or 1701)
            rng_ce = np.random.default_rng(ce_seed)
            per_round = max(24, n_ce * 2)
            elites, iw, hist = ce_iterate(_score_world, rng_ce,
                                          n_per_round=per_round, rounds=3,
                                          elite_frac=0.5,
                                          n_games=len(active_games))
            log.info("CE: %d elite worlds, final ESS %.1f, elite score "
                     "%.1f -> %.1f (candidate-only weights, %d games)",
                     len(elites), hist[-1]["ess"],
                     hist[0]["all_mean_score"], hist[-1]["elite_mean_score"],
                     len(active_games))
            banned_ce: list[frozenset] = []
            for attempt in range(max(n_ce * 3, len(elites))):
                if ce_added >= n_ce:
                    break
                kn = elites[attempt % len(elites)]
                wmean = _world(kn)
                cpool = [{**p, "proj_ce": float(wmean[i])}
                         for i, p in enumerate(pool)]
                try:
                    lu = optimize(cpool, stack=stack, objective_col="proj_ce",
                                  locks=set(locks), banned_lineups=banned_ce,
                                  env=runtime_env)
                except Exception:
                    continue
                if lu is None:
                    continue
                banned_ce.append(lu.ids)
                _note(lu.ids, "ce")
                if lu.ids not in seen:
                    lu.tag = "ce"
                    seen.add(lu.ids)
                    cands.append(lu)
                    ce_added += 1
        except Exception:
            log.exception("CE world generation failed; pool unaffected")
        if ce_added < n_ce:
            missing = n_ce - ce_added
            log.warning("CE produced %d/%d unique candidates; replacing "
                        "the missing %d with boom worlds", ce_added, n_ce,
                        missing)
            _add_boom(boom_order[boom_cursor:], unique_target=missing)

    # Faithful-regeneration seam (ATLAS C freeze Amendment 4, 2026-08-19):
    # when a replay cannot regenerate the role family (its belief draws
    # come from the role registry pipeline), the registered role-native
    # identities enter the dedup universe HERE — the exact position the
    # role family occupied in the source run — so every later family
    # skips them exactly as the source did. Requires a zero role dose;
    # default None is byte-identical to before the seam existed.
    if preseeded_role_identities is not None:
        if n_epi:
            raise ValueError(
                "preseeded role identities require a zero role dose")
        validated_role_identities: list[frozenset[str]] = []
        for identity in preseeded_role_identities:
            frozen = frozenset(str(player) for player in identity)
            if len(frozen) != 9:
                raise ValueError(
                    "preseeded role identity is not nine unique players")
            validated_role_identities.append(frozen)
        if exposure_ledger is not None:
            exposure_ledger.register_preexisting_rosters(
                validated_role_identities
            )
        seen.update(validated_role_identities)

    # A/B lever (env N_EPISTEMIC, off by default; scoring plan §8):
    # EPISTEMIC-scenario candidates. Every existing generator samples
    # the same aleatoric worlds the selector scores against — a closed
    # loop. These instead encode alternative BELIEFS about the means:
    # complete ensemble-member vectors, market/model blends and complete
    # high-disagreement-game alternatives. No independent player p99 boost
    # is used. Missing inputs are replaced by incumbent boom slots.
    epi_added = 0
    role_retry_by_request: dict[int, int] = {}
    if exposure_ledger is not None and n_epi:
        exposure_expected["role_epistemic"] = int(n_epi)
    if n_epi and epi_scenarios and epi_family == LATENT_ROLE_FAMILY:
        if exposure_ledger is not None:
            raise ValueError(
                "prospective exposure ledger does not support latent-role "
                "internal solve attempts"
            )
        latent_candidates = _latent_role_candidates(
            pool,
            epi_scenarios,
            stack=stack,
            locks=set(locks),
            env=runtime_env,
            existing=seen,
            optimization_receipt=latent_optimization_receipt,
        )
        for lu, sname in latent_candidates:
            lu.tag = "epi"
            _note(lu.ids, "epi")
            _note(lu.ids, f"epi:{sname}")
            seen.add(lu.ids)
            cands.append(lu)
            epi_added += 1
    elif n_epi and epi_scenarios:
        banned_epi: list[frozenset] = []
        max_attempts = max(n_epi * 3, len(epi_scenarios))
        for attempt in range(max_attempts):
            if epi_added >= n_epi:
                break
            requested_ordinal = epi_added
            retry_ordinal = role_retry_by_request.get(
                requested_ordinal, 0
            )
            sname, vector = epi_scenarios[attempt % len(epi_scenarios)]
            spool = [{**p, "proj_epi": float(vector[i])}
                     for i, p in enumerate(pool)]
            solve_started = perf_counter()
            try:
                lu = optimize(spool, stack=stack, objective_col="proj_epi",
                              locks=set(locks), banned_lineups=banned_epi,
                              env=runtime_env)
            except Exception as exc:
                solve_duration = perf_counter() - solve_started
                _record_exposure(
                    family="role_epistemic",
                    requested_ordinal=requested_ordinal,
                    retry_ordinal=retry_ordinal,
                    duration_seconds=solve_duration,
                    status="error",
                )
                role_retry_by_request[requested_ordinal] = retry_ordinal + 1
                log.warning("epistemic solve failed: %s", exc)
                continue
            solve_duration = perf_counter() - solve_started
            if lu is None:
                _record_exposure(
                    family="role_epistemic",
                    requested_ordinal=requested_ordinal,
                    retry_ordinal=retry_ordinal,
                    duration_seconds=solve_duration,
                    status="infeasible",
                )
                role_retry_by_request[requested_ordinal] = retry_ordinal + 1
                continue
            banned_epi.append(lu.ids)
            _note(lu.ids, "epi")
            _note(lu.ids, f"epi:{sname}")
            _record_exposure(
                family="role_epistemic",
                requested_ordinal=requested_ordinal,
                retry_ordinal=retry_ordinal,
                duration_seconds=solve_duration,
                status="dup" if lu.ids in seen else "new",
                roster_ids=lu.ids,
            )
            role_retry_by_request[requested_ordinal] = retry_ordinal + 1
            if lu.ids not in seen:
                lu.tag = "epi"
                seen.add(lu.ids)
                cands.append(lu)
                epi_added += 1
        if epi_added < n_epi:
            # Preserve the candidate-generation budget when scenario solves
            # fail or duplicate incumbent candidates.
            missing = n_epi - epi_added
            if epi_family in {"role_draws", LATENT_ROLE_FAMILY}:
                raise RuntimeError(
                    f"role-belief generator produced {epi_added}/{n_epi} "
                    "unique replacement candidates")
            log.warning("EPI produced %d/%d unique candidates; replacing "
                        "the missing %d with boom worlds", epi_added, n_epi,
                        missing)
            _add_boom(boom_order[boom_cursor:], unique_target=missing)

    # A/B lever (env N_GUMBEL, off by default; 2026-08-05 GFN gate):
    # Gumbel-perturbed MILP objectives — perturb-and-MAP diverse-mode
    # sampling. In the GFlowNet's own equal-count gate this cheap trick
    # produced +6.8 union frontier gain vs repeated-MILP (world-argmax
    # +7.9, GFlowNet +5.4) at ~zero compute. Injection via pool, tag
    # "gumbel"; selection decides. GUMBEL_SCALE in DK points (default
    # 2.0, the gate's setting).
    n_gumbel = int(runtime_env.get("N_GUMBEL", "0") or 0)
    if n_gumbel:
        _grng = _gumbel_rng(runtime_env)
        _gscale = float(runtime_env.get("GUMBEL_SCALE", "2.0") or 2.0)
        _gmode = runtime_env.get("GUMBEL_MODE", "independent")
        log.info("Gumbel generator: mode=%s scale=%.3f seed=%s n=%d",
                 _gmode, _gscale, runtime_env.get("GUMBEL_SEED", "4700"),
                 n_gumbel)
        for _ in range(n_gumbel * 3):
            _noise = _gumbel_perturbations(pool, _grng, _gscale, _gmode)
            gpool = [{**p, "proj_gum": float(
                p[objective_col] + _noise[i])} for i, p in enumerate(pool)]
            try:
                lu = optimize(gpool, stack=stack, objective_col="proj_gum",
                              locks=set(locks), env=runtime_env)
            except Exception as exc:
                log.warning("gumbel solve failed: %s", exc)
                continue
            if lu is not None:
                _note(lu.ids, "gumbel")   # every producer (A2.1)
                _note(lu.ids, f"gumbel:{_gmode}")
            if lu is not None and lu.ids not in seen:
                lu.tag = "gumbel"
                seen.add(lu.ids)
                cands.append(lu)
            if sum(1 for c in cands if c.tag == "gumbel") >= n_gumbel:
                break

    # Anti-correlation A/B (env N_NOSTACK): candidates with NO stack
    # rules — pure variance plays; coverage selection decides if any
    # earn slots. Prior is low (all 48 studied Milly winners stacked).

    n_nostack = int(runtime_env.get("N_NOSTACK", "0"))
    if n_nostack:
        banned_ns = []
        for _ in range(n_nostack):
            try:
                lu = optimize(pool, stack=None, objective_col=objective_col,
                              banned_lineups=banned_ns, max_overlap=7,
                              locks=set(locks), env=runtime_env)
            except Exception:
                break
            if lu is None:
                break
            banned_ns.append(lu.ids)
            if lu is not None:
                _note(lu.ids, "nostk")   # every producer (A2.1)
            if lu.ids not in seen:
                lu.tag = "nostk"
                seen.add(lu.ids)
                cands.append(lu)
    # Low-salary candidate batch (env N_LOWSAL, off by default;
    # underspend-family redesign 2026-08-03): the validated $49k floor
    # pushes every candidate into near-cap build space; these solves at
    # a $47k floor reach constructions the floor forbids, and the
    # coverage selector decides if any earn slots (the original
    # underspend-dedup died with the WRONG rationale — dupe avoidance;
    # ours measure ~0 — this one is pure coverage breadth).
    n_lowsal = int(runtime_env.get("N_LOWSAL", "0"))
    if n_lowsal:
        banned_ls: list = []
        for _ in range(n_lowsal):
            try:
                lu = optimize(pool, stack=stack, objective_col=objective_col,
                              banned_lineups=banned_ls, max_overlap=7,
                              min_salary=47_000, env=runtime_env)
            except Exception:
                break
            if lu is None:
                break
            banned_ls.append(lu.ids)
            if lu is not None:
                _note(lu.ids, "lowsal")   # every producer (A2.1)
            if lu.ids not in seen:
                lu.tag = "lowsal"
                seen.add(lu.ids)
                cands.append(lu)
    # Ceiling-wildcard injection (env Q99_WILD=N, off by default;
    # 2026-08-05 gap decomposition: the 16% of hindsight-optimal players
    # we NEVER rostered are mid-cheap booms — mean $4.8k, mean 30.3 pts,
    # Achane 54.3 — that mean-anchored candidates skip). For each of the
    # week's top-N TabPFN-q99 sub-$6.5k skill players not already in any
    # candidate, solve ONE lineup locking him in; the selector judges.
    # INJECTION, not tilt — ALT_CEIL/WRBOOM failed as tilts (Add. 60).
    n_wild = int(runtime_env.get("Q99_WILD", "0") or 0)
    if n_wild:
        try:
            from ..bq import query_df as _qdf
            from ..config import settings as _st

            season_w = int(slate.season.iloc[0])
            week_w = int(slate.week.iloc[0])
            qq = _qdf(f"SELECT gsis_id, q99 FROM "
                      f"`{_st.features}.tabpfn_projections` WHERE "
                      f"season={season_w} AND week={week_w}")
            qmap = dict(zip(qq.gsis_id, qq.q99))
            covered = {p["id"] for lu in cands for p in lu.players}
            wild = sorted(
                (p for p in pool
                 if p.get("gsis_id") in qmap and p["salary"] <= 6500
                 and p["pos"] != "DST" and p["id"] not in covered),
                key=lambda p: -qmap[p["gsis_id"]])[:n_wild]
            for wp in wild:
                try:
                    lu = optimize(pool, stack=stack,
                                  objective_col=objective_col,
                                  locks={wp["id"]} | set(locks),
                                  max_overlap=7, env=runtime_env)
                except Exception:
                    continue
                if lu is not None:
                    _note(lu.ids, "wild")   # every producer (A2.1)
                if lu is not None and lu.ids not in seen:
                    lu.tag = "wild"
                    seen.add(lu.ids)
                    cands.append(lu)
        except Exception:
            log.exception("q99 wildcards unavailable; batch skipped")
    # Quality-diversity archive batch (env QD_CELLS = elites per cell,
    # off by default; MAP-Elites idea, research round 8 2026-08-03): the
    # named batches above are a hand-made archive; this tessellates the
    # descriptor space the real Milly winners actually occupy —
    # max-per-game concentration {2,3,4} (winners avg 2.96) x salary band
    # (winners spend the cap, but coverage may pay off-cap) — and solves
    # the best lineups per cell. Same tail-coverage selector downstream
    # decides which cells earn entries; empty/infeasible cells just skip.
    n_qd = int(runtime_env.get("QD_CELLS", "0"))
    if n_qd:
        for mpg in (2, 3, 4):
            for lo, hi in ((44_000, 47_500), (47_500, 49_000),
                           (49_000, 50_000)):
                banned_qd: list = []
                for _ in range(n_qd):
                    try:
                        lu = optimize(pool, stack=stack,
                                      objective_col=objective_col,
                                      banned_lineups=banned_qd,
                                      max_overlap=7, locks=set(locks),
                                      min_salary=lo, max_salary=hi,
                                      max_per_game=mpg, env=runtime_env)
                    except Exception:
                        break
                    if lu is None:
                        break
                    banned_qd.append(lu.ids)
                    if lu is not None:
                        _note(lu.ids, "qd")   # every producer (A2.1)
                    if lu.ids not in seen:
                        lu.tag = "qd"
                        seen.add(lu.ids)
                        cands.append(lu)
    # Stack-depth A/B (env N_QB_VARIANTS): the harvest attribution found
    # the 40 entries spread over ~16 QBs with max 2-of-8 overlap vs the
    # weekly optimal — right stacks, wrong pieces. For each of the top-8
    # QBs by simulated p90, build several catcher-combination variants
    # (same QB, different pieces) so the pool holds real depth per stack.
    # ADOPTED 2026-08-04 (QF arm, final-exam combos): default 4. QBVAR4
    # alone +2 tails (25/107); with OWN_MODEL=fade, equal 25 tails, best
    # median of the program (14.6%) and two >=237 weeks. "0" disables.
    n_qbvar = int(runtime_env.get("N_QB_VARIANTS", "4"))
    if n_qbvar:
        qb_all = [(i, p) for i, p in enumerate(pool) if p["pos"] == "QB"]
        qb_all.sort(key=lambda t: -float(np.percentile(rd[t[0]], 90)))
        qb_targets = qb_all[:8]
        if exposure_ledger is not None:
            exposure_expected["qb_variant"] = len(qb_targets) * n_qbvar
        for qb_index, (_, qb) in enumerate(qb_targets):
            banned_qv: list = []
            for variant_index in range(n_qbvar):
                requested_ordinal = qb_index * n_qbvar + variant_index
                solve_started = perf_counter()
                try:
                    lu = optimize(pool, stack=stack,
                                  objective_col=objective_col,
                                  locks={qb["id"]} | set(locks),
                                      banned_lineups=banned_qv,
                                      max_overlap=6, env=runtime_env)
                except Exception:
                    solve_duration = perf_counter() - solve_started
                    _record_exposure(
                        family="qb_variant",
                        requested_ordinal=requested_ordinal,
                        duration_seconds=solve_duration,
                        status="error",
                    )
                    for remaining in range(variant_index + 1, n_qbvar):
                        _record_exposure(
                            family="qb_variant",
                            requested_ordinal=qb_index * n_qbvar + remaining,
                            status="exhausted",
                        )
                    break
                solve_duration = perf_counter() - solve_started
                if lu is None:
                    _record_exposure(
                        family="qb_variant",
                        requested_ordinal=requested_ordinal,
                        duration_seconds=solve_duration,
                        status="infeasible",
                    )
                    for remaining in range(variant_index + 1, n_qbvar):
                        _record_exposure(
                            family="qb_variant",
                            requested_ordinal=qb_index * n_qbvar + remaining,
                            status="exhausted",
                        )
                    break
                banned_qv.append(lu.ids)
                _record_exposure(
                    family="qb_variant",
                    requested_ordinal=requested_ordinal,
                    duration_seconds=solve_duration,
                    status="dup" if lu.ids in seen else "new",
                    roster_ids=lu.ids,
                )
                if lu is not None:
                    _note(lu.ids, "qbvar")   # every producer (A2.1)
                if lu.ids not in seen:
                    lu.tag = "qbvar"
                    seen.add(lu.ids)
                    cands.append(lu)
    # Mid-tier QB A/B (env N_MIDQB): one candidate locked on each of the
    # top-N $4-6.5k QBs by simulated p90 — targets the measured miss zone
    # (17/41 top-scorer misses were QBs, 27/41 mid-salary).
    n_midqb = int(runtime_env.get("N_MIDQB", "0"))
    if n_midqb:
        qb_rows = [(i, p) for i, p in enumerate(pool)
                   if p["pos"] == "QB" and 4000 < p["salary"] <= 6500]
        qb_rows.sort(key=lambda t: -float(np.percentile(rd[t[0]], 90)))
        for _, qb in qb_rows[:n_midqb]:
            try:
                lu = optimize(pool, stack=stack, objective_col=objective_col,
                              locks={qb["id"]} | set(locks), env=runtime_env)
            except Exception:
                continue
            if lu is not None:
                _note(lu.ids, "midqb")   # every producer (A2.1)
            if lu is not None and lu.ids not in seen:
                lu.tag = "midqb"
                seen.add(lu.ids)
                cands.append(lu)
    # Concentrated game stacks (issue #6): for each top game environment,
    # force >= 5 players from that game. Winners take 50-80% of points
    # from one game; these are deliberately lower-mean, higher-variance
    # candidates — coverage selection decides how many survive.
    game_proj = (slate[slate.get("game_id").notna()]
                 .groupby("game_id")["proj"].sum().sort_values(ascending=False)
                 if "game_id" in slate.columns else pd.Series(dtype=float))
    game_targets = list(game_proj.head(n_game_stacks).index)
    if exposure_ledger is not None and game_targets:
        exposure_expected["game_stack"] = len(game_targets) * n_per_game
    for game_index, gid in enumerate(game_targets):
        banned = []
        for game_variant in range(n_per_game):
            requested_ordinal = game_index * n_per_game + game_variant
            solve_started = perf_counter()
            try:
                lu = optimize(pool, stack=stack, objective_col=objective_col,
                              game_lock=(gid, 5), banned_lineups=banned,
                              max_overlap=7, locks=set(locks),
                              env=runtime_env)
            except Exception as exc:
                solve_duration = perf_counter() - solve_started
                _record_exposure(
                    family="game_stack",
                    requested_ordinal=requested_ordinal,
                    duration_seconds=solve_duration,
                    status="error",
                )
                for remaining in range(game_variant + 1, n_per_game):
                    _record_exposure(
                        family="game_stack",
                        requested_ordinal=game_index * n_per_game + remaining,
                        status="exhausted",
                    )
                log.warning("game-stack solve failed (%s): %s", gid, exc)
                break
            solve_duration = perf_counter() - solve_started
            if lu is None:
                _record_exposure(
                    family="game_stack",
                    requested_ordinal=requested_ordinal,
                    duration_seconds=solve_duration,
                    status="infeasible",
                )
                for remaining in range(game_variant + 1, n_per_game):
                    _record_exposure(
                        family="game_stack",
                        requested_ordinal=game_index * n_per_game + remaining,
                        status="exhausted",
                    )
                break
            banned.append(lu.ids)
            _record_exposure(
                family="game_stack",
                requested_ordinal=requested_ordinal,
                duration_seconds=solve_duration,
                status="dup" if lu.ids in seen else "new",
                roster_ids=lu.ids,
            )
            if lu is not None:
                _note(lu.ids, "game")   # every producer (A2.1)
            if lu.ids not in seen:
                lu.tag = "game"
                seen.add(lu.ids)
                cands.append(lu)
    # Dark-game A/B (env N_DARKGAME): concentrated stacks from games
    # RANKED 5+ by projected total — 29% of matched 2025 Milly winners
    # stacked a game ranked 8th-14th on the slate (addendum 20 study).
    n_dark = int(runtime_env.get("N_DARKGAME", "10"))
    if n_dark and len(game_proj) > n_game_stacks:
        dark_targets = list(
            game_proj.index[n_game_stacks:n_game_stacks + n_dark]
        )
        if exposure_ledger is not None:
            exposure_expected["dark_game"] = len(dark_targets)
        for dark_index, gid in enumerate(dark_targets):
            solve_started = perf_counter()
            try:
                lu = optimize(pool, stack=stack, objective_col=objective_col,
                              game_lock=(gid, 5), locks=set(locks),
                              env=runtime_env)
            except Exception:
                solve_duration = perf_counter() - solve_started
                _record_exposure(
                    family="dark_game",
                    requested_ordinal=dark_index,
                    duration_seconds=solve_duration,
                    status="error",
                )
                continue
            solve_duration = perf_counter() - solve_started
            if lu is None:
                _record_exposure(
                    family="dark_game",
                    requested_ordinal=dark_index,
                    duration_seconds=solve_duration,
                    status="infeasible",
                )
            else:
                _record_exposure(
                    family="dark_game",
                    requested_ordinal=dark_index,
                    duration_seconds=solve_duration,
                    status="dup" if lu.ids in seen else "new",
                    roster_ids=lu.ids,
                )
            if lu is not None:
                _note(lu.ids, "dark")   # every producer (A2.1)
            if lu is not None and lu.ids not in seen:
                lu.tag = "dark"
                seen.add(lu.ids)
                cands.append(lu)
    if not cands:
        return []
    # Exact realized-pool control (2026-08-06 audit): holding SOLVE budget
    # constant is not the same as holding the realized unique-candidate
    # count constant — dedup rates differ per arm, so the CE fixed-budget
    # comparison ran 166.35 vs 166.29 candidates in 2019, 166.50 vs 166.28
    # in 2023, etc. With an adopted lift of only +2 clears, that slack is
    # not negligible. GEN_POOL_CAP trims deterministically (by generation
    # order, which is itself deterministic) so two arms can be compared at
    # byte-identical pool size.
    # season/week are optional on a slate frame (live/ad-hoc builds and
    # several fixtures omit them); the cap map is keyed by them, so a
    # frame without them is simply uncapped rather than an exception.
    _season = (int(slate["season"].iloc[0])
               if "season" in slate.columns and len(slate) else 0)
    _week = (int(slate["week"].iloc[0])
             if "week" in slate.columns and len(slate) else 0)
    # Realized pool size is logged ALWAYS (not only when trimming) so a
    # CE-off control run can emit the per-slate cap manifest the paired
    # treatment arm consumes.
    log.info("pool size: %s wk%s n=%d", _season, _week, len(cands))
    _cap = pool_cap_for_slate(_season, _week, env=runtime_env)
    if _cap and len(cands) > _cap:
        # PAIRED replacement-slot policy: treatment protects the novel
        # candidates under test; control protects the same number of the
        # boom slots they replace. Otherwise a cap could retain a novel
        # arm more aggressively than the incumbent it displaces.
        if n_ce or n_epi or n_gumbel:
            _quotas = {"ce": n_ce, "epi": n_epi, "gumbel": n_gumbel}
            _protect = tuple(k for k, v in _quotas.items() if v)
        else:
            _replacement_slots = int(
                runtime_env.get("REPLACEMENT_SLOTS", REPLACEMENT_SLOTS)
                or REPLACEMENT_SLOTS)
            _quotas = {"boom": _replacement_slots}
            _protect = ("boom",)
        cands, _ret, _drop = trim_pool_to_cap(cands, _cap, _quotas,
                                              protect=_protect)
        log.info("pool trimmed to cap %d (protect=%s): retained=%s "
                 "dropped=%s", _cap, _protect, _ret, _drop)
    log.info("pool final: %s wk%s n=%d cap=%s", _season, _week,
             len(cands), _cap or "none")
    # Paid Route Share confirmatory arm. This is an added-budget generator,
    # so it runs only after the incumbent cap. Every source roster is banned
    # at exact-nine overlap, guaranteeing twelve genuinely novel candidates
    # without changing a production world or optimizer constraint.
    n_route_tail = int(runtime_env.get("N_ROUTE_TAIL", "0") or 0)
    if n_route_tail:
        if n_route_tail != 12:
            raise ValueError("the frozen Route Share candidate dose is 12")
        if _season in (2024, 2025):
            route_batch = route_tail_candidates(
                pool, cands, stack=stack, locks=set(locks), env=runtime_env,
                n_candidates=n_route_tail)
            for lu in route_batch:
                _note(lu.ids, "route_tail")
                seen.add(lu.ids)
                cands.append(lu)
            log.info("Route Share added %d novel candidates", len(route_batch))
    # Prior-season coverage-fit confirmatory arm. It runs after Route so a
    # combined treatment cannot relabel a Route candidate as coverage novelty.
    n_coverage_tail = int(runtime_env.get("N_COVERAGE_TAIL", "0") or 0)
    if n_coverage_tail:
        if n_coverage_tail != 12:
            raise ValueError("the frozen coverage-fit candidate dose is 12")
        if _season in (2024, 2025):
            coverage_batch = coverage_tail_candidates(
                pool, cands, stack=stack, locks=set(locks), env=runtime_env,
                n_candidates=n_coverage_tail)
            for lu in coverage_batch:
                _note(lu.ids, "coverage_tail")
                seen.add(lu.ids)
                cands.append(lu)
            log.info(
                "coverage-fit added %d novel candidates", len(coverage_batch))
    id2row = {pid: i for i, pid in enumerate(slate["id"])}
    cand_totals = np.stack([
        rd[[id2row[p["id"]] for p in lu.players]].sum(axis=0) for lu in cands
    ])
    generation_exposure_ledger = (
        exposure_ledger.finalize(
            expected_requests_by_family=exposure_expected
        )
        if exposure_ledger is not None
        else None
    )
    native_batch = CandidateBatch(
        candidates=tuple(cands),
        candidate_totals=cand_totals,
        player_ids=tuple(slate["id"].tolist()),
        player_rows=tuple(slate.to_dict("records")),
        row_draws=rd,
        all_tags={key: tuple(value) for key, value in all_tags.items()},
        metadata={
            "season": _season,
            "week": _week,
            "tail_line": float(tail_line),
            "n_entries": int(n_entries),
            "candidate_generation_entries": generation_entries,
            "model_version": str(slate.attrs.get("model_version") or ""),
            "role_model_version": str(
                slate.attrs.get("role_model_version") or ""
            ),
            "candidate_input_receipt": dict(
                slate.attrs.get("candidate_input_receipt") or {}
            ),
            "construction_preset_receipt": dict(
                construction_preset_receipt or {}
            ),
            "role_candidate_input_receipt": dict(
                slate.attrs.get("role_candidate_input_receipt") or {}
            ),
            "generation_allocation": {
                "leverage_requested": int(n_lev_solves),
                "leverage_unique": int(leverage_unique),
                "leverage_solve_attempts": int(
                    leverage_telemetry.get("solve_attempts", 0)
                ),
                "leverage_solver_errors": int(
                    leverage_telemetry.get("solver_errors", 0)
                ),
                "leverage_infeasible": int(
                    leverage_telemetry.get("infeasible", 0)
                ),
                "leverage_successful": int(
                    leverage_telemetry.get("successful", 0)
                ),
                "boom_requested": int(n_boom_solves),
                "boom_attempted": int(primary_boom_attempts),
                "boom_successful": int(primary_boom_successes),
                "boom_solver_errors": int(primary_boom_solver_errors),
                "boom_infeasible": int(primary_boom_infeasible),
                "boom_duplicates": int(primary_boom_duplicates),
                "boom_failures": int(primary_boom_failures),
                "boom_unique_added": int(_primary_boom),
                "boom_unique_fill": bool(boom_unique_fill),
                "ce_requested": int(n_ce),
                "role_or_epistemic_requested": int(n_epi),
                "gumbel_requested": int(n_gumbel),
                "core_requested": int(n_lev_solves + n_boom_solves),
                "total_requested_with_replacement_families": int(
                    n_lev_solves + n_boom_solves + n_ce + n_epi + n_gumbel
                ),
                "unique_candidates_after_all_families": int(len(cands)),
            },
            "generation_timing_seconds": {
                "leverage": float(leverage_seconds),
                "primary_boom": float(primary_boom_seconds),
                "all_generation_through_candidate_matrix": float(
                    perf_counter() - generation_started
                ),
            },
            "generation_exposure_ledger": generation_exposure_ledger,
            "latent_optimization_receipt": tuple(
                latent_optimization_receipt or ()
            ),
            "latent_scenario_receipt": dict(latent_scenario_receipt or {}),
        },
    )
    effective_batch_metadata = native_batch.metadata
    _validate_candidate_batch(native_batch)
    if candidate_capture is not None:
        candidate_capture(native_batch)
    if candidate_transform is not None:
        transformed = candidate_transform(native_batch)
        _validate_candidate_batch(transformed)
        if transformed.player_ids != native_batch.player_ids:
            raise ValueError(
                "candidate transform changed the canonical player order")
        cands = list(transformed.candidates)
        cand_totals = np.asarray(
            transformed.candidate_totals, dtype=np.float32)
        rd = np.asarray(transformed.row_draws, dtype=np.float32)
        all_tags = {
            key: list(value) for key, value in transformed.all_tags.items()
        }
        effective_batch_metadata = transformed.metadata
        log.info(
            "candidate transform: %d candidates, %d worlds, metadata=%s",
            len(cands), cand_totals.shape[1], transformed.metadata)
    if runtime_env.get("SELECT_OBJ") == "dollars" and contest is not None:
        picked = select_dollar_entries(slate, rd, cands, cand_totals,
                                       n_entries, contest,
                                       sharp_fraction=sharp_fraction)
    elif int(runtime_env.get("M4_QBLOCK", "0") or 0):
        # Review #4 F5: at tiny N (the 4-entry Milly slice) coverage
        # buys 4 disparate "flat tires"; concentrate instead — all
        # entries share the QB family whose candidates jointly clear
        # the line most often, varying only the ancillary pieces.
        picked = _select_qb_concentrated(cands, cand_totals, n_entries,
                                         tail_line)
    else:
        max_qbs = int(runtime_env.get("MAX_QBS", "0"))
        if max_qbs:
            qb_of = [next((p["id"] for p in lu.players if p["pos"] == "QB"),
                          None) for lu in cands]
            picked = _select_tail_qb_capped(cand_totals, n_entries,
                                            tail_line, qb_of, max_qbs)
        else:
            picked = select_tail_entries(cand_totals, n_entries, tail_line,
                                         env=runtime_env)
    # Peak slice (env PEAK_SLICE, 2026-08-05 null-model finding: our
    # assembly is BELOW-RANDOM — 1.87/8 best-entry overlap with the
    # hindsight-optimal vs 2.51 expected under exposure-preserving
    # random assembly; the diversity objective scatters winning
    # combinations). Reserve the final K slots for the highest
    # individual P(>= line) candidates, coverage-penalty-exempt.
    k_peak = int(runtime_env.get("PEAK_SLICE", "0") or 0)
    if k_peak > 0 and len(picked) > k_peak:
        p_line = (cand_totals >= tail_line).mean(axis=1)
        keep = list(picked[:len(picked) - k_peak])
        pool_ix = [int(i) for i in np.argsort(p_line)[::-1]
                   if int(i) not in set(keep)]
        picked = keep + pool_ix[:k_peak]
    if theses:
        picked = _enforce_theses(picked, cands, cand_totals, tail_line,
                                 theses)
    # Candidate-oracle instrumentation (review #5 F1, always on): the
    # selected 40 are all we ever scored against actuals — the
    # PRESELECTION frontier was unobserved, so "the wall is the
    # generator" rested on selected-set evidence only. Log, per week:
    # the best ACTUAL score any candidate achieves vs the best
    # selected, how many unselected candidates clear the line the
    # selected set missed, and where the actual-best candidate sat in
    # the sim's own ranking.
    try:
        actuals = np.array([
            sum(float(p.get("actual") or 0) for p in lu.players)
            for lu in cands])
        sel = set(int(i) for i in picked)
        sel_best = max((actuals[i] for i in sel), default=0.0)
        orc_ix = int(np.argmax(actuals))
        extra = sum(1 for i in range(len(cands))
                    if i not in sel and actuals[i] >= tail_line)
        p_line_all = (cand_totals >= tail_line).mean(axis=1)
        orc_simrank = int((p_line_all > p_line_all[orc_ix]).sum()) + 1
        log.info(
            "cand-oracle: n_cand %d  oracle %.1f (%s, sim-rank %d, "
            "selected %s)  selected-best %.1f  gap %.1f  "
            "unselected>=line %d",
            len(cands), actuals[orc_ix], cands[orc_ix].tag or "lev",
            orc_simrank, orc_ix in sel, sel_best,
            actuals[orc_ix] - sel_best, extra)
    except Exception:
        log.exception("cand-oracle instrumentation failed")
    # Candidate persistence (explicit cand_log_table param, or env
    # CAND_LOG_TABLE for replay arms — never global mutation): the
    # reranker (September designs #3) needs every week's FULL candidate
    # pool with sim features, selection outcome, and enough PROVENANCE
    # to tell repeated/custom builds apart. Live passes
    # cand_log_async=True so a stalled warehouse call can never block
    # lineup generation (review #5 round 3).
    _cand_tbl = (cand_log_table if cand_log_table is not None
                 else runtime_env.get("CAND_LOG_TABLE"))
    if _cand_tbl:
        try:
            import json
            import uuid
            from datetime import datetime, timezone

            from ..bq import load_dataframe

            p_line_all = (cand_totals >= tail_line).mean(axis=1)
            sel_order = {int(ix): rank for rank, ix in enumerate(picked)}
            rows = []
            now = datetime.now(timezone.utc)
            # A2.3 two-level identity: PANEL_RUN_ID is set once per
            # six-season invocation (harvest driver exports it); the
            # slate id is per (season, week). A per-slate-only uuid made
            # partial reruns look like independent panels.
            persist_panel_run_id = (panel_run_id if panel_run_id is not None
                                    else runtime_env.get("PANEL_RUN_ID", ""))
            slate_run_id = uuid.uuid4().hex[:12]
            # Run provenance (Sol audit 3): panel+slate ids alone cannot
            # detect a mixed-config panel. Capture what identifies the
            # BUILD and the CONFIG, cheaply and without failing the run.
            # Containers intentionally do not contain .git.  Merely calling
            # `git` does not raise there: it returns a non-zero result with an
            # empty stdout, so the old exception-only fallback silently wrote
            # a blank code_sha even when deployment supplied CODE_SHA.
            _sha = runtime_env.get("CODE_SHA", "").strip()
            _dirty = False
            try:
                import subprocess
                _rev = subprocess.run(
                    ["git", "rev-parse", "HEAD"], capture_output=True,
                    text=True, timeout=5)
                if _rev.returncode == 0 and _rev.stdout.strip():
                    _sha = _rev.stdout.strip()[:12]
                    _stat = subprocess.run(
                        ["git", "status", "--porcelain"],
                        capture_output=True, text=True, timeout=5)
                    _dirty = (_stat.returncode == 0
                              and bool(_stat.stdout.strip()))
            except Exception:
                pass
            _sha = _sha or "unknown"
            try:
                from ..research.config_manifest import manifest_hash
                _cfg = manifest_hash()
            except Exception:
                _cfg = ""
            _seeds = runtime_env.get("SEEDS", "")
            # Research-generator seeds belong in run metadata: an
            # independent-seed rerun is auditable only when the seeds
            # that produced candidates are stored with the rows.
            _seeds = ";".join(x for x in (
                _seeds,
                (f"REPLAY_PROJECTION_SEED="
                 f"{runtime_env['REPLAY_PROJECTION_SEED']}"
                 if "REPLAY_PROJECTION_SEED" in runtime_env else ""),
                f"CE_SEED={runtime_env.get('CE_SEED', '1701')}",
                f"ROLE_BELIEF_SEED={runtime_env.get('ROLE_BELIEF_SEED', '7331')}",
                f"GUMBEL_SEED={runtime_env.get('GUMBEL_SEED', '4700')}",
                (f"ENSEMBLE_WORLD_SEED="
                 f"{runtime_env.get('ENSEMBLE_WORLD_SEED', '8161')}"
                 if runtime_env.get("ENSEMBLE_WORLD_MODE") else ""))
                if x)
            from ..models.components import (
                effective_ensemble_size, ensemble_member_specs)
            _ensemble_size = effective_ensemble_size(runtime_env)
            _ensemble_spec = json.dumps(
                ensemble_member_specs(runtime_env),
                separators=(",", ":"), sort_keys=True)
            _seeds = ";".join(x for x in (
                _seeds,
                f"MODEL_ENSEMBLE_SIZE={_ensemble_size}",
                f"MODEL_MEMBER_SPEC={_ensemble_spec}") if x)
            _levers = ",".join(sorted(
                f"{k}={v}" for k, v in runtime_env.items()
                if k in _lever_keys))
            # A2.2 labels: `or 0` turned MISSING actuals into real-looking
            # zeros, so unlabeled live candidates appeared labeled. Labels
            # are populated ONLY when every player has an actual.
            vals = [[p.get("actual") for p in lu.players] for lu in cands]
            complete = [all(v is not None and not pd.isna(v) for v in row)
                        for row in vals]
            labels_complete = bool(complete) and all(complete)
            if labels_complete:
                acts = np.array([sum(map(float, row)) for row in vals])
                # explicit ranking method (ties -> min), not double argsort
                act_rank = pd.Series(-acts).rank(method="min").astype(int).to_numpy()
            else:
                acts = np.full(len(cands), np.nan)
                act_rank = np.full(len(cands), -1)
            sim_sd = cand_totals.std(axis=1)
            qs = np.quantile(cand_totals, [0.5, 0.9, 0.99], axis=1)
            # A2.4 masks: store the FULL world mask (no silent 2048
            # truncation) plus n_worlds/bitorder, and preregistered
            # masks at 187/194/200 plus prospective-only 210/220 masks so
            # frozen live books can target the operator's extreme-tail
            # utility without resimulation or post-outcome rule changes.
            n_worlds = int(cand_totals.shape[1])
            grid = (187.0, 194.0, 200.0, 210.0, 220.0)
            grid_masks = {g: (cand_totals >= g) for g in grid}
            for ix, lu in enumerate(cands):
                rows.append({
                    "generated_at": now,
                    "panel_run_id": persist_panel_run_id,
                    "slate_run_id": slate_run_id,
                    "run_type": (candidate_run_type or
                                 ("replay" if labels_complete
                                  else "live_unlabeled")),
                    "code_sha": _sha, "code_dirty": _dirty,
                    "config_hash": _cfg, "lever_env": _levers,
                    "seeds": _seeds,
                    "candidate_batch_metadata": json.dumps(
                        effective_batch_metadata,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    "labels_complete": labels_complete,
                    # Staging rows are NEVER research-eligible: only
                    # a passing promotion (scripts/harvest_accept.py)
                    # sets this true, so a partial or mixed-config panel
                    # cannot leak into training queries (Sol audit 3).
                    "research_eligible": False,
                    "season": int(slate["season"].iloc[0]),
                    "week": int(slate["week"].iloc[0]),
                    "cand_ix": ix, "tag": lu.tag or "lev",
                    # every generator that produced this roster, not just
                    # the first (Sol A2.1: recorded before the dedupe
                    # test). JSON list, not an ambiguous delimited string.
                    "all_tags": json.dumps(
                        all_tags.get(lu.ids, [lu.tag or "lev"])),
                    "selected": ix in sel_order,
                    "selected_rank": sel_order.get(ix, -1),
                    "salary": int(lu.salary),
                    "p_line": float(p_line_all[ix]),
                    "sim_mean": float(cand_totals[ix].mean()),
                    "sim_sd": float(sim_sd[ix]),
                    "sim_q50": float(qs[0, ix]),
                    "sim_q90": float(qs[1, ix]),
                    "sim_q99": float(qs[2, ix]),
                    "sim_rank_p_line": int(
                        (p_line_all > p_line_all[ix]).sum()) + 1,
                    "actual_score": (None if not labels_complete
                                     else float(acts[ix])),
                    "actual_rank": (None if not labels_complete
                                    else int(act_rank[ix])),
                    "tail_line": float(tail_line),
                    "n_entries": int(n_entries),
                    "n_sims": int(cand_totals.shape[1]),
                    "n_locks": len(locks or ()),
                    "n_theses": len(theses or ()),
                    "players": ",".join(
                        str(p.get("id")) for p in lu.players),
                    # clear-world masks — the greedy coverage selector
                    # cannot be reconstructed from scalar p_line (Sol
                    # §6). FULL length (no truncation), with n_worlds and
                    # bitorder recorded so decode is unambiguous, plus
                    # the preregistered 187/194/200 grid for ACTION 3.
                    "n_worlds": n_worlds,
                    "bitorder": "big",
                    "clear_bits": np.packbits(
                        cand_totals[ix] >= tail_line,
                        bitorder="big").tobytes().hex(),
                    "clear_bits_187": np.packbits(
                        grid_masks[187.0][ix], bitorder="big").tobytes().hex(),
                    "clear_bits_194": np.packbits(
                        grid_masks[194.0][ix], bitorder="big").tobytes().hex(),
                    "clear_bits_200": np.packbits(
                        grid_masks[200.0][ix], bitorder="big").tobytes().hex(),
                    "clear_bits_210": np.packbits(
                        grid_masks[210.0][ix], bitorder="big").tobytes().hex(),
                    "clear_bits_220": np.packbits(
                        grid_masks[220.0][ix], bitorder="big").tobytes().hex(),
                })
            df = pd.DataFrame(rows)
            # A2.6 (partial): the candidate-by-world SCORE MATRIX is
            # irrecoverable after the run and masks at three thresholds
            # cannot support a residual-shift-and-reselect reranker.
            # Written as one compressed npz per slate to GCS, keyed by
            # panel/slate ids, with a checksum in the warehouse row.
            art_uri = ""
            art_sha = ""
            bucket = runtime_env.get("CAND_ARTIFACT_BUCKET", "")
            include_player_worlds = (
                runtime_env.get("CAND_ARTIFACT_PLAYER_WORLDS") == "1"
            )
            if bucket and persist_panel_run_id:
                try:
                    import hashlib

                    from google.cloud import storage

                    payload = _score_artifact_payload(
                        cand_totals,
                        tail_line,
                        slate=slate,
                        row_draws=rd,
                        include_player_worlds=include_player_worlds,
                    )
                    art_sha = hashlib.sha256(payload).hexdigest()
                    season_i = int(slate["season"].iloc[0])
                    week_i = int(slate["week"].iloc[0])
                    art_uri = (f"gs://{bucket}/cand_scores/"
                               f"{persist_panel_run_id}/"
                               f"{season_i}_w{week_i}_{slate_run_id}.npz")
                    storage.Client().bucket(bucket).blob(
                        art_uri.split(f"{bucket}/", 1)[1]
                    ).upload_from_string(payload)
                    log.info("score artifact -> %s (%d bytes)",
                             art_uri, len(payload))
                except Exception:
                    log.exception("score-artifact upload failed")
                    # An explicitly requested player-world payload exists to
                    # prevent an otherwise mandatory multi-seed replay.  Its
                    # absence therefore fails the research run even though
                    # ordinary replay candidate persistence is best-effort.
                    if cand_log_required or include_player_worlds:
                        raise
            df["score_artifact_uri"] = art_uri
            df["score_artifact_sha256"] = art_sha

            # IMMUTABLE PLAYER FEATURE SNAPSHOT (Sol audit 3 §A2.6): the
            # point-in-time values construction actually used. Written
            # once per (slate, player) — candidate rows carry their
            # player ids, so the join reconstructs candidate-level
            # features without storing 9x duplicate rows. Joining to
            # mutable "latest" feature tables later would reintroduce the
            # lineage ambiguity this whole exercise exists to remove.
            feat_tbl = runtime_env.get(
                "CAND_FEATURE_TABLE",
                (_cand_tbl.rsplit(".", 1)[0] + ".slate_player_features"
                 if "." in _cand_tbl else ""))
            if feat_tbl:
                want = ["id", "gsis_id", "name", "pos", "team", "opp",
                        "game_id", "salary", "proj", "proj_tourney",
                        "own_est", "consensus_div", "market_points",
                        "model_points_pre", "mean_projection", "proj_p10",
                        "proj_p50", "proj_p90", "proj_std",
                        # Point-in-time role/archetype state.  The shared
                        # contract also governs replay projection and slate
                        # construction, so a new field cannot silently vanish
                        # before this immutable writer.
                        *PLAYER_SNAPSHOT_FEATURES, "actual"]
                for column in (
                    "fp_route_source_season", "fp_route_source_week",
                    "fp_route_source_sha256", "fp_route_prior_observations",
                    "fp_route_share_last", "fp_route_share_l4",
                    "fp_route_share_jump", "fp_route_cross_season",
                    "fp_route_fallback", "fp_route_shadow_supported",
                    "route_distribution_artifact_uri",
                    "route_distribution_artifact_sha256",
                    "route_distribution_arm",
                    "route_distribution_model_variant",
                    "route_distribution_belief_variant",
                    "route_control_p30", "route_treatment_p30",
                    "route_delta_30",
                    "fp_cov_receiver_source_season",
                    "fp_cov_defense_source_season",
                    "coverage_control_p30", "coverage_treatment_p30",
                    "coverage_delta_30",
                ):
                    if column in slate.columns:
                        want.append(column)
                # Member-level point predictions are dynamic by fitted K and
                # were previously present in the replay frame but silently
                # discarded here, making MODEL_ENSEMBLE unauditable.
                want.extend(sorted(
                    c for c in slate.columns
                    if c.startswith("ensemble_point_")))
                want.extend(sorted(
                    c for c in slate.columns
                    if c.startswith("component_mean_")))
                have = [c for c in want if c in slate.columns]
                fdf = slate[have].copy()
                # BigQuery/pyarrow cannot infer a type for an all-None
                # object column (2026-08-05: every feature write failed
                # this way while candidates wrote fine). Missing numeric
                # families become float NaN, missing string families
                # become a typed string column.
                _strcols = {"id", "gsis_id", "name", "pos", "team", "opp",
                            "game_id", "fp_route_source_sha256",
                            "fp_route_fallback",
                            "route_distribution_artifact_uri",
                            "route_distribution_artifact_sha256",
                            "route_distribution_arm",
                            "route_distribution_model_variant",
                            "route_distribution_belief_variant"}
                _boolcols = {"is_cold_start", "fp_route_shadow_supported"}
                for c in want:  # explicit missingness, never silent
                    if c not in have:
                        if c in _strcols:
                            fdf[c] = pd.Series(
                                [pd.NA] * len(fdf), dtype="string")
                        elif c in _boolcols:
                            fdf[c] = pd.Series(
                                [pd.NA] * len(fdf), dtype="boolean")
                        else:
                            fdf[c] = pd.Series(
                                np.nan, index=fdf.index, dtype="float64")
                for c in want:  # coerce present columns to a stable type
                    if c in _strcols:
                        fdf[c] = fdf[c].astype("string")
                    elif c in _boolcols:
                        fdf[c] = fdf[c].astype("boolean")
                    else:
                        fdf[c] = pd.to_numeric(fdf[c], errors="coerce")
                fdf["feature_missing"] = json.dumps(
                    [c for c in want if c not in have])
                fdf["panel_run_id"] = persist_panel_run_id
                fdf["slate_run_id"] = slate_run_id
                fdf["season"] = int(slate["season"].iloc[0])
                fdf["week"] = int(slate["week"].iloc[0])
                fdf["generated_at"] = now
                fdf["code_sha"] = _sha
                fdf["config_hash"] = _cfg
                fdf["model_ensemble_size"] = _ensemble_size
                fdf["model_member_spec"] = pd.Series(
                    [_ensemble_spec] * len(fdf), dtype="string")
                fdf["research_eligible"] = False  # promotion grants it

                def _write_feats(d=fdf, t=feat_tbl):
                    try:
                        load_dataframe(d, t, write_disposition="WRITE_APPEND")
                        log.info("player features persisted: %d -> %s",
                                 len(d), t)
                    except Exception:
                        log.exception("player-feature persistence failed")
                        if cand_log_required:
                            raise

                if cand_log_async:
                    import threading
                    threading.Thread(target=_write_feats, daemon=True).start()
                else:
                    _write_feats()

            def _write():
                try:
                    load_dataframe(df, _cand_tbl,
                                   write_disposition="WRITE_APPEND")
                    log.info("candidates persisted: %d -> %s (run %s)",
                             len(df), _cand_tbl, slate_run_id)
                except Exception:
                    log.exception("candidate persistence failed")
                    if cand_log_required:
                        raise

            if cand_log_async:
                import threading
                threading.Thread(target=_write, daemon=True).start()
            else:
                _write()
        except Exception:
            log.exception("candidate persistence failed; selection unaffected")
            if cand_log_required:
                raise
    return [cands[i] for i in picked]


def _enforce_theses(picked: list[int], cands: list, cand_totals,
                    tail_line: float, theses: list[dict]) -> list[int]:
    """Portfolio floor per thesis: swap the weakest non-thesis entries
    for the best unpicked combo-containing candidates until each quota
    is met (best-effort — a thesis the pool can't satisfy is logged)."""
    import numpy as _np

    p_line = (cand_totals >= tail_line).mean(axis=1)
    picked = list(picked)
    for th in theses:
        combo = set(th.get("players") or ())
        need = int(th.get("min") or 0)
        if not combo or need <= 0:
            continue
        def has(i):
            return combo <= {p["id"] for p in cands[i].players}
        have = sum(1 for i in picked if has(i))
        pool_extra = sorted((i for i in range(len(cands))
                             if i not in picked and has(i)),
                            key=lambda i: -p_line[i])
        while have < need and pool_extra:
            worst = min((i for i in picked if not has(i)),
                        key=lambda i: p_line[i], default=None)
            if worst is None:
                break
            picked[picked.index(worst)] = pool_extra.pop(0)
            have += 1
        if have < need:
            log.warning("thesis %s: only %d/%d entries possible",
                        sorted(combo), have, need)
    return picked


def _select_qb_concentrated(
    cands: list, cand_totals: np.ndarray, n_entries: int, line: float,
) -> list[int]:
    """One QB family for the whole portfolio (review #4 F5). For each
    QB with enough candidates, greedy-select n_entries within the
    family and score P(any clears the line); keep the best family
    (tiebreak mean best-of-N). Families smaller than n_entries are
    padded from the global pool only if no family is big enough."""
    from ..optimizer.lineup import select_tail_entries

    fams: dict = {}
    for ix, lu in enumerate(cands):
        qb = next((p["id"] for p in lu.players if p["pos"] == "QB"), None)
        fams.setdefault(qb, []).append(ix)
    best_pick, best_key = None, (-1.0, -1.0)
    for qb, ixs in fams.items():
        if qb is None or len(ixs) < min(n_entries, 2):
            continue
        sub = cand_totals[ixs]
        local = select_tail_entries(sub, n_entries, line)
        pick = [ixs[i] for i in local]
        tot = cand_totals[pick]
        key = (float((tot >= line).any(axis=0).mean()),
               float(tot.max(axis=0).mean()))
        if key > best_key:
            best_key, best_pick = key, pick
    if best_pick is None:  # no family large enough — fall back
        return select_tail_entries(cand_totals, n_entries, line)
    return best_pick


def _select_tail_qb_capped(
    cand_totals: np.ndarray, n_entries: int, line: float,
    qb_of: list, max_qbs: int,
) -> list[int]:
    """select_tail_entries with a cap on DISTINCT QBs across the selected
    set (env MAX_QBS). Once the cap is reached, only candidates reusing an
    already-selected QB stay eligible — the freed slots buy combinatorial
    depth within the kept stacks instead of a 17th stack. Mirrors the
    greedy coverage + fill of select_tail_entries."""
    cand_totals = np.asarray(cand_totals, dtype=float)
    clears = cand_totals >= line
    p_line = clears.mean(axis=1)
    mean_total = cand_totals.mean(axis=1)
    n_entries = min(n_entries, len(cand_totals))
    selected: list[int] = []
    qbs: set = set()
    covered = np.zeros(cand_totals.shape[1], dtype=bool)
    remaining = set(range(len(cand_totals)))

    def eligible():
        if len(qbs) < max_qbs:
            return remaining
        return [i for i in remaining if qb_of[i] in qbs]

    while len(selected) < n_entries:
        pool_i = eligible()
        if not pool_i:
            break
        best = max(pool_i,
                   key=lambda i: (int(np.count_nonzero(clears[i] & ~covered)),
                                  p_line[i], mean_total[i]))
        if not np.count_nonzero(clears[best] & ~covered):
            break  # coverage saturated; fill below
        selected.append(best)
        qbs.add(qb_of[best])
        covered |= clears[best]
        remaining.discard(best)
    while len(selected) < n_entries:
        pool_i = eligible()
        if not pool_i:
            break
        best = max(pool_i, key=lambda i: (p_line[i], mean_total[i]))
        selected.append(best)
        qbs.add(qb_of[best])
        remaining.discard(best)
    return selected


def run_week(
    slate: pd.DataFrame,
    contest: Contest,
    n_entries: int = 20,
    field_size: int = 5_000,
    stack: StackRules | None = None,
    seed: int | None = 42,
    sharp_fraction: float = 0.0,
    draws: np.ndarray | None = None,
    tail_line: float | None = None,
    n_boom_solves: int = 40,
    belief_slate: pd.DataFrame | None = None,
    belief_draws: np.ndarray | None = None,
    policy_env: Mapping[str, str] | None = None,
    construction_preset_receipt: Mapping[str, object] | None = None,
) -> WeekResult | None:
    """Backtest one historical slate. `slate` columns: REQUIRED_COLS.
    With `draws` (player-draw matrix indexed by the slate's draw_idx
    column) and `tail_line`, entries are selected to maximize
    P(best entry >= tail_line) instead of taking the top objective batch."""
    leakage_guard(slate)
    season = int(slate["season"].iloc[0]) if "season" in slate else 0
    week = int(slate["week"].iloc[0]) if "week" in slate else 0

    pool = slate.to_dict("records")
    obj = "proj_tourney" if "proj_tourney" in slate.columns else "proj"
    if draws is not None and tail_line is not None and "draw_idx" in slate.columns:
        runtime_env = {} if policy_env is None else policy_env

        lineups = tail_select_lineups(
            slate, pool, draws, tail_line, n_entries, stack, obj,
            contest=contest, sharp_fraction=sharp_fraction,
            candidate_multiple=int(runtime_env.get("CAND_MULT", "2")),
            n_boom_solves=int(runtime_env.get("N_BOOM", str(n_boom_solves))),
            # Generator-mix A/B (2026-08-01): 2025 replays show the top-4
            # game-stack generator won 0/17 weeks from ~6% of the pool
            # while dark games won 4/17 from ~11% -- N_GAMESTACK=0 +
            # N_DARKGAME up reallocates toward what actually wins.
            n_game_stacks=int(runtime_env.get("N_GAMESTACK", "4")),
            belief_slate=belief_slate, belief_draws=belief_draws,
            policy_env=runtime_env,
            construction_preset_receipt=construction_preset_receipt)
    else:
        lineups = optimize_many(pool, n_lineups=n_entries, stack=stack,
                                objective_col=obj, env=policy_env)
    if not lineups:
        log.warning("No feasible lineups for %s week %s", season, week)
        return None

    actual = slate.set_index("id")["actual"]
    lineup_scores = [float(actual.reindex([p["id"] for p in lu.players]).sum())
                     for lu in lineups]

    # model_own column present => OWN_MODEL replay: the trained ownership
    # model drives the simulated field instead of the naive softmax.
    own_vec = (slate["model_own"].to_numpy()
               if "model_own" in slate.columns and slate["model_own"].notna().all()
               else None)
    fld = field_sim.sample_field(slate, n_lineups=field_size, seed=seed,
                                 ownership=own_vec,
                                 sharp_fraction=sharp_fraction)
    scores = field_sim.field_scores(fld, slate["actual"].to_numpy())

    percentiles, winnings = [], []
    for s in lineup_scores:
        beaten = float(np.mean(scores > s))
        rank = max(1, int(round(beaten * contest.field_size)) + 1)
        percentiles.append(beaten)
        winnings.append(contest.payout_for_rank(rank))

    return WeekResult(season, week, lineups, lineup_scores, percentiles, winnings)


def run(
    slates: list[pd.DataFrame],
    contest: Contest,
    n_entries: int = 20,
    field_size: int = 5_000,
    stack: StackRules | None = None,
    seed: int | None = 42,
    sharp_fraction: float = 0.0,
    draws: np.ndarray | None = None,
    tail_line: float | None = None,
    n_boom_solves: int = 40,
    belief_slates: list[pd.DataFrame] | None = None,
    belief_draws: np.ndarray | None = None,
    policy_env: Mapping[str, str] | None = None,
    construction_preset_receipt: Mapping[str, object] | None = None,
) -> BacktestResult:
    result = BacktestResult(
        contest=contest,
        construction_preset_receipt=dict(
            construction_preset_receipt or {}
        ) or None,
    )
    belief_by_week = ({
        (int(s["season"].iloc[0]), int(s["week"].iloc[0])): s
        for s in (belief_slates or [])
    })
    for slate in slates:
        key = (int(slate["season"].iloc[0]), int(slate["week"].iloc[0]))
        wk = run_week(slate, contest, n_entries=n_entries,
                      field_size=field_size, stack=stack, seed=seed,
                      sharp_fraction=sharp_fraction, draws=draws,
                      tail_line=tail_line, n_boom_solves=n_boom_solves,
                      belief_slate=belief_by_week.get(key),
                      belief_draws=belief_draws, policy_env=policy_env,
                      construction_preset_receipt=construction_preset_receipt)
        if wk is not None:
            result.weeks.append(wk)
            log.info("season %s week %s: best %.1f pts, best pct %.1f%%",
                     wk.season, wk.week, max(wk.lineup_scores),
                     100 * min(wk.percentiles))
    return result
