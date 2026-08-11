"""Point-in-time contracts and immutable artifacts for the Route Share shadow.

The licensed feed is allowed to affect only the isolated prospective treatment.
Every supported live row must be attributable to the exact pre-lock source file,
and the player distributions used by both paired arms are frozen before lineup
generation so the distribution gate can be graded without reconstructing state.
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import numpy as np
import pandas as pd

from ..config import settings


ROUTE_FEATURES = (
    "fp_route_share_last",
    "fp_route_share_l4",
    "fp_route_share_jump",
    "fp_route_cross_season",
)
ROLE_FEATURES = (
    "target_share_last",
    "carry_share_last",
    "snap_share_last",
    "target_share_jump",
    "carry_share_jump",
    "snap_share_jump",
)
ROUTE_SOURCE_COLUMNS = (
    "fp_route_source_season",
    "fp_route_source_week",
    "fp_route_source_sha256",
    "fp_route_prior_observations",
    "fp_route_fallback",
)


@dataclass(frozen=True)
class DistributionArtifactSpec:
    """Identity of one pre-lock player-distribution capture."""

    bucket: str
    panel_run_id: str
    arm: str
    model_variant: str
    belief_model_variant: str


def component_feature_names(model) -> set[str]:
    """Feature-name union from a loaded component registry."""
    return {
        str(feature)
        for booster in model.models.values()
        for feature in booster.feature_name()
    }


def validate_component_feature_contract(
    model,
    *,
    registry_variant: str,
    required: Iterable[str] = (),
    forbidden: Iterable[str] = (),
) -> None:
    """Fail closed when a registry does not match its frozen arm identity."""
    required_set = set(required)
    forbidden_set = set(forbidden)
    violations = {}
    for component, booster in model.models.items():
        names = {str(feature) for feature in booster.feature_name()}
        missing = sorted(required_set - names)
        present = sorted(forbidden_set & names)
        if missing or present:
            violations[str(component)] = {
                "missing": missing, "forbidden": present}
    if violations:
        raise RuntimeError(
            f"registry variant {registry_variant} violates its feature "
            f"contract: {violations}")


def apply_live_route_policy(
    frame: pd.DataFrame, season: int, week: int,
) -> pd.DataFrame:
    """Mask Route Share unless it is the frozen live source for the target.

    Week 1 may use only a prior-season observation. Week 2 onward requires the
    immediately preceding week from the same season. This is intentionally
    stricter than the generic historical as-of join: a late or missed weekly
    download falls back instead of silently using a stale observation.
    """
    out = frame.copy()
    source_season = pd.to_numeric(
        out.get(
            "fp_route_source_season",
            pd.Series(np.nan, index=out.index)),
        errors="coerce")
    source_week = pd.to_numeric(
        out.get(
            "fp_route_source_week",
            pd.Series(np.nan, index=out.index)),
        errors="coerce")
    source_hash = out.get(
        "fp_route_source_sha256", pd.Series(pd.NA, index=out.index)
    ).astype("string").str.strip()
    attached = source_season.notna() & source_week.notna()
    source_order = source_season * 100 + source_week
    if (attached & source_order.ge(int(season) * 100 + int(week))).any():
        raise RuntimeError(
            f"Route Share live frame contains a same/future source for "
            f"{season} Week {week}")
    if int(week) == 1:
        supported = source_season.lt(int(season))
    else:
        supported = (
            source_season.eq(int(season))
            & source_week.eq(int(week) - 1)
        )
    supported &= source_hash.str.fullmatch(r"[0-9a-fA-F]{64}", na=False)

    for column in ROUTE_FEATURES:
        if column not in out:
            out[column] = np.nan
        out.loc[~supported, column] = np.nan
    out["fp_route_shadow_supported"] = supported.astype(bool)
    out.loc[~supported, "fp_route_fallback"] = (
        "route-share-live-source-unavailable-fallback")
    out.loc[supported, "fp_route_cross_season"] = int(week == 1)
    return out


def require_prior_week_source(season: int, week: int) -> None:
    """Require an attributable W-1 import before a Week 2+ treatment run."""
    if int(week) <= 1:
        return
    from ..bq import query_df

    result = query_df(
        f"""
        SELECT COUNTIF(gsis_id IS NOT NULL) AS resolved_rows,
               COUNT(DISTINCT source_sha256) AS source_files
        FROM `{settings.raw}.fantasy_points_route_share`
        WHERE CAST(season AS INT64) = @season
          AND CAST(week AS INT64) = @source_week
        """,
        params={"season": int(season), "source_week": int(week) - 1},
    )
    rows = 0 if result.empty else int(result.resolved_rows.iloc[0] or 0)
    files = 0 if result.empty else int(result.source_files.iloc[0] or 0)
    if rows <= 0 or files <= 0:
        raise RuntimeError(
            f"Route Share treatment requires a resolved, manifested "
            f"{season} Week {week - 1} import before Week {week}")


def _string_array(values: pd.Series | list) -> np.ndarray:
    return np.asarray(pd.Series(values).fillna("").astype(str), dtype=np.str_)


def distribution_artifact_payload(
    slate: pd.DataFrame,
    draws: np.ndarray,
    belief_slate: pd.DataFrame,
    belief_draws: np.ndarray,
    *,
    season: int,
    week: int,
    model_version: str,
    belief_model_version: str,
    spec: DistributionArtifactSpec,
    generated_at: datetime | None = None,
) -> bytes:
    """Serialize aligned control/treatment player distributions without pickle."""
    skill = slate[slate.draw_idx >= 0].copy().reset_index(drop=True)
    belief = belief_slate[belief_slate.draw_idx >= 0].copy().reset_index(drop=True)
    if list(skill.id) != list(belief.id):
        raise RuntimeError("base and belief player distributions are not aligned")
    base_ix = skill.draw_idx.astype(int).to_numpy()
    belief_ix = belief.draw_idx.astype(int).to_numpy()
    if draws.ndim != 2 or belief_draws.ndim != 2:
        raise ValueError("player draws must be two-dimensional")
    if draws.shape[1] != belief_draws.shape[1]:
        raise RuntimeError("base and belief distributions use different worlds")

    stamp = generated_at or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    metadata = {
        "schema_version": 1,
        "generated_at": stamp.astimezone(timezone.utc).isoformat(),
        "season": int(season),
        "week": int(week),
        "panel_run_id": spec.panel_run_id,
        "arm": spec.arm,
        "model_variant": spec.model_variant,
        "belief_model_variant": spec.belief_model_variant,
        "model_version": model_version,
        "belief_model_version": belief_model_version,
        "n_players": len(skill),
        "n_worlds": int(draws.shape[1]),
    }
    arrays: dict[str, np.ndarray] = {
        "metadata_json": np.asarray(
            json.dumps(metadata, sort_keys=True), dtype=np.str_),
        "dk_player_id": skill.id.astype(np.int64).to_numpy(),
        "gsis_id": _string_array(skill.get("gsis_id", [])),
        "name": _string_array(skill.get("name", [])),
        "position": _string_array(skill.get("pos", [])),
        "team": _string_array(skill.get("team", [])),
        "base_draws": np.asarray(draws[base_ix], dtype=np.float32),
        "belief_draws": np.asarray(belief_draws[belief_ix], dtype=np.float32),
    }
    for column in (
        "model_points_pre", "market_points", "mean_projection",
        "proj_p10", "proj_p50", "proj_p90", "proj_std",
        *ROUTE_SOURCE_COLUMNS, *ROUTE_FEATURES, "fp_route_shadow_supported",
    ):
        if column not in skill:
            continue
        if column in {"fp_route_source_sha256", "fp_route_fallback"}:
            arrays[column] = _string_array(skill[column])
        elif column == "fp_route_shadow_supported":
            arrays[column] = skill[column].fillna(False).astype(bool).to_numpy()
        else:
            arrays[column] = pd.to_numeric(
                skill[column], errors="coerce").to_numpy(dtype=np.float64)
    for column in sorted(c for c in skill if c.startswith("component_mean_")):
        arrays[column] = pd.to_numeric(
            skill[column], errors="coerce").to_numpy(dtype=np.float64)
    for column in (
        "model_points_pre", "market_points", "mean_projection",
        "proj_p10", "proj_p50", "proj_p90", "proj_std",
        *ROUTE_SOURCE_COLUMNS, *ROUTE_FEATURES, "fp_route_shadow_supported",
    ):
        if column not in belief:
            continue
        name = f"belief_{column}"
        if column in {"fp_route_source_sha256", "fp_route_fallback"}:
            arrays[name] = _string_array(belief[column])
        elif column == "fp_route_shadow_supported":
            arrays[name] = belief[column].fillna(False).astype(bool).to_numpy()
        else:
            arrays[name] = pd.to_numeric(
                belief[column], errors="coerce").to_numpy(dtype=np.float64)
    for column in sorted(
        c for c in belief if c.startswith("component_mean_")):
        arrays[f"belief_{column}"] = pd.to_numeric(
            belief[column], errors="coerce").to_numpy(dtype=np.float64)

    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arrays)
    return buffer.getvalue()


def persist_distribution_artifact(
    slate: pd.DataFrame,
    draws: np.ndarray,
    belief_slate: pd.DataFrame,
    belief_draws: np.ndarray,
    *,
    season: int,
    week: int,
    model_version: str,
    belief_model_version: str,
    spec: DistributionArtifactSpec,
    generated_at: datetime | None = None,
) -> tuple[str, str]:
    """Write the player distributions once; retries may not overwrite them."""
    if not spec.bucket.strip():
        raise RuntimeError("Route Share distribution artifact bucket is required")
    payload = distribution_artifact_payload(
        slate, draws, belief_slate, belief_draws,
        season=season, week=week, model_version=model_version,
        belief_model_version=belief_model_version, spec=spec,
        generated_at=generated_at,
    )
    digest = hashlib.sha256(payload).hexdigest()
    object_name = (
        f"route_share_player_distributions/{spec.panel_run_id}/"
        f"{season}_w{week:02d}_{spec.arm}_{digest[:16]}.npz")
    uri = f"gs://{spec.bucket}/{object_name}"
    from google.cloud import storage

    storage.Client().bucket(spec.bucket).blob(object_name).upload_from_string(
        payload,
        content_type="application/octet-stream",
        if_generation_match=0,
    )
    return uri, digest
