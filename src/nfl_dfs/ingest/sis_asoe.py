"""Strictly-prior SIS alignment share over expectation construction."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .sis_team_context import TEAM_ABBREVIATIONS
from ..ops import sis_downloads as sis


MIN_DEFENSE_ATTEMPTS = 40.0
MIN_EXPECTED_COVERAGE = 0.80
SHRINKAGE_ATTEMPTS = 40.0
TABLE = "sis_alignment_attempt_game"
SOURCE_RUN = "sis-team-pass-defense-asoe-v1"


def read_attempts(input_dir: str | Path) -> tuple[pd.DataFrame, dict]:
    """Read only identity and `Att` from the validated ASOE acquisition."""
    root = Path(input_dir)
    manifest = json.loads(
        (root / "team-pass-defense-asoe.manifest.json").read_text())
    result = json.loads(
        (root / "team-pass-defense-asoe.result.json").read_text())
    if not result.get("passes") or result.get("performance_values_read") != []:
        raise ValueError("SIS ASOE acquisition did not pass cleanly")
    verified = sis.analyze_team_pass_defense_asoe_acquisition(root, manifest)
    if verified != result:
        raise ValueError("SIS ASOE acquisition result does not reproduce")
    records: list[dict] = []
    for item in manifest["artifacts"]:
        path = root / item["artifact"]
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        identities = {
            (
                int(row["season"]), int(row["week"]),
                str(row["team"]), str(row["opp"]),
            ): int(row["teamId"])
            for row in item["identities"]
        }
        for row in rows:
            key = (
                int(row["Season"]), int(row["Week"]),
                str(row["Team"]), str(row["Opp."]),
            )
            if key not in identities:
                raise ValueError(f"{path.name} row lacks its SIS identity")
            if key[2] not in TEAM_ABBREVIATIONS or key[3] not in TEAM_ABBREVIATIONS:
                raise ValueError(f"{path.name} has an unknown team name")
            attempts = float(str(row["Att"]).replace(",", ""))
            if not attempts.is_integer() or attempts < 0:
                raise ValueError(f"{path.name} has an invalid included attempt")
            records.append({
                "season": key[0], "week": key[1],
                "defense": TEAM_ABBREVIATIONS[key[2]],
                "offense": TEAM_ABBREVIATIONS[key[3]],
                "team_id": identities[key],
                "alignment": item["alignment"],
                "attempts": int(attempts),
                "source_sha256": item["sha256"],
            })
    frame = pd.DataFrame(records)
    if frame.duplicated(["season", "week", "defense", "alignment"]).any():
        raise ValueError("SIS ASOE rows repeat defense-week-alignment")
    return frame, {
        "rows": int(len(frame)),
        "attempts": int(frame.attempts.sum()),
        "artifacts": int(len(manifest["artifacts"])),
        "protocol_sha256": manifest["protocol_sha256"],
        "performance_values_read": [],
    }


def build_defense_asoe(
    attempts: pd.DataFrame,
    offense_profiles: pd.DataFrame,
    schedule: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Build target-week ASOE on an explicit schedule spine."""
    schedule_needed = {"season", "week", "team", "opponent"}
    if missing := schedule_needed - set(schedule):
        raise ValueError(f"ASOE schedule missing {sorted(missing)}")
    spine = schedule[list(schedule_needed)].drop_duplicates().copy()
    # Week 18 was deliberately not acquired: the latest target Week 18
    # window ends at Week 17. Do not require an out-of-scope source game.
    spine = spine[spine.week.between(1, 17)].copy()
    if spine.duplicated(["season", "week", "team"]).any():
        raise ValueError("ASOE schedule repeats team-week")
    if attempts.duplicated(["season", "week", "defense", "alignment"]).any():
        raise ValueError("ASOE attempts repeat defense-week-alignment")
    wide = attempts[attempts.alignment.eq("wide")].rename(
        columns={"defense": "team", "offense": "opponent", "attempts": "wide_attempts"}
    )[["season", "week", "team", "opponent", "wide_attempts"]]
    slot = attempts[attempts.alignment.eq("slot")].rename(
        columns={"defense": "team", "offense": "opponent", "attempts": "slot_attempts"}
    )[["season", "week", "team", "opponent", "slot_attempts"]]
    games = spine.merge(
        wide, on=["season", "week", "team", "opponent"],
        how="left", validate="one_to_one",
    ).merge(
        slot, on=["season", "week", "team", "opponent"],
        how="left", validate="one_to_one",
    )
    games[["wide_attempts", "slot_attempts"]] = games[
        ["wide_attempts", "slot_attempts"]
    ].fillna(0.0)
    games["combined_attempts"] = games.wide_attempts + games.slot_attempts
    if (games.combined_attempts <= 0).any():
        bad = games.loc[games.combined_attempts.le(0), ["season", "week", "team"]]
        raise ValueError(f"ASOE schedule has games with no Wide/Slot attempts: {bad.head().to_dict('records')}")

    profile = offense_profiles[
        ["season", "target_week", "team", "offense_wide_share", "offense_alignment_supported"]
    ].rename(columns={
        "target_week": "asof_week", "team": "opponent",
        "offense_wide_share": "opponent_wide_share",
        "offense_alignment_supported": "opponent_profile_supported",
    })
    outputs: list[dict] = []
    for season in sorted(spine.season.unique()):
        for target_week in range(5, 19):
            source = games[
                games.season.eq(season)
                & games.week.between(target_week - 4, target_week - 1)
            ].copy()
            if source.empty:
                continue
            source = source.merge(
                profile[profile.season.eq(season) & profile.asof_week.eq(target_week)],
                on=["season", "opponent"], how="left", validate="many_to_one",
            )
            for defense, group in source.groupby("team", sort=True):
                total = float(group.combined_attempts.sum())
                observed = float(group.wide_attempts.sum() / total)
                covered = group.opponent_profile_supported.fillna(False).astype(bool)
                covered_attempts = float(group.loc[covered, "combined_attempts"].sum())
                coverage = covered_attempts / total if total else 0.0
                expected = (
                    float(np.average(
                        group.loc[covered, "opponent_wide_share"],
                        weights=group.loc[covered, "combined_attempts"],
                    )) if covered_attempts else np.nan
                )
                supported = bool(
                    total >= MIN_DEFENSE_ATTEMPTS
                    and coverage >= MIN_EXPECTED_COVERAGE
                    and np.isfinite(expected)
                )
                asoe = (
                    (observed - expected) * total / (total + SHRINKAGE_ATTEMPTS)
                    if supported else 0.0
                )
                outputs.append({
                    "season": int(season), "target_week": target_week,
                    "defense": str(defense),
                    "source_week_start": target_week - 4,
                    "source_week_end": target_week - 1,
                    "prior_games": int(len(group)),
                    "combined_attempts": total,
                    "observed_wide_share": observed,
                    "expected_wide_share": expected,
                    "expected_attempt_coverage": coverage,
                    "defense_asoe": asoe,
                    "asoe_supported": supported,
                })
    out = pd.DataFrame(outputs)
    if out.duplicated(["season", "target_week", "defense"]).any():
        raise ValueError("ASOE output repeats defense-target-week")
    if not out.source_week_end.lt(out.target_week).all():
        raise ValueError("ASOE output violates point-in-time scope")
    return out, {
        "rows": int(len(out)),
        "supported_rows": int(out.asoe_supported.sum()),
        "supported_fraction": float(out.asoe_supported.mean()),
        "structural_zero_cells_reconstructed": int(
            games.wide_attempts.eq(0).sum() + games.slot_attempts.eq(0).sum()
        ),
    }


def run(input_dir: str | Path, *, write: bool = False) -> dict:
    from .fantasy_points_same_season_coverage import _write_once
    from ..config import settings

    rows, audit = read_attempts(input_dir)
    rows["source_run_id"] = SOURCE_RUN
    table_ref = f"{settings.raw}.{TABLE}"
    audit.update({"table": table_ref, "write_requested": bool(write)})
    if write:
        audit["write_disposition"] = _write_once(
            table_ref, rows, run_id=SOURCE_RUN,
            hash_columns=("source_sha256",),
        )
    print("SIS_ASOE_IMPORT_JSON=" + json.dumps(audit, sort_keys=True))
    return audit


__all__ = ["build_defense_asoe", "read_attempts", "run"]
