"""Frozen prospective 2026 SIS pass-tail shadow contract.

This module is deliberately independent of the historical write-once cache
builder.  It prepares a target-week spine from completed SIS games and pins
the exact live control/treatment environments selected before 2026 outcomes.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from types import MappingProxyType

import numpy as np
import pandas as pd


PROTOCOL_VERSION = "prospective-sis-pass-tail-finite-k-v1"
CONTROL_TABLE = "tabpfn_sis_pass_tail_live_control_v1"
TREATMENT_TABLE = "tabpfn_sis_pass_tail_live_treatment_v1"
FITTED_K = "28.154043586960896"
FROZEN_BETA = "0.07771181538347656"
ENTRIES = 80
TAIL_LINE = 194.0
WORLDS = 10_000
SEEDS = {
    "R0": (0, 7331),
    "R1": (1137260708, 2690847602),
    "R2": (2875959182, 1630284992),
    "R3": (253722715, 3374646876),
    "R4": (1643280042, 3977633467),
}
FEATURES = (
    "sis_pass_def_boom_rate_l4",
    "sis_pass_def_bust_rate_l4",
    "sis_pass_rush_pressure_rate_l4",
)
SCHEDULES = {
    "control": "QB:0.85,RB:0.895,TE:0.96,WR:1.04",
    "treatment": "QB:0.92,RB:0.965,TE:0.945,WR:1.04",
}
TABLES = {"control": CONTROL_TABLE, "treatment": TREATMENT_TABLE}

# --- Amendment 1 contracts (O-3, 2026-10-05) --------------------------------
# Every job declares SIS_PASS_TAIL_CONTRACT; there is no default. The split
# (operator 2026-10-04, "we absolutely can change things mid-season"):
#   * pass-tail-v1-a1 -- the DISTRIBUTION contract of the two TabPFN cache
#     arms: exactly the frozen August caches plus two repairs (the 15de4020
#     build could not run) and the identity / dry-run rules;
#   * pass-tail-v1-a1-companion -- the paired LINEUP books under the current
#     money-path generation (defined in sis_pass_tail_portfolio, which may
#     import production_policy);
#   * pass-tail-v1-a1-frozen-2026-08 -- the August lineup generation, kept
#     for dry runs and replays only (refused live from 2026 Week 5).
# This module is copied into the GPU cache image as ``live_shadow.py``: it
# must import nothing from the ``nfl_dfs`` package.
CONTRACT_ENV = "SIS_PASS_TAIL_CONTRACT"
DISTRIBUTION_CONTRACT = "pass-tail-v1-a1"
CONTRACT = DISTRIBUTION_CONTRACT  # the cache rows' ``contract`` column
FROZEN_LINEUP_CONTRACT = "pass-tail-v1-a1-frozen-2026-08"
COMPANION_LINEUP_CONTRACT = "pass-tail-v1-a1-companion"
LINEUP_CONTRACTS = (COMPANION_LINEUP_CONTRACT, FROZEN_LINEUP_CONTRACT)
# From this target week only the companion may produce a live book.
FROZEN_LINEUP_LAST_LIVE = (2026, 4)
SHADOW_DRY_RUN_ENV = "SHADOW_DRY_RUN"
DRY_RUN_TABLES = {arm: f"{table}_dryrun" for arm, table in TABLES.items()}
DRY_RUN_PANEL_PREFIX = "dryrun-"
# Book identities per lineup contract (GCS root, candidate run type, run-id
# prefix). They never share a prefix, so companion weeks cannot be pooled with
# any August-generation book by a glob; a dry run appends ``_dryrun``.
LINEUP_IDENTITIES = MappingProxyType({
    FROZEN_LINEUP_CONTRACT: (
        "sis_pass_tail_shadow", "prospective_sis_pass_tail",
        "prospective-sis-pass-tail"),
    COMPANION_LINEUP_CONTRACT: (
        "sis_pass_tail_companion_shadow", "companion_sis_pass_tail_v1",
        "companion-sis-pass-tail-v1"),
})
# TabPFN cache settings (formerly literals in the GPU generator).
CACHE_SETTINGS = MappingProxyType({
    "context_max": 28_000,
    "random_seed": 7,
    "n_estimators": 4,
    "quantiles": (0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
                  0.60, 0.70, 0.80, 0.90, 0.95, 0.99),
    "positions": ("QB", "RB", "WR", "TE"),
})
# sha256 of scripts/tabpfn_gen/features.txt, the shared-33 control contract
# (the image copies it to /app/features_control.txt; a test pins the file).
BASE_FEATURES_SHA256 = (
    "52cc95c500bc3bd4223baacb29be73e3df4d637ce289b6431735cddd46195b83"
)
# Repair 1: the live inference table never carried ``salary`` (it is a
# training-table column from dk_salary_week). The target rows take it from the
# same table and join the training table uses, so train and serve agree.
TARGET_SALARY_SOURCE = "nfl_features.dk_salary_week.salary on (gsis_id, season, week)"
# Repair 2 (protocol: "missing ... data fail closed"): every completed
# same-season REG team-game before the target week must have a SIS row, so a
# missing W-1 load cannot silently shorten the last-four window.
SOURCE_WINDOW_RULE = "every 2026 REG team-game in weeks 1..W-1 has a SIS row"
AUTO_TARGET_RULE = "one 2026 inference week, equal to the schedule's upcoming REG week"
CACHE_ROLES = ("cache-control", "cache-treatment")
PASS_POSITIONS = ("QB", "WR", "TE")
TEAM_ALIASES = {"OAK": "LV", "SD": "LAC", "STL": "LA"}

_SOURCE_COLUMNS = (
    "pdef_attempts",
    "pdef_value_attempts",
    "pdef_boom_rate",
    "pdef_bust_rate",
    "prush_combined_sacks",
    "prush_pressures",
)


def _prior_sum(rows: pd.DataFrame, column: str) -> pd.Series:
    return rows.groupby(["season", "team"], sort=False)[column].transform(
        lambda values: values.shift(1).rolling(4, min_periods=2).sum()
    )


def build_target_context(
    source: pd.DataFrame,
    *,
    season: int,
    week: int,
    teams: Iterable[str],
) -> pd.DataFrame:
    """Build last-four context for an explicit pregame target-week spine.

    Rows at or after the target week are excluded before aggregation.  This
    makes a later rerun point-in-time safe and ensures the target game never
    needs to exist in the source table.
    """
    required = {
        "season", "week", "team", "source_run_id", *_SOURCE_COLUMNS,
    }
    if missing := required - set(source.columns):
        raise ValueError(f"live SIS pass-tail source lacks {sorted(missing)}")
    season = int(season)
    week = int(week)
    if week < 1:
        raise ValueError("live SIS pass-tail target week must be positive")
    target_teams = sorted({TEAM_ALIASES.get(str(team), str(team)) for team in teams})
    if not target_teams:
        raise ValueError("live SIS pass-tail target spine has no teams")

    rows = source.copy()
    rows["team"] = rows.team.astype(str).replace(TEAM_ALIASES)
    rows["season"] = pd.to_numeric(rows.season, errors="coerce")
    rows["week"] = pd.to_numeric(rows.week, errors="coerce")
    rows = rows[
        rows.season.eq(season)
        & rows.week.lt(week)
        & rows.team.isin(target_teams)
    ].copy()
    if rows.source_run_id.isna().any() or rows.source_run_id.astype(str).str.strip().eq("").any():
        raise ValueError("live SIS pass-tail source identity is blank")
    keys = ["season", "week", "team"]
    if rows.duplicated(keys).any():
        raise ValueError("live SIS pass-tail source repeats team-week keys")
    for column in _SOURCE_COLUMNS:
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
    for column in ("pdef_boom_rate", "pdef_bust_rate"):
        valid = rows[column].dropna()
        if not valid.between(0, 1).all():
            raise ValueError(f"live SIS pass-tail {column} is outside [0,1]")

    spine = pd.DataFrame({
        "season": season,
        "week": week,
        "team": target_teams,
        "source_run_id": PROTOCOL_VERSION,
    })
    for column in _SOURCE_COLUMNS:
        spine[column] = np.nan
    rows = pd.concat([rows, spine], ignore_index=True, sort=False)
    rows = rows.sort_values(keys).reset_index(drop=True)
    rows["_boom_events"] = rows.pdef_boom_rate * rows.pdef_value_attempts
    rows["_bust_events"] = rows.pdef_bust_rate * rows.pdef_value_attempts
    rows["_pressure_opportunities"] = (
        rows.pdef_attempts + rows.prush_combined_sacks
    )
    grouped = rows.groupby(["season", "team"], sort=False)
    output = rows[keys].copy()
    output["sis_pass_tail_source_week_end"] = grouped.week.shift(1)
    output["sis_pass_tail_prior_games"] = grouped.week.transform(
        lambda values: values.shift(1).rolling(4, min_periods=1).count()
    )
    value_attempts = _prior_sum(rows, "pdef_value_attempts")
    pressure_opportunities = _prior_sum(rows, "_pressure_opportunities")
    output[FEATURES[0]] = (
        _prior_sum(rows, "_boom_events") / value_attempts.replace(0, np.nan)
    )
    output[FEATURES[1]] = (
        _prior_sum(rows, "_bust_events") / value_attempts.replace(0, np.nan)
    )
    output[FEATURES[2]] = (
        _prior_sum(rows, "prush_pressures")
        / pressure_opportunities.replace(0, np.nan)
    )
    output = output[output.week.eq(week)].reset_index(drop=True)
    if set(output.team) != set(target_teams) or len(output) != len(target_teams):
        raise ValueError("live SIS pass-tail target spine is incomplete")
    output["sis_pass_tail_supported"] = (
        output.sis_pass_tail_prior_games.ge(2)
        & output[list(FEATURES)].notna().all(axis=1)
    )
    supported = output.sis_pass_tail_supported
    if supported.any() and not output.loc[
        supported, "sis_pass_tail_source_week_end"
    ].lt(week).all():
        raise ValueError("live SIS pass-tail context used target-week data")
    return output


def attach_target_context(
    inference: pd.DataFrame, context: pd.DataFrame,
) -> pd.DataFrame:
    """Attach opponent-team context to the target inference player rows."""
    required = {"season", "week", "opponent", "position"}
    if missing := required - set(inference.columns):
        raise ValueError(f"live SIS pass-tail inference lacks {sorted(missing)}")
    context_required = {
        "season", "week", "team", "sis_pass_tail_source_week_end",
        "sis_pass_tail_prior_games", "sis_pass_tail_supported", *FEATURES,
    }
    if missing := context_required - set(context.columns):
        raise ValueError(f"live SIS pass-tail context lacks {sorted(missing)}")
    players = inference.copy()
    players["opponent"] = players.opponent.astype(str).replace(TEAM_ALIASES)
    defense = context.rename(columns={"team": "opponent"}).copy()
    keys = ["season", "week", "opponent"]
    if defense.duplicated(keys).any():
        raise ValueError("live SIS pass-tail context repeats target keys")
    out = players.merge(
        defense[[*keys, "sis_pass_tail_source_week_end",
                 "sis_pass_tail_prior_games", "sis_pass_tail_supported",
                 *FEATURES]],
        on=keys,
        how="left",
        sort=False,
        validate="many_to_one",
    )
    if len(out) != len(inference):
        raise ValueError("live SIS pass-tail join changed inference row count")
    non_pass = ~out.position.astype(str).isin(PASS_POSITIONS)
    out.loc[non_pass, [
        "sis_pass_tail_source_week_end", "sis_pass_tail_prior_games", *FEATURES,
    ]] = np.nan
    out.loc[non_pass, "sis_pass_tail_supported"] = False
    supported = out[list(FEATURES)].notna().all(axis=1)
    if supported.any() and not out.loc[
        supported, "sis_pass_tail_source_week_end"
    ].lt(out.loc[supported, "week"]).all():
        raise ValueError("live SIS pass-tail attachment violates PIT scope")
    return out


def cache_table(arm: str, *, dry_run: bool = False) -> str:
    """The cache table one arm writes and reads; dry runs never touch live."""
    if arm not in TABLES:
        raise ValueError(f"unknown prospective SIS pass-tail arm {arm!r}")
    return DRY_RUN_TABLES[arm] if dry_run else TABLES[arm]


def arm_environment(arm: str, *, projection_seed: int, role_seed: int) -> dict[str, str]:
    """Return the exact historical-mechanism environment for one live book."""
    if arm not in TABLES:
        raise ValueError(f"unknown prospective SIS pass-tail arm {arm!r}")
    return {
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "MODEL_REGISTRY_VARIANT": "tail_k1",
        "TABPFN_MARGINALS": "1",
        # Always the LIVE table name (the licensed marginal table); a dry run
        # redirects only the read, so its env is exactly the live env.
        "TABPFN_MARGINAL_TABLE": TABLES[arm],
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": (
            "target_share_last,carry_share_last,snap_share_last,"
            "target_share_jump,carry_share_jump,snap_share_jump"
        ),
        "ROLE_BELIEF_SEED": str(int(role_seed)),
        "REPLAY_PROJECTION_SEED": str(int(projection_seed)),
        "REPLACEMENT_SLOTS": "12",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "GAME_SIM_USAGE": "dirichlet",
        "DIRICHLET_K": FITTED_K,
        "SIS_ASOE_TARGET_ALLOCATION": "1",
        "SIS_ASOE_BETA": FROZEN_BETA,
        "SERVED_POSITION_SCALES": SCHEDULES[arm],
        "MIN_LINEUP_SALARY": "49000",
        "LIVE_SIMS": str(WORLDS),
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
        "PROSPECTIVE_SIS_PASS_TAIL_VERSION": PROTOCOL_VERSION,
    }


def environment_failures(arm: str, source: Mapping[str, object]) -> list[str]:
    """Fail closed if a deployed runner drifts from the frozen contract."""
    expected = arm_environment(arm, projection_seed=0, role_seed=0)
    expected.pop("REPLAY_PROJECTION_SEED")
    expected.pop("ROLE_BELIEF_SEED")
    failures = [
        f"{name} differs"
        for name, value in expected.items()
        if str(source.get(name, "")) != value
    ]
    seed_pair = (
        int(str(source.get("REPLAY_PROJECTION_SEED", "-1"))),
        int(str(source.get("ROLE_BELIEF_SEED", "-1"))),
    )
    if seed_pair not in set(SEEDS.values()):
        failures.append("seed pair is not registered")
    if any(str(source.get(name, "")).strip() for name in (
        "MULTISEED_PORTFOLIO", "ARCHETYPE_ALLOCATION_VERSION",
        "EXTRA_FEATURES", "DROP_FEATURES",
    )):
        failures.append("unregistered composition lever is active")
    return failures


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def distribution_settings() -> dict:
    """Everything the distribution contract fixes (generation-independent)."""
    return {
        "contract": DISTRIBUTION_CONTRACT,
        "protocol_version": PROTOCOL_VERSION,
        "cache_tables": dict(TABLES),
        "treatment_extra_tabpfn_fields": list(FEATURES),
        "cache": {
            **{key: list(value) if isinstance(value, tuple) else value
               for key, value in CACHE_SETTINGS.items()},
            "base_features_sha256": BASE_FEATURES_SHA256,
            "target_salary_source": TARGET_SALARY_SOURCE,
            "source_window_rule": SOURCE_WINDOW_RULE,
            "auto_target_rule": AUTO_TARGET_RULE,
        },
        "dry_run": {"env": SHADOW_DRY_RUN_ENV, "tables": dict(DRY_RUN_TABLES)},
    }


def distribution_settings_sha256() -> str:
    return _canonical_sha256(distribution_settings())


def contract_settings_sha256() -> str:
    """The cache rows' contract identity (the distribution contract)."""
    return distribution_settings_sha256()


def frozen_lineup_settings() -> dict:
    """The August lineup generation (dry runs and replays only from W5)."""
    arms = {}
    for arm in TABLES:
        env = arm_environment(arm, projection_seed=0, role_seed=0)
        env.pop("REPLAY_PROJECTION_SEED")
        env.pop("ROLE_BELIEF_SEED")
        arms[arm] = dict(sorted(env.items()))
    return {
        "contract": FROZEN_LINEUP_CONTRACT,
        "distribution_settings_sha256": distribution_settings_sha256(),
        "arms": arms,
        "seeds": {label: list(pair) for label, pair in SEEDS.items()},
        "entries": ENTRIES,
        "tail_line": TAIL_LINE,
        "worlds": WORLDS,
        "identities": list(LINEUP_IDENTITIES[FROZEN_LINEUP_CONTRACT]),
    }


def frozen_lineup_settings_sha256() -> str:
    return _canonical_sha256(frozen_lineup_settings())


def job_environment(role: str) -> dict[str, str]:
    """What a cache job (or the paired job under the frozen generation) declares."""
    if role == "paired-frozen":
        return {CONTRACT_ENV: FROZEN_LINEUP_CONTRACT}
    if role in CACHE_ROLES:
        arm = role.split("-", 1)[1]
        return {
            CONTRACT_ENV: DISTRIBUTION_CONTRACT,
            "TABPFN_SIS_PASS_TAIL_LIVE_ARM": arm,
            "TABPFN_OUTPUT_TABLE": TABLES[arm],
            "TABPFN_UPCOMING": "auto",
        }
    raise ValueError(f"unknown SIS pass-tail job role {role!r}")


def shadow_dry_run(environ: Mapping[str, str]) -> bool:
    raw = environ.get(SHADOW_DRY_RUN_ENV)
    if raw in (None, ""):
        return False
    if raw == "1":
        return True
    raise RuntimeError(f"{SHADOW_DRY_RUN_ENV} must be unset or 1, got {raw!r}")


def require_declared(environ: Mapping[str, str], role: str) -> str:
    contract = environ.get(CONTRACT_ENV)
    if contract in (None, ""):
        raise RuntimeError(
            f"SIS pass-tail {role} requires {CONTRACT_ENV}; there is no default")
    return str(contract)


def check_job_contract(environ: Mapping[str, str], role: str) -> dict:
    """Refuse a cache job whose env is not exactly the distribution contract's."""
    require_declared(environ, role)
    expected = job_environment(role)
    wrong = {
        key: (environ.get(key), value)
        for key, value in expected.items()
        if environ.get(key) != value
    }
    if wrong:
        raise RuntimeError(
            f"SIS pass-tail {role} env contradicts its declared contract "
            f"(found, required): {wrong}")
    sha = (frozen_lineup_settings_sha256() if role == "paired-frozen"
           else distribution_settings_sha256())
    return {
        "contract": expected[CONTRACT_ENV],
        "role": role,
        "settings_sha256": sha,
        "distribution_settings_sha256": distribution_settings_sha256(),
        "dry_run": shadow_dry_run(environ),
    }


def require_live_lineup_contract(
    contract: str, season: int, week: int, *, dry_run: bool,
) -> None:
    """The August generation may not produce a LIVE book from 2026 Week 5."""
    if (contract == FROZEN_LINEUP_CONTRACT and not dry_run
            and (int(season), int(week)) > FROZEN_LINEUP_LAST_LIVE):
        raise RuntimeError(
            f"{CONTRACT_ENV}={FROZEN_LINEUP_CONTRACT} may not produce a live "
            f"book for {season} Week {week}: from 2026 Week 5 the paired books "
            f"run under {COMPANION_LINEUP_CONTRACT}. Use {SHADOW_DRY_RUN_ENV}=1 "
            "for a labelled non-live book.")


def _team(value: object) -> str:
    return TEAM_ALIASES.get(str(value), str(value))


def scheduled_team_games(schedule: pd.DataFrame) -> pd.DataFrame:
    """REG games -> one (season, week, team) row per side."""
    required = {"season", "week", "game_type", "home_team", "away_team"}
    if missing := required - set(schedule.columns):
        raise ValueError(f"schedule lacks {sorted(missing)}")
    games = schedule[schedule.game_type.astype(str).eq("REG")]
    sides = [
        pd.DataFrame({
            "season": pd.to_numeric(games.season).astype(int),
            "week": pd.to_numeric(games.week).astype(int),
            "team": games[column].map(_team),
        })
        for column in ("home_team", "away_team")
    ]
    return pd.concat(sides, ignore_index=True)


def source_window_audit(
    source: pd.DataFrame, schedule: pd.DataFrame, *, season: int, week: int,
) -> dict:
    """Compare SIS team-games in weeks 1..W-1 with the REG schedule."""
    season, week = int(season), int(week)
    expected = scheduled_team_games(schedule)
    expected = expected[expected.season.eq(season) & expected.week.lt(week)]
    rows = source.copy()
    rows["season"] = pd.to_numeric(rows.season, errors="coerce")
    rows["week"] = pd.to_numeric(rows.week, errors="coerce")
    rows = rows[rows.season.eq(season) & rows.week.lt(week)]
    want = {(int(w), str(t)) for w, t in zip(expected.week, expected.team)}
    have = {(int(w), _team(t)) for w, t in zip(rows.week, rows.team)}
    missing = sorted(want - have)
    unexpected = sorted(have - want)
    return {
        "rule": SOURCE_WINDOW_RULE,
        "season": season,
        "target_week": week,
        "source_weeks": sorted({w for w, _ in want}),
        "expected_team_games": len(want),
        "present_team_games": len(have & want),
        "missing": [f"{w}:{t}" for w, t in missing],
        "unexpected": [f"{w}:{t}" for w, t in unexpected],
        "complete": bool(want) and not missing and not unexpected,
    }


def require_complete_source_window(
    source: pd.DataFrame, schedule: pd.DataFrame, *, season: int, week: int,
    dry_run: bool = False,
) -> dict:
    """Fail closed on a missing or unscheduled SIS team-game (dry runs report)."""
    audit = source_window_audit(source, schedule, season=season, week=week)
    if not audit["complete"] and not dry_run:
        raise ValueError(
            f"live SIS pass-tail source window for {season} Week {week} is "
            f"incomplete: missing {audit['missing'][:12]} unexpected "
            f"{audit['unexpected'][:12]} (load the Wednesday acquisition first)")
    return audit


def attach_target_salary(
    target: pd.DataFrame, salaries: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Repair 1: target rows take ``salary`` from dk_salary_week (as training)."""
    keys = ["gsis_id", "season", "week"]
    if "salary" in target.columns:
        raise ValueError(
            "live inference rows now carry salary; the contract takes it from "
            "dk_salary_week -- rule on the schema change before running")
    if missing := {*keys, "salary"} - set(salaries.columns):
        raise ValueError(f"dk_salary_week rows lack {sorted(missing)}")
    if salaries.duplicated(keys).any():
        raise ValueError("dk_salary_week repeats player-week keys")
    out = target.merge(
        salaries[[*keys, "salary"]], on=keys, how="left", validate="many_to_one",
    )
    if len(out) != len(target):
        raise ValueError("salary join changed target row count")
    with_salary = int(out.salary.notna().sum())
    return out, {
        "source": TARGET_SALARY_SOURCE,
        "target_rows": int(len(out)),
        "rows_with_salary": with_salary,
        "rows_without_salary": int(len(out) - with_salary),
    }


def resolve_auto_target(inference_weeks: Iterable[tuple[int, int]],
                        schedule_week: tuple[int, int]) -> tuple[int, int]:
    """One 2026 inference week, and it must be the schedule's upcoming week."""
    weeks = sorted({(int(s), int(w)) for s, w in inference_weeks})
    if len(weeks) != 1:
        raise ValueError(
            "automatic live SIS pass-tail target requires exactly one 2026 "
            f"inference season/week, found {weeks}")
    if weeks[0] != tuple(int(v) for v in schedule_week):
        raise ValueError(
            f"inference week {weeks[0]} differs from the schedule's upcoming "
            f"week {tuple(schedule_week)}")
    if not 1 <= weeks[0][1] <= 18:
        raise ValueError("automatic live SIS pass-tail target week is invalid")
    return weeks[0]


__all__ = [
    "AUTO_TARGET_RULE", "BASE_FEATURES_SHA256", "CACHE_ROLES", "CACHE_SETTINGS",
    "COMPANION_LINEUP_CONTRACT", "CONTRACT", "CONTRACT_ENV", "CONTROL_TABLE",
    "DISTRIBUTION_CONTRACT", "DRY_RUN_PANEL_PREFIX", "DRY_RUN_TABLES", "ENTRIES",
    "FEATURES", "FITTED_K", "FROZEN_BETA", "FROZEN_LINEUP_CONTRACT",
    "LINEUP_CONTRACTS", "LINEUP_IDENTITIES", "PROTOCOL_VERSION", "SCHEDULES", "SEEDS", "SHADOW_DRY_RUN_ENV",
    "SOURCE_WINDOW_RULE", "TABLES", "TAIL_LINE", "TARGET_SALARY_SOURCE",
    "TREATMENT_TABLE", "WORLDS", "arm_environment", "attach_target_context",
    "attach_target_salary", "build_target_context", "cache_table",
    "check_job_contract", "contract_settings_sha256", "distribution_settings",
    "distribution_settings_sha256", "environment_failures",
    "frozen_lineup_settings", "frozen_lineup_settings_sha256", "job_environment",
    "require_complete_source_window", "require_declared",
    "require_live_lineup_contract",
    "resolve_auto_target", "scheduled_team_games", "shadow_dry_run",
    "source_window_audit",
]
