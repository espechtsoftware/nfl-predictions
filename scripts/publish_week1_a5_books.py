#!/usr/bin/env python3
"""Build and create-once publish the current Week-1 P_MIX/A5 books.

This is a pre-lock, outcome-blind book publisher.  It exact-reopens every raw
source it writes, publishes the adopted D800/D400 pair and participation
package through their governed operators, then publishes the salary catalog,
player bridge, and four exact-K80 A5 books.  It deliberately does not publish
an entry allocation or submit any contest entry.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from google.cloud import bigquery

from nfl_dfs.ingest import week1_a5_capture_contracts as capture
from nfl_dfs.inference import prospective_generation_shadow_evaluation as shadow
from nfl_dfs.inference import prospective_generation_shadow_operator as storage
from nfl_dfs.inference import week1_a5_book_materializer as materializer
from nfl_dfs.inference import week1_adopted_pair as adopted
from nfl_dfs.inference import week1_adopted_pair_operator as pair_operator
from nfl_dfs.inference import week1_live_pair_adapter as live_adapter
from nfl_dfs.inference import week1_participation_mixture as pmix
from nfl_dfs.inference import week1_participation_mixture_operator as pmix_operator
from nfl_dfs.inference.generation_exposure import canonical_sha256

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLISH_ROOT = (
    "gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/"
    "a5-books"
)
GENERATION_SAFETY_IDENTITY = {
    "uri": (
        "gs://nfl-predictions-503414-raw/generation_shadow/2026/week-01/"
        "safety/weekly-safety-receipt.json"
    ),
    "generation": "1789079337043256",
    "sha256": "102bb31af7e98532c1c5bc929e837fa0a1458d7c890400ddd80bb96b9e837c3c",
    "bytes": 6183059,
}
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_RUN_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,79}\Z")

# Seasons 2022--2024 use the production point-in-time training rows.  The
# 2025 raw injury release lacks source modification timestamps, so its one-row
# per player/week records are joined to the same Sunday-main salary universe
# and the production active-stat/snap definition after the season is complete.
HISTORY_SQL = r"""
WITH main_teams AS (
  SELECT CAST(season AS INT64) AS season,
         CAST(week AS INT64) AS week,
         team
  FROM `{project}.nfl_raw.schedules`, UNNEST([away_team, home_team]) AS team
  WHERE game_type = 'REG'
    AND weekday = 'Sunday'
    AND SAFE.PARSE_TIME('%H:%M', gametime) >= TIME '13:00:00'
    AND SAFE.PARSE_TIME('%H:%M', gametime) < TIME '19:00:00'
), snaps AS (
  SELECT ids.gsis_id,
         CAST(s.season AS INT64) AS season,
         CAST(s.week AS INT64) AS week,
         s.offense_pct
  FROM `{project}.nfl_raw.snap_counts` AS s
  JOIN `{project}.nfl_raw.player_ids` AS ids
    ON ids.pfr_id = s.pfr_player_id
  WHERE ids.gsis_id IS NOT NULL
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY ids.gsis_id, CAST(s.season AS INT64), CAST(s.week AS INT64)
    ORDER BY s.offense_pct DESC
  ) = 1
), historical_pit AS (
  SELECT t.season, t.week, t.gsis_id, t.injury_status,
         CAST(t.practice_level AS INT64) AS practice_level,
         t.was_active,
         'point-in-time-player-week-training' AS source_kind
  FROM `{project}.nfl_features.player_week_training` AS t
  JOIN main_teams AS m
    ON m.season = t.season AND m.week = t.week AND m.team = t.team
  WHERE t.season BETWEEN 2022 AND 2024
    AND t.position IN ('QB', 'RB', 'WR', 'TE')
    AND t.injury_status IN ('Questionable', 'Doubtful')
    AND t.was_active IS NOT NULL
), season_2025 AS (
  SELECT CAST(i.season AS INT64) AS season,
         CAST(i.week AS INT64) AS week,
         i.gsis_id,
         i.report_status AS injury_status,
         CASE i.practice_status
           WHEN 'Did Not Participate In Practice' THEN 0
           WHEN 'Limited Participation in Practice' THEN 1
           WHEN 'Full Participation in Practice' THEN 2
           ELSE NULL
         END AS practice_level,
         COALESCE(a.has_stat_line, FALSE) OR sn.offense_pct IS NOT NULL
           AS was_active,
         'completed-2025-raw-injury-plus-active-stat-snap' AS source_kind
  FROM `{project}.nfl_raw.injuries` AS i
  JOIN `{project}.nfl_features.dk_salary_week` AS sal
    ON sal.gsis_id = i.gsis_id
   AND sal.season = CAST(i.season AS INT64)
   AND sal.week = CAST(i.week AS INT64)
  JOIN main_teams AS m
    ON m.season = sal.season AND m.week = sal.week AND m.team = sal.team
  LEFT JOIN `{project}.nfl_features.player_week_actuals` AS a
    ON a.gsis_id = i.gsis_id
   AND a.season = CAST(i.season AS INT64)
   AND a.week = CAST(i.week AS INT64)
  LEFT JOIN snaps AS sn
    ON sn.gsis_id = i.gsis_id
   AND sn.season = CAST(i.season AS INT64)
   AND sn.week = CAST(i.week AS INT64)
  WHERE CAST(i.season AS INT64) = 2025
    AND i.report_status IN ('Questionable', 'Doubtful')
    AND sal.position IN ('QB', 'RB', 'WR', 'TE')
)
SELECT * FROM historical_pit
UNION ALL
SELECT * FROM season_2025
ORDER BY season, week, gsis_id, injury_status, practice_level, source_kind
""".strip()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _identity(label: str, sha256: str | None = None) -> dict[str, object]:
    return {
        "id": label,
        "sha256": sha256 or canonical_sha256({"identity": label}),
    }


def _semantic_ref(publication: dict[str, object]) -> dict[str, object]:
    return {
        "artifact_identity": publication["artifact_identity"],
        "semantic_sha256": publication["semantic_sha256"],
    }


def _dummy_ref(label: str, semantic_sha256: str) -> dict[str, object]:
    return {
        "artifact_identity": {
            "uri": f"{PUBLISH_ROOT}/dry-run/{label}.json",
            "generation": "1",
            "sha256": canonical_sha256({"dry_run": label}),
            "bytes": 1,
        },
        "semantic_sha256": semantic_sha256,
    }


def _canonical_rows(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if not rows or tuple(rows[0]) != tuple(pair_operator.DK_SLOT_ORDER):
        raise RuntimeError(f"{path} has a noncanonical DraftKings header")
    return rows[1:]


def _query_history(project: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    if re.fullmatch(r"[a-z][a-z0-9-]{4,62}", project) is None:
        raise RuntimeError("BigQuery project ID is noncanonical")
    query = HISTORY_SQL.format(project=project)
    job_config = bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000)
    job = bigquery.Client(project=project).query(query, job_config=job_config)
    result = list(job.result())
    rows = [
        {
            "season": int(row.season),
            "week": int(row.week),
            "gsis_id": str(row.gsis_id),
            "injury_status": str(row.injury_status),
            "practice_level": (
                None if row.practice_level is None else int(row.practice_level)
            ),
            "was_active": bool(row.was_active),
            "source_kind": str(row.source_kind),
        }
        for row in result
    ]
    keys = [(row["season"], row["week"], row["gsis_id"]) for row in rows]
    if len(rows) != len(set(keys)) or {row["season"] for row in rows} != {
        2022, 2023, 2024, 2025
    }:
        raise RuntimeError("participation history is duplicated or incomplete")
    artifact = {
        "schema_version": "week1-participation-history-source/v1",
        "project": project,
        "query": query,
        "query_sha256": canonical_sha256(query),
        "row_count": len(rows),
        "rows_sha256": canonical_sha256(rows),
        "rows": rows,
        "uses_target_week_outcomes": False,
    }
    return rows, artifact


def _history_projection(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "season": row["season"],
            "injury_status": row["injury_status"],
            "practice_level": row["practice_level"],
            "was_active": row["was_active"],
        }
        for row in rows
    ]


def _status_value(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    retained = str(value).strip().upper()
    if retained in {"", "NONE", "NAN", "<NA>"}:
        return None
    if retained not in {"Q", "D", "O", "OUT"}:
        raise RuntimeError(f"unsupported live DraftKings status {retained!r}")
    return retained


def _snapshot_source(frame: pd.DataFrame) -> tuple[list[str], list[dict[str, object]], dict[str, object], str]:
    pulled = pd.to_datetime(frame["pulled_at"], utc=True, errors="coerce")
    if pulled.isna().any() or pulled.nunique() != 1:
        raise RuntimeError("live frame does not bind one DraftKings pull")
    observed_at = pulled.iloc[0].to_pydatetime().isoformat()
    player_ids = frame["id"].astype(str).tolist()
    observations = [
        {
            "player_id": player_id,
            "injury_status": _status_value(status),
            "practice_level": None,
            "source_modified_at": None,
        }
        for player_id, status in zip(player_ids, frame["status"], strict=True)
    ]
    source = {
        "schema_version": "week1-draftkings-status-snapshot-source/v1",
        "season": 2026,
        "week": 1,
        "draft_group_id": "151307",
        "provider": "DraftKings salary status",
        "provider_observed_at": observed_at,
        "provider_absence_semantics": pmix.PROVIDER_ABSENCE_SEMANTICS,
        "complete_candidate_player_universe": True,
        "rows": observations,
        "uses_realized_outcomes": False,
    }
    return player_ids, observations, source, observed_at


def _raw_identity(raw: bytes, label: str) -> dict[str, object]:
    return {
        "uri": f"{PUBLISH_ROOT}/dry-run/{label}",
        "generation": "1",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _build_selection(
    *,
    paid_dir: Path,
    frame: pd.DataFrame,
    candidates: pd.DataFrame,
    history_rows: list[dict[str, object]],
    history_identity: dict[str, object],
    snapshot_identity: dict[str, object],
    snapshot_created_at: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    player_ids, observations, _source, provider_observed_at = _snapshot_source(frame)
    snapshot = pmix.build_prelock_snapshot_v1(
        player_ids=player_ids,
        observations=observations,
        provider="DraftKings salary status",
        provider_absence_semantics=pmix.PROVIDER_ABSENCE_SEMANTICS,
        provider_observed_at=provider_observed_at,
        ingested_at=snapshot_created_at,
        cutoff_at=snapshot_created_at,
        max_snapshot_age_seconds=7 * 24 * 60 * 60,
        raw_artifact=snapshot_identity,
    )
    participation_map = pmix.fit_participation_map_v1(
        _history_projection(history_rows),
        source_artifact_sha256=str(history_identity["sha256"]),
    )
    rosters = [str(value).split(",") for value in candidates["players"].tolist()]
    lineup_ids = [f"lineup-v1-{canonical_sha256(roster)}" for roster in rosters]
    selection_inputs: dict[str, Any] = {
        "player_ids": player_ids,
        "lineup_ids": lineup_ids,
        "rosters": rosters,
        "incumbent_player_scores": np.load(
            paid_dir / "incumbent_player_scores.npy", allow_pickle=False
        ),
        "corrected_hsim_player_scores": np.load(
            paid_dir / "corrected_hsim_player_scores.npy", allow_pickle=False
        ),
        "snapshot": snapshot,
        "participation_map": participation_map,
        "mixture_seed": 2157,
    }
    selection = pmix.build_participation_selection_v1(**selection_inputs)
    pmix.certify_participation_replay_v1(**selection_inputs)
    return selection_inputs, selection, participation_map


def _lineups_and_books(
    *,
    paid_dir: Path,
    shadow_dir: Path,
    selection: dict[str, object],
    bridge: dict[str, object],
    bridge_ref: dict[str, object],
) -> tuple[dict[str, list[dict[str, object]]], dict[str, dict[str, object]]]:
    paid_frame = pd.read_parquet(paid_dir / "frame.parquet")
    paid_candidates = pd.read_parquet(paid_dir / "candidates.parquet")
    shadow_frame = pd.read_parquet(shadow_dir / "frame.parquet")
    shadow_candidates = pd.read_parquet(shadow_dir / "candidates.parquet")
    lineups = {
        "P_CTRL": materializer.lineups_from_ordered_candidate_ids_v1(
            frame=paid_frame,
            candidates=paid_candidates,
            ordered_lineup_ids=selection["P_CTRL"]["ordered_lineup_ids"],
        ),
        "P_MIX": materializer.lineups_from_ordered_candidate_ids_v1(
            frame=paid_frame,
            candidates=paid_candidates,
            ordered_lineup_ids=selection["P_MIX"]["ordered_lineup_ids"],
        ),
        "D400_DEMAX": materializer.lineups_from_ranked_csv_v1(
            frame=shadow_frame,
            candidates=shadow_candidates,
            csv_rows=_canonical_rows(shadow_dir / "book.csv"),
            rank_column="book_rank",
        ),
        "D800_WEMAX": materializer.lineups_from_ranked_csv_v1(
            frame=paid_frame,
            candidates=paid_candidates,
            csv_rows=_canonical_rows(paid_dir / "book_wemax.csv"),
            rank_column="book_rank_wemax",
        ),
    }
    books = {
        policy: materializer.build_week1_book_materialization_v2(
            policy=policy,
            lineups=policy_lineups,
            bridge=bridge,
            player_bridge_ref=bridge_ref,
        )
        for policy, policy_lineups in lineups.items()
    }
    return lineups, books


def _publish_raw(
    store: storage.GCSImmutableObjectStore,
    *,
    uri: str,
    raw: bytes,
    content_type: str,
) -> dict[str, object]:
    receipt = dict(
        store.publish_create_once(uri=uri, raw=raw, content_type=content_type)
    )
    reopened = dict(store.read_exact(identity=receipt["identity"]))
    if reopened["raw"] != raw or reopened["identity"] != receipt["identity"]:
        raise RuntimeError(f"exact reopen differs for {uri}")
    created = datetime.fromisoformat(str(reopened["created_at"]))
    if created >= datetime.fromisoformat(adopted.WEEK1_LOCK_UTC):
        raise RuntimeError(f"{uri} was not published before lock")
    return {"identity": receipt["identity"], "created_at": reopened["created_at"]}


def _arm_metadata(
    *,
    arm_id: str,
    purpose: str,
    lev: int,
    boom: int,
    candidate_ids: list[str],
    sources: dict[str, dict[str, object]],
    adapter: dict[str, object],
    nfl2_root: Path,
    source_commit: str,
) -> dict[str, object]:
    common = {
        "slate_identity": _identity(
            "2026-w01-dk-151307",
            canonical_sha256({"season": 2026, "week": 1, "draft_group": 151307}),
        ),
        "input_identity": _identity(
            "live-input-root/v1", str(adapter["input_identity_sha256"])
        ),
        "player_bridge_identity": adapter["player_bridge_identity"],
        "generation_bank_identity": _identity("incumbent-generation-seed-2026"),
        "selection_bank_identity": _identity("incumbent-selection-seed-2076"),
        "audit_bank_identity": _identity("incumbent-audit-seed-2126"),
        "hsim_bank_identity": _identity("corrected-hsim-selection-seed-2326"),
        "construction_identity": _identity("house_qb2_bb1_floor49_v1"),
        "generator_source_identity": _identity(
            f"nfl2-live-week@{source_commit}",
            _file_sha256(nfl2_root / "scripts/live_week.py"),
        ),
        "selector_source_identity": _identity(
            f"nfl2-select-expected-max@{source_commit}",
            _file_sha256(nfl2_root / "src/nfl2/jpar/safe.py"),
        ),
        "hsim_source_identity": _identity(
            f"nfl2-corrected-hsim@{source_commit}",
            _file_sha256(nfl2_root / "src/nfl2/hsim/world.py"),
        ),
    }
    return {
        "arm_id": arm_id,
        "purpose": purpose,
        "config": {
            "lev": lev,
            "boom": boom,
            "selector": "dual_emax",
            "entries": 80,
            "k": 1,
        },
        **common,
        "candidate_artifact": sources["candidates"]["identity"],
        "exposure_ledger_artifact": sources["exposure_ledger"]["identity"],
        "run_receipt_artifact": sources["receipt"]["identity"],
        "candidate_ids": candidate_ids,
    }


def _check_source(code_sha: str) -> None:
    if _COMMIT.fullmatch(code_sha) is None:
        raise RuntimeError("--code-sha must be one full lowercase Git commit")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT,
        check=True, capture_output=True, text=True,
    ).stdout
    if head != code_sha or dirty:
        raise RuntimeError("publisher must execute from the exact clean --code-sha")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paid-run-dir", type=Path, required=True)
    parser.add_argument("--shadow-run-dir", type=Path, required=True)
    parser.add_argument("--nfl2-source-root", type=Path, required=True)
    parser.add_argument("--bigquery-project", default="nfl-predictions-503414")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--code-sha")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if _RUN_ID.fullmatch(args.run_id) is None:
        raise RuntimeError("--run-id is noncanonical")

    paid_dir = args.paid_run_dir.resolve(strict=True)
    shadow_dir = args.shadow_run_dir.resolve(strict=True)
    nfl2_root = args.nfl2_source_root.resolve(strict=True)
    paid_frame = pd.read_parquet(paid_dir / "frame.parquet")
    paid_candidates = pd.read_parquet(paid_dir / "candidates.parquet")
    adapter = live_adapter.adapt_week1_live_pair_directories_v1(
        paid_run_dir=paid_dir, shadow_run_dir=shadow_dir
    )
    history_rows, history_source = _query_history(args.bigquery_project)
    _player_ids, _observations, snapshot_source, _provider_at = _snapshot_source(
        paid_frame
    )
    history_raw = shadow.canonical_json_bytes_v1(history_source)
    snapshot_raw = shadow.canonical_json_bytes_v1(snapshot_source)
    dry_created = _now()
    selection_inputs, selection, participation_map = _build_selection(
        paid_dir=paid_dir,
        frame=paid_frame,
        candidates=paid_candidates,
        history_rows=history_rows,
        history_identity=_raw_identity(history_raw, "participation-history.json"),
        snapshot_identity=_raw_identity(snapshot_raw, "dk-status-snapshot.json"),
        snapshot_created_at=dry_created,
    )
    if selection["P_CTRL"]["ordered_lineup_ids"] != adapter["paid_book"][
        "roster_ids"
    ]:
        raise RuntimeError("recomputed P_CTRL differs from the repaired D800 book")

    catalog = materializer.build_week1_paid_salary_catalog_v1(paid_frame)
    catalog_ref = _dummy_ref("salary-catalog", str(catalog["semantic_sha256"]))
    bridge = materializer.build_week1_player_bridge_v1(
        paid_frame, salary_catalog=catalog, salary_catalog_ref=catalog_ref
    )
    bridge_ref = _dummy_ref("player-bridge", str(bridge["semantic_sha256"]))
    lineups, books = _lineups_and_books(
        paid_dir=paid_dir,
        shadow_dir=shadow_dir,
        selection=selection,
        bridge=bridge,
        bridge_ref=bridge_ref,
    )
    summary: dict[str, object] = {
        "schema_version": "week1-a5-four-book-preflight/v1",
        "run_id": args.run_id,
        "history_rows": len(history_rows),
        "history_seasons": sorted({int(row["season"]) for row in history_rows}),
        "participation_map_sha256": participation_map["map_sha256"],
        "designation_count": selection["designation_count"],
        "pmix_turnover_per_side": selection["membership_turnover_per_side"],
        "book_semantic_sha256": {
            policy: book["semantic_sha256"] for policy, book in books.items()
        },
        "execute": False,
        "entry_allocation_published": False,
        "contest_entries_submitted": False,
    }
    if not args.execute:
        print(json.dumps(summary, sort_keys=True))
        return
    if args.code_sha is None:
        raise RuntimeError("--execute requires --code-sha")
    _check_source(args.code_sha)

    store = storage.GCSImmutableObjectStore()
    source_root = f"{PUBLISH_ROOT}/{args.run_id}/sources"
    source_specs = {
        "D800_DEMAX": {
            "candidates": (paid_dir / "candidates.parquet", "application/octet-stream"),
            "exposure_ledger": (paid_dir / "exposure_ledger.json", "application/json"),
            "receipt": (paid_dir / "receipt.json", "application/json"),
            "frame": (paid_dir / "frame.parquet", "application/octet-stream"),
            "incumbent_scores": (
                paid_dir / "incumbent_player_scores.npy", "application/octet-stream"
            ),
            "corrected_hsim_scores": (
                paid_dir / "corrected_hsim_player_scores.npy",
                "application/octet-stream",
            ),
            "wemax_book": (paid_dir / "book_wemax.json", "application/json"),
            "wemax_csv": (paid_dir / "book_wemax.csv", "text/csv"),
        },
        "D400_DEMAX": {
            "candidates": (shadow_dir / "candidates.parquet", "application/octet-stream"),
            "exposure_ledger": (shadow_dir / "exposure_ledger.json", "application/json"),
            "receipt": (shadow_dir / "receipt.json", "application/json"),
            "frame": (shadow_dir / "frame.parquet", "application/octet-stream"),
        },
    }
    published_sources: dict[str, dict[str, dict[str, object]]] = {}
    for arm, specs in source_specs.items():
        published_sources[arm] = {}
        for name, (path, content_type) in specs.items():
            published_sources[arm][name] = _publish_raw(
                store=store,
                uri=f"{source_root}/{arm}/{path.name}",
                raw=path.read_bytes(),
                content_type=content_type,
            )
    history_publication = _publish_raw(
        store=store,
        uri=f"{source_root}/participation-history.json",
        raw=history_raw,
        content_type="application/json",
    )
    snapshot_publication = _publish_raw(
        store=store,
        uri=f"{source_root}/dk-status-snapshot.json",
        raw=snapshot_raw,
        content_type="application/json",
    )
    source_created = [
        str(receipt["created_at"])
        for arm in published_sources.values()
        for receipt in arm.values()
    ] + [
        str(history_publication["created_at"]),
        str(snapshot_publication["created_at"]),
    ]
    frozen_at = max(
        datetime.fromisoformat(value) for value in source_created
    ).astimezone(UTC).isoformat()
    source_commit = str(adapter["source_commit"])
    paid_metadata = _arm_metadata(
        arm_id=adopted.PAID_ARM_ID,
        purpose="paid",
        lev=160,
        boom=640,
        candidate_ids=list(adapter["paid_candidate_ids"]),
        sources=published_sources["D800_DEMAX"],
        adapter=adapter,
        nfl2_root=nfl2_root,
        source_commit=source_commit,
    )
    shadow_metadata = _arm_metadata(
        arm_id=adopted.SHADOW_ARM_ID,
        purpose="shadow",
        lev=80,
        boom=320,
        candidate_ids=list(adapter["shadow_candidate_ids"]),
        sources=published_sources["D400_DEMAX"],
        adapter=adapter,
        nfl2_root=nfl2_root,
        source_commit=source_commit,
    )
    pair_root = f"{PUBLISH_ROOT}/{args.run_id}/adopted-pair"
    pair_publication = pair_operator.publish_week1_adopted_pair_v1(
        store=store,
        authority={
            "season": 2026,
            "week": 1,
            "draft_group_id": "151307",
            "slate_type": "sunday-main",
            "lock_utc": adopted.WEEK1_LOCK_UTC,
            "frozen_at": frozen_at,
            "outcome_blind": True,
            "outcome_fields_read": [],
        },
        recipe={
            "generation_seed": 2026,
            "selection_seed": 2076,
            "audit_seed": 2126,
            "corrected_hsim_seed": 2326,
            "incumbent_worlds": 10_000,
            "corrected_hsim_worlds": 10_000,
            "decision_worlds": 20_000,
            "law_weighting": "equal-column-mass",
            "selector_recipe": "greedy-expected-weekly-max-v1",
            "tie_break": "first-in-candidate-order-v1",
            "construction_contract": "house_qb2_bb1_floor49_v1",
        },
        paid_arm_metadata=paid_metadata,
        shadow_arm_metadata=shadow_metadata,
        paid_book=adapter["paid_book"],
        shadow_book=adapter["shadow_book"],
        paid_book_uri=f"{pair_root}/D800_DEMAX-book.json",
        shadow_book_uri=f"{pair_root}/D400_DEMAX-book.json",
        manifest_uri=f"{pair_root}/manifest.json",
        observed_at=_now(),
    )

    selection_inputs, selection, participation_map = _build_selection(
        paid_dir=paid_dir,
        frame=paid_frame,
        candidates=paid_candidates,
        history_rows=history_rows,
        history_identity=dict(history_publication["identity"]),
        snapshot_identity=dict(snapshot_publication["identity"]),
        snapshot_created_at=str(snapshot_publication["created_at"]),
    )
    pmix_publication = pmix_operator.publish_week1_participation_package_v1(
        store=store,
        adopted_pair_manifest_identity=pair_publication["manifest_identity"],
        history_source_identity=history_publication["identity"],
        selection_inputs=selection_inputs,
        implementation_identity={
            "id": f"nfl-predictions-week1-pmix@{args.code_sha}",
            "sha256": _file_sha256(Path(pmix.__file__)),
        },
        run_id=args.run_id,
        observed_at=_now(),
    )
    reopened_pmix = pmix_operator.read_week1_participation_package_v1(
        store=store, package_identity=pmix_publication["package_identity"]
    )
    selection = reopened_pmix["selection"]

    book_root = f"{PUBLISH_ROOT}/{args.run_id}/books"
    catalog_publication = capture.publish_semantic_artifact(
        store, uri=f"{book_root}/salary-catalog.json", artifact=catalog,
        not_after=adopted.WEEK1_LOCK_UTC,
    )
    catalog_ref = _semantic_ref(catalog_publication)
    bridge = materializer.build_week1_player_bridge_v1(
        paid_frame, salary_catalog=catalog, salary_catalog_ref=catalog_ref
    )
    bridge_publication = capture.publish_semantic_artifact(
        store, uri=f"{book_root}/player-bridge.json", artifact=bridge,
        not_after=adopted.WEEK1_LOCK_UTC,
    )
    bridge_ref = _semantic_ref(bridge_publication)
    _lineups, books = _lineups_and_books(
        paid_dir=paid_dir,
        shadow_dir=shadow_dir,
        selection=selection,
        bridge=bridge,
        bridge_ref=bridge_ref,
    )
    book_publications = {
        policy: capture.publish_semantic_artifact(
            store,
            uri=f"{book_root}/{policy}.json",
            artifact=book,
            not_after=adopted.WEEK1_LOCK_UTC,
        )
        for policy, book in books.items()
    }
    source_pins = capture.pinned_source_pins()
    terminal = capture.seal_semantic_artifact({
        "schema_version": "week1-a5-four-book-publication/v1",
        "complete": True,
        "season": 2026,
        "week": 1,
        "slate_id": capture.EXPECTED_SLATE_ID,
        "draft_group_id": capture.EXPECTED_DRAFT_GROUP_ID,
        "lock_utc": adopted.WEEK1_LOCK_UTC,
        "source_code_sha": args.code_sha,
        "live_pair_source_commit": source_commit,
        "generation_shadow_safety_identity": GENERATION_SAFETY_IDENTITY,
        "adopted_pair_manifest_identity": pair_publication["manifest_identity"],
        "participation_package_identity": pmix_publication["package_identity"],
        "participation_history_identity": history_publication["identity"],
        "draftkings_status_snapshot_identity": snapshot_publication["identity"],
        "selection_receipt_sha256": selection["selection_receipt_sha256"],
        "salary_catalog": catalog_ref,
        "player_bridge": bridge_ref,
        "books": {
            policy: _semantic_ref(publication)
            for policy, publication in book_publications.items()
        },
        "raw_live_source_identities": {
            arm: {
                name: receipt["identity"] for name, receipt in sources.items()
            }
            for arm, sources in published_sources.items()
        },
        "contest_source_manifest_identity": dict(source_pins.manifest_identity),
        "contest_template_projection_identity": dict(
            source_pins.template_projection_identity or {}
        ),
        "paid_policy": "P_MIX",
        "fallback_policy": "P_CTRL",
        "entry_allocation_published": False,
        "contest_entries_submitted": False,
        "bankroll_recommendation_made": False,
        "uses_target_week_outcomes": False,
    })
    terminal_publication = capture.publish_semantic_artifact(
        store,
        uri=f"{PUBLISH_ROOT}/{args.run_id}/terminal.json",
        artifact=terminal,
        not_after=adopted.WEEK1_LOCK_UTC,
    )
    summary.update({
        "execute": True,
        "adopted_pair_manifest_identity": pair_publication["manifest_identity"],
        "participation_package_identity": pmix_publication["package_identity"],
        "salary_catalog": catalog_ref,
        "player_bridge": bridge_ref,
        "books": {
            policy: _semantic_ref(publication)
            for policy, publication in book_publications.items()
        },
        "terminal": _semantic_ref(terminal_publication),
    })
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
