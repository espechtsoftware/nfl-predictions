"""Materialize paired L1 ordinary/shootout calibration shards.

This is the narrow bridge between a content-pinned, point-in-time historical
component surface and :mod:`corpus_r6_belief_evidence_v1`.  It deliberately
does not fit component models, infer missing component means, read player or
lineup outcomes, calibrate the shootout probability, or score a lineup.

The retained historical player-world matrices are not a substitute for the
eleven component means: simulation is many-to-one and the inputs cannot be
recovered from final draws.  Accordingly, an all-null legacy
``component_mean_*`` surface fails with a concrete rematerialization error.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from ..models.components import COMPONENT_NAMES, RATE_CLIPS
from .belief_world_v1 import canonical_json_bytes, canonical_sha256
from .corpus_r6_belief_calibration_v1 import CALIBRATION_SEASONS
from .corpus_r6_belief_evidence_v1 import L1_BANK_MANIFEST_SCHEMA
from .corpus_r6_l1_simulator_components_v1 import (
    build_l1_simulator_components_v1,
)
from .corpus_retrieval_engine import canonical_npz_bytes
from .object_identity import IDENTITY_FIELDS, content_identity


SCHEMA: Final = "corpus-r6-l1-conditional-shard-materialization/v1"
PREFLIGHT_SCHEMA: Final = "corpus-r6-l1-component-surface-preflight/v1"
SHARD_RECEIPT_SCHEMA: Final = "corpus-r6-l1-conditional-shard-receipt/v1"
EXPECTED_WEEK_COUNTS: Final = {2019: 17, 2021: 18, 2022: 18}
EXPECTED_SLATE_COUNT: Final = sum(EXPECTED_WEEK_COUNTS.values())
SKILL_POSITIONS: Final = ("QB", "RB", "WR", "TE")
COMPONENT_COLUMNS: Final = tuple(
    f"component_mean_{name}" for name in COMPONENT_NAMES
)
SURFACE_COLUMNS: Final = (
    "gsis_id",
    "season",
    "week",
    "pos",
    "team",
    "opp",
    "game_id",
    "game_total",
    *COMPONENT_COLUMNS,
)


class L1ConditionalShardError(ValueError):
    """The L1 component surface or shard publication was not exact."""


@dataclass(frozen=True, slots=True)
class L1ConditionalShardMaterialization:
    manifest: dict[str, object]
    receipt: dict[str, object]


def _identity(
    value: Mapping[str, object], *, label: str,
) -> dict[str, object]:
    try:
        fields = content_identity(value)
    except (TypeError, ValueError) as exc:
        raise L1ConditionalShardError(f"{label} identity differs") from exc
    return dict(zip(IDENTITY_FIELDS, fields, strict=True))


def local_file_identity(path: str | Path) -> dict[str, object]:
    source = Path(path).resolve(strict=True)
    raw = source.read_bytes()
    stat = source.stat()
    return {
        "uri": source.as_uri(),
        "generation": str(stat.st_mtime_ns),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _records_sha256(frame: pd.DataFrame) -> str:
    records: list[dict[str, object]] = []
    for values in frame.loc[:, list(SURFACE_COLUMNS)].itertuples(
        index=False, name=None
    ):
        record: dict[str, object] = {}
        for name, value in zip(SURFACE_COLUMNS, values, strict=True):
            if isinstance(value, np.integer):
                value = int(value)
            elif isinstance(value, np.floating):
                value = float(value)
            record[name] = value
        records.append(record)
    return canonical_sha256(records)


def component_surface_preflight_v1(
    rows: pd.DataFrame,
    *,
    source_identity: Mapping[str, object],
) -> dict[str, object]:
    """Report component availability without reading any outcome column."""
    if not isinstance(rows, pd.DataFrame):
        raise L1ConditionalShardError("component surface must be a dataframe")
    missing_columns = sorted(set(SURFACE_COLUMNS) - set(rows.columns))
    source = _identity(source_identity, label="component surface")
    if missing_columns:
        body: dict[str, object] = {
            "schema": PREFLIGHT_SCHEMA,
            "source_identity": source,
            "calibration_seasons": list(CALIBRATION_SEASONS),
            "required_columns": list(SURFACE_COLUMNS),
            "missing_columns": missing_columns,
            "skill_row_count": 0,
            "slate_count": 0,
            "week_counts": {},
            "nonnull_rows_by_component": {},
            "complete_component_row_count": 0,
            "ready": False,
            "values_read": "identity-and-component-support-only",
            "uses_player_outcomes": False,
            "uses_lineup_outcomes": False,
        }
        body["receipt_sha256"] = canonical_sha256(body)
        return body

    surface = rows.loc[:, list(SURFACE_COLUMNS)].copy()
    surface["season"] = pd.to_numeric(
        surface["season"], errors="coerce"
    )
    surface["week"] = pd.to_numeric(surface["week"], errors="coerce")
    position = surface["pos"].astype("string").str.upper()
    calibration = surface[
        surface["season"].isin(CALIBRATION_SEASONS)
        & position.isin(SKILL_POSITIONS)
    ].copy()
    nonnull = {
        name: int(pd.to_numeric(calibration[name], errors="coerce").notna().sum())
        for name in COMPONENT_COLUMNS
    }
    complete = calibration.loc[:, list(COMPONENT_COLUMNS)].apply(
        pd.to_numeric, errors="coerce"
    ).notna().all(axis=1)
    week_counts = {
        str(int(season)): int(count)
        for season, count in calibration.groupby("season")["week"].nunique().items()
        if pd.notna(season)
    }
    slate_count = int(
        calibration[["season", "week"]].drop_duplicates().shape[0]
    )
    body = {
        "schema": PREFLIGHT_SCHEMA,
        "source_identity": source,
        "calibration_seasons": list(CALIBRATION_SEASONS),
        "required_columns": list(SURFACE_COLUMNS),
        "missing_columns": [],
        "skill_row_count": len(calibration),
        "slate_count": slate_count,
        "week_counts": week_counts,
        "nonnull_rows_by_component": nonnull,
        "complete_component_row_count": int(complete.sum()),
        "ready": (
            len(calibration) > 0
            and int(complete.sum()) == len(calibration)
            and slate_count == EXPECTED_SLATE_COUNT
            and week_counts == {
                str(season): count
                for season, count in EXPECTED_WEEK_COUNTS.items()
            }
        ),
        "values_read": "identity-and-component-support-only",
        "uses_player_outcomes": False,
        "uses_lineup_outcomes": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return body


def validate_l1_component_surface_v1(
    rows: pd.DataFrame,
    *,
    source_identity: Mapping[str, object],
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Validate the fixed 53-slate component surface and canonicalize rows."""
    preflight = component_surface_preflight_v1(
        rows, source_identity=source_identity
    )
    if preflight["missing_columns"]:
        raise L1ConditionalShardError(
            "component surface is missing required columns "
            f"{preflight['missing_columns']}"
        )
    if not preflight["ready"]:
        missing_rows = int(preflight["skill_row_count"]) - int(
            preflight["complete_component_row_count"]
        )
        if missing_rows:
            raise L1ConditionalShardError(
                "component surface lacks finite component means for "
                f"{missing_rows}/{preflight['skill_row_count']} calibration "
                "skill rows; final player worlds and mean_projection cannot "
                "reconstruct the eleven simulator inputs, so rematerialize "
                "the exact walk-forward component surface"
            )
        raise L1ConditionalShardError(
            "component surface CAL19/WF21/HOLD22 coverage differs: "
            f"slates={preflight['slate_count']} "
            f"weeks={preflight['week_counts']}"
        )

    out = rows.loc[:, list(SURFACE_COLUMNS)].copy()
    out["season"] = pd.to_numeric(out["season"], errors="raise").astype(int)
    out["week"] = pd.to_numeric(out["week"], errors="raise").astype(int)
    out["pos"] = out["pos"].astype("string").str.upper()
    out = out[
        out["season"].isin(CALIBRATION_SEASONS)
        & out["pos"].isin(SKILL_POSITIONS)
    ].copy()
    observed_weeks = {
        season: tuple(sorted(
            int(value)
            for value in out.loc[
                out["season"].eq(season), "week"
            ].unique()
        ))
        for season in EXPECTED_WEEK_COUNTS
    }
    expected_weeks = {
        season: tuple(range(1, count + 1))
        for season, count in EXPECTED_WEEK_COUNTS.items()
    }
    if observed_weeks != expected_weeks:
        raise L1ConditionalShardError(
            "component surface calibration week identities differ"
        )
    for name in ("gsis_id", "team", "opp", "game_id"):
        out[name] = out[name].astype("string")
        if out[name].isna().any() or (out[name].str.len() == 0).any():
            raise L1ConditionalShardError(
                f"component surface {name} identities are empty"
            )
    if out.duplicated(["gsis_id", "season", "week"]).any():
        raise L1ConditionalShardError(
            "component surface repeats a skill-player/week identity"
        )
    out["game_total"] = pd.to_numeric(out["game_total"], errors="raise")
    if not np.isfinite(out["game_total"].to_numpy(dtype=float)).all():
        raise L1ConditionalShardError("component surface game totals are nonfinite")
    for name in COMPONENT_COLUMNS:
        out[name] = pd.to_numeric(out[name], errors="raise").astype(float)
        if not np.isfinite(out[name].to_numpy(dtype=float)).all():
            raise L1ConditionalShardError(
                f"component surface {name} is nonfinite"
            )

    counts = (
        "targets", "rec_tds", "carries", "rush_tds", "pass_attempts",
        "pass_tds", "interceptions",
    )
    for name in counts:
        if (out[f"component_mean_{name}"] < 0.0).any():
            raise L1ConditionalShardError(
                f"component surface {name} contains a negative mean"
            )
    for name, (lower, upper) in RATE_CLIPS.items():
        values = out[f"component_mean_{name}"]
        if not values.between(lower, upper).all():
            raise L1ConditionalShardError(
                f"component surface {name} is outside the served clip"
            )
    qb = out["pos"].eq("QB")
    if not np.allclose(
        out.loc[qb, ["component_mean_targets", "component_mean_rec_tds"]],
        0.0,
        rtol=0.0,
        atol=0.0,
    ):
        raise L1ConditionalShardError(
            "component surface QB receiving means differ from served masks"
        )
    if not np.allclose(
        out.loc[
            ~qb,
            [
                "component_mean_pass_attempts",
                "component_mean_pass_tds",
                "component_mean_interceptions",
            ],
        ],
        0.0,
        rtol=0.0,
        atol=0.0,
    ):
        raise L1ConditionalShardError(
            "component surface non-QB passing means differ from served masks"
        )
    for key, game in out.groupby(["season", "week", "game_id"], sort=True):
        teams = tuple(sorted(str(value) for value in game["team"].unique()))
        if len(teams) != 2:
            raise L1ConditionalShardError(
                f"component surface game {key} does not contain two teams"
            )
        if game["game_total"].nunique() != 1:
            raise L1ConditionalShardError(
                f"component surface game {key} has inconsistent game totals"
            )
        for team in teams:
            observed = set(
                str(value) for value in game.loc[game["team"].eq(team), "opp"]
            )
            if observed != {value for value in teams if value != team}:
                raise L1ConditionalShardError(
                    f"component surface game {key} opponent mapping differs"
                )
    out = out.sort_values(
        ["season", "week", "game_id", "team", "pos", "gsis_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    return out, preflight


def _slate_seed(base_seed: int, season: int, week: int) -> int:
    if type(base_seed) is not int or base_seed < 0:
        raise L1ConditionalShardError("base seed must be a nonnegative integer")
    digest = sha256(
        canonical_json_bytes([base_seed, int(season), int(week), "l1-shard"])
    ).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


def _write_create_once(path: Path, raw: bytes) -> None:
    if path.exists():
        raise L1ConditionalShardError(f"output already exists: {path}")
    path.write_bytes(raw)


def materialize_l1_conditional_shards_v1(
    *,
    component_surface: pd.DataFrame,
    component_surface_identity: Mapping[str, object],
    output_dir: str | Path,
    n_sims: int,
    base_seed: int,
    usage_dirichlet_k: float = 20.0,
    td_allocation_k: float | None = None,
) -> L1ConditionalShardMaterialization:
    """Create the exact 53 paired bank shards and extraction manifest."""
    if type(n_sims) is not int or not 100 <= n_sims <= 100_000:
        raise L1ConditionalShardError(
            "n_sims must be an integer in [100,100000]"
        )
    _slate_seed(base_seed, 2019, 1)
    surface, preflight = validate_l1_component_surface_v1(
        component_surface,
        source_identity=component_surface_identity,
    )
    root = Path(output_dir).resolve()
    try:
        root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise L1ConditionalShardError("output directory already exists") from exc
    source = _identity(component_surface_identity, label="component surface")
    manifest_shards: list[dict[str, object]] = []
    receipt_shards: list[dict[str, object]] = []
    for season, week in sorted(
        (int(row.season), int(row.week))
        for row in surface[["season", "week"]]
        .drop_duplicates()
        .itertuples(index=False)
    ):
        slate = surface[
            surface["season"].eq(season) & surface["week"].eq(week)
        ].reset_index(drop=True)
        components = slate.loc[:, list(COMPONENT_COLUMNS)].rename(
            columns={
                f"component_mean_{name}": name for name in COMPONENT_NAMES
            }
        )
        banks = build_l1_simulator_components_v1(
            components=components,
            game_ids=slate["game_id"].astype(str).tolist(),
            team_ids=slate["team"].astype(str).tolist(),
            game_totals=slate["game_total"].astype(float).tolist(),
            n_sims=n_sims,
            base_seed=_slate_seed(base_seed, season, week),
            ordinary_environment=None,
            source_identities={"component_surface": source},
            usage_dirichlet_k=usage_dirichlet_k,
            td_allocation_k=td_allocation_k,
        )
        player_values = slate["gsis_id"].astype(str).tolist()
        player_ids = np.asarray(
            player_values,
            dtype=f"<U{max(len(value) for value in player_values)}",
        )
        raw, descriptors = canonical_npz_bytes((
            ("player_ids", player_ids),
            ("ordinary_draws", banks.ordinary_draws),
            ("shootout_draws", banks.shootout_draws),
        ))
        stem = f"{season}-w{week:02d}"
        path = root / f"{stem}.npz"
        _write_create_once(path, raw)
        artifact_identity = local_file_identity(path)
        shard_receipt: dict[str, object] = {
            "schema": SHARD_RECEIPT_SCHEMA,
            "season": season,
            "week": week,
            "player_count": len(slate),
            "world_count": n_sims,
            "ordered_player_ids_sha256": canonical_sha256(
                slate["gsis_id"].astype(str).tolist()
            ),
            "npz_identity": artifact_identity,
            "npz_array_descriptors": descriptors,
            "component_receipt": banks.receipt,
            "component_surface_identity": source,
            "uses_player_outcomes": False,
            "uses_lineup_outcomes": False,
            "historical_lineup_scoring_licensed": False,
            "production_change_licensed": False,
        }
        shard_receipt["receipt_sha256"] = canonical_sha256(shard_receipt)
        receipt_path = root / f"{stem}.receipt.json"
        _write_create_once(receipt_path, canonical_json_bytes(shard_receipt))
        manifest_shards.append({
            "season": season,
            "week": week,
            "path": str(path),
            "source_identity": artifact_identity,
        })
        receipt_shards.append({
            "season": season,
            "week": week,
            "artifact_identity": artifact_identity,
            "shard_receipt_identity": local_file_identity(receipt_path),
            "component_receipt_sha256": banks.receipt["receipt_sha256"],
        })
    manifest: dict[str, object] = {
        "schema": L1_BANK_MANIFEST_SCHEMA,
        "shards": manifest_shards,
    }
    receipt = {
        "schema": SCHEMA,
        "component_surface_identity": source,
        "component_surface_records_sha256": _records_sha256(surface),
        "component_surface_preflight_sha256": preflight["receipt_sha256"],
        "calibration_seasons": list(CALIBRATION_SEASONS),
        "slate_count": len(manifest_shards),
        "n_sims": n_sims,
        "base_seed": base_seed,
        "usage_dirichlet_k": float(usage_dirichlet_k),
        "td_allocation_k": (
            None if td_allocation_k is None else float(td_allocation_k)
        ),
        "shards": receipt_shards,
        "manifest_sha256": canonical_sha256(manifest),
        "component_means_inferred": False,
        "final_worlds_inverted": False,
        "uses_player_outcomes": False,
        "uses_lineup_outcomes": False,
        "historical_lineup_scoring_licensed": False,
        "production_change_licensed": False,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    _write_create_once(root / "l1-bank-manifest.json", canonical_json_bytes(manifest))
    _write_create_once(
        root / "l1-shard-materialization-receipt.json",
        canonical_json_bytes(receipt),
    )
    return L1ConditionalShardMaterialization(manifest, receipt)


__all__ = [
    "COMPONENT_COLUMNS",
    "EXPECTED_SLATE_COUNT",
    "EXPECTED_WEEK_COUNTS",
    "L1ConditionalShardError",
    "L1ConditionalShardMaterialization",
    "component_surface_preflight_v1",
    "local_file_identity",
    "materialize_l1_conditional_shards_v1",
    "validate_l1_component_surface_v1",
]
