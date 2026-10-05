"""Freeze the paired five-seed SIS pass-tail books (O-3 Amendment 1).

The books compare the two TabPFN distribution caches (control vs SIS
treatment) inside ONE lineup generation, declared by SIS_PASS_TAIL_CONTRACT:
``pass-tail-v1-a1-companion`` (the current money path, live from 2026 Week 5)
or ``pass-tail-v1-a1-frozen-2026-08`` (the August generation; dry runs and
replays only from Week 5). Books of the two never share an identity.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Iterator, Mapping

import numpy as np
import pandas as pd

from ..config import settings
from ..optimizer.construction_presets import (
    INCUMBENT_GPP_PRESET_ID,
    resolve_construction_preset_from_environment,
)
from .recourse_worlds import persist_recourse_world_artifact
from .sis_pass_tail_shadow import (
    COMPANION_LINEUP_CONTRACT,
    CONTRACT,
    CONTRACT_ENV,
    DRY_RUN_PANEL_PREFIX,
    ENTRIES,
    FROZEN_LINEUP_CONTRACT,
    LINEUP_CONTRACTS,
    LINEUP_IDENTITIES,
    PROTOCOL_VERSION,
    SEEDS,
    TABLES,
    TAIL_LINE,
    WORLDS,
    arm_environment,
    cache_table,
    check_job_contract,
    contract_settings_sha256,
    distribution_settings_sha256,
    environment_failures,
    require_declared,
    require_live_lineup_contract,
    shadow_dry_run,
)


_CODE_SHA = re.compile(r"^[0-9a-f]{7,40}$")


def policy_levers_in_environment(environ: Mapping[str, str]) -> dict[str, str]:
    """Registered roster-changing levers set on the job itself.

    The pair's settings come only from ``arm_environment`` (code, hashed into
    the contract); a lever on the Cloud Run job would silently change both
    arms' generation, so its presence is refused.
    """
    from ..backtest.engine import _lever_keys

    return {
        key: str(environ[key]) for key in sorted(_lever_keys)
        if str(environ.get(key, "") or "").strip()
    }


# --- Companion lineup contract (pass-tail-v1-a1-companion) -----------------
# The paired books under the ADOPTED money-path generation. Only the KEYS are
# listed; every VALUE is read from ClassicProductionPolicy.engine_environment()
# (tail_shadow's companion pattern), and a test pins the literals and the
# settings sha256. ROLE_BELIEF_SEED is not a job setting: the five registered
# seed pairs (= the money path's MULTISEED_SEED_PAIRS) set it per book. The
# money path combines its five seeds into one CBWU book; the pass-tail grid
# keeps one book per seed pair (the capture needs single-seed books), so
# MULTISEED_* are cleared per book, as in Route Share companion v1.
COMPANION_KEYS = (
    "GEN_TOTAL_BUDGET", "N_LEV", "N_CE", "N_EPISTEMIC", "N_BOOM",
    "N_GUMBEL", "REPLACEMENT_SLOTS", "BOOM_UNIQUE_FILL",
    "EPISTEMIC_FAMILY", "ROLE_BELIEF_FEATURES",
    "CE_SEED", "BLEND_MODEL_WEIGHT", "LIVE_SIMS", "GAME_SIM_MODE",
    "SERVED_POSITION_SCALES", "MODEL_ENSEMBLE", "MIN_LINEUP_SALARY",
)
COMPANION_SINGLE_SEED_KEYS = (
    "MULTISEED_PORTFOLIO", "MULTISEED_SEED_PAIRS",
    "MULTISEED_WORLDS_PER_BLOCK", "MULTISEED_CANDIDATE_ENTRY_BASIS",
)
COMPANION_SHADOW_ID = "2026-sis-pass-tail-companion-v1"
# Per-book keys the grid sets on top of the money-path env: the arm's cache
# (the ONLY arm difference), the registered seed pair, and capture plumbing.
COMPANION_BOOK_OVERLAY_KEYS = (
    "TABPFN_MARGINAL_TABLE", "ROLE_BELIEF_SEED", "REPLAY_PROJECTION_SEED",
    "CAND_ARTIFACT_PLAYER_WORLDS", "PROSPECTIVE_SHADOW_ID",
    "PROSPECTIVE_SIS_PASS_TAIL_VERSION", "CAND_ARTIFACT_BUCKET",
    *COMPANION_SINGLE_SEED_KEYS,
)


def _adopted_policy():
    from .production_policy import ADOPTED_CLASSIC_POLICY

    return ADOPTED_CLASSIC_POLICY


def companion_settings(policy=None) -> dict[str, str]:
    """The companion job settings, derived from the adopted money path."""
    engine = (policy or _adopted_policy()).engine_environment()
    return {key: engine[key] for key in COMPANION_KEYS}


def companion_contract_settings(policy=None) -> dict:
    """Everything the companion lineup contract fixes, canonical."""
    policy = policy or _adopted_policy()
    return {
        "contract": COMPANION_LINEUP_CONTRACT,
        "distribution_settings_sha256": distribution_settings_sha256(),
        "job_settings": dict(sorted(companion_settings(policy).items())),
        "arm_difference": {arm: {"TABPFN_MARGINAL_TABLE": TABLES[arm]}
                           for arm in TABLES},
        "seeds": {label: list(pair) for label, pair in SEEDS.items()},
        "single_seed_books": True,
        "model_variant": policy.model_variant,
        "role_model_variant": policy.role_model_variant,
        "construction_preset": policy.construction_preset().receipt(),
        "entries": ENTRIES,
        "tail_line": TAIL_LINE,
        "shadow_id": COMPANION_SHADOW_ID,
        "identities": list(LINEUP_IDENTITIES[COMPANION_LINEUP_CONTRACT]),
    }


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")).hexdigest()


def companion_settings_sha256(policy=None) -> str:
    return _canonical_sha256(companion_contract_settings(policy))


def paired_job_environment(contract: str) -> dict[str, str]:
    """What the paired Cloud Run job must declare for one lineup contract."""
    if contract == COMPANION_LINEUP_CONTRACT:
        return {CONTRACT_ENV: contract, **companion_settings()}
    if contract == FROZEN_LINEUP_CONTRACT:
        return {CONTRACT_ENV: contract}
    raise RuntimeError(
        f"paired SIS pass-tail requires {CONTRACT_ENV} in "
        f"{list(LINEUP_CONTRACTS)}, got {contract!r}")


def check_paired_contract(environ: Mapping[str, str]) -> dict:
    """Refuse a paired job that is not exactly one declared lineup contract."""
    contract = require_declared(environ, "paired")
    expected = paired_job_environment(contract)
    wrong = {
        key: (environ.get(key), value)
        for key, value in expected.items()
        if environ.get(key) != value
    }
    if wrong:
        raise RuntimeError(
            f"paired SIS pass-tail env contradicts {CONTRACT_ENV}={contract} "
            f"(found, required): {wrong}")
    stray = {
        key: value for key, value in policy_levers_in_environment(environ).items()
        if key not in expected
    }
    if stray:
        raise RuntimeError(
            "paired SIS pass-tail job env carries policy levers its contract "
            f"does not declare: {stray}")
    if contract == COMPANION_LINEUP_CONTRACT:
        policy = _adopted_policy()
        if (policy.model_variant, policy.role_model_variant) != (
                "tail_k1", "tail_k1_role"):
            raise RuntimeError(
                "the money path's registries moved off tail_k1/tail_k1_role; "
                "the companion grid must be re-declared")
        sha = companion_settings_sha256(policy)
    else:
        from .sis_pass_tail_shadow import frozen_lineup_settings_sha256

        sha = frozen_lineup_settings_sha256()
    return {
        "contract": contract,
        "role": "paired",
        "settings_sha256": sha,
        "distribution_settings_sha256": distribution_settings_sha256(),
        "dry_run": shadow_dry_run(environ),
    }


def companion_book_environment(
    arm: str, *, projection_seed: int, role_seed: int,
    environ: Mapping[str, str], bucket: str, policy=None,
) -> dict[str, str]:
    """One companion book: the money-path env plus the arm's cache and seeds."""
    if arm not in TABLES:
        raise ValueError(f"unknown SIS pass-tail arm {arm!r}")
    env = (policy or _adopted_policy()).engine_environment(environ)
    env.update({key: "" for key in COMPANION_SINGLE_SEED_KEYS})
    env.update({
        "TABPFN_MARGINAL_TABLE": TABLES[arm],
        "ROLE_BELIEF_SEED": str(int(role_seed)),
        "REPLAY_PROJECTION_SEED": str(int(projection_seed)),
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
        "PROSPECTIVE_SHADOW_ID": COMPANION_SHADOW_ID,
        "PROSPECTIVE_SIS_PASS_TAIL_VERSION": PROTOCOL_VERSION,
        "CAND_ARTIFACT_BUCKET": bucket,
    })
    return env


def companion_failures(arm: str, env: Mapping[str, str], policy=None) -> list[str]:
    """A companion book env that is not the money path + the overlay fails."""
    engine = (policy or _adopted_policy()).engine_environment()
    failures = [
        f"{key} differs" for key, value in engine.items()
        if key not in COMPANION_BOOK_OVERLAY_KEYS and str(env.get(key, "")) != value
    ]
    if env.get("TABPFN_MARGINAL_TABLE") != TABLES.get(arm):
        failures.append("TABPFN_MARGINAL_TABLE differs")
    if any(str(env.get(key, "")) for key in COMPANION_SINGLE_SEED_KEYS):
        failures.append("companion books are single-seed")
    pair = (int(str(env.get("REPLAY_PROJECTION_SEED", "-1"))),
            int(str(env.get("ROLE_BELIEF_SEED", "-1"))))
    if pair not in set(SEEDS.values()):
        failures.append("seed pair is not registered")
    for key in ("GAME_SIM_USAGE", "SIS_ASOE_TARGET_ALLOCATION", "DIRICHLET_K",
                "EXTRA_FEATURES", "DROP_FEATURES", "ARCHETYPE_ALLOCATION_VERSION"):
        if str(env.get(key, "") or "") != str(engine.get(key, "") or ""):
            failures.append(f"{key} differs from the money path")
    return failures


def slate_pool_receipt(
    frame: pd.DataFrame, allowed_ids: set[int] | None, now: datetime,
) -> dict:
    """Which DK draft groups served the pool, and proof none had started.

    O-27 class (193e1b44): an image that kept a draft group while its LAST
    game was ahead served Sunday rows from the stale full-week group after a
    Thursday game. The receipt names the groups; a row of a selectable player
    whose game has already kicked off is refused.
    """
    required = {"dk_player_id", "draft_group_id", "game_start"}
    if missing := required - set(frame.columns):
        raise RuntimeError(f"live slate features lack {sorted(missing)}")
    rows = frame
    if allowed_ids is not None:
        rows = frame[pd.to_numeric(frame.dk_player_id, errors="coerce")
                     .isin(allowed_ids)]
    starts = pd.to_datetime(rows.game_start, utc=True, errors="coerce")
    if starts.isna().any():
        raise RuntimeError("live slate rows lack a game_start")
    started = rows[starts <= pd.Timestamp(now).tz_convert("UTC")]
    if not started.empty:
        raise RuntimeError(
            f"{len(started)} selectable slate rows come from games that already "
            f"started (draft groups {sorted(set(started.draft_group_id.astype(int)))}); "
            "the pool served a stale draft group")
    count = lambda f: {str(int(g)): int(n) for g, n in  # noqa: E731
                       f.groupby("draft_group_id").size().items()}
    return {
        "draft_groups": count(frame),
        "selectable_draft_groups": count(rows),
        "selectable_rows": int(len(rows)),
        "earliest_selectable_game_start": (
            starts.min().isoformat() if len(starts) else None),
        "checked_at": pd.Timestamp(now).tz_convert("UTC").isoformat(),
    }


@contextlib.contextmanager
def one_feature_snapshot(
    allowed_ids: set[int] | None = None, now: datetime | None = None,
) -> Iterator[dict]:
    """Serve every book in the grid from ONE read of the live slate features.

    The protocol requires all ten books to share one feature build; the
    Sunday features job rebuilds hourly while the grid runs, so each book
    re-reading the table could mix builds. The first read is kept and reused;
    its content fingerprint and the draft groups it came from go into the
    manifest.
    """
    from . import run_projections

    original = run_projections.upcoming_slate_features
    receipt: dict = {"reads": 0}
    cached: dict[tuple[int, int], pd.DataFrame] = {}

    def frozen(season: int, week: int, as_of: str | None = None):
        if as_of is not None:
            raise RuntimeError("the pass-tail grid reads live features only")
        key = (int(season), int(week))
        if key not in cached:
            if cached:
                raise RuntimeError("the pass-tail grid asked for two target weeks")
            frame = original(season, week)
            pool = slate_pool_receipt(
                frame, allowed_ids, now or datetime.now(timezone.utc))
            cached[key] = frame
            receipt["_frame"] = frame
            receipt.update({
                "season": key[0], "week": key[1], "rows": int(len(frame)),
                "sha256": hashlib.sha256(
                    frame.to_csv(index=False).encode("utf-8")).hexdigest(),
                "pool": pool,
            })
        receipt["reads"] += 1
        return cached[key].copy(deep=True)

    run_projections.upcoming_slate_features = frozen
    try:
        yield receipt
    finally:
        run_projections.upcoming_slate_features = original


@contextlib.contextmanager
def marginal_reads(dry_run: bool) -> Iterator[dict]:
    """Count every TabPFN marginal-cache read; in a dry run, redirect it.

    replay.load_tabpfn_marginal_cache silently returns an empty frame on a
    failed read, and the book then falls back to empirical marginals: an arm
    without its treatment that looks complete. replay.py is pinned by the
    effective-policy inventory, so the count is taken here, at the caller,
    without changing live behaviour: every read and every empty (fallback)
    read is recorded per table in the manifest, and the weekly record treats
    a book with a fallback as incomplete. A dry run serves the _dryrun copies
    and raises on an empty read.
    """
    from ..backtest import replay
    from ..bq import query_df

    original = replay.load_tabpfn_marginal_cache
    receipt: dict = {"tables": {}}
    live_to_dry = {TABLES[arm]: cache_table(arm, dry_run=True) for arm in TABLES}

    def counted(season: int, env: dict | None = None) -> pd.DataFrame:
        table = replay._tabpfn_marginal_table(env)
        if table not in live_to_dry:
            raise RuntimeError(f"pass-tail book read an unexpected marginal table {table}")
        if dry_run:
            table = live_to_dry[table]
            frame = query_df(
                f"SELECT * FROM `{settings.features}.{table}` "
                f"WHERE season = {int(season)} ORDER BY week, gsis_id")
            if frame.empty:
                raise RuntimeError(f"pass-tail dry-run marginal table {table} is empty")
        else:
            frame = original(season, env)
        entry = receipt["tables"].setdefault(
            table, {"reads": 0, "empty_fallbacks": 0, "rows": 0})
        entry["reads"] += 1
        entry["rows"] = int(len(frame))
        if frame.empty:
            entry["empty_fallbacks"] += 1
        return frame

    replay.load_tabpfn_marginal_cache = counted
    try:
        yield receipt
    finally:
        replay.load_tabpfn_marginal_cache = original
    receipt["empty_fallbacks"] = sum(
        e["empty_fallbacks"] for e in receipt["tables"].values())


def cache_coverage(features: pd.DataFrame, cache: pd.DataFrame,
                   allowed_ids: set[int]) -> dict:
    """Selectable skill players with no cache row keep their original draws."""
    if missing := {"dk_position", "dk_player_id", "gsis_id"} - set(features):
        raise RuntimeError(f"live slate features lack {sorted(missing)}")
    skill = features[features.dk_position.isin(["QB", "RB", "WR", "TE"])]
    skill = skill[pd.to_numeric(skill.dk_player_id, errors="coerce").isin(allowed_ids)]
    have = set(cache.gsis_id.astype(str))
    ids = skill.gsis_id.dropna().astype(str)
    missing = sorted(set(ids) - have)
    return {"selectable_skill_players": int(ids.nunique()),
            "without_cache_row": len(missing), "examples": missing[:10]}


def cache_pair_receipt(
    control: pd.DataFrame,
    treatment: pd.DataFrame,
    *,
    season: int,
    week: int,
    code_sha: str,
    dry_run: bool = False,
) -> dict:
    """Prove that the two live caches share one target/source identity."""
    keys = ["season", "week", "gsis_id"]
    metadata = {
        "protocol_version", "code_sha", "training_source_checksum",
        "inference_source_checksum", "sis_source_checksum",
        "sis_source_run_ids", "contract", "contract_settings_sha256",
    }
    required = {*keys, "arm", "mean", "q99", "dry_run", *metadata}
    for name, rows, arm in (
        ("control", control, "control"),
        ("treatment", treatment, "treatment"),
    ):
        if missing := required - set(rows.columns):
            raise ValueError(f"{name} live pass-tail cache lacks {sorted(missing)}")
        if rows.empty or rows.duplicated(keys).any():
            raise ValueError(f"{name} live pass-tail cache keys are invalid")
        if not rows.season.eq(season).all() or not rows.week.eq(week).all():
            raise ValueError(f"{name} live pass-tail cache target differs")
        if set(rows.arm.astype(str)) != {arm}:
            raise ValueError(f"{name} live pass-tail arm identity differs")
        if set(rows.protocol_version.astype(str)) != {PROTOCOL_VERSION}:
            raise ValueError(f"{name} live pass-tail protocol differs")
        if set(rows.code_sha.astype(str)) != {code_sha}:
            raise ValueError(f"{name} live pass-tail code SHA differs")
        if set(rows.contract.astype(str)) != {CONTRACT} or set(
            rows.contract_settings_sha256.astype(str)
        ) != {contract_settings_sha256()}:
            raise ValueError(f"{name} live pass-tail contract differs")
        if set(rows.dry_run.astype(bool)) != {bool(dry_run)}:
            raise ValueError(f"{name} live pass-tail dry-run flag differs")
        for field in metadata:
            if rows[field].astype(str).nunique(dropna=False) != 1:
                raise ValueError(f"{name} live pass-tail {field} is not singular")
    left = control.set_index(keys).sort_index()
    right = treatment.set_index(keys).sort_index()
    if not left.index.equals(right.index):
        raise ValueError("live pass-tail cache player keys differ")
    for field in metadata:
        if str(left[field].iloc[0]) != str(right[field].iloc[0]):
            raise ValueError(f"live pass-tail cache {field} differs")
    qcols = sorted(
        column for column in control.columns
        if column.startswith("q") and column[1:].isdigit()
    )
    if not qcols or not set(qcols) <= set(treatment.columns):
        raise ValueError("live pass-tail cache quantile schema differs")
    changed = ~np.isclose(
        left[["mean", *qcols]].to_numpy(float),
        right[["mean", *qcols]].to_numpy(float),
        rtol=0,
        atol=1e-12,
    )
    if not changed.any():
        raise ValueError("live pass-tail treatment cache is inert")
    return {
        "control_table": cache_table("control", dry_run=dry_run),
        "treatment_table": cache_table("treatment", dry_run=dry_run),
        "rows_per_arm": int(len(left)),
        "changed_player_distribution_rows": int(changed.any(axis=1).sum()),
        "training_source_checksum": str(left.training_source_checksum.iloc[0]),
        "inference_source_checksum": str(left.inference_source_checksum.iloc[0]),
        "sis_source_checksum": str(left.sis_source_checksum.iloc[0]),
        "sis_source_run_ids": str(left.sis_source_run_ids.iloc[0]),
        "code_sha": code_sha,
    }


def _membership(lineups, dk_mapping: dict[int, str]) -> list[list[str]]:
    output = []
    for lineup in lineups:
        try:
            roster = sorted(dk_mapping[int(player_id)] for player_id in lineup.ids)
        except KeyError as exc:
            raise ValueError(f"pass-tail lineup lacks DK id for {exc.args[0]}") from exc
        if len(roster) != 9 or len(set(roster)) != 9:
            raise ValueError("pass-tail lineup is not exact-nine")
        output.append(roster)
    if len(output) != ENTRIES or len({tuple(row) for row in output}) != ENTRIES:
        raise ValueError("pass-tail selected book is not exact-80 unique")
    return output


def run(
    *, store=None, season: int | None = None, week: int | None = None,
    draft_group_id: int | None = None, generated_at: datetime | None = None,
    storage_client=None, bucket_name: str | None = None,
) -> dict:
    """Build all ten books and create a single complete-grid manifest."""
    code_sha = str(os.environ.get("CODE_SHA", "")).strip().lower()
    if not _CODE_SHA.fullmatch(code_sha):
        raise ValueError("prospective SIS pass-tail requires immutable CODE_SHA")
    contract = check_paired_contract(os.environ)
    lineup = contract["contract"]
    dry_run = bool(contract["dry_run"])
    companion = lineup == COMPANION_LINEUP_CONTRACT
    if store is None:
        from ..app.store import BigQueryStore

        store = BigQueryStore()
    if season is None or week is None or draft_group_id is None:
        from .tail_shadow import upcoming_season_week, sunday_main_group

        found_season, found_week, sunday = upcoming_season_week()
        season = found_season if season is None else season
        week = found_week if week is None else week
        if draft_group_id is None:
            draft_group_id = sunday_main_group(store.classic_slates(), sunday)
    season, week, draft_group_id = int(season), int(week), int(draft_group_id)
    if season != 2026:
        raise ValueError("prospective SIS pass-tail v1 is frozen to 2026")
    if week < 5:
        return {
            "disposition": "prospective-sis-pass-tail-not-yet-eligible",
            "protocol_version": PROTOCOL_VERSION,
            "season": season,
            "week": week,
            "minimum_week": 5,
            "contract": contract,
        }
    require_live_lineup_contract(lineup, season, week, dry_run=dry_run)

    salaries = store.classic_salaries(draft_group_id).drop_duplicates(
        "dk_player_id"
    )
    required = {"dk_player_id", "dk_draftable_id", "salary"}
    if salaries.empty or (required - set(salaries)):
        raise ValueError("prospective pass-tail salary snapshot is incomplete")
    if salaries[list(required)].isna().any().any():
        raise ValueError("prospective pass-tail salary identity is incomplete")
    allowed = {int(value) for value in salaries.dk_player_id}
    salary_overrides = {
        int(row.dk_player_id): int(row.salary) for row in salaries.itertuples()
    }
    dk_mapping = {
        int(row.dk_player_id): str(int(row.dk_draftable_id))
        for row in salaries.itertuples()
    }
    from ..bq import query_df

    cache_frames = {
        arm: query_df(f"""
            SELECT * FROM `{settings.features}.{table}`
            WHERE season=@season AND week=@week
        """, params={"season": season, "week": week})
        for arm, table in (
            (arm, cache_table(arm, dry_run=dry_run)) for arm in TABLES)
    }
    cache_receipt = cache_pair_receipt(
        cache_frames["control"], cache_frames["treatment"],
        season=season, week=week, code_sha=code_sha, dry_run=dry_run,
    )
    stamp = generated_at or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("prospective pass-tail generated_at must be timezone-aware")
    stamp = stamp.astimezone(timezone.utc)
    gcs_root, run_type, run_prefix = LINEUP_IDENTITIES[lineup]
    if dry_run:
        gcs_root, run_type = f"{gcs_root}_dryrun", f"{run_type}_dryrun"
    run_id = (
        f"{DRY_RUN_PANEL_PREFIX if dry_run else ''}"
        f"{run_prefix}-{season}w{week:02d}-"
        f"{stamp.strftime('%Y%m%dT%H%M%SZ')}"
    )
    bucket = bucket_name or settings.gcs_bucket
    root = f"{gcs_root}/{season}/week-{week:02d}/{run_id}"
    from ..backtest.engine import effective_generation_config
    from .live_lineups import build_sim_lineups
    from .route_share_shadow import ROLE_FEATURES

    if companion:
        policy = _adopted_policy()
        construction = policy.construction_preset()
        n_sims = int(policy.engine_environment()["LIVE_SIMS"])
    else:
        n_sims = WORLDS
    books = {}
    with one_feature_snapshot(allowed) as features_receipt, \
            marginal_reads(dry_run) as marginal_receipt:
        for label, (projection_seed, role_seed) in SEEDS.items():
            for arm in ("control", "treatment"):
                if companion:
                    env = companion_book_environment(
                        arm, projection_seed=projection_seed,
                        role_seed=role_seed, environ=os.environ, bucket=bucket,
                        policy=policy)
                    failures = companion_failures(arm, env, policy)
                else:
                    env = dict(os.environ)
                    env.update(arm_environment(
                        arm, projection_seed=projection_seed,
                        role_seed=role_seed,
                    ))
                    construction = resolve_construction_preset_from_environment(
                        INCUMBENT_GPP_PRESET_ID, env,
                    )
                    env.update(construction.optimizer_environment())
                    env["CAND_ARTIFACT_BUCKET"] = bucket
                    failures = environment_failures(arm, env)
                if failures:
                    raise ValueError(
                        f"SIS pass-tail {lineup} {label}/{arm} drift: {failures}"
                    )
                panel_id = f"{run_id}-{label.lower()}-{arm}"
                captured = []
                lineups = build_sim_lineups(
                    season,
                    week,
                    n_entries=ENTRIES,
                    stack=construction.stack,
                    tail_line=TAIL_LINE,
                    n_sims=n_sims,
                    seed=projection_seed,
                    lev_scale=1.0,
                    allowed_ids=allowed,
                    salary_overrides=salary_overrides,
                    apply_notes=False,
                    model_variant="tail_k1",
                    cand_log_table=f"{settings.predictions}.live_candidates_shadow",
                    cand_log_async=False,
                    cand_log_required=True,
                    panel_run_id=panel_id,
                    candidate_run_type=run_type,
                    policy_env=env,
                    construction_preset_receipt=construction.receipt(),
                    expected_model_k=1,
                    belief_model_variant="tail_k1_role",
                    model_forbidden_features=ROLE_FEATURES,
                    belief_required_features=ROLE_FEATURES,
                    _candidate_capture=captured.append,
                    # A shadow never writes own_shadow (O-27 follow-up): the
                    # table has no writer column, so a shadow row would
                    # become a week's "pre-lock prediction".
                    _log_ownership_shadow=False,
                )
                if len(captured) != 1:
                    raise RuntimeError("pass-tail build did not capture one candidate book")
                context = {
                    "protocol_version": PROTOCOL_VERSION,
                    "run_id": run_id,
                    "panel_run_id": panel_id,
                    "season": season,
                    "week": week,
                    "draft_group_id": draft_group_id,
                    "seed_label": label,
                    "projection_seed": projection_seed,
                    "role_seed": role_seed,
                    "arm": arm,
                    "code_sha": code_sha,
                    "cache_table": cache_table(arm, dry_run=dry_run),
                    "lineup_contract": lineup,
                    "lineup_settings_sha256": contract["settings_sha256"],
                    "distribution_settings_sha256": (
                        contract["distribution_settings_sha256"]),
                    "dry_run": dry_run,
                }
                artifact = persist_recourse_world_artifact(
                    captured[0],
                    dk_mapping,
                    generated_at=stamp,
                    bucket_name=bucket,
                    object_name=f"{root}/{label.lower()}-{arm}.npz",
                    context=context,
                    storage_client=storage_client,
                )
                books[f"{label}-{arm}"] = {
                    **context,
                    "entries": ENTRIES,
                    "tail_line": TAIL_LINE,
                    "worlds": n_sims,
                    "memberships": _membership(lineups, dk_mapping),
                    "artifact": artifact,
                    "effective_generation": effective_generation_config(env),
                }
    snapshot = features_receipt.pop("_frame", None)
    if snapshot is None:
        raise RuntimeError("the pass-tail grid never read the live slate features")
    if set(books) != {
        f"{label}-{arm}" for label in SEEDS for arm in ("control", "treatment")
    }:
        raise RuntimeError("prospective pass-tail book grid is incomplete")
    coverage = {arm: cache_coverage(snapshot, cache_frames[arm], allowed)
                for arm in TABLES}
    manifest = {
        "disposition": (
            f"{run_prefix}-shadow-dryrun" if dry_run
            else f"{run_prefix}-shadow-frozen"),
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "generated_at": stamp.isoformat(),
        "season": season,
        "week": week,
        "draft_group_id": draft_group_id,
        "code_sha": code_sha,
        "cache_pair": cache_receipt,
        "books": books,
        "uses_post_lock_outcomes": False,
        "production_enabled": False,
        "contract": contract,
        "dry_run": dry_run,
        # Only a live companion run is a candidate for the weekly record.
        "live": not dry_run,
        "feature_snapshot": dict(features_receipt),
        "marginal_reads": marginal_receipt,
        "cache_coverage": coverage,
    }
    payload = json.dumps(
        manifest, separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client()
    name = f"{root}/manifest.json"
    storage_client.bucket(bucket).blob(name).upload_from_string(
        payload, content_type="application/json", if_generation_match=0,
    )
    return {
        **manifest,
        "manifest_uri": f"gs://{bucket}/{name}",
        "manifest_sha256": digest,
        "manifest_bytes": len(payload),
        "manifest_create_only": True,
    }


def main() -> None:
    print(json.dumps(run(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()


__all__ = [
    "COMPANION_KEYS", "COMPANION_SHADOW_ID", "cache_coverage", "cache_pair_receipt",
    "check_paired_contract", "companion_book_environment", "companion_contract_settings",
    "companion_failures", "companion_settings", "companion_settings_sha256",
    "marginal_reads", "one_feature_snapshot", "paired_job_environment", "run",
    "slate_pool_receipt",
]
