#!/usr/bin/env python3
"""Produce the outcome-blind live panels consumed by the B1 shadow.

This is deliberately an isolated, default-off upstream scaffold.  It does
not fit or score the B1 model and it does not freeze, grade, or deploy the
shadow.  A successful invocation writes six named live panels to the
existing research staging tables:

* one canonical panel built by the complete adopted five-block CBWU policy;
* five companion panels, one for each registered production seed pair.

The companion panels provide the repeated pre-lock simulation summaries used
by the historical model while the canonical panel alone defines the equal-
budget control/challenger candidate pool.  No realized-score column is
selected by this program.  A create-only remote attempt precedes generation;
partial or ambiguous attempts must use a new snapshot identity rather than
appending duplicate panel keys.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

import pandas as pd
from google.api_core.exceptions import PreconditionFailed
from google.cloud import bigquery, storage


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY  # noqa: E402
from nfl_dfs.research.b1_corpus_tail import (  # noqa: E402
    CorpusTailError,
    build_deduplicated_dataset,
)


PROJECT = "nfl-predictions-503414"
CANDIDATE_TABLE = f"{PROJECT}.nfl_predictions.replay_candidates_staging"
PLAYER_TABLE = f"{PROJECT}.nfl_predictions.slate_player_features"
ENABLED_ENV = "B1_CORPUS_TAIL_PANEL_PRODUCER_ENABLED"
SEASON = 2026
WEEKS = tuple(range(1, 7))
ENTRIES = 80
RUN_TYPE_CANONICAL = "prospective_b1_corpus_tail_canonical"
RUN_TYPE_COMPANION = "prospective_b1_corpus_tail_companion"
RECEIPT_VERSION = "b1-corpus-tail-panel-source-receipt-v1"
ATTEMPT_VERSION = "b1-corpus-tail-panel-source-attempt-v1"
RECEIPT_ROOT = (
    f"gs://{PROJECT}-raw/research/b1-corpus-tail-shadow-panel-sources"
)

_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")

CANDIDATE_COLUMNS = (
    "generated_at", "panel_run_id", "slate_run_id", "run_type",
    "code_sha", "code_dirty", "config_hash", "lever_env", "seeds",
    "candidate_batch_metadata", "labels_complete",
    "research_eligible", "season", "week", "cand_ix", "players", "tag",
    "selected", "selected_rank", "salary", "p_line", "sim_mean", "sim_sd",
    "sim_q50", "sim_q90", "sim_q99", "sim_rank_p_line", "tail_line",
    "n_entries", "n_sims", "n_worlds",
)
PLAYER_COLUMNS = (
    "generated_at", "panel_run_id", "slate_run_id", "code_sha",
    "config_hash", "research_eligible", "season", "week", "id", "pos",
    "gsis_id", "team", "opp", "game_id", "salary",
)
B1_CANDIDATE_COLUMNS = (
    "panel_run_id", "season", "week", "cand_ix", "players", "tag",
    "selected", "selected_rank", "salary", "p_line", "sim_mean", "sim_sd",
    "sim_q50", "sim_q90", "sim_q99", "sim_rank_p_line",
)
B1_PLAYER_COLUMNS = (
    "season", "week", "id", "pos", "team", "opp", "game_id", "salary",
)


class PanelProducerError(RuntimeError):
    """The prospective B1 panel producer failed a pre-lock boundary."""


@dataclass(frozen=True)
class PanelSpec:
    panel_run_id: str
    role: str
    seed_index: int | None
    projection_seed: int | None
    role_seed: int | None

    @property
    def run_type(self) -> str:
        return (
            RUN_TYPE_CANONICAL if self.role == "canonical"
            else RUN_TYPE_COMPANION
        )


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _strict_json(raw: bytes, *, label: str) -> Any:
    def reject_constant(value: str) -> None:
        raise PanelProducerError(f"{label} contains non-finite JSON: {value}")

    def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PanelProducerError(f"{label} repeats JSON key {key}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicate,
        )
    except PanelProducerError:
        raise
    except Exception as exc:
        raise PanelProducerError(f"{label} is not strict JSON") from exc


def _utc(value: object, *, label: str) -> datetime:
    if isinstance(value, pd.Timestamp):
        parsed = value.to_pydatetime()
    elif isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise PanelProducerError(f"{label} is not ISO-8601") from exc
    else:
        raise PanelProducerError(f"{label} timestamp is absent")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PanelProducerError(f"{label} timestamp is not timezone-aware")
    return parsed.astimezone(timezone.utc)


def _load_deployment_authorization(
    path: Path,
    *,
    storage_client: storage.Client,
    code_sha: str,
    week: int,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Generation-pin the official create-only shadow deployment object."""
    if path.is_symlink() or not path.is_file():
        raise PanelProducerError("shadow deployment receipt is absent")
    raw = path.read_bytes()
    value = _strict_json(raw, label="shadow deployment receipt")
    if raw != _canonical_json(value) or not isinstance(value, dict):
        raise PanelProducerError("shadow deployment receipt is not canonical")
    if set(value) != {"version", "object"} or value.get("version") != (
        "b1-corpus-tail-shadow-deployment-receipt-v1"
    ):
        raise PanelProducerError("shadow deployment receipt schema differs")
    try:
        import run_b1_corpus_tail_shadow_transport as shadow_transport

        deployment_identity = shadow_transport._object_identity(
            value["object"],
            uri=shadow_transport.DEPLOYMENT_URI,
            create_only=True,
        )
        deployment, observed = shadow_transport._load_remote_deployment(
            storage_client,
            deployment_identity,
        )
    except Exception as exc:
        raise PanelProducerError(
            "official shadow deployment object does not validate"
        ) from exc
    if (
        deployment.get("status")
        != "deployed-default-off-awaiting-explicit-week-intent"
        or deployment.get("season") != SEASON
        or deployment.get("weeks") != list(WEEKS)
        or week not in deployment["weeks"]
        or deployment.get("production_licensed") is not False
        or deployment.get("default_environment", {}).get(
            "CORPUS_TAIL_SHADOW_ENABLED"
        ) != "0"
        or deployment.get("code", {}).get("commit_sha") != code_sha
        or deployment.get("historical_license", {}).get(
            "historical_gate_passed"
        ) is not True
        or deployment.get("historical_license", {}).get(
            "historical_lease_exact_generation_closed"
        ) is not True
        or _HEX64.fullmatch(str(
            deployment.get("historical_license", {}).get(
                "model_artifact_sha256", ""
            )
        )) is None
    ):
        raise PanelProducerError("shadow deployment authorization boundary differs")
    if (
        os.environ.get("CODE_SHA") != code_sha
        or os.environ.get("ANALYSIS_IMAGE")
        != deployment.get("code", {}).get("image")
    ):
        raise PanelProducerError("panel producer runtime image identity differs")
    # The loader proved the generation-pinned bytes match this identity.
    # Retain its create-only flag in every downstream producer receipt.
    if observed != {
        key: item for key, item in deployment_identity.items()
        if key != "create_only"
    }:
        raise PanelProducerError("observed deployment object identity differs")
    return deployment, deployment_identity, sha256(raw).hexdigest()


def panel_plan(*, season: int, week: int, snapshot_id: str) -> tuple[PanelSpec, ...]:
    """Return the deterministic canonical-plus-five source population."""
    if type(season) is not int or season != SEASON:
        raise PanelProducerError("panel producer is frozen to the 2026 shadow")
    if type(week) is not int or week not in WEEKS:
        raise PanelProducerError("panel producer is frozen to Weeks 1 through 6")
    if not isinstance(snapshot_id, str) or not snapshot_id.strip():
        raise PanelProducerError("panel producer snapshot ID is absent")
    snapshot_hash = sha256(snapshot_id.strip().encode("utf-8")).hexdigest()
    root = f"b1-tail-{season}w{week:02d}-{snapshot_hash}"
    companions = tuple(
        PanelSpec(
            panel_run_id=f"{root}-r{index}-v1",
            role="companion",
            seed_index=index,
            projection_seed=int(projection_seed),
            role_seed=int(role_seed),
        )
        for index, (projection_seed, role_seed) in enumerate(
            ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs
        )
    )
    canonical = PanelSpec(
        panel_run_id=f"{root}-canonical-cbwu-v1",
        role="canonical",
        seed_index=None,
        projection_seed=None,
        role_seed=None,
    )
    plan = (canonical, *companions)
    if len(plan) != 6 or len({row.panel_run_id for row in plan}) != len(plan):
        raise PanelProducerError("panel plan is not canonical plus five unique panels")
    return plan


def panel_environment(spec: PanelSpec, *, code_sha: str) -> dict[str, str]:
    """Return one complete adopted-law environment without process leakage."""
    if _HEX40.fullmatch(code_sha) is None:
        raise PanelProducerError("panel producer requires a full immutable CODE_SHA")
    seed_receipt = (
        "CBWU=" + ";".join(
            f"R{i}:{projection}:{role}"
            for i, (projection, role) in enumerate(
                ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs
            )
        )
        if spec.role == "canonical"
        else (
            f"REPLAY_PROJECTION_SEED={spec.projection_seed};"
            f"ROLE_BELIEF_SEED={spec.role_seed}"
        )
    )
    env = ADOPTED_CLASSIC_POLICY.engine_environment({
        "GCP_PROJECT": PROJECT,
        "CODE_SHA": code_sha,
        "PANEL_RUN_ID": spec.panel_run_id,
        "SEEDS": seed_receipt,
    })
    env["CAND_FEATURE_TABLE"] = PLAYER_TABLE
    if spec.role == "companion":
        env.update({
            "MULTISEED_PORTFOLIO": "",
            "MULTISEED_SEED_PAIRS": "",
            "MULTISEED_WORLDS_PER_BLOCK": "",
            "MULTISEED_CANDIDATE_ENTRY_BASIS": "",
            "REPLAY_PROJECTION_SEED": str(spec.projection_seed),
            "ROLE_BELIEF_SEED": str(spec.role_seed),
        })
    elif spec.role != "canonical":
        raise PanelProducerError("panel role differs")
    return env


def _persist_environment(spec: PanelSpec, *, code_sha: str) -> dict[str, str]:
    """Mirror the exact environment seen by the engine persistence seam."""
    env = panel_environment(spec, code_sha=code_sha)
    if spec.role == "canonical":
        projection_seed, role_seed = ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs[0]
        env.update({
            "REPLAY_PROJECTION_SEED": str(projection_seed),
            "ROLE_BELIEF_SEED": str(role_seed),
            "MULTISEED_SOURCE_LABEL": "R0",
        })
    return env


def _expected_candidate_provenance(
    spec: PanelSpec,
    *,
    code_sha: str,
) -> dict[str, Any]:
    """Reconstruct fields persisted by the existing engine, byte-exactly."""
    from nfl_dfs.backtest.engine import _lever_keys
    from nfl_dfs.models.components import (
        effective_ensemble_size,
        ensemble_member_specs,
    )
    from nfl_dfs.research.config_manifest import manifest_hash

    env = _persist_environment(spec, code_sha=code_sha)
    seeds = env.get("SEEDS", "")
    seeds = ";".join(item for item in (
        seeds,
        (
            f"REPLAY_PROJECTION_SEED={env['REPLAY_PROJECTION_SEED']}"
            if "REPLAY_PROJECTION_SEED" in env else ""
        ),
        f"CE_SEED={env.get('CE_SEED', '1701')}",
        f"ROLE_BELIEF_SEED={env.get('ROLE_BELIEF_SEED', '7331')}",
        f"GUMBEL_SEED={env.get('GUMBEL_SEED', '4700')}",
        (
            f"ENSEMBLE_WORLD_SEED={env.get('ENSEMBLE_WORLD_SEED', '8161')}"
            if env.get("ENSEMBLE_WORLD_MODE") else ""
        ),
    ) if item)
    ensemble_size = effective_ensemble_size(env)
    member_spec = json.dumps(
        ensemble_member_specs(env), separators=(",", ":"), sort_keys=True
    )
    seeds = ";".join(item for item in (
        seeds,
        f"MODEL_ENSEMBLE_SIZE={ensemble_size}",
        f"MODEL_MEMBER_SPEC={member_spec}",
    ) if item)
    return {
        "config_hash": manifest_hash(),
        "lever_env": ",".join(sorted(
            f"{key}={value}" for key, value in env.items()
            if key in _lever_keys
        )),
        "seeds": seeds,
        "n_worlds": (
            len(ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs)
            * ADOPTED_CLASSIC_POLICY.multiseed_worlds_per_block
            if spec.role == "canonical"
            else ADOPTED_CLASSIC_POLICY.multiseed_worlds_per_block
        ),
    }


def _query(
    client: bigquery.Client,
    sql: str,
    parameters: Sequence[bigquery.QueryParameter],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(query_parameters=list(parameters)),
    )
    frame = job.result().to_dataframe(create_bqstorage_client=False)
    return frame, {
        "job_id": str(job.job_id),
        "location": str(job.location or ""),
        "created": job.created.isoformat() if job.created else None,
        "started": job.started.isoformat() if job.started else None,
        "ended": job.ended.isoformat() if job.ended else None,
        "total_bytes_processed": int(job.total_bytes_processed or 0),
        "query_sha256": sha256(sql.encode("utf-8")).hexdigest(),
    }


def preflight_sql() -> str:
    sql = f"""
SELECT 'candidates' AS source, COUNT(*) AS row_count
FROM `{CANDIDATE_TABLE}`
WHERE panel_run_id IN UNNEST(@panels)
UNION ALL
SELECT 'players' AS source, COUNT(*) AS row_count
FROM `{PLAYER_TABLE}`
WHERE panel_run_id IN UNNEST(@panels)
ORDER BY source
"""
    if "actual" in sql.lower() or "winner" in sql.lower():
        raise AssertionError("preflight SQL crossed the outcome boundary")
    return sql


def schedule_sql() -> str:
    sql = f"""
SELECT season, week, gameday, game_type
FROM `{PROJECT}.nfl_raw.schedules`
WHERE season = @season AND week = @week AND game_type = 'REG'
ORDER BY gameday
"""
    if "actual" in sql.lower() or "winner" in sql.lower():
        raise AssertionError("schedule SQL crossed the outcome boundary")
    return sql


def candidate_sql() -> str:
    sql = f"""
SELECT {', '.join(CANDIDATE_COLUMNS)}
FROM `{CANDIDATE_TABLE}`
WHERE panel_run_id IN UNNEST(@panels)
ORDER BY panel_run_id, season, week, cand_ix
"""
    if "actual" in sql.lower() or "winner" in sql.lower():
        raise AssertionError("candidate verification SQL crossed the outcome boundary")
    return sql


def player_sql() -> str:
    sql = f"""
SELECT {', '.join(PLAYER_COLUMNS)}
FROM `{PLAYER_TABLE}`
WHERE panel_run_id IN UNNEST(@panels)
ORDER BY panel_run_id, season, week, id
"""
    if "actual" in sql.lower() or "winner" in sql.lower():
        raise AssertionError("player verification SQL crossed the outcome boundary")
    return sql


def _frame_sha(frame: pd.DataFrame, order: Sequence[str]) -> str:
    ordered = frame.sort_values(list(order), kind="stable").reset_index(drop=True)
    digest = sha256()
    digest.update(_canonical_json(list(ordered.columns)))
    for values in ordered.itertuples(index=False, name=None):
        row: list[Any] = []
        for value in values:
            if value is None or pd.isna(value):
                row.append(None)
            elif hasattr(value, "item"):
                row.append(value.item())
            elif hasattr(value, "isoformat"):
                row.append(value.isoformat())
            else:
                row.append(value)
        digest.update(_canonical_json(row))
    return digest.hexdigest()


def _exact_boolean(frame: pd.DataFrame, column: str) -> None:
    if column not in frame or frame[column].isna().any() or not pd.api.types.is_bool_dtype(
        frame[column].dtype
    ):
        raise PanelProducerError(f"{column} is not exact Boolean data")


def _validate_query_before_lock(meta: Mapping[str, Any], lock: datetime, *, label: str) -> datetime:
    created = _utc(meta.get("created"), label=f"{label} query creation")
    started = _utc(meta.get("started"), label=f"{label} query start")
    ended = _utc(meta.get("ended"), label=f"{label} query completion")
    if not created <= started <= ended or ended >= lock:
        raise PanelProducerError(f"{label} query completed at or after lock")
    if (
        not isinstance(meta.get("job_id"), str)
        or not meta["job_id"]
        or _HEX64.fullmatch(str(meta.get("query_sha256", ""))) is None
        or type(meta.get("total_bytes_processed")) is not int
        or int(meta["total_bytes_processed"]) < 0
    ):
        raise PanelProducerError(f"{label} query provenance differs")
    return ended


def _validate_schedule(
    frame: pd.DataFrame,
    *,
    season: int,
    week: int,
    lock_at: datetime,
) -> str:
    if set(frame) != {"season", "week", "gameday", "game_type"} or frame.empty:
        raise PanelProducerError("authoritative schedule proof schema differs")
    if not pd.to_numeric(frame.season, errors="raise").astype(int).eq(season).all():
        raise PanelProducerError("schedule proof contains another season")
    if not pd.to_numeric(frame.week, errors="raise").astype(int).eq(week).all():
        raise PanelProducerError("schedule proof contains another week")
    if not frame.game_type.astype(str).eq("REG").all():
        raise PanelProducerError("schedule proof is not regular season")
    dates = pd.to_datetime(frame.gameday, errors="raise").dt.date
    sundays = sorted({value for value in dates if value.weekday() == 6})
    lock_date = lock_at.astimezone(ZoneInfo("America/New_York")).date()
    if sundays != [lock_date]:
        raise PanelProducerError("season/week does not bind the contest-lock Sunday")
    return lock_date.isoformat()


def _validate_batch_metadata(
    values: pd.Series,
    *,
    spec: PanelSpec,
    season: int,
    week: int,
    candidate_rows: int,
) -> dict[str, Any]:
    if values.isna().any() or values.astype(str).nunique() != 1:
        raise PanelProducerError(
            f"candidate batch metadata differs within {spec.panel_run_id}"
        )
    raw = str(values.iloc[0])
    value = _strict_json(raw.encode("utf-8"), label="candidate batch metadata")
    if not isinstance(value, dict) or raw != json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ):
        raise PanelProducerError("candidate batch metadata is not canonical")
    if spec.role == "canonical":
        expected_keys = {
            "portfolio", "candidate_budget", "candidate_source_counts",
            "novel_candidates_by_seed", "world_blocks", "worlds_per_block",
        }
        labels = [
            f"R{index}"
            for index in range(len(ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs))
        ]
        counts = value.get("candidate_source_counts")
        novelty = value.get("novel_candidates_by_seed")
        if (
            set(value) != expected_keys
            or value.get("portfolio") != "CBWU"
            or type(value.get("candidate_budget")) is not int
            or value["candidate_budget"] != candidate_rows
            or type(value.get("world_blocks")) is not int
            or value["world_blocks"] != len(labels)
            or value.get("worlds_per_block")
            != [ADOPTED_CLASSIC_POLICY.multiseed_worlds_per_block] * len(labels)
            or not isinstance(counts, dict)
            or list(counts) != labels
            or any(type(counts[label]) is not int or counts[label] < 0 for label in labels)
            or sum(counts.values()) != candidate_rows
            or not isinstance(novelty, dict)
            or list(novelty) != labels
            or any(
                type(novelty[label]) is not int
                or novelty[label] < counts[label]
                for label in labels
            )
        ):
            raise PanelProducerError("canonical CBWU batch metadata differs")
    else:
        expected = {
            "season": season,
            "week": week,
            "tail_line": float(ADOPTED_CLASSIC_POLICY.tail_line),
            "n_entries": ENTRIES,
            "candidate_generation_entries": ENTRIES,
            "latent_optimization_receipt": [],
            "latent_scenario_receipt": {},
        }
        if value != expected:
            raise PanelProducerError("companion native batch metadata differs")
    return value


def validate_source_frames(
    candidates: pd.DataFrame,
    players: pd.DataFrame,
    *,
    plan: Sequence[PanelSpec],
    season: int,
    week: int,
    code_sha: str,
    lock_at: datetime,
) -> dict[str, Any]:
    """Validate the exact outcome-free staging population emitted upstream."""
    if candidates.empty or players.empty:
        raise PanelProducerError("panel producer returned an empty source")
    if set(candidates) != set(CANDIDATE_COLUMNS):
        raise PanelProducerError("candidate verification schema differs")
    if set(players) != set(PLAYER_COLUMNS):
        raise PanelProducerError("player verification schema differs")
    expected = {row.panel_run_id: row for row in plan}
    if set(candidates.panel_run_id.astype(str)) != set(expected):
        raise PanelProducerError("candidate panel set differs")
    if set(players.panel_run_id.astype(str)) != set(expected):
        raise PanelProducerError("player panel set differs")
    for frame, label in ((candidates, "candidate"), (players, "player")):
        _exact_boolean(frame, "research_eligible")
        if frame.research_eligible.any():
            raise PanelProducerError(f"{label} rows are unexpectedly research-eligible")
        if not frame.code_sha.astype(str).eq(code_sha).all():
            raise PanelProducerError(f"{label} rows do not bind the immutable code SHA")
        if frame.config_hash.isna().any() or frame.config_hash.astype(str).str.len().eq(0).any():
            raise PanelProducerError(f"{label} rows lack config identity")
        if not pd.to_numeric(frame.season, errors="raise").astype(int).eq(season).all():
            raise PanelProducerError(f"{label} rows contain another season")
        if not pd.to_numeric(frame.week, errors="raise").astype(int).eq(week).all():
            raise PanelProducerError(f"{label} rows contain another week")
        generated = frame.generated_at.map(
            lambda value: _utc(value, label=f"{label} generated_at")
        )
        if any(value >= lock_at for value in generated):
            raise PanelProducerError(f"{label} rows were generated at or after lock")
    for column in ("code_dirty", "labels_complete", "selected"):
        _exact_boolean(candidates, column)
    if candidates.code_dirty.any():
        raise PanelProducerError("candidate source was generated by a dirty checkout")
    if candidates.labels_complete.any():
        raise PanelProducerError("prospective candidate rows are outcome-labeled")
    if candidates.duplicated(["panel_run_id", "season", "week", "cand_ix"]).any():
        raise PanelProducerError("candidate rows repeat a panel key")
    if players.duplicated(["panel_run_id", "season", "week", "id"]).any():
        raise PanelProducerError("player rows repeat a panel key")
    structural_fields = (
        "id", "gsis_id", "pos", "team", "opp", "game_id", "salary"
    )
    if players.loc[:, structural_fields].isna().any().any():
        raise PanelProducerError("player catalog contains incomplete structure")
    player_salary = pd.to_numeric(players.salary, errors="raise").astype(float)
    if (player_salary <= 0).any() or (player_salary % 1.0 != 0.0).any():
        raise PanelProducerError("player catalog salary is not a positive integer")
    skill = players.pos.astype(str).str.upper().ne("DST")
    if (
        players.loc[skill, "gsis_id"].isna().any()
        or players.loc[skill, "gsis_id"].astype(str).str.strip().eq("").any()
        or players.loc[skill].duplicated(
            ["panel_run_id", "season", "week", "gsis_id"]
        ).any()
    ):
        raise PanelProducerError("skill-player DK-to-GSIS identity is incomplete")

    panel_rows: dict[str, Any] = {}
    structural_catalog: list[tuple[Any, ...]] | None = None
    for panel_id, spec in expected.items():
        cand = candidates[candidates.panel_run_id.astype(str).eq(panel_id)].copy()
        cat = players[players.panel_run_id.astype(str).eq(panel_id)].copy()
        provenance = _expected_candidate_provenance(spec, code_sha=code_sha)
        if cand.run_type.astype(str).nunique() != 1 or str(cand.run_type.iloc[0]) != spec.run_type:
            raise PanelProducerError(f"candidate run type differs for {panel_id}")
        if cand.slate_run_id.astype(str).nunique() != 1 or cat.slate_run_id.astype(str).nunique() != 1:
            raise PanelProducerError(f"panel {panel_id} does not have one slate run")
        if str(cand.slate_run_id.iloc[0]) != str(cat.slate_run_id.iloc[0]):
            raise PanelProducerError(f"candidate/catalog slate run differs for {panel_id}")
        if (
            not cand.config_hash.astype(str).eq(provenance["config_hash"]).all()
            or not cat.config_hash.astype(str).eq(provenance["config_hash"]).all()
            or not cand.lever_env.astype(str).eq(provenance["lever_env"]).all()
            or not cand.seeds.astype(str).eq(provenance["seeds"]).all()
        ):
            raise PanelProducerError(f"effective policy provenance differs for {panel_id}")
        expected_worlds = int(provenance["n_worlds"])
        if (
            not pd.to_numeric(cand.tail_line, errors="raise").astype(float).eq(
                float(ADOPTED_CLASSIC_POLICY.tail_line)
            ).all()
            or not pd.to_numeric(cand.n_entries, errors="raise").astype(int).eq(
                ENTRIES
            ).all()
            or not pd.to_numeric(cand.n_sims, errors="raise").astype(int).eq(
                expected_worlds
            ).all()
            or not pd.to_numeric(cand.n_worlds, errors="raise").astype(int).eq(
                expected_worlds
            ).all()
        ):
            raise PanelProducerError(f"selection/world contract differs for {panel_id}")
        indices = sorted(pd.to_numeric(cand.cand_ix, errors="raise").astype(int))
        if indices != list(range(len(cand))):
            raise PanelProducerError(f"candidate indices are noncanonical for {panel_id}")
        selected = cand[cand.selected].copy()
        ranks = sorted(pd.to_numeric(selected.selected_rank, errors="raise").astype(int))
        if len(selected) != ENTRIES or ranks != list(range(ENTRIES)):
            raise PanelProducerError(f"panel {panel_id} is not selected exact-80")
        if not pd.to_numeric(cand.loc[~cand.selected, "selected_rank"], errors="raise").astype(int).eq(-1).all():
            raise PanelProducerError(f"panel {panel_id} has invalid unselected ranks")
        structural = sorted(
            tuple(row)
            for row in cat.loc[:, structural_fields]
            .itertuples(index=False, name=None)
        )
        if structural_catalog is None:
            structural_catalog = structural
        elif structural != structural_catalog:
            raise PanelProducerError("companion player catalogs differ from canonical slate")
        batch_metadata = _validate_batch_metadata(
            cand.candidate_batch_metadata,
            spec=spec,
            season=season,
            week=week,
            candidate_rows=len(cand),
        )
        panel_rows[panel_id] = {
            "role": spec.role,
            "seed_index": spec.seed_index,
            "candidate_rows": len(cand),
            "selected_rows": len(selected),
            "player_rows": len(cat),
            "slate_run_id": str(cand.slate_run_id.iloc[0]),
            "config_hash": provenance["config_hash"],
            "lever_env_sha256": sha256(
                provenance["lever_env"].encode("utf-8")
            ).hexdigest(),
            "seeds_sha256": sha256(
                provenance["seeds"].encode("utf-8")
            ).hexdigest(),
            "n_worlds": expected_worlds,
            "candidate_batch_metadata": batch_metadata,
        }

    canonical = next(row.panel_run_id for row in plan if row.role == "canonical")
    b1_candidates = candidates.loc[:, B1_CANDIDATE_COLUMNS].copy()
    b1_players = players[players.panel_run_id.astype(str).eq(canonical)].loc[
        :, B1_PLAYER_COLUMNS
    ].copy()
    try:
        deduplicated = build_deduplicated_dataset(
            b1_candidates,
            b1_players,
            canonical_panel=canonical,
            include_outcomes=False,
        )
    except CorpusTailError as exc:
        raise PanelProducerError("emitted panels fail the frozen B1 source contract") from exc
    canonical_pool = deduplicated[deduplicated.canonical_candidate]
    control = canonical_pool[canonical_pool.canonical_selected]
    if len(canonical_pool) < ENTRIES or len(control) != ENTRIES:
        raise PanelProducerError("canonical B1 source cannot form its exact-80 control")
    return {
        "panel_rows": panel_rows,
        "candidate_rows": len(candidates),
        "player_rows": len(players),
        "deduplicated_rosters": len(deduplicated),
        "canonical_candidates": len(canonical_pool),
        "canonical_selected": len(control),
        "candidate_frame_sha256": _frame_sha(
            candidates, ("panel_run_id", "season", "week", "cand_ix")
        ),
        "player_frame_sha256": _frame_sha(
            players, ("panel_run_id", "season", "week", "id")
        ),
    }


def _gcs_parts(uri: str) -> tuple[str, str]:
    if not isinstance(uri, str) or not uri.startswith("gs://") or "/" not in uri[5:]:
        raise PanelProducerError("receipt URI is not a GCS object")
    bucket, name = uri[5:].split("/", 1)
    if not bucket or not name:
        raise PanelProducerError("receipt URI is not a GCS object")
    return bucket, name


def _attempt_uri(receipt_uri: str) -> str:
    if not receipt_uri.endswith("/source-receipt.json"):
        raise PanelProducerError("receipt URI must end in /source-receipt.json")
    return receipt_uri.rsplit("/", 1)[0] + "/source-attempt.json"


def canonical_receipt_uri(*, season: int, week: int, snapshot_id: str) -> str:
    plan = panel_plan(season=season, week=week, snapshot_id=snapshot_id)
    # Every panel carries the same full snapshot digest between the week and
    # role suffix.  Recompute it directly so a receipt path cannot become an
    # alternate retry namespace for identical panel keys.
    snapshot_hash = sha256(snapshot_id.strip().encode("utf-8")).hexdigest()
    if snapshot_hash not in plan[0].panel_run_id:
        raise AssertionError("panel and receipt snapshot identities diverged")
    return (
        f"{RECEIPT_ROOT}/{season}/week-{week:02d}/{snapshot_hash}/"
        "source-receipt.json"
    )


def _upload_create_once(
    client: storage.Client,
    *,
    uri: str,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    raw = _canonical_json(dict(value))
    bucket_name, name = _gcs_parts(uri)
    blob = client.bucket(bucket_name).blob(name)
    try:
        blob.upload_from_string(
            raw,
            content_type="application/json",
            if_generation_match=0,
        )
    except PreconditionFailed as exc:
        raise PanelProducerError(
            f"create-only producer object already exists: {uri}"
        ) from exc
    try:
        generation = int(blob.generation or 0)
    except (TypeError, ValueError) as exc:
        raise PanelProducerError(
            "create-only upload did not return its generation"
        ) from exc
    if generation <= 0:
        raise PanelProducerError(
            "create-only upload did not return its generation"
        )
    # Read the exact generation created above.  A current-object reload after
    # upload could observe a later overwrite while retaining the intended
    # byte count/hash in this receipt.
    pinned = client.bucket(bucket_name).blob(name, generation=generation)
    pinned.reload()
    observed_raw = pinned.download_as_bytes(if_generation_match=generation)
    if observed_raw != raw:
        raise PanelProducerError("create-only producer object bytes differ")
    identity = {
        "uri": uri,
        "generation": str(pinned.generation or ""),
        "metageneration": str(pinned.metageneration or ""),
        "bytes": int(pinned.size or 0),
        "sha256": sha256(observed_raw).hexdigest(),
        "created_at": (
            _utc(pinned.time_created, label="create-only object time").isoformat()
            if pinned.time_created else None
        ),
        "create_only": True,
    }
    if (
        identity["generation"] != str(generation)
        or identity["metageneration"] != "1"
        or identity["bytes"] != len(raw)
        or identity["created_at"] is None
    ):
        raise PanelProducerError("create-only producer object identity differs")
    return identity


def _salary_inputs(store: Any, draft_group_id: int) -> tuple[set[int], dict[int, int]]:
    salaries = store.classic_salaries(int(draft_group_id))
    if salaries.empty:
        raise PanelProducerError("Sunday-main salary snapshot is empty")
    required = {"dk_player_id", "dk_draftable_id", "salary"}
    if not required <= set(salaries):
        raise PanelProducerError("salary snapshot schema is incomplete")
    if salaries.loc[:, sorted(required)].isna().any().any():
        raise PanelProducerError("salary snapshot contains incomplete identity")
    exact: dict[str, pd.Series] = {}
    for column in sorted(required):
        if pd.api.types.is_bool_dtype(salaries[column].dtype):
            raise PanelProducerError(
                f"salary snapshot {column} is not a positive exact integer"
            )
        numeric = pd.to_numeric(salaries[column], errors="raise")
        as_float = numeric.astype(float)
        if (
            not as_float.map(math.isfinite).all()
            or as_float.le(0).any()
            or as_float.mod(1.0).ne(0.0).any()
        ):
            raise PanelProducerError(
                f"salary snapshot {column} is not a positive exact integer"
            )
        exact[column] = numeric.astype("int64")
    for column in ("dk_player_id", "dk_draftable_id"):
        if exact[column].duplicated().any():
            raise PanelProducerError(f"salary snapshot repeats {column}")
    allowed = set(exact["dk_player_id"].tolist())
    overrides = {
        int(player_id): int(salary)
        for player_id, salary in zip(
            exact["dk_player_id"], exact["salary"], strict=True
        )
    }
    if len(allowed) != len(salaries):
        raise PanelProducerError("salary snapshot player/salary identity differs")
    return allowed, overrides


def _validate_draft_group(store: Any, *, draft_group_id: int, lock_at: datetime) -> None:
    """Bind the caller's group and lock to the largest Sunday-main slate."""
    from nfl_dfs.inference.tail_shadow import sunday_main_group

    slates = store.classic_slates()
    required = {"draft_group_id", "game_start", "teams", "players"}
    if slates.empty or not required <= set(slates):
        raise PanelProducerError("classic slate inventory is absent or incomplete")
    eastern_date = lock_at.astimezone(ZoneInfo("America/New_York")).date()
    try:
        expected = sunday_main_group(slates, eastern_date)
    except Exception as exc:
        raise PanelProducerError("Sunday-main draft group cannot be proven") from exc
    if int(draft_group_id) != int(expected):
        raise PanelProducerError("draft group is not the target Sunday-main slate")
    chosen = slates[pd.to_numeric(slates.draft_group_id, errors="raise").astype(int).eq(
        int(draft_group_id)
    )]
    starts = pd.to_datetime(chosen.game_start, utc=True, errors="raise")
    if starts.empty or starts.min().to_pydatetime() != lock_at:
        raise PanelProducerError("contest lock does not equal Sunday-main first kickoff")


def _default_builder(
    spec: PanelSpec,
    *,
    season: int,
    week: int,
    allowed_ids: set[int],
    salary_overrides: Mapping[int, int],
    code_sha: str,
) -> int:
    from nfl_dfs.inference.live_lineups import build_sim_lineups
    from nfl_dfs.optimizer.lineup import StackRules

    env = panel_environment(spec, code_sha=code_sha)
    seed = 42 if spec.projection_seed is None else int(spec.projection_seed)
    lineups = build_sim_lineups(
        season,
        week,
        n_entries=ENTRIES,
        stack=StackRules(qb_stack_min=2, bring_back_min=1, forbid_rb_vs_dst=True),
        tail_line=ADOPTED_CLASSIC_POLICY.tail_line,
        n_sims=ADOPTED_CLASSIC_POLICY.multiseed_worlds_per_block,
        seed=seed,
        lev_scale=1.0,
        allowed_ids=allowed_ids,
        salary_overrides=dict(salary_overrides),
        apply_notes=False,
        model_variant=ADOPTED_CLASSIC_POLICY.model_variant,
        cand_log_table=CANDIDATE_TABLE,
        cand_log_async=False,
        cand_log_required=True,
        panel_run_id=spec.panel_run_id,
        candidate_run_type=spec.run_type,
        policy_env=env,
        expected_model_k=ADOPTED_CLASSIC_POLICY.model_ensemble,
        belief_model_variant=ADOPTED_CLASSIC_POLICY.role_model_variant,
        _log_ownership_shadow=False,
    )
    return len(lineups)


def produce(
    *,
    season: int,
    week: int,
    draft_group_id: int,
    snapshot_id: str,
    lock_at: str,
    receipt_uri: str,
    deployment_receipt: Path,
    code_sha: str,
    bq_client: bigquery.Client,
    storage_client: storage.Client,
    store: Any,
    builder: Callable[..., int] = _default_builder,
    query: Callable[[bigquery.Client, str, Sequence[bigquery.QueryParameter]], tuple[pd.DataFrame, dict[str, Any]]] = _query,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    """Execute one create-once, outcome-blind prospective source build."""
    if os.environ.get(ENABLED_ENV, "0") != "1":
        raise PanelProducerError(f"{ENABLED_ENV}=1 is required explicitly")
    if _HEX40.fullmatch(code_sha) is None:
        raise PanelProducerError("panel producer requires a full immutable CODE_SHA")
    if builder is _default_builder and (ROOT / ".git").exists():
        raise PanelProducerError(
            "default producer must run in the immutable image without .git"
        )
    lock = _utc(lock_at, label="contest lock")
    if _utc(now(), label="producer start") >= lock:
        raise PanelProducerError("panel producer started at or after lock")
    plan = panel_plan(season=season, week=week, snapshot_id=snapshot_id)
    expected_receipt_uri = canonical_receipt_uri(
        season=season,
        week=week,
        snapshot_id=snapshot_id,
    )
    if receipt_uri != expected_receipt_uri:
        raise PanelProducerError("receipt URI is not canonical for these panel keys")
    deployment, deployment_object, deployment_receipt_sha = (
        _load_deployment_authorization(
            deployment_receipt,
            storage_client=storage_client,
            code_sha=code_sha,
            week=week,
        )
    )
    schedule, schedule_meta = query(
        bq_client,
        schedule_sql(),
        [
            bigquery.ScalarQueryParameter("season", "INT64", season),
            bigquery.ScalarQueryParameter("week", "INT64", week),
        ],
    )
    _validate_query_before_lock(schedule_meta, lock, label="schedule proof")
    schedule_sunday = _validate_schedule(
        schedule,
        season=season,
        week=week,
        lock_at=lock,
    )
    panel_ids = [row.panel_run_id for row in plan]
    params = [bigquery.ArrayQueryParameter("panels", "STRING", panel_ids)]
    before, preflight_meta = query(bq_client, preflight_sql(), params)
    if set(before) != {"source", "row_count"} or set(before.source.astype(str)) != {
        "candidates", "players"
    }:
        raise PanelProducerError("panel preflight schema differs")
    if pd.to_numeric(before.row_count, errors="raise").astype(int).ne(0).any():
        raise PanelProducerError("one or more prospective panel IDs already exist")
    _validate_query_before_lock(preflight_meta, lock, label="preflight")

    _validate_draft_group(
        store,
        draft_group_id=draft_group_id,
        lock_at=lock,
    )
    allowed_ids, salary_overrides = _salary_inputs(store, draft_group_id)
    attempt_started = _utc(now(), label="attempt creation")
    if attempt_started >= lock:
        raise PanelProducerError("panel producer reached lock before its attempt")
    model_sha = deployment["historical_license"]["model_artifact_sha256"]
    attempt = {
        "version": ATTEMPT_VERSION,
        "season": season,
        "week": week,
        "draft_group_id": int(draft_group_id),
        "snapshot_id": snapshot_id,
        "lock_at": lock.isoformat(),
        "code_sha": code_sha,
        "policy_id": ADOPTED_CLASSIC_POLICY.policy_id,
        "canonical_panel": plan[0].panel_run_id,
        "companion_panels": [row.panel_run_id for row in plan[1:]],
        "deployment_object": deployment_object,
        "deployment_receipt_sha256": deployment_receipt_sha,
        "model_artifact_sha256": model_sha,
        "schedule_sunday": schedule_sunday,
        "schedule_query": schedule_meta,
        "started_at": attempt_started.isoformat(),
        "outcome_columns_allowed": [],
        "retry_same_snapshot_licensed": False,
        "production_licensed": False,
    }
    attempt_object = _upload_create_once(
        storage_client,
        uri=_attempt_uri(receipt_uri),
        value=attempt,
    )
    if _utc(attempt_object.get("created_at"), label="attempt object creation") >= lock:
        raise PanelProducerError("create-only attempt object was created at or after lock")

    # Companion rows are generated first.  The canonical/current-selector
    # panel is written only after every named companion completed.
    build_order = [*plan[1:], plan[0]]
    build_receipts = []
    for spec in build_order:
        if _utc(now(), label=f"{spec.panel_run_id} start") >= lock:
            raise PanelProducerError("panel generation reached the contest lock")
        count = builder(
            spec,
            season=season,
            week=week,
            allowed_ids=allowed_ids,
            salary_overrides=salary_overrides,
            code_sha=code_sha,
        )
        if type(count) is not int or count != ENTRIES:
            raise PanelProducerError(
                f"panel {spec.panel_run_id} did not return exact-80"
            )
        build_receipts.append({
            "panel_run_id": spec.panel_run_id,
            "role": spec.role,
            "seed_index": spec.seed_index,
            "entries_returned": count,
        })

    candidates, candidate_meta = query(bq_client, candidate_sql(), params)
    players, player_meta = query(bq_client, player_sql(), params)
    candidate_end = _validate_query_before_lock(
        candidate_meta, lock, label="candidate verification"
    )
    player_end = _validate_query_before_lock(
        player_meta, lock, label="player verification"
    )
    validation = validate_source_frames(
        candidates,
        players,
        plan=plan,
        season=season,
        week=week,
        code_sha=code_sha,
        lock_at=lock,
    )
    receipt = {
        "version": RECEIPT_VERSION,
        "status": "outcome-blind-prelock-panels-complete",
        "season": season,
        "week": week,
        "draft_group_id": int(draft_group_id),
        "snapshot_id": snapshot_id,
        "snapshot_at": max(candidate_end, player_end).isoformat(),
        "lock_at": lock.isoformat(),
        "code_sha": code_sha,
        "policy_id": ADOPTED_CLASSIC_POLICY.policy_id,
        "canonical_panel": plan[0].panel_run_id,
        "companion_panels": [row.panel_run_id for row in plan[1:]],
        "panels": sorted(panel_ids),
        "build_order": build_receipts,
        "candidate_table": CANDIDATE_TABLE,
        "player_table": PLAYER_TABLE,
        "deployment_object": deployment_object,
        "deployment_receipt_sha256": deployment_receipt_sha,
        "model_artifact_sha256": model_sha,
        "attempt_object": attempt_object,
        "schedule_sunday": schedule_sunday,
        "source_queries": {
            "schedule": schedule_meta,
            "preflight": preflight_meta,
            "candidates": candidate_meta,
            "players": player_meta,
        },
        "validation": validation,
        "realized_outcome_columns_read": [],
        "winner_fields_read": [],
        "labels_complete": False,
        "b1_shadow_input_only": True,
        "production_licensed": False,
    }
    receipt_object = _upload_create_once(
        storage_client,
        uri=receipt_uri,
        value=receipt,
    )
    if _utc(receipt_object.get("created_at"), label="source receipt creation") >= lock:
        raise PanelProducerError("source receipt object was created at or after lock")
    return {
        "receipt": receipt,
        "receipt_object": receipt_object,
    }


def _args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=SEASON)
    parser.add_argument("--week", type=int, required=True, choices=WEEKS)
    parser.add_argument("--draft-group-id", type=int, required=True)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--lock-at", required=True)
    parser.add_argument("--receipt-uri", required=True)
    parser.add_argument("--deployment-receipt", type=Path, required=True)
    parser.add_argument("--code-sha", default=os.environ.get("CODE_SHA", ""))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _args(argv)
    from nfl_dfs.app.store import BigQueryStore

    result = produce(
        season=args.season,
        week=args.week,
        draft_group_id=args.draft_group_id,
        snapshot_id=args.snapshot_id,
        lock_at=args.lock_at,
        receipt_uri=args.receipt_uri,
        deployment_receipt=args.deployment_receipt,
        code_sha=args.code_sha,
        bq_client=bigquery.Client(project=PROJECT),
        storage_client=storage.Client(project=PROJECT),
        store=BigQueryStore(),
    )
    print(json.dumps({
        "status": result["receipt"]["status"],
        "canonical_panel": result["receipt"]["canonical_panel"],
        "companion_panels": result["receipt"]["companion_panels"],
        "receipt_object": result["receipt_object"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
