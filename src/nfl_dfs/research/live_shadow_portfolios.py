"""Freeze and grade prospective tail-first live portfolios.

The K=1/K=3 shadow jobs persist complete candidate pools before lock.  This
module turns those immutable inputs into nine explicitly frozen 80-entry
books without regenerating a slate or consulting outcomes:

* K=1 production coverage at 194 (research control)
* K=1 coverage at 187 and at 200 (prospective threshold alternatives)
* K=1 lexicographic extreme coverage at 220, then 210, then 200
* K=1 coverage followed by deterministic outcome-blind one-swap refinement
* K=1 top individual ``p_line`` (the leading selector hypothesis)
* K=1 no-salary-floor coverage at 194 (post-result prospective shadow)
* K=3 production coverage at 194 (same-time stability reference)
* 20 K=1 / 60 K=3 coverage, with deterministic K=3 duplicate backfill

The freeze operation is idempotent by season/week/snapshot slot.  The grader
joins only after-the-fact authoritative DK points and never mutates candidate
or membership rows.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from ..config import settings
from ..optimizer.lineup import select_from_support
from .tail_portfolio import decode_clear_bits, refine_one_swap

log = logging.getLogger(__name__)

PORTFOLIO_TABLE = "live_shadow_portfolios"
GRADE_TABLE = "live_shadow_grades"
POLICY_VERSION = "tail-first-v5-20260810"
EXPECTED_ENTRIES = 80
SELECT_LINE = 194.0
SLOT_HOURS = {"early": 10, "late": 11}

K1_COVERAGE = "tail_k1_coverage194"
K1_COVERAGE_187 = "tail_k1_coverage187"
K1_COVERAGE_200 = "tail_k1_coverage200"
K1_EXTREME_LEX = "tail_k1_extreme_lex_220_210_200"
K1_REFINED = "tail_k1_coverage194_one_swap"
K1_TOP_P = "tail_k1_top_p"
K1_NOFLOOR_COVERAGE = "tail_k1_nofloor_coverage194"
K3_COVERAGE = "tail_k3_coverage194"
MIX_20_60 = "tail_mix_k1_20_k3_60"

_MEMBERSHIP_ID_COLUMNS = [
    "portfolio_run_id", "portfolio_id", "portfolio_entry_rank",
    "source_model", "source_panel_run_id", "source_slate_run_id",
    "cand_ix", "roster_key", "selection_method", "policy_version",
]
_PANEL_ID = re.compile(
    r"^live-shadow-(tail_k1|tail_k1_nofloor|tail_k3)-\d{4}w\d{2}-"
    r"(\d{8}T\d{6}Z)$")


def _panel_started_at(panel_run_id: str) -> pd.Timestamp:
    match = _PANEL_ID.fullmatch(str(panel_run_id))
    if not match:
        raise ValueError(f"invalid live shadow panel id {panel_run_id!r}")
    stamp = pd.to_datetime(match.group(2), utc=True, errors="coerce")
    if pd.isna(stamp):
        raise ValueError(f"invalid timestamp in shadow panel id {panel_run_id!r}")
    return stamp


def canonical_roster(value: str) -> str:
    """Order-independent nine-player roster identity."""
    ids = [item.strip() for item in str(value).split(",") if item.strip()]
    if len(ids) != 9 or len(set(ids)) != 9:
        raise ValueError(f"candidate roster must contain 9 unique ids: {value!r}")
    return ",".join(sorted(ids))


def _ordered(rows: pd.DataFrame) -> pd.DataFrame:
    needed = {
        "cand_ix", "players", "p_line", "sim_mean", "n_worlds",
        "clear_bits_194",
    }
    missing = needed - set(rows.columns)
    if missing:
        raise ValueError(f"shadow candidates missing {sorted(missing)}")
    if rows.empty:
        raise ValueError("shadow candidate panel is empty")
    out = rows.sort_values("cand_ix").reset_index(drop=True).copy()
    if out.cand_ix.duplicated().any():
        raise ValueError("shadow candidate panel has duplicate cand_ix")
    out["roster_key"] = out.players.map(canonical_roster)
    if out.roster_key.duplicated().any():
        raise ValueError("shadow candidate panel has duplicate rosters")
    return out


def coverage_order(
    rows: pd.DataFrame, select_line: float = SELECT_LINE
) -> tuple[pd.DataFrame, np.ndarray]:
    """Complete deterministic persisted-support order for one pool."""
    ordered = _ordered(rows)
    mask_columns = {
        187.0: "clear_bits_187",
        194.0: "clear_bits_194",
        200.0: "clear_bits_200",
        210.0: "clear_bits_210",
        220.0: "clear_bits_220",
    }
    line = float(select_line)
    if line not in mask_columns:
        raise ValueError(
            f"unsupported shadow selection line {line:g}; "
            f"choose one of {sorted(mask_columns)}")
    mask_column = mask_columns[line]
    if mask_column not in ordered:
        raise ValueError(f"shadow candidates missing {mask_column}")
    n_worlds = pd.to_numeric(ordered.n_worlds, errors="raise").astype(int)
    if n_worlds.nunique() != 1 or int(n_worlds.iloc[0]) <= 0:
        raise ValueError("shadow n_worlds is invalid or inconsistent")
    n = int(n_worlds.iloc[0])
    support = np.stack([
        decode_clear_bits(value, n) for value in ordered[mask_column]
    ])
    support_probability = support.mean(axis=1)
    if line == SELECT_LINE:
        persisted_p_line = pd.to_numeric(
            ordered.p_line, errors="raise").to_numpy(dtype=float)
        if not np.allclose(
                support_probability, persisted_p_line, atol=1e-12, rtol=0):
            raise ValueError("shadow p_line does not match persisted 194 support")
    sim_mean = pd.to_numeric(
        ordered.sim_mean, errors="raise").to_numpy(dtype=float)
    if (not np.isfinite(support_probability).all()
            or not np.isfinite(sim_mean).all()):
        raise ValueError("shadow selector values contain non-finite numbers")
    picked = select_from_support(
        support, support_probability, sim_mean, len(ordered),
    )
    if len(picked) != len(ordered) or len(set(picked)) != len(ordered):
        raise ValueError("coverage selector did not return a full ordering")
    return ordered, np.asarray(picked, dtype=int)


def top_p_order(rows: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Historical diagnostic's exact stable p-line/cand_ix ordering."""
    ordered = _ordered(rows)
    ranked = pd.DataFrame({
        "position": np.arange(len(ordered), dtype=int),
        "p_line": pd.to_numeric(ordered.p_line, errors="raise"),
        "cand_ix": pd.to_numeric(ordered.cand_ix, errors="raise").astype(int),
    }).sort_values(
        ["p_line", "cand_ix"], ascending=[False, True], kind="mergesort")
    return ordered, ranked.position.to_numpy(dtype=int)


def extreme_lexicographic_order(
    rows: pd.DataFrame,
    thresholds: tuple[float, ...] = (220.0, 210.0, 200.0),
) -> tuple[pd.DataFrame, np.ndarray]:
    """Greedy complete order by new high-to-low tail-world coverage.

    Newly covered 220 worlds are always more valuable than newly covered 210
    worlds, which dominate 200 worlds. Individual support probabilities at
    those thresholds, simulated mean, and lower candidate index are the fixed
    tiebreakers. The rule is frozen before any 2026 outcome exists.
    """

    ordered = _ordered(rows)
    n_worlds = pd.to_numeric(ordered.n_worlds, errors="raise").astype(int)
    if n_worlds.nunique() != 1 or int(n_worlds.iloc[0]) <= 0:
        raise ValueError("shadow n_worlds is invalid or inconsistent")
    n = int(n_worlds.iloc[0])
    masks: list[np.ndarray] = []
    for threshold in thresholds:
        column = f"clear_bits_{int(threshold)}"
        if column not in ordered:
            raise ValueError(f"shadow candidates missing {column}")
        masks.append(np.stack([
            decode_clear_bits(value, n) for value in ordered[column]
        ]))
    for high, low, high_line, low_line in zip(
            masks, masks[1:], thresholds, thresholds[1:]):
        if np.any(high & ~low):
            raise ValueError(
                f"support masks are not nested: {high_line:g} is not a "
                f"subset of {low_line:g}")
    probabilities = [mask.mean(axis=1) for mask in masks]
    mean_total = pd.to_numeric(
        ordered.sim_mean, errors="raise",
    ).to_numpy(dtype=float)
    covered = [np.zeros(mask.shape[1], dtype=bool) for mask in masks]
    remaining = set(range(len(ordered)))
    selected: list[int] = []
    while remaining:
        best = max(
            remaining,
            key=lambda ix: (
                *(int(np.count_nonzero(mask[ix] & ~seen))
                  for mask, seen in zip(masks, covered)),
                *(float(probability[ix]) for probability in probabilities),
                float(mean_total[ix]),
                -int(ordered.cand_ix.iloc[ix]),
            ),
        )
        new_counts = [
            int(np.count_nonzero(mask[best] & ~seen))
            for mask, seen in zip(masks, covered)
        ]
        if not any(new_counts):
            selected.extend(sorted(
                remaining,
                key=lambda ix: (
                    *(float(probability[ix])
                      for probability in probabilities),
                    float(mean_total[ix]),
                    -int(ordered.cand_ix.iloc[ix]),
                ),
                reverse=True,
            ))
            break
        selected.append(int(best))
        for mask, seen in zip(masks, covered):
            seen |= mask[best]
        remaining.remove(best)
    return ordered, np.asarray(selected, dtype=int)


def validate_shadow_panel(rows: pd.DataFrame, model: str) -> pd.DataFrame:
    """Fail closed unless a live shadow is complete and reproducible."""
    specs = {
        "tail_k1": ("tail_k1", 1, 49_000),
        "tail_k1_nofloor": ("tail_k1", 1, 0),
        "tail_k3": ("canonical", 3, 49_000),
    }
    if model not in specs:
        raise ValueError(f"unknown shadow model {model!r}")
    expected_variant, expected_k, expected_floor = specs[model]
    required = {
        "panel_run_id", "slate_run_id", "run_type", "code_sha",
        "config_hash", "lever_env", "seeds", "labels_complete",
        "research_eligible", "season", "week", "selected",
        "selected_rank", "tail_line", "n_entries", "actual_score",
        "score_artifact_uri", "score_artifact_sha256",
    }
    missing = required - set(rows.columns)
    if missing:
        raise ValueError(f"shadow panel missing {sorted(missing)}")
    if rows.empty:
        raise ValueError(f"{model} shadow panel is empty")
    if rows.panel_run_id.nunique() != 1 or rows.slate_run_id.nunique() != 1:
        raise ValueError(f"{model} shadow mixes panel or slate runs")
    _panel_started_at(str(rows.panel_run_id.iloc[0]))
    if not rows.run_type.eq("live_shadow").all():
        raise ValueError(f"{model} panel is not a live_shadow run")
    if rows.labels_complete.astype(bool).any() or rows.actual_score.notna().any():
        raise ValueError(f"{model} shadow contains pre-freeze actual labels")
    if rows.research_eligible.astype(bool).any():
        raise ValueError(f"{model} live rows must remain research-ineligible")
    if not pd.to_numeric(rows.n_entries, errors="raise").eq(
            EXPECTED_ENTRIES).all():
        raise ValueError(f"{model} shadow n_entries is not {EXPECTED_ENTRIES}")
    if not np.allclose(
            pd.to_numeric(rows.tail_line, errors="raise"), SELECT_LINE):
        raise ValueError(f"{model} shadow tail line is not {SELECT_LINE:g}")
    selected = rows[rows.selected.astype(bool)].copy()
    if len(selected) != EXPECTED_ENTRIES:
        raise ValueError(f"{model} shadow selected {len(selected)} entries")
    ranks = sorted(pd.to_numeric(
        selected.selected_rank, errors="raise").astype(int).tolist())
    if ranks != list(range(EXPECTED_ENTRIES)):
        raise ValueError(f"{model} shadow selected ranks are incomplete")
    for col in ("code_sha", "config_hash", "lever_env", "seeds"):
        values = rows[col].fillna("").astype(str)
        if values.nunique() != 1 or not values.iloc[0].strip():
            raise ValueError(f"{model} shadow has invalid {col} provenance")
    if rows.code_sha.astype(str).isin(("", "unknown")).any():
        raise ValueError(f"{model} shadow has unknown code provenance")
    lever = str(rows.lever_env.iloc[0])
    seeds = str(rows.seeds.iloc[0])
    if f"MODEL_REGISTRY_VARIANT={expected_variant}" not in lever:
        raise ValueError(f"{model} shadow has the wrong registry variant")
    if f"MIN_LINEUP_SALARY={expected_floor}" not in lever:
        raise ValueError(f"{model} shadow has the wrong salary floor")
    if f"MODEL_ENSEMBLE_SIZE={expected_k}" not in seeds:
        raise ValueError(f"{model} shadow has the wrong ensemble size")
    if (rows.score_artifact_uri.fillna("").astype(str).str.strip().eq("").any()
            or rows.score_artifact_sha256.fillna("").astype(str)
            .str.strip().eq("").any()):
        raise ValueError(f"{model} shadow has no score artifact")
    ordered, full_order = coverage_order(rows)
    rebuilt = ordered.iloc[full_order[:EXPECTED_ENTRIES]].cand_ix.tolist()
    persisted = selected.sort_values("selected_rank").cand_ix.tolist()
    if rebuilt != persisted:
        raise ValueError(f"{model} persisted coverage book does not reproduce")
    return ordered


def _portfolio_rows(
    ordered: pd.DataFrame,
    positions: list[int] | np.ndarray,
    *,
    portfolio_run_id: str,
    portfolio_id: str,
    source_model: str,
    selection_method: str,
    source_quota: int,
    snapshot_slot: str,
    frozen_at: datetime,
    duplicate_backfills: int = 0,
) -> pd.DataFrame:
    positions = np.asarray(positions, dtype=int)
    if len(positions) != source_quota or len(set(positions.tolist())) != len(positions):
        raise ValueError(f"{portfolio_id}/{source_model} has an invalid quota")
    picked = ordered.iloc[positions].copy().reset_index(drop=True)
    first = ordered.iloc[0]
    return pd.DataFrame({
        "frozen_at": frozen_at,
        "portfolio_run_id": portfolio_run_id,
        "portfolio_id": portfolio_id,
        "policy_version": POLICY_VERSION,
        "snapshot_slot": snapshot_slot,
        "season": int(first.season),
        "week": int(first.week),
        "portfolio_entry_rank": np.arange(len(picked), dtype=int),
        "source_model": source_model,
        "source_panel_run_id": str(first.panel_run_id),
        "source_slate_run_id": str(first.slate_run_id),
        "source_quota": int(source_quota),
        "selection_method": selection_method,
        "source_rank": np.arange(len(picked), dtype=int),
        "cand_ix": pd.to_numeric(picked.cand_ix, errors="raise").astype(int),
        "players": picked.players.astype(str).to_numpy(),
        "roster_key": picked.roster_key.astype(str).to_numpy(),
        "p_line": pd.to_numeric(picked.p_line, errors="raise").to_numpy(),
        "sim_mean": pd.to_numeric(picked.sim_mean, errors="raise").to_numpy(),
        "duplicate_backfills": int(duplicate_backfills),
    })


def build_portfolios(
    k1_rows: pd.DataFrame,
    k1_nofloor_rows: pd.DataFrame,
    k3_rows: pd.DataFrame,
    *,
    portfolio_run_id: str,
    snapshot_slot: str,
    frozen_at: datetime | None = None,
) -> pd.DataFrame:
    """Build all nine predeclared books from complete candidate pools."""
    if snapshot_slot not in SLOT_HOURS:
        raise ValueError(f"unknown shadow snapshot slot {snapshot_slot!r}")
    k1 = validate_shadow_panel(k1_rows, "tail_k1")
    k1_nofloor = validate_shadow_panel(
        k1_nofloor_rows, "tail_k1_nofloor")
    k3 = validate_shadow_panel(k3_rows, "tail_k3")
    slate_keys = [
        set(map(tuple, frame[["season", "week"]].drop_duplicates().values))
        for frame in (k1, k1_nofloor, k3)
    ]
    if not all(keys == slate_keys[0] for keys in slate_keys[1:]):
        raise ValueError("shadow policies do not cover the same slate")
    stamp = frozen_at or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    stamp = stamp.astimezone(timezone.utc)

    _, k1_coverage_order = coverage_order(k1)
    _, k1_coverage_187_order = coverage_order(k1, 187.0)
    _, k1_coverage_200_order = coverage_order(k1, 200.0)
    _, k1_extreme_order = extreme_lexicographic_order(k1)
    _, k1_nofloor_order = coverage_order(k1_nofloor)
    _, k3_coverage_order = coverage_order(k3)
    _, k1_rank_order = top_p_order(k1)
    k1_control = k1_coverage_order[:EXPECTED_ENTRIES]
    k1_187 = k1_coverage_187_order[:EXPECTED_ENTRIES]
    k1_200 = k1_coverage_200_order[:EXPECTED_ENTRIES]
    k1_extreme = k1_extreme_order[:EXPECTED_ENTRIES]
    k1_nofloor_control = k1_nofloor_order[:EXPECTED_ENTRIES]
    k3_control = k3_coverage_order[:EXPECTED_ENTRIES]
    k1_top = k1_rank_order[:EXPECTED_ENTRIES]
    n_worlds = int(pd.to_numeric(k1.n_worlds, errors="raise").iloc[0])
    k1_support = np.stack([
        decode_clear_bits(value, n_worlds) for value in k1.clear_bits_194
    ])
    k1_refined, refinement_trace = refine_one_swap(
        k1_support,
        pd.to_numeric(k1.p_line, errors="raise").to_numpy(dtype=float),
        pd.to_numeric(k1.sim_mean, errors="raise").to_numpy(dtype=float),
        k1_control,
    )
    log.info("K1 one-swap refinement completed with %d swaps",
             len(refinement_trace))

    # Preserve the declared 20 K=1 / 60 K=3 allocation. K=1 is the fixed
    # anchor; walk farther down K=3's own complete coverage order whenever a
    # K=3 roster duplicates an already chosen K=1 roster.
    mix_k1 = k1_coverage_order[:20]
    used = set(k1.iloc[mix_k1].roster_key)
    mix_k3: list[int] = []
    skipped = 0
    for position in k3_coverage_order:
        key = str(k3.iloc[int(position)].roster_key)
        if key in used:
            skipped += 1
            continue
        mix_k3.append(int(position))
        used.add(key)
        if len(mix_k3) == 60:
            break
    if len(mix_k3) != 60:
        raise ValueError("K=3 pool cannot backfill the mixed book to 60 entries")

    frames = [
        _portfolio_rows(
            k1, k1_control, portfolio_run_id=portfolio_run_id,
            portfolio_id=K1_COVERAGE, source_model="tail_k1",
            selection_method="coverage194", source_quota=80,
            snapshot_slot=snapshot_slot, frozen_at=stamp),
        _portfolio_rows(
            k1, k1_187, portfolio_run_id=portfolio_run_id,
            portfolio_id=K1_COVERAGE_187, source_model="tail_k1",
            selection_method="coverage187", source_quota=80,
            snapshot_slot=snapshot_slot, frozen_at=stamp),
        _portfolio_rows(
            k1, k1_200, portfolio_run_id=portfolio_run_id,
            portfolio_id=K1_COVERAGE_200, source_model="tail_k1",
            selection_method="coverage200", source_quota=80,
            snapshot_slot=snapshot_slot, frozen_at=stamp),
        _portfolio_rows(
            k1, k1_extreme, portfolio_run_id=portfolio_run_id,
            portfolio_id=K1_EXTREME_LEX, source_model="tail_k1",
            selection_method="coverage_lex_220_210_200", source_quota=80,
            snapshot_slot=snapshot_slot, frozen_at=stamp),
        _portfolio_rows(
            k1, k1_refined, portfolio_run_id=portfolio_run_id,
            portfolio_id=K1_REFINED, source_model="tail_k1",
            selection_method="coverage194_one_swap_lexicographic",
            source_quota=80, snapshot_slot=snapshot_slot, frozen_at=stamp),
        _portfolio_rows(
            k1, k1_top, portfolio_run_id=portfolio_run_id,
            portfolio_id=K1_TOP_P, source_model="tail_k1",
            selection_method="top_p_line", source_quota=80,
            snapshot_slot=snapshot_slot, frozen_at=stamp),
        _portfolio_rows(
            k1_nofloor, k1_nofloor_control,
            portfolio_run_id=portfolio_run_id,
            portfolio_id=K1_NOFLOOR_COVERAGE,
            source_model="tail_k1_nofloor",
            selection_method="coverage194_nofloor", source_quota=80,
            snapshot_slot=snapshot_slot, frozen_at=stamp),
        _portfolio_rows(
            k3, k3_control, portfolio_run_id=portfolio_run_id,
            portfolio_id=K3_COVERAGE, source_model="tail_k3",
            selection_method="coverage194", source_quota=80,
            snapshot_slot=snapshot_slot, frozen_at=stamp),
        _portfolio_rows(
            k1, mix_k1, portfolio_run_id=portfolio_run_id,
            portfolio_id=MIX_20_60, source_model="tail_k1",
            selection_method="coverage194_anchor", source_quota=20,
            snapshot_slot=snapshot_slot, frozen_at=stamp,
            duplicate_backfills=skipped),
        _portfolio_rows(
            k3, mix_k3, portfolio_run_id=portfolio_run_id,
            portfolio_id=MIX_20_60, source_model="tail_k3",
            selection_method="coverage194_duplicate_backfill",
            source_quota=60, snapshot_slot=snapshot_slot, frozen_at=stamp,
            duplicate_backfills=skipped),
    ]
    out = pd.concat(frames, ignore_index=True)
    for portfolio_id, group in out.groupby("portfolio_id"):
        if len(group) != EXPECTED_ENTRIES:
            raise ValueError(f"{portfolio_id} does not contain 80 entries")
        if group.roster_key.duplicated().any():
            raise ValueError(f"{portfolio_id} contains duplicate rosters")
        out.loc[group.index, "portfolio_entry_rank"] = np.arange(
            EXPECTED_ENTRIES, dtype=int)
    return out


def choose_latest_panels(
    rows: pd.DataFrame,
    *,
    season: int,
    week: int,
    target_sunday: date,
    snapshot_slot: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Choose the latest complete-looking policy runs in one CT slot."""
    if snapshot_slot not in SLOT_HOURS:
        raise ValueError(f"unknown shadow snapshot slot {snapshot_slot!r}")
    required = {"generated_at", "panel_run_id", "season", "week"}
    missing = required - set(rows.columns)
    if missing:
        raise ValueError(f"candidate query missing {sorted(missing)}")
    work = rows.copy()
    generated = pd.to_datetime(work.generated_at, utc=True, errors="coerce")
    if generated.isna().any():
        raise ValueError("shadow candidates contain an invalid generated_at")
    panel_starts = work.panel_run_id.map(_panel_started_at)
    local = pd.Series(
        pd.DatetimeIndex(panel_starts).tz_convert("America/Chicago"),
        index=work.index)
    mask = (
        pd.to_numeric(work.season, errors="coerce").eq(season)
        & pd.to_numeric(work.week, errors="coerce").eq(week)
        & local.dt.date.eq(target_sunday)
        & local.dt.hour.eq(SLOT_HOURS[snapshot_slot])
    )
    work = work.loc[mask].copy()
    if work.empty:
        raise ValueError(f"no {snapshot_slot} shadow candidates are available")
    work["_panel_started_at"] = panel_starts.loc[mask].to_numpy()

    selected: list[pd.DataFrame] = []
    for model, prefix in (
            ("tail_k1", "live-shadow-tail_k1-"),
            ("tail_k1_nofloor", "live-shadow-tail_k1_nofloor-"),
            ("tail_k3", "live-shadow-tail_k3-")):
        arm = work[work.panel_run_id.astype(str).str.startswith(prefix)]
        if arm.empty:
            raise ValueError(f"no {model} {snapshot_slot} shadow is available")
        latest = (arm.groupby("panel_run_id")["_panel_started_at"].max()
                  .sort_values().index[-1])
        panel = arm[arm.panel_run_id.eq(latest)].drop(
            columns="_panel_started_at")
        selected.append(panel)
    return selected[0], selected[1], selected[2]


def score_portfolios(memberships: pd.DataFrame,
                     actuals: pd.DataFrame) -> pd.DataFrame:
    """Join authoritative player/DST points and score each frozen book."""
    needed_m = {
        "portfolio_run_id", "portfolio_id", "policy_version",
        "snapshot_slot", "season", "week", "portfolio_entry_rank",
        "source_model", "source_panel_run_id", "cand_ix", "players",
        "roster_key",
    }
    missing = needed_m - set(memberships.columns)
    if missing:
        raise ValueError(f"portfolio memberships missing {sorted(missing)}")
    needed_a = {"season", "week", "id", "actual"}
    missing = needed_a - set(actuals.columns)
    if missing:
        raise ValueError(f"authoritative actuals missing {sorted(missing)}")
    actual = actuals.copy()
    if actual.duplicated(["season", "week", "id"]).any():
        raise ValueError("authoritative actuals contain duplicate player keys")
    actual["actual"] = pd.to_numeric(actual.actual, errors="coerce")
    if actual.actual.isna().any():
        raise ValueError("authoritative actuals contain null scores")
    lookup = actual.set_index(["season", "week", "id"]).actual.to_dict()

    scored = memberships.copy()
    lineup_scores: list[float] = []
    for row in scored.itertuples():
        ids = [item for item in str(row.players).split(",") if item]
        if canonical_roster(row.players) != str(row.roster_key):
            raise ValueError("membership roster key does not match players")
        values = []
        missing_ids = []
        for player_id in ids:
            key = (int(row.season), int(row.week), player_id)
            if key not in lookup:
                missing_ids.append(player_id)
            else:
                values.append(float(lookup[key]))
        if missing_ids:
            raise ValueError(
                f"missing actuals for {int(row.season)}w{int(row.week)}: "
                f"{missing_ids[:4]}")
        lineup_scores.append(float(sum(values)))
    scored["actual_score"] = lineup_scores

    grade_rows: list[dict] = []
    group_cols = [
        "portfolio_run_id", "portfolio_id", "policy_version",
        "snapshot_slot", "season", "week",
    ]
    for keys, group in scored.groupby(group_cols, sort=True):
        if len(group) != EXPECTED_ENTRIES:
            raise ValueError(f"{keys[1]} has {len(group)} entries, expected 80")
        if group.roster_key.duplicated().any():
            raise ValueError(f"{keys[1]} contains duplicate frozen rosters")
        best_ix = group.actual_score.idxmax()
        best = group.loc[best_ix]
        grade_rows.append({
            **dict(zip(group_cols, keys)),
            "graded_at": datetime.now(timezone.utc),
            "n_entries": int(len(group)),
            "weekly_max": float(best.actual_score),
            "best_source_model": str(best.source_model),
            "best_source_panel_run_id": str(best.source_panel_run_id),
            "best_cand_ix": int(best.cand_ix),
            "best_roster_key": str(best.roster_key),
        })
    return pd.DataFrame(grade_rows)


def summarize_grades(grades: pd.DataFrame) -> pd.DataFrame:
    """Full operator tail grid for each independently timed portfolio."""
    needed = {"snapshot_slot", "portfolio_id", "weekly_max"}
    missing = needed - set(grades.columns)
    if missing:
        raise ValueError(f"grade rows missing {sorted(missing)}")
    if grades.empty:
        raise ValueError("grade rows are empty")
    rows: list[dict] = []
    thresholds = (187, 194, 200, 210, 220, 230, 240)
    for (slot, portfolio_id), group in grades.groupby(
            ["snapshot_slot", "portfolio_id"], sort=True):
        values = pd.to_numeric(group.weekly_max, errors="raise")
        row = {
            "snapshot_slot": str(slot),
            "portfolio_id": str(portfolio_id),
            "weeks": int(len(group)),
            "mean_weekly_max": float(values.mean()),
            "max_weekly_max": float(values.max()),
        }
        for threshold in thresholds:
            row[f"ge_{threshold}"] = int(values.ge(threshold).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def _load_existing(portfolio_run_id: str) -> pd.DataFrame:
    from ..bq import query_df

    try:
        return query_df(f"""
            SELECT * FROM `{settings.predictions}.{PORTFOLIO_TABLE}`
            WHERE portfolio_run_id = @portfolio_run_id
            """, params={"portfolio_run_id": portfolio_run_id})
    except Exception as exc:
        text = str(exc).lower()
        if "not found" in text and PORTFOLIO_TABLE in text:
            return pd.DataFrame()
        raise


def freeze(snapshot_slot: str) -> dict:
    """Freeze one early/late prospective portfolio set in BigQuery."""
    from ..bq import load_dataframe, query_df
    from ..inference.tail_shadow import upcoming_season_week

    if snapshot_slot not in SLOT_HOURS:
        raise ValueError(f"unknown shadow snapshot slot {snapshot_slot!r}")
    season, week, sunday = upcoming_season_week()
    candidates = query_df(f"""
        SELECT generated_at, panel_run_id, slate_run_id, run_type, code_sha,
               config_hash, lever_env, seeds, labels_complete,
               research_eligible, season, week, cand_ix, players, selected,
               selected_rank, p_line, sim_mean, actual_score, tail_line,
               n_entries, n_worlds, clear_bits_187, clear_bits_194,
               clear_bits_200, clear_bits_210, clear_bits_220,
               score_artifact_uri, score_artifact_sha256
        FROM `{settings.predictions}.live_candidates_shadow`
        WHERE season = @season AND week = @week AND run_type = 'live_shadow'
        """, params={"season": season, "week": week})
    k1, k1_nofloor, k3 = choose_latest_panels(
        candidates, season=season, week=week, target_sunday=sunday,
        snapshot_slot=snapshot_slot)
    run_id = f"live-tail-portfolios-{season}w{week:02d}-{snapshot_slot}"
    memberships = build_portfolios(
        k1, k1_nofloor, k3, portfolio_run_id=run_id,
        snapshot_slot=snapshot_slot)
    existing = _load_existing(run_id)
    if not existing.empty:
        left = existing[_MEMBERSHIP_ID_COLUMNS].sort_values(
            _MEMBERSHIP_ID_COLUMNS).reset_index(drop=True).astype(str)
        right = memberships[_MEMBERSHIP_ID_COLUMNS].sort_values(
            _MEMBERSHIP_ID_COLUMNS).reset_index(drop=True).astype(str)
        if not left.equals(right):
            raise RuntimeError(
                f"immutable portfolio run {run_id} already exists with "
                "different membership")
        log.info("portfolio run %s already frozen identically", run_id)
        return {"portfolio_run_id": run_id, "rows": int(len(existing)),
                "idempotent": True}
    load_dataframe(
        memberships, f"{settings.predictions}.{PORTFOLIO_TABLE}",
        write_disposition="WRITE_APPEND")
    log.info("froze %s: %d membership rows", run_id, len(memberships))
    return {"portfolio_run_id": run_id, "rows": int(len(memberships)),
            "idempotent": False}


def grade(*, write: bool = False) -> pd.DataFrame:
    """Grade every complete frozen portfolio currently backed by actuals."""
    from ..bq import load_dataframe, query_df

    memberships = query_df(f"""
        SELECT * FROM `{settings.predictions}.{PORTFOLIO_TABLE}`
        WHERE policy_version = @policy_version
        """, params={"policy_version": POLICY_VERSION})
    if memberships.empty:
        raise RuntimeError("no frozen tail portfolio memberships exist")
    seasons = sorted(pd.to_numeric(
        memberships.season, errors="raise").astype(int).unique().tolist())
    actuals = query_df(f"""
        SELECT season, week, gsis_id AS id, dk_points AS actual
        FROM `{settings.features}.player_week_actuals`
        WHERE season IN UNNEST(@seasons)
        UNION ALL
        SELECT season, week, CONCAT('DST_', team) AS id,
               dst_dk_points AS actual
        FROM `{settings.features}.team_defense_week`
        WHERE season IN UNNEST(@seasons)
        """, params={"seasons": seasons})
    grades = score_portfolios(memberships, actuals)
    if write:
        load_dataframe(
            grades, f"{settings.predictions}.{GRADE_TABLE}",
            write_disposition="WRITE_APPEND")
    cols = ["season", "week", "snapshot_slot", "portfolio_id", "weekly_max"]
    print("FROZEN WEEKLY MAXIMA")
    print(grades[cols].sort_values(cols[:-1]).to_string(index=False))
    summary = summarize_grades(grades)
    print("\nPROSPECTIVE TAIL GRID")
    print(summary.to_string(index=False))

    keys = ["season", "week", "snapshot_slot"]
    pivot = grades.pivot(
        index=keys, columns="portfolio_id", values="weekly_max")
    if K1_COVERAGE in pivot:
        control = pivot[K1_COVERAGE]
        print("\nPAIRED >=200 GAINS/LOSSES VS K=1 COVERAGE")
        for portfolio_id in (
                K1_COVERAGE_187, K1_COVERAGE_200, K1_EXTREME_LEX, K1_REFINED,
                K1_TOP_P, K1_NOFLOOR_COVERAGE,
                MIX_20_60, K3_COVERAGE):
            if portfolio_id not in pivot:
                continue
            challenger = pivot[portfolio_id]
            gained = int((challenger.ge(200) & control.lt(200)).sum())
            lost = int((challenger.lt(200) & control.ge(200)).sum())
            print(f"{portfolio_id}: gained={gained} lost={lost}")
    return grades
