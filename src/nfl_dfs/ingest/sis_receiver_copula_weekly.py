"""Append-once warehouse intake for the frozen 2026 SIS receiver-copula weekly exports.

Protocol ``sis-receiver-copula-weekly-v1`` (``automation/sis/plans/receiver-copula-weekly-2026-v1.json``, pinned by
``sis.RECEIVER_COPULA_WEEKLY_PROTOCOL_SHA256``): target week W reads only the wide and slot CB-vs-WR games of week
W-1. The rows append once into the historical player-game table (an identical re-run is a no-op; a different source
hash for an existing key fails closed), the licensed CSVs are archived by content hash, and the strictly prior defense
context for W is recomputed with ``build_defense_prior`` over every warehouse game before W. A prior row's
``source_sha256`` is the hash of the source-file hashes it read, so a changed input can never silently replace a
written row. Nothing on the money path reads either table.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from . import sis_receiver_copula as history
from .sis_pass_tail_weekly import _novel_or_identical, archive_once
from ..ops import sis_downloads as sis


SEASON = 2026
PLAYER_KEYS = ["season", "week", "alignment", "defender_player_id", "defender_team_id"]
PRIOR_KEYS = ["season", "target_week", "defense", "alignment"]
GAME_COLUMNS = [
    *PLAYER_KEYS, "defense", "coverage_snaps", "targets", "completions",
    "yards", "touchdowns", "source_sha256",
]


def _load_manifest(input_dir: str | Path, *, target_week: int) -> tuple[Path, dict]:
    root = Path(input_dir)
    manifest = json.loads(
        (root / "receiver-copula-weekly.manifest.json").read_text(encoding="utf-8")
    )
    result = json.loads(
        (root / "receiver-copula-weekly.result.json").read_text(encoding="utf-8")
    )
    if int(manifest.get("target_week", -1)) != int(target_week):
        raise ValueError("SIS receiver-copula weekly target week differs")
    reproduced = sis.analyze_receiver_copula_weekly_acquisition(root, manifest)
    if result != reproduced or not result.get("passes"):
        raise ValueError("SIS receiver-copula weekly acquisition did not reproduce")
    return root, manifest


def read_export(
    input_dir: str | Path, *, target_week: int,
) -> tuple[Path, dict, pd.DataFrame]:
    """Reproduce the weekly acquisition gate and parse its week W-1 defender-game rows."""
    root, manifest = _load_manifest(input_dir, target_week=target_week)
    rows = history.player_game_rows(root, manifest["artifacts"])
    if not (rows.season.eq(SEASON) & rows.week.eq(int(target_week) - 1)).all():
        raise ValueError("SIS receiver-copula weekly row lies outside source week W-1")
    rows["source_run_id"] = str(manifest["acquisition_identity"])
    return root, manifest, rows


def source_week_completeness(
    rows: pd.DataFrame, schedule: pd.DataFrame, *, source_week: int,
) -> dict:
    """Every team scheduled in W-1 defends in the union of both alignments, against its scheduled opponent.

    An append-once table must never lock in a week SIS has not finished charting.
    """
    games = schedule[schedule.week.astype(int).eq(int(source_week))]
    scheduled = set(zip(games.team.astype(str), games.opponent.astype(str)))
    defenses = {team for team, _ in scheduled}
    missing = sorted(defenses - set(rows.defense))
    unscheduled = sorted(
        f"{defense}-{offense}"
        for defense, offense in set(zip(rows.defense, rows.offense)) - scheduled
    )
    return {
        "complete": not missing and not unscheduled,
        "scheduled_defenses": len(defenses),
        "missing_defenses": missing,
        "unscheduled_pairs": unscheduled,
    }


def defense_prior(
    games: pd.DataFrame, schedule: pd.DataFrame, *, target_week: int, run_id: str,
) -> tuple[pd.DataFrame | None, dict]:
    """The strictly prior context for (2026, W); withheld (and recorded) while a 2026 source week is absent."""
    target_week = int(target_week)
    games = games[
        games.season.lt(SEASON) | (games.season.eq(SEASON) & games.week.lt(target_week))
    ]
    current = games[games.season.eq(SEASON)]
    have = set(zip(current.week.astype(int), current.alignment))
    missing = sorted({
        week for week in range(1, target_week)
        for alignment, _values in sis.RECEIVER_COPULA_ALIGNMENTS
        if (week, alignment) not in have
    })
    if missing:
        return None, {"disposition": "withheld", "missing_2026_source_weeks": missing}
    prior, audit = history.build_defense_prior(
        games, schedule, seasons=(SEASON,), target_weeks=(target_week,),
    )
    input_sha256 = hashlib.sha256(
        "\n".join(sorted(set(games.source_sha256.astype(str)))).encode()
    ).hexdigest()
    prior["source_run_id"] = run_id
    prior["source_sha256"] = input_sha256
    for column in (
        "source_first_season", "source_first_week",
        "source_last_season", "source_last_week",
    ):
        prior[column] = prior[column].astype("Int64")
    # fewer than MIN_PRIOR_GAMES (or no coverage/targets) is recorded per cell, never a failed import
    unsupported = prior[~prior.context_supported.astype(bool)]
    audit.update({
        "disposition": "computed",
        "input_rows": int(len(games)),
        "input_sha256": input_sha256,
        "unsupported_cells": [
            f"{row.defense}:{row.alignment}:{int(row.prior_games)}"
            for row in unsupported.itertuples(index=False)
        ],
    })
    return prior, audit


def run(input_dir: str | Path, *, target_week: int, write: bool = False) -> dict:
    """Audit one target week's rows and prior; with ``write`` archive the CSVs and append both once."""
    from ..bq import load_dataframe, query_df
    from ..config import settings

    target_week = int(target_week)
    source_week = target_week - 1
    root, manifest, rows = read_export(input_dir, target_week=target_week)
    player_ref = f"{settings.raw}.{history.PLAYER_GAME_TABLE}"
    prior_ref = f"{settings.raw}.{history.DEFENSE_PRIOR_TABLE}"
    params = {"season": SEASON, "target_week": target_week}
    games = query_df(f"""
        SELECT {', '.join(GAME_COLUMNS)}
        FROM `{player_ref}`
        WHERE season < @season OR (season = @season AND week < @target_week)
        """, params=params)
    schedule = query_df(f"""
        SELECT CAST(season AS INT64) AS season, CAST(week AS INT64) AS week,
               home_team AS team, away_team AS opponent
        FROM `{settings.raw}.schedules`
        WHERE season = @season AND week IN (@target_week - 1, @target_week)
          AND game_type = 'REG'
        UNION ALL
        SELECT CAST(season AS INT64) AS season, CAST(week AS INT64) AS week,
               away_team AS team, home_team AS opponent
        FROM `{settings.raw}.schedules`
        WHERE season = @season AND week IN (@target_week - 1, @target_week)
          AND game_type = 'REG'
        """, params=params)
    in_week = games.season.eq(SEASON) & games.week.eq(source_week)
    novel_rows = _novel_or_identical(
        rows, games[in_week], keys=PLAYER_KEYS, hash_columns=["source_sha256"],
    )
    completeness = source_week_completeness(rows, schedule, source_week=source_week)
    prior, prior_audit = defense_prior(
        pd.concat([games[~in_week], rows[GAME_COLUMNS]], ignore_index=True),
        schedule, target_week=target_week,
        run_id=str(manifest["acquisition_identity"]),
    )
    novel_prior = None
    if prior is not None:
        existing_prior = query_df(f"""
            SELECT {', '.join([*PRIOR_KEYS, 'source_sha256'])}
            FROM `{prior_ref}`
            WHERE season = @season AND target_week = @target_week
            """, params=params)
        novel_prior = _novel_or_identical(
            prior, existing_prior, keys=PRIOR_KEYS, hash_columns=["source_sha256"],
        )
    audit = {
        "version": sis.RECEIVER_COPULA_WEEKLY_VERSION,
        "protocol_sha256": manifest["protocol_sha256"],
        "source_run_id": manifest["acquisition_identity"],
        "season": SEASON,
        "target_week": target_week,
        "source_week": source_week,
        "player_table": player_ref,
        "prior_table": prior_ref,
        "rows": int(len(rows)),
        "defenses": int(rows.defense.nunique()),
        "append_player_rows": int(len(novel_rows)),
        "source_week_completeness": completeness,
        "prior": prior_audit,
        "append_prior_rows": None if novel_prior is None else int(len(novel_prior)),
        "write_requested": bool(write),
        "point_in_time_contract": "rows of week W-1 only; the prior reads only games strictly before W",
    }
    if write:
        if not completeness["complete"]:
            raise RuntimeError(
                f"SIS receiver-copula week {source_week} is incomplete "
                f"({completeness}); nothing archived or appended"
            )
        audit["archives"] = archive_once(
            root, manifest["artifacts"], settings.gcs_bucket,
            prefix=f"licensed/sis/receiver-copula/season={SEASON}/week={source_week:02d}",
        )
        now = datetime.now(UTC)
        for label, ref, novel in (
            ("player", player_ref, novel_rows), ("prior", prior_ref, novel_prior),
        ):
            if novel is None:
                audit[f"{label}_write_disposition"] = "withheld"
            elif novel.empty:
                audit[f"{label}_write_disposition"] = "already-identical"
            else:
                payload = novel.copy()
                payload["ingested_at"] = now
                load_dataframe(payload, ref, write_disposition="WRITE_APPEND")
                audit[f"{label}_write_disposition"] = "appended"
    print("SIS_RECEIVER_COPULA_WEEKLY_IMPORT_JSON=" + json.dumps(audit, sort_keys=True))
    return audit


__all__ = [
    "defense_prior", "read_export", "run", "source_week_completeness",
]
